# 109 — Revisione totale (vita, morte e miracoli) — 15 ottobre 2026

Richiesta dell'utente: *«controlla vita morte e miracoli del progetto e del sito, vedi a che punto
siamo arrivati, se c'è qualcosa da fare, da rivedere, da migliorare. fai delle ricerche e studia
tutto. c'è una pr aperta controlla»*.

A differenza di `docs/107` (che ha **citato** i gate misurati da altre sessioni), questo giro
**rimisura tutto in locale da zero**: ambiente ricreato, suite completa, Ruff, build,
verificatore, parità, resa. Il sito pubblico e GitHub sono verificati **dal vivo**.

## 0. Come si legge questo documento

| Classe | Cosa significa qui |
|---|---|
| **verificato dal vivo** | letto su GitHub (`gh`) o sulle pagine di CalcioMetro, 15/10/2026 |
| **verificato in locale** | misurato in questo turno nella sandbox (`.venv` ricreato), sui Parquet del clone e sulle pagine costruite |
| **citato** | numero di un altro documento, non rifatto qui |
| **stimato** | proiezione dichiarata come tale |

Dati delle misure locali: Parquet committati su `main` (`11186b6`, registro prospettico delle
10:30 UTC del 15/10). Il sito è stato costruito in `site/` con `fda build` in questo turno.

## 1. Cos'è, in tre righe

**CalcioMetro** (`uamisjd/football-deep-analyzer`): portale statico **gratuito**, senza secret e
senza servizi a pagamento, di analisi profonda su **7 campionati** (ITA1, ENG1, ESP1, GER1, FRA1,
NED1, POR1). Una pipeline (`fda daily`: collect → calibrate → predict → backtest →
mercati-monitor → simulate → build) gira su GitHub Actions 5 volte al giorno e pubblica su
GitHub Pages. Per ogni partita: previsione 1X2 Dixon-Coles + Elo registrata **prima** del calcio
d'inizio, matrice dei risultati, gol attesi, forma, indisponibili, arbitro, meteo, mercato,
clima del club, stampa, più schede giocatore con percentili e radar.

Sito live: <https://uamisjd.github.io/football-deep-analyzer/>

## 2. Dove siamo arrivati (15/10/2026, pomeriggio)

| Voce | Stato | Classe |
|---|---|---|
| `main` | `11186b6` (solo registro prospettico; ultimo commit di contenuto `eaeb8f1`, merge `7366ae5`) | verificato `gh` |
| PR aperte (al momento delle misure) | **1** — #123, solo documenti (`+15` righe, 2 file), `MERGEABLE`/`clean`, `test`+`site`+`browser` **SUCCESS**. La PR **#124** nasce da questa sessione, dopo le misure | verificato `gh` |
| Issue aperte | **0** | verificato `gh` |
| Daily | **7 successi consecutivi** (dal 14/10 13:03 al 15/10 10:18); ultimi 3 giorni: 0 rossi | verificato `gh` |
| Deploy Pages | ultimo `7366ae5`, 15/10 10:30:45 UTC, job `run`/`deploy`/`notify` tutti `success` | verificato `gh` |
| Home | «0 partite oggi» (sosta nazionali), prossima **ven 16/10 con 5 gare** — coerente coi Parquet (5 gare il 16/10, 24 il 17/10 e il 18/10) | verificato live + locale |
| Suite test | **1.034 passed** in 141,95 s all'ingresso; **1.046** dopo i 12 test di `scripts/crescita_repo.py` aggiunti in questo giro | verificato in locale |
| Ruff / `pip check` | **0** errori / nessun conflitto | verificato in locale |
| Test nuovi di questo giro | `scripts/crescita_repo.py` + `tests/test_crescita_repo.py` (**12** test, 0 errori Ruff) | verificato in locale |
| Build | **499 schede** · 2.364 fixture · **7.626 giocatori** | verificato in locale |
| `verify_site.py` | **242.987 controlli · 0 problemi** (55 oracoli dichiarati: 32 indipendenti, 20 misti, 3 specchi) | verificato in locale |
| Parità schede | nessuna differenza su **59** schede pre-partita | verificato in locale |
| Resa 375 px | **28.597 misure · 0 problemi** | verificato in locale |
| Sito pubblicato | 4.344 file · 157 MB · 4.328 URL in `sitemap.xml` (limite Pages consigliato: 1 GB) | verificato in locale |
| Dimensione repo GitHub | **750.155 KB ≈ 732,6 MiB** | verificato API |
| Fotografia dei dati | 1 completa al giorno (13/10 20:13 `27639e6` 4,6 MiB; 14/10 22:08 `7d80ab9` 5,3 MiB); oggi attesa al run ≥20 UTC | verificato `git log` |
| Registro prospettico | 1.928 partite registrate, **5 valutate**, ΔRPS γ1,12 **+0,0059** (IC −0,0052…+0,0164), 1 lega su 4 → **nessuna promozione** | verificato in locale |

