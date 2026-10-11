# 82 — «Clima del club»: cosa dovrebbe contenere (studio e opzioni, 2026-10-11)

Richiesta dell'utente: «questa sezione dovrebbe darmi altri tipi di informazioni… fai una
ricerca profonda su cosa potrebbe invece darci il sito; possiamo usare anche altre fonti o
altri modi; dimmi cosa fare». Questo documento è lo studio: diagnosi misurata, inventario di
ciò che già raccogliamo e non pubblichiamo, candidati con numeri di copertura, tre opzioni e
una raccomandazione. **Non è ancora una modifica: la decisione è dell'utente** (le scelte
editoriali che toccano tutte le schede si prendono insieme, come per `docs/80` §2).

Misure fatte con `scripts/audit_clima_fonti.py` e con i Parquet del 2026-10-11 (77 schede
pre-partita, 154 celle-squadra, 132 squadre, 5.105 notizie raccolte fra il 27/09 e l'11/10).

---

## §1 — Diagnosi: la card di oggi è un **digest**, non un clima

Le 252 righe pubblicate oggi sono tutte derivate da dati che la stessa pagina già mostra
altrove:

| riga del clima | dove vive già nella stessa scheda |
|---|---|
| crisi / non vince / imbattuta / attacco a secco | riga «Forma» (hero + card squadra) |
| infermeria/assenze pesanti | «Analisi pre-partita» (indisponibili) e «Le due squadre» |
| riposo corto / congestione | «Le due squadre» (riposo con data e coppa) |
| scarto xPTS | «Le due squadre» (numeri) e analisi pre-partita (lettura) |
| panchina nuova | «Panchina e posta in gioco» (permanenza) |
| sconfitta pesante / espulsione | cronaca e forma (l'esito), mai l'**aggettivo di clima** |

Il contributo unico è il **tono** (bad/warn/good) e la **lettura**, non l'informazione: chi
legge non trova nulla che non sia già scritto due card più in basso. È esattamente il
«principio di utilità» della direttiva utente del 2026-09-15 (`docs/00` sez. F) applicato
male: una sezione che ripete non aiuta a decidere.

**Conclusione della diagnosi:** il nome promette il *clima del club* (intorno, pressione,
ambiente, società, tifosi), il contenuto consegna lo *stato della squadra* (forma,
disponibilità, calendario). Sono due cose diverse, e la prima oggi non esiste nel sito.

## §2 — Cosa vuol dire «clima del club» (definizione operativa)

Elementi che un lettore/una lettrice si aspetta sotto questa voce, e che sono verificabili:

1. **Pressione sull'allenatore** (esonero, panchina in bilico) — oggi non esiste: la card
   «Panchina» dà rendimento e permanenza, non la temperatura.
2. **Società e proprietà** (debiti, indagini, cessioni, contestazioni).
3. **Spogliatoio** (tensioni, litigi, chiarimenti).
4. **Tifoseria e stadio** (proteste, scioperi della tifo, riempimento, ambiente).
5. **Aspettative vs risorse** (rosa costosa che rende poco: è la definizione di pressione).
6. **Momento delle coppe** (settimana europea, turno in mezzo).
7. **Fuori dal campo** (iniziative, città, politica).

I punti 1-4 hanno come fonte la **stampa**; il 5-6 sono **nei nostri dati** già raccolti; il 7
è marginale (2 voci su 14 giorni in tutto l'archivio).

## §3 — Inventario: cosa raccogliamo e non pubblichiamo

| dato | dove è | copertura misurata | usato oggi? |
|---|---|---|---|
| Notizie con **12 categorie** già classificate (`TOPIC_RULES`: panchina, spogliatoio, società, tifo, stadio, fuori dal campo, squalifiche, infortuni, mercato…) | `news.parquet` | 5.105 voci · 132 squadre · 329 testate | solo come elenco («Vita del club»), mai come sintesi |
| **Spettatori** (`attendance`) | `match_info` | **387/495** gare, tutte con capienza | sì, ma solo a fine gara («spettatori 61.000») |
| **Valore dei titolari** (rosa) | `match_info` | 132/132 squadre | solo come «valore dei titolari» nella distinta |
| **Classifica** | `fotmob_standings` | 132 squadre | sì (posta in gioco, confronto di stagione) |
| Coppe (calendario) | `cup_fixtures` | 288 gare | sì (riposo/congestione) |
| `insights` FotMob | `insights.parquet` | 2.728 fatti | sì («Fatti rilevanti») |

**Fonti nuove ammesse ma non risolutive.** Il catalogo (`docs/02` §117) elenca
**Wikidata/Wikipedia** per stadio, capienza, città (SPARQL gratuito): sono fatti **statici**
(proprietà, fondazione, titoli), non clima; Transfermarkt diretto è bloccato da «verifica
umana» (`docs/02` §133); social e forum non sono ammessi (limiti, ToS, nessuna verifica
possibile). **La fonte del clima è già in casa: la stampa** — quello che manca è la sintesi.

## §4 — Candidati, con copertura misurata

**(a) La settimana del club dalla stampa.** Per ogni squadra, le voci degli ultimi 7 giorni
(in italiano, con i filtri già attivi) raggruppate per categoria, contate:
*Copertura*: **26 schede su 77** (41 celle su 154) hanno almeno una voce di clima; tema
dominante nella finestra: tifo 93, società 54, panchina 44, stadio 33, spogliatoio 20, fuori
dal campo 4. Con la soglia «≥3 voci di pressione in 7 giorni» (panchina/spogliatoio/società/
tifo) si accendono **22 celle su 154**.
*Parità — il punto debole, misurato*: le squadre con almeno una voce di clima in 14 giorni per
lega sono **ITA1 20/20**, ENG1 5/20, ESP1 5/20, FRA1 3/18, GER1 2/18, **NED1 0/18, POR1 0/18**
(la fonte è Google News edizione italiana). Una sintesi stampa **non è una scheda per tutte le
7 leghe**: dove non c'è, la card deve dirlo (la card notizie già lo fa con l'imbuto).

**(b) Pressione da aspettative (dai dati, parità piena).** Rango della rosa per **valore dei
titolari** contro la posizione in classifica: «rosa da 5ª per valore, in classifica 18ª».
*Copertura*: 132/132 squadre; scarto mediano |Δ| **3 posizioni**, con **56 celle su 154** (36%)
a |Δ| ≥ 5 — Atalanta 11ª con rosa 6ª, Bologna 19ª con rosa 10ª, Cagliari 4ª con rosa 15ª.
Dato **mai pubblicato** e sensato come «clima»: è la misura della distanza fra risorse e
risultato, cioè la pressione.

**(c) Ambiente (spettatori).** Riempimento misurato: mediana **0,91**, media 0,81; per lega
ENG1 0,99 · GER1 0,99 · NED1 0,95 · ITA1 0,87 · ESP1 0,86 · FRA1 0,82 · POR1 **0,44**.
*Ma la deviazione standard per squadra è 0,024*: il riempimento è un **tratto stabile**, non un
umore settimanale → utile come contesto una volta, non come segnale di clima (e per POR1 i
0,44 sono un dubbio di qualità del dato, non uno stadio vuoto: da verificare prima di
pubblicare qualunque numero).

**(d) Derby di città**: **0 su 77** oggi (le due squadre non condividono quasi mai la città
nelle gare in programma). Candidato parcheggiato, non cancellato.

**(e) Copertura della stampa per le coppe/derby**: non misurabile dal sandbox (richiederebbe
chiamate a Google News); se si vuole allargare, servono **query mirate** («esonero <squadra>»,
«tifosi <squadra>»), cioè +1-2 richieste per squadra su un budget oggi di 200/run con cache
12 h (`config/sources.yaml`; costi misurati in `docs/52`). Da verificare in CI, come sempre.

## §5 — Le opzioni

**A — Split onesto (raccomandata).** L'attuale card diventa «**Stato della squadra**» (è
quello che è: forma, disponibilità, riposo, pressione, toni) e nasce una card nuova «**Clima
del club**» con due blocchi:
 1. *La settimana del club* (stampa, 7 giorni): i temi dominanti con i conteggi e un giudizio
    «settimana calda / tranquilla» **solo** dove ci sono voci sufficienti; dove non ci sono,
    la riga dichiara il vuoto («la stampa italiana non ha pubblicato voci di clima su questa
    squadra negli ultimi 7 giorni»). Vietato ripetere i titoli (stanno in «Vita del club»):
    qui si pubblicano **conteggi e lettura**, con il rimando.
 2. *Pressione da aspettative* (dati nostri, tutte le leghe): rango per valore della rosa
    contro la classifica, col numero e la soglia dichiarata (|Δ| ≥ 5).
*Costo*: una sessione (funzione + template + oracolo indipendente [49] + test + docs);
struttura della scheda: 14 → 15 card, indice aggiornato; `parita_schede` resta verde.

**B — Una sola card, blocchi in più.** Si tiene il nome e si aggiungono i due blocchi in testa
alle righe attuali. Meno costo (mezza sessione), ma il nome continua a promettere clima e a
consegnare anche lo stato della squadra: la diagnosi del §1 resta, solo spostata in basso.

**C — Solo dati, nessuna stampa.** Clima = pressione da aspettative + coppe + ambiente, uguale
per tutte le 7 leghe, zero dipendenza dalla stampa. Parità perfetta, costo basso, ma **non è il
clima**: è contesto. Perderebbe i punti 1-4 del §2, cioè quello che l'utente sta chiedendo.

## §6 — Raccomandazione

**Opzione A.** Motivi misurati: (i) l'informazione nuova esiste già in casa — 12 categorie
classificate su 5.105 voci e il valore della rosa mai pubblicato — e copre **56 celle su 154**
(pressione: 25 «sotto le attese» e 31 «sopra», misurate sul build del giorno) più **21 lati**
con la settimana (7 «calde» e 14 «sotto pressione»); (ii) la parità è gestita dichiarando la
copertura invece di fingere che la stampa italiana copra Rotterdam come Roma (misurato: 0/18
in NED1); (iii) il nome torna a significare quello che dice, e la sezione «Stato della
squadra» resta utilissima senza dover difendere un nome che non le appartiene.

**Quello che NON farò** senza una decisione dell'utente: rinominare una card e aggiungerne una
nuova cambia l'indice, i test e tutte le 77 schede — è una scelta editoriale, non una
correzione. E resta valida la regola B.10: se l'opzione scelta peggiora un aspetto (es. una
card in più = più scroll), non si fa.

