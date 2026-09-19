"""Test del catalogo giocatori (fase 3 — docs/07_fase3_giocatori.md).

Numeri piccoli e verificabili a mano: aggregazioni per 90, soglia minuti dei
percentili, capovolgimento delle statistiche «lower is better», geometria del
radar, V/N/P del log partite e pagine costruite con segnaposto onesti.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fda.site.build import SiteBuilder
from fda.site.players import MIN_MINUTES, MIN_PEERS, POSITION_LABELS, PlayerCatalog
from fda.store import Store


def _store(tmp_path, lineup=None, player_stats=None, fixtures=None):
    st = Store(tmp_path / "processed")
    st.write("lineup", pd.DataFrame(lineup or []))
    st.write("player_stats", pd.DataFrame(player_stats or []))
    st.write("fixtures", pd.DataFrame(fixtures or []))
    return st


FX = [
    # match 1: A1 (10) in casa vs B (20), 2-1
    {"match_id": 1, "league_id": 55, "utc_kickoff": "2026-09-01", "home_id": 10,
     "away_id": 20, "home_name": "Alfa", "away_name": "Beta", "home_goals": 2,
     "away_goals": 1, "status": "finished", "season": "2026/2027", "round": 1,
     "home_id_fix": None},
    # match 2: A1 in trasferta vs B, 0-0
    {"match_id": 2, "league_id": 55, "utc_kickoff": "2026-09-08", "home_id": 20,
     "away_id": 10, "home_name": "Beta", "away_name": "Alfa", "home_goals": 0,
     "away_goals": 0, "status": "finished", "season": "2026/2027", "round": 2,
     "home_id_fix": None},
]


def _lineup_row(match_id, team_id, player_id, name, pos, role="starter", **kw):
    row = {"match_id": match_id, "team_id": team_id, "player_id": player_id,
           "player_name": name, "role": role, "shirt_number": None,
           "position_id": None, "usual_position_id": pos, "age": kw.get("age", 25),
           "country": kw.get("country", "ITA"), "market_value_eur": kw.get("market_value_eur"),
           "rating": kw.get("rating"), "season_rating": kw.get("season_rating"),
           "is_captain": kw.get("is_captain", False), "unavailability_type": kw.get("unavail"),
           "expected_return": kw.get("ret")}
    return row


def _ps_row(match_id, team_id, player_id, key, value, total=None):
    return {"match_id": match_id, "team_id": team_id, "player_id": player_id,
            "player_name": "x", "key": key, "value": value, "total": total}


def test_position_labels():
    assert POSITION_LABELS[0] == "Portiere" and POSITION_LABELS[3] == "Attaccante"


def test_aggregazione_per90_e_zero_eventi(tmp_path):
    """Gol = 1+0, minuti = 90+45 → per90 0,667; chiave assente = 0 (non inventato)."""
    lineup = [
        _lineup_row(1, 10, 101, "A1", 3), _lineup_row(2, 10, 101, "A1", 3),
        _lineup_row(1, 10, 102, "A2", 3),  # una sola gara, 0 gol → per90 0
    ]
    ps = [
        _ps_row(1, 10, 101, "minutes_played", 90), _ps_row(1, 10, 101, "goals", 1),
        _ps_row(1, 10, 101, "expected_goals", 0.5), _ps_row(1, 10, 101, "rating_title", 7.0),
        _ps_row(2, 10, 101, "minutes_played", 45), _ps_row(2, 10, 101, "rating_title", 8.0),
        _ps_row(1, 10, 102, "minutes_played", 90),
    ]
    st = _store(tmp_path, lineup, ps, FX)
    cat = PlayerCatalog(st)
    p = cat.players.loc[101]
    assert p["matches"] == 2 and p["minutes"] == 135
    # media voto ponderata sui minuti: (7*90 + 8*45)/135 = 7,(3)
    assert abs(p["rating"] - (7 * 90 + 8 * 45) / 135) < 1e-9
    assert cat._vals.loc[101, "goals"] == 1
    assert abs(cat._per90.loc[101, "goals"] - 90 / 135) < 1e-9
    # A2: nessuna riga gol → 0 eventi, per90 = 0
    assert cat._vals.loc[102, "goals"] == 0 and cat._per90.loc[102, "goals"] == 0
    st.close()


def test_percentili_soglia_minuti_e_peers(tmp_path):
    """Sotto 90' niente percentile; con pochi pari-ruolo (peer test) → n.d. onesto."""
    lineup, ps = [], []
    # 10 attaccanti (pos 3) con ≥90' → popolazione valida; l'11° con 45' → escluso
    for i in range(1, 12):
        lineup.append(_lineup_row(1, 10, 1000 + i, f"P{i}", 3))
        mins = 45 if i == 11 else 90
        ps.append(_ps_row(1, 10, 1000 + i, "minutes_played", mins))
        ps.append(_ps_row(1, 10, 1000 + i, "goals", i % 3))  # 0..2 gol
    st = _store(tmp_path, lineup, ps, FX)
    cat = PlayerCatalog(st)
    row_ok = cat._stat_row("goals", 1001)   # 1 gol (i=1)
    row_no = cat._stat_row("goals", 1011)   # 45' → non idoneo
    assert row_ok["pct"] is not None and row_ok["peers"] == 10
    assert row_no["pct"] is None
    # chi ha più gol ha percentile più alto (i=2 → 2 gol; i=1 → 1 gol)
    assert cat._stat_row("goals", 1002)["pct"] > cat._stat_row("goals", 1001)["pct"]
    # ratio senza denominatore → n.d., non 0
    assert cat._stat_row("pass_pct", 1001)["total"] == "—"
    st.close()


