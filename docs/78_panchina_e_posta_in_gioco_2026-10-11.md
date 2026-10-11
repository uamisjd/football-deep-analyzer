# 78 — Card «Panchina e posta in gioco»: controllo a 360 gradi (2026-10-11)

Richiesta dell'utente: «dobbiamo verificare e revisionare come il sito ci presenta le schede di
ogni partita — vai alla revisione di "Panchina e posta in gioco", fai un controllo a 360 gradi
di cosa ci propone e come lo propone, controlla cosa si deve aggiustare e aggiungere». Stesso
metodo di `docs/76` (card «Le due squadre»): per ogni punto **misura → correzione →
invariante o test**, e alla fine i gate. La misura vive in `scripts/audit_panchina.py`, che
legge l'HTML come sta e ricalcola tutto dai Parquet con strade **diverse** da quelle del
generatore (mai `bench_deep`).

Ambito: la card è solo sulle schede pre-partita. Al mattino del 2026-10-11 erano **104 schede
(208 celle-squadra)**; dopo il §8 sono **82 (164 celle)** — le altre erano gare già giocate.

## §1 — Difetto: la classifica virtuale copriva due esiti e ignorava i punti dell'avversaria

**La misura.** La riga verde pubblicava «con una vittoria Nº · con una sconfitta Mº»: mancava il
pareggio, e nel computo i punti del risultato andavano solo alla squadra della cella. Nella
sconfitta l'avversaria incassa i 3 punti, quindi può scavalcare: **36 celle su 208** avevano la
posizione «con una sconfitta» sbagliata (Feyenoord 1º→2º, Napoli 6º→7º, Sunderland 16º→17º).
«Con una vittoria» era già esatta perché i punti dell'avversaria restano 0.

**La correzione.** `_virtual(my, opp)` conta i punti di **entrambe** le squadre di questa
partita (vittoria 3–0, pareggio 1–1, sconfitta 0–3), tenendo ferme le altre gare in sospeso e
la differenza reti attuale; la riga dichiara i tre esiti: «con una vittoria 10º · con un
pareggio 11º · con una sconfitta 11º (classifica virtuale, altre gare in sospeso)».

**Invarianti e test.** Il verificatore [19] ricalcola la posizione con `posizione_virtuale()`
a livello di modulo, senza riusare la funzione del generatore — il gate che riusa la funzione
sotto esame non può vedere gli errori che stanno *dentro* la funzione. Test:
`test_bench_deep_profilo_rendimento_e_virtual` (i tre esiti, con la Roma che incassa i punti
nella sconfitta), `test_card_panchina_tre_esiti_eta_dichiarata_e_orologio`.

## §2 — Etichette che contraddicevano il numero stampato due righe sotto

**La misura.** Su **23 celle** l'etichetta diceva «corsa all'Europa» mentre la riga sotto
stampava `UCL (prime 4)` ≥35% — con 4 posti UCL quel traguardo è la Champions, non «l'Europa»
( Dortmund 1º con 92% compreso). E su metà delle celle senza postura in bilico l'aggettivo di
posizione contraddiceva la classifica stampata accanto (posizione reale fuori dall'intervallo
7ª–13ª su 47 celle su 101).

**La correzione.** Soglie dichiarate, 0,15 / 0,35: titolo ≥15% → «corsa al titolo»; altrimenti
probabilità UCL ≥35% → «corsa alla Champions»; salvezza-in-coda (`p_rel`) ≥35% → «lotta
salvezza»; ≥15% → «zona salvezza non lontana». Se nessuna postura è in bilico, al posto di un
aggettivo va **il numero della simulazione**: «proiezione: 11,4º posto in media», la stessa
«Media pos.» della pagina Proiezioni. Distribuzione dopo la correzione (164 celle): proiezione
79 · lotta salvezza 28 · zona salvezza non lontana 25 · corsa alla Champions 20 · corsa al
titolo 12; posizione reale mediana: titolo 2º, Champions 5º, salvezza 16º, zona 15º,
proiezione 9º.

**Invarianti e test.** [19] ricalcola l'etichetta dalla simulazione; `audit_panchina.py`
incrocia etichetta × posizione reale; test
`test_bench_deep_etichetta_champions_e_proiezione` (con `ucl_legacy is False` → Champions;
fallback → proiezione; snapshot legacy senza `top_n` → «dato storico»).

## §3 — Celle che tacevano senza dire perché

