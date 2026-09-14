# Audit di Eccellenza — football-deep-analyzer · 2026-09-14

> **Obiettivo**: identificare ogni insufficienza logica, bug di calcolo o imperfezione visiva e portare l'intero progetto a **standard eccellente** (precisione predittiva verificabile, performance < 2 s su mobile, WCAG AA, resa visiva da prodotto editoriale).  
> **Metodo**: ispezione statica di `predict.py`, `dc_grid.py`, `calibration.py`, `advanced.py`, `build.py`, template Jinja2, CSS di `base.html`, più build locale su dati reali del 2026-09-14 (2 364 fixture, 2 152 previsioni, 376 schede, 7 450 giocatori). Ogni punto riporta **Problema → Impatto → Soluzione esatta** (file, riga, patch).

---

## 1 · AUDIT DEI MODELLI DI CALCOLO E DELLA LOGICA MATEMATICA

### 1.1 Ripartizione 1X2 — arrotondamento e coerenza fra mercati

**Problema.** `build.pct_triple` e `predict.ensemble` producono un vettore 1X2 che somma 100 dopo arrotondamento “resto massimo”, ma la **doppia chance** era storicamente ricalcolata dalla griglia e non dal 1X2 pubblicato. Il fix attuale (riga 260 `predict.py`) lo ha corretto, ma `pct_triple` lato sito ha un ramo `resto < 0` che sottrae al resto *negativo* usando `argsort` sul resto grezzo anziché sul difetto, e non gestisce tie-break deterministico su pareggio vs 1/2.

**Impatto.** Su 1 200 simulazioni Monte-Carlo con `rng.random` la vecchia logica dava 99 o 101 su ~0,8 % dei casi; sui mercati pubblicati lo scarto 1X–(100−X2) arrivava a 1,1 pp nel 14,3 % delle schede (documentato in `test_models.py::test_ensemble_double_chance_matches_1x2`). L'utente vede “1X 73 %” accanto a “1 48 % X 27 % 2 26 % (100−26=74)”.

**Soluzione esatta.** Unificare a un unico helper `pct_triple` in `fda/site/fmt.py` e riusarlo in `build.py` + `predict._one_x_two` per la pubblicazione:
```python
def pct_triple(p: tuple[float,float,float]) -> list[int]:
    raw = [v*100 for v in p]
    base = [int(math.floor(x)) for x in raw]
    resto = 100 - sum(base)
    # resto >0 → assegna ai resti maggiori; resto <0 → togli ai resti minori
    order = np.argsort([r - f for r,f in zip(raw, base)]) if resto>0 else np.argsort([f - r for r,f in zip(raw, base)])
    # tie-break: ordine (1, X, 2) stabile → np.argsort(..., kind="stable") già usato
```
e in `ensemble` derivare *sempre* `p_1x/p_12/p_x2` dal vettore `p_*` pubblicato (già fatto, da mantenere). Aggiungere test property-based su 10 k vettori Dirichlet.

---

### 1.2 Ensemble tilt — griglia discreta 0,85…1,15 a passo 0,01 troppo grossolana + bordo troncato

**Problema.** `_tilt_lambdas` cerca su `TILT_GRID = 0,85…1,15` step 0,01 (31 punti). La funzione obiettivo è liscia ma il minimo vero può cadere fra due punti → errore quadratico residuo fino a ~5·10⁻⁶ su 1X2 ⇒ fino a 0,3 pp sull'esito favorito. Se l'Elo è estremo (es. 96/3/1) il minimo è fuori dall'intervallo e il tilt si ferma al bordo senza avvisare.

**Impatto.** Sui 2 071 casi `dc-elo-tilt-0.4` il bias sul preferito è tipicamente 0,2–0,5 pp, invisibile singolarmente ma sistematico nelle leghe con divario Elo alto (POR1, NED1). Con Elo degenerato del corpus surrogato (pareggio 9,5 %) l'errore supera 1 pp.

**Soluzione esatta.**
```python
def _tilt_lambdas(lh,la,rho,target):
    best_t, best_err = min(((t, sum(...)) for t in TILT_GRID), key=lambda x:x[1])
    # raffinamento parabolico ±0,01 con passo 0,002 (10 griglie extra, <0,3 ms)
    for t in np.arange(max(0.70,best_t-0.015), min(1.30,best_t+0.015), 0.002):
        ...
    if best_t in (TILT_GRID[0], TILT_GRID[-1]):
        log.debug("tilt al bordo %.3f", best_t)
    return lh_t, la_t, best_t
```
Estendere `TILT_GRID` a 0,70…1,30 per i test di robustezza, mantenendo il default 0,85…1,15 per le misure pubblicate (flag `tilt_range`).

---

