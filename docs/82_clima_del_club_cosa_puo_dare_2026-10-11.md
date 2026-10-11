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
*Copertura*: 132/132 squadre; scarto mediano |Δ| **3 posizioni**, con **60 celle su 154** (39%)
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
classificate su 5.105 voci e il valore della rosa mai pubblicato — e copre **60 celle su 154**
(pressione) più **22 celle** (settimana calda); (ii) la parità è gestita dichiarando la
copertura invece di fingere che la stampa italiana copra Rotterdam come Roma (misurato: 0/18
in NED1); (iii) il nome torna a significare quello che dice, e la sezione «Stato della
squadra» resta utilissima senza dover difendere un nome che non le appartiene.

**Quello che NON farò** senza una decisione dell'utente: rinominare una card e aggiungerne una
nuova cambia l'indice, i test e tutte le 77 schede — è una scelta editoriale, non una
correzione. E resta valida la regola B.10: se l'opzione scelta peggiora un aspetto (es. una
card in più = più scroll), non si fa.

## §7 — Prossimo passo

L'utente sceglie l'opzione (A / B / C) e, se A, risponde a due sotto-domande: (1) la card-
stampa pubblica solo conteggi e lettura, o anche **il titolo più significativo** (con link,
come fa «Vita del club»)? (2) si allargano le **query della stampa** (esonero/tifosi per
squadra) con il budget conseguente, o si aspetta di vedere l'effetto sulle voci già raccolte?
