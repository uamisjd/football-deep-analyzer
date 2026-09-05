# Regole di lavoro del progetto

Queste regole valgono per tutta la durata del progetto. Sono nate dopo un blocco della chat (6 settembre 2026) causato da un turno troppo pesante: troppe pagine di dati grezzi caricate in conversazione, nessun salvataggio intermedio. **Il lavoro di quel turno è andato perso.**

## A. Regole anti-blocco (per l'agente)

1. **Prima si salva, poi si parla.** Ogni risultato utile (decisione, verifica, codice) viene scritto su file nel repository e committato **subito**, prima di proseguire. Niente vive solo nella chat.
2. **Un turno = un obiettivo piccolo e concluso.** Mai "faccio tutta la fase in un colpo". Ogni turno termina con: cosa è stato fatto, cosa manca, qual è il prossimo passo (3–5 righe).
3. **Zero dati grezzi in chat.** Le risposte delle API/pagine non si leggono mai per intero in conversazione: si scaricano con uno script che salva su disco e stampa solo un riepilogo (`head`, conteggi, chiavi). Se serve una verifica al volo: **una sola pagina, un solo frammento**, mai in parallelo.
4. **Output dei comandi limitato.** Ogni comando stampa al massimo ~30 righe (`| head -30`, `| cut -c1-200`). Log e test lunghi vanno su file.
5. **Checkpoint obbligatorio.** Il file `docs/STATO.md` viene aggiornato a **ogni turno** con: fatto / in corso / prossimo passo / decisioni aperte. Se la chat si blocca, si riparte da lì senza dover ripetere nulla.
6. **Risposte brevi.** Spiegazioni lunghe → in un file `docs/`; in chat solo il riassunto e il link.
7. **Niente lavori pesanti nella chat.** Backfill di stagioni, scaricamento di centinaia di partite, backtest: si eseguono in GitHub Actions o con uno script lanciato in background, e in chat si guarda solo il log finale.
8. **Commit piccoli e frequenti** con messaggio chiaro, sul branch di lavoro.
9. **Avviso esplicito per la PR.** L'agente lavora sul branch `arena/...`; il ramo `main` riceve il lavoro solo tramite pull request. È compito dell'agente **dire chiaramente quando è il momento giusto di fare "Create PR"** (frase fissa: *"👉 È il momento di fare Create PR"*) e perché. Regola: la PR serve quando su `main` deve "girare" qualcosa (workflow GitHub Actions con cron, GitHub Pages) o quando un blocco di lavoro è concluso e funzionante; non serve per i passi intermedi (il lavoro è già al sicuro con i push sul branch).

## B. Cosa fare se la chat si blocca (per te)

1. Non riscrivere il messaggio lungo: scrivi solo **"continua"** (o "continua dal punto X").
2. L'agente rilegge `docs/STATO.md` e riparte dall'ultimo checkpoint.
3. Se sospetti che qualcosa sia andato perso, chiedi: *"cosa risulta salvato nel repo?"* — la verità è sempre nel repository, non nella chat.
4. Evita di allegare file grandi in chat; meglio metterli nel repository.

## C. Regole di progetto (dalle tue decisioni)

- **Costo zero**: nessuna API o servizio a pagamento, nemmeno "prova gratuita con carta".
- **Fonti**: solo quelle raggiungibili da GitHub Actions (niente scraper che richiedono il tuo PC), finché non decidi diversamente.
- **Perimetro iniziale**: 7 campionati (vedi `03_decisioni_e_funzionamento.md`).
- **Uso personale** fino al completamento: sito non pubblicizzato, nessuna ripubblicazione massiva di dati grezzi di terzi, attribuzione delle fonti.
- **Sezione quote/valore**: sì, con disclaimer (informazione statistica, non consiglio; 18+).
- **Lingua**: interfaccia, report e documenti in italiano; codice, nomi di file e dati in inglese.
- **Riuso prima di scrivere**: librerie esistenti (penaltyblog, soccerdata, mplsoccer) prima di codice proprio.
- **Onestà sui numeri**: ogni previsione viene registrata e valutata pubblicamente (RPS/Brier); niente "accuratezza" dichiarata senza misura.
- **Rispetto delle fonti**: limiti di richieste per fonte, cache, nessun aggiramento di CAPTCHA o protezioni.
