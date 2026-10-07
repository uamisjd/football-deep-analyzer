# 50 — Sito fermo da otto giorni, sei sezioni perse su 66 schede, costo delle fonti misurato

**Data:** 2026-10-05 · **Sessione:** `arena/01a10d2b-football-deep-analyzer` · **Richiesta utente:**
«controlla che il sito e tutto il progetto stiano funzionando correttamente; assicurati di non
usare troppi crediti nei siti o link che usiamo; vedi cosa manca o non funziona bene».

Tutto ciò che segue è **misurato in questa sessione** con comandi riportati: nessun numero è
ripreso da un documento precedente. Dove una cosa non è verificabile dal sandbox è scritto
esplicitamente (§7).

---

## 0. Verdetto in tre righe

1. **Il sito pubblico è fermo dal 28/09/2026** (**37 run `daily` rossi consecutivi**, dal
   28/09 10:45 UTC; ultimo verde 27/09 23:52 UTC): un **solo
   decimale scritto col punto** — le coordinate della sonda Open-Meteo, «45.48,9.12», pubblicate
   verbatim in *Stato fonti* — faceva uscire 1 il gate `verify_site`, che sta **prima** del commit
   dei dati e del deploy. Corretto (§1, §4).
2. **Difetto di contenuto indipendente e più grave:** in `match.html` la chiusura della card
   «Precedenti» stava 150 righe più in basso del dovuto, quindi **sei sezioni** (fra cui
   *Previsione del modello*) erano annidate dentro `{% if c.h2h_pattern or … %}`. Su **66 schede
   su 441** spariva il cuore della scheda e restavano **66 ancore morte**. Corretto (§2, §4).
3. **Costo delle fonti:** ~1.700 richieste/giorno (picco 6.095 il 15/09, giorni di backfill),
   tutte su fonti gratuite e senza chiave, entro i tetti dichiarati. L'unico spreco misurato è la
   **cache HTTP che non sopravvive fra un run e l'altro**: le TTL dichiarate in
   `config/sources.yaml` non si applicavano mai fra i 5 run giornalieri (§5). Corretto nel workflow.

Suite: **508 passed** (era 500). Gate: `verify_site` **0 problemi · 156.865 controlli**,
`parita_schede` exit 0, `resa_375` **0 problemi su 25.921 misure**, `ruff` = baseline.

---

## 1. Il sito è fermo dal 28/09: la causa, misurata

### 1.1 I fatti

```
$ gh run list --workflow daily.yml --limit 80   # estratto
completed  failure  daily  main  schedule  37302286386  15m27s  6h
completed  success  lab    main  schedule  37298466696   9m43s  7h
completed  failure  daily  main  schedule  37245969329  11m13s 17h
… 37 run `daily` consecutivi falliti (misurato su 80 run: il primo verde a ritroso è
   2026-09-27T23:52:01Z), tutti sul passo «Verifica il sito (verify_site)»
```

Il sito pubblicato (letto con un fetch della pagina reale):

```
CENTRO PARTITE · AGGIORNATO 28/09/2026 02:00
# Partite di oggi — lunedì 28 settembre 2026
```

Il dato più recente nel repository è la raccolta del **27/09 23:56 UTC**
(`max(source_status.run_at)`): da allora nessun run è più arrivato al passo «Commit dei dati».

### 1.2 La riga di log che lo spiega

I log di Actions non sono scaricabili dal sandbox (gli host
`results-receiver.actions.githubusercontent.com` e `*.blob.core.windows.net` non rispondono:
`curl` → `000`), ma l'URL firmato del log si ottiene da `gh api` e si legge lo stesso. Run
`37302286386`, passo *verify_site*:

```
PROBLEMI (1): {'decimale': 1}
  - stato.html: decimale col punto '45.48'
##[error]Process completed with exit code 1.
```