def test_percentile_lower_is_better_portiere(tmp_path):
    """Gol subiti: meno ne prendi, più alto il percentile (capovolto)."""
    lineup, ps = [], []
    for i in range(1, 11):
        lineup.append(_lineup_row(1, 10, 2000 + i, f"GK{i}", 0))
        ps.append(_ps_row(1, 10, 2000 + i, "minutes_played", 90))
        ps.append(_ps_row(1, 10, 2000 + i, "goals_conceded", i))  # GK1=1 ... GK10=10
    st = _store(tmp_path, lineup, ps, FX)
    cat = PlayerCatalog(st)
    gk1 = cat._stat_row("conceded", 2001)  # 1 gol subito
    gk10 = cat._stat_row("conceded", 2010)  # 10 gol subiti
    assert gk1["lower"] and gk1["pct"] > gk10["pct"]
    # rank(pct) 10 pari: GK1 = 0,1 → 10 → invertito 90; GK10 = 1,0 → 100 → invertito 0
    assert gk1["pct"] == 90 and gk10["pct"] == 0
    st.close()


def test_radar_geometria(tmp_path):
    """6 assi, poligono con 6 punti dentro il cerchio, anelli a 25/50/75/100."""
    lineup, ps = [], []
    for i in range(1, 11):
        lineup.append(_lineup_row(1, 10, 3000 + i, f"F{i}", 3))
        ps += [_ps_row(1, 10, 3000 + i, "minutes_played", 90),
               _ps_row(1, 10, 3000 + i, "goals", i),
               _ps_row(1, 10, 3000 + i, "expected_goals", i * 0.1),
               _ps_row(1, 10, 3000 + i, "expected_assists", i * 0.2),
               _ps_row(1, 10, 3000 + i, "total_shots", i),
               _ps_row(1, 10, 3000 + i, "ShotsOnTarget", i),
               _ps_row(1, 10, 3000 + i, "chances_created", i),
               _ps_row(1, 10, 3000 + i, "rating_title", 6.0 + i / 10)]
    st = _store(tmp_path, lineup, ps, FX)
    cat = PlayerCatalog(st)
    rd = cat.radar(3005)
    assert rd is not None and len(rd["axes"]) == 6 and len(rd["rings"]) == 4
    pts = [tuple(map(float, p.split(","))) for p in rd["poly"].split()]
    assert len(pts) == 6
    for x, y in pts:  # entro il cerchio di raggio 96 centrato in (160,150)
        assert (x - 160) ** 2 + (y - 150) ** 2 <= 96 ** 2 + 1e-6
    # un solo asse senza percentile → radar nullo (niente forme distorte)
    lineup.append(_lineup_row(1, 10, 3099, "Femme", 3))
    ps.append(_ps_row(1, 10, 3099, "minutes_played", 90))
    st2 = _store(tmp_path / "b", lineup, ps, FX)
    cat2 = PlayerCatalog(st2)
    assert cat2._stat_row("xg", 3099)["pct"] is not None  # 0 xG è un valore
    st.close()
    st2.close()


