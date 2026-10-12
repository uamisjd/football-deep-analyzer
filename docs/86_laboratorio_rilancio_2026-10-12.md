# 86 — Rilancio del laboratorio modelli (2026-10-12)

**Richiesta dell'utente:** «uso tutto in privato e personale, inizia a migliorare il progetto».
**Scelta:** prima misurare. Il laboratorio (`fda lab`) era fermo al 14/09 (`model_lab.parquet`,
1.603 gare, candidati già superati). Lo rilancio sullo storico attuale, senza nuove richieste alle
fonti esterne (`--history data/processed/history.parquet`, 7.522 gare, 7 campionati, al 11/10).

## 1. Esito della run (29 candidati, finestre di 28 giorni, min_train 600)

3.157 gare valutate fuori campione (walk-forward). ΔRPS rispetto alla produzione `dc_elo_prod`
(RPS 0,19840), IC 95% appaiato:

| Candidato | ΔRPS | IC 95% | Leghe migliori (su 7) |
|---|---|---|---|
| `gamma_124` (γ-sharpening 1,24) | −0,00095 | [−0,00163; −0,00024] | 7/7 |
| `gamma_112` (γ-sharpening 1,12) | −0,00070 | [−0,00105; −0,00033] | 7/7 |
| `tau_110` (temperatura 1X2 1,10) | −0,00064 | [−0,00098; −0,00030] | 7/7 |
| `tau_116` | −0,00083 | [−0,00136; −0,00028] | 6/7 |
| `tau_120` | −0,00088 | [−0,00154; −0,00020] | 6/7 |
| `dc_xi10` | +0,00010 | [−0,00040; +0,00070] | 2/7 |
| `elo_k10`, `pi_ratings`, `elo` | +0,002 ÷ +0,007 | tutti positivi | 0 |

Il candidato più netto è dunque **peggio** di quasi nulla: tutto ciò che è migliore lo è di circa
0,5% in RPS. La produzione resta competitiva; i modelli puri Elo e Pi-ratings perdono in modo
netto.

## 2. Perché NON cambio la produzione

Il criterio di promozione fissato in `docs/13` §6.5 è «IC appaiato interamente negativo + migliore
in almeno 5 leghe su 7». `gamma_112`, `gamma_124` e `tau_110` lo superano su questo campione. Non
li adotto, per quattro motivi:

1. **La γ-sharpening era già stata respinta** in `docs/19` §1.3 con griglia pre-registrata: lì
   l'IC attraversava lo zero (4/7 leghe). Il risultato dipendeva dai limiti della griglia (passa con
   γ≤1,12, non passa con γ≤1,40). Il fatto che `gamma_124` sia «l'ottimo della griglia onesta»
   è un segnale di selezione, non di robustezza.
2. **Molteplicità:** su 29 candidati, un risultato al 95% su qualche decina ne esce per caso. Un
   test corretto per i confronti multipli farebbe scattare l'IC.
3. **Varianti quasi identiche:** `tau_110`…`tau_120` e `gamma_112`…`gamma_124` sono le stesse
   correzioni a intensità diversa. Non sono cinque prove indipendenti.
4. **Entità:** circa 0,001 RPS. Sotto la soglia che il progetto considera utile (la regola B.10 di
   `docs/00` chiede che ogni modifica «migliori», non che sia solo statisticamente diversa da zero).

## 3. Prossimo passo proposto (da decidere)

**Test prospettico con una sola ipotesi pre-registrata:** `gamma_112` (il valore più prudente della
famiglia), con la regola scritta qui prima dei dati nuovi: promozione solo se, sulle gare che
arrivano dopo questa data, ΔRPS < 0 con IC interamente negativo e migliore in ≥5 leghe su 7.
Richiede un registro delle previsioni congelate per run, che il progetto già prevede (storico delle
previsioni per run, `docs/48`).

Il laboratorio resta **fuori dal `daily`** (costo: circa 20 minuti su due core con 29 candidati).

## 4. Stato dei file e verifiche

- `data/processed/model_lab.parquet`: rigenerato dalla run (240 righe, tracciato in Git).
- `fda build`: 493 schede · 2.364 partite · 7.586 giocatori.
- `scripts/verify_site.py`: 0 problemi · 235.684 controlli numerici.
- `pytest` su `test_lab.py` e `test_laboratorio.py`: 39 passati. `ruff check .`: pulito.
- Non toccati: `season_sim.parquet` (modificato da una run precedente, non committato) e
  `season_sim_cond.parquet` (non tracciato).
