# -*- coding: utf-8 -*-
"""
Punkteberechnung fuer ORAKEL FC 2026: Basis-Tippauswertung, Joker-Effekte,
Missionen/Challenges/Anpassungen und die finale Tabelle (Standings).

Reine Berechnungslogik auf Basis der Models - kein Flask-Request-Kontext
noetig, dadurch gut isoliert testbar (siehe tests/test_scoring.py).
"""
from math import floor

from extensions import db
from models import (Adjustment, Challenge, JokerPlay, JokerType, Match,
                     Mission, MissionAssignment, Player, Tip)

sign = lambda x: (x > 0) - (x < 0)


def base_match_points(tip, match):
    correct = sign(tip.home - tip.away) == sign(match.home_goals - match.away_goals)
    if tip.home == match.home_goals and tip.away == match.away_goals:
        pts = 8
    elif correct and (tip.home - tip.away) == (match.home_goals - match.away_goals):
        pts = 5
    elif correct:
        pts = 3
    else:
        pts = 0
    if correct:
        if match.is_knockout:
            pts += 2
        if match.surprise:
            pts += 3
    if tip.is_risk:
        pts = pts * 2 if correct else -4
    return pts, correct


def compute_standings():
    players = Player.query.filter_by(plays=True).all()
    matches = {m.id: m for m in Match.query.all()}
    finished = [m for m in matches.values() if m.has_result]
    tips = {(t.player_id, t.match_id): t for t in Tip.query.all()}
    plays = JokerPlay.query.all()

    double_at, allin_at, triple_at = {}, {}, set()
    swap_for, sabotaged, shielded, lucky_at = set(), set(), set(), set()
    effect = {j.id: j.auto_effect for j in JokerType.query.all()}
    for p in plays:
        eff = effect.get(p.joker_type_id, "manual")
        if eff == "double" and p.match_id:
            double_at[(p.player_id, p.match_id)] = True
        elif eff == "allin" and p.match_id:
            m = matches.get(p.match_id)
            if m:
                allin_at[(p.player_id, m.matchday)] = p.match_id
        elif eff == "triple" and p.matchday:
            triple_at.add((p.player_id, p.matchday))
        elif eff == "swap":
            swap_for.add(p.player_id)
        elif eff == "sabotage" and p.target_player_id and p.matchday:
            sabotaged.add((p.target_player_id, p.matchday))
        elif eff == "shield" and p.matchday:
            shielded.add((p.player_id, p.matchday))
        elif eff == "lucky" and p.matchday:
            lucky_at.add((p.player_id, p.matchday))

    rows, daydata = [], {}
    for p in players:
        tips_total, per_day = 0, {}
        for m in finished:
            t = tips.get((p.id, m.id))
            if not t:
                continue
            pts, _ = base_match_points(t, m)
            tips_total += pts
            day_pts = pts * (2 if double_at.get((p.id, m.id)) else 1)
            per_day[m.matchday] = per_day.get(m.matchday, 0) + day_pts
        final_day = {}
        for md, dpts in per_day.items():
            day = dpts
            mid = allin_at.get((p.id, md))
            if mid:
                m = matches.get(mid)
                t = tips.get((p.id, mid))
                ok = bool(m and t and sign(t.home - t.away) == sign(m.home_goals - m.away_goals))
                day = day * 3 if ok else 0
            if (p.id, md) in triple_at:
                day *= 3
            if (p.id, md) in sabotaged and (p.id, md) not in shielded:
                day = floor(day / 2)
            if (p.id, md) in lucky_at and day <= 0:
                day = 3
            final_day[md] = day
        daydata[p.id] = final_day
        rows.append({"player": p, "tips": tips_total})

    for pid in swap_for:
        fd = daydata.get(pid, {})
        if not fd:
            continue
        worst_md = min(fd, key=lambda k: fd[k])
        vals = [daydata[o.id][worst_md] for o in players if worst_md in daydata.get(o.id, {})]
        if vals:
            fd[worst_md] = round(sum(vals) / len(vals))

    miss = {}
    for a in MissionAssignment.query.filter_by(completed=True).all():
        m = db.session.get(Mission, a.mission_id)
        if m:
            miss[a.player_id] = miss.get(a.player_id, 0) + m.points
    chal = {}
    for c in Challenge.query.filter(Challenge.winner_player_id.isnot(None)).all():
        chal[c.winner_player_id] = chal.get(c.winner_player_id, 0) + c.points
    adj = {}
    for a in Adjustment.query.all():
        adj[a.player_id] = adj.get(a.player_id, 0) + a.points

    for r in rows:
        pid = r["player"].id
        engine = sum(daydata.get(pid, {}).values())
        r["joker"] = engine - r["tips"]
        r["missions"] = miss.get(pid, 0)
        r["challenges"] = chal.get(pid, 0)
        r["adjust"] = adj.get(pid, 0)
        r["total"] = engine + r["missions"] + r["challenges"] + r["adjust"]
    rows.sort(key=lambda r: r["total"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
