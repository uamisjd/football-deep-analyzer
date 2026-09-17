"""Test offline dei blocchi docs/21: panchina+posta in gioco (P0-1), coppe (P1-4), notizie (P1-5).

Nessuna rete: store sintetici in tmp_path, come negli altri test del sito.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest

from fda.site.analysis import MatchAnalysis, news_subjects
from fda.sources.news import classify_news, clean_text, keyword_score, news_value, parse_rss
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


def _store_news(tmp_path, nome, rows):
    st = Store(tmp_path / nome)
    st.write("news", pd.DataFrame(rows))
    return st


def test_bollettino_pubblica_solo_i_fatti_che_spostano(tmp_path):
    """Gate del valore (docs/24 §3.5): annunci, servizio, infortuni e mercato restano fuori
    e vengono contati; entra solo ciò che può spostare qualcosa."""
    st = _store_news(tmp_path, "bollettino_v4", [
        {"team_id": 2, "published_at": KO("2026-09-14 18:00"),
         "title": "Inter, il nuovo sponsor per la stagione", "url": "u1", "source": "S1",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Inter, infermeria: torna il titolare", "url": "u2", "source": "S2",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, ufficiale: preso il terzino", "url": "u3", "source": "S3",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-15 08:00"),
         "title": "Inter, multa della lega per i cori: la società protesta", "url": "u4",
         "source": "S4", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-08 08:00"),
         "title": "Inter, crisi societaria: la proprietà vuole vendere", "url": "u5",
         "source": "S5", "description": ""},
    ])
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert [n["title"] for n in nw["notizie"]] == \
        ["Inter, multa della lega per i cori: la società protesta"]
    assert nw["esaminate"] == 4 and nw["pubblicate"] == 1
    assert nw["annunci"] == 1 and nw["scartate"] == 2 and nw["piatti"] == 0
    assert nw["vecchie"] == 1          # la voce dell'8/09 è oltre i 7 giorni
    assert nw["notizie"][0]["topic_label"] == "Società"
    assert nw["notizie"][0]["ore"] == 4.0
    assert nw["notizie"][0]["punteggio"] > 0
    st.close()


def test_news_value_gate_multilingua():
    """Annuncio, piatto o fatto: il gate legge anche le lingue della seconda query."""
    # annunci: conferenza stampa, lavori, sponsor — freschi e pertinenti, ma non spostano nulla
    assert news_value("Rueda de prensa de Pellegrini previa al Betis-Getafe") == "annuncio"
    assert news_value("El Getafe climatizará el Coliseo: obras anunciadas") == "annuncio"
    assert news_value("Betis, el nuevo patrocinador principal de la temporada") == "annuncio"
    # cronaca della giornata: nessuna frizione, nessuna decisione, nessun vincolo
    assert news_value("Inter, il punto sulla giornata di campionato") == "piatto"
    assert news_value("Betis, un punto más y seguimos") == "piatto"
    # fatti che spostano qualcosa, in due lingue
    assert news_value("La FRMF rechaza la petición del Betis por Abde") is None
    assert news_value("Bordalás carga contra la directiva por la plantilla corta") is None
    assert news_value("Bordalás: «somos el único equipo que no tiene extremos»") is None
    assert news_value("Inter, multa della lega: ricorso respinto") is None
    assert news_value("Betis, el vestuario, en tensión, por los descartes") is None


def test_classifica_le_notizie_in_lingua_locale():
    """La categoria arriva anche dai titoli spagnoli: è la seconda query (docs/24 §3.5)."""
    assert classify_news("Bordalás: «somos el único equipo que no tiene extremos»")[0] == "spogliatoio"
    assert classify_news("El Getafe climatizará el Coliseo: obras anunciadas")[0] == "stadio"
    assert classify_news("La directiva del Betis rechaza el recurso de los ecologistas")[0] == "societa"
    assert classify_news("Los ultras del Betis preparan una protesta")[0] == "tifo"
    assert classify_news("Getafe, lesión de Femenía: se pierde el partido")[0] == "infortuni"


def test_bollettino_limite_per_categoria(tmp_path):
    """Non più di due fatti per categoria: la terza voce della stessa categoria si conta
    come «oltre il limite» e non entra (docs/24 §3.5)."""
    st = _store_news(tmp_path, "bollettino_categorie", [
        {"team_id": 2, "published_at": KO("2026-09-14 18:00"),
         "title": "Inter, multa della lega per i cori", "url": "u1", "source": "S1",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 16:00"),
         "title": "Inter, la proprietà smentisce la vendita del club", "url": "u2",
         "source": "S2", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 14:00"),
         "title": "Inter, ricorso respinto: la multa resta", "url": "u3", "source": "S3",
         "description": ""},
    ])
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert nw["pubblicate"] == 2 and nw["oltre"] == 1 and nw["riserva"] == []
    st.close()


def test_bollettino_riserva_oltre_i_tre(tmp_path):
    """Con più di tre fatti si pubblicano i primi tre; chi resta non si perde: «in riserva»."""
    rows = [
        ("Inter, multa della lega per i cori", "2026-09-14 18:00"),
        ("Inter, il tecnico rischia la panchina dopo il ko", "2026-09-14 20:00"),
        ("Inter, gli ultras preparano la protesta contro la dirigenza", "2026-09-14 17:00"),
        ("Inter, la proprietà smentisce la vendita del club", "2026-09-14 16:00"),
        ("Inter, ricorso respinto: la multa resta", "2026-09-14 15:00"),
    ]
    st = _store_news(tmp_path, "bollettino_riserva", [
        {"team_id": 2, "published_at": KO(ora), "title": t, "url": f"u{i}",
         "source": "S", "description": ""} for i, (t, ora) in enumerate(rows)])
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert nw["pubblicate"] == 3 and len(nw["riserva"]) == 1 and nw["oltre"] == 1
    assert nw["pertinenti"] == 5   # cinque passano i filtri; una la taglia il tetto per categoria
    st.close()


def test_bollettino_finestra_sette_giorni(tmp_path):
    """Finestra di 7 giorni: fuori le notizie più vecchie (contate) e quelle pubblicate
    dopo il calcio d'inizio."""
    st = _store_news(tmp_path, "bollettino_finestra", [
        {"team_id": 2, "published_at": KO("2026-09-07 08:00"),
         "title": "Inter, ricorso respinto: la multa resta", "url": "u1", "source": "S1",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-15 20:00"),
         "title": "Inter, multa della lega per i cori", "url": "u2", "source": "S2",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, la proprietà smentisce la vendita del club", "url": "u3",
         "source": "S3", "description": ""},
    ])
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert nw["esaminate"] == 1 and nw["pubblicate"] == 1 and nw["vecchie"] == 1
    assert nw["finestra"] == 7
    assert all(n["published_at"] <= KO("2026-09-15 12:00") for n in nw["notizie"])
    st.close()


