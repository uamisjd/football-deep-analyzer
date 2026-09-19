"""Proiezioni di stagione: la pagina dice quello che i dati sostengono (audit `docs/45`).

Due frasi, misurate sul sito pubblicato il 2026-09-19:

1. «Monte Carlo su 10000 stagioni simulate»: l'unico numero della pagina senza il
   separatore delle migliaia, mentre il resto del sito scrive «1.988 partite»,
   «154.727 controlli», «7.498 schede» (convenzione `docs/24` §4);
2. «Le squadre senza storico sufficiente (neopromosse) usano parametri neutri di lega»:
   il fallback a parametri neutri scatta solo per le squadre **assenti** dallo storico
   di allenamento (0 su 132 quel giorno), non per quelle con poche gare — che invece
   esistono (14 squadre sotto le 10 gare, minima 3) e non erano dichiarate da nessuna
   parte. Ora la pagina le nomina, lega per lega.

I test costruiscono la pagina da uno store minimo e la leggono come fa il lettore.
"""

from __future__ import annotations

import html as html_mod
import re

import pandas as pd

from fda.site.build import SiteBuilder
from fda.store import Store

LEGA = "ITA1"
SQUADRE = ("Inter", "Juventus", "Milan", "Frosinone")


def _sim_row(team: str, i: int) -> dict:
    return {"league_key": LEGA, "team": team, "played": 5, "points": 3 * (3 - i),
            "exp_points": 60.0 - 8 * i, "pos_mean": 1.0 + i, "p_title": 0.4 - 0.1 * i,
            "top_n": 4, "p_top_n": 0.9 - 0.2 * i, "p_top4": 0.9 - 0.2 * i,
            "p_rel": 0.01 * i, "n_sims": 10_000, "n_train": 1_183,
            "model_version": "test", "made_at": "2026-09-19 18:03:48+00:00"}


def _history(conteggi: dict[str, int]) -> list[dict]:
    """`n` gare di storico per squadra: è il dato da cui dipende la nota della pagina."""
    rows, giorno = [], 0
    for squadra, n in conteggi.items():
        for _ in range(n):
            rows.append({"league_key": LEGA,
                         "date": pd.Timestamp("2025-08-10") + pd.Timedelta(days=giorno),
                         "season": "2025/2026", "home": squadra, "away": "Avversario",
                         "home_goals": 1, "away_goals": 1})
            giorno += 1
    return rows


def _build(tmp_path, conteggi: dict[str, int]) -> str:
    st = Store(tmp_path / "processed")
    st.write("season_sim", pd.DataFrame([_sim_row(t, i) for i, t in enumerate(SQUADRE)]))
    st.write("history", pd.DataFrame(_history(conteggi)))
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_stagione()
    html = (out / "stagione.html").read_text(encoding="utf-8")
    st.close()
    return html


def _testo(html: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", html)))


def test_numero_simulazioni_con_separatore(tmp_path):
    """«10.000», con il separatore delle migliaia come ogni altro numero del sito."""
    html = _build(tmp_path, {s: 40 for s in SQUADRE})
    testo = _testo(html)
    assert "10.000 stagioni simulate" in testo
    assert re.search(r"\b10000\b", testo) is None, "numero grezzo senza separatore"


def test_squadre_con_poco_storico_nominate(tmp_path):
    """3 gare di storico: la squadra è dichiarata sotto la tabella, con la soglia."""
    conteggi = {"Inter": 40, "Juventus": 40, "Milan": 40, "Frosinone": 3}
    testo = _testo(_build(tmp_path, conteggi))
    assert "Poche gare di storico: Frosinone" in testo
    assert "1 squadra sotto le 10 gare di allenamento" in testo
    # l'errore standard pubblicato misura solo il rumore della simulazione: è dichiarato
    assert "più incerta di quanto dica l'errore standard" in testo


def test_intro_dice_che_nessuna_squadra_e_senza_storico(tmp_path):
    """Tutte le squadre hanno almeno una gara: il fallback a parametri neutri non scatta."""
    conteggi = {"Inter": 40, "Juventus": 40, "Milan": 40, "Frosinone": 3}
    testo = _testo(_build(tmp_path, conteggi))
    assert "oggi non ce n'è nessuna (tutte le 4 hanno almeno una gara" in testo
    assert "1 squadra ha meno di 10 gare" in testo


def test_squadra_senza_storico_dichiarata(tmp_path):
    """Senza una gara nello storico il modello userebbe i parametri neutri: va detta."""
    conteggi = {"Inter": 40, "Juventus": 40, "Milan": 40, "Frosinone": 0}
    testo = _testo(_build(tmp_path, conteggi))
    assert "ce n'è 1" in testo
    assert "Poche gare di storico: Frosinone" in testo
