# 60 — «Come arrivano»: la sintesi che mancava (2026-10-08)

Direttiva dell'utente: **«adesso fai una revisione alla card "Come arrivano", migliorala o integra
cose migliori»**.

La card mostra, gara per gara, quanto una squadra crea (xG) e quanto concede (xGA), «al netto del
risultato». Il metodo è il solito (`docs/00` B.8): prima si legge la card come la vede il lettore e
si misura, poi si corregge. Nessuna richiesta alle fonti esterne.

---

## 0. In breve

| # | Cosa è cambiato | Prima | Dopo |
|---|---|---|---|
| 1 | **La tendenza scatta da 5 gare, non 6** | servivano 6 gare: la sintesi unica della card restava fuori da **38 schede su 66** | da 5 gare (ultime 3 contro le 2 precedenti): **57 schede su 66**, campione dichiarato in pagina |
| 2 | **La tendenza legge entrambi i lati** | solo gli xG **creati**: una squadra in crisi solo in difesa non aveva alcuna sintesi | xG **creati** e **concessi**, ognuno col suo verdetto e i due valori |
| 3 | **La sede che conta è evidenziata** | «xG in casa 0,86 · xG in trasferta 0,63» per entrambe: il lettore doveva capire da sé quale numero vale per questa gara | la riga rilevante è marcata «**(questa gara)**»: per la casa il suo xG casalingo, per l'ospite il suo xG esterno |

Gate (rifatti sulla build nuova):

| Gate | Esito |
|---|---|
| `pytest -q` | **540 passed** |
| `ruff check .` | pulito |
| `fda build` | **441 / 2.364 / 7.494** |
| `verify_site` | **0 problemi · 167.701 controlli** ([43] su 132 lati, 698 righe) |
| `parita_schede` | nessuna differenza · min 21.355 · mediana 23.230 (min = 92%) |
| `resa_375` | **26.419 misure · 0 problemi** |
| `prematch_sections` | «Come arrivano» **7,0%** del visibile · 66/66 schede |

---

## 1. Cosa non ho toccato, e perché

**La lettura xPTS non torna qui.** Il candidato più ovvio — una riga «punti raccolti contro xPTS» —
è già in **due** card: «Le due squadre» («xPTS vs punti reali», soglia ±2, «sopra/sotto atteso») e
«Clima del club» (segnale «scarto punti‑xPTS da ±2»). Una terza copia sarebbe esattamente la
ridondanza che `docs/30` («un dato in un posto solo») e la nota P1.2 dentro questa card vietano.
Verificato prima di decidere: la riga di sintesi con gli xPTS era stata tolta da P1.2 proprio per
questo, e i numeri di stagione stanno nella card della squadra. Non è stata rimessa.

**I dati sono giusti.** Rileggendo la card come la vede il lettore è saltato all'occhio che
l'Atalanta aveva vinto 2‑1 col Sassuolo con xG 0,92 contro 2,70, e 1‑0 col Bologna con xG 0,18
contro 1,24: due vittorie da «nettamente dominata». Verificato sui dati grezzi
(`understat_team_matches`): i valori sono quelli, xG e xGA non sono invertiti. Non è un difetto, è
il punto della card — «al netto del risultato» mostra proprio che quei risultati erano sopra la
prestazione. Nessuna correzione necessaria.

---

## 2. La sintesi che mancava

La card dice di sé (nota P1.2): «resta la serie gara per gara **con la tendenza**, che è l'unica
cosa che questa card può dire bene». Ma la tendenza:

* **compariva solo in 28 schede su 66.** Servivano 6 gare (`len(rows) >= 6`); a ottobre le squadre
  hanno 4‑6 gare, quindi 38 schede (9 con 4 gare, 29 con 5) restavano senza alcuna sintesi — solo la
  tabella. Misurato dalle pagine generate prima della modifica.
* **leggeva solo gli xG creati.** Una squadra può arrivare in crisi **difensiva** (concede molto più
  di prima) creando come sempre: la tendenza non lo diceva.

