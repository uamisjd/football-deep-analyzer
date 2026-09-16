from fda.config import league, leagues, season, season_start_year, source


def test_seven_leagues_configured():
    lgs = leagues()
    assert [lg.key for lg in lgs] == ["ITA1", "ENG1", "ESP1", "GER1", "FRA1", "NED1", "POR1"]
    assert all(lg.fotmob_id > 0 for lg in lgs)
    assert all(lg.espn_code.endswith(".1") for lg in lgs)


def test_understat_coverage():
    assert league("ITA1").has_understat
    assert not league("NED1").has_understat
    assert not league("POR1").has_understat


def test_datahub_mirror_coverage():
    # NED1/POR1 non sono nel mirror datasets/football-datasets: puntano a un mirror dedicato.
    assert league("ITA1").datahub_dir == "serie-a" and league("ITA1").datahub_base is None
    assert league("NED1").datahub_dir == "eredivisie"
    assert league("POR1").datahub_dir == "primeira-liga"
    assert league("NED1").datahub_base.startswith("https://raw.githubusercontent.com/")
    assert league("POR1").datahub_base == league("NED1").datahub_base


def test_season():
    assert season() == "2026/2027"
    assert season_start_year() == 2026


def test_sources_have_rate_limits():
    for name in ("fotmob", "espn", "understat"):
        assert source(name)["rate_limit_s"] > 0


def test_detail_window_days_single_source():
    """P1.5 (docs/19 §2.4): il «7 giorni» ha una sola fonte — collect, CLI, build e testi.

    Un run manuale con default diversi pubblicava un elenco «Prossime» che prometteva più
    schede di quante ne esistano. Il criterio dell'audit: zero «7» letterali residui.
    """
    import inspect
    import re
    from pathlib import Path
    from typing import Any

    from fda import config
    from fda.collect import collect_league
    from fda.cli import collect_cmd

    w = config.DETAIL_WINDOW_DAYS
    assert w == 7  # il valore atteso oggi; la costante è l'unica cosa da cambiare
    assert inspect.signature(collect_league).parameters["future_days"].default == w

    def _opt_default(fn: Any) -> Any:
        d = inspect.signature(fn).parameters["future_days"].default
        return d.default if hasattr(d, "default") else d  # typer avvolge in OptionInfo

    assert _opt_default(collect_cmd) == w
    # nessun letterale residuo nei sorgenti per la finestra FUTURA (criterio del §2.4);
    # la finestra passata dei risultati (`- timedelta(days=7)`) è un concetto distinto
    banned = re.compile(r"\+ timedelta\(days=7\)|future_days[=:] ?7|calendar_days=7|prossimi 7")
    hits = [str(p) for p in Path("src").rglob("*.py")
            if banned.search(p.read_text(encoding="utf-8"))]
    hits += [str(p) for p in Path("src/fda/site/templates").rglob("*.html")
             if banned.search(p.read_text(encoding="utf-8"))]
    assert hits == [], f"finestra «7 giorni» duplicata in: {hits}"
