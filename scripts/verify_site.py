"""Verifica del sito generato: collegamenti, residui, italiano, coerenza numerica.

Nasce dall'audit del 2026-09-12 (``docs/10_verifica_sito_2026-09-12.md``): ogni controllo è
una regola misurata sui dati, con i falsi positivi già esclusi (i separatori di migliaia
«67.598» non sono decimali col punto; «Wind» è un cognome, non il meteo).

Uso:
    python scripts/verify_site.py                      # sito in site/, dati in data/processed
    python scripts/verify_site.py --site /tmp/s --data /tmp/d
Esce con codice 1 se trova almeno un problema (usabile come passo di CI).
"""

from __future__ import annotations

import argparse
import ast
import math
import re
import unicodedata
from collections import Counter
from html import unescape as html_unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# ---- residui che non devono mai arrivare a schermo -----------------------------------------
BAD_TOKENS = re.compile(r"(?<![\w.])(nan|NaN|None|NaT|inf|-inf|numpy\.|Timestamp\()(?![\w.])")
TH_SCOPE = re.compile(r"<th(?=[ >])[^>]*>")   # celle d'intestazione: [27] vuole scope su ognuna
# Intervalli fra decimali scritti col trattino ASCII («xG (0,75-0,94)», «0,19-0,20»): il sito usa
# il trattino tipografico «–» per gli intervalli (i punteggi «2-1» restano col trattino corto).
# Misurato il 2026-10-07: 375 occorrenze nelle 375 schede post-partita + 1 in info.html — e le
# due pagine che citavano lo stesso numero di RPS dei bookmaker lo scrivevano in due modi.
RANGE_ASCII = re.compile(r"\d+,\d+-\d+,\d+")
# «<» crudo davanti a una cifra («<1», «<5 gare»): i browser lo recuperano come testo, ma
# il taglio dei tag degli strumenti di verifica lo mangia insieme alla parentesi finta —
# e in un attributo non quotato romperebbe l'attributo. Il segno va scritto «&lt;».
# Misurato il 2026-10-11: 823 occorrenze su 262 pagine (815 nella matrice dei risultati
# esatti, 8 nel tooltip della forma), tutte corrette in `&lt;` (docs/78 §12).
RAW_LT_DIGIT = re.compile(r"<\d")
SCRIPT_BLOCK = re.compile(r"<script\b.*?</script>", re.DOTALL | re.IGNORECASE)

# ---- oracoli indipendenti -------------------------------------------------------------------
# Le funzioni del generatore **non** si importano per costruire il valore atteso: se il
# verificatore chiama la stessa funzione che ha prodotto la pagina, verifica che la pagina renda
# quel codice, non che il numero sia giusto (`docs/79`). Dove una riscrittura indipendente è
# possibile, vive qui: formule ricavate dalla definizione, non copiate. Al momento dell'innesto
# (2026-10-11) sono state confrontate col generatore su casi reali e casuali: RPS 4.000 terne,
# Wilson su tutte le coppie k,n ≤ 60, terne 40.000, somme stampate 20.000 — zero divergenze.


def rps_indip(probs: list, outcomes: list) -> float:
    """RPS medio: ``1/(r−1)·Σᵢ (Fᵢ − Oᵢ)²`` sulle cumulative, per i = 1…r−1."""
    if not len(probs):
        return 0.0
    tot = 0.0
    for p, o in zip(probs, outcomes):
        cum_p = cum_o = 0.0
        s = 0.0
        for i in range(len(p) - 1):
            cum_p += float(p[i])
            cum_o += 1.0 if int(o) == i else 0.0
            s += (cum_p - cum_o) ** 2
        tot += s / (len(p) - 1)
    return tot / len(probs)


def wilson_indip(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di Wilson: radici in p di ``(p̂−p)² = z²·p(1−p)/n`` (equazione di 2º grado)."""
    if n <= 0:
        return (0.0, 1.0)
    a = 1.0 + z * z / n
    b = -2.0 * (k / n) - z * z / n
    c = (k / n) ** 2
    disc = max(b * b - 4 * a * c, 0.0)
    r = math.sqrt(disc)
    return ((-b - r) / (2 * a), (-b + r) / (2 * a))


def terna_indip(p, nd: int = 0) -> list[float]:
    """Interi (o decimi) che sommano 100: pavimento + resto ai resti frazionari più alti."""
    scala = 10**nd
    grezzi = [float(x) * 100 * scala for x in p]
    base = [math.floor(x) for x in grezzi]
    manca = round(100 * scala) - sum(base)
    ordine = sorted(range(len(base)), key=lambda i: (-(grezzi[i] - base[i]), i))
    for i in ordine[:manca]:
        base[i] += 1
    return [v / scala for v in base]


def terna_valida(p, nd: int, mostrati) -> bool:
    """La terna pubblicata è un arrotondamento legittimo? (specifica, non identità fra funzioni)

    Chiude esattamente su 100, ogni valore è il pavimento o il tetto del valore esatto e il
    numero di tetti è quello che serve. Accetta i casi di parità in cui due implementazioni
    corrette scelgono un valore diverso: è la regola a essere verificata, non il tie-break.
    """
    scala = 10**nd
    grezzi = [float(x) * 100 * scala for x in p]
    if len(mostrati) != len(grezzi):
        return False
    if sum(round(float(v) * scala) for v in mostrati) != round(100 * scala):
        return False
    tetti = 0
    for g, m in zip(grezzi, mostrati):
        v = round(float(m) * scala)
        if v == math.floor(g):
            continue
        if v == math.ceil(g):
            tetti += 1
            continue
        return False
    return tetti == round(100 * scala) - sum(math.floor(g) for g in grezzi)


def somma_stampata_indip(a: float, b: float, nd: int = 2) -> float:
    """La somma come la fa il lettore: prima arrotonda le due cifre, poi le addiziona."""
    return round(round(float(a), nd) + round(float(b), nd), nd)


def pct_dichiarata(x: float) -> int:
    """Percentuale intera come la dichiara il sito: **mezzo in su** (docs/78 §15).

    Non è `round()`: ``round(0.625 * 100)`` fa 62, cioè il pari più vicino, e la cifra
    pubblicata non deve dipendere dalla parità dell'intero. Il verifier ricalcola con
    questa regola scritta qui a mano: se il generatore tornasse al banker's, i mezzi
    esatti — l'unico punto in cui le due convenzioni divergono — lo farebbero vedere.
    """
    return math.floor(float(x) * 100.0 + 0.5)

# Card «Panchina e posta in gioco»: l'oracolo di [19] legge le celle della tabella (non chiama
# ``bench_deep``, altrimenti verificherebbe il generatore con se stesso — docs/78 §1).
PANCHINA_CARD = re.compile(r'<div class="card" id="panchina">(.*?)(?=<div class="card"|<footer)',
                           re.DOTALL)
PANCHINA_ROW = re.compile(r'<th scope="row">(Allenatore|Posta in gioco|Età media titolari)</th>'
                          r'(.*?)(?=</tr>)', re.DOTALL)
PANCHINA_TD = re.compile(r'<td>(.*?)</td>', re.DOTALL)


def panchina_cella(html: str) -> str:
    """Testo della cella della card panchina: via i tag, poi le entità, spazi normalizzati.

    L'ordine conta: al contrario «&lt;1» diventa «<1» e la finta parentesi viene mangiata
    dal tag successivo, facendo sparire il valore: con l'ordine sbagliato le 81 celle-squadra
    che pubblicano un valore agli estremi (su 164 con la riga dei numeri, build #9) non
    tornavano più, perché nella cella il numero c'era ma illeggibile (`docs/78` §13).
    """
    return re.sub(r"\s+", " ", html_unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def ggmm_cella(ts: Any, tz: Any) -> str:
    """Data breve (gg/mm) nel fuso display: stesso formato della cella «Allenatore»."""
    import pandas as pd  # import locale: il modulo tiene pandas fuori dal costo d'avvio

    v = pd.Timestamp(ts)
    if v.tzinfo is None:
        v = v.tz_localize("UTC")
    v = v.tz_convert(tz)
    return f"{v.day:02d}/{v.month:02d}"


def posizione_virtuale(tab: Any, tid: int, opp_id: int, pts: int, gd: int,
                       delta_mio: int, delta_avv: int) -> int:
    """Posizione virtuale con questo risultato: punti a **entrambe** le squadre della partita.

    Ricalcolo indipendente della riga verde di «Panchina e posta in gioco» (docs/78 §1):
    nella sconfitta l'avversaria incassa i 3 punti e può scavalcare, nella vittoria li
    incassa la squadra. Le altre gare restano in sospeso e la differenza reti è quella
    attuale, come dichiara la nota della card.
    """
    mio = pts + delta_mio
    sopra = 0
    for rr in tab.itertuples(index=False):
        rid = int(rr.team_id)
        if rid == tid:
            continue
        pu = int(rr.points) + (delta_avv if rid == opp_id else 0)
        di = int(rr.goal_diff or 0)
        if pu > mio or (pu == mio and di > gd):
            sopra += 1
    return sopra + 1


def record_campo(fx: Any, team_id: int, in_casa: bool, kickoff: Any) -> tuple[int, int, int, int]:
    """Bilancio di una squadra **nel ruolo in cui gioca questa partita**.

    Ricalcolo indipendente del «Da sapere · Dentro le mura / Lontano da casa»
    (docs/25 §4): stesso numero, altra strada — qui vettorizzato su pandas, nel sito
    riga per riga. Serve a beccare l'errore che un ricalcolo con la stessa funzione
    non può vedere: se il filtro sulle gare finite o il verso casa/trasferta cambia da
    una parte sola, i due numeri divergono e il controllo salta.
    """
    fin = fx[(fx.status == "finished") & (fx.utc_kickoff < kickoff)]
    col = "home_id" if in_casa else "away_id"
    g = fin[(fin[col] == team_id) & fin.home_goals.notna() & fin.away_goals.notna()]
    if in_casa:
        vittorie = int((g.home_goals > g.away_goals).sum())
        sconfitte = int((g.home_goals < g.away_goals).sum())
    else:
        vittorie = int((g.away_goals > g.home_goals).sum())
        sconfitte = int((g.away_goals < g.home_goals).sum())
    n = len(g)
    return vittorie, n - vittorie - sconfitte, sconfitte, n


def porta_inviolata(fx: Any, team_id: int, kickoff: Any) -> tuple[int, int] | None:
    """Gare senza gol subiti (ricalcolo indipendente del «Da sapere · Porta inviolata»)."""
    fin = fx[(fx.status == "finished") & (fx.utc_kickoff < kickoff)]
    g = fin[(fin.home_id == team_id) | (fin.away_id == team_id)]
    if len(g) < 3:
        return None
    subiti = g.apply(lambda r: r.away_goals if r.home_id == team_id else r.home_goals, axis=1)
    chiuse = int((subiti == 0).sum())
    return (chiuse, len(g)) if chiuse >= 2 else None


def gol_tardi(ev: Any, fx: Any, team_id: int, kickoff: Any) -> tuple[int, int] | None:
    """Gol subiti dopo il 75' (ricalcolo indipendente del «Da sapere · Finale da brividi»)."""
    if ev.empty or "is_home" not in ev.columns:
        return None
    fin = fx[(fx.status == "finished") & (fx.utc_kickoff < kickoff)]
    giocate = {int(x) for x in fin.match_id}
    e = ev[ev.match_id.isin(giocate) & (ev.type == "Goal") & ev.minute.notna()]
    if e.empty:
        return None
    m = e.merge(fin[["match_id", "home_id", "away_id"]], on="match_id", how="inner")
    m = m[m.apply(lambda r: (r.away_id if bool(r.is_home) else r.home_id) == team_id, axis=1)]
    totale = len(m)
    if totale < 4:
        return None
    tardi = int((m.minute.astype(float) >= 75).sum())
    return (tardi, totale) if tardi >= 3 and tardi / totale >= 0.34 else None


def capocannoniere(ps: Any, fx: Any, team_id: int, kickoff: Any) -> tuple[str, int] | None:
    """Miglior marcatore di una squadra nel campionato (ricalcolo indipendente).

    Somma i gol delle sole gare **finite** prima del calcio d'inizio: sommare tutte le
    righe del Parquet includerebbe partite non ancora giocate (e quindi un futuro che
    la scheda non può conoscere). Restituisce (nome, gol) o None se nessuno ha segnato.
    """
    if ps.empty or "key" not in ps.columns:
        return None
    fin = fx[(fx.status == "finished") & (fx.utc_kickoff < kickoff)]
    giocate = {int(x) for x in fin.match_id}
    g = ps[(ps.team_id == team_id) & (ps.key == "goals") & ps.match_id.isin(giocate)]
    if g.empty:
        return None
    somme = g.groupby("player_id")["value"].sum().sort_values(ascending=False, kind="mergesort")
    if somme.empty or float(somme.iloc[0]) < 1:
        return None
    pid = int(somme.index[0])
    # stessa regola del sito: la grafia più frequente (docs/25 §4), non la prima riga
    nomi = g.loc[g.player_id == pid, "player_name"].mode()
    if nomi.empty:
        return None
    return str(nomi.iloc[0]), int(float(somme.iloc[0]))


def notizia_in_finestra(righe: Any, kickoff: Any, giorni: int = 12) -> bool:
    """True se **almeno una** riga raccolta per (url, squadra) cade nella finestra.

    Lo stesso URL può comparire più volte in ``news.parquet`` per la stessa squadra con
    ``published_at`` diversi: il feed di Google News ripubblica il link con data aggiornata
    (caso reale 2026-09-16, ``5868080.html``: due righe 07:00 e 01:21). Il build filtra su
    ``kickoff - giorni`` e stampa la riga dentro finestra; il verificatore non deve guardare
    solo ``iloc[0]`` (che può essere la riga vecchia) altrimenti segnala un falso positivo.
    Righe senza data sono ignorate, non considerate valide.
    """
    import pandas as pd

    pa = pd.to_datetime(pd.Series(list(righe["published_at"])), utc=True)
    lo = pd.Timestamp(kickoff) - pd.Timedelta(days=giorni)
    hi = pd.Timestamp(kickoff) + pd.Timedelta(days=1)
    return bool(((pa >= lo) & (pa <= hi)).any())

# decimale col punto: esclusi i separatori di migliaia (1-3 cifre . esattamente 3 cifre)
DECIMAL_POINT = re.compile(r"(?<![\w/,\-:])\d{1,3}\.\d{1,2}(?![\w.])|\d{1,3}\.\d{4,}")
ENGLISH = re.compile(
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|"
    r"June|July|August|September|October|November|December|injury|suspension|RegularPlay|FastBreak|"
    r"FromCorner|SetPiece|ThrowInSetPiece|OwnGoal|Mostly Clear|Partly Cloudy|Overcast|Showers|"
    r"Light Rain|Heavy Rain|Thunder|Doubtful|Day to day|Out for season|Club Friendlies|"
    r"haven't|matches in a row|clean sheet)\b")
# concordanza: «1 rossi», «1 gare», «1 vittorie»…
# Non intercettare il finale «,1 gialli» di un decimale (es. 3,1 gialli/gara):
# si cerca un vero contatore intero all'inizio della parola.
# Sostantivi aggiunti il 18/09/2026: la lista originale non conteneva «punti» né
# «titolari», cioè le uniche due forme davvero sbagliate allora in linea
# («+1 punti sul secondo», 56× su 43 pagine; «di cui 1 titolari abituali», 25× su 22).
# Misurato sull'estensione: 81 occorrenze intercettate, 0 falsi positivi. Il verso opposto
# («2 punto») NON è presidiato: l'unico candidato trovato era «Schalke 04 giocatore»,
# nome di squadra seguito da un'intestazione di tabella — un falso positivo certo.
# Secondo ramo (07/10/2026, docs/53 §6.2): «N i <plurale>» — «2 i titoli più vecchi
# guardati» in 17 schede (e «1 i titolo» in 3, al singolare). L'articolo vagante
# schermava il primo ramo («1» non era seguito direttamente dal nome). Misurato sul
# sito di oggi (4.205 pagine): il ramo intercetta le 17, 0 falsi positivi — «N i
# <parola>» non occorre in nessun altro testo. Il singolare «1 i titolo» sparisce col
# fix del template e resta verificato dalla misura a sito intero, non dalla regex.
AGREEMENT = re.compile(
    r"(?<![\d,])\b1 (rossi|gialli|rigori|gare|partite|vittorie|pareggi|tiri|giorni|precedenti|"
    r"punti|titolari|assenti|sconfitte|anni|mesi|settimane|squadre|incontri|titoli|fatti|"
    r"giocatori|campionati|cartellini|allenatori)\b"
    r"|(?<![\d,])\b\d+ i (rossi|gialli|rigori|gare|partite|vittorie|pareggi|tiri|giorni|precedenti|"
    r"punti|titolari|assenti|sconfitte|anni|mesi|settimane|squadre|incontri|titoli|fatti|"
    r"giocatori|campionati|cartellini|allenatori)\b")
LOCAL_HREF = re.compile(r'href="([^"#]+\.html)(#[^"]*)?"')
# Attributi che un lettore di schermo pronuncia: il testo lì dentro è a tutti gli effetti
# testo nostro, ma i controlli di lingua giravano solo sul testo visibile (audit 18/09/2026).
# Misurato su quella dimensione allora scoperta: 30 «1 punti» negli aria-label della forma e
# 124 «9.0 rigori totali» (float dove serve un intero) nei tooltip dell'arbitro. Vanno raccolti
# dentro il parser, non con una regex sul grezzo: così restano fuori i title dei link della
# card notizie, che sono titoli di stampa citati verbatim (stessa ragione del testo).
ATTR_LEGGIBILI = ("aria-label", "title", "alt", "placeholder")


class Text(HTMLParser):
    """Testo leggibile di una pagina (senza style/script/head/svg) + href locali.

    La card «Ultime dalle società» (``id="notizie"``) viene esclusa dal testo: titoli e
    brani sono della stampa, pubblicati **verbatim** per scelta documentata (docs/21 P1-5
    e footer della card stessa) — i controlli su decimali/inglese/concordanza valgono per
    il testo NOSTRO, non per le citazioni delle testate. I link della card li verifica [20].

    **Eccezione ``class="sapere"`` (audit 18/09/2026).** I blocchi «Da sapere · …» vivono
    dentro quella stessa card ma sono **frasi generate da noi**, non citazioni: escludendo
    l'intera card l'esclusione era troppo larga e il nostro testo usciva dai controlli di
    lingua. Risultato misurato: «4 punti su 9, 1.33 a gara» (decimale col punto, 52
    occorrenze su 29 schede) passava indisturbato perché nessun controllo lo leggeva.
    Gli elementi marcati ``sapere`` sono quindi riammessi anche dentro la card.

    **Eccezione ``class="imbuto"`` (07/10/2026, docs/53 §6.2).** Stessa storia un mese
    dopo: i tre paragrafi generati dell'imbuto per squadra (conteggi «esaminati /
    pubblicati / scartati / troppo vecchi») vivono nella card ma non citano nessuno —
    e pubblicavano «2 i titoli più vecchi guardati» in 17 schede senza che il gate li
    leggesse. I titoli veri della stampa (``ul.news-list`` e le righe «in riserva»)
    restano esclusi: sono citazioni verbatim.

    **Eccezione ``class="voce"`` (11/10/2026, `docs/82` §9).** L'elenco delle voci della card
    «Clima del club» cita i titoli della stampa verbatim: fuori dai controlli anti-falso, come
    le notizie della card «Vita del club». Misurato l'11/10/2026: «TORNELLI APERTI DALLE
    18.15» faceva fallire il gate dei decimali su 5749709. Solo le ancore ``a.voce`` sono
    escluse — sommario, etichette dei gruppi, testata, data e marcatore restano testo nostro.
    """

    #: Classi riammesse nei controlli anche dentro la card delle notizie: solo testo nostro.
    CLASSI_NOSTRE = ("sapere", "imbuto")
    #: Ancore dei titoli citati verbatim (`a.voce`): fuori dai controlli anti-falso.
    CLASSI_CITATE = ("voce",)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.skip = 0
        self.news_tag: str | None = None
        self.news_depth = 0
        self.nostro_tag: str | None = None
        self.nostro_depth = 0
        self.citato_tag: str | None = None
        self.citato_depth = 0
        self.readable_attrs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Any]]) -> None:
        if tag in ("style", "script", "head", "svg"):
            self.skip += 1
        if self.news_depth == 0 and any(k == "id" and v == "notizie" for k, v in attrs):
            self.news_tag, self.news_depth = tag, 1
        elif self.news_tag == tag:
            self.news_depth += 1
        # Testo nostro dentro la card delle notizie → va ricontrollato (vedi docstring)
        if self.nostro_depth == 0 and any(
                k == "class" and v and any(c in str(v).split() for c in self.CLASSI_NOSTRE)
                for k, v in attrs):
            self.nostro_tag, self.nostro_depth = tag, 1
        elif self.nostro_tag == tag:
            self.nostro_depth += 1
        # titoli citati verbatim (`a.voce`): esclusi dai controlli, come le notizie della card
        if self.citato_depth == 0 and any(
                k == "class" and v and any(c in str(v).split() for c in self.CLASSI_CITATE)
                for k, v in attrs):
            self.citato_tag, self.citato_depth = tag, 1
        elif self.citato_tag == tag:
            self.citato_depth += 1
        if tag in ("p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "table", "section", "br"):
            self.parts.append(" ")      # separa i blocchi: «…link</a>1 gare» non deve sembrare «x1 gare»
        for k, v in attrs:
            if k == "id" and v:
                self.ids.add(v)
            if tag == "a" and k == "href" and v:
                self.hrefs.append(v)
            if k in ATTR_LEGGIBILI and v and self.citato_depth == 0 \
                    and (self.news_depth == 0 or self.nostro_depth > 0):
                self.readable_attrs.append(str(v))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "head", "svg") and self.skip:
            self.skip -= 1
        if self.news_tag == tag:
            self.news_depth -= 1
            if self.news_depth <= 0:
                self.news_tag, self.news_depth = None, 0
        if self.nostro_tag == tag:
            self.nostro_depth -= 1
            if self.nostro_depth <= 0:
                self.nostro_tag, self.nostro_depth = None, 0
        if self.citato_tag == tag:
            self.citato_depth -= 1
            if self.citato_depth <= 0:
                self.citato_tag, self.citato_depth = None, 0

    def handle_data(self, data: str) -> None:
        if not self.skip and self.citato_depth == 0 \
                and (self.news_depth == 0 or self.nostro_depth > 0):
            self.parts.append(data)


def check_pages(site: Path) -> tuple[list[str], int]:
    """Controlli di contenuto e collegamenti su tutte le pagine HTML. Ritorna (problemi, pagine)."""
    fails: list[str] = []
    pages = sorted(site.rglob("*.html"))
    n_th = 0
    n_attr = 0
    for page in pages:
        rel = str(page.relative_to(site))
        raw = page.read_text(encoding="utf-8")
        parser = Text()
        parser.feed(raw)
        text = re.sub(r"\s+", " ", "".join(parser.parts))

        # 27) intestazioni di tabella: ogni <th> deve dichiarare scope (docs/21 P2-8;
        # prima dell'intervento 4.125 celle non lo avevano, i lettori di schermo non
        # sapevano dire se l'intestazione vale per la colonna o per la riga)
        for m in TH_SCOPE.finditer(raw):
            n_th += 1
            if "scope=" not in m.group(0):
                fails.append(f"{rel}: <th> senza scope: {m.group(0)[:56]}")

        for m in BAD_TOKENS.finditer(text):
            fails.append(f"{rel}: residuo {m.group(0)!r}")
        for m in ENGLISH.finditer(text):
            fails.append(f"{rel}: inglese {m.group(0)!r}")
        for m in DECIMAL_POINT.finditer(text):
            fails.append(f"{rel}: decimale col punto {m.group(0)!r}")
        for m in AGREEMENT.finditer(text):
            fails.append(f"{rel}: concordanza {m.group(0)!r}")
        for m in RANGE_ASCII.finditer(text):
            fails.append(f"{rel}: intervallo col trattino ASCII {m.group(0)!r} (serve «–»)")
        for m in RAW_LT_DIGIT.finditer(SCRIPT_BLOCK.sub(" ", raw)):
            i = m.start()
            fails.append(f"{rel}: «<» crudo davanti a una cifra: "
                         f"{raw[max(0, i - 30):i + 20]!r} (serve &lt;)")

        # stessa terna di controlli sugli attributi pronunciati dai lettori di schermo
        for attr in parser.readable_attrs:
            n_attr += 1
            for m in DECIMAL_POINT.finditer(attr):
                fails.append(f"{rel}: decimale col punto in attributo {m.group(0)!r}")
            for m in ENGLISH.finditer(attr):
                fails.append(f"{rel}: inglese in attributo {m.group(0)!r}")
            for m in AGREEMENT.finditer(attr):
                fails.append(f"{rel}: concordanza in attributo {m.group(0)!r}")

        for href in parser.hrefs:
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target, sep, fragment = href.partition("#")
            target_page = site / target.lstrip("/") if target.startswith("/") else page.parent / target
            if target and not target_page.exists():
                fails.append(f"{rel}: collegamento interno mancante {href}")
                continue
            if sep and fragment:
                if not target:
                    target_ids = parser.ids
                else:
                    target_parser = Text()
                    target_parser.feed(target_page.read_text(encoding="utf-8"))
                    target_ids = target_parser.ids
                if fragment not in target_ids:
                    fails.append(f"{rel}: ancora interna mancante {href}")
    print(f"[27] celle <th> con scope verificate: {n_th}")
    print(f"[27b] attributi leggibili (aria-label/title/alt) verificati: {n_attr}")
    return fails, len(pages)


# ---- stato fonti: righe dichiarate e motivi (docs/21 §15) -------------------------------------
# Il 2026-09-15 due fonti rispondevano «OK» con zero righe salvate (news e transfers) e dalla
# pagina non si capiva perché: la colonna «Righe» più l'imbuto rendono quel caso leggibile, e
# questa invariante impedisce che torni muto.
STATUS_ROW = re.compile(
    r'<tr><td>([^<]+)</td><td class="mut">([^<]*)</td><td class="r">([^<]*)</td>'
    r'<td class="r">([^<]*)</td><td>(.*?)</td></tr>', re.DOTALL)


def check_status(site: Path) -> tuple[list[str], int]:
    """[28] Stato fonti: una fonte «OK» con 0 righe deve dichiarare il motivo.

    Nella stessa passata si verifica la **sospensione** (docs/19 P1.9): una riga «SOSPESO»
    deve dire quanti run sono falliti di fila e fra quanti run si ritenta, e non può avere
    richieste — se una fonte sospesa interrogasse comunque la rete, il backoff non esisterebbe.
    """
    page = site / "stato.html"
    if not page.exists():
        return [], 0
    fails: list[str] = []
    checks = 0
    for match in STATUS_ROW.finditer(page.read_text(encoding="utf-8")):
        fonte, _run, richieste, righe, esito = match.groups()
        checks += 1
        cell = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", esito)).strip()
        if "SOSPESO" in cell:
            if "run falliti consecutivi" not in cell or "nuovo tentativo fra" not in cell:
                fails.append(f"stato.html: {fonte} sospesa senza motivo o senza piano di ritentativo")
            elif richieste.strip() not in ("0", "—"):
                fails.append(f"stato.html: {fonte} sospesa ma con {richieste} richieste nel run")
            continue
        if righe.strip() != "0":
            continue
        if "OK" not in cell:
            continue                      # errore/avviso: il motivo è già il testo dell'errore
        if "0 righe ·" not in cell or len(cell.split("0 righe ·", 1)[1].strip()) < 3:
            fails.append(f"stato.html: {fonte} con 0 righe e nessuna spiegazione")
    print(f"[28] fonti con righe dichiarate: {checks} righe")
    return fails, checks


# ---- calendario completo (vista «Prossime») ---------------------------------------------------
# Una riga per partita, compatta: le regole da rispettare sono le stesse delle schede, ma il
# lettore qui non ha contesto, quindi un arrotondamento sbagliato non sarebbe riconoscibile.
CAL_ROW = re.compile(
    r'<div class="cal-row([^"]*)" data-match-card data-league="([^"]+)" data-status="([^"]+)"[^>]*>(.*?)</div>',
    re.DOTALL)
CAL_PCT = re.compile(r'<span class="cal-p"[^>]*aria-label="1 (\d+)%, X (\d+)%, 2 (\d+)%"[^>]*>(.*?)</span>\s*<span class="cal-gol"', re.DOTALL)
CAL_MONTH = re.compile(
    r'<details class="cal-month" id="mese-(\d{4})-(\d{2})"[^>]*>\s*<summary>([^<]+)'
    r'<span class="cal-count">([\d.]+) ([^<]+)</span>'
    r'(?:<span class="cal-note">[^<]*</span>)?</summary>(.*?)</details>', re.DOTALL)
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"]


#: tetto al peso di una singola pagina HTML. `docs/19` §3.10 lo cita come presidio già
#: esistente («il blocco [11e] con MAX_PAGE_KB = 900 intercetta la regressione»), ma il
#: controllo non c'era: verificato su `main` e sul branch, `MAX_PAGE_KB` non compariva in
#: nessun punto di questo script. Il valore 900 KB è quello dichiarato dall'audit e resta
#: ampio rispetto alla pagina più pesante misurata (`prossime.html`, ~1,45 MB → vedi sotto).
MAX_PAGE_KB = 900
#: `prossime.html` contiene di proposito l'intero calendario di stagione (1.988 partite in
#: righe compatte, paginate per mese con <details> e fuori dal layout quando chiuse). È
#: sopra il tetto e lo resta finché non si decide la paginazione per URL (P2.7, oggi **non**
#: giustificata: la finestra dettagliata è di 66 card contro le ~250 della soglia). Si
#: dichiara l'eccezione con il suo tetto, invece di alzare il limite per tutti.
PAGINE_FUORI_TETTO = {"prossime.html": 1800}


def check_page_weight(site: Path) -> tuple[list[str], int]:
    """[11e] Peso delle pagine: nessuna pagina cresce oltre il tetto senza che si sappia.

    Perché serve (`docs/19` §3.10): una pagina che gonfia è la regressione di prestazioni
    più facile da introdurre e la più difficile da vedere in una code review — il diff
    mostra dieci righe di template, non i megabyte che ne escono. Il controllo è sul
    prodotto finito, cioè sull'unica cosa che l'utente scarica davvero.
    """
    fails: list[str] = []
    checks = 0
    for page in sorted(site.rglob("*.html")):
        rel = str(page.relative_to(site))
        kb = page.stat().st_size / 1024
        tetto = PAGINE_FUORI_TETTO.get(rel, MAX_PAGE_KB)
        checks += 1
        if kb > tetto:
            # il riepilogo raggruppa per la prima parola dopo «: », quindi la frase inizia
            # con una parola-categoria («pagina») e non con la cifra, altrimenti il
            # sommario diventa un elenco di numeri diversi uno per pagina.
            fails.append(f"{rel}: pagina di {kb:.0f} KB oltre il tetto di {tetto} KB")
    return fails, checks


def check_calendar(site: Path) -> tuple[list[str], int]:
    """[11] Calendario completo: righe coerenti, 1X2 che somma 100, mesi dichiarati correttamente."""
    fails: list[str] = []
    checks = 0
    righe_totali = 0
    for page in sorted(site.rglob("*.html")):
        rel = str(page.relative_to(site))
        h = page.read_text(encoding="utf-8", errors="replace")
        righe = list(CAL_ROW.finditer(h))
        mesi = list(CAL_MONTH.finditer(h))
        if not righe and not mesi:
            continue
        if rel != "prossime.html":
            fails.append(f"{rel}: calendario completo fuori dalla vista «Prossime» ({len(righe)} righe)")
        righe_totali += len(righe)

        for m in righe:
            classi, _lega, stato, corpo = m.groups()
            checks += 1
            if "cal-fav-" not in classi and "senza previsione" not in corpo:
                fails.append(f"{rel}: riga di calendario senza esito preferito né «senza previsione»")
            if stato != "scheduled":
                fails.append(f"{rel}: riga di calendario con stato {stato!r} (atteso «scheduled»)")
            when = re.search(r'<time class="cal-when" datetime="(\d{4})-(\d{2})-(\d{2})">([^<]*)<b>(\d{2}:\d{2})</b>', corpo)
            if not when:
                fails.append(f"{rel}: riga di calendario senza data/ora leggibili")
            else:
                checks += 1
                anno, mese, giorno, testo, ora = when.groups()
                if not 1 <= int(mese) <= 12 or not 1 <= int(giorno) <= 31:
                    fails.append(f"{rel}: data di calendario impossibile {anno}-{mese}-{giorno}")
                if f" {int(giorno)} " not in f" {testo.strip()} ":
                    fails.append(f"{rel}: data {anno}-{mese}-{giorno} ma testo «{testo.strip()}»")
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", ora):
                    fails.append(f"{rel}: ora non valida {ora!r}")
            prob = CAL_PCT.search(corpo)
            if prob:
                checks += 1
                uno, x, due, visibile = (int(prob.group(1)), int(prob.group(2)),
                                         int(prob.group(3)), prob.group(4))
                if uno + x + due != 100:
                    fails.append(f"{rel}: 1X2 di calendario {uno}+{x}+{due} != 100")
                # cal-extra contiene gol e over per mobile: va tolto prima di contare l'1X2
                vis_senza_extra = re.sub(r'<span class="cal-extra".*?</span>', '', visibile, flags=re.DOTALL)
                numeri = [int(v) for v in re.findall(r"\d+", re.sub(r"</?b>", "", vis_senza_extra))]
                if numeri != [uno, x, due]:
                    fails.append(f"{rel}: 1X2 letto {numeri} != aria-label {[uno, x, due]}")
                grassetto = re.findall(r"<b>(\d+)</b>", visibile)
                if len(grassetto) != 1 or int(grassetto[0]) != max(uno, x, due):
                    fails.append(f"{rel}: preferito in grassetto {grassetto} su 1X2 {[uno, x, due]}")
                fav = re.search(r"cal-fav-([hda])", classi)
                atteso = ("h", "d", "a")[[uno, x, due].index(max(uno, x, due))]
                if not fav or fav.group(1) != atteso:
                    fails.append(f"{rel}: classe cal-fav-{fav.group(1) if fav else '?'} ma il preferito è {atteso}")
                gol = re.search(r'<span class="cal-gol"[^>]*>([^<]*)</span>', corpo)
                over = re.search(r'<span class="cal-o"[^>]*>([^<]*)</span>', corpo)
                if not gol or not re.fullmatch(r"\d+,\d", gol.group(1)):
                    fails.append(f"{rel}: gol attesi non in formato italiano {gol.group(1) if gol else None!r}")
                else:
                    checks += 1
                if not over or not re.fullmatch(r"\d{1,3}%", over.group(1)):
                    fails.append(f"{rel}: Over 2,5 non in percentuale {over.group(1) if over else None!r}")
                else:
                    checks += 1
            elif "senza previsione" not in corpo:
                fails.append(f"{rel}: riga di calendario senza probabilità e senza «senza previsione»")
            else:
                checks += 1

        # mesi: etichetta, ordine e conteggio dichiarato devono tornare con le righe stampate
        precedente: tuple[int, int] | None = None
        for m in mesi:
            checks += 1
            anno, mese, etichetta, conto, plurale, blocco = m.groups()
            anno, mese = int(anno), int(mese)
            if etichetta.strip() != f"{MESI_IT[mese - 1].capitalize()} {anno}":
                fails.append(f"{rel}: mese {anno}-{mese:02d} con etichetta «{etichetta.strip()}»")
            if precedente is not None and (anno, mese) <= precedente:
                fails.append(f"{rel}: mesi non in ordine ({precedente} → {(anno, mese)})")
            precedente = (anno, mese)
            n = len(CAL_ROW.findall(blocco))
            if int(conto.replace(".", "")) != n:
                fails.append(f"{rel}: {etichetta.strip()} dichiara {conto} partite ma ne stampa {n}")
            if plurale.strip() != ("partita" if n == 1 else "partite"):
                fails.append(f"{rel}: {etichetta.strip()} «{plurale.strip()}» con {n} righe")
        nav = set(re.findall(r'<a href="#mese-(\d{4}-\d{2})"', h))
        dettagli = {f"{m.group(1)}-{m.group(2)}" for m in mesi}
        if nav != dettagli:
            fails.append(f"{rel}: navigazione mesi {sorted(nav)} != sezioni {sorted(dettagli)}")
    print(f"[11] righe di calendario verificate: {righe_totali}")
    return fails, checks


#: barre 1X2 (scheda partita, passi della scomposizione, mini-barra delle liste).
#: L'header riusa ``class="bar"`` per il wordmark: i suoi segmenti non hanno ``style="width:…"``,
#: quindi non entrano nel controllo (nessuna esclusione esplicita da mantenere).
BAR_BLOCK = re.compile(r'<div class="bar"([^>]*)>(.*?)</div>', re.DOTALL)
BAR_SEG = re.compile(r'<span class="([hda])" style="width:(\d+(?:\.\d+)?)%"[^>]*>([^<]*)</span>')
PROB_LABELS = re.compile(r'<div class="prob-labels">(.*?)</div>', re.DOTALL)
LAB = re.compile(r'<span( class="is-fav")?>([1X2]) (\d+)%</span>')


def _num_it(s: str) -> float:
    """'61,0' → 61.0 (virgola decimale italiana)."""
    return float(s.replace(",", "."))


def _int_it(s: str) -> int:
    """'2.494' → 2494: conteggio pubblicato con il separatore italiano delle migliaia.

    Ogni conteggio del sito sopra 999 esce con il separatore (`it_num`), quindi le regex che
    rileggono i numeri pubblicati devono accettarlo: senza questo, l'invariante [7] andava in
    eccezione su «(2.494/5.836)» e il [3b] perdeva la riga «Tutti» (docs/41 §3.2).
    """
    return int(re.sub(r"<[^>]+>", "", s).replace(".", "").replace(",", "").strip())


def check_bars(site: Path) -> tuple[list[str], int]:
    """[11a] Barre 1X2: larghezze, etichette e aria-label devono essere gli stessi tre numeri.

    Invariante di pubblicazione, non di calcolo: anche se il modello cambiasse, una barra che
    non chiude 100 è un difetto visibile (segmento mancante o strabordante) e un'etichetta che
    contraddice la larghezza è un numero non vero. Prima della correzione (docs/19 §3.3) il
    22% delle schede hero pubblicava 99% o 101% perché ogni probabilità era arrotondata da sola.
    """
    fails: list[str] = []
    checks = 0
    barre = 0
    for page in sorted(site.rglob("*.html")):
        rel = str(page.relative_to(site))
        h = page.read_text(encoding="utf-8", errors="replace")
        for attrs, corpo in BAR_BLOCK.findall(h):
            seg = BAR_SEG.findall(corpo)
            if len(seg) != 3:
                continue                      # wordmark dell'header o barra non 1X2
            checks += 1
            barre += 1
            if [c for c, _, _ in seg] != ["h", "d", "a"]:
                fails.append(f"{rel}: barra 1X2 con segmenti {[c for c, _, _ in seg]} (atteso h, d, a)")
            largh = [_num_it(w) for _, w, _ in seg]
            if abs(sum(largh) - 100.0) > 0.05:
                fails.append(f"{rel}: barra 1X2 larga {sum(largh):g}% ({largh})")
            for (_, w, testo), val in zip(seg, largh):
                if not testo.strip():
                    continue                  # mini-barra: le etichette stanno in .prob-labels
                m = re.search(r"(\d+(?:,\d+)?)\s*%", testo)
                if not m:
                    fails.append(f"{rel}: segmento della barra senza percentuale leggibile ({testo!r})")
                elif _num_it(m.group(1)) != val:
                    fails.append(f"{rel}: etichetta {m.group(1)}% ma larghezza {val:g}%")
                else:
                    checks += 1
            aria = re.search(r'aria-label="([^"]*)"', attrs)
            if aria:
                detti = [_num_it(v) for v in re.findall(r"(\d+(?:,\d+)?)\s?(?:per cento|%)", aria.group(1))]
                if len(detti) == 3:
                    checks += 1
                    if detti != largh:
                        fails.append(f"{rel}: aria-label {detti} != larghezze {largh}")
                else:
                    fails.append(f"{rel}: aria-label della barra con {len(detti)} percentuali (attese 3)")
            else:
                fails.append(f"{rel}: barra 1X2 senza aria-label (ruolo img)")
        for blocco in PROB_LABELS.findall(h):
            etichette = LAB.findall(blocco)
            if len(etichette) != 3:
                fails.append(f"{rel}: .prob-labels con {len(etichette)} esiti (attesi 3)")
                continue
            checks += 1
            valori = [int(v) for _, _, v in etichette]
            if sum(valori) != 100:
                fails.append(f"{rel}: etichette 1X2 {valori} non sommano 100")
            favoriti = [sim for sim, _, v in etichette if sim and int(v) == max(valori)]
            if [sim for sim, _, _ in etichette].count(" class=\"is-fav\"") != 1:
                fails.append(f"{rel}: .prob-labels con {blocco.count('is-fav')} favoriti evidenziati (atteso 1)")
            elif not favoriti:
                fails.append(f"{rel}: favorito evidenziato ma non è il massimo {valori}")
    print(f"[11a] barre 1X2 verificate: {barre}")
    return fails, checks


# ---- numeri derivati stampati: devono chiudere con i numeri stampati accanto -----------------
#: doppia chance pubblicata nella card «Previsione» (tre valori interi).
DC_ROW = re.compile(r"Doppia chance 1X / 12 / X2</th><td[^>]*>(\d+)% / (\d+)% / (\d+)%</td>")
#: le tre forme in cui il sito pubblica «λ + λ (totale)»: hero della scheda, card delle
#: liste (riga visibile) e tooltip della stessa riga, description SEO, riga del calendario.
# ---- registro degli oracoli ------------------------------------------------------------------
# Da dove viene il valore atteso di ogni controllo (`docs/79`). «I» = oracolo indipendente: il
# valore si ricalcola da dati primari o è un'identità sui numeri stampati. «M» = misto: una parte
# è indipendente, una parte si appoggia al generatore. «S» = specchio: il valore atteso si
# costruisce con il codice del generatore, quindi il controllo verifica la resa, non il calcolo —
# l'oracolo dei modelli sono i loro test (tests/test_models.py, test_season_sim.py, test_advanced.py).
# Il confronto col generatore doveva esistere: il 2026-10-11 la tenuta della terna dell'andamento
# è passata sotto [2] per una tolleranza «>3» e la sua regola d'arrotondamento non la vedeva
# nessuno. Il test `test_ogni_controllo_dichiara_il_suo_oracolo` obbliga ogni nuovo controllo a
# dichiararsi qui, così il debito non cresce in silenzio.
ORACOLI: dict[str, tuple[str, str]] = {
    "1": ("S", "matrice dei punteggi dalle funzioni del modello (identità: celle+coda = 100%)"),
    "1b": ("I", "ripartizione DC/Elo pubblicata: somma 100 e valori legittimi di w_dc"),
    "2": ("I", "andamento: somma esatta delle tre celle e ultima riga = risultato"),
    "3": ("M", "RPS ricalcolato dal verificatore; il campione è selezionato dai Parquet"),
    "3b": ("I", "Δ = RPS − naive sui numeri stampati e somma delle leghe = riga «Tutti»"),
    "4": ("I", "vincoli della simulazione: somme per lega = 1 e alias deprecati"),
    "5": ("I", "ruoli, indisponibili e precedenti ↔ distinta e archivio"),
    "6": ("I", "assist e xG 1T/2T ↔ events e team_stats"),
    "7": ("M", "intervallo di Wilson ricalcolato; il segnale viene dal Parquet"),
    "8": ("M", "RPS ricalcolato; campione del backtest dai Parquet"),
    "8b": ("M", "calibrazione salvata e somme del backtest dai Parquet"),
    "9": ("S", "distribuzione dei gol dalle funzioni del generatore (`goals_view`)"),
    "10": ("S", "scomposizione della probabilità dal generatore (`probability_steps`)"),
    "11": ("I", "calendario e margine sul secondo: identità sui numeri stampati"),
    "11a": ("I", "barre 1X2: etichette = larghezze, somma 100, un solo favorito"),
    "12": ("M", "copertura ↔ somma delle percentuali in pagina; il resto dai Parquet"),
    "13-14": ("I", "template e formattazione anti-falso (conteggi scritti a mano)"),
    "15": ("M", "fasce dal backtest; intervallo di Wilson ricalcolato"),
    "16": ("M", "posizione di lega dai Parquet; somma stampata ricalcolata"),
    "17": ("M", "conteggi da events; le probabilità con la formula del verificatore"),
    "18": ("I", "etichette d'impatto dell'infermeria e tooltip richiesti"),
    "19": ("M", ("classifica e posizione virtuale ricalcolate; posta in gioco dal Parquet "
                 "con la formattazione del generatore, confrontata con Proiezioni")),
    "20": ("S", "card notizie: la selezione è `team_news` del generatore"),
    "21": ("I", ("stato della squadra (ex «Clima del club»): strisce di campionato, xPTS "
                 "(Understat o Poisson FotMob), riposo/congestione con le coppe, panchina, "
                 "infermeria dai Parquet")),
    "22": ("I", "radar e scontri ricalcolati da team_stats e Understat"),
    "23": ("I", "badge «giocherà?» ↔ distinta"),
    "24": ("I", "«Il prossimo impegno» ↔ calendario"),
    "25": ("I", "conversione delle grandi occasioni ↔ occasioni"),
    "26": ("M", "card mercato ↔ tabella transfers; le soglie sono del generatore"),
    "27": ("I", "residui, inglese, scope, trattini, «<» crudo, link interni"),
    "27b": ("I", "attributi leggibili (aria-label, title, alt)"),
    "28": ("I", "coerenza di stato.html: ogni fonte sospesa dichiara motivo e piano"),
    "29": ("I", "CSS esterno in ogni pagina, zero <style> inline"),
    "30": ("I", "doppie chance = somma delle 1X2 stampate; totali = somma delle cifre"),
    "31": ("I", "somme stampate che devono chiudere"),
    "32": ("I", "stime per-90 e ◇/◎ ↔ minuti del campione"),
    "33": ("I", "indice della scheda ↔ sezioni presenti"),
    "34": ("I", "pallini e punti della forma ↔ calendario"),
    "35": ("I", "fonti dichiarate in info.html ↔ moduli implementati"),
    "36": ("I", "tabelle dentro .tablewrap"),
    "37": ("I", "didascalie del punteggio coerenti col punteggio"),
    "38": ("I", "importi non azzerati dall'arrotondamento"),
    "39": ("M", "movimenti di mercato ↔ tabella transfers"),
    "40": ("I", "meteo: valori pubblicati ↔ soglie del codice"),
    "41": ("M", ("struttura e soglie della card dei Fattori; il testo delle soglie è del "
                 "generatore (fattori_soglie_testo)")),
    "42": ("M", "fatti ricalcolati dai Parquet; il gruppo «nostro» usa `form_facts`"),
    "43": ("M", "finestra e righe ricalcolate; la tendenza è `arrival_trend`"),
    "44": ("M", "forma e calendario ricalcolati; i rapporti di forza usano il modello Elo"),
    "45": ("M", "cronologia del verificatore (`elo_reference_at_dates`); valori Elo del modello"),
    "46": ("M", "λ e confronti ricalcolati; la griglia Dixon-Coles è quella del modello"),
    "47": ("I", "terne 1/X/2 pubblicate: somma esatta, quattro grafie"),
    "48": ("M", ("percentuali intere di Accuratezza: regola dichiarata, hit e "
                 "eventi osservati ricalcolati dai gol")),
    "49": ("M", ("clima del club (`docs/82` §5-§9): conteggi **e voci elencate** della "
                 "settimana, marcatori «anche in «Vita del club»» e rango per valore ricalcolati "
                 "dai Parquet; la classificazione dei temi è `classify_news` della fonte")),
}


HERO_LAM = re.compile(r"<b>(\d+,\d+) \+ (\d+,\d+)</b><span>gol attesi · <b>(\d+,\d+) totali</b></span>")
CARD_LAM = re.compile(r"Gol attesi <b>(\d+,\d+) \+ (\d+,\d+)</b> <span class=\"mut\">\((\d+,\d+) totali\)</span>")
TIP_LAM = re.compile(r"(\d+,\d+) casa \+ (\d+,\d+) trasferta = (\d+,\d+) totali")
META_LAM = re.compile(r"gol attesi (\d+,\d+) \+ (\d+,\d+) \((\d+,\d+) totali\)")
POS_LAM = re.compile(r"I (\d+,\d+) gol attesi totali in testa alla scheda")
MATCH_LINK = re.compile(r"partite/(\d+)\.html")


def _stamp_it(v: float, nd: int = 2) -> str:
    """2.39 → '2,39': la stessa forma che il sito deve pubblicare (virgola, nd cifre)."""
    return f"{v:.{nd}f}".replace(".", ",")


def check_derived(site: Path) -> tuple[list[str], int]:
    """[30] e [31] i numeri derivati pubblicati devono chiudere con i numeri pubblicati accanto.

    [30] **doppia chance**: 1X/12/X2 sono per costruzione la somma di due dei tre esiti 1X2, quindi
    i tre valori pubblicati devono essere la somma dei tre numeri interi stampati nella barra della
    stessa card. Prima del 2026-09-16 ogni valore era arrotondato da solo: 48 schede su 165 (29,1%)
    pubblicavano una doppia chance che contraddiceva l'1X2 (docs/22 §1) — la derivazione nei modelli
    era già corretta (docs/19 §1.9), era la formattazione a non esserlo.

    [31] **somme stampate**: «1,40 + 0,99 (2,39 totali)» deve avere il totale uguale alla somma dei
    due numeri **stampati**. 88 occorrenze su 330 (26,7%) pubblicavano il totale calcolato sui valori
    grezzi (2,3829 → «2,38»). Lo stesso totale compare in più pagine della stessa partita: qui si
    verifica anche che sia lo stesso numero ovunque (docs/22 §2).
    """
    fails: list[str] = []
    checks = 0
    n_dc = 0
    n_somme = 0
    hero_per_match: dict[int, tuple[str, str]] = {}
    card_per_match: dict[int, list[tuple[str, str]]] = {}
    for page in sorted(site.rglob("*.html")):
        rel = str(page.relative_to(site))
        h = page.read_text(encoding="utf-8", errors="replace")

        # --- [30] doppia chance vs barra 1X2 pubblicata nella stessa card
        blocco = h.split('id="previsione"', 1)
        if len(blocco) > 1:
            blocco = blocco[1].split('id="scomposizione"', 1)[0]
            segs = None
            for attrs, corpo in BAR_BLOCK.findall(blocco):
                s = BAR_SEG.findall(corpo)
                if len(s) == 3 and all(t.strip() and "," not in t for _, _, t in s):
                    segs = [int(_num_it(m.group(1))) for _, _, t in s
                            if (m := re.search(r"(\d+(?:,\d+)?)\s*%", t))]
                    break
            m_dc = DC_ROW.search(blocco) or DC_ROW.search(h)
            if segs is not None and len(segs) == 3:
                n_dc += 1
                checks += 1
                if m_dc is None:
                    fails.append(f"{rel}: card «Previsione» con barra 1X2 ma doppia chance assente")
                else:
                    dc = [int(v) for v in m_dc.groups()]
                    atteso = [segs[0] + segs[1], segs[0] + segs[2], segs[1] + segs[2]]
                    if dc != atteso:
                        fails.append(f"{rel}: doppia chance {dc} ≠ somma delle 1X2 stampate "
                                     f"{segs} (attesa {atteso})")
                    if sum(dc) != 200:
                        fails.append(f"{rel}: doppia chance {dc} somma {sum(dc)} (attesa 200)")

        # --- [31] somme stampate
        for etichetta, rx in (("hero", HERO_LAM), ("card", CARD_LAM),
                              ("tooltip", TIP_LAM), ("description", META_LAM)):
            for m in rx.finditer(h):
                a, b, tot = m.group(1), m.group(2), m.group(3)
                n_somme += 1
                checks += 1
                atteso = _stamp_it(_num_it(a) + _num_it(b))
                if tot != atteso:
                    fails.append(f"{rel}: {etichetta}: totale {tot} ≠ {a} + {b} = {atteso}")
        m_hero = HERO_LAM.search(h)
        if m_hero and page.parent.name == "partite":
            hero_per_match[int(page.stem)] = (m_hero.group(3), rel)
        for m in CARD_LAM.finditer(h):
            links = MATCH_LINK.findall(h[:m.start()])
            if links:
                card_per_match.setdefault(int(links[-1]), []).append((m.group(3), rel))
        m_pos = POS_LAM.search(h)
        if m_pos and m_hero:
            checks += 1
            if m_pos.group(1) != m_hero.group(3):
                fails.append(f"{rel}: «{m_pos.group(1)} gol attesi totali» in «Dove si colloca» "
                             f"≠ {m_hero.group(3)} in testa alla scheda")
    # stesso numero su pagine diverse per la stessa partita
    for mid, (tot_hero, rel_hero) in hero_per_match.items():
        for tot_card, rel_card in card_per_match.get(mid, []):
            checks += 1
            if tot_card != tot_hero:
                fails.append(f"partita {mid}: gol attesi totali {tot_hero} in {rel_hero} "
                             f"ma {tot_card} in {rel_card}")
    print(f"[30] doppie chance coerenti con l'1X2 stampato: {n_dc}")
    print(f"[31] somme stampate verificate: {n_somme}")
    return fails, checks


#: La scala della barra «Dove si colloca» arriva al template **già arrotondata a due cifre**
#: (`viz.lo = round(lo_q, 2)`) e viene stampata con **una** cifra (`dec(1)`): la distanza dal
#: percentile grezzo può quindi arrivare a 0,05 (mezza unità dell'ultima cifra stampata) più
#: 0,005 (l'arrotondamento a due cifre), cioè ~0,055. Confrontarla con 0,05 faceva fallire
#: **22 pagine** il 2026-09-19 («scala 2,0–3,4 vs percentile 2.05–3.38») e ha bloccato il run
#: giornaliero e il deploy (issue #65): non era un numero sbagliato, era un doppio
#: arrotondamento. Il confronto si fa sul valore che il template riceve, con mezza cifra di
#: tolleranza: uno scarto vero (es. scala 2,5 su percentile 2,05) resta un problema.
TOLLERANZA_SCALA = 0.05 + 1e-9


def _scala_ok(pubblicato: float, percentile: float) -> bool:
    """La scala stampata (1 decimale) corrisponde al percentile che il template riceve?"""
    return abs(float(pubblicato) - round(float(percentile), 2)) <= TOLLERANZA_SCALA


def _pos_pct(v: float, lo_q: float, hi_q: float) -> float:
    """Posizione 0–100 di un valore sulla scala della barra (stessa formula del generatore)."""
    return round(min(100.0, max(0.0, 100.0 * (v - lo_q) / (hi_q - lo_q))), 2)


def elo_reference_at_dates(history: Any, fixtures: Any, cutoffs: Any,
                           min_teams: int = 10) -> tuple[dict, dict]:
    """Oracolo [44]: solo risultati già passati, senza usare i lettori Elo del sito.

    Un flusso cronologico di risultati alimenta penaltyblog; a ogni data richiesta si
    fotografa lo stato **prima** di applicare i risultati di quell'istante. Non usa la
    serie «prima della gara successiva» né la sua ricerca binaria, così una regressione
    temporale in ``team_elo`` non può autocertificarsi (docs/68).
    """
    import math

    import pandas as pd
    import penaltyblog as pb

    from fda.models.predict import EloModel
    from fda.teams import canonical

    required = {"home", "away", "date", "home_goals", "away_goals"}
    if history.empty or not required <= set(history.columns):
        return {}, {}
    hist = history.assign(date=pd.to_datetime(history.date, utc=True, errors="coerce"))
    hist = hist.dropna(subset=sorted(required)).copy()
    hist["home"], hist["away"] = hist.home.map(canonical), hist.away.map(canonical)
    # I vecchi CSV danno solo il giorno: il risultato non è noto durante quel giorno.
    hist["available_at"] = hist.date.where(
        hist.date != hist.date.dt.normalize(),
        hist.date + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1))
    games = list(hist.sort_values("available_at", kind="stable").itertuples(index=False))
    first = {}
    for game in games:
        for name in (game.home, game.away):
            first[name] = min(first.get(name, game.date), game.date)
    cohorts = {lg: {canonical(t) for t in [*g.home_name, *g.away_name] if pd.notna(t)}
               for lg, g in fixtures.groupby("league_id")}
    elo = pb.ratings.Elo(k=EloModel.k,
                         home_field_advantage=EloModel.home_field_advantage)
    cursor = 0
    ratings_at, leagues_at = {}, {}
    for cut in sorted(set(pd.to_datetime(cutoffs, utc=True).dropna())):
        while cursor < len(games) and games[cursor].available_at < cut:
            game = games[cursor]
            result = 0 if game.home_goals > game.away_goals else (
                1 if game.home_goals == game.away_goals else 2)
            elo.update_ratings(game.home, game.away, result)
            cursor += 1
        # Copia, non riferimento al dizionario mutabile della libreria; prima del debutto
        # non si inventa un rating. Al debutto esatto vale il prior della libreria (1500).
        ratings = {t: float(elo.get_team_rating(t)) for t, start in first.items() if start <= cut}
        ratings_at[cut] = ratings
        for lg, names in cohorts.items():
            population = {t: ratings[t] for t in names if t in ratings}
            if len(population) < min_teams:
                continue
            values = list(population.values())
            avg = math.fsum(values) / len(values)
            sd = math.sqrt(math.fsum((v - avg) ** 2 for v in values) / len(values))
            ranks = {t: 1 + sum(v > value for v in values) for t, value in population.items()}
            leagues_at[(lg, cut)] = {"avg": avg, "sd": sd, "ranks": ranks, "ratings": population}
    return ratings_at, leagues_at


def check_due_squadre(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[44] card «Le due squadre»: presente su **ogni** scheda e con i numeri ricalcolati.

    Nasce con la revisione del 2026-10-09 (`docs/64`). Controlla, per tutte le pagine di
    ``site/partite`` e per entrambe le squadre di ognuna:

    * **struttura** — il titolo del gruppo, due riquadri di squadra, i quattro riquadri di
      stagione (xG creati, xG concessi, xPTS, pressing/riposo) e il piè di card nuovo;
    * **fonte** — quella stampata è quella che ``season_xg`` userebbe davvero, e le due
      squadre della stessa scheda non mescolano Understat e FotMob senza dirlo;
    * **numeri** — xG creati/concessi per gara, campione, xPTS, punti e scarto sono quelli
      ricalcolati dai Parquet;
    * **riferimento di lega** — il rapporto «× la media del campionato» è ricalcolato con la
      media della **stessa fonte**, e c'è ovunque la fonte lo permetta (parità fra le 7 leghe);
    * **verdetto xPTS** — coincide con ``MatchAnalysis.xpts_reading`` (banda di rumore
      misurata), e nessuna pagina riporta le vecchie soglie fisse;
    * **pressing** — l'indice di pressione FotMob è ricalcolato dai Parquet per entrambe le
      squadre e c'è in **tutte e 7 le leghe** (`docs/64` §9: prima la casella pubblicava il
      PPDA di Understat e 288 riquadri su 892, tutti di Eredivisie e Liga Portugal, dicevano
      «n.d.»), col rapporto di lega, l'etichetta solo oltre l'errore standard e il PPDA
      Understat conservato nel ⓘ dove la lega è coperta;
    * **finestra** — i numeri si fermano **alla vigilia** della partita descritta: il campione
      stampato coincide con le gare giocate *prima* del calcio d'inizio, ricontate dal
      calendario e da Understat **senza passare da ``season_xg``** (`docs/64` §7), con la
      gara descritta esclusa dal suo stesso campione anche quando Understat la data qualche
      minuto prima del calcio d'inizio FotMob (`docs/76` §1);
    * **attacco contro difesa** — la striscia col confronto incrociato (`docs/76` §2) c'è
      solo sulle schede pre-partita in cui entrambe le squadre hanno i due rapporti di lega
      dalla stessa fonte, e i suoi quattro numeri sono quelli delle caselle ricalcolate;
    * **infermeria** — il totale «xG+xA a partita in meno» è la **somma esatta** della colonna
      «impatto» stampata sotto (`docs/64` §8: prima sommava le stime mentre le righe
      mostravano il grezzo, e non tornava in 101 pannelli su 118), e ogni riga dichiara il
      ruolo (o «ruolo n.d.»);
    * **forza nella forma** — nomi, risultati, sede e ordine delle gare dal calendario;
      ranghi ed Elo storici da un oracolo cronologico indipendente da ``team_elo`` e
      ``league_elo``; media, riferimento e giudizio senza chiamare ``form_strength``;
    * **testi** — nessuna attribuzione a Transfermarkt (il valore è della distinta FotMob) e
      nessuna stringa fantasma nel piè di card.
    """
    import math

    import pandas as pd

    from fda.site.analysis import MatchAnalysis
    from fda.store import Store
    from fda.teams import canonical

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    fx = st.read("fixtures")
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    if fx.empty or not pages:
        return fails, checks
    ma = MatchAnalysis(st)
    by_id = fx.drop_duplicates("match_id").set_index("match_id")
    # conteggio indipendente del campione: gare di campionato giocate prima del calcio d'inizio
    us = st.read("understat_team_matches")
    if not us.empty:
        from fda.teams import canonical as _canon
        us = us.assign(_c=us.team_name.map(_canon),
                       _d=pd.to_datetime(us["date"], utc=True, errors="coerce"))
    fin_cal = fx[fx.status == "finished"].copy()
    fin_cal["_ko"] = pd.to_datetime(fin_cal.utc_kickoff, utc=True, errors="coerce")
    # Date delle schede e delle gare della forma: l'oracolo scorre lo storico una volta
    # sola, senza i metodi del generatore che sta verificando.
    page_ids = {int(pg.stem) for pg in pages if pg.stem.isdigit()}
    cutoffs = pd.concat([fin_cal["_ko"], pd.to_datetime(
        fx.loc[fx.match_id.isin(page_ids), "utc_kickoff"], utc=True, errors="coerce")])
    elo_at, leagues_at = elo_reference_at_dates(st.read("history"), fx, cutoffs,
                                               min_teams=ma.ELO_MIN_TEAMS)
    mi_fin = st.read("match_info")
    con_xg = set()
    if not mi_fin.empty and {"home_xg", "away_xg"} <= set(mi_fin.columns):
        con_xg = set(mi_fin.dropna(subset=["home_xg", "away_xg"]).match_id.astype(int))

    #: una squadra gioca al più una partita in 24 ore: la riga Understat di questa
    #: squadra entro le 24 ore prima di ``ko`` è la partita che la scheda descrive.
    STESSA_GARA = pd.Timedelta(hours=24)

    def gare_prima(tid: int, tname: str, ko) -> tuple[int, int]:
        """(gare Understat, gare di calendario con xG) giocate **prima** di ``ko``.

        La gara descritta è esclusa dal campione della sua stessa scheda: Understat la
        data qualche minuto prima del calcio d'inizio FotMob (misurato il 2026-10-10 su
        Cagliari–Lecce, Lille–PSG e Atlético Madrid–Málaga) e il solo taglio ``date < ko``
        la lascerebbe dentro (`docs/76` §1). Il calendario non ha il problema: il calcio
        d'inizio della gara descritta è ``ko`` e ``<`` lo esclude.
        """
        n_us = 0
        if not us.empty:
            from fda.teams import canonical as _canon
            g = us[(us._c == _canon(str(tname))) & (us._d < ko)
                   & (us._d < ko - STESSA_GARA)]
            n_us = len(g)
        g2 = fin_cal[((fin_cal.home_id == tid) | (fin_cal.away_id == tid)) & (fin_cal._ko < ko)]
        return n_us, int(g2.match_id.astype(int).isin(con_xg).sum())

    box_re = re.compile(
        r"xG creati / gara</div>\s*<div[^>]*>([\d,]+) <span[^>]*>\((Understat|FotMob), "
        r"(\d+) gar[ae]\)</span></div>\s*"
        r'(?:<div class="mut small"[^>]*title="[^"]*">([\d,]+)× la media del campionato)?')
    xga_re = re.compile(
        r"xG concessi / gara</div>\s*<div[^>]*>([\d,]+) <span[^>]*>"
        r"\(stess[ae](?: (\d+))? gar[ae]\)</span></div>\s*"
        r'(?:<div class="mut small"[^>]*title="[^"]*">([\d,]+)× la media del campionato)?')
    xpts_re = re.compile(
        r"xPTS vs punti reali</div>\s*<div[^>]*>([\d,]+) <span[^>]*>vs</span> (\d+) "
        r'<span class="mut" title="[^"]*">\(([+-]?[\d,]+)\)</span>')
    verdetto_re = re.compile(r"(\d+) gar[ae] · <span title=\"[^\"]*\">(.*?)</span></div>")
    # [44]/docs/64 §9: il numero in evidenza della casella «Pressing · riposo» è l'indice di
    # pressione FotMob (7 leghe su 7), col suo rapporto di lega sulla riga sotto.
    press_re = re.compile(r"<span title=\"Passaggi che l'avversario[^\"]*\">([\d,]+)</span>")

    def num(x: str) -> float:
        return float(x.replace(",", "."))

    def forza_forma(sec: str, tid: int, lg, ko, pagina: str) -> None:
        """Calendario + oracolo Elo indipendente: il codice del sito può essere guasto."""
        nonlocal checks
        label = f"{pagina} squadra {tid}"
        games = fin_cal[(fin_cal._ko < ko)
                        & ((fin_cal.home_id == tid) | (fin_cal.away_id == tid))
                        ].sort_values("_ko").tail(5)
        rows = []
        for game in games.itertuples(index=False):
            home = game.home_id == tid
            gf, ga = ((game.home_goals, game.away_goals) if home
                      else (game.away_goals, game.home_goals))
            rows.append({"opponent": game.away_name if home else game.home_name,
                         "home": home, "gf": int(gf), "ga": int(ga),
                         "res": "V" if gf > ga else "N" if gf == ga else "P",
                         "date": pd.to_datetime(game.utc_kickoff, utc=True)})
        ref = leagues_at.get((lg, ko))
        ratings, ranks, listing, dots = [], [], [], []
        for row in rows:
            name = canonical(row["opponent"])
            elo = elo_at.get(row["date"], {}).get(name)
            ratings.append(elo)
            past = leagues_at.get((lg, row["date"]))
            rank = past["ranks"].get(name) if past else None
            venue = "in casa" if row["home"] else "in trasferta"
            item = f"{row['gf']}-{row['ga']} {venue} con {row['opponent']}"
            if elo is not None and rank is not None:
                ranks.append((round(elo), rank))
                item += f" ({rank}ª) ⓘ"
            listing.append(item)
            title = (f"{venue} contro {row['opponent']}: "
                     f"{row['gf']}-{row['ga']} (gol fatti-subiti)")
            dots.append((row["res"], title, row["res"]))
        forms = re.findall(rf'<p class="form-recent" data-team-id="{tid}"[^>]*>(.*?)</p>',
                           sec, re.DOTALL)
        checks += 1
        if len(forms) != bool(rows):
            fails.append(f"{label}: strisce della forma {len(forms)}, attese {int(bool(rows))}")
        form = forms[0] if forms else ""
        printed = re.findall(
            r'<span class="form-opp-rank" title="[^"]*?: ([\d.]+)\.[^"]*">'
            r'\((\d+)ª\) ⓘ</span>', form)
        actual = [(int(value.replace(".", "")), int(rank)) for value, rank in printed]
        checks += 1
        if actual != ranks:
            fails.append(f"{label}: ranghi/Elo degli avversari della forma non alla vigilia "
                         f"({actual} ≠ {ranks})")
        # Non basta che i numeri tornino: devono essere accanto all'avversario giusto.
        listed = re.search(r'<span class="small mut">(.*)</span>\s*$', form, re.DOTALL)
        text = Text()
        text.feed(listed.group(1) if listed else "")
        actual_list = " ".join("".join(text.parts).split())
        checks += 2
        if actual_list != " ".join(", ".join(listing).split()):
            fails.append(f"{label}: elenco della forma diverso dal calendario "
                         "(avversari, punteggi, sede o ordine)")
        printed_dots = re.findall(r'<span class="form-dot ([VNP])" title="([^"]*)">'
                                 r'([VNP])</span>', form)
        if [(res, html_unescape(title), value) for res, title, value in printed_dots] != dots:
            fails.append(f"{label}: pallini/tooltip della forma diversi dal calendario")
        summary = re.findall(
            rf'<p class="form-strength mut small" data-team-id="{tid}"[^>]*>(.*?)</p>',
            sec, re.DOTALL)
        expected = bool(rows and ref and all(value is not None for value in ratings))
        checks += 1
        if len(summary) != int(expected):
            fails.append(f"{label}: righe «Avversari affrontati» {len(summary)}, "
                         f"attese {int(expected)}")
        if not expected or len(summary) != 1:
            return
        printed_avg = re.search(r"Avversari affrontati: forza media <b>([\d.]+)</b> "
                                r"contro ([\d.]+) del campionato", summary[0])
        checks += 1
        if not printed_avg:
            fails.append(f"{label}: forza media degli avversari senza i due numeri")
            return
        avg = sum(ratings) / len(ratings)
        population = list(ref["ratings"].values())
        league_avg = sum(population) / len(population)
        sd = math.sqrt(sum((v - league_avg) ** 2 for v in population) / len(population))
        se = sd / math.sqrt(len(rows))
        diff = avg - league_avg
        verdict = ("più duro della media" if diff > se else "più morbido della media"
                   if diff < -se else "in linea col campionato")
        for text, value, name in zip(printed_avg.groups(), (avg, league_avg),
                                    ("forza media avversari", "media Elo di lega"), strict=True):
            checks += 1
            if abs(int(text.replace(".", "")) - value) > 0.501:
                fails.append(f"{label}: {name} {text} ≠ {value:.2f}")
        checks += 2
        if f'<span class="form-strength-label">{verdict}</span>' not in summary[0]:
            fails.append(f"{label}: giudizio della forma diverso da «{verdict}»")
        threshold = re.search(r"circa ±(\d+) punt[oi] Elo", html_unescape(summary[0]))
        if not threshold or abs(int(threshold.group(1)) - se) > 0.501:
            fails.append(f"{label}: soglia della forma diversa dall'errore standard")

    n_pagine = n_pannelli = n_rif = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        i = html.find('id="squadre"')
        checks += 1
        if i < 0:
            fails.append(f"{pg.name}: la card «Le due squadre» non c'è")
            continue
        sec = html[i:html.find('id="club"', i) if html.find('id="club"', i) > 0 else len(html)]
        n_pagine += 1
        try:
            mid = int(pg.stem)
            riga = by_id.loc[mid]
        except (KeyError, ValueError):
            continue
        for k in ('<h2 class="as-h2" style="grid-column:1/-1">Le due squadre</h2>',
                  "Che cosa c'è in questa card:"):
            checks += 1
            if k not in sec:
                fails.append(f"{pg.name}: «Le due squadre» senza «{k[:34]}…»")
        checks += 2
        if "Transfermarkt" in sec:
            fails.append(f"{pg.name}: «Le due squadre» attribuisce il valore a Transfermarkt")
        if "Ruolo n.d." in sec:
            fails.append(f"{pg.name}: il piè di card spiega «Ruolo n.d.», stringa che non esiste")
        # ogni riquadro di stagione va letto accanto al suo gemello: le due squadre, in ordine
        boxes = box_re.findall(sec)
        xgas = xga_re.findall(sec)
        xpts = xpts_re.findall(sec)
        verdetti = verdetto_re.findall(sec)
        ko = pd.to_datetime(riga.utc_kickoff, utc=True)
        attesi = []
        for tid, tname in ((int(riga.home_id), str(riga.home_name)),
                           (int(riga.away_id), str(riga.away_name))):
            a = ma.season_xg(tname, tid, ko)
            if a:
                a = dict(a, _prima=gare_prima(tid, tname, ko))
            attesi.append(a)
        presenti = [a for a in attesi if a]
        # il campione dichiarato non può contenere gare giocate dopo questa partita
        for a in presenti:
            checks += 1
            atteso_n = a["_prima"][0] if a["source"] == "Understat" else a["_prima"][1]
            if int(a["played"]) != int(atteso_n):
                fails.append(f"{pg.name}: campione {a['source']} {a['played']} gare, ma prima "
                             f"del calcio d'inizio ne risultano {atteso_n}")
        checks += 2
        if len(boxes) != len(presenti):
            fails.append(f"{pg.name}: riquadri «xG creati» {len(boxes)} per {len(presenti)} "
                         "squadre con dati")
            continue
        # il riposo non dipende dagli xG: due caselle «Pressing · riposo» sempre, anche quando
        # una squadra non ha gare precedenti (docs/64 §7)
        if sec.count("Pressing · riposo") != 2:
            fails.append(f"{pg.name}: caselle «Pressing · riposo» {sec.count('Pressing · riposo')}, "
                         "attese 2 (una per squadra, anche senza numeri di stagione)")
        mancanti = sum(1 for a in attesi if not a)
        if mancanti and sec.count("nessuna gara di campionato prima di questa") != mancanti:
            fails.append(f"{pg.name}: {mancanti} squadre senza gare precedenti, "
                         "ma la card non lo dichiara")
        checks += 1
        if len({b[1] for b in boxes}) > 1:
            fails.append(f"{pg.name}: le due squadre mescolano fonti xG diverse "
                         f"({sorted({b[1] for b in boxes})}): i due numeri non sono "
                         "confrontabili, serve un alias in fda/teams.py")
        for k, atteso in enumerate(presenti):
            n_pannelli += 1
            valore, fonte, gare, rapporto = boxes[k]
            checks += 3
            if fonte != atteso["source"]:
                fails.append(f"{pg.name}: fonte xG stampata {fonte}, calcolata {atteso['source']}")
            if abs(num(valore) - float(atteso["xg_pm"])) > 0.051:
                fails.append(f"{pg.name}: xG creati {valore} ≠ {atteso['xg_pm']:.2f}")
            if int(gare) != int(atteso["played"]):
                fails.append(f"{pg.name}: campione xG {gare} ≠ {atteso['played']}")
            atteso_rapporto = atteso.get("xg_ratio")
            checks += 1
            if atteso.get("ratio_short"):
                if rapporto:
                    fails.append(f"{pg.name}: rapporto di lega pubblicato su {atteso['played']} "
                                 f"gare (minimo {ma.XG_RATIO_MIN_GAMES})")
                if "campione troppo corto per il confronto con la lega" not in sec:
                    fails.append(f"{pg.name}: campione corto senza la nota che lo dichiara")
            elif atteso_rapporto and not rapporto:
                fails.append(f"{pg.name}: riferimento di lega assente con media disponibile")
            elif rapporto:
                n_rif += 1
                if abs(num(rapporto) - float(atteso_rapporto or 0)) > 0.011:
                    fails.append(f"{pg.name}: rapporto xG {rapporto}× ≠ "
                                 f"{float(atteso_rapporto or 0):.2f}×")
            if k < len(xgas):
                v_ga, gare_ga, rap_ga = xgas[k]
                checks += 2
                if abs(num(v_ga) - float(atteso["xga_pm"])) > 0.051:
                    fails.append(f"{pg.name}: xG concessi {v_ga} ≠ {atteso['xga_pm']:.2f}")
                if int(gare_ga or 1) != int(atteso["played"]):
                    fails.append(f"{pg.name}: campione xG concessi {gare_ga} ≠ {atteso['played']}")
                if rap_ga and atteso.get("xga_ratio"):
                    checks += 1
                    if abs(num(rap_ga) - float(atteso["xga_ratio"])) > 0.011:
                        fails.append(f"{pg.name}: rapporto xGA {rap_ga}× ≠ "
                                     f"{float(atteso['xga_ratio']):.2f}×")
            lettura = atteso.get("xpts_read")
            if lettura and atteso.get("xpts") is not None and k < len(xpts):
                v_x, v_p, v_d = xpts[k]
                checks += 3
                if abs(num(v_x) - float(atteso["xpts"])) > 0.051:
                    fails.append(f"{pg.name}: xPTS {v_x} ≠ {float(atteso['xpts']):.1f}")
                if int(v_p) != int(atteso["pts"]):
                    fails.append(f"{pg.name}: punti {v_p} ≠ {atteso['pts']}")
                if abs(num(v_d) - float(lettura["diff"])) > 0.051:
                    fails.append(f"{pg.name}: scarto {v_d} ≠ {lettura['diff']:.1f}")
            if lettura and k < len(verdetti):
                gare_v, testo = verdetti[k]
                atteso_testo = ("sopra gli attesi" if lettura["verdict"] == "sopra"
                                else "sotto gli attesi" if lettura["verdict"] == "sotto"
                                else "in linea" if lettura["band"] else "campione troppo corto")
                checks += 2
                if int(gare_v) != int(atteso["played"]):
                    fails.append(f"{pg.name}: gare del verdetto xPTS {gare_v} ≠ {atteso['played']}")
                if atteso_testo not in html_unescape(testo):
                    fails.append(f"{pg.name}: verdetto xPTS «{testo[:30]}» invece di "
                                 f"«{atteso_testo}»")
            # il PPDA di Understat non è più il numero in evidenza (copre 5 leghe su 7): dove
            # esiste deve comunque restare leggibile nel ⓘ del pressing, accanto all'indice
            atteso_ppda = atteso.get("ppda")
            checks += 1
            if atteso_ppda is not None and not pd.isna(atteso_ppda):
                val = f"{float(atteso_ppda):.1f}".replace(".", ",")
                # o nel ⓘ accanto all'indice FotMob, o — dove l'indice non è calcolabile —
                # come numero in evidenza della casella, col suo «PPDA (Understat)»
                atteso_txt = f"PPDA Understat sullo stesso periodo: {val}"
                ripiego = f">{val}</span> <span class=\"mut small\""
                testo_sec = html_unescape(sec)
                if atteso_txt not in testo_sec and (
                        ripiego not in sec or "PPDA (Understat)" not in sec):
                    fails.append(f"{pg.name}: il ⓘ del pressing non riporta il PPDA Understat "
                                 f"{float(atteso_ppda):.1f}")
        # [44]/docs/64 §9 — indice di pressione: ricalcolato dai Parquet per **entrambe** le
        # squadre di ogni scheda, in tutte e 7 le leghe (è la casella che prima mancava del
        # tutto a Eredivisie e Liga Portugal).
        press_stampati = press_re.findall(sec)
        press_attesi = [ma.season_pressing(int(riga.home_id), ko),
                        ma.season_pressing(int(riga.away_id), ko)]
        press_vivi = [p for p in press_attesi if p]
        checks += 1
        if len(press_stampati) != len(press_vivi):
            fails.append(f"{pg.name}: indici di pressione stampati {len(press_stampati)}, "
                         f"ricalcolati {len(press_vivi)}")
        for stampato, atteso_pr in zip(press_stampati, press_vivi, strict=False):
            checks += 2
            if abs(num(stampato) - float(atteso_pr["value"])) > 0.011:
                fails.append(f"{pg.name}: indice di pressione {stampato} ≠ "
                             f"{atteso_pr['value']:.2f}")
            rapporto = atteso_pr.get("ratio")
            atteso_rap = f"{rapporto:.2f}".replace(".", ",") if rapporto else None
            if atteso_rap and f"{atteso_rap}× la media del campionato" not in sec:
                fails.append(f"{pg.name}: rapporto di pressione {atteso_rap}× assente")
            checks += 1
            etichetta = atteso_pr.get("label")
            if etichetta and f"<b>{etichetta}</b>" not in sec:
                fails.append(f"{pg.name}: etichetta di pressing «{etichetta}» assente")
        # [44]/docs/76 §7 — «Attacco contro difesa»: esce solo sulle schede pre-partita in
        # cui entrambe le squadre hanno i due rapporti di lega dalla stessa fonte; la
        # striscia pubblica la sintesi (produzione attesa = crea × concede l'avversaria),
        # le barre in scala 0–2,5×, i quattro rapporti di dettaglio e il verdetto sullo
        # squilibrio solo oltre 1σ (stessa convenzione della banda xPTS).
        attesi_ad = None
        if ("Analisi pre-partita" in html and len(attesi) == 2 and attesi[0] and attesi[1]
                and attesi[0].get("source") == attesi[1].get("source")
                and all(x.get(c) is not None for x in attesi
                        for c in ("xg_ratio", "xga_ratio"))):
            h_ad, a_ad = attesi[0], attesi[1]
            prod_h = float(h_ad["xg_ratio"]) * float(a_ad["xga_ratio"])
            prod_a = float(a_ad["xg_ratio"]) * float(h_ad["xga_ratio"])
            q = prod_h / prod_a
            cv = 1.036 / 1.692     # sd/media xG per gara-squadra (docs/64 §7)
            se_ln_q = math.sqrt(sum((cv / (float(r) * math.sqrt(int(x["played"])))) ** 2
                                    for x in (h_ad, a_ad)
                                    for r in (x["xg_ratio"], x["xga_ratio"])))
            attesi_ad = {"prod": (prod_h, prod_a),
                         "rapporti": (float(h_ad["xg_ratio"]), float(a_ad["xga_ratio"]),
                                      float(a_ad["xg_ratio"]), float(h_ad["xga_ratio"])),
                         "q": q, "oltre": abs(math.log(q)) > se_ln_q,
                         "leader": 0 if prod_h > prod_a else 1}
        i_ad = sec.find('id="attacco-difesa"')
        blocco_ad = sec[i_ad:sec.find('<p class="small mut"', i_ad)] if i_ad >= 0 else ""
        checks += 1
        if attesi_ad is None:
            if i_ad >= 0:
                fails.append(f"{pg.name}: «Attacco contro difesa» pubblicata senza i requisiti "
                             "(gara già giocata, campione corto o fonti xG diverse)")
        elif not blocco_ad:
            fails.append(f"{pg.name}: «Attacco contro difesa» assente con entrambe le squadre "
                         "che hanno i due rapporti di lega dalla stessa fonte")
        else:
            prodotti = [num(v) for v in re.findall(
                r'font:700 13px[^>]*>([\d,]+)×</span>', blocco_ad)]
            checks += 2
            if len(prodotti) != 2 or not all(abs(p - a) <= 0.011
                                             for p, a in zip(prodotti, attesi_ad["prod"],
                                                             strict=True)):
                fails.append(f"{pg.name}: produzioni attese {prodotti}, "
                             f"calcolate {[round(v, 2) for v in attesi_ad['prod']]}")
            barre = [int(v) for v in re.findall(r"width:(\d+)%", blocco_ad)]
            checks += 2
            attese = [round(min(v, 2.5) / 2.5 * 100) for v in attesi_ad["prod"]]
            if barre != attese:
                fails.append(f"{pg.name}: barre {barre}, attese {attese}")
            rapp = [num(v) for v in re.findall(
                r"crea ([\d,]+)× la media e affronta una difesa che concede ([\d,]+)× · "
                r".*?crea ([\d,]+)× e affronta una difesa che concede ([\d,]+)×",
                blocco_ad, re.DOTALL)[0]] if re.search(
                r"crea [\d,]+× la media e affronta", blocco_ad) else []
            checks += 4
            for v, a, che in zip(rapp, attesi_ad["rapporti"],
                                 ("crea casa", "concede trasferta",
                                  "crea trasferta", "concede casa"), strict=False):
                if abs(v - a) > 0.011:
                    fails.append(f"{pg.name}: attacco contro difesa, {che} {v} ≠ {a:.2f}")
            if len(rapp) != 4:
                fails.append(f"{pg.name}: dettaglio dell'incrocio con {len(rapp)} rapporti, "
                             "attesi 4")
            checks += 1
            nomi = (str(riga.home_name), str(riga.away_name))
            if attesi_ad["oltre"]:
                if f"<b>{nomi[attesi_ad['leader']]}</b> ha il confronto offensivo migliore" \
                        not in blocco_ad:
                    fails.append(f"{pg.name}: verdetto dell'incrocio senza il leader atteso "
                                 f"{nomi[attesi_ad['leader']]}")
            elif "entro il rumore del campione" not in blocco_ad:
                fails.append(f"{pg.name}: squilibrio entro 1σ ma la striscia dichiara un "
                             "vincitore del confronto")
        for tid in (int(riga.home_id), int(riga.away_id)):
            forza_forma(sec, tid, riga.league_id, ko, pg.name)
        checks += 1
        if re.search(r"coppe incluse", sec):
            fails.append(f"{pg.name}: il riposo dice ancora «coppe incluse» senza il nome")
        # infermeria: il totale è la somma esatta della colonna, e ogni riga ha il ruolo
        for blocco in sec.split('<p id="infermeria-')[1:]:
            tabella = blocco.split("</table>", 1)[0]
            tot = re.search(r"· ([\d,]+) xG\+xA a partita in meno", blocco)
            voci = [num(v) for v in re.findall(
                r'<b style="color:var\(--accent\)">(?:◇ )?([\d,]+)</b>', tabella)]
            if tot:
                checks += 1
                if abs(sum(voci) - num(tot.group(1))) > 0.011:
                    fails.append(f"{pg.name}: infermeria, totale {tot.group(1)} ≠ somma della "
                                 f"colonna {sum(voci):.2f}")
            nomi = re.findall(r"<td><b>[^<]+</b>(.*?)</td>", tabella)
            checks += 1
            senza = [n for n in nomi if "border-radius:999px" not in n]
            if senza:
                fails.append(f"{pg.name}: infermeria, {len(senza)} righe senza la pillola "
                             "del ruolo (neanche «ruolo n.d.»)")
    print(f"[44] schede con «Le due squadre» verificate: {n_pagine} pagine, "
          f"{n_pannelli} riquadri di squadra, {n_rif} riferimenti di lega")
    return fails, checks


def check_numbers(site: Path, data: Path | None) -> tuple[list[str], int]:
    """Ricalcola i numeri pubblicati con le funzioni del progetto e li confronta."""
    import numpy as np
    import pandas as pd

    from fda.site.advanced import dixon_coles_grid, grid_1x2, score_matrix
    from fda.store import Store

    st = Store(data) if data else Store()
    fails: list[str] = []
    checks = 0
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    preds = st.read("predictions")
    if preds.empty:
        return fails, checks
    preds = preds.sort_values("made_at").groupby("match_id").tail(1).set_index("match_id")
    mi = st.read("match_info")

    # 1) matrice dei punteggi: celle = score_matrix(λ, ρ) e celle+coda = 100%
    n_matrix = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Matrice dei punteggi" not in html:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: matrice senza previsione")
            continue
        r = preds.loc[mid]
        m = score_matrix(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        # il valore «<1» è scritto «&lt;1» dal 2026-10-11 (docs/78 §12): col segno crudo i
        # browser lo recuperavano come testo ma il taglio dei tag degli strumenti di verifica
        # lo mangiava, e in un attributo non quotato avrebbe rotto l'attributo. Qui si
        # accettano entrambe le grafie, così la lettura regge anche su una build vecchia.
        cells = re.findall(
            r'<td[^>]*title="(\d)-(\d) · (meno di 0,1|\d+,\d+)%[^"]*">((?:&lt;|<)1|\d+,\d)</td>',
            html)
        if len(cells) != 36:
            fails.append(f"{pg.name}: celle matrice {len(cells)} (attese 36)")
            continue
        # normalizzato una volta sola: i due lettori qui sotto (verifica del valore e somma
        # a 100%) devono vedere la stessa grafia
        cells = [(i, j, t, "<1" if c in ("<1", "&lt;1") else c) for i, j, t, c in cells]
        n_matrix += 1
        for i, j, _title_p, cell_p in cells:
            checks += 1
            true_p = float(m["cells"][int(i)][int(j)]["p"]) * 100
            if cell_p == "<1":
                if true_p >= 0.05:
                    fails.append(f"{pg.name}: cella {i}-{j} mostra <1 ma vale {true_p:.2f}/100")
            else:
                if true_p < 0.05:
                    fails.append(f"{pg.name}: cella {i}-{j} mostra {cell_p} ma vale {true_p:.2f}/100 (<0,05)")
        worst, tot = 0.0, 0.0
        for i, j, _title_p, cell_p in cells:
            rendered = 0.0 if cell_p == "<1" else float(cell_p.replace(",", "."))
            worst = max(worst, abs(rendered - round(float(m["cells"][int(i)][int(j)]["p"]) * 100, 1)))
            tot += rendered
        tail_m = re.search(r"Almeno una delle due squadre segna 6\+ gol.*?: (\d+,\d) partite su 100", html)
        if not tail_m:
            fails.append(f"{pg.name}: etichetta della coda della matrice assente o ambigua")
        tail = float(tail_m.group(1).replace(",", ".")) if tail_m else 0.0
        # docs/77 §5: la somma è fra valori arrotondati a 0,1: va confrontata alla stessa
        # cifra, altrimenti 36 addendi in virgola mobile portano 100,6 a 100,60000000002 e
        # il limite inclusivo diventa esclusivo (falso allarme su 5749708 l'11/10/2026)
        tot_r = round(tot + tail, 1)
        if worst > 0.11:
            fails.append(f"{pg.name}: cella matrice diversa di {worst:.2f} pp")
        if not 99.0 <= tot_r <= 100.6:
            fails.append(f"{pg.name}: matrice+coda = {tot + tail:.1f}%")
        # coerenza con le probabilità pubblicate (stessa τ del modello, vedi dc_grid)
        g = dixon_coles_grid(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        ph, pdw, _pa = grid_1x2(g)
        if abs(ph - float(r.p_home)) > 0.015 or abs(pdw - float(r.p_draw)) > 0.015:
            fails.append(f"{pg.name}: 1X2 griglia ({ph:.3f}/{pdw:.3f}) != previsione "
                         f"({r.p_home:.3f}/{r.p_draw:.3f})")
    print(f"[1] matrici punteggi verificate: {n_matrix}")

    # 1b) coppia «Stime Dixon-Coles pesato + Elo (A/B)»: due cifre affiancate che il lettore
    #     legge come una ripartizione, quindi devono chiudere 100. Fino al 2026-10-11 erano due
    #     arrotondamenti indipendenti: un w_dc di 62,5% pubblicava «62/38» con `round()` e
    #     «63/38» = 101 col mezzo in su (`docs/78` §15). Ora il generatore usa il metodo del
    #     resto massimo (`pct3`) e qui si verifica la **specifica**, non l'identità con la
    #     funzione: somma 100 e valori che sono pavimento o tetto di w_dc·100 — i casi di
    #     parità in cui due implementazioni corrette scelgono diversamente sono ammessi.
    n_dcelo = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        mj = re.search(r"Stime Dixon-Coles pesato \+ Elo \((\d{1,3})/(\d{1,3})\)", html)
        if not mj:
            continue
        mid = int(pg.stem)
        if mid not in preds.index or "w_dc" not in preds.columns:
            fails.append(f"{pg.name}: riga Dixon-Coles/Elo senza previsione con w_dc")
            continue
        n_dcelo += 1
        checks += 1
        w = float(preds.loc[mid, "w_dc"])
        if not terna_valida((w, 1 - w), 0, (int(mj.group(1)), int(mj.group(2)))):
            fails.append(f"{pg.name}: ripartizione DC/Elo {mj.group(1)}/{mj.group(2)} non è un "
                         f"arrotondamento legittimo di w_dc = {w:.4f}")
    print(f"[1b] ripartizioni Dixon-Coles/Elo verificate: {n_dcelo}")

    # 2) probabilità in-play: ogni riga somma **esattamente** 100 e l'ultima coincide col
    #    risultato. Fino al 2026-10-11 la tolleranza era «>3» perché il generatore arrotondava
    #    le tre celle con tre `round()` indipendenti: con quella tolleranza 153 righe rotte
    #    (99/101) sono passate sotto il naso di questo controllo e le ha viste solo [47],
    #    aggiunto dopo (`docs/79`). Ora che la terna passa da `pct_triple` la somma è esatta.
    n_wp = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Probabilità in-play" not in html:
            continue
        block = html.split("Probabilità in-play", 1)[1]
        rows = re.findall(r'<td class="mut small">(\d+)\'</td>\s*<td>([^<]*)</td>\s*'
                          r'<td class="r">(\d+)%</td>\s*<td class="r">(\d+)%</td>\s*<td class="r">(\d+)%</td>',
                          block)
        if not rows:
            fails.append(f"{pg.name}: tabella in-play senza righe")
            continue
        n_wp += 1
        checks += 1
        for minute, _score, a, b, c in rows:
            if int(a) + int(b) + int(c) != 100:
                fails.append(f"{pg.name}: in-play {minute}' = {a}+{b}+{c}")
        sc = re.match(r"\s*(\d+)-(\d+)", rows[-1][1])
        hg, ag = (int(sc.group(1)), int(sc.group(2))) if sc else (0, 0)
        row = mi[mi.match_id == int(pg.stem)]
        if not row.empty and pd.notna(row.iloc[0]["home_goals"]) and \
                (hg, ag) != (int(row.iloc[0]["home_goals"]), int(row.iloc[0]["away_goals"])):
            fails.append(f"{pg.name}: in-play finisce {hg}-{ag}, risultato "
                         f"{int(row.iloc[0]['home_goals'])}-{int(row.iloc[0]['away_goals'])}")
    print(f"[2] pagine con probabilità in-play verificate: {n_wp}")

    # 3) accuratezza: RPS ricalcolato in modo indipendente dalla pagina
    fx = st.read("fixtures")
    fin = fx[fx.status == "finished"][["match_id", "home_goals", "away_goals", "utc_kickoff"]]
    p = st.read("predictions").merge(fin, on="match_id", suffixes=("", "_fx"))
    p = p[p.made_at < p.utc_kickoff_fx].sort_values("made_at").groupby("match_id").tail(1)
    acc_path = site / "accuratezza.html"
    if not p.empty and acc_path.exists():
        outc = np.where(p.home_goals > p.away_goals, 0, np.where(p.home_goals == p.away_goals, 1, 2))
        mine = rps_indip(p[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist(), outc.tolist())
        acc_txt = acc_path.read_text(encoding="utf-8")
        mrow = re.search(r'Tutti</td><td class="r">(\d+)</td>'
                         r'(?:<td class="r">\d+</td>)?<td class="r">(\d+,\d+)</td>', acc_txt)
        if not mrow:
            fails.append("accuratezza.html: riga 'Tutti' non trovata")
        else:
            checks += 1
            n_page, rps_page = int(mrow.group(1)), float(mrow.group(2).replace(",", "."))
            if n_page != len(p):
                fails.append(f"accuratezza: {n_page} gare in pagina vs {len(p)} ricalcolate")
            if abs(rps_page - mine) > 0.002:
                fails.append(f"accuratezza: RPS pagina {rps_page} vs ricalcolato {mine:.4f}")
            print(f"[3] accuratezza: {len(p)} gare, RPS pagina {rps_page} = ricalcolato {mine:.4f}")
        # 3b) invarianti di pubblicazione (docs/19 P0.8): ogni Δ della tabella riepilogo deve
        # equalare RPS − naive ricalcolati dai numeri stampati, e la composizione dichiarata
        # del campione deve coincidere con la somma delle gare della tabella.
        # Le colonne si leggono **per nome** (gruppi nominati): con la colonna «di cui col
        # modello corrente» (docs/46 §1) la vecchia regex posizionale ha smesso di leggere
        # la tabella e il controllo è giustamente caduto — meglio un nome che una posizione.
        righe_riep = [m.groupdict() for m in re.finditer(
            r'<td>(?P<lg>[^<]+)</td><td class="r">(?P<n>[\d.]+)</td>'
            r'<td class="r">(?P<ncorr>\d+)</td><td class="r">(?P<rps>\d+,\d+)</td>'
            r'<td class="r">(?P<brier>\d+,\d+)</td><td class="r">\d+%</td>'
            r'<td class="r">(?P<naive>\d+,\d+)</td>'
            r'<td class="r">(?:[\d.]+|fisso)</td><td class="r [a-z]+">(?P<delta>[+\-−]?[\d,]+)</td></tr>',
            acc_txt)]
        if not righe_riep:
            fails.append("accuratezza.html: tabella riepilogo non leggibile per il controllo [3b]")
        n_leghe, n_tutti, corr_leghe, corr_tutti = 0, 0, 0, 0
        for m_riep in righe_riep:
            checks += 1
            lg, n_r = m_riep["lg"], _int_it(m_riep["n"])
            n_corr = int(m_riep["ncorr"].replace(".", ""))
            if lg.strip() == "Tutti":
                n_tutti, corr_tutti = n_r, n_corr
            else:
                n_leghe += n_r
                corr_leghe += n_corr
            ric = float(m_riep["rps"].replace(",", ".")) - float(m_riep["naive"].replace(",", "."))
            pub = float(m_riep["delta"].replace(",", ".").replace("−", "-"))
            if abs(pub - ric) > 0.0011:   # rps/naive a 4 decimali + Δ a 3: tolleranza di stampa
                fails.append(f"accuratezza: Δ {lg} pubblicato {pub:+.4f} ≠ RPS − naive {ric:+.4f}")
        if n_tutti and n_leghe and n_tutti != n_leghe:
            fails.append(f"accuratezza: riga Tutti {n_tutti} gare ≠ somma leghe {n_leghe}")
        # la nuova colonna non può raccontare una storia diversa dalla composizione: le gare
        # «col modello corrente» della tabella devono essere le stesse della nota (docs/46 §1)
        if corr_tutti and corr_leghe and corr_tutti != corr_leghe:
            fails.append(f"accuratezza: riga Tutti {corr_tutti} gare del modello corrente "
                         f"≠ somma leghe {corr_leghe}")
        m_comp = re.search(r"Composizione del campione: ([\d.]+) gare valutate", acc_txt)
        if m_comp:
            checks += 1
            if _int_it(m_comp.group(1)) != n_tutti:
                fails.append(f"accuratezza: composizione {m_comp.group(1)} gare ≠ riga Tutti {n_tutti}")
            m_corr = re.search(r"di cui\s*<b>([\d.]+)</b> con il modello corrente", acc_txt)
            if m_corr:
                checks += 1
                if _int_it(m_corr.group(1)) != corr_tutti:
                    fails.append(f"accuratezza: composizione {m_corr.group(1)} gare del modello corrente "
                                 f"≠ riga Tutti {corr_tutti}")
        elif "Riepilogo" in acc_txt:
            fails.append("accuratezza.html: composizione del campione assente (docs/19 §1.5)")
        else:
            print("[3b] accuratezza: pagina senza riepilogo (nessuna previsione valutabile)")

    # 7) accuratezza: intervalli di Wilson pubblicati, ricalcolati con la funzione del progetto
    if acc_path.exists():

        def _n(txt: str) -> float:
            return float(re.sub(r"<[^>]+>", "", txt).replace(".", "").replace(",", ".").rstrip("%"))

        righe = 0
        for row in re.findall(r"<tr><td>.*?</tr>", acc_path.read_text(encoding="utf-8"), re.DOTALL):
            mi = re.search(r'<td class="r mut">(\d+,\d+)\s*[–-]\s*(\d+,\d+)%</td>', row)
            if not mi:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            lo_p, hi_p = _n(mi.group(1)), _n(mi.group(2))
            # k/n può avere il separatore delle migliaia («(2.494/5.836)», docs/41 §3.2):
            # la regex lo accetta e `_n`/`int` tolgono i punti, come per ogni altro numero
            kn = re.search(r"\(([\d.]+)/([\d.]+)\)", row)
            if kn and len(cells) >= 7:                # riga di mercato: k/n esplicito, 9-10 celle
                k, n, prev = _int_it(kn.group(1)), _int_it(kn.group(2)), _n(cells[2])
            elif kn:                                  # riga di calibrazione: k/n esplicito, 5 celle
                k, n, prev = _int_it(kn.group(1)), _int_it(kn.group(2)), _n(cells[1])
            else:                                     # nessuna k/n pubblicata: k ≈ osservato × n
                n = int(_n(cells[1]))
                prev, obs = _n(cells[2]), _n(cells[3])
                k = round(obs * n / 100.0)
            lo, hi = wilson_indip(k, n)
            checks += 1
            righe += 1
            if abs(lo_p - lo * 100) > 0.06 or abs(hi_p - hi * 100) > 0.06:
                fails.append(f"accuratezza: intervallo pubblicato {lo_p}–{hi_p}% vs ricalcolato "
                             f"{lo * 100:.1f}–{hi * 100:.1f}% (k={k}, n={n})")
            fuori = "fuori intervallo" in row
            # il previsto in pagina è arrotondato a 0,1 punti: se cade a meno di mezzo decimo dal
            # bordo dell'intervallo, la pagina ha deciso con il valore non arrotondato e il
            # confronto sul testo stampato non può essere esatto (misurato: 2 falsi positivi su
            # 24 righe, una prevista al 31,59% con estremo 31,60% e una al 23,40% con 23,40%)
            ambiguo = min(abs(prev / 100 - lo), abs(prev / 100 - hi)) < 5e-4
            if not ambiguo and fuori != bool(not (lo <= prev / 100 <= hi)):
                fails.append(f"accuratezza: segnale {'fuori intervallo' if fuori else 'compatibile'} "
                             f"incoerente con previsto {prev}% e intervallo {lo * 100:.1f}–{hi * 100:.1f}%")
        if righe:
            print(f"[7] accuratezza: {righe} righe con intervallo di Wilson ricalcolate")

    # 8) backtest fuori campione: numerosità, RPS, bias dei gol e calibrazione ricalcolati.
    #    La pagina descrive il modello **calibrato** (come viene pubblicato), quindi il
    #    confronto applica la stessa calibrazione dello store alle righe grezze.
    bt_raw = st.read("backtest")
    if not bt_raw.empty and acc_path.exists():
        from fda.models.backtest import backtest_summary, calibrate_rows
        from fda.models.calibration import from_store

        cal = from_store(st)
        bt = calibrate_rows(bt_raw, cal)
        somm, somm_raw = backtest_summary(bt), backtest_summary(bt_raw)
        text = acc_path.read_text(encoding="utf-8")
        i = text.find("Backtest storico fuori campione")
        if i < 0:
            fails.append("accuratezza.html: tabella `backtest` presente ma nessuna card pubblicata")
        else:
            card = text[i:]
            m_n = re.search(r"su <b>([\d.]+)</b> partite", card)
            m_r = re.search(r"RPS <b>(\d+,\d+)</b>", card)
            if not m_n or not m_r:
                fails.append("accuratezza.html: card backtest senza numerosità o RPS")
            else:
                checks += 1
                mine = rps_indip(bt[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist(),
                              bt["outcome"].to_numpy(int).tolist())
                rps_bt = float(m_r.group(1).replace(",", "."))
                if _int_it(m_n.group(1)) != len(bt):
                    fails.append(f"backtest: {m_n.group(1)} gare in pagina vs {len(bt)} in tabella")
                if abs(rps_bt - mine) > 0.002:
                    fails.append(f"backtest: RPS pagina {rps_bt} vs ricalcolato {mine:.4f}")
                print(f"[8] backtest: {len(bt)} gare fuori campione, RPS pagina {rps_bt} = ricalcolato {mine:.4f}")

            def _num(pattern: str, what: str) -> float | None:
                m = re.search(pattern, card, re.DOTALL)
                if not m:
                    fails.append(f"accuratezza.html: {what} non pubblicato nella card backtest")
                    return None
                return float(m.group(1).replace(",", "."))

            # bias dei gol e pareggio: i due numeri che la calibrazione deve tenere a posto
            got = _num(r"Gol attesi <b>(-?\d+,\d+)</b>", "gol attesi medi")
            if got is not None:
                checks += 1
                if abs(got - somm["lambda_media"]) > 0.002:
                    fails.append(f"backtest: gol attesi {got} vs ricalcolati {somm['lambda_media']:.3f}")
            got = _num(r"pareggio previsto <b>(\d+,\d+)%</b>", "pareggio previsto")
            if got is not None:
                checks += 1
                if abs(got - somm["pareggio_previsto"] * 100) > 0.06:
                    fails.append(f"backtest: pareggio previsto {got}% vs {somm['pareggio_previsto'] * 100:.1f}%")
            if not cal.is_identity:
                got = _num(r"λ × (\d+,\d+)", "moltiplicatore della calibrazione")
                if got is not None:
                    checks += 1
                    if abs(got - cal.lambda_scale) > 0.0015:
                        fails.append(f"backtest: calibrazione pubblicata λ×{got} vs salvata λ×{cal.lambda_scale:.3f}")
                if "versione <code>" not in card:
                    fails.append("backtest: versione della calibrazione non pubblicata")
                # il confronto "senza calibrazione" deve coincidere con la tabella grezza
                got = _num(r"Senza calibrazione lo stesso campione darebbe RPS (\d+,\d+)", "RPS grezza")
                if got is not None:
                    checks += 1
                    if abs(got - somm_raw["rps"]) > 0.002:
                        fails.append(f"backtest: RPS grezza {got} vs ricalcolata {somm_raw['rps']:.4f}")
                print(f"[8b] backtest calibrato: λ×{cal.lambda_scale:.3f} ρ{cal.rho_shift:+.2f} "
                      f"({cal.version}) · bias gol {somm_raw['bias_lambda']:+.3f} → {somm['bias_lambda']:+.3f} "
                      f"· pareggio {somm_raw['pareggio_previsto'] * 100:.1f}% → {somm['pareggio_previsto'] * 100:.1f}%"
                      f" (osservato {somm['pareggio_osservato'] * 100:.1f}%)")

    # 4) proiezioni di stagione: le probabilità di ogni lega sommano come devono.
    # P1.7: i nuovi snapshot portano la soglia configurata (`top_n`/`p_top_n`); i
    # vecchi hanno solo `p_top4` e restano verificabili come migrazione esplicita.
    sim = st.read("season_sim")
    if not sim.empty:
        for lg, g in sim.groupby("league_key"):
            checks += 1
            if abs(g.p_title.sum() - 1) > 0.01:
                fails.append(f"season_sim {lg}: somma P(titolo) = {g.p_title.sum():.3f}")
            top_col = "p_top_n" if "p_top_n" in g.columns else "p_top4"
            top_values = pd.to_numeric(g[top_col], errors="coerce").dropna()
            if not top_values.empty:
                top_n_values = (pd.to_numeric(g["top_n"], errors="coerce").dropna()
                                if "top_n" in g.columns else pd.Series(dtype=float))
                top_n = int(top_n_values.iloc[0]) if not top_n_values.empty else 4
                checks += 1
                if abs(top_values.sum() - min(top_n, len(g))) > 0.02:
                    fails.append(f"season_sim {lg}: somma P(top-{top_n}) = {top_values.sum():.3f}")
                if "p_top_n" in g.columns and "p_top4" in g.columns:
                    checks += 1
                    current = pd.to_numeric(g["p_top_n"], errors="coerce")
                    legacy = pd.to_numeric(g["p_top4"], errors="coerce")
                    both = current.notna() & legacy.notna()
                    if not both.all() or not np.allclose(
                            current[both].to_numpy(), legacy[both].to_numpy(), atol=1e-6):
                        fails.append(f"season_sim {lg}: alias p_top4 diverso da p_top_n")
            checks += 1
            if abs(g.p_rel.sum() - 3) > 0.02:
                fails.append(f"season_sim {lg}: somma P(retrocessione) = {g.p_rel.sum():.3f}")
        print(f"[4] leghe simulate: {sim.league_key.nunique()} · righe {len(sim)}")

    # 5) schede «oggi»: ruolo dei giocatori, conteggio indisponibili, archivio dei precedenti
    lineup, fixtures, h2h = st.read("lineup"), st.read("fixtures"), st.read("h2h")
    # codifica FotMob indipendente dal codice del sito: usualPosition parte da 0 (616 formazioni)
    role_names = {0: "portiere", 1: "difensore", 2: "centrocampista", 3: "attaccante"}
    hist: dict[int, int] = {}
    n_role = n_abs = n_h2h = n_list = 0
    if not lineup.empty and lineup.usual_position_id.notna().any():
        h = lineup[lineup.usual_position_id.notna()]
        hist = {int(k): int(v) for k, v in
                h.groupby("player_id").usual_position_id.agg(lambda x: x.astype(int).mode().iloc[0]).items()}
    hist_name: dict[int, str] = {}
    if not lineup.empty:
        hist_name = {int(k): str(v) for k, v in
                     lineup.dropna(subset=["player_name"]).drop_duplicates("player_id")
                     .set_index("player_id").player_name.items()}
    role_re = re.compile(r'giocatori/(\d+)\.html">([^<]+)</a>\s*<span class="mut small">'
                         r'(portiere|difensore|centrocampista|attaccante)</span>')
    abs_re = re.compile(r"Indisponibili \((\d+)\)")
    # `<th[^>]*>`: le celle d'intestazione portano scope="row" da P2-8; il letterale
    # <th> non le trovava più e [5] contava 0 archivi precedenti (74 controlli persi).
    # Da P2.4 (`docs/28` §3) la card si chiama «Precedenti» e l'etichetta della riga dice
    # il numero dei casi: «Bilancio (15)» — il titolo non ripete più la riga.
    prev_re = re.compile(r"<th[^>]*>Bilancio \((\d+)\)</th>")
    # docs/58 D9: la regex precedente cercava «Infermeria: … N assenti · … M assenti» ma la
    # marcatura reale è una chip («fact-label») senza due punti, con singolare/plurale da
    # `it_plural` — 0 match su index/prossime, il controllo sulle liste era morto. Ora rilegge
    # la chip vera (etichetta «Indisponibili», come la card di destinazione).
    inf_re = re.compile(r'partite/(\d+)\.html(?:(?!partite/).)*?class="fact-label">Indisponibili'
                        r'</span><span>([^<]*?) (\d+) assent[ei] · ([^<]*?) (\d+) assent[ei]', re.DOTALL)
    fx_by_id = {} if fixtures.empty else fixtures.set_index("match_id")
    un_count: dict[tuple[int, int], int] = {}
    if not lineup.empty:
        un = lineup[lineup.role == "unavailable"]
        un_count = {(int(a), int(b)): int(c) for (a, b), c in un.groupby(["match_id", "team_id"]).size().items()}
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        mid = int(pg.stem)
        for pid, _name, shown in role_re.findall(html):
            want = hist.get(int(pid))
            if want is None:
                continue                       # mai schierato: la pagina non stampa il ruolo
            checks += 1
            n_role += 1
            if shown != role_names[want]:
                fails.append(f"{pg.name}: ruolo {shown} per {_name}, atteso {role_names[want]}")
        if mid not in fx_by_id.index:
            continue
        row = fx_by_id.loc[mid]
        want_abs = sorted(x for x in (un_count.get((mid, int(row.home_id)), 0),
                                      un_count.get((mid, int(row.away_id)), 0)) if x)
        shown_abs = sorted(int(x) for x in abs_re.findall(html))
        if shown_abs:
            checks += 1
            n_abs += 1
            if shown_abs != want_abs:
                fails.append(f"{pg.name}: indisponibili {shown_abs} vs {want_abs} dalla distinta")
        m = prev_re.search(html)
        if m and not h2h.empty:
            kick = pd.to_datetime(row.utc_kickoff, utc=True)
            ids = (int(row.home_id), int(row.away_id))
            hh = h2h[h2h.match_id == mid].dropna(subset=["utc", "home_goals", "away_goals"])
            hh = hh[pd.to_datetime(hh.utc, utc=True) < kick].sort_values("utc",
                                                                        ascending=False).head(60)
            hh = hh[hh.home_id.isin(ids) & hh.away_id.isin(ids)]
            checks += 1
            n_h2h += 1
            if int(m.group(1)) != len(hh):
                fails.append(f"{pg.name}: {m.group(1)} precedenti in pagina vs {len(hh)} in archivio")
    for lg_page in ("index.html", "prossime.html"):
        path = site / lg_page
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        # la regex non deve morire in silenzio una seconda volta: aggancia tutte le chip
        checks += 1
        trovat = inf_re.findall(html)
        if len(trovat) != html.count("fact-absence"):
            fails.append(f"{lg_page}: regex indisponibili aggancia {len(trovat)} chip su "
                         f"{html.count('fact-absence')} nella marcatura")
        for mid, n1, c1, n2, c2 in trovat:
            if int(mid) not in fx_by_id.index:
                continue
            row = fx_by_id.loc[int(mid)]
            checks += 1
            n_list += 1
            n1, n2 = html_unescape(n1), html_unescape(n2)   # M'gladbach → M&#39;gladbach in HTML
            if (n1.strip(), int(c1)) != (str(row.home_name).strip(),
                                         un_count.get((int(mid), int(row.home_id)), 0)) or \
               (n2.strip(), int(c2)) != (str(row.away_name).strip(),
                                         un_count.get((int(mid), int(row.away_id)), 0)):
                fails.append(f"{lg_page}: chip indisponibili {n1} {c1} / {n2} {c2} != distinta")
    print(f"[5] schede oggi: {n_role} ruoli, {n_abs} indisponibili, {n_h2h} archivi precedenti, "
          f"{n_list} chip nelle liste")

    # 6) post-partita: assist della cronaca e split primo/secondo tempo contro le tabelle
    events, team_stats = st.read("events"), st.read("team_stats")
    n_assist = n_half = 0
    if not events.empty:
        goals = events[events.type == "Goal"]
        # nome dalla distinta DELLA STESSA partita: lo stesso player_id ha grafie diverse
        # fra le giornate (Uriel/Uriël van Aalst, Josko/Joško Gvardiol) e il sito usa quella
        # della partita, quindi il confronto va fatto sulla stessa base
        same_match: dict[tuple[int, int], str] = {}
        if not lineup.empty:
            same_match = {(int(a), int(b)): str(c) for a, b, c in
                          lineup.dropna(subset=["player_id", "player_name"])
                          [["match_id", "player_id", "player_name"]].itertuples(index=False)}
        names_by_match: dict[int, set[tuple[str, str]]] = {}
        for r in goals.itertuples(index=False):
            aid = getattr(r, "assist_player_id", None)
            if aid is None or pd.isna(aid):
                continue
            nm = same_match.get((int(r.match_id), int(aid))) or hist_name.get(int(aid))
            if nm:
                names_by_match.setdefault(int(r.match_id), set()).add((str(r.player_name), str(nm)))
        assist_re = re.compile(r"\u26bd <b>([^<]+)</b>.*?assist di ([^<]+)</span>")
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Cronaca essenziale" not in html:
                continue
            pairs = names_by_match.get(int(pg.stem), set())
            for scorer, helper in assist_re.findall(html):
                checks += 1
                n_assist += 1
                if (html_unescape(scorer), html_unescape(helper)) not in pairs:
                    fails.append(f"{pg.name}: assist \u00ab{helper}\u00bb a {scorer} non negli eventi")
    if not team_stats.empty:
        # tra le celle può esserci un a capo (il template va a capo dentro la riga)
        half_re = re.compile(r'<td class="c mut small">xG</td>\s*<td class="r">([^<]*)</td>\s*'
                             r'<td>([^<]*)</td>\s*<td class="r">([^<]*)</td>\s*<td>([^<]*)</td>')
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Primo e secondo tempo" not in html or int(pg.stem) not in fx_by_id.index:
                continue
            m = half_re.search(html)
            if not m:
                fails.append(f"{pg.name}: tabella 1T/2T senza riga xG")
                continue
            row = fx_by_id.loc[int(pg.stem)]
            want = []
            for period in ("FirstHalf", "SecondHalf"):
                ts = team_stats[(team_stats.match_id == int(pg.stem)) & (team_stats.period == period)
                                & (team_stats.key == "expected_goals")]
                for tid in (int(row.home_id), int(row.away_id)):
                    cell = ts[ts.team_id == tid]
                    want.append("" if cell.empty else str(cell.iloc[0].text).replace(".", ","))
            got = [html_unescape(x) for x in m.groups()]
            checks += 1
            n_half += 1
            if got != want:
                fails.append(f"{pg.name}: xG 1T/2T {got} vs {want} da team_stats")
    print(f"[6] post-partita: {n_assist} assist, {n_half} split 1T/2T")

    # 9) distribuzione dei gol totali + dotplot quantile: ricalcolate dalla λ/ρ salvate
    from fda.site.advanced import goals_view, probability_steps

    n_goals = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="gol-totali"' not in html:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: distribuzione gol senza previsione")
            continue
        r = preds.loc[mid]
        gv = goals_view(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        barre = re.findall(r'<div class="gb([^"]*)"><span class="v">(\d+)</span>'
                           r'<span class="fill" style="height:([\d.]+)%"></span>'
                           r'<span class="x">([^<]+)</span></div>', html)
        checks += 1
        n_goals += 1
        if len(barre) != len(gv["bars"]):
            fails.append(f"{pg.name}: barre gol {len(barre)} (attese {len(gv['bars'])})")
            continue
        somma = 0
        for (_cls, v_txt, h_txt, x_txt), b in zip(barre, gv["bars"]):
            somma += int(v_txt)
            checks += 1
            if int(v_txt) != b["per100"]:
                fails.append(f"{pg.name}: barra {x_txt} gol = {v_txt} su 100, ricalcolato {b['per100']}")
            if x_txt != b["label"]:
                fails.append(f"{pg.name}: etichetta barra {x_txt} != {b['label']}")
            # [11b] altezza: entro il contenitore e proporzionale alla probabilità ricalcolata.
            # La scala deve includere la barra della coda, altrimenti «7+» straborda (183%).
            altezza = float(h_txt)
            if altezza > 100.0:
                fails.append(f"{pg.name}: barra {x_txt} gol alta {altezza:g}% — esce dal contenitore")
            elif altezza != round(b["h"] * 100):
                fails.append(f"{pg.name}: barra {x_txt} gol alta {altezza:g}%, ricalcolato {round(b['h'] * 100)}%")
        if somma != 100:
            fails.append(f"{pg.name}: le barre dei gol sommano {somma} su 100")
        if max(b["h"] for b in gv["bars"]) != 1.0:
            fails.append(f"{pg.name}: nessuna barra dei gol occupa il 100% della scala "
                         f"(massimo {max(b['h'] for b in gv['bars']):g})")
        # didascalia: moda, mediana, intervallo 10°-90° con la sua copertura reale, e la coda
        cap = re.search(r"il totale più frequente è\s+<b>(\d+)\s+gol</b>\s*\((\d+) su 100\)", html)
        if not cap or int(cap.group(1)) != gv["moda"] or int(cap.group(2)) != gv["bars"][gv["moda"]]["per100"]:
            fails.append(f"{pg.name}: moda dei gol in didascalia != ricalcolata ({gv['moda']})")
        med = re.search(r"la mediana è\s+(\d+)\s+e fra 10° e 90° percentile il totale resta\s+fra\s+(\d+)\s+e\s+"
                        r"(\d+\+?)\s+gol\s+—\s+cioè nel\s+<b>(\d+,\d)%</b>", html)
        attesi = (gv["mediana"], gv["q10"], gv["q90_label"], gv["copertura"])
        if not med:
            fails.append(f"{pg.name}: didascalia dei gol senza intervallo 10°-90° percentile")
        else:
            checks += 1
            letti = (int(med.group(1)), int(med.group(2)), med.group(3), float(med.group(4).replace(",", ".")))
            if letti != attesi:
                fails.append(f"{pg.name}: mediana/intervallo/copertura in didascalia {letti} != ricalcolati {attesi}")
            if not 80.0 < letti[3] <= 100.0:
                fails.append(f"{pg.name}: copertura {letti[3]}% fuori intervalo per un intervallo 10°-90° (attesa > 80)")
        # \s+ e non uno spazio secco: in HTML il whitespace è collassato, quindi un verificatore
        # che dipende da come va a capo il template segnala un difetto dove non c'è (e ha appena
        # fatto esattamente questo, su 160 pagine, quando la didascalia è stata riformattata)
        coda = re.search(rf"Totale\s+{re.escape(gv['coda_label'])}\s+gol:\s*(\d+,\d)%", html)
        if not coda or abs(float(coda.group(1).replace(",", ".")) - gv["p_coda"] * 100) > 0.06:
            fails.append(f"{pg.name}: coda dei gol in didascalia != ricalcolata ({gv['p_coda']:.4f})")
        # dotplot: i punti sono esattamente n_dots e stanno nelle colonne giuste
        # la cattura si ferma alla chiusura del contenitore (a capo + </div>), non al primo
        # </div></div>: altrimenti l'ultima colonna resta fuori e il confronto salta proprio
        # quella. Difetto rimasto nascosto finché la coda era sempre vuota (0 punti): con la
        # calibrazione a momenti alcune partite hanno punti anche nella colonna «7+».
        dp = re.search(r'<div class="goalgrid dotplot"[^>]*>(.*?)\n\s*</div>', html, re.DOTALL)
        if not dp:
            fails.append(f"{pg.name}: dotplot dei gol non trovato")
        else:
            colonne = re.findall(r'<div class="dp"><div class="stack">((?:<i></i>)*)</div>'
                                 r'<span class="x">([^<]+)</span>', dp.group(1))
            if len(colonne) != len(gv["columns"]):
                fails.append(f"{pg.name}: colonne dotplot {len(colonne)} (attese {len(gv['columns'])})")
            else:
                for (dots, label), col in zip(colonne, gv["columns"]):
                    if dots.count("<i>") != col["n"] or label != col["label"]:
                        fails.append(f"{pg.name}: colonna dotplot {label} = {dots.count('<i>')} punti, "
                                     f"attesi {col['n']} su {col['label']}")
            n_punti = sum(dots.count("<i>") for dots, _ in colonne)
            if n_punti != gv["n_dots"]:
                fails.append(f"{pg.name}: punti dotplot {n_punti} (attesi {gv['n_dots']})")
    print(f"[9] distribuzioni dei gol totali verificate: {n_goals}")

    # 10) scomposizione della probabilità: i passi pubblicati sono quelli salvati nella riga
    n_steps = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="scomposizione"' not in html:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: scomposizione senza previsione")
            continue
        r = preds.loc[mid]
        steps = probability_steps(r.to_dict())
        blocco = html.split('id="scomposizione"', 1)[1].split("</ol>", 1)[0]
        resi = re.findall(r'<span class="h" style="width:[^"]*">1 · (\d+,\d)%</span>'
                          r'<span class="d" style="width:[^"]*">X · (\d+,\d)%</span>'
                          r'<span class="a" style="width:[^"]*">2 · (\d+,\d)%</span>', blocco)
        labels = [(n, html_unescape(lab)) for n, lab in
                  re.findall(r"<strong>(\d+) · ([^<]+)</strong>", blocco)]
        checks += 1
        n_steps += 1
        if len(resi) != len(steps) or len(labels) != len(steps):
            fails.append(f"{pg.name}: passi pubblicati {len(resi)}/{len(labels)}, attesi {len(steps)}")
            continue
        # `passo`, non `st`: il nome `st` è lo Store aperto in testa alla funzione e un ciclo
        # che lo ombreggia lo fa diventare un dict, facendo esplodere `st.close()` in fondo
        for (h, x, a), (_n, lab), passo in zip(resi, labels, steps):
            if lab != passo["label"]:
                fails.append(f"{pg.name}: passo «{lab}» != «{passo['label']}»")
            # la terna pubblicata deve essere un arrotondamento legittimo del vettore grezzo
            # (regola del resto massimo, somma esatta al decimo). Prima la si confrontava con
            # `pct_triple` del generatore — stessa funzione che ha prodotto la pagina, quindi lo
            # stesso errore sarebbe passato due volte (`docs/79` §2). Ora si verifica la regola,
            # e le parità (due terne ugualmente legittime) non fanno fallire il gate.
            mostrati = [float(v.replace(",", ".")) for v in (h, x, a)]
            grezzi = (passo["p_home"], passo["p_draw"], passo["p_away"])
            if not terna_valida(grezzi, 1, mostrati):
                fails.append(f"{pg.name}: {passo['label']} pubblica {mostrati} invece di una terna "
                             f"che chiude a 100 al decimo (riferimento {terna_indip(grezzi, 1)})")
        # la catena deve chiudersi sull'1X2 pubblicato in cima alla scheda
        for key in ("p_home", "p_draw", "p_away"):
            if abs(steps[-1][key] - float(r[key])) > 1e-6:
                fails.append(f"{pg.name}: ultimo passo {key} {steps[-1][key]:.4f} != pubblicato {r[key]:.4f}")
        # Δ esatto fra passi adiacenti: deve essere la differenza dei numeri stampati nel
        # riassunto (stesso esito preferito), non dei valori grezzi — il lettore rifà i conti
        delte = re.findall(r'<span class="delta">Δ (-?[+0-9,-]+) pp</span>', blocco)
        if len(delte) != len(steps) - 1:
            fails.append(f"{pg.name}: Δ di catena {len(delte)} per {len(steps)} passi")
        else:
            for i, dtxt in enumerate(delte):
                letto = float(dtxt.replace(",", "."))
                tops = [max(float(v.replace(",", ".")) for v in resi[k]) for k in (i, i + 1)]
                if abs(letto - round(tops[1] - tops[0], 1)) > 1e-9:
                    fails.append(f"{pg.name}: Δ del passo {i + 2} = {dtxt} pp, sono {tops[0]}→{tops[1]}")
    print(f"[10] scomposizioni della probabilità verificate: {n_steps}")

    # 11) titolo della scheda (P2 del modello): il margine pubblicato è la differenza dei due
    #     interi stampati vicini («+25 punti» tra 51% e 26%), e primo/secondo sono davvero
    #     i due esiti più probabili della triade; i λ sono «+», non un trattino
    n_margini = 0
    # «punto|punti», non solo «punti»: con la sola forma plurale le 4 schede con margine 1
    # non corrispondevano e venivano saltate in silenzio (`if not m: continue`), cioè la
    # correzione della concordanza toglieva copertura invece di essere verificata (18/09/2026).
    hero_re = re.compile(r'<strong>([^<]*)<em>(\d+)%</em>.*?'
                         r'\+(\d+(?:,\d+)?) (punti|punto) sul secondo — (.*?) (\d+)%'
                         r' · 1 (\d+)% · X (\d+)% · 2 (\d+)%', re.DOTALL)
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        m = hero_re.search(html)
        if not m:
            continue
        top_v, margine, second_v = int(m.group(2)), float(m.group(3).replace(",", ".")), int(m.group(6))
        pcts = sorted((int(m.group(7)), int(m.group(8)), int(m.group(9))), reverse=True)
        checks += 1
        n_margini += 1
        # la concordanza è ora verificata, non solo tollerata
        attesa = "punto" if int(margine) == 1 else "punti"
        if m.group(4) != attesa:
            fails.append(f"{pg.name}: «+{margine:g} {m.group(4)} sul secondo», voleva «{attesa}»")
        if (top_v - second_v) != int(margine):
            fails.append(f"{pg.name}: margine +{margine:g} punti con {top_v}% e {second_v}% stampati")
        if (top_v, second_v) != (pcts[0], pcts[1]):
            fails.append(f"{pg.name}: primo/secondo {top_v}/{second_v} non sono i due esiti più alti {pcts}")
        if re.search(r"\d,\d+–\d,\d+</b><span>gol attesi", html) or \
                re.search(r"gol attesi \d+[,.]\d+–\d+[,.]\d+", html):
            fails.append(f"{pg.name}: gol attesi separati da trattino (lettura di un intervallo)")
        if not re.search(r"<b>\d+,\d+ \+ \d+,\d+</b><span>gol attesi · <b>\d+,\d+ totali</b>", html):
            fails.append(f"{pg.name}: gol attesi senza il totale esplicito")
        if " totali) · Over" not in html:
            fails.append(f"{pg.name}: descrizione SEO senza il totale dei gol attesi")
    print(f"[11] riassunti del modello verificati: {n_margini}")

    # 12) risultati esatti: la copertura dei sei punteggi è pubblicata e combacia con la
    #     previsione salvata; la gerarchia dei titoli dentro «Verifica approfondita» è h3
    n_cov = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        cm = re.search(r"Questi (\d+) punteggi coprono (\d+,\d+) partite su 100", html)
        if not cm:
            continue
        mid = int(pg.stem)
        if mid not in preds.index:
            fails.append(f"{pg.name}: copertura senza previsione")
            continue
        block = html.split("Risultati esatti più probabili", 1)[1][:2000]
        celle = re.findall(r"<tr><td>\d+-\d+</td><td class=\"r\">(\d+,\d+)%</td></tr>", block)
        somma = sum(float(x.replace(",", ".")) for x in celle)
        letta = float(cm.group(2).replace(",", "."))
        checks += 1
        n_cov += 1
        if abs(somma - letta) > 0.35:
            fails.append(f"{pg.name}: copertura {letta}/100 ma le sei percentuali sommano {somma:.1f}")
        r = preds.loc[mid]
        try:
            raw = ast.literal_eval(r.top_scores) if isinstance(r.top_scores, str) else {}
        except (ValueError, SyntaxError):
            raw = {}
        if raw and abs(sum(raw.values()) * 100 - letta) > 0.06:
            fails.append(f"{pg.name}: copertura {letta}/100 vs {sum(raw.values()) * 100:.1f} dai dati")
        for titolo in ("Matrice dei punteggi", "Quanti gol, in pratica"):
            if f"<h2>{titolo}</h2>" in html:
                fails.append(f"{pg.name}: «{titolo}» è di secondo livello dentro Verifica approfondita")
    print(f"[12] coperture dei risultati esatti verificate: {n_cov}")

    # 15) fascia storica del pronostico: frequenze ricalcolate dalla tabella backtest, stessa
    #     fascia «questa» della scheda, numerità e intervallo di Wilson esatti a 0,1
    bt = st.read("backtest")
    n_fasc = 0
    if not bt.empty and "outcome" in bt.columns:
        from fda.site.analysis import MatchAnalysis

        pv_ = bt[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
        fav_ = pv_.max(axis=1)
        hit_ = pv_.argmax(axis=1) == bt["outcome"].to_numpy()
        tab_bt = []
        for lo_b, hi_b, label_b in MatchAnalysis.FAVORITE_BANDS:
            mm = (fav_ >= lo_b) & (fav_ < hi_b)
            nb = int(mm.sum())
            if nb < 30:
                continue
            kb = int(hit_[mm].sum())
            wl_b, wh_b = wilson_indip(kb, nb)
            tab_bt.append({"label": label_b, "lo": lo_b, "hi": hi_b, "n": nb,
                           "obs": kb / nb, "wl": wl_b, "wh": wh_b, "pm": float(fav_[mm].mean())})
        # La riga della tabella porta anche la colonna P2.3 «previsto → uscito»: la barra è
        # l'intervallo di Wilson, il riempimento la frequenza osservata, la tacca arancione la
        # media prevista. Sono gli stessi tre numeri già stampati nelle celle accanto, ma un
        # grafico può disegnare storto ciò che la tabella dice bene: qui si ricalcola che le
        # posizioni in percentuale corrispondano ai valori pubblicati (tolleranza 0,2 punti,
        # il massimo che l'arrotondamento a un decimale può spostare).
        row_re = re.compile(
            r'<tr[^>]*>\s*<td>(fino al 40%|fra 40% e 50%|fra 50% e 60%|fra 60% e 75%|oltre il 75%)'
            r'(?: (<span class="tag"[^>]*>questa</span>))?</td>'
            r'\s*<td class="r">(\d+(?:\.\d+)?)</td>'
            r'\s*<td class="r">(\d+,\d+)%</td>'
            r'\s*<td class="r"><b>(\d+,\d+)%</b></td>'
            r'\s*<td class="r mut small">(\d+,\d+)–(\d+,\d+)%</td>'
            r'\s*<td class="c"[^>]*><span class="wl"[^>]*>'
            r'<span class="fill" style="width:([\d.]+)%"></span>'
            r'<span class="ic" style="left:([\d.]+)%;width:([\d.]+)%"></span>'
            r'<span class="p" style="left:([\d.]+)%"></span></span></td></tr>')
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if 'id="fascia-storica"' not in html:
                continue
            mid = int(pg.stem)
            if mid not in preds.index:
                fails.append(f"{pg.name}: fascia storica senza previsione")
                continue
            r = preds.loc[mid]
            here = float(max(r.p_home, r.p_draw, r.p_away))
            block = html.split('id="fascia-storica"', 1)[1][:5000]
            got = row_re.findall(block)
            if len(got) != len(tab_bt):
                fails.append(f"{pg.name}: righe fascia storica {len(got)} (attese {len(tab_bt)})")
                continue
            n_fasc += 1
            fav_lbl = re.search(r"fascia di QUESTA partita \(favorito (\d+,\d+)%\)", block)
            checks += 1
            if not fav_lbl or abs(float(fav_lbl.group(1).replace(",", ".")) - here * 100) > 0.06:
                fails.append(f"{pg.name}: favorito dichiarato {fav_lbl.group(1) if fav_lbl else '?'}% != {here * 100:.1f}%")
            for (lab, span, n_t, pm_t, obs_t, lo_t, hi_t,
                 v_fill, v_lo, v_w, v_p), b in zip(got, tab_bt):
                checks += 1
                if lab != b["label"]:
                    fails.append(f"{pg.name}: fascia «{lab}» != «{b['label']}»")
                    continue
                if int(n_t.replace(".", "")) != b["n"]:
                    fails.append(f"{pg.name}: {lab} n={n_t} vs backtest {b['n']}")
                for txt, val, cosa in ((pm_t, b["pm"] * 100, "media prevista"),
                                       (obs_t, b["obs"] * 100, "frequenza osservata"),
                                       (lo_t, b["wl"] * 100, "IC inferiore"),
                                       (hi_t, b["wh"] * 100, "IC superiore")):
                    if abs(float(txt.replace(",", ".")) - val) > 0.06:
                        fails.append(f"{pg.name}: {lab} {cosa} {txt}% vs ricalcolata {val:.1f}%")
                # la colonna grafica: riempimento = osservata, barra = IC, tacca = prevista
                for vis, val, cosa in ((v_fill, b["obs"] * 100, "riempimento"),
                                       (v_lo, b["wl"] * 100, "inizio intervallo"),
                                       (v_w, (b["wh"] - b["wl"]) * 100, "larghezza intervallo"),
                                       (v_p, b["pm"] * 100, "tacca prevista")):
                    checks += 1
                    if abs(float(vis) - round(val, 1)) > 0.2:
                        fails.append(f"{pg.name}: {lab} colonna grafica {cosa} {vis}% "
                                     f"vs ricalcolata {round(val, 1)}%")
                # la marcatura «questa» deve stare sulla fascia del favorito di QUESTA scheda
                cur_page = bool(span)
                cur_data = bool(b["lo"] <= here < b["hi"])
                if cur_page != cur_data:
                    fails.append(f"{pg.name}: marcatura «questa» su {lab} ma il favorito {here:.3f} sta in un'altra fascia")
        print(f"[15] fasce storiche del pronostico verificate: {n_fasc}")

    # 16) percentile dei gol attesi nel campionato: ricalcolato da predictions.parquet pagina
    #     per pagina — il lettore legge una posizione che il conteggio sulle stesse λ conferma
    if not preds.empty and "league_key" in preds.columns:
        from fda.config import leagues as _leagues

        _lg_names = {x.key: x.name for x in _leagues()}
        pr_ = preds.reset_index() if "match_id" not in preds.columns else preds
        p_latest = pr_.sort_values("made_at").groupby("match_id").tail(1).copy()
        p_latest["lam"] = p_latest.lambda_home.astype(float) + p_latest.lambda_away.astype(float)
        n_pos = 0
        pos_re = re.compile(
            r'I (\d+,\d+) gol attesi totali in testa alla scheda vanno letti sulla scala del campionato:\s*'
            r'sono <b>più alti del (\d+)% delle (\d+) partite di ([^<]+) fin qui previste dal nostro modello</b>\s*'
            r'\(media di lega (\d+,\d+), mediana (\d+,\d+)\)')
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if 'id="posizione-lega"' not in html:
                continue
            mid = int(pg.stem)
            row = p_latest[p_latest.match_id == mid]
            m = pos_re.search(html.split('id="posizione-lega"', 1)[1][:2800])
            if row.empty or m is None:
                fails.append(f"{pg.name}: posizione-lega senza previsione o con testo atteso assente")
                continue
            # il valore pubblicato in «Dove si colloca» è la somma dei due λ **stampati** in testa
            # alla scheda: qui si confronta quel numero, non la somma grezza (docs/22 §2)

            lam_here = somma_stampata_indip(float(row.lambda_home.iloc[0]),
                                           float(row.lambda_away.iloc[0]))
            dist = p_latest[p_latest.league_key == row.league_key.iloc[0]]["lam"]
            dist = dist[np.isfinite(dist)]
            n_exp = len(dist)
            checks += 1
            n_pos += 1
            here_t, pct_t, n_t, lg_t, mean_t, med_t = m.groups()
            if here_t != _stamp_it(lam_here):
                fails.append(f"{pg.name}: gol attesi {here_t} vs somma delle λ stampate "
                             f"{_stamp_it(lam_here)}")
            below = float((dist < lam_here).mean())
            if int(pct_t) != pct_dichiarata(below):
                fails.append(f"{pg.name}: percentile {pct_t}% vs ricalcolato {below * 100:.1f}%")
            if int(n_t) != n_exp:
                fails.append(f"{pg.name}: partite di lega {n_t} vs {n_exp} in predictions")
            if lg_t != _lg_names.get(str(row.league_key.iloc[0]), ""):
                fails.append(f"{pg.name}: nome lega «{lg_t}» diverso da config «{_lg_names.get(str(row.league_key.iloc[0]))}»")
            if abs(float(mean_t.replace(",", ".")) - float(dist.mean())) > 0.06:
                fails.append(f"{pg.name}: media di lega {mean_t} vs {dist.mean():.1f}")
            if abs(float(med_t.replace(",", ".")) - float(dist.median())) > 0.06:
                fails.append(f"{pg.name}: mediana di lega {med_t} vs {dist.median():.1f}")
            # P2.3: la barra sotto la frase è la stessa misura disegnata. Il riempimento e il
            # segno devono stare sul percentile già verificato sopra, le tacche sulla mediana e
            # sulla media di lega, gli estremi della scala sul 2° e 98° percentile: un grafico
            # che mostrasse un'altra posizione sarebbe un secondo numero, non un disegno.
            # P2.3: la barra sotto la frase è la stessa misura disegnata. Riempimento e segno
            # stanno sul percentile già verificato sopra, le tacche sulla mediana e sulla media
            # di lega, gli estremi della scala sul 2° e 98° percentile: un grafico che mostrasse
            # un'altra posizione sarebbe un secondo numero, non un disegno.
            viz_re = re.compile(
                r'<div class="track" role="img" aria-label="Gol attesi totali ([\d,]+), più alti del '
                r'(\d+) per cento delle (\d+) partite di ([^"]+) previste dal modello\. '
                r'Scala dal 2° al 98° percentile: da ([\d,]+) a ([\d,]+) gol\. '
                r'Mediana di lega ([\d,]+), media ([\d,]+)">'
                r'\s*<span class="fill" style="width:([\d.]+)%"></span>'
                r'\s*<span class="tick soft" style="left:([\d.]+)%"[^>]*></span>'
                r'\s*<span class="tick" style="left:([\d.]+)%"[^>]*></span>'
                r'\s*<span class="pin" style="left:([\d.]+)%"></span>'
                r'\s*<span class="mark" style="left:([\d.]+)%">([\d,]+)</span>')
            mv = viz_re.search(html.split('id="posizione-lega"', 1)[1][:4200])
            lo_q, hi_q = float(dist.quantile(0.02)), float(dist.quantile(0.98))
            if hi_q - lo_q < 0.2:
                # distribuzione di lega senza spazio: la barra non c'è per scelta (e la card sì)
                checks += 1
                if mv is not None:
                    fails.append(f"{pg.name}: barra della posizione dove la scala non ha spazio")
                continue
            checks += 1
            if mv is None:
                fails.append(f"{pg.name}: barra della posizione di lega assente o diversa (P2.3)")
                continue
            qui = _pos_pct(lam_here, lo_q, hi_q)
            for cosa, letto, atteso in (
                    ("riempimento", float(mv.group(9)), qui),
                    ("segno", float(mv.group(12)), qui),
                    ("etichetta del segno", float(mv.group(13)), qui),
                    ("tacca mediana", float(mv.group(10)),
                     _pos_pct(float(dist.median()), lo_q, hi_q)),
                    ("tacca media", float(mv.group(11)), _pos_pct(float(dist.mean()), lo_q, hi_q)),
                    ("percentile in aria-label", float(mv.group(2)), pct_dichiarata(below))):
                checks += 1
                if abs(letto - atteso) > 0.2:
                    fails.append(f"{pg.name}: barra posizione, {cosa} {letto}% vs ricalcolato {atteso}%")
            checks += 1
            if mv.group(14) != _stamp_it(lam_here):
                fails.append(f"{pg.name}: barra posizione, segno {mv.group(14)} vs λ stampati "
                             f"{_stamp_it(lam_here)}")
            if not _scala_ok(float(mv.group(5).replace(",", ".")), lo_q) or \
                    not _scala_ok(float(mv.group(6).replace(",", ".")), hi_q):
                fails.append(f"{pg.name}: scala della barra {mv.group(5)}–{mv.group(6)} "
                             f"vs 2°–98° percentile {lo_q:.2f}–{hi_q:.2f}")
        print(f"[16] percentile dei gol attesi nel campionato verificato: {n_pos}")

    # 17) primo gol: ritmo a due tempi calibrato su events.parquet — s, quartili in forma chiusa,
    #     P(0-0 all'intervallo) e P(0-0 piena) ricalcolate; «dopo il 90'» mai oltre il fischio
    ev_df = st.read("events")
    if not ev_df.empty and "type" in ev_df.columns and not preds.empty:
        from itertools import pairwise

        import numpy as np

        pr_fg = preds.reset_index() if "match_id" not in preds.columns else preds
        pr_fg = pr_fg.sort_values("made_at").groupby("match_id").tail(1)
        gl = ev_df[ev_df.type == "Goal"]
        if len(gl) >= 60:
            s_fg = float((gl.minute <= 45).mean())
            n_fg = int(ev_df[ev_df.type == "Goal"].match_id.nunique())
            fg_re = re.compile(
                r"su (\d+(?:\.\d+)*) gol nelle\s*(\d+(?:\.\d+)*) partite di questa stagione \(7 leghe\), il "
                r"(\d+,\d)% cade nel 1° tempo", re.DOTALL)
            qq_re = re.compile(
                r"la metà centrale dei primi gol cade fra\s*(dopo il 90'|\d+')\s*e\s*"
                r"(dopo il 90'|\d+')\s*e la mediana è\s*(dopo il 90'|\d+')\. "
                r"Pari senza gol al riposo: <b>(\d+,\d)%</b>;\s*zero gol su novanta minuti: "
                r"(\d+,\d)%\.", re.DOTALL)
            n_q = 0
            for pg in pages:
                html = pg.read_text(encoding="utf-8")
                if 'id="primo-gol"' not in html:
                    continue
                mid = int(pg.stem)
                row_f = pr_fg[pr_fg.match_id == mid]
                checks += 1
                if row_f.empty:
                    fails.append(f"{pg.name}: card primo-gol senza previsione")
                    continue
                lam_fg = float(row_f.lambda_home.iloc[0]) + float(row_f.lambda_away.iloc[0])
                r1_f, r2_f = s_fg * lam_fg / 45.0, (1.0 - s_fg) * lam_fg / 45.0
                s_ht_f = float(np.exp(-r1_f * 45.0))

                # r1_f/r2_f/s_ht_f legati via default: la chiusura è usata nella stessa
                    # iterazione, ma così B023 non segnala il late-binding (ruff, pulizia 18/09)
                def _qexp(p: float, r1_f: float = r1_f, r2_f: float = r2_f,
                          s_ht_f: float = s_ht_f) -> float | None:
                    tail = 1.0 - p
                    t = (-np.log(tail) / r1_f) if tail >= s_ht_f else \
                        (45.0 + (-np.log(tail) - r1_f * 45.0) / r2_f)
                    return None if t > 90.0 else float(t)

                qs = {p: _qexp(p) for p in (0.25, 0.50, 0.75)}
                bl = html.split('id="primo-gol"', 1)[1][:2800]
                m_fg = fg_re.search(bl)
                if not m_fg or int(m_fg.group(1).replace(".", "")) != len(gl) or \
                        int(m_fg.group(2).replace(".", "")) != n_fg or \
                        abs(float(m_fg.group(3).replace(",", ".")) - s_fg * 100) > 0.06:
                    fails.append(f"{pg.name}: conteggi/quota gol di 1° tempo non tornano con events.parquet")
                m_q = qq_re.search(bl)
                if not m_q:
                    fails.append(f"{pg.name}: frase dei quartili del primo gol assente o diversa")
                    continue
                # la frase stampa «fra q1 e q3 e la mediana è q2»: riordino i gruppi
                labels = {0.25: m_q.group(1), 0.75: m_q.group(2), 0.50: m_q.group(3)}
                for p, t in qs.items():
                    atteso = "dopo il 90'" if t is None else f"{round(t)}'"
                    n_q += 1
                    if labels[p] != atteso:
                        fails.append(f"{pg.name}: quartile p={p} primo gol «{labels[p]}» vs modello «{atteso}»")
                if abs(float(m_q.group(4).replace(",", ".")) - s_ht_f * 100) > 0.06:
                    fails.append(f"{pg.name}: P(0-0 riposo) {m_q.group(4)}% vs {s_ht_f * 100:.1f}%")
                if abs(float(m_q.group(5).replace(",", ".")) - np.exp(-lam_fg) * 100) > 0.06:
                    fails.append(f"{pg.name}: P(0-0 piena) {m_q.group(5)}% vs {np.exp(-lam_fg) * 100:.1f}%")

                # P2.3: le due righe del grafico. Sopra la distribuzione OSSERVATA dei primi gol
                # (quarti d'ora, ricavata dagli stessi eventi: primo gol di ogni partita, minuto
                # 1 se il primo gol è segnato in avvio, partite senza gol escluse), sotto la banda
                # del modello per questa partita sulle stesse posizioni 0–90 dell'asse. I
                # conteggi sono ricontati qui: se la pagina mostra una distribuzione che gli
                # eventi non confermano, il gate morde.
                vizio_re = re.compile(
                    r'<div class="goalclock" role="img" aria-label="Distribuzione osservata del primo gol '
                    r'nella stagione: ([^"]+)">\s*'
                    r'(.*?</div>)\s*</div>')
                band_re = re.compile(
                    r'<div class="bandbar" role="img" aria-label="([^"]+)">\s*'
                    r'<span class="band" style="left:([\d.]+)%;width:([\d.]+)%"></span>\s*'
                    r'<span class="med" style="left:([\d.]+)%"></span>')
                primo = gl.dropna(subset=["minute"]).groupby("match_id").minute.min().clip(lower=1)
                n_primo = len(primo)
                confini = (0, 15, 30, 45, 60, 75, 10_000)
                conteggi = [int(((primo > a) & (primo <= b)).sum())
                            for a, b in pairwise(confini)]
                massimo = max(conteggi) or 1
                etichette = ("1–15'", "16–30'", "31–45'", "46–60'", "61–75'", "76–90'")
                attesi_barre = [(lab, round(100.0 * c / n_primo), round(100.0 * c / massimo))
                                for lab, c in zip(etichette, conteggi)]
                bl2 = html_unescape(html).split('id="primo-gol"', 1)[1][:6000]
                m_viz = vizio_re.search(bl2)
                m_band = band_re.search(bl2)
                checks += 1
                if m_viz is None or m_band is None:
                    fails.append(f"{pg.name}: grafico del primo gol assente o diverso (P2.3)")
                else:
                    aria = m_viz.group(1)
                    pezzi = re.findall(r"([\d–]+')\s+(\d+) per cento", aria)
                    if [p_[0] for p_ in pezzi] != list(etichette) or \
                            [int(p_[1]) for p_ in pezzi] != [b[1] for b in attesi_barre]:
                        fails.append(f"{pg.name}: percentuali osservate del primo gol diverse dagli "
                                     f"eventi: {pezzi} vs {[b[1] for b in attesi_barre]}")
                    barre = re.findall(r'<span class="v">(\d+)%</span><span class="fill" '
                                       r'style="height:([\d.]+)%"></span><span class="x">([^<]+)</span>',
                                       m_viz.group(2))
                    checks += 1
                    if len(barre) != 6:
                        fails.append(f"{pg.name}: barre del primo gol {len(barre)} invece di 6")
                    else:
                        for (pv, hv, lv), (lab, per100, h) in zip(barre, attesi_barre):
                            if lv != lab or int(pv) != per100 or abs(float(hv) - h) > 0.5:
                                fails.append(f"{pg.name}: barra primo gol {lab}: {pv}%/{hv}% "
                                             f"vs {per100}%/{h}% dagli eventi")
                    # la banda: dalla pagina (0–90) ai minuti del modello, e ritorno
                    # in pagina: inizio banda (25°), mediana (50°), fine banda (75°) — stesso ordine
                    bl_atteso = [100.0 if qs[k] is None else round(min(100.0, 100.0 * qs[k] / 90.0), 2)
                                 for k in (0.25, 0.50, 0.75)]
                    letto = [float(m_band.group(2)), float(m_band.group(4)),
                             float(m_band.group(2)) + float(m_band.group(3))]
                    checks += 1
                    for nome, a, b_ in zip(("inizio banda", "mediana", "fine banda"), letto, bl_atteso):
                        if abs(a - b_) > 0.2:
                            fails.append(f"{pg.name}: banda primo gol, {nome} {a}% vs modello {b_}%")
                    for lab, t in zip(("25°", "50°", "75°"), (qs[0.25], qs[0.50], qs[0.75])):
                        atteso_txt = "dopo il 90'" if t is None else f"{round(t)}'"
                        if atteso_txt not in m_band.group(1):
                            fails.append(f"{pg.name}: aria-label della banda senza il quartile "
                                         f"{lab} «{atteso_txt}»")
            print(f"[17] quartili del primo gol verificati: {n_q}")

    # 13) nessun numero di verifica inventato nei template: se cambia il metodo il numero è falso
    tpl = Path(__file__).resolve().parents[1] / "src" / "fda" / "site" / "templates"
    n_tpl = 0
    if tpl.is_dir():
        for f in tpl.rglob("*.html"):
            testo = f.read_text(encoding="utf-8")
            n_tpl += 1
            if re.search(r"controlla \d[\d.]+ numeri", testo):
                fails.append(f"template {f.name}: conteggio dei controlli scritto a mano")

    # 14) n_train e compagni grandi con il separatore delle migliaia (esclusi gli anni 19xx/20xx).
    #     Su **tutto** il sito e non solo su `partite/` (docs/40 §7a): `accuratezza.html`
    #     pubblicava «5836 partite» senza separatore e questo controllo non la leggeva. Il
    #     sostantivo «gol» è entrato nella lista con `docs/41`: «su 1014 gol nelle 303 partite»
    #     stava su 164 schede e la vecchia regex, che cercava solo partite/gare, non lo vedeva.
    #     «stagioni» entra con `docs/45` §3: la pagina Proiezioni pubblicava «10000 stagioni
    #     simulate» (grezzo) e nessun controllo lo leggeva; un test lo perfino difendeva.
    n_ntrain = 0
    no_year = r"\b(?!19\d\d|20\d\d)(\d{4,})\s*(?:partite|gare|gol|stagioni)\b"
    for pg in sorted(site.rglob("*.html")):
        html = pg.read_text(encoding="utf-8")
        male = re.search(no_year, re.sub(r"<[^>]+>", " ", html))
        if male:
            fails.append(f"{pg.relative_to(site)}: «{male.group(1)} "
                         "partite/gare/gol/stagioni» senza separatore delle migliaia")
        else:
            n_ntrain += 1
    print(f"[13-14] template e formattazione anti-falso: {n_tpl} template, {n_ntrain} pagine")

    # 18) etichetta della colonna «impatto» dell'infermeria onesta e senza doppio significato
    # (docs/21 Q1): «fuori rosa» è SOLO il motivo FotMob «not in squad», mai l'assenza di
    # statistiche di stagione, che si scrive «senza minuti in stagione · n.d.» con tooltip.
    n_imp = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "senza minuti in stagione · n.d." in html or "fuori rosa · n.d." in html:
            n_imp += 1
            if "fuori rosa · n.d." in html:
                fails.append(f"{pg.name}: etichetta impatto fuorviante «fuori rosa · n.d.»")
            if "non ha ancora minuti nelle statistiche di stagione" not in html:
                fails.append(f"{pg.name}: etichetta «senza minuti in stagione» senza tooltip esplicativo")
    print(f"[18] etichette impatto infermeria verificate: {n_imp} pagine")

    # 19) panchina e posta in gioco (docs/21 P0-1): coach, subentro, rendimento, distanze di
    # classifica e posizione virtuale ricalcolati dai Parquet **senza** passare da
    # ``bench_deep``. Il gate che riusa la funzione del generatore non può vedere gli errori
    # che stanno *dentro* la funzione: la posizione virtuale che dimenticava i punti
    # dell'avversaria è passata [19] per 36 celle su 208 fino al 2026-10-11 (docs/78 §1).
    from fda.config import leagues as _leagues19
    from fda.config import load_leagues_config
    from fda.models.season_sim import mc_percent_str
    from fda.teams import canonical as _canon
    fx19 = st.read("fixtures")
    lu19 = st.read("lineup")
    ps19 = st.read("player_stats")
    ev19 = st.read("events")
    # il sito giudica la lingua su titolo + estratto: qui l'estratto si rilegge dal
    # Parquet, altrimenti il controllo darebbe «non italiano» su titoli italiani brevi
    nd19 = st.read("news")
    desc19 = ({str(x): str(y or "") for x, y in zip(nd19.title, nd19.description)}
              if not nd19.empty and "description" in nd19.columns else {})
    sim19 = st.read("season_sim")
    fm19 = st.read("fotmob_standings")
    mi19 = st.read("match_info")
    from fda.site.analysis import MatchAnalysis as _MA
    from fda.sources.news import JUNK_NEWS, is_italian_news, news_value
    ma19 = _MA(st)
    _lg19 = {lg.fotmob_id: lg.key for lg in _leagues19()}
    _ucl19 = {lg.key: lg.ucl_spots for lg in _leagues19()}
    n_bench = 0
    if not fx19.empty and not lu19.empty and "role" in lu19.columns:
        ko19 = fx19.drop_duplicates("match_id").set_index("match_id")["utc_kickoff"]
        co19 = lu19[(lu19.role == "coach") & (lu19.match_id.isin(ko19.index))].copy()
        if not co19.empty:
            co19["ko"] = pd.to_datetime(co19.match_id.map(ko19), utc=True)
            co19 = co19.sort_values("ko", kind="stable")
        sim19map = {}
        if not sim19.empty:
            for r in sim19.itertuples(index=False):
                sim19map.setdefault(_canon(r.team), r)
        # La pagina Proiezioni è il **secondo** posto dove vanno a schermo gli stessi numeri:
        # se una delle due pagine cambia arrotondamento o formattazione le due divergono senza
        # che nessuna delle due sbagli il conto (successo il 2026-10-11 con `round()`: 4 numeri
        # diversi, `docs/78` §12). Qui non si ricalcola niente: si legge la pagina resa e si
        # confronta con la cella della scheda, così l'oracolo non ripete l'espressione del
        # generatore (che è come sono passati inosservati i 4 numeri).
        proiez19: dict[str, dict[str, str | None]] = {}
        pg_stag19 = site / "stagione.html"
        if pg_stag19.is_file():
            for nome_pg, corpo_pg in re.findall(
                    r"<tr><td>([^<]+)(?:<span[^>]*>[^<]*</span>)?</td>(.*?)</tr>",
                    pg_stag19.read_text(encoding="utf-8"), re.DOTALL):
                celle_pg = [html_unescape(x).strip() for x in
                            re.findall(r'<td class="r">(.*?)</td>', corpo_pg, re.DOTALL)]
                # PG, Pt, Pt attesi, Media pos., 1° [, UCL (prime N)] , Retro
                if len(celle_pg) < 6:
                    continue
                proiez19.setdefault(_canon(nome_pg.strip()), {
                    "ep": celle_pg[2], "pm": celle_pg[3], "titolo": celle_pg[4],
                    "ucl": celle_pg[5] if len(celle_pg) >= 7 else None,
                    "retro": celle_pg[-1]})
        fin19 = fx19[fx19.status == "finished"].copy() if not fx19.empty else fx19
        if not fin19.empty:
            fin19["ko"] = pd.to_datetime(fin19.utc_kickoff, utc=True)
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Analisi pre-partita" not in html:
                continue
            mid = int(pg.stem)
            if mid not in ko19.index:
                continue
            fr = fx19[fx19.match_id == mid].iloc[0]
            kickoff = pd.Timestamp(fr.utc_kickoff)
            txt = html_unescape(html)   # le etichette con apostrofo arrivano escaped (&#39;)
            # docs/78 §8: se il calendario dà la gara finita, la scheda non può restare
            # «Analisi pre-partita» solo perché i dettagli sono un'istantanea vecchia.
            # Nella build del 2026-10-11 succedeva su 22 schede, e la card contava la
            # partita stessa fra i «precedenti».
            checks += 1
            if str(fr.status) == "finished" and 'id="panchina"' in html:
                fails.append(f"{pg.name}: scheda pre-partita per una gara che il calendario "
                             f"dà finita")
            atteso = False
            # dall'HTML grezzo, non da `txt`: l'unescape prima dei tag mangerebbe «&lt;1»
            card19 = PANCHINA_CARD.search(html)
            righe19 = {}
            if card19:
                for nome_riga, corpo in PANCHINA_ROW.findall(card19.group(1)):
                    celle = PANCHINA_TD.findall(corpo)
                    if len(celle) == 2:
                        righe19[nome_riga] = [panchina_cella(c) for c in celle]
            for lato, (tid, tname, oid, oname) in enumerate((
                    (int(fr.home_id), str(fr.home_name), int(fr.away_id), str(fr.away_name)),
                    (int(fr.away_id), str(fr.away_name), int(fr.home_id), str(fr.home_name)))):
                ct = co19[(co19.team_id == tid) & (co19.ko <= kickoff)] if not co19.empty else co19
                coach = None
                if not ct.empty:
                    last = ct.iloc[-1]
                    cur = last.player_id
                    streak, prev = 0, None
                    for pid, nm in zip(ct.player_id.iloc[::-1], ct.player_name.iloc[::-1]):
                        if pid == cur:
                            streak += 1
                        else:
                            prev = nm
                            break
                    coach = (str(last.player_name), prev, streak)
                sr = sim19map.get(_canon(str(tname)))
                if coach or sr is not None:
                    atteso = True
                if 'id="panchina"' not in html:
                    continue
                # --- allenatore: nome, permanenza, rendimento (ricalcolo indipendente) ---
                # Le righe della cella si leggono dal testo della cella (i valori utili stanno
                # dentro <b>, quindi cercarli nell'HTML grezzo li troverebbe spezzati dai tag).
                cella_all = (righe19.get("Allenatore") or ["", ""])[lato]
                if coach:
                    checks += 1
                    if coach[0] not in txt:
                        fails.append(f"{pg.name}: panchina senza il coach {coach[0]} dei Parquet")
                    # docs/78 §5: la nazione si stampa col nome italiano; un codice ISO grezzo
                    # («· 45 anni · ROU») significa che la mappa `_COUNTRY_IT` è rimasta indietro
                    checks += 1
                    if re.search(r"anni · [A-Z]{3}\b", cella_all):
                        fails.append(f"{pg.name}: nazione in codice grezzo nella cella "
                                     f"allenatore ({tname}): {cella_all[:60]}")
                    # la permanenza dichiara anche da quando (docs/78 §12): la data viene
                    # dalla prima gara in archivio del coach corrente, o dall'ultima del
                    # predecessore — ricalcolate qui dalle distinte
                    from zoneinfo import ZoneInfo as _ZI19
                    _tz19 = _ZI19(load_leagues_config().get("timezone_display", "Europe/Rome"))
                    cur19p = ct.iloc[-1].player_id if not ct.empty else None
                    dal19 = None
                    if cur19p is not None and not pd.isna(cur19p):
                        if coach[1]:
                            prec19 = ct[ct.player_id != cur19p]
                            if not prec19.empty:
                                dal19 = ggmm_cella(prec19.ko.max(), _tz19)
                        else:
                            same19 = ct[ct.player_id == cur19p]
                            if not same19.empty:
                                dal19 = ggmm_cella(same19.ko.min(), _tz19)
                    stretta = ((f"panchina nuova: {coach[2]}ª gara dal subentro a {coach[1]}"
                                + (f" (dopo la gara del {dal19})" if dal19 else ""))
                               if coach[1] else
                               (f"panchina invariata da {coach[2]} "
                                f"{'gara' if coach[2] == 1 else 'gare'} nel nostro archivio"
                                + (f" (dal {dal19})" if dal19 else "")))
                    checks += 1
                    if stretta not in cella_all:
                        fails.append(f"{pg.name}: riga permanenza ({tname}) «{stretta}» assente")
                    # rendimento: punti/gara nelle gare finite dirette dal coach corrente
                    ids_coach = set(ct.loc[ct.player_id == ct.iloc[-1].player_id, "match_id"]) \
                        if not ct.empty else set()
                    gare_coach = fin19[fin19.match_id.isin(ids_coach) & (fin19.ko <= kickoff)] \
                        if not fin19.empty else fin19
                    checks += 1
                    if len(gare_coach):
                        punti = int(sum(
                            3 if ((r.home_id == tid and r.home_goals > r.away_goals)
                                  or (r.away_id == tid and r.away_goals > r.home_goals))
                            else 1 if r.home_goals == r.away_goals else 0
                            for r in gare_coach.itertuples(index=False)))
                        pg_gara = f"{punti / len(gare_coach):.1f}".replace(".", ",")
                        atteso_ppg = (f"rendimento: {pg_gara} punti/gara su "
                                      f"{len(gare_coach)} "
                                      f"{'gara finita' if len(gare_coach) == 1 else 'gare finite'}")
                    else:
                        atteso_ppg = "rendimento: nessuna gara finita con lui in panchina"
                    if atteso_ppg not in cella_all:
                        fails.append(f"{pg.name}: rendimento panchina ({tname}) «{atteso_ppg}» assente")
                    # gol fatti/subiti a gara nelle stesse partite (docs/78 §12)
                    checks += 1
                    if len(gare_coach):
                        gf19 = sum(int(r.home_goals) if int(r.home_id) == tid
                                   else int(r.away_goals) for r in gare_coach.itertuples(index=False))
                        ga19 = sum(int(r.away_goals) if int(r.home_id) == tid
                                   else int(r.home_goals) for r in gare_coach.itertuples(index=False))
                        atteso_gol = (f"con lui {gf19 / len(gare_coach):.1f}".replace(".", ",")
                                      + " gol fatti e "
                                      + f"{ga19 / len(gare_coach):.1f}".replace(".", ",")
                                      + " subiti a gara")
                        if atteso_gol not in cella_all:
                            fails.append(f"{pg.name}: gol a gara della panchina ({tname}) "
                                         f"«{atteso_gol}» assenti o diversi")
                    else:
                        if "gol fatti e" in cella_all:
                            fails.append(f"{pg.name}: gol a gara ({tname}) senza gare finite")
                    # bilancio dell'**allenatore** con l'avversaria: le sue gare in panchina
                    # (con qualunque club) contro questa squadra, finite, prima di questa
                    # partita (`docs/78` §10). Il bilancio fra i due **club** non deve
                    # comparire sotto il nome dell'allenatore: sta nella card «Precedenti»
                    # (una prima stesura lo pubblicava lì, attribuendolo all'allenatore).
                    checks += 1
                    atteso_c19 = None
                    if coach and not lu19.empty:
                        cur19 = ct.iloc[-1].player_id if not ct.empty else None
                        if cur19 is not None and not pd.isna(cur19):
                            sue19 = lu19[(lu19.role == "coach")
                                         & (lu19.player_id == cur19)]
                            fxi19 = fx19.drop_duplicates("match_id").set_index("match_id") \
                                if not fx19.empty else fx19
                            n_a = w_a = d_a = l_a = 0
                            for r in sue19.itertuples(index=False):
                                if (r.match_id not in fxi19.index or pd.isna(r.team_id)
                                        or pd.isna(r.match_id)):
                                    continue
                                g19 = fxi19.loc[r.match_id]
                                if (str(g19.status) != "finished"
                                        or pd.isna(g19.home_goals) or pd.isna(g19.away_goals)
                                        or pd.Timestamp(g19.utc_kickoff) >= kickoff):
                                    continue
                                casa = int(r.team_id) == int(g19.home_id)
                                if (int(g19.away_id) if casa else int(g19.home_id)) != oid:
                                    continue
                                gf, ga = ((g19.home_goals, g19.away_goals) if casa
                                          else (g19.away_goals, g19.home_goals))
                                n_a += 1
                                if gf > ga:
                                    w_a += 1
                                elif gf == ga:
                                    d_a += 1
                                else:
                                    l_a += 1
                            if n_a:
                                atteso_c19 = (
                                    f"da allenatore contro {oname}: 1 gara nel nostro "
                                    f"archivio ({w_a}V {d_a}N {l_a}P)" if n_a == 1 else
                                    f"da allenatore contro {oname}: {n_a} gare nel nostro "
                                    f"archivio ({w_a}V {d_a}N {l_a}P)")
                    if atteso_c19 is None:
                        if f"da allenatore contro {oname}" in cella_all:
                            fails.append(f"{pg.name}: bilancio allenatore ({tname}) presente "
                                         f"senza gare reali nei Parquet")
                        if f"bilancio con {oname} nel nostro archivio" in cella_all:
                            fails.append(f"{pg.name}: bilancio dei due club attribuito "
                                         f"all'allenatore ({tname})")
                    elif atteso_c19 not in cella_all:
                        fails.append(f"{pg.name}: bilancio allenatore ({tname}) "
                                     f"«{atteso_c19}» assenti o diversi")
                    # incroci in panchina: precedenti tra i due **allenatori** — gare in cui
                    # si sono trovati su panchine opposte, qualsiasi club, prima di questa
                    # (`docs/78` §7). Ricalcolo indipendente dalle distinte del Parquet.
                    checks += 1
                    opp19 = None
                    occ19 = co19[(co19.team_id == oid) & (co19.ko <= kickoff)] if not co19.empty else co19
                    if not occ19.empty:
                        opp19 = occ19.sort_values("ko", kind="stable").iloc[-1]
                    atteso_inc = None
                    if coach and opp19 is not None and not pd.isna(opp19.player_id):
                        cur19 = co19[(co19.team_id == tid) & (co19.ko <= kickoff)] \
                            .sort_values("ko", kind="stable").iloc[-1].player_id
                        if not pd.isna(cur19):
                            lc19 = co19[co19.ko < kickoff]
                            miei19 = lc19[lc19.player_id == cur19]
                            suoi19 = lc19[lc19.player_id == opp19.player_id]
                            mm19 = []
                            for m19 in set(miei19["match_id"]) & set(suoi19["match_id"]):
                                t1 = set(miei19.loc[miei19.match_id == m19, "team_id"])
                                t2 = set(suoi19.loc[suoi19.match_id == m19, "team_id"])
                                if t1 and t2 and not (t1 & t2):
                                    mm19.append(m19)
                            w19i = d19i = l19i = 0
                            if mm19 and not fin19.empty:
                                gg19 = fin19[(fin19.match_id.isin(mm19)) & (fin19.ko < kickoff)]
                                for r in gg19.itertuples(index=False):
                                    tm19 = set(miei19.loc[miei19.match_id == r.match_id,
                                                         "team_id"])
                                    gf19, ga19 = ((r.home_goals, r.away_goals)
                                                  if r.home_id in tm19
                                                  else (r.away_goals, r.home_goals))
                                    if pd.isna(gf19) or pd.isna(ga19):
                                        continue
                                    if gf19 > ga19:
                                        w19i += 1
                                    elif gf19 == ga19:
                                        d19i += 1
                                    else:
                                        l19i += 1
                            n19i = w19i + d19i + l19i
                            if n19i:
                                nome19 = str(opp19.player_name)
                                atteso_inc = (
                                    f"un solo incrocio in panchina con {nome19}: "
                                    f"{w19i}V {d19i}N {l19i}P" if n19i == 1 else
                                    f"incroci in panchina con {nome19}: "
                                    f"{w19i}V {d19i}N {l19i}P su {n19i} gare")
                    if atteso_inc is None:
                        if "incrocio in panchina con" in cella_all \
                                or "incroci in panchina con" in cella_all:
                            fails.append(f"{pg.name}: incroci in panchina ({tname}) presenti "
                                         f"senza un precedente reale nei Parquet")
                    elif atteso_inc not in cella_all:
                        fails.append(f"{pg.name}: incroci in panchina ({tname}) "
                                     f"«{atteso_inc}» assenti o diversi")
                # --- posta in gioco e classifica (ricalcolo indipendente) ---
                cella_st = (righe19.get("Posta in gioco") or ["", ""])[lato]
                if sr is not None:
                    checks += 1
                    raw_top = getattr(sr, "p_top_n", None)
                    if raw_top is None or pd.isna(raw_top):
                        raw_top = getattr(sr, "p_top4", None)
                    raw_n = getattr(sr, "top_n", None)
                    top_n = 4 if raw_n is None or pd.isna(raw_n) else int(raw_n)
                    pt = mc_percent_str(float(sr.p_title))
                    pe = None if raw_top is None or pd.isna(raw_top) else mc_percent_str(float(raw_top))
                    pr = mc_percent_str(float(sr.p_rel))
                    atteso = (f"titolo {pt}% · UCL (prime {top_n}) {pe}%"
                              if pe is not None else f"titolo {pt}%")
                    if atteso not in cella_st or f"retrocessione {pr}%" not in cella_st:
                        fails.append(f"{pg.name}: posta in gioco {tname} non torna coi Parquet")
                    checks += 1
                    if float(sr.p_title) >= 0.15:
                        lab = "corsa al titolo"
                    elif raw_top is not None and not pd.isna(raw_top) and float(raw_top) >= 0.35:
                        lab = "corsa alla Champions"
                    elif float(sr.p_rel) >= 0.35:
                        lab = "lotta salvezza"
                    elif float(sr.p_rel) >= 0.15:
                        lab = "zona salvezza non lontana"
                    else:
                        lab = (f"proiezione: {str(round(float(sr.pos_mean), 1)).replace('.', ',')}"
                               f"º posto in media")
                    if lab not in cella_st:
                        fails.append(f"{pg.name}: etichetta posta in gioco {tname} sbagliata ({lab})")
                    # «stima di fine stagione»: punti attesi (e posizione media quando
                    # l'etichetta non la pubblica già), dai Parquet della simulazione
                    checks += 1
                    _ep19, _pm19 = getattr(sr, "exp_points", None), getattr(sr, "pos_mean", None)
                    if _ep19 is not None and _pm19 is not None and not pd.isna(_ep19) \
                            and not pd.isna(_pm19):
                        _ep_s = f"{float(_ep19):.1f}".replace(".", ",")
                        atteso_st = (f"stima di fine stagione: {_ep_s} punti attesi"
                                     if lab.startswith("proiezione:") else
                                     f"stima di fine stagione: {_ep_s} punti attesi · "
                                     f"{float(_pm19):.1f}".replace(".", ",") + "º posto in media")
                        if atteso_st not in cella_st:
                            fails.append(f"{pg.name}: stima di fine stagione ({tname}) "
                                         f"«{atteso_st}» assente o diversa")
                    # controllo incrociato con la pagina Proiezioni: la posizione media compare
                    # sempre nella cella (nell'etichetta o nella stima), i punti attesi sempre
                    r_pg = proiez19.get(_canon(str(tname)))
                    if r_pg:
                        checks += 1
                        for nome_num, frase_pg in (
                                ("titolo", f"titolo {r_pg['titolo']}"),
                                ("retrocessione", f"retrocessione {r_pg['retro']}"),
                                ("punti attesi",
                                 f"stima di fine stagione: {r_pg['ep']} punti attesi"),
                                ("posizione media", f"{r_pg['pm']}º posto in media")):
                            if frase_pg not in cella_st:
                                fails.append(
                                    f"{pg.name}: {nome_num} di {tname} non torna fra scheda e "
                                    f"pagina Proiezioni (Proiezioni «{frase_pg}»)")
                        if r_pg["ucl"] is not None and "UCL (prime" in cella_st:
                            checks += 1
                            if f"UCL (prime {top_n}) {r_pg['ucl']}" not in cella_st:
                                fails.append(
                                    f"{pg.name}: UCL di {tname} non torna fra scheda e pagina "
                                    f"Proiezioni (Proiezioni «{r_pg['ucl']}%»)")
                code19 = _lg19.get(int(fr.league_id)) if not pd.isna(fr.league_id) else None
                tab19 = (fm19[fm19.league_code == code19].drop_duplicates("team_id")
                         if code19 and not fm19.empty else fm19.iloc[0:0])
                riga19 = tab19[tab19.team_id == tid]
                if not riga19.empty and 'id="panchina"' in html:
                    r19 = riga19.iloc[0]
                    n19 = len(tab19)
                    pts19, gd19, rank19 = int(r19.points), int(r19.goal_diff or 0), int(r19["rank"])
                    by_rank19 = tab19.set_index("rank")
                    releg19 = n19 - 2 if n19 == 20 else n19 - 1
                    pezzi = [f"{rank19}º con {pts19} punt{'o' if pts19 == 1 else 'i'}"]
                    if releg19 in by_rank19.index and rank19 < releg19:
                        marg19 = pts19 - int(by_rank19.loc[releg19, "points"])
                        pezzi.append(
                            f"{marg19} punt{'o' if marg19 == 1 else 'i'} sopra la zona retrocessione"
                            if marg19 > 0 else "a pari punti con la zona retrocessione")
                    elif releg19 - 1 in by_rank19.index:
                        need19 = int(by_rank19.loc[releg19 - 1, "points"]) - pts19
                        pezzi.append(
                            f"{need19} punt{'o' if need19 == 1 else 'i'} dalla salvezza diretta"
                            if need19 > 0 else "in zona salvezza diretta")
                    ucl19 = _ucl19.get(code19) if code19 else None
                    if ucl19 is not None and ucl19 in by_rank19.index:
                        if rank19 <= ucl19:
                            pezzi.append(f"in zona UCL (prime {ucl19})")
                        else:
                            ge19 = int(by_rank19.loc[ucl19, "points"]) - pts19
                            pezzi.append(
                                f"{ge19} punt{'o' if ge19 == 1 else 'i'} dal {ucl19}º posto"
                                if ge19 > 0 else f"a pari punti col {ucl19}º posto")
                    checks += 1
                    atteso_tab = " · ".join(pezzi)
                    if atteso_tab not in txt:
                        fails.append(f"{pg.name}: distanze di classifica ({tname}) «{atteso_tab}» "
                                     f"assenti o diverse")

                    checks += 1
                    atteso_vir = (
                        f"con una vittoria {posizione_virtuale(tab19, tid, oid, pts19, gd19, 3, 0)}º · "
                        f"con un pareggio {posizione_virtuale(tab19, tid, oid, pts19, gd19, 1, 1)}º · "
                        f"con una sconfitta {posizione_virtuale(tab19, tid, oid, pts19, gd19, 0, 3)}º")
                    if atteso_vir not in txt:
                        fails.append(f"{pg.name}: posizione virtuale ({tname}) «{atteso_vir}» "
                                     f"assente o diversa")
                # --- età media titolari: dichiarata quando la distinta non c'è ---
                if not mi19.empty and "home_avg_starter_age" in mi19.columns and card19:
                    col19 = "home_avg_starter_age" if lato == 0 else "away_avg_starter_age"
                    info19 = mi19[mi19.match_id == mid]
                    eta19 = info19.iloc[0].get(col19) if not info19.empty else None
                    titolari19 = len(lu19[(lu19.match_id == mid) & (lu19.team_id == tid)
                                          & (lu19.role == "starter")]) if not lu19.empty else 0
                    checks += 1
                    cella_eta = (righe19.get("Età media titolari") or ["", ""])[lato]
                    if eta19 is not None and not pd.isna(eta19):
                        atteso_eta = f"{round(float(eta19), 1):.1f}".replace(".", ",") + " anni"
                    else:
                        atteso_eta = "n.d." if titolari19 else "distinta non ancora pubblicata"
                    if atteso_eta not in cella_eta:
                        fails.append(f"{pg.name}: età media titolari ({tname}) «{atteso_eta}» "
                                     f"attesa, in pagina «{cella_eta[:60]}»")
            if atteso and 'id="panchina"' not in html:
                fails.append(f"{pg.name}: scheda pre senza sezione panchina pur avendo i dati")
            n_bench += 1
    print(f"[19] panchina e posta in gioco verificate: {n_bench} pagine")

    # 34) badge della forma nell'hero (P2.5, docs/28 §3): la serie di pallini e i punti devono
    # essere quelli del calendario — ultime gare giocate prima del fischio, dal punto di vista
    # della squadra — e la soglia delle 3 gare vale nei due versi: sotto quella soglia il badge
    # non c'è, da lì in su c'è. Il numero è ricalcolato qui dai Parquet, non letto dal template:
    # è il controllo che impedisce a un badge di raccontare una forma che nei dati non esiste
    # (e alla narrativa di ripetere la serie, che è la metà «riduzione» dell'intervento).
    n_form = 0
    if not fx19.empty:
        fx34 = fx19.copy()
        fx34["utc_kickoff"] = pd.to_datetime(fx34.utc_kickoff, utc=True)
        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Analisi pre-partita" not in html:
                continue          # il badge è dell'attesa: a gara finita l'hero racconta la partita
            fr34 = fx34[fx34.match_id == int(pg.stem)]
            if fr34.empty:
                continue
            fr34 = fr34.iloc[0]
            ko34 = pd.Timestamp(fr34.utc_kickoff)
            hero = html_unescape(html.split('class="match-scoreline"', 1)[1]
                                 .split('<div class="hero-model"', 1)[0])
            pallini, attesi = 0, []
            for tid, tname, lato in ((int(fr34.home_id), fr34.home_name, "home"),
                                     (int(fr34.away_id), fr34.away_name, "away")):
                # stesse regole di MatchAnalysis.form: finite, prima del fischio, ultime 5
                g34 = fx34[(fx34.status == "finished") & (fx34.utc_kickoff < ko34)
                           & ((fx34.home_id == tid) | (fx34.away_id == tid))].sort_values("utc_kickoff").tail(5)
                seq, pts = [], 0
                for row in g34.itertuples(index=False):
                    casa = row.home_id == tid
                    gf, ga = (row.home_goals, row.away_goals) if casa else (row.away_goals, row.home_goals)
                    res = "V" if gf > ga else ("N" if gf == ga else "P")
                    seq.append(res)
                    pts += 3 if res == "V" else 1 if res == "N" else 0
                seq = "".join(seq)
                checks += 1
                if len(seq) < 3:
                    if f'>{tname}<span class="form-line"' in hero:
                        fails.append(f"{pg.name}: badge della forma di {tname[:20]} con "
                                     f"{len(seq)} gare (la soglia è 3)")
                    continue
                n_form += 1
                pallini += len(seq)
                punti = f"{pts} punto" if pts == 1 else f"{pts} punti"
                attesi.append(f'<div class="match-hero-team {lato}">{tname}<span class="form-line" '
                              f'aria-label="Forma di {tname}: {seq} nelle ultime {len(seq)} partite, '
                              f'{punti}. V=vittoria, N=pareggio, P=sconfitta"')
                if attesi[-1] not in hero:
                    fails.append(f"{pg.name}: badge della forma di {tname[:20]} assente o diverso "
                                 f"dal calendario ({seq})")
                if f'<span class="fact-value">{pts} pt</span>' not in hero:
                    fails.append(f"{pg.name}: punti del badge di {tname[:20]} diversi dal "
                                 f"ricalcolo ({pts} pt)")
            n_pallini = len(re.findall(r'class="form-dot [VNP]"', hero))
            if attesi and n_pallini != pallini:
                fails.append(f"{pg.name}: pallini del badge {n_pallini} (attesi {pallini})")
    print(f"[34] badge della forma nell'hero verificati: {n_form}")

    # 20) «Vita del club» (docs/24 §3.5): la card pubblica solo fatti dentro la finestra di
    # 7 giorni che possono spostare qualcosa. Conteggi, voci pubblicate, «in riserva» e
    # blocco «Da sapere» sono ricalcolati con le stesse funzioni del build e confrontati col
    # markup: se una regola cambia nel codice e non nella pagina, il controllo fallisce.
    n_news = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="notizie"' not in html or fx19.empty:
            continue
        rows20 = fx19[fx19.match_id == int(pg.stem)]
        if rows20.empty:
            continue
        fr = rows20.iloc[0]
        mid = int(pg.stem)
        kickoff = pd.Timestamp(fr.utc_kickoff)
        n_news += 1
        inizio = html.find('id="notizie"')
        fine = html.find('<div class="card"', inizio + 10)
        card = html[inizio:fine if fine != -1 else len(html)]
        testo_card = html_unescape(card)
        # blocco «Da sapere»: ogni riga derivata dai dati deve essere sulla pagina
        for s in ma19.news_sapere(mid, int(fr.home_id), str(fr.home_name),
                                  int(fr.away_id), str(fr.away_name), kickoff):
            checks += 1
            if s["testo"] not in testo_card:
                fails.append(f"{pg.name}: riga «Da sapere · {s['titolo']}» assente o diversa")
        # 20b) gli stessi fatti ricalcolati con pandas, senza passare dal sito
        # (docs/25 §4): il bilancio casa/trasferta e l'uomo gol sono i due fatti che
        # tengono piena la card quando la stampa italiana non scrive della squadra, e
        # un errore qui si vedrebbe come un dato inventato, non come un buco.
        if not ps19.empty:
            for tid, tname, in_casa in ((int(fr.home_id), str(fr.home_name), True),
                                        (int(fr.away_id), str(fr.away_name), False)):
                checks += 1
                v, p, s, n = record_campo(fx19, tid, in_casa, kickoff)
                if n >= 3:
                    punti = 3 * v + p
                    riga = (f"{tname} {'in casa' if in_casa else 'in trasferta'}: "
                            f"{v} {'vittoria' if v == 1 else 'vittorie'}, "
                            f"{p} {'pareggio' if p == 1 else 'pareggi'} e "
                            f"{s} {'sconfitta' if s == 1 else 'sconfitte'} in "
                            f"{n} {'gara' if n == 1 else 'gare'} "
                            f"({punti} {'punto' if punti == 1 else 'punti'} su {3 * n}, "
                            # virgola italiana, ricostruita qui a mano di proposito: questo è
                            # un ricalcolo INDIPENDENTE (docs/25 §4). Fino al 18/09/2026 qui
                            # c'era lo stesso `:.2f` col punto del sito, cioè verificatore e
                            # generatore concordavano sull'errore e nessuno dei due lo vedeva.
                            f"{punti / n:.2f}".replace(".", ",") + " a gara).")
                    if riga not in testo_card:
                        fails.append(f"{pg.name}: bilancio {'casa' if in_casa else 'trasferta'} "
                                     f"di {tname[:20]} assente o diverso dal ricalcolo")
                checks += 1
                bomber = capocannoniere(ps19, fx19, tid, kickoff)
                if bomber and f"{bomber[0]} ({bomber[1]} " not in testo_card:
                    fails.append(f"{pg.name}: uomo gol di {tname[:20]} assente o diverso "
                                 f"({bomber[0]} · {bomber[1]} gol attesi)")
            # i due fatti «di dettaglio» entrano solo sotto il tetto di 8 righe: se la
            # card non è piena e il dato c'è, la riga deve esserci
            if testo_card.count("Da sapere ·") < 8:
                for tid, tname in ((int(fr.home_id), str(fr.home_name)),
                                   (int(fr.away_id), str(fr.away_name))):
                    checks += 1
                    pi = porta_inviolata(fx19, tid, kickoff)
                    if pi:
                        chiuse, n = pi
                        riga = (f"{tname} non ha ancora subito gol in campionato "
                                f"({n} gare)." if chiuse >= n else
                                f"{tname} ha chiuso la porta in {chiuse} gare su {n}.")
                        if riga not in testo_card:
                            fails.append(f"{pg.name}: porta inviolata di {tname[:20]} "
                                         f"assente o diversa ({chiuse}/{n})")
                    checks += 1
                    gt = gol_tardi(ev19, fx19, tid, kickoff)
                    if gt:
                        tardi, totale = gt
                        riga = (f"{tname} ha subito {tardi} dei {totale} gol dopo il 75' "
                                f"(il {pct_dichiarata(tardi / totale)}% di quelli presi fin qui).")
                        if riga not in testo_card:
                            fails.append(f"{pg.name}: gol nel finale di {tname[:20]} "
                                         f"assenti o diversi ({tardi}/{totale})")
        # `class="imbuto"` (docs/53 §6.2) marca l'intestazione come testo nostro da
        # ricontrollare: il selettore accetta entrambe le forme, con e senza classe.
        blocchi = re.split(r'<p (?:class="[^"]*" )?style="margin:12px 0 6px"><b>', card)[1:]
        if len(blocchi) != 2:
            fails.append(f"{pg.name}: card con {len(blocchi)} colonne invece di 2")
            continue
        visti20: set[str] = set()
        titoli_pagina: list[str] = []
        for blocco in blocchi:
            team_name = html_unescape(blocco.split("</b>", 1)[0])
            if team_name == str(fr.home_name):
                tid, opp = int(fr.home_id), str(fr.away_name)
            elif team_name == str(fr.away_name):
                tid, opp = int(fr.away_id), str(fr.home_name)
            else:
                fails.append(f"{pg.name}: intestazione card di squadra sconosciuta ({team_name[:30]})")
                continue
            co = ma19.coach(tid, kickoff) or {}
            atteso = ma19.team_news(tid, team_name, kickoff,
                                    squad=ma19.match_squad(mid, tid), seen=visti20,
                                    opponent=opp, coach=co.get("name"))
            head = blocco.split("<ul", 1)[0]
            # ogni numero stampato nell'intestazione deve essere quello calcolato
            for etichetta, valore, schema in (
                    ("titoli esaminati", atteso["esaminate"],
                     r"· (\d+) titol[oi] (?:esaminato|esaminati)"),
                    ("pubblicati", atteso["pubblicate"], r"· (\d+) pubblicat[oi]"),
                    ("annunci o logistica", atteso["annunci"], r"· (\d+) annunc"),
                    ("servizio o cronaca", atteso["scartate"], r"· (\d+) servizio o cronaca"),
                    ("altra squadra", atteso["altre"], r"· (\d+) su un'altra squadra"),
                    ("già raccontato da un'altra voce", atteso["doppioni"],
                     r"· (\d+) già raccontat[oi] da un'altra voce"),
                    ("non spostano nulla", atteso["piatti"], r"· (\d+) non (?:sposta|spostano) nulla"),
                    ("oltre il limite", atteso["oltre"], r"· (\d+) oltre il limite"),
                    ("troppo vecchi", atteso["vecchie"], r"· (\d+) troppo vecch")):
                checks += 1
                m = re.search(schema, head)
                stampato = int(m.group(1)) if m else 0
                if stampato != valore:
                    fails.append(f"{pg.name}: «{etichetta}» di {team_name[:20]} stampa "
                                 f"{stampato}, i dati dicono {valore}")
            checks += 1
            m = re.search(r"<b>(\d+) in riserva</b>", head)
            if (int(m.group(1)) if m else 0) != len(atteso["riserva"]):
                fails.append(f"{pg.name}: «in riserva» di {team_name[:20]} non corrisponde "
                             f"ai dati ({len(atteso['riserva'])})")
            stampati = re.findall(r'<a href="(https?://[^"]+)" rel="noopener noreferrer nofollow">'
                                  r'(.*?)</a>', blocco.split("In riserva", 1)[0])
            attesi = [(str(n["url"]), str(n["title"])) for n in atteso["notizie"]]
            checks += 1
            if [(u, html_unescape(t)) for u, t in stampati] != attesi:
                fails.append(f"{pg.name}: voci della card di {team_name[:20]} diverse da "
                             f"quelle calcolate ({len(stampati)} stampate, {len(attesi)} attese)")
                continue
            etichette = [html_unescape(x) for x in
                         re.findall(r'<span class="topic">(.*?)</span>', blocco.split("In riserva", 1)[0])]
            attese_et = [str(n["topic_label"]) for n in atteso["notizie"]]
            checks += 1
            if etichette != attese_et:
                fails.append(f"{pg.name}: categorie della card di {team_name[:20]} diverse "
                             f"da quelle calcolate ({etichette} vs {attese_et})")
            # limite per categoria (max 2): i dati lo garantiscono, la pagina lo rispetta
            checks += 1
            if etichette and max(etichette.count(x) for x in etichette) > atteso["categoria_limite"]:
                fails.append(f"{pg.name}: più di {atteso['categoria_limite']} voci della stessa "
                             f"categoria per {team_name[:20]}")
            # «in riserva»: le voci dichiarate devono essere quelle calcolate
            ris = re.findall(r'In riserva, fuori dai tre per regola: <a href="([^"]+)"',
                             blocco)
            checks += 1
            if ris != [str(n["url"]) for n in atteso["riserva"]]:
                fails.append(f"{pg.name}: riserva di {team_name[:20]} diversa dai dati "
                             f"({len(ris)} stampate, {len(atteso['riserva'])} attese)")
            # finestra e sostanza: nessuna voce fuori dai 7 giorni e nessun annuncio
            checks += 1
            for n in atteso["notizie"]:
                if (kickoff - n["published_at"]) > pd.Timedelta(days=atteso["finestra"]):
                    fails.append(f"{pg.name}: voce di {team_name[:20]} fuori dalla finestra "
                                 f"di {atteso['finestra']} giorni")
            checks += 1
            for _u, t in stampati:
                titolo = html_unescape(t)
                estratto = desc19.get(titolo, "")
                if JUNK_NEWS.search(titolo):
                    fails.append(f"{pg.name}: voce di servizio pubblicata in card "
                                 f"(«{titolo[:60]}»)")
                if news_value(titolo) is not None:
                    fails.append(f"{pg.name}: voce senza sostanza pubblicata in card "
                                 f"(«{titolo[:60]}»)")
                if not is_italian_news(titolo, estratto):
                    fails.append(f"{pg.name}: voce non in lingua italiana pubblicata in card "
                                 f"(«{titolo[:60]}»)")
            if not atteso["notizie"] and atteso["esaminate"]:
                checks += 1
                if "Niente che possa spostare qualcosa" not in testo_card:
                    fails.append(f"{pg.name}: card vuota di {team_name[:20]} senza riga di "
                                 f"trasparenza")
            titoli_pagina.extend(t for _u, t in stampati)
        checks += 1
        if len(titoli_pagina) != len(set(titoli_pagina)):
            fails.append(f"{pg.name}: stesso titolo pubblicato due volte nella pagina")
    print(f"[20] card «Vita del club» riconciliate: {n_news} pagine")

    # 21) stato della squadra (docs/21 P2-6, «Clima del club» fino all'11/10/2026): **oracolo
    # indipendente** dal 2026-10-11 (`docs/81` §5). Il nome è cambiato con `docs/82` §5 — il
    # contenuto (forma, disponibilità, calendario) è quello che la card ha sempre misurato.
    # Fino a ieri il controllo chiamava `club_mood` e si limitava a ritrovare nella pagina
    # le righe che il generatore aveva appena prodotto — uno specchio (`docs/79` §1): non
    # poteva vedere gli errori *dentro* la funzione. Ora ogni riga è ricalcolata dai Parquet
    # con strade diverse: strisce sulla stagione intera di campionato, riposo e congestione da
    # calendario ∪ coppe, xPTS da Understat o dal Poisson sui soli xG FotMob, panchina dalle
    # distinte, infermeria da distinta e statistiche di stagione. Le soglie sono la
    # **specifica dichiarata** nella nota della card: se il generatore le cambia senza
    # aggiornare qui (o viceversa) il gate si accende.
    n_mood = 0
    vuota = ("Nessun segnale anomalo nei dati raccolti: clima normale.")
    mood_fx = fx19.copy()
    if not mood_fx.empty:
        mood_fx["ko"] = pd.to_datetime(mood_fx.utc_kickoff, utc=True, errors="coerce")
        for _c in ("home_goals", "away_goals"):
            mood_fx[_c] = pd.to_numeric(mood_fx.get(_c), errors="coerce")
    mood_cup = st.read("cup_fixtures")
    if not mood_cup.empty:
        mood_cup["ko"] = pd.to_datetime(mood_cup.utc_kickoff, utc=True, errors="coerce")
        for _c in ("home_goals", "away_goals"):
            mood_cup[_c] = pd.to_numeric(mood_cup.get(_c), errors="coerce")
    mood_ev = st.read("events")
    mood_us = st.read("understat_team_matches")
    if not mood_us.empty:
        mood_us["_nome"] = mood_us.team_name.map(_canon)
        mood_us["_data"] = pd.to_datetime(mood_us.date, utc=True, errors="coerce")
    mood_agg = pd.DataFrame()
    if not ps19.empty and "value" in ps19.columns:
        _mps = ps19.assign(num=pd.to_numeric(ps19.value, errors="coerce")).dropna(subset=["num"])
        if not _mps.empty:
            mood_agg = (_mps.groupby(["team_id", "player_name", "key"]).num.sum()
                        .unstack("key").reset_index())

    # la specifica della card, scritta qui come la nota la dichiara al lettore
    _S_LOSS, _S_NOWIN, _S_UNB, _S_DRY = 3, 4, 5, 3
    _S_ASS, _S_START, _S_CONTRIB = 4, 2, 0.5
    _S_REST, _S_CN, _S_CD, _S_SD = 3, 3, 10, 1.133
    _S_PESANTE = 3   # scarto di una sconfitta → «sconfitta pesante»

    def _striscia_uguale(ris: list[str], val: str) -> int:
        n = 0
        for r in reversed(ris):
            if r == val:
                n += 1
            else:
                break
        return n

    def _striscia_fino_a(ris: list[str], diverso: str) -> int:
        n = 0
        for r in reversed(ris):
            if r != diverso:
                n += 1
            else:
                break
        return n

    def _poisson_xpts_indip(lh: float, la: float) -> tuple[float, float]:
        """xPTS attesi dai soli xG (Poisson indipendente, scritto qui dalla definizione)."""
        import math as _math
        def pmf(k: int, lam: float) -> float:
            return _math.exp(-lam) * lam ** k / _math.factorial(k)
        g = range(16)
        p_draw = sum(pmf(k, lh) * pmf(k, la) for k in g)
        p_home = sum(pmf(i, lh) * sum(pmf(j, la) for j in range(i)) for i in g)
        p_away = sum(pmf(j, la) * sum(pmf(i, lh) for i in range(j)) for j in g)
        return 3 * p_home + p_draw, 3 * p_away + p_draw

    def _risultati(righe: Any, tid: int) -> tuple[list[str], list[int]]:
        """Esiti e gol fatti della squadra, in ordine cronologico (dai Parquet grezzi)."""
        ris, gf = [], []
        for r in righe:
            a, b = (r.home_goals, r.away_goals) if int(r.home_id) == tid else (r.away_goals, r.home_goals)
            if pd.isna(a) or pd.isna(b):
                continue
            ris.append("V" if a > b else ("N" if a == b else "P"))
            gf.append(int(a))
        return ris, gf

    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or mood_fx.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        fr = mood_fx[mood_fx.match_id == int(pg.stem)].iloc[0]
        kickoff = pd.Timestamp(fr.ko)
        n_mood += 1
        if 'id="stato-squadra"' not in html:
            fails.append(f"{pg.name}: card «Stato della squadra» assente (deve esserci su ogni "
                         f"scheda pre-partita)")
            continue
        checks += 1
        _blocco = re.search(r'<div class="card" id="stato-squadra">(.*?)(?=<div class="card"|<footer)',
                            html, re.DOTALL)
        parti = re.split(r'<p style="margin:0 0 6px"><b>', _blocco.group(1)) if _blocco else []
        if len(parti) != 3:
            fails.append(f"{pg.name}: struttura della card «Stato della squadra» inattesa "
                         f"({len(parti)} blocchi)")
            continue
        note = html_unescape(parti[2])
        checks += 1
        # la nota dichiara il perimetro delle strisce e il significato dei tre colori (docs/81 §2-§4)
        if "campionato" not in note:
            fails.append(f"{pg.name}: la nota dello stato della squadra non dichiara il "
                         f"perimetro di campionato")
        if not all(x in note for x in ("rosso", "ambra", "verde")):
            fails.append(f"{pg.name}: la nota dello stato della squadra non spiega i toni "
                         f"dei colori")
        senza = 0
        for lato, (tid, tname) in enumerate(((int(fr.home_id), str(fr.home_name)),
                                             (int(fr.away_id), str(fr.away_name)))):
            tid = int(tid)
            righe = [html_unescape(x) for x in
                     re.findall(r'<li class="mood-(?:bad|warn|good)"><span class="small">(.*?)</span></li>',
                                parti[lato + 1], re.DOTALL)]
            if not righe:
                senza += 1
            attese: list[str] = []
            prefissi: list[str] = []
            # --- strisce: stagione intera di campionato ---
            gare = mood_fx[(mood_fx.status == "finished") & (mood_fx.ko < kickoff)
                           & ((mood_fx.home_id == tid) | (mood_fx.away_id == tid))].sort_values("ko")
            ris, gf = _risultati(gare.itertuples(index=False), tid)
            lose, nowin, unbeaten = (_striscia_uguale(ris, "P"), _striscia_fino_a(ris, "V"),
                                     _striscia_fino_a(ris, "P"))
            secco = _striscia_uguale(["1" if x else "0" for x in gf], "0")
            if lose >= _S_LOSS:
                attese.append(f"crisi di risultati: {lose} sconfitte consecutive in campionato")
            elif nowin >= _S_NOWIN:
                nd = sum(1 for r in ris[len(ris) - nowin:] if r == "N")
                attese.append(f"non vince da {nowin} gare in campionato ({nd} N, {nowin - nd} P)")
            elif unbeaten >= _S_UNB:
                attese.append(f"imbattuta da {unbeaten} gare in campionato: clima di fiducia")
            if secco >= _S_DRY:
                attese.append(f"attacco a secco: {secco} gare senza segnare in campionato")
            # --- ultima gara di campionato: sconfitta pesante e espulsione (`docs/81` §9) ---
            _gare = mood_fx[(mood_fx.status == "finished") & (mood_fx.ko < kickoff)
                            & ((mood_fx.home_id == tid) | (mood_fx.away_id == tid))]
            if not _gare.empty:
                _u = _gare.loc[_gare.ko.idxmax()]
                _casa = int(_u.home_id) == tid
                _gf, _ga = ((_u.home_goals, _u.away_goals) if _casa
                            else (_u.away_goals, _u.home_goals))
                if pd.notna(_gf) and pd.notna(_ga) and int(_ga) - int(_gf) >= _S_PESANTE:
                    attese.append(f"sconfitta pesante nell'ultima gara di campionato: "
                                  f"{int(_gf)}-{int(_ga)}")
                    prefissi.append("sconfitta pesante nell'ultima gara di campionato")
                if not mood_ev.empty and {"match_id", "card", "is_home"} <= set(mood_ev.columns):
                    _rossi = mood_ev[(mood_ev.match_id == int(_u.match_id))
                                     & mood_ev.card.astype(str).str.lower().isin(("red", "yellowred"))
                                     & mood_ev.is_home.notna()
                                     & (mood_ev.is_home.astype(bool) == _casa)]
                    if not _rossi.empty:
                        attese.append("espulsione nell'ultima gara di campionato")
                        prefissi.append("espulsione nell'ultima gara di campionato")
            # --- xPTS: Understat alla vigilia; senza Understat il Poisson sui soli xG FotMob ---
            diff = banda = None
            ur = (mood_us[(mood_us._nome == _canon(tname)) & (mood_us._data < kickoff)]
                  if not mood_us.empty else mood_us)
            if not ur.empty and len(ur) >= 3 and {"xpts", "pts"} <= set(ur.columns):
                diff, banda = float(ur.pts.sum()) - float(ur.xpts.sum()), _S_SD * len(ur) ** 0.5
            else:
                fin = mood_fx[(mood_fx.status == "finished") & (mood_fx.ko < kickoff)
                              & ((mood_fx.home_id == tid) | (mood_fx.away_id == tid))]
                info = mi19[mi19.match_id.isin(fin.match_id)] if not mi19.empty else pd.DataFrame()
                _col = {"home_xg", "away_xg", "home_goals", "away_goals"}
                if not info.empty and _col <= set(info.columns):
                    info = info.assign(**{c: pd.to_numeric(info[c], errors="coerce")
                                          for c in _col}).dropna(subset=sorted(_col))
                else:
                    info = pd.DataFrame()
                if len(info) >= 3:
                    totx = totp = 0.0
                    for r in info.itertuples(index=False):
                        casa = int(r.home_id) == tid
                        xp, xpa = _poisson_xpts_indip(float(r.home_xg), float(r.away_xg))
                        totx += xp if casa else xpa
                        hg, ag = int(r.home_goals), int(r.away_goals)
                        signed = hg - ag if casa else ag - hg
                        totp += 3 if signed > 0 else 1 if signed == 0 else 0
                    diff, banda = totp - totx, _S_SD * len(info) ** 0.5
            if diff is not None and banda is not None:
                if diff >= banda:
                    attese.append("rende più di quanto crea (xPTS)")
                elif diff <= -banda:
                    attese.append("raccoglie meno punti di quanto crea (xPTS)")
            # --- panchina nuova: cambio rilevato **e** allenatore in carica da ≤3 gare ---
            co = lu19[(lu19.team_id == tid) & (lu19.role == "coach")] if not lu19.empty else lu19
            if not co.empty:
                # la permanenza è la sequenza **consecutiva** con lo stesso id allenatore
                # (come ``coach()``): il totale delle righe conterebbe anche un ritorno
                co = co[co.match_id.isin(mood_fx.match_id)].copy()
                if not co.empty:
                    co["ko"] = pd.to_datetime(co.match_id.map(
                        mood_fx.drop_duplicates("match_id").set_index("match_id")["ko"]), utc=True)
                    co = co[co.ko <= kickoff].sort_values("ko", kind="stable")
                if not co.empty:
                    cur = co.iloc[-1].player_id
                    subentro = 0
                    for _pid in co.player_id.iloc[::-1]:
                        if _pid == cur:
                            subentro += 1
                        else:
                            break
                    if (co.player_id != cur).any() and subentro <= 3:
                        attese.append("panchina nuova: il cambio di allenatore")
            # --- infermeria: presenza e numero dagli stessi dati; il contributo è quello stampato ---
            unav = (lu19[(lu19.match_id == int(pg.stem)) & (lu19.team_id == tid)
                         & (lu19.role == "unavailable") & lu19.player_id.notna()]
                    if not lu19.empty else lu19)
            n_un = len(unav)
            titolari, contrib_certo = 0, 0.0
            if n_un and not mood_agg.empty:
                st_t = mood_agg[mood_agg.team_id == tid].drop_duplicates("player_name") \
                    .set_index("player_name")
                per_g = float(st_t["minutes_played"].sum()) / 11 if "minutes_played" in st_t else 0.0
                for r in unav.itertuples(index=False):
                    nm = str(r.player_name)
                    if nm not in st_t.index or "minutes_played" not in st_t:
                        continue
                    _mv = st_t.loc[nm, "minutes_played"]
                    mins = 0.0 if pd.isna(_mv) else float(_mv)
                    if per_g and mins >= 0.5 * per_g:
                        titolari += 1
                    if mins >= 90.0:
                        # sopra i 90′ il generatore pubblica il valore grezzo: la somma è
                        # ricalcolabile qui senza la stima stabilizzata (`docs/19` §1.10)
                        _c = 0.0
                        for _k in ("expected_goals", "expected_assists"):
                            if _k in st_t.columns:
                                _v = st_t.loc[nm, _k]
                                _c += 0.0 if pd.isna(_v) else float(_v)
                        contrib_certo += round(_c / (mins / 90.0), 2) if _c else 0.0
            riga_inf = next((x for x in righe if x.startswith(("infermeria pesante", "assenze pesanti"))), None)
            if riga_inf:
                prefissi.append("infermeria pesante" if riga_inf.startswith("infermeria")
                                else "assenze pesanti")
                # «infermeria» solo con i soli infortuni; con uno squalificato «assenze pesanti»
                checks += 1
                _soli_inf = all(str(t).strip().lower() == "injury"
                                for t in unav.unavailability_type.dropna()) if not unav.empty else True
                if _soli_inf and not riga_inf.startswith("infermeria pesante"):
                    fails.append(f"{pg.name}: {tname} assenze etichettate «assenze pesanti» "
                                 f"con soli infortuni")
                if not _soli_inf and riga_inf.startswith("infermeria pesante"):
                    fails.append(f"{pg.name}: {tname} «infermeria pesante» con una squalifica "
                                 f"fra gli indisponibili")
                checks += 1
                mm = re.search(r"≈ ([0-9]+,[0-9]+) xG\+xA a partita in meno", riga_inf)
                pub = float(mm.group(1).replace(",", ".")) if mm else 0.0
                if not (n_un >= _S_ASS or titolari >= _S_START or pub >= _S_CONTRIB):
                    fails.append(f"{pg.name}: {tname} infermeria pubblicata senza soglia "
                                 f"({n_un} assenti, {titolari} titolari, {pub} xG+xA)")
                _nm = re.match(r"(?:infermeria pesante|assenze pesanti): ([0-9]+) assent",
                                 riga_inf)
                if _nm and int(_nm.group(1)) != n_un:
                    fails.append(f"{pg.name}: {tname} infermeria «{riga_inf[:40]}» con {n_un} assenti")
            else:
                checks += 1
                if n_un >= _S_ASS or titolari >= _S_START or contrib_certo >= _S_CONTRIB:
                    fails.append(f"{pg.name}: {tname} infermeria assente con {n_un} assenti, "
                                 f"{titolari} titolari e {contrib_certo} xG+xA pubblicabili")
            # --- riposo e congestione: campionato + coppe ---
            src = (pd.concat([mood_fx, mood_cup], ignore_index=True, sort=False)
                   if not mood_cup.empty else mood_fx)
            prec = src[(src.status == "finished") & (src.ko < kickoff)
                       & ((src.home_id == tid) | (src.away_id == tid))]
            riga_rest = next((x for x in righe if x.startswith("riposo corto")), None)
            riga_cong = next((x for x in righe if x.startswith("congestione")), None)
            if not prec.empty:
                rest = int((kickoff - prec.ko.max()).total_seconds() // 86400)
                checks += 1
                if rest <= _S_REST and riga_rest is None:
                    fails.append(f"{pg.name}: {tname} riposo {rest} giorni senza riga")
                if rest > _S_REST and riga_rest:
                    fails.append(f"{pg.name}: {tname} riga «{riga_rest[:40]}» con riposo {rest} giorni")
            if riga_rest:
                prefissi.append("riposo corto")
            finestra = src[(src.status == "finished") & (src.ko >= kickoff - pd.Timedelta(days=_S_CD))
                           & (src.ko < kickoff) & ((src.home_id == tid) | (src.away_id == tid))]
            checks += 1
            if len(finestra) >= _S_CN and riga_cong is None:
                fails.append(f"{pg.name}: {tname} {len(finestra)} gare in {_S_CD} giorni senza congestione")
            if len(finestra) < _S_CN and riga_cong:
                fails.append(f"{pg.name}: {tname} «{riga_cong[:40]}» con {len(finestra)} gare in {_S_CD} giorni")
            if riga_cong:
                prefissi.append("congestione")
            # --- le due direzioni: nessuna riga inventata, nessuna riga attesa mancante ---
            for atteso in attese:
                checks += 1
                if not any(x.startswith(atteso[:24]) for x in righe):
                    fails.append(f"{pg.name}: {tname} riga clima attesa assente «{atteso[:50]}»")
            for riga in righe:
                checks += 1
                if not any(riga.startswith(a[:24]) for a in attese) and \
                        not any(riga.startswith(p) for p in prefissi):
                    fails.append(f"{pg.name}: {tname} riga clima non giustificata «{riga[:50]}»")
        checks += 1
        if txt.count(vuota) != senza:
            fails.append(f"{pg.name}: {senza} squadre senza segnali ma la riga «clima normale» "
                         f"compare {txt.count(vuota)} volte")
    print(f"[21] pagine con stato della squadra riconciliate: {n_mood} (oracolo indipendente)")

    # 49) clima del club (`docs/82` §5 e §9, opzione A): la card dell'ambiente e delle aspettative
    # e — dall'11/10/2026 — **l'elenco delle voci contate** (richiesta dell'utente: «fornirmi
    # queste voci con esattezza cosa dicono»). Conteggi e voci ricalcolati dai Parquet con la
    # classificazione della fonte (`classify_news`, la stessa di «Vita del club» — il limite
    # dichiarato in `ORACOLI`); rango per valore dei titolari e scarto dalla classifica
    # ricalcolati in modo indipendente (mediane sulle gare finite prima del fischio, soglie
    # 3 gare / |Δ| ≥ 5: la specifica dichiarata nella nota). Una voce per titolo — la stessa
    # chiave di `team_news`: i doppioni della raccolta non gonfiano i conteggi — le più recenti
    # fino al tetto dichiarato, e i marcatori «anche in «Vita del club»» verificati contro i
    # titoli pubblicati **dalla stessa pagina**. Le righe di testo devono corrispondere una a
    # una (in entrambe le direzioni) e il vuoto di raccolta ha una frase fissa che deve
    # comparire **se e solo se** il conteggio è zero.
    n_clima = 0
    if not nd19.empty and not fx19.empty and "title" in nd19.columns:
        from fda.sources.news import TOPIC_LABELS, classify_news, is_italian_news
        _temi49 = ("allenatore", "spogliatoio", "societa", "tifo", "stadio", "fuoricampo")
        _press49 = ("allenatore", "spogliatoio", "societa", "tifo")
        _ord49 = {k: i for i, k in enumerate(_temi49)}
        _max49 = 24              # CLIMA_VOCI_MAX dichiarato nella nota del codice
        _nd49 = nd19.assign(_pa=pd.to_datetime(nd19.published_at, utc=True, errors="coerce"))
        _mi49 = mi19.copy()
        for _c49 in ("home_starters_value_eur", "away_starters_value_eur"):
            if _c49 in _mi49.columns:
                _mi49[_c49] = pd.to_numeric(_mi49[_c49], errors="coerce")
        _vuoto49 = "Nessuna voce di clima raccolta dalla stampa italiana"
        _tl49 = lambda t: re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

        def _attesi49(tid: int, tname: str, ko: Any, pubblicate: set[str],
                      ) -> tuple[list[tuple[str, str]], int, list[dict]]:
            """Righe attese (testo, tono), voci contate e gruppi elencati, dai Parquet grezzi."""
            att: list[tuple[str, str]] = []
            ko = pd.Timestamp(ko)
            sub = _nd49[(_nd49.team_id == tid) & (_nd49._pa >= ko - pd.Timedelta(days=7))
                        & (_nd49._pa <= ko)].dropna(subset=["_pa"])
            voci_righe: list[dict] = []
            viste: set[str] = set()
            for r in sub.sort_values("_pa", ascending=False, kind="stable").itertuples(index=False):
                titolo = str(getattr(r, "title", "") or "").strip()
                if not titolo:
                    continue
                desc = getattr(r, "description", None)
                desc = "" if desc is None or pd.isna(desc) else str(desc)
                if not is_italian_news(titolo, desc):
                    continue
                chiave, _prova = classify_news(titolo, desc, getattr(r, "source", None))
                if chiave not in _temi49:
                    continue
                tk = _tl49(titolo)
                if not tk or tk in viste:
                    continue
                viste.add(tk)
                voci_righe.append({"key": chiave, "title": titolo,
                                   "url": str(getattr(r, "url", "") or ""),
                                   "in_vita": tk in pubblicate})
            conta: Counter[str] = Counter(v["key"] for v in voci_righe)
            voci = len(voci_righe)
            pressione = sum(conta[k] for k in _press49)
            temi = sorted(conta, key=lambda k: (-conta[k], _ord49[k]))

            def det(chiavi: list[str]) -> str:
                return " · ".join(f"{TOPIC_LABELS.get(k, k).lower()} {conta[k]}" for k in chiavi)

            det_press = det([k for k in temi if k in _press49])
            if pressione >= 3:
                _t49 = (f"settimana calda: {pressione} voci di pressione in 7 giorni "
                        f"({det_press})")
                att.append((_t49, "bad"))
            elif pressione:
                _t49 = (f"pressione in settimana: {pressione} "
                        f"{'voce' if pressione == 1 else 'voci'} ({det_press})")
                att.append((_t49, "warn"))
            elif voci:
                _t49 = (f"settimana tranquilla: {voci} "
                        f"{'voce' if voci == 1 else 'voci'}, nessuna di pressione ({det(temi)})")
                att.append((_t49, "good"))
            # pressione da aspettative: rango per valore dei titolari (mediana, minimo 3 gare)
            # contro la posizione in classifica dello snapshot raccolto
            st49 = None
            if not fm19.empty and "team_name" in fm19.columns:
                righe_st = fm19[fm19.team_name.map(_canon) == _canon(tname)]
                st49 = righe_st.iloc[0] if not righe_st.empty else None
            if st49 is not None and not _mi49.empty and pd.notna(st49.get("rank")):
                fin49 = fx19[(fx19.status == "finished") & (fx19.utc_kickoff < ko)]
                info49 = _mi49[_mi49.match_id.isin({int(x) for x in fin49.match_id})]
                valori: dict[int, list[float]] = {}
                for r in info49.itertuples(index=False):
                    for _tid, _col in ((int(r.home_id), "home_starters_value_eur"),
                                       (int(r.away_id), "away_starters_value_eur")):
                        v = getattr(r, _col, None)
                        if v is None or pd.isna(v) or float(v) <= 0:
                            continue
                        valori.setdefault(_tid, []).append(float(v))
                medie = {t: float(pd.Series(v).median()) for t, v in valori.items() if len(v) >= 3}
                lega = fm19[fm19.league_code == st49["league_code"]].drop_duplicates("team_id")
                in_lega = sorted({int(t) for t in lega.team_id} & set(medie))
                if tid in medie and len(in_lega) >= 8:
                    rango = sorted(in_lega, key=lambda t: (-medie[t], t)).index(tid) + 1
                    pos = int(st49["rank"])
                    if pos - rango >= 5:
                        _t49 = (f"pressione da aspettative: rosa da {rango}ª per valore "
                                f"dei titolari, in classifica {pos}ª")
                        att.append((_t49, "warn"))
                    elif rango - pos >= 5:
                        _t49 = (f"sopra le attese: in classifica {pos}ª con una rosa da "
                                f"{rango}ª per valore dei titolari")
                        att.append((_t49, "good"))
            elencate49 = voci_righe[:_max49]
            per_tema49: dict[str, list[dict]] = {}
            for v in elencate49:
                per_tema49.setdefault(v["key"], []).append(v)
            gruppi = [{"key": k, "label": TOPIC_LABELS.get(k, k), "n": int(conta[k]),
                       "voci": per_tema49.get(k, [])} for k in temi]
            return att, voci, gruppi

        for pg in pages:
            html = pg.read_text(encoding="utf-8")
            if "Analisi pre-partita" not in html or int(pg.stem) not in ko19.index:
                continue
            if 'id="clima"' not in html:
                fails.append(f"{pg.name}: card «Clima del club» assente "
                             f"(deve esserci su ogni scheda pre-partita)")
                continue
            n_clima += 1
            blocco49 = re.search(r'<div class="card" id="clima">(.*?)(?=<div class="card"|<footer)',
                                 html, re.DOTALL)
            parti49 = (re.split(r'<p style="margin:0 0 6px"><b>', blocco49.group(1))
                       if blocco49 else [])
            checks += 1
            if len(parti49) != 3:
                fails.append(f"{pg.name}: struttura della card «Clima del club» inattesa "
                             f"({len(parti49)} blocchi)")
                continue
            nota49 = html_unescape(blocco49.group(1))
            for frammento in ("7 giorni", "5 posizioni", "valore dei titolari", "stampa",
                              "l'elenco delle voci contate", "24 voci elencate"):
                checks += 1
                if frammento not in nota49:
                    fails.append(f"{pg.name}: la nota del clima non dichiara «{frammento}»")
            # i titoli pubblicati in «Vita del club» sulla stessa pagina (per i marcatori)
            _in49 = html.find('id="notizie"')
            _fine49 = html.find('<div class="card"', _in49 + 10) if _in49 != -1 else -1
            blocco_not49 = html[_in49:_fine49 if _fine49 != -1 else len(html)]
            pubblicate49 = {html_unescape(x) for x in re.findall(
                r'<li><span class="topic">.*?<br><a href="[^"]*"[^>]*>(.*?)</a>',
                blocco_not49, re.DOTALL)}
            pubblicate49 = {_tl49(x) for x in pubblicate49 if x}
            fr49 = fx19[fx19.match_id == int(pg.stem)].iloc[0]
            ko49 = pd.Timestamp(fr49.utc_kickoff)
            for parte in parti49[1:]:
                tname49 = html_unescape(parte.split("</b>", 1)[0]).strip()
                tid49 = int(fr49.home_id) if tname49 == str(fr49.home_name) else int(fr49.away_id)
                attesi49, voci49, gruppi = _attesi49(tid49, tname49, ko49, pubblicate49)
                # righe pubblicate: devono corrispondere una a una ai segnali attesi
                righe49 = [(html_unescape(t), tone) for tone, t in
                           re.findall(r'<li class="mood-(bad|warn|good)"><span class="small">'
                                      r'(.*?)</span></li>', parte, re.DOTALL)]
                for testo49, tone49 in attesi49:
                    checks += 1
                    if (testo49, tone49) not in righe49:
                        fails.append(f"{pg.name}: {tname49} riga clima attesa assente "
                                     f"«{testo49[:60]}»")
                for testo49, tone49 in righe49:
                    checks += 1
                    if (testo49, tone49) not in attesi49:
                        fails.append(f"{pg.name}: {tname49} riga clima non giustificata "
                                     f"«{testo49[:60]}»")
                checks += 1
                if (voci49 == 0) != (_vuoto49 in parte):
                    fails.append(f"{pg.name}: {tname49} vuoto dichiarato della stampa "
                                 f"{'assente' if voci49 == 0 else 'presente'} con {voci49} voci")
                # l'elenco delle voci contate: numeri del sommario, gruppi, item, marcatori
                elencate49 = sum(len(g["voci"]) for g in gruppi)
                in_vita49 = sum(1 for g in gruppi for v in g["voci"] if v["in_vita"])
                somm49 = re.search(r'<summary>(.*?)</summary>', parte, re.DOTALL)
                testo_somm49 = html_unescape(somm49.group(1)) if somm49 else ""
                checks += 1
                if (elencate49 > 0) != bool(somm49):
                    fails.append(f"{pg.name}: {tname49} tendina delle voci "
                                 f"{'assente' if elencate49 > 0 else 'presente'} con "
                                 f"{elencate49} voci elencate")
                if somm49:
                    checks += 1
                    atteso_somm49 = (
                        f"Le {elencate49} voci più recenti di {voci49} contate"
                        if voci49 > elencate49
                        else "Una voce contata" if voci49 == 1
                        else f"Le {voci49} voci contate")
                    if atteso_somm49 not in testo_somm49:
                        fails.append(f"{pg.name}: {tname49} sommario delle voci «"
                                     f"{testo_somm49[:60]}» invece di «{atteso_somm49}»")
                    checks += 1
                    if in_vita49:
                        atteso_marc49 = ("già raccontata in «Vita del club»" if voci49 == 1
                                         else "una già raccontata in «Vita del club»"
                                         if in_vita49 == 1
                                         else f"{in_vita49} già raccontate in «Vita del club»")
                        if atteso_marc49 not in testo_somm49:
                            fails.append(f"{pg.name}: {tname49} sommario senza il conteggio dei "
                                         f"marcatori ({in_vita49})")
                gruppi_pagina49 = re.findall(
                    r'<p class="small" style="margin:8px 0 4px"><b>(.*?) \((\d+)\)</b></p>\s*'
                    r'<ul class="news-list">(.*?)</ul>', parte, re.DOTALL)
                checks += 1
                if len(gruppi_pagina49) != len(gruppi):
                    fails.append(f"{pg.name}: {tname49} gruppi di voci {len(gruppi_pagina49)} "
                                 f"in pagina contro {len(gruppi)} attesi")
                else:
                    for (lab49, n49, ul49), att_g49 in zip(gruppi_pagina49, gruppi):
                        checks += 1
                        if html_unescape(lab49) != att_g49["label"] or int(n49) != att_g49["n"]:
                            fails.append(f"{pg.name}: {tname49} gruppo «{lab49} ({n49})» "
                                         f"invece di «{att_g49['label']} ({att_g49['n']})»")
                        items49 = re.findall(
                            r'<li><span class="small"><a href="([^"]+)"[^>]*>(.*?)</a> '
                            r'<span class="mut">(.*?)</span></span></li>', ul49, re.DOTALL)
                        checks += 1
                        if [html_unescape(t) for _u, t, _r in items49] \
                                != [v["title"] for v in att_g49["voci"]]:
                            fails.append(f"{pg.name}: {tname49} voci elencate di "
                                         f"«{att_g49['label']}» non corrispondenti "
                                         f"({len(items49)} in pagina)")
                        for (url49, _t49, meta49), v49 in zip(items49, att_g49["voci"]):
                            checks += 1
                            if url49 != v49["url"]:
                                fails.append(f"{pg.name}: {tname49} link della voce "
                                             f"«{v49['title'][:40]}» diverso")
                            checks += 1
                            marcata49 = "anche in «Vita del club»" in html_unescape(meta49)
                            if marcata49 != v49["in_vita"]:
                                fails.append(f"{pg.name}: {tname49} voce "
                                             f"«{v49['title'][:40]}» "
                                             f"{'marcata' if marcata49 else 'non marcata'} "
                                             f"contro l'atteso ({v49['in_vita']})")
                if voci49 > elencate49:
                    checks += 1
                    atteso_coda49 = ("E un'altra voce della settimana, non elencata."
                                     if voci49 - elencate49 == 1
                                     else f"E altre {voci49 - elencate49} voci della settimana, "
                                          f"non elencate.")
                    if atteso_coda49 not in html_unescape(parte):
                        fails.append(f"{pg.name}: {tname49} resto non dichiarato "
                                     f"({voci49 - elencate49} voci oltre il tetto)")
    print(f"[49] pagine con clima del club riconciliate: {n_clima} (oracolo misto)")



    # 22) scontro tattico: graduatorie attacco/difesa e duello chiave ricalcolati dalla
    # classifica FotMob (fonte unica) e confrontati col testo stampato.
    n_duel = 0
    n_radar = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        fr = fx19[fx19.match_id == int(pg.stem)].iloc[0]
        cr = ma19.clash_ranks(str(fr.home_name), str(fr.away_name))
        if not cr:
            continue
        n_duel += 1
        for key in ("home_line", "away_line", "duel_line"):
            checks += 1
            if cr[key] not in txt:
                fails.append(f"{pg.name}: riga scontro «{key}» assente o diversa")
        # 22b) radar stile: le 5 barre sono ricalcolate dalla stessa funzione del sito. Un
        # dato mancante vale «n.d.» SENZA barra né numero: l'80 celle con un 50 neutro accanto
        # a «(n.d.)» (docs/57 §8) erano valori inventati in pagina.
        n_radar += 1
        # docs/77: stessa finestra del generatore, che passa il calcio d'inizio: su una
        # scheda pre-partita il radar è fermo alla vigilia; senza ``before`` l'oracolo
        # conta anche le gare giocate dopo e diverge quando il calendario è indietro
        # (issue #104: 3 radar falsati il 10/10/2026).
        cr_radar = ma19.clash_radar(str(fr.home_name), int(fr.home_id),
                                    str(fr.away_name), int(fr.away_id),
                                    pd.to_datetime(fr.utc_kickoff, utc=True))
        k = html.find("Radar stile")
        tab = html.find("<table", k) if k >= 0 else -1
        fine = html.find("</table>", tab) if tab >= 0 else -1
        if cr_radar is None:
            checks += 1
            if k >= 0:
                fails.append(f"{pg.name}: radar in pagina senza dati ricalcolabili")
            continue
        if tab < 0 or fine < 0:
            fails.append(f"{pg.name}: radar atteso e non trovato in pagina")
            continue
        righe = re.findall(r"<tr>\s*<th scope=\"row\" class=\"small\">(.*?)</tr>",
                           html[tab:fine], re.DOTALL)
        checks += 1
        if len(righe) != len(cr_radar["labels"]):
            fails.append(f"{pg.name}: radar con {len(righe)} righe invece di "
                         f"{len(cr_radar['labels'])}")
            continue
        for i, riga in enumerate(righe):
            checks += 1
            etichetta = html_unescape(re.sub(r"<[^>]+>", " ", riga))
            if cr_radar["labels"][i] not in etichetta:
                fails.append(f"{pg.name}: radar, riga {i + 1} «{etichetta.strip()[:30]}» "
                             f"invece di «{cr_radar['labels'][i]}»")
            celle = re.findall(r"<td>(.*?)</td>", riga, re.DOTALL)
            checks += 1
            if len(celle) != 2:
                fails.append(f"{pg.name}: radar, riga {i + 1} con {len(celle)} colonne")
                continue
            for lato, cella in zip(("home", "away"), celle):
                checks += 1
                atteso = cr_radar[lato][i]
                barra = re.search(r"flex:0 0 (\d+)%", cella)
                if atteso is None:
                    if barra or "n.d." not in cella:
                        fails.append(f"{pg.name}: radar, «{cr_radar['labels'][i]}» {lato} "
                                     "senza dato ma con barra o numero")
                    continue
                if not barra:
                    fails.append(f"{pg.name}: radar, «{cr_radar['labels'][i]}» {lato} "
                                 "senza barra")
                    continue
                if int(barra.group(1)) != round(atteso):
                    fails.append(f"{pg.name}: radar, «{cr_radar['labels'][i]}» {lato}: "
                                 f"pagina {barra.group(1)}, ricalcolo {round(atteso)}")
    print(f"[22] duello chiave e graduatorie verificati: {n_duel} pagine · "
          f"radar ricalcolato: {n_radar}")

    # 23) «giocherà?»: i badge titolare/panchina/assente stampati devono coincidere di
    # numero e contenuto coi ruoli della distinta; l'avviso sul top contributor assente
    # deve esserci se e solo se serve.
    n_status = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        mid = int(pg.stem)
        fr = fx19[fx19.match_id == mid].iloc[0]
        exp = {"starter": 0, "sub": 0, "unavailable": 0}
        alerts = 0
        listed = False
        for tid in (int(fr.home_id), int(fr.away_id)):
            sts = ma19.key_status(mid, tid)
            kp = ma19.key_players_deep(tid)
            rows = (kp or {}).get("rows") or []
            if rows:
                listed = True
            for r in rows:
                stt = (sts.get(r["id"]) or {}).get("status")
                if stt in exp:
                    exp[stt] += 1
            if rows and (sts.get(rows[0]["id"]) or {}).get("status") == "unavailable":
                alerts += 1
        if not listed:
            continue
        n_status += 1
        for badge, key in (("· titolare probabile", "starter"),
                           ("· in panchina", "sub"),
                           ("· assente:", "unavailable")):
            checks += 1
            if html.count(badge) != exp[key]:
                fails.append(f"{pg.name}: badge «{badge}» {html.count(badge)} vs {exp[key]} ruoli")
        # frase intera dell'avviso (docs/25 §4): la sottostringa «è indisponibile»
        # da sola intercetta anche il «Da sapere · L'uomo gol», che è un'altra cosa
        has_alert = "Il contributo offensivo più alto della lista" in txt
        if (alerts > 0) != has_alert:
            fails.append(f"{pg.name}: avviso top contributor assente coerente? {has_alert} vs {alerts}")
    print(f"[23] badge «giocherà?» riconciliati: {n_status} pagine")

    # 24) post-partita «Il prossimo impegno»: prima gara ufficiale (campionato + coppe)
    # ricalcolata dal calendario e confrontata con la riga stampata; se nessuna delle due
    # squadre ha gare future la card non deve esserci.
    n_next = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Lettura della partita" not in html or fx19.empty:
            continue
        rows = fx19[fx19.match_id == int(pg.stem)]
        if rows.empty or str(rows.iloc[0].status) != "finished":
            continue
        fr = rows.iloc[0]
        txt = html_unescape(html)
        ko = pd.Timestamp(fr.utc_kickoff)
        has_card, nx_lines = False, []
        for tid in (int(fr.home_id), int(fr.away_id)):
            nx = ma19.next_commitment(tid, ko)
            if nx:
                has_card = True
                nx_lines.append(nx["line"])
        checks += 1
        if has_card != ("Il prossimo impegno" in txt):
            fails.append(f"{pg.name}: card «Il prossimo impegno» incoerente col calendario")
            continue
        if not has_card:
            continue
        n_next += 1
        for line in nx_lines:
            checks += 1
            if line not in txt:
                fails.append(f"{pg.name}: riga prossimo impegno assente o diversa: «{line[:60]}…»")
    print(f"[24] «Il prossimo impegno» verificato: {n_next} pagine")

    # 25) conversione delle grandi occasioni: le celle «X su Y» devono coincidere coi tiri
    # mappati a xG ≥ 0,30 (autogol esclusi); la riga c'è se e solo se qualcuno ne ha avute.
    n_conv = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Tiri e occasioni" not in html or fx19.empty:
            continue
        rows = fx19[fx19.match_id == int(pg.stem)]
        if rows.empty or str(rows.iloc[0].status) != "finished":
            continue
        fr = rows.iloc[0]
        txt = html_unescape(html)
        cells, tot_big = [], 0
        for tid in (int(fr.home_id), int(fr.away_id)):
            summ = ma19.shot_summary(int(pg.stem), tid)
            big, bg = summ.get("big_chances", 0), summ.get("big_goals", 0)
            tot_big += big
            cells.append(f"{bg} su {big}")
        checks += 1
        if tot_big > 0:
            n_conv += 1
            if "…di cui convertite in gol" not in txt:
                fails.append(f"{pg.name}: riga conversione grandi occasioni assente")
            else:
                for cell in cells:
                    checks += 1
                    if cell not in txt:
                        fails.append(f"{pg.name}: cella conversione «{cell}» assente o diversa")
        elif "…di cui convertite in gol" in txt:
            fails.append(f"{pg.name}: riga conversione presente ma nessuna grande occasione")
    print(f"[25] conversione grandi occasioni verificata: {n_conv} pagine")

    # 26) mercato (docs/21 P2-7, rifatto in docs/24 §4): la card mostra la finestra
    # ricavata dai dati, gli importi in forma leggibile e gli arrivi già in distinta.
    # Qui si rifà il conto con le stesse funzioni del build e si confronta con la pagina:
    # righe, ordine, importi, estremi della finestra, saldo e «già in campo».
    n_mkt = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty:
            continue
        rows26 = fx19[fx19.match_id == int(pg.stem)]
        if rows26.empty:
            continue
        fr = rows26.iloc[0]
        mid = int(pg.stem)
        txt = html_unescape(html)
        attesi26 = {int(fr.home_id): ma19.transfer_window(int(fr.home_id), mid),
                    int(fr.away_id): ma19.transfer_window(int(fr.away_id), mid)}
        card = "id=\"mercato\"" in html
        checks += 1
        if card != any(v is not None for v in attesi26.values()):
            fails.append(f"{pg.name}: card mercato incoerente colla tabella transfers")
            continue
        if not card:
            continue
        n_mkt += 1
        # la card è divisa in due colonne, una per squadra: i controlli vanno fatti sulla
        # colonna, non sull'intera card (la riga «già in campo» di una squadra non è di
        # pertinenza dell'altra)
        colonne = re.split(r'<h3 style="margin:0 0 8px">', html[html.find('id="mercato"'):])[1:]
        per_nome = {}
        for col in colonne:
            nome_col = html_unescape(col.split("</h3>", 1)[0]).strip()
            per_nome[nome_col] = col
        for tid, mk in attesi26.items():
            if mk is None:
                continue
            nome = str(fr.home_name) if tid == int(fr.home_id) else str(fr.away_name)
            col = per_nome.get(nome)
            checks += 1
            if col is None:
                fails.append(f"{pg.name}: colonna mercato di {nome} assente")
                continue
            col_txt = html_unescape(col)
            checks += 1
            if mk["stale"]:
                if f"l'ultimo risale al <b>{mk['ultimo']}</b>" not in col:
                    fails.append(f"{pg.name}: {nome}: ultimo movimento non dichiarato come calcolato")
                continue
            attesa_testa = (f"<b>{mk['n_in']}</b> arrivo" if mk["n_in"] == 1
                            else f"<b>{mk['n_in']}</b> arrivi")
            attesa_testa += (" · <b>1</b> partenza" if mk["n_out"] == 1
                             else f" · <b>{mk['n_out']}</b> partenze")
            attesa_testa += (f" nella finestra dal <b>{mk['window_start']}</b> al "
                             f"<b>{mk['window_end']}</b>")
            checks += 1
            if attesa_testa not in col:
                fails.append(f"{pg.name}: {nome}: finestra e conteggi non corrispondono ai dati")
            for chiave, direzione in (("arrivals", "in"), ("departures", "out")):
                righe = [t for t in mk[chiave]]
                if righe:
                    checks += 1
                    etichetta = "Arrivi" if direzione == "in" else "Partenze"
                    if etichetta not in col:
                        fails.append(f"{pg.name}: {nome}: sezione «{etichetta}» assente")
                for t in righe:
                    checks += 1
                    if str(t["name"]) not in col_txt:
                        fails.append(f"{pg.name}: mercato {nome} ({direzione}): "
                                     f"«{t['name']}» assente o diversa dalla tabella")
                    checks += 1
                    if t["fee"] not in col_txt:
                        fails.append(f"{pg.name}: mercato {nome}: importo «{t['fee']}» non "
                                     f"stampato come calcolato")
            checks += 1
            if mk["in_campo"]:
                riga = (f"<b>Già in campo:</b> {len(mk['in_campo'])} "
                        + ("arrivo" if len(mk["in_campo"]) == 1 else "arrivi"))
                if riga not in col:
                    fails.append(f"{pg.name}: {nome}: riga «già in campo» assente o diversa "
                                 f"dal calcolo")
                for p26 in mk["in_campo"]:
                    checks += 1
                    if str(p26["name"]) not in col_txt:
                        fails.append(f"{pg.name}: {nome}: arrivo già in distinta non pubblicato "
                                     f"({p26['name']})")
            elif "Già in campo:" in col:
                fails.append(f"{pg.name}: {nome}: riga «già in campo» presente ma nessun "
                             f"arrivo in distinta secondo i dati")
    print(f"[26] card mercato riconciliate: {n_mkt} pagine")

    st.close()
    return fails, checks


#: L'indice della scheda partita (`match-jump`) e il titolo della sezione che ogni voce apre.
NAV_LINK = re.compile(r'<a href="(#[^"]+)">([^<]+)</a>')
NAV_HEAD = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.DOTALL)


def _testo_confrontabile(s: str) -> str:
    """Testo per confrontare etichetta e titolo: senza tag, minuscolo, senza accenti."""
    s = re.sub(r"<[^>]+>", " ", s)
    s = unicodedata.normalize("NFKD", html_unescape(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


#: Le sezioni che l'indice della scheda partita deve saper raggiungere quando esistono nella
#: pagina: sono le card pesanti rimaste senza ancora fino alla P1.3 (`docs/28` §2). Da P2.4
#: «contesto» non c'è più: le due card che ne sono nate hanno ognuna il suo id e la sua voce.
#: «fatti» è entrata nell'elenco l'8/10/2026 (M4 di `docs/55` §6): la sezione c'era su 66
#: schede su 66 e non era raggiungibile dall'indice.
NAV_SEZIONI = ("lettura", "previsione", "scontro", "arrivi", "giocatori", "squadre", "panchina",
               "mercato", "notizie", "fatti", "arbitro-meteo", "precedenti", "statistiche",
               "cronaca", "verifica")


def check_nav(site: Path) -> tuple[list[str], int]:
    """[33] L'indice della scheda partita: ogni voce dice il titolo della sezione che apre.

    Fino alla P1.3 (`docs/28` §2) la barra prometteva quattro voci e ne azzeccava una: «Dati e
    contesto» atterrava su «Confronto di stagione» e le card più pesanti non avevano ancora. Ora
    l'etichetta è l'inizio del titolo della sezione di destinazione, e questa invariante lo
    ricalcola su ogni scheda: un'etichetta che invecchia (o una sezione che sparisce) fa fallire
    il gate invece di mentire al lettore.
    """
    partite = site / "partite"
    if not partite.is_dir():
        return [], 0
    fails: list[str] = []
    checks = 0
    for page in sorted(partite.glob("*.html")):
        raw = page.read_text(encoding="utf-8")
        if 'class="match-jump"' not in raw:
            continue
        nav = raw.split('class="match-jump"', 1)[1].split("</nav>", 1)[0]
        for href, etichetta in NAV_LINK.findall(nav):
            checks += 1
            pos = raw.find(f'id="{href[1:]}"')
            if pos < 0:
                fails.append(f"{page.name}: indice → {href}, sezione assente dalla pagina")
                continue
            testa = NAV_HEAD.search(raw, pos)
            if not testa:
                fails.append(f"{page.name}: indice → {href}, sezione senza titolo h2/h3")
                continue
            titolo = _testo_confrontabile(testa.group(2))
            if not titolo.startswith(_testo_confrontabile(etichetta)):
                fails.append(f"{page.name}: indice «{etichetta}» → sezione «{titolo[:48]}»")
        # e l'altra direzione: una sezione pesante che c'è deve essere raggiungibile dall'indice
        for ancora in NAV_SEZIONI:
            if f'id="{ancora}"' in raw and f'href="#{ancora}"' not in nav:
                checks += 1
                fails.append(f"{page.name}: sezione «{ancora}» presente ma fuori dall'indice")
    print(f"[33] voci dell'indice della scheda partita verificate: {checks}")
    return fails, checks


TERNA_TAB = re.compile(r'<td class="r">(\d{1,3}) / (\d{1,3}) / (\d{1,3})</td>')
TERNA_TESTO = re.compile(r"1 (\d{1,3})% · X (\d{1,3})% · 2 (\d{1,3})%")
TERNA_DESC = re.compile(r"1 (\d{1,3})% X (\d{1,3})% 2 (\d{1,3})%")
# riga della tabella «win probability»: minuto, punteggio, poi la terna 1/X/2
TERNA_WP = re.compile(r"<td class=\"mut small\">\d+'</td>\s*<td>[^<]*</td>\s*"
                      r"<td class=\"r\">(\d{1,3})%</td>\s*<td class=\"r\">(\d{1,3})%</td>\s*"
                      r"<td class=\"r\">(\d{1,3})%</td>")


def check_terne_1x2(site: Path) -> tuple[list[str], int]:
    """[47] Le terne 1/X/2 pubblicate devono sommare 100, ovunque compaiano.

    Tre arrotondamenti indipendenti delle stesse probabilità sommano 99 o 101: succedeva su
    11 righe su 40 della tabella Accuratezza e su 134 occorrenze delle descrizioni SEO su 564
    (che finiscono su Google, `docs/22`) finché la terna non è passata da `pct_triple`
    (`docs/78` §14). Le quattro grafie controllate sono quelle che il sito usa davvero: la
    tabella «Ultime partite valutate», i testi in evidenza di index/prossime, le
    description/og:description delle schede, e la tabella dell'andamento 1X2 minuto per
    minuto delle schede (153 righe su 754 rotte prima del fix).
    """
    fails: list[str] = []
    checks = 0
    n_terne = 0
    for pg in sorted(site.rglob("*.html")):
        h = pg.read_text(encoding="utf-8")
        for pat, dove in ((TERNA_TAB, "tabella"), (TERNA_TESTO, "testo"),
                          (TERNA_DESC, "descrizione"), (TERNA_WP, "andamento")):
            for m in pat.finditer(h):
                n_terne += 1
                checks += 1
                somma = sum(int(x) for x in m.groups())
                if somma != 100:
                    fails.append(f"{pg.name}: terna 1X2 in {dove} somma {somma} "
                                 f"({m.group(0)[:44]})")
    print(f"[47] terne 1/X/2 pubblicate: {n_terne} · tutte sommano 100")
    return fails, checks


# Mercati binari della pagina Accuratezza: etichetta in pagina → colonna della previsione.
# Scritta a mano (non presa da SiteBuilder.MARKETS): se il generatore cambia una colonna o una
# soglia, questo controllo deve continuare a misurare la pagina, non seguire il generatore.
PCT_MERCATI = (
    ("Over 1,5 gol", "p_over15"),
    ("Over 2,5 gol", "p_over25"),
    ("Over 3,5 gol", "p_over35"),
    ("Gol · entrambe a segno", "p_btts"),
    ("Doppia chance 1X", "p_1x"),
    ("Doppia chance 12", "p_12"),
    ("Doppia chance X2", "p_x2"),
    ("Porta inviolata casa", "p_home_clean_sheet"),
    ("Porta inviolata trasferta", "p_away_clean_sheet"),
)


def check_pct_accuratezza(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[48] Le percentuali intere della pagina Accuratezza, ricalcolate dai Parquet.

    Sono le cifre con cui il lettore giudica il modello: l'esito più probabile azzeccato per
    campionato, le «scelte indovinate» dei nove mercati e la probabilità dell'esito poi
    verificatosi nella tabella delle ultime partite. Il ricalcolo è scritto qui: la regola
    dichiarata per le cifre intere (**mezzo in su**, `docs/78` §15, non `round()`), la soglia
    del mercato binario (probabilità ≥ 0,5), e gli eventi osservati dai gol (over = totale
    oltre la soglia, btts, doppie chance, porta inviolata). L'hit per campionato è l'identità
    che il lettore può rifare a mano: esito più probabile = esito vero, contato sulle stesse
    gare valutate della pagina. Il campione (ultima previsione prima del fischio) viene dai
    Parquet, quindi il controllo è misto; la cifra no.
    """
    import numpy as np
    import pandas as pd

    from fda.config import leagues
    from fda.store import Store

    fails: list[str] = []
    checks = 0
    pag = site / "accuratezza.html"
    if not pag.is_file():
        return fails, checks
    h = pag.read_text(encoding="utf-8")
    st = Store(data) if data else Store()
    preds, fx = st.read("predictions"), st.read("fixtures")
    if preds.empty or fx.empty or "status" not in fx.columns:
        return fails, checks
    fin = fx[fx.status == "finished"][["match_id", "home_goals", "away_goals", "utc_kickoff",
                                        "league_id"]]
    p = preds.merge(fin, on="match_id", suffixes=("", "_fx"))
    inizio = "utc_kickoff_fx" if "utc_kickoff_fx" in p.columns else "utc_kickoff"
    p = p[p.made_at < p[inizio]]
    p = p.sort_values("made_at").groupby("match_id").tail(1)
    if p.empty:
        return fails, checks
    p["outcome"] = [0 if int(hg) > int(ag) else (1 if int(hg) == int(ag) else 2)
                    for hg, ag in zip(p.home_goals, p.away_goals)]
    probs = p[["p_home", "p_draw", "p_away"]].to_numpy(dtype=float)
    p["hit"] = probs.argmax(axis=1) == p["outcome"].to_numpy()
    p["p_real"] = probs[np.arange(len(p)), p["outcome"].to_numpy()]
    nomi = {lg.fotmob_id: lg.name for lg in leagues()}
    p["lega"] = p.league_id.map(nomi)

    # A) righe per campionato: «Partite valutate» e «Esito più probabile azzeccato»
    riga_re = re.compile(r'<tr[^>]*><td>([^<]+)</td><td class="r">(\d+)</td><td class="r">[\d.,]+</td>'
                         r'<td class="r">[\d,]+</td><td class="r">[\d,]+</td><td class="r">(\d+)%</td>')
    n_camp = 0
    for m in riga_re.finditer(h):
        nome, n_st, hit_st = m.group(1), int(m.group(2)), int(m.group(3))
        gruppo = p if nome == "Tutti" else p[p.lega == nome]
        if gruppo.empty:
            fails.append(f"accuratezza.html: riga «{nome}» senza gare nel ricalcolo")
            continue
        n_camp += 1
        checks += 2
        if n_st != len(gruppo):
            fails.append(f"accuratezza.html: {nome} «{n_st} partite valutate» vs {len(gruppo)} "
                         "dai Parquet (ultima previsione prima del fischio)")
        atteso = pct_dichiarata(float(gruppo["hit"].mean()))
        if hit_st != atteso:
            fails.append(f"accuratezza.html: {nome} esito azzeccato {hit_st}% vs ricalcolato "
                         f"{atteso}% ({int(gruppo['hit'].sum())}/{len(gruppo)})")

    # B) nove mercati: «gare», «(k/n)» e «scelte indovinate»
    blocco = re.search(r"Accuratezza per mercato(.*?)</table>", h, re.DOTALL)
    totale = (p.home_goals.astype(float) + p.away_goals.astype(float)).to_numpy()
    soli_home, soli_away = p.home_goals.astype(float).to_numpy(), p.away_goals.astype(float).to_numpy()
    osservati = {
        "p_over15": totale > 1.5, "p_over25": totale > 2.5, "p_over35": totale > 3.5,
        "p_btts": (soli_home > 0) & (soli_away > 0),
        "p_1x": soli_home >= soli_away, "p_12": soli_home != soli_away, "p_x2": soli_home <= soli_away,
        "p_home_clean_sheet": soli_away == 0, "p_away_clean_sheet": soli_home == 0}
    n_merc = 0
    if blocco:
        righe = {lab.strip(): corpo for lab, corpo in
                 re.findall(r"<tr><td>([^<]+)</td>(.*?)</tr>", blocco.group(1), re.DOTALL)}
        for lab, col in PCT_MERCATI:
            corpo = righe.get(lab)
            if corpo is None:
                fails.append(f"accuratezza.html: riga di mercato «{lab}» assente")
                continue
            celle = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", corpo, re.DOTALL)]
            if len(celle) < 9 or col not in p.columns:
                fails.append(f"accuratezza.html: riga di mercato «{lab}» inattesa")
                continue
            n_merc += 1
            pr = pd.to_numeric(p[col], errors="coerce").to_numpy(dtype=float)
            ok = ~np.isnan(pr)
            y = osservati[col][ok]
            # la riga dopo lo <td> dell'etichetta: gare, previsto, osservato (k/n), intervallo,
            # Brier, Brier base, Δ, scelte indovinate, segnale
            n_st, mkn = int(celle[0]), re.search(r"\((\d+)/(\d+)\)", celle[2])
            hit_st = int(celle[7].strip().rstrip("%"))
            checks += 3
            if n_st != int(ok.sum()):
                fails.append(f"accuratezza.html: {lab} «{n_st} gare» vs {int(ok.sum())} con "
                             "probabilità pubblicata")
            if mkn:
                k_st, n_kn = int(mkn.group(1)), int(mkn.group(2))
                if k_st != int(y.sum()) or n_kn != int(ok.sum()):
                    fails.append(f"accuratezza.html: {lab} «({k_st}/{n_kn})» vs "
                                 f"{int(y.sum())}/{int(ok.sum())} osservati dai gol")
            atteso = pct_dichiarata(float(((pr[ok] >= 0.5) == y).mean()))
            if hit_st != atteso:
                fails.append(f"accuratezza.html: {lab} scelte indovinate {hit_st}% vs ricalcolato "
                             f"{atteso}%")

    # C) tabella «Ultime partite valutate»: la probabilità dell'esito poi verificatosi
    rec_re = re.compile(r'<tr><td class="mut">[\d/]+</td>'
                        r'<td><a href="[^"]*?partite/(\d+)\.html">[^<]*</a></td>'
                        r'<td class="c">(\d+)-(\d+)</td>\s*'
                        r'<td class="r">\d+ / \d+ / \d+</td>\s*<td class="c">.*?</td>\s*'
                        r'<td class="r">[\d,]+</td>\s*<td class="r">(\d+)%</td></tr>')
    per_id = p.set_index("match_id")
    n_rec = 0
    for m in rec_re.finditer(h):
        mid, hit_st = int(m.group(1)), int(m.group(4))
        if mid not in per_id.index:
            fails.append(f"accuratezza.html: partita {mid} nella tabella ma non fra le valutate")
            continue
        n_rec += 1
        checks += 1
        atteso = pct_dichiarata(float(per_id.loc[mid, "p_real"]))
        if hit_st != atteso:
            fails.append(f"accuratezza.html: {mid} p_real {hit_st}% vs ricalcolato {atteso}% "
                         f"({float(per_id.loc[mid, 'p_real']) * 100:.4f}%)")

    print(f"[48] percentuali intere di Accuratezza ricalcolate: {n_camp} campionati · "
          f"{n_merc} mercati · {n_rec} partite")
    return fails, checks


def check_assets(site: Path) -> tuple[list[str], int]:
    """[29] CSS esterno (docs/19 P0.5): link giusto in ogni pagina, zero <style> inline.

    Il design system (~39 kB) era inline in ogni pagina: l'estrazione vale ~-38 kB × pagine
    e mette il CSS in cache una volta sola. L'invariante protegge il risultato: se una
    pagina torna a portarsi il CSS dietro (o linka il file con la profondità sbagliata,
    che romperebbe il tema nelle sottocartelle), qui si vede prima che a schermo.
    """
    fails: list[str] = []
    checks = 0
    css = site / "assets" / "site.css"
    if not css.exists() or css.stat().st_size < 1000:
        fails.append("assets/site.css: file mancante o troppo piccolo")
        return fails, 0
    for pg in sorted(site.rglob("*.html")):
        html = pg.read_text(encoding="utf-8")
        # index.html → 0; partite/123.html → 1; giocatori/123.html → 1.
        # Eccezione 404.html (P1.6): GitHub Pages la serve a QUALSIASI percorso, quindi
        # il suo CSS deve essere assoluto sul base del sito, non relativo alla profondità.
        depth = len(pg.parent.relative_to(site).parts)
        if pg.name == "404.html" and depth == 0:
            atteso = "https://uamisjd.github.io/football-deep-analyzer/assets/site.css?v="
        else:
            atteso = "../" * depth + "assets/site.css?v="
        links = re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)
        checks += 1
        if not any(h.startswith(atteso) for h in links):
            fails.append(f"{pg.relative_to(site)}: link CSS esterno mancante o percorso "
                         f"sbagliato (atteso {atteso}…)")
        if "<style" in html:
            fails.append(f"{pg.relative_to(site)}: blocco <style> inline (il CSS vive in assets/site.css)")
    if not checks:
        fails.append("nessuna pagina .html trovata per il controllo [29]")
    return fails, checks


def check_stime(site: Path) -> tuple[list[str], int]:
    """[32] stime stabilizzate dei per-90 e delle quote nelle schede giocatore (docs/19 §1.10, docs/23 §2).

    Quattro regole misurate sulle pagine:

    1. ogni cella marcata ◇ o ◎ dichiara **media dei pari, peso k e numerosità** nel tooltip:
       una stima senza il gruppo che l'ha prodotta non è verificabile;
    2. sotto i 90′ giocati nessuna cella pubblica un valore grezzo (il caso «90,00 tiri/90» su un
       minuto di gioco, o una percentuale su tre duelli): o il grezzo non c'è, o è la stima, o è
       marcato ◇;
    3. nessuna **rata per 90** pubblicata supera 25 per 90 sotto i 270′ di campione: sopra quella
       soglia il numero è di fatto impossibile e va pubblicato come stima, non come fatto;
    4. una cella **percentuale** non è una rata per 90: il suo tooltip non deve dire «/90′», perché
       una quota (passaggi riusciti, duelli vinti) non si normalizza sui minuti.
    """
    fails: list[str] = []
    checks = 0
    n_righe = n_stime = n_quote = 0
    riga = re.compile(r"<tr><td>([^<]+?)(?: <span class=\"mut small\" title=\"([^\"]*)\">([◎◇])</span>)? ?</td>"
                      r"<td class=\"r\">([^<]*)</td><td class=\"r\">(.*?)</td></tr>")
    minuti_rx = re.compile(r'<th scope="row">Minuti</th><td class="r">([\d.]+)</td>')
    for page in sorted((site / "giocatori").glob("*.html")):
        if page.name == "index.html":
            continue
        h = page.read_text(encoding="utf-8", errors="replace")
        m_min = minuti_rx.search(h)
        if not m_min:
            continue
        minuti = int(m_min.group(1).replace(".", ""))
        for match in riga.finditer(h):
            lab, nota, mark, _tot, cella = match.groups()
            n_righe += 1
            checks += 1
            testo = re.sub(r"<[^>]+>", "", cella).strip()
            if testo in ("", "—"):
                continue
            titolo_m = re.search(r'title="([^"]*)"', cella)
            titolo = titolo_m.group(1) if titolo_m else ""
            percentuale = testo.endswith("%") or lab.rstrip().endswith("%")
            if percentuale:
                n_quote += 1
                if "/90′" in titolo:
                    fails.append(f"{page.name}: {lab}: quota dichiarata come rata per 90 («/90′» nel tooltip)")
            numeri = re.findall(r"\b\d+,\d+\b", testo)
            valore = float(numeri[0].replace(",", ".")) if numeri else None
            stima = "◇" in cella or mark == "◇"
            marcata = stima or "◎" in cella or mark == "◎"
            if marcata:
                n_stime += 1
                nota_full = " ".join([nota or "", titolo])
                for token in ("media dei pari", "peso k=", "n="):
                    if token not in nota_full:
                        fails.append(f"{page.name}: {lab}: stima senza «{token}» nel tooltip")
            elif valore is not None and minuti < 90:
                fails.append(f"{page.name}: {lab}: valore {testo} pubblicato con {minuti}′ giocati")
            elif (not percentuale and valore is not None and valore > 25 and minuti < 270):
                fails.append(f"{page.name}: {lab}: rata {valore}/90 con {minuti}′ di campione")
    print(f"[32] righe per-90 delle schede giocatore verificate: {n_righe} "
          f"(stime ◇/◎: {n_stime}, quote: {n_quote})")

    # Regola 5 sulle schede partita: le celle dei giocatori decisivi e dell'infermeria usano gli
    # stessi marcatori ◇/◎, ma il valore arriva da `analysis.py` e un campo non emesso verrebbe
    # reso da Jinja come stringa vuota («◇ » senza numero, difetto già visto in questo progetto).
    rx_marcata = re.compile(r"[◎◇]\s*([^<]{0,60}?)(?:</b>|</span>)")
    righe_partita = 0
    for page in sorted((site / "partite").glob("*.html")):
        h = page.read_text(encoding="utf-8", errors="replace")
        for m in rx_marcata.finditer(h):
            righe_partita += 1
            checks += 1
            coda = m.group(1).strip()
            if not coda or coda in ("—", "-"):
                fails.append(f"{page.name}: cella ◇/◎ senza numero pubblicato")
        for m in re.finditer(r'title="([^"]*)"[^>]*>[^<]{0,40}◇', h):
            checks += 1
            if "media dei pari" not in m.group(1) and "gruppo dei pari" not in m.group(1):
                fails.append(f"{page.name}: stima ◇ senza la media dei pari nel tooltip")
    print(f"[32] celle ◇/◎ delle schede partita verificate: {righe_partita}")
    return fails, checks


# ---- fonti dichiarate nella pagina «Info» (P2.6, docs/38) --------------------------------------
# La pagina «Info» elencava fra le fonti gratuite «The Odds API — quote opzionali, solo se
# ODDS_API_KEY è configurata»: nessun modulo del progetto la chiamava, nessuna pagina pubblicava
# quote, e la chiave in `config/sources.yaml` non era letta da nessuno. Il lettore non poteva
# accorgersene: quella voce prometteva un'integrazione che non esisteva. Questa invariante lega
# l'elenco pubblicato ai moduli veri di `src/fda/sources/`, nei due versi: una voce senza modulo
# (fonte promessa e mai implementata) e un modulo senza voce (fonte implementata e mai dichiarata)
# fanno fallire il gate. Insieme fissa la decisione sulle quote: il sito non le pubblica, la
# pagina Info lo dichiara, nessuna pagina le promette. Se la decisione cambia, cambiano insieme
# questa invariante, `docs/38` e il codice che la applica.
INFO_FONTI = {
    "FotMob": "fotmob.py",
    "Understat": "understat.py",
    "Open-Meteo": "openmeteo.py",
    "Google News RSS e ESPN news": "news.py",
    "FotMob coppe (UCL/UEL)": "fotmob.py",
    "ESPN": "espn.py",
    "football-data.co.uk": "history.py",
}
#: Formule con cui si prometteva o si citava un mercato che il sito non pubblica.
QUOTE_VIETATE = ("The Odds API", "ODDS_API_KEY", "probabilità implicite", "quote consenso",
                 "quote vs modello", "sezione quote", "closing line value")
#: La frase che dichiara la decisione, nella pagina che elenca le fonti.
QUOTE_DICHIARAZIONE = "Quote di mercato: non pubblicate."


def check_fonti(site: Path) -> tuple[list[str], int]:
    """Fonti dichiarate in «Info» = moduli in `src/fda/sources/`; niente promesse di quote."""
    fails: list[str] = []
    checks = 0
    info = site / "info.html"
    if not info.is_file():
        return [f"info.html assente in {site}"], 0
    html = info.read_text(encoding="utf-8")
    inizio = html.find("<h2>Le fonti (gratuite)</h2>")
    fine = html.find("</ul>", inizio) if inizio != -1 else -1
    if inizio == -1 or fine == -1:
        return ["info.html: elenco «Le fonti (gratuite)» non trovato"], 0
    voci = re.findall(r"<li><b>([^<]+)</b>", html[inizio:fine])
    sorgenti = Path(__file__).resolve().parent.parent / "src" / "fda" / "sources"
    moduli = {p.name for p in sorgenti.glob("*.py") if p.name != "__init__.py"}
    for voce in voci:
        checks += 1
        modulo = INFO_FONTI.get(voce)
        if modulo is None:
            fails.append(f"info.html: fonte dichiarata «{voce}» senza modulo in src/fda/sources "
                         f"(promessa non mantenuta)")
        elif modulo not in moduli:
            fails.append(f"info.html: la fonte «{voce}» punta al modulo mancante {modulo}")
    for modulo in sorted(moduli - set(INFO_FONTI.values())):
        checks += 1
        fails.append(f"src/fda/sources/{modulo}: fonte implementata e non dichiarata in info.html")
    checks += 1
    if QUOTE_DICHIARAZIONE not in html:
        fails.append(f"info.html: manca la dichiarazione «{QUOTE_DICHIARAZIONE}»")
    n_pg = 0
    for pg in sorted(site.rglob("*.html")):
        n_pg += 1
        testo = html_unescape(pg.read_text(encoding="utf-8"))
        for vietata in QUOTE_VIETATE:
            checks += 1
            if vietata in testo:
                fails.append(f"{pg.relative_to(site)}: promette o cita quote di mercato "
                             f"(«{vietata}»), che il sito non pubblica (decisione docs/38)")
    print(f"[35] fonti dichiarate nella pagina «Info»: {len(voci)} voci · {len(moduli)} moduli · "
          f"{n_pg} pagine senza promesse di quote")
    return fails, checks


# ---- ogni tabella dentro un contenitore che scorre (P2.8, docs/39) ------------------------------
# A 375 px una tabella più larga della card faceva scorrere **la pagina** di lato: succedeva su
# 4.929 tabelle (la fascia storica da 6 colonne chiede 507 px in 295 disponibili). Il rimedio è
# `.tablewrap` (`overflow-x:auto`): la tabella scorre dentro la card e la pagina resta ferma. La
# regola è strutturale — una tabella senza contenitore è un difetto su un telefono, e non si vede
# da fuori perché su desktop la tabella entra comunque. Qui si controlla su tutte le pagine
# pubblicate; la misura vera delle larghezze sta in `scripts/resa_375.py`.
def check_tavole(site: Path) -> tuple[list[str], int]:
    """[36] ogni `<table>` pubblicata sta dentro un `.tablewrap`, una volta sola."""
    fails: list[str] = []
    checks = 0
    for pg in sorted(site.rglob("*.html")):
        html = pg.read_text(encoding="utf-8")
        n_tab = html.count("<table")
        n_wrap = html.count('class="tablewrap"')
        checks += n_tab
        rel = pg.relative_to(site)
        if n_wrap != n_tab:
            fails.append(f"{rel}: {n_tab} tabelle ma {n_wrap} contenitori .tablewrap")
            continue
        for m in re.finditer(r"<table\b", html):
            if html.rfind('class="tablewrap"', 0, m.start()) < html.rfind("</table>", 0, m.start()):
                fails.append(f"{rel}: <table> fuori da .tablewrap (scorre la pagina, non la card)")
    print(f"[36] tabelle dentro .tablewrap verificate: {checks}")
    return fails, checks


# ---- la didascalia sotto il punteggio dice lo stato della gara (docs/41) -------------------------
# Misurato sul sito pubblicato il 19/09/2026 alle 16:03 IT: **7 schede su 7** in corso mostravano
# il punteggio live con la didascalia «calcio d'inizio» («Bologna 1–0 calcio d'inizio» al 63' di
# gioco) e l'hero della scheda «1–0 · calcio d'inizio · 15:00». La didascalia era binaria
# (finita / tutto il resto) e nessun invariante la leggeva: `verify_site` era verde con 151.316
# controlli. Qui si verifica che la didascalia segua lo stato dichiarato dalla card stessa.
DIDASCALIA_ATTESA = {
    "finished": "finale",
    "live": "in corso",
    "paused": "intervallo",
    "postponed": "rinviata",
    "suspended": "sospesa",
    "cancelled": "annullata",
    "canceled": "annullata",
    "abandoned": "sospesa",
    "scheduled": "calcio d'inizio",
}


def check_didascalie_punteggio(site: Path) -> tuple[list[str], int]:
    """[37] didascalia del punteggio coerente con lo stato, nelle liste e nell'hero."""
    fails: list[str] = []
    checks = 0
    card = re.compile(r'data-status="([a-z_]+)".*?<div class="match-score">.*?<span>(.*?)</span>',
                      re.DOTALL)
    hero = re.compile(r'<span class="result">(.*?)</span><span class="date">(.*?)</span>', re.DOTALL)
    for pg in sorted(site.rglob("*.html")):
        html = pg.read_text(encoding="utf-8")
        rel = pg.relative_to(site)
        # liste (Oggi / Prossime / Risultati): una card per blocco, così una riga di calendario
        # senza punteggio non può prendere in prestito la didascalia della card successiva
        for blocco in html.split('<article class="match-card"')[1:]:
            m = card.search(blocco)
            if not m:
                continue
            checks += 1
            bucket, scritta = m.group(1), html_unescape(m.group(2)).strip()
            attesa = DIDASCALIA_ATTESA.get(bucket, "calcio d'inizio")
            if scritta != attesa:
                fails.append(f"{rel}: didascalia «{scritta}» su una gara «{bucket}» "
                             f"(atteso «{attesa}»)")
        # hero della scheda partita: un punteggio numerico non è mai «calcio d'inizio» da solo
        m = hero.search(html)
        if m:
            punteggio, didascalia = m.group(1).strip(), html_unescape(m.group(2)).strip()
            if punteggio != "vs":
                checks += 1
                if didascalia.startswith("calcio d'inizio"):
                    fails.append(f"{rel}: hero «{punteggio}» con didascalia «{didascalia}» "
                                 "(un punteggio giocato non è un calcio d'inizio)")
                elif punteggio.endswith("–") or punteggio.startswith("–"):
                    fails.append(f"{rel}: hero con punteggio incompleto «{punteggio}»")
    print(f"[37] didascalie del punteggio verificate: {checks}")
    return fails, checks


# Importi di mercato azzerati dall'arrotondamento (docs/43 §3). Il difetto misurato il
# 2026-09-19: `giocatore.html` divideva per un milione e poi applicava `it_num`, che non
# ha decimali → ogni valore sotto i 500.000 € diventava «€0M» su **845** schede, con
# 1.589 valori reali fra 0 e 500.000 € (minimo 73.728 €) e nessun valore nullo nella
# fonte. Non è un controllo matematico: rilegge la pagina come la legge il lettore e
# vieta la **forma** in cui uno zero falso si presenta.
IMPORTO_AZZERATO = ("€0M", "≈ 0 M€")


def check_importi_mercato(site: Path) -> tuple[list[str], int]:
    """[38] nessun importo di mercato pubblicato come zero dall'arrotondamento."""
    fails: list[str] = []
    checks = 0
    for pg in sorted(site.rglob("*.html")):
        html = pg.read_text(encoding="utf-8")
        checks += 1
        for forma in IMPORTO_AZZERATO:
            if forma in html:
                i = html.find(forma)
                contesto = re.sub(r"\s+", " ", html[max(0, i - 90):i + 40]).strip()
                fails.append(f"{pg.relative_to(site)}: importo pubblicato come «{forma}» "
                             f"(un valore di mercato non è mai zero) — …{contesto}…")
    print(f"[38] pagine senza importi azzerati dall'arrotondamento: {checks}")
    return fails, checks


# La card «Mercato» pubblicava ogni movimento due volte (docs/55 §4.1, docs/56 §2): la chiave
# dell'upsert non intercettava le righe che la fonte riscrive con l'ora locale al posto
# dell'UTC e con i diacritici diversi, quindi la pagina mostrava la stessa riga due volte e i
# conteggi erano gonfi di ~1,9×. `verify_site [26]` riconciliava la card **con la stessa
# funzione** che la costruisce: coerente e sbagliata. Questa invariante rifà il conto dal
# Parquet, in modo indipendente, e pretende che una riga per giocatore resti una.
def check_mercato_movimenti(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[39] un movimento per giocatore e direzione: niente righe ripetute, conteggi giusti."""
    import pandas as pd

    from fda.store import Store
    from fda.teams import soft_key

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    tr = st.read("transfers")
    fx = st.read("fixtures")
    if tr.empty or fx.empty or "player_name" not in tr.columns:
        return fails, checks
    date = pd.to_datetime(tr["date"], utc=True, errors="coerce", format="mixed")
    tr = tr.assign(_dt=date, _pn=tr.player_name.map(lambda v: soft_key(str(v or ""))),
                   _cn=tr.counterpart.map(lambda v: soft_key(str(v or ""))))
    tr = tr[tr._dt.notna()]
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    intestazione = re.compile(r"<b>(\d+)</b> (?:arrivo|arrivi) · <b>(\d+)</b> (?:partenza|partenze) "
                              r"nella finestra dal <b>(\d{2}/\d{2}/\d{4})</b>")
    n_pagine = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if 'id="mercato"' not in html or "Analisi pre-partita" not in html:
            continue
        mid = int(pg.stem)
        riga_fx = fx[fx.match_id == mid]
        if riga_fx.empty:
            continue
        f = riga_fx.iloc[0]
        n_pagine += 1
        # la card finisce alla card successiva: senza il taglio, `<h3>` di altre sezioni
        # entravano nella scansione (misurato: 255 blocchi invece di 132)
        inizio = html.find('id="mercato"')
        dopo = html.find('<div class="card" id="', inizio + 10)
        card = html[inizio:dopo if dopo > inizio else len(html)]
        colonne = re.split(r'<h3 style="margin:0 0 8px">', card)[1:]
        # (a) nessun nome ripetuto nella stessa colonna e direzione
        for colonna in colonne:
            pezzi = colonna.split('class="small" style="margin:8px 0 4px;')[1:]
            for direzione, pezzo in zip(("arrivi", "partenze"), pezzi, strict=False):
                nomi = re.findall(r"<tr>\s*<td>([^<]+)</td>", pezzo)
                checks += 1
                chiavi = [soft_key(html_unescape(n)) for n in nomi]
                if len(chiavi) != len(set(chiavi)):
                    doppi = sorted({n for n, k in zip(nomi, chiavi, strict=True)
                                    if chiavi.count(k) > 1})
                    fails.append(f"{pg.name}: mercato {direzione}: riga ripetuta "
                                 f"({', '.join(doppi)})")
        # (b) i conteggi pubblicati = giocatori distinti nella finestra dichiarata in pagina
        for tid, nome in ((int(f.home_id), str(f.home_name)), (int(f.away_id), str(f.away_name))):
            squadra = tr[tr.team_id == tid]
            if squadra.empty:
                continue
            attesi = {}
            for direzione, chiave in (("in", "n_in"), ("out", "n_out")):
                d = squadra[squadra.direction == direzione]
                attesi[chiave] = int(d._pn.nunique()) if not d.empty else 0
            m = None
            for col in colonne:
                if html_unescape(col.split("</h3>", 1)[0]).strip() == nome:
                    m = intestazione.search(col)
                    break
            if m is None:
                continue
            for chiave, idx in (("n_in", 1), ("n_out", 2)):
                pubblicato = int(m.group(idx))
                checks += 1
                # la finestra può escludere i movimenti vecchi: il confronto è sulla stessa
                # porzione di tabella letta dalla pagina
                inizio = pd.to_datetime(m.group(3), format="%d/%m/%Y", utc=True)
                direzione = "in" if chiave == "n_in" else "out"
                d = squadra[(squadra.direction == direzione) & (squadra._dt >= inizio)]
                distinti = int(d._pn.nunique()) if not d.empty else 0
                if pubblicato != distinti:
                    extra = pubblicato - distinti
                    spiegato = False
                    if extra > 0:
                        # eccezione dichiarata dalla card: due movimenti dello stesso
                        # giocatore verso club diversi a più di 30 giorni l'uno dall'altro
                        gruppi = 0
                        for _, g in d.groupby("_pn"):
                            if len(g) < 2:
                                continue
                            span = (g._dt.max() - g._dt.min()).days
                            if span > 30 and len({c for c in g._cn}) > 1:
                                gruppi += len(g) - 1
                        spiegato = gruppi >= extra
                    if not spiegato:
                        fails.append(f"{pg.name}: mercato {nome}: {pubblicato} movimenti "
                                     f"pubblicati contro {distinti} giocatori distinti nei dati")
    print(f"[39] card mercato senza movimenti ripetuti: {n_pagine} pagine")
    return fails, checks


# Le soglie del meteo erano scritte in due posti diversi: il testo della card diceva «nella
# norma (precip <30%, 10-28 °C, vento <15 km/h)», il codice segnalava `≥30`, `≥30/≤5`, `≥15` e
# chiamava «estremo — può spostare ritmi» una pioggia al 31% (14 schede su 66, docs/55 §4.3).
# Ora le soglie sono costanti del progetto stampate in pagina: qui si verifica che la pagina
# dica **quelle** e che il livello dichiarato corrisponda ai valori nel Parquet.
def check_meteo_soglie(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[40] meteo: stesse soglie fra testo e codice, livello coerente coi valori misurati."""
    import pandas as pd

    from fda.site.analysis import (
        WEATHER_IMPATTO_TESTO,
        WEATHER_PRECIP_IMPATTO,
        WEATHER_PRECIP_SEGNALA,
        WEATHER_SOGLIE_TESTO,
        WEATHER_TEMP_ALTA,
        WEATHER_TEMP_BASSA,
        WEATHER_VENTO_IMPATTO,
        WEATHER_VENTO_SEGNALA,
    )
    from fda.store import Store

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    mi = st.read("match_info")
    if mi.empty:
        return fails, checks
    info = mi.set_index("match_id") if "match_id" in mi.columns else mi
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    riga = re.compile(r'<th scope="row">Meteo[^<]*</th><td[^>]*>(.*?)</td></tr>', re.DOTALL)
    n = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        m = riga.search(html)
        if not m:
            continue
        mid = int(pg.stem)
        if mid not in info.index:
            continue
        n += 1
        testo = html_unescape(re.sub(r"<[^>]+>", " ", m.group(1)))
        testo = re.sub(r"\s+", " ", testo).strip()
        r = info.loc[mid]
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        precip = r.get("weather_precip_chance")
        temp = r.get("weather_temp_c")
        wind = r.get("weather_wind")
        impatto = (precip is not None and float(precip) > WEATHER_PRECIP_IMPATTO) or \
            (temp is not None and float(temp) > WEATHER_TEMP_ALTA) or \
            (wind is not None and float(wind) > WEATHER_VENTO_IMPATTO)
        attenzione = (precip is not None and float(precip) >= WEATHER_PRECIP_SEGNALA) or \
            (temp is not None and (float(temp) >= WEATHER_TEMP_ALTA
                                   or float(temp) <= WEATHER_TEMP_BASSA)) or \
            (wind is not None and float(wind) >= WEATHER_VENTO_SEGNALA)
        checks += 1
        # Le soglie si dicono **una volta**: la riga dentro soglia dichiara l'intervallo intero
        # (`WEATHER_SOGLIE_TESTO`), quella oltre soglia il testo delle soglie di impatto
        # (`WEATHER_IMPATTO_TESTO`). I valori («pioggia 68%») non portano più parentesi con la
        # soglia: fino al 7/10/2026 la stessa riga diceva «oltre la soglia di impatto» due volte
        # e il 50% due volte (`docs/57` §1). Qui si verifica che una delle due dichiarazioni ci
        # sia e che nessun *altro* numero di soglia sia scritto a mano nella riga.
        dichiarate = (WEATHER_SOGLIE_TESTO in testo or WEATHER_IMPATTO_TESTO in testo
                      or "previsione pubblicata a ridosso della gara" in testo)
        if not dichiarate:
            fails.append(f"{pg.name}: il meteo non dichiara le soglie del codice")
        citate = re.findall(r"\((?:oltre la )?soglia (?:di impatto )?([^)]*)\)", testo)
        ammesse = {
            f"{WEATHER_PRECIP_SEGNALA}%", f"{WEATHER_PRECIP_IMPATTO}%",
            f"{WEATHER_TEMP_ALTA} °C", f"{WEATHER_TEMP_ALTA} °C / {WEATHER_TEMP_BASSA} °C",
            f"{WEATHER_VENTO_SEGNALA} km/h", f"{WEATHER_VENTO_IMPATTO} km/h",
        }
        for soglia in citate:
            if soglia not in ammesse:
                fails.append(f"{pg.name}: il meteo cita una soglia che non è nel codice ({soglia})")
        checks += 1
        if "estremo" in testo.lower():
            fails.append(f"{pg.name}: il meteo usa ancora «estremo» (aggettivo non misurato)")
        checks += 1
        if testo.count("oltre la soglia di impatto") > 1 or testo.count("soglie di impatto") > 1:
            fails.append(f"{pg.name}: la soglia di impatto è ripetuta nella riga del meteo")
        if impatto and "oltre la soglia di impatto" not in testo:
            fails.append(f"{pg.name}: valori oltre la soglia di impatto ma la pagina non lo dice")
        if impatto and WEATHER_IMPATTO_TESTO not in testo:
            fails.append(f"{pg.name}: soglia di impatto citata in modo diverso dal codice")
        if attenzione and not impatto and "sopra la soglia di segnalazione" not in testo:
            fails.append(f"{pg.name}: valori sopra la soglia di segnalazione ma la pagina non lo dice")
        checks += 1
        if not impatto and not attenzione and "sopra la soglia di segnalazione" in testo:
            fails.append(f"{pg.name}: la pagina segnala il meteo ma i valori non superano le soglie")
    print(f"[40] righe meteo con le soglie del codice: {n} pagine")
    return fails, checks


# La card «Fattori che spostano la partita» è stata rifatta il 7/10/2026 (`docs/57` §2): una riga
# per fattore, soglie dalle costanti `FACTOR_*`, criterio nel ⓘ, nessuna barra-percentuale. Qui si
# verifica che la pagina dica **quelle** soglie e che nessuno dei quattro fattori quantitativi sparisca
# senza dirlo: o è una riga, o è nella riga «Sotto soglia, non in tabella (casa e ospite)».
# È l'invariante [41]; senza, un fattore calcolabile ma sotto soglia usciva dalla scheda in silenzio
# (19 schede su 66 il 7/10/2026: la riga «Sotto soglia» non lo nominava e il lettore non poteva
# distinguere «squadre simili» da «dato mancante»).
FACTOR_KEYWORDS = (("valore dei titolari", "Valore di mercato titolari"),
                   ("indisponibili", "Indisponibili"),
                   ("riposo", "Riposo corto"),
                   ("pressing", "Pressing (PPDA)"),
                   # aggiunti il 2026-10-08 (docs/58 §3-§4): i due fattori misurati prima di entrare
                   ("rendimento per sede", "Rendimento per sede"),
                   ("disciplina", "Disciplina e arbitro"))
FACTOR_ROWS_AMMESSE = ("Valore di mercato titolari", "Indisponibili", "Riposo corto",
                       "Pressing (PPDA)", "Rendimento per sede", "Disciplina e arbitro",
                       "Forma e classifica (contesto)")
#: fattori che sono medie di stagione: la cella deve dire su quante gare (o «n.d.»), altrimenti un
#: numero su 4 partite sembra solido quanto uno su 30 (docs/58 §2)
FACTOR_ROWS_CAMPIONE = ("Pressing (PPDA)", "Rendimento per sede", "Disciplina e arbitro")


def _valori_di_soglia(testo: str) -> set[float]:
    """I numeri **di soglia** di una frase, normalizzati a float: «≥1,5×» → 1.5, «≤4 giorni» → 4.0.

    Guarda solo i numeri seguiti dall'unità della soglia (×, assenti, giorni, titolare, xG): un
    dato misurato come «pressing 1,04×» non è una soglia e non deve entrare nell'insieme.
    """
    return {float(m.replace(",", "."))
            for m in re.findall(r"(\d+(?:,\d+)?)\s*"
                                r"(?:×|assenti|giorni|gare|titolare|xG|pt/gara|gialli/gara|%)",
                                testo)}


def _soglie_citate(testo: str) -> set[float]:
    """I numeri citati **dopo la parola «soglia»** («(soglia ≤0,75× o ≥1,33×)» → {0.75, 1.33})."""
    out: set[float] = set()
    for blocco in re.findall(r"soglia([^)]*)", testo):
        out |= {float(m.replace(",", ".")) for m in re.findall(r"(\d+(?:,\d+)?)", blocco)}
    return out


def check_fattori(site: Path) -> tuple[list[str], int]:
    """[41] fattori: soglie dalla stessa fonte del codice, nessun fattore che sparisce in silenzio."""
    from fda.site.analysis import fattori_soglie_testo

    fails: list[str] = []
    checks = 0
    soglie = fattori_soglie_testo()
    # le soglie ammesse sono **quelle del codice**, lette dalla sua stessa frase: un numero che non
    # c'è qui non può comparire nella riga «sotto soglia» della pagina
    ammesse = _valori_di_soglia(soglie) | {1.0, 2.0, 4.0}   # «2 assenti», «1 titolare», «≤4 giorni»
    cartella = site / "partite"
    pages = sorted(cartella.glob("*.html")) if cartella.is_dir() else []
    n = 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        i = html.find('id="fattori"')
        if i < 0:
            continue
        j = html.find('<div class="card', i + 10)
        sec = html[i:j if j > 0 else len(html)]
        n += 1
        checks += 1
        if soglie not in html_unescape(sec):
            fails.append(f"{pg.name}: la card dei Fattori non cita le soglie del codice ({soglie})")
        righe = re.findall(r"<tr>\s*<th scope=\"row\">(.*?)</tr>", sec, re.DOTALL)
        if not righe:
            fails.append(f"{pg.name}: card dei Fattori senza righe")
        for r in righe:
            checks += 2
            celle = re.findall(r"<td[^>]*>(.*?)</td>", r, re.DOTALL)
            if len(celle) != 4:
                fails.append(f"{pg.name}: riga dei Fattori con {len(celle)} colonne invece di 4")
                continue
            for k, c in enumerate(celle):
                if not html_unescape(re.sub(r"<[^>]+>", "", c)).strip():
                    fails.append(f"{pg.name}: riga dei Fattori con la colonna {k + 1} vuota")
            etichetta = html_unescape(re.sub(r"<[^>]+>", "", r)).strip()
            nome = next((x for x in FACTOR_ROWS_AMMESSE if x in etichetta), None)
            if nome is None:
                fails.append(f"{pg.name}: riga dei Fattori con etichetta fuori standard "
                             f"({etichetta[:40]})")
            if 'class="help"' not in r:
                fails.append(f"{pg.name}: riga «{nome or etichetta[:30]}» senza ⓘ del criterio")
            # le medie di stagione devono dichiarare il campione nelle **celle** (non nel ⓘ, che
            # parla sempre di «gara»): senza, un PPDA su 4 gare sembra solido come uno su 30
            if nome in FACTOR_ROWS_CAMPIONE:
                celle_txt = " ".join(html_unescape(re.sub(r"<[^>]+>", " ", c)) for c in celle[:2])
                checks += 1
                if not re.search(r"\d+ gare?\)?|n\.d\.", celle_txt):
                    fails.append(f"{pg.name}: riga «{nome}» senza il numero di gare nelle celle")
        checks += 1
        # niente markdown in pagina: la card scrive il criterio in un attributo `title`, che non
        # interpreta `**grassetto**` — usciva «**non** un secondo pronostico» in 66 schede su 66
        if re.search(r"\*\*|`[^`]+`", sec):
            fails.append(f"{pg.name}: la card dei Fattori ha markdown non reso (asterischi o backtick)")
        checks += 1
        # barra-percentuale rimossa: non deve tornare (non era spiegata e su una scheda usciva al 0%)
        if re.search(r'<i style="display:block;height:100%;width:\d+%', sec):
            fails.append(f"{pg.name}: la card dei Fattori ha di nuovo la barra-percentuale")
        checks += 1
        m = re.search(r"Sotto soglia o non calcolabile, non in tabella \(casa e ospite\): (.*?)\.</p>",
                      sec, re.DOTALL)
        sotto = html_unescape(re.sub(r"<[^>]+>", " ", m.group(1))) if m else ""
        # solo le **righe** contano come «in tabella»: la riga introduttiva nomina tutte le soglie
        # (quindi tutti e quattro i fattori) e non può valere come presenza del fattore
        tabella = " ".join(html_unescape(re.sub(r"<[^>]+>", " ", r)).lower() for r in righe)
        for kw, etichetta in FACTOR_KEYWORDS:
            checks += 1
            if etichetta.lower() not in tabella and kw not in sotto.lower():
                fails.append(f"{pg.name}: fattore «{etichetta}» né in tabella né sotto soglia "
                             "(sparisce senza dirlo)")
        checks += 1
        fuori = {x for x in _soglie_citate(sotto) if x not in ammesse}
        if fuori:
            fails.append(f"{pg.name}: «sotto soglia» cita soglie fuori dalle FACTOR_* "
                         f"({sorted(fuori)})")
    print(f"[41] schede con la card dei Fattori verificate: {n} pagine")
    return fails, checks


def voci_di_gruppo(sec: str, ancora: str) -> list[str]:
    """Le voci (testo a tag rimossi) del primo elenco che segue ``ancora`` dentro ``sec``."""
    k = sec.find(ancora)
    if k < 0:
        return []
    ul = sec.find("<ul", k)
    fine = sec.find("</ul>", ul)
    if ul < 0 or fine < 0:
        return []
    return [html_unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", li))).strip()
            for li in re.findall(r"<li>(.*?)</li>", sec[ul:fine], re.DOTALL)]


def check_fatti(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[42] «Fatti rilevanti»: i fatti «dai nostri risultati» ricalcolati dai Parquet.

    La card ha due gruppi dichiarati (``id="fatti-dati"`` e ``id="fatti-fotmob"``). Qui:

    - ogni voce del gruppo **nostro** è rifatta con :func:`form_facts` sulle gare finite di
      campionato prima del calcio d'inizio: se un numero non torna o non è nell'insieme
      ricalcolato, la pagina sta pubblicando un fatto che i Parquet non sostengono;
    - la famiglia «forma recente» (``_INSIGHT_FORM_RE``) non compare **mai** nel gruppo
      FotMob: era la fotografia che invecchiava (79 fatti su 176 verificabili non tornavano
      il 2026-10-07, docs/57 §9);
    - i record di stagione verificabili («maggior numero di porte inviolate del campionato»)
      sono ricalcolati: numero uguale al nostro e pari al massimo della lega;
    - la card dichiara entrambe le origini (le due intestazioni di gruppo esistono).
    """
    import pandas as pd

    from fda.site.analysis import MatchAnalysis, form_facts
    from fda.store import Store

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    fx = st.read("fixtures")
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    if fx.empty or not pages:
        return fails, checks
    fx = fx.copy()
    fx["utc_kickoff"] = pd.to_datetime(fx.utc_kickoff, utc=True, errors="coerce")
    ma = MatchAnalysis(st)
    # le stesse forme italiane dei fatti ricalcolati: se una di queste compare nel gruppo
    # FotMob, la fotografia è tornata in pagina
    famiglia = re.compile(
        r"ha segnato \d+ gol nell|non segna da |imbattuta da |non vince da |"
        r"ha vinto le ultime |ha perso le ultime |non tiene la porta inviolata da ")
    record = re.compile(r"ha il maggior numero di porte inviolate del campionato \((\d+)\)")
    n_dati, n_fotmob = 0, 0
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        i = html.find('id="fatti"')
        if i < 0:
            continue
        j = html.find('<div class="card', i + 10)
        sec = html[i:j if j > 0 else len(html)]
        txt = html_unescape(re.sub(r"<[^>]+>", " ", sec))
        checks += 1
        mid = int(pg.stem)
        riga = fx[fx.match_id == mid]
        if riga.empty:
            continue
        r0 = riga.iloc[0]
        kickoff = r0["utc_kickoff"]
        # la card dichiara le due origini: senza, il lettore non sa quale numero invecchia
        if "Dai nostri risultati" not in txt or "FotMob" not in txt:
            fails.append(f"{pg.name}: la card dei fatti non dichiara le due origini")
        checks += 1
        if ("Dai nostri risultati" in txt) != ('id="fatti-dati"' in sec):
            fails.append(f"{pg.name}: intestazione «Dai nostri risultati» senza gruppo dati")
        checks += 1
        if ("fotografia al momento della raccolta" in txt) != ('id="fatti-fotmob"' in sec):
            fails.append(f"{pg.name}: gruppo FotMob senza la dichiarazione di fotografia")

        voci_dati = voci_di_gruppo(sec, 'id="fatti-dati"')
        voci_fotmob = voci_di_gruppo(sec, 'id="fatti-fotmob"')
        n_dati += len(voci_dati)
        n_fotmob += len(voci_fotmob)
        # 1) le voci nostre sono esattamente quelle ricalcolabili dai Parquet
        for voce in voci_dati:
            checks += 1
            # il testo a tag rimossi lascia uno spazio al posto di <b>nome</b>: «Parma : …»
            nome, _, testo = voce.partition(": ")
            nome, testo = nome.strip(), re.sub(r"\s+", " ", testo).strip()
            tid = None
            for colonna in ("home_name", "away_name"):
                if str(r0[colonna]) == nome:
                    tid = int(r0["home_id" if colonna == "home_name" else "away_id"])
                    break
            if tid is None:
                fails.append(f"{pg.name}: fatto «{voce[:60]}» di una squadra non in partita")
                continue
            gare = fx[(fx.status == "finished") & (fx.utc_kickoff < kickoff)
                      & ((fx.home_id == tid) | (fx.away_id == tid))].sort_values("utc_kickoff")
            giocate = [(r.home_goals, r.away_goals) if r.home_id == tid else (r.away_goals, r.home_goals)
                       for r in gare.tail(5).itertuples(index=False)]
            attesi = {f["text"] for f in form_facts([(int(a), int(b)) for a, b in giocate])}
            if testo not in attesi:
                fails.append(f"{pg.name}: fatto «{voce[:60]}» non ricalcolabile dai Parquet "
                             f"(attesi: {sorted(attesi)})")
        # 2) la famiglia «forma» non si pubblica mai come fotografia
        for voce in voci_fotmob:
            checks += 1
            if famiglia.search(voce):
                fails.append(f"{pg.name}: fatto FotMob della famiglia «forma» in pagina "
                             f"«{voce[:60]}» (va ricalcolato da noi)")
            m = record.search(voce)
            if m:
                checks += 1
                nome = re.sub(r"\s+", " ", voce.split(": ", 1)[0]).strip()
                tid = None
                for colonna in ("home_name", "away_name"):
                    if str(r0[colonna]) == nome:
                        tid = int(r0["home_id" if colonna == "home_name" else "away_id"])
                        break
                if tid is None or not ma.porta_inviolata_record_ok(tid, kickoff, int(m.group(1)),
                                                                  r0["league_id"]):
                    fails.append(f"{pg.name}: record di porte inviolate «{voce[:60]}» non torna "
                                 "coi Parquet")
    print(f"[42] fatti ricalcolati e fotografia FotMob verificati: {n_dati} nostre · {n_fotmob} FotMob")
    return fails, checks


def check_terza_coppia(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[43] «Come arrivano» + «I giocatori che decidono» (docs/58).

    - **finestra**: le righe di «Come arrivano» sono le gare finite più recenti (non le più
      vecchie: il ramo FotMob prendeva le 6 più vecchie, docs/58 D1) — oltre al confronto
      col ricalcolo, un controllo indipendente vieta gare con xG più recenti della finestra
      mostrata, per entrambe le fonti;
    - **tendenza**: i due numeri e il verdetto sono rifatti dai valori pieni del ricalcolo
      (la soglia è quella stampata in pagina);
    - **classifica voti**: «Per media voto di stagione» è la top-3 per media dei voti gara
      sopra la soglia di minutaggio (docs/58 D5: prima usciva su 4 schede su 66) e la soglia
      stampata è quella del codice;
    - **testi**: niente «la riga sopra» (riga rimossa), niente «sparkline» in pagina, la colonna
      «forza avv.» dichiara il rango alla vigilia (graduatoria Elo, `docs/72`), nessun link
      «Infermeria» verso la card «Indisponibili», niente «contributo offensivo atteso» per un
      valore di stagione e niente «titolare probabile» a distinta ufficiale.
    """
    import datetime
    from zoneinfo import ZoneInfo

    import pandas as pd

    from fda.config import load_leagues_config
    from fda.site.analysis import MatchAnalysis
    from fda.site.build import it_date_short
    from fda.store import Store
    from fda.teams import canonical

    fuso = ZoneInfo(load_leagues_config().get("timezone_display", "Europe/Rome"))

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    fx = st.read("fixtures")
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    if fx.empty or not pages:
        return fails, checks
    fx = fx.copy()
    fx["utc_kickoff"] = pd.to_datetime(fx.utc_kickoff, utc=True, errors="coerce")
    fx_by_id = fx.set_index("match_id")
    ts = st.read("team_stats")
    xg_ok: set[tuple[int, int]] = set()
    if not ts.empty:
        good = ts[(ts.period == "All") & (ts.key == "expected_goals") & ts.value.notna()]
        xg_ok = {(int(m), int(t)) for m, t in zip(good.match_id, good.team_id)}
    us = st.read("understat_team_matches")
    info = st.read("match_info")
    lt_of: dict[int, str] = {}
    if not info.empty and "lineup_type" in info.columns:
        lt_of = {int(m): str(v) for m, v in zip(info.match_id, info.lineup_type)}
    ma = MatchAnalysis(st)
    riga_re = re.compile(
        r'<td class="mut small">(\d{2}/\d{2})</td>\s*'
        r'<td class="small">(?:vs|@) (.*?)</td>\s*'
        r'<td class="small mut">(.*?)</td>\s*'
        r'<td class="r"><span class="pill (\w)">\w</span></td>\s*'
        r'<td class="r small">(\d+)-(\d+)</td>\s*'
        r'<td class="r small">([\d,]+)</td>\s*'
        r'<td class="r small">([\d,]+)</td>')
    # docs/59: la tendenza ora copre creato **e** concesso, da 5 gare, con il campione in pagina
    trend_re = re.compile(
        r"Gioco recente — xG <b>creati ([^<]+)</b> \(([\d,]+) → ([\d,]+) a gara, "
        r"ultime 3 contro le (\d+) precedenti\)"
        r"(?:, xG <b>concessi ([^<]+)</b> \(([\d,]+) → ([\d,]+)\))?"
        r"; soglia ±([\d,]+) xG\.")
    voti_re = re.compile(r"Per media voto di stagione</b>: (.*?)</p>", re.DOTALL)
    n_arr, n_righe, n_voti, n_voci = 0, 0, 0, 0

    def num(s: str) -> float:
        return float(s.replace(",", "."))

    for pg in pages:
        try:
            mid = int(pg.stem)
        except ValueError:
            continue
        if mid not in fx_by_id.index:
            continue
        r0 = fx_by_id.loc[mid]
        if r0["status"] == "finished":
            continue
        html = pg.read_text(encoding="utf-8")
        kick = pd.to_datetime(r0["utc_kickoff"], utc=True)
        squadre = [(int(r0["home_id"]), str(r0["home_name"])),
                   (int(r0["away_id"]), str(r0["away_name"]))]
        # ---- [43a] Come arrivano ----
        ia = html.find('id="arrivi"')
        if ia >= 0:
            ig = html.find('id="giocatori"', ia)
            blocco = html[ia:ig if ig > 0 else len(html)]
            checks += 1
            if "la riga sopra" in blocco:
                fails.append(f"{pg.name}: «Come arrivano» cita ancora «la riga sopra» rimossa")
            checks += 1
            if re.search(r"sparkline", blocco, re.IGNORECASE):
                fails.append(f"{pg.name}: «Come arrivano» con «sparkline» in pagina")
            checks += 1
            if (blocco.count("forza avv.</th>")
                    != blocco.count("graduatoria Elo del campionato alla data della gara")):
                fails.append(f"{pg.name}: colonna «forza avv.» senza dichiarazione del rango "
                             "alla vigilia")
            colonne = re.split(r"<h3[^>]*>", blocco)[1:3]
            for (tid, tnome), col in zip(squadre, colonne):
                atteso = ma.arrival_trend(tnome, tid)
                if atteso is None:
                    checks += 1
                    if "Nessuna gara precedente con xG disponibile" not in col:
                        fails.append(f"{pg.name}: lato senza arrivi senza il testo onesto")
                    continue
                n_arr += 1
                checks += 1
                if f"Fonte: {atteso['source']}." not in col:
                    fails.append(f"{pg.name}: fonte «Come arrivano» diversa dal ricalcolo")
                    continue
                mostrate = riga_re.findall(col)
                checks += 1
                if len(mostrate) != len(atteso["rows"]):
                    fails.append(f"{pg.name}: {tnome}: {len(mostrate)} righe in pagina contro "
                                 f"{len(atteso['rows'])} ricalcolate")
                    continue
                n_righe += len(mostrate)
                for (gg, _opp, _rank, res, gf, ga, xg, xga), riga in zip(mostrate, atteso["rows"]):
                    checks += 1
                    want_res = "V" if riga["gf"] > riga["ga"] else ("N" if riga["gf"] == riga["ga"] else "P")
                    if (res != want_res or int(gf) != riga["gf"] or int(ga) != riga["ga"]
                            or gg != it_date_short(riga["date"], fuso)
                            or abs(num(xg) - round(riga["xg"], 2)) > 0.005
                            or abs(num(xga) - round(riga["xga"], 2)) > 0.005):
                        fails.append(f"{pg.name}: {tnome}: riga {gg} diversa dal ricalcolo")
                    # docs/72: la colonna «forza avv.» è il rango **alla vigilia** (graduatoria
                    # Elo del campionato alla data della gara), non la classifica di oggi
                    checks += 1
                    m_rank = re.search(r">(\d+)ª", _rank)
                    if riga.get("opp_rank") is None:
                        if m_rank:
                            fails.append(f"{pg.name}: {tnome}: riga {gg} pubblica un rango "
                                         "senza Elo dell'avversario alla vigilia")
                    elif not m_rank or int(m_rank.group(1)) != int(riga["opp_rank"]):
                        fails.append(f"{pg.name}: {tnome}: riga {gg} rango in pagina ≠ "
                                     f"ricalcolo alla vigilia ({riga['opp_rank']}ª)")
                # freschezza indipendente dal codice: nessuna gara con xG più recente della finestra
                # mostrata (le date in pagina sono giorno/mese: l'anno si inferisce dal calcio
                # d'inizio, la stagione è a cavallo di due anni)
                checks += 1
                km, ky = kick.month, kick.year
                shown_max = max(
                    datetime.date(ky if int(gg.split("/")[1]) <= km else ky - 1,
                                  int(gg.split("/")[1]), int(gg.split("/")[0]))
                    for gg, *_r in mostrate)
                if atteso["source"] == "FotMob":
                    base = fx[(fx.status == "finished")
                              & ((fx.home_id == tid) | (fx.away_id == tid))]
                    fresche = [pd.to_datetime(r.utc_kickoff, utc=True).tz_convert(fuso).date()
                               for r in base.itertuples()
                               if (int(r.match_id), tid) in xg_ok
                               and (int(r.match_id), int(r.away_id if r.home_id == tid else r.home_id)) in xg_ok]
                else:
                    usar = us[us.team_name.map(canonical) == canonical(tnome)] if not us.empty else us
                    fresche = [pd.to_datetime(d, utc=True, errors="coerce").tz_convert(fuso).date()
                               for d in usar["date"]] if not usar.empty else []
                    fresche = [d for d in fresche if pd.notna(d)]
                if any(d > shown_max for d in fresche):
                    fails.append(f"{pg.name}: {tnome}: finestra «Come arrivano» non fresca "
                                 "(gare con xG più recenti fuori dalla tabella)")
                # tendenza rifatta dai valori pieni del ricalcolo: le medie in pagina sono
                # arrotondate una sola volta, rifarle dai mostrati accumulerebbe errori (3 casi
                # oltre 0,005 il 2026-10-07); il verdetto riusa la soglia stampata in pagina
                if len(mostrate) >= 5:
                    m = trend_re.search(col)
                    checks += 1
                    if not m:
                        fails.append(f"{pg.name}: {tnome}: {len(mostrate)} righe senza frase di tendenza")
                    else:
                        checks += 1
                        xv = [riga["xg"] for riga in atteso["rows"]]
                        xav = [riga["xga"] for riga in atteso["rows"]]
                        nb = len(xv) - 3
                        rec, prima = sum(xv[-3:]) / 3, sum(xv[:-3]) / nb
                        soglia = num(m.group(8))
                        want = ("in crescita" if rec - prima > soglia
                                else ("in calo" if rec - prima < -soglia else "stabile"))
                        ok = (m.group(1) == want and atteso["trend"] == want
                              and int(m.group(4)) == nb
                              and abs(num(m.group(2)) - round(prima, 2)) <= 0.005
                              and abs(num(m.group(3)) - round(rec, 2)) <= 0.005
                              and abs(soglia - 0.15) <= 1e-9)
                        if m.group(5):                    # lato concesso, se la pagina lo stampa
                            arec, aprima = sum(xav[-3:]) / 3, sum(xav[:-3]) / nb
                            want_a = ("in crescita" if arec - aprima > soglia
                                      else ("in calo" if arec - aprima < -soglia else "stabile"))
                            ok = ok and (m.group(5) == want_a
                                         and abs(num(m.group(6)) - round(aprima, 2)) <= 0.005
                                         and abs(num(m.group(7)) - round(arec, 2)) <= 0.005)
                        if not ok:
                            fails.append(f"{pg.name}: {tnome}: tendenza non ricalcolabile "
                                         f"({m.group(1)} {m.group(2)}/{m.group(3)})")
        # ---- [43b] I giocatori che decidono ----
        ig = html.find('id="giocatori"')
        if ig >= 0:
            isq = html.find('id="squadre"', ig)
            blocco = html[ig:isq if isq > 0 else len(html)]
            checks += 1
            if ">Infermeria</a>" in blocco:
                fails.append(f"{pg.name}: link «Infermeria» verso la card «Indisponibili»")
            checks += 1
            if "contributo offensivo atteso" in blocco:
                fails.append(f"{pg.name}: «contributo offensivo atteso» per un valore di stagione")
            if lt_of.get(mid) == "official":
                checks += 1
                if "titolare probabile" in blocco:
                    fails.append(f"{pg.name}: «titolare probabile» a distinta ufficiale")
            liste = voti_re.findall(blocco)
            colonne = re.split(r"<h3[^>]*>", blocco)[1:3]
            voti = {tid: ma.team_key_players(tid) for tid, _tnome in squadre}
            for (tid, _tnome), col in zip(squadre, colonne):
                deep = ma.key_players_deep(tid)
                if deep is not None:
                    checks += 1
                    n_voti += 1
                    if f"Soglia di minutaggio: {deep['floor']} minuti" not in col:
                        fails.append(f"{pg.name}: soglia di minutaggio diversa dal ricalcolo")
                    for mm in re.findall(r'<td class="r small mut">(\d+)</td>', col):
                        checks += 1
                        if int(mm) < deep["floor"]:
                            fails.append(f"{pg.name}: riga dei decisivi sotto la soglia ({mm}′)")
            for nome in [html_unescape(re.sub(r"<[^>]+>", "", frag)) for frag in liste]:
                for voce in nome.split(" · "):
                    if " " not in voce.strip():
                        continue
                    chi, voto = voce.strip().rsplit(" ", 1)
                    checks += 1
                    n_voci += 1
                    ok = any(p["name"] == chi and abs(p["rating_avg"] - num(voto)) < 0.005
                             for _t in voti for p in voti[_t])
                    if not ok:
                        fails.append(f"{pg.name}: voto «{voce.strip()[:50]}» non ricalcolabile")
    print(f"[43] come-arrivano e giocatori-che-decidono: {n_arr} lati ({n_righe} righe), "
          f"{n_voti} soglie, {n_voci} voci di voto")
    return fails, checks


def check_forza_avversari_storica(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[45] «Come arrivano»: la colonna «forza avv.» è il rango **alla vigilia** (oracolo).

    Chiude l'anacronismo dichiarato in `docs/60` §5 (la colonna mostrava la classifica a
    punti di **oggi** su gare passate) con la correzione di `docs/72`: rango nella
    graduatoria Elo del campionato alla data della gara ed Elo storico nel ⓘ. Il
    ricalcolo usa l'oracolo cronologico di [44] (`elo_reference_at_dates`: stesso flusso
    di risultati, fotografato prima di ogni istante) — **non** `team_elo`/`league_elo`/
    `arrival_trend` del generatore, così una regressione temporale non si autocertifica.
    """
    import datetime
    from zoneinfo import ZoneInfo

    import pandas as pd

    from fda.config import load_leagues_config
    from fda.site.analysis import MatchAnalysis
    from fda.store import Store
    from fda.teams import canonical

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    fx = st.read("fixtures")
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    if fx.empty or not pages:
        return fails, checks
    fx = fx.copy()
    fx["utc_kickoff"] = pd.to_datetime(fx.utc_kickoff, utc=True, errors="coerce")
    fx_ids = set(fx.match_id.astype(int))
    fuso = ZoneInfo(load_leagues_config().get("timezone_display", "Europe/Rome"))
    fin = fx[fx.status == "finished"]
    riga_re = re.compile(
        r'<td class="mut small">(\d{2}/\d{2})</td>\s*'
        r'<td class="small">(?:vs|@) (.*?)</td>\s*'
        r'<td class="small mut">(.*?)</td>\s*'
        r'<td class="r"><span class="pill \w">\w</span></td>')
    cella_re = re.compile(
        r'<span class="form-opp-rank" title="[^"]*?: ([\d.]+)\.[^"]*">(\d+)ª ⓘ</span>')
    # (pagina, squadra, data italiana, avversario canonico, nome, rango, Elo) delle righe
    pubblicate: list[tuple] = []
    for pg in pages:
        try:
            mid = int(pg.stem)
        except ValueError:
            continue
        if mid not in fx_ids:
            continue
        r0 = fx[fx.match_id == mid].iloc[0]
        if r0["status"] == "finished":
            continue
        html = pg.read_text(encoding="utf-8")
        ia = html.find('id="arrivi"')
        if ia < 0:
            continue
        ig = html.find('id="giocatori"', ia)
        blocco = html[ia:ig if ig > 0 else len(html)]
        kick = r0["utc_kickoff"]
        colonne = re.split(r"<h3[^>]*>", blocco)[1:3]
        squadre = [(int(r0["home_id"]), str(r0["home_name"])),
                   (int(r0["away_id"]), str(r0["away_name"]))]
        for (tid, tnome), col in zip(squadre, colonne):
            for gg, opp, cella in riga_re.findall(col):
                checks += 1
                nome = html_unescape(opp).strip()
                if not nome or nome == "—":
                    continue    # riga senza avversario: nessuna «forza avv.» da verificare
                mm, dd = int(gg.split("/")[1]), int(gg.split("/")[0])
                anno = kick.year if mm <= kick.month else kick.year - 1
                m = cella_re.search(cella)
                pubblicate.append((pg.name, tid, tnome, datetime.date(anno, mm, dd),
                                   canonical(nome), nome,
                                   int(m.group(2)) if m else None,
                                   int(m.group(1).replace(".", "")) if m else None))
    # ---- ogni riga si appoggia a una gara finite del calendario (avversario + data)
    gara_of: dict[tuple, tuple] = {}
    for r in fin.itertuples(index=False):
        ko = r.utc_kickoff
        d_it = ko.tz_convert(fuso).date() if pd.notna(ko) else None
        if d_it is None:
            continue
        for tid, opp in ((int(r.home_id), canonical(str(r.away_name))),
                         (int(r.away_id), canonical(str(r.home_name)))):
            gara_of.setdefault((tid, d_it, opp), (ko, r.league_id))
    tagli = sorted({gara_of[(t, d, o)][0] for (_p, t, _n, d, o, *_r) in pubblicate
                    if (t, d, o) in gara_of})
    ratings_at, leagues_at = elo_reference_at_dates(
        st.read("history"), fx, tagli, min_teams=MatchAnalysis.ELO_MIN_TEAMS)
    n_righe = 0
    for pagina, tid, tnome, data_it, opp_c, opp_raw, rango_pub, elo_pub in pubblicate:
        n_righe += 1
        checks += 1
        if (tid, data_it, opp_c) not in gara_of:
            fails.append(f"{pagina}: {tnome} {data_it:%d/%m} vs {opp_raw}: riga senza gara "
                         "corrispondente nel calendario (avversario o data)")
            continue
        ko, lg = gara_of[(tid, data_it, opp_c)]
        ref = leagues_at.get((lg, ko))
        rango = ref["ranks"].get(opp_c) if ref else None
        rating = ratings_at.get(ko, {}).get(opp_c)
        if rango is None:
            if rango_pub is not None:
                fails.append(f"{pagina}: {tnome} {data_it:%d/%m} vs {opp_raw}: rango "
                             f"{rango_pub}ª senza graduatoria Elo alla vigilia")
        elif rango_pub != rango:
            fails.append(f"{pagina}: {tnome} {data_it:%d/%m} vs {opp_raw}: rango {rango_pub}ª "
                         f"≠ oracolo {rango}ª (vigilia)")
        if rango_pub is not None:
            checks += 1
            if rating is None or elo_pub != round(rating):
                fails.append(f"{pagina}: {tnome} {data_it:%d/%m} vs {opp_raw}: Elo {elo_pub} "
                             f"≠ oracolo {None if rating is None else round(rating)}")
    print(f"[45] forza avv. alla vigilia (oracolo): {n_righe} righe, {len(tagli)} istanti Elo")
    return fails, checks


# --------------------------------------------------------------------------------- [46]
# Il card «laboratorio» (docs/73) pubblica per ogni idea il what-if su quella partita: λ
# inclinata e 1X2 ricalcolata. Le tre formule qui sotto sono **riscritte per conto proprio**
# dalle regole dichiarate (docs/69 §1, docs/71 §3, docs/73 §3) e NON importano
# `fda.models.predict`: è lo schema degli oracoli di [44] e [45] — se il card e il modello
# sbagliassero insieme, qui si vedrebbe. La griglia Dixon-Coles resta invece quella
# condivisa (`dc_grid.tau_grid`): il progetto ne ha una sola per modelli, calibrazione e
# sito, e duplicarla sarebbe il modo più sicuro di far divergere due pagine.
MERCATO_K = 0.12
MERCATO_CLIP = (0.2, 5.0)
#: k con cui il card calcola il what-if **pubblicato** (`docs/74` §10): il mercato usa l'unico
#: k con un intervallo di confidenza fuori dallo zero (0,03, `docs/69` §1); le assenze non ne
#: hanno nessuno sostenuto e usano il tetto della griglia preregistrata (0,20, `docs/71` §3).
#: La costante nel codice (0,12 e 0,30) è pubblicata accanto come confronto: [46] verifica entrambe.
MERCATO_K_SOSTENUTO = 0.03
ASSENZE_K_PROTOCOLLO = 0.20
ASSENZE_K = 0.30
ASSENZE_AVG = 2.0
ASSENZE_CLIP = (0.70, 1.00)
RIPOSO_BREVE, RIPOSO_CORTO, RIPOSO_LUNGO = 2, 4, 7
RIPOSO_FATTORI = (0.95, 0.98, 1.02)


def _lab_mercato(lh: float, la: float, hv: float | None, av: float | None,
                 k: float = MERCATO_K) -> tuple[float, float]:
    """λ inclinate dal rapporto dei valori: (rapporto clip)**k sul rapporto, totale invariato."""
    if hv is None or av is None or hv <= 0 or av <= 0 or la <= 0 or (lh + la) <= 0:
        return lh, la
    lo, hi = MERCATO_CLIP
    adj = min(max(hv / av, lo), hi) ** k
    totale = lh + la
    r = (lh / la) * (adj ** 2)
    return (totale * r / (1.0 + r), totale / (1.0 + r))


def _lab_assenze(lh: float, la: float, ch: float | None, ca: float | None,
                 k: float = ASSENZE_K) -> tuple[float, float]:
    """λ × (1 − k · perso/2) per squadra, fattore in [0,70; 1,00], poi totale rinormalizzato."""
    lh_f, la_f = float(lh), float(la)
    totale = lh_f + la_f
    lo, hi = ASSENZE_CLIP
    if ch is not None and ch > 0:
        lh_f *= min(max(1.0 - k * float(ch) / ASSENZE_AVG, lo), hi)
    if ca is not None and ca > 0:
        la_f *= min(max(1.0 - k * float(ca) / ASSENZE_AVG, lo), hi)
    nuovo = lh_f + la_f
    if nuovo > 0 and totale > 0:
        lh_f *= totale / nuovo
        la_f *= totale / nuovo
    return (max(0.25, lh_f), max(0.25, la_f))


def _lab_riposo(lh: float, la: float, rh: float | None, ra: float | None) -> tuple[float, float]:
    """Fattore per giorni di riposo (≤2 → 0,95 · ≤4 → 0,98 · ≥7 → 1,02), totale invariato."""

    def fattore(giorni: float | None) -> float | None:
        if giorni is None:
            return None
        g = int(giorni)
        if g <= RIPOSO_BREVE:
            return RIPOSO_FATTORI[0]
        if g <= RIPOSO_CORTO:
            return RIPOSO_FATTORI[1]
        if g >= RIPOSO_LUNGO:
            return RIPOSO_FATTORI[2]
        return 1.0

    fh, fa = fattore(rh), fattore(ra)
    lh_f, la_f = float(lh), float(la)
    totale = lh_f + la_f
    if fh is not None:
        lh_f *= fh
    if fa is not None:
        la_f *= fa
    if fh is not None or fa is not None:
        nuovo = lh_f + la_f
        if nuovo > 0 and totale > 0:
            lh_f *= totale / nuovo
            la_f *= totale / nuovo
    return (max(0.25, lh_f), max(0.25, la_f))


def _lab_1x2(lh: float, la: float, rho: float) -> tuple[float, float, float]:
    """1X2 dalla griglia condivisa: le tre somme che la pagina pubblica."""
    import numpy as np

    from fda.models.dc_grid import GRID_SIZE, tau_grid

    g = tau_grid(lh, la, rho, size=GRID_SIZE)
    i, j = np.indices(g.shape)
    return (float(g[i > j].sum()), float(g[i == j].sum()), float(g[i < j].sum()))


_LAB_CARD_RE = re.compile(
    r'<div class="card detail-card" id="laboratorio"\s+data-lh="([-\d.]+)" data-la="([-\d.]+)" '
    r'data-p1="(\d+)" data-px="(\d+)" data-p2="(\d+)">(.*?)\n</div>', re.DOTALL)
_LAB_RIGA_RE = re.compile(
    r'<tr data-idea="([a-z]+)" data-in-h="([^"]*)" data-in-a="([^"]*)" '
    r'data-lh="([-\d.]+)" data-la="([-\d.]+)" data-p1="(\d+)" data-px="(\d+)" data-p2="(\d+)"'
    r'(?: data-lh2="([-\d.]+)" data-la2="([-\d.]+)" data-q1="(\d+)" data-qx="(\d+)" '
    r'data-q2="(\d+)")?>')


def check_laboratorio(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[46] card «laboratorio»: il what-if ricalcolato senza le formule del modello.

    Chiude la condizione 5 di `docs/73` §5: le λ e l'1X2 che il card attribuisce alle tre
    idee (mercato, assenze, riposo) devono poter essere rifatte **da zero** — formule
    riscritte in questo file, input riletti dai Parquet — e combaciare con ciò che la
    pagina stampa. Così il card non può raccontare un effetto diverso da quello che le
    regole dichiarate producono, e la previsione salvata resta l'unica previsione.

    Indipendenza, con onestà: gli **input** sono ricalcolati qui (riposo dal calendario
    campionato + coppe, valore dei titolari da `match_info`); il contributo perso degli
    indisponibili usa il lettore condiviso `MatchAnalysis.absences_weight`, perché è la
    somma stabilizzata di una colonna già verificata da [44] — qui si controlla che il
    card la usi, non si rifà la stabilizzazione.
    """
    import pandas as pd

    from fda.site.analysis import MatchAnalysis
    from fda.store import Store

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    preds = st.read("predictions")
    fx = st.read("fixtures")
    info = st.read("match_info")
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    if preds.empty or fx.empty or not pages:
        return fails, checks
    fx = fx.copy()
    fx["utc_kickoff"] = pd.to_datetime(fx.utc_kickoff, utc=True, errors="coerce")
    # ---- oracolo del calendario: campionato + coppe (lo stesso principio di `rest_days`)
    colonne = ["match_id", "utc_kickoff", "status", "home_id", "away_id"]
    cal = fx[colonne]
    # tabella assente (run senza coppe): `Store.read` restituisce un DataFrame vuoto
    cup = st.read("cup_fixtures")
    if not cup.empty:
        cup = cup.copy()
        cup["utc_kickoff"] = pd.to_datetime(cup.utc_kickoff, utc=True, errors="coerce")
        cal = pd.concat([cal, cup[colonne]], ignore_index=True, sort=False)
    finiti = cal[cal.status == "finished"].dropna(subset=["utc_kickoff"])

    def riposo(tid: int, kickoff) -> int | None:
        if pd.isna(kickoff):
            return None
        prima = finiti[(finiti.utc_kickoff < kickoff)
                       & ((finiti.home_id == tid) | (finiti.away_id == tid))]
        if prima.empty:
            return None
        return int((kickoff - prima.utc_kickoff.max()).total_seconds() // 86400)

    if "match_id" in preds.columns and "made_at" in preds.columns:
        preds = preds.sort_values("made_at").groupby("match_id", as_index=False).tail(1)
    pred_idx = preds.set_index("match_id") if "match_id" in preds.columns else None
    info_idx = (info.set_index("match_id")
                if not info.empty and "match_id" in info.columns else None)
    fx_idx = fx.set_index("match_id")
    # lettore condiviso per gli indisponibili: la somma stabilizzata di una colonna che [44]
    # verifica già riga per riga — qui si controlla che il card la usi per il what-if.
    ma = MatchAnalysis(st)

    def perso(match_id: int, tid: int) -> float | None:
        """xG+xA/90 persi: ``None`` = la fonte non pubblica la distinta, ``0.0`` = nessun assente."""
        ab = ma.absences_weight(match_id, tid)
        if ab is not None:
            v = ab.get("contrib_lost_p90")
            return 0.0 if v is None else round(float(v), 2)
        # nessun indisponibile: se la distinta c'è è uno zero misurato, altrimenti è un dato
        # che la fonte non pubblica e tale resta (nessuno «0» inventato dal controllo).
        if not ma.lineup.empty and ((ma.lineup.match_id == match_id)
                                    & (ma.lineup.team_id == tid)).any():
            return 0.0
        return None

    n_pagine = 0
    n_righe = 0
    for pg in pages:
        try:
            mid = int(pg.stem)
        except ValueError:
            continue
        html = pg.read_text(encoding="utf-8")
        m = _LAB_CARD_RE.search(html)
        if not m:
            continue
        if pred_idx is None or mid not in pred_idx.index or mid not in fx_idx.index:
            fails.append(f"{pg.name}: card «laboratorio» senza previsione o calendario")
            continue
        riga_fx = fx_idx.loc[mid]
        pred = pred_idx.loc[mid]
        n_pagine += 1
        lh, la = float(pred["lambda_home"]), float(pred["lambda_away"])
        # ρ non è pubblicato in pagina: si legge dalla riga salvata (0 se la colonna manca,
        # come fanno il modello e la griglia quando il dato non c'è)
        rho = 0.0
        if "dc_rho" in preds.columns and pd.notna(pred["dc_rho"]):
            rho = float(pred["dc_rho"])
        checks += 2
        # la base del card è la previsione salvata: λ e 1X2 devono essere le sue
        if abs(float(m.group(1)) - lh) > 0.005 + 1e-9 or abs(float(m.group(2)) - la) > 0.005 + 1e-9:
            fails.append(f"{pg.name}: λ di partenza del card {m.group(1)}/{m.group(2)} ≠ "
                         f"previsione salvata {lh:.2f}/{la:.2f}")
        base_pub = [int(m.group(3)), int(m.group(4)), int(m.group(5))]
        base_grezzi = _lab_1x2(lh, la, rho)          # griglia del modello, come il generatore
        if not terna_valida(base_grezzi, 0, base_pub):
            fails.append(f"{pg.name}: 1X2 di partenza del card {base_pub} non è un arrotondamento "
                         f"legittimo di {[round(v, 4) for v in base_grezzi]} "
                         f"(riferimento {terna_indip(base_grezzi)})")

        kickoff = riga_fx.utc_kickoff
        previsti = {
            "mercato": None,
            "assenze": (perso(mid, int(riga_fx.home_id)), perso(mid, int(riga_fx.away_id))),
            "riposo": (riposo(int(riga_fx.home_id), kickoff), riposo(int(riga_fx.away_id), kickoff)),
        }
        if info_idx is not None and mid in info_idx.index:
            hv = info_idx.loc[mid].get("home_starters_value_eur")
            av = info_idx.loc[mid].get("away_starters_value_eur")
            hv = None if hv is None or pd.isna(hv) or float(hv) <= 0 else round(float(hv))
            av = None if av is None or pd.isna(av) or float(av) <= 0 else round(float(av))
            previsti["mercato"] = (hv, av) if (hv is not None and av is not None) else (None, None)
        for riga in _LAB_RIGA_RE.finditer(m.group(6)):
            n_righe += 1
            idea, ih_p, ia_p = riga.group(1), riga.group(2), riga.group(3)
            checks += 1
            atteso = previsti.get(idea)
            if atteso is None:
                continue
            ih_a, ia_a = atteso

            def _num(txt: str) -> float | None:
                return float(txt) if txt not in ("", None) else None

            checks += 2
            if _num(ih_p) != ih_a or _num(ia_p) != ia_a:
                fails.append(f"{pg.name}: {idea}, dato usato {ih_p or 'n.d.'}/{ia_p or 'n.d.'} "
                             f"≠ ricalcolato {ih_a}/{ia_a}")
                continue        # con l'input sbagliato, λ e 1X2 non sono giudicabili
            if idea == "mercato":
                k, k_decl = MERCATO_K_SOSTENUTO, MERCATO_K
                lh2, la2 = _lab_mercato(lh, la, ih_a, ia_a, k=k)
            elif idea == "assenze":
                k, k_decl = ASSENZE_K_PROTOCOLLO, ASSENZE_K
                lh2, la2 = _lab_assenze(lh, la, ih_a, ia_a, k=k)
            else:
                k = k_decl = None
                lh2, la2 = _lab_riposo(lh, la, ih_a, ia_a)
            checks += 2
            if (abs(float(riga.group(4)) - lh2) > 0.005 + 1e-9
                    or abs(float(riga.group(5)) - la2) > 0.005 + 1e-9):
                fails.append(f"{pg.name}: {idea}, λ {riga.group(4)}/{riga.group(5)} "
                             f"≠ ricalcolato {lh2:.2f}/{la2:.2f} (k={k})")
                continue
            pub = [int(riga.group(6)), int(riga.group(7)), int(riga.group(8))]
            grezzi2 = _lab_1x2(lh2, la2, rho)
            checks += 1
            if not terna_valida(grezzi2, 0, pub):
                fails.append(f"{pg.name}: {idea}, 1X2 {pub} non è un arrotondamento legittimo "
                             f"(riferimento {terna_indip(grezzi2)}, λ {lh2:.2f}/{la2:.2f}, k={k})")
            # ---- seconda coppia: lo stesso what-if con la costante dichiarata nel codice,
            #      pubblicata sotto per confronto (`docs/74` §10). Se manca in pagina ma il
            #      k dichiarato esiste (o viceversa), la riga non racconta la stessa regola.
            if riga.group(9) and k_decl is not None:
                if idea == "mercato":
                    lh3, la3 = _lab_mercato(lh, la, ih_a, ia_a, k=k_decl)
                else:
                    lh3, la3 = _lab_assenze(lh, la, ih_a, ia_a, k=k_decl)
                checks += 2
                if (abs(float(riga.group(9)) - lh3) > 0.005 + 1e-9
                        or abs(float(riga.group(10)) - la3) > 0.005 + 1e-9):
                    fails.append(f"{pg.name}: {idea}, λ di confronto {riga.group(9)}/"
                                 f"{riga.group(10)} ≠ ricalcolato {lh3:.2f}/{la3:.2f} "
                                 f"(k={k_decl})")
                else:
                    q = [int(riga.group(11)), int(riga.group(12)), int(riga.group(13))]
                    grezzi3 = _lab_1x2(lh3, la3, rho)
                    checks += 1
                    if not terna_valida(grezzi3, 0, q):
                        fails.append(f"{pg.name}: {idea}, 1X2 di confronto {q} non è un "
                                     f"arrotondamento legittimo (riferimento "
                                     f"{terna_indip(grezzi3)}, k={k_decl})")
            elif k_decl is not None and ih_a is not None:
                fails.append(f"{pg.name}: {idea}: manca il confronto con il k dichiarato "
                             f"({k_decl}) pubblicato accanto al what-if")
    print(f"[46] card «laboratorio»: {n_pagine} pagine, {n_righe} righe what-if ricalcolate")
    return fails, checks


def check_confronto_stagione(site: Path, data: Path | None) -> tuple[list[str], int]:
    """[45] card «Confronto di stagione»: ogni numero ricalcolato dalle classifiche (docs/76 §8).

    Prima di questa invariante la card non aveva alcuna copertura numerica: il difetto
    «Nª su 20» nelle quattro leghe a 18 squadre (257 pagine) è rimasto invisibile a tutti i
    gate. L'oracolo rilegge ``fotmob_standings`` (riserva ``espn_standings``) con la stessa
    precedenza del generatore e verifica, per ogni pagina con la card: posizione e barra
    (scala sul numero **vero** di squadre del campionato), punti e punti/gara, V-N-P, gol
    fatti/subiti per gara, differenza reti, i rapporti «× media campionato» (media gol della
    stessa tabella), le evidenziazioni, il titolo della riga «Punti», il divario in punti e
    la dichiarazione dell'orologio nella nota.
    """
    import pandas as pd

    from fda.site.fmt import dec, it_plural
    from fda.store import Store
    from fda.teams import canonical

    fails: list[str] = []
    checks = 0
    st = Store(data) if data else Store()
    fx = st.read("fixtures")
    pages = sorted((site / "partite").glob("*.html")) if (site / "partite").is_dir() else []
    if fx.empty or not pages:
        return fails, checks
    by_id = fx.drop_duplicates("match_id").set_index("match_id")
    tabelle = [df for df in (st.read("fotmob_standings"), st.read("espn_standings"))
               if not df.empty and "team_name" in df.columns]

    def squadra(nome: str) -> tuple[Any, Any]:
        """Riga di classifica e tabella di provenienza, con la precedenza del generatore."""
        c = canonical(nome)
        for df in tabelle:
            righe = df[df.team_name.map(canonical) == c]
            if not righe.empty:
                return righe.iloc[0], df
        return None, None

    def lato(riga_cls: Any) -> dict[str, Any] | None:
        if riga_cls is None:
            return None
        p = float(riga_cls["played"])
        if p <= 0:
            return None
        return {"rank": int(riga_cls["rank"]), "p": p,
                "pts": float(riga_cls["points"]), "ppg": float(riga_cls["points"]) / p,
                "gf": float(riga_cls["goals_for"]) / p,
                "ga": float(riga_cls["goals_against"]) / p,
                "diff": int(riga_cls["goal_diff"]),
                "wdl": f"{int(riga_cls['wins'])}-{int(riga_cls['draws'])}-{int(riga_cls['losses'])}"}

    def media_gol(df: Any, code: Any) -> dict[str, float] | None:
        righe = df[df.league_code == code] if "league_code" in df.columns and code else df.iloc[0:0]
        giocate = pd.to_numeric(righe["played"], errors="coerce").sum()
        if giocate <= 0:
            return None
        return {"gf": pd.to_numeric(righe["goals_for"], errors="coerce").sum() / giocate,
                "ga": pd.to_numeric(righe["goals_against"], errors="coerce").sum() / giocate}

    def attesa_best(key_h: float | None, key_a: float | None, higher: bool = True) -> str | None:
        if key_h is None or key_a is None or key_h == key_a:
            return None
        return "h" if (key_h > key_a) == higher else "a"

    for pg in pages:
        if not pg.stem.isdigit():
            continue
        mid = int(pg.stem)
        if mid not in by_id.index:
            continue
        riga = by_id.loc[mid]
        html = pg.read_text(encoding="utf-8")
        m = re.search(r'id="confronto".*?</table>', html, re.DOTALL)
        h_st, h_df = squadra(str(riga.home_name))
        a_st, a_df = squadra(str(riga.away_name))
        checks += 1
        if h_st is None and a_st is None:
            if m:
                fails.append(f"{pg.name}: «Confronto di stagione» pubblicata senza classifica "
                             "per nessuna delle due squadre")
            continue
        if not m:
            fails.append(f"{pg.name}: «Confronto di stagione» assente con almeno una squadra "
                         "in classifica")
            continue
        sec = m.group(0)
        h, a = lato(h_st), lato(a_st)
        # ogni riga: (attr del th, attr td casa, cella casa, attr td trasferta, cella trasferta)
        righe_html = {lab: (th_attr, h_attr, h_html, a_attr, a_html) for th_attr, lab,
                      h_attr, h_html, a_attr, a_html in re.findall(
                          r'<tr><th scope="row"([^>]*)>([^<]+)</th>'
                          r'<td([^>]*)>(.*?)</td><td([^>]*)>(.*?)</td></tr>', sec, re.DOTALL)}
        if not righe_html:
            fails.append(f"{pg.name}: tabella del confronto non letta")
            continue
        # numero di squadre contato nella tabella della squadra disponibile (casa prima)
        st_rif, df_rif = (h_st, h_df) if h_st is not None else (a_st, a_df)
        n_sq = None
        if df_rif is not None and "league_code" in df_rif.columns:
            contate = int((df_rif.league_code == st_rif["league_code"]).sum())
            n_sq = contate if contate >= 2 else None
        n_sq = n_sq or 20

        def testo(html_cella: str) -> str:
            return re.sub(r"<[^>]+>", "", html_cella).strip()

        nome_h, nome_a = str(riga.home_name), str(riga.away_name)
        # --- posizione: valore, barra e «Nª su n» sul numero vero di squadre -------------
        if "Posizione" in righe_html:
            for lato_key, lato_v, nome in (("h", h, nome_h), ("a", a, nome_a)):
                cella = righe_html["Posizione"][2] if lato_key == "h" else righe_html["Posizione"][4]
                checks += 1
                if lato_v is None:
                    if testo(cella) != "—":
                        fails.append(f"{pg.name}: posizione di {nome} senza classifica ≠ «—»")
                    continue
                # la cella stampa il rango e poi il suffisso «Nª su n»: il rango si
                # controlla sul suffisso, l'attacco del testo sul rango stesso
                barra = re.search(r"width:([\d.]+)%", cella)
                suffisso = re.search(r"(\d+)ª su (\d+)", cella)
                if not barra or not suffisso:
                    fails.append(f"{pg.name}: barra o suffisso della posizione di {nome} mancanti")
                    continue
                if not testo(cella).startswith(str(lato_v["rank"])) or \
                        int(suffisso.group(1)) != lato_v["rank"]:
                    fails.append(f"{pg.name}: posizione di {nome} {testo(cella)!r}, "
                                 f"attesa {lato_v['rank']}")
                checks += 2
                attesa = round((n_sq - lato_v["rank"]) / (n_sq - 1) * 100)
                if abs(float(barra.group(1)) - attesa) > 0.51:
                    fails.append(f"{pg.name}: barra posizione di {nome} {barra.group(1)}%, "
                                 f"attesa {attesa}% su {n_sq} squadre")
                if int(suffisso.group(2)) != n_sq:
                    fails.append(f"{pg.name}: «su {suffisso.group(2)}» dichiarato ma il "
                                 f"campionato ha {n_sq} squadre ({nome})")
        # --- righe numeriche --------------------------------------------------------------
        medie = media_gol(df_rif, st_rif["league_code"]) if df_rif is not None else None
        attesi = {
            "Punti": (f"{h['pts']:.0f} in {it_plural(h['p'], 'gara')}" if h else "—",
                      f"{a['pts']:.0f} in {it_plural(a['p'], 'gara')}" if a else "—",
                      attesa_best(h and h["ppg"], a and a["ppg"])),
            "Punti/gara": (dec(h["ppg"]) if h else "—", dec(a["ppg"]) if a else "—",
                           attesa_best(h and h["ppg"], a and a["ppg"])),
            "Risultati (V-N-P)": (h["wdl"] if h else "—", a["wdl"] if a else "—", None),
            "Gol fatti/gara": (dec(h["gf"]) if h else "—", dec(a["gf"]) if a else "—",
                               attesa_best(h and h["gf"], a and a["gf"])),
            "Gol subiti/gara": (dec(h["ga"]) if h else "—", dec(a["ga"]) if a else "—",
                                attesa_best(h and h["ga"], a and a["ga"], higher=False)),
            "Differenza reti": ((f"+{h['diff']}" if h["diff"] > 0 else str(h["diff"])) if h else "—",
                                (f"+{a['diff']}" if a["diff"] > 0 else str(a["diff"])) if a else "—",
                                attesa_best(h and h["diff"], a and a["diff"])),
        }
        if medie:
            attesi["Attacco (× media campionato)"] = (
                dec(h["gf"] / medie["gf"]) if h else "—",
                dec(a["gf"] / medie["gf"]) if a else "—",
                attesa_best(h and h["gf"] / medie["gf"], a and a["gf"] / medie["gf"]))
            attesi["Difesa (× media campionato)"] = (
                dec(h["ga"] / medie["ga"]) if h else "—",
                dec(a["ga"] / medie["ga"]) if a else "—",
                attesa_best(h and h["ga"] / medie["ga"], a and a["ga"] / medie["ga"],
                            higher=False))
        for label, (att_h, att_a, att_best) in attesi.items():
            if label not in righe_html:
                fails.append(f"{pg.name}: riga «{label}» mancante")
                continue
            checks += 3
            if testo(righe_html[label][2]) != att_h:
                fails.append(f"{pg.name}: «{label}» casa {testo(righe_html[label][2])!r}, "
                             f"atteso {att_h!r}")
            if testo(righe_html[label][4]) != att_a:
                fails.append(f"{pg.name}: «{label}» trasferta {testo(righe_html[label][4])!r}, "
                             f"atteso {att_a!r}")
            visto = "h" if 'class="best"' in righe_html[label][1] else (
                "a" if 'class="best"' in righe_html[label][3] else None)
            if visto != att_best:
                fails.append(f"{pg.name}: evidenziazione «{label}» {visto}, attesa {att_best}")
        # --- titolo della riga «Punti», divario, orologio ---------------------------------
        checks += 3
        th_punti = righe_html.get("Punti", ("",))[0]
        if not ('title="' in th_punti and "punti/gara" in th_punti):
            fails.append(f"{pg.name}: la riga «Punti» non dichiara nel titolo che "
                         "l'evidenziazione è per punti/gara")
        coda = html[html.find('id="confronto"'):]
        nota = re.search(r'</table></div>\s*<p class="small mut">(.*?)</p>', coda, re.DOTALL)
        nota_txt = nota.group(1) if nota else ""
        if "Classifica raccolta oggi" not in nota_txt:
            fails.append(f"{pg.name}: la nota del confronto non dichiara l'orologio della "
                         "classifica")
        if h and a:
            gap = round(h["pts"] - a["pts"])
            if gap > 0:
                attesa_gap = f"In classifica <b>{nome_h}</b> è {max(1, gap)} punt"
            elif gap < 0:
                attesa_gap = f"In classifica <b>{nome_a}</b> è {max(1, -gap)} punt"
            else:
                attesa_gap = "Le due squadre sono a pari punti in classifica"
            if attesa_gap not in nota_txt:
                fails.append(f"{pg.name}: divario in classifica mancante o sbagliato "
                             f"(atteso {attesa_gap!r}, gap {gap})")
        elif "In classifica" in nota_txt:
            fails.append(f"{pg.name}: divario pubblicato con una squadra senza classifica")
    return fails, checks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="site", help="cartella del sito generato")
    ap.add_argument("--data", default=None, help="cartella dei Parquet (default: data/processed)")
    ap.add_argument("--content-only", action="store_true", help="salta i controlli numerici (serve lo store)")
    args = ap.parse_args()

    site = Path(args.site)
    if not site.is_dir():
        print(f"cartella sito non trovata: {site}")
        return 2

    fails, pages = check_pages(site)
    print(f"pagine analizzate: {pages}")
    calendario, checks = check_calendar(site)
    fails += calendario
    peso, peso_checks = check_page_weight(site)
    fails += peso
    checks += peso_checks
    barre, bar_checks = check_bars(site)
    fails += barre
    checks += bar_checks
    derivati, derivati_checks = check_derived(site)
    fails += derivati
    checks += derivati_checks
    stato, stato_checks = check_status(site)
    fails += stato
    checks += stato_checks
    nav, nav_checks = check_nav(site)
    fails += nav
    checks += nav_checks
    stime, stime_checks = check_stime(site)
    fails += stime
    checks += stime_checks
    fonti, fonti_checks = check_fonti(site)
    fails += fonti
    checks += fonti_checks
    tavole, tavole_checks = check_tavole(site)
    fails += tavole
    checks += tavole_checks
    didascalie, didascalie_checks = check_didascalie_punteggio(site)
    fails += didascalie
    checks += didascalie_checks
    importi, importi_checks = check_importi_mercato(site)
    fails += importi
    checks += importi_checks
    if not args.content_only:
        mercato, mercato_checks = check_mercato_movimenti(site, Path(args.data) if args.data else None)
        fails += mercato
        checks += mercato_checks
        meteo, meteo_checks = check_meteo_soglie(site, Path(args.data) if args.data else None)
        fails += meteo
        checks += meteo_checks
        fattori, fattori_checks = check_fattori(site)
        fails += fattori
        checks += fattori_checks
        fatti, fatti_checks = check_fatti(site, Path(args.data) if args.data else None)
        fails += fatti
        checks += fatti_checks
        coppia, coppia_checks = check_terza_coppia(site, Path(args.data) if args.data else None)
        fails += coppia
        checks += coppia_checks
        vigilia, vigilia_checks = check_forza_avversari_storica(
            site, Path(args.data) if args.data else None)
        fails += vigilia
        checks += vigilia_checks
        lab, lab_checks = check_laboratorio(site, Path(args.data) if args.data else None)
        fails += lab
        checks += lab_checks
        squadre, squadre_checks = check_due_squadre(site, Path(args.data) if args.data else None)
        fails += squadre
        checks += squadre_checks
        confronto, confronto_checks = check_confronto_stagione(
            site, Path(args.data) if args.data else None)
        fails += confronto
        checks += confronto_checks
        numeric, numeric_checks = check_numbers(site, Path(args.data) if args.data else None)
        fails += numeric
        checks += numeric_checks
        assets, asset_checks = check_assets(site)
        fails += assets
        checks += asset_checks
        terne, terne_checks = check_terne_1x2(site)
        fails += terne
        checks += terne_checks
        pctacc, pctacc_checks = check_pct_accuratezza(site, Path(args.data) if args.data else None)
        fails += pctacc
        checks += pctacc_checks

    # riepilogo per tipo: il prefisso è ciò che segue «<pagina>: ». Un messaggio senza «: »
    # (ne è arrivato uno il 2026-10-08) faceva cadere il gate **dopo** i controlli, nascondendo
    # i problemi invece di stamparli: la chiave di ripiego sono le prime parole del messaggio.
    by_kind: Counter[str] = Counter(
        f.split(": ", 1)[1].split(" ")[0] if ": " in f else " ".join(f.split(" ")[:3])
        for f in fails)
    print()
    if fails:
        print(f"PROBLEMI ({len(fails)}): {dict(by_kind)}")
        for f in fails[:40]:
            print("  -", f)
        return 1
    conta = Counter(categoria for categoria, _ in ORACOLI.values())
    print(f"oracoli ({len(ORACOLI)} controlli dichiarati): {conta['I']} indipendenti · "
          f"{conta['M']} misti · {conta['S']} specchi — l'oracolo dei modelli sono i loro test "
          f"(tests/test_models.py, test_season_sim.py, test_advanced.py)")
    print(f"nessun problema · {checks} controlli numerici superati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
