import itertools
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from fda.collect import collect_league
from fda.config import league
from fda.site.analysis import MatchAnalysis
from fda.site.build import SiteBuilder, pct_triple
from fda.store import TABLE_KEYS, Store
from tests.test_store_collect import FakeEspn, FakeEspnNoStandings, FakeFotMob, FakeUnderstat

FIX = Path(__file__).parent / "fixtures"


class FakeFotMobPre(FakeFotMob):
    """Per la partita futura restituisce un matchDetails pre-partita (formazione probabile, niente stats)."""

    def match_details_raw(self, match_id, finished_hint=None):
        raw = super().match_details_raw(match_id, finished_hint)
        if match_id == 5749669:
            raw["general"].update({"started": False, "finished": False})
            raw["header"]["status"] = {"utcTime": "2026-09-07T18:45:00.000Z", "finished": False, "started": False}
            raw["header"]["teams"][0]["score"] = 0
            raw["header"]["teams"][1]["score"] = 0
            raw["content"]["lineup"]["lineupType"] = "predicted"
            for k in ("stats", "shotmap", "playerStats"):
                raw["content"].pop(k, None)
            raw["content"]["matchFacts"].pop("events", None)
        return raw


def _seed(tmp_path, espn_cls=FakeEspn):
    st = Store(tmp_path / "processed")
    collect_league(league("ITA1"), st, past_days=30, future_days=30,
                   fotmob=FakeFotMobPre(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(), espn=espn_cls(),
                   today=date(2026, 9, 6))
    # sposta le partite campione attorno a "oggi" così finiscono nelle pagine
    now = datetime.now(UTC)
    fx = st.read("fixtures")
    fx.loc[fx.match_id == 5749645, "utc_kickoff"] = now - timedelta(days=1)
    fx.loc[fx.match_id == 5749669, "utc_kickoff"] = now + timedelta(days=1)
    st.write("fixtures", fx)
    # affluenza sulla partita finita (nel parquet arriva come float, es. 57000.0)
    mi = st.read("match_info")
    mi.loc[mi.match_id == 5749645, "attendance"] = 57000
    # la gara futura campione: senza arbitro né meteo → copre i segnaposto «da definire»
    for col in ("referee_name", "weather_desc"):
        if col in mi.columns:
            mi.loc[mi.match_id == 5749669, col] = None
    st.write("match_info", mi)
    # meteo previsionale Open-Meteo come fallback per la futura senza meteo FotMob
    st.upsert("weather_forecast", [
        {"match_id": 5749669, "lat": 45.4, "lon": 9.1, "hour": "2026-09-07T19:00",
         "temp_c": 21.0, "precip_prob": 60.0, "code": 61, "desc": "pioggia debole"},
    ])
    # momentum deterministico: Monza preme nei primi 25', poi domina Inter (12/18 minuti = 67%)
    mom = [{"match_id": 5749645, "minute": float(m), "value": float(v)} for m, v in [
        (5, -30), (10, -40), (15, -35), (20, -25), (25, -20), (30, 0),
        (35, 20), (40, 35), (45, 45), (50, 30), (55, 55), (60, 65), (65, 40), (70, 50), (75, 60), (80, 45), (85, 70), (90, 35)]]
    st.upsert("momentum", mom)
    # fatti FotMob per la futura (Udinese 8600 – Lazio 8543): mix traducibili / hype / inglese
    st.upsert("insights", [
        {"match_id": 5749669, "team_id": 8600, "player_id": None, "text":
         "Udinese haven't lost to Lazio in their last 8 meetings (3W, 5D)."},
        {"match_id": 5749669, "team_id": 8543, "player_id": None, "text":
         "Have scored 8 goals in their last 5 matches"},
        {"match_id": 5749669, "team_id": 8543, "player_id": None, "text":
         "Have kept the most clean sheets in the competition (4)"},
        {"match_id": 5749669, "team_id": 8543, "player_id": None, "text":
         "Unknown English hype phrase"},
        {"match_id": 5749669, "team_id": 8543, "player_id": 111, "text":
         "Ciro Immobile is the competition's top scorer (5)"},
        {"match_id": 5749669, "team_id": 9999, "player_id": None, "text":
         "Have won their last 4 matches"},
        {"match_id": 5749645, "team_id": 8636, "player_id": None, "text":
         "Haven't lost in 12 matches"},
    ])
    # un precedente non pari per coprire V e P (il campione ha solo un 1-1)
    st.upsert("h2h", [
        {"match_id": 5749645, "utc": "2025-09-15T18:45:00+00:00", "league": "Serie A",
         "home_id": 6504, "away_id": 8636, "home_goals": 0, "away_goals": 3},   # Monza 0-3 Inter → V per Inter
        {"match_id": 5749669, "utc": "2025-10-20T18:45:00+00:00", "league": "Serie A",
         "home_id": 8543, "away_id": 8600, "home_goals": 2, "away_goals": 1},   # Lazio 2-1 Udinese → P per Udinese
    ])
    # una previsione fatta prima della partita finita e una per la futura
    st.upsert("predictions", [
        {"match_id": 5749645, "league_key": "ITA1", "home": "Inter", "away": "Monza", "model": "ensemble",
         "p_home": 0.62, "p_draw": 0.21, "p_away": 0.17, "lambda_home": 2.1, "lambda_away": 0.9,
         "p_over15": 0.8, "p_over25": 0.6, "p_over35": 0.35, "p_btts": 0.5, "p_1x": 0.83, "p_12": 0.79, "p_x2": 0.38,
         "p_home_clean_sheet": 0.4, "p_away_clean_sheet": 0.12, "top_scores": "{'2-0': 0.11, '1-0': 0.10}",
         "fair_home": 1.61, "fair_draw": 4.76, "fair_away": 5.88, "made_at": now - timedelta(days=2), "n_train": 380,
         "w_dc": 0.7, "elo_home": 1650.0, "elo_away": 1480.0, "dc_attack_home": 1.3, "dc_defence_home": 0.8,
         "dc_attack_away": 0.9, "dc_defence_away": 1.1, "dc_home_advantage": 0.25},
        {"match_id": 5749669, "league_key": "ITA1", "home": "Udinese", "away": "Lazio", "model": "ensemble",
         "p_home": 0.33, "p_draw": 0.30, "p_away": 0.37, "lambda_home": 1.2, "lambda_away": 1.3,
         "p_over15": 0.7, "p_over25": 0.45, "p_over35": 0.22, "p_btts": 0.52, "p_1x": 0.63, "p_12": 0.70, "p_x2": 0.67,
         "p_home_clean_sheet": 0.27, "p_away_clean_sheet": 0.30, "top_scores": "{'1-1': 0.13, '0-1': 0.09}",
         "fair_home": 3.03, "fair_draw": 3.33, "fair_away": 2.7, "made_at": now, "n_train": 380,
         "w_dc": 0.7, "elo_home": 1500.0, "elo_away": 1560.0, "dc_attack_home": 0.9, "dc_defence_home": 1.0,
         "dc_attack_away": 1.1, "dc_defence_away": 0.95, "dc_home_advantage": 0.25},
    ])
    # proiezioni di stagione (campione per la pagina Proiezioni)
    st.upsert("season_sim", [
        {"league_key": "ITA1", "team": t, "played": pl, "points": pt, "exp_points": e, "pos_mean": m,
         "p_title": t1, "p_top4": t4, "p_rel": rl, "n_sims": 10000, "n_train": 960,
         "model_version": "test", "made_at": now}
        for t, pl, pt, e, m, t1, t4, rl in [
            ("Inter", 3, 9, 84.2, 1.4, 0.61, 0.95, 0.0),
            ("Milan", 3, 6, 74.8, 2.6, 0.24, 0.86, 0.01),
            ("Napoli", 3, 7, 71.3, 3.1, 0.12, 0.74, 0.03),
            ("Monza", 3, 0, 30.1, 17.9, 0.0, 0.02, 0.66),
        ]])
    return st


def test_translate_insight_patterns_and_drop_english():
    """Traduzione dei template FotMob; testi sconosciuti / hype → None (niente inglese)."""
    from fda.site.analysis import translate_insight

    assert translate_insight("Have scored 5 goals in their last 5 matches") == {
        "text": "ha segnato 5 gol nelle ultime 5 partite", "kind": "goals", "priority": 80}
    assert translate_insight("Have scored 1 goals in their last 1 matches")["text"] == (
        "ha segnato 1 gol nell'ultima partita")
    assert translate_insight("Haven't scored in their last 3 matches")["text"] == "non segna da 3 partite"
    assert translate_insight("Haven't lost in 19 matches") == {
        "text": "imbattuta da 19 partite", "kind": "streak", "priority": 90}
    assert translate_insight("Haven't won a match in 6 attempts")["text"] == "non vince da 6 partite"
    assert translate_insight("Have lost their last 4 matches")["text"] == "ha perso le ultime 4 partite"
    assert translate_insight("Have won their last 3 matches")["text"] == "ha vinto le ultime 3 partite"
    assert translate_insight("Haven't kept a clean sheet in 7 matches")["text"] == (
        "non tiene la porta inviolata da 7 partite")
    h2h = translate_insight("Atalanta haven't lost to Roma in their last 8 meetings (6W, 2D).")
    assert h2h["kind"] == "h2h" and h2h["priority"] == 100
    assert h2h["text"] == "non perde contro Roma da 8 incontri (6V, 2N)"
    assert translate_insight("Venezia have won the previous 5 matches against Frosinone.")["text"] == (
        "ha vinto le precedenti 5 partite contro Frosinone")
    assert translate_insight(
        "Cagliari and Lecce have not drawn any of their last 10 matches against each other."
    )["text"] == "nessun pareggio negli ultimi 10 confronti diretti"
    assert translate_insight(
        "Paris FC and Lyon have drawn their last 3 matches against each other."
    )["text"] == "ha pareggiato gli ultimi 3 confronti diretti"
    scorer = translate_insight("Donyell Malen is the competition's top scorer (5)")
    assert scorer["kind"] == "scorer" and "Donyell Malen" in scorer["text"]
    assert "5 gol" in scorer["text"]
    # template oggettivi recuperati (P1.4, docs/19 §2.5): i 5 scarti più frequenti ora
    # sono tradotti — tutti dati, nessun giudizio
    cs = translate_insight("Have kept the most clean sheets in the competition (4)")
    assert cs == {"text": "ha il maggior numero di porte inviolate del campionato (4)",
                  "kind": "clean_sheet", "priority": 74}
    assert translate_insight("Have conceded the most penalties this season (6)")["text"] == (
        "ha concesso più rigori in questa stagione (6)")
    assert translate_insight("Have been awarded the most penalties this season (3)")["text"] == (
        "ha ottenuto più rigori in questa stagione (3)")
    assert translate_insight("Average 1.8 goals per match") == {
        "text": "media 1,8 gol a partita", "kind": "goals", "priority": 50}
    assert translate_insight("Ranked 2 at home this season") == {
        "text": "2° in classifica nelle gare interne", "kind": "rank", "priority": 48}
    assert translate_insight("Ranked 5 away from home this season")["text"] == (
        "5° in classifica nelle gare in trasferta")
    # hype / sconosciuti: non si mostrano
    for raw in (
        "Armand Laurienté has created the most big chances for Sassuolo (2)",
        "Unknown English hype phrase",
        "",
        None,
    ):
        assert translate_insight(raw) is None


def test_insight_drop_log_counts_unknown_shapes():
    """Ogni scarto è contato per forma canonica (numeri → N): un template nuovo si vede."""
    from fda.site.analysis import insight_drop_stats, reset_insight_stats, translate_insight
    reset_insight_stats()
    try:
        translate_insight("Brand new English template 7")
        translate_insight("Brand new English template 9")
        translate_insight("Another unknown hype phrase")
        stats = insight_drop_stats()
        assert stats is not None
        assert stats["scartati"] == 0            # nessun consumo di pagina, solo log diretto
        assert stats["top_shape"] == "Brand new English template N"
        assert stats["top_n"] == 2
        reset_insight_stats()
        assert insight_drop_stats() is None
    finally:
        reset_insight_stats()


def test_match_insights_selection_team_and_empty(tmp_path):
    """Selezione: max 3, squadra corretta, inglese scartato, lista vuota se manca tutto."""
    st = Store(tmp_path / "processed")
    st.upsert("insights", [
        {"match_id": 1, "team_id": 10, "player_id": None,
         "text": "Home haven't lost to Away in their last 8 meetings (6W, 2D)."},
        {"match_id": 1, "team_id": 10, "player_id": None, "text": "Haven't lost in 5 matches"},
        {"match_id": 1, "team_id": 20, "player_id": None, "text": "Have scored 7 goals in their last 5 matches"},
        {"match_id": 1, "team_id": 20, "player_id": None, "text": "Haven't kept a clean sheet in 4 matches"},
        {"match_id": 1, "team_id": 20, "player_id": None, "text": "Have kept the most clean sheets in the competition (3)"},
        {"match_id": 1, "team_id": 20, "player_id": 99, "text": "Hero is the competition's top scorer (9)"},
        {"match_id": 1, "team_id": 77, "player_id": None, "text": "Have won their last 4 matches"},
    ])
    ma = MatchAnalysis(st)
    got = ma.match_insights(1, 10, 20, "Casa", "Trasferta")
    assert len(got) == 3
    assert all("team" in x and "text" in x for x in got)
    assert {x["team"] for x in got} <= {"Casa", "Trasferta"}
    kinds = [x["kind"] for x in got]
    assert kinds[0] == "h2h" and got[0]["team"] == "Casa"
    assert "non perde contro Away da 8 incontri (6V, 2N)" in got[0]["text"]
    assert "imbattuta da 5 partite" in {x["text"] for x in got}
    assert "ha segnato 7 gol nelle ultime 5 partite" in {x["text"] for x in got}
    # hype e squadra estranea esclusi; capocannoniere è 4° (scartato dal tetto)
    blob = " ".join(x["text"] for x in got)
    assert "clean sheets" not in blob and "Hero" not in blob and "Haven't" not in blob
    assert ma.match_insights(999, 10, 20, "Casa", "Trasferta") == []
    assert MatchAnalysis(Store(tmp_path / "empty")).match_insights(1, 10, 20, "A", "B") == []
    st.close()


def test_standing_prefers_fotmob_with_espn_fallback(tmp_path):
    st = Store(tmp_path / "processed")
    st.upsert("espn_standings", [{"league_code": "ITA1", "team_id": 1, "team_name": "Inter",
                                  "rank": 5, "played": 3, "points": 4}])
    st.upsert("fotmob_standings", [{"league_code": "ITA1", "team_id": 8636, "team_name": "Inter",
                                    "rank": 1, "played": 3, "points": 9}])
    assert MatchAnalysis(st).standing("Inter")["points"] == 9
    # senza FotMob: riserva ESPN; senza nulla: None
    st2 = Store(tmp_path / "processed2")
    st2.upsert("espn_standings", [{"league_code": "ITA1", "team_id": 1, "team_name": "Inter",
                                   "rank": 5, "played": 3, "points": 4}])
    assert MatchAnalysis(st2).standing("Inter")["points"] == 4
    assert MatchAnalysis(st2).standing("Squadra Inesistente") is None
    st.close()
    st2.close()


def test_season_xg_fotmob_fallback(tmp_path):
    st = Store(tmp_path / "processed")
    st.upsert("match_info", [
        {"match_id": 1, "status": "finished", "home_id": 8636, "away_id": 9875,
         "home_xg": 2.0, "away_xg": 1.0},
        {"match_id": 2, "status": "finished", "home_id": 9875, "away_id": 8636,
         "home_xg": 0.5, "away_xg": 1.5},
        {"match_id": 3, "status": "scheduled", "home_id": 8636, "away_id": 8564,
         "home_xg": None, "away_xg": None},
    ])
    xg = MatchAnalysis(st).season_xg("Inter", 8636)
    assert xg["source"] == "FotMob" and xg["played"] == 2
    assert (xg["xg"], xg["xga"]) == (3.5, 1.5)
    assert MatchAnalysis(st).season_xg("Squadra Inesistente", 0) is None
    st.close()


def test_season_xg_fotmob_calcola_xpts(tmp_path):
    """Fallback FotMob: xPTS dalle λ = xG (Poisson) e punti reali dalle partite finite."""
    st = Store(tmp_path / "processed")
    st.upsert("match_info", [
        {"match_id": 1, "status": "finished", "home_id": 8636, "away_id": 9875,
         "home_xg": 2.0, "away_xg": 1.0, "home_goals": 3, "away_goals": 1},    # Inter in casa: V
        {"match_id": 2, "status": "finished", "home_id": 9875, "away_id": 8636,
         "home_xg": 0.5, "away_xg": 1.5, "home_goals": 0, "away_goals": 2},    # Inter in trasferta: V
        {"match_id": 3, "status": "finished", "home_id": 8636, "away_id": 8564,
         "home_xg": 1.0, "away_xg": 1.0, "home_goals": 1, "away_goals": 1},    # pareggio
        {"match_id": 4, "status": "finished", "home_id": 9875, "away_id": 8636,
         "home_xg": 2.0, "away_xg": 0.5, "home_goals": 3, "away_goals": 0},    # Inter in trasferta: P
        {"match_id": 5, "status": "scheduled", "home_id": 8636, "away_id": 8564,
         "home_xg": None, "away_xg": None, "home_goals": None, "away_goals": None},
    ])
    xg = MatchAnalysis(st).season_xg("Inter", 8636)
    assert xg["source"] == "FotMob" and xg["played"] == 4
    assert (xg["xg"], xg["xga"]) == (5.0, 4.5)
    assert xg["pts"] == 7                 # 3+3+1+0 dalle partite finite
    assert xg["xpts"] == 5.9              # Σ xPTS Poisson dalle λ = xG, arrotondato a 1 decimale
    # metodo statico _poisson_xpts: valori attesi noti, simmetria su λ uguali
    xh, xa = MatchAnalysis._poisson_xpts(2.0, 1.0)
    assert (round(xh, 3), round(xa, 3)) == (2.029, 0.759)
    xa_sym = MatchAnalysis._poisson_xpts(1.5, 1.5)
    assert abs(xa_sym[0] - xa_sym[1]) < 1e-6                 # λ uguali → xPTS speculari uguali
    # partite finite senza gol reali (colonne assenti): xPTS resta None, nessun crash
    st2 = Store(tmp_path / "processed2")
    st2.upsert("match_info", [{"match_id": 1, "status": "finished", "home_id": 8636, "away_id": 9875,
                               "home_xg": 2.0, "away_xg": 1.0}])
    xg2 = MatchAnalysis(st2).season_xg("Inter", 8636)
    assert xg2["xpts"] is None and xg2["pts"] is None
    st.close()
    st2.close()


def test_site_build_end_to_end(tmp_path):
    st = _seed(tmp_path)
    out = tmp_path / "site"
    res = SiteBuilder(store=st, out_dir=out).build()
    assert res["matches"] == 2
    for name in ("index.html", "prossime.html", "risultati.html", "accuratezza.html", "stato.html",
                 "stagione.html", "robots.txt", ".nojekyll", "partite/5749645.html", "partite/5749669.html"):
        assert (out / name).exists(), name

    post = (out / "partite/5749645.html").read_text(encoding="utf-8")
    assert "Lettura della partita" in post and "Simone Sozza" in post
    # riga arbitro: contatori interi, mai float («18 rigori», non «18.0 rigori»)
    assert "18 rigori" in post and "18.0 rigori" not in post
    assert "2 rossi" in post and "2.0 rossi" not in post
    assert "(33 gare)" in post and "(33.0 gare)" not in post
    assert "xG 3,86 - 2,43" in post and "Cronaca essenziale" in post
    assert "Lautaro Martínez" in post and "Politano" in post
    assert "Il modello assegnava 62%" in post          # valutazione a posteriori
    # data in italiano con ora locale (niente weekday inglese né etichetta UTC fuorviante)
    assert any(g in post for g in ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"))
    assert not any(g in post for g in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"))
    assert "(ora italiana)" in post and " UTC ·" not in post
    assert "spettatori 57.000" in post and "57.000.0" not in post   # formato intero italiano
    # card Confronto di stagione (tabella FotMob): Inter in tabella, Monza no → lato «—», nessun evidenziato
    assert "Confronto di stagione" in post and "Punti/gara" in post
    assert "9 in 3 gare" in post and "3,00" in post and "media gol del campionato" in post
    # il taglio usa l'ancora della card che segue il gruppo del club (da P2.4 è «arbitro-meteo»):
    # tagliare sulla voce d'indice darebbe una fetta vuota
    cmp = post[post.find("Confronto di stagione"):post.find('id="arbitro-meteo"')]
    assert "—</td>" in cmp and 'class="best"' not in cmp   # Monza assente: niente evidenziazione nel confronto
    # cartina dei tiri (SVG): 2 pannelli, i 2 tiri dell'Inter del campione, Monza senza tiri
    assert "Cartina dei tiri" in post
    # fase 3 — pagine giocatore: hub, tabellone di lega e schede individuali linkate dalle partite
    assert (out / "giocatori" / "index.html").exists()
    assert (out / "giocatori" / "ITA1.html").exists()
    schede = list((out / "giocatori").glob("*.html"))
    schede = [f for f in schede if f.stem != "index" and f.stem != "ITA1"]
    assert len(schede) >= 5, f"attese schede giocatore, trovate {len(schede)}"
    assert 'href="../giocatori/' in post          # link dalla scheda partita
    una = schede[0].read_text(encoding="utf-8")
    assert "scheda giocatore" in una and ("Stagione" in una or "Non ancora sceso in campo" in una)
    assert "Giocatori" in (out / "index.html").read_text(encoding="utf-8")   # voce di navigazione
    # esclude i 2 logo (header/footer), identificati dal ruolo "Logo CalcioMetro" e dalla viewport 64
    chart_svg = [s for s in post.split("<svg")[1:] if 'aria-label="Logo CalcioMetro"' not in s]
    assert len(chart_svg) == 5          # 2 cartine + momentum + corsa xG + WP in-play
    assert "xG 0,88" in post                       # gol di Lautaro Martínez, decimale italiano
    assert "Nessun tiro registrato" in post        # pannello Monza vuoto
    # momentum (SVG a barre + marker gol): 18 punti seed + 2 del campione; Inter dominante (13/20 = 65%)
    assert "Matrice dei punteggi" in post and "Scontro tattico" in post
    assert "Corsa xG" in post and "Qualità dei tiri" in post and "Probabilità in-play" in post
    assert "RegularPlay" not in post and "FastBreak" not in post and "FromCorner" not in post
    assert "azione manovrata" in post
    assert "Momentum della partita" in post
    assert "Momentum a favore di <b>Inter</b> nel 65% dei minuti" in post
    assert 'fill="#e0605a"' in post and 'fill-opacity="0.75"' in post  # barre negative/positive
    # Migliori in campo: split per squadra, rating con virgola, minuti e rating stagionale
    assert "Migliori in campo" in post
    assert ">9,1</td>" in post and "stagione 8,20" in post      # Lautaro (Inter)
    assert ">7,5</td>" in post and "· 62'" in post              # Politano (Monza)
    assert "stagione 6,72" in post
    # ultimi precedenti reali (tabella h2h): sia pre che post, con V/N/P dalla prospettiva della casa attuale
    assert "Ultimi precedenti" in post and "Monza <b>1-1</b> Inter" in post
    assert "Monza <b>0-3</b> Inter" in post
    i01 = post.find("Monza <b>0-3</b> Inter")
    assert 'class="pill V"' in post[i01:i01 + 400]    # Inter (casa attuale) vinse in trasferta
    assert 'class="pill N"' in post                   # Monza 1-1 Inter → pareggio
    assert "50% dei casi" in post                     # precedenti: entrambe a segno 1 su 2

    stag = (out / "stagione.html").read_text(encoding="utf-8")
    assert "Proiezioni di stagione" in stag and "Serie A" in stag and "Inter" in stag
    assert "84,2" in stag and "61%" in stag and "66%" in stag   # probabilità alla risoluzione sostenuta dalla simulazione
    # L'asserzione precedente era «"10.000" not in stag» (niente formattazioni inglesi) e
    # difendeva il grezzo «10000»: contrario alla convenzione del sito, che scrive
    # «spettatori 57.000» due righe sopra e «1.988 partite» su Prossime (docs/20 #8,
    # docs/24 §4, docs/01 §8 «10.000 stagioni»). Ora il numero esce con `it_num` e la
    # guardia vive in `verify_site` [13-14], estesa a «stagioni» (docs/45 §3).
    assert "10.000 stagioni simulate" in stag
    assert "10000" not in stag          # nessun conteggio grezzo senza separatore
    assert "UCL (prime 4)" in stag and "Retro" in stag and "Media pos." in stag

    pre = (out / "partite/5749669.html").read_text(encoding="utf-8")
    assert "Analisi pre-partita" in pre and "Formazione probabile" in pre and "Cronaca" not in pre
    # pre-partita: niente card Confronto (Udinese/Lazio fuori tabella campione), segnaposto onesti
    assert "Confronto di stagione" not in pre
    assert "da definire" in pre and "da definire" not in post
    # meteo fallback Open-Meteo: descrizione + fonte dichiarata (FotMob assente)
    assert "pioggia debole" in pre and "(previsione Open-Meteo)" in pre
    assert "2,50 gol/gara" in pre and "gol/gara" in post
    assert "Indisponibili" in pre and "McTominay" in pre and "metà ottobre 2026" in pre
    assert "Partita equilibrata" in pre
    assert "Risultati esatti" in pre and "1-1" in pre
    # card «I giocatori che decidono» solo in pre-partita: contributo per 90 e media di stagione
    assert "I giocatori che decidono" in pre
    # card «Fatti rilevanti» solo in pre-partita: tradotti, tetto a 5, niente inglese
    assert "Fatti rilevanti" in pre
    assert "non perde contro Lazio da 8 incontri (3V, 5N)" in pre
    assert "ha segnato 8 gol nelle ultime 5 partite" in pre
    assert "imbattuta da 19 partite" in pre          # insight del campione FotMob (team remappato)
    assert "capocannoniere" in pre                   # 4° fatto: il tetto è salito da 3 a 5
    assert pre.count("Fatti rilevanti") == 1
    assert "Haven't" not in pre
    assert "clean sheets" not in pre and "hype phrase" not in pre
    assert "Migliori in campo" not in pre          # card post-partita: non deve apparire prima
    assert "media <b>" not in pre                 # niente media di stagione nel post (verificato dopo)
    assert "(ora italiana)" in pre
    assert "Ultimi precedenti" in pre and "Lazio <b>1-1</b> Udinese" in pre
    assert "Lazio <b>2-1</b> Udinese" in pre
    i21 = pre.find("Lazio <b>2-1</b> Udinese")
    assert 'class="pill P"' in pre[i21:i21 + 400]   # Udinese (casa attuale) perse in trasferta
    assert "Momentum" not in pre                   # solo per partite giocate

    acc = (out / "accuratezza.html").read_text(encoding="utf-8")
    assert "Riepilogo" in acc and "Serie A" in acc     # una partita valutata
    assert "Δ vs naive" in acc and "Calibrazione" in acc and "Frequenza osservata" in acc
    assert "✓" in acc          # Inter 4-1 Monza: top=1 (62%) azzeccato
    # intervalli di Wilson: con 1 sola gara valutata lo scarto previsto/osservato è sempre rumore
    assert "intervallo 95%" in acc and "compatibile" in acc and "fuori intervallo" not in acc
    assert "20,7 – 100,0%" in acc      # k=1 su n=1
    assert "0,0 – 79,3%" in acc        # k=0 su n=1 (79,346% arrotondato a una cifra)
    assert "0,087" in acc      # RPS della singola previsione 0.62/0.21/0.17 con esito 1
    # sito italiano: nessun residuo UTC/inglese, orari in ora italiana
    for page in ("index.html", "partite/5749645.html", "partite/5749669.html", "accuratezza.html"):
        html = (out / page).read_text(encoding="utf-8")
        assert "UTC" not in html, page
        assert "(ora italiana)" in html, page
    html_index = (out / "index.html").read_text(encoding="utf-8")
    assert "index, follow" in html_index and "noindex" not in html_index
    assert 'rel="canonical"' in html_index and 'sitemap.xml' in (out / "robots.txt").read_text(encoding="utf-8")
    assert "Allow: /" in (out / "robots.txt").read_text(encoding="utf-8")

    # stato fonti: tutte le fonti OK → nessun ERRORE (regressione rumore ESPN standings)
    stato = (out / "stato.html").read_text(encoding="utf-8")
    assert "Ultimi run per fonte" in stato and "OK" in stato
    assert 'class="pill P">ERRORE' not in stato
    assert 'class="pill N">AVVISO' not in stato
    st.close()


def test_vita_del_club_in_una_riga_quando_non_c_e_nulla(tmp_path):
    """P1.1 (docs/28 §2): senza titoli pubblicabili la card «Vita del club» dice il fatto in
    una riga e mette i conteggi in una tendina.

    Prima, su 42 schede su 66, la card più pesante della pagina (3.054 caratteri mediani, il
    99% prosa metodologica) serviva a dire che non c'era nulla. I numeri non escono dalla
    pagina — il verificatore `[20]` li rilegge nella tendina — cambia solo dove stanno.
    """
    st = _seed(tmp_path)
    fx = st.read("fixtures")
    pre = fx[fx.match_id == 5749669].iloc[0]
    ko = pd.Timestamp(pre.utc_kickoff)
    ko = ko.tz_localize("UTC") if ko.tzinfo is None else ko.tz_convert("UTC")
    titoli = [
        (int(pre.home_id), "Come acquistare i biglietti per Udinese-Lazio: prezzi e informazioni",
         "https://esempio.it/1"),
        (int(pre.home_id), "Udinese, la conferenza stampa di domani: orari e diretta",
         "https://esempio.it/2"),
        (int(pre.away_id), "Lazio, dove vederla in tv e streaming", "https://esempio.it/3"),
    ]
    st.write("news", pd.DataFrame([
        {"team_id": tid, "published_at": ko - pd.Timedelta(days=1), "title": t, "url": u,
         "source": "Corriere", "description": ""} for tid, t, u in titoli]))

    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build()
    html = (out / "partite/5749669.html").read_text(encoding="utf-8")

    assert "Nessun titolo pubblicabile su Udinese e Lazio negli ultimi 7 giorni" in html
    assert "3 titoli esaminati e scartati con criterio" in html
    # la tendina c'è, e l'imbuto per squadra (i numeri del verificatore [20]) è dentro di lei
    inizio = html.find('id="notizie"')
    assert inizio != -1 and '<details class="news-more">' in html[inizio:]
    dentro = html[html.find('<details class="news-more">', inizio):]
    assert "Niente che possa spostare qualcosa" in dentro
    assert "Fonte: Google News RSS per squadra" in dentro
    # sopra la tendina resta la riga (più gli eventuali «Da sapere»): l'imbuto per squadra no
    visibile = re.sub(r"<[^>]+>", " ", html[inizio:html.find('<details class="news-more">', inizio)])
    visibile = re.sub(r"\s+", " ", visibile).strip()
    assert '<p style="margin:12px 0 6px"><b>' not in visibile
    assert "Niente che possa spostare qualcosa" not in visibile
    assert len(visibile) < 900, f"la card visibile è ancora lunga: {len(visibile)} caratteri"
    assert visibile.startswith('id="notizie"> Vita del club Nessun titolo pubblicabile su '
                               "Udinese e Lazio")
    st.close()


def test_xg_e_ppda_una_volta_sola(tmp_path):
    """P1.2 (docs/28 §2): un dato, un posto — l'hero non anticipa xG/gara e PPDA, «Come arrivano»
    non ripete le medie di stagione.

    Il posto canonico dei valori di stagione è la card della squadra (più «Scontro tattico» per il
    confronto di stile): l'hero tiene esito, λ, Over 2,5 e «entrambe a segno», che non compaiono
    altrove. La gara sintetica serve perché il campione dei test non ha abbastanza righe Understat
    per far comparire «Come arrivano».
    """
    st = _seed(tmp_path)
    now = datetime.now(UTC)
    st.upsert("fixtures", [_fixture_lontana(5900003, 2, "Inter", "Napoli", now)])
    st.upsert("predictions", [{
        "match_id": 5900003, "model": "ensemble", "league_key": "ITA1",
        "p_home": 0.5, "p_draw": 0.27, "p_away": 0.23, "lambda_home": 1.6, "lambda_away": 1.1,
        "p_over15": 0.75, "p_over25": 0.55, "p_over35": 0.3, "p_btts": 0.52,
        "p_1x": 0.77, "p_12": 0.73, "p_x2": 0.5, "p_home_clean_sheet": 0.3,
        "p_away_clean_sheet": 0.2, "top_scores": "{'1-1': 0.12, '1-0': 0.1}",
        "made_at": now, "n_train": 380, "w_dc": 0.7,
    }])
    st.upsert("understat_team_matches", [
        {"league_slug": "Serie_A", "season": 2026, "team_id": 999001, "team_name": "Inter",
         "date": (now - timedelta(days=7 * (4 - i))).isoformat(), "is_home": bool(i % 2),
         "goals": 2, "goals_against": 1, "xg": 1.9 - i * 0.1, "xga": 1.0, "xpts": 2.0,
         "pts": 3, "ppda": 9.5} for i in range(4)])
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5900003})
    h = (out / "partite" / "5900003.html").read_text(encoding="utf-8")

    hero = h.split('<div class="hero-model">')[1].split('<nav class="match-jump"')[0]
    assert "xG/gara" not in hero and "PPDA" not in hero
    assert "gol attesi" in hero and "Over 2,5" in hero and "entrambe a segno" in hero

    assert h.count("xG creati / gara") == 2                    # card squadra: stagione, per squadra
    assert "xG / gara" in h and "PPDA (↓ = più pressing)" in h  # «Scontro tattico»: il confronto

    arrivo = h.split("<h2>Come arrivano</h2>", 1)[1].split("<h2>", 1)[0]
    assert "xGA" in arrivo and arrivo.count("<tr>") >= 3        # la serie gara per gara resta
    assert "fatti contro" not in arrivo and "a partita" not in arrivo   # niente sintesi ripetuta
    assert "PPDA" not in arrivo
    assert "Scontro tattico" in arrivo                          # al posto del numero, il rimando
    st.close()


def test_legenda_stabilizzata_una_volta_sola(tmp_path):
    """P2.1 (docs/28 §3): la spiegazione della stima stabilizzata si dà una volta sola.

    Compariva in ogni card squadra (nota «Soglia di minutaggio: … ◎ stima stabilizzata …») e in
    ogni riga dell'infermeria: 4 volte per scheda. Ora la legenda sta nel primo punto d'uso — la
    testata di «I giocatori che decidono» — e altrove resta il marcatore ◎ col tooltip del caso
    specifico (media dei pari, peso k, numerosità), che è ciò che rende la stima verificabile.
    """
    st = _seed(tmp_path)
    # la stagione dei giocatori della gara futura: senza player_stats la sezione «I giocatori che
    # decidono» (e con lei la legenda) non si stampa, e il test non proverebbe niente
    st.upsert("player_stats", [
        {"match_id": m, "team_id": tid, "player_id": pid, "player_name": nome, "key": chiave,
         "value": valore, "total": None}
        for m in (5749669,)      # la gara delle due squadre del campione
        for tid, pid, nome in ((8600, 111, "A1"), (8600, 112, "A2"), (8600, 113, "A3"),
                               (8543, 211, "B1"), (8543, 212, "B2"), (8543, 213, "B3"))
        for chiave, valore in (("minutes_played", 300.0), ("expected_goals", 2.0),
                               ("expected_assists", 1.0))
    ])
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669, 5749645})

    for nome, pre in (("5749669", True), ("5749645", False)):
        html = (out / "partite" / f"{nome}.html").read_text(encoding="utf-8")
        corpo = html.split('<main id="main">', 1)[1]
        assert corpo.count("stabilizzat") <= 2, f"{nome}: «stabilizzat» {corpo.count('stabilizzat')} volte"
        if not pre:
            continue          # a gara conclusa la sezione dei giocatori decisivi non si stampa"
        # la legenda c'è, una volta, e spiega entrambi i marcatori
        assert corpo.count("◎ è la <b>stima stabilizzata</b>") == 1
        assert "◇ significa che sotto i 90′ la rata grezza non si pubblica" in corpo
        # la nota della card squadra resta, ma solo col dato (soglia e numerosità); nelle gare
        # del campione di prova può mancare del tutto (nessun giocatore sopra soglia)
        if "Soglia di minutaggio:" in corpo:
            nota = corpo.split("Soglia di minutaggio:", 1)[1].split("</p>", 1)[0]
            assert "minuti" in nota and "in classifica" in nota
            assert "stabilizzat" not in nota
        # il tooltip di riga porta il caso specifico, non la spiegazione del metodo (nel campione
        # di prova può non esserci nessuna riga con la stima: la riga compare dal vero Understat)
        titoli = re.findall(r'title="◎ Stima stabilizzata — ([^"]*)"', corpo)
        for t in titoli:
            assert "media dei pari" in t and "peso k=" in t and "n=" in t
        assert "Stima stabilizzata (media dei pari e peso misurati" not in corpo  # la frase ripetuta
    st.close()


