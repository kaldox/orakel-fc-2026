# -*- coding: utf-8 -*-
"""
ORAKEL FC 2026 — selbst gehostetes WM-Tippspiel mit Jokern, Missionen,
Challenges, Sonderwertungen und Chaos-Events.

Diese Datei enthaelt nur noch das App-Setup: Konfiguration, Extension-Init,
Blueprint-Registrierung, App-weite Hooks (Error-Handler, Context-Processor,
Security-Header) sowie die Erststart-Befuellung (seed). Die eigentliche
Logik liegt in models.py, auth.py, scoring.py, settings.py, security.py,
i18n_helpers.py, catalog_config.py und routes/.
"""
import os

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFError
from werkzeug.security import generate_password_hash

from extensions import db, csrf
from models import Award, Challenge, ChaosEvent, JokerType, Mission, Player
from auth import current_player
from settings import is_simple
from security import apply_security_headers
from i18n_helpers import get_lang, t
from routes.public import public
from routes.admin import admin_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY ist nicht gesetzt. Bitte in der .env einen zufälligen Wert "
        "hinterlegen, z.B. erzeugt mit: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.config["SECRET_KEY"] = _secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DATA_DIR, "orakel.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Gehaertete Session-Cookies. SECURE erst aktivieren, wenn ueber HTTPS betrieben
# (per .env: COOKIE_SECURE=1) - sonst klappt lokales HTTP-Testen nicht.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
LEAGUE_NAME = os.environ.get("LEAGUE_NAME", "ORAKEL FC 2026")

db.init_app(app)
csrf.init_app(app)

app.register_blueprint(public)
app.register_blueprint(admin_bp)


@app.errorhandler(CSRFError)
def _handle_csrf(e):
    flash(t("Deine Sitzung ist abgelaufen. Bitte lade die Seite neu und versuch es erneut."), "error")
    return redirect(request.referrer or url_for("public.login"))


@app.context_processor
def inject_globals():
    return {"me": current_player(), "league_name": LEAGUE_NAME,
            "t": t, "lang": get_lang(), "simple_mode": is_simple()}


@app.after_request
def security_headers(resp):
    return apply_security_headers(resp)


