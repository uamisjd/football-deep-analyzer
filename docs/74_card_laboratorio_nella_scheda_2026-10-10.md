# 74 — Il card «laboratorio» nell'area previsione della scheda (2026-10-10)

**Richiesta dell'utente** (10/10, dopo la revisione di [`docs/73`](73_revisione_sezione_laboratorio_previsione_2026-10-10.md)):
«vai» — aprire la voce con il design delle otto condizioni. È la stessa richiesta che aveva
generato la revisione: una casa visibile, sulla scheda, per i tre tilt e per «le altre idee e
calcoli», «fatta molto bene».

**Stato: fatto.** Il card esce su tutte le **89** schede pre-partita, sotto la previsione
salvata; la previsione salvata non cambia (§6); una nuova invariante **[46]** ricalcola λ e 1X2
del what-if senza importare le formule del modello (§5).

## 1. Dove sta e che cosa dice

Un card a tutta larghezza `id="laboratorio"`, **dopo** `id="scomposizione"` («Come nasce questa
probabilità») e **prima** di `id="fascia-storica"`: dentro l'area previsione, sotto la previsione
salvata, mai sopra (condizione 1 di `docs/73` §5).

Titolo: **«Il laboratorio — idee misurate, _non usate_ in questa previsione»**, con ⓘ che
ripete il patto: le tre idee esistono nel codice e sono state misurate, nessuna è applicata, la
previsione in cima alla scheda non le contiene.

Una riga per idea, sei colonne:

| Colonna | Contenuto |
|---|---|
| **Idea** | nome + ⓘ con la formula applicata e le sue costanti |
| **Dato usato** | l'input di casa e di trasferta, oppure «dato non disponibile» con la ragione |
| **Se fosse applicata** | λ della partita e 1X2 calcolati con l'idea (stessa griglia della previsione) |
| **Spostamento** | Δλ per squadra e Δ sull'1X2 in punti percentuali, oppure «non sposta nulla» |
| **Misurato sull'archivio** | campione, effetto misurato con intervallo di confidenza, documento di provenienza |
| **Verdetto** | una riga + ⓘ con la ragione per esteso |

In chiusura: le λ di partenza (quelle della previsione salvata), quante idee sposterebbero
qualcosa su questa partita, e il richiamo a `verify_site` che ricontrolla le formule.

Le misure d'archivio **non sono ricalcolate a ogni build**: richiedono il backtest completo e
sono i numeri registrati in `docs/69` §1 e `docs/71` §3, citati con campione e provenienza.
Vivono in `src/fda/site/laboratorio.py` (`IDEE`), una per idea, con la stessa disciplina del
commento corretto in `predict.py` (voce G): se un candidato venisse promosso, cambierebbero
insieme a `MODEL_VERSION` e alla calibrazione.

## 2. Come è calcolato il what-if

Partenza: **le λ e il ρ della previsione salvata** (`lambda_home`, `lambda_away`, `dc_rho` di
`predictions.parquet`). Su quelle si applica la formula dell'idea e si ricalcola l'1X2 con
`dc_grid.tau_grid` — **la stessa griglia** con il τ di Dixon-Coles usata dal modello, dalla
calibrazione e dall'audit (`scripts/audit_modelli.py`): nessuna seconda implementazione, quindi
nessuna possibilità che il card racconti una superficie di probabilità diversa da quella del sito.

Le tre formule sono **quelle dichiarate in `predict.py`** (`market_value_tilt`,
`absences_tilt`, `rest_tilt`): il card le usa, non le riscrive. È la conseguenza pratica della
decisione **C** (`docs/71` §4): le funzioni passano da «codice morto» a «input della card»,
senza entrare in `predict_matches()`.

Gli input per partita, riletti a ogni build:

| Idea | Input | Fonte |
|---|---|---|
| valore dei titolari | `home/away_starters_value_eur` | `match_info` |
| indisponibili | `contrib_lost_p90` (xG+xA/90 persi) | `MatchAnalysis.absences_weight` |
| giorni di riposo | giorni dall'ultima gara, campionato **+ coppe** | `MatchAnalysis.rest_days` |

Due distinguo, perché «zero» e «mancante» non sono la stessa cosa:

* **valore**: è un rapporto, quindi serve **entrambe** le squadre; se una delle due manca la
  riga esce «dato non disponibile» (è il caso misurato di NED1 e POR1 in `docs/73` §2);
* **indisponibili**: nessun assente **con la distinta pubblicata** è uno zero misurato (`0,0`),
  mentre senza distinta è un dato mancante e resta «dato non disponibile».

> **Aggiornamento del 2026-10-10 (dopo la revisione §10).** Il what-if è ora calcolato con il
> **k che la misura sostiene** (o con il tetto della griglia preregistrata), non con la costante
> che il codice si porta dietro: quella è pubblicata sotto, per confronto. La §10 racconta la
> revisione, le misure che l'hanno imposta e i numeri corretti.

## 3. Che cosa sposta davvero, sulle 89 schede di oggi

Misurato sulle pagine generate da questo build (89 schede pre-partita, 7 leghe):

| Idea (con il k del §10) | dato mancante | sposta λ > 0,005 | Δλ mediana | Δλ p90 | Δλ max | Δ1X2 mediana · max |
|---|---:|---:|---:|---:|---:|---|
| valore titolari, k = 0,03 | **36/89** | 51/53 | 0,040 | 0,070 | 0,080 | 2 · 3 pp |
| indisponibili, k = 0,20 | 0/89 | 85/89 | 0,040 | 0,100 | 0,200 | 2 · 8 pp |
| riposo (fattori fissi) | 0/89 | **0/89** | 0,000 | 0,000 | 0,000 | 0 · 0 pp |

Sotto, per confronto, lo stesso calcolo con la **costante nel codice** (k = 0,12 e 0,30):
valore titolari Δλ mediana **0,140** (max 0,310) e Δ1X2 mediana **6 pp, max 13**;
indisponibili Δλ 0,060 (max 0,270) e Δ1X2 mediana 3 pp, max 11. È lo stesso what-if, quattro
volte più grande, e non è una stima di ciò che entrerebbe.

Lettura, senza girarci intorno:

* il **valore dei titolari**, al k che la misura sostiene, sposta **2 punti sull'1X2** (massimo
  3): è l'idea con il campione più grande e l'effetto più piccolo, e il confronto con il k del
  codice (6 pp, fino a 13) misura quanto quella costante sia lontana da ciò che è sostenuto;
* gli **indisponibili** spostano poco (mediana 3 pp) e il loro campione è sotto la soglia
  minima del protocollo preregistrato (98 gare contro 300): «non testabile», non «neutro»;
* il **riposo** in questa finestra **non sposta nulla**: è la sosta di ottobre e tutte le
  squadre stanno sopra i 7 giorni, dove il fattore è 1,02 per tutti e il totale dei gol attesi è
  preservato per costruzione. La riga esce lo stesso, con «non sposta nulla»: è la misura della
  settimana, non una riga vuota da nascondere. Nelle settimane congestionate si vedrebbe
  (backtest: 1.999/2.071 previsioni con fattore 1,02).

Il dato mancante sul valore è **36/89**, più dei 13/65 stimati in `docs/73` §2: la misura di
allora era sulle 65 gare più vicine, mentre la finestra di 30 giorni del build ne contiene 89 e
il valore dei titolari arriva con le distinte, cioè più la gara è lontana più manca. Il numero
della pagina non è una stima: [46] lo ricalcola da `match_info` riga per riga.

## 4. Peso e parità

Peso mediano della scheda **131 KB** (min 112, max 143) contro il tetto di 900 KB
(`MAX_PAGE_KB`): il card pesa ~4 KB di HTML. La **parità fra schede** resta perfetta: 89 schede,
**25 id identici**, indice uguale in tutte, nessuna differenza di struttura o di quantità.

## 5. Invariante [46]: il ricalcolo indipendente

`check_laboratorio` in `scripts/verify_site.py`, registrata nel `main` accanto a [44] e [45].
Per ogni pagina con il card:

1. legge la **previsione salvata** da `predictions.parquet` (ultima riga per partita) e
   confronta λ e 1X2 di partenza del card con essa;
