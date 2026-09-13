from datetime import datetime, timedelta, timezone

from fda.site.audit import audit_match


def _ctx(days, **values):
    c = {"match_id": 1, "utc_kickoff": datetime.now(timezone.utc) + timedelta(days=days)}
    c.update(values)
    return c


def test_audit_distinguishes_not_yet_published_from_real_missing():
    # a 5 giorni dalla gara formazioni/arbitro/meteo non sono ancora pubblicati: «attesi», non buchi.
    # La previsione invece dipende solo da noi (`fda predict --days-ahead 0` copre tutto il
    # calendario): se manca è «mancante», altrimenti il buco sparisce dal conto.
    early = audit_match(_ctx(5))
    assert early["atteso"] > 0
    stati = {i["key"]: i["state"] for i in early["items"]}
    assert stati["prediction"] == "mancante"
    assert stati["referee"] == "atteso" and stati["weather"] == "atteso"
    assert early["mancante"] == 1                              # solo la previsione

    late = audit_match(_ctx(1))
    assert late["mancante"] > early["mancante"]
    assert late["atteso"] < early["atteso"]


def test_prediction_mai_attesa_qualunque_sia_l_anticipo():
    """Con l'orizzonte esteso non esiste una finestra in cui la previsione è «legittimamente» assente."""
    for giorni in (0.5, 3, 7, 40, 200):
        stati = {i["key"]: i["state"] for i in audit_match(_ctx(giorni))["items"]}
        assert stati["prediction"] == "mancante"
    presente = audit_match(_ctx(200, prediction={"p_home": 0.4}))
    assert {i["key"]: i["state"] for i in presente["items"]}["prediction"] == "presente"


def test_audit_does_not_treat_empty_collections_as_present():
    result = audit_match(_ctx(0.5, home_starters=[], away_starters=[{"name": "Player"}]))
    states = {item["key"]: item["state"] for item in result["items"]}
    assert states["home_starters"] == "mancante"
    assert states["away_starters"] == "presente"


def test_nessun_indisponibile_con_distinta_pubblicata_non_e_un_buco():
    """«Nessuno è fuori» è un'informazione completa, non un dato mancante.

    Misurato sulla build 2026-09-13: 4 squadre su 105 schede (Telstar, Excelsior, PSG,
    Moreirense) avevano la distinta con 11 nomi e nessuna assenza segnalata, e finivano
    contate come campo mancante in `stato.html`.
    """
    con_distinta = audit_match(_ctx(1, home_starters=[{"name": "Portiere"}], home_unavailable=[]))
    stati = {i["key"]: i["state"] for i in con_distinta["items"]}
    assert stati["home_unavailable"] == "presente"

    # a calcio d'inizio ormai aperto la finestra della fonte è scaduta: il buco è nostro
    senza_distinta = audit_match(_ctx(0, home_starters=[], home_unavailable=[]))
    stati = {i["key"]: i["state"] for i in senza_distinta["items"]}
    assert stati["home_unavailable"] == "mancante"       # qui il buco è vero: distinta non raccolta

    # la finestra della fonte resta valida per l'altra squadra: distinta assente → «atteso»
    futuro = audit_match(_ctx(5, home_starters=[], home_unavailable=[]))
    assert {i["key"]: i["state"] for i in futuro["items"]}["home_unavailable"] == "atteso"
