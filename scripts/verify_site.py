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
AGREEMENT = re.compile(
    r"(?<![\d,])\b1 (rossi|gialli|rigori|gare|partite|vittorie|pareggi|tiri|giorni|precedenti|"
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
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.skip = 0
        self.news_tag: str | None = None
        self.news_depth = 0
        self.sapere_tag: str | None = None
        self.sapere_depth = 0
        self.readable_attrs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Any]]) -> None:
        if tag in ("style", "script", "head", "svg"):
            self.skip += 1
        if self.news_depth == 0 and any(k == "id" and v == "notizie" for k, v in attrs):
            self.news_tag, self.news_depth = tag, 1
        elif self.news_tag == tag:
            self.news_depth += 1
        # «Da sapere»: testo nostro dentro la card delle notizie → va ricontrollato (vedi docstring)
        if self.sapere_depth == 0 and any(
                k == "class" and v and "sapere" in str(v).split() for k, v in attrs):
            self.sapere_tag, self.sapere_depth = tag, 1
        elif self.sapere_tag == tag:
            self.sapere_depth += 1
        if tag in ("p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "table", "section", "br"):
            self.parts.append(" ")      # separa i blocchi: «…link</a>1 gare» non deve sembrare «x1 gare»
        for k, v in attrs:
            if k == "id" and v:
                self.ids.add(v)
            if tag == "a" and k == "href" and v:
                self.hrefs.append(v)
            if k in ATTR_LEGGIBILI and v and (self.news_depth == 0 or self.sapere_depth > 0):
                self.readable_attrs.append(str(v))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "head", "svg") and self.skip:
            self.skip -= 1
        if self.news_tag == tag:
            self.news_depth -= 1
            if self.news_depth <= 0:
                self.news_tag, self.news_depth = None, 0
        if self.sapere_tag == tag:
            self.sapere_depth -= 1
            if self.sapere_depth <= 0:
                self.sapere_tag, self.sapere_depth = None, 0

    def handle_data(self, data: str) -> None:
        if not self.skip and (self.news_depth == 0 or self.sapere_depth > 0):
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
    r'<div class="cal-row([^"]*)" data-match-card data-league="([^"]+)" data-status="([^"]+)">(.*?)</div>',
    re.DOTALL)
CAL_PCT = re.compile(r'<span class="cal-p"[^>]*aria-label="1 (\d+)%, X (\d+)%, 2 (\d+)%"[^>]*>(.*?)</span>')
CAL_MONTH = re.compile(
    r'<details class="cal-month" id="mese-(\d{4})-(\d{2})"[^>]*>\s*<summary>([^<]+)'
    r'<span class="cal-count">([\d.]+) ([^<]+)</span></summary>(.*?)</details>', re.DOTALL)
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
                numeri = [int(v) for v in re.findall(r"\d+", re.sub(r"</?b>", "", visibile))]
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


def _pos_pct(v: float, lo_q: float, hi_q: float) -> float:
    """Posizione 0–100 di un valore sulla scala della barra (stessa formula del generatore)."""
    return round(min(100.0, max(0.0, 100.0 * (v - lo_q) / (hi_q - lo_q))), 2)


