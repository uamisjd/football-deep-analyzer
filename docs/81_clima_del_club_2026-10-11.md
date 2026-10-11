# 81 — Card «Clima del club»: controllo a 360 gradi (2026-10-11)

Richiesta dell'utente: rivedere e verificare la sezione **«Clima del club»** per trovare errori,
correggerli e individuare miglioramenti o potenziamenti. Stesso metodo di `docs/76` (Le due
squadre) e `docs/78` (Panchina e posta in gioco): per ogni punto **misura → correzione →
invariante o test**, e alla fine i gate. La misura vive in `scripts/audit_clima.py`, che legge
l'HTML come sta e ricalcola **tutto** dai Parquet con strade diverse da quelle del generatore
(mai `club_mood`): strisce sulla stagione intera, riposo e congestione da calendario ∪ coppe,
xPTS da Understat **o** dal Poisson sui soli xG FotMob, infermeria da distinta e statistiche di
stagione, panchina dalle distinte.

Ambito: la card vive solo sulle schede pre-partita. Al momento della misura sono **77 schede
(154 celle-squadra)**, con **228 righe** pubblicate: toni `bad` 15 · `warn` 194 · `good` 19.
Per tipo: infermeria pesante 108 · scarto xPTS 55 · «non vince da» 19 · «imbattuta da» 19 ·
«crisi di risultati» 14 · panchina nuova 12 · «attacco a secco» 1.

---

## §1 — Difetto: i contatori delle strisce erano troncati alla finestra di cinque gare

**La misura.** `club_mood` leggeva la forma con `self.form(team_id, kickoff)`, che di default
prende le **ultime 5** gare: ogni striscia più lunga usciva come «5», un pavimento travestito
da numero. **14 celle su 154** pubblicavano un contatore sbagliato: Inter «imbattuta da 5» con
6 gare reali, Sparta Rotterdam «non vince da 5 (2 N, 3 P)» con 6 (3 N, 3 P), Willem II «5» con
7 (2 N, 5 P), FC Twente 5→7, Feyenoord 5→8, ADO Den Haag 5→7, Barcelona 5→8, Málaga 5→8,
Bournemouth, Brentford, Fulham, Le Havre, Monaco, Telstar. Il difetto si vede solo dove la
lega ha già giocato più di cinque giornate (Eredivisie, Premier, La Liga, Ligue 1, Liga
Portugal): in Serie A, a otto giornate, ogni squadra ha esattamente cinque gare finite.

**La correzione.** `MOOD_STREAK_N = 60` (una stagione intera) passato a `form()`: la striscia
è quella **vera**, non la finestra. Effetto: 14 celle cambiano numero, 0 righe compaiono o
spariscono. La nota della card lo dichiara («il numero è la striscia intera, non la finestra
delle ultime cinque»).

**Invarianti e test.** `scripts/audit_clima.py` confronta il numero **stampato** con la striscia
ricalcolata sull'intera stagione: `troppo_corta` 14 → **0**. Test nuovo
`test_clima_striscia_intera_non_finestra_di_cinque` (sette vittorie consecutive → «imbattuta da
7 gare», mai «da 5»). L'oracolo [21] di `verify_site` ricalcola la striscia dai Parquet e la
pretende nel testo, riga per riga.

## §2 — Ambiguità di perimetro: quali gare contano le strisce

**La misura.** Le strisce contano le sole gare di **campionato** (come la riga «Forma»), mentre
riposo e congestione includono le **coppe**: due perimetri diversi nella stessa card, senza che
la pagina lo dicesse. Con le coppe dentro, la stessa squadra avrebbe un altro verdetto su
**30 celle**: 7 righe sparirebbero (Milan ×2 e Inter «imbattuta da 5» con una sconfitta di
Champions in mezzo), 4 comparirebbero (Real Betis ×2 e Leverkusen «imbattuta da 5»), 11
cambierebbero numero (Roma 5→6, Liverpool 5→6, NEC Nijmegen 5→6…).

