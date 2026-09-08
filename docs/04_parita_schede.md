# Parità di profondità delle schede partita (tutte le 7 leghe)

> **Stato:** diagnosi misurata il 2026-09-08 sui dati del merge PR #9 · **Direttiva utente:** schede di ogni partita accurate, precise, profonde, piene di contenuti; nessuna lega di serie B.

## 1. Diagnosi misurata (dati locali, commit `3a4303f`)

| Problema | Misura |
|---|---|
| Classifica assente su **tutte** le leghe | nessun file `espn_*` in `data/processed/` (ESPN standings 403 cronico) → `standing()` ritorna sempre `None` |
| Stagione xG magra su NED1/POR1 | Understat copre solo 5 leghe (2,0–4,1 gare/squadra); NED1/POR1 usano il fallback FotMob da `match_info` (67 finite con xG su 230 totali → ~1 gara/squadra) |
| Arbitro a volte assente | FotMob lo assegna a ridosso della gara; si riempie da sola coi run daily (nessun fix codice) |

## 2. Fix A — classifica da FotMob (tutte le leghe)

- Fonte primaria: endpoint FotMob `leagues?id={fotmob_id}` (il client ha già `league_raw()`, oggi inutilizzato) → nuova tabella `fotmob_standings` (chiave: lega + squadra; campi: posizione, giocate, vinte, pareggiate, perse, gol fatti/subiti, punti).
- `analysis.standing()` legge prima FotMob, con fallback a `espn_standings` se mai tornerà a funzionare.
- Costo: 1 richiesta per lega a run (7 totali, dentro il budget 600).
- Struttura JSON dell'endpoint da mappare da documentazione pubblica (repo `pseudo-r/Public-FotMob-API`, `tommhe14/fotmob-wrapper`, leggibili via api.github.com dal sandbox) + fixture campione e test offline; conferma del formato reale in Actions (`source_status` + commit dati).

## 3. Fix B — xG di stagione per NED1/POR1

- Opzione 1 (se disponibile): xG di squadra dalla risposta `leagues` (da verificare nella mappatura).
- Opzione 2 (fallback certo): per le leghe senza Understat, `collect` scarica i `matchDetails` di **tutte** le finite di stagione (non solo la finestra ±3 gg): ogni finita si scarica una sola volta (cache 10 anni) e il fallback FotMob in `season_xg()` diventa completo. Costo una tantum ~30 richieste/lega a inizio stagione, poi solo le nuove finite.
- `season_xg()` resta invariato come interfaccia (sorgente dichiarata: «FotMob, N gare»).

## 4. Verifiche

- Offline: fixture JSON campione + test (parser tabella, standing con fallback, stagione xG completa) — suite verde + ruff pulito sul nuovo codice.
- Dal vivo: run `daily` in Actions → `fotmob_standings` popolata per 7/7 leghe, `source_status` ok, schede NED1/POR1 con classifica e stagione xG completa; confronto spot con la classifica ufficiale.

## Prossimo passo

Mappare la risposta dell'endpoint FotMob `leagues` dalla documentazione pubblica e scrivere fixture + parser + test offline (Fix A).
