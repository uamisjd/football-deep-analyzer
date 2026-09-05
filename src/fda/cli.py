"""Interfaccia a riga di comando: `fda <comando>`."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import leagues, season

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
