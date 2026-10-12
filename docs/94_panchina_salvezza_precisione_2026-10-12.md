# 94 — Revisione «Panchina e posta in gioco» (2026-10-12)

**Perimetro:** prima delle sei sezioni richieste. Misura sulle **63 schede pre-partita /
126 celle-squadra** del sito generato dai Parquet CI `514309d`; nessuna nuova raccolta.
La revisione precedente è in `docs/78`–`80`: non si riaprono scelte senza una nuova misura.

## 1. La misura iniziale: l'audit verde non bastava

`audit_panchina.py` segnalava zero scostamenti: nomi, permanenza, punti/gara, gol,
classifica, percentuali, età e segnaposto coincidevano con il suo ricalcolo. La lettura
**semantica dei ranghi** ha però trovato due rami sbagliati, ripetuti anche nell'audit:

### Pari punti non significa fuori dalla retrocessione — 5 celle

| Scheda | Squadra | Rango e punti | Testo pubblicato prima |
|---|---|---|---|
| 5749703 | Fiorentina | 19ª, 4 punti | in zona salvezza diretta |
| 5749707 | Parma | 18ª, 4 punti | in zona salvezza diretta |
| 5795468 | Coventry | 19ª, 3 punti | in zona salvezza diretta |
| 5795484 | Tottenham | 18ª, 3 punti | in zona salvezza diretta |
| 5795484 | Coventry | 19ª, 3 punti | in zona salvezza diretta |

Erano a pari punti con la 17ª, **ma il rango ufficiale le collocava ancora in zona
retrocessione**. Il codice trasformava una distanza di zero punti in salvezza.
Ora: **«a pari punti con il 17º posto (salvezza diretta)»**, senza cambiare il rango né
attribuire la salvezza. Un'eventuale classifica non monotona per punti non autorizza né
una salvezza né una parità inventata: resta dichiarata la zona del rango.

### Il 16º posto è lo spareggio, non la salvezza diretta — 2 numeri errati

Nei quattro campionati a 18 del progetto (GER1, FRA1, NED1, POR1), l'ultima salvezza diretta
è la **15ª**. I tre posti a rischio sono già quelli usati dalla simulazione (`REL_COUNTS=3`):
non viene modificato il modello. La riga delle distanze usava invece i punti della 16ª.

| Scheda | Squadra | Distanza prima | Distanza corretta dalla 15ª |
|---|---|---:|---:|
| 5781768 | Willem II | 2 punti | **4 punti** |
| 5781776 | ADO Den Haag | 1 punto | **3 punti** |

Sono 6 le celle di squadre in retrocessione diretta nei campionati a 18: in altre quattro
la 15ª e la 16ª avevano gli stessi punti, quindi il difetto non cambiava il numero oggi.
Anche lì il riferimento è ora quello corretto. La nota distingue la zona di retrocessione
**diretta** (17ª/18ª) dalla **salvezza diretta** (15ª), senza spacciarle per complementari.
Corretto anche il commento della simulazione che chiamava erroneamente il terzo posto a
rischio tedesco «diretto»: era già uno spareggio nel significato dei tre posti modellati.
**Nessun calcolo della simulazione o Parquet cambiato.**

## 2. Il controllo deve poter fallire

`audit_panchina.py` terminava sempre con `return 0`. Prova isolata, prima della correzione:
una copia temporanea della scheda Parma con rendimento falsificato in **99,9 punti/gara
su 999 gare** produceva **1 scostamento PPG ma exit 0**.

Ora:

- exit **1** su scostamenti, silenzi, celle malformate, card pre-partita mancanti o nessuna
  scheda misurabile; exit 0 solo dopo una misura senza difetti;
- `--site`, `--data`, `--json` consentono controlli su copie senza toccare il sito o i dati;
- la copertura per lega conta le schede **pre-partita**, non tutte le 498 pagine;
- nuovi oracoli in `src/fda/site/panchina_checks.py`, senza importare il generatore:
  rango/zona e distanza dalla salvezza, numerosità MC e limite dell'errore standard;
- usati sia nell'audit sia in **[19] di `verify_site`**, che ora legge la classifica nella
  **cella corretta**, non cerca il testo indistintamente in tutta la pagina.

**Prova prima di correggere il generatore:** nuovi oracoli sullo stesso HTML archiviato →
**7 difetti, exit 1**. Audit precedente sullo stesso HTML → zero scostamenti, exit 0.
Dopo la correzione, sullo stesso insieme di schede rigenerate → **0 difetti**.
[19] resta classificato **misto**, non viene rinominato indipendente per intero: per le
percentuali continua a condividere il formatter con la produzione.

## 3. Precisione Monte Carlo: corretta oggi, falsa con altri campioni

**Dati reali:** tutte le 132 righe di simulazione ordinaria e le 7.296 condizionate hanno
`n_sims=10.000`. Il vecchio tooltip era quindi corretto su questo snapshot.

