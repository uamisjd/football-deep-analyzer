"""Test offline del backfill FotMob (`scripts/backfill_fotmob.py`, `docs/80`).

Nessuna rete: il client risponde dai sample in ``tests/fixtures`` e conta le richieste come
farebbe ``HttpClient``. I test coprono il contratto dello script — cosa scrive, cosa salta,
come riparte — non la forma dei dati FotMob (quella è già coperta da `tests/test_fotmob.py`).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

from fda.config import leagues
from fda.http import SourceStats
from fda.sources.fotmob import FotMobClient
from fda.store import Store

FIX = Path(__file__).parent / "fixtures"


def _load():
    p = Path(__file__).parent.parent / "scripts" / "backfill_fotmob.py"
    spec = importlib.util.spec_from_file_location("backfill_fotmob", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bf = _load()


class HttpFinto:
    """Sostituto di ``HttpClient``: solo i contatori che lo script legge a fine run."""

    def __init__(self) -> None:
        self.stats = SourceStats()

    def mark(self) -> int:
        return self.stats.requests


class ClientOffline(FotMobClient):
    """``FotMobClient`` senza rete: calendario e dettagli dai sample del repository.

    Il dettaglio è il matchDetails reale di Inter–Milan (5749666) clonato sull'id chiesto:
    ``parse_match`` è quello vero, quindi il test attraversa la stessa pipeline del collector.
    """

    def __init__(self, calendario: list[dict], dettagli: dict[int, dict], mancanti: set[int] = frozenset()):  # type: ignore[assignment]
        self.http = HttpFinto()
        self.raw_dir = FIX
        self._calendario = calendario
        self._dettagli = dettagli
        self._mancanti = set(mancanti)

    def fixtures_raw(self, league_id: int, season_str: str | None = None) -> list[dict]:
        self.http.stats.requests += 1
        return [dict(m, __season=season_str) for m in self._calendario]

    def match_details_raw(self, match_id: int, finished_hint: bool | None = None) -> dict:
        self.http.stats.requests += 1
        if match_id in self._mancanti:
            raise RuntimeError(f"matchDetails {match_id}: 404 finto")
        raw = json.loads(json.dumps(self._dettagli[match_id]))       # copia modificabile
        raw["general"]["matchId"] = match_id
        return raw


def _calendario_finto() -> tuple[list[dict], dict[int, dict]]:
    """Tre partite: due finite (una già in lineup) e una in programma, sui club del sample."""
    sample = json.loads((FIX / "fotmob_match_sample.json").read_text())
    home, away = sample["general"]["homeTeam"], sample["general"]["awayTeam"]
    ids = [5749666, 5749667, 5749668]
    righe = []
    for i, (mid, finita) in enumerate(zip(ids, (True, True, False), strict=True)):
        righe.append({
            "id": mid, "round": str(i + 1),
            "home": {"id": home["id"], "name": home["name"], "score": 2 if finita else None},
            "away": {"id": away["id"], "name": away["name"], "score": 1 if finita else None},
            "status": {"utcTime": f"2024-0{i + 8}-01T18:00:00Z", "finished": finita,
                       "started": finita, "cancelled": False},
        })
    # il terzo (scheduled) risponde comunque, ma non deve mai essere chiesto
    return righe, {mid: sample for mid in ids}


def _store(tmp_path) -> Store:
    return Store(tmp_path / "processed")


def test_stagioni_precedenti():
    assert bf.stagioni_precedenti("2026/2027", 2) == ["2025/2026", "2024/2025"]
    assert bf.stagioni_precedenti("2026/2027", 1) == ["2025/2026"]


def test_backfill_scrive_solo_coach_e_storico(tmp_path):
    """Il run salva le righe ``coach`` in ``lineup`` e la riga-storico in ``match_storico``."""
    store = _store(tmp_path)
    calendario, dettagli = _calendario_finto()
    client = ClientOffline(calendario, dettagli)
    rep = bf.backfill(client, store, [leagues(["ITA1"])[0]], ["2024/2025"])

    assert rep["partite_fatte"] == 2          # la scheduled non si scarica
    assert rep["righe_coach"] == 4            # 2 allenatori × 2 partite, nessun giocatore
    assert rep["senza_coach"] == 0 and rep["errori"] == 0
    lu = store.read("lineup")
    assert set(lu["role"]) == {"coach"} and set(lu["match_id"]) == {5749666, 5749667}
    sto = store.read("match_storico")
    assert len(sto) == 2 and set(sto["status"]) == {"finished"}
    assert set(sto["stagione"]) == {"2024/2025"} and list(sto["home_goals"]) == [2, 2]
    assert pd.api.types.is_datetime64_any_dtype(sto["utc_kickoff"])
    assert sto["utc_kickoff"].dt.tz is not None


def test_backfill_ripartibile_e_dry_run(tmp_path):
    """Dry-run non scrive nulla; il secondo run salta ciò che c'è già; ``limite`` spezza."""
    store = _store(tmp_path)
    calendario, dettagli = _calendario_finto()
    client = ClientOffline(calendario, dettagli)

    rep = bf.backfill(client, store, [leagues(["ITA1"])[0]], ["2024/2025"], dry_run=True)
    assert rep["partite_candidate"] == 2 and rep["partite_fatte"] == 0
    assert store.read("match_storico").empty and store.read("lineup").empty

    rep1 = bf.backfill(client, store, [leagues(["ITA1"])[0]], ["2024/2025"], limite=1)
    assert rep1["partite_fatte"] == 1 and rep1["interrotto"] is True
    rep2 = bf.backfill(client, store, [leagues(["ITA1"])[0]], ["2024/2025"])
    assert rep2["partite_fatte"] == 1 and rep2["partite_saltate"] == 1
    assert len(store.read("match_storico")) == 2

    rep3 = bf.backfill(client, store, [leagues(["ITA1"])[0]], ["2024/2025"])
    assert rep3["partite_fatte"] == 0 and rep3["partite_saltate"] == 2


