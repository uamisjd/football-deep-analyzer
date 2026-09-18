# 27 — Verifica totale del sito (qualità · quantità · visivo · ordine · precisione) — 18/09/2026

Richiesta dell'utente: *«verifica che il sito sia qualitativamente, quantitativamente, visivamente,
ordinato e preciso, profondo e accurato, di qualità e di valore»*, sui due URL
`index.html` e `partite/5795456.html`.

Tutto ciò che segue è **misurato**, non impressionistico. Ogni numero ha il comando che lo
produce. Dove una misura non è possibile dal sandbox è scritto esplicitamente.

---

## 0. Metodo: il sito è stato ricostruito, non solo guardato

Il sito pubblicato non è stato valutato "a vista". È stato **rigenerato nel sandbox dagli stessi
dati che pubblica la CI** (`HEAD` = `3cc59e3`, run dati 18/09 17:11 UTC) e poi misurato:

| passo | comando | esito |
|---|---|---|
| installazione | `pip install -e ".[dev]"` | ok |
| suite di test | `pytest -q` | **431 passed** (430 baseline + 1 test nuovo) |
| build del sito | `fda build` | **exit 0** · 375 schede / 2.364 partite / 7.466 giocatori · 3m14s |
| verifica del sito | `python scripts/verify_site.py` | **exit 0 — 0 problemi · 97.872 controlli** |
| lint | `ruff check .` | **172** = baseline del repo, nessuna nuova |
| audit delle schede | `python scripts/audit_match_sections.py` | exit 0 · 375 pagine |

**Riproducibilità verificata numero per numero.** I valori letti sulla pagina live
`partite/5795456.html` (Brentford–Chelsea) coincidono tutti con la build locale:
`1,60` · `1,44` · `3,04` · `58%` · `63%` · `39,0%` · `44,2%` · Elo `1543`/`1554` ·
`5.829` gare di backtest · `1.180` partite · timestamp `19:04`. Il sito pubblicato **è**
questo codice su questi dati.

---

## 1. Quantitativo — cosa c'è davvero

| grandezza | valore | come è misurato |
|---|---|---|
| pagine HTML pubblicate | **4.124** | conteggio file in `site/` |
| peso totale | 116,8 MB | `du` |
| schede partita | 375 (mediana **64 KB**, max 93 KB) | idem |
| schede giocatore | 3.741 (mediana 27 KB) | idem |
| sezioni per scheda partita | min **22** · mediana **23** · max **30** (8.963 `<h2>` totali) | parse HTML |
| testo visibile totale | **18,66 M caratteri** | estrattore HTML proprio |
| link interni | **111.654 risolti · 0 rotti** | risoluzione percorsi |
| ancore in pagina | **0 rotte** | confronto `href="#x"` ↔ `id` |
| celle `<th>` con `scope` | **101.950 / 101.950** | verify_site [27] |
| attributi leggibili (aria-label/title/alt) | **186.054** verificati | verify_site [27b], nuovo |
| sitemap | 4.123 URL = 4.124 pagine − `404.html` (esclusa correttamente, `noindex`) | confronto |
| font | self-hosted (9 woff2 locali), **nessuna chiamata a CDN** | `ls site/assets/fonts` |
| domini esterni linkati | `news.google.com` (110), `ansa.it` (10) — solo fonti notizie | scan href |

**Profondità per scheda.** 7 sezioni su **tutte** le 375 schede (Scontro tattico, Confronto di
stagione, Contesto, Verifica approfondita, Naviga, Approfondisci, Nota); 14 sezioni sulle 309
schede di gare finite (Statistiche, Momentum, Cartina dei tiri, Corsa xG, Qualità dei tiri,
Portieri, Migliori in campo…); 8 sezioni sulle 66 schede pre-partita ricche (Analisi pre-partita,
Come arrivano, I giocatori che decidono, Panchina e posta in gioco, Mercato, Vita del club,
Clima del club, Fatti rilevanti).

**Parità fra i 7 campionati** (nessuna lega di serie B nel portale):

