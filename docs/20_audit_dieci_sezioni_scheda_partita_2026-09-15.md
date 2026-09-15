# 20 — Audit delle dieci sezioni della scheda partita

> **Stato: APPLICATO per intero il 2026-09-15** (branch `arena/01a0a4ec-football-deep-analyzer`,
> blocchi 1-3 `ee9d088`/`667aa89`/`5572dda` + blocco finiture). Soluzioni = quelle proposte qui
> sotto; misure post-fix su 376 schede (`scripts/audit_match_sections.py`): #1 media pesata vera
> + passo tilt separato (84 pagine; le 9 residui «media» sono previsioni legacy «inverti», dove la
> media è onestamente media); #2 numero manuale rimosso (0/376, interdetto per sempre dal
> controllo [13]); #3 fonte dichiarata per riga con n gare (361 pagine + 15 avvisi «due fornitori
> diversi»); #4 quote a somma 100 su 376/376; #5 margine = differenza degli interi stampati,
> **118 → 0 schede incoerenti su 165**; #6 «λ₁ + λ₂ (totale)» ovunque, SEO inclusa; #7 segnale
> con soggetti e distanza sul preferito pubblicato; #8 migliaia + nota sul dato reale; #9
> «coprono X partite su 100» su 165/165; #10 tendenza staccata e con i suoi due numeri + soglia;
> #11 code rinominate e inequivocabili, precedenti per campo da 8 casi (49 pagine); #12 un unico
> formato xPTS + ◎ sul valore stabilizzato con legenda; #13 forma sempre presente in tutte e 7 le
> leghe + «giocatore di peso» = titolare abituale (POR1 5/15 contro 1/15 prima); #14 h3 dentro
> Verifica. Verifiche finali: suite 199 passed, `fda build` 376/2.364/7.476, `verify_site`
> **0 problemi · 16.541 controlli**. Invarianti nuove: [11] margine/primo/secondo coerenti con la
> triade; [12] copertura riconciliata col Parquet; Δ della catena esatti sui valori stampati;
> [13] divieto di conteggi di verifica scritti a mano; [14] divieto di numeri ≥5 cifre senza
> separatore.

**Sessione** `arena/01a0a4ec` · **data** 2026-09-15 · **direttiva utente**: le sezioni
*Analisi pre-partita, Previsione del modello, Risultati esatti più probabili, Come nasce questa
probabilità, Scontro tattico, Fatti rilevanti, Come arrivano, Confronto di stagione, Contesto,
Verifica approfondita* devono essere «accurate, intuitive, precise, profonde, di qualità e logica».

Stessa convenzione di `docs/19`: **Osservato → Misura → Impatto → Soluzione pronta → Verifica**.
Ogni numero qui sotto è stato misurato in questa sessione sul sito generato (`site/`, build
2026-09-14 23:08, 4.123 pagine) o sui Parquet di `data/processed/`. Dove una misura non è ancora
stata fatta è scritto **DA MISURARE**, e dove un'ipotesi è stata **smentita dai dati** è scritto
esplicitamente: conta quanto un riscontro confermato.

---

## 0. Perimetro e metodo

**Campione.** 371 schede partita pubblicate: **76 pre-partita** (le 10 sezioni oggetto di questa
direttiva) e 295 post-partita. Distribuzione delle 76 per lega — la parità di presenza c'è già:

| Lega | ENG1 | ESP1 | FRA1 | GER1 | ITA1 | NED1 | POR1 |
|---|---|---|---|---|---|---|---|
| schede pre-partita | 10 | 19 | 9 | 9 | 10 | 10 | 9 |
| sezioni presenti su 10 | **10** | **10** | **10** | **10** | **10** | **10** | **10** |
| righe narrative in «Analisi pre-partita» (media / min / max) | 7,2 / 6 / 9 | 7,3 / 5 / 12 | 7,0 / 4 / 10 | 6,0 / 5 / 7 | 6,4 / 4 / 9 | 7,7 / 6 / 9 | **5,4 / 4 / 8** |
| righe «Assenze …» | 20 | 38 | 17 | 17 | 18 | 18 | **15** |
| …di cui con la qualifica «giocatore di peso» | 2 | 5 | 5 | 3 | 7 | 3 | **0** |

**Metodo.** (1) censimento automatico di presenza/profondità/segnaposto su tutte le 76 schede
(`/tmp/censimento_sezioni.py`); (2) lettura integrale di due schede vere — Roma-Inter (ITA1, dati
ricchi) ed Estrela da Amadora-Académico Viseu (POR1, dati poveri) — convertite in testo con
`/tmp/estrai_scheda.py`; (3) verifica incrociata dei numeri pubblicati contro i Parquet e contro il
codice che li genera; (4) misura delle divergenze fra fonti (Understat vs FotMob) su 92 squadre.

**Regola di lettura.** Un difetto di questa scheda non è «il numero è sbagliato» (i numeri sono
già ricontrollati da `verify_site.py`, 15.548 controlli): è **il numero giusto detto in modo che il
lettore non possa verificarlo, o attribuito alla causa sbagliata, o messo accanto a un altro numero
con cui sembra in contraddizione**. Sono i difetti che restano dopo che l'aritmetica torna.

---

