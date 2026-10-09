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
| riferimenti di lega pubblicati | 0 | **996** (tutti i riquadri con ≥3 gare di campione) |
| riquadri con PPDA numerico / `n.d.` spiegato | 582 / 310 muti | 604 / **288 spiegati** |
| verdetti xPTS | 64 (soglia ±2) | **in linea 598 · sopra 137 · sotto 157** (banda misurata) |
| contraddizioni card ↔ narrativa nella stessa pagina | 24 squadre | **0** |
| schede con fonti xG miste | 3 | **0** |
| celle voto nella distinta pre-partita | 0 | **1.176** (57 schede, «⌀ media di stagione») |
| «coppe incluse» | 37 | **0** (40 riquadri col nome della coppa) |
| data dell'ultima gara | solo oltre 6 giorni | **760 riquadri su 892** (il resto non ha archivio) |
| riquadri «Pressing · riposo» | spariva con gli xG | **892 = uno per squadra, sempre** |

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

- `pytest` → **553 passed** (erano 540);
- `ruff check .` → pulito;
- `fda build` → **446 schede / 2.364 fixture / 7.498 giocatori**, 5m22s;
- `scripts/verify_site.py` → **nessun problema · 184.245 controlli** (erano 169.967), con
  `[44] 446 pagine, 762 riquadri, 498 riferimenti` più il ricalcolo della finestra;
