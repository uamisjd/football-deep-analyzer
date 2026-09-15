"""Test offline del monitoraggio mercati binari (docs/21 P3-b).

Tre mercati sintetici con destini diversi: uno con bias vero e diffuso (deve uscire
«strutturale»), uno centrato («monitora» dentro intervallo), uno con bias in una sola
lega (fuori intervallo nel totale ma «monitora»: il verdetto strutturale chiede che
almeno 5 leghe concordino nel segno).
"""

import numpy as np
import pandas as pd

from fda.models.backtest import market_monitor


def _backtest_sintetico(seed: int = 3, n_per_league: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    leghe = ["ITA1", "ENG1", "ESP1", "GER1", "FRA1", "NED1", "POR1"]
    rows = []
    t0 = pd.Timestamp("2023-08-01")
    for lg in leghe:
        for k in range(n_per_league):
            lh, la = 1.7, 1.3
            if lg == "ITA1":          # solo qui la porta inviolata casa è molto più rara
                la = 1.8
            hg = int(rng.poisson(lh))
            ag = int(rng.poisson(la))
            rows.append({
                "date": t0 + pd.Timedelta(days=int(k * 1.8)), "league_key": lg,
                "home": f"{lg}H{k}", "away": f"{lg}A{k}",
                "home_goals": hg, "away_goals": ag,
                "p_over25": 0.40,          # vero ≈ 0,58 (Poisson 3,0): strutturale
                "p_btts": 0.59,            # vero ≈ 0,59: centrato → monitora
                "p_home_clean_sheet": 0.30,  # vero 0,27 ovunque tranne ITA1 0,17
                "outcome": 0 if hg > ag else 1 if hg == ag else 2,
            })
    return pd.DataFrame(rows)


def test_verdetti_strutturale_monitora_e_lega_singola():
    df = market_monitor(_backtest_sintetico())
    row = df.set_index("market")
    o25 = row.loc["over25"]
    assert o25.outside and o25.leagues_out == 7 and o25.verdict == "strutturale"
    assert o25.half1 == o25.half2 == 1.0            # bias stabile nelle due metà
    btts = row.loc["btts"]
    assert not btts.outside and btts.verdict == "monitora"
    cs = row.loc["cs_h"]
    # fuori intervallo nel totale ma il bias vive in una lega (più al più un'altra per
    # rumore campionario): mai vicino alla soglia delle 5 → resta «monitora»
    assert cs.outside and cs.leagues_out < 5 and cs.verdict == "monitora"
    for r in df.itertuples(index=False):           # Wilson coerente sull'osservato
        assert r.lo <= r.obs <= r.hi


def test_nessun_mercato_su_tabella_vuota():
    assert market_monitor(pd.DataFrame()).empty
