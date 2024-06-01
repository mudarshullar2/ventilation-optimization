import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
import joblib


def load_and_prepare_data(filepath):
    
    """
    Lädt die Daten aus einer CSV-Datei und bereitet sie vor, indem die Spalten umbenannt werden
    und eine neue Spalte hinzugefügt wird, die angibt, ob die Bedingungen optimal sind.

    Parameter:
    filepath (str): Der Pfad zur CSV-Datei.

    Rückgabe:
    pd.DataFrame: Das vorbereitete DataFrame mit umbenannten Spalten und einer neuen Spalte 'optimal'.
    """
    
    df = pd.read_excel(filepath)
    column_names = {
        "Time": "timestamp",
        "Temperature - Milesight Modul A 018": "temperature",
        "CO2 - Milesight Modul A 018": "co2",
        "TVOC - Milesight Modul A 018": "tvoc",
        "Humidity - Milesight Modul A 018": "humidity",
        "Outdoor Temperature" : "ambient_temp"
    }

    df.rename(columns=column_names, inplace=True)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    conditions = [
        (df['temperature'].between(19, 21)) &
        (df['co2'] <= 1000) &
        (df['tvoc'] <= 500) &
        (df['humidity'].between(40, 60))
    ]
    df['optimal'] = np.select(conditions, [1], default=0)

    return df


def feature_engineering(X):

    """
    Führt Feature Engineering auf den Daten durch, indem eine neue Spalte 'avg_time' erstellt,
    die den Unix-Zeitstempel in Sekunden darstellt und die ursprüngliche 'timestamp'-Spalte entfernt wird.
    Anschließend werden die Daten skaliert und fehlende Werte ersetzt.

    Parameter:
    X (pd.DataFrame): Das Eingabe-DataFrame.

    Rückgabe:
    pd.DataFrame: Das vorbereitete DataFrame mit neuen Features und skalierten Werten.
    """

    X['avg_time'] = X['timestamp'].astype(np.int64) // 10**9  # Konvertiert den Zeitstempel in Unix-Zeit in Sekunden
    X.drop('timestamp', axis=1, inplace=True)

    # Sicherstellen der Reihenfolge der Spalten
    X = X[['humidity', 'temperature', 'co2', 'tvoc', 'ambient_temp', 'avg_time']]

    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    X_prepared = pipeline.fit_transform(X)
    X_prepared_df = pd.DataFrame(X_prepared, columns=X.columns)

    return X_prepared_df

def train_models(X_train, y_train):

    """
    Trainiert verschiedene Modelle (Logistische Regression, Entscheidungsbaum und Random Forest)
    auf den vorbereiteten Trainingsdaten.

    Parameter:
    X_train (pd.DataFrame): Die Trainingsdaten.
    y_train (pd.Series): Die Zielvariable.

    Rückgabe:
    dict: Ein Wörterbuch mit den trainierten Modellen.
    """

    X_train_prepared = feature_engineering(X_train)
    
    models = {
        'Logistic Regression': LogisticRegression(),
        'Decision Tree': DecisionTreeClassifier(random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42)
    }

    for name, model in models.items():
        model.fit(X_train_prepared, y_train)
    
    return models


def save_models(models, directory):

    """
    Speichert die trainierten Modelle in einem angegebenen Verzeichnis ab.

    Parameter:
    models (dict): Ein Wörterbuch mit den trainierten Modellen.
    directory (str): Das Verzeichnis, in dem die Modelle gespeichert werden sollen.
    """

    for name, model in models.items():
        filename = f"{directory}/{name.replace(' ', '_')}.pkl"
        joblib.dump(model, filename)
        print(f"Saved {name} model to {filename}")


def prepare_prediction_data(data):

    """
    Bereitet die Eingabedaten für Vorhersagen vor, indem sie in ein DataFrame konvertiert,
    der Zeitstempel in Unix-Zeit umgewandelt und fehlende Werte ersetzt und skaliert werden.

    Parameter:
    data (dict): Die Eingabedaten.

    Rückgabe:
    pd.DataFrame: Das vorbereitete DataFrame für Vorhersagen.
    """

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['avg_time'] = df['timestamp'].view(np.int64) // 10**9
    df.drop(['timestamp'], axis=1, inplace=True)

    # Sicherstellen der Reihenfolge der Spalten
    df = df[['humidity', 'temperature', 'co2', 'tvoc', 'ambient_temp', 'avg_time']]

    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    df_prepared = pipeline.fit_transform(df)
    df_prepared_df = pd.DataFrame(df_prepared, columns=df.columns)

    return df_prepared_df


def load_models(directory):

    """
    Lädt die gespeicherten Modelle aus einem angegebenen Verzeichnis.

    Parameter:
    directory (str): Das Verzeichnis, aus dem die Modelle geladen werden sollen.

    Rückgabe:
    dict: Ein Wörterbuch mit den geladenen Modellen.
    """

    models = {
        'Logistic Regression': joblib.load(f"{directory}/Logistic_Regression.pkl"),
        'Decision Tree': joblib.load(f"{directory}/Decision_Tree.pkl"),
        'Random Forest': joblib.load(f"{directory}/Random_Forest.pkl")
    }

    return models

def main(filepath):

    """
    Der Hauptprozess des Skripts: lädt und bereitet die Daten vor, trainiert die Modelle und speichert sie.

    Parameter:
    filepath (str): Der Pfad zur CSV-Datei.
    """

    df = load_and_prepare_data(filepath)
    # Einschließen des 'timestamp' für das Modelltraining, um stündliche Variationen zu berücksichtigen
    X = df[['timestamp', 'humidity', 'temperature', 'co2', 'tvoc', 'ambient_temp']]
    y = df['optimal']
    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)
    
    models = train_models(X_train, y_train)
    models_directory = "/Users/mudarshullar/Desktop/ventilation-optimization Project/ventilation-optimization/smart-ventilation/models"
    save_models(models, models_directory)


if __name__ == "__main__":

    dataset_path = "/Users/mudarshullar/Desktop/ventilation-optimization Project/ventilation-optimization/smart-ventilation/dataset/dataset.xlsx"
    main(dataset_path)
