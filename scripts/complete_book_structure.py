#!/usr/bin/env python3
"""Restore missing source pages and complete book-wide accessible structure."""

from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")

PAGE_TWO_TEXT = {
    "pg002_n0001": "© Taasisi ya Elimu Tanzania 2023",
    "pg002_n0002": "Toleo la Kwanza 2018",
    "pg002_n0003": "Toleo la Pili 2023",
    "pg002_n0004": "ISBN: 978-9987-09-901-6",
    "pg002_n0005": "Taasisi ya Elimu Tanzania\nEneo la Mikocheni\n132 Barabara ya Ali Hassan Mwinyi\nS.L.P 35094\n14112 Dar es Salaam",
    "pg002_n0006": "Simu: +255 735 041 170 / +255 735 041 168",
    "pg002_n0007": "Baruapepe: director.general@tie.go.tz",
    "pg002_n0008": "Tovuti: www.tie.go.tz",
    "pg002_n0009": "Haki zote zimehifadhiwa. Hairuhusiwi kunakili, kurudufu, kuchapisha, kutafsiri wala kukitoa kitabu hiki kwa namna yoyote bila idhini ya maandishi kutoka Taasisi ya Elimu Tanzania.",
}

PAGE_TWO_HTML = """<!DOCTYPE html>
<html lang="sw">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kuhesabu Kitabu cha Mwanafunzi</title>
  <meta name="title-id" content="pg002_sec001" />
  <meta name="page-section-id" content="2" />
  <link href="./content/tailwind_output.css" rel="stylesheet">
  <link href="./assets/libs/fontawesome/css/all.min.css" rel="stylesheet">
  <link href="./assets/fonts.css" rel="stylesheet">
</head>
<body class="font-sans min-h-screen flex items-center justify-center">
  <main class="w-full">
    <h1 class="sr-only" id="page-heading">Taarifa za uchapishaji</h1>
    <div id="content" class="container mx-auto max-w-5xl bg-white px-16 py-12 max-lg:px-10 max-sm:px-5 opacity-0">
      <section role="article" data-section-type="text" data-section-id="pg002_sec001" class="mx-auto max-w-4xl space-y-10 text-left text-2xl leading-relaxed text-neutral-800 max-sm:text-lg">
        <p data-id="pg002_n0001" class="font-semibold">© Taasisi ya Elimu Tanzania 2023</p>
        <div class="space-y-1"><p data-id="pg002_n0002">Toleo la Kwanza 2018</p><p data-id="pg002_n0003">Toleo la Pili 2023</p></div>
        <p data-id="pg002_n0004">ISBN: 978-9987-09-901-6</p>
        <p data-id="pg002_n0005" class="whitespace-pre-line">Taasisi ya Elimu Tanzania\nEneo la Mikocheni\n132 Barabara ya Ali Hassan Mwinyi\nS.L.P 35094\n14112 Dar es Salaam</p>
        <div class="space-y-1"><p data-id="pg002_n0006">Simu: +255 735 041 170 / +255 735 041 168</p><p data-id="pg002_n0007">Baruapepe: director.general@tie.go.tz</p><p data-id="pg002_n0008">Tovuti: www.tie.go.tz</p></div>
        <p data-id="pg002_n0009">Haki zote zimehifadhiwa. Hairuhusiwi kunakili, kurudufu, kuchapisha, kutafsiri wala kukitoa kitabu hiki kwa namna yoyote bila idhini ya maandishi kutoka Taasisi ya Elimu Tanzania.</p>
      </section>
    </div>
  </main>
  <div class="relative z-50" id="interface-container"></div>
  <div class="relative z-50" id="nav-container"></div>
  <script src="./assets/offline-preloader.js?v=15"></script>
  <script src="./assets/scorm.js"></script>
  <script src="./assets/enable-image-descriptions.js"></script>
  <script src="./assets/base.bundle.local.js"></script>
</body>
</html>
"""

GRID_52 = (
    (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
    (1, 3, 6, 10, 7, 8, 2, 9, 4, 5),
    (10, 6, 4, 2, 1, 3, 7, 5, 8, 9),
    (8, 3, 6, 7, 1, 10, 5, 2, 9, 4),
    (4, 7, 5, 10, 3, 6, 2, 8, 1, 9),
)


def git_file(name: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"HEAD:{name}"], cwd=ROOT, text=True
    )


def restore_missing_pages() -> None:
    for name in ("pg050_sec001.html", "pg050_sec002.html", "pg062_sec001.html"):
        path = ROOT / name
        if not path.exists():
            path.write_text(git_file(name), encoding="utf-8")
    page62 = ROOT / "pg062_sec001.html"
    source = page62.read_text(encoding="utf-8")
    source = source.replace('data-section-id="pg062_sec002"', 'data-section-id="pg062_sec001"')
    page62.write_text(source, encoding="utf-8")
    page2 = ROOT / "pg002_sec001.html"
    if not page2.exists():
        page2.write_text(PAGE_TWO_HTML, encoding="utf-8")


