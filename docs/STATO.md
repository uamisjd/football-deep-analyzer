## 2026-10-10 — Voce G: tilt dichiarati, commento falso corretto, campione assenze misurato, protocollo preregistrato

Voce G della [coda](docs/69) §1, documentata in [docs/71](71_tilt_commento_falso_campione_assenze_e_protocollo_preregistrato_2026-10-10.md).
**a)** Corretto il commento falso `predict.py:41` («k calibrato su 5.7k gare»: il dato esiste
per **341** gare; k=0,12 non distinguibile da zero, solo k=0,03 sì) — nessuna λ cambia:
`test_tilt_commento_veritiero_e_lambda_immutati` pinnna costanti e uscite numeriche dei tre
tilt e blocca il ritorno del falso. **b)** Misurato (matrice 2×2 codice×dati, non
ipotizzato) perché il campione assenze è sceso 137 → 98: −3 per il cambio di codice
(docs/64 §8: totale = somma dei valori pubblicati), −37 per i dati — tra i run del 21–24
settembre 110 partite sono state riscaricate e le tabelle per-partita
(`replace_by="match_id"`) non portavano più la lista pre-partita degli indisponibili
(`lineup` `unavailable` 612 → 214; agosto intatto, mai riscaricato dopo il 12/09) — +1 gara
nuova nel backtest. Campione instabile per costruzione. **c)** Protocollo preregistrato:
griglia dichiarata (k_mercato {0; 0,03; 0,06; 0,09}, k_assenze {0; 0,1; 0,2} senza
preservazione, riposo escluso), copertura minima **≥300 gare e ≥5 leghe su 7** (sotto:
«non testabile»), walk-forward fuori campione, nessuna calibrazione a posteriori, IC
appaiato vs ricetta attuale e vs mercato; se un candidato entra: MODEL_VERSION nuova,
calibrazione ristimata, backtest con il fattore, card con i passi veri. **d)** Decisione
**A/B/C in attesa dell'utente** — le misure sostengono C o B, non A. Gate: **570 test**,
Ruff pulito. Ricetta di produzione intatta.

---

## 2026-10-10 — Hotfix P0: daily rosso post-merge #98 (campione «Le due squadre» gonfiato da `match_info`)

Il `daily` `38005701599` (push del merge) è fallito a `verify_site` con 2 problemi «campione»
(`5781769`, `5781776`): il generatore contava il campione da `match_info` (stato + xG del
solo squadra) mentre l'oracolo [44] `gare_prima` riconta dal **calendario** — il collect
fresco aveva portato `match_info` avanti (gara finita con xG, calendario indietro per cache
HTTP). Diagnosi e correzione in [docs/70](70_daily_rosso_campione_calendario_hotfix_2026-10-10.md):
nuovo `_finite_nel_calendario()` applicato a `season_xg`, `_season_xg_split`, `cards_season`,
`_with_league_ref`; in `season_xg` campione anche ristretto a xG completo di entrambe
(«xG creati» e «xG concessi» sulla stessa serie). **No-op dimostrato**: build prima/dopo
→ 4.250 file, contenuto identico (normalizzati i timestamp); gate **569 test**, Ruff
pulito, `verify_site` **202.969 · 0**, parità **89 schede · pulita**, `resa_375`
**27.255 · 0**. Nuovo test di regressione + un test esistente completato con il calendario
nel fixture. Ricetta di produzione intatta. Prossimo `daily` verde per costruzione; issue
#99 si chiude da sola. La verifica richiesta sul merge è in cima a `docs/13` §9.24.

---

## 2026-10-10 — PR #98 fusa dall'utente: forma con Elo storico e benchmark offline col mercato

Merge eseguito dall'**utente** il 2026-10-09 23:42:02Z (merge commit `98e087b`, 2 genitori:
`5b1119b` su `main` e `551feea` capo del ramo), 16 file, +1.598/−72, 9 commit. In `main`:
**B** ([docs/66](66_la_forma_dice_contro_chi_2026-10-09.md): Elo storico alla vigilia nella
forma, ranghi degli avversari, giudizio solo oltre sd/√n), **D**
([docs/67](67_modello_contro_mercato_offline_2026-10-09.md): benchmark offline modello contro
mercato, 1.071 gare NED1/POR1, ΔRPS +0,008807 grezzo), la **revisione indipendente**
([docs/68](68_revisione_forma_mercato_2026-10-10.md): 246 fit Elo su prefissi troncati, 8.191
confronti senza differenze, [44] con oracolo temporale) e la **coda**
([docs/69](69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md)). Gate dell'ultimo giro:
**568 test**, Ruff pulito, `verify_site` **202.969 · 0 problemi**, `resa_375` **27.255 · 0**,
parità **89 schede · pulita**. Registrazione in `docs/13` §9.24.

**Verifica post-merge (2026-10-10, prima del turno di lavoro):** run su `main` — `tests`
**success** (`38005701607`, push del merge, 2m26s; il check della PR `38005240962` era verde in
2m14s), `daily` schedulato `37996976659` success; il `daily` attivato dal push del merge
(`38005701599`) è **fallito allo step `verify_site`** con 2 problemi «campione» (pagine
`5781769`, `5781776`): il campione della card «Le due squadre» contava una gara finita in
`match_info` con xG ma non ancora finita nel calendario — disallineamento introdotto dal
collect fresco, non un regressione del branch (il gate sul branch era verde). Issue di guasto
**#99** aperta in automatico; nessun commit dati né deploy: il sito è fermo all'ultimo deploy
funzionante. `docs/_audit_modelli.json` è **invariato** dal 2026-09-20 (`e79c377`): snapshot con
calibrazione λ×1,040063 (fitted 2026-09-13, backtest 5.891 righe) — **non** uno snapshot del
2026-10-09; la calibrazione λ×**1,039385** è quella di **produzione** (`calibration.parquet`,
fitted 2026-10-09 22:03:50, n_fit 4.770, backtest 5.895 righe), verificata. Diagnosi e hotfix
nel giro qui sotto.

