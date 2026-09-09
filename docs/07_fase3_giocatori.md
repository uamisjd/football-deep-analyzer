# Fase 3 — Schede giocatore (progetto e ricerca)

> **Stato:** progetto approvato e implementato nella sessione `arena/01a0864d` (2026-09-09). Roadmap `01` §8, fase 3: «schede giocatore, rating e xG/xA per 90, confronto radar, percentili di lega».
> Direttiva utente collegata: profondità e parità completa tra le 7 leghe, nessun dato inventato, distinzione presente/atteso/mancante.

## 1. Ricerca e dati misurati (2026-09-09, dati del run `99ba9ee`)

### Cosa abbiamo già (nessuna nuova fonte per il nucleo della fase)

| Tabella | Contenuto | Misura |
|---|---|---|
| `player_stats` | statistiche per partita per giocatore (formato lungo: `key`/`value`/`total`) | 127.880 righe · 134 partite · 2.301 giocatori · 67 chiavi |
| `lineup` | anagrafica per partita: ruolo (starter/sub/unavailable), posizione, età, paese, valore, `season_rating`, capitano, infortunio + rientro | 3.587 giocatori distinti |
| `fixtures` | calendario canonico con `league_id` corretto | 7 leghe, stagione completa |
| `understat_players` | stagione xG/xA/xGChain (solo 5 leghe) | 1.954 righe — **non usata** per le schede (parità 7/7) |