def catalogs() -> dict[str, tuple[Path, dict, Path, dict]]:
    result = {}
    for lang in LANGS:
        base = ROOT / "content" / "i18n" / lang
        texts_path = base / "texts.json"
        audios_path = base / "audios.json"
        result[lang] = (
            texts_path,
            json.loads(texts_path.read_text(encoding="utf-8")),
            audios_path,
            json.loads(audios_path.read_text(encoding="utf-8")),
        )
    return result


def reusable_audio(texts: dict, audios: dict, value: str) -> str:
    for text_id, text in texts.items():
        if text == value and text_id in audios:
            return audios[text_id]
    raise RuntimeError(f"No reusable audio clip for {value!r}")


def add_catalog_entries(new_values: dict[str, str], require_new_audio: bool = False) -> list[str]:
    created_audio_ids: list[str] = []
    for lang, (texts_path, texts, audios_path, audios) in catalogs().items():
        for text_id, value in new_values.items():
            texts[text_id] = value
            if text_id not in audios:
                if require_new_audio:
                    audios[text_id] = f"{text_id}.mp3"
                    created_audio_ids.append(text_id)
                else:
                    audios[text_id] = reusable_audio(texts, audios, value)
        texts_path.write_text(json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audios_path.write_text(json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sorted(set(created_audio_ids))


def replace_page_52_grid() -> dict[str, str]:
    path = ROOT / "pg052_sec001.html"
    source = path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    cells = []
    for row_number, row in enumerate(GRID_52, 1):
        for column_number, number in enumerate(row, 1):
            text_id = f"pg052_grid_r{row_number}c{column_number}"
            values[text_id] = str(number)
            cells.append(
                f'<span role="cell" tabindex="0" data-id="{text_id}" '
                f'aria-label="Mstari {row_number}, safu {column_number}: {number}">{number}</span>'
            )
    grid = (
        '<div id="zoezi-2-number-grid" role="table" aria-label="Jedwali la namba za Zoezi la 2">'
        + "".join(cells)
        + "</div>"
        + '<img data-id="pg052_im029_crop1" src="images/pg052_im029_crop1.png" '
          'alt="Jedwali la namba lenye safu ya juu ya 1 hadi 10, na safu nyingine nne za namba zilizochanganywa kwa mazoezi ya kusoma." '
          'class="hidden" style="max-width: 100%; height: auto;">'
    )
    source, count = re.subn(
        r'<img\s+data-id="pg052_im029_crop1"[^>]*>', grid, source, count=1, flags=re.S
    )
    if count != 1 and 'id="zoezi-2-number-grid"' not in source:
        raise RuntimeError("Could not replace page 52 number-table image")
    source = source.replace("#zoezi-2-number-grid > button", "#zoezi-2-number-grid > [role=\"cell\"]")
    path.write_text(source, encoding="utf-8")
    return values


def label_page_62_numbers() -> dict[str, str]:
    path = ROOT / "pg062_sec001.html"
    source = path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        value = match.group("value")
        text_id = f"pg062_grid_n{counter:03d}"
        values[text_id] = value
        return match.group("open") + f'<span data-id="{text_id}">{value}</span>' + match.group("close")

    pattern = re.compile(
        r'(?P<open><div\s+class="[^"]*text-2xl[^"]*">)\s*(?P<value>10|[1-9])\s*(?P<close></div>)'
    )
    source, _ = pattern.subn(replace, source)
    path.write_text(source, encoding="utf-8")
    return values


def update_spine() -> None:
    path = ROOT / "content" / "pages.json"
    pages = json.loads(path.read_text(encoding="utf-8"))
    additions = {
        "pg002_sec001": {"section_id": "pg002_sec001", "href": "pg002_sec001.html", "page_number": "ii"},
        "pg050_sec001": {"section_id": "pg050_sec001", "href": "pg050_sec001.html", "page_number": 44},
        "pg050_sec002": {"section_id": "pg050_sec002", "href": "pg050_sec002.html", "page_number": 44},
        "pg062_sec001": {"section_id": "pg062_sec001", "href": "pg062_sec001.html", "page_number": 56},
    }
    by_id = {entry["section_id"]: entry for entry in pages}
    by_id.update(additions)

    def physical(entry: dict) -> tuple[int, int]:
        match = re.match(r"pg(\d{3})_sec(\d{3})", entry["section_id"])
        if not match:
            return (9999, 9999)
        return int(match.group(1)), int(match.group(2))

    ordered = sorted(by_id.values(), key=physical)
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    restore_missing_pages()
    new_audio_ids = add_catalog_entries(PAGE_TWO_TEXT, require_new_audio=True)
    grid_values = replace_page_52_grid()
    grid_values.update(label_page_62_numbers())
    add_catalog_entries(grid_values)
    update_spine()
    ids_path = ROOT / "reports" / "new-page-two-audio-ids.txt"
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.write_text("\n".join(new_audio_ids) + "\n", encoding="utf-8")
    print(
        f"restored_pages=4 accessible_grid_cells={len(grid_values)} "
        f"new_audio_ids={len(new_audio_ids)}"
    )


if __name__ == "__main__":
    main()
