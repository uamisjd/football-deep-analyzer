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

---

## F. Implementato (2026-09-12, stesso giorno del piano)

Richiesta utente: «falli tutti… senza errori», priorità **giocatori e assenze**. Fatto questo giro,
con le coperture misurate sul sito generato (`scripts/verify_site.py`, passo `[5]`).

### F1. Card nuove nelle schede partita (pre-partita)

| Card | Cosa mostra | Fonte e copertura | Regola di degradazione |
|---|---|---|---|
| **Come arrivano** | ultime gare con **xG e xGA a confronto**, risultato, avversario, esito V/N/P; xG e xGA per gara, **punti fatti contro xPTS**, PPDA, split casa/trasferta, tendenza (ultime 3 contro le precedenti) | Understat (38 squadre di oggi) → fallback FotMob `team_stats` (14 squadre: NED1/POR1). Avversario recuperato dal calendario: **191/191 righe** | sotto 3 gare con xG la card non compare; PPDA solo da Understat |
| **I giocatori che decidono** | **(xG+xA) per 90** con minuti, gol, assist, xG, xA, occasioni create (anche clamorose) e media voto; sotto, la classifica per media voto di stagione | `player_stats` FotMob, **7/7 leghe** (xG/xA non esistono in Understat per NED1/POR1) | soglia di minutaggio **relativa** (40% dei minuti del più impiegato, min 90′): chi non ha nessuna riga xG/xA non entra in classifica (non è «a zero», è senza dato) |
| **Infermeria pesata** | per ogni assente: **ruolo**, motivo, rientro previsto, **minuti di stagione**, gol+assist, **xG+xA per 90**, marchio «titolare»; in testa alla tabella quanti titolari abituali mancano e quanti xG+xA a partita perde la squadra | `lineup` (1340 indisponibili, ruolo dedotto) + `player_stats` | 248 assenti oggi: **99 con ruolo**, **81 con statistiche di stagione**; sotto la soglia il valore per 90 non si stampa |
| **Precedenti completi** | tutti i precedenti in archivio (non 5): V/N/P dal punto di vista della squadra di casa attuale, gol a gara, **BTTS%**, **Over 2,5%**, risultati più frequenti, da quanti scontri manca il pareggio, arco temporale con le date complete | `h2h`: **103 schede verificate**, media 19 precedenti (min 2, max 43) | sotto 3 precedenti niente card; la riga riassuntiva FotMob è soppressa quando l'archivio è completo (i due conteggi coincidono: Lazio-Milan 12/12/16 da entrambe le fonti) |
| **Arbitro a confronto** | gialli e falli a gara dell'arbitro **contro la media del campionato** e il numero di designazioni | `match_info`: 77/77 nomi, 60/77 statistiche | senza statistiche resta solo il nome, nessuna stima |
| **Fatti rilevanti** | tetto alzato da 3 a **5** per partita | `insights`: 7,5 fatti/partita in archivio | invariata: solo testi traducibili, mai inglese |

### F2. Liste (oggi / prossime / risultati)

Ogni riga futura mostra **«Infermeria: <casa> N assenti · <trasferta> M assenti»** (conteggio dalla
distinta, un solo `groupby` su `lineup`): il dato più cercato è leggibile senza aprire la scheda.

### F3. Correzioni nate dall'implementazione

- **Difetto 19** (`docs/10_…`): ruoli spostati di uno — codifica FotMob `usualPosition` da **0**, non da 1.
- **`pivot_table(dropna=False)` faceva il prodotto cartesiano** dei livelli dell'indice (18 giocatori →
  324 righe con nomi incrociati): sostituito con `groupby().unstack()`. Senza questa correzione le
  statistiche di stagione venivano attribuite al giocatore sbagliato.
- Plurali: «1 clamorose» → «1 clamorosa»; intestazione «40 Precedenti» → «Precedenti (40)».
- Nuovo filtro `it_dt_full` (data con anno nel fuso italiano) per l'arco dei precedenti.

### F4. Verifiche di questo giro

- `pytest -q` → **101 passed** (9 test nuovi in `tests/test_oggi_depth.py`: codifica dei ruoli,
  catena di risoluzione del ruolo, trend da Understat e fallback FotMob, precedenti dal punto di vista
  della squadra di casa attuale con riga anomala scartata, classifica per contributo con soglia
  relativa, infermeria pesata, arbitro contro media di lega, chiavi esposte da `build()`).
- `fda build` → 347 partite + 2364 fixture + 7388 giocatori.
- `scripts/verify_site.py` → **4056 pagine, 0 problemi, 1082 controlli numerici** (nuovo passo `[5]`:
  648 ruoli, 108 infermerie, 103 archivi di precedenti ricontrollati contro le tabelle).

### F5. Secondo giro (stesso giorno): post-partita, statistiche di dettaglio, mercati

Tutto ciò che era elencato come «resta da fare» è stato implementato nello stesso giorno.

