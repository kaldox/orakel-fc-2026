# Changelog

## [Unreleased]
### Hinzugefügt
- Mehrere Turniere/Ligen parallel (Competition-Modell): eigene Spiele, Kataloge,
  Tabelle und Mitgliedschaften je Turnier. Bei genau einem aktiven Turnier
  bleibt die Oberfläche wie bisher (kein Umschalter), ab zwei aktiven
  Turnieren erscheint ein Wechsel in der Navigation. Bestehende Installationen
  werden beim ersten Start automatisch in ein Default-Turnier migriert.
- 5 neue pytest-Tests dafür (`tests/test_competitions.py`)

### Geändert
- Flask auf 3.1.3 (CVE-2026-27205)
- README: Baseldütsch-Übersetzung entfernt

## [1.1.0] – 2026-06-22
### Geändert
- app.py in 11 Module aufgeteilt
- SECRET_KEY-Pflicht, Open-Redirect-Schutz
- README überarbeitet (DE/EN/Baseldütsch)

### Hinzugefügt
- 52 pytest-Tests
- BETRIEB.md

## [1.0.0] – 2026-06
### Hinzugefügt
- Tippsystem, Live-Tabelle, Joker, Missionen, Challenges
- CSRF-Schutz, Bruteforce-Bremse, Sicherheitsheader
- Docker-Setup, Admin-Bereich, WM-2026-Spielplan-Import
