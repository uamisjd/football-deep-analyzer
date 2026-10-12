"""Test offline dei blocchi docs/21: panchina+posta in gioco (P0-1), coppe (P1-4), notizie (P1-5).

Nessuna rete: store sintetici in tmp_path, come negli altri test del sito.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest

from fda.site.analysis import MatchAnalysis, news_quiet_line, news_subjects, news_title_key
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
    # partita dell'archivio: l'attuale allenatore dell'Inter era su un'ALTRA panchina
    # (Milan) e ha incrociato quello della Roma → precedente tra i due allenatori, non
    # uno scontro fra i due club (`docs/78` §7)
    (5, 55, "2026", "0", KO("2026-08-25 18:00"), 3, "Milan", 1, "Roma", 2, 1, "finished", "fotmob"),
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
    # l'incrocio fra i due: Milan–Roma dell'archivio, con l'allenatore dell'Inter odierno
    # (Coach Nuovo) sulla panchina del Milan e quello della Roma (Coach Stabile) sull'altra
    {"match_id": 5, "team_id": 3, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
    {"match_id": 5, "team_id": 1, "player_id": 300, "player_name": "Coach Stabile", "role": "coach"},
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
    assert c["matches"] == 4   # 25/08, 01/09, 09/09 e 13/09: sempre lo stesso allenatore


def test_stakes_etichette_e_interi(analysis):
    s = analysis.stakes("Inter")
    assert s["label"] == "corsa al titolo" and s["p_title_pct"] == "22" and s["p_top4_pct"] == "81"
    assert s["ucl_spots"] == 4 and s["ucl_legacy"] is True
    r = analysis.stakes("Roma")
    assert r["label"] == "lotta salvezza" and r["p_rel_pct"] == "41"
    assert analysis.stakes("Squadra Inesistente") is None


def test_stakes_usa_la_soglia_nuova_e_non_il_fallback(analysis):
    analysis.season_sim = SIM.assign(top_n=2, p_top_n=[0.55, 0.08])
    s = analysis.stakes("Inter")
    assert s["ucl_spots"] == 2 and s["ucl_legacy"] is False
    assert s["p_top_n_pct"] == "55"


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


def test_alias_stampa_normalizzati_sui_nomi_veri():
    """La query italiana si aggancia anche quando il nome FotMob è abbreviato o accentato.

    Misurato l'11/10/2026 (`docs/83` §1): «Köln», «Atlético Madrid» e «Nottm Forest» non
    incontravano nessuna chiave della mappa e la ricerca partiva col nome secco — le due
    squadre peggio coperte della stagione (2 notizie in 14 giorni) erano proprio due nomi
    abbreviati nei dati, «Nottm Forest» e «M'gladbach».
    """
    from fda.sources.news import google_news_params, italian_search_name
    assert "Colonia" in google_news_params("Köln")["q"]
    assert "Atletico Madrid" in google_news_params("Atlético Madrid")["q"]
    assert "Nottingham Forest" in google_news_params("Nottm Forest")["q"]
    assert "Gladbach" in google_news_params("M'gladbach")["q"]
    assert italian_search_name("Nacional") == '"Nacional Madeira"'
    assert italian_search_name("Squadra Sconosciuta") is None


def test_classifica_niente_collisioni_di_sottostringa():
    """Le parole chiave non pescano dentro altre parole (misura dell'11/10/2026, docs/83 §2).

    Sono i quattro casi trovati contando le voci di «Clima del club»: «Élite» dentro
    spogliatoio (calcio a 5), «fischierà» dentro tifoseria (designazione arbitrale), «Futuro
    del…» dentro la regola spagnola «futuro de», «rifatto» dentro «rifa», e il nome proprio
    «Berlusconi» che da solo faceva categoria su un titolo di opinione.
    """
    assert classify_news("Calcio a 5 Serie A2 Élite. Lazio, avvio positivo")[0] != "spogliatoio"
    assert classify_news("Perugia-Vado, fischierà Vincenzi di Bologna")[0] != "tifo"
    assert classify_news("Futuro del Dall'Ara, il sindaco Lepore dà il via al confronto")[0] \
        != "allenatore"
    assert classify_news("Il murale di Franco Baresi vandalizzato a Casa Milan sarà rifatto"
                         )[0] != "spogliatoio"
    assert classify_news('Brocchi: "Non è più il Milan di Berlusconi e Galliani"'
                         )[0] != "spogliatoio"
    # i casi veri restano: i fischi della tifoseria sono tifoseria, il futuro del tecnico è
    # panchina, la protesta nei confronti della società resta un fatto di società
    assert classify_news("Fischi e striscioni dei tifosi: protesta allo stadio")[0] == "tifo"
    assert classify_news("Il futuro del tecnico è in bilico: contatto con un nuovo allenatore"
                         )[0] == "allenatore"


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
    assert b["tenure_line"] == ("panchina nuova: 2ª gara dal subentro a Coach Vecchio "
                                 "(dopo la gara del 01/09)")
    # una sola gara finita col coach corrente (Inter-Milan 2-2): 1,0 punti/gara
    assert b["coach_ppg_line"] == "1,0 punti/gara su 1 gara finita"
    # bilancio dell'ALLENATORE con l'avversaria (docs/78 §10): lui con qualunque club
    # contro la Roma — la gara Milan-Roma dell'archivio, quando era sulla panchina
    # del Milan. Mai il bilancio fra i due club (che è nella card «Precedenti»).
    assert b["coach_vs_opp_line"] == ("da allenatore contro Roma: 1 gara nel nostro "
                                      "archivio (1V 0N 0P)")
    # incroci tra i due ALLENATORI: si sono trovati su panchine opposte in Milan-Roma
    assert b["coach_vs_coach_line"] == ("un solo incrocio in panchina con Coach Stabile: "
                                        "1V 0N 0P")
    # la stessa gara, letta dalla panchina della Roma: speculare
    br = analysis.bench_deep(1, "Roma", 2, "Inter", KO("2026-09-14 00:00"))
    assert br["coach_vs_coach_line"] == ("un solo incrocio in panchina con Coach Nuovo: "
                                         "0V 0N 1P")
    # l'allenatore della Roma ha affrontato l'Inter una volta: Roma-Inter 1-0
    assert br["coach_vs_opp_line"] == ("da allenatore contro Inter: 1 gara nel nostro "
                                       "archivio (1V 0N 0P)")
    # e il bilancio fra i due CLUB non compare nella cella dell'allenatore
    assert "bilancio con" not in b and "bilancio con" not in br
    assert b["table_line"] == ("2º con 7 punti · 3 punti sopra la zona retrocessione · "
                               "in zona UCL (prime 4)")
    # la riga virtuale applica i punti del risultato a entrambe le squadre e copre i tre
    # esiti (`docs/78` §1): con la sconfitta la Roma incassa i 3 punti, l'Inter resta 2ª
    assert b["virtual_line"] == ("con una vittoria 1º · con un pareggio 2º · "
                                 "con una sconfitta 2º "
                                 "(classifica virtuale, altre gare in sospeso)")


def test_bench_deep_non_conta_la_partita_stessa(tmp_path):
    """`docs/78` §7-§8: il filtro inclusivo faceva entrare la gara in corso fra i precedenti.

    Con il calendario che la dà già finita (dettagli vecchi) e la scheda ancora resa come
    pre-partita, il rendimento e i precedenti includevano **questa** partita: 22 schede
    pubblicavano il risultato in corso. Ora il passato è rigorosamente «prima».
    """
    rows = _fixtures([
        (1, 55, "2026", "1", KO("2026-09-05 18:00"), 2, "Inter", 3, "Milan", 2, 2, "finished", "fotmob"),
        # la partita della scheda: finita nel calendario, con una goleada che si vedrebbe
        (6, 55, "2026", "6", KO("2026-09-20 18:00"), 2, "Inter", 4, "Lazio", 7, 0, "finished", "fotmob"),
    ])
    lineup = pd.DataFrame([
        {"match_id": 1, "team_id": 2, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
        {"match_id": 6, "team_id": 2, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
    ])
    st = Store(tmp_path / "processed")
    st.write("fixtures", rows)
    st.write("lineup", lineup)
    st.write("season_sim", SIM)
    st.write("fotmob_standings", STANDINGS)
    ma = MatchAnalysis(st)
    b = ma.bench_deep(2, "Inter", 4, "Lazio", KO("2026-09-20 18:00"))
    # solo la gara del 05/09 (2-2): 1,0 punti/gara. Con il leak sarebbe 2,0 su 2 gare.
    assert b["coach_ppg_line"] == "1,0 punti/gara su 1 gara finita"
    # il 7-0 con la Lazio è QUESTA partita: non è un precedente dell'allenatore
    assert b["coach_vs_opp_line"] is None
    assert b["coach_vs_coach_line"] is None
    st.close()


def test_bench_deep_gol_a_gara_e_stima_di_stagione(analysis):
    """`docs/78` §12: gol fatti/subiti delle sue partite e stima di fine stagione.

    Il rendimento da solo non dice *come* (2,0 gol fatti e 2,0 subiti nell'unica gara
    finita con lui); la stima pubblica i «Pt attesi» e la «Media pos.» della simulazione,
    che prima non comparivano da nessuna parte nella scheda.
    """
    b = analysis.bench_deep(2, "Inter", 1, "Roma", KO("2026-09-14 00:00"))
    assert b["coach_goals_line"] == "con lui 2,0 gol fatti e 2,0 subiti a gara"
    assert b["season_line"] == ("stima di fine stagione: 78,0 punti attesi · "
                                "2,1º posto in media")
    # con l'etichetta «proiezione:» la posizione media è già nell'etichetta: non si ripete
    analysis.season_sim = SIM.assign(top_n=4, p_top_n=[0.05, 0.04], p_title=[0.01, 0.01],
                                     p_rel=[0.02, 0.02], pos_mean=[11.4, 12.0],
                                     exp_points=[52.0, 50.0])
    r = analysis.bench_deep(1, "Roma", 2, "Inter", KO("2026-09-14 00:00"))
    assert r["stakes"]["label"] == "proiezione: 12,0º posto in media"
    assert r["season_line"] == "stima di fine stagione: 50,0 punti attesi"


def test_la_partita_stessa_non_entra_in_rendimento_nei_gol_nei_precedenti(analysis):
    """`docs/78` §8: il passato è **rigorosamente** prima di questa partita.

    Su 22 schede del 2026-10-11 la gara era già finita nel calendario ma i dettagli
    dicevano «scheduled»: col filtro inclusivo la card contava la partita stessa fra i
    precedenti e nel rendimento («un solo incrocio in panchina: 1V 0N 0P», cioè il
    risultato della gara in corso). Qui la partita dell'Inter è finita 2-1: con `<` il
    rendimento resta quello della sola gara precedente (2-2 col Milan → 1,0), con `<=`
    diventerebbe 2,0 su due gare.
    """
    fx = FX.copy()
    fx.loc[fx.match_id == 4, ["home_goals", "away_goals", "status"]] = [2, 1, "finished"]
    analysis.fixtures = fx
    b = analysis.bench_deep(2, "Inter", 1, "Roma", KO("2026-09-13 18:00"))
    assert b["coach_ppg_line"] == "1,0 punti/gara su 1 gara finita"
    assert b["coach_goals_line"] == "con lui 2,0 gol fatti e 2,0 subiti a gara"
    # i precedenti reali (25/08, Milan–Roma) restano quelli: «1 gara», «un solo incrocio».
    # Col filtro inclusivo la partita stessa (13/09, Inter–Roma, 2-1) entrerebbe in queste
    # due righe e diventerebbero «2 gare»/«2 incroci» — il risultato della partita in corso
    # spacciato per precedente.
    assert b["coach_vs_opp_line"] == "da allenatore contro Roma: 1 gara nel nostro archivio (1V 0N 0P)"
    assert b["coach_vs_coach_line"] == "un solo incrocio in panchina con Coach Stabile: 1V 0N 0P"


def test_bench_deep_zona_retrocessione_e_nationalita(analysis):
    b = analysis.bench_deep(4, "Lazio", 1, "Roma", KO("2026-09-14 00:00"))
    assert "dalla salvezza diretta" in b["table_line"]   # ultima piazza: distanza dalla salvezza
    assert "con una vittoria" in b["virtual_line"]
    r = analysis.bench_deep(1, "Roma", 2, "Inter", KO("2026-09-14 00:00"))
    assert r["tenure_line"] == ("panchina invariata da 4 gare nel nostro archivio "
                                 "(dal 25/08)")
    # 1-0, 0-1 e 1-2 nell'archivio: 3 punti su 3 gare finite
    assert r["coach_ppg_line"] == "1,0 punti/gara su 3 gare finite"


def test_stakes_arrotonda_come_proiezioni_non_col_banker(analysis):
    """`docs/78` §12: stessa convenzione della pagina Proiezioni (`mc_percent`, mezzo in su).

    Con il `round()` di Python (banker's rounding) 0,5% diventava «0%» e 62,5% «62%», mentre
    Proiezioni stampava «1%» e «63%»: quattro numeri diversi fra le due pagine nella build
    del 2026-10-11.
    """
    from fda.models.season_sim import mc_percent, mc_percent_str
    analysis.season_sim = SIM.assign(p_title=[0.005, 0.625], p_rel=[0.625, 0.004])
    s = analysis.stakes("Inter")
    assert round(0.5) == mc_percent(0.005) - 1          # il vecchio comportamento differiva
    assert s["p_title_pct"] == "1" and s["p_rel_pct"] == "63"
    r = analysis.stakes("Roma")
    assert r["p_title_pct"] == "63"
    # 0,4% non è «0%» (impossibile): è «<1», un valore non nullo sotto il mezzo punto
    assert r["p_rel_pct"] == "<1" and mc_percent_str(0.004) == "<1"
    assert mc_percent_str(0.0) == "0" and mc_percent_str(0.999) == ">99"
    assert mc_percent_str(1.0) == "100"


def test_bench_deep_etichetta_champions_e_proiezione(analysis):
    """`docs/78` §2: l'etichetta segue il numero pubblicato, non un aggettivo di posizione.

    Con 4 posti UCL la soglia dei 35% è la Champions (prima diceva «corsa all'Europa»
    accanto a un «UCL (prime 4)»); quando nessuna postura è in bilico l'etichetta è la
    proiezione di posizione media, la stessa «Media pos.» della pagina Proiezioni.
    """
    analysis.season_sim = SIM.assign(top_n=4, p_top_n=[0.61, 0.05], p_title=[0.02, 0.01],
                                     p_rel=[0.0, 0.02], pos_mean=[2.3, 11.4])
    i = analysis.stakes("Inter")
    assert i["label"] == "corsa alla Champions" and i["ucl_legacy"] is False
    r = analysis.stakes("Roma")
    assert r["label"] == "proiezione: 11,4º posto in media"
    # uno snapshot storico (senza top_n) resta leggibile e non inventa la soglia
    leg = SIM.assign(p_top4=[0.9, 0.1], p_top_n=[float("nan")] * 2)
    analysis.season_sim = leg.drop(columns=["top_n"], errors="ignore")
    assert analysis.stakes("Inter")["ucl_legacy"] is True


def test_bench_deep_virtuale_conta_l_avversaria(tmp_path):
    """La sconfitta fa incassare i 3 punti all'avversaria: se la scavalca, la posizione scende.

    Caso reale che ha originato il fix (`docs/78` §1): Feyenoord «con una sconfitta 1º»
    mentre coi punti dell'avversaria sarebbe 2º — 36 celle su 208 sbagliate di una posizione.
    """
    st = Store(tmp_path / "avversaria")
    st.write("fixtures", FX)
    st.write("lineup", LINEUP)
    st.write("season_sim", SIM)
    st.write("fotmob_standings", pd.DataFrame([
        {"league_code": "ITA1", "team_id": 1, "team_name": "Roma", "rank": 1, "played": 3,
         "wins": 2, "draws": 1, "losses": 0, "goals_for": 6, "goals_against": 2, "goal_diff": 4, "points": 7},
        {"league_code": "ITA1", "team_id": 2, "team_name": "Inter", "rank": 2, "played": 3,
         "wins": 2, "draws": 0, "losses": 1, "goals_for": 6, "goals_against": 4, "goal_diff": 2, "points": 6},
        {"league_code": "ITA1", "team_id": 3, "team_name": "Milan", "rank": 3, "played": 3,
         "wins": 1, "draws": 0, "losses": 2, "goals_for": 3, "goals_against": 5, "goal_diff": -2, "points": 3},
        {"league_code": "ITA1", "team_id": 4, "team_name": "Lazio", "rank": 4, "played": 3,
         "wins": 0, "draws": 1, "losses": 2, "goals_for": 2, "goals_against": 6, "goal_diff": -4, "points": 1},
    ]))
    b = MatchAnalysis(st).bench_deep(2, "Inter", 1, "Roma", KO("2026-09-14 00:00"))
    assert b["table_line"].startswith("2º con 6 punti · ")
    # vittoria: Inter 9, Roma 7 → 1ª; pareggio: 7 e 8 → 2ª; sconfitta: Roma 10 → 2ª
    assert "con una vittoria 1º · con un pareggio 2º · con una sconfitta 2º" in b["virtual_line"]


def test_bench_deep_subentro_senza_gare_dichiarato(analysis):
    """Un allenatore appena subentrato non ha gare finite: la cella lo dice, non tace."""
    analysis.lineup = pd.concat([
        LINEUP,
        pd.DataFrame([{"match_id": 2, "team_id": 3, "player_id": 555,
                       "player_name": "Coach Precedente", "role": "coach"},
                      {"match_id": 4, "team_id": 3, "player_id": 777,
                       "player_name": "Coach Appena Arrivato", "role": "coach"}]),
    ], ignore_index=True)
    b = analysis.bench_deep(3, "Milan", 1, "Roma", KO("2026-09-14 00:00"))
    assert b["coach_ppg_line"] is None and b["coach_ppg_absent"] is True
    assert b["tenure_line"] == ("panchina nuova: 1ª gara dal subentro a Coach Precedente "
                                 "(dopo la gara del 05/09)")


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
    """Con una squalifica fra gli assenti la riga dice «assenze pesanti» (docs/81 §10).

    Nel fixture ci sono 3 infortuni e 1 squalifica: «infermeria» sarebbe la parola
    sbagliata, perché vale solo quando fra gli indisponibili non c'è nessuno squalificato.
    """
    rows = mood_analysis.club_mood(8, 4, "Lazio", KO("2026-09-16 18:00"))
    texts = [r["text"] for r in rows]
    assert any(t.startswith("crisi di risultati: 3 sconfitte consecutive") for t in texts)
    assert any(t.startswith("assenze pesanti: 4 assenti") for t in texts)
    assert not any(t.startswith("infermeria pesante") for t in texts)
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


def test_clima_striscia_intera_non_finestra_di_cinque(tmp_path):
    """`docs/81` §1: «imbattuta da N» conta la striscia intera, non le ultime cinque gare.

    Con la finestra di ``form()`` (5 gare) una squadra imbattuta da sette pubblicava «da 5»:
    un pavimento travestito da numero, misurato il 2026-10-11 su 14 celle su 154 (Inter 5
    contro 6, Barcelona 5 contro 8). Qui la striscia è di 7 gare e la finestra ne conterebbe 5.
    """
    st = Store(tmp_path / "striscia")
    st.write("fixtures", _fixtures([
        (200 + i, 55, "2026", str(i), KO(f"2026-08-{10 + i:02d} 18:00"), 4, "Lazio", 9, "Ospiti",
         2, 0, "finished", "fotmob")
        for i in range(7)          # sette vittorie consecutive, dal 10 al 16 agosto
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 200, "team_id": 4, "player_id": 1, "player_name": "Coach",
         "role": "coach", "market_value_eur": None, "unavailability_type": None,
         "expected_return": None},
    ]))
    testi = [r["text"] for r in MatchAnalysis(st).club_mood(207, 4, "Lazio", KO("2026-09-20 18:00"))]
    # il perimetro è dichiarato nella riga (docs/81 §2): le strisce sono di campionato
    assert any(t == "imbattuta da 7 gare in campionato: clima di fiducia" for t in testi), testi
    assert not any("imbattuta da 5" in t for t in testi), testi


def test_clima_ultima_gara_sconfitta_pesante_ed_espulsione(tmp_path):
    """`docs/81` §9: dall'ultima gara di campionato escono la sconfitta pesante e il rosso.

    Misurato il 2026-10-11 su 154 celle: 13 con una sconfitta per 3+ gol (12 non già in
    crisi), 11 con un'espulsione nell'ultima gara. La soglia della sconfitta è 3 gol di
    scarto; il minuto dell'espulsione esce solo se la fonte lo pubblica.
    """
    st = Store(tmp_path / "ultimagara")
    st.write("fixtures", _fixtures([
        # Prova: ultima gara persa 0-3 (pesante) con un'espulsione al 53'
        (400, 55, "2026", "1", KO("2026-09-01 18:00"), 7, "Prova", 9, "Ospiti", 2, 0, "finished", "fotmob"),
        (401, 55, "2026", "2", KO("2026-09-08 18:00"), 7, "Prova", 9, "Ospiti", 0, 3, "finished", "fotmob"),
        (402, 55, "2026", "3", KO("2026-09-20 18:00"), 7, "Prova", 9, "Ospiti", None, None, "scheduled", "fotmob"),
        # Sereni: ultima gara persa 1-2 (non pesante), nessun rosso
        (500, 55, "2026", "1", KO("2026-09-01 18:00"), 8, "Sereni", 9, "Ospiti", 2, 0, "finished", "fotmob"),
        (501, 55, "2026", "2", KO("2026-09-08 18:00"), 8, "Sereni", 9, "Ospiti", 1, 2, "finished", "fotmob"),
        (502, 55, "2026", "3", KO("2026-09-20 18:00"), 8, "Sereni", 9, "Ospiti", None, None, "scheduled", "fotmob"),
    ]))
    st.write("lineup", pd.DataFrame([
        {"match_id": 400, "team_id": 7, "player_id": 1, "player_name": "Coach", "role": "coach",
         "market_value_eur": None, "unavailability_type": None, "expected_return": None},
        {"match_id": 500, "team_id": 8, "player_id": 2, "player_name": "Coach", "role": "coach",
         "market_value_eur": None, "unavailability_type": None, "expected_return": None},
    ]))
    st.write("events", pd.DataFrame([
        # il rosso è della squadra di casa (Prova); is_home distingue le due squadre
        {"match_id": 401, "type": "Card", "minute": 53, "minute_added": None, "is_home": True,
         "player_id": 77, "player_name": "Espulso", "card": "Red"},
        {"match_id": 401, "type": "Card", "minute": 70, "minute_added": None, "is_home": False,
         "player_id": 78, "player_name": "Avversario", "card": "Yellow"},
    ]))
    an = MatchAnalysis(st)
    prova = [r["text"] for r in an.club_mood(402, 7, "Prova", KO("2026-09-20 18:00"))]
    assert "sconfitta pesante nell'ultima gara di campionato: 0-3" in prova, prova
    assert "espulsione nell'ultima gara di campionato al 53'" in prova, prova
    sereni = [r["text"] for r in an.club_mood(502, 8, "Sereni", KO("2026-09-20 18:00"))]
    assert not any(t.startswith(("sconfitta pesante", "espulsione")) for t in sereni), sereni


def test_clima_panchina_nuova_solo_se_recente(tmp_path):
    """`docs/81` §3: «panchina nuova» vale solo con l'allenatore in carica da ≤3 gare.

    Senza soglia la riga restava accesa per tutta la stagione (misurato: Estrela da Amadora
    alla 7ª gara dal subentro dichiarava ancora uno «shock»), mentre la voce «Panchina nuova»
    di «Da sapere» usa ≤3 (``news_sapere``). La soglia è una sola, condivisa.
    """
    def store(cartella, prima_del_nuovo):
        """Dieci gare vinte (nessuna striscia da segnalare); il nuovo coach entra alla gara
        ``prima_del_nuovo``, quindi le sue gare in carica prima del 20/09 sono ``10 − i``."""
        st = Store(cartella)
        st.write("fixtures", _fixtures([
            (mid, 55, "2026", str(i), KO(f"2026-08-{10 + i:02d} 18:00"),
             7, "Prova", 9, "Ospiti", 2, 0, "finished", "fotmob")
            for i, mid in enumerate(range(300, 310))
        ]))
        st.write("lineup", pd.DataFrame([
            {"match_id": mid, "team_id": 7, "player_id": 1 if i < prima_del_nuovo else 2,
             "player_name": "Coach Vecchio" if i < prima_del_nuovo else "Coach Nuovo",
             "role": "coach", "market_value_eur": None, "unavailability_type": None,
             "expected_return": None}
            for i, mid in enumerate(range(300, 310))
        ]))
        return MatchAnalysis(st)

    # nuovo dalla 7ª gara (indice 6): 4 gare in carica → la riga non si pubblica
    testi = [r["text"] for r in store(tmp_path / "vecchia", 6)
             .club_mood(310, 7, "Prova", KO("2026-09-20 18:00"))]
    assert not any(t.startswith("panchina nuova") for t in testi), testi
    # nuovo dalla 9ª gara (indice 8): 2 gare in carica → il segnale c'è
    testi = [r["text"] for r in store(tmp_path / "nuova", 8)
             .club_mood(310, 7, "Prova", KO("2026-09-20 18:00"))]
    assert any(t.startswith("panchina nuova: il cambio di allenatore") for t in testi), testi


def test_clima_infermeria_concordanza_titolari(mood_analysis, monkeypatch):
    """«di cui 1 titolare abituale», non «di cui 1 titolari abituali» (audit 18/09/2026).

    Sul sito pubblicato la forma sbagliata compariva 25 volte su 22 schede: era l'unica
    frase del portale a stampare il contatore senza ``it_plural``, mentre ``match.html``
    (riga indisponibili) e ``_sapere_assenze`` la concordavano già. Il test fissa il peso
    dell'infermeria e verifica solo la concordanza, che è la riga corretta.
    """
    def peso(n_titolari):
        def _f(self, match_id, team_id):
            return {"n": 4, "starters_out": n_titolari, "contrib_lost_p90": 0.9}
        return _f

    for n, attesa in ((1, "di cui 1 titolare abituale"), (2, "di cui 2 titolari abituali")):
        monkeypatch.setattr(MatchAnalysis, "absences_weight", peso(n))
        testi = [r["text"] for r in mood_analysis.club_mood(8, 4, "Lazio", KO("2026-09-16 18:00"))]
        assert any(attesa in t for t in testi), (n, testi)
        assert not any("1 titolari" in t for t in testi), testi


def test_concordanza_uno_assente_giorno_gara(mood_analysis, monkeypatch):
    """«1 assente», «un solo giorno», «in 1 gara»: i tre contatori che possono valere 1.

    Il gate ``verify_site`` del 19/09/2026 ha fermato il daily su
    ``partite/5749682.html: concordanza '1 assenti'``. La soglia della riga «infermeria
    pesante» **non** è il numero di assenti: bastano 2 titolari abituali fuori **o** 0,5
    xG+xA a gara in meno, quindi la riga scatta anche con un solo indisponibile — un
    giocatore che da solo porta via mezza occasione a partita — e la frase stampava il
    plurale. Gli altri due punti della stessa classe (un giorno di riposo, la prima
    giornata di campionato) erano raggiungibili allo stesso modo e non erano ancora passati
    dai dati (docs/40 §1, punti 1-3).
    """
    def peso(n_assenti, titolari):
        def _f(self, match_id, team_id):
            # ``starters_out`` è contato **dentro** gli ``n`` assenti: con n=1 la soglia che
            # fa scattare la riga è il contributo (0,5 xG+xA/gara), non i titolari
            return {"n": n_assenti, "starters_out": titolari, "contrib_lost_p90": 0.9}
        return _f

    testi: list[str] = []
    for n, titolari, attesa in ((1, 1, "assenze pesanti: 1 assente,"),
                                (4, 2, "assenze pesanti: 4 assenti,")):
        monkeypatch.setattr(MatchAnalysis, "absences_weight", peso(n, titolari))
        testi = [r["text"] for r in mood_analysis.club_mood(8, 4, "Lazio", KO("2026-09-16 18:00"))]
        assert any(attesa in t for t in testi), (n, testi)
    assert not any("1 assenti" in t for t in testi), testi

    # narrativa: la soglia del segnale è ≤3 giorni, quindi il caso 1 esiste
    base = {"home_name": "Inter", "away_name": "Milan"}
    assert next(s for s in MatchAnalysis.narrative({**base, "home_rest": 1})
                if "riposo" in s) == "Inter gioca dopo un solo giorno di riposo."
    assert next(s for s in MatchAnalysis.narrative({**base, "home_rest": 3})
                if "riposo" in s) == "Inter gioca dopo soli 3 giorni di riposo."

    # confronto di stagione: alla prima giornata ``played`` vale 1
    cmp = mood_analysis.season_compare(
        {"rank": 3, "played": 1, "points": 3, "goals_for": 2, "goals_against": 0,
         "goal_diff": 2, "wins": 1, "draws": 0, "losses": 0},
        {"rank": 9, "played": 4, "points": 5, "goals_for": 4, "goals_against": 4,
         "goal_diff": 0, "wins": 1, "draws": 2, "losses": 1})
    punti = next(r for r in cmp["rows"] if r["label"] == "Punti")
    assert punti["h"] == "3 in 1 gara" and punti["a"] == "5 in 4 gare"


def test_fattori_chiave_concordanza_singolare(mood_analysis, monkeypatch):
    """In «Fattori che spostano la partita» 1 assente, 1 titolare e 1 giorno di riposo usano
    la forma singolare: nessuna violazione di concordanza ('1 assenti', '1 giorni').

    Dal 7/10/2026 (`docs/57` §2) la card ha **una riga per fattore**: gli indisponibili sono una
    riga con le due squadre, il riposo è «Riposo corto» e c'è solo quando è ≤4 giorni.
    """
    from scripts.verify_site import AGREEMENT

    monkeypatch.setattr(MatchAnalysis, "absences_weight",
                        lambda self, mid, tid: {"n": 1, "starters_out": 1, "contrib_lost_p90": 0.0})
    monkeypatch.setattr(MatchAnalysis, "rest_days", lambda self, tid, ko: 1)

    res = mood_analysis.fattori_chiave(8, 4, "Lazio", 3, "Milan", KO("2026-09-16 18:00"), None)
    assert res and res["rows"]

    for row in res["rows"]:
        for key, val in row.items():
            if isinstance(val, str):
                m = AGREEMENT.search(val)
                assert not m, f"Violazione di concordanza nel campo {key}: {m.group(0)!r} in {val!r}"

    etichette = [r["label"] for r in res["rows"]]
    assert len(etichette) == len(set(etichette)), f"righe ripetute nella card: {etichette}"

    inf = next(r for r in res["rows"] if r["label"] == "Indisponibili")
    assert inf["home"] == inf["away"] == "1 assente · 1 titolare"

    riposo = next(r for r in res["rows"] if r["label"] == "Riposo corto")
    assert riposo["home"] == riposo["away"] == "1 giorno"
    assert "≤4 giorni" in riposo["impact"]
    assert res["soglie_testo"].startswith("valore dei titolari ≥1,5×")


def test_fattori_una_riga_per_fattore_e_riposo_solo_se_corto(mood_analysis, monkeypatch):
    """Il riposo lungo **non** è un fattore: con 20 giorni per entrambe le squadre la riga non
    esiste (era pubblicata su tutte le 66 schede del 7/10/2026, con due verdetti opposti —
    verde alla casa, rosso alla trasferta — per la stessa sosta).

    Verifica anche che ogni riga porti le **due** colonne (niente «—» in una delle due) e che
    il modello non sia una riga della tabella ma la nota in fondo.
    """
    monkeypatch.setattr(MatchAnalysis, "absences_weight",
                        lambda self, mid, tid: {"n": 1, "starters_out": 1, "contrib_lost_p90": 0.0})
    monkeypatch.setattr(MatchAnalysis, "rest_days", lambda self, tid, ko: 20)

    res = mood_analysis.fattori_chiave(8, 4, "Lazio", 3, "Milan", KO("2026-09-16 18:00"), None)
    assert res and res["rows"]
    assert not any("Riposo" in r["label"] for r in res["rows"]), "il riposo lungo non è un fattore"
    assert any("riposo 20 giorni e 20 giorni" in s for s in res["sotto_soglia"]), res["sotto_soglia"]
    for row in res["rows"]:
        assert row["home"] and row["away"], f"riga con una colonna vuota: {row}"
        assert "bar_pct" not in row, "la barra percentuale non spiegata è stata rimossa (docs/57 §2)"
    assert "Modello statistico" not in [r["label"] for r in res["rows"]]


def test_narrativa_non_ripete_i_fattori_della_tabella(mood_analysis):
    """«Un dato in un posto»: se il fattore è una riga della tabella dei Fattori, la narrativa
    dell'analisi pre-partita non lo ricopia con gli stessi numeri (prima il rapporto di valore
    e il PPDA comparivano due volte nella stessa pagina, `docs/57` §1).
    """
    ma = mood_analysis
    ctx = {
        "home_name": "Alpha", "away_name": "Beta",
        "prediction": {"p_home": 0.5, "p_draw": 0.3, "p_away": 0.2, "lambda_home": 1.4,
                       "lambda_away": 1.1, "p_over25": 0.5, "p_btts": 0.5},
        "clash": {"rows": [{"label": "PPDA (↓ = più pressing)", "h": 8.0, "a": 14.0},
                           {"label": "xG da palle inattive (quota)", "h": 30, "a": 30}]},
        "home_value": 200_000_000, "away_value": 40_000_000,
        "fattori_chiave": {"rows": [{"label": "Pressing (PPDA)"},
                                    {"label": "Valore di mercato titolari"}]},
        "status": "scheduled",
    }
    testo = " ".join(ma.narrative(ctx))
    assert "preme molto più" not in testo, testo
    assert "squilibrio mercato" not in testo, testo

    # senza la tabella (gara finita o dati mancanti) la narrativa torna a dirlo da sola
    ctx["fattori_chiave"] = None
    testo2 = " ".join(ma.narrative(ctx))
    assert "preme molto più" in testo2 and "squilibrio mercato" in testo2


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


def test_da_sapere_senza_strisce_che_vivono_nel_clima(tmp_path):
    """`docs/81` §8: le strisce non stanno più in «Da sapere» — vivono solo nel «Clima».

    Erano in due card della stessa pagina su 45 celle su 154, con due soglie diverse
    («Digiuno di vittorie» da 5 gare contro «non vince da» da 4). Regola `docs/30`: un dato
    in un posto. Il test fissa la rimozione: le tre voci spariscono, i fatti di rendimento
    (bilancio in casa/fuori) restano.
    """
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

    titoli = {s["titolo"] for s in sapere}
    assert not {"Striscia positiva", "Momento delicato", "Digiuno di vittorie"} & titoli, titoli
    # i fatti che restano tengono in piedi la card (misurato: 77 schede su 77 ne hanno almeno uno)
    assert "Dentro le mura" in titoli or "Lontano da casa" in titoli, titoli
    # e la stessa striscia è pubblicata dal clima, col tono e col perimetro dichiarato
    clima = [r["text"] for r in an.club_mood(9, 1, "Roma", KO("2026-09-17 18:00"))]
    assert any(t == "imbattuta da 5 gare in campionato: clima di fiducia" for t in clima), clima
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

    # virgola italiana (docs/25): prima qui era codificato l'output sbagliato «2.33 a gara»,
    # cioè il test bloccava il difetto invece di impedirlo — audit 18/09/2026.
    assert ("Dentro le mura", "Roma in casa: 2 vittorie, 1 pareggio e 0 sconfitte in 3 gare (7 punti su 9, 2,33 a gara).") in testi
    assert ("Lontano da casa", "Inter in trasferta: 1 vittoria, 1 pareggio e 1 sconfitta in 3 gare (4 punti su 9, 1,33 a gara).") in testi
    # l'uomo gol conta solo le gare finite: Pellegrini resta a 1, Dybala a 3
    # il tipo di indisponibilità va tradotto: prima qui era codificato l'inglese della fonte
    # («(injury)»), unica riga del portale a pubblicare il valore grezzo — audit 18/09/2026
    assert ("L'uomo gol", "il miglior marcatore di Roma in questo campionato è Dybala (3 gol), che però è indisponibile per questa gara (infortunio).") in testi
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


def _bollettino(**kw):
    """Bollettino della card con tutte le chiavi dell'imbuto, come le produce `team_news`."""
    d = {"notizie": [], "riserva": [], "esaminate": 0, "pubblicate": 0, "scartate": 0,
         "oltre": 0, "annunci": 0, "piatti": 0, "altre": 0, "doppioni": 0, "vecchie": 0,
         "pertinenti": 0, "lingua": 0, "finestra": 7, "limite": 3, "categoria_limite": 2,
         "riserva_limite": 2}
    d.update(kw)
    return d


def test_riga_unica_quando_nessuna_squadra_ha_titoli_pubblicabili():
    """P1.1 (docs/28 §2): la card «Vita del club» dice il fatto in una riga sola.

    I conteggi restano tutti — sono la somma dell'imbuto delle due colonne — ma i motivi a
    zero non si nominano: la riga non deve suggerire scarti che non ci sono stati.
    """
    quieta = news_quiet_line(
        _bollettino(esaminate=20, scartate=12, annunci=5, piatti=3),
        _bollettino(esaminate=7, scartate=6, lingua=1),
        "Roma", "Inter")
    assert quieta is not None
    assert quieta["riga"].startswith("Nessun titolo pubblicabile su Roma e Inter negli ultimi 7 giorni")
    assert "27 titoli esaminati e scartati con criterio" in quieta["riga"]
    assert "18 servizio o cronaca" in quieta["riga"]      # 12 + 6
    assert "5 annunci o logistica" in quieta["riga"]
    assert "1 in un'altra lingua" in quieta["riga"]
    assert "su un'altra squadra" not in quieta["riga"]    # conteggio a zero: non si stampa
    assert quieta["esaminate"] == 27


def test_riga_unica_non_scatta_se_una_squadra_ha_qualcosa():
    """Con una voce pubblicata (o in riserva) la card resta completa, colonna per colonna."""
    voce = {"title": "Roma, ricorso respinto: la multa resta", "url": "https://esempio.it/1"}
    assert news_quiet_line(_bollettino(esaminate=1, notizie=[voce]), _bollettino(),
                           "Roma", "Inter") is None
    assert news_quiet_line(_bollettino(), _bollettino(riserva=[voce]), "Roma", "Inter") is None


def test_riga_unica_senza_titoli_raccolti_dichiara_i_vecchi():
    """Nessun titolo in finestra: la riga dice anche quanti ne sono stati guardati oltre."""
    quieta = news_quiet_line(_bollettino(vecchie=2), _bollettino(vecchie=1), "Roma", "Inter")
    assert "Nessun titolo in lingua italiana raccolto su Roma e Inter negli ultimi 7 giorni" \
        in quieta["riga"]
    assert "3 titoli più vecchi oltre la finestra" in quieta["riga"]

    solo_uno = news_quiet_line(_bollettino(vecchie=1), _bollettino(), "Roma", "Inter")
    assert "1 titolo più vecchio oltre la finestra" in solo_uno["riga"]

    niente = news_quiet_line(_bollettino(), _bollettino(), "Roma", "Inter")
    assert niente["riga"].endswith("negli ultimi 7 giorni.")


# ---- card «Fattori»: i due fattori aggiunti il 2026-10-08 (docs/58 §3-§4) ----------------------

def _storia(righe):
    """Specchio dei risultati sintetico (le colonne che ``venue_form`` legge)."""
    return pd.DataFrame([{"league_key": "ITA1", "season": "2025/2026", "date": KO(d),
                          "home": h, "away": a, "home_goals": gh, "away_goals": ga,
                          "odds_home": 2.0, "odds_draw": 3.4, "odds_away": 3.8}
                         for d, h, a, gh, ga in righe])


def _store_fattori(tmp_path, storia=None, info=None, stats=None, fx_extra=None):
    st = Store(tmp_path / "fattori")
    st.write("fixtures", FX if fx_extra is None
             else pd.concat([FX, _fixtures(fx_extra)], ignore_index=True))
    if storia is not None:
        st.write("history", storia)
    if info is not None:
        st.write("match_info", info)
    if stats is not None:
        st.write("team_stats", stats)
    return MatchAnalysis(st)


def test_fattori_rendimento_per_sede_finestra_campione_soglia(tmp_path):
    """«Rendimento per sede»: finestra di 365 giorni, minimo 5 gare per sede, soglia 0,50 pt/gara.

    Il fattore è nuovo (`docs/58` §3) e ha tre modi di sbagliare che il test chiude: leggere gare
    **future** o più vecchie della finestra, pubblicare un PPG su due gare, e uscire in tabella
    quando le due squadre si equivalgono.
    """
    dentro = [(f"2026-08-{d:02d}", "Lazio", "X", 2, 0) for d in range(1, 7)]      # 6 vittorie in casa
    fuori = [("2025-08-01", "Lazio", "Y", 0, 3)]                                   # fuori finestra
    trasferta = [(f"2026-07-{d:02d}", "Y", "Milan", 2, 0) for d in range(1, 7)]    # 6 sconfitte fuori
    ma = _store_fattori(tmp_path, _storia(dentro + fuori + trasferta))
    ko = KO("2026-09-16 18:00")

    vf = ma.venue_form("Lazio", ko)
    assert vf and vf["casa"] == (3.0, 6), vf          # la gara del 2025 non entra
    assert "trasferta" not in vf                       # Lazio mai in trasferta nella finestra
    assert ma.venue_form("Milan", ko)["trasferta"] == (0.0, 6)

    res = ma.fattori_chiave(4, 1, "Lazio", 3, "Milan", ko.to_pydatetime(), None)
    riga = next(r for r in res["rows"] if r["label"] == "Rendimento per sede")
    # la cella porta anche la media per sede della stessa lega nella finestra (docs/59): nel
    # fixture tutte le gare in finestra sono vinte dalla casa, quindi la base è 3,00 / 0,00
    assert riga["home"] == "3,00 pt/gara in casa (6 gare · lega 3,00)"
    assert riga["away"] == "0,00 pt/gara in trasferta (6 gare · lega 0,00)"
    assert riga["delta"] == "+3,00 pt/gara" and riga["tone"] == "good"
    assert "68,2%" in riga["help"] and "scripts/audit_fattori.py" in riga["help"]
    assert "lega" in riga["help"]            # il ⓘ spiega come leggere il riferimento

    # sotto soglia (0,33 < 0,50): niente riga, ma il fattore è dichiarato fuori tabella
    quasi = [(f"2026-07-{d:02d}", "Y", "Milan", 0, 3) for d in range(1, 6)] + \
            [("2026-06-01", "Y", "Milan", 1, 1)]        # 5 vittorie + 1 pareggio = 2,67 pt/gara
    ma2 = _store_fattori(tmp_path / "q", _storia(dentro + quasi))
    res2 = ma2.fattori_chiave(4, 1, "Lazio", 3, "Milan", ko.to_pydatetime(), None)
    assert not any(r["label"] == "Rendimento per sede" for r in res2["rows"])
    assert any(s.startswith("rendimento per sede +0,33 pt/gara (soglia ≥0,50)")
               for s in res2["sotto_soglia"]), res2["sotto_soglia"]

    # meno di 5 gare per sede: non calcolabile, e la pagina lo dice invece di tacere
    poche = [(f"2026-07-{d:02d}", "Y", "Milan", 2, 0) for d in range(1, 4)]
    ma3 = _store_fattori(tmp_path / "p", _storia(dentro + poche))
    res3 = ma3.fattori_chiave(4, 1, "Lazio", 3, "Milan", ko.to_pydatetime(), None)
    assert not any(r["label"] == "Rendimento per sede" for r in res3["rows"])
    assert any("rendimento per sede non calcolabile (meno di 5 gare per sede" in s
               for s in res3["sotto_soglia"]), res3["sotto_soglia"]


def test_fattori_disciplina_e_arbitro_due_soglie(tmp_path):
    """«Disciplina e arbitro»: scatta sui cartellini delle due squadre **oppure** sull'arbitro.

    Misura di riferimento (`docs/58` §4): gli arbitri sopra la mediana dichiarata dànno 3,80
    gialli/gara contro 3,19; sui rigori la media di carriera non predice nulla, quindi la riga
    parla di cartellini. Il test copre entrambi i trigger e il caso «nessuno dei due».
    """
    ko = KO("2026-09-16 18:00")
    base_info = [{"match_id": 100 + d, "league_id": 55, "status": "finished",
                  "utc_kickoff": KO(f"2026-09-{d:02d} 18:00"), "home_id": 1, "away_id": 2,
                  "referee_name": f"Arbitro {100 + d}", "referee_matches": 30,
                  "referee_yellows_per_match": 3.0}
                 for d in range(1, 7)]

    def _info(yellows, gare_career=30):
        rows = [dict(r) for r in base_info]
        rows.append({"match_id": 4, "league_id": 55, "status": "scheduled",
                     "utc_kickoff": ko, "home_id": 1, "away_id": 2, "referee_name": "Severo",
                     "referee_matches": gare_career, "referee_yellows_per_match": yellows})
        return pd.DataFrame(rows)

    def _stats(gialli_casa, gialli_ospite, n=6):
        righe = []
        for i in range(n):
            for tid, val in ((1, gialli_casa), (2, gialli_ospite)):
                righe.append({"match_id": 101 + i, "team_id": tid, "period": "All",
                              "key": "yellow_cards", "value": float(val), "text": None})
                righe.append({"match_id": 101 + i, "team_id": tid, "period": "All",
                              "key": "fouls", "value": 10.0, "text": None})
        return pd.DataFrame(righe)

    def _fx_stagione():
        # le stesse 6 gare finite di `base_info` nel calendario: il campione dei cartellini
        # è quello delle gare finite **nel calendario** (docs/64 §7, regola di `season_xg`)
        return [(100 + d, 55, "2026", str(d), KO(f"2026-09-{d:02d} 18:00"), 1, "Roma", 2, "Inter",
                 0, 0, "finished", "fotmob") for d in range(1, 7)]

    # arbitro nella media e squadre simili → fattore dichiarato fuori tabella, nessuna riga
    ma = _store_fattori(tmp_path / "a", info=_info(3.06), stats=_stats(1, 1),
                        fx_extra=_fx_stagione())
    res = ma.fattori_chiave(4, 1, "Roma", 2, "Inter", ko.to_pydatetime(), None)
    assert not any(r["label"] == "Disciplina e arbitro" for r in res["rows"])
    assert any(s.startswith("disciplina +0,0 gialli/gara (soglia 0,8)") for s in res["sotto_soglia"])
    assert any(s.startswith("arbitro +2% sulla media di lega (soglia ±10%)")
               for s in res["sotto_soglia"]), res["sotto_soglia"]

    # arbitro severo (+25% sulla media di lega) → riga, con le celle «n.d.» se i cartellini
    # di stagione delle due squadre non ci sono
    ma2 = _store_fattori(tmp_path / "b", info=_info(3.75), fx_extra=_fx_stagione())
    res2 = ma2.fattori_chiave(4, 1, "Roma", 2, "Inter", ko.to_pydatetime(), None)
    r2 = next(r for r in res2["rows"] if r["label"] == "Disciplina e arbitro")
    assert r2["home"] == r2["away"] == "n.d." and r2["delta"] == "—"
    assert "più severo della media di lega (+21%)" in r2["impact"]

    # squadre con cartellini molto diversi → riga anche con l'arbitro nella media
    ma3 = _store_fattori(tmp_path / "c", info=_info(3.06), stats=_stats(3, 1),
                         fx_extra=_fx_stagione())
    res3 = ma3.fattori_chiave(4, 1, "Roma", 2, "Inter", ko.to_pydatetime(), None)
    r3 = next(r for r in res3["rows"] if r["label"] == "Disciplina e arbitro")
    assert r3["home"].startswith("3,0 gialli") and "(6 gare)" in r3["home"]
    assert r3["delta"] == "+2,0 gialli/gara" and "più esposta Roma" in r3["impact"]

    # meno di 20 gare in carriera: l'arbitro non è giudicabile, e si dice
    ma4 = _store_fattori(tmp_path / "d", info=_info(3.75, gare_career=8), stats=_stats(1, 1),
                         fx_extra=_fx_stagione())
    res4 = ma4.fattori_chiave(4, 1, "Roma", 2, "Inter", ko.to_pydatetime(), None)
    assert not any(r["label"] == "Disciplina e arbitro" for r in res4["rows"])
    assert any(s.startswith("arbitro +21% sulla media di lega (soglia ±10%)")
               for s in res4["sotto_soglia"]), res4["sotto_soglia"]


def test_fattori_ordine_fisso_e_campione_dichiarato(mood_analysis, monkeypatch):
    """Le righe hanno un ordine **fisso** (``FACTOR_PRIORITY``) e le medie di stagione dicono
    su quante gare sono calcolate: prima l'ordine dipendeva da un peso ad hoc (il rapporto di
    mercato saliva a 10,1 e scavalcava tutto) e il PPDA usciva senza campione (`docs/58` §2, §6).
    """
    monkeypatch.setattr(MatchAnalysis, "absences_weight",
                        lambda self, mid, tid: {"n": 2, "starters_out": 0, "contrib_lost_p90": 0.5})
    monkeypatch.setattr(MatchAnalysis, "rest_days", lambda self, tid, ko: 3)
    # `before` = calcio d'inizio della scheda (docs/64 §7): i numeri di stagione si fermano
    # alla vigilia, quindi il doppio di prova accetta il parametro.
    monkeypatch.setattr(MatchAnalysis, "season_xg",
                        lambda self, nome, tid, before=None: {"source": "Understat", "played": 6,
                                                              "xg_pm": 1.4, "xga_pm": 1.1, "ppda": 9.0}
                        if tid == 4 else {"source": "Understat", "played": 5,
                                          "xg_pm": 1.2, "xga_pm": 1.3, "ppda": 15.0})
    res = mood_analysis.fattori_chiave(8, 4, "Lazio", 3, "Milan", KO("2026-09-16 18:00"), None)
    etichette = [r["label"] for r in res["rows"]]
    ordini = [MatchAnalysis.FACTOR_PRIORITY[e] for e in etichette]
    assert ordini == sorted(ordini), f"righe fuori dall'ordine dichiarato: {etichette}"
    assert etichette[0] == "Indisponibili"
    if "Forma e classifica (contesto)" in etichette:      # assente senza classifica nella fixture
        assert etichette[-1] == "Forma e classifica (contesto)"
    pressing = next(r for r in res["rows"] if r["label"] == "Pressing (PPDA)")
    assert pressing["home"] == "9,0 (6 gare)" and pressing["away"] == "15,0 (5 gare)"
    assert "162 gare" in pressing["help"]


def test_fattori_contesto_leggibile(mood_analysis, monkeypatch):
    """«Forma e classifica (contesto)» si legge senza gergo (docs/59).

    Prima la cella diceva «6 pt · 1,20/gara · GD3 −4» (punti totali che da soli fuorviano, «GD3»
    criptico) e l'impatto era un numero nudo («indice +0,63»). Ora: punti/gara con le gare
    giocate, posizione, differenza reti ultime 3 scritta per esteso, e l'impatto in parole con la
    fascia «sostanzialmente pari» sotto ``FACTOR_CONTEXT_PARITY``.
    """
    stand = {"Atalanta": {"points": 10, "played": 5, "rank": 3},
             "Venezia": {"points": 2, "played": 5, "rank": 18}}
    monkeypatch.setattr(MatchAnalysis, "standing", lambda self, nome: stand.get(nome))
    monkeypatch.setattr(MatchAnalysis, "form",
                        lambda self, tid, ko, n=5: ([{"gf": 2, "ga": 0}] * 3 if tid == 4
                                                    else [{"gf": 0, "ga": 2}] * 3))
    res = mood_analysis.fattori_chiave(8, 4, "Atalanta", 3, "Venezia",
                                       KO("2026-09-16 18:00"), None)
    riga = next(r for r in res["rows"] if r["label"] == "Forma e classifica (contesto)")
    assert riga["home"] == "2,00 pt/gara (5 gare) · 3ª · reti ult. 3 +6"
    assert riga["away"] == "0,40 pt/gara (5 gare) · 18ª · reti ult. 3 −6"
    assert riga["delta"] == "PPG +1,60"
    assert "GD3" not in riga["home"] + riga["away"] + riga["delta"]      # il gergo è sparito
    assert riga["impact"] == "contesto a favore di Atalanta (indice +1,00)"

    # sotto la fascia: nessuna direzione dichiarata, e il lettore vede che è un contesto pari
    stand2 = {"Atalanta": {"points": 6, "played": 5, "rank": 8},
              "Venezia": {"points": 5, "played": 5, "rank": 9}}
    monkeypatch.setattr(MatchAnalysis, "standing", lambda self, nome: stand2.get(nome))
    monkeypatch.setattr(MatchAnalysis, "form", lambda self, tid, ko, n=5: [{"gf": 1, "ga": 1}] * 3)
    res2 = mood_analysis.fattori_chiave(8, 4, "Atalanta", 3, "Venezia",
                                        KO("2026-09-16 18:00"), None)
    r2 = next(r for r in res2["rows"] if r["label"] == "Forma e classifica (contesto)")
    assert r2["impact"].startswith("contesto sostanzialmente pari")
    assert "a favore di" not in r2["impact"]


def test_incroci_in_panchina_anche_dallo_storico(analysis):
    """Con `match_storico` gli incroci contano anche le stagioni precedenti (docs/80).

    Nella sola stagione in corso i due si sono affrontati una volta (Milan–Roma); nelle
    stagioni passate, su panchine opposte e su club diversi da quelli di oggi, altre due.
    La riga pubblicata le somma. Senza `match_storico` (fixture `analysis`) resta com'era:
    è il test qui sopra a fissarlo.
    """
    st = analysis.store
    st.write("lineup", pd.concat([LINEUP, pd.DataFrame([
        {"match_id": 9001, "team_id": 5, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
        {"match_id": 9001, "team_id": 6, "player_id": 300, "player_name": "Coach Stabile", "role": "coach"},
        {"match_id": 9002, "team_id": 6, "player_id": 300, "player_name": "Coach Stabile", "role": "coach"},
        {"match_id": 9002, "team_id": 5, "player_id": 200, "player_name": "Coach Nuovo", "role": "coach"},
    ])], ignore_index=True))
    st.write("match_storico", pd.DataFrame([
        # Torino (5) di Coach Nuovo contro il Genoa (6) di Coach Stabile: vittoria del nostro
        {"match_id": 9001, "league_id": 55, "stagione": "2024/2025", "giornata": "3",
         "utc_kickoff": KO("2024-09-01 18:00"), "home_id": 5, "home_name": "Torino",
         "away_id": 6, "away_name": "Genoa", "home_goals": 2, "away_goals": 1,
         "status": "finished"},
        # ritorno in parità
        {"match_id": 9002, "league_id": 55, "stagione": "2024/2025", "giornata": "20",
         "utc_kickoff": KO("2025-02-02 18:00"), "home_id": 6, "home_name": "Genoa",
         "away_id": 5, "away_name": "Torino", "home_goals": 1, "away_goals": 1,
         "status": "finished"},
    ]))
    an = MatchAnalysis(st)
    b = an.bench_deep(2, "Inter", 1, "Roma", KO("2026-09-14 00:00"))
    assert b["coach_vs_coach_line"] == ("incroci in panchina con Coach Stabile: 2V 1N 0P "
                                        "su 3 gare")
    # la stessa storia letta dalla panchina della Roma
    br = an.bench_deep(1, "Roma", 2, "Inter", KO("2026-09-14 00:00"))
    assert br["coach_vs_coach_line"] == ("incroci in panchina con Coach Nuovo: 0V 1N 2P "
                                         "su 3 gare")
    # le altre righe della card restano quelle della stagione in corso: il rendimento non
    # assorbe le gare storiche (`docs/80`: lo storico serve **solo** agli incroci)
    assert b["coach_ppg_line"] == "1,0 punti/gara su 1 gara finita"
    assert b["coach_vs_opp_line"] == "da allenatore contro Roma: 1 gara nel nostro archivio (1V 0N 0P)"


# ---- card «Clima del club» (`docs/82` §5): la settimana della stampa e le aspettative --------


def _clima_store(tmp_path, news: pd.DataFrame | None = None):
    """Store minimo con 8 squadre di lega: 3 gare misurate a testa e la gara della scheda."""
    st = Store(tmp_path / "clima")
    valori = {i: (9 - i) * 10 for i in range(1, 9)}          # S1 rosa più costosa, S8 la meno
    righe_fx, righe_mi, mid = [], [], 300
    for i in range(1, 9):
        avversario = i % 8 + 1
        for k in range(3):                                    # tre gare finite prima del fischio
            mid += 1
            righe_fx.append((mid, 55, "2026", str(k), KO(f"2026-08-{10 + k:02d} 18:00"),
                             i, f"S{i}", avversario, f"S{avversario}", 1, 0, "finished", "fotmob"))
            righe_mi.append({"match_id": mid, "home_id": i, "away_id": avversario,
                             "home_starters_value_eur": valori[i] * 1_000_000,
                             "away_starters_value_eur": valori[avversario] * 1_000_000})
    righe_fx.append((400, 55, "2026", "9", KO("2026-09-16 18:00"), 2, "S2", 1, "S1",
                     None, None, "scheduled", "fotmob"))
    st.write("fixtures", _fixtures(righe_fx))
    st.write("match_info", pd.DataFrame(righe_mi))
    st.write("fotmob_standings", pd.DataFrame([
        {"league_code": "ITA1", "team_id": i, "team_name": f"S{i}",
         # S2 è ultima in classifica con la seconda rosa più costosa; S8 prima con la più economica
         "rank": {2: 8, 8: 1}.get(i, i), "played": 3, "wins": 0, "draws": 0, "losses": 3,
         "goals_for": 0, "goals_against": 3, "goal_diff": -3, "points": 0}
        for i in range(1, 9)
    ]))
    if news is not None:
        st.write("news", news)
    return MatchAnalysis(st)


def test_clima_settimana_dalla_stampa_contata_per_tema(tmp_path):
    """La settimana del club è un conteggio per tema, mai un titolo (`docs/82` §5)."""
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "S1, esonero sempre più vicino per il tecnico", "url": "https://e.it/1",
         "source": "Gazzetta", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-14 10:00"),
         "title": "S1, spogliatoio spaccato dopo il ko", "url": "https://e.it/2",
         "source": "Corriere", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-14 11:00"),
         "title": "S1, gli ultras disertano la trasferta", "url": "https://e.it/3",
         "source": "ANSA", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-14 12:00"),
         "title": "S1, indagine della procura sul bilancio", "url": "https://e.it/4",
         "source": "ANSA", "description": ""},
        # fuori dai temi di clima: infortuni e mercato hanno le loro card
        {"team_id": 1, "published_at": KO("2026-09-14 13:00"),
         "title": "S1, infortunio per il capitano: out un mese", "url": "https://e.it/5",
         "source": "Gazzetta", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-14 14:00"),
         "title": "S1, ufficiale l'arrivo del difensore", "url": "https://e.it/6",
         "source": "Gazzetta", "description": ""},
        # fuori finestra: non conta
        {"team_id": 1, "published_at": KO("2026-08-30 09:00"),
         "title": "S1, protesta dei tifosi in curva", "url": "https://e.it/7",
         "source": "ANSA", "description": ""},
    ])
    a = _clima_store(tmp_path, news)
    cl = a.club_climate(1, "S1", KO("2026-09-16 18:00"))
    testi = [r["text"] for r in cl["righe"]]
    assert cl["voci"] == 4 and cl["pressione"] == 4 and cl["vuota"] is False
    assert ("settimana calda: 4 voci di pressione in 7 giorni (panchina 1 · spogliatoio 1 · "
            "società 1 · tifoseria 1)") in testi, testi
    assert cl["righe"][0]["tone"] == "bad"
    # i temi contati sono quelli di ambiente, col conteggio: nessun titolo di giornale
    assert [(t["key"], t["n"]) for t in cl["temi"]] == [
        ("allenatore", 1), ("spogliatoio", 1), ("societa", 1), ("tifo", 1)]
    assert all("https://" not in r["text"] for r in cl["righe"])


