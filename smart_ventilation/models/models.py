from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from imblearn.over_sampling import SMOTE
from sklearn.pipeline import Pipeline
from imblearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import pandas as pd
import joblib
import os


def read_data(co2_last_30_days_path, co2_older_30_days_path, temp_last_30_days_path, temp_older_30_days_path):
    """
    Liest die Datensätze ein.
    
    Parameter:
    co2_last_30_days_path (str): Pfad zu den CO2-Daten der letzten 30 Tage.
    co2_older_30_days_path (str): Pfad zu den CO2-Daten älter als 30 Tage.
    temp_last_30_days_path (str): Pfad zu den Temperaturdaten der letzten 30 Tage.
    temp_older_30_days_path (str): Pfad zu den Temperaturdaten älter als 30 Tage.
    
    Rückgabewert:
    df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days (tuple): Die eingelesenen DataFrames.
    """
    df_co2_last_30_days = pd.read_csv(co2_last_30_days_path)
    df_co2_older_30_days = pd.read_csv(co2_older_30_days_path)
    df_temp_last_30_days = pd.read_csv(temp_last_30_days_path)
    df_temp_older_30_days = pd.read_csv(temp_older_30_days_path)

    return df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days


def prepare_data(df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days):
    """
    Bereitet die CO2- und Temperaturdaten vor, indem Zeitspalten formatiert und unnötige Spalten entfernt werden.
    
    Parameter:
    df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days (DataFrame): Die CO2- und Temperatur-DataFrames.
    
    Rückgabewert:
    merged_df (DataFrame): Der zusammengeführte DataFrame.
    """
    for df in [df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days]:
        df['time'] = pd.to_datetime(df['time'], format='ISO8601').dt.strftime('%d/%m/%Y %H:%M')
        df.drop(columns=['dev_eui'], inplace=True)
    
    merged_df1 = pd.concat([df_co2_older_30_days, df_co2_last_30_days], ignore_index=True)
    merged_df2 = pd.concat([df_temp_older_30_days, df_temp_last_30_days], ignore_index=True)
    merged_df = pd.merge(merged_df1, merged_df2, on='time', suffixes=('', '_dup'))
    merged_df.drop(columns=['temperature_dup'], inplace=True)
    return merged_df


def prepare_outdoor_data(outdoor_temp_path):
    """
    Liest die Außentemperaturdaten ein und formatiert die Zeitspalten.
    
    Parameter:
    outdoor_temp_path (str): Pfad zu den Außentemperaturdaten.
    
    Rückgabewert:
    df_outdoor_temp (DataFrame): Der DataFrame mit den Außentemperaturdaten.
    """
    df_outdoor_temp = pd.read_csv(outdoor_temp_path, delimiter=';')
    df_outdoor_temp['MESS_DATUM'] = pd.to_datetime(df_outdoor_temp['MESS_DATUM'], format='%Y%m%d%H')
    df_outdoor_temp['MESS_DATUM'] = df_outdoor_temp['MESS_DATUM'].dt.strftime('%d/%m/%Y %H:%M')
    df_outdoor_temp['MESS_DATUM'] = pd.to_datetime(df_outdoor_temp['MESS_DATUM'], format='%d/%m/%Y %H:%M')
    return df_outdoor_temp


def prepare_main_dataset(main_dataset_path):
    """
    Liest den Hauptdatensatz ein und benennt die Spalten um.
    
    Parameter:
    main_dataset_path (str): Pfad zum Hauptdatensatz.
    
    Rückgabewert:
    data_set_ml (DataFrame): Der Hauptdatensatz.
    """
    data_set_ml = pd.read_excel(main_dataset_path)
    data_set_ml.rename(columns={
        'Time': 'timestamp',
        'Temperature - Milesight Modul A 018': 'temperature',
        'CO2 - Milesight Modul A 018': 'co2',
        'TVOC - Milesight Modul A 018': 'tvoc',
        'Humidity - Milesight Modul A 018': 'humidity',
        'Outdoor Temperature': 'ambient_temp'
    }, inplace=True)
    return data_set_ml


