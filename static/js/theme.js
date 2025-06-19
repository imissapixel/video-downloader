(function () {
    // This script should be placed at the end of the body tag to ensure DOM elements are loaded.
    const themeToggle = document.getElementById("themeToggle");
    const themeIcon = document.getElementById("themeIcon");
    const htmlElement = document.documentElement;

    if (!themeToggle || !themeIcon || !htmlElement) {
        console.error("Theme toggle elements could not be found in the DOM.");
        return;
    }

    const moonIcon = "bi-moon-stars-fill";
    const sunIcon = "bi-sun-fill";

    function syncToggleWithTheme() {
        const currentTheme = htmlElement.getAttribute("data-theme");
        
        if (currentTheme === "dark") {
            themeToggle.checked = true;
            themeIcon.className = "bi " + moonIcon;
        } else {
            themeToggle.checked = false;
            themeIcon.className = "bi " + sunIcon;
        }
    }

    themeToggle.addEventListener("change", () => {
        if (themeToggle.checked) {
            htmlElement.setAttribute("data-theme", "dark");
            localStorage.setItem("theme", "dark");
            themeIcon.className = "bi " + moonIcon;
        } else {
            htmlElement.setAttribute("data-theme", "light");
            localStorage.setItem("theme", "light");
            themeIcon.className = "bi " + sunIcon;
        }
    });

    // Sync toggle with the theme that was already applied in the head
    syncToggleWithTheme();
})();
