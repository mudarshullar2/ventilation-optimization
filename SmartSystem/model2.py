import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
import pickle


def load_and_preprocess_data(dataset_path):
    # Define column names for better readability
    column_names = {
        "Time": "timestamp",
        "Temperature - Milesight Modul A 018": "temperature",
        "CO2 - Milesight Modul A 018": "co2",
        "TVOC - Milesight Modul A 018": "tvoc",
        "Humidity - Milesight Modul A 018": "humidity",
    }

    # Load dataset
    dataset = pd.read_csv(dataset_path, names=column_names.values(), header=0)

    # Drop rows with NaN values
    dataset.dropna(inplace=True)

    # Create target variable for ML model
    dataset["open_windows"] = dataset.apply(determine_window_state, axis=1)

    # Define features (X) and target variable (y)
    X = dataset[["co2", "tvoc", "temperature", "humidity"]]
    y = dataset["open_windows"]

    return X, y


def determine_window_state(row):
    if (
            (row["co2"] <= 1000)
            and (row["tvoc"] <= 250)
            and (20 <= row["temperature"] <= 23)
            and (40 <= row["humidity"] <= 60)
    ):
        return 0  # Windows should not be opened
    else:
        return 1  # Windows should be opened


def train_and_evaluate_model(X_train, X_test, y_train, y_test):
    # Initialize and train Random Forest Classifier
    clf = RandomForestClassifier(random_state=42)
    clf.fit(X_train, y_train)

    # Make predictions
    y_pred = clf.predict(X_test)

    # Evaluate model performance
    accuracy = accuracy_score(y_test, y_pred)
    conf_matrix = confusion_matrix(y_test, y_pred)

    print("Accuracy:", accuracy)
    print("Confusion Matrix:\n", conf_matrix)

    return clf


def save_model(model, model_path):
    # Save trained model to .pkl file
    with open(model_path, "wb") as f:
        pickle.dump(model, f)


def main():
    dataset_path = "/Users/mudarshullar/Desktop/TelemetryData/data.csv"
    model_path = "/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl"

    # Load and preprocess data
    X, y = load_and_preprocess_data(dataset_path)

    # Split data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train and evaluate model
    trained_model = train_and_evaluate_model(X_train, X_test, y_train, y_test)

    # Save trained model
    save_model(trained_model, model_path)


if __name__ == "__main__":
    main()