def test_bollettino_non_ripete_le_altre_card(tmp_path):
    """Infortuni, squalifiche e mercato hanno la loro card in questa pagina: non si ripetono."""
    st = _store_news(tmp_path, "bollettino_altrove", [
        {"team_id": 2, "published_at": KO("2026-09-14 10:00"),
         "title": "Inter, lesione per il capitano: out un mese", "url": "u1",
         "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Inter, due turni di squalifica per X", "url": "u2", "source": "S2",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, ufficiale: preso il terzino", "url": "u3", "source": "S3",
         "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 07:00"),
         "title": "Inter, ricorso respinto: la multa resta", "url": "u4", "source": "S4",
         "description": ""},
    ])
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert [n["title"] for n in nw["notizie"]] == ["Inter, ricorso respinto: la multa resta"]
    assert nw["esaminate"] == 4 and nw["scartate"] == 3
    st.close()


def test_bollettino_un_soggetto_per_categoria(tmp_path):
    """Stessa categoria e stesso nome proprio = stesso fatto: la seconda voce non entra."""
    st = _store_news(tmp_path, "bollettino_soggetto", [
        {"team_id": 2, "published_at": KO("2026-09-14 10:00"),
         "title": "Inter, Calhanoglu multato dal club per una frase", "url": "u1",
         "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, Calhanoglu: la multa della lega resta", "url": "u2",
         "source": "S2", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-13 08:00"),
         "title": "Inter, Stones deferito: rischia una multa", "url": "u3",
         "source": "S3", "description": ""},
    ])
    nw = MatchAnalysis(st).team_news(2, "Inter", KO("2026-09-15 12:00"))
    assert nw["pertinenti"] == 2 and nw["scartate"] == 1
    assert "Calhanoglu" in nw["notizie"][0]["title"]
    st.close()