**Un problema solo.** Riprodotto in locale: build sui dati del repository e
`python scripts/verify_site.py --site site --data data/processed` → exit 1 con lo stesso unico
`decimale` (più le 132 voci del §2, che in CI non comparivano — vedi §2.4).

### 1.3 Da dove viene quel numero

`data/processed/source_probe.parquet` (la sonda settimanale delle fonti di fallback, `docs/19`
P1.10) conteneva:

```
2026-09-28 10:11:50+00:00  openmeteo  True  previsione per 45.48,9.12 alle 10:11 UTC: 22 °C, coperto · pioggia 0%
2026-10-05 10:53:49+00:00  openmeteo  True  previsione per 45.48,9.12 alle 10:53 UTC: 21 °C, parzialmente nuvoloso · pioggia 0%
```

Sono le coordinate di San Siro (`PROBE_LAT, PROBE_LON = 45.478, 9.124`) stampate con `:.2f` in
`scripts/probe_fonti.py`. La pagina *Stato fonti* pubblica quel testo **verbatim**
(`{{ p.detail }}` in `templates/status.html`), e il gate `verify_site` sui decimali
(`DECIMAL_POINT`, invariante [13-14]) lo intercetta giustamente: in italiano si scrive «45,48».

La catena completa:

```
lunedì 28/09, workflow `lab` → scripts/probe_fonti.py scrive «45.48,9.12» in source_probe.parquet
   → il commit del lab riesce (fix di docs/49, PR #77, mergiata il 21/09)
   → ogni `daily` successivo: build → stato.html pubblica la riga → verify_site exit 1
   → il run si ferma PRIMA di «Commit dei dati» e di «Prepara il sito per Pages»
   → sito congelato all'ultimo deploy buono, issue #79 aperta e commentata dal bot
```

### 1.4 Perché non è successo prima

Non è un caso che sia esploso il 28/09: **la prima riga di `source_probe` nel repository è del
28/09**. Fino al 21/09 il passo di commit del workflow `lab` era rotto
(`git add --ignore-missing` senza `--dry-run`, `docs/49` §3), quindi la sonda girava ma il suo
esito non arrivava in `main`. Il primo lunedì con il commit funzionante ha pubblicato la riga, e
dal run successivo il gate ha morso. Il difetto di formattazione era nel codice da quando la
sonda è stata scritta; mancava solo il vettore.

C'è anche un aggravante strutturale: la sonda gira **una volta alla settimana** e la riga resta
nel Parquet, quindi **un solo lunedì storto blocca sette daily**. Il produttore è stato corretto,
ma la pagina pubblica testo generato altrove e già salvato: serve anche una conversione
all'ultimo miglio (§4).

---

## 2. Sei sezioni annidate dentro «Precedenti» (66 schede su 441)

### 2.1 Il difetto

In `src/fda/site/templates/match.html`, la card «Precedenti» si apre con

```jinja
{% if c.h2h_pattern or c.h2h[0] is not none or c.h2h_list %}
```

e la sua `{% endif %}` **non** stava dopo il `</div>` della card: stava 150 righe più in basso,
dopo il blocco «Quando arriva il primo gol». Misurato sull'albero dei blocchi del template:

```
if «Precedenti» aperto a riga 449 -> chiuso a 613      ← prima
if «Precedenti» aperto a riga 449 -> chiuso a 464      ← dopo la correzione
```

Dentro quel `{% if %}` restavano quindi, annidate senza che nessuno lo volesse:

| id | sezione |
|---|---|
| `previsione` | **Previsione del modello** + Risultati esatti più probabili |
| `scomposizione` | Come nasce questa probabilità |
| `fascia-storica` | Quando il favorito aveva questa forza |
| `posizione-lega` | Dove si colloca questa partita |
| `primo-gol` | Quando arriva il primo gol |

L'indice della scheda, invece, linka `#previsione` con la sola guardia `{% if p %}`: su quelle
pagine l'indice prometteva una sezione che non c'era.

