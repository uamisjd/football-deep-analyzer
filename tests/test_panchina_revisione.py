"""Regressioni docs/94: rango ≠ punti, salvezza ≠ spareggio, precisione MC e audit."""

import json
from pathlib import Path

import pandas as pd
import pytest

from fda.site.analysis import MatchAnalysis
from fda.site.build import SiteBuilder
from fda.site.panchina_checks import monte_carlo_findings, safety_findings
from fda.store import Store
from scripts.audit_panchina import main as audit_panchina
from tests.test_panchina_notizie import FX, KO, LINEUP, SIM, STANDINGS


def table(n, league):
    return pd.DataFrame({
        "league_code": [league] * n, "team_id": range(1, n + 1),
        "team_name": [f"Squadra {i}" for i in range(1, n + 1)], "rank": range(1, n + 1),
        "points": [2 * (n - i) for i in range(1, n + 1)],
        "goal_diff": [n + 1 - 2 * i for i in range(1, n + 1)],
    })


def bench(tmp_path, standings, rank):
    store = Store(tmp_path / "data")
    store.write("fotmob_standings", standings)
    return MatchAnalysis(store).bench_deep(rank, f"Squadra {rank}", 1, "Squadra 1", KO("2026-10-20"))


@pytest.mark.parametrize("league,n,rank", [
    ("ITA1", 20, 18), ("ENG1", 20, 19), ("ESP1", 20, 20),
    ("GER1", 18, 17), ("FRA1", 18, 18),
])
def test_pari_punti_non_promuove_in_zona_salvezza(tmp_path, league, n, rank):
    standings = table(n, league)
    safe = n - 3
    standings.loc[standings["rank"].ge(safe), "points"] = 6
    b = bench(tmp_path, standings, rank)
    assert f"a pari punti con il {safe}º posto (salvezza diretta)" in b["table_line"]
    assert "in zona salvezza diretta" not in b["table_line"]
    assert safety_findings(b["table_line"], standings, rank) == []


@pytest.mark.parametrize("league", ["GER1", "FRA1", "NED1", "POR1"])
@pytest.mark.parametrize("rank", [17, 18])
def test_distanza_dalla_salvezza_non_dallo_spareggio(tmp_path, league, rank):
    standings = table(18, league)
    b = bench(tmp_path, standings, rank)
    # 15º = 6 punti; 16º = 4 (spareggio); 17º = 2; 18º = 0.
    distance = 6 - int(standings.loc[standings["rank"].eq(rank), "points"].iloc[0])
    assert f"{distance} punti dalla salvezza diretta" in b["table_line"]
    assert safety_findings(b["table_line"], standings, rank) == []


def test_classifica_non_monotona_non_inventa_la_salvezza(tmp_path):
    standings = table(20, "ITA1")
    standings.loc[standings["rank"].eq(18), "points"] = 20
    b = bench(tmp_path, standings, 18)
    assert "in zona retrocessione diretta" in b["table_line"]
    assert "in zona salvezza diretta" not in b["table_line"]
    assert "a pari punti" not in b["table_line"]


