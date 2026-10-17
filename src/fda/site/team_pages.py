"""Pagine squadra: una scheda per ciascuna delle squadre seguite (`docs/114`).

Il sito è nato attorno alla **partita**: fino al 17/10/2026 non esisteva un indirizzo a cui
seguire una squadra. Questa classe costruisce i dati di ``squadre/<team_id>.html`` da ciò che
la raccolta produce già — nessuna fonte nuova, nessuna richiesta HTTP aggiuntiva — e riusa le
funzioni della scheda partita per i numeri che le due pagine condividono (classifica, forma,
previsioni, proiezioni di stagione, indisponibili, distinta). Il principio è quello di
`docs/00` §F: se una squadra appare in due punti del sito, i due punti devono dire la stessa
cifra; per questo ogni blocco nasce da :class:`~fda.site.analysis.MatchAnalysis` o da
:class:`~fda.site.players.PlayerCatalog`, mai da un calcolo locale diverso.

Che cosa **non** fa: non inventa un «valore rosa» aggregato, non somma xG di stagione presi da
fonti diverse e non pubblica la posizione di una stagione passata se lo storico non copre quella
lega. Le sezioni senza dato spariscono o mostrano un segnaposto dichiarato, come nelle schede.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import pandas as pd

from ..config import leagues, load_leagues_config
from ..models.predict import latest_per_match
from ..teams import canonical
from .analysis import MatchAnalysis
from .fmt import it_day_time
from .players import PlayerCatalog

#: quanti impegni mostrare in «Prossime» e quanti risultati in «Ultime»
N_MATCHES = 5
#: quanti movimenti di mercato per lato (arrivi/partenze) finiscono in pagina
N_MOVES = 6
#: quante notizie italiane della squadra finiscono in pagina (con fonte, data e link)
N_NEWS = 3
#: voci che non riguardano la **prima squadra**: settore giovanile e formazioni femminili.
#: Non è un filtro di pertinenza fine (quello della scheda partita lavora sul singolo match);
#: è la regola minima perché la pagina di una squadra non racconti la Primavera o l'U19.
_NEWS_ALTRO = re.compile(r"\b(under\s*1[5-9]|u1[5-9]|primavera|women|femminil|giovanil)\b", re.IGNORECASE)

#: titoli che sono servizi di sito, non notizie: il classificatore non li conosce tutti,
#: ma sono riconoscibili a occhio e non devono riempire la rassegna della squadra
_NEWS_JUNK = re.compile(r"scheda squadra|risultati in diretta|pronostico|migliori quote", re.IGNORECASE)

#: stagioni di storico pubblicate nella tabella «Stagioni precedenti»
N_SEASONS = 4

#: `transfer_type` della fonte → parola italiana (mai inglese a schermo)
_TRANSFER_TYPE_IT: ClassVar[dict[str, str]] = {
    "contract": "definitivo",
    "on loan": "prestito",
    "loan": "prestito",
    "free": "gratuito",
}


def _news_row(v: dict[str, Any], tz: ZoneInfo) -> dict[str, Any]:
    """Una voce del bollettino `team_news` nella forma piatta che serve al template."""
    when = pd.Timestamp(v["published_at"])
    return {"title": _s(v.get("title")), "url": _s(v.get("url")), "source": _s(v.get("source")),
            "date": when.tz_convert(tz).strftime("%d/%m/%Y"),
            "kind_label": _s(v.get("kind_label")), "why": _s(v.get("why")),
            "published_at": when}


@dataclass
class TeamCatalog:
    """Dati pronti per ``squadre/<id>.html``, calcolati una volta per build.

    Il caricamento dei Parquet è unico: le 132 pagine si costruiscono dalla stessa fotografia
    (stesso istante per tutte), così due squadre non possono mostrare classifiche prese a
    orari diversi.
    """

    store: Any
    analysis: MatchAnalysis | None = None
    players: PlayerCatalog | None = None
    now: pd.Timestamp | None = None
    tz: ZoneInfo = field(default_factory=lambda: ZoneInfo(
        load_leagues_config().get("timezone_display", "Europe/Rome")))

    def __post_init__(self) -> None:
        self.analysis = self.analysis or MatchAnalysis(self.store)
        self.players = self.players or PlayerCatalog(self.store)
        self.now = pd.Timestamp(self.now) if self.now is not None else pd.Timestamp.now(tz="UTC")
        if self.now.tzinfo is None:
            self.now = self.now.tz_localize("UTC")
        self._load()

    # ---- caricamento ------------------------------------------------------------------
    def _load(self) -> None:
        fx = self.analysis.effective_fixtures(self.store.read("fixtures"), now=self.now)
        self.fixtures = fx[fx["status"] != "cancelled"].copy() if not fx.empty else fx
        self.standings = self.store.read("fotmob_standings")
        self.preds = latest_per_match(self.store.read("predictions"))
        self.news = self.store.read("news")
        self.transfers = self.store.read("transfers")
        self.season_sim = self.store.read("season_sim")
        self.history = self.store.read("history")
        self.info = self.store.read("match_info")
        self._leagues = {lg.key: lg for lg in leagues()}
        self._league_of_id = {lg.fotmob_id: lg for lg in leagues()}
        self.league_name = {lg.fotmob_id: lg.name for lg in leagues()}
        # nome pubblico per id: l'ultimo visto nel calendario, come fanno le schede giocatore
        # (le classifiche ESPN/FotMob usano grafie diverse per 18 squadre su 132: il nome che
        # il lettore vede nelle card deve essere lo stesso qui)
        self.team_names = self._names_by_id()
        self.teams = self._team_ids()
        self._season_table = self._build_season_tables()

    def _names_by_id(self) -> dict[int, str]:
        if self.fixtures.empty:
            return {}
        names = pd.concat([
            self.fixtures[["home_id", "home_name", "utc_kickoff"]].rename(
                columns={"home_id": "team_id", "home_name": "name"}),
            self.fixtures[["away_id", "away_name", "utc_kickoff"]].rename(
                columns={"away_id": "team_id", "away_name": "name"}),
        ]).dropna(subset=["team_id"])
        names = names.sort_values("utc_kickoff").drop_duplicates("team_id", keep="last")
        return {int(r.team_id): str(r.name) for r in names.itertuples(index=False)}

    def _team_ids(self) -> list[int]:
        if self.fixtures.empty:
            return []
        ids = set(self.fixtures["home_id"].astype(int)) | set(self.fixtures["away_id"].astype(int))
        return sorted(ids, key=lambda t: (self.league_of(t)[0], self.team_names.get(t, "")))

    def league_of(self, team_id: int) -> tuple[str, str]:
        """(chiave, nome) della lega della squadra, dalla sua gara più recente.

        ``fixtures`` non porta ``league_key``: la chiave arriva da ``league_id`` e dalla
        configurazione, mai da un'euristica sul nome del campionato.
        """
        if self.fixtures.empty:
            return "", ""
        sub = self.fixtures[(self.fixtures.home_id == team_id)
                            | (self.fixtures.away_id == team_id)]
        if sub.empty:
            return "", ""
        lid = int(sub.sort_values("utc_kickoff").iloc[-1]["league_id"])
        lg = self._league_of_id.get(lid)
        return (lg.key, lg.name) if lg else ("", str(lid))

    # ---- blocchi ----------------------------------------------------------------------
    def _finished(self) -> pd.DataFrame:
        if self.fixtures.empty:
            return self.fixtures
        return self.fixtures[self.fixtures["status"] == "finished"]

    @staticmethod
    def _team_matches(fx: pd.DataFrame, team_id: int) -> pd.DataFrame:
        if fx.empty:
            return fx
        return fx[(fx["home_id"] == team_id) | (fx["away_id"] == team_id)]

    def standing(self, team_id: int) -> dict[str, Any] | None:
        """Riga di classifica della squadra (FotMob, riserva ESPN)."""
        st = self.standings
        row = None
        if not st.empty and "team_id" in st.columns:
            sub = st[st["team_id"] == team_id]
            if not sub.empty:
                row = sub.iloc[0].to_dict()
        if row is None:
            row = self._espn_standing(team_id)
        if row is None:
            return None
        played = _int(row.get("played"))
        points = _int(row.get("points"))
        gf, ga = _int(row.get("goals_for")), _int(row.get("goals_against"))
        return {
            "rank": _int(row.get("rank")), "played": played,
            "wins": _int(row.get("wins")), "draws": _int(row.get("draws")),
            "losses": _int(row.get("losses")), "points": points,
            "goals_for": gf, "goals_against": ga,
            "goal_diff": _int(row.get("goal_diff", gf - ga)),
            "ppg": round(points / played, 2) if played else None,
            "gf_pm": round(gf / played, 2) if played else None,
            "ga_pm": round(ga / played, 2) if played else None,
        }

    def _espn_standing(self, team_id: int) -> dict[str, Any] | None:
        """Riserva dichiarata di `docs/00` §F: la classifica ESPN, agganciata per nome canonico.

        Gli id squadra delle due fonti sono diversi (verificato: 306 = Hull City su ESPN,
        id FotMob diverso), quindi il ponte è il nome canonico — mai l'id.
        """
        espn = self.store.read("espn_standings")
        if espn.empty or "team_name" not in espn.columns:
            return None
        name = canonical(self.team_names.get(team_id, ""))
        if not name:
            return None
        sub = espn[espn["team_name"].map(canonical) == name]
        return None if sub.empty else sub.iloc[0].to_dict()

    def splits(self, team_id: int) -> dict[str, dict[str, Any]]:
        """Rendimento casa/trasferta **delle gare finite di questa stagione**."""
        fin = self._team_matches(self._finished(), team_id)
        out: dict[str, dict[str, Any]] = {}
        for side, is_home in (("home", True), ("away", False)):
            part = fin[fin["home_id"] == team_id] if is_home else fin[fin["away_id"] == team_id]
            wins = draws = losses = gf_total = ga_total = 0
            for r in part.itertuples(index=False):
                gf = int(r.home_goals) if is_home else int(r.away_goals)
                ga = int(r.away_goals) if is_home else int(r.home_goals)
                gf_total += gf
                ga_total += ga
                if gf > ga:
                    wins += 1
                elif gf == ga:
                    draws += 1
                else:
                    losses += 1
            played = len(part)
            out[side] = {"played": played, "wins": wins, "draws": draws, "losses": losses,
                         "points": wins * 3 + draws, "goals_for": gf_total,
                         "goals_against": ga_total,
                         "ppg": round((wins * 3 + draws) / played, 2) if played else None}
        return out

    def form(self, team_id: int) -> dict[str, Any] | None:
        """Ultime 5 di campionato: la stessa vista che la scheda partita mostra in testa."""
        rows = self.analysis.form(team_id, self.now, n=N_MATCHES)
        return self.analysis.form_summary(rows) if rows else None

    def _opponent_name(self, match_id: int, team_id: int) -> str:
        """Nome dell'avversaria di ``team_id`` in quella gara, dal calendario."""
        if self.fixtures.empty:
            return ""
        sub = self.fixtures[self.fixtures["match_id"] == match_id]
        if sub.empty:
            return ""
        r = sub.iloc[0]
        return str(r["away_name"] if int(r["home_id"]) == team_id else r["home_name"])

    def _match_row(self, r: Any, team_id: int, built: set[int] | None = None) -> dict[str, Any]:
        kick = pd.Timestamp(r.utc_kickoff)
        is_home = int(r.home_id) == team_id
        finished = str(r.status) == "finished" and pd.notna(r.home_goals) and pd.notna(r.away_goals)
        hg = None if pd.isna(r.home_goals) else int(r.home_goals)
        ag = None if pd.isna(r.away_goals) else int(r.away_goals)
        res = None
        gf = ga = None
        if finished and hg is not None and ag is not None:
            gf, ga = (hg, ag) if is_home else (ag, hg)
            res = "V" if gf > ga else ("N" if gf == ga else "P")
        return {
            "match_id": int(r.match_id), "is_home": is_home,
            "home_name": str(r.home_name), "away_name": str(r.away_name),
            "home_goals": hg, "away_goals": ag,
            "opponent": str(r.away_name) if is_home else str(r.home_name),
            "date_short": kick.tz_convert(self.tz).strftime("%d/%m"),
            "when": it_day_time(kick, self.tz),
            "kickoff": kick.tz_convert(self.tz),
            "finished": finished, "res": res, "gf": gf, "ga": ga,
            # link solo se la scheda partita esiste davvero: un collegamento a una pagina
            # non generata sarebbe un 404, e il gate dei link interni lo fermerebbe
            "link": built is None or int(r.match_id) in built,
        }

    def upcoming(self, team_id: int, n: int = N_MATCHES,
                 built: set[int] | None = None) -> list[dict[str, Any]]:
        """Prossimi impegni di campionato, con la previsione pubblicata (se esiste)."""
        if self.fixtures.empty:
            return []
        fx = self._team_matches(self.fixtures, team_id)
        fx = fx[fx["utc_kickoff"] > self.now]
        fx = fx[fx["status"].isin(["scheduled", "not_started", "postponed", "suspended"])]
        fx = fx.sort_values("utc_kickoff").head(n)
        out = []
        for r in fx.itertuples(index=False):
            row = self._match_row(r, team_id, built)
            row["prediction"] = self._compact_prediction(int(r.match_id))
            out.append(row)
        return out

    def recent(self, team_id: int, n: int = N_MATCHES,
               built: set[int] | None = None) -> list[dict[str, Any]]:
        """Ultime gare concluse, dalla più recente."""
        fin = self._team_matches(self._finished(), team_id).sort_values("utc_kickoff", ascending=False)
        return [self._match_row(r, team_id, built) for r in fin.head(n).itertuples(index=False)]

    def _compact_prediction(self, match_id: int) -> dict[str, Any] | None:
        """1X2, gol attesi e Over 2,5 della previsione pubblicata per quella gara.

        È la stessa riga di ``predictions`` che la scheda partita usa: nessun ricalcolo.
        """
        if self.preds.empty:
            return None
        sub = self.preds[self.preds["match_id"] == match_id]
        if sub.empty:
            return None
        if "made_at" in sub.columns:
            sub = sub.sort_values("made_at")
        r = sub.iloc[-1]
        try:
            ph, pd_, pa = float(r.p_home), float(r.p_draw), float(r.p_away)
        except (TypeError, ValueError):
            return None
        lh = _float(r.get("lambda_home"))
        la = _float(r.get("lambda_away"))
        return {"p_home": ph, "p_draw": pd_, "p_away": pa,
                "lambda_home": lh, "lambda_away": la,
                "over25": _float(r.get("p_over25"))}

    def lineup(self, team_id: int) -> dict[str, Any] | None:
        """Formazione (probabile o ufficiale) dell'impegno più vicino, con la sua etichetta.

        La distinta viene pubblicata a ridosso del calcio d'inizio: senza, il blocco mostra il
        segnaposto onesto invece di una formazione inventata.
        """
        if self.info.empty:
            return None
        info = self.info
        info = info[(info["home_id"] == team_id) | (info["away_id"] == team_id)]
        if info.empty:
            return None
        upcoming = info[info["utc_kickoff"] > self.now].sort_values("utc_kickoff")
        if not upcoming.empty:
            match = upcoming.iloc[0]
            kind = "probabile" if str(match.get("lineup_type", "")).lower() in {"predicted", ""} else "ufficiale"
        else:
            past = info[info["utc_kickoff"] <= self.now].sort_values("utc_kickoff", ascending=False)
            if past.empty:
                return None
            match = past.iloc[0]
            kind = "ultima gara"
        mid = int(match["match_id"])
        is_home = int(match["home_id"]) == team_id
        starters = self.analysis.starters(mid, team_id)
        formation = match.get("home_formation") if is_home else match.get("away_formation")
        if not starters and (formation is None or pd.isna(formation)):
            return None
        # `match_info` non porta i nomi: arrivano dal calendario, la stessa riga che
        # pubblica il nome della squadra nel resto del sito.
        opponent = self._opponent_name(mid, team_id)
        return {"match_id": mid, "kind": kind, "formation": None if pd.isna(formation) else str(formation),
                "opponent": opponent, "is_home": is_home,
                "when": it_day_time(pd.Timestamp(match["utc_kickoff"]), self.tz),
                "starters": starters}

    def unavailable(self, team_id: int) -> list[dict[str, Any]]:
        """Indisponibili come li pubblica la scheda partita (tipo e rientro tradotti).

        Prende l'ultima distinta raccolta per la squadra — la più vicina a oggi — e non
        l'unione di tutte le gare: chi è rientrato non deve restare in infermeria perché una
        fotografia di settembre lo elencava. Il tipo e il rientro passano dalle stesse
        funzioni della scheda (`unavailability_it`, `_return_it`).
        """
        lu = self.analysis.lineup
        if lu.empty:
            return []
        un = lu[(lu["team_id"] == team_id) & (lu["role"] == "unavailable")]
        if un.empty:
            return []
        kick = (self.fixtures.drop_duplicates("match_id").set_index("match_id")["utc_kickoff"]
                if not self.fixtures.empty else pd.Series(dtype="datetime64[ns, UTC]"))
        un = un.assign(_ko=un["match_id"].map(kick))
        last_match = un.sort_values("_ko").iloc[-1]["match_id"]
        un = un[un["match_id"] == last_match]
        out = []
        for r in un.sort_values("market_value_eur", ascending=False, na_position="last").itertuples(index=False):
            out.append({"name": str(r.player_name),
                        "type": _unavail_it(getattr(r, "unavailability_type", None)),
                        "ret": _return_it(getattr(r, "expected_return", None)),
                        "value": _float(getattr(r, "market_value_eur", None))})
        return out

    def squad(self, team_id: int) -> tuple[list[dict], list[dict]]:
        """Rosa della squadra: stessa riga pubblica del tabellone di lega."""
        return self.players.team_rows(team_id)

    def market(self, team_id: int) -> dict[str, Any] | None:
        """Ultimi movimenti di mercato della squadra, con importo leggibile in italiano."""
        tr = self.transfers
        if tr.empty or "team_id" not in tr.columns:
            return None
        sub = tr[tr["team_id"] == team_id].copy()
        if sub.empty:
            return None
        sub["date_parsed"] = pd.to_datetime(sub.get("date"), utc=True, errors="coerce")
        sub = sub.sort_values("date_parsed", ascending=False, na_position="last")
        # La fonte ripete la stessa voce con timestamp diversi (Ehizibue 03/09 e 04/09):
        # la stessa operazione pubblicata due volte non è due operazioni.
        chiave = ["player_name", "direction", "counterpart", "fee_text", "transfer_type"]
        if set(chiave) <= set(sub.columns):
            sub = sub.drop_duplicates(subset=chiave, keep="first")

        def rows(direction: str) -> list[dict[str, Any]]:
            part = sub[sub["direction"] == direction].head(N_MOVES)
            return [{"name": str(r.player_name), "counterpart": _s(r.counterpart),
                     "fee": MatchAnalysis.fee_it(getattr(r, "fee_text", None)),
                     "type": _TRANSFER_TYPE_IT.get(str(getattr(r, "transfer_type", "")).lower(),
                                                   _s(getattr(r, "transfer_type", None))),
                     "date": (pd.Timestamp(r.date_parsed).strftime("%d/%m/%Y") if pd.notna(r.date_parsed) else None)}
                    for r in part.itertuples(index=False)]

        return {"arrivi": rows("in"), "partenze": rows("out"),
                "n_in": int((sub["direction"] == "in").sum()),
                "n_out": int((sub["direction"] == "out").sum())}

    def headlines(self, team_id: int, n: int = N_NEWS) -> dict[str, Any]:
        """Le notizie della squadra in italiano, con la loro provenienza dichiarata.

        Due livelli, mai mescolati in silenzio:

        1. **bollettino** — :meth:`MatchAnalysis.team_news`, la stessa selezione della scheda
           partita (lingua italiana verificata sul titolo, categorie, valore, soggetto, dedup),
           con finestra di 30 giorni. Qui però togliamo infortuni, squalifiche e mercato: la
           pagina ha già le card «Indisponibili» e «Mercato», e ripetere lo stesso fatto in due
           punti è il difetto che `docs/00` §F vieta;
        2. **rassegna** — se il bollettino non ha nulla (succede a 90 squadre su 132: il gate del
           segnale è pensato per la vigilia, non per una pagina che vive tutto l'anno), si
           ripiega sulle ultime voci italiane raccolte con i filtri di base: lingua, soggetto,
           categoria, valore editoriale, niente Primavera/femminile. La pagina dice che è una
           rassegna più larga, senza far passare per «bollettino» ciò che non lo è.

        Il ritorno è ``{"items": [...], "fallback": bool}``: il secondo campo esiste perché la
        nota in pagina possa essere vera. La versione precedente filtrava da sola il campo
        ``language``, che per due titoli ESPN era vuoto: «January» e «10.10.2026» sono arrivati
        fino al verificatore, che li ha fermati come «inglese» e «decimale col punto».
        """
        empty = {"items": [], "fallback": False}
        if self.analysis is None or self.news.empty or "team_id" not in self.news.columns:
            return empty
        name = self.team_names.get(team_id)
        if not name:
            return empty
        bollettino = self.analysis.team_news(team_id, name, self.now, days=30,
                                             limit=n + 3, now=self.now)
        out: list[dict[str, Any]] = []
        for v in bollettino.get("notizie", []):
            if str(v.get("topic_label") or "").lower() in {"infortuni", "squalifiche", "mercato"}:
                continue
            out.append(_news_row(v, self.tz))
            if len(out) >= n:
                break
        if out:
            return {"items": out, "fallback": False}
        # ripiego: stessi filtri di base della scheda partita, applicati a tutte le voci raccolte
        from ..sources.news import (
            classify_news,
            club_nel_titolo,
            is_italian_news,
            news_value,
            soggetto_tokens,
        )

        toks = soggetto_tokens(name)
        sub = self.news[self.news["team_id"] == team_id].copy()
        sub = sub.assign(published=pd.to_datetime(sub.get("published_at"), utc=True, errors="coerce"))
        sub = sub.dropna(subset=["published"]).sort_values("published", ascending=False)
        visti: set[str] = set()
        for r in sub.itertuples(index=False):
            title = _s(getattr(r, "title", None))
            url = _s(getattr(r, "url", None))
            desc = _s(getattr(r, "description", None))
            if not title or not url.startswith("http") or not is_italian_news(title, desc):
                continue
            if toks and not club_nel_titolo(title, toks):
                continue
            if _NEWS_ALTRO.search(title) or _NEWS_JUNK.search(title):
                continue
            topic = classify_news(title, desc, getattr(r, "source", None))[0]
            if topic is None or topic in self.analysis.NEWS_ALTROVE:
                continue
            if news_value(title, desc, getattr(r, "source", None)):
                continue
            key = title.strip().lower()
            if key in visti:
                continue
            visti.add(key)
            out.append({"title": title, "url": url, "source": _s(getattr(r, "source", None)),
                        "date": pd.Timestamp(r.published).tz_convert(self.tz).strftime("%d/%m/%Y"),
                        "kind_label": "", "why": "", "published_at": pd.Timestamp(r.published)})
            if len(out) >= n:
                break
        return {"items": out, "fallback": bool(out)}

    def projection(self, team_id: int) -> dict[str, Any] | None:
        """Titolo, UCL e retrocessione: le stesse cifre della pagina Proiezioni.

        Le percentuali passano da :func:`mc_percent_str`, la funzione che stampa la colonna
        «1º»/«Retro» di ``stagione.html``: così il gate [54] può confrontare le due pagine
        come stringhe, senza replicare l'arrotondamento.
        """
        from ..models.season_sim import mc_percent_str

        sim = self.season_sim
        if sim.empty or "team" not in sim.columns:
            return None
        name = canonical(self.team_names.get(team_id, ""))
        sub = sim[sim["team"].map(canonical) == name]
        if sub.empty:
            return None
        r = sub.iloc[0]
        raw_top = r.get("p_top_n")
        if raw_top is None or pd.isna(raw_top):
            raw_top = r.get("p_top4")
        top_n = r.get("top_n")
        return {
            "p_title_pct": mc_percent_str(float(r.p_title)),
            "p_top_n_pct": None if raw_top is None or pd.isna(raw_top) else mc_percent_str(float(raw_top)),
            "p_rel_pct": mc_percent_str(float(r.p_rel)),
            "top_n": None if top_n is None or pd.isna(top_n) else int(top_n),
            "pos_mean": round(float(r.pos_mean), 1),
            "exp_points": round(float(r.exp_points), 1),
            "n_sims": _int(r.get("n_sims")) or None,
            "played": _int(r.get("played")),
            "points": _int(r.get("points")),
        }

    # ---- storico ----------------------------------------------------------------------
    def _build_season_tables(self) -> dict[tuple[str, str], pd.Series]:
        """Punti per squadra e (lega, stagione) dallo storico: serve al rango di stagione.

        Una passata sola sull'archivio (7.532 gare): il rango di una stagione passata è
        calcolato sui **punti di quella stagione**, non sulla posizione di oggi.
        """
        h = self.history
        if h.empty or not {"league_key", "season", "home", "away", "home_goals", "away_goals"} <= set(h.columns):
            return {}
        pts: dict[tuple[str, str, str], int] = {}
        for r in h.itertuples(index=False):
            hg, ag = int(r.home_goals), int(r.away_goals)
            for name, gf, ga in ((str(r.home), hg, ag), (str(r.away), ag, hg)):
                key = (str(r.league_key), str(r.season), canonical(name))
                pts[key] = pts.get(key, 0) + (3 if gf > ga else 1 if gf == ga else 0)
        table: dict[tuple[str, str, str], int] = {}
        for (lg, season, team), p in pts.items():
            table[(lg, season, team)] = p
        ranks: dict[tuple[str, str], pd.Series] = {}
        df = pd.Series(table, dtype="int64")
        df.index.names = ["league_key", "season", "team"]
        for (lg, season), grp in df.groupby(level=[0, 1]):
            ranks[(str(lg), str(season))] = grp.droplevel([0, 1]).sort_values(ascending=False)
        return ranks

    def season_history(self, team_id: int) -> list[dict[str, Any]]:
        """Ultime stagioni dell'archivio: punti, posizione finale e gol."""
        h = self.history
        if h.empty or "season" not in h.columns:
            return []
        name = canonical(self.team_names.get(team_id, ""))
        if not name:
            return []
        sub = h[(h["home"].map(canonical) == name) | (h["away"].map(canonical) == name)]
        if sub.empty:
            return []
        current = str(load_leagues_config().get("season", ""))
        out = []
        for season, grp in sub.groupby("season"):
            points = wins = draws = losses = gf = ga = 0
            for r in grp.itertuples(index=False):
                is_home = canonical(str(r.home)) == name
                f, a = (int(r.home_goals), int(r.away_goals)) if is_home else (int(r.away_goals), int(r.home_goals))
                gf, ga = gf + f, ga + a
                wins += f > a
                draws += f == a
                losses += f < a
                points += 3 if f > a else 1 if f == a else 0
            lg = str(grp["league_key"].iloc[0]) if "league_key" in grp.columns else ""
            rank = None
            table = self._season_table.get((lg, str(season)))
            if table is not None and name in table.index:
                rank = int(list(table.index).index(name) + 1)
            out.append({"season": str(season), "played": len(grp), "points": points,
                        "wins": int(wins), "draws": int(draws), "losses": int(losses),
                        "goals_for": gf, "goals_against": ga, "rank": rank,
                        "in_corso": str(season) == current})
        out.sort(key=lambda x: x["season"], reverse=True)
        return out[:N_SEASONS]

    # ---- assemblaggio -----------------------------------------------------------------
    def page(self, team_id: int, built: set[int] | None = None) -> dict[str, Any]:
        """Dizionario completo per il template della pagina squadra.

        ``built`` sono gli id delle schede partita realmente generate: solo quelle diventano
        link. Senza l'insieme, i link sono dichiarati validi (uso nei test).
        """
        key, name = self.league_of(team_id)
        lg = self._leagues.get(key)
        squad_rows, bench = self.squad(team_id)
        news = self.headlines(team_id)
        return {
            "team_id": team_id,
            "name": self.team_names.get(team_id, str(team_id)),
            "league_key": key, "league_name": name,
            "league_code": lg.espn_code if lg else None,
            "standing": self.standing(team_id),
            "splits": self.splits(team_id),
            "form": self.form(team_id),
            "next": (self.upcoming(team_id, 1, built) or [None])[0],
            "upcoming": self.upcoming(team_id, built=built),
            "recent": self.recent(team_id, built=built),
            "lineup": self.lineup(team_id),
            "unavailable": self.unavailable(team_id),
            "squad": {"rows": squad_rows, "bench": bench},
            "market": self.market(team_id),
            "news": news["items"], "news_fallback": news["fallback"],
            "projection": self.projection(team_id),
            "history": self.season_history(team_id),
        }

    def league_blocks(self) -> list[dict[str, Any]]:
        """Squadre raggruppate per campionato, per l'indice ``squadre/index.html``."""
        blocks = []
        for lg in leagues():
            teams = [t for t in self.teams if self.league_of(t)[0] == lg.key]
            if not teams:
                continue
            rows = []
            for t in teams:
                st = self.standing(t) or {}
                rows.append({"team_id": t, "name": self.team_names.get(t, str(t)),
                             "rank": st.get("rank"), "points": st.get("points"),
                             "played": st.get("played")})
            rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 99, r["name"]))
            blocks.append({"key": lg.key, "name": lg.name, "teams": rows})
        return blocks


# --------------------------------------------------------------------------- helper
def _float(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _int(v: Any) -> int:
    f = _float(v)
    return int(f) if f is not None else 0


def _s(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v).strip()
    return t or None


def _unavail_it(value: Any) -> str:
    from .analysis import unavailability_it
    return unavailability_it(value)


def _return_it(value: Any) -> str | None:
    from .analysis import _return_it as conv
    return conv(value) if isinstance(value, str) else None
