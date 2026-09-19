# 43 — Audit delle schede giocatore: il valore di mercato arrotondato al milione (2026-09-19)

**Scelta dell'area (decisione dell'utente, `docs/42` §7.3).** Fra le tre candidate — schede
giocatore, *Accuratezza*, *Stagione* — è stata scelta quella **più grande e mai auditata**:
`giocatori/` raccoglie **3.757 pagine** (3.749 schede + 7 tabelloni di lega + hub) e
**95,7 MB dei 126,6 MB** di HTML del sito (**76%**). Nessun documento del progetto la passava al
setaccio dopo `docs/07` (fase 3, progetto) e `docs/23` §4 (P1.14, rate stabilizzate).

**Esito:** un solo difetto sostanziale, misurato e con la patch pronta (§3-§5); tutto il resto
dell'area è risultato sano o **onestamente** degradato (§2, §6).

---

## 1. Metodo

Sito ricostruito dai Parquet versionati a `HEAD` (`88ee2ae`, run delle 18:11Z) con `fda build`
(375 schede · 2.364 partite · **7.498** «giocatori» — numero doppio, vedi §6.1). Poi: censimento
di **tutte** le 3.749 schede (nessun campione) con espressioni regolari sul HTML pubblicato, e
confronto con i dati grezzi (`lineup.parquet`, `player_stats.parquet`). Nessuna verifica «dal
vivo»: il sito pubblicato non è raggiungibile dal sandbox (regola B6).

---

## 2. Copertura dell'area: dove arriva e dove si ferma (tutto misurato su 3.749 schede)

| contenuto | schede | quota | nota |
|---|---|---|---|
| **Radar di ruolo** (6 assi, 6 percentili) | **2.128** | 57% | sempre 6 assi e 6 valori: media, min e max = **6,00**; **0** percentili anomali (`None°`, `nan°`) |
| Segnaposto «Percentili non ancora calcolabili: servono almeno 90 minuti…» | **743** | 20% | motivo dichiarato, nessuna stima inventata |
| «Non ancora sceso in campo nelle partite raccolte finora…» | **878** | 23% | giocatori a 0 minuti: la scheda spiega perché è vuota |

**Parità fra le 7 leghe (direttiva F).** I sette tabelloni hanno le **stesse 10 colonne**
(Giocatore, Squadra, Ruolo, Età, Voto, Min, G, xG, A, xA) e le uniche celle vuote sono in «Voto»
(**18-26** per lega, ~5% di 363-457 righe). Radar per lega: **256** (GER1) … **372** (ESP1),
proporzionale alle rose. Marcatori della stima stabilizzata (◇/◎) su **2.871** schede = esattamente
i **2.871** giocatori «allineati» dei tabelloni (440+410+457+363+379+402+420): nessuno con minuti
pubblica una rata grezza senza la sua stima.

**Soglie coerenti in ogni punto pubblicato.** `MIN_MINUTES = 90` e `MIN_PEERS = 8` compaiono
identici nel radar, nel segnaposto, nella nota a piè di pagina (`giocatore.html:127`) e nell'hub
(`build.py:563`): nessun numero contraddice un altro.

---

## 3. Il difetto: il valore di mercato è arrotondato al milione intero

`src/fda/site/templates/giocatore.html:11`

```jinja
€{{ (p.market_value_eur / 1000000)|it_num }}M
```

`it_num` (`fmt.it_thousands`) formatta **senza decimali**: un giocatore da **73.728 €** diventa
«**€0M**». Non è un caso limite: è la regola.

| misura | valore |
|---|---|
| schede che pubblicano «**€0M**» | **845 su 3.749 (22,5%)** |
| righe di `lineup.parquet` con valore | 14.944 |
| …uguali a **0** (zero vero) | **0** — quindi *ogni* «€0M» è un artefatto di arrotondamento |
| …comprese fra 0 e 500.000 € | **1.589** (minimo **73.728 €**) |
| errore relativo dell'arrotondamento | mediana **7,1%** · **>10% sul 43%** dei giocatori · massimo **100%** |

**Altri due punti con lo stesso arrotondamento** (stessa classe, impatto minore):

- `match.html:389` — «€**N**M titolari» (somma Transfermarkt dei titolari): **735** occorrenze,
  **0** a zero (le somme sono grandi) ma errore fino a ±5% su ogni valore;
- `analysis.py:1465` — «≈ **N** M€ di mercato ai box» (valore degli indisponibili): **15**
  occorrenze oggi, nessuna a zero; con un solo indisponibile sotto i 500 mila € la frase
  diventerebbe «≈ 0 M€».

**Il formattatore corretto esiste già** ed è usato altrove: `MatchAnalysis.fee_it`
(`docs/24` §4, registrato come filtro Jinja `fee_it` in `build.py:189`): 12.500.000 → «**12,5 M€**»,
125.000 → «**125 k€**», 500 → «500 €», testo non riconosciuto → pubblicato com'è. Il sito quindi
formatta gli importi in due modi diversi e quello sbagliato è su 845 pagine.

---

## 4. Impatto

Non è un dato inventato (la direttiva «presente / atteso / mancante» è rispettata: chi non ha
valore mostra «—»), ma è un **numero falso**: il lettore che apre la scheda di un giocatore da
74 mila € legge «Valore di mercato **€0M**», cioè un'informazione che contraddice la fonte del
100%. La paletta B1 del progetto («ogni numero mostrato è verificabile e misurato») è violata
proprio nella sezione anagrafica, la prima che si legge.

---

## 5. Patch pronta

