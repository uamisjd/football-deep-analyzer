import time
from pathlib import Path

from fda.http import HttpClient


def test_cache_roundtrip(tmp_path: Path, monkeypatch):
    client = HttpClient(name="test", rate_limit_s=0, cache_dir=tmp_path)
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        content = b'{"ok": true}'

    def fake_get(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(client._session, "get", fake_get)
    assert client.get_json("http://x/a", ttl_h=1) == {"ok": True}
    assert client.get_json("http://x/a", ttl_h=1) == {"ok": True}
    assert calls["n"] == 1                      # seconda lettura dalla cache
    assert client.stats.cache_hits == 1


def test_rate_limit(tmp_path: Path, monkeypatch):
    client = HttpClient(name="test2", rate_limit_s=0.2, cache_dir=tmp_path)

    class FakeResp:
        status_code = 200
        content = b"1"

    monkeypatch.setattr(client._session, "get", lambda *a, **k: FakeResp())
    t0 = time.monotonic()
    client.get_bytes("http://x/1")
    client.get_bytes("http://x/2")
    assert time.monotonic() - t0 >= 0.2


def test_retry_respects_request_budget(tmp_path, monkeypatch):
    import pytest

    from fda.http import SourceError
    client = HttpClient("retry", max_requests=1, max_retries=3, cache_dir=tmp_path)
    calls = []
    def fail(*a, **kw):
        calls.append(1)
        raise ConnectionError("simulated")
    monkeypatch.setattr(client._session, "get", fail)
    monkeypatch.setattr(client, "_throttle", lambda: None)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with pytest.raises(SourceError, match="budget"):
        client.get_bytes("https://example.invalid")
    assert client.stats.requests == len(calls) == 1


def test_retry_success_within_budget_and_cache_after_exhaustion(tmp_path, monkeypatch):
    client = HttpClient("retry", max_requests=2, max_retries=3, cache_dir=tmp_path)
    calls = []
    class Response:
        status_code = 200
        content = b"cached"
    def get(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("simulated")
        return Response()
    monkeypatch.setattr(client._session, "get", get)
    monkeypatch.setattr(client, "_throttle", lambda: None)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    assert client.get_bytes("https://example.invalid", ttl_h=1) == b"cached"
    assert client.get_bytes("https://example.invalid", ttl_h=1) == b"cached"
    assert client.stats.requests == len(calls) == 2


def test_zero_budget_and_permanent_4xx(tmp_path, monkeypatch):
    import pytest

    from fda.http import SourceError
    client = HttpClient("zero", max_requests=0, cache_dir=tmp_path)
    with pytest.raises(SourceError, match="budget"):
        client.get_bytes("https://example.invalid")
    assert client.stats.requests == 0
    client.max_requests = 5
    class Response:
        status_code = 404
    monkeypatch.setattr(client._session, "get", lambda *a, **kw: Response())
    with pytest.raises(SourceError, match="404"):
        client.get_bytes("https://example.invalid")
    assert client.stats.requests == 1
