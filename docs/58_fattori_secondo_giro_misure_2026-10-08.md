# 58 — «Fattori che spostano la partita»: secondo giro, con le misure (2026-10-08)

Direttiva dell'utente: **«dentro la scheda di una partita abbiamo tante sezioni che il sito
riempie: puoi revisionare in modo accurato la sezione *Fattori che spostano la partita*? fai
qualche ricerca approfondita per migliorare questa sezione e aggiungere qualità, quantità e
valore»**.

Il documento è il verbale del secondo giro di revisione della card. Il primo (`docs/57` §1-§6,
7/10/2026) ne aveva corretto la struttura: una riga per fattore, soglie in una sola fonte, niente
barra percentuale non spiegata, niente modello in tabella. Questo giro fa la domanda successiva:
**i fattori giusti sono questi? e i numeri che li accompagnano sono misurati?**

Metodo, come sempre nel progetto (`docs/00` B.8, «prima si dimostra, poi si integra»): ogni
fattore — quelli già in card e otto candidati nuovi — è stato **misurato sugli archivi già
raccolti** con uno script nuovo, `scripts/audit_fattori.py`, prima di decidere se pubblicarlo.
Nessuna richiesta alle fonti esterne, nessuna quota bookmaker come previsione (le quote dello
specchio sono usate solo come *ancora* di confronto: «quanto sa già il mercato?»).

---

## 0. In breve

Build di riferimento: **441 schede**, **66 pre-partita** (375 finite), 2.364 partite, 7.494
giocatori. Misure dell'audit: 7.467 gare di campionato su 3 stagioni (`history`), 375 gare con
dettagli (`match_info`), 333 con l'arbitro, 162 con PPDA per entrambe le squadre.

| # | Cosa è cambiato | Prima | Dopo | Prova |
|---|---|---|---|---|
| 1 | **Fattore nuovo: rendimento per sede** — punti/gara **in casa** della squadra di casa contro punti/gara **in trasferta** dell'ospite (finestra 365 giorni, minimo 5 gare per sede, soglia 0,50 pt/gara) | 0 righe, dato pubblicato in nessuna card | **24 righe su 66** + 42 dichiarazioni fuori tabella | [41] estesa, §3 |
| 2 | **Fattore nuovo: disciplina e arbitro** — gialli e falli/gara delle due squadre più lo scarto dell'arbitro dalla media di lega (soglie 0,8 gialli/gara e ±10% su ≥20 gare in carriera) | l'arbitro solo in «Arbitro e meteo», senza confronto con le squadre | **28 righe su 66** + 38 dichiarazioni fuori tabella | [41] estesa, §4 |
| 3 | **Campione in cella** per i fattori di stagione (PPDA, sede, cartellini): «21,3 (5 gare)» invece di «21,3» | 66/66 righe PPDA senza numero di gare | 0 righe senza campione; [41] boccia la pagina se manca | [41], §2 |
| 4 | **Ordine delle righe fisso e dichiarato** (`FACTOR_PRIORITY`), non un peso ad hoc | il rapporto di mercato saliva a 10,1 e scavalcava tutto: lo stesso fattore cambiava posizione da una scheda all'altra | ordine dichiarato in pagina e nel codice | test `test_fattori_ordine_fisso_e_campione_dichiarato` |
| 5 | **I ⓘ citano misure nostre**, non solo letteratura: mercato 1,87 contro 1,43 punti/gara, pressing 3,43 contro 3,10 xG/gara, arbitri 3,80 contro 3,19 gialli/gara, Δ riposo **senza** segnale coerente | 4 ⓘ senza alcuna misura sull'archivio | 6 ⓘ con la misura e il campione | `scripts/audit_fattori.py`, §1 |
| 6 | **Tre candidati misurati e non pubblicati** (distanza della trasferta, età dei titolari, turnover per impegno ravvicinato): la card lo dice in pagina, con il rinvio alle misure | il lettore non poteva sapere che erano stati considerati | una riga dichiarata nell'intestazione della card | §5 |
| 7 | **`verify_site` non nasconde più i problemi**: il riepilogo per tipo cadeva con `IndexError` su un messaggio senza «: » — dopo i controlli, quindi i problemi non venivano stampati | gate che si rompe invece di riportare | chiave di ripiego nel riepilogo | §2.5 |

Peso della card (`prematch_sections`): **6,6% → 9,5%** del testo visibile di una scheda
pre-partita (mediana della pagina 21.680 → 22.355 caratteri, minimo 92% della mediana). È l'aumento voluto dalla direttiva
(«quantità e valore»): 229 righe contro 177, 3 righe per scheda invece di 2,7, e due fattori in
più che prima non c'erano da nessuna parte.

Gate finali (rifatti da zero dopo l'ultima modifica al sorgente):

| Gate | Prima di questo giro | Dopo |
|---|---|---|
| `pytest -q` | 534 passed | **538 passed** |
| `ruff check .` | pulito | pulito |
| `fda build` | 441 / 2.364 / 7.494 | **441 / 2.364 / 7.494** |
| `verify_site` | 0 problemi · 162.703 controlli | **0 problemi · 167.585 controlli** ([41] su 66 schede) |
| `parita_schede` | 66 · identica (24 id) · indice 14 voci · min 91% | **66 · identica (24 id) · indice 14 voci · min 92%** |
| `resa_375` | 26.424 misure · 0 problemi | **26.419 misure · 0 problemi** |
| `prematch_sections` | Fattori 6,6% · visibile 21.680 | **Fattori 9,5% · visibile 22.355** |

---

## 0.1 La stessa card, prima e dopo (`partite/5749696.html`, Lecce–Bologna)

**Prima** (build del 7/10/2026, `docs/57` §0.1): due righe quantitative e il contesto.

```
🏥 Indisponibili            1 assente · −0,26 xG+xA/90        2 assenti · 2 titolari · −0,40 …   −0,14 xG+xA/90   equilibrio fra le due squadre
📊 Forma e classifica       6 pt · 1,20/gara · GD3 −3         2 pt · 0,40/gara · GD3 −1          PPG +0,80 · …    indice +0,29 — contesto
Sotto soglia o non calcolabile: valore dei titolari non pubblicato · riposo 20 e 22 giorni (soglia ≤4) · pressing 1,15× (soglia ≤0,75× o ≥1,33×).
```

**Dopo** — quattro righe, due delle quali prima non esistevano in nessuna card del sito:

```
🏥 Indisponibili            1 assente · −0,26 xG+xA/90        2 assenti · 2 titolari · −0,40 …   −0,14 xG+xA/90   equilibrio fra le due squadre
🏟 Rendimento per sede      1,22 pt/gara in casa (18 gare)    1,83 pt/gara in trasferta (18)     −0,61 pt/gara    squilibrio di sede a favore di Bologna
🟨 Disciplina e arbitro     2,0 gialli · 12,6 falli (5 gare)  1,6 gialli · 14,6 falli (5 gare)   +0,4 gialli/gara arbitro più severo della media di lega (+16%)
📊 Forma e classifica       6 pt · 1,20/gara · GD3 −3         2 pt · 0,40/gara · GD3 −1          PPG +0,80 · …    indice +0,29 — contesto
Sotto soglia o non calcolabile: valore dei titolari non pubblicato · riposo 20 e 22 giorni (soglia ≤4) · pressing 1,15× (soglia ≤0,75× o ≥1,33×).
```

Le due righe nuove dicono cose che la scheda **non** diceva altrove: il Bologna rende di più in
trasferta (1,83) di quanto il Lecce renda in casa (1,22) — un'informazione che né «Le due
squadre» (totali di stagione) né «Confronto di stagione» (classifica) contengono — e che l'arbitro
designato è il 16% più severo della media delle designazioni della stessa lega.

---

## 1. L'audit: `scripts/audit_fattori.py`

Lo script misura **nove** blocchi sullo stesso schema (campione, effetto sull'esito, e dove
possibile il confronto con quello che le quote sanno già) e stampa solo riepiloghi:

| blocco | fonte | campione |
|---|---|---|
| riposo (livelli e Δ) | `history` (3 stagioni, campionato) | 14.578 osservazioni · 7.243 gare con Δ |
| valore dei titolari | `match_info` | 363 gare |
| distanza della trasferta | `match_info` (lat/lon degli stadi) | 375 gare |
| split di sede | `history` | 6.307 gare |
| età media dei titolari | `match_info` | 375 gare |
| arbitro (cartellini e rigori) | `match_info` + `team_stats` + `shots` | 375 gare · 333 con l'arbitro |
| impegno ravvicinato (turnover) | `fixtures` + `cup_fixtures` | 750 osservazioni |
| meteo | `match_info` + `team_stats` | 375 gare |
| pressing (PPDA) | `understat_team_matches` | 162 gare |

Due scelte di metodo che valgono come correzioni:

1. **La quota implicita va normalizzata.** Confrontare «vittorie casalinghe reali» con
   `1/quota_casa` è sbagliato: la somma dei tre `1/quota` supera 1 dell'overround del bookmaker
   (5-8%), quindi ogni confronto è sbilanciato verso il basso. La prima stesura dell'audit lo
   faceva; ora `_quota_impl()` divide per la somma dei tre. Effetto concreto sui numeri dello
   split di sede: 73,2% → **70,4%** e 12,5% → **12,0%**. I numeri pubblicati nei ⓘ sono quelli
   normalizzati.
2. **Il riposo dello specchio è solo campionato.** `history` non ha le coppe, quindi i giorni di
   riposo misurati su 3 stagioni sono una approssimazione per difetto del riposo vero (che è
   quello di `rest_days()`, campionato + coppe). Dichiarato nello script e qui: il confronto
   *relativo* fra le due squadre resta leggibile, il valore assoluto no.

Riproduzione:

```bash
.venv/bin/python scripts/audit_fattori.py            # riepilogo a schermo
.venv/bin/python scripts/audit_fattori.py --json /tmp/fattori.json
```

---

## 2. Qualità: cinque difetti corretti

### 2.1 Una media di stagione senza il campione

Il PPDA di inizio stagione è una media su 5-7 gare, e la cella diceva solo «21,3»: un numero che
sembra solido quanto una media su 30 gare. Lo stesso vale per i due fattori nuovi. Ora ogni
fattore di stagione porta il campione in cella — «21,3 (5 gare)», «1,22 pt/gara in casa
(18 gare)», «2,0 gialli · 12,6 falli (5 gare)» — e l'invariante [41] boccia la pagina se una di
quelle righe non lo dichiara **nelle celle** (il ⓘ non basta: parla di «gara» comunque, quindi il
controllo sarebbe vuoto).

### 2.2 L'ordine delle righe dipendeva da un peso ad hoc

Le righe erano ordinate per `-weight`, e i pesi erano eterogenei: il valore di mercato usava
`max(ratio, 1/ratio)` (fino a **10,1** su Stuttgart–Heidenheim), gli indisponibili `max(xG+xA
persi)` (fino a ~1,9), il riposo 1,5-2,0, il pressing 1,2. Conseguenza: con un rapporto di mercato
alto la riga del mercato scavalcava gli indisponibili, e lo stesso fattore cambiava posizione da
una scheda all'altra senza che cambiasse nulla di dichiarabile. Ora l'ordine è
`FACTOR_PRIORITY`, fisso, scritto in pagina nell'intestazione della card e nel codice:

1. Indisponibili — tolgono produzione misurabile (xG+xA/90) direttamente;
2. Valore di mercato titolari — effetto misurato più forte fra i fattori di rosa (1,87 contro
   1,43 punti/gara, §1);
3. Rendimento per sede — separa le gare più di ogni altro indicatore (10,6% → 68,2%, §3);
4. Pressing (PPDA) — 3,43 contro 3,10 xG/gara (§1);
5. Riposo corto — rischio infortuni, non pronostico (§1);
6. Disciplina e arbitro — sposta i cartellini, non il risultato (§4);
7. Forma e classifica (contesto) — ultima, dichiarata come contesto.

### 2.3 Soglie scelte a occhio → soglie misurate

Le soglie dei fattori nuovi non sono state «ragionevoli»: sono state scelte guardando la
distribuzione misurata sulle 66 schede in finestra, con l'obiettivo dichiarato di tenere la riga
**rara e informativa**:

| fattore | soglia | righe sulle 66 schede | perché quella |
|---|---|---|---|
| rendimento per sede | ≥0,50 pt/gara, ≥5 gare per sede | 24 | 0,50 pt/gara su 19 gare ≈ 9-10 punti di differenza in una stagione: separa senza essere banale |
| disciplina (squadre) | Δ ≥0,8 gialli/gara, ≥5 gare | 20 schede hanno Δ ≥0,8 (su 58 con i dati) | sotto 0,8 il Δ è dentro il rumore di 5-7 gare |
| arbitro | ±10% dalla media di lega, ≥20 gare in carriera | 13 schede su 32 con i requisiti | a ±15% restano 7 schede, a ±20% 4: troppo raro per essere utile |

### 2.4 «Non cambiano la previsione salvata» — verificato, non presunto

La card lo afferma dal 7/10. Verificato in questo giro con la ricerca dei call site:
`absences_tilt`, `rest_tilt` e `market_value_tilt` esistono in `models/predict.py` e sono chiamati
**solo** da `scripts/audit_modelli.py` (righe 267, 324, 378), mai da `predict_matches()`. Le 28
righe di `predictions.parquet` che hanno le colonne `market_value_adj`/`rest_factor_*` popolate
sono di un run del **20/09/2026** (`made_at` 2026-09-20 13:00): gare già giocate, per le quali la
card non si stampa. La dicitura resta vera per tutte le 66 schede in cui compare. Il punto 2 di
`docs/57` §7 (cablare i tilt o rimuovere il codice) resta **aperto**.

### 2.5 `verify_site` nascondeva i problemi invece di stamparli

Il riepilogo per tipo (`by_kind`) assumeva che ogni messaggio contenesse «: »: su un messaggio
senza quel separatore il gate cadeva con `IndexError` **dopo** aver eseguito tutti i controlli,
quindi i problemi trovati non venivano stampati. Trovato l'8/10 mentre si misurava una build
ancora in scrittura. Ora c'è una chiave di ripiego (le prime tre parole del messaggio).

---

## 3. Fattore nuovo: rendimento per sede

**Perché.** Il rendimento per sede è il confronto più usato dagli addetti e il meno presente nel
sito: «Le due squadre» dà i totali di stagione, «Confronto di stagione» la classifica, «Come
arrivano» le ultime 6 gare senza distinzione di sede. La letteratura di settore tratta lo split
casa/trasferta come variabile propria (i modelli di riferimento la usano con *shrinkage* verso la
media di sede della lega: 1,74 pt/gara in casa e 1,26 in trasferta, `github.com/andyscanzio/nl-predict#73`).

**Misura (6.307 gare, 3 stagioni).** PPG casalingo della squadra di casa meno PPG esterno
dell'ospite, calcolati sui 365 giorni precedenti, con almeno 5 gare per sede:

| Δ pt/gara per sede | n | vittorie della casa | IC 95% | quota implicita (normalizzata) |
|---|---|---|---|---|
| ospite ≥1 pt migliore | 235 | **10,6%** | 7,3-15,2 | 12,0% |
| ospite 0,3-1 migliore | 863 | 22,6% | 19,9-25,5 | 21,1% |
| pari (±0,33) | 1.929 | 34,6% | 32,5-36,7 | 35,8% |
| casa 0,3-1 migliore | 1.975 | 46,5% | 44,3-48,7 | 48,5% |
| casa ≥1 pt migliore | 1.305 | **68,2%** | 65,6-70,7 | 70,4% |

Lettura onesta, ed è quella che sta nel ⓘ: lo split **separa moltissimo** (dal 10,6% al 68,2%), ma
le quote dicono quasi la stessa cosa (12,0% → 70,4%). Non è quindi un vantaggio informativo sul
mercato: è contesto, e come tale è pubblicato — con i numeri e il campione, non come pronostico.

**Copertura.** 47 schede su 66 pubblicano un numero (24 in tabella + 23 nella riga fuori tabella)
e 19 dicono «non calcolabile (meno di 5 gare per sede nella finestra)»: sono neopromosse e squadre
con poche gare nel massimo campionato nella finestra (esempio misurato: Venezia, 3 gare casalinghe
e 2 esterne). Conteggio letto dalle 66 pagine generate: 24 righe + 23 voci fuori tabella con il
valore + 19 voci «non calcolabile» = 66. (La copertura grezza misurata a monte sulle 67 gare in
programma era 48: il conto non è confrontabile con quello delle pagine, perché una gara in
programma non ha la card e la soglia decide se il numero finisce in tabella o fuori.)
Il passaggio dei nomi per `canonical()` — la stessa normalizzazione dei modelli — è quello che ha
portato la copertura da 31 a 48 schede: senza, «Nottm Forest» del calendario e «Nott'm Forest»
dello specchio restavano due squadre diverse.

---

## 4. Fattore nuovo: disciplina e arbitro

**Perché.** L'arbitro era già in «Arbitro e meteo», ma come anagrafica (nome, gare, gialli/gara,
media del campionato) e senza il confronto con quanto le due squadre prendono davvero. La
letteratura è netta sul fatto che l'identità dell'arbitro conti sui provvedimenti: effetti fissi
significativi su gialli e rigori assegnati (Boyko et al. 2007 su 5.244 gare di Premier,
`tandfonline.com/doi/full/10.1080/02640410601038576`; rassegna in Dohmen & Sauermann, *Referee
Bias*, `econstor.eu/bitstream/10419/110093/1/dp8857.pdf`), e con il VAR rigori e rossi sono
aumentati in modo misurabile (DiD su 1.864 gare: +0,07 rigori e +0,07 rossi a gara,
`frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2026.1769008/full`).

**Misura (375 gare finite, 333 con l'arbitro).**

* La media di carriera pubblicata dalla fonte **ordina** gli arbitri: gli arbitri sopra la mediana
  dichiarata dànno **3,80** gialli/gara contro **3,19** degli altri (166 contro 167 gare);
  correlazione fra media dichiarata e gialli della gara **0,24**, pendenza 0,55.
* La media dichiarata **non** è la previsione della gara: dichiara 4,12, la media reale
  dell'archivio è 3,49 (campionati e stagioni diversi). Per questo la card confronta l'arbitro con
  la media delle designazioni **della stessa lega**, non con un valore assoluto.
* Sui **rigori** la media di carriera non predice nulla: 0,271 rigori/gara sopra la mediana contro
  0,216 sotto, correlazione **0,05**. La riga quindi parla di cartellini e lo dice nel ⓘ: un
  fattore che non si misura non si pubblica.
* Dispersione fra arbitri: sui 5 arbitri con ≥5 gare in archivio (26 gare) l'identità
  dell'arbitro spiega il **17%** della varianza dei gialli di gara (dal 1,67 di Allard Lindhout al
  4,20 di Sander van der Eijk). Campione piccolo, dichiarato come tale: serve a motivare il
  fattore, non a quantificarlo.

**Come è fatta la riga.** Due colonne = gialli e falli/gara di ciascuna squadra nella stagione
(minimo 5 gare); Δ = differenza di gialli; impatto = lo scarto dell'arbitro dalla media di lega,
più la squadra più esposta se anche il Δ delle squadre supera la soglia. Scatta se **almeno una**
delle due condizioni è sopra soglia; altrimenti entrambe finiscono nella riga fuori tabella con il
loro valore («disciplina +0,2 gialli/gara (soglia 0,8) · arbitro +4% sulla media di lega (soglia
±10%)»). Copertura: 58 schede su 66 hanno i cartellini di entrambe le squadre, 39 su 67 gare in
programma hanno un arbitro con le statistiche pubblicate (minimo 12, mediana 30, massimo 56 gare
in carriera — da qui la soglia di 20).

---

## 5. Misurati e non pubblicati

La parte più utile dell'audit è questa: tre candidati che sembravano buoni **non** hanno retto la
misura, e la card lo dichiara invece di tacerlo.

| candidato | misura | verdetto |
|---|---|---|
| **Distanza della trasferta** (km in linea d'aria fra lo stadio dell'ospite e quello della gara) | 375 gare, 354 km medi: punti dell'ospite 1,03 (≤50 km) · 1,36 (50-150) · 1,23 (150-300) · 1,26 (300-600) · 1,38 (>600). Nessun andamento; gli xG dell'ospite calano (1,55 → 1,31) ma i punti no. Derby cittadino: 7 sole gare | **non pubblicato.** La letteratura è divisa (Kitman Labs la indica come prima causa; le analisi sulle leghe inglesi non trovano effetto: `gwilymlockwood.com/2017-05-16/distance-travelled-and-away-performance`). Sul nostro perimetro — 7 campionati nazionali, 354 km medi — non c'è effetto misurabile |
| **Età media dei titolari** | 375 gare: punti della casa 1,48 (casa ≥2 anni più giovane) · 1,57 (1-2 più giovane) · 1,37 (pari) · 1,52 · 1,56 (≥2 anni più esperta). Correlazione Δ età / punti della casa **0,017** | **non pubblicato.** Nessun segnale |
| **Turnover per impegno ravvicinato** (gara successiva entro 3 giorni) | 750 osservazioni: 1,50 punti e 2,10 xG con un impegno ≤3 giorni (n=**16**) contro 1,35 punti e 1,53 xG con ≥7 giorni (n=520) | **non pubblicato.** Il campione è 16 gare e sono le squadre più forti (quelle in Europa): il segno è opposto a quello atteso e illeggibile. Il meccanismo esiste, ma qui non è misurabile |
| **Rigori per arbitro** | 0,271 contro 0,216 rigori/gara, correlazione 0,05 | **non pubblicato** (§4) |
| **Meteo come riga della card** | temperatura >30 °C: 21 gare, 3,95 gialli/gara contro 3,48 delle gare a 16-25 °C (i gol non si muovono: 3,14 contro 3,18). Vento: mai oltre 12 km/h in 442 gare. Pioggia: la probabilità è pubblicata **solo** per le gare future (67 righe su 442), quindi sulle finite non è misurabile | **non pubblicato nella card dei Fattori.** Il meteo ha già una card sua (`docs/56` §3 ha appena tolto le ripetizioni del testo) e una terza copia sarebbe un passo indietro. La misura sul caldo resta qui e può entrare come nota in «Arbitro e meteo» |

Coerente con la letteratura anche il **cambio di allenatore**, valutato e scartato come fattore:
la revisione sistematica di 24 studi trova un miglioramento di breve periodo che sparisce dopo
~10 gare, nessun effetto su gol fatti/subiti e un effetto nullo sulla classifica finale, con una
quota attribuibile al ritorno verso la media (`thefactball.substack.com/p/new-manager-bounce`).
In più il sito non ha una data di ingaggio affidabile (gli snapshot partono da questa stagione),
quindi non saprebbe nemmeno dire «allenatore nuovo da N gare».

---

## 6. Cosa dice la card adesso, in una riga

```
Sei fattori quantitativi con soglie dichiarate — valore dei titolari ≥1,5× (o ≤0,67×),
indisponibili ≥2 assenti o 1 titolare abituale o 0,4 xG+xA/90 persi, riposo ≤4 giorni,
pressing (PPDA) ≤0,75× (o ≥1,33×), rendimento per sede ≥0,50 pt/gara su ≥5 gare per sede,
disciplina Δ ≥0,8 gialli/gara su ≥5 gare o arbitro oltre ±10% dalla media di lega su ≥20 gare —
più una riga di contesto (classifica e forma recente), dichiarata come tale.
```

La frase è generata dalle costanti `FACTOR_*` (`fattori_soglie_testo()`), stampata così com'è e
confrontata con la pagina dall'invariante [41]: il testo non può raccontare soglie diverse da
quelle che accendono le righe.

Copertura dei sei fattori sulle 66 schede (riga in tabella · voce fuori tabella):

| fattore | riga | fuori tabella |
|---|---|---|
| Forma e classifica (contesto) | 66 | 0 |
| Indisponibili | 61 | 5 |
| Disciplina e arbitro | 28 | 38 |
| Pressing (PPDA) | 26 | 40 |
| Valore di mercato titolari | 24 | 42 |
| Rendimento per sede | 24 | 42 |

Nessuna scheda lascia un fattore non nominato: è ciò che [41] impone, e vale anche per i due
fattori nuovi.

---

## 7. Prove

**Invariante [41] estesa** (`scripts/verify_site.py`): due etichette nuove in
`FACTOR_ROWS_AMMESSE`, due parole chiave nuove in `FACTOR_KEYWORDS` (quindi anche i due fattori
nuovi non possono sparire in silenzio), unità di soglia nuove nel riconoscimento dei numeri
(`gare`, `pt/gara`, `gialli/gara`, `%`) e controllo del campione nelle celle
(`FACTOR_ROWS_CAMPIONE`).

**Test nuovi** (`tests/test_panchina_notizie.py`):

* `test_fattori_rendimento_per_sede_finestra_campione_soglia` — la finestra di 365 giorni esclude
  una gara dell'anno prima, il minimo di 5 gare blocca un PPG su 3 gare, e sotto soglia il fattore
  è dichiarato fuori tabella con il suo valore;
