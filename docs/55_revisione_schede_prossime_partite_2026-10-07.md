# 55 — Revisione delle schede delle prossime partite: sezione per sezione (2026-10-07)

**Richiesta utente:** «cosa c'è da fare al sito e al progetto? io avevo pensato di sistemare le
schede delle prossime partite, revisiona tutte le sezioni, dimmi cosa dovrebbero fare e se sono
fatte bene o devono essere migliorate».

**Metodo.** Nessun numero di questo documento è ripreso da un altro documento: tutto è stato
misurato **oggi** su questo checkout (`6cb14a7`, dati del run `e01de11`) con i comandi elencati
nell'appendice §9. Il campione è quello reale del sito di oggi: **66 schede pre-partita** (gare
del 9–11 ottobre, 9–10 per lega) su **441 schede totali**; le misure di struttura valgono su
tutte e 441. In questa sessione **non è stata fatta nessuna richiesta alle fonti esterne**
(nessun `collect`, nessuna sonda): si è lavorato sui Parquet e sul sito generato in locale.

---

## 0. Verdetto in breve

1. **La scheda pre-partita è in salute**: 66/66 con la stessa struttura (**25 id identici**), lo
   stesso indice (**14 voci**), il minimo di testo visibile al **91% della mediana**; i gate sono
   verdi (**0 problemi · 159.573 controlli**, 26.490 misure di resa a 375 px, 517 test).
2. **Le sezioni fanno il loro mestiere**, con tre eccezioni vere e misurate: **Mercato** (dati
   duplicati: le voci pubblicate sono **×1,8** quelle reali), **EPV pre-match** (indice con
   costanti arbitrarie che sul **30% delle schede contraddice il favorito pubblicato**) e
   **Arbitro e meteo** (le soglie scritte nel testo non sono quelle usate dal codice; l'etichetta
   «estremo» scatta con pioggia al 31%).
3. **Due difetti di leggibilità numerica** in «Fattori che spostano la partita» (ξ «0,0018»,
   «RPS 0,20 tipico»: numeri per addetti, non per lettori) e **una ridondanza nuova**: i punti
   contro xPTS si dicono in **4 card diverse** su 34 schede su 66.
4. Il resto della coda è cosmetico o già deciso: nessuna decisione di prodotto è stata presa in
   questo documento, la coda è in §7 e aspetta la scelta dell'utente (§8).

---

## 1. Le misure di oggi (gate completi rifatti da zero)

| Verifica | Esito | Comando |
|---|---|---|
| Suite | **517 passed** (70,8 s) | `pytest -q` |
| Lint | `All checks passed!` | `ruff check .` |
| Build | exit 0 — **441** schede / **2.364** partite / **7.496** giocatori | `fda build` |
| Invarianti di pubblicazione | **0 problemi · 159.573 controlli** su **4.205 pagine** | `scripts/verify_site.py` |
| Parità fra le schede pre-partita | **66** schede · struttura **identica (25 id)** · indice **uguale in tutte (14 voci)** · testo minimo 19.883 = **91%** della mediana | `scripts/parita_schede.py site` |
| Resa a 375 px | **26.490 misure · 0 problemi** | `scripts/resa_375.py` |
| Censimento sezioni | 20 card-foglia per scheda, tutte 66/66 salvo «Precedenti» 64/66 | `scripts/prematch_sections.py` |
| Audit sezione per sezione | 0 incoerenze sui controlli storici (margine hero 227 righe lette, 0 incoerenti) | `scripts/audit_match_sections.py` |
| Pagine «Oggi»/«Prossime» | `prossime.html` **531.850 byte** su tetto 1,8 MB · **273 righe** (66 card ricche + 207 righe calendario) · `index.html` 23.457 byte (oggi 0 partite, sosta nazionali) | misure dirette |

Sul lato GitHub, nello stesso momento: **0 issue aperte**, **0 PR aperte**, daily **#220**
(`37656789947`) verde, `lab` verde (5/10), `benchmark-quote` verde (3/10). Non serve nessun
intervento di emergenza.

