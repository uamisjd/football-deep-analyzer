# Decisioni prese e come funzionerà il sistema automatico

> Aggiornato al 6 settembre 2026. Risponde ai 5 punti decisi dall'utente.

## 1. Campionati iniziali (7)

| # | Campionato | FotMob id | ESPN code | Understat | football-data.co.uk | Note |
|---|---|---|---|---|---|---|
| 1 | Serie A (ITA) | 55 | `ita.1` | `Serie_A` | `I1` | priorità massima |
| 2 | Premier League (ENG) | 47 | `eng.1` | `EPL` | `E0` | |
| 3 | LaLiga (ESP) | 87 | `esp.1` | `La_Liga` | `SP1` | |
| 4 | Bundesliga (GER) | 54 | `ger.1` | `Bundesliga` | `D1` | 18 squadre |
| 5 | Ligue 1 (FRA) | 53 | `fra.1` | `Ligue_1` | `F1` | 18 squadre |
| 6 | Eredivisie (NED) | 57 | `ned.1` | — | `N1` | niente xG Understat → xG solo FotMob |
| 7 | Liga Portugal (POR) | 61 | `por.1` | — | `P1` | idem |

Gli id FotMob 55/47/87/54/53/57/61 sono stati verificati il 5–6 settembre 2026 (stagione 2026/2027 attiva su tutti). Le coppe europee (UCL 42, UEL 73, UECL) si aggiungono in una fase successiva: servono comunque per calcolare la **congestione del calendario** delle squadre coinvolte, quindi il calendario delle coppe verrà letto da subito, ma senza analisi dedicate.

## 2. Come funziona l'automazione giornaliera (spiegazione completa)

### L'idea in una frase
Un "robot" gratuito di GitHub (GitHub Actions) si accende da solo più volte al giorno, scarica i dati aggiornati, ricalcola i modelli, scrive le analisi di ogni partita e pubblica il sito. Tu apri un indirizzo web e trovi tutto pronto, senza fare nulla.

### I pezzi

```
 ┌──────────────── GitHub (gratis) ────────────────┐
 │                                                  │
 │  1. ORARIO (cron)  ──►  2. RACCOLTA DATI         │
 │     06:00, 12:00,        FotMob, ESPN, Understat, │
 │     16:00, 20:00,        football-data, ClubElo,  │
 │     23:30 (ora IT)       quote, meteo, notizie    │
 │                                │                  │
 │                                ▼                  │
 │                         3. DATABASE (DuckDB)      │
 │                            salvato nel repo       │
 │                                │                  │
 │                                ▼                  │
 │                         4. MODELLI + ANALISI      │
 │                            previsioni, report IT  │
 │                                │                  │
 │                                ▼                  │
 │                         5. SITO STATICO           │
 │                            GitHub Pages           │
 └──────────────────────────────────────────────────┘
                                 │
                                 ▼
                     6. TU: apri il sito (o ricevi
                        un messaggio Telegram)
```

### Passo per passo

**1. L'orario.** Nel repository c'è un file (`.github/workflows/daily.yml`) con una tabella oraria ("cron"). GitHub esegue il lavoro a quegli orari su un computer virtuale gratuito. Per un repository pubblico i minuti sono illimitati; il lavoro dura 5–15 minuti a esecuzione. Piano orario iniziale (ora italiana):
- **06:00** — run principale: risultati della sera prima, analisi post-partita, nuove previsioni per le prossime 72 ore, report del giorno.
- **12:00 e 16:00** — aggiornamento infortuni/indisponibili, quote, meteo, notizie.
- **20:00 e 23:30** — nei giorni con partite: risultati, statistiche e shot map delle gare finite.
- Ogni esecuzione può essere lanciata anche a mano da GitHub con un click ("Run workflow").

**2. La raccolta.** Uno script Python interroga le fonti gratuite (tutte raggiungibili da GitHub Actions, come da tua decisione):
- **FotMob** → calendario, risultati, statistiche complete, xG per tiro, formazioni, **indisponibili con data di rientro**, valori di mercato, arbitro, meteo della partita (FotMob espone anche un blocco `weather`), H2H.
- **ESPN** → riserva per calendario/risultati/classifiche/boxscore (se FotMob fallisce).
- **Understat** → xG, xGA, xPTS, PPDA per le 5 grandi leghe (seconda opinione).
- **football-data.co.uk** (via mirror datahub.io su GitHub) → storico dal 1993 per addestrare e validare i modelli.
- **ClubElo** → rating Elo storico.
- **The Odds API** (500 crediti/mese gratis) → quote pre-partita 1–2 volte al giorno.
- **Open-Meteo**, **Google News RSS** → contesto.
Ogni chiamata è limitata (≤1 richiesta/secondo verso FotMob) e ciò che è già stato scaricato non viene richiesto di nuovo.

**3. Il database.** Tutto finisce in un file DuckDB (`data/fda.duckdb`) più file Parquet, salvati nel repository stesso: così lo storico cresce gratis e ogni esecuzione "vede" cosa è cambiato rispetto alla precedente (quando è uscita una formazione, come si sono mosse le quote, quando è stato annunciato un infortunio).

