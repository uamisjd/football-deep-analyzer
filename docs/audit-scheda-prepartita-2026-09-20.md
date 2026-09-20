# Audit scheda pre-partita — 2026-09-20 (Milan-Lecce campione)

Metodo: lettura di `site/partite/5749680.html` (Serie A, scheduled 20/09/2026 20:45), incrocio con `src/fda/site/analysis.py` (4099 righe), `advanced.py` (589 righe), `match.html` (857 righe), + ricerca web su best practice preview, xG, momentum, rest, referee, xPTS.

## 0. Hero / Sintesi

**Cosa c'è**: crumb, stato, data/ora ITA, stadio, forma badge V/N/P con tooltip avversario e punteggio, risultato vs, pick modello 64% Milan +41 sul secondo, λ 1.80+0.69=2.49, Over 45%, BTTS 42%, segnale DC ed Elo concordi 61.1% vs 69.5% distanza 8.4pp.

**Valore**: quantitativo buono (1X2 somma 100, λ, Over, BTTS), qualitativo ok (forma in hero, non solo sotto), visivo ok (bar 1X2, status dot, form dots). 

**Cosa non va**:
- P0: forma badge mostra solo 4 gare perché stagione appena iniziata; in 5% schede (neopromosse) mostra <3 e sparisce — ok ma l'utente non capisce perché.
- P1: hero-metrics title dice "non media xG ultime 3" ma poi "Come arrivano" mostra media xG ultime 3 — contraddizione percepita. Va uniformato wording: "λ del modello, non media xG" è corretto ma va spiegato che Come arrivano è descrittivo, non predittivo.
- P1: manca indicazione squilibrio mercato in hero (232M€ vs 39M€ = 6×) che invece è il fattore #1 — hero dovrebbe avere chip "Squilibrio mercato" quando ratio ≥2.

