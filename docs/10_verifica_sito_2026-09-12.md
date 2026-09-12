# Verifica profonda di sito e progetto + correzioni (2026-09-12)

> **Data:** 2026-09-12 · **Sessione:** `arena/01a094e1-football-deep-analyzer` (da `main` `cb68f5a`)
> **Richiesta:** «controlla il sito ed il progetto per vedere se funziona tutto — sezioni, contenuti,
> calcoli e tecniche, fonti e collegamenti — aggiusta le cose che non funzionano».
> **Metodo:** `pytest -q`, `fda build` (4056 pagine), audit automatici su **tutte** le pagine,
> query su `data/processed/*.parquet`, confronto incrociato con i campi grezzi FotMob,
> controllo del sito live `uamisjd.github.io/football-deep-analyzer`. **Ogni numero è misurato.**

Lo strumento di verifica è ora nel repo: **`scripts/verify_site.py`** (contenuto + collegamenti +
ricalcolo numerico), con test in `tests/test_verify_scripts.py`. Esito finale:
**4056 pagine · 0 problemi · 140 controlli numerici superati** (prima delle correzioni: 1254 problemi
di contenuto e 14 difetti di calcolo/dati).

---

## 1. Cosa funzionava già (verificato, non presunto)

| Verifica | Esito |
|---|---|
| Suite di test | **91 passed** (erano 81 prima di questa sessione; +10 test nuovi) |
| Build sito | **347 partite + 2364 fixture + 7388 giocatori**, senza errori |
| Collegamenti interni | **0 mancanti** su 12.168 link (verifica su tutte le 4056 pagine) |
| Matrice punteggi | **105/105** pagine = `score_matrix(λh, λa, ρ)`, celle + coda = 100% |
| Probabilità in-play | **27/27** pagine: ogni riga somma 100 e l'ultima coincide col risultato |
| Accuratezza | **28 gare**, RPS pagina **0,2193** = ricalcolato 0,2193 (Brier 0,6656, esito 43%, naive 0,2412) |
| Proiezioni stagione | **7 leghe / 132 righe**, P(titolo)=1, P(top4)=4, P(retrocessione)=3 per lega |
| Parità 7 leghe | nessuna lega sguarnita (stesso controllo delle sessioni precedenti) |

---

## 2. Difetti trovati e corretti

### Calcoli e modelli

| # | Difetto | Evidenza misurata | Correzione |
|---|---|---|---|
| 1 | **τ di Dixon-Coles con λ scambiate.** `advanced.dixon_coles_grid` e `penaltyblog.create_dixon_coles_grid` applicano `1+λρ` e `1+μρ` a celle invertite rispetto a `DixonColesGoalModel.predict` (Dixon & Coles 1997 eq. 2.3) | differenza fino a **1,6e-2 su una cella** e **1,3 pp sull'1X2** (52,8% vs 54,1%); la ricostruzione corretta riproduce il modello a **2,8e-17** | nuovo modulo condiviso `src/fda/models/dc_grid.py` (`tau_grid`/`probability_grid`), usato da sito, `ensemble` e `season_sim`; test di regressione che **fallisce** con la τ vecchia |
| 2 | **Parametri DC al bordo dell'ottimizzazione** per chi ha 2-3 partite | Dortmund–Paderborn λ **1,02–0,19** (Over 2,5 al 12%) con attacco Paderborn **−2,5** (limite del risolutore) contro 0,71 xG/gara reali; anche Schalke −2,5, Coventry −2,45, Hull −2,49 | **shrinkage** verso la media di lega con `f = w/(w+8)`, `w` = peso temporale delle partite; medie di lega riportate al valore del fit (gauge invariante). `MODEL_VERSION` → `dc-elo-ens-0.2` |
| 3 | **Doppia chance incoerente col 1X2 pubblicato** | `p_1x − (p_home+p_draw)` fino a **1,14 pp**; intero a schermo incoerente nel **14,3%** delle 105 previsioni | `ensemble()` ricalcola 1X/12/X2 come somme del 1X2 mediato |
| 4 | **Autogol ribaltato nella cronaca e nelle probabilità in-play** | su 226 partite finite (22 con autogol): usando `isHome` tal quale il conteggio finale torna **225/226** e **22/22** sui casi con autogol; ribaltandolo **0/22** | `wp_path` non ribalta più; `timeline` espone `scorer_home = is_home ≠ own_goal` per l'etichetta della squadra del marcatore |
| 5 | **Punteggio della cronaca «prima» mostrato come «dopo»** | `homeScore`/`awayScore` di FotMob = punteggio **prima** del gol: **226/226** | `timeline()` ricostruisce il punteggio progressivo (Angers–Rennes: 0-1, 0-2, 1-2 invece di 0-0, 0-1, 0-2) |
| 6 | **Gol duplicati dalla fonte** finivano in cronaca e nelle probabilità in-play | Union Berlin–Schalke 11/09: Aouchiche 46' e 48' con gli stessi campi punteggio | evento gol il cui «punteggio prima» non coincide con la sequenza → scartato |
| 7 | **Tiri in porta sovrastimati** | `isOnTarget=True` su **1688** tiri bloccati; Angers–Rennes 15 «in porta» contro i 3 ufficiali | `_on_target` = (gol o parata) e non bloccato e non autogol → **476/478 (99,6%)** di concordanza con `ShotsOnTarget` (prima 94,8%) |
| 8 | **Conteggi tiri diversi dagli aggregati FotMob** | i nostri 20 tiri dell'Angers contro `total_shots` 19: la differenza è l'autogol | `shot_summary` esclude gli autogol → **475/478 (99,4%)** di concordanza |

