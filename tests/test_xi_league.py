"""Test offline di ξ per lega (docs/21 P3-a): esperimento walk-forward e gate di adozione.

Sullo storico sintetico non si pretende che una lega «vinca» lo ξ alternativo: si
verifica il protocollo (stesse gare appaiate, IC coerente col Δ) e che la regola di
adozione — IC 95% del ΔRPS interamente negativo e ≥ MIN_XI_LEAGUE_N gare — sia l'unico
cammino che accende ``adopt``. Il gate di produzione ``xi_for_league`` è testato a parte.
"""

import numpy as np
import pandas as pd

from fda.models import lab
from fda.models.predict import xi_for_league


def _hist_sintetico(seed: int = 7, n_per_league: int = 460) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for lg, squadre in (("ITA1", [f"S{i}" for i in range(8)]), ("ENG1", [f"N{i}" for i in range(8)])):
        forza = {s: rng.normal(0, 0.35) for s in squadre}
        t = pd.Timestamp("2023-09-01")
        for k in range(n_per_league):
            h, a = rng.choice(squadre, size=2, replace=False)
            lh = np.exp(0.35 + forza[h] - forza[a] * 0.5)
            la = np.exp(0.25 + forza[a] - forza[h] * 0.5)
            rows.append({"league_key": lg, "date": t + pd.Timedelta(days=int(k * 2.5)),
                         "season": "2023", "home": h, "away": a,
                         "home_goals": int(rng.poisson(lh)), "away_goals": int(rng.poisson(la)),
                         "odds_home": None, "odds_draw": None, "odds_away": None})
    return pd.DataFrame(rows)


def test_esperimento_xi_struttura_e_regola():
    hist = _hist_sintetico()
    df = lab.xi_league_experiment(hist, grid=(0.0018, 0.0030), step_days=60,
                                  min_train=250, draws=400)
    assert set(df.league_key) == {"ENG1", "ITA1"}
    for r in df.itertuples(index=False):
        assert r.n >= 20
        assert r.xi_best in (0.0018, 0.0030)
        assert r.rps_global > 0 and abs(r.rps_best - (r.rps_global + r.delta)) < 1e-9
        if r.xi_best == 0.0018:
            # nessun candidato batte il globale: Δ nullo, IC nullo, niente adozione
            assert r.delta == 0.0 and r.ci_hi == 0.0 and not r.adopt
        else:
            assert r.delta < 0 and r.ci_lo <= r.delta <= r.ci_hi
            attesa = bool(r.ci_hi < 0 and r.n >= lab.MIN_XI_LEAGUE_N)
            assert r.adopt == attesa


def test_adozione_bloccata_sotto_la_soglia_di_gare():
    hist = _hist_sintetico().groupby("league_key").head(330)   # poche gare: mai adottare
    df = lab.xi_league_experiment(hist, grid=(0.0018, 0.0030), step_days=45,
                                  min_train=250, draws=200)
    assert not df.adopt.any()          # poche gare fuori campione: mai adottare


def test_xi_for_league_legge_solo_le_adozioni(tmp_path):
    p = tmp_path / "xi_league.parquet"
    pd.DataFrame([
        {"league_key": "ITA1", "xi_best": 0.0030, "adopt": True, "n": 900},
        {"league_key": "ENG1", "xi_best": 0.0010, "adopt": False, "n": 900},
        {"league_key": "GER1", "xi_best": -1.0, "adopt": True, "n": 900},   # valore rotto
    ]).to_parquet(p)
    assert xi_for_league("ITA1", path=p) == 0.0030
    assert xi_for_league("ENG1", path=p) == 0.0018      # non adottata → globale
    assert xi_for_league("GER1", path=p) == 0.0018      # ξ non positivo → globale
    assert xi_for_league("FRA1", path=p) == 0.0018      # lega assente → globale
    assert xi_for_league("ITA1", path=tmp_path / "no.parquet") == 0.0018
