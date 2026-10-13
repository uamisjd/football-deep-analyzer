# 99 — Issue #109: diagnosi completa post-blocco e correzione dei due errori del `daily` (2026-10-13)

L'utente apre una nuova sessione dopo il blocco della chat precedente e chiede:
1. **verifica a 360° («vita, morte e miracoli»)** di dove siamo rimasti nel repository, nelle PR e in produzione;
2. **indagine e correzione** dei due problemi che hanno fatto fallire `verify_site` nel run `daily` su `main`:
   - `laboratorio.html: concordanza '1 campionati'`
   - `5749705.html: «letture sul tema» di Juventus stampa 0, i dati dicono 1`

---

## §1 — Ricostruzione completa dello stato («vita, morte e miracoli»)

### 1.1 Che cosa è salvato in Git e nella PR #108
- Il ramo della sessione precedente (`arena/8d89284f-football-deep-analyzer`, **21 commit**) è stato **unito dall'utente in `main`** il **13/10/2026 alle 10:11:42 UTC** (merge commit `6a0034c`, **PR #108**).
- Nessun commit è rimasto orfano sul ramo `arena/8d89284f-football-deep-analyzer` (la punta del ramo è `ce5d766`, interamente inclusa in `6a0034c`).
- Cosa è entrato in `main` con la PR #108:
  1. **Verifica post-merge PR #107 (`docs/91`):** storico Understat 2021–2025 completo (**8.908** gare finite, **17.816** lati-squadra, 0 difetti in `scripts/audit_understat_storico.py`) e avvio del test prospettico γ 1,12 (**3.856 righe / 1.928 coppie** pre-partita, con guardia anti-riscrittura post-kickoff).
  2. **Punto 3 — candidato `dc_xg` preregistrato e misurato (`docs/92`–`docs/93`, `fda lab-xg`):** 5.058 gare appaiate (4.810 con xG Understat + 248 fallback NED1/POR1), **ΔRPS −0,000393, IC 95% [−0,001109; +0,000332], migliore in 3/7 leghe** → criterio di promozione (IC < 0 e ≥5/7 leghe) **non superato**, ricetta di produzione invariata.
  3. **Punto 4 — revisione delle 6 sezioni della scheda partita (prime 3 affrontate):**
     - **Sezione 1 — Panchina e posta in gioco (`docs/94`):** corrette 7 celle (5 false salvezze a pari punti, 2 distanze dalla salvezza diretta nei campionati a 18 dove il riferimento è il 15º posto e non il 16º dello spareggio), precisione Monte Carlo letta dal metadato `N`, audit `scripts/audit_panchina.py` e invariante `[19]` allineati.
     - **Sezione 2 — Mercato (`docs/95`):** incrocio degli arrivi in distinta sull'intera finestra (96 corrispondenze trovate contro 35 quando si guardavano solo i primi 4 nomi), tendina per gli arrivi oltre i primi 4, separazione rigorosa fra importi noti, gratuiti e prestiti senza cifra, `scripts/audit_mercato.py` (1.008/928 controlli, 0 difetti).
     - **Sezione 3 — Vita del club (`docs/96`, `docs/97`, `docs/98`):**
       - `docs/96`: determinismo dell'imbuto, date esplicite della finestra pre-partita, contatori separati per categoria/capienza, oracolo indipendente `src/fda/site/club_news_checks.py`.
       - `docs/97`: riapertura critica per qualità editoriale e copertura; eliminata la collisione lessicale `Idrissa`/`rissa` (confini di parola); introdotto il selettore positivo `src/fda/site/club_signals.py` (`Evento segnalato` vs `Analisi / dichiarazione`), il raggruppamento prudente `letture sul tema` e la dichiarazione esplicita dei vuoti di copertura (5 leghe su 7 ancora a zero voci selezionate).
       - `docs/98`: avviato lo studio dei falsi negativi/positivi di `is_italian_news` su un benchmark congelato di **149 casi** (`tests/fixtures/news_language_review_2026-10-13.json`); documentati e scartati i candidati V1 e V2 per regressioni sul corpus reale, e dichiarata la variante conservativa V3 (`ce5d766`) poco prima del blocco della chat (il rilevatore `Lingua` su tutte le lingue carica ~909 MiB in RAM). `src/fda/sources/news.py` non era ancora stato modificato.

