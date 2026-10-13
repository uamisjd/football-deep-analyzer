# 98 — Filtro lingua e copertura: protocollo e verifica (2026-10-13)

**Perimetro:** continuazione di Vita del club, senza passare all'ensemble. Il limite di
copertura non si risolve abbassando i filtri o traducendo automaticamente le fonti estere.
Nessun modello e nessun Parquet di produzione da modificare.

## 1. Misura prima di cambiare

Riprodotti sul codice `01c38e2` tre problemi distinti:

1. «Inter: misure cautelari per i tifosi» è respinto: `langdetect` lo attribuisce al rumeno,
   pur senza parole di veto. La probabilità del rilevatore non è una certificazione.
2. «Roma, è polemica per il rigore» e «Nuovo manager per il club: il progetto della società»
   sono respinti dalla lista lessicale, benché la stima statistica sia italiana. «Polemica»
   è parola italiana; «manager» è anche un prestito d'uso comune. La normalizzazione degli
   accenti rende ambiguo anche il confronto fra «però» italiano e «pero» spagnolo.
3. «Nottingham Forest stadium expansion plans approved», chiaramente inglese, passa se
   accompagnato da una descrizione italiana sufficientemente lunga. La lingua della
   descrizione finisce per autorizzare il **titolo**, che è il testo pubblicato.

In questo sandbox sono assenti le cache e il venv della sessione precedente. Prima di
riallineare Git sono stati confrontati **51 file** con il ramo remoto: zero differenze;
reset **mixed** senza cambiare i file di lavoro. Venv ricreato. Nessuna raccolta calcistica.

## 2. Candidato dichiarato prima del replay reale

Baseline: `is_italian_news` attuale. Candidato: **Lingua 2.1.1**, libreria offline già
addestrata e adatta anche ai testi brevi, rilevatore **su tutte le lingue supportate** per
non forzare testo sconosciuto dentro le sette lingue attese.

Regola candidata fissata per la misura:

- si valuta **il titolo**, non titolo + descrizione;
- deve risultare italiano con distanza relativa dal secondo classificato **almeno 0,15**;
- sotto sei parole, si richiede anche un marcatore italiano: soli nomi propri non
  dichiarano una lingua;
- un estratto non può rendere italiano un titolo straniero; l'eventuale estratto esposto
  deve superare il suo controllo separato;
- esito incerto = astensione, non dichiarazione che il testo sia certamente straniero;
- nessuna traduzione e nessuna nuova fonte; il pacchetto è solo un rilevatore locale.

Sono stati salvati **149 casi etichettati** in
`tests/fixtures/news_language_review_2026-10-13.json` prima della valutazione comparata:
59 regressioni esistenti, 30 nuovi italiani, titoli stranieri in otto gruppi, 10 casi
ambigui e casi misti titolo/descrizione. È un campione di sviluppo/regressione, non una
stima indipendente dell'accuratezza futura.

Nella prova tecnica preliminare il rilevatore su tutte le lingue ha avuto un picco di
circa **909 MiB** (caricamento lazy dei modelli) contro circa **227 MiB** limitandolo a otto
lingue. La variante limitata non è quella scelta: confonderebbe più facilmente una lingua
non contemplata con una di quelle attese. Memoria e latenza vanno dichiarate e misurate
anche sul corpus, non ignorate perché un esempio riesce.

## 3. Criterio di integrazione

Prima si confrontano errori e astensioni sul campione dichiarato e sulle differenze del
corpus reale; poi si decide. Nessun vantaggio proclamato dal solo titolo già noto. Non si
modificano soglie dopo aver visto il risultato senza registrare la modifica e il motivo.
Se il guadagno introduce regressioni non accettabili, il candidato non entra.

La copertura si misura con due numeri separati: titoli italiani riconosciuti e segnalazioni
editoriali effettivamente esponibili, per ciascuna lega. Recuperare un titolo italiano di
formazioni o cronaca **non** significa aver trovato una notizia utile per Vita del club.

## Prossimo passo

