# Audit indipendente del progetto e del sito — 13 ottobre 2026 (UTC)

## Verdetto

**Il prodotto è sostanzioso e funzionante, ma non è corretto definirlo oggi «tutto verde».**
Il sito pubblico è raggiungibile e mantiene l'ultima pubblicazione valida; il `daily` dopo il
merge #113 è fallito. La PR #115 corregge quel guasto, ma **non corregge due ulteriori difetti
riprodotti in questa revisione nella politica di salvataggio dei dati**. Prima nuove funzioni,
poi no: la priorità è rendere affidabile il percorso completo raccolta → salvataggio → deploy.

Questa è una revisione, **non un intervento in produzione**: nessun merge, dispatch, modifica
ai Parquet o riscrittura della storia. La PR #115 appartiene a un'altra sessione e non è stata
modificata. Il riferimento locale è `cdfc85c`, ramo `arena/7c92c1a2-football-deep-analyzer`.
Documento non numerato apposta per evitare collisioni con sessioni parallele (precedente: docs/58).

## 1. Perimetro e prove

- Letti briefing, regole, checkpoint, handoff e audit recenti (104–106), configurazioni, workflow,
  storage, HTTP, generazione HTML, notizie estere, modelli e protocollo prospettico.
- Ambiente Python 3.11 ricreato e pacchetto installato da zero con extra `dev`.
- **988 test passati**, in 154,79 s; **Ruff: zero errori**; `pip check`: nessun conflitto.
- Wheel costruita: **13 template, 9 font WOFF2 e `site.css` inclusi**.
- Build locale: **499 schede partita / 2.364 fixture / 7.600 giocatori nel catalogo**.
  **4.316 file HTML**, sito **148.810.044 byte** (~148,8 MB decimali).
  Il conteggio giocatori del catalogo non è il numero delle pagine giocatore.
- Gate sulla build completa: esito registrato nella sezione 9, una volta terminati.
- Letti via `fetch_page` home, Accuratezza, Laboratorio, Stato fonti e una scheda Eredivisie
  pubblicate. **Questa è una lettura del sito reale, non una prova in browser.**
- Consultati API GitHub per issue, PR, workflow, Pages, dimensione repository, cache e artifact.
- Riproduzioni isolate: repository Git temporanei e client HTTP simulato, senza rete.

**Limiti:** nessun browser installato; nessuna misura Lighthouse/Core Web Vitals, contrasto,
interazione tastiera o screenshot reale. Le fonti FotMob/Understat/Google News non sono state
interrogate direttamente dal sandbox. I dati della nuova raccolta locale `nl`/`pt` del run
fallito non sono nel checkout; non si può certificare qui la loro copertura completa.
Il log Actions completo non è scaricabile dall'host artifact consentito: la diagnosi usa il
corpo dell'issue generato dai log, il diff della PR e il codice, non una presunta lettura del ZIP.

## 2. A che punto siamo

Il progetto non è un prototipo vuoto. È un portale statico (CalcioMetro), Python + Jinja,
Parquet/DuckDB, pubblicato su Pages, con sette leghe e pipeline schedulata cinque volte al giorno.
Comprende schede pre/post partita, giocatori, forma e xG, assenze, contesto, mercato, probabilità,
proiezioni di stagione, verifica delle previsioni e laboratorio.

Dati locali: **2.364 fixture**, di cui **440 finite, 1.923 programmate e 1 annullata**;
**2.153 previsioni**, **7.800 righe notizie**, **3.856 righe prospettiche** (due varianti su
1.928 partite), **32 Parquet**. Non tutte le partite programmate hanno una scheda dettagliata:
il calendario completo e la finestra delle schede sono cose diverse.

