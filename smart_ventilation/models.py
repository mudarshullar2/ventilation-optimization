import pandas as pd
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from imblearn.over_sampling import SMOTE
import joblib
import os
import numpy as np


def load_and_prepare_data(filepath):

    """
    Lädt die Daten aus einer Excel-Datei, benennt die Spalten um, 
    entfernt fehlende Werte und erstellt die Zielvariable basierend auf den angegebenen Bedingungen.
    
    Parameter:
    filepath (str): Der Pfad zur Excel-Datei.
    
    Rückgabe:
    pd.DataFrame: Das vorbereitete DataFrame.
    """
    
    df = pd.read_excel(filepath)
    column_names = {
        "Time": "timestamp",
        "Temperature - Milesight Modul A 018": "temperature",
        "CO2 - Milesight Modul A 018": "co2",
        "TVOC - Milesight Modul A 018": "tvoc",
        "Humidity - Milesight Modul A 018": "humidity",
        "Outdoor Temperature": "ambient_temp"
    }

    df.rename(columns=column_names, inplace=True)
    df.dropna(inplace=True)
    df['target'] = (
        (df['temperature'].between(19, 21)) &
        (df['co2'] <= 1000) &
        (df['tvoc'] <= 400) &
        (df['humidity'].between(40, 60)) &
        (df['ambient_temp'].between(15, 25))
    ).astype(int)
    
    return df


def prepare_features(df):

    """
    Trennt die Merkmale (Features) von der Zielvariable und entfernt die Zeitstempelspalte.
    
    Parameter:
    df (pd.DataFrame): Das Eingabe-DataFrame.
    
    Rückgabe:
    tuple: Ein Tuple aus den Merkmalen (X) und der Zielvariable (y).
    """

    X = df.drop(['target', 'timestamp'], axis=1)
    y = df['target']
    
    return X, y


def define_pipeline():

    """
    Definiert eine Pipeline zur Vorverarbeitung der Daten, einschließlich Imputation und Skalierung.
    
    Rückgabe:
    Pipeline: Die definierte Pipeline.
    """

    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])


def apply_smote(X, y):

    """
    Wendet SMOTE an, um die Klassen im Trainingsdatensatz auszugleichen.
    
    Parameter:
    X (pd.DataFrame): Die Merkmale.
    y (pd.Series): Die Zielvariable.
    
    Rückgabe:
    tuple: Ein Tuple aus den resampelten Merkmalen (X_resampled) und der Zielvariable (y_resampled).
    """

    smote = SMOTE(random_state=42, k_neighbors=1)
    
    return smote.fit_resample(X, y)


def train_model(X_train, y_train, model, param_grid):

    """
    Trainiert das Modell mithilfe von GridSearchCV zur Hyperparameter-Optimierung.
    
    Parameter:
    X_train (np.array): Die Trainingsmerkmale.
    y_train (pd.Series): Die Zielvariable für das Training.
    model: Das zu trainierende Modell.
    param_grid (dict): Das Parametergrid für GridSearchCV.
    
    Rückgabe:
    GridSearchCV: Das trainierte Modell.
    """
    
    grid_search = GridSearchCV(estimator=model, param_grid=param_grid, cv=5, n_jobs=-1, verbose=2)
    grid_search.fit(X_train, y_train)

    return grid_search


def save_models(models, directory):

    """
    Speichert die trainierten Modelle in einem angegebenen Verzeichnis ab.

    Parameter:
    models (dict): Ein Wörterbuch mit den trainierten Modellen.
    directory (str): Das Verzeichnis, in dem die Modelle gespeichert werden sollen.
    """

    if not os.path.exists(directory):
        os.makedirs(directory)
    for name, model in models.items():
        # Replace spaces with underscores in model names
        filename = f"{directory}/{name.replace(' ', '_')}.pkl"
        joblib.dump(model, filename)
        print(f"Saved {name} model to {filename}")


def evaluate_model(model, X_test, y_test):

    """
    Bewertet das Modell auf dem Testdatensatz und gibt die Klassifikationsmetriken aus.
    
    Parameter:
    model: Das zu bewertende Modell.
    X_test (np.array): Die Testmerkmale.
    y_test (pd.Series): Die Zielvariable für den Test.
    """

    predictions = model.predict(X_test)
    print("Klassifikationsbericht:\n", classification_report(y_test, predictions))
    print("Genauigkeit: ", accuracy_score(y_test, predictions))
    cm = confusion_matrix(y_test, predictions)
    print("Konfusionsmatrix:\n", cm)


def main(filepath, save_dir):

    # Daten laden und vorbereiten
    df = load_and_prepare_data(filepath)
    X, y = prepare_features(df)
    
    # Daten in Trainings- und Testdaten aufteilen
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    
    # Pipeline definieren und anwenden
    pipeline = define_pipeline()
    pipeline.fit(X_train)
    X_train_prepared = pipeline.transform(X_train)
    X_test_prepared = pipeline.transform(X_test)
    
    # Convert to numpy arrays to avoid feature names issues
    X_train_prepared = np.array(X_train_prepared)
    X_test_prepared = np.array(X_test_prepared)
    
    # SMOTE anwenden
    X_train_resampled, y_train_resampled = apply_smote(X_train_prepared, y_train)
    
    # Modelle und Parametergrids definieren
    models = {
        'Logistic Regression': LogisticRegression(class_weight='balanced'),
        'Decision Tree': DecisionTreeClassifier(),
        'Random Forest': RandomForestClassifier(class_weight={0: 1, 1: 10})
    }
    
    param_grids = {
        'Logistic Regression': {
            'C': [0.01, 0.1, 1, 10, 100],
            'solver': ['lbfgs', 'liblinear']
        },
        'Decision Tree': {
            'max_depth': [None, 10, 20, 30],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        },
        'Random Forest': {
            'n_estimators': [50, 100, 200],
            'max_depth': [None, 10, 20, 30],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4],
            'bootstrap': [True, False]
        }
    }
    
    # Modelle trainieren und speichern
    trained_models = {}
    for model_name in models:
        print(f"Training {model_name}...")
        model = train_model(X_train_resampled, y_train_resampled, models[model_name], param_grids[model_name])
        print(f"Beste Parameter für {model_name}: ", model.best_params_)
        evaluate_model(model, X_test_prepared, y_test)
        trained_models[model_name.replace(' ', '_')] = model
    
    # Speichere Modelle
    save_models(trained_models, save_dir)

if __name__ == "__main__":
    
    filepath = '/Users/mudarshullar/Desktop/ventilation-optimization Project/ventilation-optimization/smart_ventilation/dataset/dataset.xlsx'
    save_dir = '/Users/mudarshullar/Desktop/ventilation-optimization Project/ventilation-optimization/smart_ventilation/models'
    main(filepath, save_dir)