---

## 2026-10-10 — Coda verificata e handoff post-merge (`arena/eb94e8df`)

L'utente ha chiesto se resta altro in sospeso, se le voci sono quelle giuste e se farle ora o
dopo il merge. **Decisioni registrate: merge della PR #98 dell'utente; nella sessione nuova prima
la decisione sui tre tilt, poi «forza avv.» storica.** Questo turno non ha toccato il codice di
produzione: solo verifiche e documenti ([`docs/69`](69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md)).

**Verificato nel codice, non solo nei documenti.** `absences_tilt`, `rest_tilt` e
`market_value_tilt` esistono in `models/predict.py` e li chiama **solo** `scripts/audit_modelli.py`:
`predict_matches()` no, quindi la card dice ancora il vero. Clubelo è configurato in tutte e 7 le
leghe e **nessuna riga di codice lo usa**; `api.clubelo.com` non è raggiungibile da questo sandbox
(come footballdata per il benchmark live e la sonda sul valore dei titolari): le tre voci sono
bloccate qui, non rimandate per scelta. `docs/58` esiste **due volte** (collisione confermata).

**Misure nuove di oggi.** (1) Rimedio per l'anacronismo di `docs/60` §5: su **4.992** righe della
tabella «Come arrivano», **4.979 (99,7%)** hanno già rango ed Elo storici alla vigilia con la serie
di B — zero fonti nuove, una build + gate. (2) Audit dei modelli **rigenerato offline** sui dati
correnti: il riposo **peggiora ancora** (ΔRPS +0,0000787, IC95 [+0,0000154; +0,000141], 1.591 λ
modificate su 5.895); il valore dei titolari ha **341** gare e solo k=0,03 distinguibile da zero
(il k=0,12 in produzione no); le assenze hanno **98** gare con miglioramento monotono in k, senza
ottimo interno → campione troppo piccolo per promuovere. Il campione delle assenze era 137 nello
snapshot del 2026-09-20: **causa non isolata, da verificare**. (3) I due ΔRPS «modello contro
mercato» del repo sono riconciliati: +0,008807 (grezzo, `docs/67`) contro +0,008527 (calibrato,
audit); ricontando oggi con la calibrazione esce **+0,008530**, il mercato è identico nelle tre
misure (0,178533802717564) e gli SHA-256 degli input coincidono con `docs/67` — il benchmark
rieseguito riproduce ogni valore **bit per bit**. (4) Il commento `predict.py:41` («k calibrato su
5.7k gare») è **ancora falso**: il dato esiste per 341 gare. (5) Il clone è **shallow (1 taglio)**:
`git log --diff-filter=A` attribuisce ogni file al commit base, non leggere lì la provenienza.

**Prossimo passo:** merge della PR #98 (dell'utente); poi voce **G** (tilt: commento falso,
campione assenze, protocollo preregistrato) e **B2** («forza avv.» storica). Nessuna raccolta
sportiva, nessuna modifica di ricetta, nessuna calibrazione nuova in questo turno.

---

## 2026-10-10 — Revisione indipendente della PR #98 (`arena/eb94e8df`)

**Verificato offline:** Elo confrontato con **246 fit su prefissi realmente troncati**,
305 date, **8.191 confronti · 0 differenze**; tutti i **796 riepiloghi** ricontati dal calendario;
RPS/Brier indipendenti su 1.071 gare confermano docs/67. **Conteggi chiariti:** con la data
italiana fissata al 9/10 tornano 446 schede / 760 righe / 2.478 ranghi, ma **169 giudizi**,
non 182. Al 10/10: 464 / 796 / 2.648 / 173. History e fixtures sono gli stessi byte dello
snapshot precedente: corretta in docs/66 l'attribuzione generica ai «dati più recenti».

**Corrette tre lacune dei controlli, dimostrate prima del codice:** [44] accettava un nome
avversario alterato (0 → 1 problema sul caso reale) e poteva condividere una regressione
all'Elo odierno con il generatore (0 → 9); ora usa un oracolo temporale indipendente e
ricontrolla lista, punteggi, sede e pallini dal calendario. Il benchmark accettava una lega
vuota/spazi: ora la rifiuta. **Nessuna modifica a generatori, template, modelli o Parquet**;
JSON del benchmark prima/dopo identico. Dettagli:
[`docs/68`](68_revisione_forma_mercato_2026-10-10.md).

**Gate finali della revisione:** **568 test** (117,41 s), Ruff pulito; `verify_site`
**202.969 · 0 problemi**; resa_375 **27.255 · 0**; parità **89 schede · pulita**. CI del codice
**4d2d5e9** verde (run `38003264484` / `38003261585`). Gate sul sito già generato, non una nuova
build: nessun file di `src/` è cambiato. Il benchmark prima/dopo è identico, inclusi gli IC.

**Prossimo passo:** PR #98 aggiornata; verificare i check dell'ultimo commit e lasciare il
**merge all'utente**. Nessuna richiesta sportiva o nuova calibrazione. Il 182 resta non
riprodotto, non nascosto nel cambio di data; i 169/173 sono verificati dal calcolo indipendente.

---

## 2026-10-09 — Sessione `arena/eb94e8df`: recupero e forma degli avversari

**Fatto:** `f5dbdf3` non conservato nel clone nuovo. Recuperato `8f454cb` dal ramo remoto,
cherry-pick **fd5520d** subito pushato: merge #97 registrato (`docs/13` §9.23).
Ricostruita e verificata **B**, senza rifare le misure esplorative: Elo storico con ricerca
binaria, rango degli avversari, media e giudizio solo oltre sd/√n; stesso elenco per
striscia e riepilogo; [44] ricalcola anche ranghi e soglia. Dettagli e limiti in
[`docs/66`](66_la_forma_dice_contro_chi_2026-10-09.md).

