# 104 — Revisione totale del progetto e del sito: stato, rischi misurati e coda (2026-10-13)

Richiesta dell'utente: *«controlla vita morte e miracoli del progetto e del sito, vedi a che punto
siamo arrivati, se c'è qualcosa da fare, da rivedere, da migliorare. fai delle ricerche e studia
tutto»*. Questo documento è il risultato: **ogni numero è misurato in questa sessione** salvo dove
è indicata la fonte diversa.

## 0. Metodo (cosa è stato rifatto da zero)

- Storia completa recuperata (`git fetch --unshallow`): **713 commit**, primo commit 2026-09-05;
  branch di sessione allineato a `origin/main` (`17b46b3`).
- Ambiente ricreato (`.venv`), gate locali rifatti: `pytest`, `ruff`, `fda build`,
  `scripts/verify_site.py`, `scripts/parita_schede.py`, `scripts/resa_375.py`.
- Sito **appena costruito** dai Parquet del repo e servito in anteprima su `0.0.0.0:8000`.
- Sito **pubblicato** riletto dal vivo (`fetch_page` su `uamisjd.github.io/football-deep-analyzer`:
  home e `stato.html`).
- GitHub interrogato via `gh`: run dei workflow, issue, PR, cache Actions, artifact, dimensione repo.
- Misure del repository: `git count-objects`, `verify-pack`, mappa blob→percorso,
  byte scritti per commit dei dati (per file e per giorno).
- Ricerche web: limiti dei repository GitHub, tecniche di contenimento (`git filter-repo`,
  LFS, orphan branch), copertura italiana delle leghe estere (Eredivisie/Primeira).

## 1. Salute misurata oggi (13/10/2026, dai dati committati `17b46b3`)

| Cosa | Misura | Come |
|---|---|---|
| Test | **943 passed** (119,56 s) | `pytest -q` locale |
| Linter | **0 errori** (`All checks passed!`) | `ruff check .` |
| Build | **498 schede / 2.364 fixture / 7.602 giocatori** | `fda build` |
| Verifica numeri | **241.754 controlli · 0 problemi** (54 oracoli: 31 indipendenti, 20 misti, 3 specchi) | `scripts/verify_site.py` |
| Parità schede | **58 schede**, struttura identica (27 id), indice 16 voci; testo visibile min 31.876 · mediana 37.508 · max 41.641 | `scripts/parita_schede.py` |
| Resa 375 px | **28.728 misure · 0 problemi** | `scripts/resa_375.py` |
| Sito generato | **4.316 pagine HTML** · sitemap 4.315 URL · **498 schede partita** · 153 MB (partite 48, giocatori 103) | misura locale |
| Daily su `main` | ultimi **3 run successivi verdi** (14:31, 16:56, 17:15 UTC del 13/10); 5 rossi prima, chiusi da PR #110 | `gh run list` |
| Issue / PR | **0 aperte / 0 aperte** | `gh issue list`, `gh pr list` |
| Altri workflow | `lab` 12/10 · `benchmark` 03/10 · `understat-storico` 12/10 · `tests` 13/10 — tutti **success** | `gh run list` |
| Cache Actions | **4,57 GB in 30 voci** (limite free 10 GB/repo) | `gh api .../actions/caches` |
| Artifact Actions | 64 per **55 MB** (Pages 18 MB con scadenza 1 giorno) | `gh api .../actions/artifacts` |
| Sito pubblicato | home coerente: **0 partite oggi** (sosta nazionali), messaggio onesto «Oggi nessuna partita in programma», prossima giornata **venerdì 16/10/2026 con 5 partite**; `stato.html` con le righe delle fonti, le tabelle e l'imbuto dei fatti | `fetch_page` |

**Nessun numero pubblicato è stato smentito dai dati** in questa revisione: il gate che li ricalcola
(`verify_site`) è verde su tutta la build. Nessun nuovo difetto funzionale è emerso.

## 2. Stato dei contenuti (misurato sul sito appena costruito)

Copertura della rassegna stampa di «Vita del club» sulle **58 schede pre-partita**
(conteggio su `<li data-news-kind>` fuori dai blocchi «letture sul tema»; riserva a parte):

| Lega | Schede | Con voci esposte | Voci principali | Letture sul tema | In riserva |
|---|---|---|---|---|---|
| ITA1 | 10 | **10** | 44 | 14 | 10 |
| ESP1 | 10 | **7** | 12 | 3 | 0 |
| ENG1 | 10 | **5** | 8 | 1 | 0 |
| GER1 | 9 | **6** | 7 | 0 | 0 |
| FRA1 | 9 | **5** | 8 | 0 | 0 |
| NED1 | 9 | **0** | 0 | 0 | 0 |
| POR1 | 1 | **0** | 0 | 0 | 0 |
| **Totale** | **58** | **33 (56,9%)** | **79** | **18** | **10** |

- La misura replica esattamente la parità per lega di `docs/100` (33/58; ITA1 10/10, ESP1 7/10,
  ENG1 5/10, GER1 6/9, FRA1 5/9): il fix della PR #110 è **in produzione e stabile**.
