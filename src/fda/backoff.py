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
    """(fallimenti consecutivi, pause consecutive) dell'ultima serie di errore.

    Si cammina a ritroso nella storia della coppia (``source``, ``step``) partendo dal run più
    recente: prima le righe di pausa, poi quelle di fallimento, e ci si ferma alla prima riga
    riuscita o a una pausa più vecchia dell'ultimo tentativo (inizio di un ciclo precedente).
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
    fase = "pausa"
    for ok, errore in zip(rows["ok"].astype(bool).tolist()[::-1],
                          rows["error"].fillna("").astype(str).tolist()[::-1]):
        if ok:
            break
        sospesa = is_suspended_row(errore)
        if fase == "pausa":
            if sospesa:
                pause += 1
                continue
            fase = "falli"
        if sospesa:
            break                          # pausa più vecchia dell'ultimo tentativo: nuovo ciclo
        fails += 1
    return fails, pause


def sospensione(store: Store, source: str, step: str) -> str | None:
    """Messaggio di sospensione se questa esecuzione **non** deve interrogare la fonte, altrimenti None.

    Regola: ``BACKOFF_FAILS`` fallimenti consecutivi → pausa; dopo ``BACKOFF_PROBE_RUNS`` pause
    consecutive si riprova comunque (sonda). Un run di sonda che fallisce riparte dalla pausa,
    quindi con 5 run al giorno il costo di una fonte rotta scende da 14 richieste a run a
    **una ogni cinque run**, senza mai perdere la capacità di accorgersi del rientro.
    """
    fails, pause = state(store, source, step)
    if fails < BACKOFF_FAILS or pause >= BACKOFF_PROBE_RUNS:
        return None
    restanti = BACKOFF_PROBE_RUNS - pause
    return (f"{SUSPENDED_MARK} dopo {fails} run falliti consecutivi ({step}); "
            f"nuovo tentativo fra {restanti} run")
