# Promozione di `dc_elo_tilt` a ricetta di produzione — 2026-09-13

**In una riga:** il candidato di laboratorio che faceva entrare l'Elo **senza gonfiare i gol
attesi** ha vinto il confronto ufficiale in Actions ed è ora la ricetta con cui il sito
pubblica 1X2, gol attesi e mercati (`MODEL_VERSION` `dc-elo-ens-0.3` → `dc-elo-tilt-0.4`).

Nota sui commit: l'handover indicava il commit `f2eb01c`, che **non esiste** in questo
repository — verificato cercandolo su `main`, sui 26 branch `arena/*` e fra tutti gli oggetti
scaricati (oltre 200 commit, `git cat-file --batch-all-objects`; nessuno inizia per `f2eb01c`, e
l'API GitHub risponde `No commit found for SHA`). I numeri ufficiali usati qui sono quelli
dell'ultimo run `lab` in Actions, commit **`bb247fe`** «lab: confronto modelli 2026-09-13
21:33 UTC» (run 34784018926), che è anche il commit di partenza di questo lavoro.

---

## 1. Il verdetto ufficiale (`model_lab.parquet`, 1.527 gare, 7 leghe)

`fda lab` in Actions con 5 candidati, finestre di 90 giorni, `min_train 800`, storico reale
(`history.parquet`), correzione automatica del livello dei gol attiva per ogni candidato.

| candidato | RPS | Δ RPS | IC 95% appaiato | migliore in | bias λ | scala applicata | Brier mercati |
|---|---|---|---|---|---|---|---|
| **`dc_elo_tilt`** | **0,202705** | **−0,000406** | **[−0,000773; −0,000041]** | 57,0% | **−0,086** | 1,013 | 0,203001 |
| `dc_puro` | 0,202794 | −0,000317 | [−0,000939; +0,000257] | 54,0% | −0,086 | 1,013 | 0,202818 |
| `prod_w85` | 0,202915 | −0,000197 | [−0,000507; +0,000097] | 53,7% | +0,015 | 0,988 | 0,201966 |
| `dc_elo_prod` (baseline) | 0,203112 | — | — | — | +0,105 | 0,955 | 0,202340 |
| `prod_w50` | 0,203608 | +0,000497 | [+0,000113; +0,000909] | 43,7% | +0,245 | 0,928 | 0,203873 |

RPS più basso per lega (`dc_elo_tilt` contro la baseline): **5 su 7** — vince in ESP1
(0,201182 < 0,201491), GER1 (0,194111 < 0,194367), ITA1 (0,203990 < 0,205163), NED1
(0,197392 < 0,197553), POR1 (0,180627 < 0,180980); perde in ENG1 (0,208348 contro 0,208302) e
FRA1 (0,229643 contro 0,229595).

**Criterio di `docs/13` §6.5** — «si cambia modello solo se un candidato batte la baseline con
IC 95% appaiato interamente negativo **e** il vantaggio vale in almeno 5 leghe su 7»:

- IC interamente negativo → **sì** (estremo superiore −0,000041);
- ≥5 leghe su 7 → **sì** (5).

Gli altri due candidati che vincono 5 leghe su 7 (`dc_puro`, `prod_w85`) hanno intervalli che
contengono lo 0 e non sono promuovibili; `prod_w50` è significativamente peggiore.

## 2. Che cosa cambia nel modello

Prima: `ensemble()` prendeva l'1X2 mediato (0,7·Dixon-Coles + 0,3·Elo) e cercava **due λ
libere** capaci di riprodurlo (`penaltyblog.goal_expectancy`). Poiché l'Elo è più netto del
modello sui gol, l'unico modo di riprodurre quel vettore era **alzare i gol attesi**: +15/20%
sulle λ del Dixon-Coles, bias +0,24 gol sul backtest. Era un difetto *introdotto dalla ricetta*
e poi corretto a valle dalla calibrazione.

Ora: l'Elo **inclina** il rapporto casa/trasferta e il totale dei gol attesi resta quello
stimato dal modello sui gol (`_tilt_lambdas`, griglia di inclinazioni 0,85…1,15 a passi di
0,01). L'1X2 pubblicato è quello della griglia risultante, quindi 1X2, doppie chance, risultati
esatti, Over/Under e BTTS derivano da **una sola matrice**, senza bisogno di correzioni a valle.

| aspetto | prima (`inverti`) | ora (`tilt`) |
|---|---|---|
| totale gol attesi | gonfiato dall'inversione | = modello sui gol |
| λ pubblicate | invertite + limiti di sicurezza | inclinate + (raramente) limiti |
| 1X2 pubblicato | vettore mediato | 1X2 della griglia pubblicata |
| calibrazione necessaria | λ×0,91 per correggere la sovrastima | λ×1,04 per correggere la sottostima |
| codice | `ensemble(mode="inverti")` | `ensemble(mode="tilt")` (default) |

Modifiche concrete:

- `src/fda/models/predict.py`: `ENSEMBLE_MODE = "tilt"`, `ENSEMBLE_MODES`, `TILT_GRID`,
  `_tilt_lambdas`, `_tilt_pair`, `_one_x_two`; `ensemble(dc, elo, w_dc, mode)` con le due
  ricette; doppia chance sempre ricalcolata sull'1X2 pubblicato; i limiti di sicurezza
  (`_clamp_lambda`) ora si applicano anche **dopo** la calibrazione, cioè sui gol attesi che il
  lettore vede; `MODEL_VERSION` 0.3 → 0.4.
- `src/fda/models/lab.py`: il candidato di produzione e la sua alternativa usano
  `predict.ensemble` — **una sola implementazione**, così il laboratorio misura esattamente ciò
  che il sito pubblica; `dc_elo_tilt` (promosso) diventa la baseline `dc_elo_prod` e la
  ricetta precedente resta in laboratorio come `dc_elo_ge` (`mode="inverti"`).
- Dati rigenerati con la nuova ricetta: `backtest.parquet` (5.812 gare), `calibration.parquet`,
  `predictions.parquet` (2.071 partite).

## 3. Misure prima/dopo **sullo stesso corpus** (5.812 gare fuori campione, 7 leghe)

Confronto appaiato: stessa partita, stessa finestra, stesso storico; l'unica differenza è la
ricetta. La griglia della ricetta precedente è stata ricalcolata sullo stesso `history.parquet`
rimontando `backtest.ensemble` con `mode="inverti"`.

| metrica | grezzo vecchio | grezzo nuovo | calibrato vecchio | calibrato nuovo |
|---|---|---|---|---|
| RPS 1X2 | 0,19919 | 0,19898 | 0,19957 | **0,19881** |
| log-loss | 0,98646 | 0,98473 | 0,98635 | **0,98401** |
| Brier 1X2 | 0,58728 | 0,58680 | 0,58775 | **0,58642** |
| Brier 6 mercati | 0,20577 | 0,20588 | 0,20458 | 0,20506 |
| gol attesi (osservati 2,863) | 3,104 | 2,730 | 2,839 | 2,839 |
| bias λ | **+0,241** | −0,133 | −0,024 | −0,024 |
| pareggio previsto (osservato 25,6%) | 23,9% | **25,7%** | 26,2% | 25,9% |
| Over 2,5 previsto (osservato 54,9%) | 58,9% | 50,7% | 53,2% | 53,2% |

Bootstrap appaiato a 95% (4.000 ricampionamenti, 5.812 gare) sul **calibrato**:

| metrica | Δ (nuovo − vecchio) | IC 95% | leghe a favore |
|---|---|---|---|
| RPS 1X2 | **−0,00076** | [−0,00101; −0,00050] | **7 su 7** |
| Brier 1X2 | **−0,00133** | [−0,00189; −0,00076] | — |
| Brier 6 mercati | +0,00048 | [−0,00013; +0,00108] | 0 su 7 |
| obiettivo `fda calibrate` (RPS + 0,5·Brier) | **−0,00051** | [−0,00091; −0,00009] | — |

Per lega (RPS calibrato, vecchia → nuova): ENG1 0,20243 → 0,20174; ESP1 0,20238 → 0,20166;
FRA1 0,21060 → 0,20994; GER1 0,20406 → 0,20378; ITA1 0,19828 → 0,19731; NED1 0,19481 → 0,19418;
POR1 0,18342 → 0,18213.

Lettura onesta:

1. **l'1X2 migliora in modo significativo e in tutte e 7 le leghe** (−0,00076 di RPS, intervallo
   interamente negativo), e il log-loss migliora il triplo (−0,0023);
