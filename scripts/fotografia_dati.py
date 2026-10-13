"""Una fotografia dei dati al giorno: decide se questo run del `daily` deve committare.

Perché esiste:
    Il workflow `daily` gira **cinque volte al giorno** e ognuna ricostruisce i Parquet
    aggiornati: sono fotografie della stessa cosa, e il run successivo non le legge
    (il sito si genera in-run, non dal repository). Misurato il 2026-10-13 (`docs/104`
    §3): i commit dei dati hanno scritto **743,8 MB negli ultimi 30 giorni**, cioè
    ~24,8 MB al giorno, portando il pack a **722,85 MiB** — verso il limite che GitHub
    raccomanda (1 GB) in ~11 giorni. Con una fotografia al giorno la crescita scende a
    ~150 MB al mese (−80%), senza toccare la freschezza del sito: i cinque run
    pubblicano tutti, cambia solo quante copie entrano nell'archivio.

Regola (dichiarata in `docs/105`, misurata e provata in `tests/test_fotografia_dati.py`):
    - nessuna fotografia precedente → committa (primo giro in assoluto);
    - esiste già una fotografia di **oggi** (data UTC) → non committa;
    - altrimenti committa se **l'ora UTC è ≥ 20** (il run serale, quello con i risultati
      della giornata) **oppure** se sono passate **≥ 24 ore** (rete di sicurezza: se il
      run serale di ieri è fallito, il primo run utile recupera da solo).

Il registro preregistrato `prospettico.parquet` **non** segue questa regola: si salva a
ogni run se è cambiato, perché il suo valore di prova è la data di registrazione, non la
fotografia (gestito nel workflow, `docs/105` §3).

Uso:
    python -m scripts.fotografia_dati --repo uamisjd/football-deep-analyzer --ramo main
    → stampa `commit=true` o `commit=false` (una riga, per `$GITHUB_OUTPUT`), il motivo
      su stderr.

Fail-open: qualunque errore (rete, API, token) produce `commit=true`. Meglio una
fotografia in più che un buco nei dati.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

ORA_SERALE_UTC = 20
RETE_SICUREZZA = timedelta(hours=24)
PERCORSO_DATI = "data/processed"
SNAPSHOT_MARKER = "FDA-SNAPSHOT: full-v1"
MAX_PAGES = 20


def _a_utc(quando: datetime) -> datetime:
    """Rende consapevole un istante: i nostri timbri sono UTC, non i fusi locali."""
    return quando.replace(tzinfo=UTC) if quando.tzinfo is None else quando.astimezone(UTC)


def ultima_fotografia(repo: str, ramo: str, token: str | None = None, per_page: int = 100) -> datetime | None:
    """Ultima fotografia COMPLETA: i commit del solo registro non spostano il clock.

    Riconosce il marker nuovo e i commit storici ``data: run ...``. Scorre anche oltre
    la prima pagina, con un limite esplicito: al limite genera errore → fail-open.
    Non inferisce una fotografia dal semplice percorso modificato.
    """
    if shutil.which("gh") and (token or os.environ.get("GH_TOKEN")):
        return _leggi_con_gh(repo, ramo, per_page)
    return _leggi_con_requests(repo, ramo, token, per_page)


def _interpreta(data_iso: str | None) -> datetime | None:
    if not data_iso:
        return None
    return datetime.fromisoformat(data_iso)


def _trova_fotografia(read_page: Callable[[int], list[dict[str, Any]]], per_page: int) -> datetime | None:
    if not 1 <= per_page <= 100:
        raise ValueError("per_page deve essere fra 1 e 100")
    for page in range(1, MAX_PAGES + 1):
        entries = read_page(page)
        for entry in entries:
            commit = entry["commit"]
            message = commit["message"]
            if SNAPSHOT_MARKER in message.splitlines() or message.startswith("data: run "):
                date = _interpreta(commit["committer"]["date"])
                if date is None:
                    raise ValueError("fotografia senza data")
                return date
        if len(entries) < per_page:
            return None
    raise RuntimeError("cronologia troppo lunga senza fotografia: fail-open")


def _leggi_con_gh(repo: str, ramo: str, per_page: int = 100) -> datetime | None:
    import subprocess

    def read_page(page: int) -> list[dict[str, Any]]:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/commits", "-X", "GET",
             "-f", f"path={PERCORSO_DATI}", "-f", f"sha={ramo}",
             "-f", f"per_page={per_page}", "-f", f"page={page}"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(result.stdout)

    return _trova_fotografia(read_page, per_page)


def _leggi_con_requests(repo: str, ramo: str, token: str | None = None, per_page: int = 100) -> datetime | None:
    import requests

    base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def read_page(page: int) -> list[dict[str, Any]]:
        response = requests.get(
            f"{base}/repos/{repo}/commits",
            params={"path": PERCORSO_DATI, "sha": ramo, "per_page": per_page, "page": page},
            headers=headers, timeout=20,
        )
        response.raise_for_status()
        return response.json()

    return _trova_fotografia(read_page, per_page)


def decide(
    adesso: datetime,
    ultima: datetime | None,
    ora_serale: int = ORA_SERALE_UTC,
    rete_sicurezza: timedelta = RETE_SICUREZZA,
) -> tuple[bool, str]:
    """La decisione, pura e riproducibile: nessuna rete, nessuna variabile d'ambiente."""
    adesso = _a_utc(adesso)
    if ultima is None:
        return True, "nessuna fotografia precedente: si salva la prima"
    ultima = _a_utc(ultima)
    if ultima.date() == adesso.date():
        return False, f"fotografia di oggi ({adesso.date()}) già salvata alle {ultima:%H:%M} UTC"
    if adesso.hour >= ora_serale:
        return True, f"run serale (ore {adesso.hour} UTC ≥ {ora_serale}): si salva la fotografia di oggi"
    passate = adesso - ultima
    if passate >= rete_sicurezza:
        return True, (
            f"nessuna fotografia da {passate.total_seconds() / 3600:.1f} ore "
            f"(≥ {rete_sicurezza.total_seconds() / 3600:.0f}): rete di sicurezza"
        )
    return False, (
        f"fotografia di ieri ({ultima.date()} {ultima:%H:%M} UTC) e run non serale "
        f"({adesso.hour} UTC): si aspetta il run delle {ora_serale} UTC"
    )