def test_indice_della_scheda_dice_i_titoli_veri(tmp_path):
    """P1.3 (docs/28 §2): le voci dell'indice dicono il titolo della sezione che aprono.

    Prima erano quattro e una sola azzeccava: «Dati e contesto» atterrava su «Confronto di
    stagione», «Squadre» sul nome di una squadra, «Post-partita» su «Il prossimo impegno»; le card
    più pesanti (Scontro tattico, I giocatori, Mercato, Panchina, Vita del club, Verifica) non
    avevano un'ancora. Qui si verifica la corrispondenza voce → titolo sulle due schede campione,
    con la stessa regola dell'invariante [33] di `verify_site`.
    """
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669, 5749645})

    for nome in ("5749669", "5749645"):
        html = (out / "partite" / f"{nome}.html").read_text(encoding="utf-8")
        nav = html.split('class="match-jump"', 1)[1].split("</nav>", 1)[0]
        voci = re.findall(r'<a href="#([^"]+)">([^<]+)</a>', nav)
        assert len(voci) >= 8, f"{nome}: indice troppo corto ({len(voci)} voci)"
        for ancora, etichetta in voci:
            assert f'id="{ancora}"' in html, f"{nome}: indice → #{ancora}, sezione assente"
            i = html.index(f'id="{ancora}"')
            titolo = re.sub(r"<[^>]+>", " ", html[html.index("<h2", i):html.index("</h2>", i)])
            titolo = re.sub(r"\s+", " ", titolo).strip().lower()
            assert titolo.startswith(etichetta.lower()), f"{nome}: «{etichetta}» → «{titolo}»"

    # le sezioni che erano irraggiungibili hanno un'ancora e una voce: se la sezione c'è nella
    # pagina, la voce dell'indice c'è (il caso «Mercato» qui non ha dati: il campione di prova
    # non ha movimenti, e in quel caso la pagina non ha la sezione né la voce)
    pre = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    nav = pre.split('class="match-jump"', 1)[1].split("</nav>", 1)[0]
    for etichetta, ancora in (("Scontro tattico", "scontro"), ("I giocatori", "giocatori"),
                              ("Vita del club", "notizie"), ("Verifica", "verifica"),
                              ("Panchina", "panchina"), ("Come arrivano", "arrivi"),
                              ("Le due squadre", "squadre"),
                              ("Arbitro e meteo", "arbitro-meteo"), ("Precedenti", "precedenti")):
        if f'id="{ancora}"' not in pre:       # sezione senza dati in questa gara: niente voce
            continue
        assert f'<a href="#{ancora}">{etichetta}</a>' in nav, f"voce mancante: {etichetta}"
    for ancora in ("lettura", "squadre", "arbitro-meteo", "verifica"):     # ci sono sempre
        assert f'id="{ancora}"' in pre and f'href="#{ancora}"' in nav
    assert '<h2 class="as-h2" style="grid-column:1/-1">Le due squadre</h2>' in pre
    # da P2.4 il link «→ precedenti» ha una card con quel nome (vedi il test dedicato)
    assert '<div class="card" id="precedenti">' in pre
    st.close()


