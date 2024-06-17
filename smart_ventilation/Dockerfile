# Python-Image von Docker Hub für die Version 3.10.10
FROM python:3.10.10-slim

# Core dependencies für PostgreSQL 16 client
RUN apt-get update && \
    apt-get install -y wget gnupg2 && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ $(grep 'VERSION_CODENAME=' /etc/os-release | cut -d'=' -f2)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y libpq-dev build-essential postgresql-client-16 postgresql-contrib && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis für Backend festlegen
WORKDIR /app

# den Inhalt des aktuellen Verzeichnisses in den Container unter /app kopieren
COPY . /app

# Packages installieren 
RUN pip install --no-cache-dir -r requirements.txt

# Port, auf dem die Flask-Anwendung läuft 
EXPOSE 8000

# Umgebungsvariable definieren
ENV FLASK_APP=application.py
ENV PORT=8000

# Befehl ausführen, um den MQTT-Client und die Flask-Anwendung zu starten
CMD ["sh", "-c", "python mqtt_client.py & gunicorn --workers 4 --bind 0.0.0.0:$PORT application:app"]
