"""Pagina pubblica «Laboratorio»: verdetti derivati dal Parquet, criterio docs/13 §6.5."""

import pandas as pd

from fda.site.lab_page import lab_leaderboard, verdict

LEAGUES = ["ENG1", "ESP1", "FRA1", "GER1", "ITA1", "NED1", "POR1"]


def test_verdict_regole_del_criterio():
    assert verdict(None, None, None, 0, 7, baseline=True) == "riferimento"
    # passa: IC interamente negativo e ≥5 campionati migliori
    assert verdict(-0.001, -0.002, -0.0001, 7, 7, False).startswith("passa il criterio")
    # IC negativo ma solo in 1 campionato: plurale corretto
    assert verdict(-0.0004, -0.0007, -0.00004, 1, 7, False) == \
        "migliore in media, ma solo in 1 campionato su 7"
    # IC che attraversa lo zero
    assert verdict(0.00005, -0.0003, 0.0004, 3, 7, False) == "non distinguibile dalla produzione"
    # peggiore: IC interamente positivo
    assert verdict(0.002, 0.001, 0.003, 0, 7, False) == "peggiore della produzione"
    assert verdict(None, None, None, 0, 7, False) == "dato insufficiente"


def _frame(rows_all, rps_by_league):
    recs = []
    for cand, label, n, rps, delta, lo, hi in rows_all:
        recs.append({"candidate": cand, "league_key": "ALL", "label": label, "n": n, "rps": rps,
                     "logloss": 1.0, "delta_rps": delta, "delta_rps_lo95": lo, "delta_rps_hi95": hi})
    for cand, per in rps_by_league.items():
        for lg, v in zip(LEAGUES, per):
            recs.append({"candidate": cand, "league_key": lg, "label": None, "n": 100, "rps": v,
                         "logloss": None, "delta_rps": None, "delta_rps_lo95": None,
                         "delta_rps_hi95": None})
    return pd.DataFrame(recs)


def test_leaderboard_ordina_e_conta_i_passaggi():
    base = [0.20] * 7
    better = [0.199] * 7           # migliore in 7/7, IC negativo
    worse = [0.201] * 7
    df = _frame(
        [("dc_elo_prod", "Produzione", 3157, 0.2000, None, None, None),
         ("var_buona", "Variante buona", 3157, 0.1990, -0.001, -0.0015, -0.0002),
         ("var_peggio", "Variante peggio", 3157, 0.2010, 0.001, 0.0005, 0.0015)],
        {"dc_elo_prod": base, "var_buona": better, "var_peggio": worse},
    )
    r = lab_leaderboard(df)
    assert r is not None
    assert r["n_candidates"] == 3 and r["n_passes"] == 1 and r["n_eval"] == 3157
    # il riferimento (produzione) è in cima; le varianti seguono dalla migliore
    assert r["rows"][0]["baseline"] and r["rows"][1]["candidate"] == "var_buona"
    buona = r["rows"][1]
    assert buona["leagues_better"] == 7 and buona["passes"]
    assert r["rows"][-1]["verdict"] == "peggiore della produzione"
    assert buona["verdict"] == "passa il criterio, non promosso"
    base_row = next(x for x in r["rows"] if x["baseline"])
    assert base_row["delta"] is None and base_row["verdict"] == "riferimento"
    assert r["detail_keys"][0] == "dc_elo_prod" and len(r["detail"]) == 7


def test_leaderboard_senza_riferimento_o_dati_torna_none():
    assert lab_leaderboard(pd.DataFrame()) is None
    assert lab_leaderboard(None) is None
    df = _frame([("solo_variante", "x", 10, 0.2, -0.001, -0.002, 0.0)], {})
    assert lab_leaderboard(df) is None


def test_campionato_senza_rps_non_conta_come_migliore():
    """Un campionato senza RPS non entra né nel conteggio né nel confronto."""
    df = _frame([("dc_elo_prod", "Produzione", 100, 0.2, None, None, None),
                 ("v", "V", 100, 0.2, 0.0, -0.001, 0.001)],
                {"dc_elo_prod": [0.20] * 7, "v": [0.19] * 6 + [float("nan")]})
    r = lab_leaderboard(df)
    v = next(x for x in r["rows"] if x["candidate"] == "v")
    assert v["leagues_better"] == 6          # 6 campionati migliori, il 7º escluso
    assert v["n_leagues"] == 7


def test_etichetta_pubblica_senza_rimandi_ai_documenti():
    from fda.site.lab_page import public_label
    assert public_label("γ-sharpening 1,12 sul rapporto λ (respinto, docs/19 §1.3)") == \
        "γ-sharpening 1,12 sul rapporto λ (respinto)"
    assert public_label("Temperatura 1X2 τ 1,16 (T ≈ 0,86 de-piattimento, docs/48)") == \
        "Temperatura 1X2 τ 1,16 (T ≈ 0,86 de-piattimento)"
    assert "docs/" not in public_label("Elo (docs/13 §6.5)")
