# Revisione totale del progetto e del sito — 16 ottobre 2026

**Richiesta:** controllare il progetto «vita, morte e miracoli», verificare dove siamo, cercare le criticità e migliorare l’efficacia del portale.
**Perimetro di questa revisione:** repository e test, build statica, sito pubblicato, workflow GitHub, modelli/dati committati e condizioni pubbliche delle fonti. I risultati sono distinti fra verifica dal vivo, verifica locale e valutazione/rischio; non è una consulenza legale.

## Verdetto in breve

CalcioMetro è un prodotto funzionante e maturo, non un prototipo: raccoglie dati, costruisce previsioni, pubblica analisi pre/post partita, pagine giocatori, accuratezza e proiezioni; la pipeline automatica è attiva. Il portale ha molta profondità, copertura di sette campionati e controlli di qualità insolitamente estesi.

La debolezza più importante, però, è proprio dove il lettore si aspetta «Oggi»: **lo snapshot statico può chiamare live una partita ormai finita e mostrare risultati programmati dopo il calcio d’inizio**. Il refresh del sito non è un feed in tempo reale e l’ora di generazione non dice quanto è vecchio ciascun dato. Ho riprodotto il difetto nei Parquet locali del run: per Heerenveen–Excelsior la scheda riportava 0–0 mentre il dettaglio salvato in una fotografia separata riportava 4–0. Altri quattro incontri erano ancora «in programma» dopo l’orario previsto. Un precedente audit registra la discordanza con lo scoreboard raccolto separatamente; quel feed non è stato usato come correttore, sia perché le fonti non erano state riconciliate sia perché i diritti sono da chiarire.

**Intervento implementato e verificato in questo branch:** liste e schede condividono la stessa riconciliazione calendario/dettagli; quando il calcio d’inizio è superato ma nessuna fotografia conferma il finale, la pagina passa a «stato da verificare» e nasconde il punteggio parziale. La homepage avvisa e le schede chiariscono che non è un feed live. Il gate indipendente [51] confronta stato e risultato di ogni card con la scheda collegata. Build e gate completi sono verdi; la modifica è ancora solo sul branch Arena, non pubblicata.

**Decisione P0 ancora necessaria:** la ricerca ha trovato restrizioni esplicite o segnali avversi all’accesso automatico/riuso per alcune fonti centrali. Non ho disattivato collettori né aumentato polling. La raccolta non va ampliata finché non si decide: chiedere autorizzazione, migrare verso fonti con licenza adeguata e copertura misurata, oppure ridurre esplicitamente il requisito live.

## 1. Che cos’è oggi il prodotto