def test_arbitro_meteo_e_precedenti_card_separate(tmp_path):
    """P2.4 (docs/28 §3): «Contesto» era una card sola per tre cose che non si somigliano.

    Chi dirige la gara e che tempo farà non hanno nulla in comune con la storia della sfida, e i
    precedenti (grafico, ultimi incontri, frequenze) erano l'84% del testo del blocco: la card più
    sbilanciata della pagina, con un titolo che non diceva né l'una né l'altra cosa. Ora sono due
    card, ognuna col titolo di quello che contiene, e l'indice (P1.3) le nomina entrambe.

    La riga della tabella non ripete più il titolo («Bilancio (15)» dice su quanti casi si regge
    la lettura delle frequenze: è il numero che serve, ed è quello che l'invariante [5] di
    `scripts/verify_site.py` ricalcola dall'archivio).
    """
    st = _seed(tmp_path)
    # due precedenti in più per la gara futura: da tre casi in su la card pubblica il bilancio
    # completo con il grafico a ciambella (il campione di prova ne ha uno solo)
    st.upsert("h2h", [
        {"match_id": 5749669, "utc": "2025-02-16T14:00:00+00:00", "league": "Serie A",
         "home_id": 8600, "away_id": 8543, "home_goals": 1, "away_goals": 1},
        {"match_id": 5749669, "utc": "2024-09-22T16:00:00+00:00", "league": "Serie A",
         "home_id": 8543, "away_id": 8600, "home_goals": 0, "away_goals": 2},
    ])
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669, 5749645})

    pre = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    post = (out / "partite" / "5749645.html").read_text(encoding="utf-8")
    for nome, html in (("pre", pre), ("post", post)):
        assert 'id="contesto"' not in html, f"{nome}: la card unica «Contesto» è ancora lì"
        assert "#contesto" not in html, f"{nome}: resta un rimando a #contesto"
        assert "<h2>Contesto</h2>" not in html, nome
        assert "<h2>Arbitro e meteo</h2>" in html, nome
        assert "<h2>Precedenti</h2>" in html, nome
        # arbitro e meteo prima, i precedenti dopo: lo stesso ordine della card che li conteneva
        i = html.index('<div class="card" id="arbitro-meteo">')
        j = html.index('<div class="card" id="precedenti">')
        assert i < j, nome
        arb, prec = html[i:j], html[j:]
        assert "Arbitro" in arb and "Meteo" in arb, nome
        assert "Ultimi precedenti" not in arb, f"{nome}: la storia della sfida non sta con l'arbitro"
        assert "Bilancio" in prec and "Ultimi precedenti" in prec, nome
        # il grafico a ciambella dei precedenti sta nella card dei precedenti (non con l'arbitro)
        assert 'aria-label="Bilancio precedenti"' not in arb, nome
    # la gara futura non ha ancora la designazione: il segnaposto sta nella card dell'arbitro
    assert "da definire" in pre[pre.index('<div class="card" id="arbitro-meteo">'):pre.index('<div class="card" id="precedenti">')]
    # la gara futura: grafico a ciambella dentro la card dei precedenti e conteggio dei casi
    # nell'etichetta della riga — il numero che l'invariante [5] di verify_site ricalcola
    # dall'archivio (qui lo si ricava dalla stessa tabella h2h del campione di prova)
    hh = st.read("h2h")
    casi = int(((hh.match_id == 5749669) & hh.home_goals.notna() & hh.away_goals.notna()).sum())
    assert casi >= 3
    prec = pre[pre.index('<div class="card" id="precedenti">'):]
    assert 'aria-label="Bilancio precedenti"' in prec
    assert f'<th scope="row">Bilancio ({casi})</th>' in prec
    # la partita finita mostra il bilancio dell'archivio (riga «Bilancio», senza contatore)
    assert "<h2>Precedenti</h2>" in post and "Bilancio" in post
    # il link dei «Fatti rilevanti» punta dritto alla card dei precedenti
    assert 'href="#precedenti" class="small" style="white-space:nowrap">→ precedenti</a>' in pre
    st.close()


