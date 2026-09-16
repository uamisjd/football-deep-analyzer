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

# disposizione REALE dell'endpoint `teams` (firma del run 2026-09-16 09:34, docs/21 §17;
# confermata dai tipi Go di mheers/go-fotmob): transfers = {type, data{«Players in»,
# «Players out», «Contract extension»}, allTransfers, allRumours, maxFee, ourTeamId}.
# Le voci hanno name/position{label,key}/transferDate/fromClub(Id)/toClub(Id)/
# fee{value,feeText,localizedFeeText}/transferType{text}/contractExtension.
RAW_REALE = {"transfers": {
    "type": "team",
    "ourTeamId": 1,
    "maxFee": "€40M",
    "data": {
        "Players in": [
            {"name": "Nuovo Acquisto", "playerId": 111,
             "position": {"label": "Centre-Back", "key": "CB"},
             "transferDate": "2026-08-10T00:00:00Z",
             "fromClub": "Bologna", "fromClubId": 12, "toClub": "Roma", "toClubId": 1,
             "fee": {"feeText": "fee", "localizedFeeText": "transfer_fee", "value": "€18.5M"},
             "transferType": {"text": "transfer", "localizationKey": "transfer"},
             "marketValue": "€25M", "onLoan": False, "contractExtension": False},
            {"name": "Arrivo In Prestito", "playerId": 112,
             "position": {"label": "Keeper", "key": "GK"},
             "transferDate": "2026-08-02T00:00:00Z",
             "fromClub": "Torino", "fromClubId": 13, "toClub": "Roma", "toClubId": 1,
             "fee": {"feeText": "on loan", "localizedFeeText": "on_loan"},
             "transferType": {"text": "on loan", "localizationKey": "on_loan"},
             "onLoan": True},
        ],
        "Players out": [
            {"name": "Partenza Libera", "playerId": 113,
             "position": {"label": "Striker", "key": "ST"},
             "transferDate": "2026-07-20T00:00:00Z",
             "fromClub": "Roma", "fromClubId": 1, "toClub": "Cagliari", "toClubId": 14,
             "fee": {"feeText": "free transfer", "localizedFeeText": "transfer_type_free_transfer"},
             "transferType": {"text": "free transfer", "localizationKey": "free_transfer"}},
        ],
        "Contract extension": [
            {"name": "Capitano Rinnovato", "playerId": 114, "contractExtension": True,
             "fromClub": "Roma", "fromClubId": 1, "toClub": "Roma", "toClubId": 1,
             "transferType": {"text": "contract", "localizationKey": "contract"}},
        ],
    },
    "allTransfers": [],   # con `data` piena non serve: il parser preferisce la fonte esplicita
    "allRumours": [{"name": "Voce Di Mercato"}, {"name": "Altra Voce"}],
}}

# stessa sezione senza `data`: la direzione si calcola da ourTeamId e from/toClubId
RAW_ALL_TRANSFERS = {"transfers": {
    "type": "team",
    "ourTeamId": "1",     # può arrivare come stringa: il confronto è tollerante
    "allTransfers": [
        {"name": "Arrivo Dalla Lista", "fromClub": "Fiorentina", "fromClubId": 15,
         "toClub": "Roma", "toClubId": 1, "transferDate": "2026-08-15",
         "fee": {"value": "Free"}, "transferType": {"text": "free transfer"}},
        {"name": "Partenza Dalla Lista", "fromClub": "Roma", "fromClubId": 1,
         "toClub": "Genoa", "toClubId": 16, "transferDate": "2026-08-16",
         "fee": {"value": "€9M"}, "transferType": {"text": "transfer"}},
        {"name": "Movimento Altrui", "fromClub": 20, "fromClubId": 20,
         "toClub": "Altra Squadra", "toClubId": 21, "transferDate": "2026-08-17"},
        {"name": "Rinnovo In Lista", "contractExtension": True,
         "fromClub": "Roma", "fromClubId": 1, "toClub": "Roma", "toClubId": 1},
    ],
    "allRumours": [{"name": "Solo Voce"}],
}}


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


def test_parse_transfers_disposizione_reale_run_20260916():
    """La forma misurata dal primo run con firma (docs/21 §17): data{«Players in»/«Players out»}."""
    diag: dict = {}
    rows = FotMobClient.parse_transfers(RAW_REALE, 1, "Roma", "ITA1", diag)
    # 2 arrivi + 1 partenza; il rinnovo e le voci di mercato NON sono movimenti in/out
    assert [r["direction"] for r in rows] == ["in", "in", "out"]
    a = rows[0]
    assert (a["player_name"], a["counterpart"], a["position"]) == ("Nuovo Acquisto", "Bologna", "Centre-Back")
    assert a["fee_text"] == "€18.5M" and a["transfer_type"] == "transfer"
    assert a["date"].startswith("2026-08-10")
    prestito = rows[1]
    assert prestito["fee_text"] == "prestito" and prestito["transfer_type"] == "on loan"
    out_row = rows[2]
    assert out_row["counterpart"] == "Cagliari"          # partenza: controparte = dove va
    assert out_row["fee_text"] == "gratuito"             # chiave di localizzazione tradotta
    assert not any(r["player_name"] == "Capitano Rinnovato" for r in rows)   # rinnovo mai pubblicato
    # firma e imbuto: la sezione dice quale disposizione ha vinto, i campi di data e della
    # voce finiscono nella firma (solo nomi), rinnovi e voci di mercato sono contati
    assert diag["sezione"] == "dict/data"
    assert "Players in" in diag["campi_data"] and "Players out" in diag["campi_data"]
    assert "name" in diag["campi_voce"] and "fromClubId" in diag["campi_voce"]
    assert diag["voci"] == 3 and diag["righe"] == 3 and diag["rinnovi"] == 1 and diag["voci_mercato"] == 2


