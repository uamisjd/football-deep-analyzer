# 19 — Audit totale in tre aree (14/09/2026)

Audit completo richiesto in tre macro-aree: **1. quantitativa** (dati e logica matematica),
**2. qualitativa** (contenuti, struttura, architettura informativa), **3. visiva e interfaccia**.
Formato per ogni punto: **Osservato → Misura → Impatto → Soluzione pronta → Verifica**.

---

## 0. Metodo, riproducibilità, limiti dichiarati

| Voce | Valore misurato in questa sessione |
|---|---|
| Test | `pytest` **176 passed** (21,1 s) |
| Ruff | `ruff 0.16.7` → **145** rilievi (baseline storica 47 con ruff più vecchio: il set di regole è cresciuto, non il codice) |
| Build sito | `fda build` OK in ~140 s → **4.128 pagine**, **249 MB** |
| Audit interno | `scripts/verify_site.py` → **0 problemi su 11.590 controlli** |
| Sandbox | rete limitata a `github.com`/`api.github.com` + PyPI. **Nessun browser headless installabile** (`playwright install --with-deps chromium` fallisce: mancano `libnss3`, `libpango`). Tutto ciò che è "visivo" qui è verificato **staticamente sul CSS/HTML generato**, non renderizzato. |
| Dati usati | `data/processed/*.parquet` (versionati) + 21 CSV scaricati dal mirror GitHub delle quote (3,4 MB, `/tmp/odds/`) |

**Regola rispettata**: ogni numero qui sotto è riproducibile con i comandi indicati. Dove una misura
non è stata possibile (rendering reale, Lighthouse, chiamate live a FotMob) è scritto **NON VERIFICATO**
e la verifica va fatta in GitHub Actions.

**Tre verdetti onesti prima di tutto** (per non vendere difetti che non ci sono):

1. **Parità post-partita fra le 7 leghe: 100,0%** su 6 tabelle (`team_stats`, `shots`, `events`,
   `momentum`, `player_stats`, `match_info`) — l'obiettivo di `docs/00 §F` è raggiunto sul post-gara.
2. **Nessuna perdita di traduzione**: 0 `nan`, 0 `None`, 0 `undefined`, 0 triple `—/—/—` in 4.128 pagine.
   I 17 "residui inglesi" trovati da una scansione regex sono tutti nomi propri
   (`AZ Alkmaar`, `Vennegoor of Hesselink`, `The Odds API`, `shots` come nome tabella).
3. **Tutti i 12.089 `<svg>` hanno già `aria-hidden`/`role`** e non ci sono `<img>` nel sito:
   il lavoro di accessibilità sulle icone è fatto.

---

## Indice dei riscontri (33 punti)

### Area 1 — quantitativa

| § | Riscontro | Sev. | Misura chiave |
|---|---|---|---|
| 1.1 | Il modello non è mai stato confrontato col mercato su 5 leghe su 7; quando lo si fa, perde | **P0** | RPS 0,19803 vs 0,18843 · Δ **+0,00960** IC95 [+0,00794; +0,01126] · peggio in **7/7** |
| 1.2 | Diagnosi: sottostima sistematica dei favoriti | **P0** | decile 10: 0,728 previsto vs **0,799** osservato |
| 1.3 | Correzione γ-sharpening **testata e respinta** | — | griglia onesta: IC [−0,001037; **+0,000203**], 4/7 leghe |
| 1.4 | La griglia degli iperparametri non è pre-registrata | P1 | stesso esperimento: passa a γ≤1,12, non passa a γ≤1,40 |
| 1.5 | *Accuratezza* mescola 4 versioni del modello | **P0** | 84 gare: **3** correnti, 12 calibrate, 72 no |
| 1.6 | Baseline naive hard-coded 45/27/28 | P1 | Δ gonfiato fino a **+0,00205** (ITA1) |
| 1.7 | Griglia di calibrazione 1,02 < produzione 1,0401 | P1 | il valore attivo è fuori dalla griglia esplorata |
| 1.8 | Proiezioni: precisione falsa, TOP_N fisso, tie-break, `neutral` | P1 | SE 0,5 pp pubblicata a 0,1 pp (**5×**) |
| 1.9 | Doppia chance incoerente con l'1X2 | P1 | **60 righe** |
| 1.10 | Shrinkage per-90 con prior nell'unità sbagliata | P1 | ~**6×** troppo debole sui tiri |
| 1.11 | Verificato e corretto (9 controlli) | — | xGOT 99,6%, parità post-gara 100% |

### Area 2 — qualitativa

| § | Riscontro | Sev. | Misura chiave |
|---|---|---|---|
| 2.1 | La colonna "Richieste" di *Stato fonti* è cumulativa | **P0** | FotMob 19→138 monotono; NED1/POR1 accreditati di Understat mai chiamato |
| 2.2 | ESPN standings: 403 cronico senza backoff | P1 | 7 richieste/run sprecate, **7 avvisi fissi su 28 righe** |
| 2.3 | Open-Meteo "OK, 0 richieste" non distinguibile da "non eseguito" | P1 | fallback dichiarato P0 non osservabile |
| 2.4 | Il "7 giorni" scritto in 4 punti, default CLI = 3 | P1 | `fda collect` + `fda build` → 4 giorni di schede mancanti |
| 2.5 | Curiosità: 34% dei fatti FotMob scartati in silenzio | P1 | **685/2.014**; **75 schede (20%)** con <3 |
| 2.6 | Etichette arbitro assolute su leghe diverse + campioni da 6 gare | P1 | POR1 media **5,04** vs soglia "molto severo" 5,0 |
| 2.7 | `info.html`: claim presunto e definizione contraddetta | P1 | "0,25≈casuale" vs 0,2339 pubblicato; "0,19-0,20" → misurato **0,1884** |
| 2.8 | `narrative()`: tre frasi che si leggono come log | P2 | "ha −3,0 punti", "Assenze Inter: 3 —", "nettamente favorito (60%)" |
| 2.9 | `404.html` assente + 4 difetti di sitemap | P1 | home duplicata, 7 leghe mancanti, `[:5000]`, lastmod = build |
| 2.10 | Docs: 8 documenti non elencati; "7.474 giocatori" doppio conteggio | P2 | pagine reali **3.737** |
| 2.11 | `verify_site.py`: 11.590 controlli, **0** invarianti di pubblicazione | **P0** | tutti i difetti 1.5/1.9/3.3/3.4 sono passati con "0 problemi" |
| 2.12 | Due fonti per lo stesso dato (5 casi) | P2 | causa radice di §1.8d, §2.4, §2.6, §3.3 |

### Area 3 — visiva e interfaccia

| § | Riscontro | Sev. | Misura chiave |
|---|---|---|---|
| 3.1 | CSS inline duplicato 4.128 volte | **P0** | **144,4 MB su 248,3 MB (58%)**; 65% di ogni scheda giocatore |
| 3.2 | ✅ Tema chiaro: 3 testi **invisibili** (V della forma, selezione, punteggio più probabile) + fallback OS senza 18 token | **P0** | peggio **1,02:1**; la barra 1X2 ospite a **2,92:1** in **entrambi** i temi |
| 3.3 | ✅ Barre 1X2 che sommano 99/101 — erano **tre** barre, non due | **P0** | **565/2.152** previsioni (26,3%); ora 0 su 565 barre pubblicate |
| 3.4 | ✅ Barre dei gol oltre il contenitore + didascalia che dichiarava «90%» per un intervallo 10°-90° | **P0** | **9 barre** su 2.152 previsioni (max **183%**); copertura vera media **87,4%** |
| 3.5 | ✅ Palette chiara ricalcolata su 4 superfici | **P0** | da **21** coppie sotto AA a **0**; 14 test nuovi senza browser |
| 3.6 | 0 skip-link, 0 `<th scope>` su 99.839, salto h2→h4 ovunque | P1 | **4.128/4.128** pagine |
| 3.7 | 62 selettori CSS duplicati (fix accodate, non integrate) | P1 | bordo header scuro in tema chiaro |
| 3.8 | Colori hard-coded fuori dai token (in parte già risolti con §3.2) | P2 | 66 occorrenze → **19**; 35 colori → **14** |
| 3.9 | Font esterni: 3 richieste a Google su ogni pagina | P2 | render-blocking + terza parte GDPR |
| 3.10 | `prossime.html` 1.513 KB, filtro che ricalcola a ogni tasto | P1 | 1.987 card in una pagina |
| 3.11 | Layout 320px: 8 regole OK, 4 aspetti **NON VERIFICATI** (no browser) | P2 | `.match-open` a 11px candidato sotto i 44 px |

---

# AREA 1 — ANALISI QUANTITATIVA (dati e logica matematica)

## 1.1 [P0] Il modello non è mai stato confrontato con il mercato su 5 leghe su 7 — e quando lo si fa, perde

**Osservato.** `data/processed/history.parquet` ha le colonne `odds_home/odds_draw/odds_away`
popolate **solo per NED1 (754 righe) e POR1 (765)**: **0 righe per le 5 grandi leghe**.

```
$ python -c "import pandas as pd;h=pd.read_parquet('data/processed/history.parquet');\
print(h.groupby('league_key')['odds_home'].apply(lambda s: pd.to_numeric(s,errors='coerce').notna().sum()))"
ENG1 0 · ESP1 0 · FRA1 0 · GER1 0 · ITA1 0 · NED1 754 · POR1 765      → 1.519 / 7.387 (20,6%)
```

**Causa precisa** (`src/fda/sources/history.py:59-72`): `datahub_base` punta a
`datasets/football-datasets`, mirror **senza quote**; `football-data.co.uk` (che le quote le ha)
è usato **solo se il primo fallisce**, mai come arricchimento. Il mirror dedicato già configurato
per NED1/POR1 (`huhao930422-debug/football-odds-mirror`) **contiene in realtà tutte e 7 le leghe**:
verificato via API GitHub, 21 CSV (7 leghe × 2324/2425/2526), tutti con colonne `PSCH/PSCD/PSCA`
(Pinnacle chiusura), `B365>2.5`, handicap asiatico. Ultimo push 2026-09-11.

**Misura (nuova, fatta in questa sessione).** Ho scaricato i 21 CSV e li ho agganciati a
`backtest.parquet` con la funzione di progetto `fda.teams.canonical()` (alias football-data → nomi FotMob):

| Passo | Valore |
|---|---|
| Righe quote scaricate | **7.092** (7 leghe × 3 stagioni) |
| Aggancio al backtest | **5.543 / 5.815 = 95,3%** (con nomi esatti scendeva a 2.330: `canonical()` è decisivo) |
| Valutabili con Pinnacle chiusura valida | **4.372** |
| **RPS modello** | **0,19803** |
| **RPS mercato (Pinnacle de-vigged)** | **0,18843** |
| **Δ = modello − mercato** | **+0,00960**, IC95% bootstrap appaiato **[+0,00794; +0,01126]** → interamente positivo |

Per lega (il modello è **peggio in 7 su 7**, non è un caso locale):

| Lega | n | modello | mercato | Δ |
|---|---|---|---|---|
| ENG1 | 757 | 0,19932 | 0,19038 | **+0,00893** |
| ESP1 | 714 | 0,19928 | 0,18823 | **+0,01104** |
| FRA1 | 544 | 0,21141 | 0,20269 | **+0,00872** |
| GER1 | 538 | 0,20576 | 0,19357 | **+0,01218** |
| ITA1 | 748 | 0,19552 | 0,18671 | **+0,00881** |
| NED1 | 532 | 0,19119 | 0,18051 | **+0,01067** |
| POR1 | 539 | 0,18354 | 0,17658 | **+0,00696** |

Sui mercati gol (n=5.543): **Over 2,5 Brier modello 0,24436 · mercato 0,23759 · base 0,24796.**

**Impatto quantificato.** Il sito dice «i bookmaker si attestano intorno a 0,19-0,20»: era una
stima **presunta** (violazione di `docs/00 §B2`). Ora è **misurata: 0,18843**. Lettura onesta della
posizione del progetto:

```
base naive 0,23024  →  mercato 0,18843  →  modello 0,19803
distanza naive→mercato = 0,04181 ; il modello ne chiude 0,03221 (77%) ; ne resta 0,00960 (23%)
```

Il modello è **molto meglio del caso** (−0,032 RPS) ma **significativamente peggio del mercato**
(+0,0096 RPS, IC interamente positivo). Senza questo dato il progetto non può sapere se sta
migliorando verso il livello giusto: oggi l'unico riferimento pubblicato è la base naive, che è
un avversario debole.

**Soluzione A (raccomandata, rischio zero sul modello).** Le quote restano **fuori** dalla pipeline
di addestramento: diventano solo un **riferimento esterno misurato**, riproducibile in CI.
Nuovo file `scripts/benchmark_quote.py` (codice completo, già eseguito in questa sessione):

```python
"""Benchmark modello vs quote di chiusura Pinnacle (7 leghe x 3 stagioni).

Scarica i CSV dal mirror gia' usato per NED1/POR1 e li confronta con le previsioni
fuori campione salvate in data/processed/backtest.parquet. Le quote NON entrano nel
modello: sono solo il riferimento esterno con cui misurare la distanza dal mercato.
Uso:  python scripts/benchmark_quote.py [--json docs/_benchmark_quote.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fda.models.predict import outcome_index          # noqa: E402
from fda.teams import canonical                       # noqa: E402

BASE = "https://raw.githubusercontent.com/huhao930422-debug/football-odds-mirror/main/data"
DIRS = {"ENG1": "premier-league", "ESP1": "la-liga", "FRA1": "ligue-1", "GER1": "bundesliga",
        "ITA1": "serie-a", "NED1": "eredivisie", "POR1": "primeira-liga"}
SEASONS = ("2324", "2425", "2526")
CACHE = Path("data/cache/odds")


def scarica(http=None) -> pd.DataFrame:
    from fda.http import HttpClient
    http = http or HttpClient(name="odds-mirror", rate_limit_s=1.0, max_requests=40)
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for lg, d in DIRS.items():
        for s in SEASONS:
            url = f"{BASE}/{d}/season-{s}.csv"
            f = CACHE / f"{d}-{s}.csv"
            if not f.exists():
                f.write_bytes(http.get_bytes(url, ttl_h=24 * 30))
            c = pd.read_csv(f, encoding="latin-1", low_memory=False)
            if not {"PSCH", "PSCD", "PSCA"}.issubset(c.columns):
                continue
            keep = [x for x in ("HomeTeam", "AwayTeam", "FTHG", "FTAG", "PSCH", "PSCD", "PSCA",
                                "B365>2.5", "B365<2.5") if x in c.columns]
            c = c[["Date"] + keep].copy()
            c["lg"] = lg
            c["date"] = pd.to_datetime(c["Date"], dayfirst=True, errors="coerce")
            out.append(c.drop(columns=["Date"]))
    return pd.concat(out, ignore_index=True)


def devig(h, d, a) -> np.ndarray:
    """Quote decimali -> probabilita' senza margine (normalizzazione semplice)."""
    p = np.column_stack([1 / pd.to_numeric(h, errors="coerce"),
                         1 / pd.to_numeric(d, errors="coerce"),
                         1 / pd.to_numeric(a, errors="coerce")])
    ok = np.isfinite(p).all(1) & (p > 0).all(1)
    out = np.full_like(p, np.nan)
    out[ok] = p[ok] / p[ok].sum(1, keepdims=True)
    return out


def rps(P: np.ndarray, o: np.ndarray) -> np.ndarray:
    return ((np.cumsum(P, 1) - np.cumsum(o, 1)) ** 2).sum(1) / 2.0


def paired_bootstrap(delta: np.ndarray, draws: int = 4000, seed: int = 11):
    from fda.models.lab import paired_bootstrap as pb
    return pb(np.asarray(delta, float), draws=draws, seed=seed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="scrive il risultato in questo file")
    args = ap.parse_args()

    bt = pd.read_parquet("data/processed/backtest.parquet")
    od = scarica()
    btd = pd.to_datetime(bt.date)
    bt["date"] = (btd.dt.tz_localize(None) if getattr(btd.dt, "tz", None) else btd).dt.normalize()
    od["HomeTeam"] = od.HomeTeam.map(canonical).str.strip()
    od["AwayTeam"] = od.AwayTeam.map(canonical).str.strip()
    m = bt.merge(od, left_on=["league_key", "date", "home", "away"],
                 right_on=["lg", "date", "HomeTeam", "AwayTeam"], how="inner")

    P = devig(m.PSCH, m.PSCD, m.PSCA)
    M = np.column_stack([m.p_home, m.p_draw, m.p_away]).astype(float)
    o = np.eye(3)[[outcome_index(int(h), int(a)) for h, a in zip(m.FTHG, m.FTAG)]]
    ok = np.isfinite(P).all(1)
    P, M, o, mm = P[ok], M[ok], o[ok], m[ok]
    d = rps(M, o) - rps(P, o)
    lo, hi = paired_bootstrap(d)
    per_lega = (pd.DataFrame({"lg": mm.league_key.values, "d": d, "m": rps(M, o), "p": rps(P, o)})
                .groupby("lg").agg(n=("d", "size"), modello=("m", "mean"),
                                   mercato=("p", "mean"), delta=("d", "mean")).round(5))
    res = {"n_agganciate": int(len(m)), "n_valutate": int(ok.sum()),
           "rps_modello": float(rps(M, o).mean()), "rps_mercato": float(rps(P, o).mean()),
           "delta": float(d.mean()), "ic95": [float(lo), float(hi)],
           "leghe_vinte": int((per_lega.delta < 0).sum()), "per_lega": per_lega.to_dict("index")}
    print(json.dumps({k: v for k, v in res.items() if k != "per_lega"}, indent=2))
    print(per_lega.to_string())
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

Job CI (nuovo `.github/workflows/benchmark.yml`, mensile: le quote di chiusura cambiano solo a
stagione finita, non serve giornalmente):

```yaml
name: benchmark-quote
on:
  workflow_dispatch:
  schedule: [{cron: "20 4 3 * *"}]          # il 3 del mese
jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -e .[dev]
      - run: python scripts/benchmark_quote.py --json docs/_benchmark_quote.json
      - uses: actions/upload-artifact@v4
        with: {name: benchmark-quote, path: docs/_benchmark_quote.json}
```

**Soluzione B (solo se si vogliono le quote dentro il laboratorio).** 5 righe in
`config/leagues.yaml` (una per lega grande, stesso mirror già usato per NED1/POR1):

```yaml
   - key: ITA1
     ...
     datahub_dir: "serie-a"
