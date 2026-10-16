# Revisione post-merge — 16 ottobre 2026

**Fotografia aggiornata:** 16/10/2026, 20:38 UTC (22:38 CEST). La verifica distingue: (1) controlli
live su GitHub e sul sito pubblicato, (2) misure locali sui dati/versione correnti, (3) fatti storici
e condizioni esterne delle fonti. Il documento aggiorna l’audit pre-merge [`docs/110`](110_revisione_totale_2026-10-16.md).
**Non è un parere legale.** In questo follow-up non ho modificato codice, collettori, modello o dati e
non ho eseguito merge.

## Verdetto esecutivo

Il fix della PR #127 è in produzione e la pipeline è tornata verde. Il sito però **non offre uno stato
live affidabile**: quando la homepage pubblicata è stata controllata alle 20:38 UTC mostrava ancora
Heerenveen–Excelsior 0–0 «in corso» e quattro altre gare «in programma», mentre lo scoreboard ESPN
raccolto nel run della stessa giornata riportava tutte e cinque le gare in corso, con punteggi e fasi
sensibilmente diversi. La spiegazione tecnica più forte è la cache persistente: il run ha riutilizzato
le fixture FotMob senza richieste HTTP, con TTL di 6 ore, mentre lo scoreboard ESPN è stato richiesto
alla rete con TTL di 1 ora. I log non conservano il timestamp effettivo di fetch per ciascun file
cache, quindi l’età precisa del payload FotMob non è dimostrabile.

È inoltre urgente una **decisione sulle autorizzazioni delle fonti**. Le pagine pubbliche consultate
contengono restrizioni esplicite su accesso automatico o uso sistematico per FotMob, Disney/ESPN e
Football-Data.co.uk; Understat disallowa i crawler nel proprio `robots.txt`. L’applicabilità giuridica
ai singoli endpoint e al progetto non viene determinata qui. Non aumentare la frequenza dei fetch né
aggiungere dipendenze da queste fonti prima di una decisione informata. Il dato «0 coordinate
Open-Meteo» riportato in docs/110 era un’interpretazione errata: si veda la rettifica sotto.

## 1. Stato live: progetto, workflow e pubblicazione

