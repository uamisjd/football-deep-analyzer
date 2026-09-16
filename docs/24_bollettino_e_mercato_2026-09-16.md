# 24 — «Ultime dalle società» e «Mercato: arrivi e partenze»: due card rifatte (2026-09-16)

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
| `python -m pytest -q` | suite completa | 356 test |
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

## §3 — Il bollettino rifatto (card `id="notizie"`)

Sette regole, tutte dichiarate nel testo della card, più una di recupero:

1. **finestra vera** `kickoff − 12 giorni ≤ data ≤ kickoff` (prima il limite superiore mancava:
   entrava roba pubblicata **dopo** la gara);
2. **filtro e categoria** (`fda.sources.news.classify_news`): via dirette, «dove vederla»,
   pronostici, pagelle, video, cronache col risultato nel titolo, **e le pagine di servizio**
   (biglietti, prevendite, merchandising, figurine) — vedi §3.3;
3. **gate di soggetto**: il titolo deve parlare della squadra o citare un suo giocatore/allenatore
   (nomi della distinta di **questa** partita + presenze di stagione); ferma i pezzi di giornata
   che il feed della squadra restituisce perché citano un avversario;
4. **ordine**: categoria più importante prima (infortuni/squalifiche/panchina 5, società 4,
   mercato 3, squadra 2, colore 1), poi la notizia più recente;
5. **dedup per titolo normalizzato**, con insieme condiviso fra le due colonne della stessa
   partita: lo stesso articolo non compare due volte in pagina;
6. **«Perché conta»**: se il titolo nomina un indisponibile o un titolare di questa partita,
   la card lo dice (««Prati» è in distinta come titolare: la notizia può essere più fresca del dato»);
7. **un soggetto per categoria** (§3.4);
8. **recupero** (§3.5).

### §3.1 — Il numero dell'imbuto è pubblicato

Ogni colonna dichiara il lavoro fatto: «Racing Santander · 37 titoli esaminati negli ultimi 12
giorni · 0 notizie pertinenti: nessuna nella finestra, qui le più recenti (fino a 45 giorni fa,
27 titoli in più guardati)». Se non c'è nulla, la card lo scrive invece di riempire lo spazio:
«Meglio nessuna notizia che una notizia che non serve».

### §3.2 — La testata non decide più la categoria

La descrizione di Google News è «titolo + testata»: classificando il brano intero, la categoria la
sceglieva la fonte (un pezzo di cronaca ripreso da TUTTOmercatoWEB risultava «Mercato»).
`strip_credit()` toglie testata, «Google News» ed «ESPN» dal brano prima della classificazione.

### §3.3 — Le pagine di servizio (difetto trovato nella misura dopo)

La card dichiarava di escludere le pagine di servizio e non lo faceva: **27 voci su 162 (17%)**
pubblicate dopo il primo giro di correzioni erano «Come acquistare i biglietti per X-Y: prezzi
della …, informazioni sulla partita» (una colonna ne aveva due). Aggiunte alle regole di scarto:
`bigliett|abbonament|prevendita|figurin|magliett|merchandis|souvenir|come acquistare|come
ottenere|informazioni sulla partita|parcheggi|store ufficiale|shop ufficiale|album ufficial`.
Misura dopo: **0** voci di servizio su 135 pubblicate (invariante permanente in `verify_site [20]`).

### §3.4 — Un soggetto per categoria

Nella stessa colonna due voci della stessa categoria che citano lo stesso nome proprio sono lo
stesso fatto raccontato due volte. Misurato: **13 coppie** su 162 voci (Calhanoglu, Tedesco,
Idzes, Stones, Adams). I club sono esclusi dall'elenco dei soggetti (compaiono in qualunque
titolo) e il filtro si applica **dopo** l'ordinamento per (peso, data) — verificato: applicandolo
in lettura restava la voce **più vecchia** del doppione, perché le righe arrivano dal Parquet in
ordine di data crescente. Misura dopo: **0 coppie**.

### §3.5 — Recupero fuori finestra, dichiarato

