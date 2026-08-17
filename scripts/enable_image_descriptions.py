#!/usr/bin/env python3
"""Load the image-description preference before the ADT runtime on every page."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = '    <script src="./assets/enable-image-descriptions.js"></script>\n'
ANCHORS = (
    '    <script src="./assets/base.bundle.local.js"></script>',
    '    <script src="./assets/base.bundle.min.js?v=1" type="module"></script>',
)


def main() -> None:
    changed = 0
    for page in sorted((*ROOT.glob("pg*.html"), *ROOT.glob("qz*.html"), ROOT / "index.html")):
        source = page.read_text(encoding="utf-8")
        if "enable-image-descriptions.js" in source:
            continue
        for anchor in ANCHORS:
            if anchor in source:
                source = source.replace(anchor, SCRIPT + anchor, 1)
                page.write_text(source, encoding="utf-8")
                changed += 1
                break
        else:
            raise RuntimeError(f"No runtime script anchor found in {page.name}")
    print(f"Enabled image descriptions on {changed} page files.")


if __name__ == "__main__":
    main()
