# 89 — Test prospettico γ 1,12, stagioni StatsBomb, clima (2026-10-12)

## 1. Test prospettico γ 1,12 (approvato dall'utente)

**Protocollo, fissato prima dei dati** (codice: `src/fda/models/prospettico.py`):
- ogni `fda predict` registra per ogni partita futura due varianti nella tabella `prospettico`:
  `prod` (la previsione pubblicata) e `gamma_112` (le **λ pubblicate**, γ 1,12 sul rapporto, a
  totale invariato, griglia Dixon-Coles, 1X2; nessuna ricalibrazione aggiuntiva);
- una riga per partita e variante, aggiornata fino al calcio d'inizio; poi non si tocca più;
- valutazione solo su partite finite con entrambe le varianti; ΔRPS appaiato, bootstrap 2.000 ricampionamenti, seme fisso;
- **promozione** solo con almeno **200** partite, IC 95% interamente negativo e migliore in almeno **5** campionati su 7.

**Differenza dichiarata rispetto al laboratorio:** il laboratorio applica γ all'ensemble prima dei gol
attesi finali; il test la applica alle λ pubblicate. Misura quindi la ricetta pubblicabile.

**Stato:** il test parte dal prossimo run di previsione. Nessuna partita è ancora valutata; la
pagina «Laboratorio» mostra lo stato in corso. Test: `tests/test_prospettico.py` (5 test).

## 2. Stagioni StatsBomb: il piano non è realizzabile

Verificato sull'elenco ufficiale di competizioni (`data/competitions.json` del repo `hudl/open-data`):
- **La Liga**: 2004/05 → 2020/21 (copertura piena).
- **Serie A**: solo 2015/16 (e 1986/87). **Bundesliga**: 2015/16 e 2023/24. **Ligue 1**: 2015/16, 2021/22, 2022/23.
- **Premier League**: 2003/04 e 2015/16. **Eredivisie** e **Primeira Liga**: nessuna stagione.
- Né la stagione in corso né le ultime due sono disponibili.

Quindi StatsBomb **non** dà «4–5 stagioni precedenti per tutti i campionati». Può servire come
banco di prova per l'xG su La Liga 2017/18–2020/21 e su qualche stagione singola, con licenza per
ricerca e citazione obbligatoria.

**Alternativa per l'xG storico:** Understat. Il codice (`src/fda/sources/understat.py`) richiede già
qualsiasi stagione per campionato, ma nel repository c'è solo la stagione 2026 (554 partite).
Il backfill delle stagioni 2021–2025 per i 5 campionati va eseguito dove c'è rete (CI), perché
la sandbox non raggiunge understat.com. **Da decidere:** lo facciamo con un workflow manuale?

## 3. Clima del club (punto 10), revisione

- **Dati disponibili:** `news.parquet` contiene 5.076 titoli dal 27/09 all'11/10/2026 (due settimane).
  Il campo testo è vuoto: contiene solo il nome della testata.
- **Conseguenza:** uno sentiment non è misurabile oggi. Non c'è uno storico sul quale verificare se
  predice qualcosa, e il campione è troppo piccolo anche per una stima descrittiva.
- **VADER** è un modello per l'inglese; i titoli sono in italiano. Per l'italiano serve un modello
  diverso, da scegliere e validare.
- **Proposta:** la card resta regola-based (strisce, riposo, cambio allenatore, infermeria). Lo
  sentiment resta fuori finché non esiste un archivio di titoli con almeno una stagione. L'archivio
  si accumula già ora, quindi la decisione si può riprendere con dati veri tra qualche mese.

**Da decidere:** confermi la proposta, oppure preferisci un modello italiano descrittivo già da ora,
sapendo che non sarebbe una misura predittiva?