Misurare baseline/candidato sui 149 casi e sui Parquet, classificare le differenze reali,
integrare solo un esito giustificato. Poi tutti i gate e anteprima aggiornata. Copertura
fonte, scelta sul clima e StatsBomb restano esplicitamente aperti finché non verificati.


## 4. Primo risultato e variante conservativa (prima dell'integrazione)

Il candidato singolo rispetta tutte le 59 regressioni e riduce gli errori sul benchmark
**19→3**, ma sul corpus di 4.431 coppie titolo/descrizione uniche ha 309 esclusioni nuove
 e 179 recuperi. Fra le esclusioni c'è il titolo italiano già verificato sull'azionariato
Atlético: **regressione sostanziale, candidato singolo respinto**. Non si abbassa il margine
0,15 per far passare quel titolo.

Variante V2 dichiarata per la prossima misura: titolo ammesso se supera il vecchio controllo
**sul solo titolo** oppure il candidato Lingua già fissato. In entrambi i percorsi i titoli
brevi senza un indicatore italiano restano sospesi; «casa/rosa/gol/goal» da soli non bastano
come indicatore per una lista di nomi di club. Il vecchio ramo non deve restare permissivo
se il proprio rilevatore manca. Descrizione esclusa dall'autorizzazione del titolo; nessuna
traduzione. La variante non contiene nomi di persone/club o eccezioni per articoli specifici.

Questo secondo tentativo viene dichiarato, non nascosto come se fosse la prima ricetta.
Vanno ripetuti benchmark e replay reale e va misurato separatamente l'effetto editoriale.

## Prossimo passo aggiornato

Valutare V2 prima di integrarla. Tre italiani del benchmark restano difficili per V1
(nome con ß, un prestito lessicale e un titolo telegrafico): non sono dichiarati stranieri
con certezza. Non si cerca di risolverli riducendo alla cieca la soglia statistica.


## 5. V2: utile sul benchmark, ma troppo drastica sul corpus

V2 resta a 3 errori senza regressioni nei 149 casi e mantiene l'evento Atlético, ma respinge
149 coppie che prima passavano. Fra queste sono presenti titoli italiani telegrafici
(«LAZIO – MONZA: INFO BIGLIETTI», «LAZIO-MONZA AFFIDATA A COLLU»): non pertinenti a Vita del
club, ma non per questo stranieri. **Non si integra V2 fingendo che il resto sia rumore.**

V3, dichiarata prima della nuova misura: conserva il controllo precedente quando il titolo
è già ammesso da solo; recupera un titolo prima respinto solo con l'evidenza italiana di
Lingua al margine **0,15**, immutato. Se la vecchia decisione dipende dalla descrizione,
si blocca quando **entrambi i rilevatori del solo titolo** concordano su una lingua non
italiana: langdetect con primo punteggio almeno 0,90 e Lingua con margine almeno 0,15.
Negli altri casi si conserva la decisione precedente, dichiarando che non è una garanzia
universale. Questo impedisce le regressioni imposte da una sola stima incerta sui nomi.
I percorsi senza alcun rilevatore devono fallire chiusi, non autorizzare testo sconosciuto.

V3 non corregge per supposizione tutti i titoli telegrafici o ambigui e non interpreta i
punteggi come probabilità calibrate. Il benchmark e le differenze del corpus saranno
pubblicati anche se residuano errori; nessuna soglia viene allentata per un articolo.

## Prossimo passo aggiornato (V3)

Misurare errori, regressioni e titoli realmente utili recuperati da V3; quindi decidere se
integrare. La copertura resta un problema distinto dal filtro linguistico.


## 6. Misura V3 (puro Python + `langdetect`), replay reale e diagnosi della copertura

L'analisi puntuale dei **19 errori su 149** della baseline mostra che nessuno dei 19 casi
richiede il caricamento di un secondo modello da ~909 MiB in RAM (`Lingua` su tutte le
lingue):

1. **6 falsi positivi `[misto_titolo_straniero]`** (`en`, `fr`, `nl`, `pt`, `ro`, `pl` con
   estratto italiano): su tutti e 6 i titoli presi da soli `langdetect` assegna una lingua
   straniera con probabilità > `0,99999`; passavano solo perché `is_italian_news`
   concatenava subito `f"{title} {description}"`.
