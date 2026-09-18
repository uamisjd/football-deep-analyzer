# 28 — La scheda delle partite da giocare: sezioni, miglioramenti, ridondanze (18/09/2026)

> Direttiva dell'utente: *«sulla scheda delle partite che devono giocare fammi un elenco di tutte le
> sezioni che ci sono dentro, come si possono migliorare, e poi controlla che non ci siano cose
> troppo ridondanti e ripetute»*.
>
> **Perimetro:** le **66 schede pre-partita** su 375 pubblicate — le gare che devono ancora giocarsi
> (`c.status != 'finished'` in `match.html`; nelle pagine: hero con «Analisi pre-partita»). Le 309
> schede post-partita hanno un'altra struttura (`#postpartita`, cronaca, cartina tiri…) e restano
> fuori da questo censimento.
>
> **Tutto è misurato, non impressionistico.** Base: build locale del 2026-09-18 20:01
> (`fda build` exit 0 · 375 partite / 2.364 fixtures / 7.480 giocatori), cioè le stesse pagine che
> pubblica la CI su questi dati. Ogni numero si riproduce con
> **`.venv/bin/python -m scripts.prematch_sections`** (script nuovo, sola libreria standard:
> legge l'HTML generato, non i template — così misura ciò che vede il lettore).

---

## 0. Metodo e limiti

> **Aggiornamento del 2026-09-18 (dopo P1.1, `docs/29`).** Il censimento distingue ora **testo
> visibile senza aprire le tendine** e **testo dietro una tendina chiusa**: la colonna «% testo»
> delle tabelle sotto misurava il DOM, e una parte del testo (P1.1, poi P1.4) non sta più nel primo
> schermo. Dove i due numeri differiscono è indicato nel documento; la misura aggiornata si legge
> con `.venv/bin/python -m scripts.prematch_sections` (due colonne: «% visibile», «% tendina»).

| passo | comando | esito |
|---|---|---|
| build | `.venv/bin/fda build` | exit 0 · 375 schede (66 pre, 309 post) · 3m30s |
| censimento | `.venv/bin/python -m scripts.prematch_sections` | sezioni, pesi, ridondanze (sotto) |
| lint | `.venv/bin/ruff check scripts/prematch_sections.py` | pulito |

Il parser individua come **card** ogni elemento di flusso (`div/section/details`) che contiene un
`h2` e non ne contiene altri annidati: così una griglia (`#squadre`, `#contesto`) non viene contata
due volte, e ogni blocco titolato appare una volta sola.

**Limiti dichiarati.** Dal sandbox non c'è browser: resa visiva, tempi di rendering e comportamento
a 375 px **non** sono misurati qui (restano il punto aperto P2.8/Lighthouse già noto). I giudizi di
questa istruttoria sono sui contenuti e sulla struttura, non sul pixel.

---

## 1. Elenco completo delle sezioni della scheda pre-partita

La scheda è composta da: **hero** (`#sintesi`) + **navigazione** (`match-jump`) + **18 blocchi
titolati** + le **2 card delle squadre** + chiusura con nota di generazione e fonti. Presenza e peso
(quota di testo visibile, mediana sulle 66 schede):

| # | titolo (h2) | id | che cosa contiene | schede | % testo | caratteri |
|---|---|---|---|---|---|---|
| 1 | *hero* «Analisi pre-partita» | `#sintesi` | stato, data/ora italiana, stadio, «vs», avvisi (rinvio, prior di lega), esito più probabile + margine in punti, 1X2, λ casa+trasferta e totale, Over 2,5, entrambe a segno, segnale DC vs Elo, riga xG/gara + PPDA | 66/66 | 2,2%* | ~500 |
| 2 | *nav* «Sintesi · Previsione · Dati e contesto · Squadre» | `match-jump` | 4 link interni | 66/66 | — | — |
| 3 | Analisi pre-partita | `#lettura` | narrativa automatica (4–12 frasi: quadro, cosa pesa, freni) | 66/66 | 3,3 | 737 |
| 4 | Previsione del modello ensemble | `#previsione` | barra 1X2, gol attesi per squadra, Over 1,5/2,5/3,5, entrambe a segno, doppia chance, porta inviolata, pesi DC/Elo, n gare di addestramento, ora del calcolo | 66/66 | 1,8 | 403 |
| 5 | Risultati esatti più probabili | dentro `#previsione` | 6 punteggi con probabilità, copertura, Elo e forza DC | 66/66 | 1,8 | 404 |
| 6 | Come nasce questa probabilità | `#scomposizione` | catena dei passi (modello sui gol → Elo → calibrazione) con Δ in punti | 66/66 | 4,2 | 936 |
| 7 | Quando il favorito aveva questa forza | `#fascia-storica` | backtest per fascia di favorito, frequenza osservata, IC 95%, riga della partita | 66/66 | 3,4 | 755 |
| 8 | Dove si colloca questa partita | `#posizione-lega` | percentile dei gol attesi totali nella propria lega | 66/66 | 2,2 | 493 |
| 9 | Quando arriva il primo gol | `#primo-gol` | ritmo a due tempi, quartili del primo gol, 0-0 al riposo, zero gol | 66/66 | 2,5 | 566 |
| 10 | Scontro tattico | `#scontro` | tabella stile: λ, attacco/difesa DC, xG/xGA di stagione, quote azione manovrata/palle inattive, PPDA, profondità; graduatorie e duello chiave | 66/66 | 6,3 | 1.404 |
| 11 | Fatti rilevanti | — | fino a 5 insight FotMob tradotti (streak, testa-a-testa) | 66/66 | 1,7 | 377 |
| 12 | Come arrivano | — | ultime gare con xG/xGA, punti vs xPTS, tendenza, xG casa/trasferta, PPDA, fonte | 66/66 | 5,3 | 1.150 |
| 13 | I giocatori che decidono | — | (xG+xA)/90 con stime stabilizzate, media voto, stato (titolare/assente) | 66/66 | 8,4 | 1.917 |
| 14 | *card squadra* (una per lato) | dentro `#squadre` | forma V/N/P con risultati, 4 riquadri (xG creati, xG concessi, xPTS vs punti, pressing·riposo), indisponibili con impatto, formazione probabile + valore rosa | 132 card | 4,5 ciascuna | ~1.018 |
| 15 | Confronto di stagione | `#confronto` | posizione, punti, differenza reti, ecc. con barre | 66/66 | 1,8 | 411 |
| 16 | Panchina e posta in gioco | `#panchina` | allenatore ed età, rendimento, classifica virtuale, probabilità titolo/UCL/salvezza (Monte Carlo) | 66/66 | 7,9 | 1.786 |
| 17 | Clima del club | `#clima` | segnali misurati (crisi, imbattute, infermeria pesante, riposo corto…) | 65/66 | 3,3 | 751 |
| 18 | Mercato: arrivi e partenze | `#mercato` | finestra in corso, arrivi/partenze con importi pubblicati, «già in campo» | 66/66 | 9,9 | 2.250 |
| 19 | Vita del club | `#notizie` | notizie in italiano filtrate per rilevanza + imbuto dei titoli esaminati | 66/66 | **13,6** | 3.054 |
| 20 | Contesto | — | arbitro, meteo, precedenti (grafico a ciambella + ultimi incontri + statistiche) | 66/66 | 4,3 | 952 |
| 21 | Verifica approfondita: risultati esatti e distribuzione gol | `#verifica` | `<details>` **aperto**: matrice dei punteggi 0-5 e distribuzione dei gol (istogramma + dotplot) | 66/66 | 8,4 | 1.883 |

\* la quota dell'hero è calcolata fuori dai blocchi `h2`, come percentuale del testo dei blocchi.

**Segnali di contesto misurati** (schede su cui compaiono): «Vita del club» **senza nessuna notizia
pubblicabile 42/66**; avviso «PPDA incompleto» 22/66; avviso «due fornitori xG diversi» 4/66;
«nessun indisponibile segnalato» 8/66; formazione ufficiale **0/66** (a quest'ora la distinta
pubblicata è sempre «probabile»).

---

## 2. Come si possono migliorare

Le proposte sono ordinate per impatto misurato. **Non** ricomprendono ciò che `docs/20` ha già
applicato il 2026-09-15 (catena a 4 passi, fonte per riga, margine = differenza degli interi,
«coprono X partite su 100», formato unico xPTS, forma in tutte le leghe…): quello è già dentro.

### P1.1 — Il peso della scheda è sulle notizie, non sul calcio ✅ APPLICATA il 2026-09-18

**Osservato.** Le tre card «di contorno» pesano più di tutta l'analisi numerica messa insieme:
Vita del club **13,6%** + Mercato **9,9%** + Panchina e posta in gioco **7,9%** = **31,4%** del testo
visibile, contro Previsione + Risultati esatti **3,6%**, Scomposizione **4,2%**, Scontro tattico
**6,3%**.

**Misura.** Su **42 schede su 66** la card «Vita del club» non ha *nessuna* notizia pubblicabile per
nessuna delle due squadre: resta una card da 3.054 caratteri mediani in cui il **99%** del testo è
prosa metodologica (misura: caratteri nei `<p>` su caratteri totali della card). Il paradosso: la
sezione più grande della pagina dice, in media, che non c'è niente da dire.

**Impatto.** Chi apre «le partite che devono giocare» legge 22.500 caratteri, di cui oltre un terzo
racconta finestre di mercato, notizie assenti e metodologia; il modello — la ragione del sito — sta
in una fetta da un decimo.

**Proposta.** (a) Quando entrambe le squadre non hanno titoli pubblicabili, ridurre la card a una
riga («Nessun titolo pubblicabile negli ultimi N giorni su X e Y») con la spiegazione lunga dentro un
`<details>`; (b) spostare le note metodologiche ricorrenti in un unico blocco richiudibile
(«Come leggiamo i dati», in coda o in `info.html`) e lasciare nelle card solo il dato con il suo
tooltip. Effetto atteso misurato a valle, non stimato a priori: -2.500 caratteri sulle 42 schede
senza notizie, -30/40% del testo delle card di contorno sulle altre.

**Esito (2026-09-18, `docs/29`).** (a) fatta: riga unica + `<details>` «Che cosa è stato esaminato,
e con quali criteri». Misura prima/dopo sulle due build (stesso codice, stesso dati): card visibile
**3.030 → 829 caratteri** (mediana sulle 42 schede), −73%; testo visibile dell'intera scheda
22.520 → **20.723** (−8,0%); DOM della card 3.030 → 3.354 (la riga si aggiunge, nulla si toglie).
(b) fatta **solo per il caso vuoto** (la nota metodologica è dentro la tendina): nelle 24 schede con
notizie pubblicate resta visibile, ed è il seguito se la misura lo chiederà.

### P1.2 — Il xG e il PPDA sono detti quattro volte ✅ APPLICATA il 2026-09-18

**Osservato.** Lo stesso numero compare in: riga dell'hero, «Scontro tattico», «Come arrivano» e
riquadro della card squadra (per squadra). Idem il PPDA (hero, «Scontro tattico», «Come arrivano»,
riquadro «Pressing · riposo»).

**Misura.** Il valore dell'hero (xG/gara e PPDA) ricompare in **mediana 3 card** diverse dalla sua
(distribuzione sulle 154 misure: 3 card in 97 casi, 4 in 48, 5 in 7, 6 in 2).

**Impatto.** Il lettore non sa quale sia la cifra «vera»; due fonti xG diverse nella stessa pagina
(Understat e FotMob, già segnalate con avviso su 4 schede) rendono il rischio concreto.

**Proposta.** Un solo posto per tipo di dato: l'hero tiene esito, λ, Over 2,5 e 「entrambe a segno»
(niente xG/PPDA); «Scontro tattico» resta l'unico confronto di stile per gara; la card squadra tiene
i valori di stagione; «Come arrivano» perde la riga di sintesi e tiene la serie gara per gara con la
tendenza. Ogni altro posto cita il numero con un rimando (`→ Scontro tattico`), come già fa la
narrativa per la palla inattiva.

**Esito (2026-09-18, `docs/30`).** Fatta come proposto. Misura sulle stesse 66 schede, due build:
il dato di stagione si ripete in **mediana 1 altro riquadro** (prima 3), le occorrenze passano da
1.039 a 489; la riga xG/PPDA dell'hero e la sintesi di «Come arrivano» spariscono da **66 schede su
66** (il PPDA da quella card in 48 su 66); calo **appaiato** di **357 caratteri visibili per scheda**
(188–376, tutte e 66). Lo strumento conta ora i valori canonici della card squadra (hero incluso nel
conteggio), così il confronto prima/dopo usa la stessa definizione.

### P1.3 — La navigazione promette 4 sezioni, la pagina ne ha 21 ✅ APPLICATA il 2026-09-18

**Osservato.** `match-jump` ha quattro link: «Sintesi · Previsione · Dati e contesto · Squadre». Le
etichette non corrispondono ai titoli: «Dati e contesto» punta a `#contesto`, che comincia con
«Confronto di stagione»; «Squadre» salta a metà pagina. Mancano del tutto le ancore verso «Scontro
tattico», «Vita del club», «Verifica approfondita», «Come arrivano», «I giocatori che decidono».

**Misura.** 4 link per 18 blocchi titolati; 6 card pesanti (Vita del club, Mercato, Verifica,
Panchina, Scontro tattico, I giocatori) non hanno un'ancora in nav.

**Proposta.** Mini-indice (anche sticky su mobile) con i titoli reali, o `match-jump` esteso ai 6
blocchi più pesanti; aggiungere `id` alle card oggi senza («Fatti rilevanti», «Come arrivano»,
«I giocatori che decidono», «Contesto»).

**Esito (2026-09-18, `docs/32`).** Fatta estendendo la barra ai titoli reali (non solo ai 6 più
pesanti): pre-partita **4 → 11 voci**, tutte che dicono l'inizio del titolo della sezione che aprono
(prima **66 voci corrette su 264**, una per scheda); post-partita 3 → 7 (prima 0 su 36). Ancore
aggiunte a «Fatti rilevanti», «Come arrivano», «I giocatori che decidono», «Contesto»,
«Statistiche», «Cronaca essenziale»; titolo al gruppo delle due squadre (`Le due squadre`) e al
gruppo delle card del club, che smette di chiamarsi `#contesto` (ora `#club`) perché
l'id «contesto» va alla card che ha quel nome — così «→ precedenti» atterra sui precedenti.
**Le sei card più pesanti passano da 0 su 6 a 6 su 6 raggiungibili**; le card con un'ancora in
indice, per scheda, da 1 a 9 su 20. Nuova invariante **[33]** in `verify_site` (2.987 voci
verificate, in entrambe le direzioni: voce → titolo e sezione presente → voce presente): i controlli
salgono da 97.903 a **100.890**. Costo: **+97 caratteri** di testo visibile per scheda (l'indice è
testo nuovo). Il censimento delle card non cambia.

### P1.4 — «Verifica approfondita» aperta di default: 8,4% del testo ✅ APPLICATA il 2026-09-18

**Osservato.** Il `<details open>` contiene matrice e distribuzione dei gol, dichiarati «per chi
vuole controllare i numeri», ed è sempre espanso: è il **blocco dati più pesante** dopo le card di
contorno.

**Proposta.** `<details>` chiuso alla apertura, con il summary che porta i due numeri di testa
(«moda X gol · mediana Y») così il lettore sa se aprirlo. Il contenuto resta nel DOM: `verify_site`
continua a leggerlo, Google pure.

**Esito (2026-09-18, `docs/31`).** Fatta come proposto, più una cosa che il piano non diceva: lo
script in `base.html` che **riapriva** la tendina sopra i 760 px è stato sostituito — adesso apre da
sola la tendina che contiene il bersaglio di un'ancora (il link «matrice completa ↓» atterrava su una
riga chiusa). Misura sulle stesse 66 schede, due build: la card passa da **1.886 a 119 caratteri
visibili** (9,2% → 0,6% della pagina, con 7,9% in tendina), la scheda intera perde **1.767 caratteri
visibili** in mediana (1.758–1.782, tutte e 66); il testo visibile mediano per scheda scende da
20.577 a **18.807**, e `verify_site` resta a **97.903 controlli, 0 problemi** perché il contenuto è
nella pagina, solo chiuso. Il segno ▸/▾ è ora una regola CSS sola con la tendina di P1.1.