---

## 2. Cosa deve fare una scheda delle prossime partite (il metro di questa revisione)

Una scheda pre-partita pubblica serve a rispondere, nell'ordine in cui un lettore se le pone, a
quattro domande — e ogni sezione deve rispondere a **una** di queste, senza ripetere le altre:

1. **Che partita è?** (identità, forma, posta in gioco, condizioni, chi c'è e chi non c'è);
2. **Cosa dice il modello?** (la probabilità, i mercati derivati, e *come* ci è arrivato);
3. **Cosa l'ha spostata e cosa può spostarla?** (fattori quantitativi con soglie, assenze,
   riposo, arbitro, meteo);
4. **Quanto è affidabile?** (frequenze storiche per fascia, verifica dei numeri, fonti e
   copertura, stati «dato non pubblicato dalla fonte»).

Il metro di giudizio non è «il numero è giusto» (quello lo garantiscono i 159.573 controlli): è
**il numero giusto detto in modo che il lettore possa verificarlo, con un soggetto chiaro e senza
contraddire altri numeri della stessa pagina** (`docs/20` §0, regola di lettura).

---

## 3. Sezione per sezione: verdetto

Legenda: ✅ **fatta bene, non toccare** · ⚠️ **utile ma da migliorare** · ❌ **difetto misurato,
da correggere**.