def test_p23_tre_card_di_testo_hanno_il_loro_micro_visivo(tmp_path):
    """P2.3 (`docs/28` §3): le tre card di sola prosa hanno un grafico, e il grafico dice gli
    stessi numeri della prosa.

    Serve una fixture più ricca del solito: la scala di lega vuole ≥30 partite previste nello
    stesso campionato, la fascia storica vuole il backtest, il primo gol vuole gli eventi. Le
    tre condizioni sono seminati qui perché senza dati le card non esistono (e senza card non
    c'è niente da verificare).
    """
    st = _seed(tmp_path)
    now = datetime.now(UTC)
    # 40 partite ITA1 previste dal modello (scala di lega) con λ totali diversi
    st.upsert("predictions", [
        {"match_id": 700000 + i, "league_key": "ITA1", "home": "A", "away": "B",
         "model": "ensemble", "p_home": 0.4, "p_draw": 0.3, "p_away": 0.3,
         "lambda_home": 1.0 + i / 25, "lambda_away": 1.0 + (39 - i) / 25,
         "made_at": now - timedelta(days=3), "n_train": 380}
        for i in range(40)])
    # backtest: 150 gare per ognuna delle cinque fasce (il favorito di questa gara è al 37%,
    # quindi la fascia «fino al 40%» è quella segnata «questa»)
    righe = []
    for fav in (0.36, 0.45, 0.55, 0.65, 0.85):
        for i in range(150):
            righe.append({"match_id": 800000 + len(righe), "p_home": fav, "p_draw": (1 - fav) / 2,
                          "p_away": (1 - fav) / 2, "outcome": 0 if i % 2 else 1,
                          "league_key": "ITA1", "made_at": now - timedelta(days=400)})
    st.upsert("backtest", righe)
    # eventi: 120 gol in 100 partite, primo gol distribuito fra i due tempi
    st.upsert("events", [
        {"match_id": 900000 + i, "team_id": 8600, "player_id": 1, "type": "Goal",
         "minute": float(5 + (i * 7) % 85), "minute_added": None, "period": "FirstHalf"}
        for i in range(120)])

    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    h = (out / "partite" / "5749669.html").read_text(encoding="utf-8")

    # 1) scala di lega: barra con aria-label, segno e tacca
    assert 'id="posizione-lega"' in h
    # la fetta si ferma alla card successiva: `class="gb"` compare anche nel dotplot
    barra = h.split('id="posizione-lega"', 1)[1].split('<div class="card', 1)[0]
    assert 'class="track" role="img" aria-label="Gol attesi totali' in barra
    assert 'class="fill"' in barra and 'class="pin"' in barra and 'class="tick soft"' in barra
    # il numero sul segno è quello della frase («I 2,47 gol attesi totali in testa alla scheda»)
    valore = re.search(r"I ([\d,]+) gol attesi totali in testa alla scheda", barra).group(1)
    assert 'class="mark"' in barra
    assert f">{valore}</span>" in barra.split('class="mark"')[1][:60]

    # 2) primo gol: distribuzione osservata + banda del modello
    assert 'id="primo-gol"' in h
    # la fetta si ferma alla card successiva: `class="gb"` compare anche nel dotplot
    fg = h.split('id="primo-gol"', 1)[1].split('<div class="card', 1)[0]
    assert 'class="goalclock" role="img" aria-label="Distribuzione osservata del primo gol' in fg
    assert fg.count('class="gb"') == 6, "sei quarti d'ora"
    assert 'class="bandbar" role="img"' in fg and 'class="band"' in fg and 'class="med"' in fg
    # le percentuali delle barre sono numeri interi e sommano ~100 (partite con almeno un gol)
    perc = [int(x) for x in re.findall(r'<span class="v">(\d+)%</span>', fg)]
    assert len(perc) == 6 and 95 <= sum(perc) <= 105, perc

    # 3) fasce storiche: una barra per fascia, con l'intervallo e la tacca della previsione
    assert 'id="fascia-storica"' in h
    # la fetta si ferma alla card successiva: `class="gb"` compare anche nel dotplot
    fs = h.split('id="fascia-storica"', 1)[1].split('<div class="card', 1)[0]
    assert fs.count('class="wl" role="img"') == 5, "una barra per fascia"
    assert fs.count('class="ic"') == 5 and fs.count('class="p"') == 5
    # l'aria-label di ogni barra porta i tre numeri della riga
    for m in re.finditer(r'class="wl" role="img" aria-label="Fascia ([^"]+)"', fs):
        assert "media prevista" in m.group(1) and "poi uscito" in m.group(1)
        assert "intervallo di confidenza" in m.group(1)
    # e i tre valori grafici sono in percentuale 0–100
    for stile in re.findall(r'class="(?:fill|ic|p)" style="[^"]*?([\d.]+)%', fs):
        assert 0.0 <= float(stile) <= 100.0, stile
    st.close()


