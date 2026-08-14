# -*- coding: utf-8 -*-
"""
Flask-Extension-Instanzen, getrennt von app.py.

Liegt in einem eigenen Modul, damit models.py, auth.py und die Routen
'db' importieren koennen, ohne app.py importieren zu muessen (das wuerde
einen Zirkel ergeben, da app.py selbst die Routen registriert).
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
