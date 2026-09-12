"""Storage: DuckDB (query) + Parquet (versionato nel repo, "git scraping").

Scelte:
- ogni tabella vive come file Parquet in data/processed/<tabella>.parquet: piccolo, diff-abile,
  leggibile da pandas/DuckDB senza server;
- il database DuckDB (data/processed/fda.duckdb) è una vista di comodo ricreata dai Parquet
  (non è versionato: si rigenera in pochi secondi);
- scrittura "upsert": le righe nuove sostituiscono quelle con la stessa chiave.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

from .config import PROCESSED_DIR

log = logging.getLogger(__name__)

# Chiavi primarie per l'upsert. Una tabella senza chiave viene semplicemente accodata.
TABLE_KEYS: dict[str, list[str]] = {
    "fixtures": ["match_id"],
    "match_info": ["match_id"],
    "shots": ["match_id", "shot_id"],
    "team_stats": ["match_id", "team_id", "period", "key"],
    "player_stats": ["match_id", "player_id", "key"],
    # senza "role": il ruolo di un giocatore cambia tra snapshot (probabile → ufficiale),
    # e con il ruolo in chiave lo stesso giocatore restava in due righe (13-19 "titolari").
    "lineup": ["match_id", "team_id", "player_id"],
    "events": ["match_id", "type", "minute", "minute_added", "is_home", "player_id"],
    "momentum": ["match_id", "minute"],
    "h2h": ["match_id", "home_id", "away_id", "utc"],
    "insights": ["match_id", "team_id", "player_id", "text"],
    "understat_matches": ["understat_id"],
    "understat_team_matches": ["league_slug", "season", "team_id", "date"],
    "understat_players": ["league_slug", "season", "player_id"],
    "espn_events": ["espn_id"],
    "espn_team_stats": ["espn_event_id", "team_id", "key"],
    "season_sim": ["league_key", "team"],
    "espn_standings": ["league_code", "team_id"],
    "fotmob_standings": ["league_code", "team_id"],
    "weather_forecast": ["match_id"],
    "predictions": ["match_id", "model", "made_at"],
    "odds_snapshots": ["match_id", "bookmaker", "market", "taken_at"],
    "source_status": ["run_at", "source"],
}


class Store:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or PROCESSED_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "fda.duckdb"
        self._con: duckdb.DuckDBPyConnection | None = None

    # ---- file -------------------------------------------------------------------------------
    def path(self, table: str) -> Path:
        return self.base_dir / f"{table}.parquet"

    def exists(self, table: str) -> bool:
        return self.path(table).exists()

    def read(self, table: str) -> pd.DataFrame:
        if not self.exists(table):
            return pd.DataFrame()
        return pd.read_parquet(self.path(table))

    def write(self, table: str, df: pd.DataFrame) -> None:
        if df.empty and not self.exists(table):
            return
        df = _normalize(df)
        # ordinamento stabile → diff Git piccoli
        keys = [k for k in TABLE_KEYS.get(table, []) if k in df.columns]
        if keys:
            df = df.sort_values(keys, kind="stable")
        df.reset_index(drop=True).to_parquet(self.path(table), index=False, compression="zstd")

    def upsert(self, table: str, rows: Iterable[dict[str, Any]] | pd.DataFrame,
               replace_by: str | None = None) -> int:
        """Inserisce/aggiorna righe per chiave. Ritorna il numero di righe nuove/aggiornate.

        ``replace_by`` (es. ``"match_id"``) è per le tabelle che sono **snapshot completi**
        di un'entità: eventi, formazioni, tiri, statistiche. Le righe esistenti con lo
        stesso valore vengono sostituite in blocco dalle nuove, invece di essere fuse per
        chiave. Due motivi concreti (entrambi osservati sui dati 2026-09-12):
        - una fusione per chiave lascia le righe vecchie accanto alle nuove quando la fonte
          cambia idea (un giocatore dato titolare nella formazione probabile e poi in
          panchina/indisponibile restava in entrambe le righe → «formazioni» da 13-19 nomi);
        - due righe legittime possono condividere la chiave (due sostituzioni allo stesso
          minuto hanno ``player_id`` nullo → la seconda veniva scartata: 6,5 sostituzioni
          per partita invece di ~10).
        """
        new = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
        if new.empty:
            return 0
        new = _normalize(new)
        old = self.read(table)
        keys = [k for k in TABLE_KEYS.get(table, []) if k in new.columns]
        if replace_by and replace_by in new.columns:
            if not old.empty and replace_by in old.columns:
                fresh = set(new[replace_by].astype(str))
                old = old[~old[replace_by].astype(str).isin(fresh)]
            merged = new if old.empty else pd.concat([old, new], ignore_index=True)
            # lo snapshot nuovo è autorevole: niente dedup per chiave (due sostituzioni allo
            # stesso minuto condividono la chiave), si fondono solo le righe identiche
            merged = merged.drop_duplicates()
            self.write(table, merged)
            return int(len(new))
        if old.empty or not keys:
            merged = pd.concat([old, new], ignore_index=True) if not old.empty else new
        else:
            # allinea le colonne (nuove colonne → NaN nelle vecchie righe)
            for col in new.columns:
                if col not in old.columns:
                    old[col] = pd.NA
            for col in old.columns:
                if col not in new.columns:
                    new[col] = pd.NA
            new = new[old.columns]
            idx_old = pd.MultiIndex.from_frame(old[keys].astype(str))
            idx_new = pd.MultiIndex.from_frame(new[keys].astype(str))
            keep = old[~idx_old.isin(idx_new)]
            merged = pd.concat([keep, new], ignore_index=True)
        if keys:
            merged = merged.drop_duplicates(subset=keys, keep="last")
        self.write(table, merged)
        return int(len(new))

    # ---- DuckDB ----------------------------------------------------------------------------
    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            self._con = duckdb.connect(str(self.db_path))
        return self._con

    def refresh_views(self) -> list[str]:
        """Crea/aggiorna una vista DuckDB per ogni Parquet presente."""
        names = []
        for p in sorted(self.base_dir.glob("*.parquet")):
            name = p.stem
            path_sql = str(p).replace("'", "''")
            self.con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM read_parquet(\'{path_sql}\')')
            names.append(name)
        return names

    def sql(self, query: str, params: list | None = None) -> pd.DataFrame:
        self.refresh_views()
        return self.con.execute(query, params or []).df()

    def summary(self) -> pd.DataFrame:
        rows = []
        for p in sorted(self.base_dir.glob("*.parquet")):
            n = self.con.execute("SELECT count(*) FROM read_parquet(?)", [str(p)]).fetchone()[0]
            rows.append({"table": p.stem, "rows": n, "kb": round(p.stat().st_size / 1024, 1)})
        return pd.DataFrame(rows)

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Tipi stabili per Parquet: datetime UTC, liste → stringhe, object misti → stringhe."""
    df = df.copy()
    for col in df.columns:
        s = df[col]
        if s.dtype == object:
            sample = s.dropna()
            if not sample.empty:
                first = sample.iloc[0]
                if isinstance(first, (list, tuple, dict)):
                    df[col] = s.apply(lambda v: None if v is None else str(v))
                elif hasattr(first, "tzinfo"):
                    df[col] = pd.to_datetime(s, utc=True, errors="coerce")
        if pd.api.types.is_datetime64_any_dtype(df[col]) and getattr(df[col].dt, "tz", None) is None:
            df[col] = df[col].dt.tz_localize("UTC")
    return df
