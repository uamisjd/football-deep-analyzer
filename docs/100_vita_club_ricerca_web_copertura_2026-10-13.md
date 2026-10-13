# 100 — «Vita del club» (`#notizie`): ricerca web, disambiguazione dei club e copertura sulle 7 leghe (2026-10-13)

## 1. Problema e obiettivo

Dall'audit completo delle 493 schede partita del sito (`58` pre-partita e `435` finite) è emerso che la card **«Vita del club»** (`#notizie`), pur disponendo di `6.257` articoli raccolti in `data/processed/news.parquet` (132/132 squadre coperte su 14 giorni) e di `285` fatti verificati nel blocco «Dati di contesto della partita» (`58/58` schede pre-partita), esponeva articoli di stampa soltanto su **6 schede su 58 (`10,3%`)** e **7 lati squadra su 116 (`6,0%`)**, lasciando 52 schede su 58 (`89,7%`) in stato compatto (`news_quiet`) e con il blocco «Dati di contesto della partita» chiuso dentro una tendina `<details>`.

L'obiettivo richiesto dall'utente è che la sezione funzioni su tutte le partite e svolga in modo corretto la ricerca sul web e la selezione di informazioni utili inerenti alla partita o alle squadre.

---

## 2. Cause radice individuate e misurate

L'analisi dell'imbuto tra `collect_news` (`src/fda/sources/news.py`), `team_news` (`src/fda/site/analysis.py`) e `club_signal` (`src/fda/site/club_signals.py`) ha isolato cinque colli di bottiglia indipendenti:

1. **Disallineamento tra finestra di ritenzione (`14` giorni) e finestra di lettura (`7` giorni) durante la sosta per le nazionali**:
   - `NEWS_RETENTION_DAYS = 14` in `src/fda/collect.py` conserva 14 giorni di rassegna stampa per ciascun club, ma `MatchAnalysis.NEWS_WINDOW_DAYS = 7` tagliava a `kickoff - 7 giorni`.
   - Poiché le 58 gare in programma si giocano tra il `2026-10-16` e il `2026-10-20` (dopo la sosta nazionali) e la raccolta è del `2026-10-12`, la finestra effettiva `[kickoff - 7d, as_of]` si riduceva a 1–3 giorni (fino a 9 ore per i posticipi del lunedì), scartando come «vecchi oltre la finestra» l'82% degli articoli raccolti nei 14 giorni precedenti (`969` voci esaminate su `5.321` disponibili entro 14 giorni dal calcio d'inizio).
2. **Disambiguazione difettosa dei nomi club in `team_tokens`, `_club_tokens` e `altra_squadra` (`src/fda/site/analysis.py`)**:
   - `team_tokens(team_name)` usava solo i token $\ge 4$ caratteri del nome ufficiale FotMob (es. `"Brighton"` per `Brighton`, `"Gladbach"` per `M'gladbach`), ignorando gli esonimi e gli alias italiani di `soggetto_tokens(team_name)` (`"lipsia"`, `"colonia"`, `"stoccarda"`, `"friburgo"`, `"magonza"`, `"nizza"`, `"marsiglia"`, `" Siviglia"`, `"maiorka"`): gli articoli della stampa italiana che citavano l'esonimo venivano scartati per assenza di soggetto o attribuiti ad altra squadra.
   - `altra_squadra(title)` riconosceva il club corrente solo se il suo token aveva `len(t) >= 5`, scartando tutti i club con nome di 3–4 lettere (`Lens`, `Ajax`, `Como`, `Pisa`, `Roma`, `PSG`, `PSV`, `Hull`) ogni volta che il titolo citava un terzo club. Per `"roma"` è stata mantenuta la guardia sul complemento di stato/moto a luogo `\ba\s+roma\b`.
   - `_club_tokens` includeva prefissi condivisi fra più club (`"real"`, `"borussia"`, `"olympique"`, `"sporting"`, `"manchester"`, `"madrid"`, `"paris"`, `"united"`, `"city"`, `"union"`) e sostantivi comuni italiani (`"fortuna"`, `"santa"`, `"clara"`, `"ahead"`, `"eagles"`, `"saint"`), facendo scartare come `altre` le notizie di `Paris FC`, `Real Sociedad`, `Borussia M'gladbach`, `Man City` o qualsiasi titolo contenente la parola italiana *«fortuna»*.