## §7 — Attuazione dell'opzione A (decisa dall'utente l'11/10/2026)

L'utente ha scelto **A** e ha chiesto di «fornire al sito tutti gli strumenti per farlo
funzionare in modo corretto». Attuato così, con le due sotto-domande risolte da un default
motivato (riapribili in ogni momento, sono scelte editoriali reversibili):

1. **La card-stampa pubblica conteggi e lettura, non titoli.** I titoli sono già nella card
   «Vita del club» due card più sotto: ripeterne uno qui violerebbe `docs/30` (un dato in un
   posto) proprio nella pagina in cui la regola è appena stata applicata (le strisce, `docs/81`
   §8). Se un titolo merita di stare in «Clima del club», il posto giusto è «Vita del club»,
   che ha la selezione e la deduplicazione collaudate. — *Scelta dichiarata reversibile e
   **superata la sera stessa**: su richiesta dell'utente («fornirmi queste voci con esattezza
   cosa dicono») i titoli ora sono nell'elenco della card, **marcati** quando «Vita del club»
   li racconta già. Attuazione e misure in §9.*
2. **Nessuna query nuova alla stampa, per ora.** La copertura è misurata e dichiarata (§4a):
   il perimetro della raccolta è la stampa in lingua italiana, e allargare le query di
   *collection* non cambierebbe il filtro di pubblicazione (una scheda in italiano pubblica
   solo testi italiani). Riaprire il tema significa decidere una politica linguistica nuova
   (`docs/24` dice «solo in italiano»), non aggiungere una query: resta in coda, con la misura
   già fatta.

