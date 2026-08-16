# -*- coding: utf-8 -*-
"""
Tests fuer stats.py: Form, Kopf-an-Kopf-Bilanz und Tipp-Verteilung der
Gruppe fuers Info-Panel auf der Tippen-Seite - alles aus App-eigenen Daten.
"""
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from extensions import db
from models import Match, Player, Tip
from stats import head_to_head, match_stats, recommend_tip, team_form, tip_distribution


def mkplayer(name, competition):
    from models import Membership
    p = Player(name=name, pw_hash=generate_password_hash("x"), plays=True)
    db.session.add(p)
    db.session.commit()
    db.session.add(Membership(player_id=p.id, competition_id=competition.id, plays=True))
    db.session.commit()
    return p


def mkmatch(competition, home, away, hg, ag, days_ago):
    m = Match(competition_id=competition.id, matchday="1", stage="Test", home=home, away=away,
              kickoff=datetime.now() - timedelta(days=days_ago),
              home_goals=hg, away_goals=ag, finished=True)
    db.session.add(m)
    db.session.commit()
    return m


def test_team_form_neuestes_zuerst_und_begrenzt(app, competition):
    with app.app_context():
        mkmatch(competition, "CH", "A", 2, 0, days_ago=10)  # CH Sieg
        mkmatch(competition, "B", "CH", 1, 1, days_ago=8)   # CH Remis
        mkmatch(competition, "CH", "C", 0, 3, days_ago=6)   # CH Niederlage
        now = datetime.now()
        form = team_form(competition.id, "CH", now)
        assert form == ["N", "U", "S"]  # neuestes (Niederlage) zuerst


def test_team_form_ignoriert_spiele_nach_dem_betrachteten_anstoss(app, competition):
    with app.app_context():
        mkmatch(competition, "CH", "A", 0, 3, days_ago=10)  # Niederlage, vor dem Stichtag
        mkmatch(competition, "CH", "B", 5, 0, days_ago=-5)  # Sieg, aber NACH dem Stichtag
        stichtag = datetime.now() - timedelta(days=1)
        form = team_form(competition.id, "CH", stichtag)
        assert form == ["N"]  # der spaetere Sieg darf die "Form" nicht rueckwirkend aufhuebschen


def test_head_to_head_findet_beide_heim_auswaerts_richtungen(app, competition):
    with app.app_context():
        mkmatch(competition, "CH", "DE", 2, 1, days_ago=20)
        mkmatch(competition, "DE", "CH", 0, 0, days_ago=10)
        now = datetime.now()
        h2h = head_to_head(competition.id, "CH", "DE", now)
        assert len(h2h) == 2
        assert h2h[0].kickoff > h2h[1].kickoff  # neuestes zuerst


def test_tip_distribution_prozente_und_leer(app, competition):
    with app.app_context():
        anna = mkplayer("Anna", competition)
        ben = mkplayer("Ben", competition)
        cleo = mkplayer("Cleo", competition)
        m = mkmatch(competition, "CH", "DE", None, None, days_ago=-1)
        m.finished = False
        db.session.commit()
        assert tip_distribution(m.id) is None  # noch keine Tipps

        db.session.add(Tip(player_id=anna.id, match_id=m.id, home=2, away=0))  # Heim
        db.session.add(Tip(player_id=ben.id, match_id=m.id, home=1, away=1))   # Remis
        db.session.add(Tip(player_id=cleo.id, match_id=m.id, home=3, away=1))  # Heim
        db.session.commit()

        dist = tip_distribution(m.id)
        assert dist["total"] == 3
        assert dist["home_pct"] == 67
        assert dist["draw_pct"] == 33
        assert dist["away_pct"] == 0


def test_match_stats_gruppentipp_erst_nach_eigenem_tipp_oder_sperre(app, competition):
    with app.app_context():
        anna = mkplayer("Anna", competition)
        ben = mkplayer("Ben", competition)
        future = mkmatch(competition, "CH", "DE", None, None, days_ago=-5)
        future.finished, future.kickoff = False, datetime.now() + timedelta(days=5)
        db.session.commit()
        db.session.add(Tip(player_id=anna.id, match_id=future.id, home=1, away=0))
        db.session.commit()

        # Ben hat noch nicht getippt und das Spiel ist noch nicht gesperrt
        # -> Gruppentipp bleibt verborgen, um Beeinflussung zu vermeiden.
        st_hidden = match_stats(future, my_tip=None)
        assert st_hidden["group"] is None

        # Anna hat schon getippt -> sieht die Verteilung.
        my_tip = Tip.query.filter_by(player_id=anna.id, match_id=future.id).first()
        st_visible = match_stats(future, my_tip=my_tip)
        assert st_visible["group"] is not None
        assert st_visible["group"]["total"] == 1


