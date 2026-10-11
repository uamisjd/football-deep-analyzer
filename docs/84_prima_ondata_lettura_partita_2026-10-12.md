# 84 — Prima ondata di lettura della partita (2026-10-12)

> Richiesta dell'utente: «ti lascio scegliere a te, ma fai le cose nel modo migliore: deve dare
> tantissimo valore nella lettura della partita per scegliere il pronostico». Il lavoro parte dalla
> revisione dei 12 punti dell'esperto (`docs/` di questa sessione, punti 1–12) e applica la prima
> ondata: le correzioni con misura chiara e rischio basso. Le altre restano in coda (§5).

## 1. Che cosa cambia

| Punto | Prima | Ora | Dove |
|---|---|---|---|
| 12 · griglia gol | barre fisse 0–6, coda «7+» | barre finché la coda residua è sotto l'1% (minimo 6, massimo 11) | `advanced.py` · `adaptive_goals_cap` |
| 6 · trend xG | «in crescita/calo» con soglia fissa ±0,15 | direzione solo oltre 2 errori standard della differenza di medie (σ 0,83); altrimenti «nessuna tendenza chiara» | `analysis.py` · `arrival_trend`, `_trend_label`; `match.html`; `verify_site.py` |
| 7a · indisponibili | «I giocatori che decidono» includeva chi non gioca la gara in programma | esclusi gli indisponibili nella **prossima gara** della squadra | `analysis.py` · `_unavailable_next_match` |
| 7b · jolly | non esisteva | sottosezione «Jolly dalla panchina»: ≥5 subentri con minuti, media ≥10′, sopra la media dei subentrati, stima stabilizzata | `analysis.py` · `bench_jolly`; `match.html` |
| 1 · hero | chip «4,0× valore titolari» con la frase «prior che migliora Brier di ~0,02» (non verificata qui) | chip con l'effetto misurato sull'archivio: scaglione, percentuale di vittorie del più ricco, IC 95% | `analysis.py` · `market_bucket`, `market_sentence`; `match.html` |

## 2. Misure che hanno guidato le scelte

Tutte ricalcolate sui Parquet del repo il 2026-10-12.

- **Trend xG.** Su 92 stagioni squadra con almeno 5 gare Understat, mescolando a caso l'ordine delle gare (nessun trend vero), la regola vecchia dava «in crescita» o «in calo» nell'84% dei casi. Con il margine di 2 errori standard il rumore scende sotto il 5%. Conseguenza voluta: le etichette direzionali diventano rare, e la pagina mostra i numeri.
- **EMA a 10 partite (scartata).** Su 78 previsioni dell'xG della gara successiva l'errore quadratico medio dell'EMA a 10 è più alto dell'8,3% rispetto alla media di stagione; la media delle ultime 5 è allo stesso livello (-0,09%). Campione piccolo: non si adotta finché non c'è un backtest più ampio.
- **Coda dei gol totali.** Poisson sul totale: a λ totale 3,5 la coda oltre 6 gol pesa il 14%, oltre 7 gol il 6,5%. Con il limite fisso la barra «7+» era una coda troppo grossa.
- **Indisponibili.** Juventus: Locatelli è «unavailable» (infortunio, rientro «Late March 2027») nella distinta di Juventus–Lazio (match 5749705). Con il filtro esce dai decisivi. Il filtro non usa lo stato dei fixture: Cagliari–Juventus dell'11/10 risulta ancora «scheduled» il 12/10 (dato in ritardo), quindi la «prossima gara» è la prima con calcio d'inizio non passato da più di 3 ore.
- **Jolly.** 3.789 presenze da subentrato con minuti reali (media 20,1′). Con soglia 5 subentri e media ≥10′ restano 91 giocatori; con la condizione «sopra la media dei subentrati» emergono jolly in 18 squadre su 40. Pool dei subentrati: 0,42 xG+xA per 90; dei titolari: 0,22. Per questo lo shrinkage punta al pool dei subentrati.
- **Effetto del valore titolari.** Sulle 387 gare con valori di entrambe le formazioni: rapporto ≥1,5× → 55% di vittorie del più ricco (IC 49–60%, n 275); sotto 1,5× → 38% (n 112). Per scaglione: 1,0–1,5× 37% (n 112) · 1,5–2,0× 33% (n 59) · 2,0–3,0× 46% (n 56) · 3,0–5,0× 52% (n 71) · oltre 5× 75% (n 89).

## 3. Correzioni a testi scritti a mano

- Il testo della card fattori diceva che l'effetto «cresce in modo monotono». **Falso sull'archivio attuale**: lo scaglione 1,5–2× (33%) è sotto quello 1–1,5× (37%). La frase ora è calcolata, e dichiara che il rapporto non cresce in modo regolare.
- Il chip diceva «prior che migliora Brier di ~0,02»: quel numero viene da un altro progetto e non è stato verificato sull'archivio qui. È stato tolto.
- La nota di `docs/60` sulla finestra a 5 gare resta vera per i valori mostrati, ma il trend usa ancora 3 contro 2: la correzione è in §1.

## 4. Verifiche

- `pytest`: 643 test verdi (baseline 637; 6 nuovi test, 4 aggiornati perché codificavano la regola vecchia).
- `ruff`: pulito sui file toccati.
- `fda build` e `scripts/verify_site.py`: nessun problema · 233.318 controlli superati. Il verificatore ricalcola ora l'etichetta del trend con lo stesso margine.
- `scripts/parita_schede.py`: nessuna differenza fra le schede pre-partita. Il blocco jolly compare solo dove ci sono jolly (22 pagine), quindi non cambia il numero di card.

## 5. Coda (non fatta in questa ondata)

- **3 · semaforo Verde/Giallo/Rosso** sui fattori: da fare con le soglie `FACTOR_*` già in codice, senza giudizi di esito.
- **9 · posizione virtuale della partita** dal Monte Carlo condizionato sull'esito di quella gara.
- **11 · frase del waterfall** generata dal segno dei contributi, con controllo di direzione.
- **8 · ruoli.** Il fallback interno copre il 68% degli indisponibili (397 su 583). Il restante 32% (186) non compare mai come titolare o subentrato nell'archivio: serve una fonte esterna, da valutare per licenza e copertura (`docs/02`).
- **4 · radar.** Dichiarare la fonte di ogni asse; asse «n.d.» coerente fra le due colonne. Eredivisie e Primeira non hanno PPDA (Understat non le copre).
- **5 · stringhe non tradotte.** Report dei candidati ordinato per frequenza; le traduzioni le approva un umano in PR. Nessuna traduzione automatica nel build.
- **2 · testo.** Varianti di frase per scenario con validatore dei numeri, non un LLM nel build.
- **10 · clima.** Campione annotato di titoli italiani prima di qualsiasi punteggio. VADER è addestrato sull'inglese: non si usa.
- **Non previsti:** value bet (decisione `docs/38`: le quote non si pubblicano).

## 6. Dato da segnalare

Lo stato dei fixture resta «scheduled» per partite già giocate (es. Cagliari–Juventus dell'11/10 il 12/10). Il problema sta nel pipeline di aggiornamento degli stati, non nelle card: lo lascio come segnalazione, da verificare nel collect.