def test_log_partite_vnp_e_link(tmp_path):
    """V/N/P dal punto di vista della squadra del giocatore; link solo a pagine esistenti."""
    lineup = [_lineup_row(1, 10, 101, "A1", 3), _lineup_row(2, 10, 101, "A1", 3)]
    ps = [
        _ps_row(1, 10, 101, "minutes_played", 90), _ps_row(1, 10, 101, "goals", 2),
        _ps_row(1, 10, 101, "expected_goals", 1.2), _ps_row(1, 10, 101, "rating_title", 8.1),
        _ps_row(2, 10, 101, "minutes_played", 90), _ps_row(2, 10, 101, "expected_goals", 0.3),
        _ps_row(2, 10, 101, "rating_title", 6.5),
    ]
    st = _store(tmp_path, lineup, ps, FX)
    cat = PlayerCatalog(st)
    log = cat.match_log(101, built_ids={2})
    assert len(log) == 2
    assert log[0]["match_id"] == 2  # ordinato dalla più recente
    assert log[0]["res"] == "N" and log[0]["opponent"] == "Beta" and not log[0]["home"]
    assert log[0]["link"] is True and log[1]["link"] is False
    assert log[1]["res"] == "V" and log[1]["home"] is True and log[1]["goals"] == 2
    st.close()


def test_player_page_segnaposto_onesto(tmp_path):
    """0 minuti → niente tabelle/radar inventati, solo anagrafica e nota onesta."""
    lineup = [_lineup_row(1, 10, 501, "Riserva", 1, role="sub", unavail="Injured",
                          ret="Early October 2026")]
    st = _store(tmp_path, lineup, [], FX)
    cat = PlayerCatalog(st)
    page = cat.player_page(501, set())
    assert page is not None
    assert page["minutes"] == 0 and page["stats_table"] == [] and page["radar"] is None
    assert page["unavail"]["type"] == "Injured"
    assert page["eligible"] is False and page["n_players_league"] == 1
    st.close()


def test_minimi_dichiarati_nei_docs():
    assert MIN_MINUTES == 90 and MIN_PEERS == 8


def _store_con_pari(tmp_path):
    """Store con 8 attaccanti "pari" da 900′ (così il gruppo dei pari esiste) e due estremi:

    - ``A`` (player 900): 95′ e 6 tiri → rata grezza 5,68/90, campione piccolo (chiave ``total_shots``);
    - ``B`` (player 901): 900′ e 55 tiri → rata grezza 5,50/90, campione pieno.
    La stima li **ribalta**: A scende a ~4,6/90, B resta a ~5,2/90 (docs/19 §1.10).
    """
    lineup, ps = [], []
    for i in range(8):
        pid = 800 + i
        lineup.append(_lineup_row(1, 10, pid, f"Pari {i}", 3))
        ps += [_ps_row(1, 10, pid, "minutes_played", 900),
               _ps_row(1, 10, pid, "total_shots", 40),
               _ps_row(1, 10, pid, "goals", 8)]
    lineup.append(_lineup_row(1, 10, 900, "Piccolo campione", 3))
    ps += [_ps_row(1, 10, 900, "minutes_played", 95), _ps_row(1, 10, 900, "total_shots", 6)]
    lineup.append(_lineup_row(1, 10, 901, "Campione pieno", 3))
    ps += [_ps_row(1, 10, 901, "minutes_played", 900), _ps_row(1, 10, 901, "total_shots", 55)]
    return _store(tmp_path, lineup, ps, FX)


