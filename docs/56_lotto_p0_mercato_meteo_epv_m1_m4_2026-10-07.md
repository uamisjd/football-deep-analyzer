# 56 — Lotto «schede delle prossime partite»: i due P0, l'EPV e M1–M4 (2026-10-07)

Questo documento chiude il lotto deciso dopo `docs/55`: **P0 Mercato**, **P0 Meteo**, la revisione
dell'**EPV** e le quattro migliorie **M1–M4**, in un unico giro. Per ogni intervento: cosa è stato
toccato, **cosa dicono le misure prima/dopo** e cosa resta aperto. Le misure sono rifatte sul
Parquet già raccolto e sulla build generata in locale: **nessuna richiesta alle fonti esterne**
(niente `collect`, nessuna sonda, nessun daily manuale), nessuna quota bookmaker.

Risposte dell'utente che hanno aperto il lotto (`docs/55` §8): si parte dai due P0 in un unico
lotto; sull'EPV vale la **A** (riga dentro «Fattori», non un secondo verdetto); M1–M4 entrano
**nello stesso lotto**.

---

## 0. In breve

| # | Difetto o miglioria (`docs/55`) | Prima (build 7/10) | Dopo (build di oggi) | Prova |
|---|---|---|---|---|
| P0 | **Mercato ×1,8–2,9**: la fonte ripubblica lo stesso movimento | 3.132 arrivi + 5.001 partenze elencabili sulle 132 squadre; **874 righe ripetute** su **66/66** schede; 128/132 sotto-card con una riga doppia | **1.079 + 1.712** movimenti (una riga per giocatore); **0 righe ripetute** su 958 righe visibili; 0/255 elenchi | §1, invariante **[39]** (519 controlli, 66 pagine), 21 test |
| P0 | **Meteo**: soglie del testo ≠ soglie del codice, «estremo» per una pioggia al 31% | testo «precip <30%, 10-28 °C, vento <15 km/h» contro codice `≥30 / ≥30·≤5 / ≥15`; «estremo» su 14/66 | due livelli dichiarati e **un'unica fonte** (`WEATHER_*`): segnalazione 30% · 30 °C · 5 °C · 15 km/h, impatto 50% · 30 °C · 20 km/h; nessun aggettivo | §2, invariante **[40]** (1.764 controlli, 441 pagine) |
| P1 | **EPV pre-match**: secondo verdetto che contraddice il modello in 20/66 | card «EPV pre-match» con etichetta e indice con +0,15 fissi di sede; fonte citata non verificabile | riga **«Forma e classifica (contesto)»**: tre numeri + indice dichiarato (50/30/20), **nessun verdetto**, niente fonte non verificabile | §3, `scripts/audit_epv.py` (5.164 gare) |
| M1 | Riga «Modello e calibrazione» con ξ a 4 decimali e «RPS 0,20 tipico» | 6/6 schede con numeri per addetti e una cifra non misurata | «Modello statistico»: **RPS 0,199 su 5.895 gare**, ξ 0,0018 detto in parole («una gara di un mese fa pesa 95% di una di ieri»), λ×1,039 | §4.1, `backtest_accuracy()` |
| M2 | xPTS in **4 sezioni** su 34/66 schede | numeri ripetuti in narrativa, card Clima, fattori e card squadra | numeri **solo** nella card della squadra; le altre sezioni richiamano «i numeri in *Le due squadre*» | §4.2 |
| M3 | Nota «+N altri fattori sotto soglia non mostrati» | diceva che esistono dati non visibili, senza dirne i nomi | la nota **elenca** i fattori fuori dalle sei righe (27/66 schede, 31 etichette citate) | §4.3 |
| M4 | «Fatti rilevanti» (66/66) fuori dall'indice | 0 voci su 66 schede | voce nell'indice, invariante **[33]** verde: **4.088** voci d'indice verificate | §4.4 |

Gate finali (tutti rifatti da zero sul ramo, ambiente ricreato con `pip install -e '.[dev]'`):