Confronto con i gate di `docs/107` (citati): i controlli del verificatore passano da 242.503 a
**242.987**, i giocatori da 7.600 a **7.626**, i test da 1.033 a **1.034** d'ingresso e a
**1.046** col contributo di questo giro. La resa a 375 px misura **28.597** elementi invece di
28.766: la differenza (−179) è coerente con le tendine `#verifica` vuote tolte da `docs/108`
(211 schede), ma **non è stata riconciliata elemento per elemento** — resta un numero, non una
spiegazione.

## 3. Il ciclo di revisione delle schede è **chiuso**

`docs/101` §4 lasciava **tre blocchi** in coda. Oggi risultano tutti chiusi:

1. **«Precedenti»** → `docs/103` (13/10), con fallback dichiarato sulle gare senza h2h (`docs/62`).
2. **«Previsione ensemble»** (`#previsione`, scomposizione, laboratorio, fascia, posizione, primo gol).
3. **«Verifica approfondita»** (matrice + gol totali).

I blocchi 2 e 3 sono chiusi da `docs/108`, fuso stamattina con la **PR #122**.

Verifica indipendente fatta qui sulle 499 schede costruite:

- **59/59** schede pre-partita hanno **tutte e 8** le sezioni della previsione
  (`previsione`, `scomposizione`, `laboratorio`, `fascia-storica`, `posizione-lega`, `primo-gol`,
  `probabilita`, `gol-totali`). Copertura per lega identica a `docs/108`: ITA1 10, ENG1 10,
  ESP1 11, GER1 9, FRA1 9, NED1 9, POR1 1.
- **288 schede** hanno la sezione `#verifica` **e** la voce d'indice: **0 disallineate** su 499.
  Le 211 finite senza previsione registrata non hanno più la tendina vuota (il difetto misurato
  e corretto in `docs/108`); sulla pagina live `partite/5749640.html` la voce non c'è e la card
  resta coerente. L'invariante **[33]** regge.
- **0** schede pre-partita con «Arbitro da definire»: la copertura arbitro è completa sulle 59.
- **Stampa in lingua originale**: blocco attivo su **9/9** NED1 e **1/1** POR1, **44 titoli**
  citati in lingua con fonte, data e lingua; sulle altre 5 leghe 0, per progetto (`docs/106`).
- **Archivio notizie**: 9.872 righe, di cui 3.073 `it`, 484 `pt`, 444 `nl`. La voce di coda di
  `docs/107` («persistenza nl/pt da confermare al daily serale») è **verificata e chiusa**.

## 4. Crescita del repository: la politica A è misurata (prima volta)

`docs/105` (opzione A: **una fotografia dei dati al giorno**) attendeva la verifica sul campo.
Le misure di oggi:

| Misura | Valore | Classe |
|---|---|---|
| Fotografie complete per giorno dal 14/10 | **1** (13/10 20:13 e 14/10 22:08); i run intermedi salvano **solo** `prospettico.parquet` | verificato `git log` |
| Costo di una fotografia completa | 4,6 MiB (13/10) e 5,3 MiB (14/10) di blob scritti | verificato in locale |
| Byte scritti al giorno (tutti i commit di `main`) | 12/10 **33,2 MB** · 13/10 **38,8 MB** · 14/10 **10,8 MB** · 15/10 (parziale) **1,3 MB** | verificato in locale |
| Baseline pre-politica | 24,8 MB/giorno (media 30 giorni, `docs/105`) | citato |
| Dimensione GitHub | 14/10 **744.203 KB** → 15/10 **750.155 KB** = **+5,8 MiB in 24 h** | verificato API |
| Da dove viene il peso della storia | 911,3 MiB di blob raggiungibili da `main`: **`data/processed` 798,6 MiB (87,6%)**, `docs` 33,4, resto 79,3 | verificato in locale |
| Ramo non fusi (`arena/*`) | 83 rami remoti, 18 non fusi: pesano **3,2 MiB** di blob in più. Cancellarli **non** riduce il repo | verificato in locale |
| Proiezione a 1 GB (raccomandato da GitHub) | **~50 giorni, inizio dicembre 2026** *(stimato sul ritmo misurato di 5,8 MiB/giorno)* | stimato |

**Verdetto sulla politica A:** funziona. Il costo giornaliero dei dati scende da ~24,8 MB a
~5,8 MiB misurati (**−77%**), il sito resta aggiornato 5 volte al giorno e nessuna funzione è
cambiata. La stima di `docs/105` («metà dicembre») è confermata dalla misura, con un anticipo di
qualche giorno.

