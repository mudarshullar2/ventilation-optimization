// Funktion zum Senden von Feedback an den Server und Anzeigen einer Pop-up-Nachricht
function submitFeedback(event, form) {
    console.log("submitFeedback function called"); // Check if function is called

    event.preventDefault(); // Prevent default form submission behavior

    var isCorrect = form.querySelector('input[name="is_correct"]').value;
    console.log("isCorrect:", isCorrect); // Check the value of isCorrect

    var message = (isCorrect === '1') ? "Danke für Dein Feedback!" : "Danke für Dein Feedback!";
    console.log("Feedback message:", message); // Check the feedback message

    alert(message); // Check if alert is triggered

    event.preventDefault(); // Formularübermittlung verhindern

    var isCorrect = form.querySelector('input[name="is_correct"]').value;
    var message = (isCorrect === '1') ? "Danke für Dein Feedback!" : "Danke für Dein Feedback!";
    alert(message);

    // AJAX-Anfrage an Flask-Route
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/feedback", true);
    xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                var response = JSON.parse(xhr.responseText);
                alert(response.message);
                // Weiterleitung auf die Feedback-Seite
                window.location.href = "/feedback?message=" + encodeURIComponent(response.message);
            } else {
                alert("Fehler beim Senden des Feedbacks.");
            }
        }
    };
    xhr.send("is_correct=" + isCorrect);

    return false;
}
