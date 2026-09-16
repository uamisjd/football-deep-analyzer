# 23 — Stime stabilizzate: chiusura di P1.14 e le quote trattate come rate per 90 (2026-09-16)

Sessione `arena/01a0aad1-football-deep-analyzer`. Questo documento consuntiva **un** intervento di
`docs/19` §4 (**P1.14**) e **due difetti nuovi trovati implementandolo** (§2), misurati sul sito
pubblicato prima e dopo. Ogni numero qui riportato è ricalcolabile dai Parquet committati e dalle
pagine generate; nessuna stima a occhio.

## §0 — Metodo

1. **Difetto prima, codice dopo.** Ogni intervento nasce da una misura sul sito/Parquet (quante
   celle, quali valori, quale pagina), non da un'opinione sullo stile.
2. **La prova di morso.** La misura viene ripetuta *dopo* la correzione con lo stesso strumento
   (regex sulle pagine generate, ricalcolo dai Parquet, controllo del verificatore).
3. **L'invariante resta.** Ogni classe di difetto chiusa lascia un controllo permanente in
   `scripts/verify_site.py` o nel file di test, così non può rientrare in silenzio.
4. **Dichiarare, non nascondere.** Dove un numero non è pubblicabile (campione minuscolo, gruppo di
   pari insufficiente) la pagina lo dice con una frase, non lo omette.
5. **Unità esplicite.** Ogni peso della contrazione è espresso nell'unità del denominatore della
   rata (minuti per le rate per 90, eventi per le quote) e lo dichiara nel tooltip.

## §1 — P1.14 ✅: la rata dei giocatori con pochi minuti era rumore travestito da fatto

**Osservato (docs/19 §1.10).** `_stat_row` conteneva una contrazione verso la media dei pari con un
prior di **180′ fissi** e una media presa dalle costanti di ruolo dell'**xG+xA** (0,02/0,12/0,28/0,42)
applicate a *qualunque* statistica; `p90_shrunk()` era codice morto.

**Misura (build prima della correzione).** 8.705 celle su 54.957 con una stima «stabilizzata»
(284 delle quali con un grezzo almeno triplo della stima); estremi pubblicati come fatti:
`90,00 tiri/90` su **1′** giocato, `15,30 xG+xA/90` per un assente con **1′** in stagione
(scheda `5795461`), `89,2%/90′` per una percentuale di passaggi su 90′. Con `den = minuti/90` e
`k = 2` il prior valeva 2 eventi/90: da 6 a 45 volte più debole del dovuto a seconda della scala
della statistica.

**Correzione.** Nuovo modulo `src/fda/site/rates.py` (nessun numero tarato a mano):

| elemento | definizione nel codice | valore misurato a settembre |
|---|---|---|
| media dei pari | `Σ conteggi / Σ minuti` sui pari con ≥ 270′ (ripiego ≥ 90′, dichiarato in `Pool.soglia`) | 2,8-8,6 per 90 secondo la statistica |
| peso `k` | `POOL_WEIGHT (0,25) × mediana dei minuti dei pari` | 88-90′ oggi, ~450′ a stagione piena |
| gruppi | (lega, ruolo) → (lega, tutti) → (tutte le leghe), minimo 8 pari per gruppo | 21 gruppi per statistica |

**Regola di pubblicazione** (`_stat_row`, `est_visibile`): ≥ 270′ si pubblica il grezzo; 90-270′ il
grezzo **con** la stima accanto (◎); < 90′ il grezzo **non** si pubblica, solo la stima (◇). Le
percentuali di lega (`_pct`) ordinano i giocatori sulla **stima**, non sul grezzo: la pagina lo
dichiara dal primo giorno e ora è vero.

**Verifica dopo.** `verify_site` **[32]** (nuovo) su 55.060 righe per-90 delle schede giocatore:
ogni cella ◇/◎ dichiara «media dei pari … /90 · peso k=… · n=…»; nessuna rata grezza sotto i 90′;
nessuna rata > 25/90 con campione < 270′. Conteggi: 35.102 stime (◇/◎), 0 celle marcate senza
nota, 0 problemi.

## §2 — Difetti nuovi trovati implementando P1.14

### §2.1 [P1] Le percentuali erano pubblicate come rate per 90 (e senza stima)

