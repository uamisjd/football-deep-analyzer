# 75 — L'errore visto stamattina (issue #99): il campione gonfiato di una gara (2026-10-10)

**Richiesta dell'utente:** «stamattina ho trovato questo errore, puoi indagare sul problema e
fare una revisione, correggi gli errori» — con lo screenshot di GitHub.

## 1. Che cosa diceva l'errore

L'immagine è la segnalazione automatica **issue #99 «🚨 Fallimento run giornaliero (daily)»**,
aperta alle **01:54** di stamattina (ora italiana) dal run `38005701599`. Dentro, la diagnostica
del `verify.log`:

```
PROBLEMI (2): {'campione': 2}
  - 5781769.html: campione FotMob 8 gare, ma prima del calcio d'inizio ne risultano 7
  - 5781776.html: campione FotMob 8 gare, ma prima del calcio d'inizio ne risultano 7
```

Due schede su 89 pubblicavano un campione di **8 gare** quando, contando sul calendario, prima
di quel calcio d'inizio la squadra ne aveva giocate **7**. L'invariante **[44]** (card «Le due
squadre», `docs/64` §7) ha fermato il daily: sito non pubblicato.

## 2. Cronologia, ricostruita dai run

| Ora (CEST) | Fatto |
|---|---|
| 01:42 | run `38005701599` (push del merge #98) — **fallisce** su «Verifica il sito» |
| 01:54 | issue #99 aperta in automatico |
| 03:05 | run `38011789043` (schedulato) — **fallisce** ancora sullo stesso controllo |
| **03:47** | **PR #100 fusa**: dentro c'è il fix del campione (`_finite_nel_calendario`) |
| 10:40 | daily verde — la issue si chiude da sola alle **11:42** |

Quindi l'errore che l'utente ha visto stamattina era **già corretto** nel momento in cui lo
guardava: il fix era in produzione dalle 03:47, e l'issue è rimasta aperta solo fino al primo
run verde utile. Nessuno dei due run falliti è stato «riparato a mano»: il secondo è fallito
perché i dati erano ancora quelli del primo.

## 3. La causa vera

Non era un errore di calcolo: era **un disallineamento fra due fonti**.

* `match_info` (il dettaglio gara raccolto da FotMob) diceva «finita, con xG completo»;
* `fixtures` (il calendario) diceva ancora «da giocare».

Il campione della card «Le due squadre» veniva contato su `match_info`, quindi includeva una
gara che il calendario non riconosceva come giocata: 8 contro 7. La causa a monte, dichiarata
nel codice dal fix, è una **cache HTTP incoerente fra le fasi del collect**: due fasi dello
stesso run hanno visto la stessa partita in due stati diversi.

## 4. Il fix (PR #100, già in produzione)

`MatchAnalysis._finite_nel_calendario()` (`src/fda/site/analysis.py`): il campione si conta
sulle righe di `match_info` **che il calendario dà come finite**, con xG completo di entrambe le
squadre. Il calendario è l'autorità su «gara giocata»; `match_info` che corre avanti non gonfia
più un numero pubblicato. La stessa regola vale per lo split di `season_style` e per il
riferimento di lega, così «xG creati» e «xG concessi» restano sulla stessa serie.

Copertura: `test_season_xg_campione_solo_gare_finite_nel_calendario` ricostruisce il caso — tre
gare, una delle quali in `match_info` finita ma non nel calendario — e pretende campione 1.

**Stato dei dati oggi:** calendario e dettaglio gare sono perfettamente allineati — 381 gare
finite, 381 con xG completo, **0** fuori squadra. Lo scostamento era transitorio e si è
ricomposto da solo al run successivo.

## 5. Il buco che restava, e cosa ho aggiunto oggi

Il fix ha un effetto collaterale: **rende lo scostamento silenzioso**.

* prima: il disallineamento gonfiava il campione → il gate [44] falliva → daily rosso, sito
  fermo (rumoroso, ma visibile);
* dopo: la gara viene semplicemente esclusa → il gate passa, e per un run il campione
  pubblicato è **corto di una gara** senza che nessuno lo dica.

Un errore che non si vede non è un errore risolto: è un errore discreto. Ho aggiunto la misura:

* `allineamento_fonti(store)` (`analysis.py`) conta le due code — gare finite nel calendario
  senza xG, e gare con xG non ancora finite nel calendario — oltre al campione pubblicato;
* i quattro numeri sono pubblicati in una **card nuova di `stato.html`** («Allineamento
  calendario / dettaglio gare»): quando le due code sono a zero la pagina lo dice, quando non lo
  sono dice quante gare restano fuori e perché;
* test `test_allineamento_fonti_dice_chi_resta_fuori_dal_campione`: il caso disallineato
  (1 campione, 1 senza xG, 1 avanti), il caso allineato (3/3/0/0) e lo store vuoto (zeri, mai un
  crash in pagina).

Corretta anche una parola francese rimasta nel docstring del test di PR #100 («``match_info``
**disait**» → «diceva»).

## 6. Cosa **non** ho toccato

La **causa a monte**: la cache HTTP che fa vedere due stati diversi a due fasi dello stesso run.
Non si riproduce a comando (oggi le fonti sono allineate), e intervenire sul collect significa
cambiare il modo in cui il daily scrive lo stato delle gare — una modifica di pipeline, non un
bugfix. La misura di §5 serve esattamente a questo: la prossima volta che succede si **vede**
(subito, in pagina) invece di essere dedotto da un daily rosso o, peggio, da niente.

Non è stata fatta nessuna raccolta sportiva per scrivere questo documento: solo letture dei
Parquet versionati, `gh` su run/issue/pull request già esistenti e la ricostruzione del caso.

## 7. Gate dopo la modifica

| Gate | Esito |
|---|---|
| `pytest -q` | **585 passed** (584 + 1 nuovo: `test_allineamento_fonti_…`) |
| `ruff check src tests scripts` | pulito |
| `verify_site --site site` | **210.926 controlli · 0 problemi** |
| `resa_375` | **27.676 misure · 0 problemi** |
| `parita_schede` | **89 schede · nessuna differenza** |