Sito pubblico letto in questa sessione:
- home: **0 partite il 13 ottobre**, ripresa indicata il **16 ottobre con 5 partite**;
- ultimo aggiornamento della home **13/10 22:06 ora italiana** (20:06 UTC), precedente al run rosso;
- Accuratezza: **218 gare valutate**, **137 con ricetta corrente**, RPS **0,1990**, Brier **0,5988**,
  esito più probabile corretto nel **52%**; **20 gare finite senza previsione pre-kickoff**;
- backtest: **5.960 gare**, RPS calibrato **0,1987**; il sito dichiara correttamente che l'effetto
  sul campione usato per stimare la calibrazione non è una nuova prova fuori campione;
- Laboratorio: **29 varianti**; nessuna promossa. Test prospettico γ 1,12: **5 gare**, non zero,
  ΔRPS **+0,0059**, IC **[−0,0052; +0,0164]**, soglia 200 gare non raggiunta.

**Importante:** «RPS 0,199» non dimostra guadagno da scommesse, né superiorità al mercato.
La base naive e le quote bookmaker sono riferimenti distinti; il confronto va fatto sulle stesse
gare e con quote disponibili prima del kickoff. Non promuovere un modello perché è primo in tabella.

## 3. Operatività: criticità verificate, in ordine

### P0-A — Guasto attuale: controllo [50] (già coperto dalla PR #115)

Il `daily` **#267 / 38470105610**, attivato da `cdfc85c`, è **fallito**; il job deploy è saltato.
Issue **#114 aperta** all'inizio della revisione. Il corpo dell'issue riporta **32 problemi**
nell'attribuzione delle notizie estere alle squadre.

Il controllo in `scripts/verify_site.py:check_stampa_estera` ritaglia HTML annidato tramite
regex, inglobando nel primo riquadro le voci del secondo. Il diff **#115** usa BeautifulSoup e
aggiunge tre casi (entrambi pieni, uno vuoto, HTML manomesso). Il check PR `test` è **SUCCESS**
(terminato 22:01:40 UTC), ma questo **non è ancora un deploy riuscito**.

**Azione:** completare il percorso della #115 secondo la policy merge dell'utente e verificare
un nuovo `daily` fino al job `deploy`. Nessun merge eseguito in questa sessione.

### P0-B — Il commit del solo registro impedisce il rebase (nuovo, riprodotto)

In `.github/workflows/daily.yml`, quando la fotografia non va salvata:
1. si aggiungono tutti i dati;
2. `git reset -q` li toglie dall'indice **ma non dal working tree**;
3. si committa solo `prospettico.parquet`;
4. si esegue `git rebase origin/...`.

Se è cambiato anche un altro Parquet, il rebase termina con codice **1**:
`error: cannot rebase: You have unstaged changes. Please commit or stash them.`
Riprodotto con due file `news.parquet`/`prospettico.parquet` in un repository temporaneo con
origine locale, senza modificare questo repository. La PR #115 **non tocca quel passo**.

**Conseguenza:** il prossimo run intermedio con registro modificato può passare tutti i gate
ma fallire prima del deploy. Se il registro non è cambiato, l'uscita anticipata evita il rebase:
non è quindi un guasto inevitabile di ogni run, ma di un ramo preciso e realistico.

**Correzione da progettare:** separare il working tree di commit da quello usato per la build
(es. worktree temporaneo), oppure gestire esplicitamente le modifiche non committate prima del
rebase. Conservare il sito generato e l'eccezione di preregistrazione. Testare **l'intero passo fino
al push**, anche con un commit concorrente; non basta verificare `git add`/`git commit`.

### P0-C — Il registro è scambiato per fotografia completa (nuovo, riprodotto)

`scripts/fotografia_dati.py:ultima_fotografia` interroga i commit con
`path=data/processed&per_page=1`. Ma anche il commit del **solo** `prospettico.parquet` tocca
quel percorso. `decide()` restituisce `False` se l'ultimo commit è della giornata corrente,
prima di controllare l'orario serale.