def test_bollettino_scarta_le_voci_di_un_altra_squadra(tmp_path):
    """Un titolo su un'altra squadra del nostro archivio non è informazione per questa gara.

    Misurato il 2026-09-17 sulla colonna della Roma: «Indagine a Roma: pressioni su Lotito a
    cedere la Lazio» entrava fra i pubblicati perché «Roma» è la città, la procura e il club
    insieme. Senza avversario, tesserati o token distintivi, la voce si conta a parte.
    """
    st = _store_news(tmp_path, "bollettino_altre", [
        {"team_id": 2, "published_at": KO("2026-09-14 12:00"),
         "title": "Indagine a Roma: pressioni su Lotito a cedere la Lazio", "url": "u1",
         "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 11:00"),
         "title": "Roma, ricorso respinto: la multa resta", "url": "u2", "source": "S2",
         "description": ""},
    ])
    st.write("fixtures", FX)          # i token dei club arrivano dalle partite in archivio
    nw = MatchAnalysis(st).team_news(2, "Roma", KO("2026-09-15 12:00"))
    assert [n["title"] for n in nw["notizie"]] == ["Roma, ricorso respinto: la multa resta"]
    assert nw["altre"] == 1 and nw["scartate"] == 0
    st.close()


def test_soggetti_dei_titoli_maiuscoli():
    """I titoli di agenzia sono in maiuscolo: i nomi si prendono, le parole di servizio no."""
    soggetti = news_subjects("UFFICIALE – BOLOGNA, ESONERATO TEDESCO DOPO IL KO DI NAPOLI")
    assert "tedesco" in soggetti
    assert "esonerato" not in soggetti and "allenatore" not in soggetti
    # stesso fatto in due titoli (uno in maiuscolo) = stesso soggetto
    assert soggetti & news_subjects("Bologna, esonerato Tedesco: arriva Palladino")


def test_bollettino_rilevanza_per_questa_partita(tmp_path):
    """La rilevanza guarda questa partita: avversario e allenatore valgono più della cronaca,
    e un titolo su un'altra squadra paga la penalità (docs/24 §3.5)."""
    st = _store_news(tmp_path, "bollettino_rilevanza", [
        {"team_id": 2, "published_at": KO("2026-09-14 12:00"),
         "title": "Inter-Lazio, ricorso respinto: la multa resta", "url": "u1",
         "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 12:00"),
         "title": "Inter, il Milan: ricorso sul tetto ingaggi", "url": "u2",
         "source": "S2", "description": ""},
    ])
    an = MatchAnalysis(st)
    nw = an.team_news(2, "Inter", KO("2026-09-15 12:00"), opponent="Lazio",
                      coach="Coach Nuovo")
    titoli = [n["title"] for n in nw["notizie"]]
    # avversario citato (+5) contro altro club citato (−4): vince il primo
    assert titoli[0].startswith("Inter-Lazio")
    punteggi = {n["title"]: n["punteggio"] for n in nw["notizie"] + nw["riserva"]}
    assert punteggi["Inter-Lazio, ricorso respinto: la multa resta"] > \
        punteggi["Inter, il Milan: ricorso sul tetto ingaggi"]
    st.close()


