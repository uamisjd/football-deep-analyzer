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
