# 34 — P2.4 applicata: «Contesto» diviso in due card (19/09/2026)

> Secondo intervento della coda **P2** di `docs/28` §3, dopo la P2.1 (`docs/33`). Sessione
> `arena/01a0b61a`, branch `arena/01a0b61a-football-analyzer`, base `700fd84`.

---

## 1. Il difetto, misurato

La card «Contesto» teneva insieme tre cose che non hanno nulla in comune: **chi dirige la gara**,
**che tempo farà** e **la storia della sfida** (bilancio, grafico a ciambella, ultimi incontri,
frequenze). Misura sulle schede pre-partita (testo visibile, mediana): righe arbitro + meteo **161
caratteri** su un blocco di 966, precedenti **805** — l'**83%** del blocco sotto un titolo che non
nominava nessuna delle due. In più la parola «Contesto» compariva **due volte** nella pagina (la voce dell'indice e
il titolo della card), e l'etichetta della riga ripeteva il titolo della sezione.

## 2. Che cosa è cambiato

1. **Due card, due titoli veri**: `#arbitro-meteo` «Arbitro e meteo» (le due righe: designazione
   con i suoi numeri, previsione meteo) e `#precedenti` «Precedenti» (bilancio, grafico, ultimi
   incontri, frequenze). La guardia di ciascuna card è la stessa della sua voce d'indice: la card
   dell'arbitro c'è quando c'è un arbitro o un meteo (o quando la gara non è ancora giocata e la
   pagina stampa il segnaposto «da definire»), quella dei precedenti quando c'è almeno un
   precedente in archivio, nella riga di riepilogo o nella lista.
2. **L'indice passa da 11 a 12 voci** in una scheda pre-partita: «Contesto» diventa «Arbitro e
   meteo» (id `#arbitro-meteo`) e «Precedenti» (id `#precedenti`). Chi cerca la designazione non
   sfoglia la storia della sfida, e viceversa.
3. **L'etichetta della riga non ripete più il titolo**: «Precedenti (15)» diventa
   **«Bilancio (15)»** — il numero dei casi è il dato da cui dipende la lettura delle frequenze
   («con 15 casi le frequenze indicano una tendenza, non una regola»), e adesso è accanto alla
   riga che lo usa invece che nel titolo. Il collegamento con l'invariante **[5]** di
   `scripts/verify_site.py` (che ricalcola il numero dei precedenti dall'archivio) è aggiornato:
   legge il conteggio da «Bilancio (N)».
4. **Il link «→ precedenti»** dei «Fatti rilevanti» punta dritto a `#precedenti`, che adesso è una
   card con quel nome (prima atterrava in cima al blocco, 171 caratteri sopra i precedenti).

## 3. Misura prima/dopo

Due build dello stesso codice su dati identici: `700fd84` (prima) e il codice attuale (dopo),
confronto appaiato sulle schede pre-partita presenti in entrambe (**60**: sei sono diventate
«giocate» fra le due build).

| grandezza (schede pre-partita) | prima | dopo |
|---|---|---|
| card che contengono il blocco | 1 | **2** (una per titolo) |
| testo visibile del blocco (mediana) | 966 | 981 (**Δ +15**: il titolo in più) |
| di cui righe arbitro + meteo | 161 (16%) | card a sé |
| occorrenze di «Contesto» nella pagina (mediana · max) | 2 · 2 | **0 · 0** |
| voci dell'indice (mediana) | 11 | **12** |
| etichette di riga che ripetevano il titolo della card | 58 | **0** |
| etichette con il numero dei casi | 0 | **58** («Bilancio (N)») |
| distanza dalla voce d'indice ai precedenti (car. visibili sopra) | 171 | **0** |

Il costo è dichiarato e misurabile: **+15 caratteri visibili** (il secondo titolo). Il guadagno non
è la lunghezza — è che ogni blocco si chiama per nome e si raggiunge da solo.

## 4. Gate

`pytest -q` **442 passed** (+1: `test_arbitro_meteo_e_precedenti_card_separate`, che semina due
precedenti in più per far esistere il bilancio completo e verifica: nessun `id="contesto"` residuo,
le due card nell'ordine giusto, il grafico dentro «Precedenti», l'etichetta `Bilancio (N)` con
N ricavato dalla stessa tabella dei dati, il link `→ precedenti`) · `ruff` pulito ·
`fda build` exit 0 (369 partite / 2.364 fixtures / 7.480 giocatori) ·
`scripts/verify_site.py` **exit 0 — 0 problemi · 99.960 controlli** (le voci d'indice verificate
dall'invariante **[33]** salgono a 3.290: 12 voci per scheda pre-partita) ·
`scripts/audit_match_sections.py` exit 0 (58 archivi precedenti verificati).

**Non verificato:** la resa a schermo della barra a 12 voci e delle due card affiancate (spaziature,
a capo su mobile) → resta P2.8 di `docs/19`.

Nota sui conteggi: il sito ha ora **369** schede partita (erano 375): sei gare sono diventate
«giocate» fra le due build. I controlli totali scendono per questo, non per un allentamento
(99.960 su 369 pagine contro 100.987 su 375).

## 5. Anteprima

`site_preview/` ha ora **otto pannelli** prima/dopo: P1.1, hero e «Come arrivano» (P1.2), verifica
dei numeri (P1.4), indice (P1.3), stima stabilizzata (P2.1), la prova che con notizie vere la card
non è cambiata, e il nuovo pannello 7 con la card «Contesto» intera a sinistra e le due card a
destra, con le due versioni della coda dell'indice.

## 6. Prossimo passo

`docs/28` §3, in ordine di peso: **P2.2** (le assenze raccontate in quattro modi diversi: infermeria,
analisi, badge «giocherà?», riga di sintesi), poi P2.3 (micro-visivi), P2.5 (badge forma nell'hero),
P2.6 (quote assenti = decisione).
