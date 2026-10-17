# Pagine squadra, contatore giocatori e Accuratezza a linguette — 2026-10-17

Intervento richiesto dopo l'audit [`docs/112`](112_revisione_totale_2026-10-16.md): il sito
raccontava bene le **partite** e i **giocatori**, ma non aveva un indirizzo a cui seguire una
**squadra**. Chi voleva la classifica, la rosa, gli indisponibili e le prossime gare di Genoa
doveva aprire cinque pagine diverse e ricomporre i numeri a mente. Questo documento misura
cosa è stato costruito, con quali dati, con quali controlli e cosa resta aperto.

Tre interventi separati, come concordato:

1. **contatore dei giocatori** corretto (`7.602` → `3.801`);
2. **132 pagine squadra** + indice (`squadre/`), collegate da schede gara, schede giocatore,
   menu e sitemap;
3. **Accuratezza a linguette**: laboratorio raggiungibile dalla barra di sezione, card
   «Stabilità dei mercati nel tempo» con i dati di `mercati_monitor`, link nel footer.

Nessuna fonte nuova, nessuna richiesta HTTP aggiuntiva: tutto nasce dai Parquet già raccolti.

---

## 1. Contatore dei giocatori: perché stampava il doppio

`SiteBuilder.build_players` sommava due cose diverse nello stesso numero:

- `n += len(rows) + len(bench)` per ogni lega (le righe dei tabelloni: 3.801 giocatori
  pubblicati, contati una volta per il titolare e una per la panchina);
- `n += 1` per ogni scheda generata (altre 3.801 unità).

Il risultato, `7.602`, finiva in `/tmp` della build e da lì in cinque documenti. La cartella
`site/giocatori/` conteneva però **3.809 file**: 3.801 schede, 7 tabelloni di lega e l'indice —
esattamente i numeri che il contatore avrebbe dovuto dire.

**Correzione misurata (17/10/2026).**

| Voce | Prima | Dopo |
|---|---|---|
| File in `site/giocatori/` | 3.809 | 3.809 |
| Schede giocatore | 3.801 | 3.801 |
| Numero stampato dal build | 7.602 | **3.801** |

Il contatore ora conta solo le schede; tabelloni e indice non entrano. Il test
`tests/test_team_pages.py::test_contatore_giocatori_conta_le_schede_non_le_righe` fissa la
regola su un caso di due giocatori: due schede, non quattro. Le occorrenze storiche di
«7.602» nei documenti datati restano come sono: erano il numero che il build stampava, non
un errore di trascrizione. `docs/STATO.md` e il briefing di sessione sono aggiornati.

---

## 2. Pagine squadra (`squadre/<team_id>.html`)

### 2.1 Cosa c'è in pagina

Una scheda per ciascuna delle **132 squadre** delle 7 leghe, più l'indice `squadre/index.html`
diviso per campionato (posizione, squadra, gare, punti). Ogni scheda contiene, nell'ordine:

1. **testata**: nome, lega, posizione, punti, punti a gara e proiezione di fine stagione;
2. **prossima partita**: data e ora italiane, casa/trasferta, barra 1X2 con il favorito in
   grassetto, gol attesi e Over 2,5; link alla scheda gara solo se quella pagina esiste;
3. **ultime gare**: serie V/N/P in pallini e tabella delle ultime cinque gare finite;
4. **classifica e rendimento per sede**: la riga FotMob (riserva ESPN) e gli split casa/trasferta
   calcolati dalle gare finite in archivio, con la proiezione di stagione (posizione media,
   punti attesi, titolo, UCL, retrocessione);
5. **indisponibili**: l'ultima distinta pubblicata dalla fonte, con tipo e rientro dichiarati;
6. **formazione probabile/ufficiale**: modulo, avversario, undici con numero, ruolo e voto medio;
7. **rosa**: giocatori con presenze, minuti, voto, gol, xG, assist e xA; panchina separata;
8. **mercato**: arrivi e partenze deduplicati, con importi leggibili (`fee_it`);
9. **notizie**: fino a tre titoli italiani, con testata, data, link e collegamento ai dati;
10. **prossime partite**: le successive con 1X2, gol attesi e Over 2,5, link solo se la scheda esiste;
11. **stagioni precedenti**: ultime quattro stagioni di storico, posizione e punti;
12. **fonti**: nota che rimanda a `info.html` e allo stato delle fonti.

### 2.2 Da dove vengono i numeri (nessun calcolo parallelo)

Il principio di `docs/00` §F è che la stessa cifra non può vivere in due posti con due valori.
Per questo `TeamCatalog` **non ricalcola** nulla che esista già:

| Blocco | Funzione riusata | Fonte |
|---|---|---|
| classifica | `fotmob_standings` → riserva `espn_standings` per nome canonico | FotMob / ESPN |
| forma | `MatchAnalysis.form` + `form_summary` | `fixtures` |
| 1X2 e gol attesi | `latest_per_match` + gli stessi campi della scheda gara | `predictions` |
| indisponibili e distinta | `MatchAnalysis` (snapshot della distinta) | `lineup` |
| rosa e tabellone | `PlayerCatalog.league_rows` / `team_rows` | `lineup` + `player_stats` |
| mercato | `transfers` + `fee_it` | `transfers` |
| proiezione | `mc_percent_str` (la formattazione di `stagione.html`) | `season_sim` |
| storico | `history` + classifica ricostruita per stagione | `history` |
| notizie | `MatchAnalysis.team_news` (primo livello) | `news` |

Il catalogo giocatori viene costruito **una volta per build** e passato a `build_teams`:
`build_players` lo salva in `self.player_catalog`, `TeamCatalog` lo riusa. Il costo misurato
è 15,1 s per il caricamento unico e 12,3 s per le 132 pagine; senza riuso si sarebbero
ricaricati lineup e statistiche una seconda volta.

### 2.3 Notizie: due livelli dichiarati, nessun titolo inglese

La prima versione filtrava da sola il campo `language`, che per molti articoli è **vuoto**:
due titoli ESPN in inglese («January», «10.10.2026») sono arrivati fino al verificatore, che
li ha fermati come `inglese` e `decimale col punto`. La selezione ora usa la stessa funzione
del bollettino pre-partita (`MatchAnalysis.team_news`), con finestra di 30 giorni e senza le
categorie che hanno già una card in pagina (infortuni, squalifiche, mercato).

Il gate del «segnale di club» però è pensato per la vigilia: su **90 squadre su 132** non
produce nulla (la stampa italiana delle leghe straniere è quasi sempre un servizio, non un
fatto). Per non lasciare la card vuota e per non abbassare la soglia in silenzio esiste un
secondo livello, dichiarato in pagina:

- **bollettino** (42 squadre): stessi criteri della scheda gara;
- **rassegna** (21 squadre): ultime voci italiane con i filtri di base — lingua verificata sul
  titolo, categoria, valore editoriale, soggetto, niente Primavera/femminile — e la data
  accanto al titolo dice quanto sono vecchie;
- **nessuna voce** (69 squadre): la card dice che la copertura non c'è, invece di riempirsi
  con titoli che parlano d'altro. Misurato il 17/10/2026 sul parquet `news` (4.986 voci `it`,
  823 `nl`, 744 `pt`).

La distribuzione finale è `{3: 13, 2: 8, 1: 42, 0: 69}`. È un limite di copertura, non del
codice: le fonti italiane seguono poco Eredivisie e Liga Portugal.

### 2.4 Link solo dove la pagina esiste

Le schede partita vengono generate per un sottoinsieme di gare (finestra di 7 giorni +
archivio). La scheda squadra conosce `built` — l'insieme dei `match_id` realmente scritti — e
mette il link solo a quelli. Senza questo controllo, una gara a 10 giorni lascerebbe un 404 e
il gate dei collegamenti interni ([27]) lo fermerebbe. Se la scheda non c'è, la riga resta
testo e la card dice «la scheda completa arriva nella finestra dei 7 giorni».

### 2.5 Scopribilità

- **menu principale**: voce «Squadre» fra «Giocatori» e «Stato fonti»;
- **footer**: «Squadre» e «Laboratorio dei modelli»;
- **schede gara**: i nomi delle due squadre nell'hero sono link alla scheda (il badge della
  forma resta attaccato al nome, dentro o fuori dall'ancora);
- **schede giocatore**: il nome della squadra porta alla scheda;
- **sitemap**: `squadre/index.html` + 132 URL, `lastmod` = data di build (la scheda cambia a
  ogni raccolta, come le liste).

---

## 3. Accuratezza a linguette

Prima di questo intervento il laboratorio era raggiungibile **solo** dal testo in cima ad
Accuratezza, e i mercati del monitor non erano pubblicati da nessuna parte: `mercati_monitor`
veniva prodotto dal daily ma non letto dal sito.

- barra `.cal-nav` identica su `accuratezza.html` e `laboratorio.html`, con `aria-current`;
- card **«Stabilità dei mercati nel tempo»** subito dopo la tabella dei mercati live: nove
  mercati su **5.960 gare** fuori campione, scarto osservato−previsto, due metà cronologiche,
  leghe in accordo e verdetto;
- i valori sono quelli di `models/backtest.market_monitor`: 9 mercati, **2 fuori intervallo**
  (porta inviolata in casa e Over 2,5), **0 «strutturali»** al 17/10/2026. Il verdetto
  «monitora» è una nota di controllo, non un permesso a cambiare il modello: la regola resta
  quella del laboratorio (nessuna promozione senza test prospettico);
