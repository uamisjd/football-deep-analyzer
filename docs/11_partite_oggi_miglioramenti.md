# Come migliorare le partite della sezione «Oggi» — analisi e piano (2026-09-12)

> **Domanda:** «sulle partite della sezione "oggi" si può fare altro? come si possono migliorare le
> schede? servono analisi, notizie, informazioni, dati, statistiche, trend, pattern».
> **Metodo:** censimento di ciò che la sezione mostra oggi, incrociato con **tutte** le colonne delle
> 17 tabelle in `data/processed` e con la loro copertura reale sulle **32 partite di oggi** e sulle
> **77 in programma nei prossimi 7 giorni**. Ogni percentuale qui sotto è misurata sui dati del
> commit `cb68f5a` (run del 12/09), non stimata.

---

## A. Fotografia attuale (misurata)

**La riga nella sezione «Oggi»** mostra: ora (italiana ✓), lega, le due squadre, il punteggio o la
data, la barra 1X2, «Il modello punta su X (n%)», λ casa–trasferta, Over 2,5.

**La scheda partita pre-partita** ha 10 sezioni: Previsione del modello, Risultati esatti, Matrice dei
punteggi, Scontro tattico, Fatti rilevanti, Giocatori da tenere d'occhio, Confronto di stagione,
Contesto (forma, xG di stagione, riposo, indisponibili, formazione probabile, meteo), Precedenti,
Arbitro.

Copertura dei dati sulle **77 partite future**:

| Dato | Copertura | Già a schermo? |
|---|---|---|
| distinta probabile (`lineup`) | 77/77 partite, 138 squadre | sì (formazione + valore XI) |
| meteo (desc, °C, pioggia, vento) | 77/77 | sì (vento **no**) |
| stadio + capienza | 77/77 | stadio sì, **capienza no** |
| arbitro | 77/77 nome; 60/77 gialli, rigori, falli/gara | nome e gialli sì, **falli/gara no** |
| previsione completa (1X2, λ, O1.5/2.5/3.5, BTTS, 1X/12/X2, clean sheet, 6 risultati, Elo) | 77/77 | solo 1X2, λ, O2.5, doppia chance, risultati esatti |
| precedenti H2H | 75/77, **media 19 scontri** (min 2, max 43, 61 partite con ≥10) | **solo gli ultimi 5** + gol/gara e BTTS |
| `insights` FotMob | 77/77, **media 7,5 fatti** per partita | **solo 3** |
| classifica FotMob | 132/132 squadre (rank, punti, gol, DR) | **no** |
| valore di mercato / età dei giocatori | 90% / 100% delle righe distinta | solo il valore totale della XI |

---

## B. Dati già raccolti e **non mostrati** (il giacimento)

### `team_stats` — 40 chiavi, ne usiamo 13. Copertura sulle 478 squadre-partita finite:

| Chiave non mostrata | Copertura | Cosa racconta |
|---|---|---|
| `opposition_half_passes` / `own_half_passes` | 478/478 | **territorio**: dove si è giocata la partita |
| `duel_won`, `ground_duels_won`, `aerials_won` (con %) | 478/478 | intensità e duelli aerei |
| `interceptions`, `clearances`, `blocked_shots`, `shot_blocks` | 478/478 | fase difensiva |
| `dribbles_succeeded` (con %), `accurate_crosses` (%), `long_balls_accurate` (%) | 478/478 | come si crea |
| `keeper_saves`, `shots_woodwork`, `Offsides`, `player_throws`, `passes` | 478/478 | dettagli di gara |
| `expected_goals_non_penalty` | 478/478 | xG al netto dei rigori |
| periodi **`FirstHalf` / `SecondHalf`** di ogni chiave | 478/478 | **split primo/secondo tempo** (oggi usiamo solo `All`) |
| `physical_metrics_distance_covered`, `number_of_sprints` | **60/478 (12,5%)** | km e sprint — card condizionale, mai placeholder |

### `player_stats` — 56 chiavi per giocatore per partita (230.666 righe, 7/7 leghe)

Oltre a gol/assist/minuti/voto, non usate: `expected_goals`, `expected_assists`, `xg_and_xa`,
`chances_created`, `big_chance_created_team_title`, `big_chance_missed_title`, `goals_prevented`,
`saves`, `saved_penalties`, `errors_led_to_goal`, `conceded_penalties`, `penalties_won`,
`missed_penalty`, `last_man_tackle`, `line_breaking_passes`, `passes_into_final_third`,
`touches_opp_box`, `dribbled_past`, `dispossessed`, `shot_accuracy`, `physical_metrics_topspeed`.
Sono la base per le analisi sui singoli **su tutte e 7 le leghe** (Understat ne copre solo 5).

### `events`

- `assist_player_id`: presente su **535/753 gol (71%)** e **risolvibile in nome nel 100% dei casi**
  tramite `lineup` → la cronaca può diventare «⚽ Arcus (assist van den Boomen)».
