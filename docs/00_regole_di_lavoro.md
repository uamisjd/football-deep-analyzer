# Regole di lavoro del progetto

Queste regole valgono per tutta la durata del progetto. Sono nate dopo un blocco della chat (6 settembre 2026) causato da un turno troppo pesante: troppe pagine di dati grezzi caricate in conversazione, nessun salvataggio intermedio. **Il lavoro di quel turno è andato perso.**

Hanno lo scopo di (1) non perdere mai lavoro, (2) lavorare con la massima accuratezza e qualità, (3) rendere ogni sessione/agente nuovo immediatamente operativo. Un agente nuovo deve leggere **prima** `BRIEFING_NUOVA_SESSIONE.md`, poi questi file in ordine: `00` (regole) → `STATO.md` (checkpoint) → `01`/`02`/`03` (contesto) quando serve.

## A. Regole anti-blocco (per l'agente)

1. **Prima si salva, poi si parla.** Ogni risultato utile (decisione, verifica, codice) viene scritto su file nel repository e committato **subito**, prima di proseguire. Niente vive solo nella chat.
2. **Un turno = un obiettivo piccolo e concluso.** Mai "faccio tutta la fase in un colpo". Ogni turno termina con: cosa è stato fatto, cosa manca, qual è il prossimo passo (3–5 righe).
3. **Zero dati grezzi in chat.** Le risposte delle API/pagine non si leggono mai per intero in conversazione: si scaricano con uno script che salva su disco e stampa solo un riepilogo (`head`, conteggi, chiavi). Se serve una verifica al volo: **una sola pagina, un solo frammento**, mai in parallelo.
4. **Output dei comandi limitato.** Ogni comando stampa al massimo ~30 righe (`| head -30`, `| cut -c1-200`). Log e test lunghi vanno su file.
5. **Checkpoint obbligatorio.** Il file `docs/STATO.md` viene aggiornato a **ogni turno** con: fatto / in corso / prossimo passo / decisioni aperte. Se la chat si blocca, si riparte da lì senza dover ripetere nulla.
6. **Risposte brevi.** Spiegazioni lunghe → in un file `docs/`; in chat solo il riassunto e il link.
7. **Niente lavori pesanti nella chat.** Backfill di stagioni, scaricamento di centinaia di partite, backtest: si eseguono in GitHub Actions o con uno script lanciato in background, e in chat si guarda solo il log finale.
8. **Commit piccoli e frequenti** con messaggio chiaro, sul branch di lavoro.
9. **PR e merge: dirlo sempre in modo esplicito** (vedi sezione **D** sotto — *quando è il momento di fare PR / merge*). L'agente lavora sul branch `arena/...`; `main` riceve il lavoro solo tramite pull request.

## B. Paletti di qualità (nuovi — valgono sempre, su ogni deliverable)

L'obiettivo del progetto è **analisi molto accurata, precisa e profonda**; il lavoro (codice, analisi, documenti, comunicazione) deve riflettere gli stessi standard. Regole concrete:

1. **Accuratezza dei numeri = ogni numero mostrato è verificabile e misurato.** Nessuna previsione/statistica dichiarata senza registrazione e valutazione pubblica (RPS/Brier — vedi regola C "Onestà sui numeri"). Prima di affermare che un modello/fonte "funziona", mostrare la misura su dati reali o su test offline con fixtures; mai impressioni.
2. **Precisione del linguaggio = distinguere sempre** cosa è *verificato dal vivo*, cosa è *verificato solo offline su fixtures/campioni*, cosa è *presunto/congettura*. In STATO.md e nelle chat ogni affermazione ricade in una di queste tre classi; se non è chiaro, si dice "da verificare".
3. **Profondità = non fermarsi alla superficie.** Prima di concludere "non si può fare", verificare: fonti alternative/ridondanti (FotMob → ESPN → Understat → mirror), fallback, librerie riusabili, e documentare perché una strada è chiusa (con prova, non supposizione).
4. **Qualità del codice**: suite di test verde prima di proporre PR; `ruff` senza errori sul codice nuovo; funzioni piccole e con nomi chiari; niente codice duplicato o incollato da altrove senza capirlo; dati tipizzati (UTC stabili); log leggibili.
5. **Qualità dei documenti**: lingua italiana corretta, sezioni brevi e per titolo, link agli altri doc, niente dati grezzi incollati, ogni file `docs/` si chiude con "prossimo passo".
6. **Le verifiche di rete vanno dove la rete arriva.** Dal sandbox dell'agente alcune fonti sono irraggiungibili (si raggiungono `github.com` e `api.github.com`): le verifiche "dal vivo" su FotMob/Understat/mirror vanno fatte in **GitHub Actions** o sul PC dell'utente, mai dichiarate come fatte dal sandbox.
7. **Se un'azione non è compiuta in-turno, si dice esplicitamente** "non verificato / in attesa", mai "fatto".
8. **Prima si dimostra, poi si integra.** Feature/modello nuovi entrano solo con: prova di miglioramento (o di parità sensata), test che li coprono, e aggiornamento di STATO.md. Niente "miglioramenti" non misurati.
9. **Tutto ciò che una sessione/agente nuovo deve sapere è scritto nei `docs/`**, non solo in una chat precedente che l'agente non vede (vedi `BRIEFING_NUOVA_SESSIONE.md`).

