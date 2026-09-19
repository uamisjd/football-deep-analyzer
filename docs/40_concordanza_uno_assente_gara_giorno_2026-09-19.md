# 40 — Concordanza con 1: «1 assente», «1 gara», «1 giorno» (19/09/2026)

> **Il daily su `main` è rosso due volte di seguito e il deploy è fermo.** I run
> `35432745402` (schedulato) e `35438804509` (push del merge di PR #58) si sono fermati
> entrambi sullo stesso passo — «Verifica il sito (verify_site)» — con lo stesso messaggio:
> `partite/5749682.html: concordanza '1 assenti'`. Il gate sta **prima** del passo «Commit dei
> dati aggiornati» e **prima** di «Prepara il sito per Pages»: quindi i dati raccolti in quei
> due run non sono stati committati e il sito pubblicato è rimasto alla build precedente.
> Correzione hotfix: cinque punti di concordanza nei generatori di testo, due test, nessuna
> parola cambiata nelle pagine di oggi (misurato, §4).
> Sessione `arena/01a0b97c`, branch `arena/01a0b97c-football-deep-analyzer`, base `41c9c89`.

---

## 1. I cinque punti

Tutti e cinque sono la stessa cosa: un contatore interpolato in una frase senza
:func:`fda.site.fmt.it_plural`, l'helper che il progetto usa dal 12/09/2026 (audit: «1 gare»
su 1098 pagine) proprio perché il singolare va concordato. `it_plural(n, 'gara')` stampa
`1 gara` e `33 gare`; senza, la f-string stampa il nome al plurale qualunque sia `n`.

| # | dove | la frase **prima** (misurata) | la frase **dopo** | quando il contatore vale 1 |
|---|---|---|---|---|
| 1 | `analysis.py:1453` — `club_mood`, riga «infermeria pesante» | `infermeria pesante: 1 assenti, di cui 1 titolare abituale, ≈ 0,9 xG+xA a partita in meno` | `infermeria pesante: 1 assente, di cui 1 titolare abituale, …` | **è il caso del gate**: la soglia della riga non è il numero di assenti (§2) |
| 2 | `analysis.py:2594` — `season_compare`, riga «Punti» | `3 in 1 gare` | `3 in 1 gara` | prima giornata di campionato: `played` = 1 |
| 3 | `analysis.py:3891` — `narrative`, frase sul riposo | `Inter gioca dopo soli 1 giorni di riposo.` | `Inter gioca dopo un solo giorno di riposo.` | due gare a 24 h di distanza (la soglia del segnale è ≤ 3 giorni) |
| 4 | `advanced.py:518-526` — `style_rows._xg_help`, tooltip «xG / gara» | `Gol attesi, media stagionale FotMob su 1 gare` | `… media stagionale FotMob su 1 gara` | `played` = 1 (prima giornata, o neopromossa con un solo turno raccolto) |
| 5 | `advanced.py:541-546` — `style_rows._quota_help`, tooltip delle quote xG | `(FotMob, 1 gare finite)` | `(FotMob, 1 gara finita)` | `split_played` = 1, lo stesso campione del punto 4 |

Due note di forma, entrambe deliberate:

- **punto 3**: non basta concordare il sostantivo. «dopo **soli** 1 giorno» resta sbagliato
  perché l'aggettivo è plurale: la forma corretta è «dopo **un solo giorno** di riposo». Con
  2 o 3 giorni la frase è **identica a prima** («dopo soli 3 giorni di riposo»).
- **punti 4 e 5**: il valore può essere il trattino «—» (dato mancante), non un numero. Per
  questo `advanced.py` non chiama `it_plural` direttamente ma un helper locale,
  `_n_gare(v, singolare, plurale)`, che lascia passare il trattino tale e quale — seguito dal
  plurale, come stampava prima: `— gare`. Il punto 5 concorda anche l'aggettivo
  (`gara finita` / `gare finite`), che `it_plural` da solo non avrebbe toccato.

## 2. Perché il gate è rosso oggi e non lo era ieri

La riga «infermeria pesante» della card *Clima del club* scatta su **tre** soglie alternative
(`analysis.py`, costanti dichiarate nella nota della card):

```python
MOOD_ABSENT_N = 4           # assenti → infermeria pesante
MOOD_ABSENT_STARTERS = 2    # titolari abituali fuori
MOOD_ABSENT_CONTRIB = 0.5   # xG+xA/gara portati via dagli assenti
```

Il numero di assenti **non è** la soglia che fa scattare la riga: basta un solo
indisponibile che da solo porti via ≥ 0,5 xG+xA a gara — un titolare decisivo — perché la
frase venga pubblicata. E la frase cominciava col contatore al plurale fisso. Fino al
18/09 quel caso non era passato dai dati raccolti; nel run del 19/09 sì, su una partita
precisa (`5749682`), e il gate l'ha fermato. **Il gate ha funzionato come progettato**: la
lista dei sostantivi di `AGREEMENT` contiene `assenti` e il controllo gira su ogni pagina
(`docs/27` §4.1); mancava il prodotto, non il presidio.

