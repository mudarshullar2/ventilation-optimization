// static/js/script.js
document.addEventListener('DOMContentLoaded', function() {
    var ctx = document.getElementById('co2Chart').getContext('2d');
    var chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CO2 Levels',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
            }]
        },
        options: {
            indexAxis: 'x', // Use indexAxis instead of type: 'realtime'
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });

    function fetchData(chart) {
        fetch('/data')
            .then(response => response.json())
            .then(data => {
                chart.data.labels = data.time;
                chart.data.datasets[0].data = data.co2;
                chart.update();
            });
    }

    setInterval(() => {
        fetchData(chart);
    }, 2000); // Fetch data every 2 seconds
});