**4. Modelli e analisi.** Con i dati aggiornati si ricalcolano: Dixon-Coles (probabilità 1-X-2, risultati esatti, Over/Under, BTTS), Elo, modello su xG, ensemble calibrato; per ogni partita delle prossime 72 ore si genera un **report pre-partita in italiano** (forza, forma, xG, assenze pesate, diffidati, arbitro, riposo/viaggi, meteo, H2H, quote vs modello, notizie); per ogni partita finita un **report post-partita** (xG, shot map, momentum, prestazioni, cosa ha detto il modello). Ogni previsione viene salvata e poi valutata: la pagina "Accuratezza" è aggiornata automaticamente.

**5. Il sito.** Un generatore produce pagine HTML statiche (Oggi · Partita · Squadra · Giocatore · Campionato · Previsioni & Accuratezza · Quote · Stato fonti) pubblicate su **GitHub Pages** (gratis, sempre acceso, nessun server). URL del tipo `https://uamisjd.github.io/football-deep-analyzer/`. Poiché il repository è pubblico, il sito è raggiungibile da chi conosce l'indirizzo: per l'uso personale basta non divulgarlo; se vorrai una protezione vera, la via gratuita è Cloudflare Pages + Cloudflare Access (login con la tua email), documentata in una fase successiva.

**6. Tu.** Apri il sito. Opzionale: un bot Telegram gratuito ti manda alle 07:00 il riassunto delle partite del giorno e avvisa quando escono le formazioni ufficiali o un infortunio importante.

### Cosa succede se qualcosa si rompe
- Ogni fonte ha un fallback (FotMob → ESPN; Understat → FotMob xG). Se una fonte fallisce, il run continua e la pagina "Stato fonti" lo segnala in rosso con l'orario dell'ultimo dato buono.
- Se un run fallisce del tutto, GitHub manda un'email; il sito resta online con i dati dell'ultimo run riuscito.
- Un test giornaliero "smoke" controlla che gli endpoint rispondano ancora nel formato atteso.

### Limiti onesti
- Non è "in tempo reale": ritardo da 30 minuti a poche ore, a seconda dell'orario. Se in futuro vorrai il live vero, si aggiunge un run ogni 10 minuti nelle finestre delle partite (sempre gratis, ma più rumoroso).
- Le formazioni ufficiali escono ~1 h prima: le vedrai nel sito solo se un run cade in quella finestra (si può programmare un run "pre-gara" a orari fissi: 11:30, 14:00, 17:00, 19:45 ora IT, che coprono i calci d'inizio tipici).
- Le quote gratuite bastano per 1–2 istantanee al giorno, non per il movimento continuo.

## 3. Uso personale fino al completamento
Sito non pubblicizzato, nessun indice sui motori di ricerca (`robots.txt` + meta `noindex`), attribuzione fonti in ogni pagina, dati grezzi di terzi non riesposti in blocco (solo metriche e viste derivate).

## 4. Sezione quote / valore: sì
Si registra una chiave gratuita The Odds API (500 crediti/mese) e si salva come *secret* del repository. Il sito mostra: quote consenso, probabilità implicite senza margine (metodo Shin), confronto con il modello, e — a posteriori — quanto il modello ha fatto meglio o peggio delle quote di chiusura. Disclaimer fisso.

## 5. Fonti: solo raggiungibili da GitHub Actions
Esclusi per ora: Sofascore, WhoScored, FBref, Transfermarkt diretto. Se un giorno servissero, esiste il piano "collettore locale" nello studio (§4 di `01_studio_fattibilita.md`).

---

## Verifiche tecniche fatte il 6 settembre 2026 (salvate qui per non rifarle)

- `penaltyblog 1.12.0` funziona su Python 3.11 con `numpy 2.4.6` / `pandas 3.0.5`: **attenzione**, con pandas 3 bisogna passare al modello array NumPy scrivibili (`.to_numpy().copy()`), altrimenti errore "buffer source array is read-only". Fit Dixon-Coles su una stagione: 0,01 s. Esempio reale su Serie A 2025/26: Inter–Napoli → 56% / 21,5% / 22,4%, λ 1,95–1,16, Over 2,5 = 60%.
- Il mirror **datahub `datasets/football-datasets`** su GitHub contiene i CSV per serie-a, premier-league, la-liga, bundesliga, ligue-1 dal 1993/94 al 2025/26 (colonne base: Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, HT*, Referee, tiri, falli, corner, cartellini — **senza quote**). Il sito originale football-data.co.uk era irraggiungibile il 5–6 settembre; le quote storiche si prenderanno da lì quando torna online.
- FotMob `matchDetails` di una partita **futura** (Udinese–Lazio, 7/9) contiene già: arbitro designato con statistiche, stadio con coordinate, forma ultime 5, **formazione probabile** (`lineupType: "predicted"`), indisponibili con rientro per entrambe, H2H completo, insight testuali, **meteo previsto**. Ottimo per il report pre-partita.
- FotMob `leagues?id=` contiene anche i **trasferimenti** recenti della lega con valore e date; `fixtures?id=&season=` dà tutta la stagione con `matchId`.
- ESPN funziona anche per `ned.1` (Eredivisie) con statistiche squadra nel scoreboard.
- soccerdata `understat.py` (master) usa `/getLeagueData/{slug}/{season}` con header `X-Requested-With` e cookie: da riutilizzare così com'è.