3. **Query di ricerca web (`ITALIAN_SEARCH_NAMES`) e attribuzione multi-club nei feed RSS diretti (`src/fda/sources/news.py`)**:
   - 17 club europei (`Brighton`, `Wolverhampton`, `Mallorca`, `Osasuna`, `Alavés`, `Oviedo`, `Rennes`, `Brest`, `Nice`, `Strasbourg`, `Lens`, `Paris FC`, `Heidenheim`, `St. Pauli`, `Kaiserslautern`, `Famalicao`, `Vitoria SC`, `AVS`) non avevano la variante italiana/estesa in `ITALIAN_SEARCH_NAMES` per Google News RSS.
   - `parse_espn_news` e `parse_direct_sports_rss` interrompevano la scansione al primo club trovato (`break`), attribuendo gli articoli che menzionavano entrambe le squadre di una sfida ad un solo club.
4. **Copertura lessicale di `club_signals.py` (`src/fda/site/club_signals.py`)**:
   - `EVENT_RULES` conteneva il typo regex `ricorsi?` (che intercettava `ricors` e `ricorsi` ma non il singolare `ricorso`), e non copriva i segnali lessicali di infortunio/rientro dall'infermeria, rinnovi contrattuali ufficiali e analisi tecnico-tattiche presenti nella stampa sportiva italiana sui 7 campionati.
5. **Visibilità immediata dei «Dati di contesto della partita» (`src/fda/site/templates/match.html`)**:
   - Il blocco `<details class="news-context">` (che espone su 58/58 schede pre-partita i fatti verificati su squalifiche, ballottaggi, strisce, riposo, arbitro e meteo) era chiuso per impostazione predefinita, lasciando le schede prive di articoli di stampa visivamente ridotte a una sola riga di riepilogo.

---

## 3. Interventi effettuati

