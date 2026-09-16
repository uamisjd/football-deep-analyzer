"""Interfaccia a riga di comando: `fda <comando>`."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import DETAIL_WINDOW_DAYS, leagues, season

app = typer.Typer(help="Football Deep Analyzer", no_args_is_help=True)
console = Console()


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Log dettagliato")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def version() -> None:
    """Mostra la versione."""
    console.print(f"football-deep-analyzer {__version__} — stagione {season()}")


@app.command("leagues")
def leagues_cmd() -> None:
    """Elenca i campionati configurati."""
    table = Table(title=f"Campionati seguiti — stagione {season()}")
    for col in ("Key", "Nome", "FotMob", "ESPN", "Understat", "football-data"):
        table.add_column(col)
    for lg in leagues():
        table.add_row(lg.key, lg.name, str(lg.fotmob_id), lg.espn_code,
                      lg.understat_slug or "—", lg.footballdata_code)
    console.print(table)


if __name__ == "__main__":
    app()


@app.command("fotmob-fixtures")
def fotmob_fixtures_cmd(league_key: str = typer.Argument("ITA1")) -> None:
    """Scarica il calendario stagionale di un campionato da FotMob e stampa un riepilogo."""
    from collections import Counter

    from .config import league
    from .sources.fotmob import FotMobClient

    lg = league(league_key)
    fm = FotMobClient()
    raw = fm.fixtures_raw(lg.fotmob_id)
    fm.save_raw(f"fixtures_{lg.key}_{season().replace('/', '-')}", raw)
    fx = fm.parse_fixtures(lg.fotmob_id, raw)
    counts = Counter(f.status for f in fx)
    console.print(f"{lg.name}: {len(fx)} partite — " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    nxt = [f for f in fx if f.status == "scheduled" and f.utc_kickoff][:5]
    for f in nxt:
        console.print(f"  {f.utc_kickoff:%d/%m %H:%M} UTC  {f.home_name} - {f.away_name}  (id {f.match_id})")
    console.print(f"richieste={fm.http.stats.requests} cache={fm.http.stats.cache_hits}")


@app.command("fotmob-match")
def fotmob_match_cmd(match_id: int) -> None:
    """Scarica i dettagli di una partita da FotMob, salva il JSON grezzo e stampa un riepilogo."""
    from .sources.fotmob import FotMobClient

    fm = FotMobClient()
    raw = fm.match_details_raw(match_id)
    fm.save_raw(f"match_{match_id}", raw)
    b = fm.parse_match(raw)
    i = b.info
    console.print(f"[bold]{match_id}[/bold] {i.status} | lega {i.league_id} | giornata {i.round} | "
                  f"{i.utc_kickoff:%d/%m/%Y %H:%M} UTC")
    console.print(f"gol {i.home_goals}-{i.away_goals} | xG {i.home_xg}-{i.away_xg} | xGOT {i.home_xgot}-{i.away_xgot}")
    console.print(f"arbitro {i.referee_name} ({i.referee_matches} gare, {i.referee_yellows_per_match} gialli/gara) | "
                  f"stadio {i.stadium_name} | pubblico {i.attendance} | meteo {i.weather_desc} {i.weather_temp_c}°C")
    console.print(f"formazione: {i.lineup_type} {i.home_formation} vs {i.away_formation} | "
                  f"valore titolari €{(i.home_starters_value_eur or 0)/1e6:.1f}M vs €{(i.away_starters_value_eur or 0)/1e6:.1f}M")
    unav = [p for p in b.lineup if p.role == "unavailable"]
    console.print(f"tiri={len(b.shots)} stat_squadra={len(b.team_stats)} stat_giocatori={len(b.player_stats)} "
                  f"formazione={len(b.lineup)} eventi={len(b.events)} indisponibili={len(unav)} h2h={len(b.h2h_matches)}")
    for p in unav[:8]:
        console.print(f"  OUT {p.player_name} ({p.team_id}) {p.unavailability_type} → {p.expected_return}")


@app.command("fotmob-table")
def fotmob_table_cmd(league_key: str = typer.Argument("ITA1")) -> None:
    """Scarica la tabella di lega da FotMob e stampa la classifica."""
    from .config import league
    from .sources.fotmob import FotMobClient

    lg = league(league_key)
    fm = FotMobClient()
    raw = fm.league_raw(lg.fotmob_id)
    fm.save_raw(f"table_{lg.key}", raw)
    rows = fm.parse_league_table(lg.key, raw)
    console.print(f"{lg.name}: {len(rows)} squadre in classifica")
    for r in rows:
        console.print(f"  {r.rank or '-':>2}° {r.team_name} — {r.points} pt in {r.played} gare "
                      f"({r.wins}V {r.draws}N {r.losses}P, gol {r.goals_for}:{r.goals_against})")
    console.print(f"richieste={fm.http.stats.requests} cache={fm.http.stats.cache_hits}")


@app.command("understat-table")
def understat_table_cmd(league_key: str = typer.Argument("ITA1")) -> None:
    """Tabella xG di stagione da Understat (solo 5 grandi leghe)."""
    from .config import league, season_start_year
    from .sources.understat import UnderstatClient, team_season_table

    lg = league(league_key)
    if not lg.has_understat:
        console.print(f"{lg.name}: Understat non disponibile (xG solo da FotMob)")
        raise typer.Exit(code=0)
    uc = UnderstatClient()
    raw = uc.league_raw(lg.understat_slug, season_start_year())
    rows = team_season_table(uc.parse_team_matches(lg.understat_slug, season_start_year(), raw))
    table = Table(title=f"{lg.name} {season_start_year()} — xG (Understat)")
    for col in ("Squadra", "G", "Pt", "xPt", "xG", "xGA", "xGD", "PPDA"):
        table.add_column(col, justify="right" if col != "Squadra" else "left")
    for r in rows:
        table.add_row(r["team_name"], str(r["played"]), str(r["pts"]), f"{r['xpts']:.1f}",
                      f"{r['xg']:.2f}", f"{r['xga']:.2f}", f"{r['xgd']:+.2f}",
                      "—" if r["ppda"] is None else f"{r['ppda']:.1f}")
    console.print(table)
    console.print(f"richieste={uc.http.stats.requests} cache={uc.http.stats.cache_hits}")


@app.command("espn-today")
def espn_today_cmd(league_key: str = typer.Argument("ITA1"), day: str = typer.Option(None, help="YYYY-MM-DD")) -> None:
    """Partite del giorno + classifica da ESPN (fonte di riserva)."""
    from datetime import date

    from .config import league
    from .sources.espn import EspnClient

    lg = league(league_key)
    ec = EspnClient()
    d = date.fromisoformat(day) if day else None
    events, _ = ec.parse_scoreboard(lg.espn_code, ec.scoreboard_raw(lg.espn_code, d))
    console.print(f"{lg.name} — {len(events)} partite {d or 'oggi'}")
    for e in events[:12]:
        score = f"{e.home_goals}-{e.away_goals}" if e.home_goals is not None else "vs"
        console.print(f"  {e.utc_kickoff:%d/%m %H:%M} UTC  {e.home_name} {score} {e.away_name}  [{e.status}]")
    rows = ec.parse_standings(lg.espn_code, ec.standings_raw(lg.espn_code))
    console.print("classifica (prime 5): " + " | ".join(f"{r.rank}. {r.team_name} {r.points}" for r in rows[:5]))
    console.print(f"richieste={ec.http.stats.requests} cache={ec.http.stats.cache_hits}")


@app.command("collect")
def collect_cmd(
    league_keys: list[str] = typer.Argument(None, help="Es. ITA1 ENG1 (vuoto = tutti)"),
    past_days: int = typer.Option(3, help="Giorni indietro per i dettagli partita"),
    future_days: int = typer.Option(DETAIL_WINDOW_DAYS, help="Giorni avanti coi dettagli"),
    max_matches: int = typer.Option(40, help="Massimo partite per campionato per run"),
    max_backfill: int = typer.Option(40, help="Massimo partite finite recuperate per lega (fuori finestra)"),
) -> None:
    """Raccolta dati (calendario, dettagli partite, Understat, ESPN) → data/processed/*.parquet."""
    from .collect import collect_all
    from .store import Store

    store = Store()
    reports = collect_all(league_keys or None, store=store, past_days=past_days,
                          future_days=future_days, max_matches=max_matches, max_backfill=max_backfill)
    table = Table(title="Raccolta dati")
    for col in ("Lega", "Calendario", "Partite scaricate", "Saltate", "Understat", "ESPN", "Richieste", "Errori"):
        table.add_column(col)
    for r in reports:
        fetched = str(r.matches_fetched) + (f"+{r.matches_backfilled} storiche" if r.matches_backfilled else "")
        table.add_row(r.league, str(r.fixtures), fetched, str(r.matches_skipped),
                      str(r.understat_rows), str(r.espn_events),
                      " ".join(f"{k}={v}" for k, v in r.requests.items()),
                      f"[red]{len(r.errors)}[/red]" if r.errors else "0")
    console.print(table)
    for r in reports:
        for e in r.errors[:5]:
            console.print(f"  [red]{r.league}[/red] {e[:160]}")
    console.print(store.summary().to_string(index=False))
    store.close()
    if any(r.errors for r in reports) and all(r.fixtures == 0 for r in reports):
        raise typer.Exit(code=1)      # tutto fallito → il run in Actions deve risultare rosso


@app.command("db")
def db_cmd(query: str = typer.Argument(None, help="Query SQL opzionale sulle tabelle Parquet")) -> None:
    """Riepilogo del database (o esecuzione di una query SQL)."""
    from .store import Store

    store = Store()
    if query:
        console.print(store.sql(query).head(50).to_string(index=False))
    else:
        console.print(store.summary().to_string(index=False) if not store.summary().empty
                      else "database vuoto: esegui `fda collect`")
    store.close()


@app.command("predict")
def predict_cmd(
    league_keys: list[str] = typer.Argument(None, help="Es. ITA1 ENG1 (vuoto = tutti)"),
    seasons_back: int = typer.Option(3, help="Stagioni storiche da scaricare oltre a quella corrente"),
    days_ahead: int = typer.Option(0, help="Prevedi le partite nei prossimi N giorni (0 = tutto il calendario)"),
) -> None:
    """Addestra Dixon-Coles + Elo (storico datahub + risultati FotMob correnti) e salva `predictions`.

    Con `days_ahead=0` (default) prevede **tutte le partite in programma** del calendario già
    raccolto: non costa una richiesta in più, perché l'elenco delle partite arriva da una sola
    chiamata per lega (`fixtures`) e il modello ha bisogno solo di squadre e storico. Ciò che
    resta legato alla vicinanza della gara sono i **dettagli** (formazioni, infermeria, meteo,
    arbitro), raccolti da `fda collect` nella finestra `future_days`: la scheda di una partita
    lontana mostra il modello e i segnaposto onesti per ciò che la fonte non ha ancora pubblicato.
    """
    import warnings
    from datetime import datetime, timedelta, timezone

    import pandas as pd

    from .config import leagues, season_start_year
    from .models.calibration import from_store
    from .models.predict import latest_per_match, predict_matches
    from .sources.history import HistoryClient
    from .store import Store
    from .teams import canonical

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    store = Store()
    hc = HistoryClient()
    fixtures = store.read("fixtures")
    now = datetime.now(timezone.utc)
    yr = season_start_year()
    cal = from_store(store)
    if not cal.is_identity:
        console.print(f"calibrazione attiva: λ×{cal.lambda_scale:.4f} ρ{cal.rho_shift:+.2f} "
                      f"({cal.estimator}, {cal.fitted_at:%Y-%m-%d %H:%M} UTC)")
        console.print(f"  campione: {cal.corpus}")
    else:
        console.print("calibrazione: identità (esegui `fda calibrate` dopo un `fda backtest`)")
    # una riga per partita: le versioni accumulate dai run precedenti vengono collassate
    # sull'ultima (migrazione della chiave vecchia e garanzia a regime)
    vecchie = store.read("predictions")
    if not vecchie.empty:
        collassate = latest_per_match(vecchie)
        if len(collassate) != len(vecchie):
            store.write("predictions", collassate)
            console.print(f"previsioni: {len(vecchie)} righe → {len(collassate)} (una per partita)")
    total = 0
    for lg in leagues(league_keys or None):
        try:
            from .models.season_sim import build_hist

            hist = build_hist(lg, fixtures, hc, seasons_back=seasons_back, yr=yr, store=store)
            if hist.empty:
                console.print(f"[yellow]{lg.name}: nessuno storico disponibile, previsione saltata[/yellow]")
                continue
            upcoming = fixtures[(fixtures.league_id == lg.fotmob_id) & (fixtures.status == "scheduled")
                                & (fixtures.utc_kickoff >= now)] if not fixtures.empty else pd.DataFrame()
            if days_ahead > 0 and not upcoming.empty:
                upcoming = upcoming[upcoming.utc_kickoff <= now + timedelta(days=days_ahead)]
            if upcoming.empty:
                orizzonte = f"nei prossimi {days_ahead} giorni" if days_ahead > 0 else "in programma"
                console.print(f"{lg.name}: storico {len(hist)} partite, nessuna partita {orizzonte}")
                continue
            up = pd.DataFrame({"match_id": upcoming.match_id, "league_key": lg.key, "utc_kickoff": upcoming.utc_kickoff,
                               "home": upcoming.home_name.map(canonical), "away": upcoming.away_name.map(canonical)})
            from .models.predict import xi_for_league
            xi_lg = xi_for_league(lg.key)
            pred, dc, _ = predict_matches(hist, up, calibration=cal, xi=xi_lg)
            n = store.upsert("predictions", pred)
            total += n
            console.print(f"{lg.name}: storico {len(hist)} partite → {n} previsioni "
                          f"(home adv {dc.model.get_params().get('home_advantage', 0):.3f}"
                          f" · ξ {xi_lg}"
                          f"{'' if xi_lg == 0.0018 else ' (per lega, laboratorio P3-a)'})")
            for r in pred.head(4).itertuples(index=False):
                console.print(f"  {r.utc_kickoff:%d/%m %H:%M} {r.home}-{r.away}: {r.p_home:.0%}/{r.p_draw:.0%}/{r.p_away:.0%} "
                              f"λ {r.lambda_home:.2f}-{r.lambda_away:.2f} O2.5 {r.p_over25:.0%}")
        except Exception as exc:  # una lega senza storico non deve interrompere le altre
            console.print(f"[yellow]{lg.name}: previsione saltata ({type(exc).__name__}: {exc})[/yellow]")
    console.print(f"previsioni salvate: {total} | richieste storico={hc.http.stats.requests}")
    store.close()


@app.command("simulate")
def simulate_cmd(
    # stesso stile degli altri comandi (typer richiede la chiamata nel default)
    league_keys: list[str] = typer.Argument(None, help="Es. ITA1 ENG1 (vuoto = tutti)"),  # noqa: B008
    sims: int = typer.Option(10000, help="Numero di stagioni simulate per lega"),
    seasons_back: int = typer.Option(3, help="Stagioni storiche oltre a quella corrente"),
) -> None:
    """Monte Carlo del resto di stagione → tabella `season_sim` (prob. titolo/top-4/retrocessione)."""
    from .models.season_sim import simulate_all
    from .store import Store

    store = Store()
    res = simulate_all(league_keys or None, store=store, n_sims=sims, seasons_back=seasons_back)
    if res.empty:
        console.print("[yellow]nessuna simulazione salvata (storico o calendario mancanti)[/yellow]")
    else:
        for lk, grp in res.groupby("league_key"):
            top3 = grp.sort_values("exp_points", ascending=False).head(3)
            console.print(f"{lk}: " + " · ".join(
                f"{r.team} {r.exp_points:.0f}pt ({r.p_title:.0%} titolo, {r.p_rel:.0%} retro)"
                for r in top3.itertuples()))
        console.print(f"righe season_sim: {len(res)}")
    store.close()


@app.command("backtest")
def backtest_cmd(
    league_keys: list[str] = typer.Argument(None, help="Es. ITA1 ENG1 (vuoto = tutti)"),  # noqa: B008
    seasons_back: int = typer.Option(3, help="Stagioni storiche da scaricare oltre a quella corrente"),
    step_days: int = typer.Option(14, help="Ampiezza della finestra di valutazione, in giorni"),
    min_train: int = typer.Option(200, help="Partite minime di storico prima di iniziare a valutare"),
) -> None:
    """Backtest cronologico fuori campione sullo storico → tabella `backtest` (card su Accuratezza)."""
    import warnings

    from .config import leagues, season_start_year
    from .models.backtest import backtest_summary, chronological_backtest
    from .sources.history import HistoryClient
    from .store import Store

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    store = Store()
    hc = HistoryClient()
    fixtures = store.read("fixtures")
    yr = season_start_year()
    totale = 0
    for lg in leagues(league_keys or None):
        try:
            from .models.season_sim import build_hist

            hist = build_hist(lg, fixtures, hc, seasons_back=seasons_back, yr=yr, store=store)
            if hist.empty:
                console.print(f"[yellow]{lg.name}: nessuno storico disponibile, backtest saltato[/yellow]")
                continue
            res = chronological_backtest(hist, step_days=step_days, min_train=min_train)
            if res.empty:
                console.print(f"[yellow]{lg.name}: storico di {len(hist)} partite, troppo breve "
                              f"(minimo {min_train}) per il backtest[/yellow]")
                continue
            totale += store.upsert("backtest", res, replace_by="league_key")
            r = backtest_summary(res)
            console.print(f"{lg.name}: {r['n']} gare fuori campione · RPS {r['rps']:.4f} "
                          f"(base {r['naive']:.4f}, Δ {r['delta']:+.4f}) · log-loss {r['logloss']:.4f} · "
                          f"esito azzeccato {r['hit']:.0%}")
        except Exception as exc:  # una lega senza storico non deve interrompere le altre
            console.print(f"[yellow]{lg.name}: backtest saltato ({type(exc).__name__}: {exc})[/yellow]")
    console.print(f"backtest salvato: {totale} gare | richieste storico={hc.http.stats.requests}")
    store.close()


@app.command("calibrate")
def calibrate_cmd(
    min_rows: int = typer.Option(1200, help="Gare fuori campione minime per stimare i parametri"),
    folds: int = typer.Option(6, help="Finestre cronologiche per la validazione walk-forward"),
    dry_run: bool = typer.Option(False, help="Mostra i parametri senza salvarli"),
) -> None:
    """Stima la calibrazione della griglia (λ×m, ρ+Δ) dal `backtest` e la salva.

    Usa **solo** stime fuori campione già prodotte: nessun risultato futuro entra nel fit.
    Va eseguito dopo `fda backtest`; `fda predict` applica l'ultima calibrazione salvata.
    """
    from .models.calibration import fit
    from .store import Store

    store = Store()
    bt = store.read("backtest")
    if bt.empty:
        console.print("[yellow]nessun backtest nello store: esegui prima `fda backtest`[/yellow]")
        store.close()
        return
    cal = fit(bt, folds=folds, min_rows=min_rows)
    m = cal.metrics
    console.print(f"campione: {cal.corpus}")
    if cal.is_identity:
        console.print("[yellow]calibrazione identica (campione insufficiente o nessun guadagno)[/yellow]")
    else:
        console.print(f"parametri: λ×{cal.lambda_scale:.4f} · ρ{cal.rho_shift:+.2f} ({cal.version})")
        console.print(f"stimatore: {cal.estimator} · finestra {cal.window_days or 'tutto lo storico'} "
                      f"giorni ({int(m.get('stima_n', 0))} gare) · la griglia di punteggio avrebbe scelto "
                      f"λ×{m.get('confronto_scale_griglia', float('nan')):.2f} "
                      f"ρ{m.get('confronto_shift_griglia', float('nan')):+.2f}")
    if m:
        console.print(
            f"walk-forward ({int(m.get('holdout_n', 0))} gare tenute fuori): "
            f"RPS {m.get('holdout_rps_prima', 0):.4f} → {m.get('holdout_rps_dopo', 0):.4f} "
            f"({m.get('holdout_rps_delta', 0):+.4f}) · Brier mercati "
            f"{m.get('holdout_brier_prima', 0):.4f} → {m.get('holdout_brier_dopo', 0):.4f} "
            f"({m.get('holdout_brier_delta', 0):+.4f}) · bias λ "
            f"{m.get('holdout_bias_lambda_prima', 0):+.3f} → {m.get('holdout_bias_lambda_dopo', 0):+.3f} gol")
        console.print(
            f"sul campione pieno: bias λ {m.get('campione_bias_lambda', 0):+.3f} → "
            f"{m.get('dopo_bias_lambda', 0):+.3f} gol · pareggio previsto "
            f"{m.get('campione_pareggio_previsto', 0):.1%} → {m.get('dopo_pareggio_previsto', 0):.1%} "
            f"(osservato {m.get('campione_pareggio_osservato', 0):.1%})")
    if not dry_run:
        store.upsert("calibration", [cal.as_row()])
        console.print("calibrazione salvata in data/processed/calibration.parquet")
    store.close()


@app.command("lab")
def lab_cmd(
    league_keys: list[str] = typer.Argument(None, help="Es. ITA1 ENG1 (vuoto = tutti)"),  # noqa: B008
    seasons_back: int = typer.Option(3, help="Stagioni storiche oltre a quella corrente"),
    step_days: int = typer.Option(28, help="Ampiezza della finestra di valutazione, in giorni"),
    min_train: int = typer.Option(600, help="Partite minime di storico prima di valutare"),
    candidates: str = typer.Option("", help="Solo questi candidati, separati da spazio (vuoto = tutti)"),
    history: str = typer.Option("", help="Parquet con lo storico (offline) invece di scaricarlo"),
    max_windows: int = typer.Option(0, help="Limite di finestre per lega (0 = nessun limite)"),
    self_calibrate: bool = typer.Option(True, help="Ogni candidato corregge il proprio livello dei gol"),
    save: bool = typer.Option(True, help="Salva il riepilogo in data/processed/model_lab.parquet"),
) -> None:
    """Laboratorio: confronto fuori campione di famiglie di modelli, iperparametri e miscele."""
    import warnings

    import pandas as pd

    from .models import lab
    from .models.calibration import from_store
    from .store import Store

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    store = Store()
    cal = from_store(store)
    if history:
        hist_all = pd.read_parquet(history)
        console.print(f"storico da {history}: {len(hist_all)} gare, "
                      f"{hist_all['league_key'].nunique() if 'league_key' in hist_all else 1} leghe")
    else:
        from .config import leagues, season_start_year
        from .models.season_sim import build_hist
        from .sources.history import HistoryClient

        hc = HistoryClient()
        fixtures = store.read("fixtures")
        yr = season_start_year()
        frames = []
        for lg in leagues(league_keys or None):
            try:
                h = build_hist(lg, fixtures, hc, seasons_back=seasons_back, yr=yr, store=store)
                if not h.empty:
                    h = h.copy()
                    h["league_key"] = lg.key
                    frames.append(h)
                    console.print(f"{lg.name}: {len(h)} gare di storico")
            except Exception as exc:  # noqa: BLE001 — una lega senza storico non ferma il laboratorio
                console.print(f"[yellow]{lg.name}: storico saltato ({type(exc).__name__}: {exc})[/yellow]")
        hist_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if hist_all.empty:
        console.print("[yellow]nessuno storico disponibile: laboratorio saltato[/yellow]")
        store.close()
        return

    wanted = lab.CANDIDATES
    if candidates.strip():
        keys = set(candidates.split())
        wanted = tuple(c for c in lab.CANDIDATES if c.key in keys)
        if not wanted:
            console.print(f"[red]nessun candidato noto fra {sorted(keys)}; disponibili: "
                          f"{[c.key for c in lab.CANDIDATES]}[/red]")
            store.close()
            return
    console.print(f"candidati: {len(wanted)} · finestre di {step_days} giorni · min_train {min_train}"
                  f" · calibrazione {'λ×%.2f ρ%+.2f' % (cal.lambda_scale, cal.rho_shift) if not cal.is_identity else 'identità'}")
    rows = lab.walk_forward(hist_all, wanted, step_days=step_days, min_train=min_train,
                            calibration=cal, max_windows=max_windows or None,
                            self_calibrate=self_calibrate)
    if rows.empty:
        console.print("[yellow]nessuna gara valutata (storico troppo breve?)[/yellow]")
        store.close()
        return
    summary = lab.summarize(rows)
    by_league = lab.per_league(rows)
    console.print(f"\ngare valutate: {rows.drop_duplicates(['date', 'league_key', 'home', 'away']).shape[0]}")
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        console.print(summary[["candidate", "n", "rps", "delta_rps", "delta_rps_lo95", "delta_rps_hi95",
                               "logloss", "hit", "bias_lambda", "brier_mercati", "migliore_in"]]
                      .round(4).to_string(index=False))
    if save:
        all_rows = summary.assign(league_key="ALL")
        store.upsert("model_lab", pd.concat([all_rows, by_league], ignore_index=True).to_dict("records"),
                     replace_by="candidate")
        console.print("riepilogo salvato in data/processed/model_lab.parquet")
    store.close()


@app.command("lab-xi")
def lab_xi_cmd(
    step_days: int = typer.Option(90, help="Ampiezza della finestra di valutazione, in giorni"),
    min_train: int = typer.Option(800, help="Partite minime di storico prima di valutare"),
    history: str = typer.Option("", help="Parquet con lo storico (offline) invece dello store"),
    save: bool = typer.Option(True, help="Salva in data/processed/xi_league.parquet"),
) -> None:
    """ξ per lega: walk-forward sulla griglia, ΔRPS appaiato contro lo ξ globale (docs/21 P3-a)."""
    import pandas as pd

    from .models import lab
    from .store import Store

    store = Store()
    if history:
        hist = pd.read_parquet(history)
    else:
        hist = store.read("history")
    if hist.empty:
        console.print("[yellow]storico assente: nessun numero inventato, esperimento saltato[/yellow]")
        store.close()
        return
    df = lab.xi_league_experiment(hist, step_days=step_days, min_train=min_train)
    if df.empty:
        console.print("[yellow]nessuna lega valutabile (storico troppo breve?)[/yellow]")
        store.close()
        return
    df["delta"] = df["delta"].round(4)
    df["ci_lo"] = df["ci_lo"].round(4)
    df["ci_hi"] = df["ci_hi"].round(4)
    df["rps_global"] = df["rps_global"].round(4)
    df["rps_best"] = df["rps_best"].round(4)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        console.print(df.to_string(index=False))
    n_adottate = int(df.adopt.sum())
    console.print(f"\nleghe che adottano il proprio ξ: {n_adottate} su {len(df)} "
                  "(regola: IC 95% del ΔRPS interamente negativo e ≥300 gare fuori campione)")
    if save:
        store.write("xi_league", df)
        console.print("salvato data/processed/xi_league.parquet")
    store.close()


@app.command("mercati-monitor")
def mercati_monitor_cmd(
    save: bool = typer.Option(True, help="Salva in data/processed/mercati_monitor.parquet"),
) -> None:
    """Mercati binari sul backtest fuori campione: scarto, stabilità temporale e leghe (P3-b)."""
    import pandas as pd

    from .models.backtest import calibrate_rows, market_monitor
    from .models.calibration import from_store
    from .store import Store

    store = Store()
    bt = store.read("backtest")
    if bt.empty:
        console.print("[yellow]backtest assente: esegui `fda backtest` (lo salva il daily)[/yellow]")
        store.close()
        return
    # probabilità come pubblicate oggi (griglia calibrata), coerente con la pagina Accuratezza
    df = market_monitor(calibrate_rows(bt, from_store(store)))
    if df.empty:
        console.print("[yellow]nessun mercato valutabile[/yellow]")
        store.close()
        return
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        console.print(df.to_string(index=False))
    n_str = int((df.verdict == "strutturale").sum())
    console.print(f"\nmercati «strutturali»: {n_str} su {len(df)} — gli altri si monitorano "
                  "run per run; il modello non si tocca (regola P3)")
    if save:
        store.write("mercati_monitor", df)
        console.print("salvato data/processed/mercati_monitor.parquet")
    store.close()


@app.command("build")
def build_cmd() -> None:
    """Genera il sito statico in site/ (Oggi, Prossime, Risultati, partite, Giocatori, Accuratezza, Stato)."""
    from .site.build import SITE_DIR, SiteBuilder
    from .store import Store

    store = Store()
    res = SiteBuilder(store=store).build()
    console.print(f"sito generato in {SITE_DIR}: {res}")
    store.close()


@app.command("daily")
def daily_cmd(
    league_keys: list[str] = typer.Argument(None, help="Es. ITA1 ENG1 (vuoto = tutti)"),
    skip_predict: bool = typer.Option(False, help="Salta i modelli (solo raccolta + sito)"),
) -> None:
    """Run giornaliero completo: collect → predict → build. È ciò che esegue GitHub Actions."""
    from typer.testing import CliRunner  # noqa: F401  (import di controllo)

    # DETAIL_WINDOW_DAYS: i dettagli (incluse le coordinate stadio) sono raccolti per l'intera
    # finestra "prossime", così il meteo previsionale Open-Meteo può colmare il vuoto FotMob.
    collect_cmd(league_keys=league_keys, past_days=3, future_days=DETAIL_WINDOW_DAYS,
                max_matches=40, max_backfill=40)
    if not skip_predict:
        try:  # calibrazione della griglia dal backtest del run precedente (solo dati passati)
            calibrate_cmd()
        except Exception as exc:  # noqa: BLE001 — senza calibrazione si pubblica il modello grezzo
            console.print(f"[red]calibrate fallito: {exc}[/red]")
        try:  # tutto il calendario: zero richieste in più, il modello usa solo storico e squadre
            predict_cmd(league_keys=league_keys, seasons_back=3, days_ahead=0)
        except Exception as exc:  # i modelli non devono bloccare la pubblicazione dei dati
            console.print(f"[red]predict fallito: {exc}[/red]")
        try:  # backtest fuori campione: campione ampio per leggere la calibrazione senza rumore
            backtest_cmd(league_keys=league_keys, seasons_back=3, step_days=14, min_train=200)
        except Exception as exc:  # noqa: BLE001 — il backtest non deve bloccare il sito
            console.print(f"[red]backtest fallito: {exc}[/red]")
        try:  # monitoraggio mercati binari sul backtest appena rigenerato (docs/21 P3-b)
            mercati_monitor_cmd()
        except Exception as exc:  # noqa: BLE001 — il monitoraggio non deve bloccare il sito
            console.print(f"[red]mercati-monitor fallito: {exc}[/red]")
        try:  # Monte Carlo stagione: fallisce in isolato, il sito esce comunque
            from .models.season_sim import simulate_all
            from .store import Store

            store = Store()
            simulate_all(league_keys or None, store=store, n_sims=10000)
            store.close()
        except Exception as exc:  # noqa: BLE001 — la simulazione non deve bloccare il sito
            console.print(f"[red]simulate fallito: {exc}[/red]")
    build_cmd()