def test_clima_settimana_tranquilla_e_vuoto_dichiarato(tmp_path):
    """Voci senza pressione → «tranquilla»; zero voci → nessuna riga e vuoto dichiarato."""
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "S1, il nuovo stadio: lavori al via", "url": "https://e.it/1",
         "source": "ANSA", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-13 09:00"),
         "title": "S1, il centro sportivo apre le porte ai bambini", "url": "https://e.it/2",
         "source": "ANSA", "description": ""},
    ])
    a = _clima_store(tmp_path, news)
    cl = a.club_climate(1, "S1", KO("2026-09-16 18:00"))
    testi = [r["text"] for r in cl["righe"]]
    assert any(t.startswith("settimana tranquilla: 2 voci, nessuna di pressione") for t in testi), testi
    assert all(r["tone"] in ("bad", "warn", "good") for r in cl["righe"])
    # la squadra senza notizie: vuota, e la card lo può dichiarare
    vuoto = a.club_climate(3, "S3", KO("2026-09-16 18:00"))
    assert vuoto["vuota"] is True and vuoto["voci"] == 0
    assert [r["text"] for r in vuoto["righe"]] == [] or all(
        "settimana" not in r["text"] for r in vuoto["righe"])


def test_clima_aspettative_sotto_sopra_e_soglia(tmp_path):
    """Pressione da aspettative: rosa costosa ultima in classifica, e viceversa (`docs/82` §5)."""
    a = _clima_store(tmp_path)
    ko = KO("2026-09-16 18:00")
    sotto = a.expectation_gap(2, "S2", ko)
    assert sotto is not None and (sotto["rango"], sotto["posizione"], sotto["delta"]) == (2, 8, 6)
    sopra = a.expectation_gap(8, "S8", ko)
    assert sopra is not None and (sopra["rango"], sopra["posizione"], sopra["delta"]) == (8, 1, -7)
    # in linea con le attese (S4: rango 4, classifica 4ª) → nessuna riga
    assert a.expectation_gap(4, "S4", ko) is None
    # con meno di 3 gare misurate il rango è un caso: nessuna riga
    assert a.expectation_gap(3, "S3", KO("2026-08-11 18:00")) is None
    cl = a.club_climate(2, "S2", ko)
    testi = [r["text"] for r in cl["righe"]]
    assert ("pressione da aspettative: rosa da 2ª per valore dei titolari, in classifica 8ª"
            in testi), testi
    assert [r["tone"] for r in cl["righe"] if r["text"].startswith("pressione da")] == ["warn"]
    cl8 = a.club_climate(8, "S8", ko)
    testi8 = [r["text"] for r in cl8["righe"]]
    assert ("sopra le attese: in classifica 1ª con una rosa da 8ª per valore dei titolari"
            in testi8), testi8

