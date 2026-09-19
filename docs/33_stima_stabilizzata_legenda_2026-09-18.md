# 33 — P2.1 applicata: la stima stabilizzata si spiega una volta sola (18/09/2026)

> Primo intervento della coda **P2** di `docs/28` §3, dopo i quattro P1 (`docs/29`, `docs/30`,
> `docs/31`, `docs/32`). Sessione `arena/01a0b61a` · branch
> `arena/01a0b61a-football-deep-analyzer`.

---

## 1. Il difetto, misurato (`docs/28` §3 P2.1)

La stessa spiegazione — *«◎ stima stabilizzata della rata per 90 (media dei pari per lega e ruolo e
peso misurati dai dati del run, non costanti) per campioni sotto 270′: con pochi minuti il valore
grezzo è rumore. ◇ = sotto i 90′ la rata grezza non si pubblica, si pubblica la stima.»* —
compariva **una volta per ogni card squadra** (la nota «Soglia di minutaggio: …», due schede
pre-partita su due) e di nuovo nell'infermeria («… xG+xA a partita in meno (stima stabilizzata)»).
Misura sulle 66 schede pre-partita: **4 occorrenze visibili per scheda, identiche in tutte**.

## 2. Che cosa è cambiato

1. **La legenda si dà una volta sola**, nel primo punto d'uso: la testata di «I giocatori che
   decidono», dove il ◎ compare la prima volta. Definisce entrambi i marcatori:
   *«Due marcatori in questa sezione. ◎ è la **stima stabilizzata** della rata per 90: … ◇ significa
   che sotto i 90′ la rata grezza non si pubblica e si pubblica la stima.»*
2. **Nelle card squadra resta solo il dato**: «Soglia di minutaggio: N minuti · M giocatori in
   classifica.» (i numeri cambiano per squadra; la spiegazione no, e sta sopra).
3. **Il tooltip di ogni valore stabilizzato porta il caso specifico**, non la teoria:
   `◎ Stima stabilizzata — media dei pari (…) 0,21/90 · peso k=57′ · n=46`. È la parte che rende la
   stima verificabile, ed è quella che deve restare attaccata al numero.
4. **Nell'infermeria** il totale perde la parentesi «(stima stabilizzata)» e prende il marcatore:
   «· ◎ 0,83 xG+xA a partita in meno», col tooltip che rimanda alla legenda.

**Il gate ha corretto la mia prima stesura.** La legenda iniziale scriveva i marcatori in grassetto
da soli (`<b>◇</b> = …`) e l'invariante **[32]** è scattata su 66 pagine: *«cella ◇/◎ senza numero
pubblicato»* — la stessa regola che protegge dal difetto vero (`◇` reso senza numero perché un campo
non è stato emesso). Qui era un falso positivo, ma la regola ha ragione: un marcatore subito seguito
dal tag di chiusura è indistinguibile da un valore mancante. La legenda è stata riscritta **in
prosa** (◎ e ◇ dentro la frase, non isolati), che è anche la forma più leggibile.

## 3. Misura prima/dopo

Due build dello stesso codice (la versione precedente del template in `/tmp/out_prima_p21`, questa
in `site/`), stessi dati, sulle stesse 66 schede pre-partita.

| grandezza (66 schede pre) | prima | dopo |
|---|---|---|
| occorrenze visibili di «stabilizzat» per scheda (mediana · max) | **4 · 4** | **1 · 1** |
| occorrenze di «stima stabilizzata» per scheda | 4 · 4 | **1 · 1** |
| spiegazione del metodo (media dei pari, peso k, soglia 270′) resa **in prosa** | 4 volte | **1 volta** |
| testo visibile per scheda — calo mediano appaiato | — | **−111 caratteri** (73–111; 66/66) |
| testo visibile mediano per scheda | 19.839 | **19.752** |
| controlli del gate | 100.890 | **100.987** |

Il guadagno in caratteri è piccolo e va detto: **il vantaggio non è la lunghezza, è che la stessa
frase non si legge quattro volte.** Le spiegazioni restano tutte raggiungibili (legenda una volta,
tooltip per valore, con i numeri del caso).

## 4. Gate

`pytest -q` **441 passed** (+1: `test_legenda_stabilizzata_una_volta_sola`, che costruisce una gara
pre-partita con statistiche giocatore — senza, la sezione e la legenda non si stampano — e verifica
legenda unica, nota di squadra senza ripetizioni, tooltip col caso specifico) · `ruff` pulito ·
`fda build` exit 0 (375 partite / 2.364 fixtures / 7.480 giocatori) ·
`scripts/verify_site.py` **exit 0 — 0 problemi · 100.987 controlli** ·
`scripts/audit_match_sections.py` exit 0. `[32]` verifica 336 celle ◇/◎ sulle schede partita (468
prima: i marcatori isolati della prima stesura della legenda adesso sono testo).

**Non verificato:** la resa visiva (peso del grassetto nella legenda, tooltip su mobile) → resta
P2.8 di `docs/19`.

## 5. Anteprima

L'anteprima locale (`site_preview/`, fuori dal versionamento) ha ora **sette pannelli** prima/dopo:
P1.1, hero e «Come arrivano» (P1.2), verifica dei numeri (P1.4), indice della scheda (P1.3), stima
stabilizzata (P2.1) e la prova che dove ci sono notizie vere la card non è cambiata.

## 6. Prossimo passo

`docs/28` §3, in ordine di peso: **P2.4** (separare «Contesto»: arbitro, meteo e precedenti sono una
card sola, e la parola «Contesto» compare due volte nella pagina), **P2.2** (le assenze raccontate in
quattro modi), **P2.3** (micro-visivi), **P2.5** (badge forma nell'hero), **P2.6** (quote assenti =
decisione).
