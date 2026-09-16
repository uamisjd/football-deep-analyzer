# 21 — Verifica Quantitativa · Qualitativa · Visiva e piano di miglioramento

> **Sessione** `arena/01a0a5f3-football-deep-analyzer` · **data** 2026-09-15 ·
> **richiesta utente**: verifica quantitativa, qualitativa e visiva su progetto e sito; focus sulle
> schede delle partite **non ancora giocate**; «abbiamo informazioni accurate, profonde, ordinate
> sulle squadre? anche quelle informazioni interne importanti (dichiarazioni, crisi, problemi in
> società)? o consigliami tu altre cose».
>
> **Stato:** verifica conclusa; fix Q1 e Q6 applicati; **nella stessa sessione l'utente ha scelto
> «tutti in fila P0→P1» e i blocchi P0-1, P1-4 e P1-5 sono stati implementati, testati e pushati**
> (commit `8c81684`: card «Panchina e posta in gioco», riposo con le coppe, collettore notizie +
> card «Ultime dalle società», invarianti verify_site [19] e [20], suite 212 passed, verify_site
> 0 problemi · 23.940 controlli). Resta **DA VERIFICARE IN ACTIONS** al primo run daily la
> raggiungibilità di Google News RSS / calendario coppe (dal sandbox non è misurabile, regola B6);
> la card notizie degrada a segnaposto onesto se la fonte non risponde. Il piano §4 resta valido
> per i blocchi P2/P3 non ancora attuati. Ogni numero qui è misurato in
> questa sessione sul checkout locale (dati del run `main` 2026-09-15 16:33 UTC) o sul sito
> rigenerato; ciò che non è misurabile dal sandbox è marcato **DA VERIFICARE IN ACTIONS**.

---

## 0. Metodo e ambiente

- Checkout del ramo di lavoro, `pip install -e ".[dev]"` (Python 3.11), suite completa, `fda build`,
  `scripts/verify_site.py`, `scripts/audit_match_sections.py`, censimenti ad hoc sui Parquet di
  `data/processed/` e sulle 4.129 pagine HTML generate.
- Lettura integrale di schede pre-partita reali (Ajax–Willem II 5781718, struttura di tutte le 76).
- Audit strutturale/visuale dell'HTML+CSS (gerarchie heading, `lang`, viewport, aria, media query,
  token di contrasto) e test `test_tema_contrasto.py`.
- **Limite dichiarato:** dal sandbox non si possono fare screenshot con browser reale
  (`cdn.playwright.dev` irraggiungibile, come tutte le fonti fuori da `github.com`): la verifica
  visiva è (a) audit strutturale, (b) test di contrasto, (c) **preview live** servita dal sandbox
  (porta 8000) che l'utente può aprire nel pannello di anteprima a 375 px e desktop. Le verifiche
  di rete sulle fonti nuove vanno fatte in GitHub Actions (regola B6).

---

## 1. Verifica QUANTITATIVA

### 1.1 Pipeline, codice, verifiche automatiche

| Misura | Valore misurato oggi |
|---|---|
| Suite di test | **202 passed** (19,8 s) |
| `verify_site.py` | **0 problemi · 23.636 controlli** (17 invarianti numeriche) |
| `fda build` | **376 schede** (76 pre + 300 post) · 2.364 fixture · 7.476 pagine giocatore |
| Calendario futuro | **1.987 partite, 0 senza previsione** (orizzonte completo fino a maggio) |
| `audit_match_sections.py` | 165 schede con catena/bande/percentile; margine hero incoerente **0/165**; parità narrativa 7/7 leghe (media 8,0 righe, divario 2,1) |
| `source_status` ultimo run | FotMob **7/7 OK**, Understat OK, Open-Meteo OK; **ESPN standings 403 cronico** isolato e dichiarato (non blocca) |
| Dati nel repo | `site/` ignorato da Git (`/site/` in `.gitignore`, 262 MB locali); Parquet versionati |

### 1.2 Copertura delle partite future (prossimi 7 giorni = 76 schede)

| Blocco di contenuto | Copertura | Nota |
|---|---|---|
| Previsione (1X2, λ, mercati, catena, bande storiche, percentile di lega, primo gol) | **76/76** | somma 1X2 = 1,0000 su tutte le 2.152 righe; λ entro i limiti di sicurezza (≤4,0/squadra, ≤5,5 tot); `n_train` ≥ 934 |
| Infermeria (indisponibili con motivo e rientro) | **76/76** | 1.038 righe totali: 946 infortuni, 92 squalifiche; `expected_return` popolato al 100% (valori onesti inclusi «non nota») |
| Arbitro + meteo | **76/76** | con medie gialli/rigori e fallback Open-Meteo dichiarato |
| H2H con bilancio e precedenti per campo | **76/76** (per campo: 49/76, soglia ≥8 casi dichiarata) | |
| Insights tradotti (streak, forme) | **76/76** | mai inglese a schermo |
| Formazione probabile | **47/76** | le 29 assenti sono **tutte** a 4,7–5,1 giorni dal fischio: la fonte non l'ha ancora pubblicata → segnaposto onesto (comportamento corretto, direttiva F) |
| PPDA | 53/76 | n.d. su NED1 10, POR1 9, GER1 3, ITA1 1: Understat non copre le neopromosse; la card lo spiega |

**Letti per lega (schede pre):** ENG1 10 · ESP1 19 · FRA1 9 · GER1 9 · ITA1 10 · NED1 10 · POR1 9 —
parità di presenza confermata; nessuna lega «di serie B».

### 1.3 Qualità del modello (misurata, non dichiarata)

- **Live** (89 gare valutate pre→post): RPS **0,2023** vs naive 0,2334 (Δ **−0,031**); per lega
  0,1886 (Serie A) – 0,1989 (Ligue 1) tranne **Bundesliga 0,2627 con Δ +0,004 su n=11** → dentro il
  rumore, da monitorare al crescere del campione (la pagina lo dichiara).
- **Backtest fuori campione** 5.820 gare: RPS **0,1988** (Δ −0,0328), log-loss 0,9837, esito
  azzeccato 52%, Brier 9 mercati 0,2018; gol attesi 2,839 vs 2,865 osservati; pareggio 25,9% vs 25,6%.
- **Calibrazione per mercato:** quasi tutto «compatibile» (IC Wilson); **2 segnali «fuori
  intervallo»** su 5.820: Over 2,5 (previsto 53,2 / osservato 54,9) e porta inviolata casa
  (30,1 / 28,4). Documentati in pagina; **non toccare il modello**, monitorare (§4 P3).
- Banda «Quando il favorito aveva questa forza»: 5.820 gare, IC di Wilson pubblicati; il modello
  risulta un filo prudente sui favoriti 50%+ e viene pubblicato così com'è, con la formula
  «frequenza passata, non promessa».

### 1.4 Sito: struttura, prestazioni, accessibilità

- 4.129 pagine HTML; `index.html` 79 kB (19 kB gzip), `prossime.html` 1,5 MB (**130 kB gzip**) —
  accettabile per un sito statico con calendario completo; schede giocatore 7.476.
- `lang="it"`, viewport, `aria-label`/`aria-live` su barre e filtri, focus visibili; **14 test di
  contrasto passati**; 10 media query (375 px, 360 px, `prefers-reduced-motion`,
  `prefers-contrast`, tema chiaro).
- Difetti strutturali misurati e loro stato: salto heading h2→h4 **solo nel footer** (3.964 pagine)
  → **fixato in questo turno** (h3 con stesso aspetto); `<th>` senza `scope` su 4.125 tabelle → P2;
  PNG di anteprima ufficiali in `docs/preview/` **fermi al design del 09/09** → P2.

### 1.5 Dati già raccolti ma MAI pubblicati (opportunità a costo zero)

| Dato | Dove vive | Copertura | Uso attuale |
|---|---|---|---|
| **Allenatore** per squadra-partita | `lineup.parquet` (`role="coach"`) | 694 righe · 132 squadre · 347 partite | **nessuno** (escluso anche dalle schede giocatore) |
| **Cambio allenatore** (esonero/nomina) | derivabile dalla storia dei `coach` per squadra negli snapshot | idem | nessuno |
| **Posta in gioco** (p_title, p_top4, p_rel, pos_mean, exp_points) | `season_sim.parquet` (Monte Carlo 10.000 sim) | tutte le squadre, 7 leghe | solo `stagione.html`, **non nelle schede** |
| Età media titolari, capienza stadio | `match_info.parquet` | 376 partite | non pubblicati nel pre |
| Calendario coppe (UCL/UEL) | `config/leagues.yaml` `cups_calendar_only` | configurato | **mai collezionato** → vedi Q4 |

---

## 2. Verifica QUALITATIVA

### 2.1 Cosa funziona (letto per intero su schede reali)

- **Catena «Come nasce questa probabilità»** a 4 passi con i valori salvati al momento del calcolo
  (non ricostruiti): modello gol → media pesata → griglia sulle λ inclinate → calibrazione, con Δ
  per passo. È il livello di trasparenza che quasi nessun portale pubblico ha.
- **Comunicazione dell'incertezza** conforme alla letteratura citata nei doc (frequenze naturali su
  base 100, dotplot quantile a 20 punti, IC di Wilson, «il più probabile non è *il* risultato»).
- **Onestà dei segnaposto** (direttiva permanente F): dato assente vs «non ancora pubblicato dalla
  fonte» vs fallback sono distinti e spiegati (formazione probabile, PPDA, meteo, precedenti).
- **Italiano integrale**, parità fra le 7 leghe, tooltip con fonte per riga, nessuna quota
  bookmaker come contenuto (direttiva utente).
