"""Sintesi in italiano dei titoli in lingua originale (docs/106).

Vive in ``site/`` e non in ``sources/``: non chiama la rete e non è una fonte. Le fonti
pubblicate nella pagina «Info» sono i moduli che fanno richieste, e quel contratto è
verificato da ``tests/test_site.py`` contro l'elenco pubblicato.

Perché esiste. La stampa italiana non scrive dei club minori delle leghe estere: sulle
schede NED1/POR1 del 2026-10-13 la card «Vita del club» era vuota in 10 schede su 10, e la
prova fatta togliendo il filtro lingua non ha prodotto **nessuna** voce pubblicabile (le
uniche voci non italiane in archivio erano pagine di servizio). La stampa locale, invece,
quei club li segue ogni giorno.

Cosa fa, esattamente. Non traduce e non riscrive. Da un titolo in lingua originale ricava:

- **un'etichetta** in italiano presa da un vocabolario chiuso (``Infortunio``, ``Mercato``,
  …), scelta con una priorità fissa e dichiarata: è la riga di sintesi scritta da noi;
- **l'evidenza**: le parole del titolo originale che provano quel segnale, citate com'è;
- il resto lo fa la card: testata, data, lingua dichiarata e titolo originale per intero.

Quando il vocabolario non riconosce nulla, la voce **non viene classificata** e non si
pubblica: un'etichetta inventata sarebbe peggio di un titolo in olandese. Nessun
sentiment, nessun riassunto, nessuna inferenza oltre le parole presenti.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Sintesi:
    """Etichetta italiana + prova nel testo originale, senza traduzione."""

    chiave: str        # codice del tema, es. "infortunio"
    etichetta: str     # riga di sintesi in italiano, es. "Infortunio"
    nota: str          # cosa significa per la partita (frase fissa del tema)
    evidenza: str      # parole originali che provano il segnale


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


#: Temi in ordine di priorità: quello che un analista guarda per primo vince. L'ordine è
#: dichiarato e verificabile, non dipende dall'ordine delle parole nel titolo.
#: Ogni tema: (chiave, etichetta, nota, lingue → espressioni).
TEMI: tuple[tuple[str, str, str, dict[str, re.Pattern[str]]], ...] = (
    ("infortunio", "Infortunio", "Può pesare sulle scelte di formazione.", {
        "nl": _rx(r"\b(?:geblesseerd\w*|blessure\w*|kwetsuur\w*|geblesseerde|"
                  r"out\s+(?:met\s+een|voor|tot)|niet\s+fit|afwezig\s+met)\b"),
        "pt": _rx(r"\b(?:lesã\w*|lesõ\w*|lesionad\w*|lesao\w*|desfalque\w*|"
                  r"departamento\s+m[ée]dico|boletim\s+cl[íi]nico|trauma\w*)\b"),
    }),
    ("squalifica", "Squalifica e cartellini", "Può pesare sulla disponibilità.", {
        "nl": _rx(r"\b(?:schorsing\w*|geschorst\w*|rood\s+gehad|"
                  r"twee\s+keer\s+geel|rode\s+kaart|diskwalificat\w*)\b"),
        "pt": _rx(r"\b(?:suspens\w*|suspensã\w*|suspenso\w*|castigad\w*|castigo\w*|"
                  r"expuls\w*|cart[ãa]o\s+vermelho|vermelho\s+direto)\b"),
    }),
    ("contratto", "Contratto e rinnovo", "Riguarda il contratto di un tesserato.", {
        "nl": _rx(r"\b(?:contractverlenging\w*|verbintenis\w*|verlengt\w*|verlenging\w*|"
                  r"nieuw\s+contract|tekent\s+(?:bij|voor)|contract\s+tot)\b"),
        "pt": _rx(r"\b(?:renovaç\w*|renovacao\w*|renova\w*|v[íi]nculo\w*|"
                  r"novo\s+contrato|contrato\s+at[ée]\s+20\d\d)\b"),
    }),
    ("mercato", "Mercato", "Voce di mercato: riguarda la rosa, non la partita.", {
        "nl": _rx(r"\b(?:transfer\w*|aanwinst\w*|huurling\w*|verkocht\w*|verhuurd\w*|"
                  r"gecontracteerd\w*|bod\s+(?:van|uit)|interesse\s+van|op\s+weg\s+naar|"
                  r"haalt\s+(?:een|nieuwe)|nieuwe\s+(?:spits|doelman|keeper|verdediger|"
                  r"middenvelder|aanvaller))\b"),
        "pt": _rx(r"\b(?:transfer\w*|contrataç\w*|contratacao\w*|reforç\w*|reforco\w*|"
                  r"empr[ée]stimo\w*|vendid\w*|comprad\w*|mercado\s+de)\b"),
    }),
    ("panchina", "Guida tecnica", "Riguarda la panchina: chi guida la squadra.", {
        "nl": _rx(r"\b(?:trainer\w*|coach\w*|ontslag\w*|ontslagen\w*|aangesteld\w*|"
                  r"opvolger\s+van|hoofdtrainer\w*)\b"),
        "pt": _rx(r"\b(?:treinador\w*|t[ée]cnico\w*|demiss[ãa]o\w*|demitid\w*|"
                  r"despedid\w*|novo\s+t[ée]cnico)\b"),
    }),
    ("societa", "Società", "Riguarda la società, non il campo.", {
        "nl": _rx(r"\b(?:directie\w*|bestuur\w*|eigenaar\w*|overname\w*|overnemen\w*|"
                  r"financi[ëe]\w*|schuld\w*|investeerder\w*)\b"),
        "pt": _rx(r"\b(?:direç\w*|direcao\w*|presidente\w*|s[óo]cios\w*|d[íi]vida\w*|"
                  r"financ\w*|investidor\w*|sad\b|venda\s+do\s+clube)\b"),
    }),
    ("stadio", "Stadio e impianto", "Riguarda l'impianto, non la partita.", {
        "nl": _rx(r"\b(?:stadion\w*|verbouwing\w*|nieuw\s+stadion|kunstgras\w*)\b"),
        "pt": _rx(r"\b(?:est[áa]dio\w*|obras\s+no|relvado\w*|pavilh[ãa]o\w*)\b"),
    }),
    ("dichiarazione", "Dichiarazione o analisi", "Non è un fatto: è quello che dice qualcuno.", {
        "nl": _rx(r"\b(?:zegt\w*|vindt\w*|vinden\w*|kritiek\w*|baalt\w*|"
                  r"teleurgesteld\w*|klaar\s+mee|waarschuwt\w*|analyse\w*|openhartig\w*|"
                  r"is\s+van\s+mening|reageert\w*)\b"),
        "pt": _rx(r"\b(?:diz\w*|afirma\w*|critica\w*|lamenta\w*|reage\w*|"
                  r"an[áa]lise\w*|opini[ãa]o\w*|garante\w*)\b"),
    }),
    ("forma", "Forma e risultati", "Riguarda come sta andando la squadra.", {
        "nl": _rx(r"\b(?:zege\w*|nederlaag\w*|gelijkspel\w*|wint\w*|verliest\w*|"
                  r"verlies\w*|onverslagen\w*|regen\s+re\w*|klop\w*)\b"),
        "pt": _rx(r"\b(?:vit[óo]ria\w*|derrota\w*|empate\w*|vence\w*|perde\w*|"
                  r"invict\w*|s[ée]rie\s+de)\b"),
    }),
)

#: Pagine di servizio nelle lingue locali: dirette, formazioni, riepiloghi, pronostici.
#: Stessa funzione di ``SERVICE_TITLE`` per l'italiano (``sources/news.py``): non è
#: censura, sono pagine che il portale non può usare e che non dicono nulla di utile.
SERVIZIO: dict[str, re.Pattern[str]] = {
    "nl": _rx(r"\b(?:live|liveticker|opstelling\w*|samenvatting\w*|uitslagen|"
              r"voorbeschouwing\w*|wedstrijdverslag\w*|kijk\w*|stream\w*|"
              r"voorspelling\w*|tips\s+en|odds|speelschema|programma|"
              r"teruglezen|verslag\b|persconferentie\s+live)\b"),
    "pt": _rx(r"\b(?:ao\s+vivo|em\s+direto|onze\s+onze|escalaç\w*|escalacoes\w*|"
              r"resultados|resumo\w*|antevis[ãa]o\w*|previs[ãa]o\w*|onde\s+assistir|"
              r"apostas|palpites|progn[óo]stic\w*|jogos\s+de\s+hoje|"
              r"not[íi]cias\s+ao\s+minuto)\b"),
}

#: Rassegne e pagine «live» che elencano più fatti separati da un bullet: non sono un
#: articolo su una squadra, sono una pagina di servizio in qualunque lingua.
RASSEGNA = _rx(r"\s[\u2022|]\s")

#: Lingue ammesse: solo quelle dichiarate in configurazione e coperte dal vocabolario.
LINGUE_AMMESSE = frozenset(SERVIZIO)


def _pulito(testo: str | None) -> str:
    return re.sub(r"\s+", " ", testo or "").strip()


def sintesi_estera(title: str | None, lingua: str | None) -> Sintesi | None:
    """Etichetta italiana per un titolo in lingua originale, o ``None``.

    ``None`` significa «non classificabile»: il vocabolario non riconosce il titolo, il
    titolo è una pagina di servizio o la lingua non è coperta. Chi chiama deve contare
    questo esito, non nasconderlo.
    """
    testo = _pulito(title)
    codice = str(lingua or "").lower()
    if not testo or codice not in LINGUE_AMMESSE:
        return None
    servizio = SERVIZIO.get(codice)
    if servizio and servizio.search(testo):
        return None
    if RASSEGNA.search(testo):
        return None
    for chiave, etichetta, nota, lingue in TEMI:
        pattern = lingue.get(codice)
        if pattern is None:
            continue
        trovato = pattern.search(testo)
        if trovato:
            return Sintesi(chiave, etichetta, nota, trovato.group())
    return None