def decidi_dal_repository(
    repo: str, ramo: str, adesso: datetime, token: str | None = None,
    lettore: Callable[..., datetime | None] = ultima_fotografia,
) -> tuple[bool, str]:
    """Decisione usando l'API. Fail-open: se la lettura fallisce, si committa comunque."""
    try:
        ultima = lettore(repo, ramo, token)
    except Exception as errore:  # noqa: BLE001 — rete, 403 o JSON inatteso: non bloccare l'archivio
        return True, f"lettura dell'ultima fotografia non riuscita ({errore}): fail-open, si committa"
    return decide(adesso, ultima)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decide se il run deve salvare la fotografia dei dati (docs/105).")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--ramo", default=os.environ.get("GITHUB_REF_NAME", "main"))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--now", default=None, help="istante UTC in formato ISO, solo per prove manuali")
    parser.add_argument("--ora-serale", type=int, default=ORA_SERALE_UTC)
    args = parser.parse_args(argv)

    adesso = datetime.fromisoformat(args.now) if args.now else datetime.now(UTC)
    esito, motivo = decidi_dal_repository(args.repo, args.ramo, adesso, args.token)
    # la decisione utile va su stdout (una riga, per $GITHUB_OUTPUT); il motivo su stderr
    print(f"commit={'true' if esito else 'false'}")
    print(f"fotografia dei dati: {motivo}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