- La scheda post aggiunge lettura, tiri, cartina, corsa xG, qualità tiri, probabilità in-play
  ricostruite e momentum: il pre e il post sono coerenti fra loro.

### 2.2 Difetti trovati (Osservato → Misura → Impatto → Soluzione)

**Q1 [fixato questo turno] «fuori rosa · n.d.» nella colonna impatto dell'infermeria.**
Osservato: la stessa espressione indica due cose diverse — il motivo FotMob «not in squad»
(traduzione corretta in `_UNAVAIL_IT`) e, nella colonna *impatto*, «il giocatore non ha statistiche
di stagione». Misura: 73 schede pre su 76 contenevano almeno una riga così. Impatto: un giocatore
«infortunio · giorno per giorno» etichettato «fuori rosa» si contraddice da solo e fa dubitare
dell'infermeria. Soluzione applicata: «**senza minuti in stagione · n.d.**» con tooltip che spiega
(es. nuovo acquisto); riga già attenuata di opacità. Suite 202 passed + verify 23.636 controlli dopo
il fix.

**Q2 [P0] Mancano allenatore, cambio di panchina e posta in gioco.** Il dato c'è già (§1.5): il
coach è raccolto ma mai mostrato; il cambio allenatore — uno dei segnali di crisi/rilancio più
forti che esistano — è *derivabile* dagli snapshot storici senza nuove fonti; `season_sim` darebbe
«cosa vale questa partita» (lotta salvezza 43%, corsa top-4 78%…). Impatto: la scheda pre racconta
bene *come* si gioca ma non *chi guida* e *perché conta*. Soluzione: card «Panchina e posta in
gioco» (§4 P0-1).