def test_oracolo_semantico_non_si_fida_del_generatore(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("il verificatore non deve chiamare bench_deep")

    monkeypatch.setattr(MatchAnalysis, "bench_deep", forbidden)
    standings = table(20, "ITA1")
    standings.loc[standings["rank"].ge(17), "points"] = 6
    assert safety_findings("19º con 6 punti · in zona salvezza diretta", standings, 19)
    assert not safety_findings("17º con 6 punti · in zona salvezza diretta", standings, 17)
    assert safety_findings("17º con 2 punti · 2 punti dalla salvezza diretta", table(18, "NED1"), 17)


@pytest.mark.parametrize("n,number,se", [
    (10000, "10.000", "0,5"), (1000, "1.000", "1,6"),
    (9000, "9.000", "0,6"), (100, "100", "5,0"),
])
def test_precisione_mc_dai_metadati_e_mai_per_difetto(tmp_path, n, number, se):
    store = Store(tmp_path / "data")
    store.write("season_sim", SIM.assign(n_sims=n))
    stakes = MatchAnalysis(store).stakes("Inter")
    line = stakes["mc_precision_line"]
    assert f"{number} simulazioni Monte Carlo" in line
    assert f"errore standard fino a {se} punti percentuali" in line
    assert monte_carlo_findings(line, n) == []


@pytest.mark.parametrize("n", [None, 0, -100, float("nan"), 1.5])
def test_numerosita_non_valida_non_diventa_dieci_mila(tmp_path, n):
    store = Store(tmp_path / "data")
    store.write("season_sim", SIM.assign(n_sims=n))
    line = MatchAnalysis(store).stakes("Inter")["mc_precision_line"]
    assert "numerosità non dichiarata" in line
    assert "10.000" not in line and "0,5" not in line
    assert monte_carlo_findings(line, n) == []


def test_oracolo_precisione_rifiuta_campione_e_se_fittizi():
    old = "10.000 simulazioni Monte Carlo del resto del campionato: errore standard fino a 0,5 punti percentuali"
    assert monte_carlo_findings(old, 1000)
    too_precise = old.replace("10.000", "9.000")
    assert monte_carlo_findings(too_precise, 9000)   # massimo 0,527… pp, non 0,5
    assert monte_carlo_findings(old, None)


def render_card(tmp_path, n_sims=10000):
    """Il vero frammento Jinja, con dati offline completi per l'audit indipendente."""
    store = Store(tmp_path / "data")
    for name, df in (("fixtures", FX), ("lineup", LINEUP), ("fotmob_standings", STANDINGS),
                     ("season_sim", SIM.assign(n_sims=n_sims))):
        store.write(name, df)
    store.write("match_info", pd.DataFrame([{
        "match_id": 4, "home_avg_starter_age": None, "away_avg_starter_age": None,
    }]))
    ma = MatchAnalysis(store)
    context = {
        "home_name": "Inter", "away_name": "Roma", "home_starters": [], "away_starters": [],
        "cond_stakes": None,
        "home_bench": ma.bench_deep(2, "Inter", 1, "Roma", KO("2026-09-13 18:00")),
        "away_bench": ma.bench_deep(1, "Roma", 2, "Inter", KO("2026-09-13 18:00")),
    }
    builder = SiteBuilder(store=store, out_dir=tmp_path / "site")
    template = (Path(__file__).parents[1] / "src/fda/site/templates/match.html").read_text()
    start = template.index("  {% if c.home_bench or c.away_bench %}\n")
    end = template.index("  {#- P2.2", start)
    html = builder.env.from_string(template[start:end]).render(c=context, root="../")
    directory = tmp_path / "cards"
    directory.mkdir()
    path = directory / "4.html"
    path.write_text("<h1>Analisi pre-partita</h1>" + html + "<footer></footer>")
    return path, store


def test_template_non_promette_precisione_di_un_altro_campione(tmp_path):
    path, _ = render_card(tmp_path, n_sims=1000)
    html = path.read_text()
    assert "1.000 simulazioni Monte Carlo" in html
    assert "errore standard fino a 1,6 punti percentuali" in html
    assert "10.000 simulazioni" not in html
    assert "0,5 punti" not in html
    assert "non includono l’incertezza del modello" in html


def test_limiti_della_permanenza_e_degli_spareggi_dichiarati(tmp_path):
    path, _ = render_card(tmp_path)
    text = path.read_text()
    assert "incluse quelle di gare ancora in programma" in text
    assert "di campionato della stagione in corso" in text
    assert "prima posizione del gruppo" in text
    assert "15ª nei campionati a 18" in text
    assert "GER1" in text


def test_audit_blocca_errori_invece_di_uscire_verde(tmp_path):
    path, store = render_card(tmp_path)
    report_path = tmp_path / "audit.json"
    args = ["--site", str(path.parent), "--data", str(store.base_dir), "--json", str(report_path)]
    assert audit_panchina(args) == 0
    html = path.read_text()
    assert "1,0 punti/gara su 1 gara finita" in html
    path.write_text(html.replace("1,0 punti/gara su 1 gara finita", "99,9 punti/gara su 999 gare finite", 1))
    assert audit_panchina(args) == 1
    report = json.loads(report_path.read_text())
    assert len(report["errors"]["ppg"]) == 1 and report["defects"] >= 1


def test_audit_senza_schede_non_dichiara_una_verifica(tmp_path):
    path, store = render_card(tmp_path)
    path.unlink()
    assert audit_panchina(["--site", str(path.parent), "--data", str(store.base_dir)]) == 1
