# 52 — Verifica dello stato, dei gate e dell'uso delle fonti (2026-10-07)

**Richiesta:** capire cosa resta da fare, verificare che il progetto funzioni e non consumare inutilmente crediti o richieste ai siti usati.

Le verifiche qui sotto distinguono ciò che è stato verificato **dal vivo su GitHub**, ciò che è stato verificato **offline nel repository** e ciò che resta **da verificare**. L'agente non ha lanciato raccolte o sonde manuali; il merge ha però attivato automaticamente il daily #218 su GitHub, che ha completato la pipeline live con esito verde. Aggiornamento del 7/10 sera: la revisione più recente del progetto è [`docs/53`](53_revisione_totale_qualita_quantita_2026-10-07.md) (gate a **517** test e **159.573** controlli) e la storia delle PR #83/#84/#85/#86 è in [`docs/54`](54_pr84_conflitto_e_registrazione_pr83_2026-10-07.md); questo documento resta la verifica di questa sessione.

## 0. Verdetto

1. **Automazione live verificata dopo entrambe le PR:** PR **#82** fusa il 7/10 alle 12:05 UTC; daily **#217** (`37618498043`) verde e issue **#79 chiusa**. PR **#83** fusa alle 15:37:25 UTC (merge commit `c92adf5d`, deroga registrata in `docs/13` §9.17); il push ha avviato automaticamente il daily **#218** (`37645413601`), verde con job `run` e deploy `success`, commit dati `aa760b9` e passi di cache riusciti. Nessun daily manuale è stato dispatchato. Al controllo iniziale non risultavano altre issue o PR aperte.
2. **Verifica offline ripetuta dopo le modifiche di questa sessione:** 515 test superati; build del sito riuscita; 159.546 controlli numerici superati; parità e resa mobile senza problemi; `ruff check .` pulito.
3. **Costi a pagamento:** nessuna API sportiva a pagamento è attiva nel codice e non serve una chiave privata. Le quote bookmaker non vengono interrogate live né pubblicate; il benchmark mensile usa CSV storici su un mirror GitHub. L'agente non ha interrogato direttamente FotMob, Understat, ESPN, Google News o Open-Meteo; il daily automatico #218 ha invece eseguito il normale flusso di raccolta sui runner GitHub.
4. **Limite residuo da dichiarare:** ci sono tetti per run sulle due fonti più pesanti, non un budget giornaliero globale condiviso da tutte le fonti. I siti gratuiti possono inoltre cambiare le proprie condizioni d'uso o i limiti tecnici.

## 1. Stato verificato su GitHub

- PR **#82**: merged il 7/10/2026 alle 12:05 UTC; check `test` verde.
- PR **#83**: merged alle 15:37:25 UTC con merge commit `c92adf5d`; check `test` `success` nel run `37633874640` (1m23s) e stato pre-merge `CLEAN`. L'ordine esplicito dell'utente, i controlli pre-merge e la verifica post-merge sono registrati in `docs/13` §9.17.
- Daily **#217**, run `37618498043`: `success`; issue #79 chiusa. Daily post-merge **#218**, run `37645413601`, partito automaticamente dal push della PR: `success` su `run` e `deploy`, commit dati `aa760b9`. Restore/save cache, `verify_site`, parità schede e resa 375 px sono passati. Nessun run è stato avviato manualmente dall'agente.
- Dopo la stesura di questo documento (7/10 sera) sono arrivati altri due daily verdi, **#219** (`37656416779`, schedulato) e **#220** (`37656789947`, push del merge #85), con i commit dati `9bb23a9` e `e01de11`; il merge di #86 è di soli documenti e non ha attivato un daily (`paths-ignore: docs/**` in `daily.yml` e `tests.yml`). Stato al 7/10 sera: **0 issue**, **1 PR aperta** (#84, superata → da chiudere, `docs/54`).
- Issue **#79**: chiusa automaticamente alle 12:16 UTC dopo il daily verde.
- Workflow settimanale `lab`: ultimo run **success** il 5/10/2026; sonda Open-Meteo registrata con esito positivo. Workflow `benchmark-quote`: ultimo run **success** il 3/10/2026.
- Il client ESPN resta in **backoff** dopo risposte 403 ripetute (classifica, scoreboard e notizie). Non è un blocco del sito: FotMob è la fonte primaria e Google News copre le notizie; ESPN non viene martellato mentre è sospeso.

