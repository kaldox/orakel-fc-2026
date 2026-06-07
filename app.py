"""
ORAKEL FC 2026 — selbst gehostetes WM-Tippspiel mit Jokern, Missionen,
Challenges, Sonderwertungen und Chaos-Events.

Alles in einer Flask-App + SQLite. Die "Kataloge" (Joker, Missionen,
Challenges, Sonderwertungen, Chaos-Events) sind ueber den Admin-Bereich
frei erweiterbar - einfach neue Eintraege im Browser anlegen.
"""
import os
from datetime import datetime
from functools import wraps
from math import floor

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-please")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(DATA_DIR, "orakel.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Gehaertete Session-Cookies. SECURE erst aktivieren, wenn ueber HTTPS betrieben
# (per .env: COOKIE_SECURE=1) - sonst klappt lokales HTTP-Testen nicht.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
LEAGUE_NAME = os.environ.get("LEAGUE_NAME", "ORAKEL FC 2026")

db = SQLAlchemy(app)
sign = lambda x: (x > 0) - (x < 0)


class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    pw_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    plays = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matchday = db.Column(db.String(20), default="1")
    stage = db.Column(db.String(40), default="Gruppe")
    home = db.Column(db.String(60), nullable=False)
    away = db.Column(db.String(60), nullable=False)
    kickoff = db.Column(db.DateTime, nullable=False)
    home_goals = db.Column(db.Integer)
    away_goals = db.Column(db.Integer)
    is_knockout = db.Column(db.Boolean, default=False)
    surprise = db.Column(db.Boolean, default=False)
    finished = db.Column(db.Boolean, default=False)

    @property
    def has_result(self):
        return self.finished and self.home_goals is not None and self.away_goals is not None

    @property
    def locked(self):
        return datetime.now() >= self.kickoff


class Tip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=False)
    home = db.Column(db.Integer, nullable=False)
    away = db.Column(db.Integer, nullable=False)
    is_risk = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint("player_id", "match_id"),)


class JokerType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(8), default="")
    description = db.Column(db.Text, default="")
    auto_effect = db.Column(db.String(20), default="manual")
    max_per_player = db.Column(db.Integer, default=1)
    active = db.Column(db.Boolean, default=True)


class JokerPlay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    joker_type_id = db.Column(db.Integer, db.ForeignKey("joker_type.id"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"))
    matchday = db.Column(db.String(20))
    target_player_id = db.Column(db.Integer, db.ForeignKey("player.id"))
    note = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Mission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(8), default="")
    description = db.Column(db.Text, default="")
    points = db.Column(db.Integer, default=8)
    active = db.Column(db.Boolean, default=True)


class MissionAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey("mission.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)


class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.String(30), default="Woche 1")
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    points = db.Column(db.Integer, default=5)
    winner_player_id = db.Column(db.Integer, db.ForeignKey("player.id"))
    active = db.Column(db.Boolean, default=True)


class Award(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(8), default="")
    description = db.Column(db.Text, default="")
    winner_player_id = db.Column(db.Integer, db.ForeignKey("player.id"))


class ChaosEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(8), default="")
    description = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=False)
    activated_at = db.Column(db.DateTime)


class Adjustment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    matchday = db.Column(db.String(20))
    points = db.Column(db.Integer, default=0)
    reason = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def current_player():
    pid = session.get("pid")
    return db.session.get(Player, pid) if pid else None


def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if not current_player():
            return redirect(url_for("login", next=request.path))
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


@app.context_processor
def inject_globals():
    return {"me": current_player(), "league_name": LEAGUE_NAME}


@app.after_request
def security_headers(resp):
    """Sinnvolle Basis-Sicherheitsheader fuer alle Antworten. HSTS nur ueber
    HTTPS (erkannt am vom Reverse-Proxy gesetzten X-Forwarded-Proto)."""
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # Bewusst tolerante CSP: App nutzt Google Fonts und einige Inline-Styles/-Skripte.
    resp.headers.setdefault("Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'")
    if request.headers.get("X-Forwarded-Proto") == "https":
        resp.headers.setdefault("Strict-Transport-Security",
                                "max-age=31536000; includeSubDomains")
    return resp


