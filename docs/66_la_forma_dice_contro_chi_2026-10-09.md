# 66 — La forma dice contro chi (2026-10-09)

Voce **B** della [coda](65_handoff_e_coda_fonti_2026-10-09.md), dopo la revisione
[«Le due squadre»](64_le_due_squadre_2026-10-09.md). Branch di questa sessione:
`arena/eb94e8df-football-deep-analyzer`. Merge esclusivamente dell'utente.

## 1. Recupero della sessione precedente

Verificato nel clone locale con `git log --all --oneline | head -20` e
`git cat-file -t f5dbdf3`: il commit **f5dbdf3 non è conservato**. Il clone è shallow,
con il solo commit iniziale `5b1119b`; il fetch del ramo precedente non contiene quel commit.

Recuperato invece `8f454cb` con `git fetch origin arena/014bd558-football-deep-analyzer`,
applicato come **fd5520d** e **pushato subito** sul ramo della sessione: solo `docs/13` §9.23
e il checkpoint in `STATO.md`, che registrano il merge della PR #97. Nessun nuovo merge.
All'ingresso, ultimo daily `37996976659` verde; nessuna PR aperta.

## 2. Misure di partenza già disponibili — NON ripetute

Misure del 9/10 fornite nel passaggio di consegne dell'utente:

- `history.parquet`: **7.467 gare**, dal 2023 al 20/09/2026, tutte le sette leghe;
- `models/predict.py::EloModel`, con nomi normalizzati da `teams.canonical()`:
  **132/132 squadre agganciate**, 100% in ogni lega;
- **135 punti Elo** fra il calendario più duro e quello più morbido;
- correlazione punti nelle ultime cinque / forza media degli avversari: **−0,33**;
- costo della passata Elo già misurato: **0,09 s**, **15.112 punti** nella serie
  (due per gara più il punto finale di ogni squadra).

Queste misure giustificano l'integrazione; **nessuna nuova fonte, richiesta sportiva o
ripetizione del benchmark esplorativo** in questa sessione.

## 3. Implementazione

In `src/fda/site/analysis.py`:

1. `_elo_series()` fa una passata cronologica, usando **penaltyblog** e i parametri
   `EloModel.k` / `EloModel.home_field_advantage`. Salva l'Elo **prima** di ogni gara;
   un punto sentinella finale conserva l'Elo dopo l'ultima. Risultati e nomi originali
   dei Parquet non sono modificati. La serie è calcolata una sola volta per build.
2. `team_elo(nome, before)` usa una ricerca binaria. Tra due gare serve il rating
   **prima della successiva**, non prima della precedente: altrimenti si perderebbe
   l'ultimo risultato. La gara esattamente al limite è esclusa. Per le vecchie righe
   con la sola data (mezzanotte), il risultato non entra durante quel giorno, di cui
   non si conosce l'ora di gioco. Squadra assente o data prima dello storico → nessun Elo.
3. `league_elo()` identifica le squadre dal **calendario**, non da `match_info`, e legge
   tutti i rating alla stessa data. Media, deviazione standard **di popolazione**, ranghi
   con parità a pari Elo; sotto **ELO_MIN_TEAMS = 10** nessun riferimento.
4. `form_strength()` arricchisce **le stesse gare di `form()`** con `opp_elo` e `opp_rank`,
   valutati prima di ogni singola gara della striscia. Il riferimento è la lega alla
   vigilia della partita descritta; la soglia è **sd_lega / √gare effettive**. Giudizio
   soltanto con **|diff| > soglia**, non a uguaglianza. Se manca un Elo non si spaccia la
   media di un sottoinsieme per quella dell'intera striscia: il riepilogo non si pubblica.
5. Il contesto riusa la lista restituita per `*_form`, badge e narrativa e passa anche
   `*_form_strength`: striscia e riepilogo non possono scegliere gare diverse.

In `match.html`: rango `(4ª)` accanto all'avversario e ⓘ con l'Elo **di allora**, dichiarato
come graduatoria di forza e non classifica a punti. Sotto la striscia:

> Avversari affrontati: forza media N contro M del campionato · più duro della media /
> più morbido della media / in linea col campionato

