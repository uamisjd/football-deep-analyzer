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
