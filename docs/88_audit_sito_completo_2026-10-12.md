# 88 — Audit completo del sito (2026-10-12)

**Richiesta:** migliorare il sito «in tutto», dopo ricerca e riflessione.

## 1. Misure (prima di cambiare)

**Tecniche, nel browser (390 px, Chromium headless, 8 pagine):** nessun errore in console, nessuna
richiesta fallita, nessun overflow orizzontale, `lang="it"` su tutte, un solo H1 per pagina, nessuna
immagine senza `alt` (il sito non usa `<img>`: i grafici sono SVG). Tempi di caricamento 45–141 ms.

**Peso:** 151 MB in 4.303 pagine. Di queste 3.801 sono schede giocatore (103 MB), 493 partite (46 MB).
`prossime.html` 469 kB (42 kB gzip), `risultati.html` 294 kB.

**Contenuto (lettura della home):** un problema reale di chiarezza. Il margine tra il primo e il
secondo esito è in **punti percentuali** (68% contro 20% = 48), ma il testo diceva «+48 punti sul
secondo», che un lettore italiano legge come punti in classifica. Lo stesso per «distanza 3,9 punti»
tra DC ed Elo.

## 2. Cosa ho cambiato

- Testo visibile: «+48 punti percentuali sul secondo», «punto percentuale» al singolare; «distanza X
  punti percentuali» nel segnale DC/Elo. Modificati: `_matchlist.html`, `match.html`, `analysis.py`.
- Controlli allineati: invariante di `verify_site.py` (concordanza e margine), `audit_match_sections.py`,
  `render_preview.py`, tre test.
- `ruff`: un import da riordinare nel modulo nuovo `lab_page.py`, corretto.

## 3. Verifiche

- `pytest`: **657 passati** (tutta la suite).
- `ruff check .`: pulito.
- `fda build` completo; `scripts/verify_site.py`: 0 problemi · 235.696 controlli.
- Nel sito generato: «favorito · +48 punti percentuali sul secondo» in `index.html`; il testo vecchio
  non compare più in `index.html` né in `prossime.html`.

## 4. Non fatto, e perché

Questi punti sono aperti da sessioni precedenti e richiedono una decisione o un lavoro più lungo.
Non li ho toccati per non peggiorare il sito senza misura (regola B.10 di `docs/00`):

- **Revisione delle sezioni della scheda partita** ancora da fare: «Panchina e posta in gioco»,
  «Mercato», «Vita del club», «Previsione del modello ensemble», «Precedenti», «Verifica approfondita».
- **«Forza avv.» anacronistica** in «Come arrivano»: usa la classifica attuale, non quella alla data
  della gara. Si risolve solo con uno storico di classifiche (oggi il sito non lo raccoglie).
- **Tre fattori «tilt» non cablati** nella previsione (mercato, assenze, riposo): restano candidati
  di laboratorio, come da `docs/57` §7.
- **Peso delle schede giocatore** (103 MB): non è un problema per GitHub Pages, ma è da considerare
  se il sito cresce.
- **Clima del club** (punto 10): decisione dell'utente.
- **StatsBomb** come validazione xG: decisione dell'utente su campionati e stagioni.
