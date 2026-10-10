# 76 — Card «Le due squadre»: controllo a 360 gradi (2026-10-10)

Richiesta dell'utente: «verifica e revisiona come il sito presenta le schede di ogni partita —
della card "Le due squadre" fai un controllo a 360 gradi di cosa propone e come lo propone,
cosa si deve aggiustare e cosa aggiungere». Metodo `docs/00` B.10: per ogni punto **misura →
correzione → invariante o test**; perimetro **tutte le schede** (build del 2026-10-10 13:29
UTC: 470 pagine, 940 riquadri di squadra, 89 pre-partita).

La card era già stata revisionata il 9/10 in quattro giri (`docs/64`, PR #97); restavano in
coda le tre voci E di `docs/65` §2 (incrocio attacco–difesa, trend contro media di stagione,
assenti collegati alle notizie). Il controllo le riprende una per una e aggiunge due difetti
nuovi trovati dall'audit.

## §1 — Difetto: la gara descritta entrava nel proprio campione «alla vigilia»

### La misura

L'audit (`scripts/audit_due_squadre.py`, censimento della sezione su tutte le pagine +
confronto con `understat_team_matches`) ha trovato **3 schede finite con 6 riquadri** in cui il
campione di stagione includeva **la partita stessa descritta dalla scheda**:

| scheda | gara | data Understat | kickoff FotMob |
|---|---|---|---|
| `5749662` | Cagliari–Lecce | 16:00 | 16:30 |
| `5802918` | Lille–PSG | 18:45 | 19:00 |
| `5868012` | Atlético Madrid–Málaga | 19:00 | 19:05 |

Understat data la gara qualche minuto **prima** del calcio d'inizio FotMob: il taglio
`date < before` introdotto in `docs/64` §7 la lasciava passare. Conseguenze visibili:
Atlético–Málaga pubblicava «xG creati 1,34 (Understat, 1 gara)», «xPTS 2,4 vs 3» e «PPDA 7,5»
— tutti numeri **della partita stessa** — presentati come «stagione alla vigilia», mentre la
forma (correttamente vuota) e il piè di card («tutti i numeri sono fermi alla vigilia»)
dicevano il contrario. Il riferimento di lega delle stesse schede includeva le due righe.

Perché i gate non lo vedevano: l'oracolo indipendente dell'invariante [44]
(`gare_prima` in `scripts/verify_site.py`) applicava lo **stesso** taglio ingenuo
`date < ko`, quindi generatore e verificatore erano d'accordo sull'errore.

### La correzione

Una squadra gioca al più **una partita in 24 ore**: le righe Understat delle due squadre
della gara descritta entro 24 ore dal calcio d'inizio sono esattamente quella gara.

