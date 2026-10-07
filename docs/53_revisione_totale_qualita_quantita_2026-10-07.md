# 53 — Revisione totale di qualità e quantità (2026-10-07)

**Richiesta:** «cosa abbiamo da fare a questo progetto? fai una revisione e controlla
cosa non funziona o cosa dobbiamo migliorare, voglio che tutto abbia una qualità e
quantità ottima».

**Metodo:** ogni numero qui sotto è misurato oggi (7/10/2026) su questo checkout
(`aa760b9`, dati del run delle 15:45 UTC) o via API GitHub. Nulla è presunto:
la colonna «come» dice sempre dove la misura è stata presa.

## 0. Verdetto in breve

Il progetto **funziona e pubblica**: pipeline verde, sito live aggiornato oggi,
copertura delle partite al 100%, zero errori di raccolta, zero link rotti.
Non ci sono guasti aperti (0 issue, 0 PR rosse).

Trovati **3 difetti veri ma piccoli** (attribuzione fonti in footer, filtro leghe
nelle notizie, commenti stali), **1 voce di coda chiudibile con misura (P2.4)** e
**4 decisioni di prodotto** che spettano all'utente (già proposte in `docs/49`,
`docs/50` §6, `docs/52`: watchdog di freschezza, split dei gate, budget
giornaliero, Lighthouse). Il resto è salute confermata con numeri.

## 1. Salute della pipeline (verificato via GitHub + locale)

| Cosa | Misura | Come |
|---|---|---|
| Daily su `main` | verde: run `37645413601` (9m8s, 37 min fa) e `37618498043` | `gh run list` |
| `lab` settimanale | verde: `37298466696` (2 giorni fa, 9m43s) | `gh run list --workflow lab.yml` |
| `benchmark-quote` | verde: `37114570670` (4 giorni fa) | `gh run list --workflow benchmark.yml` |
| Issue aperte | **0** | `gh issue list` |
| PR aperte | **1**: #84, solo documenti, `MERGEABLE`/`CLEAN`, da un altro branch | `gh pr view 84` |
| Sito live | `AGGIORNATO 07/10/2026 17:40`, «Oggi nessuna partita» (sosta nazionali, corretto: ripresa 9/10 con 6 gare) | fetch della home su Pages |
| Suite | **515 passed** (91 s) | `pytest -q` in locale |
| Ruff | `All checks passed` | `ruff check .` |
| Build | exit 0: **441** schede / **2.364** partite / **7.496** giocatori | `fda build` |
| `verify_site` | **0 problemi · 159.573 controlli** | locale |
| `parita_schede` | **66** schede, 25 id, 14 voci indice, testo min 91% della mediana | locale |
| `resa_375` | **26.490** misure · **0 problemi** | locale |
| Link interni / ancore | **0** rotti / **0** morte su 4.205 pagine | audit proprio (appendice) |
| Ultimo run | **66 richieste** totali, **0 errori veri** (solo ESPN in backoff, atteso) | `source_status.parquet` |
| Calibrazione | fit di **oggi** 15:39 UTC, λ×1,0394, 4.770 gare, `cal-momenti-1.1` | `calibration.parquet` |

## 2. Quantità dei contenuti (misurato sui Parquet + sito generato)