Il ⓘ spiega campione e soglia (un errore standard, **non un intervallo di confidenza**).
Il contatore usa `|it_plural('punto')`, anche quando l'errore arrotondato vale uno.
Nessuna modifica al modello di previsione o alla sua calibrazione.

## 4. Protezioni

- Invariante **[44]** estesa: su entrambe le squadre di **ogni scheda** ricostruisce ranghi
  ed Elo storici e ricalcola media degli avversari, media/deviazione di lega, giudizio e
  soglia, **senza chiamare `form_strength()`**. Verifica anche righe mancanti o spurie.
- `test_elo_series_letta_alla_vigilia`: ordine temporale, alias, limite esatto, intervallo
  fra due gare, ultimo punto, date senza ora, modifica di un risultato futuro, dati assenti.
- `test_form_strength_giudizio_solo_oltre_errore_standard`: almeno dieci squadre, media e
  sd, ranghi a pari Elo, limite esatto e superamento nei due versi, campione effettivo e vuoti.
- Test del gate ampliato con **≥10 squadre nel calendario e storico sintetico**: manomissioni
  di media, riferimento, giudizio, rango e rimozione della riga. La riga è prima verificata
  presente: nessun test verde perché la sostituzione non aveva trovato nulla.

## 5. Verifica finale — osservata offline, non gli attesi dell'handoff

| Gate | Esito |
|---|---|
| `python -m pytest -q` | **558 passed** (111,91 s) |
| `ruff check .` | pulito |
| `python -m fda.cli build` | **464 schede / 2.364 fixture / 7.510 giocatori** |
| `python scripts/verify_site.py` | **0 problemi · 200.185 controlli** |
| `python scripts/resa_375.py` | **27.255 misure · 0 problemi** |
| `python scripts/parita_schede.py` | **89 schede**, 24 id, 14 voci d'indice; nessuna differenza |

Conteggio dell'HTML generato:

| Lega | Schede | Righe «Avversari affrontati» | Ranghi | Giudizi oltre soglia |
|---|---:|---:|---:|---:|
| ENG1 | 65 | 110 | 350 | 24 |
| ESP1 | 83 | 146 | 530 | 28 |
| FRA1 | 57 | 96 | 300 | 23 |
| GER1 | 51 | 84 | 228 | 20 |
| ITA1 | 64 | 108 | 340 | 17 |
| NED1 | 75 | 132 | 480 | 26 |
| POR1 | 69 | 120 | 420 | 35 |
| **Totale** | **464** | **796** | **2.648** | **173** |

I valori **760 / 2.478 / 182** consegnati come attesi **non sono quelli di questa build**.
La revisione successiva ([docs/68](68_revisione_forma_mercato_2026-10-10.md) §2) ha isolato
l'effetto dell'orologio: data italiana fissata al **9/10 → 446 schede, 760 righe, 2.478 ranghi,
169 giudizi**; al **10/10 → 464, 796, 2.648, 173**. `history` e `fixtures` sono identici byte
per byte allo snapshot precedente: i dati del daily più recente **non spiegano** lo scarto
della forma (questa nota corregge la prima spiegazione, troppo generica).

Il **182** dell'handoff non si riproduce neppure sulla finestra del 9/10. Il codice e la
specifica sono stati confrontati con fit Elo su prefissi temporali indipendenti: **0 differenze
su 8.191 confronti e su tutti i 796 riepiloghi**. Non si cambia la soglia per inseguire il
contatore; senza il commit perso non si attribuisce lo scarto a una sua riga di codice.
La [44] è stata inoltre rafforzata per non condividere i lettori Elo del generatore e per
verificare anche i nomi degli avversari realmente stampati (docs/68 §3).

Nessun dato Parquet modificato, nessuna richiesta sportiva. Il lavoro è stato salvato e
pushato anche durante i gate (`4a8d073`), senza lasciare un altro commit solo nel workspace.

## Prossimo passo

Anche **D è completata**, solo sui Parquet locali:
[docs/67](67_modello_contro_mercato_offline_2026-10-09.md). Il lotto della **PR #98** conta ora
**562 test verdi**, Ruff pulito e CI del codice finale verde; i gate del sito qui sopra
restano quelli del codice definitivo (D non tocca il sito). **Merge dell'utente**.