**Gate osservati:** pytest **558**, Ruff pulito; build **464/2.364/7.510**;
verify_site **200.185 · 0 problemi**; resa_375 **27.255 · 0**; parità **89 schede · pulita**.
HTML: **796 righe, 2.648 ranghi, 173 giudizi**, tutte le sette leghe. Non sono i contatori
attesi dell'handoff: finestra italiana passata al 10/10 e dati aggiornati; scarto dichiarato
in docs/66 §5, senza adattare la soglia al conteggio.

**Voce D completata offline:**
[`docs/67`](67_modello_contro_mercato_offline_2026-10-09.md). Modalità `--offline` nel benchmark
esistente: RPS/Brier, IC appaiati, alias su entrambi i lati, join uno-a-uno, copertura e scarti.
**1.071 gare NED1/POR1** (le altre cinque leghe non hanno quote complete): RPS **0,187340**
modello contro **0,178534** mercato, Δ **+0,008807**; Brier **0,563247** contro **0,543645**,
Δ **+0,019602**; IC95 positivi su entrambe le metriche e leghe. Confronto sul **grezzo** fuori
campione, non sul calibrato odierno; provenienza/ripiego delle quote non tracciati per riga.
Quattro test tematici verdi, Ruff pulito. Nessuna nuova raccolta, nessun dato o modello modificato.

**Chiusura del lotto:** suite completa finale **562 passed** (106,85 s), Ruff pulito;
**otto test del benchmark**, compresi i quattro preesistenti. CI del codice finale **d180d09**
verde (run `38000587938`, 1m23s). Gate del sito sopra già verdi sul codice definitivo:
D non modifica il sito. **PR #98 completa**, dal ramo `arena/eb94e8df-football-deep-analyzer`;
verificare sempre i check dell'ultimo commit nella PR prima del merge. Anteprima locale: porta 3000.
**Prossimo passo / decisioni:** **merge esclusivamente dell'utente**. Nessuna richiesta sportiva
aggiuntiva necessaria; non promuovere modelli sulla base di questa misura a due leghe.

---

