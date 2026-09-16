# 22 — Numeri pubblicati coerenti e fonti che dicono il vero (16/09/2026, diciannovesimo giro)

> **Sessione** `arena/01a0aad1-football-deep-analyzer` · **data** 2026-09-16 · **base** `9c316bb`
> (= `main` dopo il daily del run `35112888322` e il merge di PR #41).
>
> **Richiesta utente:** «indaga e studia il sito ed il progetto su github e continua il lavoro
> nel modo migliore, tutto deve funzionare in modo preciso, accurato, profondo e di qualità; se
> trovi errori o qualcosa che abbiamo fatto male fin qui o qualunque errore informati bene su
> cosa fare».
>
> **Risultato in una riga:** trovati e corretti **due difetti reali nei numeri pubblicati**
> (29,1% delle schede pre-partita pubblicava una doppia chance che contraddice l'1X2 stampato;
> 26,7% delle righe «gol attesi» pubblicava un totale che non è la somma delle due cifre
> stampate) e **una fonte che falliva da 76 run di fila consumando 14 richieste a run** (ESPN
> 403), ora in backoff con stato «SOSPESO» e sonda settimanale del fallback Open-Meteo.
>
> Verifiche finali: suite **316 passed**, `fda build` 376/2.364/7.478, `verify_site`
> **0 problemi · 34.144 controlli**, ruff invariato sul baseline (175).

---

## 0. Metodo e ambiente

- `.venv` locale (Python 3.11.2): `pip install -e ".[dev]"` — il `pip` di sistema è bloccato da
  PEP 668, quindi ogni comando pesante passa dal virtualenv del repo.
- Baseline misurata prima di toccare il codice: suite **290 passed**, `fda build` 376 schede ·
  2.364 fixture · 7.478 pagine giocatore, `verify_site` **0 problemi · 32.884 controlli**,
  ruff 0.16.7 → **175** rilievi (baseline storica: non si aggiunge nulla di nuovo).
- Verifica P1.7 in produzione (il «da confermare» lasciato dal giro precedente): nei dati
  committati dal daily post-merge, `season_sim.parquet` (132 righe, 7 leghe) ha
  `top_n` = **4/4/4/4/3/2/1** (ENG1/ESP1/GER1/ITA1/FRA1/NED1/POR1), `p_top_n` che somma
  esattamente `top_n`, `p_top4` identico riga per riga all'alias. **Confermato dal vivo.**
- Il log dei run GitHub non è scaricabile dal sandbox (`EOF` su `results-receiver` e su
  `blob.core.windows.net`): tutte le verifiche «di rete» restano attribuite ad Actions
  (regola B6). I controlli qui sotto girano su **dati e pagine del repository**, non su ipotesi.

---

## 1. [corretto] La doppia chance pubblicata non era la somma dell'1X2 pubblicato

**Osservato.** Nella card «Previsione del modello» la riga *Doppia chance 1X / 12 / X2* era
stampata con tre `|round|int` indipendenti, mentre la barra 1X2 degli stessi tre esiti stampa i
numeri interi del **metodo del resto massimo** (`pct_triple`, già corretta per il difetto
docs/19 §3.3). I due numeri non potevano che contraddirsi.

**Misura.** Su **165** schede pre-partita: **48 (29,1%)** pubblicavano una doppia chance diversa
dalla somma dei due numeri stampati nella stessa card. Esempi reali:

| scheda | barra 1X2 stampata | doppia chance pubblicata | somma corretta |
|---|---|---|---|
| `5749661` | 51 / 23 / 26 | **75** / 77 / 49 | 74 / 77 / 49 |
| `5749673` | 73 / 17 / 10 | **90** / 83 / 28 | 90 / 83 / **27** |
| `5749675` | 43 / 27 / 30 | 70 / 73 / **56** | 70 / 73 / 57 |
| `5749676` | 49 / 27 / 24 | 76 / **74** / 51 | 76 / 73 / 51 |

Sui Parquet (tutte le 2.071 previsioni del modello corrente) le righe coinvolte sono **506
(24,4%)**, sempre con scarto di 1 punto percentuale; nei casi peggiori anche la somma dei tre
valori pubblicati non era 200, cosa **impossibile** per definizione (1X + 12 + X2 = 2·1X2).

**Non era un difetto dei modelli.** La derivazione era già corretta (`p_1x = p_home + p_draw`
in `ensemble()` e ripubblicazione dalla griglia in `calibrated_prediction`: verificato sui
Parquet, scarto massimo **0,0**). Era **formattazione**: due arrotondamenti indipendenti della
stessa quantità.

**Correzione.** I tre valori pubblicati sono ora la somma di due dei tre numeri stampati nella
barra (`match.html`): si verificano a mente e sommano 200 esatti. In `predict.py` l'invariante
`_assert_dc_coerente()` controlla la derivazione in `ensemble()` e in `calibrated_prediction()`:
una regressione fa fallire il run invece di pubblicare numeri impossibili.

---

## 2. [corretto] «1,40 + 0,99 (2,38 totali)»: il totale non era la somma dei due numeri stampati

**Osservato.** Ogni forma in cui il sito pubblica i gol attesi mostra due cifre a due decimali e
un totale; il totale era calcolato sui valori **grezzi** e poi arrotondato, non sulla somma
delle due cifre stampate.

**Misura.** **88 occorrenze su 330** (26,7%), di cui: hero della scheda **44/165**, card di
*Oggi*/*Prossime* **41/145**, più tooltip, description SEO e riga compatta del calendario.

| dove | pubblicato | somma delle cifre stampate |
|---|---|---|
| scheda `5749662` | 1,40 + 0,99 → **2,38** | **2,39** (λ grezze 1,39777 + 0,98512 = 2,3829) |
| scheda `5749672` | 1,54 + 1,41 → **2,94** | **2,95** |
| scheda `5749674` | 1,27 + 1,34 → **2,62** | **2,61** |
| scheda `5749681` | 1,40 + 1,51 → **2,92** | **2,91** |

Verificato lo stesso difetto in «Dove si colloca questa partita» (che ripete il totale) e nella
`<meta name="description">`, cioè **fuori dal sito**, nei risultati di ricerca.

**Correzione.** Un solo idioma per ogni somma pubblicata: `fmt.displayed` (il numero come lo
stampa `dec`), `fmt.displayed_sum` (la somma delle cifre stampate) e il filtro Jinja `dec_sum`.
Usato in `match.html` (hero + «Dove si colloca»), `_matchlist.html` (riga e tooltip),
`build.py` (riga del calendario e description SEO). Regola generale registrata nel codice:
**un numero derivato pubblicato si calcola su ciò che è pubblicato.**

**Non difetti** (verificati uno per uno con lo stesso metodo, per non dichiarare problemi
inesistenti): hero vs barra 1X2, «esito più probabile» vs massimo della barra, Over 2,5 e
«entrambe a segno» hero vs riga della tabella, copertura dei sei punteggi più probabili vs
somma delle sei percentuali stampate → **0 incoerenze** su tutte le pagine.

---

## 3. [corretto] ESPN fallisce da 76 run: 14 richieste a run e 14 avvisi identici

**Osservato.** `espn.api.espn.com` risponde **HTTP 403** dall'IP dei runner su classifica e
notizie; il 403 è già classificato come avviso non bloccante perché FotMob copre la classifica e
Google News le notizie.

**Misura (sui dati versionati, non su ipotesi).**

- `state()` sullo storico `source_status` al 2026-09-16: `espn:ITA1` ed `espn:ENG1`
  **76 fallimenti consecutivi**, `espn:POR1` **75**, `espn:NEWS` **8**;
  `fotmob:ITA1` e `understat:ITA1` **0** (sani, non toccati).
- Costo: **14 richieste a run** (7 classifiche + 7 notizie) = **70 al giorno** per un dato già
  coperto, e 14 righe di avviso identiche nella pagina *Stato fonti* — dove un guasto **nuovo**
  diventa invisibile.

**Correzione (`src/fda/backoff.py`).** Lo stato non vive in un file nuovo: si **deriva** dallo
storico già versionato in `source_status`, quindi è ricostruibile a mano dal Parquet pubblicato.
Dopo `BACKOFF_FAILS = 5` fallimenti consecutivi della stessa fase la fonte non viene
interrogata; ogni `BACKOFF_PROBE_RUNS = 4` pause si fa comunque una **sonda**, così una fonte
che riapre rientra da sola. Costo di una fonte rotta: da 14 richieste a run a **una ogni cinque
run** (≈1 al giorno). Lo scoreboard ESPN, che risponde, resta attivo: la chiave è la coppia
(fonte, fase), non il client.

**Pagina *Stato fonti*.** Pill **SOSPESO** dedicata (token `--s-bg`/`--s-fg`, contrasto AA in
entrambi i temi, aggiunti anche ai test di contrasto) con il motivo: «sospeso dopo 76 run
falliti consecutivi (espn standings); nuovo tentativo fra 4 run». Invariante `verify_site [28]`
estesa: una riga sospesa deve dichiarare N run e il ritentativo **e non può avere richieste** —
se una fonte sospesa interrogasse comunque la rete, il backoff non esisterebbe.

**Da confermare al primo daily post-merge** (regola B6): 14 richieste in meno, 14 righe
«SOSPESO» invece di «AVVISO», e il ritorno a «OK» se ESPN riapre.

---

## 4. [corretto] Un fallback che non viene mai esercitato non è un fallback funzionante

**Osservato.** Il meteo Open-Meteo è un **fallback**: entra solo quando FotMob non ha ancora
pubblicato il meteo (48 ore prima). Nei run registrati ha fatto **0 richieste** con motivo
dichiarato («nessuna previsione utile su N gare future: meteo FotMob N · coordinate 0 ·
previsione assente 0») — quindi il motivo c'era già, ma nulla dimostrava che il fallback
**funzionasse**: potrebbe essere rotto da settimane e nessuno lo saprebbe fino al primo giorno
di pioggia.

**Correzione.** `scripts/probe_fonti.py`: una **richiesta vera a settimana** (campo di San Siro,
previsione a 24 ore), esito registrato in `data/processed/source_probe.parquet` (tabella nuova,
chiave `(run_at, probe)`) e pubblicato in *Stato fonti* con la data. Se la sonda fallisce il
workflow `lab` diventa rosso; se la sonda non gira da più di 14 giorni la pagina **lo dichiara**
(«sonda ferma da N giorni: il fallback non è verificato») invece di far sembrare tutto a posto.

---

## 5. Verifiche misurate e prove di morso

| Verifica | Prima | Dopo |
|---|---|---|
| `verify_site` sui dati correnti | — | **0 problemi · 34.144 controlli** |
| `verify_site` sul sito **pre-fix** (prova di morso) | — | **301 problemi**: 87 doppia chance, 214 totali |
| doppia chance incoerenti (audit indipendente) | 48/165 | **0/165** |
| somme stampate incoerenti (audit indipendente) | 88/330 | **0/330** |
| totale dei gol attesi diverso fra pagine della stessa partita | 0/145 | 0/145 (ora è un'invariante `[31]`) |
| suite di test | 290 passed | **316 passed** |
| ruff (0.16.7) | 175 | **175** (nessun rilievo nuovo; i file nuovi sono puliti) |

- Invarianti nuove: `[30]` doppia chance = somma dell'1X2 stampato (+ somma 200), `[31]` ogni
  «a + b (c totali)» chiude e lo stesso totale è identico su tutte le pagine della partita,
  `[16]` ora confronta la somma delle λ **stampate** (non quella grezza), `[28]` estesa alla
  sospensione.
- Test aggiunti: `tests/test_fmt.py` (5, incluso un caso reale della scheda 5749662),
  `tests/test_backoff.py` (10, macchina a stati + integrazione con `collect_league`: la fonte
  sospesa non fa **nessuna** chiamata), `tests/test_probe_fonti.py` (6),
  `tests/test_site.py::test_doppia_chance_e_totale_chiudono_con_i_numeri_stampati` (che include
  la prova di morso sul testo pubblicato), `test_stato_fonti_mostra_sospensione_e_sonda_fallback`,
  `test_stato_fonti_senza_sonda_dichiara_che_non_e_verificata`,
  `tests/test_verify_scripts.py::test_verify_site_sospensione_deve_dire_motivo_e_non_chiamare`,
  `tests/test_models.py::test_assert_dc_coerente_morde_una_derivazione_rotta`.

---

## 6. Coda aggiornata (docs/19 §4)

**Chiusi in questo giro:** P1.8 (coerenza 1X2/doppia chance — nella forma più utile: invariante
di pubblicazione + assert di derivazione, perché il difetto era di **formattazione**, non di
calcolo), P1.9 (backoff ESPN + stato SOSPESO), P1.10 (motivo delle 0 chiamate già pubblicato dal
giro precedente + sonda settimanale del fallback).

**Restano:** P1.11 (griglia pre-registrata nel laboratorio), P1.12 (griglia di calibrazione
allineata ai bounds), P1.14 (shrinkage per-90 dei giocatori, ~6× troppo debole sui tiri),
P1.15 (`prossime.html`: debounce del filtro + `content-visibility`), poi i P2 (CSS: 62 selettori
duplicati e 35 colori hard-coded; font; narrativa; indice dei documenti; Lighthouse CI).

**Prossimo passo consigliato:** P1.14 — è l'ultimo difetto numerico noto che il lettore **vede**
(per-90 estremi su campioni piccoli nelle classifiche dei giocatori) e chiude l'area
«quantitativa» dell'audit. In alternativa P1.15, che è solo resa.

**Nota di metodo per le sessioni future.** I due difetti del §1 e §2 non erano visibili a occhio
in nessuna pagina presa da sola: sono emersi **confrontando i numeri pubblicati fra loro** con
uno script di audit. Il verificatore ora li copre, ma il pattern da riusare è quello:
*un'ipotesi di incoerenza per volta, misurata su tutte le pagine, e solo dopo una correzione con
invariante e prova di morso.*
