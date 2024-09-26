function openDesignModal() {
    document.getElementById('designModal').style.display = 'flex';
}

function closeDesignModal() {
    document.getElementById('designModal').style.display = 'none';
}

function setTheme(themeName) {
    localStorage.setItem('theme', themeName);
    document.documentElement.className = themeName;
}

(function () {
    const savedTheme = localStorage.getItem('theme') || 'theme-light'; // Standardmäßig hell 
    setTheme(savedTheme);
})();
