# 42 — Cosa resta da fare: ricognizione misurata (2026-09-19)

**Domanda dell'utente:** *puoi esaminare cosa c'è ancora da fare?*
**Risposta breve:** la coda di `docs/41` §4 è **esaurita** (2 voci chiuse e in produzione, 2 in
attesa di una data); restano **3 voci P2 di `docs/19`**, **5 decisioni che spettano all'utente** e
**due appuntamenti con data** (lunedì 21/09 e 3/10). Tutto qui sotto è misurato in questo giro: i
gate sono stati rieseguiti e il sito ricostruito sui Parquet versionati a `HEAD` (`88ee2ae`).

---

## 1. Gate di questo giro (offline, sandbox)

| gate | esito |
|---|---|
| `pytest -q` | **475 passed in 78,0 s** (= baseline di `main`, nessun test nuovo in questo giro) |
| `ruff check .` | **All checks passed!** |
| `fda build` | exit 0 in **4m28s** — **375** schede · **2.364** partite · **7.498** giocatori; «calendario completo: **1.988** partite in 8 mesi (**0 senza previsione**)» |
| `scripts/verify_site.py` | **0 problemi · 150.587 controlli** (era 150.006 in `docs/39`: i totali dipendono dai dati, l'esito no) |
| `scripts/parita_schede.py site` | exit 0 — «nessuna differenza» fra le schede pre-partita |
| `python -m scripts.resa_375` | **23.674 misure · 0 problemi** a 375 px |
| `scripts/audit_match_sections.py` | exit 0 (divario max−min fra medie di lega: **2,9** righe, media 9,0) |

**Limite dichiarato:** il sito **pubblicato** non è raggiungibile dal sandbox
(`curl https://uamisjd.github.io/football-deep-analyzer/` → `000`, nessuna risposta). Le
verifiche «dal vivo» di questo giro vengono quindi solo da `gh api`/`gh run` (run, job, deploy),
come prescritto dalla regola B6 di `docs/00`.

---

## 2. La coda di `docs/41` §4, voce per voce (rimisurata oggi)

| # | voce | stato | misura di oggi |
|---|---|---|---|
| 1 | **Allerta quando il `daily` è rosso** | ✅ **in produzione** | PR **#63** fusa alle 17:49:54Z; run `35459538821` **success**: passo *«Segnala ripristino (chiude eventuale issue di guasto aperta)»* = **success**, passo *«Segnala fallimento (apre o aggiorna issue di guasto)»* = **skipped** (corretto: nessun guasto). Permessi `issues: write` presenti in `daily.yml:44` |
| 1b | **…ma il ramo di guasto non è mai stato esercitato** | 🔶 **aperto** | `gh issue list --state all` → **0 issue**: il passo `on-failure` è coperto da 13 unit test e da `--dry-run`, non da un run rosso reale. La condizione è `failure() && github.ref_name == default_branch`, quindi **non è riproducibile da un branch**: senza un guasto vero o un dispatch che fallisca di proposito resta non verificato dal vivo |
| 2 | **Feed Sportmediaset 404** | ✅ **chiuso e verificato in produzione** | run `35457599586` → commit `f111b95`: riga `news:NEWS` **AVVISO**, **0** righe ERRORE su 37 |
| 3 | **Prima sonda dei fallback** | ⏳ **lunedì 21/09, 03:30 UTC** (≈33 h da ora) | `data/processed/source_probe.parquet` **non esiste**; il passo c'è in `lab.yml:107-134`; ultimo run del `lab` **14/09** (5 giorni fa), cron `30 3 * * 1` |
| 4 | **Primo `benchmark.yml`** | ⏳ **3/10** | `gh run list --workflow benchmark.yml` → **nessun run**; cron `20 4 3 * *`, file nato il 16/09 → non è un guasto, è una data non ancora raggiunta |
| 5-6 | Archiviazione `STATO.md`, test contatori a 1 | ✅ fatti (`docs/41` §3.8-§3.9) | — |
| 7 | Ritardo dei cron (media 3,12 h) | **decisione dell'utente** | non è un difetto nostro: è il ritardo con cui GitHub avvia i run schedulati |

---

## 3. Il laboratorio ha due run di ritardo rispetto al codice

`model_lab.parquet` (21.952 byte, **176 righe** = 22 candidati × 8 chiavi) contiene l'ultimo
walk-forward del **14/09**:

- **mancano i candidati aggiunti il 18/09** da PR #56 — `gamma_112`, `gamma_124` (P2.9) e
  `tau_090`/`tau_110`/`tau_120` (P2.10, temperatura 1X2): ci sono nel codice (`lab.py:124-149`), non
  ancora nei dati;
- **mancano le colonne `grid_dichiarata` e `n_tentativi`** (regola P1.11): lo schema attuale ha 24
  colonne e non le prevede, perché nessun run le ha ancora scritte;
- il confronto di riferimento oggi è `dc_elo_tilt` ΔRPS **−0,000408** IC95
  **[−0,000770; −0,000045]**, `migliore_in` 0,57 su 1.528 gare.

**Primo run utile: lunedì 21/09 03:30 UTC**, lo stesso della sonda dei fallback. Da fare quel
giorno: leggere `scripts/verdetto_lab.py` e applicare il protocollo (promozione **solo** con IC 95%
interamente negativo e vantaggio in **≥5 leghe su 7**).

---

## 4. Cosa resta della coda P1/P2 di `docs/19` §4 (ricontrollata sul codice, non sui documenti)

**Chiuse (verificate nel codice o nel sito, non per deduzione):** P1.12 (claim ridotto in
`info.html`), P1.15, P2.1/P2.2 (CSS e colori), P2.3 (font auto-ospitati: 9 woff2 + `fonts.css`
12.140 byte, **0** URL `https://` nei fogli di stile pubblicati), P2.5, P2.6, **P2.8 layout**
(resa a 375 px, `docs/39`), **P2.9** (γ-sharpening respinto, tenuto in `lab.py` «perché il verdetto
sia riproducibile»), **P2.10** (candidati di temperatura, griglia pre-registrata simmetrica attorno
a 1,00).

**Ancora aperte:**

| # | voce | misura di oggi |
|---|---|---|
| **P2.7** | Paginazione/lazy-loading di `prossime.html` | la soglia dichiarata in `docs/19` («se il calendario cresce oltre ~250 card») è **superata di ~5×**: **1.362** righe-calendario in **8** mesi (`<details class="cal-month">` da 2026-09 a 2027-05) dentro una pagina di **1.287 kB** — la più pesante del sito, 42× la media (30,6 kB) |
| **P2.4** | Riscrittura delle 3 frasi-macchina di `narrative()` | da verificare: le tre forme censite nel 2026-09-14 non compaiono nelle schede ricostruite oggi (grep su `partite/*.html` → 0 occorrenze). Serve rileggere `narrative()` prima di dichiararla chiusa o aperta |
| **P2.8** | Lighthouse (accessibilità/performance/best practice) | **fuori portata dal sandbox**: serve un runner con Chrome (regola B6) |

---

## 5. Verifiche nuove di questo giro (sito ricostruito: 4.140 pagine, 126,6 MB di HTML)

Nessuno di questi controlli era in un documento: sono stati fatti sul sito appena generato.

- **Link interni: 0 rotti.** 4.250 URL distinti, **112.884** occorrenze, percorsi risolti rispetto
  alla directory di ogni pagina → **0** mancanti.
- **Sitemap onesta.** **4.139** URL, tutte con file corrispondente; fuori dalla sitemap solo
  `404.html` (giusto) e la radice `/` (presente come URL base).
- **Igiene HTML: 100%.** Su 4.140 pagine: 0 senza `<title>`, 0 senza `<h1>`, 0 con più di un
  `<h1>`, 0 senza meta description, 0 senza attributo `lang`.
- **CSS esterno confermato (P0.5 chiuso, non solo annunciato).** **0** blocchi `<style>` inline su
  4.140 pagine (0 byte); `assets/site.css` **48.043** byte, `assets/fonts/fonts.css` **12.140**
  byte, 9 woff2.
- **Peso.** Media 30,6 kB/pagina; pagine più pesanti: `prossime.html` **1.287 kB**,
  `risultati.html` 382 kB, `giocatori/ESP1.html` 232 kB. Scheda partita tipo: 101 kB
  (tabelle 38%, SVG 5%, script 2%).
- **Dati versionati a `HEAD`.** `predictions` 2.152 righe con `made_at` massimo **18:02:15Z** di
  oggi; `fixtures` 2.364; `history` 7.423; `news` 16.941; `source_status` 3.042 (storico
  cumulativo, non il solo ultimo run).

---

## 6. Decisioni che restano all'utente (l'agente non le prende)

1. **Ritardo dei cron** (media 3,12 h): più cron o accettare il ritardo dichiarato in testa alla
   pagina.
2. **Tappa 2** — schede anche per le gare lontane (`docs/13` §9.5).
3. **Traduzione del materiale straniero** (`docs/25` §7.1): oggi si scarta, non si traduce.
4. **Lighthouse** (`docs/19` P2.8): serve un runner con browser.
5. **Roadmap**: fase 3b (anagrafica giocatori da `playerData`) e fase 5 (Telegram).

---

## 7. Cosa si può fare **ora**, in ordine di utilità misurata

1. **Esercitare dal vivo il ramo di guasto dell'allerta** (§2, voce 1b): è l'unico presidio nuovo
   del progetto che non ha ancora una prova reale. Strada possibile senza danni: aggiungere a
   `daily.yml` un input `workflow_dispatch` «prova allerta» che fa fallire **solo** un passo
   finale (dopo il commit dei dati e la preparazione di Pages, così il sito non si tocca),
   verificare che la issue si apra, poi chiuderla con il run verde successivo. Costo: ~17 minuti
   di runner e una issue di prova.
2. **P2.7 — alleggerire `prossime.html`** (1.287 kB, 1.362 righe): `content-visibility` per mese
   o paginazione per giorno. Misurabile offline con `resa_375` e `verify_site`, non cambia una
   parola dei contenuti.
3. **Nuovo audit mirato** su un'area non ancora passata al setaccio: le schede giocatore
   (`giocatori/`: 7 tabelloni + **7.498** schede) o la pagina *Accuratezza* o *Stagione*. È il
   modo con cui il progetto ha trovato finora ogni difetto sostanziale.
4. **Attendere lunedì 21/09** e leggere, nello stesso run del `lab`, la **prima sonda dei
   fallback** e il **primo verdetto del laboratorio con la griglia pre-registrata**.

---

## 8. Prossimo passo

La coda documentata è vuota fino a lunedì: la scelta del lavoro di questa sessione spetta
all'utente fra le quattro voci del §7. In assenza di indicazioni, la prima (**prova dal vivo
dell'allerta**) è l'unica che chiude una casella oggi aperta; la seconda (P2.7) è l'unica con un
difetto misurato alle spalle.