def test_bollettino_perche_conta_collega_la_notizia_ai_nostri_dati(tmp_path):
    """«Perché conta»: se il titolo nomina un indisponibile o l'allenatore, la card lo dice."""
    st = Store(tmp_path / "bollettino_why")
    st.write("news", pd.DataFrame([
        {"team_id": 2, "published_at": KO("2026-09-14 08:00"),
         "title": "Inter, multa al capitano Marco Ferrante", "url": "u1",
         "source": "S1", "description": ""},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Inter, il tecnico Coach Nuovo multato dalla lega", "url": "u2",
         "source": "S2", "description": ""},
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 4, "team_id": 2, "player_id": 1, "player_name": "Marco Ferrante",
         "role": "unavailable", "unavailability_type": "injury", "expected_return": "Day to day"},
        {"match_id": 4, "team_id": 2, "player_id": 2, "player_name": "Titolare X",
         "role": "starter"},
    ]))
    an = MatchAnalysis(st)
    nw = an.team_news(2, "Inter", KO("2026-09-15 12:00"), squad=an.match_squad(4, 2),
                      coach="Coach Nuovo")
    voce = next(n for n in nw["notizie"] if "Marco" in n["title"])
    assert voce["why"].startswith("«Marco Ferrante» è nella lista indisponibili")
    coach_voce = next(n for n in nw["notizie"] if "Coach Nuovo" in n["title"])
    assert "allenatore" in coach_voce["why"]
    st.close()


def test_da_sapere_stadio_diverso_e_panchina_nuova(tmp_path):
    """Il blocco «Da sapere» deriva dai nostri dati: stadio diverso dall'abituale e panchina
    appena cambiata (docs/24 §3.5)."""
    st = Store(tmp_path / "sapere")
    st.write("fixtures", _fixtures([
        (1, 55, "2026", "1", KO("2026-09-01 18:00"), 2, "Inter", 9, "Ajax", 1, 0, "finished", "fotmob"),
        (2, 55, "2026", "2", KO("2026-09-05 18:00"), 2, "Inter", 3, "Milan", 2, 2, "finished", "fotmob"),
        (4, 55, "2026", "4", KO("2026-09-13 18:00"), 2, "Inter", 1, "Roma", None, None, "scheduled", "fotmob"),
    ]))
    st.write("match_info", pd.DataFrame([
        {"match_id": 1, "stadium_name": "Stadio Olimpico", "stadium_capacity": 70000},
        {"match_id": 2, "stadium_name": "Stadio Olimpico", "stadium_capacity": 70000},
        {"match_id": 4, "stadium_name": "San Siro", "stadium_capacity": 75000},
    ]))
    st.write("lineup", LINEUP)
    an = MatchAnalysis(st)
    sapere = an.news_sapere(4, 2, "Inter", 1, "Roma", KO("2026-09-13 18:00"))
    testo = " ".join(s["testo"] for s in sapere)
    assert "San Siro" in testo and "Stadio Olimpico" in testo
    assert any(s["titolo"] == "Panchina nuova" and "Inter" in s["testo"] for s in sapere)
    # senza dati non si inventa nulla
    vuoto = MatchAnalysis(Store(tmp_path / "sapere_vuoto"))
    assert vuoto.news_sapere(4, 2, "Inter", 1, "Roma", KO("2026-09-13 18:00")) == []
    st.close()


def test_da_sapere_ex_di_turno(tmp_path):
    """Il blocco «Da sapere» rileva quando un tecnico affronta una sua ex squadra."""
    st = Store(tmp_path / "ex_turno")
    st.write("fixtures", _fixtures([
        (10, 55, "2026", "5", KO("2026-09-20 18:00"), 1, "Roma", 2, "Inter", None, None, "scheduled", "fotmob"),
    ]))
    st.write("match_info", pd.DataFrame([
        {"match_id": 10, "stadium_name": "Stadio Olimpico", "stadium_capacity": 70000},
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 10, "team_id": 1, "player_id": 500, "player_name": "Gian Piero Gasperini", "role": "coach"},
        {"match_id": 10, "team_id": 2, "player_id": 600, "player_name": "Simone Inzaghi", "role": "coach"},
    ]))
    an = MatchAnalysis(st)
    sapere = an.news_sapere(10, 1, "Roma", 2, "Inter", KO("2026-09-20 18:00"))
    ex_list = [s for s in sapere if s["titolo"] == "Ex di turno"]
    assert len(ex_list) == 1
    assert "Gian Piero Gasperini" in ex_list[0]["testo"]
    assert "Inter" in ex_list[0]["testo"]
    st.close()


