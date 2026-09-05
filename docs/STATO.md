# STATO DEL PROGETTO (checkpoint — aggiornato a ogni turno)

**Ultimo aggiornamento:** 2026-09-06 (passo 6 completato — in attesa di PR/merge su main)

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

## In corso
- **Attivazione**: serve il merge su `main` (PR) e poi, su GitHub: Settings → Pages → Source = "GitHub Actions"; Actions → daily → "Run workflow" per il primo run dal vivo. Primo run = prima prova reale dei collettori: possibili aggiustamenti (passo 6b).

## Nota
- Dal sandbox dell'agente la rete verso FotMob è bloccata: i comandi `fotmob-*` vanno provati in GitHub Actions o sul PC. I parser sono coperti dai test offline.

## Prossimo passo (Fase 0 — un turno per riga)
1. ~~Scaffolding repo~~ ✅
2. ~~Client FotMob~~ ✅
3. ~~Client ESPN + Understat~~ ✅
4. ~~Storage + collect~~ ✅
5. ~~Modelli DC + Elo~~ ✅
6. ~~Sito statico + workflow + Pages~~ ✅ (da attivare con la PR)
6b. Primo run dal vivo in Actions e correzioni ai collettori.
7. Estensione alle 7 leghe, report pre/post in italiano, pagina Accuratezza.

## Decisioni aperte
- Nessuna bloccante. (Telegram bot e protezione accesso: fasi successive.)