| Gate | Prima (`6cb14a7`) | Dopo |
|---|---|---|
| `pytest -q` | 517 passed | **524 passed** |
| `ruff check .` | pulito | pulito |
| `fda build` | 441 / 2.364 / 7.496 | **441 / 2.364 / 7.496** |
| `verify_site` | 0 problemi · 159.573 controlli | **0 problemi · 161.731 controlli** |
| `parita_schede` | 66 schede · identica (25 id) · indice 14 voci · min 91% | **66 · identica (24 id) · indice 14 voci · min 90%** |
| `resa_375` | 26.490 misure · 0 problemi | **26.424 misure · 0 problemi** |
| `prematch_sections` / `audit_match_sections` | senza differenze | senza differenze (7,8 righe per sezione in media, divario fra leghe 2,7) |

---

## 1. P0 — Mercato: due correzioni, una sulla scrittura e una sulla lettura

**Causa (misurata, non ipotizzata).** La fonte ripubblica lo stesso movimento e le due righe
differiscono in uno dei campi della chiave dell'upsert
(`team_id, player_name, direction, counterpart, date`):

1. **l'ora del timestamp**: `2026-08-11T06:47:30Z` e `2026-08-11T08:47:30` (ora locale al posto
   dell'UTC, 1-2 ore di scarto, stesso giorno);
2. **i diacritici del nome**: `Aleksić`/`Aleksic`, `Mömmö`/`Mommo`;
3. **la controparte riscritta**: `Al Diriyah`/`Al-Diraiyah`, `Dolomiti`/`Dolomiti Bellunesi`,
   `U.Leiria`/`União de Leiria` (57 gruppi, di cui **3** con due club davvero diversi: vedi §6);
4. un quarto difetto, indipendente: **4.252 righe su 11.624 (36,6%)** hanno la data senza il
   suffisso `Z` e il parser precedente le azzerava in silenzio (`NaT`) → **134 movimenti** non
   comparivano affatto in pagina.

**Cosa è stato fatto.**

* **Scrittura** (`store.py`): la chiave dell'upsert per `transfers` si confronta in **forma
  normalizzata** — nome e controparte senza accenti né punteggiatura (`soft_key`), data **al
  giorno** (`KEY_NORMALIZERS`). Il difetto non può rientrare con le prossime raccolte, senza
  cambiare le colonne salvate.
