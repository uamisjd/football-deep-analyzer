"""Test offline dei blocchi docs/21: panchina+posta in gioco (P0-1), coppe (P1-4), notizie (P1-5).

Nessuna rete: store sintetici in tmp_path, come negli altri test del sito.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest

from fda.site.analysis import MatchAnalysis
from fda.sources.news import classify_news, clean_text, keyword_score, parse_rss
from fda.store import Store

KO = lambda s: pd.Timestamp(s, tz="UTC")


def _fixtures(rows):
    base = ["match_id", "league_id", "season", "round", "utc_kickoff", "home_id", "home_name",
            "away_id", "away_name", "home_goals", "away_goals", "status", "source"]
    return pd.DataFrame([dict(zip(base, r)) for r in rows])


FX = _fixtures([
    (1, 55, "2026", "1", KO("2026-09-01 18:00"), 1, "Roma", 2, "Inter", 1, 0, "finished", "fotmob"),
    (2, 55, "2026", "2", KO("2026-09-05 18:00"), 2, "Inter", 3, "Milan", 2, 2, "finished", "fotmob"),
    (3, 55, "2026", "3", KO("2026-09-09 18:00"), 1, "Roma", 4, "Lazio", 0, 1, "finished", "fotmob"),
    (4, 55, "2026", "4", KO("2026-09-13 18:00"), 2, "Inter", 1, "Roma", None, None, "scheduled", "fotmob"),
])

LINEUP = pd.DataFrame([
    # Inter: coach A alla 1ª, coach B dalla 2ª (gara davvero giocata dall'Inter) → cambio
    {"match_id": 1, "team_id": 2, "player_id": 100, "player_name": "Coach Vecchio", "role": "coach"},
    {"match_id": 2, "team_id": 2, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
    {"match_id": 4, "team_id": 2, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
    # Roma: panchina invariata
    {"match_id": 1, "team_id": 1, "player_id": 300, "player_name": "Coach Stabile", "role": "coach"},
    {"match_id": 3, "team_id": 1, "player_id": 300, "player_name": "Coach Stabile", "role": "coach"},
    {"match_id": 4, "team_id": 1, "player_id": 300, "player_name": "Coach Stabile", "role": "coach"},
])

SIM = pd.DataFrame([
    {"league_key": "ITA1", "team": "Inter", "played": 3, "points": 7, "exp_points": 78.0,
     "pos_mean": 2.1, "p_title": 0.22, "p_top4": 0.81, "p_rel": 0.0, "n_sims": 100},
    {"league_key": "ITA1", "team": "Roma", "played": 3, "points": 3, "exp_points": 52.0,
     "pos_mean": 9.4, "p_title": 0.01, "p_top4": 0.12, "p_rel": 0.41, "n_sims": 100},
])

CUPS = pd.DataFrame([
    {"match_id": 91, "league_id": 42, "league_key": "UCL", "cup_name": "Champions League",
     "season": "2026", "round": "MD1", "utc_kickoff": KO("2026-09-08 19:00"),
     "home_id": 2, "home_name": "Inter", "away_id": 9, "away_name": "Ajax",
     "home_goals": 1, "away_goals": 1, "status": "finished", "source": "fotmob"},
])

STANDINGS = pd.DataFrame([
    {"league_code": "ITA1", "team_id": 1, "team_name": "Roma", "rank": 1, "played": 3,
     "wins": 3, "draws": 0, "losses": 0, "goals_for": 8, "goals_against": 3, "goal_diff": 5, "points": 9},
    {"league_code": "ITA1", "team_id": 2, "team_name": "Inter", "rank": 2, "played": 3,
     "wins": 2, "draws": 1, "losses": 0, "goals_for": 6, "goals_against": 3, "goal_diff": 3, "points": 7},
    {"league_code": "ITA1", "team_id": 3, "team_name": "Milan", "rank": 3, "played": 3,
     "wins": 1, "draws": 1, "losses": 1, "goals_for": 4, "goals_against": 4, "goal_diff": 0, "points": 4},
    {"league_code": "ITA1", "team_id": 4, "team_name": "Lazio", "rank": 4, "played": 3,
     "wins": 0, "draws": 1, "losses": 2, "goals_for": 2, "goals_against": 6, "goal_diff": -4, "points": 1},
])

NEWS = pd.DataFrame([
    {"team_id": 2, "published_at": KO("2026-09-14 09:00"), "title": "Inter, infermeria: torna il titolare",
     "url": "https://esempio.it/1", "source": "Gazzetta", "description": "vigilia e convocati"},
    {"team_id": 2, "published_at": KO("2026-09-13 09:00"), "title": "Serie A, il punto sulla giornata",
     "url": "https://esempio.it/2", "source": "Corriere", "description": "cronaca generica"},
    {"team_id": 2, "published_at": KO("2026-08-01 09:00"), "title": "Inter, notizia vecchia",
     "url": "https://esempio.it/3", "source": "Gazzetta", "description": "fuori finestra"},
    {"team_id": 1, "published_at": KO("2026-09-14 10:00"), "title": "Roma, crisi di risultati: esonero?",
     "url": "https://esempio.it/4", "source": "Repubblica", "description": ""},
])


@pytest.fixture()
def analysis(tmp_path):
    st = Store(tmp_path / "processed")
    st.write("fixtures", FX)
    st.write("lineup", LINEUP)
    st.write("season_sim", SIM)
    st.write("cup_fixtures", CUPS)
    st.write("news", NEWS)
    st.write("fotmob_standings", STANDINGS)
    return MatchAnalysis(st)


def test_cambio_panchina_rilevato(analysis):
    c = analysis.coach(2, KO("2026-09-14 00:00"))
    assert c["name"] == "Coach Nuovo"
    assert c["prev_name"] == "Coach Vecchio"
    assert c["matches"] == 2  # gare da calendario col nuovo coach fino al kickoff


def test_panchina_stabile_senza_cambio(analysis):
    c = analysis.coach(1, KO("2026-09-14 00:00"))
    assert c["name"] == "Coach Stabile"
    assert c["prev_name"] is None
    assert c["matches"] == 3


def test_stakes_etichette_e_interi(analysis):
    s = analysis.stakes("Inter")
    assert s["label"] == "corsa al titolo" and s["p_title_pct"] == 22 and s["p_top4_pct"] == 81
    assert s["ucl_spots"] == 4 and s["ucl_legacy"] is True
    r = analysis.stakes("Roma")
    assert r["label"] == "lotta salvezza" and r["p_rel_pct"] == 41
    assert analysis.stakes("Squadra Inesistente") is None


def test_stakes_usa_la_soglia_nuova_e_non_il_fallback(analysis):
    analysis.season_sim = SIM.assign(top_n=2, p_top_n=[0.55, 0.08])
    s = analysis.stakes("Inter")
    assert s["ucl_spots"] == 2 and s["ucl_legacy"] is False
    assert s["p_top_n_pct"] == 55


def test_riposo_con_coppe_e_nota(analysis):
    # ultima gara Inter = 08/09 19:00 in Champions (non 05/09 di lega): al 13/09 18:00
    # sono 4 giorni e 23 ore → riposo 4 (floor), e la nota coppa deve comparire
    rest = analysis.rest_days(2, KO("2026-09-13 18:00"))
    assert rest == 4
    assert analysis.rest_cup(2, KO("2026-09-13 18:00")) == "Champions League"
    # Roma senza coppe: ultima 09/09 → 4 giorni, nessuna nota
    assert analysis.rest_days(1, KO("2026-09-13 18:00")) == 4
    assert analysis.rest_cup(1, KO("2026-09-13 18:00")) is None


def test_bollettino_tiene_solo_le_notizie_utili(analysis):
    """Selezione: categoria dichiarata, finestra vera, gate di soggetto, ordine giusto.

    Le fixture contengono una notizia utile («Inter, infermeria…»), una di cronaca
    generica, una fuori finestra e una che parla di un'altra squadra: nella card resta
    solo la prima — ed è la versione **più recente** (il difetto precedente ordinava a
    parità di punteggio per data crescente).
    """
    nw = analysis.team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert [n["title"] for n in nw["notizie"]] == ["Inter, infermeria: torna il titolare"]
    assert nw["notizie"][0]["topic"] == "infortuni"
    assert nw["notizie"][0]["topic_label"] == "Infortuni"
    assert nw["notizie"][0]["source"] == "Gazzetta"
    # «esaminate» conta i titoli DENTRO la finestra: quello di agosto è fuori e non entra
    assert nw["esaminate"] == 2 and nw["pertinenti"] == 1 and nw["scartate"] == 1
    assert nw["argomenti"] == [("Infortuni", 1)]
    # la notizia di un'altra squadra non compare mai nel bollettino di questa
    roma = analysis.team_news(1, "Roma", KO("2026-09-15 12:00"))
    assert all("Inter" not in n["title"] for n in roma["notizie"])


def test_bollettino_scarta_dirette_pronostici_e_cronaca(analysis):
    """Le pagine di servizio non entrano: dirette, «dove vederla», pronostici, pagelle,
    e la cronaca di una gara già giocata (il titolo porta il risultato)."""
    for titolo in ("Inter-Lazio risultati in diretta, testa a testa e formazioni",
                   "Pronostico Inter-Lazio: probabili formazioni",
                   "Dove vedere Inter-Lazio in tv e streaming",
                   "Inter-Lazio 3-1: le pagelle dei nerazzurri"):
        assert classify_news(titolo)[0] is None, titolo
    # la testata non è contenuto: un pezzo di cronaca ripreso da TUTTOmercatoWEB non
    # diventa «Mercato» (era il difetto: la categoria la decideva la testata)
    assert classify_news("Fumogeni in campo: sospesa la sfida",
                         "Fumogeni in campo: sospesa la sfida TUTTOmercatoWEB",
                         "TUTTOmercatoWEB")[0] is None
    assert classify_news("Roma, Dybala torna in gruppo", "", "Corriere dello Sport")[0] == "infortuni"
    assert classify_news("Napoli, il giudice sportivo: due turni a Di Lorenzo")[0] == "squalifiche"
    assert classify_news("Fiorentina, Grosso esonerato")[0] == "allenatore"


def test_bollettino_limite_per_squadra_e_ordine_per_categoria(tmp_path):
    """Al più 3 voci per squadra, la categoria più importante prima, poi la più recente."""
    st = Store(tmp_path / "bollettino")
    rows = [
        {"team_id": 2, "published_at": KO("2026-09-14 18:00"), "title": "Inter, sponsor nuovo per la stagione",
         "url": "u1", "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"), "title": "Inter, infortunio: out un mese",
         "url": "u2", "source": "S2", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-13 09:00"), "title": "Inter, esonerato il tecnico",
         "url": "u3", "source": "S3", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 16:00"), "title": "Inter, due turni di squalifica per X",
         "url": "u4", "source": "S4", "description": ""},
    ]
    st.write("news", pd.DataFrame(rows))
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert len(nw["notizie"]) == 3 and nw["pertinenti"] == 4
    assert [n["topic"] for n in nw["notizie"]] == ["squalifiche", "infortuni", "allenatore"]
    # fra voci di pari peso vince la più recente: squalifica 16:00, infortunio 09:00
    assert nw["notizie"][0]["topic"] == "squalifiche" and nw["notizie"][0]["published_at"].hour == 16
    # l'argomento meno importante non è perso: resta dichiarato nei conteggi
    assert ("Club", 1) in nw["argomenti"]
    st.close()


def test_bollettino_dedup_fra_le_due_squadre_della_partita(tmp_path):
    """Lo stesso articolo non compare due volte in pagina (era: 58 duplicati su 535 voci).

    Il feed ripubblica lo stesso pezzo con data aggiornata per la stessa squadra, e la
    stessa notizia torna dal feed di entrambe le squadre: l'insieme dei titoli visti è
    condiviso fra le due colonne.
    """
    st = Store(tmp_path / "bollettino_dedup")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"), "title": "Inter, infortunio a X",
         "url": "u1", "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 12:00"), "title": "Inter, infortunio a X",
         "url": "u1", "source": "S1", "description": ""},   # stessa notizia, data aggiornata
        {"team_id": 1, "published_at": KO("2026-09-14 12:00"), "title": "Inter, infortunio a X",
         "url": "u1", "source": "S1", "description": ""},   # e arriva anche dal feed di Roma
    ]))
    an = MatchAnalysis(st)
    visti: set[str] = set()
    casa = an.team_news(2, "Inter", KO("2026-09-15 12:00"), seen=visti)
    ospiti = an.team_news(1, "Roma", KO("2026-09-15 12:00"), seen=visti)
    assert len(casa["notizie"]) == 1 and casa["notizie"][0]["published_at"].hour == 8
    assert ospiti["notizie"] == []                      # già pubblicata nell'altra colonna
    st.close()


def test_bollettino_perche_conta_collega_la_notizia_ai_nostri_dati(tmp_path):
    """«Perché conta»: se il titolo nomina un indisponibile o un titolare, la card lo dice."""
    st = Store(tmp_path / "bollettino_why")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, lesione per Marco Indisponibile: out un mese",
         "url": "u1", "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Inter, infortunio per Coach Nuovo",
         "url": "u2", "source": "S2", "description": ""},
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 4, "team_id": 2, "player_id": 1, "player_name": "Marco Indisponibile",
         "role": "unavailable", "unavailability_type": "injury", "expected_return": "Day to day"},
        {"match_id": 4, "team_id": 2, "player_id": 2, "player_name": "Titolare X", "role": "starter"},
    ]))
    an = MatchAnalysis(st)
    nw = an.team_news(2, "Inter", KO("2026-09-15 12:00"),
                      squad=an.match_squad(4, 2))
    voce = next(n for n in nw["notizie"] if "Marco" in n["title"])
    assert voce["why"].startswith("«Marco Indisponibile» è nella lista indisponibili")
    # il titolo che cita un titolare lo dice (la notizia può essere più fresca del dato)
    assert all(not n["why"] or "Indisponibile" in n["why"] for n in nw["notizie"])
    st.close()


def test_bollettino_finestra_superiore_e_inferiore(tmp_path):
    """Finestra vera: né notizie più vecchie di 12 giorni né pubblicate dopo il calcio d'inizio."""
    st = Store(tmp_path / "bollettino_finestra")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-09-01 08:00"), "title": "Inter, infortunio vecchio",
         "url": "u1", "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-15 20:00"), "title": "Inter, infortunio dopo la gara",
         "url": "u2", "source": "S2", "description": ""},
    ]))
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert nw["esaminate"] == 0 and nw["scartate"] == 0
    # la notizia del 1° settembre è fuori finestra: può entrare solo dal recupero, con la
    # data vera e l'etichetta; quella pubblicata dopo il calcio d'inizio non entra mai
    assert all(n["recupero"] for n in nw["notizie"])
    assert all(n["published_at"] < KO("2026-09-15 12:00") for n in nw["notizie"])
    assert all("dopo la gara" not in n["title"] for n in nw["notizie"])
    st.close()


