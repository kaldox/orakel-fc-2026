# -*- coding: utf-8 -*-
"""Admin-Routen (Katalogpflege, Spielerverwaltung, Spielplan, Punkte-Korrekturen)."""
import json
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash

from extensions import db
from models import (Adjustment, Award, Challenge, ChaosEvent, JokerPlay,
                     JokerType, Match, Mission, MissionAssignment, Player, Tip)
from auth import admin_required
from settings import set_setting
from i18n_helpers import t
from catalog_config import CATALOGS, coerce

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/catalog/<kind>", methods=["GET", "POST"])
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
                flash(t("Gelöscht."), "ok")
            return redirect(url_for("admin.admin_catalog", kind=kind))
        oid = request.form.get("id")
        obj = db.session.get(Model, int(oid)) if oid else Model()
        for name, _label, ftype, *rest in cfg["fields"]:
            setattr(obj, name, coerce(ftype, request.form.get(name)))
        if not oid:
            db.session.add(obj)
        db.session.commit()
        flash(t("Gespeichert."), "ok")
        return redirect(url_for("admin.admin_catalog", kind=kind))
    items = Model.query.order_by(Model.id).all()
    edit = db.session.get(Model, int(request.args["edit"])) if request.args.get("edit") else None
    return render_template("admin_catalog.html", kind=kind, cfg=cfg, items=items,
                           edit=edit, catalogs=CATALOGS,
                           pmap={p.id: p.name for p in Player.query.all()},
                           players=Player.query.filter_by(plays=True).all())


@admin_bp.route("")
@admin_required
def admin_home():
    stats = {"players": Player.query.filter_by(plays=True).count(),
             "matches": Match.query.count(),
             "finished": Match.query.filter_by(finished=True).count(),
             "jokers": JokerType.query.count(),
             "missions": Mission.query.count()}
    return render_template("admin_home.html", stats=stats, catalogs=CATALOGS)


@admin_bp.route("/mode", methods=["POST"])
@admin_required
def admin_mode():
    set_setting("simple_mode", "1" if request.form.get("simple") == "1" else "0")
    flash(t("Modus geändert."), "ok")
    return redirect(url_for("admin.admin_home"))


@admin_bp.route("/players", methods=["GET", "POST"])
@admin_required
def admin_players():
    if request.method == "POST":
        if request.form.get("action") == "delete":
            p = db.session.get(Player, int(request.form["id"]))
            if p and p.id != session.get("pid"):
                db.session.delete(p); db.session.commit()
            return redirect(url_for("admin.admin_players"))
        if request.form.get("action") == "resetpw":
            p = db.session.get(Player, int(request.form["id"]))
            newpw = request.form.get("password", "")
            if p and len(newpw) >= 6:
                p.pw_hash = generate_password_hash(newpw)
                db.session.commit()
                flash(t("Neues Passwort für {n} gesetzt.", n=p.name), "ok")
            elif p:
                flash(t("Neues Passwort braucht mindestens 6 Zeichen."), "error")
            return redirect(url_for("admin.admin_players"))
        name = request.form.get("name", "").strip()
        pw = request.form.get("password", "")
        if name and pw:
            if Player.query.filter_by(name=name).first():
                flash(t("Name existiert schon."), "error")
            else:
                db.session.add(Player(name=name, pw_hash=generate_password_hash(pw),
                                      is_admin=bool(request.form.get("is_admin")),
                                      plays=bool(request.form.get("plays", "on"))))
                db.session.commit()
                flash(t("Spieler:in angelegt."), "ok")
        return redirect(url_for("admin.admin_players"))
    return render_template("admin_players.html", players=Player.query.order_by(Player.id).all())