def test_clima_elenco_una_voce_per_titolo_con_testata_data_e_link(tmp_path):
    """L'elenco è la prova dei conteggi (`docs/82` §9): una voce per titolo, con link e marcature.

    Lo stesso titolo ripreso da due testate è **una** voce (la più recente), e le voci che
    «Vita del club» racconta sulla stessa pagina escono marcate (`visti`), non tolte.
    """
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "S1, esonero sempre più vicino per il tecnico", "url": "https://e.it/1",
         "source": "Gazzetta", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-14 12:00"),
         "title": "S1, esonero sempre più vicino per il tecnico", "url": "https://e.it/dup",
         "source": "Corriere", "description": ""},
        {"team_id": 1, "published_at": KO("2026-09-14 11:00"),
         "title": "S1, gli ultras disertano la trasferta", "url": "https://e.it/3",
         "source": "ANSA", "description": ""},
    ])
    a = _clima_store(tmp_path, news)
    visti = {news_title_key("S1, gli ultras disertano la trasferta")}
    cl = a.club_climate(1, "S1", KO("2026-09-16 18:00"), visti=visti)
    assert cl["voci"] == 2 and cl["pressione"] == 2 and cl["vuota"] is False
    assert cl["elencate"] == 2 and cl["oltre"] == 0 and cl["in_vita"] == 1
    voci = [v for t in cl["temi"] for v in t["voci"]]
    assert [v["title"] for v in voci] == [
        "S1, esonero sempre più vicino per il tecnico", "S1, gli ultras disertano la trasferta"]
    # del titolo ripetuto resta la pubblicazione più recente (Corriere, 12:00)
    assert voci[0]["url"] == "https://e.it/dup" and voci[0]["source"] == "Corriere"
    assert voci[0]["published_at"] == KO("2026-09-14 12:00")
    assert voci[0]["in_vita"] is False and voci[1]["in_vita"] is True