+    datahub_base: "https://raw.githubusercontent.com/huhao930422-debug/football-odds-mirror/main/data"
```
(idem per ENG1/premier-league, ESP1/la-liga, GER1/bundesliga, FRA1/ligue-1).

⚠️ **Questa modifica rompe un test che codifica la decisione opposta**:
`tests/test_models.py:79-90` `test_history_uses_datahub_base_override` afferma
`assert ita.datahub_base is None` e che ITA1 resti su `datasets/football-datasets`. Va aggiornato
insieme alla config, dichiarando il cambio di rotta:

```python
-    # le 5 grandi leghe restano sul mirror datasets/football-datasets (nessun datahub_base)
-    ita = league("ITA1")
-    assert ita.datahub_base is None
-    hc2 = HistoryClient(client=_Stub())
-    hc2.datahub_csv(ita, 2025)
-    assert "datasets/football-datasets" in calls["url"] and calls["url"].endswith("/serie-a/season-2526.csv")
+    # dal 2026-09-14 anche le 5 grandi leghe usano il mirror con le quote di chiusura:
+    # i risultati sono gli stessi (stesso formato football-data), in piu' arrivano PSCH/PSCD/PSCA
+    # che servono solo come riferimento esterno (docs/19 §1.1), mai come feature del modello.
+    ita = league("ITA1")
+    assert ita.datahub_base and "football-odds-mirror" in ita.datahub_base
+    hc2 = HistoryClient(client=_Stub())
+    hc2.datahub_csv(ita, 2025)
+    assert calls["url"].endswith("/serie-a/season-2526.csv")
```

Rischio da mettere a verbale: `huhao930422-debug/football-odds-mirror` è un repo personale
(0 stelle), copia di football-data.co.uk. Se sparisce, `history.py` ricade su
`football-data.co.uk` (secondary già presente) e su `datasets/football-datasets`: **la soluzione A
non ha questo rischio** perché non tocca la pipeline.

**Verifica.** `python scripts/benchmark_quote.py` → deve stampare `n_valutate ≈ 4372`,
`delta ≈ +0.0096`, IC95 interamente positivo. In CI (rete reale) il numero può variare di ±0,0005
se il mirror viene aggiornato; la struttura del risultato no.

---

## 1.2 [P0] Diagnosi del divario: il modello sottostima i favoriti di 7 punti nel decile alto

**Osservato.** Decili della probabilità che il modello assegna all'esito che indica come più probabile
(n=4.372, stesse partite del §1.1):

| Decile | n | p modello | p osservata | scarto |
|---|---|---|---|---|
| 1 | 438 | 0,365 | 0,381 | −0,016 |
| 2 | 437 | 0,390 | 0,355 | **+0,035** (sovraconfidenza) |
| 3 | 437 | 0,412 | 0,423 | −0,011 |
| 4 | 437 | 0,435 | 0,444 | −0,009 |
| 5 | 437 | 0,461 | 0,501 | −0,040 |
| 6 | 437 | 0,489 | 0,522 | −0,033 |
| 7 | 437 | 0,523 | 0,556 | −0,033 |
| 8 | 437 | 0,566 | 0,620 | **−0,054** |
| 9 | 437 | 0,623 | 0,675 | **−0,052** |
| 10 | 438 | 0,728 | **0,799** | **−0,071** |

**Impatto.** Il difetto non è casuale né simmetrico: dai decili 5→10 il modello è
**sistematicamente sotto-confidente** (−3,3 → −7,1 punti), mentre sul decile 2 è sopra.
È la firma di una probabilità **troppo piatta**: il modello "mescola" verso il pareggio dove il
mercato invece concentra sul favorito. Conseguenza pratica già misurata: la previsione del pareggio
è corretta (25,9% previsto vs 25,6% osservato, ottimo) ma l'RPS — che punisce la distanza cumulativa
— resta sopra il mercato proprio perché le code sono compresse.

**Soluzione.** Vedi §1.3: ho testato la correzione ovvia (sharpening) e **non passa il protocollo**.
La strada corretta è aggiungere la **ricalibrazione del vettore 1X2** come candidato del laboratorio
(stessa infrastruttura di `calibration.py`, che oggi corregge solo λ e ρ), con griglia
**pre-registrata** (§1.4):

```python
# src/fda/models/predict.py — nuovo passo DOPO calibrated_prediction, PRIMA dei mercati derivati
def recalibrate_1x2(p: tuple[float, float, float], tau: float = 1.0) -> tuple[float, float, float]:
    """Riscalatura di temperatura sul vettore 1X2 (tau>1 concentra, tau<1 appiattisce).

    Motivo misurato in docs/19 §1.2: sui decili alti il modello assegna 0,728 dove si osserva
    0,799. La temperatura e' il correttore minimo che non cambia l'ordine degli esiti (argmax
    invariante) e quindi non tocca ne' l'esito indicato ne' i mercati derivati dalla matrice.
    tau viene scelto SOLO walk-forward dal laboratorio (docs/00 §D): mai tarato sul campione
    su cui poi si misura.
    """
    if tau == 1.0:
        return p
    q = np.power(np.clip(np.asarray(p, float), 1e-9, 1.0), tau)
    return tuple((q / q.sum()).tolist())
```

Da misurare con `fda lab` prima di qualunque adozione. Se non passa, **non si adotta** (come §1.3).

**Verifica.** Dopo l'eventuale adozione: rieseguire la tabella decili; l'obiettivo è
|scarto| ≤ 0,02 su tutti i decili e Δ vs mercato < +0,005.

---

## 1.3 Correzione testata e **respinta**: sharpening γ sul rapporto delle λ

**Osservato (esperimento fatto in questa sessione).** Ipotesi: se il modello è troppo piatto,
esponendo il rapporto λ_home/λ_away a γ>1 (a totale gol invariato) si concentrano le code.
Walk-forward 5 fold, griglia γ ∈ [0,94 … 1,12] passo 0,02, scelta del γ sul fold di addestramento:

| Griglia | γ scelto | ΔRPS walk-forward | IC95% | Leghe vinte | Verdetto protocollo |
|---|---|---|---|---|---|
| stretta [0,94; 1,12] | 1,12 (in 5/5 fold) | **−0,000457** | [−0,000769; −0,000145] | **6/7** | passerebbe |
| onesta [1,00; 1,40] | 1,24 | −0,000417 | **[−0,001037; +0,000203]** | **4/7** | **NON passa** |

In-sample il ottimo è γ≈1,20 (RPS 0,19811 vs 0,19876), ma allo stesso γ:
il **Brier dei mercati gol peggiora di +0,00014** e il **pareggio previsto scende a 25,20%**
contro 25,6% osservato — cioè si rompe una proprietà che il progetto ha faticosamente ottenuto
(25,9% vs 25,6%, pubblicato in `accuratezza.html`).

**Verdetto: candidato NON promosso.** Il guadagno RPS (≈ −0,0004 … −0,0007) è al limite della
significatività, dipende dalla griglia scelta, e si paga in calibrazione del pareggio e nei mercati gol.
**Va registrato come "testato e respinto"** in `model_lab.parquet` (o almeno in questo documento)
perché una sessione futura non perda tempo a ritestarlo.

**Impatto del punto.** Nessuno sul prodotto: serve a chiudere una strada. Il valore è metodologico (§1.4).

---

## 1.4 [P1] Difetto del protocollo: la griglia degli iperparametri non è pre-registrata

**Osservato.** Lo stesso identico esperimento (§1.3) **passa** i criteri di `docs/00 §D`
(IC95 interamente negativo + 6/7 leghe) se la griglia si ferma a 1,12 e **non li passa** se arriva
a 1,40. Il criterio di promozione è quindi sensibile a una scelta che oggi nessuno documenta:
**l'insieme dei valori provati**.

**Impatto.** Con 22 candidati già in `CANDIDATES` e griglie non dichiarate, la probabilità di
trovare *qualcosa* con IC<0 per caso cresce a ogni tentativo (problema classico delle comparazioni
multiple). Il laboratorio è il presidio più importante del progetto: se la griglia è libera,
il presidio è aggirabile — senza cattiva fede, solo scegliendo "la griglia ragionevole".

**Soluzione.** Tre righe di disciplina in `src/fda/models/lab.py`:

```python
 @dataclass(frozen=True)
 class Candidate:
     """Un concorrente del laboratorio: famiglia, iperparametri e, per le miscele, il peso."""
 
     key: str
     label: str
     kind: str                                    # goals | rating | blend | production
     family: str
     params: dict[str, Any] = field(default_factory=dict)
+    #: griglia PRE-REGISTRATA per i candidati che cercano un iperparametro: va dichiarata qui,
+    #: prima di guardare il risultato, e finisce in model_lab.parquet. Senza questa, "IC95<0"
+    #: si ottiene anche solo accorciando la griglia al punto giusto (caso reale: docs/19 §1.3-1.4).
+    grid: tuple[float, ...] = ()
```

e in `summarize()` (che già scrive `model_lab.parquet`) aggiungere la colonna
`grid_dichiarata = "|".join(map(str, cand.grid))` più `n_tentativi` = numero di candidati della
stessa famiglia provati nella stessa run. Regola da scrivere in `docs/00 §D`:

> Un candidato che cerca un iperparametro dichiara la griglia **nel codice**, prima del run.
> Se la griglia cambia, il run precedente resta in `model_lab.parquet` con la sua griglia:
> il confronto onesto è fra griglie dichiarate, non fra risultati scelti.

**Verifica.** `fda lab` produce `model_lab.parquet` con le colonne `grid_dichiarata` e `n_tentativi`
popolate per tutti i candidati; `scripts/verdetto_lab.py` stampa quanti tentativi hanno preceduto
la promozione.

---

## 1.5 [P0] La pagina "Accuratezza" mescola 4 versioni del modello — e le due tabelle sembrano contraddirsi

**Osservato.** `data/processed/predictions.parquet` contiene **2.152 righe di 4 versioni diverse**,
di cui **81 righe stale** (`dc-elo-ens-0.1/0.2/0.3`, ricette abbandonate). `build_accuracy`
(`src/fda/site/build.py:479-503`) prende *l'ultima previsione prima del fischio d'inizio* **senza
filtrare per versione**: la tabella pubblicata oggi (n=84) è composta da

| Segmento | Gare |
|---|---|
| Modello corrente `dc-elo-tilt-0.4` | **3** |
| Con calibrazione attiva (`cal-momenti-1.1`) | **12** |
| Senza calibrazione (ricette precedenti) | **72** |

**Misura dell'effetto.** Brier dei mercati gol sulle stesse 84 gare, per segmento:

| Mercato | tutte (84) | calibrate (12) | non calibrate (72) | tilt-0.4 (3) |
|---|---|---|---|---|
| Over 1,5 | **+0,0138** | +0,0211 | +0,0126 | +0,0689 |
| Over 2,5 | **+0,0155** | −0,0085 | +0,0198 | +0,0456 |
| BTTS | **+0,0211** | +0,0378 | +0,0183 | +0,0451 |

(Δ = Brier modello − Brier base-rate; positivo = peggio della base.)

**Impatto.** La pagina pubblica **nello stesso schermo** due affermazioni opposte:
la tabella "live" dice che il modello **perde contro la base su tutti i mercati gol**
(+0,014 … +0,021 Brier), il backtest subito sotto dice che **vince** (0,2019 vs 0,2127 su 5.815 gare).
Non è una contraddizione del modello: è il **campione live che è per l'86% composto da previsioni
di ricette precedenti, senza calibrazione**. Il lettore non può saperlo, perché la composizione
non è pubblicata. È esattamente il caso che `docs/00 §B2` vuole evitare (numeri non distinguibili
per provenienza).

**Soluzione (2 patch piccole, nessuna modifica al modello).**

1) Pubblicare la composizione del campione. In `build.py`, dentro `build_accuracy` dopo il
calcolo di `summary`:

```python
                 summary.sort(key=lambda r: (r["league"] == "Tutti", r["league"]))
+                # composizione del campione: senza questa riga la tabella live e il backtest
+                # sembrano contraddirsi (docs/19 §1.5). Le 84 gare valutate non sono tutte
+                # del modello corrente: le previsioni restano in archivio per tracciabilita'.
+                from ..models.predict import MODEL_VERSION
+                ver = p["model_version"].astype(str) if "model_version" in p.columns else pd.Series(dtype=str)
+                cal = p.get("calibration_version", pd.Series(index=p.index, dtype=object)).astype(str)
+                composizione = {
+                    "n": int(len(p)),
+                    "corrente": int((ver == MODEL_VERSION).sum()),
+                    "calibrate": int((cal.notna() & (cal != "identity") & (cal != "nan")).sum()),
+                    "versioni": sorted(ver.unique().tolist()),
+                }
```
e passarlo al template:

```python
         self._render("accuracy.html", "accuratezza.html", summary=summary, recent=recent, calib=calib,
-                     markets=markets, ...)
+                     markets=markets, composizione=composizione, ...)
```

`templates/accuracy.html`, subito dopo la tabella riepilogo:

```html
+{% if composizione %}
+<p class="small mut">Composizione del campione: {{ composizione.n }} gare valutate, di cui
+  <b>{{ composizione.corrente }}</b> con il modello corrente ({{ MODEL_VERSION }}) e
+  <b>{{ composizione.calibrate }}</b> con la calibrazione attiva; le altre appartengono a ricette
+  precedenti, tenute in archivio per tracciabilità. Per questo la tabella qui sopra — che cresce di
+  15-20 gare al giorno — può divergere dal backtest fuori campione qui sotto, che invece valuta
+  <b>solo</b> la ricetta corrente su migliaia di gare.</p>
+{% endif %}
```

2) Separare le versioni nell'archivio, senza cancellare niente (le righe storiche servono alla
tracciabilità): aggiungere una colonna `is_current` al momento della lettura e **non** mescolarle
nel riepilogo principale. Minimo indispensabile: il punto (1) sopra.

**Verifica.** Dopo la build, `site/accuratezza.html` deve contenere la frase «di cui 3 con il modello
corrente»; `verify_site.py` va esteso (vedi §2.12) per controllare che `composizione.n` coincida con
la somma degli `n` della tabella riepilogo.

---

## 1.6 [P1] La baseline "naive" pubblicata è hard-coded 45/27/28 e sovrastima il vantaggio del modello

**Osservato.** `src/fda/site/build.py:500`:

```python
naive = np.tile([0.45, 0.27, 0.28], (len(g), 1))
```

**Misura.** Le frequenze reali 1/X/2 misurate su `history.parquet` (7.387 gare) sono
**0,4290 / 0,2567 / 0,3143**, e cambiano per lega. RPS delle due baseline:

| Lega | naive hard-coded 45/27/28 | frequenze reali di lega | il Δ pubblicato è gonfiato di |
|---|---|---|---|
| ENG1 | 0,23310 | 0,23188 | +0,00122 |
| ESP1 | 0,22510 | 0,22506 | +0,00003 |
| FRA1 | 0,23341 | 0,23231 | +0,00109 |
| GER1 | 0,23308 | 0,23172 | +0,00136 |
| ITA1 | 0,23146 | 0,22941 | **+0,00205** |
| NED1 | 0,23078 | 0,23013 | +0,00065 |
| POR1 | 0,23136 | 0,23035 | +0,00101 |

**Impatto.** La colonna «Δ vs naive» di `accuratezza.html` è il **numero che il progetto usa per
dire "il modello batte il caso"**. Oggi è calcolata contro un avversario più debole del necessario:
per la Serie A il vantaggio dichiarato è gonfiato di **0,00205 RPS**, cioè ~6% del vantaggio totale
(Δ pubblicato ITA1 = −0,021 su base 0,2191). Non è un errore grave, ma è un numero **non verificabile
dai dati** — e `docs/00 §B1` chiede esattamente il contrario.

**Soluzione.** Baseline empirica per lega, con fallback sicuro:

```python
+# src/fda/site/build.py — accanto a OUTCOME_LABELS
+NAIVE_FALLBACK = np.array([0.45, 0.27, 0.28])
+
+
+def outcome_freqs(hist: pd.DataFrame) -> dict[str, np.ndarray]:
+    """Frequenze reali 1/X/2 per league_key (+ chiave 'Tutti') misurate su history.parquet.
+
+    Sostituisce il 45/27/28 hard-coded come avversario della colonna 'Δ vs naive':
+    una baseline piu' debole del reale gonfia il vantaggio dichiarato del modello
+    fino a 0,002 RPS (misurato in docs/19 §1.6).
+    """
+    out: dict[str, np.ndarray] = {}
+    if hist is None or hist.empty or not {"home_goals", "away_goals"}.issubset(hist.columns):
+        return out
+    hg = pd.to_numeric(hist["home_goals"], errors="coerce")
+    ag = pd.to_numeric(hist["away_goals"], errors="coerce")
+    ok = hg.notna() & ag.notna()
+    o = np.where(hg[ok] > ag[ok], 0, np.where(hg[ok] == ag[ok], 1, 2))
+    key = hist.loc[ok, "league_key"].to_numpy()
+
+    def _f(mask: np.ndarray) -> np.ndarray:
+        c = np.bincount(o[mask], minlength=3).astype(float)
+        return c / c.sum() if c.sum() >= 30 else NAIVE_FALLBACK
+
+    out["Tutti"] = _f(np.ones(len(o), bool))
+    for k in pd.unique(key):
+        out[str(k)] = _f(key == k)
+    return out
```

```python
     def build_accuracy(self, fx: pd.DataFrame) -> None:
         preds = self.store.read("predictions")
+        base_freqs = outcome_freqs(self.store.read("history"))
+        key_of = {lg.name: lg.key for lg in leagues()}
         summary, recent, calib, markets = [], [], [], []
@@
                 for lg_name, g in list(p.groupby("league")) + [("Tutti", p)]:
                     ...
-                    naive = np.tile([0.45, 0.27, 0.28], (len(g), 1))
+                    # baseline = frequenze reali della lega (o globali per "Tutti"), mai hard-coded
+                    freq = base_freqs.get("Tutti" if lg_name == "Tutti" else key_of.get(lg_name, ""),
+                                          NAIVE_FALLBACK)
+                    naive = np.tile(freq, (len(g), 1))
```

Test da aggiungere (`tests/test_site.py`):

```python
def test_baseline_naive_usa_frequenze_reali():
    hist = pd.DataFrame({"league_key": ["ITA1"] * 4,
                         "home_goals": [2, 1, 0, 3], "away_goals": [0, 1, 2, 1]})
    f = outcome_freqs(hist)
    assert np.allclose(f["Tutti"], [0.5, 0.25, 0.25])     # 2V 1N 1P
    assert np.allclose(f["ITA1"], [0.5, 0.25, 0.25])
    # sotto le 30 gare si resta sul fallback dichiarato, non su frequenze rumorose
    assert np.allclose(outcome_freqs(hist.head(3))["Tutti"], NAIVE_FALLBACK)
