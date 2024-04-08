import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
import pickle
import logging


def load_and_preprocess_data(dataset_path):
    """
    Lädt einen Datensatz aus einer CSV-Datei, bereitet ihn vor und gibt Features (X) und Zielvariable (y) zurück.

    Args:
        dataset_path (str): Pfad zur CSV-Datei des Datensatzes.

    Returns:
        X (DataFrame): Features des Datensatzes.
        y (Series): Zielvariable des Datensatzes.
    """
    try:
        # Spaltennamen für bessere Lesbarkeit definieren
        column_names = {
            "Time": "timestamp",
            "Temperature - Milesight Modul A 018": "temperature",
            "CO2 - Milesight Modul A 018": "co2",
            "TVOC - Milesight Modul A 018": "tvoc",
            "Humidity - Milesight Modul A 018": "humidity",
        }

        # Datensatz laden
        dataset = pd.read_csv(dataset_path, names=column_names.values(), header=0)

        # Zeilen mit NaN-Werten entfernen
        dataset.dropna(inplace=True)

        # Zielvariable für das ML-Modell erstellen
        dataset["open_windows"] = dataset.apply(determine_window_state, axis=1)

        # Features (X) und Zielvariable (y) definieren
        X = dataset[["co2", "tvoc", "temperature", "humidity"]]
        y = dataset["open_windows"]

        return X, y
    except Exception as e:
        logging.error("Fehler beim Laden und Vorverarbeiten der Daten: %s", str(e))
        return None, None


def determine_window_state(row):
    if (
            (row["co2"] <= 1000)
            and (row["tvoc"] <= 250)
            and (20 <= row["temperature"] <= 23)
            and (40 <= row["humidity"] <= 60)
    ):
        return 0  # Fenster sollte nicht geöffnet werden
    else:
        return 1  # Fenster sollte geöffnet werden


def train_and_evaluate_model(X_train, X_test, y_train, y_test):
    # Initialisieren und trainieren des Random Forest Klassifizierers
    clf = RandomForestClassifier(random_state=42)
    clf.fit(X_train, y_train)

    # Vorhersagen treffen
    y_pred = clf.predict(X_test)

    # Bewertung der Modellleistung
    accuracy = accuracy_score(y_test, y_pred)
    conf_matrix = confusion_matrix(y_test, y_pred)

    print("Accuracy:", accuracy)
    print("Confusion Matrix:\n", conf_matrix)

    return clf


def save_model(model, model_path):
    # Trainiertes Modell in .pkl-Datei speichern
    with open(model_path, "wb") as f:
        pickle.dump(model, f)


def main():
    dataset_path = "/Users/mudarshullar/Desktop/TelemetryData/data.csv"
    model_path = "/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl"

    # Daten laden und vorverarbeiten
    X, y = load_and_preprocess_data(dataset_path)

    # Daten in Trainings- und Testsets aufteilen
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Modell trainieren und bewerten
    trained_model = train_and_evaluate_model(X_train, X_test, y_train, y_test)

    # Trainiertes Modell speichern
    save_model(trained_model, model_path)


if __name__ == "__main__":
    main()
