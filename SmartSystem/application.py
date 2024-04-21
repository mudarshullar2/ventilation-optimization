from database_management import get_sensor_data_last_month
from data_generation import get_latest_sensor_data
from generating_plots import generate_plot
from load_api import load_api_config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, send_file
import joblib
import pandas as pd
import smtplib
import requests
import logging

app = Flask(__name__, static_folder='/Users/mudarshullar/Desktop/SmartSystemVS_1/SmartSchoolsAISystem/SmartSystem/static')

# Das vortrainierte Machine-Learning-Modell laden
model = joblib.load("/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl")

# Pfad zu Ihrer YAML-Konfigurationsdatei
config_file_path = 'SmartSystem/api_config.yaml'

# API-Konfiguration aus YAML-Datei laden
api_config = load_api_config(config_file_path)

# API-Schlüssel und Basis-URL extrahieren
READ_API_KEY = api_config['READ_API_KEY']
POST_DELETE_API_KEY = api_config['POST_DELETE_API_KEY']
API_BASE_URL = api_config['API_BASE_URL']


@app.route("/")
def index():
    """
    Ruft Sensordaten von einer API ab und rendert eine HTML-Seite mit den neuesten Sensorwerten.
    :return: HTML-Seite mit den extrahierten Sensorwerten oder eine Fehlermeldung im Falle eines Fehlers.
    """
    try:
        headers = {"X-Api-Key": READ_API_KEY}  # HTTP-Header mit dem API-Schlüssel definieren
        response = requests.get(API_BASE_URL, headers=headers)  # GET-Anfrage an die API senden

        if response.status_code == 200:
            data = response.json()  # Die Antwort in JSON-Format konvertieren
            logging.info("Received data:", data)  # Debugging-Ausgabe der empfangenen Daten

            if isinstance(data, list) and data:  # Überprüfen, ob die Daten eine nicht leere Liste sind
                all_sensor_data = [item for sublist in data for item in sublist]
                logging.info("All sensor data:", all_sensor_data)  # Debugging-Ausgabe der Sensordaten

                if all_sensor_data:  # Überprüfen, ob Sensordaten vorhanden sind
                    # Die neuesten Sensordaten basierend auf dem Zeitstempel extrahieren
                    latest_data = max(all_sensor_data, key=lambda x: x.get("time"))
                    logging.info("Latest data:", latest_data)  # Debugging-Ausgabe der neuesten Daten

                    # Sicherstellen, dass die neuesten Daten alle erforderlichen Schlüssel enthalten
                    required_keys = ["time", "temperature", "humidity", "co2", "accurate_prediction"]
                    if all(key in latest_data for key in required_keys):
                        # Die erforderlichen Felder aus den neuesten Daten extrahieren
                        timestamp = latest_data.get("time")
                        temperature = latest_data.get("temperature")
                        humidity = latest_data.get("humidity")
                        co2 = latest_data.get("co2")
                        accurate_prediction = latest_data.get("accurate_prediction")

                        # Die HTML-Seite mit den extrahierten Sensorwerten rendern
                        return render_template(
                            "index.html",
                            sensor_data=latest_data,
                            timestamp=timestamp,
                            temperature=temperature,
                            humidity=humidity,
                            co2=co2,
                            accurate_prediction=accurate_prediction
                        )
                    else:
                        return "Die neuesten Daten enthalten nicht alle erforderlichen Schlüssel."

                else:
                    return "Keine Sensordaten verfügbar."

            else:
                return "Die empfangenen Daten entsprechen nicht dem erwarteten Format."

        else:
            return f"Abrufen der Sensordaten fehlgeschlagen. Statuscode: {response.status_code}"

    except Exception as e:
        logging.info("Fehler in index() aufgetreten:", str(e))  # Debugging statement
        return f"Fehler: {str(e)}"


@app.route("/plots")
def plots():
    """
    Generiert und rendert verschiedene Diagramme basierend auf den neuesten Sensordaten.
    :return: HTML-Seite mit den generierten Diagrammen oder eine Fehlermeldung, falls keine Sensordaten verfügbar sind.
    """

    # Die neuesten Sensordaten abrufen
    sensor_data = get_latest_sensor_data()

    # Überprüfen, ob Sensordaten vorhanden sind
    if sensor_data:
        # Debugging-Ausgabe der empfangenen Sensordaten
        logging.info("Erhaltene Sensordaten PLOTS FUNKTION:", sensor_data)

        # Individuelle Plots generieren
        temperature_plot = generate_plot(
            sensor_data, 'time', 'temperature', "Temperature Plot"
        )
        humidity_plot = generate_plot(
            sensor_data, 'time', 'humidity', "Humidity Plot"
        )
        co2_plot = generate_plot(
            sensor_data, 'time', 'co2', "CO2 Level Plot"
        )
        tvoc_plot = generate_plot(
            sensor_data, 'time', 'accurate_prediction', "TVOC Level Plot"
        )

        # Die HTML-Seite mit den generierten Plots rendern
        return render_template(
            "plots.html",
            temperature_plot=temperature_plot,
            humidity_plot=humidity_plot,
            co2_plot=co2_plot,
            tvoc_plot=tvoc_plot
        )
    else:
        return "Keine Sensordaten verfügbar für Plots."