| Contenuto | Misura | Giudizio |
|---|---|---|
| Schede pre-partita | **66/66** gare in finestra −3h/+7gg (10/10/10/9/9/9/9 per lega) | 100%, parità esatta |
| Previsioni su gare in programma | **1.989/1.989** | 100% |
| Schede post-partita | **375/375** finite | 100% |
| Arbitro sulle 66 | nome 66/66, stats complete 38/66 (designazioni recenti) | fisiologico |
| Meteo / stadio / H2H sulle 66 | **66/66** su tutti | 100% |
| Formazioni / lineup sulle 66 | **65/66** (1 gara con `lineup_type` vuoto) | 1 buco, vedi §4.5 |
| Notizie | 3.383 righe, **128/132** squadre, 1.149 fresche (7 gg) su 122 squadre | ottimo; 10 squadre senza notizie recenti → coperte dai fatti di fallback |
| Accuratezza | **153** gare valutate, **72** col modello corrente (dichiarato in pagina) | campione onesto e crescente |
| Giocatori | 3.756 pagine; ITA1 445, ENG1 417, ESP1 459, GER1 365, FRA1 383, NED1 408, POR1 425 | proporzionale alle rose |
| Valore titolari sulle 66 | 14/66 (solo dove la distinta predetta ha valori) | fisiologico |
| `prossime.html` | 531.815 byte su tetto 1.800.000 (30%) | P2.7 non urgente |
| Sito live | 138 MB locali; repo `.git` 6,5 MB, `data/processed` 5,2 MB | sotto controllo |

## 3. Difetti veri trovati (piccoli, da correggere)

### 3.1 Footer: attribuzione delle fonti non veritiera

`base.html` dice «Dati: FotMob, ESPN, Understat, football-data.co.uk».
Misurato:

- **ESPN: 0 righe MAI in produzione** — nel repository non è mai esistita una
  tabella `espn_*` (403 cronico, confermato anche oggi: 90 run falliti
  consecutivi sulla classifica). Viene citato come fonte dati ma dati non ne ha
  mai dati.
