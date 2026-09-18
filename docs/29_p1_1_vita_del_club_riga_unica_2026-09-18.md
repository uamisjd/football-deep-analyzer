# 29 — P1.1 applicata: «Vita del club» in una riga quando non c'è nulla (18/09/2026)

> Direttiva dell'utente: *«procedi»* — primo intervento della coda misurata in `docs/28` §4,
> nell'ordine proposto: **P1.1** (empty-state della card «Vita del club» + note metodologiche
> richiudibili). Un intervento solo, con la misura prima/dopo: è la regola del progetto
> («prima si dimostra, poi si integra»).

**Sessione** `arena/01a0b61a` · **branch** `arena/01a0b61a-football-deep-analyzer`.

---

## 1. Il difetto, misurato (`docs/28` §2 P1.1)

Su **42 schede su 66** della scheda pre-partita nessuna delle due squadre aveva un titolo
pubblicabile, e la card «Vita del club» restava comunque il blocco **più pesante della pagina**:
**3.030 caratteri visibili** di cui il **99% prosa metodologica**, contro i **3,6%** di testo
occupato da «Previsione del modello» + «Risultati esatti» messi insieme. La card più grande della
pagina serviva a dire che non c'era niente da dire.

## 2. Che cosa è cambiato

1. **`news_quiet_line()`** (nuovo, `src/fda/site/analysis.py`): funzione pura che, **solo quando
   entrambe** le squadre non hanno né titoli pubblicati né «in riserva», costruisce la riga unica —
   il fatto con i suoi numeri: *«Nessun titolo pubblicabile su Milan e Lecce negli ultimi 7 giorni:
   45 titoli esaminati e scartati con criterio — 23 servizio o cronaca · 9 annunci o logistica ·
   13 non spostano nulla.»* I motivi a zero non si nominano, i titoli oltre la finestra sì
   (`· 2 troppo vecchi`, la stessa parola già usata dall'imbuto). Nel caso «niente raccolto»
   scrive l'altro fatto vero: *«Nessun titolo in lingua italiana raccolto … (3 titoli più vecchi
   oltre la finestra: guardati e lasciati fuori)»*. Se una squadra ha qualcosa da pubblicare
   ritorna `None` e la card resta **identica a prima**, colonna per colonna.
2. **`match.html`**: quando la riga esiste, la card mostra **la riga** (più gli eventuali «Da
   sapere», che sono dati nostri) e mette in un `<details>` — *«Che cosa è stato esaminato, e con
   quali criteri»* — il testo introduttivo, l'imbuto squadra per squadra e la nota sulle fonti.
   I tre frammenti sono definiti **una volta** come blocchi `{% set %}` e resi nel ramo che vale,
   così il markup che `verify_site [20]` legge resta lo stesso.
3. **`site.css`**: `.news-more` (stessa forma della tendina dei mesi nel calendario: ▸/▾, solo
   token di tema).

**Nessun numero esce dalla pagina.** Cambia dove sta: nel primo schermo il risultato, sotto il
lavoro fatto per arrivarci. È la stessa scelta di «Verifica approfondita» (`#verifica`), che però
è aperta di default — P1.4 della coda.

## 3. Misura prima/dopo

Le due build sono state fatte **dallo stesso codice e dagli stessi dati**, l'una con il template
precedente (stash dei tre file, build in `site_old/`), l'altra con l'intervento. Il censimento
`scripts/prematch_sections.py` è stato esteso proprio per questa misura: conta il testo **visibile
senza aprire le tendine** (dentro un `<details>` chiuso resta solo il `summary`), perché un
censimento del DOM non avrebbe visto il guadagno.

| grandezza (scheda pre-partita, mediana) | prima | dopo |
|---|---|---|
| card «Vita del club» — testo **visibile** sulle 42 schede in riga unica | **3.030** car. | **829** car. (**−73%**) |
| card «Vita del club» — testo nel **DOM** sulle stesse 42 schede | 3.030 car. | 3.354 car. (+324: la riga aggiunta, nulla tolto) |
| card «Vita del club» — visibile su tutte le 66 schede | 3.060 car. | 1.046 car. |
| quota della card sul testo visibile della pagina | 13,6% | **5,0%** (10,8% dietro la tendina) |
| testo visibile dell'intera scheda | 22.520 car. | **20.723 car.** (−1.797, −8,0%) |
| schede che perdono ≥2.000 car. dal primo schermo | — | **42 su 66** (le altre 24: nessun cambiamento) |

**Gate (offline, sandbox).** `pytest` **437 passed** (+4: 3 unit test su `news_quiet_line`, 1 test
end-to-end sulla pagina renderizzata) · `ruff` pulito sui file toccati · `fda build` exit 0
(375 partite / 2.364 fixtures / 7.480 giocatori) · `scripts/verify_site.py` **exit 0 — 0 problemi ·
97.903 controlli**, con la riga `[20] card «Vita del club» riconciliate: 66 pagine` (l'imbuto
riconciliato è ora dentro la tendina: il controllo continua a leggerlo perché legge l'HTML, non il
visibile) · `audit_match_sections.py` exit 0.

**Non verificato (serve un browser reale):** l'effetto percepito della tendina a 375 px e il
contrasto del `summary` in tema chiaro. Il colore usa i token di tema già verificati da
`tests/test_tema_contrasto.py`; la resa visiva resta il punto aperto P2.8 di `docs/19`.

## 4. Che cosa NON è stato fatto (e perché)

- **P1.2-P1.4 e P2.x** (`docs/28` §4): sono il seguito della coda, un intervento per giro.
- **La nota metodologica resta visibile nelle 24 schede con notizie pubblicate**: lì la card ha
  contenuto vero e il metodo sta sopra righe che lo usano. Se la misura dirà che pesa ancora, è il
  passo successivo (un unico blocco richiudibile valido per tutte le card).
- **`verify_site [20]` non è stato modificato**, e questa è la prova che il controllo era scritto
  bene: verifica i numeri pubblicati, non la loro posizione nella pagina.

## 5. Prossimo passo

P1.2 (`docs/28` §4): togliere xG/PPDA dall'hero e lasciare un solo posto per tipo di dato — con la
misura «stesso dato in più card» che `scripts/prematch_sections.py` già stampa (oggi: **mediana 3
card**, distribuzione 3→6).
