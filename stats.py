# -*- coding: utf-8 -*-
"""
Info-Panel-Statistiken fuer die Tippen-Seite: Form beider Teams, Kopf-an-
Kopf-Bilanz und Tipp-Verteilung der Gruppe - ausschliesslich aus Daten, die
bereits in der App stehen (keine externe Sport-API, kein API-Key noetig,
passt zum Selfhosted-Prinzip von ORAKEL FC). Reine Berechnungslogik, analog
zu scoring.py: kein Flask-Request-Kontext noetig, gut isoliert testbar.
"""
from extensions import db
from models import Match, Tip

FORM_LIMIT = 5
H2H_LIMIT = 5


def _result_letter(goals_for, goals_against):
    if goals_for > goals_against:
        return "S"
    if goals_for < goals_against:
        return "N"
    return "U"


def team_form(competition_id, team_name, before_kickoff, limit=FORM_LIMIT):
    """Letzte `limit` gewertete Spiele von team_name in diesem Turnier vor
    before_kickoff. Liefert eine Liste von 'S'/'U'/'N' (Sieg/Unentschieden/
    Niederlage), neuestes Spiel zuerst."""
    matches = (Match.query.filter(
        Match.competition_id == competition_id, Match.finished == True,
        Match.home_goals.isnot(None), Match.away_goals.isnot(None),
        Match.kickoff < before_kickoff,
        db.or_(Match.home == team_name, Match.away == team_name))
        .order_by(Match.kickoff.desc()).limit(limit).all())
    form = []
    for m in matches:
        is_home = m.home == team_name
        gf = m.home_goals if is_home else m.away_goals
        ga = m.away_goals if is_home else m.home_goals
        form.append(_result_letter(gf, ga))
    return form


def head_to_head(competition_id, team_a, team_b, before_kickoff, limit=H2H_LIMIT):
    """Bisherige direkte Duelle von team_a gegen team_b in diesem Turnier
    vor before_kickoff, neuestes zuerst."""
    return (Match.query.filter(
        Match.competition_id == competition_id, Match.finished == True,
        Match.home_goals.isnot(None), Match.away_goals.isnot(None),
        Match.kickoff < before_kickoff,
        db.or_(db.and_(Match.home == team_a, Match.away == team_b),
               db.and_(Match.home == team_b, Match.away == team_a)))
        .order_by(Match.kickoff.desc()).limit(limit).all())


def tip_distribution(match_id):
    """Tendenz-Verteilung aller bisher abgegebenen Tipps zu einem Spiel
    (Heimsieg/Remis/Auswaertssieg in Prozent). None, wenn noch niemand
    getippt hat."""
    tips = Tip.query.filter_by(match_id=match_id).all()
    home = draw = away = 0
    for t in tips:
        if t.home > t.away:
            home += 1
        elif t.home < t.away:
            away += 1
        else:
            draw += 1
    total = home + draw + away
    if not total:
        return None
    return {
        "total": total,
        "home_pct": round(100 * home / total), "draw_pct": round(100 * draw / total),
        "away_pct": round(100 * away / total),
    }


def match_stats(match, my_tip=None):
    """Buendelt Form, Kopf-an-Kopf und Gruppen-Tipp-Verteilung fuer ein
    Spiel. Die Gruppen-Verteilung wird nur zurueckgegeben, wenn das Spiel
    schon gesperrt ist oder my_tip vorliegt - sonst koennte das Einsehen
    fremder Tendenzen den eigenen Tipp unfair beeinflussen."""
    home_form = team_form(match.competition_id, match.home, match.kickoff)
    away_form = team_form(match.competition_id, match.away, match.kickoff)
    h2h = head_to_head(match.competition_id, match.home, match.away, match.kickoff)
    reveal_group = match.locked or my_tip is not None
    return {
        "home_form": home_form, "away_form": away_form, "h2h": h2h,
        "group": tip_distribution(match.id) if reveal_group else None,
        "has_anything": bool(home_form or away_form or h2h),
    }