**La correzione: dichiarare, non cambiare.** Le righe ora dicono «**in campionato**» (53 righe
sui quattro tipi di striscia) e la nota distingue i due perimetri («campionato» per le strisce,
«contano anche le coppe» per riposo e congestione). Non si è passati alle coppe dentro le
strisce: le coppe hanno formati e avversari non confrontabili fra le 7 leghe (e alcune squadre
non ne giocano), mentre il campionato è la base già usata da «Forma» — cambiarla avrebbe toccato
30 celle senza un criterio migliore. È la stessa scelta di `docs/60` §5 per «forza avv.»:
un'anomalia dichiarata vale più di un numero nuovo non migliore.

**Invarianti e test.** L'audit conta le celle in cui il verdetto cambierebbe
(`perimetro_coppe_verdetto`: 30, informativo) e verifica che la nota dichiari i due perimetri;
l'oracolo [21] accende il gate se la nota perde la parola «campionato».

## §3 — «Panchina nuova» senza scadenza (difetto latente)

**La misura.** La riga scattava con il solo `prev_name` presente nella storia delle distinte,
senza guardare da quante gare l'allenatore fosse in carica: la stessa informazione, nella stessa
pagina, la «Da sapere» la pubblica con la soglia **≤3 gare** (`news_sapere`) e la card
«Panchina» stampa il conteggio esatto. Sull'archivio di oggi **nessuna cella** è interessata
(la permanenza consecutiva massima fra le 12 celle con la riga è 3): è un difetto **latente**,
come quello di `docs/78` §15 — con l'archivio che si allunga un allenatore subentrato a
settembre avrebbe tenuto accesa la parola «shock» per mesi.

*Nota di metodo.* La prima misura dell'audit segnalava 1 cella (Estrela da Amadora, «7ª gara dal
subentro»): era un difetto **dell'audit**, che contava tutte le righe con quell'id allenatore
invece della sequenza consecutiva. Corretto l'audit, il numero vero è 0 — e il conteggio
consecutivo è ora la regola sia nell'audit sia nell'oracolo.

**La correzione.** `MOOD_COACH_NEW = 3` nella condizione della riga: lo stesso criterio della
voce in «Da sapere», dichiarato nella nota.

**Invarianti e test.** Test `test_clima_panchina_nuova_solo_se_recente` (subentro da 4 gare →
nessuna riga; da 2 → riga pubblicata); l'audit verifica la distribuzione delle gare dal
subentro (max 3 · oltre 3: 0/12) e l'oracolo [21] ricalcola la permanenza consecutiva.

## §4 — I toni non erano spiegati

**La misura.** Le 228 righe escono con un bordo colorato (`mood-bad` rosso, `mood-warn` ambra,
`mood-good` verde, `site.css` 332-334) e **nessuna delle 77 pagine** lo spiegava: il colore è
un'informazione che il lettore non poteva decodificare senza indovinare.

**La correzione.** La nota si apre con la legenda: «il bordo colorato dà la lettura: rosso =
allarme, ambra = attenzione, verde = fiducia».

**Invarianti e test.** L'audit (`tono_non_dichiarato` 77 → **0**) e l'oracolo [21] pretendono
le tre parole nella nota di ogni scheda pre-partita.

## §5 — L'oracolo [21]: da specchio a indipendente

**Il debito.** Fino a ieri [21] chiamava `ma19.club_mood` e cercava le righe restituite nel
testo: uno **specchio** (`docs/79` §1), che non poteva vedere gli errori dentro la funzione —
e il registro `ORACOLI` lo dichiarava perfino «M» con la nota sbagliata («righe del clima dal
Parquet delle notizie»).

**La riscrittura.** [21] ora è un **oracolo indipendente**: ricalcola dai Parquet strisce (su
tutta la stagione di campionato), verdetto xPTS (Understat, o Poisson scritto lì dalla
definizione sui soli xG FotMob dove Understat non copre), panchina nuova (permanenza
consecutiva ≤3), infermeria (presenza e numero; il contributo ricalcolato solo dove il
generatore pubblica il valore grezzo, sopra i 90′) e riposo/congestione (campionato ∪ coppe);
verifica che la nota dichiari perimetro e toni, e le **due direzioni**: nessuna riga inventata e
nessuna riga attesa mancante. Le soglie sono scritte nell'oracolo come la nota le dichiara al
lettore: se il generatore cambia una soglia senza aggiornare l'oracolo (o viceversa), il gate si
accende. Registro aggiornato: **30 indipendenti · 18 misti · 4 specchi** (erano 29/19/4 con un
misto mal etichettato).