**Osservato.** Le celle «Passaggi riusciti %» e «Duelli vinti %» finivano nello stesso ramo delle
rate per 90: sotto i 90′ pubblicavano il grezzo (`33,3%` su **37′**, `44,4%` su **69′**) e il
tooltip lo etichettava **«89,2%/90′»** — cioè dichiarava una normalizzazione sui minuti che per una
quota non esiste (una percentuale di passaggi riusciti non cambia se il giocatore gioca 60′ o 90′:
il campione sono i *tentativi*). Il percentile di quelle statistiche era calcolato sul **grezzo**,
mentre la scheda scriveva «il percentile è calcolato sulla stima stabilizzata»: 2 assi su 6 del
radar dei difensori (Duelli %, e le barre extra) erano quindi ordinati per rumore su chi ha pochi
duelli.

**Misura.** 5.387 celle di quota nelle schede giocatore (549.060 celle per-90 totali); 103 tooltip
con «/90′» su celle **non pubblicabili** e 1.464 celle ◇ dopo la correzione nella fascia < 90′.

**Correzione.** Il denominatore di una quota sono gli **eventi** (`value = riusciti`,
`total = tentati` per i passaggi; `duel_won + duel_lost` per i duelli), non i minuti:

- `pool_of(..., filtro=minuti)`: la scelta dei pari resta sui **minuti** (una quota su mezza partita
  non dice dove sta il gruppo), la media dei pari si aggrega sugli **eventi** (somma riusciti /
  somma tentativi) e il peso `k` è `0,25 × mediana degli eventi` (25 tentativi, 30 duelli nei test);
- `player_pools(..., dens=…)`: il denominatore della rata è passato per statistica;
- `_stime_quota()`: contrazione nella scala giusta, usata anche per i percentili (radar compreso);
- `StatDef.num_label/den_label/unita_den`: il tooltip **dice la frazione** («765 passaggi riusciti
  su 900 tentati (totale stagionale): la percentuale non è una rata per 90 minuti»);
- `_titolo_cella()`: il testo del tooltip è costruito in Python e testato come dato (prima era
  spezzato fra due template, dove un ramo mancante produceva silenziosamente una cella vuota).

**Verifica.** `tests/test_rates.py` (+4: contrazione sugli eventi, filtro sui minuti, nota in
eventi, `dens` nei pool), `tests/test_players.py` (+3: ◇ sotto i 90′ con frazione esatta, grezzo
pieno con frazione, percentili sulla stima), `tests/test_verify_scripts.py` (+1 su **[32]** regola 4).

### §2.2 [P1] `◇` senza numero: il segnaposto poteva restare vuoto

**Osservato.** In `match.html` la cella «xG+xA/90» dei giocatori decisivi stampava
`◇ {{ p.contrib_p90_shrunk|dec }}`: `analysis.key_players_deep` emette il campo (verificato: riga
1987), ma **Jinja rende un campo assente come stringa vuota** e il ramo «non pubblicabile» avrebbe
stampato `◇` da solo — un marcatore di stima senza nulla da stimare. Difetto oggi latente
(0 celle vuote su 241 marcate), ma della stessa classe del `_stat_row` precedente.

**Correzione.** Terzo ramo esplicito: se il grezzo non è pubblicabile **e** il gruppo dei pari non
basta, la cella mostra `—` con la spiegazione nel tooltip. `check_stime` **[32]** ora ispeziona
anche le 376 schede partita: nessuna cella ◇/◎ senza numero, ogni ◇ dichiara «media dei pari» o
«gruppo dei pari» nel tooltip (241 celle verificate).

## §3 — Verifiche eseguite in questo turno

| Verifica | Comando | Esito |
|---|---|---|
| Suite completa | `.venv/bin/python -m pytest -q` | **339 passed** (316 a inizio sessione, +23) |
| Build sito | `.venv/bin/fda build` | exit 0 · `{'matches': 376, 'fixtures': 2364, 'players': 7478}` in ~3m30s |
| Verificatore | `.venv/bin/python scripts/verify_site.py --site site --data data/processed` | exit 0 · **nessun problema · 89.448 controlli** (erano 34.144 a inizio sessione) |
| Invariante nuove | `[32]` | 55.060 righe per-90 + 241 celle di scheda partita; 35.102 stime; 5.387 quote |
| Audit schede partita | `.venv/bin/python scripts/audit_match_sections.py` | #12 `stima_marcatore` 72 · `stima_senza_marcatore` 0 · #13 parità di lega invariata (media 8,3 righe narrative) |
| Ruff | `.venv/bin/ruff check .` | **173** segnalazioni (baseline pre-sessione 175: **2 in meno, 0 nuove**) |
| Celle quote dopo la correzione | scan delle 7.478 schede | 5.490 celle · 0 tooltip con «/90′» su celle pubblicate · 1.464 ◇ nella fascia < 90′ · 0 celle «—» senza spiegazione |