| # | Sezione (id) | A cosa serve | Verdetto | Prova di oggi |
|---|---|---|---|---|
| 1 | Analisi pre-partita (`lettura`) | la partita in 6–9 frasi, prima dei numeri | ✅ | 6,1–8,8 righe di media per lega (POR1 6,1 la più bassa); 0 frasi-macchina; i nomi degli assenti non si ripetono (rinvio a Infermeria) |
| 2 | Fattori che spostano la partita (`fattori`) | i fattori quantitativi con soglia dichiarata | ⚠️ | 6 righe: 1 «Modello e calibrazione» per addetti (ξ «0,0018», «RPS 0,20 tipico»); duplica xPTS (vedi #11); nota «+1 altri fattori sotto soglia… disponibili nei dati» poco chiara |
| 3 | Scontro tattico (`scontro`) | stili a confronto, fonte dichiarata per riga | ✅ | 8,7% del testo; radar stile con valori grezzi fra parentesi; avviso «due fornitori diversi» su 2/66 schede (dove serve) |
| 4 | **EPV pre-match** (`epv`) | un secondo indice di contesto (punti, sede, differenza reti) | ❌ | **20/66 (30%) in disaccordo col favorito pubblicato** dal modello; pesi e costanti scritti a mano nel codice; fonte citata non verificabile da qui (vedi §4.2) |
| 5 | Fatti rilevanti (`fatti`) | 2–5 fatti secchi (streak, testa a testa) | ✅ | mediana **4** fatti per scheda (33 schede con 4, 18 con 5, 11 con 3, 4 con 2); nessuna riga ripetuta |
| 6 | Come arrivano (`arrivi`) | la serie gara per gara con xG/xGA e tendenza | ✅ | **0 righe duplicate** su 66 schede; fonte per lega dichiarata (Understat dove copre, altrimenti FotMob) |
| 7 | I giocatori che decidono (`giocatori`) | chi pesa, con soglia di minutaggio | ✅ | **0 nomi duplicati**; legenda ◎/◇ data una volta sola (P2.1 di `docs/33`) |
| 8 | Le due squadre (`squadre`) | forma, xG/xGA/xPTS, pressing, riposo, indisponibili, distinta | ✅ | indisponibili in **una sola card** (mediana 1, max 18 → caso: nome ricorrente in più card solo per i giocatori citati altrove); distinta su **65/66** |
| 9 | Confronto di stagione (`confronto`) | la classifica e i numeri di stagione a confronto | ✅ | 1,9% del testo; «Posizione» con barra 20ª→1ª; nota metodologica in fondo |
| 10 | Panchina e posta in gioco (`panchina`) | allenatore, rendimento, obiettivi (Monte Carlo) | ✅ | 8,3% del testo; 12 gare di campionato simulate 10.000 volte; «classifica virtuale» con la riserva dichiarata |
| 11 | Clima del club (`clima`) | i segnali anomali con la loro soglia | ⚠️ | da sola è corretta, ma **i punti vs xPTS si dicono in 4 card** su 34/66 schede (narrativa + fattori + clima + card squadra) |
| 12 | **Mercato: arrivi e partenze** (`mercato`) | chi è arrivato e partito nella finestra in corso | ❌ | **874 righe duplicate** visibili su 66/66 schede; le voci pubblicate sono **×1,8** quelle reali (vedi §4.1) |
| 13 | Vita del club (`notizie`) | solo i fatti che possono spostare, con l'imbuto | ✅ | 9,4% del testo (il massimo, per sua natura); su 49/66 nessuna notizia pubblicabile → riga unica + tendina (regola P1.1); 0 titoli duplicati in pagina |
| 14 | **Arbitro e meteo** (`arbitro-meteo`) | chi fischia e con che numeri; le condizioni | ⚠️ | arbitro con nome **47/66** (19 «da definire», onesto), gialli/gara con confronto di lega **38/66**; meteo: soglie del codice ≠ soglie scritte nel testo, «estremo» su **14/66** schede con pioggia 31–50% |
| 15 | Precedenti (`precedenti`) | il bilancio storico e gli ultimi incontri | ✅ | 66/66 con bilancio; 64/66 con «Ultimi precedenti»; 41/66 con la sotto-serie «con X di casa»; nota sul numero dei casi |
| 16 | Previsione del modello + Risultati esatti (`previsione`) | la risposta del modello e i mercati derivati | ✅ | 1X2 che somma 100 (`pct3`), Over 1,5/2,5/3,5 con confronto alla media di lega, doppia chance come somma dichiarata |
| 17 | Come nasce questa probabilità (`scomposizione`) | la catena a 4 passi, con i Δ | ✅ | passo «media pesata» vero + passo «griglia inclinata» + calibrazione; waterfall dei Δ in fondo |
| 18 | Quando il favorito aveva questa forza (`fascia-storica`) | la frequenza passata per fascia di pronostico | ✅ | 5.895 gare fuori campione; IC di Wilson; bias dichiarato riga per riga |
| 19 | Dove si colloca questa partita (`posizione-lega`) | il totale gol sulla scala del campionato | ✅ | percentile di lega con barra 2°–98°, mediana e media di lega marcate |
| 20 | Quando arriva il primo gol (`primo-gol`) | il ritmo dei gol e chi segna prima | ✅ | distribuzione osservata della stagione + banda del modello, con le due fonti etichettate |
| 21 | Verifica approfondita (`verifica`) | matrice dei punteggi e distribuzione dei gol | ✅ | chiusa di default (0,6% visibile + 7,1% in tendina); nessun conteggio scritto a mano |
| 22 | Blocco post-partita (`postpartita`, `statistiche`, `cronaca`, cartine) | com'è andata, con xG/xGOT/tiri | ✅ | fuori dal perimetro di questa richiesta; copertura 375/375 gare finite, assist risolti su 841 gol |

**Pagine «Oggi» e «Prossime» (le righe della lista).** Misurate oggi: `prossime.html` **531.850
byte** (29,5% del tetto), **273 righe** = 66 card ricche + 207 righe di calendario compatto. Sulle
66 card ricche il blocco «contesto rapido» ha meteo **66/66**, infermeria **65/66**, precedenti
**64/66**, arbitro **47/66** (gli altri 19 aspettano la designazione). Le righe del calendario
compatto (oltre i 7 giorni) portano di proposito solo data, 1X2, gol attesi e Over 2,5: è la
scelta di `docs/11` §P0, confermata. **Verdetto: ✅**, con una nota di manutenzione (prossime.html
è al 29,5% del tetto: la paginazione di `docs/19` §2.1 non serve ora).

---

## 4. I tre difetti misurati (❌)

### 4.1 Mercato: le voci pubblicate sono ×1,8 quelle reali

**Osservato.** Nella card «Mercato: arrivi e partenze» di Genoa–Fiorentina (10/10) la stessa riga
compare due volte:

```
Arrivi   Cody Drameh      da Hull · 01/09/2026      4,5 M€
Arrivi   Cody Drameh      da Hull · 01/09/2026      4,5 M€
Partenze Jeff Ekhator     a Juventus · 01/07/2026   16 M€
Partenze Jeff Ekhator     a Juventus · 01/07/2026   16 M€
```

**Misura (sulle 66 schede di oggi, il file HTML pubblicato).**

| Misura | Valore |
|---|---|
| Schede con almeno una riga duplicata nella card Mercato | **66/66** |
| Sotto-card squadra con almeno un movimento ripetuto | **128/132** |
| Righe duplicate visibili in totale | **874** |
| Movimenti distinti che risultano ripetuti | **437** |
| Movimenti pubblicati sulle 132 squadre in finestra | **676 arrivi · 932 partenze** |
| Movimenti reali (dopo la chiave normalizzata) | **377 arrivi · 517 partenze** |
| Gonfiamento dei conteggi | **×1,79 arrivi · ×1,80 partenze** |

Peggiori: Venezia 34 annunciati contro 17 reali, Genoa 26/15 e 52/28, Bologna 53/29 partenze,
Ajax 48/25 partenze. I conteggi in testa alla card («26 arrivi · 52 partenze») sono quindi gonfi
di circa il doppio, e lo stesso vale per i bilanci se qualcuno li sommasse a mano.

**Causa, misurata nel Parquet.** La chiave dell'upsert è
`("team_id", "player_name", "direction", "counterpart", "date")` (`store.py`, `TABLE_KEYS`), e i
due duplicati **differiscono proprio in uno di quei campi**, in due modi entrambi reali:

1. **l'ora del timestamp** — `date` è al secondo (`2026-06-30T23:34:10Z` contro
   `2026-06-30T21:34:10Z`): stesso giorno, stesso minuto, **due ore di differenza** (142 gruppi);
