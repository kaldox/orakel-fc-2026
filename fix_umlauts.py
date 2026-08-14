#!/usr/bin/env python3
"""
Einmalige Migration: aktualisiert die urspruenglich angelegten Katalog-Eintraege
(Joker, Missionen, Sonderwertungen, Challenges, Chaos-Events) von der alten
ASCII-Schreibweise auf echte Umlaute + Emojis.

Sicher & idempotent:
- Joker werden ueber ihren stabilen Effekt (auto_effect) gefunden.
- Missionen/Awards/Chaos/Challenges ueber ihren bisherigen (alten) Namen/Titel.
- Eigene, selbst angelegte Eintraege und bereits umbenannte werden NICHT angefasst.
- Spiele, Spieler, Tipps, Zuweisungen bleiben unveraendert.

Aufruf (im laufenden Container):
    docker compose exec orakel-fc python fix_umlauts.py
"""
from app import (app, db, JokerType, Mission, Award, Challenge, ChaosEvent)

# Joker: Schluessel = auto_effect  ->  (Name, Emoji, Beschreibung)
JOKERS = {
    "double":   ("Verdoppler",     "✖️", "Verdoppelt deine Punkte aus einem gewählten Spiel."),
    "lucky":    ("Glücksjoker",    "🍀", "0 Punkte an einem Spieltag? Trotzdem 3 Trostpunkte."),
    "triple":   ("Comeback-Joker", "🚀", "Verdreifacht einen ganzen Spieltag (nur untere Tabellenhälfte)."),
    "allin":    ("All-In",         "🎲", "Tagesertrag auf 1 Spiel: Tendenz trifft ×3, sonst 0."),
    "sabotage": ("Sabotage",       "💣", "Halbiert die Tagespunkte eines Gegners."),
    "shield":   ("Schutzschild",   "🛡️", "Einen Spieltag immun gegen Sabotage."),
    "swap":     ("Tausch-Joker",   "🔁", "Dein schlechtester Spieltag zählt wie der Durchschnitt."),
    "manual":   ("Chaos-Joker",    "🌀", "Spiel mit Remis/Eigentor/Rot → +5 (vom Admin gewertet)."),
}

# Missionen: Schluessel = alter Name  ->  (neuer Name, Emoji, Beschreibung, Punkte)
MISSIONS = {
    "Der Hellseher":        ("Der Hellseher",        "🔮", "Tippe ein exaktes Ergebnis in einem K.o.-Spiel.", 10),
    "Underdog-Liebhaber":   ("Underdog-Liebhaber",   "🐶", "Tippe 3 Außenseiter-Siege, von denen einer eintritt.", 8),
    "Der Trickser":         ("Der Trickser",         "🎭", "Überrede jemanden, seinen Tipp zu ändern (Screenshot!).", 6),
    "Das Grossmaul":        ("Das Großmaul",         "📣", "Sag vorher ein exaktes Ergebnis an – triff die Tendenz.", 6),
    "Das Comeback":         ("Das Comeback",         "🏔️", "Sei einmal Letzter und steh am Finaltag in den Top 3.", 12),
    "Der Sturkopf":         ("Der Sturkopf",         "🐏", "Tippe 5 Spiele in Folge 2:1 (egal welche Seite).", 6),
    "Der Meme-Lord":        ("Der Meme-Lord",        "😂", "Poste 3 Memes, die je 3+ Reaktionen kriegen.", 6),
    "Kassandra":            ("Kassandra",            "🌀", "Kündige eine Überraschung öffentlich an – behalte recht.", 8),
    "Der Zocker":           ("Der Zocker",           "🎰", "Spiele 3 Risiko-Tipps und gewinne mindestens 2.", 8),
    "Der Kaffeesatzleser":  ("Der Kaffeesatzleser",  "☕", "Sage das Ergebnis des Eröffnungsspiels exakt voraus.", 10),
    "Der Final-Prophet":    ("Der Final-Prophet",    "🏆", "Sage beide Finalisten schon vor Turnierstart voraus.", 12),
}

# Awards: Schluessel = alter Name  ->  (neuer Name, Emoji, Beschreibung)
AWARDS = {
    "Koenig der Ueberraschungen": ("König der Überraschungen", "👑", "Meiste korrekt getippte Außenseiter-Siege."),
    "Das WM-Orakel":              ("Das WM-Orakel",            "🔮", "Meiste exakte Ergebnisse."),
    "Der Optimist":               ("Der Optimist",             "☀️", "Tippt im Schnitt die meisten Tore."),
    "Der Pechvogel":              ("Der Pechvogel",            "🪦", "Lag am häufigsten um genau 1 Tor daneben."),
    "Der Risiko-Kaiser":          ("Der Risiko-Kaiser",        "🎯", "Meiste erfolgreiche Risiko-Tipps."),
    "Trash-Talk-Champion":        ("Trash-Talk-Champion",      "🗣️", "Der frechste Spruch der Saison."),
    "Der Meme-Meister":           ("Der Meme-Meister",         "😂", "Bestes Meme in der Gruppe."),
    "Der Comeback-King":          ("Der Comeback-King",        "🚀", "Größter Aufstieg vom Tiefpunkt bis zum Finale."),
    "Das Joker-Genie":            ("Das Joker-Genie",          "🧠", "Holt mit Jokern die meisten Extrapunkte."),
    "Die Goldene Niete":          ("Die Goldene Niete",        "🍟", "Ehrenpreis für den Letzten."),
}

