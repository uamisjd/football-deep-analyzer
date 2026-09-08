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
