# Projekt zur Optimierung des Lüftungsverhaltens in Schulen 

## Übersicht

Das Projekt bildet einen zentralen Bestandteil meiner Bachelorarbeit und wurde in Zusammenarbeit mit Stadtwerk Potsdam entwickelt. Stadtwerk Potsdam hat für dieses Projekt die notwendigen Sensoren zur Verfügung gestellt. Der praktische Test des Projekts erfolgt an der Schule am Schloss in Potsdam.

Ziel ist es, Sensordaten zu erfassen, diese zu analysieren und Vorhersagen zu treffen. Die Ergebnisse werden über eine benutzerfreundliche Webschnittstelle visualisiert und können interaktiv genutzt werden. Die technische Umsetzung erfolgt mittels Flask für das Web-Interface und MQTT für die Datenerfassung.

## Funktionen

- Echtzeit-Datensammlung von Sensoren über MQTT.
- Datenvisualisierung über eine Webschnittstelle.
- Periodische Vorhersagen mit vortrainierten Machine-Learning Modellen.
- Sammlung von Benutzerfeedback zu den Vorhersagen.

## Pythons Verison und Packages

Dieses Projekt wurde mit Python 3.10.10 entwickelt. Es wird empfohlen, 
diese Version zu verwenden, um Kompatibilitätsprobleme zu vermeiden.

Die Packages sind in der Datei `requirements.txt` definiert. 
Um alle erforderlichen Pakete zu installieren, führen Sie den folgenden Befehl aus:

```
pip install -r requirements.txt
```

## Installation

1. Repository klonen:

    ```
    git clone <repository_url>
    cd <repository_directory>
    ```

2. Erstellen und Aktivieren eines virtuellen Umfelds:

    ```
    python -m venv venv
    source venv/bin/activate   # Für Windows: `venv\Scripts\activate`
    ```

3. Erforderliche Pakete installieren:

    ```
    pip install -r requirements.txt
    ```

## Konfiguration

1. Stellen Sie sicher, dass Sie die Konfigurationsdatei `api_config.yaml` im Verzeichnis `smart-ventilation` mit der folgenden Struktur haben:

    ```
    READ_API_KEY: "" # API-Schlüssel für Lesezugriff
    POST_API_KEY: "" # API-Schlüssel für Schreibzugriff
    API_BASE_URL: "" # Basis-URL der API
    CONTENT_TYPE: "" # Inhaltstyp, der bei API-Anfragen verwendet wird
    CLOUD_SERVICE_URL: "" # URL Ihres Cloud-Dienstes
    USERNAME: "" # Benutzername für den Zugang zum Cloud-Dienst
    PASSWORD: "" # Passwort für den Zugang zum Cloud-Dienst
    ```

## Modelle

Im Verzeichnis `smart-ventilations/models/` befinden sich die folgenden vorbereiteten Machine-Learning Modelle im `.pkl`-Format. 

Diese Modelle sind serialisiert und optimiert für den Einsatz, sodass sie schnell in die Anwendung geladen und genutzt werden können:

- `Logistic_Regression.pkl` — Ein Modell basierend auf der logistischen Regression.
- `Random_Forest.pkl` — Ein Modell, das auf dem Random-Forest-Algorithmus basiert.

## Anwendung starten

1. Starten Sie den MQTT-Client und die Flask-Anwendung:

    ```
    python application.py
    ```

2. Öffnen Sie einen Browser Ihrer Wahl und besuchen Sie die URL `http://127.0.0.1:5000`, um auf die Webschnittstelle zuzugreifen.

## Endpunkte der Anwendung

- `/`: Zeigt das Hauptdashboard mit Echtzeit-Sensordaten an.
- `/plots`: Bietet Diagramme der Echtzeit-Sensordaten.
- `/feedback`: Ermöglicht es Benutzern, Feedback zu den Vorhersagen zu geben.
- `/thank_you`: Zeigt eine Dankesseite nach dem Absenden des Feedbacks an.
- `/contact`: Zeigt die Kontaktseite der Anwendung an.
- `/leaderboard`: Zeigt die Bestenliste basierend auf den vorhergesagten Daten an.
- `/future_data/<timestamp>`: Gibt die zukünftigen Daten für einen bestimmten Zeitstempel zurück.
- `/save_analysis_data`: Speichert Analyse-Daten.
- `/clear_session`: Löscht die Sitzungsdaten.

## Logging

Die Anwendung protokolliert wichtige Ereignisse und Fehler in der Konsole. 
Stellen Sie sicher, dass das Logging im `application.py`-Skript mit dem logging-Modul entsprechend konfiguriert ist.

## Hinweise

Stellen Sie sicher, dass alle Pfade in `application.py` und `mqtt_client.py` korrekt gemäß Ihrer Projektstruktur gesetzt sind. 
Die Anwendung geht davon aus, dass Sensordaten zu bestimmten MQTT-Themen veröffentlicht werden. 
Passen Sie die Themen und die Datenverarbeitung in `mqtt_client.py` nach Bedarf an.

## Fehlerbehebung

Falls die Anwendung nicht startet, überprüfen Sie die Konsolenprotokolle auf Fehler bezüglich fehlender Konfigurationsdateien, Modelle oder Abhängigkeiten. 
Stellen Sie sicher, dass Ihr MQTT-Broker läuft und mit den richtigen Anmeldeinformationen erreichbar ist.


## Fehlerbehebung

Falls die Anwendung nicht startet, überprüfen Sie die Konsolenprotokolle auf Fehler bezüglich fehlender Konfigurationsdateien, Modelle oder Abhängigkeiten. 
Stellen Sie sicher, dass Ihr MQTT-Broker läuft und mit den richtigen Anmeldeinformationen erreichbar ist.