# Challenges: Schluessel = alter Titel  ->  (neuer Titel, Beschreibung)
CHALLENGES = {
    "Tore-Schaetzung":     ("Tore-Schätzung",     "Gesamtzahl Tore am Eröffnungswochenende – nächster Wert gewinnt."),
    "Eigentor-Orakel":     ("Eigentor-Orakel",    "In welchem Spiel fällt das nächste Eigentor?"),
    "Karten-Koenig":       ("Karten-König",       "Team mit den meisten Karten der Woche."),
    "Penalty-Premiere":    ("Penalty-Premiere",   "Wann kommt das erste Elfmeterschießen?"),
    "Halbfinal-Kontinent": ("Halbfinal-Kontinent","Welcher Kontinent stellt die meisten Halbfinalisten?"),
    "Finale-Triple":       ("Finale-Triple",      "Endstand, Spieler des Turniers und Torschützenkönig."),
}

# Chaos-Events: Schluessel = alter Name  ->  (neuer Name, Emoji, Beschreibung)
CHAOS = {
    "Gluecksrad":        ("Glücksrad",         "🎡", "Zufalls-Bonus, Gratis-Joker oder Strafaufgabe."),
    "Zufalls-Jackpot":   ("Zufalls-Jackpot",   "💰", "Heute zählen ALLE Punkte doppelt."),
    "Underdog-Tag":      ("Underdog-Tag",      "🐶", "Außenseiter-Siege zählen heute doppelt."),
    "Schwarzer Schwan":  ("Schwarzer Schwan",  "🦢", "Ein Zufallsspiel zählt dreifach – erst nach Anpfiff verraten."),
    "Joker-Regen":       ("Joker-Regen",       "☔", "Alle bekommen einen Gratis-Joker geschenkt."),
    "Rache-Joker":       ("Rache-Joker",       "😈", "Der Letzte kriegt einen Sabotage-Joker."),
    "Tabellen-Blackout": ("Tabellen-Blackout", "🙈", "24 h sieht niemand die Tabelle."),
}


def _apply(obj, name, emoji, desc, points=None, name_attr="name"):
    """Setzt Felder und meldet, ob sich tatsaechlich etwas geaendert hat."""
    changed = False
    if getattr(obj, name_attr) != name:
        setattr(obj, name_attr, name); changed = True
    if emoji is not None and obj.emoji != emoji:
        obj.emoji = emoji; changed = True
    if desc is not None and obj.description != desc:
        obj.description = desc; changed = True
    if points is not None and getattr(obj, "points", None) != points:
        obj.points = points; changed = True
    return changed


def migrate():
    n = 0
    # Joker ueber auto_effect
    for eff, (name, emoji, desc) in JOKERS.items():
        for j in JokerType.query.filter_by(auto_effect=eff).all():
            if _apply(j, name, emoji, desc):
                n += 1
    # Missionen ueber alten Namen
    for old, (name, emoji, desc, pts) in MISSIONS.items():
        m = Mission.query.filter_by(name=old).first()
        if m and _apply(m, name, emoji, desc, points=pts):
            n += 1
    # Awards ueber alten Namen
    for old, (name, emoji, desc) in AWARDS.items():
        a = Award.query.filter_by(name=old).first()
        if a and _apply(a, name, emoji, desc):
            n += 1
    # Challenges ueber alten Titel
    for old, (title, desc) in CHALLENGES.items():
        c = Challenge.query.filter_by(title=old).first()
        if c and _apply(c, title, None, desc, name_attr="title"):
            n += 1
    # Chaos ueber alten Namen
    for old, (name, emoji, desc) in CHAOS.items():
        c = ChaosEvent.query.filter_by(name=old).first()
        if c and _apply(c, name, emoji, desc):
            n += 1
    db.session.commit()
    return n


if __name__ == "__main__":
    with app.app_context():
        changed = migrate()
    if changed:
        print("Fertig: %d Eintraege auf Umlaute + Emojis aktualisiert." % changed)
    else:
        print("Nichts zu tun - alles bereits aktuell (oder eigene Eintraege).")
