"""Storico risultati (football-data.co.uk) per addestrare e validare i modelli.

Fonte primaria: mirror GitHub `datasets/football-datasets` (CSV per stagione, senza quote),
raggiungibile da GitHub Actions via raw.githubusercontent.com. Fonte secondaria (con quote di
chiusura): football-data.co.uk `mmz4281/{YYYY}/{CODE}.csv` quando è online.
Le colonne vengono normalizzate in uno schema unico:
  date, season, league_key, home, away, home_goals, away_goals, [odds_home, odds_draw, odds_away]
"""

from __future__ import annotations

import io
import logging
from typing import Iterable

import pandas as pd

from ..config import League, source
from ..http import HttpClient, SourceError

log = logging.getLogger(__name__)

def _parse_dates(s: pd.Series) -> pd.Series:
    """datahub: 'YYYY-MM-DD'; football-data.co.uk: 'DD/MM/YYYY' (o 'DD/MM/YY' nelle stagioni vecchie)."""
    s = s.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    iso = s.str.match(r"^\d{4}-\d{2}-\d{2}")
    out[iso] = pd.to_datetime(s[iso], format="%Y-%m-%d", errors="coerce")
    slash4 = s.str.match(r"^\d{1,2}/\d{1,2}/\d{4}$")
    out[slash4] = pd.to_datetime(s[slash4], format="%d/%m/%Y", errors="coerce")
    slash2 = s.str.match(r"^\d{1,2}/\d{1,2}/\d{2}$")
    out[slash2] = pd.to_datetime(s[slash2], format="%d/%m/%y", errors="coerce")
    return out


# Stagione football-data: "2526" = 2025/26
def season_code(start_year: int) -> str:
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_label(start_year: int) -> str:
    return f"{start_year}/{start_year + 1}"


class HistoryClient:
    def __init__(self, client: HttpClient | None = None) -> None:
        self.datahub = source("datahub")
        self.fd = source("footballdata")
        self.http = client or HttpClient(name="history", rate_limit_s=0.5)

    # ---- download ----------------------------------------------------------------------------
    def datahub_csv(self, lg: League, start_year: int) -> pd.DataFrame | None:
        if not lg.datahub_dir:
            return None
        url = f"{self.datahub['raw_base']}/{lg.datahub_dir}/season-{season_code(start_year)}.csv"
        try:
            text = self.http.get_text(url, ttl_h=float(self.datahub.get("cache_ttl_h", 24)))
        except SourceError as exc:
            log.warning("datahub %s %s: %s", lg.key, start_year, exc)
            return None
        return self._normalize(pd.read_csv(io.StringIO(text)), lg, start_year)

    def footballdata_csv(self, lg: League, start_year: int) -> pd.DataFrame | None:
        url = f"{self.fd['base_url']}/{season_code(start_year)}/{lg.footballdata_code}.csv"
        try:
            text = self.http.get_text(url, ttl_h=float(self.fd.get("cache_ttl_h", 24)))
        except SourceError as exc:
            log.warning("football-data %s %s: %s", lg.key, start_year, exc)
            return None
        return self._normalize(pd.read_csv(io.StringIO(text), encoding_errors="replace"), lg, start_year)

    def season(self, lg: League, start_year: int) -> pd.DataFrame | None:
        """Stagione da datahub (preferito, sempre online); se manca, da football-data.co.uk."""
        df = self.datahub_csv(lg, start_year)
        if df is None or df.empty:
            df = self.footballdata_csv(lg, start_year)
        return df

    def seasons(self, lg: League, start_years: Iterable[int]) -> pd.DataFrame:
        frames = [d for y in start_years if (d := self.season(lg, y)) is not None and not d.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # ---- normalizzazione ---------------------------------------------------------------------
    @staticmethod
    def _normalize(raw: pd.DataFrame, lg: League, start_year: int) -> pd.DataFrame:
        cols = {c.strip(): c for c in raw.columns}
        need = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
        if any(c not in cols for c in need):
            raise SourceError(f"CSV storico senza colonne attese: {list(raw.columns)[:8]}")
        df = pd.DataFrame({
            "date": _parse_dates(raw[cols["Date"]]),
            "season": season_label(start_year),
            "league_key": lg.key,
            "home": raw[cols["HomeTeam"]].astype(str).str.strip(),
            "away": raw[cols["AwayTeam"]].astype(str).str.strip(),
            "home_goals": pd.to_numeric(raw[cols["FTHG"]], errors="coerce"),
            "away_goals": pd.to_numeric(raw[cols["FTAG"]], errors="coerce"),
        })
        # quote di chiusura (solo football-data.co.uk): Pinnacle chiusura > media chiusura > Bet365
        for out, candidates in (("odds_home", ["PSCH", "AvgCH", "B365CH", "PSH", "B365H"]),
                                ("odds_draw", ["PSCD", "AvgCD", "B365CD", "PSD", "B365D"]),
                                ("odds_away", ["PSCA", "AvgCA", "B365CA", "PSA", "B365A"])):
            for c in candidates:
                if c in cols:
                    df[out] = pd.to_numeric(raw[cols[c]], errors="coerce")
                    break
        df = df.dropna(subset=["date", "home_goals", "away_goals"])
        df["home_goals"] = df["home_goals"].astype(int)
        df["away_goals"] = df["away_goals"].astype(int)
        return df.sort_values("date").reset_index(drop=True)