def test_clima_elenco_tetto_dichiarato_oltre_il_limite(tmp_path):
    """Oltre il tetto di 24 voci elencate il resto è dichiarato col numero, mai tagliato in silenzio."""
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00") + pd.Timedelta(minutes=k),
         "title": f"S1, gli ultras preparano lo striscione numero {k}", "url": f"https://e.it/{k}",
         "source": "ANSA", "description": ""}
        for k in range(1, 27)
    ])
    a = _clima_store(tmp_path, news)
    cl = a.club_climate(1, "S1", KO("2026-09-16 18:00"))
    assert cl["voci"] == 26 and cl["elencate"] == 24 and cl["oltre"] == 2
    voci = [v for t in cl["temi"] for v in t["voci"]]
    assert len(voci) == 24
    # le più recenti restano in elenco (26ª → 3ª); le due più vecchie sono dichiarate col numero
    assert voci[0]["title"].endswith("numero 26") and voci[-1]["title"].endswith("numero 3")
    assert cl["temi"][0]["n"] == 26                          # il conteggio resta quello completo

def test_clima_voci_pertinenti_e_fatto_della_settimana(tmp_path):
    """I gate di pertinenza del clima e la voce in evidenza (richiesta dell'11/10/2026).

    Le stesse regole di «Vita del club» applicate al conteggio del clima (`docs/83` §2-§3):
    fuori le fonti a bassa reputazione e i temi che non si vedono nel titolo pubblicato;
    fra le voci rimaste, «il fatto della settimana» è quella che pesa di più.
    """
    news = pd.DataFrame([
        # fonte a bassa reputazione: esclusa dal conteggio (9 voci «Toro News» misurate)
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "S1, l'allenatore a rischio esonero", "url": "https://e.it/1",
         "source": "Toro News",
         "description": "Il futuro del tecnico è sempre più incerto dopo l'ultima sconfitta."},
        # tema nel brano ma non nel titolo: una citazione non fa clima
        {"team_id": 1, "published_at": KO("2026-09-14 10:00"),
         "title": "Calcio: Pisacane, la nostra fame per vincere", "url": "https://e.it/2",
         "source": "ANSA", "description": "Il tecnico ha parlato dell'esonero vicino del collega."},
        # voci vere: il tema si vede nel titolo
        {"team_id": 1, "published_at": KO("2026-09-14 11:00"),
         "title": "S1, gli ultras disertano la trasferta", "url": "https://e.it/3",
         "source": "ANSA",
         "description": "La curva ha annunciato che non sarà presente allo stadio."},
        {"team_id": 1, "published_at": KO("2026-09-14 12:00"),
         "title": "S1, il nuovo stadio: lavori al via", "url": "https://e.it/4",
         "source": "ANSA",
         "description": "Il cantiere apre la prossima settimana, pronti i primi interventi."},
    ])
    a = _clima_store(tmp_path, news)
    cl = a.club_climate(1, "S1", KO("2026-09-16 18:00"))
    assert cl["voci"] == 2 and cl["fuori_fonte"] == 1 and cl["fuori_titolo"] == 1
    assert cl["fatto"] is not None and cl["fatto"]["url"] == "https://e.it/3"
    # tifoseria 3 + 3 (fatto grave: la trasferta disertata) batte stadio 3
    assert cl["fatto"]["title"] == "S1, gli ultras disertano la trasferta"


