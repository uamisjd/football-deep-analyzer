# BRIEFING NUOVA SESSIONE — leggi questo per primo

> ⚠️ **Policy merge (decisione utente, 2026-09-08):** il merge delle PR lo esegue **SEMPRE l'utente, MAI l'agente**. L'agente apre la PR quando serve (sezione D di `00_regole_di_lavoro.md`), monitora i check e avvisa con la frase fissa **"👉 Tutto verde: è il momento di fare Merge (PR #N)."** — poi aspetta l'utente, senza eseguire il merge.

> **Ultimo aggiornamento:** 2026-09-08 · **Scopo:** rendere ogni nuovo agente (nuova sessione Arena) operativo in 2 minuti e senza ripetere verifiche già fatte. Questo file è la **porta d'ingresso**; in coda c'è l'elenco completo dei documenti del progetto.
> Se la chat è nuova, rileggilo sempre; se è la continuazione di una sessione già avviata su questo repo, può bastare `docs/STATO.md` + le regole `00`.

---

## 0. Cos'è il progetto (in una riga)

**football-deep-analyzer** = portale personale, gratuito e automatico di **analisi calcistica profonda**: per ogni partita produce previsioni probabilistiche calibrate (xG, Dixon-Coles, Elo, ensemble), indisponibili, arbitro, meteo, contesto, quote-vs-modello e report **in italiano** pre/post partita. Tutto gira su GitHub Actions (cron) e viene pubblicato su GitHub Pages; i dati sono versionati nel repo (Parquet + DuckDB).

## 1. Architettura e flusso (niente server, costo zero)

```
GitHub Actions (cron 5x/giorno) → collect (FotMob/ESPN/Understat/mirror) →
  Parquet in data/processed + DuckDB → predict (DC + Elo + xG) →
  build (sito statico in site/) → commit dati → deploy GitHub Pages
```

- Il comando che fa tutto è `fda daily` = `collect → predict → build`.
- Il sito è **statico**: `index.html` (Oggi), `prossime.html`, `risultati.html`, `partite/<id>.html`, `accuratezza.html` (RPS/Brier reali), `stato.html` (stato fonti). Report in italiano generati dai template `analysis.py` → `narrative`.
- Il pacchetto è installabile: `pip install -e ".[dev]"`; entry point CLI `fda` (typer).

## 2. Stato attuale del lavoro (sintesi — dettaglio sempre in `docs/STATO.md`)

