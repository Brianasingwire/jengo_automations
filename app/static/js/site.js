// The site's only JavaScript. Everything works without it; this adds polish.
(function () {
  "use strict";
  window.jengoSiteJs = true; // tells the inline fallback in base.html that we loaded

  // Mobile menu: [data-menu-toggle] shows/hides the element named in its aria-controls.
  document.querySelectorAll("[data-menu-toggle]").forEach(function (button) {
    var menu = document.getElementById(button.getAttribute("aria-controls"));
    function setOpen(open) {
      menu.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      button.querySelector("[data-icon-open]").hidden = open;
      button.querySelector("[data-icon-close]").hidden = !open;
    }
    button.addEventListener("click", function () {
      setOpen(menu.hidden);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !menu.hidden) {
        setOpen(false);
        button.focus();
      }
    });
  });

  // Forms with [data-submit-state]: disable the button and show "Sending…" on submit.
  document.querySelectorAll("form[data-submit-state]").forEach(function (form) {
    var button = form.querySelector("button[type=submit]");
    var idle = button.querySelector("[data-idle]");
    var busy = button.querySelector("[data-busy]");
    function setBusy(isBusy) {
      button.disabled = isBusy;
      button.classList.toggle("opacity-70", isBusy);
      button.classList.toggle("cursor-wait", isBusy);
      idle.hidden = isBusy;
      busy.hidden = !isBusy;
    }
    form.addEventListener("submit", function () {
      setBusy(true);
    });
    // Coming back via the browser's back button restores the page from cache: re-enable.
    window.addEventListener("pageshow", function () {
      setBusy(false);
    });
  });

  // Fade .reveal elements in as they scroll into view (see input.css).
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".reveal").forEach(function (el) {
      io.observe(el);
    });
  }
})();