2. **i diacritici del nome** — `Aleksić`/`Aleksic`, `Vonić`/`Vonic`,
   `Milinković-Savić`/`Milinkovic-Savic`, `Boudache`/`Boudache` con la dieresi (16 squadre).

Due righe con lo stesso fatto restano quindi due righe distinte, e la card le pubblica entrambe.

**Perché i gate non l'hanno visto.** `verify_site [26]` riconcilia la card col Parquet — e la card
*è* coerente col Parquet: i duplicati sono a monte, nella tabella. `parita_schede` misura la
struttura, non l'unicità delle righe. Nessun invariante dice «una riga per movimento».

**Fix proposto (P0, meccanico).** In `MatchAnalysis.transfer_window` (e, per coerenza dei
conteggi, dove si contano i movimenti): normalizzare prima di deduplicare — nome senza diacritici
e senza punteggiatura (`soft_key` esiste già in `analysis.py`), controparte allo stesso modo,
`fee_text` normalizzato, **data al giorno**. Poi `drop_duplicates` su quella chiave. Effetti:
conteggi e bilanci dimezzati verso il vero, righe ripetute 874 → 0 attese. Serve anche
un'invariante nuova in `verify_site` (**[39]**: nessun movimento ripetuto nella card, chiave
normalizzata) e 2–3 test con i casi reali (diacritici, ora diversa) come fixtures — così il
difetto non può rientrare. Costo: ~25 righe di codice, un test, i gate pieni.

### 4.2 EPV pre-match: un secondo indice che contraddice il modello in 1 scheda su 3

