# -*- coding: utf-8 -*-
"""
Authentifizierung und Zugriffsschutz fuer ORAKEL FC 2026.

Enthaelt:
- current_player(): aktuell eingeloggter Spieler (oder None)
- login_required / admin_required: Route-Decorators
- Bruteforce-Schutz fuer den Login (in-memory, siehe Kommentar unten)
- _safe_next_target(): Schutz gegen Open-Redirect ueber ?next=
"""
import time
import threading
from functools import wraps
from urllib.parse import urlparse

from flask import session, redirect, url_for, request, abort

from extensions import db
from models import Player

# --- Schutz gegen Passwort-Rateversuche (in-memory, pro Benutzername) ---
# Bewusst in-memory statt in der DB: einfacher, ausreichend für eine private
# Liga mit überschaubarer Nutzerzahl. Nachteil: der Sperrzustand geht bei
# jedem Prozess-/Container-Neustart verloren (z.B. durch Auto-Updates oder
# das Backup-Script, das den Container kurz stoppt). Für ein öffentlich
# exponiertes Setup mit vielen Nutzern wäre eine DB-gestützte Sperre
# (z.B. eigene Tabelle, analog zu Player) robuster.
_login_lock = threading.Lock()
_login_fails = {}            # name (lowercase) -> Liste mit Fehlversuch-Zeitstempeln
LOGIN_WINDOW = 900           # Beobachtungsfenster in Sekunden (15 min)
LOGIN_MAX = 8                # so viele Fehlversuche -> kurze Sperre


def _bf_locked(name):
    now = time.time()
    with _login_lock:
        fails = [t for t in _login_fails.get(name.lower(), []) if now - t < LOGIN_WINDOW]
        _login_fails[name.lower()] = fails
        return len(fails) >= LOGIN_MAX


def _bf_record(name):
    with _login_lock:
        _login_fails.setdefault(name.lower(), []).append(time.time())


def _bf_clear(name):
    with _login_lock:
        _login_fails.pop(name.lower(), None)


def _safe_next_target(value):
    """
    Lässt nur interne, relative Pfade als Redirect-Ziel zu (z.B. "/dashboard").
    Verhindert Open-Redirect ueber ?next=https://fremde-seite/ (Phishing).
    """
    if not value:
        return None
    parsed = urlparse(value)
    # Kein Schema (http/https) und kein Host -> rein relativer Pfad, sicher.
    if parsed.scheme or parsed.netloc:
        return None
    if not value.startswith("/") or value.startswith("//"):
        return None
    return value


def current_player():
    pid = session.get("pid")
    return db.session.get(Player, pid) if pid else None


def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if not current_player():
            return redirect(url_for("public.login", next=request.path))
        return f(*a, **k)
    return wrap


def admin_required(f):
    @wraps(f)
    def wrap(*a, **k):
        p = current_player()
        if not p or not p.is_admin:
            abort(403)
        return f(*a, **k)
    return wrap