Questa è la verifica di produzione disponibile via GitHub. Il sandbox non può raggiungere direttamente tutti gli host sportivi, quindi non si dichiara di averli provati live da qui.

## 2. Gate eseguiti offline in questa sessione

> Misure di **questa** sessione (prima del lotto di `docs/53`): i gate più recenti — **517** test,
> **0 problemi · 159.573** controlli, build 441/2.364/7.496, parità 66, resa 375 px 26.490 misure — sono
> nella tabella di `docs/53` §1 e §7. Non ripetere i gate senza cambi di codice.

| Verifica | Esito |
|---|---|
| `python -m pytest -q` | **515 passed** (92,92 s nell'ultima esecuzione) |
| `ruff check .` | **All checks passed** |
| `fda build` | exit 0 — **441** schede partita, **2.364** partite, **7.498** giocatori |
| `scripts/verify_site.py` | **0 problemi · 159.546 controlli numerici** |
| `scripts/parita_schede.py site` | **66 schede**; 25 id di sezione e 14 voci dell'indice, struttura e quantità di testo coerenti |
| `python -m scripts.resa_375` | **26.492 misure · 0 problemi** a 375 px |
| Sito generato in locale | **4.206 pagine HTML**; `prossime.html` **527.880 byte** |

Il controllo a 375 px è statico: non sostituisce una prova in un browser reale né una misura Lighthouse. Non è stato eseguito Lighthouse in questa sessione.

### Miglioramento di qualità incluso nella sessione

La prima esecuzione completa di Ruff aveva segnalato 12 rilievi: tre semplificazioni sicure (import inutilizzato, ordine import, booleano ridondante) e nove casi di gestione best-effort già intenzionali (`except` che ignora o salta un dato incompleto), ora dichiarati esplicitamente nelle eccezioni per file di `pyproject.toml`. Dopo la pulizia `ruff check .` è verde. La versione `ruff==0.16.10` è fissata in `pyproject.toml` per rendere il gate ripetibile. Il workflow `tests.yml` ora esegue Ruff prima della suite completa, così queste regressioni vengono rilevate anche sulle PR.

## 3. Richieste e crediti delle fonti

### Cosa viene usato

- **Nessun servizio sportivo a pagamento o con crediti attivo:** nessuna chiamata a The Odds API, API-Football o Bzzoiro e nessuna chiave di questi servizi nel codice operativo. Le relative menzioni nel catalogo sono note/opzioni, non integrazioni attive.
- Le fonti operative sono endpoint pubblici o feed gratuiti (FotMob, Understat, ESPN, Google News RSS, ANSA/Sky, Open-Meteo e mirror CSV su GitHub). FotMob/ESPN sono endpoint non ufficiali o non documentati: il fatto che oggi siano gratuiti non garantisce che le loro regole o disponibilità non cambino. Sul sito generato, **0 su 4.206 pagine** caricano Google Fonts: i font vengono serviti localmente.
- Il workflow `daily` è schedulato **5 volte al giorno**; un merge su `main` o un avvio manuale può aggiungere un run. La concorrenza serializza i daily, ma non limita il numero totale di avvii.
- `benchmark-quote` gira mensilmente, usa un mirror GitHub e ha una cache locale di 30 giorni con tetto di 40 richieste nel client; il workflow mensile non ripristina `data/cache`, quindi in un checkout pulito può scaricare fino a 21 CSV per run. `lab` gira settimanalmente e include una sonda live di fallback (oggi una richiesta Open-Meteo).

### Protezioni già presenti

- `HttpClient` riusa le risposte entro la TTL e applica pause tra le richieste; FotMob e notizie hanno anche tetti **hard per run** (`600` e `200` richieste rispettivamente). I client vengono condivisi nel collettore, quindi il tetto FotMob vale per le sue fasi nel singolo run.
- Le pause configurate sono 1 s per FotMob e notizie, 2 s per Understat e 0,5 s per ESPN; la cache ha TTL da 30 minuti a 10 anni secondo il tipo di dato.
- `daily.yml` ripristina e salva `data/cache` tra i run. Entrambi i passi sono riusciti nei daily #217, #218, #219 e #220. Misure della API cache GitHub del 7/10, con l'istante (è una grandezza che si muove): alle 15:5x **2.529.424.496 byte (2,53 GB) in 12 voci**, alle 17:5x **3.018.930.552 byte (3,02 GB) in 16 voci**. Composizione alle 17:5x: **5 cache `fda-http-*`** (una per daily, ~8,8 MB l'una → **44,1 MB**), il resto cache `setup-python` (11 voci da 235-342 MB, una per branch/hash del `pyproject.toml`, create anche dai run delle PR). Tutto sotto il tetto di 10 GB citato nel workflow; GitHub sfronda le voci più vecchie con criterio LRU. Storage Actions ≠ traffico verso le fonti sportive. `source_status.parquet` registra **0 richieste nelle fasi di raccolta che monitora** per il run del 7/10 alle 12:06 UTC, coerente con risposte servite dalla cache. Questo contatore non misura ogni possibile richiesta degli altri passi (per esempio lo storico letto dai modelli), quindi non viene presentato come un totale di rete dell'intera pipeline.
- La misura storica di `docs/50` prima della cache persistente era circa **1.700 richieste/giorno**; la stima di regime dopo la cache è circa **1.100/giorno**. È una stima, non una nuova misura completa post-cache. I dati del 5/10 sono il riferimento osservato: circa 200 richieste FotMob e 135 notizie per run prima della riduzione.

### Cosa non è una garanzia assoluta

I tetti 600/200 sono **per run**, non al giorno; non tutte le fonti hanno oggi un proprio `max_requests`. Un errore della cache non ferma il daily, per scelta di resilienza, ma può causare più richieste. Quindi possiamo evitare spese a crediti — non c'è un'API a pagamento da addebitare — e limitare molto il traffico, ma per una garanzia rigida sul numero totale di richieste sarebbe da aggiungere un budget aggregato giornaliero (e decidere se ridurre i cinque aggiornamenti). Non l'ho introdotto senza una decisione esplicita, perché può degradare o ritardare i dati.

## 4. Cosa resta da fare, in ordine

> **Coda aggiornata (7/10 sera).** Questi cinque punti sono stati portati all'utente come decisioni
> D1-D4 in `docs/53` §4 e **risolti in `docs/53` §7**: D1 niente watchdog, D2 gate tutti bloccanti,
> D3 nessun tetto giornaliero, D4 niente Lighthouse. P2.4 è stata **chiusa con misura** dalla stessa
> sessione. Restano come coda non bloccante solo `docs/53` §6.2 e §6.4. Le righe che seguono
> restano come traccia di cosa era aperto quando questo documento è stato scritto.

1. **Resilienza della pubblicazione (proposta, non bloccante):** aggiungere un'indicazione verificabile dell'età dell'ultimo aggiornamento, così un sito fermo viene riconosciuto subito; valutare anche la separazione tra controlli numerici bloccanti e controlli puramente cosmetici. Sono le due proposte di `docs/50` §6 e richiedono una scelta di prodotto.
2. **Linguaggio della narrativa (P2.4):** ricontrollare le frasi segnalate in `docs/19`/`docs/42` sui contenuti generati oggi; non è stata dichiarata chiusa in questa sessione.
3. **Lighthouse (P2.8):** fare il controllo con un browser reale per performance, accessibilità e best practice. La resa statica mobile è verde, ma non prova questi aspetti.
4. **Calendario `prossime.html` (P2.7):** oggi pesa 527.880 byte, sotto il tetto dichiarato di 1,8 MB; paginazione/lazy-loading non è urgente.
5. **Modelli e roadmap facoltativa:** continuare gli esperimenti solo con il protocollo del laboratorio (nessun cambio di modello senza prova walk-forward); `dc_xg`, arricchimento anagrafica giocatori e notifiche Telegram restano estensioni, non guasti del sito.

## Prossimo passo

La PR #83 è **fusa** (`c92adf5d`, 15:37:25 UTC) e il daily post-merge **#218** è verde (`37645413601`), deploy Pages incluso: nessun intervento live manuale è necessario. La registrazione della deroga è in `docs/13` §9.17. Il seguito della giornata (#84, #85, #86 e la PR sostitutiva di `docs/54`) è documentato in [`docs/54`](54_pr84_conflitto_e_registrazione_pr83_2026-10-07.md): la PR #84 è **superata e da chiudere**, la coda non bloccante è quella di `docs/53` §6.2/§6.4. La PR non modifica raccolta live o numero dei run. Dopo il merge dell'utente, verificare il daily successivo. Per ridurre ulteriormente il traffico senza rischiare di perdere dati, la prossima decisione utile è scegliere se serve un tetto aggregato giornaliero o se bastano cache e limiti per run.
