# -*- coding: utf-8 -*-
"""
Gemeinsame pytest-Fixtures fuer ORAKEL FC 2026.

Jeder Test bekommt eine frische In-Memory-SQLite-DB und eine isolierte
Flask-App-Instanz - Tests beeinflussen sich nicht gegenseitig und ruehren
nie an einer echten orakel.db.
"""
import os

# WICHTIG: Umgebungsvariablen muessen gesetzt sein, BEVOR app.py importiert
# wird (SECRET_KEY wird beim Modul-Import geprueft, siehe app.py).
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("ADMIN_NAME", "admin")

import pytest


@pytest.fixture()
def app():
    """Frische App-Instanz mit In-Memory-SQLite pro Test."""
    import importlib
    import app as app_module
    importlib.reload(app_module)  # frischer Modulzustand pro Test

    app_module.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app_module.app.config["TESTING"] = True
    # CSRF in den meisten Tests ausgeschaltet; test_auth.py prueft ihn separat.
    app_module.app.config["WTF_CSRF_ENABLED"] = False

    with app_module.app.app_context():
        app_module.db.create_all()
        app_module.seed()
        yield app_module.app
        app_module.db.session.remove()
        app_module.db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_login(client):
    """Loggt den Test-Client als den geseedeten Admin ein."""
    client.post("/login", data={"name": "admin", "password": "test-admin-password"})
    return client