### 2.2 La misura

Build in locale sui dati del repository (27/09) eseguita il 05/10:

```
PROBLEMI (133): {'ancora': 66, 'decimale': 1, 'indice': 66}
  - partite/5749690.html: ancora interna mancante #previsione
  - partite/5781764.html: ancora interna mancante #previsione
  … 66 schede
```

Le 66 schede sono **tutte le partite del 9-11 ottobre** (7 campionati). Confronto delle
intestazioni di `partite/5749690.html` (Atalanta-Venezia) prima e dopo la correzione:

```
PRIMA:  … Arbitro e meteo → Verifica approfondita            (mancano 6 sezioni)
DOPO:   … Arbitro e meteo → Previsione del modello → Risultati esatti più probabili
        → Come nasce questa probabilità → Quando il favorito aveva questa forza
        → Dove si colloca questa partita → Quando arriva il primo gol → …
```

`parita_schede.py` sulle 66 schede pre-partita dopo la correzione:
«struttura identica (23 id) · indice: uguale in tutte · 13 voci».

### 2.3 Quando si manifesta (e perché il `daily` non l'aveva mai visto)

I precedenti (`_h2h_core` in `analysis.py`) si leggono **solo** da `h2h.parquet`, che è popolato
dai dettagli FotMob di **quella** partita: niente dettagli raccolti → niente precedenti → le sei
sezioni sparivano. I dettagli si raccolgono nella finestra `[oggi−3, oggi+7]`
(`DETAIL_WINDOW_DAYS = 7`), mentre le schede esistono fino a +7 giorni e il calendario compatto
arriva a 30: finché la raccolta è fresca, ogni partita con la scheda è passata dalla finestra e
ha i suoi precedenti. Il difetto resta latente.

Si manifesta quando una partita con la scheda **non** ha precedenti, e succede in due modi:

* **dati fermi** (il caso di oggi: raccolta al 27/09, build il 05/10 → le gare del 9-11/10 non
  erano ancora entrate nella finestra quando la raccolta si è fermata);
* **primo incontro** fra due squadre nell'archivio disponibile — un caso legittimo e permanente,
  che avrebbe tolto la previsione proprio alle partite più incerte.

### 2.4 Origine

Confronto del template alle varie revisioni (file scaricato via API per ogni commit che lo
tocca):

```
4dc48a82 (19/09)  if «Precedenti» 537 -> chiuso a 551   ← corretto
64998455 (20/09)  if «Precedenti» 450 -> chiuso a 614   ← qui entra il difetto
3f64f6f7 (20/09)  if «Precedenti» 449 -> chiuso a 613   ← sopravvive al revert della PR #73
```

Introdotto da `64998455` («quality: absences λ… + hero_form fix + backtest restore 2152»),
sopravvissuto al revert dei tilt nella PR #73. In CI non ha mai morso perché — come detto — con
la raccolta fresca non esiste una scheda senza precedenti: è servito il blocco del §1 (dati
fermi) per renderlo visibile.

---

## 3. Difetto latente trovato lungo la strada: il link «salta a <mese>»

`index.html` offre «salta a *venerdì 9 ottobre 2026*» verso `prossime.html#mese-2026-10`. Le
ancore `id="mese-…"` esistono però **solo** per i mesi presenti nel calendario compatto, che
copre `CALENDAR_DAYS = 30` giorni oltre la finestra breve. Se la prossima gara è più lontana
della finestra — **sosta estiva**, sette-otto settimane — quel mese non è nel calendario, il link
punta a un id assente e il gate delle ancore interne ferma il run: lo stesso meccanismo del §1,
in attesa della prossima estate.

Trovato sul seed dei test (calendario vuoto): `index.html: ancora interna mancante
prossime.html#mese-2026-10`. Corretto passando dal build l'id verificato (§4).

---

## 4. Le correzioni

