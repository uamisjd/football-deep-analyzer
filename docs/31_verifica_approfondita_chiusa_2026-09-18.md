# 31 — P1.4 applicata: la verifica dei numeri non occupa il primo schermo (18/09/2026)

> Terzo intervento della coda misurata in `docs/28` §4, dopo **P1.1** (`docs/29`) e **P1.2**
> (`docs/30`). Sessione `arena/01a0b61a` · branch `arena/01a0b61a-football-deep-analyzer`.

---

## 1. Il difetto, misurato (`docs/28` §2 P1.4)

«Verifica approfondita: risultati esatti e distribuzione gol» — matrice dei punteggi, distribuzione
dei gol totali, dotplot — è materiale **per chi vuole controllare i numeri**, ma era sempre
espansa: nel template con `open` fisso, e in più `base.html` la riapriva da sola sopra i 760 px
(chiudeva solo da telefono). Sulle 66 schede pre-partita era il **blocco dati più pesante** della
pagina: **1.886 caratteri visibili, il 9,2% del testo** (docs/28, censimento P1.1; il titolo di
`docs/28` dice 8,4% — stessa card, denominatore diverso, la pagina si è accorciata con P1.1 e P1.2).

## 2. Che cosa è cambiato

1. **`match.html`**: via l'`open`; il `summary` porta i **due numeri di testa** — *«moda 2 gol ·
   mediana 2 · per chi vuole controllare i numeri»* — così il lettore sa se aprirla. Il contenuto
   **resta nel DOM**: `verify_site` continua a leggerlo e Google pure.
2. **`base.html`**: lo script che forzava l'apertura sopra i 760 px è stato sostituito da un
   comportamento più utile: **se un link punta a un elemento dentro una tendina chiusa, la tendina
   si apre da sola** (`closest('details:not([open])')`). Serviva: la scheda ha il link «matrice
   completa ↓» (dalla card dei punteggi più probabili) che altrimenti atterrava su una riga chiusa.
3. **`site.css`**: il segno ▸/▾ de «Vita del club» (P1.1) e quello della verifica sono ora **una
   regola sola**, così le due tendine si comportano e si vedono allo stesso modo.

## 3. Misura prima/dopo

Due build dello stesso codice (entrambe post-P1.1 e post-P1.2: cambia solo il template della
verifica e lo script), stessi dati, sulle stesse 66 schede pre-partita.

| grandezza (66 schede pre) | prima | dopo |
|---|---|---|
| card «Verifica approfondita» — testo **visibile** (mediana) | 1.886 car. | **119 car.** |
| card «Verifica approfondita» — testo nel **DOM** (mediana) | 1.886 car. | 1.911 car. (+25: i due numeri nel summary) |
| quota della card sul testo visibile della pagina | 9,2% | **0,6% visibile + 7,9% in tendina** |
| **scheda intera — testo visibile (mediana, appaiata)** | — | **−1.767 car.** (1.758–1.782; 66/66 schede) |
| testo visibile mediano per scheda | 20.577 car. | **18.807 car.** (−8,6%) |
| controllo `verify_site` | 97.903 | 97.903 (**invariato**: il contenuto è nella pagina, solo chiuso) |

Il calo è quasi identico su tutte le schede (1.758–1.782) perché la verifica c'è sempre e ha la
stessa forma: non è una media che nasconde casi diversi.

## 4. Gate

`pytest -q` **439 passed** (+1: `test_verifica_approfondita_chiusa_e_annunciata`, che verifica la
tendina chiusa, i due numeri nel summary, il contenuto nel DOM e lo script che apre la tendina del
bersaglio di un'ancora) · `ruff` pulito · `fda build` exit 0 (375 partite / 2.364 fixtures / 7.480
giocatori) · `scripts/verify_site.py` **exit 0 — 0 problemi · 97.903 controlli** ·
`scripts/audit_match_sections.py` exit 0.

**Non verificato:** resa visiva con un browser reale (segno ▸/▾ del summary, spaziatura della card
chiusa, comportamento dello script all'ancora) — resta P2.8 di `docs/19`, come per P1.1 e P1.2.

## 5. Anteprima

L'anteprima locale (`site_preview/`, fuori dal versionamento) ora ha **cinque pannelli**
prima/dopo: «Vita del club» (P1.1), hero e «Come arrivano» (P1.2), verifica dei numeri (P1.4) e la
prova che dove ci sono notizie vere la card non è cambiata.

## 6. Prossimo passo

Ultimo punto P1 della coda di `docs/28` §4: **P1.3** — la navigazione promette quattro sezioni, la
pagina ne ha ventuno: le ancore dichiarate (`#lettura`, `#previsione`, `#contesto`, `#squadre`/
`#postpartita`) vanno allineate alle sezioni che esistono davvero, o il menu va ridotto a ciò che
c'è. Poi i P2 (legenda unica delle stime, assenze in un posto, micro-visivi, «Contesto» separato).
