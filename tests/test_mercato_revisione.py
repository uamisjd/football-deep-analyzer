"""Regressioni della card Mercato: contabilità, intera finestra e tipo di distinta (docs/95)."""

from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

from fda.site.analysis import MatchAnalysis
from fda.site.build import SiteBuilder
from fda.site.mercato_checks import audit_market
from fda.store import Store
from tests.test_mercato import _transfers

NOW = pd.Timestamp("2026-10-12T12:00:00Z")


def seeded(tmp_path, *, origin="predicted", fees=None):
    st = Store(tmp_path / "data")
    fees = fees if fees is not None else [str(i * 1000000) for i in range(8, 0, -1)]
    st.write("transfers", _transfers([
        {"player_name": f"Nuovo {i}", "fee_text": fee, "date": (NOW - pd.Timedelta(days=2)).isoformat()}
        for i, fee in enumerate(fees)
    ]))
    st.write("fixtures", pd.DataFrame([{"match_id": 1, "league_id": 55, "season": "2026", "round": "8",
              "utc_kickoff": NOW + pd.Timedelta(days=1), "home_id": 1, "home_name": "Roma", "away_id": 2,
              "away_name": "Inter", "home_goals": None, "away_goals": None, "status": "scheduled"}]))
    st.write("lineup", pd.DataFrame([{"match_id": 1, "team_id": 1, "player_id": 100 + i,
              "player_name": f"Nuovo {i}", "role": "starter" if i % 2 else "sub", "market_value_eur": 100 - i}
              for i in range(len(fees))]))
    if origin is not None:
        st.write("match_info", pd.DataFrame([{"match_id": 1, "lineup_type": origin}]))
    return st


def render(tmp_path, st):
    ma = MatchAnalysis(st)
    mk = ma.transfer_window(1, 1, now=NOW)
    context = {"home_market": mk, "away_market": None, "home_name": "Roma", "away_name": "Inter", "status": "scheduled"}
    template = (Path(__file__).parents[1] / "src/fda/site/templates/match.html").read_text()
    start = template.index("  {% if (c.home_market or c.away_market) and c.status != 'finished' %}\n")
    end = template.index("  {% if (c.home_news", start)
    builder = SiteBuilder(store=st, out_dir=tmp_path / "site")
    text = builder.env.from_string(template[start:end]).render(c=context)
    directory = tmp_path / "html/partite"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "1.html"
    path.write_text("<h1>Analisi pre-partita</h1>" + text + "<footer></footer>")
    return path, mk


@pytest.mark.parametrize("limit", [1, 4])
def test_il_limite_grafico_non_taglia_gli_arrivi_in_distinta(tmp_path, limit):
    st = seeded(tmp_path)
    mk = MatchAnalysis(st).transfer_window(1, 1, n=limit, now=NOW)
    assert len(mk["arrivals"]) == limit and mk["n_in"] == 8
    assert len(mk["in_campo"]) == 8


@pytest.mark.parametrize("raw,origin,phrase", [
    ("confirmed", "official", "distinta ufficiale"),
    ("predicted", "predicted", "formazione prevista"),
    ("lastStarting11", "previous", "ultima distinta disponibile"),
    (None, "unknown", "tipo non dichiarato"),
])
def test_provenienza_della_distinta_non_diventa_impiego_certo(tmp_path, raw, origin, phrase):
    st = seeded(tmp_path, origin=raw)
    path, mk = render(tmp_path, st)
    html = path.read_text()
    assert mk["lineup_origin"] == origin and phrase in html
    assert "Già in campo" not in html
    assert "Arrivi riconosciuti:</b> 8" in html
    assert "Altri 4 arrivi riconosciuti" in html
    for i in range(8):
        assert f"Nuovo {i}" in html
    if origin == "previous":
        assert "Non è la distinta di questa gara" in html
    if origin == "predicted":
        assert "Non sono presenze confermate" in html
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] == 0


def test_importi_formule_e_mancanti_formano_una_partizione(tmp_path):
    st = seeded(tmp_path, fees=["1000000", "gratuito", "prestito", "undisclosed"])
    mk = MatchAnalysis(st).transfer_window(1, 1, now=NOW)
    assert [mk[k] for k in ("importi_noti", "gratuiti", "prestiti_senza_importo", "importi_mancanti")] == [1, 1, 1, 1]
    assert mk["spesa"] == 1000000 and mk["incasso"] == 0
    assert mk["saldo"] == 1000000
    path, _ = render(tmp_path, st)
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] == 0


def test_saldo_nullo_e_zero_contabile_non_sono_importi_ignoti(tmp_path):
    st = seeded(tmp_path, fees=["1000000"])
    tr = st.read("transfers")
    outgoing = tr.iloc[[0]].assign(direction="out", player_name="Ceduto")
    st.write("transfers", pd.concat([tr, outgoing], ignore_index=True))
    path, mk = render(tmp_path, st)
    assert mk["saldo"] == 0 and mk["saldo_it"] == "0 €" and mk["saldo_segno"] == ""
    assert "saldo 0 €" in path.read_text()
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] == 0


