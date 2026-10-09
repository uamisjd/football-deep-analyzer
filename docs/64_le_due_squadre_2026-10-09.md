# 64 — Revisione card «Le due squadre» (2026-10-09)

Metodo `docs/57`, regola `docs/00` B.10: per ogni difetto **misura → correzione → invariante o
test**; niente modifiche «a sentimento». Perimetro imposto dall'utente: **ogni partita, senza
dimenticarne una** → 446 schede, 892 riquadri di squadra, 7 leghe.

La card (`match.html`, `id="squadre"`) è la seconda cosa che il lettore vede dopo l'hero e
contiene i numeri di stagione più pesanti della scheda: forma, xG creati e concessi, xPTS
contro punti, pressing, riposo, indisponibili, distinta. È anche quella che **altre cinque card
citano** (`analysis.py:1475, 1868, 2063, 2243, 5113`).

## 1. Misura di partenza (build del 2026-10-09)

446 schede (375 finite, 71 programmate), 2.364 fixture, 7.498 giocatori.

| misura | prima |
|---|---|
| riquadri di squadra con i 4 valori di stagione | 892/892 |
| valori di stagione con un **riferimento** (è tanto? è poco?) | **0** |
| `PPDA n.d.` senza spiegazione | 310 riquadri |
| schede con le **due squadre su fonti xG diverse** senza dirlo | 3 (`5749694`, `5881186`, `5881191`) |
| voti nella distinta pre-partita | **0 su 1.210 titolari** |
| squadre con verdetto xPTS in card **negato** dalla narrativa della stessa pagina | **24 su 132** |
| «coppe incluse» (nome della coppa buttato via) | 37 |
| piè di card | spiegava `Ruolo n.d.`, stringa **mai stampata** |

Due ipotesi sono state **misurate e smentite** prima di toccare il codice (B.10):

- «il campione xG è in ritardo sulle gare giocate» → gap classifica − campione = **0 su 132
  squadre** (min −1, max 0). Unica eccezione reale: **Cagliari**, 15 pt su 6 gare Understat
  contro 12 pt su 5 in classifica → ora dichiarata nel ⓘ dello scarto, non «corretta»;
- «la griglia annidata in `{% if xg %}` fa sparire il riposo» → oggi **nessun caso reale**
  (tutte e 446 le schede hanno `xg` su entrambi i lati). Fragilità latente, non difetto.

## 2. Difetti corretti

### 2.1 Quattro grafie Understat non agganciate (`src/fda/teams.py`)

`Parma Calcio 1913`, `RasenBallsport Leipzig`, `FC Cologne`, `Borussia M.Gladbach` non
convergevano sul nome canonico: quelle squadre perdevano xG, xPTS e PPDA di Understat e
ripiegavano su FotMob. Risultato visibile: **3 schede** in cui la colonna di sinistra diceva
«1,86× la media» con un modello xG e quella di destra con un altro. Quattro alias nuovi, 0 nomi
non agganciati dopo il fix.

### 2.2 Il verdetto xPTS era una soglia fissa sotto il rumore

La card scriveva «sopra atteso / sotto atteso» quando |punti − xPTS| ≥ **2**; la narrativa della
stessa pagina usava **3**; «Clima del club» ne dichiarava un'altra ancora. Misura nuova su
**502 gare-squadra** Understat: la deviazione standard di (punti − xPTS) **su una singola gara**
è **1,133** (media −0,022). La banda di rumore a 1σ su n gare è quindi `1,133·√n`:

| gare | 3 | 4 | 5 | 6 | 7 | 10 | 20 |
|---|---|---|---|---|---|---|---|
| banda ±pt | 1,96 | 2,27 | 2,53 | 2,78 | 3,00 | 3,58 | 5,07 |

`MatchAnalysis.xpts_band()` / `xpts_reading()` (in `analysis.py`) sono ora **l'unica** sorgente
del verdetto, usata da card, narrativa pre-partita e «Clima del club». Effetto: il vecchio ±2
etichettava 64 squadre su 132, la banda ne etichetta **45** — **19 verdetti (30%) spariscono
perché erano rumore**, 0 nuovi — e le **24 contraddizioni interne alla pagina vanno a 0**.
Sotto le 3 gare non si pubblica alcun verdetto («campione troppo corto»).

### 2.3 I numeri di stagione non si rapportavano a nulla

