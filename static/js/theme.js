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

    function applyTheme() {
        const savedTheme = localStorage.getItem("theme");
        const systemPrefersDark = window.matchMedia(
            "(prefers-color-scheme: dark)",
        ).matches;

        if (
            savedTheme === "dark" ||
            (!savedTheme && systemPrefersDark)
        ) {
            htmlElement.setAttribute("data-theme", "dark");
            themeToggle.checked = true;
            themeIcon.className = "bi " + moonIcon;
        } else {
            htmlElement.setAttribute("data-theme", "light");
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

    // Apply the correct theme on initial page load
    applyTheme();
})();