Se nella finestra non c'è nulla di utile la card guarda indietro fino a `NEWS_RECOVERY_DAYS = 45`
giorni e pubblica al massimo `NEWS_RECOVERY_LIMIT = 2` voci, **con la data vera** e l'etichetta
«fuori finestra». In recupero entrano prima le categorie che cambiano qualcosa
(infortuni, squalifiche, panchina, società, squadra) e il mercato solo come ultima risorsa; il
colore no — «una notizia di tre settimane prima, con la sua data, è informazione; una diretta di
ieri no» (e nemmeno i fuochi d'artificio dei tifosi). Il recupero vale **anche** quando la
finestra è completamente vuota (prima la funzione usciva prima di guardare indietro: 2 colonne
su 140 restavano mute senza motivo).

## §4 — Prima e dopo, sullo stesso sito

| Misura | Card vecchia (live) | Dopo il primo giro (finestra+gate+dedup) | Dopo il recupero | **Finale** |
|---|---|---|---|---|
| voci pubblicate (70 schede) | **535** | 118 | 168 | **135** |
| voci di servizio/dirette pubblicate | ~38% del corpus, mai filtrate | 27 su 162 (17%) | 27 su 168 (16%) | **0** |
| duplicati esatti in pagina | **58** | 0 | 0 | **0** |
| coppie stesso soggetto nella stessa colonna | non misurate (non c'erano categorie) | 13 su 162 | 13 su 168 | **0** |
| colonne senza alcuna voce | nessuno stato vuoto dichiarato (si riempiva di servizio) | 91/140 (65%) | 56/140 (40%) | **66/140 (47%)** |
| colonne con voce utile nella finestra | — | — | — | 63/140 (45%) |
| «Perché conta» presente | assente | — | — | **28 voci (21%)** |

Le colonne vuote **aumentano** rispetto al primo giro perché 27 voci erano biglietti: erano
riempitivo, non informazione. Il residuo (66 colonne su 140) ha una causa misurata e non
riparabile per codice: per 53 di quelle colonne il feed Google News della squadra, in 45 giorni,
contiene **solo** dirette, formazioni, statistiche, video e pronostici (§6).

## §5 — Cosa è cambiato nei file

| File | Modifica |
|---|---|
| `src/fda/sources/news.py` | `JUNK_NEWS` esteso alle pagine di servizio; `strip_credit()` |
| `src/fda/site/analysis.py` | `team_news()` → dizionario con imbuto, categorie, recupero, un soggetto per categoria; `news_subjects()` a livello di modulo; `transfer_window()` con finestra ricavata dai dati, `fee_it`, «già in campo»; rimosso `summer_market()` |
| `src/fda/site/templates/match.html` | le due card riscritte (testi, etichette, casi vuoti, tabella dei giocatori dentro `tablewrap`) |
| `src/fda/site/templates/accuracy.html` | tabella «Accuratezza per mercato» dentro `tablewrap` |
| `src/fda/site/assets/site.css` | `.topic` (badge categoria), `.news-list` |
| `src/fda/site/build.py` | filtro `fee_it` per i template |
| `scripts/verify_site.py` | `[20]` e `[26]` riscritti; nuovi controlli: niente voci di servizio, un soggetto per categoria, recupero dichiarato, etichetta «fuori finestra» |
| `tests/test_panchina_notizie.py`, `tests/test_mercato.py` | 22 + 13 test sull'imbuto, le categorie, il recupero, i servizi, i soggetti, la finestra del mercato |

## §6 — Cosa resta aperto (dichiarato, non nascosto)

1. **47% delle colonne senza notizie utili.** Causa misurata: per 53 colonne su 66 il feed della
   squadra negli ultimi 45 giorni non contiene **niente** di classificabile — verificato titolo per
   titolo su Ipswich (31 titoli in banda 12-45 gg: dirette, «testa a testa e formazioni»,
   biglietti, cronache) e FC Utrecht (11: formazioni, pronostici, live). Non è un difetto del
   filtro: allargare le regole per farli entrare è esattamente il difetto che l'utente ha chiesto
   di chiudere. **Esperimento fatto e scartato**: la query Google News con operatori
   (`"FC Utrecht" calcio (infortunio OR squalifica OR esonero OR indisponibili)`) restituisce
   articoli **vecchi** (gennaio 2026, luglio 2025), quindi la query semplice resta.
2. **Rumore residuo**: 2-3 voci fuori tema per la stessa ragione (un titolo di futsal, un
   «Sestri Levante» attribuito al Levante). Servirebbe un gate per entità più stretto; oggi il
   costo di sbagliare in senso opposto (buttare notizie vere) è più alto del beneficio.
3. **Il sito pubblicato mostra ancora le card vecchie** finché la PR non viene fusa: `main` è
   l'unico ramo che alimenta GitHub Pages, e il merge lo fa l'utente (regola D).
