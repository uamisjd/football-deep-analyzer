## 2026-10-17 pomeriggio — Controllo delle schede squadra: cinque difetti corretti

Ricontrollando le 132 schede sui dati correnti sono emersi cinque difetti reali, tutti
corretti nello stesso intervento (dettaglio in `docs/114` §4bis):

1. le pagine `squadre/` non accendevano la voce «Squadre» nel menu (nuovo gate `[55]`);
2. la distinta veniva chiamata «ufficiale» anche per `lastStarting11`/`unavailable`:
   **18 squadre su 132** con l'etichetta sbagliata, ora «ultima distinta» con la spiegazione;
3. la riga «in corso» dello storico non coincideva con la testata (fino a 9 gare contro 8)
   e il rango contava solo i punti (**46 squadre su 132** con posizione diversa da quella
   ufficiale): ora la stagione in corso viene dalla classifica e le passate ordinano per
   punti, differenza reti e gol fatti;
4. una gara iniziata senza finale non compariva in nessuna lista della squadra: nuova card
   «Da verificare» (17 gare il 17/10);
5. le notizie non erano in ordine di data: ora la più recente sta in cima.

`[52]` ora verifica anche la coerenza storico↔testata (1.056 cifre su 132 squadre), `[55]`
verifica il menu. Gate locali dopo le correzioni: `pytest` **1.063** · Ruff pulito · build
532 / 2.364 / 3.801 / 132 · `verify_site` **269.577 controlli · 0 problemi** (60 oracoli) ·
`parita_schede` nessuna differenza · `resa_375` 31.286 misure · 0 problemi.

## 2026-10-17 — Pagine squadra, contatore dei giocatori corretto e Accuratezza a linguette

**Cosa è cambiato (dettaglio e misure in [`docs/114`](114_pagine_squadra_2026-10-17.md)).**

1. **132 schede squadra + indice** (`squadre/<id>.html`, `squadre/index.html`): classifica, forma,
   rendimento casa/trasferta, proiezione di stagione, indisponibili, formazione, rosa e panchina,
   mercato, notizie, prossime gare, storico. Nessuna fonte nuova: stessi Parquet e stesse
   funzioni della scheda partita (`MatchAnalysis`, `PlayerCatalog`, `season_sim`). Link solo
   verso le schede gara realmente generate. Voci in menu e footer; nomi delle squadre cliccabili
   nell'hero delle schede gara e nelle schede giocatore; 133 URL in sitemap.
2. **Contatore dei giocatori** corretto: il build sommava righe dei tabelloni e schede
   (`3.801 + 3.801`) e stampava «7.602 giocatori»; ora stampa **3.801**, cioè i file in
   `site/giocatori/` meno 7 tabelloni di lega e indice. Le occorrenze storiche di 7.602 nei
   documenti datati restano come erano (erano il numero stampato), il briefing è aggiornato.
3. **Accuratezza a linguette**: `accuratezza.html` e `laboratorio.html` hanno la stessa barra di
   sezione con `aria-current`; il laboratorio è anche nel footer. Nuova card «Stabilità dei
   mercati nel tempo» con i nove mercati di `mercati_monitor` (5.960 gare fuori campione, due
   metà, leghe in accordo, verdetto): 2 mercati fuori intervallo, 0 «strutturali» al 17/10 — il
   modello non si tocca. La card sparisce se il Parquet manca.
4. **Gate**: `[52]` schede squadra ↔ `fotmob_standings` (660 cifre su 132 squadre), `[53]` 1X2
   della prossima gara ↔ barra della scheda partita (120 gare), `[54]` proiezioni ↔ `season_sim`
   (264 stringhe), tutti indipendenti; `[34]` aggiornato all'hero con il nome-link.

