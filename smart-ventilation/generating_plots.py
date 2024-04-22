import plotly.graph_objs as go


def generate_plot(data_list, x_key, y_key, plot_title):
    """
    Generiert ein Plotly-Diagramm basierend auf den übergebenen Daten.

    Parameter:
        data_list: Eine Liste mit den Daten, aus denen das Diagramm generiert werden soll.
        x_key: Der Schlüssel für die x-Achse (z. B. 'time').
        y_key: Der Schlüssel für die y-Achse (z. B. eine der Sensordaten).
        plot_title: Der Titel des Diagramms.

    Rückgabewert:
        HTML-Code für das generierte Plotly-Diagramm.
    """
    x_data = []
    y_data = []

    # Iteration über jedes Element in der Datenliste
    for data in data_list:
        if data:
            # x- und y-Daten aus dem Dictionray
            x_data.append(data[0][x_key])  # x_key ist Timestamp
            y_data.append(data[0][y_key])  # y_key ist einer der Sensordaten

    # Plotly-Spur
    trace = go.Scatter(x=x_data, y=y_data, mode="lines+markers", name=y_key)
    layout = go.Layout(
        title=plot_title,
        xaxis=dict(title=x_key),
        yaxis=dict(title=y_key),
        plot_bgcolor='#444',
        paper_bgcolor='#333',
        font=dict(color='#ffffff')
    )
    fig = go.Figure(data=[trace], layout=layout)
    return fig.to_html(full_html=False)
