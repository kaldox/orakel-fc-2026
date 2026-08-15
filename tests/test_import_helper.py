# -*- coding: utf-8 -*-
"""
Tests fuer import_helper.py: der football.txt-Parser (Champions League,
Europa League, ...) und der JSON-Parser (WM/EM) laufen ohne Netzwerkzugriff
gegen kleine, von Hand nachgebaute Beispielausschnitte im echten
openfootball-Format (siehe Kommentare - 1:1 abgeschaut von echten Daten).
"""
from datetime import timezone, timedelta

import import_helper as ih


# ── football.txt-Parser ──────────────────────────────────────────────────

CL_SNIPPET = """\
= UEFA Champions League 2024/25

# Date       Tue Sep 17 2024 - Sat May 31 2025 (256d)



▪ League, Matchday 1
  Tue Sep 17 2024
    18:45  BSC Young Boys (SUI)    v Aston Villa FC (ENG)     0-3 (0-2)
           Juventus FC (ITA)       v PSV (NED)                3-1 (2-0)
    21:00  Real Madrid CF (ESP)    v VfB Stuttgart (GER)      3-1 (0-0)


▪ League, Matchday 2
  Tue Oct 1
    18:45  VfB Stuttgart (GER)     v AC Sparta Praha (CZE)    1-1 (1-1)


▪ Finals, Round of 16
  Tue Mar 4
    21:00  Real Madrid CF (ESP)    v Club Atlético de Madrid (ESP)  2-1 (1-1)
  Tue Mar 11
    21:00  Club Atlético de Madrid (ESP) v Real Madrid CF (ESP)     1-0 (1-0)
"""

# Ausschnitt im "keine Matchday-Nummer im Kopf"-Stil (Europa League): eine
# einzige Ueberschrift ueber mehrere Runden, Trennung nur ueber Datumsluecken.
EL_SNIPPET = """\
= UEFA Europa League 2024/25



▪ League phase
  Wed Sep 25 2024
    18:45  AZ Alkmaar (NED)        v IF Elfsborg (SWE)        3-2 (1-1)
  Thu Oct 3
    18:45  Manchester United (ENG) v FC Twente (NED)          1-1 (1-0)


▪ Final
  Wed May 21 2025
    21:00  Tottenham Hotspur (ENG) v Manchester United (ENG)  1-0 (1-0)
"""


def test_txt_parser_erkennt_matchday_aus_ueberschrift():
    rows = ih.convert_txt_source(CL_SNIPPET)
    md1 = [r for r in rows if r["matchday"] == "League, Matchday 1"]
    assert len(md1) == 3
    assert all(not r["knockout"] for r in md1)
    assert md1[0]["stage"] == "Liga-Phase"


def test_txt_parser_mehrere_spiele_gleiche_uhrzeit():
    rows = ih.convert_txt_source(CL_SNIPPET)
    young_boys = next(r for r in rows if r["home"] == "BSC Young Boys")
    juventus = next(r for r in rows if r["home"] == "Juventus FC")
    # Beide Spiele stehen unter der gleichen 18:45-Zeitmarke (zweite Zeile
    # hat keine eigene Uhrzeit - muss die vorherige uebernehmen).
    assert young_boys["kickoff"] == juventus["kickoff"] == "2024-09-17T18:45"


def test_txt_parser_zweibeinige_ko_runde_wird_getrennt():
    rows = ih.convert_txt_source(CL_SNIPPET)
    r16 = [r for r in rows if r["stage"] == "K.-o.-Phase"]
    assert len(r16) == 2
    assert r16[0]["knockout"] and r16[1]["knockout"]
    # Hin- und Rueckspiel (7 Tage Abstand) muessen unterschiedliche
    # matchday-Werte bekommen, sonst landen sie auf der Tippen-Seite in
    # derselben Gruppe und der Risiko-Tipp koennte nur fuer eines gelten.
    assert r16[0]["matchday"] != r16[1]["matchday"]


def test_txt_parser_ohne_matchday_nummer_clustert_per_datumsluecke():
    rows = ih.convert_txt_source(EL_SNIPPET)
    league = [r for r in rows if r["stage"] == "Liga-Phase"]
    matchdays = {r["matchday"] for r in league}
    # Sep 25 und Oct 3 liegen 8 Tage auseinander -> zwei getrennte Runden.
    assert len(matchdays) == 2
    final = [r for r in rows if r["stage"] == "Finale"]
    assert len(final) == 1
    assert final[0]["matchday"] == "Finale"  # einzelnes Spiel, kein Suffix noetig


