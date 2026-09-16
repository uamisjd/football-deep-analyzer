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
- le λ del **solo modello sui gol** — ricostruite invertendo il suo 1X2 (`dc_p_*`, già salvato in
  ogni riga) con la stessa `goal_expectancy`, su tutte le 5.791 gare — valgono in media **2,730**
  gol contro **2,862** osservati (−0,13: leggermente *sotto*, non sopra), mentre quelle pubblicate
  dall'ensemble valgono **3,107** (+0,245). Il rapporto invertite/DC è **1,14 in media, 1,28 al p95,
  1,35 al p99, 1,55 al massimo**: il passaggio per `goal_expectancy` su un 1X2 mescolato è ciò che
  gonfia i gol attesi, e con essi Over/Under, BTTS, porte inviolate e risultati esatti. Ne segue che
  il moltiplicatore di calibrazione 0,9135 sta *annullando quasi esattamente* quel rapporto
  (1,14 × 0,9135 = 1,04): è un tampone globale a un difetto locale, ed è il motivo per cui il
  candidato `dc_elo_tilt` (§5.1) e i limiti di sicurezza (§3.3) contano più della calibrazione stessa.

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

### 3.1 Che cosa fa (versione 1.1, stimatore a momenti)

`models/calibration.py` stima il paio **(moltiplicatore delle λ, spostamento di ρ)** sulle partite
**fuori campione** del backtest. Dalla versione `cal-momenti-1.1` il moltiplicatore **non** esce più da
una griglia di punteggio: è stimato per **uguaglianza dei momenti**, cioè

    m = gol osservati / gol attesi dalla griglia     (finestra: ultimi 730 giorni)

perché il difetto da correggere è un *livello* (le λ gonfiate), e una griglia con passo 0,01 su una
funzione obiettivo piatta sceglie quasi a caso fra 0,93 e 0,95: il valore pubblicato era quindi meno
preciso del fenomeno che doveva correggere. Misurato: la griglia di punteggio, sullo stesso campione,
sceglie 0,94 contro **0,9135** dei momenti, e la differenza si vede tutta sul bias dei gol
(+0,128 contro **+0,053** fuori campione). Lo spostamento di ρ resta su griglia (−0,06…+0,02, passo
0,02) perché agisce sulla massa del pareggio, che non ha un momento chiuso altrettanto diretto.

- finestra di stima: **ultimi 730 giorni** (`FIT_WINDOW_DAYS`), scelta misurando il bias per
  semestre: `m` vale 0,963 / 0,935 / 0,881 / 0,917 / 0,902 / 1,034, cioè il fenomeno **non è
  stazionario** e stimarlo su tutto lo storico mescola regimi diversi. 730 giorni è il compromesso
  misurato fra aderenza al regime corrente (4.743 gare) e rumore (365 giorni dà lo stesso Brier ma
  metà campione);
- limiti di sicurezza `SCALE_BOUNDS = (0,85; 1,05)`: se la finestra chiedesse una correzione più
  forte, significa che è cambiato il modello o il dato, non il calcio — si applica il limite e si
  avvisa nel log;
- la correzione è applicata a **λ e ρ**, poi l'intera previsione (1X2, doppia chance, risultati esatti,
  Over/Under, BTTS, porte inviolate) è **ripubblicata dalla griglia corretta**: una sola superficie di
  probabilità, coerente con la matrice mostrata in scheda;
- valutazione **walk-forward a 6 fold cronologici** (`FOLDS`): il guadagno dichiarato non è in-sample;
- soglia di sicurezza: sotto **1.200 partite** (`MIN_ROWS`) di backtest non si corregge nulla (identità);
- guardia sul residuo: se dopo la correzione il bias λ walk-forward resta sopra **0,10 gol** il fit
  avvisa nel log (la calibrazione non deve nascondere un difetto strutturale);
- `as_row` arrotonda λ e ρ a **6 decimali** (prima 4: con un moltiplicatore continuo il giro
  parquet→memoria non restituiva più lo stesso numero);
