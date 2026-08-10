#!/usr/bin/env python3
"""Apply the book-wide language, typography, and spine fixes from the QA matrix."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")

# Inclusive alternatives retain the original learning action while supporting
# pupils who access the page through touch or read-aloud rather than sight alone.
PREFIXES = (
    ("Tambua ", "Chunguza, gusa au sikiliza maelezo, kisha tambua "),
    ("Hesabu ", "Chunguza, gusa au sikiliza maelezo, kisha hesabu "),
    ("Soma namba ", "Soma, onyesha au wasilisha namba "),
    ("Chunguza maumbo ", "Chunguza, gusa au sikiliza maelezo ya maumbo "),
)


def inclusive(text: str) -> str:
    for old, new in PREFIXES:
        if text.startswith(old):
            return new + text[len(old) :]
    return text


def update_texts() -> dict[str, tuple[str, str]]:
    changed: dict[str, tuple[str, str]] = {}
    for lang in LANGS:
        path = ROOT / "content" / "i18n" / lang / "texts.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, old in list(data.items()):
            if not isinstance(old, str):
                continue
            new = inclusive(old)
            if new != old:
                data[key] = new
                changed.setdefault(key, (old, new))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def update_html(changed: dict[str, tuple[str, str]]) -> None:
    for path in sorted(ROOT.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        revised = source.replace("font-serif", "font-sans")
        revised = revised.replace("font-black", "font-bold").replace("font-extrabold", "font-bold")
        revised = re.sub(r'<body class="(?![^"]*\bfont-sans\b)', '<body class="font-sans ', revised)
        for old, new in changed.values():
            revised = revised.replace(old, new)
            revised = revised.replace(html.escape(old, quote=True), html.escape(new, quote=True))
        if revised != source:
            path.write_text(revised, encoding="utf-8")


def remove_blank_spine_entry() -> None:
    pages_path = ROOT / "content" / "pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))
    pages = [p for p in pages if p["section_id"] != "pg051_sec001"]
    pages_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for index, page in enumerate(pages, 1):
        path = ROOT / page["href"]
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        revised = re.sub(
            r'(<meta name="page-section-id" content=")\d+("\s*/>)',
            rf"\g<1>{index}\g<2>",
            source,
            count=1,
        )
        if revised != source:
            path.write_text(revised, encoding="utf-8")


def main() -> None:
    changed = update_texts()
    update_html(changed)
    remove_blank_spine_entry()
    report = ROOT / "matrix-corrected-audio-ids.txt"
    report.write_text("\n".join(sorted(changed)) + "\n", encoding="utf-8")
    print(f"Updated {len(changed)} localized text/audio IDs")


if __name__ == "__main__":
    main()
