# 71 — I tre tilt: commento falso corretto, campione assenze misurato (137→98), protocollo preregistrato (2026-10-10)

**Voce:** G della [coda post-merge](69_coda_post_merge_tilt_e_forza_avversari_2026-10-10.md) §1.
Tre eil tilt (`absences_tilt` `predict.py:62`, `rest_tilt` `:99`, `market_value_tilt` `:144`)
sono **candidati di laboratorio**: l'unico chiamante è `scripts/audit_modelli.py`;
`predict_matches()` non li chiama (verificato su `src/`, `scripts/`, `config/`).

## 1. Il commento falso è corretto (G-a)

`predict.py:41` diceva: «k calibrato su backtest: 0.12 è il valore che massimizza log-loss
fuori campione **su 5.7k gare** con valori FotMob disponibili». Falso due volte, misurato:

- i valori FotMob dei titolari esistono per **341 gare** del backtest (5,8% di 5.895), non 5.7k;
- su quel campione **k=0,12 non è distinguibile da zero** (Δlog-loss −0,009475, IC95
  [−0,025091; +0,007122]); solo **k=0,03** ha un IC che esclude lo zero
  (−0,004785, IC [−0,008769; −0,000581]).

Il commento ora riporta questi numeri e dichiara che la funzione non è chiamata da
`predict_matches()` (candidato di laboratorio, valutato con il protocollo del §3).
**Nessuna λ cambia**: la correzione è solo nel commento, e
`test_tilt_commento_veritiero_e_lambda_immutati` (`tests/test_models.py`) lo blocca —
le affermazioni false non tornano, le costanti restano (`MARKET_VALUE_K == 0.12`,
`ABSENCES_K == 0.30`) e l'uscita numerica dei tre tilt è **pinnata** sui valori misurati
col codice del 2026-10-10.

## 2. Perché il campione delle assenze è passato da 137 (snapshot 2026-09-20) a 98 (G-b)

**Misurato, non ipotizzato**: matrice 2×2 (codice vecchio/nuovo × Parquet dello snapshot
`e79c377`/correnti), stessa logica dell'audit (`scripts/audit_modelli.py`, identico nei due
commit). Campione = gare finite agganciate (backtest × calendario) con almeno una squadra
il cui `absences_weight` ha `contrib_lost_p90 > 0`.

| Combinazione | Gare agganciate | Campione |
|---|---:|---:|
| codice snapshot + Parquet snapshot | 348 | **137** (riproduce lo snapshot: metodo validato) |
| codice attuale + Parquet snapshot | 348 | **134** |
| codice attuale + Parquet attuali | 352 | **98** |
| codice snapshot + Parquet attuali | 352 | **100** |

**Scomposizione**: 137 − 3 (cambio di codice) − 37 (cambio di dati) + 1 (gara nuova) = 98.
Dettaglio per match: 40 persi, 1 gained (137 − 40 + 1 = 98).

