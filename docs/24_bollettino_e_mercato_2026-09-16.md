# 24 — «Ultime dalle società» e «Mercato: arrivi e partenze»: due card rifatte (2026-09-16, chiusa il 17/09)

Sessione `arena/01a0ab67-football-deep-analyzer` (poi `arena/01a0abd9-…`). L'utente ha chiesto
la verifica totale del progetto e del sito pubblicato — «controlla bene il sito, navigaci dentro
come se fossi una persona» — con una direttiva esplicita su due sezioni:

> «ultime dalle società così com'è fatto è inutile per me che ho bisogno di avere informazioni
> importanti»

Questo documento consuntiva il lavoro su quelle due card: **difetto misurato prima**, codice
dopo, **stessa misura ripetuta dopo**, invariante permanente nel verificatore. Ogni numero qui
è ricalcolabile dai Parquet committati e dalle pagine generate con gli strumenti citati.

## §0 — Metodo e strumenti

| Strumento | Cosa fa | Dove |
|---|---|---|
| `fda build` | rigenera il sito da `data/processed` | — |
| `scripts/verify_site.py` | rilegge le pagine generate e **ricalcola** i numeri pubblicati | — |
| `python -m pytest -q` | suite completa | 358 test |
| `audit/extract_cards.py` | estrae le due card dalle pagine di `site/` in CSV | `audit/cards_{mercato,notizie}.csv` |
| `audit/misura_dopo.py` | misure aggregate sulle due card (colonne vuote, categorie, importi) | `audit/*_dopo.csv` |
| `audit/crawl.py` | **non usabile**: `requests` verso GitHub Pages muore con `SSLError` dal sandbox | — |

La navigazione del sito pubblicato è stata fatta a mano (14 pagine: home, `prossime`, `risultati`,
`accuratezza`, `stato`, `info`, `giocatori/index`, una scheda pre-partita per intero, più i
link rotti e un 404 voluto). **Il sandbox non ha browser** (il download di Chromium da
`cdn.playwright.dev` è bloccato come GitHub Pages): lo studio visivo è quindi **strutturale**
— CSS, contrasti calcolati, tabelle larghe, alt, id — non uno screenshot. Il limite è dichiarato
qui e non nascosto.

## §1 — Il difetto, misurato prima di toccare il codice

### §1.1 «Ultime dalle società» (card vecchia, sito pubblicato del 2026-09-16)

| Misura | Valore |
|---|---|
| voci pubblicate sulle 70 schede con la card | **535** |
| duplicati esatti nella stessa pagina | **58** |
| pagine con lo stesso titolo in **entrambe** le colonne | **8** |
| titoli di servizio sul corpus `news.parquet` (6.877 righe) | **37,8%** (dirette, «risultati in diretta, testa a testa e formazioni», pronostici, pagelle, «dove vederla») |
| ordinamento | punteggio di parole chiave, **a parità la data crescente**: la voce presentata come «più recente» era la più vecchia |
| categoria dichiarata | nessuna |
| collegamento con i nostri dati | nessuno (né indisponibili né distinta) |

Esempi letti sulla scheda live `partite/5868066.html`: «Valencia contro FC Barcelona risultati in
diretta, testa a testa e formazioni» (Sofascore), «Pronostico …», «Barcellona, ultime notizie di
calciomercato». Nessuna di queste informazioni cambia qualcosa per la partita: è il motivo per cui
la card risultava inutile.

### §1.2 «Mercato: arrivi e partenze» (card vecchia)

| Misura | Valore |
|---|---|
| righe pubblicate sulle 70 schede | **1.115** |
| righe etichettate «rinnovo di contratto» | **630 (56%)** — e molte erano trasferimenti veri (`transfer_type = contract` mappato su «rinnovo»: «Gabriel Jesus da Arsenal», «Álvaro Cortés a Royal Antwerp») |
| righe provenienti da una finestra **non** in corso | **1.187 su 4.231 (28%)** — stagione 2025-26, cioè la finestra di gennaio |
| importo non pubblicato dalla fonte | mostrato come «**—**» su 132 righe |
| criterio di scelta delle 4 voci per direzione | le più recenti, **senza ordinamento per importo**: un colpo da 30 M€ restava fuori per una firma di secondo piano di ieri |
| collegamento con la distinta di questa partita | assente |

La finestra non è dichiarata da FotMob: pubblicare «ultima finestra» senza ricavarla dai dati
era un'affermazione non verificabile, e nei fatti sbagliata su una riga su quattro.

