# 83 — «Clima del club»: dove il sito prende le voci, e quali voci (raccolta e pertinenza)

Richiesta dell'utente (2026-10-11, sera): «puoi verificare e revisionare che il sito sappia dove
andare a prendere tutto? vorrei cose più precise, più importanti o particolari». Due criteri,
due lavori distinti in questo documento:

1. **la raccolta** — il sito deve cercare ogni squadra col nome con cui la stampa italiana la
   scrive, e gli strumenti devono **dirlo** quando la copertura è bassa (§1);
2. **la pertinenza** — le voci contate nel clima devono essere di *quella* squadra (§3) e il
   «fatto della settimana» deve essere un fatto vero della sua settimana (§4).

Misure fatte con i Parquet dell'11/10/2026 (77 schede pre-partita, 154 lati-squadra, 132
squadre, 5.105 notizie dal 27/09 all'11/10) e con lo script nuovo `scripts/audit_fonti.py`.

---

## §1 — La raccolta: la mappa delle ricerche aveva 15 buchi e 23 chiavi morte

**Cosa è stato verificato.** `scripts/audit_fonti.py` (nuovo, diagnostico: **nessuna rete,
nessuna scrittura**, ~20 s, non in CI) risponde alla domanda «il sito sa dove andare a
prendere?» con i dati che ha già: tabelle presenti in `data/processed`, fixtures, **copertura
della stampa per lega a 14 giorni**, squadre sotto la mediana, e l'elenco delle query per
squadra. Esito della prima esecuzione:

- **17/17 tabelle** presenti; fixtures **411 gare** (130 finite · 281 da giocare · leghe 1-7);
- copertura mediana a 14 giorni per lega: **ITA1 152,5 · ESP1 22 · ENG1 16 · GER1 14,5 ·
  POR1 12 · NED1 11 · FRA1 7,5**; voci di clima contate: ITA1 181 · ESP1 23 · ENG1 15 ·
  FRA1 5 · GER1 3 · **NED1 0 · POR1 0**;
- 8 squadre sotto la mediana di 3: **Nottm Forest 2 · M'gladbach 2** · Monaco 3 · Cambuur 3 ·
  Rennes 4 · Estrela da Amadora 4 · Newcastle 4 · FC Groningen 5;
- **0 difetti bloccanti, 4 avvisi, exit 0**. Un «difetto bloccante» è solo **zero notizie in
  14 giorni**: le 91 squadre senza query italiana mappata non sono un difetto (i nomi italiani
  ed europei sono già scritti come li scrive la stampa: «Arsenal», «Benfica», «Atalanta»), e le
  23 chiavi «morte» della mappa non sono un difetto (alias di altre stagioni o nomi abbreviati
  dei dati). Il difetto si dichiara con la misura, non con l'intuizione.

**Cosa è stato corretto.**

1. **La mappa `ITALIAN_SEARCH_NAMES`: 49 → 64 chiavi.** Aggiunte le 15 denominazioni che i
   dati scrivono **abbreviati o accentati** e che la stampa italiana scrive per esteso: Nottm
   Forest → «Nottingham Forest» · M'gladbach → «Gladbach»/«Borussia Monchengladbach» · Köln →
   «Colonia»/«FC Koln» · Augsburg → «Augusta» · Frankfurt → «Eintracht Francoforte» · Freiburg →
   «Friburgo» · Leverkusen · Dortmund → «BVB» · Union Berlin → «Union Berlino» · Mainz →
   «Magonza» · Man City · Man United · PSG · Vitória de Guimarães → «Vitoria SC» · Nacional →
   «Nacional Madeira» (da solo «Nacional» pescherebbe mezzo vocabolario). Effetto misurato della
   lacuna: **Nottm Forest 2 notizie e M'gladbach 2 in 14 giorni** contro mediane di 16 e 14,5
   nella loro lega (`docs/83` §1 di `news.py`).
2. **Confronto normalizzato dei nomi.** La mappa si interrogava con un confronto **esatto**:
   «Köln» nei dati e «Köln» nella mappa sono la stessa cosa, ma «Atlético Madrid» e «Atletico
   Madrid» no — e le chiavi accentate risultavano **morte** (nessuna squadra le incontrava, 23
   in tutto). Ora `_norm_nome` (minuscole, senza accenti, senza punteggiatura) e
   `italian_search_name()` sono l'unico punto che decide la query di una squadra.
