# 101 — Handoff completo per la nuova sessione: stato del progetto, architettura delle schede e coda delle ultime 3 sezioni (2026-10-13)

## 1. Stato esatto del progetto all'ingresso della nuova sessione

La sessione `arena/079933b1-football-deep-analyzer` si è chiusa il **2026-10-13** con la fusione su `main` della **PR #110** (eseguita dall'agente su ordine esplicito dell'utente: *«ok fai merge»*, deroga registrata in `docs/13` §9.26 e `docs/STATO.md`).

### Cosa è appena entrato in `main` con la PR #110 (4 commit)
1. **Hotfix dei 2 errori che bloccavano il workflow `daily` su `main` ([docs/99](99_diagnosi_daily_109_hotfix_2026-10-13.md), Issue #109)**:
   - `src/fda/site/templates/laboratorio.html`: corretta la concordanza singolare/plurale `1 campionati` → `{{ prosp.leagues_better|it_plural('campionato', 'campionati') }}` (riga 52) e `1 passaggio` (riga 12).
   - `src/fda/site/templates/match.html`, `scripts/verify_site.py`, `src/fda/site/club_news_checks.py`: corretta la concordanza `1 lettura sul tema` e allineata la regex dell'invariante `[20]` (`r"· (?:<b>)?(\d+) lettur[ae] sul tema"`) che falliva in presenza del tag `<b>` su `5749705.html` (Juventus).
2. **Filtro lingua V3 puro-Python `149/149` e diagnosi copertura per lega ([docs/98](98_lingua_copertura_2026-10-13.md) §6)**:
   - `src/fda/sources/news.py`, `tests/test_i18n.py`: `is_italian_news` raggiunge **149/149** (`0` falsi positivi, `0` falsi negativi) sul benchmark congelato `tests/fixtures/news_language_review_2026-10-13.json` con **0 MiB di RAM aggiuntiva** e fast-path con $\ge 2$ marcatori esclusivi italiani.
3. **Rifacimento completo della copertura e selezione di «Vita del club» (`#notizie`) ([docs/100](100_vita_club_ricerca_web_copertura_2026-10-13.md))**:
   - `src/fda/site/analysis.py` e `src/fda/site/club_news_checks.py`: finestra pre-partita portata a `NEWS_WINDOW_DAYS = 14` (allineata a `NEWS_RETENTION_DAYS = 14`), `team_tokens` esteso con `soggetto_tokens(team_name)` (esonimi italiani come *Lipsia*, *Colonia*, *Stoccarda*, *Nizza*, *Marsiglia*, *Siviglia*, *Maiorca*), esclusi da `_club_tokens` i prefissi condivisi (`real`, `borussia`, `olympique`, `sporting`, `manchester`, `madrid`, `paris`, `united`, `city`, `union`) e i sostantivi comuni italiani (`fortuna`, `santa`, `clara`, `ahead`, `eagles`, `saint`), corretta `altra_squadra` per i club di 3–4 lettere (`Lens`, `Ajax`, `Como`, `Pisa`, `Roma`, `PSG`, `PSV`, `Hull`, con guardia locativa `\ba\s+roma\b`), e introdotta la cache `team_player_names`.
   - `src/fda/sources/news.py`: estesa `ITALIAN_SEARCH_NAMES` per 17 club europei e abilitata l'attribuzione multi-club in `parse_espn_news` e `parse_direct_sports_rss`.
   - `src/fda/site/club_signals.py`: corretto `ricors[oi]` ed estesi i pattern club-agnostici per infortuni/recuperi, rinnovi contrattuali, provvedimenti e analisi tecnica (`31/31` invariato sul campione annotato, `0` falsi positivi sui controlli negativi).
   - `src/fda/site/templates/match.html`: impostato `<details class="news-context" open>` affinché i `285` fatti verificati della partita siano subito visibili su **58/58** schede pre-partita.
   - **Misura prima → dopo sulle 58 schede pre-partita**: schede con rassegna stampa attiva da **6/58 (`10,3%`)** a **33/58 (`56,9%`)** (`ITA1` `10/10`, `ESP1` `7/10`, `ENG1` `5/10`, `GER1` `6/9`, `FRA1` `5/9`); lati squadra con articoli da **7/116 (`6,0%`)** a **45/116 (`38,8%`)** (`12 → 67` articoli pubblicati; `7 → 49` lati e `13 → 101` segnalazioni su `audit_vita_editoriale.py`); schede con informazioni utili visibili subito in «Vita del club»: **58/58 (`100%`)**.

### Numeri dei gate di qualità alla chiusura
- **Test (`pytest -q`)**: **932 passed** (`0` falliti).
- **Linter (`ruff check .`)**: **0 errori** (`All checks passed!`).
- **Build (`fda build`)**: **493 schede partita** (`58` pre-partita + `435` finite), **2.364 fixture**, **7.594 giocatori**.
- **Verificatore (`scripts/verify_site.py`)**: **238.546 controlli numerici superati · 0 problemi** (54 invarianti attive: 31 indipendenti, 20 miste, 3 specchi).
- **Audit fonti (`scripts/audit_fonti.py`)**: **0 difetti bloccanti** (`132/132` squadre coperte).

---

## 2. Checklist immediata di ingresso per il nuovo agente (primi 2 minuti)

Appena si apre la nuova sessione:
1. **Verificare `.venv` e ambiente**:
   - In questo sandbox `.venv` può non persistere tra sessioni; se `.venv/bin/pytest` non esiste, ricrearlo subito con `python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]"`.
2. **Verificare stato Git e ultimo workflow `daily` su `main`**:
   - Eseguire `git status -sb` e `gh run list --branch main --limit 4`.
   - Controllare che il run `daily` attivato dal merge della PR #110 sia verde (`success`) e che l'issue automatica `#109` si sia chiusa automaticamente; se ci sono commit dati nuovi su `origin/main` prodotti dal `daily`, allineare il branch di sessione o verificare lo stato.
3. **Avviare il server di anteprima live su `0.0.0.0:8000`**:
   - Usare `start_process` con comando `.venv/bin/python -m http.server 8000 --bind 0.0.0.0 --directory site` e `name="Sito CalcioMetro"` (preferenza stabile dell'utente).

---

## 3. Stato della revisione delle schede partita (`src/fda/site/templates/match.html`)

L'utente ha chiesto di verificare e revisionare in profondità ogni sezione della scheda partita secondo due principi fissi (`docs/00_regole_di_lavoro.md` §B.10 e §F):
1. **Utilità concreta**: ogni sezione deve rispondere a *«a cosa mi serve per capire la partita o le squadre?»* con dati verificati, chiari, non ridondanti con le altre card e con parità sulle **7 leghe** (`ITA1`, `ENG1`, `ESP1`, `GER1`, `FRA1`, `NED1`, `POR1`).
2. **Misura prima/dopo obbligatoria (Regola B.10)**: prima si misura lo stato attuale sulle schede reali (`58` pre-partita e `435` finite presenti in `site/sitemap.xml`), si spiega all'utente come funziona la sezione e quali eventuali limiti/difetti ha, e si interviene solo dove c'è un miglioramento netto dimostrabile, accompagnato da test e invariante in `scripts/verify_site.py`.

### Sezioni già revisionate e chiuse
- `#lettura` («Analisi pre-partita» / «Lettura della partita») + `#fattori` («Fattori che spostano la partita») — `docs/57` §0–§6, invariante `[41]`.
- `#scontro` («Scontro tattico») + `#fatti` («Fatti rilevanti») — `docs/57` §8–§9, invarianti `[22b]` e `[42]`.
- `#arrivi` («Come arrivano») + `#giocatori` («I giocatori che decidono») — `docs/58`–`docs/62`, `docs/66`, `docs/72`, invarianti `[22]`, `[23]`, `[43]`, `[45]`.
- `#squadre` («Le due squadre»: forma, xG/xPTS, pressing, indisponibili, probabile formazione) — `docs/64`, invarianti `[18]`, `[44]`.
- `#confronto` («Confronto di stagione») + `#panchina` («Panchina e posta in gioco») + `#stato-squadra` («Stato della squadra») — `docs/78`–`docs/81`, invarianti `[19]`, `[21]`.
- `#mercato` («Mercato: arrivi e partenze») — `docs/56`, `docs/85`–`docs/95`, invariante `[26]`/`[39]`.
- `#clima` («Clima del club») — `docs/81`–`docs/84`, invariante `[49]`.
- `#notizie` («Vita del club») — `docs/96`–`docs/100`, invariante `[20]` + `club_news_checks.py`.
- `#arbitro-meteo` («Arbitro e meteo») — `docs/56`, invariante `[40]`.

---

## 4. Le ultime 3 sezioni in coda da esaminare e revisionare (mappa tecnica completa)

Restano esattamente **3 blocchi** della scheda partita per completare l'intero ciclo di revisione:

### 4.1. Sezione 1 in coda: **«Precedenti» (`#precedenti`)**
- **Dove vive nel codice**:
  - Template: `src/fda/site/templates/match.html` righe `650–670`.
  - Logica e calcolo: `src/fda/site/analysis.py`:
    - `h2h_summary(match_id)` / `h2h_matches(match_id, home_name, away_name, kickoff)` (legge `data/processed/h2h.parquet` raccolto da FotMob `matchDetails`).
    - `h2h_pattern(match_id, home_id, away_id, kickoff)` (costruisce il riepilogo storico `Bilancio (N)` unendo `h2h.parquet`, `fixtures.parquet` e `history.parquet`, con ciambella SVG, gol/gara, `% entrambe a segno`, `% Over 2,5`, striscia senza pareggi `draw_drought`, risultato più frequente `top_scores`, e sotto-serie `hp.venue` «di cui con X di casa» pubblicata da 8 casi in su).
    - `h2h_stats` e `h2h_trend_note` sugli ultimi precedenti elencati in tabella (`c.h2h_list`).
  - Verificatore: `scripts/verify_site.py` invariante `[7]` (verifica conteggi H2H, punteggi e coerenza della sotto-serie).
- **Cosa verificare e misurare subito**:
  1. Copertura sulle `58` schede pre-partita e sulle `435` schede post-partita per ciascuna delle 7 leghe: quante schede hanno `h2h_pattern`, quante hanno `h2h_list`, quante cadono nel segnaposto «Nessun precedente in archivio per questa sfida» (es. neopromosse o squadre con nomi non riconciliati tra `history.parquet` e FotMob).
  2. Coerenza tra `Bilancio (hp.n)` (che unisce `history.parquet` + `h2h.parquet`) e la tabella `Ultimi precedenti` (`c.h2h_list`, che mostra gli ultimi incontri da `h2h.parquet`): verificare che non ci siano duplicati, partite successive al `kickoff` della scheda (regola temporale alla vigilia!), o discrepanze di orientamento casa/trasferta (`g.res` dal punto di vista di `c.home_name`).
  3. Verificare la nota `M6` citata nei doc precedenti (sotto-serie `hp.venue` «di cui con X di casa», soglia di pubblicazione e chiarezza per il lettore).

### 4.2. Sezione 2 in coda: **«Previsione del modello ensemble» (`#previsione` e card collegate `#scomposizione`, `#laboratorio`, `#fascia-storica`, `#posizione-lega`, `#primo-gol`)**
- **Dove vive nel codice**:
  - Template: `src/fda/site/templates/match.html` righe `671–864`:
    - `#previsione` (`671–706`): barra 1X2 (`pct3`, somma esatta 100%), tabella mercati (`Gol attesi`, `Over 1,5 / 2,5 / 3,5` con confronto media lega `c.league_over`, `Entrambe a segno`, `Doppia chance 1X / 12 / X2` coerente con `b1x2`, `Porta inviolata casa / trasferta`), card affiancata `Risultati esatti più probabili` (`p.top_scores`, copertura sulla griglia 0–5 e coda 6+, Elo e forza DC attacco/difesa).
    - `#scomposizione` (`708–738`, «Come nasce questa probabilità»): passi della catena probabilistica (`c.prob_steps`, `c.prob_summary`) e waterfall $\Delta\text{pp}$ sul favorito.
    - `#laboratorio` (`740–784`, «Il laboratorio — idee misurate, non usate in questa previsione»): generata da `src/fda/site/laboratorio.py` (`docs/73`–`docs/74`), verificata dall'invariante `[46]`.
    - `#fascia-storica` (`786–804`, «Quando il favorito aveva questa forza»): calibrazione empirica fuori campione per fascia di pronostico (`c.fav_record` da `backtest.parquet`), con intervallo di Wilson al 95%.
    - `#posizione-lega` (`806–831`, «Dove si colloca questa partita»): percentile di $\lambda_{\text{tot}}$ nel campionato (`c.league_pos`) con barra visuale 2°–98° percentile.
    - `#primo-gol` (`833–864`, «Quando arriva il primo gol»): distribuzione a due tempi del primo gol (`c.first_goal`), probabilità «Chi segna prima» e confronto quarti d'ora osservati vs banda 25°–75° del modello.
  - Logica e calcolo: `src/fda/site/analysis.py` (`prediction`, `prob_steps`, `fav_record`, `league_pos`, `first_goal`, `league_over`), `src/fda/models/predict.py`, `src/fda/models/calibration.py`, `src/fda/site/laboratorio.py`.
  - Verificatore: `scripts/verify_site.py` invarianti `[8]`, `[10]`, `[11]`, `[12]`, `[15]`, `[16]`, `[17]`, `[46]`, `[47]`.
- **Attenzione — vincolo di protocollo**:
  - Qualsiasi modifica alla **ricetta matematica di produzione** (`predict.py`, `calibration.py`) richiede protocollo di laboratorio e griglia pre-registrata (`docs/00_regole_di_lavoro.md` §D). La revisione della sezione sulla scheda partita riguarda invece la **completezza, esattezza, coerenza interna, leggibilità e copertura sulle 7 leghe** di tutti i numeri, testi e grafici esposti in `#previsione` e nelle sue sotto-card.

### 4.3. Sezione 3 in coda: **«Verifica approfondita: risultati esatti e distribuzione gol» (`#verifica`: `#probabilita` + `#gol-totali`)**
- **Dove vive nel codice**:
  - Template: `src/fda/site/templates/match.html` righe `1118–1168`:
    - Tendina `<details class="card detail-card" id="verifica">` con riepilogo nel `<summary>` (`moda X gol · mediana Y`).
    - `#probabilita` (`1124–1142`, «Matrice dei punteggi»): matrice $6\times 6$ (`0–5` gol per squadra) + coda `6+ gol` (`m.p_tail`), cella modale evidenziata (`class="mode"`).
    - `#gol-totali` (`1144–1165`, «Quanti gol, in pratica»): istogramma per totale gol (`0..6`, `7+`) + quantile dotplot di Kay (`20` punti da `5` partite su 100 ciascuno, `gv.columns`), intervallo 10°–90° percentile (`gv.copertura`).
  - Logica e calcolo: `src/fda/site/analysis.py` (`score_matrix`, `goals`).
  - Verificatore: `scripts/verify_site.py` invarianti `[8]` (matrice dei punteggi) e `[9]` (distribuzione dei gol totali).
- **Cosa verificare e misurare subito**:
  1. Coerenza al decimo di punto tra i 6 risultati esatti di `#previsione` (`p.top_scores`), le celle della `Matrice dei punteggi` (`#probabilita`) e la somma delle barre in `#gol-totali` (inclusa la distinzione tra coda `6+ gol di una singola squadra` in `#probabilita` e coda `Totale 7+ gol della partita` in `#gol-totali`).
  2. Presenza e funzionamento su tutte le 493 schede (sia le 58 pre-partita sia le 435 finite provviste di previsione).

---

## 5. Regole d'oro e trappole tecniche da evitare nel sandbox

1. **Mai usare `pkill -f <pattern>` nei comandi `bash`**: la stringa del comando stesso contiene `<pattern>` in `/bin/bash -l -c ...` e uccide la subshell (`exit_code: -1`). Per terminare un processo Python specifico usare sempre:
   `ps -eo pid,comm,args | awk '$2=="python" && $0 !~ /http\.server/ {print $1}' | xargs -r kill -9`
2. **Non scansionare tutti i `2.364` file in `site/partite/*.html` quando si misurano le schede attive**: `site/partite/` può contenere file HTML di fixture future generati in test precedenti; l'elenco canonico delle **493 schede pubblicate** (`58` pre-partita + `435` finite) è sempre quello in `site/sitemap.xml` (o per le sole pre-partita: i file in `site/sitemap.xml` che contengono `"Analisi pre-partita"`).
3. **Italiano obbligatorio ovunque**: chat, documenti `docs/`, titoli delle PR, messaggi di commit e testi del sito.
4. **Push immediato dopo ogni passo concluso**: `git push origin <branch-della-sessione>` subito dopo ogni commit; mai accumulare commit solo locali.
5. **Policy merge**: non eseguire mai `gh pr merge` di propria iniziativa; quando una PR è pronta e con CI verde, fermarsi sulla frase fissa:
   `👉 Tutto verde: è il momento di fare Merge (PR #N).`
   (Eseguire il merge solo se l'utente lo ordina esplicitamente nel turno corrente, registrando la deroga in `docs/13` e `docs/STATO.md`).
