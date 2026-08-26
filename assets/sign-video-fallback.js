(function () {
  "use strict";

  function getPageNumber() {
    var meta = document.querySelector('meta[name="page-section-id"]');
    var pageNumber = meta ? Number(meta.content) : 0;
    return Number.isInteger(pageNumber) && pageNumber > 0 ? pageNumber : 0;
  }

  function attachVideo() {
    var handle = document.querySelector(
      '[role="button"][aria-label="sign-language-drag-handle"]'
    );
    if (!handle) return;

    var panel = handle.parentElement;
    if (!panel || panel.querySelector("video")) return;

    var pageNumber = getPageNumber();
    if (!pageNumber) return;

    var video = document.createElement("video");
    video.src = "./content/i18n/sw-TZ/video/page_" + pageNumber + ".mp4";
    video.controls = true;
    video.autoplay = true;
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.setAttribute("aria-label", "Lugha ya ishara, ukurasa " + pageNumber);
    video.style.display = "block";
    video.style.width = "100%";
    video.style.height = "calc(100% - 1.5rem)";
    video.style.objectFit = "contain";
    video.style.background = "black";

    var noVideoMessage = panel.querySelector('[role="status"]');
    if (noVideoMessage) noVideoMessage.remove();
    panel.appendChild(video);
    video.play().catch(function () {
      // Controls remain available if the browser blocks autoplay.
    });
  }

  var observer = new MutationObserver(attachVideo);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachVideo, { once: true });
  } else {
    attachVideo();
  }
})();
