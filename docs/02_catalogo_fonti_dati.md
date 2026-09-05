# Catalogo tecnico delle fonti dati (gratuite)

> Stato verificato il **5 settembre 2026**. "✅ verificato" = endpoint interrogato dal vivo con risposta valida; "📄 documentato" = informazione presa dalla documentazione/repo ufficiale, non testata da qui; "⛔" = testato e bloccato.
> Convenzione: tutte le date/ore in UTC nel dato; conversione a Europe/Rome solo in presentazione.

---

## 1. FotMob — endpoint non documentati (`https://www.fotmob.com/api/data/...`) ✅

Nessuna autenticazione oggi. Nel 2024 alcuni endpoint richiedevano header `x-mas` / `x-fm-req` generati dal browser; oggi il prefisso `/api/data/` risponde senza. Prevedere comunque nel client: User-Agent da browser, `Accept: application/json`, `Referer: https://www.fotmob.com/`, retry e possibilità di iniettare header extra da configurazione.

| Endpoint | Contenuto | Note |
|---|---|---|
| `leagues?id=55` | Serie A: tabella, calendario completo stagione con `matchId`, statistiche di lega, trasferimenti | ✅ id Serie A = 55, Serie B = 86, Premier = 47, Liga = 87, Bundesliga = 54, Ligue 1 = 53, UCL = 42, UEL = 73, UECL = 10216 (verificare gli id coppe al primo run) |
| `fixtures?id=55&season=2026%2F2027` | tutte le partite della stagione con esito/orario | ✅ |
| `matches?date=20260905` | tutte le partite del giorno, tutte le leghe (live score) | ✅ |
| `matchDetails?matchId=5749666` | **il cuore**: `general`, `header` (eventi), `content.matchFacts` (infoBox con arbitro + stats arbitro, stadio con lat/long, affluenza; `teamForm`; `oddspoll`; `momentum`; `postReview`/`preReview` articoli Opta multilingua; `QAData`; `matchinsights` URL), `content.stats.Periods.{All,FirstHalf,SecondHalf}` (~40 statistiche), `content.shotmap.shots[]` (x, y, xG, xGOT, `eventType`, `shotType`, `situation`, `isBlocked`, `isOnTarget`, `goalCrossedY/Z`, `keeperId`), `content.lineup` (formazione, titolari con `performance.rating`, `substitutionEvents`, panchina con `marketValue` e `seasonRating`, `unavailable[]` con `injuryId`, `type`, `expectedReturn`, allenatore), `content.playerStats` (blocchi per giocatore: rating, xG, xGOT, xA, passaggi, duelli, azioni difensive), `content.h2h` (bilancio + ultimi incontri), `content.table`, `content.matchInsights` | ✅ dimensione ~1–2 MB per partita; cache su disco obbligatoria |
| `teams?id=9875` | squadra: rosa, prossime/ultime partite, tabella, `overview`, `transfers`, `fixtures`, `squad` | ✅ |
| `playerData?id=843099` | giocatore: anagrafica, contratto (`contractEnd`), ruoli con occorrenze, `injuryInformation` (tipo, `expectedReturn`, `lastUpdated`), valore di mercato, stagione corrente (`mainLeague.stats`), trofei, `recentMatches` con rating, statistiche per stagione | ✅ |
| `https://data.fotmob.com/generated-match-insights/{leagueId}/{matchId}/matchinsights_it.json` | insight testuali della partita in italiano | 📄 (URL letto da `matchInsightsConfig.urlTemplate`) |

Id squadre Serie A (FotMob): Roma 8686 · Inter 8636 · Milan 8564 · Juventus 9885 · Napoli 9875 · Atalanta 8524 · Lazio 8543 · Como 10171 · Fiorentina 8535 · Torino 9804 · Bologna 9857 · Genoa 10233 · Parma 10167 · Udinese 8600 · Sassuolo 7943 · Lecce 9888 · Cagliari 8529 · Monza 6504 · Venezia 7881 · Frosinone 9891.

Rate suggerito: ≤ 1 req/s, max ~600 req/run; matchDetails solo per partite del giorno ±1 e per partite mai scaricate (backfill lento).

Librerie di riferimento: `tommhe14/fotmob-wrapper` (MIT), `pseudo-r/Public-FotMob-API` (elenco endpoint). soccerdata **ha rimosso** il suo reader FotMob → scrivere un client proprio, sottile.

---