## 1. [P1] «Come nasce questa probabilità»: il passo 2 è etichettato con un'operazione che non è quella che ha prodotto il numero

**Osservato.** La catena pubblicata ha tre passi:

```
1 · Modello sui gol (Dixon-Coles)   attacco/difesa pesati nel tempo, senza rating   1 · 33,8% X · 26,0% 2 · 40,2%
2 · Media con i rating Elo          Δ -0,3 pp  peso Dixon-Coles 70%, Elo 30%       1 · 34,2% X · 26,0% 2 · 39,8%
3 · Calibrazione                    Δ -0,1 pp  λ × 1,04 (momenti, ultimi 730 giorni) stimata su 4.760 gare fuori campione
                                                                            1 · 33,9% X · 26,4% 2 · 39,7%
```

Il passo 2 mostra la colonna `blend_p_*` e lo chiama «Media con i rating Elo — peso Dixon-Coles
70%, Elo 30%». Dal 2026-09-13 la produzione è `ENSEMBLE_MODE = "tilt"` (`models/predict.py:226`):
l'Elo **non** entra come media di vettori ma **inclina le λ**, e `calibrated_prediction`
(`predict.py:461-463`) salva in `blend_p_*` il vettore 1X2 della **griglia sulle λ inclinate**,
cioè il vettore pubblicato prima della calibrazione. L'etichetta descrive la ricetta precedente
(`"inverti"`), che il laboratorio ha bocciato.

**Misura** (2.080 previsioni con catena completa, tutte `ensemble_mode = "tilt"`, `tilt` da 0,835 a
1,165, diverso da 1 nel **98,1%** delle gare):

| Confronto | Scarto medio per componente | Massimo | Gare oltre 1 pp |
|---|---|---|---|
| vettore pubblicato come «media» vs **media pesata vera** `0,7·DC + 0,3·Elo` | **1,18 pp** | **7,87 pp** | **84,8%** |
| …gare in cui l'**esito più probabile** dei due non coincide | — | — | **8 (0,4%)** |
| Δ sul preferito (pubblicato − media vera) | 0,583 pp | 2,938 pp | — |

E la scomposizione vera dei Δ, ricostruita dalle colonne salvate (`dc_p_*` → media pesata →
griglia su `lambda_*_raw`/`rho_raw` → pubblicato):

| Passo | Operazione vera | \|Δ pp\| medio sul preferito | massimo |
|---|---|---|---|
| 1 → 2 | modello sui gol → media pesata 70/30 | 1,288 | 7,763 |
| 2 → 3 | **inclinazione delle λ (tilt)** — *oggi non pubblicato* | **0,583** | **2,938** |
| 3 → 4 | calibrazione λ × 1,0401, ρ − 0,04 | 0,210 | 2,142 |
| 2 → 4 | ciò che la pagina attribuisce in blocco alla «Calibrazione» | 0,210 | 2,142 |

**Ipotesi smentita dai dati** (va registrata perché era plausibile): si poteva sospettare che il Δ
mostrato come «Calibrazione» fosse in realtà prodotto dal tilt. **Non è così**: la griglia sulle λ
pubblicate riproduce l'1X2 pubblicato con scarto massimo 0,038 pp, e il contributo del tilt rispetto
al vettore pre-calibrazione è ~0 per costruzione (il tilt *cerca* proprio quel vettore). Il Δ
attribuito alla calibrazione è davvero suo. Il difetto è un altro: **manca un passo**, e quello
pubblicato come «media» non è la media.

**Impatto.** La sezione si presenta con una promessa esplicita — «Sono i valori salvati nella
previsione al momento del calcolo, non una ricostruzione a posteriori» — e la mantiene sui valori,
ma l'etichetta del passo 2 attribuisce il numero a un'operazione diversa da quella che lo ha
prodotto, con uno scarto medio di 1,18 pp e 8 gare su 2.080 in cui il preferito mostrato non è
quello della media dichiarata. In più nessuna sezione della scheda spiega **perché le λ pubblicate
(1,35 + 1,48) non sono quelle del modello sui gol**: l'unico posto in cui il tilt è nominato è
`docs/15`.

**Soluzione pronta** (nessuna modifica al modello: tutti gli ingressi sono già salvati).
In `src/fda/site/advanced.py:probability_steps`, costruire la catena a quattro passi:

```python
    # passo 2: la media pesata VERA, ricalcolabile dalle colonne salvate (dc_p_*, elo_p_*, w_dc)
    w = pred.get("w_dc")
    if _vec("dc_p_") and _vec("elo_p_") and w is not None and not pd.isna(w):
        media = tuple(float(w) * d + (1 - float(w)) * e for d, e in zip(_vec("dc_p_"), _vec("elo_p_")))
        steps.append({"label": "Media pesata con i rating Elo",
                      "note": f"peso Dixon-Coles {float(w):.0%}, Elo {1 - float(w):.0%}", **_campi(media)})
    # passo 3 (nuovo): l'inclinazione delle λ, cioè la ricetta di produzione dal 2026-09-13
    if str(pred.get("ensemble_mode") or "") == "tilt" and _vec("blend_p_"):
        tilt = pred.get("tilt")
        note = "l'Elo inclina il rapporto casa/trasferta a totale dei gol invariato"
        if tilt is not None and not pd.isna(tilt):
            note += f" (×{float(tilt):.3f}): la griglia risultante è il vettore pubblicato"
        steps.append({"label": "Griglia sulle λ inclinate", "note": note, **_campi(_vec("blend_p_"))})
```

