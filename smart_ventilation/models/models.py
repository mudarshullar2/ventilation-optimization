from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
from sklearn.pipeline import Pipeline
from imblearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import pandas as pd
import joblib
import os


def read_data(
    co2_last_30_days_path,
    co2_older_30_days_path,
    temp_last_30_days_path,
    temp_older_30_days_path,
):
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

    return (
        df_co2_last_30_days,
        df_co2_older_30_days,
        df_temp_last_30_days,
        df_temp_older_30_days,
    )


def prepare_data(
    df_co2_last_30_days,
    df_co2_older_30_days,
    df_temp_last_30_days,
    df_temp_older_30_days,
):
    """
    Bereitet die CO2- und Temperaturdaten vor, indem Zeitspalten formatiert und unnötige Spalten entfernt werden.

    Parameter:
    df_co2_last_30_days, df_co2_older_30_days, df_temp_last_30_days, df_temp_older_30_days (DataFrame): Die CO2- und Temperatur-DataFrames.

    Rückgabewert:
    merged_df (DataFrame): Der zusammengeführte DataFrame.
    """
    for df in [
        df_co2_last_30_days,
        df_co2_older_30_days,
        df_temp_last_30_days,
        df_temp_older_30_days,
    ]:
        df["time"] = pd.to_datetime(df["time"], format="ISO8601").dt.strftime(
            "%d/%m/%Y %H:%M"
        )
        df.drop(columns=["dev_eui"], inplace=True)

    merged_df1 = pd.concat(
        [df_co2_older_30_days, df_co2_last_30_days], ignore_index=True
    )
    merged_df2 = pd.concat(
        [df_temp_older_30_days, df_temp_last_30_days], ignore_index=True
    )
    merged_df = pd.merge(merged_df1, merged_df2, on="time", suffixes=("", "_dup"))
    merged_df.drop(columns=["temperature_dup"], inplace=True)
    return merged_df


def prepare_outdoor_data(outdoor_temp_path):
    """
    Liest die Außentemperaturdaten ein und formatiert die Zeitspalten.

    Parameter:
    outdoor_temp_path (str): Pfad zu den Außentemperaturdaten.

    Rückgabewert:
    df_outdoor_temp (DataFrame): Der DataFrame mit den Außentemperaturdaten.
    """
    df_outdoor_temp = pd.read_csv(outdoor_temp_path, delimiter=";")
    df_outdoor_temp["MESS_DATUM"] = pd.to_datetime(
        df_outdoor_temp["MESS_DATUM"], format="%Y%m%d%H"
    )
    df_outdoor_temp["MESS_DATUM"] = df_outdoor_temp["MESS_DATUM"].dt.strftime(
        "%d/%m/%Y %H:%M"
    )
    df_outdoor_temp["MESS_DATUM"] = pd.to_datetime(
        df_outdoor_temp["MESS_DATUM"], format="%d/%m/%Y %H:%M"
    )
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
    data_set_ml.rename(
        columns={
            "Time": "timestamp",
            "Temperature - Milesight Modul A 018": "temperature",
            "CO2 - Milesight Modul A 018": "co2",
            "TVOC - Milesight Modul A 018": "tvoc",
            "Humidity - Milesight Modul A 018": "humidity",
            "Outdoor Temperature": "ambient_temp",
        },
        inplace=True,
    )
    return data_set_ml


