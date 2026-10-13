# Stampa in lingua originale: sintesi nostra, fonte e lingua dichiarate (2026-10-13)

**Domanda dell'utente che apre il lavoro:** «perché per le squadre estere non usiamo fonti estere?»
**Decisione dell'utente (13/10/2026, via `ask_user`):** *«Cambio politica: fonti estere + sintesi
nostra»* — raccogliere le fonti estere (olandesi e portoghesi) e pubblicare una riga di sintesi in
italiano scritta da noi, con fonte e lingua originale dichiarate.

Questa è una **deroga dichiarata** alla regola della lingua (`docs/00` §E, `docs/25` §5), limitata
alle leghe che dichiarano un'edizione locale (`config/leagues.yaml`). I due paletti dell'utente sono
vincolanti: **non si traduce un titolo** e **non si riscrive il testo di terzi**.

---

## 1. Il buco, misurato prima di scrivere codice

| Misura (13/10/2026) | Valore |
|---|---|
| schede pre-partita in archivio | 58 (di cui **NED1 9 e POR1 1**) |
| schede NED1/POR1 con almeno una voce nella card «Vita del club» | **0 su 10** |
| voci esaminate sui 10 lati NED1/POR1 nella finestra | 263 |
| di cui scartate perché **in un'altra lingua** | 46 |
| di cui «servizio o cronaca» (dirette, formazioni, pronostici) | 165 |
| di cui bassa reputazione | 37 |
| pubblicabili con i criteri italiani | **0** |

**Anti-ipotesi, provata e superata.** Se il buco fosse colpa del filtro lingua, disattivandolo
dovrebbero uscire voci. Prova fatta il 13/10 su tutti i lati NED1/POR1 con `is_italian_news`
forzato: **0 pubblicabili**. Il motivo è il materiale: le 46 voci «non italiane» in archivio non
sono stampa estera, sono pagine di servizio di testate italiane (Eurosport «Punteggi & Highlights»,
Sky, la Repubblica) e siti di pronostici (Top Scommesse, Bottadiculo), concentrate su due club
(Sparta Rotterdam 15, Go Ahead Eagles 15, AZ 7, il resto ≤2). La stampa italiana **non scrive** dei
club che giocano questo fine settimana: verificato a mano su `diretta.it/news/eredivisie` (~8 pezzi
dal 30/08, tutti di lega o su nomi grossi) e su `sport.sky.it/calcio/eredivisie` (sezione esistente,
contenuti scarni).

## 2. Cosa portano le edizioni locali (misura del 13/10, feed reali)

Due letture a mano dei feed di Google News in edizione locale:

- **olandese** (`hl=nl&gl=NL&ceid=NL:nl`): stampa vera e quotidiana sui club — AD.nl, NOS,
  Voetbal International, de Stentor, Leeuwarder Courant, FeanOnline, VoetbalPrimeur;
- **portoghese** (`hl=pt&gl=PT&ceid=PT:pt`): A Bola, SAPO, Record, zerozero.pt, o minho.

