# Football Deep Analyzer — Studio di fattibilità e piano

> Data dello studio: **5 settembre 2026** · Vincolo principale: **costo zero** (dati, hosting, strumenti)
> Tutte le fonti citate come "verificate" sono state interrogate dal vivo in questa data; le altre sono documentate dalle rispettive pagine ufficiali/GitHub (vedi `02_catalogo_fonti_dati.md`).

---

## 0. In una pagina

**Obiettivo.** Un portale personale, gratuito, che per ogni partita (Serie A prima di tutto, poi le altre grandi leghe e le coppe europee) produca un'analisi profonda e aggiornata: forza reale delle squadre (xG, rating), previsioni probabilistiche calibrate, disponibilità giocatori (infortuni, squalifiche, diffidati), forma, contesto (arbitro, meteo, calendario, viaggi, H2H), giocatori chiave, quote di mercato a confronto con il modello, notizie — con un report pre-partita e uno post-partita generati automaticamente.

**Cosa ho scoperto di rilevante.**

| Scoperta | Conseguenza per il progetto |
|---|---|
| **FotMob** espone gratis (endpoint non documentati `/api/data/*`, funzionanti oggi) dati di livello Opta: xG e xGOT **per singolo tiro** con coordinate, momentum, rating giocatori, formazioni con valore di mercato, **indisponibili con data di rientro prevista**, statistiche dell'arbitro, stadio, affluenza, H2H, articoli pre/post gara anche in italiano | È la fonte primaria "profonda". Va trattata come fragile (non ufficiale): cache aggressiva, fallback su ESPN + Understat |
| **ESPN** ha API JSON pubbliche stabili da anni (scoreboard, boxscore con 30 statistiche di squadra, arbitri, classifiche, calendario) — verificate | Fonte "spina dorsale" affidabile per calendario/risultati/statistiche base |
| **Understat** copre Serie A 2026/27 con xG, xGA, xPTS, PPDA, deep completions; ha spostato i dati su endpoint JSON (soccerdata li supporta da gennaio 2026) | Seconda opinione di xG (modello diverso da Opta) → più robustezza |
| **Transfermarkt** blocca gli IP dei runner GitHub Actions da metà luglio 2026: il dataset open `transfermarkt-datasets` è **congelato al 6 luglio 2026** | Valori di mercato e trasferimenti: storico dal dataset congelato; per l'aggiornato si usa FotMob (valore di mercato, scadenza contratto) o un collettore locale (IP residenziale) |
| **API-Football gratis** = 100 richieste/giorno e **senza la stagione corrente** (solo 2021–2023) | Inutile per un portale "aggiornato" → scartata |
| **football-data.org gratis** = 12 competizioni, 10 req/min, punteggi ritardati, nessun dato giocatori | Utile solo come ridondanza per calendario/classifiche |
| **Sofascore** risponde 403 anche a client "educati"; **FBref** è dietro Cloudflare e mette in "prigione" per un giorno chi supera 10 req/min; **WhoScored** è protetto da Incapsula | Non basare nulla di critico su queste tre; FBref solo per snapshot settimanali lenti, o niente |
| **Bzzoiro Sports Data (BSD)**: API gratuita (7.500 req/giorno dal 17/8/2026) con quote consenso multi-bookmaker, infortuni, formazioni ufficiali 1h prima, xG per tiro, profili allenatori, previsioni Dixon-Coles | Ottimo integratore, ma è un progetto di una sola persona affiliato a un casinò online → usarla come fonte *secondaria*, mai unica |
| **StatsBomb Open Data** (eventi completi, incl. Serie A 2015/16, Champions League, Mondiali) | Perfetto per **addestrare/validare** un modello xG proprio e per le visualizzazioni evento; non serve al "live" |
| Le librerie **penaltyblog** (Dixon-Coles, Poisson bivariato, Bayesiani, rating Elo/Pi/Massey, quote implicite, backtest, xT), **soccerdata** (scraper unificati), **mplsoccer** (grafici campo) sono mature e mantenute (ultimi commit agosto 2026) | Non reinventare i modelli: si compone, si valida e si adatta |

