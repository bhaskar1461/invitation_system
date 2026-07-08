// Interactivity for SNIST Guest Portal
document.addEventListener("DOMContentLoaded", function() {
    // Sidebar toggle for mobile layouts
    const sidebar = document.getElementById("sidebar");
    const sidebarCollapse = document.getElementById("sidebarCollapse");
    
    if (sidebar && sidebarCollapse) {
        sidebarCollapse.addEventListener("click", function() {
            sidebar.classList.toggle("active");
        });
    }

    // Confirmation dialogues for critical operations
    const deleteForms = document.querySelectorAll("form[action*='/delete']");
    deleteForms.forEach(form => {
        form.addEventListener("submit", function(event) {
            const guestName = form.dataset.guestName || "this guest";
            const confirmed = confirm(`Are you sure you want to DELETE ${guestName}? This will remove all associated logs and barcode assets permanently.`);
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });

    const regenerateForms = document.querySelectorAll("form[action*='/regenerate']");
    regenerateForms.forEach(form => {
        form.addEventListener("submit", function(event) {
            const guestName = form.dataset.guestName || "this guest";
            const confirmed = confirm(`Are you sure you want to REGENERATE the invitation code for ${guestName}? The old code and barcode will be invalidated.`);
            if (!confirmed) {
                event.preventDefault();
            }
        });
    });

    // Auto-dismiss alert messages after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll(".alert");
        alerts.forEach(alert => {
            const bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        });
    }, 5000);
});
