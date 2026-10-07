# 57 — Schede partita, revisione sezione per sezione: «Analisi pre-partita» + «Fattori che spostano la partita» (2026-10-07)

Direttiva dell'utente: **«verifica che le schede delle partite siano fatte bene, revisiona ogni
sezione e controlla che funzioni bene e sia fatta bene, oppure miglioriamo. Inizia con *Analisi
pre-partita* e *Fattori che spostano la partita*»**.

Questo documento copre **la prima coppia**: i due blocchi in testa alla scheda, che un lettore legge
per primi e che insieme pesavano il 13,6% del testo visibile di ogni scheda pre-partita. Per ogni
difetto: **misura prima → correzione → prova**. Le misure sono rifatte sui Parquet già raccolti e
sulla build generata in locale (`fda build`): **nessuna richiesta alle fonti esterne**, nessuna
quota bookmaker. Le sezioni successive della scheda restano da revisionare con lo stesso metodo
(§6).

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

**Residuo dichiarato (decisione dell'utente).** I 19–23 giorni non sono un dato della partita ma
della **finestra di raccolta**: `collect` tiene i dettagli di `[oggi−3, oggi+future]`, quindi
l'ultima gara *raccolta* è il 20/09/2026 e il riposo risulta di tre settimane su tutte le schede.
Il numero pubblicato è quello che il progetto ha raccolto, non necessariamente quello vero. Tre
strade: **(A)** allargare la finestra (più richieste alle fonti), **(B)** dichiarare in pagina che
il riposo è calcolato sulla finestra raccolta, **(C)** lasciare com'è. Nessuna delle tre è stata
applicata: cambiare la finestra di raccolta muove anche i costi verso FotMob.

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
  ASCII. **Residuo, fuori da questa coppia:** `#scontro` (101 occorrenze) e `#scomposizione` (90)
  usano ancora il trattino ASCII — da uniformare quando si revisionano quelle sezioni.
* **Legenda del colore** della colonna «Impatto»: ⓘ nell'intestazione (verde = giova alla squadra
  di casa, rosso = alla trasferta; nessun colore = vantaggio non misurabile).

---

## 7. Aperti, per l'utente

1. **Riposo e finestra di raccolta** (§2): (A) allargare la finestra di `collect`, (B) dichiarare in
   pagina che il riposo è calcolato sulla finestra raccolta, (C) lasciare com'è. *Consigliata B: non
   costa richieste e non lascia un numero che sembra del campionato quando è della raccolta.*
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
5. **Sezioni successive** della scheda da revisionare con lo stesso metodo: «Scontro tattico»
   (compreso il trattino ASCII), «Come arrivano», «I giocatori che decidono», «Panchina e posta in
   gioco», «Mercato: arrivi e partenze», «Vita del club», «Previsione del modello ensemble»,
   «Precedenti», «Verifica approfondita».

---

## 8. Appendice — come sono state prese le misure (per riprodurle)

```bash
.venv/bin/fda build                                            # 441 / 2.364 / 7.496 (~5 min)
.venv/bin/python scripts/verify_site.py --site site --data data/processed   # [40] 441 · [41] 66
.venv/bin/python scripts/parita_schede.py site --data data/processed
.venv/bin/python -m scripts.prematch_sections site
.venv/bin/python -m scripts.resa_375
.venv/bin/pytest -q && .venv/bin/ruff check .
```

I conteggi per riga, per etichetta e per voce fuori tabella sono letti dalle pagine generate
(`site/partite/*.html`, blocchi `id="lettura"` e `id="fattori"`): riepiloghi stampati a schermo,
mai dati grezzi. Le soglie sono confrontate con le costanti importate da `fda.site.analysis`
(`FACTOR_*`, `WEATHER_*`), non riscritte a mano nel controllo.

**Cosa non è verificato da qui** (dichiarato, non taciuto): le fonti esterne non sono raggiungibili
dal sandbox e **non sono state interrogate** — niente `collect`, niente sonde, nessun `daily`
manuale; quanto sopra riguarda i dati già raccolti e il sito generato. La resa **visiva** non è
stata vista in un browser: il gate a 375 px è statico (geometria e caratteri), non un giudizio
estetico. I due conteggi «prima» (10,4% di peso della card, 132 righe «Riposo», 6·5·4 righe) vengono
dal censimento di `docs/55`/`docs/56` sulla stessa finestra di 66 schede.
