# Betrieb & Produktion – ORAKEL FC 2026

Diese Anleitung beschreibt den **laufenden Betrieb** deiner Installation: HTTPS,
Reverse Proxy, Zertifikate, Sicherheit, Backups und Updates. Sie ist auf dein
tatsächliches Setup zugeschnitten:

- **Raspberry Pi** (`dockert`) mit **Docker**
- **Nginx Proxy Manager (NPM)** als Reverse Proxy (Container)
- Domain **example.com** mit Subdomains, Port 80/443 im Router auf den Pi weitergeleitet
- ORAKEL FC läuft als Container im gemeinsamen Docker-Netz **`proxy`**, ohne eigenen Host-Port

> Hinweis: In deinem Setup übernimmt **NPM** die Aufgaben „HTTPS", „Reverse Proxy"
> und „Zertifikatserneuerung" automatisch. Du brauchst **kein** separates Nginx/Caddy
> und **kein** certbot auf dem Pi. Die mitgelieferte Datei `orakel-fc.nginx.conf` ist
> nur für ein klassisches Host-Nginx gedacht und in deinem Fall **nicht** in Gebrauch.

---

## 1. Architektur in einem Bild

```
Browser (Handy/PC)
   │  https://orakel.example.com
   ▼
Öffentliches DNS  →  A-Record auf deine WAN-IP
   ▼
Router  →  Portweiterleitung 80/443 auf den Pi (192.168.1.50)
   ▼
Nginx Proxy Manager  →  TLS/HTTPS, wählt per Hostname den Dienst
   ▼  (Docker-Netz "proxy", per Container-Name)
orakel-fc  →  gunicorn :8090  →  Flask  →  SQLite (/app/data/orakel.db)
```

Jede Schicht hat eine Aufgabe. Die App selbst veröffentlicht **keinen** Port – nur
NPM erreicht sie intern. Das verhindert Port-Konflikte und hält die App aus dem LAN.

---

## 2. HTTPS / Let's Encrypt (über NPM)

Im NPM-Web-UI unter **Hosts → Proxy Hosts → Add Proxy Host**:

**Reiter Details**
- Domain Names: `orakel.example.com`
- Scheme: `http`
- Forward Hostname / IP: `orakel-fc`  (Container-Name, **nicht** die IP)
- Forward Port: `8090`  (interner Port)
- Block Common Exploits: **an**
- Websockets Support: **an**

**Reiter SSL**
- SSL Certificate: **Request a new SSL Certificate**
- Force SSL: **an**
- HTTP/2 Support: **an**
- HSTS Enabled: **an** (sorgt dafür, dass Browser nur noch HTTPS nutzen)
- Let's-Encrypt-AGB akzeptieren → **Save**

Voraussetzungen, damit das Zertifikat ausgestellt werden kann:
- DNS-A-Record der Subdomain zeigt auf deine WAN-IP.
- Router leitet Port **80 und 443** auf den Pi weiter (80 wird für die Domain-Prüfung gebraucht).

---

## 3. Automatische Zertifikatserneuerung

**Nichts zu tun** – NPM erneuert Let's-Encrypt-Zertifikate automatisch (rund 30 Tage
vor Ablauf, Gültigkeit je 90 Tage). Kontrolle bei Bedarf:

- NPM → **SSL Certificates**: dort siehst du je Zertifikat das Ablaufdatum und „Renew".
- Eine manuelle Erneuerung ist nur nötig, wenn etwas schiefgelaufen ist (dann „Renew Now").

Wichtig ist nur, dass Port 80 von außen erreichbar bleibt – sonst scheitert die Erneuerung.

---

## 4. Sicherheits-Header

**Die App setzt die wichtigsten Sicherheitsheader ab sofort selbst** – du musst
dafür nichts tun. Bei jeder Antwort werden gesetzt:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- eine tolerante `Content-Security-Policy` (erlaubt Google Fonts + Inline-Styles)
- `Strict-Transport-Security` (HSTS), sobald der Zugriff über HTTPS läuft

Zusätzlich aktivierst du in NPM oben **Block Common Exploits**, **Force SSL** und
**HSTS** – das ist die Verstärkung auf Proxy-Ebene. Eigene Header bräuchtest du nur,
wenn du etwas verschärfen willst (Proxy-Host → **Advanced**, Feld „Custom Nginx
Configuration"). Doppelte Header schaden nicht.

> Eine strenge **Content-Security-Policy (CSP)** ist bewusst **nicht** vorgegeben:
> Die App lädt Schriften von Google Fonts und nutzt einige Inline-Styles/-Skripte.
> Eine zu strenge CSP würde das Layout zerschießen. Wer es trotzdem will, sollte
> `fonts.googleapis.com`/`fonts.gstatic.com` sowie `'unsafe-inline'` erlauben und gut testen.

Test der Header (von einem PC):
```bash
curl -sI https://orakel.example.com/ | grep -iE "strict-transport|x-frame|x-content|referrer"
```

---

## 5. Backups

Alle App-Daten stecken in **einer Datei**: `~/orakel-fc/data/orakel.db`
(Spieler, Tipps, Spiele, Joker, Ergebnisse). Zusätzlich lohnt ein Backup der
**NPM-Konfiguration** (Proxy-Hosts + Zertifikate).

### 5.1 Einfaches tägliches Backup der Spiel-Datenbank

Skript `~/backup-orakel.sh`:
```bash
#!/bin/bash
set -e
BACKUP_DIR=~/backups
mkdir -p "$BACKUP_DIR"
TS=$(date +%F_%H%M)

# Konsistente Kopie (auch wenn die App gerade schreibt):
docker exec orakel-fc python -c "import sqlite3; s=sqlite3.connect('/app/data/orakel.db'); d=sqlite3.connect('/app/data/_backup.db'); s.backup(d); d.close(); s.close()"
docker cp orakel-fc:/app/data/_backup.db "$BACKUP_DIR/orakel-$TS.db"
docker exec orakel-fc rm -f /app/data/_backup.db

# Backups älter als 30 Tage aufräumen
find "$BACKUP_DIR" -name 'orakel-*.db' -mtime +30 -delete
echo "Backup: $BACKUP_DIR/orakel-$TS.db"
```
Ausführbar machen und täglich um 03:00 per Cron laufen lassen:
```bash
chmod +x ~/backup-orakel.sh
crontab -e
# folgende Zeile einfügen:
0 3 * * * /home/docker/backup-orakel.sh >> /home/docker/backups/backup.log 2>&1
```

### 5.2 NPM-Daten sichern
NPM legt Konfiguration und Zertifikate in seinen Volumes/Ordnern ab (meist
`data/` und `letsencrypt/` im NPM-Verzeichnis). Sichere diese Ordner gelegentlich mit
(Pfad an dein NPM-Verzeichnis anpassen):
```bash
tar czf ~/backups/npm-$(date +%F).tgz -C ~/<npm-verzeichnis> data letsencrypt
```

### 5.3 Wiederherstellen der Spiel-Datenbank
```bash
cd ~/orakel-fc
docker compose down
cp ~/backups/orakel-2026-06-15_0300.db data/orakel.db   # gewünschtes Backup
docker compose up -d
docker restart Nginx_Proxy_Manager
```

---

## 6. Updates einspielen

Wenn du eine neue Version (`orakel-fc.zip`) bekommst:

```bash
# 1. Zip auf den Pi kopieren (vom PC):
#    scp "$env:USERPROFILE\Downloads\orakel-fc.zip" docker@192.168.1.50:~/

# 2. Auf dem Pi entpacken (überschreibt nur Programmdateien; data/ und .env bleiben):
cd ~
unzip -o orakel-fc.zip -d ~/
sudo chown -R docker:docker ~/orakel-fc        # nur nötig, falls mit sudo entpackt

# 3. Im Projektordner neu bauen + ggf. Migration + NPM auffrischen:
cd ~/orakel-fc
docker compose up -d --build
# Falls ein Migrationsskript mitgeliefert wird (z.B. fix_umlauts.py), einmal:
# docker compose exec orakel-fc python fix_umlauts.py
docker restart Nginx_Proxy_Manager
```

**Warum der NPM-Neustart?** Beim Neubau bekommt der Container eine neue interne
IP. NPM merkt sich die alte und liefert sonst „502 Bad Gateway". Ein Neustart von
NPM frischt das auf.

**Kontrolle nach dem Update:**
```bash
docker compose ps                                   # orakel-fc "healthy"
curl -sI https://orakel.example.com/login | head -1 # HTTP/1.1 200 OK
```

> `data/` (die Datenbank) und `.env` liegen nicht im Zip und werden beim Update
> nie überschrieben. Trotzdem vor größeren Updates ein Backup ziehen (Abschnitt 5).

---

## 7. Routine-Checks & Fehlersuche

| Symptom | Wahrscheinliche Ursache | Lösung |
|---------|------------------------|--------|
| 502 Bad Gateway | NPM hat alte Container-IP | `docker restart Nginx_Proxy_Manager` |
| Seite nicht erreichbar | Container aus / ungesund | `cd ~/orakel-fc && docker compose ps`, ggf. `up -d` |
| Zertifikat-Fehler | Port 80 nicht erreichbar / DNS falsch | Portweiterleitung & A-Record prüfen |
| „no configuration file provided" | Falscher Ordner | erst `cd ~/orakel-fc`, dann `docker compose …` |
| Änderungen wirken nicht | Image nicht neu gebaut | `docker compose up -d --build` |

Nützliche Befehle:
```bash
cd ~/orakel-fc
docker compose logs --tail=50      # App-Logs
docker compose ps                  # Status/Health
docker stats orakel-fc --no-stream # CPU/RAM
```

---

## 8. Spieler einladen (Vorlage)

Login läuft über **Name + Passwort**, das du als Spielleitung vergibst
(Admin → Spieler). Eine Einladung kann so aussehen:

```
🎉 Willkommen zum ORAKEL FC – unserem WM-Tippspiel!

Tippe die Spiele der WM 2026 und sammle Punkte gegen den Rest der Truppe.

📱 Läuft direkt im Browser – nichts installieren
⚽ Tipp in wenigen Sekunden abgegeben
🃏 Coole Joker für extra Spannung
🏆 Laufende Rangliste

Dein Zugang:
🔗 Link:        https://orakel.example.com
👤 Benutzer:    {NAME}
🔑 Passwort:    {PASSWORT}

Tipp: Beim ersten Öffnen erscheint eine kurze Einführung. Viel Erfolg! 🍀
```

Ersetze `{NAME}` und `{PASSWORT}` pro Person. Aus Sicherheitsgründen lassen sich
Passwörter nicht auslesen – wenn jemand seins vergisst, setzt du im Admin einfach
ein neues, indem du die Person neu anlegst (oder wir ergänzen später eine
„Passwort ändern"-Funktion für Spieler).

---

## 9. Gut zu wissen

- **watchtower** aktualisiert nur Images aus einer Registry. ORAKEL FC wird lokal
  gebaut (kein Registry-Image) und daher **nicht** automatisch verändert – Updates
  machst du bewusst über Abschnitt 6.
- Für ~5–15 Mitspieler:innen sind 1 gunicorn-Worker + SQLite mehr als genug.
- Die Zeitsperre der Tipps richtet sich nach der **Serverzeit** des Pi
  (Europe/Zurich). Stelle sicher, dass die Pi-Uhr korrekt geht (`timedatectl`).
