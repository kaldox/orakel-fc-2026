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


# ---------------------------------------------------------------------------
# Tipp-Vorschlag: eine grobe, transparente Einschaetzung aus Form + Kopf-an-
# Kopf-Bilanz - bewusst simpel und nachvollziehbar statt "smart", damit die
# Begruendung in einem Satz erklaerbar bleibt. Keine externen Daten, keine
# Erfolgsgarantie - siehe Hinweistext im Panel.
# ---------------------------------------------------------------------------
_FORM_POINTS = {"S": 3, "U": 1, "N": 0}

# (Punktedifferenz-Schwelle, Score-Vorschlag, Tendenz)
_SCORE_TIERS = [
    (1.3, "2:0", "home"), (0.4, "2:1", "home"),
    (-0.4, "1:1", "draw"),
    (-1.3, "1:2", "away"), (float("-inf"), "0:2", "away"),
]


def _avg_points(form):
    return sum(_FORM_POINTS[r] for r in form) / len(form) if form else None


def _h2h_tally(h2h, home_name):
    """Bisherige Duelle aus Sicht von home_name: (Siege, Remis, Niederlagen)."""
    w = d = l = 0
    for m in h2h:
        if m.home_goals == m.away_goals:
            d += 1
            continue
        winner = m.home if m.home_goals > m.away_goals else m.away
        if winner == home_name:
            w += 1
        else:
            l += 1
    return w, d, l


def recommend_tip(match, home_form, away_form, h2h):
    """Score-Vorschlag + Begruendung aus Form-Punkten (S=3/U=1/N=0 je
    Spiel) der letzten Spiele, mit Kopf-an-Kopf als Zuengelchen bei knappem
    Formvergleich. None, wenn es noch gar keine Datenbasis gibt (z.B. ganz
    zu Turnierbeginn)."""
    if not home_form and not away_form and not h2h:
        return None
    home_avg, away_avg = _avg_points(home_form), _avg_points(away_form)
    diff = (home_avg if home_avg is not None else 1.0) - (away_avg if away_avg is not None else 1.0)

    h2h_w, h2h_d, h2h_l = _h2h_tally(h2h, match.home)
    if abs(diff) < 0.3 and h2h_w != h2h_l:
        diff += 0.4 if h2h_w > h2h_l else -0.4

    score, tendency = next((s, tend) for threshold, s, tend in _SCORE_TIERS if diff > threshold)

    return {
        "score": score, "tendency": tendency,
        "home_avg": home_avg, "home_games": len(home_form),
        "away_avg": away_avg, "away_games": len(away_form),
        "h2h_w": h2h_w, "h2h_d": h2h_d, "h2h_l": h2h_l, "h2h_games": len(h2h),
    }


def match_stats(match, my_tip=None):
    """Buendelt Form, Kopf-an-Kopf, Gruppen-Tipp-Verteilung und Tipp-
    Vorschlag fuer ein Spiel. Die Gruppen-Verteilung wird nur zurueck-
    gegeben, wenn das Spiel schon gesperrt ist oder my_tip vorliegt - sonst
    koennte das Einsehen fremder Tendenzen den eigenen Tipp unfair
    beeinflussen. Der Tipp-Vorschlag beruht dagegen nur auf objektiven
    Ergebnissen (nicht auf fremden Tipps) und ist deshalb immer sichtbar."""
    home_form = team_form(match.competition_id, match.home, match.kickoff)
    away_form = team_form(match.competition_id, match.away, match.kickoff)
    h2h = head_to_head(match.competition_id, match.home, match.away, match.kickoff)
    reveal_group = match.locked or my_tip is not None
    return {
        "home_form": home_form, "away_form": away_form, "h2h": h2h,
        "group": tip_distribution(match.id) if reveal_group else None,
        "recommendation": recommend_tip(match, home_form, away_form, h2h),
        "has_anything": bool(home_form or away_form or h2h),
    }