- `models/dc_grid.py` ha le versioni vettorizzate (`tau_grid_many`, `grid_markets_many`,
  `clamp_rho_many`) e ora anche **`GRID_SIZE = 11` come unica costante condivisa**: modelli,
  laboratorio, calibrazione e schede usano la stessa matrice. Prima `calibrated_prediction` pubblicava
  da una 10×10 mentre la calibrazione era stimata su una 11×11 (differenza misurata ~4e-7 su una
  probabilità: piccola, ma era ottimizzare una superficie e mostrarne un'altra);
- CLI: **`fda calibrate [--dry-run]`**, che stampa stimatore, finestra, confronto con la scelta su
  griglia, prima/dopo e salva la tabella `calibration` (versione `cal-momenti-1.1`); `fda predict`
  applica l'ultima calibrazione salvata e scrive nella riga `lambda_scale`, `rho_shift`,
  `calibration_version`, `calibration_n_fit` e i valori grezzi (`lambda_home_raw`, `lambda_away_raw`,
  `rho_raw`, `blend_p_*`) — ogni numero pubblicato resta riconducibile alla versione che lo ha prodotto;
- `fda daily` esegue **collect → calibrate → predict → backtest → simulate → build**: si calibra sui
  dati del run precedente (solo passato) e si pubblica subito; se `calibrate` fallisce il run degrada
  al modello grezzo invece di bloccarsi.

### 3.2 Risultati misurati **[offline, su `backtest.parquet` reale: 5.791 gare fuori campione, 7 leghe]**

Parametri pubblicati: **λ × 0,9135 · Δρ −0,04** (`cal-momenti-1.1`, stimati su 4.743 gare degli
ultimi 730 giorni).

| Misura | Identità | Griglia 0,94 (v1.0) | **Momenti 730 gg (v1.1)** |
|---|---|---|---|
| Brier mercati, walk-forward (4.825 gare tenute fuori) | 0,20646 | 0,20548 | **0,20516** |
| RPS 1X2, walk-forward | **0,20056** | 0,20070 | 0,20081 |
| bias λ fuori campione | +0,264 | +0,128 | **+0,053** |
| bias λ sul campione pieno | +0,245 | +0,058 | **−0,024** |
| pareggio previsto (osservato 25,6%) | 23,9% | 25,7% | **26,2%** |
| Brier 9 mercati, campione pieno | 0,2025 | — | **0,2017** |

Scelte e rinunce, senza sconti:

- **l'1X2 è al pavimento informativo** di questa famiglia di modelli: la calibrazione lo peggiora di
  +0,0003 RPS (0,20056 → 0,20081) mentre migliora Brier mercati di −0,0013 e azzera il bias dei gol.
  Il compromesso è deliberato: i mercati e i gol attesi sono ciò che la scheda *dichiara* in decine di
  punti (Over/Under, BTTS, risultati esatti, «quanti gol in pratica», proiezioni), l'RPS 1X2 è una
  metrica sola. La pagina Accuratezza mostra entrambi i numeri e il confronto «senza calibrazione»;
- per guadagnare sull'1X2 serve **informazione nuova** (xG storici, assenze pesate) o un **modello
  strutturale diverso** (copula, dinamica temporale): è il compito del laboratorio (§5);
- la calibrazione **per lega** è stata misurata e **scartata**: guadagno sul Brier 0,20510 contro
  0,20514 globale, cioè rumore, a fronte di 7 parametri in più da stimare su campioni da 300-900 gare.

### 3.3 Limiti di sicurezza sulle λ invertite (nuovo, misurato)

> **Aggiornamento 2026-09-13:** la produzione non inverte più due λ libere dall'1X2 mediato
> (`docs/15`): l'Elo inclina e il totale dei gol attesi resta quello del modello sui gol, quindi
> il difetto descritto qui non si forma più (0,05% di gare toccate contro l'1,2%). I limiti
> restano, valgono anche **dopo** la calibrazione (che ora moltiplica: λ×1,04) e continuano a
> proteggere la ricetta `inverti`, rimasta in laboratorio come candidato `dc_elo_ge`.

`ensemble()` ricava le λ della griglia pubblicata **invertendo l'1X2 mediato** con
`pb.models.goal_expectancy`, che risolve due λ libere senza alcun vincolo. Quando l'Elo spinge il
vettore verso esiti estremi (pareggio al 5-6%) l'unico modo di riprodurlo è gonfiare i gol attesi:

- misurato sul backtest reale: il modello sui gol **da solo** non supera mai λ 3,84 per squadra né
  4,73 totali (media 2,730); dopo l'inversione la media è 3,107, il p99 4,82, il massimo **6,77**;
  il rapporto invertite/DC è 1,14 in media, 1,28 al p95, 1,35 al p99, **1,55** al massimo;
- sulle previsioni pubblicate (`predictions.parquet`) il caso limite è
  **Barcellona-Racing Santander λ 6,17 + 2,25 = 8,4 gol attesi**: Over 2,5 al 99%, risultati esatti
  centrati sul 5-1. Numeri che un lettore riconosce come assurdi e che trascinano con sé ogni mercato
  derivato e la matrice mostrata in scheda.

Correzione (`LAMBDA_MAX = 4,0`, `LAMBDA_TOTAL_MAX_REL = 1,35`, `LAMBDA_TOTAL_MIN_REL = 0,70`,
`LAMBDA_TOTAL_MAX_ABS = 5,5`): il totale resta fra il 70% e il 135% di quello del modello sui gol e
sotto il tetto assoluto, ogni λ sotto 4,0, **l'inclinazione casa/trasferta si conserva** (si scala il
totale). Quando il limite lega, l'1X2 pubblicato è quello della griglia limitata, non il vettore
mediato irraggiungibile: la scheda resta coerente con se stessa (e `lambda_limitata` lo registra).

Effetto misurato sulle 5.791 gare fuori campione:

| Misura | Prima | Dopo |
|---|---|---|
| gare toccate | — | **69 (1,19%)**, in tutte e 7 le leghe (POR1 21, NED1 15, ITA1 9, GER1 7, FRA1 7, ENG1 6, ESP1 4) |
| λ massima per squadra | 5,09 | **4,00** |
| λ totali massime | 6,77 | **5,49** |
| RPS / logloss (tutte le gare) | 0,1993 / 0,9869 | 0,1993 / 0,9869 (**invariati**) |
| bias λ (tutte le gare) | +0,245 | **+0,242** |
| sulle 69 gare toccate: logloss | 0,5676 | **0,5664** |
| sulle 69 gare toccate: Brier 9 mercati | 0,1471 | **0,1450** |
| sulle 69 gare toccate: bias λ (poi calibrato) | +0,791 (+0,395) | **+0,561 (+0,184)** |
| sulle 69 gare toccate: pareggio previsto (osservato 10,1%) | 12,3% | **13,0%** |

Nessun costo in accuratezza, mercati migliori proprio dove il modello esagerava, e nessuna scheda che
promette otto gol. La stessa protezione è applicata dentro `_mix_grids` del laboratorio (§5.2).

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
| 3 · Calibrazione | `p_*` pubblicati, con la nota «λ × 0,91 (momenti, ultimi 730 giorni) stimata su 4.743 gare fuori campione» — stimatore e finestra sono scritti nella riga di previsione (`calibration_estimator`, `calibration_window_days`) | 46,9 / 27,4 / 25,7 (Δ −1,1 pp) |

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

### 5.1 Candidati (22)

| chiave | tipo | famiglia | che cosa mette alla prova |
|---|---|---|---|
| `dc_elo_prod` | production | Dixon-Coles | **baseline**: ciò che il sito pubblica oggi (w 0,7, ricetta `tilt` dal 2026-09-13) |
| `dc_puro` | goals | Dixon-Coles | quanto vale l'Elo aggiunto |
| `dc_xi10` / `dc_xi30` | goals | Dixon-Coles | memoria lunga (ξ 0,0010) vs corta (ξ 0,0030) |
| `dc_no_shrink` / `dc_shrink16` | goals | Dixon-Coles | shrinkage verso la media di lega: 0 vs 16 |
| `poisson` | goals | Poisson | riferimento minimo |
| `biv_poisson` | goals | Poisson bivariata | correlazione senza τ di Dixon-Coles |
| `neg_binomial` | goals | binomiale negativa | sovradispersione dei gol |
| `zero_inflated` | goals | Poisson zero-inflazionata | eccesso di 0-0 |
| `weibull_copula` | goals | Weibull + copula | struttura che in DC manca su Over/Under |
| `elo` | rating | Elo (k 20, HFA 60) | solo rating, con i default di penaltyblog |
| **`elo_k10` / `elo_k40`** | rating | Elo | **nuovo**: reattività del rating (k mai tarato: è il default) |
| **`elo_hfa40` / `elo_hfa80`** | rating | Elo | **nuovo**: vantaggio del campo (60 è il default, mai misurato) |
| `pi_ratings` | rating | Pi-ratings | rating di Constantinou-Fenton |
| `mix_50` / `mix_85` | blend | Dixon-Coles | miscela **nella griglia** (matrici mescolate) al 50% e all'85% di DC |
| **`dc_elo_ge`** | production | Dixon-Coles | **ex `dc_elo_tilt`, promosso il 2026-09-13**: la ricetta ora in produzione è `dc_elo_prod` (`mode="tilt"`, l'Elo **inclina** il rapporto casa/trasferta senza gonfiare i gol attesi); `dc_elo_ge` tiene in laboratorio la ricetta precedente (λ libere da `goal_expectancy`) per rendere ripetibile il confronto — vedi `docs/15` |
| **`prod_w50` / `prod_w85`** | production | Dixon-Coles | **nuovo**: il peso 0,7 della media pesata non era mai stato confrontato con 0,50 e 0,85 |

Più `convex_weights()`: stacking convesso dei vettori 1X2 (Nelder-Mead, nessuna dipendenza nuova),
per sapere se una combinazione pesata batte il migliore dei singoli.

### 5.2 Protocollo (corretto in due punti che rendevano il confronto iniquo)

- finestre cronologiche per lega: si allena su tutto ciò che precede il taglio e si valuta sulle gare
  della finestra (default 28 giorni, minimo 600 partite di storico); il test con `SpyGoals`
  (`tests/test_lab.py`) verifica che **nessun fit veda una data successiva alle gare che valuta**;
- **ogni candidato corregge il proprio livello dei gol** (`self_calibrate`, default attivo): il
  moltiplicatore a momenti è stimato **solo sulle gare che quel candidato ha già valutato** nelle
  finestre precedenti (minimo 100, stessi limiti di sicurezza della produzione). Senza, il confronto
  era truccato: la baseline è pubblicata calibrata, e un candidato con λ più basse veniva penalizzato
  due volte. `--no-self-calibrate` confronta invece i candidati con la calibrazione salvata così com'è;
  la colonna `scala_media` del riepilogo dice quanta correzione serve a ciascun candidato;
- la correzione del livello è **conservativa della forma**: per le griglie non-Dixon-Coles (miscele e
  famiglie non-DC) si usa un'**inclinazione esponenziale** p′(i,j) ∝ p(i,j)·θ^(i+j) con θ cercato per
  bisezione (`_tilt_total`), che per Poisson indipendenti coincide con λ·θ e per le altre famiglie
  sposta la media dei gol senza trasformare una binomiale negativa in un Dixon-Coles;
- **bug trovato e corretto**: `_apply_calibration` ricostruisce una griglia τ dalle λ, e le miscele
  dichiaravano le λ del DC → con una calibrazione non identica **`mix_50` diventava identico a
  `dc_puro` riga per riga** (verificato: 405 gare su 405, p_home, mercati e λ_total uguali). Il
  candidato che doveva misurare la miscela non misurava niente. Ora le miscele dichiarano le λ della
  propria matrice e ricevono la correzione sulla propria superficie
  (`test_con_calibrazione_attiva_la_miscela_resta_diversa_dal_dc`);
- **bug trovato e corretto**: nelle famiglie non-DC la calibrazione non veniva applicata affatto,
  quindi Poisson/binomiale negativa/zero-inflazionata/Weibull erano confrontate «grezze» contro una
  baseline calibrata. Con la correzione, sul corpus surrogato il loro RPS passa da 0,2058 a **0,1968**;
- `goal_expectancy` dentro `_mix_grids` riceve gli stessi limiti di sicurezza della produzione (§3.3):
  su un vettore irraggiungibile (pareggio al 9,5%, ottenuto con un Elo degenerato sui dati H2H)
  l'inversione scappava a λ 5,80+3,14 = 8,9 gol attesi e la miscela veniva bocciata per un difetto
  dell'inversione;
- metriche per candidato: **RPS**, log-loss, Brier 1X2 e dei mercati, esito azzeccato, bias delle λ,
  pareggio previsto/osservato, scala applicata, quota di gare in cui è il migliore/il peggiore;
- **bootstrap appaiato a 95%** sulla differenza di RPS rispetto alla baseline, **sullo stesso insieme
  di partite**: se l'intervallo include 0, la differenza è rumore e non si cambia modello;
- tabella per lega (`per_league`) per la parità richiesta fra i 7 campionati;
- output: tabella in console + `data/processed/model_lab.parquet` (chiavi `candidate`, `league_key`).

### 5.3 Giri eseguiti dal sandbox **[offline, corpus surrogato — indicativo, non decisionale]**

Nel sandbox i mirror dei dati storici non sono raggiungibili, quindi il laboratorio è stato provato su
uno storico **ricostruito** da `data/processed/h2h.parquet` (`scripts/corpus_da_h2h.py`: 4.803 partite,
7 leghe, dal 2014). Quel corpus è **distorto** in due modi misurati: sottostima i gol di ~10% (è un
campione di precedenti, non un calendario completo) e, con così poche partite per squadra, **fa
degenerare l'Elo** (per Juventus-Torino dà 76/9/21: pareggio al 9,5%, che nel calcio reale non
esiste). I numeri qui sotto dimostrano che il meccanismo funziona e che il confronto è ora equo;
**non** dicono quale modello scegliere. La scelta va presa sul primo giro in Actions con
`history.parquet` reale.

16 candidati, `--min-train 300 --step-days 120 --max-windows 4`, **519 partite valutate in 95 s**
(correzione automatica del livello non ancora attiva: 519 gare su 7 leghe sono ~74 per lega, sotto la
soglia di 100; sul corpus reale scatterà):

| candidato | RPS | Δ RPS | IC 95% appaiato | log-loss | bias λ | pareggio previsto |
|---|---|---|---|---|---|---|
| `zero_inflated` | **0,1966** | −0,0031 | [−0,0090; +0,0026] | 0,9779 | +0,064 | 22,0% |
| `neg_binomial` | 0,1968 | −0,0029 | [−0,0088; +0,0028] | 0,9789 | +0,062 | 22,0% |
| `poisson` | 0,1968 | −0,0029 | [−0,0089; +0,0029] | 0,9792 | +0,063 | 22,0% |
| `elo_k40` | 0,1977 | −0,0020 | [−0,0061; +0,0024] | 0,9934 | — | 18,5% |
| `biv_poisson` | 0,1978 | −0,0018 | [−0,0084; +0,0045] | 0,9917 | +0,066 | 23,4% |
| **`dc_elo_tilt`** | 0,1996 | −0,0000 | [−0,0003; +0,0003] | 0,9915 | **−0,186** | 25,9% |
| `dc_elo_prod` (baseline) | 0,1997 | 0,0000 | — | 0,9903 | +0,155 | 25,0% |
| `prod_w50` | 0,1997 | +0,0001 | [−0,0007; +0,0008] | 0,9913 | +0,386 | 23,9% |
| `prod_w85` | 0,2001 | +0,0004 | [−0,0002; +0,0011] | 0,9918 | −0,024 | 26,0% |
| `elo` | 0,2005 | +0,0008 | [−0,0021; +0,0038] | 0,9984 | — | 20,0% |
| `mix_85` | 0,2006 | +0,0009 | [+0,0002; +0,0016] | 0,9944 | −0,066 | 25,5% |
| `dc_puro` | 0,2007 | +0,0011 | [−0,0002; +0,0023] | 0,9943 | −0,186 | 26,9% |
| `mix_50` | 0,2008 | +0,0012 | [+0,0003; +0,0020] | 0,9962 | +0,215 | 24,2% |
| `elo_hfa40` | 0,2008 | +0,0011 | [−0,0018; +0,0041] | 0,9987 | — | 20,3% |
| `pi_ratings` | 0,2018 | +0,0022 | [−0,0072; +0,0118] | 1,0115 | — | 29,3% |
| `elo_k10` | 0,2071 | **+0,0074** | **[+0,0040; +0,0110]** | 1,0161 | — | 21,2% |

Lettura onesta, in tre punti:

1. **nessun candidato batte la baseline in modo significativo** (tutti gli IC, tranne uno, contengono
   lo 0): su 519 partite non si cambia modello. L'unica differenza significativa è in peggio
   (`elo_k10`, rating troppo lenti);
2. **`dc_elo_tilt` è il segnale più interessante**: stesso RPS della produzione (0,1996 contro 0,1997,
   IC [−0,0003; +0,0003]) **senza gonfiare i gol attesi** (bias −0,186 contro +0,155). Se regge sul
   corpus reale, è la correzione strutturale del difetto che oggi la calibrazione deve tamponare
   globalmente: l'Elo entra nell'1X2, i gol attesi restano quelli del modello sui gol;
3. le famiglie Poisson-like in testa sono con ogni probabilità un **artefatto del corpus** (che
   sottostima i gol e ha pochi precedenti per squadra): in letteratura Dixon-Coles batte Poisson di
   ~0,0001-0,0002 RPS su dati veri (pena.lt 2025-03: DC 0,19138 contro Poisson 0,19154). Va
   ricontrollato sul corpus reale, non promosso qui.

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

1. **[live]** `fda calibrate` nel run giornaliero produce una calibrazione con `n_fit ≥ 1.200`,
   stimatore `momenti`, finestra 730 giorni e `bias_lambda` del campione pieno **< 0,10 gol**
   (oggi **−0,024** sul backtest, +0,053 fuori campione);
2. **[live]** nella pagina Accuratezza il pareggio dichiarato cade **dentro** l'intervallo di Wilson
   e Over 2,5 / BTTS si avvicinano all'osservato (scarto < 2 pp);
3. **[live]** Brier mercati del backtest successivo **non peggiora** oltre 0,0005 rispetto a 0,2065
   (identità) — con la v1.1 il valore atteso è ~0,2052 fuori campione e 0,2017 sul campione pieno
   (9 mercati, previsioni calibrate);
3bis. **[live]** nessuna previsione pubblicata con λ per squadra > 4,00 o λ totali > 5,5; nel log del
   run compaiono al più poche decine di `λ dall'1X2 mediato fuori dai limiti` (atteso: ~1,2% delle
   gare, concentrate dove il divario tecnico è massimo — POR1, NED1);
4. **[live]** `history.parquet` compare in `data/processed` dopo il primo run con `fda simulate`;
5. **[verificato, promosso il 2026-09-13]** il primo `lab` utile in Actions (run 34784018926,
   commit `bb247fe`) ha pubblicato `model_lab.parquet` con **1.527 partite** per candidato e 7
   leghe; il criterio — «si cambia modello **solo** se un candidato batte `dc_elo_prod` con IC 95%
   appaiato interamente negativo, e solo se il vantaggio vale in almeno 5 leghe su 7» — è stato
   soddisfatto da `dc_elo_tilt`: ΔRPS **−0,000406**, IC **[−0,000773; −0,000041]**, RPS più basso
   in **5 leghe su 7**, `scala_media` **1,013** (contro 0,955 della baseline: la firma del difetto
   strutturale, visibile senza leggere il codice). `dc_puro` e `prod_w85` vincono 5/7 ma con IC che
   contiene lo 0; `prod_w50` è significativamente peggiore (+0,000497). **Esito: `dc_elo_tilt` è
   ora la ricetta di produzione** (`predict.ENSEMBLE_MODE = "tilt"`), la baseline `dc_elo_prod`
   la usa e la ricetta precedente resta in laboratorio come `dc_elo_ge`. Sul backtest pieno
   (5.811 gare, confronto appaiato) il guadagno è confermato e più grande: RPS calibrato
   0,19958 → 0,19882 (Δ −0,00077, IC interamente negativo, **7 leghe su 7**), con Brier dei
   mercati sui gol che peggiora di 0,00047 in modo non significativo. Dettagli, misure e
   ristima della calibrazione (λ×0,9135 → **λ×1,0401**):
   [`docs/15_promozione_dc_elo_tilt_2026-09-13.md`](15_promozione_dc_elo_tilt_2026-09-13.md);
6. **[offline, già verificato]** suite **163 passed** (0 warning), `ruff --select F,E9` pulito su `src`,
   `tests` e `scripts`, build di anteprima (376 schede / 2.364 fixture / 7.394 giocatori),
   `scripts/verify_site.py` **0 problemi · 2.213 controlli numerici superati** con i controlli [8b]
   (backtest ricalcolato con la calibrazione salvata), [9] (138 distribuzioni dei gol, ultima colonna
   del dotplot compresa) e [10] (138 scomposizioni della probabilità);
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

**P2bis — struttura dell'ensemble (la strada aperta da questa sessione)**
3bis. **`dc_elo_tilt` in produzione**, se il giro reale in Actions conferma il risultato surrogato
   (stesso RPS della ricetta attuale, bias λ da +0,155 a −0,186): l'Elo inclina il rapporto
   casa/trasferta, i gol attesi restano quelli del modello sui gol. È la correzione *strutturale* del
   difetto che oggi la calibrazione tampona con un moltiplicatore globale 0,9135: se entra, la
   calibrazione dovrebbe tornare vicino a 1,00 e il suo ruolo diventare solo la deriva di regime.
   Va misurato anche l'effetto sui mercati (Over/BTTS/risultati esatti), non solo sull'1X2.
3ter. ~~**Orizzonte delle previsioni**~~ **FATTO — Tappa 1, §9** (decisione utente «procedi»,
   2026-09-13): chiave di `predictions` = `(match_id, model)` (una riga per partita, con migrazione
   delle ~23 versioni accumulate), `fda predict --days-ahead 0` = tutto il calendario, pagina
   «Prossime» estesa al calendario completo in righe compatte. Copertura **6,6% → 96%**
   (138 → 2.000 partite su 2.083), spazio per partita coperta **1,6 kB → 0,27 kB**. La Tappa 2
   (schede per le partite lontane) resta rinviata: §9.5.

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
| `src/fda/models/calibration.py` | stimatore a momenti (`_estimate`, `moment_scale`, `_best_shift`), finestra 730 gg, fit walk-forward, confronto con la scelta su griglia, `evaluate`, `from_store`, `apply_many`, `as_row` a 6 decimali |
| `src/fda/models/dc_grid.py` | `GRID_SIZE = 11` (costante unica), `tau_grid_many`, `clamp_rho_many`, `grid_markets_many` (vettorizzati) |
| `src/fda/models/lab.py` | 22 candidati, `walk_forward` con correzione del livello per candidato, `_tilt_grid`, `_tilt_total`, `_apply_grid_level`, `_mix_grids` protetta, `summarize` (bootstrap appaiato, `scala_media`), `per_league`, `convex_weights` |
| `src/fda/models/predict.py` | `_clamp_lambda` + limiti di sicurezza, `lambda_limitata`, `calibrated_prediction` su griglia 11×11, `dc_p_*` salvati, `MODEL_VERSION` `dc-elo-ens-0.3` |
| `src/fda/models/season_sim.py` | `persist_history`, calibrazione dentro `_match_grid`/`simulate_league`/`simulate_all` |
| `src/fda/cli.py` | `fda calibrate`, `fda lab`, ordine del `daily`, storico salvato da `predict`/`backtest` |
| `src/fda/store.py` | chiavi delle tabelle `history`, `calibration`, `model_lab` |
| `src/fda/site/advanced.py` | `goals_view`, `probability_steps`, `_per_cento` |
| `src/fda/site/analysis.py` | `_lambdas` (NaN → nessun blocco), wrapper `goals_view` |
| `src/fda/site/templates/match.html`, `base.html` | i due blocchi nuovi + CSS |
| `src/fda/models/backtest.py` | `model_version` per riga, `calibrate_rows` (previsioni ripubblicate dalla griglia calibrata, grezzi in `*_raw`), `backtest_summary` con bias λ / Brier 9 mercati / pareggio / versione di calibrazione e modello, `_mean_or_nan` |
| `src/fda/site/build.py`, `templates/accuracy.html` | `(k/n)` pubblicato per mercato, riga «modello calibrato» con confronto «senza calibrazione», etichetta della calibrazione e versioni del modello presenti |
| `scripts/diagnose_model.py`, `scripts/corpus_da_h2h.py`, `scripts/anteprima_scheda.py`, `scripts/verify_site.py` | diagnosi, corpus offline, anteprima locale, controlli [9]/[10] |
| `.github/workflows/lab.yml` | laboratorio settimanale su storico reale |
| `tests/test_calibration.py`, `tests/test_lab.py`, `tests/test_models.py`, `tests/test_advanced.py`, `tests/test_season_sim.py`, `tests/test_backtest.py` | test nuovi e aggiornati: stimatore a momenti, deriva di regime, scelta su griglia a confronto, `n_fit` = gare di stima, limiti di sicurezza sulle λ, coerenza 1X2/griglia, inclinazione esponenziale, correzione del livello per candidato, miscela non appiattita (suite a **163**) |

---

## 9. Tappa 1 — orizzonte esteso a tutto il calendario (implementata, 2026-09-13)

**Decisione utente**: dopo la diagnosi di copertura (**138 partite previste su 2.083 in calendario =
6,6%**) l'utente ha approvato con «procedi» la **Tappa 1**: previsione per tutte le partite in
programma, una riga per partita, pagina «Prossime» estesa al calendario completo. La **Tappa 2**
(schede complete anche per le partite lontane) resta **rinviata** (§9.5).

### 9.1 Che cosa cambia

| Dove | Prima | Dopo |
|---|---|---|
| `store.TABLE_KEYS["predictions"]` | `(match_id, model, made_at)` → una riga per run | `(match_id, model)` → **una riga per partita** |
| `models/predict.latest_per_match` | — | tiene l'ultima previsione per (partita, modello): **migrazione** delle righe accumulate e garanzia a regime |
| `cli.predict_cmd` | `--days-ahead 7` | `--days-ahead 0` = **tutto il calendario** (default); con `>0` il tetto resta, per prove |
| `cli.predict_cmd` (avvio) | — | collassa le versioni precedenti e lo dichiara: «previsioni: 3.210 righe → 138 (una per partita)» |
| filtro partite | `scheduled & kickoff <= now+7g` | `scheduled & kickoff >= now` (il tetto si applica solo se `days-ahead > 0`) |
| `site/build.build_indexes` | 3 viste ricche (oggi / 7 giorni / risultati) | **+ calendario completo** in righe compatte, solo nella vista «Prossime», raggruppato per mese |
| `templates/index.html`, `_matchlist.html`, `base.html` | — | sezione «Tutto il calendario»: navigazione per mese, un `<details>` per mese (il primo aperto), riga = data · gara · 1X2 · gol attesi · Over 2,5 |
| `scripts/verify_site.py` | controlli [1]-[10] | **+ [11] calendario**: 1X2 che somma 100, `aria-label` = testo visibile, preferito in grassetto e coerente con `cal-fav-*`, gol attesi in formato italiano, data/ora valide, mesi in ordine con etichetta coerente, conteggio dichiarato = righe stampate, navigazione = sezioni |

**Perché non costa richieste in più**: l'elenco delle partite arriva da una sola chiamata `fixtures`
per lega, che `fda collect` fa già; il modello ha bisogno solo di squadre e storico. Restano legate
alla vicinanza della gara le raccolte *per partita* (`matchDetails`, formazioni, infermeria, meteo,
arbitro) che `fda collect` fa nella finestra `future_days`: anticiparle sarebbe spreco, la fonte non
ha ancora pubblicato quei dati (coerente con la direttiva utente «distinguere assente / non ancora
pubblicato / recuperato»).

### 9.2 Misure **[offline dal sandbox: storico surrogato da `h2h`, numeri di gioco non decisionali]**

- **Copertura**: 138 → **2.000 partite previste su 2.083 in programma (96%)**. Nel calendario oltre i
  7 giorni: **1.837 righe con previsione, 150 senza** (7,5%: una o entrambe le squadre non sono nello
  storico surrogato disponibile nel sandbox).
- **Costo di previsione**: **29,7 ms per partita** → 1.862 previsioni in **55 s**; su 5 run/giorno
  ~5 minuti al giorno in più, dentro il budget del `daily` (~11 minuti oggi).
- **Spazio**: `predictions.parquet` 218 kB per 138 partite (**1,6 kB per partita coperta**) → 549 kB
  per 2.000 partite (**0,27 kB per partita coperta**): 14× la copertura a 1/6 dello spazio per
  partita. Il vecchio file comprimeva bene *perché* era 23 copie quasi identiche per gara
  (69 B/riga contro 469 B/riga delle stesse righe collassate).
- **Build del sito**: `build_indexes` **2,4 s** col calendario completo (le righe compatte non
  chiamano `analysis.list_context`, che è il costo delle righe ricche); build completo **146 s**
  (376 schede, 2.364 fixture, 7.394 giocatori) = invariato.
- **Peso della pagina**: `prossime.html` 274 kB → **1.102 kB** per 1.987 righe compatte
  (**+430 B/riga**), **83 kB gzip**; `index.html` e `risultati.html` invariati (il calendario sta in
  una vista sola, niente duplicati).
- **Verifiche**: `scripts/verify_site.py` sulla build locale completa → **0 problemi · 11.793
  controlli**, di cui **[11] 9.643 controlli su 1.987 righe di calendario**; suite **169 passed**
  (+6 test: `latest_per_match` e casi degeneri, chiave di `predictions` una riga per partita,
  `pct_triple` mai 99/101, calendario presente in «Prossime» e assente altrove, righe senza
  previsione dichiarate, nessun link a schede inesistenti).

### 9.3 Scelte di qualità dentro la Tappa 1

- **Percentuali che sommano sempre 100** (`build.pct_triple`, metodo del resto massimo, il punto
  mancante va all'esito più probabile): in una riga compatta il lettore non ha contesto per
  accorgersi di un arrotondamento sbagliato.
- **Preferito marcato due volte** (grassetto + colore della famiglia 1/X/2 già usata nelle liste):
  il colore non è mai l'unico canale (WCAG 1.4.1).
- **Degrado onesto**: senza previsione la riga scrive «senza previsione» (niente celle vuote né zeri),
  l'introduzione conta quante sono e ne dice il motivo; **nessun link a schede che non esistono**
  (`_calendar_rows` genera l'URL solo per gli id con pagina: quando la Tappa 2 accenderà le schede
  lontane i link compaiono da soli).
- **Mesi chiusi di default** (`<details>`, aperto solo il primo): 1.987 righe restano navigabili e la
  pagina resta veloce su mobile; **filtri e ricerca della toolbar valgono anche sul calendario** (la
  chiave di ricerca delle righe compatte è ricavata dal testo una volta sola, invece di duplicare
  `data-search` su 2.000 righe).
- **Log**: il dettaglio per partita dei limiti di sicurezza sulle λ scende a `DEBUG` e
  `predict_matches` scrive **un solo riepilogo** col tasso di intervento («limiti di sicurezza su
  lambda: toccate 29 partite su 2.084 (1,39%)»): su un calendario intero i singoli casi annegavano il log.

### 9.4 Da verificare dal vivo (Actions, dopo il merge)

1. `fda predict` con `days-ahead 0`: partite previste per lega (atteso: tutte quelle in programma,
   ~2.000), durata del passo (atteso 1-2 minuti), riga di collasso «3.210 → 138» al primo run.
2. Quante righe restano **senza previsione** con lo storico reale (atteso: molto meno delle 150
   offline — le neopromosse senza storico datahub ricevono il prior del DC, quindi una previsione
   ce l'hanno; il caso offline era dovuto allo storico surrogato).
3. **Effetto dell'orizzonte sulla qualità**: offline **non è misurabile** (esperimento 2026-09-13:
   RPS 0,2027 / 0,2138 / 0,1934 / 0,1943 per 0-7 / 8-14 / 15-30 / 31-60 giorni di anticipo, non
   monotono e dentro il rumore, SE ≈ 0,03 per bucket). Con tutto il calendario previsto,
   `predictions` accumula `made_at` e `utc_kickoff`: la pagina Accuratezza potrà spezzare l'RPS per
   anticipo **sui dati veri** (§7 voce 7, già in coda).

### 9.5 Tappa 2 (rinviata — serve decisione utente)

Schede complete anche per le partite lontane: ~2.000 pagine in più (**+17 minuti** di build stimati),
contenuto in gran parte segnaposto («formazioni non ancora pubblicate», «arbitro da definire»), e il
valore cresce solo a ridosso della gara. Oggi la riga compatta dà già il modello (1X2, gol attesi,
Over 2,5) per tutta la stagione; la Tappa 2 aggiungerebbe contesto, non informazione predittiva.

### 9.6 Audit pre-merge delle schede **in programma** (misurato sulla build locale, 2026-09-13)

Domanda dell'utente: «le schede delle partite in programma hanno le giuste sezioni e contenuti?».
Misurato su **95 schede pre-partita** (le gare in programma entro 7 giorni: ESP1 22, ITA1 15, POR1 15,
ENG1 12, NED1 11, FRA1 10, GER1 10) — le altre **1.987 partite in programma hanno la riga compatta e
non la scheda** (4,6% di copertura: è la Tappa 2, §9.5).

| Sezione | ENG1 | ESP1 | FRA1 | GER1 | ITA1 | NED1 | POR1 |
|---|---|---|---|---|---|---|---|
| Analisi pre-partita (hero) | 12/12 | 22/22 | 10/10 | 10/10 | 15/15 | 11/11 | 15/15 |
| Scontro tattico | 12/12 | 22/22 | 10/10 | 10/10 | 15/15 | 11/11 | 15/15 |
| I giocatori che decidono | 12/12 | 22/22 | 10/10 | 10/10 | 15/15 | 11/11 | 15/15 |
| Contesto (distinte, meteo, arbitro, precedenti) | 12/12 | 22/22 | 10/10 | 10/10 | 15/15 | 11/11 | 15/15 |
| Confronto di stagione | 12/12 | 22/22 | 10/10 | 10/10 | 15/15 | 11/11 | 15/15 |
| Fatti rilevanti | 12/12 | 22/22 | 10/10 | 10/10 | 15/15 | 11/11 | 15/15 |
| Previsione / Risultati esatti / Matrice / Quanti gol | 12/12 | 22/22 | 10/10 | **9/10** | 15/15 | 11/11 | **14/15** |
| Come arrivano | 12/12 | 22/22 | 10/10 | **9/10** | 15/15 | 11/11 | 15/15 |
| Come nasce questa probabilità | **4/12** | **5/22** | **3/10** | **2/10** | **4/15** | **3/11** | **4/15** |

Audit per campo (`audit_match`, 13 campi × 95 schede): **0 «mancante»** dopo le correzioni sotto;
«attesi dalla fonte» = formazioni 66, arbitro 75 (finestre reali di pubblicazione), indisponibili 11.

**Diagnosi delle due righe in grassetto (non sono difetti di codice):**
- **2 schede senza i blocchi del modello** (`Schalke 04–Elversberg` GER1 e `Estrela da Amadora–
  Académico Viseu` POR1, 20/09): neopromosse **senza storico** nel corpus surrogato del sandbox
  (`h2h`), quindi `predict_matches` le salta. Con lo storico reale di produzione le neopromosse
  ricevono il prior dagli esiti della stagione in corso (già verificato in `docs/STATO.md` per
  ADO Den Haag/Cambuur/Académico Viseu/Marítimo nel 2026-09-08): **da ricontare dopo il merge**
  (§9.4 punto 2). La stessa causa spiega le 150 righe «senza previsione» del calendario offline.
- **«Come nasce questa probabilità» su 25 schede su 95**: le **138 previsioni committate in
  `data/processed` sono di due versioni di modello fa** (`dc-elo-ens-0.1` 60 righe, `-0.2` 78 righe),
  quindi non hanno i campi `blend_p_*` / `lambda_*_raw` / `rho_raw` / `calibration_*` da cui la
  catena viene ricostruita. Verificato riga per riga: **25/25 schede con riga `dc-elo-ens-0.3`
  hanno la sezione, 0/138 con riga più vecchia**. Il primo `fda predict` dopo il merge le
  rigenera tutte → la sezione (e la calibrazione v1.1, e i limiti sulle λ) va a regime su **tutte**
  le schede, non solo su quelle nuove.

**Quattro correzioni fatte prima del merge (nate da questo audit):**
1. **`audit.py`: la previsione non è un dato «atteso dalla fonte».** Con `--days-ahead 0` il modello
   non aspetta nessun editore: se manca è **mancante** (`AuditItem.from_source = False`). Prima le
   2 schede senza previsione risultavano «attese» e il buco spariva dal conto in `stato.html`.
2. **`audit.py`: «nessun indisponibile» con distinta pubblicata non è un buco.** 4 squadre su 105
   schede (Telstar, Excelsior, PSG, Moreirense) avevano 11 nomi in distinta e zero assenze
   segnalate → contate come campo mancante. Ora: distinta presente e lista vuota = **presente**
   (`stato.html`: Mancante 4 → **2**, Presente 1.142 → **1.146**, «senza campi scaduti» 101 → 103).
3. **`match.html`: il silenzio non è un'informazione.** Con distinta pubblicata e nessuna assenza la
   scheda ora scrive «Nessun indisponibile segnalato nella distinta pubblicata dalla fonte
   (formazione probabile/ufficiale)» — **solo pre-partita**: sulle gare finite la fonte riporta le
   assenze una volta su due (misurato: 133 sì / 138 no su 271 finite), quindi lì il silenzio è
   davvero ambiguo e la frase sarebbe stata fuorviante.
4. **`base.html`: etichetta del footer** «Prossimi 7 giorni» → «**Prossime partite e calendario**»
   (la pagina ora copre tutta la stagione; l'h1 e la nav erano già aggiornati).

**Verifiche di compatibilità fatte sullo stesso giro** (cose che l'orizzonte esteso poteva rompere):
- tutti i lettori di `predictions` tollerano una riga per partita: `build_accuracy`
  (`made_at < kickoff` + `sort/tail(1)`, oggi un no-op), `analysis.prediction` (`sort/tail(1)`),
  `verify_site` [3]/[8], `scripts/anteprima_scheda.py` (che scrive su `/tmp/preview_data`, **non** su
  `data/processed`);
- `daily.yml` ha `timeout-minutes: 40` contro ~11 minuti di run odierni + ~1 minuto per l'orizzonte
  esteso (misurato 29,7 ms per partita);
- crescita del dato committato: `predictions.parquet` 218 kB → ~550 kB a run, 5 run/giorno
  (+~1,6 MB/giorno di blob, ~11% della cartella `data/processed` che oggi pesa 3,0 MB) — accettata,
  è il prezzo di 14× la copertura.

### 9.8 Merge PR #29 — `dc_elo_tilt` in produzione + sito pubblicato su push (2026-09-14, deroga esplicita)

**Contenuto PR #29** (10 commit, base `main` `b743408`):
- `predict.py`: `ENSEMBLE_MODE = "tilt"` — l'Elo inclina il rapporto casa/trasferta e il totale dei gol attesi resta quello del modello sui gol; `MODEL_VERSION` `dc-elo-ens-0.3` → **`dc-elo-tilt-0.4`**; limiti di sicurezza (λ ≤ 4,0 per squadra, totale ≤ 5,5) applicati **anche dopo la calibrazione**;
- `lab.py`: la baseline `dc_elo_prod` passa da `predict.ensemble` (una sola implementazione per sito e laboratorio), la ricetta precedente resta candidato `dc_elo_ge`;
- dati rigenerati: backtest **5.812 gare**, calibrazione **λ×1,0401 ρ−0,04** (4.760 gare di stima), **2.071 previsioni**;
- 4 test nuovi (tilt, limiti sui gol attesi pubblicati, ricetta precedente, candidati lab) — suite **176 passed**;
- le **4 verifiche dal vivo** di `docs/15` §7 eseguite prima del merge: calibrazione λ×1,0401 ρ−0,04 con bias λ −0,024; pagina Accuratezza RPS 0,1988 con pareggio 25,9% dentro il Wilson 95% [24,53%; 26,78%]; **nessuna scheda sopra i limiti** (trovate e strette 2 schede d'archivio fuori limite, λ 4,02 e totali 5,63/5,91, generate prima che i limiti esistessero); lab offline su 5.812 gare con `dc_elo_prod` = tilt e `dc_elo_ge` significativamente peggiore (Δ +0,0005, IC [+0,0001; +0,0009]);
- `daily.yml`: aggiunto **`push: branches: [main]`** — il sito prima si aggiornava solo ai 5 orari schedulati, che GitHub avvia con **ritardo medio 3,2 ore** (da 1h39m a 5h23m sugli ultimi 20 run).

**Deroga merge PR #29**: l'utente ha scritto «Please merge the pull request» (2026-09-14). In applicazione della regola D (eccezione con deroga esplicita) l'agente esegue `gh pr merge 29 --merge` **dopo aver verificato**: check `test` verdi, PR **MERGEABLE/clean**, `git status --porcelain` vuoto e `git log origin/main..HEAD` con solo il lavoro della PR. Documentata qui e in `STATO.md` undicesimo giro. Deroghe precedenti: PR #23 (2026-09-12), PR #27 e PR #28 (2026-09-13).

**Contenuto PR #28** (commit `f387100` → `14c9dec` → merge `cc80795`):
- fix `lab.yml` quoting bug: da `EXTRA="--candidates $CANDS"` senza virgolette (solo `dc_elo_prod` in `e6da512`) a `if [ -n "$CANDS" ]; then fda lab ... --candidates "$CANDS" --save else ... fi` — ora dispatch con 5 candidati funziona (verificato locale 1.518 gare, tilt Δ−0,000397 IC negativo 5/7 leghe);
- `info.html` IL MODELLO: badge calibrazione live λ×0,914 ρ-0,04 da `calibration.parquet`, spiegazione 70/30 misurata (0,5 peggiore +0,000488, 0,85 5/7 non significativo), limiti λ≤4,0 totale 70-135% (1,19% gare), RPS/Brier in italiano semplice, link lab 22 candidati;
- LE FONTI: Open-Meteo fallback >48h, FotMob→Understat→FotMob per xG NED1/POR1, ESPN 403→FotMob standings, mirror per-lega `datahub_base` in `leagues.yaml`;
- card compatta `_matchlist.html`: forma con legenda V/N/P, lettura modello "favorito · +31,6 pp sul 2° (Pareggio 24%)", segnale "Modelli d'accordo/divisi" con tooltip DC vs Elo scarto, gol attesi con tooltip totale e Over "51 partite su 100 con 3+ gol", infermeria/meteo/arbitro con titolo fonte, H2H bilancio 2-3-12 (2,6 gol/gara, BTTS 59%);
- `accuracy.html` RPS per anticipo bucket 0-7/8-14/15-30/31-60/61+ da `made_at` vs `utc_kickoff`;
- `verify_site.py` regex tolleranti a `title`, `tests/test_site.py` assert tollerante;
- `docs/00_regole_di_lavoro.md` 4 affinamenti logici: A5 anti-crescita STATO archivio ogni 10 giri o >80k, A8bis WIP ammesso con prefisso `WIP:`, B4 mai committare segreti, D deroga merge esplicita.

**Deroga merge PR #28**: utente ha scritto "Please merge the pull request" + "si applicale" per regole (2026-09-13 20:46 UTC). Secondo nuova regola D (eccezione con deroga esplicita) agente ha eseguito `gh pr merge 28 --merge` il 2026-09-13 20:49 UTC dopo verifica check verdi (test SUCCESS, 172 passed) e mergeable MERGEABLE. Merge commit `cc80795` su `main`. Documentata qui e in `STATO.md` nono giro. Precedenti deroghe: PR #23 (2026-09-12) e PR #27 (2026-09-13 15:46 UTC) su ordine esplicito utente, registrate in STATO.md settimo giro.

**Verifiche finali prima del merge**: suite 172 passed, build 376/2364/7434, `verify_site` 0 problemi 12.130 controlli, `site/index.html` Famalicão-Sporting 17 precedenti 2-3-12 (2,6 gol/gara, BTTS 59%), gol attesi 0,97-1,75 Over 51%, modelli d'accordo scarto 6,8pp.

### 9.9 Merge PR #34 — P0/P1/P2/P3 della verifica QQV in `main` (2026-09-15, deroga esplicita)

**Contenuto PR #34** (15 commit, base `main`, testa `arena/01a0a5f3`; 45 file, +3.597/−424):
- **P0-1/P1-4/P1-5** — card «Panchina e posta in gioco», riposo vero con le coppe (`cup_fixtures`),
  strato «interno» con `sources/news.py` (Google News RSS per squadra + ESPN news di lega) e card
  «Ultime dalle società»;
- **P2-6** card «Clima del club» (segnali a soglie dichiarate, blocco narrativo separato dall'analisi
  pre-partita), **P2-7** mercato (`FotMobClient.parse_transfers` + `collect_transfers` + card «Mercato:
  arrivi e partenze», dark launch onesto), **P2-8a** `scope` su ogni `<th>` (193 attributi),
  **P2-8b** anteprime `docs/preview/` rigenerate con Pillow sul layout corrente;
- principio di utilità applicato a Scontro tattico (graduatorie + duello chiave), «I giocatori che
  decidono» (badge «giocherà?») e post-partita (card «Il prossimo impegno», conversione delle grandi
  occasioni);
- **P3-a** ξ per lega con gate di adozione (`fda lab-xi`, `xi_league.parquet`: **0/7 adottano**) e
  **P3-b** monitoraggio dei mercati binari (`fda mercati-monitor`: **0/9 «strutturale»**);
- `docs/21_verifica_qqv_piano_2026-09-15.md` completa (§0–§14) e STATO aggiornato a ogni giro.

**Verifiche prima del merge (misurate, non presunte):** suite **246 passed**; build completa +
`scripts/verify_site.py` **0 problemi · 26.821 controlli**; ruff pulito sul codice nuovo; check
GitHub della PR: **2 su 2 SUCCESS**; `git status --porcelain` vuoto e `git log origin/main..HEAD`
limitato al lavoro della PR.

**Deroga merge PR #34**: l'utente ha chiesto esplicitamente all'agente di eseguire il merge
(2026-09-15). In applicazione della regola D (eccezione con deroga esplicita) l'agente ha eseguito
`gh pr merge 34 --merge` **dopo aver verificato** check verdi, PR mergeable e assenza di lavoro
residuo; merge commit **`bd8a4d5`** in `main` (2026-09-15T22:29:53Z). Documentata qui e in `STATO.md`
dodicesimo giro. Catena delle deroghe precedenti: PR #23 (2026-09-12), #27 e #28 (2026-09-13),
#29 (2026-09-14) — tutte su ordine esplicito dell'utente.

**Verifica post-merge (primo daily di Actions, run `35031258981`, data commit `a2fbfaf`):** run e
deploy Pages verdi; sul sito pubblicato `mercati_monitor` **9 righe** e `xi_league` **7 righe**; il
verdetto di Actions coincide col locale (0/9 «strutturale»). Punto aperto: **`news` e `transfers` a
zero righe utilizzabili** nonostante le fonti a registro OK (news 139 richieste, transfers 263) —
tabelle assenti e card buie come previsto dal dark launch onesto (consuntivo in `docs/21` §14).

### 9.10 Merge PR #35 — diagnostica delle fonti a zero righe (2026-09-15, deroga esplicita)

**Contenuto PR #35** (4 commit, testa `arena/01a0a75d`, 13 file): constatazione della deroga di
PR #34 in `docs/13` §9.9; recupero del commit orfano `07fac55` (consuntivo post-merge in `docs/21`
§14); piano `docs/21` §15 e sua attuazione (blocchi 1+2+3): modulo `fda/diagnostics.py`
(`bump`/`key_names`/`shape_of`/`detail`/`digest`, soli nomi di campo, mai valori), `source_status`
con `rows`/`detail`/`digest` e imbuto dei conteggi in tutte e quattro le fasi, colonna «Righe» in
`stato.html` con l'invariante **[28]** di `verify_site`, correzione della query Google News
(doppia codifica), contatori **per fase** (chiude il riscontro di `docs/19` §1.6), `espn news` 403
come AVVISO, firma dello schema in `parse_transfers`.

**Verifiche pre-merge**: suite **262 passed**, check GitHub `test` verde, `verify_site` **0
problemi · 26.951 controlli**, ruff pulito sul toccato.

**Deroga merge PR #35**: l'utente ha chiesto esplicitamente all'agente di eseguire il merge
(«Please merge the pull request», 2026-09-15). Secondo la regola D (eccezione con deroga
esplicita) l'agente ha eseguito `gh pr merge 35 --merge` dopo aver verificato check verdi
(`test` 1m14s), PR `MERGEABLE`/`CLEAN`, `git status --porcelain` vuoto e `git log
origin/main..HEAD` limitato al lavoro della PR. Merge commit **`1594170`** (2026-09-15T23:47:17Z).
Documentata qui e in `STATO.md` quattordicesimo giro. Catena delle deroghe: #23 (2026-09-12),
#27/#28 (2026-09-13), #29 (2026-09-14), #34 (2026-09-15), #35 (2026-09-15).

**Esito immediato (per onestà documentale)**: il primo daily su `main` col nuovo codice — run
`35037211442`, trigger push — è andato **rosso** in build. La causa **non** è nel contenuto della
PR ma in un difetto latente della card notizie di PR #34, che è stato possibile diagnosticare
proprio grazie a un fix di questa PR (la query Google News corretta ha popolato `news.parquet`,
attivando il percorso che conteneva il difetto). Diagnosi, fix e strumento di lettura dei log:
`docs/21` §16; fix in PR #36.

### 9.11 Merge PR #40 — P1 contenuti + verify_site gate in CI (2026-09-16, deroga esplicita)

**Contenuto PR #40** (7 commit, base `main`, testa `arena/01a0aa56`; `docs/21` §19):
- **P1.2+P1.3 arbitro**: un solo profilo (`referee_profile()`) ed etichetta relativa alla media
  di lega con `MIN_REFEREE_MATCHES=15` (0 «molto severo» assoluto sul sito reale; morso al vivo
  «su 12 12 gare» corretto con test anti-doppio);
- **P1.4**: 5+1 template FotMob recuperati (fatti tradotti 66,0% → 74,3%), scarti osservati per
  forma canonica in `stato.html`;
- **P1.5**: `DETAIL_WINDOW_DAYS` unica fonte del «7 giorni» + test di unicità;
- **P1.6**: `404.html` (link/CSS assoluti, noindex) + sitemap onesta (lastmod reali: 39 date
  contro 1; home unica; 7 pagine di lega);
- **P1.13**: skip-link + footer h3→h2 (scope/main/salti già coperti, misurato all'avvio);
- **CI**: `verify_site` come gate nel daily, prima di commit dati e deploy.

**Verifiche prima del merge (misurate):** suite **286 passed**; check `test` **pass** (1m24s);
PR **MERGEABLE**; `git status --porcelain` vuoto; `verify_site` **0 problemi · 32.868 controlli**
sul build reale; ruff src+tests 601 → 600.

**Deroga merge PR #40**: l'utente ha scritto esplicitamente «Please merge the pull request»
(2026-09-16). In applicazione della regola D (eccezione con deroga esplicita) l'agente ha
riverificato check verdi e mergeable, poi eseguito `gh pr merge 40 --merge`; merge commit
**`7e23e4d`** in `main`. Documentata qui e in `STATO.md`. Catena deroghe precedenti: PR #23
(2026-09-12), #27/#28 (2026-09-13), #29 (2026-09-13), #34 (2026-09-15), #35 (2026-09-15),
#38 (2026-09-16).

**Primo daily con il gate `verify_site`**: run `35106840117` partito col merge — esito da
confermare (il passo nuovo deve restare verde in Actions per chiudere la voce di §18.5/§19.7).
