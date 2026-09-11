# BRIEFING NUOVA SESSIONE — leggi questo per primo

> ⚠️ **Policy merge (decisione utente, 2026-09-08):** il merge delle PR lo esegue **SEMPRE l'utente, MAI l'agente**. L'agente apre la PR quando serve (sezione D di `00_regole_di_lavoro.md`), monitora i check e avvisa con la frase fissa **"👉 Tutto verde: è il momento di fare Merge (PR #N)."** — poi aspetta l'utente, senza eseguire il merge.

> **Ultimo aggiornamento:** 2026-09-12 · **Scopo:** rendere ogni nuovo agente (nuova sessione Arena) operativo in 2 minuti e senza ripetere verifiche già fatte. Questo file è la **porta d'ingresso**; in coda c'è l'elenco completo dei documenti del progetto.
> Se la chat è nuova, rileggilo sempre; se è la continuazione di una sessione già avviata su questo repo, può bastare `docs/STATO.md` + le regole `00`.

---

## 0. Cos'è il progetto (in una riga)

**football-deep-analyzer** = portale personale, gratuito e automatico di **analisi calcistica profonda**: per ogni partita produce previsioni probabilistiche calibrate (xG, Dixon-Coles, Elo, ensemble), indisponibili, arbitro, meteo, contesto, quote-vs-modello e report **in italiano** pre/post partita. Tutto gira su GitHub Actions (cron) e viene pubblicato su GitHub Pages; i dati sono versionati nel repo (Parquet + DuckDB).

## 1. Architettura e flusso (niente server, costo zero)

```
GitHub Actions (cron 5x/giorno) → collect (FotMob/ESPN/Understat/mirror) →
  Parquet in data/processed + DuckDB → predict (DC + Elo + xG) →
  build (sito statico in site/) → commit dati → deploy GitHub Pages
```

- Il comando che fa tutto è `fda daily` = `collect → predict → build`.
- Il sito è **statico**: `index.html` (Oggi), `prossime.html`, `risultati.html`, `partite/<id>.html` (tutte le finite di stagione, archivio), `giocatori/` (hub + tabellone per lega + schede giocatore con percentili/radar, fase 3), `accuratezza.html` (RPS/Brier reali), `stagione.html` (proiezioni), `stato.html` (stato fonti). Report in italiano generati dai template `analysis.py` → `narrative`.
- Il pacchetto è installabile: `pip install -e ".[dev]"`; entry point CLI `fda` (typer).

## 2. Stato attuale del lavoro (sintesi — dettaglio sempre in `docs/STATO.md`)

