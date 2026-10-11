"""Audit 360° della card «Panchina e posta in gioco» (revisione del 2026-10-11, `docs/78`).

Misura su **tutte** le schede pre-partita di ``site/partite`` che cosa la card propone e
come: copertura di ogni elemento (profilo allenatore, permanenza, rendimento, precedenti
mirati, distanze di classifica, posizione virtuale a tre esiti, età media), i silenzi non
dichiarati, la profondità d'archivio che rende (o non rende) pubblicabili i precedenti, e
la coerenza fra i numeri stampati e i Parquet che li generano — **senza** passare da
``bench_deep`` per leggere o per ricalcolare: l'HTML si legge com'è e i valori si
ricostruiscono con strade diverse da quelle del generatore.

Uso: ``.venv/bin/python scripts/audit_panchina.py`` (dopo ``fda build``).
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from html import unescape
from pathlib import Path

import pandas as pd

from fda.models.season_sim import mc_percent_str

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "partite"
DATA = ROOT / "data" / "processed"

CARD = re.compile(r'<div class="card" id="panchina">(.*?)(?=<div class="card"|<footer)', re.DOTALL)
ROW = re.compile(r'<th scope="row">(Allenatore|Posta in gioco|Età media titolari)</th>(.*?)(?=</tr>)',
                 re.DOTALL)
TD = re.compile(r'<td>(.*?)</td>', re.DOTALL)

ETICHETTE = ("corsa al titolo", "corsa alla Champions", "lotta salvezza",
             "zona salvezza non lontana")
PROIEZIONE = re.compile(r"proiezione: ([\d,]+)º posto in media")


def testo(html: str) -> str:
    """Testo della cella: via i tag, entità risolte, spazi normalizzati.

    Prima i tag, poi le entità: al contrario «&lt;1» diventerebbe «<1» e la finta
    parentesi verrebbe mangiata dal tag successivo, cancellando il valore (docs/78 §12).
    """
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def posizione_virtuale(tab: pd.DataFrame, tid: int, opp_id: int, pts: int, gd: int,
                       delta_mio: int, delta_avv: int) -> int:
    """Posizione virtuale con questo risultato: i punti vanno a **entrambe** le squadre."""
    mio = pts + delta_mio
    sopra = 0
    for w in tab.itertuples(index=False):
        rid = int(w.team_id)
        if rid == tid:
            continue
        punti = int(w.points) + (delta_avv if rid == opp_id else 0)
        if punti > mio or (punti == mio and int(w.goal_diff or 0) > gd):
            sopra += 1
    return sopra + 1


def main() -> int:
    """Censimento e ricalcoli; stampa solo riepiloghi."""
    if not SITE.exists():
        print("nessuna site/partite: esegui prima `fda build`")
        return 1
    from fda.config import leagues
    from fda.teams import canonical as canon
    fx = pd.read_parquet(DATA / "fixtures.parquet")
    lu = pd.read_parquet(DATA / "lineup.parquet")
    st = pd.read_parquet(DATA / "fotmob_standings.parquet")
    sim = pd.read_parquet(DATA / "season_sim.parquet")
    mi = pd.read_parquet(DATA / "match_info.parquet")
    chiave = {lg.fotmob_id: lg.key for lg in leagues()}
    posti = {lg.key: lg.ucl_spots for lg in leagues()}
    fx["ko"] = pd.to_datetime(fx.utc_kickoff, utc=True, errors="coerce")
    fx["home_goals"] = pd.to_numeric(fx.home_goals, errors="coerce")
    fx["away_goals"] = pd.to_numeric(fx.away_goals, errors="coerce")
    fxr = fx.set_index("match_id")
    fx["lg"] = fx.league_id.map(chiave)
    ko = fx.drop_duplicates("match_id").set_index("match_id")["ko"]
    co = lu[(lu.role == "coach") & (lu.match_id.isin(ko.index))].copy()
    co["ko"] = pd.to_datetime(co.match_id.map(ko), utc=True)
    fin = fx[fx.status == "finished"].copy()

    agg: Counter[str] = Counter()
    silenzi: dict[str, list[str]] = {"ppg": [], "eta": [], "table": [], "stakes": []}
    errori: dict[str, list[str]] = {"tenure": [], "ppg": [], "table": [], "virtuale": [],
                                    "etichetta": [], "eta": [], "nome_coach": [], "nazione": [],
                                    "precedenti": [], "incroci": [], "gol": [], "stima": [],
                                    "tooltip": []}
    precedenti: list[tuple[str, int, int]] = []
    etichette: Counter[str] = Counter()
    posizioni: dict[str, list[int]] = {}

    for pg in sorted(SITE.glob("*.html")):
        html = pg.read_text(encoding="utf-8")
        pre = "Analisi pre-partita" in html
        agg["pagine_totali"] += 1
        agg["pagine_pre"] += int(pre)
        m = CARD.search(html)
        if not m:
            agg["card_assente"] += 1
            continue
        agg["card_presente"] += 1
        mid = int(pg.stem)
        fr = fx[fx.match_id == mid]
        if fr.empty:
            agg["match_non_in_calendario"] += 1
            continue
        fr = fr.iloc[0]
        kickoff = pd.Timestamp(fr.utc_kickoff)
        celle: dict[str, list[str]] = {}
        grezze: dict[str, list[str]] = {}
        if str(fr.status) == "finished":
            agg["pagine_pre_con_calendario_finito"] += 1   # docs/78 §8: deve restare 0
        for nome, corpo in ROW.findall(m.group(1)):
            tds = TD.findall(corpo)
            agg[f"riga::{nome}"] += 1
            if len(tds) != 2:
                agg[f"celle_male::{nome}"] += 1
            celle[nome] = [testo(t) for t in tds]
            grezze[nome] = tds
        cellulare = celle.get("Allenatore", ["", ""])
        if len(cellulare) != 2:
            continue
        cell_st = celle.get("Posta in gioco", ["", ""])
        st_raw = grezze.get("Posta in gioco", ["", ""])
        cell_eta = celle.get("Età media titolari", ["", ""])

        for lato, (tid, tname, oid, oname) in enumerate((
                (int(fr.home_id), str(fr.home_name), int(fr.away_id), str(fr.away_name)),
                (int(fr.away_id), str(fr.away_name), int(fr.home_id), str(fr.home_name)))):
            c_co, c_st, c_eta = cellulare[lato], cell_st[lato], cell_eta[lato]
            agg["celle_squadra"] += 1
            # trasparenza (`docs/78` §12): il tooltip spiega i numeri, la loro precisione e
            # le soglie delle etichette; ogni cella con la riga dei numeri deve averlo
            if "titolo " in c_st:      # la riga dei numeri c'è: il tooltip deve esserci
                if "errore standard fino a 0,5 punti percentuali" in st_raw[lato]:
                    agg["tooltip_posta_in_gioco"] += 1
                else:
                    errori["tooltip"].append(f"{pg.stem}|{tname}| tooltip assente")

            # ---- allenatore: permanenza e rendimento, ricalcolati dal calendario ----
            ct = co[(co.team_id == tid) & (co.ko <= kickoff)].sort_values("ko", kind="stable")
            if ct.empty:
                agg["coach_assente"] += 1
                continue
            ultimo = ct.iloc[-1]
            agg["coach_nome"] += int(str(ultimo.player_name) in c_co)
            if str(ultimo.player_name) not in c_co:
                errori["nome_coach"].append(f"{pg.stem}|{tname}| {ultimo.player_name}")
            agg["coach_eta"] += int(bool(re.search(r"· \d+ anni", c_co)))
            agg["coach_nazione"] += int(bool(re.search(r"anni · [A-ZÀ-Ü][a-zà-ü]", c_co)))
            if re.search(r"anni · [A-Z]{3}\b", c_co):     # codice ISO grezzo = mappa bucata
                errori["nazione"].append(f"{pg.stem}|{tname}| {c_co[:60]}")
            streak, prev = 0, None
            for pid, nm in zip(ct.player_id.iloc[::-1], ct.player_name.iloc[::-1]):
                if pid == ultimo.player_id:
                    streak += 1
                else:
                    prev = str(nm)
                    break
            dal = None
            if prev:
                prec = ct[ct.player_id != ultimo.player_id]
                if not prec.empty:
                    dal = prec.ko.max().strftime("%d/%m")
            else:
                same = ct[ct.player_id == ultimo.player_id]
                if not same.empty:
                    dal = same.ko.min().strftime("%d/%m")
            atteso_ten = ((f"panchina nuova: {streak}ª gara dal subentro a {prev}"
                           + (f" (dopo la gara del {dal})" if dal else ""))
                          if prev else
                          (f"panchina invariata da {streak} "
                           f"{'gara' if streak == 1 else 'gare'} nel nostro archivio"
                           + (f" (dal {dal})" if dal else "")))
            agg["tenure"] += int(atteso_ten in c_co)
            agg["subentri"] += int(prev is not None)
            if atteso_ten not in c_co:
                errori["tenure"].append(f"{pg.stem}|{tname}| atteso «{atteso_ten}»")
            fl = fin[((fin.home_id == tid) | (fin.away_id == tid))
                     & (pd.to_datetime(fin.utc_kickoff, utc=True) < kickoff)]
            cur_id = ultimo.player_id
            mine = fl[fl.match_id.isin(set(ct.loc[(ct.player_id == cur_id)
                                                  & (ct.ko < kickoff), "match_id"]))]
            if mine.empty:
                atteso_ppg = "rendimento: nessuna gara finita con lui in panchina"
                agg["ppg_dichiarato_assente"] += int(atteso_ppg in c_co)
                if atteso_ppg not in c_co:
                    silenzi["ppg"].append(f"{pg.stem}|{tname}")
            else:
                punti = sum(3 if ((r.home_id == tid and r.home_goals > r.away_goals)
                                  or (r.away_id == tid and r.away_goals > r.home_goals))
                            else 1 if r.home_goals == r.away_goals else 0
                            for r in mine.itertuples(index=False))
                atteso_ppg = (f"rendimento: {punti / len(mine):.1f}".replace(".", ",")
                              + f" punti/gara su {len(mine)} "
                              + ("gara finita" if len(mine) == 1 else "gare finite"))
                agg["ppg"] += int(atteso_ppg in c_co)
                if atteso_ppg not in c_co:
                    errori["ppg"].append(f"{pg.stem}|{tname}| atteso «{atteso_ppg}»")
                gf_a = sum(int(r.home_goals) if int(r.home_id) == tid else int(r.away_goals)
                           for r in mine.itertuples(index=False))
                ga_a = sum(int(r.away_goals) if int(r.home_id) == tid else int(r.home_goals)
                           for r in mine.itertuples(index=False))
                atteso_gol = (f"con lui {gf_a / len(mine):.1f}".replace(".", ",")
                              + " gol fatti e "
                              + f"{ga_a / len(mine):.1f}".replace(".", ",")
                              + " subiti a gara")
                agg["gol_a_gara"] += int(atteso_gol in c_co)
                if atteso_gol not in c_co:
                    errori["gol"].append(f"{pg.stem}|{tname}| atteso «{atteso_gol}»")
            # bilancio dell'ALLENATORE con l'avversaria (sue gare in panchina, qualunque
            # club, prima di questa) e incroci in panchina — ricalcolati qui (docs/78 §10).
            # Il bilancio fra i due club non deve comparire nella cella: sta in «Precedenti».
            if f"bilancio con {oname} nel nostro archivio" in c_co \
                    or "un solo precedente in archivio con" in c_co:
                agg["cella_con_bilancio_club"] += 1
            sue = co[co.player_id == cur_id]
            n_b = w_b = d_b = l_b = 0
            for r in sue.itertuples(index=False):
                if r.match_id not in fxr.index:
                    continue
                g = fxr.loc[r.match_id]
                if (str(g.status) != "finished" or pd.isna(g.home_goals)
                        or pd.isna(g.away_goals) or pd.Timestamp(g.ko) >= kickoff):
                    continue
                casa = int(r.team_id) == int(g.home_id)
                if (int(g.away_id) if casa else int(g.home_id)) != oid:
                    continue
                gf, ga = ((g.home_goals, g.away_goals) if casa else (g.away_goals, g.home_goals))
                n_b += 1
                if gf > ga:
                    w_b += 1
                elif gf == ga:
                    d_b += 1
                else:
                    l_b += 1
            if n_b:
                atteso_all = (f"da allenatore contro {oname}: 1 gara nel nostro archivio "
                              f"({w_b}V {d_b}N {l_b}P)" if n_b == 1 else
                              f"da allenatore contro {oname}: {n_b} gare nel nostro archivio "
                              f"({w_b}V {d_b}N {l_b}P)")
                agg["bilancio_allenatore_pubblicato"] += int(atteso_all in c_co)
                if atteso_all not in c_co:
                    errori["precedenti"].append(f"{pg.stem}|{tname}| atteso «{atteso_all}»")
            else:
                agg["bilancio_allenatore_assente"] += 1
                if f"da allenatore contro {oname}" in c_co:
                    errori["precedenti"].append(f"{pg.stem}|{tname}| bilancio senza dati")
            oc = co[(co.team_id == oid) & (co.ko <= kickoff)]
            oid_coach = None if oc.empty else oc.iloc[-1].player_id
            # incroci = gare in cui i due allenatori si sono trovati su panchine opposte,
            # qualsiasi club, prima di questa partita (`docs/78` §7)
            comune = 0
            if oid_coach is not None and not pd.isna(oid_coach):
                lc19 = co[co.ko < kickoff]
                miei19 = lc19[lc19.player_id == cur_id]
                suoi19 = lc19[lc19.player_id == oid_coach]
                for m19 in set(miei19["match_id"]) & set(suoi19["match_id"]):
                    t1 = set(miei19.loc[miei19.match_id == m19, "team_id"])
                    t2 = set(suoi19.loc[suoi19.match_id == m19, "team_id"])
                    if t1 and t2 and not (t1 & t2):
                        comune += 1
            if comune:
                lc18 = co[co.ko < kickoff]
                miei18 = lc18[lc18.player_id == cur_id]
                suoi18 = lc18[lc18.player_id == oid_coach]
                mm18 = sorted(set(miei18["match_id"]) & set(suoi18["match_id"]))
                wi = di = li = 0
                for r in fin[fin.match_id.isin(mm18) & (fin.ko < kickoff)].itertuples(index=False):
                    tm18 = set(miei18.loc[miei18.match_id == r.match_id, "team_id"])
                    to18 = set(suoi18.loc[suoi18.match_id == r.match_id, "team_id"])
                    if not (tm18 and to18 and not (tm18 & to18)):
                        continue
                    gf, ga = ((r.home_goals, r.away_goals) if r.home_id in tm18
                              else (r.away_goals, r.home_goals))
                    if pd.isna(gf) or pd.isna(ga):
                        continue
                    if gf > ga:
                        wi += 1
                    elif gf == ga:
                        di += 1
                    else:
                        li += 1
                if wi + di + li:
                    oc_name = str(oc.iloc[-1].player_name)
                    atteso_inc = (f"un solo incrocio in panchina con {oc_name}: {wi}V {di}N {li}P"
                                  if wi + di + li == 1 else
                                  f"incroci in panchina con {oc_name}: "
                                  f"{wi}V {di}N {li}P su {wi + di + li} gare")
                    agg["incroci_panchina_pubblicati"] += int(atteso_inc in c_co)
                    if atteso_inc not in c_co:
                        errori["incroci"].append(f"{pg.stem}|{tname}| atteso «{atteso_inc}»")
                else:
                    agg["incroci_panchina_senza_esito"] += 1
            else:
                agg["incroci_panchina_assenti"] += 1
            precedenti.append((f"{pg.stem}|{tname}", n_b, comune))

            # ---- posta in gioco: percentuali dalla simulazione ----
            sm = sim[sim.team.map(canon) == canon(tname)]
            if sm.empty:
                agg["stakes_senza_simulazione"] += int("(simulazione stagione)" in c_st)
            else:
                r = sm.iloc[0]
                pct = (f"titolo {mc_percent_str(float(r.p_title))}%",
                       f"retrocessione {mc_percent_str(float(r.p_rel))}%")
                if pct[0] in c_st and pct[1] in c_st:
                    agg["stakes_pct"] += 1
                else:
                    errori["etichetta"].append(f"{pg.stem}|{tname}| percentuali «{pct}»")
                raw_top = r.get("p_top_n")
                if raw_top is None or pd.isna(raw_top):
                    raw_top = r.get("p_top4")
                p_e = None if raw_top is None or pd.isna(raw_top) else float(raw_top)
                if p_e is not None and p_e >= 0.35 and float(r.p_title) < 0.15:
                    et = "corsa alla Champions"
                elif float(r.p_title) >= 0.15:
                    et = "corsa al titolo"
                elif float(r.p_rel) >= 0.35:
                    et = "lotta salvezza"
                elif float(r.p_rel) >= 0.15:
                    et = "zona salvezza non lontana"
                else:
                    et = (f"proiezione: {str(round(float(r.pos_mean), 1)).replace('.', ',')}"
                          f"º posto in media")
                etichette[et.split(":")[0]] += 1
                if et not in c_st:
                    errori["etichetta"].append(f"{pg.stem}|{tname}| atteso «{et}»")
                ep_a, pm_a = float(r.exp_points), float(r.pos_mean)
                atteso_st = (f"stima di fine stagione: {ep_a:.1f}".replace(".", ",")
                             + " punti attesi"
                             + ("" if et.startswith("proiezione:") else
                                " · " + f"{pm_a:.1f}".replace(".", ",") + "º posto in media"))
                agg["stima_stagione"] += int(atteso_st in c_st)
                if atteso_st not in c_st:
                    errori["stima"].append(f"{pg.stem}|{tname}| atteso «{atteso_st}»")

            # ---- classifica: distanze e posizione virtuale, ricalcolate dalle tabelle ----
            tab = st[st.league_code == fr.lg].drop_duplicates("team_id") if fr.lg else st.iloc[0:0]
            rr = tab[tab.team_id == tid]
            if rr.empty:
                silenzi["table"].append(f"{pg.stem}|{tname}")
                continue
            rr = rr.iloc[0]
            pts, gd, rank = int(rr.points), int(rr.goal_diff or 0), int(rr["rank"])
            n = len(tab)
            releg = n - 2 if n == 20 else n - 1
            by = tab.set_index("rank")
            pezzi = [f"{rank}º con {pts} punt{'o' if pts == 1 else 'i'}"]
            if releg in by.index and rank < releg:
                marg = pts - int(by.loc[releg, "points"])
                pezzi.append(f"{marg} punt{'o' if marg == 1 else 'i'} sopra la zona retrocessione"
                             if marg > 0 else "a pari punti con la zona retrocessione")
            elif releg - 1 in by.index:
                need = int(by.loc[releg - 1, "points"]) - pts
                pezzi.append(f"{need} punt{'o' if need == 1 else 'i'} dalla salvezza diretta"
                             if need > 0 else "in zona salvezza diretta")
            ucl = posti.get(fr.lg)
            if ucl is not None and ucl in by.index:
                if rank <= ucl:
                    pezzi.append(f"in zona UCL (prime {ucl})")
                else:
                    ge = int(by.loc[ucl, "points"]) - pts
                    pezzi.append(f"{ge} punt{'o' if ge == 1 else 'i'} dal {ucl}º posto"
                                 if ge > 0 else f"a pari punti col {ucl}º posto")
            atteso_tab = " · ".join(pezzi)
            if atteso_tab in c_st:
                agg["table_line"] += 1
            else:
                errori["table"].append(f"{pg.stem}|{tname}| atteso «{atteso_tab}»")

            atteso_vir = (
                f"con una vittoria {posizione_virtuale(tab, tid, oid, pts, gd, 3, 0)}º · "
                f"con un pareggio {posizione_virtuale(tab, tid, oid, pts, gd, 1, 1)}º · "
                f"con una sconfitta {posizione_virtuale(tab, tid, oid, pts, gd, 0, 3)}º")
            if atteso_vir in c_st:
                agg["virtuale"] += 1
            else:
                errori["virtuale"].append(f"{pg.stem}|{tname}| atteso «{atteso_vir}»")
            posizioni.setdefault(et.split(":")[0], []).append(rank)

            # ---- età media titolari ----
            col = "home_avg_starter_age" if lato == 0 else "away_avg_starter_age"
            info = mi[mi.match_id == mid]
            eta = info.iloc[0].get(col) if not info.empty and col in info.columns else None
            titolari = int(((lu.match_id == mid) & (lu.team_id == tid)
                            & (lu.role == "starter")).sum())
            if eta is not None and not pd.isna(eta):
                atteso_eta = f"{round(float(eta), 1):.1f}".replace(".", ",") + " anni"
            else:
                atteso_eta = "n.d." if titolari else "distinta non ancora pubblicata"
            if atteso_eta in c_eta:
                agg["eta_ok"] += 1
                agg["eta_nd" if "n.d." in atteso_eta or "distinta" in atteso_eta else "eta_val"] += 1
            else:
                errori["eta"].append(f"{pg.stem}|{tname}| atteso «{atteso_eta}»")

    print("=== censimento ===")
    for k in sorted(agg):
        print(f"{k:36s} {agg[k]}")
    print("\n=== silenzi (riga assente senza dichiarazione) ===")
    for k, v in silenzi.items():
        print(f"{k}: {len(v)}" + (f" — es. {v[:3]}" if v else ""))
    print("\n=== scostamenti dal ricalcolo indipendente ===")
    for k, v in errori.items():
        print(f"{k}: {len(v)}" + (f" — es. {v[:2]}" if v else ""))
    print("\n=== etichette pubblicate e posizione reale ===")
    for et, v in etichette.most_common():
        pos = posizioni.get(et, [])
        print(f"{et:28s} {v:4d} · posizione min {min(pos) if pos else '-'} "
              f"mediana {sorted(pos)[len(pos) // 2] if pos else '-'} "
              f"max {max(pos) if pos else '-'}")
    print("\n=== precedenti (gare reali dell'allenatore vs avversaria / incroci) ===")
    if precedenti:
        d = pd.DataFrame(precedenti, columns=["cella", "vs_avv", "vs_all"])
        print(d[["vs_avv", "vs_all"]].value_counts().to_string())
    print("\n=== copertura per lega (pagine) ===")
    for k, v in fx[fx.match_id.isin([int(p.stem) for p in SITE.glob("*.html")])].lg.value_counts().items():
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
