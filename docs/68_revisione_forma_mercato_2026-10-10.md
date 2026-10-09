# 68 — Revisione indipendente di forma e benchmark (2026-10-10)

Richiesta dell'utente: «verifica che hai fatto tutto corretto e fai una revisione».
Perimetro: lavoro della **PR #98**, [B / docs/66](66_la_forma_dice_contro_chi_2026-10-09.md)
e [D / docs/67](67_modello_contro_mercato_offline_2026-10-09.md), a partire da `3f5adfd`.
Nessuna raccolta sportiva, nessun cambio di modello, nessun merge.

## 1. Verdetto del ricalcolo, prima delle correzioni

Non è stata semplicemente rilanciata la suite verde del turno precedente. Sono stati
confrontati il codice e il suo risultato con calcoli separati, sui Parquet locali:

| Controllo indipendente | Campione | Esito |
|---|---:|---|
| Elo letto dalla serie contro `EloModel.fit()` su uno storico **fisicamente troncato** alla data richiesta | **305 date**, **246 prefissi diversi** | **0 differenze** |
| Rating, media, sd e ranghi delle leghe contro quei fit | **8.191 confronti** | **0 differenze**, tolleranza 1e−9 |
| Campione della forma ricostruito dal calendario, media avversari, riferimento e soglia/giudizio contro i rating indipendenti | **796 riepiloghi** | **0 differenze** |
| RPS dal metodo scalare del progetto e Brier dalla somma dei tre errori, con un join separato | **1.071 gare appaiate** | risultati di docs/67 confermati, scarto massimo RPS **1,7e−16**, Brier identico |

L'oracolo non legge la serie del generatore. I risultati esattamente al cutoff restano
esclusi; le vecchie righe con la sola data non entrano durante quel giorno. Si conserva la
convenzione temporale del progetto sulle date delle gare: non si sta certificando il momento
esatto in cui una fonte aveva pubblicato ciascun risultato.

**Quindi i numeri pubblicati erano corretti.** Sono invece emerse tre lacune nei controlli,
provate prima di modificare il codice (§3).

## 2. Conteggi dell'handoff: separato l'effetto dell'orologio

Ho ricalcolato la selezione delle schede con data italiana **fissata**, sullo stesso calendario:

| Giorno italiano della build | Schede | Riepiloghi | Ranghi | Giudizi oltre soglia |
|---|---:|---:|---:|---:|
| **9 ottobre** | **446** | **760** | **2.478** | **169** |
| **10 ottobre** | **464** | **796** | **2.648** | **173** |

Il passaggio di giorno spiega **18 schede, 36 righe e 170 ranghi in più**. Non basta invece
citare genericamente «dati più recenti»: `history.parquet` e `fixtures.parquet` sono
**identici byte per byte** fra `8f454cb` e il checkout della sessione. Prova ripetibile:

```bash
git rev-parse 8f454cb:data/processed/history.parquet HEAD:data/processed/history.parquet
git rev-parse 8f454cb:data/processed/fixtures.parquet HEAD:data/processed/fixtures.parquet
```

È corretto quindi restringere la spiegazione in docs/66 alla finestra del sito. Il backtest
è stato aggiornato dal daily successivo, ma **non entra nei conteggi della forma**.

**I 182 giudizi dell'handoff non si riproducono nemmeno fissando il 9 ottobre**: con la
specifica `|diff| > sd_lega / √gare_effettive` e rating alla vigilia delle singole gare sono
169. Il vecchio commit `f5dbdf3` non è disponibile per attribuire lo scarto a una sua riga di
codice. Non si altera la formula per inseguire 182: i 169/173 giudizi sono verificati uno per
uno dall'oracolo indipendente. Questa differenza resta dichiarata, non nascosta nel cambio
di data.

## 3. Lacune dimostrate e corrette

### A. Nome avversario errato con Elo e rango giusti: il gate non lo vedeva

Su una copia di una scheda reale è stato sostituito **solo il nome dell'avversario** nella
lista della forma, lasciando intatti Elo e rango: **[44] dava 0 problemi**. Un numero giusto
accanto alla squadra sbagliata non è una forma corretta.

