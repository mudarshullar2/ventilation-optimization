# Python-Image von Docker Hub für die Version 3.10.10
FROM python:3.10.10-slim

# Core-Abhängigkeiten für PostgreSQL 16 Client und Zeitzonendaten
RUN apt-get update && \
    apt-get install -y wget gnupg2 tzdata && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ $(grep 'VERSION_CODENAME=' /etc/os-release | cut -d'=' -f2)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --fix-missing libpq-dev build-essential postgresql-client-16 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Zeitzone setzen
ENV TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Arbeitsverzeichnis für Backend festlegen
WORKDIR /app

# Den Inhalt des aktuellen Verzeichnisses in den Container unter /app kopieren
COPY . /app

# Packages installieren
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install redis flask-session

# Port, auf dem die Flask-Anwendung läuft
EXPOSE 8000

# Umgebungsvariablen definieren
ENV FLASK_APP=application.py
ENV PORT=8000
ENV FLASK_SECRET_KEY='5b8d0ad3179d0b0bf3d8e12a98f5b309'
ENV REDIS_URL='redis://host.docker.internal:6379'

# Befehl ausführen, um den MQTT-Client und die Flask-Anwendung zu starten
CMD ["sh", "-c", "python mqtt_client.py & gunicorn --workers 4 --bind 0.0.0.0:$PORT application:app"]