# Revisione completa del 17/09/2026 — la lingua del portale e la parità fra le 7 leghe

**Domanda di partenza:** «perché non è in lingua italiana? è pieno di informazioni succose — rivedi e
rileggiti tutto».

**Risposta breve, con i numeri:** il portale *dichiarava* di pubblicare «titoli in lingua italiana»
e ne pubblicava **61 su 161 in un'altra lingua** (olandese, tedesco, portoghese, francese, spagnolo,
inglese). Non era un caso isolato: il filtro che doveva garantire l'italiano era una lista di parole e
lasciava passare tutto ciò che non conteneva quelle parole. Corretto il filtro, la copertura della
card «Vita del club» crollava dal 91,2% al 69,1% (Ligue 1 al 22%, Bundesliga al 33%): la parità fra
le 7 leghe è una regola del progetto (`00_regole_di_lavoro.md` §F), quindi il buco è stato colmato
con **fatti in italiano ricavati dai nostri dati**, che valgono in tutti i campionati. Ora è
**100%** (68 schede su 68) e **100% in italiano**.

---

## 1. La revisione: cosa è stato riletto e cosa dice

Tutto il repository, non solo la parte sospetta. Metodo: generare il sito, scandirlo, poi leggere.

| Cosa | Quanto | Inglese / non italiano trovato |
|---|---|---|
| Pagine HTML generate | **4.130** | **0** frammenti di prosa straniera |
| Documenti in `docs/` | **27** file | 4 frammenti, **tutti codice citato** (regex FotMob, righe pandas) |
| Template Jinja | **12** | 0 (solo nomi propri: «The Odds API», «Google News RSS») |
| Codice sorgente | 20 moduli | docstring e commenti in italiano |
| Titoli di PR | ultime 25 | 1 in inglese (PR #41 «feat: make season projections league-aware») |
| `verify_site.py` | — | 0 problemi · 93.201 controlli |

Lo scandimento delle pagine usa **150 parole-funzione inglesi** (the, with, against, because…) e
richiede frammenti di almeno 30 caratteri con **almeno 4** di quelle parole e **nessun** marcatore
italiano: cerca prosa, non nomi propri. Su 4.130 pagine ha trovato **0**.

**Conclusione della prima lettura: il sito è italiano, i documenti sono italiani.** Il difetto non
stava dove il controllo d'insieme guardava, ma dentro una card — e nessuno dei due controlli
automatici poteva vederlo.

## 2. Il difetto: 61 titoli stranieri pubblicati come italiani

La card «Vita del club» pubblica titoli di rassegna stampa. Il filtro `is_italian_news()`
(`src/fda/sources/news.py`) funzionava così:

```python
return not bool(words & _NON_ITALIAN_TOKENS)   # ~230 parole straniere
```

È una **lista nera**: un titolo è italiano se *non contiene* parole strane note. «Trainerwechsel bei
Leverkusen-Gegner», «Petrasso: «Limpámos a nossa imagem»», «Nottingham Forest stadium expansion
plans approved» non ne contengono nessuna: passavano.

**Misura sul sito generato il 17/09/2026** (68 schede in programma, 161 voci pubblicate):

- **61 voci non erano in italiano (37,9%)** — 56 titoli diversi, 5 pubblicati due volte in due schede;
- distribuzione: **Francia 18, Inghilterra 14, Portogallo 12, Germania 6, Spagna 4, Paesi Bassi 3,
  Italia 0**; la stampa italiana scrive di Serie A, e lì il filtro non sbagliava mai;
- sul Parquet la stessa regola accettava **4.045 righe** che italiane non sono, su 18.270 (22,1%):
  FRA1 936 · ENG1 827 · POR1 704 · GER1 579 · NED1 492 · ESP1 384 · ITA1 123.

Perché nessun controllo lo aveva visto: `verify_site.py` [20] verifica che le voci pubblicate siano
in italiano **chiamando la stessa funzione** che le ha selezionate. Se la funzione sbaglia, il
controllo concorda con lei. È il difetto classico dei test che riusano l'implementazione: non
verificano, ricertificano.

## 3. La regola nuova

Due stadi, entrambi deterministici (`src/fda/sources/news.py`):

1. **veto lessicale** (invariato): caratteri e parole che in un titolo di calcio italiano non
   compaiono (`¿ ¡ ß œ`, «the», «el», «van de», «des», …);
2. **rilevamento statistico** con `langdetect` su *titolo + estratto*, minuscolo, seed fisso.
   - meno di **6 parole**: nessuna statistica regge, decide la grammatica italiana (articoli,
     preposizioni, lessico: «del», «nella», «gol», «panchina»);
   - prima posizione dubbia (probabilità < 0,90): serve l'italiano in classifica (≥ 0,05) **e** due
     parole funzionali italiane — è il caso dei titoli urlati («NAPOLI, LOBOTKA E IL RINNOVO…»),
     che il rilevatore da solo legge come inglese o portoghese.

`langdetect` è un pacchetto puro Python, **offline**, senza chiavi né modelli da scaricare: non
aggiunge richieste di rete e non tocca la regola del costo zero. Il seed fisso (`DetectorFactory.seed = 0`)
è obbligatorio: senza, lo stesso titolo può passare in un run e cadere in quello dopo.

**Misure a sostegno**

| Prova | Vecchio filtro | Nuovo filtro |
|---|---|---|
| 210 titoli etichettati per testata (30 per lingua) | 70,5% esatti · **60 stranieri passati** su 180 | 93,3% esatti · 5 passati · 9 italiani persi |
| 161 voci pubblicate il 17/09 | **61 stranieri pubblicati** | **61 su 61 scartati**, 100 su 100 italiani tenuti |
| Parquet (18.270 righe) | 11.568 «italiane» (63,3%) | 7.523 (41,2%) |

I 9 italiani persi nel campione sono titoli di soli nomi propri («Getafe vs Deportivo A Coruña»,
«Nottingham Forest vs Leeds United», «Live Brighton - Leeds United - Premier League: Punteggi &
Highlights Calcio»): nessuno di essi è una notizia, e la card li esclude comunque per le sue regole
di sostanza. I 5 stranieri che passano ancora sono casi in cui **la testata estera scrive in
italiano** («Il Liverpool FC rende omaggio all'ex allenatore femminile Matt Beard»): l'etichetta
automatica per testata è sbagliata, non il filtro.

Test: `tests/test_i18n.py` (22 titoli reali presi dalle schede pubblicate, più i casi brevi).

## 4. Il prezzo della regola, e come è stato pagato

Con il filtro corretto la copertura della card scende, perché **la stampa italiana non scrive di Le
Havre, Paderborn o Alverca**:

| Lega | Prima (filtro rotto) | Dopo il filtro corretto | Con i fatti dai nostri dati |
|---|---|---|---|
| Serie A | 100% | 100% | **100%** |
| LaLiga | 91,7% | 91,7% | **100%** |
| Premier League | 90,0% | 70,0% | **100%** |
| Eredivisie | 88,9% | 77,8% | **100%** |
| Liga Portugal | 100% | 77,8% | **100%** |
| Bundesliga | 77,8% | 33,3% | **100%** |
| Ligue 1 | 88,9% | 22,2% | **100%** |
| **Totale (68 schede)** | **91,2%** | **69,1%** | **100%** |

Come è stato colmato: due fatti nuovi nel blocco «Da sapere», in italiano, calcolati dai Parquet e
quindi **disponibili in tutte e 7 le leghe** (`analysis.news_sapere`):

- **«Dentro le mura» / «Lontano da casa»** — il bilancio della squadra *nel ruolo in cui gioca
  questa partita*: «FC Twente in casa: 3 vittorie, 0 pareggi e 0 sconfitte in 3 gare (9 punti su 9,
  3.00 a gara)». Il «Confronto di stagione» dice quanto vale la squadra in media; qui si separa ciò
  che ha fatto sul campo di questa gara. Pubblicato con almeno **3 gare**: con due il bilancio è un
  caso, non un fatto.
- **«L'uomo gol»** — il miglior marcatore della squadra in questo campionato: «il miglior marcatore
  di Roma in questo campionato è Dybala (3 gol)». Se è **indisponibile** lo dice
  («…, che però è indisponibile per questa gara (injury)»): nascondere il nome solo perché è
  infortunato sarebbe una verità a metà. Conta solo le gare **finite**: un gol in una partita non
  ancora giocata non esiste per chi legge.

Risultato: 68 schede su 68 con contenuto, 227 righe «Da sapere», 76 voci di rassegna pubblicate
(tutte italiane).

## 5. Fonti: due dichiarazioni che non erano vere

Trovare un difetto di lingua ha fatto rileggere anche cosa la card dichiara sulle fonti.

1. **ESPN news.** Il footer diceva «Google News RSS per squadra (edizione italiana) **più ESPN news
   di lega**». Le notizie ESPN sono **in inglese**: su 30 righe raccolte, **1** passa il filtro
   dell'italiano. Inoltre la fonte è **sospesa** (`espn:NEWS`: HTTP 403 su tutte e 7 le leghe,
   0 richieste nei run recenti). Una fonte che non può essere pubblicata e non risponde non può
   stare in cima alla card: il footer ora dice entrambe le cose e rimanda a *Stato fonti*.
2. **Feed diretto Sportmediaset — chiuso il 19/09/2026 con una misura, non con un'ipotesi.**
   L'URL risponde con una **pagina HTML vuota** (`<!doctype html><html><head></head><body></body></html>`,
   verificato il 19/09), non con un XML: il feed non esiste più. Un URL alternativo
   (`mediasetinfinity.mediaset.it/sportmediaset/rss/calcio.xml`) risponde **403**. Ma la domanda
   giusta era un'altra — **quanto costa?** Misurato su `news.parquet` (16.337 righe): Sportmediaset
   ha **205** notizie e arrivano **tutte** da Google News, **0** dal feed diretto (l'ultima il 19/09
   alle 12:02 UTC); Sky Sport 392, tutte da Google News; ANSA 377, di cui **94** dal feed diretto.
   I feed diretti sono quindi un canale **ridondante**: quello morto non toglie una notizia. Il
   difetto vero era un altro: la riga `news:NEWS` era **ERRORE** a ogni run, cioè una fonte che
   consegnava 3.938 righe dichiarata guasta e un rosso permanente in cui un guasto **vero** di
   Google News non si sarebbe più distinto. Corretto in `collect.py`: `news direct` entra in
   `_WARN_NON_BLOCCANTE` (AVVISO col motivo pubblicato, come i 403 ESPN) e `as_status_rows` ora
   richiede che **tutti** gli errori della fase siano non bloccanti — prima decideva il primo,
   quindi un feed morto scritto per primo avrebbe mascherato da AVVISO un guasto vero. Due test in
   `tests/test_diagnostica_fonti.py`. L'URL resta in configurazione: se Mediaset lo riapre, il feed
   rientra da solo.

