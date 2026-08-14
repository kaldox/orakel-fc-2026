# -*- coding: utf-8 -*-
"""
Tests fuer auth.py: Login-Flow, Bruteforce-Schutz, Open-Redirect-Schutz
und die login_required/admin_required-Decorators.
"""
import re

import pytest

from auth import _safe_next_target, _bf_locked, _bf_record, _bf_clear, _login_fails


def _get_csrf(client, path):
    r = client.get(path)
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True))
    return m.group(1) if m else None


# ── _safe_next_target: Open-Redirect-Schutz ──────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("/dashboard", "/dashboard"),
    ("/tips?week=3", "/tips?week=3"),
    ("/", "/"),
    (None, None),
    ("", None),
    ("https://evil.example/phish", None),
    ("http://evil.example", None),
    ("//evil.example/phish", None),
    ("javascript:alert(1)", None),
])
def test_safe_next_target(value, expected):
    assert _safe_next_target(value) == expected


# ── Bruteforce-Schutz ─────────────────────────────────────────────────────────

def test_bruteforce_lock_after_max_attempts():
    name = "bf-test-user"
    _login_fails.pop(name, None)
    try:
        for _ in range(7):
            _bf_record(name)
        assert not _bf_locked(name), "sollte unter dem Limit noch nicht gesperrt sein"
        _bf_record(name)  # 8. Fehlversuch
        assert _bf_locked(name), "sollte ab 8 Fehlversuchen gesperrt sein"
    finally:
        _bf_clear(name)


def test_bruteforce_clear_resets_lock():
    name = "bf-test-user-2"
    try:
        for _ in range(8):
            _bf_record(name)
        assert _bf_locked(name)
        _bf_clear(name)
        assert not _bf_locked(name)
    finally:
        _bf_clear(name)


def test_bruteforce_is_per_username_case_insensitive():
    name_lower = "bf-case-test"
    name_upper = "BF-CASE-TEST"
    _bf_clear(name_lower)
    try:
        for _ in range(8):
            _bf_record(name_lower)
        assert _bf_locked(name_upper), "Sperre sollte unabhaengig von Gross-/Kleinschreibung gelten"
    finally:
        _bf_clear(name_lower)


# ── Login-Flow (End-to-End ueber den Test-Client) ────────────────────────────

def test_login_required_redirects_to_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_login_with_correct_credentials_succeeds(client):
    r = client.post("/login", data={"name": "admin", "password": "test-admin-password"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"] == "/"


def test_login_with_wrong_password_fails(client):
    r = client.post("/login", data={"name": "admin", "password": "falsch"},
                    follow_redirects=True)
    assert r.status_code == 200
    # Kein Redirect zum Dashboard -> immer noch auf der Login-Seite
    assert "Name oder Passwort stimmt nicht" in r.get_data(as_text=True) or \
           "doesn" in r.get_data(as_text=True).lower() or \
           "name" in r.get_data(as_text=True).lower()


def test_login_redirect_ignores_external_next(client):
    """Open-Redirect-Regressionstest: ?next= mit fremder Domain wird ignoriert."""
    r = client.post("/login?next=https://evil.example/phish",
                    data={"name": "admin", "password": "test-admin-password"},
                    follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"] == "/", "Open-Redirect nicht blockiert!"


def test_login_redirect_allows_internal_next(client):
    r = client.post("/login?next=/tips",
                    data={"name": "admin", "password": "test-admin-password"},
                    follow_redirects=False)
    assert r.headers["Location"] == "/tips"


def test_admin_required_blocks_non_admin(app, client):
    from extensions import db
    from models import Player
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db.session.add(Player(name="normalo", pw_hash=generate_password_hash("x"),
                              is_admin=False, plays=True))
        db.session.commit()

    client.post("/login", data={"name": "normalo", "password": "x"})
    r = client.get("/admin")
    assert r.status_code == 403


def test_logout_clears_session(client):
    client.post("/login", data={"name": "admin", "password": "test-admin-password"})
    assert client.get("/").status_code == 200
    client.get("/logout")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]