### Dati e raccolta

| # | Difetto | Evidenza misurata | Correzione |
|---|---|---|---|
| 9 | **Formazioni accumulate da snapshot diversi** | **573 coppie** (partita, giocatore) in doppia riga su 15985; titolari per squadra da 11 a **22**; pagine con 13-19 nomi | `Store.upsert(..., replace_by="match_id")`: le tabelle per-partita sono snapshot e vengono **sostituite**, non fuse; chiave `lineup` senza `role` |
| 10 | **Sostituzioni perse** | tutte le 1558 sostituzioni hanno `player_id` nullo → due sostituzioni allo stesso minuto collidevano sulla chiave: **6,5 per partita** invece di ~10 | stesso `replace_by` (nessuna dedup per chiave sugli snapshot); test dedicato |
| 11 | **Partite finite mai rinfrescate** dopo la correzione | `already` le escludeva per sempre | `COLLECT_SNAPSHOT = 2` in `match_info`: le finite salvate con versione più vecchia vengono riscaricate, **max 6 per lega per run** (~42 richieste, nel budget 600 con ~504 già usate) |
| 12 | **Squadre sdoppiate** (identità) | Frankfurt con +2,0057 di attacco su 2 gare: «Eintracht Frankfurt» e «Frankfurt» contate come squadre diverse | alias aggiunti (Frankfurt, Nottm Forest, Den Haag/ADO, Cambuur, Académico Viseu, Marítimo) e `soft_key` senza apostrofi → **19/19** alias OK e **0** nomi FotMob fuori dalla mappa |

### Contenuti a schermo

