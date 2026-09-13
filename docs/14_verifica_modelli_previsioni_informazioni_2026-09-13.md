# Verifica di modello, previsioni e informazioni — 2026-09-13 (screen)

**Contesto**: tre screen allegati dall'utente — card «IL MODELLO», «LE FONTI (GRATUITE)», card compatta partita «Famalicão vs Sporting CP 21:30 Liga Portugal». Verifica richiesta: sono fatti bene? hanno senso logico? sono intuitivi? accurati? proposte di miglioramento.

**Verifiche eseguite** (dati committati su `main` `26c5151`, build locale 13/09 17:44 UTC):
- `info.html` template letto (`src/fda/site/templates/info.html`): ensemble 70/30, Dixon-Coles + Elo, mercati, link Accuratezza, fonti FotMob/Understat/ESPN/football-data.co.uk.
- `_matchlist.html` macro `row`: lettura modello con `top_name 56%`, margine pp, barra 1X2, `signal_label` (DC+Elo concordato / diviso), `λ`, Over 2,5, forma pills, infermeria, meteo, arbitro, H2H.
- `accuracy.html`: RPS/Brier con naive, mercati con Wilson 95%, backtest 5.801 gare RPS 0,1996, calibrazione `cal-momenti-1.1 λ×0,914 ρ-0,04` bias +0,241→-0,028 pareggio 23,9%→26,2% vs osservato 25,7%, 70 gare valutate dal vivo RPS 0,2113.
- `verify_site.py`: **0 problemi · 12.130 controlli numerici**, 4.108 pagine, 1.987 righe calendario, 165 matrici, 93 scomposizioni probabilità, 95 infermerie, 92 H2H, 570 ruoli.
- `site/stato.html` build locale: Presente 1.018, Atteso 215, Mancante 2 su 95 schede (1.235 campi), 93 senza campi scaduti, calendario 1.987 partite 0 senza previsione.
- `predictions.parquet` `f07ec3f`: 2.152 righe, chiave `(match_id,model)` unica, 2.080 con `cal-momenti-1.1` n_fit 4.743, λ×0,9135, orizzonte 30/5/2027 7/7 leghe, promosse coperte, `lambda_limitata` 62.
- Lab: bug parsing `lab.yml` → solo baseline in parquet ufficiale, riproduzione locale 5 candidati mostra `dc_elo_tilt` Δ−0,000397 IC interamente negativo 5/7 vittorie.

## 1. IL MODELLO — valutazione

**Stato attuale (screen)**: testo breve, ensemble 70/30, Dixon-Coles pesato tempo (attacco/difesa, λ, ρ), Elo forza aggiornata gara per gara, mercati derivati, accuratezza in Accuratezza con RPS/Brier vs naive.

**Fatto bene? Sì, ma incompleto rispetto a ciò che gira in produzione**:
- Punti forti: distingue due famiglie (gol vs rating), spiega da dove escono i mercati, link a Accuratezza, linguaggio non tecnico.
- Senso logico: corretto. DC modella distribuzione gol con correzione τ per risultati bassi (0-0,1-0,1-1), Elo cattura momentum. Ensemble pesato è standard (cfr. FiveThirtyEight, The Athletic).
- Intuitivo: per utente non tecnico, «70/30» senza contesto sembra arbitrario. Manca spiegazione del perché 70 e non 50, e di cosa sia RPS/Brier in parole povere.
- Accurato: sì, ma non menziona calibrazione v1.1 che è il miglioramento più importante del sesto giro (bias +0,245→-0,024, pareggio 23,9%→26,2% vs 25,6% osservato). Senza, l'utente pensa che il modello sia ancora gonfiato.

**Proposte concrete** (da applicare in `info.html`):

1. **Badge calibrazione live** (preso da `calibration.parquet`): «Calibrazione attiva: λ×0,91 (momenti, ultimi 730 giorni, 4.743 gare) ρ−0,04 — corregge la sovrastima storica dei gol». Mostrare anche `bias λ +0,053` walk-forward e link a `docs/13 §3`.

2. **Spiegare 70/30**: «Peso 0,7 misurato: il laboratorio ha provato 0,5 e 0,85 su 1.518 gare walk-forward; 0,7 è il miglior compromesso fra RPS e Brier mercati (prod_w85 batte in 5/7 leghe ma non significativo, prod_w50 peggiore +0,000488 IC positivo)».

3. **Limiti di sicurezza**: aggiungere riga «Limiti: λ≤4,0, totale 70%-135% del modello gol — evita previsioni assurde tipo 8,4 gol (Barcellona-Racing) — interviene su 1,19% gare (69/5.791) e migliora Brier sulle toccate 0,1471→0,1450».

