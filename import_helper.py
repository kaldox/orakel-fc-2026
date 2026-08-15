#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORAKEL FC - Spielplan-Import-Generator (generisch)
====================================================

Laedt Spielplaene verschiedener Turniere von openfootball (GitHub, freie
Daten, kein API-Key noetig), rechnet alle Anstosszeiten in Schweizer Zeit
(Europe/Zurich) um und schreibt eine Datei im ORAKEL-FC-Importformat.

Den Inhalt der erzeugten Datei kopierst du anschliessend 1:1 in ORAKEL FC
unter Admin -> Spiele -> "Spiele importieren (JSON)".

Aufruf:
    python3 import_helper.py --list
    python3 import_helper.py --competition worldcup2026
    python3 import_helper.py --competition euro2028
    python3 import_helper.py --competition champions-league --season 2025-26
    python3 import_helper.py --competition europa-league
    python3 import_helper.py --competition conference-league --out el.json

Fuer jede andere Liga/jeden anderen Pokal reicht in aller Regel der bereits
eingebaute generische JSON-Import in ORAKEL FC selbst (Admin -> Spiele) -
dieses Skript ist nur eine Abkuerzung fuer ein paar oeffentlich verfuegbare
Turniere. Keine externen Pakete noetig - nur Python-Standardbibliothek.
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

TARGET_TZ_NAME = "Europe/Zurich"

# Als Wandzeit angenommene Sommer-Offsets (UTC+X), falls auf diesem System
# keine Zeitzonendatenbank verfuegbar ist (z.B. sehr schlanke Container).
# Alle betroffenen Turniere finden in der europaeischen Sommerzeit statt.
_FIXED_SUMMER_OFFSET = {
    "Europe/Zurich": 2, "Europe/Berlin": 2, "Europe/London": 1,
}


