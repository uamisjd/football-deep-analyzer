# 63 — Revisione affidabilità del daily: perché falliva spesso e perché si aggiorna da solo (2026-10-09)

**Richiesta utente (2026-10-09):** «puoi fare una revisione? puoi controllare se riesci ad
aggiornarsi da solo? spesso il daily run fallisce, dà errore». Tutto qui sotto è misurato
in questa sessione (16:45–17:30 UTC, 2026-10-09) via API GitHub Actions, `git` e riesecuzione
locale dei gate; nessuna richiesta alle fonti esterne (regola B.6: dal sandbox non arrivano).

---

## 1. Verdetto in sintesi

1. **«Spesso fallisce» è confermato dai numeri, e il periodo è identificato:** negli ultimi
   30 giorni **26 run daily rossi su 43 (60%)**, tutti concentrati fra il **10-02 18:54 UTC
   e il 10-08 22:40 UTC**. Dal **10-09 01:19 UTC** i run sono **4 su 4 verdi** (01:19, 11:14,
   15:42 dal merge #95, 16:42).
2. **Ogni run rosso ha la causa radice identificata e già corretta** (due classi strutturali
   + un evento isolato): le correzioni sono in `main` (docs/51 il 10-07; PR #95 il 10-09
   15:42). In questa sessione le correzioni sono state **riverificate con misure**, non per
   assunzione (§5).
3. **«Si aggiorna da solo»: sì, allo stato attuale.** La pipeline completa (collect →
   modelli → build → 3 gate → commit dati → deploy Pages) gira senza intervento: gli ultimi
   4 run verdi hanno committato i dati a ogni run (ultimo: `4a79e2c`, 16:55 UTC) e pubblicato
   su GitHub Pages; l'alert ha aperto la issue #94 sul run rosso del 10-08 e l'ha chiusa da
   sola al primo run verde (01:30 UTC).
4. **Nessuna modifica di codice in questa sessione** (regola B.10): tutti i candidati sono
   stati misurati prima e scartati come non necessari o peggiorativi (§5, §7).

---

## 2. Mappa dei fallimenti (finestra 2026-09-09 → 2026-10-09, API `actions/runs`)

43 run `daily` (schedule + push su `main`): **17 verdi, 26 rossi**. I 26 rossi classificati
per step fallito (API `jobs`):

| Step fallito | N | Run (id) |
|---|---|---|
| `Verifica il sito (verify_site)` | 24 | `37050636618` … `37612264587` (10-02 18:54 → 10-07 11:10) |
| `Parità delle schede pre-partita` | 1 | `37854956810` (10-08 22:40, run #230) |
| `Installa il pacchetto` (pip) | 1 | `37401107496` (10-06 01:49) |

Nessun fallimento in `collect`, `build`, `resa_375`, commit dati o deploy Pages in 30 giorni.

---

## 3. Cause radice

### A — `verify_site` «concordanza» (24 run, 10-02 → 10-07): il principale

Il gate rilegge **tutto** il testo pubblicato e blocca il run (prima del commit dati e del
deploy) se trova numeri incoerenti o plurale italiano sbagliata «1 X» (regex `AGREEMENT`,
`scripts/verify_site.py:151`). È un fallimento **voluto** (docs/19 P0.8: «un numero che non
torna fallisce il run PRIMA della pubblicazione»); il difetto stava nel **testo generato**.

- Incidente misurato (issue #79, run #216, 10-07 11:26): `fattori_chiave()` stampava
  `1 assenti` quando una squadra aveva **esattamente 1** indisponibile titolare abituale
  (Como–Roma, match 5749692) — e nella stessa funzione `1 giorni` con riposo di un giorno.
- Nei log degli stessi run: traceback ricorrente del feed RSS **Sportmediaset** (HTTP 404
  permanente dal 17/09) che sporcava i log e le diagnostiche.
- **Correzione in `main` il 10-07** (docs/51): `it_plural` su assenti/giorni/titolari +
  rimozione del feed morto + test di regressione. Primo run verde: 10-07 17:05 UTC.

### B — `parita_schede`: card «Precedenti» sparita (1 run, 10-08 22:40)

Il template rendeva la card **solo** in presenza di dati h2h. Avanzando il calendario, 4
schede su 71 (5749704, 5781769, 5802957, 5868093) erano gare **senza** storico H2H → card e
ancora d'indice sparivano → struttura non uniforme → gate KO. Diagnostica automatica sulla
issue #94 (aperta da `ci_alert.py` alle 22:52, chiusa al run verde delle 01:19).

- **Correzione in `main` il 10-09 15:42** (PR #95, commit `f2af30f`, verbale in docs/62):
  la card rende **sempre**; senza storico mostra il fallback dichiarato
  «Nessun precedente in archivio per questa sfida…».
- Causa latente dichiarata in docs/62: **1.924 delle 1.989 fixture pre-match sono senza
  h2h**, quindi il caso «scheda senza precedenti» è la norma, non l'eccezione — prima della
  correzione ogni finestra di build poteva sorteggiarlo.

### C — `pip install` (1 run, 10-06 01:49)

Fallimento isolato all'installazione del pacchetto (log non scaricabili dal sandbox: lo
storage dei risultati Actions non è nell'allowlist di egress). Nessun ripetersi nei 42 run
successivi → evento transitorio di rete, nessuna azione (B.10: un intervento su un incidente
1/43 senza misura di ricorrenza aggiungerebbe complessità senza beneficio misurato).

---

## 4. «Riesce ad aggiornarsi da solo?» — le prove

**Live (GitHub Actions, osservato questa sessione):**

- 4 run verdi consecutivi dal 10-09 01:19 UTC: `37869217484` (01:19), `37922464380` (11:14),
  `37953678473` (15:42, push del merge #95), `37961077793` (16:42, schedulato — completato
  `success` durante questa revisione).
- A ogni run verde: commit dei dati in `main` (`9ec7c45` 01:30, `0d5e95a` 11:27, `fef48f0`
  15:51, `4a79e2c` **16:55 UTC — dopo l'inizio di questa revisione**, 7 Parquet aggiornati)
  e deploy su GitHub Pages.
- Loop di allerta funzionante: issue #94 aperta automaticamente sul run rosso, chiusa
  automaticamente al primo run verde (22:52 → 01:30, ~2h38m di sito fermo, non i 14h27m del
  19/09 che hanno motivato l'alert).

**Locale (sandbox, tutto tranne il collect live):**

| Gate | Esito (2026-10-09, build locale su dati `fef48f0`) |
|---|---|
| `pytest -q` | **540 passed** (73 s) |
| `ruff check .` | pulito |
| `fda build` | **446** partite / **2.364** fixture / **7.498** giocatori |
| `verify_site` | **0 problemi · 169.967 controlli** |
| `parita_schede` | **71** schede pre-partita · struttura identica (24 id) · **nessuna differenza** |
| `resa_375` | **26.628 misure · 0 problemi** a 375 px |

**Limite dichiarato (regola B.6):** dal sandbox le fonti sportive (FotMob/ESPN/Understat/
notizie) **non** sono raggiungibili, quindi il `fda daily` completo **non** si riesegue qui:
la verifica «dal vivo» della raccolta resta in carico a GitHub Actions, che da 01:19 UTC
segnala tutto verde. Questa revisione non dichiara «verificato live» ciò che è verificato
solo offline.

---

## 5. Riverifica strutturale delle due classi di fallimento (misure, non assunzioni)

### A — Plurale «1 X»: nessun percorso vivo nel testo pubblicato

Sweep statico di tutte le f-string `{n} <plurale>` (lista dei 26 sostantivi di `AGREEMENT`)
in `src/fda/`, esclusi i percorsi già protetti da `it_plural`:

- Le uniche candidate che arrivano al sito hanno **soglie ≥ 2**: righe di «Clima del club»
  (`MOOD_LOSS_STREAK=3`, `MOOD_NOWIN=4`, `MOOD_UNBEATEN=5`, `MOOD_DRY=3` → i conteggi
  pubblicati sono sempre ≥ 2).
- I fatti di forma (`form_facts`, `translate_insight`) sono già **induriti**: helper
  `_n_partite`/`_n_incontri`/`_n_confronti` e rami espliciti `n == 1` («ha perso
  l'ultima partita», «ha vinto la precedente partita contro X»).
- `Calibration.corpus` («N gare (sotto la soglia di…)», «N gare fuori campione · parametri
  stimati su M gare», `calibration.py:313/391`) **non è pubblicato**: solo log/CLI —
  verificato che le uniche occorrenze di «fuori campione» nel build locale sono testo
  **statico** dei template (descrivono il backtest, `match.html:556`, `accuracy.html`,
  `info.html`), non stringhe corpi generate dai dati.
- Soglie «come arrivano» da 5 gare (docs/60) e finestra `h2h_list(n=5)`: costanti, non
  dati.

Conclusione: della classe A non esistono istanze note vive. Il gate resta la protezione
per il futuro, per scelta di progetto (D2, docs/53 §7: **gate tutti bloccanti**).

### B — Card che possono sparire: la rete di sicurezza funziona, i margini sono misurati

- Le 71 schede pre-partita attuali hanno **tutte** lo stesso insieme di 24 id di card;
  qualsiasi scomparsa futura (anche su una scheda sola) viene fermata **prima** della
  pubblicazione: l'incidente del 10-08 è la prova che il gate fa il suo lavoro (il run era
  rosso, la issue si è aperta con la lista esatta delle 4 schede, la correzione è stata
  mergiata in giornata).
- **Margine della fallback Precedenti:** le 3 schede senza storico del build attuale
  rendono 369–376 caratteri visibili = **41% della mediana** di sezione (890); la soglia
  del gate è il **25%**. La sezione è **finita per costruzione** (ultimi 5 precedenti +
  testo riepilogativo a cap fissa; massimo osservato 1.011), quindi la mediana non può
  crescere oltre il punto in cui la fallback scenderebbe sotto il 25% (~1.476 caratteri).
  Margino strutturale, nessuna modifica necessaria.
- Le altre card condizionate (#scontro, #fattori, #giocatori, #panchina, #mercato,
  #notizie, #fatti, #previsione) restano dipendenti dai dati: la prescrizione di progetto
  (docs/00 F, parita «Che fare») è segnaposto dichiarato in pagina + `ECCEZIONI` se
  strutturale — già applicata a «Precedenti» (docs/62), «Arbitro» («da definire»),
  «Meteo» («pubblicata a ridosso della gara»), indisponibili («nessuno segnalato»).

---

## 6. Rischi residui dichiarati (nessun'azione intrapresa, con motivo)

1. **Un nuovo caso-limite di dati può ancora fermare un run** (es. un'altra frase «1 X» in
   un percorso mai scattato, o una card che diventa vuota per una lega non coperta). È il
   trade-off scelto dall'utente il 10-07 (D2: gate bloccanti): il costo è il sito fermo
   fino al prossimo run verde (~2–8 h), il beneficio è mai pubblicare un difetto. L'alert
   identifica la stringa esatta in pochi minuti. Mitigazione strutturale già in opera:
   la fallback dichiarata (docs/62) riduce la superficie delle card a guardia.
2. **I cron non sono puntuali**: i 5 run nominali (06:00/12:00/16:00/20:00/23:30 IT)
   partono con ritardo medio misurato di **3,2 h** (documentato in `daily.yml`). Non è un
   fallimento: i dati arrivano, più tardi.
3. **Fallimenti transitori di infrastruttura** (il pip 1/43, gli EOF sui log Actions dal
   sandbox): rari, self-limiting, senza impatto sulla correttezza dei dati pubblicati.

---

## 7. Decisione (regola B.10)

**Nessuna modifica di codice.** Candidati valutati con misura prima di scrivere qualsiasi
riga: (a) allungare la fallback Precedenti o intagliare la soglia di parità → non servono,
il margine misurato è strutturale (§5B); (b) pluri «1 X» → nessun percorso vivo (§5A);
(c) retry del passo `pip` → 1 incidente/43 run, nessun beneficio misurato (§3C);
(d) rendere non-bloccanti i gate → contro la decisione D2 dell'utente, scartato.

## 8. Rilevato durante la revisione (igiene documenti, non bloccante)

- **Collisione di numerazione 58/58** già esistente in `docs/`: `58_schede_terza_coppia_
  come_arrivano_giocatori_2026-10-07.md` e `58_fattori_secondo_giro_misure_2026-10-08.md`.
  È il residuo dichiarato dell'«incidente della scrittura parallela» (commit `ae5ebc9`,
  10-08): due sessioni hanno numerato lo stesso documento. Non rinominato in questa
  sessione (rinomina = rottura di ogni riferimento esistente, peggioramento, B.10): va
  sistemato in un giro dedicato con aggiornamento dei riferimenti.
- **Indice del briefing in ritardo:** mancavano le voci 57–62 (aggiunte in questa
  sessione); `README.md` mancava 57, 61, 62 (aggiunte).

## 9. Prossimo passo

- **Pipeline:** nessuna azione bloccante; monitorare i prossimi run daily (4/4 verdi da
  01:19 UTC; dati che scendono a ogni run).
- **Coda revisione schede** (docs/58 §8.5 / docs/61 §4, stesso metodo misura→correzione→
  prova): **Panchina e posta in gioco**, **Mercato**, **Vita del club**, **Previsione del
  modello ensemble**, **Verifica approfondita**; su «Come arrivano» resta l'anacronismo
  «forza avv.» (docs/60 §5).
- **Punti aperti ereditati:** tre tilt non cablati + valore titolari assente su 42/66
  (docs/57 §7); collisione 58/58 da sistemare in un giro dedicato.
