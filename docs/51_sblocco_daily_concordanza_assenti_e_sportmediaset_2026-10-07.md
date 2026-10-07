# 51 — Sblocco daily: concordanza singolare in «Fattori chiave» e rimozione Sportmediaset 404

**Data:** 2026-10-07 · **Sessione:** `arena/50d6af8a-football-deep-analyzer` · **Richiesta utente:**
«Controlla tutto il sito ed il progetto su hit hub,vedi se ci sono errori,controlla quello che abbiamo fatto e le cose in sospeso.infine miglioriamo le cose che non funzionano bene.procedi»

Tutto ciò che segue è **misurato in questa sessione** con comandi eseguiti direttamente nel repository.

---

## 0. Verdetto in sintesi

1. **Stato su GitHub:** la issue **#79** è ancora aperta («🚨 Fallimento run giornaliero (daily)»). Subito dopo il merge della PR #80 (`f5a16f0`), il run **#216** su `main` è fallito al passo `verify_site`:
   ```
   PROBLEMI (1): {'concordanza': 1}
     - partite/5749692.html: concordanza '1 assenti'
   ```
   Il fix della PR #80 ha risolto il decimale in `stato.html`, ma la comparsa di una nuova distinta con un solo indisponibile titolare (Como–Roma, match 5749692) ha attivato un secondo blocco di concordanza in `fattori_chiave`. Di conseguenza, il commit dei dati e il deploy su Pages sono rimasti bloccati.
2. **Causa radice:** in `src/fda/site/analysis.py`, `MatchAnalysis.fattori_chiave()` (righe 1618–1621) formattava `f"{ab['n']} assenti"` hardcodando il plurale su `home`, `away` e `impact`. Con `ab['n'] == 1` la pagina stampava `1 assenti`, intercettata dalla regex `AGREEMENT` del verificatore. Nella stessa funzione, `f"{rest} giorni"` generava `1 giorni` in caso di riposo di un solo giorno.
3. **Correzione applicata:**
   - Adottato `it_plural(ab["n"], "assente")` per `home`, `away` e fallback `impact`.
   - Adottato `it_plural(rest, "giorno")` per `delta` e `desc` nella card di riposo.
   - Adottato `it_plural(starters, "titolare", "titolari")` per i titolari fuori.
   - Rimosso il feed morto di **Sportmediaset** da `ITALIAN_DIRECT_FEEDS` in `src/fda/sources/news.py` (in HTTP 404 permanente dal 17/09, aperto da `docs/25` §5 e `docs/41` §4): restano ANSA e Sky Sport, eliminando il traceback di errore dai log di raccolta.
   - Aggiunto test di regressione dedicato in `tests/test_panchina_notizie.py` che valida l'assenza di violazioni tramite la regex `AGREEMENT`.

Suite: **509 passed** (era 508; +1 nuovo test). Gate: `verify_site` **0 problemi · 156.895 controlli**, `parita_schede` exit 0, `resa_375` **0 problemi · 25.921 misure**.

---

## 1. Diagnosi del fallimento in GitHub Actions (Run #216)

Subito dopo il merge della PR #80, Actions ha avviato il run #216 sul commit `f5a16f0`.
Dall'estratto automatico del log pubblicato sulla issue #79:

```
#### Log `verify.log`
[25] conversione grandi occasioni verificata: 336 pagine
[26] card mercato riconciliate: 66 pagine
PROBLEMI (1): {'concordanza': 1}
  - partite/5749692.html: concordanza '1 assenti'
```

