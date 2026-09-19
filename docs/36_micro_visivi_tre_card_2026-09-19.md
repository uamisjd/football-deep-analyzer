# 36 — P2.3 applicata: le tre card di solo testo hanno il loro micro-visivo (19/09/2026)

> Quarto intervento della coda **P2** di `docs/28` §3, dopo P2.1 (`docs/33`), P2.4 (`docs/34`) e
> P2.2 (`docs/35`). Sessione `arena/01a0b61a`, branch `arena/01a0b61a-football-analyzer`,
> base `7ecbee2`.

---

## 1. Il difetto, misurato

`docs/28` §3 aveva segnalato tre card che dicono quantità disegnabili con la sola prosa. Misura
sulle 60 schede pre-partita (testo visibile, mediana, build `2d3cf27`):

| card | testo visibile | che cosa contiene |
|---|---|---|
| «Dove si colloca questa partita» | 493 | una posizione fra le 345 partite di lega (e il totale di lega) |
| «Quando arriva il primo gol» | 566 | una distribuzione (i primi gol arrivano più nel 2° tempo) |
| «Quando il favorito aveva questa forza» | 755 | cinque righe di due percentuali da confrontare a mente |

Nelle stesse 60 schede, la quota di elementi grafici in queste tre card era **zero**: la posizione
in lega si leggeva come «più alti del 20% delle 345 partite», la distribuzione come una frase, il
backtest come una tabella di numeri. Il precedente in casa erano matrice dei punteggi e
distribuzione dei gol, già fatte bene.

## 2. Che cosa è cambiato

Tre micro-visivi, ognuno dove il dato esisteva già — **nessun numero nuovo inventato**, nessuna
card nuova, nessuna sezione in più:

1. **`#posizione-lega` — la barra della scala di lega.** Riempimento fino alla posizione di questa
   partita, tacca grigia sulla mediana di lega, tacca arancione sulla media, `pin` + valore scritto
   sul punto. L'asse dice in chiaro gli estremi («1,9 · più chiusa» … «più aperta · 4,0») e il
   confronto con la mediana. **La scala è il 2°–98° percentile, non il minimo e il massimo**:
   nelle leghe con una coda lunga (partite da 1,0 e da 4,5 gol attesi) il minimo e il massimo
   schiacciano tutto il resto nel mezzo della barra e la posizione non si legge più.
2. **`#primo-gol` — la distribuzione osservata + la banda del modello.** Due righe sovrapposte
   sullo stesso asse 0–90: sopra i **quarti d'ora dei primi gol davvero arrivati** in questa
   stagione (6 barre, etichette 1–15' … 76–90'), sotto la **banda del modello** per questa partita
   (dal 25° al 75° percentile della distribuzione a due tempi, tacca sulla mediana). Le due righe
   sono fonti diverse — storia contro previsione — e le due didascalie lo dicono. I conteggi
   vengono dagli **stessi eventi** che misurano la quota di 1° tempo già pubblicata in prosa: il
   lettore può rifarli, il verificatore li ricalcola.
3. **`#fascia-storica` — la colonna «previsto → uscito».** Per ognuna delle 5 fasce del backtest:
   barra che parte dalla previsione media del modello, si allunga fino all'uscita osservata e
   mostra **l'intervallo di confidenza al 95%** (Wilson); la tacca verticale è dove il modello si
   aspettava quella fascia. Le due percentuali che prima si confrontavano a mente ora si vedono,
   comprese le fasce dove il modello sbaglia di più (oltre il 75%: previsto 79,4% → uscito 86,2%).

**La regola di sicurezza del primo.** Se in un campionato il 2° e il 98° percentile distassero meno
di **0,2 gol** la barra non viene disegnata (`league_goals_percentile` restituisce `viz = None`): la
card e la prosa restano identiche, sparisce solo il disegno. Nella build di oggi la condizione non
si attiva mai — la barra c'è su **158 pagine su 158** che hanno la card. Il caso limite è coperto da
un test con una lega finta.

## 3. Misura prima/dopo

Due build dello stesso codice sugli stessi dati (`2d3cf27` → codice attuale), stesse **60 schede
pre-partita**, stessa sonda di lettura dell'HTML pubblicato.

