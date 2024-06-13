// Funktion zum Öffnen des Modals
function openDesignModal() {
    document.getElementById('designModal').style.display = 'flex';
}

// Funktion zum Schließen des Modals
function closeDesignModal() {
    document.getElementById('designModal').style.display = 'none';
}

// Funktion zum Festlegen eines Themas
function setTheme(themeName) {
    localStorage.setItem('theme', themeName);
    document.documentElement.className = themeName;
}

// Funktion zum Laden des Themas beim Start der Seite
(function () {
    const savedTheme = localStorage.getItem('theme') || 'theme-light'; // Standardmäßig hell 
    setTheme(savedTheme);
})();