- `analysis.py`: `_squadre_descritta()` ricava dal calendario le due squadre della partita
  della scheda (team_id + calcio d'inizio); `_us_alla_vigilia()` applica il taglio
  `date < before` **escludendo** quelle righe. Usato dal campione di `season_xg` e dalla
  media di lega di `_league_xg_reference` (stessa finestra per entrambi, cache aggiornata).
  Il ramo FotMob non è toccato: il suo taglio usa i kickoff dello stesso calendario
  (`kickoff < before`, l'uguaglianza esclude la gara).
- `verify_site.py` [44]: l'oracolo `gare_prima` applica la stessa regola **senza passare dal
  generatore** — se il taglio sparisce dal codice, il gate vede lo scarto anche se l'HTML è
  coerente col codice rotto (lo stesso principio di `docs/64` §7).

### L'effetto (misurato dopo la build)

| riquadro | prima | dopo |
|---|---|---|
| Cagliari (`5749662`) | «1 gara» (la gara stessa) | **2 gare** (22/08 e 30/08, verificate sui Parquet) |
| Lecce (`5749662`) | «1 gara» (la gara stessa) | **2 gare** (23/08 e 31/08) |
| Lille (`5802918`) | «1 gara» (la gara stessa) | **1 gara** (23/08) |
| PSG (`5802918`) | «1 gara» (la gara stessa) | **1 gara** (23/08) |
| Atlético Madrid e Málaga (`5868012`) | numeri della gara spacciati per stagione | **«nessuna gara di campionato prima di questa»** |

I riquadri con la dichiarazione «nessuna gara prima» passano da 130 a **132** e tornano a
coincidere esattamente con i riquadri senza forma (132) e senza riposo (132): le tre misure,
che prima divergevano di 2, ora si spiegano a vicenda.

Test: `tests/test_site.py::test_finestra_vigilia_esclude_la_gara_descritta` (riga a −5 min
esclusa, riga a −25 ore inclusa).

## §2 — Aggiunta: la striscia «Attacco contro difesa» (voce E1 di docs/65)

Le quattro caselle xG dicono attacco e difesa di ogni squadra contro la media del campionato,
ma l'incrocio che risponde a «l'attacco di A contro la difesa di B» restava da fare a mente.
Misura di copertura: sulle **89 schede pre-partita** della build, **89 su 89** hanno entrambe
le squadre con i due rapporti di lega (campione ≥3 gare, stessa fonte) — a metà ottobre il
campionato è abbastanza avanti perché la condizione sia sempre vera; a inizio stagione la
striscia semplicemente non esce.

`attacco_contro_difesa()` in `analysis.py` restituisce i quattro rapporti solo se:

1. la gara **non è finita** (l'incrocio serve all'attesa, non al racconto);
2. entrambe le squadre hanno `xg_ratio` **e** `xga_ratio` (niente confronti su metà campione);
3. le due squadre hanno la **stessa fonte** xG (i due modelli hanno scale diverse, `docs/64`
   §2.3: oggi 0 schede a fonti miste grazie agli alias, ma la condizione resta esplicita).

Resa: una riga a tutta larghezza dentro la card, «Espanyol crea 0,84× la media del campionato
e affronta una difesa che concede 0,75× · Atlético Madrid crea 1,21× e affronta una difesa
che concede 0,84×», col ⓘ che dichiara la convenzione (sopra 1,00× = più della media) e che
sono gli stessi numeri delle quattro caselle, già letti uno contro l'altro. Il piè di card la
descrive. Nessun numero nuovo: solo i quattro rapporti già verificati da [44].

Invariante: **[44] estesa** — su ogni scheda verifica presenza/assenza della striscia contro i
requisiti ricalcolati e, quando c'è, che i quattro numeri stampati siano quelli attesi.
Test: `test_attacco_contro_difesa_solo_quando_regge` (le quattro condizioni),
`test_card_due_squadre_attacco_contro_difesa_in_pagina` (resa e assenza a gara finita), casi
12 di `test_verify_site_due_squadre_su_ogni_scheda` (numero manomesso, striscia rimossa,
striscia su gara non più pre-partita).

## §3 — Difetto: 62 pannelli pre-partita muti sulla distinta (3 anche sulle assenze)

### La misura

Audit sui 178 pannelli pre-partita: **62** non avevano distinta pubblicata (la fonte la rende
disponibile a ridosso del calcio d'inizio; le schede più lontane non ce l'hanno ancora) e
**non dicevano nulla** — il lettore non distingueva «non ancora pubblicata» da «dato perso».
Di questi, **3** (Telstar in `5781774`, Toulouse in `5802957`, Atlético Madrid in `5868094`)
non avevano neppure la lista degli indisponibili: silenzio completo. La direttiva utente del
2026-09-08 chiede proprio di distinguere *dato assente*, *non ancora pubblicato* e *fallback*.

### La correzione

`match.html`: dopo il blocco della distinta, `{% elif c.status != 'finished' %}` dichiara:

- «**Formazione non ancora pubblicata dalla fonte**: gli indisponibili qui sopra sono
  l'ultimo aggiornamento raccolto e possono cambiare a ridosso del calcio d'inizio» — quando
  la lista degli assenti c'è ma la distinta no (59 pannelli);
- «**La fonte non ha ancora pubblicato la distinta di questa squadra**: formazione e
  indisponibili compariranno a ridosso del calcio d'inizio» — quando non c'è nulla (3).

Dopo la build: **62 dichiarazioni su 62 pannelli senza distinta** (59 + 3), 0 pannelli muti.
Le schede finite non sono toccate (62 = tutte le distinte mancanti sono pre-partita: le 381
finite hanno la distinta 940−878 = 62 volte in meno, conto esatto).
Test: `test_card_due_squadre_distinta_non_pubblicata_dichiarata`.

## §4 — Voci E2 ed E3 misurate e non pubblicate

- **E2 (trend ultime 3-5 gare contro la media di stagione)**: è già pubblicato dalla card
  «Come arrivano» (`docs/60`): xG creati e concessi delle ultime 3 contro le 3 precedenti,
  con la media di stagione dichiarata altrove. Aggiungerlo qui violerebbe la regola di
  `docs/30` (un dato in un posto solo). **Non duplicato.**
- **E3 (assenti senza numeri collegati alle notizie)**: misura nuova — sui 292 assenti
  pre-partita senza minuti in stagione, solo **12 (4%)** compaiono nelle notizie della loro
  squadra nei 7 giorni precedenti, e parte dei riscontri sono rumore (voci di mercato, classifiche
  «Golden Boy»). Un collegamento che manca 96 volte su 100 e qualche volta sbaglia non
  migliora la scheda. **Non pubblicato; la riga continua a spiegare il «senza minuti in
  stagione · n.d.» col ⓘ esistente.** Restano dichiarati i 289 casi della build.

## §5 — Gate (tutti rifatti dopo l'ultima modifica al sorgente)

- `pytest` → **589 passed** (erano 584);
- `ruff check .` → pulito;
- `fda build` → **470 schede / 2.364 fixture / 7.530 giocatori**;
- `scripts/verify_site.py` → **nessun problema · 211.906 controlli** (erano 210.499; +89
  verifiche della striscia, +6 della finestra corretta sulle tre schede);
- `scripts/parita_schede.py` → **89 schede, nessuna differenza**;
- `scripts/resa_375.py` → **27.696 misure · 0 problemi**;
- conteggi indipendenti sui Parquet per le tre schede del §1 (righe Understat prima del
  kickoff: Cagliari 3−1=2, Lecce 3−1=2, Lille 2−1=1, PSG 2−1=1, Atlético/Málaga 1−1=0).

Nessuna richiesta alle fonti esterne: tutte le misure vengono dai Parquet in `data/processed`.
Lo script riusabile è `scripts/audit_due_squadre.py` (censimento della card su tutte le
pagine + casi anomali).

## §6 — Stato della card dopo questo giro

Ogni riquadro di squadra contiene: forma con verso dei gol e forza degli avversari, xG
creati/concessi con rapporto di lega (stessa fonte), xPTS con banda di rumore, indice di
pressione su 7 leghe, riposo con data e coppa; la sezione dichiara la distinta non pubblicata,
pubblica la sintesi dell'incrocio attacco–difesa quando regge (§7), e il piè di card
descrive tutto. Residui
invariati da `docs/64` §6 (id di fase NED1, campione xG una gara avanti quando la fonte
anticipa, PPDA come media di gare) più: la striscia attacco–difesa a inizio stagione uscirà
solo sulle schede con ≥3 gare per parte (comportamento dichiarato, non un buco).

Coda della revisione sezione per sezione (da `docs/65` §2.F, invariata): «Panchina e posta in
gioco», «Mercato: arrivi e partenze», «Vita del club», «Previsione del modello ensemble»,
«Verifica approfondita», «Confronto di stagione», «Clima del club».

## §7 — Revisione della striscia «Attacco contro difesa» (richiesta dell'utente)

### La misura

L'utente, sulla prima versione (§2): «non credo che così com'è mi sia di grande aiuto» — la
striscia metteva in fila i quattro rapporti del campionato (crea casa, concede trasferta,
crea trasferta, concede casa) e lasciava al lettore il conto e il confronto. Misurato
offline sui Parquet (stessa regola B.10), sulle **1.983 gare non giocate** in cui entrambe
le squadre hanno i due rapporti dalla stessa fonte:

- la sintesi utile è il **prodotto** `crea × concede l'avversaria` per squadra: è la
  produzione offensiva attesa in questo incrocio rapportata alla media del campionato
  (stessa combinazione moltiplicativa attacco×difesa che il modello usa coi parametri
  fittati, qui con gli xG di stagione); 1,00× vale squadra media contro difesa media;
- distribuzione del prodotto su 1.983 gare: p5 0,40 · mediana 0,93 · p95 1,86 → barra in
  scala **0–2,5×** (cappata);
- squilibrio `q` fra le due produzioni (casa su trasferta): mediana 1,00 · p95 4,08 ·
  massimo 11,5 (Benfica–Rio Ave 2,54× contro 0,22×; Juventus–Lecce e Bayern–Paderborn
  10,9×);
- errore: sd/media dell'xG per gara-squadra **1,04 su media 1,69** (`docs/64` §7,
  `XG_RATIO_CV ≈ 0,612`); SE del rapporto su n gare ≈ CV/√n, quello di q combina in
  quadratura i quattro rapporti → con questo rumore lo squilibrio **supera 1σ su 918/1.983
  gare (46%)**, che quindi ricevono un verdetto; le altre restano «entro il rumore».

### La correzione

- `analysis.py` — `attacco_contro_difesa` ora restituisce anche `home_prod`, `away_prod`
  (i prodotti), `sbilancio` (q), `oltre_rumore` (|ln q| oltre l'errore a 1σ), `q_lo`/`q_hi`
  (intervallo a 1σ); costante documentata `XG_RATIO_CV = 1,036/1,692`;
- `match.html` — la striscia (`id="attacco-difesa"`) pubblica ora: titolo con ⓘ di metodo,
  una **barra per squadra** con in etichetta la produzione attesa, i quattro rapporti come
  dettaglio sotto le barre, e il **verdetto** — il nome di chi ha il confronto offensivo
  migliore con il fattore («11,5× la produzione attesa dell'altra») se lo squilibrio supera
  1σ, altrimenti «entro il rumore del campione» con l'intervallo nell'ⓘ; la barra della
  squadra in vantaggio si accende solo oltre il rumore;
- il piè di card descrive la sintesi; la resa a 375 px della griglia barre è coperta da
  `resa_375` (colonna minmax(60px, auto) + barra elastica).

### Invarianti e test

- [44] di `verify_site.py` riscritto: ricomputa da `attesi` prodotti, barre, rapporti di
  dettaglio e verdetto (leader giusto oltre 1σ; nessun vincitore entro 1σ) e confronta con
  la pagina;
- `test_site.py` aggiorna i due test della striscia (struttura e resa sulla pagina reale
  di Inter–Napoli);
- caso 12 di manomissione in `test_verify_scripts.py`: prodotto, barra, assenza e leader
  falsi vengono tutti catturati.

### Dopo la correzione

Le **89 schede pre-partita** pubblicano la sintesi con barre e verdetto: **36 dichiarano
chi ha il confronto offensivo migliore** (es. Atalanta–Venezia: «Venezia, 2,0× la
produzione attesa dell'altra»), **53 restano «entro il rumore del campione»** con
l'intervallo a 1σ nell'ⓘ. La barra della squadra indietro si spegne solo quando il
verdetto c'è; i gate della §5 sono stati rifatti dopo questa revisione: `pytest` **589
passed**, `ruff` pulito, `fda build` **470/2.364/7.530**, `verify_site` **212.351 · 0**
(+445 controlli della sintesi), parità **nessuna differenza**, `resa_375` **27.696 · 0**,
audit: 89 strisce con 36 verdetti oltre il rumore e 53 entro.

## §8 — Revisione della card «Confronto di stagione» (richiesta dell'utente)

### La misura

La card (presente su **tutte le 470 pagine**, 89 pre-partita e 381 finite) non aveva
**alcuna copertura numerica** nei gate: nessun controllo di `verify_site` ne ricalcolava i
numeri dalle classifiche. Misurata sulle pagine e sui Parquet:

- **«Nª su 20» scritto anche dove il campionato ha 18 squadre**: la resa hardcodava 20 nel
  suffisso e nella barra della posizione (`(20−rank)/19`). FRA1, GER1, NED1 e POR1 hanno 18
  squadre → **257 pagine (55%) pubblicavano un denominatore sbagliato** e una barra fuori
  scala (es. Angers–Lille: «8ª su 20», barra al 63% invece di 59%);
- la riga «Punti» evidenzia il migliore **per punti/gara** (scelta di `docs/40` §1: le due
  squadre possono avere gare in meno), ma la pagina non lo diceva: un lettore poteva leggere
  l'evidenziazione come un confronto sui punti totali;
- la nota non dichiarava **l'orologio della classifica**: la card legge la classifica
  raccolta oggi, quindi sulle schede di gare già giocate comprende i turni successivi — lo
  sapeva solo il ⓘ dell'xPTS nella card «Le due squadre», non la card stessa;
- nessun conto fatto per il lettore: il divario in punti restava da sottrarre a mente.

### La correzione

- `analysis.py` — `_n_squadre` conta le squadre del campionato **nella stessa tabella della
  classifica** (FotMob, riserva ESPN); `season_compare` lo passa alla resa insieme al
  divario in punti; la nota dichiara l'orologio; la riga «Punti» porta un titolo che spiega
  l'evidenziazione per punti/gara;
- `match.html` — barra della posizione e suffisso «Nª su n» scalano sul numero vero di
  squadre (sulle leghe a 20 la formula `(n−rank)/(n−1)` coincide con la vecchia: zero
  regressione lì); frase del divario («In classifica X è N punti davanti a Y» / pari punti)
  davanti alla nota.

### Invarianti e test

- **[45] `check_confronto_stagione`** (nuova): su ogni pagina rilegge le classifiche con la
  stessa precedenza del generatore e ricalcola posizione, barra, punti e punti/gara, V-N-P,
  gol fatti/subiti per gara, differenza reti, i rapporti «× media campionato» (media gol
  della stessa tabella), le evidenziazioni, il titolo della riga «Punti», il divario e la
  dichiarazione dell'orologio;
- `test_site.py` estende `test_season_compare` (n_squadre contato dalla tabella, divario,
  titolo, orologio) e aggiunge il caso di un campionato a 18 squadre;
- caso 13 di manomissione in `test_verify_scripts.py`: «ª su 20» in una lega a 3 squadre
  raccolte, barra fuori scala, punti falsi, evidenziazione spostata, orologio rimosso,
  divario sbagliato, titolo rimosso — tutti catturati.

### Dopo la correzione

Le 470 card pubblicano il denominatore vero del proprio campionato, il divario in punti e
l'orologio dichiarato. Gate rifatti: `pytest` **590 passed** (era 589), `ruff` pulito,
`fda build` **470/2.364/7.530**, `verify_site` **228.331 · 0** (+15.980 controlli di [45]),
parità **nessuna differenza**, `resa_375` **27.696 · 0**; l'oracolo [45] gira sulle 470
pagine reali con 0 discordanze.