def test_bollettino_recupero_fuori_finestra(tmp_path):
    """Se la finestra di 12 giorni è vuota la card non resta muta: recupera fino a 45
    giorni e lo dichiara, con la data vera e l'etichetta di recupero.

    Misurato il 2026-09-16: 91 colonne su 140 (65%) restavano senza voci perché nella
    finestra c'erano solo dirette e pronostici. Il recupero preferisce infortuni,
    panchina, società e squadra: il mercato è già nella card qui sopra.
    """
    st = Store(tmp_path / "bollettino_recupero")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-08-25 09:00"), "title": "Inter, ufficiale: preso il terzino",
         "url": "u1", "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-08-20 09:00"), "title": "Inter, lesione per il capitano: out un mese",
         "url": "u2", "source": "S2", "description": ""},
        {"team_id": 2, "published_at": KO("2026-07-01 09:00"), "title": "Inter, infortunio troppo vecchio",
         "url": "u3", "source": "S3", "description": ""},
    ]))
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert nw["pertinenti"] == 0 and nw["esaminate"] == 0
    assert nw["recupero_usato"] is True and nw["finestra_recupero"] == 45
    assert [n["title"] for n in nw["notizie"]] == ["Inter, lesione per il capitano: out un mese"]
    assert nw["notizie"][0]["recupero"] is True          # il mercato cede il posto all'infortunio
    assert nw["notizie"][0]["topic"] == "infortuni"
    st.close()