**La misura.** **108 celle su 208** dicevano un «n.d.» muto sull'età media dei titolari: non si
distingueva «FotMob non ha ancora pubblicato la distinta» da «dato perso». **6 celle** non
pubblicavano il rendimento del nuovo allenatore (Valencia/Aguirre da Oscar Sanchez,
M'gladbach/Blessin da Lichte): un subentro appena avvenuto non ha gare concluse, e la cella
taceva.

**La correzione.** Età: «distinta non ancora pubblicata» con tooltip (la distinta arriva a
ridosso del calcio d'inizio) quando la formazione non c'è; «n.d.» solo se la formazione c'è ma
l'età manca. Rendimento: flag `coach_ppg_absent` → «rendimento: nessuna gara finita con lui in
panchina», con tooltip che dice quando comparirà.

**Invarianti e test.** [19] verifica l'età («n.d.» / «distinta non ancora pubblicata») e il
segnaposto del rendimento; test `test_card_panchina_rendimento_dichiarato_per_un_subentro`,
`test_bench_deep_subentro_senza_gare_dichiarato`.

## §4 — Ripetizioni fra card: chi dice cosa

**La misura.** La notizia del cambio di panchina compariva in due card su 11 schede, e la voce
«Panchina nuova» due volte su 2. Clima e «Da sapere» raccontavano lo stesso fatto della card
panchina senza rimandarla.

**La correzione.** Una sola voce per fatto; clima e «Da sapere» fanno **segnale + rimando**
(«…è la nuova guida — i dettagli in «Panchina e posta in gioco»»). Il conteggio delle gare dal
subentro resta in una riga sola.

## §5 — Nove celle stampavano il codice nazione grezzo

**La misura.** Le distinte raccolte usano **116 codici ISO** diversi; la mappa italiano→nome ne
copriva 35. Nove celle pubblicavano «· 45 anni · ROU», «· 49 anni · BIH» (×2), «· 44 anni ·
DEN» (×2), «· 73 anni · CHI» (×2), «· 48 anni · USA» (×2).

**La correzione.** `_COUNTRY_IT` completa sui 116 codici + `country_it()`: un codice nuovo non
mappato **non finisce a schermo** (la cella mostra la sola età, come quando la fonte la nazione
non la pubblica). Misura dopo la build: 164/164 celle con la nazione in italiano (era 199/208).

**Invarianti e test.** [19] rifiuta `anni · [A-Z]{3}` nella cella allenatore;
`audit_panchina.py` conta i codici grezzi (deve restare 0).

## §6 — «salvezza N%» era «retrocessione N%»: significato invertito su tutte le celle

**La misura.** La coda della riga «Posta in gioco» stampava `p_rel` sotto la parola
**salvezza**, ma `p_rel` è la probabilità di finire nei posti rossi della lega
(`season_sim.py`: `pos > n − rel_count`; `REL_COUNTS` = 3 «dirette + spareggio» per POR1/NED1/
FRA1) — la colonna **«Retro»** della pagina Proiezioni, la stessa che la CLI stampa come
«retro». Il numero era giusto, la parola invertita: l'Estoril 18º compariva come «salvezza
52%» (51,5% di retrocedere) e il Viseu 5º come «salvezza 0%» (0,3%).

**La correzione.** «retrocessione N%» nella cella e nella nota («retrocessione» è la colonna
«Retro» della pagina Proiezioni — i posti rossi di ogni campionato, spareggio compreso per
POR1, NED1 e FRA1), attesi allineati in [19] e nell'audit, asserzione di regressione in
`test_card_panchina_tre_esiti_eta_dichiarata_e_orologio` (`retrocessione \d+%` presente,
`salvezza \d+%` assente).

## §7 — Precedenti: dall'archivio vero, e gli incroci fra **allenatori** (richiesta dell'utente)

**La misura.** Le due righe «precedenti» della cella allenatore leggevano l'archivio delle
**distinte**, che per coppia di squadre copre una sola gara: con le soglie di allora (≥3 gare
contro l'avversaria, ≥2 contro il suo allenatore) non si accendevano su **nessuna** delle 208
celle — 164 celle con 0 gare in archivio, 44 con 1.

**La correzione, prima parte (club).** Il bilancio con l'avversaria ora viene dall'**archivio
dei testa-a-testata** già raccolto per ogni partita (`h2h.parquet`: 9.730 righe, 487 contesti,
mediana 20 incontri per coppia, massimo 44): la stessa fonte della card «Testa a testa», non
l'albo d'oro completo — e la nota lo dichiara. Copertura dopo la build: **160 celle su 164**
(4 celle, 2 partite — Coventry–Newcastle e Le Mans–Toulouse — non hanno ancora l'archivio
h2h). Esempio: «bilancio con Juventus nel nostro archivio: 2V 5N 23P su 30 gare».

**Lo sbaglio che l'utente ha colto.** Dopo la risposta «non possiamo dare un archivio al
sito?», la riga «incroci in panchina con l'allenatore avversario» era stata implementata
contando le gare del **club** in cui capitava l'allenatore avversario: pubblicava cioè lo
scontro fra le due squadre sotto un'etichetta che prometteva i precedenti fra i due
allenatori. Segnalato dall'utente («quello che hai messo sono solo gli scontri tra le due
squadre»): la definizione corretta è **gare in cui i due si sono trovati su panchine opposte,
su qualunque coppia di club, sempre prima di questa partita**, con l'esito letto dalla panchina
del nostro allenatore.

**Cosa dice l'archivio panchine oggi.** 441 partite (7 agosto → 21 ottobre 2026), 2 allenatori
per partita, mediana 6 gare per allenatore, un solo allenatore con due squadre nel periodo:
**0 incroci reali** fra le coppie dei 104 anticipi (nessuna coppia si era ancora incontrata in
questa stagione). La riga quindi **non si pubblica** — e non deve: meglio il silenzio di un
numero finto. Il codice resta, corretto e coperto da test (`test_bench_deep_...` costruisce un
incrocio vero: l'allenatore dell'Inter oggi incontrava quello della Roma su Milan–Roma), e si
accenderà quando l'archivio conterrà un incrocio (es. le gare di ritorno nella seconda metà di
stagione). Un bilancio **di carriera** fra due allenatori richiederebbe il backfill delle
distinte delle gare h2h da FotMob: non misurabile da questo sandbox, da decidere a parte.

## §8 — Difetto trovato mentre si misurava il §7: 22 schede «pre-partita» per gare già giocate

**La misura.** Il 2026-10-11, **22 schede (44 celle)** erano rese come «Analisi pre-partita»
per partite che il **calendario dava già finite**: i dettagli (`match_info`) erano
un'istantanea vecchia (14 righe «scheduled», 8 «live» — la finestra dei dettagli vive di budget
e resta indietro, il calendario si riaggiorna a ogni run) e la pagina si fidava dei dettagli.
Peggio: col taglio `ko <= kickoff` la card contava **quella stessa gara** fra i «precedenti» —
per Genoa–Fiorentina (5749693, 1-0) la cella pubblicava «un solo incrocio in panchina con
Paolo Vanoli: 1V 0N 0P»: il risultato della partita in corso spacciato per un precedente.

