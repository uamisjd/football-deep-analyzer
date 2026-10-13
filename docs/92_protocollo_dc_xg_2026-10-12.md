# 92 — Protocollo preregistrato di `dc_xg` (2026-10-12)

**Una sola ipotesi, fissata e pushata prima del fit e prima dei risultati.** Esperimento
retrospettivo di laboratorio, non test prospettico e non cambio della produzione.
L'esito sarà separato in `docs/93`; questo protocollo non si riscrive dopo averlo visto.

## 1. Campione e perimetro

Snapshot CI `514309d`, ereditato dalla PR #108. Dati letti, mai modificati:

- `understat_matches.parquet`: SHA-256
  `687d76830e96ff9dea6672764aa1e20e326ca679361114071ff03af798bb5047`;
- `history.parquet`: SHA-256
  `3927c7dfdfefdf1ff8d703524949659cfead26385871b1952522250811a4174c`.

Si prendono **solo gare finite**, stagioni iniziali 2021–2026, data strettamente precedente
al **12/10/2026 13:10 UTC**. Per ENG1, ESP1, ITA1, GER1, FRA1 si usa esclusivamente la
riga di gara Understat: **9.201 gare**, comprese le 8.908 dello storico verificato in docs/91.
Identità delle squadre dagli ID Understat, non da un'unione fuzzy fra nomi. I gol osservati
e gli xG della stessa partita provengono dalla stessa riga.

Per NED1/POR1 si usa lo storico già salvato: **990 / 988 gare**. Totale atteso: **11.179**.
Gli xG mancanti in questi due campionati **non vengono inventati**: la ricetta candidata
lì resta esattamente quella di riferimento. Vengono marcati come **fallback senza xG** e
non possono contribuire al numero di leghe migliori. Nelle cinque leghe coperte, invece,
un xG mancante o un fit fallito interrompe l'esperimento: nessun ripiego silenzioso sui gol.

`understat_team_matches` non è un input del modello: così il doppione d'orario corrente
Cagliari–Lecce documentato in docs/91 non diventa una partita in più nel fit. Una chiave di
gara duplicata, un dato non finito/negativo o gol non interi fanno fallire la preparazione.

## 2. Ricetta unica, senza ricerca di iperparametri

Riferimento: `dc_elo_prod`, **riaddestrato sugli stessi dati e prefissi** del candidato.
Non sono le vecchie previsioni pubblicate, né il loro punteggio sul campione CI di 1.654 gare.

Candidato: `dc_xg`, ensemble con la stessa inclinazione DC/Elo del riferimento:

- ξ **0,0018**; shrinkage **8**; peso del modello sui gol **0,7**; Elo k **20**, HFA **60**;
- λ stimate sugli **xG continui**, con attacco/difesa e vantaggio casa log-lineari:
  `λ_casa = exp(att_casa + dif_ospite + hfa)`, `λ_ospite = exp(att_ospite + dif_casa)`;
- obiettivo quasi-Poisson pesato: somma di `w × (λ − xG × log λ)` per i due lati;
  pesi temporali identici al riferimento, attacchi centrati a media zero;
- shrinkage: quello di `DixonColesModel`, con gli stessi pesi per squadra e ricentramento;
- ρ **dal fit DC sui gol reali dello stesso prefisso**, non da xG arrotondati;
- griglia dei punteggi, inclinazione Elo, limiti delle λ e mercati: codice comune al
  riferimento, nessuna correzione aggiuntiva su γ o temperatura;
- ottimizzazione deterministica L-BFGS-B, partenza da attacchi nulli e medie xG pesate;
  limiti numerici fissi: parametri attacco non centrati/difesa in [-4, 4], hfa in [-2, 2];
  massimo 1.000 iterazioni, `ftol=1e-12`, `gtol=1e-7`, `maxls=40`. Mancata convergenza = errore.

**Perché un fit dedicato:** verificato prima dell'esperimento che `penaltyblog` converte i
risultati in interi: xG `[1,25; 1,75]` diventano `[1; 1]`, `[0,75; 0,25]` diventano `[0; 0]`.
Passargli direttamente gli xG sarebbe un test diverso e distorto. Il fit continuo avrà
prove analitiche/sintetiche e controllo del gradiente prima del primo run reale.