def check_numbers(site: Path, data: Path | None) -> tuple[list[str], int]:
    """Ricalcola i numeri pubblicati con le funzioni del progetto e li confronta."""
    import numpy as np
    import pandas as pd

    from fda.models.predict import rps as pb_rps
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
        cells = re.findall(r'<td[^>]*title="(\d)-(\d) · (meno di 0,1|\d+,\d+)%[^"]*">(<1|\d+,\d)</td>', html)
        if len(cells) != 36:
            fails.append(f"{pg.name}: celle matrice {len(cells)} (attese 36)")
            continue
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
        if worst > 0.11:
            fails.append(f"{pg.name}: cella matrice diversa di {worst:.2f} pp")
        if not 99.0 <= tot + tail <= 100.6:
            fails.append(f"{pg.name}: matrice+coda = {tot + tail:.1f}%")
        # coerenza con le probabilità pubblicate (stessa τ del modello, vedi dc_grid)
        g = dixon_coles_grid(float(r.lambda_home), float(r.lambda_away), float(r.dc_rho or 0.0))
        ph, pdw, _pa = grid_1x2(g)
        if abs(ph - float(r.p_home)) > 0.015 or abs(pdw - float(r.p_draw)) > 0.015:
            fails.append(f"{pg.name}: 1X2 griglia ({ph:.3f}/{pdw:.3f}) != previsione "
                         f"({r.p_home:.3f}/{r.p_draw:.3f})")
    print(f"[1] matrici punteggi verificate: {n_matrix}")

    # 2) probabilità in-play: ogni riga somma ~100 e l'ultima coincide col risultato
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
            if abs(int(a) + int(b) + int(c) - 100) > 3:
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
        mine = pb_rps(p[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist(), outc.tolist())
        acc_txt = acc_path.read_text(encoding="utf-8")
        mrow = re.search(r'Tutti</td><td class="r">(\d+)</td><td class="r">(\d+,\d+)</td>', acc_txt)
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
        righe_riep = re.findall(
            r'<td>([^<]+)</td><td class="r">(\d+)</td><td class="r">(\d+,\d+)</td>'
            r'<td class="r">(\d+,\d+)</td><td class="r">\d+%</td><td class="r">(\d+,\d+)</td>'
            r'<td class="r">(?:[\d.]+|fisso)</td><td class="r [a-z]+">([+\-−]?[\d,]+)</td></tr>', acc_txt)
        if not righe_riep:
            fails.append("accuratezza.html: tabella riepilogo non leggibile per il controllo [3b]")
        n_leghe, n_tutti = 0, 0
        for lg, n_r, rps_r, _brier, naive_r, delta_r in righe_riep:
            checks += 1
            if lg.strip() == "Tutti":
                n_tutti = int(n_r)
            else:
                n_leghe += int(n_r)
            ric = float(rps_r.replace(",", ".")) - float(naive_r.replace(",", "."))
            pub = float(delta_r.replace(",", ".").replace("−", "-"))
            if abs(pub - ric) > 0.0011:   # rps/naive a 4 decimali + Δ a 3: tolleranza di stampa
                fails.append(f"accuratezza: Δ {lg} pubblicato {pub:+.4f} ≠ RPS − naive {ric:+.4f}")
        if n_tutti and n_leghe and n_tutti != n_leghe:
            fails.append(f"accuratezza: riga Tutti {n_tutti} gare ≠ somma leghe {n_leghe}")
        m_comp = re.search(r"Composizione del campione: (\d+) gare valutate", acc_txt)
        if m_comp:
            checks += 1
            if int(m_comp.group(1)) != n_tutti:
                fails.append(f"accuratezza: composizione {m_comp.group(1)} gare ≠ riga Tutti {n_tutti}")
        elif "Riepilogo" in acc_txt:
            fails.append("accuratezza.html: composizione del campione assente (docs/19 §1.5)")
        else:
            print("[3b] accuratezza: pagina senza riepilogo (nessuna previsione valutabile)")

    # 7) accuratezza: intervalli di Wilson pubblicati, ricalcolati con la funzione del progetto
    if acc_path.exists():
        from fda.site.build import wilson_interval

        def _n(txt: str) -> float:
            return float(re.sub(r"<[^>]+>", "", txt).replace(".", "").replace(",", ".").rstrip("%"))

        righe = 0
        for row in re.findall(r"<tr><td>.*?</tr>", acc_path.read_text(encoding="utf-8"), re.DOTALL):
            mi = re.search(r'<td class="r mut">(\d+,\d+)\s*[–-]\s*(\d+,\d+)%</td>', row)
            if not mi:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            lo_p, hi_p = _n(mi.group(1)), _n(mi.group(2))
            kn = re.search(r"\((\d+)/(\d+)\)", row)
            if kn and len(cells) >= 7:                # riga di mercato: k/n esplicito, 9-10 celle
                k, n, prev = int(kn.group(1)), int(kn.group(2)), _n(cells[2])
            elif kn:                                  # riga di calibrazione: k/n esplicito, 5 celle
                k, n, prev = int(kn.group(1)), int(kn.group(2)), _n(cells[1])
            else:                                     # nessuna k/n pubblicata: k ≈ osservato × n
                n = int(_n(cells[1]))
                prev, obs = _n(cells[2]), _n(cells[3])
                k = round(obs * n / 100.0)
            lo, hi = wilson_interval(k, n)
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
            m_n = re.search(r"su <b>(\d+)</b> partite", card)
            m_r = re.search(r"RPS <b>(\d+,\d+)</b>", card)
            if not m_n or not m_r:
                fails.append("accuratezza.html: card backtest senza numerosità o RPS")
            else:
                checks += 1
                mine = pb_rps(bt[["p_home", "p_draw", "p_away"]].to_numpy(float).tolist(),
                              bt["outcome"].to_numpy(int).tolist())
                rps_bt = float(m_r.group(1).replace(",", "."))
                if int(m_n.group(1)) != len(bt):
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
    n_role = n_abs = n_h2h = 0
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
    inf_re = re.compile(r'partite/(\d+)\.html(?:(?!partite/).)*?Infermeria: ([^<]*?) (\d+) assenti'
                        r' · ([^<]*?) (\d+) assenti', re.DOTALL)
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
        for mid, n1, c1, n2, c2 in inf_re.findall(html):
            if int(mid) not in fx_by_id.index:
                continue
            row = fx_by_id.loc[int(mid)]
            checks += 1
            n1, n2 = html_unescape(n1), html_unescape(n2)   # M'gladbach → M&#39;gladbach in HTML
            if (n1.strip(), int(c1)) != (str(row.home_name).strip(),
                                         un_count.get((int(mid), int(row.home_id)), 0)) or \
               (n2.strip(), int(c2)) != (str(row.away_name).strip(),
                                         un_count.get((int(mid), int(row.away_id)), 0)):
                fails.append(f"{lg_page}: infermeria {n1} {c1} / {n2} {c2} != distinta")
    print(f"[5] schede oggi: {n_role} ruoli, {n_abs} infermerie, {n_h2h} archivi precedenti")

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
    from fda.site.fmt import pct_triple

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
            # il confronto è con il vettore **pubblicato** (resto massimo a un decimale), non con
            # l'arrotondamento indipendente dei tre valori grezzi: era la stessa regola sbagliata
            # corretta nelle barre (docs/19 §3.3) e tollerava 0,06 pp di scarto. Qui lo scarto
            # ammesso è zero, perché la pagina e il verificatore chiamano la stessa funzione.
            attesi = pct_triple((passo["p_home"], passo["p_draw"], passo["p_away"]), 1)
            for shown, key, atteso in ((h, "p_home", attesi[0]), (x, "p_draw", attesi[1]),
                                       (a, "p_away", attesi[2])):
                if abs(float(shown.replace(",", ".")) - atteso) > 1e-9:
                    fails.append(f"{pg.name}: {passo['label']} {key} = {shown}% vs {atteso:.1f}% "
                                 f"(vettore pubblicato {attesi})")
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
        from fda.site.build import wilson_interval

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
            wl_b, wh_b = wilson_interval(kb, nb)
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
            from fda.site.fmt import displayed_sum as _disp_sum

            lam_here = _disp_sum(float(row.lambda_home.iloc[0]), float(row.lambda_away.iloc[0]))
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
            if int(pct_t) != round(below * 100):
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
                    ("percentile in aria-label", float(mv.group(2)), round(below * 100))):
                checks += 1
                if abs(letto - atteso) > 0.2:
                    fails.append(f"{pg.name}: barra posizione, {cosa} {letto}% vs ricalcolato {atteso}%")
            checks += 1
            if mv.group(14) != _stamp_it(lam_here):
                fails.append(f"{pg.name}: barra posizione, segno {mv.group(14)} vs λ stampati "
                             f"{_stamp_it(lam_here)}")
            if abs(float(mv.group(5).replace(",", ".")) - lo_q) > 0.05 or \
                    abs(float(mv.group(6).replace(",", ".")) - hi_q) > 0.05:
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

    # 14) n_train e compagni grandi con il separatore delle migliaia (esclusi gli anni 19xx/20xx)
    n_ntrain = 0
    no_year = r"\b(?!19\d\d|20\d\d)(\d{4,})\s*(?:partite|gare)\b"
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        male = re.search(no_year, re.sub(r"<[^>]+>", " ", html))
        if male:
            fails.append(f"{pg.name}: «{male.group(1)} partite/gare» senza separatore delle migliaia")
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

    # 19) panchina e posta in gioco (docs/21 P0-1): coach, subentro e percentuali Monte Carlo
    # ricalcolati dai Parquet; la sezione deve esserci se e solo se i dati ci sono.
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
    from fda.site.analysis import MatchAnalysis as _MA
    from fda.sources.news import JUNK_NEWS, is_italian_news, news_value
    ma19 = _MA(st)
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
            atteso = False
            for tid, tname in ((int(fr.home_id), fr.home_name), (int(fr.away_id), fr.away_name)):
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
                if coach and 'id="panchina"' in html:
                    checks += 1
                    if coach[0] not in txt:
                        fails.append(f"{pg.name}: panchina senza il coach {coach[0]} dei Parquet")
                    if coach[1] is not None and \
                            ("panchina nuova" not in txt or str(coach[1]) not in txt):
                        fails.append(f"{pg.name}: subentro a {coach[1]} non dichiarato")
                if sr is not None and 'id="panchina"' in html:
                    checks += 1
                    raw_top = getattr(sr, "p_top_n", None)
                    if raw_top is None or pd.isna(raw_top):
                        raw_top = getattr(sr, "p_top4", None)
                    raw_n = getattr(sr, "top_n", None)
                    top_n = 4 if raw_n is None or pd.isna(raw_n) else int(raw_n)
                    pt = round(float(sr.p_title) * 100)
                    pe = None if raw_top is None or pd.isna(raw_top) else round(float(raw_top) * 100)
                    pr = round(float(sr.p_rel) * 100)
                    atteso = (f"titolo {pt}% · UCL (prime {top_n}) {pe}%"
                              if pe is not None else f"titolo {pt}%")
                    if atteso not in txt or f"salvezza {pr}%" not in txt:
                        fails.append(f"{pg.name}: posta in gioco {tname} non torna coi Parquet")
                    lab = ("corsa al titolo" if float(sr.p_title) >= 0.15 else
                           ("corsa alla Champions" if top_n < 4 else "corsa all'Europa")
                           if raw_top is not None and not pd.isna(raw_top) and float(raw_top) >= 0.35 else
                           "lotta salvezza" if float(sr.p_rel) >= 0.35 else
                           "zona salvezza non lontana" if float(sr.p_rel) >= 0.15 else
                           "stagione di metà classifica")
                    if lab not in txt:
                        fails.append(f"{pg.name}: etichetta posta in gioco {tname} sbagliata ({lab})")
            if atteso and 'id="panchina"' not in html:
                fails.append(f"{pg.name}: scheda pre senza sezione panchina pur avendo i dati")
            # righe «utili» della card (rendimento, precedenti mirati, distacchi, virtuale):
            # ricalcolate con le funzioni del progetto e confrontate col testo stampato
            if 'id="panchina"' in html:
                for tid, tname, oid, oname in (
                        (int(fr.home_id), str(fr.home_name), int(fr.away_id), str(fr.away_name)),
                        (int(fr.away_id), str(fr.away_name), int(fr.home_id), str(fr.home_name))):
                    bd = ma19.bench_deep(tid, tname, oid, oname, kickoff)
                    if not bd:
                        continue
                    for key in ("tenure_line", "coach_ppg_line", "coach_vs_opp_line",
                                "coach_vs_coach_line", "table_line", "virtual_line"):
                        val = bd.get(key)
                        if val:
                            checks += 1
                            if val not in txt:
                                fails.append(f"{pg.name}: riga panchina «{key}» ({tname}) assente o diversa")
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
                                f"(il {round(100 * tardi / totale)}% di quelli presi fin qui).")
                        if riga not in testo_card:
                            fails.append(f"{pg.name}: gol nel finale di {tname[:20]} "
                                         f"assenti o diversi ({tardi}/{totale})")
        blocchi = re.split(r'<p style="margin:12px 0 6px"><b>', card)[1:]
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

    # 21) clima del club (docs/21 P2-6): ogni riga stampata è ricalcolata da club_mood
    # con le stesse soglie; se una squadra ha segnali la card deve esserci. Da P2.2 (`docs/28`
    # §3) la card c'è **sempre** sulle schede pre-partita: due squadre senza segnali non devono
    # farla sparire (il lettore non distinguerebbe «clima tranquillo» da «dato non raccolto»),
    # e in quel caso la pagina lo dice riga per riga. Il controllo verifica le due direzioni.
    n_mood = 0
    vuota = ("Nessun segnale anomalo nei dati raccolti: clima normale.")
    for pg in pages:
        html = pg.read_text(encoding="utf-8")
        if "Analisi pre-partita" not in html or fx19.empty or int(pg.stem) not in ko19.index:
            continue
        txt = html_unescape(html)
        fr = fx19[fx19.match_id == int(pg.stem)].iloc[0]
        kickoff = pd.Timestamp(fr.utc_kickoff)
        rows_h = ma19.club_mood(int(pg.stem), int(fr.home_id), str(fr.home_name), kickoff)
        rows_a = ma19.club_mood(int(pg.stem), int(fr.away_id), str(fr.away_name), kickoff)
        n_mood += 1
        if 'id="clima"' not in html:
            fails.append(f"{pg.name}: card clima assente (deve esserci su ogni scheda pre-partita)")
            continue
        for r in rows_h + rows_a:
            checks += 1
            if r["text"] not in txt:
                fails.append(f"{pg.name}: riga clima «{r['text'][:40]}» assente o diversa")
        senza = (0 if rows_h else 1) + (0 if rows_a else 1)
        checks += 1
        if txt.count(vuota) != senza:
            fails.append(f"{pg.name}: {senza} squadre senza segnali ma la riga «clima normale» "
                         f"compare {txt.count(vuota)} volte")
    print(f"[21] pagine con clima del club riconciliate: {n_mood}")

    # 22) scontro tattico: graduatorie attacco/difesa e duello chiave ricalcolati dalla
    # classifica FotMob (fonte unica) e confrontati col testo stampato.
    n_duel = 0
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
    print(f"[22] duello chiave e graduatorie verificati: {n_duel} pagine")

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
NAV_SEZIONI = ("lettura", "previsione", "scontro", "arrivi", "giocatori", "squadre", "panchina",
               "mercato", "notizie", "arbitro-meteo", "precedenti", "statistiche", "cronaca",
               "verifica")


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
    if not args.content_only:
        numeric, numeric_checks = check_numbers(site, Path(args.data) if args.data else None)
        fails += numeric
        checks += numeric_checks
        assets, asset_checks = check_assets(site)
        fails += assets
        checks += asset_checks

    by_kind: Counter[str] = Counter(f.split(": ", 1)[1].split(" ")[0] for f in fails)
    print()
    if fails:
        print(f"PROBLEMI ({len(fails)}): {dict(by_kind)}")
        for f in fails[:40]:
            print("  -", f)
        return 1
    print(f"nessun problema · {checks} controlli numerici superati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
