# 40 — Concordanza con 1: «1 assente», «1 gara», «1 giorno» (19/09/2026)

> **Il `daily` su `main` è rosso due volte di seguito e il deploy è fermo.** I run
> `35432745402` (schedulato) e `35438804509` (push del merge di PR #58) si sono fermati
> entrambi sullo stesso passo — «Verifica il sito (verify_site)» — con lo stesso messaggio:
> `partite/5749682.html: concordanza '1 assenti'`. Il gate sta **prima** del passo «Commit dei
> dati aggiornati» e **prima** di «Prepara il sito per Pages»: quindi i dati raccolti in quei
> due run non sono stati committati e il sito pubblicato è rimasto alla build precedente.
> Correzione hotfix: **sei punti** nei generatori di testo (§1) più **otto punti** trovati
> chiudendo la classe sui template con un grep (§2), due test nuovi, un test del gate
> esteso, e **nessuna parola cambiata** nelle pagine di oggi (misurato, §5).
> Sessione `arena/01a0b97c`, branch `arena/01a0b97c-football-deep-analyzer`, base `41c9c89`.

---

## 1. I sei punti

Tutti e sei sono la stessa cosa: un contatore interpolato in una frase senza
:func:`fda.site.fmt.it_plural`, l'helper che il progetto usa dal 12/09/2026 (audit: «1 gare»
su 1098 pagine) proprio perché il singolare va concordato. `it_plural(n, 'gara')` stampa
`1 gara` e `33 gare`; senza, la f-string stampa il nome al plurale qualunque sia `n`.

| # | dove | la frase **prima** (misurata) | la frase **dopo** | quando il contatore vale 1 |
|---|---|---|---|---|
| 1 | `analysis.py:1453` — `club_mood`, riga «infermeria pesante» | `infermeria pesante: 1 assenti, di cui 1 titolare abituale, ≈ 0,9 xG+xA a partita in meno` | `infermeria pesante: 1 assente, di cui 1 titolare abituale, …` | **è il caso del gate**: la soglia della riga non è il numero di assenti (§3) |
| 2 | `analysis.py:2594` — `season_compare`, riga «Punti» | `3 in 1 gare` | `3 in 1 gara` | prima giornata di campionato: `played` = 1 |
| 3 | `analysis.py:3891` — `narrative`, frase sul riposo | `Inter gioca dopo soli 1 giorni di riposo.` | `Inter gioca dopo un solo giorno di riposo.` | due gare a 24 h di distanza (la soglia del segnale è ≤ 3 giorni) |
| 4 | `advanced.py:518-526` — `style_rows._xg_help`, tooltip «xG / gara» | `Gol attesi, media stagionale FotMob su 1 gare` | `… media stagionale FotMob su 1 gara` | `played` = 1 (prima giornata, o neopromossa con un solo turno raccolto) |
| 5 | `advanced.py:541-546` — `style_rows._quota_help`, tooltip delle quote xG | `(FotMob, 1 gare finite)` | `(FotMob, 1 gara finita)` | `split_played` = 1, lo stesso campione del punto 4 |
| 6 | `match.html:348` e `:359` — card della squadra | `(FotMob, 1 gare)` e `1 gare · n.d.` | `(FotMob, 1 gara)` e `1 gara · n.d.` | **la stessa variabile dei punti 4-5**: `season_xg` non ha una soglia minima su `played` |

Tre note di forma, tutte deliberate:

- **punto 3**: non basta concordare il sostantivo. «dopo **soli** 1 giorno» resta sbagliato
  perché l'aggettivo è plurale: la forma corretta è «dopo **un solo giorno** di riposo». Con
  2 o 3 giorni la frase è **identica a prima** («dopo soli 3 giorni di riposo»).
- **punti 4 e 5**: il valore può essere il trattino «—» (dato mancante), non un numero. Per
  questo `advanced.py` non chiama `it_plural` direttamente ma un helper locale,
  `_n_gare(v, singolare, plurale)`, che lascia passare il trattino tale e quale — seguito dal
  plurale, come stampava prima: `— gare`. Il punto 5 concorda anche l'aggettivo
  (`gara finita` / `gare finite`), che `it_plural` da solo non avrebbe toccato.
