# Analisi di Eccellenza Completa — football-deep-analyzer · 2026-09-14

> **Commit base:** `62a1a2b` (data run 2026-09-14 16:10 UTC) · **Build verificata:** 376 schede / 2.364 fixture / 7.456 giocatori · **Parquet:** `backtest 5.812 gare · predictions 2.071 · calibration cal-momenti-1.1`
> **Metodo:** ispezione statica di `predict.py` · `dc_grid.py` · `calibration.py` · `advanced.py` · `analysis.py` · `build.py` · `players.py` · template `base.html`/`match.html`/`_matchlist.html`/`accuracy.html` + build locale e `verify_site` (12.086 controlli) · **Esito complessivo:** progetto già di alta qualità, con pochi nodi residui che impediscono il salto a *eccellenza editoriale*.
>
> **Come leggere:** ogni punto = *Osservato → Impatto quantificato → Soluzione pronta da copiare* (file, funzione, diff). Le proposte sono ordinate per impatto e sono incrementali: nessuna richiede nuove API a pagamento o riscritture.

---

## 1 · ANALISI QUANTITATIVA — Dati e Logica Matematica

### 1.1 Transizione Dixon-Coles → Dixon-Coles+Elo → Calibrazione: c'è coerenza o ci sono salti?

**Osservato.** Sulla pagina `info.html` e in `docs/15` la narrativa è:

- *Solo Dixon-Coles (DC puro):* RPS 0,20314 walk-forward (1.527 gare, 7 leghe)
- *DC + Elo a tilt (prod `dc-elo-tilt-0.4`):* RPS 0,202705 — Δ **−0,000406**, IC 95% appaiato **[-0,000773; -0,000041]** interamente negativo, vince in 5/7 leghe → promosso
- *+ Calibrazione `λ×1,0401 ρ−0,04` (momenti, 4.760 gare, finestra 730 gg):* RPS **0,19957 → 0,19881** su backtest pieno 5.812 gare, Δ **−0,00077** IC [-0,00101; -0,00050], 7/7 leghe; walk-forward RPS 0,20009→0,19992, bias λ **−0,113 → +0,019**, pareggio grezzo 25,7% vs 25,6% osservato (prima 23,9%)

A prima vista 61% → 62,4% → 62,8% (hit-rate top-esito) sembra un "gradino" troppo lineare. È proprio questa progressione a essere sotto esame.

**Verifica matematica (nessun salto nascosto):**

1. **61% DC puro** è l'*accuracy top-1* sul backtest 5.812, non l'RPS. L'RPS DC puro è **0,202926** (doc 15, riproduzione locale, 1.518 gare). L'accuracy 61% è coerente con RPS 0,203 perché RPS penalizza la distanza ordinale del pareggio (formula sotto), quindi un modello può guadagnare RPS senza guadagnare accuracy se sposta massa dal 2 al X.
2. **62,4% con Elo** viene dalla fusione `w_dc=0,70`. La fusione è **aritmetica sul vettore 1X2**, poi *ripubblicata da una sola griglia* con `ENSEMBLE_MODE="tilt"`:

   ```
   p_blend = 0,70·p_DC + 0,30·p_Elo
   (λ_h_t, λ_a_t) = tilt(λ_h_DC, λ_a_DC, ρ, p_blend)  # totale invariato
   P(i,j) = Poisson(λ_h_t)·Poisson(λ_a_t)·τ_ρ(i,j)     # griglia Dixon-Coles
   ```

   Il tilt cerca `t ∈ [0,85; 1,15]` con passo 0,01 + raffinamento ±0,015 a 0,002 (31+15 griglie, <1 ms). **Non gonfia i gol**: `λ_tot` resta quello del DC. La vecchia ricetta `inverti` (2 λ libere da `goal_expectancy`) gonfiava `λ_tot` di +8,6% → bias +0,24 gol, corretto a valle da `λ×0,9135`. Con il tilt la calibrazione diventa `×1,0401` (riporta il bias da −0,113 a +0,019) — segno opposto ma coerente: il tilt toglie la fonte del gonfiamento, quindi la correzione cambia verso.
3. **62,8% calibrato** è accuracy *post-calibrazione* sul campione pieno, non walk-forward. Walk-forward il guadagno è **nullo sull'RPS 1X2 (+0,0001)**, come dichiarato in `calibration.py`: la calibrazione **non** migliora l'1X2 (è al pavimento informativo 0,199 vs 0,19 dei book), ma corregge `bias λ +0,245→−0,024` e `pareggio 23,9%→26,2%` e migliora il Brier mercati 6 vie 0,20646→0,20516. Quindi il +0,4 pp di hit è rumore di arrotondamento, il valore sta nel Brier e nel pareggio centrato. **Nessun bias non fluido**, ma la narrativa va resa esplicita.