2. ricalcola gli **input**: giorni di riposo dall'oracolo del calendario (campionato + coppe, lo
   stesso principio di `rest_days`, ma riletto qui), valore dei titolari da `match_info`;
   per gli indisponibili usa il lettore condiviso `MatchAnalysis.absences_weight`, perché è la
   somma stabilizzata di una colonna che [44] verifica già riga per riga — qui si controlla che
   il card **la usi**, non si rifà la stabilizzazione (è dichiarato nella docstring);
3. **riscrive le tre formule** (`_lab_mercato`, `_lab_assenze`, `_lab_riposo`) dalle regole
   pubblicate, senza importare `predict.py`, e ricalcola λ e 1X2 con la griglia condivisa;
4. confronta con gli attributi `data-*` della riga, che portano gli stessi numeri stampati con
   la precisione con cui escono in pagina (λ a due decimali, 1X2 a interi con il metodo del
   resto massimo): tolleranza 0,005 sui gol attesi, uguaglianza sugli interi dell'1X2.

Se un input non torna, λ e 1X2 non vengono giudicati: il fallimento è segnalato una volta, sulla
causa, invece di propagarsi in tre messaggi.

**Indipendenza, provata.** Un test (`test_le_formule_dell_oracolo_coincidono_con_quelle_del_modello`)
confronta le tre formule dell'oracolo con quelle di `predict.py` su **69 combinazioni** di input
(3 coppie di λ × 5 rapporti di valore, 6 contributi persi, 9 combinazioni di riposo, più i casi
con dato mancante) e pretende l'uguaglianza a 1e-12: se le due implementazioni divergessero,
[46] segnalerebbe differenze inesistenti. Un secondo test altera una λ nella pagina generata e
verifica che [46] **veda** il falso: l'invariante non è di facciata.

Risultato sul build: **[46] 89 pagine, 267 righe what-if, 1.780 controlli, zero problemi**.

## 6. La previsione salvata non cambia

Il card **legge** la previsione e non la scrive. Tre riscontri indipendenti:

* `predictions.parquet` è **identico** dopo la generazione della scheda
  (`test_il_card_non_tocca_la_previsione_salvata`: confronto byte per byte);
* il dizionario della previsione passato al calcolo non viene modificato (confronto con una
  copia profonda);
* λ e 1X2 in cima alla scheda sono quelle della riga salvata: la base del card è confrontata con
  la previsione in [46], passo 1.

Nessuna funzione di `predict.py` è stata toccata, nessuna costante, nessuna λ: le tre funzioni
restano **dichiarate e non cablati** in `predict_matches()`, come deciso con la scelta C.

## 7. Design per il futuro

La riga è generica (idea → what-if → misura → verdetto): una quarta idea entra aggiungendo un
elemento a `IDEE` con la sua formula e la sua misura registrata, una riga nel calcolo del
what-if, la sua formula riscritta in [46]. Il card, il template e l'invariante non si ridisegnano.
La lista delle idee è l'unico punto in cui si dichiara «che cosa c'è in laboratorio».

## 8. Gate alla chiusura

| Gate | Esito |
|---|---|
| `pytest -q` | **583 passed** (571 prima + 12 nuovi) |
| `ruff check .` | **pulito** (zero segnalazioni su tutto il repo) |
| build | **470** schede / 2.364 partite / 7.508 giocatori |
| `verify_site` | **210.925 controlli · 0 problemi** (baseline 208.630; [46] 2.206) |
| `parita_schede` | **89 schede · 25 id identici · nessuna differenza** |
| `resa_375` | **27.675 misure · 0 problemi a 375 px** |

## 10. Revisione del pomeriggio (2026-10-10): tre domande, tre risposte misurate

Dopo la chiusura della prima versione, tre domande: «funziona? serve? riesce a rendere la
lettura della partita più precisa?». Verificate, non discusse.

**Funziona?** Sì, su quattro riscontri indipendenti. [46] ricalcola le 267 righe e un test prova
che **vede** una λ falsa (e, dopo la correzione, anche un confronto falso). `predictions.parquet`
è byte-identico dopo la generazione. **Zero conflitti** con la card «Fattori»: sulle 87 schede
in cui entrambe pubblicano il dato degli indisponibili, il numero è lo stesso (tolleranza 0,005).
Parità e resa a 375 px restano verdi.