2. **il Brier dei mercati sui gol peggiora di 0,00048, con un intervallo che contiene lo 0**:
   non è significativo, ma è sistematico (peggiora in 7 leghe su 7, e in FRA1 di 0,0019). La
   causa è che la calibrazione corregge il **livello** medio dei gol, non la **forma** della
   distribuzione: con λ più basse gli Over perdono un po' di massa (Over 1,5 +0,00088,
   Over 2,5 +0,00117, Over 3,5 +0,00045, BTTS +0,00044; porte inviolate −0,00026 e +0,00021).
   È il prezzo dichiarato della promozione, ed è più piccolo del guadagno sull'obiettivo che
   `fda calibrate` ottimizza (−0,00051, intervallo interamente negativo);
3. **il pareggio grezzo è ora centrato** (25,7% contro 25,6% osservato, scarto 0,04 punti) senza
   bisogno di correzioni: era il difetto più visibile (23,9% contro 25,6%).

Verifica walk-forward della calibrazione (4.843 gare tenute fuori, stessa procedura per entrambe
le ricette):

| | RPS prima → dopo | Brier mercati prima → dopo | bias λ prima → dopo |
|---|---|---|---|
| ricetta precedente | 0,20025 → 0,20050 (+0,00025) | 0,20646 → 0,20517 (−0,00129) | +0,261 → +0,054 |
| **ricetta promossa** | 0,20009 → **0,19992 (−0,00016)** | 0,20636 → 0,20565 (−0,00071) | −0,113 → **+0,019** |