def test_stima_stabilizzata_ribalta_il_rumore_e_regge_il_campione_pieno(tmp_path):
    """La stima non è un abbellimento: cambia l'ordine dove il grezzo è rumore (docs/19 §1.10)."""
    cat = PlayerCatalog(_store_con_pari(tmp_path))
    grezzo_a = cat._per90.loc[900, "shots"]   # 5,68/90 grezzo
    grezzo_b = cat._per90.loc[901, "shots"]
    stima_a = cat._est.loc[900, "shots"]
    stima_b = cat._est.loc[901, "shots"]
    assert grezzo_a > grezzo_b                       # 6 tiri in 95′ battono 55 in 900′ grezzi
    assert stima_a < stima_b                         # la stima ribalta: il campione piccolo scende
    assert abs(grezzo_a - 90 * 6 / 95) < 1e-9 and abs(grezzo_b - 90 * 55 / 900) < 1e-9
    # il percentile pubblicato segue la stima, non il grezzo
    assert cat._pct.loc[900, "shots"] < cat._pct.loc[901, "shots"]


def test_scheda_giocatore_non_pubblica_rate_grezze_sotto_i_90_minuti(tmp_path):
    """«1′ e un tiro → 90,00 tiri/90» non deve più comparire in pagina (docs/19 §1.10)."""
    cat = PlayerCatalog(_store_con_pari(tmp_path))
    riga = cat._stat_row("shots", 900)                # 95′: rata pubblicata + stima accanto
    assert riga["insufficient"] is False and riga["est_visibile"] is True
    assert riga["per90"] == "5,68" and riga["est_s"] == "4,62"
    assert "media dei pari" in riga["est_note"] and "peso k=" in riga["est_note"]
    riga_piccola = cat._stat_row("shots", 800)        # 900′: nessuna stima accanto (non serve)
    assert riga_piccola["est_visibile"] is False and riga_piccola["per90"] == "4,00"


def _store_con_quote(tmp_path):
    """Store con 8 difensori da 900′ (80,0% di passaggi, 50,0% di duelli) e due estremi:

    - ``Spezzone`` (910): 45′, 22 passaggi riusciti su 25 tentativi (88,0% grezzo) e 2 duelli vinti su 3;
    - ``Pieno`` (911): 900′, 765 passaggi riusciti su 900 tentativi (85,0% grezzo) e 330 duelli vinti
      su 600 (55,0% grezzo).

    Per le quote il campione è il numero di **eventi**: ``k`` = 0,25 × 100 tentativi = 25 (passaggi)
    e 0,25 × 120 duelli = 30 (duelli), non un numero di minuti (docs/23 §2). La media del gruppo
    include chi la usa (è la media del gruppo, non "degli altri"): con 9 pari il peso è al più 1/10,
    ed è dichiarato nei docs.
    """
    lineup, ps = [], []
    for i in range(8):
        pid = 850 + i
        lineup.append(_lineup_row(1, 10, pid, f"Pari {i}", 1))
        ps += [_ps_row(1, 10, pid, "minutes_played", 900),
               _ps_row(1, 10, pid, "accurate_passes", 80, 100),
               _ps_row(1, 10, pid, "duel_won", 60), _ps_row(1, 10, pid, "duel_lost", 60)]
    lineup.append(_lineup_row(1, 10, 910, "Spezzone", 1))
    ps += [_ps_row(1, 10, 910, "minutes_played", 45),
           _ps_row(1, 10, 910, "accurate_passes", 22, 25),
           _ps_row(1, 10, 910, "duel_won", 2), _ps_row(1, 10, 910, "duel_lost", 1)]
    lineup.append(_lineup_row(1, 10, 911, "Pieno", 1))
    ps += [_ps_row(1, 10, 911, "minutes_played", 900),
           _ps_row(1, 10, 911, "accurate_passes", 765, 900),
           _ps_row(1, 10, 911, "duel_won", 330), _ps_row(1, 10, 911, "duel_lost", 270)]
    return _store(tmp_path, lineup, ps, FX)


