"""Test del gate di parità delle schede pre-partita (scripts/parita_schede.py).

Il caso centrale è lo stato vuoto legittimo: durante una sosta dei campionati la
build produce correttamente zero schede pre-partita e il gate non deve fermare il
run (misurato il 2026-09-21: ultime gare il 20/09, ripresa il 09/10, gate rosso con
«nessuna scheda pre-partita»). Lo zero resta un errore quando le gare in finestra
ci sono (build che perde pagine) o quando manca proprio la build.
"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROMA = ZoneInfo("Europe/Rome")


def _load():
    p = Path(__file__).parent.parent / "scripts" / "parita_schede.py"
    spec = importlib.util.spec_from_file_location("parita_schede", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _load()

POST = """<html><body><h2>Lettura della partita</h2><p>Finita 2-0, xG 1,8 contro 0,6:
una gara a senso unico decisa nel primo tempo con due gol di scarto pieno.</p></body></html>"""

PRE = """<html><body><h2>Analisi pre-partita</h2>
<nav class="match-jump"><a href="#analisi">Analisi</a></nav>
<div id="analisi"><h2>Analisi</h2><p>Testo della scheda pre-partita, lungo abbastanza
da superare la soglia minima di ottanta caratteri che il censimento richiede.</p></div>
</body></html>"""


def _site(tmp_path, pages):
    site = tmp_path / "site"
    (site / "partite").mkdir(parents=True)
    for name, html in pages.items():
        (site / "partite" / name).write_text(html, encoding="utf-8")
    return site


def _data(tmp_path, rows):
    data = tmp_path / "data"
    data.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(data / "fixtures.parquet", index=False)
    return data


def _fx(mid, when, status):
    return {"match_id": mid, "utc_kickoff": when, "status": status,
            "home_name": "A", "away_name": "B"}


def test_sosta_zero_schede_e_zero_gare_esce_zero(tmp_path, capsys):
    """Sosta dei campionati: 0 schede e 0 gare in finestra → gate non applicabile."""
    now = datetime.now(ROMA)
    site = _site(tmp_path, {"1.html": POST})
    data = _data(tmp_path, [
        _fx(1, now - timedelta(days=1), "finished"),
        _fx(2, now + timedelta(days=30), "scheduled"),
    ])
    assert ps.main([str(site), "--data", str(data)]) == 0
    assert "sosta dei campionati" in capsys.readouterr().out


def test_zero_schede_con_gare_in_finestra_esce_uno(tmp_path, capsys):
    """Gare in finestra ma 0 schede: la build le ha perse → errore."""
    now = datetime.now(ROMA)
    mezzogiorno = now.replace(hour=12, minute=0, second=0, microsecond=0)
    site = _site(tmp_path, {"1.html": POST})
    data = _data(tmp_path, [
        _fx(1, now - timedelta(days=1), "finished"),
        _fx(2, mezzogiorno + timedelta(days=1), "scheduled"),
    ])
    assert ps.main([str(site), "--data", str(data)]) == 1
    assert "la build le ha perse" in capsys.readouterr().out


def test_senza_build_esce_uno(tmp_path, capsys):
    """Senza cartella partite: build mancante, non sosta."""
    site = tmp_path / "site"
    site.mkdir()
    data = _data(tmp_path, [_fx(1, datetime.now(ROMA), "finished")])
    assert ps.main([str(site), "--data", str(data)]) == 1
    assert "serve una build" in capsys.readouterr().out


def test_fixtures_illeggibile_con_zero_schede_esce_uno(tmp_path, capsys):
    """Senza fixtures non si può distinguere una sosta da una build persa: errore."""
    site = _site(tmp_path, {"1.html": POST})
    data = tmp_path / "data"
    data.mkdir()
    assert ps.main([str(site), "--data", str(data)]) == 1
    assert "impossibile distinguere" in capsys.readouterr().out


def test_due_schede_identitche_restano_verdi(tmp_path):
    """Percorso normale: due schede pari → exit 0 (nessuna regressione del gate)."""
    site = _site(tmp_path, {"1.html": PRE, "2.html": PRE})
    data = _data(tmp_path, [_fx(1, datetime.now(ROMA), "finished")])
    assert ps.main([str(site), "--data", str(data)]) == 0