def test_bollettino_tabella_vuota_degrada(tmp_path):
    st = Store(tmp_path / "bollettino_vuoto")
    a = MatchAnalysis(st)
    nw = a.team_news(1, "Roma", KO("2026-09-15 12:00"))
    assert nw["notizie"] == [] and nw["riserva"] == []
    assert nw["esaminate"] == 0 and nw["finestra"] == 7 and nw["pubblicate"] == 0
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


def test_google_news_params_italian_search_names():
    """Le query di Google News per club esteri usano i nomi comuni della stampa italiana."""
    from fda.sources.news import google_news_params

    assert "Bayern Monaco" in google_news_params("Bayern München")["q"]
    assert "Betis" in google_news_params("Real Betis")["q"]
    assert "Marsiglia" in google_news_params("Marseille")["q"]
    assert "Sporting Lisbona" in google_news_params("Sporting CP")["q"]
    assert "Colonia" in google_news_params("1. FC Köln")["q"]
    assert google_news_params("Inter")["q"] == '"Inter" calcio'


def test_parse_direct_sports_rss():
    """I feed RSS diretti attribuiscono gli articoli italiani solo ai club menzionati."""
    from fda.sources.news import parse_direct_sports_rss

    xml = """<rss version="2.0"><channel>
    <item>
      <title>Bologna, Palladino presenta la sfida di campionato</title>
      <link>https://sport.sky.it/calcio/bologna</link>
      <pubDate>Thu, 17 Sep 2026 10:00:00 GMT</pubDate>
      <description>Il nuovo tecnico rossoblù carica la squadra</description>
    </item>
    <item>
      <title>Bayern Monaco, nuovo stop muscolare per Kane</title>
      <link>https://www.ansa.it/calcio/bayern</link>
      <pubDate>Thu, 17 Sep 2026 11:00:00 GMT</pubDate>
      <description>L'attaccante salta la trasferta di Bundesliga</description>
    </item>
    <item>
      <title>Tennis: trionfo azzurro in Coppa Davis</title>
      <link>https://example.com/tennis</link>
      <pubDate>Thu, 17 Sep 2026 12:00:00 GMT</pubDate>
      <description>Grande vittoria a Bologna nel girone</description>
    </item>
    </channel></rss>"""

    team_map = {"bologna": 9857, "bayern monaco": 9823}
    diag = {}
    items = parse_direct_sports_rss(xml, team_map, "Sky Sport", diag)

    assert len(items) == 3   # 2 calcio + 1 con Bologna nel desc
    assert any(it["team_id"] == 9857 and "Palladino" in it["title"] for it in items)
    assert any(it["team_id"] == 9823 and "Bayern Monaco" in it["title"] for it in items)
    assert all(it["source"] == "Sky Sport" for it in items)
    assert diag.get("direct_feed_items") == 3
    assert diag.get("direct_feed_attribuiti") == 3


