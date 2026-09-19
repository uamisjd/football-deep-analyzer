"""Didascalia del punteggio coerente con lo stato della gara (docs/41).

**Il difetto, misurato sul sito pubblicato.** Il 19/09/2026 alle 16:03 IT la pagina «Oggi»
mostrava **7 schede su 7** in corso con il punteggio live e la didascalia «calcio d'inizio»
(«Bologna **1–0** calcio d'inizio» con 63 minuti giocati), e l'hero della scheda partita
«**1–0** · calcio d'inizio · 15:00». La didascalia era binaria — `finished` → «finale»,
tutto il resto → «calcio d'inizio» — e nessun invariante di `verify_site` la leggeva: il gate
era verde con 151.316 controlli e il sito pubblicato era fermo su un'etichetta falsa.

Qui: la mappa stato → didascalia, la resa nelle liste e nell'hero su dati raccolti, e il morso
del nuovo invariante `[37]`.
"""

import importlib.util
import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fda.site.build import SiteBuilder
from tests.test_site import _seed


def _site_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "verify_site.py"
    spec = importlib.util.spec_from_file_location("verify_site_mod", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ogni_stato_ha_la_sua_didascalia():
    """La didascalia dice **che numero è**, non l'orario: un punteggio live non è un kickoff."""
    casi = {
        "finished": "finale", "full_time": "finale", "ft": "finale",
        "live": "in corso", "in_progress": "in corso", "started": "in corso",
        "halftime": "intervallo", "half_time": "intervallo", "paused": "intervallo",
        "postponed": "rinviata", "suspended": "sospesa", "abandoned": "sospesa",
        "cancelled": "annullata", "canceled": "annullata",
        "scheduled": "calcio d'inizio", None: "calcio d'inizio", "": "calcio d'inizio",
    }
    for stato, attesa in casi.items():
        assert SiteBuilder.score_caption(stato) == attesa, stato


def test_gara_in_corso_non_dice_calcio_d_inizio(tmp_path):
    """Sulle pagine generate: in corso → «in corso», finita → «finale», da giocare → kickoff."""
    st = _seed(tmp_path)
    now = datetime.now(UTC)
    fx = st.read("fixtures")
    # la gara campione finita diventa **in corso** con il punteggio live (il caso reale del 19/09).
    # Lo stato e il punteggio vanno scritti anche in `match_info`: la scheda partita legge prima
    # quella tabella (`analysis.build`: `_val(info, "status") or f["status"]`).
    fx.loc[fx.match_id == 5749645, "utc_kickoff"] = now - timedelta(hours=1)
    fx.loc[fx.match_id == 5749645, "status"] = "live"
    fx.loc[fx.match_id == 5749645, "home_goals"] = 1
    fx.loc[fx.match_id == 5749645, "away_goals"] = 0
    st.write("fixtures", fx)
    mi = st.read("match_info")
    mi.loc[mi.match_id == 5749645, "status"] = "live"
    mi.loc[mi.match_id == 5749645, "home_goals"] = 1
    mi.loc[mi.match_id == 5749645, "away_goals"] = 0
    st.write("match_info", mi)

    out = tmp_path / "sito"
    builder = SiteBuilder(store=st, out_dir=out)
    builder.build_indexes(st.read("fixtures"))
    builder.build_match_pages({5749645, 5749669})

    lista = (out / "index.html").read_text(encoding="utf-8")
    card = re.search(r'data-status="live".*?<div class="match-score">.*?<span>(.*?)</span>',
                     lista, re.DOTALL)
    assert card, "la gara in corso non è nella pagina «Oggi»"
    assert card.group(1) == "in corso"
    # nessuna card con un punteggio giocato dice ancora «calcio d'inizio»
    for blocco in lista.split('<article class="match-card"')[1:]:
        stato = re.search(r'data-status="(\w+)"', blocco).group(1)
        scritta = re.search(r'<div class="match-score">.*?<span>(.*?)</span>', blocco,
                            re.DOTALL).group(1)
        if stato != "scheduled":
            assert scritta != "calcio d'inizio", (stato, scritta)
        else:
            assert scritta == "calcio d'inizio", "una gara da giocare resta «calcio d'inizio»"

    # l'hero della scheda: il punteggio live dichiara di essere live, l'orario resta leggibile.
    # (Il punteggio dell'hero viene dal contesto della gara, non dalla riga di `fixtures` che
    # questo test ha spostato: qui conta la didascalia, non il valore.)
    live = (out / "partite" / "5749645.html").read_text(encoding="utf-8")
    hero = re.search(r'<span class="result">(.*?)</span><span class="date">(.*?)</span>', live,
                     re.DOTALL)
    assert hero.group(1) != "vs", "una gara in corso ha un punteggio"
    assert hero.group(2).startswith("in corso · calcio d'inizio "), hero.group(2)

    # la gara futura campione non cambia: «vs» e «calcio d'inizio · HH:MM»
    futura = (out / "partite" / "5749669.html").read_text(encoding="utf-8")
    hero2 = re.search(r'<span class="result">(.*?)</span><span class="date">(.*?)</span>', futura,
                      re.DOTALL)
    assert hero2.group(1) == "vs"
    assert hero2.group(2).startswith("calcio d'inizio · "), hero2.group(2)
    st.close()


def test_verify_site_ferma_la_didascalia_sbagliata(tmp_path):
    """Morso dell'invariante [37]: il gate vede il difetto che era pubblicato e passa sul corretto."""
    vs = _site_module()
    site = tmp_path / "site"
    site.mkdir()
    (site / "partite").mkdir()

    def card(stato: str, punteggio: str, didascalia: str) -> str:
        return (f'<article class="match-card" data-status="{stato}">'
                f'<div class="match-score"><strong>{punteggio}</strong>'
                f'<span>{didascalia}</span></div></article>')

    # il difetto reale: punteggio live con didascalia «calcio d'inizio»
    (site / "index.html").write_text(card("live", "1–0", "calcio d'inizio")
                                     + card("finished", "2–3", "finale")
                                     + card("scheduled", "vs", "calcio d'inizio"),
                                     encoding="utf-8")
    # e lo stesso nell'hero della scheda
    (site / "partite" / "1.html").write_text(
        '<span class="result">1–0</span><span class="date">calcio d\'inizio · 15:00</span>',
        encoding="utf-8")
    fails, checks = vs.check_didascalie_punteggio(site)
    assert checks == 4                       # 3 card + 1 hero
    assert any('didascalia «calcio d\'inizio» su una gara «live»' in f for f in fails), fails
    assert any("hero «1–0» con didascalia" in f for f in fails), fails
    # le due card corrette non sono segnalate
    assert len(fails) == 2, fails

    # stesso sito, didascalie giuste → il gate passa
    (site / "index.html").write_text(card("live", "1–0", "in corso")
                                     + card("finished", "2–3", "finale")
                                     + card("scheduled", "vs", "calcio d'inizio"),
                                     encoding="utf-8")
    (site / "partite" / "1.html").write_text(
        '<span class="result">1–0</span><span class="date">in corso · calcio d\'inizio 15:00</span>',
        encoding="utf-8")
    fails, checks = vs.check_didascalie_punteggio(site)
    assert checks == 4 and fails == []


def test_percentile_ids_ordine_dichiarato_su_ogni_hash_seed():
    """`docs/40` §5.1: l'ordine delle card «Percentili di lega» non dipende più dal processo.

    Con il `set` due build **dello stesso codice** davano 2.074 schede giocatore su 3.748 in
    sequenza diversa (misurato); qui la stessa chiamata è eseguita in quattro processi con
    `PYTHONHASHSEED` diversi e l'ordine deve essere identico e uguale a quello dichiarato.
    """
    from fda.site.players import PCT_EXTRA, RADAR, percentile_ids

    codice = ("from fda.site.players import percentile_ids;"
              "print('|'.join(f'{p}:' + ','.join(percentile_ids(p)) for p in (0, 1, 2, 3)))")
    uscite = set()
    for seed in ("0", "1", "2", "7"):
        # l'ambiente del test resta intatto (in CI l'interprete può dipendere da variabili sue):
        # cambia solo il seed dell'hash, che è ciò che prima spostava l'ordine
        env = {**os.environ, "PYTHONHASHSEED": seed}
        proc = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True,
                              env=env, check=True, cwd=str(Path(__file__).resolve().parents[1]))
        uscite.add(proc.stdout.strip())
    assert len(uscite) == 1, f"l'ordine cambia con l'hash seed: {uscite}"
    for pos in (0, 1, 2, 3):
        assert percentile_ids(pos) == [s for s, _ in RADAR[pos]] + PCT_EXTRA[pos]