def merge_data(merged_df, df_outdoor_temp, data_set_ml, output_path):
    """
    Führt die vorbereiteten CO2-, Temperatur- und Außentemperaturdaten zusammen und fügt TVOC-Daten hinzu.
    """
    merged_df.rename(columns={'time':'timestamp'}, inplace=True)
    merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'], format='%d/%m/%Y %H:%M')
    
    start_date = merged_df['timestamp'].min()
    end_date = merged_df['timestamp'].max()
    filtered_df = df_outdoor_temp[(df_outdoor_temp['MESS_DATUM'] >= start_date) & (df_outdoor_temp['MESS_DATUM'] <= end_date)]
    filtered_df = filtered_df[["MESS_DATUM", "TT_TU"]]
    
    merged_df['Time_hour'] = merged_df['timestamp'].dt.floor('h')
    merged_data = pd.merge(merged_df, filtered_df, left_on='Time_hour', right_on='MESS_DATUM', how='left')
    merged_data.drop(columns=['Time_hour', 'MESS_DATUM'], inplace=True)
    merged_data.rename(columns={'TT_TU': 'ambient_temp'}, inplace=True)
    
    data_set_ml['timestamp'] = pd.to_datetime(data_set_ml['timestamp'])
    merged_data = pd.merge(merged_data, data_set_ml[['timestamp', 'tvoc']], on='timestamp', how='left')
    if merged_data['tvoc'].isna().any():
        merged_data['tvoc'] = merged_data['tvoc'].ffill().bfill()
    
    merged_data['tvoc'] = merged_data['tvoc'].fillna(merged_data['tvoc'].rolling(window=3, min_periods=1).mean())
    median_temp = merged_data[(merged_data['ambient_temp'] >= 0) & (merged_data['ambient_temp'] <= 31.2)]['ambient_temp'].median()
    merged_data.loc[(merged_data['ambient_temp'] < 0) | (merged_data['ambient_temp'] > 31.2), 'ambient_temp'] = median_temp
    merged_data.to_excel(output_path, index=False)
    
    return merged_data


def feature_engineering(final_dataset):
    # Add temporal features
    def add_temporal_features(final_dataset):
        final_dataset['timestamp'] = pd.to_datetime(final_dataset['timestamp'])
        final_dataset['hour'] = final_dataset['timestamp'].dt.hour
        final_dataset['day_of_week'] = final_dataset['timestamp'].dt.dayofweek
        final_dataset['month'] = final_dataset['timestamp'].dt.month
        return final_dataset

    # Create the target variable `open_window` based on adjusted thresholds
    def create_open_window(final_dataset):
        adjusted_thresholds = {
            'co2': 1000,
            'temperature_min': 15,
            'temperature_max': 22,
            'humidity_min': 35,
            'humidity_max': 65,
            'tvoc': 400,
            'ambient_temp_min': 5,
            'ambient_temp_max': 25
        }

        adjusted_conditions = (
            (final_dataset['co2'] <= adjusted_thresholds['co2']) &
            (final_dataset['temperature'] >= adjusted_thresholds['temperature_min']) &
            (final_dataset['temperature'] <= adjusted_thresholds['temperature_max']) &
            (final_dataset['humidity'] >= adjusted_thresholds['humidity_min']) &
            (final_dataset['humidity'] <= adjusted_thresholds['humidity_max']) &
            (final_dataset['tvoc'] <= adjusted_thresholds['tvoc']) &
            (final_dataset['ambient_temp'] >= adjusted_thresholds['ambient_temp_min']) &
            (final_dataset['ambient_temp'] <= adjusted_thresholds['ambient_temp_max'])
        )

        final_dataset['open_window'] = (~adjusted_conditions).astype(int)
        return final_dataset

    # Apply functions to add temporal features and create the target variable
    final_dataset = add_temporal_features(final_dataset)
    final_dataset = create_open_window(final_dataset)

    # Check class distribution
    print("Class distribution in 'open_window':")
    print(final_dataset['open_window'].value_counts())

    return final_dataset


def random_forest_classifier_model(final_dataset):
    """
    Trainiert ein RandomForestClassifier-Modell.
    """
    X = final_dataset[['co2', 'temperature', 'ambient_temp', 'humidity', 'tvoc']]
    y = final_dataset['open_window']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(random_state=42)
    model.fit(X_train, y_train)

    return model


def logistic_regression_model(final_dataset):
    # Define features and target
    X = final_dataset[['co2', 'temperature', 'humidity', 'tvoc', 'ambient_temp', 'hour', 'day_of_week', 'month']]
    y = final_dataset['open_window']

    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

    # Impute missing values and scale features
    imputer = SimpleImputer(strategy='mean')
    scaler = StandardScaler()

    # Define the logistic regression model
    model = LogisticRegression(random_state=42, class_weight='balanced')

    # Create a pipeline
    pipeline = Pipeline(steps=[
        ('imputer', imputer),
        ('scaler', scaler),
        ('smote', SMOTE(sampling_strategy='auto', random_state=42)),
        ('model', model)
    ])

    # Fit the model
    pipeline.fit(X_train, y_train)

    # Predict on the test set
    y_pred = pipeline.predict(X_test)

    # Evaluate the model
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_pred)

    print(f'Accuracy: {accuracy}')
    print(f'F1-Score: {f1}')
    print(f'Precision: {precision}')
    print(f'Recall: {recall}')
    print(f'ROC-AUC: {roc_auc}')

    return pipeline


