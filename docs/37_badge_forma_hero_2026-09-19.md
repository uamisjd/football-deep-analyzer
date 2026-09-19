# 37 — P2.5 applicata: la forma recente sale in testa alla scheda (19/09/2026)

> Quinto intervento della coda **P2** di `docs/28` §3, dopo P2.1 (`docs/33`), P2.4 (`docs/34`),
> P2.2 (`docs/35`) e P2.3 (`docs/36`). Proposta che veniva da `docs/17` §2 (14/09/2026), mai
> applicata. Sessione `arena/01a0b61a`, branch `arena/01a0b61a-football-analyzer`, base `33605e6`.

---

## 1. Il difetto, misurato

La forma recente — quante gare ha vinto/pareggiato/perso una squadra nelle ultime cinque — è un dato
che si guarda per primo, ma nella scheda stava **solo sotto**: nella frase obbligatoria
dell'analisi, nella card della squadra (pallini con avversario e risultato) e nella tabella di «Come
arrivano» (colonna «es.»). In testa, dove sta il nome della squadra e l'esito più probabile, non
c'era niente: per sapere se il favorito arriva bene bisognava scorrere.

Misura sulle 60 schede pre-partita (`33605e6`): **111 serie lettera per lettera** nella sola
narrativa (1,85 per scheda: `Athletic Club: 7 punti nelle ultime 5 (PPVVN) — andamento nella
norma.`), **0** elementi di forma nell'hero, **516** pallini in pagina (8,6 per scheda, tutti nella
card della squadra).

## 2. Che cosa è cambiato

1. **Il badge nell'hero.** Sotto il nome di **entrambe** le squadre: etichetta «Forma», i pallini
   V/N/P (dalla più vecchia alla più recente) e i **punti guadagnati** (`7 pt`), con la finestra
   dichiarata nella descrizione — `Forma di Athletic Club: PPVVN nelle ultime 5 partite, 7 punti.
   V=vittoria, N=pareggio, P=sconfitta` — e il tooltip che ripete i punti di ogni gara (avversario,
   casa/trasferta, risultato). Sono le **stesse classi della pagina «Oggi»** (`.form-line`,
   `.form-dot`, `.fact-*`, la macro `form_pills` di `_matchlist.html`): chi ha visto l'elenco
   riconosce il segno.
2. **La serie non si ripete più nella narrativa.** La frase tiene i numeri e il giudizio — «7 punti
   nelle ultime 5 — andamento nella norma» — e lascia le lettere al badge. È la metà «riduzione»
   dell'intervento: **111 → 0** occorrenze.
3. **La card della squadra resta la sede del dettaglio** (pallini con avversario, casa/trasferta e
   risultato, più la riga dei risultati): il badge non la sostituisce, aggiunge la lettura a colpo
   d'occhio in cima. **Nessuna informazione esce dalla pagina.**
4. **Soglia e guardie.** Il badge compare da **3 gare giocate** in su — la stessa soglia della riga
   obbligatoria della narrativa (`docs/20` §13): due pallini non sono una forma. A **gara finita**
   il badge non c'è (l'hero racconta il risultato, non l'attesa), come già la narrativa.

**Perché non è in conflitto con `docs/20` §13.** Quella regola («la forma è un contenuto
obbligatorio, non un'eccezione: se non è estrema si dice comunque, con i numeri») resta
soddisfatta — i numeri ci sono, nella riga e nel badge — e la parità fra le 7 leghe è ora più forte:
il badge è nel template, quindi c'è su **tutte** le schede pre-partita indipendentemente dalla lega,
prima ancora che la narrativa lo dica. Cambia il formato (non più la serie fra parentesi), non la
sostanza.

## 3. Misura prima/dopo

Due build dello stesso codice sugli stessi dati (`33605e6` → codice attuale), stesse **60 schede
pre-partita**, stessa sonda di lettura dell'HTML pubblicato.

| grandezza | prima | dopo |
|---|---|---|
| serie lettera per lettera nella narrativa | **111** (1,85 per scheda) | **0** |
| badge nell'hero | 0 | **120** (2 per scheda × 60: entrambe le squadre) |
| pallini di forma in pagina (hero + card squadra) | 516 (8,60 per scheda) | 1.032 (17,20 per scheda) |
| testo visibile dell'hero (mediana) | 47 caratteri | **86** (+39) |
| testo visibile della scheda (mediana) | 22.474 | 22.500 (**+26** in mediana, Δ per scheda +22…+28) |

Il costo è di **26 caratteri** a scheda: l'etichetta, i punti e la chiusura della frase (meno le
lettere non più ricopiate). Il guadagno non è la lunghezza — è che la forma si legge **prima** delle
frasi che la commentano, e che la stessa serie non si legge più due volte.

**Parità fra le schede** (direttiva utente del 2026-09-19): `scripts/parita_schede.py` esce 0 —
60/60 schede, stesse 23 sezioni, stesso indice (12 voci), testo visibile minimo **17.604** (91%
della mediana 19.262).

## 4. Come è stato verificato: l'invariante [34]

Nuova invariante in `scripts/verify_site.py`: sulle schede pre-partita, per **ogni** squadra, la
serie e i punti del badge sono **ricalcolati dai Parquet** — gare finite prima del fischio, ultime
cinque, esito dal punto di vista della squadra — e confrontati col markup (etichetta, sequenza,
numerosità, punti stampati, numero di pallini disegnati). La soglia vale nei due versi: da 3 gare in
su il badge **deve** esserci, sotto non deve. Un badge che racconta una forma diversa da quella dei
dati non passa più.

`[34] badge della forma nell'hero verificati: 120` — i controlli totali del gate salgono da 104.918
a **105.038**.

## 5. Gate

`pytest -q` **449 passed** (+2: un'unità sulla soglia del badge in `tests/test_oggi_depth.py` — con
due sole gare giocate il badge è `None` — e un'integrazione in `tests/test_site.py` che confronta il
badge con il calendario su due squadre con serie note, `VVNNP` 8 punti e `NPVVV` 10 punti, e
pretende che a gara finita il badge non ci sia) · `ruff check .` pulito · `fda build` exit 0
(369 partite / 2.364 fixtures / 7.480 giocatori) · `scripts/verify_site.py` **exit 0 — 0 problemi ·
105.038 controlli** · `scripts/parita_schede.py` **exit 0** · `scripts/audit_match_sections.py` exit 0.

**Non verificato:** resa a schermo del badge (allineamento sotto il nome a destra/sinistra,
spaziatura a 375 px dove la colonna è larga ~130 px, contrasto dei pallini nel tema chiaro) → resta
**P2.8** di `docs/19`, come le altre rese visive della sessione.

## 6. Anteprima

`site_preview/` (porta 8000) ha ora **diciannove blocchi** prima/dopo (il «prima» è la build di
`2d3cf27`), con i due nuovi: **14** la riga delle due squadre con e senza badge (più i punti di
ciascuna) e **14b** la lista delle frasi dell'analisi, dove si vede la serie che sparisce. In fondo
il bilancio dei dieci interventi.

## 7. Prossimo passo

`docs/28` §3: **P2.6** (quote dei bookmaker: voce da decidere, non un difetto) e **P2.8** (rese in
browser: badge, micro-visivi, indice a 12 voci, tendina della verifica). Ogni intervento va
rimisurato con `scripts/parita_schede.py` oltre che con `scripts/prematch_sections.py`.
