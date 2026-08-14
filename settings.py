# -*- coding: utf-8 -*-
"""Schluessel/Wert-Einstellungen (Setting-Tabelle) lesen und schreiben."""
from extensions import db
from models import Setting


def get_setting(key, default=""):
    s = db.session.get(Setting, key)
    return s.value if s else default


def set_setting(key, value):
    s = db.session.get(Setting, key)
    if s:
        s.value = value
    else:
        db.session.add(Setting(key=key, value=value))
    db.session.commit()


def is_simple():
    """True = 'Nur Tippspiel' (Joker/Missionen/Challenges/Awards/Chaos aus)."""
    return get_setting("simple_mode", "0") == "1"
