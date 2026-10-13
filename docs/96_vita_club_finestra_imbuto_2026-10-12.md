# 96 — Vita del club: periodo, selezione e conti verificabili (2026-10-12)

**Perimetro:** terza delle sei sezioni richieste. **63 schede / 126 lati-squadra**, sullo
stesso snapshot CI `514309d`, senza raccogliere o riscrivere dati. Codice precedente `1d85ae4`.
Anteprima richiesta dall'utente: a fine giro la scheda Torino–Udinese si aprirà su `#notizie`.

## 1. Ripristino verificato dell'ambiente

Il sandbox ripristinato aveva i file del lavoro precedente ma Git puntava ancora a `514309d`;
venv, sito e server temporaneo erano assenti. Prima di riallineare il ramo si sono confrontati
**33 file**, byte per byte/hash, con `origin/arena/8d89284f-football-deep-analyzer`: **zero
differenze**. Solo dopo: reset **mixed** al ramo già salvato, senza toccare i file di lavoro.
Ricreato il venv; baseline delle 63 schede rigenerata dal codice precedente in cache.
Nessuna modifica o perdita di lavoro, nessun cambio di branch.

## 2. Misure prima di correggere

L'archivio news contiene **6.257 righe**, 132 squadre, dal **28/09 al 12/10/2026**; 632
ripetizioni della coppia squadra/URL. La descrizione RSS presente non equivale al testo
integrale dell'articolo: non si fa passare la lettura del titolo per una verifica giornalistica.

Nel perimetro realmente pubblicato:

| Grandezza | Prima |
|---|---:|
| Voci esaminate nella finestra | **1.522** |
| Titoli pubblicati | **47** |
| In riserva | **9** |
| Lati senza righe nella finestra | **42** |
| Voci più vecchie della finestra, contate a parte | **5.140** |

La prima scansione esplorativa comprendeva 65 fixture con dettagli, non il sito: una gara
annullata e una fuori dalla finestra del build sono state escluse **prima del confronto**.
Non si attribuiscono al sito i conteggi di quella scansione preliminare.

### A. La scelta dipendeva dall'ordine fisico delle righe

Invertendo soltanto le righe di `news.parquet` in memoria, **5 colonne** cambiavano voci,
URL o date (Venezia, Udinese due volte, Milan, Roma). Quattro voci esposte usavano una copia
precedente a un'altra già in archivio, fino a oltre un giorno di differenza.

La deduplicazione avveniva prima dell'ordinamento finale. Inoltre un candidato poi escluso
per i limiti prenotava comunque il titolo nell'insieme condiviso, potendo sopprimerlo nella
colonna avversaria senza che nessuno lo pubblicasse.

**Correzione:** ordine deterministico per data e chiavi di parità; rappresentante più
recente **fra le versioni ammissibili**, senza mescolare campi di righe diverse. Una copia
più recente ma in altra lingua/a bassa reputazione non elimina la versione valida. L'insieme
condiviso contiene solo i titoli **effettivamente esposti**, riserve comprese.

**Cautela:** è la data indicata dalla fonte, non una prova della prima pubblicazione. Una
ripubblicazione non viene raccontata come un nuovo fatto indipendente. Storie diverse con
titoli diversi non diventano automaticamente un unico evento.

### B. Due imbuti non chiudevano

Per Torino e Udinese sulla scheda **5749699**, esaminate ≠ pubblicate + riserva + escluse:
mancava **una voce per squadra**, rimasta oltre la capienza della riserva senza contatore.
In più, copie e soggetti ripetuti potevano essere classificati come «servizio o cronaca».

Ora ogni riga esaminata ha **un solo esito**. I doppioni sono contati come tali; i limiti
per categoria e per capienza sono distinti e la loro somma coincide con «oltre i limiti».
Le voci vecchie restano esterne al totale esaminato. Il testo parla di **voci di raccolta**,
non lascia intendere che copie ripetute siano titoli distinti.

### C. Titoli esclusi a parole, ammessi dal codice

Esempi reali esposti prima della revisione:

- «Formazioni CDA Navalcarnero - Betis Siviglia: Coppa del Re Calcio»;
- «Real Madrid-Villarreal LIVE! Cronaca e aggiornamenti in tempo reale…»;
- convocati/recuperi e annunci d'esordio, già trattati nelle altre sezioni;
- «Incontro per i media con il tecnico Abate»;
- un compleanno/intervista celebrativa e una notizia sull'Udinese Academy;
- cronache, interviste senza un fatto nel titolo e risposte virali sui social.

Aggiunti veti **locali a Vita del club**, per famiglie di titoli, non per nomi di squadre o
per singoli URL. Una conseguenza esplicita (inchiesta, esonero, sanzione, protesta, azionista,
ecc.) non viene scartata dal nuovo veto solo perché menziona una presentazione o l'Academy.
I controlli positivi proteggono questi casi; restano applicabili anche i filtri preesistenti.

Il controllo di soggetto usa parole intere: Roma non coincide con romanzo o Romagnoli.
Sono conservate le elisioni italiane: «all’Atalanta»/«dell’Inter» non diventano falsi negativi
quando la normalizzazione toglie l'apostrofo. Un club chiaramente in testa al titolo non
può diventare la notizia di un altro club citato solo nel confronto.

**Limite editoriale:** non è comprensione completa del testo. I filtri possono sbagliare e
non certificano né la verità delle notizie né il loro effetto sulla partita. Nessun nuovo
punteggio di sentiment, nessuna variazione delle soglie o dei pesi del Clima.