```

**Verifica.** Dopo la build, il Δ di Serie A passa da −0,021 a ≈ −0,023 (base 0,2294 invece di 0,2191
sul campione live: il numero esatto dipende dalle 15 gare del campione). La pagina deve dire
«base = frequenze reali della lega (n=3.760 per la Serie A)» invece di «probabilità fisse 45/27/28».

---

## 1.7 [P1] La griglia di calibrazione si ferma a 1,02 ma la produzione usa 1,0401

**Osservato.** `src/fda/models/calibration.py`: `LAMBDA_SCALE_GRID` ha massimo **1,02**, mentre il
fattore attivo pubblicato ovunque (`info.html`, `accuratezza.html`) è **λ×1,040** — **fuori griglia**.
`SCALE_BOUNDS = (0.85, 1.05)` lo consente, ma la *comparazione* che ha scelto il valore si è fermata a 1,02.

**Impatto.** Due conseguenze misurabili: (a) il valore in produzione non è il migliore della griglia
con cui è stato cercato, ma il migliore **dentro un intervallo più stretto** di quello ammesso dai
bounds; (b) `info.html` afferma «λ×1,040 (momenti, 730 giorni, 4.760 gare)» come se fosse il risultato
di una ricerca su [0,85; 1,05], mentre la ricerca si è fermata a 1,02. È un claim più forte dei dati.

**Soluzione.** Allineare griglia e bounds, e pubblicare l'intervallo realmente esplorato:

```python
-LAMBDA_SCALE_GRID = tuple(round(0.90 + 0.01 * i, 2) for i in range(13))     # 0.90 … 1.02
+LAMBDA_SCALE_GRID = tuple(round(SCALE_BOUNDS[0] + 0.01 * i, 2)
+                          for i in range(int((SCALE_BOUNDS[1] - SCALE_BOUNDS[0]) / 0.01) + 1))
+# 0.85 … 1.05: la griglia copre esattamente i bounds dichiarati, cosi' il valore scelto e'
+# davvero il migliore dell'intervallo ammesso e non di un suo sottoinsieme (docs/19 §1.7).
```

Se si preferisce non rieseguire il fit ora (costa un run del laboratorio), la soluzione minima è
**documentare l'intervallo esplorato** in `calibration.parquet` (colonna `grid_max`) e far dire a
`info.html` «λ×1,040 scelto su griglia 0,90-1,02»: un claim più piccolo ma vero.

**Verifica.** `python -c "from fda.models.calibration import LAMBDA_SCALE_GRID as g,SCALE_BOUNDS as b;\
print(min(g),max(g),b)"` → `0.85 1.05 (0.85, 1.05)`.

---

## 1.8 [P1] Proiezioni di stagione: precisione falsa, TOP_N fisso, spareggi incompleti, `neutral` non limitato

**Osservato e misurato** (`src/fda/models/season_sim.py`, `data/processed/season_sim.parquet`, 132 righe):

| # | Difetto | Misura |
|---|---|---|
| a | **Precisione falsa**: `n_sims = 10.000` → errore standard di Monte Carlo fino a **0,5 punti percentuali**, ma `stagione.html` stampa le probabilità con **1 decimale** (0,1 pp) | SE/precisione = **5×**: l'ultima cifra pubblicata è rumore. Es. POR1: gap titolo 0,066 vs SE 0,010 → 6,6σ (qui il segnale è reale, ma in generale la cifra decimale non lo è) |
| b | `TOP_N = 4` costante per tutte le leghe | In Eredivisie/Liga Portugal i posti Champions non sono 4; la riga «Top 4» è etichettata come se avesse lo stesso significato ovunque |
| c | Tie-break **solo differenza reti** | A parità di punti e DR l'ordine è arbitrario (dipende dall'ordine delle squadre nel dataframe): nei campionati reali contano scontri diretti e gol fatti. Effetto sulle probabilità di titolo: piccolo ma non nullo, e **non dichiarato** |
| d | `simulate_league()` **non limita** il fattore `neutral` a [0,6; 2,2], mentre `predict_matches()` sì | Due percorsi dello stesso modello con due regimi di sicurezza diversi: la stessa partita può produrre λ diverse a seconda che arrivi dalla simulazione di stagione o dalla scheda |

**Impatto.** (a) è il più grave sul piano dell'onestà numerica: la pagina «Proiezioni» è l'unica che
pubblica probabilità future aggregate, e lo fa con una cifra decimale che la simulazione non sostiene.
(d) è un'incoerenza di modello che `verify_site.py` non può vedere perché non confronta i due percorsi.

**Soluzione.**

```python
# season_sim.py — (a) arrotondare alla risoluzione che la simulazione sostiene
-N_SIMS = 10_000
+N_SIMS = 10_000
+# con N=10.000 l'errore standard di una probabilita' p e' sqrt(p(1-p)/N): massimo 0,5 pp a p=0,5.
+# Pubblicare il decimale mostrerebbe rumore come informazione. Si stampa il valore intero piu'
+# vicino e, dove la SE lo giustifica (gap > 2*SE), si dichiara il margine.
+MC_SE_MAX = 0.5 * (100.0 / N_SIMS) ** 0.5      # 0,5 pp
+
+
+def mc_se(p: float, n: int = N_SIMS) -> float:
+    """Errore standard di Monte Carlo per una probabilita' stimata su n simulazioni."""
+    return float((max(p, 0.0) * (1 - max(p, 0.0)) / max(n, 1)) ** 0.5)
```

```python
# (b) TOP_N per lega, dalla config (nessun numero inventato: se la lega non lo dichiara, si omette)
-TOP_N = 4
+DEFAULT_TOP_N: int | None = None      # None = la riga "Top N" non viene pubblicata per quella lega
```
con in `config/leagues.yaml` un campo `ucl_spots: 4` / `3` / `2` per lega; dove il campo manca la
riga non compare (regola di `docs/00 §F`: meglio un contenuto onestamente assente di uno sbagliato).

```python
# (c) tie-break dichiarato
-    tab = tab.sort_values(["pts", "gd"], ascending=False)
+    # ordine: punti, differenza reti, gol fatti. Gli scontri diretti NON sono implementati:
+    # e' dichiarato qui e in stagione.html, perche' un tie-break incompleto non dichiarato
+    # sposterebbe probabilita' che il lettore crede esatte (docs/19 §1.8c).
+    tab = tab.sort_values(["pts", "gd", "gf", "team"], ascending=[False, False, False, True])
```

```python
# (d) stessi limiti di sicurezza dei due percorsi
-        lh, la = neutral * lh, neutral * la
+        # predict_matches() limita neutral a [0.6, 2.2]; la simulazione deve usare lo stesso
+        # regime, altrimenti la stessa coppia di squadre produce lambda diverse a seconda
+        # del percorso (docs/19 §1.8d).
+        neutral = float(min(2.2, max(0.6, neutral)))
+        lh, la = neutral * lh, neutral * la
```

`templates/stagione.html`: cambiare `{{ p_title|dec(1) }}` in `{{ p_title|dec(0) }}` e aggiungere
nella legenda «probabilità arrotondate all'unità: con 10.000 simulazioni l'incertezza di Monte Carlo
è ±0,5 punti, quindi il decimale sarebbe rumore».

**Verifica.** Test nuovo: `assert mc_se(0.5) == pytest.approx(0.005, abs=1e-6)`; test di parità:
`simulate_league` e `predict_matches` sulla stessa coppia con `neutral=3.0` devono produrre λ identiche.

---

## 1.9 [P1] 60 righe in cui la doppia chance pubblicata non è coerente con l'1X2

**Osservato.** In `predictions.parquet`/`backtest.parquet` ci sono **60 righe** dove
`max(p_home, p_draw, p_away) ≥ 0,5` ma la doppia chance corrispondente non è `True`
(18 righe della versione corrente con peso di ensemble `w_dc = 0`, 42 di versioni precedenti).

**Impatto.** La doppia chance è un contenuto pubblicato sulla scheda. Un lettore che vede
«1 al 54%» e «doppia chance 1X: no» ha davanti due affermazioni incompatibili per costruzione
matematica (1X = p_home + p_draw ≥ p_home). Non è un problema di modello: è un problema di
**derivazione non controllata**.

**Soluzione.** Assert di coerenza nel punto in cui i mercati derivati vengono costruiti
(`src/fda/models/predict.py`, funzione che produce `p_1x/p_12/p_x2`):

```python
+def _assert_dc_coerente(p: dict[str, float]) -> None:
+    """p_1x/p_12/p_x2 devono essere la somma delle probabilita' 1X2 corrispondenti.
+
+    In archivio ci sono 60 righe (18 della versione corrente con w_dc=0) in cui la doppia
+    chance pubblicata contraddice l'1X2: matematicamente impossibile, quindi derivata da un
+    percorso diverso da quello che la pagina mostra (docs/19 §1.9).
+    """
+    tol = 1e-6
+    for key, idx in (("p_1x", (0, 1)), ("p_12", (0, 2)), ("p_x2", (1, 2))):
+        if p.get(key) is None:
+            continue
+        atteso = p["p_home"] if 0 in idx else 0.0
+        atteso += p["p_draw"] if 1 in idx else 0.0
+        atteso += p["p_away"] if 2 in idx else 0.0
+        if abs(float(p[key]) - atteso) > tol:
+            raise ValueError(f"{key}={p[key]:.4f} incoerente con 1X2 "
+                             f"({p['p_home']:.4f}/{p['p_draw']:.4f}/{p['p_away']:.4f})")
```

Più il controllo permanente in `verify_site.py` (§2.12), che è il posto giusto per intercettare
le righe **già** in archivio senza bloccare la build.

**Verifica.** `python -c "..."` sulle 60 righe → dopo la correzione della derivazione, 0 righe;
`verify_site.py` stampa `[12] coerenza 1X2/doppia chance verificata: 2152`.

---

## 1.10 [P1] Shrinkage dei per-90 dei giocatori: prior applicato con l'unità sbagliata (6× sui tiri)

**Osservato** (`src/fda/site/players.py`). La contrazione verso la media dei pari usa un prior
espresso in **minuti** (`SHRINK_PRIOR = 8` nel modello; qui una costante analoga) ma applicato a
statistiche la cui scala naturale è diversa: per i **tiri** il prior effettivo risulta ~6× più
debole del dovuto, quindi i per-90 dei giocatori con pochi minuti restano **estremi**
(es. 9,0 tiri/90 con 95 minuti giocati pubblicati come se fossero stabili).
Presente anche una funzione **morta**: `p90_shrunk()` non è chiamata da nessun punto del codice.

**Impatto.** 3.745 pagine giocatore; la classifica per-90 è il contenuto principale di
`giocatori_lega.html`. Un prior 6× troppo debole mette in testa alla classifica giocatori con
uno spezzone di partita: è il tipo di errore che il lettore **vede** e che mina la credibilità
dell'intero portale.

**Soluzione.** Un solo helper di empirical Bayes, usato per **tutte** le rate su campione piccolo
(per-90 giocatori, gialli arbitro §2.7, xG per gara a inizio stagione):

```python
# src/fda/site/players.py
-def p90_shrunk(...):     # FUNZIONE MORTA: nessuna chiamata nel repository → eliminare
-    ...
+def shrink_rate(num: float, den: float, pool_rate: float, k: float) -> float:
+    """Contrazione di una rata (num/den) verso la media dei pari con peso k espresso
+    NELLA STESSA UNITA' del denominatore.
+
+    Errore corretto (docs/19 §1.10): il prior era in minuti ma applicato a conteggi per 90,
+    quindi per i tiri risultava ~6 volte piu' debole del dovuto e i per-90 dei giocatori con
+    pochi minuti restavano estremi. Qui den e' esattamente il denominatore della rata
+    (minuti per i per-90, partite per gli arbitri) e k e' "quante unita' di den valgono
+    quanto la media dei pari".
+    """
+    den = float(den or 0.0)
+    k = max(float(k), 0.0)
+    if den <= 0 or k <= 0:
+        return float(pool_rate)
+    return (float(num) + k * float(pool_rate)) / (den + k)
```

Regola di taratura (da scrivere nel docstring, non nel codice): `k` = mediana del denominatore
nel gruppo dei pari × 0,25, cioè un giocatore con un quarto del minutaggio mediano pesa metà
la propria rata e metà la media. Per i tiri in Serie A: minutaggio mediano ≈ 1.800 → **k ≈ 450 minuti**
(oggi il valore effettivo è ≈ 75, da cui il fattore ~6).

**Verifica.** Test: `shrink_rate(9, 95, 12.0/90*95, 450)` deve restituire un valore vicino alla
media dei pari, non 8,5. E su `player_stats.parquet`: il numero di giocatori con minuti < 270
(`SMALL_SAMPLE_MINUTES`) che compaiono nella top-10 per-90 di una lega deve scendere a 0.

---

## 1.11 Verificato e **corretto** (nessun intervento)

| Controllo | Esito |
|---|---|
| Copertura `xGOT` sui tiri | **99,6-99,9%** in tutte e 7 le leghe (28 righe nulle su 8.233): il `fillna(0)` nel calcolo del *finishing* non distorce nulla. Nessun intervento. |
| Parità post-partita fra le 7 leghe | **100,0%** su 6 tabelle (`team_stats`, `shots`, `events`, `momentum`, `player_stats`, `match_info`) — obiettivo `docs/00 §F` raggiunto |
| Dotplot quantile dei gol | verificato da `verify_site.py` [9] su 2.152 partite: punti, colonne, moda, mediana, intervallo 10-90% e coda coincidono con il ricalcolo |
| Matrice dei punteggi | [1] celle = `score_matrix(λ,ρ)` e celle+coda = 100% |
| Probabilità in-play | [2] ogni riga somma ~100, l'ultima coincide col risultato |
| Bias dei gol | −0,024 (2,839 previsti vs 2,863 osservati su 5.815) |
| Pareggio previsto | 25,9% vs 25,6% osservato |
| Limiti di sicurezza λ | toccano lo 0,05% delle partite (1 su 2.071 nella versione corrente) |
| Traduzioni/`nan` | 0 occorrenze in 4.128 pagine |

---

# AREA 2 — ANALISI QUALITATIVA (contenuti, struttura, architettura informativa)

## 2.1 [P0] La colonna "Richieste" di *Stato fonti* è un contatore cumulativo, non per lega

**Osservato.** `collect_all()` (`src/fda/collect.py:255-261`) crea **un solo client per fonte** e lo
passa a tutte le leghe; `HttpClient.stats.requests` (`src/fda/http.py:41`) è un contatore **mai azzerato**.
Ogni lega poi registra il valore *corrente* del contatore:

```python
# src/fda/collect.py:246
report.requests = {"fotmob": fm.http.stats.requests, "understat": uc.http.stats.requests,
                   "espn": ec.http.stats.requests}
```

**Misura (dalla pagina pubblicata oggi).** FotMob: ITA1 19 → ENG1 38 → ESP1 66 → GER1 83 → FRA1 100 →
NED1 118 → POR1 138: **strettamente monotono nell'ordine in cui `leagues()` scorre
`config/leagues.yaml`** (ITA1, ENG1, ESP1, GER1, FRA1, NED1, POR1) — la firma aritmetica di un
contatore cumulativo. Understat:
ITA1 2 → ENG1 3 → ESP1 4 → GER1 5 → FRA1 6 → NED1 **6** → POR1 **6**.

**Impatto.** Tre effetti, tutti visibili all'utente:
1. La colonna «Richieste» di `stato.html` è **sbagliata per 6 leghe su 7** (solo la prima è corretta).
   Il numero totale del run (138 FotMob) è attribuito a Liga Portugal.
2. **NED1 e POR1 risultano "Understat OK, 6 richieste"** pur non chiamando mai Understat
   (`has_understat=False`, `collect.py:182`): la pagina accredita a due leghe una fonte che non le copre.
3. Il controllo del budget (`max_requests`) resta corretto (è globale per fonte), ma **non è verificabile
   per lega**: se una lega consuma 10× le altre, la pagina non lo mostra.

Violazione diretta di `docs/00 §B1` («ogni numero mostrato è misurato e verificabile»).

**Soluzione.** Delta del contatore per lega, e nessuna riga per le fonti non usate:

```python
# src/fda/http.py — nella classe HttpClient
+    def mark(self) -> int:
+        """Istantanea del contatore richieste: serve a misurare il consumo di UNA lega.
+
+        collect_all() condivide un client fra tutte le leghe, quindi stats.requests e'
+        cumulativo: senza il delta, stato.html attribuisce all'ultima lega il totale del run
+        e accredita a NED1/POR1 richieste Understat mai fatte (docs/19 §2.1).
+        """
+        return self.stats.requests
```

```python
# src/fda/collect.py — in collect_league(), subito dopo la creazione dei client
     fm = fotmob or FotMobClient()
     uc = understat or UnderstatClient()
     ec = espn or EspnClient()
     om = openmeteo            # None = passo meteo disattivato (es. test offline senza rete)
+    # il client e' condiviso fra le leghe: si misura il delta, non il totale cumulativo
+    _mark = {"fotmob": fm.http.mark(), "understat": uc.http.mark(), "espn": ec.http.mark()}
+    if om is not None:
+        _mark["openmeteo"] = om.http.mark()
```

```python
# src/fda/collect.py:246 — sostituzione del blocco finale
-    report.requests = {"fotmob": fm.http.stats.requests, "understat": uc.http.stats.requests,
-                       "espn": ec.http.stats.requests}
-    if om is not None:
-        report.requests["openmeteo"] = om.http.stats.requests
+    used = {"fotmob": fm, "understat": uc, "espn": ec}
+    if om is not None:
+        used["openmeteo"] = om
+    report.requests = {}
+    for src, client in used.items():
+        n = client.http.mark() - _mark[src]
+        # Understat non copre NED1/POR1 (has_understat=False): una riga "OK, 0 richieste"
+        # direbbe che la fonte e' stata interrogata con successo, il che e' falso.
+        if src == "understat" and not lg.has_understat:
+            continue
+        report.requests[src] = n
```

Test (`tests/test_collect.py` o equivalente esistente):

```python
def test_richieste_per_lega_non_cumulative(store, monkeypatch):
    """Due leghe di seguito: ognuna deve riportare le PROPRIE richieste, non il totale."""
    # ... stub HTTP che risponde a N chiamate per lega ...
    r1, r2 = collect_all(["ITA1", "ENG1"], store=store)
    assert r2.requests["fotmob"] < r1.requests["fotmob"] + r2.requests["fotmob"]   # non cumulativo
    assert "understat" not in collect_league(league("NED1"), store).requests        # fonte non usata
```

**Verifica.** Dopo un `fda collect --league ITA1 --league ENG1`, `stato.html` deve mostrare per FotMob
due numeri **non** monotoni per costruzione, e la loro somma deve equalizzare il totale del run;
nessuna riga `understat:NED1` o `understat:POR1`.

---

## 2.2 [P1] ESPN standings: 7 richieste a run che falliscono **sempere**, senza backoff

**Osservato.** `stato.html` mostra **7 righe AVVISO permanenti** (`espn:ENG1 … espn:POR1`,
`SourceError: HTTP 403` su `/standings`), note dal 2026-09-08. Il contatore cumulativo ESPN arriva a
**14 richieste per run**: 7 sono `standings` (403 garantito) e 7 `scoreboard`.

**Impatto.** Metà del budget ESPN di ogni run (5 run/giorno → **~35 richieste/giorno, ~1.050/mese**)
viene spesa su un endpoint che risponde 403 da una settimana, e la pagina di stato mostra
**7 avvisi su 28 righe (25%)** in modo cronico. Due costi: (a) rispetto della fonte
(`docs/00`: "ogni fonte ha una pausa minima tra richieste — rispetto delle fonti");
(b) **assuefazione dell'operatore**: con 7 avvisi fissi, un avviso nuovo e vero non si nota.

**Soluzione.** Backoff a memoria: dopo N fallimenti consecutivi dello stesso passo, si salta per un
periodo crescente, e lo si dichiara esplicitamente in stato fonti (trasparenza, non silenzio):

```python
# src/fda/collect.py — accanto a _safe()
+SKIP_AFTER_FAILS = 3          # fallimenti consecutivi dopo i quali il passo viene sospeso
+SKIP_HOURS = 72.0             # durata della sospensione (poi si riprova: le fonti tornano)
+
+
+def _in_backoff(store: Store, step_key: str, now: datetime) -> bool:
+    """True se il passo e' in sospensione per fallimenti ripetuti (docs/19 §2.2)."""
+    st = store.read("source_status")
+    if st.empty or "source" not in st.columns:
+        return False
+    g = st[st.source == step_key].sort_values("run_at").tail(SKIP_AFTER_FAILS)
+    if len(g) < SKIP_AFTER_FAILS:
+        return False
+    if bool(g.ok.any()):
+        return False                       # un successo recente azzera il conteggio
+    ultima = pd.to_datetime(g.run_at.iloc[-1], utc=True)
+    return (now - ultima).total_seconds() < SKIP_HOURS * 3600
```

```python
     def _standings() -> None:
+        if _in_backoff(store, f"espn standings:{lg.key}", now):
+            report.errors.append(f"espn standings:{lg.key}: sospeso per 403 ripetuti (backoff {SKIP_HOURS:.0f}h)")
+            return
         rows = ec.parse_standings(lg.espn_code, ec.standings_raw(lg.espn_code))
         store.upsert("espn_standings", espn_dicts(rows))
```

In `status.html` distinguere graficamente i tre stati (oggi AVVISO copre sia "403 di oggi" sia
"sospeso per backoff"):

```html
-<td>{% if r.ok %}<span class="pill V">OK</span>{% elif r.warn %}<span class="pill N">AVVISO</span> …
+<td>{% if r.ok %}<span class="pill V">OK</span>
+    {% elif r.skipped %}<span class="pill N">SOSPESO</span> <span class="small mut">403 ripetuti: si riprova fra {{ r.retry_in_h }} h</span>
+    {% elif r.warn %}<span class="pill N">AVVISO</span> <span class="small mut">{{ r.error }}</span>
```

**Verifica.** Al secondo run consecutivo, `stato.html` mostra 7 righe «SOSPESO» e il contatore ESPN
scende da 14 a 7 richieste/run (misurabile con il delta corretto del §2.1).

---

## 2.3 [P1] Open-Meteo: stato "OK" con **0 richieste** — il fallback non è distinguibile da "non serve"

**Osservato.** Tutte e 7 le righe `openmeteo:*` mostrano **OK · 0 richieste**.
Leggendo `collect.py:228-244`: il passo salta la chiamata se FotMob ha già il meteo
(`if isinstance(fotmob_weather, str) and fotmob_weather.strip(): continue`) — comportamento corretto.
Ma la pagina di stato non lo dice: **0 richieste + OK** è indistinguibile da "il passo non è stato eseguito".

**Impatto.** `info.html` dichiara Open-Meteo come «fallback verificato P0». Oggi non c'è modo di sapere
se il fallback **funziona** o se semplicemente **non è mai stato necessario**: se FotMob smettesse di
pubblicare il meteo e il fallback fosse rotto, la pagina continuerebbe a dire OK. È un buco di
osservabilità su un componente dichiarato critico.

**Soluzione.** Riportare il motivo, non solo l'esito:

```python
     def _weather() -> int:
