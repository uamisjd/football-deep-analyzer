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
2. **Feed diretto Sportmediaset.** Nell'ultimo run (17/09, 14:04) risponde **HTTP 404**
   (`https://www.sportmediaset.mediaset.it/rss/calcio.xml`). **Da verificare al prossimo run**: nel
   sandbox di lavoro non ho rete verso l'esterno, quindi non posso provare un URL alternativo senza
   il rischio di scriverne uno inventato. Se il 404 continua, il feed va sostituito o tolto
   (oggi restano ANSA e Sky Sport).

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
2. **Feed Sportmediaset 404** (§5): da confermare al primo run utile.
3. **PR #41**: titolo in inglese, corpo in italiano. Cosmetico, non toccato.

## 8. Regola aggiunta

La regola E di `docs/00_regole_di_lavoro.md` prescriveva l'italiano per «interfaccia, report e
documenti». Mancava la parte più visibile: **anche i messaggi dell'agente in chat, i titoli di PR e
i messaggi di commit vanno scritti in italiano**. Aggiornata.
