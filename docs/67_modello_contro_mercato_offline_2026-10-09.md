# 67 — Modello contro mercato, senza rete (2026-10-09)

Voce **D** della [coda](65_handoff_e_coda_fonti_2026-10-09.md), dopo
[la forma con Elo storico](66_la_forma_dice_contro_chi_2026-10-09.md).
PR **#98**, branch `arena/eb94e8df-football-deep-analyzer`. Merge dell'utente.

## 1. Che cosa si può misurare subito

Le colonne `odds_home`, `odds_draw`, `odds_away` **esistono già** in `history.parquet`.
La loro presenza nello schema, però, non significa che siano piene in tutte le sette leghe:

| Lega | Gare nello storico | Quote complete | Gare nel backtest | Confronti appaiati validi |
|---|---:|---:|---:|---:|
| ENG1 | 1.190 | 0 | 974 | 0 |
| ESP1 | 1.209 | 0 | 969 | 0 |
| FRA1 | 963 | 0 | 738 | 0 |
| GER1 | 954 | 0 | 728 | 0 |
| ITA1 | 1.190 | 0 | 980 | 0 |
| NED1 | 981 | 754 | 756 | **532** |
| POR1 | 980 | 765 | 750 | **539** |
| **Totale** | **7.467** | **1.519** | **5.895** | **1.071** |

I 5.895 risultati del backtest si agganciano tutti allo storico, uno a uno. Le **4.824**
esclusioni sono tutte per quote assenti o invalide; **zero** per probabilità del modello
invalide e **zero** per risultati discordanti. Le quote complete esterne al campione del
backtest non diventano nuove osservazioni del modello: non si rifà alcun addestramento.

Il confronto effettivo copre **9 marzo 2024 → 11 gennaio 2026**, non l'intero periodo del
backtest (20 gennaio 2024 → 20 settembre 2026). Nelle altre cinque leghe il risultato è
**non disponibile**, non zero e non una vittoria del modello.

## 2. Metodo dichiarato prima di leggere il verdetto

- **Modello:** vettori `p_home/p_draw/p_away` di `backtest.parquet`, ensemble **grezzo fuori
  campione**, versione `dc-elo-tilt-0.4` su tutte le 1.071 gare. Non si applica ai vecchi
  risultati la calibrazione di oggi, stimata anche sugli stessi esiti: sarebbe una
  valutazione circolare. Questo confronto **non certifica l'accuratezza prospettica del
  modello calibrato pubblicato oggi** e non cambia la ricetta di produzione.
- **Mercato:** `p_i = (1 / quota_i) / Σ(1 / quota_j)`, cioè rimozione proporzionale del
  margine. Servono tutte e tre le quote, finite e **maggiori di 1**.
- **Campione:** join uno-a-uno per **lega + giorno UTC + nomi canonici su entrambi i lati**.
  Modello e mercato si valutano sulle **stesse gare e sugli stessi esiti**; i due punteggi
  delle fonti devono coincidere, e l'eventuale `outcome` deve essere coerente. Un duplicato
  nella chiave fa fallire la misura, non moltiplica il peso della gara.
- **RPS:** ordine `1–X–2`, somma degli errori quadratici cumulati divisa per **2**, come nel
  progetto. **Brier multiclasse:** somma dei tre errori quadratici, scala **0–2**, non media
  divisa per tre e non il Brier dei mercati binari sui gol.
- **Δ = modello − mercato**: sotto zero il modello è migliore, sopra zero il mercato.
  Ogni gara ha lo stesso peso, non si fa la media non pesata delle medie di lega.
- **IC 95%:** bootstrap delle **differenze appaiate per gara**, 4.000 estrazioni, seme **11**,
  riuso di `models.lab.paired_bootstrap`. Sotto 20 gare niente intervallo. È un intervallo
  condizionato al campione, con ricampionamento per gara, **non per blocchi temporali**:
  non elimina la dipendenza fra partite della stessa squadra o finestra di addestramento.

### Limite della provenienza delle quote

Il parser `sources/history.py` dà priorità a **PSCH → AvgCH → B365CH**, ma ammette i ripieghi
**PSH → B365H** (analogamente per X e 2). Il Parquet non conserva la colonna scelta per riga.
Non si può dunque certificare dal solo file locale che ogni quota sia **Pinnacle di chiusura**;
lo script dichiara «priorità alla chiusura; fonte e ripiego non tracciati». Nessuna richiesta
aggiuntiva è stata fatta per colmare o nascondere questa limitazione.

## 3. Risultati osservati offline

Valore più basso = migliore. Tutti i valori della tabella sono calcolati sul medesimo
campione appaiato di **1.071 gare**.

