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

- [`docs/68_revisione_forma_mercato_2026-10-10.md`](docs/68_revisione_forma_mercato_2026-10-10.md) — revisione indipendente della PR #98: numeri confermati, conteggi a data fissata e tre lacune dei controlli corrette.
- [`docs/69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md`](docs/69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md) — coda verificata dopo la PR #98: decisione sui tre tilt con misure rigenerate, «forza avv.» storica già misurata, riconciliazione dei due ΔRPS col mercato.

- [`docs/104_revisione_totale_2026-10-13.md`](docs/104_revisione_totale_2026-10-13.md) — **revisione totale del 13/10**: salute misurata da zero (943 test e 241.754 controlli **al momento della revisione**; 988 e 241.774 dopo `docs/105`-`docs/106`), copertura della rassegna per lega, crescita del repository con le opzioni di contenimento.
- [`docs/105_una_fotografia_al_giorno_2026-10-13.md`](docs/105_una_fotografia_al_giorno_2026-10-13.md) — **politica adottata**: i dati entrano in `main` una volta al giorno (−80% di crescita, sito invariato), con il registro preregistrato fuori dalla regola.
- [`docs/107_revisione_totale_2026-10-14.md`](docs/107_revisione_totale_2026-10-14.md) — revisione totale del 14/10: sito live, GitHub, coda residua.
- [`docs/108_previsione_e_verifica_misura_2026-10-15.md`](docs/108_previsione_e_verifica_misura_2026-10-15.md) — chiusura del ciclo schede: le 59 pre-partita complete su tutte e 8 le sezioni e la tendina `#verifica` tolta dalle 211 finite senza previsione (misura prima/dopo).
- [`docs/109_revisione_totale_2026-10-15.md`](docs/109_revisione_totale_2026-10-15.md) — **revisione totale del 15/10**: gate rimisurati da zero (1.034 test · 242.987 controlli · 0 problemi), politica di crescita «una fotografia al giorno» **misurata** (−77% di byte scritti), confronto con la letteratura sull'RPS, coda e decisioni aperte.

> `docs/` ha **123** file `.md` (**110** documenti numerati, da `00` a `109` — il 09 non è mai esistito, il 58 è duplicato: collisione nota, `docs/63` §8 — più briefing, `STATO.md`, 6 archivi, 5 fra audit e correzioni datate e 6 file `.json` di audit). L'**albero essenziale** con la descrizione dei documenti è nel briefing, sezione 6 (arriva fino a `docs/69`): l'elenco completo dei file è `ls docs/`, e i lavori più recenti stanno nella cima di `docs/STATO.md` e in `docs/101`. La revisione indipendente più recente è [docs/109](docs/109_revisione_totale_2026-10-15.md), dopo [revisione 14/10](docs/107_revisione_totale_2026-10-14.md), [audit 13/10](docs/AUDIT_COMPLETO_2026-10-13_7c92c1a2.md) e [correzioni 14/10](docs/CORREZIONI_AUDIT_2026-10-14.md).

## Avvio rapido (sviluppo)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
fda leagues        # elenca i 7 campionati configurati
pytest -q          # test
```

### Esperimento xG isolato

`fda lab-xg` esegue **una sola ricetta preregistrata**, offline, senza cambiare il modello
in produzione o il riepilogo pubblico del laboratorio. Protocollo e limiti:
[docs/92](docs/92_protocollo_dc_xg_2026-10-12.md). Previsioni per gara e rapporto vengono
salvati in `data/cache/lab_xg/` (non versionati); l'esito del giro viene documentato in `docs/93`.

Il comando controlla gli hash degli input: se un nuovo `daily` li ha cambiati, **si ferma**
invece di ritestare una ricetta su un campione diverso. Per riprodurre lo snapshot originale,
senza sovrascrivere i dati correnti (il commit deve essere presente nel clone):

```bash
mkdir -p data/cache/lab_xg_input
git show 514309d:data/processed/understat_matches.parquet > data/cache/lab_xg_input/understat_matches.parquet
git show 514309d:data/processed/history.parquet > data/cache/lab_xg_input/history.parquet
fda lab-xg --data data/cache/lab_xg_input
```

## Come funziona (in breve)

`fda daily` = `collect` (FotMob, Understat, ESPN, Google News → `data/processed/*.parquet`) → `calibrate` → `predict` (Dixon-Coles + Elo) → `backtest` → `mercati-monitor` → `simulate` (Monte Carlo stagione) → `build` (sito in `site/`, incluse le schede giocatore). Ogni passo dopo `collect` è isolato: se cade, il run degrada e pubblica comunque.
GitHub Actions lo esegue 5 volte al giorno (`.github/workflows/daily.yml`), committa i dati e pubblica il sito su GitHub Pages.

### Attivazione (una volta sola, dal ramo `main`)
1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Actions → *daily* → **Run workflow** (primo run manuale; poi parte da solo con il cron).
3. **Nessun secret**: tutte le fonti usate sono gratuite e senza chiave. Le quote di mercato non sono pubblicate (decisione del 19/09/2026, `docs/38`).

## Verifiche riproducibili e pubblicazione (14/10/2026)

```bash
pip install -c requirements-ci.txt -e ".[dev]"
python -m pytest -q
ruff check .
fda build
python scripts/verify_site.py --site site --data data/processed
python scripts/parita_schede.py site
python -m scripts.resa_375
# Crescita del repository: byte scritti al giorno e proiezione (docs/105, docs/109 §4)
python -m scripts.crescita_repo --days 10 --da 2026-10-14 --repo uamisjd/football-deep-analyzer
# Opzionale in locale, obbligatorio nella CI PR: browser vero e axe WCAG AA
npm ci
npx playwright install --with-deps chromium
npm run test:browser
```

`requirements-ci.txt` congela le versioni runtime/dev verificate su Python 3.11; non contiene
hash di integrità e non certifica assenza di CVE. I browser test usano un campione pre/post delle
sette leghe a 375/1280 px, temi chiaro/scuro, toggle e link interni. Il report in
`browser-results/` è generato, non versionato. Non è una certificazione completa WCAG.

Nel daily, `scripts/pubblica_dati.py` salva i dati in un **worktree temporaneo isolato**:
commit/rebase/push non toccano il checkout della build. Le fotografie complete hanno marker
`FDA-SNAPSHOT: full-v1`; i commit del solo registro prospettico **non** spostano la loro data.
L'allerta di ripristino viene emessa solo dopo **raccolta e deploy riusciti**. Il cron è
nominale, non una garanzia di puntualità. Un merge resta soggetto alla policy del progetto.

### Licenza e dati di terzi

La licenza MIT già dichiarata per il codice è riportata in [`LICENSE`](LICENSE). Non concede
nuovi diritti sui dati o articoli di terzi: si applicano le condizioni delle rispettive fonti,
e ai font la licenza contenuta in `src/fda/site/assets/fonts/LICENSE.txt`.
