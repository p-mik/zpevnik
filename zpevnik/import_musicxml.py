"""Import akordového zápisu ze souboru MusicXML (schéma 2, viz
PC_zpevnik_akordovy_zapis_upravy.md bod 6, a zpevnik/serializers.py
AkordovyZapisSerializer).

Podporuje jen NEKOMPRIMOVANÉ `.musicxml`/`.xml` (`<score-partwise>`), ne
zabalené `.mxl` (to je ZIP kontejner) — appka zatím nepotřebuje nic víc,
běžný export z notačního software (MuseScore, Moises AI Studio apod.) tenhle
tvar nabízí přímo. Jen PRVNÍ `<part>` — vícehlasé/vícenástrojové partitury
appka nepodporuje (akordový zápis je jednohlasý sled akordů, ne notový
zápis).

Čte se JEN rytmus (kolik dob má který takt, z `<time>`) a `<harmony>`
značky (kde se mění akord) — noty/pomlky samotné se ignorují, slouží tu
jen jako "hodiny" pro spočítání pozice `<harmony>` v taktu (offset od
začátku taktu / počet tiků na dobu, viz `_pridej_bunky_taktu`).

Takty se skládají do řádků po `TAKTU_NA_RADEK` (stejná konvence jako
zbytek appky — viz akordy_pdf.POCET_TAKTU_NA_RADEK), do JEDNÉ sekce —
MusicXML odsud nenese žádné rehearsal marky/sekce, které by šlo použít.
"""

import xml.etree.ElementTree as ET
from defusedxml.ElementTree import parse as bezpecne_parsuj_xml
from defusedxml.common import DefusedXmlException

from rest_framework.exceptions import ValidationError

TAKTU_NA_RADEK = 4
MAX_ZNAKU_BUNKA = 16

# `text` atribut u <kind> (když je) je vždycky přednější — to je přesně
# to, co si autor partitury přál zobrazit (viz Moises export: `<kind
# text="add9">major</kind>`). Tahle tabulka je jen záložní překlad
# sémantické hodnoty <kind>, pro soubory, které `text` neposílají.
KIND_SUFFIXY = {
    "major": "",
    "minor": "m",
    "augmented": "aug",
    "diminished": "dim",
    "dominant": "7",
    "major-seventh": "maj7",
    "minor-seventh": "m7",
    "diminished-seventh": "dim7",
    "augmented-seventh": "aug7",
    "half-diminished": "m7b5",
    "major-minor": "mMaj7",
    "major-sixth": "6",
    "minor-sixth": "m6",
    "dominant-ninth": "9",
    "major-ninth": "maj9",
    "minor-ninth": "m9",
    "dominant-11th": "11",
    "major-11th": "maj11",
    "minor-11th": "m11",
    "dominant-13th": "13",
    "major-13th": "maj13",
    "minor-13th": "m13",
    "suspended-second": "sus2",
    "suspended-fourth": "sus4",
    "power": "5",
    "none": "N.C.",
}


def _text(el, tag):
    if el is None:
        return None
    return el.findtext(tag)


def _pripona_alterace(hodnota_alter):
    """`root-alter`/`bass-alter` — desetinná čísla ve MusicXML (kvůli
    čtvrttónům), appka zná jen celé půltóny (#/b)."""
    if not hodnota_alter:
        return ""
    try:
        cislo = float(hodnota_alter)
    except ValueError:
        return ""
    pocet = int(round(abs(cislo)))
    if pocet == 0:
        return ""
    return ("#" if cislo > 0 else "b") * pocet


def _sestav_akord(harmony_el):
    """Vrátí textový zápis akordu (`"C#m7"`, `"A"`, …), nebo `None`, když
    <harmony> nejde přečíst (chybí kořen, nebo výsledek je moc dlouhý na
    buňku) — volající pak `<harmony>` započítá mezi nepřečtené."""
    root_el = harmony_el.find("root")
    krok = _text(root_el, "root-step")
    if not krok:
        return None

    zaklad = krok + _pripona_alterace(_text(root_el, "root-alter"))

    kind_el = harmony_el.find("kind")
    if kind_el is None:
        pripona = ""
    else:
        text_atribut = kind_el.get("text")
        if text_atribut is not None:
            pripona = text_atribut
        else:
            hodnota = (kind_el.text or "").strip()
            pripona = KIND_SUFFIXY.get(hodnota, hodnota)

    bass_el = harmony_el.find("bass")
    bass_krok = _text(bass_el, "bass-step")
    bass_text = ""
    if bass_krok:
        bass_text = "/" + bass_krok + _pripona_alterace(_text(bass_el, "bass-alter"))

    text = zaklad + pripona + bass_text
    if not text or len(text) > MAX_ZNAKU_BUNKA:
        return None
    return text


def _tiku_na_dobu(divisions, beat_type):
    # <divisions> je vždy "tiků na čtvrťovou notu", bez ohledu na beat-type
    # (to říká, jaká notová hodnota = jedna doba, viz komentář v modulu).
    return divisions * 4 / beat_type