- **punto 6**: nel template il filtro è già registrato e già usato otto volte
  (`|it_plural('punto','punti')}`, `|it_plural('assente')}`, …): la correzione è
  `{{ xg.played|it_plural('gara') }}`, che con `played` ≥ 2 stampa esattamente ciò che
  stampava prima.

## 2. La classe chiusa anche sui template: altri otto punti

Direttiva applicata: *se il grep trova altri conteggi «dai dati e senza guardia», si
correggono ora*. Censimento completo di `src/fda/site/templates/*.html`: ogni
`{{ espressione }}` seguita da un sostantivo plurale della lista `AGREEMENT` di
`verify_site` (che è il perimetro del gate), classificato in §4 (misura) e §6 (guardie).

| # | dove | prima | dopo | minimo osservato oggi |
|---|---|---|---|---|
| 7 | `_matchlist.html:4` — `aria-label` della forma nelle card *Oggi*/*Prossime*/*Risultati* | `nelle ultime {{ form.n }} partite` | `nelle ultime {{ form.n\|it_plural('partita') }}` | **2** — il più vicino a scattare: la guardia è `{% if form and form.n %}`, non `n >= 3` |
| 8 | `_matchlist.html:66` — `title` del piede «Modello» | `significa {{ …\|round\|int }} partite su 100 con 3 o più gol` | `…\|round\|int\|it_plural('partita') }} su 100 …` | 5 (2.616 occorrenze della formula «N partite su 100») |
| 9 | `_matchlist.html:94` — `title` della cella Over 2,5 | `= {{ p.over }} partite su 100 con 3+ gol` | `= {{ p.over\|it_plural('partita') }} su 100 con 3+ gol` | 5 |
| 10 | `match.html:399` — nota della distinta | `La fonte elenca {{ stt\|length }} titolari` | `… {{ stt\|length\|it_plural('titolare') }}` | 10 (1 sola pagina oggi: la guardia è `!= 11`, quindi vale anche 1) |
| 11 | `match.html:532` — riga «Arbitro» | `({{ c.referee.matches\|int }} gare)` | `({{ c.referee.matches\|int\|it_plural('gara') }})` | **6** — `MIN_REFEREE_MATCHES = 15` protegge il *giudizio* nella narrativa, non questo conteggio |
| 12 | `match.html:601` — tabella dei dati fisici | `({{ f.players }} giocatori)` | `({{ f.players\|it_plural('giocatore') }})` | 13 |
| 13 | `accuracy.html:18` — composizione del campione | `{{ composizione.n }} gare valutate` | `{{ composizione.n\|it_num }} {{ 'gara valutata' if … == 1 else 'gare valutate' }}` | 104 |
| 14 | `accuracy.html:114` — nota sull'intervallo di Wilson | `osservata su <b>{{ calib[0].n }}</b> gare` | `… su <b>{{ …\|it_num }}</b> {{ 'gara' if … == 1 else 'gare' }}` | 104 — lo **stesso** campione del punto 13, stampato un'altra volta nella stessa pagina |

I punti 13 e 14 usano il condizionale invece di `it_plural` per **due** ragioni: concorda anche
l'aggettivo (`valutata`/`valutate`) e conserva il separatore delle migliaia, che qui serve —
il campione valutato cresce con l'archivio e `it_plural` stamperebbe `1234 gare valutate`
(invece di `1.234`). È la forma già usata in `match.html:498`
(`'titolo esaminato' if nw.esaminate == 1 else 'titoli esaminati'`).

I punti 8 e 9 sono un caso limite teorico (servirebbe un Over 2,5 all'1%, cioè λ totali
sotto 0,6): corretti perché costano una riga e non cambiano nulla oggi, non perché siano
probabili.

## 3. Perché il gate è rosso oggi e non lo era ieri

La riga «infermeria pesante» della card *Clima del club* scatta su **tre** soglie alternative
(`analysis.py`, costanti dichiarate nella nota della card):

