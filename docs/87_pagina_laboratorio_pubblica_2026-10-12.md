# 87 — Pagina pubblica «Laboratorio dei modelli» (2026-10-12)

**Richiesta:** migliorare il sito con integrazioni utili, partendo dal rilancio del laboratorio (docs/86).

**Cosa è cambiato**
- Nuova pagina `laboratorio.html` (linkata da «Accuratezza»; nessuna voce nuova nel menu). Mostra
  le 30 ricette testate: RPS, Δ RPS vs produzione con IC 95%, campionati in cui battono la produzione,
  verdetto, e RPS per campionato delle ricette più in alto.
- I verdetti sono calcolati da `src/fda/site/lab_page.py` con il criterio di `docs/13` §6.5, non scritti a mano.
  Le etichette pubbliche tolgono i rimandi interni ai documenti.
- Test: `tests/test_lab_page.py` (5 test). Sitemap aggiornata.

**Esito pubblicato:** produzione invariata; 5 varianti superano il criterio, nessuna promossa.

**Verifiche**
- `fda build` completo; `scripts/verify_site.py`: 0 problemi · 235.696 controlli.
- `ruff check .` pulito. Test pagina: 5 passati.
- Visivo a 1280 px e 390 px: nessun overflow della pagina; tabelle scorrono nel contenitore.

**Non fatto:** nessuna variante promossa; nessun nuovo dato esterno.