def test_clima_fatto_grave_batte_il_tema_piu_pesante(tmp_path):
    """Un fatto grave nel titolo (sciopero, scontri) batte anche il tema più pesante:
    società vale 5, tifoseria 3, ma lo sciopero porta la tifoseria a 6 (`docs/83` §3)."""
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "S1, il direttore sportivo lascia il club", "url": "https://e.it/1",
         "source": "ANSA",
         "description": "La decisione è arrivata questa mattina, il club cerca un sostituto."},
        {"team_id": 1, "published_at": KO("2026-09-14 08:00"),
         "title": "S1, la curva annuncia lo sciopero del tifo", "url": "https://e.it/2",
         "source": "ANSA",
         "description": "Gli ultras non entreranno allo stadio per la prossima partita."},
    ])
    a = _clima_store(tmp_path, news)
    cl = a.club_climate(1, "S1", KO("2026-09-16 18:00"))
    assert cl["fatto"]["url"] == "https://e.it/2", cl["fatto"]

def test_clima_il_club_deve_essere_nel_titolo(tmp_path):
    """Gate di soggetto (`docs/83` §3): il club si vede nel titolo, non solo nel brano.

    Il test riproduce il caso misurato l'11/10/2026: due titoli sul **Latina** contavano
    come settimana della **Lazio** perché il brano citava la Lazio e il tema c'era.
    """
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "Lazio, spogliatoio spaccato dopo il ko", "url": "https://e.it/1",
         "source": "Gazzetta",
         "description": "Il confronto è avvenuto a Formello dopo la partita."},
        {"team_id": 1, "published_at": KO("2026-09-14 10:00"),
         "title": "Latina, Pino D'Apuzzo diventa il nuovo presidente", "url": "https://e.it/2",
         "source": "Gazzetta",
         "description": "Il club pontino ha annunciato il cambio al vertice societario."},
        {"team_id": 1, "published_at": KO("2026-09-14 11:00"),
         "title": "Toro, contestazione dei tifosi dopo il ko", "url": "https://e.it/3",
         "source": "ANSA",
         "description": "Gli ultras hanno esposto uno striscione fuori dallo stadio."},
    ])
    a = _clima_store(tmp_path, news)
    cl = a.club_climate(1, "Lazio", KO("2026-09-16 18:00"))
    assert cl["voci"] == 1 and cl["fuori_soggetto"] == 2, cl
    assert [v["title"] for t in cl["temi"] for v in t["voci"]] == [
        "Lazio, spogliatoio spaccato dopo il ko"]
    # e il titolo resta **fuori** dall'elenco, non solo dai conteggi
    assert all("Latina" not in v["title"] for t in cl["temi"] for v in t["voci"])