### 1.2 Stato dei workflow GitHub Actions su `main` e issue #109
- Il workflow `tests` sul merge `6a0034c` (`38381687220`) è **verde** (`success` in 2m07s).
- Il workflow `daily` su `main` è **rosso** da 5 esecuzioni consecutive (issue automatica **#109** aperta dal run #257 del 12/10 alle 19:44 UTC):
  - **Run #257–#260** (su `514309d`, prima del merge #108): falliti al passo 11 (`verify_site`) con **1 problema**: `laboratorio.html: concordanza '1 campionati'`.
  - **Run #261** (`38381687223`, sul merge `6a0034c` di PR #108): raccolta dati, modelli, backtest, simulazioni e `fda build` tutti riusciti (`0 errori`), poi passo 11 (`verify_site`) fallito con **2 problemi**:
    1. `laboratorio.html: concordanza '1 campionati'`
    2. `5749705.html: «letture sul tema» di Juventus stampa 0, i dati dicono 1`
- Poiché `verify_site` blocca il job prima del commit dei dati e del deploy Pages, i Parquet in `main` sono fermi allo snapshot `514309d` (ma la cache HTTP di Actions è stata salvata a ogni run).

---

## §2 — Diagnosi esatta dei due problemi di `verify_site`

### 2.1 Problema 1: `laboratorio.html: concordanza '1 campionati'`
- **Causa:** in `src/fda/site/templates/laboratorio.html` (riga 52, aggiunta con il test prospettico in PR #107), il riepilogo del test prospettico stampava:
  ```jinja2
  migliore in {{ prosp.leagues_better }} campionati su {{ prosp.n_leagues }}.
  ```
  Finché nello snapshot locale nessuna partita registrata in `prospettico.parquet` era ancora terminata (`prosp.n == 0`), il ramo `{% if prosp and prosp.n %}` non veniva eseguito. La sera del 12/10 (run #257), con le prime gare concluse in produzione, `prosp.leagues_better` è diventato `1` e la pagina ha stampato `migliore in 1 campionati`, intercettato dall'invariante `[13-14]` (`AGREEMENT`).
- **Correzione:** usato il filtro `{{ prosp.leagues_better|it_plural('campionato', 'campionati') }}` nella riga 52 (e concordato anche il singolare `{{ 'supera' if lab.n_passes == 1 else 'superano' }}` / `{{ 'migliore' if lab.n_passes == 1 else 'migliori' }}` alla riga 12).

### 2.2 Problema 2: `5749705.html: «letture sul tema» di Juventus stampa 0, i dati dicono 1`
- **Causa:** in `src/fda/site/templates/match.html` (riga 611, introdotta in PR #108 / `docs/97`), il contatore finale dell'imbuto per squadra è racchiuso in `<b>...</b>` (come `in riserva`):
  ```jinja2
  {% if nw.correlate %} · <b>{{ nw.correlate }} letture sul tema</b>{% endif %}
  ```
  Mentre l'oracolo indipendente `src/fda/site/club_news_checks.py` legge `header.get_text(" ", strip=True)` (che rimuove i tag HTML, e infatti nel run #261 ha superato tutti gli **864 controlli indipendenti** senza errori), il controllo `[20]` in `scripts/verify_site.py` (riga 3212) cerca le espressioni regolari direttamente sull'HTML grezzo `head = blocco.split("<ul", 1)[0]`.
  La regex `r"· (\d+) letture sul tema"` non prevedeva il tag `<b>` dopo `· ` (a differenza di `r"<b>(\d+) in riserva</b>"` nove righe più sotto): quindi, non appena la raccolta live del run #261 ha trovato per Juventus (`5749705.html`, Juventus–Lazio) `1` lettura correlata nella finestra di 7 giorni (`atteso["correlate"] == 1`), `re.search` ha restituito `None` (`stampato = 0`) contro `valore = 1`.
  Nello snapshot locale del 13/10 il difetto era rimasto latente perché sulle 58 schede pre-partita correnti `correlate` valeva `0` ovunque (`0 == 0`).
  Inoltre, per `nw.correlate == 1`, la riga 611 stampava il plurale `1 letture sul tema` anziché il singolare `1 lettura sul tema` (già usato invece nelle righe 612–613).
- **Correzione:**
  1. In `src/fda/site/templates/match.html` (riga 611): concordato `{{ nw.correlate }} {{ 'lettura sul tema' if nw.correlate == 1 else 'letture sul tema' }}`.
  2. In `scripts/verify_site.py` (riga 3212): aggiornata la regex a `r"· (?:<b>)?(\d+) lettur[ae] sul tema"`.
  3. In `src/fda/site/club_news_checks.py` (riga 146): aggiornata la regex a `r"· (\d+) lettur[ae] sul tema"`.
  4. In `scripts/verify_site.py` (`AGREEMENT`, riga 303): aggiunto `letture` alla lista dei plurali vietati dopo `1`, così anche `[13-14]` presidia `1 letture`.

---

## §3 — Test di regressione e gate verificati

- Aggiunti test di regressione dedicati:
  - `tests/test_lab_page.py::test_pagina_laboratorio_concordanza_singolare_prospettico`
  - `tests/test_vita_editorial.py::test_letture_sul_tema_in_grassetto_e_concordate_per_verify_site`
- **Gate completi eseguiti e verdi:**
  - `pytest`: **922 passati** (0 falliti)
  - `ruff check .`: **All checks passed!**
  - `fda build`: **493 schede / 2.364 fixture / 7.594 giocatori**
  - `verify_site`: **238.235 controlli · 0 problemi**
  - `parita_schede`: **58 schede pre-partita · nessuna differenza**
  - `resa_375`: **28.504 misure · 0 problemi a 375 px**
  - Audit di sezione: `audit_vita_club` (**840 controlli · 0 difetti**), `audit_mercato` (**928 controlli · 0 difetti**), `audit_panchina` (**0 difetti**).

---

## Prossimo passo

1. **Sblocco immediato di `main` (regola D.2):** aprire la PR da `arena/079933b1-football-deep-analyzer` verso `main` affinché il fix entri in produzione, il prossimo `daily` torni verde e l'issue **#109** si chiuda in automatico.
2. **Coda lavori aperta dopo lo sblocco:**
   - **Vita del club (`docs/97`–`docs/98`):** completare la misura della variante linguistica conservativa V3 (in un processo leggero senza saturare la RAM) e il tema della copertura delle 5 leghe estere.
   - **Ultime 3 sezioni del punto 4:** *Previsione ensemble*, *Precedenti*, *Verifica approfondita*.
   - **Decisioni utente sempre aperte:** perimetro storico StatsBomb/Understat e conferma card Clima basata su regole.