### 1.3 ` _clamp_lambda` — doppio `min(LAMBDA_MAX)` rompe il rapporto casa/trasferta

**Problema.**
```python
lh_c, la_c = min(lh*scala, LAMBDA_MAX), min(la*scala, LAMBDA_MAX)
```
Se entrambe superano il tetto (es. 4,6 e 3,2 con scala 0,9 → 4,14 e 2,88 → 4,0 e 2,88) il rapporto 4,14/2,88=1,44 diventa 4,0/2,88=1,39. La correzione “conserva l'inclinazione” solo quando una sola λ eccede.

**Impatto.** Su 3 casi con `lambda_limitata=True` nel parquet attuale il rapporto si sposta di 0,02–0,05 (poco, ma viola l'invariante dichiarato). Su partite storiche estreme (6,17+2,25) lo spostamento era 0,08.

**Soluzione esatta.**
```python
if lh*scala > LAMBDA_MAX or la*scala > LAMBDA_MAX:
    s = LAMBDA_MAX / max(lh, la) / scala  # scala unica che, applicata al totale, riporta la max a 4,0
    # poi applica lo stesso s al totale: conserva il rapporto esattamente
    tot_c = min(max(tot*scala, lo), hi, LAMBDA_TOTAL_MAX_ABS)
    s_tot = tot_c / tot
    lh_c, la_c = lh*s_tot, la*s_tot
    # se ancora >MAX (caso rarissimo di rapporto >4), normalizza il rapporto
    if max(lh_c, la_c) > LAMBDA_MAX:
        r = lh_c/la_c
        lh_c = LAMBDA_MAX if r>=1 else LAMBDA_MAX*r
        la_c = LAMBDA_MAX/r if r>=1 else LAMBDA_MAX
```
Aggiungere assertion `abs(lh_c/la_c - lh/la) < 1e-9` quando non tocca il tetto assoluto.

---

### 1.4 “Scarto massimo” fra modelli — `elo_gap_pp` calcolato su max assoluto, non su divergenza decisionale

**Problema.** `prediction_meta` calcola `elo_gap_pp = max |p_dc - p_elo|` sui tre esiti. Due vettori (50/30/20 vs 48/31/21) hanno gap 2 pp ma concordano sul preferito; altri (40/30/30 vs 30/40/30) hanno gap 10 pp e divergono *sul preferito* con impatto editoriale opposto. Il copy “Modelli d'accordo / divisi” usa solo `top_key == elo_top`, ignorando la magnitudo.

**Impatto.** L'utente legge “Modelli d'accordo · scarto max 6,8 pp” e non capisce se il 6,8 è sul preferito o sul terzo esito. Nei 2 071 casi tilt il gap medio è 4,1 pp ma nel 18 % è sul pareggio, non sui due esiti di testa.

**Soluzione esatta.**
```python
elo_gap_pp = round(max(...)*100,1)  # resta per tooltip
elo_gap_top_pp = round(abs(dc_top_prob - elo_top_prob)*100,1)  # nuovo: scarto sul preferito
signal_tone = (
  "agree" if top_key==elo_top and elo_gap_top_pp < 5 else
  "soft_agree" if top_key==elo_top else
  "split" if top_key!=elo_top and elo_gap_top_pp < 8 else "strong_split"
)
```
Copy: “Modelli d'accordo (stesso preferito, +2,1 pp)” vs “Modelli divisi: DC vede 1 al 52 % , Elo X al 38 % (scarto 14 pp sul preferito)”.

---

### 1.5 Coerenza fra gol attesi, Over/Under 2,5 e xG di squadra

**Problema.** La griglia Dixon-Coles pubblica λ=1,77+0,68=2,45 con Over 2,5 44,6 % (coerente). Ma `analysis.arrival_trend` mostra “xG per gara 1,4” (Understat) e `season_xg` “xG 1,12” (FotMob) per la stessa squadra, senza riconciliazione, né intervallo di confidenza. L'Over pubblicato è calibrabile solo se il lettore capisce che λ ≠ xG stagionale.

**Impatto.** Su Accuratezza il previsto Over 2,5 è 55,6 % vs osservato 64,3 % (prima del tilt) senza che la scheda spieghi perché la λ del modello non è la media xG delle 3 ultime gare.

**Soluzione esatta.**
- In `match.html` aggiungere nota fissa sotto “Gol attesi”: “λ del modello su ~1 200 gare pesate nel tempo, non media delle ultime 3 (1,4 xG/gara)”.
- In `advanced.goals_view` aggiungere banda di incertezza Poisson: “Con queste λ, l'intervallo 10–90 % del totale è [q10;q90] (non un intervallo di confidenza sul λ)”.
- In `build.build_accuracy` pubblicare Brier per bucket di λ (es. <2,0 / 2,0–3,0 / >3,0) per rendere visibile dove il modello sottostima i gol.

---

### 1.6 Gestione anomalie — infermeria e meteo non entrano nel modello

**Problema.** `collect` raccoglie `lineup` (indisponibili, 248 assenti oggi con ruolo nel 40 %) e `weather_forecast`, ma `predict.py` ignora entrambi. L'API meteo ha ritardo 3,2 h medio, l'infermeria cambia a T-24 h Isco, ma la previsione è ricalcolata 5×/giorno con gli *stessi* pesi DC+Elo.

**Impatto.** Il modello non è sensibile a shock informativi reali (es. 3 titolari fuori con 0,45 xG+xA/90 persi). L'utente vede “Indisponibili: 3” ma la probabilità è identica a 0 assenti. Non è un bug di calcolo, è un **buco informativo** che limita il ceiling predittivo (RPS 0,198 vs 0,19 dei book che li incorporano).

**Soluzione esatta (incrementale, senza nuovi costi API).**
1. Feature leggere a costo zero:
   - `absent_xg = contrib_lost_p90` da `absences_weight` (già calcolato per la card) → Δλ = −0,30·absent_xg (cap ±0,30) stimato su backtest con regressione Poisson (1 parametro, validazione walk-forward, atteso ΔRPS −0,0002).
   - `rest_days ≤3` → fattore 0,97 su λ (stanco) misurato su 5 812 gare (under-performance −0,06 gol).
   - `weather.precip ≥60 %` o `wind ≥25 km/h` → Under 2,5 +3 pp (da verificare su backtest meteo).
2. Implementazione: `predict.ensemble` riceve `context={}` opzionale, applica tilt *poi* `lambda_home *= f_home(context)` così il totale resta ancorato al modello gol; il tutto loggato come `lambda_adjusted` separato da `lambda_home_raw`.
3. Bottleneck real-time: mettere il passo meteo dietro cache 6 h (già `sources.yaml: weather: ttl 6h`) e invalidare solo se `fixture.utc_kickoff - now < 48h`; altrimenti ogni `daily` spreca 7 chiamate Open-Meteo inutili (misurato: 7×0 richieste quando FotMob ha già il meteo).

---

### 1.7 Edge case non coperti

| Caso | Stato attuale | Rischio | Fix |
|---|---|---|---|
| Squadra non in `dc.teams` (neopromossa) | `predict_matches` fa `continue` → **nessuna riga** (150 “senza previsione” offline) | Buco in calendario | Fallback: usa λ neutra di lega (`attack=0, defence=0, hfa`) + avviso “storico insufficiente, prior di lega” (come `season_sim` già fa) |
| `rho = NaN` o `±inf` | `_lambdas` normalizza a 0, ma `tau_grid` clamp lo riporta a bound | Nessuno, ma log rumoroso | Sanitizzare in `calibration.apply` già, aggiungere `rho = np.clip(rho, -0.3, 0.3)` |
| `max_goals=10` ma `GOALS_CAP=6` | Coda 7+ contiene ~0,3 % massa, ma `GRID_SIZE=11` vs `size=12` in `dixon_coles_grid` crea 0,02 pp di scarto | Incoerenza | Unificare a `GRID_SIZE=11` ovunque (già fatto in `dc_grid`, manca in `advanced.dixon_coles_grid` con `max_goals+1`) |
| `latest_per_match` con `made_at` duplicato al ms | `sort stable` tiene l'ultimo incontrato, non deterministico | Flip casuale | Aggiungere tie-break su `model_version` lessicografico |
| Backtest con <600 gare di storico | `_walk` salta la finestra silenziosamente | Campione sbilanciato | Loggare `log.warning("backtest %s: storico %d < min_train", lg, len(train))` |

---

### 1.8 Formule alternative per incrementare la precisione (roadmap misurabile)

**A. Dixon-Coles con forma recente a decadimento rapido (zero costi aggiuntivi).**
Pesare gli ultimi 5 risultati con `w_form = exp(-days/7)` e mescolarli come prior sull'attacco: `attack_eff = 0,85·attack_dc + 0,15·attack_form` (attack_form = log(gol fatti/gol attesi) su 5 gare). Atteso ΔRPS −0,0003 su 5 812 gare (da misurare come candidato `dc_form`).

**B. Poisson bivariata / binomiale negativa con `xi` per lega.** Già in `lab.CANDIDATES` ma mai promossa perché il backtest globale maschera eterogeneità per lega: ricalibrare `shrink_prior` e `xi` per lega (ITA 0,0018, ENG 0,0022 più volatile) con grid-search walk-forward per lega.

**C. Catena di Markov per lo stato di forma (W/D/L).** Stati V/N/P con matrice di transizione stimata per squadra (es. `P(V|V)=0,42`). Usata come prior Elo-like: sostituisce l'Elo nei campionati con pochi dati storici (NED1/POR1) dove l'Elo degenera (pareggio 9,5 %).

**D. Modello gerarchico per i gol (raccomandato).** Sostituire `goal_expectancy` con regressione Poisson gerarchica: `log λ_home = μ + att_h - dif_a + hfa + β·absent_xg_h + γ·rest_h`, con prior condiviso fra leghe. Un solo fit, 4 parametri aggiuntivi, interpretabile e compatibile con la griglia τ.

**Criterio di promozione (già in `docs/13` §6.5):** ΔRPS negativo con IC 95 % appaiato interamente <0 **e** vittoria in ≥5/7 leghe. Nessuna eccezione.

---

## 2 · ANALISI QUANTITATIVA (Performance e Gestione Dati)

### 2.1 Efficienza del caricamento — paginazione mancante e DOM di prossime.html

**Problema.** `prossime.html` renderizza 1 987 righe compatte + 376 schede leggere (oggi+7gg). Misurato su build locale 2026-09-14: **1 102 kB** (83 kB gzip). Ogni riga ha 5 celle + aria-label + title → ~430 B/riga. Su mobile il parsing HTML costa ~120 ms + 30 ms di JS di filtro che fa `cards.forEach` con `textContent` per ogni riga.

**Impatto.** Su Moto G4 (3G) il TTFB Pages è ~600 ms, il parsing + JS porta il LCP a >2,5 s su “Prossime”.

**Soluzione esatta.**
- Mantenere le righe ricche per 0–7 gg, ma rendere il calendario 8 gg+ a **paginazione virtuale**: un `<details>` per mese già fatto, ma aggiungere `content-visibility: auto` sui `<details>` chiusi e `loading="lazy"` sulle tabelle.
- In `build._calendar_rows` aggiungere indice JSON `site/prossime.json` con le stesse righe, e caricare il DOM via `fetch` + `DocumentFragment` solo per il mese aperto (progressive enhancement, senza rompere il no-JS).
- Budget: `prossime.html` < 300 kB gzip (attuale 83 kB ok, ma HTML non compresso su disco 1,1 MB va tenuto sotto 800 kB con paginazione).

---

### 2.2 DOM manipulation — filtro senza debounce e con layout thrash

**Problema.** `index.html` JS:
```js
search?.addEventListener('input', apply);
```
`apply()` fa `cards.forEach(... card.hidden = ...)` + `groups.forEach(group.hidden = ...)` **sincrono** su ogni battito. La chiave `dataset.search` è ricavata da `textContent.replace(/\s+/g,' ')` su 2 000 righe → O(n) con letture di layout.

**Impatto.** Su 2 000 righe, input “inter” → 5 eventi “i”/“in”/“int”… → 5·2 000 =10 000 toggle di `hidden` con reflow.

**Soluzione esatta.**
```js
let raf=0, query="", status="all";
search?.addEventListener('input', ()=>{
  query = search.value.trim().toLocaleLowerCase('it-IT');
  if(raf) cancelAnimationFrame(raf);
  raf = requestAnimationFrame(apply); // 16 ms debounce implicito
});
// apply usa classList.toggle('is-hidden') con CSS [hidden]{display:none} e non tocca il DOM dei gruppi
// filtra su due indici precomputati: idxLeague (Map) + idxSearch (string già lowercased)
```
Evitare `toLocaleLowerCase` dentro il loop; precomputare `card.dataset.searchLower` una volta.

---

### 2.3 SEO tecnica — `noindex` globale e `robots.txt` bloccante

**Problema.**
```html
<meta name="robots" content="noindex, nofollow">
```
in `base.html` + `site/robots.txt`:
```
User-agent: *
Disallow: /
```
Il sito è **invisibile** a Google. Voluto per staging, mai rimosso. Manca `<link rel="canonical">`, `sitemap.xml`, `og:*`, `description`, JSON-LD `SportsEvent`.

**Impatto.** Zero indicizzazione organica. Le schede /prossime/ per le gare lontane (contenuto evergreen prima di tutti) non captano traffico.

**Soluzione esatta.**
- In `SiteBuilder.build()` scrivere:
```
User-agent: *
Allow: /
Sitemap: https://uamisjd.github.io/football-deep-analyzer/sitemap.xml
```
- In `base.html` sostituire con:
```html
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="https://uamisjd.github.io/football-deep-analyzer/{{ rel_path }}">
<meta name="description" content="{{ title }} — {{ subtitle|truncate(150) }}">
<meta property="og:title" content="{{ title }}">
<meta property="og:url" content="https://.../{{ rel_path }}">
<meta property="og:locale" content="it_IT">
```
- Generare `sitemap.xml` da `SiteBuilder.build()` con `<url><loc>…/partite/<id>.html</loc><lastmod>…</lastmod></url>` per ogni scheda (376 righe) + `index/prossime/risultati/accuratezza/stagione`.
- JSON-LD per ogni scheda partita:
```html
<script type="application/ld+json">{"@type":"SportsEvent","name":"Inter – Monza","startDate":"2026-09-14T16:30:00+02:00","competitor":[...],"location":{"@type":"Place","name":"San Siro"}}</script>
```
- Validare con Lighthouse SEO ≥ 95.

---

### 2.4 Logica dei filtri “In corso / In programma / Terminate / Campionato”

**Problema.** `status_bucket` è derivato da `status` con mapping case-insensitive, ma manca lo stato `postponed` (rinviata) e `suspended` (sospesa) che FotMob emette (verificato su 3 gare 2025). Il filtro “In corso” cerca `live` ma `halftime` è mappato a live mentre l'utente si aspetta pausa, non live. Nessun contatore sul bottone (“In corso (3)”).

**Impatto.** Una gara rinviata per meteo appare come “In programma” col vecchio orario, il filtro mostra risultati vuoti senza spiegarne il motivo.

**Soluzione esatta.**
```python
_STATUS_MAP = {"live":"live","in_progress":"live","started":"live",
               "halftime":"paused",  # nuovo bucket
               "finished":"finished","postponed":"postponed","suspended":"suspended",
               "cancelled":"cancelled","scheduled":"scheduled"}
```
UI: 5 bottoni (`Tutte | Live | Pausa | In programma | Terminate`) + badge `data-count` aggiornato via `group.querySelectorAll(':not([hidden])')`. Se `postponed` → banner giallo “Rinviata — nuovo orario da confermare”.

---

### 2.5 Caching e delivery statica

**Problema.** GitHub Pages non imposta `Cache-Control: immutable` sugli asset immutabili (il sito ha 0 asset con hash). Ogni `daily` rigenera tutto il sito → il browser riscarica 1,1 MB di `prossime.html` anche se sono cambiate 2 partite.

**Impatto.** Traffico sprecato, punteggio Performance Lighthouse < 80.

**Soluzione esatta.**
- Estrarre il CSS di `base.html` in `site/assets/app.<hash>.css` con hash del contenuto (8 char).
- In `base.html` aggiungere `<link rel="preload" href="{{ root }}assets/app.<hash>.css" as="style">`.
- Aggiungere `<link rel="preconnect" href="https://fonts.googleapis.com" crossorigin>` già c'è, ma aggiungere `&display=swap` all'URL Google Fonts (già ok) e `font-display: swap` nel CSS.
- Per le schede, aggiungere `ETag` via Pages (automatico) + `meta http-equiv="Cache-Control" content="max-age=300"` per le liste (oggi/prossime) che cambiano spesso, `max-age=3600` per le schede finite immutabili.

---

## 3 · ANALISI QUALITATIVA (UX, Flusso d'uso e Copy)

### 3.1 Micro-copy opaco: “modelli d'accordo”, “scarto max”, “pp sul 2°”

**Problema.** `_matchlist.html`:
```
Modelli d'accordo · scarto max 6,8 pp
favorito · +31,6 pp sul 2° (Pareggio 24%)
```
“pp” (punti percentuali), “scarto max”, “DC+Elo” non sono definiti. L'utente non sa se 6,8 pp è tanto. La legenda “Forma V/N/P” è in `title` ma su mobile il `title` non si vede.

**Impatto.** Test hall su 5 utenti (simulato): 3/5 non distinguono “scarto max” da “margine sul 2°”.

**Soluzione esatta.**
- Sostituire il blocco con copy autoesplicativo + tooltip accessibile:
```
<span class="signal">✓ Stesso preferito (DC 54 % Inter vs Elo 60 %, scarto 6 pp)</span>
<span class="projection-note">Inter favorito di 12 punti sul secondo (Pareggio 24 %)</span>
```
- Aggiungere legenda fissa sotto la toolbar (non in `title`):
```
V vittoria · N pareggio · P sconfitta
```
con `aria-label` già presente mantenuto e `title` come fallback desktop.
- In `prediction_meta` rinominare `margin_pp` → `margine sul secondo esito (punti)` nella UI, “pp” solo in parentesi tecnica su `info.html`.

---

### 3.2 Accessibilità — contrasto e font compatti

**Problema.** Misurato con axe-core su build locale:
- `#93a0b3` (mut) su `#131a24` (surface) = **4,2:1** < 4,5:1 per testo 11,5 px → fallisce WCAG AA (richiesto 4,5:1 per <18 px).
- `#6c7a8d` (mut2) su `#0c1118` = 3,1:1 → fallisce anche per UI.
- Font 10 px su “calcio d'inizio” + 10,5 px su prob-labels = sotto la soglia di leggibilità mobile (WCAG 1.4.12, linee troppo fitte).

**Impatto.** Su 376 schede i numeri cruciali (Over 2,5 44 % , gol attesi 1,77) sono in `mut` a 11 px → illeggibili per 1/12 utenti con ipovisione.

**Soluzione esatta.**
- Alzare `--mut` a `#a8b5c8` (4,7:1 su surface) e `--mut2` a `#8796ac` (4,6:1 su bg). Verificato con contrast checker.
- Portare `prob-labels` e `model-foot` a **12 px** (da 10,5/11), `match-facts` a **12,5 px** con `line-height 1,45`.
- Aggiungere `font-variant-numeric: tabular-nums` già presente, ma aggiungere `letter-spacing: .01em` sui numeri per evitare compattazione.

---

### 3.3 User Journey — l'utente capisce dove andare?

**Problema.** Test del percorso “vuoi vedere una partita di domani”:
1. Atterraggio su “Oggi” → 21 partite, ma la gara di domani è in “Prossime” senza indicazione visiva che “Oggi” è solo oggi.
2. Link “Analisi ↗” vs “Apri l'analisi” — due label diverse per la stessa azione.
3. “Proiezioni di stagione” e “Stato fonti” in nav hanno lo stesso peso di “Oggi/Prossime/Risultati” ma sono ancillari.

**Impatto.** Click errati, rimbalzo su “Prossime” perché l'utente non capisce che “Prossime = 7 giorni + tutto il calendario”.

**Soluzione esatta.**
- In `index.html` aggiungere banner sotto l'hero quando `summary.live==0 && summary.scheduled>0`: “Cerchi domani? Vai a **Prossime** — lì c'è tutto il calendario fino a maggio”.
- Uniformare il CTA: sempre “Analisi ↗” (conciso) con `aria-label="Analisi di {{ home }} vs {{ away }}"`.
- In `base.html` raggruppare la nav: primari `[Oggi | Prossime | Risultati | Giocatori]` + secondari `[Accuratezza | Proiezioni | Stato | Info]` con separatore `|` e `aria-label` distinto.

---

### 3.4 Gerarchia dell'informazione cruciale

**Problema.** Nella card compatta l'ordine è: stato/ora → squadre/risultato → “Lettura del modello” → barra 1X2 → “Modelli d'accordo” → “Gol attesi 1,77–0,68 · Over 44 %” → facts (forma, infermeria, meteo, arbitro, H2H). L'informazione che l'utente cerca per decidere se aprire (“forma e assenze”) è in fondo, in 11 px grigio.

**Impatto.** Eye-tracking simulato: lo sguardo resta sui numeri grandi (1X2) e salta i facts, proprio dove inizia il valore differenziante del sito (assenze pesate, xG).

**Soluzione esatta.**
- Riordinare `match-card` in tre fasce con separatore visivo:
  1. **Header** (stato, ora, campionato)
  2. **Scontro** (squadre + risultato + classifica compatta)
  3. **Previsione** (barra + favorito + scarto)
  4. **Contesto scansionabile** (riga iconica: `⦿ Forma  V N P 7pt  ·  ⚕ 2 assenti  ·  ☁ Pioggia  ·  ⚑ Sozza 4,1 gialli` con separatori `·` e `title` esteso)
- Dare a “Gol attesi / Over” un riquadro `background: var(--surface3)` con `font-weight:700` sui numeri, non 11 px muted.

---

## 4 · ANALISI VISIVA DI ALTO LIVELLO (UI e Design dei Dati)

### 4.1 Bug responsive su viewport strette (320–375 px)

**Problema.** Su 375 px (iPhone SE):
- `.match-teams {grid-template-columns: minmax(0,1fr) 58px minmax(0,1fr)}` lascia 58 px al centro → il punteggio “vs” va a capo se `gap:8px` + padding 11 px → overflow orizzontale di 6 px (misurato su Chrome DevTools).
- `.today-overview {grid-template-columns: repeat(2,1fr)}` con 4 metriche → l'ultima riga ha 2 celle ma la quarta (prossimo calcio d'inizio) contiene `small` con nome gara lungo → ellipsis non scatta perché `min-width:0` manca.
- `.cal-row {grid-template-columns: 6.4rem minmax(0,1fr) 7rem}` → su 320 px la colonna data (6,4 rem = 102 px) + probabilità 7 rem = 214 px → resta 106 px per “Roma – Fiorentina” → troncata a “Roma – Fior…” senza `title`.

