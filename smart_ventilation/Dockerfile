FROM python:3.10.10-slim

RUN apt-get update && \
    apt-get install -y wget gnupg2 tzdata && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    echo "deb http://apt.postgresql.org/pub/repos/apt/ $(grep 'VERSION_CODENAME=' /etc/os-release | cut -d'=' -f2)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --fix-missing libpq-dev build-essential postgresql-client-16 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install redis flask-session

EXPOSE 8000

ENV FLASK_APP=application.py
ENV PORT=8000
ENV FLASK_SECRET_KEY=''
ENV REDIS_URL='redis://host.docker.internal:6379'

CMD ["sh", "-c", "python mqtt_client.py & gunicorn --workers 4 --bind 0.0.0.0:$PORT application:app"]