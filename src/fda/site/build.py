"""Generazione del sito statico in `site/` (pubblicato da GitHub Pages)."""

from __future__ import annotations

import logging
import shutil
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import REPO_ROOT, leagues, load_leagues_config
from ..models.predict import latest_per_match, outcome_index, wilson_interval
from ..store import Store
from .analysis import MatchAnalysis, prediction_meta
from .audit import audit_match
from .fmt import it_plural, pct_triple
from .players import PlayerCatalog

log = logging.getLogger(__name__)

SITE_DIR = REPO_ROOT / "site"
TEMPLATES = Path(__file__).parent / "templates"
OUTCOME_LABELS = ("1", "X", "2")
ITALIAN_DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
ITALIAN_MONTHS = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                  "settembre", "ottobre", "novembre", "dicembre"]
# forme brevi per il calendario completo: una riga per partita deve stare in poco spazio
ITALIAN_DAYS_SHORT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
ITALIAN_MONTHS_SHORT = ["", "gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


# ``pct_triple`` vive in fmt.py (unico punto di definizione, testato con property-based):
# qui era un wrapper con una copia di riserva di 15 righe dello stesso algoritmo, cioè
# duplicazione §3.7 — se la copia diverge, le barre del calendario e quelle della scheda
# mostrano percentuali diverse per la stessa previsione. Import diretto al posto del wrapper.


def day_label(d) -> str:
    return f"{ITALIAN_DAYS[d.weekday()]} {d.day} {ITALIAN_MONTHS[d.month]} {d.year}"


def it_datetime(ts) -> str:
    """Timestamp (già nel fuso display) → 'domenica 06/09/2026, 15:30'."""
    t = pd.Timestamp(ts)
    return f"{ITALIAN_DAYS[t.weekday()]} {t.day:02d}/{t.month:02d}/{t.year}, {t.hour:02d}:{t.minute:02d}"


def it_thousands(x) -> str:
    """Numero (anche float, es. 57000.0 dal Parquet) → '57.000' con separatore italiano."""
    return f"{int(float(x)):,}".replace(",", ".")


def it_dec(v, nd: int = 2, plus: bool = False) -> str:
    """Numero → stringa con virgola decimale italiana: 3.86 → '3,86' (plus=True → '+0,038')."""
    if v is None:
        return ""
    fv = float(v)
    if pd.isna(fv):
        return ""
    s = f"{fv:.{nd}f}".replace(".", ",")
    return f"+{s}" if plus and fv >= 0 else s


def it_from_utc(ts, tz) -> str:
    """Timestamp UTC → '08/09/2026 15:36' nel fuso display (Europe/Rome)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert(tz)
    return f"{t.day:02d}/{t.month:02d}/{t.year} {t.hour:02d}:{t.minute:02d}"


def it_date_short(ts, tz) -> str:
    """Timestamp → '08/09' nel fuso display (log partite delle schede giocatore)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return f"{t.tz_convert(tz).day:02d}/{t.tz_convert(tz).month:02d}"


def it_date_full(ts, tz) -> str:
    """Timestamp → '08/09/2026' nel fuso display (serve dove l'anno non è deducibile)."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert(tz)
    return f"{t.day:02d}/{t.month:02d}/{t.year}"


class SiteBuilder:
    def __init__(self, store: Store | None = None, out_dir: Path | None = None) -> None:
        self.store = store or Store()
        self.out = out_dir or SITE_DIR
        self.tz = ZoneInfo(load_leagues_config().get("timezone_display", "Europe/Rome"))
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                               autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
        # barra 1X2: larghezze ed etichette che sommano esattamente 100 (nd=0 o 1 decimali)
        self.env.filters["pct3"] = lambda t, nd=0: pct_triple(tuple(float(v) for v in t), nd)
        self.env.filters["it_dt"] = it_datetime
        self.env.filters["it_num"] = it_thousands
        self.env.filters["dec"] = it_dec
        self.env.filters["it_plural"] = it_plural
        self.env.filters["it_utc"] = lambda ts: it_from_utc(ts, self.tz)
        self.env.filters["it_dt_short"] = lambda ts: it_date_short(ts, self.tz)
        self.env.filters["it_dt_full"] = lambda ts: it_date_full(ts, self.tz)
        self.now = datetime.now(UTC)
        self.league_names = {lg.fotmob_id: lg.name for lg in leagues()}
        self.league_keys = {lg.fotmob_id: lg.key for lg in leagues()}
        self.analysis = MatchAnalysis(self.store)
        self.audit_rows: list[dict[str, Any]] = []

    # ---- helpers ------------------------------------------------------------------------------
    # mappa pagina → voce di nav attiva (aria-current)
    NAV_SECTIONS: ClassVar[dict[str, str]] = {
        "index.html": "oggi", "prossime.html": "prossime", "risultati.html": "risultati",
        "accuratezza.html": "accuratezza", "stagione.html": "stagione", "stato.html": "stato",
        "info.html": "info",
    }
    NAV_PREFIXES: ClassVar[list[tuple[str, str]]] = [("giocatori/", "giocatori")]

    def _render(self, template: str, rel_path: str, **ctx: Any) -> None:
        depth = rel_path.count("/")
        root = "../" * depth
        section = self.NAV_SECTIONS.get(rel_path, "")
        if not section:
            section = next((s for prefix, s in self.NAV_PREFIXES if rel_path.startswith(prefix)), "")
        # SEO: percorso canonico per <link rel="canonical"> e og:url
        canonical_path = rel_path if rel_path != "index.html" else ""
        html = self.env.get_template(template).render(root=root, generated_at=self.now, section=section, canonical_path=canonical_path, **ctx)
        path = self.out / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def _absence_counts(self) -> dict[tuple[int, int], int]:
        """Indisponibili per (partita, squadra): un groupby sulla distinta, costa poco.

        Serve alle liste (oggi / prossime) per anticipare il dato più richiesto senza
        aprire la scheda: quanti giocatori mancano a ciascuna squadra.
        """
        lu = self.analysis.lineup
        if lu.empty:
            return {}
        un = lu[lu.role == "unavailable"]
        if un.empty:
            return {}
        g = un.groupby(["match_id", "team_id"]).size()
        return {(int(a), int(b)): int(c) for (a, b), c in g.items()}

    @staticmethod
    def _status_bucket(status: Any) -> str:
        """Stato stabile per i filtri client-side della lista."""
        value = str(status or "").lower().strip()
        if value in {"in_progress", "live", "started", "started_live"}:
            return "live"
        if value in {"halftime", "half_time", "paused", "break"}:
            return "paused"
        if value in {"finished", "full_time", "ft"}:
            return "finished"
        if value in {"postponed", "postp", "delayed"}:
            return "postponed"
        if value in {"suspended", "abandoned", "cancelled", "canceled"}:
            return value  # bucket dedicato (filtro Tutti li mostra, banner dedicato)
        return "scheduled"

    @staticmethod
    def _status_label(status: Any) -> str:
        bucket = SiteBuilder._status_bucket(status)
        return {
            "live": "In corso",
            "paused": "Intervallo",
            "finished": "Terminata",
            "postponed": "Rinviata",
            "suspended": "Sospesa",
            "cancelled": "Annullata",
            "canceled": "Annullata",
            "abandoned": "Sospesa",
            "scheduled": "In programma",
        }.get(bucket, "In programma")

    def _match_rows(self, fx: pd.DataFrame) -> list[dict[str, Any]]:
        absent = self._absence_counts()
        rows = []
        for r in fx.itertuples(index=False):
            local = pd.Timestamp(r.utc_kickoff).tz_convert(self.tz)
            home_id, away_id = int(r.home_id), int(r.away_id)
            context = self.analysis.list_context(int(r.match_id), home_id, away_id,
                                                 r.home_name, r.away_name,
                                                 pd.Timestamp(r.utc_kickoff))
            prediction = context.get("prediction")
            if prediction is not None and prediction.get("meta") is None:
                prediction["meta"] = prediction_meta(prediction, r.home_name, r.away_name)
            league_key = self.league_keys.get(int(r.league_id), str(r.league_id))
            bucket = self._status_bucket(r.status)
            rows.append({
                "match_id": int(r.match_id), "league_name": self.league_names.get(int(r.league_id), str(r.league_id)),
                "league_key": league_key, "utc_kickoff": local, "home_name": r.home_name, "away_name": r.away_name,
                "home_goals": None if pd.isna(r.home_goals) else int(r.home_goals),
                "away_goals": None if pd.isna(r.away_goals) else int(r.away_goals),
                "status": r.status, "status_bucket": bucket, "status_label": self._status_label(r.status),
                "prediction": prediction, "context": context,
                "abs_home": absent.get((int(r.match_id), home_id), 0),
                "abs_away": absent.get((int(r.match_id), away_id), 0),
            })
        return rows

    @staticmethod
    def _list_filters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Leghe presenti nella vista, nell'ordine editoriale dei campionati configurati."""
        found = {str(row["league_key"]): str(row["league_name"]) for row in rows}
        return [{"key": key, "name": found[key]} for key in sorted(found, key=lambda k: found[k])]

    def _today_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        live = sum(row["status_bucket"] == "live" for row in rows)
        scheduled = sum(row["status_bucket"] == "scheduled" for row in rows)
        finished = sum(row["status_bucket"] == "finished" for row in rows)
        predicted = sum(row["prediction"] is not None for row in rows)
        next_match = next((row for row in sorted(rows, key=lambda item: item["utc_kickoff"])
                           if row["status_bucket"] == "scheduled"), None)
        return {
            "matches": len(rows), "leagues": len({row["league_key"] for row in rows}),
            "live": live, "scheduled": scheduled, "finished": finished,
            "predicted": predicted, "prediction_total": len(rows),
            "next_time": next_match["utc_kickoff"].strftime("%H:%M") if next_match else None,
            "next_match": (f'{next_match["home_name"]} – {next_match["away_name"]}'
                           if next_match else None),
        }

    def _calendar_rows(self, fx: pd.DataFrame, preds: pd.DataFrame,
                       with_card: set[int]) -> tuple[list[dict[str, Any]], int]:
        """Righe compatte per TUTTO il calendario in programma → (mesi, senza_previsione).

        Le righe ricche di ``_match_rows`` costano un contesto per partita (forma, classifica,
        assenze) e restano limitate alla finestra breve. Qui servono solo data, squadre e
        l'ultima previsione: così "Prossime" elenca l'intera stagione senza moltiplicare né i
        tempi di build né il peso della pagina (misurato: ~30 ms per previsione, ~250 B per riga).
        """
        by_id: dict[int, Any] = {}
        if preds is not None and not preds.empty:
            for r in latest_per_match(preds).itertuples(index=False):
                by_id[int(r.match_id)] = r
        mesi: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        senza = 0
        for r in fx.sort_values("utc_kickoff").itertuples(index=False):
            local = pd.Timestamp(r.utc_kickoff).tz_convert(self.tz)
            p = by_id.get(int(r.match_id))
            prev: dict[str, Any] | None = None
            if p is not None:
                pct = pct_triple((float(p.p_home), float(p.p_draw), float(p.p_away)))
                fav_i = max(range(3), key=lambda i: pct[i])
                tot = float(p.lambda_home) + float(p.lambda_away)
                prev = {"pct": pct, "fav": ("h", "d", "a")[fav_i], "fav_i": fav_i,
                        "gol": it_dec(tot, 1) if np.isfinite(tot) else None,
                        "over": int(round(float(p.p_over25) * 100)) if np.isfinite(p.p_over25) else None}
            else:
                senza += 1
            mesi[(local.year, local.month)].append({
                "match_id": int(r.match_id),
                "league_key": self.league_keys.get(int(r.league_id), str(r.league_id)),
                "league_name": self.league_names.get(int(r.league_id), str(r.league_id)),
                "when": f"{ITALIAN_DAYS_SHORT[local.weekday()]} {local.day} {ITALIAN_MONTHS_SHORT[local.month]}",
                "time": local.strftime("%H:%M"), "date": local.date().isoformat(),
                "home_name": str(r.home_name), "away_name": str(r.away_name),
                # la scheda esiste solo nella finestra breve: altrove la riga resta testuale
                "url": f"partite/{int(r.match_id)}.html" if int(r.match_id) in with_card else None,
                "prediction": prev,
            })
        # la chiave si chiama "matches", non "items": in Jinja `mo.items` risolverebbe al
        # metodo dict.items invece che alla lista
        out = [{"id": f"mese-{y}-{m:02d}", "label": f"{ITALIAN_MONTHS[m].capitalize()} {y}",
                "label_short": f"{ITALIAN_MONTHS_SHORT[m].capitalize()} {str(y)[2:]}",
                "count": len(rows), "matches": rows}
               for (y, m), rows in sorted(mesi.items())]
        return out, senza

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
        today_rows = self._match_rows(today)
        upcoming_rows = self._match_rows(upcoming)
        result_rows = self._match_rows(results)
        ids_breve = set(pd.concat([today, upcoming, results]).match_id.astype(int))
        # --- calendario completo: ciò che la finestra breve non copre, in forma compatta ---
        # non costa richieste extra (le partite sono già state raccolte da `fda collect`) e
        # nemmeno analisi per partita: una riga = data, squadre e ultima previsione disponibile
        lontano = fx[(fx.status.isin(["scheduled", "postponed", "suspended", "cancelled"])) & (fx.local_date > today_local + timedelta(days=7))]
        calendar, calendar_missing = self._calendar_rows(lontano, self.store.read("predictions"), ids_breve)
        log.info("calendario completo: %d partite in %d mesi (%d senza previsione)",
                 len(lontano), len(calendar), calendar_missing)
        self._render("index.html", "index.html", title=f"Partite di oggi — {day_label(today_local)}",
                     subtitle="Il quadro della giornata, poi il dettaglio verificabile di ogni partita.",
                     page_title=f"Partite di oggi — {day_label(today_local)} · CalcioMetro",
                     page_description="Tutte le partite di oggi con analisi pre-partita, previsioni Dixon-Coles+Elo, forma, indisponibili, arbitro e meteo. Aggiornato 5 volte al giorno.",
                     days=self._group_by_day(today_rows), view_kind="today",
                     summary=self._today_summary(today_rows), filters=self._list_filters(today_rows))
        self._render("index.html", "prossime.html", title="Prossime partite",
                     subtitle="I prossimi 7 giorni con la scheda completa, poi tutto il calendario "
                              "della stagione in forma compatta.",
                     page_title="Prossime partite e calendario completo · CalcioMetro",
                     page_description="I prossimi 7 giorni con schede dettagliate e l'intero calendario stagionale in forma compatta: pronostici, gol attesi e Over 2,5 per ogni gara.",
                     days=self._group_by_day(upcoming_rows), view_kind="upcoming", summary=None,
                     filters=self._list_filters(upcoming_rows),
                     calendar=calendar, calendar_missing=calendar_missing, calendar_days=7)
        self._render("index.html", "risultati.html", title="Risultati degli ultimi 7 giorni",
                     subtitle="Con lettura post-partita: xG, occasioni, cronaca e cosa aveva detto il modello.",
                     page_title="Risultati recenti e analisi post-partita · CalcioMetro",
                     page_description="Risultati degli ultimi 7 giorni con lettura post-partita: xG, occasioni, cronaca e verifica delle previsioni.",
                     days=self._group_by_day(result_rows), view_kind="results", summary=None,
                     filters=self._list_filters(result_rows))
        return ids_breve

    @staticmethod
    def _json_ld_match(ctx: dict[str, Any], league_name: str, base_url: str) -> str:
        """JSON-LD SportsEvent per SEO (audit 2.3) — una stringa JSON pronta per <script>."""
        import json
        try:
            kick = pd.Timestamp(ctx["utc_kickoff"])
            if kick.tzinfo is None:
                kick = kick.tz_localize("UTC")
            iso = kick.tz_convert(ZoneInfo("Europe/Rome")).isoformat()
        except Exception:
            iso = str(ctx.get("utc_kickoff", ""))
        name = f'{ctx.get("home_name","")} – {ctx.get("away_name","")} ({league_name})' if league_name else f'{ctx.get("home_name","")} – {ctx.get("away_name","")}'
        url = f'{base_url}/partite/{ctx.get("match_id")}.html'
        data = {
            "@context": "https://schema.org",
            "@type": "SportsEvent",
            "name": name,
            "startDate": iso,
            "sport": "Soccer",
            "homeTeam": {"@type": "SportsTeam", "name": ctx.get("home_name","")},
            "awayTeam": {"@type": "SportsTeam", "name": ctx.get("away_name","")},
            "competitor": [{"@type": "SportsTeam", "name": ctx.get("home_name","")}, {"@type": "SportsTeam", "name": ctx.get("away_name","")}],
            "location": {"@type": "Place", "name": ctx.get("stadium",{}).get("name") or league_name, "address": ctx.get("stadium",{}).get("city") or ""},
            "url": url,
            "eventStatus": "https://schema.org/EventScheduled" if ctx.get("status") != "finished" else "https://schema.org/EventCompleted",
        }
        # pulisci campi vuoti per validatore
        if not data["location"]["address"]:
            data["location"].pop("address", None)
        return json.dumps(data, ensure_ascii=False)


    def build_match_pages(self, match_ids: set[int]) -> set[int]:
        """Pagine partita: ritorna gli id effettivamente generati (per i link del log giocatori)."""
        built: set[int] = set()
        base_url = "https://uamisjd.github.io/football-deep-analyzer"
        for mid in sorted(match_ids):
            ctx = self.analysis.build(mid)
            if not ctx:
                continue
            ctx["utc_kickoff"] = pd.Timestamp(ctx["utc_kickoff"]).tz_convert(self.tz)
            if ctx["status"] != "finished":
                self.audit_rows.append(audit_match(ctx))
            league_name = self.league_names.get(ctx["league_id"], "")
            json_ld = self._json_ld_match(ctx, league_name, base_url)
            # SEO per la scheda: descrizione compatta con 1X2 se disponibile
            p = ctx.get("prediction")
            if p and p.get("p_home") is not None:
                page_desc = (f'{ctx.get("home_name")}–{ctx.get("away_name")} · {league_name}: '
                             f'1 {int(round(p["p_home"]*100))}% X {int(round(p["p_draw"]*100))}% 2 {int(round(p["p_away"]*100))}% '
                             f'· gol attesi {p.get("lambda_home",0):.2f}–{p.get("lambda_away",0):.2f} · Over 2,5 {int(round(p.get("p_over25",0)*100))}%')
            else:
                page_desc = f'{ctx.get("home_name")}–{ctx.get("away_name")} · {league_name} — analisi pre-partita, forma e precedenti.'
            page_title = f'{ctx.get("home_name")} - {ctx.get("away_name")} — analisi · CalcioMetro'
            self._render("match.html", f"partite/{mid}.html", c=ctx,
                         league_name=league_name, json_ld=json_ld,
                         page_title=page_title, page_description=page_desc)
            built.add(mid)
        return built

    def build_players(self, built_match_ids: set[int]) -> int:
        """Pagine `giocatori/`: hub, tabellone per lega e scheda di ogni giocatore (fase 3)."""
        cat = PlayerCatalog(self.store)
        lg_by_id = {lg.fotmob_id: lg for lg in leagues()}
        blocks = []
        for lg in leagues():
            if cat.empty:
                break
            rows, bench = cat.league_rows(lg.fotmob_id)
            if not rows and not bench:
                continue
            blocks.append(cat.hub_block(lg.fotmob_id, lg.name, lg.key))
        self._render("giocatori_hub.html", "giocatori/index.html", leagues=blocks,
                     min_minutes=90, title="Giocatori")
        n = 0
        for lg in leagues():
            rows, bench = cat.league_rows(lg.fotmob_id)
            if not rows and not bench:
                continue
            self._render("giocatori_lega.html", f"giocatori/{lg.key}.html", rows=rows,
                         bench=bench, league_name=lg.name, season=cat.season,
                         positions=[("Portieri", "Portiere"), ("Difensori", "Difensore"),
                                    ("Centrocampisti", "Centrocampista"), ("Attaccanti", "Attaccante")])
            n += len(rows) + len(bench)
        for pid in cat.player_ids():
            page = cat.player_page(pid, built_match_ids)
            if page is None:
                continue
            lg = lg_by_id.get(page["league_id"])
            self._render("giocatore.html", f"giocatori/{pid}.html", p=page,
                         league_name=lg.name if lg else None,
                         league_key=lg.key if lg else None)
            n += 1
        return n

    def build_stagione(self) -> None:
        """Pagina «Proiezioni di stagione» dalla tabella `season_sim` (vuota → segnaposto)."""
        sim = self.store.read("season_sim")
        if sim.empty:
            self._render("stagione.html", "stagione.html", title="Proiezioni di stagione",
                         n_sims=None, updated=None, leagues=[],
                         subtitle="Le proiezioni arrivano dopo il primo run con `fda simulate`.")
            return
        names = {l.key: l.name for l in leagues(None)}
        blocks = []
        for key, grp in sim.groupby("league_key"):
            rows = grp.sort_values("exp_points", ascending=False)
            blocks.append({"key": str(key), "name": names.get(str(key), str(key)),
                           "rows": rows.to_dict("records")})
        order = {k: i for i, k in enumerate(["ITA1", "ENG1", "ESP1", "GER1", "FRA1", "NED1", "POR1"])}
        blocks.sort(key=lambda b: order.get(b["key"], 99))
        self._render("stagione.html", "stagione.html", title="Proiezioni di stagione",
                     n_sims=sim["n_sims"].max(), updated=it_from_utc(sim["made_at"].max(), self.tz),
                     leagues=blocks)

    # mercati binari pubblicati dal modello → (colonna, etichetta, evento osservato)
    MARKETS: ClassVar[tuple[tuple[str, str, str], ...]] = (
        ("p_over15", "Over 1,5 gol", "over15"),
        ("p_over25", "Over 2,5 gol", "over25"),
        ("p_over35", "Over 3,5 gol", "over35"),
        ("p_btts", "Gol · entrambe a segno", "btts"),
        ("p_1x", "Doppia chance 1X", "d1x"),
        ("p_12", "Doppia chance 12", "d12"),
        ("p_x2", "Doppia chance X2", "dx2"),
        ("p_home_clean_sheet", "Porta inviolata casa", "cs_h"),
        ("p_away_clean_sheet", "Porta inviolata trasferta", "cs_a"),
    )

    def build_accuracy(self, fx: pd.DataFrame) -> None:
        preds = self.store.read("predictions")
        summary, recent, calib, markets = [], [], [], []
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
                p["top"] = [OUTCOME_LABELS[i] for i in probs.argmax(1)]
                p["hit"] = probs.argmax(1) == p["outcome"].to_numpy()
                p["rps"] = _rps_rows(probs, p["outcome"].to_numpy())
                p["league"] = p.league_id.map(self.league_names)
                for lg_name, g in list(p.groupby("league")) + [("Tutti", p)]:
                    pr = g[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
                    oc = g["outcome"].to_numpy()
                    onehot = np.eye(3)[oc]
                    naive = np.tile([0.45, 0.27, 0.28], (len(g), 1))
                    rps, rps_naive = _rps(pr, oc), _rps(naive, oc)
                    summary.append({"league": lg_name, "n": len(g), "rps": rps, "brier": float(((pr - onehot) ** 2).sum(1).mean()),
                                    "hit": float((pr.argmax(1) == oc).mean()), "naive": rps_naive, "delta": rps - rps_naive})
                summary.sort(key=lambda r: (r["league"] == "Tutti", r["league"]))
                # calibrazione: probabilità media prevista vs frequenza osservata (tutte le gare valutate)
                oc_all = p["outcome"].to_numpy()
                n_all = int(len(p))
                calib = []
                for i, lbl in enumerate(("1 · vittoria in casa", "X · pareggio", "2 · vittoria in trasferta")):
                    k = int((oc_all == i).sum())
                    lo, hi = wilson_interval(k, n_all)
                    prev = float(probs[:, i].mean())
                    calib.append({"label": lbl, "prev": prev, "obs": k / n_all if n_all else 0.0,
                                  "k": k, "n": n_all, "lo": lo, "hi": hi,
                                  "outside": bool(not (lo <= prev <= hi))})
                fxn = fx.set_index("match_id")
                for r in p.sort_values("utc_kickoff_fx" if "utc_kickoff_fx" in p.columns else "utc_kickoff", ascending=False).head(40).itertuples(index=False):
                    recent.append({"date": pd.Timestamp(getattr(r, "utc_kickoff_fx", r.utc_kickoff)).tz_convert(self.tz).strftime("%d/%m"),
                                   "match_id": int(r.match_id), "home": fxn.loc[r.match_id, "home_name"],
                                   "away": fxn.loc[r.match_id, "away_name"], "hg": int(r.home_goals), "ag": int(r.away_goals),
                                   "p_home": r.p_home, "p_draw": r.p_draw, "p_away": r.p_away, "p_real": r.p_real,
                                   "top": r.top, "hit": bool(r.hit), "rps": float(r.rps)})
                # mercati binari: Brier contro quello della frequenza di base (stesso campione)
                tot = (p.home_goals.astype(float) + p.away_goals.astype(float)).to_numpy()
                hg = p.home_goals.astype(float).to_numpy()
                ag = p.away_goals.astype(float).to_numpy()
                observed = {
                    "over15": tot > 1.5, "over25": tot > 2.5, "over35": tot > 3.5,
                    "btts": (hg > 0) & (ag > 0),
                    "d1x": hg >= ag, "d12": hg != ag, "dx2": hg <= ag,
                    "cs_h": ag == 0, "cs_a": hg == 0}
                for col, label, key in self.MARKETS:
                    if col not in p.columns:
                        continue
                    pr = pd.to_numeric(p[col], errors="coerce").to_numpy(dtype=float)
                    y = observed[key].astype(float)
                    ok = ~np.isnan(pr)
                    if ok.sum() < 5:
                        continue
                    pr, y = pr[ok], y[ok]
                    base = y.mean()
                    n_mk = int(ok.sum())
                    k_mk = int(round(float(y.sum())))
                    lo_mk, hi_mk = wilson_interval(k_mk, n_mk)
                    prev_mk = float(pr.mean())
                    markets.append({"label": label, "n": n_mk, "k": k_mk, "prev": prev_mk,
                                    "obs": float(base), "brier": float(((pr - y) ** 2).mean()),
                                    "brier_base": float(((base - y) ** 2).mean()),
                                    "hit": float((((pr >= 0.5).astype(float)) == y).mean()),
                                    "lo": lo_mk, "hi": hi_mk,
                                    "outside": bool(not (lo_mk <= prev_mk <= hi_mk))})
                    markets[-1]["delta"] = markets[-1]["brier"] - markets[-1]["brier_base"]
                # RPS per anticipo (lead time): ora misurabile perché Tappa 1 prevede tutto il calendario
                # made_at vs utc_kickoff → bucket 0-7/8-14/15-30/31-60/61+ giorni
                lead_buckets = []
                try:
                    # p ha made_at (UTC) e utc_kickoff_fx (UTC)
                    made = pd.to_datetime(p["made_at"], utc=True)
                    kick = pd.to_datetime(p["utc_kickoff_fx"] if "utc_kickoff_fx" in p.columns else p["utc_kickoff"], utc=True)
                    lead_days = (kick - made).dt.total_seconds() / 86400.0
                    p["_lead_days"] = lead_days
                    buckets = [
                        (0, 7, "0–7 giorni"),
                        (8, 14, "8–14 giorni"),
                        (15, 30, "15–30 giorni"),
                        (31, 60, "31–60 giorni"),
                        (61, 9999, "61+ giorni"),
                    ]
                    for lo, hi, label in buckets:
                        sub = p[(lead_days >= lo) & (lead_days <= hi)]
                        if sub.empty:
                            continue
                        pr_b = sub[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
                        oc_b = sub["outcome"].to_numpy()
                        rps_b = _rps(pr_b, oc_b)
                        hit_b = float((pr_b.argmax(1) == oc_b).mean())
                        lead_buckets.append({
                            "label": label,
                            "lo": lo,
                            "hi": hi,
                            "n": int(len(sub)),
                            "rps": float(rps_b),
                            "hit": hit_b,
                            "lead_mean": float(lead_days[(lead_days >= lo) & (lead_days <= hi)].mean()),
                        })
                except Exception as exc:
                    # non bloccare la pagina se il calcolo fallisce (dati vecchi senza made_at)
                    lead_buckets = []
                    import logging
                    logging.getLogger(__name__).debug("RPS per anticipo saltato: %s", exc)
        # backtest cronologico fuori campione (tabella prodotta da `fda backtest`): la card
        # compare solo se esiste, come le sezioni condizionate alla disponibilità della fonte
        bt_rows = self.store.read("backtest")
        bt = {}
        if not bt_rows.empty:
            from ..models.backtest import backtest_summary, calibrate_rows
            from ..models.calibration import from_store

            # la card descrive il modello **come viene pubblicato** (previsioni calibrate);
            # `backtest.parquet` resta grezzo perché è il campione su cui si stima la
            # calibrazione. Il riepilogo grezzo resta a fianco, per il confronto.
            cal = from_store(self.store)
            bt = backtest_summary(calibrate_rows(bt_rows, cal))
            bt["grezzo"] = backtest_summary(bt_rows)
        self._render("accuracy.html", "accuratezza.html", summary=summary, recent=recent, calib=calib,
                     markets=markets, bt=bt, lead_buckets=lead_buckets if 'lead_buckets' in locals() else [])

    def build_status(self) -> None:
        st = self.store.read("source_status")
        rows = []
        if not st.empty:
            last = st.sort_values("run_at").groupby("source").tail(1).sort_values("source")
            rows = []
            for r in last.itertuples(index=False):
                err = (r.error or "") if isinstance(r.error, str) else ""
                rows.append({"source": r.source,
                             "run_at": pd.Timestamp(r.run_at).tz_convert(self.tz).strftime("%d/%m %H:%M"),
                             "requests": int(r.requests), "ok": bool(r.ok),
                             "warn": bool(getattr(r, "warn", False)) or "espn standings" in err,
                             "error": err[:120]})
        tables = self.store.summary().to_dict("records") if not self.store.summary().empty else []
        by_state = {s: sum(1 for a in self.audit_rows for i in a["items"] if i["state"] == s)
                    for s in ("presente", "atteso", "mancante")}
        self._render("status.html", "stato.html", sources=rows, tables=tables,
                     audit=self.audit_rows, audit_counts=by_state)

    def _write_seo_files(self, built_match_ids: set[int] | None = None) -> None:
        """robots.txt aperto + sitemap.xml per indicizzazione organica (SEO)."""
        base = "https://uamisjd.github.io/football-deep-analyzer"
        (self.out / "robots.txt").write_text(
            "User-agent: *\nAllow: /\nSitemap: " + base + "/sitemap.xml\n"
        )
        urls = ["", "index.html", "prossime.html", "risultati.html",
                "accuratezza.html", "stagione.html", "stato.html", "info.html",
                "giocatori/index.html"]
        if built_match_ids:
            urls += [f"partite/{mid}.html" for mid in sorted(built_match_ids)]
            # schede giocatore (opzionale, sitemap solo se presenti)
            try:
                from ..site.players import PlayerCatalog
                cat = PlayerCatalog(self.store)
                urls += [f"giocatori/{pid}.html" for pid in cat.player_ids()[:5000]]
            except Exception:
                pass
        now = self.now.strftime("%Y-%m-%d")
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for u in urls:
            loc = f"{base}/{u}" if u else base + "/"
            lines.append(f"  <url><loc>{loc}</loc><lastmod>{now}</lastmod></url>")
        lines.append("</urlset>")
        (self.out / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")

    def build(self) -> dict[str, int]:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        (self.out / ".nojekyll").write_text("")
        (self.out / "robots.txt").write_text(
            "User-agent: *\nAllow: /\nSitemap: https://uamisjd.github.io/football-deep-analyzer/sitemap.xml\n"
        )
        fx = self.store.read("fixtures")
        if fx.empty:
            self._render("index.html", "index.html", title="Nessun dato",
                         subtitle="Esegui `fda collect` per popolare il database.", days=[],
                         view_kind="today", summary=None, filters=[])
            self.build_status()
            return {"matches": 0}
        ids = self.build_indexes(fx)
        # tutte le partite finite con dati raccolti hanno la loro pagina (archivio:
        # backfill completo di stagione dal 2026-09-09), oltre alla finestra oggi/7 giorni
        mi = self.store.read("match_info")
        if not mi.empty:
            fin = set(mi.loc[mi["status"] == "finished", "match_id"].astype(int))
            fx_fin = set(fx.loc[fx["status"] == "finished", "match_id"].astype(int))
            ids |= fin & fx_fin
        built = self.build_match_pages(ids)
        n_players = self.build_players(built)
        self.build_accuracy(fx)
        self.build_stagione()
        self.build_status()
        # info.html ora riceve la calibrazione live e il riepilogo lab per mostrare badge e dettagli misurati
        try:
            from ..models.calibration import from_store
            cal = from_store(self.store)
            cal_info = {
                "version": cal.version if not cal.is_identity else None,
                "lambda_scale": cal.lambda_scale,
                "rho_shift": cal.rho_shift,
                "estimator": cal.estimator,
                "window_days": cal.window_days,
                "n_fit": cal.n_fit if hasattr(cal, 'n_fit') else None,
                "is_identity": cal.is_identity,
                # bias dei gol attesi sul campione pieno, prima e dopo la correzione: la scheda
                # dice in quali numeri si vede l'effetto, invece di descriverlo a parole
                "bias_prima": cal.metrics.get("campione_bias_lambda"),
                "bias_dopo": cal.metrics.get("dopo_bias_lambda"),
            }
        except Exception:
            cal_info = {"is_identity": True}
        try:
            ml = self.store.read("model_lab")
            lab_rows = len(ml) if not ml.empty else 0
        except Exception:
            lab_rows = 0
        self._render("info.html", "info.html", title="Metodologia e fonti", cal=cal_info, lab_rows=lab_rows)
        # sitemap finale con tutte le partite effettivamente generate
        try:
            self._write_seo_files(built)
        except Exception as exc:  # mai bloccare il build per la sitemap
            log.warning("sitemap non scritta: %s", exc)
        return {"matches": len(built), "fixtures": len(fx), "players": n_players}


def _rps(probs: np.ndarray, outcomes: np.ndarray) -> float:
    onehot = np.eye(3)[outcomes]
    cp, co = probs.cumsum(1), onehot.cumsum(1)
    return float((((cp - co) ** 2).sum(1) / 2).mean())


def _rps_rows(probs: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    """RPS per singola gara (array 1-D, lunghezza = numero di gare)."""
    onehot = np.eye(3)[outcomes]
    cp, co = probs.cumsum(1), onehot.cumsum(1)
    return ((cp - co) ** 2).sum(1) / 2