1. **`src/fda/site/analysis.py` e `src/fda/site/club_news_checks.py`**:
   - Allineato `MatchAnalysis.NEWS_WINDOW_DAYS = 14` a `NEWS_RETENTION_DAYS = 14` (e aggiornato l'oracolo indipendente `club_news_checks.py` a `kickoff - pd.Timedelta(days=14)`).
   - Esteso `MatchAnalysis.team_tokens` con `soggetto_tokens(team_name)`, esclusi i prefissi condivisi e i nomi comuni da `self._club_tokens`, e corretta la guardia sui token di 3–4 lettere in `altra_squadra`.
   - Introdotta la cache per `team_player_names(team_id)` su `MatchAnalysis` per evitare la scansione ripetuta delle `401.770` righe di `player_stats.parquet`.
2. **`src/fda/sources/news.py`**:
   - Estesa `ITALIAN_SEARCH_NAMES` con le varianti italiane/complete dei club europei senza alterare le query dei club già mappati.
   - Rimossa l'interruzione al primo club (`break`) in `parse_espn_news` e `parse_direct_sports_rss` (con deduplicazione per `tid`), così un articolo che cita due club viene attribuito a entrambi.
3. **`src/fda/site/club_signals.py`**:
   - Corretto `ricors[oi]` in `EVENT_RULES` ed estesi i pattern club-agnostici per assetto societario, panchina, provvedimenti, infortuni/rientri, contratti/rinnovi e analisi tecnica, mantenendo `31/31` (`0` falsi positivi) sul campione annotato `tests/fixtures/vita_editorial_review_2026-10-12.json` e tutti i controlli negativi (`SERVICE_TITLE` e `OFF_SCOPE`).
4. **`src/fda/site/templates/match.html`**:
   - Impostato `<details class="news-context" open>` affinché i fatti verificati della partita siano immediatamente visibili in «Vita del club» su tutte le 58 schede pre-partita.

---

## 4. Risultati misurati prima e dopo sulle 58 schede pre-partita (`sitemap.xml`)

| Campionato | Schede pre-partita | Schede con stampa (prima) | Schede con stampa (dopo) | Lati con stampa (prima) | Lati con stampa (dopo) | Articoli pubblicati (prima → dopo) | Schede con dati di contesto aperti (dopo) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Serie A (`ITA1`)** | 10 | 5 / 10 (`50%`) | **10 / 10 (`100%`)** | 6 / 20 (`30%`) | **17 / 20 (`85%`)** | 11 → **34** | **10 / 10** (`50` fatti) |
| **LaLiga (`ESP1`)** | 10 | 1 / 10 (`10%`) | **7 / 10 (`70%`)** | 1 / 20 (`5%`) | **10 / 20 (`50%`)** | 1 → **11** | **10 / 10** (`57` fatti) |
| **Premier League (`ENG1`)** | 10 | 0 / 10 (`0%`) | **5 / 10 (`50%`)** | 0 / 20 (`0%`) | **6 / 20 (`30%`)** | 0 → **8** | **10 / 10** (`53` fatti) |
| **Bundesliga (`GER1`)** | 9 | 0 / 9 (`0%`) | **6 / 9 (`67%`)** | 0 / 18 (`0%`) | **6 / 18 (`33%`)** | 0 → **7** | **9 / 9** (`31` fatti) |
| **Ligue 1 (`FRA1`)** | 9 | 0 / 9 (`0%`) | **5 / 9 (`56%`)** | 0 / 18 (`0%`) | **6 / 18 (`33%`)** | 0 → **7** | **9 / 9** (`42` fatti) |
| **Eredivisie (`NED1`)** | 9 | 0 / 9 (`0%`) | **0 / 9 (`0%`)** | 0 / 18 (`0%`) | **0 / 18 (`0%`)** | 0 → **0** | **9 / 9** (`45` fatti) |
| **Liga Portugal (`POR1`)** | 1 | 0 / 1 (`0%`) | **0 / 1 (`0%`)** | 0 / 2 (`0%`) | **0 / 2 (`0%`)** | 0 → **0** | **1 / 1** (`7` fatti) |
| **Totale (7 leghe)** | **58** | **6 / 58 (`10,3%`)** | **33 / 58 (`56,9%`)** | **7 / 116 (`6,0%`)** | **45 / 116 (`38,8%`)** | **12 → 67** | **58 / 58 (`100%`, `285` fatti)** |

Su tutte le schede pre-partita presenti in `site/partite` (`scripts/audit_vita_editoriale.py`), i lati con segnalazioni di stampa salgono da **7** a **49** (`75` principali + `4` di riserva + `22` sul tema = **101 segnalazioni**, contro le `13` precedenti).

---

## 5. Verifiche eseguite

- `.venv/bin/pytest -q`: **`932 passed`** (`0` errori).
- `.venv/bin/ruff check`: **`All checks passed!`** (`0` errori).
- `.venv/bin/fda build` + `.venv/bin/python scripts/verify_site.py`: **`nessun problema · 238546 controlli numerici superati`** (`[20] card «Vita del club» riconciliate: 58 pagine; 1148 controlli indipendenti su periodo/conti/fonte`).
- `.venv/bin/python scripts/audit_vita_editoriale.py`: **49 lati con segnalazioni**, `31/31` sul campione annotato di sviluppo.
- `.venv/bin/python scripts/audit_fonti.py`: **`nessun difetto bloccante: ogni squadra dei dati ha una query (mappata o nome secco) e almeno una notizia in 14 giorni`**.