def test_da_sapere_strisce_e_digiuni(tmp_path):
    """«Da sapere» rileva strisce di imbattibilità, serie di sconfitte e digiuni dai dati."""
    st = Store(tmp_path / "strisce")
    # Squadra 1 (Roma): 5 vittorie consecutive
    # Squadra 2 (Inter): 3 sconfitte consecutive
    rows = [
        (1, 55, "2026", "1", KO("2026-09-01 18:00"), 1, "Roma", 3, "Milan", 2, 0, "finished", "fotmob"),
        (2, 55, "2026", "2", KO("2026-09-04 18:00"), 4, "Lazio", 1, "Roma", 0, 1, "finished", "fotmob"),
        (3, 55, "2026", "3", KO("2026-09-07 18:00"), 1, "Roma", 5, "Torino", 3, 1, "finished", "fotmob"),
        (4, 55, "2026", "4", KO("2026-09-10 18:00"), 6, "Genoa", 1, "Roma", 1, 2, "finished", "fotmob"),
        (5, 55, "2026", "5", KO("2026-09-13 18:00"), 1, "Roma", 7, "Parma", 2, 0, "finished", "fotmob"),
        # Inter: 3 sconfitte
        (6, 55, "2026", "3", KO("2026-09-07 18:00"), 2, "Inter", 3, "Milan", 0, 1, "finished", "fotmob"),
        (7, 55, "2026", "4", KO("2026-09-10 18:00"), 4, "Lazio", 2, "Inter", 2, 1, "finished", "fotmob"),
        (8, 55, "2026", "5", KO("2026-09-13 18:00"), 2, "Inter", 5, "Torino", 0, 2, "finished", "fotmob"),
        # Gara futura
        (9, 55, "2026", "6", KO("2026-09-17 18:00"), 1, "Roma", 2, "Inter", None, None, "scheduled", "fotmob"),
    ]
    st.write("fixtures", _fixtures(rows))
    st.write("match_info", pd.DataFrame([{"match_id": 9, "stadium_name": "Olimpico"}]))
    st.write("lineup", pd.DataFrame())
    an = MatchAnalysis(st)
    sapere = an.news_sapere(9, 1, "Roma", 2, "Inter", KO("2026-09-17 18:00"))

    assert any(s["titolo"] == "Striscia positiva" and "Roma" in s["testo"] and "5 partite consecutive" in s["testo"] for s in sapere)
    assert any(s["titolo"] == "Momento delicato" and "Inter" in s["testo"] and "3 sconfitte consecutive" in s["testo"] for s in sapere)
    st.close()


