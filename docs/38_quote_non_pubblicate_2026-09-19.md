# 38 — P2.6 applicata: le quote di mercato non si pubblicano (decisione, 19/09/2026)

> Sesto intervento della coda **P2** di `docs/28` §3, dopo P2.1 (`docs/33`), P2.4 (`docs/34`),
> P2.2 (`docs/35`), P2.3 (`docs/36`) e P2.5 (`docs/37`). Sessione `arena/01a0b61a`, branch
> `arena/01a0b61a-football-analyzer`, base `6abf7f5`. P2.6 non era un difetto da riparare ma **una
> voce da decidere**: «le quote dei bookmaker non ci sono».

---

## 1. Il difetto vero: una promessa che nessuno manteneva

Nelle pagine non c'era nessuna quota — quello era già verificato. Il problema era l'opposto: il sito
**prometteva** una cosa che non esisteva.

- `info.html` elencava fra le fonti gratuite: *«**The Odds API** — quote opzionali, solo se
  `ODDS_API_KEY` configurata (non prioritarie, l'utente non le richiede)»*;
- il README diceva, alla terza riga e nella parte sui secret, che per la sezione quote bastava
  impostare `ODDS_API_KEY`;
- `config/sources.yaml` aveva un blocco `oddsapi`, `.github/workflows/daily.yml` passava
  `ODDS_API_KEY` all'ambiente del run e lo schema dello store dichiarava una tabella
  `odds_snapshots`;
- `docs/03` §4 si intitolava *«Sezione quote / valore: sì»* e descriveva quote consenso,
  probabilità implicite senza margine (metodo Shin) e confronto col modello.

Nel codice, però, **non esisteva nulla di tutto questo**: nessun modulo in `src/fda/sources/`, nessun
fetcher, nessuna riga che leggesse o scrivesse una quota, nessuna pagina che la stampasse. Il lettore
non poteva accorgersene: una fonte in più nell'elenco sembra un dato in più, non un debito.

## 2. La decisione (e perché)

**Le quote dei bookmaker non si pubblicano.** Motivazioni, in ordine di peso:

1. **Il taglio editoriale.** Il sito pubblica la **propria** probabilità e la misura da sola (pagina
   Accuratezza). Mettere accanto il prezzo dei bookmaker sposta il giudizio del lettore dal modello
   al mercato, che è l'opposto del progetto — nato per dire «quanto vale questa previsione», non per
   dire «cosa dicono i bookmaker».
2. **Il confronto col mercato c'è già, dove serve.** `scripts/benchmark_quote.py` confronta le
   previsioni fuori campione con le **quote di chiusura storiche** di football-data.co.uk (mirror,
   colonne `PSCH`/`PSCD`/`PSCA`, lette da `src/fda/sources/history.py`). È una misura del modello,
   non un contenuto per il lettore: resta **offline**.
3. **Costo e superficie.** Nessun secret da gestire, nessun tetto di crediti mensili, nessuna fonte
   in più che può rompersi: il sito continua a girare a costo zero e senza chiavi (regola E di
   `docs/03`).

## 3. Che cosa è stato tolto

| dove | che cosa | adesso |
|---|---|---|
| `src/fda/site/templates/info.html` | la voce «The Odds API» nell'elenco delle fonti | voce tolta + **dichiarazione al lettore** |
| `README.md` (3ª riga e «Mettere i secret») | il passo «imposta `ODDS_API_KEY`» | niente secret |
| `config/sources.yaml` | il blocco `oddsapi` | rimosso |
| `.github/workflows/daily.yml` | `ODDS_API_KEY` fra le variabili del run | rimosso |
| `src/fda/store.py` | la tabella `odds_snapshots` nello schema | rimossa |
| `docs/03` §4 | «Sezione quote / valore: sì» | riscritto: **no**, con il perché |
| `docs/02` §9, `docs/05` M4, `BRIEFING`, `STATO` | le tracce della stessa promessa | allineate alla decisione |

Sulla pagina Info il lettore legge ora, subito sotto le fonti:

> **Quote di mercato: non pubblicate.** Il sito non mostra le quote dei bookmaker: pubblica la
> probabilità del modello e la misura da sola, nella pagina Accuratezza. Le quote di chiusura
> storiche servono solo *fuori* dal sito, come metro di confronto esterno per sapere quanto il modello
> dista dal mercato: non entrano nella previsione e non compaiono in nessuna pagina.

Una decisione scritta è più utile di un silenzio: chi arriva cercando i pronostici dei bookmaker lo
scopre in una riga, invece di dedurlo da un elenco che non li nomina.

## 4. L'invariante [35]: la decisione non può regredire

Nuovo controllo in `scripts/verify_site.py` (funzione `check_fonti`, chiamata da `main()` dopo
`check_stime`), perché una cosa tolta a mano torna indietro da sola alla prima distrazione:

1. **Elenco pubblicato ↔ moduli veri, nei due versi.** Le fonti lette in `info.html` devono
   corrispondere esattamente ai moduli di `src/fda/sources/`: una fonte dichiarata senza modulo è
   una promessa fantasma; un modulo senza fonte dichiarata è un dato raccolto senza dirlo al lettore.
2. **La dichiarazione esatta** `«Quote di mercato: non pubblicate.»` deve essere presente.
3. **Nessuna pagina promette quote.** Su **tutte** le pagine pubblicate (4.125) si cerca una lista di
   formule vietate (`The Odds API`, `ODDS_API_KEY`, `probabilità implicite`, `quote consenso`, …).

**Prova di morso** (fatta *prima* di correggere il prodotto, sulla build ferma a `6abf7f5`): la riga
è uscita con **exit 1** e **4 problemi** — la fonte senza modulo, la dichiarazione mancante e due
formule di quote vietate in pagina. Dopo l'intervento, sulla build corrente:

```
[35] fonti dichiarate nella pagina «Info»: 7 voci · 6 moduli · 4125 pagine senza promesse di quote
```

Un test in `tests/test_site.py`
(`test_p26_fonti_dichiarate_e_quote_di_mercato_fuori_dal_sito`) copre gli stessi tre lati su una build
piccola, così il difetto si vede anche in pochi secondi e non solo con lo scan completo.

## 5. Che cosa **non** è cambiato

- Le quote di chiusura storiche restano nei Parquet (`history.parquet`, colonne `odds_home`/`draw`/
  `away`) e restano il metro di confronto del backtest: `scripts/benchmark_quote.py`,
  `scripts/mercati_monitor.py`. Non entrano nel modello e non compaiono in pagina.
- `predictions.parquet` non ha mai contenuto quote: le colonne sono `p_home`/`p_draw`/`p_away` e i
  derivati.
- Il campo `fair_home`/`fair_draw`/`fair_away` delle previsioni **non** è una quota di mercato: è la
  probabilità del modello convertita in numero decimale (1/p), un modo di scrivere la stessa cosa. La
  pagina continua a non stamparlo come «quota».

## 6. Verifiche

| controllo | esito |
|---|---|
| `fda build` | 369 partite / 2.364 fixtures / 7.480 giocatori (invariato) |
| `scripts/verify_site.py` | **0 problemi · 133.921 controlli** (28.883 dei quali della riga [35]) |
| `pytest` | **450** passati (449 + il test nuovo) |
| `ruff check` | pulito |
| `scripts/parita_schede.py` | exit 0 — 60/60 schede, 23 sezioni, indice 12 voci, visibile min 17.604 · mediana 19.262 |
| `scripts/audit_match_sections.py` | exit 0 — nessuna sezione persa |
| prova di morso di [35] | exit 1 con 4 problemi sulla build pre-fix |

Nessuna pagina della scheda partita è cambiata: l'intervento è su Info, sulla configurazione e sui
documenti, quindi la parità fra le schede è per costruzione la stessa di `docs/37`.

## 7. Cosa resta

**P2.8** — la resa in browser a 375 px (badge della forma, micro-visivi di P2.3, indice a 12 voci,
tendina della verifica). È l'ultima voce aperta della coda P2 e l'unica che richiede di guardare le
pagine, non di misurarle.
