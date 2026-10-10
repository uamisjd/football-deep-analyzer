# 73 — Revisione: una sezione «laboratorio» nell'area previsione della scheda partita (2026-10-10)

**Richiesta dell'utente:** sulla scheda delle partite, una sezione «previsione» dove mettere in
futuro i tre tilt e «le altre idee e calcoli» — «ma deve essere fatta molto bene». Chiesta
una **revisione di fattibilità** prima di impegnarsi.

**Verdetto: fattibile, e consigliata con le condizioni del §5.** La sezione «previsione»
**esiste già**: la proposta è aggiungervi un card «laboratorio», non una sezione nuova.

## 1. Cosa esiste già (misurato sul template e sul sito)

La scheda ha un'area previsione con tre pezzi, in quest'ordine:

1. `id="previsione"` — «Previsione del modello» (barra 1X2, gol attesi λ, Over, BTTS, doppia
   chance, porta inviolata) + «Risultati esatti più probabili» (griglia `detail-card` a due card);
2. `id="scomposizione"` — «Come nasce questa probabilità»: catena dei passi con Δ pp e waterfall;
3. `id="fascia-storica"` — «Fascia storica del favorito».

La card «Fattori che spostano la partita» (`id="fattori"`) già dichiara il principio
editoriale: «Non sono un secondo pronostico e non cambiano la previsione salvata: la spiegano
con numeri già raccolti». Il sito già pubblica fattori **misurati e scartati** con la
ragione («Distanza della trasferta, età dei titolari e turnover … misurati e **non**
pubblicati, perché la misura non li sostiene»).

## 2. Copertura degli input per partita (misurata sulle 65 prossime, 7 leghe)

| Input | ITA1 | ENG1 | ESP1 | GER1 | FRA1 | POR1 | NED1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| prossime in finestra | 11 | 10 | 10 | 9 | 9 | 7 | 9 |
| valore titolari (entrambe > 0) | 10 | 10 | 9 | 8 | 8 | **3** | **4** |
| infermeria pesata (almeno una squadra) | 10 | 10 | 8 | 8 | 8 | 4 | 8 |
| riposo (da calendario) | 11 | 10 | 10 | 9 | 9 | 7 | 9 |

- **Riposo**: sempre calcolabile (7/7 leghe).
- **Assenze**: calcolabile quasi ovunque (7/7; POR1 4/7).
- **Valore titolari**: completo nelle 5 grandi leghe, **scarso in NED1/POR1** (3/7 e 4/9) —
  la card mostrerebbe «dato non disponibile» lì (regola del progetto: distinguere il dato
  assente).

## 3. Quanto muoverebbe il what-if (misurato applicando i tilt alle λ salvate, 65 prossime)

| Tilt | mediana Δλ (per squadra) | p90 | max | effetto > 0,15 |
|---|---:|---:|---:|---:|
| mercato (k=0,12) | **0,098** | 0,243 | 0,309 | 24 gare |
| assenze (k=0,30) | 0,054 | 0,140 | 0,216 | 5 gare |
| riposo | **0,000** | 0,000 | 0,000 | 0 gare |

- Il **mercato** è l'unico con un effetto visibile (mediana ~0,10 λ): il card mostrerebbe
  λ tiltate e 1X2 ricalcolati (la stessa griglia di `scripts/audit_modelli.py`).
- Le **assenze** muovono poco (mediana ~0,05 λ).
- Il **riposo** sulle prossime **non sposta nulla** (settimana normale, fattori 1,0): il card
  mostrerebbe «su questa partita non sposta nulla» — onesto, ma è la riga più vuota.
  Nelle settimane congestionate (backtest: 1.999/2.071 previsioni con fattore 1,02) si
  vedrebbe; sulle prossime attuali no.
- Le colonne tilt esistono nello schema di `predictions.parquet`
  (`lambda_home_market`, `lambda_home_absences`, `lambda_home_rest`, …) ma sono **vuote**
  nelle previsioni correnti: il what-if va calcolato al build (input per partita + λ salvata
  + le tre funzioni di `predict.py`), non letto da una colonna già pronta.