def _zpracuj_takt(measure_el, stav):
    """`stav` (měnitelný dict) nese `divisions`/`dob`/`hodnota`, které mezi
    takty přežívají, dokud je nepřepíše další `<attributes>` — MusicXML je
    nastavuje jen tam, kde se MĚNÍ, ne v každém taktu znovu."""
    chyb = 0

    attrs_el = measure_el.find("attributes")
    if attrs_el is not None:
        divisions_text = attrs_el.findtext("divisions")
        if divisions_text:
            stav["divisions"] = float(divisions_text)
        time_el = attrs_el.find("time")
        if time_el is not None:
            beats = time_el.findtext("beats")
            beat_type = time_el.findtext("beat-type")
            if beats and beat_type:
                stav["dob"] = int(beats)
                stav["hodnota"] = int(beat_type)

    for direction_el in measure_el.findall("direction"):
        for sound_el in direction_el.findall("sound"):
            tempo = sound_el.get("tempo")
            if tempo and stav.get("tempo") is None:
                # Jen PRVNÍ tempo v celé skladbě — schéma 2 má tempo jedno,
                # globální pro celý dokument (žádné "tempo od taktu X"),
                # takže případné pozdější změny appka nemá kam uložit.
                stav["tempo"] = round(float(tempo))

    dob = stav["dob"]
    tiku_na_dobu = _tiku_na_dobu(stav["divisions"], stav["hodnota"])
    bunky = [""] * dob
    tik = 0.0

    for el in measure_el:
        if el.tag == "harmony":
            doba_idx = int(tik // tiku_na_dobu) if tiku_na_dobu else 0
            doba_idx = max(0, min(dob - 1, doba_idx))
            akord = _sestav_akord(el)
            if akord is None:
                chyb += 1
            else:
                bunky[doba_idx] = akord
        elif el.tag == "note":
            trvani = el.findtext("duration")
            je_soucast_akordu = el.find("chord") is not None
            if trvani and not je_soucast_akordu:
                tik += float(trvani)
        elif el.tag == "backup":
            trvani = el.findtext("duration")
            if trvani:
                tik -= float(trvani)
        elif el.tag == "forward":
            trvani = el.findtext("duration")
            if trvani:
                tik += float(trvani)

    takt = {"bunky": bunky}
    if (dob, stav["hodnota"]) != (stav["takt_vychozi"]["dob"], stav["takt_vychozi"]["hodnota"]):
        takt["takt"] = {"dob": dob, "hodnota": stav["hodnota"]}
    return takt, chyb


def parsuj_musicxml(soubor):
    """`soubor` — file-like objekt (Django `UploadedFile` i obyčejné `open()`
    fungují, čte se přes `ET.parse`). Vrací dict:

        {
          "akordy": {...validated i "syrová" data pro AkordovyZapisSerializer...},
          "pocet_taktu": int,
          "harmony_chyb": int,   # kolik <harmony> značek se nepodařilo přečíst
        }

    Sám nic nevaliduje přes AkordovyZapisSerializer — to je na volající
    straně (stejně jako import_pisni.proved_import nechává obsahovou
    validaci na serializerech), tady se jen řeší tvar MusicXML → náš JSON.
    Neplatné/nerozpoznatelné XML zvedne `ValidationError`.
    """
    try:
        soubor.seek(0)
    except (AttributeError, OSError):
        pass
    try:
        strom = bezpecne_parsuj_xml(soubor)
    except ET.ParseError as chyba:
        raise ValidationError({"soubor": [f"MusicXML se nepodařilo přečíst: {chyba}"]})
    except DefusedXmlException as chyba:
        # Škodlivé/podezřelé konstrukce (entity bomby, externí entity apod.)
        # — defusedxml je odmítne dřív, než by se vůbec začaly parsovat.
        raise ValidationError({"soubor": [f"MusicXML odmítnuto z bezpečnostních důvodů: {chyba}"]})

    root = strom.getroot()
    if root.tag not in ("score-partwise",):
        raise ValidationError(
            {"soubor": ["Jen 'score-partwise' MusicXML je podporované (ne komprimované .mxl)."]}
        )

    part_el = root.find("part")
    if part_el is None:
        raise ValidationError({"soubor": ["Soubor neobsahuje žádný part."]})

    measures = part_el.findall("measure")
    if not measures:
        raise ValidationError({"soubor": ["Soubor neobsahuje žádný takt."]})

    # Výchozí takt dokumentu = takt PRVNÍHO taktu partitury — zjistí se
    # zvlášť předem, ať `_zpracuj_takt` může porovnávat "je tenhle takt
    # jiný než výchozí" hned od prvního taktu (ne jen od druhého dál).
    prvni_attrs = measures[0].find("attributes")
    prvni_time = prvni_attrs.find("time") if prvni_attrs is not None else None
    if prvni_time is None or not prvni_time.findtext("beats"):
        raise ValidationError({"soubor": ["První takt nemá určené 'time' (počet dob)."]})
    if prvni_attrs.findtext("divisions") is None:
        raise ValidationError({"soubor": ["První takt nemá určené 'divisions'."]})

    takt_vychozi = {
        "dob": int(prvni_time.findtext("beats")),
        "hodnota": int(prvni_time.findtext("beat-type")),
    }

    stav = {
        "divisions": float(prvni_attrs.findtext("divisions")),
        "dob": takt_vychozi["dob"],
        "hodnota": takt_vychozi["hodnota"],
        "tempo": None,
        "takt_vychozi": takt_vychozi,
    }

    vsechny_takty = []
    harmony_chyb = 0
    for measure_el in measures:
        takt, chyb = _zpracuj_takt(measure_el, stav)
        vsechny_takty.append(takt)
        harmony_chyb += chyb

    radky = [
        {"takty": vsechny_takty[i : i + TAKTU_NA_RADEK]}
        for i in range(0, len(vsechny_takty), TAKTU_NA_RADEK)
    ]

    akordy = {
        "schema": 2,
        "takt": takt_vychozi,
        "tempo": stav["tempo"],
        "sekce": [{"nazev": "", "radky": radky, "repetice": []}],
    }

    return {
        "akordy": akordy,
        "pocet_taktu": len(vsechny_takty),
        "harmony_chyb": harmony_chyb,
    }