def merge_data(merged_df, df_outdoor_temp, data_set_ml, output_path):
    """
    Führt die vorbereiteten CO2-, Temperatur- und Außentemperaturdaten zusammen und fügt TVOC-Daten hinzu.
    """
    merged_df.rename(columns={"time": "timestamp"}, inplace=True)
    merged_df["timestamp"] = pd.to_datetime(
        merged_df["timestamp"], format="%d/%m/%Y %H:%M"
    )

    start_date = merged_df["timestamp"].min()
    end_date = merged_df["timestamp"].max()
    filtered_df = df_outdoor_temp[
        (df_outdoor_temp["MESS_DATUM"] >= start_date)
        & (df_outdoor_temp["MESS_DATUM"] <= end_date)
    ]
    filtered_df = filtered_df[["MESS_DATUM", "TT_TU"]]

    merged_df["Time_hour"] = merged_df["timestamp"].dt.floor("h")
    merged_data = pd.merge(
        merged_df, filtered_df, left_on="Time_hour", right_on="MESS_DATUM", how="left"
    )
    merged_data.drop(columns=["Time_hour", "MESS_DATUM"], inplace=True)
    merged_data.rename(columns={"TT_TU": "ambient_temp"}, inplace=True)

    data_set_ml["timestamp"] = pd.to_datetime(data_set_ml["timestamp"])
    merged_data = pd.merge(
        merged_data, data_set_ml[["timestamp", "tvoc"]], on="timestamp", how="left"
    )
    if merged_data["tvoc"].isna().any():
        merged_data["tvoc"] = merged_data["tvoc"].ffill().bfill()

    merged_data["tvoc"] = merged_data["tvoc"].fillna(
        merged_data["tvoc"].rolling(window=3, min_periods=1).mean()
    )
    median_temp = merged_data[
        (merged_data["ambient_temp"] >= 0) & (merged_data["ambient_temp"] <= 31.2)
    ]["ambient_temp"].median()
    merged_data.loc[
        (merged_data["ambient_temp"] < 0) | (merged_data["ambient_temp"] > 31.2),
        "ambient_temp",
    ] = median_temp
    merged_data.to_excel(output_path, index=False)

    return merged_data


def feature_engineering(final_dataset):

    # Zeitliche Aspekte hinzufügen
    def add_temporal_features(final_dataset):
        final_dataset["timestamp"] = pd.to_datetime(final_dataset["timestamp"])
        final_dataset["hour"] = final_dataset["timestamp"].dt.hour
        final_dataset["day_of_week"] = final_dataset["timestamp"].dt.dayofweek
        final_dataset["month"] = final_dataset["timestamp"].dt.month
        return final_dataset

    #  Zielvariablen "open_window" auf der Grundlage der angepassten Schwellenwerte erstellen
    def create_open_window(final_dataset):
        adjusted_thresholds = {
            "co2": 1000,
            "temperature_min": 15,
            "temperature_max": 22,
            "humidity_min": 35,
            "humidity_max": 65,
            "tvoc": 400,
            "ambient_temp_min": 5,
            "ambient_temp_max": 25,
        }

        adjusted_conditions = (
            (final_dataset["co2"] <= adjusted_thresholds["co2"])
            & (final_dataset["temperature"] >= adjusted_thresholds["temperature_min"])
            & (final_dataset["temperature"] <= adjusted_thresholds["temperature_max"])
            & (final_dataset["humidity"] >= adjusted_thresholds["humidity_min"])
            & (final_dataset["humidity"] <= adjusted_thresholds["humidity_max"])
            & (final_dataset["tvoc"] <= adjusted_thresholds["tvoc"])
            & (final_dataset["ambient_temp"] >= adjusted_thresholds["ambient_temp_min"])
            & (final_dataset["ambient_temp"] <= adjusted_thresholds["ambient_temp_max"])
        )

        final_dataset["open_window"] = (~adjusted_conditions).astype(int)
        return final_dataset

    # Funktionen anwenden, um zeitliche Merkmale hinzuzufügen und die Zielvariable zu erstellen
    final_dataset = add_temporal_features(final_dataset)
    final_dataset = create_open_window(final_dataset)

    # Klassenverteilung prüfen
    print("Class distribution in 'open_window':")
    print(final_dataset["open_window"].value_counts())

    return final_dataset


