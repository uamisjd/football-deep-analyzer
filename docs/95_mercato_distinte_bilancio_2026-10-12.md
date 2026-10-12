# 95 — Mercato: distinte, importi e bilancio verificabile (2026-10-12)

**Perimetro:** seconda delle sei sezioni richieste, dopo Panchina (`docs/94`). Stesso
snapshot CI `514309d`: **63 schede, 126 colonne-squadra**, nessuna nuova raccolta.
Codice precedente `02a242d`. Metodo: misura → correzione → invariante/test.

## 1. La riga «Già in campo» ometteva 61 corrispondenze

`transfer_window` passava all'incrocio con le distinte solo i **quattro arrivi esposti**,
non l'intera finestra. Il limite grafico diventava quindi un limite sul dato.

- Arrivi riconoscibili nei dati, contando tutte le voci della finestra: **96**.
- Arrivi dichiarati dalla card: **35**.
- **61 corrispondenze omesse in 14 colonne**, distribuite su 9 schede.
- Esempi: Venezia **2→6**, Frosinone **4→16**, Excelsior **3→12**, Torino **2→7**.

**Correzione:** prima si incrociano tutti gli arrivi, poi si limita l'esposizione. Il numero
è completo; quattro nomi in apertura, gli altri consultabili nel dettaglio espandibile.
Lo stesso giocatore con due movimenti nella finestra conta una sola volta nella distinta.
Le liste dei movimenti restano limitate a quattro per direzione, con ordine e contenuti
preesistenti: il collegamento alle distinte non ne modifica la selezione.

**Limite:** l'archivio trasferimenti non conserva l'ID del giocatore; il collegamento è per
nome normalizzato, non una ricostruzione certa dell'identità o della carriera. Niente
abbinamenti fuzzy inventati. Sono occorrenze nelle schede, non 96 acquisti distinti globali.

## 2. Prevista o precedente non significa confermata per questa partita

Nelle **15 colonne con arrivi riconosciuti**, la fonte dichiara:

| Tipo grezzo di distinta | Colonne | Significato pubblicato ora |
|---|---:|---|
| `predicted` | 8 | formazione prevista; presenze non confermate |
| `lastStarting11` | 7 | ultima distinta disponibile; non quella di questa gara |
| `confirmed` / `official` | 0 nel campione | distinta ufficiale, quando disponibile |

Prima tutte le righe dicevano «**Già in campo**» e «nella distinta **di questa partita**»,
con «titolare» anche per una previsione. Ora: **«Arrivi riconosciuti»**, provenienza e ruolo
qualificati. Tipo mancante/sconosciuto → «tipo non dichiarato», non una conferma implicita.
Anche una distinta ufficiale non garantisce che un giocatore a disposizione venga impiegato.

## 3. Cifre, gratuiti e prestiti non sono lo stesso tipo di informazione

Sulle 126 colonne, la selezione pubblicata comprende **1.009 arrivi + 1.647 partenze = 2.656
occorrenze di movimento** (le stesse squadre possono ricomparire su più schede):

| Voce della fonte | Occorrenze |
|---|---:|
| Importi numerici | **866** |
| Gratuiti | **459** |
| Prestiti senza importo | **922** |
| Altre voci senza importo dichiarato/riconosciuto | **409** |

Prima le ultime tre categorie erano tutte chiamate «importo non noto». Ora la copertura
è esposta e la somma delle quattro categorie deve coincidere col numero dei movimenti.
Un prestito **non** viene fatto passare per un gratuito: può costare, ma non stimiamo la cifra
se manca. «Gratuito» sostiene lo zero del solo corrispettivo, non assenza di stipendio o
commissioni. Importi e formule restano quelli della fonte, senza conversioni valutarie.

Nei dati grezzi esistono anche **123 righe di prestito con importo numerico**: il testo vecchio
«al netto di prestiti e gratuiti» era fuorviante, perché il calcolo includeva già quei prestiti
con cifra. Ora **47 righe visibili** acquistano l'etichetta di prestito prima assente (con
importo o formula gratuita), senza cambiare il corrispettivo. Non sono 47 nuovi movimenti.

### Bilancio parziale, non bilancio del club

La convenzione resta **saldo = spesa − incasso**, ora dichiarata: positivo indica uscita netta,
negativo entrata netta, sui soli corrispettivi noti. Sono esclusi altri costi e importi ignoti.

- Se un lato ha importi numerici, se ne mostra la **somma parziale**, non il costo totale.
- Senza numeri, solo **tutti gratuiti** o **nessun movimento** sostengono lo zero. Un misto
  di prestiti/ignoti non diventa zero per far tornare un saldo.
- Se un lato non è quantificabile, anche il saldo resta **non quantificabile**.
- Lo **zero contabile** si stampa «0 €», non passa dal formatter dei valori di mercato
  mancanti (che trasformava `0` in «importo non noto»).

Nel campione corretto **24 colonne** hanno saldo non quantificabile; in **14** di esse prima
compariva comunque un saldo numerico (es. Cagliari −13 M€ con spesa senza cifra, Coventry
+133,6 M€ con incasso senza cifra). Le cifre disponibili restano: è l'inferenza sul lato
ignoto a essere rimossa. **7 saldi nulli** sostenuti dai dati sono ora dichiarati come zero.
Questa è una regola prudente di esposizione, non un accertamento contabile sui club.

