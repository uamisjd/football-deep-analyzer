"""Anteprima locale delle nuove sezioni della scheda (non tocca data/processed).

Copia lo store in /tmp/preview_data, applica la calibrazione salvata alle previsioni già
pubblicate (le λ/ρ grezze sono nella riga, quindi il risultato è lo stesso che produrrebbe
`fda predict` con la calibrazione attiva) e rigenera il sito per ispezione visiva.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

SRC = Path("data/processed")
DST = Path("/tmp/preview_data")

shutil.rmtree(DST, ignore_errors=True)
DST.mkdir(parents=True)
for f in SRC.glob("*"):
    shutil.copy(f, DST)

import fda.store as store_mod                                    # noqa: E402

store_mod.PROCESSED_DIR = DST
from fda.models.calibration import from_store                     # noqa: E402
from fda.models.predict import calibrated_prediction              # noqa: E402
from fda.store import Store                                       # noqa: E402

store = Store(base_dir=DST)
cal = from_store(store)
print("calibrazione:", cal.lambda_scale, cal.rho_shift, cal.version)
pred = store.read("predictions")
print("previsioni:", pred.shape)

# Le righe pubblicate sono state prodotte **prima** dei limiti di sicurezza sulle λ (§3.3 del
# piano): qui li si riapplica come fa `ensemble()` in produzione, recuperando le λ del solo
# modello sui gol dall'1X2 mediato, dai rating Elo e dal peso già salvati nella riga. Senza
# questo passaggio l'anteprima mostrerebbe ancora partite da 8,4 gol attesi.
import numpy as np                                               # noqa: E402
import penaltyblog as pb                                         # noqa: E402

from fda.models.dc_grid import GRID_SIZE                         # noqa: E402
from fda.models.predict import _clamp_lambda                     # noqa: E402

limitate = 0
rows = []
for rec in pred.to_dict("records"):
    r = dict(rec)
    w = float(r.get("w_dc") or 0.0)
    try:
        if w > 0 and np.isfinite([r.get(f"elo_p_{k}", np.nan) for k in ("home", "draw", "away")]).all():
            dc_p = tuple((float(r[f"p_{k}"]) - (1 - w) * float(r[f"elo_p_{k}"])) / w
                         for k in ("home", "draw", "away"))
            ge = pb.models.goal_expectancy(*dc_p, dc_adj=True, rho=float(r.get("dc_rho") or 0.0),
                                           max_goals=GRID_SIZE)
            lim = _clamp_lambda(float(r["lambda_home"]), float(r["lambda_away"]),
                                float(ge["home_exp"]), float(ge["away_exp"]))
            if lim is not None:
                r["lambda_home"], r["lambda_away"] = lim
                r["lambda_limitata"] = True
                limitate += 1
    except (TypeError, ValueError, KeyError):
        pass
    r.update(calibrated_prediction(r, cal))
    r.update({"lambda_scale": float(cal.lambda_scale), "rho_shift": float(cal.rho_shift),
              "calibration_version": cal.version, "calibration_n_fit": int(cal.n_fit),
              "calibration_estimator": str(cal.estimator or ""),
              "calibration_window_days": int(cal.window_days or 0)})
    r["top_scores"] = str(r.get("top_scores"))
    rows.append(r)
print(f"previsioni con λ riportate entro i limiti di sicurezza: {limitate}")
store.upsert("predictions", pd.DataFrame(rows))

from fda.site.build import SITE_DIR, SiteBuilder                  # noqa: E402

res = SiteBuilder(store=store).build()
print("sito di anteprima in", SITE_DIR, res)
store.close()