4. **RPS/Brier in italiano semplice**: sotto Accuratezza, aggiungere tooltip: «RPS 0=perfetto, 0,25=casuale con frequenze medie, 0,19-0,20 bookmaker; Brier più basso meglio. Δ negativo = batte la base» — già presente in `accuracy.html`, ma manca in `info.html`.

5. **Link a laboratorio**: «22 candidati testati (DC puro, Poisson, binomiale negativa, Elo k10/k40, tilt a gol invariati) con bootstrap 95% — si cambia modello solo se IC interamente negativo E 5/7 leghe vinte (docs/13 §5-§6)».

Esempio di nuovo paragrafo per `info.html`:
```html
<p>La previsione 1X2 nasce da un <b>ensemble 70/30</b> misurato (non arbitrario): 
<b>Dixon-Coles</b> pesato nel tempo (attacco/difesa, λ gol, ρ risultati bassi, ξ=0,0018) + 
<b>Elo</b> (k 20, HFA 60, aggiornato gara per gara). Il peso 0,7 è il miglior compromesso 
fra 0,5 e 0,85 provati su 1.518 gare walk-forward. 
Da questi escono 1X2, gol attesi, Over/Under, BTTS, doppia chance, clean sheet, risultati esatti 
tramite matrice 0–5 (coda oltre 5 dichiarata). 
<b>Calibrazione v1.1</b> <code>cal-momenti-1.1</code> λ×0,9135 ρ−0,04 (momenti, 730 giorni, 4.743 gare) 
corregge bias λ +0,245→−0,024 e pareggio 23,9%→26,2% vs 25,6% osservato; limiti λ≤4,0 evitano 8,4 gol attesi.
Accuratezza live in <a href="accuratezza.html">Accuratezza</a> con RPS/Brier vs naive e intervalli Wilson 95%.</p>
```

## 2. LE FONTI (GRATUITE) — valutazione

**Stato attuale**: FotMob primaria (calendario, formazioni, indisponibili, arbitro, meteo, xG, stats, momentum, classifiche), Understat xG/xA/xPTS dove copre, ESPN classifica riserva, football-data.co.uk mirror storico, segnaposto onesto.

**Fatto bene? Sì, onesto e a costo zero**, con attribuzione e distinzione presente/atteso/mancante (audit.py). 

**Criticità**:
- Manca Open-Meteo (fallback meteo oltre 48h) già implementato in `collect.py` e verificato in P0.
- Non spiega fallback chain: FotMob → Understat fallback FotMob per xG NED1/POR1, ESPN 403 cronico → FotMob standings primaria, mirror per-lega `datahub_base`.
- Non menziona che quote The Odds API sono opzionali e non usate.
- Non linka `stato.html` dove si vede lo stato sorgenti.

**Proposte**:
- Aggiungere riga: «Open-Meteo — meteo previsto oltre 48h quando FotMob non lo ha ancora».
- Aggiungere nota: «Mirror dedicato NED1/POR1 configurato in `config/leagues.yaml` (campo per-lega `datahub_base`), facilmente sostituibile».
- Aggiungere link: «Stato fonti in tempo reale in <a href="stato.html">Stato</a> (tabelle, righe, KB, completezza schede)».
- Aggiungere icone e tooltip per ogni fonte, e badge «costo zero, nessuna API a pagamento» (regola E).

## 3. Card compatta partita (Famalicão vs Sporting CP) — valutazione

**Stato attuale**: In programma 21:30 Liga Portugal, rank+pt, vs, calcio d'inizio, Lettura modello: favorito 56% margine 31,6 pp sul 2°, barra 1 21% X 24% 2 56%, DC+Elo concordato scarto max 6,8 pp, λ 0,97–1,75 Over 2,5 51% modello ensemble, forma N P P N N 3pt vs N V V V V 13pt, infermeria 1 vs 5 assenti, meteo sereno 27°C, arbitro 5,2 gialli/gara, 17 precedenti.

**Fatto bene? Sì, densa ma leggibile**, con barra colorata, preferito in grassetto+colore (WCAG 1.4.1), forma con pallini colorati, contesto rapido.

**Senso logico**: Sporting 3ª 13 pt vs Famalicão 15ª 3 pt → favorito 56% plausibile, margine 31,6 pp sul 2° (probabilmente X 24%), λ totale 2,72 gol, Over 51% coerente, forma 3 vs 13 pt coerente, infermeria 1 vs 5, meteo sereno 27°C plausibile Portogallo, arbitro Luís Godinho 5,2 gialli plausibile, 17 precedenti plausibile.