def test_da_sapere_bilancio_campo_e_uomo_gol(tmp_path):
    """I due fatti che tengono piena la card quando la stampa non copre la squadra.

    docs/25 §4: con il filtro lingua del 17/09/2026 la card restava vuota nel 78% delle
    partite di Ligue 1. «Dentro le mura / Lontano da casa» e «L'uomo gol» sono
    ricavati dai nostri dati e valgono in tutti e 7 i campionati.
    """
    st = Store(tmp_path / "campo")
    rows = [
        # Roma in casa: vittoria, pareggio, vittoria (3 gare interne)
        (1, 55, "2026", "1", KO("2026-09-01 18:00"), 1, "Roma", 3, "Milan", 2, 0, "finished", "fotmob"),
        (3, 55, "2026", "3", KO("2026-09-07 18:00"), 1, "Roma", 5, "Torino", 1, 1, "finished", "fotmob"),
        (5, 55, "2026", "5", KO("2026-09-13 18:00"), 1, "Roma", 7, "Parma", 2, 0, "finished", "fotmob"),
        # Inter in trasferta: vittoria, pareggio, sconfitta
        (2, 55, "2026", "2", KO("2026-09-04 18:00"), 4, "Lazio", 2, "Inter", 1, 2, "finished", "fotmob"),
        (4, 55, "2026", "4", KO("2026-09-10 18:00"), 6, "Genoa", 2, "Inter", 2, 1, "finished", "fotmob"),
        (6, 55, "2026", "6", KO("2026-09-14 18:00"), 8, "Napoli", 2, "Inter", 1, 1, "finished", "fotmob"),
        # gara futura: Roma-Inter
        (9, 55, "2026", "7", KO("2026-09-20 18:00"), 1, "Roma", 2, "Inter", None, None, "scheduled", "fotmob"),
    ]
    st.write("fixtures", _fixtures(rows))
    st.write("match_info", pd.DataFrame([{"match_id": 9, "stadium_name": "Olimpico"}]))
    st.write("player_stats", pd.DataFrame([
        {"match_id": 1, "team_id": 1, "player_id": 10, "player_name": "Dybala", "key": "goals", "value": 2.0, "total": None},
        {"match_id": 3, "team_id": 1, "player_id": 10, "player_name": "Dybala", "key": "goals", "value": 1.0, "total": None},
        {"match_id": 5, "team_id": 1, "player_id": 11, "player_name": "Pellegrini", "key": "goals", "value": 1.0, "total": None},
        # gol in una gara NON ancora giocata: non conta (la scheda non conosce il futuro)
        {"match_id": 9, "team_id": 1, "player_id": 11, "player_name": "Pellegrini", "key": "goals", "value": 9.0, "total": None},
        {"match_id": 2, "team_id": 2, "player_id": 20, "player_name": "Thuram", "key": "goals", "value": 1.0, "total": None},
        {"match_id": 2, "team_id": 2, "player_id": 20, "player_name": "Thuram", "key": "minutes_played", "value": 90.0, "total": None},
    ]))
    st.write("lineup", pd.DataFrame([
        # il capocannoniere della Roma è indisponibile per questa partita
        {"match_id": 9, "team_id": 1, "player_id": 10, "player_name": "Dybala", "role": "unavailable",
         "unavailability_type": "injury"},
    ]))
    an = MatchAnalysis(st)
    sapere = an.news_sapere(9, 1, "Roma", 2, "Inter", KO("2026-09-20 18:00"))
    # due squadre → due righe «L'uomo gol»: il titolo si ripete, il testo dice di chi
    testi = [(s["titolo"], s["testo"]) for s in sapere]

    assert ("Dentro le mura", "Roma in casa: 2 vittorie, 1 pareggio e 0 sconfitte in 3 gare (7 punti su 9, 2.33 a gara).") in testi
    assert ("Lontano da casa", "Inter in trasferta: 1 vittoria, 1 pareggio e 1 sconfitta in 3 gare (4 punti su 9, 1.33 a gara).") in testi
    # l'uomo gol conta solo le gare finite: Pellegrini resta a 1, Dybala a 3
    assert ("L'uomo gol", "il miglior marcatore di Roma in questo campionato è Dybala (3 gol), che però è indisponibile per questa gara (injury).") in testi
    assert ("L'uomo gol", "il miglior marcatore di Inter in questo campionato è Thuram (1 gol).") in testi
    st.close()


def test_da_sapere_bilancio_con_poche_gare_non_pubblica(tmp_path):
    """Con meno di 3 gare nel ruolo il bilancio è un caso, non un fatto: non si pubblica."""
    st = Store(tmp_path / "poche")
    rows = [
        (1, 55, "2026", "1", KO("2026-09-01 18:00"), 1, "Roma", 3, "Milan", 2, 0, "finished", "fotmob"),
        (2, 55, "2026", "2", KO("2026-09-05 18:00"), 1, "Roma", 4, "Sassuolo", 1, 0, "finished", "fotmob"),
        (3, 55, "2026", "3", KO("2026-09-09 18:00"), 1, "Roma", 2, "Inter", None, None, "scheduled", "fotmob"),
    ]
    st.write("fixtures", _fixtures(rows))
    st.write("match_info", pd.DataFrame([{"match_id": 3, "stadium_name": "Olimpico"}]))
    st.write("player_stats", pd.DataFrame())
    st.write("lineup", pd.DataFrame())
    an = MatchAnalysis(st)
    sapere = an.news_sapere(3, 1, "Roma", 2, "Inter", KO("2026-09-09 18:00"))
    assert not any(s["titolo"] in ("Dentro le mura", "Lontano da casa") for s in sapere)
    st.close()


