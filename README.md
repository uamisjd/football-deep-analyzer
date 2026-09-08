# football-deep-analyzer

Analisi calcistica con dati reali — portale gratuito di analisi profonda delle partite (xG, previsioni calibrate, indisponibili, arbitro, contesto, quote vs modello, report in italiano).

## Stato

Fase 0–7b concluse e live su `main` (collettori, modelli, sito, automazione giornaliera su GitHub Pages con Accuratezza reale). Stato dettagliato sempre in [`docs/STATO.md`](docs/STATO.md).

## Documenti

- [`docs/BRIEFING_NUOVA_SESSIONE.md`](docs/BRIEFING_NUOVA_SESSIONE.md) — **leggi per primo** se apri una nuova sessione/agente: stato, prossimi passi, mappa dei file, limitazioni note.
- [`docs/00_regole_di_lavoro.md`](docs/00_regole_di_lavoro.md) — regole del progetto: anti-blocco chat, **paletti di qualità**, e quando fare Create PR / Merge.
- [`docs/STATO.md`](docs/STATO.md) — checkpoint: cosa è fatto, cosa manca, prossimo passo. **Se la chat si blocca, si riparte da qui.**
- [`docs/01_studio_fattibilita.md`](docs/01_studio_fattibilita.md) — studio completo: cosa costruire, fonti (con verdetto), progetti open source da riutilizzare, architettura a costo zero, metodologia dei modelli, aspetti legali, rischi, roadmap, decisioni aperte.
- [`docs/02_catalogo_fonti_dati.md`](docs/02_catalogo_fonti_dati.md) — catalogo tecnico degli endpoint gratuiti verificati (FotMob, ESPN, Understat, football-data.co.uk, ClubElo, StatsBomb, Transfermarkt datasets, BSD, quote, meteo, notizie), limiti, id utili e schema dati minimo.
- [`docs/03_decisioni_e_funzionamento.md`](docs/03_decisioni_e_funzionamento.md) — decisioni prese (7 campionati, uso personale, quote) e spiegazione dell'automazione giornaliera.

## Avvio rapido (sviluppo)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
fda leagues        # elenca i 7 campionati configurati
pytest -q          # test
```

## Come funziona (in breve)

`fda daily` = `collect` (FotMob, Understat, ESPN → `data/processed/*.parquet`) → `predict` (Dixon-Coles + Elo) → `build` (sito in `site/`).
GitHub Actions lo esegue 5 volte al giorno (`.github/workflows/daily.yml`), committa i dati e pubblica il sito su GitHub Pages.

### Attivazione (una volta sola, dal ramo `main`)
1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Actions → *daily* → **Run workflow** (primo run manuale; poi parte da solo con il cron).
3. Opzionale: Settings → Secrets → `ODDS_API_KEY` (The Odds API, piano gratuito) per la sezione quote.