+        saltate = {"nessuna_coord": 0, "meteo_gia_da_fotmob": 0, "chiamate": 0}
         ...
             if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
+                saltate["nessuna_coord"] += 1
                 continue
             if isinstance(fotmob_weather, str) and fotmob_weather.strip():
+                saltate["meteo_gia_da_fotmob"] += 1
                 continue
+            saltate["chiamate"] += 1
             fc = om.forecast(float(lat), float(lon), f.utc_kickoff)
         ...
+        report.weather_detail = saltate        # nuovo campo di CollectReport
         return store.upsert("weather_forecast", rows) if rows else 0
```

`status.html`:

```html
+{% if r.source.startswith('openmeteo') %}
+  <span class="small mut">{{ r.requests }} chiamate · {{ r.meteo_gia_da_fotmob }} gare con meteo già da FotMob · {{ r.nessuna_coord }} senza coordinate</span>
+{% endif %}
```

E — punto più importante — **un test periodico che il fallback funzioni davvero**, perché "non serve
oggi" non vuol dire "funziona": in `.github/workflows/daily.yml`, un passo settimanale che forza una
chiamata Open-Meteo su una partita reale e confronta la risposta con lo schema atteso.

**Verifica.** `stato.html` mostra per ogni lega quante gare avevano già il meteo da FotMob;
il passo settimanale in CI fallisce se l'API cambia schema.

---

## 2.4 [P1] `future_days`: il valore "7 giorni" è scritto in 4 punti diversi (e il default del CLI è 3)

**Osservato.**

| Punto | Valore |
|---|---|
| `src/fda/collect.py:85` (`collect_league`) | `future_days: int = 3` |
| `src/fda/cli.py:160` (`fda collect`) | `typer.Option(3, ...)` |
| `src/fda/cli.py:513` (`fda daily`) | `future_days=7` |
| `src/fda/site/build.py` (`build_indexes`) | `today_local + timedelta(days=7)` e `_render(..., calendar_days=7)` |
| Testo pubblicato (`index.html`, `info.html`) | «I prossimi **7** giorni con la scheda completa» |

**Misura della copertura reale** (gare `scheduled` con dettagli raccolti, per lega):
ENG1 2,9% · ESP1 5,8% · FRA1 3,3% · GER1 3,2% · ITA1 2,9% · NED1 4,0% · POR1 3,6%
(su 1.987 gare in calendario: è corretto, perché la finestra è corta per progetto — Tappa 1).

**Impatto.** Se qualcuno esegue `fda collect` (default 3) e poi `fda build`, le partite fra il 4° e il
7° giorno **appaiono nell'elenco "Prossime" come ricche** ma non hanno scheda: il sito promette 7 giorni
e ne mantiene 3. Non succede con `fda daily` (che passa 7 esplicitamente), quindi è un difetto
**latente**: compare al primo run manuale o al primo refactoring. La duplicazione in 4 punti è la
radice: nessuna singola fonte di verità.

**Soluzione.**

```python
# src/fda/config.py
+#: giorni avanti per cui si raccolgono i dettagli partita (formazione, arbitro, meteo, h2h).
+#: UN SOLO PUNTO: collect, build e i testi delle pagine devono leggere questo valore,
+#: altrimenti un run manuale con un default diverso pubblica un elenco che promette piu'
+#: schede di quante ne esistano (docs/19 §2.4).
+DETAIL_WINDOW_DAYS: int = 7
```

```python
# collect.py:85 e cli.py:160
-    future_days: int = 3,
+    future_days: int = DETAIL_WINDOW_DAYS,
# build.py
-        upcoming = upcoming[upcoming.date_local <= today_local + timedelta(days=7)]
+        upcoming = upcoming[upcoming.date_local <= today_local + timedelta(days=DETAIL_WINDOW_DAYS)]
-        self._render("index.html", "index.html", ..., calendar_days=7, ...)
+        self._render("index.html", "index.html", ..., calendar_days=DETAIL_WINDOW_DAYS, ...)
```
e nei template sostituire il "7" letterale con `{{ detail_window_days }}` (passato dal builder),
inclusa la frase di `info.html`.

**Verifica.** `grep -rn "days=7\|future_days=7\|calendar_days=7\|prossimi 7" src/ | wc -l` → **0**.

---

## 2.5 [P1] Il blocco "Curiosità" scarta il 34% dei fatti FotMob; il 20% delle schede ne mostra solo 2

**Osservato.** `translate_insight()` (`src/fda/site/analysis.py:262`) è una whitelist di pattern:
ciò che non riconosce viene **scartato** (scelta corretta: mai inglese a schermo). Ma lo scarto
non è misurato né monitorato.

**Misura (eseguita su `insights.parquet`, 2.014 righe / 376 partite):**

| Voce | Valore |
|---|---|
| Fatti tradotti | 1.329 (**66,0%**) |
| Fatti scartati | **685 (34,0%)** |
| Schede con **meno di 3** curiosità | **75 su 376 (20,0%)** |
| Schede con 0 curiosità | 0 |

Top 5 template scartati — **tutti oggettivi, tutti traducibili**:

| Ocorrenze | Testo FotMob | Traduzione proponibile |
|---|---|---|
| 57 | `Have kept the most clean sheets in the competition (N)` | «ha il maggior numero di porte inviolate del campionato (N)» |
| 41 | `Have conceded the most penalties this season (N)` | «ha concesso più rigori in questa stagione (N)» |
| 40 | `Have been awarded the most penalties this season (N)` | «ha ottenuto più rigori in questa stagione (N)» |
| 22 | `Average N.N goals per match` / `Average N goals per match` | «media N,N gol a partita» |
| 6 | `Ranked N at home this season` | «N° in classifica considerando le gare interne» |

**Impatto.** 138 righe di fatti oggettivi (top 3) vengono buttate, e **una scheda su cinque** mostra
2 curiosità invece di 3. Il resto degli scarti (fatti su "big chances created", "most shots on target")
è **correttamente** escluso: sono giudizi/hype, non dati. Il difetto è doppio: contenuto perso **e**
nessun allarme se FotMob cambia un template (il blocco si svuoterebbe in silenzio).

**Soluzione 1 — recuperare i 5 template oggettivi** (in `translate_insight`, accanto agli altri):

```python
+    m = re.fullmatch(r"Have kept the most clean sheets in the competition \((\d+)\)", t)
+    if m:
+        return {"kind": "clean_sheets", "priority": 3, "text": f"ha il maggior numero di porte inviolate del campionato ({m.group(1)})"}
+
+    m = re.fullmatch(r"Have conceded the most penalties this season \((\d+)\)", t)
+    if m:
+        return {"kind": "penalties_conceded", "priority": 2,
+                "text": f"ha concesso più rigori in questa stagione ({m.group(1)})"}
+
+    m = re.fullmatch(r"Have been awarded the most penalties this season \((\d+)\)", t)
+    if m:
+        return {"kind": "penalties_awarded", "priority": 2,
+                "text": f"ha ottenuto più rigori in questa stagione ({m.group(1)})"}
+
+    m = re.fullmatch(r"Average (\d+(?:\.\d+)?) goals per match", t)
+    if m:
+        return {"kind": "avg_goals", "priority": 1, "text": f"media {_it2(m.group(1))} gol a partita"}
+
+    m = re.fullmatch(r"Ranked (\d+) at home this season", t)
+    if m:
+        return {"kind": "rank_home", "priority": 1, "text": f"{m.group(1)}° in classifica nelle gare interne"}
```

*(i nomi dei campi `kind`/`priority` e la forma del dict restituito vanno allineati a quelli già
usati dagli altri rami della funzione: qui è indicata la struttura, il valore esatto va copiato dai
pattern vicini — è l'unico punto del documento che richiede di guardare il codice adiacente.)*

**Soluzione 2 — rendere visibile lo scarto** (osservabilità, `docs/00 §B2`):

```python
# analysis.py, accanto a translate_insight
+INSIGHT_DROP_LOG: dict[str, int] = {}
+
+
+def insight_dropped(text: str) -> None:
+    """Conta gli scarti per forma canonica: se FotMob cambia un template, si vede.
+
+    Oggi il 34% dei fatti viene scartato in silenzio (docs/19 §2.5). Il conteggio per forma
+    canonica (numeri -> 'N') distingue 'template nuovo' da 'caso singolo'.
+    """
+    key = re.sub(r"\d+", "N", str(text))[:80]
+    INSIGHT_DROP_LOG[key] = INSIGHT_DROP_LOG.get(key, 0) + 1
```

chiamato nel ramo `return None` di `translate_insight`, e pubblicato in `stato.html` come riga
«Fatti FotMob: 1.329 tradotti · 685 scartati · top template scartato: …».

**Verifica.** Rieseguire la misura: tradotti ≥ 1.467 (72,8%), schede con <3 curiosità < 75.
Comando di controllo (da mettere in `scripts/`):

```bash
python - <<'EOF'
import pandas as pd, sys; sys.path.insert(0,'src')
from fda.site.analysis import translate_insight
i = pd.read_parquet('data/processed/insights.parquet')
ok = sum(1 for t in i.text.astype(str) if translate_insight(t))
print(f"tradotti {ok}/{len(i)} = {100*ok/len(i):.1f}%")
EOF
```

---

## 2.6 [P1] Etichette dell'arbitro: soglie assolute in leghe con medie molto diverse, su campioni da 6 partite

**Osservato.** `narrative()` (`src/fda/site/analysis.py:1806-1812`) classifica l'arbitro con soglie fisse:

```python
tone = "molto severo" if y >= 5 else "severo" if y >= 4.2 else "permissivo" if y <= 3.2 else "nella media"
```

**Misura** (282 designazioni con statistiche, in `match_info.parquet`):

| Lega | n | media gialli/partita | p25 | p75 |
|---|---|---|---|---|
| FRA1 | 36 | 3,85 | 3,57 | 4,26 |
| ENG1 | 50 | 3,99 | 3,73 | 4,34 |
| GER1 | 27 | 3,97 | 3,46 | 4,40 |
| ITA1 | 40 | 4,16 | 3,68 | 4,76 |
| ESP1 | 50 | 4,54 | 3,90 | 4,89 |
| **POR1** | 34 | **5,04** | 4,29 | **5,85** |

Distribuzione globale: min 2,21 · p25 3,52 · mediana 3,96 · media 4,57 · p75 5,23 · max 6,57.
Con le soglie fisse: **38 arbitri "molto severo" (13,5%)**, ma in **POR1 la media di lega è 5,04** →
lì l'etichetta «molto severo» scatta per un arbitro **nella media del proprio campionato**.
Inoltre `referee_matches` ha **minimo 6** (mediana 33): una media su 6 partite ha un errore standard
di ~0,6 gialli/partita, quindi l'etichetta è spesso rumore.

**Nota strutturale.** Il progetto **calcola già** il confronto con la lega:
`referee_profile()` (`analysis.py:1193-1225`) restituisce `league_yellows`, `league_fouls`,
`league_matches`. Ma `narrative()` usa un **altro dizionario** (`ctx["referee"]`, `analysis.py:1894-1896`)
che quei campi non li ha. Due fonti per lo stesso dato, una delle quali meno informata: è lo schema
che genera questo tipo di errore.

**Soluzione.** Una sola fonte + etichetta relativa alla lega + soglia minima di campione:

```python
# analysis.py — build(): un solo profilo arbitro, usato sia dalla card sia dalla narrazione
-            "referee": {"name": _val(info, "referee_name"), "matches": _val(info, "referee_matches"),
-                        "yellows": _val(info, "referee_yellows_per_match"), "pens": _val(info, "referee_penalties_total"),
-                        "reds": _val(info, "referee_reds_total")},
+            # un'unica fonte: referee_profile() ha gia' il confronto con la media di lega,
+            # che le soglie assolute ignoravano (docs/19 §2.6)
+            "referee": self.referee_profile(match_id),
```

```python
# analysis.py — narrative(): etichetta relativa e campione minimo
-        ref = ctx.get("referee")
-        if ref and ref.get("name"):
-            y = ref.get("yellows")
-            if y is not None:
-                tone = "molto severo" if y >= 5 else "severo" if y >= 4.2 else "permissivo" if y <= 3.2 else "nella media"
-                s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita ({tone})"
-                         + (f", {it_plural(ref['pens'], 'rigore')} in {it_plural(ref['matches'], 'gara')}."
-                            if ref.get("pens") is not None else "."))
+        ref = ctx.get("referee")
+        if ref and ref.get("name"):
+            y, ly = ref.get("yellows"), ref.get("league_yellows")
+            n = ref.get("matches") or 0
+            if y is not None and n >= MIN_REFEREE_MATCHES:
+                # soglie RELATIVE alla lega: in Liga Portugal la media e' 5,04 gialli/partita,
+                # in Ligue 1 3,85. Un valore assoluto chiamava "molto severo" un arbitro
+                # portoghese perfettamente nella media (docs/19 §2.6).
+                tone = ("sopra la media del campionato" if ly and y >= 1.15 * ly
+                        else "sotto la media del campionato" if ly and y <= 0.85 * ly
+                        else "nella media del campionato")
+                s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita, {tone}"
+                         + (f" ({_f(ly, 1)} la media di lega)." if ly else ".")
+                         + (f" {it_plural(ref['pens'], 'rigore')} in {it_plural(n, 'gara')}."
+                            if ref.get("pens") is not None else ""))
+            elif y is not None:
+                # campione troppo piccolo: si pubblica il numero, non il giudizio
+                s.append(f"Arbitro {ref['name']}: {_f(y, 1)} ammonizioni a partita su {n} gare "
+                         f"designate (campione ridotto, nessuna valutazione).")
```

```python
+MIN_REFEREE_MATCHES = 15   # sotto questa soglia la media gialli/partita ha SE ~0,4: solo il numero, mai l'aggettivo
```

**Verifica.** Test: con `league_yellows=5.04` (POR1) e `yellows=5.0` la frase deve dire
«nella media del campionato», non «molto severo». Con `matches=6` deve uscire la variante
«campione ridotto». `grep -c "molto severo" site/partite/*.html` → 0.

---

## 2.7 [P1] `info.html`: un claim presunto ("0,19-0,20 i bookmaker") e una definizione contraddetta dalla tabella

**Osservato.** Due frasi della pagina Metodologia:

1. «RPS (0=perfetto, **0,25≈casuale con frequenze medie**, **0,19-0,20 bookmaker**)»
2. In `accuratezza.html`: «0,25 ≈ tirare a caso con le frequenze medie»

**Misura.**

| Riferimento | RPS misurato | Dove |
|---|---|---|
| Predizione **uniforme** 1/3-1/3-1/3 | **0,2352** | 7.387 gare `history.parquet` |
| **Frequenze reali** 0,4290/0,2567/0,3143 | **0,23024** | idem |
| Naive **hard-coded** 45/27/28 | **0,23105** | idem |
| Naive pubblicata in `accuratezza.html` (riga "Tutti") | **0,2339** | n=84 |
| **Mercato** (Pinnacle chiusura, de-vigged) | **0,18843** | n=4.372 (§1.1) |
| Modello corrente | 0,19803 | n=4.372 |

**Impatto.** (a) «0,19-0,20 bookmaker» è una **stima non misurata** pubblicata come riferimento
principale: viola `docs/00 §B2`. Ora il numero vero c'è: **0,1884** — più basso (quindi il mercato è
*meglio* di quanto la pagina lasci intendere) e il modello è a **+0,0096** da esso.
(b) «0,25 ≈ casuale con frequenze medie» è **falso due volte**: 0,25 non è né il caso uniforme (0,2352)
né le frequenze medie (0,2302), e la stessa pagina mostra 0,2339 nella colonna "RPS naive".
Un lettore attento trova la contraddizione in 10 secondi.

**Soluzione.** Testo corretto, con ogni numero agganciato alla sua misura:

```html
-  <li>RPS (0=perfetto, 0,25≈casuale con frequenze medie, 0,19-0,20 bookmaker) e Brier …</li>
+  <li>RPS: 0 = perfetto. Riferimenti <b>misurati</b> su 7.387 partite di archivio —
+      previsione uniforme 1/3-1/3-1/3: <b>0,2352</b>; frequenze reali dei tre esiti
+      (42,9 / 25,7 / 31,4): <b>0,2302</b>. Su 4.372 partite con quote di chiusura Pinnacle
+      il mercato de-vigged ottiene <b>0,1884</b> e il modello <b>0,1980</b>: il modello batte
+      nettamente il caso (−0,032) e resta a +0,0096 dal mercato (IC95% [+0,0079; +0,0113],
+      peggio in 7 leghe su 7). Brier: errore quadratico, più basso è meglio.</li>
```

```html
-  <p class="mut">RPS (Ranked Probability Score): 0 = perfetto, 0,25 ≈ tirare a caso con le
-  frequenze medie; i bookmaker si attestano intorno a 0,19–0,20.</p>
+  <p class="mut">RPS (Ranked Probability Score): 0 = perfetto. Per orientarsi, sullo stesso
+  archivio: tirare a caso in modo uniforme dà 0,2352, usare le frequenze reali dei tre esiti
+  dà 0,2302, le quote di chiusura Pinnacle (margine rimosso) danno 0,1884 su 4.372 partite.</p>
```

Più la riga onesta sul **confronto col mercato** in `accuratezza.html` (una riga, non una nuova
sezione — le quote non sono una priorità del prodotto, ma il riferimento sì):

```html
+<p class="small mut">Riferimento esterno misurato (<a href="../info.html">metodo</a>): sulle
+  {{ bench.n_valutate|it_num }} partite dell'archivio per cui esistono quote di chiusura Pinnacle,
+  il mercato de-vigged ottiene RPS {{ bench.rps_mercato|dec(5) }} e il modello
+  {{ bench.rps_modello|dec(5) }} (Δ {{ bench.delta|dec(5, plus=True) }}). Il modello non usa le
+  quote: sono solo il metro con cui si misura la distanza dal livello di mercato.</p>
```

**Verifica.** `grep -o "0,25 ≈ tirare a caso" site/*.html` → 0 occorrenze;
`grep -o "0,19-0,20\|0,19–0,20" site/*.html` → 0 occorrenze.

---

## 2.8 [P2] `narrative()`: tre frasi che si leggono come output di macchina

**Osservato** (stesso file, righe 1780-1805). Le frasi sono corrette nei numeri ma non nella lingua:

| Frase pubblicata | Problema |
|---|---|
| «Inter **ha −3,0 punti** rispetto agli xPTS» | `dec(diff, plus=True)` con valore negativo produce "ha −3,0 punti": in italiano si dice "ha 3,0 punti in meno" |
| «**Assenze Inter: 3** (tra cui 2 giocatori di peso) — Lautaro Martínez, Barella, Calhanoglu» | Formato elenco-dati, non frase; «giocatori di peso» è definito da una soglia hard-coded `value >= 15_000_000` senza giustificazione |
| «Il modello vede Inter **nettamente favorito (60%)**» | A 60% il favorito perde 4 volte su 10: "nettamente" è più forte del dato |

**Impatto.** La narrazione è il contenuto che dà personalità al portale: 3 frasi su ~12 suonano
come un log. La soglia «nettamente» a 0,60 in particolare contraddice la cura dichiarata in
`prediction_meta()` («una probabilità del 57% resta un evento incerto»).

**Soluzione.**

```python
-                if diff >= 3:
-                    s.append(f"{name} ha raccolto {dec(diff, 1, plus=True)} punti rispetto agli xPTS: rendimento "
-                             f"sopra la qualità del gioco prodotto, possibile regressione.")
-                elif diff <= -3:
-                    s.append(f"{name} ha {dec(diff, 1, plus=True)} punti rispetto agli xPTS: sta rendendo meno di "
-                             f"quanto crea, segnale di sottovalutazione.")
+                if diff >= 3:
+                    s.append(f"{name} ha raccolto {_f(diff, 1)} punti in più di quanto dica l'xPTS: "
+                             f"rendimento sopra la qualità del gioco prodotto, regressione possibile.")
+                elif diff <= -3:
+                    s.append(f"{name} ha {_f(-diff, 1)} punti in meno di quanto dica l'xPTS: "
+                             f"rende meno di ciò che crea, segnale di sottovalutazione.")
```

```python
-                heavy = [u for u in un if u.get("value") and u["value"] >= 15_000_000]
-                names = ", ".join(u["name"] for u in un[:4])
-                extra = (" (tra cui 1 giocatore di peso)" if len(heavy) == 1
-                         else f" (tra cui {len(heavy)} giocatori di peso)") if heavy else ""
-                s.append(f"Assenze {name}: {len(un)}{extra} — {names}{'…' if len(un) > 4 else ''}.")
+                # soglia relativa alla rosa, non assoluta: 15 milioni pesano molto in Eredivisie
+                # e poco in Premier. Si usa il valore mediano degli indisponibili della lega.
+                heavy = [u for u in un if u.get("value") and u["value"] >= HEAVY_VALUE_EUR]
+                nomi = _elenco_it([u["name"] for u in un[:4]], max_items=4)
+                quanti = it_plural(len(un), "assente")
+                peso = (f", di cui {it_plural(len(heavy), 'giocatore')} sopra i "
+                        f"{int(HEAVY_VALUE_EUR / 1_000_000)} milioni di valore") if heavy else ""
+                s.append(f"{name} senza {quanti}{peso}: {nomi}.")
```

```python
+_elenco_it = lambda items, max_items=4: (          # "A, B e C" / "A, B, C e D…"
+    " e ".join([", ".join(items[:-1]), items[-1]]) if len(items) > 1 else items[0]
+) + ("…" if len(items) > max_items else "")
```

```python
-            elif pf >= 0.60:
-                s.append(f"Il modello vede {top_name} nettamente favorito ({_pct(pf)}).")
-            elif pf >= 0.45:
-                s.append(f"Il modello indica {top_name} favorito ({_pct(pf)}), ma con margine contenuto.")
+            elif pf >= 0.60:
+                s.append(f"Il modello indica {top_name} come esito più probabile ({_pct(pf)}): "
+                         f"su 100 partite così, {int(round(pf * 100))} finiscono in quel modo.")
+            elif pf >= 0.45:
+                s.append(f"Il modello indica {top_name} ({_pct(pf)}), con margine contenuto sul secondo esito.")
```

La formulazione in **frequenze naturali** («su 100 partite così, 60 finiscono…») non è decorativa:
è il formato che la letteratura sulla comunicazione del rischio indica come meglio compreso delle
percentuali, ed è già la filosofia usata dal dotplot dei gol. Estenderla all'1X2 è coerente.

**Verifica.** `grep -c "ha −\|Assenze .*: [0-9]" site/partite/*.html` → 0; test sulle frasi con
`diff=-3.0` e con 1/2/5 indisponibili.

---

## 2.9 [P1] `404.html` assente + 4 difetti di `sitemap.xml`

**Osservato.**

```bash
$ ls site/ | grep -c 404 || true
0
```

`sitemap.xml` (generato da `_write_seo_files`): contiene sia `/` sia `/index.html` (duplicato),
**non** contiene le 7 pagine di lega (`giocatori/ENG1.html` …), limita i giocatori a `[:5000]`
(oggi 3.737 → il limite non morde ancora, ma è una bomba a orologeria), e usa come `lastmod`
la **data di build** per tutte le URL.

**Impatto.** (a) Un link sbagliato o una partita rimossa mostra il 404 di GitHub Pages: inglese,
senza navigazione, senza marchio — l'unico punto del sito dove l'utente esce dal design.
(b) `lastmod` identico per 4.128 URL dice ai motori "tutto è cambiato adesso" a ogni run (5 volte al
giorno): è il segnale che viene ignorato più in fretta, e spreca crawl budget.
(c) Le 7 pagine di lega sono le più ricche di contenuto indicizzabile e non sono in sitemap.

**Soluzione.**

```python
# build.py — _write_seo_files()
-        urls = [("index.html", now), ("oggi.html", now), ...]
+        # 1) una sola URL per la home (niente /index.html duplicato)
+        # 2) le pagine di lega entrano in sitemap: sono le piu' ricche di contenuto indicizzabile
+        # 3) lastmod = data reale dell'ultimo cambiamento del contenuto, non la data di build:
+        #    4.128 URL con lo stesso lastmod a ogni run insegnano ai motori a ignorarlo (docs/19 §2.9)
+        urls: list[tuple[str, str]] = [("index.html", build_date), ("prossime.html", build_date),
+                                       ("risultati.html", build_date), ("accuratezza.html", build_date),
+                                       ("stagione.html", sim_date), ("info.html", docs_date),
+                                       ("stato.html", status_date)]
+        urls += [(f"giocatori/{lg.key}.html", players_date) for lg in leagues()]
+        for pg in sorted(partite_dir.glob("*.html"))[:MAX_SITEMAP_MATCHES]:
+            urls.append((f"partite/{pg.name}", match_date(pg)))
```

con `match_date(pg)` = data della partita (dal nome/riga), `MAX_SITEMAP_MATCHES = 50_000`, e
`players_date` = data dell'ultimo aggiornamento di `player_stats`.

Nuovo `src/fda/site/templates/404.html` (GitHub Pages lo serve automaticamente se si chiama `404.html`
alla radice):

```html
{% extends "base.html" %}
{% block title %}Pagina non trovata — CalcioMetro{% endblock %}
{% block content %}
<h1>Questa pagina non c'è (o non c'è più)</h1>
<p class="mut">Le schede delle partite restano online finché la partita è in archivio; i calendari
  vengono rigenerati e un indirizzo vecchio può smettere di esistere.</p>
<div class="grid">
  <div class="card"><h2>Da dove ripartire</h2>
    <ul class="mut small">
      <li><a href="/index.html">Partite di oggi</a> — le gare in programma con l'analisi completa</li>
      <li><a href="/prossime.html">Prossime partite</a> — il calendario dei prossimi giorni</li>
      <li><a href="/risultati.html">Risultati</a> — le gare già giocate con xG e momentum</li>
      <li><a href="/accuratezza.html">Accuratezza del modello</a> — come sta andando</li>
    </ul>
  </div>
  <div class="card"><h2>Cerchi una squadra o un giocatore?</h2>
    <p class="small mut">Le schede giocatore sono tutte sotto <a href="/giocatori/">giocatori</a>,
      una pagina per campionato.</p>
  </div>
</div>
{% endblock %}
```

⚠️ Il 404 di GitHub Pages **non** eredita i percorsi relativi: gli `href` devono essere assoluti
(`/index.html`) e il `<base>`/canonical vanno disattivati per questa pagina, altrimenti i link
si rompono su URL di sottocartelle (`/partite/999.html` → `/index.html` corretto, `index.html` no).

**Verifica.** `test -f site/404.html`; `grep -c "<loc>" site/sitemap.xml` deve crescere di 7;
`grep -c "index.html</loc>" site/sitemap.xml` → 0 (solo `/`); i `lastmod` devono essere **diversi**
fra loro.

---

## 2.10 [P2] Documentazione: 8 documenti non elencati, e "7.474 giocatori" è un doppio conteggio

**Osservato.** `docs/` contiene 18 documenti numerati; `README.md` e `docs/STATO.md` ne elencano
una parte (i più recenti 11-18 non sono raggiunti dalla navigazione). Inoltre il log di `fda build`
e la documentazione riportano **«players: 7.474»** mentre i file generati sono **3.745**
(3.737 schede giocatore + 8 pagine di lega).

**Misura.** Il numero 7.474 = `sum(len(rows) + len(bench))` sulle 7 leghe: **ogni giocatore è contato
due volte** (titolare e panchinaro della stessa lista). Le pagine reali sono 3.737.

**Impatto.** Piccolo ma corrosivo: è il numero che compare nei log e nei documenti di progetto, e
chi legge `docs/` si aspetta 7.474 schede. Regola `§B1`: i numeri mostrati devono essere verificabili.

**Soluzione.** Contare ciò che si scrive su disco:

```python
-        log.info("players: %d", n)
+        # n conta rows+bench: ogni giocatore due volte. Le pagine scritte sono len(ids).
+        log.info("players: %d pagine (%d righe di lista elaborate)", len(ids), n)
```

Più un indice dei documenti in `docs/README.md` (o in testa a `docs/STATO.md`) con una riga per
documento: numero, data, tema, stato (attuato / proposto / respinto). Serve anche a non ripetere
audit già fatti — incluso il candidato respinto del §1.3.

**Verifica.** Il log della build deve stampare `players: 3737 pagine`; `ls site/giocatori/*.html | wc -l` → 3.745 (3.737 + 8).

---

## 2.11 [P0] `verify_site.py`: 11.590 controlli matematici, **zero** controlli di pubblicazione

**Osservato.** L'harness verifica in modo eccellente la matematica pubblicata (matrice punteggi,
in-play, dotplot, Wilson, backtest, proiezioni, xG, precedenti). I controlli esistenti sono
`[1] [2] [3] [4] [5] [6] [7] [8] [9] [10]`. **Nessuno** riguarda invarianti di pubblicazione:
somme delle percentuali 1X2, altezze delle barre, coerenza 1X2/doppia chance, contrasto dei colori,
dimensione delle pagine, completezza della sitemap, corrispondenza fra numero dichiarato e file scritti.

**Impatto.** È la ragione per cui **tutti** i difetti di quest'audit nelle aree 1.5, 1.9, 3.3, 3.4
sono arrivati in produzione con «0 problemi su 11.590 controlli» stampato a log. L'harness dà
falsa sicurezza: il numero di controlli è alto, la loro copertura è concentrata su una sola classe
di difetti.

**Soluzione.** Un blocco `[11] invarianti di pubblicazione` (codice pronto, da aggiungere in fondo
a `main()` prima del riepilogo):

```python
    # 11) invarianti di pubblicazione: le cose che un lettore VEDE e che nessuna formula garantisce
    n_pub = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        n_pub += 1
        # a) barre 1X2: etichette e larghezze devono sommare 100 (pct_triple esiste, va usata)
        for m in re.finditer(r'<div class="bar"(?: role="img"[^>]*)?[^>]*>(.*?)</div>', html, re.S):
            spans = re.findall(r'<span class="[hda]"[^>]*width:\s*([\d.]+)%[^>]*>(.*?)</span>',
                               m.group(1), re.S)
            if len(spans) != 3:
                continue
            widths = [float(w) for w, _ in spans]
            labs = []
            for _w, txt in spans:
                mm = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", txt)
                if mm:
                    labs.append(float(mm[-1].replace(",", ".")))
            if len(labs) == 3 and abs(sum(labs) - 100) > 0.051:
                fails.append(f"{pg.name}: barre 1X2 sommano {sum(labs):.1f} (etichette {labs})")
            if abs(sum(widths) - 100) > 0.01:
                fails.append(f"{pg.name}: larghezze barre 1X2 sommano {sum(widths):.1f}")
        # b) nessuna barra verticale oltre il 100% del contenitore
        for h in re.findall(r"height:\s*([\d.]+)%", html):
            if float(h) > 100.0:
                fails.append(f"{pg.name}: altezza barra {h}% (overflow del contenitore)")
        # c) doppia chance coerente con l'1X2 pubblicato
        for m in re.finditer(r"1 · (\d+)%.*?X · (\d+)%.*?2 · (\d+)%", html, re.S):
            ph, pd_, pa = (int(x) for x in m.groups())
            if max(ph, pd_, pa) >= 50 and f"Doppia chance" in html:
                n_pub += 0    # il controllo puntuale e' sui dati, non sull'HTML: vedi sotto
    # d) coerenza 1X2 / doppia chance sui dati salvati (60 righe incoerenti misurate il 14/09)
    preds = store.read("predictions")
    if not preds.empty:
        p = preds[["p_home", "p_draw", "p_away"]].to_numpy(float)
        for key, idx in (("p_1x", (0, 1)), ("p_12", (0, 2)), ("p_x2", (1, 2))):
            if key not in preds.columns:
                continue
            atteso = p[:, list(idx)].sum(1)
            bad = int((np.abs(preds[key].to_numpy(float) - atteso) > 1e-6).sum())
            if bad:
                fails.append(f"predictions: {bad} righe con {key} incoerente con la somma 1X2")
    # e) peso delle pagine: oltre la soglia il caricamento da mobile diventa un problema reale
    for pg in pages:
        kb = pg.stat().st_size / 1024
        if kb > MAX_PAGE_KB:
            fails.append(f"{pg.name}: {kb:.0f} KB (soglia {MAX_PAGE_KB})")
    print(f"[11] invarianti di pubblicazione verificate su {n_pub} pagine")
```

con in testa al file:

```python
+MAX_PAGE_KB = 900.0     # prossime.html oggi e' 1.513 KB: vedi docs/19 §3.10
```

**Verifica.** Al primo run il blocco deve **fallire** (37 barre 1X2, 5 altezze >100%, 60 righe
incoerenti, 1 pagina oltre soglia): è la conferma che il controllo funziona. Poi si applicano le
correzioni delle aree 1.9/3.3/3.4/3.10 e il run torna a 0 problemi — con un numero di controlli
che include davvero ciò che l'utente vede.

---

## 2.12 [P2] Architettura informativa: due dizionari per lo stesso dato, tre implementazioni della stessa funzione

**Osservato** (pattern ricorrente, non un singolo bug):

| Dato | Fonti nel codice | Conseguenza |
|---|---|---|
| Profilo arbitro | `ctx["referee"]` (5 campi) **e** `ctx["referee_profile"]` (9 campi, con media di lega) | la narrazione usa quello povero → §2.6 |
| Percentuali 1X2 | `fmt.pct_triple()` **e** `build.pct_triple()` (wrapper con fallback inline di 15 righe) **e** `\|round` nei template | tre comportamenti diversi → §3.3 |
| Finestra giorni | `collect.future_days` / `cli` / `build_indexes` / testo HTML | quattro valori → §2.4 |
| Baseline naive | `[0.45,0.27,0.28]` in `build.py:500` **e** in `models/backtest.py` **e** descritta in `info.html` | tre punti da allineare → §1.6 |
| Limiti di λ | `predict_matches()` limita `neutral`, `simulate_league()` no | due regimi → §1.8d |

**Impatto.** Ogni duplicazione è un posto dove i due rami divergono **senza che un test se ne accorga**:
4 dei 5 casi qui sopra sono già divergenti in produzione. Non è un problema estetico, è la causa
radice di un quarto dei difetti di questo audit.

**Soluzione strutturale** (una sola regola + un controllo automatico):

> **Regola**: ogni numero pubblicato ha **una** funzione che lo produce e **una** costante che lo
> definisce. I template non fanno aritmetica (niente `|round` su percentuali che devono sommare 100,
> niente somme in Jinja). Le costanti di dominio stanno in `config.py`.

Controllo automatico in CI (`.github/workflows/tests.yml`, un passo in più):

```yaml
+      - name: Costanti duplicate (una sola fonte di verità)
+        run: |
+          set -e
+          # nessuna aritmetica sulle percentuali 1X2 nei template
+          ! grep -rn 'p_home\*100)|round' src/fda/site/templates/
+          # nessuna baseline naive hard-coded fuori da config.py
+          ! grep -rn '0\.45, *0\.27, *0\.28' src/fda --include=*.py | grep -v config.py
+          # la finestra dettagli e' una sola
+          ! grep -rn 'future_days: int = 3\|days=7\|calendar_days=7' src/fda --include=*.py
```

**Verifica.** Il passo CI deve fallire oggi (3 match) e passare dopo le patch §1.6/§2.4/§3.3.

---

# AREA 3 — ANALISI VISIVA E INTERFACCIA

## 3.1 [P0] Il CSS è inline e duplicato 4.128 volte: **144 MB su 249 MB del sito (58%)**

**Osservato.** `base.html` contiene un blocco `<style>` di **34.984 byte** che viene copiato
identico in ogni pagina.

**Misura.**

| Voce | Valore |
|---|---|
| Pagine HTML generate | **4.128** |
| Byte HTML totali | **248.274.952** (249 MB) |
| CSS duplicato | 4.128 × 34.984 = **144.413.952 byte (58,2%)** |
| Sito senza duplicazione | **103,9 MB** |
| `site/giocatori` | 3.745 file, **209 MB**, media 54 KB → il **65%** di ogni scheda giocatore è CSS |
| `site/partite` | 376 file, 37 MB, media 96 KB (36% CSS) |
| CSS minificato | 34.984 → 31.447 byte (−10%): la minificazione **non** è la leva, l'estrazione sì |

**Impatto.** Tre costi concreti: (a) **banda per l'utente**: una scheda giocatore scarica 54 KB di cui
35 di CSS già scaricato nella pagina precedente — con un file esterno e la cache del browser,
dalla seconda pagina in poi il costo del CSS è **zero**; (b) **crescita del sito**: a fine stagione
le partite con scheda passeranno da 376 a ~2.000 (+1.624 pagine): il sito arriverebbe a **401 MB**
contro il limite soft di 1 GB di GitHub Pages, e il deploy giornaliero si allunga; con il CSS esterno
si ferma a **200 MB** (−50%); (c) **Lighthouse/SEO**: HTML più pesante = parsing più lento, e il CSS non usato
(ogni pagina usa forse il 30% delle 403 regole) viene scaricato per intero 4.128 volte.
*Non verificato in sandbox (nessun browser): i punteggi Lighthouse vanno misurati in CI.*

**Soluzione.** Estrarre il CSS in un file con cache-busting sul contenuto (nessuna dipendenza nuova:
l'hash è `sha1` del testo, già usato in `http.py`).

```python
# src/fda/site/build.py
+import hashlib
+
+CSS_FILE = "assets/style.css"
+
+
+def _write_css(self) -> str:
+    """Estrae il <style> di base.html in assets/style.css e ritorna l'URL con cache-busting.
+
+    Il blocco era duplicato in 4.128 pagine: 144 MB su 249 MB di sito (58%), e il 65% del peso
+    di ogni scheda giocatore. Un file esterno + cache del browser azzera il costo dalla seconda
+    pagina in poi. L'hash nel nome evita il CSS vecchio in cache dopo un cambio (docs/19 §3.1).
+    """
+    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
+    css = re.search(r"<style>(.*?)</style>", base, re.S).group(1)
+    digest = hashlib.sha1(css.encode("utf-8")).hexdigest()[:10]
+    out = SITE_DIR / "assets" / f"style.{digest}.css"
+    out.parent.mkdir(parents=True, exist_ok=True)
+    out.write_text(css, encoding="utf-8")
+    return f"assets/style.{digest}.css"
```

```python
# base.html — sostituire il blocco <style>…</style> con
+<link rel="stylesheet" href="{{ css_href }}">
+<style>/* solo le regole critiche sopra la piega: reset, tipografia base, header, layout griglia.
+        Obiettivo < 4 KB: serve a evitare il flash di pagina non stilizzata, non a duplicare il tema. */
+  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 var(--font-body)}
+  /* …massimo una ventina di regole… */
+</style>
```

e nel builder: `self.env.globals["css_href"] = self._write_css()` (una volta per build).

⚠️ **Due attenzioni obbligatorie**, altrimenti si peggiora:
1. Le variabili `:root` e `[data-theme="light"]` devono restare **nel CSS esterno** (non in quello
   critico), altrimenti il tema si applica in due tempi con un flash. Nel CSS critico va solo
   `color-scheme: dark light` + il fallback di `background`/`color`.
2. Il percorso è **relativo** (`assets/…` dalle pagine in `partite/` e `giocatori/` diventa
   `../assets/…`): usare il prefisso già esistente nel progetto per gli asset, lo stesso di
   `canonical_path`, altrimenti le sottocartelle restano senza stile.

**Verifica.** Dopo la build: `ls site/assets/style.*.css` esiste;
`du -sb site` deve scendere da 248.878.258 a ~110 MB;
`grep -c "<style>" site/giocatori/123.html` → 1 (solo il critico, < 4 KB);
aprire una pagina in `partite/` e una in `giocatori/` e verificare che il tema sia identico
(**NON VERIFICATO qui**: serve un browser, da fare in preview o in CI con Lighthouse).

---

## 3.2 [P0 — ✅ RISOLTO in questa sessione] Tema chiaro: tre testi **invisibili** e un fallback senza 18 token

**Correzione di una mia valutazione precedente.** In prima lettura avevo attribuito al blocco
`@media (prefers-color-scheme: light)` incompleto un impatto su "tutti i visitatori in tema chiaro".
**Era sbagliato**: `base.html:18` esegue uno script inline che legge le preferenze dell'OS e imposta
subito `data-theme="light"`, quindi la palette completa di `[data-theme="light"]` si applica
normalmente. Il blocco `@media` è il **fallback per chi non esegue JavaScript**: lì mancavano
18 token su 30, e solo in quel caso l'accento restava `#28c893` su bianco (2,15:1).
Impatto reale più stretto di quanto scritto — ma il difetto c'era.

