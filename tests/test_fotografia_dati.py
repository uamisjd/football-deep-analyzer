"""Test della regola «una fotografia dei dati al giorno» (scripts/fotografia_dati.py, docs/105).

Nessuna rete: la decisione è una funzione pura e la lettura dall'API si prova con un
finto lettore. I casi coprono le quattro situazioni reali del `daily` (cinque run al
giorno: 04, 10, 14, 18, 21:30 UTC) più la rete di sicurezza e il fail-open.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scripts import fotografia_dati as fd

# i cinque orari del cron di daily.yml (UTC)
ORA_MATTINA = 4
ORA_SERALE = 21


def quando(giorno: int, ora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 10, giorno, ora, minuto, tzinfo=UTC)


def test_prima_fotografia_in_assoluto() -> None:
    esito, motivo = fd.decide(quando(13, ORA_MATTINA), None)
    assert esito is True
    assert "nessuna fotografia precedente" in motivo


def test_fotografia_di_oggi_gia_salvata_non_si_ripete() -> None:
    for ora in (ORA_MATTINA, 14, ORA_SERALE):
        esito, motivo = fd.decide(quando(13, ora), quando(13, ORA_SERALE - 1, 30))
        assert esito is False, f"alle {ora} UTC non deve ripetere la fotografia di oggi"
        assert "già salvata" in motivo


def test_run_serale_salva_la_fotografia_del_giorno() -> None:
    esito, motivo = fd.decide(quando(13, ORA_SERALE), quando(12, ORA_SERALE, 30))
    assert esito is True
    assert "run serale" in motivo


def test_run_di_mattina_il_giorno_dopo_non_salva() -> None:
    # ieri sera alle 21:30 → oggi alle 04:00 sono 6,5 ore: la fotografia di ieri sera è fresca
    esito, motivo = fd.decide(quando(13, ORA_MATTINA), quando(12, ORA_SERALE, 30))
    assert esito is False
    assert "si aspetta il run" in motivo


def test_rete_di_sicurezza_dopo_24_ore() -> None:
    # il run serale di ieri è fallito (ultima fotografia: 12/10 alle 04:00) → il primo run
    # utile di oggi recupera, anche se non è serale
    esito, motivo = fd.decide(quando(13, 10), quando(12, ORA_MATTINA))
    assert esito is True
    assert "rete di sicurezza" in motivo


def test_confine_delle_24_ore() -> None:
    ultima = quando(12, 10)
    prima, _ = fd.decide(quando(13, 9, 59), ultima)
    dopo, _ = fd.decide(quando(13, 10, 0), ultima)
    assert prima is False and dopo is True


def test_istante_ingenuo_viene_letto_come_utc() -> None:
    # le date dell'API e di git sono UTC con offset; un istante senza fuso non deve
    # cambiare la decisione (né far esplodere il confronto)
    esito, _ = fd.decide(
        datetime(2026, 10, 13, 21, 0),  # noqa: DTZ001 — l'istante ingenuo È il caso in prova
        datetime(2026, 10, 12, 21, 30),  # noqa: DTZ001
    )
    assert esito is True


def test_fail_open_se_la_lettura_fallisce() -> None:
    def lettore_rotto(repo: str, ramo: str, token: str | None = None):
        raise RuntimeError("403 rate limit")

    esito, motivo = fd.decidi_dal_repository("uamisjd/progetto", "main", quando(13, ORA_MATTINA), None, lettore_rotto)
    assert esito is True
    assert "fail-open" in motivo


def test_lettura_riuscita_passa_la_decisione() -> None:
    chiamate: list[tuple[str, str]] = []

    def lettore_finto(repo: str, ramo: str, token: str | None = None):
        chiamate.append((repo, ramo))
        return quando(13, ORA_SERALE - 1, 30)

    esito, _ = fd.decidi_dal_repository("uamisjd/progetto", "main", quando(13, 14), None, lettore_finto)
    assert esito is False
    assert chiamate == [("uamisjd/progetto", "main")]


def test_output_una_riga_per_github_output(capsys) -> None:
    # il workflow legge stdout con `>> $GITHUB_OUTPUT`: una riga sola, nel formato chiave=valore
    codice = fd.main(["--repo", "", "--ramo", "main", "--now", "2026-10-13T04:00:00+00:00"])
    assert codice == 0
    catturato = capsys.readouterr()
    assert catturato.out.strip() in {"commit=true", "commit=false"}
    assert "\n" not in catturato.out.strip()


@pytest.mark.parametrize("ora_utc,atteso", [(4, False), (10, False), (14, False), (18, False), (21, True)])
def test_i_cinque_orari_del_cron(ora_utc: int, atteso: bool) -> None:
    """Simula la giornata di `daily` con la fotografia salvata la sera prima alle 21:30."""
    esito, _ = fd.decide(quando(13, ora_utc), quando(12, 21, 30))
    assert esito is atteso


def test_giornata_completa_una_sola_fotografia() -> None:
    """La giornata intera: cinque run, la fotografia si salva una volta sola (la sera).

    È l'invariante che conta per la crescita del repository: `docs/105` §2 stima così la
    riduzione (−80%). Se questo test cambia, cambia il conto dei megabyte.
    """
    ultima = quando(12, 21, 30)
    salvata: datetime | None = None
    for ora, minuto in [(4, 0), (10, 0), (14, 0), (18, 0), (21, 30)]:
        esito, _ = fd.decide(quando(13, ora, minuto), ultima)
        if esito:
            assert salvata is None, "la fotografia si salva una volta sola al giorno"
            salvata = quando(13, ora, minuto)
    assert salvata == quando(13, 21, 30)


def test_rete_di_sicurezza_non_si_attiva_se_il_run_serale_ha_salvato() -> None:
    # ieri sera 21:30 → oggi 21:30: le 24 ore esatte sono passate, ma la regola serale
    # basta da sola; il test fissa che non serve la rete di sicurezza
    esito, motivo = fd.decide(quando(13, 21), quando(12, 21), rete_sicurezza=timedelta(hours=48))
    assert esito is True
    assert "run serale" in motivo


def test_preferisce_gh_quando_esiste(monkeypatch) -> None:
    """In CI `gh` c'è e usa lo stesso token del workflow: è la strada primaria."""
    chiamate: list[str] = []
    monkeypatch.setattr(fd.shutil, "which", lambda nome: "/usr/bin/gh" if nome == "gh" else None)
    monkeypatch.setenv("GH_TOKEN", "finto")
    monkeypatch.setattr(fd, "_leggi_con_gh", lambda repo, ramo, per_page=1: chiamate.append("gh") or quando(13, 4))
    monkeypatch.setattr(fd, "_leggi_con_requests", lambda *a, **k: chiamate.append("requests"))
    esito = fd.ultima_fotografia("uamisjd/progetto", "main")
    assert esito == quando(13, 4)
    assert chiamate == ["gh"]


def test_senza_gh_usa_requests(monkeypatch) -> None:
    chiamate: list[str] = []
    monkeypatch.setattr(fd.shutil, "which", lambda nome: None)
    monkeypatch.setattr(fd, "_leggi_con_gh", lambda *a, **k: chiamate.append("gh"))
    monkeypatch.setattr(fd, "_leggi_con_requests", lambda *a, **k: chiamate.append("requests") or quando(13, 4))
    esito = fd.ultima_fotografia("uamisjd/progetto", "main")
    assert esito == quando(13, 4)
    assert chiamate == ["requests"]


def test_data_iso_con_z_viene_letta(monkeypatch) -> None:
    assert fd._interpreta("2026-10-13T21:34:12Z") == datetime(2026, 10, 13, 21, 34, 12, tzinfo=UTC)
    assert fd._interpreta("") is None