| campionato | schede | sezioni min/med/max |
|---|---|---|
| LaLiga | 69 | 22 / 22 / 29 |
| Eredivisie | 63 | 22 / 22 / 29 |
| Liga Portugal | 62 | 22 / 22 / 29 |
| Serie A | 50 | 22 / 23 / 29 |
| Premier League | 50 | 23 / 23 / 30 |
| Ligue 1 | 45 | 22 / 22 / 29 |
| Bundesliga | 36 | 22 / 23 / 28 |

Le 7 sezioni di base sono a **100 % in ogni lega**. Le differenze sono spiegate dai dati, non
da scelte editoriali: le sezioni post-partita seguono il numero di gare finite per lega
(59/69, 54/63, 53/62, 40/50, 40/50, 36/45, 27/36).

---

## 2. Qualitativo — accuratezza dichiarata e verificata

- **Accuratezza live**: 98 gare valutate, RPS **0,1993** vs base naive 0,2324 (Δ −0,033).
  La pagina dichiara da sola che «i bookmaker si attestano intorno a 0,19–0,20»: il modello è
  **a quel livello, non sopra**, e lo dice.
- **Onestà dove il modello perde**: la riga Bundesliga riporta RPS 0,2627 vs naive 0,2499,
  cioè **Δ +0,013 — peggio della base**. È pubblicato, non nascosto.
- **Backtest fuori campione**: 5.829 gare, RPS 0,1987, ricalcolato dal verificatore e uguale
  al pubblicato (verify_site [8]).
- **Intervalli, non promesse**: ogni fascia di pronostico ha l'IC 95 % di Wilson ricalcolato
  (24 righe, verify_site [7]); i quartili del primo gol sono 492 verificati.
- **Nessuna stima al posto di un dato mancante**: la card «Dati fisici» compare **solo** in
  Premier League perché `physical_metrics_*` esiste nei dati solo lì (240 righe, **0** per le
  altre 6 leghe — misurato su `player_stats.parquet`). È un limite di fonte, gestito senza
  inventare numeri.

---

## 3. Visivo e ordinato — misure, non opinioni

**Contrasto WCAG ricalcolato dai token del CSS** (formula WCAG 2.1, 18 colori di testo × 5
superfici × 2 temi = 180 coppie):

- tema **chiaro**: minimo **4,50:1** — 0 coppie sotto 4,5:1, 0 sotto 3:1.
- tema **scuro**: minimo 3,98:1 (`--accent-soft` su `--surface3`). Verificato nel CSS: quel
  token è usato **solo come `border-color`** e in un gradiente, mai come `color:` → la soglia
  applicabile è 3:1, quindi conforme. Le coppie di testo vere stanno tutte ≥ 4,57:1.
- Il bordo dell'header che nel tema chiaro restava scuro (P2.1/P2.2, `docs/19` §4) è corretto:
  `site.css:105` e `:514` usano entrambi `var(--line)`.

**Struttura e accessibilità** su 4.124 pagine: `lang="it"` 4.124/4.124 · un solo `<h1>` per
pagina · `title` + `meta description` + `og:*` + `viewport` presenti · `canonical`
auto-referenziale su tutte (su `index.html` punta alla radice, coerente con la sitemap) ·
`404.html` senza canonical e con `noindex` (corretto) · 0 id duplicati · 0 `<img>` senza `alt` ·
skip-link presente · `prefers-reduced-motion` e `prefers-contrast: more` gestiti ·
7 breakpoint responsive (360/380/520/560/760/900 px) · `.tablewrap{overflow-x:auto}` sulle
tabelle.

