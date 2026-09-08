from datetime import datetime, timedelta, timezone

from fda.site.audit import audit_match


def _ctx(days, **values):
    c = {"match_id": 1, "utc_kickoff": datetime.now(timezone.utc) + timedelta(days=days)}
    c.update(values)
    return c


def test_audit_distinguishes_not_yet_published_from_real_missing():
    early = audit_match(_ctx(5))
    assert early["mancante"] == 0
    assert early["atteso"] > 0

    late = audit_match(_ctx(1))
    assert late["mancante"] > 0
    assert late["atteso"] < early["atteso"]


def test_audit_does_not_treat_empty_collections_as_present():
    result = audit_match(_ctx(0.5, home_starters=[], away_starters=[{"name": "Player"}]))
    states = {item["key"]: item["state"] for item in result["items"]}
    assert states["home_starters"] == "mancante"
    assert states["away_starters"] == "presente"
