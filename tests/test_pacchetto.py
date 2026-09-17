"""Ordine del pacchetto e degli artefatti derivati (revisione del 2026-09-17, docs/26).

Tre difetti veri trovati guardando il progetto come lo vede chi lo installa o lo clona,
non come lo vede chi lo sviluppa in editable:

1. la CSS del sito non entrava nella wheel → ``pip install .`` produceva un pacchetto
   con cui ``fda build`` cade (``_write_assets`` legge ``assets/site.css`` dal pacchetto);
2. ``scripts/anteprima_scheda.py`` scriveva l'anteprima dentro ``site/``, la directory che
   il workflow ``daily`` pubblica su GitHub Pages: interrotto a metà lasciava il sito a
   poche centinaia di pagine su 4.100 (successo durante questa revisione);
3. ``data/processed/fda.duckdb`` era versionato benché ``store.py`` lo dichiari derivato:
   un binario riscritto a ogni run (5 al giorno) nella history senza informazione.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE_PKG = REPO / "src" / "fda" / "site"


def _package_data() -> dict[str, list[str]]:
    with (REPO / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["tool"]["setuptools"]["package-data"]


def _inclusi(patterns: dict[str, list[str]]) -> set[str]:
    base = REPO / "src"
    out: set[str] = set()
    for pkg, globs in patterns.items():
        radice = base / pkg.replace(".", "/")
        for g in globs:
            # `pkg` è un nome di pacchetto punteggiato (`fda.site`): i percorsi vanno
            # normalizzati a `fda/site/...`, altrimenti non si confrontano con i file reali
            out |= {f"{pkg.replace('.', '/')}/{p.relative_to(radice).as_posix()}"
                    for p in radice.glob(g)}
    return out


def test_ogni_file_non_python_del_pacchetto_e_dichiarato():
    """Un file di dati letto a runtime va dichiarato, altrimenti l'installazione lo perde.

    ``build.py`` carica i template con ``FileSystemLoader(Path(__file__).parent/'templates')``
    e la CSS con ``Path(__file__).parent/'assets'/'site.css'``: entrambe le directory vivono
    dentro il pacchetto, quindi entrambe devono stare in ``package-data``.
    """
    inclusi = _inclusi(_package_data())
    presenti = {f"fda/{p.relative_to(REPO / 'src' / 'fda').as_posix()}"
                for p in (REPO / "src" / "fda").rglob("*")
                if p.is_file() and p.suffix != ".py" and "__pycache__" not in p.parts}
    mancanti = sorted(presenti - inclusi)
    assert not mancanti, f"file del pacchetto non dichiarati in package-data: {mancanti}"


def test_css_e_template_del_sito_entrano_nel_pacchetto():
    inclusi = _inclusi(_package_data())
    for necessario in ("fda/site/templates/base.html", "fda/site/templates/match.html",
                       "fda/site/assets/site.css"):
        assert necessario in inclusi, f"{necessario} non è dichiarato in package-data"
        assert (REPO / "src" / necessario).exists(), f"{necessario} manca dal repository"


def test_l_anteprima_non_scrive_nella_directory_pubblicata():
    """``site/`` è l'output di ``fda build`` e ciò che Pages pubblica: l'anteprima sta altrove."""
    src = (REPO / "scripts" / "anteprima_scheda.py").read_text(encoding="utf-8")
    assert "out_dir=PREVIEW_DIR" in src, "l'anteprima deve dichiarare la sua directory"
    assert "SITE_DIR" not in src, "l'anteprima non deve toccare la directory pubblicata"
    assert 'PREVIEW_DIR = Path("site_preview")' in src
    assert "/site_preview/" in (REPO / ".gitignore").read_text(encoding="utf-8")


def test_il_database_derivate_non_e_versionato():
    """``fda.duckdb`` si rigenera dai Parquet: fuori da Git, come dice ``store.py``."""
    assert "data/processed/fda.duckdb" in (REPO / ".gitignore").read_text(encoding="utf-8")
    # `git ls-files` nel repository di lavoro: argomento fisso, nessun input esterno
    tracciati = subprocess.run(
        ["git", "ls-files", "data/processed/fda.duckdb"], cwd=REPO,
        capture_output=True, text=True, check=True).stdout.strip()
    assert tracciati == "", "fda.duckdb è ancora versionato: binario derivato, va tolto"