- **PR #127** ([fix delle notizie Vita/Clima](https://github.com/uamisjd/football-deep-analyzer/pull/127)) è stata fusa il 16/10 alle **19:48:51 UTC**; merge commit `0ae98bca`. Non ho effettuato il merge.
- Il daily [#38957677291](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38957677291) è partito alle **19:48:55 UTC** ed è terminato alle 20:07:03 con `run`, `deploy` e `notify` riusciti. La CI post-merge [#38957677296](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38957677296) ha completato i job `test`, `site` e `browser` con successo. Il commit dei dati su `main` osservato dopo il run è `0e9b864`; l’issue #126 è chiusa.
- Nelle query GitHub effettuate prima di aprire la PR di sola documentazione di questo audit non risultavano altre PR o issue aperte.
- **Controllo diretto del sito**: alle 20:38 UTC la [homepage pubblica](https://uamisjd.github.io/football-deep-analyzer/) riportava ancora `AGGIORNATO 16/10/2026 21:54` (ora italiana), 5 gare / 5 campionati / 5 su 5 modellate, «1 in corso / 4 in programma» e `SC Heerenveen 0–0 Excelsior`. Indicava anche Frankfurt–Köln delle 20:30 come prossimo calcio d’inizio, benché quell’orario fosse già trascorso. La pagina è un artefatto statico; l’orario mostrato è di generazione e non certifica quando ogni fonte è stata aggiornata.
- Il workflow `daily.yml` è schedulato cinque volte al giorno (04:07, 10:11, 14:17, 18:23, 21:30 UTC); GitHub non garantisce l’avvio esattamente all’ora prevista. Non è una copertura minuto per minuto.

## 2. Problema prioritario: fixture stale e stato live discordante

Ho confrontato la fotografia `data/processed` del run riuscito del 16/10. `fixtures.parquet` contiene gli
stati usati dal generatore del sito; `espn_events.parquet` conserva separatamente lo scoreboard. Le
cinque partite della giornata risultano così:

| Partita | Calcio d’inizio UTC | Fixture FotMob salvata e mostrata dal sito | ESPN scoreboard nel run (19:49–19:50 UTC) |
|---|---:|---|---|
| SC Heerenveen–Excelsior | 18:00 | `live`, 0–0 | `live`, 4–0, 90′ |
| Frankfurt–Köln | 18:30 | `scheduled`, nessun punteggio | `live`, 0–0, 59′ |
| Frosinone–Sassuolo | 18:45 | `scheduled`, nessun punteggio | `live`, 3–2, intervallo |
| Le Mans–Toulouse | 18:45 | `scheduled`, nessun punteggio | `live`, 0–1, 48′ |
| Deportivo A Coruña–Levante | 19:00 | `scheduled`, nessun punteggio | `live`, 0–0, intervallo |

**Verificato nel codice:** `src/fda/site/build.py` costruisce i gruppi «in corso / in programma /
terminate» da `fixtures.status`; la raccolta ESPN in `src/fda/collect.py` salva eventi separati e non
li riconcilia con le fixture. Il risultato osservabile è la homepage con 1 gara live e 4 programmate,
nonostante lo scoreboard di quel run avesse cinque eventi live. La scheda pubblica di Heerenveen mostra
0–0, mentre il dato ESPN dello stesso run riporta 4–0 al 90′. Questo accerta la discordanza tra le due
fotografie, non stabilisce da solo quale fornitore abbia ragione su ogni singolo evento.

**Evidenza sulla cache e limite della diagnosi:**

1. `config/sources.yaml` assegna **6 ore** alle fixture FotMob e **1 ora** allo scoreboard ESPN.
   `src/fda/http.py` determina la validità dal `mtime` del file cache.
2. `.github/workflows/daily.yml` ripristina `data/cache` da run precedenti e la salva nuovamente dopo
   la raccolta. La cache Actions `fda-http-38944906063`, prodotta dal run #287, è stata creata alle
   **18:20:42 UTC** e riutilizzata alle **19:49:41 UTC**, durante il daily post-merge.
3. Nel nuovo run `source_status` registra **0 richieste HTTP FotMob** e **3 richieste scoreboard ESPN
   per lega** nelle leghe interrogate. L’endpoint ESPN è stato interrogato dalla rete nel run,
   quindi la raccolta è più recente della risposta FotMob riutilizzata; ciò non certifica l’ora di
   aggiornamento interna del fornitore. FotMob non è stata ricaricata dalla rete.
4. La fixture FotMob conservata mostra esattamente uno stato live e quattro gare non iniziate,
   coerente con una fotografia precedente ai calci d’inizio delle quattro partite serali. È una
   spiegazione tecnica **fortemente supportata**, ma non una prova del timestamp effettivo di ciascun
   payload: `source_status` non ha un campo `last_fetched_at`, e l’ora di creazione dell’archivio
   GitHub non è l’ora di fetch del singolo file.

La correzione non è «aggiornare il sito più spesso» a qualunque costo. Prima vanno risolti i diritti
sulle fonti; poi occorre rendere visibile l’età del dato e definire uno stato non ingannevole quando la
fixture è stale. Senza un feed live autorizzato, non presentare uno status in cache come conferma
attuale. Un gate di qualità dovrebbe misurare la freschezza e segnalare la discordanza, non nascondere
il conflitto tra fornitori.

## 3. Misure locali e qualità verificata

Esecuzione locale sulla fotografia corrente, senza usare i risultati come prova dello stato del sito
pubblico:

- `pytest`: **1.047 test passati**; `ruff check .`: nessun errore; `pip check`: nessun conflitto di
  dipendenze.
- `fda build`: **506** pagine partita, **2.364** fixture, **7.602** giocatori.
- `scripts/verify_site.py`: **247.770 controlli, 0 problemi**; `scripts/parita_schede.py`: **66**
  schede senza differenze; `scripts/resa_375.py`: **28.886** misure, 0 problemi. Tutti e tre i gate
  sono terminati con codice 0.
- Build locale `site/`: **154.168.061 byte**, 4.324 HTML e 4.339 file complessivi (circa 147 MiB).
  La misura è sul filesystem del clone locale, non sulla risposta di Pages.
- GitHub API riportava `size=754527 KB` per il repository al controllo del 16/10 20:06 UTC, +92 KB
  rispetto alla misura puntuale citata in docs/110. È un delta tra due istanti, non una curva di
  crescita né un confronto diretto con i byte del sito. Pages consente al massimo 1 GB per il sito
  pubblicato e raccomanda un repository sorgente sotto 1 GB: al momento il sito generato è sotto il
  limite, ma il repository versionato va misurato nel tempo ([limiti GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)).
- Playwright è stato verificato dalla CI GitHub; non l’ho rieseguito localmente in questo audit.

**Modello e calibrazione:** la pagina locale/pubblica di accuratezza riporta 218 partite valutate, di
cui 137 con la ricetta corrente; RPS **0,1990** contro **0,2267** naive. Il backtest walk-forward su
5.960 partite riporta RPS **0,1987** contro **0,2313**. Nel campione live di 218, Over 2,5, Over 3,5
e «entrambe a segno» sono fuori dall’intervallo al 95% e sottostimati rispetto alle frequenze
osservate. È un segnale da monitorare, non una base sufficiente per cambiare modello: i campioni sono
ancora limitati e valgono le soglie preregistrate in vigore. Nessuna promozione di modello effettuata.

## 4. Fonti, condizioni e limiti d’uso da decidere

Le seguenti pagine sono state consultate il 16/10/2026. Condizioni pubblicate e accessibilità tecnica
non equivalgono a un parere legale; non è stato stabilito quale contratto regoli ogni endpoint né se
l’attività specifica rientri in un’eccezione applicabile.

| Fonte | Evidenza rilevante | Implicazione prudente |
|---|---|---|
| **FotMob** | La [FAQ ufficiale](https://www.fotmob.com/faq) dice che servizi automatici (robot, crawler, indexing) e uso sistematico o regolare non sono permessi. Il progetto la usa come fonte primaria per fixture e molti dettagli. | Rischio alto rispetto alla raccolta ricorrente: chiedere autorizzazione o valutare una sostituzione; non aumentare frequenza. |
| **ESPN / Disney** | I [termini Disney in italiano](https://disneytermsofuse.com/italian/) (ultimo aggiornamento 10/07/2014) includono ESPN tra i marchi e vietano accesso, monitoraggio o copia con robot, spider, scraper o altri mezzi automatici/manuali senza autorizzazione scritta. La pagina indirizza i residenti in Italia che usano servizi specifici per l’Italia a termini separati, non verificati in questo audit. I [termini statunitensi](https://disneytermsofuse.com/english/) sono più recenti (24/05/2024), ma non dimostrano quali condizioni disciplinino questo endpoint. | Il codice usa `site.api.espn.com/apis` (configurato in `config/sources.yaml` e chiamato da `src/fda/sources/espn.py`); ho consultato anche i [termini ESPN](https://support.espn.com/hc/en-us/articles/360035445091-Terms-of-Use), ma non ho trovato una licenza ufficiale per l’uso automatico di questo endpoint nel progetto. Accessibilità pubblica ≠ autorizzazione. Chiarire per iscritto; non usare ESPN come fallback di produzione prima della decisione. |
| **Understat** | Il [robots.txt](https://understat.com/robots.txt) restituisce `Disallow: /` per i crawler. La fonte è usata come supporto per dati xG in più leghe. | Segnale esplicito contro il crawling; verificare termini/permesso prima di continuare o ampliare la raccolta. |
| **Football-Data.co.uk** | Il [sito della fonte](https://football-data.co.uk/data.php) dichiara che l’uso gratuito è inteso per individui privati e non per prodotti commerciali o prodotti di training con bot/scraper/AI. Il progetto usa dati storici nei modelli. | La disponibilità dei CSV non risolve i diritti per pubblicazione o uso modellistico; chiedere chiarimento o trovare dati con licenza adatta. Non confondere questa fonte con Football-Data.org. |
| **Open-Meteo** | Il piano gratuito è per uso non commerciale; i dati sono CC BY 4.0 e richiedono credito appropriato, link alla licenza e indicazione delle modifiche ([pricing](https://open-meteo.com/en/pricing), [licenza](https://open-meteo.com/en/licence)). | Nel run esaminato non è servito alcun forecast Open-Meteo; prima di riattivare/mostrare dati del fallback verificare attribuzione completa e perimetro non commerciale. |
| **Google News RSS e altri feed** | Non è stata completata una verifica autonoma delle condizioni di riuso per ogni feed/articolo e delle regole di conservazione. | Il registro delle fonti è incompleto: controllare titolo, estratto, attribuzione, retention e uso pubblico separatamente, senza presumere che RSS significhi licenza di ripubblicazione. |

### Alternative: copertura parziale, non sostituti già approvati

- **OpenLigaDB** si descrive come progetto comunitario gratuito; la sua API di lettura non richiede
  autenticazione e i dati sono dichiarati sotto ODbL ([sito/API](https://www.openligadb.de/)). È una
  candidata da misurare su accuratezza, latenza e copertura di ciascuna delle sette leghe; non è
  stata verificata come rimpiazzo 7/7 né integrata.
- **Football-Data.org** è distinto da `football-data.co.uk`: la pagina ufficiale offre un tier
  gratuito con 12 competizioni ma risultati/programmi ritardati; i live scores sono indicati a
  **€12/mese** ([pricing](https://www.football-data.org/pricing)). Il costo contrasta con il vincolo
  di progetto a costo zero; il tier gratuito non risolve il requisito live.
- **OpenFootball Italia** dichiara dati CC0 e può aiutare sui calendari, ma non è un feed live di
  statistiche avanzate. La cartella `2026/27` di `openfootball/italy` aveva ultimo commit osservato
  il 21/09/2026 ([commit](https://github.com/openfootball/italy/commit/48954d1)); non è un sostituto
  tempestivo garantito.
- Non ho individuato, in questa revisione, una fonte **gratuita, con licenza documentata e copertura
  live verificata per tutte e sette le leghe**. Non aggiungere chiamate a OpenLigaDB o ad altri
  fornitori finché non sono verificati licenza, copertura e limiti.

## 5. Rettifica meteo a docs/110

La frase di docs/110 «Open-Meteo ha zero coordinate» era errata. Nel dettaglio `source_status`,
`coordinate 0` significa **zero gare future saltate perché prive di coordinate**, non zero coordinate
disponibili. Nel run del 16/10 `openmeteo:*` ha 0 richieste e 0 righe perché il meteo FotMob era già
presente per tutte le gare future valutate: i dettagli riportano `meteo FotMob N · coordinate 0 ·
previsione assente 0`. Non è una lacuna di copertura Open-Meteo; il fallback semplicemente non era
necessario.

La fotografia `match_info.parquet` ha coordinate, descrizione, temperatura e vento in **507/507**
righe; la probabilità di precipitazione è disponibile in **90/507**. La sonda settimanale su 45,48°N /
9,12°E verifica la risposta del servizio in quel punto, non una copertura generale. **Lacuna per un
uso futuro:** il template (`src/fda/site/templates/match.html`) etichetta il dato con il testo
«previsione Open-Meteo», ma non linka la licenza né indica le modifiche; il footer riporta solo il
nome del provider. La pagina ufficiale richiede credito, link alla CC BY 4.0 e indicazione delle
modifiche. Poiché in questo run non è stato pubblicato alcun forecast Open-Meteo, è una condizione da
risolvere prima di riattivare il fallback, non un problema di forecast presenti in questa fotografia.

## 6. Sicurezza e punti non verificati

- Le API GitHub non hanno permesso di verificare branch protection e stato delle scansioni di
  sicurezza/code scanning; `docs/110` registra inoltre gli alert Dependabot come disabilitati alla
  data di quel controllo. Non li dichiaro attivi o risolti in assenza di una nuova verifica nella UI.
- La cache GitHub usata dal daily è una cache di trasporto, non un registro completo della provenienza:
  mancano l’ora dell’ultima fetch per ogni risorsa e l’età mostrata nel sito.
- I contatori di `verify_site` certificano coerenza interna dei dati pubblicati e struttura; non
  sostituiscono un controllo di freschezza o di concordanza tra fornitori. La discordanza live appena
  misurata non ha fatto fallire il deploy.
- Non è una revisione visiva/manuale di tutte le 506 schede o 4.324 pagine HTML: il giudizio si basa
  sui gate automatici, sulla homepage live e su pagine campione consultate nell’audit complessivo.
  Non erano disponibili metriche di banda Pages o traffico utenti; il limite soft di 100 GB/mese non
  è stato misurato.
- La copertura ODbL/OpenLigaDB su tutte le leghe, le condizioni specifiche del sito Disney per
  l’Italia, la licenza dell’endpoint ESPN e le condizioni dei feed RSS restano da verificare.

## 7. Coda raccomandata per priorità

1. **P0 — decisione sulle fonti prima di ampliare la raccolta.** Chiedere autorizzazione scritta o
   pianificare sostituzione/disattivazione selettiva per le fonti con restrizioni esplicite. Tenere
   separata la valutazione tecnica da quella legale. Nessun collettore è stato disattivato in questo
   audit.
2. **P1 — freschezza e correttezza dello stato partita.** Dopo la decisione sulle fonti, registrare
   per ogni endpoint `last_fetched_at`, esito cache e `cache_age`; far apparire sul sito sia l’ora di
   generazione sia l’età del dato. Se lo stato della fixture non è recente, etichettarlo come non
   verificato/storico, non «in corso». Non aumentare oggi il ritmo di polling.
3. **P1 — fonte live autorizzata o requisito ridotto.** Valutare un provider con licenza verificabile
   e copertura misurata delle sette leghe; se non c’è una soluzione compatibile con costo zero,
   scegliere esplicitamente tra status non-live e cambiamento del vincolo economico. Non usare ESPN
   come correzione automatica finché la questione dei diritti è aperta.
4. **P2 — registro diritti/provenienza.** Per ogni campo tenere titolare, endpoint, licenza/termini,
   frequenza, cache, attribuzione, retention, derivati pubblicati e sostituto; datare ogni verifica.
5. **P2 — meteo.** Nessun intervento urgente sui dati correnti: coordinate complete e fallback non
   necessario. Se si riattiva Open-Meteo, verificare attribuzione CC BY 4.0 e misurare la copertura
   per gara.
6. **P2 — modello.** Continuare il monitor prospettico e il backtest preregistrato; indagare i tre
   segnali sui mercati goal solo al raggiungimento dei criteri già fissati. Nessun tuning sulla sola
   fotografia di 218 partite.
7. **P2 — capacità e sicurezza.** Rimisurare la dimensione del repository su una finestra più lunga
   e chiedere all’amministratore la verifica in UI di protezioni e scansioni. La build Pages attuale
   è sotto 1 GB; il delta puntuale di 92 KB non basta a proiettare una tendenza.

## 8. Esito e limiti del follow-up

**Stato complessivo: pipeline attiva e verde; sito online; stato live non affidabile; autorizzazioni di
alcune fonti da decidere; modello da monitorare senza modifiche.** Il fix #127 ha ripristinato la
produzione, ma non risolve la freschezza delle fixture. Il documento distingue osservazione live,
fotografia locale e condizioni storiche/esterne. Non prova l’ora precisa del payload FotMob in cache,
non certifica la correttezza assoluta di ESPN e non costituisce consulenza legale.

L’unico lavoro proposto in questa sessione è documentale: questo report, il checkpoint e le rettifiche
collegate. Ogni merge della PR documentale resta riservato all’utente.