- `goal_description`: 166/753 (22%) — «Header», «Penalty», «Direct freekick», «Overhead kick»:
  utile dove c'è, da omettere dove manca.

### `predictions` (già calcolati, in parte non pubblicati)

`p_over15`, `p_over35`, `p_home_clean_sheet`, `p_away_clean_sheet`, `elo_p_home/draw/away`,
`fair_home/draw/away`, `n_train`, `dc_attack/defence` di entrambe. La **differenza DC−Elo** è un
segnale di confidenza pronto all'uso: sulle 32 di oggi supera gli 8 punti in **5 partite**
(Mainz–Frankfurt +25, Chelsea–Hull −24, Cambuur–NEC −19, Dortmund–Paderborn −12, Twente–ADO +10).

---

## C. Piano ordinato (per valore, con copertura e regola di degradazione)

### P0 — dentro la riga della sezione «Oggi» (nessun dato nuovo, copertura piena)

1. **Posizione in classifica**: «3ª (6 pt) vs 13ª (1 pt)» — `fotmob_standings` 132/132.
2. **Forma**: ultimi 5 esiti in sequenza «V V N P V» + punti — da `fixtures`, 100%.
3. **Grado di confidenza del modello**: badge «DC ed Elo concordano» / «segnale debole (Δ 12 pp)» —
   da `predictions`, 100%. È il modo onesto di non far leggere un 57% come una certezza.
4. **Assenze di peso**: «8 indisponibili, 3 titolari» — da `lineup` + rating di stagione.
5. **Contesto in una riga**: stadio (capienza), meteo, arbitro con gialli/gara — 77/77 (arbitro
   dettagliato 60/77: se manca, solo il nome).
6. **Precedenti in sintesi**: «31 scontri · 61% entrambe a segno» — 75/77.

### P1 — nuove card nella scheda pre-partita

7. **«Come arrivano» (trend, non solo risultati)**: xG/xGA per gara, PPDA, xPTS vs punti reali sulle
   ultime 5-6 partite. Fonte: `understat_team_matches` (5 leghe) **e** `team_stats` FotMob (7/7) →
   parità garantita.
8. **«Scontri diretti: pattern»**: sugli N precedenti (media 19) → gol/gara, % BTTS, % Over 2,5,
   margine medio, «il pareggio manca da n scontri», andamento casa/trasferta. Oggi ne mostriamo 5 su 19.
