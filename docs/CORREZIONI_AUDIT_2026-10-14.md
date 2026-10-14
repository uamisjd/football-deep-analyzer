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

**Giro definitivo locale completato:**
- **1.023 test passati** (248,02 s con gli altri controlli in parallelo), Ruff 0, `pip check` OK.
- Build **499 schede / 2.364 fixture / 7.600 giocatori nel catalogo**; **4.316 HTML**, sito
  **152.786.020 byte**. Il JS di accessibilità aumenta lievemente gli HTML, senza cambiare i dati.
- `verify_site`: **242.503 controlli, zero problemi**, 55 oracoli.
- Parità: **59 schede**, struttura/indice coerenti. Resa 375: **28.766 misure, zero problemi**.
- **Chromium 153 reale: 84 visite su 21 pagine, zero problemi**; 7 pre e 7 post (una scheda per lega per tipo), più
  7 pagine principali, 375/1280 px, chiaro/scuro, tendina matrice aperta e interazioni.
- Wheel: **13 template, 9 font e LICENSE inclusi**.
- `git diff cdfc85c -- data/processed src/fda/models`: vuoto; nessun modello/Parquet modificato.

Nel primo test della ricerca il nuovo harness leggeva troppo presto il DOM (il filtro ha
**debounce di 120 ms**): 4 segnalazioni spurie, **zero segnalazioni axe** dopo i fix visivi.
Corretto il test con attesa dell'esito osservabile (righe nascoste/ripristinate), non con un
cambiamento al filtro funzionante e non disattivando controlli. Il giro ripetuto è tutto verde.

**GitHub finale #116:** `test`, `site`, `browser` **SUCCESS** su `d1465b7`.
Merge autorizzato dall'utente «ok procedi»: `8a6791a`, 14/10 09:19:25 UTC.
La #115 non è stata chiusa né fusa separatamente; il suo codice era incluso nella #116.

**Primo daily reale dopo merge:** `38541503143` **FAILURE**, deploy **SKIPPED**,
notify **SUCCESS** e #114 ancora aperta con diagnostica. L'oracolo residuo [50] non
riconosce «1 voce» (`voci?`): quattro intestazioni segnalate. Regressione riprodotta
prima della patch con 5 test del template tutti falliti. Hotfix minimo `voc[ei]`,
38 test tematici verdi (10 casi nuovi nl/pt, inclusi conteggi manomessi), suite
completa **1.033 passed**: vedi [`HOTFIX_SINGOLARE_2026-10-14.md`](HOTFIX_SINGOLARE_2026-10-14.md).
I gate offline precedenti restano risultati storici veri, **non prova di ripristino in produzione**.

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

Completare suite/check della nuova PR correttiva e attendere il merge dell'utente.
Poi verificare il nuovo daily fino al deploy. #114 resta aperta fino al ripristino reale;
salvataggi e dati esteri archiviati ancora da dimostrare dal vivo.