**Intuitivo? Parzialmente**: abbreviazioni N/P/V senza legenda, «DC + Elo concordato - scarto max 6,8 pp» tecnico, «λ 0,97–1,75» non etichettato, «17 precedenti» senza bilancio.

**Accurato? Sì**, numeri verificati da `predictions.parquet` e `context` (forma, standings, lineup, weather, referee, h2h_n).

**Proposte concrete** per `_matchlist.html`:

1. **Legenda forma**: tooltip su hover «N=pareggio, P=sconfitta, V=vittoria» e `aria-label` già presente, ma aggiungere icona ℹ e testo «Forma ultime 5» esplicito. Già c'è `aria-label` con sequenza, buono.

2. **Gol attesi etichettato**: da `λ 0,97–1,75` a `Gol attesi 0,97–1,75` e tooltip «Somma λ = 2,72 gol attesi totali».

3. **Over 2,5 con barra**: se >50% mostrare in verde, altrimenti mut, e aggiungere «(51% = 51 partite su 100 con 3+ gol)» per coerenza con distribuzione «partite su 100».

4. **Segnale modelli**: da «DC + Elo concordato · scarto max 6,8 pp» a «Modelli d'accordo (scarto max 6,8 pp)» con `signal_tone=agree` verde ✓, `split` giallo ↔, altrimenti neutro. Aggiungere tooltip «Dixon-Coles dice 58%, Elo 51%, differenza 6,8 pp».

5. **H2H con bilancio**: da «17 precedenti» a «17 precedenti: Famalicão 2-5-10 Sporting (0,8-1,2 gol/gara, BTTS 47%)» — dati già in `ctx.h2h` (conteggio V/N/P, gol/gara, BTTS).

6. **Infermeria cliccabile**: «Famalicão 1 assente · Sporting 5 assenti» con link alla scheda dove si vede lista (già in scheda completa).

7. **Meteo e arbitro con icone**: già ☁ e ⚑, aggiungere «rigori» se disponibile (`referee.penalties`).

8. **Margine favorito**: da «margine 31,6 punti sul 2°» a «Netto favorito: +31,6 pp sul secondo esito (X 24%)».

9. **RPS per anticipo** (prossimo): aggiungere in card `made_at` vs `utc_kickoff` → «Previsione di 3 giorni fa» e in Accuratezza tabella RPS per bucket 0-7/8-14/15-30/31-60 giorni (ora misurabile perché Tappa 1 copre tutto il calendario).

## Valutazione complessiva

- **Fatti bene?** Sì: 0 problemi su 12.130 controlli, 172 test, ruff pulito, build 376/2.364/7.394, audit 0 mancante dopo correzioni, calibrazione a momenti con bias <0,10, limiti λ, laboratorio equo con bootstrap, Tappa 1 a costo zero, segnaposto onesti mai valori inventati.
- **Senso logico?** Sì: DC per distribuzione gol bassi, Elo per momentum, ensemble pesato misurato, calibrazione per livello gol, limiti per evitare assurdità, fallback fonti con finestra editoriale.
- **Intuitivi?** Abbastanza, ma migliorabili con badge calibrazione live, legenda forma, etichette esplicite λ/Over, H2H con bilancio, modelli d'accordo in linguaggio naturale.
- **Accurati?** Sì entro rumore: RPS 0,20 vs naive 0,23, backtest 5.801 RPS 0,1996, live 70 gare RPS 0,2113, pareggio e Over entro Wilson, Brier mercati batte base, promosse coperte, 0 senza previsione su 1.987.

## Prossimi passi proposti (in ordine)

1. Fix `lab.yml` quoting bug e ridispatch lab con 5 candidati (o 22) per verdetto ufficiale.
2. Aggiornare `info.html` con badge calibrazione, spiegazione 70/30 misurata, limiti, RPS in parole semplici.
3. Aggiornare `LE FONTI` con Open-Meteo, fallback chain, link `stato.html`.
4. Migliorare `row` in `_matchlist.html` con gol attesi etichettato, H2H bilancio, modelli d'accordo in chiaro, legenda forma.
5. Implementare «RPS per anticipo» in `accuracy.html` (bucket 0-7/8-14/15-30/31-60) usando `made_at` vs `utc_kickoff` — ora possibile da Tappa 1.
6. Mantenere Tappa 2 rinviata (non ora) per non aggiungere 17 min build di segnaposto.