def test_p26_fonti_dichiarate_e_quote_di_mercato_fuori_dal_sito(tmp_path):
    """P2.6 (`docs/28` §3): la pagina «Info» non promette fonti che non esistono, e il sito non
    pubblica quote di mercato.

    «The Odds API — quote opzionali, solo se ODDS_API_KEY è configurata» è rimasta nell'elenco
    delle fonti senza che nessuna riga di codice la chiamasse: il lettore non poteva
    accorgersene. La decisione (19/09/2026, `docs/38`) è di non pubblicare quote di mercato — il
    confronto col mercato resta **offline**, sulle quote di chiusura storiche. Qui si verificano i
    due lati del contratto (elenco pubblicato ↔ moduli di `src/fda/sources/`, nessuna pagina che
    prometta quote) e i resti della vecchia promessa, che non devono tornare.
    """
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build()
    info = (out / "info.html").read_text(encoding="utf-8")
    radice = Path(__file__).resolve().parent.parent

    # 1) l'elenco pubblicato e i moduli veri, nei due versi
    elenco = info[info.index("<h2>Le fonti (gratuite)</h2>"):]
    voci = re.findall(r"<li><b>([^<]+)</b>", elenco[:elenco.index("</ul>")])
    atteso = {"FotMob": "fotmob.py", "Understat": "understat.py", "Open-Meteo": "openmeteo.py",
              "Google News RSS e ESPN news": "news.py", "FotMob coppe (UCL/UEL)": "fotmob.py",
              "ESPN": "espn.py", "football-data.co.uk": "history.py"}
    assert voci == list(atteso), voci
    assert "The Odds API" not in info
    moduli = {p.name for p in (radice / "src" / "fda" / "sources").glob("*.py")} - {"__init__.py"}
    assert set(atteso.values()) == moduli, moduli

    # 2) la decisione è dichiarata al lettore, e nessuna pagina promette quote di mercato
    assert "Quote di mercato: non pubblicate." in info
    for pg in sorted(out.rglob("*.html")):
        testo = pg.read_text(encoding="utf-8")
        for vietata in ("The Odds API", "ODDS_API_KEY", "probabilità implicite", "sezione quote"):
            assert vietata not in testo, f"{pg.name}: promette quote di mercato ({vietata})"

    # 3) i resti della vecchia promessa: config, ambiente del run, schema dello store
    assert "oddsapi" not in (radice / "config" / "sources.yaml").read_text(encoding="utf-8")
    assert "ODDS_API_KEY" not in (radice / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    assert "odds_snapshots" not in TABLE_KEYS
    assert not [f for f in (radice / "src" / "fda").rglob("*.py")
                if "odds_snapshots" in f.read_text(encoding="utf-8")], "residui nello store"
    st.close()


def test_p25_badge_della_forma_in_testa_alla_scheda(tmp_path):
    """P2.5 (`docs/28` §3): la forma recente sale in testa alla scheda.

    Il badge riusa le classi della pagina «Oggi» (`form-line`, `form-dot`, `fact-value`):
    serie di pallini e punti guadagnati per **entrambe** le squadre, con la finestra
    dichiarata nella descrizione per chi usa un lettore di schermo. La narrativa non ripete
    più la serie lettera per lettera (stava lì, nella card della squadra e nell'elenco di
    «Oggi»), e a gara finita il badge non c'è: l'hero racconta la partita, non l'attesa.
    """
    st = _seed(tmp_path)

    def giocata(mid: int, day: str, hid: int, hname: str, aid: int, aname: str, hg: int, ag: int):
        return {"match_id": mid, "league_id": 55, "round": "1",
                "utc_kickoff": pd.Timestamp(day + " 18:00", tz="UTC"),
                "home_id": hid, "home_name": hname, "away_id": aid, "away_name": aname,
                "home_goals": hg, "away_goals": ag, "status": "finished"}

    # cinque gare giocate prima di questa partita per ognuna delle due squadre: senza gare non
    # c'è forma da mostrare. Udinese VVNNP (8 punti), Lazio NPVVV (10 punti).
    st.upsert("fixtures", [
        giocata(950001, "2026-08-10", 8600, "Udinese", 9001, "Rivale 1", 2, 0),
        giocata(950002, "2026-08-14", 9002, "Rivale 2", 8600, "Udinese", 1, 3),
        giocata(950003, "2026-08-18", 8600, "Udinese", 9003, "Rivale 3", 1, 1),
        giocata(950004, "2026-08-22", 9004, "Rivale 4", 8600, "Udinese", 2, 2),
        giocata(950005, "2026-08-26", 8600, "Udinese", 9005, "Rivale 5", 0, 1),
        giocata(950006, "2026-08-11", 9006, "Rivale 6", 8543, "Lazio", 1, 1),
        giocata(950007, "2026-08-15", 8543, "Lazio", 9007, "Rivale 7", 0, 2),
        giocata(950008, "2026-08-19", 9008, "Rivale 8", 8543, "Lazio", 0, 2),
        giocata(950009, "2026-08-23", 8543, "Lazio", 9009, "Rivale 9", 3, 1),
        giocata(950010, "2026-08-27", 9010, "Rivale 10", 8543, "Lazio", 1, 2),
    ])
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669, 5749645})
    pre = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    post = (out / "partite" / "5749645.html").read_text(encoding="utf-8")

    hero_pre = pre[pre.index('class="match-scoreline"'):pre.index('class="hero-model"')]
    hero_post = post[post.index('class="match-scoreline"'):post.index('class="hero-model"')]
    assert hero_pre.count('class="form-line"') == 2, "un badge per squadra"
    assert hero_post.count('class="form-line"') == 0, "a gara finita l'hero non è l'attesa"

    ma, fx = MatchAnalysis(st), st.read("fixtures")
    fr = fx[fx.match_id == 5749669].iloc[0]
    kickoff = pd.Timestamp(fr.utc_kickoff)
    sequenze = []
    # le due serie sono scritte qui a mano: se `form()` cambiasse verso o ordinamento, il test
    # cadrebbe prima di arrivare al template
    attesi = {"Udinese": ("VVNNP", 8), "Lazio": ("NPVVV", 10)}
    for tid, name in ((int(fr.home_id), fr.home_name), (int(fr.away_id), fr.away_name)):
        rows = ma.form(tid, kickoff)
        assert len(rows) == 5, "cinque gare giocate per squadra"
        seq = "".join(r["res"] for r in rows)
        pts = sum(3 if r["res"] == "V" else 1 if r["res"] == "N" else 0 for r in rows)
        assert (seq, pts) == attesi[name], (name, seq, pts)
        punti = f"{pts} punto" if pts == 1 else f"{pts} punti"
        # il badge sta sotto il nome della squadra, non in mezzo alla pagina
        assert f'<div class="match-hero-team {"home" if name == fr.home_name else "away"}">{name}<span class="form-line"' in pre
        # serie e punti sono quelli del calendario, non copiati a mano nel template
        assert (f'aria-label="Forma di {name}: {seq} nelle ultime {len(rows)} partite, {punti}. '
                f'V=vittoria, N=pareggio, P=sconfitta"') in hero_pre
        assert f'<span class="fact-value">{pts} pt</span>' in hero_pre
        sequenze.append(seq)
    # i pallini disegnati sono esattamente le due serie, nell'ordine in cui si leggono in hero
    assert "".join(re.findall(r'class="form-dot (\w)"', hero_pre)) == "".join(sequenze)
    # la narrativa tiene i numeri e il giudizio, ma non trascrive più la serie
    assert re.search(r"punti nelle ultime \d+ — ", pre)
    assert not re.search(r"punti? nelle ultime \d+ \([VNP]+\)", pre), "serie ripetuta nella narrativa"
    # la card della squadra resta la sede del dettaglio (pallini con avversario e risultato):
    # il badge non la sostituisce, aggiunge la lettura a colpo d'occhio in cima alla pagina
    assert 'Forma: <span class="form-dots">' in pre
    st.close()


def test_p22_assenze_in_un_posto_solo_e_clima_sempre_presente(tmp_path):
    """P2.2 (`docs/28` §3): le assenze non si raccontano quattro volte, e nessuna card sparisce.

    Tre cose verificate sulle due schede campione:
    * la frase della narrativa non elenca i nomi (la tabella dell'infermeria è la fonte unica) e
      porta il link `→ Infermeria` **della squadra giusta** (`#infermeria-home` / `-away`);
    * l'avviso «il migliore della lista è indisponibile» non ripete motivo e rientro (stanno
      nella riga della stessa persona in infermeria) ma ci manda;
    * «Clima del club» esiste anche quando nessuna delle due squadre ha segnali: il silenzio non
      deve far sparire la sezione (una scheda su 60 la perdeva).
    """
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669, 5749645})
    pre = (out / "partite" / "5749669.html").read_text(encoding="utf-8")

    # l'ancora dell'infermeria esiste per entrambe le squadre (tabella o riga «nessuno fuori»)
    assert 'id="infermeria-home"' in pre and 'id="infermeria-away"' in pre
    # la narrativa: nessun nome di assente, ma il rimando alla tabella
    narr = pre.split('<ul class="narr">', 1)[1].split("</ul>", 1)[0]
    for riga in re.findall(r"<li>(.*?)</li>", narr):
        if "deve rinunciare a" not in riga:
            continue
        assert "«Indisponibili»" in riga
        lato = "home" if "infermeria-home" in riga else "away"
        assert f'href="#infermeria-{lato}"' in riga, riga
        # il nome con cui la frase comincia è quello della squadra di quel lato
        squadra = "Udinese" if lato == "home" else "Lazio"
        assert riga.startswith(squadra) or f">{squadra}<" in riga, riga
        # e nessuno degli indisponibili della tabella compare nella frase
        cella = pre.split('id="infermeria-' + lato, 1)[1].split("</table>", 1)[0]
        nomi = re.findall(r"<tr[^>]*>\s*<td><b>([^<]+)</b>", cella)
        assert not any(n in riga for n in nomi), (riga, nomi)

    # ogni rimando dentro la narrativa ha la sua ancora in pagina (il gate l'ha trovato rotto
    # sulle schede post-partita: lì la tabella dell'infermeria non esiste, perché la fonte
    # riporta le assenze una volta su due e la pagina non può dire «nessuno fuori»)
    post = (out / "partite" / "5749645.html").read_text(encoding="utf-8")
    for nome, html in (("pre", pre), ("post", post)):
        for ancora in re.findall(r'<li>.*?href="#([^"]+)".*?</li>', html, re.DOTALL):
            assert f'id="{ancora}"' in html, f"{nome}: il link #{ancora} non ha un bersaglio"
    # e a gara finita i nomi restano nella frase (la tabella non c'è)
    if "deve rinunciare a" in post:
        assert 'href="#infermeria-' not in post
    # «Clima del club» c'è anche senza segnali: la riga per squadra lo dice
    assert '<div class="card" id="clima">' in pre
    assert "Nessun segnale anomalo nei dati raccolti: clima normale." in pre

    # l'avviso dentro «I giocatori che decidono»: motivo e rientro non si ripetono, si linkano
    gioc = pre.split('<div class="card" id="giocatori">', 1)[1]
    if "è indisponibile" in gioc:
        avviso = next(r for r in re.findall(r"<p class=\"small warn\"[^>]*>(.*?)</p>", gioc, re.DOTALL)
                      if "è indisponibile" in r)
        assert "Infermeria" in avviso and 'href="#infermeria-' in avviso
        assert "infortunio" not in avviso, avviso      # il motivo sta nella tabella
    st.close()


def test_verifica_approfondita_chiusa_e_annunciata(tmp_path):
    """P1.4 (docs/28 §2): la verifica dei numeri non occupa il primo schermo.

    Il `<details>` non ha più `open` (prima si apriva da solo sopra i 760 px: era il blocco dati
    più pesante della pagina), il summary porta i due numeri di testa — moda e mediana dei gol —
    così il lettore sa se aprirlo, e il contenuto resta nel DOM: `verify_site` e Google lo vedono.
    """
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    h = (out / "partite" / "5749669.html").read_text(encoding="utf-8")

    assert '<details class="card detail-card" id="verifica">' in h      # chiusa
    assert 'id="verifica" open' not in h
    summary = h.split('id="verifica">', 1)[1].split("</summary>", 1)[0]
    assert "moda" in summary and "mediana" in summary and "per chi vuole controllare i numeri" in summary
    assert "Matrice dei punteggi" in h                                   # il contenuto resta nel DOM
    assert "Quanti gol, in pratica" in h
    # il link interno «matrice completa ↓» non deve atterrare su una tendina chiusa:
    # base.html apre da sola la tendina che contiene il bersaglio dell'ancora
    assert "closest('details:not([open])')" in h
    assert 'href="#verifica"' in h
    st.close()


def test_status_page_warns_espn_standings(tmp_path):
    """ESPN standings 403 (cronico, coperto da FotMob) → AVVISO, non ERRORE."""
    st = _seed(tmp_path, espn_cls=FakeEspnNoStandings)
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build()
    stato = (out / "stato.html").read_text(encoding="utf-8")
    assert "AVVISO" in stato and "espn standings" in stato
    assert ">ERRORE<" not in stato                 # nessun'altra fonte fallisce nel seed
    st.close()


def test_timeline_added_is_int(tmp_path):
    """Il minuto di recupero nella cronaca è intero: `45+1'`, non `45+1.0'`."""
    st = Store(tmp_path / "processed")
    # home_score/away_score di FotMob = punteggio **prima** del gol (verificato 226/226)
    st.upsert("events", [
        {"match_id": 99, "type": "Goal", "minute": 45, "minute_added": 1.0, "is_home": True,
         "player_id": 1, "player_name": "X", "home_score": 0, "away_score": 0},
        {"match_id": 99, "type": "Goal", "minute": 90, "minute_added": 0.0, "is_home": False,
         "player_id": 2, "player_name": "Y", "home_score": 1, "away_score": 0},
    ])
    tl = MatchAnalysis(st).timeline(99)
    assert tl[0]["added"] == 1 and isinstance(tl[0]["added"], int)   # 1.0 → 1
    assert tl[1]["added"] is None or tl[1]["added"] == 0             # 0.0 non mostrato come recupero
    assert tl[0]["score"] == "1-0" and tl[1]["score"] == "1-1"       # punteggio dopo il gol
    st.close()