```python
MOOD_ABSENT_N = 4           # assenti → infermeria pesante
MOOD_ABSENT_STARTERS = 2    # titolari abituali fuori
MOOD_ABSENT_CONTRIB = 0.5   # xG+xA/gara portati via dagli assenti
```

Il numero di assenti **non è** la soglia che fa scattare la riga: basta un solo
indisponibile che da solo porti via ≥ 0,5 xG+xA a gara — un titolare decisivo — perché la
frase venga pubblicata (`starters_out` è contato *dentro* gli `n` assenti, quindi con `n = 1`
la soglia che scatta è quella sul contributo). E la frase cominciava col contatore al plurale
fisso. Fino al 18/09 quel caso non era passato dai dati raccolti; nel run del 19/09 sì, su
una partita precisa (`5749682`), e il gate l'ha fermato. **Il gate ha funzionato come
progettato**: la lista dei sostantivi di `AGREEMENT` contiene `assenti` e il controllo gira
su ogni pagina e sugli attributi pronunciati dai lettori di schermo (`docs/27` §4.1);
mancava il prodotto, non il presidio.

Gli altri tredici punti **non** sono ancora passati dai dati (§4): sono della stessa classe e
sarebbero stati fermati allo stesso modo, il primo giorno in cui un contatore vale 1.

## 4. La misura: dove stanno oggi quei contatori

Conteggi sulle **4.131 pagine** della build locale fatta con i dati versionati su `main`
(che non sono quelli dei due run rossi: quei run si sono fermati prima del commit dei dati).
Nessuna delle forme sbagliate compare oggi — `verify_site` dà 0 problemi — quindi la prova
che la correzione funziona non può essere «rigiro il sito e guardo»: deve essere (a) la
chiamata diretta col contatore a 1 e (b) la prova che col contatore ≥ 2 **non cambia una
parola** (§5).

I sei punti (§1), frase per frase:

| frase pubblicata | occorrenze | valore **minimo** osservato | può valere 1? |
|---|---|---|---|
| `infermeria pesante: N assenti` | 68 | **2** | sì — soglia sul contributo, non su `N` (punto 1) |
| `M in N gare` (confronto di stagione) | 750 | **3** | sì — `played` ≥ 1 per costruzione (punto 2) |
| `gioca dopo soli N giorni di riposo` | 78 | **2** | sì — la soglia è ≤ 3 (punto 3) |
| `media stagionale … su N gare` | 750 | **3** | sì — prima giornata (punto 4) |
| `(FotMob, N gare finite)` | 1.500 | **3** | sì — stesso campione (punto 5) |
| `(FotMob, N gare)` / `N gare ·` nella card squadra | 750 + 750 | **3** | sì — la stessa variabile (punto 6) |

I sette punti dei template (§2):

| frase pubblicata | occorrenze | minimo | nota |
|---|---|---|---|
| `nelle ultime N partite` (`aria-label` della forma) | 503 | **2** | il più vicino a scattare (punto 7) |
| `N partite su 100` (Over 2,5 e code) | 2.616 | 5 | punti 8-9; le altre occorrenze sono `dec(1)` → la virgola le protegge (§6) |
| `La fonte elenca N titolari` | 1 | 10 | punto 10 |
| `(N gare)` nella riga dell'arbitro | 328 | **6** | punto 11 |
| `(N giocatori)` nei dati fisici | 82 | 13 | punto 12 |
| `N gare valutate` (composizione del campione) | 1 | 104 | punto 13 |
| `osservata su N gare` (intervallo di Wilson) | 1 | 104 | punto 14 |

### 4.1 Prova di morso (prima di correggere, come da prassi — `docs/27` §4.3)

I due test nuovi sono stati eseguiti sul codice **non corretto** (fix sotto `git stash`):

```
FAILED tests/test_panchina_notizie.py::test_concordanza_uno_assente_giorno_gara
E  AssertionError: (1, ['crisi di risultati: 3 sconfitte consecutive',
     'infermeria pesante: 1 assenti, di cui 1 titolare abituale, ≈ 0,9 ...a in meno,
      ≈ 35 M€ di mercato ai box', 'riposo corto: 2 giorni',
     'congestione: 5 gare giocate negli ultimi 10 giorni'])
FAILED tests/test_advanced.py::test_style_rows_concordanza_una_sola_gara
E  ImportError: cannot import name '_n_gare' from 'fda.site.advanced'
```