## 6. Verifiche

- **369 test** passati (+4: 2 sul filtro lingua con i casi reali, 2 sui fatti «Da sapere»);
- `fda build`: 375 schede · 2.364 partite · 7.478 giocatori;
- `verify_site.py`: **0 problemi · 93.696 controlli** (erano 93.201) con la **nuova invariante
  [20b]**: bilancio casa/trasferta e uomo gol **ricalcolati con pandas in modo indipendente** dalle
  funzioni del sito, così un errore nel calcolo non si certifica da sé;
- `ruff`: **173** rilievi, esattamente la baseline del progetto (nessuno nuovo);
- due difetti trovati *mentre* si correggeva: l'invariante [23] cercava la sottostringa «è
  indisponibile», che ora compare anche in «L'uomo gol» (resa specifica), e il controllo lingua del
  verificatore usava il solo titolo mentre il sito usa titolo + estratto (allineati).

## 7. Aperto

1. **Traduzione automatica.** Il materiale straniero scartato è davvero ricco («Cómo afecta la
   detención de Rakan Al-Thani al futuro del Málaga CF», «Iñigo Pérez: "No tengo miedo al cese"»):
   4.045 righe su 18.270. Pubblicarlo in italiano richiederebbe una traduzione automatica, che nel
   perimetro del progetto (costo zero, niente chiavi, rispetto delle fonti) significa o un modello
   locale da scaricare in CI o un endpoint pubblico non ufficiale: **entrambe le strade vanno
   decise dall'utente**, perché toccano la promessa «nessun testo è inventato» — una traduzione non
   è invenzione, ma non è nemmeno il testo della fonte.