Il sito, **CalcioMetro**, è un portale statico GitHub Pages alimentato da GitHub Actions, senza backend interattivo. Il workflow raccoglie/aggiorna dati, esegue i modelli, genera migliaia di pagine HTML e pubblica un artefatto. La configurazione pianifica cinque esecuzioni al giorno; non equivale a copertura live minuto per minuto e GitHub avverte che i trigger schedulati possono subire ritardi nei periodi di carico [documentazione GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

Le aree pubbliche comprendono:

- **Oggi / Prossime / Risultati** con filtri e riepiloghi;
- schede partita pre e post gara con previsione Dixon–Coles + Elo, probabilità, risultati esatti, forma, xG/xPTS, indisponibili, probabili formazioni, arbitro, meteo, precedenti, mercato delle rose, notizie e analisi post-partita;
- schede e hub dei giocatori, accuratezza del modello, laboratorio e proiezioni di stagione;
- Stato fonti/database e metodologia.

La profondità è un vantaggio reale, ma al lettore interessa prima sapere **se la partita è da giocare, in corso, finita o se i dati non sono aggiornati**. La fiducia nello stato è quindi una priorità più alta di aggiungere altre card o nuovi numeri.

## 2. Controllo dal vivo di GitHub e Pages

Controlli eseguiti il 16/10/2026 alle 23:45–23:51 UTC:

- `main` è al commit `7e672b0` (merge della PR documentale #128). La #128 risulta **fusa** e il run `tests` successivo #38977504667 è verde. Non c’erano PR o issue aperte nel controllo.
- Il daily #38983052624 è stato avviato alle 23:45 UTC ed era **ancora in corso** all’interrogazione; non ne presumo l’esito né un nuovo deploy.
- La homepage pubblica, rifetchata alle 23:51 UTC, riportava ancora **venerdì 16 ottobre, aggiornata 23:26 ora italiana**, 5 gare, 5 campionati, 5/5 con modello, **1 in corso e 4 in programma**. Heerenveen–Excelsior appariva 0–0 in corso; Frankfurt–Köln delle 20:30 era ancora proposto come prossimo calcio d’inizio. Alle 23:51 UTC quelle indicazioni erano temporalmente superate. La scheda di Heerenveen mostrava già 4–0 finale: il lettore poteva quindi vedere due stati diversi passando dalla lista al dettaglio.
- **Follow-up delle 23:58 UTC:** il daily #38983052624 ha completato con successo raccolta/build/deploy/notify e Pages ha poi mostrato sabato 17 ottobre, 24 partite, 6 campionati, 24/24 modellate, 0 live e 24 in programma. Questo aggiorna il quadro della giornata nuova, ma non prova che tutte le partite del 16/10 siano state riconciliate: la pagina Risultati pubblica mostrava ancora 59 gare, con gli ultimi gruppi visibili al 10–12 ottobre e nessuna delle cinque partite del venerdì. L’aggiornamento della homepage non equivale a chiusura dei risultati arretrati.
- La pagina Accuratezza pubblica **218** gare valutate, 137 con la ricetta corrente, RPS 0,1990 vs baseline 0,2267; il backtest walk-forward è su 5.960 gare, RPS 0,1987 vs 0,2313. I mercati Over 2,5, Over 3,5 e BTTS sono fuori intervallo al 95% nel campione di stagione: sono un segnale da monitorare, non una ragione per fare tuning senza il protocollo già stabilito.
- La repository API riporta `size=761752 KB` (~744 MiB), sotto la raccomandazione Pages di 1 GB; non è una misurazione del sito generato né una proiezione della crescita. La copia locale è shallow, perciò `git count-objects` non misura tutta la storia.

Limiti GitHub Pages: il sito pubblicato deve restare sotto 1 GB, la sorgente è raccomandata sotto 1 GB, la banda ha limite morbido di 100 GB/mese; le build con workflow GitHub Actions non ricadono nel limite morbido di 10 build/ora [limiti ufficiali Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits). La build locale precedente pesava circa 160 MiB: non è oggi il collo di bottiglia.

## 3. Diagnosi del difetto più importante

**Riprodotto localmente sui dati versionati:** il builder delle liste classificava i match con `fixtures.status`; la scheda, invece, poteva prendere `status` e gol da `match_info`. Le due tabelle sono aggiornate/cachate separatamente. Se una delle fotografie è più nuova, lista e dettaglio possono divergere; se entrambe sono vecchie, possono restare pubblici stati apparentemente validi ma superati.

La causa precisa del dato FotMob stale non è provata: cache persistente Actions, TTL fixture FotMob di 6 h e TTL scoreboard ESPN di 1 h rendono la cache una spiegazione plausibile. I contatori `source_status` sono aggregati per lega/fase e non registrano l’ora della fetch per singolo endpoint/file; non consentono di stabilire esattamente quando sia stato letto il payload fixture.

### Correzione prudenziale in questo branch

1. **Una sola funzione** riconcilia stato e punteggio per liste e schede: se una delle due fotografie dichiara il finale, la gara è finale e il punteggio proviene dalla fotografia che lo dichiara; negli altri casi i dettagli hanno precedenza e le fixture sono fallback.
2. Se lo stato rimane `scheduled` oltre 30 minuti dal calcio d’inizio, oppure `live/intervallo` oltre 105 minuti, si degrada a **`unverified`**: nessun punteggio parziale è mostrato come corrente. La soglia è una regola cautelativa di presentazione, non una misura dell’età della cache e non certifica il risultato reale.
3. Homepage e scheda spiegano che il dato non è verificato e che la previsione è una stima pre-partita, non una probabilità live.
4. Nuovo controllo **[51]** in `scripts/verify_site.py`: legge indipendentemente la card e la scheda collegata e segnala stato, risultato o link discordanti.
5. Non vengono interrogate fonti aggiuntive, non viene usato ESPN per scegliere un punteggio e non è cambiato il modello.

Il fallback corretto nel tempo resta registrare `last_fetched_at`, cache hit/age e provenienza **per endpoint**, e mostrarne l’età. Senza timestamp granulari, la soglia è deliberatamente un freno prudenziale, non una soluzione definitiva alla freschezza.

## 4. Stato della qualità e verifiche

Sulla fotografia Parquet committata e sulla build locale rigenerata dopo il fix:

- `pytest`: **1.052 passati** (suite completa);
- Ruff e `pip check`: puliti;
- `fda build`: **532** schede partita, **2.364** fixture, **7.602** giocatori; sito **4.365 file / 157.890.385 byte (~151 MiB)**;
- `verify_site`: **264.436 controlli, 0 problemi**; nuovo gate [51] ha verificato **151** card/schede;
- parità pre-partita: **92 schede**, struttura di 27 sezioni e 16 voci d’indice identiche;
- resa a 375 px: **29.965 misure, 0 problemi**;
- `pip-audit --requirement requirements-ci.txt`: nessuna vulnerabilità nota; `npm audit`: zero vulnerabilità nel lockfile Node.

Questi sono controlli offline sulla versione e sui Parquet locali, non prova di deploy né di live accuracy. Chromium/Playwright non è stato eseguito localmente in questa sessione; deve passare nel job browser della PR.

La revisione di accessibilità esistente usa Playwright + axe su campioni, viewport 375/1280 e temi chiaro/scuro. È un buon controllo continuo, non equivale a una prova manuale completa con tecnologie assistive. WCAG 2.2 resta il riferimento normativo pubblicato dal W3C [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## 5. Ricerca esterna: dati, diritti e alternative

La ricerca è stata usata per trovare il perimetro operativo, non per esprimere un giudizio legale.

| Fonte / tema | Evidenza pubblica trovata | Implicazione per CalcioMetro |
|---|---|---|
| **FotMob** | La FAQ afferma che servizi automatici (robot/crawler/indexing) e uso sistematico o regolare non sono permessi [FAQ FotMob](https://www.fotmob.com/faq). | Rischio alto rispetto alla raccolta ricorrente del progetto. Non aumentare i fetch; chiedere licenza/permesso o pianificare sostituzione. |
| **Understat** | `robots.txt` pubblica `Disallow: /` [robots.txt](https://understat.com/robots.txt). | Non è un’autorizzazione all’uso: sospendere l’espansione e verificare termini/permesso prima di mantenere o ampliare lo scraping. |
| **ESPN / Disney** | I termini italiani Disney rinviano per l’Italia a termini specifici e includono restrizioni su monitoraggio/copia automatizzati senza permesso scritto [termini italiani](https://disneytermsofuse.com/italian/). | L’applicabilità all’endpoint usato non è risolta. Non scegliere ESPN come fonte correttiva automatica senza permesso/analisi. |
| **Football-Data.co.uk** | La pagina dati dichiara uso inteso per individui privati e non per prodotti commerciali o training con bot/scraper/AI [pagina dati](https://football-data.co.uk/data.php). | Fonte storica usata nel modello: il repo usa anche un mirror. La licenza/riuso dei dati del mirror va chiarita; disponibilità CSV ≠ autorizzazione. |
| **OpenLigaDB** | Il sito descrive l’API comunitaria come gratuita e i dati come ODbL [sito/API ufficiale](https://www.openligadb.de/). | Candidata per risultati/calendari, ma la copertura e l’aggiornamento delle sette leghe non sono stati validati. ODbL comporta attribuzione/share-alike da esaminare. Non è stata integrata. |
| **Football-Data.org** | Il tier gratuito è limitato a dati base e competizioni; il live scoring è a pagamento [registrazione/pricing](https://www.football-data.org/client/register). | Possibile alternativa per calendari/risultati in un sottoinsieme; non soddisfa live sette leghe a costo zero. |
| **GitHub Actions** | Gli orari schedulati possono essere ritardati e alcuni run possono essere persi sotto carico [documentazione](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows). | Non presentare il sito statico come live. Il numero di run giornalieri non garantisce freschezza. |

**Non ho trovato/verificato** una fonte gratuita con licenza adatta, copertura live e qualità convalidate su tutti i sette campionati e su tutti i campi che il sito pubblica. Rispettare il vincolo costo-zero senza inventare una copertura sostitutiva.

## 6. Coda di lavoro utile, in ordine

1. **P0 — scelta del committente sui diritti e sul requisito live:** permessi scritti; migrazione selettiva a fonti riutilizzabili; oppure dichiarazione esplicita che gli stati sono differiti/non-live. Serve una scelta su FotMob, Understat, ESPN e dati storici Football-Data.co.uk/mirror.
2. **P1 — chiudere la correzione stato:** terminare build/gate sul branch, aprire una PR e lasciare che la CI del repo verifichi `test/site/browser`. Il merge resta al committente. Dopo il merge, accertare che la pagina pubblicata mostri «da verificare» per gli stati scaduti, non dare per avvenuto il deploy prima del daily.
3. **P1 — provenienza e freschezza:** aggiungere timestamps/cache-age granulari per endpoint e campo; status pagina deve distinguere ora build, ultimo fetch, age ed eventuale degradazione. Evitare un generico «aggiornato alle HH:MM» che sembra attestare ogni singola fonte.
4. **P2 — accuratezza del modello:** monitorare il campione live e gli intervalli già pubblicati; non ritoccare i mercati goal solo sulla base di 218 gare. Conservare walk-forward e confronti appaiati preregistrati.
5. **P2 — sicurezza e manutenzione:** in questa revisione i pacchetti fissati non hanno vulnerabilità note secondo `pip-audit`/`npm audit`; i permessi API non consentono di certificare branch protection o code-scanning. Verificare questi controlli nell’interfaccia GitHub.
6. **P2 — usabilità:** le card e il sistema di analisi sono completi, ma la scheda partita è lunga; tenere indice/ancore e messaggi di stato ben distinguibili. Nessuna nuova sezione prima di misurarne utilità e ridondanza.

## 7. Limiti della verifica

- Il sito pubblico è stato letto direttamente e la fotografia stale è un’osservazione dal vivo; la correzione è sul branch e non è ancora pubblicata.
- Non è stata fatta una lettura visiva manuale di tutte le ~4.300 pagine né un benchmark di traffico/banda Pages.
- La cache precisa per endpoint, i permessi GitHub di branch protection/code scanning, i termini applicabili a ogni endpoint, la copertura ODbL 7/7 e il daily avviato alle 23:45 UTC restano da verificare.
- Questa verifica non cambia configurazioni di fonti, volume richieste, modello, dati pubblici o decisioni economiche.

## Fonti di ricerca esterna

- [FAQ ufficiale FotMob](https://www.fotmob.com/faq)
- [Understat robots.txt](https://understat.com/robots.txt)
- [Termini Disney in italiano](https://disneytermsofuse.com/italian/)
- [Football-Data.co.uk — dati e condizioni dichiarate](https://football-data.co.uk/data.php)
- [OpenLigaDB](https://www.openligadb.de/)
- [Football-Data.org — tier gratuito](https://www.football-data.org/client/register)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
- [GitHub Actions schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Wheatcroft (2021), valutazione delle previsioni calcistiche e RPS](https://doi.org/10.1515/jqas-2019-0089) — la letteratura non ha consenso assoluto su un singolo punteggio; l’accuratezza va confrontata fuori campione con regole probabilistiche e baseline dichiarate.

## Prossimo passo

Aspettare gli esiti della suite/build/gate completi sul branch, aggiornare `docs/STATO.md` e il briefing, poi aprire una PR tecnica con il fix di stato e il gate [51]. Non fare merge automaticamente. In parallelo chiedere al committente una decisione sulle autorizzazioni delle fonti e sul significato desiderato di «live» entro il vincolo di costo zero.