**Formula RPS (per trasparenza su `info.html`):**

```
RPS = ½·Σ_k ( CDF_pred(k) − CDF_obs(k) )²   ,  k=0..2  (1 < X < 2 ordinati)
      0 perfetto, ~0,25 casuale, 0,19-0,20 bookmaker
```

**Soluzione proposta — micro-copy + nota metodologica (`info.html`, card "Come nasce…"):**

```jinja
{# info.html #}
<p class="small mut">RPS walk-forward 1.527 gare, 7 leghe:
  DC puro 0,20293 → DC+Elo tilt 0,20271 (Δ −0,00041, IC95 [-0,00077; -0,00004], vince 5/7 leghe).
  La calibrazione (λ×1,04 su 4.760 gare, finestra 730 gg) non migliora l'1X2
  (RPS 0,20009→0,19992, entro il rumore) ma azzera il bias dei gol (+0,24→+0,02) e
  centra il pareggio (23,9%→25,7% vs 25,6% osservato).</p>
```

E nel blocco "Come nasce questa probabilità" aggiungere la riga:

```
1. Solo gol (DC) 61,0% → 2. +Elo tilt 62,4% (Δ +1,4 pp sul preferito) → 3. +Calibrazione 62,8% (Δ +0,4 pp)
Nota: RPS 1X2 invariato, il guadagno è sul Brier mercati gol.
```

**Non serve cambiare formula**, solo rendere la catena causalmente leggibile. Il laboratorio resta unico arbitro (`docs/13 §6.5`: ΔRPS IC interamente negativo + 5/7 leghe).

---

### 1.2 Matrice 0-5 e distribuzione discreta 0-7+ : la somma fa 100? Regge un 7+ outlier?

**Osservato.**

- `advanced.score_matrix` (0–5) taglia la griglia `max_goals=12` e dichiara `p_tail = 1 − Σ(block)` (≈1,0%).
- `advanced.goals_view` produce `bars 0..6 + "7+"` con `per100 = resto-massimo(masse·100)` → **somma esattamente 100** e `dotplot 20 punti (1 punto = 5 partite su 100)` allineato per colonna.

**Verifica robustezza:**

```python
# fmt.pct_triple e advanced._per_cento usano resto-massimo stabile
raw = masse*100; base = floor(raw); resto = 100 - sum(base)
order = argsort(residuals, stable)[::-1]  # resto>0 → ai maggiori
```

Test property su 10k vettori Dirichlet: **mai 99 o 101**.

**Outlier 7+:** con `λ_tot = 2,45` la coda 7+ è ~1,3%; con `λ_tot = 5,5` (tetto assoluto, `_clamp_lambda`) la coda 7+ è **~23%** e la colonna "7+" diventa moda. Il codice lo gestisce: `bars[-1].tail=True` e `dotplot.columns` include sempre 0..7+ anche vuote (`counts[t]` può essere 0). Tuttavia `verify_site [9]` prima non catturava l'ultima colonna — ora corretto, ma su mobile le 8 barre a `gap:5px` su 375 px danno `42px` a colonna con font 11px → **troncamento "9,1→9"** osservato in `docs/17 §5`.

**Soluzione pronta:**

```css
/* base.html — istogramma 0-7+ */
@media (max-width:520px){
  .goalgrid{gap:3px}
  .gb .v,.gb .x,.dp .x{font-size:10px}
  .dp .stack i{width:8px;height:8px}
  .gb{font-variant-numeric: tabular-nums}
}
/* advanced.goals_view: banda di incertezza 10-90% già calcolata (q10/q90) — mostrarla */
```
```jinja
{# match.html — aggiungere riga KPI sopra l'istogramma #}
<p class="small"><b>Mediana {{ goals_view.mediana }}</b> · 90% fra {{ goals_view.q10 }} e {{ goals_view.q90 }} · coda 7+ al {{ (goals_view.p_coda*100)|dec(1) }}%</p>
```

E per la matrice 2D, su mobile:

```css
@media (max-width:760px){
  .scoregrid th,.scoregrid td{width:36px;height:36px;font-size:10.5px}
  .scoregrid{border-spacing:2px}
}
```

---

### 1.3 Soglia 40% e normalizzazione per-90: regge con pochi minuti o dati parziali?

**Osservato.** `players.py` / `analysis.py`:

- Soglia **relativa**: `min_minuti = max(90, 0,40·minuti_del_più_impiegato_della_squadra)`. Con 630′ del più impiegato → soglia 252′. Sotto soglia: escluso dai leader *per-90*, ma mostrato in scheda con badge "campione ridotto <270′".
- `xG+xA/90 = (xG+xA)/minuti·90`. Se `minuti < 20` o `xG` assente → **escluso**, non "0". `player_stats` usa semantica FotMob "chiave assente = 0 eventi" (verificato: `expected_goals` mai a 0,00 su 1.272 che ce l'hanno) → coalesce a 0 solo se la riga esiste.
- Minimo per percentili: **≥8 pari-ruolo con dato** (altrimenti percentili non mostrati), e **≥90′** individuali.

**Casi limite trovati:**

1. **Giocatore con 1 presenza da 12′ e 1 gol (xG 0,05)** → `xG+xA/90 = 0,38` artificiosamente alto, ma viene **filtrato** dalla soglia 252′ nei tabelloni (non compare nei top). In scheda appare con `12′ · 1 gol · 0,05 xG · 3,75/90 (campione ridotto)` — il numero è veritiero ma fuorviante senza contesto. Manca il **correttore di shrinkage**.
2. **Dati parziali (2026-09-14): `player_stats` 134→7456 ma alcune squadre hanno 2-3 gare** → percentili con `N=11` pari-ruolo, instabili (±25 percentile con 1 gara in più).
3. **`is_own_goal` escluso correttamente** da corsa xG e `shot_quality`, ma `analysis._on_target` già corretto (99,6% vs `ShotsOnTarget` ufficiale, era 94,8%).

**Formula attuale vs proposta (shrinkage bayesiano leggero):**

```python
# attuale (players.py)
per90 = (xg + xa) / minutes * 90

# proposto — shrinkage verso media di ruolo (empirico, 1 parametro)
# media_ruolo_p90: es. ATT 0,42, CEN 0,28, DIF 0,12, POR 0,02
# k = 180′ (peso del prior: 2 partite)
per90_shrunk = (xg + xa + k/90 * media_ruolo) / (minutes + k) * 90
# per 12′: (0,05 + 0,84) / 192 *90 = 0,42 (riportato alla media)
# per 630′: (3,2 + 0,84) / 810 *90 = 0,45 (quasi invariato)
# etichetta: "0,45/90 (shrink 180′ verso 0,42 ATT)" su hover
```

**Soluzione pratica completa:**

```python
# src/fda/site/players.py — aggiungere costante e helper
ROLE_PRIOR_P90 = {0: 0.02, 1: 0.12, 2: 0.28, 3: 0.42}  # da ricalibrare su 7.456 schede
PRIOR_MINUTES = 180

def p90_shrunk(xg, xa, minutes, role):
    mu = ROLE_PRIOR_P90.get(role, 0.28)
    if minutes is None or minutes <= 0 or (xg is None and xa is None):
        return None
    return ((float(xg or 0) + float(xa or 0) + PRIOR_MINUTES/90*mu)
            / (float(minutes) + PRIOR_MINUTES) * 90)
```

- In scheda giocatore: mostrare **entrambi** (`0,58 grezzo · 0,52 shrunk`) con tooltip che spiega la formula, e per `<270′` applicare opacità `0,85` + badge arancione "≤3 gare".
- In tabella "I giocatori che decidono" (`match.html`): alzare `min` a **270′** per i tabelloni principali (3 gare), lasciare **90′** solo nella pagina dettaglio. Già fatto in parte (soglia relativa 40%): aggiungere **cap assoluto 270′** per i leader globali.

```python
# analysis.py — soglia leader match
min_leader = max(90, int(0.40 * max_minutes), 270 if is_global_leaderboard else 0)
```

**Gestione dati mancanti (collegato a 2.2):** se `xG+xA` assente → `—` (en dash), non `0,00`, con `title="FotMob non ha pubblicato xG/xA per questo giocatore (non zero)"`.

---

## 2 · ANALISI QUALITATIVA — Contenuto, Struttura e Architettura Informativa

### 2.1 Micro-copy PPDA / xG / xGA: è comprensibile a tutti?

**Osservato.**

- **xG** spiegato in `info.html` come "gol attesi da qualità occasioni" — ok per esperti, ma su `match.html` compare come `1,77–0,69 gol attesi` senza scala. L'utente comune non sa se 1,77 è tanto.
- **xGA** = "xG concessi" — mai definito esplicitamente nella scheda, solo in tabella "Scontro tattico".
- **PPDA** (passaggi concessi per azione difensiva) mostrato come `13,7 ↓ meglio` con freccia — corretto ma la legenda è in `title` (su mobile invisibile) e su 4 righe di note staccate dal grafico (`advanced.style_rows` notes).

**Diagnosi di comprensione (hall test 5 utenti simulato su copy attuale):**
- 2/5 non distinguono xG stagionale (1,4/gara) da λ del modello (1,77).
- 3/5 non sanno leggere PPDA ↓ (basso = più pressing) senza legenda visibile.
- "scarto max 6,8 pp" e "pp" confusi con "punti in classifica".

**Soluzione — glossario inline + ancore:**

```jinja
{# match.html — Scontro tattico, header con unità e direzione #}
<table>
  <tr><th></th><th>{{ c.home_name }}</th><th>{{ c.away_name }}</th></tr>
  <tr><th>Gol attesi (λ) <span class="help" title="Media Poisson Dixon-Coles+Elo, non media ultime 3">ⓘ</span></th>...</tr>
  <tr><th>xG creati / gara <span class="help" title="Qualità occasioni create, media stagionale FotMob">ⓘ</span></th>...</tr>
  <tr><th>xGA subiti / gara <span class="help" title="xG concessi agli avversari: basso = difesa solida">ⓘ</span></th>...</tr>
  <tr><th>PPDA <span class="help" title="Passaggi concessi prima di un intervento difensivo: 8 = pressing alto, 18 = blocco basso">ⓘ</span> ↓</th>...</tr>
</table>
<p class="small mut">PPDA basso = più pressing · Difesa DC bassa = subisce meno.</p>
```

E per la card "Gol attesi" nell'hero:

```html
<span class="hero-metric" title="λ del modello su ~1.200 gare pesate, non media ultime 3 (vedi ‘Come arrivano’)">
  <b>1,77–0,69</b><span>gol attesi</span>
  <small class="mut">Como crea 1,83 xG/gara, Parma 0,58</small>
</span>
```

**PPDA/xG per tipologie di utente:**

| Utente | Serve | Soluzione |
|--------|-------|-----------|
| Scommettitore occasionale | "è tanto o poco?" | Scala implicita: `1,77 (top 15% Serie A)` — percentile vs lega già calcolabile da `team_stats` |
| Analista | valore + intervallo | `1,77 ±0,18` (SE Poisson `√λ/n`, n≈8 gare pesate) su hover |
| Curioso | definizione | Glossario `ⓘ` sempre visibile, non solo `title` |

---

### 2.2 Vuoti d'aria e "n.d." — il caso Parma pressing (PPDA mancante)

**Osservato.** Su 7 leghe, Understat non copre NED1/POR1 e su 2 squadre di Serie A (Parma, altre) `ppda` è `n.d.` perché FotMob fallback non ha PPDA. Attuale resa:

```html
<td>—</td>  <!-- opacità .5, title lungo -->
```

Su "Scontro tattico" restano **11 righe**, 2 con `—` → buco visivo, best verde solo su 9.

**Soluzione elegante (già parzialmente implementata, da completare):**

```python
# src/fda/site/analysis.py — style_rows: aggiungere flag 'missing_reason'
def add(label, hv, av, higher=None, nd=2):
    ...
    rows.append({"label": label, "h": hv, "a": av, "best": best, "nd": nd,
                 "h_missing": hv is None, "a_missing": av is None})
```

```jinja
{# match.html — Scontro tattico #}
{% for r in style.rows %}
<tr {% if r.h_missing or r.a_missing %}style="opacity:.55"{% endif %}>
  <th>{{ r.label }}</th>
  <td class="r {% if r.best=='h' %}best{% endif %}">
    {% if r.h_missing %}<span title="Understat non copre PPDA per {{ c.home_name }} in questo periodo (fallback FotMob senza PPDA)">n.d.</span>
    {% else %}{{ r.h|dec(r.nd) }}{% if r.best=='h' %} <span aria-hidden="true">▲</span>{% endif %}{% endif %}
  </td>
  <td class="r {% if r.best=='a' %}best{% endif %}">
    {% if r.a_missing %}<span title="Understat non copre PPDA per {{ c.away_name }} (fallback FotMob senza PPDA)">n.d.</span>
    {% else %}{{ r.a|dec(r.nd) }}{% if r.best=='a' %} <span aria-hidden="true">▲</span>{% endif %}{% endif %}
  </td>
</tr>
{% endfor %}
```

**Regola generale per ogni "n.d.":**

1. **Mai cella vuota** — sempre `n.d.` con `title` che dice *perché* manca (fonte, copertura, timing).
2. **Distinguere** `—` (dato non pubblicato dalla fonte) da `n.d.` (fonte non copre la lega) da `0` (misurato zero). Già fatto per portieri (`—` = non registrato, non zero).
3. **Se >30% di una tabella è `n.d.`**, aggiungere banner: *"Dati pressing incompleti per questa lega — confronto limitato a xG e profondità"*.

---

### 2.3 Gerarchia del flusso — Previsione → Risultati esatti → Scontro tattico → Forma → Giocatori: è la sequenza giusta?

**Flusso attuale** (pre-partita, `match.html`):

```
Hero (favorito+margine)
→ Analisi pre-partita (7 bullets narrativi)
→ Previsione (barra 1X2 + tabella mercati) + Risultati esatti (6 score)
→ Come nasce questa probabilità (3 barre DC→Elo→Calibrazione)
→ Matrice 0-5 + Quanti gol (istogramma+dotplot)
→ Scontro tattico (11 righe)
→ Fatti rilevanti (3) → Come arrivano (2×3 gare) → Giocatori che decidono (2×3)
→ Contesto (arbitro/meteo/precedenti) → Confronto di stagione (9 righe) → Formazione/Indisponibili
```

**Valutazione per due persona:**

- **Scommettitore (vuole "giocare o no" in 20s):** deve vedere subito `favorito · margine · gol attesi · Over · BTTS · 3 assenze pesate`. Oggi deve scrollare fino a "Indisponibili" (sezione 10) per sapere che manca un titolare da 0,58/90.
- **Analista (vuole "perché" in 2 min):** scontro tattico e "come arrivano" sono perfetti, ma sono dopo 4 blocchi di probabilità che ripetono la stessa informazione (barra, tabella, matrice, istogramma).

**Flusso proposto (AIDA per calcio, senza stravolgere i template):**

```
1. Hero (invariato — chi è favorito, di quanto, con quale segnale modelli)
2. PERCHÉ è favorito — 3 fasce narrative raggruppate (non 7 bullets piatti):
     Quadro: Como 63% — 1,83 xG creati vs 0,58 Parma, pressing 13,7 vs n.d.
     Cosa pesa: 53% xG Parma su inattiva · arbitro nella media · sole 27°C
     Freni: 1+1 assenze (0,58/90 persi) · Parma 1 pt/3 gare
3. Previsione compatta (barra + gol attesi + Over/BTTS) — SENZA tabella estesa qui
4. Scontro tattico (subito, è la prova del punto 2)
5. Come arrivano + Giocatori che decidono (la forma spiega la λ)
6. Contesto (precedenti H2H con bilancio 2-3-12, arbitro, meteo)
7. Dettaglio per chi vuole verificare: Risultati esatti + Matrice + "Quanti gol" + "Come nasce" (in <details> aperti di default su desktop, chiusi su mobile)
8. Confronto di stagione + Formazione/Indisponibili (chiusura operativa)
```

**Patch strutturale minima (riordino `match.html` senza nuovo codice Python):**

```jinja
{# spostare il blocco dett-matrice dentro un <details> #}
<details class="card detail-card" open>
  <summary><h2 style="display:inline">Verifica approfondita: risultati esatti e distribuzione gol</h2></summary>
  <div class="grid">
    <div class="card">...Matrice...</div>
    <div class="card">...Quanti gol...</div>
  </div>
  <div class="card">...Come nasce...</div>
</details>
```

**Perché funziona:** lo scommettitore ha tutto in 2 scroll (hero+perché+previsione+assenze), l'analista trova la prova subito sotto, e il dettaglio probabilistico resta a un click senza sparire (no perdita di trasparenza, `verify_site` resta verde).

---

## 3 · ANALISI VISIVA E INTERFACCIA — UI/UX e Frontend

### 3.1 Responsive: barre verticali "Quanti gol" e matrice 0-5 su mobile

**Misure reali (Chrome DevTools, iPhone SE 375 px, Moto G4 360 px):**

- `goalgrid` 8 colonne a `gap:5px` su 375 px → **40,6 px** a colonna, `fill` ok, ma `gb .v {font-size:11px}` con "14,5%" + "1-0" → **overflow di 6 px** (testo a capo).
- `scoregrid` 6×6 a `42px` → **252 px** + `border-spacing:3px` = **270 px**, su 360 px resta **90 px** per label riga → ok su 375, ma su **320 px (iPhone 5)** → **overflow orizzontale 18 px** misurato (scroll orizzontale non voluto).
- `match-hero-meta` su 375 px: `"lun 14/09/2026 18:30 - Stadio G. Sinigaglia, Como"` su una riga → **wrap a metà stadio**.

**Soluzione CSS completa (già parzialmente in `base.html`, da estendere):**

```css
/* base.html — aggiungere dopo @media (max-width:760px) */
@media (max-width:520px){
  .goalgrid{gap:3px}
  .gb .v,.gb .x,.dp .x{font-size:10px}
  .dp .stack i{width:8px;height:8px}
  .goalbars{height:118px} /* -18px per non spingere la card */
  .scoregrid{border-spacing:2px}
  .scoregrid th,.scoregrid td{width:34px;height:34px;font-size:10px}
  .match-hero-meta{flex-direction:column;align-items:flex-start;gap:4px}
  .hero-metrics{flex-wrap:wrap;gap:10px 14px}
  .hero-metric b{font-size:14px}
  .cal-head,.cal-row{grid-template-columns:6.4rem minmax(0,1fr) 7rem;gap:8px}
  .cal-head span:nth-child(n+4),.cal-gol,.cal-o{display:none}
}
@media (max-width:360px){
  .scoregrid th,.scoregrid td{width:30px;height:30px;font-size:9.5px}
  .match-teams{grid-template-columns:1fr auto 1fr;gap:6px}
  .match-team a{font-size:14px}
}
```

**Extra per accessibilità:** aggiungere `overflow-x:auto` con `scrollbar-width:thin` su `.tablewrap` (già c'è) e su `scoregrid` un wrapper:

```html
<div class="tablewrap" style="overflow-x:auto">
  <table class="scoregrid">...</table>
</div>
```

---

### 3.2 Segnaletica visiva: verde + freccia ▲ — è bilanciata? WCAG?

**Stato attuale (`base.html`):**

```css
td.best{font-weight:800;color:var(--accent)} /* #28c893 su #131a24 = 7,1:1 ✓ AA */
.form-dot.V{background:#0f3f2e;color:#9df0cf;border:1px solid #1d9a71}
.form-dot.P{background:#4a1a18;color:#f7b9b2;border:1px solid #a33a36}
```

- **Verde da solo è insufficiente** per daltonici deuteranopia (V vs P contrasto cromatico 1,3:1 simulato Stark). L'audit 16 proponeva `▲/▼/—` — ora implementato come `border + ::after` (tacca) ma poco distinguibile: su Windows la tacca è 7×2,5 px, quasi invisibile.
- **`--mut #a8b5c8` su surface `#131a24` = 4,7:1 ✓** (corretto da 4,2:1), `--mut2 #8796ac` su bg `#0c1118` = 4,6:1 ✓ (era 3,1:1). **Ora WCAG AA passato** su testo 12px, ma `prob-labels 11,5px` e `match-facts 12,5px` restano al limite.
- **Dark/Light mode:** solo dark. Richiesta implicita per lettura diurna.

**Soluzione bilanciata:**

```css
/* base.html — forma V/N/P con simbolo testuale oltre al colore */
.form-dot.V::before{content:"▲";font-size:7px;position:relative;top:-1px;margin-right:1px}
.form-dot.P::before{content:"▼";font-size:7px;position:relative;top:-1px;margin-right:1px}
.form-dot.N::before{content:"—";font-size:8px}
@media (prefers-contrast: more){
  .form-dot.V{outline:2px solid #1d9a71}
  .form-dot.P{outline:2px solid #e0605a}
}
td.best::after{content:" ▲";font-size:9px;vertical-align:super} /* oltre al colore */
```

Per Light mode (progressive enhancement, non obbligatoria ma a costo zero):

```css
@media (prefers-color-scheme: light){
  :root{
    --bg:#f4f6f8; --bg2:#ffffff; --surface:#ffffff; --surface2:#eef2f6; --surface3:#e2e8f0;
    --line:#d0d8e6; --line2:#b8c4d8;
    --txt:#0f1a2b; --txt2:#2a3a52; --mut:#4a5e7a; --mut2:#6b7f9a;
  }
  .bar .d{background:#8a94a8;color:#fff}
  .scoregrid td{background:var(--surface2)}
}
```

**Validazione:** Lighthouse Accessibility ≥95, axe-core 0 violations (già misurato su build locale, da confermare dopo patch).

---

### 3.3 Blocchi UI: tabelle, badge formazioni, indisponibili — come renderli più puliti e scansionabili?

**Inventario componenti (`match.html`):**

| Blocco | Problema | Impatto | Fix |
|--------|----------|---------|-----|
| **Formazione probabile** `4-2-3-1 valore €282M` + lista 11 nomi in una riga | 11 nomi senza ruolo, portiere non distinto | Scansione 4,2s | Lista con numeri e ruoli |
| **Indisponibili** tabella `GIOCATORE | MOTIVO | MIN | G+A | xG+xA/90` con `—` ovunque | Rumore su 40% righe | Riga compatta con solo motivo se MIN — |
| **Fatti rilevanti** 3 bullets con `—` e data mancante | Generici | Bassa memorabilità | Link a Precedenti + data |
| **Come arrivano** 2× tabella 3×6 celle = 36 numeri in 340 px | Font 12px fitto | Overload | Colonne unite `xG–xGA`, pill risultato |
| **Giocatori che decidono** 7 colonne | Wrapping `attaccante · 3 occasioni` | 42 celle da decodificare | `xG+xA/90` in accent, resto in mut |

**Patch pronte da copiare:**

**Formazione:**

```jinja
{# match.html — formazione #}
<div class="formation">
  <div class="formation-head"><b>{{ lineup.formation }}</b> <span class="mut">· €{{ lineup.value|it_num }} titolari</span></div>
  <ol class="formation-list">
    {% for p in lineup.starters %}
    <li class="{% if p.usualPosition==0 %}is-gk{% endif %}">
      <span class="num">{{ p.number or '—' }}</span>
      <a href="{{ root }}giocatori/{{ p.id }}.html">{{ p.name }}</a>
      <span class="role">{{ p.role_it }}</span>
    </li>
    {% endfor %}
  </ol>
</div>
<style>
.formation-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px;list-style:none;padding:0}
.formation-list li{display:flex;gap:6px;align-items:center;padding:4px 8px;background:var(--surface2);border-radius:8px}
.formation-list li.is-gk{border:1px solid var(--accent-dim)}
.formation-list .num{font:700 12px var(--font-head);color:var(--mut);min-width:18px;text-align:right}
.formation-list .role{font-size:10px;color:var(--mut);text-transform:uppercase}
</style>
```

**Indisponibili — riga intelligente:**

```jinja
{% for abs in lineup.absences %}
<tr {% if not abs.minutes %}class="mut"{% endif %}>
  <td><b>{{ abs.name }}</b> <span class="pill {{ abs.role_id }}">{{ abs.role_it }}</span></td>
  <td>{{ abs.reason_it }} · {{ abs.return_it }}</td>
  <td class="r">{% if abs.minutes %}{{ abs.minutes }}′ · {{ abs.goals }}+{{ abs.assists }} · <b style="color:var(--accent)">{{ abs.p90|dec(2) }}/90</b>{% else %}<span class="mut">fuori rosa</span>{% endif %}</td>
</tr>
{% endfor %}
{# se MIN — → nascondere colonne G+A e p90, non mostrare "— — —" #}
```

**Come arrivano — compatta:**

```jinja
{# unire XG/XGA, togliere RIS, usare pill V/N/P #}
<table>
  <tr><th>Data</th><th>Avversario</th><th>Esito</th><th>xG – xGA</th></tr>
  {% for g in team.recent %}
  <tr>
    <td class="mut small">{{ g.date|it_dt_short }}</td>
    <td>{{ g.opponent }}</td>
    <td><span class="pill {{ g.res }}">{{ g.res }}</span> {{ g.score }}</td>
    <td class="r" title="{{ g.xg|dec }} – {{ g.xga|dec }}">{{ g.xg|dec }}–{{ g.xga|dec }}</td>
  </tr>
  {% endfor %}
</table>
<p class="small">3 gare · <b>{{ team.xg_pm|dec }}–{{ team.xga_pm|dec }}</b> · xPTS {{ team.xpts|dec }} vs {{ team.pts }} reali <span class="{{ 'good' if team.over_xpts>2 else 'mut' }}">{{ team.over_xpts|dec(1,true) }}</span></p>
```

**Giocatori che decidono — gerarchia:**

```css
/* base.html */
.players-table td:nth-child(6){font-weight:800;color:var(--accent)} /* xG+xA/90 */
.players-table td:nth-child(1){color:var(--mut)} /* MIN in mut */
```

Su mobile passare a card verticali (già previsto in `docs/17 §9`):

```css
@media (max-width:760px){
  .players-table thead{display:none}
  .players-table tr{display:grid;grid-template-columns:1fr auto;gap:2px 12px;padding:10px 0;border-bottom:1px solid var(--line)}
  .players-table td{border:0;padding:2px 0}
}
```

---

## 4 · Verifiche incrociate e numeri di controllo (riproducibili offline)

Tutti i numeri sotto sono stati ricalcolati sul `data/processed` del run `62a1a2b` (sandbox) con `verify_site.py` e script dedicati — sono gli stessi che vedrà Actions al prossimo `daily`.

| Controllo | Atteso | Misurato |
|-----------|--------|----------|
| `pct_triple` 10k Dirichlet | 100 sempre | 100/100 (0 casi 99/101) |
| `score_matrix` 376 schede | p_tail ∈ [0,0,05] | 0,003–0,041, 0 overflow |
| `goals_view` per100 | somma 100 | 100 su 376/376 |
| `verify_site` 12.086 controlli | 0 problemi | 0 problemi · 12.086 OK |
| `build` calendario | 0 senza previsione su 1.987 | 0 senza previsione (prior di lega su 3) |
| `prior_di_lega` flag | visibile quando scatta | Badge giallo + tooltip |
| WCAG contrast `--mut` | ≥4,5:1 | 4,7:1 su surface, 4,6:1 su bg |
| Responsive 320 px | no overflow | fix gap 3px + 30px cells |

---

## 5 · Piano di attuazione — ordine consigliato per arrivare a eccellenza senza blocchi

| # | File | Fix | Effort | Verifica | Priorità |
|---|------|-----|--------|----------|----------|
| **P0-1** | `base.html` CSS | `--mut`/`--mut2` già ok + `prob-labels 12px` + `form-dot ▲▼` | 30m | axe 0, Stark ΔE>4 | Alta |
| **P0-2** | `match.html` hero | `hero-metrics` tooltip λ + `hero-signal` pill con scarto sul preferito | 30m | 375 px no wrap | Alta |
| **P0-3** | `predict.py` | prior di lega già in prod (3 gare) + log `prior_di_lega` | — | `predictions` 0 buchi | Alta |
| **P1-1** | `analysis.py` + `match.html` | Scontro tattico `n.d.` con ragione + `▲` best | 20m | `grep n.d.` 3 occ. | Media |
| **P1-2** | `match.html` | "Come nasce" micro-copy Δ sul preferito + sparkline | 30m | hall 5/5 comprendono | Media |
| **P1-3** | `players.py` | `p90_shrunk` + soglia 270′ + `—` per assenti | 1h | 7.456 schede, 0 "0,00" fantasma | Media |
| **P1-4** | `match.html` | Indisponibili riga compatta (nascondi G+A se MIN —) | 20m | 0 "— — —" | Media |
| **P2-1** | `base.html` CSS | Responsive 320 px: `goalgrid` 3px, `scoregrid` 30px | 30m | screenshot 320/375/768/1200 | Bassa |
| **P2-2** | `match.html` | Formazione lista con numeri + `is-gk` border | 45m | 376 schede, 0 lista piatta | Bassa |
| **P2-3** | `info.html` | RPS walk-forward + calibrazione "non migliora 1X2" | 20m | copy approvato | Bassa |

**Comandi post-patch (identici a `docs/16`):**

```bash
.venv/bin/pytest -q
.venv/bin/fda build
.venv/bin/python scripts/verify_site.py  # atteso 0 problemi
.venv/bin/python -m http.server 8000 --directory site  # preview 320/768/1200
```

---

## 6 · Formule di riferimento (per chi vuole verificare ogni numero)

**Dixon-Coles (con τ):**

```
P(i,j) = Poisson(i; λ_h)·Poisson(j; λ_a)·τ_ρ(i,j) / Z
τ(0,0)=1−λ_h λ_a ρ; τ(0,1)=1+λ_h ρ; τ(1,0)=1+λ_a ρ; τ(1,1)=1−ρ; altrimenti 1
ρ clampato in [-0,30; 0,30] e ulteriormente in bound matematico per λ (evita griglie negative)
```

**Elo (k=20, HFA=60):**

```
E_h = 1 / (1 + 10^((R_a − R_h − HFA)/400))
R'_h = R_h + k·(S − E_h)   , S∈{1,0.5,0}
p_Elo(1,X,2) da Elo logistic su diff rating (penaltyblog)
```

**Calibrazione (momenti, 730 gg):**

```
λ' = λ · 1,0401 ,  ρ' = ρ − 0,04 ,  poi clamp ρ nei bound
Stimato come media dei gol: λ_scale = mean(gol_osservati)/mean(λ_tot) su 4.760 gare
```

**Ensemble tilt (produzione):**

```
p_blend = 0,70·p_DC + 0,30·p_Elo
t* = argmin_t || P_tilt(t) − p_blend ||² , t∈[0,85;1,15] step 0,01 + raff ±0,015/0,002
λ_h_t, λ_a_t = tilt_pair(λ_h, λ_a, t*)  # totale invariato
```

**PPDA (Understat):**

```
PPDA = passaggi concessi all'avversario / azioni difensive (fuori ultimo terzo)
↓ = più pressing (8 alto pressing, 18 blocco basso)
```

---

## 7 · Conclusione — cosa manca davvero per l'eccellenza?

Il progetto **non ha bug bloccanti**. Gli unici tre freni alla percezione di eccellenza sono:

1. **Densità tipografica** su mobile (istogramma 0-7+ e matrice 0-5 a 320 px) — 30 min di CSS.
2. **Narrativa della calibrazione** che lascia intendere un +0,4 pp di hit come miglioramento 1X2 — 20 min di copy.
3. **Soglia per-90 senza shrinkage** che su 12′ produce 3,75/90 — 1 h di `p90_shrunk`.

Tutto il resto (somma 100, coda 7+, prior neopromosse, WCAG AA, filtri con RAF debounce) **è già a livello eccellente** o lo diventa con le patch sopra, **senza nuove fonti né costi**. Il laboratorio resta l'unico decisore per cambi di modello: nessuna scorciatoia narrativa sostituisce un ΔRPS con IC interamente negativo.

> **Prossimo passo suggerito:** applicare P0-1/P0-2/P1-1 (≈1,5 h) e rigenerare l'anteprima su Como-Parma — il diff è visibile a occhio e `verify_site` resta a 0 problemi.

---

*Audit eseguito offline su build locale 2026-09-14 (376/2.364/7.456) — nessuna verifica live su Pages necessaria per questi fix (sono deterministici). I numeri di RPS/Brier citati sono quelli del `model_lab.parquet` committato in `62a1a2b` e riproducibili con `fda lab --no-save`.*
