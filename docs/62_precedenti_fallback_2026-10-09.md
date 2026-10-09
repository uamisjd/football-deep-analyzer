# 62 — Card «Precedenti» sempre presente: fallback quando manca l'h2h (2026-10-09)

Chiude il residuo dichiarato in `docs/61` §4 (gate `parita_schede` KO per schede senza
`#precedenti`). Metodo `docs/57`: misura → correzione → prova. Regola `docs/00` B.10.

## 1. Difetto (misura)

- La card Precedenti era resa **solo** in presenza di dati h2h
  (`match.html:464` `{% if c.h2h_pattern or c.h2h[0] is not none or c.h2h_list %}`), e così la
  sua ancora nell'indice (`match.html:57`). Senza h2h → card **e** ancora sparivano →
  `parita_schede` KO su due fronti: struttura (insieme di `id` non identico) e indice (ancore
  non uniformi).
- Il build è **dipendente dalla data reale** (`build.py:243` `datetime.now(UTC)`,
  `build.py:498` seleziona `local_date > today_local`): al avanzare della data entrano nel set
  «in programma» gare senza h2h. Nel dataset **1.924 fixture pre-match su 1.989** sono senza
  h2h; nel build del 09/10 le schede pre-match senza `#precedenti` erano 4-5.
- **Bug latente**: 2 schede pre-match (`5795468` Coventry–Newcastle, `5881187`
  Union Berlin–Elversberg) avevano bilancio `(0,0,0)` e rendevano
  «0 vittorie · 0 pareggi · 0 vittorie» — cioè *nessun incontro*, ma in forma di bilancio
  senza senso (74-79 caratteri visibili).

## 2. Correzione

- La card Precedenti rende **sempre**. Condizione «ha precedenti significativi»:
  `{% set incontri = (c.h2h[0] or 0) + (c.h2h[1] or 0) + (c.h2h[2] or 0) %}` /
  `{% set ha_precedenti = incontri > 0 or c.h2h_list or c.h2h_pattern %}` — esclude il caso
  degenere `(0,0,0)`, che ora cade nel fallback invece di rendere il bilancio vuoto.
- Senza dati: riga di fallback «Nessun precedente in archivio per questa sfida: tra {home} e
  {away} non risultano confronti diretti nelle stagioni coperte dai dati. Quando uno storico
  esiste, questa sezione raccoglie il bilancio…, i gol a gara, «entrambe a segno», Over 2,5 e
  l'elenco degli ultimi confronti…». Sono **367 caratteri** visibili: sopra la soglia di
  quantità di `parita_schede` (`SOGLIA_SEZIONE = 0.25` × mediana), quindi niente «presente ma
  vuota».
- Ancora `#precedenti` **sempre** presente: coerente con la direzione inversa di `check_nav`
  [33] (`scripts/verify_site.py`), che boccia una sezione presente ma fuori dall'indice.
- L'`{% endif %}` della card resta al suo posto (subito dopo il fallback, prima di
  `#previsione`): il cuore della scheda non è più annidato dentro la condizione h2h.

## 3. Prova (gate, tutti verdi)

- `pytest` → **540 passed**. Aggiornato `test_previsione_pubblicata_anche_senza_precedenti`:
  prima asseriva `'id="precedenti"' not in pre` (vecchio assunto «card condizionata ai dati»);
  ora asserisce che la card c'è e mostra «Nessun precedente in archivio». La garanzia centrale
  del test — Previsione e le altre sezioni pubblicate anche senza precedenti — resta invariata.
- `ruff check src tests scripts` → pulito.
- `fda build` → 446 schede, exit 0.
- `scripts/verify_site.py` → **nessun problema · 169.694 controlli numerici superati**.
- `scripts/parita_schede.py` → **exit 0**: struttura identica (24 id), indice uguale (14 voci),
  «Precedenti 367–1011», «nessuna differenza».
- `scripts/resa_375` → **26.606 misure · 0 problemi a 375 px**.
- Resa controllata a mano: `5749704` (senza h2h) e `5795468` (ex 0-0-0) mostrano il fallback;
  ancora `#precedenti` presente in entrambe.

## 4. Effetto

Il fix risolve **strutturalmente** la fragilità dipendente dalla data: ogni gara senza h2h ora
mostra la riga di fallback invece di rompere la parità di struttura/indice. Il gate `parita`
non dipende più da quali gare capitano nel set «in programma» quel giorno.
