# 90 — Storico Understat e pull request (2026-10-12)

## Cosa funziona ora
- **Comando `fda understat-storico`**: scarica le stagioni precedenti a quella in corso (2021–2025
  con la corrente 2026) per le 5 leghe coperte da Understat (ENG1, ESP1, ITA1, GER1, FRA1) e le
  salva in `understat_matches` e `understat_team_matches`. Stessi parser e store della raccolta quotidiana.
- **Workflow manuale `understat-storico.yml`**: esegue il comando in CI (la sandbox non raggiunge
  understat.com, la CI sì) e committa i due Parquet solo se cambiano, con `[skip ci]`. Usa il
  gruppo di concorrenza del `daily`, così non scrivono insieme.
- **Pull request #107 (bozza)** verso `main`: contiene tutto il lavoro della sessione.

## Vincolo: il workflow non è ancora lanciabile
GitHub registra un workflow manuale solo quando il file è su `main`. Finché la PR non è unita,
`gh workflow run understat-storico.yml` risponde 404. Il lancio è quindi bloccato dal merge, che
è una decisione tua. Dopo il merge: Actions → understat-storico → Run workflow.

## Non verificato
- Il recupero reale da Understat: non eseguito qui. Il test copre solo la pianificazione delle stagioni.
- Il dato effettivo delle stagioni: da leggere dopo il primo run (numero di partite per stagione).

## Cosa sblocca
Il candidato `dc_xg` del laboratorio (xG storico) era «in attesa di accumulo dati» (docs/53 §6.4).
Con lo storico, si può testarlo nel laboratorio, con lo stesso protocollo e la stessa regola di
promozione di docs/13 §6.5. Nessun risultato è ancora misurato.

## Non fatto in questa tranche
- Revisione delle sei sezioni della scheda (ancora da fare).
- StatsBomb: il dato c'è su GitHub, ma copre solo alcune stagioni (docs/89 §2). Non lo integro
  finché non decidi su quali campionati e stagioni usarlo.
- Clima: decisione in attesa (docs/89 §3).
