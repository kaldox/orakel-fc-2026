# -*- coding: utf-8 -*-
"""
Statische Konfiguration, die sowohl von oeffentlichen Routen (Hilfe-Seite,
Joker-Auswahl) als auch von den Admin-Routen (generischer Katalog-Editor)
gebraucht wird. Eigenes Modul, damit routes/public.py und routes/admin.py
sich nicht gegenseitig importieren muessen.
"""
from models import Award, Challenge, ChaosEvent, JokerType, Mission

EFFECTS = [("manual", "manuell (per Punkte-Anpassung)"),
           ("double", "Verdoppler – 1 Spiel ×2"),
           ("lucky", "Glücksjoker – 0-Tag wird 3"),
           ("triple", "Comeback – Spieltag ×3"),
           ("allin", "All-In – Tagesertrag auf 1 Spiel (×3 / 0)"),
           ("sabotage", "Sabotage – Tagespunkte des Ziels halbieren"),
           ("shield", "Schutzschild – immun gegen Sabotage"),
           ("swap", "Tausch – schlechtester Tag = Durchschnitt")]

# Klartext-Erklärungen je Joker-Effekt (ohne Fachbegriffe, fürs ℹ️ + Hilfe-Seite)
EFFECT_HELP = {
    "double":   "Such dir ein Spiel aus – deine Punkte aus diesem Spiel werden verdoppelt. Ideal, wenn du dir bei einem Spiel sicher bist.",
    "lucky":    "Holst du an einem Spieltag 0 Punkte, bekommst du trotzdem 3 Punkte geschenkt. Ein Sicherheitsnetz für schlechte Tage.",
    "triple":   "Verdreifacht alle deine Punkte eines kompletten Spieltags. Gedacht zum Aufholen, wenn du hinten liegst.",
    "allin":    "Alles auf einen Tag: Triffst du beim gewählten Spiel die Tendenz (Sieg/Unentschieden/Niederlage), zählt dein Tagesertrag dreifach – sonst gibt es an dem Tag 0 Punkte. Hohes Risiko, hohe Belohnung.",
    "sabotage": "Halbiere die Punkte eines Mitspielers an einem Spieltag deiner Wahl. Du wählst Ziel und Spieltag aus.",
    "shield":   "Schützt dich an einem Spieltag vor einer Sabotage. Greift dich jemand an, passiert nichts.",
    "swap":     "Dein schlechtester Spieltag wird automatisch durch deinen Durchschnitt ersetzt. Beispiel: Statt 2 Punkten an deinem schwächsten Tag zählen deine durchschnittlichen 9.",
    "manual":   "Such dir ein Spiel aus. Kommt darin ein Unentschieden, ein Eigentor oder eine Rote Karte vor, bekommst du +5 Punkte. Die Spielleitung prüft das nach dem Spiel.",
}

CATALOGS = {
    "jokers": {"model": JokerType, "title": "Joker", "icon": "JK",
               "fields": [("name", "Name", "text"), ("emoji", "Emoji", "text"),
                          ("description", "Beschreibung", "textarea"),
                          ("auto_effect", "Automatik-Effekt", "select", EFFECTS),
                          ("max_per_player", "Max. pro Person", "number"),
                          ("active", "Aktiv", "bool")]},
    "missions": {"model": Mission, "title": "Missionen", "icon": "MS",
                 "fields": [("name", "Name", "text"), ("emoji", "Emoji", "text"),
                            ("description", "Beschreibung", "textarea"),
                            ("points", "Bonuspunkte", "number"), ("active", "Aktiv", "bool")]},
    "challenges": {"model": Challenge, "title": "Wochen-Challenges", "icon": "CH",
                   "fields": [("week", "Woche", "text"), ("title", "Titel", "text"),
                              ("description", "Beschreibung", "textarea"),
                              ("points", "Punkte", "number"), ("active", "Aktiv", "bool")]},
    "awards": {"model": Award, "title": "Sonderwertungen", "icon": "AW",
               "fields": [("name", "Name", "text"), ("emoji", "Emoji", "text"),
                          ("description", "Beschreibung", "textarea")]},
    "chaos": {"model": ChaosEvent, "title": "Chaos-Events", "icon": "CX",
              "fields": [("name", "Name", "text"), ("emoji", "Emoji", "text"),
                         ("description", "Beschreibung", "textarea"),
                         ("active", "Gerade aktiv", "bool")]},
}


def coerce(ftype, raw):
    if ftype == "bool":
        return bool(raw)
    if ftype == "number":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return (raw or "").strip()
