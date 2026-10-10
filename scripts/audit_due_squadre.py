"""Audit 360° della card «Le due squadre» (revisione del 2026-10-10, `docs/76`).

Misura su **tutte** le schede di ``site/partite`` che cosa la card propone e come:
copertura di ogni elemento (forma, forza degli avversari, xG con rapporto di lega,
xPTS col verdetto sulla banda, indice di pressione, riposo, infermeria, distinta),
i silenzi non dichiarati (distinta mancante senza messaggio, pannelli pre-partita
senza né assenze né formazione) e la finestra «alla vigilia» (nessun campione che
contenga la partita stessa descritta, anche quando Understat la data qualche minuto
prima del calcio d'inizio FotMob). Non duplica l'invariante [44], che ricalcola i
numeri: qui si misura la copertura comunicativa.

Uso: ``.venv/bin/python scripts/audit_due_squadre.py`` (dopo ``fda build``).
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "partite"
DATA = ROOT / "data" / "processed"

SEZ = re.compile(r'<div class="grid detail-card" id="squadre">(.*?)<div class="grid detail-card"',
                 re.DOTALL)
PANEL = re.compile(r'<div class="card">\s*<h2>(.*?)</h2>(.*?)(?=<div class="card">\s*<h2>|'
                   r'</div>\s*<p class="small mut")', re.DOTALL)


def main() -> int:
    if not SITE.exists():
        print("nessuna site/partite: esegui prima `fda build`")
        return 1
    fx = pd.read_parquet(DATA / "fixtures.parquet")
    us = pd.read_parquet(DATA / "understat_team_matches.parquet")
    us["_d"] = pd.to_datetime(us["date"], utc=True, errors="coerce")
    fx["ko"] = pd.to_datetime(fx.utc_kickoff, utc=True, errors="coerce")

    agg: Counter[str] = Counter()
    no_min, casi_forma, silenziosi = [], [], []
    for p in sorted(SITE.glob("*.html")):
        html = p.read_text(encoding="utf-8")
        m = SEZ.search(html)
        if not m:
            agg["sezioni_mancanti"] += 1
            continue
        pre = "Analisi pre-partita" in html
        agg["pagine"] += 1
        agg["pagine_pre" if pre else "pagine_finite"] += 1
        for name, body in PANEL.findall(m.group(1)):
            agg["riquadri"] += 1
            has_form = "form-dots" in body
            if has_form:
                agg["forma_presente"] += 1
                agg["pallini_forma"] += len(re.findall(r'class="form-dot [VNP]"', body))
            else:
                agg["forma_assente"] += 1
                if "nessuna gara di campionato prima di questa" not in body:
                    casi_forma.append((p.stem, name.strip()))
            if "form-strength" in body:
                agg["forza_avv_presente"] += 1
            if "nessuna gara di campionato prima di questa" in body:
                agg["riquadri_senza_gare_prima"] += 1
            if "xG creati / gara" in body:
                agg["xg_creati"] += 1
            agg["rapporti_lega"] += body.count("× la media del campionato")
            agg["rapporto_corto"] += body.count("campione troppo corto per il confronto")
            agg["verdetti_xpts"] += len(re.findall(
                r"sopra gli attesi, oltre il rumore|sotto gli attesi, oltre il rumore|"
                r"in linea \(scarto entro", body))
            agg["xpts_verdetto_corto"] += body.count("campione troppo corto per un verdetto")
            agg["press_fotmob"] += body.count("pass. concessi / azione dif.")
            agg["press_ppda_ripiego"] += body.count("PPDA (Understat)")
            agg["press_etichetta"] += len(re.findall(r"pressa alto|lascia giocare", body))
            agg["riposo_presente"] += body.count("di riposo")
            agg["riposo_nd"] += body.count("riposo n.d.")
            if re.search(r"<b>Indisponibili \(", body):
                agg["infermeria_presente"] += 1
                agg["righe_infermeria"] += len(re.findall(r"<td><b>.*?</b>", body))
                agg["righe_senza_minuti"] += body.count("senza minuti in stagione")
                agg["righe_stima"] += body.count("◇")
                agg["righe_ruolo_nd"] += body.count("ruolo n.d.")
                for nm in re.findall(r"<td><b>(.*?)</b>.*?senza minuti in stagione",
                                     body, re.DOTALL):
                    no_min.append((p.stem, nm))
            elif "Nessun indisponibile segnalato" in body:
                agg["infermeria_vuota_dichiarata"] += 1
            elif pre:
                agg["infermeria_silente_pre"] += 1
                silenziosi.append((p.stem, name.strip()))
            if "formation-list" in body:
                agg["distinta_presente"] += 1
                agg["distinta_media_voto"] += body.count("⌀")
                agg["panchina_presente"] += body.count("Panchina (")
            elif pre:
                agg["distinta_assente_pre"] += 1
        agg["striscia_attacco_difesa"] += m.group(1).count('id="attacco-difesa"')
        agg["striscia_verdetto_oltre"] += m.group(1).count(
            "ha il confronto offensivo migliore")
        agg["striscia_verdetto_entro"] += m.group(1).count("entro il rumore del campione")
        # la dichiarazione della distinta non ancora pubblicata può stare dopo il punto in
        # cui il regex dei pannelli taglia il corpo: si conta sulla sezione intera
        agg["distinta_dichiarata_assente"] += m.group(1).count(
            "non ha ancora pubblicato la distinta")

    # righe Understat a ridosso del calcio d'inizio: sono gare descritte che il taglio
    # «date < before» lascerebbe entrare nel campione della loro stessa scheda; la finestra
    # di season_xg le esclude (docs/76 §1) e l'invariante [44] lo verifica sul reso
    from fda.teams import canonical
    fin = fx[fx.status == "finished"]
    contam = 0
    for r in fin.itertuples(index=False):
        for tname in (r.home_name, r.away_name):
            rows = us[(us.team_name.map(canonical) == canonical(tname))
                      & (us._d < r.ko) & (us._d >= r.ko - pd.Timedelta(hours=24))]
            contam += len(rows)

    out = ["AUDIT CARD «LE DUE SQUADRE» — sito corrente", "=" * 56]
    for k in sorted(agg):
        out.append(f"{k:36s} {agg[k]}")
    out.append(f"\nrighe Understat a ridosso del kickoff (escluse dalla finestra): {contam}")
    out.append(f"assenti senza minuti in stagione: {len(no_min)}")
    if casi_forma:
        out.append("riquadri senza forma e senza dichiarazione:")
        out += [f"  {mid}: {nm}" for mid, nm in casi_forma]
    if silenziosi:
        out.append("pannelli pre senza infermeria né dichiarazione:")
        out += [f"  {mid}: {nm}" for mid, nm in silenziosi]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