**La correzione.** Due regole, entrambe con nome e motivo nel codice:

1. **Una partita finita lo resta**: `status = "finished"` se lo dice il **calendario**, poi si
   guardano i dettagli. Misura dello store: nessun caso inverso (nessun `match_info` «finished»
   con calendario non finito), quindi la regola non ha controindicazioni.
2. **Il passato è rigorosamente prima di questa partita**: `fin.ko < kickoff` e
   `ct.ko < kickoff` per rendimento e precedenti (con `<=` la partita stessa entrava nel
   campione). Vale anche per `_h2h_core`, che già usava `<`.

**Effetto misurato.** Schede pre-partita **104 → 82** (le 22 gare finte ora si leggono come
«Finale», con punteggio e sezioni post-partita: 5749693 → «Genoa - Fiorentina, 1 - 0 Finale»);
righe «incrocio in panchina» pubblicate **44 → 0**; card solo su gare vere da giocare.

**Invarianti e test.** [19] fallisce se una pagina con la card ha il calendario «finished»
(«scheda pre-partita per una gara che il calendario dà finita»);
`audit_panchina.py` conta le pagine pre con calendario finito (deve restare 0);
`test_scheda_di_una_gara_finita_non_resta_pre_partita` (calendario finito + dettagli
«scheduled» → pagina «Finale», niente card); `test_bench_deep_non_conta_la_partita_stessa`
(una goleada 7-0 della partita stessa non entra nel rendimento).

## §9 — Gate (tutti rifatti dopo l'ultima modifica al sorgente)

- `pytest`: **598 passed** (0 falliti).
- `ruff check`: pulito sui file toccati.
- `fda build`: **493 schede** · 2.364 fixture · 7.560 giocatori (build 2026-10-11, 4 min 24 s).
- `scripts/verify_site.py`: **nessun problema · 233.508 controlli numerici** (include [19]
  riscritto: coach, permanenza, rendimento, precedenti, incroci, etichette, distanze,
  posizione virtuale a 3 esiti, età, nazioni, più l'invariante «niente card su gare finite»).
- `scripts/audit_panchina.py`: **0 scostamenti** dal ricalcolo indipendente su tutte le
  famiglie (nome_coach, tenure, ppg, precedenti, incroci, table, virtuale, etichetta, età,
  nazioni) e **0 silenzi** (nessuna riga assente senza dichiarazione).
- `scripts/parita_schede.py`: **82 schede pre-partita · struttura identica** (26 id, 14 voci
  d'indice), nessuna differenza.
- `scripts/resa_375.py`: **28.467 misure · 0 problemi a 375 px**.

## §10 — Punti aperti

- **Incroci fra allenatori**: riga corretta ma senza dati oggi (0 incroci reali su 164 celle);
  si accende con l'archivio. Un bilancio di carriera richiede il backfill delle distinte
  storiche da FotMob (rete + budget: decisione separata, non eseguibile dal sandbox).
- **Permanenza**: «panchina invariata da N gare nel nostro archivio» — il «nel nostro
  archivio» resta, perché la misura è quella (l'archivio distinte, non la carriera).
- **4 celle POR1** con tutte le percentuali ≤1 (5887645/46/48/49): oneste dopo il §6
  («titolo 0% · UCL (prime 0–1) 0% · retrocessione 0%»), senza arrotondamenti finti.
- **4 celle senza archivio h2h** (2 partite): il bilancio non si pubblica, il resto della
  cella resta; si riempiranno alla prossima raccolta.