## §2 — Il mercato rifatto (card `id="mercato"`)

Regole nuove, tutte visibili in pagina:

1. **finestra ricavata dai dati**: dal movimento più recente all'indietro finché fra due movimenti
   non passano più di `TRANSFER_GAP_DAYS = 21` giorni; gli **estremi veri** sono pubblicati
   («nella finestra dal 16/05/2026 al 02/09/2026»);
2. **tipo di movimento corretto**: niente più «rinnovo di contratto» sui trasferimenti
   (i rinnovi veri restano fuori tabella nella fonte e sono contati a parte in `stato.html`);
3. **importi leggibili in italiano** (`fee_it`): `12500000 → 12,5 M€`, `850000 → 850 k€`,
   `prestito`, `gratuito`, `importo non noto` — la fonte non pubblica l'importo e noi non lo stimiamo;
4. **ordine per importo pubblicato**, a parità di importo il più recente — si vedono i colpi;
5. **bilancio dichiarato sui soli importi pubblicati**: «spesa 182,5 M€ · incasso 91,5 M€ ·
   saldo +91 M€ (importo non noto per 13 movimenti)»;
6. **«Già in campo»**: quali arrivi di questa finestra sono nella distinta di questa partita, e con
   quale stato (titolare / a disposizione) — è il punto in cui il mercato tocca la formazione;
7. **onestà quando la fonte tace**: se l'ultimo movimento è più vecchio di
   `TRANSFER_STALE_DAYS = 90` la card non sparisce, dice da quando non ne pubblica;
8. **nota sui limiti**: un arrivo delle ultime settimane può non essere ancora riflesso nelle
   statistiche di stagione della scheda.

Misure dopo (70 pagine, `audit/misura_dopo.py`): **1.049 righe**, **0** fuori finestra,
**0** importi «—» (176 prestito · 93 gratuito · 87 importo non noto · 693 importi numerici),
date mostrate 01/06/2026 → 31/08/2026.

## §3 — La card «Vita del club» (portata in produzione il 2026-09-17)

La card si chiama adesso **«Vita del club»** (`id="notizie"` è rimasto: gli id non si cambiano
per non rompere i link interni). Riscritta dopo il confronto con l'utente del 16-17/09, che ha
bocciato due volte la selezione precedente («informazioni non recentissime o inerenti a questa
partita», «con queste notizie non ci faccio nulla») e ha chiesto di **cercare più a fondo** invece
di riempire lo spazio. Il prototipo approvato è `audit/vita_club.py`; qui c'è la traduzione in
produzione, con le stesse regole ma generiche — valgono per **tutte** le partite in programma.

Nove regole, tutte dichiarate nel testo della card:

1. **finestra vera di 7 giorni** (`NEWS_WINDOW_DAYS`): `kickoff − 7 giorni ≤ data ≤ kickoff`.
   Il **recupero fino a 45 giorni è stato rimosso**: l'utente ha rifiutato due volte le voci
   vecchie. Le righe fra 7 e 45 giorni non si pubblicano ma si **contano** (`vecchie`), così la
   card può dichiararle invece di far credere di non averle viste;
2. **due edizioni per squadra** (`GOOGLE_EDITIONS`): quella italiana e quella della lingua del
   campionato (es. `hl=es&gl=ES` per la Liga). La seconda porta il materiale di vita del club
   che la stampa italiana non raccoglie (misurato il 16/09 su Feyenoord, OM, Betis). Per i
   campionati italiani una richiesta sola. Tetto richieste alzato a 320/run: 20 squadre × 1 +
   112 × 2 = 244;
3. **filtro e categoria multi-lingua** (`classify_news`): via dirette, «dove vederla», pronostici,
   pagelle, video, cronache col risultato nel titolo, pagine di servizio — e, dal 17/09,
   **formazioni e squadre non prime** (`U23`, `Primavera`, `Serie C`, `femminile`), pubblicate
   per errore come «Società» alla prima misura;
4. **già altrove** (`NEWS_ALTROVE`): infortuni, squalifiche e mercato hanno la loro card in questa
   pagina; qui si **contano** come «servizio o cronaca» e non si ripetono. Era la richiesta
   esplicita dell'utente («gli infortunati sono già nella scheda partita, non ripetere sempre le
   stesse cose»);
5. **gate del valore** (`news_value`): un titolo fresco e pertinente entra solo se può spostare
   qualcosa. Annunci e logistica (conferenza stampa, orari, accessi, lavori, sponsor, premi,
   compleanni) vanno in `annunci`; i fatti senza frizione né decisione (dichiarazioni di
   circostanza, cronaca, «un punto più») vanno in `piatti`. Entrambi restano fuori **e si
   contano**: è la correzione chiesta dall'utente;
