import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
import pickle

# Daten laden und vorverarbeiten
dataset_path = '/Users/mudarshullar/Desktop/TelemetryData/data.csv'

# Neue Spaltennamen definieren, um die Lesbarkeit zu verbessern
column_names = {
    'Time': 'timestamp',
    'Temperature - Milesight Modul A 018': 'temperature',
    'CO2 - Milesight Modul A 018': 'co2',
    'TVOC - Milesight Modul A 018': 'tvoc',
    'Humidity - Milesight Modul A 018': 'humidity'
}

# Dataset einlesen
dataset = pd.read_csv(dataset_path, names=column_names.values(), header=0)

# NAN-Werte aus dem Dataset löschen
dataset.dropna(inplace=True)


# Zielvariable für ML-Modell erstellen
def determine_window_state(row):
    if (row['co2'] <= 1000) and (row['tvoc'] <= 250) and (20 <= row['temperature'] <= 23) and (
            40 <= row['humidity'] <= 60):
        return 0  # Fenster sollten nicht geöffnet werden
    else:
        return 1 # Fenster sollten geöffnet werden


# Funktion anwenden, um die Zielvariable zu erstellen
dataset['open_windows'] = dataset.apply(determine_window_state, axis=1)

# Schritt 3: Machine-Learning-Modell trainieren
# Merkmale (X) und Zielvariable (y) definieren
X = dataset[['co2', 'tvoc', 'temperature', 'humidity']]
y = dataset['open_windows']

# Daten in Trainings- und Testsets aufteilen
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Random Forest Classifier initialisieren und trainieren
clf = RandomForestClassifier(random_state=42)
clf.fit(X_train, y_train)

# Modell evaluieren und speichern
# Vorhersagen treffen
y_pred = clf.predict(X_test)

# Modellgenauigkeit evaluieren
accuracy = accuracy_score(y_test, y_pred)
conf_matrix = confusion_matrix(y_test, y_pred)

print("Accuracy:", accuracy)
print("Confusion Matrix:\n", conf_matrix)

# Trainiertes Modell als .pkl-Datei speichern
model_path = '/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl'
with open(model_path, 'wb') as f:
    pickle.dump(clf, f)