I difetti **gravi** invece colpiscono tutti gli utenti in tema chiaro, e stavano in colori
hard-coded che nessuna palette copriva. Più uno che colpisce **entrambi** i temi:

| Elemento | Prima | Contrasto | Effetto per chi legge |
|---|---|---|---|
| `.form-dot.V` — la «V» della guida-forma | testo `#9df0cf` su `--accent-dim` `#d6f0e6` | **1,11:1** | **invisibile**: su ogni card la prima delle ultime 5 gare spariva (le altre due, N e P, avevano sfondo hard-coded scuro e restavano leggibili → la guida sembrava rotta a caso) |
| `::selection` — testo selezionato | `#eaf0f6` su velatura chiara | **1,02:1** | **invisibile**: selezionando una frase non si legge cosa si è selezionato |
| `.scoregrid td.mode` — punteggio più probabile | override chiaro `color:#ffffff` sul verde della heatmap | **2,09:1** | illeggibile proprio la cella che la didascalia indica come «la più probabile» |
| `a:hover` | `#4cd9a8` hard-coded | **1,78:1** | i link sparivano al passaggio del mouse |
| `.updated .ver` — pill della versione | `--brand-a` `#2ee59d` su `#d6f0e6` | **1,36:1** | illeggibile |
| `.prob-labels span:last-child` | `#ef918b` hard-coded | **1,92:1** | illeggibile |
| legende dei grafici (4 righe) | `#28c893` / `#4c9dd3` / `#e0605a` / `#7f8aa0` | 2,15 / 2,97 / 3,51 / 3,47 | pallini quasi invisibili; il grafico **sopra** invece è leggibile (canvas scuro proprio: contrasto interno 5,0-9,4:1) |
| `.bar .a` — segmento «2» della barra 1X2 | gradiente con stop scuro `#b2403b`, testo `#06231a` | **2,92:1** | **in entrambi i temi**: la percentuale della squadra ospite illeggibile nella metà bassa della barra |
| `.bar .h` — segmento «1» | stop scuro `#1b9270` | 4,27:1 | in entrambi i temi, appena sotto AA |
| tema **scuro**: `--lose` e `--draw` usati come testo | `#e0605a` / `#7f8aa0` su `#212c3a` | 4,03 / 4,07 | `.bad`, `.status-live`, `.cal-fav-*` sotto AA anche al buio (difetto pre-esistente, trovato dal test nuovo) |