**Limite della scelta:** questa ricetta cambia anche la verosimiglianza usata per stimare
le λ (quasi-Poisson xG invece di DC sui gol); non isola causalmente il solo contributo del
dato xG. Un esito favorevole o sfavorevole riguarda **questa ricetta**, non tutti i modelli xG.
Non verranno provati altri pesi, finestre o varianti dopo aver visto l'esito in questo giro.

## 3. Valutazione temporale

- Motore `lab.walk_forward`, finestre di **90 giorni**, minimo **800 gare** di allenamento
  per lega (parametri del laboratorio CI, non quelli del precedente run locale 28/600).
- Fit solo su date strettamente precedenti all'inizio della finestra. Le squadre mai viste
  nel prefisso sono escluse **per entrambi**; esclusioni e copertura vengono contate.
- Calibrazione iniziale **identità**, spostamento di ρ **zero** per entrambi. Non si legge
  `calibration.parquet`, perché i suoi parametri correnti usano anche esiti futuri rispetto
  alle finestre storiche.
- Ogni candidato corregge il proprio livello dei gol con la ricetta già nel laboratorio:
  gol/λ grezze sulle sole finestre precedenti, minimo 100 gare, fattore limitato a [0,85; 1,05].
  Nessun esito della finestra in corso può cambiare la sua calibrazione.
- Registrare per riga inizio finestra, massima data del fit, numerosità di calibrazione e
  presenza/fallback xG. Fit falliti non vengono ignorati. Prima del riepilogo, richiedere
  esattamente due previsioni valide per ciascuna gara eleggibile e nessuna gara extra.

## 4. Criterio fissato

Metrica primaria **ΔRPS appaiato = candidato − riferimento**, negativo = migliore.
Bootstrap per partita, **2.000** ricampionamenti, seme **11** (quello di `lab.paired_bootstrap`).
Il confronto aggregato è sulla ricetta dei **sette** campionati: nei due senza xG il delta è
zero, non un miglioramento. Riportare separatamente numero di gare con xG e fallback.

Stessa soglia richiesta: **almeno 200 gare, IC 95% interamente negativo, almeno 5 campionati
migliori su 7**. Per evitare che i fallback gonfino la numerosità, richiedere anche almeno
**200 gare effettivamente previste con xG**. Non si cambia 5/7 in 5/5.

Diagnostiche, non nuovi obiettivi da ottimizzare: RPS per lega, log-loss, Brier 1X2,
Brier dei sei mercati sui gol, bias delle λ, conteggi per stagione e copertura. Il criterio
statistico superato non autorizza una promozione: occorrono revisione e decisione dell'utente.

## 5. Riproducibilità, limiti e separazione dalla produzione

Comando dedicato previsto: **`fda lab-xg`**, offline, protocollo fisso. Artefatti dettagliati
(storia normalizzata, previsioni per gara e confronto) in `data/cache/lab_xg/`, ignorati da Git;
riepilogo compatto e hash degli input in `docs/93`. Nessuna scrittura su `predictions`,
`model_lab`, `prospettico` o `season_sim*`. Candidato escluso dal laboratorio generico di default
finché non gli viene fornito il suo input verificato: niente aggiornamento parziale del
Parquet pubblico che mescoli campioni diversi.

Limiti da mantenere nel verdetto: cinque leghe hanno xG, due no; gli xG storici sono quelli
recuperati oggi e potrebbero includere revisioni della fonte (non sono snapshot pre-partita);
bootstrap per partita non risolve tutte le dipendenze temporali/fra squadre; campione e
calibrazione non coincidono con le previsioni storicamente pubblicate. Si misura una ricetta
fuori campione temporale, **non un vantaggio già provato in produzione**.

## Prossimo passo

Implementare e testare il fit continuo e le barriere temporali, poi eseguire **un solo run
completo** su questo snapshot, senza cambiare la ricetta in base al risultato. Pubblicare
esito, limiti e tutti i gate in `docs/93`, quindi passare alle sei sezioni della scheda.