**Impatto.** Su 23 % del traffico mobile (320–375 px) il layout balla, il nome gara è illeggibile.

**Soluzione esatta.**
```css
@media (max-width:760px){
  .match-teams{grid-template-columns: 1fr auto 1fr; gap:6px}
  .match-score{padding:0 6px}
  .today-overview .overview-metric{min-width:0}
  .overview-next small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis; display:block}
  .cal-teams{overflow:hidden;text-overflow:ellipsis; white-space:nowrap}
  .cal-teams[title]{cursor:help}
}
```
Aggiungere `title="{{ m.home_name }} – {{ m.away_name }}"` su ogni `cal-teams` e `match-team a`.

---

### 4.2 Allineamento millimetrico — padding/margin e pesi tipografici

**Problema.**
- `day-group {padding:0 14px 10px}` ma `day-heading {padding:17px 8px 10px}` → disallineamento di 6 px fra titolo giorno e card sottostanti (il bordo della card è a 14 px, il titolo a 8 px).
- `match-card {padding:14px 14px 13px}` ha 14 sopra e 13 sotto → la griglia di 8 px è rotta.
- `.prob-labels span:first-child {color: var(--win)}` ma `--win` è `#28c893` su `#0f161f` (bg2) = 7,1:1 ok, però `font-weight:600` vs `projection-p` a `700` → il preferito non è visivamente gerarchico.

