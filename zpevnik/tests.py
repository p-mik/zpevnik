import io
import json
import os
import shutil
import tempfile
from io import StringIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader, PdfWriter
from rest_framework import status
from rest_framework.test import APIClient

from .apps import zkontroluj_servirovani_souboru
from .models import (
    Anotace,
    Pisen,
    PolozkaSetlistu,
    PolozkaZpevniku,
    Setlist,
    Slozka,
    VerzePisne,
    Zpevnik,
)
from .serializers import AkordovyZapisSerializer

# Minimální, ale platné PDF (rozhodují úvodní magic bytes "%PDF-").
PDF_OBSAH = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


def pdf_upload(nazev="noty.pdf", obsah=PDF_OBSAH):
    return SimpleUploadedFile(nazev, obsah, content_type="application/pdf")


def vicestrankove_pdf_bytes(pocet_stran):
    """Skutečně platné PDF (na rozdíl od PDF_OBSAH výše) — potřebuje ho pypdf
    umět reálně otevřít a rozřezat, ne jen projít kontrolou magic bytes."""
    writer = PdfWriter()
    for _ in range(pocet_stran):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class ZpevnikTokenViditelnostTests(TestCase):
    """Token je sdílitelný odkaz — čitelný jen pro admina, ne pro každého člena."""

    def setUp(self):
        self.client = APIClient()
        self.zpevnik = Zpevnik.objects.create(nazev="Interní zpěvník")
        self.zpevnik.vygeneruj_verejny_token()
        self.clen = User.objects.create_user("clen_token", password="heslo123")
        self.admin = User.objects.create_user(
            "admin_token", password="heslo123", is_staff=True
        )

    def test_clen_nevidi_token(self):
        self.client.force_authenticate(self.clen)
        response = self.client.get(f"/api/zpevniky/{self.zpevnik.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["verejny_token"])

    def test_admin_vidi_token(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/zpevniky/{self.zpevnik.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["verejny_token"], self.zpevnik.verejny_token)

    def test_clen_nevidi_token_ani_v_seznamu(self):
        self.client.force_authenticate(self.clen)
        response = self.client.get("/api/zpevniky/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tokeny = [z["verejny_token"] for z in response.data["results"]]
        self.assertTrue(all(t is None for t in tokeny))


class VerejnyZpevnikTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.pisen = Pisen.objects.create(nazev="Testovací píseň")
        self.cizi_pisen = Pisen.objects.create(nazev="Jiná píseň")

        self.zpevnik = Zpevnik.objects.create(nazev="Testovací zpěvník")
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=self.pisen, kod=1)
        self.zpevnik.vygeneruj_verejny_token()

        self.jiny_zpevnik = Zpevnik.objects.create(nazev="Jiný zpěvník")
        PolozkaZpevniku.objects.create(zpevnik=self.jiny_zpevnik, pisen=self.cizi_pisen, kod=2)
        self.jiny_zpevnik.vygeneruj_verejny_token()

        self.clen = User.objects.create_user("clen_verejny", password="heslo123")
        VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_PERSONAL, vlastnik=self.clen
        )
        self.confirmed = VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_CONFIRMED
        )

    def test_verejny_zpevnik_vraci_jen_svoje_pisne(self):
        url = reverse("verejny-zpevnik", args=[self.zpevnik.verejny_token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nazev"], "Testovací zpěvník")
        kody = [p["kod"] for p in response.data["pisne"]]
        self.assertEqual(kody, [1])
        self.assertNotIn(2, kody)

    def test_verejny_zpevnik_neprozrazuje_personal_verzi_ani_vlastniky(self):
        url = reverse("verejny-zpevnik", args=[self.zpevnik.verejny_token])
        response = self.client.get(url)
        pisen_data = response.data["pisne"][0]
        # confirmed verze musí vyhrát, ne cizí personal
        self.assertEqual(pisen_data["aktivni_verze"]["typ_obsahu"], "pdf")
        self.assertNotIn("vlastnik", pisen_data["aktivni_verze"])
        self.assertNotIn("stav", pisen_data["aktivni_verze"])

    def test_odpoved_neobsahuje_id_ani_jine_zpevniky(self):
        url = reverse("verejny-zpevnik", args=[self.zpevnik.verejny_token])
        response = self.client.get(url)
        self.assertNotIn("id", response.data)
        self.assertNotIn("verejny_token", response.data)
        text = str(response.data)
        self.assertNotIn("Jiný zpěvník", text)

    def test_neplatny_token_vraci_404(self):
        url = reverse("verejny-zpevnik", args=["neexistujici-token"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_zpevnik_bez_tokenu_je_nedostupny(self):
        Zpevnik.objects.create(nazev="Bez odkazu")
        url = reverse("verejny-zpevnik", args=["cokoliv"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NeprihlasenyPristupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Pisen.objects.create(nazev="Skrytá píseň")

    def test_seznam_pisni_vyzaduje_prihlaseni(self):
        response = self.client.get("/api/pisne/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ostatni_endpointy_vyzaduji_prihlaseni(self):
        chranene = [
            "/api/verze-pisni/",
            "/api/slozky/",
            "/api/zpevniky/",
            "/api/setlisty/",
            "/api/polozky-setlistu/",
        ]
        for url in chranene:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_me_bez_prihlaseni(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["authenticated"])


class ClenEditaceCiziPersonalVerzeTests(TestCase):
    def setUp(self):
        self.pisen = Pisen.objects.create(nazev="Sdílená píseň")
        self.alice = User.objects.create_user("alice", password="heslo123")
        self.bob = User.objects.create_user("bob", password="heslo123")
        self.verze = VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_PERSONAL, vlastnik=self.alice
        )
        self.client = APIClient()

    def test_clen_nemuze_editovat_cizi_personal_verzi(self):
        self.client.force_authenticate(self.bob)
        url = f"/api/verze-pisni/{self.verze.id}/"
        response = self.client.patch(url, {"stav": "confirmed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_clen_nemuze_smazat_cizi_personal_verzi(self):
        self.client.force_authenticate(self.bob)
        url = f"/api/verze-pisni/{self.verze.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(VerzePisne.objects.filter(id=self.verze.id).exists())

    def test_vlastnik_muze_editovat_svoji_personal_verzi(self):
        self.client.force_authenticate(self.alice)
        url = f"/api/verze-pisni/{self.verze.id}/"
        response = self.client.patch(url, {"typ_obsahu": "pdf"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_clen_vytvori_verzi_vzdy_jako_vlastni_personal(self):
        self.client.force_authenticate(self.bob)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        nova = VerzePisne.objects.get(id=response.data["id"])
        self.assertEqual(nova.stav, VerzePisne.STAV_PERSONAL)
        self.assertEqual(nova.vlastnik_id, self.bob.id)


class AktivniVerzeLogikaTests(TestCase):
    def setUp(self):
        self.pisen = Pisen.objects.create(nazev="Logika verzí")
        self.uzivatel = User.objects.create_user("clen2", password="heslo123")
        self.jiny = User.objects.create_user("clen3", password="heslo123")

    def test_bez_verze_vraci_none(self):
        self.assertIsNone(self.pisen.aktivni_verze(user=self.uzivatel))

    def test_vrati_nejnovejsi_pri_absenci_personal_a_confirmed(self):
        VerzePisne.objects.create(pisen=self.pisen, stav=VerzePisne.STAV_DRAFT)
        nova = VerzePisne.objects.create(pisen=self.pisen, stav=VerzePisne.STAV_DOWNLOAD)
        vysledek = self.pisen.aktivni_verze(user=self.uzivatel)
        self.assertEqual(vysledek, nova)

    def test_confirmed_ma_prednost_pred_cimkoliv_jinym(self):
        VerzePisne.objects.create(pisen=self.pisen, stav=VerzePisne.STAV_DOWNLOAD)
        potvrzena = VerzePisne.objects.create(pisen=self.pisen, stav=VerzePisne.STAV_CONFIRMED)
        vysledek = self.pisen.aktivni_verze(user=self.uzivatel)
        self.assertEqual(vysledek, potvrzena)

    def test_personal_ma_nejvyssi_prioritu(self):
        VerzePisne.objects.create(pisen=self.pisen, stav=VerzePisne.STAV_CONFIRMED)
        moje = VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_PERSONAL, vlastnik=self.uzivatel
        )
        vysledek = self.pisen.aktivni_verze(user=self.uzivatel)
        self.assertEqual(vysledek, moje)

    def test_cizi_personal_verzi_nevidi(self):
        VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_PERSONAL, vlastnik=self.jiny
        )
        vysledek = self.pisen.aktivni_verze(user=self.uzivatel)
        self.assertIsNone(vysledek)

    def test_anonymni_uzivatel_nikdy_nedostane_personal(self):
        VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_PERSONAL, vlastnik=self.uzivatel
        )
        vysledek = self.pisen.aktivni_verze(user=None)
        self.assertIsNone(vysledek)


class CsrfEnforcementTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            "staff1", password="heslo123", is_staff=True
        )

    def test_post_bez_csrf_tokenu_selze(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="staff1", password="heslo123")
        response = client.post(
            "/api/pisne/",
            data={"nazev": "Bez CSRF"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_s_platnym_csrf_tokenem_projde(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="staff1", password="heslo123")
        client.get("/api/auth/me/")  # nastaví csrftoken cookie (ensure_csrf_cookie)
        csrftoken = client.cookies["csrftoken"].value
        response = client.post(
            "/api/pisne/",
            data={"nazev": "S CSRF"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrftoken,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class SouboroveTestyZaklad(TestCase):
    """Společný základ — každý test si nese vlastní dočasné MEDIA_ROOT."""

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="zpevnik-test-")
        prepinac = override_settings(MEDIA_ROOT=self.media, X_ACCEL_REDIRECT=True)
        prepinac.enable()
        self.addCleanup(prepinac.disable)
        self.addCleanup(shutil.rmtree, self.media, True)

        self.client = APIClient()
        self.admin = User.objects.create_user(
            "admin_soubor", password="heslo123", is_staff=True
        )
        self.alice = User.objects.create_user("alice_soubor", password="heslo123")
        self.bob = User.objects.create_user("bob_soubor", password="heslo123")

    def nahraj(self, pisen, stav, vlastnik=None, nazev="noty.pdf"):
        """Vytvoří verzi se souborem přímo přes model (obchází API)."""
        verze = VerzePisne.objects.create(pisen=pisen, stav=stav, vlastnik=vlastnik)
        verze.soubor.save(nazev, pdf_upload(nazev), save=True)
        return verze


class UploadPdfTests(SouboroveTestyZaklad):
    def setUp(self):
        super().setUp()
        self.pisen = Pisen.objects.create(nazev="Píseň s notami")

    def test_admin_nahraje_pdf(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "soubor": pdf_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertTrue(verze.soubor)
        self.assertEqual(verze.stav, VerzePisne.STAV_CONFIRMED)
        self.assertEqual(verze.puvodni_nazev_souboru, "noty.pdf")

    def test_clen_nahraje_jen_vlastni_personal(self):
        self.client.force_authenticate(self.bob)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "soubor": pdf_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        verze = VerzePisne.objects.get(id=response.data["id"])
        # Člen si nemůže vynutit confirmed — server dosadí personal + sebe.
        self.assertEqual(verze.stav, VerzePisne.STAV_PERSONAL)
        self.assertEqual(verze.vlastnik_id, self.bob.id)

    def test_admin_nahraje_osobni_verzi_a_dostane_ji_do_vlastnictvi(self):
        """Osobní verze bez vlastníka by byla nedostupná i svému autorovi —
        Pisen.aktivni_verze() páruje osobní verze právě přes vlastníka, a
        `vlastnik` je v serializeru read-only, takže ho musí dosadit server."""
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "personal", "soubor": pdf_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertEqual(verze.stav, VerzePisne.STAV_PERSONAL)
        self.assertEqual(verze.vlastnik_id, self.admin.id)
        # A rovnou se i nabídne jako aktivní verze pro svého autora.
        self.assertEqual(self.pisen.aktivni_verze(user=self.admin).id, verze.id)

    def test_adminova_neosobni_verze_zustava_bez_vlastnika(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "soubor": pdf_upload()},
            format="multipart",
        )
        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertIsNone(verze.vlastnik_id)

    def test_admin_upravou_nepreveme_cizi_osobni_verzi(self):
        verze = self.nahraj(self.pisen, VerzePisne.STAV_PERSONAL, vlastnik=self.bob)
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/api/verze-pisni/{verze.id}/", {"typ_obsahu": "pdf"}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        verze.refresh_from_db()
        self.assertEqual(verze.vlastnik_id, self.bob.id)

    def test_neni_pdf_jen_prejmenovane(self):
        self.client.force_authenticate(self.admin)
        png = SimpleUploadedFile(
            "podvrh.pdf", b"\x89PNG\r\n\x1a\n" + b"x" * 100, content_type="application/pdf"
        )
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "soubor": png},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("soubor", response.data)

    def test_prazdny_soubor_odmitnut(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/",
            {
                "pisen": self.pisen.id,
                "stav": "confirmed",
                "soubor": SimpleUploadedFile("prazdny.pdf", b""),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(MAX_UPLOAD_SIZE=1024)
    def test_prilis_velky_soubor_odmitnut(self):
        self.client.force_authenticate(self.admin)
        velky = pdf_upload("velky.pdf", PDF_OBSAH + b"x" * 5000)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "soubor": velky},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_path_traversal_ve_jmene_souboru_neuspeje(self):
        self.client.force_authenticate(self.admin)
        zakerny = pdf_upload("../../../../etc/passwd.pdf")
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "soubor": zakerny},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        verze = VerzePisne.objects.get(id=response.data["id"])
        # 1) cesta v DB je serverem generovaná, bez traversalu
        self.assertTrue(verze.soubor.name.startswith("verze/"))
        self.assertNotIn("..", verze.soubor.name)
        self.assertNotIn("etc", verze.soubor.name)
        # 2) soubor fyzicky leží uvnitř MEDIA_ROOT
        skutecna = os.path.realpath(verze.soubor.path)
        self.assertTrue(skutecna.startswith(os.path.realpath(self.media) + os.sep))
        # 3) původní jméno je uložené jen jako očištěný popisek
        self.assertEqual(verze.puvodni_nazev_souboru, "passwd.pdf")

    def test_windowsovska_cesta_ve_jmene_je_ocistena(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/",
            {
                "pisen": self.pisen.id,
                "stav": "confirmed",
                "soubor": pdf_upload("C:\\Users\\petr\\tajne\\noty.pdf"),
            },
            format="multipart",
        )
        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertEqual(verze.puvodni_nazev_souboru, "noty.pdf")
        self.assertNotIn("\\", verze.soubor.name)

    def test_api_neprozradi_cestu_k_souboru(self):
        verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        self.client.force_authenticate(self.bob)
        response = self.client.get(f"/api/verze-pisni/{verze.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("soubor", response.data)
        self.assertTrue(response.data["ma_soubor"])


class StahovaniSouboruTests(SouboroveTestyZaklad):
    def setUp(self):
        super().setUp()
        self.pisen = Pisen.objects.create(nazev="Píseň ke stažení")
        self.bezna = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        self.personal_alice = self.nahraj(
            self.pisen, VerzePisne.STAV_PERSONAL, vlastnik=self.alice
        )

    def url(self, verze):
        return f"/api/verze-pisni/{verze.id}/soubor/"

    def test_neprihlaseny_nedostane_soubor(self):
        response = self.client.get(self.url(self.bezna))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("X-Accel-Redirect", response)

    def test_clen_dostane_beznou_verzi(self):
        self.client.force_authenticate(self.bob)
        response = self.client.get(self.url(self.bezna))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["X-Accel-Redirect"], "/protected/" + self.bezna.soubor.name
        )
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))

    def test_clen_nedostane_cizi_personal_verzi(self):
        self.client.force_authenticate(self.bob)
        response = self.client.get(self.url(self.personal_alice))
        # 404, ne 403 — cizí personal verze nemá dát vědět ani že existuje.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn("X-Accel-Redirect", response)

    def test_vlastnik_dostane_svoji_personal_verzi(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.url(self.personal_alice))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_dostane_i_cizi_personal_verzi(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url(self.personal_alice))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_verze_bez_souboru_vraci_404(self):
        prazdna = VerzePisne.objects.create(
            pisen=self.pisen, stav=VerzePisne.STAV_DRAFT
        )
        self.client.force_authenticate(self.bob)
        response = self.client.get(self.url(prazdna))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_neexistujici_verze_vraci_404(self):
        self.client.force_authenticate(self.bob)
        response = self.client.get("/api/verze-pisni/999999/soubor/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cesta_v_x_accel_jde_z_databaze_ne_z_requestu(self):
        self.client.force_authenticate(self.bob)
        ocekavana = "/protected/" + self.bezna.soubor.name

        # Ať klient přihodí do requestu cokoliv, hlavička se nehne.
        pokusy = [
            "?soubor=/etc/passwd",
            "?path=../../../../etc/passwd",
            "?soubor=../../../etc/shadow&filename=x.pdf",
        ]
        for dotaz in pokusy:
            response = self.client.get(
                self.url(self.bezna) + dotaz,
                HTTP_X_ACCEL_REDIRECT="/protected/../../etc/passwd",
                HTTP_X_ORIGINAL_URL="/protected/../../etc/passwd",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, dotaz)
            self.assertEqual(response["X-Accel-Redirect"], ocekavana, dotaz)
            self.assertNotIn("..", response["X-Accel-Redirect"])


class VerejnyPristupKSouboruTests(SouboroveTestyZaklad):
    def setUp(self):
        super().setUp()
        # Zpěvník s tokenem: jedna píseň s confirmed verzí, jedna jen s personal.
        self.pisen = Pisen.objects.create(nazev="Veřejná píseň")
        self.jen_personal = Pisen.objects.create(nazev="Jen osobní verze")
        self.bezna = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        self.personal = self.nahraj(
            self.jen_personal, VerzePisne.STAV_PERSONAL, vlastnik=self.alice
        )

        self.zpevnik = Zpevnik.objects.create(nazev="Veřejný zpěvník")
        self.kod = 700
        self.kod_jen_personal = 701
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=self.pisen, kod=self.kod)
        PolozkaZpevniku.objects.create(
            zpevnik=self.zpevnik, pisen=self.jen_personal, kod=self.kod_jen_personal
        )
        self.token = self.zpevnik.vygeneruj_verejny_token()

        # Píseň mimo tenhle zpěvník (je v jiném, taky veřejném) — SCHVÁLNĚ se
        # stejným kódem jako `self.pisen` výš: kolize čísel mezi dvěma
        # nezávislými zpěvníky je teď v pořádku, kolidovat smí jen v rámci
        # JEDNOHO (viz PolozkaZpevniku.Meta.constraints).
        self.cizi_pisen = Pisen.objects.create(nazev="Cizí píseň")
        self.cizi_verze = self.nahraj(self.cizi_pisen, VerzePisne.STAV_CONFIRMED)
        self.jiny_zpevnik = Zpevnik.objects.create(nazev="Jiný zpěvník")
        self.kod_cizi = self.kod
        PolozkaZpevniku.objects.create(
            zpevnik=self.jiny_zpevnik, pisen=self.cizi_pisen, kod=self.kod_cizi
        )
        self.jiny_token = self.jiny_zpevnik.vygeneruj_verejny_token()

    def url(self, token, kod):
        return f"/api/verejny/{token}/pisen/{kod}/soubor/"

    def test_verejny_token_da_soubor_bez_prihlaseni(self):
        response = self.client.get(self.url(self.token, self.kod))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["X-Accel-Redirect"], "/protected/" + self.bezna.soubor.name
        )

    def test_verejny_token_nikdy_neda_personal_verzi(self):
        response = self.client.get(self.url(self.token, self.kod_jen_personal))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn("X-Accel-Redirect", response)

    def test_verejny_token_neda_neexistujici_kod(self):
        response = self.client.get(self.url(self.token, 999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_stejny_kod_ve_dvou_zpevnicich_se_nemicha(self):
        # Stejné číslo (self.kod_cizi == self.kod) existuje ve DVOU různých
        # zpěvnících nezávisle na sobě — smí, kolidovat nesmí jen v rámci
        # JEDNOHO (viz PolozkaZpevniku.Meta.constraints). Přes token
        # `self.zpevnik` musí vrátit JEHO píseň, ne tu cizí.
        response = self.client.get(self.url(self.token, self.kod_cizi))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["X-Accel-Redirect"], "/protected/" + self.bezna.soubor.name
        )
        # A přes SVŮJ vlastní token je cizí píseň dostupná taky — nezávisle.
        self.assertEqual(
            self.client.get(self.url(self.jiny_token, self.kod_cizi)).status_code,
            status.HTTP_200_OK,
        )

    def test_neplatny_token_neda_nic(self):
        for token in ["neexistujici", "x", self.token + "a", self.token[:-1]]:
            response = self.client.get(self.url(token, self.kod))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, token)

    def test_odvolany_token_prestane_fungovat(self):
        stary = self.token
        self.zpevnik.vygeneruj_verejny_token()  # rotace tokenu
        response = self.client.get(self.url(stary, self.kod))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_zpevnik_bez_tokenu_neni_dostupny(self):
        self.zpevnik.verejny_token = None
        self.zpevnik.save()
        response = self.client.get(self.url(self.token, self.kod))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_vypis_zpevniku_nabizi_url_jen_k_verejnym_souborum(self):
        response = self.client.get(f"/api/verejny/{self.token}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        podle_kodu = {p["kod"]: p for p in response.data["pisne"]}
        self.assertIsNotNone(podle_kodu[self.kod]["soubor_url"])
        # Píseň, která má jen personal verzi, veřejné URL nedostane.
        self.assertIsNone(podle_kodu[self.kod_jen_personal]["soubor_url"])
        # A nikde se neprozradí cesta na disk.
        self.assertNotIn(self.bezna.soubor.name, str(response.data))


class AnotaceTests(SouboroveTestyZaklad):
    """Osobní poznámky nad konkrétní verzí (fáze 2a)."""

    def setUp(self):
        super().setUp()
        self.pisen = Pisen.objects.create(nazev="Píseň s poznámkami")
        self.verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        self.url = f"/api/verze-pisni/{self.verze.id}/anotace/"

    def objekt(self, **zmeny):
        zaklad = {
            "id": "a1",
            "strana": 1,
            "x": 0.42,
            "y": 0.17,
            "sirka": 0.2,
            "text": "REF 2x",
            "styl": "normal",
            "velikost": "normalni",
        }
        zaklad.update(zmeny)
        return zaklad

    def test_nova_verze_nema_zadne_poznamky(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"], [])

    def test_cteni_nezaklada_zaznam(self):
        """Čtečka se ptá při každém otevření písně — prolistování zpěvníku
        nesmí vyrobit prázdnou anotaci ke každé verzi."""
        self.client.force_authenticate(self.alice)
        self.client.get(self.url)
        self.client.get(self.url)
        self.assertEqual(Anotace.objects.count(), 0)

        self.client.put(self.url, {"data": [self.objekt()]}, format="json")
        self.assertEqual(Anotace.objects.count(), 1)

    def test_ulozeni_a_nacteni(self):
        self.client.force_authenticate(self.alice)
        objekty = [self.objekt(), self.objekt(id="a2", styl="akord", text="Ami")]
        response = self.client.put(self.url, {"data": objekty}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        znovu = self.client.get(self.url)
        self.assertEqual(znovu.data["data"], objekty)
        # Souřadnice musí přežít roundtrip přesně — na nich stojí umístění.
        self.assertEqual(znovu.data["data"][0]["x"], 0.42)
        self.assertEqual(znovu.data["data"][0]["y"], 0.17)

    def test_opakovane_ulozeni_prepise_a_nezaloz_druhy_zaznam(self):
        self.client.force_authenticate(self.alice)
        self.client.put(self.url, {"data": [self.objekt()]}, format="json")
        self.client.put(self.url, {"data": [self.objekt(text="jiny")]}, format="json")
        self.assertEqual(
            Anotace.objects.filter(verze_pisne=self.verze, vlastnik=self.alice).count(), 1
        )
        self.assertEqual(self.client.get(self.url).data["data"][0]["text"], "jiny")

    def test_poznamky_jsou_osobni(self):
        """Každý vidí jen svoje — a to i admin, který jinak smí všechno."""
        self.client.force_authenticate(self.alice)
        self.client.put(self.url, {"data": [self.objekt(text="Alicina")]}, format="json")

        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get(self.url).data["data"], [])

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.url).data["data"], [])

        # Bobovo uložení nesmí přepsat Alicino.
        self.client.force_authenticate(self.bob)
        self.client.put(self.url, {"data": [self.objekt(text="Bobova")]}, format="json")
        self.client.force_authenticate(self.alice)
        self.assertEqual(self.client.get(self.url).data["data"][0]["text"], "Alicina")

    def test_cizi_personal_verze_je_neviditelna(self):
        cizi = self.nahraj(self.pisen, VerzePisne.STAV_PERSONAL, vlastnik=self.bob)
        self.client.force_authenticate(self.alice)
        response = self.client.get(f"/api/verze-pisni/{cizi.id}/anotace/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_neprihlaseny_nema_pristup(self):
        response = self.client.get(self.url)
        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )

    def test_souradnice_mimo_stranku(self):
        self.client.force_authenticate(self.alice)
        for zmena in ({"x": 1.4}, {"y": -0.2}, {"x": 0.9, "sirka": 0.3}):
            with self.subTest(zmena=zmena):
                response = self.client.put(
                    self.url, {"data": [self.objekt(**zmena)]}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_neznamy_styl_a_chybejici_pole(self):
        self.client.force_authenticate(self.alice)
        spatne = self.client.put(
            self.url, {"data": [self.objekt(styl="duha")]}, format="json"
        )
        self.assertEqual(spatne.status_code, status.HTTP_400_BAD_REQUEST)

        bez_strany = self.objekt()
        del bez_strany["strana"]
        response = self.client.put(self.url, {"data": [bez_strany]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicitni_id_a_prilis_mnoho_poznamek(self):
        self.client.force_authenticate(self.alice)
        dvakrat = self.client.put(
            self.url, {"data": [self.objekt(), self.objekt()]}, format="json"
        )
        self.assertEqual(dvakrat.status_code, status.HTTP_400_BAD_REQUEST)

        moc = [self.objekt(id=f"a{i}") for i in range(201)]
        response = self.client.put(self.url, {"data": moc}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dlouhy_text_odmitnut(self):
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            self.url, {"data": [self.objekt(text="x" * 2001)]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mono_zachova_mezery_a_radky(self):
        """Tab/rytmus stojí na mezerách — DRF by je jinak sám ořezal."""
        self.client.force_authenticate(self.alice)
        tab = "e|--0--|\nB|--1--|"
        self.client.put(
            self.url,
            {"data": [self.objekt(styl="mono", text=tab)]},
            format="json",
        )
        self.assertEqual(self.client.get(self.url).data["data"][0]["text"], tab)

    def test_velikost_pisma(self):
        self.client.force_authenticate(self.alice)
        odpoved = self.client.put(
            self.url, {"data": [self.objekt(velikost="mala")]}, format="json"
        )
        self.assertEqual(odpoved.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(self.url).data["data"][0]["velikost"], "mala")

        spatne = self.client.put(
            self.url, {"data": [self.objekt(velikost="obri")]}, format="json"
        )
        self.assertEqual(spatne.status_code, status.HTTP_400_BAD_REQUEST)

    def test_starsi_poznamka_bez_velikosti_se_precte(self):
        """Poznámky uložené před zavedením velikosti klíč nemají — musí vyjít
        jako střední, ne shodit čtení celé vrstvy."""
        stara = self.objekt()
        del stara["velikost"]
        Anotace.objects.create(
            verze_pisne=self.verze, vlastnik=self.alice, data=[stara]
        )
        self.client.force_authenticate(self.alice)
        odpoved = self.client.get(self.url)
        self.assertEqual(odpoved.status_code, status.HTTP_200_OK)
        self.assertEqual(odpoved.data["data"][0]["velikost"], "normalni")

    def test_poznamky_patri_ke_konkretni_verzi(self):
        druha = self.nahraj(self.pisen, VerzePisne.STAV_DOWNLOAD)
        self.client.force_authenticate(self.alice)
        self.client.put(self.url, {"data": [self.objekt()]}, format="json")
        response = self.client.get(f"/api/verze-pisni/{druha.id}/anotace/")
        self.assertEqual(response.data["data"], [])


class MazaniSouboruTests(SouboroveTestyZaklad):
    def setUp(self):
        super().setUp()
        self.pisen = Pisen.objects.create(nazev="Píseň k mazání")

    def test_smazani_verze_nechava_soubor_na_disku(self):
        """Vědomé rozhodnutí: mazání verze soubor nemaže (viz README)."""
        verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        cesta = verze.soubor.path
        verze.delete()
        self.assertTrue(os.path.exists(cesta))

    def test_uklid_bez_prepinace_nemaze(self):
        verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        cesta = verze.soubor.path
        verze.delete()

        vystup = StringIO()
        call_command("uklid_souboru", "--dny", "0", stdout=vystup)
        self.assertIn("osiřelé", vystup.getvalue())
        self.assertTrue(os.path.exists(cesta))

    def test_uklid_smaze_osirely_soubor(self):
        verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        cesta = verze.soubor.path
        verze.delete()

        call_command("uklid_souboru", "--dny", "0", "--smazat", stdout=StringIO())
        self.assertFalse(os.path.exists(cesta))

    def test_uklid_nesahne_na_pouzivany_soubor(self):
        verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        call_command("uklid_souboru", "--dny", "0", "--smazat", stdout=StringIO())
        self.assertTrue(os.path.exists(verze.soubor.path))

    def test_uklid_setri_cerstve_soubory(self):
        verze = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        cesta = verze.soubor.path
        verze.delete()

        # Výchozí odklad 30 dnů — čerstvý osiřelý soubor musí přežít.
        call_command("uklid_souboru", "--smazat", stdout=StringIO())
        self.assertTrue(os.path.exists(cesta))


class HromadnyImportTests(TestCase):
    """Import (fáze 1e, cíl podle PC_zpevnik_sprava.md bod 4) — jen admin,
    atomicita. Idempotence kódu přes reject-on-collision platí jen pro
    KATEGORIE; cílový zpěvník (`cely_zpevnik`) kolize řeší přeřazením kódu,
    ne odmítnutím (viz test_kolize_kodu_v_cilovem_zpevniku_prerazuje…)."""

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="zpevnik-test-import-")
        prepinac = override_settings(MEDIA_ROOT=self.media, X_ACCEL_REDIRECT=True)
        prepinac.enable()
        self.addCleanup(prepinac.disable)
        self.addCleanup(shutil.rmtree, self.media, True)

        self.client = APIClient()
        self.admin = User.objects.create_user(
            "admin_import", password="heslo123", is_staff=True
        )
        self.clen = User.objects.create_user("clen_import", password="heslo123")

    def kniha(self, pocet_stran=3):
        return SimpleUploadedFile(
            "kniha.pdf",
            vicestrankove_pdf_bytes(pocet_stran),
            content_type="application/pdf",
        )

    def zavolej(self, soubor, plan):
        return self.client.post(
            "/api/import/",
            {"soubor": soubor, "plan": json.dumps(plan)},
            format="multipart",
        )

    def zakladni_plan(self):
        return {
            "pisne": [
                {"kod": 101, "nazev": "První píseň", "interpret": "Kapela A", "stranky": [1]},
                # dvoustránková píseň — druhá strana jako "pokračování"
                {"kod": 102, "nazev": "Druhá píseň", "interpret": "", "stranky": [2, 3]},
            ],
            # `cely_zpevnik` je od bodu 4 POVINNÝ cíl — testy, kterým na
            # konkrétním cíli nezáleží, dostanou tenhle výchozí (nový).
            "cely_zpevnik": {"nazev": "Testovací kniha"},
        }

    def test_clen_nesmi_importovat(self):
        self.client.force_authenticate(self.clen)
        response = self.zavolej(self.kniha(), self.zakladni_plan())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Pisen.objects.count(), 0)

    def test_neprihlaseny_nesmi_importovat(self):
        response = self.zavolej(self.kniha(), self.zakladni_plan())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def podle_kodu(self, response):
        """Kód je od fáze 2b vlastnost zařazení do zpěvníku, ne písně —
        odpověď importu (`response.data["pisne"]`) je teď jediné místo, kde
        jde "kód z plánu" spárovat s PK nově založené písně, pokud plán
        necílí na žádný zpěvník (řada testů níž kategorie/celý zpěvník
        záměrně vynechává, aby otestovala jen samotné řezání/validaci)."""
        return {p["kod"]: p for p in response.data["pisne"]}

    def test_admin_importuje_vicestrankovou_pisen(self):
        self.client.force_authenticate(self.admin)
        response = self.zavolej(self.kniha(3), self.zakladni_plan())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Pisen.objects.count(), 2)

        podle_kodu = self.podle_kodu(response)
        prvni = Pisen.objects.get(id=podle_kodu[101]["id"])
        druha = Pisen.objects.get(id=podle_kodu[102]["id"])
        self.assertEqual(prvni.nazev, "První píseň")
        self.assertEqual(druha.interpret, "")

        verze_prvni = prvni.verze.get()
        self.assertEqual(verze_prvni.stav, VerzePisne.STAV_DOWNLOAD)
        self.assertTrue(verze_prvni.soubor)
        # sama o sobě musí jít znovu otevřít jako platné jednostránkové PDF
        with verze_prvni.soubor.open("rb") as f:
            self.assertEqual(len(PdfReader(f).pages), 1)

        verze_druha = druha.verze.get()
        with verze_druha.soubor.open("rb") as f:
            self.assertEqual(len(PdfReader(f).pages), 2)

    def test_duplicitni_kod_v_ramci_planu_odmitnuto(self):
        self.client.force_authenticate(self.admin)
        plan = {
            "pisne": [
                {"kod": 101, "nazev": "A", "stranky": [1]},
                {"kod": 101, "nazev": "B", "stranky": [2]},
            ]
        }
        response = self.zavolej(self.kniha(2), plan)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pisen.objects.count(), 0)

    def test_kolize_kodu_v_cilovem_zpevniku_prerazuje_misto_odmitnuti(self):
        """Bod 4: kolize kódu v CÍLOVÉM zpěvníku se neodmítá jako dřív, ale
        píseň dostane další volný kód — přeřazení se vrátí v
        `prejmenovani_kodu` pro souhrn importu ("312 → 745: …")."""
        existujici = Pisen.objects.create(nazev="Existující píseň")
        cil = Zpevnik.objects.create(nazev="Moje kniha")
        PolozkaZpevniku.objects.create(zpevnik=cil, pisen=existujici, kod=101)

        self.client.force_authenticate(self.admin)
        plan = self.zakladni_plan()  # kódy 101 (koliduje), 102 (volný)
        plan["cely_zpevnik"] = {"existujici_id": cil.id}
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Pisen.objects.count(), 3)
        self.assertEqual(cil.polozky.count(), 3)

        prejmenovani = response.data["prejmenovani_kodu"]
        self.assertEqual(len(prejmenovani), 1)
        self.assertEqual(prejmenovani[0]["puvodni"], 101)
        self.assertEqual(prejmenovani[0]["novy"], 103)
        self.assertEqual(prejmenovani[0]["nazev"], "První píseň")

        # Kód 102 z plánu nekoliduje s ničím existujícím, takže se použije
        # beze změny — náhradní kód pro "První píseň" ho proto nesmí sebrat
        # (rezervovaná množina zahrnuje VŠECHNY kódy dávky od začátku, ne
        # jen ty, co se ukážou postupně).
        kody = sorted(cil.polozky.values_list("kod", flat=True))
        self.assertEqual(kody, [101, 102, 103])

    def test_stejny_kod_v_jinem_zpevniku_nekoliduje(self):
        """Dvě různé kapely/repertoáry mohou mít stejné číslo zároveň — kód
        je jedinečný jen VNITŘ jednoho zpěvníku, ne napříč všemi."""
        existujici = Pisen.objects.create(nazev="Existující píseň jinde")
        jina_kapela = Zpevnik.objects.create(nazev="Jiná kapela")
        PolozkaZpevniku.objects.create(zpevnik=jina_kapela, pisen=existujici, kod=101)

        self.client.force_authenticate(self.admin)
        plan = self.zakladni_plan()
        plan["cely_zpevnik"] = {"nazev": "Moje nová kniha"}
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Pisen.objects.count(), 3)

    def test_druhe_spusteni_stejneho_importu_do_stejneho_cile_vyrobi_duplicity(self):
        """POZNÁMKA (bod 4, viz report): idempotence písní se NEŘEŠÍ — druhý
        běh stejného plánu do TÉHOŽ cílového zpěvníku už se neodmítne (na
        rozdíl od dřívějška), kódy se prostě přeřadí a vzniknou DUPLICITNÍ
        písně. Tenhle test tu záměrně dokumentuje současné (nedokonalé)
        chování, ne že by šlo o žádoucí vlastnost."""
        self.client.force_authenticate(self.admin)
        cil = Zpevnik.objects.create(nazev="Moje kniha")
        plan = self.zakladni_plan()
        plan["cely_zpevnik"] = {"existujici_id": cil.id}

        prvni = self.zavolej(self.kniha(3), plan)
        self.assertEqual(prvni.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Pisen.objects.count(), 2)

        druhy = self.zavolej(self.kniha(3), plan)
        self.assertEqual(druhy.status_code, status.HTTP_201_CREATED, druhy.data)
        self.assertEqual(Pisen.objects.count(), 4)
        self.assertEqual(cil.polozky.count(), 4)
        # obě "První píseň" existují teď jako dva samostatné záznamy
        self.assertEqual(Pisen.objects.filter(nazev="První píseň").count(), 2)
        # druhé kolo dostalo přeřazené kódy pro OBĚ písně (101, 102 už zabrané)
        self.assertEqual(len(druhy.data["prejmenovani_kodu"]), 2)

    def test_novy_zpevnik_zacina_cistym_kodem_bez_ohledu_na_db(self):
        """To hlavní, oč ve fázi 2b šlo: nový zpěvník bez vlastních čísel
        může vždycky začít na 100/101, i když DB obsahuje úplně jiné, byť
        stejně nízké kódy — patří jinému zpěvníku."""
        existujici = Pisen.objects.create(nazev="Píseň v jiné knize")
        jina_kniha = Zpevnik.objects.create(nazev="Úplně jiná kniha")
        PolozkaZpevniku.objects.create(zpevnik=jina_kniha, pisen=existujici, kod=101)
        PolozkaZpevniku.objects.create(
            zpevnik=jina_kniha,
            pisen=Pisen.objects.create(nazev="Druhá v jiné knize"),
            kod=102,
        )

        self.client.force_authenticate(self.admin)
        plan = self.zakladni_plan()  # kody 101, 102 - stejne jako "jina_kniha"
        plan["cely_zpevnik"] = {"nazev": "Čerstvá kniha"}
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        cerstva = Zpevnik.objects.get(nazev="Čerstvá kniha")
        self.assertEqual(sorted(cerstva.polozky.values_list("kod", flat=True)), [101, 102])

    def test_stranka_mimo_rozsah_odmitnuta(self):
        self.client.force_authenticate(self.admin)
        plan = {"pisne": [{"kod": 101, "nazev": "A", "stranky": [999]}]}
        response = self.zavolej(self.kniha(2), plan)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pisen.objects.count(), 0)

    def test_stejna_strana_ve_dvou_pisnich_odmitnuta(self):
        self.client.force_authenticate(self.admin)
        plan = {
            "pisne": [
                {"kod": 101, "nazev": "A", "stranky": [1, 2]},
                {"kod": 102, "nazev": "B", "stranky": [2]},
            ]
        }
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pisen.objects.count(), 0)

    def test_soubor_ktery_neni_pdf_odmitnut(self):
        self.client.force_authenticate(self.admin)
        nepdf = SimpleUploadedFile(
            "kniha.pdf", b"toto neni pdf", content_type="application/pdf"
        )
        response = self.zavolej(nepdf, self.zakladni_plan())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pisen.objects.count(), 0)

    def test_kategorie_vytvori_slozku_a_zpevnik_a_prirazeni_pisni(self):
        self.client.force_authenticate(self.admin)
        plan = {
            "pisne": [
                {"kod": 101, "nazev": "A", "stranky": [1]},
                {"kod": 205, "nazev": "B", "stranky": [2]},
            ],
            "kategorie": [
                {"digit": "1", "nazev": "Ploužáky", "vytvorit": True},
                {"digit": "2", "nazev": "Pomalejší", "vytvorit": True},
            ],
            "cely_zpevnik": {"nazev": "Kniha pro kategorie"},
        }
        response = self.zavolej(self.kniha(2), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        plouzaky = Zpevnik.objects.get(nazev="Ploužáky")
        self.assertEqual(plouzaky.slozka.nazev, "Ploužáky")
        self.assertEqual(list(plouzaky.polozky.values_list("kod", flat=True)), [101])

        pomalejsi = Zpevnik.objects.get(nazev="Pomalejší")
        self.assertEqual(list(pomalejsi.polozky.values_list("kod", flat=True)), [205])

    def test_kategorie_oznacena_vytvorit_false_se_preskoci(self):
        self.client.force_authenticate(self.admin)
        plan = {
            "pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}],
            "kategorie": [{"digit": "1", "nazev": "Ploužáky", "vytvorit": False}],
            "cely_zpevnik": {"nazev": "Kniha bez kategorie"},
        }
        response = self.zavolej(self.kniha(1), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Slozka.objects.filter(nazev="Ploužáky").exists())

    def test_opakovany_import_do_stejne_kategorie_nezdvoji_slozku(self):
        """Druhé kolo s NOVÝMI kódy do stejné kategorie musí přiřadit do
        stejné složky/zpěvníku, ne vyrobit druhou 'Ploužáky'. Cíl obou kol
        je STEJNÝ existující zpěvník (přes `existujici_id`) — jméno pro
        NOVÝ cíl je teď jednorázové (viz test_novy_cil_se_stejnym_nazvem…),
        tak by druhé kolo se stejným `nazev` samo o sobě spadlo."""
        self.client.force_authenticate(self.admin)
        cil = Zpevnik.objects.create(nazev="Sdílený cíl")
        plan1 = {
            "pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}],
            "kategorie": [{"digit": "1", "nazev": "Ploužáky", "vytvorit": True}],
            "cely_zpevnik": {"existujici_id": cil.id},
        }
        self.assertEqual(
            self.zavolej(self.kniha(1), plan1).status_code, status.HTTP_201_CREATED
        )

        plan2 = {
            "pisne": [{"kod": 103, "nazev": "C", "stranky": [1]}],
            "kategorie": [{"digit": "1", "nazev": "Ploužáky", "vytvorit": True}],
            "cely_zpevnik": {"existujici_id": cil.id},
        }
        self.assertEqual(
            self.zavolej(self.kniha(1), plan2).status_code, status.HTTP_201_CREATED
        )

        self.assertEqual(Slozka.objects.filter(nazev="Ploužáky").count(), 1)
        zpevnik = Zpevnik.objects.get(nazev="Ploužáky")
        self.assertEqual(
            sorted(zpevnik.polozky.values_list("kod", flat=True)), [101, 103]
        )

    def test_prazdny_plan_odmitnut(self):
        self.client.force_authenticate(self.admin)
        response = self.zavolej(self.kniha(1), {"pisne": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cely_zpevnik_obsahuje_vsechny_pisne_bez_ohledu_na_kategorie(self):
        """Kategorie jsou navíc pro procházení, ne náhrada za knihu jako
        celek — ta musí jít jedním odkazem/setlistem nezávisle na nich."""
        self.client.force_authenticate(self.admin)
        plan = {
            "pisne": [
                {"kod": 101, "nazev": "A", "stranky": [1]},
                {"kod": 205, "nazev": "B", "stranky": [2]},
            ],
            "kategorie": [{"digit": "1", "nazev": "Ploužáky", "vytvorit": True}],
            "cely_zpevnik": {"nazev": "ŠUBAPS zpěvník 2026"},
        }
        response = self.zavolej(self.kniha(2), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        cely = Zpevnik.objects.get(nazev="ŠUBAPS zpěvník 2026")
        self.assertIsNone(cely.slozka)
        self.assertEqual(sorted(cely.polozky.values_list("kod", flat=True)), [101, 205])
        # kod 205 nebyl v žádné vytvořené kategorii, ale v celé knize být musí
        plouzaky = Zpevnik.objects.get(nazev="Ploužáky")
        self.assertEqual(list(plouzaky.polozky.values_list("kod", flat=True)), [101])

    def test_cely_zpevnik_je_povinny(self):
        """Bod 4: import je vždycky DO KONKRÉTNÍHO zpěvníku — na rozdíl od
        dřívějška (`vytvorit: False`/chybějící pole = přeskočit) teď bez
        `cely_zpevnik` neprojde vůbec."""
        self.client.force_authenticate(self.admin)
        response = self.zavolej(
            self.kniha(1), {"pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}]}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cely_zpevnik", response.data)
        self.assertEqual(Pisen.objects.count(), 0)

    def test_cily_zpevnik_existujici_podle_id(self):
        """`existujici_id` cílí přesně na jeden konkrétní zpěvník bez
        spoléhání na shodu názvu (na rozdíl od dřívějšího get_or_create)."""
        self.client.force_authenticate(self.admin)
        cil = Zpevnik.objects.create(nazev="Repertoár kapely")
        plan = {
            "pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}],
            "cely_zpevnik": {"existujici_id": cil.id},
        }
        response = self.zavolej(self.kniha(1), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(list(cil.polozky.values_list("kod", flat=True)), [101])

    def test_novy_cil_se_stejnym_nazvem_jako_existujici_zpevnik_odmitnut(self):
        """`nazev` je pro NOVÝ zpěvník — pokud už jméno existuje, appka to
        neslije potichu (jako dřívější get_or_create), ale odmítne s jasnou
        hláškou ať uživatel vybere „existující“."""
        self.client.force_authenticate(self.admin)
        Zpevnik.objects.create(nazev="Kniha")
        plan = self.zakladni_plan()
        plan["cely_zpevnik"] = {"nazev": "Kniha"}
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cely_zpevnik", response.data)
        self.assertEqual(Pisen.objects.count(), 0)


class AkordovyZapisSerializerTests(TestCase):
    """Validace schématu 2 (viz PC_zpevnik_akordovy_zapis_upravy.md) —
    čisté serializerové testy, bez DB/HTTP. Schéma 1 se NEPODPORUJE
    (viz test_schema_1_odmitnuto) — v produkci nikdy nic nebylo, není co
    převádět."""

    def zaklad(self, **prepis):
        data = {
            "schema": 2,
            "takt": {"dob": 4, "hodnota": 4},
            "sekce": [
                {
                    "nazev": "Sloka",
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""]}]}],
                    "repetice": [],
                }
            ],
        }
        data.update(prepis)
        return data

    def test_platny_zapis_projde(self):
        serializer = AkordovyZapisSerializer(data=self.zaklad())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_schema_1_odmitnuto(self):
        data = self.zaklad(schema=1)
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_pocet_bunek_musi_sedet_s_efektivnim_taktem(self):
        data = self.zaklad(
            sekce=[{"nazev": "X", "radky": [{"takty": [{"bunky": ["A", "G", "C"]}]}], "repetice": []}]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_vlastni_takt_na_baru_prepise_ocekavany_pocet_bunek(self):
        # 2 buňky sedí s vlastním přepisem 2/4, i když výchozí je 4/4.
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "X",
                    "radky": [{"takty": [{"bunky": ["A", ""], "takt": {"dob": 2, "hodnota": 4}}]}],
                    "repetice": [],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_vlastni_takt_se_spatnym_poctem_bunek_odmitnut(self):
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "X",
                    # takt 2/4 očekává 2 buňky, tady jsou 4
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""], "takt": {"dob": 2, "hodnota": 4}}]}],
                    "repetice": [],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_repetice_pres_vic_radku_jedne_sekce_projde(self):
        # sekce se 2 řádky po 2 taktech (dob=4 => 8 bunek/radek), repetice
        # 0..3 sahá přes OBA řádky (takty 0,1 na 1. řádku, 2,3 na 2.)
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "X",
                    "radky": [
                        {"takty": [{"bunky": ["A", "", "", ""]}, {"bunky": ["B", "", "", ""]}]},
                        {"takty": [{"bunky": ["C", "", "", ""]}, {"bunky": ["D", "", "", ""]}]},
                    ],
                    "repetice": [{"od_taktu": 0, "do_taktu": 3, "krat": 2}],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_prekryvajici_se_repetice_odmitnuty(self):
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "X",
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""]}] * 4}],
                    "repetice": [
                        {"od_taktu": 0, "do_taktu": 2, "krat": 2},
                        {"od_taktu": 1, "do_taktu": 3, "krat": 2},
                    ],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_repetice_mimo_sekci_odmitnuta(self):
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "X",
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""]}] * 2}],
                    "repetice": [{"od_taktu": 0, "do_taktu": 5, "krat": 2}],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_nesousedici_repetice_se_nepovazuji_za_prekryv(self):
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "X",
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""]}] * 6}],
                    "repetice": [
                        {"od_taktu": 0, "do_taktu": 1, "krat": 2},
                        {"od_taktu": 2, "do_taktu": 3, "krat": 3},
                    ],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_prilis_mnoho_radku_celkem_odmitnuto(self):
        # 200 limit je SOUČET řádků přes všechny sekce, ne per-sekce.
        data = self.zaklad(
            sekce=[
                {"nazev": "", "radky": [{"takty": [{"bunky": ["A", "", "", ""]}]}]} for _ in range(201)
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_prilis_mnoho_sekci_odmitnuto(self):
        data = self.zaklad(
            sekce=[
                {"nazev": "", "radky": [{"takty": [{"bunky": ["A", "", "", ""]}]}]} for _ in range(51)
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_prilis_dlouha_bunka_odmitnuta(self):
        data = self.zaklad(
            sekce=[{"nazev": "X", "radky": [{"takty": [{"bunky": ["A" * 17, "", "", ""]}]}]}]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_prazdna_sekce_povolena(self):
        serializer = AkordovyZapisSerializer(data=self.zaklad(sekce=[]))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_sekce_bez_radku_povolena(self):
        # Sekce jen s nadpisem, bez taktů (editor: smazání úplně posledního
        # taktu sekci na tohle nechá, viz akordovyModel.odeberTaktZeSekce) —
        # `radky: []` musí projít, i beze změny výchozího `takt`.
        data = self.zaklad(sekce=[{"nazev": "Interlude", "radky": [], "repetice": []}])
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["sekce"][0]["radky"], [])

    def test_sekce_bez_radku_a_bez_nazvu_take_povolena(self):
        data = self.zaklad(sekce=[{"nazev": "", "radky": [], "repetice": []}])
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_sekce_bez_radku_s_repetici_odmitnuta(self):
        # V sekci bez taktů nemá repetice co indexovat — jakýkoliv rozsah
        # je nutně "mimo sekci" (0 taktů celkem).
        data = self.zaklad(
            sekce=[
                {
                    "nazev": "Interlude",
                    "radky": [],
                    "repetice": [{"od_taktu": 0, "do_taktu": 0, "krat": 2}],
                }
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def _sekce_s_10_takty(self, **prepis):
        radky = [{"takty": [{"bunky": ["A", "", "", ""]}] * 10}]
        sekce = {"nazev": "X", "radky": radky, "repetice": [], "volty": []}
        sekce.update(prepis)
        return sekce

    def test_volta_uvnitr_repetice_povolena(self):
        # Přesně příklad ze zadání: repetice 6-7, volta 1 UVNITŘ ní.
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[{"cislo": 1, "od_taktu": 6, "do_taktu": 7}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_volta_hned_za_repetici_povolena(self):
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[{"cislo": 2, "od_taktu": 8, "do_taktu": 9}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_prima_a_secunda_volta_spolu_povoleny(self):
        # Celý příklad ze zadání najednou - 1. UVNITŘ repetice, 2. HNED ZA ní.
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[
                        {"cislo": 1, "od_taktu": 6, "do_taktu": 7},
                        {"cislo": 2, "od_taktu": 8, "do_taktu": 9},
                    ],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_volta_s_mezerou_za_repetici_odmitnuta(self):
        # "hned za" - MEZERA (takt 9, ne 8) repetici nesplňuje.
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[{"cislo": 2, "od_taktu": 9, "do_taktu": 9}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_volta_bez_jakekoliv_repetice_odmitnuta(self):
        data = self.zaklad(
            sekce=[self._sekce_s_10_takty(volty=[{"cislo": 1, "od_taktu": 2, "do_taktu": 3}])]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_volta_castecne_prekryvajici_repetici_ale_ne_cela_uvnitr_odmitnuta(self):
        # od_taktu(3) je PŘED repetici (4-7) - není to "uvnitř" ani "hned za".
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[{"cislo": 1, "od_taktu": 3, "do_taktu": 5}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_prekryvajici_se_volty_odmitnuty(self):
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[
                        {"cislo": 1, "od_taktu": 6, "do_taktu": 7},
                        {"cislo": 2, "od_taktu": 7, "do_taktu": 7},
                    ],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_volta_mimo_sekci_odmitnuta(self):
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 9, "krat": 2}],
                    volty=[{"cislo": 1, "od_taktu": 8, "do_taktu": 10}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_volta_cislo_mimo_rozsah_odmitnuta(self):
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[{"cislo": 5, "od_taktu": 6, "do_taktu": 7}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_volta_do_taktu_pred_od_taktu_odmitnuta(self):
        data = self.zaklad(
            sekce=[
                self._sekce_s_10_takty(
                    repetice=[{"od_taktu": 4, "do_taktu": 7, "krat": 2}],
                    volty=[{"cislo": 1, "od_taktu": 7, "do_taktu": 6}],
                )
            ]
        )
        serializer = AkordovyZapisSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class AkordyPdfMrizkaTests(TestCase):
    """Mřížka akordového PDF (zpevnik/akordy_pdf.py), schéma 2: ŘÁDEK SE
    NIKDY NEZALAMUJE — delší než 4 takty výchozího taktu zmenší CELÝ
    dokument, ne jen ten řádek. Prázdná doba má VŽDY tečku (nikdy se
    nepotlačuje, viz oprava bodu 4) a akord nesmí zasahovat do sousední
    doby — místo lokálního zmenšování písma se rozšíří jen POSTIŽENÁ doba
    na šířku textu (viz oprava bodu 5). Šířka doby se počítá PER POZICE
    NAPŘÍČ CELÝM DOKUMENTEM (viz oprava "zarovnání do mřížky"), ne uvnitř
    jednotlivého taktu — takže taktové čáry jsou ve všech řádcích ve
    stejné svislici, i když se řádky liší obsahem."""

    def test_prazdna_doba_ma_zakladni_sirku(self):
        from zpevnik.akordy_pdf import _sirka_doby

        self.assertEqual(_sirka_doby("", 40, 17.5), 40)

    def test_kratky_akord_se_vejde_do_zakladni_sirky(self):
        from zpevnik.akordy_pdf import _sirka_doby

        self.assertEqual(_sirka_doby("C", 40, 17.5), 40)

    def test_dlouhy_akord_rozsiri_dobu_na_sirku_textu_plus_rezervu(self):
        from reportlab.pdfbase import pdfmetrics

        from zpevnik.akordy_pdf import FONT_AKORD, REZERVA_MEZI_AKORDY, _sirka_doby, _zaregistruj_fonty

        _zaregistruj_fonty()
        text = "Gmaj7/D"
        sirka = _sirka_doby(text, 20, 17.5)
        ocekavana = pdfmetrics.stringWidth(text, FONT_AKORD, 17.5) + REZERVA_MEZI_AKORDY
        self.assertGreater(sirka, 20)
        self.assertAlmostEqual(sirka, ocekavana)

    def test_sirky_pozic_pro_kratke_akordy_je_zakladni_na_kazde_pozici(self):
        from zpevnik.akordy_pdf import _sirky_pozic

        radky = [{"takty": [{"bunky": ["C", "", "", ""]}]}]
        self.assertEqual(_sirky_pozic(radky, 40, 17.5), [40, 40, 40, 40])

    def test_takt_s_prepisem_na_2_doby_ma_presne_2x_zakladni_sirku_kdyz_prazdny(self):
        # Regrese k opravenému bodu 9: badge "2/4" nesmí mít za sebou žádné
        # navíc místo, pokud jsou obě doby prázdné/krátké a nic jinde v
        # dokumentu na těch pozicích nerozšiřuje.
        from zpevnik.akordy_pdf import _sirky_pozic

        radky = [{"takty": [{"bunky": ["G", "C"], "takt": {"dob": 2, "hodnota": 4}}]}]
        self.assertEqual(_sirky_pozic(radky, 40, 17.5), [40, 40])

    def test_sirky_pozic_je_globalni_max_pres_vsechny_radky_na_stejne_pozici(self):
        # Přímo srdce opravy "zarovnání do mřížky": dlouhý akord v JEDNOM
        # řádku na pozici 2 rozšíří POZICI 2 pro VŠECHNY řádky dokumentu,
        # ne jen svůj vlastní takt — jinak by taktové čáry nebyly pod
        # sebou (přesně bug, co se opravoval).
        from zpevnik.akordy_pdf import _sirky_pozic

        radky = [
            {"takty": [{"bunky": ["A", "", "Gmaj7", ""]}]},
            {"takty": [{"bunky": ["C", "", "", ""]}]},
        ]
        sirky = _sirky_pozic(radky, 40, 17.5)
        self.assertGreater(sirky[2], 40)
        self.assertEqual(sirky[0], 40)
        self.assertEqual(sirky[1], 40)
        self.assertEqual(sirky[3], 40)

    def test_kratsi_radek_neomezuje_sirku_pozic_za_svym_koncem(self):
        from zpevnik.akordy_pdf import _sirky_pozic

        radky = [
            {"takty": [{"bunky": ["C"]}]},
            {"takty": [{"bunky": ["D", "", "Gmaj7", ""]}]},
        ]
        sirky = _sirky_pozic(radky, 40, 17.5)
        self.assertEqual(len(sirky), 4)
        self.assertGreater(sirky[2], 40)

    def test_pozice_zacatku_taktu_scita_delky_predchozich_taktu(self):
        from zpevnik.akordy_pdf import _pozice_zacatku_taktu

        radek = {
            "takty": [
                {"bunky": ["A", "", "", ""]},
                {"bunky": ["G", "C"]},
                {"bunky": ["E"]},
            ]
        }
        self.assertEqual(_pozice_zacatku_taktu(radek, 0), 0)
        self.assertEqual(_pozice_zacatku_taktu(radek, 1), 4)
        self.assertEqual(_pozice_zacatku_taktu(radek, 2), 6)

    def test_taktove_cary_ve_dvou_ruznych_radcich_jsou_ve_stejne_pozici(self):
        # End-to-end ověření celé opravy: dva řádky, jeden s dlouhým
        # akordem, druhý bez — hranice mezi 1. a 2. taktem musí vyjít
        # STEJNĚ pro oba, i když jsou jinak obsahem různě "těžké".
        from zpevnik.akordy_pdf import _sirky_pozic, _x_pozice_taktu

        radek_s_dlouhym = {
            "takty": [{"bunky": ["A", "", "Gmaj7", ""]}, {"bunky": ["D", "", "", ""]}]
        }
        radek_kratky = {"takty": [{"bunky": ["C", "", "", ""]}, {"bunky": ["E", "", "", ""]}]}
        sirky = _sirky_pozic([radek_s_dlouhym, radek_kratky], 40, 17.5)

        hranice_dlouhy = _x_pozice_taktu(radek_s_dlouhym, sirky, 1)
        hranice_kratky = _x_pozice_taktu(radek_kratky, sirky, 1)
        self.assertEqual(hranice_dlouhy, hranice_kratky)
        self.assertGreater(hranice_dlouhy, 4 * 40)

    def test_mezery_znacek_repetice_zacatek_a_konec_mid_radku(self):
        from zpevnik.akordy_pdf import (
            SIRKA_ZNACKY_ZACATEK_REPETICE,
            VELIKOST_REPETICE_N,
            _mezery_znacek_repetice,
            _radky_s_metadaty,
            _zaregistruj_fonty,
        )

        _zaregistruj_fonty()
        sekce = [
            {
                "nazev": "S",
                "radky": [{"takty": [{"bunky": ["A"]}, {"bunky": ["B"]}, {"bunky": ["C"]}, {"bunky": ["D"]}]}],
                # repetice na taktech 1-2 (0-based) - ZAČÍNÁ i KONČÍ
                # uprostřed řádku (ne na taktu 0, ne na posledním taktu 3).
                "repetice": [{"od_taktu": 1, "do_taktu": 2, "krat": 2}],
            }
        ]
        polozky = _radky_s_metadaty(sekce)
        vlevo, vpravo = _mezery_znacek_repetice(polozky, VELIKOST_REPETICE_N)

        self.assertEqual(vlevo, {1: SIRKA_ZNACKY_ZACATEK_REPETICE})
        self.assertEqual(set(vpravo.keys()), {2})
        self.assertGreater(vpravo[2], 0)

    def test_znacka_konce_repetice_uprostred_radku_nezasahuje_do_dalsiho_taktu(self):
        # Regrese k bodu 1 PC_zpevnik_akordy_ovladani.md: ':|' + '×N' na
        # konci repetice uprostřed řádku nesmí přepsat akord následujícího
        # taktu (viz "Don't Bring Me Down", refrén: ×2 na G). Dva řádky -
        # jeden s repeticí končící uprostřed (takt index 1 ze 4), druhý bez
        # repetice - taktové čáry musí vyjít stejně (sdílená mřížka), a
        # '×N' text se musí vejít do rezervovaného místa PŘED další takt.
        from reportlab.pdfbase import pdfmetrics

        from zpevnik.akordy_pdf import (
            FONT_POPISEK_TUCNE,
            ODSTUP_ZA_ZNACKOU_KONCE,
            ODSTUP_ZNACKY_KONCE_OD_CARY,
            VELIKOST_REPETICE_N,
            _mezery_znacek_repetice,
            _radky_s_metadaty,
            _rozsir_sirky_pro_znacky,
            _sirky_pozic,
            _x_pozice_taktu,
            _zaregistruj_fonty,
        )

        _zaregistruj_fonty()
        sekce = [
            {
                "nazev": "S repeticí",
                "radky": [{"takty": [{"bunky": ["A"]}, {"bunky": ["B"]}, {"bunky": ["C"]}, {"bunky": ["D"]}]}],
                "repetice": [{"od_taktu": 0, "do_taktu": 1, "krat": 2}],
            },
            {
                "nazev": "Bez repetice",
                "radky": [{"takty": [{"bunky": ["E"]}, {"bunky": ["F"]}, {"bunky": ["G"]}, {"bunky": ["H"]}]}],
                "repetice": [],
            },
        ]
        polozky = _radky_s_metadaty(sekce)
        radek_s_rep, radek_bez_rep = polozky[0]["radek"], polozky[1]["radek"]
        radky = [p["radek"] for p in polozky]

        sirka_doby_zakladni, velikost_akordu = 40, 17.5
        sirky = _sirky_pozic(radky, sirka_doby_zakladni, velikost_akordu)
        vlevo, vpravo = _mezery_znacek_repetice(polozky, VELIKOST_REPETICE_N)
        sirky = _rozsir_sirky_pro_znacky(sirky, vlevo, vpravo)

        # Taktové čáry PO taktu 1 (hranice před taktem 2) ve stejné
        # svislici pro OBA řádky, přestože jen jeden má repetici na
        # týhle pozici - to je celý smysl sdílené mřížky pozic.
        hranice_s_rep = _x_pozice_taktu(radek_s_rep, sirky, 2)
        hranice_bez_rep = _x_pozice_taktu(radek_bez_rep, sirky, 2)
        self.assertEqual(hranice_s_rep, hranice_bez_rep)
        # a je znatelně širší než bez rezervy (jinak by test neověřoval nic).
        self.assertGreater(hranice_s_rep, 2 * sirka_doby_zakladni)

        # '×2' text (stejná logika jako _kresli_repetici) musí SKONČIT
        # PŘED touhle hranicí, s odstupem ODSTUP_ZA_ZNACKOU_KONCE - žádný
        # překryv s akordem taktu 2 ('C').
        mezera_konce = vpravo[1]
        x_konec_znacky = hranice_s_rep - mezera_konce
        sirka_textu = pdfmetrics.stringWidth("×2", FONT_POPISEK_TUCNE, VELIKOST_REPETICE_N)
        konec_textu = x_konec_znacky + ODSTUP_ZNACKY_KONCE_OD_CARY + sirka_textu
        self.assertLessEqual(konec_textu, hranice_s_rep - ODSTUP_ZA_ZNACKOU_KONCE + 0.01)

    def test_volty_v_radku_najde_jen_volty_ktere_radek_zasahuji(self):
        from zpevnik.akordy_pdf import _volty_v_radku

        sekce = {
            "volty": [
                {"cislo": 1, "od_taktu": 0, "do_taktu": 1},  # v prvnim radku (0-3)
                {"cislo": 2, "od_taktu": 5, "do_taktu": 5},  # v druhem radku (4-7)
            ]
        }
        self.assertEqual(len(_volty_v_radku(sekce, 0, 4)), 1)
        self.assertEqual(_volty_v_radku(sekce, 0, 4)[0]["cislo"], 1)
        self.assertEqual(len(_volty_v_radku(sekce, 4, 8)), 1)
        self.assertEqual(_volty_v_radku(sekce, 4, 8)[0]["cislo"], 2)

    def test_ma_navic_nad_radkem_kvuli_volte_i_bez_badge(self):
        from zpevnik.akordy_pdf import _ma_navic_nad_radkem

        sekce = {"volty": [{"cislo": 1, "od_taktu": 0, "do_taktu": 1}]}
        radek = {"takty": [{"bunky": ["A", "", "", ""]}] * 4}
        polozka = {"typ": "radek", "radek": radek, "sekce": sekce, "od_g": 0, "do_g": 4}
        self.assertTrue(_ma_navic_nad_radkem(polozka))

        polozka_bez_volty = {"typ": "radek", "radek": radek, "sekce": {"volty": []}, "od_g": 0, "do_g": 4}
        self.assertFalse(_ma_navic_nad_radkem(polozka_bez_volty))

    def test_volta_zavorka_koncici_soucasne_s_repetici_nezasahuje_do_znacky_konce(self):
        # Regrese k nálezu při ladění bodu 5: volta, co končí PŘESNĚ na
        # stejné pozici jako repetice (běžný případ - "volta 1" těsně
        # před ':|'), musí svojí závorkou skončit PŘED rezervou pro '×N',
        # ne za ní (jinak by přesahovala přes okraj stránky).
        from zpevnik.akordy_pdf import (
            OKRAJ,
            SIRKA_GUTTERU,
            SIRKA_STRANKY,
            VELIKOST_AKORDU,
            VELIKOST_REPETICE_N,
            POCET_TAKTU_NA_RADEK,
            TECHNICKY_MIN_VELIKOST,
            _mezery_znacek_repetice,
            _najdi_scale,
            _pozice_zacatku_taktu,
            _radky_s_metadaty,
            _rozsir_sirky_pro_znacky,
            _sirky_pozic,
            _x_pozice_taktu,
            _zaregistruj_fonty,
        )

        _zaregistruj_fonty()
        sekce = [
            {
                "nazev": "S",
                "radky": [{"takty": [{"bunky": ["A"]}, {"bunky": ["B"]}, {"bunky": ["C"]}, {"bunky": ["D"]}]}],
                "repetice": [{"od_taktu": 0, "do_taktu": 3, "krat": 2}],
                "volty": [{"cislo": 1, "od_taktu": 2, "do_taktu": 3}],
            }
        ]
        polozky = _radky_s_metadaty(sekce)
        polozky_radek = [p for p in polozky if p["typ"] == "radek"]
        radek = polozky_radek[0]["radek"]
        sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
        scale = _najdi_scale(polozky_radek, sirka_obsahu, 4)
        sirka_doby_zakladni = (sirka_obsahu / (POCET_TAKTU_NA_RADEK * 4)) * scale
        velikost_akordu = max(VELIKOST_AKORDU * scale, TECHNICKY_MIN_VELIKOST)
        velikost_repetice_n = max(VELIKOST_REPETICE_N * scale, TECHNICKY_MIN_VELIKOST)
        sirky = _sirky_pozic([radek], sirka_doby_zakladni, velikost_akordu)
        vlevo, vpravo = _mezery_znacek_repetice(polozky_radek, velikost_repetice_n)
        sirky = _rozsir_sirky_pro_znacky(sirky, vlevo, vpravo)

        # volta konci na taktu 3 (index 3, posledni takt radku) - stejne
        # jako repetice - takze p_konec_volty == p_konec_repetice.
        p_konec_volty = _pozice_zacatku_taktu(radek, 3) + len(radek["takty"][3]["bunky"]) - 1
        posun_konce = vpravo.get(p_konec_volty, 0.0)
        self.assertGreater(posun_konce, 0)

        x_konec_hranice = _x_pozice_taktu(radek, sirky, 4)
        x_konec_zavorky = x_konec_hranice - posun_konce
        x_konec_znacky_repetice = x_konec_hranice - vpravo[p_konec_volty]
        # zavorka konci PŘESNĚ tam, kde zacina rezerva pro ':|'+'×N', ne za ni.
        self.assertAlmostEqual(x_konec_zavorky, x_konec_znacky_repetice)

    def test_dokument_s_repetici_a_voltou_v_pdf_projde(self):
        from zpevnik import akordy_pdf

        class FakePisen:
            nazev = "Test"
            interpret = ""

        zapis = self._zapis(
            [
                {
                    "nazev": "Sloka",
                    "radky": [{"takty": [{"bunky": ["A"]}, {"bunky": ["B"]}, {"bunky": ["C"]}, {"bunky": ["D"]}]}],
                    "repetice": [{"od_taktu": 0, "do_taktu": 3, "krat": 2}],
                    "volty": [{"cislo": 1, "od_taktu": 2, "do_taktu": 3}],
                }
            ],
            dob=1,
        )
        pdf = akordy_pdf.vygeneruj_pdf(FakePisen(), zapis)
        self.assertEqual(pdf[:5], b"%PDF-")

    def test_rozvrhni_stranky_jednoducha_pisen_zustane_na_jedne_strance(self):
        from zpevnik.akordy_pdf import (
            OKRAJ,
            SIRKA_GUTTERU,
            SIRKA_STRANKY,
            _najdi_scale,
            _radky_s_metadaty,
            _rozvrhni_stranky,
        )

        sekce = [
            {
                "nazev": "A",
                "radky": [{"takty": [{"bunky": ["C", "", "", ""]}] * 4}] * 3,
                "repetice": [],
            }
        ]
        polozky = _radky_s_metadaty(sekce)
        sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
        scale = _najdi_scale(polozky, sirka_obsahu, 4)
        self.assertAlmostEqual(scale, 1.0, places=2)
        stranky = _rozvrhni_stranky(polozky, scale)
        self.assertEqual(len(stranky), 1)

    def test_rozvrhni_stranky_deli_jen_podle_vysky_ne_podle_scale(self):
        # Mřížka je teď SPOLEČNÁ pro celý dokument (viz modul docstring) —
        # stránkování už nesmí dělit podle scale, jen podle výšky. Dost
        # řádků na to, aby se na výšku nevešly na jednu stránku, musí dát
        # víc stránek se STEJNÝM scale na všech (na rozdíl od dřívějšího
        # chování, kdy pozdější stránky mohly vyjít větší).
        from zpevnik.akordy_pdf import (
            OKRAJ,
            SIRKA_GUTTERU,
            SIRKA_STRANKY,
            _najdi_scale,
            _radky_s_metadaty,
            _rozvrhni_stranky,
        )

        sekce = [
            {
                "nazev": "A",
                "radky": [{"takty": [{"bunky": ["C", "", "", ""]}] * 4}] * 60,
                "repetice": [],
            }
        ]
        polozky = _radky_s_metadaty(sekce)
        sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
        scale = _najdi_scale(polozky, sirka_obsahu, 4)

        stranky = _rozvrhni_stranky(polozky, scale)
        self.assertGreater(len(stranky), 1)
        self.assertEqual(sum(len(s) for s in stranky), len(polozky))

    def test_husta_pisen_uz_nerozdeli_stranky_kvuli_scale(self):
        # Regrese k ZRUŠENÉMU chování (viz modul docstring): dřív sdílená
        # mřížka přes moc řádků srážela scale, a stránkování na to reagovalo
        # děním stránek i podle výšky by se vešly. Teď je mřížka pro celý
        # dokument a stránkování řeší JEN výšku — hustá "písnička", co se na
        # výšku vejde na jednu stránku, musí zůstat na jedné, i když je
        # scale kvůli širokým akordům nízký.
        from zpevnik.akordy_pdf import (
            OKRAJ,
            SIRKA_GUTTERU,
            SIRKA_STRANKY,
            _najdi_scale,
            _radky_s_metadaty,
            _rozvrhni_stranky,
        )

        # 12 řádků (4 takty po 4 dobách = 16 pozic), každý má "G#m7" na
        # JINÉ z prvních 12 pozic — žádný řádek sám o sobě není široký (jen
        # 1 široký akord v něm), ale mřížka sdílená přes všech 12 rozšíří
        # 12 pozic najednou, takže scale vyjde pod 1.0 — 12 řádků se ale
        # při tomhle scale pořád vejde na výšku jedné (landscape) stránky.
        radky_data = []
        for i in range(12):
            bunky = ["C", "", "", ""] * 4
            bunky[i] = "G#m7"
            takty = [{"bunky": bunky[t * 4 : t * 4 + 4]} for t in range(4)]
            radky_data.append({"takty": takty})
        sekce = [{"nazev": "A", "radky": radky_data, "repetice": []}]

        polozky = _radky_s_metadaty(sekce)
        sirka_obsahu = SIRKA_STRANKY - 2 * OKRAJ - SIRKA_GUTTERU
        scale = _najdi_scale(polozky, sirka_obsahu, 4)
        self.assertLess(scale, 1.0)  # sanity: scénář skutečně cvičí zúžení

        stranky = _rozvrhni_stranky(polozky, scale)
        self.assertEqual(len(stranky), 1)

    def test_radky_s_metadaty_sekce_bez_radku_je_polozka_typu_nadpis(self):
        from zpevnik.akordy_pdf import _radky_s_metadaty

        sekce = [
            {"nazev": "Intro", "radky": [], "repetice": []},
            {"nazev": "Sloka", "radky": [{"takty": [{"bunky": ["A"]}]}], "repetice": []},
        ]
        polozky = _radky_s_metadaty(sekce)
        self.assertEqual(len(polozky), 2)
        self.assertEqual(polozky[0]["typ"], "nadpis")
        self.assertNotIn("radek", polozky[0])
        self.assertTrue(polozky[0]["je_prvni_v_sekci"])
        self.assertTrue(polozky[0]["je_posledni_v_sekci"])
        self.assertEqual(polozky[1]["typ"], "radek")

    def test_seskup_pro_zalomeni_slepi_nadpis_s_prvni_polozkou_za_nim(self):
        from zpevnik.akordy_pdf import _seskup_pro_zalomeni

        radek1 = {"typ": "radek", "je_prvni_v_sekci": True, "je_posledni_v_sekci": False}
        nadpis = {"typ": "nadpis", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        radek2 = {"typ": "radek", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        skupiny = _seskup_pro_zalomeni([radek1, nadpis, radek2])
        self.assertEqual(skupiny, [[radek1], [nadpis, radek2]])

    def test_seskup_pro_zalomeni_slepi_retez_nadpisu_az_po_prvni_skutecny_radek(self):
        from zpevnik.akordy_pdf import _seskup_pro_zalomeni

        nadpis1 = {"typ": "nadpis", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        nadpis2 = {"typ": "nadpis", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        radek = {"typ": "radek", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        skupiny = _seskup_pro_zalomeni([nadpis1, nadpis2, radek])
        self.assertEqual(skupiny, [[nadpis1, nadpis2, radek]])

    def test_seskup_pro_zalomeni_osamoceny_nadpis_na_konci_dokumentu_zustane_sam(self):
        # Nemá s čím se slepit - to zadání výslovně neřeší (viz modul
        # docstring).
        from zpevnik.akordy_pdf import _seskup_pro_zalomeni

        radek = {"typ": "radek", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        nadpis = {"typ": "nadpis", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        skupiny = _seskup_pro_zalomeni([radek, nadpis])
        self.assertEqual(skupiny, [[radek], [nadpis]])

    def test_rozvrhni_stranky_nenecha_osamoceny_nadpis_na_konci_stranky(self):
        # Regrese k požadavku "nadpis a první řádek další sekce nejsou
        # rozdělené koncem stránky": sestavíme scénář, kde by se BEZ
        # seskupení (_seskup_pro_zalomeni) nadpis vešel jako poslední
        # položka na stránku, ale spolu s řádkem hned za ním už ne - a
        # ověříme, že se stránkuje po CELÉ skupině, ne po jednotlivé
        # položce.
        from zpevnik.akordy_pdf import OKRAJ, Y_ZACATEK_OBSAHU, _rozvrhni_stranky, _vyska_obsahu_stranky

        scale = 1.0
        vyska_dostupna = Y_ZACATEK_OBSAHU - OKRAJ

        prazdna_sekce = {"volty": []}

        def filler_radek():
            return {
                "typ": "radek",
                "radek": {"takty": [{"bunky": [""]}]},
                "sekce": prazdna_sekce,
                "od_g": 0,
                "do_g": 1,
                "je_prvni_v_sekci": False,
                "je_posledni_v_sekci": False,
            }

        nadpis = {"typ": "nadpis", "je_prvni_v_sekci": True, "je_posledni_v_sekci": True}
        posledni_radek = {
            "typ": "radek",
            "radek": {"takty": [{"bunky": [""]}]},
            "sekce": prazdna_sekce,
            "od_g": 0,
            "do_g": 1,
            "je_prvni_v_sekci": True,
            "je_posledni_v_sekci": True,
        }

        filler = []
        while True:
            filler.append(filler_radek())
            s_nadpisem = _vyska_obsahu_stranky(filler + [nadpis], scale)
            s_obema = _vyska_obsahu_stranky(filler + [nadpis, posledni_radek], scale)
            if s_nadpisem <= vyska_dostupna < s_obema:
                break
            if len(filler) > 500:
                self.fail("nepodařilo se sestavit scénář pro test")

        polozky = filler + [nadpis, posledni_radek]
        stranky = _rozvrhni_stranky(polozky, scale)

        self.assertNotIn(nadpis, stranky[0])
        self.assertIn(nadpis, stranky[1])
        self.assertIn(posledni_radek, stranky[1])

    def _zapis(self, sekce, dob=4, hodnota=4):
        return {"schema": 2, "takt": {"dob": dob, "hodnota": hodnota}, "tempo": None, "sekce": sekce}

    def test_ctyri_takty_vychoziho_taktu_nezmensi_dokument(self):
        from zpevnik.akordy_pdf import vygeneruj_pdf

        class FakePisen:
            nazev = "Test"
            interpret = ""

        zapis = self._zapis(
            [
                {
                    "nazev": "A",
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""]}] * 4}],
                    "repetice": [],
                }
            ]
        )
        pdf = vygeneruj_pdf(FakePisen(), zapis)
        self.assertEqual(pdf[:5], b"%PDF-")

    def test_delsi_radek_nez_4_takty_se_nezalomi_zmensi_dokument(self):
        # 4 takty 4/4 + 1 takt 2/4 = 18 dob > 16 (4*4) -> CELÝ dokument se
        # zmenší (scale = 16/18), řádek zůstane jeden, žádné auto-zalomení.
        from zpevnik import akordy_pdf

        class FakePisen:
            nazev = "Test"
            interpret = ""

        zapis = self._zapis(
            [
                {
                    "nazev": "A",
                    "radky": [
                        {
                            "takty": [{"bunky": ["A", "", "", ""]}] * 4
                            + [{"bunky": ["E", ""], "takt": {"dob": 2, "hodnota": 4}}]
                        }
                    ],
                    "repetice": [],
                }
            ]
        )
        pdf = akordy_pdf.vygeneruj_pdf(FakePisen(), zapis)
        self.assertEqual(pdf[:5], b"%PDF-")
        # jen jedna stránka (žádné zalomení řádku ani stránky u tak krátkého
        # zápisu) — PDF s jednou stránkou má v bytech přesně jeden "/Type /Page"
        # (ne /Pages, ten je vždy) mimo katalog; jednodušší a stabilnější
        # ověření je přes pypdf.
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)

    def test_sekce_bez_radku_v_pdf_projde(self):
        # Sekce jen s nadpisem (Intro) vedle normální sekce s obsahem -
        # vygeneruj_pdf nesmí spadnout, jen vykreslí Intro jako samotný
        # nadpis bez mřížky (viz akordy_pdf docstring).
        from zpevnik import akordy_pdf

        class FakePisen:
            nazev = "Test"
            interpret = ""

        zapis = self._zapis(
            [
                {"nazev": "Intro", "radky": [], "repetice": []},
                {
                    "nazev": "Sloka",
                    "radky": [{"takty": [{"bunky": ["A", "", "", ""]}] * 4}],
                    "repetice": [],
                },
            ]
        )
        pdf = akordy_pdf.vygeneruj_pdf(FakePisen(), zapis)
        self.assertEqual(pdf[:5], b"%PDF-")

        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 1)

    def test_dokument_jen_z_nadpisu_bez_radku_v_pdf_projde(self):
        # Krajní případ: žádná sekce v celém dokumentu nemá řádky - mřížka
        # (scale i sirky_pozic) se počítá z prázdného seznamu.
        from zpevnik import akordy_pdf

        class FakePisen:
            nazev = "Test"
            interpret = ""

        zapis = self._zapis(
            [
                {"nazev": "Intro", "radky": [], "repetice": []},
                {"nazev": "Outro", "radky": [], "repetice": []},
            ]
        )
        pdf = akordy_pdf.vygeneruj_pdf(FakePisen(), zapis)
        self.assertEqual(pdf[:5], b"%PDF-")


class VerzeAkordyVytvoreniTests(TestCase):
    """POST /api/pisne/<id>/verze-akordy/ — nová akordová verze."""

    def setUp(self):
        self.pisen = Pisen.objects.create(nazev="Chord song", interpret="Kapela")
        self.clen = User.objects.create_user("clen-akordy", password="heslo123")
        self.client = APIClient()

    def test_prazdne_telo_vyrobi_prazdny_zapis_a_pdf(self):
        self.client.force_authenticate(self.clen)
        response = self.client.post(f"/api/pisne/{self.pisen.id}/verze-akordy/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertEqual(verze.zdroj, VerzePisne.ZDROJ_AKORDY)
        self.assertEqual(verze.stav, VerzePisne.STAV_PERSONAL)
        self.assertEqual(verze.vlastnik_id, self.clen.id)
        self.assertTrue(verze.soubor)
        with verze.soubor.open("rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")

    def test_telo_s_akordy_se_ulozi(self):
        self.client.force_authenticate(self.clen)
        telo = {
            "akordy": {
                "schema": 2,
                "takt": {"dob": 4, "hodnota": 4},
                "sekce": [
                    {
                        "nazev": "Refrén",
                        "radky": [{"takty": [{"bunky": ["D", "A", "Bm", "G"]}]}],
                        "repetice": [],
                    }
                ],
            }
        }
        response = self.client.post(
            f"/api/pisne/{self.pisen.id}/verze-akordy/", telo, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertEqual(verze.akordy["sekce"][0]["nazev"], "Refrén")

    def test_neplatny_akordovy_zapis_odmitnut(self):
        self.client.force_authenticate(self.clen)
        telo = {
            "akordy": {
                "schema": 2,
                "takt": {"dob": 4, "hodnota": 4},
                "sekce": [{"nazev": "X", "radky": [{"takty": [{"bunky": ["A", "B"]}]}]}],
            }
        }
        response = self.client.post(
            f"/api/pisne/{self.pisen.id}/verze-akordy/", telo, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nepriblasenemu_uzivateli_se_odmita(self):
        response = self.client.post(f"/api/pisne/{self.pisen.id}/verze-akordy/")
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )


class AkordyApiTests(TestCase):
    """GET/PUT /api/verze-pisni/<id>/akordy/ — roundtrip, práva, regenerace PDF."""

    def setUp(self):
        self.pisen = Pisen.objects.create(nazev="Písnička s akordy")
        self.alice = User.objects.create_user("alice-akordy", password="heslo123")
        self.bob = User.objects.create_user("bob-akordy", password="heslo123")
        self.admin = User.objects.create_user(
            "admin-akordy", password="heslo123", is_staff=True
        )
        self.zapis = {
            "schema": 2,
            "takt": {"dob": 4, "hodnota": 4},
            "tempo": None,
            "sekce": [
                {"nazev": "Sloka", "radky": [{"takty": [{"bunky": ["C", "", "", ""]}]}], "repetice": []}
            ],
        }
        self.verze_akordy = VerzePisne.objects.create(
            pisen=self.pisen,
            zdroj=VerzePisne.ZDROJ_AKORDY,
            stav=VerzePisne.STAV_PERSONAL,
            vlastnik=self.alice,
            akordy=self.zapis,
        )
        self.verze_pdf = VerzePisne.objects.create(
            pisen=self.pisen, zdroj=VerzePisne.ZDROJ_PDF, stav=VerzePisne.STAV_CONFIRMED
        )
        self.client = APIClient()

    def test_vlastnik_precte_svuj_zapis(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(f"/api/verze-pisni/{self.verze_akordy.id}/akordy/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sekce"][0]["nazev"], "Sloka")

    def test_cizi_personal_verze_da_404(self):
        self.client.force_authenticate(self.bob)
        response = self.client.get(f"/api/verze-pisni/{self.verze_akordy.id}/akordy/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_vidi_cizi_personal_zapis(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/verze-pisni/{self.verze_akordy.id}/akordy/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_akordy_na_pdf_verzi_da_404(self):
        self.client.force_authenticate(self.alice)
        response = self.client.get(f"/api/verze-pisni/{self.verze_pdf.id}/akordy/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_prepise_zapis_a_regeneruje_pdf(self):
        self.client.force_authenticate(self.alice)
        puvodni_nazev_souboru = self.verze_akordy.soubor.name if self.verze_akordy.soubor else None
        novy_zapis = {
            "schema": 2,
            "takt": {"dob": 3, "hodnota": 4},
            "tempo": 120,
            "sekce": [
                {"nazev": "Bridge", "radky": [{"takty": [{"bunky": ["Em", "G", "D"]}]}], "repetice": []}
            ],
        }
        response = self.client.put(
            f"/api/verze-pisni/{self.verze_akordy.id}/akordy/", novy_zapis, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn("pocet_anotaci_ktere_mohly_ujet", response.data)

        self.verze_akordy.refresh_from_db()
        self.assertEqual(self.verze_akordy.akordy["sekce"][0]["nazev"], "Bridge")
        self.assertEqual(self.verze_akordy.akordy["takt"]["dob"], 3)
        self.assertTrue(self.verze_akordy.soubor)
        self.assertNotEqual(self.verze_akordy.soubor.name, puvodni_nazev_souboru)
        with self.verze_akordy.soubor.open("rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")

    def test_put_vraci_pocet_anotaci_ktere_mohly_ujet(self):
        Anotace.objects.create(
            verze_pisne=self.verze_akordy,
            vlastnik=self.alice,
            data=[
                {"id": "a", "strana": 1, "x": 0.1, "y": 0.1, "sirka": 0.2, "text": "raz"},
                {"id": "b", "strana": 1, "x": 0.3, "y": 0.3, "sirka": 0.2, "text": "dva"},
            ],
        )
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            f"/api/verze-pisni/{self.verze_akordy.id}/akordy/", self.zapis, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pocet_anotaci_ktere_mohly_ujet"], 2)

    def test_clen_nemuze_prepsat_cizi_potvrzeny_zapis(self):
        cizi = VerzePisne.objects.create(
            pisen=self.pisen,
            zdroj=VerzePisne.ZDROJ_AKORDY,
            stav=VerzePisne.STAV_CONFIRMED,
            akordy=self.zapis,
        )
        self.client.force_authenticate(self.bob)
        response = self.client.put(
            f"/api/verze-pisni/{cizi.id}/akordy/", self.zapis, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_s_neplatnym_zapisem_neulozi_nic(self):
        self.client.force_authenticate(self.alice)
        response = self.client.put(
            f"/api/verze-pisni/{self.verze_akordy.id}/akordy/",
            {
                "schema": 2,
                "takt": {"dob": 4, "hodnota": 4},
                "sekce": [{"nazev": "X", "radky": [{"takty": [{"bunky": ["A", "B", "C"]}]}]}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.verze_akordy.refresh_from_db()
        self.assertEqual(self.verze_akordy.akordy, self.zapis)


class PridatPisenDoZpevnikuTests(TestCase):
    """GET dalsi-kod, POST pridat-pisen na ZpevnikViewSet."""

    def setUp(self):
        self.zpevnik = Zpevnik.objects.create(nazev="Zkušebna")
        self.pisen = Pisen.objects.create(nazev="Nová píseň")
        self.clen = User.objects.create_user("clen-pridani", password="heslo123")
        self.client = APIClient()

    def test_navrh_kodu_pro_prazdny_zpevnik_je_101(self):
        self.client.force_authenticate(self.clen)
        response = self.client.get(f"/api/zpevniky/{self.zpevnik.id}/dalsi-kod/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kod"], 101)

    def test_navrh_kodu_pokracuje_za_nejvyssim(self):
        jina_pisen = Pisen.objects.create(nazev="Jiná")
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=jina_pisen, kod=205)
        self.client.force_authenticate(self.clen)
        response = self.client.get(f"/api/zpevniky/{self.zpevnik.id}/dalsi-kod/")
        self.assertEqual(response.data["kod"], 206)

    def test_clen_muze_pridat_pisen(self):
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            f"/api/zpevniky/{self.zpevnik.id}/pridat-pisen/",
            {"pisen": self.pisen.id, "kod": 101},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(
            PolozkaZpevniku.objects.filter(
                zpevnik=self.zpevnik, pisen=self.pisen, kod=101
            ).exists()
        )

    def test_kolize_kodu_odmitnuta(self):
        jina_pisen = Pisen.objects.create(nazev="Jiná")
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=jina_pisen, kod=101)
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            f"/api/zpevniky/{self.zpevnik.id}/pridat-pisen/",
            {"pisen": self.pisen.id, "kod": 101},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kod", response.data)

    def test_pisen_jde_pridat_jen_jednou(self):
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=self.pisen, kod=101)
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            f"/api/zpevniky/{self.zpevnik.id}/pridat-pisen/",
            {"pisen": self.pisen.id, "kod": 102},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pisen", response.data)

    def test_nepriblasenemu_uzivateli_se_odmita(self):
        response = self.client.post(
            f"/api/zpevniky/{self.zpevnik.id}/pridat-pisen/",
            {"pisen": self.pisen.id, "kod": 101},
            format="json",
        )
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )


class ZalozeniZpevnikuTests(TestCase):
    """POST /api/zpevniky/ — založení nového zpěvníku (PC_zpevnik_sprava.md bod 2)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            "admin-zalozeni", password="heslo123", is_staff=True
        )
        self.clen = User.objects.create_user("clen-zalozeni", password="heslo123")
        self.client = APIClient()

    def test_admin_zalozi_zpevnik(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/zpevniky/", {"nazev": "Nový repertoár"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(Zpevnik.objects.filter(nazev="Nový repertoár").exists())
        self.assertEqual(response.data["pisne"], [])

    def test_duplicitni_nazev_odmitnut(self):
        Zpevnik.objects.create(nazev="Repertoár")
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/zpevniky/", {"nazev": "Repertoár"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("nazev", response.data)

    def test_clen_nesmi_zalozit_zpevnik(self):
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            "/api/zpevniky/", {"nazev": "Repertoár členů"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Zpevnik.objects.filter(nazev="Repertoár členů").exists())


class CisloVerzeTests(TestCase):
    """VerzePisne.cislo — přiděluje server (max+1), přes všechny cesty
    vzniku verze (viz PC_zpevnik_akordovy_zapis_upravy.md bod 5)."""

    def setUp(self):
        self.pisen = Pisen.objects.create(nazev="Číslovaná píseň")
        self.clen = User.objects.create_user("clen-cislo", password="heslo123")
        self.admin = User.objects.create_user("admin-cislo", password="heslo123", is_staff=True)
        self.client = APIClient()

    def test_prvni_verze_dostane_cislo_1(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/", {"pisen": self.pisen.id, "stav": "confirmed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["cislo"], 1)

    def test_druha_verze_dostane_cislo_2(self):
        VerzePisne.objects.create(pisen=self.pisen, cislo=1, stav=VerzePisne.STAV_CONFIRMED)
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            "/api/verze-pisni/", {"pisen": self.pisen.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["cislo"], 2)

    def test_cislo_se_neprecisluje_po_smazani(self):
        VerzePisne.objects.create(pisen=self.pisen, cislo=1, stav=VerzePisne.STAV_CONFIRMED)
        druha = VerzePisne.objects.create(pisen=self.pisen, cislo=2, stav=VerzePisne.STAV_CONFIRMED)
        VerzePisne.objects.filter(cislo=1, pisen=self.pisen).delete()
        # další nová verze pokračuje za nejvyšším ZBÝVAJÍCÍM číslem (2), ne
        # za tím, co bylo smazáno
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/", {"pisen": self.pisen.id, "stav": "confirmed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["cislo"], 3)
        druha.refresh_from_db()
        self.assertEqual(druha.cislo, 2)  # nedotčeno

    def test_klient_nemuze_poslat_vlastni_cislo(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/verze-pisni/",
            {"pisen": self.pisen.id, "stav": "confirmed", "cislo": 999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["cislo"], 1)  # 999 se ignoruje, cislo je read-only

    def test_akordova_verze_taky_dostane_cislo(self):
        self.client.force_authenticate(self.clen)
        response = self.client.post(f"/api/pisne/{self.pisen.id}/verze-akordy/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["cislo"], 1)

    def test_cisla_ruznych_pisni_se_neovlivnuji(self):
        jina_pisen = Pisen.objects.create(nazev="Jiná píseň")
        VerzePisne.objects.create(pisen=jina_pisen, cislo=1, stav=VerzePisne.STAV_CONFIRMED)
        VerzePisne.objects.create(pisen=jina_pisen, cislo=2, stav=VerzePisne.STAV_CONFIRMED)
        self.assertEqual(self.pisen.dalsi_cislo_verze(), 1)  # nová píseň, žádná kolize


class SpaIndexCacheTests(TestCase):
    """index.html je jediná nehashovaná část frontendu a ukazuje na hashované
    bundly — bez `no-cache` by prohlížeč po nasazení držel starou appku."""

    def test_index_se_nekesuje(self):
        response = Client().get("/pisne/1/ctecka")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-cache")


class E001SystemCheckTests(TestCase):
    """Kontrola je vědomě vázaná na ENVIRONMENT, ne na DEBUG — Django test
    runner DEBUG vždy vynutí na False, takže vazba na DEBUG by kontrolu
    spouštěla i tady, v běžném `manage.py test` s X_ACCEL_REDIRECT=False."""

    @override_settings(ENVIRONMENT="production", X_ACCEL_REDIRECT=False)
    def test_produkce_bez_x_accel_redirect_spadne(self):
        chyby = zkontroluj_servirovani_souboru(None)
        self.assertEqual(len(chyby), 1)
        self.assertEqual(chyby[0].id, "zpevnik.E001")

    @override_settings(ENVIRONMENT="production", X_ACCEL_REDIRECT=True)
    def test_produkce_s_x_accel_redirect_projde(self):
        self.assertEqual(zkontroluj_servirovani_souboru(None), [])

    @override_settings(ENVIRONMENT="development", X_ACCEL_REDIRECT=False)
    def test_lokalni_vyvoj_bez_x_accel_redirect_projde(self):
        """Přesně scénář z README — lokální .env bez nginx."""
        self.assertEqual(zkontroluj_servirovani_souboru(None), [])


class MazaniPisneTests(TestCase):
    """DELETE /api/pisne/<id>/ a GET .../smazat-nahled/ (PC_zpevnik_sprava.md
    bod 5) — jen admin, kaskáda (verze, anotace, zařazení, položky
    setlistů), soubory z disku AŽ PO COMMITU, setlist samotný přežije."""

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="zpevnik-test-mazani-")
        prepinac = override_settings(MEDIA_ROOT=self.media)
        prepinac.enable()
        self.addCleanup(prepinac.disable)
        self.addCleanup(shutil.rmtree, self.media, True)

        self.admin = User.objects.create_user(
            "admin-mazani-pisne", password="heslo123", is_staff=True
        )
        self.clen = User.objects.create_user("clen-mazani-pisne", password="heslo123")
        self.client = APIClient()

    def _pisen_se_vsim(self):
        pisen = Pisen.objects.create(nazev="Píseň k smazání")
        verze = VerzePisne.objects.create(
            pisen=pisen,
            cislo=pisen.dalsi_cislo_verze(),
            soubor=pdf_upload(),
            stav=VerzePisne.STAV_CONFIRMED,
        )
        Anotace.objects.create(verze_pisne=verze, vlastnik=self.admin, data=[])
        Anotace.objects.create(pisen=pisen, vlastnik=self.admin, data=[])
        zpevnik = Zpevnik.objects.create(nazev="Zpěvník pro mazání písně")
        PolozkaZpevniku.objects.create(zpevnik=zpevnik, pisen=pisen, kod=101)
        setlist = Setlist.objects.create(nazev="Koncert")
        PolozkaSetlistu.objects.create(setlist=setlist, pisen=pisen, poradi=0)
        return pisen, verze, zpevnik, setlist

    def test_nahled_vraci_spravne_pocty(self):
        pisen, verze, zpevnik, setlist = self._pisen_se_vsim()
        self.client.force_authenticate(self.clen)
        response = self.client.get(f"/api/pisne/{pisen.id}/smazat-nahled/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["verzi"], 1)
        self.assertEqual(response.data["anotaci"], 2)
        self.assertEqual(response.data["zpevniky"], [zpevnik.nazev])
        self.assertEqual(response.data["setlisty"], 1)

    def test_admin_smaze_pisen_kaskadove_a_soubory_z_disku(self):
        pisen, verze, zpevnik, setlist = self._pisen_se_vsim()
        cesta_souboru = verze.soubor.path
        self.assertTrue(os.path.exists(cesta_souboru))

        self.client.force_authenticate(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f"/api/pisne/{pisen.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Pisen.objects.filter(id=pisen.id).exists())
        self.assertFalse(VerzePisne.objects.filter(id=verze.id).exists())
        self.assertEqual(Anotace.objects.filter(pisen_id=pisen.id).count(), 0)
        self.assertEqual(Anotace.objects.filter(verze_pisne_id=verze.id).count(), 0)
        self.assertFalse(PolozkaZpevniku.objects.filter(pisen_id=pisen.id).exists())
        self.assertFalse(PolozkaSetlistu.objects.filter(pisen_id=pisen.id).exists())
        # Setlist SAMOTNÝ zůstává, jen bez týhle položky.
        self.assertTrue(Setlist.objects.filter(id=setlist.id).exists())
        # Zpěvník taky zůstává (má i jiné/žádné jiné písně, ale nemazal se on).
        self.assertTrue(Zpevnik.objects.filter(id=zpevnik.id).exists())
        self.assertFalse(os.path.exists(cesta_souboru))

    def test_clen_nesmi_smazat_pisen(self):
        pisen, verze, zpevnik, setlist = self._pisen_se_vsim()
        self.client.force_authenticate(self.clen)
        response = self.client.delete(f"/api/pisne/{pisen.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Pisen.objects.filter(id=pisen.id).exists())

    def test_neprihlasenemu_se_odmita(self):
        pisen, verze, zpevnik, setlist = self._pisen_se_vsim()
        response = self.client.delete(f"/api/pisne/{pisen.id}/")
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )
        self.assertTrue(Pisen.objects.filter(id=pisen.id).exists())


class MazaniZpevnikuTests(TestCase):
    """DELETE /api/zpevniky/<id>/ a GET .../smazat-nahled/ — výhradní písně
    (jen v tomhle zpěvníku) zmizí i s verzemi/soubory/anotacemi, sdílené
    (i v jiném zpěvníku) přežijí."""

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="zpevnik-test-mazani-zpevniku-")
        prepinac = override_settings(MEDIA_ROOT=self.media)
        prepinac.enable()
        self.addCleanup(prepinac.disable)
        self.addCleanup(shutil.rmtree, self.media, True)

        self.admin = User.objects.create_user(
            "admin-mazani-zpevniku", password="heslo123", is_staff=True
        )
        self.clen = User.objects.create_user("clen-mazani-zpevniku", password="heslo123")
        self.client = APIClient()

        self.zpevnik = Zpevnik.objects.create(nazev="Zpěvník k smazání")
        self.jiny_zpevnik = Zpevnik.objects.create(nazev="Jiný zpěvník")

        self.vyhradni = Pisen.objects.create(nazev="Jen v mazaném zpěvníku")
        self.vyhradni_verze = VerzePisne.objects.create(
            pisen=self.vyhradni,
            cislo=self.vyhradni.dalsi_cislo_verze(),
            soubor=pdf_upload("vyhradni.pdf"),
            stav=VerzePisne.STAV_CONFIRMED,
        )
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=self.vyhradni, kod=101)
        self.setlist_vyhradni = Setlist.objects.create(nazev="Jen výhradní")
        PolozkaSetlistu.objects.create(
            setlist=self.setlist_vyhradni, pisen=self.vyhradni, poradi=0
        )

        self.sdilena = Pisen.objects.create(nazev="V obou zpěvnících")
        PolozkaZpevniku.objects.create(zpevnik=self.zpevnik, pisen=self.sdilena, kod=102)
        PolozkaZpevniku.objects.create(zpevnik=self.jiny_zpevnik, pisen=self.sdilena, kod=201)

    def test_nahled_pocita_vyhradni_sdilene_a_setlisty(self):
        self.client.force_authenticate(self.clen)
        response = self.client.get(f"/api/zpevniky/{self.zpevnik.id}/smazat-nahled/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pisni_zmizi"], 1)
        self.assertEqual(response.data["pisni_zustane"], 1)
        self.assertEqual(response.data["setlisty"], 1)

    def test_admin_smaze_zpevnik_vyhradni_zmizi_sdilena_zustane(self):
        cesta_souboru = self.vyhradni_verze.soubor.path
        self.assertTrue(os.path.exists(cesta_souboru))

        self.client.force_authenticate(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f"/api/zpevniky/{self.zpevnik.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Zpevnik.objects.filter(id=self.zpevnik.id).exists())
        self.assertFalse(Pisen.objects.filter(id=self.vyhradni.id).exists())
        self.assertFalse(VerzePisne.objects.filter(id=self.vyhradni_verze.id).exists())
        self.assertFalse(os.path.exists(cesta_souboru))
        self.assertFalse(PolozkaSetlistu.objects.filter(pisen_id=self.vyhradni.id).exists())
        self.assertTrue(Setlist.objects.filter(id=self.setlist_vyhradni.id).exists())

        # sdílená píseň přežije a zůstane v tom druhém zpěvníku
        self.assertTrue(Pisen.objects.filter(id=self.sdilena.id).exists())
        self.assertTrue(
            PolozkaZpevniku.objects.filter(
                zpevnik=self.jiny_zpevnik, pisen=self.sdilena
            ).exists()
        )

    def test_clen_nesmi_smazat_zpevnik(self):
        self.client.force_authenticate(self.clen)
        response = self.client.delete(f"/api/zpevniky/{self.zpevnik.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Zpevnik.objects.filter(id=self.zpevnik.id).exists())


FIXTURE_AFRICA = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tests", "fixtures", "africa_moises.musicxml"
)
FIXTURE_THE_LOOK = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tests", "fixtures", "the_look_moises.musicxml"
)


class MusicXmlParserTests(TestCase):
    """import_musicxml.parsuj_musicxml — čisté parserové testy, bez DB/HTTP
    (PC_zpevnik_akordovy_zapis_upravy.md bod 6)."""

    def test_africa_fixture_se_precte_cele_bez_chyb(self):
        from .import_musicxml import parsuj_musicxml

        with open(FIXTURE_AFRICA, "rb") as f:
            vysledek = parsuj_musicxml(f)

        self.assertEqual(vysledek["pocet_taktu"], 101)
        self.assertEqual(vysledek["harmony_chyb"], 0)
        akordy = vysledek["akordy"]
        self.assertEqual(akordy["schema"], 2)
        self.assertEqual(akordy["takt"], {"dob": 4, "hodnota": 4})
        self.assertEqual(akordy["tempo"], 94)

        # 101 taktů / 4 na řádek -> 26 řádků (poslední neúplný, 1 takt)
        radky = akordy["sekce"][0]["radky"]
        self.assertEqual(len(radky), 26)
        self.assertEqual(sum(len(r["takty"]) for r in radky), 101)

        # takt 6 (index 5): "A . . C#m7" (viz XML — harmony na dobu 1 a 4)
        takt6 = radky[1]["takty"][1]
        self.assertEqual(takt6["bunky"], ["A", "", "", "C#m7"])

        # posledni takt (101, index 100): stejný vzorec, "A . . C#m7"
        posledni = radky[-1]["takty"][-1]
        self.assertEqual(posledni["bunky"], ["A", "", "", "C#m7"])

        # žádný takt v týhle fixture nemá vlastní přepis - je jen 4/4 všude
        self.assertTrue(all("takt" not in t for r in radky for t in r["takty"]))

    def test_akordy_z_fixture_projdou_validaci_serializeru(self):
        from .import_musicxml import parsuj_musicxml

        with open(FIXTURE_AFRICA, "rb") as f:
            vysledek = parsuj_musicxml(f)
        serializer = AkordovyZapisSerializer(data=vysledek["akordy"])
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def _xml(self, telo):
        hlavicka = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<score-partwise version="4.0"><part-list>'
            '<score-part id="P1"><part-name>X</part-name></score-part>'
            "</part-list><part id=\"P1\">"
        )
        return io.BytesIO((hlavicka + telo + "</part></score-partwise>").encode("utf-8"))

    def test_harmony_bez_korene_se_pocita_jako_neprectena(self):
        xml = self._xml(
            "<measure number=\"1\">"
            "<attributes><divisions>1</divisions>"
            "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            "<harmony><kind>major</kind></harmony>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "</measure>"
        )
        from .import_musicxml import parsuj_musicxml

        vysledek = parsuj_musicxml(xml)
        self.assertEqual(vysledek["harmony_chyb"], 1)
        self.assertEqual(vysledek["akordy"]["sekce"][0]["radky"][0]["takty"][0]["bunky"], ["", "", "", ""])

    def test_zmena_taktu_uprostred_skladby_se_projevi_jako_prepis(self):
        xml = self._xml(
            "<measure number=\"1\">"
            "<attributes><divisions>1</divisions>"
            "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            "<harmony><root><root-step>C</root-step></root><kind>major</kind></harmony>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "</measure>"
            "<measure number=\"2\">"
            "<attributes><time><beats>3</beats><beat-type>4</beat-type></time></attributes>"
            "<harmony><root><root-step>G</root-step></root><kind>major</kind></harmony>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "</measure>"
        )
        from .import_musicxml import parsuj_musicxml

        vysledek = parsuj_musicxml(xml)
        akordy = vysledek["akordy"]
        self.assertEqual(akordy["takt"], {"dob": 4, "hodnota": 4})
        takty = akordy["sekce"][0]["radky"][0]["takty"]
        self.assertNotIn("takt", takty[0])
        self.assertEqual(takty[1]["takt"], {"dob": 3, "hodnota": 4})
        self.assertEqual(takty[1]["bunky"], ["G", "", ""])

    def test_nezname_score_timewise_odmitnuto(self):
        from .import_musicxml import parsuj_musicxml

        xml = io.BytesIO(
            b'<?xml version="1.0"?><score-timewise version="4.0"></score-timewise>'
        )
        with self.assertRaises(Exception):
            parsuj_musicxml(xml)

    def test_the_look_fixture_predtakti_zkraceno_a_akordy_na_spravne_dobe(self):
        # the_look_moises.musicxml: takt 1 je předtaktí (Moises ho nezkrátí
        # v XML, jen před první akord dá plné 2 doby pomlk navíc) - musí
        # vyjít jako takt o 2 dobách s "A" na 1. době, ne akord uprostřed
        # plného 4/4 taktu. Takt 3 (Am na 3. době) je regulérní - beze změny.
        from .import_musicxml import parsuj_musicxml

        with open(FIXTURE_THE_LOOK, "rb") as f:
            vysledek = parsuj_musicxml(f)

        self.assertEqual(vysledek["pocet_taktu"], 92)
        self.assertEqual(vysledek["harmony_chyb"], 0)
        akordy = vysledek["akordy"]
        self.assertEqual(akordy["takt"], {"dob": 4, "hodnota": 4})
        self.assertEqual(akordy["tempo"], 95)

        takty = akordy["sekce"][0]["radky"][0]["takty"]
        self.assertEqual(takty[0]["bunky"], ["A", ""])
        self.assertEqual(takty[0]["takt"], {"dob": 2, "hodnota": 4})
        self.assertEqual(takty[1]["bunky"], ["", "", "", ""])
        self.assertNotIn("takt", takty[1])
        self.assertEqual(takty[2]["bunky"], ["", "", "Am", ""])
        self.assertNotIn("takt", takty[2])
        self.assertEqual(takty[3]["bunky"], ["", "", "", ""])

    def test_africa_fixture_nema_predtakti_prvni_takt_beze_zmeny(self):
        # Africa: první takt je úplně tichý (žádná harmonie) - "předtaktí"
        # heuristika se nesmí spustit jen proto, že je první takt skladby.
        from .import_musicxml import parsuj_musicxml

        with open(FIXTURE_AFRICA, "rb") as f:
            vysledek = parsuj_musicxml(f)

        prvni_takt = vysledek["akordy"]["sekce"][0]["radky"][0]["takty"][0]
        self.assertEqual(prvni_takt["bunky"], ["", "", "", ""])
        self.assertNotIn("takt", prvni_takt)

    def test_predtakti_jen_pokud_pred_prvni_harmonii_je_jen_ticho(self):
        # Znějící nota (ne pomlka) před první harmonií v prvním taktu ->
        # neni to "tiché zahřívací" místo, předtaktí heuristika se nesmí
        # uplatnit.
        xml = self._xml(
            "<measure number=\"1\">"
            "<attributes><divisions>1</divisions>"
            "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            "<note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<harmony><root><root-step>G</root-step></root><kind>major</kind></harmony>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "</measure>"
        )
        from .import_musicxml import parsuj_musicxml

        vysledek = parsuj_musicxml(xml)
        takt1 = vysledek["akordy"]["sekce"][0]["radky"][0]["takty"][0]
        self.assertEqual(takt1["bunky"], ["", "", "G", ""])
        self.assertNotIn("takt", takt1)

    def test_predtakti_se_neuplatni_na_druhy_takt(self):
        # Stejný vzor pomlk před harmonií, ale ve DRUHÉM taktu skladby -
        # předtaktí je z definice jen na začátku, tenhle akord musí
        # zůstat na spočtené (nezkrácené) době.
        xml = self._xml(
            "<measure number=\"1\">"
            "<attributes><divisions>1</divisions>"
            "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "</measure>"
            "<measure number=\"2\">"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "<harmony><root><root-step>D</root-step></root><kind>major</kind></harmony>"
            "<note><rest/><duration>1</duration></note>"
            "<note><rest/><duration>1</duration></note>"
            "</measure>"
        )
        from .import_musicxml import parsuj_musicxml

        vysledek = parsuj_musicxml(xml)
        takt2 = vysledek["akordy"]["sekce"][0]["radky"][0]["takty"][1]
        self.assertEqual(takt2["bunky"], ["", "", "D", ""])
        self.assertNotIn("takt", takt2)

    def test_harmony_offset_posune_dobu(self):
        # <offset> u <harmony> (Moises konvence, může být i záporný) -
        # posune vypočtenou dobu, i když je note/rest struktura beze změny.
        xml = self._xml(
            "<measure number=\"1\">"
            "<attributes><divisions>4</divisions>"
            "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            "<harmony><root><root-step>C</root-step></root><kind>major</kind>"
            "<offset>4</offset></harmony>"
            "<note><rest/><duration>4</duration></note>"
            "<note><rest/><duration>4</duration></note>"
            "<harmony><root><root-step>G</root-step></root><kind>major</kind>"
            "<offset>-4</offset></harmony>"
            "<note><rest/><duration>4</duration></note>"
            "<note><rest/><duration>4</duration></note>"
            "</measure>"
        )
        from .import_musicxml import parsuj_musicxml

        vysledek = parsuj_musicxml(xml)
        takt1 = vysledek["akordy"]["sekce"][0]["radky"][0]["takty"][0]
        # C: bez posunu doba 0, s offsetem +4 (1 doba) -> doba 1.
        # G: bez posunu doba 2 (po 2 dobách pomlk), s offsetem -4 -> doba 1,
        # ale to uz je obsazene C, takze G ho prepise (poslednejsi harmonie
        # na stejne dobe vyhrava - stejne jako dosud).
        self.assertEqual(takt1["bunky"], ["", "G", "", ""])


class ImportMusicXmlApiTests(TestCase):
    """POST /api/pisne/<id>/verze-musicxml/ — end-to-end přes API."""

    def setUp(self):
        self.pisen = Pisen.objects.create(nazev="Africa", interpret="Toto")
        self.clen = User.objects.create_user("clen-musicxml", password="heslo123")
        self.client = APIClient()

    def _soubor(self):
        with open(FIXTURE_AFRICA, "rb") as f:
            obsah = f.read()
        return SimpleUploadedFile(
            "africa_moises.musicxml", obsah, content_type="application/xml"
        )

    def test_clen_naimportuje_musicxml(self):
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            f"/api/pisne/{self.pisen.id}/verze-musicxml/",
            {"soubor": self._soubor()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["pocet_taktu"], 101)
        self.assertEqual(response.data["harmony_chyb"], 0)

        verze = VerzePisne.objects.get(id=response.data["id"])
        self.assertEqual(verze.zdroj, VerzePisne.ZDROJ_AKORDY)
        self.assertEqual(verze.stav, VerzePisne.STAV_PERSONAL)
        self.assertEqual(verze.vlastnik_id, self.clen.id)
        self.assertEqual(verze.akordy["tempo"], 94)
        self.assertTrue(verze.soubor)
        with verze.soubor.open("rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")

    def test_bez_souboru_odmitnuto(self):
        self.client.force_authenticate(self.clen)
        response = self.client.post(
            f"/api/pisne/{self.pisen.id}/verze-musicxml/", {}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nepriblasenemu_se_odmita(self):
        response = self.client.post(
            f"/api/pisne/{self.pisen.id}/verze-musicxml/",
            {"soubor": self._soubor()},
            format="multipart",
        )
        self.assertIn(
            response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )
