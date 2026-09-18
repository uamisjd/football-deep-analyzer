# 35 — P2.2 applicata: le assenze in un posto solo, e la parità fra le schede (19/09/2026)

> Terzo intervento della coda **P2** di `docs/28` §3, dopo P2.1 (`docs/33`) e P2.4 (`docs/34`).
> Sessione `arena/01a0b61a`, branch `arena/01a0b61a-football-analyzer`, base `938c42a`.

---

## 1. Il difetto, misurato

Le assenze erano raccontate in quattro punti della scheda: la **frase della narrativa** (fino a
quattro nomi), la **tabella dell'infermeria** (con impatto, motivo e rientro), lo **stato dentro «I
giocatori che decidono»**, il **segnale aggregato in «Clima del club»**. Misura sulle 60 schede
pre-partita: **129 nomi elencati nella sola frase di narrativa** (mediana 2 per scheda, max 3),
tutti presenti anche nella tabella — con **più** informazione lì (minuti, gol+assist, xG+xA per 90
con la stima stabilizzata, motivo, rientro). In 4 schede c'era anche l'avviso «il contributo
offensivo più alto della lista è indisponibile», che ripeteva **motivo e rientro** della stessa
persona già nella riga dell'infermeria.

## 2. Che cosa è cambiato

1. **La tabella è la fonte unica.** La frase della narrativa tiene ciò che la tabella non dice in
   una riga — *quanto* pesa l'assenza (quanti, quanti titolari abituali, quanta produzione
   offensiva manca) — e manda al dettaglio: «Lecce deve rinunciare a 3 assenti — nomi e impatto in
   «Indisponibili».» col link **→ Infermeria**, che atterra sull'infermeria **della squadra giusta**
   (`#infermeria-home` / `#infermeria-away`, nuove ancore nelle card delle due squadre).
2. **A gara finita i nomi restano nella frase**, perché lì la tabella non c'è: la fonte riporta le
   assenze una volta su due (133 sì e 138 no sulle 271 finite misurate il 2026-09-13), quindi la
   pagina non può distinguere «nessuno fuori» da «non raccolto» e non deve fingere. Il generatore e
   il template usano la **stessa** condizione (`status != 'finished'`).
3. **«Il migliore della lista è indisponibile»** non ripete più motivo e rientro: ci manda.
4. **«Clima del club» non sparisce più** quando nessuna delle due squadre ha segnali: la riga per
   squadra dice già «Nessun segnale anomalo nei dati raccolti: clima normale», e il lettore non
   deve poter confondere «clima tranquillo» con «dato non raccolto». Era l'**unica** differenza di
   struttura fra le 60 schede pre-partita (Alverca–Rio Ave, 59 su 60).

## 3. Misura prima/dopo

Due build dello stesso codice sugli stessi dati (`938c42a` → codice attuale), stesse 60 schede
pre-partita.

| grandezza | prima | dopo |
|---|---|---|
| nomi di indisponibili elencati nella frase di narrativa | **129** (mediana 2 · max 3) | **0** |
| frasi con il link all'infermeria (`→ Infermeria`) | 0 | **60/60** |
| lunghezza della frase (mediana) | 96 | 90 |
| avviso «il migliore è indisponibile»: motivo e rientro ripetuti | 4 schede | **0** (link) |
| schede con «Clima del club» | 59/60 | **60/60** |
| struttura (id delle card) identica in tutte le schede | 59/60 | **60/60** |
| voci dell'indice | 12 in tutte | 12 in tutte |
| testo visibile della scheda più leggera (mediana del gruppo 18.922) | 17.242 (91%) | 17.260 (91%) |
| sezioni con peso sotto un quarto della mediana | 0 | **0** |

La frase non si accorcia (96 → 90 caratteri di mediana): **il guadagno è che i nomi non si leggono
due volte**, e che il rimando porta al posto dove ci sono anche i numeri.

**Bilancio della sessione sulla scheda pre-partita** (base `2d3cf27` → oggi, stesse 60 schede):
testo visibile mediano **22.905 → 18.987 caratteri (−17,1%)**, tutte e 60 in calo (Δ mediano
−4.164, min −1.948, max −4.390).

