# Changelog

## [Unreleased]
### Hinzugefügt
- Mehrere Turniere/Ligen parallel (Competition-Modell): eigene Spiele, Kataloge,
  Tabelle und Mitgliedschaften je Turnier. Bei genau einem aktiven Turnier
  bleibt die Oberfläche wie bisher (kein Umschalter), ab zwei aktiven
  Turnieren erscheint ein Wechsel in der Navigation. Bestehende Installationen
  werden beim ersten Start automatisch in ein Default-Turnier migriert.
- 5 neue pytest-Tests dafür (`tests/test_competitions.py`)
- `import_helper.py` (ersetzt `wm2026_import.py`): generischer Spielplan-Import
  von openfootball mit Presets für WM 2026, EM 2024/2028, Champions League,
  Europa League und Conference League (`--list` zeigt alle). Erkennt
  Turnier-/Spieltag-Struktur automatisch (auch aus dem football.txt-Format),
  rechnet Anstosszeiten korrekt in Schweizer Zeit um (inkl. Host-Zeitzone bei
  EM) und warnt vor noch nicht feststehenden Teams/Terminen. 11 neue Tests
  (`tests/test_import_helper.py`), keine Netzwerkzugriffe in der Testsuite.
- Info-Panel pro Spiel auf der Tippen-Seite (`stats.py`): bisherige Form
  beider Teams in diesem Turnier, Kopf-an-Kopf-Bilanz und Tipp-Verteilung
  der Gruppe. Nur aus bereits erfassten App-Daten, keine externe API. Die
  Gruppen-Verteilung wird pro Spiel erst sichtbar, nachdem man selbst
  getippt hat oder nach Anpfiff, um niemanden beim Tippen zu beeinflussen.
  6 neue pytest-Tests (`tests/test_stats.py`).

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
