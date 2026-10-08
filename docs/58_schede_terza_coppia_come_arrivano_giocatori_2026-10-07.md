# 58 — Schede partita, terza coppia: «Come arrivano» + «I giocatori che decidono» (2026-10-07)

Direttiva dell'utente (stessa della prima e seconda coppia, `docs/57`): revisione sezione per
sezione delle schede partita, con lo stesso metodo — **misura prima → correzione → prova**
(invariante in `scripts/verify_site.py` o test in `tests/`). Questo documento è il verbale della
terza coppia; la prima («Analisi pre-partita» + «Fattori») e la seconda («Scontro tattico» +
«Fatti rilevanti») sono in produzione (`docs/57`, PR #91 fusa il 7/10/2026 alle 22:54:01Z).

Build di riferimento: 441 schede, **66 pre-partita**, 2.364 partite, 7.496 giocatori. Tutti i
conteggi «su 66» sono su quelle schede. Nessuna richiesta alle fonti esterne (nessun `collect`,
nessuna sonda, nessun daily manuale): misure sui Parquet già raccolti e sul sito generato in
locale. Nessuna quota bookmaker.

---

## 0. In breve

| # | Difetto misurato | Prima | Dopo | Prova |
|---|---|---|---|---|
| D1 | **«Come arrivano» mostrava le gare più vecchie**: il ramo FotMob di `arrival_trend` scorreva in ordine di data con un `break` a 6 — teneva le 6 più vecchie, non le più recenti. Understat prendeva già la coda giusta | 18/18 schede NED1/POR1 incoerenti con «Le due squadre» (Feyenoord: ultima in tabella il 13/09, in campo il 20/09) | finestra = 6 più recenti con xG, 66/66 coerenti | **[43a]** + test |
| D2 | **«la riga sopra misura l'intero campione»**: residuo della P1.2 — la riga di sintesi non esiste più, la frase puntava al vuoto | 56 frasi di tendenza su 56 | «le medie di stagione sono nella card della squadra» | [43a] vieta la frase |
| D3 | **«xG sparkline» in inglese a schermo** (etichetta + 2 tooltip per colonna) | 132 etichette · 264 tooltip | «xG/xGA per gara», «Andamento … (gara per gara)» | [43a] vieta la parola |
| D4 | **«forza avv.» = classifica attuale, non dichiarato**: la colonna sta su righe datate e mostra posizione/punti di oggi | 696 celle senza dichiarazione | tooltip «classifica attuale, non alla data della gara» | [43a] lo impone |
| D5 | **«Per media voto di stagione» promessa e quasi mai pubblicata**: `team_key_players` leggeva `season_rating` dalla distinta, nullo al 99,6% (73 righe su 18.445, 4 squadre su 132) | testata su 66/66, lista su 4/66 (12 voci) | top-3 per media voti gara sopra la soglia 40%, 132/132 squadre coperte | **[43b]** + test riscritto |
| D6 | **Link «sono in Infermeria» verso la card «Indisponibili»**: lo stesso difetto di `docs/57` §4, mancato in questo punto | 12 link su 10 schede | «motivo e rientro» (il nome della colonna di destinazione) | [43b] vieta il testo |
| D7 | **«titolare probabile» incondizionato**: con distinta ufficiale direbbe «probabile» (latente: oggi 0/66 ufficiali) | 102 diciture senza distinzione | «titolare» se `lineup_type` è ufficiale | [43b] a distinta ufficiale |
| D8 | **«contributo offensivo atteso» per un valore di stagione**: la testata faceva passare una media retrospettiva per un'attesa | 66/66 testate | «contributo offensivo di stagione» | [43b] vieta la parola |
| D9 | **Extra**: chip «Infermeria» nelle liste + regex di [5] **morta** (cercava «Infermeria:» col colon che non esiste, e il plurale su entrambi i lati: 0 match) | 65 chip · 0 controlli | «Indisponibili» + regex sulla marcatura reale con autotest | [5] torna viva |

Verificato senza difetto (§4): copertura degli stati (102 titolari, 0 panchinari — le probabili a
due giorni dalla gara elencano solo gli 11 + gli indisponibili —, ~40 indisponibili, il resto
fuori distinta: gli id combaciano, nessun falso); soglia 40% e minimo 90′ (soglie 126–252′,
9–16 giocatori in classifica); formula della tendenza (±0,15 dichiarato e usato); i punteggi
con trattino ASCII («2-1») sono risultati, non intervalli, e `RANGE_ASCII` non li copre di
proposito.

Residui dichiarati (§5): alias Understat mancanti (Parma, M'gladbach, Leipzig, Köln/«FC Cologne»:
2 schede con le colonne da fonti diverse); «infermeria pesante» (segnale della prossima coppia,
«Panchina»); i punti di `docs/57` §7 ancora aperti (tilt, valore titolari, duello/radar).

Gate finali (tutti rifatti da zero dopo l'ultima modifica al sorgente):

| Gate | Prima di questa revisione | Dopo |
|---|---|---|
| `pytest -q` | 534 passed | 535 passed |
| `ruff check .` | pulito | pulito |
| `fda build` | 441 / 2.364 / 7.496 | 441 / 2.364 / 7.496 |
| `verify_site` | 0 problemi · 164.729 controlli | 0 problemi · 167.255 controlli |
| `parita_schede` | 66 · identica (24 id) · min 19.697 · mediana 21.680 | 66 · nessuna differenza · min 19.931 · mediana 21.843 · max 25.720 |
| `resa_375` | 26.424 misure · 0 problemi | 26.424 misure · 0 problemi |
| `prematch_sections` | — | Come arrivano 5,4% · I giocatori che decidono 8,4% |

---

## 1. «Come arrivano»: la finestra, la frase rimasta e le parole

### D1. Le sei più vecchie invece delle più recenti (il difetto grave della coppia)

**Cosa non andava.** `arrival_trend` ha due rami: Understat (5 leghe) prende le ultime `n` gare con
`tail(n)`; il ramo FotMob (NED1/POR1 + 4 colonne di ripiego, §1.5) scorreva le finite in ordine di
data e si fermava con `if len(rows) == n: break` — tenendo le **prime** 6, cioè le più vecchie, e
scartando la più recente. Con 7 giornate giocate ogni colonna FotMob restava indietro di una
partita: la più importante per una card che si chiama «Come arrivano».

**Misura.** Confronto fra le pill V/N/P di «Come arrivano» (ultime 5 per colonna) e i pallini di
«Le due squadre» sulle 66 schede: **48 coerenti, 18 incoerenti — e le 18 sono esattamente le
schede di NED1 e POR1** (9 + 9), mentre le 5 leghe Understat sono tutte coerenti: un difetto di
parità. Esempio (`5781759`, Feyenoord–AZ): il Feyenoord ha 7 finite (09/08 → 20/09, tutte con xG
su entrambi i fronti) ma la tabella mostrava 09/08 → 13/09 — il 5-0 all'Utrecht del 20/09 fuori,
la tendenza calcolata sulla finestra sbagliata.

**Correzione.** Via il `break` (e il `tail(n*2)` che limitava i candidati: il ciclo su ~40 gare è
gratuito) e `rows = rows[-n:]` dopo il dedup — la coda, come il ramo Understat. Stesso ordine di
stampa (vecchie → recenti), stessa tendenza, stessa sparkline: cambia solo quali gare entrano.

**Prova.** Test `test_arrival_trend_fotmob_tiene_le_piu_recenti` (7 finite, n=6: dentro il 07/09,
fuori il 01/09) e invariante **[43a]**: ogni riga contro il ricalcolo (data/esito/punteggio/xG) +
**freschezza indipendente dal codice** (nessuna gara con xG più recente della finestra mostrata,
per entrambe le fonti) + tendenza rifatta dai numeri in pagina. Sul sito pre-correzione [43a]
segnalava 6 righe + 1 freschezza per ognuna delle 36 colonne FotMob con 7 finite.

### D2. «la riga sopra misura l'intero campione»

La frase di tendenza chiudeva con «Valuta il gioco recente, non i punti: la riga sopra misura
l'intero campione» — ma la riga di sintesi l'ha tolta la P1.2 (`docs/30`): «la riga sopra» non
esiste più. Presente su **56 frasi su 56** (le colonne con 6 righe). Ora: «le medie di stagione
sono nella card della squadra» — le stesse parole della testata della card, che già dice dove
stanno. [43a] boccia la pagina se la frase torna.

### D3. «sparkline» in italiano

Ogni colonna mostra due mini-grafici con l'etichetta visibile «xG sparkline» (132) e i tooltip
«Sparkline xG creati (gara per gara)» / «Sparkline xGA» (264): l'unica parola inglese delle due
card (regola E: mai inglese a schermo; i termini calcistici come «pressing» sono un'altra cosa,
qui l'italiano esiste). Ora «xG per gara» / «xGA per gara» e «Andamento xG creati (gara per gara)»
/ «Andamento xGA (gara per gara)». [43a] vieta la parola nel blocco. (`spark_xg` resta dov'è: è
un nome di variabile, il codice è in inglese per regola.)

### D4. «forza avv.»: la classifica è quella attuale

La colonna mostra posizione e punti dell'avversario presi dalla classifica **attuale**
(`standing()`: FotMob, poi ESPN) — non alla data della gara. Su righe datate («23/08 @ Cambuur»)
il lettore legge il passato con i numeri di oggi, e niente lo diceva (696 celle). Ora l'intestazione
ha il tooltip «Posizione e punti in classifica attuale, non alla data della gara»; [43a] impone un
tooltip per ogni tabella. Lo storico delle classifiche passate non c'è nei Parquet: dichiarare è
l'unica correzione onesta.

### D5. Contesto misurato (non difetti)

Fonti per colonna sulle 66 schede: **Understat 92, FotMob 40** — le leghe 57/61 tutte FotMob (18 +
18), le altre quasi tutte Understat. Righe mostrate: 698 (8/10/12 per scheda). Avversario «—»:
2 righe su 698 (Understat con data non riconciliata alle fixtures); «forza avv.» «—»: le stesse 2.
Frasi di tendenza: 56 colonne.

---

## 2. «I giocatori che decidono»: la classifica fantasma e le parole

### D5. «Per media voto di stagione»: promessa su 66, pubblicata su 4

**Cosa non andava.** La testata dice «Sotto, la classifica per media voto di stagione» su tutte le
66 schede, ma la lista usciva su **4 schede** (12 voci: Ipswich–Fulham, Liverpool–Man City,
Levante–Siviglia, Rayo–Athletic). Causa: `team_key_players` leggeva `season_rating` dalla
distinta, che la fonte pubblica quasi mai — **73 righe su 18.445 (0,4%), 4 squadre su 132, 2
partite** (leghe 47/87). Non un difetto di raccolta nostro (il parser legge il campo quando c'è):
la base era sbagliata.

**Correzione.** Riscritta sulla media dei voti gara (`rating_avg` da `player_stats`: la stessa base
della tabella dei decisivi, disponibile ovunque) con la **stessa soglia** della card (40% dei
minuti del più impiegato, minimo 90′: senza soglia un 9,9 in una gara guiderebbe la classifica).
Misurato prima di scrivere: **132 squadre su 132** hanno almeno 3 votati sopra soglia — la
classifica promessa ora esce su 66/66. La chiave `season_rating` diventa `rating_avg` anche nel
template (la provenienza non si camuffa). La lista resta complementare alla tabella: ordina per
voto, quindi promuove anche chi non crea xG (difensori, portieri, registi).

**Prova.** Test `test_team_key_players_media_voto_sopra_soglia` (riscritto: ordine, soglia che
esclude il 9,9 a 90′, escluso senza voto, gol/assist, limite n, squadra vuota) e **[43b]**: ogni
voce contro il ricalcolo, soglia stampata contro il codice, ogni riga dei decisivi sopra la soglia.
Sul sito pre-correzione [43b] segnalava le 12 voci vecchie (giocatori e voti diversi).

### D6. «sono in Infermeria» → «motivo e rientro»

Quando il primo dei decisivi è indisponibile (12 casi su 10 schede) la card diceva «motivo e
rientro sono in **Infermeria**» — lo stesso difetto di `docs/57` §4 (testo diverso dal titolo di
destinazione «Indisponibili»), mancato in questo punto. Ora il link dice **«motivo e rientro»**:
il nome della colonna dove si atterra («motivo · rientro»), che è esattamente ciò che il lettore
trova. [43b] vieta `>Infermeria</a>` nel blocco. (L'ancora `id="infermeria-…"` resta: gli id non
sono testo visibile, come in §4.)

### D7. «titolare probabile» anche a distinta ufficiale (latente)

Lo stato dei decisivi diceva «titolare probabile» senza guardare `lineup_type` — mentre la card
«Le due squadre» distingue «Formazione» da «Formazione probabile». Oggi 0 schede su 66 hanno la
distinta ufficiale (tutte probabili a due giorni dalla gara: 102 «titolare probabile», 0 «in
panchina» — le probabili elencano gli 11 + gli indisponibili, senza panchinari), quindi il
difetto è latente: ora è «titolare» se la distinta è ufficiale. [43b] lo impone quando capita.

### D8. «contributo offensivo atteso» → «di stagione»

«In alto il contributo offensivo **atteso**: (xG + xA) per 90 minuti…» — ma il numero è una media
retrospettiva di stagione, non un'attesa per questa gara (l'avviso sull'indisponibile lo diceva
già: «il valore per 90 è stagionale»). Ora «contributo offensivo **di stagione**» (testata +
docstring, le uniche 2 occorrenze). [43b] vieta la parola.

---

## 3. Extra fuori coppia: D9 (chip «Infermeria» + regex morta)

La chip nelle liste («Oggi»/«Prossime») diceva **«Infermeria»** (65 occorrenze) mentre tooltip
(«Indisponibili dalla distinta») e card di destinazione («Indisponibili») dicono altro: ora
«Indisponibili». E la regex di [5] che verificava le chip era **morta**: cercava «Infermeria:»
col colon (la marcatura non ce l'ha) e il plurale su entrambi i lati (`it_plural` fa anche «1
assente») — **0 match**, controllo silenziosamente spento. Riscritta sulla marcatura reale con un
**autotest**: il numero di match deve pareggiare il gancio `fact-absence`, così non può morire di
nuovo in silenzio. Dopo: [5] conta le chip (65) e le confronta con la distinta.

Non toccato: «infermeria pesante» (segnale + legenda della card «Panchina», minuscolo, 66 + ~63
occorrenze) — è la sezione della prossima coppia, decide lei.

---

## 4. Verificato senza difetto

- **Stati dei decisivi**: 102 starter, 0 sub, ~40 unavailable, il resto senza stato perché fuori
  distinta — gli id di `player_stats` e `lineup` combaciano (Lens: 13/17 e 13/14; i mancanti sono
  allenatore e indisponibili senza minuti), nessun falso «assente» e nessun «titolare» mancato.
- **Soglia 40%**: valori 126–252′ (moda 180 e 252), 9–16 giocatori in classifica per colonna;
  «Nessun giocatore sopra la soglia» mai mostrato (0/132 colonne).
- **Formula della tendenza**: ultime 3 contro precedenti, verdetto ±0,15 — dichiarato e usato
  (56/56 rifatte dai numeri in pagina da [43a]).
- **Punteggi col trattino** («2-1» in «Come arrivano», forma, precedenti): sono risultati, non
  intervalli — `RANGE_ASCII` (`\d+,\d+-\d+,\d+`) non li copre di proposito.
- **Deep table**: 396 righe (3 per colonna su 132), tutte sopra soglia; voto = media dei voti gara.
- **Coerenza dopo D1**: 66/66 (da script dedicato; il ramo FotMob ora prende la coda).

---

## 5. Aperti e residui

1. **Alias Understat** (nuovo): Parma («Parma Calcio 1913»), M'gladbach («Borussia M.Gladbach»),
   RB Leipzig («RasenBallsport Leipzig») e Köln («FC Cologne») cadono nel ramo FotMob per
   normalizzazione del nome — la fonte li copre. Effetto oggi: 2 schede con le colonne da fonti
   diverse (Inter–Parma, RB Leipzig–Francoforte). La correzione (alias in `teams.py`) sposta i
   numeri in più card (Scontro, Le due squadre, Come arrivano, Fattori): lotto a sé, con gate
   pieni — non un ritocco di questa coppia.
2. **«infermeria pesante»**: segnale e legenda della card «Panchina e posta in gioco» — alla
   prossima coppia (naming: segnale minuscolo contro card «Indisponibili»).
3. **`top_players` post-partita** (card «Migliori in campo»): mostra «stagione X» quando c'è —
   condizionale, non promessa rotta; da rivalutare con la revisione delle post-partita.
4. Da `docs/57` §7, ancora aperti: tre tilt non cablati, valore titolari assente su 42/66,
   ridondanza duello chiave ↔ radar.
5. Prossime coppie: **Panchina e posta in gioco** + **Mercato: arrivi e partenze**, poi Vita del
   club, Previsione del modello ensemble, Precedenti, Verifica approfondita.

---

## 6. Appendice — come sono state prese le misure (per riprodurle)

```bash
.venv/bin/fda build                                            # 441 / 2.364 / 7.496 (~5 min)
.venv/bin/python scripts/verify_site.py --site site --data data/processed   # 0 problemi · 167.255 controlli
#   [43] lati/righe/voti · [5] chip nelle liste · [41]/[42]/[22b]/RANGE_ASCII invariati
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site
.venv/bin/python -m scripts.resa_375
.venv/bin/pytest -q && .venv/bin/ruff check .
```

I conteggi per scheda/colonna/riga sono letti dalle pagine generate (`site/partite/*.html`,
blocchi `id="arrivi"` e `id="giocatori"`) e dai Parquet (`fixtures`, `team_stats`,
`understat_team_matches`, `lineup`, `player_stats`, `match_info`): riepiloghi stampati a schermo,
mai dati grezzi. La coerenza V/N/P confronta le ultime 5 pill di ogni colonna coi 5 pallini di
«Le due squadre». `season_rating`: 73 non-nulli su 18.445 righe di `lineup` (4 squadre, 2 partite).

**Cosa non è verificato da qui** (dichiarato, non taciuto): le fonti esterne non sono raggiungibili
dal sandbox e **non sono state interrogate** — niente `collect`, niente sonde, nessun `daily`
manuale; quanto sopra riguarda i dati già raccolti e il sito generato. La resa **visiva** non è
stata vista in un browser: il gate a 375 px è statico (geometria e caratteri), non un giudizio
estetico.

---

## 7. Incidente di lavorazione: scrittura parallela corrotta (lezione)

Cinque modifiche al template lanciate in parallelo non si sono solo perse per strada
(last-wins: 3 «success» erano falsi, §2): una ha anche **corrotto byte altrove nel file** —
la barra 1X2 della previsione (`style="wids="...`) su tutte le schede pre-partita del build
23:49Z. L'ha intercettata la suite (`test_barra_1x2...`, più altri due test che leggono la
barra), non la verifica dei numeri — il gate dei test va rifatto sempre, anche quando «si
sono toccati solo testi». Riparato byte per byte dall'originale, diff riga per riga contro
`main` (7 coppie, tutte volute), rebuild e gate pieni rifatti da zero.

Stessa lezione per il seed dei test: `end_to_end` e `p22` presupponevano la card «I giocatori
che decidono» dai `season_rating` della distinta — con D5 la card vuole i voti gara, e i due
test ora seminano `rating_title`/`minutes_played` come la raccolta vera.