**Non verificato in questo turno** (regola B6): la resa a schermo con un browser reale (nessun
headless in sandbox) e il primo `daily` post-merge in Actions.

## §4 — Coda aggiornata

| # | Stato | Nota |
|---|---|---|
| P1.14 | ✅ **chiuso** (questo documento) | `rates.py` + regola di pubblicazione + `[32]`; `docs/19` §1.10 marcato ✅ |
| P1.11 | aperto | griglia pre-registrata nel laboratorio (`Candidate.grid`, `n_tentativi`) |
| P1.12 | aperto | griglia di calibrazione vs bounds (preferire il claim ridotto in `info.html`) |
| P1.15 | aperto | `prossime.html`: debounce del filtro + `content-visibility` sulle card |
| P2.x | aperti | pulizia e debito di `docs/19` §4 |

**Residui dichiarati di P1.14**: (a) la media dei pari include il giocatore stesso quando ha ≥ 270′
(è la media del *gruppo*, non «degli altri»; con 9-70 pari il peso del singolo è ≤ 1/10, e la nota
dichiara `n`); (b) il peso `k` misurato a settembre (88-90′) sale a ~450′ a stagione piena — i test
lo fissano sulla formula, non sul valore, quindi la stima si rivaluta da sola a ogni run; (c) le
statistiche di quota con `0` tentativi restano fuori dalla stima (nessuna quota senza
denominatore), e la cella lo dichiara.

## §3 — Il gate in CI ha morso: due difetti reali nel backoff (dopo il merge di PR #42)

**Come è stato scoperto.** Il daily partito col push del merge (run `35129006426`, 2026-09-16
17:34:12Z) è **fallito sul passo «Verifica il sito (verify_site)»** con 7 problemi, uno per lega:

```
PROBLEMI (7): {'espn:ENG1': 1, 'espn:ESP1': 1, 'espn:FRA1': 1, 'espn:GER1': 1,
               'espn:ITA1': 1, 'espn:NED1': 1, 'espn:POR1': 1}
  - stato.html: espn:ITA1 sospesa ma con 1 richieste nel run
```

Il gate ha quindi funzionato come previsto: ha fermato il run **prima** del commit dei dati e del
deploy. Ma ha fermato anche la mia capacità di capirlo: i log dei run non sono leggibili dal
sandbox (blob storage fuori allowlist) e l'artifact `run-log-*` contiene solo l'output di
`fda daily`, non quello dei passi successivi. Il workflow `diag` — creato il 2026-09-15 proprio
per questa classe di problemi — è stato esteso in questo turno: su un runner la rete funziona,
quindi ora scarica il **log dei passi falliti** (`gh run view --log-failed`, che segue il 302
verso il blob storage; `gh api .../actions/jobs/{id}/logs` restituisce 0 righe) e lo pubblica sul
branch `diag-logs`; il `run_id` si legge da `diag/trigger.txt` quando il workflow parte da un push.
Dal rosso alla diagnosi: **~15 minuti**, senza chiedere log a nessuno. *(La lezione è generale: un
gate che non si può diagnosticare è un gate che si finisce per spegnere.)*

### §3.1 [P1] La riga di una fonte sospesa contava le richieste di un'altra fase

**Osservato.** `report.requests` ha una chiave per **client** (`espn`), non per fase: la riga
`espn:ITA1` sommava la richiesta della classifica con quelle dello **scoreboard** (che non è in
backoff). Con la classifica sospesa la riga risultava «SOSPESA … 1 richiesta»: l'invariante [28]
(«una fonte sospesa non può avere richieste») leggeva un numero vero come se fosse una contraddizione.

**Impatto.** Due effetti, uno dei quali grave: (a) la pagina *Stato fonti* non distingueva più un
backoff **attivo** da un backoff **inesistente** — l'unico controllo che il progetto ha su questa
meccanica; (b) lo scoreboard, che funziona, era invisibile dentro una riga sospesa.

**Correzione.** Due righe e due contatori, uno per fase: la classifica mantiene la chiave `espn`
(**l'identità su cui cammina `backoff.state()`**: cambiarla avrebbe azzerato la serie dei
fallimenti) e lo scoreboard ha la sua riga `espn scoreboard`, con le sue richieste, le sue righe e
il suo esito. Aggiunto anche `error_prefix` in `CollectReport`: l'errore di una riga si cerca col
prefisso della **sua fase**, non con `startswith("espn")` (che attribuiva l'errore dello scoreboard
alla classifica quando solo la seconda falliva).