| Novità | Cosa mostra | Copertura misurata sul sito generato |
|---|---|---|
| **Assist e tipo di gol in cronaca** | «⚽ Rasmus Højlund · *assist di Giovanni Di Lorenzo* · 0-2», con «di testa», «rigore», «punizione diretta», «rovesciata» dove la fonte lo dice | **534 assist su 752 gol** (71%), nome risolto dalla distinta della stessa partita nel 100%; tipo di gol su **143** gol (gli autogol non ripetono «autogol») |
| **Primo e secondo tempo** | xG, tiri, tiri in porta, possesso, angoli, grandi occasioni per tempo | **239/239** partite finite, 7/7 leghe |
| **I portieri** | parate, **gol prevenuti** (xG subito − gol incassati), errori che hanno portato a un gol, rigori parati | **239/239**; il portiere è chi ha `saves`/`goals_prevented` — validato: **478/478** con ruolo 0 in distinta (prima versione pescava i difensori: van Ewijk al posto di Raya) |
| **Dati fisici** (condizionale) | distanza in km, sprint, metri in sprint, giocatore più veloce con km/h | **30 partite** (FotMob li pubblica solo lì): la card compare solo quando i dati esistono |
| **Statistiche di dettaglio** | le altre 23 voci FotMob: tiri da dentro/fuori area, xG azione manovrata vs palle inattive, duelli (a terra/aerei), intercetti, rinvii, tiri bloccati, dribbling, cross, lanci, passaggi per metà campo, legni, fuorigioco | **239/239**, due colonne per non allungare la pagina |
| **Accuratezza per mercato** | per 9 mercati (Over 1,5/2,5/3,5, BTTS, doppie chance 1X/12/X2, porte inviolate): previsto vs osservato, **Brier**, Brier della frequenza di base, Δ, scelte indovinate | 28 gare valutate |

**Risultato scomodo ma pubblicato**: sui 9 mercati il modello **batte la frequenza di base solo su
doppia chance 1X (Δ −0,0223) e porta inviolata in trasferta (Δ −0,0139)**; sugli altri il Brier è
peggiore del riferimento, e la causa è visibile nella stessa tabella: dichiara Over 2,5 al 56,0%
contro un osservato del 64,3% (sottostima dei gol, coerente con il difetto di shrinkage già corretto
nel codice ma non ancora nelle previsioni pubblicate). Campione di 28 gare: va riletto dopo qualche
giornata di run.

### F6. Verifiche del secondo giro

- `pytest -q` → **106 passed** (+5 test post-partita: assist/tipo di gol, split 1T/2T, portiere
  che esclude i giocatori di movimento, fisiche condizionali, statistiche di dettaglio).
- `fda build` → 347 partite, 2364 fixture, 7388 giocatori.
- `scripts/verify_site.py` → **4056 pagine, 0 problemi, 1855 controlli numerici**; nuovo passo `[6]`
  che ricontrolla **534 assist** contro gli eventi (con la grafia del nome della stessa partita:
  lo stesso `player_id` ha grafie diverse fra le giornate) e **239 split 1T/2T** contro `team_stats`.

### F6b. Rilettura dal vivo dopo il merge (run `daily` 21:30 UTC del 12/09)

PR #23 mergiata in `main` (`6124bb3`, 19:41:12 UTC); il sito pubblicato contiene tutte le nuove
sezioni (verificate su `partite/5749674.html`, Lazio 2-2 Milan). Con **50 gare valutate** la tabella
per mercato dà una lettura più solida di quella locale a 28:

- RPS complessivo **0,2203** contro 0,2282 della base naive (Δ **−0,008**).
- Sottostima dei gol confermata: Over 2,5 **57,4% dichiarato contro 62,0% osservato**, BTTS
  **57,5% contro 72,0%**, doppia chance X2 **56,1% contro 74,0%**.
- Il modello batte la frequenza di base **solo su doppia chance 1X** (Δ −0,0052).
- Calibrazione per esito sbilanciata sulla casa: **44,0% previsto contro 26,0% osservato**,
  pareggio 24,0% contro 40,0%.

Da qui il prossimo passo analitico: ricalibrare vantaggio casa e λ dei gol, usando questa tabella
come verifica (ogni modifica si legge subito nei Δ per mercato).

### F6c. Intervalli di confidenza sulla pagina accuratezza (rigore statistico)

La lettura del turno precedente («il modello sottostima i gol») era basata su differenze fra previsto
e osservato **senza incertezza campionaria**: su 50 gare una differenza di 10 punti è spesso rumore.
Ora `build_accuracy()` pubblica l'**intervallo di Wilson al 95%** della frequenza osservata e un
segnale per riga (`compatibile` / `fuori intervallo`), sia nella tabella per mercato sia in quella di
calibrazione (dove compare anche il conteggio `k/n`). Funzione: `wilson_interval(k, n, z=1.96)` in
`src/fda/site/build.py`; verificata dal blocco **[7]** di `scripts/verify_site.py` (ricalcola gli
intervalli pubblicati e la coerenza del segnale) e da `test_wilson_interval_bounds_and_coverage`.

Lettura corretta con gli intervalli (50 gare live del 12/09):