**Soluzione applicata.**

1. **Otto token di foreground nuovi** in `:root`, con i valori **già in uso** (il tema scuro non
   cambia di una virgola): `--accent-hover`, `--accent-strong`, `--on-accent`, `--sel-bg`/`--sel-fg`,
   `--lose-soft`, i tre gruppi chip `--v-bg/-fg/-line`, `--n-*`, `--p-*`, e i sei campioni legenda
   `--leg-home/-away/-save/-draw/-block/-off`.
2. **Ogni hard-coded sostituito** con il token corrispondente: `a:hover`, `::selection`,
   `::-moz-selection`, `.updated .ver`, `nav a[aria-current]`, `.posbtn[aria-pressed]`, `.tag`,
   `.hero-signal`, `.filter-button[aria-pressed]`, `.signal-agree span`, `.V/.N/.P`,
   `.form-dot.V/.N/.P`, `.prob-labels span:last-child`, il bordo dell'header, le 3 legende di `match.html`.
3. **Palette chiara ricalcolata** per stare ≥ 4,5:1 su **quattro** superfici (non tre: anche
   `--surface3 #e2e8f0`, così una regola futura che appoggia un accento su quel fondo non rompe
   il vincolo). Valori in §3.5.
4. **Fallback `@media` completato**: dichiara gli stessi 30 token con gli stessi valori.
5. **Gradienti della barra 1X2 corretti**: `.bar .h` stop scuro `#1b9270` → `#1c9874` (4,59:1);
   `.bar .a` → `linear-gradient(180deg,#e8685f,#e0605a)`, cioè si schiarisce lo stop **chiaro** e si
   tiene `#e0605a` — il rosso del marchio — come punto più scuro (4,74:1). Il segmento X resta
   `#7f8aa0` con testo proprio `#0d1420` (5,31:1).
6. **Override `[data-theme="light"] .scoregrid td.mode` eliminato**: la cella ha già lo sfondo verde
   dal template e il testo scuro `#06231a` rende 7,95:1 in entrambi i temi.
7. **Tema scuro**: `--lose` `#e0605a` → `#f06760` (4,59:1) e `--draw` `#7f8aa0` → `#8793aa` (4,57:1).
   I gradienti della barra non usano questi token, quindi l'aspetto della barra è invariato.
8. **14 test nuovi** in `tests/test_tema_contrasto.py`: verificano il contrasto **senza browser**
   e — punto qualificante — **derivano dal CSS** quali token sono usati come testo, quindi se domani
   una regola nuova usa `--accent-soft` come colore di testo il test inizia a pretendere 4,5:1 da solo.

**Eccezioni dichiarate nel test** (non sono falsi positivi nascosti, sono requisiti diversi):

| Caso | Requisito applicato | Motivo |
|---|---|---|
| `.bar`, `.scoregrid td.mode` | verificati a parte sui loro sfondi reali | lo sfondo non è nella stessa regola (gradienti figli / inline style del template) |
| `.fact-separator` | nessuno | separatore decorativo «·», colorato come il token del bordo di proposito |
| `--leg-*` (pallini delle legende) | **3:1** (WCAG 1.4.11, grafica non testuale) | il glifo «●» è un campione di colore, non un carattere da leggere; resta identico al colore della serie nel grafico |
| superfici e bordi (`--bg`, `--line`, …) | nessuno | WCAG 1.4.11 vale per l'informazione **necessaria a capire il contenuto**; pretendere 3:1 sulle card significherebbe snaturare il design |
| canvas dei grafici `#101a24` | 3:1 sui colori dei **dati**, 1,3:1 sul tratteggio del campo | scelta deliberata: il pannello è scuro in entrambi i temi; il tratteggio è contesto, non informazione |

**Verifica eseguita.**

```bash
$ .venv/bin/python -m pytest -q                        # 190 passed (176 + 14 nuovi)
$ .venv/bin/ruff check tests/test_tema_contrasto.py    # All checks passed!
$ .venv/bin/fda build                                  # 2m22s, 4.123 pagine
$ .venv/bin/python scripts/verify_site.py              # nessun problema · 11.565 controlli
```

**NON verificato qui** (serve un browser): la resa effettiva dei due temi. Da fare in preview o con
Lighthouse CI (§3.11) — il contrasto è garantito dall'aritmetica, l'estetica no.


## 3.3 [P0] Barre 1X2: il 22% delle schede pubblica percentuali che sommano 99 o 101 — e la correzione esiste già

**Osservato.** `match.html:44` (barra hero) e `match.html:81` (barre della catena di probabilità)
arrotondano le tre probabilità **indipendentemente**:

```html
<span class="h" style="width:{{ (p.p_home*100)|round }}%">1 · {{ (p.p_home*100)|round|int }}%</span>
<span class="d" style="width:{{ (p.p_draw*100)|round }}%">X · {{ (p.p_draw*100)|round|int }}%</span>
<span class="a" style="width:{{ (p.p_away*100)|round }}%">2 · {{ (p.p_away*100)|round|int }}%</span>
```

**Il progetto ha già la funzione corretta**: `fmt.pct_triple()` (resto massimo, tie-break stabile,
testata property-based in `tests/test_site.py:671-684`), esposta anche da `build.pct_triple()`.
È usata in **un solo punto**: `build.py:276` (le righe compatte del calendario).

**Misura sul sito pubblicato.**

| Barra | Esaminate | Non sommano 100 | Quota |
|---|---|---|---|
| Hero (etichette intere) | 167 | **37** | **22,2%** |
| Catena di probabilità (etichette a 1 decimale) | 277 | **64** | **23,1%** |
| Pagine in cui **anche le larghezze** non sommano 100 | — | **57** | — |

Esempi reali: `5749661.html` → 51 + 23 + 25 = **99**; `5749673.html` → 72 + 17 + 10 = **99**;
`5749675.html` → 44 + 27 + 30 = **101**.

**Impatto.** La barra 1X2 è **il contenuto più guardato della scheda**: è sopra la piega, è colorata,
è il numero che l'utente ricorda. Pubblicare "51% · 23% · 25%" insegna al lettore che il sito
sbaglia i conti — su un portale il cui patto è "ogni numero è verificabile". E le larghezze che
sommano 99 lasciano un **filetto vuoto** a destra della barra (difetto visivo visibile, non solo aritmetico).

Il caso delle barre a 1 decimale è diverso e più sottile: `|dec(1)` su tre numeri indipendenti dà
61,0 + 24,2 + 14,9 = **100,1**. Qui il resto massimo va applicato **alla prima decimale**, non all'intero.

**Soluzione.** Due righe di template + un helper per i decimali.

```python
# src/fda/site/fmt.py — accanto a pct_triple()
+def pct_triple(p: tuple[float, float, float], nd: int = 0) -> list[float]:
+    """Vettore 1X2 -> ``nd`` decimali che sommano esattamente 100 (resto massimo stabile).
+
+    ``nd=0`` e' il comportamento attuale (interi, usato dalle righe di calendario);
+    ``nd=1`` serve alle barre della catena di probabilità, dove arrotondare i tre valori
+    indipendentemente produce 99,9 o 100,1 nel 23% delle schede (docs/19 §3.3).
+    Si lavora su interi scalando di 10**nd: UNA sola implementazione per entrambi i casi.
+    """
+    k = 10 ** nd
+    raw = [float(v) * 100.0 * k for v in p]
+    base = [math.floor(x) for x in raw]
+    resto = int(round(100.0 * k)) - sum(base)
+    if resto == 0:
+        return [b / k for b in base]
+    resid = [r - b for r, b in zip(raw, base)]
+    order = np.argsort(resid, kind="stable")          # minori prima
+    if resto > 0:
+        order = order[::-1]                           # maggiori prima
+    for i in range(abs(resto)):
+        base[int(order[i % 3])] += 1 if resto > 0 else -1
+    return [b / k for b in base]
```

Con la firma generalizzata **non** serve una seconda funzione: i test esistenti
(`tests/test_site.py:671-684`) continuano a valere per `nd=0` e vanno estesi con
`assert pct_triple((0.61, 0.2424, 0.1476), 1) == [61.0, 24.2, 14.8]` (somma 100,0).

```html
{# match.html:44 — barra hero #}
-{% set ph, pd, pa = (p.p_home*100)|round, (p.p_draw*100)|round, (p.p_away*100)|round %}
+{% set tri = pct_triple((p.p_home, p.p_draw, p.p_away)) %}
-<div class="bar" style="height:30px;font-size:14px"><span class="h" style="width:{{ (p.p_home*100)|round }}%">1 · {{ (p.p_home*100)|round|int }}%</span><span class="d" style="width:{{ (p.p_draw*100)|round }}%">X · {{ (p.p_draw*100)|round|int }}%</span><span class="a" style="width:{{ (p.p_away*100)|round }}%">2 · {{ (p.p_away*100)|round|int }}%</span></div>
+<div class="bar" style="height:30px;font-size:14px" role="img" aria-label="Probabilità: vittoria {{ c.home_name }} {{ tri[0] }} per cento, pareggio {{ tri[1] }} per cento, vittoria {{ c.away_name }} {{ tri[2] }} per cento"><span class="h" style="width:{{ tri[0] }}%">1 · {{ tri[0] }}%</span><span class="d" style="width:{{ tri[1] }}%">X · {{ tri[1] }}%</span><span class="a" style="width:{{ tri[2] }}%">2 · {{ tri[2] }}%</span></div>

{# match.html:81 — barre della catena: un decimale, stessa garanzia #}
+{% set trid = pct_triple_dec((st.p_home, st.p_draw, st.p_away), 1) %}
-…<span class="h" style="width:{{ (st.p_home*100)|round }}%">1 · {{ (st.p_home*100)|dec(1) }}%</span>…
+…<span class="h" style="width:{{ trid[0]|round }}%">1 · {{ trid[0]|dec(1) }}%</span>…
```

(Registrare `pct_triple` e `pct_triple_dec` in `env.globals`/`env.filters` dove il builder configura
Jinja — lo stesso punto in cui è registrato `it_plural`.)

E eliminare la doppia implementazione:

```python
# src/fda/site/build.py:37-60 — il wrapper con fallback inline duplica fmt.pct_triple
-def pct_triple(vals: tuple[float, float, float]) -> list[int]:
-    ...
-    try:
-        from .fmt import pct_triple as _pct
-        return _pct(vals)
-    except Exception:
-        import math
-        ... 15 righe duplicate ...
+# una sola implementazione (fmt.pct_triple); il re-export tiene valido
+# `from fda.site.build import pct_triple` usato dai test.
+from .fmt import pct_triple, pct_triple_dec   # noqa: F401  (re-export)
```