def random_forest_model(final_dataset):
    """
    Trainiert ein RandomForestRegressor-Modell, um die Dauer der Fensteröffnung vorherzusagen.

    Parameter:
    final_dataset (DataFrame): Das endgültige Dataset.

    Rückgabewert:
    model (RandomForestRegressor): Das trainierte RandomForestRegressor-Modell.
    """
    # Daten bereinigen
    final_dataset = final_dataset.dropna()

    # Zeitstempel in datetime umwandeln und temporale Features extrahieren
    final_dataset['timestamp'] = pd.to_datetime(final_dataset['timestamp'])
    final_dataset['hour'] = final_dataset['timestamp'].dt.hour
    final_dataset['day_of_week'] = final_dataset['timestamp'].dt.dayofweek
    final_dataset['month'] = final_dataset['timestamp'].dt.month

    # Grenzwerte für optimale Umweltbedingungen definieren
    co2_limit = 1000
    temp_limit = 21
    tvoc_limit = 400
    humidity_lower_limit = 40
    humidity_upper_limit = 60

    # Funktion zur Simulation der erforderlichen Fensteröffnungsdauer für optimale Bedingungen definieren
    def calculate_duration(row):
        duration = 0
        if row['co2'] > co2_limit:
            duration += (row['co2'] - co2_limit) / 30  # Erhöhtes Gewicht für CO2
        if row['temperature'] > temp_limit:
            duration += (row['temperature'] - temp_limit) * 3  # Erhöhtes Gewicht für Temperatur
        if row['ambient_temp'] > temp_limit:
            duration += (row['ambient_temp'] - temp_limit) * 3  # Erhöhtes Gewicht für Außentemperatur
        if row['tvoc'] > tvoc_limit:
            duration += (row['tvoc'] - tvoc_limit) / 20  # Verringertes Gewicht für TVOC
        if row['humidity'] < humidity_lower_limit:
            duration += (humidity_lower_limit - row['humidity']) / 10  # Verringertes Gewicht für Luftfeuchtigkeit
        if row['humidity'] > humidity_upper_limit:
            duration += (row['humidity'] - humidity_upper_limit) / 10  # Verringertes Gewicht für Luftfeuchtigkeit
        return duration

    # Synthetische Zielvariable generieren
    final_dataset['duration_open'] = final_dataset.apply(calculate_duration, axis=1)

    # Merkmale und Zielvariable definieren
    features = ['co2', 'humidity', 'temperature', 'ambient_temp', 'tvoc', 'hour', 'day_of_week', 'month']
    target = 'duration_open'

    X = final_dataset[features]
    y = final_dataset[target].values

    # Modell Pipeline erstellen
    model = Pipeline(steps=[
        ('scaler', StandardScaler()),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    # Daten in Trainings- und Testmengen aufteilen
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Modell trainieren
    model.fit(X_train, y_train)

    # Vorhersagen auf dem Testdatensatz machen
    y_pred = model.predict(X_test)

    # Modell evaluieren
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f'Random Forest: Mean Squared Error: {mse}')
    print(f'Random Forest: R-squared: {r2}')

    return model


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
        filename = f"{directory}/{name.replace(' ', '_')}.pkl"
        joblib.dump(model, filename)
        print(f"{name} gepsichert in {filename}")

def main(co2_last_30_days_path, co2_older_30_days_path, temp_last_30_days_path, temp_older_30_days_path, outdoor_temp_path, main_dataset_path, final_dataset_path, models_directory):
    """
    Hauptfunktion, die alle Schritte der Datenvorbereitung, des Feature Engineerings und der Modellierung durchführt.
    """
    
    df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days = read_data(co2_last_30_days_path, co2_older_30_days_path, temp_last_30_days_path, temp_older_30_days_path)
    
    merged_df = prepare_data(df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days)
    
    df_outdoor_temp = prepare_outdoor_data(outdoor_temp_path)
    
    data_set_ml = prepare_main_dataset(main_dataset_path)
    
    merged_data = merge_data(merged_df, df_outdoor_temp, data_set_ml, final_dataset_path)
    
    final_dataset = pd.read_excel(final_dataset_path)
    
    final_dataset['timestamp'] = pd.to_datetime(final_dataset['timestamp'])
    
    final_dataset = final_dataset.ffill().dropna()
    
    final_dataset = feature_engineering(final_dataset)

    log_model = logistic_regression_model(final_dataset)

    rf_model = random_forest_model(final_dataset)

    models = {
        "Logistic Regression": log_model,
        "Random Forest": rf_model,
    }

    save_models(models, models_directory)

if __name__ == "__main__":

    main(
        co2_last_30_days_path="smart_ventilation/dataset/10c_co2_last_30_days.csv",
        co2_older_30_days_path="smart_ventilation/dataset/10c_co2_older_30_days.csv",
        temp_last_30_days_path="smart_ventilation/dataset/10c_temp_last_30_days.csv",
        temp_older_30_days_path="smart_ventilation/dataset/10c_temp_older_30_days.csv",
        outdoor_temp_path="smart_ventilation/dataset/outdoor_temperature.txt",
        main_dataset_path="smart_ventilation/dataset/dataset.xlsx",
        final_dataset_path="smart_ventilation/dataset/final_dataset.xlsx",
        models_directory="smart_ventilation/models"
    )
