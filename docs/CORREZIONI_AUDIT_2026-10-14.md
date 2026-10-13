# Correzioni dell'audit — 14 ottobre 2026

Richiesta: «correggi e sistema tutto vita morte e miracoli». Seguito dell'
[`audit indipendente`](AUDIT_COMPLETO_2026-10-13_7c92c1a2.md).

## 1. Correzioni operative implementate

| Difetto verificato | Correzione | Prova di regressione |
|---|---|---|
| Oracolo [50] ingloba le notizie dell'altra squadra | Integrata la correzione della PR #115 (parser HTML), senza i suoi aggiornamenti documentali concorrenti | Tre casi della #115: entrambi pieni, uno vuoto, pagina manomessa |
| Commit del solo registro lascia working tree sporco prima del rebase | `scripts/pubblica_dati.py`: copia i soli file selezionati in worktree detached temporaneo; commit/rebase/push isolati, cleanup anche in conflitto | Test Git end-to-end su origine locale: dirty tree, full/registro, concorrenza, push race, conflitto, nulla da salvare, nuova/cancellata tabella |
| Registro scambiato per fotografia completa | Cronologia paginata, marker `FDA-SNAPSHOT: full-v1`, compatibilità con vecchi `data: run ...`; registro escluso | Registro → sera; seconda pagina; assenza di foto; limite fail-open; giornata completa con registri intermedi |
| Ripristino segnalato prima del deploy | Job `notify` con `needs: [run, deploy]`, `always()`, `ci_alert on-result`; successo solo se entrambi i job sono `success` | Matrice di 25 combinazioni, routing CLI, contract test YAML |
| Retry HTTP oltre budget | Verifica del tetto prima di ogni tentativo | Budget 1 → un tentativo; successo al retry; cache dopo esaurimento; zero e 404 |
| Diagnostica dei gate assente dall'artifact | Upload alla fine del job, anche su failure: run/verify/parità/375/fotografia | Contract test YAML |

Il checkout e il sito verificato non vengono ripristinati/stashati/cancellati dal salvataggio.
In caso di conflitto vero sul registro il run **fallisce esplicitamente**, senza sovrascrivere i
dati remoti e senza perdere quelli locali. Non si nasconde un conflitto scegliendo una versione.
La ricerca della fotografia ha un limite di 20 pagine: superarlo genera errore e quindi fail-open,
non una falsa fotografia. Un commit del registro non rinnova la rete di sicurezza delle 24 ore.

Gli input liberi del daily passano da variabili d'ambiente/array Bash e non vengono interpolati
come codice shell. Gli orari principali sono spostati di pochi minuti rispetto all'inizio dell'ora:
restano nominali, **nessuna promessa di puntualità**. Il fuso delle allerte è `ZoneInfo(Europe/Rome)`,
non un'approssimazione per mese del cambio dell'ora.

## 2. Sito e accessibilità

- Titolo Accuratezza ripulito; link al Laboratorio nel `main`, effettivamente visibile.
- Rimossi testi che dichiaravano tutta ESPN sospesa; la pagina distingue classifica, scoreboard,
  notizie, cache e richieste. Nessuna affermazione nuova sulla salute dal vivo delle fonti.
- Link nel testo e nelle tabelle sottolineati: non si riconoscono solo dal colore.
- Rimossi attenuamenti `opacity` da testi/righe informative che facevano fallire il contrasto.
  I token chiaro/scuro esistenti restano; non vengono cambiate probabilità o metriche.
- Solo le tabelle **realmente scorrevoli** ricevono Tab, ruolo regione e nome leggibile;
  aggiornamento dopo font, resize e apertura tendine. Niente tab stop su ogni tabella desktop.
- Smoke test Chromium + Playwright + axe: campione pre/post per ciascuna lega, pagine principali,
  375/1280 px, chiaro/scuro, prima Tab, tema, ricerca, link al Laboratorio e matrice nelle tendine.
  Report/screenshot in `browser-results/`, ignorati da Git.

