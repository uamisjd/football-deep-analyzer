# 57 — Schede partita, revisione sezione per sezione (2026-10-07)

Direttiva dell'utente: **«verifica che le schede delle partite siano fatte bene, revisiona ogni
sezione e controlla che funzioni bene e sia fatta bene, oppure miglioriamo. Inizia con *Analisi
pre-partita* e *Fattori che spostano la partita*»**.

Il documento è il verbale della revisione, sezione per sezione. Copre **due coppie**:

* **prima coppia** (§0-§6): «Analisi pre-partita» + «Fattori che spostano la partita», i due blocchi
  in testa alla scheda, che insieme pesavano il 13,6% del testo visibile di una scheda pre-partita;
* **seconda coppia** (§8-§9): «Scontro tattico» + «Fatti rilevanti», richiesta dall'utente prima del
  merge — «come si incontrano gli stili» e i fatti che la scheda racconta.

Per ogni difetto: **misura prima → correzione → prova**. Le misure sono rifatte sui Parquet già
raccolti e sulla build generata in locale (`fda build`): **nessuna richiesta alle fonti esterne**,
nessuna quota bookmaker. Le altre sezioni della scheda restano da revisionare con lo stesso metodo
(§7).

---

## 0. In breve

Build di riferimento: 441 schede, **66 pre-partita** (le altre 375 finite), 2.364 partite, 7.496
giocatori. Tutti i conteggi «su 66» sono su quelle schede.

| # | Difetto misurato | Prima | Dopo | Prova |
|---|---|---|---|---|
| 1 | **Righe una per squadra**: 132 righe «Riposo …» e 82 «Infermeria …», ognuna con «—» nella colonna dell'altra squadra e un Δ che mescolava unità (1,60×, «2 titolari», «21 giorni», «λ × 1,039») | 6 · 5 · 4 righe su 56 · 5 · 5 schede | **una riga per fattore**: «Forma e classifica (contesto)» 66, «Indisponibili» 61, «Pressing (PPDA)» 26, «Valore di mercato titolari» 20; 1 · 2 · 3 · 4 righe su 5 · 25 · 26 · 10 schede | invariante **[41]**, §1 |
| 2 | **Barra-percentuale non spiegata** accanto al nome, calcolata da un numero letto male: su `partite/5802947.html` una riga con 5 assenti e −0,9 xG+xA/90 usciva al **0%** | 66/66 schede, nessuna legenda | rimossa; [41] boccia la pagina se la barra torna | §1, [41] |
| 3 | **«Modello statistico» come riga** della tabella: RPS e ξ finivano nelle colonne delle **due squadre** — non è un confronto casa/ospite | 57/66 | nota a piè di card (`modello.testo`), 66/66; [41] ammette solo le 5 etichette di riga | §1, test |
| 4 | **Riposo ≥7 giorni** su tutte le righe: 19–23 giorni per ogni squadra delle 7 leghe, con **due verdetti opposti** (verde alla casa, rosso alla trasferta) per la stessa sosta | 132 righe | riga solo se **≤4 giorni**: oggi 0 righe, 66 schede lo dichiarano fuori tabella | §2, test |
| 5 | **Meteo**: «oltre la soglia di impatto» due volte sulla stessa riga e il 50% due volte | 5/66 | `segnalazioni` = valori puri, `livello_testo` una volta sola | §3, [40] aggiornata |
| 6 | **Link a un nome che in pagina non esiste**: «→ Infermeria» puntava a una card intitolata «Indisponibili (N)» | 66/66 pre-partita | «→ Indisponibili» | §4 |
| 7 | **Fattore che sparisce**: PPDA calcolabile ma vicino alla pari, non nominato da nessuna parte — il lettore non poteva distinguere «squadre simili» da «dato mancante» | 19/66 | voce «pressing 1,15× (soglia ≤0,75× o ≥1,33×)»; **0** schede senza il fattore | §5, test |
| 8 | **Etichetta «Sotto soglia»** applicata a dati *mancanti* («valore titolari non pubblicato») | 44/66 | «Sotto soglia **o non calcolabile**, non in tabella (casa e ospite)» + voci riscritte | §5 |
| 9 | **Markdown non reso**: il criterio sta in un attributo `title`, che non interpreta `**grassetto**` — usciva «**non** un secondo pronostico» | 66/66 | tolto; [41] vieta `**` e backtick nella card | §6, test |
| 10 | **Segni**: Δ con trattino ASCII (`-1,40`) accanto a numeri in colonna; indice di contesto senza segno (`indice 0,18`, `indice -0,97`) | 66/66 | «−» (U+2212) e indice firmato (+0,18 / −0,97); 0 numeri ASCII negativi nella card | §6 |
| 11 | **Colonna «Impatto» a colori senza legenda** | — | ⓘ nell'intestazione: verde = giova alla casa, rosso = alla trasferta, nessun colore = vantaggio non misurabile | §6 |

