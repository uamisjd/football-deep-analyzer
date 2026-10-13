# 103 — Revisione della sezione «Precedenti» (`#precedenti`), prima voce della coda di `docs/101` §4 (2026-10-13)

Metodo `docs/57` / regola `docs/00` B.10: **misura prima, poi la correzione più piccola che
il dato giustifica**. Elenco canonico delle pagine: `site/sitemap.xml` (4.316 pagine; 498
schede partita = 58 pre-partita + 440 finite). Nessun cambiamento di modello, nessun Parquet
toccato.

---

## §1 — Misura d'ingresso (le tre domande di `docs/101` §4.1)

**1) Copertura.** Sette leghe, tutte presenti; nessuna lega scoperta.

| Blocco della card | pre-partita (58) | finite (440) |
|---|---|---|
| `Bilancio (N)` completo (ciambella, gol/gara, BTTS, Over 2,5, striscia dei pareggi, risultato più frequente, sotto-serie per campo) | **52** | **0** |
| bilancio corto (1-2 precedenti: 3 numeri senza frequenze) | 5 | 433 |
| segnaposto «Nessun precedente in archivio» | 1 | 7 |

- Le **8 schede col segnaposto** sono vere: sulle 8 l'archivio (`h2h.parquet` filtrato come
  `_h2h_core`) è vuoto. Nessuna delle 8 è una neopromossa «spiegata male»: non ci sono
  precedenti, punto.
- Il blocco completo **non esiste sulle finite per progetto**, non per difetto: `h2h_pattern`
  è nella famiglia dei blocchi pre-partita (`if status != "finished" else None`, come
  `key_players_deep` e `absences_weight`, introdotti così il 12/09 in `6124bb3`). La pagina
  post-partita è un **referto**: bilancio + ultimi 5 + frequenze sui 5 mostrati.
  *Misurato e scartato (B10):* portare il blocco completo sulle 433 finite cambierebbe la
  natura della pagina per un guadagno mai misurato — la coda di `docs/101` chiede la
  revisione delle sezioni, non la loro estensione alle pagine finite.

**2) Coerenza interno↔archivio** (oracolo indipendente, ricalcolo dai Parquet):

- 490 schede con l'elenco «Ultimi precedenti», **2.353 righe**; 0 date ripetute, 0 righe con
  data ≥ calcio d'inizio (regola della vigilia), 0 righe con data, punteggio o esito `V/N/P`
  divergenti dall'archivio, 0 righe anomale (terza squadra) in tutte le 498 schede.
- Il bilancio corto di FotMob combacia **438 casi su 438** col ricalcolo dall'archivio: le due
  viste vengono dallo stesso nodo `h2h` della stessa risposta — motivo per cui il fix §4 non
  introduce un numero non verificabile, ma ne rende verificabile uno che c'era già.

**3) Sotto-serie per campo (M6 di `docs/55`).** Pubblicata su **39** schede (8–25 casi,
39–60% del bilancio); su **13** schede con 2–7 casi la riga **non c'era e non diceva perché**
(è esattamente il difetto che M6 chiedeva di chiudere). Soglia: 8 casi, decisa in `docs/20`
§11 — non si tocca. Note di trend BTTS/Over: 21 schede, tutte pre-partita, nessuna incoerenza.

**Difetto trovato dalla revisione** (non segnalato da nessuna domanda): **8 schede** stampavano
«nessun pareggio **negli ultimi 1**» nella riga della striscia senza pareggi.

---

## §2 — Fix 1: «nessun pareggio negli ultimi 1» → «nell'ultimo precedente» (8 schede)

Stessa classe dell'incidente del `daily`: un «1» davanti a un plurale, qui con **l'ordine
invertito** (l'1 segue l'aggettivo), che i tre rami di `AGREEMENT` non potevano vedere perché
cercano il numero *prima* della parola.

- **Template** (`match.html`, riga della striscia): il ramo `draw_drought == 1` dice
  «nessun pareggio nell'ultimo precedente»; `>= 2` resta «negli ultimi N»; `0` resta
  «l'ultimo precedente è finito in pareggio».
- **Invariante (quarto ramo di `AGREEMENT`, `verify_site.py`):**
  `(altri|altre|ultim[ie]|prim[ie]|prossim[ie]|scors[ie]) 1` — misurato *prima* di aggiungerlo
  sulle **4.314 pagine + gli attributi leggibili**: l'unica forma presente era il difetto
  (8 occorrenze), 0 falsi positivi; il guard `(?![\d.,])` esclude i «1.000» col separatore.
