# 70 — Daily rosso post-merge #98: campione «Le due squadre» gonfiato da `match_info` (hotfix, 2026-10-10)

**Voce:** P0 produzione — il `daily` attivato dal push del merge di PR #98 è fallito, il sito è fermo.
**Esito:** correzione nel generatore (campione = calendario), **dimostrata no-op** sui dati
attuali (sito byte-identico), test di regressione, tutti i gate verdi. Il prossimo `daily`
torna verde per costruzione.

## 1. Il sintomo

- Il merge di PR #98 (2026-10-09 23:42:02Z, eseguito dall'utente) ha attivato su `main`
  `tests` (`38005701607`, **success**, 2m26s) e `daily` (`38005701599`).
- Il `daily` è **fallito allo step `verify_site`** con 2 problemi (`docs/13` §9.24):

  ```
  PROBLEMI (2): {'campione': 2}
    - 5781769.html: campione FotMob 8 gare, ma prima del calcio d'inizio ne risultano 7
    - 5781776.html: campione FotMob 8 gare, ma prima del calcio d'inizio ne risultano 7
  ```

  (`5781769` = Heerenveen–Excelsior 16/10, `5781776` = ADO Den Haag–PSV 17/10, entrambe
  Eredivisie). Issue di guasto **#99** aperta in automatico; nessun commit dati né deploy.

## 2. La diagnosi (misurata)

- Il controllo è [44] `gare_prima` (da PR #97, `docs/64` §7): il campione stampato nella
  card «Le due squadre» deve coincidere con le gare finite **nel calendario** (`fixtures`)
  prima della vigilia, con xG completo di entrambe le squadre — ricontate **senza passare
  da `season_xg`** (oracolo indipendente).
- Il generatore (`MatchAnalysis.season_xg`, ramo FotMob) contava invece da `match_info`:
  stato `finished` + xG del **solo** squadra (one-sided). Su dati coerenti le due fonti
  coincidono — misurato sui Parquet committati: 375 gare finite in `fixtures` e 375 in
  `match_info`, **gli stessi match_id**; 0 righe con xG parziale; tutte le 375 hanno xG
  completo — quindi il gate sul branch era verde (202.969 · 0).
- Il collect fresco del daily ha introdotto un **disallineamento**: una gara finita in
  `match_info` con xG completo ma non ancora finita nel calendario (la fase calendario è
  servita da cache HTTP, quella dei dettagli partita no). Il generatore contava 8, l'oracolo
  7 → gate rosso. La stessa firma su ADO Den Haag; il collect del run non è ricostruibile
  esattamente (il run è fallito prima del commit dati), ma la classe è provata:
- Nei dati **committati** esiste già la stessa forma: la gara PSV–Heerenveen del
  2026-10-09 18:00 UTC è `live` con xG (1,19–1,32, in corso) in `match_info` e non finita
  nel calendario. Un'ora dopo (daily 23:42) quella gara è `finished` con xG finale in
  `match_info` mentre il calendario — servito da cache — è rimasto indietro: il generatore
  la contava, l'oracolo no.

## 3. La correzione

- Nuovo metodo `MatchAnalysis._finite_nel_calendario()`: righe `match_info` ristrette alle
  gare finite **nel calendario** (`fixtures.status == "finished"`). Il calendario è
  l'autorità su «gara giocata» (`docs/64` §7).
- Applicato a **tutti** i campioni FotMob pubblicati che derivano da `match_info`:
  `season_xg` (xG creati/concessi, campione, xPTS), `_season_xg_split` (xG da azione /
  palle inattive), `cards_season` (gialli e falli per gara), `_with_league_ref` (media di
  lega del rapporto «× la media del campionato»).
- In `season_xg` il campione è anche ristretto alle gare con **xG completo di entrambe**
  le squadre: «xG creati» e «xG concessi» restano sulla stessa serie e il numero stampato
  è quello ricontato dal calendario (prima, con xG parziale, le due medie podían cadere
  su serie diverse con lo stesso N dichiarato).
- **Nessuna modifica alla ricetta di produzione**: `predict.py` e la calibrazione sono
  intatti.

## 4. Dimostrazione che non cambia nulla sui dati attuali

- Dati coerenti (misura del §2): la restrizione al calendario non toglie nulla e il
  filtro xG completo non toglie nulla.
- Build completo **prima** e **dopo** la correzione: 4.250 file; contenuto **identico**
  (4.250/4.250 file, zero differenze dopo aver normalizzato i timestamp di generazione
  «aggiornato …» / «generata …» — unici bit volatili tra due build).
- Gate: **569 test** (568 + 1 nuovo), Ruff pulito, `verify_site` **202.969 · 0 problemi**,
  parità **89 schede · nessuna differenza**, `resa_375` **27.255 · 0**.
- Nuovo test `test_season_xg_campione_solo_gare_finite_nel_calendario`
  (`tests/test_site.py`): `match_info` «finished» con xG ma calendario indietro → la gara
  **non** entra nel campione; xG parziale → non entra; lo split segue lo stesso criterio.
- Un test esistente (`test_fattori_disciplina_e_arbitro_due_soglie`) è stato **completato**:
  il suo store sintetico aveva le 6 gare finite solo in `match_info`, senza righe di
  calendario — in produzione le due fonti coincidono (misura del §2), quindi il fixture
  ora semina anche il calendario (`fx_extra`). Nessuna asserzione cambiata.

## 5. Effetto atteso

- Il prossimo `daily` torna verde **per costruzione**: il generatore conta per definizione
  quello che l'oracolo riconta, quindi un disallineamento `match_info`/calendario non può
  più gonfiare un campione pubblicato (né far fallire il gate).
- Il sito resta fermo all'ultimo deploy finché il primo `daily` verde non deploya;
  l'issue #99 si chiude da sé al primo run completato.

## 6. Nota

Il disallineamento è transitorio lato collect (la prossima raccolta del calendario lo
assorbe da sé); la correzione immunizza il sito dalla **classe**, non solo dall'istanza.