### §3.2 [P1] Una sonda che falliva riapriva la fonte: il costo reale era 5 volte il dichiarato

**Osservato.** In `state()` una sonda fallita veniva letta come **primo fallimento di una serie
nuova** (`fails = 1`): dopo ogni sonda servivano altri 4 tentativi prima di risospendere, quindi
il costo di una fonte rotta era ~5 richieste ogni 9 run invece di 1 ogni 5. Sul run incriminato
`espn:ITA1` aveva **76 fallimenti consecutivi** e una richiesta nel run.

**Correzione.** La serie dei fallimenti non si azzera più con le pause: si contano le pause in
testa e, dietro di esse, i tentativi falliti **saltando le pause delle serie precedenti**, fino al
primo run riuscito (che chiude la serie, come prima). Il ciclo di una fonte rotta è
`BACKOFF_PROBE_RUNS` pause + 1 tentativo = **5 run con una sola richiesta** (una al giorno con 5
run al giorno), che è il numero dichiarato in `docs/22` §3 e nella pagina.

**Test che lo fissa** (`tests/test_backoff.py`): simulando il ciclo a regime, **4 richieste in 20
run** (non ~11 come con la semantica precedente); una sonda fallita porta lo stato a
`(BACKOFF_FAILS + 1, 0)` e la fonte resta sospesa.

### Verifica di questo turno

| Verifica | Comando | Esito |
|---|---|---|
| Suite completa | `pytest -q` | **343 passed** (339 → +4, tutti nuovi casi sul backoff) |
| Prova del caso CI (classifica sospesa + scoreboard attivo) | righe sintetiche nello store + `fda build` + `verify_site` | **0 problemi · 89.455 controlli**; pagina: **7 righe `espn:*` SOSPESO con 0 richieste** + **7 righe `espn scoreboard:*` OK con 1 richiesta e 42 righe** |
| Ruff sui file toccati | `ruff check` | invariato sul baseline (0 nuove) |
| Attribuzione degli errori per fase | `tests/test_store_collect.py::test_lo_scoreboard_separato_dalla_classifica` | l'errore della classifica non finisce sulla riga dello scoreboard |

**Perché è urgente**: finché la correzione non è in `main`, **ogni run del daily fallisce al gate**
e il sito resta all'ultimo build buono (nessun aggiornamento dati né deploy).


## §5 — Lo scoreboard ESPN era l'unica fase fuori dal backoff, e il 403 era il suo (2026-09-16, ventitreesimo giro)

> **Nota sulla numerazione di questo documento.** Esistono **due §3**: il primo (§3 «Verifiche
> eseguite in questo turno», prima del merge di PR #42) e il secondo (§3 «Il gate in CI ha morso»,
> aggiunto dopo). I riferimenti esterni («`docs/23` §3») intendono **il secondo**, quello sui
> difetti del backoff. Non si rinumera per non rompere i riferimenti già scritti in `docs/19` §4,
> `docs/22` §3, `STATO.md` e nei messaggi di commit di PR #43.

**Come è emerso.** Il §3 ha dato allo scoreboard una **riga propria** in `source_status`
(`espn scoreboard:<lega>`): fino ad allora le sue richieste erano nascoste dentro la riga della
classifica. Il primo run con quella contabilità separata (**`35131980208`**, raccolta 18:09-18:11
UTC, dati committati in `c969b6b`) ha misurato la fase per la prima volta: **HTTP 403 su 7 leghe
su 7**, 1 richiesta ciascuna, **0 righe di dati**.

**La frase da correggere.** `docs/22` §3 e il docstring di `backoff.py` dichiaravano «lo
scoreboard ESPN, **che risponde**, resta attivo»: era un'**assunzione**, non una misura, e non
poteva essere misurata prima che la fase avesse una riga propria. Due fatti la smentiscono:

| Fatto | Misura |
|---|---|
| lo scoreboard risponde 403 | 7 righe `espn scoreboard:*` con `ok=False` ed errore `HTTP 403 .../scoreboard`, run 18:09-18:11 UTC |
| non ha **mai** portato un dato | in `data/processed/` non è mai esistito `espn_events.parquet`, né `espn_team_stats.parquet`, né `espn_standings.parquet` (`git ls-tree origin/main data/processed/`) |

