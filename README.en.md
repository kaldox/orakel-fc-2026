<div align="center">

# ORAKEL FC 2026 ⚽🔮

**A self-hosted World Cup 2026 prediction game for your group of friends.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Self-hosted](https://img.shields.io/badge/self--hosted-%E2%9C%93-success)
![UI](https://img.shields.io/badge/UI-EN%20%2F%20DE-informational)

[🇩🇪 Deutsch](README.md) · **🇬🇧 English** · [🟥⚫ Baseldütsch](README.bl.md)

</div>

> *Talk is silver. Correct predictions are gold. Wrong ones are kitchen gossip.*

**Jokers, secret missions, weekly challenges, special awards and chaos events** — and you can keep **adding your own ideas in the browser**, no coding required. Not everyone's thing? A single switch turns it into a **plain prediction game**. A compact **Flask + SQLite** app, everything in **one Docker container**: runs on a Raspberry Pi or any server, behind a reverse proxy for HTTPS.

## Features

- ⚽ **Predictions** that lock at kickoff, plus one risk pick per matchday (×2 / −4)
- 🏆 **Live standings** with a deterministic scoring engine (tendency / goal difference / exact, knockout & underdog bonus)
- 🃏 **Jokers** with automatic effects (double, sabotage, shield, swap, …) — fully extensible
- 🔮 **Secret missions**, 🎯 **weekly challenges**, 🏅 **awards**, 🌀 **chaos events** — all editable in the admin UI
- 🎚️ **Plain-mode switch** — hide all the extras with one click for a classic predictions-only game
- 🌍 **Bilingual UI** (English / German) that follows the browser, switchable any time
- 📱 **Mobile-first**: bottom tab bar, large buttons, first-login tutorial, help page, add-to-home-screen
- 🛠️ **Admin area**: players, fixtures (incl. JSON import), results, manual point adjustments, password reset
- 🔒 **Security**: CSRF protection, login brute-force throttling, sensible security headers, hardened session cookies

## Screenshots

<!-- Drop your PNGs into the docs/ folder, then uncomment this block:
| Standings | Predict | Help |
|:---:|:---:|:---:|
| ![Standings](docs/standings.png) | ![Predict](docs/predict.png) | ![Help](docs/help.png) |
-->

_Add a few screenshots to `docs/` and uncomment the gallery above — see the [Wiki](../../wiki) for a styling guide._

## Documentation

Full guides live in the **[Wiki](../../wiki)**: installation, running it on the internet with HTTPS, the season workflow, scoring rules, backups & updates, and a FAQ.

A helper script (`wm2026_import.py`) pulls the full WC 2026 fixture list from [openfootball](https://github.com/openfootball) and produces the import file (kickoff times converted to your timezone).

---

## Quickstart (Docker)

```bash
git clone https://github.com/kaldox/orakel-fc-2026.git
cd orakel-fc-2026

cp .env.example .env
nano .env            # set SECRET_KEY + ADMIN_PASSWORD!

docker compose up -d --build
```

The app then listens on **`127.0.0.1:8090`**. Generate a strong secret with `openssl rand -hex 32`.

> Just trying it out? Temporarily change the port mapping to `"8090:8090"` to reach it on your LAN at `http://<server-ip>:8090`.

## First login

Open `http://<server>:8090/login` and sign in with the credentials from your `.env` (default user `admin`). The admin account does **not** appear in the standings. Under **Admin → Players** create one account (name + password) per participant.

## Run it on the internet (HTTPS)

You already have a domain and nginx — you just need a vhost:

```bash
# 1. Edit orakel-fc.nginx.conf to use your domain, then:
sudo cp orakel-fc.nginx.conf /etc/nginx/sites-available/orakel-fc
sudo ln -s /etc/nginx/sites-available/orakel-fc /etc/nginx/sites-enabled/

# 2. Test and reload
sudo nginx -t && sudo systemctl reload nginx

# 3. Get HTTPS (certbot adds the 443 block automatically)
sudo certbot --nginx -d orakel.your-domain.tld
```

Point the subdomain's DNS A record at your server's IP (use DDNS/your domain provider's API if your home IP is dynamic).

Prefer a different reverse proxy? **Nginx Proxy Manager** or **Caddy** work just as well — the container only needs to be reachable from whatever sits in front of it. A complete, beginner-friendly operations guide (HTTPS, auto-renewal, security headers, backups, updates) is in **`BETRIEB.md`** *(currently German — an English version is planned)*.

## Season workflow

| Step | Where | What |
|--------|-----|-----|
| **Create players** | Admin → Players | Name + password for each participant |
| **Enter the fixtures** | Admin → Matches | Add matches one by one **or** import as JSON |
| **Assign secret missions** | Admin → Assign missions | Each player gets one — only they can see it |
| **Predictions** | Players, under "Predict" | Locks automatically at kickoff |
| **Enter results** | Admin → Matches | Score, optionally flag "surprise"/"knockout" |
| **Jokers** | Players under "Jokers", admin sees "Joker plays" | Automatic effects calculate themselves |
| **Special cases** | Admin → Adjustments | Manual bonus/malus with a reason |
| **Challenge/award winners** | Admin → Catalog | Pick a winner, points are added automatically |

### Fixture import (JSON)
Paste a list under *Admin → Matches*:
```json
[
  {"home":"Mexico","away":"Poland","kickoff":"2026-06-11T18:00","matchday":"1","stage":"Group A"},
  {"home":"Canada","away":"Switzerland","kickoff":"2026-06-12T21:00","matchday":"1","stage":"Group B","knockout":false}
]
```
Required: `home`, `away`, `kickoff` (`YYYY-MM-DDTHH:MM`). Optional: `matchday`, `stage`, `knockout`. The full WC 2026 fixture list is available for free, no API key needed, from **openfootball** (github.com/openfootball) — convert it into this format once with `wm2026_import.py`.

## ⭐ Add your own ideas (the whole point)

All "catalogs" are **editable in the browser** — no deploy needed. The admin area has a dedicated page to create/edit/delete:

- **Jokers** · **Missions** · **Challenges** · **Awards** · **Chaos events**

A new idea is just a new entry. Start small and keep adding more over the season.

### Joker auto-effects
When creating a joker you pick an `auto_effect`. The app calculates these automatically:

| Effect | Result |
|--------|---------|
| `double` | Doubles the points from **one chosen match** |
| `triple` | Triples **an entire matchday** |
| `allin` | All-in on one match: tendency correct → ×3 for the day, otherwise 0 |
| `lucky` | 0 points on a matchday → 3 consolation points anyway |
| `sabotage` | Halves an opponent's points for one matchday |
| `shield` | Makes a matchday immune to sabotage |
| `swap` | Worst matchday is replaced by the league average |
| `manual` | No automation — you score it yourself via **Adjustments** |

For anything creative that can't be automated (chaos jokers, side bets, water-cooler forfeits): just pick `manual` and book the points under **Admin → Adjustments** with a reason (positive = bonus, negative like `-4` = penalty).

## Scoring

**Per prediction:**
- Correct tendency: **3**
- Correct goal difference: **5**
- Exact result: **8**

**Bonuses (only on a correct tendency):**
- Knockout match: **+2**
- Flagged "surprise": **+3**

**Risk pick** (max one per matchday): correct → **×2**, wrong → **−4**.

Mission, challenge and award points plus manual adjustments are added on top. Standings update live.

## Backup & update

All data lives in a single file: `./data/orakel.db`.
```bash
# Backup
cp data/orakel.db data/orakel-backup-$(date +%F).db
```

**Update** (data is preserved — it lives in a volume):
```bash
git pull        # or copy in the new files
docker compose up -d --build
```

See `BETRIEB.md` for a ready-made backup script and a more detailed update flow.

## Security

- Make sure to change **`SECRET_KEY`** and **`ADMIN_PASSWORD`** in `.env` — the app refuses to start without a `SECRET_KEY`.
- The container binds to `127.0.0.1` — only reachable from outside via your reverse proxy + HTTPS.
- For a small group of friends (5–15 people), 1 worker + SQLite is plenty. Only consider Postgres if you expect heavy concurrent writes.

## Tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install pytest
python3 -m pytest tests/      # 52 tests: scoring engine, login/brute-force/open-redirect, routes
```

---

## Project structure

```
orakel-fc/
├── app.py                  # app setup: config, extensions, blueprint registration
├── extensions.py           # db, csrf (Flask extension instances)
├── models.py                # SQLAlchemy models (Player, Match, Tip, Joker, …)
├── auth.py                  # login, brute-force protection, open-redirect protection, decorators
├── scoring.py                # scoring engine (point calculation, standings)
├── settings.py                # key/value settings (e.g. plain-mode switch)
├── security.py                # HTTP security headers
├── i18n_helpers.py            # language-selection logic (uses i18n.py)
├── i18n.py                    # translation table (German → English)
├── catalog_config.py          # shared config for joker effects & admin catalogs
├── routes/
│   ├── public.py            # player-facing routes (predict, jokers, standings, …)
│   └── admin.py              # admin routes (players, fixtures, catalogs, adjustments)
├── templates/              # all HTML pages
├── static/style.css        # ORAKEL theme (dark, green/gold)
├── tests/                    # pytest suite (scoring, auth, routes)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── orakel-fc.nginx.conf    # ready-made nginx server block
└── .env.example            # config template
```

Have fun — and may the best oracle win. 🏆

---

## License

Released under the **MIT License** (see `LICENSE`). Use, modify and share it freely. Pull requests and ideas are welcome.

## Contributing / running your own instance

1. Clone the repo, `cp .env.example .env` and set the values (`SECRET_KEY`, `ADMIN_PASSWORD`).
2. `docker compose up -d --build` — the app runs on `127.0.0.1:8090`.
3. For internet use, put a reverse proxy with HTTPS in front (Nginx Proxy Manager,
   Caddy, or nginx + certbot) — step by step in `BETRIEB.md`.

> Note: `.env` and the `data/` folder (database) are excluded via `.gitignore` and must **never** be committed.