**Q3 [P1] Manca lo strato «interno»: dichiarazioni, crisi, problemi di società, mercato.**
Osservato: nessuna fonte notizie è implementata. Misura: `grep` su `src/` = zero collettori news;
eppure il catalogo `docs/02` ha **già verificato** Google News RSS (✅ titoli, link, fonte, data;
uso personale consentito) e l'endpoint ESPN `news`, e lo schema minimo `news(team_id,
published_at, title, url, source)` è disegnato da settembre. Impatto: è esattamente l'informazione
che l'utente chiede e che oggi il sito non può dare. Soluzione: collettore news + card «Ultime
dalle società» (§4 P1-5), con verifica di raggiungibilità **in Actions** (regola B6).

**Q4 [P1] I giorni di riposo contano solo il campionato.** `analysis.rest_days()` usa le fixture di
lega; `cups_calendar_only` (UCL/UEL) è configurato ma mai collezionato. Impatto: nelle settimane
europee una squadra che gioca il martedì in Champions mostra «6 giorni di riposo» nella scheda del
sabato — informazione sbagliata su un fattore che il modello non vede e la scheda sì. Soluzione:
collezionare il solo calendario coppe (~2 richieste/lega/run) e includerlo in riposo/congestione.

**Q5 [P2] Contesto stadio/rosa sottousato.** Età media dei titolari e capienza sono in
`match_info` ma non compaiono nel pre (lo stadio c'è solo come nome+città). Impatto minore: sono
dettagli di colore che completano «ordinate e profonde». Soluzione: riga nel blocco Contesto.

**Q6 [P2, parte fixata] Micro-accessibilità e documentazione visiva.** Footer h2→h4 fixato; restano
`<th>` senza `scope` (lettori di schermo) e i PNG di `docs/preview/` fermi al 09/09 (chi apre il
repo vede una home che non esiste più).

**Q7 [monitoraggio, non difetto] Due mercati fuori intervallo e Bundesliga live.** Su 5.820 gare
Over 2,5 e clean-sheet casa escono dall'IC Wilson; live la Bundesliga è sopra il naive con n=11.
Entrambi pubblicati con onestà. Regola: **nessun intervento sul modello** finché il campione non
rende il segnale stabile (paletto B8: prima si dimostra, poi si integra).

---

## 3. Verifica VISIVA

- **Preview live** del sito generato servita dal sandbox (porta 8000): l'utente la vede nel
  pannello di anteprima; verifica manuale consigliata a 375 px e desktop (regola: mai dichiarata
  fatta dall'agente finché non è fatta).
- Audit strutturale su 4.129 pagine: gerarchia heading pulita dentro le schede (h1 → h2 → h3,
  nessuno salto), card e tabelle coerenti col design system (36 token), tema scuro/chiaro,
  `prefers-reduced-motion` e `prefers-contrast` rispettati, barre 1X2 con valori testuali oltre al
  colore (WCAG).
- Contrasto: `tests/test_tema_contrasto.py` 14 passed.
- Screenshot con browser reale **non eseguibile dal sandbox** (rete limitata a github.com):
  dichiarato, non aggirato.
- Fix visivi di questo turno: footer con h3 (stesso aspetto, gerarchia corretta).
- Da fare: rigenerare i PNG/SVG di `docs/preview/` sul layout corrente; `scope` sui `<th>`.

---

## 4. Piano di miglioramento priorizzato

**P0 — zero fonti nuove, dati già nei Parquet (≈1 turno).**
1. ✅ **ATTUATO 2026-09-15** — **Card «Panchina e posta in gioco»** nelle schede pre: allenatore per squadra (da `lineup`
   coach); **rilevazione cambio allenatore** dalla storia degli snapshot (prima partita con coach
   nuovo → «Nª gara con X in panchina», segnale di crisi o di svolta); posta in gioco da
   `season_sim` (p_title/p_top4/p_rel + posizione media attesa, frase in italiano); età media
   titolari. Con invariante `verify_site` che ricalcola coach e cambio panchina dai Parquet.
2. *(fatto questo turno)* etichetta impatto infermeria onesta.
3. *(fatto questo turno)* gerarchia heading footer.

**P1 — 1-2 turni, con verifica in Actions.**
4. ✅ **ATTUATO 2026-09-15** — **Calendario coppe** (`cups_calendar_only`) collezionato calendar-only → `rest_days` e
   congestione veri («3 giorni di riposo, Champions inclusa»); zero impatto sul modello.
5. ✅ **ATTUATO 2026-09-15 (collaudo rete al primo run daily)** — **Collettore news** (Google News RSS per squadra `hl=it&gl=IT` + ESPN news per lega): tabella
   `news(...)` già disegnata in `02`; dedup per titolo normalizzato; finestra 14 giorni; card
   «Ultime dalle società» con ≤5 titoli per squadra, data e testata, link alla fonte; **solo
   titoli** (niente riassunti clickbait), niente hype «most X»; etichetta [news] e riga in
   `source_status`. Reachability e volumi **DA VERIFICARE IN ACTIONS** prima di pubblicare.

**P2 — rifiniture.**
6. Card «Clima del club» che unifica i segnali derivati già disponibili: streak senza vittorie
   (insights), scarto punti−xPTS (fortuna/sfortuna), cambio allenatore, peso dell'infermeria
   (assenti × valore di mercato), riposo corto → un solo blocco narrato con la regola che lo
   genera, mai un punteggio sintetico inventato.
7. Mercato: endpoint FotMob `transfers/marketValue/contractEnd` (da verificare in Actions) oppure
   dataset dcaribou come storico (congelato a luglio 2026); card «Mercato d'estate» arrivi/partenze.
8. Rigenerare `docs/preview/` sul layout corrente; `scope="col"`/`"row"` sui `<th>`.

**P3 — modello (laboratorio, non daily).**
9. ξ per lega e monitoraggio dei due mercati fuori intervallo + Bundesliga live, col protocollo
   walk-forward esistente; si cambia solo a IC interamente negativo e ≥5 leghe su 7.

**Da NON fare** (direttive utente o perimetro): quote come contenuto delle schede, in-play reale,
fonti a pagamento, scraper che richiedono il PC dell'utente.

---

## 5. Decisioni aperte per l'utente

1. Quale blocco parte prima: **P0-1** (panchina + posta in gioco, subito, senza rete) o **P1-5**
   (news, il vero strato «interno», ma serve il collaudo in Actions)?
2. News: soli titoli con testata+data (consigliato) o anche descrizione RSS (rischio clickbait)?
3. La card «Clima del club» (P2-6) la vuoi come blocco narrativo separato o integrata in
   «Analisi pre-partita»?

**Prossimo passo:** alla scelta dell'utente, implementare il blocco scelto con test + invariante
`verify_site` + aggiornamento di `STATO.md` e di questo doc; il merge resta all'utente (policy D).


---

## 6. Secondo giro sulla card «Panchina e posta in gioco» (2026-09-15, secondo turno)

**Direttiva utente:** «in questa sezione puoi fare di meglio e darmi informazioni più utili?
ogni sezione dovrebbe essere fatta per fornirmi informazioni utilissime» → diventata regola
permanente in `docs/00` (principio di utilità delle sezioni).

**Misura del difetto.** La prima versione pubblicava solo: nome allenatore + «panchina invariata
da N gare», percentuali Monte Carlo, età media. Letta sulla gara reale Rayo Vallecano–Espanyol
non rispondeva alle domande utili: *quanto rende* l'allenatore, *cosa succede* vincendo o
perdendo, *quanto dista* la squadra dagli obiettivi di classifica.

**Soluzione attuata** (solo dati già raccolti, nessuna fonte nuova; commit successivo a `8c81684`):
- profilo: età e nazionalità dell'allenatore dalla distinta (codici ISO tradotti, mai a schermo grezzi);
- **rendimento**: punti/gara sulle sole partite *finite* con l'allenatore corrente, con il numero
  di gare (es. Rayo 0,8 su 5 → segnale di crisi leggibile);
- **precedenti mirati**: bilancio dell'allenatore contro la squadra avversaria (da 3 gare in su) e
  scontro diretto col collega avversario (da 2 in su); sotto soglia non si stampa nulla;
- **posta in gioco di classifica viva**: posizione e punti, distacco dalla zona retrocessione
  (retrocessioni dirette: 18ª su 20 squadre, 17ª su 18) e dal 4º posto (linea Europa minima in
  tutte e 7 le leghe), regole dichiarate nella nota della card;
- **cosa succede**: posizione virtuale con vittoria/sconfitta (punti e differenza reti, altre gare
  in sospeso), etichettata «virtuale» e spiegata: «dice cosa vale il risultato, non lo prevede».

**Verifica.** Suite 215 passed (3 test nuovi sul blocco); `verify_site` 0 problemi · **24.546
controlli** con [19] estesa: le sei righe (`tenure`, rendimento, due precedenti, classifica,
virtuale) sono ricalcolate per ogni scheda pre e confrontate col testo stampato; ruff pulito sul
codice nuovo. Resa reale misurata su Rayo–Espanyol: «16º con 4 punti · 2 punti sopra la zona
retrocessione · 6 punti dal 4º posto · con una vittoria 13º · con una sconfitta 16º».


---

## 7. Card «Clima del club» (2026-09-15, terzo turno — blocco P2-6 attuato)

**Richiesta utente:** «clima del club. procedi» (blocco narrativo separato, decisione già presa
nel primo turno).

**Cosa pubblica** (per squadra, solo se una soglia è superata; toni colore bad/warn/good):
- crisi di risultati da **3 sconfitte consecutive**; «non vince da N gare» da 4; «imbattuta da N» da 5;
- attacco a secco da **3 gare senza segnare**;
- scarto **punti−xPTS** da ±2 («raccoglie X punti meno di quanto crea» / «rendimento sopra la
  qualità del gioco, regressione possibile»);
- **shock di panchina**: Nª gara dal subentro (riusa il rilevamento cambio allenatore);
- **infermeria pesante** da 4 assenti o 2 titolari abituali o 0,5 xG+xA/gara in meno, con il
  valore di mercato ai box da 30 M€ in su;
- **riposo corto** ≤3 giorni (coppe incluse) e **congestione** da 3 gare in 10 giorni.

**Regola di onestà:** nessun punteggio sintetico; ogni riga è un fatto misurato col suo criterio;
soglie dichiarate nella nota della card; se nessuna soglia è superata la squadra legge «nessun
segnale anomalo nei dati raccolti: clima normale» (mai aggettivi inventati).

**Verifica:** suite **217 passed** (+2 test clima: Lazio in crisi con infermeria da 35 M€ e
congestione da 5 gare; Milan senza segnali → zero righe); `verify_site` **0 problemi · 24.781
controlli** con invariante nuova **[21]**: le righe stampate sono ricalcolate da `club_mood` per
ogni scheda pre e confrontate col testo (74 pagine riconciliate; le 2 senza segnali non hanno la
card, e se una squadra ha segnali la card deve esserci). Resa reale su Ajax–Willem II: Ajax
«infermeria pesante: 4 assenti… · riposo corto: 3 giorni», Willem II «non vince da 5 gare ·
raccoglie 2,3 punti meno di quanto crea · infermeria pesante: 6 assenti».


---

## 8. Principio di utilità applicato ad altre due sezioni (2026-09-15, quinto turno)

**Richiesta utente:** «continua e spiegami bene cosa vuoi fare, riflettici in modo accurato».
Ragionamento registrato: rilettura delle 17 sezioni della scheda pre con la domanda «che
decisione aiuta a prendere?»; le due ancora descrittive erano «Scontro tattico» (stile senza
conclusione) e «I giocatori che decidono» (percentili senza dire se giocheranno).

**Scontro tattico → graduatorie e duello chiave.** Righe nuove per squadra: posizione in
classifica per attacco e difesa *per gol* («5º attacco · 2ª difesa su 18») e riga «duello
chiave» che nomina il lato più sbilanciato del match (prodotto dei rapporti attacco/difesa
sulla media gol della lega; vince il prodotto maggiore). **Scelta di metodo:** graduatorie e
rapporti si calcolano sulla **classifica FotMob**, una sola fonte per tutte le squadre della
lega, perché gli xG mescolano fornitori e violerebbero la regola di purezza già dichiarata
nella card; la nota lo spiega a schermo.

**Giocatori che decidono → «giocherà?».** Badge per ogni giocatore dalla distinta della
partita: «titolare probabile» / «in panchina» / «assente: motivo · rientro»; se la fonte elenca
lo stesso giocatore titolare e indisponibile vince l'indisponibilità (regola già in
``starters``). Avviso esplicito se il contributo offensivo più alto della lista è assente:
«il valore per 90 è stagionale e non vale per questa gara» (caso reale online: Ché Adams in
5749682, Ricardo Mangas in 5749686).

**Verifica:** suite **219 passed** (+2 test: graduatorie/duello su classifica sintetica con
skew atteso 1,20 vs 0,90; stati titolare/panchina/assente con duplicato che deve vincere
l'indisponibilità); `verify_site` **0 problemi · 25.237 controlli** con invarianti nuove
**[22]** (home_line/away_line/duel_line ricalcolati e confrontati col testo, 76 pagine) e
**[23]** (conteggi dei badge per pagina = conteggi dei ruoli nella distinta; avviso top
contributor presente se e solo se serve, 76 pagine). Resa reale su Ajax–Willem II: «duello
chiave: attacco Ajax (1,43× la media gol della lega) contro difesa Willem II (1,43× la media
gol subiti)».


---

## 9. Principio di utilità applicato al post-partita (2026-09-15, sesto turno)

**Richiesta utente:** «procedi» → estendo alle sezioni post-partita la domanda «che
decisione aiuta a prendere?». Audit delle 10 sezioni post: cronaca, tiri, migliori in
campo, cartina, corsa xG, qualità tiri, probabilità in-play, momentum, verifica
distribuzione, dettaglio — tutte *cosa è successo*; la «Lettura della partita» già
confronta xG-risultato e dà la probabilità che il modello assegnava all'esito. Mancava
lo sguardo in avanti: **quando si rigioca, con quanto riposo, e chi ha sprecato**.

**«Il prossimo impegno» (card nuova, in testa alla griglia post-partita).** Per squadra:
prima gara ufficiale dopo questa da `_rest_source()` (campionato + coppe europee, la
stessa fonte di `rest_days`), con competizione, avversario, casa/trasferta, giorno e ora
nel fuso display e giorni di riposo dal calcio d'inizio di stasera. Contano solo le gare
`scheduled`: rinviate/annullate non danno un impegno certo. Esempio reale online
(5749640): «Roma · Campionato · Inter in casa · sabato 19/09, ore 18:00 · 25 giorni di
riposo».

**Conversione delle grandi occasioni (riga nuova in «Tiri e occasioni»).** `shot_summary`
guadagna `big_goals` (gol tra i tiri a xG ≥ 0,30, autogol esclusi): «…di cui convertite
in gol: 3 su 4 / 0 su 0». Distingue «ha creato poco» da «ha sprecato», il segnale più
utile per la gara successiva. La riga c'è se e solo se almeno una squadra ha avuto grandi
occasioni; `or 0` nel template perché una squadra senza tiri mappati ha summary `{}`
(l'aritmetica su Undefined Jinja solleva: trovato dai test sintetici, non in produzione).

**Nota di riuso:** i nomi di giorni/mesi italiani vivevano in `build.py`; spostati in
`fmt.py` (fonte unica) con il nuovo helper `it_day_time(ts, tz)` usato da
`next_commitment` per comporre la riga pronta per il template.

**Verifica:** suite **223 passed** (+4: coppa che batte campionato e gara annullata
saltata; riga esatta campionato con fuso; nessun impegno → None; 2 grandi occasioni con
1 convertita e autogol escluso); `verify_site` **0 problemi · 26.973 controlli** con
invarianti nuove **[24]** (righe «prossimo impegno» ricalcolate dal calendario su tutte
le **300** pagine finite; card presente se e solo se esiste una gara futura) e **[25]**
(celle «X su Y» = conteggi dai tiri mappati, **268** pagine; riga assente se nessuna
grande occasione). Ruff: nessun avviso sul codice nuovo.


---

## 10. Mercato d'estate (P2-7 attuato, 2026-09-15 — sesto turno, parte 2)

**Richiesta utente:** «procedi» → primo blocco del P2 residuo: il mercato. La fonte è
l'endpoint FotMob `teams?id=...` (marcato ✅ in docs/02, sezione `transfers`), lo stesso
client già usato per tutto il resto: **schema non documentato**, quindi il parser
(`FotMobClient.parse_transfers`) accetta le due disposizioni note — `{incoming, outgoing}`
e lista piatta con direzione per voce — più gli alias comuni dei campi (fee oggetto o
stringa, from/to oggetto o stringa, date oggetto o stringa). Forma non riconosciuta →
**zero righe, mai righe inventate**: il conteggio appare nel log di run («transfers: N
righe da M squadre», artifact di Actions) e in `source_status`.

**Collettore isolato** `collect_transfers` (stesso pattern delle notizie): una richiesta
per squadra della classifica FotMob (~140), cache 24 h (la finestra si muove piano), una
squadra irraggiungibile non ferma il run. È dentro `collect_all(with_transfers=True)`:
dal merge in poi il run giornaliero di Actions lo esegue e committa `transfers.parquet`
insieme agli altri dati. **Dark launch onesto:** finché la tabella non esiste la card non
compare da nessuna parte (placeholder onesto, `summer_market → None`); si accende da sola
al primo run riuscito. DA VERIFICARE IN ACTIONS al primo daily: righe > 0 e forma dei
campi (importi, date).

**Card «Mercato: arrivi e partenze»** (pre-partita, tra «Clima del club» e «Ultime dalle
società»): per squadra i conteggi e i 4 movimenti più recenti per direzione (data desc),
con formula in italiano (prestito / titolo definitivo / gratuito / rientro), controparte
e data; importi **come pubblicati dalla fonte**, senza conversioni. Nota di utilità in
chiusura: un arrivo recente può non essere ancora riflesso nelle statistiche stagionali
della scheda. Resa collaudata con store sintetico in /tmp (Monza–Sassuolo 5749686, non
committato): conteggi, ordine per data, traduzioni e importi corretti.

**Verifica:** suite **229 passed** (+6: parser dizionario/lista/forma-ignota, collettore
tollerante con stub che esplode su una squadra, `summer_market` ordine+conteggi+None);
`verify_site` **0 problemi · 26.973 controlli** con invariante nuova **[26]** (nomi e
conteggi della card = tabella transfers; card presente se e solo se la fonte ha righe —
oggi vacua per costruzione: 0 pagine, diventa attiva al primo dato reale). Ruff: RUF012
risolto con `ClassVar` (come `_COUNTRY_IT`); UP017 su `datetime.now(timezone.utc)`
lasciato: è l'idioma del file (6 occorrenze identiche a baseline).


---

## 11. Accessibilità delle tabelle: `scope` su ogni `<th>` (P2-8a, 2026-09-15 — settimo turno, parte 2)

**Richiesta utente:** «procedi» → prima metà del P2-8 (i PNG di `docs/preview/` restano
bloccati nel sandbox: CDN di Playwright irraggiungibile). L'audit Q6 aveva contato
4.125 celle d'intestazione senza `scope`: i lettori di schermo non potevano dire se
l'intestazione vale per la colonna o per la riga.

**Intervento:** trasformazione meccanica delle 7 template con `<th>` (193 attributi
aggiunti: `scope="col"` nelle righe d'intestazione, `scope="row"` nelle etichette di
riga, `scope="colgroup"` sui `colspan` che coprono più colonne — half-split e gruppi
statistiche giocatore). Due casi multiriga (etichetta dello Scontro tattico e intestazioni
della matrice punteggi) gestiti esplicitamente perché il `<td>` vive nelle righe
successive. Resa visiva invariata: il CSS usa selettori d'elemento, non attributi.

**Verifica:** invariante nuova **[27]** in `check_pages` — ogni `<th>` di ogni pagina
generata deve dichiarare `scope` (oggi **101.958 celle** su 376 pagine, 0 violazioni) —
più test statico sulle template (`test_scope_th`, 11 parametrizzati) che scatta prima
ancora del build. Suite **240 passed**.

**Regressione trovata e riparata:** `verify_site` [5] cercava il letterale
`<th>Precedenti (N)</th>`; con lo scope l'archivio precedenti non veniva più contato
(0 archivi, −74 controlli sul totale). Regex allargata a `<th[^>]*>`: [5] torna a 74
archivi e il totale a **26.973 controlli · 0 problemi**. Lezione: i parser del
verificatore vanno scritti tolleranti agli attributi, non solo al testo.

**Nota dati:** la tabella `news` nel repo è vuota ([20] = 0 pagine, card «Ultime dalle
società» assente): stato preesistente a questo turno, si popola al primo run di Actions
con Google News raggiungibile — stessa logica del dark launch di `transfers`.


---

## 12. Anteprime di `docs/preview/` rigenerate sul layout corrente (P2-8b, 2026-09-15 — nono turno)

**Richiesta utente:** «procedi, e spiegami meglio le proposte ogni volta». Prima di
proporre ho riletto come nascono le anteprime: **non sono screenshot del browser** ma
disegni Pillow di `scripts/render_preview.py`, coi token del CSS copiati a mano. Nel
sandbox un browser non c'è (e la CDN Playwright è irraggiungibile), ma Pillow sì: il
problema vero non era «serve un workflow Actions», era che lo script disegnava ancora il
layout del 09/09 (nav a 7 voci senza «Giocatori», card col chip-data in mezzo, niente
barra 1X2 con etichette sotto, niente segnale DC/Elo, footer vecchio).

**Cosa ho ridisegnato (tutto verificato sul sito reale prima di scrivere):**
- header: brand + sottotitolo, nav a **8 voci** con pill «Oggi», badge «v2 · aggiornato
  15/09/2026 23:32 (ora italiana)», bottone tema ◐;
- home: titolo e sottotitolo della pagina, striscia riepilogo giornata (4 partite ·
  2 campionati · 4/4 con modello · 1 in corso · 3 terminate + nota), chip dei filtri e
  ricerca, etichetta del giorno;
- card partite con l'anatomia attuale: stato col pallino (in corso rosso / terminata
  grigio), orario, tag lega, «Analisi ↗», squadre con posizione e punti in classifica,
  punteggio centrale, «Lettura del modello» (favorito + %, margine sul secondo), barra
  1X2 con etichette sotto e favorito in accent, striscia segnale DC/Elo, piede
  «MODELLO» con gol attesi e Over 2,5, forme V/N/P e fatti rapidi (infermeria, meteo,
  arbitro, precedenti);
- footer con la nota legale per esteso (18+).
I numeri nelle due card sono **quelli veri pubblicati su `site/index.html` nel build del
15/09**: Elche–Real Madrid *in corso* 0–2 (con l'infermeria 2+3 assenti) e Ajax–Willem II
5–1: l'anteprima mostra sia lo stato live sia quello finale.

**SVG ritirati:** `home-preview.svg` e `header-preview.svg` erano mock vettoriali
disegnati a mano, derivati dal sito e non referenziati da nessuna parte: tenerli accanto
ai PNG nuovi avrebbe mostrato due design diversi per la stessa pagina. Ora i PNG generati
dallo script sono l'unica anteprima ufficiale (riproducibile: `python
scripts/render_preview.py [--out DIR]`, Pillow dichiarata tra le dev-extras; smoke test
`test_render_preview` che rigenera in tmp e controlla le dimensioni). I PNG li ho
ispezionati a occhio dopo la generazione (sovrapposizione sottotitolo/nav corretta,
sottolineatura del giorno fuori dal testo).

**Nota operativa:** il sandbox è stato riavviato a metà turno (persi `.venv/` e `site/`,
`.git` riportato shallow al commit base). Ripristinato da `origin/arena/…` (tip
`db7aaa3`), `git fetch --unshallow`, merge di `origin/main` (data run 20:48 UTC: dati
freschi, sito e verify rigirati: **26.933 controlli · 0 problemi**), venv ricreato.
Suite finale **241 passed** (+1 smoke preview).


---

## 13. ξ per lega: esperimento e gate di adozione (P3-a, 2026-09-15 — decimo turno)

**Richiesta utente:** «procedi» → primo blocco del P3 laboratorio. ξ è il decadimento
temporale di Dixon-Coles (quanto in fretta le gare vecchie smettono di contare: oggi
0,0018/giorno, unico per tutte le leghe). L'idea del piano: stimarlo lega per lega col
protocollo walk-forward già esistente, cambiando solo a evidenza solida.

**Cosa è stato costruito.**
- ``lab.xi_league_experiment``: per lega e per ξ nella griglia (0,0010 / 0,0014 / 0,0018 /
  0,0024 / 0,0030) cammina sullo storico con le stesse finestre del laboratorio (fit solo
  sul passato); il ξ migliore è confrontato con quello globale **sulle stesse identiche
  gare** (appaiate per data+squadre) e il ΔRPS passa dal bootstrap appaiato 95% già usato
  dal laboratorio (``paired_bootstrap``).
- Regola di adozione (quella del piano, resa eseguibile): una lega prende il proprio ξ
  solo se l'IC 95% del Δ è **interamente sotto zero** e le gare fuori campione sono
  almeno 300 (``MIN_XI_LEAGUE_N``); altrimenti tiene il globale. Il modello globale non
  viene mai toccato da questo meccanismo.
- Comando ``fda lab-xi`` (stesse opzioni del laboratorio: ``--step-days``,
  ``--min-train``, ``--history``, ``--save``) che scrive ``xi_league.parquet``; il
  workflow ``lab`` (settimanale) ora lo esegue dopo il confronto modelli e committa
  l'artifact con log negli artefatti di run.
- Produzione: ``predict.xi_for_league`` legge l'artifact e restituisce il ξ della lega
  **solo se ``adopt=True``** (file assente, lega non adottata o valore non positivo →
  globale); il ciclo di ``fda predict`` lo usa e stampa nel log quale ξ ha applicato.

**Risultato (due configurazioni, stessi dati).**
- protocollo lab (finestre 90 g, min 800): ENG1 Δ −0,0001 IC [−0,0004; +0,0002], ESP1
  −0,0001 [−0,0008; +0,0006], NED1 −0,0012 [−0,0025; +0,0002], ITA1 nessun candidato
  migliore del globale; FRA/GER/POR sotto le 300 gare → **0 leghe su 7 adottano**.
- robustezza (finestre 60 g, min 600 → 335-490 gare per lega): ancora **0 su 7**, tutti
  gli IC a cavallo di zero (il più vicino, NED1: −0,0006 [−0,0015; +0,0003]).
L'esito «nessun cambiamento» *è* il risultato: con lo storico attuale (3 stagioni) il
decadimento per lega non si distingue da quello globale; il laboratorio settimanale
ririfà la misura man mano che lo storico cresce, e l'artifact commitato terrà memoria
dell'evidenza (oggi: tutte ``adopt=False``).

**Verifica:** suite **244 passed** (+3: struttura e regola dell'esperimento su storico
sintetico, soglia delle 300 gare, gate ``xi_for_league`` con adozioni/rotte/assenti);
ruff pulito sul nuovo (RUF046 su ``int(len())`` corretto). P3-b (monitoraggio mercati
fuori intervallo) resta in coda.

## 14. Monitoraggio dei mercati fuori intervallo (P3-b, 2026-09-15 — undicesimo turno)

**Richiesta utente:** «procedi» → secondo e ultimo blocco del P3 laboratorio. L'audit
(§3) aveva trovato due mercati binari con probabilità prevista fuori dall'intervallo di
Wilson dell'osservata: **Over 2,5** (53,2% prevista vs 54,9% osservata) e **porta
inviolata casa** (30,1% vs 28,4%). La regola del piano: si tocca un mercato solo se lo
scarto è *strutturale*, altrimenti si monitora e il modello resta com'è.

**Cosa è stato costruito.**
- ``backtest.BINARY_MARKETS``: i 9 mercati binari della card Accuratezza (stesse chiavi
  di ``SiteBuilder.MARKETS``) + ``observed_markets``, che per ogni gara del backtest
  ricava il vettore osservato 0/1 di ciascun mercato dai gol reali.
- ``market_monitor(df, min_league_n=150, min_structural_leagues=5)``: per mercato —
  scarto media prevista vs osservata con Wilson 95%; **stabilità temporale** (il campione
  diviso in due metà cronologiche: ciascuna metà conta solo se anche lei è fuori
  intervallo); **stabilità tra leghe** (quante leghe con n≥150 sono fuori intervallo con
  lo stesso segno). Verdetto ``strutturale`` solo se: fuori intervallo overall **e** ≥5
  leghe stesso segno **e** entrambe le metà temporali stesso segno; altrimenti
  ``monitora``.
- Comando ``fda mercati-monitor``: legge la tabella ``backtest`` e le applica la
  calibrazione salvata (``calibrate_rows(bt, from_store(store))``) così monitora le
  probabilità *pubblicate*, non quelle grezze; stampa la tabella e salva
  ``mercati_monitor.parquet``. È agganciato al ``fda daily`` subito dopo ``backtest``:
  dal merge, ogni run di Actions ricalcola il verdetto.

**Risultato (probabilità calibrate, n=5.823 gare, 7 leghe, 3 stagioni).**
- **0 mercati su 9 «strutturale»** — nessun mercato viene toccato.
- I due segnali dell'audit restano fuori intervallo overall, ma ciascuno vive in **una
  sola metà temporale**: porta inviolata casa 0,3015 vs 0,2840, IC [0,2726; 0,2958],
  prima metà fuori(−) / seconda dentro, 1 lega su 7 fuori; Over 2,5 0,5317 vs 0,5490,
  IC [0,5362; 0,5618], prima metà dentro / seconda fuori(+), 1 lega su 7 fuori.
- Gli altri 7 mercati (btts, 1X2 doppie chance, over 1,5/3,5, cs trasferta) sono dentro
  l'intervallo overall.
Lettura: scarti veri ma **non coerenti nel tempo né tra leghe** → più deriva/rumore di
periodo che bias strutturale; la regola P3 dice di non calibrare e di continuare a
misurare. Il monitor giornaliero è il meccanismo che trasformerà la misura in decisione
se e quando lo scarto diventerà persistente.

**Verifica:** suite **246 passed** (+2: su storico sintetico a 7 leghe — over25 con bias
indotto ovunque → ``strutturale`` con 7 leghe; btts centrato → ``monitora``; cs_h con
bias in una sola lega → fuori intervallo ma ``leagues_out`` < 5 → ``monitora``); run
reale → ``mercati_monitor.parquet``; build + ``verify_site`` **0 problemi · 26.821
controlli**; ruff pulito sul nuovo (3 RUF046 corretti). **P3 completo (P3-a + P3-b).**
Resta: verifica post-merge del primo daily di Actions (righe transfers, tabella news,
``mercati_monitor`` aggiornato).

**Consuntivo post-merge (run daily 35031258981, 2026-09-15 22:42 UTC).** PR #34 fusa
in ``main`` (``bd8a4d5``); il trigger push ha girato il primo daily col nuovo codice:
success + deploy Pages. Sul sito pubblicato: ``mercati_monitor`` **9 righe** e
``xi_league`` **7 righe** presenti tra le tabelle; il verdetto ricalcolato da Actions è
identico al locale (0/9 «strutturale»; cs_h fuori solo nella prima metà, over25 solo
nella seconda, 1 lega su 7 ciascuno). Notizie e trasferimenti: fonti a registro OK
(news 139 richieste, transfers 263) ma **zero righe utilizzabili** → tabelle assenti e
card buie come da dark launch onesto; ESPN dai runner risponde 403 su standings e news
(lato fonte). I log testuali di Actions non sono scaricabili dal sandbox (blob storage
irraggiungibile): i conteggi esatti («transfers: N righe») restano nell'artifact
``run-log`` del run.

## 15. Diagnostica delle due fonti a zero righe (`news`, `transfers`) — piano proposto (2026-09-15, tredicesimo turno)

### 15.1 Punto di partenza: quello che i dati committati dicono già (offline, run `35031258981`)

- `source_status`: `news:NEWS` **139 richieste**, `ok=True`, nessun errore; `transfers:TRANSFERS`
  **263 richieste**, `ok=True`, nessun errore. In `data/processed` **non esistono** `news.parquet`
  né `transfers.parquet` (il dark launch onesto non crea tabelle vuote).
- **Il contatore delle richieste è cumulativo sul client condiviso**, non per fase: `fotmob:CUPS` 131
  → `transfers:TRANSFERS` 263 ⇒ la fase transfers ha fatto **132 richieste = una per squadra** della
  tabella `fotmob_standings` (verificato offline: 132 righe, 132 `team_id` distinti, 7 leghe). Poiché
  nessuna voce di `source_status` inizia con «transfers», `_safe` non ha catturato eccezioni:
  **132 payload su 132 sono arrivati con HTTP 200 e `parse_transfers` ne ha estratto 0 righe.**
- Stessa lettura per le notizie: 139 = **132 feed RSS** (uno per squadra) + **7 ESPN di lega**; nessun
  errore «news rss …». Quindi **la rete ha risposto**: i due zeri nascono da *cosa c'è dentro il
  payload* o da *cosa il parser ne fa*, non da un blocco di rete.
- Limite dichiarato: dal sandbox `news.google.com` e FotMob sono irraggiungibili (verificato: SSLError),
  quindi la forma esatta dei payload resta non osservabile da qui; si progetta per **non doverla
  osservare a mano**.

### 15.2 Difetto meccanico dimostrato sulla fonte notizie (offline, deterministico)

`NewsClient.team_rss_raw` pre-codifica la query con `quote()` e poi la passa a `requests` in `params=`,
che la codifica **una seconda volta**:

```
requests.Request("GET", GOOGLE_RSS, params={"q": quote('"Ajax" calcio'), ...}).prepare().url
→ .../rss/search?q=%2522Ajax%2522%2520calcio&hl=it&gl=IT&ceid=IT%3Ait     # doppia codifica
atteso:                q=%22Ajax%22%20calcio
```

Google riceve la ricerca del testo letterale `%22Ajax%22 calcio`: feed **valido con 0 `<item>`** → `parse_rss`
ritorna `[]` → nessuna riga → nessun errore → «OK ma zero righe». È il sintomo osservato, spiegato senza
ipotesi. **[dimostrato offline; la conferma sul payload reale richiede Actions]**

### 15.3 Cosa manca oggi: perché un run «OK ma zero righe» non si spiega da solo

1. `source_status` registra **richieste ed esito**, mai **quante righe** sono state raccolte: «OK» e «OK
   senza niente» sono indistinguibili a schermo.
2. I parser inghiottono il silenzio: `parse_rss` ritorna `[]` sia per un feed vuoto sia per un corpo
   non-RSS (`ET.ParseError`), `parse_transfers` ritorna `[]` per qualunque forma non riconosciuta.
   Nessuno dei tre casi lascia traccia.
3. La contabilità è **conflata**: le richieste ESPN di lega passano dal client `news` (139) ma l'errore
   finisce sulla riga `espn:NEWS` (14, contatore del client ESPN condiviso) — due righe che raccontano
   una cosa sola.
4. `parse_rss` documenta «date illeggibili → la riga resta», ma `collect_news` scarta le righe senza
   data (`if pa is None: continue`): comportamento e documentazione divergono, e le righe scartate per
   questo motivo non si contano.
5. La diagnosi dell'utente («articoli fuori finestra / parsing fallito» per news, «schema cambiato /
   sezione assente» per transfers) **non è oggi decidibile** con i dati disponibili.

### 15.4 Piano proposto (4 blocchi, in ordine di dipendenza)

**Blocco 1 — imbuto dei conteggi per fonte (P0).** In `collect.py`: `CollectReport` acquisisce
`rows` (righe effettivamente salvate) e `detail` (imbuto compatto: `fetch=132 ok · item=0 · parsed=0 ·
kept=0 · stored=0`), pubblicati come **due colonne nuove** di `source_status`. In `stato.html`: colonna
«Righe» e, per le fonti `ok=True` con 0 righe, il motivo in chiaro accanto alla pill. Invariante nuova
in `verify_site.py`: *nessuna fonte con `ok=True` e `rows=0` può comparire in pagina senza spiegazione*.
- *Alternative valutate*: **(A1)** solo la colonna numerica `rows` → non dice *perché* è zero;
  **(A2)** solo testo in `warn` → mescola la semantica di `warn` («problema non bloccante») e non è
  testabile né aggregabile; **(A3)** tabella separata `source_diag` (una riga per fase) → più ricca ma
  raddoppia le superfici da mantenere per un guadagno marginale.
- *Scelta*: A su `source_status` (superficie che già esiste, già committata a ogni run, già in pagina).
  *Trade-off*: cambio di schema su Parquet → le righe vecchie avranno `NaN` in pagina (mostrate «—») e
  il costo è una manciata di kB per run.

**Blocco 2 — firma dello schema, *committata* e non solo loggata (P0).** Quando un payload arriva e le
righe sono 0, il parser produce un **digest**: solo **nomi** di campo (regex `[A-Za-z0-9_]{1,40}`,
max 12 per livello, max ~200 caratteri) del livello superiore e della sezione attesa, mai valori.
Il digest finisce in `detail` (quindi **nel Parquet committato**, leggibile dall'agente nel turno
successivo) *e* nel log.
- *Perché non la sola proposta (b) dell'utente (log dei nomi)*: i log di Actions non sono raggiungibili
  dal sandbox (blob storage) — già successo tre volte — mentre `data/processed/*.parquet` sì. Scrivere
  la diagnosi dove l'agente può leggerla costa zero e chiude il ciclo in un turno invece di chiedere
  all'utente di copiare righe di log a mano.
- *Trade-off/rischi*: nessun dato grezzo (solo nomi), lunghezza limitata, sanitizzazione; un test
  dedicato verifica che il digest non contenga valori né PII.

**Blocco 3 — correzione del difetto dimostrato sulle notizie (P0).** (a) `q` non più pre-codificato
(test con `requests.PreparedRequest` che asserisce **una sola** codifica); (b) `Accept` dedicato
`application/rss+xml, application/xml;q=0.9, */*;q=0.8` (oggi l'header di default è `application/json`,
che su un endpoint RSS è un invito a ricevere la pagina sbagliata); (c) il corpo non-RSS e il feed vuoto
diventano **conteggi** dell'imbuto (`bytes`, `items`, `parse_error`), mai silenzio; (d) contatori
**separati** `news` (RSS squadre) ed `espn` (notizie di lega, richieste fatte dal client ESPN);
(e) righe senza data: contate a parte (`no_date`) e **tenute**, con data «—» in card (allineando codice
e documentazione).
- *Criterio*: se dopo il fix i feed arrivano popolati, `news` mostra decine di righe per squadra;
  se Google risponde ancora con 0 `<item>`, il `detail` lo dirà con i byte scaricati (feed vuoto ≠ blocco).

**Blocco 4 — `parse_transfers` tollerante *dopo* la firma (P1, turno successivo).** Sapendo da 15.1 che
i 132 payload arrivano e che il parser non estrae nulla, le forme candidate sono tre: `{incoming,
outgoing}` (già gestita), lista piatta (già gestita), **contenitore `{"data": [...]}`** (frequente nelle
API FotMob, *non* gestita). Il Blocco 2 dirà quale è; poi il parser accetta anche il contenitore, con
**guardie anti-falso-positivo** (una voce è un trasferimento solo se ha un nome giocatore *e* almeno un
campo da trasferimento: fee/type/date/club) — così la rosa di una squadra non può essere letta come
mercato. *Perché non farlo subito*: la regola B8 («prima si dimostra, poi si integra») e il rischio di
pubblicare righe sbagliate in una card nuova; *costo*: un secondo ciclo di run invece di uno.

### 15.5 Criteri di accettazione e cosa non faremo

- **Verifica**: suite verde + `ruff` pulito sul nuovo; `fda build` + `verify_site.py` **0 problemi** con
  l'invariante nuova; un run daily reale (cron o dispatch utente) che mostri in `stato.html` o
  `righe>0` (fonte sana) o `righe=0` **con motivo** — mai più «OK» muto.
- **Chiusura del punto aperto**: se la firma rivela una forma nuova, il Blocco 4 la copre e si torna qui
  con i numeri; se i feed restano vuoti con byte>0, si valuta una seconda fonte RSS (o il ritorno a ESPN
  news quando il 403 cesserà) **solo con i dati in mano**.
- **Non faremo**: nuove fonti a pagamento, scraper che richiedono il PC, allargamento della finestra
  delle notizie «per far salire i numeri» (sarebbe un aggiustamento a caso), toccare ESPN 403 (degrado
  lato fonte, già coperto da FotMob/Google). Zero richieste in più verso le fonti: tutti i conteggi
  nascono da payload già scaricati.

### 15.6 Attuazione dei blocchi 1+2+3 (2026-09-15, tredicesimo turno — richiesta utente «123»)

**Cosa è entrato nel codice.**
- **Nuovo modulo `src/fda/diagnostics.py`**: `bump` (contatori d'imbuto), `key_names`/`shape_of`
  (firma dello schema: tipo, dimensioni e **soli nomi di campo**, whitelist
  `^[A-Za-z0-9_]{1,40}$`, max 12 per livello), `detail` (frase italiana per la pagina, ≤200
  caratteri) e `digest` (firma tecnica per il Parquet e il log, ≤240). Nessun valore, nessun
  dato grezzo, nessuna richiesta in più verso le fonti.
- **`collect.py`**: `CollectReport` ha ora `row_counts` / `details` / `digests` e il metodo
  `note(...)`; `as_status_rows()` pubblica tre colonne nuove di `source_status` — `rows`,
  `detail`, `digest`. Imbuto in tutte e quattro le fasi: lega (`fotmob` con calendario/partite/
  backfill/classifica, `understat`, `espn` con classifica+eventi, `openmeteo` **con il motivo**
  quando non salva nulla), coppe, notizie, mercato. Le notizie contano byte letti, articoli,
  corpi non-RSS, righe in finestra, fuori finestra, **senza data** e salvate; il mercato conta
  payload letti, voci viste, righe salvate e in quale forma è stata trovata la sezione.
- **`news.py`**: la query non è più pre-codificata (`google_news_params`), `Accept` RSS dedicato,
  `parse_rss` e `parse_espn_news` riempiono l'imbuto, `league_news_raw(..., http=)` fa contare
  le richieste ESPN al client ESPN; le righe senza data **non** vengono più scartate in silenzio:
  vengono contate (`senza data N`) e restano fuori perché la card promette una finestra di 12
  giorni — senza data la promessa non è verificabile (nota: anche `team_news` le escluderebbe,
  `NaT >= cut` è falso).
- **`fotmob.parse_transfers(..., diag=)``**: registra `sezione` (dict/lista/assente), i nomi dei
  campi della sezione e del livello superiore, le voci viste e le righe estratte.