Con la ricetta promossa la calibrazione non costa più RPS (era il «prezzo dichiarato» di
`docs/13` §3.2: +0,0003) e lascia un bias residuo più piccolo: c'è meno da correggere.

## 4. Perché la calibrazione è stata ristimata

I due parametri (`λ×m`, `ρ+Δ`) sono una correzione del **livello** dei gol attesi: dipendono
dalla ricetta che produce quelle λ. Riutilizzare il moltiplicatore stimato sulla ricetta
precedente (λ×0,9135) sulle λ della nuova avrebbe significato pubblicare per un run — fino al
primo `fda backtest` utile — numeri sbagliati in modo visibile:

| con λ×0,9135 (vecchio) sulle λ nuove | con λ×1,0401 (ristimato) |
|---|---|
| bias λ **−0,369** gol | bias λ **−0,024** gol |
| Brier 6 mercati **0,21016** (contro 0,20458) | Brier 6 mercati 0,20506 |
| pareggio previsto **28,2%** (osservato 25,6%) | pareggio previsto 25,9% |

La calibrazione è stata quindi ricalcolata **sul backtest rigenerato con la nuova ricetta**
(`fda calibrate`, stimatore a momenti, finestra 730 giorni, 4.760 gare di stima su 5.812):

```
λ×1,0401 · ρ−0,04 · cal-momenti-1.1
walk-forward (4.843 gare): RPS 0,20009 → 0,19992 · Brier mercati 0,20636 → 0,20565
                           bias λ −0,113 → +0,019 gol
campione pieno:            bias λ −0,133 → −0,024 · pareggio 25,7% → 25,9% (osservato 25,6%)
```

Sullo stesso corpus la ricetta precedente chiede λ×0,9148: il moltiplicatore passa da «tira giù»
a «tira su», e si ferma appena sotto il limite di sicurezza 1,05. È la firma del difetto che la
promozione rimuove: i gol attesi non sono più gonfiati, quindi la correzione non deve più
comprimerli.

