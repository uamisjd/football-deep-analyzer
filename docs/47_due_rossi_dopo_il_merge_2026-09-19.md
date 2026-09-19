# 47 — I due rossi dopo il merge: una bomba a orologeria e una scala arrotondata due volte (2026-09-19)

Il merge di #64 (`6adb463`, 22:17:19Z) è andato a buon fine, ma **venti minuti dopo `main` era
rosso e il sito era fermo**. Sono due guasti **indipendenti**, e — questo conta — **nessuno dei
due è stato introdotto da #64**: erano già lì, e si sono visti proprio perché i controlli
automatici funzionano.

Cronologia, con gli orari (UTC):

| Ora | Cosa | Esito |
|---|---|---|
| **18:11:48** | ultimo deploy riuscito | sito aggiornato |
| **20:00:42** | run `daily` di schedulazione (**#118**, `35465437015`) | **fallito** → deploy **saltato** → issue **#65** aperta da sola |
| **22:17:19** | merge di #64 (`6adb463`) | `main` avanti |
| **22:19** | run `tests` su `main` (`35472896106`) | **rosso** — bomba a orologeria |
| **22:19** | run `daily` su push (`35472896089`) | **rosso** — scala della barra |
| **22:34** | push della correzione (`b9ad8ef`) | check `test` **pass** in 1m34s |
| **22:37:53** | merge di #66 (`031644e`) | correzione in `main` |
| **22:37:55** | run `daily` su `main` (**#120**, `35473881781`) | **success** — deploy **22:51:41Z** |
| **22:51:38** | la issue #65 si chiude **da sola** | «Ripristinato» |

Il sito era quindi **fermo dalle 18:11Z**, cioè da **prima** del merge: il deploy mancato delle
20:00 non c'entra con #64. Lo dico perché la tentazione, davanti a un `main` rosso subito dopo un
merge, è di dare la colpa al merge. Qui i numeri dicono altro.

---

## 1. Il test che saltava un'ora al giorno

`tests/test_didascalia_punteggio.py::test_gara_in_corso_non_dice_calcio_d_inizio` costruisce una
gara **in corso** e controlla che la sua didascalia non dica «calcio d'inizio», ma qualcosa tipo
«in corso · 34'». Per farlo spostava il calcio d'inizio a **«adesso meno un'ora»**:

```python
fx.loc[fx.match_id == 5749645, "utc_kickoff"] = now - timedelta(hours=1)
```

Sbagliato di un'ora all'anno… no: **sbagliato un'ora al giorno**. La pagina «Oggi» non ragiona in
UTC: `build_indexes` raggruppa le gare per **data italiana**. Fra le **22:00 e le 23:00 UTC**
(mezzanotte–una in Italia) «adesso meno un'ora» cade sul **giorno prima**, la gara finisce fuori
dalla pagina «Oggi» e `assert card` — «la gara in corso dev'essere in «Oggi»» — fallisce.

Il merge è capitato alle 22:17Z, dentro quella finestra: il test è esploso, e lo avrebbe fatto
**ogni sera** a quell'ora, da quando è stato scritto.

**Correzione:** il calcio d'inizio resta «circa un'ora fa», ma non può precedere la mezzanotte
italiana di oggi:

```python
adesso_roma = datetime.now(UTC).astimezone(ZoneInfo("Europe/Rome"))
mezzanotte_roma = adesso_roma.replace(hour=0, minute=1, second=0, microsecond=0)
fx.loc[fx.match_id == 5749645, "utc_kickoff"] = max(
    now - timedelta(hours=1), mezzanotte_roma.astimezone(UTC)
)
```

Così il test non dipende dall'ora in cui gira, in nessun fuso. **`pytest`: 488 passed.**

> Regola che ne esce: un test che costruisce date «relative a ora» deve usare lo **stesso fuso con
> cui il sito le mostra**, altrimenti è una bomba a orologeria, non un test.

---

## 2. La scala arrotondata due volte (il sito fermo, issue #65)

Il run delle 20:00 si è fermato al passo «Verifica il sito» con **22 problemi** di questo tipo:

```
scala della barra 2,0–3,4 vs 2°–98° percentile 2.05–3.38
```

La barra che dice «dove sta questa gara fra i gol attesi del campionato» ha sotto una scala: a
sinistra il 2° percentile, a destra il 98°. Il controllo **[16]** di `scripts/verify_site.py`
ricalcolava i percentili dalle previsioni e li confrontava con i due numeri stampati, con mezza
cifra di tolleranza:

```python
if abs(pubblicato - percentile) > 0.05:      # prima
    fails.append(...)
```

Il guaio è che i due numeri **non sono la stessa cosa arrotondata una volta**:

1. il generatore (`src/fda/site/analysis.py:964`) passa al template il percentile **già
   arrotondato a due cifre** — `viz = {"lo": round(lo_q, 2), ...}` → `2.05`;
2. il template stampa con **una** cifra, in italiano → **`2,0`**.

Quindi lo scarto legittimo fra «numero stampato» e «percentile grezzo» non è al massimo 0,05 (una
sola cifra di arrotondamento) ma **0,005 + 0,05 = 0,055**: il controllo era **più stretto della
sua stessa tolleranza dichiarata**. E sul confine la virgola mobile dà il colpo di grazia:
`2.05 - 2.0 = 0.05000000000000004`, che è **maggiore** di `0.05`.

Non era un numero sbagliato pubblicato: era **un confronto fra due cose diverse**.

**Correzione:** il confronto si fa sul valore che il template **riceve davvero**, con mezza cifra
di tolleranza e un margine per la virgola mobile:

```python
TOLLERANZA_SCALA = 0.05 + 1e-9

def _scala_ok(pubblicato: float, percentile: float) -> bool:
    """La scala stampata (1 decimale) corrisponde al percentile che il template riceve?"""
    return abs(float(pubblicato) - round(float(percentile), 2)) <= TOLLERANZA_SCALA
```

Con una **prova di morso** (`test_scala_della_barra_tollera_il_doppio_arrotondamento`): passano
`(2,0 / 2,0503)`, `(2,1 / 2,0503)`, `(3,4 / 3,38)`; **non** passano `(2,5 / 2,0503)`,
`(2,0 / 3,1)`, `(3,9 / 3,38)`. Uno scarto vero — una scala che dice 2,5 su un percentile di 2,05 —
resta un problema segnalato: la guardia non è stata addolcita, le è stato spiegato **cosa**
confrontare.

---

## 3. La parte buona: i cani da guardia hanno abbaiato

- L'allerta del `daily` ha funzionato **dal vivo e da sola**: la issue **#65** si è aperta alle
  20:00:43Z, un secondo dopo il fallimento, con data, ora, link al run e la nota che il sito era
  fermo all'ultimo deploy buono. Era la prova che l'interruttore `prova_allerta` (PR #64) doveva
  esercitare: **l'abbiamo avuta gratis, in produzione**, senza simulare nulla.
- Il `verify_site` ha **bloccato il deploy** invece di pubblicare pagine che non sapeva
  giustificare: è esattamente il suo mestiere, e per questo il sito è rimasto fermo quattro ore
  invece di mentire.
- Il workflow `tests` ha preso una bomba a orologeria che dormiva da giorni.

Nessuno dei tre controlli è stato aggirato: in tutti e due i casi è stato **corretto il difetto**
(non ci sono eccezioni, né tolleranze allargate a caso), e in tutti e due i casi la correzione ha
la sua prova al contrario.

---

## 4. Il giro si è chiuso da solo

Alle **22:51:38Z** la issue **#65** è stata **chiusa in automatico** dal passo «Segnala
ripristino», tre secondi prima del deploy (**22:51:41Z**): il sito è tornato a muoversi dopo
**4h40m** di fermo (18:11Z → 22:51Z), e l'intero ciclo — guasto rilevato, issue aperta, correzione,
run verde, issue chiusa — è avvenuto **senza intervento umano**, a parte la diagnosi.

È la conferma che il presidio pensato per il `daily` (PR #63) regge su un guasto vero, non solo in
prova.

---

## 5. Cosa resta aperto

- La prova **volontaria** dell'allerta (`gh workflow run daily.yml --ref main -f
  prova_allerta=true`) resta utile: stavolta il ramo di guasto si è esercitato da sé, ma la prova
  programmata serve a non scoprire un domani che l'interruttore si è rotto.
- Lunedì **21/09, 03:30 UTC**: run del `lab`, con la prima sonda dei fallback
  (`source_probe.parquet`). Il **3/10** il primo `benchmark.yml`.
