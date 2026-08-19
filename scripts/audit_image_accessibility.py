#!/usr/bin/env python3
"""Audit every textbook image for Swahili text and read-aloud audio."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")


class ImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.images.append({key: value or "" for key, value in attrs})


def main() -> None:
    catalogs = {}
    for lang in LANGS:
        base = ROOT / "content" / "i18n" / lang
        catalogs[lang] = (
            json.loads((base / "texts.json").read_text(encoding="utf-8")),
            json.loads((base / "audios.json").read_text(encoding="utf-8")),
            base / "audio",
        )

    errors: list[str] = []
    total = 0
    for page in sorted((*ROOT.glob("pg*.html"), ROOT / "index.html")):
        parser = ImageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for image in parser.images:
            total += 1
            text_id = image.get("data-id", "").strip()
            alt = image.get("alt", "").strip()
            if not text_id:
                if image.get("aria-hidden", "").casefold() == "true" and not alt:
                    continue
                visual_id = image.get("data-visual-id", "").strip()
                if visual_id and f'data-id="{visual_id}"' in page.read_text(encoding="utf-8"):
                    continue
                errors.append(f"{page.name}: image without data-id")
                continue
            if not alt:
                errors.append(f"{page.name}:{text_id}: empty alt text")
            sw_description = catalogs["sw"][0].get(text_id, "")
            if isinstance(sw_description, str) and sw_description.strip() and alt != sw_description:
                errors.append(f"{page.name}:{text_id}: HTML alt text differs from Swahili description")
            for lang, (texts, audios, audio_dir) in catalogs.items():
                description = texts.get(text_id, "")
                filename = audios.get(text_id, "")
                if not isinstance(description, str) or not description.strip():
                    errors.append(f"{page.name}:{text_id}: missing {lang} description")
                if not filename:
                    errors.append(f"{page.name}:{text_id}: missing {lang} audio mapping")
                elif not (audio_dir / filename).is_file():
                    errors.append(f"{page.name}:{text_id}: missing {lang} audio file {filename}")

    print(f"Audited {total} images across all page files.")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("Every image has alt text, Swahili descriptions, audio mappings, and audio files in both locales.")


if __name__ == "__main__":
    main()