**Il muro non è quello che sembra.** GitHub raccomanda <1 GB e «fortemente raccomandato» <5 GB, ma
non blocca: 1 GB è una soglia di cortesia (eventuale email), il blocco vero è a **100 MB per
file** (il nostro blob più grande in storia resta 4,9 MB, `docs/105`) e il tetto duro è 100 GB.
A 5,8 MiB/giorno i 5 GB arriverebbero **dopo il 2028**.

Opzioni, con i numeri di oggi — **decisione dell'utente, non presa qui**:

| Opzione | Effetto misurato/stimato | Costo |
|---|---|---|
| **A (in vigore)** | +5,8 MiB/giorno (~1,8 GB/anno) | nessuno |
| **B — fotografia completa 1 volta a settimana** (registro sempre a ogni run) | ~1,4 MB/giorno (registro ~0,6 + foto 5,3/7) → ~0,5 GB/anno: **1 GB oltre il 2027** | l'archivio perde 6 fotografie su 7; nessuna funzione del sito/pipeline le legge (`docs/105` §1) |
| **C — riscrittura della storia** (`git filter-repo`, preparata su una copia, senza force push alla cieca) | la parte non-dati è 112,7 MiB di blob: il repo tornerebbe a poche decine di MB | riscrive tutti gli SHA, richiede force push e la ricreazione della storia; da fare solo se deciso |
| **D — fotografie fuori da Git** (Release asset: non contano nel repo; artifact Actions gratuiti sui repo pubblici) | crescita dei dati nel repo ~0 | l'archivio non è più dentro un clone; le misure «dal Parquet committato» andrebbero rifatte sui release |

## 5. Altre verifiche di questo turno

- **Puntualità del cron (giorni completi 8–14/10):** 29 slot su 35 coperti; ritardi fino a ~3,5 h
  su un singolo slot; i buchi sono compensati dai **run da push** (5 al giorno in più nei giorni
  con merge). L'ultimo rosso è del 14/10 09:19 (oracolo [50], poi corretto): **da lì in poi 7/7
  verdi**. Conferma quanto già scritto: il cron è nominale, non una garanzia di puntualità — e il
  sistema non dipende dai singoli slot.
- **Test prospettico γ 1,12:** registro completo (1.928 partite = tutto il calendario rimasto),
  ma **solo 5 gare finite** da valutare — la sosta delle nazionali ha fermato il campionato dal
  13/10. ΔRPS +0,0059 (favorevole alla produzione, ma dentro il rumore: IC a cavallo dello zero),
  1 lega su 4. La soglia del protocollo è 200 gare: **si accumula dal 16/10**, ossia ~15-20 gare al
  giorno; 200 gare ≈ **inizio novembre**. Nessuna promozione, come deve essere.
- **Issue automatica:** 0 aperte; l'ultima (#114) è stata chiusa **dal daily verde**, non a mano.
- **Coda di `docs/107`** (5 voci): (1) fotografia serale → **verificata**; (2) revisione B.10 di
  previsione/verifica → **fatta** con `docs/108` e riverificata qui; (3) −80% pack → **misurato
  −77%**, da riconfermare su una settimana piena; (4) nessuna promozione modello → **confermato**;
  (5) decisioni aperte storiche → invariate.

## 6. Ricerca esterna: dove sta il progetto rispetto al mondo