Il passo 4 («Calibrazione») resta quello che confronta il vettore pubblicato: la sua nota è già
corretta. Se `ensemble_mode` non è `"tilt"` (previsioni storiche) il passo 3 non compare — coerente
con la promessa della sezione: «se un passaggio non è tracciato nei dati, qui non compare».

**Verifica.** (a) test: per ogni previsione del campione, `steps[1]` coincide con `0,7·DC + 0,3·Elo`
a 1e-9 e `steps[2]` coincide con la griglia su `lambda_*_raw`/`rho_raw`; (b) invariante di
pubblicazione in `verify_site.py`: l'ultimo passo della catena pubblicata **deve** coincidere con
l'1X2 della scheda (già presente) e ogni Δ pp deve equalare la differenza fra i due passi adiacenti
**stampati**, non fra un passo stampato e uno no; (c) `fda build` + `verify_site.py`.

---

## 2. [P0] La scheda dichiara un numero di controlli che non è vero (e cambia a ogni build)

**Osservato.** In fondo a «Verifica approfondita», su **tutte le 371 schede**:

> Tutto è ricalcolabile: `verify_site` controlla **11.582** numeri.

Il numero è scritto a mano nel template (`match.html:571`). Era già stantio quando è stato
pubblicato (alla build precedente i controlli erano 11.590) e dopo gli interventi di questa sessione
sono **15.548**.