9. **«Giocatori decisivi»** (7/7 leghe): top 3 per squadra per `xg_and_xa` per 90, `chances_created`,
   `big_chance_created`, rating — con soglia minuti dichiarata (≥270') e «campione ridotto» sotto,
   come già fanno le schede giocatore. Per le 5 leghe Understat: anche `xg_chain`, `xg_buildup`,
   `key_passes`.
10. **«Quanto pesano le assenze»**: per ogni indisponibile, gol+assist e xG+xA di stagione che porta
    via → «senza X e Y: −0,9 xG/gara attesi». Dati: `lineup.unavailability_type` + `player_stats`.
11. **«Chi fischia»**: arbitro con gialli, rossi, rigori e falli/gara (60/77) **confrontati con la
    media di lega**, più quanti rigori ha concesso nelle ultime N gare. Dove manca: solo il nome.
12. **«Mercati del modello» in una card unica**: 1X2, doppia chance, Over 1.5/2.5/3.5, BTTS, porta
    inviolata, 6 risultati esatti, con la nota esplicita che sono stime del modello (le quote dei
    bookmaker non sono e non saranno esposte).
13. **Fatti rilevanti più ricchi**: oggi mostriamo 3 fatti su **7,5 disponibili** per partita;
    alzare a 5-6 mantenendo il filtro anti-hype già esistente.

### P2 — post-partita e laboratorio

14. **Cronaca con gli assist** (71% dei gol, nome risolto nel 100% dei casi).
15. **Statistiche avanzate post-partita** (478/478): territorio, duelli, aerials %, dribbling,
    intercetti, spazzate, parate, pali/traverse, xG non-penalty, fuorigioco.
16. **Split primo/secondo tempo** (478/478): xG e tiri per frazione → «squadra che parte lenta».
17. **Metriche fisiche** (12,5% di copertura): km e sprint **solo** dove ci sono, senza placeholder.
18. **Portieri**: `goals_prevented`, `saves`, `errors_led_to_goal`, `saved_penalties` nella lettura
    della partita.
19. **Accuratezza per mercato**: oggi la pagina Accuratezza valuta solo l'1X2 (RPS 0,2193 su 28 gare);
    aggiungere Over 2,5 e BTTS (log loss) e la calibrazione per mercato.

### Cosa **non** fare

- Niente dati inventati o interpolati per riempire una card: se manca, si dichiara «atteso dalla
  fonte» o la sezione non compare (regola di progetto).
- Nessuna quota/bookmaker (indicazione esplicita dell'utente).
- Nessuno scraper nuovo pesante (FBref/SofaScore): tutto il P0-P2 sta nei dati già raccolti.
- Nessuna card che funzioni su 5 leghe e 7 no senza dichiararlo (parità 7/7).

---

## D. Esempio lavorato: i segnali derivabili **oggi** sulle 32 partite

Tabella costruita solo con dati già nel repo (nessuna fonte nuova). `pos` = posizione in classifica,
`forma` = punti nelle ultime 5, `ΔElo` = scarto DC−Elo in punti percentuali, `h2h` = precedenti
disponibili, `ass` = indisponibili casa/trasferta.

| Ora | Lega | Partita | pos | forma | 1 | X | 2 | λ | O2.5 | BTTS | ΔElo | h2h | ass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14:00 | ESP | Racing Santander–Deportivo Alavés | 13/2 | 4-10 | 45% | 22% | 34% | 1.93/1.66 | 69% | 69% | +1 | 8 | 2/3 |
| 15:00 | ITA | Genoa–Frosinone | 19/7 | 0-6 | 40% | 25% | 35% | 1.54/1.41 | 56% | 59% | −6 | 8 | 2/0 |
| 15:30 | GER | Augsburg–Leverkusen | 1/8 | 6-3 | 25% | 23% | 52% | 1.30/1.96 | 64% | 63% | −8 | 31 | 5/6 |
| 15:30 | GER | Dortmund–Paderborn | 3/13 | 6-1 | 57% | 37% | 6% | 1.02/0.19 | 12% | 11% | −12 | 8 | 8/5 |
| 15:30 | GER | Mainz–Frankfurt | 5/14 | 4-1 | 75% | 12% | 13% | 4.02/1.89 | 93% | 84% | +25 | 32 | 6/3 |
| 16:00 | ENG | Crystal Palace–Ipswich | 13/14 | 3-3 | 63% | 20% | 17% | 2.40/1.19 | 70% | 64% | +2 | 11 | 5/3 |
| 16:00 | ENG | Chelsea–Hull | 4/3 | 6-7 | 25% | 34% | 40% | 0.80/1.08 | 29% | 38% | −24 | 9 | 5/11 |
| 16:00 | ENG | Liverpool–Fulham | 6/19 | 5-0 | 60% | 21% | 19% | 2.33/1.29 | 70% | 67% | −1 | 22 | 6/1 |
| 16:30 | NED | FC Twente–ADO Den Haag | 5/17 | 10-1 | 75% | 14% | 11% | 3.37/1.36 | 85% | 72% | +10 | 19 | 2/2 |
| 18:00 | ITA | Lazio–Milan | 3/5 | 9-7 | 35% | 27% | 38% | 1.27/1.34 | 49% | 53% | −7 | 40 | 6/2 |
| 19:00 | POR | Casa Pia AC–FC Porto | 18/1 | 1-15 | 11% | 16% | 73% | 0.79/2.39 | 61% | 49% | −4 | 9 | 0/5 |
| 20:45 | ITA | Atalanta–Cagliari | 8/9 | 6-6 | 62% | 21% | 17% | 2.11/1.01 | 60% | 56% | 0 | 28 | 3/5 |
| 21:00 | NED | Cambuur–NEC Nijmegen | 18/9 | 1-7 | 15% | 13% | 71% | 1.89/3.75 | 92% | 83% | −19 | 19 | 1/8 |
| 21:00 | ESP | Real Madrid–Rayo Vallecano | 4/14 | 9-4 | 73% | 16% | 11% | 2.62/0.96 | 69% | 57% | +1 | 22 | 5/9 |

Estratto di 14 righe su 32 per leggibilità; l'elenco completo è riproducibile con i dati in
`data/processed`. Segnali aggregati sulle 32: **5** partite con ΔElo > 8 pp, **11** con BTTS storico
> 60% negli scontri diretti, **16** con Over 2,5 del modello > 60%, **25** con almeno 4 indisponibili
in una delle due squadre.

Due letture immediate che oggi il sito **non** rende visibili: Lazio–Milan ha **40 precedenti** in
archivio (ne mostriamo 5) e un 1X2 quasi pari nonostante il 3º contro 5º posto; Dortmund–Paderborn ha
λ 0,19 per il Paderborn, cioè il difetto di shrinkage corretto in PR #23 — è l'esempio di come un
numero pubblicato possa essere letto male senza contesto.

---

## E. Ordine di esecuzione consigliato

Un solo passo alla volta, ciascuno con i suoi controlli in `scripts/verify_site.py`:

1. **P0 (1-6)** — nessuna funzione nuova di modello, solo contesto: effetto immediato sulla sezione
   «Oggi», rischio minimo.
2. **P1 (7-13)** — una card per PR, con copertura dichiarata nel testo della card.
3. **P2 (14-19)** — post-partita e accuratezza per mercato.

Ogni card nuova deve superare: (a) 0 inglese, (b) 0 `nan`/placeholder, (c) parità 7/7 o copertura
dichiarata, (d) un controllo numerico nel verificatore del sito.
