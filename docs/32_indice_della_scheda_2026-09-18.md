# 32 — P1.3 applicata: l'indice della scheda dice i titoli veri (18/09/2026)

> Quarto e ultimo intervento P1 della coda misurata in `docs/28` §4, dopo **P1.1** (`docs/29`),
> **P1.2** (`docs/30`) e **P1.4** (`docs/31`). Sessione `arena/01a0b61a` · branch
> `arena/01a0b61a-football-deep-analyzer`.

---

## 1. Il difetto, misurato (`docs/28` §2 P1.3)

La barra sticky in cima alla scheda (`match-jump`) aveva **quattro voci per diciotto blocchi
titolati**, e tre su quattro non corrispondevano alla sezione che aprivano:

| voce (prima) | atterrava su | |
|---|---|---|
| «Sintesi» | «Lettura della partita» / «Analisi pre-partita» | etichetta inventata |
| «Previsione» | «Previsione del modello» | corretta |
| «Dati e contesto» | «Confronto di stagione» | **tutt'altra sezione** |
| «Squadre» / «Post-partita» | il nome di una squadra / «Il prossimo impegno» | a metà pagina |

Misurato sulle 66 schede pre-partita: **66 voci corrette su 264** (una per pagina), e le **sei card
più pesanti** — Vita del club, Mercato, Verifica, Panchina, Scontro tattico, I giocatori — erano
**0 su 6 raggiungibili** dalla barra. Le card senza `id` non potevano nemmeno essere linkate:
«Fatti rilevanti», «Come arrivano», «I giocatori che decidono», «Contesto», «Statistiche»,
«Cronaca essenziale».

## 2. Che cosa è cambiato

1. **L'indice ha le voci che la pagina ha davvero**, in ordine di pagina e con le sue stesse
   guardie: le voci compaiono solo quando la sezione esiste (una scheda senza mercato non promette
   «Mercato»). Pre-partita: 11 voci — Analisi · Previsione · Scontro tattico · Come arrivano ·
   I giocatori · Le due squadre · Panchina · Mercato · Vita del club · Contesto · Verifica.
   Post-partita: 7 — Lettura · Scontro tattico · Le due squadre · Panchina · Contesto ·
   Statistiche · Cronaca essenziale · Verifica.
2. **Le etichette sono l'inizio del titolo** della sezione di destinazione («Panchina» →
   «Panchina e posta in gioco», «Verifica» → «Verifica approfondita: …»), così la barra non promette
   niente che non trovi.
3. **Ancore aggiunte** alle card che non ne avevano (`#arrivi`, `#giocatori`, `#fatti`,
   `#statistiche`, `#cronaca`) e **titolo al gruppo delle due squadre** (`<h2>Le due squadre</h2>`,
   a tutta larghezza dentro la griglia): la voce «Le due squadre» atterrava sul nome di una squadra
   perché quel gruppo non aveva un titolo.
4. **Il gruppo delle card del club** smette di chiamarsi `#contesto` (non era il suo nome) e prende
   `#club`; l'id `#contesto` va alla card che si chiama così — quindi il link «→ precedenti» della
   narrativa ora atterra **sui precedenti** invece che in cima al gruppo.
5. **Invariante nuova [33]** in `scripts/verify_site.py`, in **entrambe le direzioni**, su tutte le
   375 schede: ogni voce dell'indice deve puntare a una sezione presente e il suo testo deve essere
   l'inizio del titolo di quella sezione; una sezione pesante presente ma fuori dall'indice fa
   fallire il gate. È la rete che impedisce all'indice di rinvecchiare: se domani una sezione cambia
   nome, la CI lo dice.

## 3. Misura prima/dopo

Due build dello stesso codice (la versione precedente del template in `/tmp/out_prima_p13`, quella
nuova in `site/`), stessi dati, stesse schede.

| grandezza | prima | dopo |
|---|---|---|
| voci dell'indice, schede pre-partita (mediana) | 4 | **11** |
| voci che dicono il titolo della sezione aperta | 66 su 264 (**1/4 per scheda**) | **726 su 726** |
| voci dell'indice, schede post-partita (mediana) | 3 | **7** |
| voci corrette, schede post-partita | 0 su 36 | **84 su 84** |
| card raggiungibili dalla barra (mediana su 20, pre) | 1 | **9** |
| **le 6 card più pesanti** raggiungibili | **0 su 6** | **6 su 6** |
| card raggiungibili dalla barra (post-partita) | 1 | 6 |
| testo visibile in più per scheda (l'indice è testo nuovo) | — | **+97 caratteri** |
| controlli del gate | 97.903 | **100.890** (+2.987 voci verificate) |

Il censimento delle card **non cambia** (20 card-foglia per scheda, stesse sezioni e stesse
ridondanze): il titolo di gruppo aggiunto sta in una griglia che non era una card-foglia, e le
etichette dell'indice non sono card.

## 4. Gate

`pytest -q` **440 passed** (+1: `test_indice_della_scheda_dice_i_titoli_veri`, che ricalcola la
corrispondenza voce → titolo sulle due schede campione e verifica che le sezioni prima
irraggiungibili abbiano voce e ancora) · `ruff` pulito · `fda build` exit 0 (375 partite / 2.364
fixtures / 7.480 giocatori) · `scripts/verify_site.py` **exit 0 — 0 problemi · 100.890 controlli**
(con `[33] voci dell'indice della scheda partita verificate: 2.987`) ·
`scripts/audit_match_sections.py` exit 0.

**Un test esistente è stato adattato, non il prodotto**: `test_site_build_end_to_end` ritagliava la
card «Confronto di stagione» cercando la parola «Contesto» come fine — ora «Contesto» compare anche
nella barra in cima (è una voce dell'indice) e la fetta veniva vuota. Il taglio usa l'ancora
`id="contesto"`, che è il confine vero.

**Non verificato:** la resa della barra con 11 voci (scroll orizzontale su mobile, a capo su
desktop) → resta P2.8 di `docs/19`, come per gli altri tre interventi.

## 5. Anteprima

L'anteprima locale (`site_preview/`, fuori dal versionamento) ha ora **sei pannelli** prima/dopo:
P1.1, hero e «Come arrivano» (P1.2), verifica dei numeri (P1.4), indice della scheda (P1.3) e la
prova che dove ci sono notizie vere la card non è cambiata.

## 6. Prossimo passo

La coda **P1 di `docs/28` §4 è esaurita** (P1.1, P1.2, P1.3, P1.4). Restano i **P2**, in ordine di
peso misurato: P2.1 (legenda unica delle stime stabilizzate), P2.4 (separare «Contesto»: arbitro,
meteo, precedenti sono oggi una card sola con la parola che compare due volte nella pagina), P2.2
(assenze in un posto solo), P2.3 (micro-visivi), P2.5 e P2.6.
