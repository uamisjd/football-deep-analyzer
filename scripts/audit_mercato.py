"""Audit misurato della card «Mercato» (docs/56): dove nascono i duplicati e cosa li toglie.

Il difetto misurato in ``docs/55``: la scheda pubblica molti più movimenti di quanti ne
pubblici la fonte. Qui si isola la causa sui dati del repository, senza rete:

1. quante righe di ``transfers.parquet`` sono **illeggibili** al parser usato oggi
   (``pd.to_datetime(..., utc=True)`` a formato misto → NaT) e quanti movimenti restano
   perciò invisibili;
2. quante righe restano applicando la chiave dell'upsert confrontata con la chiave
   normalizzata (nome e controparte senza diacritici/punteggiatura, data al giorno);
3. l'effetto sulle 66 schede pre-partita in finestra: totale arrivi/partenze pubblicati,
   righe duplicate visibili, schede cambiate.

Uso: ``.venv/bin/python -m scripts.audit_mercato``
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from itertools import pairwise
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DATA = ROOT / "data" / "processed"


def soft(s: object) -> str:
    """Chiave di confronto: senza accenti né punteggiatura, minuscola."""
    s = unicodedata.normalize("NFKD", str(s or "").strip())
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def load(path: Path = DATA / "transfers.parquet") -> pd.DataFrame:
    df = pd.read_parquet(path)
    d = df.copy()
    # parser tollerante: i due formati della fonte convivono nella stessa colonna
    d["_dt"] = pd.to_datetime(d["date"], utc=True, errors="coerce", format="mixed")
    d["_dt_strict"] = pd.to_datetime(d["date"], utc=True, errors="coerce")
    d["_day"] = d["_dt"].dt.floor("D").dt.strftime("%Y-%m-%d")
    for c in ("player_name", "counterpart"):
        d[f"_k_{c}"] = d[c].map(soft)
    return d


def report_parse(d: pd.DataFrame) -> None:
    n = len(d)
    strict_na = int(d._dt_strict.isna().sum())
    tol_na = int(d._dt.isna().sum())
    piena = ["team_id", "direction", "_k_player_name", "_k_counterpart"]
    ok = d[d._dt_strict.notna()]
    gruppi_ok = ok.groupby(piena + ["_day"], dropna=False).size()
    tutti = d.groupby(piena + ["_day"], dropna=False).agg(n=("_dt", "size"), leggibili=("_dt_strict", "count"))
    invisibili = tutti[tutti.leggibili == 0]
    print(f"righe: {n} · NaT col parser attuale (formato misto): {strict_na} ({strict_na / n:.1%})"
          f" · NaT col parser tollerante: {tol_na}")
    print(f"movimenti (chiave normalizzata + giorno) con 0 righe leggibili → mai in pagina: "
          f"{len(invisibili)} ({int(invisibili.n.sum())} righe)")
    print(f"movimenti letti dal parser attuale: {len(gruppi_ok)}")


def dedup(d: pd.DataFrame, *, chiave_attuale: bool = False) -> pd.DataFrame:
    """Righe dopo la deduplicazione.

    ``chiave_attuale=True`` riproduce la chiave dell'upsert (nome e controparte *così come
    sono*, data al secondo): è il comportamento di oggi. Altrimenti: chiave normalizzata
    (senza diacritici, data al giorno) e si tiene la riga con l'importo pubblicato; a parità,
    la più recente.
    """
    if chiave_attuale:
        k = ["team_id", "player_name", "direction", "counterpart", "date"]
        return d.drop_duplicates(subset=k, keep="last")
    d = d[d._dt.notna()].copy()
    k = ["team_id", "direction", "_k_player_name", "_k_counterpart"]
    parts = []
    for _, g in d.groupby(k, dropna=False, sort=False):
        # stesso movimento ripetuto a poche ore di distanza (o a cavallo della mezzanotte:
        # la fonte mescola UTC e ora locale): si tiene la riga più informativa del gruppo
        # di righe a meno di ``TOLLERANZA`` ore dalla prima.
        g = g.sort_values("_dt")
        primo = g._dt.iloc[0]
        vicino = g[(g._dt - primo) <= pd.Timedelta(hours=TOLLERANZA_ORE)]
        resto = g[(g._dt - primo) > pd.Timedelta(hours=TOLLERANZA_ORE)]
        scelta = vicino.sort_values(["fee_text", "_dt"], key=lambda s: s.isna() if s.name == "fee_text" else s)
        parts.append(scelta.tail(1))
        parts.append(resto)
    out = pd.concat(parts).sort_values("_dt")
    return out


TOLLERANZA_ORE = 30


def finestra(d: pd.DataFrame, team_id: int, gap_days: int = 21) -> dict | None:
    """Finestra della squadra come in ``analysis.transfer_window`` (semplificata)."""
    t = d[(d.team_id == team_id) & d._dt.notna()].sort_values("_dt", ascending=False)
    if t.empty:
        return None
    dates = t._dt.tolist()
    first = dates[0]
    for prev, cur in pairwise(dates):
        if (prev - cur) > pd.Timedelta(days=gap_days):
            break
        first = cur
    w = t[t._dt >= first]
    return {"in": int((w.direction == "in").sum()), "out": int((w.direction == "out").sum()),
            "start": first, "end": dates[0], "nomi_in": w[w.direction == "in"].player_name.tolist()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default=str(DATA / "transfers.parquet"))
    args = ap.parse_args(argv)
    d = load(Path(args.file))
    print("=== 1. leggibilità delle date ===")
    report_parse(d)
    print("\n=== 2. righe dopo la deduplicazione ===")
    oggi = dedup(d, chiave_attuale=True)
    nuovo = dedup(d)
    print(f"chiave attuale: {len(oggi)} righe · chiave normalizzata: {len(nuovo)} righe "
          f"(−{len(oggi) - len(nuovo)} duplicate, −{len(d) - len(nuovo)} sul totale)")
    print(f"movimenti mai in pagina per via delle date: {len(d) - len(d[d._dt.notna()])} righe "
          f"(tutte NaT anche col parser tollerante)")
    print("\n=== 3. effetto sulle 66 schede in finestra ===")
    fixtures = pd.read_parquet(DATA / "fixtures.parquet")
    in_finestra = fixtures[fixtures.status != "finished"]
    print(f"schede in finestra: {len(in_finestra)}")
    for nome, tab in (("oggi", oggi), ("normalizzata", nuovo)):
        tot_in = tot_out = 0
        dup_vis = 0
        for r in in_finestra.itertuples(index=False):
            for tid in (int(r.home_id), int(r.away_id)):
                f = finestra(tab, tid)
                if not f:
                    continue
                tot_in += f["in"]
                tot_out += f["out"]
                dup_vis += len(f["nomi_in"]) - len(set(f["nomi_in"]))
        print(f"  {nome}: arrivi pubblicati {tot_in} · partenze {tot_out} · nomi ripetuti nella "
              f"stessa colonna {dup_vis}")
    print("\n=== 4. esempi (Santa Clara) ===")
    s = d[(d.team_id == 1567)].sort_values("_dt").tail(8)
    print(s[["player_name", "direction", "counterpart", "fee_text", "date"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