| grandezza | prima | dopo |
|---|---|---|
| schede con la barra della scala di lega | 0/60 | **60/60** |
| schede con la distribuzione osservata del primo gol (6 quarti d'ora) | 0/60 | **60/60** |
| schede con la banda del modello del primo gol | 0/60 | **60/60** |
| fasce storiche con la barra «previsto → uscito» | 0 su 5 | **5 su 5** (60/60 schede) |
| testo visibile «Dove si colloca questa partita» (mediana) | 493 | **599** (+106) |
| testo visibile «Quando arriva il primo gol» (mediana) | 566 | **794** (+228) |
| testo visibile «Quando il favorito aveva questa forza» (mediana) | 755 | **773** (+18) |
| schede pre-partita con la stessa struttura | 60/60 | 60/60 |
| voci dell'indice | 12 in tutte | 12 in tutte |
| parità (`scripts/parita_schede.py`) | exit 0 | **exit 0** (23 sezioni, min 17.616 · mediana 19.278) |

I **+352 caratteri** mediani delle tre card sono il prezzo del disegno: didascalie, etichette
dell'asse e le descrizioni `aria-label` che rendono il grafico leggibile anche a chi usa uno screen
reader. Non c'è nulla da aprire e nulla è stato tolto: le tre card erano e restano di sola lettura,
solo che ora la quantità si vede.

**La parità fra le schede** (direttiva utente del 2026-09-19) resta sotto gate: `parita_schede.py`
esce 0 sulle 60 schede pre-partita, con le stesse 23 sezioni e lo stesso indice; il testo visibile
minimo è il **91%** della mediana.

## 4. Come è stato verificato (e che cosa il gate ha corretto)

Il gate `scripts/verify_site.py` è stato **esteso**, non allentato: le tre invarianti che leggono
queste card ora controllano anche il disegno.

| invariante | prima | ora |
|---|---|---|
| **[15]** fasce storiche | i 5 valori in prosa | 5 valori + 4 valori grafici per riga (tolleranza ±0,2 pt) |
| **[16]** percentile di lega | i 4 numeri pubblicati | i 4 numeri + la barra: posizione, tacche, estremi; **se la scala è piatta (< 0,2 gol) pretende che la barra NON ci sia** |
| **[17]** quartili del primo gol | i 3 quartili ricalcolati dal modello | i 3 quartili + le 6 barre osservate ricontate dagli eventi + la banda ricalcolata dai quartili |

Errori trovati e corretti durante la stesura (tutti nella verifica, non nel prodotto): la regex dei
tick senza `title=` (158 «barra assente» inventate), l'ordine degli attesi della banda (in pagina:
inizio 25°, mediana, fine 75°), gli apostrofi che Jinja scrive `&#39;` nei frammenti (serve
`html_unescape`). Nella sonda di anteprima è stato un errore mio a ricordare che i tick sono
*posizioni percentuali*, non minuti: la banda letta come «13%–61%» è in realtà **dal 12' al 55'**
(la barra è su una scala 0–90), ed è il testo che ora sta nell'anteprima.

## 5. Gate

`pytest -q` **447 passed** (+3 in `tests/test_oggi_depth.py`: distribuzione osservata e banda con
quota di 1° tempo misurata; banda che finisce «dopo il 90'»; `viz` assente quando la scala è piatta —
+1 integrazione in `tests/test_site.py` sulle tre card generate) · `ruff check .` pulito ·
`fda build` exit 0 (369 partite / 2.364 fixtures / 7.480 giocatori) ·
`scripts/verify_site.py` **exit 0 — 0 problemi · 104.918 controlli** ([15] 158 · [16] 158 ·
[17] 474) · `scripts/parita_schede.py` **exit 0** · `scripts/audit_match_sections.py` exit 0.

**Non verificato:** resa a schermo dei tre micro-visivi a 375 px (contrasto delle tacche, altezza
delle barre del primo gol, leggibilità dell'asse a sette etichette) → resta **P2.8** di `docs/19`,
come le altre rese visive della sessione.

## 6. Anteprima

`site_preview/` (porta 8000) ha ora **sedici blocchi** prima/dopo con il «prima» che è la build di
`2d3cf27`: i dodici della P1/P2 più i tre nuovi — **11** la barra della scala di lega, **12** la
distribuzione del primo gol con la banda del modello, **13** le fasce storiche con «previsto →
uscito» — e il riquadro **13b** con le quattro cifre lette dalla pagina pubblicata (gara 5868071,
LaLiga). In fondo il bilancio dei nove interventi della sessione.

## 7. Prossimo passo

`docs/28` §3, in ordine di peso: **P2.5** (badge della forma recente nell'hero: la forma compare
ancora in narrativa, «Fatti rilevanti», card squadra e «Clima»), poi **P2.6** (quote dei bookmaker:
voce da decidere, non un difetto) e **P2.8** (misure di resa in browser). Con la parità sotto gate,
ogni intervento successivo va rimisurato con `scripts/parita_schede.py` oltre che con
`scripts/prematch_sections.py`.