Sul campione di **27 titoli reali** letti il 13/10 (primi item di ogni feed, non l'intero feed):

| Club | voci esaminate | non classificabili | di altre squadre | **pubblicabili** |
|---|---|---|---|---|
| SC Heerenveen | 19 | 11 | 5 | **3** |
| Sparta Rotterdam | 19 | 11 | 5 | **3** |
| AZ | 19 | 11 | 7 | **1** |
| SC Braga | 8 | 7 | 0 | **1** |

Prima: **0**. Dopo: **1–3 voci per club**, tutte con titolo originale citato. I titoli sono
conservati in `tests/fixtures/estero_2026-10-13.json` e la misura è congelata in un test, così se il
vocabolario deriva ce ne accorgiamo.

## 3. Come è fatto

**Raccolta** (`src/fda/sources/news.py`, `src/fda/collect.py`). Le leghe dichiarano le edizioni
locali in `config/leagues.yaml` (`news: {editions, lingua, label}`); oggi solo NED1 (`nl`) e POR1
(`pt`). L'edizione italiana resta la prima per tutte. Ogni riga raccolta porta la lingua
dell'edizione (colonna `language` nella tabella `news`); le righe scritte prima di questa modifica
sono trattate come italiane, perché erano l'unica edizione interrogata. Costo: **168 richieste** a
run completo (132 italiane + 36 locali), dentro il tetto di 200; con la cache a 12 h sono ~2 fetch
reali per squadra al giorno.

**Sintesi** (`src/fda/site/estero.py`, 9 temi in priorità fissa: infortunio, squalifica, contratto,
mercato, panchina, società, stadio, dichiarazione, forma). Da un titolo originale si ricava
un'**etichetta italiana di tema** (vocabolario chiuso), la **prova** (le parole originali che
l'hanno attivata) e una **nota fissa** che dice cosa significa per la partita. Le pagine di servizio
(dirette, formazioni, riepiloghi, pronostici) sono escluse in entrambe le lingue; un titolo che il
vocabolario non riconosce **non si pubblica** — un'etichetta inventata sarebbe peggio di un titolo in
olandese. Il modulo non chiama la rete e vive in `site/`, non in `sources/`: l'elenco delle fonti
pubblicato in `info.html` resta il contratto dei moduli che fanno richieste (`tests/test_site.py`).

**Card** («Vita del club», `docs/106`). Blocco separato, con classe `news-estera` per non toccare gli
oracoli del bollettino italiano. Per ogni squadra: intestazione con conteggi (`N voci su M esaminate`),
poi ogni voce con etichetta, nota, **titolo originale** (attributo `lang`), testata, data, lingua
dichiarata, la prova citata fra virgolette e il link. Massimo 3 voci, non più di 2 per tema. Il blocco
è **fuori dalla tendina di metodo**: è il caso in cui la card italiana è vuota. La riga unica della
card, quando esiste, dichiara anche le voci in lingua originale.

**Verifica.** Oracolo indipendente **[50]** in `scripts/verify_site.py`: rifà il lavoro dai Parquet e
da `config/leagues.yaml` e pretende che ogni voce resa esista in archivio **per quella squadra e in
quella lingua**, che l'etichetta appartenga al vocabolario, che la prova sia dentro il titolo e che i
conteggi dell'intestazione corrispondano alla lista.

## 4. Cosa NON facciamo (limiti dichiarati)

- **Nessuna traduzione** del titolo: resta in lingua originale, con `lang` e etichetta di lingua.
- **Nessuna riscrittura** né riassunto del testo di terzi: non scarichiamo l'articolo, non lo
  parafrasiamo.
- **Nessun sentiment**, nessuna valutazione: l'etichetta è un tema, non un giudizio.
- **Nessuna attribuzione sbagliata**: il titolo deve parlare della squadra, di un suo giocatore o del
  suo allenatore, altrimenti si conta come «fuori ambito» e non entra.
- Il blocco **non promette completezza**: dichiara quante voci sono state esaminate e quante escluse.

## 5. Misura prima/dopo (B.10)

| | prima | dopo |
|---|---|---|
| schede NED1/POR1 con voci | 0 su 10 | misura sul campione reale: **1–3 voci per club** |
| voci pubblicabili sui club del campione | 0 | **8** (27 titoli esaminati, 65 valutazioni club × titolo) |
| richieste per run | 132 | 168 (tetto 200) |
| righe di testo di terzi non in italiano | 0 | **titoli originali citati**, con lingua dichiarata |

La resa vera sulle schede pubblicate si vedrà al primo run dopo il merge: la raccolta delle edizioni
locali non è eseguibile dall'ambiente di sviluppo (rete bloccata), quindi la misura qui è **offline,
su feed reali letti a mano** e su un archivio che ancora non contiene le righe `nl`/`pt`.

## Prossimo passo

Dopo il merge: al primo run serale verificare (a) che l'archivio contenga righe con `language` `nl` e
`pt`, (b) che le schede NED1/POR1 mostrino il blocco, (c) il conteggio di richieste in
`stato.html` (atteso: +36). Se la resa reale è sotto 1 voce per scheda, il vocabolario va esteso — non
allargato il gate.
