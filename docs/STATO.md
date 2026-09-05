# STATO DEL PROGETTO (checkpoint — aggiornato a ogni turno)

**Ultimo aggiornamento:** 2026-09-06 (passo 4 completato)

## Fatto
- [x] Studio di fattibilità e catalogo fonti (`01`, `02`) — commit `ac35f2b`
- [x] Decisioni utente registrate (7 campionati, automazione giornaliera, uso personale, quote sì, solo fonti GitHub Actions) — `03_decisioni_e_funzionamento.md`
- [x] Regole anti-blocco chat — `00_regole_di_lavoro.md`
- [x] Verifiche tecniche: penaltyblog OK (nota pandas 3), datahub CSV OK, FotMob id 7 leghe OK, matchDetails pre-partita ricco (formazione probabile, meteo, arbitro)
- [x] **Passo 1 — scaffolding**: `pyproject.toml`, `src/fda/` (config, http client con cache+rate limit+retry, cli), `config/leagues.yaml` (7 leghe + coppe), `config/sources.yaml` (budget richieste), `tests/` (6 test verdi), `.gitignore`, `data/README.md`. Comandi: `fda leagues`, `fda version`.

- [x] **Passo 2 — client FotMob** (`src/fda/sources/fotmob.py`): `fixtures`, `matchDetails`, `teams`, `playerData`, `matches?date`; parser → record piatti (MatchInfo con arbitro/stadio/meteo/xG/H2H, Shot, TeamMatchStat per periodo, PlayerMatchStat, LineupPlayer con indisponibili+rientro, eventi, momentum). Test su JSON campione (9 verdi). Comandi `fda fotmob-fixtures ITA1`, `fda fotmob-match <id>`.

- [x] **Passo 3 — Understat + ESPN**: `sources/understat.py` (endpoint JSON con cookie+XHR, senza soccerdata/seleniumbase; partite con xG, righe squadra-partita con xPTS/PPDA/deep, giocatori; `team_season_table`) e `sources/espn.py` (scoreboard con statistiche, classifiche, boxscore, arbitri). 11 test verdi. Comandi `fda understat-table ITA1`, `fda espn-today ITA1`.

- [x] **Passo 4 — storage + collect**: `store.py` (Parquet versionati in `data/processed/` + viste DuckDB, upsert per chiave, tipi UTC stabili) e `collect.py` (per lega: calendario → dettagli partite oggi ±3 gg, finite una sola volta, future a ogni run → Understat → ESPN; fonti isolate, esiti in `source_status`). 13 test verdi (incluso un run completo offline). Comandi `fda collect [ITA1 ...]`, `fda db [SQL]`.

## In corso
- Passo 5 (modelli Dixon-Coles + Elo su storico datahub → tabella `predictions`).

## Nota
- Dal sandbox dell'agente la rete verso FotMob è bloccata: i comandi `fotmob-*` vanno provati in GitHub Actions o sul PC. I parser sono coperti dai test offline.

## Prossimo passo (Fase 0 — un turno per riga)
1. ~~Scaffolding repo~~ ✅
2. ~~Client FotMob~~ ✅
3. ~~Client ESPN + Understat~~ ✅
4. ~~Storage + collect~~ ✅
5. Modello Dixon-Coles + Elo su datahub CSV → tabella previsioni.
6. Generatore sito statico (pagina Oggi + pagina Partita) + workflow GitHub Actions + GitHub Pages.
7. Estensione alle 7 leghe, report pre/post in italiano, pagina Accuratezza.

## Decisioni aperte
- Nessuna bloccante. (Telegram bot e protezione accesso: fasi successive.)
