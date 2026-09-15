"""Anti-regressione sull'etichetta della colonna «impatto» dell'infermeria (docs/21, Q1).

La dicitura «fuori rosa · n.d.» aveva due significati diversi (motivo FotMob «not in squad»
e assenza di statistiche di stagione) e contraddiceva righe come «infortunio · giorno per
giorno»: sulle schede pre-partita la colonna impatto deve dire «senza minuti in stagione»,
con tooltip che spiega il perché. Il motivo «not in squad» resta tradotto «fuori rosa»
(_UNAVAIL_IT) e non è toccato da questo test.
"""

from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "src" / "fda" / "site" / "templates" / "match.html"


def test_impatto_senza_minuti_etichetta_onesta() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "fuori rosa · n.d." not in html, "etichetta fuorviante tornata nella colonna impatto"
    assert "senza minuti in stagione · n.d." in html
    assert "non ha ancora minuti nelle statistiche di stagione" in html  # tooltip esplicativo


def test_motivo_not_in_squad_resta_fuori_rosa() -> None:
    from fda.site.analysis import unavailability_it

    assert unavailability_it("not in squad") == "fuori rosa"
    assert unavailability_it("injury") == "infortunio"
