# Gli oracoli di `verify_site`: quali controlli ricalcolano davvero (2026-10-11)

Richiesta: classificare i ~46 controlli di `scripts/verify_site.py` in «oracolo indipendente» e
«specchio del generatore», e sistemare gli specchi. È il debito tecnico principale del
verificatore: un controllo che costruisce il valore atteso **chiamando il codice del generatore**
verifica che la pagina renda quel codice, non che il numero sia giusto — e in due casi misurati
oggi quella differenza è stata decisiva.

## §1 — Perché conta (i due casi che l'hanno dimostrato)

1. **[2] con la tolleranza «>3».** Il controllo guardava esattamente la tabella dell'andamento
   1X2 e chiedeva solo che le tre celle sommassero ~100: **153 righe rotte (99/101) su 754** gli
   sono passate sotto il naso, in 103 schede. La regola d'arrotondamento della terna non la
   verificava nessuno (la pagina e il controllo usavano la stessa funzione, `round()`). Le ha
   viste solo [47], aggiunto dopo (`docs/78` §14).
2. **[9] lo diceva di sé.** Il commento nel codice era esplicito: «lo scarto ammesso è zero,
   perché la pagina e il verificatore chiamano la stessa funzione». Vero — ma è la definizione
   di specchio: `pct_triple` che sbagliasse avrebbe prodotto lo stesso errore in pagina e nel
   controllo.

## §2 — Cosa è diventato indipendente (riscritture dalla definizione)

| funzione del generatore | riscrittura in `verify_site` | definizione usata | confronto all'innesto |
|---|---|---|---|
| `fda.models.predict.rps` (libreria `prob_backtest`) | `rps_indip` | `1/(r−1)·Σᵢ(Fᵢ−Oᵢ)²` sulle cumulative | 4.000 terne casuali: identico |
| `fda.models.predict.wilson_interval` | `wilson_indip` | radici di `(p̂−p)² = z²p(1−p)/n` | tutte le coppie k,n ≤ 60: scarto max 4,4e−15 |
| `fda.site.fmt.pct_triple` | `terna_indip` + `terna_valida` | pavimento + resto ai resti più alti / specifica: chiude a 100, ogni valore pavimento o tetto | 40.000 casi (nd 0 e 1): zero divergenze |
| `fda.site.fmt.displayed_sum` | `somma_stampata_indip` | somma delle due cifre **stampate** | 20.000 coppie: zero divergenze |

`terna_valida` è una **specifica**, non una seconda implementazione: accetta qualunque terna
legittima (comprese le parità in cui due implementazioni corrette scelgono diversamente) e
rifiuta tutto il resto. È il tipo di oracolo che non produce falsi positivi e non si autocertifica.

Usi sostituiti: [3] e [8] (RPS), [7] e [15] (Wilson), [9] e [46] (terna), [16] (somma stampata).

**[2] è stato anche rafforzato**: da `abs(somma − 100) > 3` a `somma != 100`, ora che il
generatore chiude esattamente (`pct_triple`).

## §3 — Il registro: 50 controlli, 28 indipendenti · 18 misti · 4 specchi

`ORACOLI` in `verify_site.py` dichiara per ogni controllo da dove viene il valore atteso
(«I» indipendente, «M» misto, «S» specchio) con una nota, e il gate lo stampa a ogni esecuzione:

```
oracoli (50 controlli dichiarati): 28 indipendenti · 18 misti · 4 specchi
```

Un test lo tiene onesto, con **ratchet**: ogni etichetta stampata deve essere dichiarata
(`test_ogni_controllo_dichiara_il_suo_oracolo`), gli specchi possono solo diminuire (`S ≤ 4`),
i misti non crescere (`M ≤ 18`), gli indipendenti non calare (`I ≥ 28`). Un controllo nuovo non
dichiarato non passa; un controllo che peggiora la sua natura nemmeno.

**Gli specchi dichiarati (4)** — restano, con la ragione scritta:

| check | perché resta uno specchio | dove sta il suo oracolo |
|---|---|---|
| [1] matrice dei punteggi | usa `score_matrix`/`grid_1x2` del modello (resta l'identità celle+coda = 100%) | test del modello (`tests/test_models.py`) |
| [9] distribuzione dei gol | usa `goals_view` del modello (la terna dei passi è ora su specifica) | `tests/test_models.py`, `tests/test_advanced.py` |
| [10] scomposizione della probabilità | usa `probability_steps` del generatore | `tests/test_advanced.py` |
| [20] card notizie | la selezione è `team_news` del generatore | `tests/test_panchina_notizie.py` |

**I misti (18)**: [3] [7] [8] [8b] [12] [15] [16] [17] [19] [21] [26] [39] [41] [42] [43] [44]
[45] [46]. In tutti, la parte numerica è ricalcolata dal verificatore e una parte (il campione,
la formattazione, la griglia del modello, la cronologia Elo) viene dal generatore: la nota nel
registro dice quale. Ridurli è lavoro futuro, non un difetto nascosto.

## §4 — Controlli positivi (mutazione della pagina pubblicata, non del codice)

Sette difetti iniettati nell'HTML pubblicato (su una copia ridotta del sito, 2 schede +
Accuratezza + Proiezioni: `check_numbers` + `check_laboratorio` + `check_terne_1x2`, ~9 s per
giro). Tutti e sette intercettati:

| # | mutazione | messaggio del gate |
|---|---|---|
| C1 | riga dell'andamento 51+24+26 | `in-play 0' = 51+24+26` |
| C2 | «2,86 gol attesi totali» → 2,96 | `gol attesi 2,96 vs somma delle λ stampate 2,86` |
| C3 | RPS pagina 0,2010 → 0,2510 | `RPS pagina 0.251 vs ricalcolato 0.2010` |
| C4 | intervallo di Wilson 76,5–87,3 → 76,5–96,9 | `intervallo pubblicato 76.5–96.9% vs ricalcolato 76.5–87.3%` |
| C5 | terna di un passo a un decimale | `pubblica [67.0, 20.3, 12.6] invece di una terna che chiude a 100` |
| C6 | terna della tabella 27/30/43 → 27/30/44 | `terna 1X2 in tabella somma 101` |
| C7 | 1X2 del laboratorio 68/20/12 → 69/20/12 | `non è un arrotondamento legittimo` |

C3, C4, C5 sono la prova che le riscritture del §2 sono oracoli veri: prima di oggi, mutare il
numero pubblicato non avrebbe fatto fallire nulla (il controllo ricalcolava con la stessa
funzione che aveva prodotto la pagina).

## §5 — La lezione: anche gli strumenti sbagliano

Cercando una pagina con la tabella dell'andamento, uno script ad-hoc di verifica ha segnalato
`<1` crudo nell'HTML della matrice dei risultati esatti («un difetto di produzione»). **Era
falso**: il sito scrive `&lt;1` (12 occorrenze, lette correttamente da un parser HTML) e zero
`<` crudi. Il colpevole era lo script: `re.sub(r"<[^>]+>", "", html)` **non** è un taglio di tag
sicuro quando un attributo contiene un `>` (qui il `title="…"` contiene `·` e parentesi, e in
altri punti dei veri `<span>`), quindi il testo estratto era spazzatura. Da qui due regole già
vive nel progetto, ora scritte: (a) gli strumenti di verifica leggono la **pagina resa** con le
regex ancorate ai marcatori (`CARD`/`ROW`/`TD` di `audit_panchina`, `PANCHINA_CARD`/`PANCHINA_TD`
di `verify_site`), non con un taglio generico; (b) un difetto si dichiara solo dopo averlo
riprodotto con uno strumento affidabile.

## §6 — La riga d'uscita del gate

`verify_site` stampa ora, prima dell'esito, il censimento:

```
[47] terne 1/X/2 pubblicate: 1642 · tutte sommano 100

oracoli (50 controlli dichiarati): 28 indipendenti · 18 misti · 4 specchi — l'oracolo dei modelli
sono i loro test (tests/test_models.py, test_season_sim.py, test_advanced.py)
nessun problema · 235.804 controlli numerici superati
```
