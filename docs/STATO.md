# STATO DEL PROGETTO (checkpoint — aggiornato a ogni turno)

**Ultimo aggiornamento:** 2026-09-05 (handoff ricevuto; passo 6b confermato)

## Fatto
- [x] Studio di fattibilità e catalogo fonti (`01`, `02`) — commit `ac35f2b`
- [x] Decisioni utente registrate (7 campionati, automazione giornaliera, uso personale, quote sì, solo fonti GitHub Actions) — `03_decisioni_e_funzionamento.md`
- [x] Regole anti-blocco chat — `00_regole_di_lavoro.md`
- [x] Verifiche tecniche: penaltyblog OK (nota pandas 3), datahub CSV OK, FotMob id 7 leghe OK, matchDetails pre-partita ricco (formazione probabile, meteo, arbitro)
- [x] **Passo 1 — scaffolding**: `pyproject.toml`, `src/fda/` (config, http client con cache+rate limit+retry, cli), `config/leagues.yaml` (7 leghe + coppe), `config/sources.yaml` (budget richieste), `tests/` (6 test verdi), `.gitignore`, `data/README.md`. Comandi: `fda leagues`, `fda version`.

- [x] **Passo 2 — client FotMob** (`src/fda/sources/fotmob.py`): `fixtures`, `matchDetails`, `teams`, `playerData`, `matches?date`; parser → record piatti (MatchInfo con arbitro/stadio/meteo/xG/H2H, Shot, TeamMatchStat per periodo, PlayerMatchStat, LineupPlayer con indisponibili+rientro, eventi, momentum). Test su JSON campione (9 verdi). Comandi `fda fotmob-fixtures ITA1`, `fda fotmob-match <id>`.

- [x] **Passo 3 — Understat + ESPN**: `sources/understat.py` (endpoint JSON con cookie+XHR, senza soccerdata/seleniumbase; partite con xG, righe squadra-partita con xPTS/PPDA/deep, giocatori; `team_season_table`) e `sources/espn.py` (scoreboard con statistiche, classifiche, boxscore, arbitri). 11 test verdi. Comandi `fda understat-table ITA1`, `fda espn-today ITA1`.

- [x] **Passo 4 — storage + collect**: `store.py` (Parquet versionati in `data/processed/` + viste DuckDB, upsert per chiave, tipi UTC stabili) e `collect.py` (per lega: calendario → dettagli partite oggi ±3 gg, finite una sola volta, future a ogni run → Understat → ESPN; fonti isolate, esiti in `source_status`). 13 test verdi (incluso un run completo offline). Comandi `fda collect [ITA1 ...]`, `fda db [SQL]`.

- [x] **Passo 5 — modelli**: `sources/history.py` (CSV storici datahub/football-data → schema unico, quote di chiusura se presenti), `teams.py` (nomi canonici tra fonti, ~300 alias per le 7 leghe), `models/predict.py` (Dixon-Coles pesato nel tempo + Elo + ensemble 70/30 con griglia coerente; mercati 1X2, risultati esatti, O/U, BTTS, doppia chance, clean sheet; RPS). Backtest onesto Serie A 2025/26 (train 300 → test 80): RPS ensemble 0,212 vs Elo 0,218 vs naive 0,244. 18 test verdi. Comando `fda predict [ITA1 ...]`.

- [x] **Passo 6 — sito + automazione**: `site/analysis.py` (contesto analitico e frasi in italiano da regole esplicite), template Jinja2 (Oggi, Prossime, Risultati, pagina partita pre/post, Accuratezza con RPS/Brier, Stato fonti), `site/build.py`, comandi `fda build` e `fda daily` (collect → predict → build). Workflow `.github/workflows/daily.yml` (cron 5 volte al giorno + manuale, commit dei Parquet, deploy Pages) e `tests.yml`. 19 test verdi.
- [x] **Passo 6b — primo run dal vivo**: su `main`, run `daily` #2 (2026-09-06, come da handoff) concluso **Success** in 3m17s: collettori → modelli → build sito → commit dati → deploy GitHub Pages. Artefatto `github-pages` di 132 KB; Pages usa source = **GitHub Actions**. Restano solo gli avvisi non bloccanti sulla deprecazione Node.js 20.
- [x] **Correzione PR #2**: merge su `main` nel commit `968f2d7`; lo step di installazione di `daily.yml` usa `pip install -e ".[dev]"`, così `pytest` è disponibile nel workflow.