**Raccomandazione architetturale.** *Pipeline Python su GitHub Actions (cron) → dati versionati nel repo/Parquet → sito statico (GitHub Pages o Cloudflare Pages) con grafici interattivi.* Zero server, zero costi, sempre acceso, deploy automatico. Per le poche fonti che bloccano i datacenter, un **collettore locale opzionale** sul tuo PC (IP residenziale) che pubblica sul repo.

**Cosa NON è realistico gratis (e va detto subito).** Dati tracking/posizionali live, feed ufficiali Opta/StatsBomb in tempo reale, quote di tutti i bookmaker in tempo reale, formazioni ufficiali *garantite* prima delle 60'. Tutto il resto — con un livello di profondità paragonabile ai siti di analisi a pagamento — è ottenibile combinando le fonti sopra.

---

## 1. Cosa significa "analisi molto accurata e profonda" — la mappa dei contenuti

Ho tradotto la richiesta in un inventario concreto. Per ogni voce: **cosa** si mostra, **da dove** arriva, **come** si calcola. (F = FotMob, E = ESPN, U = Understat, FD = football-data.co.uk, CE = ClubElo, SB = StatsBomb open, TM = transfermarkt-datasets, B = BSD, O = The Odds API / odds-api.io, OM = Open-Meteo, N = Google News RSS)

### 1.1 Livello partita (pre-gara)

| Contenuto | Fonte | Metodo |
|---|---|---|
| Probabilità 1 / X / 2 calibrate | FD + U + F (storico gol e xG) | Dixon-Coles con decadimento temporale (penaltyblog), ensemble con modello xG-based e Elo; calibrazione verificata con RPS/Brier su 5+ stagioni |
| Matrice risultati esatti, Over/Under 0.5–4.5, BTTS, handicap asiatico, doppia chance | modello | Griglia di probabilità dal modello (penaltyblog `FootballProbabilityGrid`) |
| Gol attesi per squadra nella partita (λ casa/trasferta) | modello | Componenti attacco/difesa + fattore campo + correzioni contestuali |
| Confronto modello ↔ mercato ("valore", margine bookmaker rimosso) | O / B + modello | Probabilità implicite con rimozione dell'overround (penaltyblog `implied`, metodi Shin/potenza) |
| Forma recente (5/10 gare): punti, gol, **xG e xGA rolling**, xGD trend | F, U | Medie mobili, grafici a linee con soglie di lega |
| Forza: Elo (ClubElo + Elo proprio), Pi-rating, xPTS di stagione | CE, U, modello | Storico Elo per squadra dal 2000 |
| Casa/trasferta split, rendimento contro top-6/bottom-6 | E, F | Aggregazioni |
| **Indisponibili**: infortunati (con rientro previsto), squalificati, dubbi; % del valore rosa assente | F (+B) | Endpoint formazione/squadra FotMob (`unavailable` con `expectedReturn`) |
| **Diffidati** (a rischio squalifica alla prossima ammonizione) | F, E (eventi cartellini) | Conteggio gialli stagionali + regole Lega (soglia 5ª ammonizione, poi soglie successive) |
| Formazione probabile e ufficiale (quando esce) | F, B | FotMob pubblica la formazione ufficiale ~1h prima; probabile = ultima formazione + indisponibili |
| Arbitro: gare, gialli/rossi e falli per partita, rigori, media lega | F | Endpoint matchDetails → `infoBox.Referee.stats` (verificato) |
| Contesto: giorni di riposo, partite negli ultimi 15 giorni (coppe incluse), distanza di viaggio, orario, stadio, affluenza attesa | E, F | Calendari multi-competizione; geodati stadio (FotMob dà lat/long) |
| Meteo al calcio d'inizio (temperatura, pioggia %, vento) | OM | Open-Meteo, gratis senza chiave (verificato) |
| Head-to-head: ultimi 10 incontri, tendenze (gol, pareggi, cartellini) | F, FD | FotMob `h2h` (verificato) + storico CSV dal 1993 |
| Allenatori: profilo, modulo preferito, rendimento | B, F | BSD `managers`, FotMob formazioni |
| Rassegna notizie (ultime 48h, italiano) | N | Google News RSS per squadra (verificato; uso personale) |
| **Report pre-partita in italiano** generato automaticamente | tutto | Template testuale basato sui numeri (opzionale: rifinitura con LLM gratuito) |