Ora la tendenza scatta da **5 gare** (ultime 3 contro le 2 precedenti — con 4 non si divide in modo
sensato, e quelle 9 schede restano senza, onestamente) e legge **entrambi** i lati. Copertura:
**57 schede su 66**. Il campione è dichiarato in pagina («ultime 3 contro le **2** precedenti»), così
il lettore sa che su 5 gare la direzione è più fragile che su 6 — coerente con l'avviso già in card
(«con poche giornate giocate i valori per gara oscillano molto»).

Esempio generato (`partite/5749690.html`, Atalanta):

```
Gioco recente — xG creati in crescita (0,55 → 0,91 a gara, ultime 3 contro le 2 precedenti),
xG concessi in crescita (1,97 → 2,26); soglia ±0,15 xG. Valuta il gioco, non i punti: le medie
di stagione sono nella card della squadra.
```

La freccia va dal valore **precedente** al **recente**, così la direzione si legge nel verso giusto.
La soglia ±0,15 xG è quella di prima, stampata in pagina e rifatta dall'invariante.

---

## 3. La sede che conta

La riga dello split dava «xG in casa X · xG in trasferta Y» per **entrambe** le squadre, ma in questa
gara la casa gioca in casa e l'ospite in trasferta: i numeri da confrontare sono il casalingo della
casa e l'esterno dell'ospite. Ora la card marca la riga rilevante con «**(questa gara)**», così il
confronto giusto (es. Atalanta 0,86 in casa contro Venezia 1,48 in trasferta) è immediato invece di
richiedere al lettore di ricordare chi gioca dove.

---

## 4. Prove

**Invariante [43] aggiornata** (`scripts/verify_site.py`): la regex della tendenza riconosce il testo
nuovo (creato **e** concesso, freccia, campione), il controllo scatta da 5 righe invece di 6, rifà le
medie sul campione vero (`/(n−3)`, non `/3`) e verifica **anche** il lato concesso. Senza
l'aggiornamento [43] bocciava 114 lati (la regex cercava ancora «(soglia … xG)» con le parentesi del
vecchio formato).

**Test nuovo** (`tests/test_oggi_depth.py`): `test_arrival_trend_da_cinque_gare_su_entrambi_i_lati`
— con 5 gare la tendenza esce, `trend_n_before` vale 2, il lato creato è «in calo» (2,40 → 0,80) e il
concesso «in crescita» (0,50 → 2,00). I test esistenti (`n=4` → nessuna tendenza, `n=6` → «in calo»)
restano verdi.

---

## 5. Aperto

**«forza avv.» è la classifica attuale, non quella alla data della gara.** La colonna accanto a ogni
gara passata mostra posizione e punti **odierni** dell'avversario; il tooltip lo dichiara
(«Posizione e punti in classifica attuale, non alla data della gara»), ma resta un anacronismo: per
una gara di agosto la forza dell'avversario a ottobre non è quella di allora. Correggerlo serve una
classifica storica per giornata, che il sito non raccoglie (gli snapshot partono da questa stagione).
Dichiarato, non risolto: è il candidato del prossimo giro su questa card.

---

## 6. Come riprodurre

```bash
.venv/bin/fda build                                                          # 441 / 2.364 / 7.494 (~5 min)
.venv/bin/python scripts/verify_site.py --site site --data data/processed    # 0 problemi · 167.701 ([43] 132 lati)
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site                           # Come arrivano 7,0%
.venv/bin/python -m scripts.resa_375                                         # 26.419 · 0
.venv/bin/pytest -q && .venv/bin/ruff check .                                # 540 passed · pulito
```

La copertura della tendenza (57/66) e l'assenza della vecchia dicitura («Direzione degli») sono
lette dalle pagine generate. **Cosa non è verificato da qui**: le fonti esterne non sono raggiungibili
dal sandbox; la resa **visiva** non è stata vista in un browser (`resa_375` misura geometria, non
estetica).
