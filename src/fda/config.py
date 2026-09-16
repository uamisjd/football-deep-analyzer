"""Caricamento della configurazione (config/leagues.yaml, config/sources.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Radice del repository: .../src/fda/config.py -> parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"

#: Giorni avanti per cui si raccolgono i dettagli partita (formazione, arbitro, meteo, h2h)
#: e per cui il sito promette «la scheda completa». UN SOLO PUNTO: collect, build e i testi
#: delle pagine leggono questo valore — un run manuale con un default diverso pubblicava un
#: elenco che prometteva più schede di quante ne esistano (P1.5, docs/19 §2.4).
DETAIL_WINDOW_DAYS: int = 7


@dataclass(frozen=True)
class League:
    key: str
    name: str
    country: str
    priority: int
    fotmob_id: int
    espn_code: str
    understat_slug: str | None
    footballdata_code: str
    datahub_dir: str | None
    clubelo_country: str
    teams: int
    datahub_base: str | None = None  # override del raw_base del mirror "datahub" per questa lega

    @property
    def has_understat(self) -> bool:
        return bool(self.understat_slug)


@dataclass(frozen=True)
class Cup:
    """Coppa europea seguita solo come calendario (congestione/riposo, docs/21 P1-4)."""

    key: str
    name: str
    fotmob_id: int
    espn_code: str | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def load_leagues_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "leagues.yaml")


@lru_cache(maxsize=1)
def load_sources_config() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "sources.yaml")


def cups() -> list[Cup]:
    """Coppe configurate in ``cups_calendar_only``: calendario, non modelli né schede."""
    return [Cup(**item) for item in load_leagues_config().get("cups_calendar_only", [])]


def season() -> str:
    """Stagione corrente in formato FotMob, es. '2026/2027'."""
    return str(load_leagues_config()["season"])


def season_start_year() -> int:
    """Anno di inizio stagione (usato da Understat e football-data)."""
    return int(season().split("/")[0])


def leagues(keys: list[str] | None = None) -> list[League]:
    """Elenco dei campionati configurati, ordinati per priorità.

    Args:
        keys: se indicato, filtra per chiavi (es. ["ITA1", "ENG1"]).
    """
    out = [League(**item) for item in load_leagues_config()["leagues"]]
    if keys:
        wanted = {k.upper() for k in keys}
        out = [lg for lg in out if lg.key in wanted]
        missing = wanted - {lg.key for lg in out}
        if missing:
            raise KeyError(f"Campionati sconosciuti: {sorted(missing)}")
    return sorted(out, key=lambda lg: lg.priority)


def league(key: str) -> League:
    return leagues([key])[0]


def source(name: str) -> dict[str, Any]:
    """Configurazione di una fonte (es. source('fotmob'))."""
    cfg = load_sources_config()
    if name not in cfg:
        raise KeyError(f"Fonte non configurata: {name}")
    return cfg[name]
