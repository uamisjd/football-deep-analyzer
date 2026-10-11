"""Mappa delle fonti: il sito sa dove andare a prendere tutto? (richiesta dell'11/10/2026).

Risponde a due domande con numeri, non a impressioni:

1. **La raccolta copre gli enti che il sito pubblica?** Per ogni tabella di
   ``data/processed`` che la scheda usa (calendario, dettagli, formazioni, eventi,
   classifiche, notizie, storia, coppe…) stampa righe, copertura per lega dove ha senso e
   freschezza (ultima modifica del file), così un buco si vede prima della pagina.
2. **La ricerca stampa sa dove cercare?** Per ognuna delle 132 squadre della stagione
   stampa la query configurata (``google_news_params``, la stessa funzione della
   raccolta), quante notizie ha in archivio negli ultimi 14 giorni e quante voci di clima
   produce, e cerca tre difetti con nome e cognome:
   - **chiave morta**: una voce di ``ITALIAN_SEARCH_NAMES`` che nessuna squadra incontra
     (era il caso di «Nottingham Forest» e «Borussia Mönchengladbach», mentre nei dati le
     squadre si chiamano «Nottm Forest» e «M'gladbach»: due squadre sotto-coprite);
   - **squadra senza query italiana**: nessuna chiave, nessun alias — si cerca il nome
     secco e la copertura dipende da quanto la stampa italiana usa quel nome;
   - **copertura bassa**: zero notizie in 14 giorni, o meno di 3 (il clima vive di voci).

Non fa richieste di rete e non scrive nulla: è un diagnostico da riga di comando,
come ``audit_clima.py``. Esce con codice 1 se trova difetti, così è usabile in una
verifica manuale senza toccare la CI (i gate di pagina restano in ``verify_site``).

Uso: ``.venv/bin/python scripts/audit_fonti.py`` (dopo un `fda daily`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

#: Tabelle che il sito legge, in ordine di lettura della scheda, con la cosa che coprono.
TABELLE: tuple[tuple[str, str], ...] = (
    ("fixtures", "calendario della stagione: la spina di ogni pagina"),
    ("predictions", "pronostico dei modelli (1X2, O/U, gol)"),
    ("match_info", "dettagli, meteo, formazioni, valore dei titolari"),
    ("lineup", "distinta, panchina, allenatore per gara"),
    ("player_stats", "statistiche dei giocatori"),
    ("team_stats", "statistiche di squadra per gara"),
    ("events", "gol, assist, cartellini"),
    ("understat_team_matches", "xG/xPTS di stagione (5 leghe)"),
    ("fotmob_standings", "classifica (fonte primaria)"),
    ("standings", "classifica (riserva ESPN)"),
    ("news", "rassegna stampa per squadra"),
    ("transfers", "mercato: acquisti, cessioni, rinnovi"),
    ("cup_fixtures", "coppe nazionali e internazionali"),
    ("history", "Elo storico per la forma"),
    ("season_sim", "simulazione di stagione"),
    ("h2h", "precedenti fra le due squadre"),
    ("insights", "letture della partita"),
)


def _freschezza(p: Path) -> str:
    if not p.exists():
        return "assente"
    import datetime as _dt
    return _dt.datetime.fromtimestamp(p.stat().st_mtime, tz=_dt.UTC).strftime("%d/%m %H:%M")


def main() -> int:
    from fda.config import leagues as _lgs
    from fda.sources.news import (
        ITALIAN_SEARCH_NAMES,
        classify_news,
        google_news_params,
        is_italian_news,
        is_low_reputation,
    )

    if not (DATA / "fixtures.parquet").exists():
        print("nessun dato in data/processed: esegui prima `fda daily`")
        return 1
    leghe = {int(lg.fotmob_id): lg.key for lg in _lgs()}

    print("=== 1. le tabelle che il sito legge ===")
    for nome, cosa in TABELLE:
        p = DATA / f"{nome}.parquet"
        if not p.exists():
            print(f"  ASSENTE  {nome:24s} {cosa}")
            continue
        df = pd.read_parquet(p)
        print(f"  {len(df):7d}  {nome:24s} {cosa} · aggiornata {_freschezza(p)}")
    fx = pd.read_parquet(DATA / "fixtures.parquet")
    print(f"\n  stagione: {fx.match_id.nunique()} gare · "
          f"{(fx.status == 'finished').sum()} finite · "
          f"{(fx.status == 'scheduled').sum()} da giocare · leghe {sorted(set(fx.league_id))}")

    # ---- 2. la ricerca stampa, squadra per squadra ----
    nd = pd.read_parquet(DATA / "news.parquet")
    nd["pa"] = pd.to_datetime(nd.published_at, utc=True, errors="coerce")
    adesso = nd.pa.max()
    squadre = fx.drop_duplicates("home_id")[["home_id", "home_name", "league_id"]].copy()
    squadre.columns = ["team_id", "team_name", "league_id"]
    temi = ("allenatore", "spogliatoio", "societa", "tifo", "stadio", "fuoricampo")
    clima = {int(t.team_id): 0 for t in squadre.itertuples()}
    for r in nd[nd.pa >= adesso - pd.Timedelta(days=14)].itertuples(index=False):
        titolo = str(getattr(r, "title", "") or "").strip()
        desc = getattr(r, "description", None)
        desc = "" if desc is None or pd.isna(desc) else str(desc)
        if not titolo or not is_italian_news(titolo, desc) or is_low_reputation(r.source):
            continue
        chiave, _p = classify_news(titolo, "", getattr(r, "source", None))
        if chiave in temi and int(r.team_id) in clima:
            clima[int(r.team_id)] += 1
    recenti = nd[nd.pa >= adesso - pd.Timedelta(days=14)].groupby("team_id").size()
    squadre["n14"] = squadre.team_id.map(recenti).fillna(0).astype(int)
    squadre["clima14"] = squadre.team_id.map(clima).fillna(0).astype(int)
    squadre["leg"] = squadre.league_id.map(leghe)

    print("\n=== 2. copertura della stampa per lega (14 giorni) ===")
    g = squadre.groupby("leg").agg(squadre=("team_id", "size"),
                                   con_notizie=("n14", lambda s: int((s > 0).sum())),
                                   mediana=("n14", "median"), minime=("n14", "min"),
                                   clima=("clima14", "sum"))
    print(g.to_string())

    difetti: list[str] = []
    avvisi: list[str] = []
    # chiavi non incontrate: un alias che nessuna squadra dei dati usa. Non è un difetto —
    # la mappa copre anche i nomi di altre stagioni e delle coppe (Hertha, Schalke,
    # Wolverhampton…) — ma va letto: se una chiave «morta» è solo l'abbreviazione di un
    # nome vivo, la query di quella squadra sta usando il nome sbagliato (docs/83 §1).
    nomi = {str(n) for n in squadre.team_name}
    from fda.sources.news import _norm_nome, italian_search_name
    non_incontrate = [k for k in ITALIAN_SEARCH_NAMES
                      if not any(_norm_nome(k) == _norm_nome(n) for n in nomi)]
    # squadre senza query mappata e copertura
    senza = squadre[squadre.team_name.map(lambda n: italian_search_name(str(n)) is None)]
    if len(senza):
        avvisi.append(f"{len(senza)} squadre su {len(squadre)} senza query italiana mappata "
                      f"(si cerca il nome secco): "
                      + " · ".join(sorted(senza.team_name.tolist())[:12])
                      + (" …" if len(senza) > 12 else ""))
    for r in squadre.itertuples(index=False):
        if r.n14 == 0:
            difetti.append(f"{r.leg} {r.team_name}: zero notizie in 14 giorni "
                           f"(query: {google_news_params(str(r.team_name))['q']})")
        elif r.n14 < 3:
            avvisi.append(f"{r.leg} {r.team_name}: {r.n14} notizie in 14 giorni "
                          f"(query: {google_news_params(str(r.team_name))['q']})")
    if non_incontrate:
        avvisi.append(f"{len(non_incontrate)} chiavi della mappa che nessuna squadra dei dati "
                      f"incontra (alias di altre stagioni o nomi abbreviati nei dati): "
                      + " · ".join(sorted(non_incontrate)[:10])
                      + (" …" if len(non_incontrate) > 10 else ""))

    print("\n=== 3. le squadre con meno copertura (sotto la mediana di 3) ===")
    basse = squadre.sort_values("n14").head(8)
    for r in basse.itertuples(index=False):
        q = google_news_params(str(r.team_name))["q"]
        print(f"  {r.leg}  {r.team_name[:22]:22s} notizie {r.n14:3d} · clima {r.clima14:2d} "
              f"· query {q[:52]}")

    print("\n=== esito ===")
    if avvisi:
        print(f"avvisi: {len(avvisi)}")
        for a_ in avvisi:
            print(f"  ~ {a_}")
    if difetti:
        print(f"difetti: {len(difetti)}")
        for d in difetti:
            print(f"  - {d}")
        return 1
    print("nessun difetto bloccante: ogni squadra dei dati ha una query (mappata o nome "
          "secco) e almeno una notizia in 14 giorni")
    return 0


if __name__ == "__main__":
    sys.exit(main())