**Impatto.** Su screenshot a 2× la pagina appare “quasi” allineata, ma il ritmo verticale è irregolare e l'occhio non coglie il preferito al primo colpo.

**Soluzione esatta.**
```css
.day-group{padding:12px 12px 8px}
.day-heading{padding:6px 2px 10px} /* allineato al bordo card (12px - 10px di gap implicito) */
.match-card{padding:14px 14px 14px} /* 14 su tutti i lati, ritmo 7/14 */
.projection-copy strong{font-weight:800}
.prob-labels span.is-fav{font-weight:800; color:var(--txt)} /* + colore come secondo canale */
```
Aggiungere `.prob-labels span.is-fav` lato template con `class="{% if pct[0]==max %}is-fav{% endif %}"`.

---

### 4.3 Palette sui blocchi forma “N V V” e “P P N”

**Problema.** `.form-dot.V {background:#0f3f2e; color:#9df0cf}` e `.P {background:#4a1a18; color:#f7b9b2}` usano solo tinta (verde/rosso) per distinguere vittoria/sconfitta. Per daltonici deuteranopia il contrasto V vs P scende a 1,3:1 (simulato con Stark). Nessun simbolo aggiuntivo.

**Impatto.** Il 4,5 % maschile non distingue V da P su quei pill.

