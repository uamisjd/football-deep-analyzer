# Perfezionamento scheda partita — Como vs Parma (caso campione) · 2026-09-14

> Audit mirato sulla sola **scheda partita** a partire dagli screenshot Como-Parma (18:30, Stadio G. Sinigaglia). Obiettivo: portare ogni blocco da “informativo” a **editoriale di livello prodotto**: gerarchia, densità giusta, zero ripetizioni, logica esplicita e verificabilità immediata.

## Metodo
Ispezione delle 9 sezioni viste + `src/fda/site/templates/match.html` (hero → contesto). Ogni punto: **Osservazione → Impatto → Patch esatta** (file + snippet). Priorità P0 = leggibilità/accuratezza rotta, P1 = ordine/logica, P2 = densità/estetica.

---

## 1 · Hero (Como vs Parma, vs 18:30, 63% / 1,77-0,69 / 45% / 42%)

**Osservato:**
- riga top `lun 14/09/2026 18:30 - Stadio...` in 12px `mut` su una sola riga → su 375px va a capo spezzando stadio e orario
- `ESITO PIÙ PROBABILE 63%` + `Margine sul secondo: +39,1 punti (Pareggio 24%)` corretto ma “39,1 punti” senza spiegare che sono **punti percentuali**
- metriche `1,77-0,69 Gol attesi · 45% Over · 42% Btts` in tre pill isolate, senza unità né tooltip; `Stesso preferito · scarto 4,5 punti` a destra staccato, sembra un tag secondario invece è il **confronto modelli**

**Impatto:** primo colpo d’occhio dice “chi è favorito” ma non *di quanto* e *perché* — l’utente non distingue margine sul secondo da scarto DC vs Elo.

**Patch P0 - `match.html` hero-model:**
```jinja
<div class="hero-model">
  <div class="hero-pick">
    <span class="eyebrow">Esito più probabile</span>
    <strong>Como <em>63%</em></strong>
    <span class="small mut">di 39 punti sul secondo — Pareggio 24% · 1 49% · 2 13% (scala 1X2)</span>
  </div>
  <div class="hero-metrics">
    <span class="hero-metric" title="λ Dixon-Coles+Elo calibrate, non media xG ultime 3"><b>1,77 – 0,69</b><span>gol attesi</span></span>
    <span class="hero-metric"><b>45%</b><span>Over 2,5</span></span>
    <span class="hero-metric"><b>42%</b><span>entrambe a segno</span></span>
  </div>
  <span class="hero-signal" title="Dixon-Coles 62,9% vs Elo 60,4% sullo stesso preferito (Como)">✓ Stesso preferito · scarto 2,5 pt</span>
</div>
```
+ CSS `hero-metrics b {letter-spacing:.02em}` e `hero-signal {max-width:190px; text-align:center; line-height:1.25}`

**P1 -** spezzare la riga top in due su mobile: `{{ c.utc_kickoff|it_dt }} · {{ c.stadium.name }}` → `@media(max-width:760px){.match-hero-meta{flex-direction:column; align-items:flex-start}}`

---

## 2 · Analisi pre-partita (7 bullets)

**Osservato:**
- 7 punti a elenco puntato, tutti uguali tipograficamente: due “Assenze: 1 — …” identiche ma separate da “Parma in difficoltà: PPN…”, arbitro e meteo in fondo
- frasi utili ma isolate: “Parma crea quota alta xG palla inattiva 53%” non rimanda a *Scontro tattico* dove quel 0,31 vs 0,39 è tabellato
- manca il **filo logico**: favorito → perché (xG, forma, pressing) → cosa può smentirlo (assenze, precedente diretto)

**Impatto:** lettura lineare senza priorità; l’utente non capisce se “PPN (1 punto)” è grave.

**Patch P1 - raggruppare in 3 fasce con icone + cross-link:**
```html
<div class="narr-groups">
  <p><b>Quadro:</b> Como nettamente favorito (63%) — crea 1,83 xG/gara (Understat) vs 0,58 Parma.</p>
  <p><b>Cosa pesa:</b> 53% xG Parma da inattiva · arbitro Mucera nella media (3,24 gialli, media camp. 4,16) · meteo soleggiato 27°C</p>
  <p><b>Freni:</b> Assenze 1+1 (Addai / Nicolussi) · Parma 1 pt nelle ultime 3 (PPN)`</p>
