"""Diagnostica delle fonti: imbuto dei conteggi per stadio e firma dello schema.

Perché esiste (docs/21 §15). Un run può chiudersi con esito «OK» e **zero righe** — feed
valido ma vuoto, forma del payload cambiata, finestra temporale che scarta tutto. Senza
conteggi per stadio e senza i nomi dei campi visti, quel caso è indistinguibile da una
fonte sana: la card resta buia e nessuno sa perché (misurato il 2026-09-15: `news` 139
richieste e `transfers` 132 payload, zero righe, zero errori).

Due prodotti, due destinazioni diverse:

- ``detail``: frase breve in **italiano** di soli numeri e fatti dell'imbuto, pubblicata
  in ``stato.html`` accanto alla riga della fonte — una fonte «OK» con 0 righe deve dire
  perché (invariante [28] di ``scripts/verify_site.py``);
- ``digest``: firma tecnica con i **soli nomi dei campi** visti nel payload, salvata in
  ``source_status.parquet`` e scritta nel log. I log di Actions non sono leggibili dal
  sandbox dell'agente, i Parquet committati sì: la firma vive nel dato, non solo nel log.

Regole rispettate: mai valori, mai dati grezzi (whitelist di caratteri per i nomi e tetti
di lunghezza), nessuna richiesta in più verso le fonti — i conteggi nascono da payload già
scaricati.
"""

from __future__ import annotations

import re
from typing import Any

# Un nome di campo è pubblicabile solo se sta in questa forma: parole di sole lettere,
# cifre o «_», separate da spazi singoli, tetto di lunghezza incluso. Niente valori,
# niente testo libero, niente identificatori lunghi (che sarebbero dati travestiti da
# chiave). Gli spazi fra parole sono ammessi dal 2026-09-16 (docs/21 §17) perché la
# sezione `transfers` di FotMob usa chiavi come «Players in»/«Players out»/«Contract
# extension»: senza spazi la firma di quella sezione risultava vuota. Rischio residuo
# accettato e documentato: una chiave che È un dato (es. un nome di squadra) passa la
# whitelist se è fatta di sole parole breve — i contenitori su cui si calcola la firma
# non sono mai chiavati per valore nelle fonti in uso.
FIELD_NAME = re.compile(r"^[A-Za-z0-9_]+(?: [A-Za-z0-9_]+)*$")
FIELD_MAX_LEN = 40

MAX_DETAIL = 200      # sta in una cella di tabella senza rompere la pagina
MAX_DIGEST = 240      # sta in una cella di Parquet e in una riga di log
MAX_KEYS = 12         # nomi di campo mostrati per livello (oltre non serve a diagnosticare)


def bump(diag: dict[str, int] | None, key: str, n: int = 1) -> None:
    """Somma un contatore dell'imbuto (``None`` → no-op: i parser restano chiamabili da soli)."""
    if diag is not None:
        diag[key] = int(diag.get(key, 0)) + int(n)


def key_names(obj: Any, limit: int = MAX_KEYS) -> list[str]:
    """Nomi dei campi visibili in un payload: *solo nomi*, mai valori.

    Dizionario → le sue chiavi. Lista → le chiavi del primo elemento dizionario (la forma
    di una lista è la forma dei suoi elementi). Qualunque altro tipo non ha nomi da
    mostrare → lista vuota. I nomi fuori dalla whitelist vengono scartati.
    """
    names: list[str] = []
    if isinstance(obj, dict):
        names = [str(k) for k in obj.keys()]
    elif isinstance(obj, list):
        for element in obj:
            if isinstance(element, dict):
                names = [str(k) for k in element.keys()]
                break
    return [n for n in names if FIELD_NAME.match(n) and len(n) <= FIELD_MAX_LEN][:limit]


def shape_of(obj: Any, limit: int = MAX_KEYS) -> str:
    """Firma compatta della forma di un payload: tipo, dimensioni e nomi dei campi.

    Esempi: ``dict(4): transfers,details,fixtures,squad`` · ``lista(0)`` · ``NoneType``.
    Non contiene mai valori: serve a riconoscere «la fonte ha cambiato schema» senza
    scaricare nulla a mano.
    """
    if isinstance(obj, dict):
        names = key_names(obj, limit)
        return f"dict({len(obj)}): {','.join(names)}" if names else f"dict({len(obj)}): nessun nome utile"
    if isinstance(obj, list):
        names = key_names(obj, limit)
        return f"lista({len(obj)}) di dict: {','.join(names)}" if names else f"lista({len(obj)})"
    return type(obj).__name__


def _join(parts: list[str], limit: int) -> str:
    text = " · ".join(p for p in parts if p)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def detail(*parts: str, limit: int = MAX_DETAIL) -> str:
    """Frase dell'imbuto per la pagina — solo numeri e fatti, in italiano, con tetto di lunghezza."""
    return _join([str(p) for p in parts], limit)


def digest(*parts: str, limit: int = MAX_DIGEST) -> str:
    """Firma tecnica per il Parquet e il log — nomi di campo, mai valori, con tetto di lunghezza."""
    return _join([str(p) for p in parts], limit)
