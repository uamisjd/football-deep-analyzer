# 46 — *Accuratezza* e *Proiezioni* più leggibili: la colonna mancante, il grafico dei mercati, il marcatore delle squadre fragili (2026-09-19)

Richiesta dell'utente prima del merge: *«rendiamo tutto accurato, ordinato, preciso e di valore,
a livello quantitativo, qualitativo, grafico e visivo»*. Questo documento registra i cinque
interventi che ne seguono, tutti misurati e tutti con la loro prova al contrario.

Nessuno tocca il modello, i dati o le previsioni: cambiano **come il sito presenta numeri che
già pubblicava** — più un controllo nuovo che impedisce alle due forme di contraddirsi.

---

## 1. Quantitativo — *Accuratezza*: quante di quelle gare sono del modello di oggi

Il Riepilogo diceva «Bundesliga: 16 partite valutate, RPS 0,2370» senza dire che la maggior
parte di quelle 16 gare è stata prevista da **ricette precedenti**, tenute in archivio per
tracciabilità. La composizione lo dichiarava in fondo alla pagina (39 su 120 col modello
corrente), ma chi guarda la riga della propria lega non lo vedeva. Ora c'è la colonna
**«di cui col modello corrente»**:

| Lega | Partite valutate | …col modello corrente | RPS |
|---|---|---|---|
| Bundesliga | 16 | **5** | 0,2370 |
| Eredivisie | 14 | **3** | 0,1715 |
| LaLiga | 27 | **12** | 0,1916 |
| Liga Portugal | 13 | **5** | 0,1903 |
| Ligue 1 | 14 | **2** | 0,2014 |
| Premier League | 17 | **6** | 0,2187 |
| Serie A | 19 | **6** | 0,2041 |
| **Tutti** | **120** | **39** | 0,2021 |

È il dato che mancava per leggere la tabella con onestà: l'RPS della Bundesliga (0,2370) poggia
su **5** gare della ricetta di oggi, e la pagina stessa dice che ne servono ~30 per una lettura
stabile. La nota sotto la tabella lo spiega.

**Nuova invariante in `verify_site` [3b]:** la somma per lega della colonna deve eguagliare la
riga «Tutti» **e** il numero dichiarato nella composizione del campione. Se una delle tre fonti
dice una cosa diversa dalle altre, il run fallisce.
**Prova al contrario:** portando la riga «Tutti» da 39 a 38, il verificatore segnala **2**
problemi («riga Tutti 38 ≠ somma leghe 39» e «composizione 39 ≠ riga Tutti 38»).

## 2. Grafico — *Accuratezza*: previsto vs osservato sui 9 mercati

La tabella «Accuratezza per mercato» (9 righe, 10 colonne di decimali) è il cuore della pagina,
ma il confronto che conta — *la probabilità dichiarata sta dentro l'intervallo della frequenza
vista?* — si leggeva solo cercando nella riga la parola «compatibile». Ora è disegnato:

- **punto** = probabilità media dichiarata;
- **linea orizzontale** = intervallo di Wilson al 95% della frequenza osservata;
- **trattino verticale** = frequenza osservata;
- **verde** = dentro l'intervallo, **rosso** = fuori.

È un **SVG inline** (7 kB), con la geometria calcolata in `build.grafico_mercati` e il disegno
nel template: stessa regola del radar dei giocatori, nessuna libreria, nessun file esterno, e i
colori vengono dai token del tema (`var(--win)`, `var(--lose)`, `var(--mut)`) quindi funziona
anche in tema chiaro. Ha `role="img"` con una `aria-label` che riassume il contenuto (compreso
«nessun mercato è fuori intervallo» / «N mercati sono fuori intervallo») e una didascalia; la
tabella sopra resta la fonte dei numeri esatti.

Controllo di coerenza fatto a mano: per «Over 1,5 gol» il grafico disegna l'intervallo fra
x=305,5 e x=330,4 (74,7%–88,3%), il punto a 313,1 (78,9%) e il trattino a 319,8 (82,5%):
**gli stessi numeri della tabella**, nessuna seconda fonte da far divergere.

## 3. Visivo — *Accuratezza*: la barra della copertura

Sotto la riga «Copertura: 120 gare valutate su 331 finite» c'è ora una barra che mostra la
proporzione (**36,3%**). È decorativa (`aria-hidden="true"`: i numeri sono già nel testo) e dà
nell'occhio la cosa che il testo da solo non trasmette: il campione valutato è **un terzo** di
quelle giocate.

## 4. Qualitativo — *Proiezioni*: il ◇ accanto alle squadre con poco storico

`docs/45` aveva aggiunto la nota «Poche gare di storico» sotto ogni tabella, ma la nota si legge
*dopo* la tabella: chi guarda la riga dello Schalke 04 non sa che poggia su 3 gare. Ora il nome
della squadra porta un **◇** (con `title` esplicativo), lo stesso simbolo già usato nelle schede
giocatore per i valori non allineati: **14 squadre su 132** lo hanno, nessuna in Serie A.

## 5. Qualitativo — *Prossime*: ogni mese dice che è la stima di oggi

Il calendario compatto pubblica 1X2 e gol attesi per partite fino a **253 giorni** da oggi
(media 133). La pagina lo dichiarava in cima alla sezione, ma aprendo «Maggio 2027» — 285 righe
con «61 · 23 · 16» — quella frase è lontana. Ora ogni intestazione di mese la ripete in piccolo:
«**stima di oggi · ricalcolata a ogni aggiornamento**». Sotto i 520 px la nota è nascosta per non
stringere il titolo (decisione misurata con `resa_375`).

## 6. Cosa è caduto strada facendo (e la lezione)

Aggiungere una colonna e una riga di testo ha fatto fallire **due controlli** di `verify_site`
che leggevano l'HTML **per posizione**:

1. `[3]` cercava `Tutti</td><td…>N</td><td…>RPS</td>`: con la colonna nuova in mezzo, la riga
   «Tutti» non si trovava più;
2. `CAL_MONTH` chiudeva con `</span></summary>`: la nota del mese in mezzo ha azzerato i mesi
   letti («navigazione mesi […] != sezioni []»).

È esattamente il lavoro che i verificatori devono fare, e il modo di risolverlo non è aggirarli
ma **renderli più robusti**: il controllo `[3b]` ora legge la tabella con **gruppi nominati**
(`(?P<n>`, `(?P<rps>`…) invece che per posizione, e i due parser accettano gli elementi nuovi
come parti opzionali e dichiarate.

## 7. Gate

`pytest -q` **487 passed** (484 + 3 nuovi: colonna del modello corrente, grafico dei mercati,
marcatore ◇), `ruff check .` pulito, `fda build` exit 0 (375 schede · 2.364 partite · 7.498
giocatori), `verify_site` **0 problemi · 154.728 controlli** (+1: l'invariante di §1),
`parita_schede` nessuna differenza, `resa_375` **23.674 misure · 0 problemi a 375 px**.

Pesi: `accuratezza.html` 37 → **45 kB** (il grafico è 7 kB), `stagione.html` 45 → **48 kB**,
`prossime.html` **1.257 kB** (tetto dichiarato 1.800 kB, 70%).

## 8. Prossimo passo

Restano i due candidati già registrati: conservare lo storico delle previsioni (`docs/44` §7) e
trattare nel laboratorio le squadre con poche gare (`docs/45` §7). Con questo giro il sito è,
per quanto misurato, **privo di affermazioni non sostenute dai dati**: è il momento del merge.