**Cosa ha già trovato.** All'innesto l'oracolo ha bocciato una cella su Estrela da Amadora —
e aveva ragione lui: era lo stesso errore di conteggio (totale invece che consecutivo) che
l'audit aveva corretto mezz'ora prima. Un oracolo indipendente serve esattamente a questo.

## §6 — Misure e gate

`scripts/audit_clima.py` (dopo `fda build`):

| grandezza | prima | dopo |
|---|---|---|
| celle con il contatore di striscia sbagliato (`troppo_corta`) | **14** | **0** |
| celle dove le coppe cambierebbero il verdetto | 30 | 30 (dichiarato nelle righe e nella nota) |
| celle con «panchina nuova» oltre 3 gare dal subentro | 0 (latente) | 0 (guardia attiva) |
| pagine senza legenda dei toni | **77** | **0** |
| note non allineate alle soglie del codice | 0 | 0 |
| righe pubblicate | 228 | 228 (14 numeri corretti) |

Gate (build del 2026-10-11): **`pytest` 623 passed** (+2 test nuovi), **`ruff` pulito**,
**`fda build` 493 partite · 2.364 gare di calendario · 7.578 giocatori** (exit 0),
**`verify_site` 0 problemi · 235.782 controlli** con [21] oracolo indipendente,
**`parita_schede` 77 schede · nessuna differenza**, **`resa_375` 28.466 misure · 0 problemi**,
`audit_clima` 0 difetti strutturali.

**Limite dichiarato dell'audit.** Tre celle (Frosinone, Le Mans, Frankfurt) pubblicano la riga
«infermeria pesante» grazie alla **stima stabilizzata** di un giocatore sotto i 90 minuti
(`docs/19` §1.10): l'audit ricalcola solo i valori che la card pubblica grezzi e quindi le
segnala come ambigue, non come errori — il numero stampato è coerente con la stima e con la
tabella della stessa card.

## §7 — Misurato e **non** cambiato (regola B.10)

- **Soglia del riposo corto.** La card dichiara ≤3 giorni, mentre la ricerca indicata nel
  codice (PubMed, RR 1,32 per ≤4 vs ≥6) considerebbe corta anche la fascia dei 4 giorni.
  Oggi la distribuzione del riposo sulle 154 celle è tutta ≥6 giorni (sosta del campionato):
  spostare la soglia a 4 sarebbe una modifica **non misurabile** oggi e con il rischio di
  accendere la riga in ogni settimana europea. Scelta: soglia invariata e docstring allineato
  al comportamento reale (non più «allineata a ≤4»), punto riapribile quando i dati mostrano
  una settimana densa.
- **Precedenza «non vince da» su «imbattuta da».** Una squadra imbattuta ma senza vittorie
  (tutti pareggi) riceve la riga warn, non quella verde. Misura: oggi **19 righe su 19** hanno
  composizione mista (N e P) e nessuna è «tutti pareggi», quindi il caso non è osservabile; la
  riga resta com'è (dichiara la composizione «(N N, M P)», quindi non nasconde nulla).
- **Lunghezza delle righe.** Non sono state accorciate: le 53 righe di striscia crescono di
  «in campionato» (12 caratteri) e la nota di una riga di legenda; il testo visibile mediano
  delle schede resta invariato al 100% della parità (`parita_schede`).

## §8 — Prossimo passo

La coda di revisione sezione per sezione (`docs/55` §7, `docs/STATO.md`) resta: **Mercato**,
**Vita del club**, **Previsione del modello ensemble**, **Verifica approfondita**, **Confronto
di stagione** — oltre ai residui dichiarati in `docs/64` §6 (id di fase NED1, Cagliari,
collisione 58/58). Il lavoro va sul branch `arena/9912b625-football-deep-analyzer` con la
solita PR unica di sessione: merge all'utente.