def test_da_sapere_porta_e_finale(tmp_path):
    """«Porta inviolata» e «Finale da brividi»: contano solo le gare già giocate."""
    st = Store(tmp_path / "porta")
    # Roma (id 1) in casa: 6 gare, 3 senza gol subiti, 4 gol subiti di cui 3 dopo il 75'
    rows = [
        (1, 55, "2026", "1", KO("2026-09-01 18:00"), 1, "Roma", 3, "Verona", 2, 0, "finished", "fotmob"),
        (2, 55, "2026", "2", KO("2026-09-04 18:00"), 1, "Roma", 4, "Genoa", 1, 0, "finished", "fotmob"),
        (3, 55, "2026", "3", KO("2026-09-07 18:00"), 1, "Roma", 5, "Milan", 3, 2, "finished", "fotmob"),
        (4, 55, "2026", "4", KO("2026-09-10 18:00"), 1, "Roma", 6, "Inter", 0, 1, "finished", "fotmob"),
        (5, 55, "2026", "5", KO("2026-09-13 18:00"), 1, "Roma", 7, "Lazio", 1, 1, "finished", "fotmob"),
        (6, 55, "2026", "6", KO("2026-09-16 18:00"), 1, "Roma", 8, "Parma", 2, 0, "finished", "fotmob"),
        (7, 55, "2026", "7", KO("2026-09-20 18:00"), 1, "Roma", 2, "Napoli", None, None, "scheduled", "fotmob"),
    ]
    st.write("fixtures", _fixtures(rows))
    st.write("match_info", pd.DataFrame([{"match_id": 7, "stadium_name": "Olimpico"}]))
    st.write("player_stats", pd.DataFrame())
    st.write("lineup", pd.DataFrame())
    st.write("events", pd.DataFrame([
        # gol subiti dalla Roma: 78' e 85' (Milan), 12' (Inter), 88' (Lazio)
        {"match_id": 3, "type": "Goal", "minute": 78, "is_home": False, "player_name": "Leao"},
        {"match_id": 3, "type": "Goal", "minute": 85, "is_home": False, "player_name": "Gimenez"},
        {"match_id": 4, "type": "Goal", "minute": 12, "is_home": False, "player_name": "Thuram"},
        {"match_id": 5, "type": "Goal", "minute": 88, "is_home": False, "player_name": "Zaccagni"},
        # un gol della Roma: non conta fra quelli subiti
        {"match_id": 3, "type": "Goal", "minute": 8, "is_home": True, "player_name": "Dybala"},
    ]))
    an = MatchAnalysis(st)
    sapere = an.news_sapere(7, 1, "Roma", 2, "Napoli", KO("2026-09-20 18:00"))
    testi = [(s["titolo"], s["testo"]) for s in sapere]

    assert ("Porta inviolata", "Roma ha chiuso la porta in 3 gare su 6.") in testi
    assert ("Finale da brividi",
            "Roma ha subito 3 dei 4 gol dopo il 75' (il 75% di quelli presi fin qui).") in testi
    st.close()


def test_da_sapere_tetto_righe(tmp_path):
    """Oltre 8 righe la card diventa un elenco: i fatti di dettaglio non entrano."""
    st = Store(tmp_path / "tetto")
    rows = []
    for i in range(1, 10):                      # 9 gare finite, Roma sempre in casa
        rows.append((i, 55, "2026", str(i), KO(f"2026-09-0{i % 9 + 1} 18:00"), 1, "Roma",
                     3, "Verona", 2, 0 if i % 2 else 1, "finished", "fotmob"))
    rows.append((99, 55, "2026", "10", KO("2026-09-21 18:00"), 1, "Roma", 2, "Napoli",
                 None, None, "scheduled", "fotmob"))
    st.write("fixtures", _fixtures(rows))
    st.write("match_info", pd.DataFrame([{"match_id": 99, "stadium_name": "Olimpico"}]))
    st.write("player_stats", pd.DataFrame())
    st.write("lineup", pd.DataFrame())
    st.write("events", pd.DataFrame())
    an = MatchAnalysis(st)
    sapere = an.news_sapere(99, 1, "Roma", 2, "Napoli", KO("2026-09-21 18:00"))
    assert len(sapere) <= an.SAPERE_MAX
    st.close()
