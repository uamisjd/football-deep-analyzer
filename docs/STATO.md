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
