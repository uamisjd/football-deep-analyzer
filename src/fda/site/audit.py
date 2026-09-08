"""Audit della completezza delle schede generate.

Un campo non pubblicato prima della sua finestra editoriale (arbitro, meteo e
formazioni ufficiali) non viene contato come errore: viene classificato come
``atteso``. In questo modo distinguiamo un dato realmente mancato da un dato
che la fonte non ha ancora reso disponibile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class AuditItem:
    key: str
    label: str
    required: bool = True
    min_days_before: int = 0


PREMATCH_ITEMS = (
    AuditItem("prediction", "Previsione modello"),
    AuditItem("home_form", "Forma casa"),
    AuditItem("away_form", "Forma trasferta"),
    AuditItem("home_xg", "xG stagione casa"),
    AuditItem("away_xg", "xG stagione trasferta"),
    AuditItem("season_compare", "Confronto di stagione"),
    AuditItem("home_unavailable", "Indisponibili casa"),
    AuditItem("away_unavailable", "Indisponibili trasferta"),
    AuditItem("home_starters", "Formazione casa", min_days_before=1),
    AuditItem("away_starters", "Formazione trasferta", min_days_before=1),
    AuditItem("referee", "Arbitro", min_days_before=2),
    AuditItem("weather", "Meteo", min_days_before=3),
    AuditItem("h2h_list", "Precedenti H2H"),
)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    if isinstance(value, dict):
        return any(_present(v) for v in value.values())
    if isinstance(value, (list, tuple, set, pd.Series)):
        return len(value) > 0
    return bool(value)


def audit_match(ctx: dict[str, Any], now: pd.Timestamp | None = None) -> dict[str, Any]:
    """Restituisce stato dettagliato senza nascondere i dati veramente assenti."""
    now = now or pd.Timestamp.now(tz="UTC")
    kickoff = pd.Timestamp(ctx["utc_kickoff"])
    if kickoff.tzinfo is None:
        kickoff = kickoff.tz_localize("UTC")
    days = (kickoff - now).total_seconds() / 86400
    items = []
    for item in PREMATCH_ITEMS:
        value = ctx.get(item.key)
        if _present(value):
            state = "presente"
        elif days > item.min_days_before:
            state = "atteso"
        else:
            state = "mancante"
        items.append({"key": item.key, "label": item.label, "state": state})
    counts = {state: sum(i["state"] == state for i in items) for state in ("presente", "atteso", "mancante")}
    counts["totale"] = len(items)
    counts["percentuale"] = round(100 * (counts["presente"] + counts["atteso"]) / len(items), 1)
    return {"match_id": ctx["match_id"], "items": items, **counts}


def audit_summary(contexts: list[dict[str, Any]]) -> dict[str, Any]:
    audits = [audit_match(c) for c in contexts]
    total = sum(a["totale"] for a in audits)
    complete = sum(a["presente"] + a["atteso"] for a in audits)
    return {"matches": len(audits), "audits": audits, "complete": complete,
            "fields": total, "percentuale": round(100 * complete / total, 1) if total else 0.0}