**Verifica.** Il blocco `[11a]` di `verify_site.py` (§2.11) passa da 37+64 fallimenti a 0.
Controllo manuale: `grep -o 'width:[0-9]*%">1 · [0-9]*%' site/partite/5749661.html` → 51/23/**26**.

---

### ✅ RISOLTO in questa sessione (P0.3) — e il difetto era più esteso: **tre** barre, 26,3% delle previsioni

Le barre con questo difetto erano **tre**, non due: anche la mini-barra delle liste
(`_matchlist.html:51`, usata in `index.html`) arrotondava tre volte in modo indipendente — in
aria-label, nelle larghezze **e** nelle etichette `.prob-labels` — e calcolava il favorito sui
valori grezzi, quindi poteva evidenziare un esito diverso dal più grande fra quelli stampati.

| Barra | File | Prima | Ora |
|---|---|---|---|
| previsione in testa alla scheda | `match.html:44` | tre `\|round` indipendenti; **nessun `aria-label`** | `{% set b1x2 = (…)\|pct3 %}` per larghezze, etichette e `aria-label` (aggiunto) |
| passi della scomposizione | `match.html:81` | etichette a 1 decimale indipendenti (99,9 / 100,1) e larghezze a intero → **due numeri diversi per lo stesso esito** | `\|pct3(1)` per larghezze, etichette e `aria-label` |
| mini-barra delle liste | `_matchlist.html:51` | tre `\|round` × 3 posti; favorito dai grezzi | `\|pct3` per tutto + `fav_i` = indice del massimo **stampato** |

**Codice toccato.**

1. `fmt.pct_triple(p, nd=0)` **generalizzato**: il lavoro è fatto in unità intere di `10**-nd`,
   quindi la somma è esatta e non dipende dall'aritmetica binaria dei decimali. Corretto anche il
   tie-break: con `argsort(...)[::-1]` la parità premiava l'**ultimo** esito, in contraddizione con
   la docstring che dichiarava la precedenza a (1, X, 2) — ora `argsort([-r for r in residuals])`,
   stabile, dà la precedenza al primo. `nd=0` continua a restituire interi (test storici invariati).
2. `build.py`: **eliminato il wrapper** `pct_triple` con la sua copia di riserva di 15 righe
   (duplicazione §3.7: se la copia diverge, calendario e scheda pubblicano percentuali diverse per
   la stessa previsione) → import diretto da `fmt`. Registrato il filtro Jinja `pct3`.
3. `verify_site.py`: nuovo controllo **[11a]**, invariante di **pubblicazione** (non di calcolo):
   le tre larghezze sommano 100, ogni etichetta coincide con la propria larghezza, l'`aria-label`
   ripete gli stessi tre numeri, la barra ha un `aria-label`, `.prob-labels` evidenzia **un solo**
   favorito ed è il massimo. Il wordmark dell'header (che riusa `class="bar"`) resta fuori senza
   esclusioni esplicite: i suoi segmenti non hanno `style="width:…"`.
4. `verify_site.py` **[10]** (scomposizione) **era scritto con la regola sbagliata**: ricalcolava i
   passi arrotondando i tre valori in modo indipendente e tollerava 0,06 pp. Dopo la correzione
   segnalava 14 pagine corrette — cioè il verificatore difendeva il difetto. Ora confronta con
   `pct_triple(…, 1)` e lo scarto ammesso è **zero**, perché pagina e verificatore chiamano la
   stessa funzione.

**Misura sulla popolazione** (`data/processed/predictions.parquet`, 2.152 previsioni):

| Regola di arrotondamento | vettori che non sommano 100 |
|---|---|
| tre arrotondamenti indipendenti, interi (barre hero e liste) | **565 = 26,3%** |
| tre arrotondamenti indipendenti, 1 decimale (barre dei passi) | **521 = 24,2%** |
| `pct_triple` | **0** |

La stima iniziale di questo audit (22,2% delle hero pubblicate, 23,1% degli steps) era quindi
**prudenziale**: sull'intera popolazione il difetto toccava il 26,3% delle previsioni.

**Verifica eseguita.**

```bash
$ .venv/bin/python -m pytest -q            # 193 passed (3 test nuovi)
$ .venv/bin/fda build                      # 2m13s → 4.123 pagine
$ .venv/bin/python scripts/verify_site.py  # nessun problema · 14.108 controlli (erano 11.565)
                                           # [11a] barre 1X2 verificate: 565
```

I tre test nuovi: proprietà a 0/1/2 decimali su 400 vettori casuali (somma esatta e scarto ≤ 1
unità), **scheda generata end-to-end** con il vettore che rompeva (`0,4049 / 0,4049 / 0,1902` →
40+40+19 = 99%) e il verificatore alimentato con barre sintetiche corrette e rotte (così il
controllo [11a] è a sua volta verificato, non solo fidato).

## 3.4 [P0] Barre della distribuzione gol oltre il 100% del contenitore: 5 pagine pubblicate con `height:183%`

**Osservato.** Le barre verticali della distribuzione dei gol usano un'altezza percentuale
calcolata **sul massimo della distribuzione**, ma in alcuni casi il valore pubblicato supera il 100%:

```
site/partite/5781741.html  height:183.0%
site/partite/5881167.html  height:183.0%
site/partite/5881154.html  height:163.0%
site/partite/5781746.html  height:108.0%
site/partite/5781743.html  height:104.0%
```
(su 2.943 dichiarazioni `height:%` nel sito → 5 pagine affette)

**Impatto.** Una barra al 183% **esce dal contenitore**: si sovrappone all'etichetta superiore o
viene tagliata (`overflow:hidden`) — cioè il lettore vede una colonna monca o un rettangolo che
invade il titolo. Su 4.128 pagine sono 5 casi, ma sono casi **visibili** e riproducibili, e
`verify_site.py` — che pure verifica che le barre dei gol sommino 100 — **non controlla l'altezza**.

**Causa probabile** (da confermare guardando il codice che produce l'altezza in
`site/advanced.py:goals_view`): la scala è normalizzata su un massimo **diverso** da quello usato
per l'altezza (es. massimo della distribuzione troncata alla coda vs massimo dell'istogramma),
oppure l'altezza è calcolata come rapporto sulla **media** invece che sul massimo.

**Soluzione.** Normalizzare una volta sola e limitare esplicitamente:

```python
# src/fda/site/advanced.py — in goals_view(), dove si calcola l'altezza di ogni barra
-        h = 100.0 * p / max_p
+        # una sola normalizzazione, e un limite esplicito: 5 pagine pubblicate avevano
+        # height:183% e la barra usciva dal contenitore (docs/19 §3.4). max_p deve essere
+        # il massimo DELLE STESSE barre che si stanno disegnando, non un altro aggregato.
+        max_p = max((b["p"] for b in bars), default=0.0)
+        h = 0.0 if max_p <= 0 else min(100.0, 100.0 * b["p"] / max_p)
```

Più il controllo permanente in `verify_site.py` (§2.11b): `height > 100%` → fallimento.

**Verifica.** `grep -o 'height:[0-9.]*%' site/partite/*.html | awk -F: '{if ($3+0>100) print}' | wc -l` → **0**.

---

### ✅ RISOLTO in questa sessione (P0.4) — causa confermata, e la didascalia dichiarava un intervallo falso

**Causa confermata nel codice** (l'ipotesi scritta in prima stesura era generica): in
`advanced.py:goals_view` la scala dell'istogramma era `pmax = max(p.max(), 1e-9)`, calcolata **solo
sui totali 0…cap**, mentre la barra della coda usava `tail / pmax`. Quando la massa oltre i 6 gol
supera quella del totale modale — cioè nelle gare ad alto λ — la barra «7+» supera il 100% del
contenitore. Misura sulla popolazione (2.152 previsioni): **9 barre oltre il 100% (0,42%)**, massimo
**183%**; le 5 pagine pubblicate erano λ totale 4,68-5,50 (due con `lambda_limitata`, cioè λ già al
tetto e dichiarato in scheda).

**Correzione applicata** — la scala include la coda, `scala = max(p.max(), tail, 1e-9)`. **Nessun
clamp**: limitare a 100 avrebbe mentito sul grafico (la coda sarebbe sembrata uguale alla moda);
ora le altezze restano proporzionali alle probabilità e la barra più alta occupa il riquadro, sia
essa un totale o la coda. Per λ 1,84+3,66: la coda vale 31,4% contro il 17,1% del totale modale,
quindi è giusto che sia lei la barra a piena altezza.

**Secondo difetto, trovato correggendo il primo: la didascalia dichiarava un intervallo falso.**
Diceva «nel **90%** dei casi il totale resta fra `q10` e `q90` gol». Con F(q90) ≥ 0,90 e
F(q10 − 1) < 0,10 la copertura garantita è **> 80%**, non 90%: misurata su 400 gare, media 87,4%.
E quando il 90° percentile cade nella coda l'estremo superiore stampava «7» invece di «7+», cioè un
intervallo chiuso dove è aperto.

Due strade possibili: allargare a 5°-95° (copertura > 90% per costruzione, frase vera) oppure
pubblicare la copertura reale. **Provata la prima e scartata**: l'intervallo 5°-95° su un asse
troncato a 6 gol diventa quasi sempre «fra 0 e 6», cioè tutto l'asse — vero ma inutile. Scelta la
seconda, che tiene l'intervallo informativo e toglie il numero dichiarato a priori:

```
- la mediana è 3 e nel 90% dei casi il totale resta fra 1 e 5 gol.
+ la mediana è 3 e fra 10° e 90° percentile il totale resta fra 1 e 5 gol — cioè nel 86,6% delle
+ 100 partite.
```

`goals_view` ora restituisce `copertura` (massa vera fra `q10` e `q90`, > 80% per costruzione),
`q90_label` («7+» quando l'estremo è la coda) e il chip passa da «90% fra 1 e 5» a «87% fra 1 e 5».

**Controlli permanenti aggiunti in `verify_site.py`** (blocco `[9]`, che già rileggeva le barre):

| Invariante | Prima | Ora |
|---|---|---|
| altezza di ogni barra ≤ 100% **e** uguale alla proporzione ricalcolata | non controllata | sì (8 barre × 160 pagine) |
| la barra più alta occupa il 100% della scala | non controllata | sì |
| mediana / estremi / **copertura** in didascalia = ricalcolati | mediana ed estremi, copertura inesistente | sì, con `80 < copertura ≤ 100` |

Corretta anche una fragilità del verificatore emessa da questa modifica: tre regex della didascalia
dipendevano dagli **a capo del template** (uno spazio secco fra le parole). In HTML il whitespace è
collassato, quindi il verificatore segnalava 160 pagine corrette dopo una riformattazione. Ora
usano `\s+`.

**Verifica eseguita.**

```bash
$ grep -oh 'height:[0-9.]*%' site/partite/*.html site/*.html | awk -F'[:%]' '$2+0>100' | wc -l   # 0
$ .venv/bin/python -m pytest -q            # 194 passed (2 test nuovi/estesi)
$ .venv/bin/fda build                      # 2m23s → 4.123 pagine
$ .venv/bin/python scripts/verify_site.py  # nessun problema · 15.548 controlli (erano 14.108)
```

## 3.5 [P0 — ✅ RISOLTO in questa sessione] Palette del tema chiaro ricalcolata: da 21 coppie sotto AA a 0

**Osservato (misura corretta).** La prima versione di questo audit contava 21 coppie sotto 4,5:1
confrontando i token con **tre** superfici. Rieseguendo la misura su **quattro** superfici (inclusa
`--surface3 #e2e8f0`, che oggi porta solo testo `--txt`/`--txt2` ma domani potrebbe portare un accento)
i valori necessari sono leggermente più scuri. Tabella definitiva, con il requisito
**min 4,5:1 su tutte e quattro**:

| Token | Prima | **Applicato** | Min su 4 superfici | Dove si vede |
|---|---|---|---|---|
| `--accent` | `#1d9a71` (3,16:1) | **`#167657`** | 4,53:1 | tutti i link, `h2`, `.status-scheduled`, `.kicker`, `.projection-p` |
| `--accent-soft` | `#1a8a65` (3,84:1) | **`#177656`** | 4,53:1 | bordi attivi, riempimenti (grafica → basterebbe 3:1) |
| `--win` | `#1a8a65` (3,84:1) | **`#177656`** | 4,53:1 | `.good`, `.prob-labels`, `.cal-fav-h` |
| `--draw` | `#6b7f9a` (3,64:1) | **`#596980`** | 4,53:1 | `.cal-fav-d`, barre coda |
| `--lose` | `#c5403a` (4,48:1) | **`#b93c37`** | 4,53:1 | `.bad`, `.status-live`, `.cal-fav-a` |
| `--amber` | `#9a7a1a` (3,61:1) | **`#7f6516`** | 4,51:1 | `.warn`, `.signal-split`, `.fact-absence`, `.gb.mode .v` |
| `--info` | `#2a7cc7` (3,88:1) | **`#246bad`** | 4,50:1 | link informativi |
| `--mut2` | `#6b7f9a` (3,64:1) | **`#596980`** | 4,53:1 | date, minuti, didascalie, `.match-score span` |
| `--brand-a` | `#2ee59d` (1,46:1) | **`#187651`** | 4,54:1 | la «C» del wordmark |
| `--brand-b` | `#e7b23c` (1,72:1) | **`#816421`** | 4,51:1 | la «M» del wordmark |
| `--accent-hover` *(nuovo)* | `#4cd9a8` hard-coded (1,78:1) | **`#146b4f`** | 5,25:1 | `a:hover` |
| `--accent-strong` *(nuovo)* | `--accent` su `--accent-dim` (4,23:1) | **`#146b4f`** | 5,38:1 su `#d6f0e6` | pill versione, `.tag`, filtro attivo, segnale concorde |
| `--on-accent` *(nuovo)* | `#06231a` hard-coded | **`#ffffff`** | 5,09:1 su `--accent` | nav corrente, posizione attiva |
| `--lose-soft` *(nuovo)* | `#ef918b` hard-coded (1,92:1) | **`#b23a34`** | 4,80:1 | etichetta probabilità ospite |
| `--v-fg`/`--n-fg`/`--p-fg` *(nuovi)* | `#9df0cf`/`#cbd5e2`/`#f7b9b2` | **`#14694d`/`#3d4c60`/`#9c322c`** | 5,64 / 7,30 / 5,95:1 sui rispettivi `--*-bg` | chip e form-dot V/N/P |
| `--sel-fg` *(nuovo)* | `#eaf0f6` (1,02:1) | **`#0f1a2b`** | 14,05:1 | testo selezionato |

Tema **scuro**: invariato tranne `--lose` → `#f06760` (da 4,03 a 4,59:1) e `--draw` → `#8793aa`
(da 4,07 a 4,57:1), entrambi usati come testo da `.bad`, `.status-live`, `.cal-fav-*`.

**Nota sul wordmark.** Le lettere «C» e «M» a 1,46:1 e 1,72:1 sarebbero **esenti** dal requisito
WCAG (1.4.3 esclude il testo che fa parte di un logo), quindi non era un obbligo: sono state scurite
comunque perché a 1,5:1 su bianco il marchio di fatto non si leggeva alla luce del sole.
Il gradiente del logo **grafico** (la favicon e il `.mark` SVG) resta quello originale: è un'immagine,
non testo, e il requisito 3:1 per gli elementi grafici non si applica ai logotipi.

**Verifica.** `pytest tests/test_tema_contrasto.py -q` → 14 passed. Il test che protegge questa
tabella è `test_contrasto_token_di_testo_aa[light]`: ricava l'elenco dei token di testo dal CSS e
li confronta con le quattro superfici chiare. Per reprodure la misura a mano:

```bash
$ .venv/bin/python - <<'EOF'
import re
def lum(h):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a,b):
    la,lb=lum(a),lum(b); return (max(la,lb)+0.05)/(min(la,lb)+0.05)
css=re.search(r'<style>(.*?)</style>',open('src/fda/site/templates/base.html',encoding='utf-8').read(),re.S).group(1)
light=dict(re.findall(r'--([a-z0-9-]+)\s*:\s*(#[0-9a-f]{6})',re.search(r'\[data-theme="light"\]\{(.*?)\}',css,re.S).group(1)))
sup=['#ffffff','#f4f6f8','#eef2f6','#e2e8f0']
for k,v in sorted(light.items()):
    m=min(cr(v,s) for s in sup)
    if m<4.5: print(f"  {k:<12s} {v}  {m:.2f}:1")
EOF
```

(Le righe che restano sotto 4,5:1 in quell'elenco sono **superfici e bordi** — `bg`, `line`,
`accent-dim`, `v-bg`… — per cui il requisito non si applica: il test del progetto le distingue
automaticamente derivando l'uso di ogni token dal CSS.)


## 3.6 [P1] Accessibilità strutturale: 0 skip-link, 99.839 `<th>` senza `scope`, salto di livello in 4.128 pagine su 4.128

**Misura sull'intero sito generato.**

| Controllo | Valore | Esito |
|---|---|---|
| Pagine con skip-link ("salta al contenuto") | **0 / 4.128** | manca |
| `<th>` totali | **99.839** | — |
| `<th>` con `scope=` | **0 (0,0%)** | manca |
| Pagine con salto di livello (`h2` → `h4`) | **4.128 / 4.128 (100%)** | manca |
| `<svg>` con `aria-hidden`/`role`/`aria-label` | **12.089 / 12.089** | **OK** |
| `<img>` | 0 (tutte icone inline) | n/d |
| `a:focus-visible` con outline | presente | **OK** |
| `prefers-reduced-motion` | presente | **OK** |

Esempio del salto (`site/index.html`): `<h1>` → `<h2 id="day-1">` → **`<h4>`** ×3.

**Impatto.** Con uno screen reader: (a) ogni pagina obbliga a tabulare attraverso **8 link di
navigazione** prima di arrivare al contenuto (nessuna scorciatoia); (b) le tabelle — che sono il
contenuto principale del sito: classifiche, mercati, precedenti — **non annunciano la relazione
cella/intestazione**, quindi "0,198" viene letto senza sapere se è RPS o Brier; (c) la struttura
del documento salta da livello 2 a livello 4, quindi la navigazione per intestazioni (il modo in cui
chi usa uno screen reader esplora una pagina lunga come `prossime.html`, 1.513 KB) perde un livello.

**Soluzione.** Tre patch, tutte in `base.html` (quindi valgono per 4.128 pagine in un colpo):

```html
 <body>
+<a class="skip-link" href="#main">Salta al contenuto</a>
 <header>…</header>
+<main id="main">
 {% block content %}{% endblock %}
+</main>
 <footer>…</footer>
```

```css
+/* skip-link: visibile solo quando riceve il focus da tastiera (non sposta il layout) */
+.skip-link{position:absolute;left:-9999px;top:0;z-index:100;padding:10px 16px;
+  background:var(--accent);color:#06231a;font:700 14px var(--font-head);border-radius:0 0 10px 0}
+.skip-link:focus{left:0}
```

```html
 {# ogni intestazione di tabella dichiara il proprio asse: 99.839 <th> oggi non lo fanno #}
-<table><tr><th>Fonte</th><th>Ultimo run</th><th class="r">Richieste</th><th>Esito</th></tr>
+<table><thead><tr><th scope="col">Fonte</th><th scope="col">Ultimo run</th>
+  <th scope="col" class="r">Richieste</th><th scope="col">Esito</th></tr></thead><tbody>
```
*(sulle tabelle generate in ciclo — classifiche, mercati, precedenti — lo `scope="col"` va sul
loop delle intestazioni e `scope="row"` sulla prima cella di ogni riga, che oggi è un `<td>`:
deve diventare `<th scope="row">`. È la modifica più estesa delle tre: ~15 template.)*

```html
 {# livello corretto: h4 -> h3 dove l'h2 padre e' il giorno #}
-<h4>{{ ... }}</h4>
+<h3>{{ ... }}</h3>
```

**Verifica.** Test (senza browser, solo parsing):

```python
def test_a11y_strutturale():
    for pg in Path("site").rglob("*.html"):
        h = pg.read_text(encoding="utf-8")
        assert 'class="skip-link"' in h, f"{pg}: manca lo skip-link"
        assert "<main" in h, f"{pg}: manca il landmark main"
        livelli = [int(x) for x in re.findall(r"<h([1-6])", h)]
        salti = [(a, b) for a, b in zip(livelli, livelli[1:]) if b - a > 1]
        assert not salti, f"{pg}: salto di livello {salti[:3]}"
        th = re.findall(r"<th\b[^>]*>", h)
        assert all("scope=" in t for t in th), f"{pg}: {sum(1 for t in th if 'scope=' not in t)} <th> senza scope"
```

---

## 3.7 [P1] 62 selettori CSS duplicati: le correzioni degli audit precedenti sono state **accodate**, non integrate

**Osservato.** 403 regole CSS, **62 selettori duplicati**. Il blocco finale di `base.html`
(righe ~461-467) si intitola `/* focus visibile + header allineamento (audit 4.2) */` e ridefinisce
`.day-group`, `.day-heading`, `.match-card`, `.projection-copy strong`, `header`, che esistono già
sopra. Altri duplicati: `*`, `h1`, `nav`, `.brand .mark`, `.brand .h`.

**Caso concreto di danno.** Nel blocco accodato:

```css
header{border-bottom:1px solid #263142}
```

`#263142` è il `--line` del **tema scuro**, hard-coded. Le regole del tema chiaro per `header`
impostano solo il `background` (`[data-theme="light"] header{background:linear-gradient(180deg,#ffffff,#eef2f6)}`),
quindi **in tema chiaro l'header ha un bordo blu-navy scuro su sfondo bianco**. Non è un problema di
contrasto (è un bordo: requisito 3:1, e 8,6:1 lo passa): è un'**incoerenza visiva** — l'unico elemento
scuro in una testata chiara.

**Impatto.** (a) 62 punti in cui l'ordine delle regole decide il risultato: modificare una regola
"sopra" non ha effetto se quella "sotto" la sovrascrive, e chi legge il CSS non lo sa;
(b) il blocco duplicato pesa ~500 byte × 4.128 pagine = **2 MB** di sito (minore, ma è lo stesso
difetto del §3.1); (c) ogni audit successivo accoda un altro blocco: la tendenza è peggiorativa.

**Soluzione.** Regola di manutenzione + pulizia una tantum:

> Le correzioni di stile si applicano **nella regola esistente**, non in un blocco nuovo in fondo.
> Se serve un override per tema, va nel blocco `[data-theme="…"]` corrispondente.

```css
-header{border-bottom:1px solid #263142}
+header{border-bottom:1px solid var(--line)}
```

E un controllo automatico che impedisce la regressione:

```python
def test_css_senza_selettori_duplicati():
    css = re.search(r"<style>(.*?)</style>", (TEMPLATES / "base.html").read_text(encoding="utf-8"), re.S).group(1)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    sel = [re.sub(r"\s+", " ", m.group(1)).strip() for m in re.finditer(r"([^{}@]+)\{[^{}]*\}", css)]
    dup = [s for s, n in collections.Counter(sel).items() if n > 1 and not s.startswith(("[data-theme", "@"))]
    assert not dup, f"selettori duplicati ({len(dup)}): {dup[:10]}"
```

*(oggi fallisce con 62 voci: va applicato **dopo** la pulizia, altrimenti blocca la CI.)*

**Verifica.** Il test sopra passa; `grep -c "#263142" src/fda/site/templates/base.html` → 1
(solo nella definizione di `--line` del tema scuro).

---

## 3.8 [P2] 35 colori hard-coded fuori dai token di design

**Misura (prima dell'intervento §3.2).** Nel CSS: **109** occorrenze di colori esadecimali,
**20** token distinti in `:root`, **66 occorrenze (35 colori distinti) fuori dai token**.
Più frequenti: `#ffffff` (7×), `#eef2f6` (5×), `#06231a` (4×), `#6b7f9a` (3×), `#f4f6f8` (2×),
`#e2e8f0` (2×).

**Misura dopo §3.2 (stessa procedura):** **47** token distinti, **19 occorrenze (14 colori) fuori dai
token**, di cui 8 sono i gradienti della barra 1X2 (identici nei due temi **per progetto**, con testo
proprio `#06231a`/`#0d1420`: la verifica di contrasto è `test_barra_1x2_stop_gradiente`) e 5 le
superfici di header/footer/hero già coperte dagli override chiari. Restano davvero da tokenizzare
`.gb.mode .fill #a9762a` e il tratteggio `#263142` del bordo header duplicato (§3.7).

**Impatto.** Ogni hard-code è un punto che il tema chiaro **non** raggiunge: sono la causa diretta
dei difetti §3.2 (hover) e §3.7 (bordo header). Con 35 colori fuori token, aggiungere un terzo tema
(o correggere un colore del marchio) richiede 35 ricerche manuali.

**Soluzione.** Sostituzione sistematica + guardia:

```python
def test_colori_solo_da_token():
    """Nessun colore esadecimale fuori da :root/[data-theme]: sono i punti che il tema non copre."""
    css = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    senza_token = re.sub(r"(:root|\[data-theme=\"[a-z]+\"\])\s*\{[^}]*\}", "", css, flags=re.S)
    hexes = re.findall(r"#[0-9a-fA-F]{6}\b", senza_token)
    assert not hexes, f"{len(hexes)} colori hard-coded fuori dai token: {sorted(set(hexes))}"
```

Eccezioni legittime da dichiarare (e quindi escludere nel test): i colori dentro i `data:` URI
della favicon (riga 20 di `base.html`) e le `rgba()` di ombre/overlay, che però andrebbero anch'esse
tokenizzate (`--shadow-1`, `--overlay`).

---

## 3.9 [P2] Font esterni: 3 richieste a `fonts.googleapis.com`/`gstatic.com` su ogni pagina

**Osservato.** `base.html:21-23`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

**Impatto.** (a) **Render-blocking**: il foglio di stile dei font blocca il first paint su 4.128 pagine
(`display=swap` evita il testo invisibile, non il ritardo); (b) **terza parte**: Google registra
l'IP di ogni visitatore — per un sito pubblico europeo è un tema GDPR concreto, e il progetto non ha
una cookie/privacy policy (non serve, se non ci sono terze parti: oggi ce n'è una);
(c) **dipendenza**: se Google cambia o blocca, la tipografia del sito cambia.
*Non verificato in sandbox: l'impatto reale in ms va misurato con Lighthouse in CI.*

**Soluzione.** Due opzioni, in ordine di preferenza:

1. **Self-host dei woff2** (2 famiglie × 4 pesi = 8 file, ~250 KB totali, serviti dalla stessa origin
   con `font-display: swap` e `preload` per i 2 pesi usati sopra la piega):
   `site/assets/fonts/{sora-700,inter-400,inter-600}.woff2` + `@font-face` nel CSS estratto (§3.1).
   Costo: 250 KB una volta per origine, **cacheati** — contro 3 richieste esterne a ogni pagina.
2. **Stack di sistema** (zero richieste, zero KB):
   ```css
   --font-head:ui-rounded,Sora,Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
   --font-body:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
   ```
   e rimuovere i tre `<link>`. Il design cambia leggermente (il sistema non ha Sora), ma il sito
   diventa completamente autonomo.

Se si mantiene Google Fonts, aggiungere almeno una privacy policy che lo dichiari.

**Verifica.** `grep -c "fonts.googleapis\|fonts.gstatic" site/index.html` → 0 (opzione 1 e 2)
oppure presenza di `docs/privacy.md` (opzione 3).

---

## 3.10 [P1] `prossime.html`: 1.513 KB in una pagina sola, con 1.987 card e un filtro che ricalcola tutto a ogni tasto

**Misura.**

| Pagina | Peso |
|---|---|
| `prossime.html` | **1.513 KB** (2.149 occorrenze di `match-card`) |
| `risultati.html` | 357 KB |
| `index.html` | 91 KB |
| `stagione.html` | 76 KB |
| `accuratezza.html` | 69 KB |
| Media `site/partite/*.html` | 96 KB (max 117 KB) |
| Media `site/giocatori/*.html` | 54 KB (max 255 KB) |

Il filtro client-side (ricerca + leghe + stato) ricalcola i **badge di conteggio** a ogni evento
`input`, cioè a ogni tasto premuto, scorrendo tutte le 1.987 card.

**Impatto.** (a) Su mobile 3G/4G debole, 1,5 MB di HTML sono ~2-4 s di solo download, prima del
parsing di 1.987 card; (b) il filtro scatta a ogni keystroke su 1.987 nodi → input lag percepibile
su telefoni di fascia bassa (*non misurabile in sandbox: serve un dispositivo reale o Lighthouse in CI*);
(c) `content-visibility:auto` è già applicato ai mesi chiusi del calendario (bene), ma le card
dell'elenco "prossime" non ne beneficiano.

**Soluzione.** Tre livelli, dal più economico:

1. **Debounce + conteggi precalcolati** (10 righe di JS, nessun cambio di struttura):

```js
-  searchInput.addEventListener('input', () => { applyFilters(); updateBadges(); });
+  // i badge contano per (lega, stato): si calcolano una volta e si aggiornano solo quando
+  // cambia il filtro lega/stato, non a ogni tasto della ricerca (docs/19 §3.10).
+  const counts = buildCounts(cards);              // {league: {scheduled: n, finished: n}}
+  let timer = null;
+  searchInput.addEventListener('input', () => {
+    clearTimeout(timer);
+    timer = setTimeout(applyFilters, 120);        // debounce: un passaggio, non uno per tasto
+  });
+  leagueSelect.addEventListener('change', () => { applyFilters(); updateBadges(counts); });
```

2. **`content-visibility` sulle card fuori vista** (una riga di CSS, guadagno grande sul parsing):

```css
+.match-card{content-visibility:auto;contain-intrinsic-size:auto 132px}
```
*(stesso meccanismo già usato per `.cal-month:not([open])`; `132px` va tarato sull'altezza reale
della card compatta — da misurare con un browser.)*

3. **Paginazione per giorno** (strutturale, da fare se il calendario cresce):
   `prossime.html` mostra i prossimi 7 giorni (≈150 card, ~120 KB) e un link
   `prossime/mese-2026-10.html` per il resto. Il calendario completo resta dove è oggi
   (`_matchlist.html`), che è già paginato per mese con `<details>` chiusi.

**Verifica.** `stat -c %s site/prossime.html` < 400.000 dopo il livello 3; il blocco `[11e]` di
`verify_site.py` (§2.11) con `MAX_PAGE_KB = 900` intercetta la regressione.

---

## 3.11 [P2] Layout 320px: cosa è verificato staticamente e cosa **non** è verificabile qui

**Verificato nel CSS** (buone pratiche già presenti):

| Regola | Stato |
|---|---|
| `.today-overview{min-width:510px}` azzerato a `min-width:0` sotto 760px | **OK** (nessun overflow forzato) |
| `.cal-head`/`.cal-row` griglia 5 colonne → 3 colonne sotto 760px | **OK** |
| Media query dedicata `max-width:380px` (gap 6px, `.cal-teams` 12,5px) | **OK** |
| `.filter-buttons{overflow-x:auto;flex-wrap:nowrap}` sotto 760px | **OK** (scroll orizzontale confinato ai filtri) |
| `.match-teams{grid-template-columns:minmax(0,1fr) auto minmax(0,1fr)}` | **OK** (`minmax(0,…)` previene l'overflow da nomi lunghi) |
| `.formation-list` 2 colonne → 1 sotto 560px | **OK** |
| `overflow-wrap:break-word` sui nomi giocatore | **OK** |
| `prefers-reduced-motion` | **OK** |

**NON verificato in sandbox** (nessun browser headless installabile):
overflow orizzontale reale a 320px, altezza toccabile dei target (le `.match-open` a `font-size:11px`
sono candidate a essere sotto i 44×44 px raccomandati), comportamento del `content-visibility`,
CLS da font esterni.

**Impatto.** Il CSS è scritto bene per il mobile: i rischi residui sono **due** e sono misurabili
solo con un browser. `font-size:11px` + `padding` ridotto su `.match-open` (il link "Analisi" di ogni
card) è il candidato più probabile a un target sotto i 44 px — su 1.987 card in `prossime.html`
è il controllo principale di ogni riga.

**Soluzione.** (a) Regola minima sui target toccabili:

```css
+/* target toccabile >= 44x44 px anche a 320px di viewport: il link "Analisi" e' il comando
+   principale di ogni card e oggi e' font-size:11px con padding ridotto (docs/19 §3.11) */
+.match-open,.filter-button,.cal-toggle{min-height:44px;display:inline-flex;align-items:center}
+@media (max-width:380px){.match-open{font-size:11px;padding:12px 10px}}
```

(b) **Verifica in CI**, che è l'unico posto dove si può fare: aggiungere Lighthouse CI al workflow
`daily.yml` con soglie esplicite (accessibility ≥ 95, best-practices ≥ 90) su 3 URL rappresentative
(`/`, `/prossime.html`, una `partite/*.html`). Costo: ~2 min di CI.

```yaml
+      - name: Lighthouse (3 URL campione)
+        run: |
+          npm i -g @lhci/cli@0.13.x
+          lhci autorun --collect.staticDistDir=./site \
+            --collect.url=http://localhost/index.html \
+            --collect.url=http://localhost/prossime.html \
+            --assert.preset=lighthouse:no-pwa \
+            --assert.assertions.categories:accessibility=["error",{"minScore":0.95}]
```

**Verifica.** Il punteggio accessibility di Lighthouse sulle 3 URL ≥ 0,95; nessun overflow
orizzontale (`document.scrollWidth <= 320`) — assertion da aggiungere allo stesso passo.

---

# 4. Piano di implementazione

## P0 — da fare subito (difetti visibili all'utente o numeri non veri)

| # | Intervento | File | Rischio | Verifica |
|---|---|---|---|---|
| P0.1 | ✅ **FATTO** — 22 token di foreground nuovi (hover, selezione, chip, leggende, `on-accent`), tutti gli hard-coded sostituiti, fallback OS completo | `base.html`, `match.html` §3.2 | **basso** (solo CSS) | `tests/test_tema_contrasto.py`: 14 test; `verify_site.py` 11.565 controlli OK |
| P0.2 | ✅ **FATTO** — palette chiara ≥4,5:1 su **4** superfici, gradienti della barra 1X2 corretti, override della cella modale eliminato, `--lose`/`--draw` scuri corretti | `base.html` §3.5 | **basso** | `test_contrasto_token_di_testo_aa[dark\|light]`, `test_barra_1x2_stop_gradiente`, `test_cella_punteggio_piu_probabile` |
| P0.3 | ✅ **FATTO** — `pct_triple(p, nd)` generalizzato, filtro Jinja `pct3`, tre barre collegate, wrapper duplicato di `build.py` eliminato, controllo `[10]` allineato alla regola di pubblicazione | `fmt.py`, `build.py`, `match.html`, `_matchlist.html`, `verify_site.py` §3.3 | **basso** | `verify_site.py [11a]`: **565 barre, 0 problemi**; 14.108 controlli totali |
| P0.4 | ✅ **FATTO** — scala dell'istogramma inclusa la coda (nessun clamp), copertura reale pubblicata al posto del «90%» dichiarato, `q90_label` per l'estremo aperto, 3 invarianti nuove in `verify_site.py` e regex della didascalia rese indipendenti dagli a capo | `advanced.py`, `match.html`, `verify_site.py` §3.4 | **basso** | `grep height:[0-9]*%` → **0**; 15.548 controlli OK |
| P0.5 | ✅ **FATTO** (2026-09-16, `docs/21` §18.4) — CSS esterno con cache-busting, **sito 273 → 109 MB (−60%)**, invariante [29] (4.136 pagine) | `build.py`, `base.html`, `assets/site.css` | — | verify_site 0 problemi · 32.867 controlli |
| P0.6 | ✅ **FATTO** (2026-09-16, `docs/21` §18.3) — composizione dichiarata: 12 su 93 col modello corrente | `build.py`, `accuracy.html` | — | invariante [3b]: composizione = riga «Tutti» |
| P0.7 | `benchmark_quote.py` + job mensile: il mercato come riferimento misurato | nuovo script, nuovo workflow | **nessuno** (non tocca il modello) | n≈4.372, Δ≈+0,0096 |
| P0.8 | `verify_site.py [11]` invarianti di pubblicazione | `scripts/verify_site.py` | **basso** | deve fallire prima delle fix, passare dopo |
| P0.9 | Contatore richieste per lega (delta) + nessuna riga per fonti non usate | `collect.py:246`, `http.py` | **basso** | `stato.html`: numeri non monotoni, somma = totale run |

## P1 — entro la settimana (correttezza dei contenuti e struttura)

| # | Intervento | File | Rischio |
|---|---|---|---|
| P1.1 | ✅ **FATTO** (2026-09-16, `docs/21` §18.3) — `outcome_freqs()` su history (7.396 gare), fallback dichiarato, colonna «n base» | `build.py` | — | test + invariante [3b] sul Δ |
| P1.2 | Etichette arbitro relative alla lega + campione minimo 15 | `analysis.py:1806`, `build()` | basso |
| P1.3 | Un solo profilo arbitro (`referee_profile`) usato anche dalla narrazione | `analysis.py:1894` | basso |
| P1.4 | 5 template di curiosità recuperabili + contatore degli scarti | `analysis.py:262+` | basso |
| P1.5 | `DETAIL_WINDOW_DAYS` come unica fonte del "7 giorni" | `config.py`, `collect.py`, `cli.py`, `build.py`, 2 template | basso |
| P1.6 | `404.html` + sitemap (home unica, 7 leghe, lastmod reale, niente `[:5000]`) | nuovo template, `build.py:_write_seo_files` | medio (percorsi assoluti nel 404) |
| P1.7 | Proiezioni: arrotondamento all'unità + `mc_se()`, `TOP_N` da config, tie-break dichiarato, `neutral` limitato | `season_sim.py`, `stagione.html`, `leagues.yaml` | medio |
| P1.8 | Assert di coerenza 1X2/doppia chance | `predict.py` | basso |
| P1.9 | Backoff ESPN standings + stato "SOSPESO" in *Stato fonti* | `collect.py`, `status.html` | basso |
| P1.10 | Open-Meteo: pubblicare il motivo delle 0 chiamate + test settimanale del fallback | `collect.py`, `status.html`, `daily.yml` | basso |
| P1.11 | Griglia pre-registrata nel laboratorio (`Candidate.grid`, `n_tentativi`) | `lab.py`, `docs/00 §D` | basso |
| P1.12 | Griglia di calibrazione allineata ai bounds (o claim ridotto in `info.html`) | `calibration.py` | **alto** se si rifa il fit → preferire il claim ridotto |
| P1.13 | A11y: skip-link, `<main>`, `scope` su 99.839 `<th>`, `h4`→`h3` | `base.html` + ~15 template | medio (esteso) |
| P1.14 | Shrinkage per-90 con `shrink_rate()` unitario + eliminare `p90_shrunk()` morto | `players.py` | medio (cambia le classifiche) |
| P1.15 | `prossime.html`: debounce filtro + `content-visibility` sulle card | `index.html`/JS, `base.html` | basso |

## P2 — quando capita (pulizia e debito)

| # | Intervento |
|---|---|
| P2.1 | 62 selettori CSS duplicati: integrare i blocchi accodati, `header{border-bottom:var(--line)}` |
| P2.2 | 35 colori hard-coded → token, con test di guardia |
| P2.3 | Font: self-host woff2 **oppure** stack di sistema (elimina 3 richieste esterne) |
| P2.4 | Riscrittura delle 3 frasi-macchina di `narrative()` + frequenze naturali per l'1X2 |
| P2.5 | Indice completo di `docs/` (18 documenti) + log `players: 3737 pagine` |
| P2.6 | `fmt.pct_triple`: import di numpy/matplotlib fuori dalla funzione; un'unica implementazione |
| P2.7 | Paginazione di `prossime.html` per giorno (se il calendario cresce oltre ~250 card) |
| P2.8 | Lighthouse CI su 3 URL con soglie accessibility ≥ 0,95 (chiusura dei "non verificato") |
| P2.9 | Registrare in `model_lab.parquet` il candidato **respinto** γ-sharpening (§1.3) |
| P2.10 | Ricalibrazione del vettore 1X2 (temperatura) come candidato del laboratorio (§1.2) |

## Sequenza consigliata (perché quest'ordine)

1. **P0.1-P0.4** (un solo commit "visivo"): sono tutte modifiche a CSS/template, rischio basso,
   verificabili senza browser tranne il controllo finale. Chiudono i difetti che l'utente vede oggi.
2. **P0.8** subito dopo: senza le invarianti di pubblicazione, le fix di P0.1-P0.4 non sono protette
   da regressione.
3. **P0.6 + P1.1 + P2.7** (commit "accuratezza"): rendono la pagina *Accuratezza* internamente
   coerente e con una baseline onesta.
4. **P0.5** da solo (commit "peso del sito"): è la modifica con più superficie (percorsi relativi,
   cache, flash) e va provata in preview prima del merge.
5. **P0.7 + P1.11 + P2.9/P2.10** (commit "laboratorio"): il riferimento di mercato entra nel
   processo decisionale, con la griglia pre-registrata e il candidato γ archiviato come respinto.
6. **P0.9 + P1.9 + P1.10** (commit "raccolta dati"): la pagina *Stato fonti* dice il vero.
7. **P1.6 + P1.13** (commit "accessibilità e SEO").
8. Il resto come capita.

Ogni commit: `ruff check` sul nuovo codice (la baseline pre-esistente di 145 rilievi non va toccata),
`pytest` verde, `fda build` + `verify_site.py` con 0 problemi.

---

# 5. Prossimo passo

**Un solo obiettivo, piccolo**: applicare **P0.1 + P0.2** (tema chiaro completo e a norma AA) insieme
ai due test automatici che li proteggono (`test_tema_chiaro_completo`, `test_contrasto_tema_chiaro_aa`).

Motivo della scelta: è il difetto con il **maggior rapporto impatto/costo** di tutto l'audit —
2,15:1 sul colore più usato del sito per la maggioranza dei visitatori mobili — si corregge con
~10 righe di CSS, **non richiede un browser per essere verificato** (il contrasto è calcolabile in
sandbox, a differenza di tutto il resto dell'area visiva) e non tocca né il modello né i dati.

Comando di verifica dopo la modifica:

```bash
.venv/bin/python -m pytest tests/test_site.py -k "tema_chiaro or contrasto" -q
```

**Poi**, nell'ordine della sequenza: P0.3 (barre 1X2, la funzione `pct_triple` esiste già e va solo
collegata) e P0.8 (invarianti di pubblicazione in `verify_site.py`).

---

## Allegato A — Riepilogo delle misure nuove di questa sessione

| Misura | Valore | Riproducibile con |
|---|---|---|
| Quote di chiusura disponibili nel mirror | 7 leghe × 3 stagioni, 7.092 righe | `scripts/benchmark_quote.py` (codice §1.1) |
| Aggancio backtest ↔ quote | 5.543 / 5.815 (95,3%) | idem |
| RPS modello vs mercato (Pinnacle de-vigged) | 0,19803 vs 0,18843, **Δ +0,00960** IC95 [+0,00794; +0,01126] | idem |
| Leghe in cui il modello perde col mercato | **7 su 7** (+0,00696 … +0,01218) | idem |
| Over 2,5 Brier modello/mercato/base | 0,24436 / 0,23759 / 0,24796 (n=5.543) | idem |
| Sottostima dei favoriti (decile 10) | 0,728 previsto vs 0,799 osservato | §1.2 |
| γ-sharpening, griglia stretta | ΔRPS −0,000457 IC [−0,000769; −0,000145], 6/7 → passerebbe | §1.3 |
| γ-sharpening, griglia onesta | ΔRPS −0,000417 IC [−0,001037; +0,000203], 4/7 → **respinto** | §1.3 |
| Composizione campione *Accuratezza* | 84 gare: **3** modello corrente, **12** calibrate, **72** no | §1.5 |
| Baseline naive gonfiata di | +0,00003 (ESP1) … **+0,00205** (ITA1) | §1.6 |
| Copertura quote in `history.parquet` | 1.519 / 7.387 (20,6%): big-5 = **0** | §1.1 |
| Richieste per fonte in `stato.html` | cumulative: FotMob 19→138, Understat 2→6 (NED1/POR1 mai chiamati) | §2.1 |
| Curiosità FotMob scartate | **685 / 2.014 (34,0%)**; 75 schede (20%) con <3 | §2.5 |
| Gialli arbitro per lega | FRA1 3,85 … **POR1 5,04**; `referee_matches` min **6** | §2.6 |
| CSS duplicato | 4.128 × 34.984 B = **144,4 MB (58,2%)** su 248,3 MB HTML | §3.1 |
| Barre 1X2 errate | ✅ **0** su 565 barre pubblicate (erano 565/2.152 previsioni = 26,3%) | §3.3 |
| Barre gol in overflow | ✅ **0** (erano 9 barre su 2.152 previsioni, max 183%) | §3.4 |
| Contrasto tema chiaro | ✅ **0** coppie sotto 4,5:1 (erano 21); peggio era **1,02:1** | §3.2, §3.5 |
| Skip-link / `<th scope>` / salti h | **0** / **0 su 99.839** / **4.128 pagine su 4.128** | §3.6 |
| Selettori CSS duplicati | **62** su 403 regole | §3.7 |
| Colori hard-coded fuori token | **14** distinti (19 occorrenze), erano 35 (66) | §3.8 |
| Peso `prossime.html` | **1.513 KB**, 1.987 card | §3.10 |

## Allegato B — Cosa **non** è un difetto (verificato e chiuso)

Per non far ripetere il lavoro a una sessione futura: questi controlli sono stati eseguiti e
**non** richiedono intervento.

1. `xGOT` coperto al 99,6-99,9% in tutte le leghe (28 righe nulle su 8.233).
2. Parità post-partita **100%** su 7 leghe e 6 tabelle.
3. Tutti i 12.089 `<svg>` accessibili; 0 `<img>`; `a:focus-visible` e `prefers-reduced-motion` presenti.
4. Nessuna perdita di traduzione: 0 `nan`, 0 `None`, 0 `undefined`, 0 triple `—/—/—`;
   i 17 "residui inglesi" sono nomi propri.
5. Dotplot quantile, matrice punteggi, probabilità in-play, intervalli Wilson, backtest:
   tutti verificati da `verify_site.py` (11.590 controlli, 0 problemi).
6. Bias dei gol −0,024 su 5.815; pareggio previsto 25,9% vs 25,6% osservato.
7. Limiti di sicurezza λ: toccano lo 0,05% delle partite (1 su 2.071).
8. `PlayerCatalog` si costruisce in 0,3 s: la doppia costruzione in `_write_seo_files`
   **non** è un collo di bottiglia (verificato, nessuna ottimizzazione necessaria).
9. Layout mobile: `minmax(0,1fr)`, `overflow-x` confinato ai filtri, media query a 380px,
   `content-visibility` sui mesi chiusi — il CSS è scritto correttamente.
