# Handoff e coda «fonti nuove» — 2026-10-09

> Scopo: permettere a una **sessione nuova** di ripartire senza rifare misure. Porta d'ingresso
> del progetto: [`BRIEFING_NUOVA_SESSIONE.md`](BRIEFING_NUOVA_SESSIONE.md); stato: cima di
> [`STATO.md`](STATO.md); regole: [`00_regole_di_lavoro.md`](00_regole_di_lavoro.md).

## 1. Che cosa è stato fatto in questo giro (PR #97)

Revisione completa della card **«Le due squadre»** delle schede partita, in quattro passaggi,
tutti documentati in [`64_le_due_squadre_2026-10-09.md`](64_le_due_squadre_2026-10-09.md):

| § | Contenuto | Misura chiave |
|---|---|---|
| §2 | Primo giro: 9 difetti (alias Understat, fonti miste, rapporti di lega assenti, verdetto xPTS a soglia fissa, forma senza verso dei gol, PPDA con aggettivo ambiguo…) | 446 schede |
| §5-§7 | Finestra **alla vigilia**: i numeri di stagione non includono più gare successive alla partita descritta | 750/750 riquadri contaminati, Δ xG mediana 0,23 |
| §8 | Infermeria: totale = somma delle righe; badge «x su y con minuti»; pillola «ruolo n.d.» | 101/118 pannelli sbagliati · 197/507 righe senza ruolo |
| §9 | **Pressing in tutte e 7 le leghe** con l'indice FotMob; PPDA Understat nel ⓘ | caselle piene 604 → **760/892**, NED1 e POR1 da 0% a 88% |

Gate alla chiusura: pytest **556 passed** · `ruff` pulito · build **446/2.364/7.498** ·
`verify_site` **0 problemi · 187.107 controlli** · `parita_schede` nessuna differenza ·
`resa_375` **26.565 · 0**. Invariante **[44]** (`check_due_squadre` in `scripts/verify_site.py`)
copre struttura, fonti, numeri ricalcolati, finestra, pressing e infermeria su **ogni** scheda.

## 2. Coda operativa, in ordine di valore misurato

### B — forza dell'avversario nella forma (nessuna fonte nuova)

**Completata sul branch della PR #98:** [docs/66](66_la_forma_dice_contro_chi_2026-10-09.md).
L'Elo si ricostruisce da `history.parquet` **alla vigilia**, non da `predictions.parquet`
(rating odierno). Le misure esplorative sono state consegnate dall'utente e non ripetute;
serie, ranghi, media, soglia sd/√n e gate sono implementati. Le righe sotto sono il piano originario.

La striscia «V V V V P» non dice **contro chi**: quattro vittorie con le ultime quattro non
valgono quanto con le prime. **L'Elo esiste già**: `predictions.parquet` ha `elo_home`/`elo_away`
per **133 squadre** (modello interno, usato dall'ensemble `dc_elo_tilt` in
`src/fda/models/predict.py`). Prima di aggiungere qualunque fonte esterna, usare questo.

Passi: esporre l'Elo per squadra in `analysis.py` → qualificare ogni pallino della forma col
livello dell'avversario (ⓘ con il valore) → opzionale: «forza media degli avversari affrontati»
accanto al campione xG. Misurare prima **quanta** varianza di risultato spiega l'Elo
dell'avversario nel corpus attuale: se è poca, pubblicare solo il ⓘ e non un indicatore nuovo.

### C — Clubelo come controllo indipendente (fonte già configurata, mai usata)

> **Bloccata in questo sandbox (verificato il 10/10):** `api.clubelo.com` non è fra gli host
> raggiungibili (solo github.com, codeload, api.github.com, registry.npmjs.org, pypi.org,
> files.pythonhosted.org). Serve una sessione con accesso alla fonte; la configurazione c'è già.

`config/sources.yaml` ha la sezione `clubelo` e ogni lega ha `clubelo_country` in
`config/leagues.yaml`, ma **nessuna riga di codice la usa**. Un CSV al giorno, tutte e 7 le
leghe. Valore reale: confrontare il **nostro** Elo con uno esterno e dichiarare lo scarto
(controllo di qualità del modello), non sostituirlo. Priorità **dopo** B: se B mostra che l'Elo
interno è già informativo, C resta un controllo, non un contenuto.

### D — quote di chiusura per misurare il modello (fonte già configurata)

**Misurata offline sul branch della PR #98:**
[docs/67](67_modello_contro_mercato_offline_2026-10-09.md),
`python scripts/benchmark_quote.py --offline`. Quote già in `history.parquet`, ma complete
solo in NED1/POR1: **1.071 gare appaiate**, ΔRPS **+0,008807**, ΔBrier **+0,019602**
(modello grezzo − mercato, entrambi a favore del mercato; IC in docs/67). Non «sette leghe
verificate»; la fonte esatta e il ripiego delle quote non sono tracciati per riga.
Zero richieste sportive, nessuna modifica al modello o al workflow mensile. Il piano originario segue.