def test_backfill_una_partita_rotta_non_ferma_il_run(tmp_path):
    store = _store(tmp_path)
    calendario, dettagli = _calendario_finto()
    client = ClientOffline(calendario, dettagli, mancanti={5749666})
    rep = bf.backfill(client, store, [leagues(["ITA1"])[0]], ["2024/2025"])
    assert rep["errori"] == 1 and rep["partite_fatte"] == 1
    assert list(store.read("match_storico")["match_id"]) == [5749667]


def test_riepilogo_incroci_conta_le_panchine(tmp_path):
    """Il riepilogo dice quante panchine in programma hanno davvero un incrocio nello storico."""
    store = _store(tmp_path)
    # due allenatori che si sono già affrontati su panchine opposte (una gara dello storico)
    store.write("lineup", pd.DataFrame([
        {"match_id": 1, "team_id": 10, "player_id": 100, "player_name": "Uno", "role": "coach"},
        {"match_id": 1, "team_id": 20, "player_id": 200, "player_name": "Due", "role": "coach"},
        {"match_id": 9, "team_id": 10, "player_id": 100, "player_name": "Uno", "role": "coach"},
        {"match_id": 9, "team_id": 20, "player_id": 200, "player_name": "Due", "role": "coach"},
    ]))
    store.write("fixtures", pd.DataFrame([
        {"match_id": 9, "home_id": 10, "home_name": "A", "away_id": 20, "away_name": "B",
         "home_goals": 1, "away_goals": 0, "status": "scheduled",
         "utc_kickoff": pd.Timestamp("2026-10-20 18:00", tz="UTC")},
    ]))
    store.write("match_storico", pd.DataFrame([
        {"match_id": 1, "home_id": 30, "away_id": 40, "home_goals": 0, "away_goals": 2,
         "status": "finished", "utc_kickoff": pd.Timestamp("2024-09-01 18:00", tz="UTC")},
    ]))
    rep = bf.riepilogo_incroci(store, log=lambda *_a: None)
    assert rep == {"panchine": 2, "con_incrocio": 2}    # entrambi i lati hanno il precedente

    store.write("match_storico", pd.DataFrame(columns=["match_id", "home_id", "away_id",
                                                       "home_goals", "away_goals", "status",
                                                       "utc_kickoff"]))
    rep = bf.riepilogo_incroci(store, log=lambda *_a: None)
    assert rep["con_incrocio"] == 0
