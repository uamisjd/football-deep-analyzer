"""Generazione del sito statico in `site/` (pubblicato da GitHub Pages)."""

from __future__ import annotations

import logging
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import REPO_ROOT, leagues, load_leagues_config
from ..models.predict import outcome_index
from ..store import Store
from .analysis import MatchAnalysis

log = logging.getLogger(__name__)

SITE_DIR = REPO_ROOT / "site"
TEMPLATES = Path(__file__).parent / "templates"
ITALIAN_DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
ITALIAN_MONTHS = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                  "settembre", "ottobre", "novembre", "dicembre"]


def day_label(d) -> str:
    return f"{ITALIAN_DAYS[d.weekday()]} {d.day} {ITALIAN_MONTHS[d.month]} {d.year}"


class SiteBuilder:
    def __init__(self, store: Store | None = None, out_dir: Path | None = None) -> None:
        self.store = store or Store()
        self.out = out_dir or SITE_DIR
        self.tz = ZoneInfo(load_leagues_config().get("timezone_display", "Europe/Rome"))
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                               autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
        self.now = datetime.now(timezone.utc)
        self.league_names = {lg.fotmob_id: lg.name for lg in leagues()}
        self.league_keys = {lg.fotmob_id: lg.key for lg in leagues()}
        self.analysis = MatchAnalysis(self.store)

    # ---- helpers ------------------------------------------------------------------------------
    def _render(self, template: str, rel_path: str, **ctx: Any) -> None:
        depth = rel_path.count("/")
        root = "../" * depth
        html = self.env.get_template(template).render(root=root, generated_at=self.now, **ctx)
        path = self.out / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def _match_rows(self, fx: pd.DataFrame) -> list[dict[str, Any]]:
        preds = self.store.read("predictions")
        latest = {}
        if not preds.empty:
            for r in preds.sort_values("made_at").itertuples(index=False):
                latest[int(r.match_id)] = r._asdict()
        rows = []
        for r in fx.itertuples(index=False):
            local = pd.Timestamp(r.utc_kickoff).tz_convert(self.tz)
            rows.append({
                "match_id": int(r.match_id), "league_name": self.league_names.get(int(r.league_id), str(r.league_id)),
                "utc_kickoff": local, "home_name": r.home_name, "away_name": r.away_name,
                "home_goals": None if pd.isna(r.home_goals) else int(r.home_goals),
                "away_goals": None if pd.isna(r.away_goals) else int(r.away_goals),
                "status": r.status, "prediction": latest.get(int(r.match_id)),
            })
        return rows

    def _group_by_day(self, rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
        groups: dict = defaultdict(list)
        for m in rows:
            groups[m["utc_kickoff"].date()].append(m)
        return [(day_label(d), sorted(v, key=lambda m: m["utc_kickoff"])) for d, v in sorted(groups.items())]

    # ---- pagine ----------------------------------------------------------------------------------
    def build_indexes(self, fx: pd.DataFrame) -> set[int]:
        today_local = self.now.astimezone(self.tz).date()
        fx = fx[fx.status != "cancelled"].copy()
        fx["local_date"] = pd.to_datetime(fx.utc_kickoff).dt.tz_convert(self.tz).dt.date
        today = fx[fx.local_date == today_local]
        upcoming = fx[(fx.local_date > today_local) & (fx.local_date <= today_local + timedelta(days=7))]
        results = fx[(fx.local_date < today_local) & (fx.local_date >= today_local - timedelta(days=7))
                     & (fx.status == "finished")]
        self._render("index.html", "index.html", title=f"Partite di oggi — {day_label(today_local)}",
                     subtitle="Probabilità 1 / X / 2 del modello, gol attesi e Over 2,5. Clicca una partita per l'analisi completa.",
                     days=self._group_by_day(self._match_rows(today)))
        self._render("index.html", "prossime.html", title="Prossimi 7 giorni",
                     subtitle="Previsioni aggiornate a ogni run (formazioni e assenze incluse quando disponibili).",
                     days=self._group_by_day(self._match_rows(upcoming)))
        self._render("index.html", "risultati.html", title="Risultati degli ultimi 7 giorni",
                     subtitle="Con lettura post-partita: xG, occasioni, cronaca e cosa aveva detto il modello.",
                     days=self._group_by_day(self._match_rows(results)))
        return set(pd.concat([today, upcoming, results]).match_id.astype(int))

    def build_match_pages(self, match_ids: set[int]) -> int:
        n = 0
        for mid in sorted(match_ids):
            ctx = self.analysis.build(mid)
            if not ctx:
                continue
            ctx["utc_kickoff"] = pd.Timestamp(ctx["utc_kickoff"]).tz_convert(self.tz)
            self._render("match.html", f"partite/{mid}.html", c=ctx,
                         league_name=self.league_names.get(ctx["league_id"], ""))
            n += 1
        return n

    def build_accuracy(self, fx: pd.DataFrame) -> None:
        preds = self.store.read("predictions")
        summary, recent = [], []
        if not preds.empty:
            fin = fx[fx.status == "finished"][["match_id", "home_goals", "away_goals", "utc_kickoff", "league_id"]]
            # la previsione valida è l'ultima fatta PRIMA del calcio d'inizio
            p = preds.merge(fin, on="match_id", suffixes=("", "_fx"))
            p = p[p.made_at < p.utc_kickoff_fx] if "utc_kickoff_fx" in p.columns else p[p.made_at < p.utc_kickoff]
            p = p.sort_values("made_at").groupby("match_id").tail(1)
            if not p.empty:
                p["outcome"] = [outcome_index(int(h), int(a)) for h, a in zip(p.home_goals, p.away_goals)]
                probs = p[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
                p["p_real"] = probs[np.arange(len(p)), p["outcome"].to_numpy()]
                p["league"] = p.league_id.map(self.league_names)
                for lg_name, g in list(p.groupby("league")) + [("Tutti", p)]:
                    pr = g[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
                    oc = g["outcome"].to_numpy()
                    onehot = np.eye(3)[oc]
                    naive = np.tile([0.45, 0.27, 0.28], (len(g), 1))
                    summary.append({"league": lg_name, "n": len(g), "rps": _rps(pr, oc), "brier": float(((pr - onehot) ** 2).sum(1).mean()),
                                    "hit": float((pr.argmax(1) == oc).mean()), "naive": _rps(naive, oc)})
                summary.sort(key=lambda r: (r["league"] == "Tutti", r["league"]))
                fxn = fx.set_index("match_id")
                for r in p.sort_values("utc_kickoff_fx" if "utc_kickoff_fx" in p.columns else "utc_kickoff", ascending=False).head(40).itertuples(index=False):
                    recent.append({"date": pd.Timestamp(getattr(r, "utc_kickoff_fx", r.utc_kickoff)).tz_convert(self.tz).strftime("%d/%m"),
                                   "match_id": int(r.match_id), "home": fxn.loc[r.match_id, "home_name"],
                                   "away": fxn.loc[r.match_id, "away_name"], "hg": int(r.home_goals), "ag": int(r.away_goals),
                                   "p_home": r.p_home, "p_draw": r.p_draw, "p_away": r.p_away, "p_real": r.p_real})
        self._render("accuracy.html", "accuratezza.html", summary=summary, recent=recent)

    def build_status(self) -> None:
        st = self.store.read("source_status")
        rows = []
        if not st.empty:
            last = st.sort_values("run_at").groupby("source").tail(1).sort_values("source")
            rows = [{"source": r.source, "run_at": pd.Timestamp(r.run_at).tz_convert(self.tz).strftime("%d/%m %H:%M"),
                     "requests": int(r.requests), "ok": bool(r.ok), "error": (r.error or "")[:120] if isinstance(r.error, str) else ""}
                    for r in last.itertuples(index=False)]
        tables = self.store.summary().to_dict("records") if not self.store.summary().empty else []
        self._render("status.html", "stato.html", sources=rows, tables=tables)

    def build(self) -> dict[str, int]:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        (self.out / ".nojekyll").write_text("")
        (self.out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        fx = self.store.read("fixtures")
        if fx.empty:
            self._render("index.html", "index.html", title="Nessun dato", subtitle="Esegui `fda collect` per popolare il database.", days=[])
            self.build_status()
            return {"matches": 0}
        ids = self.build_indexes(fx)
        n = self.build_match_pages(ids)
        self.build_accuracy(fx)
        self.build_status()
        return {"matches": n, "fixtures": int(len(fx))}


def _rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    onehot = np.eye(3)[outcomes]
    cp, co = probs.cumsum(1), onehot.cumsum(1)
    return float((((cp - co) ** 2).sum(1) / 2).mean())
