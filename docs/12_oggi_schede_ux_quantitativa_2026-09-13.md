# Oggi e schede partita — ricerca, misure e intervento UX (2026-09-13)

## Scopo

La richiesta non è «aggiungere più numeri» in modo indiscriminato. È rendere la decisione dell'utente
più rapida nella lista **Oggi**, senza impoverire la scheda, e rendere esplicita l'incertezza del
modello. Il lavoro combina:

1. **quantità misurata**: cosa è disponibile per ogni partita;
2. **qualità editoriale**: gerarchia, linguaggio probabilistico, fonti e degradazione onesta;
3. **qualità visiva**: scansione a colpo d'occhio, mobile, accessibilità e approfondimento a livelli.

Le ricerche esterne sono state usate come principi di progettazione, non come giustificazione per
inventare dati o importare dipendenze.

## Ricerca esterna e decisioni

| Principio | Evidenza | Decisione per CalcioMetro |
|---|---|---|
| Disclosure progressiva | [Nielsen Norman Group — Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/) raccomanda di mostrare subito ciò che serve spesso e rimandare il dettaglio avanzato a un livello secondario, con un passaggio evidente. | La lista mostra identità, stato, probabilità e contesto minimo; la scheda conserva matrice, xG, assenze, H2H e post-partita. L'indice sticky «Sintesi / Previsione / Dati e contesto / Post-partita» rende il secondo livello raggiungibile, non nascosto. |
| Dashboard leggibili | [Nielsen Norman Group — Dashboards: Making Charts and Graphs Easier to Understand](https://www.nngroup.com/articles/dashboards-preattentive/) indica posizione e lunghezza come codifiche quantitative più rapide da confrontare di aree e forme complesse. | La barra 1X2 resta lineare; vengono aggiunti etichette testuali, margine sul secondo esito e dati tabellari. Nessun donut decorativo per dare un'impressione di precisione. |
| Card come unità tematica | [Material Design — Cards](https://m2.material.io/develop/web/components/cards) definisce la card come superficie per un singolo soggetto, con titolo, supporto e azione in gerarchia chiara. | Ogni partita è una card autonoma: intestazione (stato/ora/lega), squadre, previsione, fatti rapidi, link «Analisi». La card non è un'unica grande area cliccabile ambigua. |
| Accessibilità | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) raccomanda gerarchia, focus visibile, contrasto, uso da tastiera e target adeguati; il criterio 1.4.3 richiede 4,5:1 per il testo normale. | I filtri sono veri button/select/input, hanno focus, `aria-pressed`, `aria-live`, testo oltre al colore, `time`, `aria-label` per la barra e layout mobile senza scroll orizzontale della card. |
| Probabilità, non verdetti | [Constantinou & Fenton, valutazione dei forecast calcistici](https://arxiv.org/abs/1908.08980) confronta RPS, Brier e log score e richiama la natura probabilistica della previsione. | «Margine sul 2° esito» non viene chiamato confidenza. La card espone il massimo, il margine e la concordanza/divergenza DC–Elo; la nota chiarisce che sono stime, non certezze né quote. |
| Aspettative dei live-score | Le pratiche raccolte in [Sportmonks — live score app](https://www.sportmonks.com/blogs/building-a-real-time-livescore-app-best-practices/) e il riscontro di prodotto su [Flashscore](https://apps.apple.com/us/app/flashscore-live-scores-news/id766443283) convergono su stato esplicito, minuto/risultato, fasi, formazioni e statistiche progressive. | La lista ha stato testuale e punto colorato (`In corso`, `In programma`, `Terminata`), ora locale, risultato e filtri. Non viene simulato un live feed: il sito resta statico e mostra l'ultimo aggiornamento. |

## Fotografia quantitativa del dataset usato

Verifica offline sullo snapshot locale del **13/09/2026**, dopo aver filtrato le partite nella data
locale `Europe/Rome`:

| Copertura oggi | Misura |
|---|---:|
| Partite | **21** |
| Campionati | **7/7** |
| Previsioni 1X2 | **21/21** |
| Classifica per entrambe le squadre | **42/42** squadre |
| Meteo con descrizione | **21/21** |
| Designazione arbitrale | **21/21** |
| Assenze dalla distinta | **145 righe: 63 lato casa + 82 lato ospite; almeno una in 21/21** |
| Precedenti utilizzabili (almeno 3) | **20/21** |
| Forma recente di almeno 3 gare per entrambe | **19/21**; le altre mostrano solo ciò che è disponibile |
| Segnale DC–Elo concorde | **20/21** |
| Segnale DC–Elo divergente | **1/21** |

Questi numeri misurano **presenza e comparabilità**, non accuratezza predittiva. L'accuratezza resta
valutata nella pagina [Accuratezza](../src/fda/site/templates/accuracy.html) con dati storici risolti.

## Cosa cambia nel codice

### Pagina «Oggi»

- riepilogo sopra la lista: partite, campionati, copertura del modello e prossimo calcio d'inizio;
- stato della giornata separato in corso / programma / terminate;
- card partita in tre livelli di lettura:
  1. **identità**: stato, ora, lega, squadre, classifica;
  2. **segnale**: barra 1X2, esito più probabile, margine sul secondo, confronto DC–Elo, λ e Over 2,5;
  3. **contesto**: forma V/N/P e punti, infermeria, meteo, arbitro, numero di precedenti;
- filtro client-side per stato, campionato e squadra, senza richieste di rete e senza cambiare la fonte;
- `aria-label`, `time`, focus da tastiera, testo duplicato al colore e target di almeno 36 px per i
  controlli principali;
- il filtro nasconde le sezioni giorno vuote e aggiorna un contatore `aria-live`.

### Scheda partita

- hero con stato, squadre, risultato/ora, stadio e lettura primaria del modello;
- KPI sintetici: esito più probabile, margine, λ, Over 2,5, entrambe a segno;
- segnale esplicito «DC + Elo concordano» / «DC ed Elo divergono»; se Elo non è presente compare
  «Segnale DC», non una falsa concordanza;
- indice sticky per muoversi nelle schede molto lunghe;
- il vento, già raccolto da FotMob, ora viene mostrato nel contesto solo quando presente;
- rimosso il campo «Quota equa»: non è un requisito editoriale dell'utente e distraeva dalla
  lettura del modello. La scheda dichiara invece che le percentuali non sono quote.

### Correzione qualitativa collegata

La narrativa non sceglie più automaticamente una squadra quando il **pareggio** è l'esito più
probabile: ora scrive «Il pareggio è l'esito più probabile» e mantiene tutte le probabilità visibili.

## Criteri di accettazione

1. **Parità**: una partita di ciascuna delle 7 leghe passa dalla stessa macro e riceve gli stessi
   campi condizionali; un dato assente resta assente, non viene riempito.
2. **Numeri**: il margine è mostrato con una cifra decimale per non trasformare 38,1%–37,2% in
   «0 punti»; il vettore 1X2 e la barra usano la stessa previsione.
3. **Stati**: il colore non è l'unico segnale; ogni stato ha anche una parola.
4. **Mobile**: sotto 760 px la card passa a una colonna, i filtri scorrono solo nella loro riga e
   non compare una tabella orizzontale per la lista.
5. **Degradazione**: senza H2H, arbitro, forma completa o previsione, la card omette quel fatto o
   dichiara il dato non disponibile; non usa zero come sinonimo di assenza.
6. **Regressione**: suite Python verde, build statico completo e controllo link/contenuti prima
   della PR.

## Misure da seguire dopo il merge

Il progetto non raccoglie analytics personali, quindi non va dichiarato un miglioramento di
conversione senza test utente. Al primo run live post-merge verificare:

- numero di card per giorno e copertura previsioni/classifica/meteo/arbitro;
- zero link mancanti e zero testo inglese residuo;
- coerenza `p_home + p_draw + p_away = 1` e coerenza del margine con il vettore pubblicato;
- resa a 375 px e da tastiera (focus sui filtri, ricerca, link «Analisi»);
- su un campione di gare risolte, andamento RPS/Brier e calibrazione: la nuova UI non deve essere
  scambiata per un miglioramento del modello.

## Verifica eseguita sul branch

- `.venv/bin/pytest -q`: **118 passed**.
- `.venv/bin/fda build`: **376** schede partita, **2364** fixture, **7392** giocatori.
- `.venv/bin/python scripts/verify_site.py`: **4087 pagine**, **1860 controlli numerici**, zero problemi; in particolare 136 matrici, 55 pagine in-play, 60 gare di accuratezza, 630 ruoli, 76 infermerie e 73 archivi H2H ricontrollati.
- Il verificatore ora tratta correttamente le ancore `#sezione` della jump navigation e non confonde il decimale «3,1 gialli/gara» con «1 gialli».
- Durante il controllo sono state rimosse dal Parquet due righe **stale**, non nuove stime: `Nottm Forest` e `Frankfurt` erano snapshot `dc-elo-ens-0.1` rimasti accanto alle righe canoniche `Nottingham Forest`/`Eintracht Frankfurt`. `season_sim` ora sostituisce lo snapshot per lega (`replace_by="league_key"`), così una futura rinomina non può duplicare le probabilità. Le somme pubblicate sono tornate 1/4/3 per ogni lega.
- Avviata la preview statica su `0.0.0.0:3000`; verificati nel rendering reale il riepilogo, 21 card/7 leghe, margini con una cifra decimale e la jump navigation sia per una futura sia per una finita. La resa a 375 px resta da confermare manualmente nel browser dell'utente.
- `ruff` sul perimetro toccato conserva **15 segnalazioni preesistenti** (FURB/RUF/UP/SIM, inclusi vecchi blocchi di `analysis.py`, `build.py` e `verify_site.py`); non è una regressione funzionale introdotta dalla P0. La CI del progetto esegue pytest.

## Prossimo passo

- Il `daily` GitHub Actions `34749412140` del 13/09 09:23 UTC ha completato raccolta, modelli e build ma ha fallito nel commit dei dati; Pages è stato saltato, quindi la produzione mostrava ancora l'ultima build riuscita delle 01:14. La PR #26 include rebase/push con retry e un errore esplicito al posto del precedente `|| true`.
- Eseguire il controllo visuale finale a 375 px/desktop nel live preview. Dopo il merge, il primo `daily` deve confermare dal vivo copertura, vento e stati; solo con dati risolti si valuteranno eventuali correzioni quantitative del modello.