Peso delle due sezioni (quota del testo **visibile senza aprire le tendine**, mediana sulle 66):
«Fattori» **10,4% → 6,6%**, «Analisi pre-partita» 3,2% (invariata), pagina visibile mediana
**21.563 → 20.634** caratteri. La card ha perso la barra, la tabella per-squadra e la lista che
ripeteva ogni riga a parole: lo stesso contenuto in meno spazio, con il criterio nel ⓘ.

Gate finali (tutti rifatti da zero dopo l'ultima modifica al sorgente):

| Gate | Prima di questa revisione | Dopo |
|---|---|---|
| `pytest -q` | 524 passed | **529 passed** |
| `ruff check .` | pulito | pulito |
| `fda build` | 441 / 2.364 / 7.496 | **441 / 2.364 / 7.496** |
| `verify_site` | 0 problemi · 161.731 controlli | **0 problemi · 162.703 controlli** ([40] 441 pagine, **[41] 66 schede**) |
| `parita_schede` | 66 · identica (24 id) · indice 14 voci · min 91% | **66 · identica (24 id) · indice 14 voci · min 90%** |
| `resa_375` | 26.424 misure · 0 problemi | **26.424 misure · 0 problemi** |
| `prematch_sections` | Fattori 10,4% · visibile 21.563 | **Fattori 6,6% · visibile 20.634** |

Riferimenti delle sezioni: `docs/57` §1 (una riga per fattore, invariante **[41]**), §2 (riposo:
perché 19–23 giorni sono corretti), §3 (meteo), §4–§5 (narrativa e fattori dichiarati), §6
(rifiniture).

---

## 0.1 La stessa scheda, prima e dopo (`partite/5802947.html`, Lens–Lyon)

Le due versioni della card, testo letto dalla pagina (l'intestazione `Fattore · Lens · Lyon · Delta ·
Impatto` è la stessa nei due casi). **Prima** — 6 righe, di cui quattro non dicevano ciò che
sembravano dire:

```
🛌 Riposo Lyon            100%  —            20 gg        20 giorni          +ampio
💰 Valore di mercato      100%  56,6 M€      159,3 M€     1/2,8×             Trasferta +6% forza
🛌 Riposo Lens            100%  21 gg        —            21 giorni          +ampio
📊 Forma e classifica      50%  4 pt (0,80/g) GD3 -2      11 pt (2,20/g) …   indice -0,97 — contesto…
🧮 Modello statistico      50%  RPS 0,210 (738 gare)  ξ 0,0018   λ × 1,039   errore fuori campo 0,199
🏥 Infermeria Lens          0%  5 assenti — 1 titolare -0,9 xG+xA/90         riduce λ di ~0,52 gol
   (sotto: la stessa tabella riscritta a parole, riga per riga)
   Fuori dai sei per impatto (soglie comunque superate): Infermeria Lyon.
```

**Dopo** — 3 righe, una per fattore, con le due squadre nelle due colonne:

```
💰 Valore di mercato titolari ⓘ   56,6 M€                    159,3 M€                  2,8×            squilibrio a favore di Lyon
🏥 Indisponibili ⓘ                5 assenti · 1 titolare · −0,86 xG+xA/90  2 assenti · …   +0,77 xG+xA/90  pesa di più su Lens
📊 Forma e classifica (contesto) ⓘ  4 pt · 0,80/gara · GD3 −2  11 pt · … · GD3 +6   PPG −1,40 · GD3 −8 · pos −13  indice −0,97 — contesto
🧮 (nota a piè di card) Dixon-Coles + Elo … RPS 0,199 su 5.895 gare, 0,210 su 738 di questa lega …
Sotto soglia o non calcolabile, non in tabella (casa e ospite): riposo 21 giorni e 20 giorni
(soglia ≤4) · pressing 1,15× (soglia ≤0,75× o ≥1,33×).
```

Quattro cose che il lettore vede diverse, sulla stessa partita:

* **Il riposo non è più un «fattore»**: la vecchia card aveva due righe («Riposo Lyon», «Riposo
  Lens») con lo stesso verdetto «+ampio», e la barra al 100% che sembrava dire «riposo perfetto»;
  ora è una voce fuori tabella con i due numeri e la soglia, e le righe per squadra sono sparite.
* **L'«Infermeria» non esce più al 90%**: la riga di Lens (5 assenti, 1 titolare abituale, 0,86
  xG+xA/90 persi) usciva con la barra al **0%**, e il dato di Lyon comparve per la prima volta solo
  come «Fuori dai sei per impatto». Ora è **una** riga con le due squadre e il Δ in xG+xA/90.
* **Il modello non è una riga**: RPS e ξ stavano nelle colonne di Lens e Lyon (dove non
  significano nulla); ora è la nota in fondo.
* **La soglia si legge una volta**: nel meteo la stessa frase diceva «oltre la soglia di impatto»
  due volte e citava il 50% due volte (`… pioggia 75% (oltre la soglia di impatto 50%) (pioggia
  >50%, temperatura >30 °C, vento >20 km/h)`); ora è `… pioggia 75%` in narrativa e
  `oltre la soglia di impatto: pioggia 75% · soglie di impatto: pioggia >50%, …` nella card.

---

## 1. «Fattori che spostano la partita»: una riga per fattore

**Cosa non andava.** La tabella prometteva un confronto casa/ospite (due colonne intestate ai nomi
delle squadre) ma conteneva **righe per squadra**: su 66 schede, 132 righe «Riposo …» e 82
«Infermeria …», ognuna con «—» nella colonna dell'altra squadra. Il Δ mescolava unità diverse nella
stessa colonna — `1,60×`, «2 titolari», «21 giorni», `λ × 1,039` — senza dire l'unità. In più:

* la **barra-percentuale** accanto al nome non era spiegata da nessuna parte e veniva da un numero
  letto male (`-0,9 xG+xA/90` → `0,0`): su `partite/5802947.html` la riga con 5 assenti usciva al
  **0%**, cioè il fattore più pesante della partita sembrava il più leggero;
* la riga **«Modello statistico»** (57/66) infilava `RPS 0,202 (974 gare)` nella colonna della
  squadra di casa e `ξ 0,0018` in quella ospite: nessuno dei due numeri è un confronto fra le due
  squadre;
* ogni riga era ripetuta a parole in una lista sotto la tabella (stesso testo, tre volte in
  pagina: cella, `title`, lista).

**Cosa c'è ora.** Una riga per fattore, con etichetta, i valori di **entrambe** le squadre, un Δ
nella sua unità, l'impatto in parole e il criterio nel ⓘ (`help`). Etichette ammesse e nient'altro:
`Valore di mercato titolari`, `Indisponibili`, `Riposo corto`, `Pressing (PPDA)`, `Forma e
classifica (contesto)` — l'ultima dichiarata come contesto, non come pronostico. Il modello è
sceso a **nota a piè di card** (RPS fuori campione e ξ detto in parole). Le soglie non sono scritte
a mano: `fattori_soglie_testo()` le compone dalle costanti `FACTOR_*`, il template stampa **quella**
frase e [41] verifica che sia in pagina.

**Prova.** `scripts/verify_site.py` [41] (`check_fattori`): per ognuna delle 66 schede con la card —
soglie del codice citate *verbatim*; ogni riga con 4 colonne piene; etichetta fra le 5 ammesse;
ⓘ del criterio presente; barra-percentuale assente; markdown assente; i quattro fattori
quantitativi presenti **o in tabella o nella riga fuori tabella**; le soglie citate fuori tabella
dentro le `FACTOR_*`. Più i test:
`tests/test_panchina_notizie.py::test_fattori_una_riga_per_fattore_e_riposo_solo_se_corto`,
`tests/test_site.py::test_fattori_soglie_testo_viene_dalle_costanti`,
`tests/test_site.py::test_verify_site_fattori_boccia_il_fattore_che_sparisce`.

---

## 2. Riposo: da «tutte le righe» a «solo se corto» — e un residuo da decidere

Il fattore «riposo» scattava **sempre**: su 66 schede, 132 righe con 19–23 giorni per ogni squadra
delle 7 leghe, con due verdetti opposti — verde alla squadra di casa, rosso alla trasferta — per la
stessa identica sosta. Una sosta uguale per tutti non sposta una partita, e i giorni delle due
squadre sono già nella card «Le due squadre». Ora la riga esiste **solo se ≤4 giorni** (la soglia
dello studio UEFA già citato, RR 1,32) e negli altri casi il fattore è dichiarato fuori tabella.

**Misura.** Righe «Riposo»: **132 → 0**; schede che nominano il riposo fuori tabella: **66**;
schede con la riga: 0 (sul dataset attuale nessuna squadra è sotto i 5 giorni).

**Verificato: i 19–23 giorni sono il numero giusto, non un difetto (7/10/2026).** In una prima
lettura avevo attribuito il valore alla finestra di raccolta (`collect`, `past_days=3`): **era
sbagliato**, e i dati lo dicono in tre modi.

1. **Il codice legge il calendario di stagione, non la finestra.** `rest_days()` (e `rest_last()`)
   partono da `_rest_source()` = `fixtures` (tutte le 2.364 partite della stagione, con data e
   stato) più `cup_fixtures`; la finestra `[oggi−3, oggi+future]` decide **solo quali partite
   ricevono i dettagli** (formazioni, indisponibili, meteo, arbitro), non quali gare la scheda
   conosce.
2. **Due fonti indipendenti dicono la stessa cosa.** Calendario FotMob (`fixtures.parquet`): 375
   gare finite, l'ultima il **20/09/2026**; 1.989 programmate, la prima il **09/10**. Mirror dei
   risultati (`history.parquet`, scaricato da un'altra fonte): 212 gare dal 01/09, ultima il
   **20/09**, e nulla dopo. Anche le coppe si fermano: giornate di Champions/Europa il 07–13/09 e
   il 14–20/09, poi il **12/10**. Il calendario non ha buchi altrove (61–83 gare a settimana dal
   17/08 al 20/09, poi 61 dal 05/10): il vuoto di tre settimane è nell'**ordine del calendario**,
   non nei dati raccolti — è la sosta delle nazionali, come quella del 25/10→16/11.
3. **Conto rifatto a mano** su `partite/5802947.html` (Lens–Lyon, fischio 09/10): Lens ultima gara
   **18/09** (Monaco–Lens) → 21 giorni, Lyon **19/09** (Lyon–Rennes) → 20 giorni: sono esattamente
   i due valori in pagina.

Non c'è quindi niente da correggere nel calcolo, e trattare il riposo come *non fattore* (uguale
per le due squadre in una sosta) resta giusto. L'unico residuo era **visivo**: «21 giorni di
riposo · ampio» senza la data fa pensare a un dato vecchio. Il 7/10 la riga della card «Le due
squadre» è diventata «21 giorni di riposo (ultima gara 18/09) · ampio» — la data compare solo
quando il riposo è ampio (≥6 giorni), così non appesantisce i casi normali; `rest_last()` legge la
stessa base di `rest_days()` e ha il suo test.

---

## 3. Meteo: la soglia si dice una volta sola

Difetto (`docs/56` §3): ogni segnalazione portava la sua parentesi e il consumatore aggiungeva il
livello e le soglie, quindi sulla stessa riga si leggeva **due volte** «oltre la soglia di impatto»
e **due volte** il `50%` — 5 schede su 66. Ora `weather_flags()` restituisce `segnalazioni` come
**valori puri** (`pioggia 75%`) e un campo `livello_testo` («oltre la soglia di impatto» / «sopra
la soglia di segnalazione»): chi scrive la frase mette il livello una volta e le soglie una volta,
dalla stessa fonte delle costanti `WEATHER_*`.

**Misura.** Righe meteo con «oltre la soglia di impatto» ripetuto: **5/66 → 0/441**. La card
«Arbitro e meteo» ora dice `oltre la soglia di impatto: pioggia 75% · soglie di impatto: pioggia
>50%, temperatura >30 °C, vento >20 km/h`.

**Prova.** Invariante [40] aggiornata (soglie citate = costanti, nessuna ripetizione, livello
coerente coi valori nel Parquet) e **primo test su `weather_flags()`**, che prima non ne aveva
nessuno: 10 casi di confine presi dalle costanti (29/30/50/51% di pioggia, 30/31 °C, 5/4 °C,
15/21 km/h) più i dati mancanti e il fatto che `segnalazioni` non contenga mai la parola «soglia».
`tests/test_site.py::test_weather_flags_livelli_e_soglie_del_codice`.

---

## 4. «Analisi pre-partita»: rinvii che esistono davvero

* **«→ Infermeria» → «→ Indisponibili»**: il link portava a una card il cui titolo è «Indisponibili
  (N)». Il testo dell'ancora ora è quello che il lettore trova dove atterra: **65 schede
  pre-partita su 66** hanno il link (122 link in tutto), la sessantaseiesima — `partite/5887645.html`
  — non ha indisponibili pubblicati e quindi non ha nulla da rinviare; **0** schede finite lo
  mostrano (lì la tabella non c'è). Le ancore di destinazione esistono e sono verificate da
  `verify_site` [33] («ancora interna mancante»).
* **Niente doppioni con la tabella**: quando il fattore è una riga di «Fattori», la narrativa non
  lo ricopia. Vale per il **pressing** (la frase «X preme molto più di Y (PPDA …)» è saltata su
  tutte le schede in cui la riga esiste) e per il **valore di mercato** (`X vale N× Y nei titolari
  — squilibrio mercato`). Restano per le gare finite, dove la card non c'è.
  `tests/test_panchina_notizie.py::test_narrativa_non_ripete_i_fattori_della_tabella`.
* **Le assenze restano dette due volte**, di proposito: la frase «X deve rinunciare a N assenti,
  uno dei quali titolare abituale — nomi e impatto in *Indisponibili*» (sintesi, con il rinvio) e la
  riga della tabella (numeri, inclusa la produzione persa). **I due conteggi coincidono su 56
  schede su 56 confrontabili** (5 non lo sono: una delle due colonne è «distinta non pubblicata»),
  quindi non c'è contraddizione; se l'utente vuole «un dato in un posto» anche qui, la frase deve
  perdere i numeri e restare un puro rinvio.

---

## 5. Fattori che sparivano, e l'etichetta che mentiva

Due difetti trovati **girando le misure** di questo giro, non nei documenti precedenti.

1. **Il pressing calcolabile ma vicino alla pari non era nominato** (19 schede su 66): la riga
   scattava solo a rapporto ≤0,75× o ≥1,33×, e sotto quella soglia il fattore usciva dalla scheda
   senza traccia. Il lettore non poteva distinguere «squadre simili» da «dato mancante». Ora è una
   voce esplicita: `pressing 1,15× (soglia ≤0,75× o ≥1,33×)`, e anche l'errore di calcolo diventa
   una voce dichiarata invece di un `except: pass`.
2. **«Sotto soglia, non in tabella» copriva anche i dati mancanti** (44 schede su 66):
   «valore titolari non pubblicato» non è sotto soglia, è assente. Etichetta corretta in «Sotto
   soglia **o non calcolabile**, non in tabella (casa e ospite)» e voci riscritte
   («valore dei titolari non pubblicato dalla fonte», «indisponibili non pubblicati (distinta non
   disponibile)»).

**Come si vede il difetto 1 a occhio:** su `partite/5802947.html`, dopo la correzione, la riga
finale è «Sotto soglia o non calcolabile, non in tabella (casa e ospite): riposo 21 giorni e 20
giorni (soglia ≤4) · pressing 1,15× (soglia ≤0,75× o ≥1,33×)». Prima il pressing non c'era.

**Copertura dei quattro fattori sulle 66 schede** (riga della tabella · voce fuori tabella):
valore dei titolari 20 · 46; indisponibili 61 · 5; riposo 0 · 66; pressing 26 · 40. Nessuna scheda
lascia un fattore non nominato — è esattamente ciò che [41] impone.

---

## 6. Rifiniture della card (e residui fuori da questa coppia)

* **Markdown non reso** (66/66): il testo del criterio sta in un attributo `title`, che non
  interpreta `**neretto**`; usciva «**non** un secondo pronostico». Tolto, e [41] vieta asterischi e
  backtick nel blocco.
* **Segni**: i Δ della card usano il meno tipografico `−` (U+2212), non il trattino ASCII, e
  l'indice di contesto è firmato (`indice +0,18`, `indice −0,97`). Nella card: 0 numeri negativi in
  ASCII. **Il residuo del trattino ASCII è chiuso** in §8, con una misura che corregge quella
  scritta qui nella prima stesura: le «101 occorrenze, 90 in `#scomposizione`» **non si
  riproducono** — in `#scomposizione` il trattino fra cifre è 0, anche nel sorgente. Gli intervalli
  veri erano altrove: **375 nelle 375 schede post-partita** (`#lettura`, «Gara equilibrata negli xG
  (0,75-0,94)», «Risultato coerente con gli xG (2,14-1,50)») e **1 in `info.html`** («0,19-0,20
  bookmaker», mentre `accuracy.html` scriveva già «0,19–0,20» lo stesso numero). Ora: 0, con
  l'invariante `RANGE_ASCII` in [27].
* **Legenda del colore** della colonna «Impatto»: ⓘ nell'intestazione (verde = giova alla squadra
  di casa, rosso = alla trasferta; nessun colore = vantaggio non misurabile).

---

## 7. Aperti, per l'utente

1. ~~Riposo e finestra di raccolta~~ **chiuso**: il numero è corretto (sosta del calendario,
   verificata su due fonti indipendenti e ricalcolata a mano) e la card «Le due squadre» ora cita
   anche la data dell'ultima gara. Nessuna modifica a `collect` necessaria.
2. **I tre tilt** (`absences_tilt`, `rest_tilt`, `market_value_tilt` in `models/predict.py`)
   esistono, sono misurati da `scripts/audit_modelli.py`… e **non sono chiamati da
   `predict_matches()`**: la card «Fattori» descrive, non sposta la previsione. Tre strade: (A)
   cablarli e ricalibrare (è un lotto di modello, con backtest e verifica), (B) rimuovere il codice
   non usato, (C) lasciarlo com'è dichiarandolo. *Consigliata C in questa sede: finché la card dice
   «non cambiano la previsione salvata» il testo è vero; ma la dicitura va tenuta.*
3. **Assenze in due posti** (§4): tenere la sintesi in narrativa (misurata coerente) o toglierne i
   numeri.
4. **Valore dei titolari assente su 42 schede su 66** (`home_starters_value_eur` presente per 25
   gare su 67 in programma): è una lacuna di **raccolta**, non di scheda — la card lo dichiara. Da
   valutare se la fonte lo pubblica solo a distinta depositata.
5. ~~«Scontro tattico» + «Fatti rilevanti»~~ **chiuso** in §8-§9 (richiesta dell'utente prima del
   merge).
6. **Sezioni successive** della scheda da revisionare con lo stesso metodo: «Come arrivano»,
   «I giocatori che decidono», «Panchina e posta in gioco», «Mercato: arrivi e partenze», «Vita del
   club», «Previsione del modello ensemble» (con «Come nasce questa probabilità», «Quando il
   favorito aveva questa forza», «Dove si colloca questa partita», «Quando arriva il primo gol»),
   «Precedenti», «Verifica approfondita».
7. **Ridondanza (non contraddizione) fra «Scontro tattico» e radar**: i due rapporti del duello
   chiave (`1,88× la media gol della lega`) sono anche il valore grezzo della riga «Attacco × media»
   del radar — stesso numero, stessa fonte (classifica FotMob), due posti. Da decidere se togliere
   uno dei due quando si riprende la card.
8. **Un difetto trovato fuori dalle due coppie in revisione** e già chiuso: il test
   `test_transfer_window_stesso_movimento_con_ora_locale` era dipendente dall'ora di esecuzione —
   con «adesso» dopo le 22 UTC il `+2h` dell'ora locale cade nel giorno dopo e l'atteso non
   reggeva (fallito il 2026-10-07 alle 22:06 UTC: `06/10/2026` contro `05/10/2026`). Ora l'ora del
   campione è fissa a metà mattina: il test misura il dedup, non il fuso.

---

## 8. «Scontro tattico»: dai numeri inventati alle ancore dichiarate

Build di riferimento: **441 schede** con la card, **66 pre-partita** con il radar (il radar si stampa
solo prima della gara). Difetti, misure e prove:

| # | Difetto misurato | Prima | Dopo | Prova |
|---|---|---|---|---|
| 1 | **Il radar inventava un valore neutro**: dove il dato mancava stampava `50 (n.d.)` — barra al 50% e il numero 50 accanto a «(n.d.)». In `5781759` (Feyenoord–AZ) mancavano pressing **e** profondità, in entrambe le colonne | **80 celle** (66 schede con radar) | `n.d.` **senza barra e senza numero**; `norm_*` restituisce `None`, non 50 | [22b]: 66 radar ricalcolati dai Parquet, **0 problemi**; 80 celle «n.d.» |
| 2 | **Piè di card falso**: «100 = migliore in lega su quella metrica». Le ancore sono **fisse e scelte a mano** (attacco 0,5×→0 e 1,5×→100; difesa 1,5×→0 e 0,5×→100; PPDA 8→100 e 20→0; profondità 2→0 e 10→100; palle inattive 10%→0 e 60%→100): 100 non è un primato di lega | 66/66 radar | «100 è l'estremo alto della scala, non un primato di lega» + **un ⓘ per riga** con ancora e verso | [22b] confronta le barre col ricalcolo |
| 3 | **«Palle inattive %» letta come merito**: la scala premia chi ha la quota più alta di xG da palle inattive, che è una **dipendenza**, non una qualità | nessuna nota, e il piè di card diceva «100 = migliore in lega» | ⓘ della riga: «più alta = più dipendenza dalle palle inattive, non un giudizio di qualità» | §8 riga 5 di `helps`, test |
| 4 | **Banner non verificato**: «Confronto limitato a xG e profondità» — su 21 schede pre-partita con la nota, **19** mancavano di tutto il blocco Understat (anche la profondità): la frase elencava come disponibile un dato assente | 162 schede la stampavano | nota **costruita dai valori presenti**: «manca PPDA, PPDA concesso, passaggi profondi e passaggi profondi subiti per entrambe le squadre» (145) o «per una delle due squadre» (17) + «Le righe presenti restano confrontabili» | test `test_style_rows_copertura_understat_detta_davvero`; 162 schede |
| 5 | **Trattino ASCII negli intervalli** (residuo dichiarato in §6) | rev. §6: «101 in `#scontro`, 90 in `#scomposizione`» — **misura non riprodotta**: in «#scomposizione» 0, e in `#scontro` gli unici due intervalli erano «0-100» (testata e piè del radar) | en dash «–»; residuo vero corretto altrove: **375 occorrenze in `#lettura`** (375 schede post-partita) e 1 in `info.html` | invariante `RANGE_ASCII` in [27]: 0 in tutto il sito |

Cosa **non** è cambiato, per non allargare la revisione: la struttura della tabella (λ, DC, xG/xGA,
quote, PPDA, profondità), le graduatorie e il «duello chiave» di [22], la scomposizione xG come quota
interna a una sola fonte. Un solo dubbio resta **aperto e dichiarato** (§7): i due rapporti del duello
chiave (`1,88× la media gol della lega`) compaiono anche nel radar come valore grezzo della riga
«Attacco × media» — stesso numero, stessa fonte (classifica FotMob), due posti: è ridondanza, non
contraddizione.

Peso della card: 9,0% → **9,2%** del testo visibile di una scheda pre-partita (la nota di copertura
è più lunga della frase fissa che sostituisce).

---

## 9. «Fatti rilevanti»: due origini, e i numeri ricalcolati

La card diceva «Streak, testa-a-testa e forma recente (FotMob), tradotti e filtrati»: un elenco solo,
senza dire che erano **una fotografia scattata quando la gara è stata raccolta**. Misurato il
2026-10-07 su `insights.parquet` (402 righe, 67 gare da giocare, 3 righe per squadra — **nessun
duplicato**: lo scatto non viene dal nostro upsert):

* **79 fatti su 176 verificabili non tornavano** coi nostri risultati, e **75 su 175** non si
  riconciliavano con nessuna finestra (stagione in corso, stagione a cavallo dello storico, coppe);
* prova della staleness: per l'Atalanta il fatto «gol nelle ultime 5» vale **8 → 7 → 5 → 5 → 6 → 4**
  passando da una gara all'altra della stessa raccolta, mentre i suoi ultimi 5 risultati (23/08 →
  20/09) sommano **3**;