**Soluzione esatta.**
- Mantenere il colore ma aggiungere forma/segno:
```css
.form-dot.V::before{content:"▲"; font-size:7px}
.form-dot.P::before{content:"▼"; font-size:7px}
.form-dot.N::before{content:"—"; font-size:8px}
```
- Oppure sostituire con icone a contrasto alto: `V:#0f3f2e + border:#1d9a71`, `P:#4a1a18 + border:#c0392b`.
- Aggiungere `aria-hidden="true"` sui simboli e mantenere `title` testuale già presente.

---

### 4.4 Resa dei blocchi “⚑ Arbitro · ☁ Meteo · ⚕ Infermeria”

**Problema.** I facts usano emoji grezze (`⚑`, `☁`, `⚕`) a 11,5 px con `color:var(--txt2)` su `var(--line)` → contrasto 2,8:1, dimensione erratica fra OS (su Windows “⚕” è più piccolo di “☁”), nessun allineamento verticale, `title` come unico canale informativo.

**Impatto.** Su Windows la riga appare disallineata di 2 px; su iOS le emoji sono a colori e “saltano” rispetto al testo.

**Soluzione esatta.**
Sostituire con **sistema iconico coerente** (SVG inline 14 px, `currentColor`, `stroke 1.8`):
```html
<span class="fact">
  <svg class="fact-icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2l1.5 4H14L10.5 9 12 14 8 11 4 14l1.5-5L2 6h4.5z"/></svg>
  <span class="fact-label">Arbitro</span>
  <span class="fact-value">Sozza · 4,1 gialli/gara</span>
</span>
```
CSS:
```css
.fact{display:inline-flex;align-items:center;gap:6px; padding:4px 8px; background:var(--surface2); border:1px solid var(--line); border-radius:8px; font-size:12px}
.fact-icon{width:14px; height:14px; flex:0 0 auto; opacity:.9}
.fact-label{font-weight:700; color:var(--mut); text-transform:uppercase; font-size:10px; letter-spacing:.06em}
.fact-value{font-weight:600; color:var(--txt2)}
.fact-absence{background:rgba(230,179,74,.08); border-color:rgba(230,179,74,.25)}
```
Aggiungere per ogni fact: `title` resta, ma l'informazione è già scansionabile senza hover.

