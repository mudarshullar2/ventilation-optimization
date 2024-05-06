**## Lüftungsoptimierungssystem**

Dieses Projekt implementiert ein Lüftungsoptimierungssystem, das Echtzeitdaten von verschiedenen Sensoren sammelt und verarbeitet, um die Luftqualität in Innenräumen zu verbessern. Das System verwendet MQTT zur Datenübertragung und maschinelles Lernen zur Vorhersage der Luftqualität.

**# Features**

## **Echtzeit-Sensordatenerfassung: **
Sammelt Daten über Temperatur, Luftfeuchtigkeit, CO2, TVOC und Umgebungstemperatur.
## Machine Learning Integration: 
Nutzt vorab trainierte Modelle (Logistische Regression, Entscheidungsbaum, Random Forest), um Vorhersagen zur Luftqualität zu treffen.
## Datenspeicherung und -verarbeitung: 
Sammelt und aggregiert Sensorwerte, um durchschnittliche Umgebungszustände zu berechnen.
## Webinterface: 
Ein Flask-basiertes Dashboard zur Anzeige der gesammelten Daten und Vorhersagen.


**# Systemarchitektur**
Die Anwendung setzt sich aus mehreren Hauptkomponenten zusammen:

## **Flask-Server:**
Bietet ein Webinterface zur Interaktion mit dem System.
## **MQTT-Client:** 
Kommuniziert mit IoT-Geräten, um Sensordaten in Echtzeit zu empfangen.
## **Data Processing:** 
Verarbeitet die empfangenen Daten, führt Vorhersagen durch und stellt diese Daten über das Webinterface bereit.
## **E-Mail Benachrichtigung:** 
Erlaubt das Senden von E-Mails durch Formulareingaben über das Webinterface.

**# Installation**

**## 1. Voraussetzungen installieren:**
pip install -r requirements.txt

**## 2. Vorab trainierte ML-Modelle bereitstellen:**
Stellen Sie sicher, dass die ML-Modelle im Verzeichnis smart-ventilation/models vorhanden sind.

**## 3. Konfigurationsdatei anpassen:**
Aktualisieren Sie die api_config.yaml mit den entsprechenden API-Schlüsseln und URLs.

**## 4. MQTT-Server Konfiguration:**
Richten Sie die Verbindung zu Ihrem MQTT-Server ein, wie in der Klasse MQTTClient beschrieben.

**# Nutzung**

**Starten Sie das System mit:**
python application.py

Besuchen Sie dann http://localhost:5000 in Ihrem Webbrowser, um auf das Dashboard zuzugreifen.

**# APIs**

Das System kommuniziert mit externen APIs zur Datenübermittlung und um Feedback zu empfangen. Die relevanten Endpunkte und Authentifizierungsdetails sind in der api_config.yaml definiert.

**# Sicherheitshinweise**

## **API-Schlüssel:**
Vermeiden Sie es, Ihre API-Schlüssel und andere sensible Informationen in Ihrem Code hart zu codieren.

## **MQTT-Sicherheit:**
Verwenden Sie TLS/SSL zur Verschlüsselung Ihrer MQTT-Kommunikation.