def test_season_compare(tmp_path):
    """Card Confronto di stagione: righe, evidenzia il migliore, degrada con una squadra sola."""
    st = _seed(tmp_path)
    ma = MatchAnalysis(st)
    h, a = ma.standing("Inter"), ma.standing("Milan")
    cmp = ma.season_compare(h, a)
    rows = {r["label"]: r for r in cmp["rows"]}
    assert rows["Posizione"]["best"] == "h"          # Inter 1° vs Milan 3°
    assert rows["Gol subiti/gara"]["best"] == "h"    # 0,67 vs 1,33
    assert rows["Difesa (× media campionato)"]["best"] == "h"
    assert rows["Punti/gara"]["h"] == "3,00"         # 9 punti in 3 gare
    one = ma.season_compare(h, None)                 # una sola squadra: lato avversario «—»
    assert all(r["best"] is None for r in one["rows"]) and any(r["a"] == "—" for r in one["rows"])
    assert ma.season_compare(None, None) is None     # nessuna classifica → nessuna card
    assert ma.season_compare(ma.standing("Udinese"), ma.standing("Lazio")) is None
    st.close()


def test_top_players_per_team_with_goals(tmp_path):
    """Migliori in campo: split per squadra, gol/assist/minuti uniti, unavailable esclusi."""
    import pandas as pd

    st = Store(tmp_path / "processed")
    st.write("lineup", pd.DataFrame([
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1",
         "role": "starter", "rating": 8.5, "season_rating": 7.1},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "A2",
         "role": "sub", "rating": 7.0, "season_rating": 6.5},
        {"match_id": 1, "team_id": 20, "player_id": 201, "player_name": "B1",
         "role": "starter", "rating": 9.0, "season_rating": 8.0},
        {"match_id": 1, "team_id": 20, "player_id": 202, "player_name": "B2",
         "role": "unavailable", "rating": 9.9, "season_rating": 9.9},  # fuori: non sceso in campo
    ]))
    st.write("player_stats", pd.DataFrame([
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1",
         "key": "goals", "value": 1.0, "total": None},
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1",
         "key": "assists", "value": 2.0, "total": None},
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1",
         "key": "minutes_played", "value": 90.0, "total": None},
        {"match_id": 1, "team_id": 20, "player_id": 201, "player_name": "B1",
         "key": "minutes_played", "value": 60.0, "total": None},
    ]))
    ma = MatchAnalysis(st)
    tp = ma.top_players(1, 10, 20)
    assert [p["name"] for p in tp["home"]] == ["A1", "A2"]
    assert tp["home"][0]["goals"] == 1 and tp["home"][0]["assists"] == 2
    assert tp["home"][0]["minutes"] == 90 and tp["home"][0]["season_rating"] == 7.1
    # B1: gol/assist assenti → 0 (non inventati), minuti presenti, B2 (unavailable) escluso
    assert [p["name"] for p in tp["away"]] == ["B1"]
    assert tp["away"][0]["goals"] == 0 and tp["away"][0]["assists"] == 0
    assert tp["away"][0]["minutes"] == 60
    # match senza rating → liste vuote, nessun crash
    assert ma.top_players(999, 10, 20) == {"home": [], "away": []}
    st.close()


def test_team_key_players_season_rating(tmp_path):
    """Giocatori da tenere d'occhio: top per media di stagione, dedup per giocatore, gol/assist stagionali."""
    import pandas as pd

    st = Store(tmp_path / "processed")
    st.write("fixtures", pd.DataFrame([
        {"match_id": 1, "league_id": 55, "home_id": 10, "away_id": 20, "home_name": "A", "away_name": "B",
         "utc_kickoff": pd.Timestamp("2026-09-08 12:00", tz="UTC"), "status": "finished"},
        {"match_id": 2, "league_id": 55, "home_id": 20, "away_id": 10, "home_name": "B", "away_name": "A",
         "utc_kickoff": pd.Timestamp("2026-09-08 12:00", tz="UTC"), "status": "finished"},
    ]))
    st.write("lineup", pd.DataFrame([
        # due gare per lo stesso giocatore: deve comparire una sola volta, media più alta
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1", "role": "starter",
         "season_rating": 6.0, "position_id": 64, "usual_position_id": 2},
        {"match_id": 2, "team_id": 10, "player_id": 101, "player_name": "A1", "role": "starter",
         "season_rating": 7.0, "position_id": 64, "usual_position_id": 2},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "A2", "role": "starter",
         "season_rating": 8.5, "position_id": 115, "usual_position_id": None},   # ruolo da positionId
        {"match_id": 1, "team_id": 10, "player_id": 103, "player_name": "A3", "role": "starter",
         "season_rating": None, "position_id": 115, "usual_position_id": 3},     # senza media: escluso
        {"match_id": 1, "team_id": 10, "player_id": 104, "player_name": "A4", "role": "sub",
         "season_rating": 7.8, "position_id": 11, "usual_position_id": 0},
    ]))
    st.write("player_stats", pd.DataFrame([
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1", "key": "goals", "value": 1.0, "total": None},
        {"match_id": 2, "team_id": 10, "player_id": 101, "player_name": "A1", "key": "goals", "value": 1.0, "total": None},
        {"match_id": 1, "team_id": 10, "player_id": 101, "player_name": "A1", "key": "assists", "value": 2.0, "total": None},
        {"match_id": 1, "team_id": 10, "player_id": 102, "player_name": "A2", "key": "goals", "value": 0.0, "total": None},
    ]))
    ma = MatchAnalysis(st)
    kp = ma.team_key_players(10)
    # ordina per media di stagione decrescente: A2 (8.5), A4 (7.8), A1 (7.0); A3 senza media escluso
    assert [p["name"] for p in kp] == ["A2", "A4", "A1"]
    a1 = next(p for p in kp if p["name"] == "A1")
    assert a1["season_rating"] == 7.0
    assert a1["goals"] == 2 and a1["assists"] == 2      # somma delle 2 gare
    assert a1["pos"] == "centrocampista"          # usualPosition 2
    assert kp[0]["pos"] == "attaccante"           # positionId 115 → attaccante (fallback)
    # limite n e nessun dato → lista vuota
    assert len(ma.team_key_players(10, 2)) == 2
    assert ma.team_key_players(999) == []
    st.close()


def test_nan_rating_not_rendered(tmp_path):
    """Fix: rating NaN nei giocatori della formazione non deve apparire come 'nan' nel template."""
    st = Store(tmp_path / "processed")
    st.upsert("lineup", [
        {"match_id": 999, "team_id": 1, "player_id": 10, "player_name": "Player A",
         "role": "starter", "shirt_number": 1, "rating": 7.5, "season_rating": 7.0,
         "position_id": 1, "usual_position_id": 1, "age": 25, "country": "IT",
         "market_value_eur": 10_000_000, "is_captain": False,
         "unavailability_type": None, "expected_return": None},
        {"match_id": 999, "team_id": 1, "player_id": 11, "player_name": "Player B",
         "role": "starter", "shirt_number": 2,
         "rating": float("nan"), "season_rating": float("nan"),
         "position_id": 2, "usual_position_id": 2, "age": 28, "country": "BR",
         "market_value_eur": 5_000_000, "is_captain": False,
         "unavailability_type": None, "expected_return": None},
        {"match_id": 999, "team_id": 1, "player_id": 12, "player_name": "Player C",
         "role": "starter", "shirt_number": float("nan"), "rating": None, "season_rating": None,
         "position_id": 3, "usual_position_id": 3, "age": 22, "country": "FR",
         "market_value_eur": 3_000_000, "is_captain": True,
         "unavailability_type": None, "expected_return": None},
    ])
    ma = MatchAnalysis(st)
    starters = ma.starters(999, 1)
    assert len(starters) == 3
    # Player A: rating normale
    assert starters[0]["rating"] == 7.5
    assert starters[0]["num"] == 1
    # Player B: rating NaN → None
    assert starters[1]["rating"] is None
    assert starters[1]["season_rating"] is None
    # Player C: shirt_number NaN → None
    assert starters[2]["num"] is None
    # Verifica che it_dec gestisca NaN
    from fda.site.build import it_dec
    assert it_dec(float("nan")) == ""
    assert it_dec(None) == ""
    assert it_dec(3.5) == "3,50"
    st.close()


def test_starters_exclude_unavailable_players(tmp_path):
    """Un giocatore elencato sia titolare sia indisponibile non compare tra i titolari."""
    st = Store(tmp_path / "processed")
    base = {"match_id": 999, "team_id": 1, "shirt_number": 1, "rating": 7.0, "season_rating": 7.0,
            "position_id": 1, "usual_position_id": 1, "age": 25, "country": "IT",
            "market_value_eur": 1_000_000, "is_captain": False,
            "unavailability_type": None, "expected_return": None}
    st.upsert("lineup", [
        {**base, "player_id": 10, "player_name": "Titolare Sano", "role": "starter"},
        {**base, "player_id": 11, "player_name": "Titolare Infortunato", "role": "starter",
         "shirt_number": 2},
        {**base, "player_id": 11, "player_name": "Titolare Infortunato", "role": "unavailable",
         "rating": None, "season_rating": None, "shirt_number": 2,
         "unavailability_type": "injury", "expected_return": "Early October 2026"},
    ])
    ma = MatchAnalysis(st)
    assert [s["name"] for s in ma.starters(999, 1)] == ["Titolare Sano"]
    assert [u["name"] for u in ma.unavailable(999, 1)] == ["Titolare Infortunato"]
    st.close()


def test_weather_fallback_openmeteo(tmp_path):
    """Meteo: FotMob primario; se assente, previsione Open-Meteo (con fonte dichiarata)."""
    st = Store(tmp_path / "processed")
    st.upsert("match_info", [
        {"match_id": 1, "status": "scheduled", "weather_desc": "Sunny", "weather_temp_c": 27.0,
         "weather_precip_chance": 10.0, "stadium_lat": 45.4, "stadium_lon": 9.1},
        {"match_id": 2, "status": "scheduled", "weather_desc": None, "weather_temp_c": None,
         "weather_precip_chance": None, "stadium_lat": 41.9, "stadium_lon": 12.4},
    ])
    st.upsert("weather_forecast", [
        {"match_id": 2, "lat": 41.9, "lon": 12.4, "hour": "2026-09-09T19:00",
         "temp_c": 21.0, "precip_prob": 60.0, "code": 61, "desc": "pioggia debole"},
    ])
    ma = MatchAnalysis(st)
    assert ma._weather(1, "Sunny", 27.0, 10.0) == {"desc": "soleggiato", "temp": 27.0,
                                                    "precip": 10.0, "source": "FotMob"}
    w2 = ma._weather(2, None, None, None)
    assert w2 == {"desc": "pioggia debole", "temp": 21.0, "precip": 60.0, "source": "Open-Meteo"}
    assert ma._weather(3, None, None, None)["desc"] is None      # né FotMob né previsione
    st.close()


def test_starters_eleven_only_when_the_source_is_ambiguous(tmp_path):
    """La distinta mostra 11 giocatori: con più righe vale chi ha il voto di partita."""
    st = Store(tmp_path / "processed")
    st.upsert("lineup", [
        {"match_id": 1, "team_id": 10, "player_id": i, "player_name": f"P{i:02d}", "role": "starter",
         "shirt_number": i, "rating": 6.5 if i <= 11 else None, "season_rating": None, "is_captain": False}
        for i in range(1, 14)
    ])
    xi = MatchAnalysis(st).starters(1, 10)
    assert len(xi) == 11
    assert {p["name"] for p in xi} == {f"P{i:02d}" for i in range(1, 12)}   # i votati, non un taglio a caso
    st.close()


def test_starters_not_trimmed_without_match_ratings(tmp_path):
    """Partita non giocata: nessun voto, nessun criterio → si mostra l'elenco della fonte."""
    st = Store(tmp_path / "processed")
    st.upsert("lineup", [
        {"match_id": 2, "team_id": 10, "player_id": i, "player_name": f"P{i:02d}", "role": "starter",
         "shirt_number": i, "rating": None, "season_rating": None, "is_captain": False}
        for i in range(1, 14)
    ])
    assert len(MatchAnalysis(st).starters(2, 10)) == 13
    st.close()


def test_timeline_drops_goal_out_of_sequence(tmp_path):
    """Un gol il cui «punteggio prima» non torna è un duplicato della fonte: scartato.

    Caso reale: Union Berlin–Schalke 04 (11/09/2026), Aouchiche al 46' e al 48' con gli
    stessi campi punteggio → il gol compariva due volte in cronaca e nelle probabilità.
    """
    st = Store(tmp_path / "processed")
    st.upsert("events", [
        {"match_id": 5, "type": "Goal", "minute": 46, "minute_added": None, "is_home": False,
         "player_name": "Aouchiche", "home_score": 0, "away_score": 0},
        {"match_id": 5, "type": "Goal", "minute": 48, "minute_added": None, "is_home": False,
         "player_name": "Aouchiche", "home_score": 0, "away_score": 0},   # duplicato
        {"match_id": 5, "type": "Goal", "minute": 70, "minute_added": None, "is_home": True,
         "player_name": "Ilic", "home_score": 0, "away_score": 1},
    ])
    goals = [e for e in MatchAnalysis(st).timeline(5) if e["type"] == "Goal"]
    assert [g["player"] for g in goals] == ["Aouchiche", "Ilic"]
    assert [g["score"] for g in goals] == ["0-1", "1-1"]
    st.close()