- `scripts/parita_schede.py` → **71 schede, nessuna differenza** (minimo 88% della mediana);
- `scripts/resa_375.py` → **26.565 misure · 0 problemi a 375 px**;
- HTML letto a mano su quattro casi: `5881181` (Köln–M'gladbach, i due alias nuovi),
  `5887650` (Marítimo–Porto, fonte FotMob), `5881154` (2ª giornata, campione di 1 gara) e
  `5749640` (1ª giornata, nessuna gara precedente).

**Nessuna richiesta alle fonti esterne** in questa sessione (nessun `collect`, nessuna sonda,
nessun daily a mano); nessun file di dati toccato.

## 6. Residui dichiarati

- `match_info.league_id` vale **937276** (id di fase) su tutte le 73 gare NED1: ogni join con la
  lega va fatto via `fixtures`. Fuori dal perimetro di questa card, ma è una trappola per chi
  scrive query nuove.
- Il campione xG può restare **una gara avanti** rispetto alla classifica quando la fonte
  pubblica prima (oggi Cagliari e Lecce): dichiarato nel ⓘ, non corretto.
- Il PPDA di stagione è la **media dei PPDA di gara**, non il rapporto delle somme: Understat
  pubblica solo il valore per partita. Limite dichiarato nel ⓘ insieme all'errore standard.
- Coda della revisione sezione per sezione: **Panchina e posta in gioco**, **Mercato**, **Vita
  del club**, **Previsione del modello ensemble**, **Verifica approfondita**, **Confronto di
  stagione**, **Clima del club**.

## 7. Secondo giro (stesso giorno): la card guardava nel futuro

Richiesta dell'utente dopo la prima consegna: «verifica che sia tutto corretto, ad esempio xG
creati / gara e xG concessi / gara; mi sembra che ci sia qualche errore».

**L'aritmetica era giusta**: 892 celle ricalcolate dai Parquet con codice indipendente (non
`season_xg`), **0 discordanze** su valori, campione, fonte e rapporti; `len(xg) == len(xga)` su
tutte le squadre (l'etichetta «stesse N gare» non mentiva); la media xG di lega coincide con la
media xGA a meno di 1e-15 in tutte e 5 le leghe Understat (quindi usare la media xG come
riferimento anche per i gol concessi è corretto); `match_info` non contiene gare di coppa.

**L'errore era la finestra temporale.** `season_xg()` leggeva *tutta* la stagione raccolta,
senza guardare la data della partita descritta:

| misura (schede già giocate) | valore |
|---|---|
| riquadri il cui campione includeva gare **successive** alla partita | **750 su 750 (100%)** |
| gare «dal futuro» per riquadro | mediana **3**, massimo **7** |
| scostamento dello xG creati per gara | mediana **0,23**, 90° pct **0,74**, massimo **3,39** |
| riquadri con scostamento > 0,50 xG | **115** |
| riquadri di squadre che a quella data **non avevano ancora giocato** | **130** |

Esempio: Frankfurt–Augsburg del **6 settembre** dichiarava «Augsburg 2,14 xG creati per gara
(Understat, 4 gare)» — quattro gare di cui tre giocate *dopo*. Alla vigilia l'Augsburg aveva una
gara sola, da 5,54 xG. Nella stessa card la riga «Forma» era invece corretta (`form()` filtra
`utc_kickoff < before`): due finestre diverse a cinque centimetri di distanza.

### Correzione

1. `season_xg`, `season_style`, `_season_xg_split` e `_league_xg_reference` accettano `before`;
   la scheda passa il proprio calcio d'inizio, **anche al riferimento di lega** (confrontare 4
   gare di una squadra con 7 giornate di campionato sarebbe un rapporto fra finestre diverse).
   Tutti i consumatori della scheda sono allineati — card «Le due squadre», «Clima del club»
   (verdetto xPTS), «Fattori» (PPDA), «Scontro tattico» e radar — così la pagina non contiene
   due versioni dello stesso numero. Sulle **71 schede pre-partita non cambia nulla** (il calcio
   d'inizio è nel futuro): verificato squadra per squadra.
2. **Soglia di campione per il rapporto di lega** (`XG_RATIO_MIN_GAMES = 3`): lo xG per
   gara-squadra ha sd **1,036** su media **1,692**, quindi l'errore standard del rapporto vale
   **±0,61×** dopo una gara e **±0,43×** dopo due — un «2,74× la media» su una partita sola è
   rumore stampato in grassetto. Sotto le 3 gare la card scrive «campione troppo corto per il
   confronto con la lega» (**253 riquadri**).
3. **Etichetta del pressing** con la stessa soglia: il PPDA per gara-squadra ha sd **6,50**,
   cioè ±6,5 su una gara e ±3,8 su tre, contro fasce larghe **3 punti**; sotto le 3 gare esce il
   numero senza aggettivo (**192 riquadri**) e il ⓘ dichiara sempre l'errore standard.
4. **La griglia non è più annidata in `{% if xg %}`**: le 130 squadre senza gare precedenti
   mostrano «nessuna gara di campionato prima di questa» e **conservano la casella del riposo**
   — chiude anche la fragilità latente dichiarata in §6 della prima stesura.
5. Dichiarazione in testa al piè di card: «**tutti i numeri di questa card sono fermi alla
   vigilia di questa partita**», più i ⓘ di xPTS e PPDA riscritti sulla nuova finestra. Corretto
   anche il plurale «stesse 1 gara» → «stessa gara».

### Invariante estesa

**[44]** ora ricalcola il campione **dal calendario e da Understat senza passare da
`season_xg`**: se il codice perdesse il taglio, il gate lo vede anche se l'HTML è coerente col
codice rotto (test `test_verify_site_due_squadre_finestra_alla_vigilia`, che simula proprio
quella regressione). Verifica inoltre le due caselle «Pressing · riposo» su ogni scheda, la
dichiarazione per le squadre senza gare precedenti e il rispetto della soglia del rapporto.
Test nuovi: `test_numeri_di_stagione_fermi_alla_vigilia`,
`test_rapporto_di_lega_solo_con_campione_che_lo_regge`,
`test_card_due_squadre_senza_gare_precedenti_resta_completa`.

## §8 — Terzo giro: la card letta sulla scheda PSV–Heerenveen (2026-10-09)

Punto di partenza: lo screenshot della card del **PSV** nella scheda di oggi
(`site/partite/5781762.html`, PSV–Heerenveen, NED1, 9/10 18:00 UTC). Rilettura sezione per
sezione, con ricalcolo indipendente dai Parquet.

### Quello che la card diceva giusto (verificato, nessuna modifica)

| Sezione | Controllo fatto | Esito |
|---|---|---|
| Forma | `V V V V P` contro i risultati nei Parquet (Twente 3-2 PSV = sconfitta), ordine vecchia→recente, glifi ▲/—/▼ e colori distinti in `site.css` 274-288 | corretta |
| xG creati / concessi | 2,80 (1,61× su NED1 1,740) e 1,31 (0,75×) su 7 gare, campione fermo alla vigilia | corretti |
| xPTS | 14,8 contro 16 punti ricontati a mano (1+3+3+3+3+3+0), banda ±3,0 su 7 gare → «in linea» | corretto |
| Pressing | «n.d.»: l'Eredivisie non è coperta da Understat, l'unica fonte PPDA | corretto |
| Riposo | ultima gara 20/09 (tutte le 18 squadre NED1 a 7 gare), prossima oggi → **19 giorni**; la Champions del 10/09 è precedente e `_rest_source()` include davvero `cup_fixtures` | corretto |
| Titolari fuori | «2 titolari abituali fuori» = i due «· titolare» in tabella | coerente |

### Difetto A — il totale dell'infermeria non era la somma delle righe

Il badge pubblicava `contrib_lost_p90`, che sommava la **stima stabilizzata**, mentre ogni riga
pubblica il **grezzo** quando il campione supera i 90′ (`contrib_p90 = grezzo if pubblicabile
else stima`). PSV: badge «◎ 1,92» contro 0,91+0,46+0,35+0,13+0,12 = **1,98**.

Misura sulla build precedente: **101 pannelli su 118 (86%)** con totale ≠ somma della colonna,
scarto mediano **0,040**, massimo **0,670** (mid 5881179, tid 8406: 1,34 contro 2,01 — il 33% in
meno). Viola la regola [31]/docs/22: *una somma stampata è la somma delle cifre stampate*.

Correzione in `analysis.py::absences_weight`: il totale somma **i valori pubblicati riga per
riga**, arrotondati come la tabella li stampa (`displayed(·, 2)`, la stessa convenzione di
`displayed_sum`) — senza l'arrotondamento per riga un pannello su 141 restava fuori di 0,02 per
accumulo. Dopo la ricostruzione: **141 pannelli, 0 scostamenti**; PSV «1,97», somma della
colonna 1,97.

### Difetto B — chi non ha numeri spariva dalla lettura del badge

«Indisponibili (9) · 1,92» non diceva che **4 dei 9** non hanno minuti in stagione e quindi non
entrano nel totale (**202 assenti senza dati su 87 pannelli**). Ora `absences_weight` restituisce
anche `con_dati` e il badge scrive «**(5 su 9 con minuti)**» quando i due numeri divergono
(**83 badge**), col ⓘ che spiega la composizione del totale.

### Difetto C — 197 righe su 507 (39%) senza ruolo e senza spiegazione

La cella del nome restava muta quando la fonte non dà il ruolo (Schouten e Nagalo nella card
PSV). Ora la pillola c'è sempre: «**ruolo n.d.**» con il ⓘ «il giocatore non è ancora comparso in
una distinta di questa stagione, l'unica fonte di ruolo che raccogliamo». Nessuna riga resta muta
(507 su 507 con pillola).

### Invariante estesa

**[44]** controlla ora anche l'infermeria dentro «Le due squadre», su ogni scheda: il totale deve
coincidere con la somma della colonna «impatto» (tolleranza 0,011) e ogni riga deve avere la
pillola del ruolo. Test: i casi 10 e 11 di `test_verify_site_due_squadre_su_ogni_scheda` e
`test_absences_weight_total_is_the_sum_of_the_published_rows` (con la stima forzata lontana dal
grezzo: col codice vecchio fallisce, controprova eseguita).

### Stato dopo il terzo giro

pytest **554 passed** · ruff pulito · build 446/2.364/7.498 · `verify_site` **0 problemi ·
184.381 controlli** (`[44] 446 pagine · 762 riquadri · 498 riferimenti`) · `parita_schede` nessuna
differenza · `resa_375` 26.565 · 0.

## §9 — Pressing su tutte e 7 le leghe (2026-10-09, quarto giro)

### Il buco

La casella «Pressing · riposo» pubblicava il **PPDA di Understat**, che copre 5 leghe su 7:
**288 caselle su 892 (il 32%)** dicevano «n.d.», e sono tutte e sole quelle di **Eredivisie e
Liga Portugal**. Due campionati su sette restavano senza alcun numero di pressing: la disparità
più grossa rimasta nella card.

### La misura (prima del codice)

FotMob salva per **ogni** gara di tutte le leghe i passaggi giocati nella propria metà campo,
i contrasti, gli intercetti e i falli: **750 gare-squadra su 750**. Da qui l'indice

> **passaggi che l'avversario gioca nella sua metà campo ÷ azioni difensive della squadra**

cioè l'idea del PPDA con una fonte che copre tutto. Misure sul corpus del 2026-10-09:

| | valore |
|---|---|
| per gara-squadra | media **5,52**, sd **1,99** (p5 2,70 · p95 9,02) |
| per squadra (rapporto di somme) | media **5,36**, sd 0,98 |
| medie di lega | ENG1 5,12 · ESP1 5,15 · FRA1 5,70 · GER1 5,10 · ITA1 5,70 · NED1 5,14 · POR1 5,30 |
| errore standard del rapporto | ±0,21 a 3 gare · ±0,17 a 5 · ±0,14 a 7 |
| **validazione** contro il PPDA Understat (96 squadre) | Pearson **0,58**, Spearman **0,63**; per lega da +0,31 (GER1) a +0,82 (ENG1, ITA1); stessa fascia su 3 nel 56% dei casi, **fasce opposte solo 6 su 96** |

Il valore di stagione è un **rapporto di somme** (totale passaggi ÷ totale azioni), non la media
dei rapporti di gara: una partita con poche azioni difensive non pesa come una intera — lo stesso
difetto che il registro segnalava per il PPDA di stagione.

### Le scelte

1. **Non si chiama PPDA**: correla ma non coincide (le scale non sono confrontabili). In card è
   «*n,nn* pass. concessi / azione dif.», col ⓘ che definisce la metrica e la fonte.
2. **Il PPDA di Understat non si perde**: resta nel ⓘ della stessa casella dove la lega è
   coperta (**508 caselle**) e resta riga di confronto in «Scontro tattico».
3. **Etichetta solo oltre il rumore**: «pressa alto» / «lascia giocare» appaiono solo se lo
   scarto dalla media di lega supera l'errore standard del campione (**151 etichette**,
   distribuite su tutte le leghe: ENG1 22 · ESP1 34 · FRA1 11 · GER1 11 · ITA1 26 · NED1 32 ·
   POR1 15). Sotto le 3 gare niente rapporto, come per gli xG.