def seed():
    db.create_all()
    if not Player.query.filter_by(is_admin=True).first():
        pw = os.environ.get("ADMIN_PASSWORD", "admin")
        db.session.add(Player(name=os.environ.get("ADMIN_NAME", "admin"),
                              pw_hash=generate_password_hash(pw), is_admin=True, plays=False))
        db.session.commit()
    if JokerType.query.count() == 0:
        for n, e, d, eff, mx in [
            ("Verdoppler", "✖️", "Verdoppelt deine Punkte aus einem gewählten Spiel.", "double", 2),
            ("Glücksjoker", "🍀", "0 Punkte an einem Spieltag? Trotzdem 3 Trostpunkte.", "lucky", 1),
            ("Comeback-Joker", "🚀", "Verdreifacht einen ganzen Spieltag (nur untere Tabellenhälfte).", "triple", 1),
            ("All-In", "🎲", "Tagesertrag auf 1 Spiel: Tendenz trifft ×3, sonst 0.", "allin", 1),
            ("Sabotage", "💣", "Halbiert die Tagespunkte eines Gegners.", "sabotage", 1),
            ("Schutzschild", "🛡️", "Einen Spieltag immun gegen Sabotage.", "shield", 1),
            ("Tausch-Joker", "🔁", "Dein schlechtester Spieltag zählt wie der Durchschnitt.", "swap", 1),
            ("Chaos-Joker", "🌀", "Spiel mit Remis/Eigentor/Rot → +5 (vom Admin gewertet).", "manual", 1),
        ]:
            db.session.add(JokerType(name=n, emoji=e, description=d, auto_effect=eff, max_per_player=mx))
        db.session.commit()
    if Mission.query.count() == 0:
        for n, e, d, pts in [
            ("Der Hellseher", "🔮", "Tippe ein exaktes Ergebnis in einem K.o.-Spiel.", 10),
            ("Underdog-Liebhaber", "🐶", "Tippe 3 Außenseiter-Siege, von denen einer eintritt.", 8),
            ("Der Trickser", "🎭", "Überrede jemanden, seinen Tipp zu ändern (Screenshot!).", 6),
            ("Das Großmaul", "📣", "Sag vorher ein exaktes Ergebnis an – triff die Tendenz.", 6),
            ("Das Comeback", "🏔️", "Sei einmal Letzter und steh am Finaltag in den Top 3.", 12),
            ("Der Sturkopf", "🐏", "Tippe 5 Spiele in Folge 2:1 (egal welche Seite).", 6),
            ("Der Meme-Lord", "😂", "Poste 3 Memes, die je 3+ Reaktionen kriegen.", 6),
            ("Kassandra", "🌀", "Kündige eine Überraschung öffentlich an – behalte recht.", 8),
            ("Der Zocker", "🎰", "Spiele 3 Risiko-Tipps und gewinne mindestens 2.", 8),
            ("Der Kaffeesatzleser", "☕", "Sage das Ergebnis des Eröffnungsspiels exakt voraus.", 10),
            ("Der Final-Prophet", "🏆", "Sage beide Finalisten schon vor Turnierstart voraus.", 12),
        ]:
            db.session.add(Mission(name=n, emoji=e, description=d, points=pts))
        db.session.commit()
    if Award.query.count() == 0:
        for n, e, d in [
            ("König der Überraschungen", "👑", "Meiste korrekt getippte Außenseiter-Siege."),
            ("Das WM-Orakel", "🔮", "Meiste exakte Ergebnisse."),
            ("Der Optimist", "☀️", "Tippt im Schnitt die meisten Tore."),
            ("Der Pechvogel", "🪦", "Lag am häufigsten um genau 1 Tor daneben."),
            ("Der Risiko-Kaiser", "🎯", "Meiste erfolgreiche Risiko-Tipps."),
            ("Trash-Talk-Champion", "🗣️", "Der frechste Spruch der Saison."),
            ("Der Meme-Meister", "😂", "Bestes Meme in der Gruppe."),
            ("Der Comeback-King", "🚀", "Größter Aufstieg vom Tiefpunkt bis zum Finale."),
            ("Das Joker-Genie", "🧠", "Holt mit Jokern die meisten Extrapunkte."),
            ("Die Goldene Niete", "🍟", "Ehrenpreis für den Letzten."),
        ]:
            db.session.add(Award(name=n, emoji=e, description=d))
        db.session.commit()
    if Challenge.query.count() == 0:
        for w, ti, d in [
            ("Woche 1", "Tore-Schätzung", "Gesamtzahl Tore am Eröffnungswochenende – nächster Wert gewinnt."),
            ("Woche 2", "Eigentor-Orakel", "In welchem Spiel fällt das nächste Eigentor?"),
            ("Woche 3", "Karten-König", "Team mit den meisten Karten der Woche."),
            ("Woche 4", "Penalty-Premiere", "Wann kommt das erste Elfmeterschießen?"),
            ("Woche 5", "Halbfinal-Kontinent", "Welcher Kontinent stellt die meisten Halbfinalisten?"),
            ("Woche 6", "Finale-Triple", "Endstand, Spieler des Turniers und Torschützenkönig."),
        ]:
            db.session.add(Challenge(week=w, title=ti, description=d, points=5))
        db.session.commit()
    if ChaosEvent.query.count() == 0:
        for n, e, d in [
            ("Glücksrad", "🎡", "Zufalls-Bonus, Gratis-Joker oder Strafaufgabe."),
            ("Zufalls-Jackpot", "💰", "Heute zählen ALLE Punkte doppelt."),
            ("Underdog-Tag", "🐶", "Außenseiter-Siege zählen heute doppelt."),
            ("Schwarzer Schwan", "🦢", "Ein Zufallsspiel zählt dreifach – erst nach Anpfiff verraten."),
            ("Joker-Regen", "☔", "Alle bekommen einen Gratis-Joker geschenkt."),
            ("Rache-Joker", "😈", "Der Letzte kriegt einen Sabotage-Joker."),
            ("Tabellen-Blackout", "🙈", "24 h sieht niemand die Tabelle."),
        ]:
            db.session.add(ChaosEvent(name=n, emoji=e, description=d))
        db.session.commit()


with app.app_context():
    seed()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8090)), debug=False)