* contraddizioni secche (verificate a mano una per una): «Athletic Club imbattuta da 5 partite»
  (`5868088`) con una sconfitta nelle ultime cinque, «non tiene la porta inviolata da 5 partite» su
  Aston Villa, Marsiglia e Real Sociedad con un porta inviolata dentro la finestra;
* composizione delle **272 voci pubblicate** su 67 schede: **181 famiglia «forma» (67%)**, 16 record,
  75 altro.

| # | Difetto misurato | Prima | Dopo | Prova |
|---|---|---|---|---|
| 1 | **I numeri invecchiavano**: la famiglia «forma» (gol nelle ultime N, strisce, porta inviolata) è una foto della raccolta, non il numero di oggi | 181/272 voci (67%) | la famiglia **non si pubblica più da FotMob**: si pubblica il ricalcolo dalle nostre gare di **campionato** (`form_facts`, finestra 5, minimo 3 gare), rifatto a ogni build | [42]: 258 voci nostre su 66 schede, 0 problemi |
| 2 | **Nessuno sapeva da dove venisse il numero** | un elenco, un'etichetta | **due gruppi dichiarati** (`id="fatti-dati"` · `id="fatti-fotmob"`): «Dai nostri risultati · campionato, ricalcolati a ogni build» e «FotMob · fotografia al momento della raccolta» | [42] verifica le due intestazioni |
| 3 | **Record di stagione non verificati**: «ha il maggior numero di porte inviolate del campionato (N)» | 16 voci, nessun controllo | pubblicato **solo se** N = conteggio del campionato dal nostro Parquet **e** massimo di lega (`porta_inviolata_record_ok`) | [42]: 11 voci, tutte verificate, 0 rifiutate in questa build |
| 4 | **La fotografia poteva contraddire i nostri stessi dati** | 4 casi provati (sopra) | impossibile per costruzione: [42] boccia la scheda se una frase della famiglia compare nel gruppo FotMob | [42], test |
| 5 | **`stato.html` con l'etichetta vecchia** («blocco «Curiosità»») | 1 riga | «Fatti FotMob (blocco «Fatti rilevanti»)» + i due contatori nuovi: **188** voci della famiglia non pubblicate da FotMob (ricalcolate), **0** record rifiutati | `site/stato.html` |