* `test_fattori_disciplina_e_arbitro_due_soglie` — entrambi i trigger (squadre e arbitro), le celle
  «n.d.» quando mancano i cartellini di stagione, e l'arbitro con 8 gare in carriera che **non** è
  giudicabile;
* `test_fattori_ordine_fisso_e_campione_dichiarato` — l'ordine è quello di `FACTOR_PRIORITY` e il
  PPDA esce con il campione.

**Test aggiornati** (`tests/test_site.py`): `test_fattori_soglie_testo_viene_dalle_costanti` copre
le cinque soglie nuove; `test_verify_site_fattori_boccia_il_fattore_che_sparisce` passa da 4 a
**6** fattori che non possono sparire e aggiunge il caso «media di stagione senza numero di gare».

---

## 8. Aperti, per l'utente

1. **Il peso della card è salito al 9,5%** del testo visibile (era 6,6%): è l'effetto richiesto
   («quantità»), ma se la scheda sembra troppo lunga la prima candidata a uscire è la riga di
   contesto «Forma e classifica», che ripete in forma sintetica numeri già in «Le due squadre».
2. **La riga fuori tabella è lunga** (fino a 6 voci, ~430 caratteri): è il prezzo di non far
   sparire nessun fattore. Alternativa: nasconderla in un `<details>`, perdendo la visibilità
   della dichiarazione.
3. **`docs/57` §7.2 resta aperto**: i tre tilt (`absences_tilt`, `rest_tilt`, `market_value_tilt`)
   sono misurati ma non chiamati da `predict_matches()`. Cablarli è un lotto di modello
   (griglia pre-registrata, backtest, ricalibrazione), non una modifica di scheda.
4. **Il calore come nota in «Arbitro e meteo»**: la misura c'è (3,95 gialli/gara oltre 30 °C
   contro 3,48, su 21 gare) e la card del meteo è il posto giusto. Non fatto in questo giro per
   non toccare due card con lo stesso lotto.
5. **Sezioni successive** da revisionare con lo stesso metodo (`docs/57` §7.6): «Come arrivano»,
   «I giocatori che decidono», «Panchina e posta in gioco», «Mercato», «Vita del club»,
   «Previsione del modello ensemble», «Precedenti», «Verifica approfondita».

---

## 9. Come riprodurre tutto

```bash
.venv/bin/python scripts/audit_fattori.py                              # le misure dei fattori
.venv/bin/fda build                                                    # 441 / 2.364 / 7.494 (~5 min)
.venv/bin/python scripts/verify_site.py --site site --data data/processed   # 0 problemi · 167.585 controlli
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site
.venv/bin/python -m scripts.resa_375
.venv/bin/pytest -q && .venv/bin/ruff check .
```

I conteggi per riga e per voce fuori tabella sono letti dalle pagine generate
(`site/partite/*.html`, blocco `id="fattori"`): riepiloghi stampati a schermo, mai dati grezzi.

**Cosa non è verificato da qui** (dichiarato, non taciuto): le fonti esterne non sono raggiungibili
dal sandbox e non sono state interrogate — niente `collect`, nessuna sonda. Le misure riguardano i
dati già raccolti e il sito generato in locale. La resa **visiva** non è stata vista in un browser:
`resa_375` misura geometria e caratteri a 375 px, non è un giudizio estetico. La ricerca citata in
§4-§5 è letteratura pubblica letta in questo giro (link nel testo): è usata per motivare i
fattori, mai come numero pubblicato in pagina — i numeri in pagina vengono solo dai nostri
archivi.

---

**Prossimo passo.** La coda è in §8: decidere se il peso della card al 9,3% va bene così, se la
riga fuori tabella resta visibile, e se il lotto successivo è la nota sul caldo in «Arbitro e
meteo» oppure la prossima sezione della scheda (§8.5).
