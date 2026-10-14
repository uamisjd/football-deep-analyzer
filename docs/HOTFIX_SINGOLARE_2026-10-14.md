# Hotfix del singolare nell'oracolo [50] — 14 ottobre 2026

## Esito reale dopo il merge

PR #116 unita con deroga esplicita dell'utente: merge `8a6791a`, 09:19:25 UTC.
I tre check GitHub erano verdi su `d1465b7`; questo **non** dimostrava che tutte le
combinazioni delle nuove notizie reali fossero coperte dalle fixture.

[Daily 38541503143](https://github.com/uamisjd/football-deep-analyzer/actions/runs/38541503143):
**run failure**, **deploy skipped**, **notify success**. L'issue #114 resta aperta,
con un nuovo commento che conserva la diagnostica. Il sito non è ancora ripristinato.
Il gate segnala quattro intestazioni assenti: pagina/squadra
`5781768/8614`, `5781771/10229`, `5781774/6414`, `5781775/6433`.
Gli altri gate successivi, il salvataggio e il deploy non sono stati eseguiti.

## Causa riprodotta e correzione minima

Il parser residuo usa `voci?`, che riconosce «voci» (e l'inesistente «voc»), ma **non**
«voce». Il template rende correttamente «1 voce». I precedenti casi con zero,
due o tre voci, pur coprendo l'isolamento tra squadre, non esponevano questo errore.

**Prima di modificare il controllo:** cinque regressioni renderizzate dal vero
`SiteBuilder` falliscono, con i lati vuoto/singolare/plurale scambiati.
Prova ulteriore standard-library: intestazioni 0/2 riconosciute, intestazione 1 no.

**Patch:** una sola espressione, `voci?` → `voc[ei]`. Nessun cambiamento a HTML,
fonti, dati, pubblicazione, ricetta del modello o significato dei conteggi.
Si accettano le due forme italiane corrette; non si disabilita il gate.

**Dopo:** 38 test tematici passati, di cui 10 regressioni nuove:
cinque combinazioni su entrambe le lingue `nl`/`pt`. Pagine generate dal template
reale, non stringhe HTML adattate alla regex. Per ogni combinazione viene anche
manomesso il conteggio «1 voce» → «3 voci»: il gate deve ancora rilevare la bugia.
Restano verdi le regressioni precedenti su titoli non archiviati, lingua falsa,
conteggi falsi e isolamento dei due riquadri. Ruff e `pip check` puliti.
Suite completa: **1.033 passed in 145,25 s**. Dopo l’aggiunta delle manomissioni
dei conteggi, ripetuti tutti i 38 test tematici: ancora verdi.

## Limiti / prossimo passo

La diagnosi e la regressione sono provate; la patch **non è ancora su main**.
Il sito/dataset del run fallito non viene dichiarato ripubblicato o archiviato.
Aperta [PR #119](https://github.com/uamisjd/football-deep-analyzer/pull/119); i tre check
GitHub sono in attesa al checkpoint di apertura. Il merge resta all’utente perché la
deroga riguardava solo #116. Poi verificare il nuovo daily fino al deploy,
la chiusura automatica #114 e i salvataggi. Nessun dispatch duplicato o chiusura
manuale dell'allerta per mascherare il fallimento.
