#!/usr/bin/env python3
"""Add visual-only answer boxes to page 22 without form controls."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pg022_sec001.html"

STYLE = """<style data-static-answer-boxes>
  .static-answer-box {
    display: inline-block;
    box-sizing: border-box;
    width: 5.5rem;
    height: 3.4rem;
    border: 2px solid #64748b;
    border-radius: 0.65rem;
    background: #fff;
    box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.2);
    vertical-align: middle;
    pointer-events: none;
    user-select: none;
  }
  @media (max-width: 640px) {
    .static-answer-box { width: 3.6rem; height: 2.6rem; border-radius: 0.45rem; }
  }
</style>"""

BOX = '<span class="static-answer-box" role="img" aria-label="Kisanduku cha jibu kisichoingilika"></span>'


def main() -> None:
    source = PAGE.read_text(encoding="utf-8")
    if "data-static-answer-boxes" not in source:
        source = source.replace("</head>", f"{STYLE}\n</head>", 1)
    for number in range(1, 11):
        anchor = f'<label for="item-{number}"'
        if f'data-static-box-for="item-{number}"' in source:
            continue
        box = BOX.replace('class="static-answer-box"', f'class="static-answer-box" data-static-box-for="item-{number}"')
        source = source.replace(anchor, box + anchor, 1)
    PAGE.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
