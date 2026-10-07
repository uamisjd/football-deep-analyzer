# 52 — Verifica dello stato, dei gate e dell'uso delle fonti (2026-10-07)

**Richiesta:** capire cosa resta da fare, verificare che il progetto funzioni e non consumare inutilmente crediti o richieste ai siti usati.

Le verifiche qui sotto distinguono ciò che è stato verificato **dal vivo su GitHub**, ciò che è stato verificato **offline nel repository** e ciò che resta **da verificare**. L'agente non ha lanciato raccolte o sonde manuali; il merge ha però attivato automaticamente il daily #218 su GitHub, che ha completato la pipeline live con esito verde.

## 0. Verdetto

1. **Automazione live verificata dopo entrambe le PR:** PR **#82** fusa alle 12:05 UTC; daily **#217** (`37618498043`) verde e issue **#79 chiusa**. PR **#83** fusa alle 15:37:25 UTC (merge commit `c92adf5d`); il push ha avviato automaticamente il daily **#218** (`37645413601`), concluso verde con job `run` e deploy `success`, dati aggiornati nel commit `aa760b9` e passi di cache riusciti. Nessun daily manuale è stato dispatchato.
2. **Verifica offline ripetuta dopo le modifiche di questa sessione:** 515 test superati; build del sito riuscita; 159.546 controlli numerici superati; parità e resa mobile senza problemi; `ruff check .` pulito.
3. **Costi a pagamento:** nessuna API sportiva a pagamento è attiva nel codice e non serve una chiave privata. Le quote bookmaker non vengono interrogate live né pubblicate; il benchmark mensile usa CSV storici su un mirror GitHub. L'agente non ha interrogato direttamente FotMob, Understat, ESPN, Google News o Open-Meteo; il daily automatico #218 ha invece eseguito il normale flusso di raccolta sui runner GitHub.
4. **Limite residuo da dichiarare:** ci sono tetti per run sulle due fonti più pesanti, non un budget giornaliero globale condiviso da tutte le fonti. I siti gratuiti possono inoltre cambiare le proprie condizioni d'uso o i limiti tecnici.

## 1. Stato verificato su GitHub

- PR **#82**: merged il 7/10/2026 alle 12:05 UTC; check `test` verde.
- PR **#83**: merged alle 15:37:25 UTC con commit `c92adf5d`; check `test` `success` nel run `37633874640` (1m23s) e stato pre-merge `CLEAN`. L'ordine esplicito dell'utente e i controlli pre-merge sono registrati in `docs/13` §9.17.
- Daily **#217**, run `37618498043`: `success`; issue #79 chiusa. Daily post-merge **#218**, run `37645413601`, partito automaticamente dal push della PR: `success` su `run` e `deploy`, commit dati `aa760b9`. Restore/save cache, `verify_site`, parità schede e resa 375 px sono passati. Nessun run è stato avviato manualmente dall'agente.
- Issue **#79**: chiusa automaticamente alle 12:16 UTC dopo il daily verde.
- Workflow settimanale `lab`: ultimo run **success** il 5/10/2026; sonda Open-Meteo registrata con esito positivo. Workflow `benchmark-quote`: ultimo run **success** il 3/10/2026.
- Il client ESPN resta in **backoff** dopo risposte 403 ripetute (classifica, scoreboard e notizie). Non è un blocco del sito: FotMob è la fonte primaria e Google News copre le notizie; ESPN non viene martellato mentre è sospeso.

Questa è la verifica di produzione disponibile via GitHub. Il sandbox non può raggiungere direttamente tutti gli host sportivi, quindi non si dichiara di averli provati live da qui.

## 2. Gate eseguiti offline in questa sessione

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
- Il workflow `daily` è schedulato **5 volte al giorno**; un merge su `main` o un avvio manuale può aggiungere un run. Il merge #83 ha effettivamente avviato il daily #218 via evento `push`; la concorrenza serializza i daily, ma non limita il numero totale di avvii.
- `benchmark-quote` gira mensilmente, usa un mirror GitHub e ha una cache locale di 30 giorni con tetto di 40 richieste nel client; il workflow mensile non ripristina `data/cache`, quindi in un checkout pulito può scaricare fino a 21 CSV per run. `lab` gira settimanalmente e include una sonda live di fallback (oggi una richiesta Open-Meteo).