- **Contatori per fase** (chiude anche il riscontro di `docs/19` §1.6 sulla colonna «Richieste»
  cumulativa): `source_status` registra il **delta** del contatore del client attorno alla fase,
  non il totale cumulativo del client condiviso. Prima `fotmob:POR1` 129 includeva le richieste
  di NED1 e `transfers:TRANSFERS` 263 quelle di tutte le fasi precedenti (la fase ne faceva 132).
- **`espn news` è un AVVISO, non un ERRORE** (`_WARN_NON_BLOCCANTE`): il 403 è un degrado lato
  fonte già coperto da Google News, come lo standings 403 è coperto da FotMob.
- **Sito**: `stato.html` ha la colonna **«Righe»** (— quando non applicabile) e, per le fonti
  `OK` con 0 righe, l'imbuto accanto alla pill; le righe vecchie senza le colonne nuove restano
  leggibili. Nuova invariante **[28]** in `verify_site.py`: *una fonte «OK» con 0 righe deve
  dichiarare il motivo* (un errore/avviso no: il motivo è già il suo testo).

**Verifiche misurate (offline).** Suite **261 passed** (246 + 15 nuove: 14 in
`tests/test_diagnostica_fonti.py`, 1 in `tests/test_verify_scripts.py`), `ruff --select F,E9`
pulito su tutto il toccato; `fda build` 376 partite / 2.364 fixtures / 7.478 giocatori in 2m43s;
`scripts/verify_site.py` **0 problemi · 26.951 controlli** con `[28] fonti con righe dichiarate:
32 righe`; scrittura reale provata su store sintetico (righe vecchie → `NaN` → «—» in pagina,
righe nuove → 0 righe con motivo). Il difetto Google News è coperto da un test di regressione su
`requests.PreparedRequest` (una sola codifica, `%2522` vietato).