**Ultimo aggiornamento:** 2026-10-09 (sessione `arena/014bd558`, **revisione della card «Le due squadre»**, richiesto dall'utente: «fai una revisione accurata… deve valere per ogni partita, senza dimenticarne nessuna») — **Documento `docs/64`; ramo `arena/014bd558-football-deep-analyzer`.** Sei difetti misurati e corretti sulla card più densa della scheda (446 schede, 892 riquadri, 7 leghe): **(1) il verdetto xPTS era una soglia fissa a ±2 punti sotto il rumore della misura** — sd(punti − xPTS) su una singola gara = **1,133** (502 gare-squadra Understat), quindi la banda 1σ è 1,13×√gare (±2,5 dopo 5 gare, ±3,0 dopo 7): ora card, narrativa pre-partita e «Clima del club» leggono la stessa `xpts_reading()`, **19 verdetti su 64 spariscono perché erano caso** (0 nuovi) e le **24 squadre con verdetto in card negato dalla narrativa della stessa pagina vanno a 0**; **(2) i numeri di stagione non si rapportavano a nulla** → ogni xG creato/concesso esce con «× la media del campionato», calcolata **sulla stessa fonte** (Understat e FotMob non sono confrontabili: Bundesliga 1,959 contro 1,791 xG per gara-squadra) → **1.784 riferimenti, 2 per riquadro, parità piena anche per Eredivisie e Liga Portugal**; **(3) quattro grafie Understat non agganciate** (`Parma Calcio 1913`, `RasenBallsport Leipzig`, `FC Cologne`, `Borussia M.Gladbach`) facevano confrontare **due fonti xG diverse nella stessa scheda** (3 schede) → 0; **(4) la distinta pre-partita aveva la colonna voto sempre vuota** (0 titolari su 1.210: il voto di gara non esiste ancora) → ⌀ media di stagione **nostra**, che copre 1.195 su 1.210 contro il 68% della `seasonRating` FotMob (38% in Serie A) ed è la stessa base della classifica della scheda → **1.176 celle dove c'era il vuoto**; **(5) «PPDA 8,5 alto»** (l'aggettivo sembrava riferito al numero) → «pressing alto · lega 13,3», soglie e media nel ⓘ, e il `n.d.` dice che il PPDA lo pubblica solo Understat, 5 leghe su 7; **(6) riposo**: la data dell'ultima gara esce sempre (760 riquadri) e la coppa si chiama col suo nome (40) invece del generico «coppe incluse» (37 → 0), via gli aggettivi «ampio»/«corto» che erano una terza soglia incoerente. In più: forma con verso dichiarato («Forma (campionato, gol fatti-subiti)», tooltip «in casa contro Monza: 4-1»), valore dei titolari attribuito alla distinta **FotMob** e non a Transfermarkt (mai interrogato), **piè di card riscritto** (spiegava «Ruolo n.d.», stringa mai stampata, e taceva sui quattro riquadri). **Due ipotesi misurate e scartate (B.10):** il campione xG non è in ritardo sulla classifica (gap 0 su 132 squadre; unica eccezione il Cagliari, dichiarata nel ⓘ) e la griglia dentro `{% if xg %}` non fa sparire il riposo in nessuna scheda reale. **Invariante nuova [44] `check_due_squadre`**: su **tutte** le pagine ricalcola dai Parquet fonte, xG creati/concessi, campione, xPTS/punti/scarto, PPDA e rapporti di lega, e confronta il verdetto con `xpts_reading` → **446 pagine, 892 riquadri, 892 riferimenti, 0 problemi**. **Gate:** `pytest` **549 passed** (+9, fra cui 5 test nuovi e la sezione xPTS di `test_oggi_depth` riscritta), `ruff` pulito, `fda build` **446/2.364/7.498** (4m58s), `verify_site` **0 problemi · 185.117 controlli** (erano 169.967), `parita_schede` **71 schede, nessuna differenza** (min 88% della mediana), `resa_375` **26.628 · 0**. HTML letto a mano su entrambe le fonti (`5749694` Understat, `5781769` FotMob). **Nessuna richiesta alle fonti esterne**; nessun file di dati toccato.

**Secondo giro sulla stessa card (richiesta utente: «verifica che sia tutto corretto… mi sembra che ci sia qualche errore»):** l'aritmetica era giusta — **892 celle ricalcolate dai Parquet con codice indipendente, 0 discordanze**, `len(xg)==len(xga)` ovunque, media xG di lega = media xGA a meno di 1e-15, nessuna gara di coppa in `match_info` — ma **la finestra temporale era sbagliata**: `season_xg` leggeva tutta la stagione raccolta, quindi **750 riquadri su 750 delle schede già giocate (100%) mostravano medie che includevano gare successive alla partita descritta** (mediana 3 gare dal futuro, massimo 7; scostamento mediano 0,23 xG/gara, 90° pct 0,74, massimo **3,39**; 130 riquadri descrivevano squadre che a quella data non avevano ancora giocato), mentre la riga «Forma» della stessa card si fermava correttamente alla vigilia — due finestre diverse a cinque centimetri di distanza (es. Frankfurt–Augsburg del 6/9: «Augsburg 2,14 xG su 4 gare», tre delle quali giocate dopo). **Corretto:** `season_xg`/`season_style`/`_season_xg_split`/`_league_xg_reference` accettano `before` e la scheda passa il proprio calcio d'inizio **anche al riferimento di lega**; allineati tutti i consumatori della pagina (card, «Clima del club», «Fattori», «Scontro tattico», radar) così non esistono due versioni dello stesso numero; **sulle 71 schede pre-partita non cambia nulla** (verificato squadra per squadra). In più, due soglie misurate: il **rapporto di lega** si pubblica da **3 gare** in su (sd xG 1,036 su media 1,692 → errore standard del rapporto ±0,61× dopo 1 gara, ±0,43× dopo 2; 253 riquadri ora lo dichiarano invece di stamparlo) e l'**etichetta del pressing** idem (sd PPDA 6,50 → ±6,5 su 1 gara contro fasce larghe 3 punti; 192 riquadri col solo numero, errore standard sempre nel ⓘ); la **griglia non è più annidata in `{% if xg %}`**, così le 130 squadre senza gare precedenti dichiarano il vuoto e **conservano la casella del riposo** (892 su 892) — chiusa anche la fragilità latente di `docs/64` §6; piè di card che dichiara «tutti i numeri sono fermi alla vigilia di questa partita». **[44] estesa**: ricalcola il campione dal calendario e da Understat **senza passare da `season_xg`**, così una regressione del codice si vede anche con l'HTML coerente col codice rotto (test che simula proprio quella regressione). **Gate rifatti:** `pytest` **553 passed**, `ruff` pulito, `fda build` 446/2.364/7.498 (5m22s), `verify_site` **0 problemi · 184.245 controlli** ([44] 446 pagine · 762 riquadri · 498 riferimenti), `parita_schede` nessuna differenza, `resa_375` **26.565 · 0**. Dettaglio in `docs/64` §7.

**Prossimo passo:** merge della PR (regola D: lo fa l'utente); coda della revisione sezione per sezione — **Panchina e posta in gioco**, **Mercato**, **Vita del club**, **Previsione del modello ensemble**, **Verifica approfondita**, **Confronto di stagione**, **Clima del club**. Residui dichiarati in `docs/64` §6: `match_info.league_id` = 937276 (id di fase) su tutte le gare NED1 — i join di lega vanno fatti via `fixtures`; campione xG una gara avanti sulla classifica per il Cagliari; collisione di numerazione 58/58 ancora da sistemare.

**Ultimo aggiornamento:** 2026-10-09 (sessione `arena/9b461802`, **revisione affidabilità del daily**, richiesto dall'utente: «puoi fare una revisione? puoi controllare se riesci ad aggiornarsi da solo? spesso il daily run fallisce, dà errore») — **Documento `docs/63`; ramo `arena/9b461802-football-deep-analyzer`.** Verdetto misurato (API Actions + riesecuzione locale dei gate): **(1) la pipeline si aggiorna da sola** — 4 run daily verdi consecutivi dal 10-09 01:19 UTC, dati committati a ogni run (ultimo `4a79e2c`, 16:55 UTC) + deploy Pages; alert in loop (issue #94 aperta 22:52, chiusa da sola 01:30). **(2) «spesso fallisce» confermato: 26 rossi su 43 run in 30 giorni (60%)**, tutti fra il 10-02 18:54 e il 10-08 22:40 UTC — 24×`verify_site` «concordanza» (incidente «1 assenti» + feed Sportmediaset 404, corretti il 10-07 in `docs/51`), 1×`parita_schede` (card «Precedenti» sparita sulle gare senza h2h: 1.924 delle 1.989 fixture pre-match, corretto in PR #95 = `docs/62`, mergiato 15:42), 1×`pip` (transitorio, 1/43, nessuna ricorrenza). **(3) Riverifica strutturale delle due classi con misure:** nessun percorso «1 X» vivo nel testo pubblicato (soglie mood ≥2, helper `_n_partite` già induriti, `Calibration.corpus` non pubblicato); fallback Precedenti a 369–376 caratteri = **41% della mediana** di sezione (soglia 25%, sezione finita per costruzione → margino strutturale). **Nessuna modifica di codice (B.10):** tutti i candidati (allungare fallback, intagliare soglie, retry pip, gate non bloccanti) misurati e scartati. Gate locali (tutto tranne collect live, regola B.6): `pytest` **540 passed**, `ruff` pulito, `fda build` **446/2.364/7.498**, `verify_site` **0 problemi · 169.967 controlli**, `parita_schede` **71 schede · nessuna differenza**, `resa_375` **26.628 · 0**. Documenti: nuovo `docs/63`; indice briefing completato (57–62 mancanti); README completato (57, 61, 62, 63). **Rilevato:** collisione di numerazione 58/58 già esistente (residuo dell'incidente di scrittura parallela, commit `ae5ebc9`) — non rinominato (B.10), va sistemato in un giro dedicato.

**Prossimo passo:** pipeline senza azioni bloccanti (monitorare i prossimi run, 4/4 verdi); coda revisione schede (`docs/58` §8.5 / `docs/61` §4): **Panchina e posta in gioco**, **Mercato**, **Vita del club**, **Previsione del modello ensemble**, **Verifica approfondita** (la coppia «Come arrivano» + «I giocatori che decidono» è chiusa da `docs/60`/`docs/61`); anacronismo «forza avv.» (`docs/60` §5); punti aperti `docs/57` §7 (tre tilt non cablati, valore titolari 42/66); collisione 58/58 da rinominare in un giro dedicato.

**Ultimo aggiornamento:** 2026-10-08 (sessione `arena/3e87d2ec`, **revisione della card «Come arrivano»**, richiesto dall'utente: «migliorala o integra cose migliori») — **Documento `docs/60`; ramo `arena/3e87d2ec-football-deep-analyzer`.** La sintesi unica della card (la direzione degli xG recenti) **compariva solo in 28 schede su 66** (servivano 6 gare) e **leggeva solo gli xG creati**: ora scatta da **5 gare** (ultime 3 contro le 2 precedenti, campione dichiarato in pagina → **57 schede su 66**) e copre **creato e concesso** (una squadra in crisi solo in difesa prima non aveva sintesi). In più la riga dello split di sede marca «**(questa gara)**» sul numero che vale per questo incontro (il casalingo della casa, l'esterno dell'ospite), così il confronto giusto è immediato. **Non toccato, e verificato prima:** la lettura xPTS resta dov'è (già in «Le due squadre» e «Clima del club», entrambe ±2 «sopra/sotto atteso» — una terza copia violerebbe `docs/30` e la nota P1.2); i dati xG/xGA sono corretti (le vittorie «da dominata» dell'Atalanta sono reali, verificate su `understat_team_matches`). **[43] aggiornata** (regex sul testo nuovo, controllo da 5 righe, medie su `/(n−3)`, verifica anche il lato concesso: senza, bocciava 114 lati). Test nuovo `test_arrival_trend_da_cinque_gare_su_entrambi_i_lati`. **Aperto:** «forza avv.» è la classifica attuale, non quella alla data della gara (anacronismo dichiarato dal tooltip; serve una classifica storica che il sito non raccoglie). **Gate:** `pytest` **540 passed**, `ruff` pulito, `fda build` **441/2.364/7.494**, `verify_site` **0 problemi · 167.701 controlli** ([43] 132 lati · 698 righe), `parita_schede` senza differenze (min 92%), `resa_375` **26.419 · 0**, `prematch_sections` «Come arrivano» 7,0%. **Nessuna richiesta alle fonti esterne**; anteprima sulla porta 8000. **Nuova regola di progetto (`docs/00` B.10, direttiva utente 2026-10-08):** ogni modifica deve **migliorare, non peggiorare** — si verifica prima di scrivere il codice, e «decidere di non fare» una modifica che peggiorerebbe (come la classifica storica di «forza avv.») è un esito corretto e completo.

**Prossimo passo:** la coda di sezioni da revisionare (`docs/58` §8.5): **I giocatori che decidono**, **Panchina e posta in gioco**, **Mercato**, **Vita del club**, **Previsione del modello ensemble**, **Precedenti**, **Verifica approfondita**; su «Come arrivano» resta l'anacronismo di «forza avv.» (§5 di `docs/60`). Restano aperti i punti di `docs/57` §7 (tre tilt non cablati, valore titolari assente su 42/66).

**Ultimo aggiornamento:** 2026-10-08 (sessione `arena/3e87d2ec`, **terzo giro sulla card «Fattori che spostano la partita»**, richiesto dall'utente: «fai un'altra revisione… non banale, di qualità, quantità e valore, correggi errori e cose non chiare») — **Documento `docs/59`; ramo `arena/3e87d2ec-football-deep-analyzer`.** Rileggendo la card come la vede il lettore: **(1) corretto un errore di misura nel ⓘ del pressing** — il testo spacciava il solo bucket «casa pressa molto» (≤0,75×, 40 gare: 3,43 xG, 1,70 punti) per «una delle due pressa molto più dell'altra», ma quando pressa l'ospite (≥1,33×, 28 gare) gli xG sono 3,03 e la casa 1,07, quasi pari alle gare con pressing simile (3,10 xG, 36 gare); ora i tre bucket sono separati col loro campione, nessuna soglia toccata. **(2) Valore: riferimento di lega nel rendimento per sede** — la cella dava un numero assoluto («1,22 pt/gara in casa») che il lettore non sa collocare; `venue_form()` calcola ora il PPG per sede **della stessa lega** nella finestra e la cella lo porta («2,50 pt/gara in casa (18 gare · **lega 1,44**)»): **24 righe su 24** lo hanno, `resa_375` e parità reggono. **(3) Chiarezza:** l'intestazione non rimanda più a `docs/58` (il lettore del sito non può aprirlo) ma dà il motivo in pagina (punti dell'ospite piatti con i km, correlazione età-punti 0,02, 16 gare con impegno ravvicinato). **(4) La riga «Forma e classifica (contesto)» resa leggibile** (l'utente: «non ho capito come leggerla»): celle «1,20 pt/gara (5 gare) · 11ª · reti ult. 3 −4» invece di «6 pt · 1,20/gara · **GD3** −4» (gergo sparito da 66 pagine, punti grezzi tolti perché fuorvianti senza gare giocate), Delta ridotto al solo «PPG ±X», e impatto **in parole** («contesto a favore di Atalanta (indice +0,63)» / «contesto sostanzialmente pari») con fascia `FACTOR_CONTEXT_PARITY` 0,15 misurata sulle 66 schede (11 pari, 55 con direzione); test nuovo `test_fattori_contesto_leggibile`. **Due candidati valutati e NON aggiunti** (misura insufficiente): regressione gol−xG (storico xG solo 5-7 gare a squadra = rumore) e mismatch su palla inattiva (già in «Scontro tattico» + stesso limite di campione) — nessun fattore nuovo, la card resta a sei + contesto. **Gate (rifatti sulla build nuova):** `pytest` **539 passed**, `ruff` pulito, `fda build` **441/2.364/7.494**, `verify_site` **0 problemi · 167.585 controlli**, `parita_schede` senza differenze (min 92%), `resa_375` **26.419 · 0**, `prematch_sections` Fattori **10,7%** (era 9,5%, per il riferimento di lega). **Nessuna richiesta alle fonti esterne**; nessun file di dati toccato; anteprima del sito sulla porta 8000.

**Prossimo passo:** il peso della card è al 10,7% (secondo aumento consecutivo): se la scheda sembra lunga, la prima candidata a uscire resta «Forma e classifica (contesto)» (`docs/58` §8.1). Il riferimento di lega è un pattern estendibile a pressing e disciplina (non fatto per non gonfiare la card). Restano aperti i punti di `docs/57` §7 (tre tilt non cablati, valore titolari assente su 42/66, ridondanza duello/radar) e la coda di sezioni da revisionare (`docs/58` §8.5).

**Ultimo aggiornamento:** 2026-10-08 (sessione `arena/3e87d2ec`, **secondo giro sulla card «Fattori che spostano la partita»**, richiesto dall'utente: «revisiona in modo accurato la sezione… aggiungi qualità, quantità e valore») — **Documento `docs/58`; ramo `arena/3e87d2ec-football-deep-analyzer`.** Metodo: **prima la misura** — script nuovo `scripts/audit_fattori.py` che misura **nove** blocchi sugli archivi già raccolti (7.467 gare di 3 stagioni, 375 con dettagli, 333 con l'arbitro, 162 con PPDA), nessuna richiesta alle fonti. **Due fattori nuovi, entrambi misurati prima di entrare:** **«Rendimento per sede»** (punti/gara **in casa** della casa contro **in trasferta** dell'ospite, finestra 365 giorni, minimo 5 gare per sede, soglia 0,50 pt/gara — 6.307 gare: 10,6% di vittorie casalinghe con ≥1 punto a favore dell'ospite, 68,2% con ≥1 a favore della casa, quote implicite normalizzate 12,0% e 70,4%; **24 righe su 66**) e **«Disciplina e arbitro»** (gialli e falli/gara delle due squadre + scarto dell'arbitro dalla media di lega; 333 gare: arbitri sopra la mediana dichiarata **3,80** gialli/gara contro **3,19**, correlazione 0,24; sui **rigori** la media di carriera non predice nulla — 0,271 contro 0,216, correlazione 0,05 — e la riga lo dice; soglie Δ 0,8 gialli/gara e ±10% su ≥20 gare in carriera; **28 righe su 66**). **Tre candidati misurati e NON pubblicati**, con la card che lo dichiara: distanza della trasferta (punti dell'ospite 1,03-1,38 senza andamento, 375 gare), età media dei titolari (correlazione 0,017), turnover per impegno ravvicinato (n=16 e segno opposto all'atteso); più il meteo (già in una card sua: `docs/56` §3) e il cambio di allenatore (letteratura: effetto nullo dopo ~10 gare). **Qualità:** il **campione entra nelle celle** dei fattori di stagione («21,3 (5 gare)» invece di «21,3»), l'**ordine delle righe è fisso e dichiarato** (`FACTOR_PRIORITY`, prima un peso ad hoc faceva scavallare il mercato a 10,1), i **ⓘ citano misure nostre** (mercato 1,87 contro 1,43 punti/gara su 363 gare; pressing 3,43 contro 3,10 xG su 162; Δ riposo **senza segnale coerente** su 7.243 gare, quindi la riga resta sul rischio infortuni), la **quota implicita dell'audit è normalizzata** per l'overround (73,2% → 70,4%), e `verify_site` non cade più con `IndexError` sul riepilogo quando un messaggio non ha «: » (nascondeva i problemi invece di stamparli). Verificato anche il claim della card: `absences_tilt`/`rest_tilt`/`market_value_tilt` sono chiamati **solo** da `scripts/audit_modelli.py`, quindi «non cambiano la previsione salvata» resta vero. **[41] estesa**: due etichette e due parole chiave nuove (anche i fattori nuovi non possono sparire in silenzio), unità di soglia nuove (gare, pt/gara, gialli/gara, %) e controllo del **campione nelle celle**. **Effetto sulle pagine (66 schede):** righe **177 → 229** (3 per scheda invece di 2,7), nessun fattore non nominato (24+23+19 = 66 per la sede), peso della card **6,6% → 9,5%** del visibile, mediana visibile **21.680 → 22.355** caratteri, parità invariata (min 92% della mediana). **Gate (rifatti dopo l'ultima modifica al sorgente):** `pytest` **538 passed**, `ruff` pulito, `fda build` **441/2.364/7.494**, `verify_site` **0 problemi · 167.585 controlli** ([41] 66 schede), `parita_schede` senza differenze, `resa_375` **26.419 misure · 0 problemi**, `prematch_sections` Fattori 9,5%. **Nessuna richiesta alle fonti esterne in questa sessione**; nessun file di dati toccato.

**Prossimo passo:** decidere i punti aperti di `docs/58` §8 (peso della card al 9,5%, riga fuori tabella fino a 6 voci, nota sul caldo in «Arbitro e meteo») e riprendere la revisione sezione per sezione: **Come arrivano**, **I giocatori che decidono**, **Panchina e posta in gioco**, **Mercato**, **Vita del club**, **Previsione del modello ensemble**, **Precedenti**, **Verifica approfondita**. Restano aperti i punti di `docs/57` §7 (tre tilt non cablati, valore titolari assente su 42/66, ridondanza duello chiave/radar).

**Ultimo aggiornamento:** 2026-10-07, notte fonda (sessione `arena/18575843`, **registrazione del merge #92**) — su ordine esplicito dell'utente la PR **#92 è fusa in `main`** alle **23:12:34Z** dall'agente in deroga (merge commit **`ed4b119`**; solo documenti, 4 file, +54/−13; record in `docs/13` §9.22). Verifiche pre-merge tutte superate: check `test` verde su `e53d50b` (run `37700026749`), PR `MERGEABLE · CLEAN`, albero pulito, 1 solo commit sul ramo `arena/aaa98843-football-deep-analyzer`. **Nessun run attivato dal merge** (verificato: nessun `tests`/`daily` dopo le 23:12:34Z — `paths-ignore: docs/**`), come atteso per le PR solo-documenti; produzione ferma ai dati in `0d9fc28`. **Nessuna richiesta alle fonti fatta a mano** in questa sessione; nessun file di dati toccato.

**Prossimo passo:** la **terza coppia** della revisione delle schede — **«Come arrivano» + «I giocatori che decidono»** — con lo stesso metodo (misura prima/dopo → correzione → invariante o test); poi Panchina e posta in gioco, Mercato, Vita del club, Previsione del modello ensemble, Precedenti, Verifica approfondita. Restano aperti i punti di `docs/57` §7 (tre tilt non cablati, valore titolari assente su 42/66, ridondanza duello chiave ↔ radar).

**Ultimo aggiornamento:** 2026-10-07, notte fonda (sessione `arena/aaa98843`, **registrazione del merge #91**) — su ordine esplicito dell'utente (*«ok fai merge»*) la PR **#91 è fusa in `main`** alle **22:54:01Z** dall'agente in deroga (merge commit **`f4c4eb6`**; 15 file, +1.902/−500; record in `docs/13` §9.21). Verifiche pre-merge tutte superate: check `test` verde su `e84bf1d` (run `37698233647`), PR `MERGEABLE · CLEAN`, albero pulito, 6 commit. **Il push del merge ha attivato i run di produzione e sono entrambi verdi:** `tests` (`37699054427`) e `daily` (`37699054654`, 22:54:05 → 23:02:25Z, tutti e 17 gli step: `collect → predict → backtest → simulate → build`, `verify_site`, parità delle schede, resa a 375 px, **deploy Pages**), che ha committato i dati in **`0d9fc28`** (8 Parquet; `insights` rimesso a nuovo: 23 testi sostituiti sulle gare programmate). Le due coppie della revisione (prima: «Analisi pre-partita» + «Fattori»; seconda: «Scontro tattico» + «Fatti rilevanti») sono quindi **in produzione**: 66 schede pre-partita coi fatti in due gruppi dichiarati (258 ricalcolati da noi + 68 FotMob-fotografia), radar senza gli 80 «50 (n.d.)» inventati, banner di copertura costruito dai dati, 0 intervalli col trattino ASCII in tutto il sito. **Nessuna richiesta alle fonti fatta a mano**: le uniche raccolte sono quelle del `daily` attivato dal merge.

**Prossimo passo:** la **terza coppia** della revisione delle schede, con lo stesso metodo (misura prima/dopo → correzione → invariante o test) e l'ordine già dichiarato: **Come arrivano**, **I giocatori che decidono**, **Panchina e posta in gioco**, **Mercato: arrivi e partenze**, **Vita del club**, **Previsione del modello ensemble**, **Precedenti**, **Verifica approfondita**. Restano aperti i punti di `docs/57` §7 (tre tilt non cablati, valore titolari assente su 42/66, ridondanza duello chiave ↔ radar).

**Ultimo aggiornamento:** 2026-10-07, notte (sessione `arena/aaa98843`, revisione delle schede partita — **seconda coppia, «Scontro tattico» + «Fatti rilevanti»**, richiesta dall'utente prima del merge) — **Documento `docs/57` §8-§9; ramo `arena/aaa98843-football-deep-analyzer`, commit `f8a29eb` (catena `a6e829e` → `f8a29eb`), PR #91 estesa verso `main` (merge = utente, regola D).** **«Scontro tattico»:** il radar stampava `50 (n.d.)` dove il dato mancava — **80 celle** (su 66 schede) con un numero inventato e la barra al 50%, es. Feyenoord–AZ con pressing **e** profondità assenti in entrambe le colonne → ora `n.d.` senza barra né numero (`norm_*` → `None`); piè di card «100 = migliore in lega su quella metrica» **falso** (le ancore sono fisse: attacco 0,5×→0 e 1,5×→100, difesa invertita, PPDA 8→100 e 20→0, profondità 2→0 e 10→100, palle inattive 10%→0 e 60%→100) → riscritto + **un ⓘ per riga** con ancora, verso e unità (compreso «palle inattive % = dipendenza, non qualità»); banner fisso «Confronto limitato a xG e profondità» **anche dove mancava la profondità** (145 delle 162 schede col banner mancavano di tutto il blocco Understat) → nota costruita dai valori presenti («manca PPDA, PPDA concesso, passaggi profondi e passaggi profondi subiti per entrambe le squadre», 145 schede, o «per una delle due», 17); intervalli col trattino ASCII → **en dash**, con l'invariante `RANGE_ASCII` in [27] (0 in tutto il sito): le **375** occorrenze vere erano in `#lettura` («xG 0,75-0,94») e **1** in `info.html` («0,19-0,20», mentre `accuracy.html` scriveva già «0,19–0,20»), mentre la misura «101 in `#scontro`, 90 in `#scomposizione`» scritta in §6 **non si riproduce** ed è stata corretta nel documento. **«Fatti rilevanti»:** i fatti FotMob sono una **fotografia scattata alla raccolta** e invecchiano — **79 fatti su 176 verificabili non tornavano** coi nostri risultati (Atalanta «4 gol nelle ultime 5» contro 3 reali; «Athletic Club imbattuta da 5» con una sconfitta dentro) e la famiglia «forma» pesava **181 delle 272 voci pubblicate (67%)** → non si pubblica più da FotMob: al suo posto il **ricalcolo** dalle nostre gare di campionato (`form_facts`, finestra 5, minimo 3 gare), con **due gruppi dichiarati** in card (`id="fatti-dati"`: «dai nostri risultati · campionato, ricalcolati a ogni build»; `id="fatti-fotmob"`: «fotografia al momento della raccolta»); il record «maggior numero di porte inviolate (N)» si pubblica **solo se N regge al ricalcolo** (numero nostro **e** massimo di lega — 11 su 11 verificate, 0 rifiutate); `stato.html` aggiornato (etichetta «Curiosità» → «Fatti rilevanti», contatori nuovi: **188** voci di famiglia ricalcolate da noi, **0** record rifiutati). **Effetto sulle pagine (66 schede pre-partita):** voci **272 → 326** (258 nostre · 68 FotMob), 59 schede con entrambi i gruppi e 7 col solo gruppo nostro (senza il ricalcolo sarebbero rimaste senza card); peso della card 4,0% del visibile, mediana visibile della scheda **21.084 → 21.680** caratteri. **Verificatori nuovi:** **[42]** rifà le voci «nostre» dai Parquet e ricalcola i record (258 + 68 voci, 535 controlli) e rifiuta la famiglia «forma» nel gruppo FotMob; **[22b]** ricalcola le 5 barre del radar (66 schede). **Extra fuori dalle due coppie:** il test `test_transfer_window_stesso_movimento_con_ora_locale` era dipendente dall'ora di esecuzione (falliva dopo le 22 UTC, `06/10/2026` contro `05/10/2026`): ora l'ora del campione è fissa a metà mattina. **Gate (rifatti dopo l'ultima modifica al sorgente):** `pytest` **534 passed**, `ruff` pulito, `fda build` **441/2.364/7.496**, `verify_site` **0 problemi · 164.729 controlli** ([22b] 66 radar, [40] 441, [41] 66, **[42] 258+68 voci**), `parita_schede` senza differenze (66 schede, 24 id, min 19.697 · mediana 21.680), `resa_375` **26.424 misure · 0 problemi**, `prematch_sections` «Scontro tattico» 9,2% · «Fatti rilevanti» 4,0%. **Nessuna richiesta alle fonti esterne in questa sessione** (nessun `collect`, nessuna sonda, nessun daily manuale); nessun file di dati toccato; anteprima del sito sulla porta 3000.

**Prossimo passo:** restano da revisionare le altre sezioni della scheda con lo stesso metodo — **Come arrivano**, **I giocatori che decidono**, **Panchina e posta in gioco**, **Mercato: arrivi e partenze**, **Vita del club**, **Previsione del modello ensemble**, **Precedenti**, **Verifica approfondita** — più i punti aperti di `docs/57` §7 (tre tilt non cablati, valore titolari assente su 42/66, ridondanza duello chiave/radar). Il merge della PR #91 resta dell'utente.

## 2026-10-09 — PR #97 fusa: «Le due squadre» in produzione

Merge eseguito dall'agente su ordine esplicito dell'utente («fai merge»), 21:00:40Z, commit
`3cef641` (13 file, +1.853/−70). In produzione: finestra alla vigilia su 750 riquadri, infermeria
che torna con le righe stampate, ruolo sempre dichiarato, **pressing in tutte e 7 le leghe**
(caselle piene 604 → 760 su 892), invariante **[44]**. Deroga registrata in `docs/13` §9.23.
Coda e prompt per la sessione nuova: `docs/65_handoff_e_coda_fonti_2026-10-09.md`.

## 2026-10-09 — Pressing su tutte e 7 le leghe (PR #97)

Prima fonte nuova del giro «dati, poi sezioni»: l'indice di pressione calcolato dalle statistiche
gara FotMob (passaggi concessi nella metà campo avversaria per azione difensiva) sostituisce il
PPDA di Understat come numero in evidenza della casella «Pressing · riposo». **288 caselle su 892
dicevano «n.d.»** (tutta l'Eredivisie e tutta la Liga Portugal): ora le caselle piene sono
**760/892 con la stessa copertura in tutte e 7 le leghe**. Il PPDA resta nel ⓘ dove c'è, le
etichette escono solo oltre l'errore standard (151), e [44] ricalcola tutto dai Parquet.
Validazione e soglie in `docs/64_le_due_squadre_2026-10-09.md` §9.

## 2026-10-09 — «Le due squadre», terzo giro: l'infermeria (PR #97)

Revisione della card sulla scheda PSV–Heerenveen (`5781762`). Forma, xG, xPTS, pressing e riposo
**verificati corretti** (19 giorni di pausa reali, coppe incluse). Corretti tre difetti
nell'infermeria, validi su tutte le schede: il **totale non era la somma delle righe** (101
pannelli su 118, max 0,67 xG+xA) → ora somma le cifre pubblicate; il badge non diceva **quanti
assenti hanno minuti** → «(5 su 9 con minuti)» su 83 badge; **197 righe su 507 senza ruolo** →
pillola «ruolo n.d.» con spiegazione. Invariante **[44]** estesa ai due controlli. Dettagli:
`docs/64_le_due_squadre_2026-10-09.md` §8.
