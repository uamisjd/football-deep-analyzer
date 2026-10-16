# Revisione totale — 16 ottobre 2026

**Fotografia dell’audit:** 16/10/2026, circa 17:11 UTC; **aggiornamento live:** 16/10/2026,
18:32 UTC (20:32 CEST). Il branch di partenza e `main` erano a
`8715a41e43ed91bd4ace4826563114a5491ce68e`. Questo documento separa i controlli rifatti oggi,
le osservazioni aggiornate del sito pubblico e i numeri storici ripresi dai documenti precedenti.
Non è un parere legale.

## Verdetto in breve

Il progetto è un’applicazione statica ampia, automatizzata e con molti controlli proprietari: i
gate locali rifatti oggi sono verdi e il difetto che ha fermato il daily è stato riprodotto,
corretto sul branch e coperto da una regressione. **La produzione non ha ancora ricevuto la
correzione:** due run consecutivi su `main` (#286 e #287) hanno fallito al controllo [49]; l’ultimo
deploy resta quello delle 09:19 UTC. Alle 18:32 UTC la homepage è ferma ai dati delle 11:07 CEST e
mostra come «in programma» una partita il cui calcio d’inizio è già passato. La PR
[#127](https://github.com/uamisjd/football-deep-analyzer/pull/127) è aperta, `MERGEABLE` e con
`test`, `site` e `browser` verdi sullo SHA `4ef6f13`; il merge resta all’utente, come da regola del
progetto.

Il rilievo più importante emerso dalla ricerca sulle fonti non è un bug: le condizioni pubblicate
da FotMob, Understat e Football-Data.co.uk sono in tensione con gli accessi automatici e ricorrenti
e con l’addestramento/uso modellistico che il progetto effettua. Non ho fermato i collettori e non
traggo conclusioni legali: serve una decisione documentata, un’autorizzazione o una migrazione
mirata. Le alternative gratuite individuate coprono solo una parte dei dati, non sono un rimpiazzo
integrale immediato. Nuovo rilievo operativo: OpenMeteo ha **zero coordinate e zero righe previsionali
per tutte e sette le leghe**; la sonda settimanale su una sola località non misura la copertura
meteo delle partite.

## 1. Stato GitHub e sito pubblico — verificato oggi

- `main`: `8715a41`; **PR #127 aperta** e **issue #126 aperta**. PR #127 è `MERGEABLE`; i check
  `test`, `site` e `browser` risultano verdi sul head `4ef6f13` (run push #38941230956 e PR
  #38941239498). Il fix non è ancora entrato in `main`.
- Daily riuscito precedente: [run #38877192657](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38877192657),
  avviato alle 08:57:48 UTC e terminato alle 09:20:03 UTC. L’ultimo deployment Pages censito via
  API è stato creato alle 09:19:39 UTC, sullo SHA `c348074d0bb5cfce6b759520c51c3e1ac432e768`.
- Daily fallito #286: [run #38918710431](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38918710431),
  avviato alle 14:48:08 UTC e terminato alle 15:06:31 UTC. La build è arrivata a
  `scripts/verify_site.py`; la verifica [49] del Clima è fallita e deploy/commit dati sono stati
  saltati.
- Daily fallito #287: [run #38944906063](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38944906063),
  su `main`/`8715a41`, avviato alle 18:07:26 UTC e terminato alle 18:24:29 UTC. Ha fallito di
  nuovo `verify_site` [49]; la pubblicazione Pages è stata saltata. Il commento automatico più
  recente sull’issue #126 riporta le stesse due anomalie: `5749704.html`, Sassuolo «sommario senza
  il conteggio dei marcatori (1)» e voce «Frosinone-Sassuolo, protesta della Curva» non marcata
  contro l’atteso (`True`). Il body dell’issue cita ancora #286, ma il commento è riferito a #287.
- Rettifica degli orari: `.github/workflows/daily.yml` dichiara cron nominali **04:07, 10:11,
  14:17, 18:23 e 21:30 UTC**. Il run #287 è iniziato alle **18:07 UTC**, prima del cron 18:23;
  il #286 era partito dopo il nominale 14:17. Il prossimo orario nominale configurato è 21:30 UTC
  (23:30 CEST), ma l’anomalia osservata impedisce di promettere quando GitHub avvierà davvero il
  run.
- Ho consultato la [homepage pubblica](https://uamisjd.github.io/football-deep-analyzer/), lo
  [stato delle fonti](https://uamisjd.github.io/football-deep-analyzer/stato.html) e le schede
  [Frosinone–Sassuolo](https://uamisjd.github.io/football-deep-analyzer/partite/5749704.html) e
  [Heerenveen–Excelsior](https://uamisjd.github.io/football-deep-analyzer/partite/5781769.html).
  Il deployment GitHub Pages più recente resta quello delle **09:19:39 UTC**, SHA `c348074`.
  Homepage: dati aggiornati alle **11:07 CEST** (09:07 UTC), **5 partite**, **5/5 con modello**,
  **0 in corso / 5 in programma**; fonti aggiornate fino a circa **11:01 CEST**. Alle 20:32 CEST
  l’orario previsto di Heerenveen–Excelsior (20:00) è trascorso da 32 minuti: il riquadro principale
  dice «in corso o appena iniziato», ma i contatori e la card la classificano «In programma» e la
  scheda dice «Analisi pre-partita». È una contraddizione interna e un’informazione non aggiornata
  rispetto all’orario pubblicato; non ho verificato un live-score esterno. Il payload live è quello
  dell’ultimo deploy, non quello del run fallito.
- Il download dei log/artifact da Actions ha restituito `EOF` sia per #286 sia per #287. Per #287,
  però, il commento automatico su #126 include un estratto di `run.log` e il `verify.log` con gli
  errori esatti riportati sopra; non è il dump completo della raccolta e non lo confondo con i
  Parquet locali.

### Perché i dati locali non sono la fotografia esatta della produzione

Il daily raccoglie e costruisce il sito con dati freschi, ma la regola `docs/105` conserva in `main`
una fotografia completa al giorno e può committare nel frattempo soltanto il registro prospettico.
Di conseguenza il build locale odierno, fatto dai Parquet versionati, non riproduce integralmente
la raccolta effimera del run fallito. Per esempio, `news.parquet` locale ha 10.802 righe, mentre la
pagina stato pubblica del deploy precedente ne dichiarava 11.836. La regressione qui sotto
riproduce la **classe** di errore (titolo condiviso tra le due squadre), non pretende di essere il
replay byte-per-byte dei run #286/#287.

## 2. Incidente ricorrente #286/#287: causa e correzione

### Causa strutturale riprodotta

`MatchAnalysis.build` passa le notizie di casa e trasferta a `team_news` con un `news_seen`
condiviso: un titolo duplicato viene quindi pubblicato una sola volta nella card «Vita del club».
Prima del fix, però, il set `visti` passato a `club_climate` veniva costruito separatamente dai
soli titoli di casa o dai soli titoli dell’ospite. Il controllo indipendente [49] confronta invece
il marcatore «già in Vita» con tutti i titoli visibili nella pagina.

Se un titolo comune è selezionato nel bollettino di casa, è visibile una sola volta in «Vita» e
riguarda anche l’ospite, ma il Clima dell’ospite non lo riconosceva come già pubblicato. Lo stesso
booleano alimenta il richiamo editoriale e il marcatore della voce: è quindi compatibile con le due
segnalazioni dell’issue, senza dover ipotizzare due bug distinti. Il run #287 ha riprodotto gli
stessi due messaggi su 5749704: questo conferma che il problema è rimasto in produzione perché il
fix non è ancora su `main`, non che la CI della PR sia fallita.

### Fix e regressione sul branch

In `src/fda/site/analysis.py` ora si calcola l’unione dei titoli primari pubblicati da entrambi i
bollettini e si passa lo stesso insieme a tutti e due i Climi. In `tests/test_site.py` la regressione
costruisce una notizia Udinese–Lazio presente nei dati di entrambe le squadre e verifica che:

1. «Vita del club» la pubblichi una volta sola;
2. entrambi i lati del Clima la riconoscano come già presente in Vita.

**Red/green osservato:** prima della correzione il test mostrava un solo marcatore invece dei due
attesi; dopo la correzione il test passa. Non ho modificato il collettore né i dati.

### Verifiche locali rifatte dopo il fix

| Controllo | Esito misurato il 16/10 |
|---|---:|
| `ruff check .` | passato |
| `pip check` | nessun requisito rotto |
| Suite `pytest -q` completa | **1.047 passati**, 178,08 s |
| `fda build` | **506** partite, 2.364 fixture, 7.598 giocatori |
| `scripts/verify_site.py` | **247.419 controlli numerici**, 0 problemi; 66 pagine pre-partita per i controlli Vita/Clima |
| `scripts/parita_schede.py site` | **66** schede pre-partita, struttura e indice identici |
| `scripts/resa_375` | **28.857 misure**, 0 problemi a 375 px |
| Sito generato localmente | 4.337 file (4.322 HTML), circa 158 MiB |

Le misure del sito generato sono **locali**, non l’inventario aggiornato del sito remoto. Non ho
eseguito il browser Playwright in locale: in questo ambiente non sono installati Chromium né altri
browser. La CI GitHub sul head corrente `4ef6f13` ha poi superato tutti i check: `test` (#38941239498),
`site` e `browser` (#38941230956). Sono prove della PR, **non** un deploy in produzione: `main`
resta a `8715a41`.

## 3. Modello: decisioni ancora conservative

Ho ricalcolato sul dataset versionato `prospettico.evaluate`: **5** partite finite appaiate per
γ 1,12 contro produzione, ΔRPS **+0,005851** (positivo = candidato peggiore), bootstrap 95%
**[−0,005229; +0,016406]**, γ migliore in **1/4** leghe. La regola preregistrata richiede almeno
200 partite, intervallo interamente sotto zero e almeno 5 leghe: **non promuovere γ**.

Ho inoltre rieseguito `scripts/verdetto_lab.py` sui risultati già archiviati. Nessun candidato
soddisfa insieme IC superiore < 0 e vittoria in almeno 5/7 leghe: `dc_elo_prod` resta il modello
di produzione. Alcuni candidati soddisfano una sola condizione (fra cui `dc_elo_tilt`, con IC
negativo ma 3/7 leghe; `gamma_112`, con 5/7 ma IC superiore +0,000024). È corretto non scegliere
il solo risultato favorevole.

Per contesto esterno, lo studio Serie A [arXiv:2608.11505](https://arxiv.org/abs/2608.11505) riporta
RPS 0,1972 per Dixon–Coles e 0,1905 per il mercato nel proprio campione. Non è un confronto
controllato con questo repository: periodi, quote, campione, definizioni e pipeline possono
cambiare; il numero non giustifica da solo alcun cambio di modello. I valori 0,1987/0,1990 del
report `docs/109` restano **misure storiche del 15/10**, non li ho ricalcolati oggi.

## 4. Fonti: ricerca aggiornata e decisione richiesta

Questa sezione riporta ciò che i fornitori dichiarano nelle pagine consultate il 16/10/2026 e come
si confronta con il codice. È un rilievo operativo, **non una conclusione sulla legalità**.

| Fonte | Dichiarazione verificata | Uso rilevato nel progetto | Conseguenza pratica |
|---|---|---|---|
| [FotMob FAQ](https://www.fotmob.com/faq) | L’uso di servizi automatici (robots, crawler, indexing) e l’uso sistematico o regolare non sono consentiti. | `config/sources.yaml` interroga `https://www.fotmob.com/api/data`; ci sono rate limit e cache, ma la raccolta è automatica e ricorrente. | Il rate limit non equivale a un’autorizzazione. Richiedere permesso o deliberare una fonte sostitutiva prima di ampliare l’uso. |
| [Understat robots.txt](https://understat.com/robots.txt) | `User-agent: *` / `Disallow: /`. | `src/fda/sources/understat.py` estrae dati dalla pagina; il budget è 2 s tra le richieste e la cache è 12 h. | La regola dichiarata è esplicitamente restrittiva per i crawler. Non tentare aggiramenti; chiedere autorizzazione oppure pianificare la dismissione. |
| [Football-Data.co.uk](https://football-data.co.uk/data.php) | La pagina dati dice “free”, ma specifica uso previsto per individui privati, non prodotti commerciali o di addestramento dati con bot/scraper/AI. | Il progetto usa dati storici nel modello; `config/sources.yaml` comprende download diretti e il mirror GitHub `datasets/football-datasets`. | Chiarire con il titolare l’ambito di uso/pubblicazione e non assumere che un mirror terzo conceda diritti ulteriori. |

### Alternative gratuite trovate, ma non drop-in

- **OpenFootball Italy**: repository [openfootball/italy](https://github.com/openfootball/italy), licenza CC0 dichiarata, calendario/risultati Serie A e altre competizioni. Ha una cartella 2026/27; al controllo, l’ultimo aggiornamento della stagione era il 21/09. Può essere valutato per fixture e risultati, ma non fornisce in blocco quote, xG, dati giocatore e notizie del progetto, né garantisce la stessa cadenza.
- **football-data.org** (servizio distinto da football-data.co.uk): la pagina ufficiale di [registrazione e condizioni](https://www.football-data.org/client/register) descrive un tier gratuito con 12 competizioni, dati base e 10 richieste/minuto; richiede attribuzione visibile. Le condizioni pubblicate risultano datate 2018 e vanno riconfermate prima di un’adozione; non sostituisce le statistiche avanzate/xG o lo storico quote richiesti dal modello.
- **StatsBomb Open Data**: subset gratuito per ricerca e competizioni/seasons selezionate. Il [README](https://github.com/hudl/open-data) e il [Public Data User Agreement](https://github.com/hudl/open-data/raw/refs/heads/master/LICENSE.pdf) richiedono attribuzione/logo e vietano la redistribuzione dei dati grezzi e lo sfruttamento commerciale dei dati o delle analisi derivate. È un possibile dataset di ricerca separato, non una fonte live completa per sette leghe.

### Copertura meteo: il fallback non copre le partite

Nella [pagina stato pubblicata](https://uamisjd.github.io/football-deep-analyzer/stato.html), tutte e sette le righe `openmeteo:*` sono marcate `OK`, ma hanno **0 richieste, 0 righe e 0 coordinate**. Per le 2–12 gare future per lega il meteo FotMob è invece presente. La sonda settimanale OpenMeteo verifica una sola località (45,48 N / 9,12 E): prova che il servizio risponde lì, non che le coordinate degli stadi siano disponibili né che ci sia copertura delle fixture. Priorità: reperire/associare coordinate stadio con provenienza, misurare la copertura per gara e rendere esplicito «nessuna copertura» nello stato; non disattivare il meteo primario FotMob senza alternativa validata.

**Decisione non presa:** in questo audit non ho disattivato FotMob, Understat o i feed storici. Proposta: prima di aumentare i fetch, decidere se chiedere autorizzazione scritta o sospendere i collettori che non risultano utilizzabili; quindi mappare fonte per campo, licenza, frequenza, attribuzione e piano di fallback. Le fonti gratuite reperite sostituiscono solo sottoinsiemi.

## 5. Repository, automazione e sicurezza operativa

- Il controllo live più recente di `gh repo view` riporta **754.435 KB**, **+160 KB** rispetto alla misura di 754.275 KB della prima fotografia di questo audit. È una differenza fra due misure, non una media di crescita; il clone locale è superficiale e non consente di rifare qui l’intera serie storica. Le linee guida GitHub Pages raccomandano il repository sorgente entro 1 GB e pongono un limite di 1 GB al sito: continuare a misurare, senza estrapolare una data di saturazione da un solo intervallo.
- `.github/dependabot.yml` configura aggiornamenti settimanali per Python e GitHub Actions. L’endpoint API degli avvisi Dependabot ha risposto che gli alert sono disabilitati. Gli endpoint per branch protection, secret scanning e code scanning hanno restituito 403 per permessi dell’integrazione: **non ho potuto verificarne lo stato**, quindi non li dichiaro disattivati né attivi.
- Il daily prevede cinque pianificazioni nominali al giorno. Il failure #287 è stato notificato e il deploy non è stato falsamente segnalato come riuscito: fail-closed è corretto, ma il costo osservabile è che il sito resta obsoleto durante una giornata con partite in corso. Dopo il merge va verificato un run completo `run`/`deploy`/`notify`, il timestamp/lo stato delle partite pubblicate e la chiusura dell’issue.
- La regola “una fotografia completa al giorno” riduce la crescita dei Parquet versionati; il sito pubblicato può comunque usare dati più freschi del checkout locale. Questa distinzione va mantenuta nelle prossime verifiche e nei report.

## 6. Coda operativa prioritaria

1. **P0 — codice e produzione:** la PR #127 è già aperta, `MERGEABLE` e con `test`/`site`/`browser` verdi sul head `4ef6f13`. Il merge spetta all’utente. Dopo il merge, verificare un `daily` completo, il superamento di [49], il deploy Pages e l’eventuale chiusura di #126.
2. **P0 — decisione sulle fonti:** decidere con l’utente come gestire FotMob/Understat/Football-Data.co.uk. Finché non c’è decisione, non aggiungere richieste né nuovi campi da queste fonti; non interpretare la nota come parere legale.
3. **P1 — stato sito:** dopo il deploy, ricontrollare timestamp e stato in homepage, la pagina fonti e le schede 5749704 e 5781769; la pagina Heerenveen–Excelsior era ancora pre-partita 32 minuti dopo il calcio d’inizio. Annotare lo SHA effettivamente pubblicato.
4. **P1 — meteo:** coprire le fixture con coordinate stadio verificabili e una metrica esplicita di copertura OpenMeteo; la sonda su una sola città non basta. Mantenere FotMob primario finché un fallback non è validato.
5. **P1 — repository:** ripetere la misura di `diskUsage` e dei byte delle fotografie dopo alcuni giorni completi; valutare le opzioni di `docs/109` §4 se la curva risale verso 1 GB.
6. **P1 — controllo accessi sicurezza:** chiedere all’amministratore di verificare branch protection e scansioni nella UI GitHub; valutare l’attivazione degli alert Dependabot (distinti dagli aggiornamenti settimanali già configurati).
7. **P2 — audit dati/provenienza:** aggiungere una tabella mantenuta per fonte/campo: titolare, endpoint, modalità, condizioni, cache, attribuzione, retention, sostituto e data dell’ultima verifica.
8. **P2 — modello:** continuare il test prospettico preregistrato; nessuna promozione prima delle soglie già fissate.

## Fonti esterne consultate

- [Daily #286](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38918710431), [daily #287](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38944906063), [commento diagnostico dell’issue #126](https://github.com/uamisjd/football-deep-analyzer/issues/126) e [PR #127](https://github.com/uamisjd/football-deep-analyzer/pull/127), consultati/riverificati il 16/10/2026.
- [Homepage](https://uamisjd.github.io/football-deep-analyzer/), [stato fonti](https://uamisjd.github.io/football-deep-analyzer/stato.html) e [scheda Heerenveen–Excelsior](https://uamisjd.github.io/football-deep-analyzer/partite/5781769.html), consultati durante l’aggiornamento live delle 18:32 UTC del 16/10/2026.
- [FotMob FAQ](https://www.fotmob.com/faq) e [Understat robots.txt](https://understat.com/robots.txt), consultati il 16/10/2026.
- [Football-Data.co.uk — Data](https://football-data.co.uk/data.php), consultata il 16/10/2026.
- [OpenFootball Italy](https://github.com/openfootball/italy), [football-data.org — registrazione/termini](https://www.football-data.org/client/register), [StatsBomb Open Data e User Agreement](https://github.com/hudl/open-data), consultati il 16/10/2026.
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits), già esaminati nel report del 15/10.
- [Studio Serie A su Dixon–Coles e mercato](https://arxiv.org/abs/2608.11505), riferimento contestuale, non benchmark interno.
