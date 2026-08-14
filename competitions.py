# -*- coding: utf-8 -*-
"""
Turnier-/Wettbewerbsauswahl fuer ORAKEL FC.

Eine Installation kann ein oder mehrere Turniere (Competition) parallel
verwalten (z.B. Bundesliga-Tippspiel + DFB-Pokal-Tippspiel gleichzeitig).
Bei genau einem aktiven Turnier wird es automatisch verwendet - kein
Umschalter, kein Extra-Klick, Verhalten bleibt wie bisher. Erst ab zwei
aktiven Turnieren kommt ein Session-basierter Umschalter zum Einsatz,
analog zu current_player() in auth.py.

"Format" ist reine Beschriftungs-Vorbelegung (Spieltag-/Phasen-Label) fuer
neue Turniere - die Wertungslogik in scoring.py ist fuer jedes Format
identisch (Tendenz/Differenz/Exakt, K.-o.- und Ueberraschungs-Bonus).
"""
import re

from flask import abort, session

from models import Competition, Membership

# Vorbelegung fuer's Anlegen eines neuen Turniers im Admin-Bereich.
FORMAT_PRESETS = {
    "league": {"label": "Liga (Hin-/Rückrunde)", "matchday_label": "Spieltag", "stage_label": "Runde"},
    "cup": {"label": "Pokal (K.-o.-Runden)", "matchday_label": "Runde", "stage_label": "Runde"},
    "group_knockout": {"label": "Gruppenphase + K.-o. (z.B. WM, EM)", "matchday_label": "Spieltag", "stage_label": "Gruppe"},
    "swiss": {"label": "Schweizer Modus + K.-o. (z.B. Champions League)", "matchday_label": "Spieltag", "stage_label": "Ligaphase"},
}


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "turnier"


def unique_slug(name):
    """Slug aus name, mit Suffix -2, -3, ... falls schon vergeben."""
    base = slugify(name)
    slug, n = base, 2
    while Competition.query.filter_by(slug=slug).first():
        slug = "%s-%d" % (base, n)
        n += 1
    return slug


def active_competitions():
    return Competition.query.filter_by(active=True).order_by(Competition.sort_order, Competition.id).all()


def my_competitions(player):
    """Aktive Turniere, an denen player teilnimmt. Admins sehen alle aktiven
    Turniere, unabhaengig von einer eigenen Mitgliedschaft (sie tippen selbst
    nicht mit, verwalten aber jedes Turnier)."""
    if not player:
        return []
    if player.is_admin:
        return active_competitions()
    ids = {m.competition_id for m in Membership.query.filter_by(player_id=player.id, plays=True).all()}
    return [c for c in active_competitions() if c.id in ids]


def current_competition():
    """Aktuell aktives Turnier fuer den eingeloggten Spieler, oder None.

    - Genau 1 aktives Turnier insgesamt -> immer dieses (kein Umschalten noetig).
    - Sonst: aus der Session, sofern der Spieler dort Mitglied ist.
    - Fallback: erstes Turnier aus my_competitions(player).
    """
    from auth import current_player
    all_active = active_competitions()
    if len(all_active) == 1:
        return all_active[0]
    if not all_active:
        return None
    player = current_player()
    mine = my_competitions(player)
    if not mine:
        return None
    cid = session.get("cid")
    if cid:
        match = next((c for c in mine if c.id == cid), None)
        if match:
            return match
    return mine[0]


def require_competition():
    """Wie current_competition(), bricht aber mit 403 ab, wenn der eingeloggte
    Spieler (noch) keinem Turnier zugeordnet ist."""
    comp = current_competition()
    if not comp:
        abort(403, description="no-competition")
    return comp


def switch_competition(cid):
    """Setzt die aktive Competition in der Session, nur wenn der eingeloggte
    Spieler dort Mitglied ist (oder Admin ist). True bei Erfolg."""
    from auth import current_player
    player = current_player()
    if not player:
        return False
    if any(c.id == cid for c in my_competitions(player)):
        session["cid"] = cid
        return True
    return False