| # | Difetto | Evidenza misurata | Correzione |
|---|---|---|---|
| 13 | **`nan` nel titolo delle schede giocatore** | **285/3694** giocatori senza `usual_position_id`; con pandas 3 `nan` è truthy in Jinja → **292 pagine** con «Amad Diallonan» | `_label_or_none()` → «ruolo n.d.»; **0** pagine con `nan` |
| 14 | **Concordanza singolare/plurale** | **1098 occorrenze** («1 gare» ×1020, «1 pareggi» ×36, «1 vittorie» ×31, «1 rigori» ×6, «1 precedenti» ×4, «1 tiri») | filtro `it_plural` + `plural_it` (con la regola -io → -i: pareggio/pareggi) applicato a template e testo narrativo |
| 15 | **Decimali col punto** | «peso DC 0.7» su **105** pagine, «+3.0 punti» su **51**, KB in `stato.html` su **17** | filtro `dec`/`fmt.dec` nei tre punti |
| 16 | **Testo FotMob non tradotto** | xG con punto decimale (`1.69`) su ~478 righe × 5 chiavi; meteo «Rain Shower», «Few Showers», «Light Rain with Thunder», «Scattered Thunderstorms»; «RegularPlay» in `info.html`; «clean sheet»; «Club Friendlies», «League Cup Grp. A» nei precedenti | `_stat_text_it()`, `_weather_it()` composizionale, `SITUATION_IT`, `_competition_it()` |
| 17 | **Conteggi di conteggio con decimali** | statistiche per-90 formattate a 2 decimali anche per i conteggi | `StatDef.count` + `int_it` (20 statistiche) |
| 18 | **Formazioni con più di 11 nomi** | 61 squadre-partita finite con ≠11 titolari | se ci sono più righe e almeno 11 hanno il voto di partita (snapshot ufficiale) → si mostrano quelle: **11 esatti in 472/478**; senza voti (partita da giocare) nessun taglio arbitrario, ma nota esplicita |
| 19 | **Ruoli dei giocatori spostati di uno** (trovato implementando le card giocatori/assenze) | `POSITION_NAMES` partiva da **1**, ma la codifica FotMob `usualPosition` parte da **0**: su 616 formazioni il valore 0 compare 632 volte (1,03 a formazione) ed è il portiere in 600/600 formazioni che lo contengono (Lazio 12/09: Mandas n. 35 = 0, Doekhi/Provstgaard = 1, Frattesi = 2, Zaccagni = 3). Ogni riga di distinta era etichettata col ruolo precedente e il portiere restava senza etichetta; sugli indisponibili `usualPosition` è sempre vuoto (0/1340) e `positionId` vale 1000/1100 (vocabolario diverso) → ruolo mai mostrato | `POSITION_NAMES` ricentrata su 0-3; mappa `POSITION_ID_ROLE` per i `positionId` tattici tenuta solo dove ≥20 titolari concordano nel 90% dei casi (11 portiere 632/632, 33-38 difensori, 64-77 centrocampisti, 105/106/115 attaccanti); fallback sullo storico delle distinte per gli assenti (99/248 assenti di oggi). Verificatore: **648 ruoli** pubblicati ricontrollati |

---

## 3. Verifiche finali

- `pytest -q` → **91 passed** (10 test nuovi: τ del modello, shrinkage, λ ricostruite, doppia chance,
  snapshot/`replace_by`, sostituzioni allo stesso minuto, distinta a 11, gol fuori sequenza, plurali,
  verificatore del sito). *(Aggiornamento 2026-09-12, secondo giro: **101 passed** con i 9 test di
  `tests/test_oggi_depth.py` sulle card di profondità.)*
- `fda build` → 347 partite + 2364 fixture + 7388 giocatori.
- `scripts/verify_site.py` → **4056 pagine, 0 problemi, 140 controlli numerici superati**.
  *(Secondo giro, dopo le card di profondità: **1082 controlli** — il nuovo passo `[5]` ricontrolla
  **648 ruoli**, **108 conteggi di indisponibili** e **103 archivi di precedenti** contro le tabelle.)*
- Esempi ricontrollati pagina per pagina: `partite/5802919.html` (cronaca 0-1/0-2/1-2, tiri 19 (3),
  xG 1,69-1,36 con virgola, nota sull'xG dei tiri mappati), `giocatori/1070052.html` («Amad Diallo ·
  ruolo n.d.»), `partite/5881162.html` (Karetsas indisponibile fuori dalla distinta).

## 4. Cosa resta aperto (dichiarato, non nascosto)

1. **Le previsioni pubblicate non cambiano finché non gira `fda predict` con la rete.** Lo shrinkage
   e la τ corretta sono nel codice; le λ in `predictions` sono quelle del run precedente. Dopo il
   merge, al primo `daily`: controllare che Dortmund–Paderborn non abbia più λ ~0,2 per il Paderborn
   e che `dc_attack_*` non sia più a ±2,5 per le neopromosse.
2. **Le partite già archiviate guariscono in ~1-2 giorni** (6 per lega per run, ~42 richieste/run):
   fino ad allora le formazioni delle **future** possono ancora mostrare più di 11 nomi, con la nota
   esplicita a schermo.
3. **Due anomalie residue della fonte** (non nostre): per Rennes in Angers–Rennes FotMob conta 17 tiri
   e xG 1,36 negli aggregati di squadra ma ne elenca 18 con xG 1,69 nella mappa (il tiro di Cresswell
   61' non è nei suoi totali). La nota nella card spiega la differenza.
4. **Il merge della PR lo fa l'utente** (policy `docs/00_regole_di_lavoro.md` sez. D).