3. **Gli alias dei feed diretti.** `collect.py` leggeva la stessa mappa con il match esatto:
   una chiave accentata o abbreviata valeva **zero alias** sui feed diretti (Tuttosport, ANSA…).
   Ora legge `italian_search_name`, come la ricerca per squadra.

**Dichiarato, perché conta.** Questi fix cambiano le **prossime** raccolte (`fda daily`):
l'archivio di oggi resta quello raccolto, con le sue medie. La prova che il fix funziona si
avrà la prossima volta che `audit_fonti.py` gira: Nottm Forest e M'gladbach devono uscire
dall'elenco delle squadre sotto la mediana.

## §2 — Le collisioni delle parole chiave (regex senza confini di parola)

Nel classificare i titoli, alcune regole erano scritte come **sottostringhe**: pescavano dentro
altre parole. Misurato l'11/10/2026:

| regola | parola vera pescata per sbaglio | titolo che entrava per errore |
|---|---|---|
| `lite` | «Élite» | «Youth League Élite: …» |
| `fischi` | «fischierà» | «…fischierà l'arbitro X» |
| `rifa` | «rifatto» | «stadio rifatto» |
| `futuro de` | «Futuro del…» | «Il Futuro del club» |
| `berlusconi` (nome proprio) | «Milan di Berlusconi» | opinioni e memoria storica fra i segnali di spogliatoio |

Correzioni: `\b…\b` (confini di parola) per `lite`, `rifa`, `futuro de`; per `fischi` le forme
esplicite `\bfischi\b|\bfischiato\b|\bfischia(?:no)?\b`; rimossi i **nomi propri** dalle regole
(un nome proprio non è un tema: è un argomento). Test:
`test_classifica_niente_collisioni_di_sottostringa`.

**Perché in questo documento**: nel clima una collisione non è una questione di stile. Una
regola larga **inventa una voce di tifoseria** e, con i pesi del §4, può spostare il fatto
della settimana.

## §3 — I tre gate di pertinenza: la fonte, il tema e il club

Una voce conta per il clima di una squadra solo se supera **tre** controlli, tutti e tre
dichiarati nella nota della card. L'imbuto misurato sull'archivio (154 lati-squadra, finestra
di 7 giorni prima del fischio, una voce per titolo):

| gate | voci | cadute |
|---|---|---|
| solo lingua italiana | 1.612 | — |
| + fonte non a bassa reputazione | 1.315 | 297 |
| + **tema nel titolo** | 58 | 1.257 |
| + **club nel titolo** | **44** | 14 |

Il terzo gate (`docs/83` §3) è nuovo di questa sessione: era il buco rimasto. Le 14 cadute,
una per una:

- **11 senza il nome del club nel titolo**: «Latina, Pino D'Apuzzo diventa il nuovo presidente»
  e «Stadio Bartolani, rinviato il ricorso presentato dal Latina Calcio» per la **Lazio**;
  «Possibilità al Cesena per Mencucci» per il Lecce; «Rolando Bianchi sarà il nuovo allenatore
  del Villa Valle» e «Incontro per i media con il tecnico Abate» per il Torino; «Graduation
  day, in 6mila per la festa dei laureati allo stadio Friuli» e «Nota ufficiale: Idrissa Gueye»
  per l'Udinese; «Commissariamento FIGC…» per il Venezia; «INTERVISTA | Il Direttore Sportivo
  Accardi con *Tuttosport*» per il Cagliari; «Il nuovo stadio avanza. Contatti con Uva e Abodi»
  e «È la notte di Riccardo Calafiori» per il Bologna;
- **3 col club come oggetto della notizia di un altro**: «Real Madrid, alta tensione a pochi
  giorni dalla Roma» (per il Roma), «Juventus, la protesta della curva Sud: “Contro la Lazio
  resteremo fuori”» e «Juve, duro comunicato della Curva Sud: “Contro la Lazio resteremo
  fuori”» (per la Lazio: sono la settimana della Juventus, e si contano lì).

**Come è fatto il gate.**

