# Verifica del sito e del progetto — cosa manca e cosa migliorare

> **Data verifica:** 2026-09-08 (sessione `arena/01a08295-football-deep-analyzer`, da `main` `bd1f80e`)
> **Metodo:** navigazione completa del sito generato (`site/`), ispezione del codice (`src/fda/`), query sui dati (`data/processed/*.parquet`), GitHub (PR/run), ricerca web mirata.
> Ogni numero qui sotto è **misurato oggi**, non presunto.

> ✅ **Stato di avanzamento (stessa sessione):** B1, B2, B3, B4, B6, B7 e M1 **implementati e committati** (commit `55539ca` per P0, `7b1a42c` per P1). Restano aperti: **B5** (collegare/rimuovere SofaScore), **M2/M3/M5** (roadmap) e la **pulizia ruff E501**. La verifica dal vivo di Open-Meteo e di `future_days=7` avverrà dopo il merge in Actions (dal sandbox `api.open-meteo.com` è irraggiungibile).

---

## 1. Sintesi: cosa funziona (misurato)

| Verifica | Esito misurato |
|---|---|
| Suite di test | **51 passed** (`pytest -q`, 8,6 s) |
| Build sito | **141 pagine partita + 2364 fixture** generate senza errori |
| Sito live su Pages | **online e aggiornato** (`uamisjd.github.io/football-deep-analyzer`); ultimi 5 run `daily` tutti **success** (~3 min) |
| Previsioni | **73/73** partite in programma nei prossimi 7 giorni hanno la previsione, distribuite su **tutte le 7 leghe** (10–13 per lega) |
| Classifiche | `fotmob_standings` = **132 righe** = tutte le squadre delle 7 leghe (20+20+20+18+18+18+18) |
| Completezza schede future (audit) | 73 partite analizzate: **490 «presente» + 459 «atteso» + 0 «mancante»** |
| Dettagli partita | 134 finite + 8 future con arbitro/meteo/formazione al 100% dove scaricate |
| Monte Carlo stagione | `season_sim` popolata (132 righe), pagina `stagione.html` attiva |
| Accuratezza live | 20 gare valutate, RPS 0,205 vs naive 0,239 (Δ −0,034) |

**Conclusione:** la direttiva «parità tra le 7 leghe» è **raggiunta** — le schede NED1/POR1 (es. FC Twente–Telstar) hanno la stessa profondità delle big-5 (es. Venezia–Fiorentina). Non ci sono più leghe «di serie B».

---

## 2. Bug e rifiniture trovate navigando il sito

Tutti riproducibili e con fix puntuale.

### B1 — Decimali `.0` nella riga arbitro (70 pagine)
Nel card **Contesto** la riga arbitro mostra float grezzi: `Richard Martens · 3,83 gialli/gara · 15.0 rigori · 2.0 rossi (24.0 gare)`.
Il narrativo usa già `int(...)`, il template no.
**Fix:** in `src/fda/site/templates/match.html` riga 72 applicare `|int` a `pens`, `reds`, `matches` (il campo `yellows` usa già `|dec`).

### B2 — Minuti di recupero con `.0` (92 occorrenze)
Nella cronaca/timeline e nei marker gol compare `45+1.0'` invece di `45+1'`.
**Fix:** in `src/fda/site/analysis.py`, `timeline()` riga ~367, castare `added` a `int` (il valore arriva da `minute_added` come float).

### B3 — Attribuzione fonti non allineata ✅ (risolto, commit `55539ca`)
- ~~Il footer globale cita **«Open-Meteo»** come fonte, ma Open-Meteo **non è implementato**~~ → implementato (vedi M1) e ora citato correttamente.
- ~~In fondo a ogni pagina partita: *«Fonti: … ESPN (classifica)»*, ma la classifica è ormai **FotMob-primaria**~~ → testo allineato: «FotMob (… classifica)».
**Fix:** allineare i testi alle fonti reali.

### B4 — Rumore «ERRORE» su ESPN standings (7 righe ogni run)
`stato.html` mostra 7 righe `espn:<lega>` con `ERRORE HTTP 403 …/standings` **a ogni run**. È cronico e noto; poiché la classifica FotMob è primaria e funziona, il 403 non ha impatto sui contenuti ma inquina la pagina «Stato fonti».
**Fix consigliato:** declassare ESPN standings da «errore» ad «avviso/noto» o rimuovere la chiamata (costo 0; FotMob copre la classifica 7/7).

### B5 — Client SofaScore scritto ma non collegato
`src/fda/sources/sofascore.py` esiste (endpoint pubblici: calendario del giorno, dettagli evento, formazioni, statistiche, incidenti) con test dedicati, ma **nessun punto di `collect.py` lo usa**. È un fallback pronto ma inerte.
**Fix/decisione:** collegarlo al collect per i dati che FotMob pubblica in ritardo (formazioni ufficiali, arbitro) **oppure** rimuoverlo per non lasciare codice morto.

