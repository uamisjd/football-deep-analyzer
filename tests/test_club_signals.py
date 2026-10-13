"""Criterio positivo: sviluppo annotato PRIMA del selettore + controlli separati (docs/97)."""

import json
from pathlib import Path

import pytest

from fda.site.club_signals import club_signal

CASES = json.loads((Path(__file__).parent / "fixtures/vita_editorial_review_2026-10-12.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"sviluppo-{c['case']}-{c['expected']}")
def test_campione_editoriale_di_sviluppo(case):
    signal = club_signal(case["title"])
    assert (signal.kind if signal else "reject") == case["expected"], case["reason"]
    if signal:
        assert signal.evidence in case["title"]  # prova lessicale, non sintesi inventata


@pytest.mark.parametrize("title,kind,topic", [
    ("AZ Alkmaar: stadio dichiarato inagibile, gara spostata", "event", "stadio"),
    ("Twente, approvato un aumento di capitale", "event", "societa"),
    ("Braga: stipendi arretrati, interviene la proprietà", "event", "societa"),
    ("Wolves, esonerato il tecnico dopo la riunione", "event", "allenatore"),
    ("Dortmund, gli ultras annunciano la protesta", "event", "tifo"),
    ("Rennes, nominato il nuovo direttore sportivo", "event", "societa"),
    ("PSV: vendita dei biglietti vietata ai tifosi ospiti", "event", "tifo"),
    ("Inter, esonero del tecnico? La proprietà non conferma", "analysis", "allenatore"),
    ("Roma smentisce l'esonero del tecnico", "analysis", "allenatore"),
    ("Lazio, nessuna rissa: il club smentisce la ricostruzione", "analysis", "spogliatoio"),
    ('Torino: il tecnico dice "mi dimetto"', "analysis", "allenatore"),
    ("Benfica: incidente stradale per un tesserato", "event", "fuoricampo"),
    ("Genoa, nuova proprietà dopo il passaggio delle quote", "event", "societa"),
    ("Brest, ufficiale: il capitano rinnova fino al 2029", "event", "mercato"),
    ("Lipsia, tegola in allenamento: tempi di recupero lunghi", "event", "infortuni"),
    ("Siviglia, multa UEFA e diffida per il settore ospiti", "event", "societa"),
    ("L'ad del club: «Potremmo approvare la variante per lo stadio»", "analysis", "stadio"),
    ("Nizza, svolta Haise: la rimonta rilancia la squadra", "analysis", "allenatore"),
])
def test_controlli_separati_su_altri_club_e_modalita(title, kind, topic):
    signal = club_signal(title)
    assert signal is not None and signal.kind == kind and signal.topic == topic
    assert signal.evidence in title


@pytest.mark.parametrize("title", [
    "Nota ufficiale: Idrissa Gueye", "Il Larissa continua il campionato", "Rissato firma con il club",
    "Inter, squadra in forma: ecco le statistiche", "Il Tottenham guida la classifica dei minutaggi",
    "Rennes, intervista: dobbiamo fare più punti", "AZ, due pullman e 2000 tifosi allo stadio",
    "PSV, vince la solidarietà nella partita benefica", "Feyenoord, VIP in tribuna per la partita",
    "Sporting: il difensore vuole la maglia, il compagno insegue", "La squadra segue il modulo del tecnico",
    "Inter, protesta per il rigore secondo l'opinionista", "Formazioni AZ-PSV: la vigilia del derby",
    "Roma-Inter LIVE! Cronaca della protesta per un rigore", "Milan, i tifosi vogliono ritirare la maglia storica",
    "Pronostico e quote di Lens-Nizza: dove vederla in tv e streaming",
    "Fantacalcio: chi schierare in questa giornata di Serie A",
])
def test_controlli_negativi_non_confondono_parole_generiche_e_fatti(title):
    assert club_signal(title) is None
