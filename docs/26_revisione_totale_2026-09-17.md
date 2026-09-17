# Revisione totale del 17/09/2026 — cosa funziona, cosa era rotto, cosa è in ordine

**Richiesta dell'utente:** «mi fai una revisione del progetto? verifica che funzioni tutto in modo
accurato, scopri malfunzionamenti o bug, trova e ordina cose fuori posto, fai un lavoro di ordine e
miglioramenti».

**Risposta breve.** Il progetto è sano nelle parti che erano già misurate (suite verde, build senza
errori, gate `verify_site` a zero problemi, sito strutturalmente pulito, numeri pubblicati che
tornano ricalcolandoli da zero). La revisione ha trovato **un difetto funzionale vero** — la potatura
dell'archivio notizie era **documentata e promessa dalla docstring ma non implementata**, e
`news.parquet` cresceva senza limite verso il tetto GitHub di 100 MB per file — più **tre difetti di
confezionamento/ordine** (CSS assente dalla wheel, script di anteprima che sovrascriveva il sito
pubblicato, database derivato versionato in Git) e **un difetto della suite di test** che copriva un
ramo di raccolta con un `AttributeError` inghiottito. Tutti corretti, con test che falliscono senza
il fix. In coda restano tre decisioni che sono dell'utente, non dell'agente (§8).

---

## 1. Metodo

Prima verificare, poi cercare. Ogni numero qui sotto è stato misurato in questa sessione con un
comando, non ripreso dai documenti dei giri precedenti.

1. Ambiente ricostruito da zero (`.venv`, `pip install -e ".[dev]"`), suite completa, `ruff`,
   `fda build`, `scripts/verify_site.py`, `fda lab --history` (offline), CLI (`version`, `leagues`,
   `db`).
2. Audit **indipendente** del sito generato (4.126 pagine): link, sitemap, struttura HTML,
   residui `nan`/`NaT`/`None`/`UTC`, entità doppie, canonical, token CSS. Controlli scritti ex novo,
   non riusando `verify_site`: la lezione di `docs/25` §2 è che un verificatore che richiama la
   funzione sotto esame ricertifica invece di verificare.
3. Ricalcolo da zero dei numeri pubblicati più sensibili (RPS/Brier di *Accuratezza*, coerenza delle
   classifiche, somme delle probabilità di stagione).
4. Lettura del codice dei moduli non coperti o poco coperti (misurata con `coverage`: totale **85%**,
   `cli.py` 18%, `season_sim.py` 58%).
5. Costruzione della **wheel** per vedere il pacchetto come lo vede chi non sviluppa in editable.

## 2. Difetto 1 (funzionale): la potatura delle notizie era promessa e non esisteva

**Cosa diceva il codice.** `collect_news()` in `src/fda/collect.py`:

> «Le righe vecchie oltre ``window_days`` vengono potate: la card legge 7 giorni, il resto è peso
> morto nel Parquet.»

**Cosa faceva.** `window_days` costruiva solo `cut = now - timedelta(days=window_days)` e filtrava le
righe **in arrivo**. Le righe già archiviate non venivano mai toccate: la tabella `news` è
append-only.

**Prova.** Store sintetico con 4 righe (90 giorni, 31 giorni, 5 giorni, senza data), `collect_news`
con client finti e `window_days=30`: dopo la chiamata le righe erano ancora **4**, compresa quella di
90 giorni.

**Perché è un problema serio e non estetico.** `data/processed/` è versionato e committato a ogni run
(5 al giorno). Misurato sui dati del repository:

