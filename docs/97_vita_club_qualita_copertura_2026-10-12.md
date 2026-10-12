# 97 — Vita del club: audit editoriale e di copertura riaperto (2026-10-12)

Richiesta dell'utente: verificare davvero se la sezione sia accurata, efficace e intuitiva
**per tutte le partite**, con ricerche approfondite. **La risposta precedente era troppo
netta:** i gate di docs/96 provavano coerenza tecnica, non utilità editoriale o copertura.
Non si passa all'ensemble dando per risolta questa domanda.

## 1. Che cosa vogliamo misurare (prima di correggere)

Una voce in questa sezione deve riguardare il club/la prima squadra e contenere:

1. un **evento specifico** di società, finanze, panchina, disciplina, tifoseria/accesso o
   impianto, con un elemento esplicito nel titolo; oppure
2. un'**analisi/dichiarazione attribuita** sulle dinamiche del club, separata dai fatti.

Non bastano un nome di squadra, una parola come «tifosi», la categoria «Società» assegnata
per regex o la freschezza. Formazioni, infortuni/mercato già trattati altrove, cronache,
statistiche tecniche, motivazione generica, VIP e commemorazioni non riempiono i tre posti.
Questo è un **perimetro editoriale**, non una misura dell'effetto sul risultato.

Prima di modificare il selettore sono stati annotati **tutti i 31 titoli distinti esposti**
(35 occorrenze fra schede e riserve): 7 con evento esplicito, 3 analisi/dichiarazioni ammissibili,
21 fuori dal perimetro o insufficienti. Scheda completa in
`tests/fixtures/vita_editorial_review_2026-10-12.json`: ragione per ogni titolo, senza
chiamare «falso» ciò che è solo poco pertinente. Due dei 7 titoli di evento riprendono la
stessa vicenda. È un campione di sviluppo **manuale e non cieco**, non una stima indipendente
della precisione futura. La recall richiederebbe un catalogo esterno completo degli eventi:
non la inventiamo dai titoli che il collector ha trovato.

## 2. La copertura non è uniforme

Snapshot CI `514309d`, build del branch `5f9028e`, 63 schede / 126 lati:

| Lega | Schede | Lati | Righe in finestra | Lati con righe | Titoli + riserve | Lati con titoli |
|---|---:|---:|---:|---:|---:|---:|
| ITA1 | 12 | 24 | 1.186 | 20 | 33 | 16 |
| ENG1 | 11 | 22 | 82 | 13 | 0 | 0 |
| ESP1 | 11 | 22 | 111 | 17 | 2 | 2 |
| GER1 | 9 | 18 | 62 | 18 | 0 | 0 |
| FRA1 | 9 | 18 | 49 | 9 | 0 | 0 |
| NED1 | 9 | 18 | 15 | 5 | 0 | 0 |
| POR1 | 2 | 4 | 17 | 2 | 0 | 0 |

**108 lati su 126 senza titoli selezionati; cinque leghe senza alcuna voce esposta.**
È un limite di raccolta, periodo e selezione, non la prova che quelle squadre non abbiano
vicende rilevanti. 58 finestre sono ancora aperte: non si può raccogliere ora la stampa
che uscirà in futuro. Le fixture più lontane non hanno ancora la settimana di vigilia.

Una scansione supplementare di tutti i titoli esclusi ma con parole di eventi forti
nel periodo ha trovato 8 candidati distinti, tutti associati a Torino: sei altre riprese
sui provvedimenti del derby, una dichiarazione da valutare e un esonero della nazionale
turca (altra squadra). Nelle altre leghe due candidati con parole generiche erano una
cronaca del Mainz e un articolo sull'**Athletic Club Palermo**, non il club di Bilbao.
Non emerge da questo controllo una riserva di fatti societari pronta a coprire tutte le leghe.

## 3. Verifiche esterne, con livello della prova dichiarato

Ricerca web e lettura delle pagine accessibili; nessuna raccolta automatica aggiunta al
programma, nessun testo di articolo riversato nei Parquet. Titoli e metadati locali da soli
non certificano il contenuto. Le ricerche senza risultato non dimostrano che un articolo
sia falso. I link Google RSS non sempre si risolvono: registrare questo limite, non
attribuire loro automaticamente il contenuto di un risultato omonimo.

### Collisione Idrissa / rissa — difetto di codice certo

`classify_news("Nota ufficiale: Idrissa Gueye", ...)` restituisce **fuoricampo, «rissa»**:
la regex trova una sottostringa dentro **Idrissa**. Riprodotto anche con descrizione vuota.
Questo errore non ha bisogno di inferenze giornalistiche per essere dimostrato.