4. **Ripiego dichiarato**: dove FotMob non ha quelle gare in archivio ma Understat sì (inizio
   stagione), la casella pubblica il PPDA con l'etichetta «PPDA (Understat)» invece di «n.d.» —
   caso trovato dal gate stesso sulla scheda `5868012`.

### Il risultato

| | prima | dopo |
|---|---|---|
| caselle con un numero di pressing | 604/892 (5 leghe) | **760/892 (tutte e 7)** |
| copertura per lega | 80-89% · **NED1 0% · POR1 0%** | 80-88% in **tutte** (il resto è la prima giornata) |

### Invariante estesa

**[44]** ricalcola l'indice dai Parquet per entrambe le squadre di ogni scheda, controlla che il
numero di caselle piene coincida con quelle calcolabili, che il rapporto e l'etichetta stampati
siano quelli attesi e che il PPDA Understat resti leggibile dove la lega è coperta. Test nuovi:
`test_season_pressing_su_tutte_le_leghe`,
`test_season_pressing_etichetta_solo_oltre_il_rumore`, più il caso 10bis di
`test_verify_site_due_squadre_su_ogni_scheda` (indice manomesso e casella svuotata).

### Stato

pytest **556 passed** · ruff pulito · build 446/2.364/7.498 · `verify_site` **0 problemi ·
187.107 controlli** · `parita_schede` nessuna differenza · `resa_375` 26.565 · 0.