- **Fase 0–7b concluse e su `main`** (PR #1–#5 mergiate): scaffolding, client FotMob, client ESPN+Understat, storage+collect, modelli (Dixon-Coles+Elo, RPS Serie A ~0,205–0,212), sito+workflow+Pages, primo run dal vivo OK (run #2/#3 Success, Accuratezza live con 19+ gare reali), resilienza del run, storico NED1/POR1 da mirror dedicato.
- **`main` HEAD:** `91f7109` (merge PR #8). Branch di lavoro della sessione corrente: `arena/01a08091-football-deep-analyzer` (ogni sessione Arena ha il proprio branch `arena/...`, indicato nel messaggio di inizio sessione).
- **Ultimo aggiornamento STATO.md**: 2026-09-08 10:32 UTC (controllo live NED1/POR1 post PR #4: nessun `daily` post-merge ancora partito, slot 10:00 in ritardo; attesa finestra conferma).

## 3. Prossimi passi (in ordine — da `docs/STATO.md`)

1. **Confermare live NED1/POR1** sul primo `daily` di `main` post-merge (il mirror dedicato è de-risked offline: NED1 11 / POR1 9 predizioni; il cron è dilazionato e il dispatch manuale dà 403 dal token del sandbox — la conferma arriva da sola quando un run `schedule` parte su `main`).
2. **Rifinire i report pre/post in italiano** e **Accuratezza** via via che le gare previste (incluse NED1/POR1) si risolvono.
3. Poi riprendere la roadmap (`01` §8): fasi **2 → 5** non ancora coperte a fondo (shot map, indisponibili+diffidati, arbitro/meteo/viaggi, notizie RSS, valori, Monte Carlo stagione → fase 2; schede giocatore → fase 3; quote The Odds API → fase 4; notifiche Telegram → fase 5).

## 4. Cosa fare appena entri (checklist rapida)

1. `git status`, `git branch`, `git log --oneline -10` → capire dov'è il lavoro (deve essere su `arena/...`, mai su `main`).
2. Leggi `docs/STATO.md` (il checkpoint vero) e `docs/00_regole_di_lavoro.md`.
3. Verifica il branch di lavoro del repo (questa sessione è fissata al branch indicato qui sopra).
4. Non rifare verifiche di rete già fatte: è tutto annotato in `03` (§"Verifiche tecniche") e in `STATO.md`.
5. Lavora a **un obiettivo piccolo per turno**, committa subito, aggiorna `STATO.md` a ogni turno.
6. Indica **da solo** quando è il momento di Create PR / Merge (regola D in `00`). Non aspettare che te lo chiedano.

## 5. Paletti di qualità (nuovi — riassunto, dettaglio in `00` sez. B)

Massima accuratezza, precisione, profondità e qualità su ogni deliverable: numeri sempre **verificabili e misurati**; distinguere in modo esplicito *verificato dal vivo* / *verificato offline* / *presunto*; non dichiarare "fatto" ciò che è solo "in attesa"; test verdi + ruff pulito prima delle PR; documenti in italiano brevi e linkati.

## 6. Dove sta il lavoro — albero essenziale

| Percorso | Contenuto |
|---|---|
| `docs/STATO.md` | **Checkpoint**: fatto / in corso / prossimo passo / decisioni aperte. Aggiornato ogni turno. |
| `docs/00_regole_di_lavoro.md` | Regole anti-blocco, paletti di qualità, quando fare PR/merge. |
| `docs/01_studio_fattibilita.md` | Studio completo: fonti (con verdetto), architettura, modelli, rischi, roadmap (fasi 0→5), appendice con esempio reale di profondità. |
| `docs/02_catalogo_fonti_dati.md` | Catalogo endpoint gratuiti verificati, limiti, id utili, schema minimo. |
| `docs/03_decisioni_e_funzionamento.md` | Decisioni utente (7 leghe, uso personale, quote) + spiegazione automazione + verifiche tecniche salvate. |
| `docs/BRIEFING_NUOVA_SESSIONE.md` | Questo file. |
| `src/fda/` | Codice: `cli.py`, `config.py`, `collect.py`, `store.py`, `http.py`, `teams.py`, `sources/` (fotmob, espn, understat, history), `models/predict.py`, `site/` (build, analysis, templates). |
| `config/leagues.yaml` | Le 7 leghe + coppe; aggiungere una lega = aggiungere una voce qui. |
| `.github/workflows/daily.yml` | Cron 5x/giorno + dispatch manuale → `fda daily`, commit dati, Pages. |
| `tests/` | 20+ test offline (parser su JSON campione, config, modelli, site, store/collect). |
| `data/processed/` | Parquet versionati + `fda.duckdb`. |

## 7. Limitazioni note (per non ri-verificare a vuoto)

- **Dal sandbox dell'agente** sono raggiungibili solo `github.com` e `api.github.com`: FotMob, Understat, ESPN, `football-data.co.uk` e il mirror `raw.githubusercontent.com` possono essere **bloccati**. Le verifiche "dal vivo" si fanno in GitHub Actions o sul PC dell'utente; i parser sono coperti da test offline.
- **Dispatch manuale** del workflow: il token del bot dà **403** anche su `main` → non si può forzare un run live in-turno; si aspetta il cron (dilazionato/irregolare).
- **football-data.co.uk diretto** irraggiungibile dagli IP cloud → si usa il mirror datahub (5 leghe) + mirror dedicato per NED1/POR1 (campo `datahub_base` in `leagues.yaml`).
- La sezione **quote** usa The Odds API solo se è impostato il secret `ODDS_API_KEY` (opzionale).

## 8. Decisioni aperte / prossime scelte che spettano all'utente

- Niente di bloccante al momento (Telegram bot, protezione accesso e collettore locale sono fasi successive).
- Da confermare col tempo: soglia/forma del monitoraggio Accuratezza (es. quanti match servono per una valutazione stabile per lega), e quando introdurre le coppe UCL/UEL per l'analisi dedicata (oggi solo calendario per la congestione).