| # | File | Correzione |
|---|---|---|
| 1 | `scripts/probe_fonti.py` | coordinate con `fmt.dec` → «45,48 N / 9,12 E» (virgola italiana, emisfero dichiarato) |
| 2 | `src/fda/site/fmt.py` | nuova `decimali_it()`: converte i decimali col punto **dentro una stringa libera**; stessa identica espressione di `verify_site.DECIMAL_POINT` |
| 3 | `src/fda/site/build.py` | `build_status` passa da `decimali_it()` i testi pubblicati verbatim (`detail`, `error`, `detail` della sonda): la pagina non dipende più da come il testo è stato scritto a monte |
| 4 | `src/fda/site/templates/match.html` | `{% endif %}` di «Precedenti» riportato alla fine della sua card (riga 464) e tolta la chiusura vagante a riga 613 |
| 5 | `src/fda/site/build.py` + `templates/index.html` | `next_info["anchor"]` = l'id del mese **solo se** quel mese è nel calendario; i due link «salta a …» escono solo con l'ancora verificata |
| 6 | `data/processed/source_probe.parquet` | le due righe già salvate riscritte nel formato nuovo: la sonda gira il lunedì, senza questo la pagina avrebbe pubblicato «45,48,9.12» per una settimana |
| 7 | `.github/workflows/daily.yml` | cache HTTP persistente fra i run (§5) |

Il punto 6 è l'unica modifica a un dato versionato: è una correzione di **formato** di un testo di
diagnostica (stesso contenuto, virgola italiana), riproducibile, e la sonda di lunedì 12/10
sovrascrive la riga da sola (chiave `run_at + probe`).

### 4.1 Dopo le correzioni (misure di questa sessione)

```
$ python -m pytest -q                                   → 508 passed
$ fda build                                             → exit 0 · 441 schede / 2.364 partite / 7.158 giocatori
$ python scripts/verify_site.py --site site --data data/processed
                                                        → exit 0 · nessun problema · 156.865 controlli
$ python scripts/parita_schede.py site                  → exit 0 · 66 schede, struttura identica (23 id), indice 13 voci
$ python -m scripts.resa_375                            → exit 0 · 25.921 misure · 0 problemi
$ ruff check <file toccati>                             → 1 segnalazione = baseline preesistente (S112, già su HEAD)
```

### 4.2 Test aggiunti (8) e prova di morso

| Test | Cosa presidia |
|---|---|
| `test_fmt.py::test_decimali_it_converte_solo_i_decimali` | la conversione |
| `test_fmt.py::test_decimali_it_non_tocca_migliaia_versioni_url` | 8 falsi positivi da non creare («84.594», «v1.5», «Chrome/124.0», URL, orari) |
| `test_fmt.py::test_decimali_it_allineata_al_gate_di_verify_site` | le due espressioni restano identiche |
| `test_probe_fonti.py::test_sonda_ok_non_pubblica_decimali_col_punto` | il dettaglio della sonda, sui tre esiti (ok / errore / risposta vuota) |
| `test_site.py::test_previsione_pubblicata_anche_senza_precedenti` | end-to-end: scheda senza H2H → previsione presente, zero ancore morte |
| `test_site.py::test_stato_fonti_pubblica_decimali_italiani_nei_testi_liberi` | end-to-end su `build_status` con Parquet avvelenati |
| `test_site.py::test_salto_al_mese_solo_se_il_mese_e_nel_calendario` | calendario vuoto → nessun link |
| `test_site.py::test_salto_al_mese_presente_quando_il_mese_e_nel_calendario` | caso positivo: l'ancora c'è ed è quella giusta |

**Prova di morso** (ogni fix è stato annullato e il test rieseguito):

* template riportato al difetto → `test_previsione_pubblicata_anche_senza_precedenti` **fallisce**
  su `assert 'id="previsione"' in …`; ripristinato → passa;