Una nota ufficiale **con lo stesso titolo, testata e data** (5 ottobre) riguarda invece un
intervento alla caviglia: materia degli indisponibili, non un fatto giudiziario. La pagina
è stata letta, ma il redirect dello specifico URL Google RSS ha restituito errore: la
corrispondenza esterna è per metadati, non una catena di redirect verificata.
[1](https://www.udinese.it/Apps/WebObjects/Udinese.woa/wa/viewSection?id=93019&lang=ita)

### Casi pertinenti preservati

- **Genoa, nuovi incarichi:** il comunicato del club conferma l'ingresso di Modesto e
  Melissano e i rispettivi ruoli. È vita societaria, non un generico «ufficiale» di mercato.
  [1](https://genoacfc.it/2026/10/11/genoa-cfc-francois-modesto-chief-of-football-stefano-melissano-direttore-sportivo/)
- **Atlético, azionariato:** conferma sul sito ufficiale dell'ingresso di Gilgeous-Alexander;
  la fonte italiana della card non è l'unica evidenza. Non si inventano quota o importo.
  [1](https://en.atleticodemadrid.com/noticias/shai-gilgeous-alexander-joins-atletico-de-madrid-ownership-group)
- **Atalanta/Sarri:** letto il pezzo originale. È un'analisi giornalistica sul rapporto
  squadra-tecnico e sulle possibili scelte, non un esonero annunciato né una probabilità.
  [1](https://bergamo.corriere.it/notizie/sport/atalanta/26_ottobre_12/atalanta-venezia-dira-se-la-squadra-segue-davvero-sarri-499326d0-7d6d-4ca7-8830-2a1d93c4exlk.shtml)
- **Venezia/stadio:** titolo e riscontro indicizzato ANSA descrivono variante approvata e
  maggiori costi. La fetch diretta ha mostrato anche il gate cookie/abbonamento: non
  si dichiara lettura integrale né lo si aggira. Rilevanza societaria di medio periodo,
  non effetto certo sulla prossima gara.
  [1](https://www.ansa.it/sito/notizie/sport/calcio/2026/10/07/calcio-a-venezia-variante-al-progetto-stadio-costi-su-di-un-milione_78746068-7814-4f8f-8248-17a95b2e5cf3.html)

### Una vicenda, più titoli; data del pezzo ≠ data del fatto

Tuttosport e la ripresa video della notizia «oltre 20 misure» descrivono i provvedimenti
annunciati il 6 ottobre per gli scontri del **24 maggio**. LaPresse li riscontra come
misure per 22 persone. Non sono due nuovi scontri questa settimana, né tante vicende
quante sono le testate. Il raggruppamento automatico deve restare prudente: stessi tema
 e giorno non garantiscono identità dell'evento; i titoli correlati non vanno cancellati.
[1](https://www.tuttosport.com/news/calcio/serie-a/juventus/2026/10/06-151708783/scontri_torino-juve_misure_cautelari_per_tantissimi_tifosi_coinvolti_la_decisione_della_digos)
[1](https://stream24.ilsole24ore.com/video/italia/torino-juventus-oltre-20-misure-cautelari-i-tifosi-entrambi-club/AJfm7eaB)
[2](https://www.lapresse.it/cronaca/2026/10/06/scontri-torino-juventus-blitz-della-polizia-misure-cautelari-per-22-ultras/)

Altri riscontri: ritorno dei tifosi Roma in trasferta riportato nella cronaca (non dedurre
una specifica norma revocata dal solo titolo);
[1](https://www.corrieredellosport.it/news/calcio/serie-a/2026/10/11-151799977/como-roma_diretta_serie_a_segui_il_match_tra_fabregas_e_gasperini_live)
confronto fra i tecnici Spalletti/Pisacane riportato da più testate (non anticipare pene
non deliberate);
[1](https://www.ilfattoquotidiano.it/2026/10/12/spalletti-pisacane-lite-cagliari-juventus-notizie/8534965/)
sostegno pubblico di De Laurentiis al tecnico, da trattare come dichiarazione;
[1](https://www.ansa.it/sito/notizie/sport/calcio/2026/10/12/calcio-de-laurentiis-mai-avuto-dubbi-su-allegri_2fb640f6-3a67-49b7-a5e9-97bb5c1854f0.html)
reportage sul Como ripreso da QuiComo, lettura attribuita e non fatto sintetico autonomo.
[1](https://www.quicomo.it/attualita/times-como-1907-tifosi-turismo-scuola-perti-rapinese.html)

## 4. Intervento pianificato, ancora da verificare

- Correggere la collisione lessicale alla radice, con controesempi positivi e negativi.
- Richiedere un **segnale positivo esplicito**, non soltanto assenza di parole vietate.
  Separare evento e analisi/dichiarazione, mantenendo titolo, fonte, data e link.
- Rendere visibile la copertura e non spacciare la mancanza di materiale per quiete.
- Rendere i dati «Da sapere» un contesto riconoscibile, non riempimento della rassegna.
- Conservare tutte le fonti di titoli correlati senza contarle come eventi indipendenti.
- Misurare il nuovo selettore sui 31 casi annotati e su casi di controllo separati; non
  trasformare il risultato sul campione di sviluppo in un claim di accuratezza universale.

**Gate ancora da eseguire dopo le correzioni.** Nessun modello o Parquet modificato,
nessun merge. La copertura delle fonti resta un problema aperto da non nascondere.


## 5. Continuazione verificata il 13/10/2026: ricerca primaria e prova in ombra

Recuperato il checkpoint `40d56f8` già sul ramo remoto: i due file di ricerca e le etichette
non erano nel filesystem ripristinato. Confrontati i restanti file; la copia locale di
STATO era esattamente il suffisso della versione remota. Recupero senza sovrascrivere codice
locale divergente. L'ambiente Python è stato ricreato; nessun Parquet modificato.

**Riletti tramite lo strumento web, non tramite la rete del collector del sandbox:** nota
Udinese del 5 ottobre (intervento alla caviglia, non rissa), comunicato Genoa dell'11 ottobre
(incarichi), comunicato Atlético (azionariato). Le letture confermano i livelli di prova
sopra; nessun testo originale è stato importato nel sito o nei dati.

Nuovo riscontro primario: [Polizia di Stato](https://www.poliziadistato.it/articolo/scontri-prima-del-derby-torino-juventus--22-misure-cautelari-e-42-daspo),
comunicato del **6/10/2026**: **22 misure cautelari e 42 Daspo**, riferiti agli incidenti
prima del derby del **24 maggio**. I titoli della rassegna citano numeri e grandezze diverse:
non vengono sommati, uniformati né spacciati per conferme indipendenti. Pubblicazione,
provvedimento e incidente originario non sono la stessa data.

Ricerche di controllo per le leghe scoperte: la query italiana su Benfica ha restituito
anche [1](https://www.diretta.it/news/calcio-liga-portugal-rui-costa-domina-le-elezioni-l-ex-giocatore-rieletto-presidente-del-benfica/8GM2cFKE/);
quella su Ajax anche [1](https://www.tuttomercatoweb.com/calcio-estero/ufficiale-ajax-rivoluzione-in-dirigenza-ad-amsterdam-c-e-un-nuovo-director-of-football-1905961).
Sono fuori periodo: **non si riciclano per riempire le schede attuali**. La ricerca senza
riscontro coevo non dimostra che non ci siano eventi; non è una misura di recall.

**Prima di integrare:** `club_signals.py` provato in ombra sulle 31 annotazioni già committate
prima del codice: **31/31 corrispondenze**. Altri 28 controlli separati, positivi e negativi,
portano a **59 test** del criterio. È conformità al perimetro di sviluppo, non «100% di
accuratezza» sul mondo o su notizie future. Fra i controlli separati è emerso che vietare
«quote» avrebbe escluso quote societarie: il veto è rimasto solo nel contesto delle scommesse.

## 6. Correzioni e presentazione, ancora sotto gate finali

- Collisione `Idrissa`/`rissa` eliminata nel classificatore: confini di parola, controlli su
  nomi e su vere risse. Non basta nasconderla soltanto in una pagina.
- Il selettore richiede un **segnale positivo nel titolo**. `Evento segnalato` e
  `Analisi / dichiarazione` hanno etichette diverse; smentite, ipotesi e citazioni non
  vengono trasformate in eventi accertati. La porzione di titolo che attiva il segnale
  rimane visibile. Non si fabbricano sintesi o effetti sulla partita.
- Il solo nome della stessa persona non è più prova dello stesso evento. I titoli sullo
  stesso segnale/tema possono stare in un dettaglio di **letture sul tema**, tutti con
  fonte, data e link. Questo non certifica identità dell'evento o indipendenza delle fonti.
- Copertura per squadra in apertura: righe raccolte e titoli consultabili. Lo zero è
  dichiarato, non coperto da frasi generiche. La rassegna resta parziale e solo italiana.
- «Da sapere» resta consultabile come **Dati di contesto della partita · non sono notizie
  di stampa**, distinto dalla rassegna. Nessun numero viene eliminato o modificato.
- Date etichettate come **articolo**, non data certa dell'evento. Le ore al fischio restano
  una componente interna dell'ordinamento, non un numero che suggerisca impatto predittivo.

Sul campione fisso del 12/10, con gli stessi 1.522 input: **10 titoli principali + 6 letture
sul tema**, 15 titoli distinti, 10 lati con segnalazioni (9 ITA1, 1 ESP1). Le altre cinque
leghe restano senza voci esposte. I 5 titoli non presenti nelle annotazioni iniziali sono
stati riletti dopo la selezione: tutte ulteriori riprese dei provvedimenti sul derby, non
nuovi eventi dimostrati. Questo secondo controllo **non è validazione cieca** e non entra
nel 31/31. I titoli con numeri diversi restano attribuiti alle fonti, senza riconciliazioni
arbitrarie.

Misura ripetibile: `scripts/audit_vita_editoriale.py --reference-date 2026-10-12`.
Audit tecnico sul frammento: **946 controlli, 0 difetti**. Test mirati complessivi:
**299 passati**, Ruff pulito. In attesa dei gate completi e dell'anteprima ricostruita.

## Prossimo passo

Eseguire suite completa, build, verify_site, audit e resa mobile; mostrare l'anteprima.
**Non dichiarare risolta la copertura per tutte le partite:** non lo è. Decidere poi come
estendere e verificare la raccolta italiana via CI, senza inventare notizie, cambiare i
Parquet qui o aggirare protezioni. La revisione di Vita del club resta aperta su questo
punto; non si passa automaticamente all'ensemble. PR #108 in bozza, nessun merge.
