#!/usr/bin/env python3
"""Synchronize HTML page-section-id metadata with content/pages.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pages = json.loads((ROOT / "content" / "pages.json").read_text(encoding="utf-8"))
    for position, entry in enumerate(pages, 1):
        path = ROOT / entry["href"]
        source = path.read_text(encoding="utf-8")
        revised, count = re.subn(
            r'(<meta name="page-section-id" content=")\d+("\s*/>)',
            rf"\g<1>{position}\g<2>",
            source,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f"Missing page-section-id in {path.name}")
        if revised != source:
            path.write_text(revised, encoding="utf-8")
    print(f"Synchronized {len(pages)} page-section-id values")


if __name__ == "__main__":
    main()
