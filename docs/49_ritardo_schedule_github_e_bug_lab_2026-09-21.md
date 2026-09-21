# 49 — Perché il sito era fermo alle 01:29 e il bug del `lab` (2026-09-21)

**Scopo.** Domanda dell'utente alle 11:44 IT: *«aggiornato 21/09/2026 01:29 (ora italiana) — sono
le 11:44, come mai non sono partiti gli aggiornamenti automatici?»*. Tutto ciò che segue è
**misurato oggi** (11:44–12:05 IT) con `gh api`, `gh run list`, `git show origin/diag-logs:*`,
riproduzione locale e lettura del sito pubblicato.

---

## 1. Verdetto: nessun guasto nel repository — GitHub avvia gli schedule in grave ritardo

Il sito fermo alle **01:29** era il build del run schedulato delle 23:30 IT della notte prima
(`35544390716`, partito 23:21 UTC con 1h51m di ritardo, commit dati `281fda4`, success). Da
allora **nessun run `daily` risultava creato, in esecuzione o in coda** (verificato via API:
zero run pending su tutto il repo): il cron delle **06:00 IT** (04:00 UTC) di oggi non era
proprio partito, 5h46m dopo l'orario nominale.

**Prova regina che non è un problema del workflow `daily`:** stamattina anche il workflow
`lab` (cron del lunedì 05:30 IT) è partito solo alle **11:11 IT** (+5h41m). Gli schedule
funzionano: GitHub li avvia con ritardi di molte ore (fenomeno già misurato in `docs/41` §1.3,
media 3,1h — oggi superato anche il massimo storico di 5h35m).

## 2. Ritardi misurati (ora di creazione del run rispetto al cron nominale)

| cron (IT) | 18/09 | 19/09 | 20/09 | 21/09 |
|---|---|---|---|---|
| 06:00 | +4h56 | +4h42 | +5h12 | **+5h49** (partito 11:49 IT) |
| 12:00 | +3h58 | +3h34 | +3h49 | — |
| 16:00 | +3h25 | +2h58 | +3h14 | — |
| 20:00 | +2h10 | +1h47 | +2h01 | — |
| 23:30 | +1h58 | +1h49 | +1h51 | — |
| `lab` lun 05:30 | — | — | — | **+5h41** (partito 11:11 IT) |

Pattern stabile: più il cron è nelle ore centrali europee (carico della piattaforma), più il
ritardo cresce. Il run delle 06:00 IT di oggi, alle 11:46 non era ancora nemmeno in coda: è
arrivato da solo alle 11:49 IT (`35585378048`), concluso **verde** alle 12:00 IT (run + deploy).
Catena verificata fino in fondo: commit dati `551a6a0` «data: run 2026-09-21 09:59 UTC [skip ci]»
e sito pubblicato con **«AGGIORNATO 21/09/2026 11:56»**.

## 3. Il bug del `lab`: `git add --ignore-missing` richiede `--dry-run`

Il run del `lab` delle 11:11 IT (`35581890193`) è **caduto** al passo «Commit del riepilogo del
laboratorio». Log portati dal workflow `diag` su `diag-logs` (il blob storage di Actions resta
irraggiungibile dal sandbox, `docs/00` §B6). L'errore è una sola riga:

```
fatal: the option '--ignore-missing' requires '--dry-run'
```

- **Causa**: `lab.yml` faceva `git add --ignore-missing <3 file>` senza `--dry-run`: git rifiuta
  la combinazione con exit 128 (riprodotto in locale, git 2.39.5). Non era un conflitto di push.
- **Perché non si era mai visto**: la riga è entrata in `bb99d93` del **15/09** (aggiunta di
  `xi_league.parquet` al commit del riepilogo), poi estesa da `2687c8f` del 16/09. Il cron del
  `lab` gira **solo il lunedì**: stamattina era il primo run dopo la riga rotta. L'ultimo run
  verde (14/09) usava ancora `git add data/processed/model_lab.parquet`, valido.
- **Fix** (in questa PR): loop `for f in …; do if [ -f "$f" ]; then git add "$f"; fi; done` —
  ogni file solo se esiste, senza flag incompatibili (testato con `bash -e`, la shell dei runner).

## 4. Bucchi residui (non approvati in questa sessione)

1. **Allerta silenziosa sui run che NON partono**: `ci_alert.py` scatta solo su run **rossi**.
  Un cron saltato/dilazionato da GitHub non apre issue: l'unico sintomo resta l'orario in testa
  alla pagina. Candidato futuro: watchdog che, se il sito supera N ore senza run, rilancia il
  `daily` e apre una issue (proposto all'utente il 21/09, non approvato in questa sessione).
2. **Dispatch dei workflow dal sandbox = 403** (`Resource not accessible by integration`):
  confermato oggi su `gh workflow run daily.yml` (come già `docs/21` §16). L'avvio manuale resta
  un click dell'utente su «Run workflow»; per il `diag` il workaround `diag/trigger.txt` + push
  funziona ed è quello che ha portato i log di oggi.

## Prossimo passo

Merge della PR (utente). Al lunedì successivo verificare che il `lab` committi il riepilogo
senza errori. Se i ritardi degli schedule restano su queste ampiezze, riprendere il watchdog
di §4.1.
