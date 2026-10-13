# 102 — I due errori del `daily` erano già chiusi; la stessa classe restava in «UCL (prime 1)» e «Altri 1 arrivi» (2026-10-13)

L'utente apre la sessione incollando il log rosso del workflow `daily` con i due problemi
dell'issue #109. Questa sessione: (1) verifica **con prove** che quei due problemi sono già
corretti e in produzione, (2) misura se la stessa **classe** di difetto (««1» + nome plurale»)
esiste ancora sul sito pubblicato, (3) la chiude nei due punti misurati e allarga l'invariante
`[13-14]`. Nessun cambiamento di modello, nessun Parquet toccato.

---

## §1 — Verifica d'ingresso: i due errori del log sono già chiusi (con prove)

Il log incollato appartiene ai run su `6a0034c` (merge della PR #108, 10:11 UTC):

- `38381687223` (push, 10:11:45Z, 17m58s) e `38391444901` (schedule, 11:36:59Z, 15m57s) —
  entrambi `failure` al passo `verify_site`, con lo stesso elenco del log incollato
  (`[20] … 864 controlli`, `PROBLEMI (2): {'concordanza': 1, '«letture': 1}`).
- I due problemi erano già stati diagnosticati e corretti **lo stesso giorno** dal commit
  `b021aeb` («fix: sblocca daily (#109) su concordanza laboratorio e contatore letture sul
  tema», [docs/99](99_diagnosi_daily_109_hotfix_2026-10-13.md)), fuso in `main` con la PR #110
  (merge `b6d7cc3`, 14:31:39Z, ordine esplicito dell'utente, deroga `docs/13` §9.26).
- Prova dell'avvenuta chiusura:
  - run `daily` `38414127388` su `b6d7cc3` = **success** (16m21s) e commit dati
    `1364678` («data: run 2026-10-13 14:47 UTC»);
  - issue **#109 chiusa automaticamente** alle 14:47:42Z dal run verde (`scripts/ci_alert.py`);
  - verifica locale indipendente sul `main` di oggi: `fda build` (498/2.364/7.602) +
    `scripts/verify_site.py` → **nessun problema · 240.691 controlli numerici superati**.

Conclusione del §1: **non c'era nulla da correggere** del log incollato; il lavoro utile della
sessione è stato il §2.

## §2 — Misura della stessa classe sul sito pubblicato

Il difetto dell'issue era di classe: un **contatore uguale a 1** davanti a un **nome plurale**
(«1 campionati» nel test prospettico, «1 letture sul tema» nell'imbuto delle notizie). La lista
nera `AGREEMENT` di `verify_site.py` presidia solo i nomi elencati, quindi la sessione ha
misurato il testo di **tutte le 4.316 pagine pubblicate** con il parser del gate (lo stesso
`Text` di `check_pages`, che esclude già le citazioni della stampa):

- bigrammi «1 <parola>» distinti: **331** · occorrenze: **10.581**;
- di questi, parole che finiscono in ‑i/‑e (candidati plurali): **3.530**, quasi tutte
  **falsi positivi strutturali**: etichette di colonna in maiuscolo («1 Minuti 62»,
  «1 Stagione», «1 Grandi occasioni 4») e celle delle tabelle di confronto, dove l'1 è il
  valore della squadra e non il contatore («1 Ammonizioni 3»). La regex è case-sensitive: i
  titoli di colonna non la toccano. **Una regola generica «1 + parola che finisce in -i/-e»
  non è utilizzabile** (proverebbe a correggere 3.500 righe legittime): la lista nera misurata
  resta la strada giusta — è questa la misura che chiude il dubbio.
- Candidati **veri**, fuori dalla lista nera:

| Difetto | Dove | Occorrenze |
|---|---|---|
| `Altri 1 arrivi riconosciuti` | tendina della card Mercato, 5 schede pre-partita pre-partita (5781776, 5795476, 5802958, 5881191, 5881196) | 5 |
| `UCL (prime 1)` | cella «Posta in gioco» di POR1 (es. 5887594) e intestazione della tabella Proiezioni | 3 |
| `nelle prime 1 posizioni` | nota sotto la tabella della pagina Proiezioni (Liga Portugal) | 1 |

Cause: la lega **POR1 ha `ucl_spots: 1`** in `config/leagues.yaml`, quindi l'etichetta
«prime N» va al singolare; e la tendina degli arrivi oltre i primi 4 non prevedeva il caso
«ne resta esattamente uno».

## §3 — Correzioni (misura prima → dopo)

1. **`src/fda/site/fmt.py` — `ucl_label(spots)`**: fonte unica dell'etichetta
   (1 → `UCL (1ª)`, N ≥ 2 → `UCL (prime N)`, soglia ignota → `UCL`). Prima era scritta a
   mano in cinque punti (due template, `analysis.py`, due verificatori).
   Registrata come filtro Jinja `ucl_label` in `build.py`.
2. **`src/fda/site/templates/match.html`**: cella «Posta in gioco» →
   `{{ b.stakes.ucl_spots|ucl_label }}`; la tendina degli arrivi oltre i 4 diventa
   «Un altro arrivo riconosciuto» quando ne resta **uno** (con 8 arrivi resta
   «Altri 4 arrivi riconosciuti»); il tooltip dichiara la forma con un posto solo.
3. **`src/fda/site/templates/stagione.html`**: intestazione di colonna `{{ lg.top_n|ucl_label }}`
   e nota «chiudere **nella 1ª posizione** con accesso ordinario» quando la soglia è 1
   (l'aggancio «N/D» per gli snapshot senza soglia resta invariato).
4. **`src/fda/site/analysis.py`** e **`scripts/audit_panchina.py`**: la riga di classifica
   «in zona UCL (…​)» usa la stessa etichetta (il verificatore resta indipendente: ricompone
   la stringa dai Parquet, non chiama la funzione del generatore).
5. **`scripts/verify_site.py`**: le tre attese di `[19]`/Proiezioni riconoscono la forma
   singolare; `AGREEMENT` guadagna i plurali `arrivi, posizioni, occasioni, presenze,
   partenze, reti, trasferte, ammonizioni, espulsioni, parate, legni, angoli, sostituzioni,
   giornate, rimonte` — tutti **misurati a zero occorrenze legittime** sulle 4.316 pagine
   (nessuno segue mai un «1» corretto; i singolari veri «1 assente», «1 occasione», «1 voce»,
   «1 fonte», «1 rigore» non sono in lista, e i titoli di colonna in maiuscolo restano fuori).

**Misura dopo** (stesso giorno, sito ricostruito): `prime 1` → **0** occorrenze,
`1 arrivi` → **0**, `UCL (1ª)` presente dove serve (intestazione Proiezioni, nota, celle
POR1). Su una scheda POR1: `titolo 0% · UCL (1ª) 0% · retrocessione 2%`.

## §4 — Test aggiunti (6 casi)

- `tests/test_fmt.py::test_ucl_label_singolare_e_plurale` (6 parametri).
- `tests/test_stagione_dichiarazioni.py::test_ucl_con_un_posto_solo_e_concordato` — pagina
  Proiezioni con `top_n = 1`: «UCL (1ª)», «nella 1ª posizione», nessun «prime 1», e il gate
  `AGREEMENT` non trova nulla.
- `tests/test_mercato_revisione.py::test_un_altro_arrivo_singolare` — 5 arrivi in distinta →
  «Un altro arrivo riconosciuto», mai «Altri 1 arrivi».
- `tests/test_panchina_notizie.py::test_posta_in_gioco_con_un_solo_posto_ucl` — frammento
  vero del template con `ucl_spots = 1` → «UCL (1ª) 52%».
- `tests/test_panchina_notizie.py::test_zona_ucl_con_un_solo_posto` — riga di classifica
  «in zona UCL (1ª)».
- `tests/test_numeri_pubblicati.py::test_agreement_presidia_i_plurali_misurati` — il gate
  intercetta i difetti nuovi e **non** i singolari né le celle di tabella («1 Ammonizioni 3»,
  «1,2 ammonizioni»).

## §5 — Gate verificati

- `pytest -q`: **943 passati** (0 falliti; erano 932).
- `ruff check .`: **All checks passed!**
- `fda build`: **498 schede / 2.364 fixture / 7.602 giocatori**.
- `scripts/verify_site.py --site site --data data/processed`: **240.691 controlli · 0 problemi**.
- `scripts/parita_schede.py site`: **nessuna differenza** (58 schede pre-partita, stessa
  struttura/indice/quantità).
- `python -m scripts.resa_375`: **28.722 misure · 0 problemi a 375 px**.

## §6 — Punti aperti dichiarati

1. **`[20]` legge ancora l'HTML grezzo** (`head = blocco.split("<ul", 1)[0]`): il fix del
   13/10 (`· (?:<b>)?(\d+) lettur[ae] sul tema`) copre il tag `<b>` ma una futura
   decorazione diversa (es. `<span>`) farebbe **fallire** il contatore con «stampa 0» —
   rumore, non un dato sbagliato, ma un rosso evitabile. Da valutare: far leggere al gate il
   **testo** dell'imbuto (come fa già l'oracolo `club_news_checks.py`) invece della regex
   sull'HTML.
2. Restano le **ultime 3 sezioni** della revisione della scheda partita (`docs/101` §4):
   Precedenti, Previsione ensemble, Verifica approfondita.

## Prossimo passo

La PR del branch di sessione porta: correzioni §3, invariante estesa, 6 test. Poi la coda
resta quella di `docs/101` §4 (3 sezioni) con la misura prima/dopo obbligatoria, e il punto
aperto §6.1 da decidere con l'utente.