| Misura | Valore |
|---|---|
| `news.parquet` oggi | **18.705 righe · 4,89 MB · 262 byte/riga** |
| Ritmo recente (media ultimi 7 giorni) | **1.562 righe/giorno = 0,41 MB/giorno** |
| Giorni per arrivare a **100 MB** | **~233** (≈ metà aprile 2027) |
| Limite GitHub per singolo file | **100 MB, oltre il push è rifiutato** ([1](https://fixdevs.com/blog/git-file-too-large-to-push/), [2](https://techearl.com/git-file-too-large-error)) |

Cioè: fra ~8 mesi il commit dei dati del run giornaliero avrebbe cominciato a **fallire**, e con lui
la pubblicazione su Pages — non per un guasto delle fonti ma per un file che nessuno potava.

**Correzione.** Dopo l'`upsert`, l'archivio viene riletto e le righe con `published_at` più vecchio
di `cut` vengono rimosse (`store.write`); una riga **senza data non si butta** (non si elimina un dato
solo perché non se ne conosce l'età); il conteggio finisce nell'imbuto dichiarato di *Stato fonti*
(`… salvate N · potate M`), quindi la potatura è visibile e non silenziosa. Nessuna riscrittura se non
c'è nulla da potare (test dedicato: i byte del Parquet restano identici, niente diff Git inutile).

**Effetto misurato.** Oggi le righe oltre i 30 giorni sono **24**: l'intervento non svuota nulla,
**mette un tetto**. A regime con 30 giorni di ritenzione il file si stabilizza intorno a
**46.900 righe ≈ 12,3 MB** invece di crescere per sempre. Il costo residuo sulla history Git è
dichiarato in §8.

**Test.** `tests/test_diagnostica_fonti.py`: `test_collect_news_pota_l_archivio_oltre_la_finestra`
(tre casi: oltre la finestra / in finestra / senza data + contatore nell'imbuto) e
`test_collect_news_non_pota_se_non_ce_nulla_di_vecchio`. Verificato che **falliscono** senza il fix
(`AssertionError: 'Vecchia'` resta in archivio) e passano con il fix.

## 3. Difetto 2 (confezionamento): la CSS del sito non entrava nella wheel

`pyproject.toml` dichiarava solo i template:

```toml
"fda.site" = ["templates/*.html"]
```

ma `build.py` legge a runtime **due** risorse dal pacchetto: i template
(`FileSystemLoader(Path(__file__).parent / "templates")`) e la CSS
(`Path(__file__).parent / "assets" / "site.css"` in `_write_assets`).

**Misura.** Wheel costruita con `python -m build --wheel`: **nessun file `.css`**; installata in un
ambiente pulito, `_write_assets()` non può funzionare. Con `pip install -e` (ciò che usano README e
CI) il difetto non si vede, perché l'editable punta al checkout.

**Correzione.** `"fda.site" = ["templates/*.html", "assets/*.css"]`. Wheel ricostruita:
`fda/site/assets/site.css` presente. **Test** `tests/test_pacchetto.py`: oltre al caso specifico,
un'invariante generica — *ogni* file non-`.py` dentro `src/fda/` deve essere coperto da un glob di
`package-data`, così il prossimo file di dati aggiunto non può ripetere l'errore.

## 4. Difetto 3 (ordine): l'anteprima sovrascriveva il sito pubblicato

`scripts/anteprima_scheda.py` rigenerava il sito in `SITE_DIR`, cioè **`site/`**: la directory che
`fda build` produce e che il workflow `daily` carica su GitHub Pages. Lo script la svuota e la
riscrive (il builder fa `rmtree` dell'output).

**Caso reale, capitato durante questa revisione.** Un'anteprima interrotta a 120 secondi ha lasciato
`site/` con **135 pagine invece di 4.126**: chi avesse lanciato il deploy in quel momento avrebbe
pubblicato un sito monco. Nessun danno (il `fda build` successivo ha ricostruito tutto: 4.126 pagine,
125 MB), ma il rischio era reale e invisibile.

**Correzione.** L'anteprima scrive in `site_preview/` (`out_dir=PREVIEW_DIR`, directory aggiunta a
`.gitignore`); il nome `SITE_DIR` non compare più nello script. **Test** in `tests/test_pacchetto.py`.

## 5. Difetto 4 (ordine): un database derivato era versionato

`data/processed/fda.duckdb` era tracciato da Git mentre `store.py` lo dichiara:

> «il database DuckDB (data/processed/fda.duckdb) è una vista di comodo ricreata dai Parquet
> (**non è versionato**: si rigenera in pochi secondi)»

Il `.gitignore` diceva il contrario («Dati elaborati: versionati (data/processed, data/*.duckdb)») e
il `daily` faceva `git add data/processed`: un binario riscritto a ogni run finiva in history senza
aggiungere informazione, con rischio di conflitto binario nel rebase del push.

**Verifica prima di toglierlo.** Con il file cancellato, `Store` lo ricrea e `refresh_views()`
restituisce **26 viste**; `fda db` funziona. Quindi: `git rm --cached`, regola in `.gitignore`,
commento corretto, e `docs/03` annotato (il percorso scritto lì, `data/fda.duckdb`, era peraltro
sbagliato). **Test** `test_il_database_derivate_non_e_versionato` (regola in `.gitignore` + `git
ls-files` vuoto).

## 6. Difetto 5 (suite di test): un ramo di raccolta non era mai esercitato

`collect_news` scarica anche i **feed RSS diretti** della stampa italiana (ANSA, Sky Sport,
Sportmediaset) chiamando `nc.direct_feed_raw(url)`. Il client finto di
`tests/test_diagnostica_fonti.py` non aveva quel metodo: a ogni test il collettore sollevava
`AttributeError` su ciascuno dei tre feed e `_safe` lo **catturava**, quindi la suite restava verde
mentre:

- il ramo dei feed diretti non veniva eseguito da nessun test;
- tre errori finti finivano negli errori del report, rumore che avrebbe nascosto un errore vero.

**Correzione.** `direct_feed_raw` aggiunto al fake (passa da `http.get_bytes`, quindi conta le
richieste come in produzione); l'asserzione sul contatore passa da `{"news": 2}` a **`{"news": 5}`**
(2 ricerche Google + 3 feed diretti: è il valore corretto, prima ne mancavano tre) e c'è un assert
esplicito che non restino errori `news direct …`.

## 7. Ordine e coerenza (cose fuori posto, corrette)

| Dove | Cosa non tornava | Intervento |
|---|---|---|
| `README.md` | «`fda daily` = collect → predict → simulate → build»: la catena vera ha 7 passi | descrizione allineata al codice (`collect → calibrate → predict → backtest → mercati-monitor → simulate → build`, con la regola «ogni passo è isolato») |
| `src/fda/cli.py` | docstring di `daily_cmd`: «collect → predict → build» | catena reale, e cosa fa `--skip-predict` |
| `docs/BRIEFING_NUOVA_SESSIONE.md` §6 | l'«indice completo» dei documenti si fermava a `docs/23`: mancavano `docs/24` e `docs/25`, e i conteggi (27 file, 347 test) erano vecchi | indice aggiornato a **30 file**, conteggi veri (test **377** in **35** file, **26** Parquet senza più `fda.duckdb`) |
| `.github/workflows/benchmark.yml` | `checkout@v4`, `setup-python@v5`, `upload-artifact@v4` mentre gli altri workflow sono a v7; `pip install -e .[dev]` non quotato (glob per la shell); nessuna retention | allineato a v7, `".[dev]"` quotato, `retention-days`/`if-no-files-found`, `timeout-minutes` |
| `.gitignore` | mancavano `.coverage`/`htmlcov/` (artefatti di misura) e `site_preview/` | aggiunti |
| `docs/03` | percorso del DuckDB sbagliato e dichiarato versionato | annotazione datata, senza riscrivere il documento storico |

**Non toccato di proposito:** `diag/trigger.txt` resta dov'è (è l'interruttore documentato del
workflow `diag`); la numerazione di `docs/` resta con il buco del **09**, che non è mai esistito —
rinumerare i documenti romperebbe centinaia di riferimenti incrociati.

## 8. Aperto: tre decisioni che spettano all'utente

1. **Costo residuo di `news.parquet` sulla history Git.** Con la potatura il file ha un tetto
   (~12,3 MB), ma resta committato 5 volte al giorno: a regime sono **~61 MB/giorno di history**
   (~22 GB/anno). Tre strade: (a) ritenzione più corta — la card legge 7 giorni e `verify_site` 12,
   quindi 14 giorni basterebbero e il tetto scenderebbe a ~5,5 MB; (b) non versionare `news.parquet`
   (è l'unica tabella interamente ricostruibile dalla fonte entro la finestra) e lasciarlo al solo
   runner; (c) accettare il costo. **Non deciso di iniziativa**: cambia la politica dei dati, che è
   una scelta dell'utente (`docs/03`).
2. **Font di Google su ogni pagina.** `base.html` carica `Sora` e `Inter` da
   `fonts.googleapis.com` (misurato: **8.252 link** sulle 4.126 pagine, due per pagina). È l'unica
   dipendenza esterna a runtime di un sito che per regola non usa servizi di terzi: implica una
   richiesta a Google a ogni visita e una resa diversa offline. Alternative: font auto-ospitati
   (file nel pacchetto, +~300 kB una tantum) o stack di sistema. Tocco estetico: va deciso.
3. **Crescita di `source_status`.** Non limitata, ma **misurata e trascurabile**: 2.376 righe /
   17 kB in 12 giorni (~198 righe/giorno, ~0,5 MB/anno). Nessun intervento, annotato per non
   ri-misurarlo.

## 9. Verifiche

| Verifica | Prima | Dopo |
|---|---|---|
| Suite (`pytest -q`) | 371 passed | **377 passed** (+2 potatura, +4 pacchetto) |
| `fda build` | exit 0 | exit **0** — 375 schede · 2.364 partite · 7.470 giocatori · calendario 1.988 partite (0 senza previsione) |
| `verify_site` (gate CI) | 0 problemi · 94.008 controlli | **0 problemi · 94.008 controlli** (invariato: nessun contenuto pubblicato è cambiato) |
| `ruff check .` | 173 (baseline) | **173** — una segnalazione nuova introdotta e tolta nello stesso giro (`noqa` inutile nel test nuovo) |
| Wheel (`python -m build`) | senza `site.css` | con **`fda/site/assets/site.css`** |
| `fda lab --history …` (offline) | — | exit **0** su 202 gare per candidato |
| `git status --porcelain` | — | solo i file di questo giro; `fda.duckdb` non più tracciato |

## 10. Cosa è risultato a posto (misurato, per non ri-verificarlo)

- **Numeri pubblicati.** *Accuratezza* pubblica RPS **0,2004**: ricalcolato da zero da
  `predictions.parquet` (96 gare finite) con la convenzione normalizzata Σ(CDFₚ−CDFₒ)²/(r−1) dà
  0,4008/2 = **0,2004**; Brier **0,6095** identico; esito azzeccato 47,92% → **48%** a schermo.
- **Classifiche** (`fotmob_standings`, 7 leghe): `points = 3V+N`, `played = V+N+P`, differenza reti,
  `rank` unico e monotono rispetto ai punti — tutto vero su tutte e 7.
- **Proiezioni** (`season_sim`): `p_title` somma 1 per lega; `p_top4` somma esattamente i posti UCL
  configurati (4/4/3/4/4/**2**/**1** per NED1/POR1); `p_rel` somma 3.
- **Sito generato** (4.126 pagine): **0** link interni rotti, **0** URL di sitemap senza file
  (4.125 URL, `404.html` esclusa di proposito), **0** id duplicati, **0** ancore interne mancanti,
  `lang="it"`/`viewport`/`charset`/un solo `h1`/`title` non vuoto su **tutte** le pagine, canonical
  unici; **0** occorrenze visibili di `nan`, `NaT`, `None`, `inf`, `undefined`, `UTC`, `{{`.
  (Un falso positivo iniziale su `NaT` era dentro gli URL base64 delle immagini.)
- **Entità HTML**: nessun doppio escape (`&amp;#34;` assente); i `&#34;` dei titoli Google News sono
  escape singoli e il browser li rende come virgolette.
- **Filtro lingua** (`is_italian_news`, `docs/25`): sui **103 titoli pubblicati** nelle schede (98
  unici) un controllo indipendente con `langdetect` ne segnala 12 come «non italiano», e sono **tutti
  italiani** (titoli in maiuscolo letti come inglese/portoghese dal rilevatore). Nessun titolo
  straniero pubblicato.
- **CSS**: 49 token definiti, 47 usati, **0 usati e non definiti**; 2 definiti e mai usati
  (`--info`, `--radius-sm`), lasciati perché fanno parte del sistema di design.
- **CLI**: `fda version`, `fda leagues`, `fda db <sql>` funzionano offline sui dati versionati.
