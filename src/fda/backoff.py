"""Sospensione temporanea di una fonte che fallisce sempre allo stesso modo (docs/19 P1.9).

**Il problema misurato (2026-09-16).** `espn.api.espn.com` risponde **403 su tutti i run**
dall'IP dei runner: 20 run registrati su 20 per `espn:ITA1` e 7 richieste su 7 per
`espn:NEWS`. Le fonti primarie (FotMob per la classifica, Google News per le notizie)
coprono il dato, quindi il fallimento è già classificato come *avviso non bloccante*: ma il
costo resta — **14 richieste a run, 70 al giorno** — e la pagina *Stato fonti* ripete 14
righe di avviso identiche, in cui un guasto nuovo non si distingue più.

**La soluzione.** Non un flag in un file di stato (il runner riparte da un clone: lo stato
andrebbe versionato a mano), ma lo **storico già versionato** in ``source_status``: se le
ultime ``BACKOFF_FAILS`` esecuzioni della stessa fase sono tutte fallite, la fonte viene
**sospesa** e non viene interrogata; ogni ``BACKOFF_PROBE_RUNS`` run si fa comunque un
tentativo di **sonda**, così una fonte che torna disponibile rientra da sola entro un giorno.
La decisione è ricostruibile a mano dallo stesso Parquet che l'utente vede in *Stato fonti*.

Limite dichiarato: la chiave è la coppia (fonte, fase) — `("espn:ITA1", "espn standings")` —
quindi la sospensione copre esattamente le richieste il cui errore è quello osservato, non
tutto il client. Lo scoreboard ESPN, che risponde, continua a essere interrogato.
"""

from __future__ import annotations

from typing import Any

from .store import Store

#: Fallimenti consecutivi (stessa fonte e stessa fase) che fanno scattare la sospensione.
BACKOFF_FAILS = 5
#: Run di pausa consecutivi prima di riprovare con una sonda (~1 giorno con 5 run al giorno).
BACKOFF_PROBE_RUNS = 4
#: Marcatore nel testo dell'errore: distingue una riga «sospesa» da un fallimento vero.
SUSPENDED_MARK = "sospeso"


def is_suspended_row(errore: Any) -> bool:
    """True se la riga di ``source_status`` è una pausa programmata, non un tentativo fallito.

    Convenzione: il testo di una pausa è ``"<fase>: sospeso dopo N run falliti consecutivi …"``,
    quindi l'unicità è data dal marcatore dopo i due punti — un errore vero (HTTP 403, timeout)
    non lo contiene mai.
    """
    return isinstance(errore, str) and f": {SUSPENDED_MARK}" in errore


def state(store: Store, source: str, step: str) -> tuple[int, int]:
    """(tentativi falliti consecutivi, pause consecutive) dell'ultima serie di errore.

    Si cammina a ritroso nella storia della coppia (``source``, ``step``) partendo dal run più
    recente e si contano due cose distinte:

    - le **pause** consecutive in testa (righe «sospeso …»: la fonte non è stata interrogata);
    - gli **tentativi falliti** che precedono quelle pause, **saltando le pause delle serie
      precedenti**, fino al primo run riuscito.

    La seconda regola è la correzione del 2026-09-16 (docs/23 §3). Prima una **sonda** che
    falliva veniva contata come il primo fallimento di una serie nuova: dopo ogni sonda la
    fonte ripartiva da ``fails = 1``, servivano altri 4 tentativi prima di risospenderla e il
    costo reale diventava ~5 richieste ogni 9 run invece di 1 ogni 5 — misurato sul run
    `35129006426`, dove `espn:ITA1` aveva **76 fallimenti consecutivi** e una richiesta nel run.
    Con la semantica corretta il ciclo di una fonte rotta è «``BACKOFF_PROBE_RUNS`` pause +
    1 tentativo» = **5 run, una sola richiesta** (una al giorno con 5 run al giorno), e una fonte
    rientrata si riattiva subito, perché una riga riuscita chiude comunque la serie.

    ``step`` è il prefisso dell'errore (es. ``"espn standings"``): una fonte che fallisce su una
    richiesta e non su un'altra non viene sospesa a torto.
    """
    try:
        df = store.read("source_status")
    except Exception:  # noqa: BLE001 — storico illeggibile o assente non deve fermare la raccolta
        return 0, 0
    if df is None or df.empty or not {"source", "error", "ok"}.issubset(df.columns):
        return 0, 0
    rows = df[df["source"] == source]
    if rows.empty:
        return 0, 0
    rows = rows.sort_values("run_at").drop_duplicates("run_at", keep="last")
    errori = rows["error"].fillna("").astype(str)
    # contano i run in cui QUESTA fase è fallita o è andata bene: una riga riuscita chiude la
    # serie, una riga di un'altra fase della stessa fonte non dice nulla su questa
    rows = rows[rows["ok"].astype(bool) | errori.str.startswith(step)]
    if rows.empty:
        return 0, 0
    fails = pause = 0
    in_pausa = True
    for ok, errore in zip(rows["ok"].astype(bool).tolist()[::-1],
                          rows["error"].fillna("").astype(str).tolist()[::-1]):
        if ok:
            break                          # una riga riuscita chiude la serie: la fonte è viva
        if is_suspended_row(errore):
            if in_pausa:
                pause += 1                 # pause in testa: quante volte di fila non si è provato
            continue                       # quelle vecchie non azzerano la serie dei fallimenti
        in_pausa = False
        fails += 1
    return fails, pause


def sospensione(store: Store, source: str, step: str) -> str | None:
    """Messaggio di sospensione se questa esecuzione **non** deve interrogare la fonte, altrimenti None.

    Regola: ``BACKOFF_FAILS`` fallimenti consecutivi → pausa; dopo ``BACKOFF_PROBE_RUNS`` pause
    consecutive si riprova comunque (sonda). Una sonda che fallisce **non azzera la serie** (si
    conta come tentativo fallito in più, ``state()``), quindi la fonte resta sospesa e si ritenta
    dopo altre ``BACKOFF_PROBE_RUNS`` pause: il ciclo è di **5 run con una sola richiesta dentro**
    (una al giorno con 5 run al giorno), testato in `tests/test_backoff.py`, che a regime conta
    4 richieste in 20 run.
    """
    fails, pause = state(store, source, step)
    if fails < BACKOFF_FAILS or pause >= BACKOFF_PROBE_RUNS:
        return None
    restanti = BACKOFF_PROBE_RUNS - pause
    return (f"{SUSPENDED_MARK} dopo {fails} run falliti consecutivi ({step}); "
            f"nuovo tentativo fra {restanti} run")
