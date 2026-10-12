# 91 — Storico verificato e avvio del test prospettico (2026-10-12)

**Perimetro di questo giro:** punti 1–2 dell'handoff, più una correzione del congelamento
emersa dalla misura. Il punto 3 (`dc_xg`) e la revisione delle sei sezioni **non sono conclusi**.
Nessuna promozione, nessuna nuova fonte e nessuna modifica ai Parquet di produzione.

## 1. Provenienza verificata

Il checkout iniziale `514309d` coincideva già con `origin/main`. La prima voce di `STATO.md`
era però ancora «Storico Understat e PR #107», con PR in bozza: la voce «Merge PR #107»
indicata nell'handoff **non era presente nel repository**. Verificato via API GitHub:

- [PR #107](https://github.com/uamisjd/football-deep-analyzer/pull/107): unita il
  12/10 alle **12:53:12 UTC**, commit `1bc3a71`.
- [Primo daily dopo il merge](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38251884898):
  **success**, avviato alle 12:53:15, concluso alle 13:10:33; dati in `93e6a27`.
  Risultano riusciti anche i passi di verifica, commit e deploy.
- [Storico Understat](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38271006444):
  **success**, dispatch manuale su `main`, 15:32:37–15:34:15; dati in `514309d`.

**Limite della verifica live:** leggibili stato e passi dei run via API; non i log integrali,
perché il download viene reindirizzato a un host Actions non raggiungibile dal sandbox.
La prova sui contenuti è quindi la lettura indipendente dei Parquet committati dalla CI,
non un nuovo download da Understat o football-data.

## 2. Storico Understat: numero di partite finite

L'anno è quello **iniziale**: 2021 significa 2021/22, non l'anno solare.

| Stagione | ENG1 | ESP1 | ITA1 | GER1 | FRA1 | Totale |
|---|---:|---:|---:|---:|---:|---:|
| 2021/22 | 380 | 380 | 380 | 306 | 380 | 1.826 |
| 2022/23 | 380 | 380 | 380 | 306 | 380 | 1.826 |
| 2023/24 | 380 | 380 | 380 | 306 | 306 | 1.752 |
| 2024/25 | 380 | 380 | 380 | 306 | 306 | 1.752 |
| 2025/26 | 380 | 380 | 380 | 306 | 306 | 1.752 |
| **Totale** | **1.900** | **1.900** | **1.900** | **1.530** | **1.678** | **8.908** |

**Verificato offline sui dati CI:**

- tutte le 8.908 gare sono finite, con gol e xG presenti, finiti e non negativi;
- nessun ID Understat duplicato; nessuna chiave lato-squadra duplicata nello storico;
- `understat_team_matches` contiene **17.816 lati-squadra** delle stesse stagioni;
- incrocio su campionato, stagione, squadra e data/ora: **17.816 corrispondenze**, zero
  righe orfane e zero differenze nei gol, gol contro, xG, xGA e lato casa/trasferta;
- i conteggi coincidono con i calendari completi a 20/18 squadre delle cinque leghe.

La misura è ripetibile con **`scripts/audit_understat_storico.py`** (sola lettura, exit 1
in caso di difetti), coperto da test con archivi sintetici completi e corrotti. Il controllo
è esplicitamente limitato al formato delle stagioni **2021–2025**: non presume che futuri
campionati abbiano sempre lo stesso numero di squadre.

Questa è una prova di **completezza e coerenza interna**, non dell'esattezza degli xG
rispetto al campo e tantomeno della loro utilità predittiva. Le due tabelle sono della stessa
fonte, quindi la loro concordanza non costituisce conferma da una fonte indipendente.

### Avviso separato sulla stagione corrente (non nel backfill)

`understat_matches` contiene anche il calendario 2026/27: **1.752 gare**, di cui **293 finite**
(ENG1 59, ESP1 77, ITA1 58, GER1 45, FRA1 54). Totale del file: 10.660 righe, non altrettante
gare utilizzabili per addestramento.

Nei lati-squadra correnti ci sono **588 righe**, anziché 586. Misura puntuale:
**Cagliari–Lecce del 07/09/2026** è presente due volte per ciascuna squadra, alle 16:00 e alle
16:30, sempre con risultato 1–0; `understat_matches` (ID 31588) e il calendario FotMob
(ID 5749662) riportano solo le **16:30**. È compatibile con un aggiornamento d'orario
conservato dalla chiave di upsert basata sulla data, ma la causa a monte non è provata dai
log. **Non corretto in questo giro; non riguarda le 8.908 gare storiche.** Per `dc_xg` non
si dovranno contare ciecamente i lati correnti né dividerli per due: usare ID di gara e
un incrocio verificato. Nessuna riga di dati è stata cancellata per deduzione.

## 3. Il prospettico ha scritto davvero le sue righe

Dal primo daily dopo #107: **3.856 righe = 1.928 coppie `prod`/`gamma_112`**.

| Campionato | Partite / coppie |
|---|---:|
| ITA1 | 322 |
| ENG1 | 321 |
| ESP1 | 302 |
| GER1 | 261 |
| FRA1 | 252 |
| NED1 | 234 |
| POR1 | 236 |

- `made_at`: **12/10/2026 12:58:20.005375–12:58:28.758255 UTC**.
- Calci d'inizio registrati: dal **12/10/2026 16:30** al **30/05/2027 16:30 UTC**.
- Zero chiavi duplicate, zero coppie incomplete, zero registrazioni al/dopo il fischio.
- Probabilità finite, nel range [0, 1], somma 1 (errore massimo **6,7 × 10⁻¹⁶**).
- `prod` identica a `predictions` sulle 1.928 gare: differenza massima **0**.
- Replay dell'intera registrazione **in uno store temporaneo**, fissando l'orologio alle
  13:10 UTC: 3.856 righe, probabilità di entrambe le varianti identiche all'archivio CI
  (differenza massima **0**). I Parquet originali non sono stati riscritti.
- Valutazione sul calendario dello stesso snapshot: **0 partite**, nessun ΔRPS o IC,
  **nessun esito positivo o negativo del test**.

L'avvio è quindi verificato; l'efficacia di γ 1,12 resta da misurare. Il criterio non cambia:
**almeno 200 gare, IC 95% interamente negativo, almeno 5 campionati migliori su 7**, bootstrap
appaiato con 2.000 ricampionamenti e seme preregistrato (`docs/89`).

## 4. Misura → correzione → regressione: il congelamento mancava

**Difetto riprodotto offline prima di correggere:** `record()` si affidava interamente al
filtro delle partite future in `fda predict`; `evaluate()` si fidava delle date archiviate
senza controllarle. In uno store temporaneo, non nei dati reali:

| Prova | Prima | Dopo |
|---|---:|---:|
| Registrazione di una partita già iniziata | 2 righe scritte | 0 |
| Riscrittura di una coppia già congelata | 2 righe scritte | 0 |
| Coppia postuma importata, valutata come partita finita | 1 gara valutata | 0 |

**Correzione in `src/fda/models/prospettico.py`:**

1. il momento della registrazione è ricontrollato dopo il fit: kickoff strettamente futuro;
2. una gara che ha già raggiunto il kickoff **archiviato** non viene riaperta da un input con
   una data successiva; nessuna scrittura sul file se tutte le righe sono congelate;
3. probabilità, λ e ρ non validi vengono rifiutati prima di scrivere;
4. la valutazione richiede due varianti univoche, della stessa lega, data e snapshot
   `made_at`, entrambe pre-partita e con probabilità valide;
5. se il calendario contiene il kickoff effettivo, anche quello deve essere successivo
   alla registrazione; coppie ambigue, postume o incomplete sono escluse;
6. l'orologio è iniettabile nei test: nessuna dipendenza da una data futura hardcoded.

**Scelta conservativa e limite:** un rinvio noto solo dopo il kickoff originariamente
archiviato non sblocca la previsione: si conserva la vecchia coppia. Può renderla meno
aggiornata, ma evita di riaprire a posteriori un test già congelato. Cambiare questa politica
richiederebbe una regola esplicita, non un aggiornamento silenzioso dopo aver visto i risultati.

I test coprono il confine esatto del fischio, i rinvii, il file byte-identico dopo il
congelamento, input non validi, snapshot diversi, duplicati, coppie incomplete e le soglie
199/200 gare, 4/5 leghe e IC che tocca lo zero. **Non sono cambiati γ, bootstrap, metriche
né criterio di promozione.** La correzione è sul branch di lavoro, non ancora in `main`.

## 5. Punto 3: prerequisiti chiariti, esperimento ancora da fare

`dc_xg` è descritto in `docs/13` §7 e `docs/53` §6, **ma non esiste nel registro dei candidati
né come implementazione nel laboratorio**. Il backfill lo rende possibile, non già testato.
Il riepilogo CI conservato in `model_lab.parquet` ha ancora **1.654 partite** per la baseline
e **zero varianti che superano il criterio**; non è stato sostituito dal campione locale di
3.157 gare né da un esperimento parziale.

Il prossimo giro deve definire la ricetta xG prima di misurarla, allineare gli stessi
prefissi temporali per candidato e riferimento, evitare l'uso della calibrazione corrente
su dati passati e dichiarare la copertura: Understat copre **5 leghe**, non NED1/POR1.
**Nessun abbassamento della regola da 5/7 a 5/5 e nessuna promozione automatica.**

## 6. Gate e confini

- Baseline prima della modifica: **664 test passati**.
- Gate finali: **in esecuzione**; aggiornare questa sezione con gli esiti, non presumerli.
- Nessuna richiesta a Understat o football-data; nessun `predict` sullo store reale.
- Nessun Parquet modificato; `season_sim.parquet` e `season_sim_cond.parquet` esclusi dal lavoro.
  Nota di allineamento: nel checkout `514309d` risultano **entrambi già tracciati**; questo
  giro non li aggiunge, non li modifica e non li committa.
- Revisione delle sei sezioni della scheda: **non avviata**, resta dopo il laboratorio.
- StatsBomb (campionati/stagioni) e conferma della card clima regola-based/sentiment rinviato:
  **decisioni dell'utente ancora aperte**. Nessuna scelta fatta al suo posto.

## Prossimo passo

Implementare e misurare **un solo candidato `dc_xg` preregistrato**, con confronto appaiato,
criterio invariato e dati correnti incrociati senza duplicazioni; poi procedere con le sei
sezioni nell'ordine richiesto, sempre misura → correzione → invariante/test. Non proporre
il merge di una PR come se questi punti fossero già conclusi.
