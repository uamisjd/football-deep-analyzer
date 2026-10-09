# 61 — Revisione card «I giocatori che decidono» (2026-10-09)

Metodo `docs/57`: per ogni difetto **misura → correzione → prova**. Regola `docs/00` B.10:
ogni modifica deve essere un miglioramento netto verificato prima di scrivere codice.

## 1. Difetto trovato (misura)

L'intro della card (`match.html`, `id="giocatori"`) descriveva il marcatore ◎ in modo
**contraddittorio rispetto al rendering**.

- Testo prima: «◎ è la stima stabilizzata della rata per 90: sotto i 270′ di campione,
  **al posto del valore grezzo** (che a quel punto è rumore) **si pubblica una stima** …».
- Rendering reale (fissato dal test `tests/test_verify_scripts.py:316`):
  `<span title="grezzo 5,68/90 · stima stabilizzata 4,62/90">5,68 <span class="mut small">◎ 4,62</span></span>`
  → sotto i 270′ (e ≥ `MIN_DEN_FOR_RATE = 90`, `src/fda/site/rates.py:52`) escono **sia il
  valore grezzo in grassetto sia la ◎ stima accanto**. Il grezzo non viene sostituito.

Quindi «al posto del valore grezzo si pubblica una stima» era falso: la stima è *affiancata*,
non sostitutiva. (La ◇, sotto i 90′, era invece descritta correttamente: lì il grezzo non esce.)

Seconda imprecisione: «**In classifica** entrano solo i giocatori con almeno il 40% dei minuti…»
— ambiguo su *quale* classifica. La soglia di minutaggio vale per **entrambe** le classifiche
della card (tabella contributi `key_players_deep` e lista voti `team_key_players`).

## 2. Correzione

Solo testo nell'intro (2 righe di `match.html`), nessun comportamento modificato:

- ◎ → «sotto i 270′ di campione la rata grezza è rumorosa, **quindi le viene affiancata la
  stima** …» (descrive ciò che la pagina mostra davvero).
- ◇ → «sotto i 90′ la rata grezza non si pubblica: **esce solo la stima**» (più limpida).
- «In classifica» → «**In entrambe le classifiche** entrano solo i giocatori con almeno il 40%…».

Vincolo rispettato: `tests/test_site.py:733` impone `corpo.count("◎ è la <b>stima stabilizzata</b>") == 1`;
la stringa è conservata identica.

## 3. Prova (gate)

- `pytest` → **540 passed** (incl. `test_site.py:733` sul count di ◎ e `test_verify_scripts.py:316`
  sul formato cella grezzo+◎).
- `ruff check src tests scripts` → pulito.
- `fda build` → 446 schede generate.
- `scripts/verify_site.py` → **nessun problema · 169.696 controlli numerici superati**.
- `scripts/resa_375` → **26.613 misure · 0 problemi a 375 px**.
- Card resa controllata a mano (`site/partite/5749690.html`): testo nuovo presente e corretto.

## 4. Residuo dichiarato — parita KO non causato da questa modifica (finding separato)

`scripts/parita_schede.py` chiude **KO (exit 1)**: 4 schede pre-partita
(`5749704` Frosinone–Sassuolo, `5781769` Heerenveen–Excelsior, `5802957` Le Mans–Toulouse,
`5868093` Deportivo A Coruña–Levante, tutte gare del 16/10) non hanno la sezione `#precedenti`.

Diagnosi (verificata, **non** imputabile a questa revisione):

- `git diff` = 2 righe nell'intro giocatori; la card Precedenti non è toccata.
- La card Precedenti è resa solo in presenza di dati h2h:
  `{% if c.h2h_pattern or c.h2h[0] is not none or c.h2h_list %}` (`match.html:464`).
- Quelle 4 gare non hanno righe in `data/processed/h2h.parquet` (0 precedenti in archivio);
  nel dataset **1.924 fixture pre-match su 1.989** sono senza h2h.
- Il build è **dipendente dalla data reale** (`build.py:243` `datetime.now(UTC)`,
  `build.py:498` seleziona `local_date > today_local`): al avanzare della data entrano nel set
  «in programma» gare senza h2h, e la card Precedenti sparisce → parita KO. Per questo i gate
  risultavano verdi in build precedenti (data antecedente) e KO oggi: è una fragilità strutturale, non
  una regressione di questa modifica.

Fix raccomandato (convenzione indicata dallo stesso `parita_schede.py`), da fare come
**intervento separato** su un'altra card: rendere sempre la card Precedenti con una riga di
fallback («Nessun precedente in archivio per questa sfida») quando manca l'h2h, e dichiarare
l'assenza strutturale in `ECCEZIONI`. Non incluso in questo commit per rispetto dell'ambito
(revisione richiesta = «I giocatori che decidono»).