- **Fase 0–7b CONCLUSA E VALIDATA DAL VIVO** (PR #1–#9 mergiate): scaffolding, client FotMob, client ESPN+Understat, storage+collect, modelli (Dixon-Coles+Elo, backtest RPS 0,212), sito+workflow+Pages, run dal vivo OK, resilienza, storico NED1/POR1 da mirror dedicato **confermato in produzione** (run `34232722943` del 2026-09-08: NED1 11 / POR1 11 predizioni, `n_train=960`, commit dati `6a31d39`).
- **PR #9 (2026-09-08) porta su `main`**: policy «il merge lo esegue SEMPRE l'utente» (sez. D + avviso in cima qui), Accuratezza con Δ vs naive/calibrazione/RPS per gara, cartina dei tiri SVG nei post-partita, card Momentum (barre + marker gol), ultimi precedenti reali V/N/P, **italianizzazione completa** (ora italiana ovunque, virgole decimali, meteo e rientri tradotti), script `scripts/verify_ned_por.py`. Commit di merge in `git log` (HEAD di `main`).
- **Accuratezza oggi**: 20 gare valutate su 7 leghe (incluse le prime NED1/POR1), RPS **0,205** vs naive 0,239 (il modello batte la base in ogni lega).
- **PR #16 (2026-09-08 sera, in attesa di merge utente)**: verifica completa sito/progetto + fix P0/P1 — formato arbitro/recupero, attribuzione fonti, ESPN standings→AVVISO, **meteo previsionale Open-Meteo** (fallback sui futuri, `future_days=7`), formazione probabile pulita (niente indisponibili tra i titolari), playoff Liga Portugal. Suite **63 passed**, ruff F pulito.
- **Branch di lavoro**: ogni sessione Arena ha il proprio branch `arena/...` (indicato nel messaggio di inizio sessione); mai lavorare su `main`.
- **Ultimo aggiornamento STATO.md**: 2026-09-12 — sessione `arena/01a092ab` (**laboratorio analitico** sulle schede: matrice DC, scontro tattico, corsa xG, qualità tiri, WP in-play). PR #1–#21 mergiate.

## 3. Prossimi passi (in ordine — da `docs/STATO.md`)

> 🎯 **Direttiva utente (2026-09-08, prioritaria su tutto)**: «tutti i contenuti delle partite devono essere accurati, precisi, profondi e di qualità» — le schede di **tutte** le partite ancora da giocare (tutte le 7 leghe) devono essere **piene di contenuti e servizi**, nessuna lega di serie B. **Raggiunta** (verificato 2026-09-08): classifica FotMob 7/7, xG stagione completo NED1/POR1, meteo con fallback Open-Meteo, audit 0 «mancante» su 73 partite.

1. ~~**Parità di profondità delle schede partita**~~ ✅ (PR #10–#15 + rifiniture in PR #16): classifica FotMob primaria (ESPN 403 isolato), xG/xPTS stagione NED1/POR1 da FotMob, segnaposti onesti per arbitro/meteo/formazioni, card «Confronto di stagione» su tutte le leghe, meteo previsionale Open-Meteo. Contenuti pre/post già presenti ovunque (previsione completa, formazione, indisponibili, forma, riposo, H2H, momentum, cartina tiri).
2. ~~**Monte Carlo stagione**~~ ✅ (fase 2): pagina **`stagione.html` «Proiezioni»** con punti attesi, media posizione, % titolo/top-4/retrocessione per le 7 leghe (simulazione DC+Elo, regole retrocessione per lega incluse i playoff).
3. **Seguire Accuratezza** via via che le gare previste si risolvono: le valutazioni si calcolano da sole nei run daily; rifinire la pagina se emergono problemi (es. calibrazione per lega). Con il backfill esteso (2026-09-09) le gare valutabili cresceranno più in fretta. **Laboratorio analitico (2026-09-12)** ✅ offline: matrice, scontro, corsa xG, qualità tiri, WP in-play — `docs/08_laboratorio_analitico.md`.
4. ~~**Verifica dal vivo del meteo Open-Meteo**~~ ✅ chiusa 2026-09-09 (passo attivo, 0 richieste perché FotMob copre già i futuri ≤7 gg).
5. **Pulizia ruff** (opzionale): 254 segnalazioni pre-esistenti `E501`/`E741` su `main` (CI esegue solo pytest, non blocca) — un turno con `ruff --fix` + revisione.
6. ~~**Card post-partita «Migliori in campo» per squadra**~~ ✅ (PR #17).
7. ~~**Card pre-partita «Fatti rilevanti» (insights FotMob)**~~ ✅ (sessione `arena/01a08630`): traduzione a template, max 3, 0 inglese, 7/7 leghe.
8. Poi la roadmap (`01` §8): ~~**B5** SofaScore~~ ✅ rimosso 2026-09-09 (codice mai collegato), ~~**fase 3** schede giocatore~~ ✅ 2026-09-09 (`arena/01a0864d`: hub + tabelloni per lega + 3.457 schede con percentili lega+ruolo, radar SVG, log partite — progetto `docs/07_fase3_giocatori.md`); resta opzionale la **fase 3b** arricchimento anagrafica da `playerData` (contratto, trofei, infortuni storici; ~3.300 giocatori / TTL 168h ≈ 80 richieste/run). Poi **fase 4** quote The Odds API (serve `ODDS_API_KEY`, non prioritario), **fase 5** notifiche Telegram. Nota: i **diffidati** non sono implementati — FotMob non li espone nei dati raccolti (verificato 2026-09-08).

## 4. Cosa fare appena entri (checklist rapida)

1. `git status`, `git branch`, `git log --oneline -10` → capire dov'è il lavoro (deve essere su `arena/...`, mai su `main`).
2. Leggi `docs/STATO.md` (il checkpoint vero) e `docs/00_regole_di_lavoro.md`.
3. Verifica il branch di lavoro del repo (questa sessione è fissata al branch indicato qui sopra).
4. Non rifare verifiche di rete già fatte: è tutto annotato in `03` (§"Verifiche tecniche") e in `STATO.md`.
5. Lavora a **un obiettivo piccolo per turno**, committa subito, aggiorna `STATO.md` a ogni turno.
6. Indica **da solo** quando è il momento di Create PR / Merge (regola D in `00`). Non aspettare che te lo chiedano.

## 5. Paletti di qualità (nuovi — riassunto, dettaglio in `00` sez. B)

Massima accuratezza, precisione, profondità e qualità su ogni deliverable: numeri sempre **verificabili e misurati**; distinguere in modo esplicito *verificato dal vivo* / *verificato offline* / *presunto*; non dichiarare "fatto" ciò che è solo "in attesa"; test verdi + ruff pulito prima delle PR; documenti in italiano brevi e linkati. **Direttiva utente (2026-09-08)**: le **schede di ogni partita** devono essere piene di contenuti accurati, precisi, profondi e di qualità — **parità completa tra le 7 leghe**, nessuna lega trattata "di serie B" (v. sez. 3, punto 1).

## 6. Dove sta il lavoro — albero essenziale

| Percorso | Contenuto |
|---|---|
| `docs/STATO.md` | **Checkpoint**: fatto / in corso / prossimo passo / decisioni aperte. Aggiornato ogni turno. |
| `docs/00_regole_di_lavoro.md` | Regole anti-blocco, paletti di qualità, quando fare PR/merge. |
| `docs/01_studio_fattibilita.md` | Studio completo: fonti (con verdetto), architettura, modelli, rischi, roadmap (fasi 0→5), appendice con esempio reale di profondità. |
| `docs/02_catalogo_fonti_dati.md` | Catalogo endpoint gratuiti verificati, limiti, id utili, schema minimo. |
| `docs/03_decisioni_e_funzionamento.md` | Decisioni utente (7 leghe, uso personale, quote) + spiegazione automazione + verifiche tecniche salvate. |
| `docs/07_fase3_giocatori.md` | Progetto fase 3 schede giocatore: dati misurati, metodologia, decisioni. |
| `docs/08_laboratorio_analitico.md` | Matrice DC, scontro tattico, corsa xG, qualità tiri, WP in-play. |
| `docs/BRIEFING_NUOVA_SESSIONE.md` | Questo file. |
| `src/fda/` | Codice: `cli.py`, `config.py`, `collect.py`, `store.py`, `http.py`, `teams.py`, `sources/` (fotmob, espn, understat, history), `models/` (predict, season_sim), `site/` (build, analysis, **advanced**, **players**, audit, fmt, templates). |
| `config/leagues.yaml` | Le 7 leghe + coppe; aggiungere una lega = aggiungere una voce qui. |
| `.github/workflows/daily.yml` | Cron 5x/giorno + dispatch manuale → `fda daily`, commit dati, Pages. |
| `tests/` | 20+ test offline (parser su JSON campione, config, modelli, site, store/collect). |
| `data/processed/` | Parquet versionati + `fda.duckdb`. |

## 7. Limitazioni note (per non ri-verificare a vuoto)

- **Dal sandbox dell'agente** sono raggiungibili `github.com` e `api.github.com` (e **PyPI**: `pip install -e ".[dev]"` funziona). FotMob, Understat, ESPN, `football-data.co.uk`, il mirror `raw.githubusercontent.com` e i **blob Azure degli artifact Actions** sono bloccati → le verifiche "dal vivo" si fanno sui commit dati (`git show origin/main:data/...`, vedi `scripts/verify_ned_por.py`) o in GitHub Actions/PC utente; i parser sono coperti da test offline.
- **Cron GitHub molto dilazionati** (fino a ~5 h; gli slot possono saltare del tutto). **Dispatch manuale**: il token dell'agente dà 403, ma **dall'utente via UI GitHub funziona** (Actions → daily → Run workflow su `main`): è la scorciatoia quando serve un run subito (usata con successo il 2026-09-08).
- **football-data.co.uk diretto** irraggiungibile dagli IP cloud → mirror datahub (5 leghe) + mirror dedicato per NED1/POR1 (campo `datahub_base` in `leagues.yaml`), confermato funzionante in produzione.
- **ESPN standings**: 403 cronico e isolato (loggato in `source_status`, non blocca il run; scoreboard/classifiche ESPN restano ok dove raggiungibili).
- **Preview del sito dal sandbox**: dopo `fda build` (scrive in `site/`, gitignored) si serve con `python3 -m http.server 3000 --bind 0.0.0.0 --directory site` (via start_process) → l'utente vede il sito modificato nel browser prima del merge.
- La sezione **quote** usa The Odds API solo se è impostato il secret `ODDS_API_KEY` (opzionale).
- I **diffidati** non sono implementati: FotMob non li espone nei dati raccolti (ruoli lineup: starter/sub/unavailable/coach — verificato 2026-09-08).

## 8. Decisioni aperte / prossime scelte che spettano all'utente

- Niente di bloccante al momento (Telegram bot, protezione accesso e collettore locale sono fasi successive).
- Da confermare col tempo: soglia/forma del monitoraggio Accuratezza (es. quanti match servono per una valutazione stabile per lega), e quando introdurre le coppe UCL/UEL per l'analisi dedicata (oggi solo calendario per la congestione).

## Direttive utente persistenti (2026-09-08)
- Le quote bookmaker non sono un requisito e non vanno prioritarizzate né mostrate come contenuto delle schede.
- Obiettivo prioritario: nessun dato realmente mancante nelle schede; ogni partita deve avere la quantità corretta di contenuti, accurati, profondi e comparabili tra tutte le 7 leghe.
- È richiesto un sistema che distingua tra dato assente, dato non ancora pubblicato dalla fonte e dato recuperato da fallback.
- Prima di ogni modifica importante l’agente deve verificare ricerche web/GitHub e progetti open source riutilizzabili, annotando qui i risultati utili per le sessioni successive.
- Suggerimenti e decisioni dell’utente vanno registrati in questo documento e in `docs/STATO.md`, così restano disponibili agli agenti futuri.

### Ricerca laboratorio analitico 2026-09-12
- **Matrice DC**: penaltyblog `create_dixon_coles_grid` richiede λ>0 e ρ nei bound; implementata griglia propria (clamp ρ, λ≈0 ammessi, coda rinormalizzata) per non far cadere le pagine.
- **xG race / WP in-play**: Understat e FiveThirtyEight SPI come riferimento metodologico; nessuna dipendenza nuova (SVG lato server). ρ non si scala al tempo parziale → Poisson indipendente sul residuo, dichiarato in `info.html`.
- **Open/set play**: `team_stats.expected_goals_open_play` / `_set_play` coprono **235/235** finite, **7/7 leghe** (misurato sui dati `7ab51fe`) → parità senza Understat. `shots.situation` (8 valori reali) tradotto; mai inglese a schermo.
- **PPDA/deep**: Understat 292 righe / 96 squadre; riga assente se manca (come PPDA già in scheda).

### Ricerca schede giocatore (fase 3) 2026-09-09 sera
- **Metodologia radar/percentili**: prassi mplsoccer (`Radar` con `rank(pct=True)*100`, stesso principio del tutorial «Visualizing Striker Profiles»; `lower_is_better` per le stat capovolte) e DataMB (percentili «League and Position per 90», 7 metriche/ruolo). FBref: normalizzazione per-90 + soglie minime di minuti contro le distorsioni da campioni piccoli. Implementato tutto in SVG lato server (nessuna dipendenza nuova). Dettagli e misure in `docs/07_fase3_giocatori.md`.
- **`playerData?id=`** (FotMob, doc `pseudo-r/Public-FotMob-API` `docs/endpoints/players.md`, VERIFIED): anagrafica, `recentMatches` con rating, `careerHistory`; il catalogo `02` aggiunge `mainLeague.stats`, infortuni, valore, trofei. Non usato nella fase 3 (il nucleo è coperto da `player_stats`/`lineup` già raccolti, parità 7/7); candidato naturale per la fase 3b. Client già pronto (`player_raw()`, TTL 168h in `sources.yaml`).
- **Scoperta utile**: `player_stats` usa la semantica «chiave assente = 0 eventi» (verificato: `expected_goals` mai a 0,00 sui 1.272 che ce l'hanno) → le aggregazioni coalescono a 0 senza inventare nulla. `match_info.league_id` per NED1 riporta l'id stagione 937276 (non il canonico 57): la lega si risolve sempre da `fixtures`.
- **Gap i18n trovato e chiuso**: `unavailability_type` («injury»/«suspension», 897+39 righe reali) non era tradotto nelle schede partita → `unavailability_it()` in `analysis.py`, riusata dalle schede giocatore.

### Ricerca insights FotMob 2026-09-09
- Catalogo misurato su 1274 righe / 211 match (`insights.parquet`): template inglesi fissi, non NL libero. Squadra: scored N in last K, haven't scored, haven't lost in N, haven't won in N attempts, lost/won last N, haven't kept a clean sheet, H2H (haven't lost to / won previous N / not drawn / drawn last N). Giocatore: top scorer, most big chances, most shots on target/match, ranked in saves / big chances.
- Nessun traduttore OSS riusabile per questi template (Sportmonks Match Facts è a pagamento e strutturato). Scelta: mappa regex + drop dei non tradotti (mai inglese a schermo). Hype «most X in the competition» escluso di proposito.

### Ricerca fonti/progetti 2026-09-08
- `probberechts/soccerdata`: scraper multi-fonte (ESPN, FBref, Football-Data, SofaScore, Understat, WhoScored, ClubElo); utile come riferimento per fallback e normalizzazione, non da importare alla cieca.
- `oseymour/ScraperFC`: copre FBref, SofaScore, Transfermarkt, Understat e ClubElo; utile soprattutto per pattern di rate limiting/cache.
- `tunjayoff/sofascore_scraper`: pipeline SofaScore con calendario, dettagli, statistiche, formazioni, incidenti e H2H; candidato per studiare gli endpoint di riserva.
- `statsbomb/open-data`: eventi dettagliati e xG per competizioni selezionate, utile per validazione storica, non per copertura live delle 7 leghe.
- Conclusione: nessuna fonte gratuita unica garantisce ogni campo; mantenere FotMob primaria, aggiungere fallback mirati e conservare fonte/timestamp/confidenza per ogni contenuto.
