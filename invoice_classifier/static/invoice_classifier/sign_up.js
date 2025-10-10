(function () {
  function onReady(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  onReady(function () {
    var passwordInput = document.getElementById("id_password1");
    var strengthContainer = document.querySelector("[data-password-strength]");

    if (!passwordInput || !strengthContainer) {
      return;
    }

    var strengthBar = strengthContainer.querySelector("[data-strength-bar]");
    var strengthText = strengthContainer.querySelector("[data-strength-text]");

    if (!strengthBar || !strengthText) {
      return;
    }

    var meterColors = ["#d64550", "#e67e22", "#f1c40f", "#27ae60", "#2ecc71"];
    var descriptions = ["Muy débil", "Débil", "Aceptable", "Fuerte", "Muy fuerte"];

    function evaluateStrength(value) {
      var score = 0;

      if (value.length >= 8) score += 1;
      if (value.length >= 12) score += 1;
      if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
      if (/\d/.test(value)) score += 1;
      if (/[^A-Za-z0-9]/.test(value)) score += 1;

      return Math.min(score, 4);
    }

    function updateStrength(value) {
      if (!value) {
        strengthBar.style.setProperty("--strength-width", "0%");
        strengthBar.style.setProperty("--strength-color", meterColors[0]);
        strengthText.textContent = "Escribe una contraseña segura.";
        return;
      }

      var score = evaluateStrength(value);
      var progress = Math.min(score + 1, 5) * 20 + "%";
      var color = meterColors[score];

      strengthBar.style.setProperty("--strength-width", progress);
      strengthBar.style.setProperty("--strength-color", color);
      strengthText.textContent = descriptions[score];
    }

    passwordInput.addEventListener("input", function (event) {
      updateStrength(event.target.value);
    });

    updateStrength(passwordInput.value || "");
  });
})();