2. ~~**Feed Sportmediaset 404** (§5): da confermare al primo run utile~~ — **chiuso il 19/09/2026** (§5.2): il feed è morto (pagina HTML vuota), ma è ridondante — 205 notizie Sportmediaset arrivano tutte da Google News, 0 dal feed. Corretto il difetto vero: la riga `news:NEWS` era ERRORE a ogni run, ora è AVVISO col motivo.
3. **PR #41**: titolo in inglese, corpo in italiano. Cosmetico, non toccato.

## 8. Regola aggiunta

La regola E di `docs/00_regole_di_lavoro.md` prescriveva l'italiano per «interfaccia, report e
documenti». Mancava la parte più visibile: **anche i messaggi dell'agente in chat, i titoli di PR e
i messaggi di commit vanno scritti in italiano**. Aggiornata.

## 9. Secondo giro (stesso giorno): la card era *scarna* e i contatori mentivano

L'utente ha incollato la card «Vita del club» di **Málaga-Villarreal** com'era online: una sola voce
per squadra, i due titoli spagnoli («Cómo afecta la detención de Rakan Al-Thani…», «Iñigo Pérez:
"No tengo miedo al cese"») e la riga «131/110 servizio o cronaca». Due problemi distinti.

### 9.1 Quella card è il sito *pubblicato*, non questo lavoro

