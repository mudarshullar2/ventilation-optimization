import plotly.graph_objs as go


def generate_plot(data, x_label, y_label, plot_title):
    # x- und y-Daten aus den Sensordaten-Tupeln extrahieren
    x_data = [row[0] for row in data]  # Wichtig: Timestamp muss das erste Element sein
    y_data = [row[y_label] for row in data]  # Daten basierend auf y_label extrahieren

    # Plotly-Trace erstellen
    trace = go.Scatter(x=x_data, y=y_data, mode="lines+markers", name=y_label)
    layout = go.Layout(
        title=plot_title, xaxis=dict(title=x_label), yaxis=dict(title=y_label)
    )
    fig = go.Figure(data=[trace], layout=layout)
    return fig.to_html(full_html=False)