</div>
```
+ togliere bullet singolo, usare `p.small` con `·` e link `→ vedi Scontro tattico` su “53% inattiva”.

**P2 -** aggiungere micro-badge forma accanto a squadra in hero: `Como [N V V] 7pt` — riduce ripetizione sotto.

---

## 3 · Previsione del modello (sinistra) + Risultati esatti (destra)

**Osservato:**
- barra 1·63% / X·24% / 2·13% corretta ma tabella sotto ha `GOL ATTESI 1,77 0,69` senza dire *cosa* è 1,77 (casa) e 0,69 (trasferta) — mancano le teste colonna “Como / Parma”
- righe `OVER 1,5/2,5/3,5 71/45/23%` allineate a destra ma senza barra di contesto; `DOPPIA CHANCE 87/76/37%` ridondante con 1X2 ma utile — va resa secondaria
- footer “Sono stime… addestrato su 1177 partite…” troncato dal watermark Windows su screenshot, in `mut small` su 2 righe → illeggibile
- destra: `1-0 14,5%` etc. senza evidenziare che 1-0 e 2-0 sommano 27,9% (≈ 1 su 4)

**Patch P0:**
- aggiungere `thead` leggera: `<th>Como</th><th>Parma</th>` su riga Gol attesi
- `OVER` con mini-barra grigia sotto i numeri (`width: %` in `var(--line2)`)
- `PORTA INVIOLATA 50%/17%` spostare in secondario (`opacity:.8; font-size:12px`)

**P1 - footer:** spezzare in due righe:
```
Stime Dixon-Coles pesato + Elo (70/30) · 1.177 gare · 14/09 11:27 (ora ITA)
λ su ~1.200 gare pesate, non media ultime 3 (→ “Come arrivano”)
```

---

## 4 · Come nasce questa probabilità (3 barre)

**Osservato:** perfetto come idea (1·61% → 62,4% → 62,9%) ma `Δ +1,4 pp peso DC 70%` è criptico; `λ ×1,04 (momenti, ultimi 730gg su 4760 gare)` pure. Le tre barre sono identiche in altezza, il salto è solo nel testo.

**Patch P1:**
- rinominare: `1. Solo gol (DC)` / `2. + Rating Elo (70/30) Δ+1,4pt` / `3. + Calibrazione Δ+0,4pt (bias gol -0,13 → -0,02)`
- aggiungere **sparkline delta** sotto ogni barra: `▁▂▃` visivo del +1,4
- tooltip: “Dopo l’Elo il preferito resta Como ma sale di 1,4 punti; la calibrazione aggiunge 0,4”

---

## 5 · Matrice dei punteggi 0-5

**Osservato:** matrice 6×6 leggibile, verde ben scalato, cella 1-0 evidenziata (14,5%). Ma header `0 1 2 3 4 5` senza etichette “gol Parma” / “gol Como”, e `Coda 6+: 1,0%` in didascalia piccola staccata. Su mobile i numeri `9,1` diventano `9` per troncamento.

**Patch P1:**
- header colonna con `aria-label="Gol Parma"` e riga con `aria-label="Gol Como"`
- celle con `font-variant-numeric: tabular-nums; letter-spacing:.02em` già ok, alzare a 12px su mobile per evitare troncamento
- aggiungere riga sotto: `Somma riga 1 (Como 1 gol): 14,5+11,0+3,6… = 30,1%` — aiuta a leggere

---

## 6 · Quanti gol, in pratica (istogramma 0-7+ + dotplot)

**Osservato:** histogram alto 20/27/21/13/6/3/1 è chiaro; testo sopra “mediana 2 e nel 90% resta fra 1 e 5” è ottimo. Dotplot sotto però usa stessi colori ma con 2-3 puntini per colonna su sfondo scuro → poco contrasto su 1 e 6 (3 e 1 punto). Descrizione “20 punti, ognuno vale 5 partite” è corretta ma lunga.

**Patch P1:**
- allineare colonne histogram e dotplot con `grid-template-columns: repeat(8,1fr)` identico (già fatto, verificare gap)
- puntini `background: var(--accent)` → aggiungere `border:1px solid var(--bg)` per contrasto su fondo scuro
- compattare descrizione: `Mediana 2 · 90% fra 1 e 5 · 7+ al 1,3%` come **kpi row** sopra histogram, non frase lunga

---

## 7 · Scontro tattico

**Osservato:** tabella 11 righe, best evidenziato in verde (`1,77` `1,29` `-1,10` `1,83` `1,05` `0,39` …). Righe PPDA / passaggi profondi con `—` per Parma (manca Understat) lasciano buco visivo. Legenda in fondo su 4 righe, poco scansionabile.

**Patch P0:**
- per `—` mostrare `n.d.` con `title="Understat non copre questa lega per Parma (FotMob fallback senza PPDA)"` + riga attenuata `opacity:.5`
- unità in header: `xG/gara`, `PPDA ↓`, `profondi/gara` già ok, aggiungere `Difesa DC ↓` con freccia per dire “più basso = meglio”
- best: oltre al verde, aggiungere `▲` piccolo accanto al valore migliore (non solo colore, WCAG)

**P1 -** raggruppare in sottosezioni: `Modello | Stagione xG | Pressing & profondità` con `tbody` separati e `border-top:1px solid var(--line2)` leggera

---

## 8 · Fatti rilevanti + Come arrivano

**Osservato:**
- Fatti: 4 bullets tradotti bene (“non perde da 5…”, “11 gol nelle ultime 5”) ma generici; manca data (“da 5 incontri” quali?)
- Come arrivano: due card Como/Parma con tabella DATA/AVVERSARIO/ES/RIS/XG/XGA su 3 gare ciascuna, poi riga “3 gare, 1,83-1,36” e “PPDA 13,7”. Parma tabella con `0,75 vs Cagliari` etc. Tutto corretto ma denso: 3×6 celle = 18 numeri in 340px → font 12px fitto.

**Patch P1:**
- Fatti: aggiungere `→ vedi Precedenti (5V 3N)` come link su “non perde da 5”
- Come arrivano: compattare colonne `XG | XGA` in una sola `xG – xGA` con `1,83–1,36`; togliere colonna `RIS.` (già in `ES.`) e usare `pill V/N/P` cliccabile con tooltip `1-1 @Udinese 2,39-2,12`
- riga sintesi: `7 pt vs 5,1 xPTS (+1,9)` con colore `good` se over-performance >2

---

## 9 · I giocatori che decidono

**Osservato:** due tabelle con 7 colonne `MIN GOL ASSIST XG XA xG+xA/90 VOTO` — 7×3 righe = 42 celle, font 11px, pos “attaccante · 3 occasioni” su due righe → wrapping. Soglia `108 minuti` corretta ma in fondo piccola. Colonna `xG+xA/90` è la chiave ma ha stesso peso visivo di `MIN`.

**Patch P0:**
- evidenziare `xG+xA/90` con `font-weight:800; color:var(--accent)` e `MIN` in `mut`
- `POS` come badge `pill small` sopra nome: `Douwikas — [ATT] · 3 occ.` invece di due righe
- tooltip su `xG+xA/90`: “(1,41+0,18)/246′×90 = 0,58” — rende verificabile

**P1 -** su mobile passare a card verticali: ogni giocatore una riga con `nome — 0,58/90 — 7,37` e dettagli in `small mut`

---

## 10 · Forma / Stagione / Indisponibili / Formazione

**Osservato:**
- Forma `N V V 1-1 @Udinese…` stringa lunga senza separatore; `Stagione 1,83/1,36 xPTS 5,1 vs 7 reali` su una riga illeggibile su 375px
- Indisponibili: tabella `GIOCATORE | MOTIVO | MIN | G+A | xG+xA/90` con `—` ovunque (perché 108′ soglia non raggiunta) → rumore
- Formazione `4-2-3-1 valore €282M` + lista 11 nomi in una riga senza distinzione ruolo/portiere

**Patch P1:**
- Forma: `N V V` come `form-dots` già usati sopra + `1-1 @Udinese · 2-1 @Napoli · 4-1 v Genoa` con `·` e `pill` per risultato
- Stagione: spezzare `xG 1,83 – xGA 1,36 · xPTS 5,1 vs 7 pt (+1,9)` con `+1,9` in `good`
- Indisponibili: se `MIN —` → nascondere colonne `G+A` e `xG+xA/90` (mostrare solo `Motivo` + `fine settembre 2026`) per non inquinare
- Formazione: lista con numeri `1` portiere in bold + `value` sotto come `€282M titolari` con `title="Somma Transfermarkt titolari"`

---

## 11 · Confronto di stagione

**Osservato:** tabella 9 righe, valori Como in verde (`6`, `2,33`, `1,60`, `0,69`). Corretto ma “6” (posizione) in verde sembra “buono” ma non dice su 20 squadre; “2,33 punti/gara” vs “0,33” già chiarissimo. `ATTACCO × MEDIA` `1,60 vs 0,23` è ottimo ma senza scala.

**Patch P2:**
- aggiungere mini-barra accanto a `POSIZIONE`: `6ª su 20` con `width: (20-6)/20`
- `ATTACCO ×1,60` con `title="1,60× la media gol del campionato (1,46)"` — rende concreto
- attenuare il verde su `POSIZIONE` (è ordinale, non metrica) → lasciare verde solo su metriche continue

---

## 12 · Contesto (Arbitro / Meteo / Precedenti 10 + Ultimi 5)

**Osservato:**
- Arbitro: `Mucera (17 gare) - 3,24 gialli (media 4,16 su 40) · 25,65 falli (27,21) · 2 rigori · 2 rossi` — denso, tutto in una riga
- Meteo: una riga, ok
- Precedenti: `3V Como -4 pareggi -3V Parma — 28/11/2021 al 17/05/2026` poi `2,10 gol/gara … 1-1 (3 volte)` — buono
- Ultimi 5: tabella con `V N V N N` a destra, ma `Serie A` ripetuto 5 volte

**Patch P1:**
- Arbitro: spezzare in `Gialli/gara 3,24 (camp. 4,16) · Falli 25,6 (27,2) · Rigori 2 · Rossi 2 · 17 gare` con `camp.` in `mut small`
- Precedenti: aggiungere **mini-donut** 30%V 40%N 30%P accanto a numeri
- Ultimi 5: togliere colonna `Serie A`, mettere `17/05/2026` come sotto-riga `small mut`, pill `V/N` con `title="Como 1-0 Parma, 1° gol Diao 23'"`

---

## Piano di attuazione (ordine consigliato)

| # | File | Fix | Effort | Verifica |
|---|------|-----|--------|----------|
| P0-1 | `match.html` hero | tipografia + tooltip λ + signal come pill | 30m | 375/1200px no wrap |
| P0-2 | `match.html` scontro | `n.d.` con title, ▲ su best | 20m | `grep n.d.` 3 occ. |
| P0-3 | `templates/_matchlist.html` | `punti sul secondo` (fatto), fact SVG (fatto) | — | `verify_site 0` |
| P1-1 | `match.html` analisi | raggruppa in 3 fasce + link a Scontro | 45m | leggere <12s |
| P1-2 | `match.html` previsione | thead Como/Parma + mini-bar Over | 30m | axe 0 |
| P1-3 | `base.html` CSS | `hero-metrics` gap, `fact` 12px lh1.45 (fatto) | — | Lighthouse AA |
| P2-1 | `advanced.py` goals_view | kpi row `Mediana 2 · 90% 1-5` sopra histogram | 20m | screenshot 320/768 |
| P2-2 | `match.html` giocatori | `xG+xA/90` accent, badge ruolo | 45m | 3 OS pixel diff |

**Vuoi che applichi ora questi patch e rigeneri l’anteprima live?** Posso partire da P0-1/P0-2 (≈1h) e mostrarti il diff su Como-Parma in tempo reale.

