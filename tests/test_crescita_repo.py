"""Test di ``scripts/crescita_repo.py`` (politica A di ``docs/105``, misure di ``docs/109`` §4).

Solo funzioni pure: nessun test legge la storia del repository o la rete, così non dipende da
quanto è profondo il clone in CI.
"""

from __future__ import annotations

import pytest

from scripts.crescita_repo import (
    DayRow,
    classify_commit,
    days_to_target,
    mean_recent,
    parse_raw_changes,
)

# Righe reali di `git diff-tree -r --raw` (formato: mode src mode dst sha-src sha-dst status\tpath)
RIGA_MODIFICA = ":100644 100644 2c23ba1a 4f9c1b7e M\tdata/processed/news.parquet"
RIGA_CREAZIONE = ":000000 100644 00000000 a1b2c3d4 A\tsrc/fda/site/estero.py"
RIGA_CANCELLAZIONE = ":100644 000000 5e6f7a8b 00000000 D\tdocs/vecchio.md"


def test_parse_raw_changes_tiene_modifiche_e_creazioni():
    out = parse_raw_changes(f"{RIGA_MODIFICA}\n{RIGA_CREAZIONE}")
    assert out == [
        ("4f9c1b7e", "data/processed/news.parquet"),
        ("a1b2c3d4", "src/fda/site/estero.py"),
    ]


def test_parse_raw_changes_scarta_le_cancellazioni():
    # una cancellazione non scrive byte: contarla gonfierebbe la misura della crescita
    assert parse_raw_changes(RIGA_CANCELLAZIONE) == []


def test_parse_raw_changes_ignora_righe_malformate():
    assert parse_raw_changes("non è una riga raw\n\n") == []


@pytest.mark.parametrize(
    ("percorsi", "atteso"),
    [
        # la fotografia completa del run tocca più Parquet
        (["data/processed/news.parquet", "data/processed/predictions.parquet"], "snapshot"),
        # il registro preregistrato è l'unica eccezione alla regola «una al giorno»
        (["data/processed/prospettico.parquet"], "registro"),
        (["data/processed/prospettico.parquet", "src/fda/site/analysis.py"], "registro"),
        (["docs/STATO.md", "README.md"], "codice"),
        ([], "vuoto"),
    ],
)
def test_classify_commit(percorsi, atteso):
    assert classify_commit(percorsi) == atteso


def test_days_to_target_aritmetica_e_confini():
    assert days_to_target(100.0, 10.0, 110.0) == pytest.approx(1.0)
    # bersaglio già superato: zero giorni, non un numero negativo
    assert days_to_target(1200.0, 10.0, 1024.0) == 0.0
    # ritmo nullo o negativo: non si arriva mai
    assert days_to_target(100.0, 0.0) is None
    assert days_to_target(100.0, -1.0) is None


def _row(day: str, mib: float, commits: int = 1) -> DayRow:
    return DayRow(day=day, commits=commits, snapshots=0, registro=0, files=1, mib=mib)


def test_mean_recent_usa_le_giornate_piu_recenti_con_commit():
    rows = [_row("2026-10-13", 30.0), _row("2026-10-14", 10.0), _row("2026-10-15", 2.0)]
    assert mean_recent(rows, 2) == pytest.approx(6.0)  # (10+2)/2, non (30+10)/2


def test_mean_recent_ignora_i_giorni_senza_commit():
    rows = [_row("2026-10-14", 8.0), _row("2026-10-15", 0.0, commits=0)]
    assert mean_recent(rows, 3) == pytest.approx(8.0)


def test_mean_recent_senza_giornate_piene_e_zero():
    assert mean_recent([_row("2026-10-15", 0.0, commits=0)], 3) == 0.0
    assert mean_recent([], 3) == 0.0
