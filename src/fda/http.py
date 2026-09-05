"""Client HTTP comune: cache su disco, rate limit per fonte, retry con backoff.

Regole di progetto applicate qui:
- ogni fonte ha una pausa minima tra richieste (rispetto delle fonti);
- ciò che è già stato scaricato e ancora valido non viene richiesto di nuovo;
- le risposte grezze finiscono in data/cache (non versionata), mai in chat.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from .config import CACHE_DIR

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


class SourceError(RuntimeError):
    """Errore definitivo verso una fonte (dopo i retry)."""


@dataclass
class SourceStats:
    requests: int = 0
    cache_hits: int = 0
    errors: int = 0
    last_error: str | None = None


@dataclass
class HttpClient:
    """Client per una singola fonte."""

    name: str
    rate_limit_s: float = 1.0
    headers: dict[str, str] = field(default_factory=dict)
    timeout_s: float = 30.0
    max_retries: int = 3
    max_requests: int | None = None
    cache_dir: Path | None = None
    stats: SourceStats = field(default_factory=SourceStats)
    _last_call: float = field(default=0.0, init=False, repr=False)
    _session: requests.Session = field(default_factory=requests.Session, init=False, repr=False)

    def __post_init__(self) -> None:
        self._session.headers.update({**DEFAULT_HEADERS, **self.headers})
        if self.cache_dir is None:
            self.cache_dir = CACHE_DIR / self.name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---- cache -----------------------------------------------------------------------------
    def _cache_path(self, url: str, params: dict[str, Any] | None) -> Path:
        key = url + ("?" + json.dumps(params, sort_keys=True) if params else "")
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, path: Path, ttl_h: float | None) -> bytes | None:
        if ttl_h is None or not path.exists():
            return None
        age_h = (time.time() - path.stat().st_mtime) / 3600.0
        if age_h > ttl_h:
            return None
        return path.read_bytes()

    # ---- richiesta -------------------------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.rate_limit_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get_bytes(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        ttl_h: float | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> bytes:
        """GET con cache (se ttl_h) e retry. Ritorna il corpo grezzo."""
        cache_path = self._cache_path(url, params)
        cached = self._read_cache(cache_path, ttl_h)
        if cached is not None:
            self.stats.cache_hits += 1
            return cached

        if self.max_requests is not None and self.stats.requests >= self.max_requests:
            raise SourceError(f"[{self.name}] budget richieste esaurito ({self.max_requests})")

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            self.stats.requests += 1
            try:
                resp = self._session.get(
                    url, params=params, timeout=self.timeout_s, headers=extra_headers
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                if resp.status_code >= 400:
                    # 4xx diversi da 429: inutile riprovare
                    self.stats.errors += 1
                    self.stats.last_error = f"HTTP {resp.status_code} {url}"
                    raise SourceError(self.stats.last_error)
                body = resp.content
                if ttl_h is not None:
                    cache_path.write_bytes(body)
                return body
            except SourceError:
                raise
            except Exception as exc:  # rete, timeout, 429, 5xx
                last_exc = exc
                self.stats.errors += 1
                self.stats.last_error = f"{type(exc).__name__}: {exc}"
                backoff = min(60.0, 2.0**attempt)
                log.warning("[%s] tentativo %d/%d fallito (%s); attendo %.0fs",
                            self.name, attempt, self.max_retries, exc, backoff)
                time.sleep(backoff)
        raise SourceError(f"[{self.name}] richiesta fallita: {url} ({last_exc})")

    def get_json(self, url: str, params: dict[str, Any] | None = None,
                 ttl_h: float | None = None, extra_headers: dict[str, str] | None = None) -> Any:
        body = self.get_bytes(url, params=params, ttl_h=ttl_h, extra_headers=extra_headers)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise SourceError(f"[{self.name}] risposta non JSON da {url}: {exc}") from exc

    def get_text(self, url: str, params: dict[str, Any] | None = None,
                 ttl_h: float | None = None) -> str:
        return self.get_bytes(url, params=params, ttl_h=ttl_h).decode("utf-8", errors="replace")