def test_clima_i_nomi_d_edicola_valgono_come_il_club(tmp_path):
    """«Juve» è la Juventus e «Colonia» è il Köln: il gate usa i nomi della stampa (`docs/83` §3).

    Senza, due voci vere della settimana (lo sciopero della Curva Sud, il bilancio del club
    tedesco) sparivano perché il titolo non scriveva il nome dei dati.
    """
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 10:00"),
         "title": "Juve-Lazio senza Curva Sud: gli ultras disertano lo Stadium",
         "url": "https://e.it/1", "source": "Gazzetta",
         "description": "La protesta dei tifosi organizzati è stata annunciata ieri sera."},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Colonia, il bilancio chiude in perdita: i tifosi protestano",
         "url": "https://e.it/2", "source": "Gazzetta",
         "description": "Il club tedesco ha presentato i conti della scorsa stagione."},
    ])
    a = _clima_store(tmp_path, news)
    juve = a.club_climate(1, "Juventus", KO("2026-09-16 18:00"))
    assert juve["voci"] == 1 and juve["fuori_soggetto"] == 0, juve
    assert juve["fatto"] is not None and juve["fatto"]["url"] == "https://e.it/1"
    colonia = a.club_climate(2, "Köln", KO("2026-09-16 18:00"))
    assert colonia["voci"] == 1 and colonia["fuori_soggetto"] == 0, colonia


