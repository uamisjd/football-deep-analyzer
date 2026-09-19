# 41 — Verifica dell'autoaggiornamento e coda del progetto (2026-09-19)

**Scopo.** Due domande dell'utente: (1) *l'autoaggiornamento del sito ogni tot ore funziona?*
(2) *cos'altro c'è da esaminare e verificare?* Tutto ciò che segue è **misurato oggi** con
comandi (`gh api`, `gh run list`, Parquet versionati, sito pubblicato, build locale): niente è
ripreso da un documento precedente senza essere ricontrollato. Le misure sono delle
**14:30–15:20 UTC del 19/09/2026**.

---

## 1. L'autoaggiornamento funziona — verificato dall'inizio alla fine

### 1.1 Il meccanismo (riletto, non ricordato)

`.github/workflows/daily.yml`: 5 cron UTC — `0 4`, `0 10`, `0 14`, `0 18`, `30 21` — più il
trigger `push` su `main` (`paths-ignore: docs/**, *.md`) e `workflow_dispatch`. Un solo run alla
volta (`concurrency: daily`, `cancel-in-progress: false`), timeout 40 minuti. Il job `run` fa:
install → test rapidi → `fda daily` (collect → calibrate → predict → backtest → simulate →
build) → **`verify_site`** → **`parita_schede`** → **`resa_375`** → commit dei dati →
`upload-pages-artifact`; il job `deploy` pubblica su Pages e gira **solo** sul ramo predefinito.

### 1.2 Parte davvero 5 volte al giorno

Run schedulati per giorno (`gh api .../workflows/daily.yml/runs`, evento `schedule`):

| giorno | run schedulati | esiti |
|---|---|---|
| 14/09 | 5 | 5 success |
| 15/09 | 5 | 5 success |
| 16/09 | 5 | 3 success · 2 failure |
| 17/09 | 5 | 5 success |
| 18/09 | 5 | 5 success |
| 19/09 | 2 (alle 15:10 UTC il terzo non era ancora partito) | 2 failure, poi sbloccati |

### 1.3 L'orario nominale non è l'orario reale (misurato, non stimato)

Ritardo reale dei **ultimi 20 run schedulati** rispetto all'ora del cron: **media 3,12 h**,
mediana 3,09 h, minimo **0,45 h**, massimo **5,35 h**. Il commento in testa a `daily.yml` dice
«in media 3,2 ore, da 1h39m a 5h23m»: la sostanza regge, la finestra no (il minimo osservato
oggi è 27 minuti, non 1h39m). Esito degli stessi 20 run: **16 success / 4 failure**.

Conseguenza pratica già dichiarata dal sito: l'orario in testa alla pagina («AGGIORNATO …») è
l'unico indicatore onesto di freschezza, e c'è.

### 1.4 La catena completa, verificata anello per anello (oggi)

