# 54 — PR #84 in conflitto: diagnosi, registrazione della deroga di #83 e stato dopo #85/#86 (2026-10-07)

**Richiesta utente:** «c'è qualche problema con questa PR? informati anche sul progetto senza fare
cose a caso, studia bene tutto» (07/10/2026, PR #84).

## 0. Verdetto in breve

1. **Sì, #84 ha un problema e non è (solo) il conflitto.** GitHub la mostra `CONFLICTING` /
   `DIRTY`, con conflitti in due file: `docs/13_modelli_e_schede_piano_2026-09-13.md` e
   `docs/STATO.md`. Causa: la PR è partita dalla base `aa760b9` (07/10, 15:50 UTC) e su `main`
   sono poi entrate **PR #85** (17:08:41, `819630e`) e **PR #86** (17:33:11, `7d3d0ae`), che
   toccano gli stessi due documenti.
2. **Il conflitto è anche di merito, non solo di testo.** #84 aggiunge una sezione `### 9.17`
   (deroga del merge di #83), ma `main` ha **già** una `### 9.17` (deroga del merge di #85): una
   risoluzione ingenua del conflitto produrrebbe due §9.17 oppure cancellerebbe un record. Anche
   il paragrafo in cima a `STATO.md` e la «Catena delle deroghe» vanno **uniti**, non scelti.
3. **Il contenuto di #84 era già in parte superato quando è stato scritto.** Aggiornava il
   briefing a «#83 fusa, daily #218 verde», ma non conosceva #85/#86, `docs/53` e le decisioni
   D1–D4. Se fosse entrata in `main` così com'era, avrebbe riportato l'handoff della porta
   d'ingresso su `docs/52` (invece che sul più recente `docs/53`) e avrebbe declassato lo stato
   di oggi. Il conflitto, in questo caso, ha **impedito** che il problema arrivasse in `main`.
4. **Restano però tre cose che #84 portava e che oggi su `main` mancano** (verificate con
   comandi in questa sessione, §4): (a) il **record della deroga del merge di #83** in `docs/13` e
   `STATO.md` — la regola D lo richiede e su `main` non esiste da nessuna parte; (b) la
   **verifica post-merge** di #83 (daily #218, commit dati `aa760b9`) in `docs/52`; (c)
   l'aggiornamento dell'**handoff del briefing**, che su `main` è ancora fermo a «PR #83 aperta …
   verificare lo stato prima di agire» e non cita `docs/53`.
5. **Come si risolve:** #84 **non si ripara da questa sessione** — il suo branch
   (`arena/e20f049c`) appartiene a un'altra sessione e questa sessione ha il divieto di pushare
   su branch diversi dal proprio. La via corretta è una **PR sostitutiva** dal branch di questa
   sessione che porta in `main` il contenuto di #84 ancora valido, aggiornato allo stato di oggi;
   #84 è stata poi **chiusa** (7/10/2026, ore 17:51:32Z) su decisione dell'utente, non mergiata;
   è quello che fa questa PR sostitutiva, **PR #87** (§3), **fusa alle 17:55:26Z su ordine
   esplicito dell'utente** (deroga registrata in `docs/13` §9.19).

## 1. Cronologia degli eventi (tutto verificato via API GitHub, §4)

| Ora (UTC) | Evento |
|---|---|
| 15:37:25 | **PR #83 fusa** in deroga (ordine utente «Please merge the pull request»): merge commit `c92adf5d`, `merged_by=uamisjd`. Il push avvia automaticamente il daily **#218** (`37645413601`), verde, dati `aa760b9` |
| 15:50:20 | **PR #84 aperta** dal branch `arena/e20f049c` (base `aa760b9`), con il record del merge di #83 |
| 15:52 | check `test` di #84 **verde** (run `37647213692`, 2m11s): la CI non è mai stata un problema |
| 17:05:59 | daily **#219** (schedulato), verde, dati `9bb23a9` |
| 17:08:41 | **PR #85 fusa** in deroga: `819630e` → daily **#220**, verde, dati `e01de11` |
| 17:33:11 | **PR #86 fusa**: `7d3d0ae` (record del merge di #85). Solo documenti → `paths-ignore: docs/**`: **nessun daily nuovo** |
| dopo le 17:33 | #84 passa a `CONFLICTING` / `DIRTY`: `docs/13` e `STATO.md` sono esattamente i file toccati da #85/#86 |
| 17:51:32 | **#84 chiusa** su decisione dell'utente, perché superata: il suo contenuto valido è in questa PR (#87) |
| 17:55:26 | **PR #87 fusa dall'agente in deroga** (ordine esplicito dell'utente): merge commit `01fd0e4`; nessun run attivato su `main` (solo documenti) |

## 2. Il conflitto, misurato con un comando

```
$ git merge-base origin/main 4ae80c3        # 4ae80c3 = head di #84
aa760b9ae1a88afe9de2e29cf0e48e409563f72e
$ git merge-tree --write-tree origin/main 4ae80c3      # git 2.39.5, exit 1
… CONFLICT (content): Merge conflict in docs/13_modelli_e_schede_piano_2026-09-13.md
… CONFLICT (content): Merge conflict in docs/STATO.md
```

I due file in conflitto sono esattamente quelli toccati **sia** da #84 **sia** da #85/#86:

| File | Chi lo tocca | Esito |
|---|---|---|
| `docs/13_modelli_e_schede_piano_2026-09-13.md` | #84 (aggiunge §9.17 su #83) **e** #86 (§9.17 su #85 + catena deroghe) | conflitto + collisione di numerazione |
| `docs/STATO.md` | #84 (paragrafo di stato) **e** #85/#86 (paragrafo di stato più recente) | conflitto (due «Ultimo aggiornamento» alternativi) |
| `docs/52_verifica_stato_costi_e_gate_2026-10-07.md` | solo #84 | nessun conflitto file, ma contenuto da aggiornare (non conosce #85/#86) |
| `docs/BRIEFING_NUOVA_SESSIONE.md` | solo #84 | nessun conflitto file, ma contenuto da aggiornare (idem) |

## 3. Cosa porta questa PR sostitutiva (PR #87)

1. **`docs/13`** — nuova **§9.17 «Merge PR #83 — lint in CI e handoff (deroga esplicita)»**; la
   vecchia §9.17 (deroga #85) diventa **§9.18**, con nota di rinumerazione; «Catena delle
   deroghe» aggiornata a `#80, #83, #85 (2026-10-07)`.
2. **`docs/52`** — applicati gli aggiornamenti di #84 ancora veri (post-merge #83, daily #218,
   cache) + **misura di oggi** della cache Actions (16 voci · 3,02 GB, di cui `fda-http-*`
   5 voci · 44,1 MB) + coda aggiornata alle decisioni D1–D4 di `docs/53` §7.
3. **`docs/BRIEFING_NUOVA_SESSIONE.md`** — handoff riscritto allo stato di oggi (con #85/#86,
   `docs/53`, D1–D4), sezioni 2/3/4 riallineate, indice con `docs/53` e `docs/54` e conteggi
   corretti.
4. **`docs/STATO.md`** — nuovo paragrafo di sessione in cima; riferimento a «§9.17» per #85
   corretto in «§9.18».
5. **`README.md`** — conteggio dei file di `docs/` aggiornato.
6. **`docs/54`** (questo file) — la diagnosi, i comandi e le prove, perché una sessione futura
   non debba rifarli.

## 4. Prove raccolte (comandi e risultati, 07/10/2026)

| Verifica | Comando | Risultato |
|---|---|---|
| Stato di #84 | `gh api repos/…/pulls/84` | `mergeable=false`, `mergeable_state=dirty`; commit `4ae80c3`; 4 file, solo `docs/` |
| Conflitti | `git merge-tree --write-tree origin/main 4ae80c3` | conflitti in `docs/13` e `docs/STATO.md` |
| Merge di #83 | `gh api repos/…/pulls/83` | `merged=true`, `merged_at=15:37:25Z`, `merged_by=uamisjd`, `merge_commit_sha=c92adf5d…` |
| Check di #83 | `gh api repos/…/commits/4da7bc3/check-runs` | `test` `success` (14:06:04→14:07:27Z) |
| Merge di #85/#86 | `gh api repos/…/pulls/85`, `…/pulls/86` | `819630e`, 17:08:41Z · `7d3d0ae`, 17:33:11Z |
| Daily | `gh run list --workflow=daily.yml` | #218 `37645413601`, #219 `37656416779`, #220 `37656789947`: tutti `success` |
| Issue/PR aperte | `gh issue list`, `gh pr list --state open` | al momento della misura: 0 issue; 1 PR aperta, **#84** — chiusa alle 17:51:32Z perché superata da #87 |
| Cache Actions | `gh api repos/…/actions/caches` | **16 voci · 3.018.930.552 B (3,02 GB)**; `fda-http-*` 5 voci · 44,1 MB; il resto `setup-python` (11 voci, 235–342 MB, una per branch/hash) |
| Trigger dei workflow | `daily.yml`, `tests.yml` | entrambi con `paths-ignore: docs/**` → un merge di soli documenti non consuma run né richieste alle fonti |

**Nota sulle cache (misura, non allarme):** le voci `fda-http-<run_id>` crescono di **una per
daily** (~8,8 MB l'una), le `setup-python` di una per branch/hash del `pyproject.toml`
(~235–342 MB). Il totale resta sotto il tetto di 10 GB citato nel workflow e GitHub sfronda con
criterio LRU; non è traffico verso le fonti sportive. Il valore di 2,53 GB/12 voci registrato da
#84 alle 15:5x e questo di 3,02 GB/16 voci alle 17:5x sono due fotografie di una grandezza che si
muove: nei documenti va sempre indicato l'istante della misura.

## 5. Cosa NON è stato fatto (e perché)

- **Nessun merge di #84**: il merge spetta all'utente (regola D). La sua **chiusura** è stata
  eseguita alle 17:51:32Z **su richiesta esplicita dell'utente** («chiudi tu #84 ora»), non di
  iniziativa dell'agente. Tecnicamente, questa sessione **non può** comunque pushare sul branch
  `arena/e20f049c`. Il **merge di questa PR (#87)** è stato eseguito dall'agente alle 17:55:26Z
  **in deroga esplicita** (ordine dell'utente «Please merge the pull request»), dopo le verifiche
  pre-merge di regola D; la deroga è registrata in `docs/13` §9.19 e in `docs/STATO.md`.
- **Nessuna raccolta live, nessuna sonda, nessun daily manuale**: la modifica è solo documentale,
  e i trigger di `daily`/`tests` escludono i push di soli documenti (§4).
- **Nessuna modifica a codice, dati o workflow**: `git diff --stat` della PR tocca solo `*.md`.

## Prossimo passo

1. **Fatto — chiusura di #84** (7/10/2026, 17:51:32Z): decisione dell'utente perché superata da
   questa PR; motivazione e prove restano in questo documento.
2. **Fatto — merge di questa PR**: #87 fusa alle **17:55:26Z** su ordine esplicito dell'utente
   (deroga registrata in `docs/13` §9.19), merge commit `01fd0e4`; **nessun** daily né run di test
   attivato su `main` (solo documenti).
3. Nessun'altra azione operativa: la coda non bloccante è quella di `docs/53` §6.2/§6.4 e le
   decisioni D1–D4 di `docs/53` §7 restano chiuse (non riproporle senza nuovi motivi).
