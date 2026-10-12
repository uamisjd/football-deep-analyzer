"""Regole circoscritte della sola Vita del club (docs/96), non del punteggio Clima.

Veti ricavati dai falsi positivi misurati. Non sono sentiment né una stima dell'impatto
sul risultato. Si guarda il titolo pubblicato, senza inventare il contenuto dell'articolo.
"""

from __future__ import annotations

import re

# Un titolo con una decisione/conseguenza esplicita non è scartato solo perché menziona
# una conferenza, un compleanno o l'Academy. Le altre regole esistenti restano applicabili.
MATERIAL_EVENT = re.compile(
    r"\b(?:esoner\w*|dimission\w*|licenzi\w*|scioper\w*|daspo|arrest\w*|inchiest\w*|"
    r"indagin\w*|procura|tribunale|ricors\w*|sentenz\w*|multa\w*|debit\w*|fallimen\w*|"
    r"protest\w*|scontri|rissa|lite|ammutin\w*|disciplin\w*|sanzion\w*|viet\w*|diviet\w*|"
    r"azionista|acquisizion\w*|licenza|revocat\w*|denunci\w*|accus\w*|minacc\w*|violenz\w*)\b", re.IGNORECASE,
)
SERVICE = re.compile(
    r"^\s*formazioni\b|^\s*statistiche\b.*risultati calcio|"
    r"\blive\s*[!:]|cronaca e aggiornamenti in tempo reale|"
    r"\bconvocat[oi]\b|\b(?:pronto per|verso) l[’']esordio\b|"
    r"\b(?:rientri|recuperi) in difesa\b|riprendersi (?:il|un) posto|\bespuls[oa]\b", re.IGNORECASE,
)
ANNOUNCEMENT = re.compile(
    r"incontro per i media|\bsi presenta\b|\bcompie \d{1,3} anni\b|\bbuon compleanno\b|"
    r"applausi allo stadio.*campioni del mondo", re.IGNORECASE,
)
OUT_OF_SCOPE = re.compile(r"\bacademy\b", re.IGNORECASE)
BARE_REPORT = re.compile(
    r"\ble parole di .+ al termine di\b|,\s*intervista\s+[^:«\"]+$|"
    r"si vendica sui social|risposta epica|fa il giro del web|"
    r"squadra giusta per me|mi sento gi[aà] a casa|"
    r"orgoglios\w* (?:della|di (?:vestire|indossare)(?: questa| la)?) maglia|"
    r"chi [eè] (?:il|la) (?:classe )?20\d\d\b|"
    r"\bstende (?:il|la|lo) .+ al\b", re.IGNORECASE,
)


def title_exclusion(title: str) -> str | None:
    """Motivo esclusivo dell'imbuto; None non certifica la rilevanza della notizia."""
    if MATERIAL_EVENT.search(title):
        return None
    if SERVICE.search(title):
        return "scartate"
    if ANNOUNCEMENT.search(title):
        return "annunci"
    if OUT_OF_SCOPE.search(title):
        return "fuori_ambito"
    if BARE_REPORT.search(title):
        return "piatti"
    return None


def whole_phrase(text: str, phrase: str) -> bool:
    """Testi già normalizzati: Roma non coincide con romanzo o Romagnoli."""
    # soft_key elimina l'apostrofo: «all’Atalanta» diventa «allatalanta». Conserviamo
    # le elisioni italiane, non prefissi arbitrari («aroma» non deve diventare Roma).
    prefix = r"(?:(?:all|dall|dell|nell|sull|un|l))?"
    return bool(phrase) and re.search(rf"(?<!\w){prefix}{re.escape(phrase)}(?!\w)", text) is not None
