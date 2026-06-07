#!/usr/bin/env python3
"""
ORAKEL FC 2026 - Spielplan-Import-Generator
============================================

Holt den offiziellen WM-2026-Spielplan direkt von openfootball (GitHub),
rechnet alle Anstosszeiten in Schweizer Zeit (Europe/Zurich) um, uebersetzt
Team- und Rundennamen ins Deutsche und schreibt eine Datei `wm2026-import.json`.

Den Inhalt dieser Datei kopierst du anschliessend 1:1 in ORAKEL FC unter
  Admin -> Spiele -> "Spiele importieren (JSON)".

Aufruf (auf dem Pi oder ueberall mit Python 3):
    python3 wm2026_import.py

Keine externen Pakete noetig - nur Python-Standardbibliothek.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Einstellungen
# ---------------------------------------------------------------------------
SOURCE_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
TARGET_TZ = "Europe/Zurich"      # Zielzeitzone fuer die Anstosszeiten
OUTPUT_FILE = "wm2026-import.json"
TRANSLATE_TEAMS = True           # Teamnamen ins Deutsche uebersetzen
INCLUDE_KNOCKOUT = True          # K.-o.-Spiele mit aufnehmen (mit Platzhalter-Namen)

# Deutsche Namen der 48 Teilnehmer (Fallback: Originalname, falls hier nicht gelistet)
TEAMS_DE = {
    "Algeria": "Algerien", "Argentina": "Argentinien", "Australia": "Australien",
    "Austria": "Österreich", "Belgium": "Belgien",
    "Bosnia & Herzegovina": "Bosnien und Herzegowina", "Brazil": "Brasilien",
    "Canada": "Kanada", "Cape Verde": "Kap Verde", "Colombia": "Kolumbien",
    "Croatia": "Kroatien", "Curaçao": "Curaçao", "Czech Republic": "Tschechien",
    "DR Congo": "DR Kongo", "Ecuador": "Ecuador", "Egypt": "Ägypten",
    "England": "England", "France": "Frankreich", "Germany": "Deutschland",
    "Ghana": "Ghana", "Haiti": "Haiti", "Iran": "Iran", "Iraq": "Irak",
    "Ivory Coast": "Elfenbeinküste", "Japan": "Japan", "Jordan": "Jordanien",
    "Mexico": "Mexiko", "Morocco": "Marokko", "Netherlands": "Niederlande",
    "New Zealand": "Neuseeland", "Norway": "Norwegen", "Panama": "Panama",
    "Paraguay": "Paraguay", "Portugal": "Portugal", "Qatar": "Katar",
    "Saudi Arabia": "Saudi-Arabien", "Scotland": "Schottland", "Senegal": "Senegal",
    "South Africa": "Südafrika", "South Korea": "Südkorea", "Spain": "Spanien",
    "Sweden": "Schweden", "Switzerland": "Schweiz", "Tunisia": "Tunesien",
    "Turkey": "Türkei", "USA": "USA", "Uruguay": "Uruguay", "Uzbekistan": "Usbekistan",
}

# K.-o.-Runden: openfootball-Name -> (Spieltag-Label, deutsche Phase)
KO_ROUNDS = {
    "Round of 32":          ("18", "Sechzehntelfinale"),
    "Round of 16":          ("19", "Achtelfinale"),
    "Quarter-final":        ("20", "Viertelfinale"),
    "Semi-final":           ("21", "Halbfinale"),
    "Match for third place":("22", "Spiel um Platz 3"),
    "Final":                ("23", "Finale"),
}


def target_tz():
    """Zielzeitzone laden. Faellt auf feste +2 h (Sommerzeit CH) zurueck,
    falls keine Zeitzonendatenbank vorhanden ist (z.B. schlanke Container)."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TARGET_TZ)
    except Exception:
        # Die gesamte WM 2026 (11. Juni - 19. Juli) liegt in der CH-Sommerzeit
        # (CEST = UTC+2), ohne Zeitumstellung in diesem Zeitraum.
        return timezone(timedelta(hours=2))


def to_zurich(date_str, time_str, tz):
    """'2026-06-11' + '13:00 UTC-6' -> '2026-06-11T21:00' (Zuerich)."""
    m = re.match(r"(\d{1,2}):(\d{2})\s*UTC([+-]\d+)", time_str.strip())
    if not m:
        raise ValueError("Unerwartetes Zeitformat: %r" % time_str)
    hh, mm, off = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y, mo, d = (int(x) for x in date_str.split("-"))
    src = datetime(y, mo, d, hh, mm, tzinfo=timezone(timedelta(hours=off)))
    return src.astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def team(name):
    if TRANSLATE_TEAMS:
        return TEAMS_DE.get(name, name)
    return name


def convert(matches, tz):
    rows = []
    for m in matches:
        rnd = m.get("round", "")
        is_ko = rnd in KO_ROUNDS
        if is_ko and not INCLUDE_KNOCKOUT:
            continue
        if is_ko:
            matchday, stage = KO_ROUNDS[rnd]
        else:
            num = re.search(r"\d+", rnd)
            matchday = num.group(0) if num else "1"
            stage = (m.get("group", "Gruppe")).replace("Group", "Gruppe")
        rows.append({
            "home": team(m["team1"]),
            "away": team(m["team2"]),
            "kickoff": to_zurich(m["date"], m["time"], tz),
            "matchday": matchday,
            "stage": stage,
            "knockout": is_ko,
        })
    rows.sort(key=lambda r: r["kickoff"])
    return rows


def main():
    print("Lade Spielplan von openfootball ...")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("FEHLER beim Download: %s" % e, file=sys.stderr)
        print("Pruefe deine Internetverbindung oder die URL.", file=sys.stderr)
        sys.exit(1)

    tz = target_tz()
    rows = convert(data.get("matches", []), tz)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    ko = sum(1 for r in rows if r["knockout"])
    group = len(rows) - ko
    first, last = rows[0]["kickoff"], rows[-1]["kickoff"]
    print("Fertig: %d Spiele geschrieben nach %s" % (len(rows), OUTPUT_FILE))
    print("  - %d Gruppenspiele, %d K.-o.-Spiele" % (group, ko))
    print("  - Anstoss (Schweizer Zeit) von %s bis %s" % (first, last))
    print("\nJetzt den Inhalt von %s kopieren und in ORAKEL FC unter" % OUTPUT_FILE)
    print("Admin -> Spiele -> 'Spiele importieren (JSON)' einfuegen.")
    if ko:
        print("\nHinweis: K.-o.-Spiele tragen noch Platzhalter (z.B. '2A', 'W97'),")
        print("solange die Teams nicht feststehen. Siehe README-Hinweis zum Nachpflegen.")


if __name__ == "__main__":
    main()