def test_bollettino_biglietti_e_merch_scartati(tmp_path):
    """Le pagine di servizio non entrano: biglietti, prevendite, merchandising, figurine.

    Misurato il 2026-09-16 sul sito pubblicato: 27 voci su 162 erano «Come acquistare i
    biglietti per X-Y» mentre la card dichiarava di escluderle. Il filtro le scarta e
    conta la riga fra le scartate, così il numero stampato resta riconciliabile.
    """
    st = Store(tmp_path / "bollettino_servizio")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Come acquistare i biglietti per Inter-Milan: prezzi e informazioni",
         "url": "u1", "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Inter, lesione per il capitano: out un mese",
         "url": "u2", "source": "S2", "description": ""},
    ]))
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert [n["title"] for n in nw["notizie"]] == ["Inter, lesione per il capitano: out un mese"]
    assert nw["esaminate"] == 2 and nw["scartate"] == 1 and nw["pertinenti"] == 1
    st.close()


def test_bollettino_un_soggetto_per_categoria(tmp_path):
    """Stessa categoria e stesso nome proprio = stesso fatto: la seconda voce non entra."""
    st = Store(tmp_path / "bollettino_soggetto")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-09-14 10:00"),
         "title": "Inter, Calhanoglu ko: lesione all'adduttore", "url": "u1",
         "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, Calhanoglu: risentimento muscolare, salta la Roma", "url": "u2",
         "source": "S2", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-13 08:00"),
         "title": "Inter, infortunio per Stones: gli esami di giovedì", "url": "u3",
         "source": "S3", "description": ""},
    ]))
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    # due infortuni su giocatori diversi restano, il doppione su Calhanoglu no
    assert [n["title"].split(",")[1].strip().split()[0] for n in nw["notizie"]] == \
        ["Calhanoglu", "infortunio"]
    assert nw["pertinenti"] == 2 and nw["scartate"] == 1
    st.close()


