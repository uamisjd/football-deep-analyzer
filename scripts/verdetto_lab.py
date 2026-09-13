#!/usr/bin/env python3
"""
Verdetto del laboratorio: applica la regola decisionale registrata in docs/13 §5-§6
- Si cambia modello di produzione SOLO se delta_rps_hi95 < 0 (IC 95% interamente negativo)
  E il candidato ha RPS più basso in almeno 5 leghe su 7.
Altrimenti si resta su dc_elo_prod.

Legge data/processed/model_lab.parquet (ALL + per-lega) e stampa:
- ΔRPS complessivo + IC per ogni candidato
- vittorie per lega vs baseline
- bias λ, brier mercati
- verdetto finale
"""
import pandas as pd
import sys
from pathlib import Path

def main():
    parquet = Path("data/processed/model_lab.parquet")
    if not parquet.exists():
        print(f"{parquet} non trovato", file=sys.stderr)
        sys.exit(1)
    df = pd.read_parquet(parquet)
    # Separare ALL e per-lega
    all_df = df[df['league_key'] == 'ALL'].copy()
    per_df = df[df['league_key'] != 'ALL'].copy()

    print(f"model_lab.parquet: {df.shape[0]} righe, {df['candidate'].nunique()} candidati")
    print(f"ALL: {all_df.shape[0]} righe, per-lega: {per_df.shape[0]} righe")
    if all_df.empty:
        print("Nessuna riga ALL", file=sys.stderr)
        sys.exit(1)

    # Baseline
    baseline = "dc_elo_prod"
    base_all = all_df[all_df['candidate'] == baseline]
    if base_all.empty:
        print(f"Baseline {baseline} non trovata in ALL", file=sys.stderr)
        # prendi primo come riferimento
        baseline = all_df.iloc[0]['candidate']
        base_all = all_df[all_df['candidate'] == baseline]
        print(f"Uso {baseline} come riferimento")

    # Per ogni candidato in ALL, stampa ΔRPS
    print("\n=== ΔRPS complessivo (ALL) ===")
    for _, row in all_df.sort_values('rps').iterrows():
        cand = row['candidate']
        rps = row['rps']
        delta = row.get('delta_rps', float('nan'))
        lo = row.get('delta_rps_lo95', float('nan'))
        hi = row.get('delta_rps_hi95', float('nan'))
        bias = row.get('bias_lambda', float('nan'))
        brier = row.get('brier_mercati', float('nan'))
        mig = row.get('migliore_in', float('nan'))
        print(f"{cand:15s} RPS {rps:.6f} Δ {delta:+.6f} IC [{lo:+.6f}; {hi:+.6f}] bias {bias:+.3f} brier {brier:.6f} migliore_in {mig:.1%}")

    # Vittorie per lega vs baseline
    if not per_df.empty:
        print("\n=== Vittorie per lega vs baseline ===")
        # baseline per lega
        base_per = per_df[per_df['candidate'] == baseline][['league_key','rps']].rename(columns={'rps':'rps_base'})
        # merge
        merged = per_df.merge(base_per, on='league_key', how='left')
        # conta per candidato quante leghe ha rps < rps_base
        wins = {}
        for cand in per_df['candidate'].unique():
            sub = merged[merged['candidate']==cand]
            # confronta solo dove baseline presente
            cnt = (sub['rps'] < sub['rps_base']).sum()
            tot = sub['rps_base'].notna().sum()
            wins[cand] = (int(cnt), int(tot))
            print(f"{cand:15s} batte baseline in {cnt}/{tot} leghe")
            # dettaglio per lega
            for _, r in sub.sort_values('league_key').iterrows():
                mark = "✓" if r['rps'] < r['rps_base'] else " "
                print(f"  {mark} {r['league_key']:4s} {r['candidate']:15s} {r['rps']:.6f} vs {r['rps_base']:.6f} (n={r['n']})")
    else:
        print("\nNessuna riga per-lega, impossibile contare vittorie")
        wins = {}

    # Applica regola decisionale
    print("\n=== Verdetto (regola docs/13 §5-§6) ===")
    print("Si cambia modello SOLO se delta_rps_hi95 < 0 E vittorie >=5/7")
    candidates_to_promote = []
    for _, row in all_df.iterrows():
        cand = row['candidate']
        if cand == baseline:
            continue
        hi = row.get('delta_rps_hi95', float('nan'))
        if pd.isna(hi):
            continue
        if hi < 0:
            cnt, tot = wins.get(cand, (0,0))
            if cnt >= 5:
                candidates_to_promote.append((cand, row['delta_rps'], hi, cnt))

    if not candidates_to_promote:
        print(f"Verdetto: RESTA {baseline} — nessun candidato soddisfa entrambe le condizioni")
        # mostra chi soddisfa solo una
        for _, row in all_df.iterrows():
            cand = row['candidate']
            if cand == baseline:
                continue
            hi = row.get('delta_rps_hi95', float('nan'))
            cnt, tot = wins.get(cand, (0,0))
            cond1 = hi < 0 if not pd.isna(hi) else False
            cond2 = cnt >=5
            print(f"  {cand}: IC<0? {cond1} (hi95={hi:.6f})  >=5 leghe? {cond2} ({cnt}/7)")
    else:
        # ordina per delta più negativo
        candidates_to_promote.sort(key=lambda x: x[1])
        best = candidates_to_promote[0]
        print(f"Verdetto: PROMUOVERE {best[0]} — ΔRPS {best[1]:+.6f} hi95 {best[2]:+.6f} vittorie {best[3]}/7")
        for cand, delta, hi, cnt in candidates_to_promote:
            print(f"  candidato {cand}: Δ {delta:+.6f} hi95 {hi:+.6f} vittorie {cnt}/7")

if __name__ == "__main__":
    main()
