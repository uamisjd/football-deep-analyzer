# Laboratorio analitico sulle schede partita

> **Stato:** implementato nella sessione `arena/01a092ab` (2026-09-12). Verificato **offline** su dati reali del run `7ab51fe` (343 pagine partita).
> Direttiva utente: analisi tecniche profonde, parità 7/7, nessun dato inventato.

## 1. Ricerca (prima di integrare)

Cosa mancava rispetto alla mappa di `01` §1.2 e a quanto mostrano i siti di riferimento:

| Analisi | Riferimento | Dati già in repo | Scelta |
|---|---|---|---|
| Matrice risultati 0–n (non solo top-6) | penaltyblog `FootballProbabilityGrid`; The Analyst / infogol | `predictions.lambda_*` + `dc_rho` | Griglia Dixon-Coles 0–5 + coda 6+ dichiarata |
| xG race | Understat, The Athletic | `shots` (6.576 tiri, 239 partite, `minute`+`xg`) | Cumulativo SVG, autogol esclusi |
| Open play vs set piece | FotMob `expected_goals_open_play` / `_set_play` (235/235 finite, 7/7 leghe) | `team_stats` + `shots.situation` | Media stagione + split tiri della gara |
| PPDA / deep | Understat (292 righe, 96 squadre) | `understat_team_matches` | Righe assenti se la fonte non copre |
| Win probability in-play | FiveThirtyEight SPI live; Dixon-Coles residuo | λ pre-partita + cronaca gol | Ricostruzione *post*, non live feed |

Nessuna fonte nuova: FotMob/Understat restano quelle già raccolte. Non si importa mplsoccer (SVG lato server, come cartina e radar).

**Scelta onesta sulla WP in-play.** ρ Dixon-Coles è una correzione da partita intera (0-0, 1-0, 0-1, 1-1). Scalarlo ai minuti restanti non è identificato: dopo il primo gol si usa Poisson indipendente sulle λ residue `λ × (90−t)/90`. Al 90' il risultato è certo. Documentato in `info.html`.

## 2. Cosa si vede

- **Pre-partita:** matrice dei punteggi; scontro tattico (λ, attacco/difesa DC, xG/xGA, xG azione vs palle inattive, PPDA, passaggi profondi).
- **Post-partita:** in più corsa xG, qualità dei tiri (xG/tiro, split, gol−xG, gol−xGOT), probabilità in-play se esistono gol *e* una previsione.

Degrada: niente λ → niente matrice/WP; niente tiri → niente corsa/qualità; niente Understat → PPDA/deep assenti (riga non mostrata).

## 3. Verifiche

- **Offline (questa sessione):** suite **81 passed** (8 test nuovi in `test_advanced.py` + e2e); ruff F,E pulito su `advanced.py` e `test_advanced.py`; `fda build` su dati reali → 343 partite; **0** residui `RegularPlay`/`FromCorner`/…; **0** `nan` standalone; matrice 101/101 partite con previsione; corsa xG e qualità **235/235** finite con tiri; WP **23/23** finite con previsione e gol.
- **Dal vivo:** al primo `daily` su `main` dopo il merge. Nessuna richiesta extra.

## Prossimo passo

PR verso `main` → merge utente. Poi, se si vuole spingere ancora: fase 3b `playerData`, o classifica «vera» (xPTS) a livello lega.
