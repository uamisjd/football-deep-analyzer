"""Accuratezza: copertura del campione e anticipo delle previsioni (docs/44 §3 e §4).

Due affermazioni della pagina erano, in due modi diversi, non sostenute dai dati:

1. la tabella diceva «120 gare valutate» senza dire **su quante** gare finite: sono
   120 su 331 (36%), e le escluse hanno un motivo (202 precedenti al primo run,
   9 senza una previsione salvata prima del fischio d'inizio);
2. «RPS per anticipo» prometteva «se la qualità peggiora con l'anticipo, lo vedremo
   qui», ma la chiave ``(match_id, model)`` è unica e la previsione viene **rifatta a
   ogni run**: quella valutata è sempre l'ultima (≈2 ore prima), quindi i bucket oltre
   le 24 ore non possono riempirsi.

I test costruiscono la pagina da uno store minimo e leggono l'HTML, come fa il lettore.
"""

from __future__ import annotations

import re

import pandas as pd

from fda.models.predict import MODEL_VERSION
from fda.site.build import SiteBuilder
from fda.store import Store

LEGA = "ITA1"      # Serie A: id FotMob 55, presente nella configurazione
LID = 55


def _pred(match_id: int, kickoff: str, made: str, ph=0.5, pd_=0.28, pa=0.22) -> dict:
    """Riga di `predictions` con le colonne che `build_accuracy` legge davvero."""
    return {"match_id": match_id, "league_key": LEGA, "utc_kickoff": kickoff,
            "home": f"Casa{match_id}", "away": f"Ospite{match_id}", "model": "ensemble",
            "model_version": MODEL_VERSION, "calibration_version": "cal-test-1.0",
            "made_at": made, "p_home": ph, "p_draw": pd_, "p_away": pa,
            "lambda_home": 1.5, "lambda_away": 1.1, "p_over15": 0.8, "p_over25": 0.55,
            "p_over35": 0.3, "p_btts": 0.55, "p_1x": 0.78, "p_12": 0.72, "p_x2": 0.5,
            "p_home_clean_sheet": 0.27, "p_away_clean_sheet": 0.24}


def _fx(match_id: int, kickoff: str, hg: int, ag: int) -> dict:
    return {"match_id": match_id, "league_id": LID, "season": "2026/2027", "round": 1,
            "utc_kickoff": kickoff, "home_id": 1, "home_name": "Casa", "away_id": 2,
            "away_name": "Ospite", "home_goals": hg, "away_goals": ag,
            "status": "finished", "source": "fotmob"}


def _store(tmp_path, preds, fx) -> Store:
    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame(fx))
    st.write("predictions", pd.DataFrame(preds))
    st.write("history", pd.DataFrame([]))      # senza storico: base naive «fisso»
    return st


def _build(tmp_path, preds, fx) -> str:
    st = _store(tmp_path, preds, fx)
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build_accuracy(st.read("fixtures"))
    html = (out / "accuratezza.html").read_text(encoding="utf-8")
    st.close()
    return html


def _paragrafo_copertura(html: str) -> str:
    m = re.search(r"Copertura:(.*?)</p>", html, re.DOTALL)
    assert m, "la pagina deve dire su quante gare finite è calcolata"
    return re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", m.group(1))).strip()


def test_copertura_del_campione_dichiarata(tmp_path):
    """4 gare finite: 2 valutate, 1 precedente al primo run, 1 prevista dopo il fischio."""
    preds = [
        # la prima previsione in assoluto: fissa l'inizio del modello prima di tutti i kickoff
        _pred(1, "2026-09-10 18:00:00+00:00", "2026-09-01 08:00:00+00:00"),
        _pred(1, "2026-09-10 18:00:00+00:00", "2026-09-10 16:00:00+00:00"),   # 2h prima → valutata
        _pred(2, "2026-09-10 20:00:00+00:00", "2026-09-10 19:00:00+00:00"),   # 1h prima → valutata
        _pred(4, "2026-09-08 12:00:00+00:00", "2026-09-09 09:00:00+00:00"),   # dopo il fischio → esclusa
    ]
    fx = [
        _fx(1, "2026-09-10 18:00:00+00:00", 2, 1),
        _fx(2, "2026-09-10 20:00:00+00:00", 1, 1),
        _fx(3, "2026-08-20 18:00:00+00:00", 0, 3),      # prima del primo run → esclusa
        _fx(4, "2026-09-08 12:00:00+00:00", 1, 0),
    ]
    par = _paragrafo_copertura(_build(tmp_path, preds, fx))
    assert "2 gare valutate su 4 finite in stagione" in par
    assert "1 gara è precedente alla prima previsione registrata (01/09/2026 10:00)" in par
    assert "1 gara non aveva una previsione salvata prima del calcio d'inizio" in par
    assert "Nessuna di quelle escluse entra nei numeri qui sopra" in par


