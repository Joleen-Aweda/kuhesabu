(function enableImageDescriptions() {
  let activeAudio = null;
  const audioMaps = new Map();

  try {
    window.localStorage.setItem("describeImagesMode", "true");
  } catch (_) {
    document.cookie = "describeImagesMode=true; path=./; SameSite=Lax";
  }

  function currentLanguage() {
    let stored = null;
    try {
      stored = window.localStorage.getItem("currentLanguage");
    } catch (_) {}
    if (stored) {
      try {
        stored = JSON.parse(stored);
      } catch (_) {}
    }
    return stored === "sw" || stored === "sw-TZ" ? stored : "sw-TZ";
  }

  async function playDescription(image) {
    const textId = image.getAttribute("data-id");
    if (!textId) return;
    const language = currentLanguage();
    if (!audioMaps.has(language)) {
      const response = await fetch(`./content/i18n/${language}/audios.json`);
      if (!response.ok) return;
      audioMaps.set(language, await response.json());
    }
    const filename = audioMaps.get(language)[textId];
    if (!filename) return;
    if (activeAudio) activeAudio.pause();
    activeAudio = new Audio(`./content/i18n/${language}/audio/${filename}`);
    await activeAudio.play();
  }

  document.addEventListener("click", (event) => {
    const image = event.target.closest?.("img[data-id]");
    if (image) playDescription(image).catch(() => {});
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const image = event.target.closest?.("img[data-id]");
    if (!image) return;
    event.preventDefault();
    playDescription(image).catch(() => {});
  });

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("img[data-id]").forEach((image) => {
      if (!image.closest("label, button, [role='button']")) {
        image.tabIndex = 0;
        image.setAttribute("role", "button");
      }
      image.setAttribute("aria-label", `${image.alt} Bonyeza kusikiliza maelezo.`);
    });
  });
})();
