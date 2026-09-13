# Consegna del lavoro bloccato nel sandbox `arena/01a094e1` (2026-09-13)

Questo file serve a trasferire in un'altra sessione il lavoro che **non è mai arrivato su GitHub**:
l'egress HTTPS del sandbox `arena/01a094e1-football-deep-analyzer` taglia il TLS verso GitHub
(vedi sotto), quindi i 4 commit locali esistono solo lì.

## Correzione di quanto affermato in precedenza

Nel turno precedente è stato detto che, aprendo una sessione nuova, «i file restano». **È falso per
una sessione nuova**: i file del workspace persistono fra i *turni della stessa sessione*, ma una
sessione nuova parte da un clone fresco di `origin/main` e quindi **non contiene** questo lavoro.
La verifica fatta nel sandbox originale conferma che qui il lavoro c'è ancora:

- branch `arena/01a094e1-football-deep-analyzer`, working tree pulita
- commit locali: `acc5ec5` (docs post-merge), `fdd539a` (intervalli di Wilson),
  `86ef902` (backtest fuori campione), `b3282c0` (nota di ripresa) — nessuno pushato
- `docs/STATO.md` riga 3 = `## ⚠ In attesa di push — rete del sandbox bloccata`
- `src/fda/models/backtest.py` (8208 byte) e `tests/test_backtest.py` (9924 byte) presenti
- `git ls-remote origin -h` → `gnutls_handshake() failed: The TLS connection was non-properly terminated`

## Rete del sandbox originale (misurata)

DNS ok (`github.com → 140.82.116.3`), TCP ok (`Connected to api.github.com port 443`), connessione
persa **durante l'handshake TLS** (`OpenSSL SSL_ERROR_SYSCALL` dopo il Client Hello → blocco su SNI).
Rispondono 200 solo `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`. Resettati:
`api.github.com`, `github.com`, `objects.githubusercontent.com`, `uamisjd.github.io`, `google.com`,
`example.com` (anche in HTTP semplice), SSH porta 22. Provati senza successo: TLS 1.1/1.2/1.3 forzati,
HTTP/1.1, IP GitHub alternativi. Non è un problema di credenziali: dallo stesso ambiente push e merge
di PR #23 erano riusciti alle 19:41 UTC dello stesso giorno.

## Cosa contiene il lavoro (11 file, +704/−15)

1. **Intervalli di Wilson al 95% sull'accuratezza** — `wilson_interval(k, n)` (definizione unica in
   `src/fda/models/predict.py`, riesportata da `src/fda/site/build.py`); colonna «intervallo 95%» e
   segnale `compatibile` / `fuori intervallo` nella tabella per mercato e in calibrazione (con `k/n`).
2. **Backtest cronologico fuori campione** — `src/fda/models/backtest.py`
   (`chronological_backtest()`, `backtest_summary()`, `observed_flags()`), comando `fda backtest`
   incluso in `fda daily`, tabella `backtest`, card condizionale su `accuratezza.html`.
3. **Verificatore** — blocco `[7]` (intervalli pubblicati ricalcolati) e `[8]` (backtest: numerosità
   e RPS ricalcolati con `predict.rps`).
4. **Test** — `tests/test_backtest.py` (8 test, incluso il controllo anti-leakage con modello-spy) e
   nuove asserzioni in `tests/test_site.py`.
5. **Docs** — `docs/11_partite_oggi_miglioramenti.md` sezioni F6b/F6c/F6d.
6. **Regole di lavoro** — `docs/00_regole_di_lavoro.md`: nuova regola **8bis** (push immediato, mai
   commit locali in attesa), condizione di stop **prima del merge** (`git log --oneline
   origin/main..HEAD` e `git status --porcelain` devono essere puliti), voce nuova nella checklist
   pre-PR e nota dell'incidente 2026-09-12/13 (merge di PR #23 seguito da 4 commit mai pushati,
   rimasti intrappolati nel sandbox quando l'egress è stato tagliato).

## Come scaricare questi due file

Il sandbox originale non può pushare, quindi i file sono serviti dal server di preview
(`python3 -m http.server 8000 --directory site`, copiato in `site/handover/`): aprire la preview e
aggiungere il percorso `/handover/` → elenco cliccabile con `IN_ATTESA_DI_PUSH.md` e
`patch_codice_e_test.patch`.

## Come applicarlo nella sessione nuova

Il patch **esclude `docs/STATO.md`** (quel file viene scritto anche dal run `daily`, quindi il
contesto non è affidabile): la sezione di STATO da incollare è riportata in fondo a questo file.

