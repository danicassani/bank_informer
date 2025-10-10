(function () {
  function onReady(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  }

  onReady(function () {
    var wrappers = document.querySelectorAll("[data-password-wrapper]");

    if (!wrappers.length) {
      return;
    }

    wrappers.forEach(function (wrapper) {
      var input = wrapper.querySelector("input");
      var toggle = wrapper.querySelector("[data-password-toggle]");

      if (!input || !toggle) {
        return;
      }

      var labelSpan = toggle.querySelector("[data-password-toggle-text]");

      function updateState() {
        var isVisible = input.type === "text";
        toggle.classList.toggle("is-active", isVisible);
        toggle.setAttribute("aria-pressed", isVisible ? "true" : "false");
        toggle.setAttribute(
          "aria-label",
          isVisible ? "Ocultar contraseña" : "Mostrar contraseña"
        );

        var labelText = isVisible ? "Ocultar" : "Mostrar";

        if (labelSpan) {
          labelSpan.textContent = labelText;
        } else {
          toggle.textContent = labelText;
        }
      }

      toggle.addEventListener("click", function () {
        var isVisible = input.type === "text";
        input.setAttribute("type", isVisible ? "password" : "text");
        updateState();

        try {
          input.focus({ preventScroll: true });
        } catch (error) {
          input.focus();
        }
      });

      updateState();
    });
  });
})();