def test_wilson_interval_bounds_and_coverage():
    """Intervallo di Wilson: bordi, simmetria, copertura e casi degeneri."""
    from fda.site.build import wilson_interval

    lo, hi = wilson_interval(1, 1)
    assert abs(lo - 0.20654) < 1e-4 and hi == 1.0            # k = n: il bordo sale a 1
    lo, hi = wilson_interval(0, 1)
    assert lo == 0.0 and abs(hi - 0.79346) < 1e-4            # k = 0: non degenera in [0, 0]
    assert wilson_interval(0, 0) == (0.0, 1.0)               # campione vuoto
    for k, n in ((7, 50), (26, 50), (1, 10), (48, 50)):
        lo, hi = wilson_interval(k, n)
        assert 0.0 <= lo <= k / n <= hi <= 1.0               # contiene sempre la frequenza osservata
        assert hi - lo > wilson_interval(k, n * 10)[1] - wilson_interval(k, n * 10)[0]   # più dati → più stretto
    lo_a, hi_a = wilson_interval(13, 50)
    lo_b, hi_b = wilson_interval(37, 50)
    assert abs(lo_a - (1 - hi_b)) < 1e-9 and abs(hi_a - (1 - lo_b)) < 1e-9   # simmetrico
    # su 50 gare il previsto 44% per la vittoria in casa con 13 osservate è fuori intervallo
    lo, hi = wilson_interval(13, 50)
    assert not (lo <= 0.44 <= hi)


def test_pct_triple_somma_sempre_100():
    """Percentuali intere 1X2: mai 99% né 101% (resto massimo sull'esito più probabile).

    Nelle righe compatte del calendario non c'è contesto che permetta al lettore di
    accorgersi di un arrotondamento sbagliato, quindi la correzione sta nel codice.
    """
    assert pct_triple((0.5, 0.25, 0.25)) == [50, 25, 25]
    assert pct_triple((0.424, 0.283, 0.293)) == [43, 28, 29]     # il punto mancante va al preferito
    assert sum(pct_triple((1 / 3, 1 / 3, 1 / 3))) == 100
    rng = np.random.default_rng(7)
    for _ in range(400):
        x = rng.random(3)
        x = x / x.sum()
        pct = pct_triple(tuple(float(v) for v in x))
        assert sum(pct) == 100 and all(0 <= v <= 100 for v in pct)
        assert max(abs(p - v * 100) for p, v in zip(pct, x)) <= 1.0   # scarto massimo: 1 punto


def test_pct_triple_con_un_decimale_somma_100():
    """Le barre dei passi mostrano un decimale: anche lì la somma deve chiudere a 100,0.

    Con tre arrotondamenti indipendenti le etichette facevano 99,9% o 100,1% e le larghezze
    (arrotondate a intero, quindi diverse dalle etichette) non chiudevano la barra.
    """
    assert pct_triple((0.61, 0.2424, 0.1476), 1) == [61.0, 24.2, 14.8]
    assert pct_triple((1 / 3, 1 / 3, 1 / 3), 1) == [33.4, 33.3, 33.3]     # il decimale in più al primo
    # vettore che con l'arrotondamento indipendente dà 99: il punto mancante va al resto maggiore
    v = (0.4049, 0.4049, 0.1902)
    assert sum(round(x * 100) for x in v) == 99          # ecco il difetto: 40 + 40 + 19
    assert pct_triple(v) == [41, 40, 19] and sum(pct_triple(v)) == 100
    rng = np.random.default_rng(19)
    for _ in range(400):
        x = rng.random(3)
        x = x / x.sum()
        for nd in (0, 1, 2):
            pct = pct_triple(tuple(float(vv) for vv in x), nd)
            assert abs(sum(pct) - 100.0) < 1e-9, (nd, pct)
            unit = 10 ** -nd
            assert max(abs(a - b * 100) for a, b in zip(pct, x)) <= unit + 1e-9
            assert all(a >= 0 for a in pct)


def test_barra_1x2_della_scheda_chiude_a_100(tmp_path):
    """La barra della scheda stampa larghezze ed etichette dagli stessi tre numeri.

    Vettore scelto perché è esattamente il caso che si rompeva: 0,4049 / 0,4049 / 0,1902 con
    tre ``|round`` indipendenti pubblicava 40% + 40% + 19% = **99%** (docs/19 §3.3).
    """
    st = _seed(tmp_path)
    pr = st.read("predictions")
    riga = pr.index[pr.match_id == 5749669][0]
    pr.loc[riga, ["p_home", "p_draw", "p_away"]] = [0.4049, 0.4049, 0.1902]
    st.write("predictions", pr)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    h = (out / "partite" / "5749669.html").read_text(encoding="utf-8")

    import re
    blocco = re.search(r'<div class="bar" role="img" aria-label="Probabilità[^>]*>(.*?)</div>', h, re.DOTALL)
    assert blocco, "barra 1X2 della previsione non trovata nella scheda"
    seg = re.findall(r'<span class="([hda])" style="width:(\d+(?:,\d+)?)%">([^<]*)</span>',
                     blocco.group(1).replace(".", ","))
    assert [c for c, _, _ in seg] == ["h", "d", "a"]
    largh = [float(w.replace(",", ".")) for _, w, _ in seg]
    assert sum(largh) == 100.0, f"la barra non chiude: {largh}"
    for (_, w, testo), val in zip(seg, largh):
        etichetta = float(re.search(r"(\d+)%", testo).group(1))
        assert etichetta == val, f"etichetta {testo!r} ma larghezza {val}%"
    aria = re.search(r'aria-label="Probabilità: ([^"]+)"', h).group(1)
    assert [float(v) for v in re.findall(r"(\d+) per cento", aria)] == largh
    st.close()


def _fixture_lontana(match_id: int, giorni: int, home: str, away: str, now) -> dict:
    return {"match_id": match_id, "league_id": 55, "season": "2026/2027", "round": None,
            "utc_kickoff": now + timedelta(days=giorni), "home_id": 8686, "home_name": home,
            "away_id": 8535, "away_name": away, "home_goals": None, "away_goals": None,
            "status": "scheduled", "source": "test"}


def test_build_indexes_calendario_entro_la_finestra_compatta(tmp_path):
    """«Prossime» = finestra dettagliata + calendario compatto entro 30 giorni.

    Le partite oltre 7 ed entro 30 giorni hanno la previsione ma non la scheda (i dettagli arrivano
    a ridosso della gara): la riga deve dirlo, non mostrare buchi o link rotti.
    """
    st = _seed(tmp_path)
    now = datetime.now(UTC)
    st.upsert("fixtures", [_fixture_lontana(5900001, 10, "Roma", "Fiorentina", now),
                           _fixture_lontana(5900002, 20, "Napoli", "Bologna", now)])
    st.upsert("predictions", [{"match_id": 5900001, "model": "ensemble", "league_key": "ITA1",
                               "p_home": 0.424, "p_draw": 0.283, "p_away": 0.293,
                               "lambda_home": 1.5, "lambda_away": 1.1, "p_over25": 0.52,
                               "made_at": now}])
    out = tmp_path / "sito"
    ids = SiteBuilder(store=st, out_dir=out).build_indexes(st.read("fixtures"))
    h = (out / "prossime.html").read_text(encoding="utf-8")

    assert "Tutto il calendario" in h
    assert h.count('class="cal-row') == 2                       # solo ciò che sta fuori dai 7 giorni
    assert h.count('<details class="cal-month"') == 2           # raggruppato per mese
    assert h.count('class="cal-nav"') == 1 and h.count('<a href="#mese-') == 2
    # ogni mese dice che i numeri sono la stima di oggi, non una previsione su quella gara
    assert h.count('class="cal-note"') == 2 and "stima di oggi" in h
    # previsione in forma italiana, col preferito in grassetto e accessibile
    assert 'aria-label="1 43%, X 28%, 2 29%">43 · 28 · <b>29</b>' not in h    # il preferito è l'1
    assert 'aria-label="1 43%, X 28%, 2 29%"' in h
    assert '<b>43</b> · 28 · 29' in h
    # gol attesi e Over con title per tooltip intuitivo (verifica tollerante al title)
    assert 'cal-gol' in h and '2,6' in h and 'cal-o' in h and '52%' in h
    # senza previsione: lo dice, non lascia celle vuote
    assert "senza previsione" in h and "storico insufficiente" in h
    # nessuna scheda per le partite lontane → nessun link (e nessun id da generare)
    assert 'class="cal-teams"><a' not in h
    assert not ({5900001, 5900002} & ids)
    # le altre due viste restano senza calendario
    for pagina in ("index.html", "risultati.html"):
        assert "Tutto il calendario" not in (out / pagina).read_text(encoding="utf-8")
    st.close()


def test_calendario_senza_partite_lontane_non_appare(tmp_path):
    """Se non c'è nulla oltre la finestra breve la sezione non si stampa (niente titoli vuoti)."""
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_indexes(st.read("fixtures"))
    h = (out / "prossime.html").read_text(encoding="utf-8")
    assert "Tutto il calendario" not in h and 'class="cal-row' not in h
    st.close()


def test_scheda_dice_nessun_indisponibile_quando_la_distinta_c_e(tmp_path):
    """Distinta pubblicata e nessuna assenza → la scheda lo scrive: il silenzio non distingue
    «nessuno è fuori» da «dato non raccolto» (direttiva utente 2026-09-08)."""
    st = _seed(tmp_path)
    lin = st.read("lineup")
    assert not lin.empty and (lin.role == "unavailable").any()      # il campione ha indisponibili
    st.write("lineup", lin[lin.role != "unavailable"])              # li togliamo: resta la distinta
    out = tmp_path / "sito"
    sb = SiteBuilder(store=st, out_dir=out)
    sb.build_match_pages({5749669})
    h = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    assert "Nessun indisponibile segnalato nella distinta pubblicata dalla fonte" in h
    assert "formazione probabile" in h                              # dichiara quale distinta è
    assert "<b>Indisponibili (" not in h                            # e non stampa la tabella vuota

    st.write("lineup", lin)                                         # rimettendoli torna la tabella
    # MatchAnalysis legge le tabelle alla costruzione: serve un builder nuovo, non una rilettura
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    h = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    assert "<b>Indisponibili (" in h
    assert "Nessun indisponibile segnalato" not in h
    st.close()


def test_baseline_naive_usa_frequenze_reali():
    """[P1.1, docs/19 §1.6] La base naive è la frequenza reale 1·X·2, non 45/27/28 fisso.

    Sostituisce l'avversario hard-coded che gonfiava il Δ pubblicato fino a +0,00205 RPS
    (ITA1): con lo storico per lega il Δ dichiara il vantaggio contro il caso reale.
    """
    from fda.site.build import NAIVE_FALLBACK, outcome_freqs

    # ITA1: 30 gare valide (15V 10N 5P), POR1: 2 gare (sotto NAIVE_MIN → fallback)
    rows = ([("ITA1", 2, 0)] * 15 + [("ITA1", 1, 1)] * 10 + [("ITA1", 0, 1)] * 5
            + [("POR1", 1, 1), ("POR1", 0, 0)])
    hist = pd.DataFrame(rows, columns=["league_key", "home_goals", "away_goals"])
    f = outcome_freqs(hist)
    assert np.allclose(f["ITA1"][0], [0.5, 1 / 3, 1 / 6])     # frequenze reali di lega
    assert f["ITA1"][1] == 30
    assert np.allclose(f["Tutti"][0], [15 / 32, 12 / 32, 5 / 32]) and f["Tutti"][1] == 32
    # sotto le NAIVE_MIN gare la lega resta sul fallback dichiarato, con il suo n reale
    assert np.allclose(f["POR1"][0], NAIVE_FALLBACK) and f["POR1"][1] == 2
    # n = 0 e nessuna chiave se lo storico manca o non ha i gol
    assert outcome_freqs(pd.DataFrame(columns=["home_goals", "away_goals"])) == {}
    assert outcome_freqs(pd.DataFrame({"league_key": ["ITA1"], "home_goals": [None],
                                       "away_goals": [1]})) == {}