Prova deterministica con le funzioni reali:
- fotografia completa **12/10 21:30 UTC**;
- solo registro **13/10 18:15 UTC**;
- run serale **13/10 21:00 UTC**;
- con la data della fotografia completa: **True**;
- con la data del registro (quella restituita dalla query): **False**, «fotografia di oggi già salvata».

**Conseguenza:** dopo aver risolto P0-B, i commit del registro possono continuare a far saltare
le fotografie complete, compresa la rete di sicurezza a 24 ore. Il registro modifica il clock
che dovrebbe misurare un altro oggetto. Il −80% di crescita è una stima subordinata al corretto
funzionamento della politica, non un risultato già osservato.

**Correzione:** distinguere i commit di fotografia completa da quelli del registro, con un marker
non ambiguo o selezione esplicita nella cronologia. Coprire fotografia → più registri → sera,
paginazione della storia, nessuna fotografia, errore API e confine di mezzanotte.

### P1-D — Allerta di ripristino prima del deploy (verificato nel codice)

`on-success` gira alla fine del job `run`; il job `deploy` viene **dopo**. Eppure
`format_recovery_comment_body` dichiara «deploy su GitHub Pages eseguiti» e chiude la issue.
Un fallimento del deploy non passa dall'allerta del job precedente.

**Non è un guasto di deploy osservato oggi**: è una lacuna certa del percorso di allerta.
Spostare ripristino/fallimento in un job finale che legga l'esito di **entrambi** i job;
provare deploy fallito e deploy saltato. Mostrare lo stato della pubblicazione, non solo delle fonti.

### P1-E — Il budget HTTP può essere superato dai retry (nuovo, riprodotto)

`src/fda/http.py:get_bytes` verifica `max_requests` prima del ciclo, non prima di ciascun
retry. Con **max_requests=1**, **max_retries=3**, errore simulato senza rete e attese disattivate:
**3 tentativi contati**. Il massimo può essere superato fino a `max_retries−1` tentativi in una
singola chiamata vicina al tetto; non è una prova di richieste abusive osservate sulle fonti.

Controllare il budget a ogni tentativo e coprire successo al retry, 429/5xx, 4xx definitivo,
cache hit e budget zero/esaurito. Distinguere le **168 ricerche logiche** previste per le notizie
dalle richieste HTTP reali: cache e retry rendono scorretto promettere sempre «+36 richieste».

## 4. Contenuti e qualità del sito

### Difetto certo: HTML nel titolo della pagina Accuratezza

`src/fda/site/templates/accuracy.html:2` contiene un `<p>` con link al laboratorio **dentro**
`{% block title %}`. Il sito pubblico restituisce quel markup nel titolo; la build locale ha
un titolo di **181 caratteri** e **zero link `laboratorio.html` nel `main`**.

**Effetto:** titolo della scheda browser/SEO contaminato e link d'approfondimento non visibile nel
corpo. Spostare il paragrafo nel contenuto; test di titolo privo di markup e link nel `main`.
È un fix piccolo e misurabile, ma meno urgente della pipeline.

### Parità della struttura non significa parità della copertura

Sulla build di questa sessione, **59 pre-partita**, **34 con almeno una voce di stampa italiana**:

| Lega | Schede | Con voci italiane |
|---|---:|---:|
| ITA1 | 10 | 10 |
| ESP1 | 11 | 8 |
| GER1 | 9 | 6 |
| ENG1 | 10 | 5 |
| FRA1 | 9 | 5 |
| NED1 | 9 | 0 |
| POR1 | 1 | 0 |

I **10 blocchi esteri** sono presenti ma vuoti sui dati versionati (colonna `language` ancora
assente in `news.parquet`). Non è la prova che la nuova raccolta non funzioni: il run rosso ha
costruito titoli olandesi reali, ma non ha salvato/pubblicato i dati. Dopo il ripristino misurare
schede con voci e qualità per **entrambe** le lingue; non trasformare il campione dei titoli
congelati in promessa di copertura sul sito reale.