@admin_bp.route("/matches", methods=["GET", "POST"])
@admin_required
def admin_matches():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            m = db.session.get(Match, int(request.form["id"]))
            if m:
                Tip.query.filter_by(match_id=m.id).delete()
                db.session.delete(m); db.session.commit()
            return redirect(url_for("admin.admin_matches"))
        try:
            kickoff = datetime.strptime(request.form["kickoff"], "%Y-%m-%dT%H:%M")
        except (ValueError, KeyError):
            flash(t("Ungültiger Anpfiff-Zeitpunkt."), "error")
            return redirect(url_for("admin.admin_matches"))
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
                flash(t("Spiel aktualisiert."), "ok")
            return redirect(url_for("admin.admin_matches"))
        db.session.add(Match(matchday=request.form.get("matchday", "1").strip() or "1",
                             stage=request.form.get("stage", "Gruppe").strip() or "Gruppe",
                             home=request.form["home"].strip(), away=request.form["away"].strip(),
                             kickoff=kickoff, is_knockout=bool(request.form.get("is_knockout"))))
        db.session.commit()
        flash(t("Spiel angelegt."), "ok")
        return redirect(url_for("admin.admin_matches"))
    matches = Match.query.order_by(Match.kickoff, Match.id).all()
    edit = db.session.get(Match, int(request.args["edit"])) if request.args.get("edit") else None
    return render_template("admin_matches.html", matches=matches, edit=edit)


@admin_bp.route("/matches/import", methods=["POST"])
@admin_required
def admin_matches_import():
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
        flash(t("{n} Spiele importiert.", n=n), "ok")
    except Exception as e:
        flash(t("Import fehlgeschlagen: {e}", e=e), "error")
    return redirect(url_for("admin.admin_matches"))


@admin_bp.route("/result/<int:mid>", methods=["POST"])
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
    flash(t("Ergebnis gespeichert."), "ok")
    return redirect(url_for("admin.admin_matches"))


@admin_bp.route("/assign", methods=["GET", "POST"])
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
            flash(t("Mission zugewiesen."), "ok")
        elif request.form.get("action") == "toggle":
            a = db.session.get(MissionAssignment, int(request.form["id"]))
            if a:
                a.completed = not a.completed; db.session.commit()
        return redirect(url_for("admin.admin_assign"))
    return render_template("admin_assign.html",
                           players=Player.query.filter_by(plays=True).all(),
                           missions=Mission.query.filter_by(active=True).all(),
                           assignments=MissionAssignment.query.all(),
                           pmap={p.id: p.name for p in Player.query.all()},
                           mmap={m.id: m for m in Mission.query.all()})


@admin_bp.route("/winner/<kind>/<int:oid>", methods=["POST"])
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
        flash(t("Gewinner:in gesetzt."), "ok")
    return redirect(url_for("admin.admin_catalog", kind=kind))


@admin_bp.route("/adjustments", methods=["GET", "POST"])
@admin_required
def admin_adjustments():
    if request.method == "POST":
        if request.form.get("action") == "delete":
            a = db.session.get(Adjustment, int(request.form["id"]))
            if a:
                db.session.delete(a); db.session.commit()
            return redirect(url_for("admin.admin_adjustments"))
        try:
            pts = int(request.form["points"])
        except (ValueError, KeyError):
            pts = 0
        db.session.add(Adjustment(player_id=int(request.form["player_id"]), points=pts,
                                  matchday=request.form.get("matchday", "").strip() or None,
                                  reason=request.form.get("reason", "")[:200]))
        db.session.commit()
        flash(t("Anpassung gespeichert."), "ok")
        return redirect(url_for("admin.admin_adjustments"))
    return render_template("admin_adjustments.html",
                           players=Player.query.filter_by(plays=True).all(),
                           items=Adjustment.query.order_by(Adjustment.id.desc()).all(),
                           pmap={p.id: p.name for p in Player.query.all()})


@admin_bp.route("/jokerplays", methods=["GET", "POST"])
@admin_required
def admin_jokerplays():
    if request.method == "POST" and request.form.get("action") == "delete":
        jp = db.session.get(JokerPlay, int(request.form["id"]))
        if jp:
            db.session.delete(jp); db.session.commit()
        return redirect(url_for("admin.admin_jokerplays"))
    return render_template("admin_jokerplays.html",
                           plays=JokerPlay.query.order_by(JokerPlay.id.desc()).all(),
                           jt={j.id: j for j in JokerType.query.all()},
                           pm={p.id: p.name for p in Player.query.all()},
                           mm={m.id: m for m in Match.query.all()})


@admin_bp.route("/chaos/<int:cid>/toggle", methods=["POST"])
@admin_required
def admin_chaos_toggle(cid):
    c = db.session.get(ChaosEvent, cid)
    if c:
        c.active = not c.active
        c.activated_at = datetime.utcnow() if c.active else None
        db.session.commit()
    return redirect(url_for("admin.admin_catalog", kind="chaos"))
