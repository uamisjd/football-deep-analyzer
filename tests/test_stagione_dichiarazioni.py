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


def test_marcatore_sulle_squadre_con_poco_storico(tmp_path):
    """Accanto al nome, un ◇ dice che quella proiezione poggia su poche gare."""
    conteggi = {"Inter": 40, "Juventus": 40, "Milan": 40, "Frosinone": 3}
    html = _build(tmp_path, conteggi)
    riga = re.search(r"<tr><td>Frosinone.*?</tr>", html, re.DOTALL)
    assert riga, "la riga della squadra fragile deve esistere"
    assert "◇" in riga.group(0) and "Meno di 10 gare di storico" in riga.group(0)
    riga_ok = re.search(r"<tr><td>Inter.*?</tr>", html, re.DOTALL)
    assert "◇" not in riga_ok.group(0), "chi ha storico non porta il marcatore"


def test_convenzione_degli_estremi_dichiarata_e_applicata(tmp_path):
    """`docs/78` §12: la pagina Proiezioni usa la stessa convenzione della scheda partita.

    Un valore non nullo sotto il mezzo punto si legge «<1%» e uno sopra il 99,5 «>99%»:
    «0%»/«100%» si leggerebbero «impossibile»/«certo». Lo zero vero resta «0%». La pagina
    lo dichiara nella sua introduzione — altrimenti «<1%» è un simbolo senza spiegazione,
    e la scheda partita e questa pagina potrebbero divergere senza che nessuna delle due
    sbagli il conto (i 4 numeri diversi del 2026-10-11, `docs/78` §12).
    """
    st = Store(tmp_path / "processed")
    righe = [
        dict(_sim_row("Inter", 0), p_title=0.004, p_top_n=0.9999, p_top4=0.9999, p_rel=0.0),
        dict(_sim_row("Juventus", 1), p_title=0.005, p_top_n=0.004, p_top4=0.004, p_rel=0.9999),
        _sim_row("Milan", 2), _sim_row("Frosinone", 3),
    ]
    st.write("season_sim", pd.DataFrame(righe))
    st.write("history", pd.DataFrame(_history({t: 40 for t in SQUADRE})))
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_stagione()
    testo = _testo((out / "stagione.html").read_text(encoding="utf-8"))
    st.close()
    # la convenzione è dichiarata dove il lettore la incontra
    assert "«<1»" in testo and "«>99»" in testo and "lo zero vero resta «0»" in testo
    assert "gli stessi numeri che la scheda partita pubblica" in testo
    # e applicata alle colonne, cella per cella (l'intestazione del titolo è «1°», non
    # «titolo»: il confronto si fa sulla cella, non sul testo della pagina)
    html = (out / "stagione.html").read_text(encoding="utf-8")

    def celle(squadra: str) -> list[str]:
        riga = re.search(rf"<tr><td>{squadra}.*?</tr>", html, re.DOTALL).group(0)
        return [html_mod.unescape(x).strip()
                for x in re.findall(r'<td class="r">(.*?)</td>', riga, re.DOTALL)]

    inter = celle("Inter")      # PG, Pt, Pt attesi, Media pos., 1°, UCL (prime 4), Retro
    assert inter[4] == "<1%" and inter[5] == ">99%" and inter[-1] == "0%"   # 0,4% · 99,99% · 0
    juventus = celle("Juventus")
    assert juventus[4] == "1%" and juventus[5] == "<1%" and juventus[-1] == ">99%"


def test_ucl_con_un_posto_solo_e_concordato(tmp_path):
    """POR1 ha un solo posto UCL: «UCL (1ª)» e «nella 1ª posizione», mai «prime 1» (docs/102).

    Misurato il 13/10/2026 sulla pagina pubblicata: l'intestazione della colonna e la nota
    sotto la tabella stampavano «UCL (prime 1)» e «chiudere nelle prime 1 posizioni» — la
    stessa classe di difetto del guasto del `daily` («1 campionati», `docs/99`).
    """
    st = Store(tmp_path / "processed")
    righe = [dict(_sim_row(t, i), league_key="POR1", top_n=1, p_top_n=0.9 - 0.2 * i)
             for i, t in enumerate(SQUADRE)]
    st.write("season_sim", pd.DataFrame(righe))
    st.write("history", pd.DataFrame(_history({t: 40 for t in SQUADRE})))
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_stagione()
    html = (out / "stagione.html").read_text(encoding="utf-8")
    st.close()
    testo = _testo(html)
    assert "UCL (1ª)" in testo
    assert "nella 1ª posizione con accesso ordinario" in testo
    assert "prime 1" not in testo
    # e il gate di concordanza del sito non trova nulla da ridire su questa variante
    from scripts.verify_site import AGREEMENT

    trovato = AGREEMENT.search(testo)
    assert trovato is None, f"concordanza sfuggita: {trovato.group(0)!r}"
