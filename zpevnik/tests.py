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
from .models import Anotace, Pisen, PolozkaZpevniku, Slozka, VerzePisne, Zpevnik

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
    """Import (fáze 1e) — jen admin, atomicita, idempotence přes kód."""

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
            ]
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

    def test_kod_uz_ve_cilovem_zpevniku_odmitne_cely_import(self):
        """Kód je od fáze 2b vlastnost zařazení do KONKRÉTNÍHO zpěvníku, ne
        písně — kolize se proto řeší jen proti zpěvníku, který plán osloví
        jménem (tady `cely_zpevnik`), ne globálně přes celou DB."""
        existujici = Pisen.objects.create(nazev="Existující píseň")
        cil = Zpevnik.objects.create(nazev="Moje kniha")
        PolozkaZpevniku.objects.create(zpevnik=cil, pisen=existujici, kod=101)

        self.client.force_authenticate(self.admin)
        plan = self.zakladni_plan()
        plan["cely_zpevnik"] = {"nazev": "Moje kniha", "vytvorit": True}
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Ani kod=102 (validní, nekolidující) se nesmí založit — buď vše, nebo nic.
        self.assertEqual(Pisen.objects.count(), 1)
        self.assertEqual(cil.polozky.count(), 1)

    def test_stejny_kod_v_jinem_zpevniku_nekoliduje(self):
        """Dvě různé kapely/repertoáry mohou mít stejné číslo zároveň — kód
        je jedinečný jen VNITŘ jednoho zpěvníku, ne napříč všemi."""
        existujici = Pisen.objects.create(nazev="Existující píseň jinde")
        jina_kapela = Zpevnik.objects.create(nazev="Jiná kapela")
        PolozkaZpevniku.objects.create(zpevnik=jina_kapela, pisen=existujici, kod=101)

        self.client.force_authenticate(self.admin)
        plan = self.zakladni_plan()
        plan["cely_zpevnik"] = {"nazev": "Moje nová kniha", "vytvorit": True}
        response = self.zavolej(self.kniha(3), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Pisen.objects.count(), 3)

    def test_druhe_spusteni_stejneho_importu_do_stejne_knihy_nevyrobi_duplicity(self):
        """Idempotence: druhý běh se stejným plánem do STEJNÉHO zpěvníku
        (jménem) se odmítne dřív, než by cokoliv založil znovu."""
        self.client.force_authenticate(self.admin)
        plan = self.zakladni_plan()
        plan["cely_zpevnik"] = {"nazev": "Moje kniha", "vytvorit": True}

        prvni = self.zavolej(self.kniha(3), plan)
        self.assertEqual(prvni.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Pisen.objects.count(), 2)

        druhy = self.zavolej(self.kniha(3), plan)
        self.assertEqual(druhy.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pisen.objects.count(), 2)

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
        plan["cely_zpevnik"] = {"nazev": "Čerstvá kniha", "vytvorit": True}
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
        }
        response = self.zavolej(self.kniha(1), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Slozka.objects.filter(nazev="Ploužáky").exists())

    def test_opakovany_import_do_stejne_kategorie_nezdvoji_slozku(self):
        """Druhé kolo s NOVÝMI kódy do stejné kategorie musí přiřadit do
        stejné složky/zpěvníku, ne vyrobit druhou 'Ploužáky'."""
        self.client.force_authenticate(self.admin)
        plan1 = {
            "pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}],
            "kategorie": [{"digit": "1", "nazev": "Ploužáky", "vytvorit": True}],
        }
        self.assertEqual(
            self.zavolej(self.kniha(1), plan1).status_code, status.HTTP_201_CREATED
        )

        plan2 = {
            "pisne": [{"kod": 103, "nazev": "C", "stranky": [1]}],
            "kategorie": [{"digit": "1", "nazev": "Ploužáky", "vytvorit": True}],
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
            "cely_zpevnik": {"nazev": "ŠUBAPS zpěvník 2026", "vytvorit": True},
        }
        response = self.zavolej(self.kniha(2), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        cely = Zpevnik.objects.get(nazev="ŠUBAPS zpěvník 2026")
        self.assertIsNone(cely.slozka)
        self.assertEqual(sorted(cely.polozky.values_list("kod", flat=True)), [101, 205])
        # kod 205 nebyl v žádné vytvořené kategorii, ale v celé knize být musí
        plouzaky = Zpevnik.objects.get(nazev="Ploužáky")
        self.assertEqual(list(plouzaky.polozky.values_list("kod", flat=True)), [101])

    def test_cely_zpevnik_neni_povinny(self):
        self.client.force_authenticate(self.admin)
        plan = {
            "pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}],
            "cely_zpevnik": {"nazev": "Cokoliv", "vytvorit": False},
        }
        response = self.zavolej(self.kniha(1), plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Zpevnik.objects.filter(nazev="Cokoliv").exists())

    def test_cely_zpevnik_bez_pole_v_planu_nic_nezalozi(self):
        """Starší/minimální plán bez cely_zpevnik vůbec nesmí spadnout."""
        self.client.force_authenticate(self.admin)
        response = self.zavolej(self.kniha(1), {"pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}]})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_opakovany_import_doplni_stejny_cely_zpevnik(self):
        self.client.force_authenticate(self.admin)
        plan1 = {
            "pisne": [{"kod": 101, "nazev": "A", "stranky": [1]}],
            "cely_zpevnik": {"nazev": "Kniha", "vytvorit": True},
        }
        self.assertEqual(
            self.zavolej(self.kniha(1), plan1).status_code, status.HTTP_201_CREATED
        )
        plan2 = {
            "pisne": [{"kod": 102, "nazev": "B", "stranky": [1]}],
            "cely_zpevnik": {"nazev": "Kniha", "vytvorit": True},
        }
        self.assertEqual(
            self.zavolej(self.kniha(1), plan2).status_code, status.HTTP_201_CREATED
        )

        self.assertEqual(Zpevnik.objects.filter(nazev="Kniha").count(), 1)
        kniha = Zpevnik.objects.get(nazev="Kniha")
        self.assertEqual(sorted(kniha.polozky.values_list("kod", flat=True)), [101, 102])


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
