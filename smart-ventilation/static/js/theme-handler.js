// Function to open the modal
function openDesignModal() {
    document.getElementById('designModal').style.display = 'flex';
}

// Function to close the modal
function closeDesignModal() {
    document.getElementById('designModal').style.display = 'none';
}

// Function to set a theme
function setTheme(themeName) {
    localStorage.setItem('theme', themeName);
    document.documentElement.className = themeName;
}

// Function to load the theme on page startup
(function () {
    const savedTheme = localStorage.getItem('theme') || 'theme-light'; // Default to light theme
    setTheme(savedTheme);
})();