**Cosa resta (blocco 4).** Il parser tollerante per `parse_transfers` (contenitore `{"data":
[...]}` e guardie anti-falso-positivo) **non** è entrato: la firma committata dal primo run reale
dirà quale forma ha davvero la sezione, poi si corregge con la prova in mano. **Da confermare in
Actions** (il sandbox non raggiunge le fonti): (a) `news:NEWS` con righe > 0 dopo il fix della
query; (b) la firma di `transfers:TRANSFERS`; (c) `mercati_monitor` invariato.

## 16. Primo run post-merge rosso: diagnosi e fix (2026-09-15 sera, tredicesimo turno)

**Cosa è successo.** Il merge di PR #35 (merge commit `1594170`) ha fatto partire il daily su
`main` dal trigger push — run **`35037211442`**, passo «Run giornaliero» **failure** (23:48:04 →
23:56:49), `deploy` saltato e **nessun commit di dati** (il sito è rimasto a quello del run
precedente). Il run `tests` su `main` è verde: il problema era nel runtime, non nei test.

**Come è stato letto il log (il pezzo che mancava).** Log e artifact di Actions stanno su blob
storage non raggiungibile dal sandbox (`docs/00` §B6): verificato di nuovo sul campo (EOF sia su
`results-receiver.actions.githubusercontent.com` sia su `productionresultssa8.blob.core.windows.net`),
e `gh run rerun` / `workflow_dispatch` rispondono **403** per il token dell'agente. Soluzione:
nuovo workflow **`.github/workflows/diag-fetch-log.yml`** che da un *runner* — che il blob lo
raggiunge — scarica l'artifact `run-log-*` del run indicato (`actions/download-artifact` con
`run-id`) e ne pubblica la coda sul branch **dedicato `diag-logs`**, dove l'agente la legge con
`git show origin/diag-logs:run-tail.txt` (branch riscritto a ogni estrazione: interessa solo
l'ultimo log). Il branch di lavoro e `main` restano così **puliti dai log**.
Si attiva con il dispatch (utente) o modificando `diag/trigger.txt` e pushando su un branch
`arena/**` (agente). Costo: un run di ~10 secondi, **zero richieste alle fonti**.

**Causa (dal traceback, non da ipotesi).**
```
src/fda/site/analysis.py:1110 in team_news
    unav = {u["name"].lower() for u in self.unavailable_for_news(team_name)}
TypeError: string indices must be integers, not 'str'
```
`unavailable_for_news` restituisce **nomi** (`list[str]`), mentre `team_news` li leggeva come
righe di tabella. Il difetto era **latente**: `team_news` esce prima quando la tabella `news` è
vuota (`news_df.empty`) — la condizione di tutti i run precedenti — e scatta solo con tabella
piena **e** almeno un indisponibile in distinta. I test coprivano i due casi separatamente
(tabella piena *senza* indisponibili; tabella vuota), mai la combinazione.

**Perché è emerso proprio ora (ed è una buona notizia).** Il fix del §15.6 ha funzionato: Google
News risponde e `news.parquet` si è popolato al primo run utile → la card notizie è uscita dal
dark launch ed è entrata in funzione, scoprendo subito il difetto. È la conferma del limite del
dark launch: **una card che non è mai stata eseguita con dati veri non è verificata**, anche se
i test sono verdi.

**Fix e verifiche (tutte misurate in locale).**
- `analysis.team_news`: l'insieme degli indisponibili si costruisce dai **nomi** (con commento
  che spiega il contratto e la storia del difetto).