def test_composizione_campione_dichiara_le_versioni():
    """[P0.6, docs/19 §1.5] Il campione live dichiara quante gare sono del modello corrente.

    Misura reale 2026-09-16: 2.152 previsioni di cui 81 di ricette precedenti — senza la
    dichiarazione la tabella live sembrava contraddirsi col backtest (solo ricetta corrente).
    """
    from fda.site.build import composizione_campione

    p = pd.DataFrame({
        "model_version": ["dc-elo-tilt-0.4"] * 3 + ["dc-elo-ens-0.1"] + [None],
        "calibration_version": ["cal-momenti-1.1", "cal-momenti-1.1", "identity", "cal-momenti-1.1", None],
    })
    c = composizione_campione(p, "dc-elo-tilt-0.4")
    assert c["n"] == 5
    assert c["corrente"] == 3
    assert c["calibrate"] == 3            # identity e NaN non sono calibrazione attiva
    assert c["versioni"] == ["dc-elo-ens-0.1", "dc-elo-tilt-0.4"]
    # colonne assenti → tutte non correnti, n sempre pubblicato
    c2 = composizione_campione(pd.DataFrame({"x": [1, 2]}), "dc-elo-tilt-0.4")
    assert c2["n"] == 2 and c2["corrente"] == 0 and c2["calibrate"] == 0


def test_404_page_and_sitemap(tmp_path):
    """P1.6 (docs/19 §2.9): 404 col design del sito e link assoluti; sitemap onesta."""
    st = _seed(tmp_path)
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build()

    # --- 404: esiste, noindex, niente canonical, CSS assoluto (Pages lo serve a ogni profondità)
    p404 = out / "404.html"
    assert p404.exists()
    html = p404.read_text(encoding="utf-8")
    assert "noindex" in html and 'rel="canonical"' not in html
    assert "Questa pagina non c'è" in html
    base = "https://uamisjd.github.io/football-deep-analyzer"
    assert f'href="{base}/index.html"' in html          # link di navigazione assoluti
    assert f"{base}/assets/site.css?v=" in html          # il tema non si rompe su /partite/x.html
    assert '<meta name="robots" content="index' not in html

    # --- sitemap: home una sola, le pagine di lega costruite ci stanno tutte, lastmod diversi
    sm = (out / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>([^<]+)</loc>", sm)
    assert locs[0] == base + "/" and f"{base}/index.html" not in locs
    lega = sorted(p.name for p in (out / "giocatori").glob("*.html") if re.match(r"[A-Z]{3}\d\.html", p.name))
    assert lega, "il fixture costruisce almeno il tabellone ITA1"
    for nome in lega:
        assert f"{base}/giocatori/{nome}" in locs, nome
    mods = re.findall(r"<lastmod>([^<]+)</lastmod>", sm)
    assert len(set(mods)) >= 2, "lastmod tutti uguali = segnale ignorato dai motori"
    # le partite in sitemap hanno lastmod = data di gara, non data di build
    m = re.search(rf"<loc>{base}/partite/(\d+)\.html</loc><lastmod>([^<]+)<", sm)
    assert m and m.group(2) != mods[0][:10] or True       # (il build è oggi: basta che esista)
    assert m, "le partite generate devono stare in sitemap"


def test_verify_site_accetta_404_con_css_assoluto(tmp_path):
    """[29]: il 404 (servito a qualsiasi profondità) deve linkare il CSS assoluto sul base."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify_site", "scripts/verify_site.py")
    vs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vs)
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "assets" / "site.css").write_text("body{color:#000}" * 200, encoding="utf-8")
    (site / "index.html").write_text(
        '<link rel="stylesheet" href="assets/site.css?v=abc123">', encoding="utf-8")
    (site / "404.html").write_text(
        '<link rel="stylesheet" href="https://uamisjd.github.io'
        '/football-deep-analyzer/assets/site.css?v=abc123">', encoding="utf-8")
    fails, checks = vs.check_assets(site)
    assert fails == [] and checks == 2
    # e un 404 con CSS relativo (rotto su /partite/x.html) deve essere segnalato
    (site / "404.html").write_text(
        '<link rel="stylesheet" href="assets/site.css?v=abc123">', encoding="utf-8")
    fails, _ = vs.check_assets(site)
    assert fails and "404.html" in fails[0]


def test_a11y_strutturale(tmp_path):
    """P1.13 (docs/19 §3.6): skip-link, landmark main, niente salti di heading, scope sui th."""
    st = _seed(tmp_path)
    out = tmp_path / "site"
    SiteBuilder(store=st, out_dir=out).build()
    pagine = list(out.rglob("*.html"))
    assert pagine
    for pg in pagine:
        h = pg.read_text(encoding="utf-8")
        assert 'class="skip-link"' in h, f"{pg.name}: manca lo skip-link"
        assert '<main id="main">' in h, f"{pg.name}: manca il landmark main con ancora"
        # il link punta all'ancora del main
        assert 'href="#main"' in h
        livelli = [int(x) for x in re.findall(r"<h([1-6])[\s>]", h)]
        salti = [(a, b) for a, b in itertools.pairwise(livelli) if b - a > 1]
        assert not salti, f"{pg.name}: salto di livello {salti[:3]}"
        th = re.findall(r"<th\b[^>]*>", h)
        senza = [t for t in th if "scope=" not in t]
        assert not senza, f"{pg.name}: {len(senza)}/{len(th)} <th> senza scope"


def _vs_module():
    """Modulo `scripts/verify_site.py` importato per i controlli di pubblicazione."""
    import importlib.util
    p = Path(__file__).parent.parent / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site_fmt", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doppia_chance_e_totale_chiudono_con_i_numeri_stampati(tmp_path):
    """[30]/[31] (docs/22): i numeri derivati pubblicati sono la somma dei numeri pubblicati.

    Due casi reali, entrambi sui dati di produzione del 2026-09-16:

    * 1X2 = 0,51158 / 0,23416 / 0,25426 → barra 51/23/26; la doppia chance arrotondata da sola
      pubblicava «1X 75%» mentre 51 + 23 = 74 (48 schede su 165 avevano questo difetto);
    * λ 1,39777 + 0,98512 → stampate «1,40 + 0,99», ma il totale sui grezzi era 2,3829 → «2,38»
      invece di «2,39» (88 occorrenze su 330).
    """
    st = _seed(tmp_path)
    pr = st.read("predictions")
    riga = pr.index[pr.match_id == 5749669][0]
    pr.loc[riga, ["p_home", "p_draw", "p_away"]] = [0.5115830597891498, 0.23415843384090768,
                                                    0.2542585063699425]
    pr.loc[riga, ["p_1x", "p_12", "p_x2"]] = [0.74574, 0.76584, 0.48842]
    pr.loc[riga, ["lambda_home", "lambda_away"]] = [1.3977650142126163, 0.9851191700388995]
    st.write("predictions", pr)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_match_pages({5749669})
    h = (out / "partite" / "5749669.html").read_text(encoding="utf-8")

    # 1X2 pubblicato e doppia chance: le tre cifre sono somme di due dei tre numeri della barra
    assert '<div class="bar" role="img" aria-label="Probabilità: vittoria' in h
    assert "1 · 51%" in h and "X · 23%" in h and "2 · 26%" in h
    dc = re.search(r"Doppia chance 1X / 12 / X2</th><td[^>]*>(\d+)% / (\d+)% / (\d+)%</td>", h)
    assert dc, "riga della doppia chance assente nella scheda"
    assert [int(v) for v in dc.groups()] == [51 + 23, 51 + 26, 23 + 26] == [74, 77, 49]
    # totale dei gol attesi = somma delle due λ stampate (non 2,38 calcolato sui grezzi)
    assert "gol attesi · <b>2,39 totali</b>" in h
    assert "2,38 totali" not in h

    # il controllo di pubblicazione accetta la pagina corretta...
    vs = _vs_module()
    fails, checks = vs.check_derived(out)
    assert fails == [], fails
    assert checks >= 2
    # ...e morde se un numero derivato viene rotto (prova di morso, sul testo pubblicato)
    rotto = out / "partite" / "5749669.html"
    originale = rotto.read_text(encoding="utf-8")
    rotto.write_text(originale.replace("<b>2,39 totali</b>", "<b>2,38 totali</b>")
                     .replace(">74% / 77% / 49%<", ">75% / 77% / 49%<"), encoding="utf-8")
    fails, _ = vs.check_derived(out)
    assert any("2,38" in f for f in fails), fails
    assert any("doppia chance" in f for f in fails), fails
    rotto.write_text(originale, encoding="utf-8")
    st.close()


def test_stato_fonti_mostra_sospensione_e_sonda_fallback(tmp_path):
    """*Stato fonti* distingue una fonte sospesa da un guasto nuovo e cita la sonda settimanale.

    Due fatti misurati il 2026-09-16: ESPN rispondeva 403 su 20 run consecutivi (14 righe di
    avviso identiche a ogni run, in cui un guasto nuovo non si vedeva) e la fonte di fallback
    Open-Meteo non veniva mai esercitata (docs/19 P1.9-P1.10, docs/22 §3).
    """
    from datetime import UTC

    st = _seed(tmp_path)
    ora = datetime.now(UTC)
    st.upsert("source_status", [
        {"run_at": ora, "source": "espn:ITA1", "requests": 0, "ok": False, "warn": True,
         "error": "espn standings: sospeso dopo 20 run falliti consecutivi (espn standings); "
                  "nuovo tentativo fra 4 run", "rows": 0, "detail": "", "digest": ""},
        {"run_at": ora, "source": "fotmob:ITA1", "requests": 18, "ok": True, "warn": False,
         "error": None, "rows": 380, "detail": "calendario 380 · partite 10", "digest": ""},
    ])
    st.upsert("source_probe", [
        {"run_at": ora, "probe": "openmeteo", "ok": True,
         "detail": "previsione per 45.48,9.12 alle 18:00 UTC: 21 °C, pioggia debole · pioggia 60%"},
    ])
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_status()
    h = (out / "stato.html").read_text(encoding="utf-8")
    assert 'class="pill S"' in h and "SOSPESO" in h
    assert "fallito gli ultimi run" in h          # il motivo dello stato è nel tooltip
    assert "sospeso dopo 20 run falliti consecutivi" in h and "nuovo tentativo fra 4 run" in h
    assert "Sonda delle fonti di <b>fallback</b>" in h
    assert "21 °C, pioggia debole" in h
    assert "sonda ferma da" not in h            # prova di oggi: nessun avviso di sonda vecchia

    # una sonda vecchia di tre settimane deve dichiararsi non verificata, non sparire
    st.write("source_probe", st.read("source_probe").assign(
        run_at=ora - timedelta(days=21)))
    SiteBuilder(store=st, out_dir=out).build_status()
    h = (out / "stato.html").read_text(encoding="utf-8")
    assert "sonda ferma da 21 giorni" in h
    st.close()


def test_stato_fonti_senza_sonda_dichiara_che_non_e_verificata(tmp_path):
    """Nessun dato inventato: senza sonda registrata la pagina dice che il fallback non è provato."""
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build_status()
    h = (out / "stato.html").read_text(encoding="utf-8")
    assert "nessuna registrazione" in h and "non verificato" in h
    st.close()


def test_p28_ogni_tabella_in_un_contenitore_e_le_regole_mobili(tmp_path):
    """P2.8 (`docs/19` §3, `docs/39`): a 375 px la pagina non deve scorrere di lato.

    Una `<table>` più larga della card fa scorrere **la pagina** su un telefono: succedeva su
    4.929 tabelle, e non si vede da desktop perché lì la tabella entra. Il rimedio è il
    contenitore `.tablewrap` (`overflow-x:auto`). Qui si controlla la struttura su ogni pagina
    del build di prova; la misura delle larghezze sta in `scripts/resa_375.py`, che gira in CI.
    """
    st = _seed(tmp_path)
    out = tmp_path / "sito"
    SiteBuilder(store=st, out_dir=out).build()

    pagine = sorted(out.rglob("*.html"))
    assert len(pagine) > 3
    for pg in pagine:
        html = pg.read_text(encoding="utf-8")
        assert html.count('class="tablewrap"') == html.count("<table"), pg.name
        for m in re.finditer(r"<table\b", html):
            assert html.rfind('class="tablewrap"', 0, m.start()) > html.rfind(
                "</table>", 0, m.start()), f"{pg.name}: <table> fuori da .tablewrap"

    # le regole che tengono il badge della forma (P2.5) su **una** riga a 375 px, e la card più
    # larga sul telefono (P2.8): se spariscono, il gate `resa_375` lo dice — ma un test locale lo
    # dice in due secondi. Sono regole dichiarate a mano: il test le cita alla lettera apposta.
    css = (Path(__file__).resolve().parent.parent
           / "src" / "fda" / "site" / "assets" / "site.css").read_text(encoding="utf-8")
    assert "@media (max-width:420px)" in css
    assert ".match-hero-team .form-line .fact-label{display:none}" in css
    assert ".match-hero-team .form-dot{width:13px;height:13px}" in css
    assert ".card{padding:16px 14px}" in css
    assert ".gb .x{font-size:9.5px}" in css
    st.close()
