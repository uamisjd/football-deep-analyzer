"""Criterio positivo per Vita del club, misurato in ombra prima dell'integrazione (docs/97).

Un segnale nel titolo non certifica la verità del fatto né l'impatto sulla partita.
L'assenza di segnale non dimostra irrilevanza: significa informazione insufficiente per
questa rassegna. Nessuna lista di club/giocatori/URL e nessuna ricerca di sentiment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClubSignal:
    kind: str                 # event = evento segnalato; analysis = analisi/dichiarazione
    topic: str
    label: str
    evidence: str             # porzione testuale del titolo, mai un riassunto inventato
    family: str


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Formati di servizio espliciti: non diventano eventi perché contengono una parola forte.
SERVICE_TITLE = _rx(r"^\s*(?:formazioni|statistiche)\b|\blive\s*[!:]|cronaca.{0,30}tempo reale|"
                    r"\b(?:pronostici?|pagelle|highlights)\b|dove veder|in diretta|"
                    r"\bquote\b.{0,30}(?:1x2|scommess\w*|bookmaker|pronostic\w*)")
OFF_SCOPE = _rx(r"\b(?:ballottaggio|minutaggi|minuti in nazionale|vip|gotha|collezione|"
                r"souvenir|commemorazion\w*|compleanno|maglia celebrativa)\b|"
                r"ritirare la maglia|tifoso speciale|la regia|dazn.{0,20}sky")
# Un'intenzione, un dubbio o una smentita non viene presentata come evento compiuto.
UNCERTAIN = _rx(r"\?|\b(?:possibil\w*|ipotizz\w*|ipotesi|potrebbe|potrebbero|sarebbe|"
                 r"indiscrezion\w*|rischia|in bilico|smentisc\w*|smentit\w*|nega|nessun[ao]?|non conferm\w*)\b")

EVENT_RULES = (
    ("societa", "Assetto societario", "ownership",
     _rx(r"\b(?:divent\w* azionist\w*|entra\w* nell[’']?azionariato|"
         r"acquisizion\w* del club|acquist\w* (?:il club|le quote)|cedut\w* (?:il club|le quote)|"
         r"nuov[ao] propriet[aà]|passaggio di propriet[aà])\b")),
    ("societa", "Incarichi societari", "appointments",
     _rx(r"\b(?:entran\w* nell[’']?organigramma|nominat\w*.{0,35}(?:presidente|direttore|dirigente)|"
         r"nuovo (?:direttore sportivo|direttore generale|presidente)|chief of football|"
         r"dimissioni del presidente)\b")),
    ("societa", "Vincoli e conti del club", "finance",
     _rx(r"\b(?:debiti|insolvenza|fallimento|amministrazione controllata|"
         r"bilancio.{0,35}(?:perdit\w*|approvat\w*|depositat\w*)|"
         r"aumento di capitale|ricapitalizz\w*|licenza (?:negata|revocata)|"
         r"stipendi (?:non pagati|arretrati))\b")),
    ("allenatore", "Panchina", "coach",
     _rx(r"\b(?:esoner\w*|dimissioni|si dimette|mi dimetto|panchina (?:a rischio|in bilico)|"
         r"rischia la panchina|rescissione.{0,30}(?:tecnico|allenatore)|"
         r"nomina.{0,25}(?:tecnico|allenatore)|nuovo (?:allenatore|tecnico))\b")),
    ("tifo", "Provvedimenti sulla tifoseria", "supporters_orders",
     _rx(r"\b(?:misure cautelari|daspo|divieto di trasferta|trasferta vietata|"
         r"chiusura (?:della curva|del settore)|settore ospiti chiuso|"
         r"vendita (?:dei )?biglietti (?:vietata|sospesa))\b")),
    ("tifo", "Presenza e accesso dei tifosi", "supporters_access",
     _rx(r"\b(?:tifosi.{0,45}tornano in trasferta.{0,25}dopo|"
         r"revocat\w*.{0,25}divieto|riapert\w*.{0,25}settore ospiti)\b")),
    ("tifo", "Protesta della tifoseria", "supporters_protest",
     _rx(r"\b(?:scioper\w*|protest\w*|contestazion\w*|disert\w*)\b")),
    ("societa", "Provvedimento o ricorso", "club_order",
     _rx(r"\b(?:multa(?:to|ti|ta|te)?|ricorso|sentenza|tribunale|deferit\w*|inchiesta|indagin\w*|"
         r"procura|denunc\w*|sanzione.{0,25}club)\b")),
    ("spogliatoio", "Disciplina e organizzazione", "discipline",
     _rx(r"\b(?:ritiro punitivo|ammutin\w*|provvedimento disciplinare|"
         r"motivi disciplinari|allenament\w* (?:annullat\w*|sospes\w*)|"
         r"riss[ae]|lite.{0,35}doppio rosso)\b")),
    ("fuoricampo", "Episodio fuori dal campo", "off_pitch",
     _rx(r"\b(?:arrestat\w*|rinviat\w* a giudizio|incidente stradale|"
         r"incidente d[’']auto|patente ritirata|tasso alcolemico)\b")),
)
STADIUM = _rx(r"\b(?:stadio|impianto|curva|tribuna)\b")
STADIUM_ACTION = _rx(r"\b(?:variante|approvat\w*|bocciat\w*|finanziament\w*|"
                      r"costi|vendita|chiusur\w*|riapert\w*|inagibil\w*)\b")
SUPPORT = _rx(r"\b(?:mai avuto dubbi su|conferma.{0,20}fiducia|fiducia (?:al|nel) tecnico|"
              r"sostegno.{0,20}allenatore|smentisce.{0,20}vendita)\b")
RELATION = _rx(r"\bsquadra.{0,25}(?:segue|sostiene)(?: davvero)? (?!(?:il|la|lo|un|una)\b)(?-i:[A-ZÀ-Ö][\w’'-]+)|"
               r"\b(?:rapporto|contrasto|fiducia|spaccatur\w*).{0,25}(?:squadra.{0,15}(?:tecnico|allenatore)|spogliatoio)\b")
REPORTAGE = _rx(r"\b(?:reportage|racconta|analizza|avverte)\b")
SOCIETAL = _rx(r"\b(?:tifosi.{0,40}(?:rischiano|esclus\w*|lasciati indietro)|"
               r"rapporto.{0,30}(?:club|citt[aà]|tifosi)|identit[aà] del club)\b")


def club_signal(title: str) -> ClubSignal | None:
    """Evento esplicito o analisi attribuibile dal titolo, altrimenti astensione."""
    if SERVICE_TITLE.search(title):
        return None
    # La memoria sportiva/il gossip non occupano la rassegna; un provvedimento concreto
    # resta valutabile anche se nomina uno stadio, una maglia o una testata televisiva.
    off = OFF_SCOPE.search(title)
    if off and not _rx(r"\b(?:revocat\w*|vietat\w*|daspo|arrestat\w*|inchiesta|procura)\b").search(title):
        return None
    for pattern, label, family in ((SUPPORT, "Dichiarazione di sostegno", "support"),
                                   (RELATION, "Rapporto squadra–tecnico", "team_coach")):
        match = pattern.search(title)
        if match:
            topic = "societa" if "vendita" in match.group().lower() else "allenatore"
            return ClubSignal("analysis", topic, label, match.group(), family)
    if REPORTAGE.search(title) and (match := SOCIETAL.search(title)):
        return ClubSignal("analysis", "dichiarazioni", "Analisi club–tifoseria", match.group(), "club_supporters")
    narration = re.sub(r'«[^»]*»|“[^”]*”|"[^"]*"', " ", title)
    if STADIUM.search(title) and (match := STADIUM_ACTION.search(title)):
        kind = "analysis" if UNCERTAIN.search(narration) or not STADIUM_ACTION.search(narration) else "event"
        return ClubSignal(kind, "stadio", "Decisione sull’impianto", match.group(), "stadium")
    ordered_rules = sorted(EVENT_RULES, key=lambda rule: rule[2] == "supporters_protest")
    for topic, label, family, pattern in ordered_rules:
        match = pattern.search(title)
        if match:
            # «protesta» deve riferirsi a un soggetto di club, non alla regia TV.
            if family == "supporters_protest" and not _rx(r"\b(?:tifosi|ultras|curva|dirigenza)\b").search(title):
                continue
            kind = "analysis" if UNCERTAIN.search(narration) or not pattern.search(narration) else "event"
            return ClubSignal(kind, topic, label, match.group(), family)
    return None
