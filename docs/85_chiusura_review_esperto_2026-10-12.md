# 85 — Chiusura della revisione dei 12 punti dell'esperto (2026-10-12)

Stato finale dei punti di `docs/84` e decisioni prese con l'utente. Ogni punto dice cosa è
stato fatto, dove, e cosa resta fuori.

## 1. Stato dei punti

| Punto | Decisione | Stato | Dove |
|---|---|---|---|
| 1 · hero / «valore» | mantenere la scelta editoriale (niente quote in pagina) | chiuso, nessuna modifica | `docs/38` |
| 2 · testo pre-partita | niente LLM; template deterministico | chiuso, nessuna modifica | — |
| 3 · semaforo fattori | grigio «nei parametri», ambra «vicino alla soglia» (entro il 20%), verde/rosso per il vantaggio | fatto; corretto il colore della trasferta (legenda rosso, codice ambra) | `analysis.py` (`_calma`, `FACTOR_NEAR_SHARE`), `match.html`, `site.css` |
| 4 · radar | PPDA e profondità (entrambe Understat) solo se disponibili per **entrambe** le squadre | fatto, con testo di aiuto che dichiara il perché | `analysis.py` (`clash_radar`) |
| 5 · fatti non tradotti | report completo delle forme scartate, più frequenti prima | fatto, 92 forme distinte nel build di oggi | `analysis.py` (`insight_drop_stats`), `status.html` |
| 6 · «Come arrivano» | trend con margine di significatività; EMA non adottata (peggiora l'errore dell'8% nel backtest) | fatto nella tranche precedente | `analysis.py`, `docs/60`, `docs/72` |
| 7 · giocatori che decidono | Locatelli escluso dalla «prossima gara» se indisponibile; jolly: ≥5 subentri e media ≥10′ | fatto | `analysis.py` (`_unavailable_next_match`, `bench_jolly`) |
| 8 · ruolo n.d. | nessuna pillola quando il ruolo manca; «ruolo n.d.» non compare mai | fatto | `match.html`, `verify_site.py` |
| 9 · Monte Carlo | probabilità condizionate per gara: titolo, UCL, retrocessione se la gara finisce 1, X o 2, con le altre gare simulate | fatto; controllo di verifica con la legge della probabilità totale | `season_sim.py` (`simulate_conditions`), `analysis.py` (`conditional_stakes`), `match.html`, `verify_site.py` [4b] |
| 10 · clima del club | non toccato: nessuna decisione dell'utente su VADER/Transformers | **aperto** | `docs/81`–`83` |
| 11 · waterfall | frase «In breve» generata dai passi salvati, con i numeri delle barre | fatto | `advanced.py` (`probability_summary`) |
| 12 · griglia gol | cap adattivo da 6 a 11 barre finché la coda oltre il cap è sotto l'1%; matrice 0–5 con coda dichiarata | fatto; `info.html` aggiornato | `advanced.py` (`adaptive_goals_cap`) |

## 2. Correzioni emerse in questa tranche

- **Pipeline rossa (ruff).** Le esecuzioni `tests` sui push del branch fallivano allo step
  «Controllo statico (ruff)». Gli 8 avvisi erano stati introdotti dalle mie modifiche: avevo
  scritto che fossero preesistenti, ed era sbagliato. `main` passa il lint. Corretti con
  `ruff check --fix` e la rimozione di una variabile inutilizzata (`ps`) nel codice del jolly.
  Ora `ruff check .` è pulito.
- **Verifica del verificatore.** Un controllo di `verify_site` basato su una stringa
  («Understat, ») colpiva un tooltip della card Fattori invece della card «Le due squadre».
  Il test ora delimita la ricerca dopo l'ancora della card.
- **Dati.** `history.parquet` era stato riscritto da una run senza rete (fallback). Ripristinato
  dal commit. `season_sim.parquet` e `season_sim_cond.parquet` restano locali e non committati:
  li rigenera la CI giornaliera.

## 3. Verifiche

- `pytest`: 650 test passati (baseline del progetto: 637).
- `ruff check .`: pulito.
- `verify_site.py`: nessun problema; nuovo controllo [4b] sulla legge della probabilità totale
  per ogni gara condizionata.
- Visivo (Chromium headless): nessun overflow orizzontale della pagina partita né a 390 px né
  a 1280 px. Le tabelle larghe scorrono nel contenitore `tablewrap`, come previsto.
- Limite della sandbox: il glifo ⓘ appare come quadrato per mancanza di font, non nel sito.

## 4. Limiti da tenere presenti

- **Bundesliga**: senza rete lo storico non si scarica. Nessuna simulazione di stagione né
  probabilità condizionate, come già accadeva. Da verificare nella run CI con rete.
- **Tempi**: le probabilità condizionate aggiungono circa 1,5 minuti per lega alla simulazione.
- **Il modello non garantisce risultati**: le probabilità condizionate descrivono scenari,
  non previsioni certe.

## 5. Aperto

- Punto 10 (clima del club): decisione dell'utente richiesta prima di qualsiasi modifica.