*Sul titolo:* dice 8,4%, la ri-misura di oggi sulla stessa card dà 9,2%. Non è un errore: la card
è la stessa, è cambiato il **denominatore** — dopo P1.1 e P1.2 la pagina è più corta, quindi la
stessa quantità di testo pesa di più in percentuale. Le cifre in caratteri non cambiano.

### P2.1 — Le stesse spiegazioni ripetute quattro-sei volte ✅ APPLICATA il 2026-09-18

**Misura** (occorrenze mediane per scheda): «stabilizzata / stima stabilizzata» **4**, «partite su
100» **6**, «Understat» **8**, «FotMob» **8** (fino a 14), «football-data.co.uk» 1, «non media delle
ultime 3» 1.

**Verdetto.** Le sorgenti citate 8-14 volte sono **una decisione**, non un difetto (docs/20 §3: ogni
riga dichiara la sua fonte). Il rumore è la spiegazione della stima stabilizzata ripetuta in ogni
tabella: va spiegata **una volta** (legenda nel primo punto d'uso) e poi richiamata con ◎/◇ nel
tooltip.

**Esito (2026-09-18, `docs/33`).** Fatta come proposto: la legenda dei due marcatori sta **una volta
sola**, nella testata di «I giocatori che decidono» (primo punto d'uso), le card squadra tengono solo
il dato («Soglia di minutaggio: N minuti · M giocatori in classifica») e ogni valore stabilizzato
porta il tooltip del **caso specifico** (media dei pari, peso k, numerosità); nell'infermeria il
totale prende il marcatore ◎ invece della parentesi «(stima stabilizzata)». Misura sulle stesse 66
schede, due build: «stabilizzat» **4 → 1** per scheda (max 4 → 1), testo visibile **−111 caratteri**
in mediana appaiata (73–111, tutte e 66). Le sorgenti citate 8-14 volte **non** sono state toccate:
restano una decisione (docs/20 §3). Il gate **[32]** ha corretto la prima stesura della legenda
(`<b>◇</b>` isolato = «cella senza numero»): riscritta in prosa.

### P2.2 — Le assenze sono raccontate in quattro modi

**Misura.** 653 nomi di indisponibili misurati; ciascuno compare in **mediana 2 card** (max 15). Le
quattro sedi: narrativa (riga «Assenze…»), tabella «Indisponibili» con impatto, stato dentro «I
giocatori che decidono», segnale «infermeria pesante» in «Clima del club». Nei 4 casi su 66 in cui il
migliore della lista è indisponibile c'è anche un avviso dedicato.

**Proposta.** Tabella = fonte unica. La narrativa cita «vedi Infermeria ↓» senza ripetere i nomi;
«I giocatori che decidono» lascia il solo marcatore di stato senza ripetere il motivo; «Clima» tiene
la soglia aggregata (4 assenti / 2 titolari / 0,5 xG+xA in meno) senza elencare.

### P2.3 — Card di solo testo senza un grafico

**Misura** (caratteri mediani, tutte prosa): «Dove si colloca questa partita» 493, «Quando arriva il
primo gol» 566, «Quando il favorito aveva questa forza» 755, «Analisi pre-partita» 737.

**Proposta.** Un micro-visivo per card dove il dato esiste già: barra del percentile (posizione in
lega), distribuzione del primo gol (quartili), sparkline delle fasce del backtest. Il precedente in
casa sono matrice e distribuzione dei gol, già fatte bene.

### P2.4 — «Contesto» impacchetta tre cose diverse ✅ APPLICATA il 2026-09-19

Arbitro + meteo + precedenti (con grafico a ciambella e ultimi incontri) in una card da 4,3%: la
parte precedenti è oltre metà del blocco. Proposta: separare «Arbitro e meteo» (due righe) da
«Precedenti» (grafico + incontri + statistiche).

**Esito (2026-09-19, `docs/34`).** Fatta come proposto: `#arbitro-meteo` «Arbitro e meteo» (due righe) e
`#precedenti` «Precedenti» (bilancio, grafico, ultimi incontri, frequenze), ognuna con la voce
d'indice che ne dice il titolo (11 → 12 voci in una scheda pre-partita). La riga della tabella non
ripete più il titolo: «Precedenti (15)» è diventata **«Bilancio (15)»**, e l'invariante [5] di
`verify_site` legge da lì il numero dei casi che ricalcola dall'archivio. Il link «→ precedenti»
punta a una card che si chiama così. Misura appaiata su 60 schede pre-partita: card 1 → 2,
«Contesto» **2 → 0** occorrenze per pagina, etichette che ripetevano il titolo 58 → 0, distanza
dalla voce d'indice ai precedenti 171 → **0** caratteri, costo **+15 caratteri** visibili (il titolo
in più). La misura ha corretto la stima di questo documento: i precedenti erano l'**83%** del blocco,
non «oltre metà».

### P2.5 — Micro-badge forma nell'hero (già proposto in `docs/17` §2, mai applicato)

La forma compare in narrativa, «Fatti rilevanti», card squadra e «Clima»: portarla anche nell'hero
(`Milan [V V N N] 7pt`) riduce la ripetizione sotto, come già indicato il 14/09.

### P2.6 — Le quote dei bookmaker non ci sono (voce da decidere, non un difetto)

Verificato: **0** riferimenti a quote di mercato nelle pagine partita. `docs/03` le descrive come
parte del sito (consenso, probabilità implicite, confronto col modello); `info.html` le dichiara
«non prioritarie, l'utente non le richiede». È una decisione aperta, la si cita qui perché è
l'unica sezione «promessa» che manca alla scheda.

---

## 3. Ridondanze e ripetizioni: che cosa c'è davvero

Mappa dei dati ripetuti (sedi strutturali, dalla struttura della pagina; conteggi dallo script):

| dato | dove compare | misura | verdetto |
|---|---|---|---|
| xG/gara di stagione | hero · Scontro tattico · Come arrivano · card squadra | valore dell'hero in **mediana 3 card** | **da ridurre** (P1.2) |
| PPDA | hero · Scontro tattico · Come arrivano · riquadro «Pressing · riposo» | idem (≤6 card) | **da ridurre** (P1.2) |
| λ per squadra e totali | hero · Previsione · Scontro tattico (+ totali in Posizione lega, Primo gol, Quanti gol) | 3 sedi per squadra | accettabile se i richiami sono espliciti: oggi non lo sono |
| forma recente | narrativa · Fatti rilevanti · card squadra · Clima | 3-4 sedi | da ridurre con il badge in hero (P2.5) |
| indisponibili (nome) | narrativa · tabella Indisponibili · giocatori che decidono · Clima | 653 nomi, mediana 2 card | da ridurre (P2.2) |
| punti vs xPTS | Come arrivano · riquadro card squadra · Clima | 3 sedi | accettabile (numeri diversi: serie, sintesi, soglia) |
| 1X2 completo | hero · Previsione (barra, tabella, doppia chance) · Scomposizione · matrice | 3-4 sedi | accettabile: sono letture diverse, ma vanno legate da un rimando |
| Over 2,5 · entrambe a segno | hero · Previsione | 2 sedi | ok |
| precedenti (h2h) | Fatti rilevanti (insight FotMob) · Contesto (grafico + tabella) | 2 sedi | ok se collegati da un link |
| origine/qualità dei dati | ogni card con una nota metodologica | «Vita del club» 99% prosa con 0 notizie | **da ridurre** (P1.1) |

**Non-ridondanze verificate (ipotesi smentite dai dati):** il banner «prior di lega» compare su
**0/66** schede e «λ limitate» su **2/66**: i due avvisi temuti come ripetuti quasi non si attivano
in questo momento della stagione. Anche «non media delle ultime 3» è ormai **1 sola volta** per
scheda (docs/20 §6 ha funzionato).

**Ripetizioni necessarie, da non toccare:** ogni riga dello «Scontro tattico» dichiara la propria
fonte nel tooltip (Understat/FotMob/modello) — è il presidio anti-mescolamento di `docs/20` §3; le
etichette V/N/P; i tooltip di accessibilità su barre e matrici (invarianti di `verify_site.py`).

---

## 4. Priorità consigliate (ordine di lavoro)

| ordine | intervento | misura attesa |
|---|---|---|
| 1 | P1.1 empty-state di «Vita del club» + note metodologiche richiudibili | −2.500 car. su 42/66 schede |
| 2 | P1.2 hero senza xG/PPDA, un solo posto per dato | mediana da 3 card a 1-2 |
| 3 | P1.4 «Verifica approfondita» chiusa, summary con i due numeri | 1.883 car. fuori dal primo schermo |
| 4 | P1.3 nav con ancore reali | 6 blocchi pesanti raggiungibili |
| 5 | P2.1 ✅ · P2.4 ✅ · P2.2-P2.3 · P2.5 (legenda unica, Contesto, assenze, micro-visivi, badge forma) | una alla volta, con la misura rifatta |

Ogni intervento va rifatto passare da `fda build` + `verify_site.py` + `scripts/audit_match_sections.py`
e rimisurato con `scripts/prematch_sections.py`: la quota di testo per sezione è il numero che dice
se il peso si è spostato davvero dove serve.

---

## 5. Prossimo passo

**Il 2026-09-18 sono stati applicati i quattro P1 e il primo P2 (P2.1)** — misure prima/dopo in
[`docs/29`](29_p1_1_vita_del_club_riga_unica_2026-09-18.md) (3.030 → 829 caratteri visibili sulla
card «Vita del club»), [`docs/30`](30_un_dato_in_un_posto_2026-09-18.md) (dato di stagione ripetuto
in 3 → 1 altri riquadri; −357 caratteri visibili per scheda), [`docs/31`](31_verifica_approfondita_chiusa_2026-09-18.md)
(verifica chiusa; −1.767 caratteri visibili per scheda) e [`docs/32`](32_indice_della_scheda_2026-09-18.md)
(indice 4 → 11 voci, tutte vere; 0 → 6 card pesanti raggiungibili). Bilancio del turno: il testo
visibile per scheda pre-partita scende da **22.520 a 18.807 caratteri (−16,5%)**. Il 2026-09-19, sulla coda **P2**: applicate **P2.1** (`docs/33`: legenda unica della stima stabilizzata, 4 → 1 occorrenze) e **P2.4** (`docs/34`: «Contesto» diviso in «Arbitro e meteo» e «Precedenti», indice 11 → 12 voci, «Contesto» 2 → 0 occorrenze). **In coda**, in ordine di peso: **P2.2** (assenze raccontate in quattro modi), P2.3 (micro-visivi), P2.5 (badge forma nell'hero), P2.6 (quote assenti = decisione).
