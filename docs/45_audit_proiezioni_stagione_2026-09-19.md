# 45 — Audit della pagina *Proiezioni di stagione*: un numero grezzo difeso da un test, e 14 squadre con pochissimo storico non dichiarate (2026-09-19)

Chiude l'ordine della sessione: dopo *Accuratezza* (`docs/44`), l'ultima area del sito mai
passata al setaccio. Stesso metodo: **misurare la pagina pubblicata** e confrontarla con i
Parquet, senza toccare nulla finché non si è capito.

Area: `site/stagione.html` (**45 kB**, 7 tabelle, **132** righe) prodotta da
`SiteBuilder.build_stagione` (`build.py`) con `templates/stagione.html`, dai Parquet
`season_sim` e `history`.

---

## 1. Metodo

1. estratte le 7 tabelle e la nota iniziale (intestazioni, righe, numeri);
2. ricalcolati gli stessi numeri dai Parquet (`fixtures`, `history`, `predictions`,
   `season_sim`), compresa la **coerenza con le schede partita** — le due pagine devono
   raccontare lo stesso campionato;
3. verificate una per una le affermazioni della nota iniziale (è lì che stanno le promesse:
   metodo, numero di simulazioni, tie-break, casi limite).

## 2. Cosa pubblica la pagina (censimento)

Una tabella per lega (Serie A, Premier, LaLiga, Bundesliga, Ligue 1, Eredivisie, Liga
Portugal), colonne: **Squadra · PG · Pt · Pt attesi · Media pos. · 1° · UCL (prime N) · Retro**;
poi, sotto ogni tabella, la nota sull'accesso UCL e l'errore standard massimo misurato.

Il numero di posizioni UCL non è fisso: **4** per ITA1/ENG1/ESP1/GER1, **3** per FRA1,
**2** per NED1, **1** per POR1 — viene dalla configurazione (`ucl_spots`), non dedotto dalla
grandezza della lega (chiusura di `docs/19` P1.7).

## 3. Difetto A — «Monte Carlo su 10000 stagioni simulate», e il test che lo difendeva

La nota iniziale pubblicava il numero di simulazioni **senza il separatore delle migliaia**:
l'unico numero di quel tipo in tutto il sito, che altrove scrive «1.988 partite»,
«154.727 controlli», «7.498 schede», «spettatori 57.000» (convenzione `docs/24` §4, regola
`docs/20` #8: nessun numero ≥ 1000 senza separatore).

Due cose lo hanno tenuto in piedi:

- il controllo `[13-14]` di `verify_site.py` cerca `(\d{4,})\s*(partite|gare|gol)`: il
  sostantivo qui è **«stagioni»**, quindi «10000 stagioni» non era nemmeno letto;
- un'asserzione del test end-to-end (`tests/test_site.py:365`) diceva
  `assert "10.000" not in stag  # niente formattazioni inglesi`, cioè **difendeva il grezzo**:
  nata quando la pagina scriveva «10000», vieta proprio la forma italiana corretta, ed è in
  contraddizione con la riga precedente dello stesso test che pretende
  «spettatori 57.000» col separatore.

**Correzione:** `{{ n_sims|it_num }}`; il sostantivo «stagioni» aggiunto al controllo
`[13-14]`, che ora copre **tutto il sito**; l'asserzione riscritta (chiede «10.000 stagioni
simulate» e vieta «10000»), con la storia della riga precedente in commento per non
ripetere l'errore. **Prova di morso:** rimettendo «10000» nella pagina generata,
`verify_site` esce con **1 problema** («stagione.html: «10000 partite/gare/gol/stagioni»
senza separatore delle migliaia»).

## 4. Difetto B — parametri neutri promessi a squadre che non li ricevono, e 14 squadre con pochissimo storico taciute

La nota diceva:

> «Le squadre senza storico sufficiente (neopromosse) usano parametri neutri di lega.»

**Falso nel caso concreto.** Il fallback a parametri neutri (`_match_grid` in
`season_sim.py`) scatta solo quando una squadra è **del tutto assente** dallo storico di
allenamento, e oggi non ce n'è nessuna (tutte le 132 hanno almeno una gara in
`history.parquet`). Le squadre con **poche** gare ricevono invece parametri stimati su quei
pochi dati — e ve ne sono **14**, mai dichiarate da nessuna parte:

| Lega | Squadre sotto le 10 gare di storico | Gare |
|---|---|---|
| Bundesliga | SC Paderborn 07, SV Elversberg, Schalke 04 | **3** |
| Premier League | Coventry City (4), Hull City (5) | 4-5 |
| Liga Portugal | Académico Viseu (6), Marítimo (7) | 6-7 |
| LaLiga | Deportivo La Coruna, Malaga, Racing Santander | 6 |
| Ligue 1 | Le Mans, Troyes | 4 |
| Eredivisie | ADO Den Haag, Cambuur | 7 |
| Serie A | nessuna (minimo 42: Frosinone) | — |