## 4. La parità fra le schede: da misura a gate

Direttiva utente del 2026-09-19: *«assicurati che poi tutte queste modifiche vengano fatte in tutte
le schede pre match, ogni partita deve avere la stessa alta qualità e quantità»*.

La differenza di «Clima del club» era invisibile a tutti i controlli: nessuno guardava le schede
**l'una contro l'altra**. Ora c'è `scripts/parita_schede.py`, che confronta le schede pre-partita
fra loro e **esce 1** se:

1. l'insieme degli id delle card non è identico in tutte (una sezione in più o in meno);
2. le voci dell'indice non sono le stesse, nello stesso ordine;
3. una scheda scende sotto il **75%** della mediana del testo visibile, o una sezione presente in
   tutte scende sotto il **25%** della sua mediana (sezione «presente ma vuota» = guardia che
   scatta a metà).

Le forbici di peso legittime restano e la sonda le **stampa**: «Vita del club» 436–4.579 caratteri,
«Mercato» 1.677–2.425, «Precedenti» 277–954, «Come arrivano» 792–1.422 — una partita con tre
precedenti in archivio e una con quaranta non possono raccontare la stessa storia, e non devono: il
controllo è sulla **struttura** e sull'ordine di grandezza, non sull'uguaglianza dei dati.

Il gate gira anche in CI (`.github/workflows/daily.yml`, subito dopo `verify_site` e **prima** del
commit dei dati): una scheda che perde una sezione ferma il run, invece di finire online.

## 5. Il gate ha trovato un difetto introdotto da me

Prima stesura: il link `→ Infermeria` era agganciato alla sola presenza della frase. Su 369 pagine
`verify_site` è uscito **1** con una decina di `ancora interna mancante #infermeria-home/-away`:
**a gara finita la tabella dell'infermeria non esiste** (`absences_weight` è `None` per le partite
giocate), quindi quelle pagine avevano un link verso il nulla. Corretto con la stessa condizione
della tabella (`c.status != 'finished'`), e la regressione è ora fissata da un test che pretende,
su ogni `href="#…"` dentro la narrativa, un `id` corrispondente **in pagina** — sulle schede
pre-partita e su quelle giocate.

## 6. Gate

`pytest -q` **443 passed** (+1 `test_p22_assenze_in_un_posto_solo_e_clima_sempre_presente`; il test
delle assenze riscritto sul nuovo contratto: nessun nome nella frase, numero e peso dichiarati) ·
`ruff` pulito · `fda build` exit 0 (369 partite / 2.364 fixtures / 7.480 giocatori) ·
`scripts/verify_site.py` **exit 0 — 0 problemi · 100.020 controlli** (invariante **[21]**
aggiornata: la card del clima deve esserci su ogni scheda pre-partita, con il conteggio delle righe
«clima normale» pari alle squadre senza segnali) · `scripts/parita_schede.py` **exit 0 — nessuna
differenza fra le 60 schede** · `scripts/audit_match_sections.py` exit 0.

**Non verificato:** resa a schermo dei due link nuovi e dell'ancora (spaziature, focus da tastiera)
→ resta P2.8 di `docs/19`.

## 7. Anteprima

`site_preview/` (porta 8000) ha ora **dodici pannelli** prima/dopo, con il «prima» che è la build
del commit `2d3cf27` (l'ultima prima di questa sessione): P1.1, P1.2 (hero e «Come arrivano»),
P1.4, P1.3, P2.1, P2.4, il nuovo **P2.2** (frase degli assenti, infermeria che riceve il rimando,
avviso del migliore indisponibile) e i due pannelli sulla **parità** (la card che spariva, la
tabella delle misure). In fondo il bilancio dei sette interventi.

## 8. Prossimo passo

`docs/28` §3, in ordine di peso: **P2.3** (un micro-visivo nelle card di solo testo: barra del
percentile, quartili del primo gol, sparkline delle fasce storiche), poi P2.5 (badge forma
nell'hero), P2.6 (quote assenti = decisione). Con la parità ora sotto gate, ogni intervento
successivo va rimisurato con `scripts/parita_schede.py` oltre che con `scripts/prematch_sections.py`.
