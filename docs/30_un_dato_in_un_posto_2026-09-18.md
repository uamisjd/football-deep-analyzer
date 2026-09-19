# 30 — P1.2 applicata: un dato di stagione, un posto (18/09/2026)

> Secondo intervento della coda misurata in `docs/28` §4, dopo **P1.1** (`docs/29`).
> Sessione `arena/01a0b61a` · branch `arena/01a0b61a-football-deep-analyzer`.

---

## 1. Il difetto, misurato (`docs/28` §2 P1.2)

Il valore di stagione della card squadra (xG creati/concessi per gara, PPDA) ricompariva in
**mediana 3 altri riquadri** della stessa scheda: la riga dell'hero (*«X crea 1,45 xG/gara
(Understat) · Y 1,20 · PPDA 11,5 vs 12,1»*), la tabella di «Scontro tattico» e la riga di sintesi di
«Come arrivano» (*«12 gare: 1,45 xG e 1,20 xGA a partita · 18 punti fatti contro 16,3 attesi»*).
Sulle 154 misure iniziali la distribuzione era 3 riquadri in 97 casi, 4 in 48, 5 in 7, 6 in 2.
Con due fornitori xG diversi nella stessa pagina (4 schede) il rischio concreto è che il lettore non
sappia quale cifra è quella «vera».

## 2. Che cosa è cambiato

1. **Hero** (`match.html`): via la riga con xG/gara e PPDA. Restano esito, λ (con il tooltip che
   spiega perché non è la media xG), Over 2,5 e «entrambe a segno», che non compaiono altrove.
2. **«Come arrivano»**: via la riga di sintesi (le medie e i punti contro xPTS sono già nella card
   della squadra) e via il PPDA (che sta nella card della squadra e in «Scontro tattico»). Resta la
   **serie gara per gara** con la tendenza e lo split casa/trasferta, che è l'unica cosa che questa
   card può dire bene; al posto dei numeri tolti, un rimando: *«Le medie di stagione sono nella card
   della squadra, il confronto degli stili in → Scontro tattico»*.
3. **Nessun dato esce dalla pagina**: i valori restano nella card della squadra (stagione, per
   squadra) e in «Scontro tattico» (confronto di stile della gara), che è la divisione dei ruoli
   scritta in `docs/28` §2.
4. **`scripts/prematch_sections.py`**: la misura «stesso dato in più card» è rifatta sui valori
   *canonici* — quelli della card squadra — contati in quanti **altri** riquadri compaiono, hero
   incluso (così il prima/dopo si misura con la stessa definizione, anche ora che l'hero non li
   stampa più).

## 3. Misura prima/dopo

Due build dello stesso codice (le due versioni del template), stessi dati, sulle stesse 66 schede
pre-partita: la versione «prima» è il commit `c581a81` renderizzato di nuovo in `/tmp/out_prima_p12`
(gli altri riquadri, P1.1 compresa, sono identici nelle due build).

| grandezza (66 schede pre-partita) | prima | dopo |
|---|---|---|
| dato di stagione ripetuto in altri riquadri (mediana) | **3** | **1** |
| occorrenze di ripetizione totali | 1.039 | 489 (**−53%**) |
| schede con la riga xG/PPDA nell'hero | 66/66 | **0** |
| schede con la riga di sintesi in «Come arrivano» | 66/66 | **0** |
| schede con il PPDA in «Come arrivano» | 48/66 | **0** |
| card «Come arrivano» — testo visibile (mediana) | 1.150 car. | 865 car. (**−285**) |
| hero `#sintesi` — testo visibile (mediana) | 489 car. | 415 car. (**−74**) |
| **scheda intera — testo visibile (mediana, per scheda)** | — | **−357 car.** (188–376; 66/66 schede) |
| «Understat» citato per scheda (mediana) | 8 | 7 |

**Perché due numeri diversi per la scheda.** Il calo per scheda è **bimodale**: −119 caratteri dove
una sola squadra aveva la riga di sintesi, −286 dove l'avevano entrambe. Lo strumento stampa la
mediana dei *totali* delle card-foglia (20.723 → 20.577), che in una distribuzione bimodale si muove
meno del calo vero (la pagina mediana cambia gruppo) e non contiene la riga dell'hero, che non è una
card. La cifra onesta è quella **appaiata** scheda per scheda: −357 caratteri visibili in mediana,
tutte e 66 le schede. Entrambi i numeri sono rifacibili con
`.venv/bin/python -m scripts.prematch_sections` (sul build prima e su quello dopo).

## 4. Gate

`pytest -q` **438 passed** (+1: `test_xg_e_ppda_una_volta_sola`, che costruisce una gara con dati
Understat e verifica che l'hero non stampi né xG/gara né PPDA, che i valori di stagione restino nella
card della squadra e in «Scontro tattico», che «Come arrivano» non ripeta la sintesi e che il
rimando ci sia) · `ruff` pulito · `fda build` exit 0 (375 partite / 2.364 fixtures / 7.480
giocatori) · `scripts/verify_site.py` **exit 0 — 0 problemi · 97.903 controlli** ·
`scripts/audit_match_sections.py` exit 0.

**Non verificato:** la resa visiva con un browser reale (spaziatura dove la riga è sparita, resa
della card «Come arrivano» più corta) — resta il punto aperto P2.8 di `docs/19`, come per P1.1.

## 5. Anteprima per il lettore

Per questo turno è stata preparata un'anteprima **prima/dopo** servita localmente
(`site_preview/`, fuori dal versionamento): i riquadri sono i frammenti veri delle due build, non
ricostruzioni. Il generatore è rimasto fuori dal repo perché usa due worktree temporanei
(`git worktree add <dir> 1669413` e `c581a81`, poi `SiteBuilder(out_dir=…).build_match_pages(ids)`)
e serve solo a mostrare il confronto.

## 6. Prossimo passo

`docs/28` §4: **P1.4** («Verifica approfondita» chiusa di default, con il metodo in testa) e poi
**P1.3** (la navigazione promette 4 sezioni, la pagina ne ha 21).
