# -*- coding: utf-8 -*-
"""
Rauchtests fuer die zentralen Routen: erreichbar nach Login, durchsetzen
von login_required/admin_required, Security-Header auf jeder Antwort.

Bewusst keine vollstaendigen Verhaltenstests jeder Route (das waere viel
Aufwand fuer wenig zusaetzlichen Schutz) - dieses Modul soll vor allem
verhindern, dass ein zukuenftiger Umbau (z.B. weitere Blueprint-Aenderungen)
eine Route still kaputt macht (404 statt 200, falscher Decorator etc.).
"""
import pytest


PUBLIC_ROUTES = ["/tips", "/jokers", "/missions", "/challenges", "/awards",
                 "/passwort", "/hilfe"]

ADMIN_ROUTES = ["/admin", "/admin/players", "/admin/matches", "/admin/assign",
                "/admin/adjustments", "/admin/jokerplays", "/admin/catalog/jokers"]


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_public_route_requires_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_public_route_reachable_after_login(admin_login, path):
    r = admin_login.get(path)
    assert r.status_code == 200, f"{path} sollte nach Login erreichbar sein"


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_route_requires_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code in (302, 403)


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_route_reachable_for_admin(admin_login, path):
    r = admin_login.get(path)
    assert r.status_code == 200, f"{path} sollte fuer Admin erreichbar sein"


def test_dashboard_reachable_after_login(admin_login):
    r = admin_login.get("/")
    assert r.status_code == 200


def test_security_headers_present_on_every_response(admin_login):
    for path in ["/", "/login"] + PUBLIC_ROUTES:
        r = admin_login.get(path)
        assert r.headers.get("X-Content-Type-Options") == "nosniff", path
        assert r.headers.get("X-Frame-Options") == "SAMEORIGIN", path
        assert r.headers.get("Content-Security-Policy"), path


def test_unknown_route_returns_404(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
