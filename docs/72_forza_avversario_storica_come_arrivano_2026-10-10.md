# 72 — «forza avv.» storica: la colonna «Come arrivano» smette di mostrare la classifica di oggi (2026-10-10)

**Voce:** B2 della [coda post-merge](69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md) §2.
**Esito:** la colonna «forza avv.» della tabella «Come arrivano» passa dalla classifica a
punti di **oggi** al rango nella **graduatoria Elo del campionato alla data della gara**,
con l'Elo storico nel tooltip — la stessa macchina della striscia «Forma» (`docs/66`).
L'anacronismo dichiarato in `docs/60` §5 è chiuso.

## 1. L'anacronismo

La tabella «Come arrivano» (`MatchAnalysis.arrival_trend`) mostrava, accanto a ogni gara
della striscia, la **posizione e i punti in classifica attuale** dell'avversario
(`self.standing(opp)`): una gara di agosto mostrava la posizione di ottobre. La colonna lo
dichiarava onestamente nel `title` («Posizione e punti in classifica attuale, non alla data
della gara») e il controllo [43] verificava solo che la dichiarazione ci fosse.

## 2. La correzione

Misurata in `docs/69` §2 prima di scrivere: 4.992 righe di tabella «Come arrivano», di cui
**4.979 (99,7%)** con rango ed Elo storici alla vigilia (la serie B di `docs/66`); **zero
fonti nuove**.

- `arrival_trend`: per ogni riga, rango nella **graduatoria Elo del campionato alla data
  della gara** (`league_elo`) ed **Elo storico** (`team_elo`) — la stessa macchina della
  striscia «Forma». La classifica a punti di oggi non entra più (e non esiste una
  classifica a punti storica: i punti attuali erano l'anacronismo).
- Template `match.html`: la cella mostra «4ª» con ⓘ (tooltip: Elo dell'avversario prima
  della gara + «graduatoria Elo del campionato alla stessa data, non nella classifica a
  punti di oggi»); l'intestazione della colonna dichiara il rango alla vigilia.
- Copertura misurata sul sito generato: **923 celle** con rango ed Elo alla vigilia
  (su 926 righe di tabella; le 3 rimanenti sono righe senza avversario, che mostrano «—»).

## 3. I controlli

- **[43] esteso**: la colonna deve dichiarare il rango alla vigilia e ogni cella deve
  portare quel rango (o «—» se non c'è Elo alla vigilia).
- **[45] nuovo — oracolo**: `check_forza_avversari_storica` — ogni riga pubblicata si
  appoggia a una gara finite del calendario (avversario + data italiana) e il rango e l'Elo
  pubblicati vengono confrontati con l'**oracolo cronologico di [44]**
  (`elo_reference_at_dates`: stesso flusso di risultati, fotografato prima di ogni istante
  — senza usare `team_elo`/`league_elo`/`arrival_trend` del generatore, così una regressione
  temporale non si autocertifica). Risultato: **923 righe verificate, 226 istanti Elo**.
- **Test**: `test_arrival_trend_forza_avversario_alla_vigilia` — il rango è quello della
  vigilia (9ª), non la classifica di oggi (1ª); senza Elo alla vigilia la cella resta vuota.

## 4. Gate (build completa)

- build: 464 schede / 2.364 partite / 7.510 giocatori;
- **571 test**, Ruff pulito;
- `verify_site` **206.667 · 0 problemi** ([43] esteso + [45]: 923 righe oracolo);
- parità **89 schede · nessuna differenza** (7 leghe);
- `resa_375` **27.255 · 0**.

## 5. Effetto

Ogni numero della tabella «Come arrivano» si riferisce alla data della gara: la colonna
«forza avv.» diventa storica come il resto della card.