- **Mancano** le fonti che dati ne danno davvero: Google News RSS (3.383 righe
  notizie), Open-Meteo (fallback meteo), ANSA/Sky Sport (feed diretti),
  football-datasets/mirror (storico modelli, citato come football-data.co.uk
  che è solo l'origine).

È un difetto di onestà, non di numeri: la riga va riscritta sulle fonti reali.
Attenzione: `verify_site` [35] lega le fonti dichiarate ai moduli veri
(`docs/38`) — va adeguata insieme.

### 3.2 `collect_news` ignora il filtro leghe per le squadre

`collect_news(store, keys=...)` usa `keys` solo nel ciclo ESPN (`leagues(keys)`),
ma le squadre vengono da **tutte** le `fixtures`. Quindi `fda daily ITA1`
raccoglie comunque le notizie delle 132 squadre (134 richieste invece di ~22).
Nessun danno in produzione (il daily gira sempre su tutte le leghe), ma il
comportamento è incoerente con `collect_league`. Fix: filtrare le squadre per
`league_id` quando `keys` è dato + test di regressione.

### 3.3 Commenti stali sulla raccolta notizie

- `collect.py` (`collect_news`): «Una o due richieste RSS per squadra»
  e `sources.yaml`: «Il tetto copre una richiesta per squadra» con riferimento
  a `docs/24` §3.5 (doppia edizione IT+locale). Oggi `editions_for()` restituisce
  **solo** `[EDIZIONE_IT]` (1 richiesta/squadra, regola lingua): il tetto 200
  copre 134 richieste reali con margine. I commenti descrivono un comportamento
  passato.
- `collect.py`: «Feed RSS diretti della stampa sportiva italiana (ANSA, Sky
  Sport, Sportmediaset)» — Sportmediaset è stato rimosso da
  `ITALIAN_DIRECT_FEEDS` (PR #82, feed 404). Resta solo nei commenti.

### 3.4 P2.4 — chiudibile: le 3 frasi-macchina non esistono più

`docs/19` §2.8 chiedeva la riscrittura di 3 frasi di `narrative()`; `docs/42` §4
misurava già 0 occorrenze ma chiedeva di rileggere la funzione prima di chiudere.
Riletta oggi (`analysis.py:4251+`): tutte e tre le frasi sono riscritte con
commento `P2.4` (frequenza naturale «su 100 partite così…», «punti in più/meno»
in parole, frase corrente per le assenze) e il grep sulle pagine di oggi dà
**0 occorrenze** dei 3 pattern. **P2.4 si dichiara chiusa** (verifica: codice +
`grep -o` su `site/partite/*.html`).

## 4. Decisioni per l'utente (non implementate senza via libera)

| # | Proposta | Origine | Effetto |
|---|---|---|---|
| D1 | **Watchdog di freschezza**: workflow schedulato che legge «aggiornato» dal sito live e apre una issue se è vecchio > N ore | `docs/49` §4 (proposto, non approvato), `docs/50` §6.2 | il blocco 28/9→5/10 (8 giorni di sito fermo) sarebbe stato visibile il primo giorno |
| D2 | **Gate bloccanti vs cosmetici**: un difetto di formato non deve più congelare commit dati + deploy | `docs/50` §6.3 | sito sempre fresco; rischio: pubblicare un refuso |
| D3 | **Budget giornaliero aggregato** delle richieste (oggi solo tetti per run: FotMob 600, notizie 200) | `docs/52` §3 | garanzia rigida di traffico; può degradare i dati se stretto |
| D4 | **Lighthouse con browser vero** (job CI con Chrome headless, es. settimanale su 3 pagine) | P2.8, `docs/19` §3.11 | punteggi reali di performance/accessibilità; oggi solo misura statica |

Nota su D1: un controllo *dentro* il daily non basta — se il daily è rosso non c'è
deploy e il sito resta vecchio comunque. Serve un controllo esterno che guardi il
sito pubblicato. Il workflow `diag-fetch-log.yml` dimostra che un workflow
aggiuntivo è fattibile; per la regola «PR ricca» (nuovi workflow fuori) andrebbe
in una PR separata dopo l'ok.

## 5. Cose verificate e chiuse (non riaprire senza nuove misure)

- **Tetto notizie 200**: con 1 richiesta/squadra il consumo a cache fredda è 134 —
  il tetto regge con margine. Le cache hit non consumano budget (`http.py`).
- **Sportmediaset in `news.parquet`** (125 righe dalla fonte `Sportmediaset`):
  arrivano via Google News come testata, non dal feed diretto rimosso. Corretto.
- **Laboratorio**: nessun candidato promuovibile (tutti gli IC del ΔRPS
  attraversano lo zero; `dc_elo_tilt` in produzione resta la scelta giusta).
  Dettaglio in `scripts/verdetto_lab.py`.
- **Calibrazione**: si ristima a ogni run sui dati passati (ultimo fit oggi).
- **Gap 27/9→7/10 in `source_status`**: è il fermo noto e già documentato
  (`docs/50`), non un buco nuovo.
- **`league_id` 937276 su NED1**: quirk noto di FotMob, la lega si risolve da
  `fixtures` (già gestito).
- **Sosta nazionali**: 0 gare oggi, 66 in finestra 9–14/10 — il sito gestisce
  correttamente lo stato vuoto («È pausa per le nazionali…»).

## 6. Migliorie di quantità proposte (dopo le decisioni)

1. **1 gara senza distinta** (§2, formazioni 65/66): identificare il match e
   verificare se la fonte l'ha pubblicata dopo il run (fisiologico) o se il
   parser la perde (difetto). Costo: un'analisi, zero codice se fisiologico.
2. **10 squadre senza notizie a 7 giorni**: misurare se la card di fallback
   («Vita del club» da dati propri) regge il confronto — audit mirato su quelle
   schede.
3. **Copertura Accuratezza per lega**: con 153 gare, verificare quante leghe
   hanno superato le ~30 gare per lettura stabile e dichiararlo in pagina.
4. **Storico xG (`dc_xg`)**: il candidato resta in attesa di accumulo dati
   (limite noto da `docs/19`).

## Appendice — come sono state prese le misure

- Parquet: `pandas` sui file di `data/processed/` al commit `aa760b9`.
- Sito: `fda build` locale + `verify_site.py` + `parita_schede.py` + `resa_375.py`.
- Link: script dedicato (risoluzione `..`, query `?v=` tolta, `href`+`src`):
  0 rotti su 4.205 pagine; ancore `id=` verificate una per una: 0 morte.
- P2.4: `grep -o` dei 3 pattern di `docs/19` §2.8 su `site/partite/*.html` → 0.
- Live: fetch HTTP della home Pages (07/10 17:40, sosta nazionali corretta).
- GitHub: `gh run list` (daily/lab/benchmark), `gh pr view 84`, `gh issue list`.

## 7. Esiti (stessa sessione, dopo le risposte dell'utente)

**Decisioni:** D1 **no** (niente watchdog); D2 **resta tutto bloccante** (l'utente
non aveva capito la domanda: spiegato con l'esempio del fermo 28/9–5/10 e
raccomandato di non cambiare — nessun intervento); D3 **nessun tetto
giornaliero** (chiarito l'equivoco: il fermo non fu causato dai limiti di GitHub —
cache 1,26/10 GB, repo 6,5 MB — ma dal refuso del §D2; restano i tetti per run);
D4 **niente Lighthouse** (raccomandato: sito statico già coperto dai gate statici).

**Lotto sicuro implementato** (tutto misurato, gate pieni in coda):

- §3.1: footer riscritto sulle fonti reali — «FotMob, Understat, Google News,
  Open-Meteo, ANSA/Sky Sport, football-data.co.uk (storico modelli)». ESPN tolto
  (0 righe mai in produzione, verificato: nessuna tabella `espn_*`, 0 notizie
  ESPN); ANSA/Sky aggiunti (62+50 righe). Nessun test fissava il testo;
  invariante [35] invariata (lega Info↔moduli, non il footer).
- §3.2: `collect_news` filtra le squadre per `keys` + test di regressione
  (prova di morso: fallisce senza il fix).
- §3.3: commenti aggiornati (edizione solo italiana, feed diretti senza
  Sportmediaset) in `collect.py` e nei fake dei test.
- §6.1: la gara senza distinta è Académico Viseu–Estoril (POR1, 10/10),
  scaricata oggi con `lineup_type` vuoto → la fonte non l'ha ancora pubblicata
  a 3 giorni dalla gara: **fisiologico**, nessun fix.
- §6.2: le 11 squadre senza notizie a 7 giorni sono la coda naturale
  dell'edizione solo italiana (mediana 8 righe/squadra; le big italiane hanno
  100–289 righe). La card di fallback regge (verificata su PSG–Le Mans:
  imbuto onesto + fatti «Da sapere» incrociati con l'infermeria). **Difetto vero
  trovato leggendola:** «2 i titoli più vecchi guardati» (17 schede) e
  «1 i titolo più vecchio guardato» (3 schede) — articolo vagante nel template,
  invisibile al gate perché l'imbuto vive nella card `id="notizie"` (esclusa dai
  controlli lingua) e «1» non era seguito direttamente dal nome. Fix in tre
  parti: (a) template senza «i»; (b) ramo AGREEMENT «N i + plurale» (misurato:
  17 prese, 0 falsi positivi su 4.205 pagine); (c) `class="imbuto"` sui 3
  paragrafi generati + parser che riammette `("sapere", "imbuto")` (precedente:
  `sapere`, audit 18/09). Il selettore di [20] accetta entrambe le forme.
  Regressione in `test_verify_scripts.py` + morso end-to-end su pagina reale.
- §6.3: gare valutate per lega — ITA 23, ENG 19, ESP 33, GER 20, FRA 20,
  NED 18, POR 20: solo LaLiga sopra le ~30 per lettura stabile. La pagina lo
  dichiara già: nessun intervento.

**Gate finali:** `pytest` **517 passed** (+2), `ruff` pulito, `fda build` exit 0
(441/2.364/7.496), `verify_site` **0 problemi · 159.573 controlli** ([20] gira
sulle 66), `parita_schede` nessuna differenza, `resa_375` 26.490 · 0 problemi.

## Prossimo passo

Una sola PR con questo lotto (regola «PR ricca») → merge dell'utente → controllo
del daily successivo. D1–D4 restano decisioni registrate: non riproporre senza
nuovi motivi.