## 5. Controverifica del laboratorio con il codice promosso

Riesecuzione offline (`fda lab`, `--history data/processed/history.parquet`, 90 giorni,
`min_train 800`, 1.527 gare, `--no-save` per non toccare il parquet ufficiale) con la baseline
che ora è il tilt e la ricetta precedente come candidato `dc_elo_ge`:

| candidato | RPS | Δ RPS | IC 95% | bias λ |
|---|---|---|---|---|
| `prod_w85` | 0,2026 | −0,0001 | [−0,0004; +0,0002] | −0,086 |
| **`dc_elo_prod` (tilt, baseline)** | 0,2027 | — | — | −0,086 |
| `dc_puro` | 0,2028 | +0,0001 | [−0,0005; +0,0007] | −0,086 |
| `prod_w50` | 0,2028 | +0,0001 | [−0,0002; +0,0005] | −0,086 |
| `dc_elo_ge` (ricetta precedente) | 0,2031 | **+0,0004** | [+0,0001; +0,0008] | +0,105 |

Il risultato è l'immagine speculare del verdetto originale: la ricetta precedente è ora
**significativamente peggiore** (+0,0004, IC interamente positivo), con lo stesso ordine di
grandezza (−0,000406) misurato in Actions quando il tilt era il candidato. Laboratorio e
produzione usano lo stesso codice, quindi il confronto è ripetibile.

## 6. Verifiche eseguite

- suite **176 passed** (4 test nuovi: tilt, ricetta precedente, limiti pubblicati, candidati
  del laboratorio; 2 aggiornati), `ruff --select F,E9` pulito su `src`, `tests`, `scripts`;
- **2.071 previsioni rigenerate** con la nuova ricetta (7/7 leghe): nessuna con λ per squadra
  > 4,00 o totale > 5,5 (massimo 5,195), **1 sola** con i limiti di sicurezza attivi (0,05%:
  con la ricetta precedente erano l'1,2%);
- `scripts/verify_site.py`: **0 problemi · 12.086 controlli numerici**, 4.116 pagine (376
  schede / 2.364 fixture / 7.450 giocatori); controllo [8b] ricalcola la calibrazione
  λ×1,040 ρ−0,04 sul nuovo backtest e trova bias −0,133 → −0,024 e pareggio 25,7% → 25,9%;
- backtest rigenerato offline da `history.parquet`: la procedura è stata validata riproducendo
  **riga per riga** il backtest della ricetta precedente committato da Actions (5.811 gare,
  RPS 0,19919, bias λ +0,24084) prima di generare quello nuovo;
- i dati grezzi del confronto (bootstrap, per lega, per mercato) sono ricalcolabili con gli
  stessi comandi descritti qui; `model_lab.parquet` **non** è stato riscritto.

## 7. Da verificare dal vivo (Actions, dopo il merge)

1. il primo run `daily` conferma `λ×1,04 ρ−0,04` e un bias λ del campione pieno entro ±0,05;
2. la pagina Accuratezza mostra RPS ≈ 0,1988 (calibrato) e il pareggio dentro l'intervallo di
   Wilson 95% dell'osservato;
3. nessuna scheda pubblicata con λ per squadra > 4,00 o totale > 5,5;
4. il prossimo `lab` in Actions (lunedì 05:30 IT) riporta `dc_elo_prod` = tilt e `dc_elo_ge`
   come ricetta precedente.

## 8. Prossimo passo

Il Brier dei mercati sui gol peggiora in modo non significativo ma sistematico in 7 leghe su 7
(Over 1,5 +0,00088, Over 2,5 +0,00117). La causa strutturale è nota in letteratura
(arXiv:2103.07272): nella griglia di Dixon-Coles ρ non può spostare le probabilità Over/Under,
serve una copula. Candidati da mettere in laboratorio, in ordine: `weibull_copula` (già fra i
22 candidati, mai girato su storico reale) e una correzione della **forma** (non solo del
livello) nella calibrazione. Non prima di avere un secondo giro di lab che confermi questo
primo verdetto.