6. **gate di soggetto**: il titolo deve parlare della squadra o citare un suo giocatore/allenatore,
   e **non di un'altra squadra**: se nomina un altro club del nostro archivio e l'unico aggancio
   a questa è il nome della città (misurato: «Indagine a Roma: pressioni su Lotito a cedere la
   Lazio» nella colonna della Roma), la voce si conta a parte (`altre`);
7. **punteggio**: categoria + sostanza (numeri e decisioni sopra le dichiarazioni) + freschezza
   (ore al fischio d'inizio: ≤12h +6, ≤24h +5, ≤36h +4, ≤48h +3, ≤72h +1,5, oltre 0) + rilevanza
   per **questa** partita (avversario o vigilia +5, allenatore +4, un giocatore della distinta
   +3, la squadra +2, **−4** se il titolo nomina un altro club);
8. **diversità**: al massimo **3 fatti per squadra**, **2 per categoria**, **1 per soggetto**.
   Chi resta fuori per il tetto dei tre non si perde: i primi due restano **«in riserva»** e la
   card li mostra come tali (nella pagina di esempio: Ceballos per il Betis);
9. **dedup** per titolo normalizzato, con insieme condiviso fra le due colonne della stessa
   partita; e **«Da sapere»**, due fatti derivati dai nostri dati: stadio di questa partita
   diverso dall'abituale (con le due capienze) e panchina cambiata da poco (≤3 gare).

### §3.1 — Il numero dell'imbuto è pubblicato

Ogni colonna dichiara il lavoro fatto, non solo il risultato: «Real Betis · 20 titoli esaminati
negli ultimi 7 giorni · 3 pubblicati · 2 annunci o logistica · 9 servizio o cronaca · 3 non
spostano nulla · 2 troppo vecchi». Se non c'è nulla, la card scrive **perché**:
«**Niente che possa spostare qualcosa** su questa squadra: 19 servizio o cronaca · 2 annunci o
logistica · 3 non spostano nulla. La card non riempie lo spazio con conferenze stampa, orari,
lavori allo stadio o frasi di circostanza».

### §3.2 — La testata non decide più la categoria

La descrizione di Google News è «titolo + testata»: classificando il brano intero, la categoria la
sceglieva la fonte (un pezzo di cronaca ripreso da TUTTOmercatoWEB risultava «Mercato»).
`strip_credit()` toglie testata, «Google News» ed «ESPN» dal brano prima della classificazione.

### §3.3 — Le pagine di servizio (difetto trovato nella misura dopo)

La card dichiarava di escludere le pagine di servizio e non lo faceva: **27 voci su 162 (17%)**
pubblicate dopo il primo giro di correzioni erano «Come acquistare i biglietti per X-Y: prezzi
della …, informazioni sulla partita». Aggiunte alle regole di scarto e, con il port, estese alle
lingue delle due edizioni (`dónde ver`, `how to watch`, `wo sehen`, `où voir`, `waar te zien`,
`onde assistir`). Misura dopo: **0** voci di servizio pubblicate (invariante permanente in
`verify_site [20]`).

### §3.4 — Un soggetto per categoria

Nella stessa colonna due voci della stessa categoria che citano lo stesso nome proprio sono lo
stesso fatto raccontato due volte. I club sono esclusi dall'elenco dei soggetti (compaiono in
qualunque titolo) e il filtro si applica **dopo** l'ordinamento per (punteggio, data) —
applicandolo in lettura restava la voce **più vecchia** del doppione, perché le righe arrivano dal
Parquet in ordine di data crescente.

### §3.6 — Tre difetti trovati sui titoli della seconda edizione (2026-09-17)

Misurata la card sull'archivio nuovo (titoli in spagnolo, tedesco, francese) sono usciti tre
difetti, tutti corretti e coperti:

1. **`incidente` da solo non basta**: «Pellegrini difende Ez Abde dopo l'**incidente della
   maglia** di Ceuta» finiva in «Fuori dal campo». Ora servono le forme di strada o di salute
   (`incidente stradale/d'auto/automobilistico/mortale/in auto…`, `incidente … alcol|tossicolog`);
2. **i «contratti» generici non sono la panchina**: «FC Bayern: **Profi-Vertrag** für Tim Binder
   bis 2030» è il contratto di un giocatore. `vertrag`, `contrat`, `renewal`, `renovación`,
   `renovaçao`, `manager` valgono ora solo se nel titolo c'è anche una parola di panchina
   (`CONTRATTO_GENERICO` + `COACH_CONTEXT`);