«xG creati 1,42» non dice se sia tanto o poco. Ora ogni valore esce con `×  la media del
campionato (crea di più / di meno)`, calcolato con `_league_xg_reference()` **sulla stessa fonte
della squadra**, perché i due modelli non sono confrontabili — misurato il 9/10 sulla
Bundesliga: **1,959 xG** per gara-squadra con Understat, **1,791** con FotMob.

| fonte | media xG per gara-squadra |
|---|---|
| Understat | Bundesliga 1,959 · EPL 1,636 · La Liga 1,625 · Ligue 1 1,669 · Serie A 1,671 |
| FotMob | ENG1 1,514 · ESP1 1,481 · FRA1 1,641 · GER1 1,791 · ITA1 1,489 · **NED1 1,740** · **POR1 1,365** |

**Parità fra le 7 leghe**: anche Eredivisie e Liga Portugal, che non hanno Understat, hanno il
loro riferimento (dalle statistiche gara FotMob). Nessuna duplicazione: `season_compare()` e
`_league_averages()` confrontano i **gol**, `clash_radar()` usa ancore fisse 0,5×/1,5×.

### 2.4 «PPDA 8,5 alto»: l'aggettivo sembrava riferito al numero

8,5 è un numero *basso*; «alto» è il pressing. Ora la riga dice `pressing alto · lega 13,3`, il
ⓘ dichiara le soglie (10 / 13 / 16), la media del campionato e la finestra. Dove il dato manca,
`n.d.` spiega **perché**: il PPDA lo pubblica solo Understat, che copre 5 leghe su 7, e non si
mette una stima al suo posto. Quartili misurati su 92 squadre: 5,43 / 10,84 / 12,96 / 14,52 / 25,95.

### 2.5 Riposo: data nascosta e nome della coppa buttato via

La data dell'ultima gara usciva solo oltre i 6 giorni, e la coppa diventava un generico «coppe
incluse» benché `rest_cup()` restituisca già il nome. Ora: `21 giorni di riposo (ultima gara
19/09)` sempre, e `(ultima gara 16/09, Europa League)` dove c'è la coppa (**40 riquadri**). Via
gli aggettivi «ampio»/«corto»: erano una terza soglia (≤2 giorni) diversa da quella di «Clima
del club» (≤3) e da quella misurata nei «Fattori» (≤4, studio UEFA). Dove manca il calendario
precedente (132 riquadri) il ⓘ dice che è inizio stagione o archivio incompleto.

### 2.6 La distinta pre-partita aveva una colonna voto sempre vuota

Misura: **0 titolari su 1.210** (71 schede) avevano un voto di gara prima della partita — ovvio,
non esiste ancora. La `seasonRating` della distinta FotMob copre 827 (68%, in Serie A **38%**),
mentre la **nostra** media ricalcolata dai voti gara copre **1.195 su 1.210 (99%)** ed è la
stessa base della classifica «Per media voto di stagione» della scheda. `starters()` ora
restituisce `rating_avg` / `rating_games` (con cache `_sps_cache`) e la riga pubblica
`⌀ 6,70`, con il ⓘ che dice che è la media di stagione e non il voto di questa partita. A gara
finita resta il voto della partita (8.247 su 8.250) e la media entra nel suo ⓘ.

### 2.7 Forma: verso del punteggio non dichiarato

`2-0 @ Parma` si poteva leggere al contrario. Ora l'etichetta dichiara finestra e verso —
**Forma (campionato, gol fatti-subiti)** — e ogni pallino ha `in casa contro Monza: 4-1 (gol
fatti-subiti)` (prima il tooltip scriveva «1 fatti», plurale sbagliato).

### 2.8 Il valore dei titolari era attribuito a Transfermarkt

Il ⓘ diceva «Somma Transfermarkt titolari», ma il progetto **non interroga Transfermarkt**: il
dato è `totalStarterMarketValue` della distinta FotMob (`src/fda/sources/fotmob.py`).
Attribuzione corretta.

### 2.9 Il piè di card spiegava una stringa che non esiste

«“Ruolo n.d.” = non ancora visto in distinta»: la pagina non stampa mai quella stringa (il ruolo
ignoto resta vuoto), e del resto il piè non diceva **niente** dei quattro riquadri di stagione,
cioè dei numeri più pesanti della card. Riscritto: descrive forma, xG creati/concessi col
rapporto e la fonte, xPTS con la banda, PPDA (5 leghe su 7), riposo con le coppe, indisponibili,
distinta e il significato di «⌀». Ogni soglia è comunque ripetuta nel ⓘ della propria riga.

