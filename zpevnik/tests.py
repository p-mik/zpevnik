from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Pisen, VerzePisne, Zpevnik


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
