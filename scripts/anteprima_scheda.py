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

rows = []
for rec in pred.to_dict("records"):
    r = dict(rec)
    r.update(calibrated_prediction(r, cal))
    r.update({"lambda_scale": float(cal.lambda_scale), "rho_shift": float(cal.rho_shift),
              "calibration_version": cal.version, "calibration_n_fit": int(cal.n_fit)})
    r["top_scores"] = str(r.get("top_scores"))
    rows.append(r)
store.upsert("predictions", pd.DataFrame(rows))

from fda.site.build import SITE_DIR, SiteBuilder                  # noqa: E402

res = SiteBuilder(store=store).build()
print("sito di anteprima in", SITE_DIR, res)
store.close()
