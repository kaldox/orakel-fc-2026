# -*- coding: utf-8 -*-
"""
Tests fuer das Mehrere-Turniere-Feature (competitions.py + Scoping in
scoring.py/routes). Deckt ab: der Ein-Turnier-Alltag bleibt unveraendert
(kein Umschalter), Admins koennen ein zweites Turnier anlegen und bestehende
Spieler:innen dafuer gewinnen, ein Turnier-Wechsel ohne Mitgliedschaft wird
abgelehnt, und der Migrations-Backfill fuer Bestandsdaten funktioniert.
"""
import re

from werkzeug.security import generate_password_hash

from extensions import db
from models import Competition, Match, Membership, Player


def _get_csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True))
    return m.group(1) if m else None


def test_ein_turnier_zeigt_keinen_umschalter(admin_login):
    """Bei genau einem aktiven Turnier bleibt die Oberflaeche wie vor dem
    Multi-Turnier-Umbau: kein Umschalter, kein Extra-Klick."""
    r = admin_login.get("/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'name="competition_id"' not in html


def test_admin_legt_zweites_turnier_an_und_fuegt_bestehenden_spieler_hinzu(app, admin_login, competition):
    with app.app_context():
        db.session.add(Player(name="mira", pw_hash=generate_password_hash("x"), plays=True))
        db.session.commit()

    csrf = _get_csrf(admin_login, "/admin/wettbewerbe")
    r = admin_login.post("/admin/wettbewerbe", data={
        "csrf_token": csrf, "name": "DFB-Pokal", "format": "cup",
    }, follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        assert Competition.query.count() == 2
        pokal = Competition.query.filter_by(name="DFB-Pokal").first()
        assert pokal is not None
        assert pokal.matchday_label  # aus FORMAT_PRESETS vorbelegt
        mira = Player.query.filter_by(name="mira").first()
        # Neu angelegtes Turnier ist jetzt aktiv gewaehlt (Session) - "mira"
        # ist dort aber noch nicht Mitglied.
        assert not Membership.query.filter_by(player_id=mira.id, competition_id=pokal.id).first()

    csrf2 = _get_csrf(admin_login, "/admin/players")
    r = admin_login.post("/admin/players", data={
        "csrf_token": csrf2, "action": "addmember", "player_id": mira.id,
    }, follow_redirects=False)
    assert r.status_code == 302

    with app.app_context():
        assert Membership.query.filter_by(player_id=mira.id, competition_id=pokal.id).first()
        # Ursprüngliches Turnier bleibt unberuehrt.
        assert Membership.query.filter_by(player_id=mira.id, competition_id=competition.id).first() is None


def test_wechsel_zu_turnier_ohne_mitgliedschaft_wird_abgelehnt(app, client, competition):
    with app.app_context():
        db.session.add(Player(name="theo", pw_hash=generate_password_hash("x"), plays=True))
        db.session.commit()
        fremd = Competition(slug="fremd", name="Fremdes Turnier")
        db.session.add(fremd)
        db.session.commit()
        fremd_id = fremd.id

    client.post("/login", data={"name": "theo", "password": "x"})
    csrf = _get_csrf(client, "/")
    r = client.post("/wettbewerb/wechseln", data={"csrf_token": csrf, "competition_id": fremd_id},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "nicht verfügbar" in r.get_data(as_text=True) or "not available" in r.get_data(as_text=True).lower()


def test_letztes_aktives_turnier_kann_nicht_archiviert_werden(admin_login, competition):
    """Regressionstest: sonst kann man sich komplett aus dem Admin-Bereich
    aussperren, weil jede Admin-Seite ein erreichbares aktives Turnier
    braucht - auch die Turnierverwaltung selbst."""
    csrf = _get_csrf(admin_login, "/admin/wettbewerbe")
    r = admin_login.post("/admin/wettbewerbe", data={
        "csrf_token": csrf, "action": "archive", "id": competition.id,
    }, follow_redirects=True)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Mindestens ein Turnier" in html or "must stay active" in html.lower()

    # Turnier ist immer noch aktiv, Admin-Bereich bleibt erreichbar.
    assert admin_login.get("/admin/wettbewerbe").status_code == 200
    assert admin_login.get("/admin").status_code == 200


def test_migration_backfill_zieht_alte_zeilen_ohne_competition_id_nach(app, competition):
    """Simuliert eine Zeile wie vor dem Umstieg auf Competition (noch ohne
    competition_id) - der naechste Migrationslauf muss sie nachziehen."""
    import app as app_module
    from datetime import datetime

    with app.app_context():
        m = Match(home="A", away="B", kickoff=datetime.now())
        db.session.add(m)
        db.session.commit()
        assert m.competition_id is None

        app_module._migrate_to_competitions()

        db.session.refresh(m)
        assert m.competition_id == competition.id
