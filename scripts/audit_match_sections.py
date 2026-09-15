"""Censimento misurato dei contenuti della scheda partita (verifica sezione per sezione).

Misura, sulle pagine generate in ``site/partite/*.html`` e sui Parquet di
``data/processed/``, lo stato dei punti verificati uno per uno dalla direttiva
«accurate, intuitive, precise, profonde, di qualità e logica» (docs/20):

1. Analisi pre-partita        → numero di righe narrative per lega (parità) + qualifiche assenze
2. Previsione del modello     → riga n_train formattata con separatore delle migliaia
3. Risultati esatti           → riga di copertura dei 6 punteggi mostrati
4. Come nasce questa probabilità → etichetta del passo Elo vs ricetta di produzione (tilt)
5. Scontro tattico            → tooltip xG con fonte reale; righe-quota azione/palle inattive
6. Fatti rilevanti            → (censimento presenza, già coperta da verify_site)
7. Come arrivano              → righe «punti vs attesi» con tendenza in direzione opposta
8. Confronto di stagione      → (coperto da verify_site: valori identici alla classifica)
9. Contesto                   → etichetta della coda della matrice («almeno una delle due squadre»)
10. Verifica approfondita     → nessun numero di controlli scritto a mano; gerarchia h2/h3

Sintesi della riga di testa (hero): margine coerente con le percentuali stampate.

Uso: ``.venv/bin/python -m scripts.audit_match_sections [site_dir]`` — stampa solo
riepiloghi (nessun dato grezzo), pensato per essere ri-eseguito dopo ogni intervento.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed"


def _league_map() -> dict[int, str]:
    """match_id → chiave di lega (via league_id FotMob e config/leagues.yaml)."""
    from fda.config import leagues

    id2key = {lg.fotmob_id: lg.key for lg in leagues()}
    fx = pd.read_parquet(DATA / "fixtures.parquet")
    return {int(m): id2key.get(int(l), "?") for m, l in
            zip(fx.match_id, fx.league_id, strict=True)}


def _hero_margin(page: str) -> tuple[int, int, float] | None:
    """(percentuale favorito stampata, percentuale seconda, margine pubblicato)."""
    m = re.search(r"hero-pick.*?<strong>[^<]*<em>(\d+)%</em></strong>"
                  r".*?\+(\d+(?:,\d+)?) punti sul secondo — [^<]*? (\d+)%", page, re.DOTALL)
    if not m:
        return None
    top, margin, second = int(m.group(1)), float(m.group(2).replace(",", ".")), int(m.group(3))
    return top, second, margin


def main() -> int:
    site = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    pages = sorted((site / "partite").glob("*.html"))
    if not pages:
        print(f"nessuna pagina in {site}/partite — eseguire prima `fda build`")
        return 1
    league_of = _league_map()

    n = len(pages)
    stats: dict[str, int] = {}
    narr_rows: dict[str, list[int]] = {}
    peso: dict[str, int] = {}
    assenze: dict[str, int] = {}
    margin_seen = margin_bad = 0
    margin_examples: list[str] = []

    for f in pages:
        try:
            mid = int(f.stem)
        except ValueError:
            continue
        lg = league_of.get(mid, "?")
        txt = f.read_text(encoding="utf8")
        pre = "Analisi pre-partita" in txt  # schede pre-partita (sintesi hero)

        def k(key: str, hit: bool) -> None:
            if hit:
                stats[key] = stats.get(key, 0) + 1

        # #10/§2 — numero di controlli scritto a mano
        k("conta_controlli_manuale", bool(re.search(r"controlla [\d.]+ numeri", txt)))
        # #1/§4 — passo Elo etichettato come media
        k("passo_media_elo", "Media con i rating Elo" in txt or "Media pesata con i rating Elo" in txt)
        k("passo_tilt", "inclina" in txt)
        # #3/§5 — tooltip xG che dichiara solo FotMob
        k("tooltip_xg_solo_fotmob", "media stagionale FotMob" in txt)
        # #4/§5 — righe xG split in valori assoluti (da sostituire con quote)
        k("xg_split_assoluti", "xG azione manovrata / gara" in txt)
        k("xg_split_quote", "xG da azione manovrata (quota" in txt)
        # #6 — notazione λ con trattino vs totale esplicito
        k("lambda_trattino", bool(re.search(r"\d,\d+–\d,\d+</b><span>gol attesi", txt)))
        k("lambda_totale", "gol attesi totali" in txt)
        # #7 — segnale DC/Elo senza soggetti
        k("segnale_senza_soggetti", "scarto " in txt and "DC ed Elo sullo stesso preferito" not in txt)
        k("segnale_esplicito", "DC ed Elo sullo stesso preferito" in txt or "Preferiti diversi:" in txt)
        # #8 — n_train senza separatore migliaia
        k("ntrain_senza_separatore", bool(re.search(r"\b\d{4,}\s+(?:partite|gare)\b", txt)))
        # #9 — copertura dei 6 risultati esatti
        k("copertura_risultati", "coprono il" in txt and "delle 100 partite" in txt)
        # #11 — etichetta coda matrice
        k("coda_matrice_vaga", "Coda 6+ gol" in txt)
        k("coda_matrice_esplicita", "Almeno una delle due squadre" in txt)
        # #12 — marcatore del valore stabilizzato
        k("shrunk_senza_marcatore", "valore stabilizzato" not in txt and "<br><span class=\"mut small\" title=\"Valore stabilizzato" in txt)
        k("shrunk_marcatore", "◎" in txt)
        # #13 — profondità narrativa per lega
        if pre:
            m = re.search(r'<h2>Analisi pre-partita</h2>\s*.*?<ul class="narr">(.*?)</ul>', txt, re.DOTALL)
            if m:
                narr_rows.setdefault(lg, []).append(len(re.findall(r"<li>", m.group(1))))
            peso[lg] = peso.get(lg, 0) + txt.count("giocatore di peso") + txt.count("giocatori di peso")
            assenze[lg] = assenze.get(lg, 0) + len(re.findall(r"Assenze [^<]*?:", txt))
        # #14 — gerarchia delle due card figlie di «Verifica approfondita»
        k("figlie_h2", "<h2>Matrice dei punteggi</h2>" in txt)
        k("figlie_h3", "<h3>Matrice dei punteggi</h3>" in txt)
        # #5 — margine coerente con le percentuali stampate
        hm = _hero_margin(txt)
        if hm:
            top, second, margin = hm
            margin_seen += 1
            if abs((top - second) - margin) > 0.15:
                margin_bad += 1
                if len(margin_examples) < 5:
                    margin_examples.append(f.stem)

    print(f"pagine esaminate: {n}")
    print("— contatori sulle pagine —")
    for key in sorted(stats):
        print(f"  {key:28s} {stats[key]:5d}")
    print("— #5 margine hero —")
    print(f"  righe lette: {margin_seen} · incoerenti (|stampato−pubblicato|>0,15): {margin_bad}"
          + (f" · es. {margin_examples}" if margin_examples else ""))
    print("— #13 righe narrative «Analisi pre-partita» per lega (media/min/max, n schede) —")
    vals = []
    for lg in sorted(narr_rows):
        v = narr_rows[lg]
        media = sum(v) / len(v)
        vals.append(media)
        print(f"  {lg:5s} {media:4.1f} / {min(v)} / {max(v)}  (n={len(v)}) · "
              f"«giocatore di peso» nelle assenze: {peso.get(lg, 0)} su {assenze.get(lg, 0)} righe-assenze")
    if vals:
        media_gen = sum(vals) / len(vals)
        spread = max(vals) - min(vals)
        print(f"  divario max−min fra medie di lega: {spread:.1f} righe (media generale {media_gen:.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