Chi legge la proiezione di Paderborn (3 gare) o Coventry (4) deve sapere che poggia su
pochi dati: l'errore standard pubblicato (±0,50 pp) misura **solo** il rumore della
simulazione, non l'incertezza dei parametri — e la pagina non lo distingueva.

**Correzione:** `build_stagione` conta le gare di storico per squadra (`history.parquet`,
soglia dichiarata `STORICO_MINIMO = 10`, che **non** è una soglia di modello) e la pagina
pubblica, nell'intestazione: «Le squadre del tutto prive di storico sarebbero simulate con
le medie di lega: oggi non ce n'è nessuna (tutte le 132 hanno almeno una gara nello storico
di allenamento), ma 14 squadre hanno meno di 10 gare di storico e quindi parametri stimati
su pochi dati: è indicato lega per lega sotto ogni tabella», più una riga sotto **ogni**
tabella con i nomi (es. «Poche gare di storico: **Coventry City, Hull City** (2 squadre
sotto le 10 gare di allenamento): i loro parametri sono stimati su pochi dati, quindi la
loro proiezione è più incerta di quanto dica l'errore standard qui sopra, che misura solo il
rumore della simulazione»).

## 5. Correzione applicata (stesso giro)

- `templates/stagione.html`: `n_sims` con `it_num`; nota iniziale riscritta sui numeri
  calcolati; riga «Poche gare di storico» per lega, con singolare/plurale (`docs/40`).
- `build.py`: `STORICO_MINIMO = 10`; `build_stagione` conta le gare di storico per squadra e
  passa `fragili`, `n_fragili`, `n_senza_storico`, `n_squadre` al template.
- `scripts/verify_site.py`: controllo `[13-14]` esteso a «stagioni».
- `tests/test_site.py`: asserzione «niente formattazioni inglesi» sostituita dalla forma
  corretta (con la storia in commento).
- **4 test nuovi** in `tests/test_stagione_dichiarazioni.py` su store minimo, letti
  sull'HTML: separatore delle migliaia, squadra fragile nominata, intestazione che dice
  «nessuna senza storico», caso con una squadra a zero gare.

**Gate:** `pytest -q` **484 passed** (480 + 4), `ruff check .` pulito, `fda build` exit 0,
`verify_site` **0 problemi · 154.727 controlli**, `parita_schede` nessuna differenza,
`resa_375` **23.674 misure · 0 problemi**.

## 6. Cosa **non** è un difetto (verificato e chiuso, non intervenire)

- **Coerenza con le schede partita**: ripercorso il percorso delle *Proiezioni* (fit
  Dixon-Coles + Elo su `history.parquet`, ensemble 70/30, calibrazione dal Parquet) e
  confrontato con `predictions.parquet` su **10 gare restanti per 7 leghe = 70 gare**:
  **Δ massimo 0,00 punti percentuali** su 1·X·2. Stesso `n_train` per lega
  (1.183/1.185/1.202/950/956/973/974), stesso `model_version` (`dc-elo-tilt-0.4`), stessa
  calibrazione (`cal-momenti-1.1`, λ×1,0401 ρ−0,04). Le due pagine raccontano lo stesso
  campionato, come promette il docstring di `_match_grid`.
- **Classifica di partenza**: PG e Pt delle **132** squadre ricalcolati dalle gare finite di
  `fixtures.parquet` → **0 differenze**.
- **Somme delle probabilità** (atteso: 100% per il titolo, `top_n`×100% per l'UCL, 300% per
  la retrocessione): 1° tra 98% e 101%, UCL 398-400% contro 400% (top-4), 300/200/100% per
  3/2/1 posti, Retro 299-300%: scostamenti da **arrotondamento all'unità**, dichiarato in
  pagina.
- **Errore standard**: ±0,50 pp su tutte le 7 leghe = 0,5/√10.000 × 100 ✓ coerente con le
  10.000 simulazioni dichiarate.
- **Ordinamento e intervalli**: tabelle ordinate per punti attesi; «Pt attesi» sempre sopra i
  punti attuali (+19,1 … +32,1); posizione media dentro 1-N in ogni lega.
- **Retrocessioni**: 3 posti per tutte le leghe (`REL_COUNTS`), come dice la nota sulle
  regole di ogni campionato.
- **Nessun fallback attivo**: la colonna UCL non mostra «dato storico», cioè nessuno
  snapshot legacy senza `top_n` è in pagina.

## 7. Prossimo passo

Restano due candidati, non urgenti: (1) **conservare lo storico delle previsioni** per
rendere misurabile l'anticipo (`docs/44` §7); (2) valutare nel laboratorio se le squadre
con pochissimo storico vadano trattate esplicitamente (parametri neutri o shrinkage più
forte) invece di essere stimate su 3-7 gare — è una scelta di modello, non di sito, e come
tale passa dal `lab`.