### Protezioni già presenti

- `HttpClient` riusa le risposte entro la TTL e applica pause tra le richieste; FotMob e notizie hanno anche tetti **hard per run** (`600` e `200` richieste rispettivamente). I client vengono condivisi nel collettore, quindi il tetto FotMob vale per le sue fasi nel singolo run.
- Le pause configurate sono 1 s per FotMob e notizie, 2 s per Understat e 0,5 s per ESPN; la cache ha TTL da 30 minuti a 10 anni secondo il tipo di dato.
- `daily.yml` ripristina e salva `data/cache` tra i run. Entrambi i passi sono riusciti nei daily #217 e #218. Dopo il #218, l'API cache GitHub riporta **2.529.424.496 byte (2,53 GB) in 12 cache attive**, sotto il tetto di 10 GB citato nel workflow. Le 3 cache `fda-http-*` sommano **26.464.202 byte (~26,5 MB)**; il restante ~2,50 GB è principalmente cache `setup-python` per i pacchetti. È storage GitHub Actions, non consumo di crediti sportivi. `source_status.parquet` del #217 registra **0 richieste nelle fasi di raccolta che monitora**; per il #218 non è stato ricalcolato qui il totale di richieste. In ogni caso quel contatore non misura tutto il traffico della pipeline.
- La misura storica di `docs/50` prima della cache persistente era circa **1.700 richieste/giorno**; la stima di regime dopo la cache è circa **1.100/giorno**. È una stima, non una nuova misura completa post-cache. I dati del 5/10 sono il riferimento osservato: circa 200 richieste FotMob e 135 notizie per run prima della riduzione.

### Cosa non è una garanzia assoluta

I tetti 600/200 sono **per run**, non al giorno; non tutte le fonti hanno oggi un proprio `max_requests`. Un errore della cache non ferma il daily, per scelta di resilienza, ma può causare più richieste. Quindi possiamo evitare spese a crediti — non c'è un'API a pagamento da addebitare — e limitare molto il traffico, ma per una garanzia rigida sul numero totale di richieste sarebbe da aggiungere un budget aggregato giornaliero (e decidere se ridurre i cinque aggiornamenti). Non l'ho introdotto senza una decisione esplicita, perché può degradare o ritardare i dati.

## 4. Cosa resta da fare, in ordine

1. **Resilienza della pubblicazione (proposta, non bloccante):** aggiungere un'indicazione verificabile dell'età dell'ultimo aggiornamento, così un sito fermo viene riconosciuto subito; valutare anche la separazione tra controlli numerici bloccanti e controlli puramente cosmetici. Sono le due proposte di `docs/50` §6 e richiedono una scelta di prodotto.
2. **Linguaggio della narrativa (P2.4):** ricontrollare le frasi segnalate in `docs/19`/`docs/42` sui contenuti generati oggi; non è stata dichiarata chiusa in questa sessione.
3. **Lighthouse (P2.8):** fare il controllo con un browser reale per performance, accessibilità e best practice. La resa statica mobile è verde, ma non prova questi aspetti.
4. **Calendario `prossime.html` (P2.7):** oggi pesa 527.880 byte, sotto il tetto dichiarato di 1,8 MB; paginazione/lazy-loading non è urgente.
5. **Modelli e roadmap facoltativa:** continuare gli esperimenti solo con il protocollo del laboratorio (nessun cambio di modello senza prova walk-forward); `dc_xg`, arricchimento anagrafica giocatori e notifiche Telegram restano estensioni, non guasti del sito.

## Prossimo passo

La PR #83 è fusa (`c92adf5d`); il daily #218 (`37645413601`) successivo al merge è verde, incluso il deploy Pages. Nessun intervento live manuale è necessario. La decisione di prodotto ancora aperta è se aggiungere un tetto aggregato giornaliero o mantenere i limiti per run e la schedulazione attuale. Restano non bloccanti Lighthouse con browser reale, revisione della narrativa P2.4 e proposte di freschezza/gate cosmetici.