- `soggetto_tokens(nome)` (`news.py`) raccoglie le parole con cui un titolo può **nominare**
  quella squadra, da tre sorgenti già nel file: il nome nei dati, i **nomi italiani fra
  virgolette** della mappa delle ricerche («Colonia», «Gladbach», «Stoccarda», «Marsiglia»…) e
  `SOPRANNOMI` per i club che la mappa non copre — **Juve**, **Toro**, **Internazionale**,
  **Barcellona**/**Barça**, **Siviglia**, **Atleti**. Parole **intere** di almeno 3 lettere,
  senza sigle societarie (`FC`, `AC`, `SC`, `Rb`…): senza i confini di parola «Toro» pescherebbe
  «tornerà» e «Juve» «juventino».
- `club_nel_titolo(titolo, tokens)` aggiunge la **guardia sull'oggetto**: se l'unica occorrenza
  del nome è preceduta da una preposizione che rende il club l'oggetto della notizia di
  qualcun altro (`contro`, `dalla`, `dal`, `dai`, `dalle`, `verso`, `vs`, con l'articolo che
  segue: «contro **la** Lazio»), la voce non conta. La famiglia è **corta di proposito**: «di»,
  «del», «al», «con», «per» compaiono nell'archivio **843 volte** davanti a un nome di club e
  quasi sempre il club è il soggetto («Statistiche **di** Arouca», «l'addio **al** City»),
  quindi non entrano nella guardia.
- **L'alternativa scartata, con la misura**: far contare anche una voce in cui compare
  **l'avversario** invece del club. Misurata sull'archivio: **0 voci in più** — nessuna voce
  della settimana arrivava solo dall'avversario. Regola più stretta e più semplice, e niente
  effetto.

**Limiti dichiarati del gate.**

- Guarda **il titolo**, non il brano: è il titolo che la card pubblica, ed è l'unico testo su
  cui chi legge può controllare il conteggio. Costo accettato e misurato: cade «Il nuovo stadio
  avanza. Contatti con Uva e Abodi» (notizia del Bologna che il Bologna non lo nomina).
- Resta dentro una voce come «Eleonora Goldoni della Lazio fermata dai tifosi della Roma»: la
  notizia è **dei tifosi della Lazio**, quindi è tifoseria di quella settimana — la guardia non
  distingue «i tifosi della Lazio» da «la Lazio».
- `SOPRANNOMI` copre 6 club: quando una voce **vera** cade per un nome che non conosciamo, il
  contatore `fuori_soggetto` la fa trovare e si aggiunge il nome (metodo, non intuito).

**Esito sulla build**: le voci elencate passano da 86 (build #3, senza gate di soggetto) a
**44**, i lati con il vuoto dichiarato da 133 a **138**, le marcatrici «anche in «Vita del
club»» da 25 a **13** (l'elenco contiene solo voci pertinenti, quindi anche le voci già
raccontate sopra diminuiscono). Il conteggio resta la prova di sé stesso: ogni voce è apribile
con titolo, testata, data e link.

## §4 — Il fatto della settimana: cosa è un fatto

Il «fatto della settimana» è la voce che pesa di più fra quelle contate. Il peso è quello
dichiarato dei temi (5 panchina/spogliatoio/società · 4 fuori dal campo · 3 tifoseria/stadio)
più **3** (era 2) se il titolo dice un fatto grave; a parità vince la più recente. Tre
correzioni, tutte da una misura:

1. **Bonus +2 → +3.** Con +2 lo sciopero della curva della Juventus (tifoseria 3+2=5) pareggiava
   con una voce di società qualunque (5) e il fatto lo decideva l'**ora** della pubblicazione.
   Con +3 il fatto grave vince: **6 > 5** (Juventus: la Curva Sud che diserta Juve-Lazio, non
   un comunicato societario).
2. **Il fatto esce solo se pesa almeno 4** (`CLIMA_FATTO_MIN`): cioè fuori dal campo, panchina,
   spogliatoio, società — o qualunque tema con un fatto grave. Tifoseria o stadio **da soli**
   non bastano. Misura: gli 8 lati che pubblicavano un fatto di peso 3 pubblicavano una
   petizione dei tifosi per il ritiro di una maglia, «Votato dai tifosi: le 10 migliori vittorie
   del Liverpool», «polemiche dei tifosi sui social» per una regia televisiva, «Nuovo stadio del
   Bologna in Fiera, Lepore: “Non sarà come Fico”», «Cruciani: “Monza poco seguito”. Juric
   risponde». **Nessuno** di quei lati aveva un fatto più pesante da mettere al posto loro: la
   riga esce quando c'è qualcosa, altrimenti tace (17 lati → 9 → **8**).
3. **Un fatto grave detto in proprio.** Le **citazioni fra virgolette** non contano: fra
   virgolette c'è la frase di qualcun altro. Misura: 1 voce su 58, ed era il fatto della
   Juventus — «Gasperini, la risposta sulla Juve: “…Esonero Inter? Ho vacillato”», la domanda di
   un giornalista a un altro club. E **«plusvalenz» è uscita** dalla lista dei fatti gravi: è il
   tema delle colonne di fantacalcio («Statistiche Fantacampionato, Juventus: le tre plusvalenze
   maggiori dopo la 5ª giornata»), non un fatto — e uno scandalo di plusvalenze resta coperto da
   «inchiesta», «indagine», «procura». Una sola copia della lista vive ora in
   `news.py` (`fatto_grave`), usata da `analysis.py` e dai due oracoli.

**Esito sulla build: 8 fatti pubblicati**, tutti fatti della settimana di quella squadra.

| squadra | tema | fatto della settimana |
|---|---|---|
| Juventus | tifoseria | «Juve-Lazio senza Curva Sud: gli ultras disertano lo Stadium dopo i provvedimenti per il derby» |
| Torino | tifoseria | «Scontri durante Torino-Juventus: emessi 22 Daspo per gli ultras» |
| Lazio | società | «Lazio, l'analisi dei conti del club: debiti record e i ricavi sono fermi» |
| Man City | società | «City, che retroscena: no a maxi-multa con cui evitare la retrocessione» |
| Milan | stadio | «San Siro, il Tar boccia i ricorsi contro la vendita a Inter e Milan» |
| Cagliari | società | «Cagliari \| Pavoletti e Zanda, ammessi al corso da direttore sportivo» |
| PSG | tifoseria | «La curva del Psg si svuota durante la partita: colpa di uno striscione» |
| Atlético Madrid | società | «Gilgeous-Alexander diventa azionista dell'Atlético Madrid» |

Dove non esce: 8 lati hanno voci ma nessun fatto abbastanza pesante (prima ne avevano uno
debole), e **138 lati non hanno voci di clima** — la card lo dichiara, non lo nasconde.

## §5 — Misure e gate (build #4, 2026-10-11 sera)

| gate | esito |
|---|---|
| `pytest -q` | **637 passed** (+4 test: soggetto/edicola, club nel titolo, soglia del fatto, unità delle tre funzioni) |
| `ruff check` | pulito |
| `fda build` | 493 partite · 2.364 fixtures · 7.578 giocatori |
| `verify_site` | **0 problemi · 238.062 controlli** ([49] estesa: nota con 3 frammenti nuovi — «il club si vede nel titolo», «avversario di passaggio», «fra virgolette è la frase di qualcun altro» — e ricalcolo con la guardia sull'oggetto e la soglia ≥4) |
| `audit_clima` | **0 difetti** · 72 righe (bad 4 · warn 34 · good 34) · 44 voci elencate · 13 marcate · 138 vuoti dichiarati · 0 scostamenti |
| `parita_schede` | nessuna differenza |
| `resa_375` | **28.482 misure · 0 problemi** |
| `audit_fonti` | 0 difetti bloccanti · 4 avvisi · exit 0 |

Nessuna richiesta alle fonti esterne è stata fatta per questo lavoro: tutte le misure vengono
dai Parquet raccolti.

## §6 — Cosa resta aperto (dichiarato, non risolto)

1. **La stessa storia da più testate conta più volte.** La curva Sud della Juventus è raccontata
   da 4 titoli diversi questa settimana: 4 voci, e il conteggio lo dice (l'elenco le mostra tutte
   e quattro). Non è un errore — sono quattro titoli — ma il numero non distingue «quanto è
   grande la storia» da «quante testate l'hanno ripresa». Servirebbe un raggruppamento per
   storia con una soglia di somiglianza **misurata**: rinviato, non stimato a occhio.
2. **La copertura non è uniforme**: NED1 e POR1 hanno **0** voci di clima in 14 giorni, la FRA1
   ne ha 5. Il vuoto è dichiarato in ogni card, e la nota dice che è vuoto di raccolta, non
   quiete dimostrata.
3. **I gate guardano il titolo**, non il brano (scelta dichiarata al §3): la prossima
   iterazione può guardare la descrizione per i casi in cui il club è nel brano e non nel
   titolo — ma allora la card deve pubblicare la descrizione, altrimenti il lettore non può
   controllare il conteggio.
4. **`SOPRANNOMI` va ampliato con le cadute vere**, non con i nomi che ci vengono in mente: il
   contatore `fuori_soggetto` (e l'elenco delle 14 cadute in questo documento) è il punto di
   partenza.
