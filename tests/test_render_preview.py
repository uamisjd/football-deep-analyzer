"""Smoke test di scripts/render_preview.py: i PNG di anteprima si generano davvero.

Non giudica l'estetica (quella si controlla a occhio su docs/preview/): verifica che lo
script giri in un ambiente pulito (Pillow dichiarata tra le dev-extras dal P2-8b) e
produca i due file alle dimensioni attese.
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]


def test_render_preview_genera_i_png(tmp_path):
    out = subprocess.run([sys.executable, str(REPO / "scripts" / "render_preview.py"),
                          "--out", str(tmp_path)],
                         capture_output=True, text=True, timeout=120, check=False)
    assert out.returncode == 0, out.stderr[-800:]
    for name, size in (("header-preview.png", (1200, 168)), ("home-preview.png", None)):
        f = tmp_path / name
        assert f.exists(), f"manca {name}"
        with Image.open(f) as img:
            assert img.size[0] == size[0] if size else img.size[0] == 1200
            assert img.size[1] > 900 if name == "home-preview.png" else img.size[1] == 168