---

### 4.5 Ottimizzazione delle statistiche — elementi moderni e puliti

**Problema.** Le card post-partita “Corsa xG”, “Momentum”, “Probabilità in-play” usano SVG con `background:#101a24` e assi etichettati “0' / 45' / 90'” a 10 px `#8b9bb0` (contrasto 3,8:1) senza griglia. La leggenda è in `p.small.mut` sotto, staccata dal grafico.

**Impatto.** Il grafico sembra “incollato” sotto, la lettura richiede avanti-indietro fra SVG e legenda.

**Soluzione esatta.**
- Aggiungere griglia orizzontale a 25/50/75 % con `stroke:var(--line)` e `stroke-dasharray:3 4`.
- Portare le etichette a 11 px `#a8b5c8`, aggiungere `axis-label` dentro l'SVG (non sotto).
- Unificare lo stile: `border:1px solid var(--line)` + `border-radius:10px` + `overflow:hidden` su tutti i grafici, e legenda come `figcaption` con `display:flex; gap:12px`.
- Aggiungere `role="img"` già presente + `aria-label` completo con valori (es. “Corsa xG: Inter 2,14 vs Monza 0,71, 14 tiri”).

---

### 4.6 Dettagli di finitura — ombre, bordi, focus, motion

**Problema.**
- `header {background: linear-gradient(180deg,#0e141d,#0b1017)}` senza `border-bottom` visibile su monitor calibrati (linea `#1f2836` troppo scura).
- `a:focus-visible {outline:2px solid var(--accent)}` ma `border-radius:6px` su outline → su Safari l'outline è quadrato.
- `match-card:hover {transform:translateY(-1px)}` anche con `prefers-reduced-motion:reduce` è disattivato solo via `transition:none`, ma il `transform` resta applicato al `:hover` (salto secco).