| anello | misura |
|---|---|
| run | `35447124903`, trigger `push` (merge PR #59), 13:54:17Z → **success**, 17m19s |
| commit dei dati | **`e9af29c`** «data: run 2026-09-19 14:11 UTC [skip ci]», autore `fda-bot`, 14:11:32Z |
| deploy Pages | deployment `github-pages` creato alle **14:11:39Z** (sha `b8bfe12`) |
| sito pubblicato | intestazione «CENTRO PARTITE · **AGGIORNATO 19/09/2026 16:03**» (= 14:03 UTC, l'ora di build dentro quel run) |
| corrispondenza coi dati versionati | il sito dichiara **31** partite · **7** campionati · **7** in corso · **23** in programma · **1** terminate; `fixtures.parquet` a HEAD ha esattamente 31 gare il 19/09 con status `live` 7, `scheduled` 23, `finished` 1; `predictions.parquet` ha `made_at` massimo **14:01:50Z** |

**Conclusione: l'autoaggiornamento funziona** — raccolta, modelli, commit dei dati, build e
pubblicazione sono concatenati e l'ultimo anello (la pagina che l'utente legge) corrisponde ai
Parquet versionati nel repository.

### 1.5 Oggi però è stato fermo, e questo va detto

I run `35432745402` (08:42Z, schedulato), `35438804509` (10:57Z, push) e `35446188137` (13:34Z,
schedulato) sono **rossi tutti e tre** sul passo «Verifica il sito (verify_site)»
(`concordanza '1 assenti'`, corretto dalla PR #59). Poiché quel gate sta **prima** del commit dei
dati e **prima** della preparazione di Pages, in quei run i dati raccolti **non sono stati
committati** e il sito è rimasto fermo: l'ultimo deploy precedente è delle **23:44:23Z del 18/09**,
quindi la pagina pubblicata è stata vecchia di **14h27m** (23:44Z del 18/09 → 14:11Z del 19/09),
non delle 5 ore dei soli run schedulati.

### 1.6 Buco vero: nessun avviso quando il daily è rosso

`grep -rn "issues: write|gh issue|notify|slack|mail" .github/workflows/` → **nessuna notifica** in
nessun workflow (escono solo le righe `git config user.email`). Un `daily` rosso congela il sito
**in silenzio**: l'unico segnale è la ❌ nel tab Actions e l'orario in testa alla pagina. Con 5
run al giorno e una media di 3 ore di ritardo, un guasto serale può restare invisibile fino al
mattino dopo. È la prima voce della coda (§4).

### 1.7 Gli altri workflow schedulati: stato reale

- **`lab.yml`** (lunedì 03:30 UTC): ultimo run **14/09 success**. La **sonda delle fonti di
  fallback** (`scripts/probe_fonti.py`) è stata aggiunta il **16/09** (commit `2687c8f`), quindi
  **non è mai girata**: `data/processed/source_probe.parquet` **non esiste** e la pagina *Stato
  fonti* pubblicata lo dichiara onestamente («nessuna registrazione … finché non gira, il
  fallback meteo è dichiarato ma non verificato»). Primo run utile: **lunedì 21/09, 03:30 UTC**.
- **`benchmark.yml`** (giorno 3 del mese, 04:20 UTC): **nessun run** — ma il file è nato il
  **16/09** (`d0ca94d`), quindi la prima esecuzione è il **3/10**. Non è un guasto: è una data non
  ancora raggiunta.
- **`tests.yml`**: verde su `main` agli ultimi 3 push (19/09 13:54Z, 19/09 10:57Z, 18/09 19:36Z).
- **`font-locali.yml`**, **`diag-fetch-log.yml`**: solo `workflow_dispatch` (nessun run atteso).

### 1.8 *Stato fonti* pubblicato, letto oggi (run delle 15:54–15:59 IT)

- **FotMob**: OK su 7 leghe + coppe (380/380/306… righe, 16-17 richieste per lega).
- **Understat**: OK su 5 leghe (ENG/ESP/FRA/GER/ITA), dichiarato «riserva: la classifica primaria
  è FotMob». NED1/POR1 non coperte — coerente con `docs/02`.
- **Open-Meteo**: OK con **0 righe** e il motivo scritto («nessuna previsione utile su 8 gare
  future: meteo FotMob 8») — il fallback non serve, e si vede perché.
- **ESPN**: **15 righe SOSPESO con 0 richieste** (standings 79-80 fallimenti consecutivi,
  scoreboard 8, news 12). Il messaggio «nuovo tentativo fra 1 run» con 0 richieste **non** è una
  contraddizione: `BACKOFF_PROBE_RUNS = 4` e le pause consecutive sono 3, quindi la sonda tocca al
  run successivo (verificato leggendo `backoff.py`, non supposto).
- **transfers**: OK (132 payload, 4.235 voci).
- **`news:NEWS`: ERRORE** — «news direct Sportmediaset: SourceError: HTTP 404
  https://www.sportmediaset.mediaset.it/rss/calcio.xml». **Non è una scoperta di oggi**: è
  dichiarato aperto dal **17/09** in `docs/25` §5 e §7.2 («se il 404 continua, il feed va
  sostituito o tolto; oggi restano ANSA e Sky Sport»). Dopo due giorni il 404 è ancora lì, con
  135 richieste e 3.938 righe salvate dalle altre fonti. L'URL è scritto in
  `src/fda/sources/news.py:311`. **Non riproducibile dal sandbox** (nessun egress: `curl` →
  `SSL_ERROR_SYSCALL`), quindi la misura è quella del runner, non mia.

---

## 2. Gate rieseguiti oggi, prima di toccare qualunque cosa

Ambiente ricostruito nel sandbox (`python -m venv` + `pip install -e ".[dev]"`: il sistema è
*externally managed*, PEP 668). Base: codice di `main` a `b925e62` + Parquet versionati.

| gate | esito |
|---|---|
| `pytest -q` | **453 passed** (71 s) |
| `ruff check .` | **All checks passed!** |
| `fda build` | exit 0 — **375** schede partita · **2.364** partite · **7.492** giocatori (4m50s) |
| `scripts/verify_site.py` | **0 problemi · 151.316 controlli** (1m50s) |
| `scripts/parita_schede.py site` | exit 0 — 59 schede · 23 id · 12 voci · min 17.677 = 92% della mediana |
| `python -m scripts.resa_375` | **23.658 misure · 0 problemi** |
| `scripts/audit_match_sections.py` | exit 0 |

---

## 3. Difetti nuovi, trovati misurando (e corretti in questo giro)

Nessuno di questi era in un documento: sono usciti leggendo **il sito pubblicato** e i numeri
stampati, non i `docs/`.

### 3.1 La didascalia del punteggio diceva «calcio d'inizio» su una gara in corso

Sul sito pubblicato alle 16:03 IT: **7 schede su 7** in corso mostravano il punteggio live con la
didascalia «calcio d'inizio» — «Bologna **1–0** calcio d'inizio» con 63 minuti giocati — e l'hero
della scheda «**1–0** · calcio d'inizio · 15:00». La causa è una riga di `_matchlist.html:34`:
la didascalia era **binaria** (`finished` → «finale», tutto il resto → «calcio d'inizio»), e lo
stesso schema stava in `match.html:20`. `verify_site` era **verde con 151.316 controlli**: nessun
invariante leggeva quella stringa.

Correzione: `SiteBuilder.score_caption()` (stesso bucket dei filtri: `in corso`, `intervallo`,
`rinviata`, `sospesa`, `annullata`, `finale`, `calcio d'inizio`) usata dalle liste e dall'hero;
nuovo invariante **`[37]`** che ricontrolla ogni card e ogni hero pubblicati. Misura dopo la
correzione, sulla build locale: `index.html` → `{live: «in corso» 7, finished: «finale» 1,
scheduled: «calcio d'inizio» 23}`; hero di Bologna–Torino → «1–0 · **in corso** · calcio d'inizio
15:00»; hero di Tottenham–Aston Villa (finita) → «2–3 · risultato finale».

### 3.2 Numeri sopra 1.000 senza separatore delle migliaia, fuori dalla copertura del gate

Il controllo `[14]` di `verify_site` cercava `\d{4,}` seguito da «partite|gare» **solo dentro
`partite/*.html`** (`verify_site.py:665`: il punto era già dichiarato in `docs/40` §7a). Misurando
su tutto il sito sono usciti **quattro** casi reali, non uno:

| dove | testo pubblicato | pagine |
|---|---|---|
| `accuratezza.html` | «valutato su **5836** partite già giocate» | 1 |
| `partite/*.html` | «su **1014** gol nelle 303 partite di questa stagione» | **164** |
| `accuratezza.html` | tabelle di calibrazione e mercati: `5836`, `(4565/5836)`, `2494` | 1 |
| `accuratezza.html` | «Versioni del modello nel campione: dc-elo-tilt-0.4: **5836** gare» | 1 |

Correzioni: `it_num` su `bt.n`, `c.k/c.n`, `m.k/m.n`, `m.n`, `composizione.corrente/calibrate`,
`fg.n_goals`, `fg.n_matches`; separatore anche in `backtest.py` (`model_versions`, che arriva già
formattato nel template). Il gate ora legge **tutte** le pagine del sito e cerca anche «gol»:
prima della correzione avrebbe segnalato **165 pagine**, dopo **0**.

### 3.3 Tre conteggi che sopra 1.000 avrebbero fermato il daily

`lp.n` (partite previste per lega), `fg.n_matches` e `fg.n_first` erano stampati **senza**
`it_num` (`match.html:160`, `:170`, `:187`, `:196`). Misurato oggi: `lp.n` max **356**,
`fg.n_matches` **303** — sotto la soglia, quindi il gate non li vedeva; `fg.n_matches` conta le
partite della stagione e a fine campionato arriva a ~2.300, cioè **il daily si sarebbe fermato da
solo** con l'invariante `[14]`. Corretti (è il punto §7b di `docs/40`, chiuso).

### 3.4 L'ordine delle card «Percentili di lega» dipendeva dal processo

`players.py:594` costruiva un `set` di id e lo iterava: l'ordine cambia con l'hash seed.
**Riprodotto qui**, non citato: `PYTHONHASHSEED` 0/1/2 → tre sequenze diverse
(`recoveries,rating,xa,…` / `dribbles,passes,xa,…` / `chances,dribbles,passes,…`). Correzione:
`percentile_ids()` restituisce l'ordine **dichiarato** in `RADAR` + `PCT_EXTRA`; nessuna deduplica
persa (verificato: 0 id ripetuti in `RADAR` e 0 intersezioni con `PCT_EXTRA` su tutte e 4 le
posizioni). Test con 4 seed in 4 processi separati.

### 3.5 Il gate stesso si è rotto due volte, e va detto

Estendere `[14]` e aggiungere separatori ha **rotto il verificatore**, non il sito: le regex con
cui `verify_site` rilegge i numeri pubblicati cercavano solo cifre. Due sintomi reali, entrambi
presi dai gate locali prima di qualsiasi push:

1. `ValueError: could not convert string to float: '42.7% (2494/5836)'` nell'invariante `[7]`
   (intervalli di Wilson): la regex `\((\d+)/(\d+)\)` non riconosceva più «(2.494/5.836)» e la
   riga cadeva nel ramo «nessuna k/n pubblicata».
2. `accuratezza.html: card backtest senza numerosità o RPS`: `su <b>(\d+)</b> partite` non
   leggeva più «su **5.836** partite».

Correzione: helper `_int_it()` («2.494» → 2494) e regex rese tolleranti al separatore in `[3]`
(riga «Tutti»), `[3b]` (tabella riepilogo e composizione del campione) e `[7]`; `it_num` anche su
`r.n` del riepilogo. **Lezione registrata**: ogni numero che il sito pubblica formattato deve
essere riletto da un parser che accetta la formattazione, altrimenti il gate si rompe il giorno in
cui il numero cresce — esattamente il meccanismo che avrebbe fermato il daily da solo (§3.3).

### 3.6 Gate dopo le correzioni (stessi dati, stesso ambiente, build finale)

| gate | prima | dopo |
|---|---|---|
| `pytest -q` | 453 passed | **457 passed** (+4) |
| `ruff check .` | pulito | **pulito** |
| `fda build` | exit 0 · 375/2.364/7.492 | **exit 0 · 375/2.364/7.492** |
| `verify_site` | 0 problemi · 151.316 controlli | **0 problemi · 151.775 controlli** (`[37]` 459 didascalie; `[14]` su **4.137** pagine invece di 375) |
| `parita_schede` | exit 0 | **exit 0** (59 schede · 23 id · 12 voci) |
| `resa_375` | 23.658 misure · 0 problemi | **23.658 misure · 0 problemi** |
| `audit_match_sections` | exit 0 | **exit 0** |

Misure sul sito ricostruito: `index.html` → 7 card «in corso», 1 «finale», 23 «calcio d'inizio»;
hero di una gara in corso → «1–0 · in corso · calcio d'inizio 15:00»; `accuratezza.html` →
**0** numeri ≥ 1000 senza separatore (prima: 4 forme diverse); pagine che violano `[14]` esteso
→ **0** (prima della correzione: **165**).

### 3.7 GitHub ricollegato: i commit della sessione sono sul branch (secondo giro)

Nel primo giro il push era bloccato dal token scaduto (`gh auth status` → `authentication failed`,
`git push` → `could not read Username for 'https://github.com': terminal prompts are disabled`,
`gh api user` → `401 Bad credentials`) e il lavoro era stato consegnato in `handover/` secondo la
regola A8bis. Dopo l'intervento dell'utente: `gh auth status` → `✓ Logged in to github.com as
arena-ai-coding-agent[bot] (GH_TOKEN)`, `git push origin arena/01a0ba12-football-deep-analyzer` →
`fd03015..9bbc055`. La CI `tests` è verde su entrambi gli sha (`gh run list --branch
arena/01a0ba12-…`: run `35451417391` su `fd03015`, run `35453307792` su `9bbc055`). `handover/`
resta come copia di riserva.

### 3.8 Archiviazione di `docs/STATO.md` (regola A5, coda P2.5)

`docs/STATO.md` era a **118.900 byte** con **18** giri «Ultimo aggiornamento»: sopra la soglia di
~80 kB della regola A5, già dichiarata come punto aperto in `docs/40` §9.3. Fatto: i giri **30-45**
sono in `docs/STATO_archivio_2026-09-19.md` (**61.120 byte**, testo integro, senza riscritture), in
`STATO.md` restano gli ultimi 3 giri e il link — **61.422 byte**, sotto la soglia. Verifica riga
per riga contro il testo pubblicato su GitHub (`git show HEAD:docs/STATO.md`): **271** righe non
vuote originali, **270** presenti tra `STATO.md` e l'archivio; l'unica non coperta è la riga «Giri
archiviati (regola A5)», sostituita dalla versione col link nuovo. Le sei sezioni permanenti
(`## Fatto`, `## In corso`, `## Nota`, `## Prossimo passo`, `## Decisioni aperte`,
`## Direttive utente persistenti`) sono intatte.

*Nota di metodo:* la prima esecuzione dello script di archiviazione è caduta a metà
(`ValueError: not enough values to unpack`) **dopo** aver già riscritto `STATO.md`: il giro 45 era
uscito da `STATO.md` senza entrare nell'archivio. Recuperato da `git show HEAD:docs/STATO.md` e
reinserito; la verifica riga per riga qui sopra è il controllo che lo dimostra. Chi riscrive un
registro in più passi deve verificare il risultato prima di considerarlo chiuso.

### 3.9 Il test di render coi contatori a 1 (`docs/40` §8, coda P2.6)

`docs/40` §8 chiedeva «un test di render che costruisca le card con i contatori a 1 e verifichi la
formattazione (oggi il minimo osservato è `n=104` e la soglia dei mille non è mai stata
attraversata in produzione)». Nuovo file `tests/test_numeri_pubblicati.py`, 3 test:

* `int_it` come fonte unica della formattazione: 5836 → «5.836», 1000 → «1.000», 999 → «999»,
  356 → «356», 1 → «1», `57000.0` → «57.000» (nel parquet gli interi arrivano float), `None` →
  vuoto e non uno zero inventato;
* il render con **una sola gara valutata** (lo seed dei test di sito): «1 gara valutata» e non
  «1 gare», la riga di riepilogo «Tutti» espone la cardinalità `1`, la calibrazione resta un
  rapporto `(k/1)` leggibile, nessun numero a quattro cifre senza separatore;
* il morso del §3.5: `check_numbers` rilegge sia «2494/5836» sia «2.494/5.836» senza andare in
  `ValueError`.

`pytest tests/test_numeri_pubblicati.py -q` → **3 passed in 3.91s**.

---

## 4. Cosa resta da fare (coda verificata, in ordine di utilità)

**P1 — presidi che oggi non esistono**

1. ~~**Avviso quando il `daily` è rosso**~~ (§1.6) — **implementato e coperto da test** (sessione `arena/01a0bab0`: script `scripts/ci_alert.py` con subcomandi `on-failure` e `on-success`, 13 unit test in `tests/test_ci_alert.py`, permessi `issues: write` e passi in `.github/workflows/daily.yml`). Allerta automatica a costo zero: apre/commenta issue di guasto con diagnostica dai log in caso di rosso, e chiude in automatico la issue appena il run successivo torna verde.
2. ~~**Feed Sportmediaset 404** (§1.8)~~ — **diagnosticato e corretto il 19/09** (terzo giro) e **verificato in produzione** (sessione `arena/01a0bab0`: `daily` `35457599586` post-merge PR #62 → commit `f111b95`, `news:NEWS` = **AVVISO** con 4.052 righe, **0** righe ERRORE su 37).
   Misura su `news.parquet` (16.337 righe): Sportmediaset 205 notizie, **tutte** da Google News,
   **0** dal feed diretto; Sky Sport 392, tutte da Google News; ANSA 377, di cui 94 dal feed.
   Il feed morto **non costa una notizia**: il difetto vero era che la riga `news:NEWS` restava
   **ERRORE** a ogni run, dichiarando guasta una fonte che consegnava 3.938 righe e rendendo
   indistinguibile un guasto vero di Google News. Corretto in `collect.py` (`news direct` in
   `_WARN_NON_BLOCCANTE`; `as_status_rows` richiede che **tutti** gli errori della fase siano non
   bloccanti, prima decideva il primo) + 2 test. Dettagli in `docs/25` §5.2.
3. **Sonda dei fallback** (§1.7): primo run lunedì **21/09** 03:30 UTC. Da controllare che
   `source_probe.parquet` entri nel repository e che *Stato fonti* pubblichi la data al posto di
   «nessuna registrazione».
4. **`benchmark.yml`**: primo run **3/10**. Da controllare che produca `mercati_monitor` e che la
   pagina lo pubblichi.

**P2 — qualità e manutenzione**

5. ~~**Archiviazione di `STATO.md`**~~ — **fatta** (§3.8): 118.900 → **61.422 byte**, i giri 30-45
   in `docs/STATO_archivio_2026-09-19.md`, verifica riga per riga senza perdite.
6. ~~**Test di render coi contatori a 1**~~ (`docs/40` §8) — **fatto** (§3.9): nuovo
   `tests/test_numeri_pubblicati.py`, 3 test, 3 passed.
7. **Ritardo dei run schedulati** (§1.3, media 3,12 h): non è un difetto nostro ma di GitHub
   Actions. Se l'utente vuole più freschezza le opzioni sono più cron (costo: più run) o accettare
   il ritardo dichiarato in testa alla pagina. **Decisione dell'utente**, non dell'agente.

**Fuori perimetro, già deciso**: Lighthouse/accessibilità automatica (serve un browser), traduzione
del materiale straniero (decisione dell'utente, `docs/25` §7), quote dei bookmaker (`docs/38`).

---

## 5. Prossimo passo

1. Le correzioni di §3 sono committate e **pushate** sul branch `arena/01a0ba12-…` (`fd03015..9bbc055`,
   §3.7) con la CI `tests` verde. Quando l'utente dà il via, una sola PR (regola «PR ricca»,
   `docs/00` §D) contenente i difetti di §3.1-§3.6, l'archiviazione di §3.8 e il test di §3.9.
2. Subito dopo, in una PR propria perché verificabile solo dal vivo: **l'avviso sul `daily` rosso**
   (coda 1) e la decisione sul **feed Sportmediaset** (coda 2).
3. Lunedì 21/09: controllo della prima sonda dei fallback (coda 3).
