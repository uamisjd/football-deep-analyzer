## 2026-10-12 — `dc_xg` misurato: criterio non superato (docs/92–93)

**Fatto, fuori campione temporale e offline:** protocollo [docs/92](92_protocollo_dc_xg_2026-10-12.md)
pushato in `fbc811b` prima dei fit; codice `ad07059` con 69 test mirati; **un solo run** completo.
11.179 gare CI in input, **5.058 appaiate**, 4.810 con xG / 248 fallback NED1-POR1 identici.
**ΔRPS −0,000393, IC 95% [−0,001109; +0,000332], RPS più basso in 3/7 leghe: non passa**.
Nessuna promozione, nessun tuning dopo l'esito. Riferimento riaddestrato sullo stesso campione,
non previsioni storicamente pubblicate; risultato non generalizzabile a tutti i modelli xG.

- `fda lab-xg`: ricetta isolata, xG continui senza troncamento a interi, ρ dai gol dello stesso
  prefisso, calibrazione solo su finestre precedenti, input bloccati per hash, errore al primo
  fit fallito e confronto obbligatoriamente appaiato. Criterio sempre 200 gare / IC < 0 / 5 su 7.
- Metriche e bootstrap ricalcolati con un oracolo separato dai gol originali: coincidono entro
  10⁻¹². Cagliari–Lecce: usata la riga di gara per ID, mai i lati-squadra duplicati.
- Riepilogo in [docs/93](93_esito_dc_xg_2026-10-12.md) e `docs/_lab_xg_2026-10-12.json`;
  dettagli rigenerabili in `data/cache/lab_xg/` (non versionati). Nessun Parquet di produzione
  modificato, compresi `season_sim*`; laboratorio pubblico ancora sul campione CI di 1.654.
  Il prospettico γ resta separato: nessun nuovo run su dati reali.

**Gate verificati:** **743 test** passati, Ruff pulito; CI del codice verde (run `38277105600`,
`38277101042`, commit `ad07059`). **Build completa, verify_site, parità e resa ancora in corso**:
non dichiarati conclusi. PR #108 sempre in bozza, nessun merge; tutti i commit sul ramo della sessione.

**Prossimo:** chiudere i gate, poi punto 4: Panchina e posta in gioco → Mercato → Vita del club
→ Previsione ensemble → Precedenti → Verifica approfondita. Metodo: misura → correzione →
invariante/test. **Decisioni aperte:** campionati/stagioni StatsBomb; conferma card clima basata
su regole e sentiment rinviato. Nessuna scelta fatta al posto dell'utente.

## 2026-10-12 — Merge PR #107 verificato: storico e avvio prospettico (docs/91)

**Fatto e verificato sui dati CI:** PR #107 unita (`1bc3a71`), primo `daily` post-merge
`38251884898` riuscito, storico manuale `38271006444` riuscito. Il checkout iniziale
`514309d` era già `main`; la voce «Merge PR #107» dell'handoff non era stata salvata qui.

- **Storico Understat 2021–2025 completo:** 1.826 / 1.826 / 1.752 / 1.752 / 1.752 gare
  finite = **8.908**; **17.816** lati-squadra incrociati senza orfani, duplicati o differenze
  nei gol/xG. Nuovo audit ripetibile `scripts/audit_understat_storico.py`, 10 test.
- **Prospettico avviato:** **3.856 righe / 1.928 coppie**, sette leghe, tutte pre-partita;
  produzione e variante riprodotte senza differenze in uno store temporaneo. **0 risultati**
  valutabili nello snapshot. Nessuna promozione; soglie 200 gare, IC < 0, 5/7 immutate.
- **Difetto misurato e corretto sul branch:** `record` accettava righe postume e riscriveva
  coppie congelate; `evaluate` le contava. Prima: 2 righe postume, 2 riscritte, 1 gara
  valutata; dopo: **0 / 0 / 0**. Ora controllo del kickoff corrente e archiviato,
  validazione numerica, confronto solo fra coppie dello stesso snapshot. 31 test prospettico.
  Nei dati reali **nessuna violazione osservata**. Fix non ancora in `main`.
- **Avviso sui soli dati correnti:** due lati extra di Cagliari–Lecce 07/09/2026, alle 16:00
  oltre alle 16:30 corrette: possibile residuo di aggiornamento d'orario. Non riguarda lo
  storico 2021–2025; non cancellato per deduzione. Dettagli e limiti in `docs/91`.

