import os
import shutil
import tempfile
from io import StringIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .apps import zkontroluj_servirovani_souboru
from .models import Pisen, VerzePisne, Zpevnik

# Minimální, ale platné PDF (rozhodují úvodní magic bytes "%PDF-").
PDF_OBSAH = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


def pdf_upload(nazev="noty.pdf", obsah=PDF_OBSAH):
    return SimpleUploadedFile(nazev, obsah, content_type="application/pdf")


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

        self.pisen = Pisen.objects.create(kod=1, nazev="Testovací píseň")
        self.cizi_pisen = Pisen.objects.create(kod=2, nazev="Jiná píseň")

        self.zpevnik = Zpevnik.objects.create(nazev="Testovací zpěvník")
        self.zpevnik.pisne.add(self.pisen)
        self.zpevnik.vygeneruj_verejny_token()

        self.jiny_zpevnik = Zpevnik.objects.create(nazev="Jiný zpěvník")
        self.jiny_zpevnik.pisne.add(self.cizi_pisen)
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
        Pisen.objects.create(kod=10, nazev="Skrytá píseň")

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
        self.pisen = Pisen.objects.create(kod=20, nazev="Sdílená píseň")
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
        self.pisen = Pisen.objects.create(kod=30, nazev="Logika verzí")
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
            data={"kod": 99, "nazev": "Bez CSRF"},
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
            data={"kod": 100, "nazev": "S CSRF"},
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
        self.pisen = Pisen.objects.create(kod=500, nazev="Píseň s notami")

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
        self.pisen = Pisen.objects.create(kod=600, nazev="Píseň ke stažení")
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
        self.pisen = Pisen.objects.create(kod=700, nazev="Veřejná píseň")
        self.jen_personal = Pisen.objects.create(kod=701, nazev="Jen osobní verze")
        self.bezna = self.nahraj(self.pisen, VerzePisne.STAV_CONFIRMED)
        self.personal = self.nahraj(
            self.jen_personal, VerzePisne.STAV_PERSONAL, vlastnik=self.alice
        )

        self.zpevnik = Zpevnik.objects.create(nazev="Veřejný zpěvník")
        self.zpevnik.pisne.add(self.pisen, self.jen_personal)
        self.token = self.zpevnik.vygeneruj_verejny_token()

        # Píseň mimo tenhle zpěvník (je v jiném, taky veřejném).
        self.cizi_pisen = Pisen.objects.create(kod=800, nazev="Cizí píseň")
        self.cizi_verze = self.nahraj(self.cizi_pisen, VerzePisne.STAV_CONFIRMED)
        self.jiny_zpevnik = Zpevnik.objects.create(nazev="Jiný zpěvník")
        self.jiny_zpevnik.pisne.add(self.cizi_pisen)
        self.jiny_token = self.jiny_zpevnik.vygeneruj_verejny_token()

    def url(self, token, kod):
        return f"/api/verejny/{token}/pisen/{kod}/soubor/"

    def test_verejny_token_da_soubor_bez_prihlaseni(self):
        response = self.client.get(self.url(self.token, self.pisen.kod))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["X-Accel-Redirect"], "/protected/" + self.bezna.soubor.name
        )

    def test_verejny_token_nikdy_neda_personal_verzi(self):
        response = self.client.get(self.url(self.token, self.jen_personal.kod))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn("X-Accel-Redirect", response)

    def test_verejny_token_neda_pisen_z_jineho_zpevniku(self):
        # Píseň existuje a má veřejnou verzi, ale v tomhle zpěvníku není.
        response = self.client.get(self.url(self.token, self.cizi_pisen.kod))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # A přes svůj vlastní token dostupná je — takže to fakt dělá kontrola
        # příslušnosti, ne nějaká jiná náhoda.
        self.assertEqual(
            self.client.get(self.url(self.jiny_token, self.cizi_pisen.kod)).status_code,
            status.HTTP_200_OK,
        )

    def test_neplatny_token_neda_nic(self):
        for token in ["neexistujici", "x", self.token + "a", self.token[:-1]]:
            response = self.client.get(self.url(token, self.pisen.kod))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, token)

    def test_odvolany_token_prestane_fungovat(self):
        stary = self.token
        self.zpevnik.vygeneruj_verejny_token()  # rotace tokenu
        response = self.client.get(self.url(stary, self.pisen.kod))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_zpevnik_bez_tokenu_neni_dostupny(self):
        self.zpevnik.verejny_token = None
        self.zpevnik.save()
        response = self.client.get(self.url(self.token, self.pisen.kod))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_vypis_zpevniku_nabizi_url_jen_k_verejnym_souborum(self):
        response = self.client.get(f"/api/verejny/{self.token}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        podle_kodu = {p["kod"]: p for p in response.data["pisne"]}
        self.assertIsNotNone(podle_kodu[self.pisen.kod]["soubor_url"])
        # Píseň, která má jen personal verzi, veřejné URL nedostane.
        self.assertIsNone(podle_kodu[self.jen_personal.kod]["soubor_url"])
        # A nikde se neprozradí cesta na disk.
        self.assertNotIn(self.bezna.soubor.name, str(response.data))


class MazaniSouboruTests(SouboroveTestyZaklad):
    def setUp(self):
        super().setUp()
        self.pisen = Pisen.objects.create(kod=900, nazev="Píseň k mazání")

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
