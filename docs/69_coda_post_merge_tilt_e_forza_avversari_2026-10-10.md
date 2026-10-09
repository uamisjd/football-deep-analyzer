# 69 — Coda dopo la PR #98: i tre tilt e la «forza avv.» storica (2026-10-10)

Handoff scritto su richiesta dell'utente («c'è ancora altro in sospeso? hai verificato che siano
le cose giuste? le facciamo ora o dopo il merge?»). Decisioni prese: **merge della PR #98
dell'utente**, poi in una sessione nuova **prima la decisione sui tre tilt**, quindi
«forza avv.» storica. Questo documento non cambia una riga di codice di produzione: registra
solo ciò che è stato verificato oggi, con le misure.

## 1. I tre tilt — stato verificato nel codice, non solo nei documenti

`absences_tilt` (`src/fda/models/predict.py:62`), `rest_tilt` (`:99`) e `market_value_tilt`
(`:144`) **esistono e non sono chiamati da `predict_matches()`**. Verifica di oggi su tutto
`src/`, `scripts/`, `config/`: l'unico chiamante è `scripts/audit_modelli.py` (import a
`:40-42`, uso a `:262-267`, `:324`, `:378`). La card «Fattori che spostano la partita» dice
ancora il vero: descrive, non sposta la previsione salvata.

Le misure già prese (`docs/48`, snapshot `docs/_audit_modelli.json` del 2026-09-20) e le stesse
misure **rigenerate oggi** con lo stesso script, interamente offline, sui Parquet correnti
(backtest 5.895 righe, calibrazione λ×1,039385 stimata il 2026-10-09 22:03):

| Tilt | Campione oggi | Snapshot 2026-09-20 | Oggi (misura rigenerata) |
|---|---:|---|---|
| **riposo** | 1.591 λ modificate su 5.895 | ΔRPS **+0,000080**, IC95 [+0,000011; +0,000146] | ΔRPS **+0,0000787**, IC95 **[+0,0000154; +0,000141]** → **peggiora ancora**, IC fuori dallo zero |
| **valore dei titolari** | **341** gare | n 337, non distinguibile da zero | solo **k=0,03** ha IC che esclude lo zero (Δlog-loss −0,004785, IC [−0,008769; −0,000581]); il **k=0,12 in produzione no** (−0,009475, IC [−0,025091; **+0,007122**]) |
| **assenze** | **98** gare con infermeria pesata | n 137, non distinguibile da zero | IC che escludono lo zero per ogni k>0, ma **miglioramento monotono senza ottimo interno** (k=0,5 il migliore): su 98 gare è l'impronta di un campione troppo piccolo, non un effetto promuovibile |

Il valore dei titolari resta in gran parte **ridondante**: correlazione col modello **0,883**,
col residuo **0,148**. Il riposo ha anche tre difetti di costruzione dichiarati in `docs/48`
§2.4: la fonte citata («UEFA RR 1,32») è un rischio relativo di **infortunio**, non un effetto
sui gol; `//86400` sposta i confini delle fasce («≤2» cattura turni da 2,9 giorni); il riposo è
contato dall'ultima gara **giocata**, così 1.999 previsioni su 2.071 portano il fattore 1,02 e
con le gare monche l'asimmetria è rumore.

**Da verificare prima di usare il numero delle assenze:** lo snapshot diceva 137 gare, oggi ne
escono 98. Non ho isolato la causa (la finestra è «gare finite di questa stagione con
`match_info`», ricampionata dal daily); va capita prima di qualunque conclusione su quel tilt.

**Conseguenza sulla strada A (cablarli):** per il riposo è **contraria all'evidenza misurata due
volte**, a tre settimane di distanza; per gli altri due poggia su **341 e 98 gare** — 5,8% e 1,7%
del backtest. Non è un'opinione: sono i numeri già registrati, e la regola del progetto vieta
cambi di ricetta senza protocollo preregistrato. Misura accessoria dello stesso audit: l'unica
cosa che chiude davvero il divario col mercato è il mercato stesso (miscela 25/50/75% → RPS
0,1838 / 0,1813 / 0,1796), ma le quote non sono un obiettivo editoriale (`docs/65` §0) e
esistono solo in NED1/POR1.

