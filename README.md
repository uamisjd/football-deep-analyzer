# football-deep-analyzer

Analisi calcistica con dati reali — portale gratuito di analisi profonda delle partite (xG, previsioni calibrate, indisponibili, arbitro, contesto, schede giocatore con percentili e radar, report in italiano).

## Stato

Fase 0–7b concluse e live su `main` (collettori, modelli, sito, automazione giornaliera su GitHub Pages con Accuratezza reale). Stato dettagliato sempre in [`docs/STATO.md`](docs/STATO.md).

## Documenti

- [`docs/BRIEFING_NUOVA_SESSIONE.md`](docs/BRIEFING_NUOVA_SESSIONE.md) — **leggi per primo** se apri una nuova sessione/agente: stato, prossimi passi, mappa dei file, limitazioni note.
- [`docs/00_regole_di_lavoro.md`](docs/00_regole_di_lavoro.md) — regole del progetto: anti-blocco chat, **paletti di qualità**, e quando fare Create PR / Merge.
- [`docs/STATO.md`](docs/STATO.md) — checkpoint: cosa è fatto, cosa manca, prossimo passo. **Se la chat si blocca, si riparte da qui.**
- [`docs/01_studio_fattibilita.md`](docs/01_studio_fattibilita.md) — studio completo: cosa costruire, fonti (con verdetto), progetti open source da riutilizzare, architettura a costo zero, metodologia dei modelli, aspetti legali, rischi, roadmap, decisioni aperte.
- [`docs/02_catalogo_fonti_dati.md`](docs/02_catalogo_fonti_dati.md) — catalogo tecnico degli endpoint gratuiti verificati (FotMob, ESPN, Understat, football-data.co.uk, ClubElo, StatsBomb, Transfermarkt datasets, BSD, quote, meteo, notizie), limiti, id utili e schema dati minimo.
- [`docs/03_decisioni_e_funzionamento.md`](docs/03_decisioni_e_funzionamento.md) — decisioni prese (7 campionati, uso personale, quote) e spiegazione dell'automazione giornaliera.
- [`docs/07_fase3_giocatori.md`](docs/07_fase3_giocatori.md) — progetto delle schede giocatore (fase 3): dati misurati, metodologia percentili/radar, decisioni.
- [`docs/08_laboratorio_analitico.md`](docs/08_laboratorio_analitico.md) — matrice Dixon-Coles, scontro tattico, corsa xG, qualità tiri, probabilità in-play.
- [`docs/19_audit_totale_tre_aree_2026-09-14.md`](docs/19_audit_totale_tre_aree_2026-09-14.md) — audit in tre aree; **§4 = tabella P0/P1/P2, la coda di lavoro autoritativa**.
- [`docs/21_verifica_qqv_piano_2026-09-15.md`](docs/21_verifica_qqv_piano_2026-09-15.md) — verifica quantitativa/qualitativa/visiva e piano di miglioramento.
- [`docs/22_numeri_pubblicati_e_fonti_2026-09-16.md`](docs/22_numeri_pubblicati_e_fonti_2026-09-16.md) — coerenza dei numeri pubblicati e fonti che dicono il vero (backoff, sonda).
- [`docs/23_quote_e_rate_stabilizzate_2026-09-16.md`](docs/23_quote_e_rate_stabilizzate_2026-09-16.md) — stime stabilizzate, quote non più rate per 90, difetti del backoff ESPN.
- [`docs/25_revisione_lingua_e_parita_2026-09-17.md`](docs/25_revisione_lingua_e_parita_2026-09-17.md) — revisione completa del portale: il filtro che pubblicava titoli stranieri come italiani e la parità fra le 7 leghe.
- [`docs/26_revisione_totale_2026-09-17.md`](docs/26_revisione_totale_2026-09-17.md) — **revisione totale del progetto**: cosa è stato riverificato, i difetti trovati (potatura delle notizie, CSS fuori dalla wheel, anteprima che sovrascriveva il sito, DuckDB derivato versionato) e le decisioni aperte.
- [`docs/50_sito_fermo_e_sezioni_perse_2026-10-05.md`](docs/50_sito_fermo_e_sezioni_perse_2026-10-05.md) — incidente del daily, sezioni delle schede e misure del costo delle fonti.
- [`docs/51_sblocco_daily_concordanza_assenti_e_sportmediaset_2026-10-07.md`](docs/51_sblocco_daily_concordanza_assenti_e_sportmediaset_2026-10-07.md) — fix che ha sbloccato il daily e rimosso il feed RSS 404.
- [`docs/52_verifica_stato_costi_e_gate_2026-10-07.md`](docs/52_verifica_stato_costi_e_gate_2026-10-07.md) — gate ripetuti, limiti/costi delle fonti e misure delle cache.
- [`docs/53_revisione_totale_qualita_quantita_2026-10-07.md`](docs/53_revisione_totale_qualita_quantita_2026-10-07.md) — **revisione più recente**: salute della pipeline, quantità dei contenuti e decisioni dell'utente.
- [`docs/54_pr84_conflitto_e_registrazione_pr83_2026-10-07.md`](docs/54_pr84_conflitto_e_registrazione_pr83_2026-10-07.md) — perché la PR #84 è in conflitto e superata, e cosa è stato registrato al suo posto.
- [`docs/55_revisione_schede_prossime_partite_2026-10-07.md`](docs/55_revisione_schede_prossime_partite_2026-10-07.md) — revisione delle schede delle prossime partite, sezione per sezione, con i tre difetti misurati (Mercato ×1,8, EPV, meteo) e la coda.
- [`docs/56_lotto_p0_mercato_meteo_epv_m1_m4_2026-10-07.md`](docs/56_lotto_p0_mercato_meteo_epv_m1_m4_2026-10-07.md) — i due P0 (Mercato, Meteo) con le misure prima/dopo, l'EPV declassato a riga di contesto, M1–M4, le due invarianti nuove e i residui dichiarati.
- [`docs/57_schede_sezione_prepartita_fattori_2026-10-07.md`](docs/57_schede_sezione_prepartita_fattori_2026-10-07.md) — revisione delle schede sezione per sezione: le prime due coppie («Analisi pre-partita» + «Fattori», «Scontro tattico» + «Fatti rilevanti») con le invarianti nuove [41]/[42]; §7 = punti aperti.
- [`docs/58_schede_terza_coppia_come_arrivano_giocatori_2026-10-07.md`](docs/58_schede_terza_coppia_come_arrivano_giocatori_2026-10-07.md) — verbale della terza coppia (sessione parallela del 7/10 notte); numero in collisione con il doc `58` dei «Fattori» (incidente di scrittura parallela, vedi `docs/63` §8).
- [`docs/58_fattori_secondo_giro_misure_2026-10-08.md`](docs/58_fattori_secondo_giro_misure_2026-10-08.md) — secondo giro sulla card «Fattori che spostano la partita» — l'audit `scripts/audit_fattori.py`, due fattori nuovi misurati (rendimento per sede, disciplina e arbitro), tre candidati misurati e non pubblicati.
- [`docs/59_fattori_terzo_giro_2026-10-08.md`](docs/59_fattori_terzo_giro_2026-10-08.md) — terzo giro sulla card «Fattori» — corretto un errore di misura nel ⓘ del pressing, aggiunto il riferimento di lega al rendimento per sede, intestazione resa autonoma; due candidati valutati e non aggiunti.
- [`docs/60_come_arrivano_2026-10-08.md`](docs/60_come_arrivano_2026-10-08.md) — revisione di «Come arrivano» — la tendenza degli xG da 5 gare (57/66 schede invece di 28/66) e su creato **e** concesso, sede della gara evidenziata; xPTS non duplicato, [43] aggiornata.
- [`docs/61_giocatori_che_decidono_2026-10-09.md`](docs/61_giocatori_che_decidono_2026-10-09.md) — revisione di «I giocatori che decidono»: intro coerente col rendering, chiusura della terza coppia.
- [`docs/62_precedenti_fallback_2026-10-09.md`](docs/62_precedenti_fallback_2026-10-09.md) — **fix del fallimento del 10-08**: la card «Precedenti» era assente sulle gare senza h2h e fermava il gate `parita_schede`; ora è sempre presente con fallback dichiarato (PR #95).
- [`docs/63_revisione_affidabilita_daily_2026-10-09.md`](docs/63_revisione_affidabilita_daily_2026-10-09.md) — **revisione affidabilità del daily**: 26/43 run rossi in 30 giorni classificati per step e causa radice, riverifiche strutturali con misure, prove che la pipeline si aggiorna da sola; nessuna modifica di codice (regola B.10).
- [`docs/64_le_due_squadre_2026-10-09.md`](docs/64_le_due_squadre_2026-10-09.md) — **revisione della card «Le due squadre»**: verdetto xPTS sulla banda di rumore misurata (1σ = 1,13×√gare) al posto del ±2 fisso, riferimento di lega su ogni xG (1.784 rapporti, parità sulle 7 leghe), 4 alias Understat che eliminavano le fonti miste, media voto nella distinta pre-partita (1.176 celle dove c'era il vuoto), piè di card riscritto; poi finestra **alla vigilia** su 750 riquadri, infermeria che torna con le righe stampate (101 pannelli su 118 non tornavano) e **pressing in tutte e 7 le leghe** (caselle piene da 604 a 760 su 892); invariante **[44]**.
- [`docs/65_handoff_e_coda_fonti_2026-10-09.md`](docs/65_handoff_e_coda_fonti_2026-10-09.md) — handoff 2026-10-09: stato, coda operativa e prompt per la sessione nuova.

- [`docs/66_la_forma_dice_contro_chi_2026-10-09.md`](docs/66_la_forma_dice_contro_chi_2026-10-09.md) — Elo storico degli avversari nella forma, rango alla vigilia e giudizio solo oltre l'errore standard; gate [44] esteso.
- [`docs/67_modello_contro_mercato_offline_2026-10-09.md`](docs/67_modello_contro_mercato_offline_2026-10-09.md) — confronto RPS/Brier senza rete, quote già nello storico; 1.071 gare NED1/POR1, copertura e limiti dichiarati.

> L'**indice completo** dei 77 file `.md` di `docs/` (68 documenti numerati — il 09 non è mai esistito, il 58 è duplicato: collisione nota, `docs/63` §8 — + briefing + `STATO.md` + 5 archivi + 2 audit datati, più `_audit_modelli.json`) è nel briefing, sezione 6.

## Avvio rapido (sviluppo)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
fda leagues        # elenca i 7 campionati configurati
pytest -q          # test
```

## Come funziona (in breve)

`fda daily` = `collect` (FotMob, Understat, ESPN, Google News → `data/processed/*.parquet`) → `calibrate` → `predict` (Dixon-Coles + Elo) → `backtest` → `mercati-monitor` → `simulate` (Monte Carlo stagione) → `build` (sito in `site/`, incluse le schede giocatore). Ogni passo dopo `collect` è isolato: se cade, il run degrada e pubblica comunque.
GitHub Actions lo esegue 5 volte al giorno (`.github/workflows/daily.yml`), committa i dati e pubblica il sito su GitHub Pages.

### Attivazione (una volta sola, dal ramo `main`)
1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Actions → *daily* → **Run workflow** (primo run manuale; poi parte da solo con il cron).
3. **Nessun secret**: tutte le fonti usate sono gratuite e senza chiave. Le quote di mercato non sono pubblicate (decisione del 19/09/2026, `docs/38`).
