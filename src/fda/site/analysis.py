"""Costruzione del contenuto analitico di una partita (in italiano) a partire dallo store.

Nessuna generazione "creativa": ogni frase deriva da un numero presente nel database, con
regole esplicite (soglie documentate nel codice). Il risultato è un dizionario che i template
Jinja2 rendono in HTML.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..store import Store
from ..teams import canonical

POSITION_NAMES = {1: "portiere", 2: "difensore", 3: "centrocampista", 4: "attaccante"}


def _pct(p: float | None) -> str:
    return "—" if p is None or pd.isna(p) else f"{p * 100:.0f}%"


def _f(x: Any, nd: int = 2) -> str:
    return "—" if x is None or pd.isna(x) else f"{float(x):.{nd}f}"


def _first(df: pd.DataFrame) -> dict[str, Any]:
    return {} if df.empty else df.iloc[0].to_dict()


def _goals(info: dict, key: str, fixture: dict) -> int | None:
    v = _val(info, key)
    if v is None:
        v = _val(fixture, key)
    return None if v is None else int(v)


def _val(d: dict, key: str, default=None):
    v = d.get(key, default)
    return default if v is None or (isinstance(v, float) and pd.isna(v)) else v


class MatchAnalysis:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.fixtures = store.read("fixtures")
        self.info = store.read("match_info")
        self.lineup = store.read("lineup")
        self.team_stats = store.read("team_stats")
        self.shots = store.read("shots")
        self.events = store.read("events")
        self.preds = store.read("predictions")
        self.us_team = store.read("understat_team_matches")
        self.standings = store.read("espn_standings")

    # ---- forma recente da calendario --------------------------------------------------------
    def form(self, team_id: int, before: datetime, n: int = 5) -> list[dict[str, Any]]:
        fx = self.fixtures
        if fx.empty:
            return []
        played = fx[(fx.status == "finished") & (fx.utc_kickoff < before)
                    & ((fx.home_id == team_id) | (fx.away_id == team_id))].sort_values("utc_kickoff").tail(n)
        out = []
        for r in played.itertuples(index=False):
            is_home = r.home_id == team_id
            gf, ga = (r.home_goals, r.away_goals) if is_home else (r.away_goals, r.home_goals)
            res = "V" if gf > ga else ("N" if gf == ga else "P")
            opp = r.away_name if is_home else r.home_name
            out.append({"date": r.utc_kickoff, "opponent": opp, "home": is_home, "gf": int(gf), "ga": int(ga), "res": res})
        return out

    def rest_days(self, team_id: int, kickoff: datetime) -> int | None:
        fx = self.fixtures
        if fx.empty:
            return None
        prev = fx[(fx.utc_kickoff < kickoff) & (fx.status == "finished")
                  & ((fx.home_id == team_id) | (fx.away_id == team_id))]
        if prev.empty:
            return None
        return int((kickoff - prev.utc_kickoff.max()).total_seconds() // 86400)

    # ---- xG di stagione (Understat se c'è, altrimenti FotMob) ---------------------------------
    def season_xg(self, team_name: str, team_id: int) -> dict[str, Any] | None:
        canon = canonical(team_name)
        if not self.us_team.empty:
            rows = self.us_team[self.us_team.team_name.map(canonical) == canon]
            if not rows.empty:
                n = len(rows)
                return {"source": "Understat", "played": n, "xg": rows.xg.sum(), "xga": rows.xga.sum(),
                        "xg_pm": rows.xg.mean(), "xga_pm": rows.xga.mean(), "xpts": rows.xpts.sum(),
                        "pts": rows.pts.sum(), "ppda": rows.ppda.mean()}
        if not self.info.empty:
            fin = self.info[self.info.status == "finished"]
            h = fin[fin.home_id == team_id]
            a = fin[fin.away_id == team_id]
            xg = pd.concat([h.home_xg, a.away_xg]).dropna()
            xga = pd.concat([h.away_xg, a.home_xg]).dropna()
            if len(xg):
                return {"source": "FotMob", "played": int(len(xg)), "xg": xg.sum(), "xga": xga.sum(),
                        "xg_pm": xg.mean(), "xga_pm": xga.mean(), "xpts": None, "pts": None, "ppda": None}
        return None

    def standing(self, team_name: str) -> dict[str, Any] | None:
        if self.standings.empty:
            return None
        canon = canonical(team_name)
        rows = self.standings[self.standings.team_name.map(canonical) == canon]
        return None if rows.empty else rows.iloc[0].to_dict()

    # ---- assenze ------------------------------------------------------------------------------
    def unavailable(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "unavailable")]
        rows = rows.sort_values("market_value_eur", ascending=False, na_position="last")
        return [{"name": r.player_name, "type": _val(r._asdict(), "unavailability_type", "indisponibile"),
                 "ret": _val(r._asdict(), "expected_return"), "value": _val(r._asdict(), "market_value_eur"),
                 "pos": POSITION_NAMES.get(int(r.usual_position_id) if pd.notna(r.usual_position_id) else 0, "")}
                for r in rows.itertuples(index=False)]

    def starters(self, match_id: int, team_id: int) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.team_id == team_id)
                           & (self.lineup.role == "starter")]
        return [{"name": r.player_name, "num": r.shirt_number, "rating": r.rating, "season_rating": r.season_rating,
                 "captain": bool(r.is_captain)} for r in rows.itertuples(index=False)]

    # ---- statistiche post-partita ----------------------------------------------------------------
    def key_stats(self, match_id: int, home_id: int, away_id: int) -> list[dict[str, Any]]:
        if self.team_stats.empty:
            return []
        ts = self.team_stats[(self.team_stats.match_id == match_id) & (self.team_stats.period == "All")]
        wanted = [("BallPossesion", "Possesso palla"), ("expected_goals", "xG"), ("expected_goals_on_target", "xGOT"),
                  ("total_shots", "Tiri"), ("ShotsOnTarget", "Tiri in porta"), ("big_chance", "Grandi occasioni"),
                  ("big_chance_missed_title", "Grandi occasioni fallite"), ("accurate_passes", "Passaggi riusciti"),
                  ("corners", "Calci d'angolo"), ("fouls", "Falli"), ("yellow_cards", "Ammonizioni"),
                  ("red_cards", "Espulsioni"), ("touches_opp_box", "Tocchi in area avversaria")]
        out = []
        for key, label in wanted:
            h = ts[(ts.team_id == home_id) & (ts.key == key)]
            a = ts[(ts.team_id == away_id) & (ts.key == key)]
            if not h.empty and not a.empty:
                out.append({"label": label, "home": h.iloc[0].text, "away": a.iloc[0].text})
        return out

    def timeline(self, match_id: int) -> list[dict[str, Any]]:
        if self.events.empty:
            return []
        ev = self.events[(self.events.match_id == match_id) & (self.events.type.isin(["Goal", "Card", "Substitution"]))]
        ev = ev.sort_values(["minute", "minute_added"], na_position="first")
        out = []
        for r in ev.itertuples(index=False):
            d = r._asdict()
            swap = _val(d, "swap")
            if isinstance(swap, str):
                try:
                    swap = ast.literal_eval(swap)
                except (ValueError, SyntaxError):
                    swap = None
            out.append({"type": r.type, "minute": _val(d, "minute"), "added": _val(d, "minute_added"),
                        "home": bool(_val(d, "is_home", False)), "player": _val(d, "player_name"),
                        "card": _val(d, "card"), "own_goal": bool(_val(d, "own_goal", False)),
                        "score": f"{_val(d, 'home_score', '')}-{_val(d, 'away_score', '')}" if r.type == "Goal" else None,
                        "swap_in": swap[0][1] if swap and len(swap) > 0 else None,
                        "swap_out": swap[1][1] if swap and len(swap) > 1 else None})
        return out

    def top_players(self, match_id: int, n: int = 3) -> list[dict[str, Any]]:
        if self.lineup.empty:
            return []
        rows = self.lineup[(self.lineup.match_id == match_id) & (self.lineup.role.isin(["starter", "sub"]))
                           & self.lineup.rating.notna()].sort_values("rating", ascending=False).head(n)
        return [{"name": r.player_name, "team_id": int(r.team_id), "rating": float(r.rating)} for r in rows.itertuples(index=False)]

    def shot_summary(self, match_id: int, team_id: int) -> dict[str, Any]:
        if self.shots.empty:
            return {}
        s = self.shots[(self.shots.match_id == match_id) & (self.shots.team_id == team_id)]
        if s.empty:
            return {}
        big = s[s.xg >= 0.3]
        return {"n": int(len(s)), "xg": float(s.xg.sum()), "on_target": int(s.is_on_target.fillna(False).sum()),
                "inside_box": int(s.is_inside_box.fillna(False).sum()), "big_chances": int(len(big)),
                "best": _first(s.sort_values("xg", ascending=False)[["player_name", "xg", "minute", "event_type"]])}

    # ---- previsione ---------------------------------------------------------------------------------
    def prediction(self, match_id: int) -> dict[str, Any] | None:
        if self.preds.empty:
            return None
        p = self.preds[self.preds.match_id == match_id].sort_values("made_at").tail(1)
        if p.empty:
            return None
        d = p.iloc[0].to_dict()
        top = d.get("top_scores")
        if isinstance(top, str):
            try:
                top = ast.literal_eval(top)
            except (ValueError, SyntaxError):
                top = {}
        d["top_scores"] = top or {}
        return d

    # ---- testo analitico ----------------------------------------------------------------------------
    @staticmethod
    def narrative(ctx: dict[str, Any]) -> list[str]:
        """Frasi in italiano derivate dai numeri (regole esplicite)."""
        s: list[str] = []
        h, a = ctx["home_name"], ctx["away_name"]
        p = ctx.get("prediction")
        if p:
            fav = h if p["p_home"] >= p["p_away"] else a
            pf = max(p["p_home"], p["p_away"])
            if pf >= 0.60:
                s.append(f"Il modello vede {fav} nettamente favorito ({_pct(pf)}).")
            elif pf >= 0.45:
                s.append(f"Il modello indica {fav} favorito ({_pct(pf)}), ma con margine contenuto.")
            else:
                s.append(f"Partita equilibrata secondo il modello: {h} {_pct(p['p_home'])}, pareggio "
                         f"{_pct(p['p_draw'])}, {a} {_pct(p['p_away'])}.")
            tot = p["lambda_home"] + p["lambda_away"]
            if tot >= 3.0:
                s.append(f"Attesa una gara aperta: {_f(tot)} gol attesi complessivi, Over 2,5 al {_pct(p['p_over25'])}.")
            elif tot <= 2.2:
                s.append(f"Gara da pochi gol: {_f(tot)} gol attesi complessivi, Under 2,5 al {_pct(1 - p['p_over25'])}.")
            if p.get("p_btts") is not None and p["p_btts"] >= 0.58:
                s.append(f"Entrambe a segno probabile ({_pct(p['p_btts'])}).")
        for side, name in (("home", h), ("away", a)):
            f = ctx.get(f"{side}_form") or []
            if len(f) >= 3:
                pts = sum(3 if x["res"] == "V" else 1 if x["res"] == "N" else 0 for x in f)
                seq = "".join(x["res"] for x in f)
                if pts >= 2.4 * len(f):
                    s.append(f"{name} arriva in grande forma: {seq} nelle ultime {len(f)} ({pts} punti).")
                elif pts <= 0.6 * len(f):
                    s.append(f"{name} in difficoltà: {seq} nelle ultime {len(f)} ({pts} punti).")
            xg = ctx.get(f"{side}_xg")
            if xg and xg.get("xpts") is not None and xg.get("pts") is not None and xg["played"] >= 4:
                diff = xg["pts"] - xg["xpts"]
                if diff >= 3:
                    s.append(f"{name} ha raccolto {diff:+.1f} punti rispetto agli xPTS: rendimento sopra la qualità "
                             f"del gioco prodotto, possibile regressione.")
                elif diff <= -3:
                    s.append(f"{name} ha {diff:+.1f} punti rispetto agli xPTS: sta rendendo meno di quanto crea, "
                             f"segnale di sottovalutazione.")
            un = ctx.get(f"{side}_unavailable") or []
            if un:
                heavy = [u for u in un if u.get("value") and u["value"] >= 15_000_000]
                names = ", ".join(u["name"] for u in un[:4])
                extra = (" (tra cui 1 giocatore di peso)" if len(heavy) == 1
                         else f" (tra cui {len(heavy)} giocatori di peso)") if heavy else ""
                s.append(f"Assenze {name}: {len(un)}{extra} — {names}{'…' if len(un) > 4 else ''}.")
            rest = ctx.get(f"{side}_rest")
            if rest is not None and rest <= 3:
                s.append(f"{name} gioca dopo soli {rest} giorni di riposo.")
        ref = ctx.get("referee")
        if ref and ref.get("name"):
            y = ref.get("yellows")
            if y is not None:
                tone = "molto severo" if y >= 5 else "severo" if y >= 4.2 else "permissivo" if y <= 3.2 else "nella media"
                s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita ({tone})"
                         + (f", {ref['pens']} rigori in {ref['matches']} gare." if ref.get("pens") is not None else "."))
        w = ctx.get("weather")
        if w and w.get("desc"):
            extra = ""
            if w.get("precip") is not None and w["precip"] >= 50:
                extra = " — pioggia probabile, campo pesante"
            elif w.get("temp") is not None and w["temp"] >= 30:
                extra = " — caldo intenso, ritmi più bassi nel finale"
            s.append(f"Meteo previsto: {w['desc']}, {_f(w.get('temp'), 0)}°C{extra}.")
        if ctx.get("status") == "finished":
            hx, ax = ctx.get("home_xg_match"), ctx.get("away_xg_match")
            hg, ag = ctx.get("home_goals"), ctx.get("away_goals")
            if hx is not None and ax is not None and hg is not None and ag is not None:
                exp_w = h if hx > ax + 0.5 else a if ax > hx + 0.5 else None
                real_w = h if hg > ag else a if ag > hg else None
                if exp_w and real_w and exp_w != real_w:
                    s.append(f"Risultato contro il flusso di gioco: xG {_f(hx)}-{_f(ax)} a favore di {exp_w}, "
                             f"ma ha vinto {real_w}.")
                elif exp_w is None and real_w:
                    s.append(f"Gara equilibrata negli xG ({_f(hx)}-{_f(ax)}): {real_w} ha fatto la differenza nei dettagli.")
                else:
                    s.append(f"Risultato coerente con gli xG ({_f(hx)}-{_f(ax)}).")
            if p and hg is not None and ag is not None:
                ph = p["p_home"] if hg > ag else p["p_draw"] if hg == ag else p["p_away"]
                s.append(f"Il modello assegnava {_pct(ph)} all'esito verificatosi"
                         + (" (esito atteso)." if ph >= 0.4 else " (sorpresa)." if ph < 0.25 else "."))
        return s

    # ---- contesto completo ----------------------------------------------------------------------------
    def build(self, match_id: int) -> dict[str, Any] | None:
        fx = self.fixtures[self.fixtures.match_id == match_id] if not self.fixtures.empty else pd.DataFrame()
        if fx.empty:
            return None
        f = fx.iloc[0].to_dict()
        info = _first(self.info[self.info.match_id == match_id]) if not self.info.empty else {}
        kickoff = pd.Timestamp(f["utc_kickoff"])
        home_id, away_id = int(f["home_id"]), int(f["away_id"])
        status = _val(info, "status") or f["status"]
        ctx: dict[str, Any] = {
            "match_id": match_id, "league_id": int(f["league_id"]), "round": _val(f, "round"),
            "utc_kickoff": kickoff, "status": status,
            "home_id": home_id, "away_id": away_id,
            "home_name": f["home_name"], "away_name": f["away_name"],
            "home_goals": _goals(info, "home_goals", f), "away_goals": _goals(info, "away_goals", f),
            "home_form": self.form(home_id, kickoff), "away_form": self.form(away_id, kickoff),
            "home_rest": self.rest_days(home_id, kickoff), "away_rest": self.rest_days(away_id, kickoff),
            "home_xg": self.season_xg(f["home_name"], home_id), "away_xg": self.season_xg(f["away_name"], away_id),
            "home_standing": self.standing(f["home_name"]), "away_standing": self.standing(f["away_name"]),
            "home_unavailable": self.unavailable(match_id, home_id), "away_unavailable": self.unavailable(match_id, away_id),
            "home_starters": self.starters(match_id, home_id), "away_starters": self.starters(match_id, away_id),
            "lineup_type": _val(info, "lineup_type"),
            "home_formation": _val(info, "home_formation"), "away_formation": _val(info, "away_formation"),
            "home_value": _val(info, "home_starters_value_eur"), "away_value": _val(info, "away_starters_value_eur"),
            "referee": {"name": _val(info, "referee_name"), "matches": _val(info, "referee_matches"),
                        "yellows": _val(info, "referee_yellows_per_match"), "pens": _val(info, "referee_penalties_total"),
                        "reds": _val(info, "referee_reds_total")},
            "stadium": {"name": _val(info, "stadium_name"), "city": _val(info, "stadium_city"),
                        "attendance": _val(info, "attendance")},
            "weather": {"desc": _val(info, "weather_desc"), "temp": _val(info, "weather_temp_c"),
                        "precip": _val(info, "weather_precip_chance")},
            "h2h": (_val(info, "h2h_home_wins"), _val(info, "h2h_draws"), _val(info, "h2h_away_wins")),
            "prediction": self.prediction(match_id),
            "home_xg_match": _val(info, "home_xg"), "away_xg_match": _val(info, "away_xg"),
            "home_xgot_match": _val(info, "home_xgot"), "away_xgot_match": _val(info, "away_xgot"),
            "key_stats": self.key_stats(match_id, home_id, away_id) if status == "finished" else [],
            "timeline": self.timeline(match_id) if status == "finished" else [],
            "top_players": self.top_players(match_id) if status == "finished" else [],
            "home_shots": self.shot_summary(match_id, home_id) if status == "finished" else {},
            "away_shots": self.shot_summary(match_id, away_id) if status == "finished" else {},
            "generated_at": datetime.now(timezone.utc),
        }
        ctx["narrative"] = self.narrative(ctx)
        return ctx
