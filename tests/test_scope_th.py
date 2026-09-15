"""Ogni <th> delle template deve dichiarare scope (docs/21 P2-8): controllo offline
immediato, prima ancora del build; verify_site [27] fa lo stesso sulle pagine generate."""

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "fda" / "site" / "templates"
TH = re.compile(r"<th(?=[ >])[^>]*>")


@pytest.mark.parametrize("tpl", sorted(TEMPLATES.glob("*.html")), ids=lambda p: p.name)
def test_ogni_th_ha_scope(tpl: Path) -> None:
    senza = [m.group(0) for m in TH.finditer(tpl.read_text(encoding="utf-8"))
             if "scope=" not in m.group(0)]
    assert not senza, f"{tpl.name}: <th> senza scope → {senza[:3]}"