def _tz(name):
    """Zeitzone laden, mit Fallback auf einen festen Sommer-Offset."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=_FIXED_SUMMER_OFFSET.get(name, 2)))


# ---------------------------------------------------------------------------
# Deutsche Namen der ueblichen Nationalmannschaften (WM/EM). Nur fuer
# Nationalmannschafts-Turniere relevant - Vereinsnamen (Champions League &
# Co.) werden unveraendert uebernommen.
# ---------------------------------------------------------------------------
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
    "Wales": "Wales", "Poland": "Polen", "Slovenia": "Slowenien", "Slovakia": "Slowakei",
    "Serbia": "Serbien", "Ukraine": "Ukraine", "Denmark": "Dänemark",
    "Romania": "Rumänien", "Hungary": "Ungarn", "Albania": "Albanien",
    "Georgia": "Georgien", "Finland": "Finnland", "Northern Ireland": "Nordirland",
    "Republic of Ireland": "Irland", "Greece": "Griechenland",
}

# Turnier-Rundennamen -> deutsche Phase (fuer die "stage"-Spalte).
STAGE_DE = {
    "League": "Liga-Phase", "League phase": "Liga-Phase",
    "Playoffs": "Playoffs", "Finals": "K.-o.-Phase",
    "Round of 16": "Achtelfinale", "Quarterfinals": "Viertelfinale",
    "Quarter-finals": "Viertelfinale", "Semifinals": "Halbfinale",
    "Semi-finals": "Halbfinale", "Final": "Finale",
}

# Runden-Bezeichnung (JSON-Quellen worldcup.json/euro.json) -> (Matchday-Label, Phase).
KO_ROUNDS = {
    "worldcup2026": {
        "Round of 32": ("18", "Sechzehntelfinale"),
        "Round of 16": ("19", "Achtelfinale"),
        "Quarter-final": ("20", "Viertelfinale"),
        "Semi-final": ("21", "Halbfinale"),
        "Match for third place": ("22", "Spiel um Platz 3"),
        "Final": ("23", "Finale"),
    },
    "euro": {
        "Round of 16": ("7", "Achtelfinale"),
        "Quarter-finals": ("8", "Viertelfinale"),
        "Semi-finals": ("9", "Halbfinale"),
        "Final": ("10", "Finale"),
    },
}


def _current_season():
    """Grobe Schaetzung der laufenden/naechsten Europapokal-Saison
    (z.B. '2026-27') anhand des heutigen Datums. Die europaeischen
    Vereinswettbewerbe starten im August/September - vor Juli gilt daher
    noch die Saison, die im Vorjahr begonnen hat."""
    now = datetime.now()
    start_year = now.year if now.month >= 7 else now.year - 1
    return "%d-%02d" % (start_year, (start_year + 1) % 100)


PRESETS = {
    "worldcup2026": {
        "label": "WM 2026 (USA/Mexiko/Kanada)",
        "format": "json",
        "url": "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
        "time_mode": "offset",
        "ko_key": "worldcup2026",
        "translate": True,
    },
    "euro2024": {
        "label": "EM 2024 (Deutschland) - bereits gespielt, taugt als Testdaten",
        "format": "json",
        "url": "https://raw.githubusercontent.com/openfootball/euro.json/master/2024/euro.json",
        "time_mode": "host_local", "host_tz": "Europe/Berlin",
        "ko_key": "euro", "translate": True,
    },
    "euro2028": {
        "label": "EM 2028 (Grossbritannien & Irland)",
        "format": "json",
        "url": "https://raw.githubusercontent.com/openfootball/euro.json/master/2028/euro.json",
        "time_mode": "host_local", "host_tz": "Europe/London",
        "ko_key": "euro", "translate": True,
    },
    "champions-league": {
        "label": "UEFA Champions League",
        "format": "txt",
        "url": "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/cl.txt",
    },
    "europa-league": {
        "label": "UEFA Europa League",
        "format": "txt",
        "url": "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/el.txt",
    },
    "conference-league": {
        "label": "UEFA Conference League",
        "format": "txt",
        "url": "https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/conf.txt",
    },
}


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def team_name(name, translate):
    return TEAMS_DE.get(name, name) if translate else name


# ---------------------------------------------------------------------------
# JSON-Quellen (worldcup.json, euro.json): Schema {"matches": [{"team1",
# "team2", "date", "time", "round", "group"}, ...]}. worldcup.json gibt die
# Zeit inkl. UTC-Offset an ("13:00 UTC-6" - noetig, da die WM ueber mehrere
# Zeitzonen verteilt ist). euro.json gibt nur die Ortszeit im Gastgeberland
# ohne Offset an ("21:00") - dafuer wird die Zeitzone des Gastgeberlandes
# (host_tz) angenommen und explizit nach Zuerich umgerechnet.
# ---------------------------------------------------------------------------

def _kickoff_from_offset(date_str, time_str, target_tz):
    m = re.match(r"(\d{1,2}):(\d{2})\s*UTC([+-]\d+)", time_str.strip())
    if not m:
        raise ValueError("Unerwartetes Zeitformat: %r" % time_str)
    hh, mm, off = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y, mo, d = (int(x) for x in date_str.split("-"))
    src = datetime(y, mo, d, hh, mm, tzinfo=timezone(timedelta(hours=off)))
    return src.astimezone(target_tz).strftime("%Y-%m-%dT%H:%M")


def _kickoff_from_host_local(date_str, time_str, host_tz, target_tz):
    y, mo, d = (int(x) for x in date_str.split("-"))
    if not time_str:
        hh, mm = 12, 0  # Anstoss noch nicht terminiert -> Platzhalter Mittag
    else:
        hh, mm = (int(x) for x in time_str.split(":"))
    src = datetime(y, mo, d, hh, mm, tzinfo=host_tz)
    return src.astimezone(target_tz).strftime("%Y-%m-%dT%H:%M")


def _is_placeholder_team(name):
    """Erkennt Turnier-Platzhalter (noch nicht feststehende Teilnehmer):
    kurze Codes wie 'A1', '2A', 'W97' (kurz + mind. eine Ziffer - echte
    Team-/Laendernamen sind das praktisch nie) sowie ausgeschriebene
    Platzhalter wie 'Winner Group A' oder '3rd Group A/D/E/F'."""
    if len(name) <= 4 and any(c.isdigit() for c in name):
        return True
    return bool(re.match(r"^(Winner|Runner-up|\d(st|nd|rd|th)?\s+Group)\b", name))


def convert_json_source(data, cfg, translate_teams):
    target_tz = _tz(TARGET_TZ_NAME)
    ko_map = KO_ROUNDS.get(cfg["ko_key"], {})
    rows, placeholders, unscheduled = [], 0, 0
    for m in data.get("matches", []):
        rnd = m.get("round", "") or ""
        is_ko = rnd in ko_map
        if is_ko:
            matchday, stage = ko_map[rnd]
        else:
            num = re.search(r"\d+", rnd)
            matchday = num.group(0) if num else "1"
            stage = (m.get("group") or "Gruppe").replace("Group", "Gruppe")
        team1, team2 = m.get("team1", "?"), m.get("team2", "?")
        if _is_placeholder_team(team1) or _is_placeholder_team(team2):
            placeholders += 1
        if not m.get("time"):
            unscheduled += 1
        if cfg["time_mode"] == "offset":
            kickoff = _kickoff_from_offset(m["date"], m["time"], target_tz)
        else:
            kickoff = _kickoff_from_host_local(m["date"], m.get("time"), _tz(cfg["host_tz"]), target_tz)
        rows.append({
            "home": team_name(team1, translate_teams), "away": team_name(team2, translate_teams),
            "kickoff": kickoff, "matchday": matchday, "stage": stage, "knockout": is_ko,
        })
    rows.sort(key=lambda r: r["kickoff"])
    return rows, placeholders, unscheduled


# ---------------------------------------------------------------------------
# football.txt-Quellen (Champions League, Europa League, Conference League -
# und im Prinzip jede andere openfootball-Liga in diesem Format). Aufbau:
#
#   ▪ <Phase>[, <Runde>]              <- Abschnitts-Kopf
#     <Wochentag> <Monat> <Tag> [<Jahr>]   <- Datum (2 Leerzeichen Einzug)
#       <HH:MM>  Team1 (XXX) v Team2 (YYY)  <Ergebnis>   <- Spiel (4+ Einzug)
#              Team2 (XXX) v Team2 (YYY)  <Ergebnis>     <- weiteres Spiel,
#                                                            gleiche Uhrzeit
#
# Wenn der Abschnitts-Kopf schon eine Runde nennt (z.B. "League, Matchday
# 1"), ist die Gruppierung eindeutig. Sonst (z.B. nur "League phase" fuer
# alle 8 Runden in einem Rutsch) werden die Runden anhand von Datumsluecken
# > GAP_THRESHOLD_DAYS auseinandergehalten (typisch: 1-2 Tage Abstand
# innerhalb einer Runde, mehrere Wochen zwischen zwei Runden).
# ---------------------------------------------------------------------------
GAP_THRESHOLD_DAYS = 4
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_SECTION_RE = re.compile(r"^▪\s*(.+?)\s*$")
_DATE_RE = re.compile(r"^\s{2}\S{3}\s+(\w{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_MATCH_RE = re.compile(
    r"^\s{4,}(?:(\d{1,2}:\d{2})\s+)?(.+?\([A-Z]{3}\))\s+v\s+(.+?\([A-Z]{3}\))\s{2,}\S")
_CC_RE = re.compile(r"\s*\([A-Z]{3}\)\s*$")


def _strip_country_code(name):
    return _CC_RE.sub("", name).strip()


def _parse_txt_rows(text):
    """Liest jede Spielzeile ein: (section, datum, zeit, team1, team2)."""
    rows, section, cur_date, cur_year, cur_time = [], None, None, None, None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("▪"):
            section, cur_time = _SECTION_RE.match(line).group(1), None
            continue
        m = _DATE_RE.match(line)
        if m:
            mon, day, year = m.group(1), int(m.group(2)), m.group(3)
            if year:
                cur_year = int(year)
            if cur_year is None:
                continue  # Datum ohne bekanntes Jahr - kann nicht passieren, defensiv
            new_date = datetime(cur_year, _MONTHS[mon], day).date()
            if not year and cur_date and new_date < cur_date:
                # Jahreswechsel ohne explizite Jahreszahl in der Quelle
                # (Saison laeuft z.B. von September bis Mai) - Sicherheitsnetz,
                # falls eine Quelle das Jahr nicht jedes Mal wiederholt.
                cur_year += 1
                new_date = datetime(cur_year, _MONTHS[mon], day).date()
            cur_date, cur_time = new_date, None
            continue
        m = _MATCH_RE.match(line)
        if m and cur_date and section:
            time_s = m.group(1) or cur_time
            cur_time = time_s
            rows.append((section, cur_date, time_s,
                        _strip_country_code(m.group(2)), _strip_country_code(m.group(3))))
    return rows


def convert_txt_source(text):
    raw = _parse_txt_rows(text)
    if not raw:
        raise ValueError("Keine Spiele im Text gefunden - falsches Format oder leere Datei?")

    sections, cur_sec, bucket = [], None, []
    for row in raw:
        if row[0] != cur_sec:
            if bucket:
                sections.append((cur_sec, bucket))
            cur_sec, bucket = row[0], []
        bucket.append(row)
    sections.append((cur_sec, bucket))

    rows = []
    for header, section_rows in sections:
        stage_part, _, extra_part = header.partition(",")
        stage_part, extra_part = stage_part.strip(), extra_part.strip() or None
        is_ko = not any(k in stage_part.lower() for k in ("league", "group", "gruppe"))

        dates = []
        for row in section_rows:
            if row[1] not in dates:
                dates.append(row[1])
        clusters, cur_cluster = [], [dates[0]]
        for prev, d in zip(dates, dates[1:]):
            if (d - prev).days > GAP_THRESHOLD_DAYS:
                clusters.append(cur_cluster)
                cur_cluster = []
            cur_cluster.append(d)
        clusters.append(cur_cluster)
        date_to_cluster = {d: i for i, cl in enumerate(clusters, 1) for d in cl}

        stage_label = STAGE_DE.get(stage_part, stage_part)
        multi = len(clusters) > 1
        for _sec, date, time_s, home, away in section_rows:
            if extra_part:
                # Ueberschrift nennt die Runde schon (z.B. "League, Matchday
                # 1") - eindeutig, ausser die Runde selbst hat mehrere
                # Datumscluster (z.B. Hin-/Rueckspiel wie "Finals, Round of
                # 16"), dann zusaetzlich das Leg anhaengen.
                matchday = "%s (Leg %d)" % (header, date_to_cluster[date]) if multi else header
            elif multi:
                matchday = "%s %d" % (stage_label, date_to_cluster[date])
            else:
                matchday = stage_label
            rows.append({
                "home": home, "away": away,
                "kickoff": datetime.combine(date, datetime.min.time()).strftime("%Y-%m-%dT") +
                          (time_s or "12:00"),
                "matchday": matchday, "stage": stage_label, "knockout": is_ko,
            })
    rows.sort(key=lambda r: r["kickoff"])
    return rows


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--competition", choices=sorted(PRESETS), help="Welches Turnier importieren")
    ap.add_argument("--season", help="Saison fuer Vereinswettbewerbe, z.B. 2025-26 (Default: aktuell/naechste)")
    ap.add_argument("--out", help="Zieldatei (Default: <competition>[-<season>]-import.json)")
    ap.add_argument("--no-translate", action="store_true", help="Team-/Laendernamen NICHT ins Deutsche uebersetzen")
    ap.add_argument("--list", action="store_true", help="Verfuegbare Turniere auflisten und beenden")
    args = ap.parse_args()

    if args.list or not args.competition:
        print("Verfuegbare Turniere (--competition <key>):\n")
        for key, cfg in PRESETS.items():
            print("  %-20s %s" % (key, cfg["label"]))
        print("\nBeispiel: python3 import_helper.py --competition champions-league --season 2025-26")
        return

    cfg = PRESETS[args.competition]
    season = args.season or _current_season()
    url = cfg["url"].format(season=season) if "{season}" in cfg["url"] else cfg["url"]

    print("Lade Spielplan von %s ..." % url)
    try:
        raw_text = fetch(url)
    except Exception as e:
        print("FEHLER beim Download: %s" % e, file=sys.stderr)
        if cfg["format"] == "txt":
            print("Diese Saison ist bei openfootball evtl. noch nicht angelegt (Fixtures "
                  "werden oft erst wenige Wochen vor Saisonstart veroeffentlicht).", file=sys.stderr)
            print("Verfuegbare Saison-Ordner pruefen: "
                  "https://github.com/openfootball/champions-league", file=sys.stderr)
            print("Andere Saison versuchen, z.B.: --season %s" %
                  ("%d-%02d" % (int(season[:4]) - 1, int(season[:4]) % 100)), file=sys.stderr)
        sys.exit(1)

    translate = not args.no_translate and cfg.get("translate", False)
    placeholders = unscheduled = 0
    if cfg["format"] == "json":
        data = json.loads(raw_text)
        rows, placeholders, unscheduled = convert_json_source(data, cfg, translate)
    else:
        rows = convert_txt_source(raw_text)

    out_file = args.out or ("%s%s-import.json" % (
        args.competition, ("-" + season) if "{season}" in cfg["url"] else ""))
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    ko = sum(1 for r in rows if r["knockout"])
    print("Fertig: %d Spiele geschrieben nach %s" % (len(rows), out_file))
    print("  - %d Gruppen-/Liga-Spiele, %d K.-o.-Spiele" % (len(rows) - ko, ko))
    if rows:
        print("  - Anstoss (Schweizer Zeit) von %s bis %s" % (rows[0]["kickoff"], rows[-1]["kickoff"]))
    if placeholders:
        print("\nHinweis: %d Spiele haben noch Platzhalter-Teams (z.B. 'A1', 'W23'), "
              "solange die Teilnehmer nicht feststehen. Vor dem Turnierstart neu importieren, "
              "sobald die echten Teams feststehen." % placeholders)
    if unscheduled:
        print("Hinweis: %d Spiele hatten noch keine offizielle Anstosszeit - Platzhalter "
              "12:00 (Schweizer Zeit) verwendet. Vor Turnierstart pruefen/aktualisieren." % unscheduled)
    print("\nJetzt den Inhalt von %s kopieren und in ORAKEL FC unter" % out_file)
    print("Admin -> Spiele -> 'Spiele importieren (JSON)' einfuegen.")


if __name__ == "__main__":
    main()
