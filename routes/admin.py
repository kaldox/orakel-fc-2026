# -*- coding: utf-8 -*-
"""Admin-Routen (Katalogpflege, Spielerverwaltung, Spielplan, Punkte-Korrekturen)."""
import json
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash

from extensions import db
from models import (Adjustment, Award, Challenge, ChaosEvent, Competition,
                     JokerPlay, JokerType, Match, Membership, Mission,
                     MissionAssignment, Player, Tip)
from auth import admin_required
from competitions import FORMAT_PRESETS, require_competition, unique_slug
from i18n_helpers import t
from catalog_config import CATALOGS, coerce

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/catalog/<kind>", methods=["GET", "POST"])
@admin_required
def admin_catalog(kind):
    cfg = CATALOGS.get(kind)
    if not cfg:
        abort(404)
    comp = require_competition()
    Model = cfg["model"]
    if request.method == "POST":
        if request.form.get("action") == "delete":
            obj = db.session.get(Model, int(request.form["id"]))
            if obj and obj.competition_id == comp.id:
                db.session.delete(obj); db.session.commit()
                flash(t("Gelöscht."), "ok")
            return redirect(url_for("admin.admin_catalog", kind=kind))
        oid = request.form.get("id")
        obj = db.session.get(Model, int(oid)) if oid else None
        if oid and (not obj or obj.competition_id != comp.id):
            abort(404)
        if not obj:
            obj = Model(competition_id=comp.id)
        for name, _label, ftype, *rest in cfg["fields"]:
            setattr(obj, name, coerce(ftype, request.form.get(name)))
        if not oid:
            db.session.add(obj)
        db.session.commit()
        flash(t("Gespeichert."), "ok")
        return redirect(url_for("admin.admin_catalog", kind=kind))
    items = Model.query.filter_by(competition_id=comp.id).order_by(Model.id).all()
    edit = db.session.get(Model, int(request.args["edit"])) if request.args.get("edit") else None
    if edit and edit.competition_id != comp.id:
        edit = None
    member_ids = [m.player_id for m in Membership.query.filter_by(competition_id=comp.id, plays=True).all()]
    return render_template("admin_catalog.html", kind=kind, cfg=cfg, items=items,
                           edit=edit, catalogs=CATALOGS,
                           pmap={p.id: p.name for p in Player.query.all()},
                           players=Player.query.filter(Player.id.in_(member_ids)).all() if member_ids else [])


@admin_bp.route("")
@admin_required
def admin_home():
    comp = require_competition()
    stats = {"players": Membership.query.filter_by(competition_id=comp.id, plays=True).count(),
             "matches": Match.query.filter_by(competition_id=comp.id).count(),
             "finished": Match.query.filter_by(competition_id=comp.id, finished=True).count(),
             "jokers": JokerType.query.filter_by(competition_id=comp.id).count(),
             "missions": Mission.query.filter_by(competition_id=comp.id).count()}
    return render_template("admin_home.html", stats=stats, catalogs=CATALOGS, comp=comp,
                           competition_count=Competition.query.count())


@admin_bp.route("/wettbewerbe", methods=["GET", "POST"])
@admin_required
def admin_competitions():
    if request.method == "POST":
        action = request.form.get("action")
        if action in ("archive", "reactivate"):
            c = db.session.get(Competition, int(request.form["id"]))
            if c:
                c.active = (action == "reactivate")
                db.session.commit()
                flash(t("Turnier archiviert.") if action == "archive" else t("Turnier reaktiviert."), "ok")
            return redirect(url_for("admin.admin_competitions"))
        oid = request.form.get("id")
        obj = db.session.get(Competition, int(oid)) if oid else None
        if oid and not obj:
            abort(404)
        fmt = request.form.get("format", "league")
        labels = FORMAT_PRESETS.get(fmt, FORMAT_PRESETS["league"])
        name = request.form.get("name", "").strip()
        if not name:
            flash(t("Bitte einen Namen für das Turnier angeben."), "error")
            return redirect(url_for("admin.admin_competitions"))
        is_new = obj is None
        if is_new:
            obj = Competition(slug=unique_slug(name))
            db.session.add(obj)
        obj.name = name
        obj.format = fmt
        obj.matchday_label = request.form.get("matchday_label", "").strip() or labels["matchday_label"]
        obj.stage_label = request.form.get("stage_label", "").strip() or labels["stage_label"]
        db.session.commit()
        if is_new:
            # Neu angelegtes Turnier gleich als aktives auswaehlen, damit man
            # direkt Spieler/Spiele dafuer anlegen kann, ohne umzuschalten.
            session["cid"] = obj.id
        flash(t("Turnier gespeichert."), "ok")
        return redirect(url_for("admin.admin_competitions"))
    items = Competition.query.order_by(Competition.sort_order, Competition.id).all()
    counts = {c.id: Membership.query.filter_by(competition_id=c.id, plays=True).count() for c in items}
    return render_template("admin_competitions.html", items=items, counts=counts,
                           formats=FORMAT_PRESETS, current=require_competition())