def base_match_points(tip, match):
    correct = sign(tip.home - tip.away) == sign(match.home_goals - match.away_goals)
    if tip.home == match.home_goals and tip.away == match.away_goals:
        pts = 8
    elif correct and (tip.home - tip.away) == (match.home_goals - match.away_goals):
        pts = 5
    elif correct:
        pts = 3
    else:
        pts = 0
    if correct:
        if match.is_knockout:
            pts += 2
        if match.surprise:
            pts += 3
    if tip.is_risk:
        pts = pts * 2 if correct else -4
    return pts, correct


def compute_standings():
    players = Player.query.filter_by(plays=True).all()
    matches = {m.id: m for m in Match.query.all()}
    finished = [m for m in matches.values() if m.has_result]
    tips = {(t.player_id, t.match_id): t for t in Tip.query.all()}
    plays = JokerPlay.query.all()

    double_at, allin_at, triple_at = {}, {}, set()
    swap_for, sabotaged, shielded, lucky_at = set(), set(), set(), set()
    effect = {j.id: j.auto_effect for j in JokerType.query.all()}
    for p in plays:
        eff = effect.get(p.joker_type_id, "manual")
        if eff == "double" and p.match_id:
            double_at[(p.player_id, p.match_id)] = True
        elif eff == "allin" and p.match_id:
            m = matches.get(p.match_id)
            if m:
                allin_at[(p.player_id, m.matchday)] = p.match_id
        elif eff == "triple" and p.matchday:
            triple_at.add((p.player_id, p.matchday))
        elif eff == "swap":
            swap_for.add(p.player_id)
        elif eff == "sabotage" and p.target_player_id and p.matchday:
            sabotaged.add((p.target_player_id, p.matchday))
        elif eff == "shield" and p.matchday:
            shielded.add((p.player_id, p.matchday))
        elif eff == "lucky" and p.matchday:
            lucky_at.add((p.player_id, p.matchday))

    rows, daydata = [], {}
    for p in players:
        tips_total, per_day = 0, {}
        for m in finished:
            t = tips.get((p.id, m.id))
            if not t:
                continue
            pts, _ = base_match_points(t, m)
            tips_total += pts
            day_pts = pts * (2 if double_at.get((p.id, m.id)) else 1)
            per_day[m.matchday] = per_day.get(m.matchday, 0) + day_pts
        final_day = {}
        for md, dpts in per_day.items():
            day = dpts
            mid = allin_at.get((p.id, md))
            if mid:
                m = matches.get(mid)
                t = tips.get((p.id, mid))
                ok = bool(m and t and sign(t.home - t.away) == sign(m.home_goals - m.away_goals))
                day = day * 3 if ok else 0
            if (p.id, md) in triple_at:
                day *= 3
            if (p.id, md) in sabotaged and (p.id, md) not in shielded:
                day = floor(day / 2)
            if (p.id, md) in lucky_at and day <= 0:
                day = 3
            final_day[md] = day
        daydata[p.id] = final_day
        rows.append({"player": p, "tips": tips_total})

    for pid in swap_for:
        fd = daydata.get(pid, {})
        if not fd:
            continue
        worst_md = min(fd, key=lambda k: fd[k])
        vals = [daydata[o.id][worst_md] for o in players if worst_md in daydata.get(o.id, {})]
        if vals:
            fd[worst_md] = round(sum(vals) / len(vals))

    miss = {}
    for a in MissionAssignment.query.filter_by(completed=True).all():
        m = db.session.get(Mission, a.mission_id)
        if m:
            miss[a.player_id] = miss.get(a.player_id, 0) + m.points
    chal = {}
    for c in Challenge.query.filter(Challenge.winner_player_id.isnot(None)).all():
        chal[c.winner_player_id] = chal.get(c.winner_player_id, 0) + c.points
    adj = {}
    for a in Adjustment.query.all():
        adj[a.player_id] = adj.get(a.player_id, 0) + a.points

    for r in rows:
        pid = r["player"].id
        engine = sum(daydata.get(pid, {}).values())
        r["joker"] = engine - r["tips"]
        r["missions"] = miss.get(pid, 0)
        r["challenges"] = chal.get(pid, 0)
        r["adjust"] = adj.get(pid, 0)
        r["total"] = engine + r["missions"] + r["challenges"] + r["adjust"]
    rows.sort(key=lambda r: r["total"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pw = request.form.get("password", "")
        p = Player.query.filter_by(name=name).first()
        if p and check_password_hash(p.pw_hash, pw):
            session["pid"] = p.id
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Name oder Passwort stimmt nicht.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    rows = compute_standings()
    me = current_player()
    my_mission = None
    a = MissionAssignment.query.filter_by(player_id=me.id).first()
    if a:
        my_mission = (db.session.get(Mission, a.mission_id), a)
    my_jokers = JokerPlay.query.filter_by(player_id=me.id).all()
    chaos = ChaosEvent.query.filter_by(active=True).all()
    return render_template("dashboard.html", rows=rows, my_mission=my_mission,
                           my_jokers=my_jokers, chaos=chaos,
                           joker_types={j.id: j for j in JokerType.query.all()},
                           matches={m.id: m for m in Match.query.all()})


@app.route("/tips", methods=["GET", "POST"])
@login_required
def tips():
    me = current_player()
    if request.method == "POST":
        mid = int(request.form["match_id"])
        m = db.session.get(Match, mid)
        if not m:
            abort(404)
        if m.locked:
            flash("Anpfiff vorbei – dieser Tipp ist gesperrt.", "error")
            return redirect(url_for("tips"))
        try:
            h = int(request.form["home"]); a = int(request.form["away"])
        except (ValueError, KeyError):
            flash("Bitte gültige Zahlen eintippen.", "error")
            return redirect(url_for("tips"))
        risk = bool(request.form.get("risk"))
        t = Tip.query.filter_by(player_id=me.id, match_id=mid).first()
        if not t:
            t = Tip(player_id=me.id, match_id=mid)
            db.session.add(t)
        t.home, t.away, t.is_risk = max(0, h), max(0, a), risk
        if risk:
            for other in Tip.query.filter_by(player_id=me.id, is_risk=True).all():
                om = db.session.get(Match, other.match_id)
                if other.id != t.id and om and om.matchday == m.matchday:
                    other.is_risk = False
        db.session.commit()
        flash("Tipp gespeichert.", "ok")
        return redirect(url_for("tips") + ("#m%d" % mid))

    all_matches = Match.query.order_by(Match.kickoff, Match.id).all()
    mytips = {t.match_id: t for t in Tip.query.filter_by(player_id=me.id).all()}
    groups = {}
    for m in all_matches:
        groups.setdefault(m.matchday, []).append(m)
    return render_template("tips.html", groups=groups, mytips=mytips, now=datetime.now())


@app.route("/jokers", methods=["GET", "POST"])
@login_required
def jokers():
    me = current_player()
    if request.method == "POST":
        jt = db.session.get(JokerType, int(request.form["joker_type_id"]))
        if not jt or not jt.active:
            abort(404)
        used = JokerPlay.query.filter_by(player_id=me.id, joker_type_id=jt.id).count()
        if used >= jt.max_per_player:
            flash("Joker '%s' ist aufgebraucht." % jt.name, "error")
            return redirect(url_for("jokers"))
        play = JokerPlay(player_id=me.id, joker_type_id=jt.id,
                         note=request.form.get("note", "")[:200])
        mid = request.form.get("match_id")
        if mid:
            play.match_id = int(mid)
            mm = db.session.get(Match, int(mid))
            if mm:
                play.matchday = mm.matchday
        if request.form.get("matchday"):
            play.matchday = request.form["matchday"]
        if request.form.get("target_player_id"):
            play.target_player_id = int(request.form["target_player_id"])
        db.session.add(play)
        db.session.commit()
        flash("Joker '%s' aktiviert." % jt.name, "ok")
        return redirect(url_for("jokers"))

    types = JokerType.query.filter_by(active=True).order_by(JokerType.id).all()
    used = {}
    for jp in JokerPlay.query.filter_by(player_id=me.id).all():
        used[jp.joker_type_id] = used.get(jp.joker_type_id, 0) + 1
    upcoming = Match.query.filter(Match.kickoff > datetime.now()).order_by(Match.kickoff).all()
    matchdays = [r[0] for r in db.session.query(Match.matchday).distinct().all()]
    opponents = Player.query.filter(Player.plays == True, Player.id != me.id).all()
    return render_template("jokers.html", types=types, used=used, upcoming=upcoming,
                           matchdays=sorted(matchdays), opponents=opponents,
                           myplays=JokerPlay.query.filter_by(player_id=me.id).all(),
                           jt_map={j.id: j for j in JokerType.query.all()},
                           m_map={m.id: m for m in Match.query.all()},
                           help=EFFECT_HELP)


@app.route("/missions")
@login_required
def missions():
    me = current_player()
    a = MissionAssignment.query.filter_by(player_id=me.id).first()
    mine = (db.session.get(Mission, a.mission_id), a) if a else None
    catalog = Mission.query.filter_by(active=True).order_by(Mission.id).all()
    return render_template("missions.html", mine=mine, catalog=catalog)


@app.route("/challenges")
@login_required
def challenges():
    items = Challenge.query.order_by(Challenge.id).all()
    return render_template("challenges.html", items=items,
                           pmap={p.id: p.name for p in Player.query.all()})


@app.route("/awards")
@login_required
def awards():
    items = Award.query.order_by(Award.id).all()
    return render_template("awards.html", items=items,
                           pmap={p.id: p.name for p in Player.query.all()})


@app.route("/passwort", methods=["GET", "POST"])
@login_required
def passwort():
    me = current_player()
    if request.method == "POST":
        cur = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")
        if not check_password_hash(me.pw_hash, cur):
            flash("Dein aktuelles Passwort stimmt nicht.", "error")
        elif len(new) < 6:
            flash("Das neue Passwort muss mindestens 6 Zeichen haben.", "error")
        elif new != confirm:
            flash("Die beiden neuen Passwörter stimmen nicht überein.", "error")
        else:
            me.pw_hash = generate_password_hash(new)
            db.session.commit()
            flash("Passwort geändert. ✓", "ok")
            return redirect(url_for("passwort"))
    return render_template("passwort.html")


@app.route("/hilfe")
@login_required
def hilfe():
    jokers = JokerType.query.filter_by(active=True).order_by(JokerType.id).all()
    return render_template("hilfe.html", jokers=jokers, help=EFFECT_HELP)


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


def _coerce(ftype, raw):
    if ftype == "bool":
        return bool(raw)
    if ftype == "number":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return (raw or "").strip()


@app.route("/admin/catalog/<kind>", methods=["GET", "POST"])
@admin_required
def admin_catalog(kind):
    cfg = CATALOGS.get(kind)
    if not cfg:
        abort(404)
    Model = cfg["model"]
    if request.method == "POST":
        if request.form.get("action") == "delete":
            obj = db.session.get(Model, int(request.form["id"]))
            if obj:
                db.session.delete(obj); db.session.commit()
                flash("Gelöscht.", "ok")
            return redirect(url_for("admin_catalog", kind=kind))
        oid = request.form.get("id")
        obj = db.session.get(Model, int(oid)) if oid else Model()
        for name, _label, ftype, *rest in cfg["fields"]:
            setattr(obj, name, _coerce(ftype, request.form.get(name)))
        if not oid:
            db.session.add(obj)
        db.session.commit()
        flash("Gespeichert.", "ok")
        return redirect(url_for("admin_catalog", kind=kind))
    items = Model.query.order_by(Model.id).all()
    edit = db.session.get(Model, int(request.args["edit"])) if request.args.get("edit") else None
    return render_template("admin_catalog.html", kind=kind, cfg=cfg, items=items,
                           edit=edit, catalogs=CATALOGS,
                           pmap={p.id: p.name for p in Player.query.all()},
                           players=Player.query.filter_by(plays=True).all())


@app.route("/admin")
@admin_required
def admin_home():
    stats = {"players": Player.query.filter_by(plays=True).count(),
             "matches": Match.query.count(),
             "finished": Match.query.filter_by(finished=True).count(),
             "jokers": JokerType.query.count(),
             "missions": Mission.query.count()}
    return render_template("admin_home.html", stats=stats, catalogs=CATALOGS)


@app.route("/admin/players", methods=["GET", "POST"])
@admin_required
def admin_players():
    if request.method == "POST":
        if request.form.get("action") == "delete":
            p = db.session.get(Player, int(request.form["id"]))
            if p and p.id != session.get("pid"):
                db.session.delete(p); db.session.commit()
            return redirect(url_for("admin_players"))
        if request.form.get("action") == "resetpw":
            p = db.session.get(Player, int(request.form["id"]))
            newpw = request.form.get("password", "")
            if p and len(newpw) >= 6:
                p.pw_hash = generate_password_hash(newpw)
                db.session.commit()
                flash("Neues Passwort für %s gesetzt." % p.name, "ok")
            elif p:
                flash("Neues Passwort braucht mindestens 6 Zeichen.", "error")
            return redirect(url_for("admin_players"))
        name = request.form.get("name", "").strip()
        pw = request.form.get("password", "")
        if name and pw:
            if Player.query.filter_by(name=name).first():
                flash("Name existiert schon.", "error")
            else:
                db.session.add(Player(name=name, pw_hash=generate_password_hash(pw),
                                      is_admin=bool(request.form.get("is_admin")),
                                      plays=bool(request.form.get("plays", "on"))))
                db.session.commit()
                flash("Spieler:in angelegt.", "ok")
        return redirect(url_for("admin_players"))
    return render_template("admin_players.html", players=Player.query.order_by(Player.id).all())


@app.route("/admin/matches", methods=["GET", "POST"])
@admin_required
def admin_matches():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            m = db.session.get(Match, int(request.form["id"]))
            if m:
                Tip.query.filter_by(match_id=m.id).delete()
                db.session.delete(m); db.session.commit()
            return redirect(url_for("admin_matches"))
        try:
            kickoff = datetime.strptime(request.form["kickoff"], "%Y-%m-%dT%H:%M")
        except (ValueError, KeyError):
            flash("Ungültiger Anpfiff-Zeitpunkt.", "error")
            return redirect(url_for("admin_matches"))
        if action == "edit":
            m = db.session.get(Match, int(request.form["id"]))
            if m:
                m.home = request.form["home"].strip()
                m.away = request.form["away"].strip()
                m.kickoff = kickoff
                m.matchday = request.form.get("matchday", "1").strip() or "1"
                m.stage = request.form.get("stage", "Gruppe").strip() or "Gruppe"
                m.is_knockout = bool(request.form.get("is_knockout"))
                db.session.commit()
                flash("Spiel aktualisiert.", "ok")
            return redirect(url_for("admin_matches"))
        db.session.add(Match(matchday=request.form.get("matchday", "1").strip() or "1",
                             stage=request.form.get("stage", "Gruppe").strip() or "Gruppe",
                             home=request.form["home"].strip(), away=request.form["away"].strip(),
                             kickoff=kickoff, is_knockout=bool(request.form.get("is_knockout"))))
        db.session.commit()
        flash("Spiel angelegt.", "ok")
        return redirect(url_for("admin_matches"))
    matches = Match.query.order_by(Match.kickoff, Match.id).all()
    edit = db.session.get(Match, int(request.args["edit"])) if request.args.get("edit") else None
    return render_template("admin_matches.html", matches=matches, edit=edit)


@app.route("/admin/matches/import", methods=["POST"])
@admin_required
def admin_matches_import():
    import json
    try:
        data = json.loads(request.form.get("payload", "[]"))
        n = 0
        for row in data:
            db.session.add(Match(home=row["home"], away=row["away"],
                                 kickoff=datetime.strptime(row["kickoff"], "%Y-%m-%dT%H:%M"),
                                 matchday=str(row.get("matchday", "1")),
                                 stage=row.get("stage", "Gruppe"),
                                 is_knockout=bool(row.get("knockout", False))))
            n += 1
        db.session.commit()
        flash("%d Spiele importiert." % n, "ok")
    except Exception as e:
        flash("Import fehlgeschlagen: %s" % e, "error")
    return redirect(url_for("admin_matches"))


@app.route("/admin/result/<int:mid>", methods=["POST"])
@admin_required
def admin_result(mid):
    m = db.session.get(Match, mid)
    if not m:
        abort(404)
    try:
        m.home_goals = int(request.form["home_goals"])
        m.away_goals = int(request.form["away_goals"])
        m.finished = True
    except (ValueError, KeyError):
        m.home_goals = m.away_goals = None
        m.finished = False
    m.surprise = bool(request.form.get("surprise"))
    m.is_knockout = bool(request.form.get("is_knockout"))
    db.session.commit()
    flash("Ergebnis gespeichert.", "ok")
    return redirect(url_for("admin_matches"))


@app.route("/admin/assign", methods=["GET", "POST"])
@admin_required
def admin_assign():
    if request.method == "POST":
        if request.form.get("action") == "assign":
            pid = int(request.form["player_id"]); mid = int(request.form["mission_id"])
            a = MissionAssignment.query.filter_by(player_id=pid).first()
            if not a:
                a = MissionAssignment(player_id=pid); db.session.add(a)
            a.mission_id = mid; a.completed = False
            db.session.commit()
            flash("Mission zugewiesen.", "ok")
        elif request.form.get("action") == "toggle":
            a = db.session.get(MissionAssignment, int(request.form["id"]))
            if a:
                a.completed = not a.completed; db.session.commit()
        return redirect(url_for("admin_assign"))
    return render_template("admin_assign.html",
                           players=Player.query.filter_by(plays=True).all(),
                           missions=Mission.query.filter_by(active=True).all(),
                           assignments=MissionAssignment.query.all(),
                           pmap={p.id: p.name for p in Player.query.all()},
                           mmap={m.id: m for m in Mission.query.all()})


@app.route("/admin/winner/<kind>/<int:oid>", methods=["POST"])
@admin_required
def admin_winner(kind, oid):
    Model = {"challenges": Challenge, "awards": Award}.get(kind)
    if not Model:
        abort(404)
    obj = db.session.get(Model, oid)
    if obj:
        val = request.form.get("winner_player_id")
        obj.winner_player_id = int(val) if val else None
        db.session.commit()
        flash("Gewinner:in gesetzt.", "ok")
    return redirect(url_for("admin_catalog", kind=kind))


@app.route("/admin/adjustments", methods=["GET", "POST"])
@admin_required
def admin_adjustments():
    if request.method == "POST":
        if request.form.get("action") == "delete":
            a = db.session.get(Adjustment, int(request.form["id"]))
            if a:
                db.session.delete(a); db.session.commit()
            return redirect(url_for("admin_adjustments"))
        try:
            pts = int(request.form["points"])
        except (ValueError, KeyError):
            pts = 0
        db.session.add(Adjustment(player_id=int(request.form["player_id"]), points=pts,
                                  matchday=request.form.get("matchday", "").strip() or None,
                                  reason=request.form.get("reason", "")[:200]))
        db.session.commit()
        flash("Anpassung gespeichert.", "ok")
        return redirect(url_for("admin_adjustments"))
    return render_template("admin_adjustments.html",
                           players=Player.query.filter_by(plays=True).all(),
                           items=Adjustment.query.order_by(Adjustment.id.desc()).all(),
                           pmap={p.id: p.name for p in Player.query.all()})


@app.route("/admin/jokerplays", methods=["GET", "POST"])
@admin_required
def admin_jokerplays():
    if request.method == "POST" and request.form.get("action") == "delete":
        jp = db.session.get(JokerPlay, int(request.form["id"]))
        if jp:
            db.session.delete(jp); db.session.commit()
        return redirect(url_for("admin_jokerplays"))
    return render_template("admin_jokerplays.html",
                           plays=JokerPlay.query.order_by(JokerPlay.id.desc()).all(),
                           jt={j.id: j for j in JokerType.query.all()},
                           pm={p.id: p.name for p in Player.query.all()},
                           mm={m.id: m for m in Match.query.all()})


@app.route("/admin/chaos/<int:cid>/toggle", methods=["POST"])
@admin_required
def admin_chaos_toggle(cid):
    c = db.session.get(ChaosEvent, cid)
    if c:
        c.active = not c.active
        c.activated_at = datetime.utcnow() if c.active else None
        db.session.commit()
    return redirect(url_for("admin_catalog", kind="chaos"))


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
        for w, t, d in [
            ("Woche 1", "Tore-Schätzung", "Gesamtzahl Tore am Eröffnungswochenende – nächster Wert gewinnt."),
            ("Woche 2", "Eigentor-Orakel", "In welchem Spiel fällt das nächste Eigentor?"),
            ("Woche 3", "Karten-König", "Team mit den meisten Karten der Woche."),
            ("Woche 4", "Penalty-Premiere", "Wann kommt das erste Elfmeterschießen?"),
            ("Woche 5", "Halbfinal-Kontinent", "Welcher Kontinent stellt die meisten Halbfinalisten?"),
            ("Woche 6", "Finale-Triple", "Endstand, Spieler des Turniers und Torschützenkönig."),
        ]:
            db.session.add(Challenge(week=w, title=t, description=d, points=5))
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8090)), debug=True)
