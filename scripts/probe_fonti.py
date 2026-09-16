"""Sonda periodica delle fonti di **fallback** (docs/19 P1.10).

Perché serve: Open-Meteo interviene solo quando FotMob non ha ancora pubblicato il meteo
(48 ore prima della gara), quindi può passare settimane senza essere esercitato — e una fonte
che non viene mai chiamata si rompe in silenzio (endpoint cambiato, parametri non più
accettati, licenza modificata). Lo stesso vale per qualunque fallback: *non usato* non è
*funzionante*.

Questa sonda fa **una richiesta vera a settimana** (workflow `lab`, lunedì) e registra l'esito
in ``data/processed/source_probe.parquet``, che la pagina *Stato fonti* pubblica con la data:
così «il fallback funziona» non è un'ipotesi ma una misura datata, e un guasto del fallback
si vede in una settimana invece che alla prima pioggia di novembre.

Uso:
    python scripts/probe_fonti.py                    # tutte le sonde, esito a schermo
    python scripts/probe_fonti.py --store /tmp/dati  # parquet altrove (test)
Esce con codice 1 se una sonda fallisce: nel workflow il run diventa rosso.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fda.config import PROCESSED_DIR
from fda.sources.openmeteo import OpenMeteoClient
from fda.store import Store

#: Campo di San Siro: coordinate reali e stabili, usate solo per provare l'endpoint.
PROBE_LAT, PROBE_LON = 45.478, 9.124


def probe_openmeteo(client: Any, now: datetime) -> dict[str, Any]:
    """Una previsione vera a 24 h: ``{probe, ok, detail}`` (mai un esito inventato)."""
    quando = now + timedelta(hours=24)
    try:
        fc = client.forecast(PROBE_LAT, PROBE_LON, quando)
    except Exception as exc:  # noqa: BLE001 — una sonda rotta è un esito, non un crash
        return {"probe": "openmeteo", "ok": False,
                "detail": f"errore: {type(exc).__name__}: {str(exc)[:120]}"}
    if not fc:
        return {"probe": "openmeteo", "ok": False, "detail": "risposta senza ore utilizzabili"}
    temp, desc = fc.get("temp_c"), fc.get("desc")
    if temp is None or not desc:
        return {"probe": "openmeteo", "ok": False,
                "detail": f"previsione incompleta: {fc}"}
    return {"probe": "openmeteo", "ok": True,
            "detail": (f"previsione per {PROBE_LAT:.2f},{PROBE_LON:.2f} alle {quando:%H:%M} UTC: "
                       f"{temp:.0f} °C, {desc}"
                       + (f" · pioggia {fc['precip_prob']:.0f}%" if fc.get("precip_prob") is not None else ""))}


#: Sonde attive: nome → funzione che restituisce l'esito. Aggiungere qui una fonte di
#: fallback significa anche vederla in *Stato fonti* con la data dell'ultima prova.
PROBES: dict[str, Callable[[datetime], dict[str, Any]]] = {
    "openmeteo": lambda now: probe_openmeteo(OpenMeteoClient(), now),
}


def esegui(now: datetime | None = None, probes: dict[str, Callable[[datetime], dict[str, Any]]] | None = None
           ) -> list[dict[str, Any]]:
    """Esegue tutte le sonde e restituisce le righe da salvare (ordinate per nome)."""
    now = now or datetime.now(UTC)
    probes = PROBES if probes is None else probes
    righe: list[dict[str, Any]] = []
    for nome in sorted(probes):
        try:
            esito = probes[nome](now)
        except Exception as exc:  # noqa: BLE001 — idem: l'esito negativo va registrato
            esito = {"probe": nome, "ok": False, "detail": f"errore: {type(exc).__name__}: {exc}"}
        righe.append({"run_at": now, "probe": str(esito.get("probe", nome)),
                      "ok": bool(esito.get("ok")), "detail": str(esito.get("detail", ""))[:200]})
    return righe


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", default=str(PROCESSED_DIR), help="cartella dei Parquet")
    args = ap.parse_args()
    righe = esegui()
    store = Store(Path(args.store))
    store.upsert("source_probe", righe)
    store.close()
    for r in righe:
        stato = "OK" if r["ok"] else "FALLITA"
        print(f"[sonda] {r['probe']}: {stato} — {r['detail']}")
    fallite = [r for r in righe if not r["ok"]]
    if fallite:
        print(f"[sonda] {len(fallite)} fonte/i di fallback non risponde: "
              f"il fallback è dichiarato ma non funziona")
    return 1 if fallite else 0


if __name__ == "__main__":
    raise SystemExit(main())
