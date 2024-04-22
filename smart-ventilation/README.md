Beschreibung der Anwendung:
- Die folgende Anwendung stellt eine Verbindung zu einer PostgreSQL-Datenbank her, indem sie die Bibliothek psycopg2 verwendet, und ruft die Sensordaten aus der Tabelle "SensorData" ab. Anschließend verwendet sie diese Daten, um eine Vorhersage mit einem vorab trainierten Machine-Learning-Modell zu treffen.

- Das Vorhersageergebnis bestimmt eine Empfehlungsnachricht, die auf der Startseite angezeigt wird. Auf der zweiten Seite der Anwendung werden interaktive Diagramme für die erhobenen Temperatur-, Luftfeuchtigkeits-, CO2- und TVOC-Gehalte generiert und angezeigt.

- Die Anwendung verarbeitet das Feedback der Nutzer, indem sie die Genauigkeit des Modells basierend auf der Antwort des Nutzers aktualisiert.

- Die Anwendung zeigt, wie man Flask mit einer PostgreSQL-Datenbank und einem Machine-Learning-Modell integriert, um Echtzeitempfehlungen und Visualisierungen basierend auf Sensordaten bereitzustellen. Sie zeigt außerdem, wie man Nutzerfeedback behandelt, um die Genauigkeit des Modells kontinuierlich zu verbessern.
