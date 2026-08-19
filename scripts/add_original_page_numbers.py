#!/usr/bin/env python3
"""Add exactly one accessible original-book page number for every PDF page."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKER_RE = re.compile(
    r'\s*<footer\b[^>]*class="[^"]*adt-original-page-number[^"]*"[^>]*>.*?</footer>',
    re.I | re.S,
)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def label(page: int) -> str:
    roman = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi"}
    return roman.get(page, str(page - 6))


def element_end(source: str, attribute_at: int) -> int:
    start = source.rfind("<", 0, attribute_at)
    open_end = source.find(">", attribute_at)
    if start < 0 or open_end < 0:
        return attribute_at
    match = re.match(r"<\s*([A-Za-z][\w:-]*)", source[start:open_end + 1])
    if not match:
        return open_end + 1
    tag = match.group(1).lower()
    if tag in VOID or source[start:open_end + 1].rstrip().endswith("/>"):
        return open_end + 1
    token_re = re.compile(rf"</?\s*{re.escape(tag)}\b[^>]*>", re.I)
    depth = 0
    for token in token_re.finditer(source, start):
        value = token.group(0)
        if value.lstrip().startswith("</"):
            depth -= 1
            if depth == 0:
                return token.end()
        elif not value.rstrip().endswith("/>"):
            depth += 1
    return open_end + 1


def page_occurrences(source: str, page: int) -> list[int]:
    prefix = f"pg{page:03d}_"
    return [match.start() for match in re.finditer(rf'(?:data-id|data-section-id)=["\']{prefix}', source)]


def ancestors_at(source: str, point: int) -> list[tuple[str, int, str]]:
    token_re = re.compile(r'</?\s*(div|section)\b[^>]*>', re.I)
    stack: list[tuple[str, int, str]] = []
    for match in token_re.finditer(source, 0, point):
        tag = match.group(1).lower()
        token = match.group(0)
        if token.lstrip().startswith('</'):
            for index in range(len(stack) - 1, -1, -1):
                if stack[index][0] == tag:
                    del stack[index:]
                    break
        else:
            stack.append((tag, match.start(), token))
    return stack


def boundary_before_next_page(source: str, next_hit: int) -> int:
    ancestors = ancestors_at(source, next_hit)
    for tag, start, opening in reversed(ancestors):
        classes = re.search(r'class=(["\'])(.*?)\1', opening, re.I | re.S)
        class_value = classes.group(2) if classes else ''
        if tag == 'div' and 'grid' in class_value.split() and 'min-h' in class_value:
            return start
    for tag, start, opening in reversed(ancestors):
        if 'sr-only' not in opening and 'hidden' not in opening:
            return start
    return source.rfind('<', 0, next_hit)


def enclosing_section_close(source: str, hit: int) -> int:
    sections = [item for item in ancestors_at(source, hit) if item[0] == 'section']
    if sections:
        _, start, _ = sections[-1]
        end = element_end(source, start + 1)
        close = source.rfind('</section', start, end)
        if close >= 0:
            return close
    main_close = source.rfind('</main>')
    return main_close if main_close >= 0 else len(source)


def main() -> None:
    paths = sorted((*ROOT.glob("pg*_sec*.html"), ROOT / "index.html"))
    sources = {path: MARKER_RE.sub("", path.read_text(encoding="utf-8")) for path in paths}
    inserted: Counter[Path] = Counter()

    for page in range(1, 133):
        candidates = [(path, page_occurrences(source, page)) for path, source in sources.items()]
        candidates = [(path, hits) for path, hits in candidates if hits]
        if not candidates:
            raise RuntimeError(f"No converted content found for physical PDF page {page}")
        path, hits = max(candidates, key=lambda item: len(item[1]))
        source = sources[path]
        next_hits = page_occurrences(source, page + 1) if page < 132 else []
        later_next_hits = [hit for hit in next_hits if hit > hits[-1]]
        if later_next_hits:
            point = boundary_before_next_page(source, later_next_hits[0])
        else:
            point = enclosing_section_close(source, hits[-1])
        visible = label(page)
        marker = (
            f'<footer class="adt-original-page-number" data-pdf-page="{page}" '
            f'aria-label="Ukurasa wa {visible}"><span aria-hidden="true">{visible}</span></footer>'
        )
        sources[path] = source[:point] + marker + source[point:]
        inserted[path] += 1

    for path, source in sources.items():
        path.write_text(source, encoding="utf-8")

    total = sum(inserted.values())
    print(f"numbered_physical_pages={total} files={len(inserted)}")


if __name__ == "__main__":
    main()