## 3. Effetto misurato (dopo la build)

| misura | prima | dopo |
|---|---|---|
| riferimenti di lega pubblicati | 0 | **1.784** (2 per riquadro × 892 = 100%) |
| riquadri con PPDA numerico / `n.d.` spiegato | 582 / 310 muti | 604 / **288 spiegati** |
| verdetti xPTS | 64 (soglia ±2) | **in linea 598 · sopra 137 · sotto 157** (banda misurata) |
| contraddizioni card ↔ narrativa nella stessa pagina | 24 squadre | **0** |
| schede con fonti xG miste | 3 | **0** |
| celle voto nella distinta pre-partita | 0 | **1.176** (57 schede, «⌀ media di stagione») |
| «coppe incluse» | 37 | **0** (40 riquadri col nome della coppa) |
| data dell'ultima gara | solo oltre 6 giorni | **760 riquadri su 892** (il resto non ha archivio) |

## 4. Invariante nuova e test

**[44] `check_due_squadre`** (`scripts/verify_site.py`, prima di `check_numbers`): gira su
**tutte** le pagine di `site/partite` e, per entrambe le squadre, verifica struttura e piè di
card, fonte xG uguale a quella che `season_xg` userebbe, assenza di fonti miste, xG
creati/concessi + campione + xPTS/punti/scarto + PPDA **ricalcolati dai Parquet**, presenza e
valore del rapporto di lega ovunque la media esista, verdetto coincidente con `xpts_reading`,
assenza di «Transfermarkt», «Ruolo n.d.» e «coppe incluse». Esito sulla build: **446 pagine, 892
riquadri, 892 riferimenti verificati, 0 problemi**.

Test nuovi:

- `tests/test_site.py::test_xpts_banda_di_rumore_misurata` — banda e verdetti di §2.2;
- `tests/test_site.py::test_nomi_understat_agganciati` — i quattro alias di §2.1;
- `tests/test_site.py::test_card_due_squadre_riferimento_di_lega_e_verdetto` — rapporti,
  banda, pressing e distinta su una scheda resa davvero;
- `tests/test_site.py::test_titolari_media_voto_dalla_nostra_base` — §2.6;
- `tests/test_verify_scripts.py::test_verify_site_due_squadre_su_ogni_scheda` — otto
  manomissioni dell'HTML, una per difetto storico, tutte intercettate da [44];
- `tests/test_oggi_depth.py` — sezione xPTS riscritta sulla banda, più
  `test_narrative_xpts_dentro_la_banda_resta_muta`.

## 5. Gate (tutti rifatti dopo l'ultima modifica al sorgente)

- `pytest` → **549 passed** (erano 540);
- `ruff check .` → pulito;
- `fda build` → **446 schede / 2.364 fixture / 7.498 giocatori**, 4m58s;
- `scripts/verify_site.py` → **nessun problema · 185.117 controlli** (erano 169.967), con
  `[44] 446 pagine, 892 riquadri, 892 riferimenti`;
- `scripts/parita_schede.py` → **71 schede, nessuna differenza** (minimo 88% della mediana);
- `scripts/resa_375.py` → **26.628 misure · 0 problemi a 375 px**;
- HTML letto a mano su due fonti diverse: `5749694` (Inter, Understat) e `5781769`
  (Heerenveen–Excelsior, FotMob).

**Nessuna richiesta alle fonti esterne** in questa sessione (nessun `collect`, nessuna sonda,
nessun daily a mano); nessun file di dati toccato.

## 6. Residui dichiarati

- `match_info.league_id` vale **937276** (id di fase) su tutte le 73 gare NED1: ogni join con la
  lega va fatto via `fixtures`. Fuori dal perimetro di questa card, ma è una trappola per chi
  scrive query nuove.
- Il campione xG può restare **una gara avanti** rispetto alla classifica quando la fonte
  pubblica prima (oggi solo il Cagliari): dichiarato nel ⓘ, non corretto.
- La griglia dei quattro riquadri vive dentro `{% if xg %}`: oggi non sparisce mai, ma una
  squadra senza alcun dato di stagione perderebbe anche la riga del riposo.
- Coda della revisione sezione per sezione: **Panchina e posta in gioco**, **Mercato**, **Vita
  del club**, **Previsione del modello ensemble**, **Verifica approfondita**, **Confronto di
  stagione**, **Clima del club**.