**Misura iniziale del browser:** 84 visite (21 pagine × 2 viewport × 2 temi), **117 segnalazioni
raggruppate**: focus delle aree scorrevoli, contrasto e link distinti solo dal colore. Non sono
117 bug indipendenti, né una certificazione manuale di ciascuna segnalazione. Il successivo
campione usa anche tendine aperte e test d'interazione più estesi, quindi va dichiarato il perimetro.

## 3. CI e manutenzione

- La CI non si ferma più a pytest/Ruff: nuovo job **site** con build offline e tutti e tre i gate,
  seguito da job **browser** bloccante, artifact della build e report degli errori.
- Tutte le Actions nei sette workflow sono fissate a SHA verificati sul repository ufficiale;
  permessi del daily separati: salvataggio `contents: write`, deploy `pages/id-token`, allerta
  `issues: write` e `actions: read`, default `contents: read`.
- `requirements-ci.txt`: versioni Python runtime/dev dell'ambiente verificato, applicate nei
  workflow di installazione; `package-lock.json`: dipendenze dei test browser e integrità npm.
- Dependabot settimanale per Python e Actions; aggiornamenti raggruppati e PR limitate.
- LICENSE MIT aggiunta, coerente con la licenza già dichiarata nei metadati; README distingue
  codice, font e diritti delle fonti. Non è una nuova licenza dei dati.

Le constraints Python **non** hanno hash di integrità, e questo lavoro **non certifica assenza di
CVE**. La licenza non rende automaticamente commercializzabili i dati raccolti.

## 4. Due sezioni analitiche rimaste nella coda

Riletta Previsione ensemble (produzione, scomposizione, laboratorio, fascia storica, posizione
nella lega, primo gol) e Verifica approfondita (matrice, coda, gol totali). La loro matematica
resta sotto gli oracoli e i test esistenti; i candidati di laboratorio restano dichiarati non usati.
Le correzioni qui sono di contrasto e accesso alla prova, **non nuovi tilt o nuove probabilità**.
Matrice e istogramma mantengono distinzione fra coda di una squadra e totale gol, frequenze su
100 e limiti del modello. Non viene spacciata questa revisione per prova di superiorità ai bookmaker.

## 5. Verifiche e stato del rilascio

Prima del giro finale: **1.019 test**, Ruff 0, `pip check` OK; build **499/2.364/7.600**;
`verify_site` **242.503 · 0**, parità **59 schede**, resa 375 **28.766 · 0**.
Queste misure precedono le ultime correzioni browser: il giro finale è in esecuzione e sarà
registrato prima della consegna. I test nuovi mirati passano, incluso il salvataggio fino al push.

**PR #116** contiene ora audit e correzioni sul ramo della sessione. La correzione della #115
è inclusa, ma #115 non è stata chiusa né fusa dall'agente. Nessun merge di produzione, nessun
run di raccolta esterna o riscrittura di `main` è stato eseguito.

## 6. Cosa richiede ancora produzione / evidenza, non altre patch speculative

- Primo daily dopo il merge: **run + deploy** verdi, allerta coerente, salvataggio del solo
  registro nei run intermedi e fotografia completa serale.
- Dati `nl`/`pt` nuovi: verificare archivio e copertura effettiva su NED1/POR1 dopo raccolta;
  i titoli in fixture non certificano tutti i club del sito pubblico.
- Crescita Git: misurare una settimana di fotografie complete, non assumere −80% già ottenuto.
- Modelli: accumulare il test prospettico; nessuna promozione giustificata adesso.
- Browser/axe sono un campione automatizzato, non audit completo con lettore di schermo né
  misura Core Web Vitals degli utenti reali. Non riscrivere migliaia di righe solo per ridurle.

## Prossimo passo

Completare i gate locali e quelli della PR #116; poi merge da parte dell'utente e verifica del
primo daily fino al deploy. Registrare separatamente cosa è provato offline e cosa è pubblicato.