* **Lettura** (`analysis.py`, è questa che corregge il Parquet già committato):
  * `parse_moments()` legge la colonna `date` con `format="mixed"` (pandas 3): i due formati
    convivono e nessuna riga va più persa;
  * `dedup_transfers()` tiene **una riga per movimento** — nome e controparte normalizzati, due
    righe a meno di `TRANSFER_DEDUP_HOURS = 3` ore sono lo stesso annuncio (si preferisce quella
    con l'importo pubblicato);
  * `transfer_window()` fonde poi le **ri-pubblicazioni** dello stesso giocatore nella stessa
    direzione: stesso club (anche scritto in modi diversi) **o** data entro
    `TRANSFER_REPUBLISH_DAYS = 30` giorni; oltre quella soglia restano due movimenti distinti
    (misurato: le ri-pubblicazioni stanno entro 25 giorni: 0, 7, 11, 12, 13, 14, 15, 22, 24, 25).

**Misure (Parquet, 132 squadre delle 66 schede in finestra).**

| Regola | Arrivi | Partenze |
|---|---|---|
| Vecchia: una riga per riga della fonte (chiave esatta dell'upsert) | **3.132** | **5.001** |
| Nuova: una riga per giocatore e direzione | **1.079** | **1.712** |
| Riduzione | ×2,90 | ×2,92 |

Sulla pagina pubblicata, con lo stesso metodo di `docs/55` §4.1: righe ripetute **874 → 0**;
schede con almeno una riga doppia **66/66 → 0/66**; elenchi (sotto-card per direzione) con una
riga doppia **128/132 → 0/255**; righe visibili **958**, conteggi in testa alle sotto-card
**1.063 arrivi · 1.676 partenze** (le sotto-card sono 255: alcune squadre non hanno elenchi o
hanno la finestra scaduta). In `docs/55` §4.1 i due conteggi (676/932 pubblicati contro 377/517
reali) erano una **prima stima** con la chiave comprensiva dell'importo: i numeri definitivi sono
quelli di questa tabella, rifatti sul Parquet con entrambe le regole nella stessa passata.

**Test e invariante.** `tests/test_mercato.py` passa da 14 a **21 test** (dedup entro 3 ore,
diacritici, controparte riscritta, importo pubblicato più tardi, ri-pubblicazione a 7 e 25 giorni,
secondo movimento vero oltre 30 giorni con club diverso, date nei due formati). L'invariante
**`verify_site [39]`** rifà il conto **dal Parquet** (non dalla funzione che costruisce la card):
nessun nome ripetuto per colonna e direzione, e conteggi pubblicati = giocatori distinti nella
finestra dichiarata in pagina — con l'eccezione esplicita dei due movimenti veri oltre 30 giorni.
Misura di oggi: **66 pagine, 519 controlli, 0 problemi**.

---

## 2. P0 — Meteo: due livelli, una sola fonte per le soglie

**Causa.** Le soglie erano scritte in due posti che dicevano cose diverse: il testo della card
«nella norma (precip <30%, 10-28 °C, vento <15 km/h)» e il codice che segnalava `≥30`, `≥30/≤5`,
`≥15` chiamando **«estremo — può spostare ritmi»** una pioggia al 31% (14 schede su 66).

**Cosa è stato fatto.** Le soglie sono ora **costanti di modulo** in `analysis.py`
(`WEATHER_PRECIP_SEGNALA = 30`, `WEATHER_TEMP_ALTA = 30`, `WEATHER_TEMP_BASSA = 5`,
`WEATHER_VENTO_SEGNALA = 15`, e per il secondo livello `WEATHER_PRECIP_IMPATTO = 50`,
`WEATHER_VENTO_IMPATTO = 20`), e `weather_flags()` è l'unico punto che decide il livello e prepara
i testi pubblicati (`livello`, `segnalazioni`, `soglie_testo`, `impatto_testo`). La pagina usa solo
quei campi: la riga dice i valori, la soglia superata e il livello («sopra la soglia di
segnalazione» / «oltre la soglia di impatto»), mai un aggettivo non misurato.

**Misura sui 442 valori di `match_info.parquet`.** Temperatura ≥30 °C: **32** (7,2%); pioggia ≥30%:
**15**; ≥40%: 12; ≥50% (impatto): **5**; pioggia presente: 67 (15%). Due clausole sono
**dichiarate ma inerti** su questo dataset: vento ≥15 km/h (**0** casi, massimo osservato sotto
soglia) e temperatura ≤5 °C (**0** casi). Restano nel testo perché sono le soglie con cui la riga
si accende, ma oggi non scattano mai: se resteranno inerti anche a fine stagione si potranno
togliere con una misura alla mano, non prima.

**Invariante.** **`verify_site [40]`** verifica su ogni pagina con riga meteo che i numeri citati
fra parentesi siano **esattamente** le costanti del codice, che il livello dichiarato corrisponda ai
valori nel Parquet, che il testo delle soglie ci sia quando serve e che la parola «estremo» non
compaia più. Misura di oggi: **441 pagine, 1.764 controlli, 0 problemi**. Prova negativa fatta a
mano: cambiando in una copia della pagina «30 °C» in «99 °C» e nascondendo «oltre la soglia di
impatto», l'invariante fallisce (2 segnalazioni) — non è un controllo vuoto.

---

## 3. P1 — EPV: da secondo verdetto a riga di contesto

**Revisione (come chiesto: non rimozione cieca).** Il vecchio «EPV pre-match» era un secondo
pronostico accanto a quello pubblicato. Rifatto l'audit con la **stessa formula del codice** e lo
stato di stagione ricostruito gara per gara (`scripts/audit_epv.py`, rieseguibile offline):

| Misura sul backtest fuori campione | Valore |
|---|---|
| Gare valutate | 5.164 |
| Favorito azzeccato — modello pubblicato | **0,521** |
| Favorito azzeccato — indice (senza la costante di sede) | 0,493 |
| Favorito azzeccato — vecchio EPV (sede = +0,15 fissi) | 0,491 |
| Verdetti «casa» — indice / vecchio EPV | 0,438 / **0,538** |
| Disaccordi indice↔modello (esclusi i pareggi) | 807 (15,6%) |
| Quando sono in disaccordo azzecca — modello / indice | **0,401** / 0,321 |
| Correlazione (Spearman) con la differenza reti reale — indice / modello | 0,394 / **0,439** |
| L'indice aggiunto al modello migliora? | log-loss −0,0016, RPS **+0,0152 (peggio)** |

**Decisione (A).** L'indice **non è un pronostico** e non entra in pagina come tale: la card è
sparita, il suo contenuto sopravvive come **riga 0 dei «Fattori che spostano la partita»** —
«Forma e classifica (contesto)» — con i tre numeri veri (punti e punti/gara, differenza reti delle
ultime tre, differenza di posizione), l'indice dichiarato (50% punti/gara · 30% differenza reti
ultime 3 · 20% posizione, **senza** il termine di sede costante), la nota «contesto, non
pronostico» e la misura che la sostiene («questo indice da solo azzecca il favorito nel 49% delle
gare, il modello pubblicato nel 52%»). Sono spariti: l'etichetta-verdetto, la riga «EPV attesi
2,90 tot (media lega 1,45)» che confrontava un totale con una media per squadra con costanti
scritte a mano, e la citazione di una fonte **non verificabile dal sandbox** (`PMC12640942`).
Sulla build di oggi la stringa «EPV» compare in **0 pagine su 441**; la riga di contesto c'è su
**66/66** schede pre-partita.

---

## 4. M1–M4

### 4.1 M1 — «Modello statistico», con un errore misurato
`backtest_accuracy()` (nuova, in `analysis.py`) ricostruisce l'RPS del modello **dalla tabella
`backtest`** con la stessa formula di `models/calibration.py`: **5.895 gare, RPS 0,1991** —
ITA1 0,1974 (980) · ENG1 0,2024 (974) · ESP1 0,2017 (969) · POR1 0,1829 (750) · NED1 0,1941 (756)
· GER1 0,2039 (728) · FRA1 0,2103 (738). La riga mostra l'RPS **della lega della partita** con il
numero di gare, ξ (0,0018) e λ× dalla calibrazione, e dice l'errore in parole; è sparita la cifra
scritta a mano «RPS 0,20 tipico». Esempio pubblicato (Atalanta–Venezia): «RPS 0,197 (980 gare) ·
ξ 0,0018 · λ × 1,039 · errore fuori campo 0,199». Presenza della riga: **66/66** schede.

### 4.2 M2 — xPTS in un posto solo
Misura di partenza (`docs/55` §5, M2): i numeri dei punti contro xPTS comparivano in **4 card**
su **34/66** schede (sul resto 3). Misura di oggi sulle stesse 66 schede: la sigla «xPTS» compare
ancora in quattro sezioni, ma **i numeri stanno solo nella card della squadra** (etichetta «xPTS vs
punti reali») — la narrativa (34 schede) e la riga di umore della panchina dicono il verso **senza
cifre** e rimandano («i numeri in *Le due squadre*»), e la card dei fattori lo dichiara nella sua
introduzione. Il blocco #4 dei fattori «xPTS sopra/sotto atteso» è stato rimosso: era il terzo
posto in cui lo stesso scarto veniva quantificato. Test riscritti
(`tests/test_oggi_depth.py`, `pytest -k xpts` → 5 passed).

### 4.3 M3 — i fattori fuori dalle sei righe hanno un nome
`fattori_chiave()` restituisce anche `altri`: le etichette dei fattori che superano comunque la
soglia ma non entrano nelle sei righe ordinate per impatto. La nota pubblicata è «Fuori dai sei per
impatto (soglie comunque superate): …». Misura di oggi: **27/66** schede con la nota, **31**
etichette citate in totale; prima la nota diceva «+N altri fattori sotto soglia non mostrati in
tabella ma disponibili nei dati» (e «sotto soglia» era pure sbagliato).

### 4.4 M4 — «Fatti rilevanti» entra nell'indice
La sezione esisteva su 66/66 schede e non era raggiungibile dall'indice. La voce è stata aggiunta
**nel blocco `<nav>`** (fra «Vita del club» e «Arbitro e meteo») e l'id `fatti` è entrato in
`NAV_SEZIONI` di `verify_site`: da oggi un'ancora presente ma non linkata **blocca** il gate.
Misura: **4.088** voci d'indice verificate su 4.205 pagine, 0 problemi — prima il gate segnalava
«sezione presente ma fuori dall'indice» su tutte le 66 schede pre-partita.

---

## 5. Come si riproducono le misure

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/fda build                                                # 441 / 2.364 / 7.496
.venv/bin/python scripts/verify_site.py --site site --data data/processed
.venv/bin/python -m scripts.parita_schede site --data data/processed
.venv/bin/python -m scripts.prematch_sections site
.venv/bin/python -m scripts.audit_match_sections site
.venv/bin/python -m scripts.resa_375
.venv/bin/python -m scripts.audit_mercato                          # duplicati nel Parquet
.venv/bin/python -m scripts.audit_epv                              # EPV/indice vs modello
.venv/bin/python -m pytest -q && .venv/bin/ruff check .
```

---

## 5-bis. Il merge e la prova in produzione (7/10, 19:27–19:39 UTC)

**PR #89 mergiata su ordine esplicito dell'utente** (`docs/13` §9.20): merge commit **`6b3518d`**,
`merged_at` 19:27:49Z. Il push del merge tocca `src/`, `tests/` e `scripts/` — non coperti da
`paths-ignore` — quindi **ha attivato `daily` e `tests`**, entrambi **verdi**: `tests` run
`37674673264`, `daily` run `37674673310` (run + deploy Pages, 19:27:52 → 19:39:22Z), dati committati
in **`c6b214c`**, 0 issue aperte.

**La prova che conta, sulla tabella committata dal run:** `data/processed/transfers.parquet` passa
da **11.624 a 4.701 righe** (−60%), con **4.644 movimenti distinti** (squadra+direzione+giocatore+
giorno) **identici prima e dopo**. Cioè: la correzione dell'upsert non si limita a nascondere i
duplicati in pagina, **impedisce che si accumulino** nelle prossime raccolte — e la tabella ora
contiene una riga per movimento più i 57 gruppi in cui la fonte scrive la controparte in due modi
diversi (§6). Le correzioni sono online nelle schede pubblicate dal `daily` delle 19:38.

## 6. Cosa resta aperto (dichiarato, non taciuto)

* **Tre fusioni ambigue nel mercato.** Su 4.644 gruppi (stessa squadra, direzione, giocatore,
  giorno) **57** hanno la controparte scritta in due modi diversi e **3** nominano due club
  davvero diversi (Atalanta–Ahanor `Chelsea`/`Crystal Palace` il 01/09/2026, Real Sociedad–Kita
  `Kyoto Sanga FC`/`Real Sociedad B`, Arouca–Jansonas `CF Os Belenenses`/`Cova da Piedade SAD`).
  La regola pubblica la riga più recente: quando la fonte dice due cose incompatibili sullo stesso
  giorno, il sito non ne inventa una terza. Restano nei dati, non nascosti.
* **Due soglie del meteo inerti** (vento ≥15 km/h, temperatura ≤5 °C: 0 casi su 442). Dichiarate
  in §2, si tolgono solo con una misura di fine stagione.
* **M5 è morta con l'EPV** (era la riga dei gol attesi con il confronto esplicito). **M6**
  (sotto-serie dei precedenti 41/66) resta in coda P2: non è in questo lotto.
* **EPV come candidato del laboratorio (opzione B)** non è stato fatto: l'audit dice che aggiunto
  al modello non porta informazione (log-loss −0,0016, RPS peggiore di 0,015), quindi non c'è
  motivo di stimarne i pesi ora.
* **Fonti esterne non interrogate** (sandbox): le misure riguardano il Parquet già raccolto e la
  build locale. La resa visiva è verificata dal gate statico a 375 px, non a occhio in un browser.
