"""Sospensione di una fonte che fallisce sempre allo stesso modo (docs/19 P1.9, docs/22 §3).

Misura che ha motivato il meccanismo: `espn standings` e `espn news` rispondono **403 da 20+
run consecutivi** dall'IP dei runner — 14 richieste a run (70 al giorno) per un dato che FotMob
e Google News coprono già, e 14 righe di avviso identiche in *Stato fonti* che rendevano
invisibile qualunque guasto nuovo.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from fda.backoff import (
    BACKOFF_FAILS,
    BACKOFF_PROBE_RUNS,
    is_suspended_row,
    sospensione,
    state,
)
from fda.store import Store
from tests.test_store_collect import FakeEspn, FakeEspnContato, FakeFotMob, FakeUnderstat

SORGENTE = "espn:ITA1"
FASE = "espn standings"
# storico seminato nel passato: l'esecuzione del test è il run più recente
BASE = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)


def _store(tmp_path, righe: list[dict]) -> Store:
    st = Store(tmp_path / "processed")
    if righe:
        st.upsert("source_status", righe)
    return st


def _riga(n: int, *, ok=False, errore="espn standings: SourceError: HTTP 403 https://x",
          richieste=1, source=SORGENTE) -> dict:
    return {"run_at": BASE + timedelta(hours=2 * n), "source": source, "requests": richieste,
            "ok": ok, "warn": not ok, "error": None if ok else errore,
            "rows": 0, "detail": "", "digest": ""}


def _sospesa(n: int, fallimenti: int) -> dict:
    return _riga(n, errore=f"espn standings: sospeso dopo {fallimenti} run falliti consecutivi "
                           f"({FASE}); nuovo tentativo fra 3 run", richieste=0)


def test_senza_storico_non_sospende(tmp_path):
    st = _store(tmp_path, [])
    assert state(st, SORGENTE, FASE) == (0, 0)
    assert sospensione(st, SORGENTE, FASE) is None


def test_sotto_la_soglia_non_sospende(tmp_path):
    """Un guasto saltuario non deve sospendere: servono BACKOFF_FAILS fallimenti di fila."""
    st = _store(tmp_path, [_riga(i) for i in range(BACKOFF_FAILS - 1)])
    assert state(st, SORGENTE, FASE) == (BACKOFF_FAILS - 1, 0)
    assert sospensione(st, SORGENTE, FASE) is None


def test_alla_soglia_sospende_col_piano_di_ritentativo(tmp_path):
    st = _store(tmp_path, [_riga(i) for i in range(BACKOFF_FAILS)])
    msg = sospensione(st, SORGENTE, FASE)
    assert msg and "sospeso" in msg
    assert f"{BACKOFF_FAILS} run falliti consecutivi" in msg
    assert f"nuovo tentativo fra {BACKOFF_PROBE_RUNS} run" in msg


def test_le_pause_consecutive_portano_alla_sonda(tmp_path):
    """Dopo BACKOFF_PROBE_RUNS pause si riprova: una fonte che riapre rientra da sola."""
    righe = [_riga(i) for i in range(BACKOFF_FAILS)]
    for p in range(BACKOFF_PROBE_RUNS):
        righe.append(_sospesa(BACKOFF_FAILS + p, BACKOFF_FAILS))
        st = _store(tmp_path, righe)
        if p < BACKOFF_PROBE_RUNS - 1:
            assert sospensione(st, SORGENTE, FASE) is not None, f"pausa {p}: doveva restare sospesa"
        else:
            assert sospensione(st, SORGENTE, FASE) is None, "ultima pausa: tocca alla sonda"
    # la sonda riesce → la storia riparte pulita
    st = _store(tmp_path, righe + [_riga(BACKOFF_FAILS + BACKOFF_PROBE_RUNS, ok=True)])
    assert state(st, SORGENTE, FASE) == (0, 0)
    assert sospensione(st, SORGENTE, FASE) is None


def test_un_successo_azzera_la_serie(tmp_path):
    st = _store(tmp_path, [_riga(0), _riga(1), _riga(2, ok=True)])
    assert state(st, SORGENTE, FASE) == (0, 0)


def test_altre_fonti_e_altre_fasi_non_contano(tmp_path):
    """La sospensione è per coppia (fonte, fase): il 403 della classifica non ferma altro."""
    st = _store(tmp_path, [
        *[_riga(i) for i in range(BACKOFF_FAILS)],
        *[_riga(i, source="espn:ENG1") for i in range(BACKOFF_FAILS)],
        *[_riga(i, source="fotmob:ITA1", errore="fotmob: SourceError: HTTP 500") for i in range(3)],
    ])
    assert sospensione(st, SORGENTE, FASE) is not None
    assert sospensione(st, "espn:ENG1", FASE) is not None
    assert sospensione(st, "fotmob:ITA1", "fotmob") is None       # solo 3 fallimenti
    assert sospensione(st, "understat:ITA1", FASE) is None        # fonte mai fallita


def test_is_suspended_row_distingue_pausa_e_guasto():
    assert is_suspended_row("espn standings: sospeso dopo 20 run falliti consecutivi (espn standings)")
    assert is_suspended_row("espn news: sospeso dopo 20 run falliti consecutivi (espn news)")
    assert not is_suspended_row("espn standings: SourceError: HTTP 403 https://x")
    assert not is_suspended_row(None)
    assert not is_suspended_row(float("nan"))


def test_la_riga_sospesa_e_riconosciuta_dopo_il_giro_nel_parquet(tmp_path):
    """Round-trip: il testo scritto dalla raccolta è lo stesso che la build classifica."""
    st = _store(tmp_path, [_riga(i) for i in range(BACKOFF_FAILS)])
    msg = sospensione(st, SORGENTE, FASE)
    st.upsert("source_status", [_riga(BACKOFF_FAILS, errore=f"espn standings: {msg}", richieste=0)])
    df = st.read("source_status")
    ultimo = df.sort_values("run_at").iloc[-1]
    assert bool(ultimo["ok"]) is False and ultimo["requests"] == 0
    assert is_suspended_row(ultimo["error"])
    assert sospensione(st, SORGENTE, FASE) is not None      # resta sospesa, non riparte da zero


def test_la_raccolta_non_interroga_espn_quando_e_sospeso(tmp_path):
    """Integrazione: con la fonte sospesa il client ESPN non riceve alcuna richiesta.

    Il contratto verificato è quello che conta per il costo: `report.requests["espn"] == 0`
    per la fase sospesa e nessuna riga di dati inventata.
    """
    from datetime import date

    from fda.collect import collect_league
    from fda.config import league

    st = _store(tmp_path, [_riga(i) for i in range(BACKOFF_FAILS)])

    chiamate: list[str] = []

    class EspnTracciato(FakeEspn):
        def standings_raw(self, code):
            chiamate.append("standings")
            return super().standings_raw(code)

        def scoreboard_raw(self, code, day=None):
            chiamate.append("scoreboard")
            return super().scoreboard_raw(code, day)

    rep = collect_league(league("ITA1"), st, past_days=30, future_days=30,
                         fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
                         espn=EspnTracciato(), today=date(2026, 9, 6))
    assert "standings" not in chiamate, "la classifica ESPN non doveva essere interrogata"
    assert chiamate.count("scoreboard") >= 1, "lo scoreboard non è in backoff e deve restare attivo"
    riga = st.read("source_status")
    riga = riga[(riga.source == "espn:ITA1") & (pd.to_datetime(riga.run_at, utc=True) > pd.Timestamp(BASE))]
    ultima = riga.sort_values("run_at").iloc[-1]
    # col client finto il contatore HTTP non si muove: 0 richieste documenta che la fase
    # sospesa non ne accende nemmeno una (in produzione il contatore è `http.mark()`)
    assert ultima["requests"] == 0
    assert not bool(ultima["ok"]) and "sospeso" in str(ultima["error"])
    assert any("sospeso" in e for e in rep.errors)
    st.close()


@pytest.mark.parametrize("sorgente,fase,prefisso_errore", [
    ("espn:NEWS", "espn news", "espn news ITA1: SourceError: HTTP 403 https://x"),
])
def test_anche_le_notizie_espn_si_sospendono(tmp_path, sorgente, fase, prefisso_errore):
    """La fase notizie ha un nome di fonte diverso (`espn:NEWS`) e la stessa regola."""
    st = _store(tmp_path, [_riga(i, source=sorgente, errore=prefisso_errore)
                           for i in range(BACKOFF_FAILS)])
    assert sospensione(st, sorgente, fase) is not None


# ---- il costo reale del backoff (correlato del 2026-09-16, docs/23 §3) -----------------------
def test_una_sonda_che_fallisce_non_riapre_la_fonte(tmp_path):
    """Regresso del run `35129006426`: la sonda fallita contava come «primo fallimento» di una
    serie nuova, quindi la fonte tornava a essere interrogata a ogni run per altri 4 run."""
    storico = ([_riga(i) for i in range(BACKOFF_FAILS)]              # 5 fallimenti → sospensione
               + [_sospesa(i, BACKOFF_FAILS) for i in range(BACKOFF_FAILS, BACKOFF_FAILS + BACKOFF_PROBE_RUNS)]
               + [_riga(BACKOFF_FAILS + BACKOFF_PROBE_RUNS)])        # la sonda: fallisce di nuovo
    st = _store(tmp_path, storico)
    # i fallimenti sono 6 (5 + sonda), la pausa riparte da zero: la fonte resta sospesa
    assert state(st, SORGENTE, FASE) == (BACKOFF_FAILS + 1, 0)
    stop = sospensione(st, SORGENTE, FASE)
    assert stop is not None and f"nuovo tentativo fra {BACKOFF_PROBE_RUNS} run" in stop


def test_il_costo_di_una_fonte_rotta_e_una_richiesta_ogni_cinque_run(tmp_path):
    """Il numero che giustifica il meccanismo, misurato a regime.

    Fase di apprendimento: i primi ``BACKOFF_FAILS`` run falliscono (il backoff non esiste ancora,
    quindi ogni run tenta). Poi la fonte è sospesa e il ciclo diventa «``BACKOFF_PROBE_RUNS`` pause
    + 1 tentativo» = 5 run: in 20 run di regime, **4** richieste invece di 20 — che con la semantica
    precedente (la sonda che riapriva la fonte) diventavano ~11.
    """
    st = Store(tmp_path / "processed")

    def _esegui(i: int) -> bool:
        """Un run: True se ha tentato la fonte (nessuna sospensione attiva)."""
        stop = sospensione(st, SORGENTE, FASE)
        err = ("espn standings: SourceError: HTTP 403 https://x" if stop is None else
               f"espn standings: sospeso dopo 5 run falliti consecutivi ({FASE}); nuovo tentativo fra 1 run")
        st.upsert("source_status", [{"run_at": BASE + timedelta(hours=2 * i), "source": SORGENTE,
                                     "requests": 0 if stop else 1, "ok": False, "warn": True,
                                     "error": err, "rows": 0, "detail": "", "digest": ""}])
        return stop is None

    avvio = sum(_esegui(i) for i in range(BACKOFF_FAILS))
    assert avvio == BACKOFF_FAILS                       # prima della sospensione si prova sempre
    regime = 20
    tentativi = sum(_esegui(i) for i in range(BACKOFF_FAILS, BACKOFF_FAILS + regime))
    # ciclo = BACKOFF_PROBE_RUNS pause + il tentativo: 4 richieste in 20 run (una al giorno con 5
    # run al giorno, come dichiara la pagina *Stato fonti*)
    assert tentativi == regime // (BACKOFF_PROBE_RUNS + 1)


def test_riga_sospesa_senza_richieste_e_scoreboard_a_parte(tmp_path):
    """Il caso che ha reso rosso il daily (run `35129006426`, docs/23 §3).

    Il contatore della riga «espn:ITA1» era il **totale del client**: includeva le richieste
    dello scoreboard, che non è in backoff. La pagina mostrava quindi una fonte «SOSPESA con 1
    richiesta» e l'invariante [28] non poteva più distinguere un backoff attivo da un backoff
    inesistente. Ora la classifica e lo scoreboard hanno due righe e due contatori.
    """
    from datetime import date

    from fda.collect import collect_league
    from fda.config import league

    st = _store(tmp_path, [_riga(i) for i in range(BACKOFF_FAILS)])
    espn = FakeEspnContato()
    rep = collect_league(league("ITA1"), st, past_days=30, future_days=30,
                         fotmob=FakeFotMob(raw_dir=tmp_path / "raw"), understat=FakeUnderstat(),
                         espn=espn, today=date(2026, 9, 6))
    assert espn.n >= 1, "lo scoreboard è stato interrogato: il contatore deve muoversi"
    righe = st.read("source_status")
    righe = righe[pd.to_datetime(righe.run_at, utc=True) > pd.Timestamp(BASE)]
    sospesa = righe[righe.source == "espn:ITA1"].sort_values("run_at").iloc[-1]
    scoreboard = righe[righe.source == "espn scoreboard:ITA1"].sort_values("run_at").iloc[-1]
    assert sospesa["requests"] == 0, "una fase sospesa non tocca la rete: il backoff deve esistere"
    assert "sospeso" in str(sospesa["error"])
    assert scoreboard["requests"] >= 1, "lo scoreboard non è governato dal backoff: resta attivo"
    assert bool(scoreboard["ok"]) and scoreboard["rows"] > 0
    assert rep.requests["espn"] == 0 and rep.requests["espn scoreboard"] >= 1
    st.close()