Gli altri quattro punti **non** sono ancora passati dai dati (§3): sono della stessa classe
e sarebbero stati fermati allo stesso modo, il primo giorno in cui un contatore vale 1.

## 3. La misura: dove stanno oggi quei contatori

Conteggi sulle **4.131 pagine** della build locale fatta con i dati versionati su `main`
(che non sono quelli dei due run rossi: quei run si sono fermati prima del commit dei dati).

| frase pubblicata | occorrenze | valore **minimo** osservato | può valere 1? |
|---|---|---|---|
| `infermeria pesante: N assenti` | 68 | **2** | sì — soglia sul contributo, non su `N` (punto 1) |
| `gioca dopo soli N giorni di riposo` | 78 | **2** | sì — la soglia è ≤ 3 (punto 3) |
| `media stagionale … su N gare` | 750 | **3** | sì — prima giornata (punto 4) |
| `(FotMob, N gare finite)` | 1.500 | **3** | sì — stesso campione (punto 5) |
| `M in N gare` (confronto di stagione) | 750 | **3** | sì — `played` ≥ 1 per costruzione (punto 2) |

Quindi con i dati di oggi le cinque forme sbagliate **non compaiono**: il minimo osservato è
sempre ≥ 2. Non è un motivo per lasciarle — è il motivo per cui la prova che la correzione
funziona non può essere «rigiro il sito e guardo», ma deve essere (a) la chiamata diretta
con il contatore a 1 e (b) la prova che con il contatore ≥ 2 **non cambia una parola**.

### 3.1 Prova di morso (prima di correggere, come da prassi — `docs/27` §4.3)

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

Le cinque frasi, misurate chiamando le funzioni con il contatore a 1 (prima → dopo):

| # | prima | dopo |
|---|---|---|
| 1 | `infermeria pesante: 1 assenti, di cui 1 titolare abituale, ≈ 0,9 xG+xA a partita in meno` | `infermeria pesante: 1 assente, di cui 1 titolare abituale, ≈ 0,9 xG+xA a partita in meno` |
| 2 | `{'label': 'Punti', 'h': '3 in 1 gare', 'a': '5 in 4 gare'}` | `{'label': 'Punti', 'h': '3 in 1 gara', 'a': '5 in 4 gare'}` |
| 3 | `Inter gioca dopo soli 1 giorni di riposo.` | `Inter gioca dopo un solo giorno di riposo.` |
| 4 | `Gol attesi, media stagionale FotMob su 1 gare` | `Gol attesi, media stagionale FotMob su 1 gara` |
| 5 | `(FotMob, 1 gare finite)` | `(FotMob, 1 gara finita)` |

E con il contatore ≥ 2 l'uscita è **identica** a prima, carattere per carattere:
`soli 3 giorni di riposo`, `5 in 4 gare`, `su 5 gare`, `(FotMob, 5 gare finite)`.

## 4. Il sito di oggi non cambia di una parola

Build completa prima e dopo la correzione, **stesso codice a parte il fix, stessi dati**
(`41c9c89` + dati versionati), pagine confrontate al netto dei due timestamp di build
(`aggiornato gg/mm/aaaa hh:mm` e `Pagina generata automaticamente il …`):

| blocco | pagine diverse |
|---|---|
| `partite/` (le schede toccate dalla correzione) | **0 / 375** |
| radice (`index`, `oggi`, `prossime`, `risultati`, `accuratezza`, `info`, `stato`, `404`) | **0 / 8** |
| `giocatori/` | 2.074 / 3.748 — **non attribuibili al fix**: vedi §4.1 |

### 4.1 Un difetto preesistente misurato per caso (non toccato qui)

Le 2.074 schede giocatore diverse **non** dipendono da questa correzione: lo stesso codice,
costruito **due volte di seguito**, produce la stessa differenza sullo stesso numero di
pagine (controllo eseguito: 2.074 / 3.748 anche fra le due build del codice corretto, mentre
`partite/` resta 0 / 375 in entrambi i confronti).

La causa è una riga di `players.py` (`:594`):

```python
radar_ids = {sid for sid, _ in RADAR.get(pos_int, [])}     # insieme: ordine non deterministico
for sid in list(radar_ids) + PCT_EXTRA.get(pos_int, []):   # l'ordine cambia a ogni processo
```