**Difetto latente riprodotto su dati sintetici:** con `n_sims=1.000`, il vero template
continuava a dire **10.000 simulazioni / errore standard massimo 0,5 punti percentuali**.
La CLI consente numerosità diverse: non è lecito ignorare il metadato.

Ora il tooltip usa `n_sims` e il limite **50/√N punti percentuali**, arrotondato **verso
l'alto** a un decimale (1.000 → 1,6 pp; 9.000 → 0,6 pp, non 0,5; 10.000 → 0,5 pp).
Metadato assente o non valido → «numerosità non dichiarata, precisione non quantificabile»,
mai un default inventato. La nota distingue questo rumore MC dall'**incertezza del modello**,
che non è quantificata da quel numero. Probabilità, loro arrotondamenti e simulazioni non
sono stati cambiati. L'oracolo controlla il limite numerico, non ricopia il formatter.

## 4. Limiti esplicitati, senza alterare numeri o regole esistenti

- **Permanenza:** conta le distinte fino alla gara, comprese quelle in programma, non solo
  partite già dirette. **10 celle** includono almeno un'altra gara non finita prima della
  gara della scheda. Ora la nota lo dice; rendimento e gol/gara restano sulle sole finite.
  Non viene attribuita una carriera completa a un archivio parziale.
- **Classifica virtuale:** applica i punti a entrambe le squadre, mantiene ferme altre gare
  e differenza reti. In **35 scenari su 378, su 34 celle**, altre squadre hanno pari punti
  e differenza reti: il codice riporta la **prima posizione del gruppo**, senza ulteriori
  spareggi. Questo limite è ora dichiarato, non trasformato in una previsione esatta della
  futura classifica. Non sono cambiati criteri o numeri virtuali dopo averli osservati.
- **Precedenti allenatori:** zero righe su 126 celle nel campione disponibile;
  `match_storico.parquet` è assente e le distinte raccolte coprono la sola stagione corrente.
  Non si inventano incroci né si attribuiscono al coach i precedenti del club. Lo storico
  Understat dei punti 1–3 non contiene le distinte degli allenatori: non colma quel vuoto.
- **Età titolari:** 18 valori disponibili, 108 assenze dichiarate; nessun numero ricostruito
  arbitrariamente. Identità/età/nazionalità degli allenatori e tutte le percentuali sono
  state ricontrollate sui dati già salvati, non sul vivo delle fonti.

## 5. Prova di impatto prima della build completa

Rigenerato il solo frammento Jinja sulle stesse 63 schede (copie in cache, non `site/`):

| Celle confrontate | Identiche | Corrette |
|---|---:|---:|
| Allenatore | **126** | 0 |
| Posta in gioco | **119** | **7** |
| Età media titolari | **126** | 0 |

Le sette celle cambiate sono esattamente quelle delle due tabelle sopra. Il confronto è
stato ripetuto dopo la **build completa**, con lo stesso esito; anche le **63 tabelle di
probabilità condizionate** restano identiche. I chiarimenti sono nelle note e nei tooltip;
nessun nuovo segnale di clima, nessuna modifica a previsioni, probabilità o dati.
Riepilogo macchina: [`_audit_panchina_2026-10-12.json`](_audit_panchina_2026-10-12.json).

**Test:** 29 nuovi casi su parità di punti, soglia diretta/spareggio per le sette leghe,
classifica non monotona, MC con N diverso o mancante, limite SE, testo delle cautele e
kill-test dell'audit. Prima del fix: 25 falliti / 4 passati; dopo: **29 passati**.
Con i test panchina/notizie preesistenti: **102 passati**.

## 6. Gate e stato

**Tutti eseguiti dopo l'ultima modifica al codice:**

- **`pytest`: 772 passati**; `ruff check .` pulito.
- **Prova negativa di `verify_site` sull'intero sito precedente:** exit 1, **14 segnalazioni
  sulle stesse 7 celle** (7 semantiche + 7 del confronto testuale). Non sono 14 difetti distinti.
- **`fda build`: 498 schede / 2.364 fixture / 7.594 giocatori**.
- **`verify_site`: 239.769 controlli, 0 problemi**; 54 oracoli, 31 I / 19 M / 4 S.
- **`audit_panchina`: 0 difetti** sull'intero sito rigenerato.
- **Parità: 63 schede, nessuna differenza**; resa a 375 px: **28.657 misure, 0 problemi**.
- CI del codice **`9c038ae`** verde: run
  [38283708700](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38283708700) e
  [38283703373](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38283703373).
- Nessun Parquet modificato, inclusi `season_sim.parquet` e `season_sim_cond.parquet`.

**Prima sezione verificata.** PR #108 sempre in bozza, nessun merge: correzioni sul branch,
non ancora pubblicate su `main`. I limiti dichiarati non diventano accuratezza garantita.

## Prossimo passo

Passare a **Mercato**, seconda delle sei sezioni. Restano dopo Mercato:
Vita del club, Previsione ensemble, Precedenti, Verifica approfondita. StatsBomb e decisione
sul clima restano aperti; nessuna decisione presa al posto dell'utente.