**Osservato.** La card «EPV pre-match» (uscita dall'audit del 20/09) dà un verdetto tutto suo —
«leggero vantaggio casa», «vantaggio trasferta EPV», «equilibrata» — accanto a quello del modello.

**Misura (sulle 66 schede pubblicate).**

| Misura | Valore |
|---|---|
| Etichette | casa 36 (28 «vantaggio» + 8 «leggero») · trasferta 20 (12 + 8) · equilibrata 10 |
| **Schede in cui l'EPV contraddice il favorito del modello** | **20/66 (30%)** |
| Esempi | Atalanta–Venezia: modello trasferta, EPV casa (0,35) · Leicester–Hull: modello trasferta, EPV casa (0,36) · Roma–Como: modello trasferta, EPV casa (0,36) · Union Berlin–Elversberg: modello casa, EPV trasferta (−0,52) |
| Andamento dell'indice | nel codice: `0,4·(PPG. diff) + 0,3·(1×0,5) + 0,2·(GD ultimi 3) + 0,1·pos`, con `venue = 1,0` **costante** → **+0,15 fissi alla squadra di casa** in ogni partita |
| Le stesse misure in 4 card | punti, PPG, posizione e differenza reti degli ultimi 3 compaiono anche in «Confronto di stagione», nella forma dell'hero e in «Dove si colloca» |
| Riga dei gol attesi | «1,18 1,72 **2,90 tot (media lega 1,45)**»: il 2,90 è un **totale**, l'1,45 è una **media per squadra** — accostati senza dire che il riferimento è 2,90 (= 2×1,45) |

**Perché è un problema e non un'opinione.** L'EPV non è presentato come indice di contesto ma
come *«Confronto EPV attesi vs modello DC+Elo»*, con una riga «Modello vs EPV Δ diff gol»; un
lettore legge due verdetti e nel 30% dei casi sono opposti. In più: i pesi (0,4/0,3/0,2/0,1) sono
scritti a mano nel codice, il `venue` è una costante che sposta tutti i verdetti di +0,15, la
soglia «estremo» del contesto gol è per costruzione `1,6 × gol medi di lega` (mai misurato), e la
fonte citata (Bundesliga, `PMC12640942`) **non è verificabile da questo sandbox** (rete limitata a
GitHub/PyPI: non è una prova che sia sbagliata, è la prova che oggi non la si può confermare).

**Tre strade, da decidere (è una decisione di prodotto, non un fix).**

* **(A, raccomandata, costo basso)** declassare l'EPV **dentro «Fattori che spostano la partita»**
  come *una riga*, con l'etichetta esplicita «indice di contesto — non è una previsione, non entra
  nel modello»: sparisce il secondo verdetto, resta il valore informativo, e la card `#epv` da
  sola (0,9% del testo + una voce d'indice) si libera.
* **(B)** tenerlo come card ma con i **pesi stimati** (candidato del laboratorio con griglia
  pre-registrata e misura ΔRPS/log-loss fuori campione) e senza la costante di sede.
* **(C)** rimuoverlo (come si è fatto con SofaScore): è l'unica strada che non richiede misure
  nuove, ma butta via 3.756 righe di contesto che oggi qualcuno legge.

### 4.3 Arbitro e meteo: le soglie del testo non sono quelle del codice

**Osservato.** La riga «nella norma» dichiara al lettore i propri criteri: *«precip <30%, 10-28°C,
vento <15 km/h»*. La riga «⚠ estremo — può spostare ritmi» scatta invece con
`precip ≥ 30`, `temp ≥ 30` **o `≤ 5`**, `vento ≥ 15` (`analysis.py`, filtro `weather["extreme"]`).

| Misura | Valore |
|---|---|
| Schede con meteo «estremo» | **14/66**, tutte per pioggia fra **31% e 75%** (vento 5–7 km/h, 11–16 °C) |
| Soglie incoerenti fra testo e codice | fra **5 e 10 °C** e fra **28 e 30 °C** la pagina direbbe «nella norma» dentro un intervallo dichiarato che non lo comprende (oggi 0 casi: difetto latente, non attivo) |
| Arbitro | nome 47/66 (19 «da definire» — dichiarato), gialli/gara con confronto di lega 38/66, falli e rigori dove la fonte li dà |

**Perché conta.** «Può spostare ritmi» con una probabilità di pioggia del 31% a tre giorni di
distanza è un'affermazione non sostenuta: gli stessi riferimenti citati dall'audit del 20/09
indicano pioggia >50%, vento >20 km/h, temperatura >30 °C come soglie di impatto. Qui l'etichetta
dipinge 14 partite su 66 come condizionate dal meteo senza che nessuna misura interna lo dica.

**Fix proposto (P0/P1).** (a) stesse soglie in testo e codice (una sola costante condivisa, letta
dal template); (b) due etichette distinte: «pioggia probabile (>30%)» — informativa — e «condizioni
estreme» solo oltre le soglie di impatto (50% / 20 km/h / 30 °C), con la ricerca a supporto già in
`docs/audit-scheda-prepartita-2026-09-20.md` §19; (c) invariante **[40]** che confronta i due testi
delle soglie con i valori usati dal codice, così non possono divergere di nuovo.

---

## 5. Migliorie proposte (⚠️, piccole e misurabili)

| # | Dove | Cosa | Perché (misura di oggi) | Costo |
|---|---|---|---|---|
| M1 | Fattori che spostano | Togliere dal primo piano la riga «Modello e calibrazione» (ξ a 4 decimali, «RPS 0,20 tipico») o riscriverla in parole («ξ 0,0018», «λ corrette del 3,9%», «errore tipo del modello su 5.895 gare: 0,20») | è l'unica riga della card che un lettore non può verificare da solo; 6/6 schede la mostrano | basso |
| M2 | Fattori / Clima / squadre / narrativa | xPTS **in un posto solo** (card squadra) e richiami senza numeri nelle altre | i punti vs xPTS si dicono in **4 card** su 34/66 schede (regola di `docs/30`) | basso |
| M3 | Fattori | La nota «+1 altri fattori sotto soglia non mostrati in tabella ma disponibili nei dati»: o si nominano, o si toglie | dice che esistono dati che il lettore non vede, senza dirgli quali | basso |
| M4 | Indice (nav) | Aggiungere «Fatti» (l'ancora `#fatti` esiste già, la sezione è 66/66) | unica sezione presente in tutte le schede e fuori dall'indice; l'invariante [33] la coprirebbe subito | basso |
| M5 | EPV | Come M4 di §4.2: la riga dei gol attesi con il confronto esplicito (2,90 vs 2,90 di lega), non «media lega 1,45» | l'accostamento totale/media per squadra si legge come un errore di conto | basso (muore con §4.2-A) |
| M6 | Precedenti | Portare la sotto-serie «con X di casa» da 41/66 a 66/66 dove i casi bastano (soglia 8 dichiarata) o dire perché non c'è | oggi 25 schede non hanno la riga e non dicono il motivo | medio |
| M7 | Post-partita (fuori perimetro) | Nessun intervento proposto: copertura 375/375, statistiche avanzate, portieri, cartine | richiesta dell'utente sulle **prossime** partite | — |

---

## 6. Cosa NON va toccato (e perché)

* **La struttura e la parità fra leghe**: 25 id identici, indice uguale in tutte, minimo di testo
  al 91% della mediana — il gate `parita_schede` esiste per questo e oggi è verde.
* **Le spiegazioni metodologiche** (posizione delle fonti, finestre, soglie nei tooltip): sono la
  ragione per cui i numeri sono verificabili. La ridondanza da correggere è quella dei **valori**
  (xPTS), non delle note.
* **«Vita del club» senza notizie** (49/66 schede): la riga unica + tendina è la soluzione
  approvata il 18/09 (`docs/29`) e regge; non tornare al testo esteso.
* **L'indice in fondo alla pagina, la verifica chiusa, i marcatori ◎/◇**: decisioni già misurate
  (`docs/31`, `docs/32`, `docs/33`).
* **Nessuna quota bookmaker** e **nessuna nuova fonte**: le tre correzioni di questa revisione si
  fanno con i Parquet già raccolti e zero richieste esterne.

---

## 7. Coda proposta (ordine di lavorazione)

1. **P0 — Mercato ×1,8** (§4.1): dedup normalizzata + invariante [39] + test. È un difetto vero,
   visibile su tutte le 66 schede, e si corregge senza decisioni.
2. **P0 — Meteo** (§4.3): soglie condivise fra testo e codice, doppia etichetta, invariante [40].
3. **P1 — EPV** (§4.2): decisione utente fra A (riga nei Fattori, raccomandata), B (candidato
   laboratorio), C (rimozione).
4. **P1 — M1/M2/M3/M4**: quattro interventi piccoli di leggibilità e ridondanza, tutti con misura
   prima/dopo sulle stesse 66 schede.
5. **P2 — M5/M6**: rifiniture (confronto EPV, sotto-serie dei precedenti).
6. **P3 — niente altro in coda**: le decisioni D1–D4 di `docs/53` §7 restano chiuse e la coda
   non bloccante di `docs/53` §6.2/§6.4 non cambia.

---

## 8. Domande per l'utente

1. **Si parte dai due P0** (Mercato + Meteo) in un unico lotto, con i gate pieni, e poi si decide
   l'EPV con il lotto già chiuso? *(raccomandato: sono gli unici due punti in cui il sito oggi
   scrive un numero sbagliato o un'affermazione non sostenuta)*
2. **EPV**: (A) riga dentro «Fattori», (B) rifatto con pesi stimati dal laboratorio, (C) rimosso?
3. **I quattro M1–M4** entrano nello stesso lotto dei P0 o in un secondo giro?

---

## 9. Appendice — come sono state prese le misure (per riprodurle)

```bash
python -m venv .venv && .venv/bin/pip install -e '.[dev]'      # sandbox fresco, PyPI raggiungibile
.venv/bin/fda build                                            # 441 schede · 2.364 partite · 7.496 giocatori
.venv/bin/python scripts/verify_site.py --site site --data data/processed
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site
.venv/bin/python -m scripts.audit_match_sections site
.venv/bin/python -m scripts.resa_375
.venv/bin/python -m pytest -q && .venv/bin/ruff check .
```

Le misure di §4.1, §4.2, §4.3 e §5 sono state prese con script `pandas`/`BeautifulSoup` letti dai
Parquet (`transfers.parquet`, `fixtures.parquet`) e dalle pagine generate in `site/partite/`
(riepiloghi stampati a schermo, mai dati grezzi): chiave normalizzata
`(team_id, direction, giorno, nome senza diacritici, controparte, importo)`, etichette EPV lette
dall'`h2` della card `#epv`, soglie meteo confrontate fra `analysis.py` e il testo del template.

**Cosa non è verificato da qui** (dichiarato, non taciuto): le fonti esterne (FotMob, Understat,
Open-Meteo, Google News) non sono raggiungibili dal sandbox e **non sono state interrogate**: le
misure riguardano i dati già raccolti e il sito generato. La resa visiva non è stata vista in un
browser (il gate a 375 px è statico); il documento `PMC12640942` citato dall'EPV non è
verificabile da qui.

---

## Prossimo passo

Nessun file di codice o dato è stato modificato in questa revisione. Su risposta dell'utente alle
domande di §8, il lotto successivo è: **P0 Mercato** (dedup + invariante [39] + test), **P0 Meteo**
(soglie condivise + [40]) e la decisione sull'EPV, con i gate pieni (517 test, `verify_site`,
`parita_schede`, `resa_375`) e un unico giro di PR.