@pytest.mark.parametrize("fees,expected", [
    (["gratuito", "gratuito"], 0.0), (["prestito"], None),
    (["gratuito", "undisclosed"], None), (["undisclosed"], None),
])
def test_zero_solo_se_sostenuto_da_gratuiti_o_assenza_movimenti(tmp_path, fees, expected):
    st = seeded(tmp_path, fees=fees)
    path, mk = render(tmp_path, st)
    assert mk["spesa"] == expected
    assert mk["saldo"] == expected
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] == 0
    if expected is None:
        assert "saldo non quantificabile" in path.read_text()


def test_un_lato_ignoto_non_diventa_zero_per_calcolare_il_saldo(tmp_path):
    st = seeded(tmp_path, fees=["undisclosed"])
    tr = st.read("transfers")
    outgoing = tr.iloc[[0]].assign(direction="out", fee_text="13000000", player_name="Ceduto")
    st.write("transfers", pd.concat([tr, outgoing], ignore_index=True))
    path, mk = render(tmp_path, st)
    assert mk["spesa"] is None and mk["incasso"] == 13000000 and mk["saldo"] is None
    assert "saldo non quantificabile" in path.read_text()
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] == 0


def test_prestito_con_corrispettivo_non_perde_tipo_ne_importo(tmp_path):
    st = seeded(tmp_path, fees=["1000000"])
    st.write("transfers", st.read("transfers").assign(transfer_type="on loan"))
    path, mk = render(tmp_path, st)
    assert mk["arrivals"][0]["is_loan"] is True
    assert mk["spesa"] == 1000000 and mk["importi_noti"] == 1
    assert '<span class="mut">prestito</span><br>1 M€' in path.read_text()


def test_cutoff_prima_del_kickoff_precede_la_deduplica(tmp_path):
    st = seeded(tmp_path, fees=["1000000"])
    kickoff = NOW - pd.Timedelta(hours=2)
    st.write("fixtures", st.read("fixtures").assign(utc_kickoff=kickoff))
    tr = st.read("transfers")
    tr["date"] = (kickoff - pd.Timedelta(minutes=30)).isoformat()
    future = tr.copy().assign(date=(kickoff + pd.Timedelta(minutes=30)).isoformat(), fee_text="9000000")
    st.write("transfers", pd.concat([tr, future], ignore_index=True))
    mk = MatchAnalysis(st).transfer_window(1, 1, now=NOW)
    assert mk["n_in"] == 1 and mk["spesa"] == 1000000


def test_annuncio_futuro_non_diventa_finestra_corrente(tmp_path):
    st = seeded(tmp_path, fees=["1000000"])
    st.write("transfers", st.read("transfers").assign(date=(NOW + pd.Timedelta(hours=1)).isoformat()))
    assert MatchAnalysis(st).transfer_window(1, 1, now=NOW) is None


def test_due_movimenti_non_raddoppiano_la_persona_nella_distinta(tmp_path):
    st = seeded(tmp_path, fees=["1000000"])
    ma = MatchAnalysis(st)
    player = {"name": "Nuovo 0"}
    assert len(ma.arrivals_on_pitch(1, 1, [player, player])) == 1


@pytest.mark.parametrize("defect", ["count", "origin", "name", "money", "coverage"])
def test_oracolo_rifiuta_le_mutazioni_senza_chiamare_il_generatore(tmp_path, monkeypatch, defect):
    st = seeded(tmp_path)
    path, _ = render(tmp_path, st)
    html = path.read_text()
    if defect == "count":
        html = html.replace("Arrivi riconosciuti:</b> 8", "Arrivi riconosciuti:</b> 4")
    elif defect == "origin":
        html = html.replace("formazione prevista", "distinta ufficiale")
    elif defect == "name":
        html = html.replace("Nuovo 7", "Un nome sbagliato")
    elif defect == "money":
        html = html.replace("spesa 36 M€", "spesa 999 M€")
    elif defect == "coverage":
        html = html.replace("Importi numerici: 8", "Importi numerici: 7")
    assert html != path.read_text()
    path.write_text(html)
    monkeypatch.setattr(MatchAnalysis, "transfer_window", lambda *a, **k: pytest.fail("oracolo accoppiato al generatore"))
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] > 0


def test_due_mosse_distinte_oltre_trenta_giorni_non_sono_un_duplicato(tmp_path):
    st = seeded(tmp_path, fees=["1000000"])
    st.write("transfers", _transfers([
        {"player_name": "Nuovo 0", "counterpart": "Club A", "fee_text": "1000000",
         "date": (NOW - pd.Timedelta(days=31, hours=1)).isoformat()},
        {"player_name": "Ponte", "counterpart": "Club B", "fee_text": "1000000",
         "date": (NOW - pd.Timedelta(days=15)).isoformat()},
        {"player_name": "Nuovo 0", "counterpart": "Club C", "fee_text": "2000000",
         "date": (NOW - pd.Timedelta(days=1)).isoformat()},
    ]))
    path, mk = render(tmp_path, st)
    assert mk["n_in"] == 3 and len(mk["in_campo"]) == 1
    assert audit_market(path.parents[1], st.base_dir, now=NOW)["defects"] == 0


def test_tutti_i_nomi_restano_consultabili_ma_solo_quattro_in_apertura(tmp_path):
    st = seeded(tmp_path)
    path, _ = render(tmp_path, st)
    roster = BeautifulSoup(path.read_text(), "html.parser").select_one(".market-roster")
    assert roster.details is not None
    assert len(roster.select("details")) == 1
    hidden = roster.details.get_text()
    assert "Nuovo 7" in hidden and "Nuovo 0" not in hidden