Come riprodurre la misura rigenerata (nessuna richiesta di rete, ~2 minuti):

```bash
.venv/bin/python scripts/audit_modelli.py --json data/cache/audit_modelli_oggi.json
```

`data/cache/` non è versionato: il JSON va rigenerato, non letto come stato corrente.

### Difetto ancora aperto nel codice di produzione

`src/fda/models/predict.py:41` afferma: «k calibrato su backtest: 0.12 è il valore che
massimizza log-loss fuori campione **su 5.7k gare** con valori FotMob disponibili». `docs/48`
l'ha già dichiarata **impossibile**: il dato esiste per 371 gare. Il commento falso è ancora lì.
Correggerlo non tocca alcuna previsione ed è l'unica modifica di codice raccomandata in questa
voce, insieme al protocollo.

### Protocollo preregistrato che un candidato deve superare

Da scrivere **prima** di guardare i risultati: griglia dichiarata (`k_mercato ∈ {0; 0,03; 0,06;
0,09}`, `k_assenze ∈ {0; 0,1; 0,2}` senza preservazione del totale, **riposo escluso**);
copertura minima dichiarata in anticipo (sotto quella soglia l'esito è «non testabile», non
«neutro»); walk-forward fuori campione; nessuna calibrazione stimata a posteriori; IC bootstrap
appaiato sia contro la ricetta attuale sia contro il mercato; e, se entra in produzione,
`MODEL_VERSION` nuova + calibrazione ristimata + backtest che applica il fattore + card che
mostra i passi veri (invariante di `docs/20`: ogni Δ pubblicato è la differenza fra due passi
stampati).

**Scelta dell'utente:** **C** tenere il codice dichiarandolo (raccomandazione di `docs/57` §7.2),
**B** spostare le tre funzioni in un modulo di laboratorio così `predict.py` contiene solo ciò
che la produzione usa (va dimostrato che le previsioni restano **byte per byte** identiche),
**A** cablarli (non sostenuto dalle misure).

## 2. «forza avv.» storica — rimedio misurato, pronto da scrivere

Oggi la colonna della tabella «Come arrivano» (`src/fda/site/analysis.py:4457-4467`) legge
`self.standing(opp)`: **posizione e punti della classifica odierna** accanto a una gara di
agosto. Il tooltip lo dichiara e `verify_site` controlla solo che la dichiarazione ci sia
(`:3742`), non che il numero sia temporalmente giusto: è l'anacronismo aperto di `docs/60` §5.

Misura di oggi, sullo store e sulla finestra del sito correnti, **senza modificare il codice**:

| Voce | Valore |
|---|---:|
| Righe della tabella «Come arrivano» | **4.992** |
| Con rango/punti della classifica attuale (anacronismo) | **4.979** |
| Con **Elo storico alla vigilia** già disponibile (serie B di `docs/66`) | **4.979** |
| Con **rango storico della lega alla vigilia** | **4.979** |

Copertura **99,7%**, **zero fonti nuove**: la macchina validata in `docs/68` (246 fit su
prefissi troncati, 8.191 confronti senza differenze) fornisce già il numero giusto per le stesse
righe. Piano: sostituire la colonna con il rango alla vigilia (formato `(4ª)` come nella
striscia della forma), tooltip con l'Elo storico, dichiarazione onesta aggiornata, estensione di
[43] e controllo indipendente come in [44], poi build completa e tutti i gate con parità sulle
7 leghe. Costo stimato: una build + gate (~20 minuti).

## 3. Cosa non è fattibile in questo sandbox (verificato, non presunto)