def test_anticipo_dichiarato_e_bucket_spiegati(tmp_path):
    """L'anticipo medio è pubblicato e la pagina dice perché i bucket oltre il primo restano vuoti."""
    preds = [_pred(i, f"2026-09-1{i} 18:00:00+00:00", f"2026-09-1{i} 16:00:00+00:00")
             for i in (1, 2, 3)]
    fx = [_fx(i, f"2026-09-1{i} 18:00:00+00:00", 2, 1) for i in (1, 2, 3)]
    html = _build(tmp_path, preds, fx)
    assert "RPS per anticipo" in html
    assert "<b>0,1 giorni</b>" in html                     # 2 ore = 0,083 giorni → 0,1
    assert "rifatta a ogni run" in html                    # il motivo, non solo il numero
    assert "non</b> si può leggere se la qualità peggiora con l'anticipo" in html


def test_colonna_modello_corrente_pubblicata(tmp_path):
    """Accanto alle gare valutate, quante sono state previste dalla ricetta di oggi."""
    preds = [
        _pred(1, "2026-09-10 18:00:00+00:00", "2026-09-10 16:00:00+00:00"),
        _pred(2, "2026-09-10 20:00:00+00:00", "2026-09-10 19:00:00+00:00"),
        # una gara valutata con una versione precedente: resta in archivio, non è «corrente»
        _pred(3, "2026-09-11 20:00:00+00:00", "2026-09-11 19:00:00+00:00"),
    ]
    preds[2]["model_version"] = "dc-elo-ens-0.1"
    fx = [_fx(i, f"2026-09-1{i if i < 3 else 1} 18:00:00+00:00", 2, 1) for i in (1, 2, 3)]
    fx[2] = _fx(3, "2026-09-11 20:00:00+00:00", 1, 1)
    html = _build(tmp_path, preds, fx)
    assert "di cui col modello corrente" in html
    # 3 gare valutate, di cui 2 con la ricetta corrente: la riga «Tutti» lo dice
    assert re.search(r">Tutti<.*?>3<.*?>2<", html, re.DOTALL) or "3</td>\n        <td class=\"r\">2" in html
    assert "La colonna «di cui col modello corrente»" in html
    # la composizione del campione resta la stessa fonte: 2 = le gare «correnti»
    assert "di cui\n  <b>2</b> con il modello corrente" in html


def test_grafico_mercati_pubblicato(tmp_path):
    """Il confronto previsto/osservato per mercato è disegnato con gli stessi numeri."""
    preds = [_pred(i, f"2026-09-1{i} 18:00:00+00:00", f"2026-09-1{i} 16:00:00+00:00") for i in range(1, 7)]
    fx = [_fx(i, f"2026-09-1{i} 18:00:00+00:00", 2, 1) for i in range(1, 7)]
    html = _build(tmp_path, preds, fx)
    assert "<figure class=\"grafico\">" in html
    assert 'role="img"' in html and "intervallo 95% della frequenza osservata" in html
    # un punto per mercato (9) dentro la figura — il logo e le icone stanno fuori
    figura = re.search(r'<figure class="grafico">.*?</figure>', html, re.DOTALL).group(0)
    assert figura.count("<circle") == 9
    assert "Punto verde = dentro l'intervallo, punto rosso = fuori." in html