| Misura | Modello | Mercato | Δ modello − mercato | IC 95% del Δ |
|---|---:|---:|---:|---:|
| **RPS** | **0,187340** | **0,178534** | **+0,008807** | **[+0,005362; +0,012135]** |
| **Brier 1X2** | **0,563247** | **0,543645** | **+0,019602** | **[+0,011923; +0,026925]** |

| Lega | Gare | RPS modello | RPS mercato | Δ RPS [IC 95%] | Δ Brier [IC 95%] |
|---|---:|---:|---:|---|---|
| NED1 | 532 | 0,191187 | 0,180513 | +0,010675 [+0,005524; +0,015666] | +0,021879 [+0,010027; +0,033273] |
| POR1 | 539 | 0,183543 | 0,176580 | +0,006963 [+0,002545; +0,011488] | +0,017354 [+0,007277; +0,027422] |

**Verdetto limitato al campione disponibile:** il mercato precede l'ensemble grezzo in
**entrambe le leghe valutabili**, sia per RPS sia per Brier; gli intervalli appaiati del Δ
sono tutti positivi. **0 leghe vinte su 2 valutate**, non «0 su 7». Non è una prova su tutta
la stagione corrente, né un motivo per cambiare modello senza il protocollo del laboratorio.

## 4. Strumento riproducibile e protezioni

Esteso **lo script esistente** `scripts/benchmark_quote.py`, senza una nuova fonte:

```bash
.venv/bin/python scripts/benchmark_quote.py --offline \
  --json data/cache/benchmark_history.json
```

- `--offline` legge solo `history.parquet` e `backtest.parquet`; `--data` permette di scegliere
  un'altra cartella. Nessuna rete, nessun fit, nessuna scrittura sui Parquet.
- Il JSON contiene copertura per **tutte le sette leghe**, esclusioni disgiunte, periodo,
  versioni del modello, convenzioni, IC e SHA-256 dei due input. Dato mancante = `null`, mai
  `NaN` o uno zero numerico che sembri una misura.
- La modalità preesistente **senza `--offline`** resta quella del benchmark mensile sulle
  chiusure Pinnacle di sette leghe; il workflow non è stato cambiato né lanciato. Ridurlo
  silenziosamente a due leghe locali sarebbe un peggioramento (regola B.10).
- Quattro test nuovi (`tests/test_benchmark_quote.py`): metriche ricontate a mano e rimozione
  del margine; alias e date; copertura delle leghe vuote e IC riproducibili; esclusione di
  quote/vettori/esiti invalidi e rifiuto dei duplicati; campione vuoto con JSON valido;
  CLI offline con downloader e client HTTP **sostituiti da funzioni che falliscono** se chiamati.

Identità degli input di questa misura:

```text
backtest.parquet  db61245728b8eca44e1a09e5baf0aa20249b9df3a47e9760104a08d59a2d0705
history.parquet   b2afb6e4624ce26ee6536a03846ed16301316437fe12ad976b26a80ebfa6b19c
```

**Gate della prima consegna:** suite completa **562 passed** (106,85 s), Ruff pulito; gli **otto test del
benchmark** comprendono i quattro nuovi e tutte e quattro le regressioni preesistenti.
CI del codice finale **d180d09** verde (run `38000587938`, 1m23s); i check aggiornati dei
commit documentali sono visibili nella [PR #98](https://github.com/uamisjd/football-deep-analyzer/pull/98).
I gate del sito di [docs/66 §5](66_la_forma_dice_contro_chi_2026-10-09.md#5-verifica-finale--osservata-offline-non-gli-attesi-dellhandoff)
restano applicabili: D non modifica il codice o i template del sito.

**Revisione del 10/10:** [docs/68](68_revisione_forma_mercato_2026-10-10.md). Le quattro
metriche confermate da un calcolo separato; chiavi di lega vuote/spazi ora rifiutate; percorso
mensile verificato con fake senza usare il Parquet locale. **JSON prima/dopo identico**,
compresi IC, copertura e hash. Suite del lotto rivisto **568 passed**, Ruff e CI verdi.

## Prossimo passo

**PR #98 completa: merge dell'utente**, dopo i check dell'ultimo commit. Nessuna raccolta richiesta
per questa voce D e nessuna nuova calibrazione/promozione. Per estendere la misura a sette
leghe, usare in un giro distinto il benchmark mensile già previsto, senza presentare come
localmente verificati dati oggi assenti; la provenienza esatta delle quote e la valutazione
prospettica del calibrato restano limiti dichiarati, non risultati acquisiti.
