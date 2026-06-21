<div align="center">

# ORAKEL FC 2026 ⚽🔮

**Dein selbst gehostetes WM-2026-Tippspiel für die Freundesrunde.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Self-hosted](https://img.shields.io/badge/self--hosted-%E2%9C%93-success)
![UI](https://img.shields.io/badge/UI-EN%20%2F%20DE-informational)

**🇩🇪 Deutsch** · [🇬🇧 English](README.en.md) · [🟥⚫ Baseldütsch](README.bl.md)

</div>

> *Reden ist Silber. Richtig tippen ist Gold. Falsch tippen ist Kaffeeküche.*

Mit **Jokern, geheimen Missionen, Challenges, Sonderwertungen und Chaos-Events** – und du kannst es jederzeit im Browser mit **neuen Ideen erweitern**, ohne eine Zeile Code. Nicht jedermanns Sache? Ein Schalter macht daraus ein **schlichtes Tippspiel**. Eine kompakte **Flask + SQLite**-App, alles in **einem Docker-Container**: läuft auf einem Raspberry Pi oder beliebigen Server, hinter einem Reverse-Proxy (HTTPS).

## Features

- ⚽ **Tippen** mit Sperre zum Anpfiff, Risiko-Tipp pro Spieltag (×2 / −4)
- 🏆 **Live-Tabelle** mit deterministischer Wertung (Tendenz/Differenz/Exakt, K.-o.- und Außenseiter-Bonus)
- 🃏 **Joker** mit automatischen Effekten (Verdoppeln, Sabotage, Schutzschild, Tausch, …) – frei erweiterbar
- 🔮 **Geheime Missionen**, 🎯 **Wochen-Challenges**, 🏅 **Sonderwertungen**, 🌀 **Chaos-Events** – alles im Browser editierbar
- 🎚️ **Nur-Tippspiel-Schalter** – blendet alle Extras mit einem Klick aus (klassisches Tippspiel)
- 🌍 **Zweisprachig** (Deutsch / Englisch), folgt dem Browser und jederzeit umschaltbar
- 📱 **Mobil-optimiert**: untere Tab-Leiste, große Buttons, Erstlogin-Tutorial, Hilfe-Seite
- 🛠️ **Admin-Bereich**: Spieler, Spielplan (inkl. JSON-Import), Ergebnisse, Punkte-Anpassungen, Passwort-Reset
- 🔒 **Sicherheit**: CSRF-Schutz, Bruteforce-Bremse beim Login, sinnvolle Sicherheitsheader, gehärtete Session-Cookies

## Screenshots

<!-- Lege deine PNGs in den docs/-Ordner und entferne dann die Kommentarzeichen:
| Tabelle | Tippen | Hilfe |
|:---:|:---:|:---:|
| ![Tabelle](docs/standings.png) | ![Tippen](docs/predict.png) | ![Hilfe](docs/help.png) |
-->

_Lege ein paar Screenshots in `docs/` ab und entkommentiere die Galerie oben – siehe [Wiki](../../wiki)._

## Dokumentation

Ausführliche Anleitungen stehen im **[Wiki](../../wiki)**: Installation, Betrieb im Internet mit HTTPS, Saison-Ablauf, Wertungsregeln, Backups & Updates sowie eine FAQ.

Ein Helfer-Skript (`wm2026_import.py`) lädt den kompletten WM-2026-Spielplan von [openfootball](https://github.com/openfootball) und erzeugt die Import-Datei.

---

## 1. Schnellstart (Docker)

```bash
# 1. Ins Projektverzeichnis wechseln
cd orakel-fc

# 2. Konfiguration anlegen und anpassen
cp .env.example .env
nano .env          # SECRET_KEY + ADMIN_PASSWORD setzen!

# 3. Starten
docker compose up -d --build
```

Die App lauscht jetzt auf **`127.0.0.1:8090`** (nur lokal – nach außen geht es über nginx, siehe Schritt 3).

Logs ansehen / stoppen:
```bash
docker compose logs -f
docker compose down
```

### SECRET_KEY erzeugen
```bash
openssl rand -hex 32
```

---

## 2. Erster Login

Öffne `http://<pi-ip>:8090/login` (oder gleich deine Domain nach Schritt 3) und melde dich mit den Daten aus deiner `.env` an (Standard: `admin` / dein `ADMIN_PASSWORD`).

Der Admin-Account **spielt selbst nicht mit** (taucht also nicht in der Tabelle auf). Lege im Admin-Bereich unter **Spieler** alle Mitspieler:innen an – jede:r bekommt Name + Passwort.

---

## 3. Hinter deinen nginx hängen

Du hast Domain + nginx schon – es fehlt nur ein vhost:

```bash
# 1. In der Datei orakel-fc.nginx.conf die Domain anpassen, dann:
sudo cp orakel-fc.nginx.conf /etc/nginx/sites-available/orakel-fc
sudo ln -s /etc/nginx/sites-available/orakel-fc /etc/nginx/sites-enabled/

# 2. Testen + neu laden
sudo nginx -t && sudo systemctl reload nginx

# 3. HTTPS holen (certbot ergänzt den 443-Block automatisch)
sudo certbot --nginx -d orakel.deine-domain.tld
```

DNS-A-Record der Subdomain auf deine IP zeigen lassen (bei dynamischer Heim-IP per DDNS/Domain-API aktuell halten).

---

## 4. Saison-Ablauf

| Schritt | Wo | Was |
|--------|-----|-----|
| **Spieler anlegen** | Admin → Spieler | Name + Passwort für jede:n |
| **Spielplan einlesen** | Admin → Spiele | Spiele einzeln anlegen **oder** als JSON importieren |
| **Geheime Missionen verteilen** | Admin → Missionen zuweisen | Jede:r kriegt eine – sieht nur die eigene |
| **Getippt wird** | von den Spieler:innen unter „Tippen" | Sperrt automatisch zum Anpfiff |
| **Ergebnisse eintragen** | Admin → Spiele | Tor:Tor, ggf. „Überraschung"/„KO" anhaken |
| **Joker** | Spieler unter „Joker", Admin sieht „Gespielte Joker" | Auto-Effekte rechnen sich selbst |
| **Sonderfälle** | Admin → Anpassungen | Manueller Bonus/Malus mit Begründung |
| **Challenge-/Award-Gewinner** | Admin → Katalog | Gewinner:in auswählen, Punkte fließen automatisch |

### Spielplan-Import (JSON)
Unter *Admin → Spiele* eine Liste einfügen:
```json
[
  {"home":"Mexiko","away":"Polen","kickoff":"2026-06-11T18:00","matchday":"1","stage":"Gruppe A"},
  {"home":"Kanada","away":"Schweiz","kickoff":"2026-06-12T21:00","matchday":"1","stage":"Gruppe B","knockout":false}
]
```
Pflichtfelder: `home`, `away`, `kickoff` (`YYYY-MM-DDTHH:MM`). Optional: `matchday`, `stage`, `knockout`. Den WM-2026-Spielplan bekommst du z. B. kostenlos und ohne API-Key von **openfootball** (github.com/openfootball) und formst ihn einmalig in dieses Format um.

---

## 5. ⭐ Mit eigenen Ideen erweitern (der Clou)

Alle „Kataloge" sind **im Browser editierbar** – kein Deploy nötig. Im Admin-Bereich gibt es je eine Seite zum Anlegen/Bearbeiten/Löschen für:

- **Joker** · **Missionen** · **Challenges** · **Sonderwertungen (Awards)** · **Chaos-Events**

Neue Idee = neuer Eintrag, fertig. Du kannst klein starten und über die Saison immer mehr dazupacken.

### Joker-Auto-Effekte
Beim Anlegen eines Jokers wählst du ein `auto_effect`. Die App rechnet diese automatisch:

| Effekt | Wirkung |
|--------|---------|
| `double` | Verdoppelt die Punkte **eines gewählten Spiels** |
| `triple` | Verdreifacht **einen ganzen Spieltag** |
| `allin` | Tagesertrag auf 1 Spiel: Tendenz trifft → ×3, sonst 0 |
| `lucky` | 0 Punkte an einem Spieltag → trotzdem 3 Trostpunkte |
| `sabotage` | Halbiert die Tagespunkte eines Gegners |
| `shield` | Macht einen Spieltag immun gegen Sabotage |
| `swap` | Schlechtester Spieltag zählt wie der Liga-Durchschnitt |
| `manual` | Kein Automatismus – du wertest ihn über **Anpassungen** |

Für alles Kreative, das sich nicht automatisieren lässt (Chaos-Joker, Wett-Einsätze, Kaffeeküchen-Bußen): einfach `manual` wählen und die Punkte unter **Admin → Anpassungen** mit Begründung buchen (positiv = Bonus, negativ wie `-4` = Malus).

---

## 6. Wertungssystem

**Pro Tipp:**
- Richtige Tendenz: **3**
- Richtige Tordifferenz: **5**
- Exaktes Ergebnis: **8**

**Boni (nur bei richtiger Tendenz):**
- K.-o.-Spiel: **+2**
- Als „Überraschung" markiert: **+3**

**Risiko-Tipp** (max. 1 pro Spieltag): richtig → **×2**, falsch → **−4**.

Dazu kommen Missions-, Challenge- und Award-Punkte sowie manuelle Anpassungen. Die Tabelle aktualisiert sich live.

---

## 7. Backup & Update

**Alle Daten** liegen in einer einzigen Datei: `./data/orakel.db`.
```bash
# Backup
cp data/orakel.db data/orakel-backup-$(date +%F).db
```

**Update** (Daten bleiben erhalten, da im Volume):
```bash
git pull        # oder neue Dateien einspielen
docker compose up -d --build
```

---

## 8. Sicherheit

- **`SECRET_KEY`** und **`ADMIN_PASSWORD`** in `.env` unbedingt ändern.
- Der Container ist an `127.0.0.1` gebunden – von außen nur über nginx + HTTPS erreichbar.
- Für eine kleine Freundesrunde (5–15 Leute) ist 1 Worker + SQLite ideal. Erst bei sehr vielen gleichzeitigen Schreibzugriffen lohnt ein Umstieg auf Postgres.

---

## 9. Tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install pytest
python3 -m pytest tests/      # 52 Tests: Wertungs-Engine, Login/Bruteforce/Open-Redirect, Routen
```

---

## Projektstruktur

```
orakel-fc/
├── app.py                  # App-Setup: Konfiguration, Extensions, Blueprint-Registrierung
├── extensions.py           # db, csrf (Flask-Extension-Instanzen)
├── models.py                # SQLAlchemy-Modelle (Player, Match, Tip, Joker, …)
├── auth.py                  # Login, Bruteforce-Schutz, Open-Redirect-Schutz, Decorators
├── scoring.py                # Wertungs-Engine (Punkteberechnung, Tabelle)
├── settings.py                # Key/Value-Einstellungen (z. B. Nur-Tippspiel-Modus)
├── security.py                # HTTP-Sicherheitsheader
├── i18n_helpers.py            # Sprachauswahl-Logik (nutzt i18n.py)
├── i18n.py                    # Übersetzungstabelle (Deutsch → Englisch)
├── catalog_config.py          # Gemeinsame Konfiguration für Joker-Effekte & Admin-Kataloge
├── routes/
│   ├── public.py            # Routen für Spieler:innen (Tippen, Joker, Tabelle, …)
│   └── admin.py              # Admin-Routen (Spieler, Spielplan, Kataloge, Anpassungen)
├── templates/              # alle HTML-Seiten
├── static/style.css        # ORAKEL-Design (dunkel, grün/gold)
├── tests/                    # pytest-Suite (Wertung, Auth, Routen)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── orakel-fc.nginx.conf    # fertiger nginx-Server-Block
└── .env.example            # Konfig-Vorlage
```

Viel Spaß – und möge der/die beste Orakel gewinnen. 🏆

---

## Lizenz

Veröffentlicht unter der **MIT-Lizenz** (siehe `LICENSE`). Du darfst die Software frei
nutzen, anpassen und weitergeben. Pull Requests und Ideen sind willkommen.

## Mitwirken / Eigene Instanz

1. Repo klonen, `cp .env.example .env` und Werte setzen (`SECRET_KEY`, `ADMIN_PASSWORD`).
2. `docker compose up -d --build` – App läuft auf `127.0.0.1:8090`.
3. Für den Internet-Betrieb einen Reverse-Proxy mit HTTPS davorsetzen (Nginx Proxy Manager,
   Caddy oder nginx + certbot) – Schritt für Schritt in `BETRIEB.md`.

> Hinweis: `.env` und der `data/`-Ordner (Datenbank) sind in `.gitignore` ausgeschlossen
> und gehören **nie** ins Repository.