## In corso
- [x] **Upgrade GitHub Actions a Node 24**: verifica live su Marketplace/API completata il 2026-09-05. Le versioni latest risultano `checkout@v7.0.1`, `setup-python@v7.0.0`, `upload-artifact@v7.0.1`, `upload-pages-artifact@v5.0.0` e `deploy-pages@v5.0.1`; i ref richiesti nel passaggio (`setup-python@v5`, `upload-artifact@v5`, `upload-pages-artifact@v4`) usano ancora Node 20 o dipendenze Node 20. Workflow aggiornati ai latest major compatibili (`daily.yml` e `tests.yml`) nel commit `0c906ce`; test locali: **19 passed**.
- **Verifica di qualità dal vivo (parziale)**: run `daily` #2 `33998180166` su `main` ha entrambi i job (`run`, `deploy`) in success; artefatti presenti `github-pages` (135333 byte) e `run-log-2` (2432 byte). Il download degli zip dal blob Actions e la pagina Pages non sono raggiungibili dal sandbox (EOF/SSL), quindi la verifica è stata fatta sui metadati GitHub, sul commit dati e sul build locale.
- **Esito dati live**: `fixtures.parquet` ha 2364 righe e tutti i 7 id configurati; FotMob è `ok` per 7/7 leghe, Understat è presente solo per le 5 leghe coperte, mentre ESPN ha restituito HTTP 403 sull'endpoint standings per tutte le 7 (la run non si è bloccata). Le predizioni sono 48 per ITA1/ENG1/ESP1/GER1/FRA1; NED1/POR1 non hanno storico sufficiente/disponibile nel run. Probabilità senza null e somme coerenti. Build locale riuscito (2364 fixture, 158 pagine partita); Accuratezza mostra onestamente che non ci sono ancora previsioni pre-partita valutabili, perché il primo run ha predetto solo gare future.
- [x] **Passo 7a — resilienza del run**: ESPN standings e scoreboard sono ora isolati (un 403 della classifica non impedisce il recupero degli eventi) con test offline; inoltre `fda predict` isola gli errori/storici insufficienti per lega, così NED1 non interrompe il tentativo su POR1 e sulle altre leghe. Commit `d8063c1` + `0bcde50`; suite locale: **20 passed**; workflow `tests` sul branch: run `33999155759` **Success** in 44s.
- **Passo 7 — estensione/rifinitura (in corso)**: assicurare un percorso storico/predittivo per NED1/POR1 senza inventare dati, report pre/post in italiano e rifinitura di Accuratezza dopo le prime gare previste. Procedere per piccoli passi verificati.

## Nota
- Dal sandbox dell'agente la rete verso FotMob può essere bloccata: i comandi `fotmob-*` vanno provati in GitHub Actions o sul PC. I parser sono coperti dai test offline.
- Il checkout locale va riallineato/verificato con i riferimenti remoti prima delle modifiche ai workflow: il handoff indica `main` a `968f2d7`, mentre il ref locale può essere fermo a un commit dati precedente.
- Le quote The Odds API sono opzionali: vengono usate solo se `ODDS_API_KEY` è configurata.

## Prossimo passo (Fase 0/7 — un turno per riga)
1. ~~Scaffolding repo~~ ✅
2. ~~Client FotMob~~ ✅
3. ~~Client ESPN + Understat~~ ✅
4. ~~Storage + collect~~ ✅
5. ~~Modelli DC + Elo~~ ✅
6. ~~Sito statico + workflow + Pages~~ ✅
6b. ~~Primo run dal vivo in Actions e correzioni ai collettori~~ ✅
7. Upgrade Node 24 e verifica qualità dei dati/sito; poi estensione e rifinitura dei report/accuratezza.

## Decisioni aperte
- Nessuna bloccante. (Telegram bot e protezione accesso: fasi successive.)
