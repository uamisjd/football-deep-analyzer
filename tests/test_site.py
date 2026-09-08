import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from fda.collect import collect_league
from fda.config import league
from fda.site.analysis import MatchAnalysis
from fda.site.build import SiteBuilder
from fda.store import Store
from tests.test_store_collect import FakeEspn, FakeFotMob, FakeUnderstat

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


def _seed(tmp_path):
    st = Store(tmp_path / "processed")
    collect_league(league("ITA1"), st, past_days=30, future_days=30,
                   fotmob=FakeFotMobPre(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(), espn=FakeEspn(),
                   today=date(2026, 9, 6))
    # sposta le partite campione attorno a "oggi" così finiscono nelle pagine
    now = datetime.now(timezone.utc)
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
    # momentum deterministico: Monza preme nei primi 25', poi domina Inter (12/18 minuti = 67%)
    mom = [{"match_id": 5749645, "minute": float(m), "value": float(v)} for m, v in [
        (5, -30), (10, -40), (15, -35), (20, -25), (25, -20), (30, 0),
        (35, 20), (40, 35), (45, 45), (50, 30), (55, 55), (60, 65), (65, 40), (70, 50), (75, 60), (80, 45), (85, 70), (90, 35)]]
    st.upsert("momentum", mom)
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
    assert "—</td>" in post and 'class="best"' not in post
    # cartina dei tiri (SVG): 2 pannelli, i 2 tiri dell'Inter del campione, Monza senza tiri
    assert "Cartina dei tiri" in post
    assert post.count("<svg") == 3          # 2 cartine + 1 momentum
    assert "xG 0,88" in post                       # gol di Lautaro Martínez, decimale italiano
    assert "Nessun tiro registrato" in post        # pannello Monza vuoto
    # momentum (SVG a barre + marker gol): 18 punti seed + 2 del campione; Inter dominante (13/20 = 65%)
    assert "Momentum della partita" in post
    assert "Momentum a favore di <b>Inter</b> nel 65% dei minuti" in post
    assert 'fill="#f2555a"' in post and 'fill-opacity="0.75"' in post  # barre negative/positive
    # ultimi precedenti reali (tabella h2h): sia pre che post, con V/N/P dalla prospettiva della casa attuale
    assert "Ultimi precedenti" in post and "Monza <b>1-1</b> Inter" in post
    assert "Monza <b>0-3</b> Inter" in post
    i01 = post.find("Monza <b>0-3</b> Inter")
    assert 'class="pill V"' in post[i01:i01 + 400]    # Inter (casa attuale) vinse in trasferta
    assert 'class="pill N"' in post                   # Monza 1-1 Inter → pareggio
    assert "50% dei casi" in post                     # precedenti: entrambe a segno 1 su 2

    stag = (out / "stagione.html").read_text(encoding="utf-8")
    assert "Proiezioni di stagione" in stag and "Serie A" in stag and "Inter" in stag
    assert "84,2" in stag and "61,0%" in stag and "66,0%" in stag   # virgola decimale italiana
    assert "10.000" not in stag  # niente formattazioni inglesi
    assert "Top-4" in stag and "Retro" in stag and "Media pos." in stag

    pre = (out / "partite/5749669.html").read_text(encoding="utf-8")
    assert "Analisi pre-partita" in pre and "Formazione probabile" in pre and "Cronaca" not in pre
    # pre-partita: niente card Confronto (Udinese/Lazio fuori tabella campione), segnaposto onesti
    assert "Confronto di stagione" not in pre
    assert "da definire" in pre and "da definire" not in post
    assert "2,50 gol/gara" in pre and "gol/gara" in post
    assert "Indisponibili" in pre and "McTominay" in pre and "metà ottobre 2026" in pre
    assert "Partita equilibrata" in pre
    assert "Risultati esatti" in pre and "1-1" in pre
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
    assert "0,087" in acc      # RPS della singola previsione 0.62/0.21/0.17 con esito 1
    # sito italiano: nessun residuo UTC/inglese, orari in ora italiana
    for page in ("index.html", "partite/5749645.html", "partite/5749669.html", "accuratezza.html"):
        html = (out / page).read_text(encoding="utf-8")
        assert "UTC" not in html, page
        assert "(ora italiana)" in html, page
    assert "noindex" in (out / "index.html").read_text(encoding="utf-8")
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