## 4. Tempo e perimetro della finestra

Prima di deduplicare si escludono i movimenti datati dopo il minimo fra **costruzione della
pagina** e **kickoff**, se noto. Un orologio iniettabile rende i test deterministici: una
ripubblicazione posteriore non può cancellare la voce antecedente al kickoff.

**Impatto reale oggi:** nessun cambio di selezione; l'ultimo movimento è del 10/10 e tutte
le schede misurate sono successive. La barriera copre un difetto latente riprodotto in test.
**Limite:** le date sono quelle dei movimenti fornite dalla fonte, non timestamp di quando
la fonte li ha resi conoscibili. Questo filtro non dimostra un backtest informativo senza
leakage; il prospettico resta separato.

La finestra rimane il gruppo di movimenti concatenati entro 21 giorni, **non il calendario
ufficiale del mercato**. Nel campione la più lunga dura **126 giorni**: tolta la promessa
assoluta che la regola non possa mescolare periodi diversi. Non si cambia la soglia dopo
averne visto i risultati, né si unificano due vere mosse distanti oltre 30 giorni.

## 5. L'audit precedente non misurava questi difetti

[39] del vecchio `verify_site`: **493 controlli, zero difetti**, anche con 61 omissioni e
provenienze non dichiarate. [26] ricalcolava con `transfer_window`, ripetendone il limite.

Il vecchio `audit_mercato.py` era un **diagnostico storico dei duplicati** (`docs/56`), non
un gate: non leggeva le schede, analizzava tutte le fixture non finite, parlava ancora di
«66 schede» e usava 30 ore invece delle 3 del generatore. È sostituito dall'audit corrente,
con `--site`, `--data`, `--json`, conteggi reali e **exit 1** su difetti o assenza di card
misurabili. L'implementazione precedente resta nella storia Git.

Il nuovo `mercato_checks.py` non chiama il generatore: dalla finestra dichiarata rilegge i
movimenti, le formule/cifre (con parser Decimal separato), le somme e le distinte complete.
Controlla il tipo dalla tabella `match_info`, i nomi consultabili, la completezza e il saldo.
[39] usa questi controlli; [26] conserva la riconciliazione, ma limitata alla cella Mercato,
non alle sezioni successive. Classificazione degli oracoli ancora **mista**, senza vantare
indipendenza totale della politica di selezione o una verifica dell'esattezza della fonte.

**Prova prima/dopo:** il nuovo audit rifiuta l'HTML precedente e accetta il frammento corretto.
Le sue 248 segnalazioni iniziali includono obblighi di trasparenza nuovi e controlli multipli
sulla stessa cella: **non sono 248 errori fattuali distinti**. Verifica positiva attuale:
**1.008 controlli, zero difetti** sulle 63 schede: prima sul frammento rigenerato e poi sulla build completa.

## 6. Impatto e invarianti

- **126 elenchi-squadra / 897 righe visibili:** nomi, controparti, date e ordine identici,
  confronto ripetuto e confermato dopo la build completa.
- Conteggi **1.009 / 1.647** invariati; importi individuali invariati. Solo 47 etichette di
  prestito aggiunte nelle righe che ne erano prive.
- Arrivi riconosciuti **35→96**, con la provenienza dichiarata, non un'affermazione che giochino.
- 24 nuovi test: intera finestra vs top-4, ufficiale/prevista/precedente/sconosciuta,
  categorie, prestiti onerosi, saldo nullo, lati ignoti, orologio/cutoff, doppie mosse e
  dettaglio espandibile. Cinque kill-test corrompono count/tipo/nome/importo/copertura;
  l'oracolo deve fallire anche con il generatore reso inutilizzabile.
- Test mirati (nuovi + mercato + verificatori): **71 passati**; Ruff pulito.
- Nessuna modifica ai Parquet, ai modelli o alle altre sezioni della scheda.

## 7. Gate

**Tutti eseguiti dopo l'ultima modifica al codice:**

- **796 test passati**; `ruff check .` pulito.
- Prova negativa sul sito precedente: **exit 1**, 324 segnalazioni fra [26] e [39]. Sono
  controlli sovrapposti e nuove dichiarazioni richieste, non 324 errori distinti.
- **`fda build`: 498 schede / 2.364 fixture / 7.594 giocatori**.
- **`verify_site`: 240.345 controlli, 0 problemi** (54 oracoli: 31 I / 19 M / 4 S).
- **Audit Mercato: 1.008 controlli, 0 difetti**; audit Panchina ancora **0 difetti**.
- **Parità: 63 schede, nessuna differenza**; resa a 375 px: **28.667 misure, 0 problemi**.
- CI del codice **`b77c048`** verde: run
  [38292304131](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38292304131) e
  [38292299551](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38292299551).
- `git diff --exit-code -- data/processed` senza differenze, inclusi i due `season_sim*`.

Misura macchina in [`_audit_mercato_2026-10-12.json`](_audit_mercato_2026-10-12.json).
**Seconda sezione verificata.** PR #108 sempre in bozza, non unita: correzioni sul branch,
non ancora pubblicate su `main`. Nessuna garanzia sull'esattezza o completezza della fonte.

## Prossimo passo

Passare a **Vita del club**; restano dopo: Previsione ensemble, Precedenti,
Verifica approfondita. La scelta sul clima e l'ambito StatsBomb restano decisioni dell'utente.
