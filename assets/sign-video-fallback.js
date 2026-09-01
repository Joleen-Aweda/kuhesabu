(function () {
  "use strict";

  function getBookPageNumber() {
    var meta = document.querySelector('meta[name="title-id"]');
    var match = meta && String(meta.content).match(/^pg(\d{3})_sec/);
    return match ? Number(match[1]) : 0;
  }

  function attachVideo() {
    var handle = document.querySelector(
      '[role="button"][aria-label="sign-language-drag-handle"]'
    );
    if (!handle) return;

    var panel = handle.parentElement;
    if (!panel) return;

    var pageNumber = getBookPageNumber();
    var existingVideo = panel.querySelector("video");
    if (!pageNumber) {
      if (existingVideo) existingVideo.remove();
      return;
    }

    var desiredSrc = "./content/i18n/sw-TZ/video/page_" + pageNumber + ".mp4";
    if (existingVideo) {
      if (!existingVideo.getAttribute("src")?.endsWith("/video/page_" + pageNumber + ".mp4") &&
          existingVideo.getAttribute("src") !== desiredSrc) {
        existingVideo.src = desiredSrc;
        existingVideo.setAttribute("aria-label", "Lugha ya ishara, ukurasa " + pageNumber);
        existingVideo.load();
        existingVideo.play().catch(function () {});
      }
      return;
    }

    var video = document.createElement("video");
    video.src = desiredSrc;
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