Ora [44] ricostruisce dal calendario **nomi, punteggi fatti-subiti, sede, ordine e pallini**
(con i rispettivi tooltip) e confronta il testo realmente visibile, non attributi nascosti
che potrebbero essere giusti mentre il testo è sbagliato. La stessa manomissione è rilevata:
**0 → 1 problema**. Esteso il test esistente anche a punteggio e tooltip alterati.

### B. Generatore e verificatore potevano condividere lo stesso errore temporale

Ho simulato `team_elo()` che ignora `before` e restituisce sempre il rating odierno, lasciando
il guasto attivo **sia durante il rendering sia durante il gate**. La pagina cambiava davvero,
ma **[44] restava verde**: anche il verificatore chiamava `team_elo()` / `league_elo()`.

Ora `elo_reference_at_dates()` nel verificatore scorre i risultati in ordine temporale,
applica solo quelli precedenti al cutoff e ne conserva copie indipendenti; non usa la serie,
la ricerca binaria, `form()`, `team_elo()`, `league_elo()` o `form_strength()` del generatore.
I parametri restano quelli di `EloModel`, come richiesto dalla specifica. È **una sola passata**,
non 246 fit aggiunti al daily: i fit ripetuti sono serviti solo alla revisione indipendente.
La stessa regressione simulata produce ora **0 → 9 problemi** sulla scheda campione.

Due test nuovi: snapshot dell'oracolo con pari Elo, cutoff esatto, date senza ora e assenza
di dati; rendering sintetico con almeno dieci squadre e risultato futuro, con il lettore
Elo guasto lasciato attivo durante la verifica.

### C. Il benchmark accettava una lega vuota come chiave valida

Due stringhe vuote (o composte solo da spazi) su entrambi i lati del join si agganciavano:
la gara veniva valutata e il report aggiungeva una **lega senza nome**. Il controllo cercava
`NaN`, ma non `""` o spazi.

Ora queste chiavi fanno fallire la misura, come una lega assente; test parametrico su
`None`, stringa vuota e spazi. Aggiunto anche il controllo del percorso mensile: **senza
`--offline`** viene usato il downloader storico (fake nel test), non il Parquet locale.
Il caso `outcome` intero nullable mancante era già scartato correttamente: verificato,
**nessuna modifica inutile** a quel ramo.

**Impatto sui dati reali del benchmark: nullo**, dimostrato confrontando il JSON prima/dopo:
identico, compresi valori, IC, copertura, esclusioni e SHA-256 dei due input.

## 4. Gate della revisione — esiti finali

| Verifica | Esito osservato |
|---|---|
| Test tematici dei due verificatori | **16 passed** |
| Suite completa | **568 passed** (117,41 s; +6 casi rispetto alla prima consegna) |
| `ruff check .` | pulito |
| `verify_site` | **202.969 controlli · 0 problemi** (prima 200.185) |
| `resa_375` | **27.255 misure · 0 problemi** |
| `parita_schede` | **89 schede**, 24 id, 14 voci d'indice; nessuna differenza |
| CI del codice rivisto `4d2d5e9` | **verde**, run `38003264484` (PR) e `38003261585` (push) |
| `git diff --check` | pulito |

Gate eseguiti sulla build da **464 schede / 2.364 fixture / 7.510 giocatori** già generata
nel turno precedente. Non è stata rilanciata la build: nella revisione **nessun file di
`src/`, nessun modello, template o Parquet è cambiato**. I test di regressione costruiscono
invece nuove schede sintetiche per provare gli errori del generatore e la reazione del gate.
Non si spaccia il controllo della build esistente per una nuova generazione.

I numeri RPS/Brier restano quelli di docs/67; JSON del benchmark prima/dopo identico.
Nessuna raccolta, nuova stima, calibrazione o promozione del modello. I controlli degli ultimi
commit documentali sono consultabili nella [PR #98](https://github.com/uamisjd/football-deep-analyzer/pull/98).

## Prossimo passo

**PR #98 aggiornata e completa; merge esclusivamente dell'utente**, dopo i check dell'ultimo
commit. Il benchmark live mensile non è stato eseguito: percorso verificato offline con fake,
non dichiarato verificato contro la rete. I 182 giudizi dell'handoff restano non riprodotti;
il risultato indipendentemente verificato è quello del §2.