- **C — Clubelo**: `config/sources.yaml:44` e `clubelo_country` in tutte e 7 le leghe, ma
  **nessuna riga di codice la usa** (grep). `api.clubelo.com` non è raggiungibile da qui: gli
  unici host ammessi sono github.com, codeload, api.github.com, registry.npmjs.org, pypi.org,
  files.pythonhosted.org.
- **D online** — il benchmark mensile live con le quote footballdata/Pinnacle: verificato solo
  il percorso **offline**, con downloader fake.
- **Valore dei titolari assente su 42 schede su 66**: lacuna di **raccolta**, serve una sonda
  live verso la fonte.

## 4. Due numeri «modello contro mercato» nello stesso repo — riconciliati oggi

Chi legge `docs/67` e `docs/_audit_modelli.json` trova due ΔRPS diversi. Non è una
contraddizione: è la **calibrazione**. Ricontato oggi con lo stesso join, sulle stesse gare:

| Misura | Probabilità del modello | RPS modello | ΔRPS |
|---|---|---:|---:|
| `docs/67` (benchmark offline) | **grezze** fuori campione | 0,1873403080035183 | **+0,008806505285954799** |
| Ricontato oggi | **calibrate** (λ×1,039385 del 2026-10-09, ρ−0,04) | 0,18706361313745334 | +0,008529810419889854 |
| `docs/_audit_modelli.json` (audit 2026-09-20, backtest 5.891 righe) | calibrate (λ×1,040063 del 2026-09-13) | 0,18706032149477558 | +0,008526518777212071 |

Stesso campione (**1.071 gare**) e **RPS del mercato identico in tutte e tre**:
0,178533802717564. Decomposizione dello scarto 2,800e−04 fra `docs/67` e l'audit: la
calibrazione spiega **2,767e−04**; il residuo **3,3e−06** viene dalla calibrazione **ristimata
dal daily** il 2026-10-09 22:03 (λ×**1,039385**, `n_fit` 4.770) contro quella dello snapshot
(λ×**1,040063**, stimata il 2026-09-13, `n_fit` 4.760) — il backtest nel frattempo è passato da
5.891 a 5.895 righe. Non isolato riga per riga; l'ordine di grandezza è 20 volte sotto la
differenza grezzo/calibrato. Conclusione invariata e più forte: **anche con la calibrazione di
produzione il modello resta dietro il mercato** (Δ +0,00853, IC che esclude lo zero).

Da qui un piccolo punto di ordine: `docs/_audit_modelli.json` è uno **snapshot del 2026-09-20**
con una calibrazione ormai ristimata due volte, ma vive in `docs/` dove chi legge può prenderlo
per corrente. Lo script è **interamente offline** (lo dichiara in testa e l'ho verificato
eseguendolo): rigenerarlo a richiesta costa poco, e per la decisione sui tilt conviene partire
dalle misure di oggi, non da quelle di tre settimane fa.

Controlli di contorno: gli **SHA-256 dei due input coincidono con quelli registrati in
`docs/67`** e il benchmark offline rieseguito oggi **riproduce ogni valore pubblicato bit per
bit**. Attenzione al clone: questa workspace è **shallow (1 taglio)**, quindi
`git log --diff-filter=A` attribuisce ogni file al commit base — non leggere la provenienza dei
file da quel comando.

## 5. Prossimo passo

Sessione nuova: leggere `docs/BRIEFING_NUOVA_SESSIONE.md`, la cima di `docs/STATO.md` e questo
documento; partire dalla **decisione sui tre tilt** (§1, compresa la correzione del commento
falso in `predict.py:41` e la verifica del campione delle assenze, 137 → 98), poi
**«forza avv.» storica** (§2). Il merge della PR #98 resta dell'utente.

Per scrivere questo documento non è stata fatta **nessuna raccolta sportiva**: solo letture dei
Parquet versionati, `scripts/audit_modelli.py` offline, `scripts/benchmark_quote.py --offline` e
grep sul codice.
