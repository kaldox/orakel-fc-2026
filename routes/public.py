# -*- coding: utf-8 -*-
"""Oeffentliche Routen (fuer eingeloggte Spieler, nicht Admin-spezifisch)."""
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import (ChaosEvent, JokerPlay, JokerType, Match, Mission,
                     MissionAssignment, Player, Tip, Award, Challenge)
from auth import (current_player, login_required, _bf_locked, _bf_record,
                  _bf_clear, _safe_next_target)
from settings import is_simple
from scoring import compute_standings
from i18n_helpers import t
from catalog_config import EFFECT_HELP

public = Blueprint("public", __name__)


@public.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pw = request.form.get("password", "")
        if name and _bf_locked(name):
            flash(t("Zu viele Fehlversuche. Bitte warte ein paar Minuten und versuch es erneut."), "error")
            return render_template("login.html")
        p = Player.query.filter_by(name=name).first()
        if p and check_password_hash(p.pw_hash, pw):
            _bf_clear(name)
            session["pid"] = p.id
            target = _safe_next_target(request.args.get("next")) or url_for("public.dashboard")
            return redirect(target)
        if name:
            _bf_record(name)
        flash(t("Name oder Passwort stimmt nicht."), "error")
    return render_template("login.html")


@public.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.login"))


@public.route("/")
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


@public.route("/tips", methods=["GET", "POST"])
@login_required
def tips():
    me = current_player()
    if request.method == "POST":
        mid = int(request.form["match_id"])
        m = db.session.get(Match, mid)
        if not m:
            abort(404)
        if m.locked:
            flash(t("Anpfiff vorbei – dieser Tipp ist gesperrt."), "error")
            return redirect(url_for("public.tips"))
        try:
            h = int(request.form["home"]); a = int(request.form["away"])
        except (ValueError, KeyError):
            flash(t("Bitte gültige Zahlen eintippen."), "error")
            return redirect(url_for("public.tips"))
        risk = bool(request.form.get("risk"))
        tp = Tip.query.filter_by(player_id=me.id, match_id=mid).first()
        if not tp:
            tp = Tip(player_id=me.id, match_id=mid)
            db.session.add(tp)
        tp.home, tp.away, tp.is_risk = max(0, h), max(0, a), risk
        if risk:
            for other in Tip.query.filter_by(player_id=me.id, is_risk=True).all():
                om = db.session.get(Match, other.match_id)
                if other.id != tp.id and om and om.matchday == m.matchday:
                    other.is_risk = False
        db.session.commit()
        flash(t("Tipp gespeichert."), "ok")
        return redirect(url_for("public.tips") + ("#m%d" % mid))

    all_matches = Match.query.order_by(Match.kickoff, Match.id).all()
    mytips = {tp.match_id: tp for tp in Tip.query.filter_by(player_id=me.id).all()}
    groups = {}
    for m in all_matches:
        groups.setdefault(m.matchday, []).append(m)
    return render_template("tips.html", groups=groups, mytips=mytips, now=datetime.now())


@public.route("/jokers", methods=["GET", "POST"])
@login_required
def jokers():
    if is_simple():
        return redirect(url_for("public.dashboard"))
    me = current_player()
    if request.method == "POST":
        jt = db.session.get(JokerType, int(request.form["joker_type_id"]))
        if not jt or not jt.active:
            abort(404)
        used = JokerPlay.query.filter_by(player_id=me.id, joker_type_id=jt.id).count()
        if used >= jt.max_per_player:
            flash(t("Joker '{n}' ist aufgebraucht.", n=jt.name), "error")
            return redirect(url_for("public.jokers"))
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
        flash(t("Joker '{n}' aktiviert.", n=jt.name), "ok")
        return redirect(url_for("public.jokers"))

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


@public.route("/missions")
@login_required
def missions():
    if is_simple():
        return redirect(url_for("public.dashboard"))
    me = current_player()
    a = MissionAssignment.query.filter_by(player_id=me.id).first()
    mine = (db.session.get(Mission, a.mission_id), a) if a else None
    catalog = Mission.query.filter_by(active=True).order_by(Mission.id).all()
    return render_template("missions.html", mine=mine, catalog=catalog)


@public.route("/challenges")
@login_required
def challenges():
    if is_simple():
        return redirect(url_for("public.dashboard"))
    items = Challenge.query.order_by(Challenge.id).all()
    return render_template("challenges.html", items=items,
                           pmap={p.id: p.name for p in Player.query.all()})


@public.route("/awards")
@login_required
def awards():
    if is_simple():
        return redirect(url_for("public.dashboard"))
    items = Award.query.order_by(Award.id).all()
    return render_template("awards.html", items=items,
                           pmap={p.id: p.name for p in Player.query.all()})


@public.route("/passwort", methods=["GET", "POST"])
@login_required
def passwort():
    me = current_player()
    if request.method == "POST":
        cur = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")
        if not check_password_hash(me.pw_hash, cur):
            flash(t("Dein aktuelles Passwort stimmt nicht."), "error")
        elif len(new) < 6:
            flash(t("Das neue Passwort muss mindestens 6 Zeichen haben."), "error")
        elif new != confirm:
            flash(t("Die beiden neuen Passwörter stimmen nicht überein."), "error")
        else:
            me.pw_hash = generate_password_hash(new)
            db.session.commit()
            flash(t("Passwort geändert. ✓"), "ok")
            return redirect(url_for("public.passwort"))
    return render_template("passwort.html")


@public.route("/hilfe")
@login_required
def hilfe():
    jokers_list = JokerType.query.filter_by(active=True).order_by(JokerType.id).all()
    return render_template("hilfe.html", jokers=jokers_list, help=EFFECT_HELP)


@public.route("/lang/<code>")
def set_lang(code):
    if code in ("en", "de"):
        session["lang"] = code
    return redirect(request.referrer or url_for("public.dashboard"))
