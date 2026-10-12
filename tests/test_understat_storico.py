"""Storico Understat (docs/90): stagioni precedenti a quella in corso, senza la corrente."""

from fda.cli import understat_storico_pianifica


def test_stagioni_precedenti_escludono_la_corrente():
    assert understat_storico_pianifica(2026, 5) == [2021, 2022, 2023, 2024, 2025]
    assert 2026 not in understat_storico_pianifica(2026, 5)


def test_zero_stagioni_non_scarica_nulla():
    assert understat_storico_pianifica(2026, 0) == []