**Peso**: mediana 27 KB, p95 64 KB, max 1.417 KB (`prossime.html`, che contiene di proposito
l'intero calendario ed è sotto il suo tetto dichiarato di 1.800 KB).

**Navigazione**: 0 destinazioni rotte. La barra «Naviga» usa etichette di gruppo («Sintesi»,
«Dati e contesto», «Post-partita») che puntano alla prima sezione del gruppo: è una scelta,
non un errore — ogni destinazione esiste e ha un titolo.

---

## 4. Difetti trovati (e corretti in questo giro)

La verifica ha trovato **quattro classi di difetti reali**, tutte dello stesso tipo: il testo
generato era giusto quasi ovunque e sbagliato in punti singoli che nessun controllo leggeva.

| # | difetto | occorrenze | radice | correzione |
|---|---|---|---|---|
| 1 | `(7 punti su 9, **2.33** a gara)` — decimale col **punto** in un portale che usa la virgola | 52 su 29 schede | `analysis.py:1958`, unico `:.2f` del file senza `.replace(".", ",")` | virgola italiana |
| 2 | «+1 **punti** sul secondo» | 56 su 43 pagine | `_matchlist.html:47`, `match.html:22` | filtro `it_plural` |
| 2b | «{squadra}: 1 **punti** nelle ultime 3» e «15º con 1 **punti**» | 49 | `analysis.py:3680` e `:1214` | `it_plural` |
| 3 | «di cui 1 **titolari abituali**» | 25 su 22 schede | `analysis.py:1319`, unica frase senza `it_plural` | `it_plural` |
| 4 | «indisponibile per questa gara (**injury**)» — valore grezzo inglese della fonte | 8 | `analysis.py:2018` non usava `unavailability_it()` (usato invece a `:2529` e `:3569`) | traduttore esistente |
| 5 | `aria-label="… nelle ultime 3 partite, 1 **punti**."` | 30 | `_matchlist.html:4` | `it_plural` |
| 6 | `title="Arbitro: … — **9.0** rigori totali"` — float dove serve un intero | 124 | `_matchlist.html:76` | `|round|int|it_plural` |

Totale: **344 stringhe sbagliate** corrette. Nessun numero è cambiato: sono tutte frasi.

**Due test bloccavano i difetti invece di impedirli** — cioè il difetto era diventato la
aspettativa:

- `test_panchina_notizie.py:667` asseriva `«…(7 punti su 9, 2.33 a gara).»`;
- `test_panchina_notizie.py:692` asseriva `«…(injury).»`.

Entrambi aggiornati alla forma corretta. Aggiunto un test nuovo sulla concordanza dei
titolari (1 → singolare, 2 → plurale).

### 4.1 Perché nessuno dei sei difetti era intercettato

Non è mancanza di controlli: `verify_site.py` ha da sempre `DECIMAL_POINT`, `ENGLISH` e
`AGREEMENT`. Il problema era **dove guardavano**:

1. **Esclusione troppo larga.** I blocchi «Da sapere · …» vivono dentro la card
   `id="notizie"`, che il parser esclude per proteggere i titoli di stampa citati *verbatim*.
   Ma quei blocchi sono **frasi generate da noi**: escludendo l'intera card, il nostro testo
   usciva dai controlli di lingua. → Aggiunta la classe `sapere` e la sua riammissione.
2. **Lista di sostantivi incompleta.** `AGREEMENT` cercava `gare|partite|vittorie|…` ma non
   conteneva né `punti` né `titolari`, cioè le uniche due forme davvero sbagliate. → Estesa;
   misurato: 81 occorrenze intercettate, **0 falsi positivi**. Il verso opposto («2 punto»)
   **non** è presidiato: l'unico candidato era «Schalke **04 giocatore**», nome di squadra
   seguito da un'intestazione di tabella — un falso positivo certo, documentato nel codice.
3. **Gli attributi non erano una dimensione presidiata.** `aria-label` e `title` li legge un
   lettore di schermo, ma i controlli giravano solo sul testo visibile. → Nuovo blocco
   **[27b]**: 186.054 attributi verificati, raccolti dentro il parser così restano fuori i
   `title` dei link di stampa.
4. **Il verificatore duplicava il bug.** `verify_site.py` ricostruiva in modo indipendente la
   frase del bilancio casa/trasferta… con lo stesso `:.2f` col punto. Generatore e verificatore
   concordavano sull'errore, quindi nessuno dei due lo vedeva. → Corretto mantenendo il
   ricalcolo indipendente (la virgola è scritta a mano lì di proposito).

### 4.2 Una regressione di copertura trovata e chiusa nello stesso giro

Dopo la correzione, `verify_site` dava **0 problemi** ma il contatore
`[11] riassunti del modello` era sceso da **164 a 160**. Causa: `hero_re` cercava solo
«punti sul secondo», quindi le 4 schede con margine 1 non corrispondevano più e venivano
saltate in silenzio (`if not m: continue`). **Un'uscita pulita con copertura ridotta non è un
pass.** → Regex estesa a `punto|punti` e concordanza ora *verificata*, non solo tollerata.

Controllato con un diff sui contatori: **tutti** i 35 contatori di copertura sono identici a
prima dell'intervento, e il totale è tornato a **97.872**, con in più i 186.054 attributi.

### 4.3 Presidio: la prova che funziona

Il nuovo controllo è stato **provato a fallire** sulla build difettosa, prima di correggere il
codice: `verify_site --content-only` → **exit 1, `PROBLEMI (141): {'concordanza': 81, 'inglese': 8,
'decimale': 52}`**. Dopo le correzioni: **exit 0**.

---

## 5. Cose che restano aperte (dichiarate, non risolte)

1. **`docs/preview/*.png` disallineati dal CSS.** `scripts/render_preview.py` copia i token a
   mano e **7 su 18** non corrispondono più a `site.css` (`--line` `#1f2836` vs `#263142`,
   `--mut` `#93a0b3` vs `#a8b5c8`, `--mut2`, `--surface2`, `--draw`, `--lose`, `--accent-dim`),
   più i 6 colori V/N/P dichiarati «approssimazioni». In più il blocco `PAGE` è fermo al
   **build 15/09/2026** (Elche–Real Madrid, Ajax 75 %), mentre la home di oggi ha 6 gare.
   **Non tocca il sito pubblicato**: sono solo le immagini di documentazione nel repo.
2. **`ruff`: 172 segnalazioni** (99 auto-fixabili). È la baseline dichiarata in `docs/STATO.md`,
   non una regressione di questo giro, ma il gate di lint non è pulito.
3. **Docstring datata**: `analysis.py:3132` dice «**30** partite in archivio» per i dati fisici;
   misurato oggi sono **40** partite (1.236 righe giocatore, 20 squadre).
4. **`analysis.py:1958` era l'unico** `:.2f` senza virgola su 10 occorrenze nel file: vale la
   pena di un helper unico invece di 10 `.replace(".", ",")` ripetuti.
5. **Non verificabile dal sandbox**: resa visiva reale in un browser (Lighthouse, paint,
   comportamento a 375 px). Nel sandbox non c'è un browser; la verifica visiva qui è
   strutturale e sui token. Il sito è servito in preview Arena per il controllo a vista.
6. **Clone shallow**: il sandbox ha **1 solo commit** (`git rev-list --count HEAD` = 1), quindi
   nessuna affermazione sulla storia (chi ha introdotto cosa, quando) è verificabile da qui.

---

## 6. Verdetto

| dimensione | esito | motivo misurato |
|---|---|---|
| quantitativa | **solida** | 4.124 pagine, 111.654 link senza un rotto, 375 schede da 23 sezioni mediane |
| qualitativa | **solida** | accuratezza pubblicata e ricalcolata, IC 95 %, i casi in cui il modello perde sono esposti |
| visiva | **conforme** | 180 coppie di contrasto ricalcolate: 0 sotto AA nel testo; temi coerenti |
| ordine | **buono** | 0 residui (`nan`/`None`/`NaN`/`inf`/template non resi) su 18,66 M caratteri; 0 inglese nei giorni/mesi/etichette/meteo |
| precisione | **migliorata in questo giro** | 344 stringhe sbagliate corrette + 4 punti ciechi del verificatore chiusi |
| profondità | **alta** | 22–30 sezioni per scheda, 7 leghe alla pari, catena della probabilità tracciata passo per passo |

**Prossimo passo:** i 6 punti di §5. Il più utile è il primo (token letti dal CSS a runtime in
`render_preview.py`, invece di copiati a mano) perché elimina la classe di difetto, non
l'istanza.