@app.route("/feedback", methods=["POST"])
def feedback():
    """
    Verarbeitet das Feedback, das über ein Formular gesendet wurde.
    :return: Weiterleitung zur Indexseite nach erfolgreicher Verarbeitung des Feedbacks
    """

    try:
        # Konvertiere das Feedback zu einer Ganzzahl (0 oder 1)
        is_correct = int(request.form["is_correct"])
        payload = {
            "temperature": request.form["temperature"],  # Temperaturwert aus dem Payload
            "humidity": request.form["humidity"],  # Luftfeuchtigkeitswert aus dem Payload
            "co2": request.form["co2"],  # CO2-Level aus dem Payload
            "accurate_prediction": is_correct,  # Genauigkeitsbewertung des Modells (0 oder 1)
        }
        headers = {
            "X-Api-Key": POST_DELETE_API_KEY,  # API-Schlüssel für den POST-Request
            "Content-Type": "application/json",  # Angegebener Inhaltstyp für die Anfrage
        }
        response = requests.post(API_BASE_URL, headers=headers, json=payload)  # POST-Anfrage an die API senden
        if response.status_code == 200:
            feedback_message = (
                "Vielen Dank! Dein Feedback wird die Genauigkeit "
                "des Modells verbessern!"
            )
        else:
            feedback_message = "Feedback konnte nicht gespeichert werden."
            # HTML-Seite mit Rückmeldung rendern
        return render_template("feedback.html", feedback_message=feedback_message)

    except Exception as e:
        return f"Fehler: {str(e)}"


@app.route("/download_co2_data", methods=["GET"])
def download_co2_data():
    """
    Ruft Sensordaten der letzten Woche ab und erstellt eine Excel-Datei mit diesen Daten sowie deskriptive Statistiken.
    :return: Sendet die erstellte Excel-Datei als Download, falls Sensordaten vorhanden sind; ansonsten eine Fehlermeldung.
    """
    try:
        # Sensordaten des letzten Monats abrufen
        sensor_data = get_sensor_data_last_month()
        # Überprüfen, ob Sensordaten vorhanden sind
        if sensor_data:
            df = pd.DataFrame(sensor_data, columns=["Timestamp", "Temperature", "Humidity", "CO2", "TVOC"])
            descriptive_stats = df.describe()  # Deskriptive Statistiken über die Sensordaten berechnen
            # Excel-Datei erstellen
            output_path = "co2_data_last_month.xlsx"
            with pd.ExcelWriter(output_path) as writer:
                df.to_excel(writer, index=False, sheet_name="Sensor Data")
                descriptive_stats.to_excel(writer, sheet_name="Descriptive Statistics")
            # Excel-Datei als Download senden
            return send_file(output_path, as_attachment=True)
        else:
            return "Keine Sensordaten verfügbar für den letzten Monat."
    except Exception as e:
        return f"Fehler: {str(e)}"


# Neue Route zum Rendern von contact.html
@app.route('/contact')
def contact():
    """
    Rendert die contact.html-Seite.
    :return: Die gerenderte HTML-Seite contact.html.
    """
    return render_template('contact.html')


receiver_email = "mudarshullar22@gmail.com"


@app.route('/send_email', methods=['POST'])
def send_email():
    """
    Verarbeitet das Senden einer E-Mail über ein Formular.
    :return: Eine Bestätigungsmeldung bei erfolgreicher E-Mail-Zustellung oder eine Fehlermeldung.
    """
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        try:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587

            # Sichere Verbindung zum SMTP-Server von Gmail herstellen
            smtp = smtplib.SMTP(smtp_server, smtp_port)
            smtp.starttls()

            # Anmelden beim SMTP-Server von Gmail mit Ihren Anmeldeinformationen
            gmail_user = 'your_email@gmail.com'  # Durch Gmail-Adresse ersetzen
            gmail_password = 'your_password'  # Durch Ihr Gmail-Passwort ersetzen
            smtp.login(gmail_user, gmail_password)

            # E-Mail-Nachricht erstellen
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = receiver_email
            msg['Subject'] = f"New Message from {name} ({email})"
            msg.attach(MIMEText(message, 'plain'))

            # E-Mail senden
            smtp.sendmail(email, receiver_email, msg.as_string())

            # SMTP-Verbindung beenden
            smtp.quit()

            return "E-Mail erfolgreich gesendet!"
        except Exception as e:
            return f"Fehler: {str(e)}"


if __name__ == "__main__":
    app.run(debug=True)