**Effetto sulle pagine** (66 schede pre-partita, prima 67): voci **272 → 326** (nostre 258 · FotMob
68), tutte con un'origine dichiarata; **59 schede** hanno entrambi i gruppi, **7** solo il nostro
(prima sarebbero rimaste senza card). Tipi delle voci nostre: gol 128, imbattuta 38, non vince 29,
porta inviolata 25, perse 19, vinte 15, non segna 4.

**Il sospetto «default `n=3` contro "al più cinque" in pagina» è infondato**: il call site passava già
`n=5`; il default della funzione è ora 5, così l'uno non contraddice l'altra.

Peso della card: **4,0%** del testo visibile di una scheda pre-partita (`prematch_sections`), con
+0,9 voci per scheda e due intestazioni di gruppo. Il testo visibile mediano di una scheda
pre-partita passa da **21.084 a 21.680 caratteri** (+2,8%: `parita_schede` prima e dopo, stesse 66
schede) — l'aumento è tutto qui e nella nota di copertura dello «Scontro tattico» (§8.4). Parità
invariata: min 19.697 · mediana 21.680.

---

## 10. Appendice — come sono state prese le misure (per riprodurle)

```bash
.venv/bin/fda build                                            # 441 / 2.364 / 7.496 (~5 min)
.venv/bin/python scripts/verify_site.py --site site --data data/processed   # 0 problemi · 164.729 controlli
#   [22b] radar ricalcolato 66 · [40] meteo 441 · [41] fattori 66 · [42] fatti 258 nostre + 68 FotMob
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site
.venv/bin/python -m scripts.resa_375
.venv/bin/pytest -q && .venv/bin/ruff check .
```