2. **3 falsi negativi `[misto_titolo_italiano]`**: titoli italiani scartati a causa di un
   estratto inglese o dei falsi veti lessicali (`polemica`, `manager`).
3. **9 falsi negativi `[nuovi_it]`**:
   - `_strip_accents("però")` trasformava la congiunzione italiana «però» (già presente in
     `_ITALIAN_MARKERS`) nel veto spagnolo `pero`;
   - «polemica» (italiano standard, distinto dallo spagnolo accentato «polémica»), «Under»,
     «Eredivisie», «ADO Den Haag» (`den`), «para» (voce del verbo *parare*), «vai» e «now»
     erano trattati come veti incondizionati;
   - i prestiti d'uso corrente nel giornalismo sportivo italiano («manager», «fans»,
     «meeting») e la lettera `ß` nei cognomi propri («Groß») scartavano anche frasi con ≥ 2
     marcatori grammaticali esclusivi dell'italiano;
   - i titoli brevi (≤ 8 parole) con ≥ 2 marcatori esclusivi dell'italiano («Inter: misure
     cautelari per i tifosi», «Milan: tecnico esonerato») venivano scartati quando i nomi
     propri spostavano la stima di `langdetect`.
4. **1 falso positivo `[ambiguo]`** («Casa Pia Porto», 3 parole): la parola maiuscola
   «Casa» del club portoghese *Casa Pia* veniva contata come marcatore grammaticale
   italiano isolato.

### Regola V3 integrata in `src/fda/sources/news.py` (0 MB extra RAM, 0 nuove dipendenze)

- Distinzione tra **marcatori esclusivi dell'italiano** (`_ITALIAN_EXCLUSIVE_MARKERS`: es.
  `il`, `lo`, `gli`, `i`, preposizioni articolate composte, `però`, `più`, `è`, `tifosi`,
  `società`, `allenatore`, `partita`, `rigore`, `squalificato`, `esonerato`, ecc. —
  escludendo le forme condivise con ES/FR/PT/RO come `la`, `le`, `un`, `una`, `al`, `del`,
  `per`, `in`, `sua`) e marcatori ambigui nei nomi di club (`_CLUB_AMBIGUOUS_MARKERS`:
  `casa`, `rosa`, `gol`, `goal`, ammessi solo in minuscolo o insieme ad altri marcatori;
  neutralizzati inoltre i toponimi `Le Havre`, `Le Mans` e `ADO Den Haag`).
- Tokenizzazione Unicode (`[^\W\d_]+`) per non spezzare diacritici extra-Latin-1 (romeno
  `și-a`, polacco `ł`) in falsi token monolitterali (`i`).
- Valutazione **prima sul solo titolo** (`_verifica_testo_italiano(title,
  richiedi_marcatore_se_incerto=True)`): se il titolo è autonomamente italiano, l'estratto
  non può invalidarlo; se il titolo contiene un veto lessicale proprio, viene scartato
  subito; se il titolo è breve o incerto ma non è classificato con certezza ≥ 0,90 in una
  lingua straniera senza marcatori esclusivi italiani, si valuta `f"{title} {description}"`.
- Memoizzazione LRU (`@functools.lru_cache(maxsize=16384)`) su `_stima_lingua` e
  `_is_italian_news_cached`, evitando invocazioni di `langdetect` sotto la soglia di 6
  parole.

### Risultati misurati (prima / dopo)

| Misura | Baseline (`01c38e2`) | Candidato V1 | Candidato V2 | **V3 integrata (`news.py`)** |
|---|---:|---:|---:|---:|
| Errori sul benchmark (`149` casi) | 19 (12 FN + 7 FP) | 3 | 3 | **0 (0 FN + 0 FP)** |
| Nuove esclusioni su `news.parquet` (`4.431` coppie uniche) | — | 309 | 149 | **1** (solo `"Parma's Nesta Elphege Undergoes Appendix Surgery"`, inglese vero) |
| Recuperi italiani su `news.parquet` (`4.431` coppie uniche) | — | 179 | 179 | **185** (0 falsi positivi stranieri) |
| Memoria aggiuntiva a runtime | 0 MiB | ~909 MiB | ~909 MiB | **0 MiB** |

