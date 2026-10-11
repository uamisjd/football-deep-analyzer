# 77 — Issue #104: il daily del 10/10/2026 e il punteggio che arriva prima del calendario

L'utente mostra lo screenshot dell'issue **#104** («🚨 Fallimento run giornaliero (daily)»,
aperta da `github-actions` il 10/10 alle 17:48 CEST, run
[#243](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38064406770) su
`main`) e chiede «che succede?». Il daily raccoglie dati freschi, rigenera il sito e si
autoverifica con `verify_site`: stavolta la verifica ha trovato **15 problemi** e il deploy
è rimasto fermo all'ultimo sito buono. Diagnosi e correzione seguono la regola B.10.

## §1 — La misura: due sintomi, una sola causa

Dal `verify.log` del run:

- **12 hero** — «partite/5781765.html: hero «1–1» con didascalia «calcio d'inizio · 16:30»
  (un punteggio giocato non è un calcio d'inizio)» e undici sorelle (5795466, 5795467,
  5795471, 5795474, 5802948, 5868081, 5881179–5881187): gare giocate nel pomeriggio del
  10/10, il cui **risultato era già nei dettagli FotMob ma lo stato nel calendario era
  ancora «da giocare»** al momento della raccolta;
- **3 radar** — «Palle inattive %»: pagina e ricalcolo divergenti su 5749693 (4 vs 8) e
  5795465 (27 vs 19, 62 vs 58).

La causa comune è l'anticipo della fonte: l'endpoint dei dettagli partita pubblica gol e
statistiche **prima** che il calendario ribalti lo stato a «finished». È la stessa famiglia
dell'issue #99 (PR #100), dove l'incoerenza gonfiava il campione «alla vigilia»; lì si
stabilì che **il calendario è l'autorità su «gara giocata»**. I due sintomi sono due posti
in cui il sito (o il suo verificatore) non rispettava quella regola.

## §2 — Sintomo 1: il risultato accanto a «calcio d'inizio»

L'hero stampava il punteggio quando `c.home_goals is not none` — e i gol arrivano da
`match_info` (i dettagli, più veloci) — mentre la didascalia segue lo **stato**, che viene
dal calendario. Con la fonte in anticipo usciva «1–1 · calcio d'inizio · 16:30», la
combinazione che l'invariante [37] vieta giustamente (e che le liste non mostrano: le card
delle liste leggono il punteggio dal calendario, che ancora non ce l'ha → «vs»).

**Correzione** (`match.html`, docs/77 §2): il punteggio nell'hero (e nell'`h1` per gli
screen reader) esce solo se lo stato lo giustifica — `mostra_punteggio` è falso quando la
didascalia sarebbe «calcio d'inizio». Finché il calendario non dice «finita», la scheda
resta «vs · calcio d'inizio · HH:MM», coerente con le liste e col campione alla vigilia;
al ribaltamento dello stato, il daily seguente pubblica risultato e sezioni post-gara. Un
punteggio live resta visibile (la didascalia «in corso» non è «calcio d'inizio»).

## §3 — Sintomo 2: l'oracolo del radar con la finestra sbagliata

La scheda pre-partita disegna il radar stile **fermo alla vigilia**: il generatore chiama
`clash_radar(..., before=kickoff)`, che esclude dal campione le gare giocate dopo il calcio
d'inizio. L'oracolo [22b] di `verify_site` richiamava la stessa funzione **senza**
`before`: finché ogni scheda pre-partita aveva il kickoff nel futuro le due finestre
coincidevano e il controllo passava; sulle schede il cui kickoff è già passato ma lo stato
è ancora «da giocare» (la coda della stessa lentezza della fonte) l'oracolo contava anche
le gare successive e divergeva — 3 celle «Palle inattive %». **La pagina era giusta;
l'oracolo no.**

**Correzione** (`verify_site.py` [22b]): l'oracolo passa `before` = calcio d'inizio della
gara, la stessa finestra del generatore.

## §4 — Invarianti e test

- [37] esisteva già ed è il presidio che ha fermato il daily: continua a vietare un
  punteggio numerico con didascalia «calcio d'inizio»;
- `test_site.py` — `test_hero_niente_punteggio_se_calendario_indietro`: alla gara futura
  del seed vengono infilate i gol in `match_info` (il caso misurato su main); l'hero deve
  restare «vs · calcio d'inizio»;
- l'oracolo [22b] con `before` gira su tutte le pagine pre-partita a ogni run.

## §5 — Dopo la correzione

Con la regola del calendario rispettata anche nell'hero, le 12 schede del 10/10 avrebbero
pubblicato «vs · calcio d'inizio» fino al ribaltamento dello stato, come le liste; i 3
radar tornano a coincidere fra pagina e oracolo. L'issue #104 si chiude da sola al primo
run daily che completa tutti i passaggi: serve quindi che la correzione entri in `main`
prima del run successivo (merge della PR, regola D: lo fa l'utente). Gate rifatti su questa
branch: pytest **591 passed**, ruff pulito, build **470/2.364/7.530**, `verify_site`
**223.338 controlli · 0 problemi**, parità nessuna differenza, `resa_375` **27.312 · 0**
(il conteggio assoluto delle misure è sceso rispetto ai 27.696 precedenti perché l'ambiente
di sviluppo è stato ricreato — il `.venv` non persiste fra le sessioni — e i font tool
reinstallati misurano diversamente: a parità di sito byte-identico il gate resta 0 problemi).
Da questo giro esce anche un rinforzo di `verify_site`: il totale «matrice+coda» si confronta
arrotondato a 0,1, altrimenti 36 addendi in virgola mobile portano il limite inclusivo 100,6
a 100,60000000002 (falso allarme su 5749708).
