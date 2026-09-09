# Verifica del progetto + prossimi passaggi (audit 2026-09-08)

> **Data:** 2026-09-08 · **Sessione:** `arena/01a082e0-football-deep-analyzer` (da `main` `723ad7f` = merge PR #17)
> **Metodo:** `pytest -q` (65 passed), `ruff` (`--select F` pulito / `E501+E741` 216), `fda build` (141 pagine partita + 2364 fixture), ispezione `src/fda/`, query su `data/processed/*.parquet`, `gh pr list`, ricerca web mirata. **Ogni numero è misurato, non presunto.**

> **Aggiornato (stessa sessione, turno 2):** implementata la card pre-partita **«Giocatori da tenere d'occhio»** (top per media voto di stagione FotMob con gol/assist stagionali) — **su tutte le 7 leghe** (73 pagine pre-partita). Diffidati (`M2`) **non** implementati: dati non sufficientemente accurati (vedi §4).

> ⚠️ **Nota sul dataset nel repo:** l'ultimo run dati in `data/processed` è del **2026-09-08 20:31 UTC**, eseguito **prima** del merge di PR #16 (20:33 UTC) che ha introdotto l'**Open-Meteo**. Per questo la tabella `weather_forecast` **non esiste ancora** nei dati (non è un bug: va popolata al primo `daily` post-merge). Tutte le altre conclusioni di sotto sono basate sul codice e sui dati correnti.

---

## 1. Cosa funziona (verificato e misurato)

| Verifica | Esito |
|---|---|
| Suite di test | **64 passed** (`pytest -q`, ~10 s) |
| Build sito | **141 pagine partita + 2364 fixture**, senza errori |
| Parità tra le 7 leghe | **73/73** partite nei prossimi 7 giorni con previsione, distribuite su **tutte** le 7 leghe (10–13 per lega) |
| Classifiche | `fotmob_standings` = **132 righe** = tutte le squadre delle 7 leghe |
| Completezza schede future (audit) | **490 «presente» + 459 «atteso» + 0 «mancante»** su 73 partite |
| Monte Carlo stagione | `season_sim` = 132 righe, pagina `stagione.html` attiva |
| Accuratezza live | **20 gare valutate** su 6 leghe, RPS **0,2045** vs naive 0,2385 (Δ **−0,034**) |
| Integrità repo | worktree pulito; `.venv/` e `site/` gitignored |

**Conclusione:** la direttiva «parità tra le 7 leghe e schede piene, nessuna lega di serie B» è **raggiunta e verificata**. Non ci sono più leghe sguarnite.

---

## 2. Cosa manca / deve essere ancora verificato

### 🔴 P0 — Verifiche dal vivo (non bloccanti sul codice, ma da confermare in Actions/PC)

1. **Open-Meteo + `future_days=7` (il principale punto aperto).** Il codice è collegato (`collect.py` passo `weather_forecast`, fallback in `analysis._weather`), ma la tabella **non è ancora stata prodotta** perché il run dati in repo è antecedente al merge PR #16. Al primo `daily` post-merge va verificare: tabella `weather_forecast` popolata **e** schede «(previsione Open-Meteo)» sui futuri oltre le ~48 h. Non verificabile dal sandbox (`api.open-meteo.com` irraggiungibile, `SSL_ERROR_SYSCALL`).
2. **ESPN standings 403 cronico.** 7/7 leghe in **AVVISO** (già declassato da ERRORE). È innocuo (FotMob è la fonte primaria della classifica) ma sporca la pagina "Stato fonti". Opzioni: rimuovere la chiamata `standings` (costo 0) o lasciare l'avviso. Decisione da prendere.

### 🟠 P1 — Lavoro di codice (oggetti delle prossime sessioni)

3. **B5 — Client SofaScore scritto ma mai collegato.** `src/fda/sources/sofascore.py` + `tests/test_sofascore.py` esistono, ma **nessun punto di `collect.py` lo usa** → codice morto. Decisione: **collegarlo** (fallback per formazioni ufficiali/arbitro quando FotMob è in ritardo, rispettando ToS e rate-limit: endpoint pubblici non ufficiali) **oppure rimuoverlo**. SofaScore non è raggiungibile dal sandbox.
4. **M2 — Diffidati (non implementati).** Non c'è alcuna sezione diffidati nelle schede; FotMob non li espone. **Fattibile** contando i gialli stagionali dalla tabella `events` con soglie per lega (Serie A: 5º giallo → squalifica; poi 4, 3, 2, 1 — altre leghe hanno regole diverse, alcune con playoff/barrage). Da fare con attenzione: variabilità delle regole per lega e distinzione dei gialli (da gioco vs da proteste).
5. **M3 — Schede giocatore (Fase 3, avviata con la card «Migliori in campo»).** Dati già pronti: `understat_players` **1954** giocatori con `xg/xa/minutes/position`; `player_stats` **127.880** righe (134 partite); `top_players()` già in use. Prossimo passo naturale: pagina/segmento giocatore con **rating, xG/xA per 90, percentili per ruolo** calcolati internamente (FBref è più ricco ma è uno scraper pesante e non copre tutte le leghe → usare i dati già raccolti).

### 🟡 P2 — Migliorie / igiene

6. **Tabella `insights` raccolta ma mai mostrata.** 824 righe da FotMob (`insights` in `fotmob.py`) vengono salvate ma **nessun template/analysis le legge** → dati morti. O mostrarle (es. «ha segnato in N gare consecutive»), o rimuoverle.
7. **Formazione: alcuni titolari senza rating.** Nella card "Formazione probabile" alcuni giocatori compaiono senza numero/rating. È onesto (niente dati inventati) ma visivamente spoglio; da chiarire se il rating manca perché non ancora pubblicato o perché il dato non è raccolto.
8. **Pulizia ruff.** `ruff --select F` **pulito**; restano **216 segnalazioni `E501`/`E741`** (baseline storica ~254). La CI esegue solo `pytest`, quindi non blocca; un turno `ruff --fix` + revisione ridurrebbe il rumore.
9. **`docs/STATO.md` molto lungo e con storico stantio.** Il file accumula lo storico delle sessioni; va snellito (storico in un file separato) e le intestazioni riallineate all'ultimo merge (PR #17).

### 🟢 P3 — Roadmap lunga / non prioritaria

10. **M4 — Quote vs modello**: non prioritaria per l'utente (direttiva registrata).
11. **M5 — Fase 5**: notifiche Telegram, xG proprio su StatsBomb Open Data, collettore locale per fonti protette, eventuale PWA.

---

## 3. Card aggiunta in questo turno: «Giocatori da tenere d'occhio»

**Motivazione.** La direttiva F (12 contenuti pre-partita) era già coperta su tutte le 7 leghe. L'unico gap di **profondità** colmabile in modo accurato con i dati già raccolti era una scheda sui **singoli giocatori**: c'era la card post-partita «Migliori in campo» ma nessun riferimento pre-partita ai giocatori chiave.

**Implementazione** (`src/fda/site/analysis.py` + `templates/match.html`):
- Nuovo metodo `team_key_players(team_id, n=3)`: top `n` per **media voto di stagione** (`lineup.season_rating`, FotMob), dedupe per `player_id` (una riga a giocatore), con **gol/assist stagionali** sommati da `player_stats` (verificato: 0 doppioni per match/player/chiave) e **posizione** (`POSITION_NAMES`).
- Chiavi `home_key_players`/`away_key_players` nel contesto `build()`.
- Card mostrata **solo in pre-partita** (`status != 'finished'`) per non duplicare «Migliori in campo»; senza media di stagione mostra un messaggio onesto. Nessun dato inventato.

**Verifiche (misurate):**
- **65 passed** (64 + 1 nuovo test).
- **ruff `--select F` pulito**; `E501/E741` **216 = baseline** (nessuna nuova).
- `fda build`: card presente in **73 pagine pre-partita** su **tutte le 7 leghe** (ITA1 10 · NED1 11 · ENG1 10 · FRA1 9 · ESP1 13 · GER1 9 · POR1 11).
- **0 occorrenze `nan` standalone** in tutto il sito (le 27 pagine segnalate in un primo controllo contenevano solo sottostringhe di parole reali: "Fernandes", "segnano", ecc.).
- Esempi reali: FC Twente–Telstar (Ruud Nijstad 7,99 · 1 gol; Younes Taha 7,85 · 1 gol 1 assist), Moreirense–Benfica (Vangelis Pavlidis 8,64 · 5 gol 2 assist).

## 4. Perché **non** ho implementato i diffidati (M2) — accuratezza > zelo

La direttiva è «prima si dimostra, poi si integra» e «nessun dato inventato». I dati attuali **non** supportano una card diffidati accurata su tutte le 7 leghe:
- **Big-5**: gli eventi (`events`) coprono solo ~10/30 gare finite per lega → totali di gialli stagionali **sottostimati**. L'alternativa (Understat `yellow_cards`) non allinea i nomi in modo affidabile (testato su Serie A: **~65%** di match FotMob→Understat, mancano anche giocatori reali e si includono gli allenatori) e copre solo il big-5.
- **NED1/POR1**: gli eventi coprono il 100% delle gare finite → gialli corretti. Ma un contenuto presente solo per 2 leghe violerebbe la **parità** (invertendo la gerarchia, esattamente il contrario della direttiva).
- **Stagione appena iniziata**: nessun giocatore ha più di 3 gialli (soglia 5) → la card sarebbe comunque **vuota** fin quasi a metà stagione.

I diffidati andranno fatti a metà stagione e con una fonte che allinei i nomi in modo affidabile su tutte le leghe.

## 5. Priorità consigliate (per la prossima sessione)

| Livello | Intervento | Sforzo | Effetto |
|---|---|---|---|
| **P0** | Verifica dal vivo Open-Meteo + `future_days=7` (primo `daily` post-merge) | 1 run | Chiude l'unico «vuoto» residuo delle schede future |
| **P0** | Decidere su ESPN standings 403 (rimuovere chiamata vs avviso) | 15 min | Pagina "Stato fonti" pulita |
| **P1** | B5 SofaScore: collegare o rimuovere | ~2 h | Togliere codice morto / aggiungere fallback reale |
| **P1** | M3 schede giocatore (rating, xG/xA per 90, percentili) | ~3–4 h | Fase 3 (la card di questo turno è un tassello) |
| **P1** | M2 diffidati (gialli stagionali) — **a metà stagione** | ~2–3 h | Contenuto pre-partita in più |
| **P2** | Motivare/rimuovere tabella `insights`; chiarire rating mancanti | ~1 h | Pulizia dati |
| **P2** | Pulizia ruff `E501/E741` + snellimento `STATO.md` | vari | Igiene del repo |

---

## Prossimo passo

La direttiva «parità di profondità e schede piene su tutte le 7 leghe» è **raggiunta e misurata**. In questo turno ho aggiunto la card **«Giocatori da tenere d'occhio»** (pre-partita, tutte le 7 leghe). Restano, in ordine: (1) **confermare dal vivo l'Open-Meteo** al primo `daily` post-merge; (2) chiudere **B5 SofaScore** (collegare o rimuovere), (3) **M3 schede giocatore**, (4) **M2 diffidati** a metà stagione; (5) igiene (ruff, `STATO.md`, tabella `insights`). Nessuna decisione bloccante spetta all'utente al momento.