def test_bollettino_tabella_vuota_degrada(tmp_path):
    st = Store(tmp_path / "bollettino_vuoto")
    a = MatchAnalysis(st)
    nw = a.team_news(1, "Roma", KO("2026-09-15 12:00"))
    assert nw["notizie"] == [] and nw["esaminate"] == 0 and nw["finestra"] == 12
    assert a.coach(1) is None and a.stakes("Roma") is None
    assert a.bench_side(1, "Roma") is None


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item><title>Inter, pressing per il rinnovo - La Gazzetta dello Sport</title>
<link>https://news.google.com/read/1</link><pubDate>Mon, 14 Sep 2026 08:15:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Inter&lt;/a&gt; e il rinnovo del centrocampista</description></item>
<item><title>Titolo senza testata</title><link>https://news.google.com/read/2</link>
<pubDate data-invalid="1"></pubDate><description></description></item>
</channel></rss>"""


def test_parse_rss_testata_data_e_pulizia():
    rows = parse_rss(RSS, team_id=2)
    assert len(rows) == 2
    a, b = rows
    assert a["title"] == "Inter, pressing per il rinnovo"
    assert a["source"] == "La Gazzetta dello Sport"
    assert a["published_at"] == datetime(2026, 9, 14, 8, 15, tzinfo=UTC)
    assert a["description"] == "Inter e il rinnovo del centrocampista"
    assert b["published_at"] is None and b["source"] == "Google News"
    assert parse_rss("<xml rotto", 2) == []


def test_keyword_score_e_clean_text():
    assert keyword_score("ESONERO in vista? Crisi di risultati") >= 2
    assert keyword_score("cronaca della partita") == 0
    assert clean_text("<b>a</b>  &amp; b") == "a & b"


def test_bench_deep_profilo_rendimento_e_virtual(analysis):
    b = analysis.bench_deep(2, "Inter", 1, "Roma", KO("2026-09-14 00:00"))
    assert b["tenure_line"] == "panchina nuova: 2ª gara dal subentro a Coach Vecchio"
    # una sola gara finita col coach corrente (Inter-Milan 2-2): 1,0 punti/gara
    assert b["coach_ppg_line"] == "1,0 punti/gara su 1 gara finita"
    assert b["coach_vs_opp_line"] is None      # 1 gara < soglia 3
    assert b["coach_vs_coach_line"] is None    # 1 gara < soglia 2
    assert b["table_line"] == ("2º con 7 punti · 3 punti sopra la zona retrocessione · "
                               "in zona Europa (4º posto o meglio)")
    assert b["virtual_line"] == ("con una vittoria 1º · con una sconfitta 2º "
                                 "(classifica virtuale, altre gare in sospeso)")


def test_bench_deep_zona_retrocessione_e_nationalita(analysis):
    b = analysis.bench_deep(4, "Lazio", 1, "Roma", KO("2026-09-14 00:00"))
    assert "dalla salvezza diretta" in b["table_line"]   # ultima piazza: distanza dalla salvezza
    assert "con una vittoria" in b["virtual_line"]
    r = analysis.bench_deep(1, "Roma", 2, "Inter", KO("2026-09-14 00:00"))
    assert r["tenure_line"] == "panchina invariata da 3 gare nel nostro archivio"
    assert r["coach_ppg_line"] == "1,5 punti/gara su 2 gare finite"  # 1-0 e 0-1: 3 punti su 2


def test_bench_deep_senza_classifica_degrada(tmp_path):
    st = Store(tmp_path / "nostand")
    st.write("fixtures", FX)
    st.write("lineup", LINEUP)
    a = MatchAnalysis(st)
    b = a.bench_deep(2, "Inter", 1, "Roma", KO("2026-09-14 00:00"))
    assert b["table_line"] is None and b["virtual_line"] is None
    assert b["coach_ppg_line"] == "1,0 punti/gara su 1 gara finita"


FX_MOOD = _fixtures([
    # Lazio: P il 06, V il 09 (in FX), poi tre perse consecutive (10, 12, 14) → crisi
    (5, 55, "2026", "5", KO("2026-09-06 18:00"), 4, "Lazio", 2, "Inter", 0, 2, "finished", "fotmob"),
    (6, 55, "2026", "6", KO("2026-09-10 18:00"), 3, "Milan", 4, "Lazio", 3, 0, "finished", "fotmob"),
    (7, 55, "2026", "7", KO("2026-09-12 20:00"), 4, "Lazio", 1, "Roma", 1, 2, "finished", "fotmob"),
    (9, 55, "2026", "9", KO("2026-09-14 18:00"), 4, "Lazio", 5, "Napoli", 1, 3, "finished", "fotmob"),
    (8, 55, "2026", "8", KO("2026-09-16 18:00"), 4, "Lazio", 3, "Milan", None, None, "scheduled", "fotmob"),
])

LINEUP_MOOD = pd.DataFrame([
    {"match_id": 8, "team_id": 4, "player_id": 901, "player_name": "Assente Uno", "role": "unavailable",
     "unavailability_type": "injury", "expected_return": "unknown", "market_value_eur": 12_000_000},
    {"match_id": 8, "team_id": 4, "player_id": 902, "player_name": "Assente Due", "role": "unavailable",
     "unavailability_type": "injury", "expected_return": "unknown", "market_value_eur": 9_000_000},
    {"match_id": 8, "team_id": 4, "player_id": 903, "player_name": "Assente Tre", "role": "unavailable",
     "unavailability_type": "suspension", "expected_return": "unknown", "market_value_eur": 8_000_000},
    {"match_id": 8, "team_id": 4, "player_id": 904, "player_name": "Assente Quattro", "role": "unavailable",
     "unavailability_type": "injury", "expected_return": "unknown", "market_value_eur": 6_000_000},
])


@pytest.fixture()
def mood_analysis(tmp_path):
    st = Store(tmp_path / "mood")
    st.write("fixtures", pd.concat([FX, FX_MOOD], ignore_index=True))
    lu = pd.concat([LINEUP, LINEUP_MOOD], ignore_index=True)
    for col in ("position_id", "usual_position_id"):
        if col not in lu.columns:
            lu[col] = pd.NA
    st.write("lineup", lu)
    return MatchAnalysis(st)


def test_clima_crisi_infermeria_congestione(mood_analysis):
    rows = mood_analysis.club_mood(8, 4, "Lazio", KO("2026-09-16 18:00"))
    texts = [r["text"] for r in rows]
    assert any(t.startswith("crisi di risultati: 3 sconfitte consecutive") for t in texts)
    assert any(t.startswith("infermeria pesante: 4 assenti") for t in texts)
    assert any("35 M€ di mercato ai box" in t for t in texts)   # 12+9+8+6 = 35
    assert any(t.startswith("riposo corto: 2 giorni") for t in texts)
    assert any(t.startswith("congestione: 5 gare giocate negli ultimi 10 giorni") for t in texts)
    assert all(r["tone"] in ("bad", "warn", "good") for r in rows)


def test_clima_squadra_serenissima_senza_segnali(mood_analysis):
    # Milan: [N, V], ultima gara il 09/09 (7 giorni di riposo), niente coach né assenti
    # → nessuna soglia superata: la card direbbe «clima normale», zero righe inventate
    rows = mood_analysis.club_mood(8, 3, "Milan", KO("2026-09-16 18:00"))
    assert rows == []
    # Roma invece ha giocato il 13/09: il riposo corto È un segnale, e va pubblicato
    roma = mood_analysis.club_mood(8, 1, "Roma", KO("2026-09-16 18:00"))
    assert [r["text"] for r in roma] == ["riposo corto: 3 giorni"]