- Test di regressione `test_notizie_con_indisponibili_regressione_run_35037211442` sulla
  combinazione esatta: **verificato che fallisce sul codice precedente** con lo stesso
  `TypeError` a `analysis.py:1110`, e che passa col fix (un test di regressione che non fallisce
  sul bug non è un test).
- Riproduzione del **percorso appena attivato**: store con `news` popolata su 12 squadre → build
  completa **OK**, card resa correttamente («Milan · 3 notizie verificate negli ultimi 12
  giorni…», con titolo, testata, data e link), `verify_site` **0 problemi · 26.987 controlli**.
- Dati reali del repo: `fda build` 376/2.364/7.478 in **3m12s**, `verify_site` **0 problemi ·
  26.951 controlli**; suite **262 passed** (+1); ruff pulito su tutto il toccato.
- **Non verificato**: il run reale successivo al merge (il sandbox non raggiunge le fonti) — è il
  primo controllo da fare, con l'imbuto di `news`/`transfers` in `stato.html` e la firma dello
  schema del mercato.

**Lezione registrata (vale per le sessioni future).** (1) Prima di dichiarare pronta una card in
dark launch, esercitarla in locale con la **tabella popolata**, non solo con tabella vuota: è il
punto in cui il difetto di oggi è passato. (2) Un run rosso non deve restare muto:
`diag-fetch-log.yml` porta i log nel repository e rende la diagnosi possibile anche quando il
sandbox non vede il blob.

