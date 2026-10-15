# 108 — Previsione e Verifica: misura prima, un solo ritocco (15/10/2026)

Richiesta: qualità sulla coda delle ultime due sezioni della scheda. Regola B.10:
misurare, poi toccare solo un miglioramento netto.

Build locale dai Parquet del clone: **499 schede** (59 pre-partita, 440 finite).

## 1. Copertura (id presenti nella pagina)

| Sezione | Pre (59) | Finite con previsione (229) | Finite senza previsione (211) |
|---|---:|---:|---:|
| `#previsione` | 59 | 229 | 0 |
| `#scomposizione` | 59 (sempre 4 passi) | 157 | 0 |
| `#laboratorio` | 59 | **0** (scelta: what-if dopo il risultato) | 0 |
| `#fascia-storica` | 59 | 229 | 0 |
| `#posizione-lega` | 59 | 200 | 0 |
| `#primo-gol` | 59 | 229 | 0 |
| `#verifica` **prima** | 59, piena | 229, piena | **211, vuota** |
| `#probabilita` / `#gol-totali` | 59 | 229 | 0 |

Pre per lega: ITA1 10, ENG1 10, ESP1 11, GER1 9, FRA1 9, NED1 9, POR1 1.

## 2. Numeri della previsione (59 pre)

- Barra 1X2: somma **100/100** su 59/59 (resto massimo `pct3`).
- Tag modello **ensemble** su 59/59. Nessun «prior di lega» né «λ limitate» su questo campione.
- I 6 risultati esatti coprono **41,0–74,0** partite su 100 (mediana 51,7): il piè di card che
  manda alla matrice è onesto.
- Laboratorio: 59/59; «dato non disponibile» 1 o 2 volte per scheda (tipicamente valore titolari
  NED/POR e/o un input assente) — dichiarato, non inventato.

## 3. Cosa non si tocca (B.10)

- La ricetta Dixon-Coles + Elo.
- Laboratorio, fascia, posizione, primo gol: già sotto oracoli [10][12][15][16][17][46][47].
- Scomposizione assente su 72/229 finite con previsione: previsioni vecchie senza catena
  salvata; il template già nasconde la card se `prob_steps` è vuoto. Ricostruire a posteriori
  mentirebbe («non una ricostruzione», copy attuale).
- Posizione in lega assente su 29/229: campione di lega troppo magro a quella data. Non
  riempire.

## 4. Difetto misurato e correzione

**Prima:** 211 schede finite (Roma–Fiorentina 4-0 e analoghe, senza riga in
`predictions.parquet`) avevano `<details id="verifica">` con griglia vuota e voce indice
«Verifica» che atterrava sul nulla. Il piè diceva che matrice e istogramma «sono la stessa
previsione» in assenza di previsione.

**Dopo:** `{% if c.score_matrix or c.goals %}` su tendina **e** voce d'indice. Le 288 schede
con modello restano identiche. Invariante [33]: se la sezione c'è deve stare nell'indice;
se non c'è, niente voce.

Test: `test_verifica_assente_senza_previsione` (seed senza riga predizioni sulla 5749645).

## 5. Verdetto

La card previsione sulle 59 pre è **completa e internamente coerente**. L'unico intervento
di questa sessione è togliere la verifica vuota. Il resto è chiusura documentale, non
refactor.

## Prossimo passo

Gate tematici + ruff sul template; poi suite se verde. Daily serale (fotografia) resta
osservazione, non codice.
