#!/usr/bin/env python3
"""Synchronize every HTML image alt value with its Swahili description."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
DATA_ID = re.compile(r'\bdata-id="([^"]+)"')
ALT = re.compile(r'\balt="[^"]*"')


def main() -> None:
    texts = json.loads(
        (ROOT / "content" / "i18n" / "sw" / "texts.json").read_text(encoding="utf-8")
    )
    changed_pages = 0
    changed_images = 0

    for page in sorted((*ROOT.glob("pg*.html"), ROOT / "index.html")):
        source = page.read_text(encoding="utf-8")

        def update(match: re.Match[str]) -> str:
            nonlocal changed_images
            tag = match.group(0)
            id_match = DATA_ID.search(tag)
            if not id_match:
                return tag
            description = texts.get(id_match.group(1))
            if not isinstance(description, str) or not description.strip():
                return tag
            replacement = f'alt="{html.escape(description, quote=True)}"'
            updated = ALT.sub(replacement, tag, count=1) if ALT.search(tag) else tag[:-1] + f" {replacement}>"
            if updated != tag:
                changed_images += 1
            return updated

        updated_source = IMAGE_TAG.sub(update, source)
        if updated_source != source:
            page.write_text(updated_source, encoding="utf-8")
            changed_pages += 1

    print(f"Synchronized {changed_images} image descriptions across {changed_pages} pages.")


if __name__ == "__main__":
    main()