**Misure locali (dati del 17/10/2026).** `pytest` **1.059** (+5 di pagina squadra) · Ruff pulito ·
build **532 partite / 2.364 fixture / 3.801 schede giocatore / 132 squadre** in 8m16 ·
**4.483 HTML / 167 MB** · `verify_site` **269.056 controlli · 0 problemi** (59 oracoli, 36
indipendenti) · `parita_schede` nessuna differenza · `resa_375` **31.288 misure · 0 problemi**.
Il gate browser non è eseguibile in questa sandbox (nessun Chromium scaricabile): le nuove
pagine sono state aggiunte a `scripts/browser_smoke.mjs` e la CI della PR le ha verificate
(`test`/`site`/`browser` verdi su head `051c370`, PR
[#130](https://github.com/uamisjd/football-deep-analyzer/pull/130), MERGEABLE/CLEAN).

**Limiti dichiarati.** Le notizie italiane della prima squadra coprono 63 squadre su 132: 42
hanno il bollettino con i criteri della scheda gara, 21 la rassegna più larga (dichiarata in
pagina), 69 nessuna voce — è copertura delle fonti, non una quiete dimostrata. Nessun fetch
nuovo, diritti delle fonti invariati. 👉 La PR unica di sessione è [#130](https://github.com/uamisjd/football-deep-analyzer/pull/130),
con tutti i check verdi; il merge resta esclusivamente al committente.

## 2026-10-17 — PR #129 completa, audit docs/112 e correzione prudenziale dello stato gara (00:50 UTC)

**Stato GitHub dal vivo:** PR tecnica [#129](https://github.com/uamisjd/football-deep-analyzer/pull/129), head `2f10d42`, OPEN e MERGEABLE. Sul suo head i run #38987085075 hanno `test`, `site` e `browser` tutti SUCCESS; il run duplicato #38985411806 sul precedente head `1000469` è anch’esso tutto verde. Nessun merge eseguito: resta al committente. La PR documentale #128 è fusa. Daily/deploy #38983052624 riuscito alle 23:58 UTC.

**Produzione osservata:** homepage rifetchata dopo il deploy: sabato 17/10, 24 gare, 6 campionati, 24/24 modellate, 0 live e 24 in programma. La pagina Risultati pubblica ancora 59 gare, con ultimi gruppi visibili al 10–12/10 e nessuna delle cinque partite del 16/10. Il rollover alla nuova giornata ha tolto i match problematici dalla vista «Oggi», non dimostra che i risultati arretrati siano stati riconciliati. Coda di freschezza ancora valida.

**Intervento della PR #129:** unica riconciliazione stato/punteggio per liste e schede; dopo kickoff >30 min se ancora programmato o >105 min se live/intervallo senza finale → `unverified`, nessun punteggio parziale; homepage e scheda avvertono, Risultati elenca anche le gare incerte. Gate indipendente [51] controlla card, scheda, risultato e link. Nessuna fonte nuova, richiesta extra o modifica del modello.

**Gate locali sul commit con dati di main aggiornati:** 1.052 test; Ruff/pip check puliti; pip-audit requirements e npm audit senza vulnerabilità note; build 532 / 2.364 / 7.602 (4.365 file, 157.890.385 byte); `verify_site` 264.436 controlli / 0 problemi, [51] 151 card; parità 92 schede; resa 375 px 29.965 misure / 0 problemi. La CI browser è passata su #129. Report, ricerca e limiti: [`docs/112`](112_revisione_totale_2026-10-16.md); audit precedente [`docs/111`](111_revisione_totale_2026-10-16_post_merge.md).

**Decisione aperta:** autorizzazioni/riuso di FotMob, Understat, ESPN e Football-Data.co.uk/mirror non decisi; non ampliare i fetch. `unverified` è una protezione prudenziale basata sul tempo dal kickoff, non una misura dell’età cache; obiettivo futuro resta `last_fetched_at`/`cache_age` per endpoint. 👉 Tutto verde: è il momento di fare Merge (PR #129). Il merge resta esclusivamente al committente.

## 2026-10-16 — Revisione post-merge (docs/111), snapshot precedente alle 22:41 UTC

**Stato storico:** al controllo delle 22:05 UTC la homepage Pages era ancora stale. PR #128 era aperta e i due run intermedi `site` rossi; successivamente #128 è stata fusa alle 23:08 UTC e il daily #38983052624 ha ridistribuito alle 23:58 UTC. Vedi l’aggiornamento attuale sopra e il report [`docs/112`](112_revisione_totale_2026-10-16.md). Audit storico completo: [`docs/111`](111_revisione_totale_2026-10-16_post_merge.md).

**GitHub e produzione (controllati dal vivo):** PR #127 fusa alle 19:48:51 UTC, merge commit `0ae98bc`; daily [#38957677291](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38957677291) e CI post-merge [#38957677296](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38957677296) verdi; issue #126 chiusa. Il daily [#38968833035](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38968833035) ha completato `run`/`deploy`/`notify` con successo. La PR solo documentale [#128](https://github.com/uamisjd/football-deep-analyzer/pull/128), head `bbe6c52`, resta aperta e non fusa: due run intermedi (#38968370499, #38971973093) avevano `site` rosso, ma il più recente [#38975278301](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38975278301) ha `test`/`site`/`browser` tutti passati. L’API riporta `MERGEABLE`; nessun merge eseguito.

La homepage Pages, rifetchata alle 22:05 UTC, dice ancora `AGGIORNATO 23:26` ora italiana e mostra **5 partite / 5 campionati / 5 su 5 modellate**; lo stato resta **1 in corso / 4 in programma**, Heerenveen–Excelsior **0–0** in corso e Frankfurt–Köln (calcio d’inizio 20:30) come prossimo avvio, benché già trascorso. È uno snapshot statico, non un feed live: nessun nuovo deploy dopo il daily #38968833035 e il dato stale persiste. Dettagli e cinque incontri sono in docs/111 §§2, 9–10.

**Discordanza fra fonti, P1:** nel run delle 19:49–19:50 UTC ESPN aveva cinque eventi in corso: Heerenveen–Excelsior 4–0 al 90′, Frankfurt–Köln 0–0 al 59′, Frosinone–Sassuolo 3–2 all’intervallo, Le Mans–Toulouse 0–1 al 48′, Deportivo–Levante 0–0 all’intervallo. `fixtures.parquet` ne mostrava uno live (Heerenveen 0–0) e quattro programmati; il builder usa `fixtures.status`, mentre `espn_events` è una tabella separata e non riconciliata.

**Causa tecnica più probabile, ma non timestampata per endpoint:** nel daily #38957677291 la cache Actions `fda-http-38944906063` (creata alle 18:20:42 UTC) è stata riutilizzata alle 19:49:41; `source_status` registrava FotMob **0 richieste HTTP** ed ESPN scoreboard **3 per lega**. Nel daily successivo #38968833035, il sito è rimasto stale; `stato.html` mostra 10–12 richieste aggregate per riga FotMob e 3 per scoreboard ESPN. La cache `fda-http-38957677291` è stata riutilizzata alle 21:22:19 UTC e il nuovo archivio `fda-http-38968833035` creato alle 21:29:52. I contatori FotMob aggregano più endpoint: non provano che la lista fixture sia stata ricaricata né danno l’età del payload. TTL fixture FotMob **6 h**, TTL scoreboard ESPN **1 h**; manca `last_fetched_at` per file/endpoint. Cache ancora plausibile, causa precisa non dimostrata. Non aumentare il polling e non usare ESPN come fallback finché i diritti non sono chiariti.

**Gate locali:** verifica iniziale: 1.047 test, Ruff e `pip check` puliti; build 506 / 2.364 / 7.602; `verify_site` 247.770 controlli, 0 problemi; parità 66 schede; resa 375 px 28.886 misure, 0 problemi. Ripetizione dopo il primo CI rosso, con i dati di `HEAD`: 247.771 controlli, 0 problemi; parità senza differenze; resa 28.886 misure, 0 problemi. Con il solo aggiornamento `prospettico.parquet` di `origin/main` (`b3d0cc8`), più vicino alla base del PR: build 527 / 2.364 / 7.602; `verify_site` 260.765 controlli, 0 problemi; parità 87 schede, nessuna differenza; resa 375 px 29.738 misure, 0 problemi. I due precedenti errori CI `site` restano inspiegati, ma il run #38975278301 ha poi passato tutti i check sull’head corrente. Cartella sito locale 154.168.061 byte (misurata sulla build precedente, 4.324 HTML / 4.339 file). Repository API `size=754527 KB` al controllo delle 20:06 UTC: delta +92 KB rispetto al dato di docs/110, non un trend.

**Rettifica meteo:** nel run le righe `openmeteo:*` hanno 0 richieste/0 righe perché FotMob aveva già fornito il meteo delle gare future. `coordinate 0` conta le gare saltate per coordinate mancanti, quindi qui nessuna; `match_info` ha coordinate, descrizione, temperatura e vento in 507/507 righe, precipitazione in 90/507. Open-Meteo non è stato usato come fallback nel run. Vedi docs/111 §5.

**Modello:** accuratezza live 218 gare, 137 con ricetta corrente, RPS 0,1990 vs naive 0,2267; walk-forward 5.960 gare, 0,1987 vs 0,2313. Over 2,5, Over 3,5 e BTTS fuori dall’intervallo al 95% nel campione live: monitorare, non ritoccare sulla sola base di 218 gare.

**Rischio fonti / decisione utente:** FotMob FAQ vieta servizi automatici/uso sistematico; `understat.com/robots.txt` disallowa i crawler; i termini Disney italiani (2014, includono ESPN) vietano accessi automatizzati senza permesso scritto, ma l’applicabilità allo specifico endpoint ESPN resta incerta; Football-Data.co.uk limita l’uso dichiarato. Non è un parere legale. Alternative (OpenLigaDB ODbL comunitaria, Football-Data.org gratuito ma ritardato, OpenFootball CC0 per calendari) non sono un sostituto live 7/7 validato. Rispettare il vincolo di costo zero; non ampliare i fetch prima di autorizzazione o migrazione decisa.

**Prossimo:** i check correnti della PR #128 sono verdi su `bbe6c52`; la decisione di merge resta all’utente. I due run intermedi rossi hanno log non recuperabili (download `EOF`); se si vuole indagare la causa, aprire i raw logs in GitHub UI. Separatamente, serve una decisione documentata sulle fonti e sul requisito live; poi, solo su autorizzazione, misurare `last_fetched_at`/`cache_age` per endpoint e coprire la discordanza con test/gate misurabili (regola B.10). Verificare in UI GitHub le protezioni e le scansioni, che non risultano verificabili via API. Ogni merge resta all’utente.

## 2026-10-16, 18:32 UTC — Revisione pre-merge (docs/110; snapshot storico) e fix del daily #286/#287

Verifica da zero il 16/10, base `main` `8715a41`; aggiornamento live alle **18:32 UTC / 20:32 CEST**.
I daily [#286](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38918710431) e
[#287](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38944906063) sono entrambi
falliti al gate [49] sulla scheda 5749704; il #287 si è concluso alle 18:24 UTC con `verify_site`
fallito e il deploy saltato. Il commento automatico più recente sull’issue
[#126](https://github.com/uamisjd/football-deep-analyzer/issues/126) riporta le stesse due
anomalie: sommario Sassuolo senza conteggio dei marcatori e voce «Frosinone-Sassuolo, protesta
della Curva» non marcata contro l’atteso.

Ultimo deploy Pages: 09:19:39 UTC (`c348074`); homepage ferma alle 11:07 CEST, 5 partite, 5/5
modellate, fonti fino a circa 11:01. Alle 20:32 CEST la homepage indica 0 partite in corso e 5 in
programma, ma Heerenveen–Excelsior (orario previsto 20:00, già trascorso) risulta ancora «In
programma» e la scheda «Analisi pre-partita»: stato pubblico non aggiornato rispetto all’orario.

**Causa riprodotta:** il dedup «Vita del club» è condiviso fra casa/trasferta, ma i titoli `visti`
per i due Climi erano separati; la verifica [49] usa invece i titoli della pagina intera. Fix in
`src/fda/site/analysis.py`: unione dei titoli primari di entrambi i bollettini per entrambi i
Climi; regressione in `tests/test_site.py`, rossa prima del fix (un marcatore invece di due), verde
dopo. Dati/collettori non modificati. Il run #287 ripete gli stessi messaggi su Sassuolo: il fix
non è ancora su `main`.

**Gate locali dopo il fix:** Ruff e `pip check` verdi; **1.047 test**; build 506 / 2.364 / 7.598;
`verify_site` **247.419 controlli, 0 problemi**; parità 66 schede; resa 375 px **28.857, 0**.
Browser Playwright non eseguito localmente perché manca Chromium. La CI della PR sul head
`4ef6f133a355f0f794b2407efbc76455b43792a7` è verde per `test`, `site` e `browser` (run
[#38941239498](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38941239498) e
#38941230956). PR #127 aperta/`MERGEABLE`; nessun merge eseguito. Modello: γ 1,12 su 5 risultati,
ΔRPS +0,005851, IC [−0,005229; +0,016406], 1/4 leghe; nessuna promozione, `dc_elo_prod` invariato.

**Ricerca fonti:** FAQ FotMob contro servizi automatici/uso sistematico; Understat `robots.txt`
`Disallow: /`; pagina Football-Data.co.uk limita l’uso previsto a individui privati e dichiara
contro prodotti di data-training basati su bot/scraper/AI. Nessun collettore disattivato; alternative
solo parziali, decisione utente aperta. Dettagli e link in [`docs/110`](110_revisione_totale_2026-10-16.md).

**Copertura meteo — rettifica post-merge:** le righe `openmeteo:*` hanno 0 richieste/righe perché FotMob fornisce già il meteo delle gare future. `coordinate 0` significa zero gare saltate per coordinate mancanti, non zero coordinate disponibili; la fotografia `match_info` successiva ha lat/lon in 507/507 righe. La precedente raccomandazione di reperire coordinate per questo motivo è ritirata; la sonda settimanale su un punto non misura la copertura generale. Dettagli in [`docs/111`](111_revisione_totale_2026-10-16_post_merge.md) §5.

Il cron configurato è 04:07, 10:11, 14:17, 18:23 e 21:30 UTC; il #287 è partito alle 18:07,
prima del nominale 18:23. Prossimo cron nominale 21:30 UTC, non garanzia d’avvio puntuale.
Repository `diskUsage` 754.435 KB (+160 KB rispetto alla misura precedente 754.275 KB; differenza
singola, non proiezione); alert Dependabot disabilitati secondo API, stato branch protection e
scansioni non verificabile con i permessi dell’integrazione. Il merge resta responsabilità
esclusiva dell’utente.

## 2026-10-15 — PR #124 fusa (revisione 15/10 + misura della crescita); registrazione del merge #123

Ordine utente: **«ok procedi»**, dopo la proposta esplicita dell'agente di chiudere le due PR
aperte del giro (#123 e #124). **PR #124** fusa alle **12:39:54 UTC**, merge commit
**`79a97c4222158eb22dea559d8423f50b64eb3414`** (deroga in `docs/13` §9.37, insieme alla §9.36
per la #123).

Prima del merge: `test` 3m37s · `site` 10m11s · `browser` 4m25s tutti **SUCCESS** su `6c9f8d8`,
PR `MERGEABLE`/`CLEAN`, `git status --porcelain` vuoto, `origin/main..HEAD` = i **3** commit della
PR. Contenuto entrato in `main`: `docs/109` (revisione totale con gate rimisurati), la misura
riproducibile della crescita (`scripts/crescita_repo.py` + 12 test), i conteggi dell'indice in
`README` e nel briefing, la registrazione del merge della #123 e la deroga §9.36.

Il push del merge ha avviato `tests` e `daily` su `main` (`79a97c4`, 12:39:58 UTC): il contenuto
include `scripts/` e `tests/`, quindi **non** è coperto da `paths-ignore`.
**Esito misurato:** `tests` verde e `daily` [`38736379599`](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38736379599)
**success** con `run`/`deploy`/`notify` riusciti (12:39:58 → 12:59:18 UTC). Il run ha committato
**solo il registro** (`332817e`, 12:58 UTC): è il comportamento corretto della politica di
`docs/105`, perché erano passate **14h50m** dalla fotografia del 14/10 22:08 (< 24 ore) e l'ora UTC
era 12 (< 20). La fotografia completa di oggi resta attesa al **run ≥20 UTC**, non a questo.
Nessuna previsione è stata scritta come fatto: la prima stesura di questo blocco la dava per
probabile e la misura l'ha smentita, quindi è stata corretta prima del merge.

## 2026-10-15 — PR #123 fusa dall'agente su ordine «ok procedi» (deroga §9.36)

Su richiesta dell'utente (*«ok procedi»*, dopo la proposta esplicita di chiudere le due PR aperte)
e con **tutti i check verdi** su `45c6102` (`test` 3m14s · `site` 6m21s · `browser` 4m34s, tutti
SUCCESS), PR `MERGEABLE`/`CLEAN`, `git status --porcelain` vuoto, eseguito
`gh pr merge 123 --merge`: **PR #123 fusa il 2026-10-15 alle 12:12:55 UTC**, merge commit
**`6b456319543c604f8fd77cdd2f6f68666c0d27f5`**. Contenuto: registrazione del merge di #122
(`docs/13` §9.35) e cima di `STATO.md`. Deroga registrata in `docs/13` §9.36, limitata a questa PR.
Il push del merge **non** avvia run su `main`: il commit è di soli documenti e `tests.yml` e
`daily.yml` hanno `paths-ignore: docs/**`.
**Prossimo:** fusione della **#124** (questa sessione), poi daily serale ≥20 UTC.

## 2026-10-15 — Revisione totale `docs/109`: gate rimisurati da zero, crescita misurata

Richiesta utente: *«controlla vita morte e miracoli del progetto e del sito… c'è una pr aperta
controlla»*. Relazione completa: [`docs/109`](109_revisione_totale_2026-10-15.md).

**Verificato dal vivo (`gh` + pagine):** `main` `11186b6` alle 10:38 UTC (poi `6b45631` col
merge della #123); **0 issue**, **1 PR (#123**, solo documenti, `MERGEABLE`, `test`/`site`/
`browser` SUCCESS — fusa alle 12:12:55, vedi il blocco sopra; la PR di questo giro è la **#124**);
**7 daily verdi di fila** dal 14/10 13:03;
ultimo deploy `7366ae5` del 15/10 10:30:45 UTC con `run`/`deploy`/`notify` verdi; home coerente con
la sosta (0 partite il 15/10, **5 il 16/10**, 24 il 17/10 e 18/10); repo GitHub **750.155 KB
(≈732,6 MiB)**.

**Verificato in locale (rimisurato, non citato):** **1.034 test** in 141,95 s (= **1.046** con i 12 test di `scripts/crescita_repo.py` aggiunti nel giro) · Ruff 0 · `pip check`
ok · build **499 / 2.364 / 7.626** · `verify_site` **242.987 controlli · 0 problemi** (55 oracoli:
32 indipendenti, 20 misti, 3 specchi) · parità **59 schede, nessuna differenza** · resa 375 px
**28.597 misure · 0 problemi** · sito 4.344 file / 157 MB / 4.328 URL. Verifiche indipendenti:
**59/59** pre con tutte e 8 le sezioni, **288** schede con `#verifica` **e** voce d'indice
(**0** disallineate → invariante [33] regge, la correzione di `docs/108`/PR #122 è live), **0**
«Arbitro da definire» sulle pre, stampa in lingua originale **9/9** NED1 + **1/1** POR1 (44 titoli),
archivio notizie con **484 `pt`** e **444 `nl`** → la voce di coda di `docs/107` è chiusa.

**Crescita (prima misura della politica A):** una fotografia completa al giorno (4,6 e 5,3 MiB),
registro a ogni run; byte scritti al giorno 33–39 MB (12–13/10) → **10,8 MB** (14/10) → 1,3 MB
(15/10, parziale); dimensione GitHub **+5,8 MiB in 24 h (−77%** contro i 24,8 MB/giorno di
`docs/105`). I 1 GB raccomandati (non bloccanti) arrivano **a inizio dicembre**; opzioni B/C/D in
`docs/109` §4, **decisione dell'utente**. Il peso della storia è `data/processed` (798,6 MiB su
911,3 = 87,6%); i 18 rami `arena/*` non fusi pesano solo 3,2 MiB.

**Modelli:** test prospettico γ 1,12 con **5 gare valutate** su 200 (ΔRPS +0,0059, IC a cavallo
dello zero, 1 lega su 4) — si accumula dal 16/10. Confronto con la letteratura: il nostro RPS
0,1987/0,1990 è nella banda attesa per un Dixon-Coles ben costruito (0,177–0,199) e ~0,007 sopra
il mercato. Nessuna promozione.

**Aggiornati in questo giro:** conteggi dell'indice in `README` (erano 121/108, ora **123/110**) e
cima del briefing (15/10). Nessun codice di produzione toccato, nessun dato modificato, nessun
merge autonomo.

## 2026-10-15 — PR #122 fusa su ordine dell'utente

L'utente ha scritto **«ok fai merge»**. Prima: `git status --porcelain` vuoto; `origin/main..HEAD`
= `191c559` + `eaeb8f1`; PR MERGEABLE; `test`/`site`/`browser` SUCCESS su entrambi i run.
**Merge:** `gh pr merge 122 --merge`, exit 0; commit **`7366ae5`**, **15/10 10:18:48 UTC**.
Deroga in `docs/13` §9.35. Il sito pubblico si aggiorna al daily post-merge, non in questo
istante. Nessun dispatch extra.

## 2026-10-15 — Previsione/Verifica misurate (docs/108): tolta la tendina vuota

Build 499 schede. Sulle 59 pre: previsione/laboratorio/fascia/posizione/primo-gol **59/59**,
1X2 somma 100, coperture esatti 41–74/100. **211/440** finite avevano `#verifica` vuota:
template e indice ora la stampano solo con matrice o gol. Nessun cambio al modello.
Dettaglio: [`docs/108`](108_previsione_e_verifica_misura_2026-10-15.md).

## 2026-10-14 — Revisione totale (docs/107): prodotto vivo, coda piccola

Richiesta utente: vita/morte/miracoli. Relazione: [`docs/107`](107_revisione_totale_2026-10-14.md).

**Verificato in questo turno (live + `gh`, non rifatti i gate locali):** sito
[CalcioMetro](https://uamisjd.github.io/football-deep-analyzer/) aggiornato 14/10 15:09;
0 partite oggi, prossima ven 16/10 (5 gare); `stato.html` FotMob 7/7 OK; issue **0**, PR **0**;
ultimi 3 daily verdi; `main` `23efbc1`; repo GitHub **~727 MiB**. Gate 1.033 / 242.503 citati
dal giro #119, non ripetuti qui.

**Coda:** (1) daily ≥20 UTC = fotografia completa + `nl`/`pt`; (2) revisione B.10 delle due
sezioni previsione/verifica solo se misura prima/dopo; (3) −80% pack da misurare dopo 7 giorni;
(4) nessuna promozione modello. Nessun codice in questo turno.

## 2026-10-14 — PR #120 fusa; CI, daily e deploy post-merge verdi

**PR #119** (merge `abf75cf`) e **PR #117** (merge `d171e48`) erano già state fuse dall'utente;
i daily #271 e #272 e i rispettivi deploy riuscirono. Il run #271 chiuse automaticamente l'issue
#114. **PR #115** fu chiusa dall'utente senza merge perché il ramo conservava la regex vecchia
`voci?`.

Su richiesta esplicita dell'utente («Please merge the pull request»), eseguito
`gh pr merge 120 --merge`: **PR #120** fusa il **2026-10-14 alle 13:03:17 UTC** (15:03:17 CEST),
merge commit **`44df6a43604d07c0c858d26ca630963e75598a2a`**. Prima del merge: `git status --porcelain`
vuoto; `git log origin/main..HEAD` conteneva solo i due commit della PR (`431d2d2`, `67e05ae`);
nessun commit non pushato; PR mergeable e `test`, `site`, `browser` SUCCESS sullo SHA `67e05ae`
(run [`38564116348`](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38564116348)).

**PR #118** di Dependabot si è chiusa automaticamente alle **13:08:03 UTC**, non fusa (`mergedAt`
null), dopo l'integrazione della correzione #120; non è stata modificata né chiusa manualmente.

**Verifiche post-merge:** workflow `tests` [`38568634353`](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38568634353)
verde; daily [`38568634387`](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38568634387)
con `run`, `deploy` (`115876287520`) e `notify` (`115876534387`) tutti riusciti. Il commit dati
successivo **`190256d`** ha aggiornato soltanto `prospettico.parquet`, come previsto per un run
intermedio; la fotografia completa resta da verificare al run serale.

**Prossimo operativo:** pubblicare questa registrazione post-merge con una PR documentale dal
branch di sessione; poi attendere il daily serale (dalle 20:00 UTC in poi) e verificare il commit
della fotografia completa e la persistenza dei dati `nl`/`pt`. Non fare dispatch duplicati né
riaprire manualmente #114.

## 2026-10-14 — Primo daily dopo #116 fallito: hotfix del singolare, produzione NON ripristinata

Run [`38541503143`](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38541503143):
**run FAILURE**, **deploy SKIPPED**, **notify SUCCESS**; la #114 resta correttamente **OPEN**
e riceve la diagnostica. Raccolta/build conclusi, blocco al gate `verify_site`: **4 intestazioni**
non riconosciute (5781768/8614, 5781771/10229, 5781774/6414, 5781775/6433).
Il parser residuo `voci?` non riconosce «1 voce»: riprodotto **prima della correzione** con
5 test sul template reale, tutti falliti; correzione minima `voc[ei]`, senza cambiare sito,
dati o modelli. Test tematici: **38 passed**, inclusi 10 casi singolare nl/pt, lati scambiati,
vuoto/singolare/plurale; Ruff e pip check puliti. Suite completa **1.033 passed in 145,25 s**.
Prove e limiti: [`HOTFIX_SINGOLARE_2026-10-14.md`](HOTFIX_SINGOLARE_2026-10-14.md).
**PR correttiva [#119](https://github.com/uamisjd/football-deep-analyzer/pull/119) aperta.**
**Prossimo:** attendere i tre check GitHub sullo SHA finale, poi merge dell’utente.
Merge futuro **all'utente**: l'autorizzazione precedente valeva solo per #116. Nessun dispatch
ripetuto, nessuna chiusura manuale #114, nessuna verifica dal vivo di salvataggi/deploy ancora riuscita.

## 2026-10-14 — PR #116 unita su ordine dell'utente; verifica produzione in corso

L'utente ha risposto **«ok procedi»** alla proposta esplicita di merge #116 e verifica del daily.
Controllati prima del merge: `test`, `site`, `browser` **SUCCESS** sullo SHA `d1465b7`, PR
`MERGEABLE`; file locali identici al ramo remoto, nessun lavoro non pubblicato. Riconciliati
HEAD/indice della sessione con i commit già remoti senza scartare file (ripristino sandbox).
**Merge eseguito:** `gh pr merge 116 --merge`, exit 0; **`8a6791a`**, **14/10 09:19:25 UTC**
(11:19:25 ora italiana). Deroga una tantum registrata in `docs/13` §9.30.

**Daily del merge:** [`38541503143`](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38541503143),
trigger `push`, SHA `8a6791a`, in esecuzione. Issue **#114 ancora aperta**: non dichiarato
ripristino prima del deploy. La #115 non è stata chiusa/fusa (il suo fix è già incluso nella #116).
**Prossimo:** esito run + deploy + notify, chiusura allerta, lettura del sito aggiornato e prova
salvataggio registro; fotografia completa/archivio nl-pt da verificare al run serale, se non
salvati in questo run intermedio. Nessun risultato futuro dato per già ottenuto.

## 2026-10-14 — Correzioni dell'audit: tutti i controlli locali verdi, CI finale in attesa

Richiesta utente: «correggi e sistema tutto». Dettagli e prove in
[`CORREZIONI_AUDIT_2026-10-14.md`](CORREZIONI_AUDIT_2026-10-14.md).
Worktree isolato per commit/rebase/push; marker/paginazione delle fotografie senza includere
il registro; budget per ogni retry; allerta solo dopo run+deploy; parser [50] della #115 integrato;
titolo Accuratezza e testi ESPN corretti. CI con build/gate/browser, Actions a SHA, permessi per
job, constraints Python/npm e Dependabot, LICENSE già dichiarata resa esplicita.
Browser reale avviato nel sandbox: trovati e corretti problemi di focus tabelle, link e contrasto;
nuovo controllo Playwright/axe a 375/1280 px e due temi. Nessun cambiamento al modello o ai dati.

**Giro definitivo locale verde:** **1.023 test**, Ruff 0, pip check OK, build 499/2.364/7.600,
**4.316 HTML / 152,8 MB**, verify **242.503 · 0**, parità **59**, resa **28.766 · 0**;
**browser reale Chromium 153: 84 visite / 21 pagine / 0 problemi** (7 pre + 7 post, una per lega per tipo,
7 pagine principali, due viewport/temi, matrice aperta e interazioni). Wheel completa con LICENSE.
Il test della ricerca attende ora il debounce: corrette 4 segnalazioni spurie del nuovo harness,
nessun bug inventato del filtro. Modelli e Parquet byte-invariati rispetto a `cdfc85c`.
**GitHub:** `test` e `site` già verdi su `77e173c`; check della revisione finale ancora da completare.
Nessun merge/dispatch/chiusura #115 eseguiti. **Prossimo:** check finali #116; merge utente;
poi prova dal vivo di daily+deploy, foto serale, registro intermedio e raccolta nl/pt.

## 2026-10-13 — Audit indipendente della sessione 7c92c1a2: prodotto verificato, pipeline da correggere

Relazione completa: [`AUDIT_COMPLETO_2026-10-13_7c92c1a2.md`](AUDIT_COMPLETO_2026-10-13_7c92c1a2.md).
Riferimento verificato: `cdfc85c`; nessun merge/dispatch/modifica ai dati. **988 test**, Ruff 0,
`pip check` OK, wheel completa; build **499/2.364/7.600**, **4.316 HTML / 148,8 MB**;
`verify_site` **242.493 · 0**, parità **59 schede**, resa 375 **28.766 · 0**.

**Dal vivo:** sito raggiungibile ma ultimo daily **#267 rosso**, issue **#114** aperta;
PR **#115** già aperta da altra sessione, check `test` verde, corregge l'oracolo [50].
**Nuovi difetti riprodotti offline**, non coperti dalla #115: (1) commit parziale del registro
lascia altri Parquet modificati e `git rebase` fallisce; (2) la query dell'ultima fotografia
include i commit del solo registro e può far saltare la fotografia serale; (3) retry HTTP supera
il budget (1 consentita → 3 tentativi). **Verificati nel codice/sito:** ripristino allerta prima
del job deploy; paragrafo/link Laboratorio dentro `<title>` di Accuratezza; testi ESPN stantii.
Il prospettico pubblicato ha **5 gare valutate**, non zero; nessuna variante da promuovere.

**Prossimo:** coordinare #115 con i due fix del salvataggio, verificare daily fino al deploy e
fotografia completa/registro separati; poi integrazione CI, allerta, titolo e ultime due sezioni.
Questo turno consegna l'audit, non dichiara implementate le correzioni. Nessuna prova browser/CVE.

## 2026-10-13 — Stampa in lingua originale: fonti estere con sintesi nostra (docs/106, PR #113)

**Decisione dell'utente (13/10, `ask_user`):** «cambio politica: fonti estere + sintesi nostra» —
risposta alla sua domanda «perché per le squadre estere non usiamo fonti estere?».

**Misura che motiva la deroga** (`docs/106` §1): sulle 58 schede pre-partita la card «Vita del
club» era vuota in **10 su 10** fra NED1 e POR1; togliendo il filtro lingua le voci pubblicabili
restavano **0** — le 46 voci non italiane in archivio sono pagine di servizio di testate italiane
e siti di pronostici, non stampa estera. La stampa italiana non scrive dei club di queste leghe.

**Implementato:** edizioni locali dichiarate per lega (`config/leagues.yaml`), lingua nelle righe
raccolte (colonna `language`), vocabolario chiuso di 9 temi con priorità fissa
(`src/fda/site/estero.py`), card `news-estera` con titolo originale citato + fonte + lingua
dichiarate, riga unica che dichiara anche le voci in lingua originale, **oracolo indipendente
[50]** in `verify_site.py`. Costo: 168 richieste per run (tetto 200).

**Misura sul campione reale (27 titoli, feed del 13/10):** prima 0 voci → dopo **1–3 voci per
club** (Heerenveen 3, Sparta 3, AZ 1, Braga 1). Titoli conservati in
`tests/fixtures/estero_2026-10-13.json`, resa congelata in un test.

**Gate:** pytest **988** (+25) · ruff 0 · build **498/2.364/7.602** · `verify_site` **241.774 controlli · 0 problemi**
(55 oracoli: 32 indipendenti, uno nuovo — [50]) · parità **58 schede identiche** · resa 375 px **28.728 · 0**.

**Chiusura del turno (dopo `docs/106`, commit `c07ea95`):** corretti i conteggi dell'indice dei documenti, che erano
sbagliati da più giri — **117 file `.md` e 107 documenti numerati** (`00`–`106`: il 09 non è mai esistito, il 58 è
duplicato) — e i numeri stantii della tabella del briefing (515 test in 44 file → **988 in 60**; 26 Parquet → **32**;
template 12 → **13**), dichiarando che la tabella arriva fino a `docs/69` e che l'elenco completo è `ls docs/`.
PR #113: check `test` **verde** (3m24s), `MERGEABLE`/**clean**.

**Merge eseguito il 13/10 dall'agente su ordine esplicito dell'utente** (*«Please merge the pull request.»*):
deroga alla regola D registrata in [`docs/13` §9.29](13_modelli_e_schede_piano_2026-09-13.md). Prima del merge,
verifica d'ordine con i comandi: `git log --oneline origin/main..HEAD` = solo i commit della PR,
`git status --porcelain` vuoto, nessun commit non pushato. Commit di merge e run del `daily` registrati nella
voce di chiusura qui sotto.

## 2026-10-13 — Una fotografia dei dati al giorno: opzione A adottata (docs/105), −80% di crescita

**Decisione dell'utente (via domande di sessione): opzione A** — i Parquet entrano in `main`
**una volta al giorno** invece di ~5, con un'unica eccezione motivata (il registro preregistrato).
Il sito resta identico: cinque build e cinque deploy al giorno, stessi gate, stesse richieste.

**Implementato:**
- `scripts/fotografia_dati.py`: decisione pura (`decide()`), stato letto dalla cronologia del
  repository (`gh api`, ripiego `requests`), fail-open su qualunque errore.
  Regola: prima fotografia → sì; fotografia di **oggi** (UTC) → no; altrimenti sì se
  **ora UTC ≥ 20** (run serale) **oppure** se sono passate **≥ 24 ore** (rete di sicurezza).
- `tests/test_fotografia_dati.py`: **20 test** (giornata a cinque run con una sola fotografia,
  confine delle 24 ore, fail-open, ripiego su `requests`, output a una riga per `$GITHUB_OUTPUT`).
- `.github/workflows/daily.yml`: nuovo passo «Fotografia dei dati — decidere se questo run
  committa», commit condizionale, e nuovo input di dispatch **`forza_commit`** (default `false`).
  Quando la fotografia è già salvata si committa **solo** `data/processed/prospettico.parquet`
  se è cambiato (il suo valore di prova è la data di registrazione: costo misurato 0,5 MB/30 gg).

**Prove:** estrazione del passo dal YAML ed esecuzione in un repository di prova con origine
locale — cinque scenari, tutti corretti: con «fotografia già salvata» i Parquet grandi **non**
sono su origine e il registro sì; nei casi serali si committa `data: run …`. Prova dal vivo dal
sandbox: lo script legge il commit dati delle 17:33 UTC e risponde `commit=false`.

**Effetto atteso** (`docs/105` §4): da ~155 fotografie e 743,8 MB/mese a **~30 fotografie e
~150 MB/mese (−80%)**; 1 GB spostato da ~24/10/2026 a ~metà dicembre 2026, 5 GB oltre il 2029.
**Da verificare dopo il merge:** il primo run serale (fotografia presente) e i run intermedi
(solo registro o «niente da fare») — è la verifica che i gate offline non possono dare.

**Prossimo:** merge delle due cose insieme (la revisione `docs/104` e questa), poi la verifica
d'ingresso del `daily`; in coda le 2 sezioni della scheda e l'esperimento notizie NED1/POR1.

## 2026-10-13 — Revisione totale del progetto e del sito (docs/104): salute confermata, tre decisioni all'utente

**Richiesta utente:** *«controlla vita morte e miracoli del progetto e del sito, vedi a che punto
siamo arrivati, se c'è qualcosa da fare, da rivedere, da migliorare. fai delle ricerche e studia
tutto»*. Relazione completa in [`docs/104`](104_revisione_totale_2026-10-13.md).

**Misurato da zero in quella sessione** (i numeri di oggi, dopo `docs/105` e `docs/106`, sono `pytest` **988** e
`verify_site` **241.774 · 0 problemi** con 55 oracoli — [50] è la card «stampa in lingua originale»; storia
completa recuperata: 713 commit; build locale dai dati di `17b46b3`): `pytest` **943**, `ruff` **0 errori**, `fda build` **498 schede / 2.364 fixture /
7.602 giocatori**, `verify_site` **241.754 controlli · 0 problemi**, parità **58 schede** (struttura
identica, indice 16 voci, testo min 31.876 · mediana 37.508), resa 375 px **28.728 misure · 0**;
sito **4.316 pagine HTML / 153 MB**; anteprima attiva su `0.0.0.0:8000`. GitHub: **0 issue, 0 PR**,
daily 3/3 verdi dopo la PR #110, `lab`/`benchmark`/`understat-storico` verdi. Sito pubblicato:
0 partite oggi (sosta nazionali), messaggio onesto, ripresa **venerdì 16/10/2026 con 5 partite**.
Nessun numero pubblicato smentito dai dati.

**Contenuti — «Vita del club» sulle 58 pre-partita:** 33/58 con voci (ITA1 10/10, ESP1 7/10,
GER1 6/9, ENG1 5/10, FRA1 5/9, **NED1 0/9, POR1 0/1**). Ricerca web di conferma: la stampa italiana
copre le leghe estere solo per i club maggiori → il buco di NED1/POR1 è **di fonte**, non di filtro.

**Rischio nuovo, misurato:** il repository cresce di **~24,8 MB/giorno** (743,8 MB negli ultimi 30
giorni; pack **722,85 MiB**; news.parquet 45%, backtest 27%, predictions 12%; blob massimo 4,9 MB,
nessun file vicino ai limiti 50/100 MiB). A questo ritmo **1 GB ~24/10/2026** e 5 GB ~7/4/2027. Opzioni con numeri in `docs/104` §3: **A** commit dei dati 1×/giorno (−80%), **B** stop agli
snapshot derivati, **C** compattazione periodica con `git filter-repo`, **D** LFS (insufficiente da
sola: 1 GB gratis). Il checkout della CI è shallow e non è toccato. **Decisione dell'utente, non
presa d'ufficio.**

**Coda confermata:** restano le **ultime 2 sezioni** della scheda partita («Previsione del modello
ensemble»; «Verifica approfondita» — «Precedenti» chiusa con `docs/103`); decisioni aperte su
StatsBomb e clima; `dc_xg` non promosso (in attesa di accumulo); igiene documentale: l'indice di
briefing/README diceva «92 file `.md` / 83 numerati», oggi sono **114 / 104**.

**Ricerca:** limiti GitHub (file 50/100 MiB; repo ideale <1 GB, <5 GB raccomandato; LFS 1 GB),
`git filter-repo`/`git-sizer` per il contenimento, stampa italiana delle leghe estere (Sky Sport,
Eurosport, Diretta.it: coprono i club grandi e gli eventi di lega).

**Prossimo:** tre decisioni all'utente (politica del repository; le 2 sezioni; feed di lega per
NED1/POR1). PR aperta con questo documento (`docs/104`), nessun merge.

## 2026-10-13 — Merge PR #111 su ordine esplicito dell'utente (docs/102 + docs/103)

**Merge PR #111 (`arena/3bafce48-football-deep-analyzer` → `main`):**
- Eseguito dall'agente su ordine esplicito dell'utente nel turno corrente (*«Please merge the pull request.»*; deroga una tantum registrata in `docs/13` §9.27).
- **Contenuto fuso su `main`:** concordanza ««1» + plurale» rimasta sul sito (`docs/102`) e revisione misurata della sezione «Precedenti» (`docs/103`).
- **Verifica pre-merge (controllo d'ordine `docs/00` §D eseguito):** `git log --oneline origin/main..HEAD` = solo i commit della PR, `git status --porcelain` vuoto · `pytest` **943** · `ruff` pulito · build **498/2.364/7.602** · `verify_site` **241.619 · 0** · `parita_schede` nessuna differenza · `resa_375` **28.722 · 0** · CI `tests` verde (`38432135717`).
- **Prossimo passo:** le due sezioni restanti della coda `docs/101` §4 (Previsione del modello ensemble; Verifica approfondita), e la verifica all'ingresso del `daily` post-merge su `main`.
- **Esito (verificato nello stesso turno):** merge `1cc4e16` (16:56:29Z, eseguito da `uamisjd` su autorizzazione dell'agente); `daily` **38434603128** su `main` = **success** (`run` + `deploy`, run 16:56 → 17:15Z) con commit dati **`c073c90`** («data: run 2026-10-13 17:15 UTC»); nessuna issue aperta. Il deploy Pages ha pubblicato il sito coi fix `docs/102`/`docs/103`.

## 2026-10-13 — Revisione di «Precedenti» (`#precedenti`): misurata, tre difetti chiusi (`docs/103`)

**Misura d'ingresso** (`docs/101` §4.1; elenco canonico dal `sitemap.xml`: 498 schede = 58 pre-partita + 440 finite): blocco completo su **52/58** pre-partita (sulle finite **0 per progetto**: `h2h_pattern` è un blocco pre-partita come `key_players_deep`), bilancio corto 5+433, segnaposto 8/8 veri; **490 schede** con l'elenco «Ultimi precedenti» (**2.353 righe**) e **0 incoerenze** rispetto ai Parquet (date, punteggi, esiti V/N/P, duplicati, regola della vigilia, righe anomale); il bilancio corto di FotMob combacia con l'archivio **438/438**; sotto-serie per campo su 39 schede, **muta su 13** (il difetto M6 di `docs/55`).

**Difetti chiusi:** (1) «nessun pareggio **negli ultimi 1**» su 8 schede → «nell'ultimo precedente», con **quarto ramo di `AGREEMENT`** (aggettivo plurale + «1»; misurato prima: 8 hit reali, 0 falsi positivi su 4.314 pagine e attributi); (2) **M6** → `venue_n` esposto sempre e riga «di cui con X di casa (N): sotto la soglia di 8 casi non pubblichiamo le frequenze» sulle 13 schede, col numero ricalcolato dall'archivio in `[5]` (39 pubblicate + 13 col motivo); (3) il **bilancio corto porta il numero dei casi** («Bilancio (2)») su 438 schede, verificato come somma dei tre numeri stampati — `[5]` passa così da 52 a **490** schede verificate.

**Gate:** `pytest` **943** · `ruff` pulito · build **498/2.364/7.602** · `verify_site` **241.619 · 0** (erano 240.691) · `parita_schede` nessuna differenza · `resa_375` 28.722 · 0. Dopo: «ultimi 1» **0**, righe «Bilancio (N)» **490**, frasi di soglia **13**. Restano la sezione 2 («Previsione del modello ensemble») e la 3 («Verifica approfondita») della coda `docs/101` §4.

## 2026-10-13 — Chiusa la classe ««1» + plurale» su UCL e arrivi (`docs/102`), dopo la verifica d'ingresso del daily

**Verifica d'ingresso:** il log incollato dall'utente corrisponde ai run `38381687223`/`38391444901` su `6a0034c`, già corretti da `b021aeb` (PR #110); daily `38414127388` **success** su `b6d7cc3` + commit dati `1364678`, issue #109 chiusa automaticamente alle 14:47:42Z. Nessun intervento ulteriore sui due errori del log ([`docs/102`](102_concordanza_ucl_e_arrivi_2026-10-13.md) §1).

**Misura della stessa classe sulle 4.316 pagine pubblicate** (parser del gate; §2): 331 bigrammi «1 <parola>» distinti, quasi tutti falsi positivi strutturali (etichette di colonna in maiuscolo, celle di confronto). Due difetti veri: «Altri 1 arrivi riconosciuti» (5 schede pre-partita) e «UCL (prime 1)» / «nelle prime 1 posizioni» (POR1, `ucl_spots: 1`, 4 occorrenze).

**Correzioni (§3):** fonte unica `ucl_label(spots)` in `src/fda/site/fmt.py` (1 → «UCL (1ª)», N ≥ 2 → «UCL (prime N)», soglia ignota → «UCL»), registrata come filtro Jinja in `build.py` e usata da `match.html` (Posta in gioco + legenda), `stagione.html` (intestazione e nota «nella 1ª posizione») e `analysis.py` («in zona UCL (…)»); tendina Mercato con «Un altro arrivo riconosciuto» quando ne resta uno; `verify_site.py` e `audit_panchina.py` ricompongono la forma nuova in modo indipendente; `AGREEMENT` esteso con 15 plurali misurati a zero occorrenze legittime.

**Misure dopo:** «prime 1» 0 · «1 arrivi» 0 · «UCL (1ª)» presente dove serve. **Gate:** `pytest` 943 passati · `ruff` pulito · build 498/2.364/7.602 · `verify_site` **240.691 controlli · 0 problemi** · `parita_schede` nessuna differenza · `resa_375` 28.722 misure · 0 problemi. **Punto aperto dichiarato (§6.1):** `[20]` legge ancora l'HTML grezzo per il contatore letture; da valutare la lettura sul testo.

## 2026-10-13 — Merge PR #110 su ordine esplicito dell'utente e handoff per la nuova sessione (`docs/101`)

**Merge PR #110 (`arena/079933b1-football-deep-analyzer` → `main`):**
- Eseguito dall'agente su ordine esplicito dell'utente nel turno corrente (*«ok fai merge ,dopo
  continuiamo su una nuova sessione,quindi in caso prepara la nuova sessione con i prossimi
  lavori»*; deroga una tantum registrata in `docs/13` §9.26).
- **Contenuto fuso su `main`:** hotfix dei 2 errori del workflow `daily` (Issue #109,
  [`docs/99`](99_diagnosi_daily_109_hotfix_2026-10-13.md)), filtro lingua V3 puro-Python
  `149/149` ([`docs/98`](98_lingua_copertura_2026-10-13.md) §6), copertura e ricerca web di
  «Vita del club» (`#notizie`) su tutte le partite ([`docs/100`](100_vita_club_ricerca_web_copertura_2026-10-13.md)),
  e preparazione completa della nuova sessione ([`docs/101`](101_handoff_prossima_sessione_2026-10-13.md)
  e `docs/BRIEFING_NUOVA_SESSIONE.md`).
- **Prossimo passo (nella nuova sessione):** verificare all'ingresso il `daily` post-merge su
  `main` e l'issue `#109`, avviare il server di anteprima su `0.0.0.0:8000` e completare la
  revisione delle **ultime 3 sezioni della scheda partita** secondo la mappa tecnica in
  [`docs/101_handoff_prossima_sessione_2026-10-13.md`](101_handoff_prossima_sessione_2026-10-13.md):
  1. **«Precedenti» (`#precedenti`)** (`match.html:650–670`, `h2h_pattern`, `h2h_list`, `h2h_stats`, invariante `[7]`);
  2. **«Previsione del modello ensemble» (`#previsione` + `#scomposizione` + `#laboratorio` + `#fascia-storica` + `#posizione-lega` + `#primo-gol`)** (`match.html:671–864`, invarianti `[8]`, `[10]`, `[11]`, `[12]`, `[15]`, `[16]`, `[17]`, `[46]`, `[47]`);
  3. **«Verifica approfondita: risultati esatti e distribuzione gol» (`#verifica`: `#probabilita` + `#gol-totali`)** (`match.html:1118–1168`, invarianti `[8]`, `[9]`).

## 2026-10-13 — «Vita del club» (`#notizie`): ricerca web, disambiguazione club, finestra 14 giorni e copertura su tutte le partite (`docs/100`)

**Diagnosi e risoluzione dei 5 colli di bottiglia ([docs/100](100_vita_club_ricerca_web_copertura_2026-10-13.md)):**
- **Allineamento finestra pre-partita (`MatchAnalysis.NEWS_WINDOW_DAYS = 14`, `club_news_checks.py`):**
  con le gare in programma a fine sosta nazionali (`16–20/10`), la finestra di 7 giorni
  (`[kickoff - 7d, as_of]`) si comprimeva a 1–3 giorni (fino a 9 ore sui posticipi), scartando
  l'82% degli articoli già raccolti nei 14 giorni di `NEWS_RETENTION_DAYS` (`969` voci
  esaminate contro `5.321` entro 14 giorni dal calcio d'inizio).
- **Disambiguazione dei nomi club (`src/fda/site/analysis.py`):** esteso `team_tokens` con gli
  esonimi e gli alias italiani di `soggetto_tokens(team_name)` (`Lipsia`, `Colonia`,
  `Stoccarda`, `Friburgo`, `Magonza`, `Nizza`, `Marsiglia`, `Siviglia`, `Maiorca`, ecc.);
  esclusi da `_club_tokens` i prefissi condivisi fra più club (`real`, `borussia`, `olympique`,
  `sporting`, `manchester`, `madrid`, `paris`, `united`, `city`, `union`) e i nomi comuni
  italiani (`fortuna`, `santa`, `clara`, `ahead`, `eagles`, `saint`); corretta `altra_squadra`
  sui club con nome di 3–4 lettere (`Lens`, `Ajax`, `Como`, `Pisa`, `Roma`, `PSG`, `PSV`,
  `Hull`, con guardia locativa `\ba\s+roma\b`); introdotta la cache `team_player_names`.
- **Query di ricerca web e attribuzione multi-club (`src/fda/sources/news.py`):** estesa
  `ITALIAN_SEARCH_NAMES` a 17 club europei privi di variante italiana/completa (`Brighton`,
  `Wolverhampton`, `Mallorca`, `Osasuna`, `Alavés`, `Oviedo`, `Rennes`, `Brest`, `Nice`,
  `Strasbourg`, `Lens`, `Paris FC`, `Heidenheim`, `St. Pauli`, `Kaiserslautern`, `Famalicao`,
  `Vitoria SC`, `AVS`) e rimossa l'interruzione al primo club in `parse_espn_news` e
  `parse_direct_sports_rss`.
- **Selettore positivo (`src/fda/site/club_signals.py`) e visibilità dati (`match.html`):**
  corretto il typo regex `ricors[oi]` in `EVENT_RULES`, estesi i pattern club-agnostici per
  assetto societario, panchina, provvedimenti, infortuni/rientri, rinnovi contrattuali e
  analisi tecnico-tattica (`31/31` invariato sul benchmark annotato, `0` falsi positivi sui
  controlli negativi), e impostato `<details class="news-context" open>` affinché i `285`
  fatti verificati («Dati di contesto della partita») siano subito visibili su **58/58**
  schede pre-partita.
- **Misura prima → dopo sulle 58 schede pre-partita (`sitemap.xml`):**
  - Schede con rassegna stampa attiva: da **6 / 58 (`10,3%`)** a **33 / 58 (`56,9%`)**
    (`ITA1` `5/10 → 10/10`, `ESP1` `1/10 → 7/10`, `ENG1` `0/10 → 5/10`, `GER1` `0/9 → 6/9`,
    `FRA1` `0/9 → 5/9`).
  - Lati squadra con notizie di stampa: da **7 / 116 (`6,0%`)** a **45 / 116 (`38,8%`)**,
    con **67 articoli pubblicati** (contro `12` prima; su `audit_vita_editoriale.py` da `7` a
    **49 lati** e da `13` a **101 segnalazioni**).
  - Schede con informazioni utili visibili subito in «Vita del club» (stampa + dati di
    contesto aperti): **58 / 58 (`100%`)** su tutte le 7 leghe.
- **Gate verificati:** **932 test** passati (`+9` nuovi controlli in `test_club_signals.py` e
  `test_vita_club.py`), `ruff check .` 0 errori; `fda build` **493/2.364/7.594**; `verify_site`
  **238.546 controlli / 0 problemi** (`[20]` **1.148 controlli indipendenti** su 58 pagine);
  `audit_fonti.py` **0 difetti bloccanti**. Anteprima attiva su `0.0.0.0:8000`.

## 2026-10-13 — Chiusura di `docs/98` §6: filtro lingua V3 puro-Python (`149/149`) e diagnosi copertura per lega

**Misura e integrazione V3 (`src/fda/sources/news.py`, `tests/test_i18n.py`, [docs/98](98_lingua_copertura_2026-10-13.md) §6):**
- Risolti tutti i **19 errori su 149** della baseline sul benchmark congelato
  `tests/fixtures/news_language_review_2026-10-13.json` (**149/149 corretti: 0 falsi
  positivi, 0 falsi negativi**) senza introdurre `Lingua` (~909 MiB in RAM) né nuove
  dipendenze (**0 MiB extra RAM**).
- Valutazione **prima sul solo titolo**: i 6 falsi positivi `[misto_titolo_straniero]`
  (`en`, `fr`, `nl`, `pt`, `ro`, `pl` con estratto italiano) sono tutti bloccati e i 3
  falsi negativi `[misto_titolo_italiano]` sono tutti recuperati.
- Corretti i falsi veti lessicali su parole italiane o prestiti correnti (`però` che senza
  accento collideva con lo spagnolo `pero`, `polemica` vs `polémica`, `Under`, `Eredivisie`,
  `ADO Den Haag`, `para`, `vai`, `now`; `manager`, `fans`, `meeting`, `ß` in cognomi come
  `Groß` e genitivo sassone ammessi in presenza di ≥ 2 marcatori esclusivi italiani;
  `Casa`/`Rosa`/`Gol` neutralizzati nei nomi propri di club isolati come «Casa Pia Porto»;
  tokenizzazione Unicode `[^\W\d_]+`).
- **Replay sulle 4.431 coppie uniche di `data/processed/news.parquet`:** **1 sola nuova
  esclusione** (`"Parma's Nesta Elphege Undergoes Appendix Surgery"`, titolo inglese che la
  baseline lasciava passare) e **185 recuperi italiani** (0 falsi positivi stranieri).
- **Effetto su «Vita del club» e diagnosi della copertura per campionato:** sulle 63 schede
  del campione di `docs/97` gli scarti impropri «in un'altra lingua» scendono da **145 a 80**
  (`-65`, di cui `11 → 1` in `NED1` e `23 → 8` in `GER1`; sulle 58 schede pre-partita del
  13/10 da **110 a 60**, `-50`), attribuendo le righe italiane recuperate alla vera ragione
  editoriale (`servizio o cronaca`, `bassa reputazione`, `su un'altra squadra`, `senza
  segnale`) e recuperando nel *Clima intorno al club* di `5749690` (`Atalanta-Venezia`) la
  notizia societaria de *Il Gazzettino* prima scartata per «polemica». Dimostrato con misura
  per lega che l'assenza di voci esposte nelle leghe estere dipende dalla natura di cronaca
  delle 197 righe italiane raccolte su 51 gare estere, non dal filtro lingua.
- **Gate verificati:** **923 test** passati (`+1` benchmark test su 149 casi in
  `test_i18n.py`), `ruff check .` 0 errori; `fda build` **493/2.364/7.594**; `verify_site`
  **238.235 controlli / 0 problemi**; parità **58 schede**; resa 375 px **28.504 misure /
  0 problemi**; audit Vita (**840 / 0**), Mercato (**928 / 0**) e Panchina (**0 difetti**).
  Anteprima attiva su `0.0.0.0:8000`.
- **Prossimo:** audit delle ultime 3 sezioni della scheda partita (*Previsione ensemble*,
  *Precedenti*, *Verifica approfondita*). PR **#110** aperta e pronta per il merge quando
  vorrai sbloccare `daily` su `main`.

## 2026-10-13 — Post-merge PR #108, diagnosi issue #109 e hotfix dei due errori del `daily` (docs/99)

**Stato verificato su Git e GitHub Actions:** PR #108 unita dall'utente (`6a0034c`, 21 commit
dal ramo `arena/8d89284f-football-deep-analyzer`; nessun commit orfano rimasto fuori).
Workflow `tests` su `main` verde (`38381687220`), mentre `daily` su `main` era rosso da
5 run consecutivi (issue automatica **#109** aperta dal run #257 del 12/10 19:44 UTC e
aggiornata fino al run #261 `38381687223` del 13/10 10:29 UTC). Raccolta dati, modelli,
backtest, simulazioni e `fda build` riuscivano con 0 errori; il blocco avveniva al passo 11
(`verify_site`), prima del commit dei Parquet e del deploy Pages.

**Due cause diagnosticate e corrette ([docs/99](99_diagnosi_daily_109_hotfix_2026-10-13.md)):**
1. `laboratorio.html: concordanza '1 campionati'`: la riga 52 del test prospettico stampava
   `{{ prosp.leagues_better }} campionati` senza filtro plurale; rimasta latente finché
   `prosp.n == 0` nello snapshot locale, si è attivata in produzione alla prima gara finita
   con `leagues_better == 1`. Corretta con `|it_plural('campionato', 'campionati')` (e
   concordato anche `lab.n_passes == 1` alla riga 12).
2. `5749705.html: «letture sul tema» di Juventus stampa 0, i dati dicono 1`: in `match.html`
   (riga 611) il contatore è dentro `<b>...</b>` (`· <b>1 letture sul tema</b>`). Mentre
   l'oracolo indipendente `club_news_checks.py` legge il testo senza tag HTML (ed è passato
   nel run #261 con 864/864 controlli verdi), `[20]` in `verify_site.py` (riga 3212) cercava
   `r"· (\d+) letture sul tema"` sull'HTML grezzo `head`, fallendo per via di `<b>` non
   appena il run live ha trovato 1 lettura correlata su Juventus (`5749705.html`). Corretto
   il singolare in `match.html` (`1 lettura sul tema`), allineate le regex in `verify_site.py`
   (`r"· (?:<b>)?(\d+) lettur[ae] sul tema"`) e `club_news_checks.py`, ed esteso `AGREEMENT`
   a `1 letture`.

**Gate finali verificati:** **922 test** passati (+2 test di regressione dedicati in
`test_lab_page.py` e `test_vita_editorial.py`), `ruff check .` pulito; `fda build`
**493/2.364/7.594**; `verify_site` **238.235 controlli / 0 problemi**; parità **58 schede**;
resa 375 px **28.504 misure / 0 problemi**; audit Vita (**840 / 0**), Mercato (**928 / 0**)
e Panchina (**0 difetti**) superati. Nessun Parquet modificato, nessun modello cambiato.

**Prossimo:** (1) PR pronta per sbloccare subito `daily` su `main` e far chiudere in
automatico l'issue #109 (merge dell'utente, regola D); (2) proseguire su Vita del club
(`docs/98` §5: misura di V3 sul filtro lingua e copertura delle 5 leghe estere), poi le
ultime 3 sezioni del punto 4 (*Previsione ensemble*, *Precedenti*, *Verifica approfondita*).
Decisioni utente aperte: StatsBomb e conferma card Clima.

## 2026-10-13 — Lingua e copertura: misura del difetto e confronto preregistrato (docs/98)

**In corso, nessun candidato ancora integrato.** Prima attività: file riallineati al ramo
salvato dopo confronto hash di 51 file, zero differenze; venv ricreato, Parquet intatti.
Riprodotti: italiano breve letto come rumeno; veto su «polemica»/«manager» italiani;
titolo inglese autorizzato da una descrizione italiana. Non basta aumentare i titoli.

Candidato dichiarato prima del replay: Lingua offline, tutte le lingue supportate, solo
titolo, margine almeno 0,15 e guardia sui titoli brevi senza grammatica. **149 casi**
congelati per confronto (italiani/stranieri/ambigui/misti). Prove preliminari e costi in
[docs/98](98_lingua_copertura_2026-10-13.md); nessun risultato di accuratezza ancora attribuito.
**Prossimo:** confronto + replay reale per lega, poi eventuale integrazione, gate e
anteprima. Vita del club ancora aperta: niente passaggio all'ensemble, merge o cambio
modelli. Vincolo italiano, decisioni StatsBomb/clima e tutela dei `season_sim*` invariati.

## 2026-10-13 — Vita del club: qualità editoriale migliorata, copertura ancora insufficiente

**Richiesta utente:** verificare davvero accuratezza, utilità, intuibilità e tutte le partite.
Riaperta la sezione, senza avanzare all'ensemble. Recuperati dal ramo remoto `40d56f8` la
ricerca docs/97 e i 31 titoli annotati prima del nuovo codice. Nessuna perdita di file.

**Ricerca e misura:** nota primaria Udinese riletta: Idrissa Gueye, intervento alla caviglia;
la regex trovava «rissa» nel nome. Conferme primarie su Genoa/Atlético; Polizia di Stato:
22 misure cautelari + 42 Daspo, comunicato 6/10 sugli scontri del 24/5. Date e conteggi non
vengono confusi o sommati. Ricerche Benfica/Ajax hanno anche restituito articoli del 2025/2023:
scartati perché fuori periodo, senza dedurre che non esistano eventi recenti.

**Prima dell'integrazione:** criterio positivo provato in ombra, 31/31 etichette manuali di
sviluppo rispettate + 28 controlli separati. Non precisione futura né recall certificata.
**Ora implementato:** confini di parola per rissa; segnale esplicito di evento o analisi;
modalità distinta e prova nel titolo; letture sul tema tutte consultabili (non equivalgono
a eventi/conferme indipendenti); copertura per squadra visibile; dati numerici separati
come contesto, non notizie. Nessun punteggio di sentiment o modifica ai modelli.

**Misura sul campione fisso:** 63 schede / 126 lati, 1.522 voci; 10 principali + 6 sul tema,
15 titoli distinti, solo 10 lati con segnalazioni (9 ITA1, 1 ESP1). **ENG1, GER1, FRA1,
NED1 e POR1 ancora senza voci selezionate.** Non risolto, non mascherato da riempitivi.
Relazione [docs/97](97_vita_club_qualita_copertura_2026-10-12.md).

**Gate finali verificati:** **920 test**, Ruff pulito; build **493/2.364/7.594**; verify_site
**238.235 controlli / 0 problemi**. Audit Vita **840 / 0**, editoriale, Mercato **928 / 0**,
Panchina e Clima superati; parità **58 schede**, resa 375 px **28.504 / 0 problemi**.
CI `00d3d3a` verde (`38324483243`, `38324477217`). Corrette anche concordanze e lettura DOM
dei marcatori Clima, con regressioni e gate rifatti. Parquet intatti, `season_sim*` compresi;
nessun modello modificato. PR #108 in bozza, nessun merge.

**Sito del 13/10:** 58 schede / 116 lati (cinque gare uscite dal calendario breve), 969 voci,
7 titoli principali: 4 eventi segnalati + 3 analisi/dichiarazioni. **109 lati senza voci**;
ancora 5 leghe a zero. Il confronto di sviluppo resta fisso a 63 schede, non mescolare campioni.
**Limite aggiuntivo provato:** il filtro lingua scarta la frase italiana breve «Inter: misure
cautelari per i tifosi». Non risolto; da valutare con un campione multilingue, non abbassando
la soglia alla cieca. I test verdi non certificano utilità, recall o completezza universali.

**Anteprima attiva/verificata** 0.0.0.0:8000: Roma–Genoa `5749701.html#notizie`; esempio
scoperto SC Heerenveen–Excelsior `5781769.html#notizie`. HTTP 200 su schede, homepage, CSS/font.
**Prossimo:** Vita del club resta APERTA su copertura e falsi negativi linguistici. Non passare
all'ensemble dando questa verifica per definitiva. Decisioni StatsBomb/clima ancora aperte.

## 2026-10-12 — Vita del club: terza sezione verificata, anteprima ripristinata (docs/96)

**Terza sezione del punto 4.** Sandbox ripristinato: confrontati 33 file con il ramo remoto,
zero differenze; riallineamento Git mixed senza toccare il lavoro. Venv ricreato, baseline
63 schede rigenerata dal codice `1d85ae4`. Sito/server temporanei da ricreare, dati CI invariati.

**Misura su 63 schede / 126 lati:** 1.522 voci esaminate, prima 47 pubblicate + 9 riserve.
Invertire le righe cambiava 5 colonne; due imbuti perdevano una voce ciascuno. Ora ordine
stabile delle versioni ammissibili, insieme condiviso limitato a ciò che viene esposto,
contatori di doppioni/categoria/capienza distinti: **0 differenze d'ordine, 0 imbuti aperti**.
Veti circoscritti per titoli di servizio, convocati, conferenze, compleanni, Academy e frasi
senza fatto; parole intere con elisioni italiane e club d'apertura riconosciuto. Regole e pesi
Clima invariati (cambiano solo eventuali marcatori di presenza nella rassegna).

**Dopo, sullo stesso campione:** 32 pubblicate + 3 riserve, 23 uscite / 2 entrate; non è una
metrica di qualità. Date assolute e fase della finestra dichiarate (58 aperte, 5 terminate).
Non si promette assenza di fatti importanti quando la selezione è vuota. Nessuna data futura
rispetto al match o al build; tipo distinta esplicito in «Perché conta». Nessun modello o Parquet
modificato. I filtri sono euristiche, non una verifica giornalistica o di impatto predittivo.

**Gate finali verificati:** **850 test**, Ruff pulito; build **498/2.364/7.594**; verify_site
**241.464 controlli / 0 problemi**; audit Vita **987 / 0**, Mercato **1.008 / 0**, Panchina
 e Clima superati. Parità **63 schede**; resa 375 px **28.669 misure / 0 problemi**.
**63 card Mercato e 63 Panchina identiche** alla baseline. Oracolo senza `team_news`: periodo,
conti, tuple fonte. [20] diventa M da S; tetto S 4→3, S+M≤23 e I≥31. CI `5e45f35` verde
(`38307602678`, `38307597677`). Il delimitatore del test Mercato è stato disaccoppiato dalla
card successiva; suite e gate rifatti. Nessun Parquet modificato, nessun modello promosso.
Relazione [docs/96](96_vita_club_finestra_imbuto_2026-10-12.md) e JSON della misura.

**Anteprima attiva** su 0.0.0.0:8000, server ignorato `data/cache/preview_server.py`:
Torino–Udinese, `partite/5749699.html#notizie`. HTTP 200 su scheda, homepage e CSS/font;
nuovo dominio del sandbox, non il vecchio link. Build locale, non nuova raccolta dati.
PR #108 resta in bozza, nessun merge. **Tre sezioni verificate su sei**, non le ultime tre.
**Prossimo:** Previsione ensemble, poi Precedenti e Verifica approfondita, con anteprima.
Scelte StatsBomb/clima ancora all'utente; non avviato sentiment né una nuova fonte.

## 2026-10-12 — Anteprima navigabile richiesta dall'utente

**Preferenza utente:** vedere anche l'anteprima delle modifiche, non soltanto la relazione.
Avviato nel sandbox un server statico su **0.0.0.0:8000**, limitato alla cartella `site/`:
la pagina iniziale apre **Frosinone–Sassuolo**, `partite/5749704.html#mercato` (16 e 8 arrivi
riconosciuti nell'ultima distinta disponibile, con dettaglio espandibile). `index.html`
resta raggiungibile per navigare il resto del sito. Server temporaneo in
`data/cache/preview_server.py`, escluso da Git; URL dell'anteprima dipendente dal sandbox.

**Verificato via HTTP con Host/Origin del proxy:** scheda, homepage, CSS e font CSS rispondono
200; presenti gli arrivi riconosciuti e il dettaglio degli altri 12. Servita la build già
verificata in `docs/95`: nessuna nuova build, modifica applicativa, modifica ai Parquet o
pubblicazione su `main`. PR #108 resta in bozza. I gate applicativi restano quelli della
voce precedente (796 test, 240.345 controlli).

**Prossimo:** Vita del club, mostrando anche l'anteprima; poi Previsione ensemble,
Precedenti e Verifica approfondita. Decisioni StatsBomb/clima ancora aperte.

## 2026-10-12 — Mercato: seconda sezione verificata, distinte e bilanci riconciliati (docs/95)

**Seconda sezione del punto 4.** Su 63 schede / 126 colonne, gli arrivi nelle distinte
venivano cercati solo fra i quattro esposti: **35 anziché 96 corrispondenze**, 61 omesse in
14 colonne. Ora incrocio sull'intera finestra, quattro nomi in apertura e dettaglio espandibile.
Le 15 colonne interessate usano **8 formazioni previste e 7 ultime distinte**, non conferme:
via «Già in campo / di questa partita», provenienza e ruoli espliciti. Nessun abbinamento fuzzy;
la tabella trasferimenti non ha ID giocatore.

**Cifre e formule separate:** 866 importi numerici, 459 gratuiti, 922 prestiti senza importo,
409 altre voci non dichiarate (1.009 arrivi / 1.647 partenze sulle colonne). Non si assume
un prestito gratuito; corrispettivi noti dei prestiti inclusi ed etichetta aggiunta a 47 righe.
Saldo = spesa − incasso sui soli importi noti, non bilancio del club; 24 colonne non
quantificabili, di cui 14 mostravano prima un saldo con un lato senza cifra. Sette veri zeri
contabili mostrati come 0 €, non importo ignoto. Filtro date prima di deduplica: limite al
momento della pagina/kickoff; non dimostra la conoscenza storica della fonte.

**Impatto verificato sul frammento:** tutti i 126 elenchi / 897 movimenti visibili conservano
nomi, controparti, date e ordine. Conteggi e corrispettivi invariati. Nuovo audit reale su HTML,
con `--site/--data/--json` ed exit 1; [39] senza chiamare il generatore, [26] limitato alla card.
**1.008 controlli, zero difetti** sulle copie corrette; vecchio [39] 493 controlli senza vedere
le omissioni. I 248 rilievi del nuovo audit sul vecchio HTML includono le nuove dichiarazioni
richieste e più controlli sulla stessa cella, non sono 248 errori fattuali distinti.

**Gate finali verificati:** **796 test**, Ruff pulito; `fda build` **498/2.364/7.594**;
`verify_site` **240.345 controlli, 0 problemi**; audit Mercato **1.008 controlli / 0 difetti**,
Panchina ancora **0 difetti**; parità **63 schede**, resa 375 px **28.667 misure / 0 problemi**.
Prova negativa [26]/[39] sull'HTML precedente: exit 1 (324 segnalazioni sovrapposte, non
324 errori distinti). Confronto dopo la build completa conferma tutti i 126 elenchi / 897
righe e le 47 etichette di prestito aggiunte. CI `b77c048` verde: `38292304131`, `38292299551`.
Relazione [docs/95](95_mercato_distinte_bilancio_2026-10-12.md) e JSON della misura.
Nessun Parquet modificato, compresi `season_sim*`; nessun modello promosso. PR #108 resta
in bozza e non unita. **Due sezioni verificate su sei**, non le altre quattro.

**Prossimo:** **Vita del club**; dopo: Previsione ensemble, Precedenti,
Verifica approfondita. StatsBomb e scelta sul clima restano aperti.

## 2026-10-12 — Panchina e posta in gioco: prima sezione verificata, 7 celle corrette (docs/94)

**Prima sezione del punto 4, misura → correzione → prova.** Su 63 schede / 126 lati,
l'audit vecchio dava zero scostamenti ma ricopiava due errori: **5 false salvezze** (pari
punti non cambia il rango in retrocessione) e **2 distanze sbagliate** dalla salvezza diretta
(nei campionati a 18 il riferimento è il 15º, non il 16º dello spareggio). Nuovi controlli
semantici indipendenti: sull'HTML precedente **7 difetti / exit 1**, sul frammento rigenerato
**0**; cambiano esattamente 7 celle di posta in gioco, restano identici 126 allenatori,
126 età e le altre 119 celle di posta. Numeri/probabilità dei modelli e Parquet invariati.

**Audit corretto anche nel comportamento:** prima restituiva exit 0 pur segnalando errori
(prova con PPG falsificato); ora exit 1. Opzioni `--site`, `--data`, `--json`, controlli
rango/salvezza e precisione MC condivisi con [19] di `verify_site`, non col generatore.
**Latente riprodotto:** il template dichiarava sempre 10.000 simulazioni / SE 0,5 pp, anche
con N=1.000. Ora usa il metadato e 50/√N arrotondato per eccesso; N assente dichiarato.
Sui dati reali N è sempre 10.000: nessun cambiamento alle percentuali. Note chiarite:
permanenza include distinte future (10 lati con altra gara non finita); virtuale usa prima
posizione del gruppo a pari punti/DR (35 scenari su 34 lati), non gli spareggi completi.
Nessuna nuova fonte o dato inventato: precedenti coach ancora vuoti nel campione, storico
FotMob assente. Dettagli in [docs/94](94_panchina_salvezza_precisione_2026-10-12.md).

**Gate finali verificati:** **772 test**, Ruff pulito; `fda build` **498/2.364/7.594**;
`verify_site` **239.769 controlli, 0 problemi**; audit panchina **0 difetti**; parità **63 schede**
pulite; resa a 375 px **28.657 misure, 0 problemi**. Prova negativa sul sito precedente:
**14 segnalazioni sulle 7 celle**, exit 1; sito nuovo exit 0. Confronto sulla build completa:
solo le 7 celle attese cambiano, le **63 tabelle condizionate restano identiche**.
CI `9c038ae` verde (`38283708700`, `38283703373`). Nessun Parquet modificato, compresi
`season_sim*`; PR #108 ancora in bozza, nessun merge. **Prima delle sei sezioni verificata**,
non le altre cinque. Correzioni sul branch, non ancora in `main`.

**Prossimo:** **Mercato**; dopo: Vita del club, Previsione ensemble,
Precedenti, Verifica approfondita. StatsBomb e scelta sul clima restano decisioni aperte.

## 2026-10-12 — `dc_xg` misurato: criterio non superato (docs/92–93)

**Fatto, fuori campione temporale e offline:** protocollo [docs/92](92_protocollo_dc_xg_2026-10-12.md)
pushato in `fbc811b` prima dei fit; codice `ad07059` con 69 test mirati; **un solo run** completo.
11.179 gare CI in input, **5.058 appaiate**, 4.810 con xG / 248 fallback NED1-POR1 identici.
**ΔRPS −0,000393, IC 95% [−0,001109; +0,000332], RPS più basso in 3/7 leghe: non passa**.
Nessuna promozione, nessun tuning dopo l'esito. Riferimento riaddestrato sullo stesso campione,
non previsioni storicamente pubblicate; risultato non generalizzabile a tutti i modelli xG.

- `fda lab-xg`: ricetta isolata, xG continui senza troncamento a interi, ρ dai gol dello stesso
  prefisso, calibrazione solo su finestre precedenti, input bloccati per hash, errore al primo
  fit fallito e confronto obbligatoriamente appaiato. Criterio sempre 200 gare / IC < 0 / 5 su 7.
- Metriche e bootstrap ricalcolati con un oracolo separato dai gol originali: coincidono entro
  10⁻¹². Cagliari–Lecce: usata la riga di gara per ID, mai i lati-squadra duplicati.
- Riepilogo in [docs/93](93_esito_dc_xg_2026-10-12.md) e `docs/_lab_xg_2026-10-12.json`;
  dettagli rigenerabili in `data/cache/lab_xg/` (non versionati). Nessun Parquet di produzione
  modificato, compresi `season_sim*`; laboratorio pubblico ancora sul campione CI di 1.654.
  Il prospettico γ resta separato: nessun nuovo run su dati reali.

**Gate finali verificati:** **743 test** passati, Ruff pulito; CI del codice verde (run `38277105600`,
`38277101042`, commit `ad07059`); `fda build` **498/2.364/7.594**; `verify_site`
**239.517 controlli, 0 problemi**; parità **63 schede, nessuna differenza**; resa a 375 px
**28.657 misure, 0 problemi**. Nessun Parquet modificato. PR #108 sempre in bozza, nessun merge;
tutti i commit sul ramo della sessione. **Punto 3 verificato, criterio di promozione non superato.**

**Prossimo:** punto 4: Panchina e posta in gioco → Mercato → Vita del club
→ Previsione ensemble → Precedenti → Verifica approfondita. Metodo: misura → correzione →
invariante/test. **Decisioni aperte:** campionati/stagioni StatsBomb; conferma card clima basata
su regole e sentiment rinviato. Nessuna scelta fatta al posto dell'utente.

## 2026-10-12 — Merge PR #107 verificato: storico e avvio prospettico (docs/91)

**Fatto e verificato sui dati CI:** PR #107 unita (`1bc3a71`), primo `daily` post-merge
`38251884898` riuscito, storico manuale `38271006444` riuscito. Il checkout iniziale
`514309d` era già `main`; la voce «Merge PR #107» dell'handoff non era stata salvata qui.

- **Storico Understat 2021–2025 completo:** 1.826 / 1.826 / 1.752 / 1.752 / 1.752 gare
  finite = **8.908**; **17.816** lati-squadra incrociati senza orfani, duplicati o differenze
  nei gol/xG. Nuovo audit ripetibile `scripts/audit_understat_storico.py`, 10 test.
- **Prospettico avviato:** **3.856 righe / 1.928 coppie**, sette leghe, tutte pre-partita;
  produzione e variante riprodotte senza differenze in uno store temporaneo. **0 risultati**
  valutabili nello snapshot. Nessuna promozione; soglie 200 gare, IC < 0, 5/7 immutate.
- **Difetto misurato e corretto sul branch:** `record` accettava righe postume e riscriveva
  coppie congelate; `evaluate` le contava. Prima: 2 righe postume, 2 riscritte, 1 gara
  valutata; dopo: **0 / 0 / 0**. Ora controllo del kickoff corrente e archiviato,
  validazione numerica, confronto solo fra coppie dello stesso snapshot. 31 test prospettico.
  Nei dati reali **nessuna violazione osservata**. Fix non ancora in `main`.
- **Avviso sui soli dati correnti:** due lati extra di Cagliari–Lecce 07/09/2026, alle 16:00
  oltre alle 16:30 corrette: possibile residuo di aggiornamento d'orario. Non riguarda lo
  storico 2021–2025; non cancellato per deduzione. Dettagli e limiti in `docs/91`.

**Gate finali verificati:** **700 test** passati; `ruff check .` pulito; audit storico 0 difetti;
`fda build` **498/2.364/7.594**; `verify_site` **239.517 controlli, 0 problemi**;
parità **63 schede, nessuna differenza**; resa a 375 px **28.657 misure, 0 problemi**.
CI `tests` del codice verde: run `38273582240`, commit `836a0a2`.
**PR [#108](https://github.com/uamisjd/football-deep-analyzer/pull/108) in bozza**, aperta
per conservare questo blocco e proseguire la coda sullo stesso ramo; **non unita**.
Il commit finale dei gate e del numero PR aggiorna solo la documentazione.
Nessun Parquet modificato; i due `season_sim*` restano fuori dal lavoro (in questo checkout
sono entrambi già tracciati). Nessuna richiesta alle fonti; API GitHub lette, log integrali
Actions non raggiungibili.

**Prossimo, in ordine:** (3) implementare e testare **un solo `dc_xg` preregistrato**:
nei documenti esiste, nel registro del laboratorio **no**. Campione CI 1.654, nessuna
variante robusta; non sostituito con il campione locale 3.157. Understat copre 5 leghe,
non ridurre la regola da 5/7 a 5/5. (4) sei sezioni della scheda ancora da revisionare:
Panchina e posta in gioco, Mercato, Vita del club, Previsione ensemble, Precedenti,
Verifica approfondita — misura → correzione → invariante/test.

**Decisioni utente aperte:** campionati/stagioni StatsBomb; conferma card clima basata su
regole con sentiment rinviato. Nessuna decisione presa al suo posto, nessuna PR unita.
Il congelamento resta conservativo anche se un rinvio diventa noto dopo il kickoff
archiviato: può conservare una previsione meno aggiornata, mai riaprire il test a posteriori.

Le due voci successive sono storiche: gli stati «PR in bozza» e «test dal prossimo run»
sono superati dalle verifiche sopra. Relazione: [docs/91](91_verifica_storico_avvio_prospettico_2026-10-12.md).

## 2026-10-12 — Storico Understat e PR #107 (docs/90)

- Comando `fda understat-storico` (stagioni 2021–2025, 5 leghe) e workflow manuale `understat-storico.yml` (commit dei Parquet solo se cambiano, `[skip ci]`). Test pianificazione: 2.
- Il workflow non è lanciabile finché non è su `main`: GitHub risponde 404 su un workflow manuale che non esiste sul branch di default. PR #107 in bozza, non unita: il merge è dell'utente.
- Non verificato: il recupero reale da Understat (la sandbox non lo raggiunge). Non ancora misurato alcun risultato sul candidato `dc_xg`.
- Aperti: sei sezioni della scheda, StatsBomb (decisione utente), clima (decisione utente).

## 2026-10-12 — Test prospettico γ 1,12, verifica StatsBomb, clima (docs/89)

Decisioni dell'utente: (1) rivedere il clima; (2) StatsBomb su tutti i campionati, 4–5 stagioni precedenti; (3) procedere con le sezioni della scheda; (4) test prospettico γ 1,12.

- **Test prospettico** (`src/fda/models/prospettico.py`, tabella `prospettico`, hook in `fda predict`, sezione in «Laboratorio»): registra produzione e γ 1,12 sulle λ pubblicate prima del calcio d'inizio; promozione solo con 200 partite, IC interamente negativo, 5/7 campionati. 5 test. Nessun risultato ancora.
- **StatsBomb (2): non realizzabile come chiesto.** La Liga 2004/05–2020/21; altri campionati solo poche stagioni; Eredivisie e Primeira nessuna; stagioni recenti assenti. Proposta alternativa: backfill Understat 2021–2025 via CI (da decidere).
- **Clima (1): revisione.** Notizie disponibili solo due settimane, testo vuoto, VADER inglese: sentiment non misurabile oggi. Card resta regola-based; archivio titoli già in accumulo.
- **Sezioni scheda (3): da fare** nel prossimo giro.

**Gate:** `pytest` 662 passati, `ruff` pulito, `fda build` completo, `verify_site` 0 problemi · 235.696 controlli. Nessuna richiesta a fonti esterne in questa tranche, salvo la verifica di StatsBomb.


---

Voci precedenti: [archivio del 12/10](STATO_archivio_2026-10-12.md),
[archivio del 07/10](STATO_archivio_2026-10-07.md); ulteriori archivi `STATO_archivio_2026-09-*.md`.