**(a) −3 per il codice** (`docs/64` §8, PR #97): il totale dell'infermeria è ora la somma
dei **valori pubblicati riga per riga** (arrotondati come la tabella li stampa). Tre gare
con totale vecchio 0,02–0,03 (Sevilla–Valencia, Gil Vicente–Casa Pia, Moreirense–Benfica)
arrotondano ora a 0,00 → `contrib_lost_p90` None → fuori dal campione.

**(b) −37 per i dati** — il meccanismo, datato con la storia git di `lineup.parquet`:

- il campione delle assenze vive nella tabella `lineup` (righe `role == "unavailable"`);
- le tabelle per-partita sono **sostituite intere** alla ricollezione
  (`store.upsert(..., replace_by="match_id")`, `collect.py:237`);
- tra i data commit del **2026-09-21 e del 2026-09-24** (subito dopo lo snapshot) le righe
  `unavailable` sono crollate **612 → 214** (settembre 496 → 98; agosto intatto a 110):
  110 partite di settembre sono state **riscaricate** dopo lo snapshot (backfill/rinfresco
  delle finite non ancora salvate con `COLLECT_SNAPSHOT = 2`, che torna indietro nella
  stagione partendo dalle più recenti), e le nuove righe non portavano più l'elenco
  pre-partita degli indisponibili (una gara passata da 11 a 1 indisponibili: la pagina
  fonte, letta settimane dopo, non serve più la lista pre-partita);
- agosto è sopravvissuto perché le sue partite (163 finite) sono state tutte scaricate
  entro il 2026-09-12 e **mai più riscaricate** (`match_info.fetched_at`);
- 40 delle 137 gare del campione hanno perso l'infermeria pesata → fuori; ne è entrata 1
  nuova (FC Porto–Benfica, una delle 4 gare arrivate in ritardo nel backtest, 5.891 → 5.895).

Campione per mese: snapshot 137 = 47 agosto + 90 settembre; oggi 98 = 46 agosto + 52
settembre (l'agosto perde 1 per il punto (a): Sevilla–Valencia è una gara di agosto).

**Conseguenza**: il campione delle assenze è **instabile per costruzione** — cala col tempo,
man mano che le partite invecchiano e vengono riscaricate senza la lista pre-partita. Un
candidato su questo tilt deve dichiarare un campione **pinnato** (es. la prima lettura
post-partita), non la tabella corrente.

## 3. Protocollo preregistrato per qualsiasi candidato tilt (G-c)

Scritto **prima** di guardare i risultati di qualquer nuovo candidato. Le misure già
registrate (`docs/48`, `docs/69` §1, §2 di questo doc) sono l'audit, non una calibrazione.

1. **Griglia dichiarata in anticipo**: `k_mercato ∈ {0; 0,03; 0,06; 0,09}`;
   `k_assenze ∈ {0; 0,1; 0,2}` **senza preservazione del totale**; **riposo escluso**
   (la misura è contraria, due volte: ΔRPS +0,0000787, IC95 [+0,0000154; +0,000141], 1.591 λ
   modificate su 5.895 → peggiora).
2. **Copertura minima dichiarata prima di guardare**: **≥ 300 gare** con il fattore
   misurabile (≈5% del backtest) **e presenti in almeno 5 leghe su 7**. Sotto la soglia
   l'esito è «**non testabile**», non «neutro». Con i campioni attuali: valore 341 gare →
   testabile; assenze 98 gare → **non testabile**.
3. **Walk-forward fuori campione**: campione = backtest (gare fuori dal fit della
   calibrazione); ogni fattore usa solo dati disponibili **prima del calcio d'inizio**
   (riposo = giorni dall'ultima gara giocata; assenze = lista pre-partita; valore =
   titolari pre-partita); nessuna stima usa dati successivi alla partita.
4. **Nessuna calibrazione a posteriori**: il verdetto si legge sulla griglia dichiarata;
   la calibrazione (λ×, ρ) non viene mai ri-stimata per migliorare il punteggio di un
   candidato. Se un candidato entra, la calibrazione è ristimata **con il fattore nella
   ricetta** (`fda calibrate`), non attorno ad esso.
5. **IC appaiato**: bootstrap appaiato (3.000 draw) sulle differenze di punteggio
   **per partita** (log-loss e RPS), contro (a) la **ricetta attuale** (λ calibrate, senza
   tilt) e (b) il **mercato** (dove le quote esistono: benchmark offline NED1/POR1,
   1.071 gare, `docs/67`). Promozione solo se l'IC95 è **interamente** sul lato del
   miglioramento per il log-loss e il RPS non peggiora oltre l'IC.
6. **Se un candidato entra in produzione**: `MODEL_VERSION` nuova (es. `dc-elo-tilt-0.5`);
   calibrazione ristimata; **backtest che applica il fattore** (righe rigenerate con le λ
   tiltate); **card che mostra i passi veri** (ogni Δ pubblicato è la differenza fra due
   passi stampati — invariante di `docs/20`); suite completa di gate (test, Ruff,
   `verify_site`, parità 7 leghe, `resa_375`).

**Verdetto pre-registrato sulle misure attuali** (le stesse lette con il protocollo):
riposo escluso (contrario); valore testabile ma nessun k della griglia promossa (solo
k=0,03 distinguibile, e il guadagno è su 341 gare con correlazione 0,883 col modello —
ridondante); assenze non testabili (98 < 300, campione instabile). **Nessun candidato
entra oggi.**

## 4. La decisione A/B/C — in attesa dell'utente

| Opzione | Cosa significa | Sostenuta dalle misure? |
|---|---|---|
| **A** — cablare i tilt in `predict_matches()` | la ricetta di produzione applica i prior | **No**: riposo contrario (misurato 2 volte), valore 341 gare, assenze 98 instabili |
| **B** — spostare le tre funzioni in un modulo di laboratorio | `predict.py` contiene solo ciò che la produzione usa; le previsioni restano **byte-identiche** (da dimostrare) | Neutra: è un'organizzazione del codice, non una modifica di ricetta |
| **C** — tenere il codice in `predict.py` dichiarandolo | commento veritiero (fatto, §1) + questo documento + la card «Fattori» che descrive senza spostare | Neutra: è la raccomandazione di `docs/57` §7.2 |

La decisione è dell'utente (regola: nessuna modifica alla ricetta senza protocollo; il
merge delle PR lo esegue l'utente).
