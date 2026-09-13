(function () {
  "use strict";

  function getBookPageNumber() {
    var meta = document.querySelector('meta[name="title-id"]');
    var match = meta && String(meta.content).match(/^pg(\d{3})_sec/);
    return match ? Number(match[1]) : 0;
  }

  function getVideoForCurrentPage() {
    var meta = document.querySelector('meta[name="title-id"]');
    var titleId = meta && String(meta.content);
    if (titleId === "cover_sec001") {
      return { src: "./content/i18n/sw-TZ/video/front-cover.mp4", label: "Lugha ya ishara, jalada la mbele" };
    }
    if (titleId === "back_cover_sec001") {
      return { src: "./content/i18n/sw-TZ/video/page_134.mp4", label: "Lugha ya ishara, jalada la nyuma" };
    }
    var pageNumber = getBookPageNumber();
    return pageNumber ? {
      src: "./content/i18n/sw-TZ/video/page_" + pageNumber + ".mp4",
      label: "Lugha ya ishara, ukurasa " + pageNumber
    } : null;
  }

  function attachVideo() {
    var handle = document.querySelector(
      '[role="button"][aria-label="sign-language-drag-handle"]'
    );
    if (!handle) return;

    var panel = handle.parentElement;
    if (!panel) return;

    var selectedVideo = getVideoForCurrentPage();
    var existingVideo = panel.querySelector("video");
    if (!selectedVideo) {
      if (existingVideo) existingVideo.remove();
      return;
    }

    var desiredSrc = selectedVideo.src;
    if (existingVideo) {
      if (existingVideo.getAttribute("src") !== desiredSrc) {
        existingVideo.src = desiredSrc;
        existingVideo.setAttribute("aria-label", selectedVideo.label);
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
    video.setAttribute("aria-label", selectedVideo.label);
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