def test_match_stats_nach_anpfiff_immer_sichtbar(app, competition):
    with app.app_context():
        anna = mkplayer("Anna", competition)
        past = mkmatch(competition, "CH", "DE", 1, 0, days_ago=1)
        db.session.add(Tip(player_id=anna.id, match_id=past.id, home=1, away=0))
        db.session.commit()
        st = match_stats(past, my_tip=None)  # Betrachter hat selbst nicht getippt
        assert st["group"] is not None  # Spiel ist gesperrt (Anpfiff vorbei) -> trotzdem sichtbar


# ── Tipp-Vorschlag ──────────────────────────────────────────────────────

def test_recommend_tip_ohne_datenbasis_liefert_none():
    # Ganz zu Turnierbeginn: keine Form, kein Kopf-an-Kopf -> kein Vorschlag,
    # statt eine unbegruendbare Zahl zu erfinden.
    class Dummy:
        home, away = "CH", "DE"
    assert recommend_tip(Dummy(), [], [], []) is None


def test_recommend_tip_klar_ueberlegenes_heimteam(app, competition):
    with app.app_context():
        # CH: 3 Siege in Folge, DE: 3 Niederlagen in Folge
        mkmatch(competition, "CH", "X", 3, 0, days_ago=10)
        mkmatch(competition, "CH", "Y", 2, 0, days_ago=8)
        mkmatch(competition, "CH", "Z", 1, 0, days_ago=6)
        mkmatch(competition, "DE", "X", 0, 2, days_ago=9)
        mkmatch(competition, "DE", "Y", 0, 1, days_ago=7)
        mkmatch(competition, "DE", "Z", 0, 3, days_ago=5)
        upcoming = mkmatch(competition, "CH", "DE", None, None, days_ago=-1)
        upcoming.finished = False
        db.session.commit()

        home_form = team_form(competition.id, "CH", upcoming.kickoff)
        away_form = team_form(competition.id, "DE", upcoming.kickoff)
        h2h = head_to_head(competition.id, "CH", "DE", upcoming.kickoff)
        rec = recommend_tip(upcoming, home_form, away_form, h2h)

        assert rec["tendency"] == "home"
        assert rec["home_avg"] == 3.0  # 3 Siege = 3.0 Punkte/Spiel
        assert rec["away_avg"] == 0.0  # 3 Niederlagen = 0.0 Punkte/Spiel
        assert rec["home_games"] == 3 and rec["away_games"] == 3


def test_recommend_tip_ausgeglichene_form_remis():
    from stats import recommend_tip

    class Dummy:
        home, away = "CH", "DE"
    # Gleiche Form (je 1 Sieg, 1 Niederlage) und keine Kopf-an-Kopf-Historie
    # -> ausgeglichen, Vorschlag soll auf Remis lauten.
    rec = recommend_tip(Dummy(), ["S", "N"], ["S", "N"], [])
    assert rec["tendency"] == "draw"
    assert rec["score"] == "1:1"


def test_recommend_tip_kopf_an_kopf_als_zuenglein_bei_gleicher_form():
    # Bewusst mit handgebauten Objekten statt DB-Fixtures: team_form() zieht
    # auch die Kopf-an-Kopf-Spiele selbst mit ein, sobald sie in der DB
    # stehen - dann waere die "Form" nie wirklich unabhaengig von der
    # Duell-Historie testbar. Hier bleiben beide bewusst getrennt.
    class FakeMatch:
        def __init__(self, home, away, hg, ag):
            self.home, self.away, self.home_goals, self.away_goals = home, away, hg, ag

    class Dummy:
        home, away = "DE", "CH"

    # Gleiche Form (je 1 Sieg, 1 Niederlage) fuer beide Teams...
    home_form, away_form = ["S", "N"], ["S", "N"]
    # ...aber CH hat die letzten direkten Duelle klar dominiert.
    h2h = [FakeMatch("CH", "DE", 3, 1), FakeMatch("CH", "DE", 2, 0)]
    rec = recommend_tip(Dummy(), home_form, away_form, h2h)

    assert rec["h2h_games"] == 2
    assert rec["tendency"] == "away"  # CH (hier Gast) dominierte die Duelle
