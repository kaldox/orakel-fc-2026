# -*- coding: utf-8 -*-
"""
Laufzeit-Hilfsfunktionen fuer Mehrsprachigkeit.

Die eigentlichen Uebersetzungstabellen liegen in i18n.py (TR_EN).
Hier nur die Logik, welche Sprache aktiv ist und wie uebersetzt wird.
"""
from flask import session, has_request_context, request

from i18n import TR_EN


def get_lang():
    lang = session.get("lang") if has_request_context() else None
    if lang in ("en", "de"):
        return lang
    # Keine explizite Wahl -> an Browsersprache ausrichten (sonst Englisch).
    if has_request_context():
        best = request.accept_languages.best_match(["de", "en"])
        if best:
            return best
    return "en"


def t(s, **kw):
    """Uebersetzt den deutschen Quelltext s. In EN via Tabelle, sonst (DE) 1:1.
    Fehlt ein Eintrag, bleibt der deutsche Text stehen (kein Crash)."""
    out = s if get_lang() == "de" else TR_EN.get(s, s)
    if kw:
        try:
            out = out.format(**kw)
        except Exception:
            pass
    return out