**Cosa è stato costruito** (branch `arena/9912b625-football-deep-analyzer`):

| pezzo | dove | cosa fa |
|---|---|---|
| `club_week` | `src/fda/site/analysis.py` | conteggi per tema della stampa nella finestra `kickoff − 7 giorni`, filtro lingua e `classify_news` **gli stessi di «Vita del club»**; soglie: «settimana calda» da 3 voci di pressione (panchina/spogliatoio/società/tifoseria), «pressione in settimana» da 1, «settimana tranquilla» altrimenti; zero voci → `vuota=True` |
| `expectation_gap` | idem | rango della squadra per **mediana del valore dei titolari** sulle gare finite prima del fischio (minimo 3) contro la posizione in classifica dello snapshot raccolto; pubblica con \|Δ\| ≥ 5 e almeno 8 squadre nel rango di lega |
| `club_climate` | idem | unisce le due parti nell'ordine di lettura: settimana → aspettative |
| card «Clima del club» | `templates/match.html` | due colonne (casa/trasferta), righe col tono, frase fissa del **vuoto dichiarato**, nota con tutte le soglie e il perimetro della raccolta |
| card «Stato della squadra» | idem | l'ex «Clima del club» rinominata (id `stato-squadra`), nota che rimanda alla card nuova; indice aggiornato con le due voci |
| oracolo **[49]** | `scripts/verify_site.py` | su ogni scheda pre-partita ricalcola dai Parquet i conteggi della settimana (stessa classificazione della fonte) e il rango per valore **in modo indipendente**; verifica testo per testo e la frase del vuoto «se e solo se» zero voci; **dall'11/10/2026 sera (§9) verifica anche l'elenco: sommario, gruppi, item, link, marcatori, coda oltre il tetto**; registrato in `ORACOLI` come misto, col limite dichiarato |
| audit | `scripts/audit_clima.py` | misura le **due** card: la vecchia (ora «Stato della squadra») come prima, la nuova con conteggi per tipo, toni, lati con vuoto dichiarato e ogni dislivello pagina↔ricalcolo (`clima_dislivello`, `clima_nota_disallineata`, `clima_elenco_disallineato` per l'elenco) |
| test | `tests/test_panchina_notizie.py` | 5 test nuovi: conteggi per tema (4 voci di pressione → «settimana calda», infortuni e mercato **non** contati), tranquilla + vuoto dichiarato, aspettative sotto/sopra/soglia/minimo gare, **elenco con una voce per titolo e marcature di «Vita del club»**, **tetto di 24 col resto dichiarato**; `tests/test_site.py` verifica le due card e le due voci d'indice su una scheda vera |

**Efficacia dichiarata in pagina**: la copertura misurata è scritta nella nota (20/20 in
Serie A, 0/18 in Eredivisie): dove la stampa italiana non scrive, la card **dichiara il vuoto
di raccolta** e la pressione resta affidata ai dati nostrani, che valgono per tutte e 7 le
leghe. È il compromesso che tiene insieme onestà e parità (`docs/00` sez. F).

## §8 — Misure «dopo» e gate (build dell'11/10/2026)

**La card in pagina.** Su tutte le **77 schede pre-partita** la card «Clima del club» c'è,
con due colonne (casa/trasferta) e la nota con le soglie:

- settimana: **21 lati** con una riga — 7 «settimana calda» (es. Juventus, 14 voci di
  pressione: tifoseria 9 · società 4 · panchina 1 — numeri **rigenerati dopo la deduplica di
  §9**, prima erano 15), 14 «pressione in settimana», 0
  «tranquilla» (oggi ogni lato con voci ha almeno una voce di pressione); **133 lati** con il
  **vuoto dichiarato** («nessuna voce di clima raccolta…» — la parola è «raccolta», non
  «pubblicata»: per le partite ancora lontane la settimana è incompleta, e la card lo dice);
- aspettative: **56 lati** pubblicano (25 «sotto le attese», 31 «sopra le attese»), con
  almeno 3 gare misurate e almeno 8 squadre nel rango di lega; 98 lati in linea con le attese
  non stampano nulla (il silenzio non è un verdetto).

**Una correzione prima di chiudere.** La stima preliminare della pressione (60 celle) e la
prima misura con lo script di sondaggio (58) usavano un perimetro di gare diverse
(`match_info.status`); la definizione della scheda è **le gare finite dal calendario prima del
fischio** (`_gare_finite`, la stessa di forma, xG e strisce) e con quella le celle sono **56**:
la differenza è di due celle Liverpool, dove il rango cambia di una posizione. Nel dubbio ha
vinto la definizione usata da tutta la pagina — e l'oracolo [49] ricalcola proprio quella.

**Gate** (build 2026-10-11, `arena/9912b625`):

| gate | esito |
|---|---|
| `pytest -q` | **627 passed** (+3 test nuovi: settimana, tranquilla/vuoto, aspettative) |
| `ruff` | pulito su `analysis.py`, `match.html` (Jinja), `verify_site.py`, i due audit, i test |
| `fda build` | **493 partite · 2.364 gare · 7.578 giocatori** (exit 0) |
| `verify_site` | **0 problemi · 236.749 controlli**; [21] rinominata (77 pagine), **[49] nuova** (77 pagine); registro **53 controlli: 30 I · 19 M · 4 S** |
| `parita_schede` | **nessuna differenza**: stesse sezioni, stesso indice, stessa quantità di testo (minimo 90% della mediana, 27.411 su 30.352) |
| `resa_375` | **28.466 misure · 0 problemi** a 375 px |
| `audit_clima` | difetti nuovi **0** (`clima_dislivello` 0, `clima_nota_disallineata` 0); i difetti noti restano quelli dichiarati (perimetro coppe 30, infermeria 3) |
| `audit_clima_candidati` | invariato (sonda dei candidati scartati) |

**Nessuna richiesta alle fonti esterne** in nessun passaggio; nessun file di dati toccato.

## §9 — Le voci contate, in chiaro (richiesta dell'utente, 11/10/2026 sera)

Richiesta: «rendi in grado il sito di fornirmi queste voci con esattezza cosa dicono». Prima di
questa sera la card pubblicava **solo i conteggi**: un «15 voci di pressione» che non si può
aprire non è verificabile dal lettore, e il numero non si può ricondurre a ciò che dice. Attuato:

- **Elenco per lato**, in una tendina chiusa per default (non occupa il primo schermo):
  raggruppato per tema, ogni voce con **titolo, testata, data e link**; il sommario dichiara
  quante voci sono elencate — «Le X più recenti di Y contate» quando il tetto taglia — e quante
  sono già raccontate in «Vita del club».
- **Una voce per titolo** (`news_title_key`: la stessa chiave di normalizzazione del dedup di
  `team_news`, un'unica definizione in `analysis.py`): la misura ha trovato **11 righe doppie**
  (97 righe → 86 voci) che gonfiavano i conteggi pubblicati su 5 lati — Lazio 19→14, Torino
  19→17, Juventus 16→15, Milan 6→4, Venezia 3→2. Vale contare due volte lo stesso titolo ripreso
  da due testate: era il caso.
- **Tetto 24 voci per lato** (`CLIMA_VOCI_MAX`), dichiarato in nota; oltre il tetto il resto è
  dichiarato col numero («E altre N della settimana, non elencate»). Nel sito di oggi il massimo
  per lato è **17**: la guardia non taglia nulla, serve per quando la raccolta crescerà.
- **Marcatura, non esclusione** (supera la scelta di §7.1): le voci che «Vita del club» racconta
  sulla stessa pagina escono marcate «anche in «Vita del club»» — qui si contano, lì si
  raccontano (`docs/30` resta salvo: l'elenco è la prova del numero, non un secondo racconto).
- **Citazioni verbatim**: i titoli di stampa sono esclusi dai controlli anti-falso con la classe
  `a.voce` nel parser di `verify_site` (misurato: «TORNELLI APERTI DALLE 18.15» su 5749709 faceva
  fallire il gate dei decimali col punto). Sommario, etichette dei gruppi, testata, data e
  marcatore restano testo nostro e restano controllati.

**Misure** (build 2026-10-11 sera, dopo la deduplica): **86 voci elencate**, **25 marcate**
«anche in «Vita del club»», massimo **17** per lato; righe pubblicate invariate (77 in tutto:
7 «settimana calda» · 14 «pressione in settimana» · 56 aspettative; 133 lati col vuoto
dichiarato).

**Gate**: `pytest` **629** (+2 test), `ruff` pulito, `fda build` **493/2.364/7.578**,
`verify_site` **0 problemi · 237.513 controlli** ([49] estesa: l'elenco deve corrispondere ai
conteggi voce per voce, sommario, gruppi, item, link, marcatori e coda), `parita_schede`
**nessuna differenza**, `resa_375` **28.487 · 0**, `audit_clima` **0 difetti**
(`clima_elenco_disallineato` 0). Nessuna richiesta alle fonti esterne.