* link «salta a …» riportato alla forma vecchia → `test_salto_al_mese_solo_se…` **fallisce**;
  ripristinato → passa.

Aggiornato anche `test_probe_fonti.py::test_sonda_ok_registra_il_valore_vero`, che **asseriva il
formato sbagliato** (`assert "45.48,9.12" in esito["detail"]`): è il motivo per cui il difetto è
passato dai test.

---

## 5. Costo delle fonti: misurato, non dichiarato

### 5.1 Quanto consuma il progetto oggi

Da `source_status.parquet` (4.596 righe, 05/09 → 27/09, 5 run/giorno):

```
richieste/giorno, media sugli ultimi 8 giorni disponibili:
  news:NEWS                692   → Google News (132 feed squadra) + ESPN news + feed diretti
  transfers:TRANSFERS      676   → FotMob `teams`, 132 squadre × 5 run
  fotmob:<lega> × 7        294   → ~42/lega/giorno (calendario, classifica, dettagli, meteo)
  fotmob:CUPS               10
  understat:*               30
  espn:* + espn scoreboard  15   → quasi tutte sonde di riattivazione: le fasi sono SOSPESO
  openmeteo                  0   → FotMob copre il meteo; la sonda è 1 richiesta/settimana
  ─────────────────────────────
  TOTALE                ~1.700/giorno
```

Media sull'intero periodo 2.703/giorno; **picco 6.095 richieste il 15/09** e sei giorni sopra
4.000 (9, 13, 14, 15, 16, 18/09): sono i giorni del backfill di stagione, una tantum.

Per host: **www.fotmob.com ~980/giorno** (calendario + dettagli + mercato), **news.google.com
~600**, understat.com ~30, site.api.espn.com ~15, api.open-meteo.com ~0,
raw.githubusercontent.com solo per lo storico (mirror datahub).

### 5.2 Siamo entro i tetti dichiarati?

Sì, con margine. `config/sources.yaml` dichiara `max_requests_per_run: 600` per FotMob
(misurato: ~200/run, di cui 132 per il mercato) e `200` per le notizie (misurato 135). Il tetto è
applicato davvero (`HttpClient.max_requests` → `SourceError` «budget richieste esaurito»). Le
pause fra richieste sono rispettate (1 s FotMob/notizie, 2 s Understat, 0,5 s ESPN).

### 5.3 Lo spreco misurato: la cache non sopravviveva fra i run

`data/cache/` non è versionato (`.gitignore`) e il checkout di Actions riparte da una cartella
vuota (nel log del run: `Deleting the contents of '/home/runner/work/…'`). Quindi le TTL scritte
in `config/sources.yaml` valevano **solo dentro un run**:

| fonte | TTL dichiarata | intenzione dichiarata | realtà misurata |
|---|---|---|---|
| `transfers` (FotMob `teams`) | 24 h | 132 richieste/giorno | **676/giorno** (5×) |
| `news` | 12 h | «solo ~2 fetch reali per squadra al giorno» (≈264) | **692/giorno** |
| `fixtures` FotMob | 6 h | ~2 volte/giorno/lega | a ogni run |