Restano da chiudere le due revisioni editoriali già in coda: **Previsione ensemble** e
**Verifica approfondita / risultati esatti e distribuzione gol**. La scheda letta è ricca ma lunga:
la metodologia può occupare molto spazio; valutare una gerarchia riassunto → prova → metodo
con test utenti/browser, senza rimuovere informazioni obbligatorie né abbassare i filtri.

**Testi stantii osservati:** `stato.html` e metodo della card notizie descrivono ESPN sospesa per
403, mentre la tabella pubblica mostra scoreboard OK con richieste reali e `espn:NEWS` OK.
Dati da cache e endpoint differenti vanno distinti: non sostituire la frase con «ESPN funziona
tutto», ma renderla dipendente dal componente/stato attuale.

## 5. Architettura, manutenzione e sicurezza

**Punti forti:** sito statico (nessuna API pubblica con login/database), autoescape Jinja attivo,
font locali, cache/rate limit/backoff, fallback dichiarati, preregistrazione con controllo temporale,
misure della previsione pubbliche e invarianti di pubblicazione bloccanti.

**Debiti misurati:** `analysis.py` **7.460 righe**, `verify_site.py` **6.180**, `build.py` **1.431**.
La lunghezza non dimostra un bug, ma aumenta l'accoppiamento fra produzione e controllo.
Rifattorizzare a piccoli moduli di dominio con resa/dati invariati, non riscrivere il portale.

**CI:** `tests.yml` esegue Ruff e pytest, **non la build completa con i tre gate sui Parquet**.
Il daily ha invece i gate ma li esercita dopo il merge. Il caso #267 dimostra che suite verde e
archivio privo del nuovo schema non bastano. Aggiungere un fixture d'integrazione con dati nuovi
non vuoti, casi negativi/manomessi e una prova del workflow Git. Prima misurare i tempi della CI.

**Supply chain:** dipendenze Python con soglie minime, nessun lockfile versionato; Actions
riferite a tag maggiori, non SHA completi. L'installazione attuale passa, ma non è riproducibile
nel tempo. Introdurre constraints/lock verificato e aggiornamenti controllati, SHA o lock delle
Actions con permessi minimi per job. Nessun CVE è stato certificato o escluso da questo audit.