> **Aggiornamento del 10/10:** la parte **online** (footballdata/Pinnacle su tutte e 7 le leghe)
> resta bloccata in questo sandbox per gli stessi host di C. In più, `docs/69` §4 riconcilia il
> ΔRPS di docs/67 (+0,008807, probabilità grezze) con quello di `docs/_audit_modelli.json`
> (+0,008527, calibrate): stesso campione, stesso mercato, differenza spiegata dalla calibrazione.

`footballdata` è in `config/sources.yaml` e ogni lega ha il suo `footballdata_code`
(I1, E0, SP1, D1, F1, N1, P1: **tutte e 7**). Oggi il modello si valuta solo contro se stesso
(`backtest.parquet`, `calibration.parquet`, `accuratezza.html`). Confrontare RPS/Brier con le
quote di chiusura è il test più severo e renderebbe credibile «Previsione del modello ensemble».
Attenzione alla linea editoriale: le quote **non** sono un obiettivo editoriale (vedi §0 del
briefing), quindi usarle come **metro di misura**, non come contenuto.

### E — ritocchi dentro la card, a costo zero

1. confronto incrociato «xG creati di A contro xG concessi di B» (oggi lo fa il lettore a mente);
2. trend ultime 3-5 gare contro la media di stagione;
3. agganciare l'assente alla notizia che ne parla (`news.parquet`, **3.873 righe**) per sostituire
   i rientri stimati con quelli annunciati — nella card restano **202 assenti senza numeri**.

### B2 — «forza avv.» storica (rimedio misurato il 10/10, nessuna fonte nuova)

L'anacronismo aperto di `docs/60` §5 ha ora una soluzione misurata: su **4.992** righe della
tabella «Come arrivano», **4.979 (99,7%)** hanno già il rango Elo storico alla vigilia grazie alla
serie di B. Piano, misure e costi in [`docs/69`](69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md) §2.

### G — decisione sui tre tilt (`absences_tilt`, `rest_tilt`, `market_value_tilt`)

Aperta da `docs/57` §7.2 e `docs/48` §4.1.1: esistono in `models/predict.py`, li chiama solo
`scripts/audit_modelli.py`. Misure rigenerate il 10/10: il riposo **peggiora** ancora
(ΔRPS +0,0000787, IC [+0,0000154; +0,000141]); valore dei titolari su **341** gare, solo k=0,03
distinguibile da zero; assenze su **98** gare con miglioramento monotono in k (campione troppo
piccolo). Resta falso il commento `predict.py:41` («k calibrato su 5.7k gare»). Protocollo
preregistrato e strade A/B/C in [`docs/69`](69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md) §1.

### F — sezioni ancora da revisionare (metodo: misura prima/dopo → correzione → invariante)

«Panchina e posta in gioco», «Mercato: arrivi e partenze», «Vita del club», «Previsione del
modello ensemble», «Verifica approfondita», «Confronto di stagione», «Clima del club».

## 3. Residui noti, fuori perimetro di questo giro

- `match_info.league_id` vale 937276 su tutte le gare NED1 (id di fase): la lega si prende da
  `fixtures`, mai da `match_info`.
- Il campione xG può risultare una gara avanti rispetto alla classifica (Cagliari, Lecce).
- Il PPDA **di stagione** di Understat è una media di PPDA di gara (il nuovo indice FotMob usa
  invece il rapporto di somme, corretto).
- Collisione di numerazione fra i due `docs/58`.

## 4. Comandi utili (ambiente già pronto con `pip install -e ".[dev]"`)

```bash
.venv/bin/python -m fda.cli build          # ~5m20s, 446 schede
.venv/bin/python scripts/verify_site.py    # ~2m20s, invarianti [0]-[44]
.venv/bin/python scripts/parita_schede.py  # parità fra le schede pre-partita
.venv/bin/python scripts/resa_375.py       # resa su schermo stretto
.venv/bin/python -m pytest -q              # ~1m40s, 556 test
.venv/bin/ruff check .
```

Nessun comando di rete verso le fonti dati: la cache e i Parquet in `data/processed` bastano per
tutte le verifiche. I tetti sono **per run** (FotMob 600, notizie 200) e non c'è tetto giornaliero.

## 5. Prompt pronto per la sessione nuova

> **Prompt aggiornato il 2026-10-10 (usare questo).** Continuiamo il lavoro sul portale: leggi
> `docs/BRIEFING_NUOVA_SESSIONE.md`, la cima di `docs/STATO.md` e
> `docs/69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md`. B e D sono chiuse nella PR #98
> (docs/66, docs/67) e revisionate in modo indipendente (docs/68): numeri confermati, tre lacune
> dei controlli corrette. Parti dalla **voce G** — la decisione sui tre tilt, con la correzione
> del commento falso in `predict.py:41` e la verifica del campione delle assenze (137 → 98) — e
> poi dalla **B2**, «forza avv.» storica (rimedio già misurato: 4.979 righe su 4.992). Metodo del
> progetto: misura prima/dopo → correzione → invariante o test, parità su tutte e 7 le leghe.
> Le voci C e D-online sono bloccate qui: gli host esterni non sono raggiungibili dal sandbox.
> Il merge delle PR lo faccio io.