## 3. Il vuoto non dimostra quiete

«Negli ultimi 7 giorni» descriveva male una finestra ancorata a una gara futura. Ora si
vedono **inizio e fine assoluti** e lo stato del periodo:

- settimana non ancora iniziata;
- finestra ancora aperta, raccolta potenzialmente incompleta;
- finestra terminata, ma copertura limitata ai titoli raccolti.

Si escludono anche date successive alla costruzione della pagina, non solo successive al
kickoff. Orologio iniettabile e test sui confini esatti. Sul campione misurato: **58 finestre
aperte e 5 terminate**; il caso non ancora iniziato è coperto con dati sintetici.

Via l'affermazione «Niente che possa spostare qualcosa»: si dichiara **nessun titolo
selezionato**, non assenza di fatti importanti nel mondo. La sezione resta presente anche
senza titoli e senza «Da sapere». Il richiamo «Perché conta» distingue inoltre distinta
ufficiale, prevista, precedente e tipo non dichiarato, senza promettere un impiego certo.

Le date disponibili non sono timestamp di prima conoscenza della fonte: questo filtro
non trasforma l'archivio in un backtest prospettico. Le notizie restano citazioni con link,
non fatti verificati tramite la lettura dell'articolo completo.

## 4. Esito della misura dopo le correzioni

Sulle stesse **1.522 voci / 126 lati**:

| Esito dell'imbuto | Dopo |
|---|---:|
| Pubblicate | **32** |
| In riserva | **3** |
| Servizio/cronaca o già altrove | **1.016** |
| Annunci/logistica | **14** |
| Senza un fatto specifico nel titolo | **18** |
| Su un'altra squadra | **3** |
| Doppioni | **12** |
| Altra lingua | **145** |
| Fonte a bassa reputazione | **277** |
| Oltre i limiti di esposizione | **1** |
| Fuori ambito prima squadra | **1** |
| **Totale** | **1.522** |

Gli imbuti non chiusi passano **2→0**; invertire le righe ora cambia **0 colonne su 126**.
Voci esposte (pubblicate + riserva) **56→35**: 23 escono, 2 entrano dopo il riordinamento e
la rimozione dei veti. Questo conteggio **non è una metrica di qualità** e non rende ogni
voce rimasta utile per definizione: è l'impatto controllabile della revisione.

«Da sapere» mantiene calcoli e criteri precedenti. Le regole del Clima sono invariate;
possono cambiare i soli marcatori che dicono se una voce è anche esposta in Vita del club.
Nessuna modifica a probabilità, modelli, mercato, panchina o Parquet.

## 5. Invarianti, audit e gate

Nuovo **`scripts/audit_vita_club.py`**, con `--site`, `--data`, `--json` ed exit 1 su difetti
o nessuna card verificabile. Non chiama `team_news`: controlla periodo, fase della finestra,
conteggi e loro conservazione, limiti, duplicati fra le due colonne, e la tupla esatta
**titolo / URL / fonte / data** nei Parquet della squadra. Sette kill-test alterano numero,
data, titolo, link, testata, periodo e copertura, con il generatore reso inutilizzabile.

[20] resta riconciliazione della selezione ma incorpora gli oracoli indipendenti: passa
**da S a M**, non a I. Il ratchet si stringe sugli specchi **4→3**, con massimo invariato
**S+M≤23** e **I≥31**: non si autorizza alcuna retrocessione di controlli indipendenti.

**Gate finali eseguiti:**

- **850 test passati**, `ruff check .` pulito.
- **`fda build`: 498 schede / 2.364 fixture / 7.594 giocatori**.
- **`verify_site`: 241.464 controlli, 0 problemi**; 54 oracoli, 31 I / 20 M / 3 S.
- **Audit Vita del club: 987 controlli, 0 difetti**, sia sul frammento sia sul sito completo;
  anche audit Mercato (1.008 controlli), Panchina e Clima superati.
- **Parità: 63 schede, nessuna differenza**; resa a 375 px **28.669 misure, 0 problemi**.
- Confronto sul sito completo: **63 card Mercato e 63 Panchina identiche** nel testo visibile
  alla baseline. Nessun Parquet modificato, inclusi i due `season_sim*`.
- CI del codice **`5e45f35`** verde: run
  [38307602678](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38307602678) e
  [38307597677](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38307597677).

La prima suite completa aveva intercettato 19 fallimenti nel test del frammento Mercato:
il suo delimitatore dipendeva dall'`if` della card successiva. Corretto il test per chiudere
sulla propria card (senza indebolire le asserzioni); tutti i gate sono stati poi rieseguiti.

Misura macchina: [`_audit_vita_club_2026-10-12.json`](_audit_vita_club_2026-10-12.json).
**Anteprima ripristinata** su 0.0.0.0:8000: pagina iniziale → Torino–Udinese, `#notizie`.
Scheda, homepage, CSS e font CSS verificati HTTP 200 con Host/Origin del proxy. Il dominio
è cambiato con il nuovo sandbox: il link precedente non identifica questa istanza.
La preview mostra i dati CI dello snapshot, non un nuovo aggiornamento delle fonti.

**Terza sezione verificata**, con i limiti editoriali sopra dichiarati. PR #108 ancora in
bozza, nessun merge o pubblicazione su `main`.

## Prossimo passo

Passare a **Previsione ensemble**, seguita da Precedenti e Verifica approfondita,
mantenendo disponibile anche l'anteprima. StatsBomb e
la scelta sul clima restano decisioni aperte dell'utente. PR #108 in bozza, nessun merge.