- **Prova che morde:** `tests/test_site.py` (pagina con ultimo precedente non pari e secondo
  pari) asserisce la frase singolare e l'assenza di «ultimi 1»; `test_numeri_pubblicati.py`
  aggiunge «nessun pareggio negli ultimi 1» / «nelle ultime 1» ai positivi e «negli ultimi 2» /
  «primi 1.000» ai negativi.

**Prima/dopo:** 8 → **0** occorrenze del difetto; 8 schede col singolare corretto; 38 schede
col plurale (2–15) invariate. Il quarto ramo girato sul sito nuovo: **0 hit**.

## §3 — Fix 2 (M6): la sotto-serie per campo ora dice *perché* non c'è (13 schede)

- `h2h_pattern` espone `venue_n` **sempre** (anche sotto soglia): è il conteggio che serve a
  spiegare l'assenza, non a pubblicare frequenze.
- Template: sotto gli 8 casi la riga diventa «di cui con {casa} di casa (N): **sotto la soglia
  di 8 casi non pubblichiamo le frequenze**» — dichiarata al posto giusto, non in un tooltip.
- **Invariante ([5] estesa):** su ogni scheda col blocco completo il numero mostrato
  (`di cui con … di casa (N)`) viene ricalcolato dall'archivio; con ≥ 8 casi la riga deve
  esserci e **senza** la frase di soglia, con 1–7 casi deve esserci **con** la frase, con 0
  casi non deve esserci nulla. 52 schede coperte (39 pubblicate + 13 col motivo).

## §4 — Fix 3: anche il bilancio corto porta il numero dei casi (438 schede)

Sul bilancio corto (≤ 2 precedenti) l'etichetta era «Bilancio» senza conteggio: il lettore non
poteva distinguere due gare da uno storico, ed era l'unico blocco della card a omettere la
numerosità. Ora è «Bilancio (2)», «Bilancio (1)», con la somma dei tre numeri stampati accanto.

- **Invariante:** `[5]` leggeva `Bilancio (N)` solo sulla riga completa (52 schede); dal 13/10
  la stessa etichetta esiste su **tutte** le 490 schede col bilancio. Sulle righe complete il
  conteggio resta ricontrollato contro l'archivio (come prima); sulle corte la lettura verifica
  che l'etichetta sia **la somma dei tre numeri mostrati** — ciò che il lettore può rifare a
  mano — senza pretendere che l'archivio ne contenga di più (l'elenco FotMob può coprirne una
  parte: la riga promette i casi del bilancio, non i casi del database). 438 bilanci corti
  verificati a ogni build.
- **Prova che morde:** `tests/test_site.py` estrae l'etichetta dalla pagina finita e la
  confronta con la somma dei tre numeri; senza il fix la regex non trova nulla e il test
  fallisce.

## §5 — Misure dopo e gate

- «ultimi 1» → **0**; «Bilancio (N)» → **490** schede (prima 52); frasi di soglia → **13**;
  sotto-serie pubblicate invariate (**39**, numeri identici).
- `pytest -q`: **943 passati**. `ruff check src tests scripts`: **All checks passed!**
- `fda build`: **498 / 2.364 / 7.602**.
- `scripts/verify_site.py`: **241.619 controlli · 0 problemi** (erano 240.691: +928 — i 438
  bilanci corti ora letti dall'invariante, più 52 + 438 controlli nuovi).
- `scripts/parita_schede.py`: nessuna differenza (58 schede; «Precedenti» 282–1.028 caratteri).
- `scripts/resa_375.py`: **28.722 misure · 0 problemi**.
- `[5]` stampa ora: «490 archivi precedenti, 52 sotto-serie per campo ricalcolate, 438 bilanci
  corti».

## §6 — Cosa resta

Della coda di `docs/101` §4 restano la **sezione 2** — «Previsione del modello ensemble» e le
sue sotto-card (`#previsione`, `#scomposizione`, `#laboratorio`, `#fascia-storica`,
`#posizione-lega`, `#primo-gol`; invarianti [8] [10] [11] [12] [15] [16] [17] [46] [47]) — e la
**sezione 3** — «Verifica approfondita» (`#probabilita` + `#gol-totali`; invarianti [8] [9]) —
con la stessa regola: misura prima, modifica solo se il dato la giustifica, test + invariante
per ogni modifica.