## 4. Effetti misurati in aggregato (già registrati: docs/48, docs/69 §1, docs/71)

| Tilt | Campione | Effetto misurato | Verdetto |
|---|---:|---|---|
| riposo | 1.591 λ modificate su 5.895 | ΔRPS **+0,0000787**, IC95 [+0,0000154; +0,000141] | **peggiora** (misurato 2 volte) |
| valore titolari | 341 gare | solo k=0,03 con IC che esclude lo zero; k=0,12 no | non promosso |
| assenze | 98 gare (instabile, docs/71 §2) | IC escludono lo zero ma andamento monotono | non testabile (< 300 gare) |

## 5. Condizioni per «fatta molto bene»

1. **Posizione**: un card a tutta larghezza `id="laboratorio"` **dopo** `id="scomposizione"`
   (previsione → come nasce → laboratorio): dentro l'area previsione, ma **sotto** la
   previsione salvata, mai sopra.
2. **Etichetta**: «Il laboratorio — idee misurate, **non usate** in questa previsione», con
   ⓘ che ripete: i numeri in cima alla scheda sono la previsione salvata; questo card mostra
   cosa cambierebbe ogni idea e quanto ha misurato sull'archivio; nessuna è applicata.
3. **Contenuto per idea**: (a) what-if su questa partita (λ tiltata vs λ publicada per
   squadra, 1X2 ricalcolata con la stessa griglia dell'audit); (b) l'effetto misurato in
   aggregato con IC; (c) il verdetto; (d) «dato non disponibile» dove manca l'input
   (NED1/POR1 sul valore titolari).
4. **La previsione salvata non cambia**: il card legge la previsione, non la scrive —
   dimostrabile (λ e probabilità del hero byte-identiche, predictions.parquet intatto).
5. **Invariante nuova** (es. [46] in `verify_site.py`): i λ what-if del card ricalcolati con
   un'implementazione **indipendente** delle tre formule (non importando le funzioni di
   `predict.py`), come l'oracolo di [44]/[45].
6. **Parità 7 leghe**: il card esce su tutte le leghe (con «dato non disponibile» dove
   manca), test di rendering, parità e `resa_375` verdi.
7. **Peso**: pagina più grande ~135 KB, tetto 900 KB (`MAX_PAGE_KB`) — un card da 2–4 KB
   non cambia nulla.
8. **Design per il futuro**: la lista è generico (idea → what-if → effetto misurato →
   verdetto), così le prossime idee entrano senza ridisegnare.

## 6. Rischi (e mitigazione)

- **«Secondo pronostico»**: il card mostra previsioni alternative — mitigato dalla
  posizione (sotto), dall'etichetta e dal verdetto misurato accanto a ogni idea.
- **Contenuto vuoto** (riposo sulle prossime): mitigato mostrando «non sposta nulla»
  invece di nascondere la riga — è onesto e dichiarato.
- **Dati mancanti** (NED1/POR1 sul valore): mitigato da «dato non disponibile».

## 7. Collegamento con la decisione A/B/C (docs/71 §4)

Il card dà ai tre tilt una **casa visibile**: le funzioni passano da «codice morto» a
«input della card di laboratorio», senza entrare nella ricetta di produzione. La scelta
A/B/C diventa allora quasi solo di organizzazione: **C** (restano in `predict.py`, dichiarate
e ora usate dal card) o **B** (spostate in un modulo di laboratorio, se il card cresce).
**A** resta non sostenuta dalle misure. La card funziona con entrambe.

## 8. Raccomandazione

**Si può fare, e fatto bene aggiunge profondità senza toccare la previsione.** Stima:
un card + calcolo what-if in `analysis.py` + invariant [46] + test + doc — una voce di
intervento, gate pieni. La decisione di procedere è dell'utente.