def test_txt_parser_jahreswechsel_wird_uebernommen():
    rows = ih.convert_txt_source(CL_SNIPPET)
    r16 = sorted((r for r in rows if r["stage"] == "K.-o.-Phase"), key=lambda r: r["kickoff"])
    assert r16[0]["kickoff"].startswith("2025-03-04")
    assert r16[1]["kickoff"].startswith("2025-03-11")


def test_txt_parser_laendercode_wird_entfernt():
    rows = ih.convert_txt_source(CL_SNIPPET)
    names = {r["home"] for r in rows} | {r["away"] for r in rows}
    assert "BSC Young Boys" in names
    assert "BSC Young Boys (SUI)" not in names


# ── JSON-Parser (WM/EM) ───────────────────────────────────────────────────

WORLDCUP_SNIPPET = {
    "matches": [
        {"round": "Group Stage - 1", "date": "2026-06-11", "time": "18:00 UTC-6",
         "team1": "Mexico", "team2": "Poland", "group": "Group A"},
        {"round": "Final", "date": "2026-07-19", "time": "12:00 UTC-4",
         "team1": "Winner SF1", "team2": "Winner SF2"},
    ],
}

EURO_SNIPPET = {
    "matches": [
        {"round": "Matchday 1", "date": "2024-06-14", "time": "21:00",
         "team1": "Germany", "team2": "Scotland", "group": "Group A"},
        {"round": "Round of 16", "date": "2024-06-29", "time": "18:00",
         "team1": "Switzerland", "team2": "Italy"},
    ],
}


def test_json_parser_worldcup_utc_offset_und_uebersetzung():
    cfg = ih.PRESETS["worldcup2026"]
    rows, placeholders, unscheduled = ih.convert_json_source(WORLDCUP_SNIPPET, cfg, translate_teams=True)
    mex = next(r for r in rows if r["stage"] == "Gruppe A")
    assert mex["home"] == "Mexiko" and mex["away"] == "Polen"
    # 18:00 UTC-6 -> Zuerich ist zu dem Zeitpunkt UTC+2 -> +8h -> 02:00 naechster Tag
    assert mex["kickoff"] == "2026-06-12T02:00"
    final = next(r for r in rows if r["knockout"])
    assert final["stage"] == "Finale"
    assert placeholders == 1  # "Winner SF1"/"Winner SF2"


def test_json_parser_euro_host_timezone_konvertierung():
    cfg_2024 = dict(ih.PRESETS["euro2024"])
    cfg_2028 = dict(ih.PRESETS["euro2028"])
    rows_de, _, _ = ih.convert_json_source(EURO_SNIPPET, cfg_2024, translate_teams=True)
    rows_uk, _, _ = ih.convert_json_source(EURO_SNIPPET, cfg_2028, translate_teams=True)
    group_de = next(r for r in rows_de if r["stage"] == "Gruppe A")
    group_uk = next(r for r in rows_uk if r["stage"] == "Gruppe A")
    # Deutschland (Gastgeber 2024) hat im Sommer dieselbe Zeitzone wie Zuerich.
    assert group_de["kickoff"] == "2024-06-14T21:00"
    # UK (Gastgeber 2028) liegt im Sommer 1h hinter Zuerich -> +1h Korrektur.
    assert group_uk["kickoff"] == "2024-06-14T22:00"
    ko_uk = next(r for r in rows_uk if r["knockout"])
    assert ko_uk["stage"] == "Achtelfinale"


def test_json_parser_ohne_uebersetzung_laesst_originalnamen():
    cfg = ih.PRESETS["worldcup2026"]
    rows, _, _ = ih.convert_json_source(WORLDCUP_SNIPPET, cfg, translate_teams=False)
    mex = next(r for r in rows if r["stage"] == "Gruppe A")
    assert mex["home"] == "Mexico" and mex["away"] == "Poland"


# ── Platzhalter-Erkennung ─────────────────────────────────────────────────

def test_platzhalter_erkennung():
    for name in ["A1", "2A", "W97", "Winner Group A", "3rd Group A/B/C"]:
        assert ih._is_placeholder_team(name), name
    for name in ["Wales", "Brasilien", "FC Bayern München", "USA"]:
        assert not ih._is_placeholder_team(name), name


# ── Saisonschaetzung ────────────────────────────────────────────────────

def test_current_season_format():
    season = ih._current_season()
    assert len(season) == 7 and season[4] == "-"
