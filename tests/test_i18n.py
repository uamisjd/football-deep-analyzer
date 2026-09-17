"""Test dei formatter/traduttori italiani del sito (numeri, date, meteo, rientri)."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fda.site.analysis import _f, _return_it, _weather_it
from fda.site.build import it_dec, it_from_utc, it_thousands

ROMA = ZoneInfo("Europe/Rome")


def test_it_dec():
    assert it_dec(3.86) == "3,86"
    assert it_dec(0.0866, nd=3) == "0,087"
    assert it_dec(-0.0384, nd=3) == "-0,038"
    assert it_dec(0.05, nd=3, plus=True) == "+0,050"
    assert it_dec(-0.05, nd=3, plus=True) == "-0,050"
    assert it_dec(None) == ""


def test_it_thousands():
    assert it_thousands(57000) == "57.000"
    assert it_thousands(57000.0) == "57.000"  # float dal Parquet
    assert it_thousands(1234567) == "1.234.567"


def test_it_from_utc():
    ts = datetime(2026, 9, 8, 11, 41, tzinfo=UTC)
    assert it_from_utc(ts, ROMA) == "08/09/2026 13:41"       # ora legale: +2
    inverno = datetime(2026, 12, 8, 10, 5, tzinfo=UTC)
    assert it_from_utc(inverno, ROMA) == "08/12/2026 11:05"  # ora solare: +1
    assert it_from_utc("2026-09-08T11:41:00Z", ROMA) == "08/09/2026 13:41"  # stringa ISO


def test_f_virgola():
    assert _f(3.116) == "3,12"
    assert _f(4.14, 1) == "4,1"
    assert _f(None) == "—"


def test_weather_it():
    assert _weather_it("Partly Cloudy") == "parzialmente nuvoloso"
    assert _weather_it("Mostly Clear") == "per lo più sereno"
    assert _weather_it("Fair") == "bel tempo"
    assert _weather_it("Partly Cloudy/Wind") == "parzialmente nuvoloso e ventoso"
    assert _weather_it("Showers in the Vicinity") == "rovesci nelle vicinanze"
    assert _weather_it("Condizione Sconosciuta") == "Condizione Sconosciuta"  # fallback
    assert _weather_it(None) is None


def test_return_it():
    assert _return_it("Mid October 2026") == "metà ottobre 2026"
    assert _return_it("Early January 2027") == "inizio gennaio 2027"
    assert _return_it("Late December 2026") == "fine dicembre 2026"
    assert _return_it("January 2027") == "gennaio 2027"
    assert _return_it("Day to day") == "giorno per giorno"
    assert _return_it("About 1-2 weeks") == "circa 1-2 settimane"
    assert _return_it("Out for season") == "fuori per tutta la stagione"
    assert _return_it("Back in training") == "rientrato agli allenamenti"
    assert _return_it("Custom 2027") == "Custom 2027"  # fallback
    assert _return_it(None) is None


def test_plurali_italiani():
    """«1 gara» / «33 gare»: la concordanza era rotta su 1098 pagine (audit 2026-09-12)."""
    from fda.site.fmt import it_plural, plural_it

    assert plural_it("gara") == "gare" and plural_it("partita") == "partite"
    assert plural_it("pareggio") == "pareggi"          # -io: cade solo la -o
    assert plural_it("giocatore") == "giocatori" and plural_it("vittoria") == "vittorie"
    assert plural_it("gol") == "gol" and plural_it("assist") == "assist"   # invariabili
    assert it_plural(1, "gara") == "1 gara" and it_plural(33, "gara") == "33 gare"
    assert it_plural(1, "pareggio") == "1 pareggio" and it_plural(12, "pareggio") == "12 pareggi"
    assert it_plural(1, "vittoria", "vittorie") == "1 vittoria"
    assert it_plural(2, "tiro", "tiri") == "2 tiri"


def test_is_italian_news():
    """I titoli pubblicati nelle schede devono essere rigorosamente in lingua italiana."""
    from fda.sources.news import is_italian_news

    # Titoli italiani validi: devono essere accettati
    assert is_italian_news("Bologna, esonerato Tedesco: arriva Palladino con contratto fino al 2029")
    assert is_italian_news("Lazio-Milan, tifosi scortano la squadra ma disertano l’Olimpico")
    assert is_italian_news("Cuesta si gioca la panchina del Parma, pronto uno tra Nicola e D'Aversa")
    assert is_italian_news("Real Madrid, Espì al 91’ salva Mourinho dalla contestazione")
    assert is_italian_news("Atalanta, i conti del mercato e l'impatto che avranno sul bilancio")

    # Titoli spagnoli: devono essere scartati
    assert not is_italian_news("«La política divide y el fútbol une»: Pellegrini defiende a Ezzalzouli tras los insultos marroquíes")
    assert not is_italian_news("José Bordalás se vuelve a quejar de la plantilla del Getafe y ensalza la del Betis")
    assert not is_italian_news("El Getafe CF dibuja un presupuesto récord desde la Covid en 2026-2027")
    assert not is_italian_news("Iñigo Pérez y su posible destitución del Villarreal CF")
    assert not is_italian_news("¿Cuándo y dónde ver el partido?")

    # Titoli inglesi: devono essere scartati
    assert not is_italian_news("Carrick sack demanded now but Man Utd fans split")
    assert not is_italian_news("Jamie Carragher: Arsenal boss Mikel Arteta becoming like Sir Alex Ferguson")
    assert not is_italian_news("Inside Matthias Jaissle's brutal dressing room blast as Newcastle stars told learn fast")

    # Titoli tedeschi: devono essere scartati
    assert not is_italian_news("Fußball-Bundesliga: Medien – HSV verlängert Vertrag mit Trainer Polzin bis 2029")
    assert not is_italian_news("Bayern-Star Lennart Karl entschuldigt sich für Jubel-Geste beim Elversberg-Spiel")

    # Titoli francesi: devono essere scartati
    assert not is_italian_news("Santos – Monaco : Neymar solde une dette de 2 M€ liée à Jean Lucas")
    assert not is_italian_news("Les supporters de Marseille interdits de déplacement à Istanbul après une sanction")

    # Titoli olandesi: devono essere scartati
    assert not is_italian_news("Veelbesproken oud-Feyenoorder (31) bekent schuld na stevige crash met Lamborghini")
    assert not is_italian_news("FC Utrecht grijpt hard in na incidenten en deelt eerste stadionverboden uit")

    # Titoli portoghesi: devono essere scartati
    assert not is_italian_news("Cérebro com mais golo e sem limites: Gabri Veiga vai estar na seleção espanhola")


def test_is_italian_news_casi_reali_2026_09_17():
    """I 61 titoli stranieri davvero pubblicati il 17/09/2026 (docs/25 §2).

    Erano passati dal vecchio filtro a liste di parole perché non contenevano nessuna
    parola-chiave straniera: il portale dichiarava «titoli in lingua italiana» e
    pubblicava olandese, tedesco, francese, spagnolo, portoghese e inglese. Ogni riga
    qui sotto è una voce vista su una scheda pubblicata.
    """
    from fda.sources.news import is_italian_news

    stranieri = [
        # olandese
        "FC Utrecht Maatjes officieel van start in Stadion Galgenwaard",
        "Voormalig FC Twente-ster Bryan Ruiz begint aan eerste klus als hoofdtrainer",
        "Ajax-coach Míchel hoopt op komst Bissouma: 'Heeft veel kwaliteiten'",
        # inglese
        "Bournemouth left-back Adrien Truffert named in Zinédine Zidane’s first extended France squad",
        "Mark Walter sells stake in Chelsea FC amid investigation",
        "When will Man United’s £2bn new stadium open? Latest news amid ‘opening date’ reports",
        "Rodri a player 'we cannot replace,' says Man City's Hugo Viana",
        "Nottingham Forest stadium expansion plans approved",
        "Hull FC suspend prop forward Sam Lisone pending investigation",
        "7pm BST: Live U21s football - watch West Ham United v Liverpool",
        # francese
        "Auxerre - Still : « C'est peut-être romantique, mais... » : Sports - Orange - Sports",
        "Stade Brestois. Mama Baldé, opéré du pouce, espéré contre Auxerre",
        "VIDÉO. FC Lorient. Ibrahima Baldé : « Forcément content de mon match »",
        "Ligue 1. Le coordinateur sportif Kader Mangane sur le départ du Racing Club de Strasbourg",
        "« Genesio ne démissionnera pas » : le message qui circule à Marseille",
        "L’OGC Nice vers un triste record…",
        # spagnolo
        "Cómo afecta la detención de Rakan Al-Thani al futuro del Málaga CF",
        "Iñigo Pérez: \"No tengo miedo al cese\"",
        # tedesco
        "Trainerwechsel bei Leverkusen-Gegner",
        "Eintracht Frankfurt: Adi Hütters Knallhart-Kurs – Kader, System, Talente",
        "Nationalmannschaft: Jürgen Klopp setzt auf Felix Nmecha im DFB-Team",
        "WERDERFRAUEN: Nordderby erneut im Weserstadion",
        # portoghese
        "Petrasso: «Limpámos a nossa imagem»",
        "FC Porto tem nova academia de futebol no Paquistão",
        "«Agora é fácil falar!» Marco Silva analisa triunfo histórico do Benfica e visita ao FC Porto",
        "Manuel Mendonça: «Demonstração muito grande»",
    ]
    for t in stranieri:
        assert not is_italian_news(t), f"titolo straniero pubblicato: {t}"

    # Gli italiani dello stesso giorno devono restare: compresi i titoli urlati, che
    # il rilevatore statistico da solo legge come inglese o portoghese
    italiani = [
        "NAPOLI, LOBOTKA E IL RINNOVO: IL FUTURO DEL CENTROCAMPISTA RESTA UN REBUS",
        "FIORENTINA-NAPOLI, 300 TIFOSI AZZURRI AL FRANCHI: LA SQUADRA NON SARÀ SOLA",
        "FIGC * FEDERAZIONE ITALIANA GIUOCO CALCIO: «SERIE A WOMEN, DERBY ROMA SABATO 3 OTTOBRE ORE 18, MILAN-JUVENTUS DOMENICA 4",
        "Pellegrini difende Ez Abde dopo l'incidente della maglia di Ceuta: \"Il calcio non deve essere motivo di divisione, ma di",
        "Il Lens caccia Toppmöller: le motivazioni dietro l'esonero",
        "Newcastle, Jaissle: il pesante ko contro il Leeds è «difficile da digerire»",
        "Tottenham, De Zerbi nei guai: spesi 300 milioni ma la squadra non segna più",
        "Lo stadio del Levante si allaga dopo il diluvio: il tunnel sommerso dall'acqua, non si può giocare",
        "Ex viola, Gosens: «Il calcio è follia, mi hanno tagliato all'improvviso. Grato allo Schalke»",
        "Goncalo Ramos: \"Se segno non esulto perché il Benfica è la mia casa\". Sulla maglia n° 9, Ibra, Modric...",
    ]
    for t in italiani:
        assert is_italian_news(t), f"titolo italiano scartato: {t}"


def test_is_italian_news_senza_grammatica_non_pubblica():
    """Un titolo di soli nomi propri non dichiara nessuna lingua: non si pubblica.

    «Getafe vs Deportivo A Coruña» e «Nottingham Forest vs Leeds United» non hanno
    una sola parola italiana: pubblicarli come italiani era un azzardo, e sono di
    norma pagine di «quote e pronostici» o di diretta, che la card esclude comunque.
    """
    from fda.sources.news import is_italian_news

    assert not is_italian_news("Getafe vs Deportivo A Coruña")
    assert not is_italian_news("Nottingham Forest vs Leeds United")
    assert is_italian_news("Bologna-Torino, Orsolini prova il recupero")
