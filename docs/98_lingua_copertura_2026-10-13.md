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
