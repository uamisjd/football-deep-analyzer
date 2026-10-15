# 107 — Revisione totale (vita, morte e miracoli) — 14 ottobre 2026

Richiesta: *«controlla vita morte e miracoli del progetto e del sito, vedi a che punto siamo
arrivati, se c’è qualcosa da fare, da rivedere, da migliorare»*.

Questa sessione **non ha ripetuto** la suite locale (pytest / build / verify) già misurata ieri
e oggi in altre sessioni: i numeri di gate sotto sono **citati** da `STATO.md` e dai check
GitHub **verificati in questo turno** via `gh`. Il sito pubblico e lo stato GitHub sono
**verificati dal vivo** (14/10 pomeriggio UTC).

## 1. Cos’è il progetto

**CalcioMetro** (`football-deep-analyzer`): portale statico gratuito di analisi profonda su
**7 campionati** (ITA1, ENG1, ESP1, GER1, FRA1, NED1, POR1). Pipeline `fda daily`: collect →
calibrate → predict (Dixon-Coles + Elo) → backtest → mercati-monitor → simulate → build.
Pubblicazione su GitHub Pages, **senza secret**, fonti gratuite. Quote di mercato **non
pubblicate** (`docs/38`).

Sito live: [https://uamisjd.github.io/football-deep-analyzer/](https://uamisjd.github.io/football-deep-analyzer/)

## 2. Dove siamo (14/10/2026, pomeriggio)

| Voce | Stato | Classe |
|---|---|---|
| `main` | `23efbc1` (merge PR #121, registrazione post-#120) | verificato `gh` |
| Issue aperte | **0** (#114 chiusa dal daily #271) | verificato `gh` |
| PR aperte | **0** | verificato `gh` |
| Daily ultimi 3 su `main` | **verdi** (#271 post-#119, #272 post-#117, `38568634387` post-#120) | verificato `gh` |
| Daily prima di #119 | 3 rossi di fila (#113, due schedule, #116) per oracolo [50] / «1 voce» | verificato `gh` |
| Deploy Pages | ultimo daily con deploy **success**; home aggiornata **14/10 15:09** | verificato live |
| Home | **0 partite oggi** (sosta nazionali); messaggio onesto; prossima **ven 16/10 con 5 gare** | verificato live |
| Fonti (`stato.html`) | FotMob 7/7 OK; ESPN classifica OK da cache; scoreboard 0 righe (giornata vuota); news 4.050 in finestra; Understat 5 grandi leghe OK | verificato live |
| Gate offline (ultimo giro locale registrato, post-hotfix) | **1.033 test**, Ruff 0, `verify_site` **242.503 · 0**, parità 59, resa 375 **28.766 · 0** | citato da `STATO` / #119, **non rifatto qui** |
| CI PR #120 | `test` / `site` / `browser` SUCCESS su `67e05ae` | verificato `gh` |
| Dimensione repo GitHub | **~727 MiB** (`size` 744 203 KB) | verificato API |
| Fotografia dati 1×/giorno | run intermedi **`190256d` e analoghi**: solo `prospettico.parquet` | citato `STATO`; **foto serale ≥20 UTC ancora da vedere** |
| Stampa `nl`/`pt` | codice in produzione (docs/106, oracolo [50] corretto da #119); **persistenza in archivio da confermare al daily serale** | da verificare |

**Il prodotto è vivo e coerente con la sosta.** Nessun numero della home smentisce il calendario.
La pipeline, dopo tre rossi ieri/notte, è **di nuovo verde** da #119 in poi.

## 3. Cosa è già chiuso (ciclo schede e qualità)

Revisionate e chiuse con misura + invarianti (handoff `docs/101`, confermato in `docs/104`–`106`
e correzioni 14/10):

- Lettura, Fattori, Scontro, Fatti, Come arrivano, Giocatori, Due squadre, Confronto,
  Panchina, Mercato, Clima, Vita del club, Arbitro/meteo, Precedenti (`docs/103`).
- Laboratorio pubblico, test prospettico avviato, storico Understat, fotografia 1×/giorno,
  stampa estera NED1/POR1, hardening CI/browser/worktree (PR #116), hotfix singolare (#119),
  pin Ruff 0.17.0 (#120).

**Non è un prototipo:** è un sito in produzione con ~4 300 HTML, ~500 schede partita,
migliaia di controlli automatici a ogni PR.

## 4. Cosa resta da fare (coda onesta)

Ordine di utilità, senza inventare lavoro:

1. **Operativo stasera (non codice):** daily ≥20 UTC → commit fotografia completa
   (`FDA-SNAPSHOT: full-v1`) e controllo righe `language` `nl`/`pt` in `news.parquet`.
   Se manca, diagnosticare; **non** fare dispatch duplicati.
2. **Due sezioni scheda ancora in coda di revisione B.10 “da capo”:**
   «Previsione ensemble» (`#previsione` + scomposizione, laboratorio, fascia, posizione, primo gol)
   e «Verifica approfondita» (matrice + gol totali).
   I numeri sono già sotto oracoli [8]–[12], [15]–[17], [46], [47]; le correzioni del 14/10
   sono contrasto/accessibilità, **non** un ciclo prima/dopo di contenuto.
   Intervenire **solo** se una misura mostra un miglioramento netto (regola B.10).
3. **Crescita Git:** politica A adottata (`docs/105`). Il −80% è **atteso**, non ancora
   misurato su una settimana di foto complete. Repo ~727 MiB; 1 GB resta un orizzonte da
   ricalcolare dopo 7 giorni di foto 1×.
4. **Modelli:** `dc_xg` e tilt **non promossi**; accumulare il test prospettico. Nessuna
   promozione senza griglia preregistrata.
5. **Decisioni aperte storiche** (non sbloccate da questa revisione): StatsBomb open data;
   eventuali fonti meteo oltre FotMob (Open-Meteo 0 righe utili oggi perché meteo già da FotMob);
   igiene `docs/` (119+ file, duplicato `58`).
6. **Copertura NED1/POR1 «Vita del club»:** buco di **fonte italiana**, mitigato dalla stampa
   originale; non abbassare le soglie.

**Non fare adesso:** rewrite del modello, LFS, `git filter-repo`, nuove sezioni decorative,
merge autonomi, riaprire #114.

## 5. Rischi (misurati o già visti)

- **Gate fragili sul testo italiano** (concordanza `voce`/`voci`, `campionato`/`campionati`):
  tre daily rossi in 24 h. Mitigazione: test sul template reale; restare stretti sulle regex.
- **Repo size** verso i limiti GitHub “comodi” (<1 GB). Politica A in vigore; da misurare.
- **ESPN** in backoff/cache: classifica OK, scoreboard vuoto in sosta — dichiarato, non un bug.
- **Clone sandbox shallow:** `git count-objects` locale non misura il pack reale (~10 MiB vs 727 MiB GitHub).

## 6. Verdetto

Il progetto è **maturo, in produzione, e in salute dopo l’incidente [50]**. Il sito dice il
vero sulla giornata vuota. La coda utile è **piccola e precisa**: verifica serale della
fotografia, eventuale revisione misurata delle due sezioni previsione/verifica, pazienza sui
modelli. Non serve un rifacimento.

## Prossimo passo

Attendere il daily serale; in parallelo, se l’utente lo chiede, aprire il ciclo B.10 sulla
card «Previsione ensemble» **misurando prima** sulle schede pre-partita del 16/10.