Correzione: due passi in `daily.yml` con `actions/cache/restore@v6` e `actions/cache/save@v6` su
`data/cache` (chiave nuova a ogni run, `restore-keys` sul prefisso, GitHub fa l'LRU da solo). Con
la cache persistente è la TTL a decidere quante volte si scarica: a regime il mercato passa da
676 a ~132 richieste/giorno e le notizie da 692 a ~264, cioè **circa un terzo delle richieste
totali in meno** (~1.700 → ~1.100/giorno) senza togliere un dato al sito.

**Sicurezza:** entrambi i passi hanno `continue-on-error: true`, e il salvataggio gira solo se il
ripristino è riuscito. Un problema di cache (quota, restore) non può fermare il run: la raccolta
funziona identica, solo con più richieste. Il passo di salvataggio sta dopo `fda daily` (le fasi
successive non fanno richieste) e ha `if: always()`, quindi la cache si salva anche se la
raccolta cade a metà.

Nota di costo: la cache contiene anche i payload delle partite finite (TTL 10 anni, per scelta:
`matchDetails_finished: 87600`), quindi cresce durante la stagione. Non è misurabile da qui
(§7): se nei prossimi run il salvataggio dovesse superare qualche centinaio di MB, la leva è
abbassare quella TTL — il backfill non ne dipende, perché «già scaricata» è deciso dallo store
(`already`), non dalla cache HTTP.

### 5.4 Le altre voci di costo

* `lab` (lunedì): 1 richiesta vera/settimana (la sonda) + lavoro offline sullo storico.
* `benchmark-quote` (il 3 del mese): qualche CSV dal mirror datahub.
* Il backoff (`src/fda/backoff.py`) funziona e fa risparmiare: le fasi ESPN in 403 cronico sono
  SOSPESO e **non** vengono interrogate; ogni 4 run una sonda le riattiva da sole. Misurato: le
  righe `espn:*` sono ~1 richiesta/giorno invece delle 14/run (70/giorno) di prima del backoff.

---

## 6. Cosa manca / cosa resta da fare

1. **Far ripartire il `daily`.** Le correzioni sono su questo ramo: il sito torna aggiornato solo
   quando entrano in `main` (il primo run verde chiude da solo la issue #79). Fino ad allora il
   sito pubblico resta al 28/09.
2. **Un gate che dica «il sito è vecchio».** Oggi l'unico segnale di un sito congelato è la issue
   del bot: niente, nel sito o nei gate, dice «questi dati hanno 8 giorni». Un'invariante di
   freschezza (età dell'ultimo run pubblicata e verificata) avrebbe reso il blocco evidente il
   primo giorno. **Non implementato in questa sessione** — proposta.
3. **Un difetto di formato non deve congelare il sito.** La catena è: gate cosmetico → exit 1 →
   niente commit dati → niente deploy. È una scelta documentata (P0.8), ma un'alternativa da
   valutare è separare i gate *bloccanti* (numeri sbagliati) da quelli *estetici* (formato),
   pubblicando comunque i dati con un avviso. **Non implementato** — decisione per l'utente.
4. `docs/42` §4 resta valido: `prossime.html` 1.240 kB su un tetto di 1.800 (P2.7), sotto soglia.

## 7. Cosa **non** ho potuto verificare da qui (dichiarato, non taciuto)

* **La rete del sandbox è limitata a `api.github.com` e PyPI**: `curl` verso fotmob.com,
  understat.com, espn, open-meteo, news.google.com, raw.githubusercontent.com e
  uamisjd.github.io restituisce `000`. Quindi:
  * **`collect` non è stato eseguito** (nessuna richiesta alle fonti è stata fatta in questa
    sessione, se non i fetch di pagine e log via API/proxy): la catena è stata verificata da
    `calibrate` in poi;
  * il sito pubblicato è stato letto **una volta sola** (fetch della home) per datare il blocco;
  * i log di Actions sono stati letti dall'URL firmato, non scaricati.
* **`simulate`** non è stato completato in locale: scarica lo storico dal mirror datahub, host non
  raggiungibile da qui. Nel primo tentativo (interrotto da un timeout del tool a 30 minuti) ha
  scritto `season_sim.parquet`, ma non ho la conferma di un'esecuzione completa. In CI il passo è
  verde nel run di oggi.
* `backtest` e `mercati-monitor` sono stati eseguiti **con campione ridotto** (`seasons_back=1`,
  `step_days=30`) per restare nei tempi: exit 0.
* La cache HTTP del §5 si esercita solo in Actions: qui è verificata la sintassi dei workflow
  (tutti e 6 parsano) e la logica dei passi, non un run reale.
