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
    df = pd.read_csv(filepath)
    column_names = {
        "Time": "timestamp",
        "Temperature - Milesight Modul A 018": "temperature",
        "CO2 - Milesight Modul A 018": "co2",
        "TVOC - Milesight Modul A 018": "tvoc",
        "Humidity - Milesight Modul A 018": "humidity",
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
    X['avg_time'] = X['timestamp'].view(np.int64) // 10**9  # Convert timestamp to Unix time in seconds
    X.drop('timestamp', axis=1, inplace=True)

    # Ensuring the order of columns
    X = X[['humidity', 'temperature', 'co2', 'tvoc', 'avg_time']]

    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    X_prepared = pipeline.fit_transform(X)
    X_prepared_df = pd.DataFrame(X_prepared, columns=X.columns)
    return X_prepared_df

def train_models(X_train, y_train):
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
    for name, model in models.items():
        filename = f"{directory}/{name.replace(' ', '_')}.pkl"
        joblib.dump(model, filename)
        print(f"Saved {name} model to {filename}")

def prepare_prediction_data(data):
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['avg_time'] = df['timestamp'].view(np.int64) // 10**9
    df.drop(['timestamp'], axis=1, inplace=True)

    # Ensuring the order of columns
    df = df[['humidity', 'temperature', 'co2', 'tvoc', 'avg_time']]

    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    df_prepared = pipeline.fit_transform(df)
    df_prepared_df = pd.DataFrame(df_prepared, columns=df.columns)
    return df_prepared_df

def load_models(directory):
    models = {
        'Logistic Regression': joblib.load(f"{directory}/Logistic_Regression.pkl"),
        'Decision Tree': joblib.load(f"{directory}/Decision_Tree.pkl"),
        'Random Forest': joblib.load(f"{directory}/Random_Forest.pkl")
    }
    return models

def main(filepath):
    df = load_and_prepare_data(filepath)
    # Including 'timestamp' for model training to consider hourly variations
    X = df[['timestamp', 'temperature', 'co2', 'humidity', 'tvoc']]
    y = df['optimal']
    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)
    
    models = train_models(X_train, y_train)
    models_directory = "/Users/mudarshullar/Desktop/ventilation-optimization Project/ventilation-optimization/smart-ventilation/models"
    save_models(models, models_directory)

if __name__ == "__main__":
    dataset_path = "/Users/mudarshullar/Desktop/TelemetryData/data.csv"
    main(dataset_path)
    