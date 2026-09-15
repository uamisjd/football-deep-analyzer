"""Test offline del blocco mercato (docs/21 P2-7): parser FotMob `teams.transfers`,
collettore isolato e card «Mercato: arrivi e partenze»."""

import pandas as pd

from fda.collect import collect_transfers
from fda.site.analysis import MatchAnalysis
from fda.sources.fotmob import FotMobClient
from fda.store import Store

STANDINGS = pd.DataFrame([
    {"league_code": "ITA1", "team_id": 1, "team_name": "Roma", "rank": 1, "played": 3,
     "goals_for": 8, "goals_against": 3, "goal_diff": 5, "points": 9},
    {"league_code": "ITA1", "team_id": 2, "team_name": "Inter", "rank": 2, "played": 3,
     "goals_for": 6, "goals_against": 3, "goal_diff": 3, "points": 7},
])

# forma «documentata» dai client FotMob della community: dizionario incoming/outgoing,
# fee e from/to come oggetti, date come oggetto con utc/localized
RAW_DICT = {"transfers": {
    "incoming": [
        {"name": "Neo Arrivo", "position": "LW",
         "from": {"name": "Ajax", "id": "9"},
         "transferType": "transfer", "fee": {"feeText": "€45.0M", "localizedFeeText": "45,0 M€"},
         "date": {"utc": "2026-07-05T00:00:00Z", "localized": "05/07/2026"}},
        {"name": "Prestito Nuovo", "position": "CB",
         "from": {"name": "Chelsea"}, "transferType": "loan", "fee": {"feeText": "Loan"},
         "date": {"utc": "2026-08-01T00:00:00Z"}},
    ],
    "outgoing": [
        {"name": "Vecchia Gloria", "position": "CF",
         "to": {"name": "Milan"}, "transferType": "free", "fee": "",
         "date": {"utc": "2026-07-01T00:00:00Z"}},
    ],
}}

# forma alternativa tollerata: lista piatta con direzione per voce
RAW_LIST = {"transfers": [
    {"playerName": "Lista Piatta", "transferDirection": "out", "to": "Napoli",
     "type": "loan", "fee": "Prestito", "transferDate": "2026-08-20"},
]}


def test_parse_transfers_dizionario():
    rows = FotMobClient.parse_transfers(RAW_DICT, 1, "Roma", "ITA1")
    assert len(rows) == 3
    a = rows[0]
    assert (a["player_name"], a["direction"], a["counterpart"]) == ("Neo Arrivo", "in", "Ajax")
    assert a["fee_text"] == "45,0 M€" and a["transfer_type"] == "transfer"
    assert a["date"].startswith("2026-07-05") and a["position"] == "LW"
    assert rows[2]["direction"] == "out" and rows[2]["counterpart"] == "Milan"


def test_parse_transfers_lista_piatta():
    rows = FotMobClient.parse_transfers(RAW_LIST, 2, "Inter", "ITA1")
    assert rows == [{"team_id": 2, "team_name": "Inter", "league_code": "ITA1",
                     "player_name": "Lista Piatta", "position": "", "direction": "out",
                     "counterpart": "Napoli", "fee_text": "Prestito", "transfer_type": "loan",
                     "date": "2026-08-20"}]


def test_parse_transfers_forma_sconosciuta_zero_righe():
    assert FotMobClient.parse_transfers({"transfers": "boh"}, 1, "Roma", "ITA1") == []
    assert FotMobClient.parse_transfers({}, 1, "Roma", "ITA1") == []
    assert FotMobClient.parse_transfers(None, 1, "Roma", "ITA1") == []


class _StubFotMob:
    """Solo le chiamate: Roma risponde, Inter esplode (una fonte rotta non ferma il run)."""

    def __init__(self):
        # come un client vero: il contatore parte da zero e sale a ogni richiesta. Da
        # quando `source_status` registra le richieste **della fase** (non il cumulativo
        # del client condiviso), uno stub fermo a un numero fisso farebbe leggere 0.
        self.requests = 0
        self.http = type("H", (), {"stats": self})()

    def team_raw(self, team_id: int) -> dict:
        self.requests += 1
        if team_id == 2:
            raise RuntimeError("teams temporaneamente irraggiungibile")
        return RAW_DICT


def test_collect_transfers_isolato_e_tollerante(tmp_path):
    st = Store(tmp_path / "mercato")
    st.write("fotmob_standings", STANDINGS)
    report = collect_transfers(st, fotmob=_StubFotMob())
    tr = st.read("transfers")
    assert len(tr) == 3 and set(tr.team_id) == {1}          # Roma sì, Inter saltata
    assert any("transfers Inter" in e for e in report.errors)  # errore registrato, run vivo
    assert report.requests == {"transfers": 2}
    st.close()


def test_summer_market_card_e_ordine(tmp_path):
    st = Store(tmp_path / "mercato2")
    rows = FotMobClient.parse_transfers(RAW_DICT, 1, "Roma", "ITA1")
    # terza entrata, la più vecchia: l'ordine in card deve essere per data desc
    rows.append({**rows[0], "player_name": "Arrivo Vecchio",
                 "date": "2026-06-01T00:00:00Z"})
    st.write("transfers", pd.DataFrame(rows))
    an = MatchAnalysis(st)
    assert an.summer_market(2) is None                        # squadra senza righe → None
    mk = an.summer_market(1)
    assert mk is not None
    assert mk["n_in"] == 3 and mk["n_out"] == 1
    assert len(mk["arrivals"]) == 3 and mk["arrivals"][0]["name"] == "Prestito Nuovo"  # data desc
    assert mk["arrivals"][0]["type_it"] == "prestito" and mk["arrivals"][0]["date_it"] == "01/08/2026"
    assert mk["departures"][0]["name"] == "Vecchia Gloria"
    st.close()


def test_summer_market_senza_tabella(tmp_path):
    st = Store(tmp_path / "mercato3")
    an = MatchAnalysis(st)
    assert an.summer_market(1) is None                        # tabella mai raccolta → None
    st.close()
