import logging
from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import joblib
import yaml
import plotly.graph_objs as go

app = Flask(__name__)


def load_database_config(config_file):
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config['database']
    except FileNotFoundError:
        logging.error(f"Config file '{config_file}' not found")
        raise


# Load database configuration
config_file = '/Users/mudarshullar/PycharmProjects/BAProject/databaseConfig.yaml'
db_config = load_database_config(config_file)

# Load the pre-trained machine learning model
model = joblib.load('/Users/mudarshullar/Desktop/TelemetryData/model/model.pkl')


def get_latest_sensor_data():
    try:
        conn = psycopg2.connect(dbname=db_config["DBNAME"], user=db_config["DBUSER"],
                                password=db_config["DBPASSWORD"], host=db_config["DBHOST"],
                                port=db_config["DBPORT"])
        cursor = conn.cursor()

        # Fetch latest sensor data
        query = ('SELECT "timestamp", temperature, humidity, co2_values, tvoc_values '
                 'FROM public."SensorData" ORDER BY "timestamp" DESC LIMIT 100;')
        cursor.execute(query)
        sensor_data = cursor.fetchall()

        conn.close()
        return sensor_data

    except psycopg2.Error as e:
        print("Error connecting to PostgreSQL database:", e)
        return None


def generate_plot(data, x_label, y_label, plot_title):
    # Extract x and y data from sensor_data tuples
    x_data = [row[0] for row in data]  # Assuming timestamp is the first element
    y_data = [row[y_label] for row in data]  # Extract data based on y_label

    # Create Plotly trace
    trace = go.Scatter(x=x_data, y=y_data, mode='lines+markers', name=y_label)
    layout = go.Layout(title=plot_title, xaxis=dict(title=x_label), yaxis=dict(title=y_label))
    fig = go.Figure(data=[trace], layout=layout)
    return fig.to_html(full_html=False)


@app.route('/')
def index():
    sensor_data = get_latest_sensor_data()

    if sensor_data:
        # Generate recommendation using the machine learning model
        latest_data = sensor_data[0]  # Use the latest data point for recommendation
        features = [[latest_data[1], latest_data[2], latest_data[3], latest_data[4]]]
        prediction = model.predict(features)[0]

        if prediction == 1:
            recommendation = "Es wird empfohlen, die Fenster zu öffnen (Empfehlung des KI Systems)"
        else:
            recommendation = "Es wird empfohlen, die Fenster nicht zu öffnen (Empfehlung des KI Systems)"

        return render_template('index.html', sensor_data=latest_data, recommendation=recommendation)

    else:
        return render_template('index.html', sensor_data=None, recommendation=None)


@app.route('/plots')
def plots():
    sensor_data = get_latest_sensor_data()

    if sensor_data:
        # Generate individual plots
        temperature_plot = generate_plot(sensor_data, 0, 1, 'Temperature Plot')  # (timestamp, temperature)
        humidity_plot = generate_plot(sensor_data, 0, 2, 'Humidity Plot')  # (timestamp, humidity)
        co2_plot = generate_plot(sensor_data, 0, 3, 'CO2 Level Plot')  # (timestamp, co2_values)
        tvoc_plot = generate_plot(sensor_data, 0, 4, 'TVOC Level Plot')  # (timestamp, tvoc_values)

        return render_template('plots.html', temperature_plot=temperature_plot,
                               humidity_plot=humidity_plot, co2_plot=co2_plot, tvoc_plot=tvoc_plot)

    else:
        return "No sensor data available for plots."


@app.route('/feedback', methods=['POST'])
def feedback():
    is_correct = int(request.form['is_correct'])

    try:
        conn = psycopg2.connect(dbname=db_config["DBNAME"], user=db_config["DBUSER"],
                                password=db_config["DBPASSWORD"], host=db_config["DBHOST"],
                                port=db_config["DBPORT"])
        cursor = conn.cursor()
        cursor.execute('UPDATE public."SensorData" SET accurate_prediction = %s WHERE "timestamp" = (SELECT MAX('
                       '"timestamp") FROM public."SensorData");',
                       (is_correct,))
        conn.commit()
        conn.close()
        if is_correct == 1:
            feedback_message = "Vielen Dank! Dein Feedback wird die Genauigkeit " \
                               "des Modells verbessern!"
        else:
            feedback_message = "Vielen Dank! Dein Feedback wird die Genauigkeit " \
                               "des Modells verbessern!"

        return render_template('feedback.html', feedback_message=feedback_message)

    except psycopg2.Error as e:
        print("Fehler beim Aktualisieren des Feedbacks:", e)

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