## 2. ESPN — API pubbliche non documentate (`site.api.espn.com`) ✅

Nessuna autenticazione. Codici lega: `ita.1` Serie A, `ita.2` Serie B, `eng.1`, `esp.1`, `ger.1`, `fra.1`, `uefa.champions`, `uefa.europa`, `uefa.europa.conf`, `ita.coppa_italia`.

| Endpoint | Contenuto |
|---|---|
| `/apis/site/v2/sports/soccer/ita.1/scoreboard?dates=20260905` | partite del giorno con stato, punteggi, marcatori, formazione (dopo l'uscita), quote base, arbitri, stadio, meteo (a volte) |
| `/apis/site/v2/sports/soccer/ita.1/summary?event={id}` | boxscore (≈30 statistiche squadra: possesso, tiri, tiri in porta, falli, corner, fuorigioco, passaggi, cross, salvataggi…), rosa/eventi, `officials`, `lastFiveGames`, `headToHead`, `standings`, `odds`, `news` |
| `/apis/site/v2/sports/soccer/ita.1/teams` e `/teams/{id}` | anagrafica squadra, loghi, colori, record |
| `/apis/site/v2/sports/soccer/ita.1/teams/{id}/schedule` | calendario completo (tutte le competizioni) con affluenza, stadio, emittenti |
| `/apis/site/v2/sports/soccer/ita.1/teams/{id}/roster` | rosa con ruoli, età, altezza, nazionalità |
| `/apis/v2/sports/soccer/ita.1/standings` | classifica completa (G, V, N, P, GF, GS, DR, Pt, note Champions/retrocessione) |
| `/apis/site/v2/sports/soccer/ita.1/news` | notizie ESPN |

Id squadre ESPN: Napoli 114 · Inter 110 · Fiorentina 109 · Torino 239 · Roma 104 · Como 2572 (le altre si leggono da `/teams`).
`/teams/{id}/injuries` → vuoto per il calcio (⛔ non usare).

---

## 3. Understat (`https://understat.com`) ✅ (pagina) / 📄 (JSON)

Copertura: EPL, La Liga, Bundesliga, Serie A, Ligue 1, RFPL dal 2014/15. Contenuti: per squadra xG, xGA, npxG, npxGA, xPTS, PPDA, OPPDA, deep, deep_allowed per partita; per giocatore xG, xA, npxG, xGChain, xGBuildup, tiri con coordinate e xG; per partita tiri e formazioni.

Da dicembre 2025 i dati non sono più nel `<script>` della pagina ma su endpoint JSON, chiamati con header `X-Requested-With: XMLHttpRequest` e cookie ottenuti visitando prima la home:
- `/getLeagueData/Serie_A/2026` (datesData con xG per partita, teamsData, playersData)
- `/getTeamData/Napoli/2026`
- `/getMatchData/{match_id}` (shots + rosters)
- `/getStatData` (POST per tabella lega)

Senza XHR header + cookie → 404 (⛔ verificato dal sandbox). **soccerdata ≥ 1.9** (`soccerdata/understat.py`, `_ensure_cookies`) implementa già tutto: `Understat(leagues="ITA-Serie A", seasons=2026)` → `read_schedule()`, `read_team_match_stats()`, `read_player_season_stats()`, `read_shot_events()`. Possibile blocco IP datacenter: prevedere fallback FotMob.

---

## 4. football-data.co.uk (CSV) 📄 (oggi il sito risponde "temporarily unavailable" ⛔ — riprovare)

URL: `https://www.football-data.co.uk/mmz4281/{stagione}/{lega}.csv` con stagione `2526`, `2627`; leghe `I1` Serie A, `I2` Serie B, `E0`, `SP1`, `D1`, `F1`. Storico dal 1993.
Colonne: `Date, Time, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HTHG, HTAG, HTR, Referee, HS, AS, HST, AST, HF, AF, HC, AC, HY, AY, HR, AR` + quote `B365H/D/A, BWH.., PSH.., WHH.., MaxH.., AvgH..`, Over/Under 2.5 (`B365>2.5`, `Avg>2.5`…), handicap asiatico (`AHh, B365AHH…`), e le versioni **di chiusura** (`B365CH, PSCH, AvgC>2.5`…). Note e legenda: `notes.txt`.
Mirror aggiornato quotidianamente da GitHub Actions: **datahub.io `football-datasets`** (repo `datasets/football-datasets`, CSV per lega e stagione) e soccerdata `MatchHistory` reader. Uso: backtest, quote storiche, calibrazione.

---

## 5. ClubElo (`http://api.clubelo.com`) 📄

`GET /Napoli` → CSV storico Elo del club dal 2000 (`Rank,Club,Country,Level,Elo,From,To`); `GET /2026-09-05` → Elo di tutti i club a una data; `GET /Fixtures` → prossime partite con probabilità Elo. Nessun limite dichiarato; una richiesta al giorno basta. soccerdata `ClubElo` e penaltyblog lo supportano. Nomi club in stile ClubElo (mapping necessario).

---

## 6. StatsBomb Open Data (`github.com/statsbomb/open-data`) ✅

`data/competitions.json`, `data/matches/{competition_id}/{season_id}.json`, `data/events/{match_id}.json`, `data/lineups/{match_id}.json`, `data/three-sixty/{match_id}.json`. Includono Serie A 2015/16 (competition_id 12), Champions League (molte finali/stagioni), Mondiali 2018/2022, Euro 2020/2024, Liga (Messi), Premier 2015/16, Bundesliga 2015/16, Liga femminile, ecc. Licenza: attribuzione + non commerciale. Lettura con `statsbombpy` (`sb.events(match_id=…)`) o `mplsoccer.Sbopen`. Uso: addestramento xG, VAEP (socceraction), demo pass map/pressure map.

---

## 7. transfermarkt-datasets (dcaribou) — CC0, ma **congelato** ⚠️

Discussione ufficiale del 5/9/2026 ("Dataset updates are paused — data is current to 6 July 2026"): le pagine sorgente non sono più raggiungibili dai runner GitHub Actions; `games`/`game_events` fermi al 2026-07-06, `appearances` al 2026-06-28, `player_valuations` al 2026-06-12, `players` senza le rose 2026/27.
Download: file DuckDB unico e CSV (`competitions, clubs, players, player_valuations, transfers, games, club_games, appearances, game_events, game_lineups`) dal bucket R2 indicato nel README, o mirror Kaggle/data.world.
Uso: storico valori/trasferimenti/formazioni dal 2012 al luglio 2026. Per l'aggiornato: FotMob (`marketValue`, `contractEnd`, `transfers`) oppure `felipeall/transfermarkt-api` eseguito **in locale** (IP residenziale).

---

## 8. Bzzoiro Sports Data — BSD (`https://sports.bzzoiro.com`) ✅ (senza token) / 📄 (con token)

Registrazione gratuita → token; header `Authorization: Token <KEY>`; base `https://sports.bzzoiro.com/api/v2/`. Documentazione `/docs/football/`, OpenAPI `/openapi.json`, guida agenti `/docs/guides/ai-agents/`.
Endpoint: `events/` (`?date=`, `?league=`, `?team=`, `?live=true`), `events/{id}/` (+ `stats/`, `lineups/`, `incidents/`, `h2h/`, `odds/`, `predictions/`), `leagues/`, `teams/`, `players/`, `managers/`, `referees/`, `venues/`, `odds/`, `odds/best/`, `predictions/`, `coverage/` (pubblico).
Limiti piano gratuito (dal 17/8/2026): 7.500 req/giorno, 25 req/s; quote solo consenso (le singole book sul piano a pagamento); paginazione `limit/offset` ≤ 200; orari UTC ISO 8601; quote decimali.
Dichiarano: formazioni ufficiali ~1 h prima, `unavailable_players`, xG per tiro, storico 15 anni, previsioni Dixon-Coles. **Da verificare con il token** prima di affidarci (progetto individuale, contiene affiliazioni betting).

---

## 9. Quote — piani gratuiti 📄

- **The Odds API** (`api.the-odds-api.com/v4/sports/soccer_italy_serie_a/odds?regions=eu&markets=h2h,totals,spreads`): 500 crediti/mese; 1 richiesta = 1 credito × mercati × regioni → con `eu` + `h2h,totals` = 2 crediti → ~8 snapshot/giorno possibili, consigliati 2/giorno + 1 a 1 h dal calcio d'inizio. Fornisce ~15–20 bookmaker (Pinnacle incluso in `eu`).
- **odds-api.io**: 500 req/giorno gratis ma solo 2 bookmaker.
- **OddsPapi**: 250 req/mese.
- **Quote di chiusura storiche**: football-data.co.uk (B365C, PSC, AvgC).
- **Consenso**: BSD `odds/` (gratis).
- **WhoScored/FotMob**: mostrano quote di un singolo bookmaker nelle pagine (FotMob `oddspoll`) — non affidabile come fonte.

---

## 10. Contesto

- **Open-Meteo** (`https://api.open-meteo.com/v1/forecast?latitude=40.828&longitude=14.193&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m&timezone=Europe%2FRome`) ✅ senza chiave; previsioni 16 giorni; archivio storico su `archive-api.open-meteo.com`. Coordinate stadi da FotMob `infoBox.Stadium.lat/long`.
- **Google News RSS** (`https://news.google.com/rss/search?q=%22SSC+Napoli%22&hl=it&gl=IT&ceid=IT:it`) ✅ titoli, link, fonte, data; consentito solo uso personale non commerciale.
- **Wikidata/Wikipedia** per stadio, capienza, città (SPARQL gratuito) 📄.
- **openfootball/football.json** (`raw.githubusercontent.com/openfootball/football.json/master/2025-26/it.1.json`) 📄 calendari CC0.
- **TheSportsDB** (`thesportsdb.com/api/v1/json/3/...`) 📄 loghi, stadi; chiave test "3"; 30 req/min.
- **football-data.org v4** (`api.football-data.org/v4/competitions/SA/matches`, header `X-Auth-Token`) 📄 12 competizioni, 10 req/min, ritardato.

---

## 11. Fonti scartate o solo "locali"

| Fonte | Motivo | Se proprio |
|---|---|---|
| API-Football (api-sports.io) | gratis: 100 req/giorno e stagioni 2021–2023 soltanto | — |
| Sportmonks free | solo lega scozzese e danese | — |
| Sofascore (`api.sofascore.com`) | 403 da IP datacenter ⛔; funziona con `curl_cffi` impersonate da IP residenziale | collettore locale, ≤ 1 req/2 s (rating, heatmap, media attributi) |
| WhoScored | Incapsula; serve browser reale (Selenium/undetected-chromedriver) | collettore locale settimanale |
| FBref (Sports Reference) | Cloudflare + regola ≤ 10 req/min, ban 24 h se violata; ma i dati sono Opta ricchissimi (possesso, passaggi progressivi, GCA/SCA, pressioni, ecc.) | soccerdata `FBref` con delay 7 s, solo run settimanale notturno e cache permanente |
| Transfermarkt diretto | muro "verifica umana" su datacenter; le pipeline open sono ferme | `felipeall/transfermarkt-api` in locale |
| Flashscore/Diretta.it | JS pesante, anti-bot | — |
| Kaggle datasets vari | statici, spesso vecchi | solo per esperimenti |

---

## 12. Schema dati minimo (per orientare l'implementazione)

```
competitions(id, name, country, fotmob_id, espn_code, understat_name, fd_code, clubelo_country)
seasons(competition_id, season, start, end)
teams(id, name_canonical, fotmob_id, espn_id, understat_name, fd_name, clubelo_name, stadium_id)
stadiums(id, name, city, lat, lon, capacity)
matches(id, competition_id, season, round, utc_kickoff, home_team_id, away_team_id, status,
        home_goals, away_goals, ht_home, ht_away, referee_id, attendance, fotmob_id, espn_id, understat_id)
match_team_stats(match_id, team_id, source, stat_key, value, period)
shots(match_id, team_id, player_id, minute, x, y, xg, xgot, situation, body_part, outcome, source)
player_match_stats(match_id, player_id, team_id, minutes, rating, xg, xa, ... , source)
players(id, name, birth_date, nationality, position, foot, height, fotmob_id, espn_id, understat_id, tm_id)
availability(team_id, player_id, as_of, status{injured,suspended,doubtful,national_duty}, reason, expected_return, source)
referees(id, name, fotmob_id, matches, yellows_per_match, fouls_per_match, penalties)
odds_snapshots(match_id, bookmaker, market, selection, price, captured_at, source)
ratings(team_id, as_of, model{elo,pi,dc_attack,dc_defence}, value)
predictions(match_id, model_version, made_at, p_home, p_draw, p_away, lambda_home, lambda_away, grid_json)
prediction_scores(match_id, model_version, rps, brier, logloss)
weather(match_id, captured_at, temp_c, precip_prob, precip_mm, wind_kmh)
news(team_id, published_at, title, url, source)
source_health(source, last_success_at, last_error, requests_today)
```

Chiavi esterne multi-fonte per ogni entità = riconciliazione esplicita, controllata da test.