Le sei frasi, misurate chiamando le funzioni con il contatore a 1 (prima → dopo):

| # | prima | dopo |
|---|---|---|
| 1 | `infermeria pesante: 1 assenti, di cui 1 titolare abituale, ≈ 0,9 xG+xA a partita in meno` | `infermeria pesante: 1 assente, di cui 1 titolare abituale, ≈ 0,9 xG+xA a partita in meno` |
| 2 | `{'label': 'Punti', 'h': '3 in 1 gare', 'a': '5 in 4 gare'}` | `{'label': 'Punti', 'h': '3 in 1 gara', 'a': '5 in 4 gare'}` |
| 3 | `Inter gioca dopo soli 1 giorni di riposo.` | `Inter gioca dopo un solo giorno di riposo.` |
| 4 | `Gol attesi, media stagionale FotMob su 1 gare` | `Gol attesi, media stagionale FotMob su 1 gara` |
| 5 | `(FotMob, 1 gare finite)` | `(FotMob, 1 gara finita)` |
| 6 | `(FotMob, 1 gare)` nella card della squadra | `(FotMob, 1 gara)` — stesso `played` del punto 4 |

E con il contatore ≥ 2 l'uscita è **identica** a prima, carattere per carattere:
`soli 3 giorni di riposo`, `5 in 4 gare`, `su 5 gare`, `(FotMob, 5 gare finite)`,
`nelle ultime 5 partite`, `(FotMob, 4 gare)`.

## 5. Il sito di oggi non cambia di una parola

Build completa prima e dopo la correzione, **stesso codice a parte il fix, stessi dati**
(`41c9c89` + dati versionati), pagine confrontate al netto dei due timestamp di build
(`aggiornato gg/mm/aaaa hh:mm` e `Pagina generata automaticamente il …`):

| blocco | pagine diverse |
|---|---|
| `partite/` (punti 1-6, 10-12) | **0 / 375** |
| radice (`index`, `oggi`, `prossime`, `risultati`, `accuratezza`, `info`, `stato`, `404`) — punti 7-9 e 13 | **0 / 8** |
| `giocatori/` | 2.074 / 3.748 — **non attribuibili al fix**: vedi §5.1 |

### 5.1 Un difetto preesistente misurato per caso (non toccato qui)

Le 2.074 schede giocatore diverse **non** dipendono da questa correzione: lo stesso codice,
costruito **due volte di seguito**, produce la stessa differenza sullo stesso numero di
pagine (controllo eseguito: 2.074 / 3.748 anche fra le due build del codice corretto, mentre
`partite/` resta 0 / 375 in entrambi i confronti).

La causa è una riga di `players.py:594`:

```python
radar_ids = {sid for sid, _ in RADAR.get(pos_int, [])}     # insieme: ordine non deterministico
for sid in list(radar_ids) + PCT_EXTRA.get(pos_int, []):   # l'ordine cambia a ogni processo
```

