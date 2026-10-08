# 59 — «Fattori che spostano la partita»: terzo giro (2026-10-08)

Direttiva dell'utente: **«fai un'altra revisione a questa sezione, sicuro che non vuoi fare
altro? puoi fare anche altro usando altre fonti, l'importante che non sia una cosa banale e sia
invece di qualità, quantità e di valore, leggi bene tutta la sezione e correggi se ci sono errori
o cose non chiare»**.

Il primo giro (`docs/57`) ne aveva corretto la struttura, il secondo (`docs/58`) aveva aggiunto
due fattori misurati e il campione nelle celle. Questo giro fa due cose: **corregge un errore di
misura** trovato rileggendo la card come la vede il lettore, e **aggiunge valore** rendendo
interpretabile il fattore più forte (il rendimento per sede), che prima dava numeri assoluti senza
una base di confronto.

Metodo invariato (`docs/00` B.8): ogni numero pubblicato viene dagli archivi già raccolti, rimisurato
in questo giro con `scripts/audit_fattori.py` (`/tmp/fattori_audit5.json`). Nessuna richiesta alle
fonti esterne.

---

## 0. In breve

| # | Cosa è cambiato | Prima | Dopo | Prova |
|---|---|---|---|---|
| 1 | **Errore nel ⓘ del pressing** — il testo spacciava il solo bucket «casa pressa molto» per «una delle due pressa molto più dell'altra» | «quando una delle due pressa molto più dell'altra la gara produce 3,43 xG […] chi pressa di più fa 1,70 punti contro 1,07» | i tre bucket separati: casa pressa (≤0,75×, 40 gare) 3,43 xG e 1,70 punti; ospite pressa (≥1,33×, 28 gare) 3,03 xG e 1,07; pressing simile (36 gare) 3,10 xG | §1, audit |
| 2 | **Riferimento di lega nel rendimento per sede** — la cella dà anche la media per sede della stessa lega nella finestra | «2,50 pt/gara in casa (18 gare)»: un numero assoluto che il lettore non sa collocare | «2,50 pt/gara in casa (18 gare · **lega 1,44**)»: si legge subito che è sopra la base | §2, 24/24 righe |
| 3 | **Intestazione autonoma** — i tre fattori non pubblicati spiegavano il motivo rimandando a `docs/58`, un file che il lettore del sito non può aprire | «numeri e motivo in `docs/58`» | il motivo in pagina: punti dell'ospite piatti con i km, correlazione età-punti 0,02, 16 gare con impegno ravvicinato | §3 |

Gate finali (rifatti da zero sulla build nuova):

| Gate | Esito |
|---|---|
| `pytest -q` | **538 passed** |
| `ruff check .` | pulito |
| `fda build` | **441 / 2.364 / 7.494** (EXIT 0) |
| `verify_site` | **0 problemi · 167.585 controlli** ([41] su 66 schede) |
| `parita_schede` | nessuna differenza · min 21.153 · mediana 23.068 (min = 92%) |
| `resa_375` | **26.419 misure · 0 problemi** |
| `prematch_sections` | Fattori **10,7%** del visibile (era 9,5%) · 66/66 schede |

---

## 1. L'errore corretto: il ⓘ del pressing raccontava un solo bucket

Rileggendo la card come la vede il lettore (celle + tooltip) è emerso che il ⓘ del pressing diceva:

> «quando **una delle due** pressa molto più dell'altra la gara produce **3,43 xG** contro i 3,10
> delle gare con pressing simile, e chi pressa di più fa **1,70 punti** a gara contro 1,07».

I numeri vengono dall'audit (`pressing`, 162 gare con PPDA per entrambe le squadre), ma sono letti
male: 3,43 xG e 1,70 punti sono **solo** il bucket «la casa pressa molto» (rapporto ≤0,75×, 40
gare). Quando è l'**ospite** a pressare molto (≥1,33×, 28 gare) gli xG sono **3,03** — quasi pari
alle gare con pressing simile (3,10) — e i punti della casa scendono a 1,07. Quindi «una delle due
pressa molto più dell'altra produce 3,43 xG» era falso per metà dei casi: l'effetto sugli xG c'è
soprattutto quando pressa la casa, non quando pressa l'ospite.

Il ⓘ ora separa i tre bucket con il loro campione, e la conclusione resta quella onesta: chi pressa
di più crea più xG ma rischia il contropiede. Nessuna soglia è cambiata (`FACTOR_PRESS_RATIO` 0,75),
quindi `fattori_soglie_testo()` e l'invariante [41] non sono toccati.

---

## 2. Il valore aggiunto: il riferimento di lega nel rendimento per sede

**Il problema.** Il rendimento per sede è il fattore che separa di più (10,6% → 68,2% di vittorie
al crescere del Δ, `docs/58` §3), ma la cella dava un numero **assoluto**: «1,22 pt/gara in casa».
Il lettore non può sapere se 1,22 è tanto o poco, perché non conosce la base della lega. Un numero
senza un riferimento è metà dell'informazione.

