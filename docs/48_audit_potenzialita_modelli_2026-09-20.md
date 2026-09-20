# Audit delle potenzialità di calcolo dei modelli di previsione — 2026-09-20

> **Domanda dell'utente:** «audit delle potenzialità di calcolo dei modelli usati per i pronostici: si può fare di meglio? ci sono altre cose che possiamo usare? ci sono calibrazioni da fare a livello quantitativo, qualitativo, visivo e grafico?»
>
> **Metodo.** Tutto misurato **offline** sui Parquet versionati (`backtest.parquet` 5.891 gare fuori campione 2024-01-20→2026-09-20, `history.parquet` 7.463 gare, `predictions.parquet` 2.152 righe, `model_lab.parquet` 22 candidati × 1.528 gare, `match_info`/`lineup`/`player_stats` della stagione in corso), con lo script riproducibile **`scripts/audit_modelli.py`** (output completo in `docs/_audit_modelli.json`). Nessuna richiesta di rete. Le classi di verità sono quelle della regola B.2: *misurato* (qui), *misurato dal laboratorio in Actions* (`model_lab.parquet`), *letteratura* (citata come tale).

---

## 0. Verdetto in dieci righe

1. **Il motore è sano e vicino al suo tetto strutturale**: RPS **0,1989** pubblicato su 5.891 gare (naive 0,2305), log-loss 0,984, Brier 0,587. Tutte le famiglie provate dal laboratorio (Poisson, DC, binomiale negativa, zero-inflazionata, bivariata, Weibull-copula, Elo, pi-ratings) stanno in **0,0008 RPS** l'una dall'altra: **cambiare famiglia non serve più**.
2. **L'Elo non aggiunge nulla di misurabile**: Dixon-Coles puro 0,1991 contro 0,1989 dell'ensemble, Δ 0,00014 con IC 95% [−0,00015; +0,00044] → zero dentro. L'Elo da solo è molto peggio (0,2025). Si tiene per prudenza, ma **non è una leva**.
3. **Il difetto misurabile del modello è la piattezza**: sottostima i favoriti netti e sovrastima gli sfavoriti netti in modo statisticamente distinguibile (decile alto casa: dichiarato 72,9% → osservato **79,2%** [75,7; 82,2]; decile basso trasferta: 9,4% → **6,1%** [4,4; 8,3]). Una **temperatura T ≈ 0,86** (stimata walk-forward, stessa direzione in 3 stagioni su 3 e 7 leghe su 7) vale **−0,0004 RPS**: tanto quanto tutta la promozione del tilt (`docs/15`). È il candidato di laboratorio più forte oggi (§4.1).
4. **La distanza dal mercato è il vero divario**: sulle 1.071 gare NED1/POR1 con quote di chiusura nello storico il modello fa 0,1871 contro **0,1785** del mercato (Δ **0,0085**, IC [0,0050; 0,0119]): **venti volte** l'effetto dell'Elo. Nessun ritocco interno lo chiude; lo chiude solo **informazione** (xG storico, formazioni, mercato) — §3.
5. **Regressione di processo (P0)**: la PR #68 di oggi ha messo in produzione **tre correttivi alle λ** (valore di mercato dei titolari, assenze, riposo) **senza laboratorio, senza griglia dichiarata, senza ristimare la calibrazione, senza cambiare `MODEL_VERSION`** e senza che il backtest li includa — in violazione della regola D («nessuna PR che cambi `predict.py` senza griglia dichiarata»). Misurati qui: **riposo peggiora** (ΔRPS +0,00008, IC [+0,00001; +0,00015]); **valore di mercato e assenze non distinguibili da zero** sugli unici 337/137 casi disponibili, e il commento «k=0,12 calibrato su 5,7k gare» è **impossibile** (il dato esiste per 371 gare). Le dimensioni degli effetti sono arbitrarie: l'infermeria ha tagliato **−22%** la λ della Juventus oggi, ribaltando il favorito (§2.5).
6. **La scheda mente sul primo passo**: «Come nasce questa probabilità» chiama «Modello sui gol (Dixon-Coles), senza rating» un vettore che include già mercato+assenze+riposo (Juventus–Atalanta: DC puro **42,7/27,8/29,5**, mostrato **34,2/28,1/37,7**). E la riga dei «Fattori» dice «non cambiano la previsione salvata»: da oggi è falso.
7. **La calibrazione in produzione è ferma al 13/09**: `daily` chiama `calibrate_cmd()` senza argomenti e i default restano oggetti `typer.OptionInfo` → `TypeError` catturato, «calibrate fallito», run che prosegue. Stesso bug già corretto per `collect` l'8/9. **Corretto in questa sessione** con test di regressione (§5).
8. **Il campione corrente è più prolifico del modello**: nelle 348 gare 2026-27 il rapporto gol/λ è **1,124** (GER1 1,42, NED1 1,19, ENG1/ITA1 1,12) e la vittoria interna è al 39,9% contro il 42,9% dichiarato; la calibrazione «a momenti su 730 giorni» reagisce con mesi di ritardo (§4.2).
9. **Visivo/grafico**: la pagina *Accuratezza* verifica la calibrazione con **tre medie** (1, X, 2) che per costruzione **non possono vedere** la piattezza (i decili sbagliano in direzioni opposte e si compensano): serve il **diagramma di affidabilità per decili** (§6).
10. **Cosa usare in più, in ordine di resa attesa**: xG storico Understat (2 stagioni, 5 leghe, ~10 richieste) → candidato `dc_xg`; temperatura; shrinkage ridotto; storico delle previsioni per run (per misurare davvero l'anticipo); quote di chiusura come **metro** su tutte e 7 le leghe (già decisione A di `docs/19`) — §3.

---

## 1. Cosa c'è oggi (inventario verificato nel codice)

| Componente | Dove | Stato misurato |
|---|---|---|
| Dixon-Coles (penaltyblog) ξ=0,0018, `max_goals` 10, shrinkage `SHRINK_PRIOR=8` verso la media di lega | `predict.py::DixonColesModel` | RPS puro 0,1991; il laboratorio dà `dc_no_shrink` **0,20256** contro `dc_elo_prod` 0,20309 e `dc_shrink16` 0,20410: **monotono, meno shrinkage = meglio** (IC include 0) |
| Elo k=20, HFA 60 | `EloModel` | 0,2025 da solo; nell'ensemble contributo 0,00014 (IC con 0) |
| Ensemble «tilt»: l'Elo inclina il rapporto casa/trasferta a totale invariato, ricerca su griglia 0,85…1,15 | `ensemble`, `_tilt_lambdas` | promosso con ΔRPS −0,000406 (`docs/15`); qui confermato dello stesso ordine |
| Calibrazione «momenti» (λ×m, ρ+Δ) su 730 giorni | `calibration.py` | +0,00017 RPS fuori campione (IC positivo); **ferma al 13/09** per il bug §5 |
| ξ per lega (`xi_league.parquet`) | `xi_for_league` | file **vuoto**: `lab-xi` non è mai stato eseguito → ξ globale ovunque |
| **Nuovi (PR #68, oggi)**: valore titolari `ratio^0,12` (clip 0,2–5), assenze `1−0,3·c/2` (min 0,70), riposo 0,95/0,98/1,02 | `market_value_tilt`, `absences_tilt`, `rest_tilt` | **non nel backtest, non nel laboratorio, non nella calibrazione**; misure in §2 |
| Limiti di sicurezza sulle λ | `_clamp_lambda` | 3 partite su 2.152 toccate (0,14%) |
| Laboratorio walk-forward, 22 candidati, griglia pre-registrata | `lab.py`, `lab.yml` (lunedì) | ultimo run: tutte le famiglie entro 0,0008 RPS |
| Monte Carlo stagione 10.000 | `season_sim.py` | coerente con `predictions` (Δ max 0,00 pp, `docs/45`) |

---

## 2. Misure (tutte riproducibili con `python scripts/audit_modelli.py`)

### 2.1 Quanto vale ogni pezzo (5.891 gare, stesse gare, IC appaiato bootstrap 3.000)

| ricetta | RPS | log-loss | Brier | X previsto | ΔRPS vs pubblicato | IC 95% |
|---|---|---|---|---|---|---|
| **pubblicato** (DC+Elo tilt, calibrato) | **0,1989** | 0,9842 | 0,5865 | 25,9% | — | — |
| stesso, senza calibrazione | 0,1991 | 0,9849 | 0,5869 | 25,7% | +0,00017 | [+0,00011; +0,00022] |
| Dixon-Coles puro | 0,1991 | 0,9849 | 0,5868 | 25,6% | +0,00014 | [−0,00015; +0,00044] |
| Elo puro | 0,2025 | 1,0060 | 0,5970 | 19,7% | +0,00356 | [+0,00273; +0,00442] |
| naive (frequenze del campione) | 0,2305 | 1,0761 | 0,6515 | 25,6% | +0,03159 | [+0,02883; +0,03442] |

Osservato: 1 = 42,8% · X = 25,6% · 2 = 31,6%. Per lega il pubblicato va da **0,1825** (POR1) a **0,2103** (FRA1); il DC puro è entro ±0,0005 in ogni lega.

**Lettura.** La calibrazione paga poco ma con certezza; l'Elo non paga. Il modello sui gol da solo è già il prodotto.

### 2.2 Affidabilità dell'1X2 per decili (pubblicato)

| esito | decile più basso | decile più alto |
|---|---|---|
| 1 casa | dichiarato 17,3% → osservato **13,8%** [11,2; 16,8] ← fuori | 72,9% → **79,2%** [75,7; 82,2] ← fuori |
| X | 16,6% → 14,9% [12,3; 18,0] | 33,1% → **29,3%** [25,8; 33,1] ← fuori |
| 2 trasferta | 9,4% → **6,1%** [4,4; 8,3] ← fuori | 59,3% → **65,6%** [61,7; 69,3] ← fuori (anche il 9º: 47,0% → 54,8%) |

Scomposizione di Brier: **affidabilità 0,0024 · risoluzione 0,0657 · incertezza 0,6515**. Il termine di affidabilità è piccolo (il modello è *mediamente* calibrato) ma non nullo, e ha una forma precisa: **troppo piatto agli estremi**. Il pareggio, invece, è sovrastimato proprio quando il modello lo dichiara alto (partite a λ basse): artefatto di ρ/τ.

**Temperatura** (p ∝ p^(1/T), T<1 = più appuntito), stimata **solo sulle stagioni precedenti** e misurata sulla stagione successiva:

| stagione di prova | n | T stimata prima | ΔRPS | IC 95% | Δlog-loss |
|---|---|---|---|---|---|
| 2024-25 | 2.332 | 0,80 | −0,00028 | [−0,00130; +0,00077] | −0,00057 |
| 2025-26 | 2.344 | 0,86 | −0,00046 | [−0,00113; +0,00023] | −0,00078 |
| 2026-27 | 348 | 0,88 | −0,00079 | [−0,00224; +0,00068] | −0,00228 |

T ottima in-sample per lega: ENG1 0,88 · ESP1 0,84 · FRA1 0,88 · GER1 0,94 · ITA1 0,86 · NED1 0,94 · POR1 0,82 — **sempre sotto 1**. DC puro 0,88; Elo puro **1,06** (l'Elo è leggermente troppo sicuro, il DC troppo prudente: la media 70/30 eredita la prudenza del DC). In pratica un 60/25/15 diventa 64/23/13; un 75/17/8 diventa 80/14/6. Gli IC per singola stagione includono lo zero; **il segno è lo stesso in tutte le prove e la dimensione è quella della promozione del tilt**: è materia da laboratorio con griglia dichiarata (§4.1), non da applicare a mano.

### 2.3 Distanza dal mercato (1.071 gare NED1/POR1 con quote di chiusura in `history.parquet`)

| | RPS | log-loss |
|---|---|---|
| modello pubblicato | 0,1871 | 0,9500 |
| **mercato (de-vig proporzionale)** | **0,1785** | **0,9198** |
| Δ modello − mercato | **+0,00853** IC [+0,00503; +0,01187] | +0,0302 |
| miscela 25% / 50% / 75% mercato | 0,1838 / 0,1813 / 0,1796 | |

NED1: 0,1910 vs 0,1805 · POR1: 0,1832 vs 0,1766. Conferma su un campione diverso il +0,0096 del benchmark del 14/09 (`benchmark_quote.py`, 4.372 gare, 7/7 leghe). **Scala di riferimento**: gli interventi interni valgono 0,0001–0,0005; il mercato sta 0,0085 più avanti.

### 2.4 Riposo (giorni dall'ultima gara di campionato, storico 3 stagioni)

| fascia | squadre-gara | gol/λ [IC ~95%] | fattore in produzione |
|---|---|---|---|
| 3 | 598 | **1,058** [0,991; 1,125] | 0,98 |
| 4-5 | 1.364 | 0,984 [0,939; 1,029] | 0,98 |
| 6-7 | 5.371 | 1,013 [0,991; 1,036] | 1,00 |
| 8-13 | 2.919 | 1,012 [0,982; 1,043] | 1,02 |
| ≥14 | 1.516 | 0,992 [0,950; 1,034] | 1,02 |

Nessuna fascia si stacca da 1; se mai chi ha 3 giorni segna **di più**, non di meno. **Il fattore di produzione applicato al backtest** (1.590 gare con λ modificate su 5.891): **ΔRPS +0,000080, IC [+0,000011; +0,000146] → peggiora, e l'IC non contiene lo zero.** Difetti di costruzione: (a) «UEFA RR 1,32» citato a sostegno è un **rischio relativo di infortunio**, non un effetto sui gol; (b) `rest_days` usa `//86400` quindi «≤2» cattura i turni di **2,9 giorni** (giovedì→domenica) e «≤4» quelli di 3-4; (c) per le gare a settimane di distanza il riposo è calcolato dall'ultima gara **giocata**, non dalla precedente in calendario: oggi **1.999 previsioni su 2.071** portano il fattore 1,02 (si annulla solo quando ce l'hanno entrambe). Con 135 gare senza il dato per una sola squadra l'asimmetria è rumore puro.

### 2.5 Valore di mercato dei titolari (337 gare finite: l'unico campione che ha il dato)

- log(rapporto valore) correla **0,88** con (p₁−p₂) del modello: il modello lo sa già; col **residuo** correla 0,14 → un po' d'informazione residua c'è.
- Griglia di k (Δlog-loss vs k=0, IC appaiato): 0,03 → −0,0044 [−0,0084; −0,0001] · 0,06 → −0,0071 [−0,0150; +0,0015] · 0,09 → −0,0083 [−0,0200; +0,0046] · **0,12 (produzione) → −0,0079 [−0,0235; +0,0091]** · 0,18 → −0,0032 · 0,25 → **+0,0082**.
- Il segnale è **promettente ma non provato**: con 337 gare l'IC del k di produzione è sette volte l'effetto. L'affermazione nel codice «k=0,12 massimizza il log-loss fuori campione su 5,7k gare con valori FotMob» è **falsa per costruzione**: `match_info.home_starters_value_eur` esiste per **371** gare (tutte di questa stagione). Il riferimento citato (world-cup-predictor, Brier 0,612→0,591) è su **nazionali al Mondiale**, dove non esiste uno storico di gare: qui il DC ha già 3 stagioni.
- Problema di coerenza: il dato compare **solo quando FotMob pubblica la formazione** (oggi 29 previsioni su 2.071 lo hanno): la probabilità **salta nell'ultimo run** prima del calcio d'inizio, e con rapporto 7,4 (AZ–Telstar) l'aggiustamento è ×1,213 → il rapporto λ casa/trasferta si sposta di **×1,47** sopra a un DC che già dava 66/21/13.

### 2.6 Assenze (137 gare con infermeria pesata)

- `contrib_lost_p90` è la **somma** degli xG+xA/90 di tutti gli assenti (anche chi non giocherebbe): mediana 0,21, p90 0,84, max **1,60** → fattore λ mediano 0,968, p90 0,874, min 0,76. Oggi Juventus **1,47 → ×0,78**: DC puro 42,7/27,8/29,5 → mostrato 34,2/28,1/37,7 → pubblicato 37,0/28,5/34,5 (l'Elo rimedia in parte). Il favorito è cambiato per un numero mai misurato.
- gol/λ per contributo perso: 0 → 1,135 · 0-0,5 → 1,132 · 0,5-1 → 0,902 [0,66; 1,14] (n=42). Un accenno nella direzione giusta, **non significativo**.
- Griglia di k: 0,1 → −0,0016 [−0,0041; +0,0012] · 0,2 → −0,0029 · **0,3 (produzione) → −0,0039 [−0,0120; +0,0051]** · 0,5 → −0,0081 [−0,0208; +0,0059]. Non distinguibile da zero.
- Difetto di modello: «preservare il totale» significa che se la Juventus perde attaccanti **l'Atalanta segna di più**. Perdere xG+xA riduce la **propria** λ; è la perdita di difensori/portiere che alza quella avversaria — e il contributo misurato è solo offensivo. La letteratura (fonti di settore, `BRIEFING` 13/09) parla di 8-15% sulla probabilità di vittoria **per un titolare chiave**, non di un fattore lineare sulla somma degli assenti.

### 2.7 Calibrazione ferma e deriva stagionale

| stagione | n | gol/gara | λ totale | **gol/λ** | 1 osservato / previsto |
|---|---|---|---|---|---|
| 2023-24 (da gen.) | 867 | 3,02 | 2,87 | 1,053 | 42,1% / 43,4% |
| 2024-25 | 2.332 | 2,82 | 2,84 | 0,994 | 42,6% / 42,8% |
| 2025-26 | 2.344 | 2,81 | 2,84 | 0,992 | 43,6% / 43,2% |
| **2026-27** | 348 | **3,14** | 2,80 | **1,124** | **39,9% / 42,9%** |

Per lega nel 2026-27: GER1 **1,42**, NED1 1,19, ITA1 1,12, ENG1 1,12, ESP1 1,10, FRA1 0,99, POR1 1,00. Con n=348 è presto per dichiararlo strutturale, ma i mercati Over/BTTS di *questa* stagione sono sistematicamente prudenti e la finestra di 730 giorni non se ne accorgerà per mesi. Nel frattempo `calibration.parquet` **non cambia dal 13/09** (commit `51ca43d`; `backtest.parquet` invece si aggiorna a ogni run): vedi §5.

---

## 3. «Ci sono altre cose che possiamo usare?» — sì, in quest'ordine

| # | Cosa | Costo | Resa attesa | Stato |
|---|---|---|---|---|
| 1 | **xG storico Understat** per le 5 grandi leghe (stagioni 2024-25 e 2025-26: 10 richieste una tantum) → candidato **`dc_xg`**: DC allenato su una miscela gol/xG (griglia dichiarata w ∈ {0,3; 0,5; 0,7}) | basso | **la più alta**: la letteratura (IJtsma, ASA, Elhabr 2024; `BRIEFING` 13/09) dà agli xG un potere predittivo superiore ai gol già da 7-10 gare, ed è informazione che il mercato usa e noi no | il candidato è già in coda (`docs/13`); mancava solo lo storico |
| 2 | **Temperatura / de-shrinkage** (§2.2): T ∈ {0,80; 0,85; 0,90; 0,95; 1,00} × `shrink_prior` ∈ {0; 4; 8} | zero | −0,0002 ÷ −0,0005 RPS | da mettere nel laboratorio con griglia dichiarata |
| 3 | **Quote di chiusura su tutte e 7 le leghe come metro** (già decisione A, `docs/19` §1.1): benchmark mensile in CI e riga «distanza dal mercato» nella pagina *Accuratezza* | zero | non migliora il modello, **misura** quanto ogni candidato chiude il divario 0,0085 | script pronto (`benchmark_quote.py`), workflow esiste, il numero non è ancora pubblicato |
| 4 | **Storico delle previsioni per run** (`predictions_log`, solo gare entro 10 giorni, ~30 righe/run) | basso | rende misurabile «la qualità peggiora con l'anticipo?» — oggi la pagina *Accuratezza* dichiara di non poterlo dire | nuovo |
| 5 | **Calibrazione con memoria corta** (peso esponenziale, emivita 90-120 giorni) accanto a quella a 730 giorni | basso | aggancia derive come il 1,124 del 2026-27 senza rincorrere il rumore | candidato di laboratorio |
| 6 | **Formazione/valore titolari come aggiornamento dell'ultima ora, dichiarato** (non dentro il DC) | medio | segnale residuo 0,14 (§2.5) ma serve ≥1.000 gare per dimostrarlo: accumulare il dato a ogni run **prima** di usarlo | i dati si stanno accumulando da settembre |
| 7 | ξ per lega (`fda lab-xi`) | zero | il laboratorio dice ξ 0,0010 ≈ 0,0018 ≈ 0,0030 (entro 0,0006): resa **bassa** | eseguire una volta, poi archiviare |
| 8 | Modelli dinamici/Bayesiani (`footBayes`, state-space) | alto (runtime jax/numpyro) | in letteratura 0,192 EPL: **non meglio** di quanto abbiamo | non ora (già P3 in `docs/13`) |
| 9 | Copula per i mercati Over/Under | basso | i mercati binari sono già entro gli intervalli dopo la calibrazione (`mercati_monitor`) | solo se il monitor esce dagli IC |

**Cosa non usare** (misurato): il riposo come fattore moltiplicativo (§2.4); la somma delle rate degli assenti (§2.6); qualunque coefficiente preso da un contesto diverso (Mondiali, Bundesliga momentum) senza rimisurarlo qui.

---

## 4. Calibrazioni da fare

### 4.1 Quantitative (modello)

1. **P0 — Ripristinare la ricetta misurata.** Le tre inclinazioni (mercato, assenze, riposo) escono da `predict_matches` finché non passano il laboratorio: il riposo perché **peggiora**, le altre due perché **non provate** e con effetti arbitrari. Restano come **candidati** con griglia dichiarata (`k_mercato ∈ {0; 0,03; 0,06; 0,09}`, `k_assenze ∈ {0; 0,1; 0,2}` **senza** preservazione del totale, riposo **escluso**) e come **spiegazione** nella card «Fattori che spostano la partita», che era già il loro posto. Se si decide di tenerle, allora: `MODEL_VERSION` nuova, calibrazione ristimata, backtest che le applica (altrimenti *Accuratezza* misura un modello che non esiste più), e la scheda che mostra i passi veri.
2. **P1 — Temperatura e shrinkage nel laboratorio** (§2.2, §1): griglia dichiarata in `Candidate.grid`; criterio di promozione quello di `docs/13` §6.5 (IC appaiato interamente negativo + migliore in ≥5 leghe su 7).
3. **P1 — `dc_xg`** appena c'è lo storico Understat (§3.1).
4. **P1 — Calibrazione fresca** (bug §5, corretto) e **con memoria corta** come secondo stimatore da confrontare (§3.5).
5. **P2 — Pareggio nel decile alto** (33,1% → 29,3%): verificare se una τ con ρ per lega o il solo `rho_shift` per lega lo corregge; altrimenti la temperatura lo attenua da sola.
6. **P2 — `xi_league`**: eseguire `lab-xi` una volta e chiudere la voce.

### 4.2 Qualitative (cosa dice la scheda)

1. **P0 — «Come nasce questa probabilità»** deve mostrare i passi **reali**: se in produzione restano correttivi pre-Elo, il passo 1 è «Dixon-Coles puro» (da salvare in colonne proprie: oggi le λ pure **non sono salvate**, `dc_lambda_*` viene sovrascritto dalle λ inclinate), poi «valore titolari ×…», «assenze ×…», «riposo ×…», poi Elo, poi calibrazione, ciascuno con Δ pp. Vale l'invariante già scritta in `docs/20`: *ogni Δ pubblicato è la differenza fra due passi stampati*.
2. **P0 — Frasi diventate false oggi** in `match.html`: «Non cambiano la previsione salvata» (card Fattori) e il tooltip «prior che migliora Brier di ~0,02» (numero di un altro dominio). Da riscrivere nella direzione della decisione presa al punto 4.1.1.
3. **P1 — «2020→2026»** nella card «Quando il favorito aveva questa forza»: il backtest parte dal **2024-01-20**. Corretto in questa sessione: l'intervallo di anni ora viene dai dati.
4. **P1 — Linguaggio dell'incertezza**: la fascia storica del favorito usa il backtest **grezzo** mentre la partita è calibrata (scarto piccolo, ma la riga «questa» può cadere nella fascia sbagliata al confine). Allineare a `calibrate_rows`.
5. **P2 — Dichiarare la stagionalità**: quando gol/λ della stagione corrente esce dall'IC (oggi 1,124), la pagina *Accuratezza* lo dice in una riga, invece di lasciarlo nel Brier dei mercati.

### 4.3 Visive e grafiche

1. **P1 — Diagramma di affidabilità per decili** in *Accuratezza* (uno per esito: punto = dichiarato, barra = Wilson 95% dell'osservato, diagonale di riferimento; la geometria di `grafico_mercati` si riusa). La tabella attuale a tre medie **non può** vedere la piattezza: 17,3→13,8 e 72,9→79,2 si compensano nella media di colonna. Stesso grafico anche per i due nuovi correttivi, se restano.
2. **P1 — RPS scorrevole nel tempo** (per mese, 7 leghe insieme e separate) con banda naive e, dove esiste, riga del mercato: rende visibile una deriva come quella di §2.7 prima che entri nelle tabelle.
3. **P2 — Scheda partita**: la «Waterfall Δ sul favorito» è la resa giusta; va solo alimentata con i passi veri (4.2.1). Nella card Fattori, ogni fattore che *entra* nel modello mostri il moltiplicatore applicato alle λ (×0,78) accanto all'impatto in pp, così il lettore vede dove nasce il numero.
4. **P2 — Palette e lettura**: già Okabe-Ito/WCAG (`docs/12`); il diagramma di affidabilità usi verde/rosso **solo** per «dentro/fuori intervallo», come il grafico dei mercati.

---

## 5. Corretto in questa sessione (piccolo, verificato, senza toccare la ricetta)

- **`daily` → `calibrate_cmd()` senza argomenti** (`cli.py`): i default `typer.Option` restavano oggetti `OptionInfo` → `TypeError: '<' not supported between instances of 'int' and 'OptionInfo'` (riprodotto chiamando la funzione: vedi `tests/test_cli_daily.py`), catturato dal `try` del daily → calibrazione mai risalvata dal 13/09 (prova: `git log` di `calibration.parquet` si ferma a `51ca43d`; `backtest.parquet` cambia a ogni run). Ora `daily` passa `min_rows=1200, folds=6, dry_run=False` e `mercati_monitor_cmd(save=True)` (quest'ultimo funzionava per caso: `OptionInfo` è truthy). Test di regressione nello stesso stile di quello che l'8/9 fissò il bug identico su `collect`.
- **`scripts/audit_modelli.py`** nuovo: sei sezioni, output in `docs/_audit_modelli.json`; rieseguibile a ogni run per rifare le misure di questo documento.
- **«2020→2026»** sostituito dagli anni reali del backtest (`favorite_track_record` pubblica `anni`).

**Non toccato di proposito** (decisione dell'utente): la ricetta di produzione (`predict_matches` e i tre correttivi), perché cambia ogni numero pubblicato e la PR #68 è stata fusa oggi dall'utente.

---

## 6. Decisioni da prendere (utente)

1. **Correttivi della PR #68**: (A, raccomandata) toglierli dalla produzione e riportarli nel laboratorio con griglia dichiarata; (B) tenerli, e allora fare subito le cinque cose del §4.1.1 perché il sito torni a dire il vero. In entrambi i casi il riposo va tolto: **peggiora**.
2. **Laboratorio di lunedì 21/09**: aggiungere ai candidati temperatura × shrinkage (§4.1.2) prima del run, così il primo verdetto con griglia pre-registrata risponde alla domanda «si può fare di meglio?» con un numero.
3. **Understat storico** (2 stagioni, 5 leghe): via libera al backfill una tantum per sbloccare `dc_xg`.

## Prossimo passo

Aprire la PR di questa sessione (audit + fix calibrazione + script + anni reali) e, ottenute le decisioni del §6, una PR **separata** per la ricetta (regola D). Il laboratorio con i nuovi candidati gira lunedì.