3. **un evento, un fatto, anche fra categorie**: `un_soggetto` guarda dentro la stessa categoria,
   quindi lo stesso episodio poteva entrare due volte — per il Betis la difesa di Pellegrini su
   Abde compariva come «Dichiarazioni» e come «Club». Nuovo `un_evento()`: la chiave è la
   **persona di questa partita** nominata nel titolo; il fatto in più si conta (`doppioni`) e la
   card lo dichiara («già raccontato da un'altra voce»).

Misura dopo: **58 fatti in 29 partite** con 3 doppioni fermati e 8 voci di altre squadre contate.
Il totale scende da 65 a 58: sono i duplicati e i falsi positivi che non si vedono più.

### §3.5 — Le due edizioni, il gate del valore, la riserva e «Da sapere»

Il port del prototipo approvato ha cambiato tre cose rispetto alla card di settembre:

1. **la seconda query** (`news.py`, `collect.py`): per i campionati stranieri ogni squadra viene
   interrogata due volte — edizione italiana e edizione locale — e la lingua del titolo non è più
   un ostacolo, perché regole di servizio, categorie e gate portano le alternative in spagnolo,
   inglese, tedesco, francese, olandese e portoghese. Il conteggio delle ricerche passa dalle
   richieste effettive (`diag["ricerche"]`), non da `len(teams)`: era un contatore che mentiva
   appena le richieste per squadra sono diventate due;
2. **l'esclusione di ciò che è già in pagina**: infortuni, squalifiche e mercato non si ripetono
   (§3 regola 4). È il motivo principale per cui la card pubblica **meno** voci di prima: erano
   la maggioranza di quelle vecchie, e l'utente le ha rifiutate come «cose che non danno nessun
   vantaggio»;
3. **il gate del valore e la riserva**: 1.053 righe su 2.582 in finestra (tutte le partite future
   del 17/09) hanno una categoria e un punteggio, ma 270 sono «piatte» e 9 sono annunci: restano
   fuori, contate. I **24 fatti pubblicati** su 4.110 colonne-squadra (12 partite) sono: 9 Panchina,
   6 Società, 5 Tifoseria, 2 Spogliatoio, 1 Fuori dal campo, 1 Club; **nessuno in riserva** con
   questo archivio — la riserva si accende quando una squadra ha più di tre fatti. Fra questi:
   «Bologna, esonerato Tedesco: arriva Palladino con contratto fino al 2029», «Le false offerte, i
   450 milioni e l'indagine: dentro il complotto per spingere Lotito a cedere la Lazio», «Daniel
   Maldini positivo all'etilometro: ritirata la patente», «Calcio: protesta dei tifosi del Genoa
   contro il taglio dei posti al Ferraris», «UDINESE SULLE SPINE: RINVIATA LA SENTENZA DEL
   PROCESSO».
   Il numero misurava l'**archivio con la sola edizione italiana**. **Misurato il 2026-09-17**
   al primo run di raccolta con due edizioni (`35201313177`, `news:NEWS` da 132 a **244
   richieste**, 21.990 articoli visti, `news.parquet` da 6.877 a **16.623 righe**): la card passa
   a **65 fatti in 32 partite** (poi **58 in 29** dopo le tre correzioni del §3.6), e per
   Betis–Getafe pubblica — Pellegrini che difende Ezzalzouli, Bordalás che si lamenta della rosa,
   il bilancio record del Getafe.

Quattro difetti trovati proprio misurando il port (e corretti, uno con un test):

1. i titoli italiani delle inchieste e delle sentenze finivano **fuori categoria** («indagine»,
   «sentenza», «perquisizioni», «minacce» non erano nelle regole);
2. il pattern spagnolo `contrat` pescava il «contratto» italiano di un giocatore;
3. **i titoli di agenzia in maiuscolo** («UFFICIALE – BOLOGNA, ESONERATO TEDESCO…») sfuggivano al
   dedup dei soggetti, che cerca l'iniziale maiuscola seguita da minuscole: la colonna del Bologna
   pubblicava **due volte** lo stesso esonero. Ora i titoli senza minuscole passano da una lista di
   parole di servizio (`_MAIUSCOLE_NON_NOMI`) e il secondo titolo resta fuori;
4. **la voce di un'altra squadra**: il nome della città è anche il nome del club, e la regola 6 la
   conta a parte.

Il campione dei titoli resta verificabile: 1.130 scartati come servizio, 32 fuori categoria su
2.582. Resta dichiarato un residuo che il codice non chiude: **due testate sullo stesso episodio**
(due pezzi sui Daspo della curva) possono entrare insieme quando non condividono nessun nome
proprio — l'evento è lo stesso, il titolo no.

## §4 — Prima e dopo, sullo stesso sito

| Misura | Card vecchia (live) | Dopo il primo giro | Card v4 (port in produzione) |
|---|---|---|---|
| voci pubblicate | **535** (70 schede) | 135 | **24** su 2.055 partite future |
| finestra | nessuna (anche notizie dopo la gara) | 12 giorni + recupero a 45 | **7 giorni, nessun recupero** |
| voci di servizio/dirette pubblicate | ~38% del corpus | 0 | **0** |
| duplicati esatti in pagina | **58** | 0 | **0** |
| stesso soggetto nella stessa categoria | non misurato | 0 | **0** |
| infortuni/mercato/squalifiche ripetuti | erano la maggioranza | presenti | **0** (contati a parte) |
| colonne che dichiarano l'imbuto | nessuna | tutte | tutte, con annunci/piatti/vecchi/riserva |
| «Da sapere» | assente | assente | presente quando i dati lo dicono |

Il calo di volume è **voluto**: le voci che escono erano in maggioranza doppioni di altre card o
riempitivo. Le 4.086 colonne vuote oggi dichiarano l'imbuto; il rifornimento è la seconda
edizione, non un allargamento dei filtri.

## §5 — Cosa è cambiato nei file

| File | Modifica |
|---|---|
| `src/fda/sources/news.py` | `GOOGLE_EDITIONS`/`editions_for()` (due edizioni), `news_value()` (gate annuncio/piatto), `JUNK_NEWS` esteso alle lingue locali, formazioni e squadre non prime; `TOPIC_RULES` riscritte in 12 categorie multi-lingua (con «Spogliatoio», «Tifoseria», «Stadio e città», «Fuori dal campo») |
| `src/fda/collect.py` | paese della lega → edizione locale; conteggio `ricerche` per richiesta effettiva |
| `src/fda/site/analysis.py` | `team_news()` riscritto (finestra 7 giorni, gate, punteggio, tetto per categoria, riserva, imbuto), `news_sapere()`, `news_freshness()`, `news_substance()`, `_no_news()` |
| `src/fda/site/templates/match.html` | card «Vita del club» (testo, «Da sapere», «in riserva», caso vuoto con i conteggi) |
| `config/sources.yaml` | tetto richieste notizie 200 → 320 (due edizioni per squadra) |
| `scripts/verify_site.py` | `[20]` riscritto: ricalcola imbuto, conteggi, categorie, riserva, finestra, gate e «Da sapere» per ogni pagina |
| `tests/test_panchina_notizie.py`, `tests/test_diagnostica_fonti.py` | 24 + nuovi test sul port (gate, edizioni, riserva, categoria, soggetto, rilevanza, tabella vuota) |
| `src/fda/site/build.py` | filtro `fee_it` per i template (invariato) |

## §6 — Cosa resta aperto (dichiarato, non nascosto)

1. **Il volume dipende dalla seconda edizione — chiuso il 2026-09-17.** Il primo run con due
   edizioni (`35201313177`) ha portato `news:NEWS` a **244 richieste** e l'archivio a **16.623
   righe**: la card pubblica **58 fatti in 29 partite** (erano 24 in 12) e le colonne senza nulla
   scendono di conseguenza. Tre difetti emersi da quei titoli sono stati corretti subito (§3.6).
2. **Lo stadio della partita di esempio è sbagliato a monte.** Per `5868063` il dato della partita
   dice «Estadio Benito Villamarín» mentre le due gare interne precedenti del Betis sono a La
   Cartuja. Invece di inventare, la card lo **dichiara** nel blocco «Da sapere». La correzione a
   monte (dove nasce il `location` JSON-LD) è aperta.
3. **Il testo pubblicato resta quello della fonte** (titolo, testata, data, link): la riscrittura
   in italiano con «Perché conta» era fatta a mano nel prototipo e non è generalizzabile senza
   inventare. La card lo dice: «Titolo, testata, data e link come pubblicati».
4. **Il sito pubblicato mostra ancora le card vecchie** finché la PR non viene fusa: `main` è
   l'unico ramo che alimenta GitHub Pages, e il merge lo fa l'utente (regola D).