## 17. Blocco 4: parser `transfers` sulla firma reale + card notizie al primo esercizio vero (2026-09-16, quindicesimo turno)

### 17.1 Post-merge della PR #36 e primo run verde con notizie

PR #36 fusa dall'utente (merge commit `f75ea6d`, 09:29:07Z). Il push ha fatto partire il daily su
`main` (run **`35079677152`**): **Success in 12m57s**, commit dati `6674adc` (run 09:41 UTC),
deploy Pages ok. Il sito è tornato a muoversi e — per la prima volta — la tabella `news` è
**popolata**.

**Imbuto del run, letto dai Parquet committati** (il prodotto del §15.6):

| fonte | richieste | righe | dettaglio |
|---|---|---|---|
| `news:NEWS` | 132 | **5.341** | il fix della doppia codifica funziona: ~40 notizie/squadra |
| `transfers:TRANSFERS` | 132 | **0** | 132 payload letti, 0 voci — ma ora **con la firma dello schema** |
| `espn:*` | 14 | 0 | standings/news 403 (lato fonte, isolati in avviso come da §15.6) |
| `fotmob:*` / `understat:*` | — | 380/380/306… · 866…938 | regolare |

Firma di `transfers` (dal `digest` in `source_status`):
`top dict(12): tabs,allAvailableSeasons,details,seostr,QAData,table,transfers,overview,stats,fixtures,squad,history · sezione dict campi type,data,allTransfers,allRumours,maxFee,ourTeamId`.

### 17.2 Ricerca: la forma reale della sezione (docs/02 aggiornato di fatto qui)

La firma dice **dove** stanno i dati ma non i campi delle voci. Prima di scrivere il parser
(regola: ricerca prima di ogni modifica importante) — fonte trovata: il pacchetto Go
**`mheers/go-fotmob`** (pkg.go.dev), che modella l'endpoint `teams` con tipi completi:

```go
type Team struct { Tabs …; Details *Details; Table …; Transfers *Transfers; Overview …; … }   // = le 12 chiavi della firma
type Transfers struct { Type *string; Data *TransfersData }                                   // + allTransfers/allRumours/maxFee/ourTeamId (non modellati lì, presenti nella firma)
type TransfersData struct {
    PlayersIn         []*Players            `json:"Players in,omitempty"`
    PlayersOut        []*Players            `json:"Players out,omitempty"`
    ContractExtension []*ContractExtension  `json:"Contract extension,omitempty"` }
type Players struct {  // la voce di trasferimento
    Name *string; PlayerID *int; Position *Position /*{label,key}*/; TransferDate *time.Time
    TransferText []interface{}; FromClub *string; FromClubID *int; ToClub *string; ToClubID *int
    Fee interface{} /*{feeText,localizedFeeText,value}*/; TransferType *TransferType /*{text,localizationKey}*/
    ContractExtension bool; OnLoan bool; FromDate *time.Time; ToDate *time.Time; MarketValue *string }
```

Punti salienti: le chiavi di `data` **contengono spazi** («Players in», «Players out», «Contract
extension»); `fee` è un dict `{value, feeText, localizedFeeText}` con chiavi di localizzazione
(`on_loan`, `transfer_fee`, `transfer_type_free_transfer`); `transferType` è un dict `{text,
localizationKey}`; la direzione è deducibile da `ourTeamId` vs `fromClubId`/`toClubId`.

### 17.3 Il parser tollerante (blocco 4 attuato)

`FotMobClient.parse_transfers` riscritto con **disposizioni a strati**, in ordine di preferenza:

1. `transfers.data["Players in" / "Players out"]` — quella vera, direzione esplicita;
2. `transfers.allTransfers` — lista piatta: direzione da `ourTeamId` vs `toClubId`/`fromClubId`
   (confronto tollerante int/str), o campo `transferDirection` se presente;
3. legacy `transfers.incoming/outgoing` e lista piatta (i test del P2-7 continuano a passare).

Scelte deliberate, dichiarate nella docstring:
- **Rinnovi** («Contract extension», o voce con `contractExtension: true`) **non sono movimenti
  in/out** e non vengono pubblicati come tali: solo contati nell'imbuto (`rinnovi`). La card
  «Mercato» mostra arrivi e partenze, non le proroghe.
- **Voci di mercato** (`allRumours`) **non confermate**: mai nella tabella, solo contate
  (`voci_mercato`). Pubblicare una trattativa come se fosse un trasferimento fatto sarebbe
  un dato falso.
- `marketValue` non si salva: colonna che nessuna pagina usa oggi (l'audit del §1 misurava i
  «dati raccolti mai pubblicati» come difetto, non come obiettivo).
- Fee e tipo **tradotti** (`_FEE_KEY_IT` nel parser + `_FEE_IT` e «on loan»/«contract» in
  `analysis`): le chiavi di localizzazione e i testi inglesi noti non vanno a schermo; i valori
  sconosciuti restano come la fonte li scrive (es. «€18.5M»), nessun dato inventato.
- Controparte **per direzione**: un arrivo arriva *da* (`fromClub`), una partenza va *verso*
  (`toClub`).

Diagnostica estesa (sempre e solo nomi di campo, mai valori): `campi_data` (chiavi di `data`,
ora visibili perché la whitelist `FIELD_NAME` ammette spazi singoli fra parole — rischio residuo
documentato nel codice), `campi_voce` (chiave della prima voce), contatori `rinnovi`,
`voci_mercato`, `senza_direzione`, `voci_senza_nome`; la «disposizione» vinta finisce in
`sezione` (`dict/data`, `dict/allTransfers`, `dict/in-out`, `lista`, `assente`) e quindi nel
detail di `stato.html` **anche con righe > 0** (prima il «perché» si pubblicava solo a righe
zero). La firma in `source_status` ora include `campi data` e `campi voce`: se la forma cambia
ancora, il Parquet del run successivo lo dice da solo.