**Misura.** `grep -c "11.582 numeri" site/partite/*.html` → 371 pagine. Valore vero oggi: 15.548
(`scripts/verify_site.py` sull'ultima build). Scarto pubblicato: **−3.966 controlli (−25,5%)**.

**Impatto.** È l'unica affermazione **auto-referenziale** del sito: dice «puoi ricontrollare tutto»
e lo fa con un numero falso. Peggio: è un numero che **non può** restare vero, perché cresce a ogni
controllo aggiunto — cioè diventa più falso esattamente quando il progetto migliora.

**Soluzione pronta.** Togliere il numero, tenere la garanzia (che è la parte vera):

```diff
- Tutto è ricalcolabile: <code>verify_site</code> controlla 11.582 numeri.
+ Tutto è ricalcolabile: <code>scripts/verify_site.py</code> rilegge ogni numero pubblicato e lo
+ confronta con i dati e con il modello (barre, matrice, distribuzione dei gol, catena della
+ probabilità, calendario, accuratezza, backtest).
```

Se si vuole un numero, deve essere **generato**, non scritto: `verify_site.py --json` che stampa il
conteggio e `build.py` che lo legge dal file dell'ultima verifica. Non vale il costo: il numero non
aggiunge informazione al lettore.

**Verifica.** `grep -rn "[0-9]\{2\}\.[0-9]\{3\} numeri" src/fda/site/templates/` → 0 occorrenze;
più un'invariante in `verify_site.py`: **nessun numero scritto a mano nel template** che pretenda di
descrivere l'output del verificatore (regex sui template, non sulle pagine).

---

## 3. [P1] «Scontro tattico»: la stessa riga «xG / gara» ha due fonti diverse a seconda della lega, e il tooltip ne dichiara una sola

**Osservato.** La tabella «Scontro tattico» mette nella stessa griglia:

| Riga | Fonte vera | Come lo sa il lettore |
|---|---|---|
| Gol attesi (λ) | modello | tooltip: «Media Poisson Dixon-Coles+Elo, non media ultime 3» ✓ |
| **xG / gara** | **Understat** in ENG1/ESP1/FRA1/GER1/ITA1, **FotMob** in NED1/POR1 | tooltip: «Gol attesi: qualità occasioni, **media stagionale FotMob**» ✗ |
| xG azione manovrata / gara | FotMob (`team_stats.expected_goals_open_play`) | tooltip generico «xG» ✗ |
| xG palle inattive / gara | FotMob (`expected_goals_set_play`) | idem ✗ |
| PPDA, PPDA concesso, passaggi profondi | Understat | `n.d.` dove manca, con avviso ✓ |

Il tooltip è unico per ogni etichetta che contiene «xG» (`match.html:105`) e dice **FotMob** anche
dove il valore viene da Understat. La sezione «Come arrivano» invece la fonte la dichiara
(«Fonte: Understat»), e le card delle squadre pure («3,45 (Understat, 4 gare)»): **la stessa
grandezza è attribuita in tre modi diversi nella stessa pagina**.

**Misura.** `season_xg()` (`analysis.py:620-660`) preferisce Understat e ripiega su FotMob.
Divergenza fra le due fonti sulle 92 squadre coperte da entrambe (stagione 2026):

| | Understat − FotMob |
|---|---|
| differenza media | **+0,146 xG/gara** |
| \|differenza\| media / mediana / massima | 0,192 / 0,179 / **0,641** |
| rapporto medio | **1,095** (Understat legge il ~10% in più) |
| per lega | GER1 +0,209 · ITA1 +0,197 · ESP1 +0,149 · ENG1 +0,145 · FRA1 +0,039 |

Caso limite pubblicato: Roma **3,45** (Understat) contro **2,81** (FotMob) sulle stesse 4 gare.

**Impatto.** Due lettori della stessa riga in due leghe diverse confrontano numeri non omogenei,
con un bias sistematico del ~10% a favore di chi gioca nelle 5 leghe coperte da Understat: è un
difetto di **parità fra le leghe** (regola `docs/00` §F) oltre che di attribuzione. E il tooltip
dichiara la fonte sbagliata su 5 leghe su 7.

**Soluzione pronta.** Due righe di template + una di dati (la fonte è già nel dizionario:
`season_style()["source"]`):

```diff
- {% elif 'xG' in r.label %} <span class="help" title="Gol attesi: qualità occasioni, media stagionale FotMob">ⓘ</span>
+ {% elif 'xG' in r.label %} <span class="help" title="Gol attesi: qualità delle occasioni,
+   media stagionale {{ r.fonte or 'FotMob' }} su {{ r.gare or '—' }} gare">ⓘ</span>
```

con `fonte` e `gare` aggiunti a ogni riga in `style_rows()` (`analysis.py`), presi da
`season_style()`. In più, quando le due squadre della stessa gara hanno fonti diverse (capita: una
coperta da Understat e l'altra no), la nota in fondo alla tabella deve dirlo — oggi l'avviso esiste
solo per il PPDA.

**Verifica.** test: per ogni riga xG pubblicata, la fonte nel tooltip coincide con
`season_style(...)["source"]`; `verify_site.py`: su ogni scheda, la «xG / gara» di «Scontro
tattico» è identica a quella delle card squadra (che la fonte la dichiarano già).

---

## 4. [P1] «Scontro tattico»: le due componenti dell'xG non sommano al totale mostrato sopra

**Osservato.** Scheda Roma-Inter:

```
xG / gara                    3,45 ▲   3,10        ← Understat
xG azione manovrata / gara   2,55 ▲   1,85        ← FotMob
xG palle inattive / gara     0,25     1,01 ▲      ← FotMob
```

Il lettore somma 2,55 + 0,25 = **2,80** e lo confronta con **3,45**: mancano 0,65. Non è un errore
di calcolo — sono due fornitori diversi — ma la tabella non lo dice, e le tre righe hanno la stessa
etichetta «xG … / gara».

**Misura.** Verificato sui dati FotMob di Roma (4 gare, `team_stats`, `period = "All"`):
`expected_goals_open_play` 2,552 + `expected_goals_set_play` 0,252 = **2,804** = `expected_goals`
**2,805** ✓. Quindi **dentro FotMob la scomposizione chiude**; è il totale della riga sopra a venire
da un'altra fonte (Understat, 3,446). Stesso controllo su Inter: 1,800 + 0,840 = 2,640 vs 2,638 ✓.

**Impatto.** L'unico punto della scheda in cui due numeri pubblicati sembrano contraddirsi
aritmeticamente. Chi controlla — ed è esattamente il lettore a cui «Verifica approfondita» si
rivolge — conclude che il sito sbaglia i conti.

**Soluzione pronta.** Esprimere la scomposizione in **quote**, non in valori assoluti: la quota è
interna a una sola fonte, quindi è coerente per costruzione e confrontabile fra leghe. La narrativa
della scheda lo fa già: «Académico Viseu crea una quota alta di xG su palla inattiva (**42% del
totale**)».

```diff
- ("expected_goals_open_play", "xG azione manovrata"),
- ("expected_goals_set_play", "xG palle inattive"),
+ # quote interne a FotMob: sommano 100% e non si possono sommare a un totale di un'altra fonte
+ ("quota_open_play", "xG da azione manovrata (quota)"),     # open / (open + set)
+ ("quota_set_play", "xG da palle inattive (quota)"),
```

In alternativa, se si vuole tenere il valore assoluto, la riga del totale va sdoppiata:
«xG / gara 3,45 (Understat) · 2,81 (FotMob)» — più onesto, più rumoroso. **Raccomandata la quota.**

**Verifica.** test: `quota_open + quota_set == 100%` ±0,1 per ogni squadra con split disponibile;
`verify_site.py`: nessuna riga della tabella «Scontro tattico» invita a sommare due fonti (le due
righe di quota sommano 100, il totale resta una riga sola con la sua fonte nel tooltip).

---

## 5. [P1] Sintesi: «+5,8 punti sul secondo» accanto a «40%» e «34%» che ne fanno 6

**Osservato.** Riga di testa della scheda Roma-Inter:

> Esito più probabile **Inter 40%** · **+5,8 punti sul secondo** — Roma 34% · 1 34% · X 26% · 2 40%

Il margine è calcolato sulle probabilità grezze (0,3978 − 0,3398 = 5,8 pp), le percentuali stampate
sono il vettore corretto con il resto massimo (40 e 34). Il lettore fa 40 − 34 = **6** e legge 5,8.

**Misura.** DA MISURARE sull'intero sito (il meccanismo è certo, l'incidenza no): va contato quante
schede hanno `round(top) − round(second) ≠ round(margin_pp)`. Con tre arrotondamenti indipendenti
l'incidenza attesa è nell'ordine del 30-50% delle schede — la stessa famiglia di difetti già
corretta sulle barre 1X2 (`docs/19` §3.3, 26,3% delle previsioni).

**Impatto.** È la **prima riga** della scheda, quella che resta negli occhi. Un margine che non
torna con i due numeri accanto mina la fiducia in tutto il resto.

**Soluzione pronta.** Derivare il margine dal vettore pubblicato, come si fa già per il preferito
nelle liste (`_matchlist.html`, `fav_i = b1x2.index(b1x2|max)`):

```python
# analysis.py: prediction_meta() — il margine deve essere quello dei numeri stampati
pct = pct_triple((p_home, p_draw, p_away))
ordinati = sorted(pct, reverse=True)
margin_pp = ordinati[0] - ordinati[1]          # interi: il lettore può rifare il conto a mente
```

**Verifica.** `verify_site.py`: per ogni scheda, `margin_pp` stampato == differenza fra le due
percentuali più alte stampate nella stessa riga.

---

## 6. [P2] Sintesi: «1,35–1,48 gol attesi» si legge come un intervallo, ma è la somma che interessa

**Osservato.** `1,35–1,48 gol attesi` · `54% Over 2,5` · `58% entrambe a segno`.
Il trattino fra due λ si legge come un intervallo («da 1,35 a 1,48 gol»), mentre il numero che
davvero orienta la lettura è il **totale** 2,83 — che nella riga non c'è, ma c'è poco sotto
(«gol attesi 1,35 + 1,48» in «Quanti gol, in pratica», con il `+`).

**Impatto.** Due notazioni diverse per la stessa coppia di numeri nella stessa pagina
(`1,35–1,48` in testa, `1,35 + 1,48` in fondo), e in testa manca il totale, che è la grandezza
dietro Over/Under e BTTS pubblicati accanto.

**Soluzione pronta.** Allineare alla notazione del resto della scheda e aggiungere il totale:

```diff
- {{ lam_h|dec(2) }}–{{ lam_a|dec(2) }} gol attesi
+ {{ lam_h|dec(2) }} + {{ lam_a|dec(2) }} gol attesi ({{ (lam_h + lam_a)|dec(2) }} totali)
```

**Verifica.** `verify_site.py`: la somma stampata in testa coincide con `lambda_home + lambda_away`
della previsione e con i «gol attesi» di «Quanti gol, in pratica».

---

## 7. [P2] Sintesi: «Stesso preferito · scarto 0,8 punti sul preferito» non dice di che cosa

**Osservato.** Il segnale di concordanza DC/Elo stampa «Stesso preferito · scarto 0,8 punti sul
preferito» (POR1: «scarto 0,4»). Non si capisce **fra chi**: è lo scarto fra la probabilità del
preferito secondo Dixon-Coles e secondo Elo? fra primo e secondo esito? La riga sopra dice già
«+5,8 punti sul secondo», quindi il lettore legge due «scarti» diversi senza sapere quali.

**Impatto.** Un indicatore di affidabilità (i due motori concordano?) che non si lascia interpretare
è peggio di nessun indicatore: invita a ignorare la riga.

**Soluzione pronta.** Esplicitare i due soggetti e l'unità:

```
✓ DC ed Elo sullo stesso preferito (Inter): 40,2% vs 39,4%, 0,8 punti di distanza
↔ DC ed Elo su preferiti diversi: Dixon-Coles X (28,1%), Elo 2 (35,6%)
```

**Verifica.** test su `prediction_meta`/`signal_*`: la stringa contiene sempre i due soggetti e la
distanza ricalcolabile dai vettori `dc_p_*` ed `elo_p_*` salvati.

---

## 8. [P2] «Previsione del modello»: `1179 partite` senza separatore, e in nota «~1·200 gare» per la stessa quantità

**Osservato.** Piedino della card:

> Stime Dixon-Coles pesato + Elo (70/30) · **1179 partite** · 14/09/2026 22:22 (ora ITA)
> λ su **~1·200 gare** pesate, non media ultime 3 → vedi «Come arrivano»

Due problemi: (a) `1179` senza separatore delle migliaia, in un sito che usa `int_it()` e stampa
altrove «4.760 gare fuori campione» e «67.598 spettatori»; (b) la nota riscrive la stessa quantità
in un altro formato (`~1·200`, con il punto in alto) e con un altro arrotondamento. In POR1 la riga
è «969 partite» con la stessa nota «~1·200» — cioè **la nota non segue il dato**.

**Misura.** `n_train` pubblicato: 1.179 (ITA1) e 969 (POR1) sulla stessa build; la nota dice
«~1·200» in entrambi i casi. Il filtro `it_plural` (`fmt.py:52-61`) formatta `f"{n} {nome}"` senza
migliaia; `int_it` (`fmt.py:23-27`) esiste e non è usato qui.

**Soluzione pronta.**

```diff
- {{ p.n_train|it_plural('partita') }}
+ {{ p.n_train|int_it }} {{ 'partita' if p.n_train == 1 else 'partite' }}
- λ su ~1·200 gare pesate, non media ultime 3 → vedi “Come arrivano”
+ λ pesate nel tempo su {{ p.n_train|int_it }} gare, non media delle ultime 3 → vedi “Come arrivano”
```

**Verifica.** `verify_site.py`: nessun numero ≥ 1000 senza separatore nelle schede (la regola esiste
già per i decimali col punto: `check_pages` segnala «1.69» come decimale sbagliato — qui serve il
controllo simmetrico).

---

## 9. [P2] «Risultati esatti più probabili»: sei risultati senza dire quanta probabilità coprono

**Osservato.** La tabella stampa sempre i primi 6 risultati (Roma-Inter: 1-1 12,4% · 1-2 8,7% ·
0-1 8,1% · 2-1 8,0% · 1-0 7,3% · 0-0 6,6%) e sotto mette Elo e parametri DC. Non dice **quanta
massa** coprono quei sei, né quanta ne resta.

**Misura.** Somma dei sei pubblicati su Roma-Inter: **51,1%**; la matrice 0-5 poco sotto dichiara
«Coda 6+ gol: 0,7%», quindi il resto (48,2%) è negli altri 30 risultati della griglia. Il lettore
non può saperlo dalla tabella.

**Impatto.** Il rischio classico delle liste di risultati esatti: leggerle come se fossero lo
spazio degli esiti. Con «1-1 12,4%» in testa e nessun totale, la tentazione è sommare i sei e
trattare il 51% come se fosse «il risultato» della partita.

**Soluzione pronta.** Una riga di chiusura, con i numeri già disponibili:

```html
<p class="small mut">Questi sei risultati coprono il {{ copertura|dec(1) }}% delle 100 partite;
il resto si distribuisce sugli altri {{ n_altri }} punteggi della matrice
(<a href="#verifica">matrice completa ↓</a>).</p>
```

`copertura = sum(top_scores.values())`, `n_altri = (cap+1)**2 - len(top_scores)` — entrambi già
calcolati per la matrice, nessuna nuova fonte.

**Verifica.** `verify_site.py`: `copertura` stampata == somma dei valori di `top_scores` nella riga
di previsione (la somma dei sei pubblicati deve coincidere al decimale).

---

## 10. [P1] «Come arrivano»: «10 punti fatti contro 5,8 attesi · tendenza in calo» mette insieme due grandezze diverse

**Osservato.** Riga di chiusura della tabella per squadra:

> 6 gare: 1,33 xG e 1,52 xGA a partita · **10 punti fatti contro 5,8 attesi** · **tendenza in calo**

`tendenza` è il confronto fra gli xG **creati** nelle ultime 3 gare e quelli nelle precedenti
(`analysis.py:1039-1044`, soglia ±0,15 xG); la clausola prima è il rapporto fra punti reali e punti
attesi su **tutte** le gare mostrate. Accostate senza soggetto, si leggono come un'unica
valutazione: «ha più punti di quanti meritava, ed è in calo».

**Misura.** 138 righe «punti fatti contro attesi» nelle 371 schede; 29 portano anche la parola
«tendenza» (15 «in calo», 7 «in crescita», 7 «stabile»). In **10 di queste 29 (34%)** le due
clausole puntano in direzioni opposte (punti sopra l'atteso + «in calo», oppure sotto + «in
crescita») — cioè una riga su tre si legge come contraddizione.

**Impatto.** La sezione serve a rispondere a «questa squadra vale i suoi punti?»: mescolare
over-performance stagionale e direzione recente degli xG senza nominarle produce la risposta
contraria a seconda di come il lettore attacca le due clausole.

**Soluzione pronta.** Dare un soggetto alla tendenza e separare le due letture:

```diff
- {{ a.pts }} punti fatti contro {{ a.xpts|dec(1) }} attesi{% if a.trend %} · tendenza {{ a.trend }}{% endif %}
+ {{ a.pts }} punti fatti contro {{ a.xpts|dec(1) }} attesi ({{ delta_pts }})
+ {% if a.trend %} · xG creati {{ a.trend }}: {{ a.xg_recent|dec(2) }} nelle ultime 3 contro
+   {{ a.xg_before|dec(2) }} nelle precedenti{% endif %}
```

con `delta_pts = f"{a.pts - a.xpts:+,.1f}"` in formato italiano, e `xg_recent`/`xg_before` già
calcolati in `analysis.py` per decidere la tendenza (oggi vengono buttati via: resta solo
l'aggettivo).

**Verifica.** `verify_site.py`: ogni «tendenza» pubblicata ha accanto i due numeri che la generano,
e la loro differenza supera la soglia dichiarata nel codice (0,15 xG).

---

## 11. [P2] «Contesto»: due code diverse con etichette quasi identiche, e precedenti non separati per campo

**Osservato.** Nella stessa scheda compaiono:

- matrice dei punteggi: «Coda **6+ gol**: 0,7%» — cioè *almeno una delle due squadre* segna 6 o più;
- distribuzione dei gol: «Totale **7+ gol**: 2,6%» — cioè la *somma* dei gol è 7 o più.

Due grandezze diverse (una per squadra, una sul totale), due soglie diverse (6 e 7), due etichette
quasi uguali («Coda … gol», «Totale … gol») a pochi pixel di distanza.

In più: «Precedenti (39) · 11 vittorie Roma · 11 pareggi · 17 vittorie Inter — archivio dal
21/08/2010 al 05/04/2026», con 5 precedenti mostrati. Nessuna distinzione fra precedenti **allo
stadio di questa gara** e precedenti in generale — il dato c'è (`h2h` ha `home_id`/`away_id` e il
luogo è derivabile), e per una lettura «come finirà *questa* partita all'Olimpico» è la distinzione
che interessa.

**Impatto.** Il primo punto è un rischio di lettura concreto su numeri piccoli (0,7% vs 2,6%: un
lettore che li confonda sbaglia di un fattore 4). Il secondo è profondità mancante, non errore.

**Soluzione pronta.**

```diff
- Coda 6+ gol: {{ (m.p_tail*100)|dec(1) }}%.
+ Almeno una delle due squadre a 6+ gol: {{ (m.p_tail*100)|dec(1) }}%.
```

e nei precedenti, se il campione lo regge (soglia minima da fissare, es. ≥ 8 gare allo stesso campo):

```
Precedenti (39) · 11 V Roma · 11 N · 17 V Inter — archivio 2010-2026
   di cui all'Olimpico (20): 8 V Roma · 7 N · 5 V Inter · 2,75 gol a gara
```

**Verifica.** `verify_site.py`: l'etichetta della coda della matrice contiene «almeno una»; il
sotto-insieme per campo, se pubblicato, somma al totale dichiarato e riporta il numero di casi.

---

## 12. [P2] Card delle squadre: stessa riga, due formati non confrontabili; e il valore «stabilizzato» dei giocatori si vede solo al passaggio del mouse

**Osservato (a).** «xPTS vs punti reali»: Roma `11,2 vs 12` + `4 gare · in linea`; Inter `6,8 vs 9`
+ `3 gare · sovra/sotto-performance` con `+2,2`. Una squadra mostra il giudizio, l'altra il delta:
il lettore non può confrontarle, e «in linea» non dice quanto.

**Osservato (b).** Nella tabella «I giocatori che decidono», la cella `xG+xA/90` stampa **due
numeri** quando i minuti sono sotto 270: il valore grezzo e, a capo, quello stabilizzato
(Malen `1,55` / `1,08`). Il significato sta solo in un `title` al passaggio del mouse. Nella scheda
giocatore (`giocatore.html:35`) lo stesso valore è marcato con **◎** e spiegato in legenda: due
trattamenti diversi per lo stesso oggetto.

**Misura.** DA MISURARE: quante righe giocatore pubblicano il doppio valore (atteso: tutte quelle
sotto 270 minuti, cioè la maggioranza a inizio stagione — nella scheda Roma-Inter 5 righe su 6).

**Impatto.** (a) due squadre della stessa partita giudicate con due scale. (b) su touch il secondo
numero non ha spiegazione: sembra un refuso.

**Soluzione pronta.** (a) sempre entrambe le informazioni: `11,2 vs 12 (+0,8) · in linea`.
(b) marcatore ◎ e una riga di legenda sotto la tabella, identica a quella di `giocatore.html`:

```html
<b>{{ p.contrib_p90|dec }}</b>{% if p.contrib_p90_shrunk is not none %} <span class="mut small">◎ {{ p.contrib_p90_shrunk|dec }}</span>{% endif %}
…
<p class="small mut">◎ valore stabilizzato con prior bayesiano (180′ verso la media di ruolo) per
campioni sotto 270′: con pochi minuti il valore per 90 è rumore.</p>
```

---

## 13. [P2] «Analisi pre-partita»: profondità diseguale fra le leghe, per regola e non per dati

**Osservato.** La sezione è generata da regole (`analysis.py:narrative`): la forma recente compare
solo se è estrema («Roma arriva in **grande forma**: VVVV nelle ultime 4»). Nelle schede POR1 lette
la riga non compare per nessuna delle due squadre, mentre i dati ci sono — la stessa scheda mostra
«Forma: N V N V N» e «6 gare: 1,33 xG …» più sotto.

**Misura.** Righe narrative per lega (tabella in §0): POR1 **5,4** di media contro NED1 **7,7** e
ESP1 **7,3**; minimo POR1/ITA1/FRA1 = 4 righe. Qualifica «giocatore di peso» nelle assenze:
**0 occorrenze in POR1** contro 7 in ITA1 e 5 in ESP1/FRA1.

**Impatto.** È il caso d'uso della direttiva utente sulla parità (`docs/00` §F): stessa sezione,
stessa presenza, **profondità diversa del 30%** fra la lega meglio e quella peggio servita. Non è
colpa dei dati (la forma c'è): è la regola che parla solo quando il caso è eccezionale, quindi le
leghe con più dati anomali sembrano più raccontate.

**Soluzione pronta.** Rendere la forma **sempre** presente, con la stessa onestà sui casi:

```python
# la forma non è un'eccezione da segnalare, è un contenuto obbligatorio: se non è estrema si
# dice comunque, con i numeri, invece di tacere (parità §F fra le 7 leghe)
righe.append(f"{nome}: {punti} punti nelle ultime {n} ({forma}) — "
             f"{aggettivo_se_estrema or 'andamento nella norma'}")
```

e per le assenze, quando l'impatto non è calcolabile, dirlo invece di omettere la qualifica:
«Assenze Estrela da Amadora: 1 (impatto non calcolabile: giocatore sotto la soglia di minutaggio) —
Jeremy Arévalo».

**Verifica.** censimento (lo script di questa sezione, riusabile): deviazione standard delle righe
narrative fra le 7 leghe < 0,5; nessuna lega con 0 occorrenze di una qualifica che le altre hanno.

---

## 14. [P1] «Verifica approfondita»: tre `h2` di fila dove il primo è il padre degli altri due

**Osservato.** La struttura pubblicata è:

```
<h2>Verifica approfondita: risultati esatti e distribuzione gol</h2>
   per chi vuole controllare i numeri
<h2>Matrice dei punteggi</h2>
<h2>Quanti gol, in pratica</h2>
```

Un'intestazione che annuncia un contenitore, seguita da due intestazioni **allo stesso livello**
che ne sono il contenuto. È il caso particolare del riscontro `docs/19` §3.6 (salto di livello in
4.128 pagine su 4.128): qui non salta un livello, ma la gerarchia dice il falso — un lettore che
naviga per intestazioni (screen reader, o l'indice del browser) vede tre sezioni sorelle dove ce
n'è una con due figli.

**Misura.** DA MISURARE sul sito: numero di `h2` che hanno come fratello seguente un `h2` di cui
sono semanticamente il padre (candidati: «Verifica approfondita», «Post-partita»).

**Soluzione pronta.** `h3` per i due figli, oppure (meglio, perché l'ancora `#verifica` è già nei
link interni) mantenere l'`h2` padre e declassare i figli:

```diff
- <h2>Matrice dei punteggi</h2>
+ <h3>Matrice dei punteggi</h3>
```

Attenzione: le due card sono visivamente indipendenti, quindi `h3` va accompagnato da uno stile che
non le faccia sembrare minori (`.detail-card h3` con lo stesso peso visivo di `h2`).

---

## 15. Riepilogo e piano

| # | Sezione | Riscontro | Sev. | Misura chiave |
|---|---|---|---|---|
| 1 | Come nasce questa probabilità | passo 2 etichettato «media 70/30» ma è la griglia sulle λ inclinate; il tilt non compare | **P1** | scarto medio **1,18 pp**, max **7,87**; **8** gare con preferito diverso |
| 2 | Verifica approfondita | «verify_site controlla 11.582 numeri» scritto a mano | **P0** | vero **15.548**; **371** pagine; scarto **−25,5%** |
| 3 | Scontro tattico | tooltip dichiara FotMob dove il valore è Understat (5 leghe su 7) | **P1** | bias sistematico **+9,5%**, max **0,641** xG/gara |
| 4 | Scontro tattico | componenti FotMob che non sommano al totale Understat | **P1** | 2,55 + 0,25 = **2,80** vs **3,45** pubblicato |
| 5 | Sintesi | margine «+5,8 punti» accanto a 40% e 34% | **P1** | incidenza DA MISURARE (attesa 30-50%) |
| 6 | Sintesi | «1,35–1,48 gol attesi» letto come intervallo; totale assente | P2 | due notazioni nella stessa pagina |
| 7 | Sintesi | «scarto 0,8 punti sul preferito» senza soggetti | P2 | — |
| 8 | Previsione del modello | `1179 partite` senza separatore + «~1·200» in nota | P2 | POR1 stampa 969 con la stessa nota «~1·200» |
| 9 | Risultati esatti | 6 risultati senza la quota di probabilità coperta | P2 | coprono **51,1%**, non dichiarato |
| 10 | Come arrivano | «punti sopra attesi · tendenza in calo» = due grandezze accostate | **P1** | **10 righe su 29 (34%)** in lettura contraddittoria |
| 11 | Contesto | «Coda 6+ gol» vs «Totale 7+ gol»; precedenti non separati per campo | P2 | 0,7% vs 2,6% a pochi pixel |
| 12 | Card squadre / giocatori | due formati per xPTS; ◎ mancante sul valore stabilizzato | P2 | 5 righe su 6 con doppio valore |
| 13 | Analisi pre-partita | profondità diseguale per regola, non per dati | **P1** | POR1 **5,4** righe vs NED1 **7,7**; «giocatore di peso» **0** in POR1 |
| 14 | Verifica approfondita | gerarchia `h2` → `h2` dove il primo è padre | **P1** | caso particolare di `docs/19` §3.6 |

**Ordine di esecuzione proposto** (ogni passo con test + `fda build` + `verify_site.py`):

1. **#2** (una riga di template, è un'affermazione falsa pubblicata 371 volte);
2. **#1** (catena a quattro passi: è la sezione che spiega il modello, e gli ingressi sono già salvati);
3. **#3 + #4** (stessa tabella, stessa causa: attribuzione della fonte);
4. **#5 + #6 + #7** (stessa riga di testa, si correggono insieme);
5. **#10 + #13** (narrativa: soggetto alle grandezze e parità fra leghe);
6. **#8, #9, #11, #12, #14** (finiture).

**Prossimo passo concreto**: applicare #2 e #1, con i due test indicati nelle rispettive «Verifica»
e un'invariante nuova in `verify_site.py` — **ogni Δ pp pubblicato deve equalare la differenza fra
due passi adiacenti stampati**, che è la regola che avrebbe preso il difetto #1 da sola.
