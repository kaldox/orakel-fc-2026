# -*- coding: utf-8 -*-
"""
Tests fuer die Wertungs-Engine (scoring.py) von ORAKEL FC 2026.

Deckt Basis-Tippauswertung (Tendenz/Differenz/Exakt), KO- und
Ueberraschungsbonus, Risiko-Verdopplung sowie den Verdoppler-Joker ab.
Identische Szenarien wie der urspruengliche Skript-Test, jetzt als
pytest-Faelle mit Fixtures statt eigener check()-Funktion.
"""
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from extensions import db
from models import JokerPlay, JokerType, Match, Membership, Player, Tip
from scoring import compute_standings


def mkplayer(name, competition):
    p = Player(name=name, pw_hash=generate_password_hash("x"), plays=True)
    db.session.add(p)
    db.session.commit()
    db.session.add(Membership(player_id=p.id, competition_id=competition.id, plays=True))
    db.session.commit()
    return p


def mkmatch(competition, md, home, away, hg, ag, ko=False, surprise=False, days_ago=1):
    m = Match(competition_id=competition.id, matchday=md, stage="Test", home=home, away=away,
              kickoff=datetime.now() - timedelta(days=days_ago),
              home_goals=hg, away_goals=ag, finished=True,
              is_knockout=ko, surprise=surprise)
    db.session.add(m)
    db.session.commit()
    return m


def tip(player, match, h, a, risk=False):
    db.session.add(Tip(player_id=player.id, match_id=match.id,
                       home=h, away=a, is_risk=risk))
    db.session.commit()


def row_for(rows, player):
    return next(r for r in rows if r["player"].id == player.id)


def test_basis_wertung_tendenz_differenz_exakt_ko_ueberraschung(app, competition):
    """Szenario A: reine Tippauswertung ohne Joker."""
    with app.app_context():
        anna = mkplayer("Anna", competition)
        ben = mkplayer("Ben", competition)

        m1 = mkmatch(competition, "1", "CH", "BR", 2, 1)                          # 2:1
        m2 = mkmatch(competition, "2", "DE", "FR", 0, 1, ko=True, surprise=True)  # 0:1, KO + Ueberraschung

        tip(anna, m1, 2, 1)   # exakt -> 8
        tip(anna, m2, 0, 1)   # exakt + KO(+2) + Ueberraschung(+3) -> 13
        tip(ben, m1, 1, 0)    # Tendenz Heimsieg, Differenz 1 == 1 -> 5
        tip(ben, m2, 1, 0)    # falsche Tendenz -> 0

        rows = compute_standings(competition)

        assert row_for(rows, anna)["tips"] == 21
        assert row_for(rows, anna)["total"] == 21
        assert row_for(rows, ben)["tips"] == 5
        assert row_for(rows, ben)["total"] == 5
        assert rows[0]["player"].name == "Anna"


def test_risiko_tipp_und_verdoppler_joker(app, competition):
    """Szenario B: Risiko-Tipp (x2 bei Treffer) + Verdoppler-Joker auf einen Spieltag."""
    with app.app_context():
        anna = mkplayer("Anna", competition)
        ben = mkplayer("Ben", competition)

        m1 = mkmatch(competition, "1", "CH", "BR", 2, 1)
        m2 = mkmatch(competition, "2", "DE", "FR", 0, 1, ko=True, surprise=True)

        tip(anna, m1, 2, 1)             # 8
        tip(anna, m2, 0, 1)             # 13 (Basis)
        tip(ben, m1, 1, 0, risk=True)   # 5 -> Risiko korrekt -> x2 = 10
        tip(ben, m2, 1, 0)              # 0

        # Anna spielt Verdoppler auf m2 -> Tagespunkte von Spieltag "2" verdoppeln sich: 13 -> 26
        dbl = JokerType.query.filter_by(auto_effect="double", competition_id=competition.id).first()
        db.session.add(JokerPlay(competition_id=competition.id, player_id=anna.id, joker_type_id=dbl.id,
                                 match_id=m2.id, matchday="2"))
        db.session.commit()

        rows = compute_standings(competition)
        ra, rb = row_for(rows, anna), row_for(rows, ben)

        assert ra["tips"] == 21           # unverdoppelte Tipp-Summe bleibt gleich
        assert ra["joker"] == 13          # 26 - 13 Joker-Bonus
        assert ra["total"] == 34          # 8 + 26
        assert rb["tips"] == 10           # Risiko x2
        assert rb["joker"] == 0
        assert rb["total"] == 10


def test_zwei_turniere_bleiben_getrennt(app, competition, second_competition):
    """Punkte/Tabellen zweier paralleler Turniere duerfen sich nicht vermischen."""
    with app.app_context():
        anna = mkplayer("Anna", competition)
        # Gleicher Name waere durch die Unique-Constraint auf Player.name verboten -
        # ein Spieler kann aber Mitglied in mehreren Turnieren sein.
        db.session.add(Membership(player_id=anna.id, competition_id=second_competition.id, plays=True))
        db.session.commit()

        m1 = mkmatch(competition, "1", "CH", "BR", 2, 1)
        m2 = mkmatch(second_competition, "1", "DE", "FR", 1, 1)

        tip(anna, m1, 2, 1)   # exakt im ersten Turnier -> 8
        tip(anna, m2, 2, 0)   # falsche Tendenz (Heimsieg statt Remis) im zweiten Turnier -> 0

        rows1 = compute_standings(competition)
        rows2 = compute_standings(second_competition)

        assert row_for(rows1, anna)["total"] == 8
        assert row_for(rows2, anna)["total"] == 0