Test: +4 su `test_mercato.py` (disposizione reale con tutti i tipi di campo; `allTransfers` con
direzione calcolata, movimento estraneo scartato, rinnovo contato; imbuto del collettore con
detail/digest; card end-to-end con fee/tipi italiani) — **272 righe di fixture sulla forma
misurata**.

### 17.4 La card notizie al primo esercizio vero: 115 problemi, tutti diagnosticati

`verify_site` sul sito costruito con le notizie vere (il daily **non** lo esegue: è un gate
locale) ha segnalato **115 problemi**: 99 sulla card notizie («notizia di squadra estranea» ×95,
«N notizie (max 4)» ×4) e 16 «decimale col punto». Diagnosi, con i dati alla mano:

1. **Attribuzione per URL (difetto del verificatore).** Lo stesso articolo viene raccolto per
   **entrambe** le squadre che cita (misurato: **885 URL su 4.419** presenti in `news.parquet`
   per più `team_id`; es. «Formazioni Toulouse - Le Havre AC» sta nei feed di Toulouse *e* Le
   Havre). [20] attribuiva ogni link alla **prima riga** con quell'URL → notizie giuste lette
   come «estranee» e conteggi gonfiati. Erano falsi positivi: la ricomputazione con
   attribuzione corretta dà **0** estranee vere e **0** sforamenti del tetto.
2. **Decimali col punto dentro titoli e brani verbatim** («quote 13.09.2026», «Valutazione
   Sofascore 8.9», «venerdì alle 13.15»): sono parole delle testate, pubblicate *verbatim* per
   scelta progettuale (P1-5, dichiarato nel footer della card). L'invariante protegge i numeri
   **nostri**, non le citazioni.
3. **Un difetto VERO trovato sotto i falsi positivi**: 116 righe con stesso `team_id`+titolo e
   URL diversi (sindacazione) → **2 pagine** con lo stesso titolo stampato due volte nella
   stessa card (Sassuolo su 5749686, Cambuur su 5781755). Sembra un bug del sito, sprecava uno
   slot del limite.

Correzioni:
- **`analysis.team_news`**: dedup per titolo (case-insensitive) prima del taglio a `limit` —
  la card mostra 4 notizie **distinte**, resta la copia più rilevante (regressione testata);
- **`verify_site` [20] riscritto per blocchi**: l'header «<p><b>Squadra</b> · N notizie…</p>»
  dice di chi è la card; ogni link deve esistere in `news.parquet` **per quella squadra**,
  conteggio ≤ 4 e **uguale al dichiarato** nell'header;
- **`verify_site` controlli token** (decimali/inglese/residui/concordanza): la card
  `id="notizie"` è esclusa dal testo verificato (parser `Text` con salto del blocco), come
  già accade per style/script/svg.

**Prova di morso** (un verificatore che non morde è decorativo): pagina reale 5802944 con una
notizia di Le Havre spostata nella card di Toulouse → `[20]` segnala **«notizia di squadra
estranea alla card di Toulouse»**, «5 notizie per Toulouse (max 4)» e «dichiara 4 notizie ma ne
stampa 5»; pagina ripristinata → 0 problemi.

### 17.5 Verifiche e cosa resta da confermare in Actions

- Suite **268 passed** (262 + 6: 4 parser mercato + dedup notizie + esclusione verbatim),
  `fda build` 376/2.364/7.490, `verify_site` **0 problemi · 27.501 controlli** (prima:
  115 problemi), ruff **invariato sul baseline** (64 = 64 sui file toccati).
- **Non verificabile dal sandbox** (fonti irraggiungibili): il parse dei **payload reali** di
  `transfers` — la firma dice che la forma è quella del §17.2 e il parser la copre, ma il
  conteggio vero (righe, rinnovi, voci di mercato) lo dirà il **prossimo run daily**, leggibile
  dall'imbuto in `stato.html` e da `transfers.parquet`. Se fosse di nuovo zero, la firma estesa
  (`campi data`, `campi voce`) dirà esattamente cosa cambia, senza aprire i log.
- Da quel run si attiva anche l'invariante **[26]** della card mercato (oggi vacua: tabella
  vuota), già compatibile con le colonne del parser.

## 18. Conferme dal primo daily post-blocco 4 + coda P0 svuotata (2026-09-16, sedicesimo turno — sessione `arena/01a0a9eb`)

### 18.1 Le due conferme lasciate in sospeso dal §17: **entrambe verificate**

Letti i Parquet committati dal run verde `35087648951` (post-merge PR #37, dati `e94700b`, 11:06 UTC):

- **`transfers` ha righe vere: 4.230** (prima: 0 su tutti i run precedenti). Imbuto dal `detail`:
  «payload letti 132 · voci viste 4.231 · salvate 4.231», 132/132 squadre con dati (media 32,
  min 7, max 73 per squadra). Il parser a disposizioni sovrapposte del §17 funziona **dal vivo**.
- **Invariante [26] attivata**: «card mercato riconciliate: 72 pagine» — prima vacua (tabella vuota).
- **Card notizie senza doppi**: il build locale sui dati reali (376/2.364/7.490) e `verify_site`
  non segnalano più titoli duplicati per sindacazione (il difetto reale del §17 è chiuso).
- `news` stabile: 5.343 righe (5.341 nel run precedente).

### 18.2 Falso positivo residuo di [20], trovato e corretto

Con `transfers` e `news` piene, il verificatore segnalava **1 problema** su `5868080.html`
(Villarreal–Levante, futura al 20/09): «notizia fuori finestra 12 giorni». Diagnosi coi dati:
lo **stesso URL** era presente in `news.parquet` **due volte per la stessa squadra** con
`published_at` diversi (07:00 e 01:21 del giorno dopo — il feed di Google News ripubblica il
link con data aggiornata). Il build filtra su `kickoff − 12g` e stampa la riga dentro finestra
(01:21); il verificatore guardava solo `iloc[0]` (la riga vecchia, fuori di 9,5 ore). Fix:
helper `notizia_in_finestra()` — la notizia passa se **almeno una** riga raccolta per
(url, squadra) rispetta la finestra; righe senza data ignorate, non valide. Test di regressione
con le due righe reali. Verifica: **0 problemi · 28.722 controlli**.

### 18.3 Accuratezza onesta: P1.1 (baseline naive) + P0.6 (composizione del campione)

- **`outcome_freqs()`** in `build.py`: frequenze reali 1·X·2 per `league_key` da
  `history.parquet` (**7.396 gare**: ITA1 1.180, ENG1 1.180, ESP1 1.194, NED1 972, POR1 971,
  FRA1 954, GER1 945); sotto le 30 gare di storico la lega resta sul fallback **dichiarato**
  45/27/28 (colonna nuova «n base» in tabella: «fisso» quando scatta il fallback). Il 45/27/28
  fisso gonfiava il Δ fino a +0,00205 RPS (§1.6 di `docs/19`); ora la Serie A mostra Δ −0,031
  su base 0,2200 (frequenza reale di lega) invece di −0,021 su base hard-coded.
- **`composizione_campione()`**: la pagina dichiara quante gare valutate sono del modello
  corrente. **Misura reale: 93 gare, solo 12 con `dc-elo-tilt-0.4`**, 21 con calibrazione
  attiva, 81 di ricette precedenti in archivio — conferma che l'audit di `docs/19` §1.5 era
  ancora più moderato del vero. Riga di composizione con le versioni in archivio.
- **`verify_site` [3b]** (spirito P0.8, invarianti di pubblicazione): ogni Δ della tabella
  deve equalare RPS − naive **ricalcolato dai numeri stampati**; la composizione dichiarata
  deve coincidere con la riga «Tutti»; Σ leghe = «Tutti». Ha morso subito in sviluppo
  (raddoppio di conteggio includendo «Tutti» nella somma) → corretto.

### 18.4 P0.5: CSS esterno con cache-busting — **sito 273 MB → 109 MB (−60%)**

Il design system (**39.590 byte**) era inline in `base.html` e duplicato in ogni pagina
(~10.400 file). Ora vive in `src/fda/site/assets/site.css`, scritto in `site/assets/site.css`
dal primo `_render` (lazy: copre anche `build_match_pages`/`build_indexes` usati dai test),
linkato con percorso **relativo alla profondità** (`assets/…`, `../assets/…`) — coerente col
deploy Pages sotto subpath — e **cache-busting** `?v=<sha256[:10]>` che cambia solo quando
cambia il CSS. I 14 test di contrasto/tema leggono il CSS dal nuovo percorso. Verificatore:
nuovo controllo **[29]** (link giusto in ogni pagina, zero `<style>` inline) → **4.136 pagine
verificate**. Preview servita via HTTP: css 200 (39.666 B), path relativi corretti a ogni
profondità. `verify_site` finale: **0 problemi · 32.867 controlli**.

### 18.5 Stato della coda P0 dopo questo turno

- ✅ P0.5 (CSS esterno), ✅ P0.6 (composizione), ✅ P1.1 (baseline naive) — questo turno.
- Restano in coda: **P0.7** (`benchmark_quote.py` + job mensile, il mercato come riferimento
  misurato — raccomandata opzione A di `docs/19` §1.1), **P0.8** (altre invarianti di
  pubblicazione oltre [3b]/[29]), **P0.9** (contatore richieste per lega), poi i P1
  (`docs/19` §4, sequenza consigliata).

**Prossimo passo**: merge utente della PR → al prossimo daily confermare che `verify_site` in
CI resta a 0 e che il deploy Pages serve il CSS esterno; poi P0.7 (script benchmark quote in
CI mensile) come blocco successivo.