## C. Cosa fare se la chat si blocca (per te)

1. Non riscrivere il messaggio lungo: scrivi solo **"continua"** (o "continua dal punto X").
2. L'agente rilegge `docs/STATO.md` e riparte dall'ultimo checkpoint.
3. Se sospetti che qualcosa sia andato perso, chiedi: *"cosa risulta salvato nel repo?"* — la verità è sempre nel repository, non nella chat.
4. Evita di allegare file grandi in chat; meglio metterli nel repository.

## D. Quando fare "Create PR" e quando fare "Merge" (policy esplicita)

L'agente lavora sul branch `arena/...` e il lavoro è già al sicuro grazie ai push sul branch: **non serve una PR per ogni passo intermedio**. Serve quando su `main` deve esserci qualcosa di nuovo. L'agente **deve dirlo da solo**, in modo esplicito e nel momento giusto, senza aspettare che glielo chiedano.

**È il momento di fare "Create PR" quando** ricorre **una o più** di queste condizioni:
1. Un **blocco di lavoro è concluso, testato e funzionante** e deve entrare in `main` per chiudere il passo (fase/roadmap completata).
2. Su `main` deve **"girare" qualcosa**: workflow GitHub Actions (cron `daily`, `tests`), GitHub Pages, bot/automazione → prima che `main` ne disponga non esegue nulla.
3. Il lavoro serve alle **sessioni successive**: aggiornamenti alle regole, al briefing o a STATO sono inutili se restano solo sul branch — le nuove sessioni partono da `main`. (Questo è il caso dei presenti doc di lavoro.)

**Prima di proporre la PR, checklist obbligatoria:**
- [ ] suite di test verde (localmente e, se possibile, sul branch via workflow `tests`);
- [ ] nessun dato/file spurio o grande committato;
- [ ] `docs/STATO.md` aggiornato con quanto fa questa PR;
- [ ] messaggio PR chiaro che riassume cosa fa e il motivo;
- [ ] la PR parte dal branch di lavoro corretto (`arena/...`) verso `main`.

**Dopo la PR aperta**: l'agente monitora i check (tests). Quando sono verdi e la PR è mergeable, l'agente **lo comunica e indica il momento del merge** con la frase fissa:
> *"👉 Tutto verde: è il momento di fare Merge (PR #N)."*

E spiega in una riga perché è sicuro. L'agente può eseguire il merge quando ha l'autorizzazione/frutto dell'accordo di lavoro (es. è già prassi nel progetto mergiare PR verdi senza ulteriore conferma); altrimenti lo lascia decidere all'utente. Dopo il merge: aggiorna STATO.md con il commit di merge e indica il prossimo passo.

## E. Regole di progetto (dalle tue decisioni)

- **Costo zero**: nessuna API o servizio a pagamento, nemmeno "prova gratuita con carta".
- **Fonti**: solo quelle raggiungibili da GitHub Actions (niente scraper che richiedono il tuo PC), finché non decidi diversamente.
- **Perimetro iniziale**: 7 campionati (vedi `03_decisioni_e_funzionamento.md`).
- **Uso personale** fino al completamento: sito non pubblicizzato, nessuna ripubblicazione massiva di dati grezzi di terzi, attribuzione delle fonti.
- **Sezione quote/valore**: sì, con disclaimer (informazione statistica, non consiglio; 18+).
- **Lingua**: interfaccia, report e documenti in italiano; codice, nomi di file e dati in inglese.
- **Riuso prima di scrivere**: librerie esistenti (penaltyblog, soccerdata, mplsoccer) prima di codice proprio.
- **Onestà sui numeri**: ogni previsione viene registrata e valutata pubblicamente (RPS/Brier); niente "accuratezza" dichiarata senza misura.
- **Rispetto delle fonti**: limiti di richieste per fonte, cache, nessun aggiramento di CAPTCHA o protezioni.
