document.addEventListener('DOMContentLoaded', function() {
    console.log("FoodBridge Script Active"); // Confirm it's running in browser console

    // --- INSTANT SEARCH ---
    const searchInput = document.getElementById('donationSearch');
    if (searchInput) {
        searchInput.addEventListener('keyup', function(e) {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('.donation-col').forEach(card => {
                card.style.display = card.textContent.toLowerCase().includes(term) ? 'block' : 'none';
            });
        });
    }

    // --- ROBUST COUNTDOWN TIMER ---
    const timers = document.querySelectorAll('.countdown-timer');

    function updateTimers() {
        const now = new Date().getTime();

        timers.forEach(timer => {
            // 1. Get the raw date string from HTML
            let rawStr = timer.getAttribute('data-expiry');
            if (!rawStr) return;

            // 2. Force standardized ISO format (YYYY-MM-DDTHH:MM)
            // Replaces " at " with "T", Replaces spaces with "T"
            let cleanStr = rawStr.replace(' at ', 'T').replace(' ', 'T');

            // 3. Parse date
            let expiryDate = new Date(cleanStr).getTime();

            // 4. If it fails, try appending seconds ":00" (common fix for some browsers)
            if (isNaN(expiryDate)) {
                expiryDate = new Date(cleanStr + ":00").getTime();
            }

            // 5. If STILL failing, show error instead of stuck on "Calculating..."
            if (isNaN(expiryDate)) {
                timer.innerHTML = "Date Format Error";
                timer.style.color = "red";
                return;
            }

            // 6. Calculate remaining time
            const distance = expiryDate - now;

            if (distance < 0) {
                timer.innerHTML = "EXPIRED";
                timer.classList.add('text-danger');
                // Optional: Disable the claim button
                let btn = timer.closest('.card-body')?.querySelector('button');
                if (btn) btn.disabled = true;
            } else {
                const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                timer.innerHTML = `⏳ ${hours}h ${minutes}m ${seconds}s left`;
            }
        });
    }

    if (timers.length > 0) {
        updateTimers(); // Run once immediately
        setInterval(updateTimers, 1000); // Then every second
    }
});