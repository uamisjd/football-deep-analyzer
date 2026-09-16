"""Sonda delle fonti di fallback (docs/19 P1.10): una richiesta vera, un esito registrato.

Il punto non è il meteo di San Siro: è che un fallback **non esercitato** non è un fallback
funzionante. Questi test verificano il contratto della sonda — esito sempre registrato (anche
quando la fonte è rotta), tipi stabili per il Parquet, codice di uscita non zero se fallisce.
"""

from datetime import UTC, datetime

import pandas as pd

from fda.store import Store
from scripts.probe_fonti import PROBES, esegui, probe_openmeteo  # noqa: F401 (PROBES = contratto)

ORA = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)


class _ClientOk:
    def forecast(self, lat, lon, when):
        return {"temp_c": 21.4, "precip_prob": 60.0, "desc": "pioggia debole",
                "code": 61, "hour": f"{when:%Y-%m-%dT%H:00}"}


class _ClientRotto:
    def forecast(self, lat, lon, when):
        raise RuntimeError("HTTP 503 https://api.open-meteo.com/v1/forecast")


class _ClientVuoto:
    def forecast(self, lat, lon, when):
        return {}


def test_sonda_ok_registra_il_valore_vero():
    esito = probe_openmeteo(_ClientOk(), ORA)
    assert esito["ok"] is True
    assert "21 °C" in esito["detail"] and "pioggia 60%" in esito["detail"]
    assert "45.48,9.12" in esito["detail"]           # coordinate dichiarate, non implicite


def test_sonda_fallita_dichiara_l_errore():
    esito = probe_openmeteo(_ClientRotto(), ORA)
    assert esito["ok"] is False
    assert "RuntimeError" in esito["detail"] and "503" in esito["detail"]


def test_sonda_con_risposta_inutilizzabile():
    esito = probe_openmeteo(_ClientVuoto(), ORA)
    assert esito["ok"] is False and "ore utilizzabili" in esito["detail"]


def test_esegui_registra_ogni_sonda_anche_quando_una_esplode():
    def ko(_now):
        raise ValueError("client mal configurato")

    righe = esegui(ORA, probes={"openmeteo": lambda now: probe_openmeteo(_ClientOk(), now), "beta": ko})
    assert [r["probe"] for r in righe] == ["beta", "openmeteo"]      # ordine stabile
    assert righe[0]["ok"] is False and "ValueError" in righe[0]["detail"]
    assert righe[1]["ok"] is True
    for r in righe:
        assert r["run_at"] == ORA and isinstance(r["ok"], bool) and r["detail"]


def test_la_riga_finisce_nel_parquet_con_la_chiave_giusta(tmp_path):
    st = Store(tmp_path / "processed")
    st.upsert("source_probe", esegui(ORA, probes={"openmeteo": lambda now: probe_openmeteo(_ClientOk(), now)}))
    df = st.read("source_probe")
    assert list(df.columns) == ["run_at", "probe", "ok", "detail"]
    assert df.iloc[0]["probe"] == "openmeteo" and bool(df.iloc[0]["ok"]) is True
    # una seconda prova aggiorna la stessa riga (chiave run_at + probe), non la duplica
    st.upsert("source_probe", esegui(ORA, probes={"openmeteo": lambda now: probe_openmeteo(_ClientRotto(), now)}))
    df = st.read("source_probe")
    assert len(df) == 1 and bool(df.iloc[0]["ok"]) is False
    assert pd.Timestamp(df.iloc[0]["run_at"]) == pd.Timestamp(ORA)
    st.close()


def test_il_comando_esce_non_zero_se_una_sonda_fallisce(tmp_path, monkeypatch, capsys):
    import scripts.probe_fonti as mod

    monkeypatch.setattr(mod, "PROBES", {"rotta": lambda now: {"probe": "rotta", "ok": False,
                                                              "detail": "endpoint sparito"}})
    monkeypatch.setattr(mod, "Store", lambda path: Store(path))
    monkeypatch.setattr("sys.argv", ["probe_fonti.py", "--store", str(tmp_path / "processed")])
    assert mod.main() == 1
    assert "non risponde" in capsys.readouterr().out
    monkeypatch.setattr(mod, "PROBES", {"buona": lambda now: {"probe": "buona", "ok": True,
                                                              "detail": "previsione ok"}})
    assert mod.main() == 0