- la card sparisce se il Parquet non c'è (nessun numero inventato); quando una metà è
  «compatibile» (la previsione cade dentro il suo intervallo di Wilson) la cella lo dice,
  senza colorare di rosso un'assenza di segnale.

---

## 4. Gate e misure

### 4.1 Gate nuovi in `scripts/verify_site.py`

| Gate | Cosa controlla | Misura 17/10/2026 |
|---|---|---|
| `[52]` | ogni riga di `fotmob_standings` ha una scheda; nome, lega, posizione, punti e gare coincidono con la tabella | **660 cifre · 132 squadre · 0 problemi** |
| `[53]` | l'1X2 della prossima gara è identico alla barra della scheda partita collegata e somma 100 | **120 gare confrontate** |
| `[54]` | posizione media e punti attesi sono quelli di `season_sim`, formattati in modo indipendente | **264 stringhe ricalcolate** |

I tre gate sono registrati in `ORACOLI` come **indipendenti** (`I`): il valore atteso viene
ricalcolato dai Parquet, non dal codice che ha prodotto la pagina. `[52]` ha già trovato un
difetto reale durante lo sviluppo: `html.unescape` mancava sul nome nell'`h1`, e
«M&#39;gladbach» non coincideva con «Borussia Mönchengladbach».

### 4.2 Misure della build

| Voce | Prima (17/10, dati di `main`) | Dopo |
|---|---|---|
| pagine analizzate | 4.350 | **4.483** (+133) |
| file in `site/` | 4.350 HTML / 161 MB | **4.483 HTML / 167 MB** |
| schede partita / fixture / schede giocatore | 532 / 2.364 / 7.602 | **532 / 2.364 / 3.801** |
| durata build | 8m08 | **8m16** |
| `verify_site` | 264.436 controlli / 0 problemi | **269.056 / 0** |
| test | 1.054 (misurati in sessione; 1.052 in `docs/112`) | **1.059** (+5 di pagina squadra) |
| `parita_schede` | nessuna differenza | nessuna differenza |
| `resa_375` | 29.965 misure / 0 | **31.288 misure / 0** |

I tempi sono quelli della macchina locale; il build in CI è più lento e resta sotto i limiti
del workflow.

---

## 5. Limiti dichiarati

1. **Notizie**: 69 squadre su 132 non hanno una voce italiana che parli della prima squadra
   con i criteri dichiarati. Non è una quiete dimostrata, è copertura delle fonti.
2. **Storico**: la tabella «Stagioni precedenti» copre al massimo quattro stagioni e la
   posizione si ricostruisce solo se lo storico contiene quella lega.
3. **Proiezione**: le cifre sono quelle di `season_sim` (10.000 stagioni per lega); non sono
   una previsione puntuale e non incorporano il mercato.
4. **Mercato**: `transfers` copre i movimenti raccolti dalla fonte, non l'intero mercato.
5. **Nessuna fonte nuova**: per riempire le lacune di notizie servirebbe un'edizione locale
   per ENG1/ESP1/GER1/FRA1, che oggi non è dichiarata e non è stata aggiunta.
6. **Diritti**: restano valide le cautele di `docs/111` e `docs/112`; questo intervento non
   amplia i fetch né riusa dati grezzi di terzi.

---

## 6. File toccati

- `src/fda/site/team_pages.py` (nuovo): `TeamCatalog`, `league_blocks`, `page`;
- `src/fda/site/templates/squadra.html`, `squadre.html` (nuovi);
- `src/fda/site/templates/base.html`: voce di menu e footer;
- `src/fda/site/templates/match.html`, `giocatore.html`: link alla scheda squadra;
- `src/fda/site/templates/accuracy.html`, `laboratorio.html`: linguette e card del monitor;
- `src/fda/site/build.py`: `build_teams`, sitemap, contatore, card monitor;
- `src/fda/site/players.py`: `team_rows` sopra `_rows` condiviso;
- `scripts/verify_site.py`: gate `[52]`–`[54]`, `[34]` aggiornato all'hero con link;
- `scripts/browser_smoke.mjs`: indice squadre + una scheda per lega;
- `tests/test_team_pages.py` (nuovo): cinque test;
- `docs/114` (questo file), `docs/STATO.md`.

---

## Prossimo passo

Rifare la build completa e i gate su `main` aggiornato (i Parquet cambiano a ogni daily),
poi aprire la PR unica di sessione. Il merge resta al committente. Se si vorrà chiudere il
buco delle notizie per le leghe senza stampa italiana, la strada è dichiarare un'edizione
locale per una lega alla volta — con lingua, traduzione e diritti espliciti — non allargare
i filtri della pagina squadra.
