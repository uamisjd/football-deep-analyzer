"""Card «laboratorio» della scheda partita: idee **misurate e non usate** nella previsione.

Perché esiste questo modulo: i tre ``*_tilt`` di :mod:`fda.models.predict`
(``market_value_tilt``, ``absences_tilt``, ``rest_tilt``) sono **candidati di laboratorio**
— dichiarati, commentati onestamente, mai cablati in ``predict_matches()``
(docs/71 §4, decisione A/B/C = **C** del 2026-10-10). Restavano però invisibili: nessuna
pagina diceva che esistono, cosa farebbero e quanto hanno misurato. La revisione
`docs/73` (§5, otto condizioni) chiede una casa per queste misure e questo modulo la
realizza:

1. il card sta **sotto** la previsione salvata (dopo «Come nasce questa probabilità»),
   mai sopra: è una finestra sul laboratorio, non un secondo pronostico;
2. l'etichetta dice che le idee sono **misurate e non applicate**;
3. per ogni idea il card mostra **il what-if su questa partita** (λ inclinata e 1X2
   ricalcolata con la stessa griglia Dixon-Coles dell'audit: ``dc_grid.tau_grid``),
   **l'effetto misurato in aggregato** con campione e intervallo di confidenza, il
   **verdetto** e — dove l'input manca — «dato non disponibile» invece di un numero;
4. **legge** la previsione salvata e non la scrive: λ, 1X2 e ``predictions.parquet``
   restano identici (test ``test_laboratorio_non_tocca_la_previsione``).

Le formule applicate dal card sono quelle di ``predict.py`` (una sola implementazione,
usata dalla pagina); ``scripts/verify_site.py`` le ricontrolla con l'invariante **[46]**,
che le riscrive per conto proprio **senza importarle** — lo stesso schema degli oracoli di
[44] e [45].

Le misure d'archivio accanto a ogni idea **non sono ricalcolate a ogni build**: richiedono
il backtest completo e sono i numeri registrati in `docs/69` §1 e `docs/71` §3, citati con
campione e provenienza. Se un candidato venisse promosso cambierebbero (MODEL_VERSION
nuova, calibrazione ristimata), e con loro queste costanti.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..models.dc_grid import GRID_SIZE, tau_grid
from ..models.predict import (
    ABSENCES_K,
    MARKET_VALUE_K,
    absences_tilt,
    market_value_tilt,
    rest_tilt,
)

#: sotto questo spostamento (gol attesi per squadra) l'idea non cambia nulla di visibile:
#: le λ sono pubblicate con due decimali, quindi 0,005 è il primo scarto che si vede.
SOGLIA_SPOSTA = 0.005

#: Due k per idea, e la differenza conta più del numero (revisione del 2026-10-10, `docs/74` §10):
#: il what-if va calcolato con il k che la **misura** sostiene — non con la costante che il
#: codice si porta dietro e che la misura non distingue dallo zero. Mostrare solo il secondo
#: darebbe al lettore uno spostamento ~4 volte più grande di quello che entrerebbe davvero.
#: * mercato: k = 0,03 è l'unico con un intervallo di confidenza che esclude lo zero
#:   (`docs/69` §1); la griglia preregistrata è {0; 0,03; 0,06; 0,09} (`docs/71` §3).
#: * assenze: nessun k è sostenuto (98 gare, sotto i 300 del protocollo), quindi si mostra il
#:   **massimo della griglia preregistrata** (0,20) come tetto di ciò che il protocollo
#:   prenderebbe in considerazione; la griglia è {0; 0,1; 0,2}.
#: Il k dichiarato nel codice (0,12 e 0,30) resta pubblicato accanto, per confronto: non è un
#: candidato della griglia, ed è per questo che non è il numero della riga.
MERCATO_K_SOSTENUTO: float = 0.03
ASSENZE_K_PROTOCOLLO: float = 0.20

#: formato delle λ pubblicate (decimali): vale per il card e per chi lo ricalcola ([46]).
ND_LAMBDA = 2


@dataclass(frozen=True)
class Idea:
    """Un'idea del laboratorio: cosa fa, quanto ha misurato, che cosa se n'è fatto."""

    key: str
    nome: str
    icona: str
    unita: str
    formula: str          # ⓘ dell'idea: la regola applicata, con le sue costanti
    campione: str         # su quante gare è misurata (e che fine ha fatto il campione)
    misura: str           # effetto misurato in aggregato, con intervallo di confidenza
    fonte: str            # documento che registra la misura
    verdetto: str         # una riga: che cosa se n'è fatto
    verdetto_help: str    # ⓘ del verdetto: la ragione per esteso
    # «k» dell'idea, se ne ha uno: quello con cui il card calcola il what-if (sostenuto dalla
    # misura, o il massimo previsto dal protocollo) e quello dichiarato nel codice, pubblicato
    # accanto per confronto. `None` per le idee senza k (il riposo: fattori fissi).
    k_usato: float | None = None
    k_usato_label: str = ""
    k_dichiarato: float | None = None
    k_dichiarato_label: str = ""
    nota_k: str = ""      # ⓘ della colonna dello spostamento: perché questo k e non l'altro


#: Le tre idee, nell'ordine in cui escono in pagina: prima quella con il campione più
#: grande (valore, 341 gare), poi le due che la misura non sostiene.
IDEE: tuple[Idea, ...] = (
    Idea(
        key="mercato",
        nome="Valore di mercato dei titolari",
        icona="💰",
        unita="M€",
        formula=("Il rapporto fra il valore dei titolari (casa/trasferta), limitato fra 0,2 e 5, "
                 "inclina le λ di rapporto^k; il totale dei gol attesi resta quello del modello "
                 "— l'idea sposta il peso fra le due squadre, non i gol della partita."),
        campione="341 gare dell'archivio (5,8%): è l'unica idea con un campione testabile",
        misura=("solo k = 0,03 ha un intervallo che esclude lo zero (Δlog-loss −0,004785, IC95 "
                "[−0,008769; −0,000581]); k = 0,12 — la costante nel codice — è indistinguibile "
                "dallo zero (−0,009475, IC95 [−0,025091; +0,007122])"),
        fonte="docs/69 §1 · docs/71 §3",
        verdetto="non usata: la misura non sostiene questo k",
        verdetto_help=("Il guadagno misurato è su k = 0,03, un quarto della costante che il codice "
                       "si porta dietro, e con una correlazione di 0,883 fra valore e modello: "
                       "quasi tutto ciò che il valore sa, il modello lo sa già. Promuoverla "
                       "richiederebbe una MODEL_VERSION nuova e una calibrazione ristimata sul "
                       "backtest con il fattore dentro."),
        k_usato=MERCATO_K_SOSTENUTO,
        k_usato_label="k = 0,03 — l'unico con IC fuori dallo zero",
        k_dichiarato=MARKET_VALUE_K,
        k_dichiarato_label="k = 0,12 — la costante nel codice",
        nota_k=("Il what-if è calcolato con k = 0,03, l'unico valore dell'intervallo con un "
                "intervallo di confidenza che esclude lo zero. Sotto, per confronto, lo stesso "
                "calcolo con k = 0,12 — la costante oggi nel codice — che la misura NON "
                "distingue dallo zero: sposta circa quattro volte tanto, e non è una stima di "
                "ciò che entrerebbe in produzione."),
    ),
    Idea(
        key="assenze",
        nome="Indisponibili pesati",
        icona="🏥",
        unita="xG+xA/90",
        formula=("Ogni λ è moltiplicata per 1 − k × (xG+xA/90 persi) / 2,0, con il fattore "
                 "limitato fra 0,70 e 1,00; il totale dei gol attesi resta quello del modello. "
                 "L'input è la stessa somma pubblicata nella card «Indisponibili», dove la riga "
                 "esce (87 schede su 89 in questo build)."),
        campione="98 gare (1,7% dell'archivio); campione instabile: 137 → 98 in tre settimane",
        misura=("sotto la soglia minima del protocollo preregistrato (≥ 300 gare e ≥ 5 leghe su 7): "
                "esito «non testabile», non «neutro»"),
        fonte="docs/71 §2-§3 · docs/73 §4",
        verdetto="non testabile: il campione non basta",
        verdetto_help=("Il campione si è ridotto da 137 a 98 gare senza che cambiasse il codice: "
                       "tra i run del 21–24 settembre 110 partite sono state riscaricate e le "
                       "tabelle per-partita non portavano più la lista pre-partita degli "
                       "indisponibili. Con un campione che si muove da solo, nessuna misura "
                       "regge: il protocollo preregistrato chiede almeno 300 gare."),
        k_usato=ASSENZE_K_PROTOCOLLO,
        k_usato_label="k = 0,20 — il massimo della griglia preregistrata",
        k_dichiarato=ABSENCES_K,
        k_dichiarato_label="k = 0,30 — la costante nel codice",
        nota_k=("Nessun k è sostenuto: con 98 gare l'esito del protocollo è «non testabile». Il "
                "what-if usa k = 0,20, il valore più alto della griglia preregistrata "
                "({0; 0,1; 0,2}): è il tetto di ciò che il protocollo prenderebbe in esame, non "
                "un k misurato. Sotto, per confronto, la costante k = 0,30 che il codice si porta "
                "dietro e che è fuori dalla griglia."),
    ),
    Idea(
        key="riposo",
        nome="Giorni di riposo",
        icona="🛌",
        unita="giorni",
        formula=("Fattore per squadra: ≤ 2 giorni → 0,95; ≤ 4 giorni → 0,98; ≥ 7 giorni → 1,02; "
                 "negli altri casi 1,00. Il totale dei gol attesi resta quello del modello, quindi "
                 "una sosta uguale per tutti non sposta nulla."),
        campione="1.591 λ modificate su 5.895 previsioni del backtest",
        misura=("ΔRPS +0,0000787, IC95 [+0,0000154; +0,000141]: peggiora. Misurato due volte, "
                "a tre settimane di distanza, con lo stesso segno"),
        fonte="docs/69 §1 · docs/71 §3",
        verdetto="non usata: la misura è contraria",
        verdetto_help=("È l'unica idea con una misura ripetuta e stabile, e dice che applicarla "
                       "peggiora la previsione (RPS più alto = previsione peggiore). L'intervallo "
                       "di confidenza esclude lo zero: non è «non si vede», è «fa danno». "
                       "Per questo non entra nella ricetta, pur essendo la più facile da calcolare."),
    ),
)


def _p1x2(lh: float, la: float, rho: float) -> tuple[float, float, float]:
    """1X2 dalla griglia Dixon-Coles condivisa (``dc_grid.tau_grid``), come l'audit."""
    g = tau_grid(lh, la, rho, size=GRID_SIZE)
    i, j = np.indices(g.shape)
    return (float(g[i > j].sum()), float(g[i == j].sum()), float(g[i < j].sum()))