**Serve?** Sì — ma la prima versione no, e la revisione l'ha cambiata. Il difetto trovato:

> **R1 — il numero più vistoso veniva da una costante che il card stesso bocciava.** La riga del
> mercato usava k = 0,12 mentre la colonna accanto scrive che la misura sostiene solo k = 0,03.
> Misurato sulle 53 schede con il dato: Δλ mediana **0,138** contro **0,036**; sull'1X2 **6 pp
> contro 1,4** (Genoa–Fiorentina: 5,5 → 1,4). Mostrare l'effetto di un k che la misura non
> distingue dallo zero è l'equivoco che il card nasce per evitare. Lo stesso valeva per le
> assenze: k = 0,30 nel codice contro la griglia preregistrata {0; 0,1; 0,2}.

Correzione: il what-if si calcola con il **k sostenuto** (0,03 per il mercato, l'unico con
intervallo di confidenza fuori dallo zero) o, dove nessun k è sostenuto, con il **tetto della
griglia preregistrata** (0,20 per le assenze). La costante del codice resta pubblicata sotto,
etichettata come tale. [46] verifica **entrambe** le coppie (2.206 controlli).

L'effetto collaterale è misurabile e va a segno anche sul secondo rischio:

| Rischio «secondo pronostico» (schede con Δ1X2 ≥ 5 pp) | prima | dopo |
|---|---:|---:|
| valore titolari | 35/53 | **0/53** |
| indisponibili | 27/89 | **9/89** |
| riposo | 0/89 | 0/89 |

Due rischi minori, **non** corretti perché non sono difetti:

* **R2 — la riga del riposo**: 0/89 oggi, e non è un buco: la sosta dà 7–28 giorni a tutte e due
  le squadre (fattore 1,02 a entrambe, totale preservato). È però intermittente: sulle **325
  gare già giocate di questa stagione il 49,8%** ha fattori di riposo diversi fra le due squadre
  (Δλ mediana 0,012, max 0,042 — sempre sopra la soglia di visibilità). In una settimana normale
  la riga parla.
* **R3 — la visibilità**: il distanziamento dell'1X2 alternativa resta affidato al testo
  (titolo, etichetta, verdetto, ⓘ). Con la correzione del k, i casi in cui l'alternativa è
  davvero lontana da quella pubblicata sono scesi da 62 a 9 su 231 righe.

**Rende la lettura della partita più precisa? No — e non può.** La previsione non cambia per
costruzione (§6): il card aggiunge precisione **sul modello** (quanto peserebbe ogni idea, su
quale campione, con quale verdetto), non sulla partita. Serve a chi vuole sapere che cosa **non**
c'è nel numero in cima alla scheda e quanto costerebbe aggiungerlo; non rende quel numero più
preciso. Chi leggesse l'1X2 alternativa come «la previsione vera» avrebbe un'informazione
peggiore di prima: è il rischio che R1 ha reso trascurabile sul mercato (0/53) e che resta da
tenere d'occhio sulle assenze (9/89).

**Un limite dichiarato**: [46] verifica i numeri ricalcolabili, non le frasi. Campioni,
intervalli e verdetti sono costanti con provenienza; il test
`test_le_misure_d_archivio_sono_quelle_registrate_nei_documenti` li pinna uno per uno sui valori
di `docs/69` §1 e `docs/71` §2-§3, così chi li cambia deve aver rifatto la misura e aggiornato il
documento che la registra.

## 9. Cosa resta aperto

* Le tre misure d'archivio sono **costanti con provenienza**, non ricalcolate: se il backtest
  venisse rifatto con campioni diversi, vanno aggiornate insieme al documento che le registra.
  Un prossimo passo onesto è un test che confronti le costanti con `docs/_audit_modelli.json`
  quando lo snapshot verrà rigenerato.
* La riga del riposo è «non sposta nulla» in questa finestra: vale la pena rileggerla in una
  settimana congestionata, dove il what-if si vedrebbe, e riportare la misura.
* Il card non elenca le idee **scartate prima di essere candidate** (distanza della trasferta,
  età dei titolari, turnover): stanno già dichiarate nella card «Fattori». Se il laboratorio
  cresce, quella lista è il posto dove unificarle.
