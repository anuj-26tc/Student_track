// All the JavaScript of the website is in this one file.
(function () {

    // ----- 1. Dark mode button -----
    var root = document.documentElement;
    var themeBtn = document.getElementById("themeBtn");

    function showThemeIcon() {
        if (root.getAttribute("data-theme") === "dark") {
            themeBtn.textContent = "☀️";
        } else {
            themeBtn.textContent = "🌙";
        }
    }

    showThemeIcon();

    themeBtn.addEventListener("click", function () {
        var next = "dark";
        if (root.getAttribute("data-theme") === "dark") {
            next = "light";
        }
        root.setAttribute("data-theme", next);
        try {
            localStorage.setItem("theme", next);
        } catch (e) {}
        showThemeIcon();
    });


    // ----- 2. Menu button on mobile -----
    var menuBtn = document.querySelector(".nav-toggle");
    var menu = document.querySelector(".nav-links");

    if (menuBtn && menu) {
        menuBtn.addEventListener("click", function () {
            menu.classList.toggle("open");
        });
    }


    // ----- 3. Messages: close button and auto hide -----
    document.querySelectorAll(".flash").forEach(function (box) {
        function hideBox() {
            box.classList.add("hide");
            setTimeout(function () {
                box.remove();
            }, 400);
        }
        box.querySelector(".flash-close").addEventListener("click", hideBox);
        setTimeout(hideBox, 6000);
    });


    // ----- 4. Show / hide password -----
    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var box = document.getElementById(btn.getAttribute("data-toggle-password"));
            if (box.type === "password") {
                box.type = "text";
                btn.textContent = "Hide";
            } else {
                box.type = "password";
                btn.textContent = "Show";
            }
        });
    });


    // ----- 5. Nice "Are you sure?" box before delete -----
    var modal = document.getElementById("modal");
    var modalText = document.getElementById("modalText");
    var waitingForm = null;

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();
            waitingForm = form;
            modalText.textContent = form.getAttribute("data-confirm");
            modal.classList.remove("hidden");
        });
    });

    document.getElementById("modalYes").addEventListener("click", function () {
        if (waitingForm) {
            waitingForm.submit();
        }
    });

    document.getElementById("modalNo").addEventListener("click", function () {
        modal.classList.add("hidden");
        waitingForm = null;
    });


    // ----- 6. Numbers count up from 0 -----
    document.querySelectorAll(".count").forEach(function (item) {
        var target = parseInt(item.getAttribute("data-value"), 10);
        var suffix = item.getAttribute("data-suffix") || "";
        var steps = 30;
        var step = 0;

        if (isNaN(target)) {
            return;
        }

        var timer = setInterval(function () {
            step = step + 1;
            item.textContent = Math.round(target * step / steps) + suffix;
            if (step >= steps) {
                clearInterval(timer);
            }
        }, 25);
    });


    // ----- 7. Greeting by time of day -----
    var greet = document.getElementById("greet");

    if (greet) {
        var hour = new Date().getHours();
        var word = "Good evening";
        if (hour < 12) {
            word = "Good morning";
        } else if (hour < 17) {
            word = "Good afternoon";
        }
        greet.textContent = word;
    }


    // ----- 8. Warning if the subject or skill is already added -----
    document.querySelectorAll("input[data-existing]").forEach(function (box) {
        var oldNames = JSON.parse(box.getAttribute("data-existing")).map(function (name) {
            return name.toLowerCase();
        });
        var warning = document.getElementById(box.getAttribute("data-warning"));
        var button = box.form.querySelector("button[type=submit]");

        box.addEventListener("input", function () {
            var typed = box.value.trim().toLowerCase();
            var found = typed !== "" && oldNames.indexOf(typed) !== -1;
            warning.classList.toggle("show", found);
            button.disabled = found;
        });
    });


    // ----- 9. Password strength and match check (profile page) -----
    var newPass = document.getElementById("newPassword");
    var confirmPass = document.getElementById("confirmPassword");

    if (newPass) {
        var fill = document.getElementById("strengthFill");
        var text = document.getElementById("strengthText");

        newPass.addEventListener("input", function () {
            var p = newPass.value;
            var score = 0;
            if (p.length >= 6) { score = score + 1; }
            if (p.length >= 10) { score = score + 1; }
            if (/[A-Z]/.test(p) && /[a-z]/.test(p)) { score = score + 1; }
            if (/[0-9]/.test(p)) { score = score + 1; }
            if (/[^A-Za-z0-9]/.test(p)) { score = score + 1; }

            var names = ["Too short", "Weak", "Okay", "Good", "Strong", "Very strong"];
            var colors = ["#dc2626", "#dc2626", "#d97706", "#65a30d", "#16a34a", "#16a34a"];
            if (p.length === 0) {
                score = 0;
                text.textContent = "";
            } else {
                text.textContent = names[score];
            }
            fill.style.width = (score * 20) + "%";
            fill.style.background = colors[score];
        });

        var matchText = document.getElementById("matchText");

        function checkMatch() {
            if (confirmPass.value === "") {
                matchText.textContent = "";
            } else if (confirmPass.value === newPass.value) {
                matchText.textContent = "✅ Passwords match";
            } else {
                matchText.textContent = "❌ Passwords do not match";
            }
        }

        confirmPass.addEventListener("input", checkMatch);
        newPass.addEventListener("input", checkMatch);
    }


    // ----- 10. Live search in the teacher table -----
    document.querySelectorAll("input[data-filter]").forEach(function (box) {
        var rows = document.querySelectorAll(box.getAttribute("data-filter") + " tr.student-row");

        box.addEventListener("input", function () {
            var typed = box.value.toLowerCase();
            rows.forEach(function (row) {
                if (row.textContent.toLowerCase().indexOf(typed) === -1) {
                    row.style.display = "none";
                } else {
                    row.style.display = "";
                }
            });
        });
    });

})();
