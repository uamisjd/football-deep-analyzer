"""Invarianti di contrasto del design system (WCAG 2.1) verificate senza browser.

Perché un file dedicato: il sito ha due temi e 4.128 pagine generate, e il contrasto è
l'unico difetto visivo misurabile **staticamente** — non serve un headless browser, bastano
la luminanza relativa e i token dichiarati in ``base.html``.

Questi test esistono perché il tema chiaro aveva testi quasi invisibili: la «V» della
guida-forma a 1,11:1 (verde chiaro su verde chiaro), il testo selezionato a 1,02:1, il
punteggio più probabile a 2,09:1, i link al hover a 1,78:1 — più 21 coppie di token sotto
AA. Difetti che nessuno screenshot fatto in tema scuro poteva mostrare. Vedi ``docs/19`` §3.2 e §3.5.

Requisiti applicati (WCAG 2.1):
- **4,5:1** testo normale (1.4.3) — tutti i token usati in una proprietà ``color:``;
- **3,0:1** grafica non testuale (1.4.11) — bordi, riempimenti, e i campioni di colore ``●``
  delle legende dei grafici, che sono simboli cromatici e non caratteri da leggere;
- l'uso di ogni token è **derivato dal CSS**, non dichiarato a mano: se domani qualcuno usa
  ``--accent-soft`` come colore di testo, il test inizia a pretendere 4,5:1 da solo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SITE_SRC = Path(__file__).resolve().parents[1] / "src" / "fda" / "site"
BASE = SITE_SRC / "assets" / "site.css"

#: superfici su cui il tema poggia il contenuto. ``--surface3`` è incluso per prudenza anche se
#: oggi porta solo ``--txt``/``--txt2``: se domani qualcuno ci mette un accento, il test lo prende.
SURFACES = {
    "dark": ["#0c1118", "#131a24", "#1a2330", "#212c3a"],
    "light": ["#ffffff", "#f4f6f8", "#eef2f6", "#e2e8f0"],
}

#: token che stanno su uno sfondo proprio (non sulla superficie della pagina): la coppia va
#: verificata insieme, altrimenti il confronto con la pagina non significa niente.
COPPIE = {
    "on-accent": "accent",          # nav corrente, posizione attiva
    "accent-strong": "accent-dim",  # pill versione, tag, filtro attivo, segnale concorde
    "v-fg": "v-bg", "n-fg": "n-bg", "p-fg": "p-bg",   # chip risultato V/N/P
    "sel-fg": None,                 # sfondo = velatura rgba: verificata a parte
}

#: campioni di colore delle legende (il glifo «●»/«◌»): grafica non testuale → 3:1.
#: Restano identici ai colori dei grafici dentro il pannello SVG scuro, così legenda e serie
#: coincidono esattamente; il requisito AA 4,5:1 varrebbe se fossero caratteri da leggere.
CAMPIONI = ("leg-home", "leg-away", "leg-save", "leg-draw", "leg-block", "leg-off")

#: eccezioni dichiarate del linter per regole, con il motivo. Non sono falsi positivi nascosti:
#: sono regole il cui sfondo non è nella regola stessa (quindi il linter non può vederlo).
ECCEZIONI = {
    # sfondo dipinto dai segmenti .bar .h/.d/.a (gradienti propri): verificato in
    # test_barra_1x2_stop_gradiente → 4,59-8,72:1 in entrambi i temi
    ".bar": "sfondo dai segmenti .bar .h/.d/.a, verificato a parte",
    # sfondo dipinto dall'inline style del template (rgba(40,200,147,op)): 7,95:1 misurato
    ".scoregrid td.mode": "sfondo heatmap inline nel template",
    # separatore decorativo «·»: usa --line2 di proposito, stesso peso visivo di un bordo
    ".fact-separator": "decorativo, colore = token del bordo",
}


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def f(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrasto(fg: str, bg: str) -> float:
    """Rapporto di contrasto WCAG 2.1: (L1 + 0,05) / (L2 + 0,05)."""
    la, lb = _lum(fg), _lum(bg)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _css() -> str:
    # il design system vive in assets/site.css (estratto da base.html nel 2026-09-16,
    # docs/19 P0.5: 39 kB inline duplicati in ~10.000 pagine)
    assert BASE.exists(), "assets/site.css mancante: il CSS è stato rimesso inline?"
    return re.sub(r"/\*.*?\*/", "", BASE.read_text(encoding="utf-8"), flags=re.DOTALL)


def _blocchi(css: str) -> dict[str, str]:
    """Corpo CSS dei tre blocchi di token: root (scuro), light esplicito, light da preferenze OS."""
    root = re.search(r":root\s*\{(.*?)\n\}", css, re.DOTALL)
    light = re.search(r'\[data-theme="light"\]\s*\{(.*?)\n\}', css, re.DOTALL)
    media = re.search(
        r"prefers-color-scheme:\s*light\)\s*\{\s*:root:not\(\[data-theme=\"dark\"\]\)\s*\{(.*?)\n\s*\}",
        css, re.DOTALL)
    assert root and light and media, "uno dei tre blocchi di token manca"
    return {"dark": root.group(1), "light": light.group(1), "media": media.group(1)}


def _token(blocco: str) -> dict[str, str]:
    return {k: v.strip() for k, v in re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", blocco)}


def _css_senza_token(css: str) -> str:
    return re.sub(r'(:root|\[data-theme="[a-z]+"\])\s*\{[^}]*\}', "", css, flags=re.DOTALL)


def _uso_token(css: str) -> dict[str, set[str]]:
    """In quali proprietà compare ogni token: {'accent': {'color'}, 'line': {'border', ...}}.

    Le regole in ECCEZIONI sono saltate: l'eccezione va dichiarata una volta sola e vale sia
    per il linter sulle regole sia per la classificazione dei token (altrimenti ``--line2``
    risulterebbe "token di testo" solo perché il separatore decorativo «·» lo usa).
    """
    uso: dict[str, set[str]] = {}
    for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", _css_senza_token(css)):
        sel = re.sub(r"\s+", " ", m.group(1)).strip()
        if any(sel.startswith(e) for e in ECCEZIONI):
            continue
        corpo = m.group(2)
        for prop in re.findall(r"([a-z-]+)\s*:\s*([^;}]+)", corpo):
            nome, valore = prop[0].strip(), prop[1]
            for tok in re.findall(r"var\(--([a-z0-9-]+)\)", valore):
                chiave = "color" if nome == "color" else (
                    "background" if nome.startswith("background") else "decor")
                uso.setdefault(tok, set()).add(chiave)
    return uso


@pytest.fixture(scope="module")
def temi() -> dict[str, object]:
    """Palette risolte per tema: il chiaro eredita dal :root ciò che non ridefinisce."""
    css = _css()
    b = _blocchi(css)
    dark = _token(b["dark"])
    return {"dark": dark, "light": {**dark, **_token(b["light"])},
            "media": {**dark, **_token(b["media"])}, "_blocchi": b, "_uso": _uso_token(css)}


# --------------------------------------------------------------------------- allineamento temi
def test_tema_chiaro_palette_allineata(temi: dict) -> None:
    """Il fallback per prefers-color-scheme deve dichiarare gli STESSI token e valori.

    Difetto corretto: il blocco @media dichiarava 12 token su 30 e mancavano proprio
    accent/win/draw/lose/amber/info/hover. Con JS disabilitato (o non supportato) un utente
    in tema chiaro otteneva superfici bianche con il verde #28c893 del tema scuro: 2,15:1.
    """
    b = temi["_blocchi"]
    dichi_light, dichi_media = set(_token(b["light"])), set(_token(b["media"]))
    assert dichi_light == dichi_media, (
        f"token solo nel tema chiaro esplicito: {sorted(dichi_light - dichi_media)}; "
        f"solo nel fallback OS: {sorted(dichi_media - dichi_light)}")
    light, media = temi["light"], temi["media"]
    diversi = {k: (light[k], media[k]) for k in dichi_light if light[k] != media[k]}
    assert not diversi, f"valori divergenti fra i due temi chiari: {diversi}"


def test_token_di_foreground_presenti(temi: dict) -> None:
    """I token nati per togliere gli hard-coded esistono in entrambi i temi."""
    richiesti = {"accent-hover", "accent-strong", "on-accent", "sel-bg", "sel-fg", "lose-soft",
                 "v-bg", "v-fg", "v-line", "n-bg", "n-fg", "n-line", "p-bg", "p-fg", "p-line",
                 *CAMPIONI}
    for tema in ("dark", "light"):
        mancanze = richiesti - set(temi[tema])
        assert not mancanze, f"tema {tema}: token mancanti {sorted(mancanze)}"


# --------------------------------------------------------------------------- contrasto AA
@pytest.mark.parametrize("tema", ["dark", "light"])
def test_contrasto_token_di_testo_aa(temi: dict, tema: str) -> None:
    """4,5:1 per ogni token usato come colore di testo, su tutte le superfici del tema.

    L'elenco dei token di testo è derivato dal CSS (``color: var(--x)``), quindi una nuova
    regola che usa un token come testo entra da sola nel controllo.
    """
    palette, superfici, uso = temi[tema], SURFACES[tema], temi["_uso"]
    di_testo = sorted(t for t, u in uso.items() if "color" in u
                      and t not in COPPIE and t not in CAMPIONI)
    assert di_testo, "nessun token di testo individuato: la derivazione dal CSS si è rotta"
    scarti = []
    for nome in di_testo:
        v = palette.get(nome, "")
        if not v.startswith("#"):
            continue                       # --sel-bg è una rgba: verificata in test_selezione
        for s in superfici:
            c = contrasto(v, s)
            if c < 4.5:
                scarti.append(f"--{nome} {v} su {s} = {c:.2f}:1")
    assert not scarti, f"tema {tema}, testo sotto AA 4,5:1:\n  " + "\n  ".join(scarti)


@pytest.mark.parametrize("tema", ["dark", "light"])
def test_contrasto_campioni_legenda(temi: dict, tema: str) -> None:
    """3:1 per i campioni di colore delle legende (WCAG 1.4.11, grafica non testuale).

    Sono gli unici elementi cromatici che veicolano informazione da soli: collegano un colore
    a una serie del grafico. Superfici, bordi di card e separatori NON sono soggetti a 3:1
    perché non sono necessari a capire il contenuto (il requisito vale per "visual information
    required to understand state or boundaries"): pretendere 3:1 su --bg o --line genererebbe
    solo rumore e spingerebbe a schiarire/scurire le superfici rovinando il design.
    """
    palette, superfici = temi[tema], SURFACES[tema]
    scarti = []
    for nome in CAMPIONI:
        v = palette[nome]
        for s in superfici:
            c = contrasto(v, s)
            if c < 3.0:
                scarti.append(f"--{nome} {v} su {s} = {c:.2f}:1")
    assert not scarti, f"tema {tema}, campioni legenda sotto 3:1:\n  " + "\n  ".join(scarti)


@pytest.mark.parametrize("tema", ["dark", "light"])
def test_contrasto_coppie_su_sfondo_proprio(temi: dict, tema: str) -> None:
    """Testo sul proprio sfondo: chip V/N/P, pill versione, nav corrente.

    Qui stava il difetto più grave del tema chiaro: la «V» della guida-forma era verde chiaro
    (#9df0cf) su sfondo verde chiaro (--accent-dim #d6f0e6) = **1,11:1**, cioè invisibile.
    """
    p = temi[tema]
    for fg, bg in COPPIE.items():
        if bg is None:
            continue
        c = contrasto(p[fg], p[bg])
        assert c >= 4.5, f"{tema}: --{fg} {p[fg]} su --{bg} {p[bg]} = {c:.2f}:1"


def test_contrasto_selezione_testo(temi: dict) -> None:
    """Il testo selezionato era #eaf0f6 su una velatura chiara: 1,02:1 in tema chiaro (invisibile)."""
    css = _css()
    assert "var(--sel-bg)" in css and "var(--sel-fg)" in css, "::selection non usa i token"
    # velatura rgba(23,125,92,.18) sopra #ffffff → fondo effettivo #dfe8e3
    assert contrasto(temi["light"]["sel-fg"], "#dfe8e3") >= 4.5
    # tema scuro: velatura rgba(120,150,190,.22) sopra #131a24 → fondo effettivo #2c3543
    assert contrasto(temi["dark"]["sel-fg"], "#2c3543") >= 4.5


# --------------------------------------------------------------------------- barra 1X2
def test_barra_1x2_stop_gradiente() -> None:
    """La barra 1X2 ha sfondi propri identici nei due temi: ogni stop deve reggere il testo.

    Prima: stop scuro verde #1b9270 = 4,27:1 e stop scuro rosso #b2403b = **2,92:1** con il
    testo #06231a — il numero del segmento «2» era illeggibile nella metà bassa della barra,
    su tutte le pagine e in entrambi i temi.
    """
    css = _css()
    testo = re.search(r"^\.bar\{[^}]*?color:\s*(#[0-9a-fA-F]{6})", css, re.MULTILINE)
    assert testo, "colore del testo della barra non trovato"
    fg = testo.group(1)
    for sel in (".bar .h", ".bar .a"):
        regola = re.search(re.escape(sel) + r"\{background:linear-gradient\(180deg,"
                           r"(#[0-9a-fA-F]{6}),(#[0-9a-fA-F]{6})\)\}", css)
        assert regola, f"gradiente di {sel} non trovato o cambiato formato"
        for stop in regola.groups():
            c = contrasto(fg, stop)
            assert c >= 4.5, f"{sel}: testo {fg} sullo stop {stop} = {c:.2f}:1"
    x = re.search(r"\.bar \.d\{background:(#[0-9a-fA-F]{6});color:(#[0-9a-fA-F]{6})\}", css)
    assert x, "segmento X della barra non trovato"
    assert contrasto(x.group(2), x.group(1)) >= 4.5


def test_cella_punteggio_piu_probabile() -> None:
    """Nessun override chiaro per .scoregrid td.mode: con color:#ffffff rendeva 2,09:1."""
    css = _css()
    assert '[data-theme="light"] .scoregrid td.mode' not in css, (
        "l'override chiaro della cella modale è tornato: il punteggio più probabile torna illeggibile")
    m = re.search(r"\.scoregrid td\.mode\{[^}]*?color:\s*(#[0-9a-fA-F]{6})", css)
    assert m, "colore della cella modale non trovato"
    # sfondo = verde heatmap più saturo del template: rgba(40,200,147,.95) sopra --surface2
    assert contrasto(m.group(1), "#32ca98") >= 4.5


# --------------------------------------------------------------------------- niente hard-coded
def test_nessun_colore_di_testo_hardcoded() -> None:
    """Ogni ``color:`` del CSS usa un token: gli hard-coded sono punti che il tema non copre.

    Corretti: a:hover #4cd9a8 (1,78:1 in chiaro), ::selection #eaf0f6, chip V/N/P,
    .prob-labels #ef918b, nav corrente #06231a, .ver --brand-a, bordo header #263142.
    """
    colpevoli = []
    for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", _css_senza_token(_css())):
        sel = re.sub(r"\s+", " ", m.group(1)).strip()
        if any(sel.startswith(e) for e in ECCEZIONI):
            continue
        for hard in re.finditer(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{3,8})", m.group(2)):
            colpevoli.append(f"{sel} → {hard.group(1)}")
    assert not colpevoli, ("colori di testo hard-coded (il tema chiaro non li copre):\n  "
                           + "\n  ".join(colpevoli))


def test_legende_dei_grafici_usano_i_token() -> None:
    """Le legende sotto i grafici sono sulla pagina, non nel pannello: devono seguire il tema.

    Il pannello SVG resta scuro in entrambi i temi (contrasto interno 5,0-9,4:1, verificato),
    ma le legende stavano fuori: #28c893 su bianco = 2,15:1, #4c9dd3 = 2,97:1.
    """
    t = (SITE_SRC / "templates" / "match.html").read_text(encoding="utf-8")
    legende = [m.group(1) for m in re.finditer(r'<p class="small mut"[^>]*>(.*?)</p>', t, re.DOTALL)
               if "●" in m.group(1) or "◌" in m.group(1)]
    assert legende, "nessuna legenda trovata in match.html: il selettore del test è da aggiornare"
    for corpo in legende:
        hard = re.findall(r'style="color:(#[0-9a-fA-F]{3,6})"', corpo)
        assert not hard, f"legenda con colori hard-coded {hard}"


def test_pannelli_svg_autoconsistenti() -> None:
    """Il pannello dei grafici è scuro in entrambi i temi: i colori interni devono reggerlo.

    Scelta deliberata (non è un residuo del tema scuro): il canvas è una figura con sfondo
    proprio #101a24 e tutti i tratti/testi interni stanno fra 5,0 e 9,4:1.
    """
    canvas = "#101a24"
    #: tratteggio del campo (linee dell'area, dischetto, asse dei minuti): deve vedersi ma
    #: restare recessivo rispetto ai dati. Non è informazione: è contesto.
    tratteggio = {"#3b5068"}
    #: il colore del canvas ricompare come stroke dei marcatori: è il contorno che separa i
    #: punti sovrapposti dal campo, quindi DEVE essere uguale allo sfondo (contrasto 1:1 voluto).
    contorno = {canvas}
    t = (SITE_SRC / "templates" / "match.html").read_text(encoding="utf-8")
    interni = set(re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{6})"', t))
    assert interni, "nessun colore interno ai grafici trovato"
    dati = sorted(c for c in interni if c not in tratteggio | contorno)
    deboli = [c for c in dati if contrasto(c, canvas) < 3.0]
    assert not deboli, f"colori dei DATI sotto 3:1 sul canvas {canvas}: {deboli}"
    invisibili = [c for c in tratteggio & interni if contrasto(c, canvas) < 1.3]
    assert not invisibili, f"tratteggio del campo illeggibile anche come contesto: {invisibili}"
    assert contorno & interni, "il contorno dei marcatori non è più del colore del canvas: verificare"
