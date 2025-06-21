(function () {
    "use strict";

    const SIGNAL_FILE = "_build_signal.txt";
    const POLLING_INTERVAL = 5000;
    const REBUILD_ENDPOINT = "/rebuild";

    let currentBuildId = null;
    function createRebuildButton() {
        const button = document.createElement("div");
        button.id = "devildex-rebuild-button";
        button.textContent = "Rebuild";
        Object.assign(button.style, {
            position: "fixed",
            bottom: "20px",
            right: "20px",
            padding: "10px 20px",
            backgroundColor: "#AF4D98",
            color: "white",
            border: "none",
            borderRadius: "5px",
            cursor: "pointer",
            boxShadow: "0 2px 5px rgba(0,0,0,0.2)",
            zIndex: "10000",
            fontFamily: "sans-serif",
            fontSize: "16px",
        });

        button.addEventListener("click", async () => {
            console.log("Requesting rebuild from server...");
            button.textContent = "Rebuilding...";
            button.style.backgroundColor = "#7F3A72";

            try {
                await fetch(REBUILD_ENDPOINT);
            } catch (error) {
                console.error("Rebuild request failed:", error);
                button.textContent = "Error!";
                setTimeout(() => {
                    button.textContent = "Rebuild";
                    button.style.backgroundColor = "#AF4D98";
                }, 2000);
            }
        });

        document.body.appendChild(button);
    }

    async function fetchBuildId() {
        try {
            const response = await fetch(`/${SIGNAL_FILE}?t=${new Date().getTime()}`, {
                cache: "no-cache",
            });
            if (response.ok) {
                return await response.text();
            }
        } catch (error) {
        }
        return null;
    }

    async function checkForUpdates() {
        const newBuildId = await fetchBuildId();
        if (newBuildId) {
            if (currentBuildId === null) {
                currentBuildId = newBuildId;
                console.log(`Live-Reload connected. Initial build ID: ${currentBuildId}`);
            } else if (newBuildId !== currentBuildId) {
                console.log(
                    `New build detected (ID: ${newBuildId}). Reloading page...`
                );
                location.reload();
            }
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        createRebuildButton();

        setInterval(checkForUpdates, POLLING_INTERVAL);
        checkForUpdates();
    });
})();