**Licenza:** `pyproject.toml` dichiara MIT, ma manca una LICENSE del progetto alla radice;
GitHub API restituisce `license: null` (la licenza dei font è un'altra cosa). Chiarire la licenza
del codice e separarla dai diritti d'uso dei dati/fonti. Endpoint gratuiti non equivalgono a una
licenza di ridistribuzione: eventuale apertura commerciale richiede una revisione specifica.

## 6. Costi e sostenibilità

- GitHub API: repository **743.109 KB** (misura remota, non dimensione di questo clone shallow).
- API cache: **68 voci**, **1.938.088.913 byte restituiti** nella risposta consultata;
  non dichiarati come censimento di tutta la paginazione.
- Artifact: **65 totali**, **76.499.088 byte sulla prima pagina** (non il totale di tutti gli artifact).
- Sito ~148,8 MB, molto sotto 1 GB; `prossime.html` **493.280 byte**, risultati **345.342**.
- Nei **100 run di main** consultati (02/10–13/10), **76 daily: 38 successi e 38 fallimenti**.
  Non è un tasso dell'intera vita del progetto, né prova che le correzioni recenti non valgano:
  prima dell'ultimo rosso ci sono quattro daily verdi consecutivi nel campione.

Cinque cron non garantiscono cinque deploy né puntualità. La riduzione delle fotografie è una
buona decisione, ma P0-B/P0-C vanno risolti e il risultato misurato per almeno una settimana.
Non riscrivere ora `main`, non introdurre LFS a occhi chiusi e non acquistare un server solo
per mascherare bug del workflow. Più avanti valutare snapshot esterni/versioni giornaliere,
retention esplicita e un indicatore indipendente di ultimo deploy riuscito.

## 7. Ricerca esterna e conseguenze pratiche

Riferimenti consultati il 13/10; servono a orientare le decisioni, non a sostituire le prove sul repo.

- GitHub Pages: **sito pubblicato massimo 1 GB**, banda soft **100 GB/mese**; il limite soft
  di 10 build/ora non si applica al workflow Actions personalizzato.
  [1](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
  → la dimensione attuale del sito non è l'emergenza; non confonderla con la storia Git.
- GitHub documenta possibili ritardi e job schedulati persi sotto carico, soprattutto a inizio ora.
  [1](https://docs.github.com/en/enterprise-server@3.4/actions/managing-issues-and-pull-requests/scheduling-issue-creation)
  → valutare minuti meno affollati, ma nessuna promessa di puntualità; pagina di freshness e allerta
  sono più importanti di una modifica cosmetica al cron.
- GitHub raccomanda protezioni delle dipendenze workflow: lockfile e/o SHA completi.
  [1](https://docs.github.com/en/actions/reference/security/secure-use)
  → aggiornamenti controllati, soprattutto dove il token può scrivere dati o issue.
- Il Brier è una scoring rule strettamente propria; il suo valore dipende anche da discriminazione
  e incertezza, non solo calibrazione.
  [2](https://scikit-learn.org/stable/modules/model_evaluation.html)
  → affiancare reliability diagram, numerosità, confronto appaiato e split temporali; non leggere
  la percentuale di esiti azzeccati come qualità sufficiente delle probabilità.

## 8. Piano consigliato e criteri di chiusura

1. **Ripristino:** #115, P0-B e P0-C. Chiusura solo con daily verde **incluso deploy**, fotografia
   completa serale verificata e run intermedio con solo registro pubblicato senza rebase sporco.
2. **Affidabilità:** allerta dopo deploy; test integrazione nuovi schemi + Git; budget retry.
   Chiusura con prove deliberate di fallimento e ripristino, non solo test sul percorso felice.
3. **Fix editoriale certo:** titolo Accuratezza, testi ESPN dinamici; poi ultime due sezioni.
4. **Qualità reale:** dati `nl`/`pt` salvati/pubblicati, copertura per lega, deduplica e pertinenza;
   test in browser mobile/desktop, light/dark, navigazione/filtri, tastiera, performance.
5. **Manutenzione:** constraints/lock, Actions, licenza, piccoli moduli, crescita Git misurata.
6. **Modelli:** accumulare il prospettico preregistrato. Nessuna promozione oggi.

## 9. Gate finali sulla build completa

- `verify_site`: **242.493 controlli numerici, zero problemi**, 55 oracoli dichiarati
  (32 indipendenti, 20 misti, 3 specchi).
- `parita_schede`: **59 schede**, struttura identica con 27 id, indice identico con 16 voci;
  testo visibile minimo 32.114, mediana 37.721, massimo 41.641 caratteri.
- `resa_375`: **28.766 misure, zero problemi**. È una stima delle larghezze basata su CSS/font,
  non una prova in browser; alcuni simboli non hanno metrica nel font e sono dichiarati dal tool.
- Exit code dei tre gate: **0 / 0 / 0**.

I risultati intermedi ottenuti durante la build sono esclusi perché il sito era ancora incompleto.
Non costituiscono difetti del prodotto. Il controllo [50] passa su dati locali senza notizie
`nl`/`pt`: proprio questo caso non può escludere il guasto verificatosi nel daily con dati nuovi.
La variazione rispetto ai conteggi di docs/104 (498 schede / 58 pre-partita) non è una misura di
miglioramento: build e selezione delle pagine dipendono anche dall'istante di esecuzione.

## Prossimo passo

Risolvere insieme i due difetti del salvataggio e coordinare il ripristino con la PR #115;
solo dopo un deploy verificato riprendere la revisione delle sezioni e i miglioramenti di prodotto.