La pagina su GitHub Pages è l'ultima build **fusa su main**; la PR #50 non lo era ancora. I due
titoli spagnoli, verificati sul `news.parquet` con il gate nuovo, danno entrambi
`is_italian_news = False`: nel build locale non escono. Nessuna correzione era necessaria sul
filtro: serviva dirlo, non «ri-aggiustarlo».

### 9.2 I contatori attribuivano i titoli stranieri a «servizio o cronaca»

Il controllo lingua veniva **dopo** l'argomento e i doppioni, così 116 titoli spagnoli finivano nel
numero «131 servizio o cronaca»: la card dichiarava un motivo falso e nascondeva il vero. Ora la
lingua è il **primo** vaglio dell'imbuto e ha il suo contatore (`team_news()["lingua"]`), stampato
sia nella riga dell'imbuto sia nella frase della card vuota. Confronto sulla stessa partita:

| contatore | prima | dopo |
|---|---|---|
| servizio o cronaca | 131 | **11** |
| in un'altra lingua | (nascosto) | **121** |

Su 132 titoli esaminati per il Málaga, 121 sono in spagnolo: ora la card lo dice.

### 9.3 Due fatti in più dai nostri dati (la card non era vuota, era povera)

Restano derivati dai nostri dati, in italiano, e *dopo* le righe di casa/trasferta, solo se la card
non ha ancora raggiunto le 8 righe (`SAPERE_MAX`) — così non scalzano mai ciò che già la regge:

- **Porta inviolata** — «X ha chiuso la porta in N gare su M», o «non ha ancora subito gol» quando
  le gare senza gol subiti sono tutte. Entrano in gioco con almeno 3 gare finite e 2 porte chiuse.
- **Finale da brividi** — «X ha subito 3 dei 4 gol dopo il 75' (il 75% di quelli presi fin qui)»:
  gol subiti **dopo il 75'**, calcolati su `events.parquet` (`type == "Goal"`, `minute` sempre
  presente su 974 righe). Soglia: almeno 4 gol subiti, 3 nel finale, quota ≥ 34%.

L'«uomo gol» ora dice anche gli assist («Adrián Nino (1 gol e 2 assist)»), e la «panchina nuova»
diceva «è in carica da 1 gare»: corretto in «1 gara» con `it_plural`.

### 9.4 Misura dopo il secondo giro

| | prima del giro | dopo il secondo giro |
|---|---|---|
| partite future con qualcosa nella card | 68/68 (100%) | **68/68 (100%)** |
| notizie di stampa pubblicate | 76 | 76 |
| righe «Da sapere» | 227 | **295** |
| titoli non italiani pubblicati | 0 | **0** |

Verifiche: **371 test** superati (2 nuovi su «Porta inviolata», «Finale da brividi» e sul tetto di
8 righe), `fda build` uscita 0, `verify_site.py` **nessun problema · 94.024 controlli** (con i
ricalcoli indipendenti dei due fatti nuovi: porte inviolate e gol nel finale ricalcolati su pandas
senza passare da `analysis.py`), ruff 173 = baseline.
