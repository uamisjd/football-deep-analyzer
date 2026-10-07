"""Test offline del blocco mercato (docs/21 P2-7, rifatto in docs/24 §4): parser FotMob
`teams.transfers`, collettore isolato e card «Mercato: arrivi e partenze» con finestra
ricavata dai dati, importi leggibili e collegamento con la distinta della partita."""

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


def _transfers(rows):
    """Righe della tabella `transfers` per la squadra 1 (Roma), con date già utc."""
    base = {"team_id": 1, "team_name": "Roma", "league_code": "ITA1", "position": "",
            "counterpart": "", "direction": "in", "fee_text": "", "transfer_type": "",
            "date": "2026-08-01T00:00:00Z"}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_transfer_window_finestra_ricavata_dai_dati(tmp_path):
    """La finestra è ricavata dai dati, non dall'agenda: i movimenti della stagione
    precedente (gennaio 2026) non entrano nella card della finestra in corso."""
    from datetime import UTC, datetime, timedelta
    oggi = datetime.now(UTC)
    st = Store(tmp_path / "mercato_finestra")
    st.write("transfers", _transfers([
        {"player_name": "Colpo Grosso", "direction": "in", "fee_text": "30000000",
         "date": (oggi - timedelta(days=3)).isoformat()},
        {"player_name": "Altro Arrivo", "direction": "in", "fee_text": "1000000",
         "date": (oggi - timedelta(days=15)).isoformat()},
        # il buco: nessun movimento per 5 mesi → la finestra vecchia resta fuori
        {"player_name": "Vecchio Di Gennaio", "direction": "in", "fee_text": "9000000",
         "date": (oggi - timedelta(days=200)).isoformat()},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1)
    assert mk["n_in"] == 2 and mk["n_out"] == 0               # gennaio escluso
    assert [a["name"] for a in mk["arrivals"]] == ["Colpo Grosso", "Altro Arrivo"]
    assert mk["window_end"] == (oggi - timedelta(days=3)).strftime("%d/%m/%Y")
    assert mk["window_start"] == (oggi - timedelta(days=15)).strftime("%d/%m/%Y")
    st.close()


def test_transfer_window_ordina_per_importo_pubblicato(tmp_path):
    """Ordine per importo pubblicato (a parità, il più recente): il colpo non resta fuori."""
    from datetime import UTC, datetime, timedelta
    oggi = datetime.now(UTC)
    st = Store(tmp_path / "mercato_ordine")
    st.write("transfers", _transfers([
        {"player_name": "Firma Di Ieri", "fee_text": "", "date": (oggi - timedelta(days=1)).isoformat()},
        {"player_name": "Colpo Da 30", "fee_text": "30000000", "date": (oggi - timedelta(days=20)).isoformat()},
        {"player_name": "Prestito", "fee_text": "prestito", "date": (oggi - timedelta(days=5)).isoformat()},
        {"player_name": "Gratuito", "fee_text": "gratuito", "date": (oggi - timedelta(days=6)).isoformat()},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1)
    # importo pubblicato decrescente; senza importo, il più recente prima
    assert [a["name"] for a in mk["arrivals"]] == ["Colpo Da 30", "Firma Di Ieri", "Prestito", "Gratuito"]
    assert mk["arrivals"][0]["fee"] == "30 M€"
    assert mk["arrivals"][1]["fee"] == "importo non noto"     # mai un numero inventato
    assert mk["arrivals"][3]["fee"] == "gratuito"
    assert mk["importi_noti"] == 1 and mk["importi_mancanti"] == 3
    assert mk["spesa"] == 30000000.0 and mk["saldo"] == 30000000.0
    st.close()


def test_transfer_window_stantio_dichiara_l_ultimo_movimento(tmp_path):
    """Se la fonte non pubblica movimenti recenti la card lo dice invece di sparire."""
    from datetime import UTC, datetime, timedelta
    vecchia = datetime.now(UTC) - timedelta(days=200)
    st = Store(tmp_path / "mercato_stantio")
    st.write("transfers", _transfers([
        {"player_name": "Movimento Vecchio", "fee_text": "1000000", "date": vecchia.isoformat()},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1)
    assert mk["stale"] is True and mk["n_in"] == 0
    assert mk["ultimo"] == vecchia.strftime("%d/%m/%Y")
    st.close()


def test_transfer_window_fee_da_testo_della_fonte():
    """Importi e formule: numeri leggibili, inglese mai a schermo, nulla inventato."""
    assert MatchAnalysis.fee_it("21250000") == "21,2 M€"
    assert MatchAnalysis.fee_it("850000") == "850 k€"
    assert MatchAnalysis.fee_it("900") == "900 €"
    assert MatchAnalysis.fee_it("") == "importo non noto"
    assert MatchAnalysis.fee_it("undisclosed") == "importo non noto"
    assert MatchAnalysis.fee_it("Prestito") == "prestito"
    assert MatchAnalysis.fee_it("free transfer") == "gratuito"
    assert MatchAnalysis.fee_eur("prestito") is None and MatchAnalysis.fee_eur("") is None
    assert MatchAnalysis.fee_eur("1,5 M") == 1500000.0


def test_fee_it_accetta_anche_importi_numerici() -> None:
    """Valori già numerici (valore di mercato dei giocatori), non solo testo della fonte.

    Il difetto corretto in `docs/43` §3 era un arrotondamento a parte: `|it_num` senza
    decimali, quindi 73.728 € diventava «€0M» su 845 schede. Ogni importo passa da
    `fee_it`, che sotto il milione usa i «k€» invece di stampare zero.
    """
    assert MatchAnalysis.fee_it(73_728) == "74 k€"
    assert MatchAnalysis.fee_it(499_999) == "500 k€"
    assert MatchAnalysis.fee_it(850_000) == "850 k€"
    assert MatchAnalysis.fee_it(2_250_000) == "2,2 M€"
    assert MatchAnalysis.fee_it(12_500_000) == "12,5 M€"
    assert MatchAnalysis.fee_it(148_000_000) == "148 M€"
    # nessun importo pubblicato è mai «0»: sotto i mille euro si scrive l'importo per intero
    assert MatchAnalysis.fee_it(500) == "500 €"
    assert "0 M€" not in MatchAnalysis.fee_it(1)


def test_transfer_window_senza_tabella(tmp_path):
    st = Store(tmp_path / "mercato_vuoto")
    an = MatchAnalysis(st)
    assert an.transfer_window(1) is None                      # tabella mai raccolta → None
    st.close()


def test_arrivi_gia_in_distinta(tmp_path):
    """Il collegamento che mancava: quali arrivi sono già nella distinta di questa partita."""
    from datetime import UTC, datetime, timedelta
    oggi = datetime.now(UTC)
    st = Store(tmp_path / "mercato_distinta")
    st.write("transfers", _transfers([
        {"player_name": "Nuovo Acquisto", "fee_text": "18000000",
         "date": (oggi - timedelta(days=10)).isoformat()},
        {"player_name": "Sconosciuto", "fee_text": "", "date": (oggi - timedelta(days=10)).isoformat()},
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 4, "team_id": 1, "player_id": 111, "player_name": "Nuovo Acquisto",
         "role": "starter", "market_value_eur": 25000000.0},
        {"match_id": 4, "team_id": 1, "player_id": 112, "player_name": "Titolare Storico",
         "role": "sub", "market_value_eur": 1000000.0},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1, match_id=4)
    assert [p["name"] for p in mk["in_campo"]] == ["Nuovo Acquisto"]
    assert mk["in_campo"][0]["status"] == "titolare"
    assert an.transfer_window(1, match_id=99)["in_campo"] == []   # nessuna distinta → nessuna riga
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




# ---------------------------------------------------------------------------------------------
# Difetto misurato il 2026-10-07 (docs/56 §2): la card pubblicava ~2 volte i movimenti veri.
# Tre cause, tutte reali nei dati: la data in ora locale invece che UTC (1-2 ore di scarto),
# i diacritici scritti in due modi, e la stessa mossa ripubblicata con la data aggiornata.
# ---------------------------------------------------------------------------------------------


def test_transfer_window_stesso_movimento_con_ora_locale(tmp_path):
    """La fonte riscrive la stessa mossa con l'ora locale al posto dell'UTC: una riga sola.

    Forma reale (``transfers.parquet``, Santa Clara/Adriano): ``2026-02-04T16:03:14Z`` e
    ``2026-02-04T17:03:14`` — stesso movimento, un'ora di scarto, e la seconda data **senza
    la Z** che il vecchio parser azzerava in silenzio (il movimento spariva del tutto).
    """
    from datetime import UTC, datetime, timedelta
    # ora fissa a metà mattina: con «adesso» dopo le 22 UTC il +2h dell'ora locale cade nel
    # giorno dopo e l'atteso (la data di `quando`) non regge — flake trovato il 2026-10-07
    # alle 22:06 UTC, non un difetto del codice
    quando = (datetime.now(UTC) - timedelta(days=2)).replace(hour=10, minute=0, second=0,
                                                            microsecond=0)
    utc = quando.strftime("%Y-%m-%dT%H:%M:%SZ")
    locale = (quando + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")     # ora locale, senza Z
    st = Store(tmp_path / "mercato_ora")
    st.write("transfers", _transfers([
        {"player_name": "Adriano", "direction": "out", "counterpart": "Wuhan Three Towns",
         "date": utc},
        {"player_name": "Adriano", "direction": "out", "counterpart": "Wuhan Three Towns",
         "date": locale},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1)
    assert mk["n_out"] == 1
    assert [t["name"] for t in mk["departures"]] == ["Adriano"]
    # la data senza Z è leggibile (prima era NaT: il movimento non entrava nella finestra)
    assert mk["window_end"] == quando.strftime("%d/%m/%Y")
    st.close()


def test_transfer_window_stesso_movimento_con_diacritici_diversi(tmp_path):
    """``Aleksić``/``Aleksic`` sono lo stesso giocatore: una riga, non due."""
    from datetime import UTC, datetime, timedelta
    quando = datetime.now(UTC) - timedelta(days=4)
    st = Store(tmp_path / "mercato_diacritici")
    st.write("transfers", _transfers([
        {"player_name": "Aleksa Aleksić", "direction": "in", "counterpart": "Sarajevo",
         "date": quando.strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"player_name": "Aleksa Aleksic", "direction": "in", "counterpart": "Sarajevo",
         "date": (quando + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1)
    assert mk["n_in"] == 1 and len(mk["arrivals"]) == 1
    st.close()


def test_transfer_window_movimenti_diversi_restano_due(tmp_path):
    """Due movimenti dello stesso giocatore verso club diversi restano due righe.

    Misurato: nel finestra attuale non c'è nessun caso così (0 su 132 club), ma la regola
    non li nasconde — la soglia di ri-pubblicazione (30 giorni) e quella sui duplicati
    (3 ore) non li toccano.
    """
    from datetime import UTC, datetime, timedelta
    oggi = datetime.now(UTC)
    st = Store(tmp_path / "mercato_due")
    # i movimenti di riempimento tengono la finestra concatenata (fra due movimenti della
    # squadra non devono passare più di 21 giorni), così le due righe del giocatore cadono
    # nella stessa finestra
    righe = [{"player_name": "Doppio Prestito", "direction": "out", "counterpart": "Mantova",
              "date": (oggi - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")}]
    for i, gg in enumerate((50, 40, 30, 20)):
        righe.append({"player_name": f"Riempimento {i}", "direction": "out",
                      "counterpart": "Altro Club",
                      "date": (oggi - timedelta(days=gg)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    righe.append({"player_name": "Doppio Prestito", "direction": "out", "counterpart": "Rijeka",
                  "date": (oggi - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    st.write("transfers", _transfers(righe))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1, n=10)          # tutti i movimenti, non solo i primi 4
    doppio = [t for t in mk["departures"] if t["name"] == "Doppio Prestito"]
    assert len(doppio) == 2
    assert {t["counterpart"] for t in doppio} == {"Mantova", "Rijeka"}
    st.close()


def test_transfer_window_una_riga_per_giocatore(tmp_path):
    """La mossa ripubblicata con la **data aggiornata** resta una riga: vince l'ultima versione.

    Caso reale (Braga/Sporting CP, Zalazar): 30/06 e 13/07, stesso importo pubblicato. Il
    lettore vede un movimento, con la data e l'importo della versione più recente.
    """
    from datetime import UTC, datetime, timedelta
    oggi = datetime.now(UTC)
    st = Store(tmp_path / "mercato_ripubblicato")
    st.write("transfers", _transfers([
        {"player_name": "Rodrigo Zalazar", "direction": "out", "counterpart": "Sporting CP",
         "fee_text": "30000000", "date": (oggi - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        {"player_name": "Rodrigo Zalazar", "direction": "out", "counterpart": "Sporting CP",
         "fee_text": "30000000", "date": (oggi - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")},
    ]))
    an = MatchAnalysis(st)
    mk = an.transfer_window(1)
    assert mk["n_out"] == 1
    assert mk["departures"][0]["date_it"] == (oggi - timedelta(days=2)).strftime("%d/%m/%Y")
    assert mk["departures"][0]["fee"] == "30 M€"
    assert mk["incasso"] == 30000000.0
    st.close()


def test_upsert_transfers_riconosce_lo_stesso_movimento(tmp_path):
    """L'upsert non deve creare una seconda riga per la stessa mossa riscritta dalla fonte.

    Misurato sui Parquet committati: 2.919 righe in più su 11.624 con la vecchia chiave. Qui
    la seconda scrittura ha l'ora locale al posto dell'UTC **e** il nome senza diacritici:
    deve sostituire la prima, non aggiungersi.
    """
    st = Store(tmp_path / "mercato_upsert")
    st.upsert("transfers", _transfers([
        {"player_name": "Aleksa Aleksić", "direction": "in", "counterpart": "Sarajevo",
         "date": "2026-08-20T09:00:00Z"},
    ]))
    st.upsert("transfers", _transfers([
        {"player_name": "Aleksa Aleksic", "direction": "in", "counterpart": "Sarajevo",
         "date": "2026-08-20T11:00:00"},
    ]))
    salvate = st.read("transfers")
    assert len(salvate) == 1
    assert str(salvate.iloc[0]["player_name"]) == "Aleksa Aleksic"   # l'ultima versione
    st.close()


def test_parse_moments_legge_i_due_formati():
    """``parse_moments`` legge le date con e senza ``Z``; una data vuota resta NaT, non zero."""
    from fda.site.analysis import parse_moments
    s = pd.Series(["2026-08-11T06:47:30Z", "2026-08-11T08:47:30", "", None])
    out = parse_moments(s)
    assert out.notna().sum() == 2
    assert out.iloc[0] == pd.Timestamp("2026-08-11T06:47:30Z")
    assert out.iloc[1] == pd.Timestamp("2026-08-11T08:47:30Z")
    assert pd.isna(out.iloc[2]) and pd.isna(out.iloc[3])


def test_dedup_transfers_dati_reali_del_difetto():
    """Sulle righe reali del difetto: 11.624 → una riga per movimento (nessun doppione)."""
    from fda.site.analysis import dedup_transfers
    df = pd.DataFrame([
        # Santa Clara / Adriano: UTC e ora locale (una riga senza Z)
        {"team_id": 1, "direction": "out", "player_name": "Adriano",
         "counterpart": "Wuhan Three Towns", "fee_text": "", "date": "2026-02-04T16:03:14Z"},
        {"team_id": 1, "direction": "out", "player_name": "Adriano",
         "counterpart": "Wuhan Three Towns", "fee_text": "", "date": "2026-02-04T17:03:14"},
        # Atalanta / Djimsiti: tre righe, controparte anche scritta in due modi
        {"team_id": 2, "direction": "out", "player_name": "Berat Djimsiti",
         "counterpart": "Al Diriyah", "fee_text": "3000000", "date": "2026-08-11T06:47:30Z"},
        {"team_id": 2, "direction": "out", "player_name": "Berat Djimsiti",
         "counterpart": "Al Diriyah", "fee_text": "3000000", "date": "2026-08-11T08:47:30"},
        {"team_id": 2, "direction": "out", "player_name": "Berat Djimsiti",
         "counterpart": "Al-Diraiyah", "fee_text": "3000000", "date": "2026-08-11T08:47:30Z"},
    ])
    out = dedup_transfers(df)
    # primo livello: le righe a 1-2 ore l'una dall'altra sono la stessa mossa → una sola
    # per squadra (Adriano) e due per Djimsiti, perché la controparte è scritta anche
    # «Al-Diraiyah»: quel caso lo chiude il secondo livello, per giocatore, in
    # ``transfer_window`` (vedi ``test_transfer_window_una_riga_per_giocatore``)
    assert len(out) == 3
    assert set(out[out.team_id == 1].player_name) == {"Adriano"}
    assert set(out[out.team_id == 2].fee_text.astype(str)) == {"3000000"}