1. **`giocatore.html:11`** — usare il filtro già esistente:

   ```jinja
   <td class="r">{% if p.market_value_eur %}{{ p.market_value_eur|fee_it }}{% else %}—{% endif %}</td>
   ```

2. **`match.html:389`** — `€{{ (c[side ~ '_value']/1e6)|it_num }}M titolari` →
   `{{ c[side ~ '_value']|fee_it }} titolari` (guardia `{% if %}` invariata).
3. **`analysis.py:1465`** — `f"≈ {round(value / 1_000_000)} M€ di mercato ai box"` →
   `f"≈ {MatchAnalysis.fee_it(value)} di mercato ai box"` (`fee_it` porta già l'unità).
4. **Test** (in `tests/test_players.py`, o file nuovo): una scheda costruita con
   `market_value_eur = 73_728` pubblica «**74 k€**» e **non** «€0M»; 2.250.000 → «2,3 M€» (o
   «2,2 M€»: il valore atteso va preso da `fee_it`, non scritto a mano); `None` → «—».
5. **Invariante `verify_site`** (nuova, es. `[38]`): nessuna pagina del sito pubblica «**€0M**» o
   «**≈ 0 M€**». È un controllo di pubblicazione, non matematico: rilegge l'HTML come fa il
   lettore, e protegge la correzione da regressione.

Verifica attesa dopo la patch: «€0M» **0** occorrenze (oggi 845), `pytest` verde, `verify_site`
0 problemi con `[38]` attiva, **nessun'altra parola cambiata** nelle schede (il filtro tocca solo
la cella del valore).

---

## 6. Cosa **non** è un difetto (verificato e chiuso, non intervenire)

1. **«7.498 giocatori»** nel riepilogo di `fda build` è un **doppio conteggio** (già notato in
   `docs/19` §2.10): `build_players()` somma le righe dei sette tabelloni (3.749) **e** le schede
   scritte (3.749). Il numero **non è pubblicato sul sito** (grep di «7.498»/`7498` su tutte le
   pagine → 0 occorrenze): vive solo nel log del comando e nei documenti. Da correggere nel
   riepilogo (`n` = schede scritte), non nelle pagine.
2. **878 schede senza statistiche** (23%): sono giocatori a 0 minuti e la scheda lo dichiara
   («Non ancora sceso in campo nelle partite raccolte finora…»). Segnaposto onesto, non un buco.
3. **743 schede senza percentili** (20%): sotto i 90 minuti o senza pari-ruolo sufficienti
   (`MIN_PEERS = 8`), con il motivo scritto.
4. **241 schede con «ruolo n.d.»** (6%): **1 sola** ha minuti > 0 (230′, messaggio generico sui
   minuti invece che sul ruolo): caso trascurabile, non una classe di difetto.
5. **Celle «Voto» vuote** nei tabelloni (18-26 per lega, ~5%): la fonte non assegna un voto a
   chi ha giocato pochi minuti; il trattino è corretto.

---

## 7. Prossimo passo

Applicare la patch del §5 in un turno dedicato (4 righe di template, 1 di `analysis.py`, 1 test,
1 invariante), con i gate pieni: `pytest` verde, `ruff` pulito, `fda build` + `verify_site`
0 problemi e «€0M» sparito da tutte le 3.757 pagine. Restano fuori da questo giro: *Accuratezza* e
*Stagione*, le altre due aree candidate rimaste indietro.

---

## 8. Correzione applicata (stesso giorno, giro 54)

Patch del §5 applicata in tre punti: `giocatore.html:11` e `match.html:389` usano il filtro
`fee_it` già registrato in `build.py:189`; `analysis.py:1465` chiama `self.fee_it(value)` al posto
di `round(value / 1_000_000)`.

**Prove di morso (entrambe eseguite, come richiede la regola B8).**

| prova | esito |
|---|---|
| template riportato alla forma sbagliata | **2 test falliscono**: `test_scheda_giocatore_valore_di_mercato_in_k_euro` (render: la pagina contiene «€0M») e `test_nessun_template_arrotonda_a_milioni_interi` (guardia) |
| `verify_site` sul sito **pre-correzione** | **exit 1** — `[38]` segnala **845** pagine con «importo pubblicato come «€0M»» |

**Misure dopo la correzione** (sito ricostruito dagli stessi Parquet, nessun dato cambiato):

| misura | prima | dopo |
|---|---|---|
| occorrenze di «€0M» nell'intero sito | **845** | **0** |
| scheda del giocatore con valore 603.000 € | «Valore di mercato **€0M**» | «Valore di mercato **603 k€**» |
| «€216M titolari» nella scheda partita | «€216M titolari» | «**216,4 M€** titolari» |
| parole cambiate nelle schede (a parte il valore) | — | **nessuna**: l'unica altra riga diversa è il timestamp di generazione |

**Gate:** `pytest -q` **478 passed** (475 + 3 nuovi: 2 in `tests/test_players.py`, 1 in
`tests/test_mercato.py`); `ruff check .` pulito; `fda build` exit 0 (375/2.364/7.498);
`verify_site` **0 problemi · 154.727 controlli** (150.587 + 4.140 della nuova `[38]`);
`parita_schede` exit 0 («nessuna differenza»); `resa_375` **23.674 misure · 0 problemi**.

**Osservazione da registrare.** Eseguendo `verify_site` su un sito costruito **3 ore prima** sono
comparsi **12** problemi di tipo «riga» (riconciliazione di righe pubblicate col dato), **spariti
dopo il rebuild** con gli stessi dati: il verificatore non è del tutto indipendente dal tempo.
In CI non morde (il sito è costruito e verificato nello stesso run); va ricordato quando si
verifica a mano una build non appena generata.
