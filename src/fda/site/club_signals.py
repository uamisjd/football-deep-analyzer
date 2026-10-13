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
SERVICE_TITLE = _rx(r"^\s*(?:formazioni|statistiche|scheda\s+squadra)\b|"
                    r"\blive\s*[!:]|cronaca.{0,30}tempo reale|"
                    r"\b(?:pronostici?|pagelle|highlights)\b|dove veder|in diretta|"
                    r"risultati di calcio di oggi|risultati e classifiche|"
                    r"riassunto della partita|notizie e informazioni - calcio|"
                    r"notizie, calendario e risultati|risultato, info partita|"
                    r"\bquote\b.{0,30}(?:1x2|scommess\w*|bookmaker|pronostic\w*)")
OFF_SCOPE = _rx(r"\b(?:ballottaggio|minutaggi|minuti in nazionale|vip|gotha|collezione|"
                r"souvenir|commemorazion\w*|compleanno|maglia celebrativa|"
                r"seconda categoria|prima categoria|promozione|eccellenza|allievi|juniores|"
                r"serie c|serie d|calcio a 5|calcio a 11|uisp|memorial|old star|e-22 youth|"
                r"coppa provincia|valle belbo|sestri|caprarica|picerno|colonia julia|"
                r"under\s*1\d|under\s*2[013]|u1[4-9]|u2[013]|"
                r"femminile|women|féminines|vrouwen|futsal|jugend|wsl|"
                r"fantabilancio|fantamedia|fantacalcio|fanta)\b|"
                r"arbitra.{0,35}sezione di|colpito con un calcio|aggredito mentre|"
                r"apre un nuovo store|nuovo third kit|"
                r"ritirare la maglia|tifoso speciale|la regia|dazn.{0,20}sky")
# Un'intenzione, un dubbio o una smentita non viene presentata come evento compiuto.
UNCERTAIN = _rx(r"\?|\b(?:possibil\w*|ipotizz\w*|ipotesi|potrebbe|potrebbero|sarebbe|"
                 r"indiscrezion\w*|rischia|in bilico|smentisc\w*|smentit\w*|nega|nessun[ao]?|non conferm\w*)\b")

EVENT_RULES = (
    ("societa", "Assetto societario", "ownership",
     _rx(r"\b(?:divent\w* azionist\w*|entra\w* nell[’']?azionariato|"
         r"acquisizion\w* del club|acquist\w* (?:il club|le quote)|cedut\w* (?:il club|le quote)|"
         r"mett\w* in vendita|piano da \d+\s*miliard\w*|"
         r"nuov[ao] propriet[aà]|passaggio (?:di|delle) (?:propriet[aà]|quote)|"
         r"rientra nella efc|torna a far parte dell[’']efc|"
         r"rinnovo commerciale ed espansione)\b")),
    ("societa", "Incarichi societari", "appointments",
     _rx(r"\b(?:entran\w* nell[’']?organigramma|entra\w* nella governance|"
         r"nominat\w*.{0,35}(?:presidente|direttore|dirigente)|"
         r"nuovo (?:direttore sportivo|direttore generale|presidente)|chief of football|"
         r"dimissioni del presidente)\b")),
    ("societa", "Vincoli e conti del club", "finance",
     _rx(r"\b(?:debiti|insolvenza|fallimento|amministrazione controllata|"
         r"bilanci\w*.{0,35}(?:perdit\w*|approvat\w*|depositat\w*|rosso di|falsat\w*)|"
         r"violazioni finanziarie|aumento di capitale|ricapitalizz\w*|licenza (?:negata|revocata)|"
         r"stipendi (?:non pagati|arretrati))\b")),
    ("allenatore", "Panchina", "coach",
     _rx(r"\b(?:esoner\w*|dimissioni|si dimette|mi dimetto|panchina (?:a rischio|in bilico)|"
         r"rischia la panchina|rescissione.{0,30}(?:tecnico|allenatore)|"
         r"nomina.{0,25}(?:tecnico|allenatore)|nuovo (?:allenatore|tecnico)|"
         r"firma un nuovo contratto.{0,30}fino al \d{4})\b")),
    ("tifo", "Provvedimenti sulla tifoseria", "supporters_orders",
     _rx(r"\b(?:misure cautelari|daspo|divieto di trasferta|trasferta vietata|"
         r"chiusura (?:della curva|del settore)|settore ospiti chiuso|"
         r"vendita (?:dei )?biglietti (?:vietata|sospesa))\b")),
    ("tifo", "Presenza e accesso dei tifosi", "supporters_access",
     _rx(r"\b(?:tifosi.{0,45}tornano in trasferta.{0,25}dopo|"
         r"revocat\w*.{0,25}divieto|riapert\w*.{0,25}settore ospiti)\b")),
    ("tifo", "Protesta della tifoseria", "supporters_protest",
     _rx(r"\b(?:scioper\w*|protest\w*|contestazion\w*|disert\w*|curva.{0,25}si svuota)\b")),
    ("societa", "Provvedimento o ricorso", "club_order",
     _rx(r"\b(?:multa(?:to|ti|ta|te)?|ricors[oi]|sentenza|tribunale|tar boccia|deferit\w*|"
         r"inchiesta|indagin\w*|plusvalenze.{0,25}assolt\w*|invia documenti a uefa|"
         r"procura|denunc\w*|sanzione.{0,25}club)\b")),
    ("spogliatoio", "Disciplina e organizzazione", "discipline",
     _rx(r"\b(?:ritiro punitivo|ammutin\w*|provvedimento disciplinare|"
         r"motivi disciplinari|allenament\w* (?:annullat\w*|sospes\w*)|"
         r"riss[ae]|lite.{0,35}doppio rosso|in campo vola di tutto:\s*sospesa)\b")),
    ("fuoricampo", "Episodio fuori dal campo", "off_pitch",
     _rx(r"\b(?:arrestat\w*|notte in carcere|rinviat\w* a giudizio|incidente stradale|"
         r"incidente d[’']auto|incidente per.{0,45}secondo in meno di un mese|"
         r"patente ritirata|tasso alcolemico)\b")),
    ("infortuni", "Infermeria e rientri", "injuries",
     _rx(r"\b(?:grave infortunio|infortunato in\b|infortunio.{0,25}:\s*cosa si è fatto|"
         r"distrazione alla coscia|lussazione alla spalla|problemi al tendine|"
         r"ancora ai box:\s*il|pronto a tornare dopo \d+ giorni|"
         r"inizia la nuova fase del recupero|verso il recupero di|rientra l[’']allarme|"
         r"(?:infortun\w*|tegola|ko).{0,35}tempi di recupero)\b")),
    ("mercato", "Contratti e rosa", "contracts",
     _rx(r"\b(?:rinnov\w* (?:del contratto |il contratto )?fino al \d{4}|blinda.{0,35}pronto a rinnovare|"
         r"nessun rinnovo all[’']orizzonte.{0,35}rischia di perderlo|"
         r"sarà un nuovo giocatore.{0,45}superate le visite mediche|"
         r"mandato in prestito.{0,45}segnare a raffica)\b")),
)
STADIUM = _rx(r"\b(?:stadio|impianto|curva|tribuna)\b")
STADIUM_ACTION = _rx(r"\b(?:variante|approvat\w*|bocciat\w*|finanziament\w*|lettera di intenti|"
                     r"costruire il suo stadio|piccolissimo stadio.{0,75}trattare affari|"
                     r"costi|vendita|chiusur\w*|riapert\w*|inagibil\w*)\b")