**Il costo è lo stesso già giudicato inaccettabile in P1.9.** Lo scoreboard era l'unica fase ESPN
**senza** `sospensione()` (classifica e notizie ce l'avevano): 7 richieste a run × 5 run al giorno
= **35 richieste al giorno (~1.050 al mese) per zero righe**, più **7 righe rosse «ERRORE»** a
ogni run in *Stato fonti* (`ok=False, warn=False`: il 403 dello scoreboard non era in
`_WARN_NON_BLOCCANTE`) — lo stesso rumore identico che P1.9 aveva tolto alla classifica perché
«rendeva invisibile ogni guasto nuovo».

**Nessun impatto sui contenuti pubblicati** (verificato, non presunto): nessuna sezione del sito
legge `espn_events`/`espn_team_stats`; l'unico riferimento a una tabella ESPN nel codice del sito
è `analysis.py:601` (`store.read("espn_standings")`), riserva della classifica il cui primario è
FotMob — `Store.read` su tabella assente restituisce un DataFrame vuoto e le **132** righe di
classifica pubblicate vengono da `fotmob_standings`. Gli eventi del giorno sono di FotMob
(`events.parquet` 6.083 righe, +5 nel run).

**Correzione** (nello stile già usato per le due fasi, chiave = fonte + fase):

- `collect.py`: `sospensione(store, f"espn scoreboard:{lg.key}", "espn scoreboard")` **prima**
  della chiamata, come per classifica e notizie. La chiave è quella della riga introdotta dal §3,
  quindi la serie dei fallimenti parte dal run `35131980208`: la sospensione scatta dopo
  `BACKOFF_FAILS = 5` run (≈ un giorno con 5 run al giorno) e la sonda ogni `BACKOFF_PROBE_RUNS = 4`
  pause, quindi un rientro di ESPN viene visto da solo entro un giorno;
- `_WARN_NON_BLOCCANTE` += `"espn scoreboard"`: il degrado è coperto da FotMob → **AVVISO**, non
  ERRORE rosso, come per le altre due fasi;
- `note("espn scoreboard", …)`: il testo pubblicato in *Stato fonti* non dice più «sempre attivo:
  non è governato dal backoff della classifica», che era diventato falso;
- `backoff.py` (docstring) e `docs/22` §3: la frase «che risponde» è annotata come smentita dalla
  misura, con rimando qui.

**Nessuna modifica a `scripts/verify_site.py`**: l'invariante **[28]** è già generica su qualunque
riga «SOSPESO» (motivo + piano di ritentativo + **0 richieste**), quindi copre la fase nuova senza
toccare il verificatore — il fatto che basti cambiare la raccolta è la prova che l'invariante era
scritta nel punto giusto.

**Prova end-to-end sul caso reale** (stesso metodo del §3: righe vere + righe sintetiche nello
store, poi `fda build` + `verify_site`; il Parquet originale è stato ripristinato, `git status`
pulito):

| Passo | Esito |
|---|---|
| righe vere del run 18:22 nello store | 7 righe `espn scoreboard:*`, **7 richieste**, **0 righe di dati** |
| + 4 run falliti per lega fino alla soglia, + la riga di pausa che `collect_league` scriverebbe | `sospensione()` risponde per **7/7** leghe |
| `fda build` | exit **0** · 376/2.364/7.478 |
| `scripts/verify_site.py` | exit **0** · **nessun problema · 89.455 controlli** (+7: le righe nuove passano da [28]) |
| pagina *Stato fonti* | **15 righe ESPN tutte SOSPESO con 0 richieste · 0 righe in ERRORE** (prima: 7 rosse) |
| suite | **347 passed** (343 → **+4**: serie propria, indipendenza delle due fasi, integrazione con contatore delle richieste, costo a regime ora parametrizzato su **entrambe** le fasi) |
| ruff | **173** = baseline, 0 nuove |

**Da guardare nel primo daily che porta la serie a 5 run** (dal 2026-09-17): le righe
`espn scoreboard:*` devono passare da ERRORE a **SOSPESO con 0 richieste** e le richieste ESPN del
run devono scendere da **7 a 0** (tutte e tre le fasi ESPN in pausa: classifica, notizie, eventi).

**Prossimo passo.** La coda resta quella di `docs/19` §4: **P1.11** (griglia pre-registrata nel
laboratorio), poi P1.12 come *claim ridotto* in `info.html` e P1.15; P2.5 (indice completo di
`docs/`) è chiuso in questo giro nel briefing.