L'ordine delle card «Percentili di lega» dipende dall'ordine di iterazione di un `set` di
stringhe, che cambia con l'hash seed del processo. Il contenuto è lo stesso, cambia la
sequenza. La correzione è una riga (`[sid for sid, _ in RADAR.get(pos_int, [])]`, che tiene
l'ordine dichiarato in `RADAR`), ma **non è di questo hotfix**: qui si sblocca il daily, e un
diff che tocca 2.074 pagine ne nasconderebbe cinque. Resta come punto aperto (§6).

## 5. Esaminati e **non** toccati

Censimento completo dei contatori interpolati nei generatori di testo
(`src/fda/site/*.py`, tutti i sostantivi della lista `AGREEMENT` di `verify_site`):

- **`advanced.py:263` e `:267`** — la nota della calibrazione nello «scomposizione della
  probabilità»: `ultimi 730 giorni` e `4.743 gare fuori campione`. Il primo valore è
  `FIT_WINDOW_DAYS` (costante del calibratore, non un dato), il secondo è la numerosità del
  backtest (misurato oggi: 4.743 / 4.760 / 5.812). Non possono valere 1, e `it_plural`
  **toglierebbe** il separatore delle migliaia (`4.743` → `4743`), cioè peggiorerebbe la
  formattazione. Se un giorno la finestra diventasse piccola, la forma giusta è un
  condizionale che conserva `_int_it`.
- **`analysis.py:1270-1272`, `:1283`, `:1297`** (panchina: punti/gara, bilancio contro
  l'avversaria, scontro diretto fra allenatori) — già concordati o già protetti da una
  soglia (`len(vs) >= 3`, `len(hv) >= 2`); `1271` stampa esplicitamente
  «1,0 punti/gara su 1 gara finita».
- **`analysis.py:1417`, `:1421`, `:1424`, `:1426`, `:1482`** (le altre righe del clima:
  sconfitte consecutive, «non vince da», imbattuta, attacco a secco, congestione) — ognuna
  è pubblicata solo sopra la propria soglia (3, 4, 5, 3, 3): il contatore non può valere 1.
- **`analysis.py:1471`** («riposo corto») e **`:1095`** («giorni di riposo» nel prossimo
  impegno) — già concordati con un condizionale.
- **Template** — `match.html:348` e `:359` stampano `({{ xg.source }}, {{ xg.played }} gare)`
  e `{{ xg.played }} gare ·` **senza** `it_plural`, e `season_xg` non ha una soglia minima su
  `played`: con una sola gara raccolta la card della squadra stamperebbe «(FotMob, 1 gare)».
  È la stessa classe dei punti 4-5 e la stessa variabile (`played`), ma sta nel template, non
  nei due moduli di questo hotfix: **segnalato, non corretto qui** (§6). Non è scattato nel
  run del 19/09 (il minimo osservato è 3) e la correzione è
  `{{ xg.played|it_plural('gara') }}`, che con `played` ≥ 2 stampa esattamente ciò che stampa
  oggi.
- `accuracy.html:18` (`composizione.n`, migliaia di gare), `match.html:532`
  (`referee.matches`, protetto da `MIN_REFEREE_MATCHES = 15`), `index.html:61` e
  `build.py:436-439` (`DETAIL_WINDOW_DAYS`, costante) — non raggiungibili con 1.

## 6. Verifiche

| controllo | esito |
|---|---|
| `pytest -q` | **453 passed** (451 + i due test nuovi) |
| `ruff check .` | pulito (`All checks passed!`) |
| `fda build` | exit 0 — 375 partite / 2.364 fixtures / 7.480 giocatori (invariato) |
| `scripts/verify_site.py --site site --data data/processed` | exit 0 — **0 problemi · 151.388 controlli** (gli stessi 151.388 di prima del fix: nessuna copertura persa) |
| `scripts/parita_schede.py site` | exit 0 — 60/60 schede · 23 sezioni · 12 voci d'indice · min 17.546 = 91% della mediana 19.264 |
| `scripts/resa_375.py` | exit 0 — **23.648 misure · 0 problemi** |
| `scripts/audit_match_sections.py` | exit 0 (divario max−min fra medie di lega: 1,8 righe) |
| diff del sito prima/dopo | `partite/` **0/375** pagine diverse, radice **0/8** (§4) |

I numeri di `verify_site` e `parita_schede` dipendono dai dati: qui sono calcolati sui
Parquet versionati su `main`, non su quelli raccolti dai due run rossi (che il gate ha
fermato prima del commit). Con i dati del run il totale dei controlli sarà diverso
(l'ultimo valore registrato in `docs/39` è 150.006); ciò che deve restare uguale è
**0 problemi** e la parità dei contatori di copertura.

## 7. Prossimo passo

1. **Merge di questo hotfix** → il `daily` riparte da solo (trigger `push` su `main`) e, se
   il gate passa, committa i dati e pubblica su Pages.
2. Due punti aperti della stessa classe, da fare in un giro proprio (non nell'hotfix):
   `match.html:348`/`:359` (`{{ xg.played }} gare` senza `it_plural`) e l'ordine non
   deterministico delle card «Percentili di lega» (`players.py`, `set` → lista, §4.1).
3. Verifica dopo il merge: run `daily` verde, deploy Pages arrivato, e sulla pagina
   `partite/5749682.html` la riga del clima con «1 assente».