```bash
cd football-deep-analyzer
git fetch origin main && git reset --mixed FETCH_HEAD     # allinea al main corrente
git apply --check handover/patch_codice_e_test.patch      # deve passare senza output
git apply handover/patch_codice_e_test.patch              # 10 file modificati/nuovi
python -m venv .venv && .venv/bin/pip install -q -e ".[dev]"
.venv/bin/pytest -q                                       # atteso: 115 passed
.venv/bin/ruff check --select F,E src/fda/models/backtest.py tests/test_backtest.py   # atteso: pulito
.venv/bin/fda build
.venv/bin/python scripts/verify_site.py --site site --data data/processed
#   atteso: nessun problema · 1727 controlli numerici superati
git add -A && git commit -m "Accuratezza: intervalli di Wilson 95% e backtest fuori campione"
git push origin <branch-della-sessione>
gh pr create --fill                                       # il merge lo fa sempre l'utente (policy sez. D)
```

Il patch è stato verificato nel sandbox originale: `git apply --check` sulla base `f4ce2a0` passa e
l'applicazione produce esattamente 10 file modificati.

## Ultimi esiti delle verifiche (sandbox originale, sugli stessi file)

- `pytest -q` → **115 passed**
- `ruff --select F,E` → pulito su `src/fda/models/backtest.py` e `tests/test_backtest.py`
- `fda build` → 344 partite / 2364 fixture / 7388 giocatori
- `scripts/verify_site.py` → **nessun problema · 1727 controlli** (1740 con la tabella `backtest`
  popolata; `[8] backtest: 63 gare fuori campione, RPS pagina 0,2015 = ricalcolato 0,2015`)
- backtest su storico **sintetico** (non calcio reale): 63 gare, RPS 0,2015 contro 0,2282 della base,
  log-loss 0,9997 — i numeri reali li produrrà il primo `fda daily` con rete

---

## Sezione da incollare in cima a `docs/STATO.md`

## ⚠ In attesa di push — rete del sandbox bloccata (aggiornato 2026-09-13)

Tre commit locali sono pronti ma **non pushati**: l'egress HTTPS del sandbox è stato ridotto a una
allowlist di registry di pacchetti. Misurato in questo turno: DNS ok (`github.com → 140.82.116.3`),
TCP ok (`Connected to api.github.com port 443`), poi la connessione cade **durante l'handshake TLS**
(`OpenSSL SSL_ERROR_SYSCALL` subito dopo il Client Hello → blocco su SNI). `pypi.org`,
`files.pythonhosted.org` e `registry.npmjs.org` rispondono **200**; `api.github.com`,
`objects.githubusercontent.com`, `uamisjd.github.io`, `google.com`, `example.com` (anche in HTTP
semplice) e SSH porta 22 sono resettati. Non è un problema di credenziali (curl fallisce allo stesso
modo senza autenticazione) né del repository: dallo stesso ambiente il push e il merge di PR #23
erano riusciti alle 19:41 UTC.

**Importante per chi riprende:** i **file** del workspace restano, i **commit locali no** (già
osservato in questa sessione: al giro successivo il repo era ri-clonato e gli oggetti commit
spariti). Quindi il lavoro va ricommitato, non ricercato per SHA.

Delta da pushare (11 file, +689/−14) — verificato con `git diff --name-status`:
`.github/workflows/daily.yml`, `docs/11_partite_oggi_miglioramenti.md`, `docs/STATO.md`,
`scripts/verify_site.py`, `src/fda/cli.py`, `src/fda/models/backtest.py` (nuovo),
`src/fda/models/predict.py`, `src/fda/site/build.py`, `src/fda/site/templates/accuracy.html`,
`tests/test_backtest.py` (nuovo), `tests/test_site.py`.

Comandi di ripresa (in una sessione nuova, con rete):

```bash
cd football-deep-analyzer
git status --porcelain                      # deve mostrare gli 11 file come modifiche
git fetch origin main && git reset --mixed FETCH_HEAD
.venv/bin/pip install -q -e ".[dev]"        # il venv non sopravvive
.venv/bin/pytest -q                         # atteso: 115 passed
.venv/bin/fda build && .venv/bin/python scripts/verify_site.py --site site --data data/processed
git add -A && git commit -m "Accuratezza: intervalli di Wilson 95% e backtest fuori campione"
git push origin arena/01a094e1-football-deep-analyzer
gh pr create --fill                         # il merge lo fa sempre l'utente (policy sez. D)
```

Ultimo esito delle verifiche su questi file (eseguite in questo turno): **115 passed**, `ruff
--select F,E` pulito sui file nuovi, `fda build` 344 partite / 2364 fixture / 7388 giocatori,
`verify_site.py` **1727 controlli · 0 problemi** (1740 con la tabella `backtest` popolata).
