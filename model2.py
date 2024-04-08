import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
import pickle

# Step 1: Load and Preprocess the Data
dataset_path = '/Users/mudarshullar/Desktop/TelemetryData/data.csv'

# Define the new column names for easier reading
column_names = {
    'Time': 'timestamp',
    'Temperature - Milesight Modul A 018': 'temperature',
    'CO2 - Milesight Modul A 018': 'co2',
    'TVOC - Milesight Modul A 018': 'tvoc',
    'Humidity - Milesight Modul A 018': 'humidity'
}

# Read the dataset with renamed columns
dataset = pd.read_csv(dataset_path, names=column_names.values(), header=0)

# Check for missing values and drop rows with missing data
dataset.dropna(inplace=True)


# Step 2: Create the Target Variable
def determine_window_state(row):
    if (row['co2'] <= 1000) and (row['tvoc'] <= 250) and (20 <= row['temperature'] <= 23) and (
            40 <= row['humidity'] <= 60):
        return 0  # Windows should not be opened
    else:
        return 1  # Windows should be opened


# Apply the function to create the target variable
dataset['open_windows'] = dataset.apply(determine_window_state, axis=1)

# Step 3: Train a Machine Learning Model
# Define features (X) and target variable (y)
X = dataset[['co2', 'tvoc', 'temperature', 'humidity']]
y = dataset['open_windows']

# Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Initialize and train a Random Forest Classifier
clf = RandomForestClassifier(random_state=42)
clf.fit(X_train, y_train)

# Step 4: Evaluate and Save the Model
# Make predictions
y_pred = clf.predict(X_test)

# Evaluate model accuracy
accuracy = accuracy_score(y_test, y_pred)
conf_matrix = confusion_matrix(y_test, y_pred)

print("Accuracy:", accuracy)
print("Confusion Matrix:\n", conf_matrix)

# Save the trained model as a .pkl file
model_path = '/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl'
with open(model_path, 'wb') as f:
    pickle.dump(clf, f)

print("Model saved successfully at:", model_path)
