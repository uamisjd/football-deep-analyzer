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

### Struttura risposta `leagues` (mappata il 2026-09-08 da documentazione pubblica — DA VERIFICARE DAL VIVO)

Fonti: `pseudo-r/Public-FotMob-API` (`docs/endpoints/leagues.md`, stato VERIFIED) e `tommhe14/fotmob-wrapper` (`FotMob.standings()` → `/data/tltable?leagueId=`, `get_league()` → `/data/leagues?id=`). Nota: il wrapper conferma che il path `/api/data/leagues` (stesso `base_url` del nostro client, senza header `x-mas`) è quello giusto; parametro `season` opzionale (default = stagione corrente).

```json
{
  "details": {"id": 47, "name": "Premier League", "selectedSeason": "2023/2024"},
  "table": [{"data": {"leagueId": 47, "table": {"all": [
    {"idx": 1, "name": "Arsenal", "id": 9825, "played": 28, "wins": 20,
     "draws": 4, "losses": 4, "scoresStr": "70-24", "goalConDiff": 46, "pts": 64}
  ]}}}]
}
```

Avvertenze per il parser (difensivo): le due fonti divergono sul nodo `table` (**lista** con `[0].data.table.all` vs **dict** con `table.data.table.all`) → gestire entrambe le forme; anche `table.home`/`table.away` disponibili (non servono). Campi riga: `idx` = posizione, `scoresStr` = "golFatti-golSubiti", `goalConDiff` = differenza reti, `pts` = punti. Nessun xG di squadra nella risposta → per il Fix B serve un'altra strada (v. sotto). Fallback candidato se `leagues` non dovesse rispondere: endpoint dedicato `tltable?leagueId={id}` (usato dal wrapper; struttura risposta non documentata → solo se serve).

## 3. Fix B — xG di stagione per NED1/POR1

**Decisione (2026-09-08): opzione 2** — la risposta `leagues` non contiene xG di squadra, quindi per le leghe senza Understat `collect` scarica i `matchDetails` di **tutte** le finite di stagione (non solo la finestra ±3 gg): ogni finita si scarica una sola volta (cache 10 anni) e il fallback FotMob in `season_xg()` diventa completo. Scelta perché riusa endpoint già verificati dal vivo (`fixtures` + `matchDetails`); l'alternativa `teamseasonstats?teamId=&tournamentId=` ha struttura non documentata. `season_xg()` resta invariato come interfaccia (sorgente dichiarata: «FotMob, N gare»).

**Implementato (2026-09-08, verificato offline)**: passo 2b in `collect_league` — finite fuori finestra recuperate dalle più recenti, tetto `max_backfill=40`/run, blocco fetch estratto in `_fetch()` riusato da finestra e backfill; contatore `matches_backfilled` nel report e in `fda collect` («N+M storiche»), opzione `--max-backfill`. Test: NED1 recupera 1 fuori finestra + 1 in finestra (0 al secondo run), ITA1 invariata, `season_xg()` FotMob su 2 finite (3,5/1,5). Suite 36 passed, ruff 47 = baseline.

## 4. Verifiche

- Offline: fixture JSON campione + test (parser tabella, standing con fallback, stagione xG completa) — suite verde + ruff pulito sul nuovo codice.
- Dal vivo: run `daily` in Actions → `fotmob_standings` popolata per 7/7 leghe, `source_status` ok, schede NED1/POR1 con classifica e stagione xG completa; confronto spot con la classifica ufficiale.

## Prossimo passo

Fix A + Fix B completati offline. Ora: verifica dal vivo in Actions — serve un run `daily` su `main` (via PR + merge utente, poi dispatch manuale dalla UI come il 2026-09-08): atteso `fotmob_standings` popolata 7/7 leghe, `match_info` NED1/POR1 con tutte le finite (stagione xG «FotMob, N gare» completa nelle schede), `source_status` senza errori nuovi.
