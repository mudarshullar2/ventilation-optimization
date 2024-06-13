from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import StandardScaler
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
    
    merged_df['Time_hour'] = merged_df['timestamp'].dt.floor('H')
    merged_data = pd.merge(merged_df, filtered_df, left_on='Time_hour', right_on='MESS_DATUM', how='left')
    merged_data.drop(columns=['Time_hour', 'MESS_DATUM'], inplace=True)
    merged_data.rename(columns={'TT_TU': 'ambient_temp'}, inplace=True)
    
    data_set_ml['timestamp'] = pd.to_datetime(data_set_ml['timestamp'])
    merged_data = pd.merge(merged_data, data_set_ml[['timestamp', 'tvoc']], on='timestamp', how='left')
    if merged_data['tvoc'].isna().any():
        merged_data['tvoc'].fillna(method='ffill', inplace=True)
        merged_data['tvoc'].fillna(method='bfill', inplace=True)

    merged_data['tvoc'] = merged_data['tvoc'].fillna(merged_data['tvoc'].rolling(window=3, min_periods=1).mean())

    # Given the current max in your data is 31.2 and considering a practical minimum, let's use 0 to 31.2
    median_temp = merged_data[(merged_data['ambient_temp'] >= 0) & (merged_data['ambient_temp'] <= 31.2)]['ambient_temp'].median()

    # Replace values outside this range with the median
    merged_data.loc[(merged_data['ambient_temp'] < 0) | (merged_data['ambient_temp'] > 31.2), 'ambient_temp'] = median_temp

    merged_data.to_excel(output_path, index=False)

    return merged_data


def feature_engineering(final_dataset):
    """
    Erstellt die Zielvariablen und führt weitere Datenaufbereitungen durch.
    """
    scaler = MinMaxScaler()
    features = ['co2', 'temperature', 'ambient_temp', 'humidity', 'tvoc']
    final_dataset[features] = scaler.fit_transform(final_dataset[features])

    weights = {
        'co2': 0.35,
        'temperature': 0.25,
        'ambient_temp': 0.2,
        'humidity': 0.2,
        'tvoc': 0.1
    }

    final_dataset['composite_score'] = (
        final_dataset['co2'] * weights['co2'] +
        final_dataset['temperature'] * weights['temperature'] +
        final_dataset['ambient_temp'] * weights['ambient_temp'] +
        final_dataset['humidity'] * weights['humidity'] +
        final_dataset['tvoc'] * weights['tvoc']
    )

    threshold = 0.5
    final_dataset['open_window'] = (final_dataset['composite_score'] >= threshold).astype(int)
    return final_dataset, scaler


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
    """
    Trainiert ein logistisches Regressionsmodell.
    
    Parameter:
    final_dataset (DataFrame): Der finale Datensatz.
    
    Rückgabewert:
    log_model, scaler (tuple): Das trainierte Modell und der StandardScaler.
    """

    X = final_dataset[['co2', 'temperature', 'humidity', 'tvoc', 'ambient_temp']]
    y = final_dataset['open_window']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    log_model = LogisticRegression()
    log_model.fit(X_train, y_train)
    y_pred = log_model.predict(X_test)

    # Evaluate the model
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f'Logistic Regression: Mean Squared Error: {mse}')
    print(f'Logistic Regression: R-squared: {r2}')

    return log_model, scaler


def random_forest_model(final_dataset):
    """
    Train a RandomForestRegressor model to predict window opening duration.
    
    Parameter:
    final_dataset (DataFrame): The final dataset.
    
    Rückgabewert:
    model (RandomForestRegressor): Das trainierte RandomForestRegressor Modell.
    """
    # Data cleaning
    final_dataset = final_dataset.dropna()

    # Convert timestamp to numeric format (seconds since epoch)
    final_dataset['timestamp'] = pd.to_datetime(final_dataset['timestamp']).astype(int) / 10**9

    # Define constraints for optimal environmental settings
    co2_limit = 1000
    temp_limit = 21
    tvoc_limit = 400
    humidity_lower_limit = 40
    humidity_upper_limit = 60

    # Function to simulate the window open duration required to achieve optimal conditions
    def calculate_duration(row):
        duration = 0
        if row['co2'] > co2_limit:
            duration += (row['co2'] - co2_limit) / 50  # Example: duration increases with higher CO2
        if row['temperature'] > temp_limit:
            duration += (row['temperature'] - temp_limit) * 2  # Example: duration increases with higher temperature
        if row['tvoc'] > tvoc_limit:
            duration += (row['tvoc'] - tvoc_limit) / 10  # Example: duration increases with higher TVOC
        if row['humidity'] < humidity_lower_limit:
            duration += (humidity_lower_limit - row['humidity']) / 5  # Example: duration increases with lower humidity
        if row['humidity'] > humidity_upper_limit:
            duration += (row['humidity'] - humidity_upper_limit) / 5  # Example: duration increases with higher humidity
        return duration

    # Generate synthetic target variable
    final_dataset['duration_open'] = final_dataset.apply(calculate_duration, axis=1)

    # Define features and target
    features = ['co2', 'humidity', 'temperature', 'ambient_temp', 'tvoc']
    target = 'duration_open'

    X = final_dataset[features].values
    y = final_dataset[target].values

    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train a Random Forest Regressor
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Predict on the test set
    y_pred = model.predict(X_test)

    # Evaluate the model
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
        print(f"Saved {name} model to {filename}")


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
    
    final_dataset = final_dataset.fillna(method='ffill')
    
    final_dataset.dropna(inplace=True)
    
    final_dataset, scaler = feature_engineering(final_dataset)
    
    log_model = logistic_regression_model(final_dataset)
    
    rf_model = random_forest_model(final_dataset)
    
    models = {
        "Logistic Regression": log_model,
        "Random Forest": rf_model,
        "Scaler": scaler,
    }
    save_models(models, models_directory)


if __name__ == "__main__":
    main(
        co2_last_30_days_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/10c_co2_last_30_days.csv",
        co2_older_30_days_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/10c_co2_older_30_days.csv",
        temp_last_30_days_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/10c_temp_last_30_days.csv",
        temp_older_30_days_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/10c_temp_older_30_days.csv",
        outdoor_temp_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/outdoor_temperature.txt",
        main_dataset_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/dataset.xlsx",
        final_dataset_path="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/dataset/final_dataset.xlsx",
        models_directory="/Users/mudarshullar/Desktop/ventilation-optimization/smart_ventilation/Models1"
    )