@admin_bp.route("/mode", methods=["POST"])
@admin_required
def admin_mode():
    comp = require_competition()
    comp.simple_mode = request.form.get("simple") == "1"
    db.session.commit()
    flash(t("Modus geändert."), "ok")
    return redirect(url_for("admin.admin_home"))


@admin_bp.route("/players", methods=["GET", "POST"])
@admin_required
def admin_players():
    comp = require_competition()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            p = db.session.get(Player, int(request.form["id"]))
            if p and p.id != session.get("pid"):
                Membership.query.filter_by(player_id=p.id).delete()
                db.session.delete(p); db.session.commit()
            return redirect(url_for("admin.admin_players"))
        if action == "resetpw":
            p = db.session.get(Player, int(request.form["id"]))
            newpw = request.form.get("password", "")
            if p and len(newpw) >= 6:
                p.pw_hash = generate_password_hash(newpw)
                db.session.commit()
                flash(t("Neues Passwort für {n} gesetzt.", n=p.name), "ok")
            elif p:
                flash(t("Neues Passwort braucht mindestens 6 Zeichen."), "error")
            return redirect(url_for("admin.admin_players"))
        if action == "addmember":
            p = db.session.get(Player, int(request.form.get("player_id", 0)))
            if p and not p.is_admin and not Membership.query.filter_by(
                    player_id=p.id, competition_id=comp.id).first():
                db.session.add(Membership(player_id=p.id, competition_id=comp.id, plays=True))
                db.session.commit()
                flash(t("{n} zu '{c}' hinzugefügt.", n=p.name, c=comp.name), "ok")
            return redirect(url_for("admin.admin_players"))
        if action == "removemember":
            mem = db.session.get(Membership, int(request.form.get("membership_id", 0)))
            if mem and mem.competition_id == comp.id:
                db.session.delete(mem); db.session.commit()
                flash(t("Aus '{c}' entfernt.", c=comp.name), "ok")
            return redirect(url_for("admin.admin_players"))
        name = request.form.get("name", "").strip()
        pw = request.form.get("password", "")
        if name and pw:
            if Player.query.filter_by(name=name).first():
                flash(t("Name existiert schon."), "error")
            else:
                is_admin = bool(request.form.get("is_admin"))
                plays = bool(request.form.get("plays", "on"))
                p = Player(name=name, pw_hash=generate_password_hash(pw), is_admin=is_admin, plays=plays)
                db.session.add(p)
                db.session.commit()
                if not is_admin:
                    # Wie bisher: neu angelegte Person spielt sofort im aktuell
                    # gewaehlten Turnier mit - keine zweite Aktion noetig.
                    db.session.add(Membership(player_id=p.id, competition_id=comp.id, plays=plays))
                    db.session.commit()
                flash(t("Spieler:in angelegt."), "ok")
        return redirect(url_for("admin.admin_players"))
    all_players = Player.query.order_by(Player.id).all()
    memberships = {m.player_id: m for m in Membership.query.filter_by(competition_id=comp.id).all()}
    non_members = [p for p in all_players if not p.is_admin and p.id not in memberships]
    return render_template("admin_players.html", players=all_players, memberships=memberships,
                           non_members=non_members, comp=comp)


@admin_bp.route("/matches", methods=["GET", "POST"])
@admin_required
def admin_matches():
    comp = require_competition()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            m = db.session.get(Match, int(request.form["id"]))
            if m and m.competition_id == comp.id:
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
            if m and m.competition_id == comp.id:
                m.home = request.form["home"].strip()
                m.away = request.form["away"].strip()
                m.kickoff = kickoff
                m.matchday = request.form.get("matchday", "1").strip() or "1"
                m.stage = request.form.get("stage", comp.stage_label).strip() or comp.stage_label
                m.is_knockout = bool(request.form.get("is_knockout"))
                db.session.commit()
                flash(t("Spiel aktualisiert."), "ok")
            return redirect(url_for("admin.admin_matches"))
        db.session.add(Match(competition_id=comp.id,
                             matchday=request.form.get("matchday", "1").strip() or "1",
                             stage=request.form.get("stage", comp.stage_label).strip() or comp.stage_label,
                             home=request.form["home"].strip(), away=request.form["away"].strip(),
                             kickoff=kickoff, is_knockout=bool(request.form.get("is_knockout"))))
        db.session.commit()
        flash(t("Spiel angelegt."), "ok")
        return redirect(url_for("admin.admin_matches"))
    matches = Match.query.filter_by(competition_id=comp.id).order_by(Match.kickoff, Match.id).all()
    edit = db.session.get(Match, int(request.args["edit"])) if request.args.get("edit") else None
    if edit and edit.competition_id != comp.id:
        edit = None
    return render_template("admin_matches.html", matches=matches, edit=edit, comp=comp)


