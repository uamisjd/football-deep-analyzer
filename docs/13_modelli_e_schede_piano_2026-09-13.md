# Modelli di calcolo e schede partita — ricerca, misure, intervento (2026-09-13)

## Scopo

La richiesta dell'utente è su tre piani, da trattare insieme:

1. **quantitativo** — i modelli che producono le probabilità sono «abbastanza precisi e potenti»?
2. **qualitativo** — il contenuto delle analisi pre-partita e delle schede è profondo, confrontabile, onesto;
3. **visivo** — l'incertezza e i numeri si leggono bene, su tutte le 7 leghe, in italiano.

Regole del progetto che vincolano tutto il documento (`docs/00_regole_di_lavoro.md`, sez. B):
ogni miglioramento dichiarato deve essere **misurato fuori campione** (RPS / Brier / log-loss),
valere **per tutte le 7 leghe**, degradare in modo **onesto** quando il dato manca, e ogni numero
pubblicato deve essere **ricalcolabile** da `scripts/verify_site.py`. Le quote dei bookmaker non
sono un requisito e non entrano nelle schede (direttiva utente 2026-09-08).

Etichette usate per lo stato di ogni affermazione (regola B2):
**[offline]** misurato nel sandbox sui dati già nel repository;
**[live]** misurato su dati scaricati dalla rete (dal sandbox non è possibile: mirror FotMob/Understat
non raggiungibili, quindi in questa sessione non c'è nessun **[live]**);
**[presunto]** ipotesi non ancora misurata.

---

## 1. Diagnosi misurata: dove sbaglia il modello oggi

Campione: `data/processed/backtest.parquet`, **5.791 partite fuori campione** prodotte da
`fda backtest` (finestre cronologiche, il modello non ha mai visto il risultato), 7 campionati.
Strumento: `scripts/diagnose_model.py` (nuovo, ripetibile). **[offline]**

| Misura | Modello | Riferimento | Scarto |
|---|---|---|---|
| RPS 1X2 | **0,1993** | Elo puro 0,2027 · naive 45/27/28 0,2315 | il modello batte i riferimenti |
| log-loss 1X2 | 0,9869 | — | — |
| esito più probabile azzeccato | 52,3% | — | — |
| **gol totali attesi (λ)** | **3,107** | **2,862 osservati** | **+0,245 (+8,6%)** |
| bias λ per lega | da +0,16 a +0,36 | 0 | **positivo in 7 leghe su 7** |
| pareggio dichiarato | 23,9% | 25,6% osservato | **−1,7 pp** |
| Over 2,5 dichiarato | 59,0% | 54,8% osservato | +4,2 pp |
| entrambe a segno | 59,1% | 55,0% | +4,1 pp |
| porta inviolata casa | 26,1% | 28,5% | −2,4 pp |
| porta inviolata trasferta | 20,5% | 22,3% | −1,8 pp |

Lettura: **l'1X2 è a posto** (RPS 0,199 contro 0,203 dell'Elo e 0,232 del naive), ma
**tutto ciò che dipende dal numero di gol è sistematicamente gonfiato**, nella stessa direzione in
tutti e 7 i campionati. Non è rumore: su 5.791 gare un bias di +0,245 gol ha un errore standard
di circa 0,015.

### 1.1 La causa è meccanica, non statistica

`models/predict.ensemble()` media il vettore 1X2 di Dixon-Coles con quello di Elo (peso 0,7/0,3) e
poi **ricalcola le λ** dalle probabilità mediate con `penaltyblog.models.goal_expectancy`. Due
verifiche hanno isolato il difetto **[offline]**:

- la τ di Dixon-Coles non c'entra: media della griglia contro λ dichiarata, scarto **0,0003**;
- le λ «DC puro» (senza Elo) riproducono i gol osservati entro ±0,05, mentre quelle dell'ensemble
  stanno **+15/20%** sopra: il passaggio per `goal_expectancy` su un 1X2 mescolato è ciò che gonfia
  i gol attesi, e con essi Over/Under, BTTS, porte inviolate e risultati esatti.

Conseguenza progettuale: la correzione deve agire su **λ e ρ insieme** (gli unici due ingressi della
matrice), non con una temperatura sulle probabilità 1X2 — quella sposta l'1X2, che non è il problema,
e rompe la coerenza con la matrice dei punteggi mostrata in scheda.

---

