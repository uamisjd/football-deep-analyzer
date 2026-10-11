# D — «Incroci in panchina»: piano e script di backfill FotMob (2026-10-11)

Riferimenti: la card è descritta in `docs/78` §7 (cosa significa «incroci in panchina»), la sua
revisione in `docs/78` §10–§13, gli oracoli del verificatore in `docs/79`.

## §1 — Il problema, misurato

La riga «incroci in panchina con l'allenatore avversario» pubblica i **precedenti tra i due
allenatori** (panchine opposte, qualunque coppia di club, sempre prima di questa partita). Oggi
non si vede su nessuna delle 164 panchine: `scripts/audit_panchina.py` conta
`incroci_panchina_assenti 164`, `incroci_panchina_pubblicati 0`.

Il motivo non è un difetto di calcolo: è **profondità d'archivio**. Il collector salva le distinte
della finestra recente e l'archivio ha oggi 411 gare finite (dal 07/08/2026), tutte con il coach
(822 righe `lineup`, 144 allenatori distinti). Con otto giornate di stagione, due allenatori della
stessa lega non si sono ancora incontrati due volte: la riga non ha nulla da contare.

Per popolarla servono le distinte delle **stagioni precedenti**: `data/processed/history.parquet`
ne ha già i risultati (7.503 partite, 3 stagioni × 7 leghe) ma non i nomi degli allenatori e
nemmeno gli id di partita, quindi non basta: serve una chiamata `matchDetails` per partita.

## §2 — La scelta: lo storico sta fuori da `fixtures`

Scaricare 7.500 partite e buttarle in `fixtures` avrebbe conseguenze su tutto il sito (risultati,
accuratezza, forma, porta inviolata, gol nel finale, precedenti, medie di lega): decine di numeri
pubblicati cambierebbero insieme agli incroci, e ogni gate andrebbe riletto. Per questo lo storico
sta in una tabella **sua**:

| dove | cosa | chi la legge |
|---|---|---|
| `lineup` | righe `role="coach"` delle partite storiche (chi sedeva in panchina) | solo il calcolo degli incroci |
| `match_storico` | una riga per partita: id, lega, stagione, giornata, data, squadre, gol, stato | solo il calcolo degli incroci |

`MatchAnalysis` costruisce due indici unificati (stagione ∪ storico) e li usa **soltanto** nel
blocco degli incroci; il resto della card continua a leggere `fixtures` — quindi rendimento
(«punti/gara»), bilancio con l'avversaria, permanenza ed età restano quelli di oggi. Con
`match_storico` assente il comportamento è identico a prima, per costruzione (`Store.read` di una
tabella mancante è un DataFrame vuoto): i 615 test e i gate esistenti lo dimostrano.

Fase 2, **da decidere insieme dopo aver visto i numeri**: se estendere lo storico anche alle
righe vicine (rendimento, «da allenatore contro X», permanenza). Sono scelte editoriali con
effetto su 82 schede: prima si guarda quanti dati arrivano, poi si decide.

## §3 — Lo script

`scripts/backfill_fotmob.py` (niente rete nei test: client finto su `tests/fixtures`):

1. per ogni lega e stagione chiede il **calendario** (`fixtures?id=<lega>&season=<stagione>`),
   tiene le gare finite con data, e salta quelle già in archivio;
2. per ogni partita chiede il **dettaglio** (`matchDetails`) e salva in `lineup` le sole righe
   `coach` (`--tutti-i-ruoli` salva l'intera distinta) e in `match_storico` la riga della partita;
3. scrive su disco ogni `--flush` partite (default 50): un'interruzione non perde il lavoro;
4. è **ripartibile**: rilanciato, salta quello che c'è già (verificato dai test);
5. un dettaglio che fallisce viene contato e saltato; oltre 20 errori il run si ferma da solo.

**Costo.** Le partite da scaricare sono le 7.503 di `history.parquet`, in parte già in cache
`matchDetails_finished` (TTL 10 anni): la cache HTTP del collector vale anche qui, quindi un run
successivo non ripaga ciò che ha già scaricato. A `rate_limit_s: 1.0` della config sono ~2h05m di
rete per tre stagioni; due stagioni ~1h20m; si può spezzare in più sere con `--limite`.
`--budget` (default: nessuno) esiste perché il tetto di 600 richieste di `config/sources.yaml`
vale per il run giornaliero del collector, non per un backfill una tantum.

## §4 — Comandi (ambiente dell'utente)

```bash
.venv/bin/python scripts/backfill_fotmob.py --riepilogo            # prima: 0 incroci attesi
.venv/bin/python scripts/backfill_fotmob.py --stagioni 2025/2026   # ~1h20m (prima sera)
.venv/bin/python scripts/backfill_fotmob.py --stagioni 2024/2025   # ~1h20m (seconda sera)
.venv/bin/python scripts/backfill_fotmob.py --riepilogo            # quanti incroci sono emersi
```

Utili: `--leghe ITA1,ENG1` per limitare, `--limite 1500` per spezzare un run, `--dry-run` per
vedere quante partite scaricherebbe senza chiedere nulla, `--tutti-i-ruoli` se in futuro servisse
l'intera distinta (per ora no: 4 righe per partita invece di 40).

## §5 — Cosa aspettarsi, e poi

`--riepilogo` risponde alla domanda «basta così?»: per ogni gara in programma con una previsione
conta le panchine il cui allenatore ha già incrociato l'altro (qualunque club). Se resta a zero
dopo due stagioni, significa che gli allenatori attuali hanno carriere più lunghe dello storico
scaricato: si aggiunge una stagione, non si cambia codice.

Poi `fda build` e i gate (`pytest`, `verify_site.py`, `audit_panchina.py`, `parita_schede.py`,
`resa_375.py`). `audit_panchina.py` è già stato adeguato: legge anche `match_storico` e ricalcola
gli incroci sulla stessa fonte della pagina, altrimenti segnalerebbe uno scostamento su ogni riga
pubblicata.

## §6 — Cosa è già in questo commit

- `scripts/backfill_fotmob.py` (nuovo) con i test offline `tests/test_backfill_fotmob.py`
  (5 test: stagioni, scrittura, dry-run, ripartenza, errore singolo, riepilogo);
- `analysis.py`: `self.storico`, gli indici `ko_unito` / `risultati_uniti` e il blocco incroci che
  li usa; `tests/test_panchina_notizie.py` ha il test con lo storico (2V 1N 0P su 3 gare) e quello
  che fissa l'invarianza delle righe vicine;
- `audit_panchina.py`: ricalcolo degli incroci su stagione ∪ storico;
- `store.py`: `match_storico` fra le tabelle con chiave `match_id`.

Misura di impatto: con la tabella assente il sito è identico (è la condizione di oggi); il gate
di questa patch lo verifica.
