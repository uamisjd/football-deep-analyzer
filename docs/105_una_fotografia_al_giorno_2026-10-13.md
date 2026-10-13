# 105 — Una fotografia dei dati al giorno: politica di crescita del repository (2026-10-13)

**Decisione dell'utente (13/10/2026, dopo [`docs/104`](104_revisione_totale_2026-10-13.md) §3):
opzione A** — i Parquet aggiornati entrano in `main` **una volta al giorno** invece di ~5.
Il sito continua a essere costruito e pubblicato a ogni run: cambia solo quante copie finiscono
nell'archivio.

## 1. Il problema, misurato (`docs/104` §3)

| Misura (13/10/2026) | Valore |
|---|---|
| Pack del repository | **722,85 MiB** |
| Byte scritti dai commit dei dati — ultimi 30 giorni | **743,8 MB** (~24,8 MB/giorno) |
| Commit dei dati negli ultimi 30 giorni | **155** (~5,2 al giorno) |
| Da dove viene (30 giorni) | news 338,2 MB · backtest 201,7 · predictions 88,6 · player_stats 31,3 · lineup 19,0 · altri ~65 |
| Blob più grande nella storia | 4,9 MB (limiti GitHub: avviso 50 MiB, blocco 100 MiB) |
| Proiezione al ritmo attuale | **1 GB ~24/10/2026** · 5 GB ~7/4/2027 (GitHub raccomanda < 1 GB) |

Ogni run ricostruisce i Parquet da zero e **non legge quelli committati**: le quattro fotografie
intermedie della giornata non servono né al sito né alla pipeline. Servono solo all'archivio.

## 2. La regola (una fotografia al giorno)

`scripts/fotografia_dati.py` — funzione pura `decide()`, 20 test in
`tests/test_fotografia_dati.py` — decide così:

1. **nessuna fotografia precedente** → si committa (primo giro in assoluto);
2. esiste già una fotografia di **oggi** (data UTC) → **non** si committa;
3. altrimenti si committa se **l'ora UTC è ≥ 20** (il run serale delle 23:30 italiane, quello
   con i risultati della giornata) **oppure** se sono passate **≥ 24 ore** (rete di sicurezza:
   se il run serale è fallito, il primo run utile recupera da solo).

Stato letto da dove esiste già: **la cronologia del repository**
(`GET /repos/{repo}/commits?path=data/processed` via `gh api`, con `requests` come ripiego).
Nessun file segnalibro da conservare tra un run e l'altro; "oggi" è sempre la data UTC del server.

**Fail-open:** qualunque errore di lettura (rete, 403, JSON inatteso) produce `commit=true`.
Meglio una fotografia in più che un buco nell'archivio — e una fotografia in più costa ~5 MB.

### Tabella della giornata (orari del cron, UTC)

| Run | 04:00 | 10:00 | 14:00 | 18:00 | 21:30 |
|---|---|---|---|---|---|
| Fotografia committata? | — | — | — | — | ✅ |
| Il sito si pubblica? | ✅ | ✅ | ✅ | ✅ | ✅ |

## 3. L'unica eccezione: il registro preregistrato

`prospettico.parquet` si salva **a ogni run**, se è cambiato. Non è una comodità: è il registro
del test prospettico di γ 1,12 (`docs/89`), e il suo valore di prova è **la data di
registrazione** — la previsione è congelata *prima* del calcio d'inizio. Rinviarlo alla sera
potrebbe perdere le righe delle partite che iniziano nel pomeriggio (una riga si scrive solo
finché il kickoff è futuro). Costo misurato: **0,5 MB in 30 giorni**, cioè niente.

Nel workflow il passo di commit, quando la fotografia è già salvata, stacca tutto dallo staging
(`git reset -q`) e rimette dentro **solo** `data/processed/prospettico.parquet`.

## 4. Effetto atteso

| | Prima | Dopo |
|---|---|---|
| Fotografie dei dati al mese | ~155 | **~30** |
| Byte scritti al mese | 743,8 MB | **~150 MB (−80%)** |
| 1 GB raggiunto | ~24/10/2026 | **~metà dicembre 2026** *(stima: 723 MB + ~150 MB/mese)* |
| 5 GB raggiunti | ~7/4/2027 | **oltre il 2029** *(stessa stima)* |
| Freschezza del sito | 5 build + 5 deploy al giorno | **identica** |
| Richieste alle fonti | invariate | **invariate** |

**Cosa non cambia:** i cinque run del cron, i gate (`verify_site`, parità, resa 375 px), il deploy
Pages a ogni run, i dati con cui il sito è costruito (sono quelli del run, non quelli del repo).

## 5. Come si verifica (fatto)

- **Prova della decisione:** 20 test in `tests/test_fotografia_dati.py`, fra cui la giornata
  intera a cinque run con **una sola** fotografia e la rete di sicurezza a 24 ore (confine
  compreso), il fail-open e il ripiego `gh` → `requests`.
- **Prova del passo di workflow:** il testo del passo è stato estratto dal YAML ed eseguito in un
  repository di prova (origine locale) in **cinque scenari**: fotografia già salvata con e senza
  modifiche, registro cambiato, fotografia da salvare con e senza modifiche. Esiti corretti:
  nei due casi «fotografia già salvata» i Parquet grandi **non** finiscono su origine, il registro
  sì; nei casi serali si committa `data: run …`.
- **Prova dal vivo (sandbox, 13/10):** `python -m scripts.fotografia_dati --repo … --ramo main`
  legge il commit dei dati delle 17:33 UTC di oggi e risponde `commit=false` col motivo
  («fotografia di oggi già salvata»).

## 6. Cosa fare se serve forzare

Nel dispatch manuale di `daily` il campo **`forza_commit`** (default `false`) salva la fotografia
anche se quella di oggi esiste già. Non serve per il funzionamento normale: è l'interruttore per
un salvataggio straordinario.

## 7. Rischi e limiti dichiarati

- **Un giorno senza fotografia** (run serale rosso e nessun run nella finestra successiva):
  la rete di sicurezza a 24 ore committa al primo run utile. Non c'è perdita di dati: i Parquet
  del run successivo sono ricostruiti da zero.
- **Le fotografie intermedie non esistono più**: chi volesse ricostruire lo stato di metà giornata
  non lo trova nel repository. Non serviva a nessuna verifica in corso (`docs/104` §0 spiega come
  sono state fatte le misure: dai Parquet committati, che restano).
- **Il segnaposto della verifica:** dopo il merge, il primo run serale sarà la prima fotografia
  con la regola nuova; i run intermedi devono loggare «fotografia dei dati già salvata oggi».

## 8. Prossimo passo

- Al merge: verificare all'ingresso il primo run serale (fotografia presente) e i run intermedi
  («niente da fare» / solo registro) — la verifica dal vivo che i gate offline non possono dare.
- Se dopo qualche settimana la crescita misurata è dentro la stima, la compattazione periodica
  (**opzione C** di `docs/104` §3, `git filter-repo`) resta la strada per riportare il repo
  sotto i 100 MB; la preparazione (prova su una copia, nessun force push) è a parte.