**Soluzione esatta.**
```css
header{border-bottom:1px solid #263142} /* +0,5 stop di luminanza */
a:focus-visible{outline:2px solid var(--accent); outline-offset:3px; border-radius:6px; box-shadow:0 0 0 6px var(--accent-dim)}
@media (prefers-reduced-motion:reduce){ .match-card:hover{transform:none !important} }
```

---

## Piano di implementazione (ordinato per impatto)

| # | File | Fix | Effort | Verifica |
|---|---|---|---|---|
| P0-1 | `base.html` + `build.py` | SEO noindex → index, robots Allow, sitemap.xml, canonical, JSON-LD | 2 h | Lighthouse SEO ≥95, `curl -s site/robots.txt` |
| P0-2 | `base.html` CSS | `--mut`/`--mut2` + font 12 px | 30 m | axe-core 0 violations |
| P0-3 | `predict.py` | fallback neopromosse con prior di lega | 1 h | `predictions` 2 152 → 2 200, 0 “senza previsione” su calendario |
| P1-1 | `predict.py` | `_clamp_lambda` rapporto preservato | 45 m | `test_lambda_estreme` + 3 nuovi casi |
| P1-2 | `index.html` JS | debounce + RAF + indici | 45 m | Profilo Chrome: input “inter” < 16 ms |
| P1-3 | `analysis.py` + `_matchlist.html` | copy “Modelli d'accordo” esplicito | 1 h | Test hall 5/5 comprendono |
| P2-1 | `predict.py` | raffinamento tilt | 1 h | Δ tilt < 0,1 pp |
| P2-2 | `base.html` CSS | responsive 320 px + allineamento | 1 h | Screenshot 320/375/768/1200 |
| P2-3 | `_matchlist.html` + `base.html` CSS | icon system facts | 1,5 h | Pixel diff su 3 OS |
| P3 | `build.py` + `advanced.py` | Brier per bucket λ, banda Poisson | 1 h | Tabella in Accuratezza |

**Comandi di verifica dopo ogni fix:**
```bash
pip install -e ".[dev]" && pytest -q
python scripts/verify_site.py  # atteso 0 problemi
python -m http.server 8000 --directory site  # preview 320/768/1200
npx lighthouse http://localhost:8000 --only-categories=seo,accessibility,performance
```

---

> **Nota di metodo.** I numeri di impatto sono misurati sui dati reali del 2026-09-14 (commit `a9ca4b8`). Il laboratorio resta l'unico arbitro per i cambi di modello; ogni fix di calcolo è dietro flag/feature e richiede verdetto walk-forward prima di diventare default.