SUPPORT = _rx(r"\b(?:mai avuto dubbi su|conferma.{0,20}fiducia|fiducia (?:al|nel) tecnico|"
              r"sostegno.{0,20}allenatore|smentisce.{0,25}(?:vendita|accuse)|"
              r"accuse.{0,25}senza fondamento|momento storico tra stadio e vetta)\b")
RELATION = _rx(r"\bsquadra.{0,25}(?:segue|sostiene)(?: davvero)? (?!(?:il|la|lo|un|una)\b)(?-i:[A-ZÀ-Ö][\w’'-]+)|"
               r"\b(?:rapporto|contrasto|fiducia|spaccatur\w*).{0,25}(?:squadra.{0,15}(?:tecnico|allenatore)|spogliatoio)\b")
REPORTAGE = _rx(r"\b(?:reportage|racconta|analizza|avverte)\b")
SOCIETAL = _rx(r"\b(?:tifosi.{0,40}(?:rischiano|esclus\w*|lasciati indietro)|"
               r"rapporto.{0,30}(?:club|citt[aà]|tifosi)|identit[aà] del club)\b")
TACTICAL_CONTEXT = _rx(
    r"\b(?:per migliorare sulle palle inattive|"
    r"diventato una squadra che fa tanto possesso palla|"
    r"viaggio alla «scuola».{0,80}laboratorio da|"
    r"più visibilità globale,\s*ma la crescita economica resta una sfida|"
    r"vinceva tutto,\s*ora vende l[’']erba ai tifosi|"
    r"quante soluzioni per\s+(?-i:[A-ZÀ-Ö][\w’'-]+):\s*non solo|"
    r"svolta\s+(?-i:[A-ZÀ-Ö][\w’'-]+):\s*la rimonta|"
    r"i gol sono pochi:\s*non basta|"
    r"segnano tutti eccetto gli attaccanti|"
    r"d['’]assalto:\s*l['’]attacco si accende con|"
    r"anteprima di (?:premier league|ligue 1|serie a|la\s*liga|liga|bundesliga|eredivisie|primeira liga).{0,35}tutto quello che c[’']è da sapere|"
    r"incassa un gol dopo \d+|subisce il gol più veloce della|"
    r"pareggia.{0,25}ed entra nella storia|in vantaggio dopo \d+ secondi|"
    r"(?:beffa|gela|trova il pareggio|doppietta).{0,30}(?:nel recupero|al 9\d['’])|"
    r"già decisivo col\b|"
    r"avvio di campionato.{0,25}è stato folgorante|"
    r"travolge.{0,25}e vola al secondo posto|"
    r"amichevole durante la sosta|pareggio.{0,35}in amichevole)\b"
)


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
            low_m = match.group().lower()
            topic = "societa" if any(w in low_m for w in ("vendita", "accuse", "stadio")) else "allenatore"
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
    if match := TACTICAL_CONTEXT.search(title):
        return ClubSignal("analysis", "allenatore", "Analisi tecnica e di contesto", match.group(), "tactical_context")
    return None
