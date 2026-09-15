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