@admin_bp.route("/matches/import", methods=["POST"])
@admin_required
def admin_matches_import():
    comp = require_competition()
    try:
        data = json.loads(request.form.get("payload", "[]"))
        n = 0
        for row in data:
            db.session.add(Match(competition_id=comp.id, home=row["home"], away=row["away"],
                                 kickoff=datetime.strptime(row["kickoff"], "%Y-%m-%dT%H:%M"),
                                 matchday=str(row.get("matchday", "1")),
                                 stage=row.get("stage", comp.stage_label),
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
    comp = require_competition()
    m = db.session.get(Match, mid)
    if not m or m.competition_id != comp.id:
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
    comp = require_competition()
    if request.method == "POST":
        if request.form.get("action") == "assign":
            pid = int(request.form["player_id"]); mid = int(request.form["mission_id"])
            a = MissionAssignment.query.filter_by(competition_id=comp.id, player_id=pid).first()
            if not a:
                a = MissionAssignment(competition_id=comp.id, player_id=pid); db.session.add(a)
            a.mission_id = mid; a.completed = False
            db.session.commit()
            flash(t("Mission zugewiesen."), "ok")
        elif request.form.get("action") == "toggle":
            a = db.session.get(MissionAssignment, int(request.form["id"]))
            if a and a.competition_id == comp.id:
                a.completed = not a.completed; db.session.commit()
        return redirect(url_for("admin.admin_assign"))
    member_ids = [m.player_id for m in Membership.query.filter_by(competition_id=comp.id, plays=True).all()]
    return render_template("admin_assign.html",
                           players=Player.query.filter(Player.id.in_(member_ids)).all() if member_ids else [],
                           missions=Mission.query.filter_by(active=True, competition_id=comp.id).all(),
                           assignments=MissionAssignment.query.filter_by(competition_id=comp.id).all(),
                           pmap={p.id: p.name for p in Player.query.all()},
                           mmap={m.id: m for m in Mission.query.filter_by(competition_id=comp.id).all()})


@admin_bp.route("/winner/<kind>/<int:oid>", methods=["POST"])
@admin_required
def admin_winner(kind, oid):
    Model = {"challenges": Challenge, "awards": Award}.get(kind)
    if not Model:
        abort(404)
    comp = require_competition()
    obj = db.session.get(Model, oid)
    if obj and obj.competition_id == comp.id:
        val = request.form.get("winner_player_id")
        obj.winner_player_id = int(val) if val else None
        db.session.commit()
        flash(t("Gewinner:in gesetzt."), "ok")
    return redirect(url_for("admin.admin_catalog", kind=kind))


@admin_bp.route("/adjustments", methods=["GET", "POST"])
@admin_required
def admin_adjustments():
    comp = require_competition()
    if request.method == "POST":
        if request.form.get("action") == "delete":
            a = db.session.get(Adjustment, int(request.form["id"]))
            if a and a.competition_id == comp.id:
                db.session.delete(a); db.session.commit()
            return redirect(url_for("admin.admin_adjustments"))
        try:
            pts = int(request.form["points"])
        except (ValueError, KeyError):
            pts = 0
        db.session.add(Adjustment(competition_id=comp.id, player_id=int(request.form["player_id"]), points=pts,
                                  matchday=request.form.get("matchday", "").strip() or None,
                                  reason=request.form.get("reason", "")[:200]))
        db.session.commit()
        flash(t("Anpassung gespeichert."), "ok")
        return redirect(url_for("admin.admin_adjustments"))
    member_ids = [m.player_id for m in Membership.query.filter_by(competition_id=comp.id, plays=True).all()]
    return render_template("admin_adjustments.html",
                           players=Player.query.filter(Player.id.in_(member_ids)).all() if member_ids else [],
                           items=Adjustment.query.filter_by(competition_id=comp.id)
                                 .order_by(Adjustment.id.desc()).all(),
                           pmap={p.id: p.name for p in Player.query.all()})


@admin_bp.route("/jokerplays", methods=["GET", "POST"])
@admin_required
def admin_jokerplays():
    comp = require_competition()
    if request.method == "POST" and request.form.get("action") == "delete":
        jp = db.session.get(JokerPlay, int(request.form["id"]))
        if jp and jp.competition_id == comp.id:
            db.session.delete(jp); db.session.commit()
        return redirect(url_for("admin.admin_jokerplays"))
    return render_template("admin_jokerplays.html",
                           plays=JokerPlay.query.filter_by(competition_id=comp.id)
                                 .order_by(JokerPlay.id.desc()).all(),
                           jt={j.id: j for j in JokerType.query.filter_by(competition_id=comp.id).all()},
                           pm={p.id: p.name for p in Player.query.all()},
                           mm={m.id: m for m in Match.query.filter_by(competition_id=comp.id).all()})


@admin_bp.route("/chaos/<int:cid>/toggle", methods=["POST"])
@admin_required
def admin_chaos_toggle(cid):
    comp = require_competition()
    c = db.session.get(ChaosEvent, cid)
    if c and c.competition_id == comp.id:
        c.active = not c.active
        c.activated_at = datetime.utcnow() if c.active else None
        db.session.commit()
    return redirect(url_for("admin.admin_catalog", kind="chaos"))
