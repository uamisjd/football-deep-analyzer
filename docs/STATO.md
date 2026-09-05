# STATO DEL PROGETTO (checkpoint — aggiornato a ogni turno)

**Ultimo aggiornamento:** 2026-09-06

## Fatto
- [x] Studio di fattibilità e catalogo fonti (`01`, `02`) — commit `ac35f2b`
- [x] Decisioni utente registrate (7 campionati, automazione giornaliera, uso personale, quote sì, solo fonti GitHub Actions) — `03_decisioni_e_funzionamento.md`
- [x] Regole anti-blocco chat — `00_regole_di_lavoro.md`
- [x] Verifiche tecniche: penaltyblog OK (nota pandas 3), datahub CSV OK, FotMob id 7 leghe OK, matchDetails pre-partita ricco (formazione probabile, meteo, arbitro)

## In corso
- Nessun codice ancora scritto.

## Prossimo passo (Fase 0 — un turno per riga)
1. Scaffolding repo: `pyproject.toml`, `src/fda/`, `config/leagues.yaml` (7 leghe con tutti gli id), `.gitignore`, `README`.
2. Client FotMob minimale (`fixtures`, `matchDetails`) con cache su disco + test su 1 partita.
3. Client ESPN (scoreboard, standings) + Understat via soccerdata.
4. Storage DuckDB + script `collect` (una lega, oggi ±3 giorni).
5. Modello Dixon-Coles + Elo su datahub CSV → tabella previsioni.
6. Generatore sito statico (pagina Oggi + pagina Partita) + workflow GitHub Actions + GitHub Pages.
7. Estensione alle 7 leghe, report pre/post in italiano, pagina Accuratezza.

## Decisioni aperte
- Nessuna bloccante. (Telegram bot e protezione accesso: fasi successive.)
