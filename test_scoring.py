"""
Smoke-Test fuer die Wertungs-Engine von ORAKEL FC 2026.

Laeuft komplett gegen eine temporaere SQLite-DB (kein Einfluss auf echte Daten).
Aufruf:  python test_scoring.py
"""
import os
import tempfile

# WICHTIG: DATA_DIR setzen, BEVOR app importiert wird -> Wegwerf-Datenbank.
_tmp = tempfile.mkdtemp(prefix="ofc_test_")
os.environ["DATA_DIR"] = _tmp
os.environ["SECRET_KEY"] = "test"

from datetime import datetime, timedelta
from app import (app, db, Player, Match, Tip, JokerType, JokerPlay,
                 compute_standings)
from werkzeug.security import generate_password_hash


def reset_game_data():
    """Loescht Spiel-Daten, behaelt aber die geseedeten Joker-Typen + Admin."""
    JokerPlay.query.delete()
    Tip.query.delete()
    Match.query.delete()
    Player.query.filter_by(is_admin=False).delete()
    db.session.commit()


def mkplayer(name):
    p = Player(name=name, pw_hash=generate_password_hash("x"), plays=True)
    db.session.add(p)
    db.session.commit()
    return p


def mkmatch(md, home, away, hg, ag, ko=False, surprise=False, days_ago=1):
    m = Match(matchday=md, stage="Test", home=home, away=away,
              kickoff=datetime.now() - timedelta(days=days_ago),
              home_goals=hg, away_goals=ag, finished=True,
              is_knockout=ko, surprise=surprise)
    db.session.add(m)
    db.session.commit()
    return m


def tip(player, match, h, a, risk=False):
    db.session.add(Tip(player_id=player.id, match_id=match.id,
                       home=h, away=a, is_risk=risk))
    db.session.commit()


def row_for(rows, player):
    return next(r for r in rows if r["player"].id == player.id)


failures = []


def check(label, got, want):
    ok = got == want
    print(("  OK  " if ok else " FAIL ") + f"{label}: got {got}, want {want}")
    if not ok:
        failures.append(label)


with app.app_context():
    # ---------- Szenario A: Basis-Wertung ohne Joker ----------
    print("\n[Szenario A] Basis-Wertung (Tendenz/Differenz/Exakt + KO + Ueberraschung)")
    reset_game_data()
    anna = mkplayer("Anna")
    ben = mkplayer("Ben")

    m1 = mkmatch("1", "CH", "BR", 2, 1)                     # 2:1
    m2 = mkmatch("2", "DE", "FR", 0, 1, ko=True, surprise=True)  # 0:1, KO + Ueberraschung

    tip(anna, m1, 2, 1)   # exakt -> 8
    tip(anna, m2, 0, 1)   # exakt + KO(+2) + Ueberraschung(+3) -> 13
    tip(ben, m1, 1, 0)    # Tendenz Heimsieg, Differenz 1 == 1 -> 5
    tip(ben, m2, 1, 0)    # falsche Tendenz -> 0

    rows = compute_standings()
    check("Anna Tipp-Punkte", row_for(rows, anna)["tips"], 21)
    check("Anna Gesamt", row_for(rows, anna)["total"], 21)
    check("Ben Tipp-Punkte", row_for(rows, ben)["tips"], 5)
    check("Ben Gesamt", row_for(rows, ben)["total"], 5)
    check("Rang 1 = Anna", rows[0]["player"].name, "Anna")

    # ---------- Szenario B: Risiko-Tipp + Verdoppler-Joker ----------
    print("\n[Szenario B] Risiko-Tipp (x2) + Verdoppler-Joker")
    reset_game_data()
    anna = mkplayer("Anna")
    ben = mkplayer("Ben")

    m1 = mkmatch("1", "CH", "BR", 2, 1)
    m2 = mkmatch("2", "DE", "FR", 0, 1, ko=True, surprise=True)

    tip(anna, m1, 2, 1)        # 8
    tip(anna, m2, 0, 1)        # 13 (Basis)
    tip(ben, m1, 1, 0, risk=True)   # 5 -> Risiko korrekt -> x2 = 10
    tip(ben, m2, 1, 0)              # 0

    # Anna spielt Verdoppler auf m2 -> Tag von Spieltag "2" zaehlt doppelt: 13 -> 26
    dbl = JokerType.query.filter_by(auto_effect="double").first()
    db.session.add(JokerPlay(player_id=anna.id, joker_type_id=dbl.id,
                             match_id=m2.id, matchday="2"))
    db.session.commit()

    rows = compute_standings()
    ra, rb = row_for(rows, anna), row_for(rows, ben)
    check("Anna Tipp-Punkte (unverdoppelt)", ra["tips"], 21)
    check("Anna Joker-Bonus", ra["joker"], 13)      # 26 - 13
    check("Anna Gesamt (8 + 26)", ra["total"], 34)
    check("Ben Tipp-Punkte (Risiko x2)", rb["tips"], 10)
    check("Ben Joker-Bonus", rb["joker"], 0)
    check("Ben Gesamt", rb["total"], 10)

print("\n" + ("=" * 40))
if failures:
    print(f"FEHLGESCHLAGEN: {len(failures)} Checks -> {failures}")
    raise SystemExit(1)
print("Alle Checks bestanden. Die Wertungs-Engine rechnet korrekt.")