| riga | previsto | osservato | intervallo 95% | esito |
| --- | --- | --- | --- | --- |
| vittoria in casa | 44,0% | 26,0% (13/50) | 15,9 – 39,6% | **fuori** |
| pareggio | 24,0% | 40,0% (20/50) | 27,6 – 53,8% | **fuori** |
| vittoria in trasferta | 32,0% | 34,0% (17/50) | 22,4 – 47,8% | compatibile |
| Over 1,5 / 2,5 / 3,5 | 78,9 / 57,4 / 37,0% | 86,0 / 62,0 / 46,0% | 73,8–93,0 / 48,2–74,1 / 33,0–59,6% | **compatibili** |
| Gol entrambe a segno | 57,5% | 72,0% (36/50) | 58,3 – 82,5% | **fuori** |
| Doppia chance 1X | 67,8% | 66,0% | 52,2 – 77,6% | compatibile |
| Doppia chance 12 | 76,0% | 60,0% | 46,2 – 72,4% | **fuori** |
| Doppia chance X2 | 56,1% | 74,0% | 60,4 – 84,1% | **fuori** |
| Porta inviolata casa / trasferta | 27,4 / 21,7% | 20,0 / 14,0% | 11,2–33,0 / 7,0–26,2% | compatibili |

**Correzione rispetto al turno precedente:** gli Over 1,5/2,5/3,5 e le porte inviolate **non** sono
scostamenti significativi su 50 gare; l'unico segnale solido sui gol è **BTTS sottostimato**. I due
segnali forti restano la **calibrazione 1X2 sbilanciata sulla casa** (casa sovrastimata, pareggio
sottostimato — sono due facce dello stesso difetto) e la **doppia chance**: 12 sovrastimata, X2
sottostimata, di nuovo coerente con l'eccesso di peso alla vittoria in casa. 5 righe su 12 fuori
intervallo a α = 0,05 (attese ~0,6) è già di per sé un segnale reale.

Regola adottata: **nessuna correzione dei parametri senza almeno ~150 gare valutate e scarto
confermato nella stessa direzione**. Il campione cresce da solo (~15-20 gare/giorno con i run
`daily`), quindi la verifica è ripetibile senza toccare il modello.

### F6d. Backtest cronologico fuori campione (campione ampio per la calibrazione)

La tabella per mercato cresce solo con i run giornalieri (~15-20 gare/giorno): per decidere se
correggere un parametro servono centinaia di gare, e soprattutto stime che **non** abbiano visto il
risultato. Nuovo modulo `src/fda/models/backtest.py`:

- `chronological_backtest(hist, step_days=14, min_train=200, ...)` cammina sullo storico di ogni lega
  a finestre di `step_days`: il modello (Dixon-Coles + Elo, stessi parametri di `fda predict`,
  shrinkage compreso) è allenato **solo** sulle partite precedenti l'inizio della finestra e valuta
  quelle successive. Squadre mai viste nello storico sono saltate (stesso `KeyError` di `predict`).
- `backtest_summary(df)` → RPS contro la base naive, Brier, log-loss, esito azzeccato, calibrazione
  1X2 e 9 mercati binari, tutti con **intervallo di Wilson e segnale** (stessa funzione della pagina).
- Comando **`fda backtest [LEGHE] --seasons-back 3 --step-days 14 --min-train 200`** → tabella
  `backtest`; è incluso in `fda daily`, quindi i numeri reali li produce GitHub Actions (che ha rete),
  come vuole la regola B.6.
- Sulla pagina **Accuratezza** compare la card «Backtest storico fuori campione», **condizionale**:
  senza tabella non si vede niente (nessun segnaposto).
- Verifica automatica: blocco **[8]** di `scripts/verify_site.py` (riconteggia le gare e ricalcola
  l'RPS con `predict.rps`, percorso indipendente da `backtest_summary`).
- Test `tests/test_backtest.py` (8): **assenza di leakage** (un modello-spy registra l'ultima data di
  allenamento e la restituisce in ogni previsione: per ogni gara `_train_max < data gara`), squadre
  sconosciute saltate senza perdere il resto della finestra, metriche ricalcolate in modo indipendente,
  definizione degli esiti osservati, card presente/assente, finestre configurabili.

**Stato della verifica (regola B.2):** l'intera catena è verificata **offline su dati sintetici**
(storico generato con Poisson, 14 squadre × 3 stagioni): 63 gare fuori campione, RPS 0,2015 contro
0,2282 della base, log-loss 0,9997, tutte le righe «compatibile», blocco [8] verde. **Non è una
misura del modello sul calcio reale**: i numeri veri arriveranno dal primo `fda daily` con rete, e da
lì si legge se lo scarto sulla vittoria in casa regge su migliaia di gare o era rumore.

### F7. Resta aperto (dichiarato)

1. **Le previsioni pubblicate** cambiano solo al primo `fda predict` con la rete: la tabella dei
   mercati va riletta allora (atteso: Over/Under più calibrati dopo lo shrinkage corretto).
2. **Metriche fisiche** su 30 partite: la copertura dipende dalla fonte, non da noi.
3. **`goals_prevented`/`errors_led_to_goal`** mancano su alcune partite (93/239 per gli errori):
   il «—» a schermo significa «non registrato dalla fonte», non zero (nota nella card).