**Gate finali verificati:** **700 test** passati; `ruff check .` pulito; audit storico 0 difetti;
`fda build` **498/2.364/7.594**; `verify_site` **239.517 controlli, 0 problemi**;
parità **63 schede, nessuna differenza**; resa a 375 px **28.657 misure, 0 problemi**.
CI `tests` del codice verde: run `38273582240`, commit `836a0a2`.
**PR [#108](https://github.com/uamisjd/football-deep-analyzer/pull/108) in bozza**, aperta
per conservare questo blocco e proseguire la coda sullo stesso ramo; **non unita**.
Il commit finale dei gate e del numero PR aggiorna solo la documentazione.
Nessun Parquet modificato; i due `season_sim*` restano fuori dal lavoro (in questo checkout
sono entrambi già tracciati). Nessuna richiesta alle fonti; API GitHub lette, log integrali
Actions non raggiungibili.

**Prossimo, in ordine:** (3) implementare e testare **un solo `dc_xg` preregistrato**:
nei documenti esiste, nel registro del laboratorio **no**. Campione CI 1.654, nessuna
variante robusta; non sostituito con il campione locale 3.157. Understat copre 5 leghe,
non ridurre la regola da 5/7 a 5/5. (4) sei sezioni della scheda ancora da revisionare:
Panchina e posta in gioco, Mercato, Vita del club, Previsione ensemble, Precedenti,
Verifica approfondita — misura → correzione → invariante/test.

**Decisioni utente aperte:** campionati/stagioni StatsBomb; conferma card clima basata su
regole con sentiment rinviato. Nessuna decisione presa al suo posto, nessuna PR unita.
Il congelamento resta conservativo anche se un rinvio diventa noto dopo il kickoff
archiviato: può conservare una previsione meno aggiornata, mai riaprire il test a posteriori.

Le due voci successive sono storiche: gli stati «PR in bozza» e «test dal prossimo run»
sono superati dalle verifiche sopra. Relazione: [docs/91](91_verifica_storico_avvio_prospettico_2026-10-12.md).

## 2026-10-12 — Storico Understat e PR #107 (docs/90)

- Comando `fda understat-storico` (stagioni 2021–2025, 5 leghe) e workflow manuale `understat-storico.yml` (commit dei Parquet solo se cambiano, `[skip ci]`). Test pianificazione: 2.
- Il workflow non è lanciabile finché non è su `main`: GitHub risponde 404 su un workflow manuale che non esiste sul branch di default. PR #107 in bozza, non unita: il merge è dell'utente.
- Non verificato: il recupero reale da Understat (la sandbox non lo raggiunge). Non ancora misurato alcun risultato sul candidato `dc_xg`.
- Aperti: sei sezioni della scheda, StatsBomb (decisione utente), clima (decisione utente).

## 2026-10-12 — Test prospettico γ 1,12, verifica StatsBomb, clima (docs/89)

Decisioni dell'utente: (1) rivedere il clima; (2) StatsBomb su tutti i campionati, 4–5 stagioni precedenti; (3) procedere con le sezioni della scheda; (4) test prospettico γ 1,12.

- **Test prospettico** (`src/fda/models/prospettico.py`, tabella `prospettico`, hook in `fda predict`, sezione in «Laboratorio»): registra produzione e γ 1,12 sulle λ pubblicate prima del calcio d'inizio; promozione solo con 200 partite, IC interamente negativo, 5/7 campionati. 5 test. Nessun risultato ancora.
- **StatsBomb (2): non realizzabile come chiesto.** La Liga 2004/05–2020/21; altri campionati solo poche stagioni; Eredivisie e Primeira nessuna; stagioni recenti assenti. Proposta alternativa: backfill Understat 2021–2025 via CI (da decidere).
- **Clima (1): revisione.** Notizie disponibili solo due settimane, testo vuoto, VADER inglese: sentiment non misurabile oggi. Card resta regola-based; archivio titoli già in accumulo.
- **Sezioni scheda (3): da fare** nel prossimo giro.

**Gate:** `pytest` 662 passati, `ruff` pulito, `fda build` completo, `verify_site` 0 problemi · 235.696 controlli. Nessuna richiesta a fonti esterne in questa tranche, salvo la verifica di StatsBomb.


---

Voci precedenti: [archivio del 12/10](STATO_archivio_2026-10-12.md),
[archivio del 07/10](STATO_archivio_2026-10-07.md); ulteriori archivi `STATO_archivio_2026-09-*.md`.