def random_forest_classifier_model(final_dataset):
    """
    Trainiert ein RandomForestClassifier-Modell.
    """
    X = final_dataset[["co2", "temperature", "ambient_temp", "humidity", "tvoc"]]
    y = final_dataset["open_window"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = RandomForestClassifier(random_state=42)
    model.fit(X_train, y_train)

    return model


def logistic_regression_model(final_dataset):
    # Sicherstellen, dass die Merkmale in der richtigen Reihenfolge sind
    feature_order = [
        "co2",
        "temperature",
        "humidity",
        "tvoc",
        "ambient_temp",
        "hour",
        "day_of_week",
        "month",
    ]

    X = final_dataset[feature_order]
    y = final_dataset["open_window"]

    # Daten aufteilen
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    # Pipeline erstellen
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="mean")),
            ("scaler", StandardScaler()),
            ("smote", SMOTE(sampling_strategy="auto", random_state=42)),
            ("model", LogisticRegression(random_state=42, class_weight="balanced")),
        ]
    )

    # Pipeline fitten
    pipeline.fit(X_train, y_train)

    # Vorhersagen machen
    y_pred = pipeline.predict(X_test)

    return pipeline


def random_forest_model(final_dataset):
    # Sicherstellen, dass die Merkmale in der richtigen Reihenfolge sind
    feature_order = ["co2", "temperature"]

    final_dataset = final_dataset.dropna()
    final_dataset["timestamp"] = pd.to_datetime(final_dataset["timestamp"])
    final_dataset["hour"] = final_dataset["timestamp"].dt.hour
    final_dataset["day_of_week"] = final_dataset["timestamp"].dt.dayofweek
    final_dataset["month"] = final_dataset["timestamp"].dt.month

    co2_limit = 1000
    temp_limit = 21

    # Dauer auf Grundlage von CO2-Werten und Innentemperatur berechnen
    def calculate_duration(row):
        duration = 0
        if row["co2"] > co2_limit:
            duration += (row["co2"] - co2_limit) / 45
        if row["temperature"] > temp_limit:
            duration += row["temperature"] - temp_limit * 1.05
        return duration

    final_dataset["duration_open"] = final_dataset.apply(calculate_duration, axis=1)

    X = final_dataset[feature_order]
    y = final_dataset["duration_open"].values

    # Pipeline erstellen
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("regressor", RandomForestRegressor(n_estimators=20, random_state=20)),
        ]
    )

    # Daten aufteilen
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=20
    )

    # Modell fitten
    model.fit(X_train, y_train)

    # Vorhersagen machen
    y_pred = model.predict(X_test)
    y_pred = [int(str(int(pred))[:2]) for pred in y_pred]

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


def main(
    co2_last_30_days_path,
    co2_older_30_days_path,
    temp_last_30_days_path,
    temp_older_30_days_path,
    outdoor_temp_path,
    main_dataset_path,
    final_dataset_path,
    models_directory,
):
    """
    Hauptfunktion, die alle Schritte der Datenvorbereitung, des Feature Engineerings und der Modellierung durchführt.
    """

    (
        df_co2_last_30_days,
        df_co2_older_30_days,
        df_temp_last_30_days,
        df_temp_older_30_days,
    ) = read_data(
        co2_last_30_days_path,
        co2_older_30_days_path,
        temp_last_30_days_path,
        temp_older_30_days_path,
    )

    merged_df = prepare_data(
        df_co2_last_30_days,
        df_co2_older_30_days,
        df_temp_last_30_days,
        df_temp_older_30_days,
    )

    df_outdoor_temp = prepare_outdoor_data(outdoor_temp_path)

    data_set_ml = prepare_main_dataset(main_dataset_path)

    merged_data = merge_data(
        merged_df, df_outdoor_temp, data_set_ml, final_dataset_path
    )

    final_dataset = pd.read_excel(final_dataset_path)

    final_dataset["timestamp"] = pd.to_datetime(final_dataset["timestamp"])

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
        co2_last_30_days_path="datasets/10c_co2_last_30_days.csv",
        co2_older_30_days_path="datasets/10c_co2_older_30_days.csv",
        temp_last_30_days_path="datasets/10c_temp_last_30_days.csv",
        temp_older_30_days_path="datasets/10c_temp_older_30_days.csv",
        outdoor_temp_path="datasets/outdoor_temperature.txt",
        main_dataset_path="datasets/dataset.xlsx",
        final_dataset_path="datasets/final_dataset.xlsx",
        models_directory="models",
    )
    