def _float(v: Any) -> float | None:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _applica(key: str, lh: float, la: float, ih: float | None, ia: float | None,
             k: float | None, disponibile: bool) -> tuple[float, float]:
    """Applica la formula dell'idea alle λ: con ``k`` se l'idea ne ha uno, senza altrimenti.

    Senza input non si applica nulla: le λ restano quelle pubblicate, e in pagina la riga lo
    dichiara («dato non disponibile») invece di simulare uno zero.
    """
    if not disponibile:
        return lh, la
    if key == "mercato":
        return market_value_tilt(lh, la, ih, ia, k=MARKET_VALUE_K if k is None else k)[:2]
    if key == "assenze":
        return absences_tilt(lh, la, ih, ia, k=ABSENCES_K if k is None else k)[:2]
    return rest_tilt(lh, la, ih, ia)[:2]


def laboratorio(
    prediction: dict[str, Any] | None,
    *,
    rest_home: int | None,
    rest_away: int | None,
    valore_home: float | None,
    valore_away: float | None,
    perso_home: float | None,
    perso_away: float | None,
) -> dict[str, Any] | None:
    """Il what-if delle tre idee su **questa** partita, a partire dalla previsione salvata.

    ``rest_*`` sono i giorni dall'ultima gara (calendario campionato + coppe), ``valore_*``
    il valore dei titolari pubblicato dalla fonte, ``perso_*`` gli xG+xA/90 che mancano per
    gli indisponibili (``None`` = la fonte non pubblica la distinta, non «zero assenti»).

    Ritorna ``None`` se la partita non ha una previsione salvata: il card legge la
    previsione, quindi senza previsione non esiste. Nessun valore scritto qui finisce in
    ``predictions.parquet``.
    """
    if not prediction:
        return None
    lh = _float(prediction.get("lambda_home"))
    la = _float(prediction.get("lambda_away"))
    if lh is None or la is None or lh <= 0 or la <= 0:
        return None
    rho = _float(prediction.get("dc_rho")) or 0.0
    base = _p1x2(lh, la, rho)

    righe: list[dict[str, Any]] = []
    for idea in IDEE:
        # ---- l'input dell'idea su questa partita (None = dato non disponibile)
        if idea.key == "mercato":
            # il tilt è un rapporto: senza **entrambe** le squadre non si calcola, e la riga
            # esce come «dato non disponibile» (NED1 e POR1: 3/7 e 4/9, docs/73 §2).
            ih, ia = _float(valore_home), _float(valore_away)
            if ih is not None and ih <= 0:
                ih = None
            if ia is not None and ia <= 0:
                ia = None
            if ih is None or ia is None:
                ih = ia = None
            else:
                ih, ia = round(ih), round(ia)
            motivo = "la fonte non pubblica il valore dei titolari di entrambe le squadre"
        elif idea.key == "assenze":
            # arrotondati a due decimali: sono la somma pubblicata riga per riga (docs/64 §8)
            ih, ia = _float(perso_home), _float(perso_away)
            ih = None if ih is None else round(ih, 2)
            ia = None if ia is None else round(ia, 2)
            motivo = "distinta non pubblicata dalla fonte: nessun impatto misurabile"
        else:
            ih, ia = _float(rest_home), _float(rest_away)
            ih = None if ih is None else round(ih)
            ia = None if ia is None else round(ia)
            motivo = "nessuna gara precedente in calendario per entrambe"
        disponibile = ih is not None or ia is not None

        # ---- what-if: le λ che l'idea produrrebbe, con le formule dichiarate in predict.py.
        # Due passate quando l'idea ha un k: quella con il k **sostenuto** (o il massimo della
        # griglia preregistrata) è il numero della riga; quella con la costante del codice è il
        # confronto pubblicato sotto (revisione del 2026-10-10, `docs/74` §10).
        lh2, la2 = (float(v) for v in _applica(idea.key, lh, la, ih, ia, idea.k_usato, disponibile))
        sposta = max(abs(lh2 - lh), abs(la2 - la)) > SOGLIA_SPOSTA
        p2 = _p1x2(lh2, la2, rho) if disponibile else base
        d_pp = max(abs(p2[k] - base[k]) for k in range(3)) * 100.0
        # confronto con la costante dichiarata nel codice (solo per le idee con un k)
        lh3 = la3 = None
        p3: tuple[float, float, float] | None = None
        d_pp3 = None
        if disponibile and idea.k_dichiarato is not None:
            lh3, la3 = (float(v) for v in
                        _applica(idea.key, lh, la, ih, ia, idea.k_dichiarato, disponibile))
            p3 = _p1x2(lh3, la3, rho)
            d_pp3 = max(abs(p3[k] - base[k]) for k in range(3)) * 100.0

        righe.append({
            "key": idea.key,
            "nome": idea.nome,
            "icona": idea.icona,
            "unita": idea.unita,
            "formula": idea.formula,
            "campione": idea.campione,
            "misura": idea.misura,
            "fonte": idea.fonte,
            "verdetto": idea.verdetto,
            "verdetto_help": idea.verdetto_help,
            "k_usato": idea.k_usato,
            "k_usato_label": idea.k_usato_label,
            "k_dichiarato": idea.k_dichiarato,
            "k_dichiarato_label": idea.k_dichiarato_label,
            "nota_k": idea.nota_k,
            # what-if con la costante del codice, pubblicato sotto per confronto
            "lh_decl": None if lh3 is None else round(lh3, ND_LAMBDA),
            "la_decl": None if la3 is None else round(la3, ND_LAMBDA),
            "p_home_decl": None if p3 is None else p3[0],
            "p_draw_decl": None if p3 is None else p3[1],
            "p_away_decl": None if p3 is None else p3[2],
            "d_pp_decl": d_pp3,
            # input: «None» resta «None» anche in pagina — «dato non disponibile», non 0
            "in_home": ih,
            "in_away": ia,
            "disponibile": disponibile,
            "motivo": None if disponibile else motivo,
            "lh": round(lh2, ND_LAMBDA),
            "la": round(la2, ND_LAMBDA),
            "p_home": p2[0], "p_draw": p2[1], "p_away": p2[2],
            "sposta": sposta,
            "d_lambda": max(abs(lh2 - lh), abs(la2 - la)),
            "d_pp": d_pp,
        })

    return {
        "lh": round(lh, ND_LAMBDA),
        "la": round(la, ND_LAMBDA),
        "p_home": base[0], "p_draw": base[1], "p_away": base[2],
        "righe": righe,
        "n_spostano": sum(1 for r in righe if r["sposta"]),
        "n_idee": len(righe),
    }
