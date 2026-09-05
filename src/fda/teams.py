"""Normalizzazione dei nomi squadra tra fonti (football-data / FotMob / Understat / ESPN).

Il nome canonico è quello di FotMob (è la fonte principale). Le tabelle dei modelli usano
`canonical(name)`; i casi non coperti dalla mappa passano per una normalizzazione "soft"
(minuscole, senza accenti/punteggiatura, senza suffissi tipo FC/AC/Calcio).
"""

from __future__ import annotations

import re
import unicodedata

# fonte → nome FotMob. Copre le 7 leghe seguite; ampliare qui quando spunta un nome nuovo.
ALIASES: dict[str, str] = {
    # ---- Serie A ----
    "inter": "Inter", "internazionale": "Inter", "inter milan": "Inter",
    "milan": "AC Milan", "ac milan": "AC Milan",
    "juventus": "Juventus", "napoli": "Napoli", "roma": "Roma", "as roma": "Roma",
    "lazio": "Lazio", "atalanta": "Atalanta", "fiorentina": "Fiorentina", "bologna": "Bologna",
    "torino": "Torino", "udinese": "Udinese", "genoa": "Genoa", "sassuolo": "Sassuolo",
    "cagliari": "Cagliari", "lecce": "Lecce", "parma": "Parma", "como": "Como",
    "verona": "Hellas Verona", "hellas verona": "Hellas Verona", "cremonese": "Cremonese",
    "pisa": "Pisa", "venezia": "Venezia", "frosinone": "Frosinone", "monza": "Monza",
    "empoli": "Empoli", "salernitana": "Salernitana", "spezia": "Spezia", "sampdoria": "Sampdoria",
    "palermo": "Palermo", "bari": "Bari",
    # ---- Premier League ----
    "man city": "Manchester City", "manchester city": "Manchester City",
    "man united": "Manchester United", "man utd": "Manchester United", "manchester united": "Manchester United",
    "arsenal": "Arsenal", "chelsea": "Chelsea", "liverpool": "Liverpool",
    "tottenham": "Tottenham", "tottenham hotspur": "Tottenham", "spurs": "Tottenham",
    "newcastle": "Newcastle United", "newcastle united": "Newcastle United",
    "aston villa": "Aston Villa", "brighton": "Brighton & Hove Albion",
    "brighton and hove albion": "Brighton & Hove Albion", "brighton & hove albion": "Brighton & Hove Albion",
    "west ham": "West Ham United", "west ham united": "West Ham United",
    "wolves": "Wolverhampton Wanderers", "wolverhampton": "Wolverhampton Wanderers",
    "wolverhampton wanderers": "Wolverhampton Wanderers",
    "everton": "Everton", "fulham": "Fulham", "brentford": "Brentford", "bournemouth": "Bournemouth",
    "afc bournemouth": "Bournemouth", "crystal palace": "Crystal Palace",
    "nott'm forest": "Nottingham Forest", "nottingham forest": "Nottingham Forest",
    "leeds": "Leeds United", "leeds united": "Leeds United", "sunderland": "Sunderland",
    "burnley": "Burnley", "ipswich": "Ipswich Town", "ipswich town": "Ipswich Town",
    "leicester": "Leicester City", "leicester city": "Leicester City",
    "southampton": "Southampton", "hull": "Hull City", "hull city": "Hull City",
    "coventry": "Coventry City", "coventry city": "Coventry City", "sheffield united": "Sheffield United",
    "sheffield utd": "Sheffield United", "luton": "Luton Town", "luton town": "Luton Town",
    # ---- LaLiga ----
    "barcelona": "Barcelona", "fc barcelona": "Barcelona", "real madrid": "Real Madrid",
    "ath madrid": "Atletico Madrid", "atletico madrid": "Atletico Madrid", "atlético madrid": "Atletico Madrid",
    "ath bilbao": "Athletic Club", "athletic bilbao": "Athletic Club", "athletic club": "Athletic Club",
    "betis": "Real Betis", "real betis": "Real Betis", "sevilla": "Sevilla", "villarreal": "Villarreal",
    "sociedad": "Real Sociedad", "real sociedad": "Real Sociedad", "valencia": "Valencia",
    "girona": "Girona", "osasuna": "Osasuna", "celta": "Celta Vigo", "celta vigo": "Celta Vigo",
    "getafe": "Getafe", "mallorca": "Mallorca", "alaves": "Alaves", "alavés": "Alaves",
    "deportivo alaves": "Alaves", "vallecano": "Rayo Vallecano", "rayo vallecano": "Rayo Vallecano",
    "espanol": "Espanyol", "espanyol": "Espanyol", "las palmas": "Las Palmas", "leganes": "Leganes",
    "leganés": "Leganes", "valladolid": "Real Valladolid", "real valladolid": "Real Valladolid",
    "levante": "Levante", "elche": "Elche", "oviedo": "Real Oviedo", "real oviedo": "Real Oviedo",
    "la coruna": "Deportivo La Coruna", "deportivo la coruna": "Deportivo La Coruna",
    "deportivo a coruña": "Deportivo La Coruna", "deportivo": "Deportivo La Coruna",
    "santander": "Racing Santander", "racing santander": "Racing Santander", "malaga": "Malaga",
    "málaga": "Malaga", "cadiz": "Cadiz", "cádiz": "Cadiz", "granada": "Granada", "almeria": "Almeria",
    # ---- Bundesliga ----
    "bayern munich": "Bayern München", "bayern münchen": "Bayern München", "bayern": "Bayern München",
    "fc bayern münchen": "Bayern München",
    "dortmund": "Borussia Dortmund", "borussia dortmund": "Borussia Dortmund",
    "leverkusen": "Bayer Leverkusen", "bayer leverkusen": "Bayer Leverkusen", "bayer 04 leverkusen": "Bayer Leverkusen",
    "rb leipzig": "RB Leipzig", "leipzig": "RB Leipzig", "stuttgart": "VfB Stuttgart", "vfb stuttgart": "VfB Stuttgart",
    "ein frankfurt": "Eintracht Frankfurt", "eintracht frankfurt": "Eintracht Frankfurt",
    "freiburg": "SC Freiburg", "sc freiburg": "SC Freiburg", "m'gladbach": "Borussia Mönchengladbach",
    "borussia monchengladbach": "Borussia Mönchengladbach", "borussia mönchengladbach": "Borussia Mönchengladbach",
    "gladbach": "Borussia Mönchengladbach", "wolfsburg": "VfL Wolfsburg", "vfl wolfsburg": "VfL Wolfsburg",
    "mainz": "Mainz 05", "mainz 05": "Mainz 05", "1. fsv mainz 05": "Mainz 05",
    "augsburg": "FC Augsburg", "fc augsburg": "FC Augsburg", "werder bremen": "Werder Bremen",
    "hoffenheim": "TSG Hoffenheim", "tsg hoffenheim": "TSG Hoffenheim", "1899 hoffenheim": "TSG Hoffenheim",
    "union berlin": "Union Berlin", "1. fc union berlin": "Union Berlin", "heidenheim": "1. FC Heidenheim",
    "1. fc heidenheim": "1. FC Heidenheim", "st pauli": "FC St. Pauli", "st. pauli": "FC St. Pauli",
    "fc st. pauli": "FC St. Pauli", "hamburg": "Hamburger SV", "hamburger sv": "Hamburger SV",
    "fc koln": "1. FC Köln", "koln": "1. FC Köln", "köln": "1. FC Köln", "1. fc köln": "1. FC Köln",
    "elversberg": "SV Elversberg", "sv elversberg": "SV Elversberg", "paderborn": "SC Paderborn 07",
    "sc paderborn": "SC Paderborn 07", "sc paderborn 07": "SC Paderborn 07", "schalke 04": "Schalke 04",
    "schalke": "Schalke 04", "bochum": "VfL Bochum", "vfl bochum": "VfL Bochum", "holstein kiel": "Holstein Kiel",
    "darmstadt": "Darmstadt 98", "hertha": "Hertha BSC", "hertha berlin": "Hertha BSC",
    # ---- Ligue 1 ----
    "paris sg": "Paris Saint-Germain", "psg": "Paris Saint-Germain", "paris saint-germain": "Paris Saint-Germain",
    "paris saint germain": "Paris Saint-Germain", "marseille": "Marseille", "olympique marseille": "Marseille",
    "monaco": "AS Monaco", "as monaco": "AS Monaco", "lyon": "Lyon", "olympique lyonnais": "Lyon",
    "lille": "Lille", "losc lille": "Lille", "nice": "Nice", "ogc nice": "Nice", "lens": "Lens", "rc lens": "Lens",
    "rennes": "Rennes", "stade rennais": "Rennes", "strasbourg": "Strasbourg", "rc strasbourg": "Strasbourg",
    "brest": "Brest", "stade brestois": "Brest", "toulouse": "Toulouse", "nantes": "Nantes", "fc nantes": "Nantes",
    "auxerre": "Auxerre", "aj auxerre": "Auxerre", "angers": "Angers", "angers sco": "Angers", "le havre": "Le Havre",
    "lorient": "Lorient", "fc lorient": "Lorient", "metz": "Metz", "fc metz": "Metz", "paris fc": "Paris FC",
    "reims": "Reims", "stade de reims": "Reims", "montpellier": "Montpellier", "st etienne": "Saint-Étienne",
    "saint-etienne": "Saint-Étienne", "saint-étienne": "Saint-Étienne", "as saint-étienne": "Saint-Étienne",
    "troyes": "Troyes", "estac troyes": "Troyes", "le mans": "Le Mans",
    # ---- Eredivisie ----
    "psv eindhoven": "PSV Eindhoven", "psv": "PSV Eindhoven", "ajax": "Ajax", "ajax amsterdam": "Ajax",
    "afc ajax": "Ajax", "feyenoord": "Feyenoord", "feyenoord rotterdam": "Feyenoord", "az alkmaar": "AZ Alkmaar",
    "az": "AZ Alkmaar", "twente": "FC Twente", "fc twente": "FC Twente", "utrecht": "FC Utrecht", "fc utrecht": "FC Utrecht",
    "nec nijmegen": "NEC Nijmegen", "nijmegen": "NEC Nijmegen", "nec": "NEC Nijmegen", "go ahead eagles": "Go Ahead Eagles",
    "groningen": "FC Groningen", "fc groningen": "FC Groningen", "sparta rotterdam": "Sparta Rotterdam",
    "heerenveen": "SC Heerenveen", "sc heerenveen": "SC Heerenveen", "fortuna sittard": "Fortuna Sittard",
    "heracles": "Heracles Almelo", "heracles almelo": "Heracles Almelo", "pec zwolle": "PEC Zwolle", "zwolle": "PEC Zwolle",
    "willem ii": "Willem II", "excelsior": "Excelsior", "volendam": "FC Volendam", "fc volendam": "FC Volendam",
    "telstar": "Telstar", "waalwijk": "RKC Waalwijk", "rkc waalwijk": "RKC Waalwijk", "almere city": "Almere City",
    # ---- Liga Portugal ----
    "benfica": "Benfica", "sl benfica": "Benfica", "porto": "FC Porto", "fc porto": "FC Porto",
    "sp lisbon": "Sporting CP", "sporting cp": "Sporting CP", "sporting lisbon": "Sporting CP", "sporting": "Sporting CP",
    "braga": "SC Braga", "sp braga": "SC Braga", "sc braga": "SC Braga", "guimaraes": "Vitória SC",
    "vitoria guimaraes": "Vitória SC", "vitória sc": "Vitória SC", "famalicao": "Famalicão", "famalicão": "Famalicão",
    "casa pia": "Casa Pia", "estoril": "Estoril Praia", "estoril praia": "Estoril Praia", "arouca": "Arouca",
    "rio ave": "Rio Ave", "gil vicente": "Gil Vicente", "moreirense": "Moreirense", "santa clara": "Santa Clara",
    "nacional": "Nacional", "cd nacional": "Nacional", "estrela": "Estrela Amadora", "estrela amadora": "Estrela Amadora",
    "avs": "AVS", "boavista": "Boavista", "farense": "Farense", "alverca": "Alverca", "tondela": "Tondela",
    "vizela": "Vizela", "chaves": "Chaves", "portimonense": "Portimonense",
}

_SUFFIXES = re.compile(r"\b(fc|cf|ac|as|ss|us|sc|afc|rc|cd|ud|sd|calcio|club|de|futbol|football|1\.)\b")


def soft_key(name: str) -> str:
    """Chiave di confronto: minuscole, senza accenti, punteggiatura e suffissi comuni."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", "and").replace("-", " ").replace("'", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    s = _SUFFIXES.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# indice per chiave soft, così "FC Barcelona"/"Barcelona"/"barcelona" convergono
_INDEX: dict[str, str] = {}
for alias, canon in ALIASES.items():
    _INDEX.setdefault(soft_key(alias), canon)
    _INDEX.setdefault(soft_key(canon), canon)


def canonical(name: str | None) -> str:
    """Nome canonico (FotMob) di una squadra; se sconosciuto, il nome ripulito."""
    if not name:
        return ""
    raw = str(name).strip()
    low = raw.lower()
    if low in ALIASES:
        return ALIASES[low]
    key = soft_key(raw)
    if key in _INDEX:
        return _INDEX[key]
    return raw


def same_team(a: str | None, b: str | None) -> bool:
    return canonical(a) == canonical(b) and bool(canonical(a))