### 1.2 Livello partita (live / post-gara)

| Contenuto | Fonte | Metodo |
|---|---|---|
| Live score, eventi, statistiche in corso | E, F | Polling ogni 1–2 min nei giorni gara (limite: si accetta ritardo ~1') |
| Mappa dei tiri con xG/xGOT per tiro, tipo azione, parte del corpo, posizione | F | `shotmap` (coordinate x,y, xG, xGOT, situazione, `isFromInsideBox`) — verificato |
| Grafico "xG race" (cumulativo per minuto) e momentum (xT) | F | `momentum` + shotmap |
| Statistiche complete (possesso, passaggi, big chances, duelli, pressing, corner, legni…) per periodo | F, E | matchDetails `stats.Periods` (1° tempo, 2° tempo, totale) |
| Prestazioni giocatori: rating, xG, xA, tocchi in area, dribbling, duelli, recuperi | F | `playerStats` (verificato) |
| "Prevenzione gol" del portiere (xGOT subito − gol subiti) | F | Derivato |
| Valutazione: la partita è andata "come da modello"? Errore di previsione, aggiornamento rating | modello | Log delle previsioni → metriche di calibrazione mostrate pubblicamente (onestà) |
| Report post-partita in italiano | tutto | Template |

### 1.3 Livello squadra (pagina squadra)

- Tabella xG di stagione: G, GA, xG, xGA, npxG, xGD, **xPTS vs punti reali** (fortuna/sfortuna), PPDA/OPPDA (pressing), deep completions (U, verificato con dati 2026/27).
- Andamento Elo dal 2000 (CE) e rating Dixon-Coles attacco/difesa nel tempo.
- Profilo stile: possesso, passaggi lunghi %, cross, tiri da fuori %, xG su palla inattiva vs azione manovrata (F `xG set play` / `xG open play`, verificato).
- Rosa: età media titolari, valore di mercato titolari (F, verificato `totalStarterMarketValue`), scadenze contratto (F `playerData.contractEnd`), storico valori (TM congelato).
- Infermeria e squalifiche aggiornate; giocatori più utilizzati; minuti per ruolo.
- Calendario futuro con difficoltà (Elo avversari) e congestione.
- Trasferimenti (F `transfers`, TM storico).

### 1.4 Livello giocatore

- Scheda: ruolo/i, piede, altezza, età, contratto, valore, infortunio in corso e rientro, trofei (F `playerData`, verificato).
- Stagione: rating medio, xG/xA per 90, gol/assist, minuti, cartellini; ultime partite con rating.
- Confronto giocatori (radar/pizza chart con percentili di lega) — mplsoccer.
- Storico stagioni precedenti (U per Big 5 dal 2014).

### 1.5 Livello lega

- Classifica reale vs classifica xPTS; grafico "punti vs xG differenziale".
- Proiezione fine stagione via simulazione Monte Carlo (10.000 stagioni): % scudetto, % Champions, % retrocessione.
- Classifiche speciali: pressing, palle inattive, portieri, arbitri (severità), fair play.
- Mercato: valori rosa per squadra.

### 1.6 Trasversali (le cose che "servono" anche se non richieste)

1. **Health monitor delle fonti**: pagina che mostra per ogni fonte l'ultimo aggiornamento riuscito e gli errori → si sa sempre quanto sono freschi i dati.
2. **Log delle previsioni e pagina "Quanto siamo bravi"**: accuratezza, Brier/RPS, confronto con il mercato. Senza questo, "accuratezza" è solo una parola.
3. **Riconciliazione entità**: mappa dei nomi squadre/giocatori fra fonti (es. "Internazionale"/"Inter"/"Inter Milan"). soccerdata ha già una tabella `TEAMNAME_REPLACEMENTS` riutilizzabile.
4. **Notifiche** (gratis, bot Telegram): formazioni ufficiali uscite, nuovo infortunio in una squadra seguita, partita "di valore" secondo il modello.
5. **Fusi orari e date**: tutto in UTC nel dato, mostrato in ora italiana.
6. **Cache e rispetto dei limiti**: ogni fonte ha un budget richieste/ora configurato; retry con backoff; niente scraping aggressivo.
7. **Attribuzione e licenze** (vedi §6).
8. **Interfaccia in italiano, mobile-first**, con condivisione immagini (shot map, xG race) per social.

---

## 2. Fonti dati: verdetto sintetico

Dettagli tecnici, endpoint e limiti nel `02_catalogo_fonti_dati.md`. Qui il giudizio.

| Fonte | Costo | Profondità | Affidabilità/rischio | Ruolo nel progetto |
|---|---|---|---|---|
| **FotMob** (non ufficiale) | 0 | ★★★★★ | Media: endpoint non documentati, cambiati già una volta (nel 2024 richiedevano header `x-mas`; oggi `/api/data/*` risponde senza) | **Primaria** per profondità (xG per tiro, infortuni, rating, arbitro, valori) |
| **ESPN** (non ufficiale) | 0 | ★★★☆☆ | Alta (stabile da anni, JSON pulito) | **Spina dorsale**: calendario, risultati, boxscore, classifiche |
| **Understat** | 0 | ★★★★☆ (xG, xPTS, PPDA; Big 5 + Russia dal 2014) | Media: ha cambiato formato a dic. 2025; possibile blocco IP datacenter | **Seconda opinione xG**, storico 12 stagioni |
| **football-data.co.uk** | 0 | ★★★☆☆ (risultati, tiri, corner, cartellini, **quote di chiusura** dal 1993) | Alta (CSV; datahub.io lo aggiorna ogni giorno via GitHub Actions) | **Backtest** e quote storiche |
| **ClubElo** | 0 | ★★☆☆☆ (Elo dal 2000) | Alta (CSV API) | Rating di forza a lungo termine |
| **StatsBomb Open Data** | 0 | ★★★★★ (eventi) | Alta (GitHub) | **Addestramento xG proprio**, demo visualizzazioni |
| **transfermarkt-datasets** | 0 | ★★★★☆ | **Congelato al 6/7/2026** | Storico valori/trasferimenti/formazioni |
| **BSD (Bzzoiro)** | 0 (7.500 req/g) | ★★★★☆ | Media-bassa (progetto individuale, affiliazioni betting) | Integratore: quote consenso, allenatori, arbitri, infortuni; **mai unica fonte** |
| **The Odds API** | 0 (500 crediti/mese) | quote 1X2/totali di ~15–20 bookmaker | Alta | Snapshot quote pre-gara 1–2 volte/giorno per la Serie A |
| **odds-api.io** | 0 (500 req/g, 2 bookmaker) | basso | Media | Alternativa/ridondanza quote |
| **Open-Meteo** | 0 | meteo orario | Alta | Meteo allo stadio |
| **Google News RSS** | 0 | titoli/link | Alta (solo uso personale) | Rassegna stampa |
| **football-data.org** | 0 (12 comp., 10 req/min) | ★★☆☆☆ | Alta | Ridondanza calendario/classifiche |
| **TheSportsDB** | 0 (limitato) | loghi, metadati | Media (crowd-sourced) | Immagini/loghi |
| **openfootball** | 0 | calendari/risultati JSON | Alta | Ridondanza |
| API-Football | 0* | — | *niente stagione corrente gratis | **Scartata** |
| Sofascore / WhoScored / FBref | 0 | ★★★★★ | **Bassa** (403 / Incapsula / Cloudflare + 10 req/min) | Solo opzionali via collettore locale lento |
| Sportmonks | 0 solo 2 leghe minori | — | — | Scartata |

---

## 3. Progetti open source da riutilizzare (verificati su GitHub, settembre 2026)

| Progetto | Stelle | Ultimo push | Licenza | Uso previsto |
|---|---|---|---|---|
| [`martineastwood/penaltyblog`](https://github.com/martineastwood/penaltyblog) | 216 | 2026-08 | MIT | **Modelli** (Poisson, Dixon-Coles, Poisson bivariato, binomiale negativa, Weibull-copula, Bayesiani gerarchici), **rating** (Elo, Pi, Massey, Colley), **quote implicite**, **backtest**, RPS, xT, Kelly, MatchFlow per JSON |
| [`probberechts/soccerdata`](https://github.com/probberechts/soccerdata) | 2.058 | 2026-08 | proprietaria (uso libero non commerciale) | Scraper pronti per Understat (nuovo JSON API), ESPN, ClubElo, football-data.co.uk, FBref (Selenium), Sofascore, WhoScored; mappa nomi squadre |
| [`andrewRowlinson/mplsoccer`](https://github.com/andrewRowlinson/mplsoccer) | 540 | 2026-07 | MIT | Campo, shot map, pass map, heatmap, pizza/radar chart, lettura StatsBomb |
| [`hudl/statsbombpy`](https://github.com/hudl/statsbombpy) + [`hudl/open-data`](https://github.com/statsbomb/open-data) | 741 / 3.585 | 2026-09 / 2026-05 | vedi licenza SB | Dataset eventi per addestrare xG |
| [`ML-KULeuven/socceraction`](https://github.com/ML-KULeuven/socceraction) | 809 | 2026-01 | MIT | VAEP/xT su dati evento (StatsBomb) — valutazione azioni |
| [`PySport/kloppy`](https://github.com/PySport/kloppy) | 548 | 2026-09 | BSD-3 | Standardizzazione dati evento (se in futuro si aggiungono altri provider) |
| [`dcaribou/transfermarkt-datasets`](https://github.com/dcaribou/transfermarkt-datasets) | 494 | 2026-09 | CC0 | 12 tabelle (giocatori, valori, trasferimenti, formazioni, eventi) — **snapshot al 6/7/2026**, scaricabile come DuckDB |
| [`felipeall/transfermarkt-api`](https://github.com/felipeall/transfermarkt-api) | 448 | 2026-04 | MIT | API FastAPI self-hosted su Transfermarkt (solo da IP residenziale) |
| [`oseymour/ScraperFC`](https://github.com/oseymour/ScraperFC) | 409 | 2026-05 | GPL-3 | Alternativa scraper (Sofascore, FBref, Understat, Capology stipendi, Transfermarkt) |
| [`tommhe14/fotmob-wrapper`](https://github.com/tommhe14/fotmob-wrapper), [`pseudo-r/Public-FotMob-API`](https://github.com/pseudo-r/Public-FotMob-API) | 7 / 11 | 2025-09 / 2026-03 | MIT / n.d. | Riferimento per endpoint FotMob e gestione token se torna il blocco |
| [`kochlisGit/ProphitBet`](https://github.com/kochlisGit/ProphitBet-Soccer-Bets-Predictor) | 571 | 2026-04 | MIT | Riferimento per feature engineering e ML su football-data.co.uk (non da copiare: monolitico) |
| [`openfootball/football.json`](https://github.com/openfootball/football.json) | 1.011 | 2026-09 | CC0 | Calendari/risultati JSON di ridondanza |
| [`eddwebster/football_analytics`](https://github.com/eddwebster/football_analytics), [`devinpleuler/analytics-handbook`](https://github.com/devinpleuler/analytics-handbook) | 2.771 / 1.700 | 2025 / 2024 | — | Manuali/notebook di riferimento metodologico |

**Non esiste** un progetto open source già pronto che faccia "tutto" (portale + pipeline + modelli aggiornati): quelli trovati sono o dashboard didattiche su StatsBomb, o predittori betting monolitici, o scraper. Il valore del nostro progetto è nella **composizione** e nella **disciplina di validazione**.

---

## 4. Architettura proposta (tutto gratis)

```
┌────────────────────────────── GitHub (repo pubblico) ──────────────────────────────┐
│                                                                                      │
│  .github/workflows/                                                                  │
│   ├─ collect.yml   cron: ogni 30' nei giorni gara, ogni 3h altrimenti               │
│   ├─ model.yml     dopo collect: aggiorna rating, previsioni, report                 │
│   └─ deploy.yml    build sito statico → GitHub Pages / Cloudflare Pages              │
│                                                                                      │
│  pipeline/  (Python 3.11)                                                            │
│   ├─ sources/   espn.py fotmob.py understat.py footballdata.py clubelo.py            │
│   │             odds.py openmeteo.py news.py bsd.py statsbomb.py (+ collettore loc.) │
│   ├─ store/     DuckDB + Parquet (data/), snapshot JSON versionati ("git scraping")  │
│   ├─ models/    dixon_coles.py elo.py xg_ensemble.py montecarlo.py calibration.py    │
│   ├─ features/  form.py availability.py congestion.py referee.py context.py          │
│   ├─ reports/   prematch_it.py postmatch_it.py (template Jinja2)                     │
│   └─ export/    genera i JSON leggeri che il sito consuma                            │
│                                                                                      │
│  site/  (statico: Astro o Vite+React; grafici Plotly/ECharts; UI italiana)           │
│   pagine: Oggi · Partita · Squadra · Giocatore · Lega · Previsioni & accuratezza ·   │
│           Quote & valore · Notizie · Stato fonti                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
          ▲ (opzionale)                                   ▼
  collettore locale sul tuo PC                    Telegram bot (notifiche gratis)
  (IP residenziale per Transfermarkt/Sofascore)
```

**Perché così.**
- **GitHub Actions** su repo pubblico: minuti illimitati, cron integrato, segreti per le chiavi API. È il pattern "git scraping" (Simon Willison): ogni run salva lo stato → si ottiene gratis anche lo **storico delle variazioni** (es. quando è uscita una formazione, come si sono mosse le quote).
- **Sito statico**: gratuito, istantaneo, nessun server da tenere acceso, nessun "sleep". Tutte le analisi sono **precalcolate** a ogni run (10 partite a giornata × 20 squadre → pochi MB di JSON). Per query ad hoc si può aggiungere DuckDB-WASM nel browser.
- **DuckDB/Parquet**: un solo file, query SQL veloci, zero database da amministrare; compatibile con il dataset Transfermarkt già distribuito in DuckDB.
- **Collettore locale opzionale**: uno script (o container) che gira sul tuo PC, chiama le fonti che bloccano i datacenter e fa `git push` dei JSON. Se il PC è spento, il sito continua a funzionare con le altre fonti.

**Alternativa più rapida da prototipare (meno robusta):** app **Streamlit** su Streamlit Community Cloud (gratis; ~1 GB RAM; si addormenta dopo 12 h senza visite, risveglio ~30–60 s) oppure **Hugging Face Spaces** (2 vCPU, 16 GB RAM; dorme dopo 48 h). Vantaggio: interattività immediata in puro Python; svantaggi: latenza al risveglio, meno "portale", limiti di memoria. Può convivere come "laboratorio" accanto al sito statico.

**Stack tecnico.** Python 3.11, `httpx`/`curl_cffi`, `pandas`, `duckdb`, `penaltyblog`, `mplsoccer`, `scipy`, `numpy`, `jinja2`, `pydantic`; test con `pytest`; frontend statico con grafici Plotly (o ECharts) e tabelle ordinabili; deploy GitHub Pages (o Cloudflare Pages, banda illimitata).

---

## 5. Metodologia dei modelli (la parte "accuratezza")

1. **Base storica**: football-data.co.uk dal 2005 (risultati + tiri + quote di chiusura) per Serie A, Serie B e Big 5; Understat dal 2014 per xG.
2. **Modello 1 – Dixon-Coles** con decadimento temporale ottimizzato (ξ scelto minimizzando RPS su validazione walk-forward). Output: λ casa/trasferta → griglia probabilità.
3. **Modello 2 – "xG-Poisson"**: stessa struttura, ma la forza è stimata da xG/xGA (più stabile dei gol) con "shrinkage" verso la media di lega a inizio stagione.
4. **Modello 3 – Elo/Pi-rating** con margine di vittoria; ClubElo come prior per neopromosse e coppe.
5. **Correzioni contestuali** (stimate, non inventate): assenze pesate per valore/minuti, riposo/congestione, arbitro (per mercati cartellini), meteo estremo. Ogni correzione entra solo se migliora il RPS in backtest — altrimenti resta come informazione mostrata ma non usata nel modello.
6. **Ensemble** (media geometrica pesata) + **calibrazione** (isotonic/Platt) e **stacking con le quote di chiusura** come feature opzionale.
7. **Valutazione pubblica**: RPS, Brier, log-loss, calibration plot, confronto con "modello bookmaker" (probabilità implicite di Pinnacle/consenso), per stagione e per lega. Nessuna metrica "accuracy" da sola: in calcio è fuorviante.
8. **Simulazione stagione**: Monte Carlo sulle partite restanti con le probabilità del modello.
9. **xG proprio (fase avanzata)**: modello logistico/GBM addestrato su StatsBomb Open Data (distanza, angolo, parte del corpo, situazione, pressione) per (a) capire come funziona xG, (b) ricalcolare xG su fonti che danno solo coordinate.

Aspettative oneste: i migliori modelli pubblici sul mercato 1X2 stanno intorno a RPS ≈ 0.19–0.20 sulle grandi leghe, poco peggio delle quote di chiusura dei bookmaker. L'obiettivo è **avvicinarsi al mercato** ed **essere calibrati**, non "batterlo" sistematicamente.

---

## 6. Aspetti legali e di correttezza (da rispettare, anche a costo zero)

- **FotMob, ESPN, Understat, Sofascore, WhoScored, FBref**: endpoint non ufficiali o siti con ToS che vietano lo scraping massivo. Uso **personale e non commerciale**, con rate limit prudente e cache, è tollerato di fatto ma **non garantito**. Un sito pubblico che ripubblica *in massa* i loro dati grezzi (specie quelli Opta via FotMob) è zona grigia: la scelta consigliata è **portale privato/personale** (o accesso con password) che mostra soprattutto **metriche derivate** con attribuzione della fonte.
- **StatsBomb Open Data**: licenza propria — richiede attribuzione e uso non commerciale.
- **Google News RSS**: consentito solo per uso personale non commerciale (dichiarato nel feed stesso).
- **football-data.co.uk, openfootball, transfermarkt-datasets (CC0), ClubElo, Open-Meteo**: liberi per uso non commerciale (alcuni anche commerciale).
- **The Odds API / BSD / football-data.org**: chiavi API gratuite personali → conservate come **secret** di GitHub, mai nel codice.
- **Scommesse**: se si mostra il confronto modello/mercato, va aggiunto un disclaimer chiaro (informazione statistica, non consiglio; gioco responsabile; 18+). Il portale non deve spingere a giocare.
- **robots.txt e rate limit**: budget per fonte, identificazione User-Agent onesta dove sensato, nessun aggiramento di CAPTCHA/challenge JavaScript.

---

## 7. Rischi principali e contromisure

| Rischio | Probabilità | Impatto | Contromisura |
|---|---|---|---|
| FotMob cambia/chiude gli endpoint | media | alto | Astrazione "provider" con fallback ESPN (stat base) + Understat (xG); cache dell'ultimo dato buono; monitor + alert |
| Understat blocca IP GitHub | media | medio | Fallback FotMob xG; collettore locale; cache |
| Rate limit / ban | bassa se disciplinati | medio | Budget per fonte, backoff, run distanziati |
| Quote gratuite insufficienti | media | basso | 500 crediti/mese bastano per ~2 snapshot al giorno della sola Serie A; consenso BSD come ridondanza; quote di chiusura storiche da football-data.co.uk per il backtest |
| Overfitting/illusione di accuratezza | alta se non si è rigorosi | alto | Walk-forward, metriche pubbliche, nessuna feature senza prova di miglioramento |
| Nomi squadre/giocatori non allineati fra fonti | certa | medio | Tabella di mapping versionata + test automatici |
| Manutenzione (rotture) | certa nel tempo | medio | Test di "smoke" giornalieri sulle fonti, pagina stato, log strutturati |

---

## 8. Roadmap proposta

**Fase 0 — Fondamenta (1ª settimana)**
Scaffolding repo, configurazione leghe (Serie A, Serie B, Premier, Liga, Bundesliga, Ligue 1, UCL/UEL/UECL), collettori ESPN + FotMob + Understat + football-data.co.uk + ClubElo, storage DuckDB/Parquet, workflow Actions con cron, pagina "Oggi" (partite, classifica, tabella xG) online su GitHub Pages. Health monitor fonti.

**Fase 1 — Previsioni credibili (2ª–3ª settimana)**
Dixon-Coles + Elo + xG-Poisson, backtest su 10 stagioni Serie A e Big 5, calibrazione, pagina "Partita" con probabilità, matrice risultati, O/U, BTTS, e pagina pubblica "Accuratezza". Report pre-partita in italiano (template).

**Fase 2 — Profondità squadra e contesto (4ª–5ª settimana)**
Shot map, xG race, momentum, statistiche per periodo, indisponibili + diffidati, arbitro, meteo, congestione/viaggi, H2H, notizie RSS, valori di mercato e contratti, report post-partita. Simulazione Monte Carlo stagione.

**Fase 3 — Giocatori (6ª settimana)**
Schede giocatore, rating e xG/xA per 90, confronto radar, percentili di lega, infortuni storici.

**Fase 4 — Mercato e valore (opzionale, 7ª settimana)**
Snapshot quote (The Odds API / BSD), probabilità implicite, modello vs mercato, tracking del "closing line value", disclaimer.

**Fase 5 — Qualità e automazione continua**
Notifiche Telegram, test, ottimizzazioni, collettore locale per fonti protette, xG proprio su StatsBomb, eventuale PWA.

Ogni fase termina con qualcosa di **visibile e usabile online**.

---

## 9. Decisioni da prendere insieme prima di scrivere codice

1. **Perimetro iniziale**: solo Serie A (+ coppe europee delle italiane) oppure subito Big 5 + coppe? (Consiglio: partire da Serie A + UCL/UEL/UECL con architettura multi-lega già pronta; aggiungere le altre leghe è un file di configurazione.)
2. **Forma del prodotto**: sito statico sempre acceso (consigliato) vs app Streamlit (più veloce da prototipare, si addormenta).
3. **Visibilità**: portale privato/personale (consigliato per la questione ToS) o pubblico.
4. **Sezione quote/valore**: sì o no. Cambia le fonti da registrare (chiavi gratuite) e la comunicazione del sito.
5. **Collettore locale**: sei disposto a far girare uno script sul tuo PC (anche solo qualche volta a settimana) per le fonti che bloccano i datacenter (Transfermarkt/Sofascore)? Se no, si vive benissimo con FotMob per valori e infortuni.
6. **Lingua**: interfaccia in italiano (dato per scontato) — dati e codice in inglese.

---

## Appendice — Esempio reale di profondità ottenibile gratis (verificato il 5/9/2026)

Inter–Napoli 3-2, Serie A, 3ª giornata, San Siro (75.423 spettatori), arbitro Simone Sozza (33 gare in Serie A, 3,76 gialli/gara, 24,45 falli/gara, 18 rigori):

- xG 3,86 – 2,43 (open play 1,96 – 2,27; palle inattive 1,90 – 0,17); xGOT 3,20 – 1,95; tiri 29–16; big chances 5–3; legni 3–0; possesso 63–37; passaggi riusciti 486 (89%) – 265 (78%); corner 10–5.
- Per ogni tiro: giocatore, minuto, coordinate, xG, xGOT, parte del corpo, situazione, dentro/fuori area, se parato/bloccato, portiere.
- Politano: rating 7,47, 1 gol, xG 0,56, xGOT 0,89, xA 0,13, 1 big chance sbagliata, 18/23 passaggi.
- Indisponibili Napoli: Buongiorno (rientro inizio ottobre), Marianucci (metà ottobre), McTominay (problemi cardiaci, metà ottobre), Giovane (metà ottobre); età media titolari 29,1; valore titolari €109,5M.
- H2H: Napoli imbattuto negli ultimi 5 incontri prima di questa gara (1V, 4N); prossimo incrocio 31/1/2027.
- Articoli Opta pre e post gara disponibili anche in italiano.

Tutto questo da **una sola chiamata** all'endpoint dettagli partita di FotMob, più i complementi di ESPN (boxscore con 30 statistiche di squadra, arbitri, ultime 5 gare di ciascuna squadra) e Understat (xG di squadra e giocatori per l'intera stagione, xPTS, PPDA).