### Perché è accaduto su `partite/5749692.html`
Il match 5749692 è Como–Roma (in programma l'11/10/2026). Durante il run, `fda collect` ha scaricato la distinta aggiornata da FotMob: la Roma presenta 1 giocatore indisponibile con ruolo titolare abituale (`ab['n'] == 1`, `starters_out >= 1`).

In `MatchAnalysis.fattori_chiave()`:
```python
if ab["n"] >= 2 or starters >= 1 or lost >= 0.4:
    tone = "bad" if side == "home" else "good"
    fattori.append({
        "icon": "🏥",
        "label": f"Infermeria {tname}",
        "home": f"{ab['n']} assenti" if side=="home" else "—",
        "away": f"{ab['n']} assenti" if side=="away" else "—",
        ...
```
Con `ab['n'] == 1`, veniva generata la stringa `"1 assenti"`.
Il gate `verify_site` verifica tutto il testo leggibile tramite:
```python
AGREEMENT = re.compile(
    r"(?<![\d,])\b1 (rossi|gialli|rigori|gare|partite|vittorie|pareggi|tiri|giorni|precedenti|"
    r"punti|titolari|assenti|sconfitte|anni|mesi|settimane|squadre|incontri|titoli|fatti|"
    r"giocatori|campionati|cartellini|allenatori)\b")
```
Rilevando `'1 assenti'`, il verificatore è uscito con exit code 1, bloccando il commit dei dati e il deploy su Pages.

Nella stessa sezione, per il riposo (`Riposo <squadra>`):
```python
"delta": f"{rest} giorni",
"desc": f"{tname} gioca dopo {rest} giorni — riposo corto..."
```
Se `rest == 1` (gara ravvicinata con 1 giorno di riposo), generava `"1 giorni"`, anch'esso vietato da `AGREEMENT`.

---

## 2. Pulizia feed RSS Sportmediaset (HTTP 404 permanente)

Nei log di `fda.collect` di tutti i run recenti compariva sistematicamente:
```
ERROR fda.collect: news direct Sportmediaset: SourceError: HTTP 404 https://www.sportmediaset.mediaset.it/rss/calcio.xml
```
Questo problema era già documentato in:
- `docs/25_revisione_lingua_e_parita_2026-09-17.md` §5 e §7.2: *«se il 404 continua, il feed va sostituito o tolto; oggi restano ANSA e Sky Sport»*.
- `docs/41_verifica_autoaggiornamento_e_coda_2026-09-19.md` §2.

A distanza di 3 settimane il server Mediaset continua a rispondere 404 poiché la vecchia rotta RSS è stata dismessa.
Rimuovendo `("Sportmediaset", ...)` da `ITALIAN_DIRECT_FEEDS` in `src/fda/sources/news.py`:
- Restano attivi i due feed affidabili: ANSA e Sky Sport.
- I log di raccolta tornano puliti, senza eccezioni né allarmi ingiustificati.
- Aggiornato l'assert in `tests/test_diagnostica_fonti.py` (le richieste notizie scendono da 5 a 4: 2 ricerche Google + 2 feed diretti).

---

## 3. Riepilogo Gate ed Esecuzioni Locali

| Verifica | Esito | Note |
|---|---|---|
| `pytest -q` | **509 passed in 89s** | era 508 passed; +1 test di regressione concordanza `test_fattori_chiave_concordanza_singolare` |
| `fda build` | **exit 0** | 441 schede · 2.364 partite · 7.158 giocatori |
| `scripts/verify_site.py` | **0 problemi · 156.895 controlli** | superato su tutte le 4.036 pagine |
| `scripts/parita_schede.py site` | **exit 0** | 66 schede pre-partita: 23 sezioni, 13 voci indice |
| `python -m scripts.resa_375` | **0 problemi · 25.921 misure** | tabelle e grafici perfetti a 375 px |
| `ruff check` | **pulito sul nuovo codice** | corretta anche stringa `f"RPS 0,20 tipico"` priva di interpolazioni |
| Live Preview | **Attiva su porta 3000** | servita con `start_process` (`python3 -m http.server 3000 --directory site`) |

---

## 4. Prossimi Passi

1. Eseguire il commit e push sul branch della sessione `arena/50d6af8a-football-deep-analyzer`.
2. Aprire la Pull Request verso `main`.
3. Notificare l'utente per il merge (secondo la policy di progetto `00_regole_di_lavoro.md` sez. D, il merge viene eseguito dall'utente).
4. Il primo run del workflow `daily` su `main` chiuderà in automatico la issue **#79**.