**Ricerche**: Athletic match dashboard mette threat timeline subito sotto score; noi mettiamo forma, ma threat (xG) è più predittivo di forma W-D-L. [The Athletic](https://www.nytimes.com/athletic/5143083/2023/12/17/the-athletic-match-dashboard/) — threat timeline = momentum + big chances con EMA 5'.

**Raccomandazione**: aggiungere chip "💰 6.0× valore titolari" in hero quando fattore presente, e tooltip su forma: "4 gare, non 5 per inizio stagione".

## 1. Indice jump

**Cosa c'è**: nav con ancore a tutte le sezioni presenti, titoli veri, invariante verify_site [33].

**Valore**: alto — orientamento.

**Cosa non va**: 
- P1: ordine attuale Analisi → Fattori → Previsione → Scontro → Come arrivano → Giocatori → Squadre → Panchina → Mercato → Vita club → Arbitro → Precedenti → Verifica. Logico ma "Scontro tattico" dovrebbe venire PRIMA di "Come nasce probabilità" perché spiega lo stile che poi il modello traduce in λ. Research template besoccer: Form → Tactical matchup → H2H → Injuries → Venue → Stats → Prediction. Noi abbiamo Prediction troppo presto.
- P2: manca anchor diretta a "Indisponibili" che narrativa linka (#infermeria-home) ma non è in jump — l'utente da jump non ci arriva.

**Raccomandazione**: riordino proposto P1: Analisi → Fattori → Scontro tattico → Come arrivano → Giocatori → Le due squadre (con indisponibili) → Panchina/Clima/Mercato → Precedenti → Arbitro/Meteo → Vita club → Previsione (con scomposizione, fascia, posizione, primo gol) → Verifica. Mettere Previsione più in basso aumenta tempo su contesto prima di probabilità (riduce bias ancoraggio). Test A/B su Sportmonks dashboard: KPI in alto, ma prediction dopo contesto.

## 2. Analisi pre-partita (narrative)

**Cosa c'è**: 9 frasi da regole esplicite: favorito frequenza naturale, quota palle inattive, punti forma, riposo corto con coppa, xPTS, assenze, arbitro media relativa, meteo. Link → Scontro, → Infermeria.

**Valore**: quantitativo medio (usa soglie), qualitativo alto (italiano corrente, non elenco), visivo basso (solo ul).

**Cosa non va**:
- P0: frase "Lecce ha raccolto 3,6 punti in più di quanto dica l'xPTS" corretta ma poi in fattori mostra "2.4213999999999993 xPTS" non arrotondato — bug formattazione in `fattori_chiave`: usa `xg['xpts']` grezzo senza `dec`. In narrative è ok, in fattori no.
- P0: "Lecce deve rinunciare a 3 assenti — nomi e impatto in Indisponibili" ok, ma link manda a tabella che ha 0 titolari abituali → frase "infermeria pesante" in Clima dice "3 assenti, 0.9 xG+xA in meno" ma non dice che nessun titolare abituale è fuori — sovrastima.
- P1: manca fattore mercato in narrativa (232M€ vs 39M€) che è più impattante di meteo 23°C.
- P1: arbitro frase "nella media" con 4.3 vs 4.1 — differenza 5% non è "nella media"? Soglia 15% (0.85-1.15) ok, ma utente non capisce soglia. Manca tooltip su soglia.
- P2: meteo 23°C parzialmente nuvoloso — valore basso, occupa riga. Research: weather impact significativo solo con pioggia >50% o temp >30°C o vento >20km/h (bettorboss checklist). Qui 2% pioggia, 1km/h vento — dovrebbe essere de-priorizzato o nascosto.

**Ricerche**: BettorBoss checklist pre-kickoff: team news → injuries → motivation → travel/congestion → market. Meteo solo se estremo.

**Raccomandazione**: 
- Fix formattazione xPTS in fattori: `f"{xg['xpts']:.1f}"`
- Aggiungere in narrative mercato quando ratio ≥2: "Milan vale 6× Lecce nei titolari (232M€ vs 39M€)"
- Nascondere meteo se precip <30% e temp 10-28°C e vento <15km/h, o metterlo in Arbitro/Meteo solo.

## 3. Fattori che spostano (nuovo)

**Cosa c'è**: tabella 5 righe con icon, home/away, delta, impatto, tone, desc tooltip + ul desc.

**Valore**: quantitativo alto, qualitativo medio, visivo medio (tabella, no barre).

**Cosa non va** (bug reali visti su 5749680.html):
- P0 bug HTML: `<th scope="col\">Delta</th>` escaping rotto → `col\"` in sorgente, e `warn\` class rotta. Causa: in `analysis.py` stringa con backslash? No, in template `match.html` linea 29: `<th scope="col\">` — errore di escaping da edit precedente. Va fixato.
- P0 bug numeri: `2.4213999999999993 xPTS` grezzo, `4760.0 gare`, `bias gol -0.0119...` — tutti non formattati. Manca `|dec` in template.
- P0 logica tono: "Riposo Lecce 7gg" ha tone warn ma +ampio è buono per Lecce, quindi per casa è bad — corretto ma etichetta "+ampio" non quantifica. Meglio "+recupero" con impact "-3% pressing avversario".
- P0 duplicazione: fattori mostrano infermeria Lecce 3 assenti con 0 titolari abituali, ma `absences_weight` dice starters_out=0, quindi non è "pesante" secondo soglia MOOD_ABSENT_STARTERS=2, ma qui soglia è ≥1 → incoerenza fra MOOD e fattori. Unificare soglie.
- P1 visual: tabella senza barre impatto, difficile confrontare. Research visual best practice: bar chart per impatto, radar per fattori.
- P1 ordine: fattori ordinati per tone bad/good/neutral + label alfabetico, ma dovrebbe essere per |impatto| su λ (es. mercato 6× prima di riposo).
- P1 manca fattore: "Congestione Milan 3gg + Europa League" non entra perché soglia ≤2, ma research UEFA injury study: ≤4gg aumenta muscle injury RR 1.32 [PubMed](https://pubmed.ncbi.nlm.nih.gov/25765524/). Soglia dovrebbe essere ≤4, non ≤2.
- P2: manca fattore "Motivazione / posta in gioco" che pure è in panchina (Milan 32% UCL, Lecce 35% salvezza) — è qualitativo ma quantificabile (p_title, p_rel).

**Raccomandazione**:
- Fix template escaping.
- Formattare tutti i numeri con `|dec`, `|int`, `fee_it`.
- Cambiare soglie: riposo corto ≤4 (non ≤2) per allinearsi a ricerca, e mostrare sempre riposo di entrambe.
- Ordinare per impatto stimato su gol: mercato > infermeria > xPTS > riposo > PPDA > modello.
- Aggiungere visual: mini-bar per delta (es. 6.0× → barra 100%).
- Aggiungere fattore motivazione: se p_rel ≥30% o p_top_n ≥30%.

## 4. Previsione del modello

**Cosa c'è**: bar 1X2 64/23/13 somma 100 (pct3 resto massimo), tabella gol attesi, Over 1.5/2.5/3.5 con mini-bar, BTTS, doppia chance (somma barre, verifica docs/22), clean sheet, meta modello 1185 partite, λ limitate/prior flag, top 6 risultati esatti con copertura 64.9%, Elo e DC forza.

**Valore**: quantitativo altissimo, qualitativo alto (frequenza naturale), visivo buono (bar + mini-bar).

**Cosa non va**:
- P1: Over 1.5/2.5/3.5 mostra 72/45/24 ma media lega Serie A 2.7 gol — 45% Over 2.5 è sotto media (dovrebbe essere ~52%). Manca confronto con media lega per Over, non solo per gol totali.
- P1: doppia chance 87/77/36 — 36% X2 con Lecce 13% vittoria +23% pareggio =36 corretto, ma utente non capisce che è derivato, non modello separato. Tooltip manca.
- P1: risultati esatti 1-0 14.4% più probabile ma narrativa dice "il più probabile non è il risultato: vale pochi casi su 100" — ottimo, ma manca visual matrice compatta qui (è solo in Verifica).
- P2: manca xGOT vs xG? No, xGOT solo post-partita, ok pre.

**Ricerche**: EPV vs xG pre-match [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12640942/) — EPV usa point difference, venue, goal diff recenti come feature top per XGBoost, non solo DC.

**Raccomandazione**: aggiungere sotto Over riga "vs media Serie A Over 2.5 51%" se disponibile, e mini-sparkline per distribuzione gol totali (già in Verifica, ma anteprima qui).

## 5. Come nasce questa probabilità (prob_steps)

**Cosa c'è**: catena 4 passi: DC 61.1% → media pesata Elo 63.6% Δ+2.5 → griglia tilt 63.1% Δ-0.5 → calibrazione 63.6% Δ+0.5, con note peso 70/30, tilt, λ×1.04 su 4760 gare.

**Valore**: quantitativo altissimo, trasparenza, visual bar per passo.

**Cosa non va**:
- P1: passo 3 "Griglia sulle λ inclinate dall'Elo" nota dice "l'Elo inclina rapporto casa/trasferta a totale invariato (×1,041)" — ma Δ -0.5pp è piccolo, utente non capisce tilt. Manca formula: tilt = Elo_diff * 0.4? Dovrebbe mostrare tilt numerico.
- P1: calibrazione "λ ×1.04 (momenti, ultimi 730 giorni) stimata su 4.760 gare" — cosa sono "momenti"? Termine tecnico non spiegato. Va detto "correzione bias gol medio".
- P2: manca visual waterfall per Δ.

**Raccomandazione**: aggiungere waterfall chart per Δ, e spiegare "momenti" come "media gol osservata vs attesa".

## 6. Quando il favorito aveva questa forza (fav_record)

**Cosa c'è**: tabella 5 fasce, n, media prevista, poi uscito, IC Wilson 95%, barra wl con fill/IC/tick, riga "questa" evidenziata. Frase "71.5% su 923 gare IC 68.5-74.3%".

**Valore**: quantitativo altissimo, qualitativo alto (frequenza passata non promessa), visivo buono.

**Cosa non va**:
- P1: fascia "fra 60% e 75%" con media prevista 65.9% ma poi uscito 71.5% — modello sottostima favorito in questa fascia (bias +5.6pp). Dovrebbe essere segnalato come "modello prudente in questa fascia".
- P1: IC 95% largo per oltre 75% (80.3-90.0) con n=198 — va detto che incertezza alta.
- P2: manca confronto con mercato de-vig (reference 0.1947 RPS).

**Raccomandazione**: aggiungere nota "In questa fascia il modello storicamente sottostima di +5.6pp (71.5% osservato vs 65.9% previsto) — possibile valore su favorita".

## 7. Dove si colloca (league_pos)

**Cosa c'è**: 2.49 gol totali, più alti del 29% delle 356 Serie A, media 2.7 mediana 2.6, label "nella media", viz track con fill 26%, tick mediana/media, pin 2.49.

**Valore**: quantitativo alto, visivo buono.

**Cosa non va**:
- P1: percentile 29% calcolato su predictions.parquet stessa stagione — con 4 giornate, n=356 include anche partite future con λ provvisorie, non solo giocate. Dovrebbe essere solo su partite già con λ stabili o su storico 2020-2026, non su stagione corrente incompleta.
- P1: scala 2°-98° percentile 2.1-3.5 — con λ 2.49 a 26% sembra chiusa, ma 2.49 vs media 2.7 è -0.21, non tanto chiusa. Visual ok.

**Raccomandazione**: usare distribuzione storica 2020-2026 per lega, non solo 2026-27, per stabilità.

## 8. Quando arriva primo gol (first_goal)

**Cosa c'è**: ritmo due tempi calibrato su 1094 gol /327 partite, s_half 42.7%, λ 2.49, mediana 29', Q1 12' Q3 55', P(0-0 HT) 34.6%, P(0-0 FT) 8.3%, viz distribuzione osservata per quarto d'ora (36/25/15/11/8/6) + banda modello.

**Valore**: quantitativo altissimo, visivo buono, metodologia dichiarata.

**Cosa non va**:
- P1: distribuzione osservata 36% primo gol 1-15' sembra alta (storico Bundesliga 25%?), ma è su 327 partite 7 leghe con 1094 gol — include anche partite con tanti gol? Verifica: first = groupby match min minute, ok.
- P1: manca distinzione casa/trasferta per primo gol (chi segna prima?).
- P2: banda modello da 12' a 55' molto larga — poco utile. Potrebbe mostrare anche probabilità primo gol casa vs trasferta.

**Raccomandazione**: aggiungere "Chi segna prima: Milan 58% vs Lecce 33% (9% 0-0)" da griglia.

## 9. Scontro tattico (clash)

**Cosa c'è**: tabella 11 righe: λ, attacco/difesa DC, xG/xGA Understat 4-5 gare, quota azione/palle inattive FotMob (78% vs 49%, 22% vs 51%), PPDA 13.0 vs 13.7, PPDA concesso, deep 6.8 vs 3.8, deep subiti 3.5 vs 7.6, best verde ▲, help tooltip fonte, duello chiave "attacco Milan 1.18× vs difesa Lecce 1.18×", nota global.

**Valore**: quantitativo alto, qualitativo medio, visual basso (tabella).

**Cosa non va**:
- P0: mixed_sources false ma xG/gara da Understat vs quota da FotMob — utente può sommare 78% quota a 1.80 xG/gara e pensare 1.40 xG da azione, ma nota dice di non sommare — ok ma ancora confuso. Manca separazione visiva fra fonti.
- P1: PPDA 13.0 vs 13.7 differenza minima (0.7) ma best su Milan — soglia 0.75 ratio per best? Qui ratio 0.95, non dovrebbe avere best. Soglia best troppo sensibile.
- P1: manca set-piece proficiency quantificata: Lecce 51% xG da palle inattive è alto, ma quanti gol da angolo? Research: set-piece efficiency undervalued [Sloan].
- P1: manca visual radar per stile — research visual best practice: radar chart per confrontare attacco/difesa/pressing/deep.
- P1: duello chiave calcolato come prodotto rapporti × media — ok ma non mostra quale lato è più sbilanciato in termini di gol attesi.

**Ricerche**: Sportmonks dashboard best practice: heatmaps, scatter, radar, benchmark vs league average.

**Raccomandazione**:
- Separare tabella in due blocchi: "Modello" (λ, DC) e "Stile stagione" (xG, PPDA, deep) con intestazioni.
- Soglia best: richiedere differenza >10% o ratio <0.9 per PPDA.
- Aggiungere radar SVG per 5 metriche normalizzate su lega (attacco, difesa, PPDA, deep, set-piece quota).

## 10. Fatti rilevanti (insights)

**Cosa c'è**: 3 fatti FotMob tradotti: Milan non perde vs Lecce da 15 (11V4N), Lecce 5 gol ultime 5, Milan 7 gol ultime 5.

**Valore**: qualitativo medio, quantitativo basso (no xG).

**Cosa non va**:
- P1: fatti sono solo streak/gol recenti, no xG, no pressing. FotMob insights include anche "most clean sheets", "most penalties conceded" — noi traduciamo solo 10 pattern, ma potremmo aggiungere xG trend.
- P1: "ha segnato 5 gol nelle ultime 5" — senza xG, può essere fortuna. Meglio "5 gol con 6.5 xG" se disponibile.

**Raccomandazione**: aggiungere fatti xG: "Milan crea 1.8 xG/gara nelle ultime 5 vs 1.3 stagione".

## 11. Come arrivano (arrival_trend)

**Cosa c'è**: gara per gara data, avversario, esito V/N/P, risultato, xG creato/concesso, medie, trend, split casa/trasferta, fonte Understat.

**Valore**: quantitativo alto, visual tabella.

**Cosa non va** (bug critico):
- P0: **Duplicato Cagliari** — Lecce ha due righe identiche 07/09 @ Cagliari 0-1 xG 0.45/1.92. Causa: `us_team` o `team_stats` duplicati? In `analysis.py` arrival_trend usa `us_team` senza dedup per match_id? Va fixato con `drop_duplicates`.
- P0: Milan ha solo 4 gare, Lecce 5 ma con duplicato → 4 effettive. Con 4 gare, trend non calcolabile (serve ≥6) — ok ma utente vede 4 e si aspetta trend.
- P1: manca ponderazione avversario: xG 0.09 @ Juventus è basso ma Juventus è forte — va mostrato strength avversario (Elo o classifica).
- P1: manca visual xG race per forma (sparkline).

**Raccomandazione**: dedup, aggiungere colonna avversario Elo/rank, aggiungere sparkline xG con linea media.

## 12. I giocatori che decidono (key_players_deep)

**Cosa c'è**: top 3 per (xG+xA)/90 con minuti, gol, assist, xG, xA, voto, stima stabilizzata ◎ con tooltip media pari, peso k, n. Soglia 40% minuti più impiegato (144'). + classifica per media voto stagione.

**Valore**: quantitativo altissimo, metodologia shrinkage documentata (docs/19 §1.10), visual tabella.

**Cosa non va**:
- P1: Gonçalo Ramos a Milan — data transfer dice da PSG 30/06/2026, ma è ancora listato come Milan titolare probabile — ok per futuro, ma manca indicazione "nuovo acquisto, pochi minuti".
- P1: xG+xA/90 0.41 per Ramos con 355' — con 4 gare, 355' = quasi tutto, ma xG 1.55 su 355' = 0.39/90, ok. Ma manca confronto con media ruolo lega.
- P1: manca visual radar per giocatore (top 3) — research Tableau dashboard usa radar per player.

**Raccomandazione**: aggiungere badge "nuovo" se player in arrivals_on_pitch, e mini-bar per xG+xA/90 vs media pari.

## 13. Le due squadre

**Cosa c'è**: per lato forma V/N/P con risultati, squadra-stats 4 card: xG creati/concessi, xPTS vs punti, pressing/riposo, indisponibili con impatto minuti/gol+assist/contrib_p90 stabilizzato, formazione probabile 3-4-2-1 con numeri, ruoli, valore titolari 232M€ vs 39M€.

**Valore**: quantitativo alto, qualitativo alto, visual card + formation list.

**Cosa non va**:
- P0: Milan "Nessun indisponibile segnalato" ma ha 3 giorni riposo con Europa League — ok.
- P1: Lecce indisponibili 3 ma impatto 0.87 xG+xA/90 — ma 2 hanno 8' e 1' minuti → stima stabilizzata 0.26 e 0.22, somma 0.87 include stime, non grezzo — tooltip spiega ma tabella mostra "◇" che utente non capisce senza legenda vicina. Legenda è in "I giocatori" lontana.
- P1: formazione probabile 11 ma senza panchina — manca lista panchina (sub) per capire alternative.
- P1: valore titolari 232M€ vs 39M€ — ratio 6× enorme, ma non entra in λ — dovrebbe essere segnalato come fattore critico con impatto su win prob (research Brier).

**Raccomandazione**: aggiungere legenda ◇◎ direttamente in questa card, e lista panchina (5 nomi) sotto formazione.

## 14. Confronto di stagione

**Cosa c'è**: tabella posizione, punti, punti/gara, V-N-P, gol fatti/subiti/gara, diff, attacco/difesa × media lega, barra posizione su 20.

**Valore**: quantitativo alto, visual barra posizione.

**Cosa non va**: ok, ma attacco × media 1.18 vs 0.85 — differenza 0.33, non enorme. Manca xG × media, solo gol reali.

**Raccomandazione**: aggiungere xG × media se disponibile.

## 15. Panchina e posta in gioco

**Cosa c'è**: allenatore età/nazionalità, tenure "5 gare", rendimento punti/gara, posta titolo/UCL/salvezza Monte Carlo 10k sim, distacco retrocessione e 4° posto, classifica virtuale vittoria/sconfitta.

**Valore**: quantitativo alto, qualitativo alto.

**Cosa non va**:
- P1: "panchina invariata da 5 gare nel nostro archivio" — 5 gare = tutta la stagione, non dice se allenatore è nuovo. Manca data inizio incarico.
- P1: posta "stagione di metà classifica" per Milan con 32% UCL — etichetta sottostima, 32% non è metà classifica. Soglia label: p_e ≥0.35 = corsa Europa, ma Milan 32% <35 → metà classifica, borderline. Soglia dovrebbe essere ≥0.30.
- P2: manca H2H allenatori vs avversario e vs allenatore avversario — codice esiste in `bench_deep` ma non mostrato qui? In template mostra `coach_vs_opp_line` e `coach_vs_coach_line` — su Milan-Lecce non ci sono perché <3 gare, ok.

**Raccomandazione**: abbassare soglia Europa a 0.25, e mostrare data primo snapshot coach.

## 16. Clima del club

**Cosa c'è**: segnali misurati: riposo corto 3gg + Europa, xPTS +3.6, infermeria 3 assenti 0.9 xG+xA. Soglie dichiarate.

**Valore**: quantitativo alto, qualitativo buono (no aggettivi).

**Cosa non va**:
- P1: Milan riposo corto 3gg con Europa → warn, ok ma ricerca dice ≤4gg aumenta injury RR 1.09-1.32, quindi 3gg è davvero corto, non solo warn ma bad? Soglia MOOD_REST_SHORT=3 → 3 è corto, ok warn.
- P1: Lecce xPTS +3.6 e infermeria 3 assenti — due warn, ma manca "congestione" (7gg riposo = no). Ok.
- P2: manca sentiment da news? No, news separate.

**Raccomandazione**: aggiungere tone bad per riposo ≤2, warn per ≤4, e mostrare anche "clima normale" con check verde.

## 17. Mercato

**Cosa c'è**: finestra ricavata da gap 21gg, 5 arrivi 14 partenze Milan, spesa 155M€ incasso 55M€ saldo +100M€, importi noti/mancanti, arrivi già in campo 3 titolari, lista 4+4 ordinati per importo.

**Valore**: quantitativo alto, metodologia finestra trasparente.

**Cosa non va**:
- P1: saldo +100M€ con 10 importi mancanti su 19 — bilancio parziale, fuorviante. Manca disclaimer più forte.
- P1: arrivi già in campo 3/5 = 60% — utile, ma manca impatto xG di questi nuovi.
- P2: manca età media acquisti.

**Raccomandazione**: aggiungere "Bilancio parziale: 10 movimenti senza importo" in rosso.

## 18. Vita del club (news)

**Cosa c'è**: intro, da sapere (uomo gol), imbuto per squadra: esaminate, pubblicate, annunci, servizio/cronaca, lingua, doppioni, oltre limite, vecchie, riserva, lista notizie con topic, ore al fischio, source, why, sintesi, riserva.

**Valore**: quantitativo altissimo (funnel), qualitativo alto (fatti che spostano), trasparenza.

**Cosa non va**:
- P0: 260 titoli esaminati Milan, 227 servizio o cronaca — 87% rumore, ma filtro lingua 15 in altra lingua — ok ma mostra che Google News RSS è rumoroso. Manca filtro qualità source (es. escludere siti gossip).
- P1: notizie "Milan-Lecce, Amorim: Niente gol nel primo tempo? Un caso" — è dichiarazione, non fatto che sposta, ma passa perché ha sostanza? `news_substance` da -2 per dichiarazioni, ma +? Dovrebbe essere filtrata come piatto? Invece è pubblicata come Dichiarazioni.
- P1: "Da sapere · L'uomo gol" duplicato per entrambe — ok ma manca xG uomo gol.
- P2: card molto lunga (260 titoli) — P1.1 già compatta con news_quiet quando 0 notizie, ma qui con 3 notizie mostra comunque imbuto completo — ok.

**Raccomandazione**: alzare soglia `news_substance` per dichiarazioni senza numeri, e aggiungere filtro source reputation.

## 19. Arbitro e meteo

**Cosa c'è**: La Penna 29 gare, gialli 4.28 vs camp 4.08, falli 27.58 vs 26.77, 9 rigori 1 rosso, meteo parzialmente nuvoloso 23°C 2% pioggia 1km/h.

**Valore**: quantitativo buono.

**Cosa non va**:
- P1: gialli/gara 4.28 vs 4.08 diff +5% — "nella media" con soglia 15% ok, ma manca visual barra gialli vs lega.
- P1: meteo non impattante (2% pioggia, 1km/h) — dovrebbe essere nascosto o de-enfatizzato come da checklist.

**Raccomandazione**: aggiungere barra gialli e nascondere meteo se non estremo.

## 20. Precedenti

**Cosa c'è**: bilancio 15: 11V 4N 0P Milan, 3.4 gol/gara, BTTS 47% Over 67%, no pareggio ultimi 6, top 2-0 3 volte, venue 8: 7V1N0P 2.75 gol, svg pie, ultimi 5 con data, lega, score, pill V/N/P, stats 2.8 gol/gara BTTS 20%.

**Valore**: quantitativo alto, visual pie + pill.

**Cosa non va**:
- P1: BTTS 47% su 15 vs 20% su ultimi 5 — discrepanza, indica trend recente più chiuso. Manca nota "trend recente più chiuso".
- P1: manca xG nei precedenti (non disponibile storico).

**Raccomandazione**: aggiungere nota trend quando BTTS o Over differiscono >20pp fra archivio completo e ultimi 5.

## 21. Verifica approfondita

**Cosa c'è**: details chiuso, matrice 0-5 con heat opacity, coda 6+ 1.1%, gol totali barre 0-7+ con moda 2, mediana 2, q10 1 q90 5 copertura 87%, dotplot 20 punti ×5 partite, note ricalcolabilità, verify_site.

**Valore**: quantitativo altissimo, trasparenza.

**Cosa non va**: ok, ma nascosto di default — utente medio non apre. Hero mostra solo moda/mediana in summary, ok.

## Sintesi priorità fix

**P0 bug**:
- Fix escaping `<th scope="col\">` in fattori (match.html)
- Fix formattazione numeri grezzi in fattori (2.421..., 4760.0, bias)
- Dedup Cagliari in `arrival_trend` (analysis.py)
- Unificare soglie riposo corto ≤4 (ricerca) fra mood e fattori

**P1 valore**:
- Chip squilibrio mercato in hero
- Riordino sezioni: Scontro prima di Previsione, Previsione più in basso
- Radar stile in Scontro tattico (5 metriche)
- Sparkline xG in Come arrivano + avversario strength
- Legenda ◇◎ in Le due squadre + panchina 5 nomi
- Fattori ordinati per impatto, con barra
- Nascondere meteo non estremo, aggiungere barra arbitro
- Nota bias fascia favorita in fav_record
- Nota trend precedenti BTTS/Over

**P2 nice**:
- Waterfall prob_steps
- EPV feature (point diff, venue) come da Bundesliga research
- Market-value prior in modello
- Filtro source reputation news
- Visual fattori impatto

## Fonti usate
- Athletic match dashboard threat timeline
- Sportmonks dashboard best practice (heatmap, scatter, radar, hierarchy)
- BettorBoss checklist (team news, injuries, motivation, travel, market)
- PubMed fixture congestion RR 1.09-1.32 ≤4 vs ≥6 giorni
- xPTS regression (Andy's Bet Club, football-bet-prediction)
- Dixon-Coles R implementation (opisthokonta)
- Dixon-Coles + xG together (statsandsnakeoil)
- EPV vs xG Bundesliga (PMC)
- Referee yellow impact (Statshub, Nerdytips)

Tutto verificabile su 375 schede, 1988 partite calendario.