def test_parse_transfers_all_transfers_con_direzione_da_our_team_id():
    """Senza `data`, la lista piatta `allTransfers` dà la direzione: toClubId == ourTeamId → arrivo."""
    diag: dict = {}
    rows = FotMobClient.parse_transfers(RAW_ALL_TRANSFERS, 1, "Roma", "ITA1", diag)
    by_name = {r["player_name"]: r for r in rows}
    assert set(by_name) == {"Arrivo Dalla Lista", "Partenza Dalla Lista"}
    assert by_name["Arrivo Dalla Lista"]["direction"] == "in"
    assert by_name["Arrivo Dalla Lista"]["counterpart"] == "Fiorentina"
    assert by_name["Arrivo Dalla Lista"]["fee_text"] == "gratuito"    # «Free» → italiano
    assert by_name["Partenza Dalla Lista"]["direction"] == "out"
    assert by_name["Partenza Dalla Lista"]["counterpart"] == "Genoa"
    # il movimento che non coinvolge la squadra resta fuori (contato, mai inventato);
    # il rinnovo in lista è contato come rinnovo, non pubblicato come movimento
    assert diag["voci"] == 4 and diag["righe"] == 2
    assert diag["senza_direzione"] == 1 and diag["rinnovi"] == 1
    assert diag["sezione"] == "dict/allTransfers" and diag["voci_mercato"] == 1


def test_collect_transfers_imbuto_reale(tmp_path):
    """Il collettore con la disposizione reale pubblica righe e il detail con rinnovi/voci."""
    st = Store(tmp_path / "mercato4")
    st.write("fotmob_standings", STANDINGS)

    class _RealFotMob:
        def __init__(self):
            self.requests = 0
            self.http = type("H", (), {"stats": self, "mark": lambda s: self.requests})()

        def team_raw(self, team_id: int) -> dict:
            self.requests += 1
            return RAW_REALE if team_id == 1 else {"transfers": {"type": "team", "data": {}}}

    report = collect_transfers(st, fotmob=_RealFotMob())
    riga = st.read("source_status").query("source == 'transfers:TRANSFERS'").iloc[0]
    assert riga["rows"] == 3                                     # 2 arrivi + 1 partenza di Roma
    assert "rinnovi 1" in riga["detail"] and "voci di mercato 2" in riga["detail"]
    assert "dict/data in 1" in riga["detail"]                    # disposition dichiarata
    assert "campi data" in riga["digest"] and "campi voce" in riga["digest"]
    assert report.requests == {"transfers": 2}
    st.close()


def test_summer_market_con_disposizione_reale(tmp_path):
    """End-to-end: righe dal payload reale → card con fee e tipi in italiano."""
    st = Store(tmp_path / "mercato5")
    rows = FotMobClient.parse_transfers(RAW_REALE, 1, "Roma", "ITA1")
    st.write("transfers", pd.DataFrame(rows))
    an = MatchAnalysis(st)
    mk = an.summer_market(1)
    assert mk is not None and mk["n_in"] == 2 and mk["n_out"] == 1
    a0 = mk["arrivals"][0]                                       # data desc: 10/08 prima del 02/08
    assert a0["name"] == "Nuovo Acquisto" and a0["fee"] == "€18.5M"
    assert a0["type_it"] == "titolo definitivo" and a0["date_it"] == "10/08/2026"
    assert mk["arrivals"][1]["type_it"] == "prestito"            # «on loan» → italiano
    assert mk["departures"][0]["type_it"] == "gratuito" and mk["departures"][0]["fee"] == "gratuito"
    st.close()


class _StubFotMob:
    """Solo le chiamate: Roma risponde, Inter esplode (una fonte rotta non ferma il run)."""

    def __init__(self):
        # come un client vero: il contatore parte da zero e sale a ogni richiesta. Da
        # quando `source_status` registra le richieste **della fase** (non il cumulativo
        # del client condiviso), uno stub fermo a un numero fisso farebbe leggere 0.
        self.requests = 0
        self.http = type("H", (), {"stats": self, "mark": lambda s: self.requests})()

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