- **NED1 e POR1 pubblicano zero voci** su 235 + 28 voci esaminate. L'imbuto dichiarato sulla
  pagina attribuisce le esclusioni NED1 a *servizio o cronaca* (~146), *fonte a bassa reputazione*
  (~56), *in un'altra lingua* (~46), *fuori finestra* (~45), *senza evento o analisi espliciti* (~16):
  è **disponibilità di stampa italiana**, non un difetto del filtro (conferma `docs/98` §5-6).
- Ricerca web di questa sessione (per non riaprire il tema a vuoto): la stampa italiana **copre le
  leghe estere** (Sky Sport Italia ha una sezione Eredivisie; Eurosport Italia, Diretta.it, Mediagol
  hanno pagine dedicate) **ma quasi solo i club grandi e gli eventi di lega**; per Heerenveen,
  Excelsior, Fortuna Sittard, Famalicão, AVS… non esiste copertura in italiano. Il buco è
  **strutturale di fonte**: non si ripara abbassando le soglie d'ingresso (si riempirebbe con
  contenuto non pertinente) — la card lo dichiara già, ed è la scelta coerente con `docs/00` §B.10.

## 3. Il rischio nuovo, misurato: la crescita del repository

**Oggi:** pack **722,85 MiB** (`git count-objects`; GitHub riporta ~712 MB).

**Il ritmo (misurato per blob, ultimi 30 giorni):**

| Finestra | Byte scritti dai commit dei dati | Media |
|---|---|---|
| oggi (13/10) | 17,6 MB | — |
| ultimi 7 giorni | 147,0 MB | 21,0 MB/giorno |
| ultimi 30 giorni | **743,8 MB** | **24,8 MB/giorno** |

- **155 commit dei dati in 30 giorni** (~5/giorno): la frequenza della pipeline moltiplica ogni
  fotografia dei Parquet.
- Da dove viene (30 giorni, per file): **news 338,2 MB (45%)** · **backtest 201,7 MB (27%)** ·
  **predictions 88,6 MB (12%)** · player_stats 31,3 · lineup 19,0 · shots 12,1 · team_stats 10,9 ·
  match_info 8,2 · tutti gli altri ~34 MB.
- Il blob più grande nella storia è **4,9 MB**: nessun file è vicino ai limiti per file
  (50 MiB avviso · 100 MiB blocco). Il costo sono le **versioni multiple**, non la dimensione.
- **Proiezione al ritmo attuale:** 1 GB intorno al **24 ottobre 2026** (~11 giorni);
  5 GB verso il **7 aprile 2027**. GitHub raccomanda < 1 GB e «fortemente» < 5 GB.
- **Cosa non è a rischio:** il run giornaliero fa un checkout **shallow** (`actions/checkout`,
  fetch-depth 1): non scarica la storia e non rallenta. Il costo è per lo spazio del repo/GitHub
  e per i cloni completi (nel sandbox: `--unshallow` di 723 MB in ~33 s, oggi accettabile).

### Opzioni di contenimento (con il numero accanto)

| # | Opzione | Effetto stimato | Costo / rischio |
|---|---|---|---|
| A | Committare i dati **una volta al giorno** invece di ~5 (es. solo il run delle 04:00) | da ~745 a **~145 MB/mese (−80%)** | si perdono le fotografie intermedie; la CI non ne ha bisogno (build e gate girano nello stesso run). **Attenzione:** `prospettico` è un registro **preregistrato** e il timestamp git fa parte della prova → va tenuto fuori dalla riduzione (pesa ~0,5 MB/mese) |
| B | Non versionare gli **snapshot derivati rigenerabili** (backtest, predictions, calibration, player_stats, lineup, shots, team_stats, match_info, events, momentum, season_sim*) | **−65/70%** | le sessioni dell'agente non possono più verificare quei dati dal repo (oggi lo fanno: è il modo in cui questa revisione ha misurato); `stato.html` non cambia (è costruito in-run) |
| C | **Compattazione periodica** della storia con `git filter-repo` (mensile o quindicinale) | riporta il repo a **~50–100 MB** a ogni passata | riscrittura di `main` con force-push (nessun collaboratore esterno oggi; la CI clona shallow), script da mantenere e provare |
| D | Git LFS sui Parquet | sposta i byte fuori dalla storia | **1 GB di storage e 1 GB/mese di banda** gratis: insufficiente da sola (consumo attuale ~745 MB/mese) |
| E | Migliore compressione/forma dei Parquet | guadagno piccolo | i Parquet sono già compressi: la delta-compressione git non guadagna quasi nulla — non risolve il problema di fondo |

**Raccomandazione:** **A** subito (una riga nel workflow, reversibile) e **C** come manutenzione
periodica se si vuole restare sotto 1 GB senza perdere la disponibilità dei dati nel repo.

> **Aggiornamento dello stesso giorno:** l'utente ha scelto l'**opzione A**, che è stata
> implementata e provata in [`docs/105`](105_una_fotografia_al_giorno_2026-10-13.md)
> (`scripts/fotografia_dati.py`, 20 test, modifica a `daily.yml`, input `forza_commit`).
> La **C** resta preparabile a parte, senza force push, quando servirà.