- **Modelli — il nostro RPS è nella banda giusta.** La letteratura recente colloca un
  Dixon-Coles ben costruito a **RPS 0,177–0,199** e il mercato a **~0,19**
  ([JRSS-C 2026, modelli dinamici bayesiani](https://academic.oup.com/jrsssc/advance-article/doi/10.1093/jrsssc/qlag032/8704597);
  [TableTalk, modello 0,199 vs mercato 0,192](https://github.com/umarjaved204/TableTalk)).
  CalcioMetro pubblica **0,1987** sul backtest di 5.960 gare e **0,1990** sulle 218 gare
  valutate in stagione: è **il risultato atteso** per questa famiglia di modelli, ~0,007 sopra il
  mercato, cioè il «gap residuo» che la letteratura considera normale. Non c'è margine facile da
  prendere senza quote (che il progetto ha deciso di non pubblicare) o senza dati nuovi: la
  scelta di **non** promuovere le varianti in coda è coerente con questa misura.
- **Understat — fonte viva ma fragile.** Non esiste un'API ufficiale; l'accesso è scraping, la
  politica robots del sito disincentiva la raccolta automatica e la community documenta blocchi
  403/429 frequenti
  ([comparativa API 2026](https://www.thestatsapi.com/blog/free-football-api-alternatives);
  [scheda dello scraper con la nota sulla robots policy](https://apify.com/datascraperes/understat-football-data)).
  Il progetto lo tratta già come **riserva** (la classifica primaria è FotMob, `stato.html`) e usa
  xG Understat solo dove copre la lega: la dipendenza è già nella posizione giusta, ma resta un
  rischio dichiarato, non eliminabile a costo zero.
- **Limiti GitHub (verificati oggi).** Repo: <1 GB raccomandato, <5 GB fortemente raccomandato,
  **100 MB per singolo file**, tetto duro 100 GB
  ([GitHub Community](https://github.com/orgs/community/discussions/188694)). Release: ogni file
  <2 GB e **gli asset di release non contano nella dimensione del repo**
  ([filesize.org](https://filesize.org/limits/github/)). Pages: sito pubblicato <1 GB, banda
  ~100 GB/mese e 10 build/ora come tetti morbidi (non si applicano al percorso con Actions)
  ([panoramica limiti Pages](https://supadrop.host/blog/github-pages-limits/)). Il nostro sito
  pesa **157 MB** e il file più grande della storia del repo è **4,9 MB**: siamo lontani da ogni
  limite tecnico.

## 7. Cosa resta da fare (coda onesta, in ordine di utilità)

1. **Stasera (osservazione, non codice):** il daily ≥20 UTC deve produrre la **fotografia
   completa** di oggi e il commit del registro. Se manca, diagnosticare; nessun dispatch doppio.
2. **Decisione dell'utente sulla crescita** (§4): restare sulla politica A, passare a una
   fotografia completa a settimana (B), preparare la riscrittura della storia (C) o spostare le
   fotografie fuori da Git (D). Con i numeri di oggi, **A va bene ancora per ~50 giorni** prima
   dei 1 GB, e C è l'unica che riporta il repo sotto i 100 MB.
3. **Misura a 7 giorni della politica A** (al 20/10): un comando solo, ora che la misura è
   riproducibile da `scripts/crescita_repo.py` (aggiunto in questo giro, con 12 test) —
   `python -m scripts.crescita_repo --days 10 --da 2026-10-14 --ritmo 3 --repo uamisjd/football-deep-analyzer`.
   Oggi risponde: ritmo **5,7 MiB/giorno** (ultimi 2 giorni con commit), **~51 giorni** ai
   1 GB raccomandati. Chiude la stima di `docs/105` §4 con un dato misurabile.
4. **Pulizia dei rami remoti:** 65 dei 83 rami `arena/*` sono già fusi in `main`; 18 no. Non è
   una questione di peso (3,2 MiB), è ordine operativo. Va fatta **dall'utente** o su sua
   richiesta esplicita: qui non si toccano rami di altre sessioni.
5. **Modelli:** continuare a raccogliere il test prospettico (soglia 200 gare, ~inizio novembre);
   nessuna promozione senza griglia preregistrata e IC interamente negativo.
6. **Igiene `docs/`:** 123 file `.md` (110 documenti numerati: manca il `09`, il `58` è doppio).
   Aggiornati in questo giro i conteggi dell'indice in `README` (erano fermi a 121/108) e la cima
   del briefing.
7. **Copertura NED1/POR1 su «Vita del club»:** mitigata dalla stampa in lingua originale (9/9 e
   1/1 sulle pre); il buco di **fonte italiana** resta e non si tappa abbassando le soglie.

## 8. Cosa NON fare adesso

Rewrite del modello (l'RPS è già nella banda della letteratura), LFS, `git filter-repo` senza una
decisione esplicita e una prova su copia, nuove sezioni decorative, merge autonomi, riaprire
issue chiuse, inseguire GitHub Pages a 5 build/giorno (già ok coi limiti).

## 9. Verdetto

Il progetto è **vivo, in produzione e in salute**, non un prototipo: 499 schede partita, 4.344
file pubblicati, ~243.000 controlli automatici per build, 1.046 test, 7 daily verdi di fila dopo
l'incidente dell'oracolo [50]. Il ciclo di revisione delle schede partita — iniziato a inizio
ottobre — è **completo**: tutte le sezioni sono state riviste con misura prima/dopo e protette da
invarianti. La crescita del repository è **sotto controllo** e per la prima volta **misurata**:
−77% di byte scritti, una fotografia al giorno, nessun file vicino ai limiti di GitHub.

La coda utile è **corta**: una decisione dell'utente sulla politica di crescita, una misura a 7
giorni, la pulizia dei rami, e pazienza sul test prospettico. **Non serve un rifacimento.**

## Prossimo passo

Il daily serale ≥20 UTC (fotografia completa di oggi). In parallelo: la PR **#123** (solo
documenti, check verdi) attende il merge, e questa sessione porta su `main` — con una PR
documentale — questo `docs/109` e l'aggiornamento dei conteggi di indice in `README` e briefing.