def test_quota_stimata_sugli_eventi_e_dichiarata_nella_cella(tmp_path):
    """Sotto i 90′ il grezzo di una percentuale non si pubblica: si pubblica la stima (docs/23 §2)."""
    cat = PlayerCatalog(_store_con_quote(tmp_path))
    riga = cat._stat_row("pass_pct", 910)              # 45′: 22 su 25 tentativi
    assert riga["quota"] is True and (riga["num"], riga["den"]) == (22, 25)
    assert riga["insufficient"] is True and riga["per90"] == "—"
    # media della lega × ruolo sui soli 9 pari sopra i 90′: 1.405 riusciti su 1.700 tentativi
    assert riga["est_s"] == "85,3%"                    # (22 + 25 × 0,8265) / (25 + 25)
    assert riga["est_visibile"] is True
    assert riga["per90_titolo"].startswith("Campione di 45′")
    assert "Stima stabilizzata 85,3%" in riga["per90_titolo"]
    assert "media dei pari (difensori di Serie A) 82,6%" in riga["est_note"]
    assert "peso k=25 tentativi" in riga["est_note"] and "/90" not in riga["est_note"]


def test_quota_piena_pubblicata_come_frazione_e_mai_come_rata_per_90(tmp_path):
    """Con il campione pieno si pubblica il grezzo, ma la cella dice la frazione esatta."""
    cat = PlayerCatalog(_store_con_quote(tmp_path))
    piena = cat._stat_row("pass_pct", 911)             # 900′: 765 su 900
    assert piena["insufficient"] is False and piena["per90"] == "85,0%"
    assert piena["est_s"] == "84,9%"                   # (765 + 25 × 0,8265) / (900 + 25)
    assert "/90" not in piena["per90_titolo"]
    assert "765 passaggi riusciti su 900 tentati" in piena["per90_titolo"]


def test_stima_delle_quote_entra_nei_percentili(tmp_path):
    """Il percentile di una quota segue la stima stabilizzata, non il valore grezzo."""
    cat = PlayerCatalog(_store_con_quote(tmp_path))
    assert abs(cat._est.loc[911, "pass_pct"] - 785.6617647 / 925) < 1e-6
    grezzo, stima = cat._per90.loc[911, "duels_pct"], cat._est.loc[911, "duels_pct"]
    assert stima < grezzo and 0.5 < stima < 0.55      # 55,0% grezzo trascinato verso il 50,0% dei pari
    assert cat._pct.loc[911, "pass_pct"] == 100.0      # il grezzo 85,0% supera la media dei pari
    # lo spezzone da 45′ resta fuori dai percentili (soglia MIN_MINUTES), come prima
    assert 910 not in cat._pct.index


def test_scheda_giocatore_valore_di_mercato_in_k_euro(tmp_path):
    """`docs/43` §3: 73.728 € si pubblica «74 k€», non «€0M» (oggi 845 schede a zero).

    Il difetto era `|it_num` senza decimali sul rapporto in milioni: qualsiasi valore
    sotto i 500.000 € diventava zero. La prova è sul render, non sul formattatore,
    perché è la pagina ciò che il lettore vede.
    """
    lineup = [_lineup_row(1, 10, 501, "Giovane", 3, market_value_eur=73_728.0)]
    ps = [_ps_row(1, 10, 501, "minutes", 95)]
    st = _store(tmp_path, lineup, ps, FX)
    out = tmp_path / "out"
    SiteBuilder(store=st, out_dir=out).build_players(set())
    html = (out / "giocatori" / "501.html").read_text(encoding="utf-8")
    assert "74 k€" in html, "il valore di mercato va pubblicato in k€, non arrotondato a zero"
    assert "€0M" not in html
    st.close()


def test_nessun_template_arrotonda_a_milioni_interi():
    """Guardia (`docs/43` §5): gli importi passano tutti da `fee_it`, senza divisioni proprie."""
    tpl = Path(__file__).resolve().parents[1] / "src" / "fda" / "site" / "templates"
    for nome in ("giocatore.html", "match.html"):
        testo = (tpl / nome).read_text(encoding="utf-8")
        assert "fee_it" in testo, f"{nome}: importo di mercato senza il formattatore comune"
        assert "/ 1000000" not in testo and "/1e6" not in testo, \
            f"{nome}: arrotondamento a milioni interi (sotto il milione stampa zero)"