## 4. Coda aggiornata (cosa c'è da fare)

1. **Ultime 2 sezioni della scheda partita** (`docs/101` §4, metodo misura → correzione → invariante):
   - **«Previsione del modello ensemble»** (`#previsione` + `#scomposizione` + `#laboratorio` +
     `#fascia-storica` + `#posizione-lega` + `#primo-gol`; invarianti `[8] [10] [11] [12] [15] [16]
     [17] [46] [47]`).
   - **«Verifica approfondita»** (`#verifica`: `#probabilita` + `#gol-totali`; invarianti `[8] [9]`).
   *(«Precedenti» è stata chiusa ieri con `docs/103`; le altre nove sezioni sono già revisionate.)*
2. **Copertura stampa NED1/POR1** (misurata oggi: 0/10) e debolezza relativa di ENG1/GER1/FRA1
   (5–6/10). Il buco è di **fonte**. Opzioni oneste: (a) provare un feed italiano **di lega**
   (Sky Sport/Eurosport, sezioni Eredivisie e Primeira) con attribuzione **di lega** dichiarata e
   pertinenza minima; (b) lasciare la dichiarazione di vuoto (già presente). Da decidere.
3. **Decisioni utente ancora aperte:** StatsBomb (non fattibile come chiesto: La Liga solo per
   stagioni vecchie, Eredivisie/Primeira assenti; alternativa Understat già eseguita, 8.908 gare
   2021–2025) e **clima** (card rule-based; sentiment rinviato per assenza di testo sufficiente).
4. **`dc_xg`:** criterio di promozione **non superato** (ΔRPS −0,000393, IC 95% [−0,001109;
   +0,000332], migliore in 3/7 leghe — `docs/93`). Resta in attesa di accumulo; il test
   **prospettico** γ 1,12 è avviato (3.856 righe, **0 risultati** ancora valutabili).
5. **Igiene documentale (piccola, ma va corretta):** l'indice in `docs/BRIEFING_NUOVA_SESSIONE.md` §6
   e in `README.md` dichiara «92 file `.md` / 83 documenti numerati», mentre oggi sono **114 file .md
   e 104 documenti numerati**; il numero **58 è duplicato** (collisione nota, `docs/63` §8) e il
   «09» non è mai esistito.
6. **Rischi minori monitorati:** cache Actions 4,57 GB su 10 GB (crescita lenta, LRU di GitHub);
   `prossime.html` 484,5 kB su un tetto dichiarato di 1,8 MB (non urgente).

## 5. Cosa è stato ricercato (fonti usate)

- **GitHub Docs — *About large files on GitHub* / *Repository limits***: file > 50 MiB avviso,
  > 100 MiB bloccati; repo **ideale < 1 GB**, < 5 GB «fortemente raccomandato»; guida ~10 GB per
  il `.git` su disco; push max 2 GB; Git LFS 1 GB gratis (storage e banda).
  <https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github>
- **Contenimento delle storie grandi**: `git filter-repo` è lo strumento raccomandato dal progetto
  Git (alternativa a `git filter-branch`/BFG) + `git-sizer` per diagnosticare; trunk di cloni
  shallow/sparse per la CI. (Documentazione Git/GitLab e guida operativa DZone/Ryan Gibson.)
- **Stampa italiana per le leghe estere**: Sky Sport Italia (sezione Eredivisie), Eurosport Italia,
  Diretta.it, Mediagol — coprono i **club maggiori** e gli eventi di lega, non i club minori di
  NED1/POR1 (evidenza per il punto 2 della coda).
- Restano valide le ricerche già in repo (`docs/00` §«Ricerca modelli», `docs/01`-`02`, `docs/12`),
  che non vengono duplicate qui.

## 6. Giudizio complessivo

- Il progetto è **sano e maturo**: pipeline automatica 5×/giorno con gate **bloccanti** prima del
  commit e del deploy, zero issue aperte, sito pubblicato coerente coi dati (241.754 controlli),
  parità di contenuti fra le 7 leghe garantita da un gate dedicato.
- I due lavori che spostano davvero l'ago sono: (1) **finire le ultime 2 sezioni** della scheda
  partita (chiudono il ciclo di revisione iniziato a ottobre); (2) **decidere la politica di
  crescita del repo**, prima che superi 1 GB (~25 ottobre al ritmo attuale).
- Il buco di copertura stampa su NED1/POR1 è **di fonte**, non di codice: dichiararlo è corretto;
  riempirlo con soglie più basse sarebbe un peggioramento (`docs/00` §B.10).

## 7. Prossimo passo

Tre decisioni da chiedere all'utente (nessuna presa al posto suo):
(a) politica del repository (A / C / A+C / nessuna azione);
(b) se procedere con le ultime 2 sezioni della scheda partita;
(c) se provare un feed italiano di lega per NED1/POR1 o lasciare la dichiarazione di vuoto.
