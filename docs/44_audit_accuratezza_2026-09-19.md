# 44 — Audit della pagina *Accuratezza*: due affermazioni non sostenute dai dati (2026-09-19)

Quarto punto dell'ordine scelto in sessione (dopo i numeri falsi del valore di mercato, il peso
delle pagine e la prova dell'allerta). Stesso metodo di `docs/43`: **misurare la pagina pubblicata**
e confrontarla con i Parquet, senza toccare nulla finché non si è capito.

Area: `site/accuratezza.html` (**37 kB**, 7 tabelle) prodotta da `SiteBuilder.build_accuracy`
(`build.py:646`) con `templates/accuracy.html`.

---

## 1. Metodo

1. estratte le 7 tabelle della pagina (intestazioni, righe, numeri);
2. ricostruiti gli stessi numeri dai Parquet (`predictions`, `fixtures`, `backtest`) per vedere
   se ciò che la pagina *dice* combacia con ciò che *misura*;
3. cercate, una per una, le affermazioni della pagina che i dati non possono sostenere
   (è la classe di difetti già vista in `docs/20` #2: frasi vere ieri, false oggi).

Tutto è misurato sul sito ricostruito il 2026-09-19 con i dati del run delle 18:02 UTC.

## 2. Cosa pubblica la pagina (censimento)

| Sezione | Contenuto | Righe |
|---|---|---|
| Riepilogo | per lega e «Tutti»: gare valutate, RPS, Brier, esito top, RPS naive, n base, Δ | 8 (7 leghe + Tutti) |
| Accuratezza per mercato | Over 1,5 / 2,5 / 3,5, BTTS, 1X, 12, X2, clean sheet casa/trasferta | 9 |
| Backtest storico fuori campione | riepilogo + esiti + mercati, solo ricetta corrente | 3 + 9 |
| RPS per anticipo | bucket 0–7 / 8–14 / 15–30 / 31–60 / 61+ giorni | **1** |
| Calibrazione | 1 / X / 2: previsto, osservato, Wilson 95% | 3 |
| Ultime partite valutate | le 40 più recenti | 40 |

Numeri pubblicati oggi: **120** gare valutate (13-27 per lega), RPS **0,2021**, Brier **0,6096**,
RPS naive **0,2300**, Δ **−0,028**; calibrazione 1: 43,4% previsto contro 37,5% osservato
(29,4–46,4%), X: 24,2% contro 29,2%, 2: 32,4% contro 33,3% — tutte dentro l'intervallo.

## 3. Difetto A — «RPS per anticipo» promette un confronto che il disegno rende impossibile

La sezione diceva:

> «Quanto prima è stata fatta la previsione? **Ora misurabile** perché Tappa 1 prevede tutto il
> calendario (chiave `(match_id, model)` unica, `made_at` vs `utc_kickoff`). **Se la qualità
> peggiora con l'anticipo, lo vedremo qui.**»

e sotto elencava cinque bucket (0–7, 8–14, 15–30, 31–60, 61+ giorni). **Nella pagina ce n'è uno
solo** («0–7 giorni», 120 gare, anticipo medio 0,1 giorni). Non è un caso:

| Misura (120 gare valutate) | Valore |
|---|---|
| righe di `predictions.parquet` per `match_id` | **max 1** |
| `made_at` distinti in tutto il file | 97 (uno per run: 5 al giorno dal 6 settembre) |
| anticipo medio / mediana | **0,11 / 0,06 giorni** (2,6 h / 1,4 h) |
| anticipo min / max | 0,00 / **0,60 giorni** |
| gare con anticipo < 12 h / 12-24 h / > 24 h | **110 / 10 / 0** |
| anticipo medio sulle 2.026 gare *future* | **133,5 giorni** (max 252,9) |

La chiave `(match_id, model)` unica significa che la previsione di ogni gara viene **sovrascritta a
ogni run**: resta sempre e solo l'ultima, cioè quella delle ~2 ore prima del calcio d'inizio. Una
previsione «vecchia di 10 giorni» **non esiste più nel file** quando la gara si gioca, quindi il
bucket corrispondente non può riempirsi — oggi, domani o fra un anno, finché il disegno resta questo.
La frase «se la qualità peggiora con l'anticipo, lo vedremo qui» era una promessa non mantenibile.

## 4. Difetto B — «120 gare valutate» senza dire su quante

Il Riepilogo pubblica «120 gare valutate» e, più sotto, la **composizione** del campione
(39 gare col modello corrente, 48 con la calibrazione attiva, versioni in archivio: chiusura di
`docs/19` P0.6, fatta bene). Manca però la **copertura**: 120 su quante?

| Gare finite in stagione (`fixtures.status == finished`) | **331** |
|---|---|
| valutate (previsione salvata prima del fischio d'inizio) | **120** (36%) |
| giocate **prima** della prima previsione registrata (06/09/2026 10:35) | **202** |
| finite dopo, ma **senza** una previsione salvata prima del calcio d'inizio | **9** |

Le 9 (8-9 settembre: 5 di Eredivisie, 1 di Liga Portugal, ecc.) sono entrate nel calendario quando
la finestra di previsione era già passata: una previsione fatta dopo la partita non è una
previsione, e infatti `build.py:656` le scarta giustamente (`made_at < utc_kickoff`). Ma la pagina
non lo diceva, e «120 gare valutate» si legge come «tutte le gare giocate».

La copertura non è uniforme fra le leghe: conta anche su quale campionato si legge l'RPS.

| Lega | Valutate | Finite in stagione | % |
|---|---|---|---|
| LaLiga | 27 | 62 | 44% |
| Eredivisie | 14 | 56 | 25% |
| Liga Portugal | 13 | 55 | 24% |
| Premier League | 17 | 45 | 38% |
| Serie A | 19 | 43 | 44% |
| Ligue 1 | 14 | 38 | 37% |
| Bundesliga | 16 | 32 | 50% |
| **Tutti** | **120** | **331** | **36%** |

## 5. Correzione applicata (stesso giro)

Due righe di testo nella pagina, ma **costruite sui numeri**, non scritte a mano:

1. **`copertura`** calcolata in `build.py` (finite / valutate / precedenti / senza / prima
   previsione registrata) e pubblicata sotto il Riepilogo:
   > «Copertura: **120** gare valutate su **331** finite in stagione: **202** gare sono precedenti
   > alla prima previsione registrata (06/09/2026 10:35) e **9** gare non avevano una previsione
   > salvata prima del calcio d'inizio. Nessuna di quelle escluse entra nei numeri qui sopra: una
   > previsione fatta dopo la partita non è una previsione.»
2. **`lead_stats`** (n, media, min, max) e la spiegazione del perché i bucket oltre il primo restano
   vuoti, al posto della promessa:
   > «…oggi **0,1 giorni** su **120** gare (min 0,0, max 0,6).» / «La chiave `(match_id, model)` è
   > unica e la previsione di ogni gara viene **rifatta a ogni run** (5 al giorno): ne resta una
   > sola, l'ultima… Per costruzione non esiste una previsione “vecchia di 10 giorni” da valutare,
   > quindi da questa tabella **non** si può leggere se la qualità peggiora con l'anticipo: serve
   > conservare lo storico delle previsioni (una riga per run), che oggi non c'è.»

Concordanza singolare/plurale gestita nel template (come richiesto da `docs/40`).

**Test nuovi (2)** in `tests/test_accuratezza_copertura.py`, costruiti su uno store minimo e letti
sull'HTML, come fa il lettore: copertura 2 valutate su 4 finite (1 precedente, 1 senza previsione
valida) e anticipo pubblicato con la spiegazione. Entrambi falliscono senza la modifica: i paragrafi
semplicemente non esistevano.

**Gate (dopo la ricostruzione del sito):** `pytest -q` **480 passed** (478 + 2), `ruff check .`
pulito, `fda build` exit 0 (375/2.364/7.498), `verify_site` **0 problemi · 154.727 controlli**,
`parita_schede` **nessuna differenza**, `resa_375` **23.674 misure · 0 problemi**.

## 6. Cosa **non** è un difetto (verificato e chiuso, non intervenire)

- **Composizione del campione** (`docs/19` P0.6): la pagina la dichiara (39 col modello corrente,
  48 calibrate, versioni in archivio) e spiega perché la tabella live può divergere dal backtest.
- **Base naive**: non è più 45/27/28 hard-coded ma la frequenza reale 1X2 per lega (`outcome_freqs`,
  `docs/19` P1.1): colonna «n base» 950-1.202 gare di storico, e sotto le 30 la pagina lo dichiara
  con «fisso».
- **Previsioni sul calendario lontano**: `prossime.html` dichiara che per le 1.988 gare oltre i
  7 giorni «c'è già la previsione del modello (1X2, gol attesi, Over 2,5), **ricalcolata a ogni
  aggiornamento**» e che la scheda completa arriva a ridosso della gara. Nessuna promessa falsa.
- **Quote e confronto coi bookmaker**: non compaiono (decisione `docs/38`); il benchmark resta un
  job mensile (`benchmark.yml`, primo run 3/10) e non è pubblicato come vanto.
- **Δ vs naive −0,028**: il modello batte la base, e la pagina dice che il segno è «modello − base».

## 7. Prossimo passo

L'unico modo per avere davvero un gradiente di qualità sull'anticipo è **conservare lo storico delle
previsioni** (una riga per run per gara, tabella `prediction_history`), con due effetti da valutare
prima: peso su disco/runtime del commit giornaliero e regola di scarto (tenere 1 previsione al
giorno per gara, non 5). Da non fare a cuor leggero: **candidato**, non urgenza, e la pagina oggi
dice la verità senza bisogno di quello storico.
