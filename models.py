# -*- coding: utf-8 -*-
"""
Datenbankmodelle fuer ORAKEL FC 2026.

Alle SQLAlchemy-Modelle an einer Stelle, getrennt von Routen und Logik.
"""
from datetime import datetime

from extensions import db


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


class Setting(db.Model):
    """Einfacher Schluessel/Wert-Speicher fuer App-Einstellungen."""
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), default="")