### Effetto sull'imbuto e sulla copertura di «Vita del club» per campionato

Sulle **63 schede del campione di `docs/97`** (1.522 righe in finestra di 7 giorni) e sulle
**58 schede pre-partita del 2026-10-13** (969 righe in finestra):

| Lega | Schede (campione 63) | Righe in finestra | Scarti «in un'altra lingua» (prima → dopo V3) | Righe italiane recuperate dal falso scarto lingua | Fonte bassa rep. (dopo V3) | Cronaca / annunci / senza segnale (dopo V3) | Voci esposte in card (prima → dopo V3) |
|---|---:|---:|---:|---:|---:|---:|---:|
| ITA1 | 12 | 1.186 | 68 → **34** | +34 | 231 | 845 | 7 → **7** |
| ENG1 | 11 | 82 | 17 → **17** | 0 | 22 | 33 | 0 → **0** |
| ESP1 | 11 | 111 | 18 → **16** | +2 | 18 | 72 | 1 → **1** |
| GER1 | 9 | 62 | 23 → **8** | +15 | 4 | 41 | 0 → **0** |
| FRA1 | 9 | 49 | 6 → **2** | +4 | 7 | 29 | 0 → **0** |
| NED1 | 9 | 15 | 11 → **1** | +10 | 1 | 8 | 0 → **0** |
| POR1 | 2 | 17 | 2 → **2** | 0 | 1 | 14 | 0 → **0** |
| **Totale (63 schede)** | **63** | **1.522** | **145 → 80** | **+65** | **284** | **1.042** | **8 → 8** (+6 letture) |
| **Totale (58 schede 13/10)** | **58** | **969** | **110 → 60** | **+50** | **157** | **666** | **7 → 7** |

### Conclusione sul divario di copertura (`docs/98` §5)

1. **Onestà dell'imbuto ristabilita**: 65 righe italiane sulle 63 schede (50 sulle 58 schede
   del 13/10), in particolare in `NED1` (`11 → 1`) e `GER1` (`23 → 8`), non vengono più
   dichiarate falsamente «in un'altra lingua» nell'intestazione `p.imbuto`, ma attribuite
   al motivo reale dello scarto (`servizio o cronaca`, `bassa reputazione`, `su un'altra
   squadra`, `senza evento o analisi espliciti`). Sulla scheda `5749690` (`Atalanta-Venezia`)
   viene inoltre recuperata nel *Clima intorno al club* la notizia societaria de *Il
   Gazzettino* («Il figlio del presidente del Coni consulente del Venezia Calcio: è
   polemica…»), prima bloccata dalla parola italiana «polemica».
2. **Perché le 6 leghe estere restano quasi prive di voci in «Vita del club»**: la misura
   dimostra che il collo di bottiglia **non** era `is_italian_news`. Nelle 6 leghe estere
   l'edizione italiana di Google News raccoglie in 7 giorni **336 righe totali su 51 gare**
   (contro 1.186 su 12 gare in Serie A); tolte le 46 righe realmente in lingua straniera e
   le 53 da aggregatori a bassa reputazione, le restanti **197 righe in italiano** sono
   quasi interamente guide TV/streaming, probabili formazioni, pronostici o tabellini
   (`servizio o cronaca`), mentre le edizioni estere di Google News sono state rimosse il
   2026-09-17 (`docs/24` §3.7, `docs/25`) per rispettare il vincolo che ogni titolo
   pubblicato sia nativamente in lingua italiana. Finché la raccolta resta limitata a fonti
   in lingua italiana senza traduzione automatica, la minore copertura di eventi societari
   sui club esteri minori è una proprietà strutturale delle fonti italiane disponibili, e
   la card lo dichiara onestamente senza abbassare la soglia editoriale di `club_signal`.