L'ordine delle card «Percentili di lega» dipende dall'ordine di iterazione di un `set` di
stringhe, che cambia con l'hash seed del processo. Il contenuto è lo stesso, cambia la
sequenza. La correzione è una riga (`[sid for sid, _ in RADAR.get(pos_int, [])]`, che tiene
l'ordine dichiarato in `RADAR`), ma **non è di questo hotfix**: qui si sblocca il daily, e un
diff che tocca 2.074 pagine ne nasconderebbe quattordici. Resta come punto aperto (§8).

> **Chiuso il 2026-09-19** (sessione `arena/01a0ba12`, [`docs/41`](41_verifica_autoaggiornamento_e_coda_2026-09-19.md)
> §3.4): la riga è diventata `percentile_ids()` in `players.py`, l'ordine è quello dichiarato in
> `RADAR` + `PCT_EXTRA` e un test lo esegue in quattro processi con `PYTHONHASHSEED` 0/1/2/7
> pretendendo un'unica sequenza (prima: tre sequenze diverse su tre seed, riprodotto).

## 6. Esaminati e **non** toccati, con la guardia che li protegge

Censimento completo dei contatori interpolati nei generatori di testo (`src/fda/site/*.py`)
e nei template. Per ognuno: perché il contatore non può valere 1, o perché la correzione
peggiorerebbe le cose.

**Protetti da una soglia nel codice che li produce**

| dove | frase | guardia |
|---|---|---|
| `match.html:8` — `hero_form` | `nelle ultime {{ f.n }} partite` | `{% if f and f.n >= 3 %}`: il badge in testa alla scheda compare da 3 gare giocate (P2.5, `docs/37`). Lo stesso testo **senza** guardia sta in `_matchlist.html:4` → punto 7 |
| `giocatore.html:60` e `:91` | `N giocatori del campionato` / `N pari-ruolo con dato` | `MIN_PEERS = 8`: `players.py:379` azzera i percentili sotto 8 pari-ruolo, quindi il conteggio pubblicato è ≥ 8 (minimo osservato 19) |
| `analysis.py:1417`, `:1421`, `:1424`, `:1426`, `:1482` | sconfitte consecutive, «non vince da», imbattuta, attacco a secco, congestione | ognuna è pubblicata solo sopra la propria soglia (3, 4, 5, 3, 3) |
| `analysis.py:1271`, `:1283`, `:1297` | punti/gara dell'allenatore, bilancio contro l'avversaria, scontro diretto fra allenatori | già concordato (`1271` stampa «1,0 punti/gara su 1 gara finita») o protetto da `len(vs) >= 3` / `len(hv) >= 2` |
| `analysis.py:1471` e `:1095` | «riposo corto», giorni di riposo nel prossimo impegno | già concordati con un condizionale |
| `status.html:16` | `sonda ferma da N giorni` | `{% if p.days > 14 %}` |
| `match.html:532` (giudizio) | «molto severo» / media gialli | `MIN_REFEREE_MATCHES = 15` — ma protegge il giudizio, non il conteggio: per quello vedi il punto 11 |

**Costanti o configurazione, non dati**

| dove | frase | perché |
|---|---|---|
| `advanced.py:263` e `:267` | `ultimi 730 giorni`, `4.743 gare fuori campione` | la finestra è `FIT_WINDOW_DAYS` (costante del calibratore), `n_fit` è la numerosità del backtest (misurato: 4.743 / 4.760 / 5.812). `it_plural` **toglierebbe** il separatore delle migliaia (`4.743` → `4743`): peggiorerebbe la formattazione. Se un giorno la finestra diventasse piccola, la forma giusta è un condizionale che conserva `_int_it` |
| `info.html:14` | `{{ cal.window_days }} giorni`, `{{ cal.n_fit\|it_num }} gare` | stesse due grandezze del rigo sopra |
| `accuracy.html:54` | `in {{ bt.leagues }} campionati` | viene dalla configurazione (7 leghe): raggiungibile solo cambiando la config, non per deriva dei dati |
| `index.html:61` | `Altre {{ cal_total\|it_num }} partite … dopo i primi {{ calendar_days }} giorni` | `calendar_days` è `DETAIL_WINDOW_DAYS` (costante, come in `build.py:436-439`); `cal_total` è l'intero calendario (1.988) ed è già con `it_num` |
| `match.html:834-847` | `su 100 partite`, `{{ gv.n_dots }} punti`, `{{ gv.per_dot }} partite` | `n_dots = 20` e `per_dot = round(100/20) = 5` (`advanced.py:159-160`), `100` è letterale |
| `match.html:495-505` | `negli ultimi {{ nw.finestra }} giorni` | `NEWS_WINDOW_DAYS = 7` |
| `giocatore.html:61`/`:65`/`:127`, `giocatori_hub.html:7` | `N minuti` | è la soglia `min_minutes` (450), non un conteggio di gare — e «minuti» non è nella lista del gate |
| `match.html:428` | `{{ b.coach_age }} anni` | età di un allenatore in carica |

**Già concordati nel template** (nessun intervento): `match.html:327`
(`'giocatore in classifica' if kp.eligible == 1 else 'giocatori in classifica'`),
`match.html:498` (`'titolo esaminato' if nw.esaminate == 1 else …`), `match.html:548`
(`'Nel precedente mostrato' if c.h2h_stats.n == 1 else 'Nei N precedenti mostrati'`),
`_matchlist.html:74` (`|it_plural('assente')`), `_matchlist.html:4` e `match.html:8` per i
punti (`|it_plural('punto','punti')`), `match.html:312` (`|it_plural('occasione')` e
`'clamorosa' if p.big_chances == 1`). In `_matchlist.html` la serie V/N/P e «N pt» non hanno
un plurale da concordare.

**Protetti dalla virgola del decimale**: `dec(1)`/`dec(2)` stampano `1,0`, e `AGREEMENT`
esclude esplicitamente quel caso (`(?<![\d,])`) — `_matchlist.html:76` («3,1 gialli/gara»,
già documentato in `tests/test_verify_scripts.py`), `match.html:110` e `:813`
(`… partite su 100` con `dec(1)`), `accuracy.html:102`, `stagione.html:26`,
`match.html:280`/`:430`. Sono decimali, non contatori.

**Numeri grandi con `it_num`** — la concordanza con 1 è irraggiungibile e `it_plural`
toglierebbe il separatore: `match.html:139` (`fr.n_tot`), `:148`/`:150` (`r.n` delle fasce
storiche, minimo osservato **197**), `:201` (`fg.n_first`).

## 7. Due cose viste passando, dichiarate e non toccate

Non sono concordanza, quindi non entrano in questo hotfix; sono scritte qui perché le ho
misurate e non voglio che si perdano.

1. **Il controllo [14] (separatore delle migliaia) legge solo `partite/*.html`.**
   `verify_site.py:665` definisce `pages = sorted((site / "partite").glob("*.html"))`, quindi
   `<b>5835</b> partite` su `accuratezza.html` — che la regex di [14] **trova** (verificato:
   `re.search` → match `5835  partite`) — non viene segnalato. I controlli di contenuto
   (`AGREEMENT`, decimali, inglese) invece girano su tutte le pagine (`:225`). Copertura
   ridotta su una pagina sola: un'uscita pulita con copertura ridotta non è un pass
   (`docs/27` §4.2).
2. **Tre conteggi sulle schede partita crescono con l'archivio e sono stampati senza
   `it_num`**: `{{ lp.n }} partite di <lega>` (`match.html:160`/`:170`, oggi 263–356),
   `{{ fg.n_matches }} partite di questa stagione` (`:187`, oggi 297) e `{{ fg.n_first }}`
   (`:196`, che a `:201` lo stesso numero lo stampa **con** `it_num`). Quando supereranno
   1.000 il controllo [14] — che su `partite/` gira — fermerà il daily: è la stessa trappola
   di oggi, con un altro invariante. Correzione da tre righe (`|it_num`), output identico
   finché restano sotto 1.000.

> **Entrambi chiusi il 2026-09-19** (sessione `arena/01a0ba12`,
> [`docs/41`](41_verifica_autoaggiornamento_e_coda_2026-09-19.md) §3.2 e §3.3): `[14]` ora gira su
> **tutte** le 4.137 pagine del sito e legge anche il sostantivo «gol» (prima: 375 pagine, solo
> `partite/`), e i tre conteggi passano da `it_num` insieme a `composizione`, alla colonna
> «mercato» e a `model_versions`. Misura dopo la correzione: **0** pagine che violano `[14]`
> esteso, prima erano **165**.

## 8. Verifiche

| controllo | esito |
|---|---|
| `pytest -q` | **453 passed** (451 + i due test nuovi; il terzo intervento è l'estensione di un test già esistente) |
| `ruff check .` | pulito (`All checks passed!`) |
| `fda build` | exit 0 — 375 partite / 2.364 fixtures / 7.480 giocatori (invariato) |
| `scripts/verify_site.py --site site --data data/processed` | exit 0 — **0 problemi · 151.388 controlli** (gli stessi di prima del fix: nessuna copertura persa) |
| `scripts/parita_schede.py site` | exit 0 — 60/60 schede · 23 sezioni · 12 voci d'indice · min 17.546 = 91% della mediana 19.264 |
| `scripts/resa_375.py` | exit 0 — **23.648 misure · 0 problemi** |
| `scripts/audit_match_sections.py` | exit 0 (divario max−min fra medie di lega: 1,8 righe) |
| diff del sito prima/dopo | `partite/` **0/375** pagine diverse, radice **0/8** (§5) |

**Copertura dei test.** I punti 1-5 hanno un test unitario ciascuno
(`test_concordanza_uno_assente_giorno_gara` per 1-3, `test_style_rows_concordanza_una_sola_gara`
per 4-5). I punti 6-14 sono nei template: la loro prova è (a) il gate, che gira su tutte le
pagine **e** sugli attributi — il test `test_verify_site_content_checks` è stato esteso per
dimostrare che intercetta `1 assenti`, `1 titolari`, `1 giocatori`, `1 partite` e `1 giorni`
sia nel testo sia in un `aria-label`, e che `1 gara finita` **non** è un problema — e (b) la
build prima/dopo identica (§5). Un test di render con `played = 1` richiederebbe una fixture
di build completa: resta un punto aperto, dichiarato come tale. **Chiuso il 2026-09-19**
(sessione `arena/01a0ba12`, `docs/41` §3.9): `tests/test_numeri_pubblicati.py` costruisce
`accuratezza.html` sullo seed dei test di sito — che ha **una** gara valutata — e verifica la
concordanza («1 gara valutata», non «1 gare»), la cardinalità nella riga «Tutti» e il rapporto
`(k/1)` della calibrazione.

I numeri di `verify_site` e `parita_schede` dipendono dai dati: qui sono calcolati sui
Parquet versionati su `main`, non su quelli raccolti dai due run rossi (che il gate ha
fermato prima del commit). Con i dati del run il totale dei controlli sarà diverso
(l'ultimo valore registrato in `docs/39` è 150.006); ciò che deve restare uguale è
**0 problemi** e la parità dei contatori di copertura.

## 9. Prossimo passo

1. ~~**Merge di questo hotfix**~~ **fatto e verificato in produzione** (2026-09-19, merge
   commit `b8bfe12`, deroga su ordine esplicito dell'utente — `docs/13`, «Deroga al flusso
   di merge (2026-09-19, PR #59)»). Il `daily` è ripartito da solo (trigger `push` su
   `main`): run **`35447124903`** **success**, job `run` verde in 17m19s con `verify_site`,
   `parita_schede` e `resa_375` — i tre passi che erano rossi — più il commit dei dati
   **`e9af29c`** («data: run 2026-09-19 14:11 UTC [skip ci]») e il deploy Pages (9s).
   Sulla pagina pubblicata `partite/5749682.html` si legge «infermeria pesante: **1
   assente**, ≈ 0,7 xG+xA a partita in meno» e «Bologna deve rinunciare a **1 assente**»;
   col contatore a 3 il plurale resta corretto («Torino … **3 assenti**, di cui 1 titolare
   abituale»). I tre run rossi (`35432745402`, `35438804509`, `35446188137`) sono chiusi.
2. ~~Punti aperti dichiarati in questo documento, da fare in un giro proprio~~ — **tutti e tre
   chiusi il 2026-09-19** (sessione `arena/01a0ba12`, `docs/41` §3.2-§3.4 e §3.9): l'ordine non
   deterministico delle card «Percentili di lega» (§5.1), la copertura di [14] limitata a
   `partite/` e i tre conteggi senza `it_num` (§7), il test di render coi contatori a 1 (§8).
3. ~~`docs/STATO.md` sopra la soglia degli ~80 kB della regola A5~~ — **archiviazione fatta il
   2026-09-19** (`docs/41` §3.8): 118.900 → **61.422 byte**, i giri 30-45 in
   `STATO_archivio_2026-09-19.md`, verifica riga per riga senza perdite.
