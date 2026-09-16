"""Stima stabilizzata di una rata su campioni piccoli (empirical Bayes).

**Perché esiste** (docs/19 §1.10, docs/22 §5). Una rata per 90 su pochi minuti è rumore: un
minuto giocato con un tiro pubblica «90,00 tiri/90», e il portale la stampa in **8.705 celle su
54.957** (284 delle quali con un grezzo almeno triplo della stima). La correzione precedente
aveva due difetti misurati:

1. il peso era un numero fisso (**180′**) invece di essere misurato sulla distribuzione dei
   minuti dei pari — a settembre, con un minutaggio mediano di 360′, un peso tarato a mano
   vale 2-4 volte il dovuto;
2. la media verso cui contrarre era la costante di ruolo dell'**xG+xA** (0,02/0,12/0,28/0,42)
   applicata a *qualunque* statistica: il valore «stabilizzato» dei tiri era quindi la
   contrazione verso un numero che con i tiri non c'entra nulla.

**Come funziona.** Media dei pari e peso si **misurano dai dati del run**:

- la media dei pari è la rata aggregata del gruppo (somma dei conteggi / somma dei denominatori,
  cioè pesata sul tempo di gioco), calcolata sui pari con almeno ``SMALL_SAMPLE_MINUTES`` se ce
  ne sono abbastanza, altrimenti su quelli con almeno ``MIN_DEN_FOR_RATE`` (a inizio stagione
  nessuno ha 270′: il ripiego è dichiarato, non nascosto);
- il peso ``k`` è ``POOL_WEIGHT`` volte il denominatore **mediano** del gruppo: con
  ``POOL_WEIGHT = 0,25`` un giocatore con un quarto del minutaggio mediano pesa metà la propria
  rata e metà la media dei pari;
- ``k`` è espresso **nella stessa unità del denominatore** (minuti per le rate per 90, partite
  per quelle per partita) ed è questo l'errore di unità corretto qui: il prior non è «180
  minuti» per convenzione, è «un quarto del tempo di gioco mediano dei pari».

**Estensione alle quote** (percentuali: passaggi riusciti, duelli vinti). Vale la stessa logica, con
una differenza di **unità**: per una quota il campione non è il tempo di gioco ma il numero di
eventi, quindi ``den`` è il numero di tentativi/duelli del giocatore e ``k`` è misurato in eventi.
La selezione dei pari, invece, continua a usare i minuti: una quota su mezza partita non dice dove
sta la quota del gruppo, mentre la media dei pari si aggrega sugli eventi (somma dei successi su
somma delle occasioni). Il percentile di una quota segue la stima, non il grezzo: la pagina dichiara
«il percentile è calcolato sulla stima stabilizzata» e questo è vero anche per gli assi a quota.

``shrink_rate(num, den, pool_rate, k)`` restituisce la rata nella stessa unità di ``num/den``
(per minuto se ``num`` è un conteggio e ``den`` i minuti); i per-90 si ottengono con
``Pool.per90``. Le rate si pubblicano solo sopra ``MIN_DEN_FOR_RATE``: sotto quella soglia la
scheda mostra la **stima** (e lo dichiara), non un numero che nessuno dovrebbe leggere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

#: Sotto questo denominatore (minuti) il campione è piccolo: la scheda pubblica anche la stima.
SMALL_SAMPLE_MINUTES = 270.0
#: Sotto questo denominatore la rata grezza **non si pubblica**: si pubblica solo la stima.
MIN_DEN_FOR_RATE = 90.0
#: Peso del prior in frazione del denominatore mediano dei pari (vedi docstring del modulo).
POOL_WEIGHT = 0.25
#: Sotto questo numero di pari il gruppo non basta per una media: si ripiega sul gruppo più ampio.
MIN_POOL_PEERS = 8


@dataclass(frozen=True)
class Pool:
    """Media dei pari e peso della contrazione, misurati dal run (mai costanti nel codice)."""

    rate: float           # conteggi per unità di denominatore (per minuto, per le rate per 90)
    k: float              # peso, nella stessa unità del denominatore (minuti per i per-90)
    n: int                # quanti pari concorrono alla media
    den: float            # denominatore aggregato dei pari (es. minuti totali)
    soglia: float = SMALL_SAMPLE_MINUTES   # soglia usata per scegliere i pari che formano la media

    def shrink(self, num: float, den: float) -> float:
        """Rata stabilizzata di ``num/den`` verso ``self.rate``, peso ``self.k``."""
        return shrink_rate(num, den, self.rate, self.k)

    def per90(self, num: float, den: float) -> float:
        """Come :meth:`shrink`, ma in unità «per 90 minuti» (denominatore in minuti)."""
        return self.shrink(num, den) * 90.0

    def note(self, group: str, *, scale: float = 90.0, unit: str = "′") -> str:
        """Frase unica per tooltip e schede: media dei pari, peso e numerosità (niente numeri senza fonte)."""
        from .fmt import dec

        return (f"media dei pari ({group}) {dec(self.rate * scale)}/90 · "
                f"peso k={self.k:.0f}{unit} · n={self.n}")

    def note_pct(self, group: str, *, unit: str) -> str:
        """Come :meth:`note`, ma per una **quota** (percentuale): la media dei pari è già una percentuale.

        Il peso è in unità di *evento* (tentativi di passaggio, duelli), non di minuti: per una quota
        il denominatore che dice quanto pesa il campione è il numero di eventi, non il tempo di gioco.
        """
        from .fmt import pct_str

        return (f"media dei pari ({group}) {pct_str(self.rate, 1)} · "
                f"peso k={self.k:.0f} {unit} · n={self.n}")


def shrink_rate(num: float, den: float, pool_rate: float, k: float) -> float:
    """Contrazione di una rata ``num/den`` verso la media dei pari con peso ``k``.

    ``k`` è nella stessa unità di ``den`` e vale «quanto den della media dei pari pesa come
    tutto il campione del giocatore». Con ``k = 0`` (o denominatore nullo) la stima è la media
    dei pari: non c'è informazione su cui contrarre, e inventare una rata non è un'opzione.
    """
    den = float(den or 0.0)
    k = max(float(k), 0.0)
    if den <= 0 or k <= 0:
        return float(pool_rate)
    return (float(num) + k * float(pool_rate)) / (den + k)


def pool_of(num: Sequence[float] | pd.Series, den: Sequence[float] | pd.Series, *,
            filtro: Sequence[float] | pd.Series | None = None,
            weight: float = POOL_WEIGHT, min_den: float = MIN_DEN_FOR_RATE,
            min_peers: int = MIN_POOL_PEERS) -> Pool | None:
    """Misura il gruppo dei pari: ``None`` se i pari non bastano (il chiamante ripiega più in alto).

    ``num`` e ``den`` sono allineati e riferiti ai singoli pari; ``den`` è il denominatore **della
    rata** (i minuti per le rate per 90, gli eventi — tentativi, duelli — per le quote).

    ``filtro`` è il denominatore con cui si decide se un pari ha un campione utilizzabile e vale
    ``den`` quando non è dato. Per le quote il filtro sono i **minuti**: una quota costruita su
    mezza partita non dice dove sta il gruppo, mentre la media dei pari si aggrega sugli eventi
    (somma dei successi / somma delle occasioni), che è la stima pooled della quota di gruppo.

    ``k`` resta ``weight`` volte la **mediana del denominatore della rata** fra i pari utilizzabili,
    quindi è sempre nell'unità giusta per :func:`shrink_rate` (minuti con i minuti, eventi con gli
    eventi): la contrazione avviene nella scala in cui il campione è piccolo davvero.
    """
    n_s = pd.to_numeric(pd.Series(list(num)), errors="coerce").fillna(0.0)
    d_s = pd.to_numeric(pd.Series(list(den)), errors="coerce")
    f_s = d_s if filtro is None else pd.to_numeric(pd.Series(list(filtro)), errors="coerce")
    if len(n_s) != len(d_s) or len(f_s) != len(d_s):
        return None
    # un pari è utilizzabile se il suo *filtro* ha un campione (≥ min_den) e il denominatore della
    # rata esiste (per le quote: 0 tentativi → nessuna informazione, non una quota)
    ok = f_s.notna() & (f_s >= min_den) & (f_s > 0) & d_s.notna() & (d_s >= 0)
    if int(ok.sum()) < min_peers:
        return None
    # media dei pari preferita sui campioni pieni; se non bastano, sui campioni pubblicabili
    for soglia in (SMALL_SAMPLE_MINUTES, MIN_DEN_FOR_RATE):
        sel = ok & (f_s >= soglia)
        if int(sel.sum()) >= min_peers:
            break
    else:                                          # pragma: no cover — coperto dal ramo sopra
        return None
    den_tot = float(d_s[sel].sum())
    if den_tot <= 0:
        return None
    mediana = float(d_s[ok].median())
    return Pool(rate=float(n_s[sel].sum()) / den_tot,
                k=max(float(weight) * mediana, 0.0),
                n=int(sel.sum()), den=den_tot, soglia=float(soglia))


def player_pools(totals: pd.DataFrame, groups: pd.DataFrame, keys: Mapping[str, Sequence[str]],
                 *, dens: Mapping[str, Sequence[str]] | None = None,
                 minutes_col: str = "minutes", league_col: str = "league_id",
                 role_col: str = "position", weight: float = POOL_WEIGHT,
                 min_den: float = MIN_DEN_FOR_RATE, min_peers: int = MIN_POOL_PEERS
                 ) -> dict[tuple[int | None, int | None], dict[str, Pool]]:
    """Medie dei pari per (lega, ruolo), più i ripieghi (lega, tutti i ruoli) e (tutte, tutti).

    ``totals`` è indicizzato per giocatore e contiene i **conteggi** per chiave; ``groups`` ha
    per ogni giocatore lega, ruolo e denominatore (minuti). ``keys`` mappa l'id della statistica
    alle chiavi di ``totals`` che la compongono (una lista: l'xG+xA ne somma due). I gruppi con
    meno di ``min_peers`` pari non entrano nel dizionario: chi cerca ripiega.

    ``dens`` (opzionale) mappa l'id della statistica alle colonne di ``totals`` che formano il
    **denominatore della rata** quando non sono i minuti — per le percentuali gli eventi
    (tentativi di passaggio, duelli totali). La selezione dei pari resta sui minuti: una quota
    su mezza partita non dice dove sta la quota del gruppo (docs/23 §2).
    """
    out: dict[tuple[int | None, int | None], dict[str, Pool]] = {}
    if totals.empty or groups.empty:
        return out
    # il denominatore sta nei totali (una colonna) o nei gruppi: si accetta in entrambi i posti,
    # perché i chiamanti costruiscono le due tabelle in modi diversi (schede giocatore e scheda partita)
    colonna_den = None
    if minutes_col in totals.columns:
        colonna_den = totals[minutes_col]
    elif minutes_col in groups.columns:
        colonna_den = groups[minutes_col]
    if colonna_den is None:
        return out
    den = pd.to_numeric(colonna_den, errors="coerce").fillna(0.0)
    lega = groups.get(league_col)
    ruolo = groups.get(role_col)
    if lega is None or ruolo is None:
        return out

    def _livello(ll: int | None, rr: int | None) -> pd.DataFrame:
        m = pd.Series(True, index=groups.index)
        if ll is not None:
            m &= lega.fillna(-1).astype(int) == ll
        if rr is not None:
            m &= ruolo.fillna(-1).astype(int) == rr
        return totals[m.reindex(totals.index, fill_value=False)]

    def _somma_colonne(sub: pd.DataFrame, colonne: Sequence[str]) -> pd.Series:
        tot = pd.Series(0.0, index=sub.index)
        for c in colonne:
            if c in sub.columns:
                tot = tot + pd.to_numeric(sub[c], errors="coerce").fillna(0.0)
        return tot

    leghe = sorted({int(v) for v in lega.fillna(-1).tolist() if int(v) >= 0})
    ruoli = sorted({int(v) for v in ruolo.fillna(-1).tolist() if int(v) >= 0})
    combinazioni: list[tuple[int | None, int | None]] = (
        [(lg, rl) for lg in leghe for rl in ruoli]
        + [(lg, None) for lg in leghe]           # ripiego: tutti i ruoli della lega
        + [(None, None)]                         # ripiego finale: tutte le leghe
    )
    for lid, rid in combinazioni:
        sub = _livello(lid, rid)
        if sub.empty:
            continue
        sub_den = den.reindex(sub.index).fillna(0.0)
        pools: dict[str, Pool] = {}
        for sid, componenti in keys.items():
            num = _somma_colonne(sub, componenti)
            # denominatore della rata: i minuti, oppure gli eventi dichiarati dal chiamante
            den_rata = sub_den if not dens or sid not in dens else _somma_colonne(sub, dens[sid])
            p = pool_of(num, den_rata, filtro=sub_den, weight=weight, min_den=min_den,
                        min_peers=min_peers)
            if p is not None:
                pools[sid] = p
        if pools:
            out[(lid, rid)] = pools
    return out


#: Nome leggibile dei ruoli nelle etichette dei gruppi («attaccanti di Serie A»).
ROLE_PLURALS = {0: "portieri", 1: "difensori", 2: "centrocampisti", 3: "attaccanti"}


def league_names() -> dict[int, str]:
    """Id FotMob della lega → nome italiano (dalla configurazione, nessun nome scritto nel codice)."""
    from ..config import load_leagues_config

    return {int(l["fotmob_id"]): str(l["name"])
            for l in load_leagues_config().get("leagues", [])
            if l.get("fotmob_id") is not None}


def group_label(league: int | None, role: int | None) -> str:
    """«attaccanti di Serie A», «tutti i ruoli di Serie A», «tutte le leghe»."""
    ruolo = ROLE_PLURALS.get(role, "tutti i ruoli")
    if league is None:
        return "tutte le leghe"
    nome = league_names().get(int(league))
    return f"{ruolo} di {nome}" if nome else ruolo


def lookup(pools: dict[tuple[int | None, int | None], dict[str, Pool]],
           league: int | None, role: int | None, stat: str
           ) -> tuple[Pool, tuple[int | None, int | None]] | None:
    """Il gruppo più specifico che ha una media per ``stat``: (lega, ruolo) → (lega, ·) → (·, ·).

    Restituisce anche la chiave del gruppo trovato: serve a dire **quale** gruppo è stato usato
    («attaccanti di Serie A» invece di «i pari»), perché una media senza il gruppo che l'ha
    prodotta non è verificabile.
    """
    for chiave in ((league, role), (league, None), (None, None)):
        p = pools.get(chiave, {}).get(stat)
        if p is not None:
            return p, chiave
    return None