I conteggi per riga, per etichetta e per voce fuori tabella sono letti dalle pagine generate
(`site/partite/*.html`, blocchi `id="lettura"`, `id="fattori"`, `id="scontro"`, `id="fatti"`):
riepiloghi stampati a schermo, mai dati grezzi. I numeri del §9 (79 fatti incoerenti, 181 voci di
famiglia, 4 contraddizioni, 402 righe con 3 per squadra) vengono da uno script di verifica scritto
per l'occasione, che confronta `insights.parquet` con `fixtures.parquet`/`history.parquet`/
`cup_fixtures.parquet`: lo stesso confronto è ora l'invariante [42], che gira a ogni gate. Le soglie sono confrontate con le costanti importate da `fda.site.analysis`
(`FACTOR_*`, `WEATHER_*`), non riscritte a mano nel controllo.

**Cosa non è verificato da qui** (dichiarato, non taciuto): le fonti esterne non sono raggiungibili
dal sandbox e **non sono state interrogate** — niente `collect`, niente sonde, nessun `daily`
manuale; quanto sopra riguarda i dati già raccolti e il sito generato. La resa **visiva** non è
stata vista in un browser: il gate a 375 px è statico (geometria e caratteri), non un giudizio
estetico. I due conteggi «prima» (10,4% di peso della card, 132 righe «Riposo», 6·5·4 righe) vengono
dal censimento di `docs/55`/`docs/56` sulla stessa finestra di 66 schede.
