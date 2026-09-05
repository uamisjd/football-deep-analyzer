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