## 2. Ricerca esterna (principi → decisioni)

Regola del progetto: prima di un cambiamento importante si cercano progetti open source riutilizzabili
e si registra il risultato. Fonti raggiunte dal sandbox solo via ricerca/motore (la rete è limitata a
github.com, api.github.com e PyPI): dove il fetch diretto non è riuscito è indicato.

| Evidenza | Fonte | Decisione per CalcioMetro |
|---|---|---|
| Fra le famiglie «a gol» le differenze sono piccole ma ordinate: Dixon-Coles ≈ copula di Weibull (RPS 0,19138 vs 0,19141) > Poisson ≈ zero-inflazionata (0,19154) > binomiale negativa (0,19156) > Poisson bivariata (0,19162); ~4 stagioni di storico è l'orizzonte migliore; ξ (decadimento temporale) va tarato per lega (Eredivisie 2023/24: 0,191 → 0,189 con ξ=0,001). | pena.lt, *«Which model should you use»*, 10/03/2025 (autore di `penaltyblog`; fetch diretto 404, contenuto letto via ricerca) | Il laboratorio confronta **tutte** queste famiglie con la stessa procedura walk-forward, invece di sceglierne una sulla fiducia. `xi` e `shrink_prior` diventano candidati espliciti (`dc_xi10`, `dc_xi30`, `dc_no_shrink`, `dc_shrink16`). |
| La famiglia migliore **cambia per lega e per periodo** (DC prima in Bundesliga, COMP prima in Premier in alcune stagioni); ξ ottimale ≈0,0021 EPL, ≈0,0015 Bundesliga. | opisthokonta.net (analisi di Friske su DC/COMP/Poisson) | `fda lab --league-keys` e la tabella `per_league`: nessuna decisione «una lega vale l'altra»; la parità richiesta dall'utente si verifica leggendo i numeri per lega. |
| Con modelli statistici moderni la scelta esatta di feature/modello ha **influenza minore** di quanto si pensi, e i livelli di prestazione delle squadre non cambiano sistematicamente dentro la stagione. | Fischer & Heuer, [arXiv:2408.08331](https://arxiv.org/abs/2408.08331) (letto) | Niente corsa al machine learning: prima si corregge il difetto misurato (calibrazione), poi si confrontano famiglie semplici con un protocollo serio. |
| La copula di Weibull (Mar-Co) batte Dixon-Coles soprattutto su Over/Under, perché in DC ρ non può cambiare le probabilità di Over/Under. | [arXiv:2103.07272](https://arxiv.org/abs/2103.07272) | Candidato `weibull_copula` nel laboratorio; è il primo sostituto strutturale da provare se i mercati sui gol restano distorti dopo la calibrazione. |
| Modelli dinamici/gerarchici: Rue & Salvesen (2000) GLM dinamico; Koopman & Lit state-space; Egidi et al. (2018) con le quote; Baio & Blangiardo (2010) gerarchico (con il noto rischio di over-shrinkage); pacchetto R `footBayes` (preprint 2026: precisioni variabili nel tempo per squadra, spike-and-slab; DC dinamico pesato RPS 0,192 EPL / 0,146 LaLiga); JRSS-C 74(3): binomiale negativa bivariata leggermente meglio del Poisson indipendente e shrinkage κ delle probabilità estreme utile. | riferimenti bibliografici (non raggiunti dal sandbox: niente PDF/arXiv fuori dalla whitelist, salvo 2408.08331) | **Non ora**: richiedono runtime Bayesiane (`numpyro`/`jax`, oggi non installate) e un flusso di verifica più lungo. Restano il piano P3, con l'avvertenza che il mercato delle quote resta davanti a metà stagione. |
| Gli xG predicono i punti futuri meglio dei punti stessi già dopo ~8 giornate (replicazioni IJtsma/American Soccer Analysis; Elhabr 2024: rapporto xG+xAG affidabile già a 7-10 gare, xGOT peggio di xG); una regressione di Poisson in cross-validation predice meglio i gol futuri dalla media xG che dalla media gol. | americansocceranalysis.com, Tony Elhabr (2024), Medium (2022) — via ricerca | **P2**: usare gli xG di stagione (Understat per le big-5, `team_stats` FotMob per NED1/POR1) come covariata o come λ alternativa. Oggi lo storico xG nel repo copre solo la stagione corrente, quindi serve prima un accumulo (`understat_team_matches`). |
| Ensembling e calibrazione sono le raccomandazioni ricorrenti nelle competizioni accademiche; il Poisson log-linear gerarchico ≈ il miglior Bradley-Terry. | Hubáček & Groll, *Machine Learning and Knowledge Discovery in Databases* (MLS 2017 challenge), [doi:10.1007/s10994-018-5741-1](https://doi.org/10.1007/s10994-018-5741-1); Journal of Big Data 2024 (Eredivisie: FNN/voting migliori, regressione logistica migliore su U/O 2,5) | La miscela resta, ma **nella griglia dei punteggi** (`_mix_grids`: si invertono le λ con `goal_expectancy` e si mescolano le matrici), non solo sul vettore 1X2 — così anche i mercati restano coerenti. Candidati `mix_50`, `mix_85` e stacking convesso (`convex_weights`). |
| In-play: intensità stocastiche temporali con gol/espulsioni/xT (RPS aggregato 0,1338); Weibull-AFT con PSxG e forme specifiche per tempo (RPS 0,1294); espulsione −30% di intensità, squadra in rimonta +10/20%. | Robberechts et al., KDD 2021; [arXiv:2605.16066](https://arxiv.org/abs/2605.16066); Maia 2025 (Cox) — via ricerca | Fuori perimetro ora: il sito è statico e la nostra curva in-play è dichiarata come ricostruzione, non come live feed. Resta un candidato P3 con dati FotMob già raccolti (`events`, `momentum`). |
| Assenze e infortuni: l'effetto dichiarato dai blog di settore è ~8-15% di spostamento sulla probabilità di vittoria e un xGA più alto quando mancano difensori, ma **non è stata trovata una fonte accademica solida**. | blog di settore (sportbotai e simili) — qualità bassa | Se si userà, andrà etichettato **[presunto]** e misurato prima di pubblicarlo. Oggi l'infermeria in scheda è descrittiva (minuti, xG+xA persi), non entra nel modello. |
| Comunicazione dell'incertezza: i **quantile dotplot** hanno varianza di lettura ~1,15× più bassa delle densità e sfruttano il subitizing fino a ~5 punti; il framing a frequenze («1 su 10») batte le percentuali per lettori non esperti; palette colorblind-safe (Okabe-Ito/viridis) e contrasto WCAG 4,5:1; mai codificare solo col colore. | Kay et al. CHI 2016; Hullman et al. IEEE TVCG 2015; [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Le due nuove viste della scheda (sez. 4): barre in «partite su 100» e dotplot a 20 punti, con numeri scritti accanto al colore e `aria-label` testuali. |
| Libreria riusabile già a progetto: `penaltyblog` (Dixon-Coles, Poisson, binomiale negativa, zero-inflazionata, Poisson bivariata, copula di Weibull, Elo, Pi-ratings) con API uniforme `fit()/predict()`; tempi di fit su 720 gare: DC/Poisson/NegBin/ZIP ~0,02 s, Poisson bivariata 0,07 s, **copula di Weibull 1,23 s**. | [github.com/martin-eastswood/penaltyblog](https://github.com/martin-eastswood/penaltyblog) (dipendenza già in `pyproject.toml`) | Nessuna dipendenza nuova (niente `numpyro`/`jax`). Attenzione nota: `create_dixon_coles_grid` di penaltyblog ha le celle τ scambiate → si usa solo `models/dc_grid.py` del progetto. Il costo della copula di Weibull è il motivo per cui il laboratorio **non** sta nel run giornaliero. |

---

## 3. Intervento quantitativo: calibrazione della griglia (implementato)

### 3.1 Che cosa fa

`models/calibration.py` sceglie su griglia il paio **(moltiplicatore delle λ, spostamento di ρ)** che
minimizza `RPS + 0,5 · Brier(mercati)` sulle partite **fuori campione** del backtest:

- griglia: λ × 0,88…1,02 (passo 0,01), Δρ −0,08…0,00 (passo 0,01);
- la correzione è applicata a **λ e ρ**, poi l'intera previsione (1X2, doppia chance, risultati esatti,
  Over/Under, BTTS, porte inviolate) è **ripubblicata dalla griglia corretta**: una sola superficie di
  probabilità, coerente con la matrice mostrata in scheda;
- valutazione **walk-forward a 4 fold cronologici**: il guadagno dichiarato non è in-sample;
- soglia di sicurezza: sotto **1.200 partite** di backtest non si corregge nulla (identità);
- `models/dc_grid.py` ha ricevuto le versioni vettorizzate (`tau_grid_many`, `grid_markets_many`,
  `clamp_rho_many`): stessa formula della scalare, verificata cella per cella nei test, e migliaia di
  righe corrette in pochi secondi (fit completo: **3,2 s**);
- CLI: **`fda calibrate [--dry-run]`**, che stampa prima/dopo e salva la tabella `calibration`
  (versione `grid-cal-1.0`); `fda predict` applica l'ultima calibrazione salvata e scrive nella riga
  `lambda_scale`, `rho_shift`, `calibration_version`, `calibration_n_fit` e i valori grezzi
  (`lambda_home_raw`, `lambda_away_raw`, `rho_raw`, `blend_p_*`) — ogni numero pubblicato resta
  riconducibile alla versione che lo ha prodotto;
- `fda daily` ora esegue **collect → calibrate → predict → backtest → simulate → build**: si calibra
  sui dati del run precedente (solo passato) e si pubblica subito; se `calibrate` fallisce il run
  degrada al modello grezzo invece di bloccarsi. La simulazione di stagione usa la stessa
  calibrazione delle schede (altrimenti «Proiezioni» e «Analisi» racconterebbero due campionati).

### 3.2 Risultati misurati **[offline, su `backtest.parquet` reale]**

Parametri scelti: **λ × 0,94 · Δρ −0,04**.

| Misura | Prima | Dopo | Lettura |
|---|---|---|---|
| bias λ (gol totali) | +0,245 | **+0,058** | il difetto principale è ridotto di ~4× |
| pareggio dichiarato | 23,9% | **25,7%** (osservato 25,6%) | dentro l'intervallo |
| Brier mercati, **walk-forward** (4.825 gare tenute fuori) | 0,2065 | **0,2055** | −0,0010: piccolo ma nella direzione giusta e misurato onestamente |
| RPS 1X2, walk-forward | 0,2006 | 0,2007 | +0,0001: **invariato entro il rumore** |

Il punto da comunicare senza sconti: **l'1X2 è al pavimento informativo** di questa famiglia di modelli
(±0,0001…0,0004 su RPS). Ricalibrare non lo migliora; migliora la coerenza dei gol e dei mercati, che
è dove il modello dichiarava numeri sbagliati. Per guadagnare sull'1X2 serve **informazione nuova**
(xG storici, assenze pesate) o un **modello strutturale diverso** (copula, dinamica temporale): è il
compito del laboratorio, non della calibrazione.

---

## 4. Intervento visivo e qualitativo sulle schede (implementato)

Due blocchi nuovi nella scheda partita, entrambi derivati **solo** dai numeri già pubblicati
(λ, ρ, vettori 1X2 salvati nella riga di previsione) e ricalcolati da `verify_site.py`.

### 4.1 «Quanti gol, in pratica» — distribuzione dei gol totali + dotplot quantile

- la matrice Dixon-Coles letta per **totale dei gol**: barre 0…6 gol più la coda «7+»;
- le etichette sono **partite su 100** e sommano esattamente 100 (metodo del resto massimo:
  arrotondare per conto suo darebbe 99 o 101 e la scheda smetterebbe di tornare a occhio);
- **quantile dotplot a 20 punti**, 1 punto = 5 partite su 100, asse allineato con l'istogramma;
- didascalia con moda, mediana e intervallo 10-90% («nel 90% dei casi il totale resta fra 1 e 5 gol»);
- perché questa forma: le frequenze discrete si leggono meglio di una densità continua e non invitano
  a cercare un valore «vero» dove c'è una distribuzione (Kay/Hullman); il valore numerico è scritto,
  quindi il significato non passa solo dal colore; `role="img"` + `aria-label` elencano tutti i valori.

### 4.2 «Come nasce questa probabilità» — scomposizione della catena

| Passo | Da dove viene | Esempio |
|---|---|---|
| 1 · Modello sui gol (Dixon-Coles) | nuove colonne `dc_p_*` salvate in previsione | 46,1 / 26,8 / 27,0 |
| 2 · Media con i rating Elo | `blend_p_*` (media pesata 0,7/0,3 già salvata dalla calibrazione) | 48,0 / 26,1 / 25,9 (Δ +1,9 pp) |
| 3 · Calibrazione | `p_*` pubblicati, con la nota «λ × 0,94 stimata su 5.791 gare fuori campione» | 46,9 / 27,4 / 25,7 (Δ −1,1 pp) |

Ogni barra è un vettore 1X2 **realmente calcolato e salvato**, non una ricostruzione a posteriori; se
un passaggio non è tracciato nei dati (righe prodotte prima di questa modifica) il blocco mostra solo
i passi esistenti, e se i passi sono identici o incoerenti (somma ≠ 1) il blocco non compare: meglio
nessun grafico che un grafico sbagliato. Le λ non finite (NaN dello store) ora fanno sparire sia la
matrice sia la distribuzione invece di stampare valori NaN — difetto trovato scrivendo il test.

### 4.3 Coerenza e verificabilità

- `scripts/verify_site.py` ha due passi nuovi: **[9]** ricalcola barre, etichette, somma 100, dotplot,
  moda/mediana/intervallo e coda dalle λ/ρ salvate (138 schede verificate); **[10]** ricalcola i passi
  della catena e controlla che l'ultimo passo coincida con l'1X2 pubblicato in cima alla scheda
  (138 schede). Esito sull'anteprima locale: **4.088 pagine, 0 problemi**.
- le righe per mercato della pagina **Accuratezza** pubblicano ora `(k/n)` come quelle di calibrazione:
  il verificatore prima ricostruiva `k` dalla percentuale arrotondata e segnalava **2 falsi problemi**
  (intervallo 53,6–56,1% contro 53,5–56,1%). Ora confronta i conteggi veri.

---

## 5. Laboratorio modelli (implementato, primo giro reale in Actions)

`models/lab.py` + **`fda lab`**: confronto **walk-forward** fra famiglie di modelli, iperparametri e
miscele, con la stessa procedura per tutti e nessuna informazione dal futuro.

### 5.1 Candidati (15)

| chiave | tipo | famiglia | che cosa mette alla prova |
|---|---|---|---|
| `dc_elo_prod` | production | Dixon-Coles | **baseline**: ciò che il sito pubblica oggi (w 0,7) |
| `dc_puro` | goals | Dixon-Coles | quanto vale l'Elo aggiunto |
| `dc_xi10` / `dc_xi30` | goals | Dixon-Coles | memoria lunga (ξ 0,0010) vs corta (ξ 0,0030) |
| `dc_no_shrink` / `dc_shrink16` | goals | Dixon-Coles | shrinkage verso la media di lega: 0 vs 16 |
| `poisson` | goals | Poisson | riferimento minimo |
| `biv_poisson` | goals | Poisson bivariata | correlazione senza τ di Dixon-Coles |
| `neg_binomial` | goals | binomiale negativa | sovradispersione dei gol |
| `zero_inflated` | goals | Poisson zero-inflazionata | eccesso di 0-0 |
| `weibull_copula` | goals | Weibull + copula | struttura che in DC manca su Over/Under |
| `elo` | rating | Elo | solo rating (k 20, vantaggio casa 60) |
| `pi_ratings` | rating | Pi-ratings | rating di Constantinou-Fenton |
| `mix_50` / `mix_85` | blend | Dixon-Coles | miscela **nella griglia** (λ invertite con `goal_expectancy`, matrici mescolate) al 50% e all'85% di DC |

Più `convex_weights()`: stacking convesso dei vettori 1X2 (Nelder-Mead, nessuna dipendenza nuova),
per sapere se una combinazione pesata batte il migliore dei singoli.

### 5.2 Protocollo

- finestre cronologiche per lega: si allena su tutto ciò che precede il taglio e si valuta sulle gare
  della finestra (default 28 giorni, minimo 600 partite di storico); il test `SpyDC`-style
  (`tests/test_lab.py`) verifica che **nessun fit veda una data successiva alle gare che valuta**;
- metriche per candidato: **RPS**, log-loss, Brier 1X2 e dei mercati, esito azzeccato, bias delle λ,
  quota di gare in cui è il migliore/il peggiore;
- **bootstrap appaiato a 95%** sulla differenza di RPS rispetto alla baseline, **sullo stesso insieme
  di partite**: se l'intervallo include 0, la differenza è rumore e non si cambia modello;
- tabella per lega (`per_league`) per la parità richiesta fra i 7 campionati;
- output: tabella in console + `data/processed/model_lab.parquet` (chiavi `candidate`, `league_key`).

### 5.3 Primo giro eseguito dal sandbox **[offline, corpus surrogato — indicativo]**

Nel sandbox i mirror dei dati storici non sono raggiungibili, quindi il laboratorio è stato provato su
uno storico **ricostruito** da `data/processed/h2h.parquet` (`scripts/corpus_da_h2h.py`: 4.803 partite,
7 leghe, dal 2014). Quel corpus è **distorto** (sottostima i gol di ~10%: è un campione di precedenti,
non un calendario completo): i numeri qui sotto dimostrano che il meccanismo funziona, **non** dicono
quale modello scegliere. La scelta va presa sul primo giro in Actions con `history.parquet` reale.

6 candidati, `--min-train 300 --step-days 120`, 6 finestre, **783 partite valutate in 59 s**:

| candidato | RPS | Δ RPS vs baseline | IC 95% appaiato | esito azzeccato | bias λ |
|---|---|---|---|---|---|
| `dc_elo_prod` (baseline) | **0,2036** | 0,0000 | — | 52,1% | +0,159 |
| `mix_50` | 0,2038 | +0,0002 | [−0,0005; +0,0008] | 52,6% | +0,652 |
| `dc_puro` | 0,2040 | +0,0004 | [−0,0006; +0,0014] | 52,5% | −0,203 |
| `elo` | 0,2057 | +0,0021 | [−0,0003; +0,0045] | 51,9% | — |
| `neg_binomial` | 0,2058 | +0,0022 | [−0,0029; +0,0071] | 52,1% | +0,041 |
| `poisson` | 0,2058 | +0,0022 | [−0,0029; +0,0071] | 52,1% | +0,041 |

Lettura onesta: **nessuna differenza significativa** su questo corpus (tutti gli IC contengono lo 0).
È esattamente il comportamento atteso e il motivo per cui il laboratorio esiste: senza IC appaiati si
sarebbe potuto «promuovere» `mix_50` o `dc_puro` su 0,0002 di RPS.

### 5.4 Come gira in produzione

`.github/workflows/lab.yml`: lunedì **05:30 IT** e a richiesta (`workflow_dispatch` con finestra,
storico minimo, candidati e campionati regolabili). Legge `data/processed/history.parquet`, che da
questa modifica viene **salvato a ogni run** da `fda simulate` (`persist_history`, snapshot per lega):
così il laboratorio gira offline, sullo storico vero su cui sono state addestrate le previsioni
pubblicate, e ogni numero resta riproducibile. Se il file manca, il passo si ferma con un messaggio
esplicito invece di inventare dati. Finestre da **90 giorni** (non 28) per restare entro ~10 minuti:
il collo di bottiglia è la copula di Weibull (~1,2 s per fit su 720 gare). Il laboratorio **non** sta
nel `daily`.

---

## 6. Criteri di accettazione (da verificare dopo il merge)

1. **[live]** `fda calibrate` nel run giornaliero produce una calibrazione con `n_fit ≥ 1.200` e
   `bias_lambda` del campione pieno **< 0,10 gol** (oggi +0,058 sul backtest);
2. **[live]** nella pagina Accuratezza il pareggio dichiarato cade **dentro** l'intervallo di Wilson
   e Over 2,5 / BTTS si avvicinano all'osservato (scarto < 2 pp);
3. **[live]** Brier mercati del backtest successivo **non peggiora** oltre 0,0005 rispetto a 0,2065;
4. **[live]** `history.parquet` compare in `data/processed` dopo il primo run con `fda simulate`;
5. **[live]** il primo `lab` in Actions pubblica `model_lab.parquet` con ≥ 1.000 partite valutate per
   candidato e 7 leghe; si cambia modello **solo** se un candidato batte `dc_elo_prod` con IC 95%
   appaiato interamente negativo, e solo se il vantaggio vale in almeno 5 leghe su 7;
6. **[offline, già verificato]** suite **150 passed**, `ruff --select F,E9` pulito, `fda build`
   (376 schede / 2.364 fixture / 7.394 giocatori), `scripts/verify_site.py` **4.088 pagine · 0 problemi**
   con i nuovi controlli [9] e [10];
7. ogni blocco nuovo compare **in tutte le 7 leghe** (la distribuzione dei gol dipende solo da λ/ρ,
   che esistono per ogni partita prevista: 138/138 schede verificate nell'anteprima).

---

## 7. Prossimi passi (in ordine di valore atteso per punto di sforzo)

**P2 — informazione nuova (l'unico modo di muovere l'1X2)**
1. **xG storici cumulati**: `understat_team_matches` esiste ma copre la stagione corrente; serve un
   accumulo run dopo run e poi un candidato `dc_xg` (λ stimate dagli xG invece che dai gol). Attesa
   dalla letteratura: riduzione del rumore di finishing, non miracoli (MSE 1,35 vs 1,38 sulla
   previsione dei gol futuri).
2. **ξ per lega** (`dc_xi10`/`dc_xi30` già nel laboratorio): se il primo giro reale mostra un
   vantaggio per lega stabile, `fda predict` prende ξ da una tabella per lega invece che un valore unico.
3. **Assenze pesate**: oggi l'infermeria è descrittiva. Prima di farla entrare nel modello serve una
   misura (effetto su xGA/xG per ruolo) altrimenti resta **[presunto]**.

**P3 — struttura del modello**
4. Copula di Weibull come generatore dei mercati sui gol (1X2 da DC, Over/Under dalla copula), se il
   laboratorio conferma il vantaggio su quei mercati.
5. Dinamica temporale (Rue-Salvesen / state-space / `footBayes`): richiede runtime Bayesiane,
   quindi una valutazione di costo runtime in Actions prima di qualsiasi impegno.
6. Shrinkage delle probabilità estreme (κ del JRSS-C) come alternativa alla calibrazione attuale.

**Qualità editoriale e visiva (nessun modello nuovo richiesto)**
7. Pagina **Accuratezza**: pubblicare la tabella del laboratorio (migliore/peggiore per lega, IC
   appaiati) così la scelta del modello è leggibile da chi usa il sito.
8. Proiezioni di stagione: dotplot dei punti finali invece della sola media (stessa grammatica visiva
   delle schede, coerenza fra pagine).
9. Scheda: lettura in frequenza anche per l'1X2 («su 100 partite così: 47 vittorie, 27 pareggi,
   26 sconfitte») accanto alle percentuali, mantenendo il margine sul secondo esito.

**Fuori perimetro (direttive utente)**: quote dei bookmaker come contenuto delle schede; live feed.

---

## 8. File toccati in questo intervento

| File | Che cosa contiene |
|---|---|
| `src/fda/models/calibration.py` | griglia (m, Δρ), fit walk-forward, `evaluate`, `from_store`, `apply_many` |
| `src/fda/models/dc_grid.py` | `tau_grid_many`, `clamp_rho_many`, `grid_markets_many` (vettorizzati) |
| `src/fda/models/lab.py` | candidati, `walk_forward`, `_mix_grids`, `summarize` (bootstrap appaiato), `per_league`, `convex_weights` |
| `src/fda/models/predict.py` | `calibrated_prediction`, `dc_p_*` salvati, `MODEL_VERSION` `dc-elo-ens-0.3` |
| `src/fda/models/season_sim.py` | `persist_history`, calibrazione dentro `_match_grid`/`simulate_league`/`simulate_all` |
| `src/fda/cli.py` | `fda calibrate`, `fda lab`, ordine del `daily`, storico salvato da `predict`/`backtest` |
| `src/fda/store.py` | chiavi delle tabelle `history`, `calibration`, `model_lab` |
| `src/fda/site/advanced.py` | `goals_view`, `probability_steps`, `_per_cento` |
| `src/fda/site/analysis.py` | `_lambdas` (NaN → nessun blocco), wrapper `goals_view` |
| `src/fda/site/templates/match.html`, `base.html` | i due blocchi nuovi + CSS |
| `src/fda/models/backtest.py`, `src/fda/site/build.py`, `templates/accuracy.html` | `(k/n)` pubblicato per mercato |
| `scripts/diagnose_model.py`, `scripts/corpus_da_h2h.py`, `scripts/anteprima_scheda.py`, `scripts/verify_site.py` | diagnosi, corpus offline, anteprima locale, controlli [9]/[10] |
| `.github/workflows/lab.yml` | laboratorio settimanale su storico reale |
| `tests/test_calibration.py`, `tests/test_lab.py`, `tests/test_advanced.py`, `tests/test_season_sim.py` | 32 test nuovi (suite a **150**) |
