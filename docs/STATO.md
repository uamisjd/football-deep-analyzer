# STATO DEL PROGETTO (checkpoint — aggiornato a ogni turno)

**Ultimo aggiornamento:** 2026-09-06 (PR #3 mergiata in `main`; run `daily` #3 verificato; passo 7b avviato — PR #4 aperta)

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
- [x] **PR #3 mergiata su `main`** nel commit `3359fdc` (workflow con versioni Node 24).
- [x] **Run `daily` #3 su `main` verificato** (id `33999756428`, head `3359fdc`): job `run` **Success** 3m08s + `deploy` **Success** 10s; commit dati `43b848c` pushato; artefatti `github-pages` (135358 B) e `run-log-3`; deployment Pages riuscito. `predictions` 48 → **96** righe (ITA1 20, ENG1 18, ESP1 22, GER1 18, FRA1 18), probabilità coerenti e senza null, tutte gare `scheduled`. FotMob ok 7/7; Understat per le 5 leghe coperte; ESPN standings ancora **403 isolato** (non blocca). Suite locale 20 passed. (Blob di log Actions e pagina Pages non raggiungibili dal sandbox — verifica su metadati/commit/dati.)

## In corso
- [x] **Passo 7a — resilienza del run**: ESPN standings e scoreboard isolati; `fda predict` isola errori/storici per lega. Commit `d8063c1` + `0bcde50`; suite locale 20 passed; workflow `tests`: Success.
- **Passo 7b — storico NED1/POR1 (avviato)**: il mirror `datasets/football-datasets` non copre Eredivisie/Liga Portugal e `football-data.co.uk` è irraggiungibile dagli IP cloud (root cause: nei run #2/#3 NED1/POR1 avevano partite in programma ma 0 predizioni). Risolto puntando NED1 (`eredivisie`) e POR1 (`primeira-liga`) a un mirror `raw.githubusercontent.com` dedicato con la stessa struttura `season-XXXX.csv` (campo per-lega `datahub_base`), + alias squadra alle grafie N1/P1 (`For Sittard`→`Fortuna Sittard`, `Estrela`→`Estrela da Amadora`). Commit `85b515f`.
- **Verifica passo 7b**: suite locale **23 passed** (3 nuovi test); simulazione offline con CSV reali del mirror + calendario FotMob → NED1 **11** e POR1 **9** predizioni (tutte le partite in programma; le promosse ADO Den Haag/Cambuur/Académico Viseu/Marítimo ricevono prior dagli esiti di stagione in corso via FotMob). Workflow `tests` sul branch e check PR: **Success**.
- **PR #4 aperta verso `main`**: https://github.com/uamisjd/football-deep-analyzer/pull/4; in attesa di review/merge. La verifica live end-to-end avverrà sul prossimo `daily` di `main` dopo il merge (dispatch su branch non-default non consentito dal token del sandbox; blob Actions irraggiungibile dal sandbox). Dopo la conferma live: report pre/post in italiano e rifinitura di Accuratezza con le prime gare reali.

## Nota
- Dal sandbox dell'agente la rete verso FotMob, `football-data.co.uk` e `raw.githubusercontent.com` può essere bloccata (si raggiungono solo `github.com` e `api.github.com`): le verifiche di rete vanno fatte in GitHub Actions o sul PC. I parser sono coperti dai test offline.
- Il mirror dedicato NED1/POR1 è configurato solo in `config/leagues.yaml` (campo per-lega `datahub_base`): facile da cambiare se il mirror diventasse irraggiungibile.
- Le quote The Odds API sono opzionali: vengono usate solo se `ODDS_API_KEY` è configurata.

## Prossimo passo (Fase 0/7 — un turno per riga)
1. ~~Scaffolding repo~~ ✅
2. ~~Client FotMob~~ ✅
3. ~~Client ESPN + Understat~~ ✅
4. ~~Storage + collect~~ ✅
5. ~~Modelli DC + Elo~~ ✅
6. ~~Sito statico + workflow + Pages~~ ✅
6b. ~~Primo run dal vivo in Actions e correzioni ai collettori~~ ✅
7. ~~Upgrade Node 24~~ ✅
7b. storico NED1/POR1 (in corso, PR #4) → confermare su un `daily` di `main` post-merge, poi report pre/post in italiano e rifinitura di Accuratezza con le prime gare reali.

## Decisioni aperte
- **Fonte storica NED1/POR1** (deciso 2026-09-06): mirror GitHub `raw.githubusercontent.com` di football-data.co.uk dedicato (via `datahub_base` per-lega), scelto perché il mirror datahub copre solo 5 leghe e `football-data.co.uk` diretto è irraggiungibile dagli IP cloud.
- Nessuna altra bloccante. (Telegram bot e protezione accesso: fasi successive.)