Verifiche puntuali sui dati:
- **Chiavi dense** (copertura ~100% dei giocatori con ≥90'): `minutes_played`, `rating_title`, `goals`, `assists`, `accurate_passes`(+`total`), `interceptions`, `recoveries`, `clearances`, `duel_won`/`duel_lost`, `aerials_won`, `chances_created`, `total_shots`, `ShotsOnTarget`, `expected_goals`, `expected_goals_non_penalty`, `expected_assists`, `dribbles_succeeded`, `touches`, `passes_into_final_third`, `defensive_actions`.
- **Portieri**: `saves`, `saves_inside_box`, `keeper_high_claim`, `keeper_sweeper`, `punches`, `goals_conceded`, `expected_goals_on_target_faced` (133/135), `goals_prevented` (133/135).
- **Semantica `key` assente = 0 eventi** (verificato: `expected_goals` presente solo con valore > 0 su 1.272 giocatori, nessuno a 0,00) → i conteggi mancanti si coalescono a 0 (non è un'invenzione, è la semantica della fonte).
- **Posizione**: `lineup.usual_position_id` ∈ {0,1,2,3} mappato su Portiere/Difensore/Centrocampista/Attaccante. Inchiodato per incrocio con le posizioni Understat su 1.539 giocatori: 0→GK 87/90, 1→D 382/485, 2→M 324/524, 3→F 150/458 (le righe «S» di Understat sono ambigue e distribuite, la diagonale domina). **Verificato offline su dati reali.**
- **Minuti** (aggregati per giocatore): ≥90' = 1.145 giocatori; ≥180' = 434; mediana 89'. A inizio stagione i campioni sono piccoli: ogni numero mostra le gare di riferimento.

### Metodologia di riferimento (ricerca web, direttiva «verifica prima di integrare»)

- **Radar a percentili per lega+ruolo** è la prassi (mplsoccer `Radar` con `rank(pct=True)*100`; tutorial che filtrano stessa lega + stesso ruolo): i valori mostrati sono percentili 0–100, non valori grezzi. «Lower is better» va capovolto (es. gol subiti per un portiere) — mplsoccer `lower_is_better`.
- **Per 90 + soglia minuti**: FBref normalizza a per-90 e le analisi serie applicano soglie di minuti per evitare distorsioni da campioni piccoli; DataMB usa 7 metriche per posizione con percentili calcolati «League and Position per 90».
- **playerData?id=** (FotMob, catalogo `02` + doc `pseudo-r/Public-FotMob-API` `docs/endpoints/players.md`, stato VERIFIED): anagrafica, `recentMatches` con rating, `careerHistory`. Costo ~1 richiesta/giocatore: **rimandato alla fase 3b** (arricchimento anagrafica/infortuni storici) perché il nucleo è già coperto dai dati raccolti; TTL 168h già configurato in `sources.yaml`.

## 2. Decisioni di progetto

1. **Fonte unica per le statistiche di stagione: `player_stats` FotMob** (parità 7/7: Understat non copre NED1/POR1). Ogni scheda dichiara «FotMob, N gare».
2. **Backfill esteso a tutte le leghe** (prima solo NED1/POR1): ogni partita finita di stagione viene scaricata una sola volta (TTL 10 anni). Costo misurato: **97 richieste una tantum** per il catch-up (stagione in corso), poi ~10/lega a giornata, dentro il budget 600/run. Effetti: statistiche giocatore complete dall'1ª giornata **e** report completi per tutte le partite finite (schede partita storicizzate).
3. **Soglia percentili: ≥90 minuti**; popolazione = stessa lega + stesso ruolo, **≥90 minuti**, minimo 8 pari-ruolo con dato (altrimenti «n.d.» onesto). Statistiche «lower is better» capovolte (gol subiti/90). Zero-eventi = 0 nella popolazione.
4. **Radar SVG** (6 assi per ruolo, percentili): generato lato Python (punti poligono) e disegnato dal template, come cartina tiri e momentum — nessuna dipendenza nuova (mplsoccer resta solo ispirazione metodologica).
5. **Pagine**: `giocatori/index.html` (hub 7 leghe), `giocatori/<lega>.html` (tabellone con filtro testo/ruolo, JS vanilla ~20 righe), `giocatori/<player_id>.html` (scheda). Link dalle schede partita («da tenere d'occhio», «migliori in campo»). Nav: voce «Giocatori».
6. **Onestà**: giocatore senza minuti → scheda anagrafica + «non ancora sceso in campo»; campione piccolo → avviso «campione ridotto» se minuti < 270; ogni valore percentilato mostra N pari-ruolo; il log partite linka solo pagine partita esistenti.
7. **Media voto**: media dei rating di partita (`rating_title`) ponderata sui minuti giocati (formula dichiarata a piè di scheda).

### Insieme di statistiche per ruolo (percentili, per 90 salvo ratio)

- **Portiere**: media voto, parate, gol prevenuti, uscite alte, gol subiti (inv.), xGOT affrontato.
- **Difensore**: media voto, intercessioni, palloni recuperati, duelli vinti %, respingimenti, xA.
- **Centrocampista**: media voto, occasioni create, xA, passaggi riusciti, dribbling riusciti, palloni recuperati.
- **Attaccante**: media voto, xG, gol, tiri nello specchio, xA, occasioni create.

La tabella «Stagione» mostra totali + per 90 per un insieme più ampio (passaggi, falli, tocchi, area avversaria…), con 0 onesti per gli eventi nulli.

## 3. Verifiche

- **Offline (questa sessione)**: suite pytest (aggregazioni, per-90, percentili con popolazione minima e stat invertita, punti radar entro i limiti, V/N/P del log, pagine costruite con segnaposto onesti, zero inglese, decimali con virgola) + build locale su dati reali + `ruff` senza nuove segnalazioni.
- **Dal vivo (dopo il merge, primo run `daily`)**: `player_stats` passa da 134 a ~231 partite (catch-up completo), schede giocatore con stagione completa, `source_status` senza errori nuovi. Da lì le gare valutate crescono a ogni giornata.

## Prossimo passo

Fase 3b (opzionale): arricchimento anagrafica da `playerData` (contratto, trofei, storico infortuni, `recentMatches` FotMob) con rotazione settimanale (~3.300 giocatori / TTL 168h ≈ 80 richieste/run), dopo verifica dal vivo del costo reale.