def test_clima_fatto_solo_se_il_tema_pesa(tmp_path):
    """Il fatto della settimana esce solo se pesa: tifoseria o stadio da soli non bastano.

    Misurato l'11/10/2026 sugli 8 lati che pubblicavano un fatto di peso 3: erano una
    petizione per una maglia, un elenco di vittorie, «polemiche sui social» (`docs/83` §4).
    """
    news = pd.DataFrame([
        {"team_id": 1, "published_at": KO("2026-09-14 09:00"),
         "title": "Lazio, la Curva prepara la coreografia per la prima in casa",
         "url": "https://e.it/1", "source": "Gazzetta",
         "description": "Il gruppo organizzato ha annunciato la scenografia per domenica."},
        {"team_id": 2, "published_at": KO("2026-09-14 09:00"),
         "title": "Juventus, sciopero della Curva Sud: gli ultras disertano lo Stadium",
         "url": "https://e.it/2", "source": "Gazzetta",
         "description": "La protesta è stata decisa dopo i provvedimenti della questura."},
        {"team_id": 3, "published_at": KO("2026-09-14 09:00"),
         "title": "Lazio, spogliatoio spaccato dopo il ko", "url": "https://e.it/3",
         "source": "Gazzetta",
         "description": "Il confronto è avvenuto a Formello dopo la partita."},
    ])
    a = _clima_store(tmp_path, news)
    ko = KO("2026-09-16 18:00")
    solo_tifo = a.club_climate(1, "Lazio", ko)
    assert solo_tifo["voci"] == 1 and solo_tifo["fatto"] is None, solo_tifo
    grave = a.club_climate(2, "Juventus", ko)          # tifoseria 3 + 3 (sciopero) = 6
    assert grave["fatto"] is not None and grave["fatto"]["url"] == "https://e.it/2"
    peso5 = a.club_climate(3, "Lazio", ko)             # spogliatoio 5, nessun fatto grave
    assert peso5["fatto"] is not None and peso5["fatto"]["url"] == "https://e.it/3"