**La correzione.** `venue_form()` calcola ora anche il PPG per sede **della stessa lega** nella
stessa finestra di 365 giorni (tutte le gare di quella lega, non solo della squadra), e la cella lo
porta: «2,50 pt/gara in casa (18 gare · **lega 1,44**)». Adesso il confronto è immediato: 2,50 contro
una base di 1,44 dice che quella casa rende molto sopra la norma; 1,28 in trasferta contro una base
di 1,32 dice che quell'ospite è nella norma. Il Δ della riga (+1,22) resta il numero decisivo, ma
ora anche i due valori assoluti si leggono.

**Perché nella cella e non nel ⓘ.** Il riferimento serve a leggere il numero a colpo d'occhio: nel
ⓘ sarebbe stato nascosto dietro un tap su mobile. Costa ~12 caratteri a cella; `resa_375` resta a
0 problemi e la parità a 92%, quindi il layout regge.

**Implementazione.** `_hist_venue()` tiene ora anche `league_key`; `venue_form()` filtra le gare
della lega della squadra nella finestra e ne media `ph`/`pa`. Per una gara di campionato la lega è
la stessa da entrambe le parti, quindi il riferimento è preso dal lato che ce l'ha. Se `history`
non ha `league_key` (o la squadra non ha gare nella finestra) il riferimento non esce: la cella
resta quella di prima, senza «lega». Copertura misurata sulle pagine generate: **24 righe su 24**
portano il riferimento (tutte quelle in cui la riga di sede è sopra soglia).

Il ⓘ spiega come leggerlo: «"lega" è la media per sede della stessa lega nella finestra: il valore
della squadra va letto contro quella base (1,44 in casa, 1,32 in trasferta)».

---

## 3. Chiarezza: l'intestazione non rimanda più a un file interno

L'intestazione della card chiudeva con «Distanza della trasferta, età dei titolari e turnover per
impegno ravvicinato sono stati misurati e **non** pubblicati […] numeri e motivo in `docs/58`». Un
lettore del sito non può aprire `docs/58`: il rinvio era inutile e la dichiarazione restava senza
prova. Ora il motivo è in pagina, in una riga: i punti dell'ospite non cambiano con i chilometri,
la correlazione fra età e punti è 0,02, e le gare con un impegno entro 3 giorni sono 16 — poche e
sbilanciate verso le squadre più forti. Sono i numeri dell'audit (`distanza`, `eta`, `impegno`), gli
stessi di `docs/58` §5, ora leggibili senza uscire dalla scheda.

---

## 4. Misurati e non aggiunti in questo giro

Coerente con il metodo, due candidati sono stati valutati e **non** aggiunti, perché la misura non
li sostiene con i dati disponibili:

| candidato | perché non è entrato |
|---|---|
| **Regressione gol−xG** (chi segna sopra gli xG tende a tornare indietro) | lo storico per squadra con gli xG (`understat_team_matches`) copre solo la stagione in corso: 5-7 gare a squadra. Un «rendimento rispetto agli xG» su 5 gare è rumore — lo stesso motivo per cui `docs/58` §2 ha messo il campione in cella. Non pubblicabile |
| **Mismatch su palla inattiva** (xG da set-piece concessi contro prodotti) | la quota di xG da palla inattiva è già in «Scontro tattico» (radar e tabella); in più varrebbe lo stesso limite di campione. Sarebbe una ripetizione, non un fattore nuovo |

Nessun fattore nuovo è quindi entrato in questo giro: la card resta a **sei fattori + contesto**. Il
valore è venuto dal rendere interpretabile il fattore più forte e dal correggere un ⓘ sbagliato, non
dall'aggiungere righe.

---

## 5. Peso della card

Il riferimento di lega aggiunge testo: la card passa da **9,5% a 10,7%** del testo visibile di una
scheda pre-partita (mediana della pagina 23.068 caratteri, minimo 92% della mediana). È l'effetto
voluto dalla direttiva («quantità e valore»), ma è il secondo aumento consecutivo: se la scheda
dovesse sembrare troppo lunga, la prima candidata a uscire resta la riga di contesto «Forma e
classifica» (`docs/58` §8.1), che ripete in sintesi numeri già in «Le due squadre».

---

## 6. Come riprodurre

```bash
.venv/bin/python scripts/audit_fattori.py --json /tmp/fattori_audit5.json   # le misure (pressing, sede, …)
.venv/bin/fda build                                                          # 441 / 2.364 / 7.494 (~5 min)
.venv/bin/python scripts/verify_site.py --site site --data data/processed    # 0 problemi · 167.585
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site                           # Fattori 10,7%
.venv/bin/python -m scripts.resa_375                                         # 26.419 · 0
.venv/bin/pytest -q && .venv/bin/ruff check .                                # 538 passed · pulito
```

Test aggiornato: `test_fattori_rendimento_per_sede_finestra_campione_soglia` ora verifica che la
cella porti il riferimento di lega e che il ⓘ lo spieghi.

**Cosa non è verificato da qui** (dichiarato, non taciuto): le fonti esterne non sono raggiungibili
dal sandbox e non sono state interrogate. La resa **visiva** non è stata vista in un browser:
`resa_375` misura geometria e caratteri a 375 px, non è un giudizio estetico.