### B6 — Formazione probabile con giocatori indisponibili
In più schede lo stesso giocatore compare sia tra gli **Indisponibili** sia nella **Formazione probabile** (es. Bella-Kotchap nel Venezia, Thorisson nel Telstar): FotMob espone lo stesso giocatore con ruolo `starter` e `unavailable`.
**Fix consigliato:** in `starters()` filtrare via i giocatori già presenti in `unavailable()` (stesso `match_id`+`team_id`+nome), così la formazione probabile non contraddice l'infermeria.

### B7 — Retrocessione Liga Portugal incompleta nel Monte Carlo
`season_sim.REL_COUNTS` usa `POR1: 2`, ma la Liga Portugal ha **2 retrocessioni dirette + 1 playoff (16ª classificata)** → 3 posti «a rischio». La probabilità di retrocessione della 16ª non viene calcolata (per NED1 e FRA1 il playoff è invece incluso nei 3).
**Fix:** portare `POR1` a 3 (o calcolare separatamente il playoff), allineando la nota esplicita in `stagione.html`.

---

## 3. Miglioramenti / contenuti mancanti (roadmap, non ancora fatti)

### M1 — Meteo previsionale Open-Meteo ✅ (implementato, commit `7b1a42c` — verifica dal vivo dopo il merge)
Oggi il meteo è solo da FotMob, pubblicato a ridosso della gara: per la maggior parte delle 73 partite future risulta «atteso». **Open-Meteo** (verificato: gratuito, senza chiave, previsioni orarie fino a **16 giorni**, ~10.000 richieste/giorno, licenza CC BY 4.0) riempie il meteo per **tutte** le partite future. Le coordinate dello stadio sono già nei dati FotMob (`matchDetails`). Implementato: client `sources/openmeteo.py`, passo in `collect_league` (tabella `weather_forecast`), fallback solo se FotMob non ha ancora il meteo, `fda daily` con `future_days=7`.

### M2 — Diffidati (Fase 2)
Non implementati: FotMob non li espone nei dati raccolti. Richiederebbe conteggio gialli stagionali da `events` + soglie di lega (5ª ammonizione, ecc.).

### M3 — Schede giocatore (Fase 3)
Non presenti: pagina giocatore con rating, xG/xA per 90, confronto radar. I dati grezzi (`player_stats`, 127.880 righe) sono già raccolti.

### M4 — Quote vs modello (Fase 4, opzionale)
Non prioritaria per l'utente (direttiva registrata). Richiederebbe `ODDS_API_KEY`/BSD.

### M5 — Fase 5 (automazione/qualità)
Notifiche Telegram, xG proprio su StatsBomb Open Data, collettore locale per fonti protette, eventuale PWA.

### M6 — Pulizia ruff + igiene docs
- `ruff check src/` → **44 segnalazioni** pre-esistenti (30 auto-fixabili); la CI esegue solo pytest, quindi non blocca. Un turno dedicato con `--fix` + revisione.
- `docs/STATO.md`: l'intestazione «Ultimo aggiornamento» è **stantia** (parla di PR #14 «aperta» e sessione `arena/01a08232`, mentre PR #14 e #15 sono già mergiate). Da riallineare.

---

## 4. Priorità consigliate

| Livello | Intervento | Sforzo | Effetto |
|---|---|---|---|
| **P0** | B1 + B2 (formattazione) + B3 (attribuzione) con test | ~30 min | Qualità visibile su tutte le pagine, coerenza italiana |
| **P0** | B4 (declassare rumore ESPN) | ~15 min | Pagina «Stato fonti» pulita e onesta |
| **P1** | B7 (POR1 playoff) + B6 (formazione vs indisponibili) | ~1 h | Correttezza dati |
| **P1** | M1 Open-Meteo | ~2 h | Toglie il «vuoto meteo» su tutte le partite future |
| **P2** | B5 (collegare o rimuovere SofaScore) | ~2 h | Fallback reale o meno codice morto |
| **P3** | M2/M3/M5 + M6 (ruff, docs) | vari | Roadmap futura |

---

## Prossimo passo

✅ **P0** (B1–B4) e **P1** (M1 + B7 + B6) completati e in PR #16. Restano, per sessioni future: **B5** (collegare o rimuovere il client SofaScore), **M2** diffidati, **M3** schede giocatore, **M5** Telegram/xG proprio, e la **pulizia ruff E501** (257 pre-esistenti, CI non bloccata). La verifica dal vivo di Open-Meteo e di `future_days=7` avverrà al primo run `daily` dopo il merge.