def test_soggetto_edicola_e_fatto_grave_in_proprio():
    """Le due regole di pertinenza in una riga di codice, senza dati (`docs/83` §3-§4).

    `soggetto_tokens` riconosce i nomi d'edicola e le sigle societarie non identificano
    nessuno; `club_nel_titolo` pretende il club come soggetto, non come oggetto; `fatto_grave`
    non conta le citazioni e non conta le plusvalenze delle colonne di fantacalcio.
    """
    from fda.sources.news import club_nel_titolo, fatto_grave, soggetto_tokens

    assert soggetto_tokens("Juventus") == {"juve", "juventus"}
    assert soggetto_tokens("Köln") == {"colonia", "koln"}
    assert soggetto_tokens("M'gladbach") == {"borussia", "gladbach", "monchengladbach"}
    assert soggetto_tokens("Man City") == {"city", "man", "manchester"}
    assert soggetto_tokens("Barcelona") == {"barca", "barcellona", "barcelona"}
    assert soggetto_tokens("S1") == set()          # nome finto: il gate non giudica

    roma = soggetto_tokens("Roma")
    assert club_nel_titolo("Roma, l'analisi dei conti del club", roma) is True
    assert club_nel_titolo("Scontri prima del derby Roma-Lazio", roma) is True
    assert club_nel_titolo("Real Madrid, alta tensione a pochi giorni dalla Roma", roma) is False
    assert club_nel_titolo("Protesta dei tifosi contro la Roma", roma) is False
    assert club_nel_titolo("Romanzo di una stagione", roma) is False   # parole intere
    assert club_nel_titolo("qualsiasi titolo", set()) is True         # niente da giudicare

    assert fatto_grave("Scontri durante Torino-Juventus: emessi 22 Daspo") is True
    assert fatto_grave('Gasperini: "Esonero Inter? Ho vacillato"') is False
    assert fatto_grave("Statistiche Fantacampionato: le tre plusvalenze maggiori") is False
    assert fatto_grave("Lazio, l'analisi dei conti del club: debiti record") is True


def test_radar_pressing_e_profondita_solo_se_per_entrambe(mood_analysis, monkeypatch):
    """Regola «entrambe o nessuna» (richiesta del 2026-10-12): PPDA e profondità vengono da
    Understat. Se il dato manca per una sola squadra, l'asse non si confronta: n.d. per entrambe
    e il testo di aiuto dice perché. Con il dato per entrambe l'asse resta.
    """
    monkeypatch.setattr(MatchAnalysis, "standing",
                        lambda self, name: {"goals_for": 20, "goals_against": 10, "played": 10,
                                            "points": 20, "rank": 3})
    monkeypatch.setattr(MatchAnalysis, "_league_averages",
                        lambda self, st: {"gf": 1.5, "ga": 1.5})

    def stile_sbilanciato(self, name, tid, before):
        return {"ppda": 10.0 if name == "Lazio" else None, "deep": 5.0 if name == "Lazio" else None,
                "open_pm": 1.0, "set_pm": 1.0}

    monkeypatch.setattr(MatchAnalysis, "season_style", stile_sbilanciato)
    r = mood_analysis.clash_radar("Lazio", 8, "Milan", 3)
    assert r is not None
    assert r["home"][2] is None and r["away"][2] is None          # PPDA: n.d. per entrambe
    assert r["home"][3] is None and r["away"][3] is None          # profondità: n.d. per entrambe
    assert "Non mostrato" in r["helps"][2] and "Non mostrato" in r["helps"][3]
    assert r["home"][1] is not None and r["away"][1] is not None  # difesa: nessuna regola

    def stile_completo(self, name, tid, before):
        return {"ppda": 10.0, "deep": 5.0, "open_pm": 1.0, "set_pm": 1.0}

    monkeypatch.setattr(MatchAnalysis, "season_style", stile_completo)
    r2 = mood_analysis.clash_radar("Lazio", 8, "Milan", 3)
    assert r2["home"][2] is not None and r2["away"][2] is not None
    assert "Non mostrato" not in r2["helps"][2]


def test_insight_drop_stats_elenca_tutte_le_forme_non_tradotte(monkeypatch):
    """Report delle stringhe non tradotte (richiesta del 2026-10-12): elenco completo, più
    frequente prima, cifre normalizzate. Un testo tradotto non entra nel report."""
    from fda.site import analysis as an

    monkeypatch.setattr(an, "INSIGHT_DROP_LOG", {})
    monkeypatch.setitem(an.INSIGHT_SEEN, "tradotti", 0)
    monkeypatch.setitem(an.INSIGHT_SEEN, "scartati", 0)
    monkeypatch.setitem(an.INSIGHT_SEEN, "forma_ricalcolata", 0)
    monkeypatch.setitem(an.INSIGHT_SEEN, "record_rifiutati", 0)
    for testo in ["Scored 2 goals at home", "Scored 3 goals at home", "Booked 4 players", "Booked 5 players",
                  "Booked 6 players", "Rare thing"]:
        an.insight_dropped(testo)
    stats = an.insight_drop_stats()
    shapes = stats["top_shapes"]
    assert shapes[0] == {"shape": "Booked N players", "n": 3}
    assert shapes[1] == {"shape": "Scored N goals at home", "n": 2}
    assert shapes[2] == {"shape": "Rare thing", "n": 1}
    assert stats["n_shapes"] == 3


def test_conditional_stakes_tutto_o_niente(mood_analysis):
    """Tabella condizionata per gara: tre esiti × due squadre, altrimenti niente (mai a metà)."""
    rows = []
    for o, (pt_home, pt_away) in {"1": (0.30, 0.01), "X": (0.12, 0.05), "2": (0.02, 0.22)}.items():
        for team, pt in (("Lazio", pt_home), ("Milan", pt_away)):
            rows.append({"cond_home": "Lazio", "cond_away": "Milan", "cond_outcome": o, "team": team,
                         "p_title": pt, "p_top_n": 0.5, "p_rel": 0.02, "top_n": 4, "n_sims": 10000})
    mood_analysis.season_sim_cond = pd.DataFrame(rows)
    cs = mood_analysis.conditional_stakes("Lazio", "Milan")
    assert cs and [r["outcome"] for r in cs["rows"]] == ["vince Lazio", "pareggio", "vince Milan"]
    assert cs["rows"][0]["home"]["title"] == "30" and cs["rows"][0]["away"]["title"] == "1"  # senza % (lo mette il template)
    assert cs["ucl_spots"] == 4 and cs["n_sims"] == 10000
    # un esito mancante: niente tabella invece di una a metà
    mood_analysis.season_sim_cond = pd.DataFrame(rows).query("cond_outcome != 'X'")
    assert mood_analysis.conditional_stakes("Lazio", "Milan") is None
    # gara non presente: niente
    mood_analysis.season_sim_cond = pd.DataFrame(rows)
    assert mood_analysis.conditional_stakes("Roma", "Inter") is None
