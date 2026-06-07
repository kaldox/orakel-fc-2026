FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

EXPOSE 8090

# 1 Worker + Threads: SQLite vertraegt nur einen schreibenden Prozess gut.
# Fuer 5-15 Mitspieler:innen ist das mehr als ausreichend.
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8090", "app:app"]
