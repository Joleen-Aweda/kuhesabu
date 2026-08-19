#!/usr/bin/env python3
"""Restore non-editable answer boxes at the book's former answer locations."""

from __future__ import annotations

import json
import html
import re
import subprocess
import tarfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = Path('/private/tmp/kuhesabu-before-rollback-20260819T1300.tgz')

MARKER_RE = re.compile(
    r'<span\b[^>]*class="[^"]*adt-answer-line[^"]*"[^>]*></span>', re.I
)
BOX_RE = re.compile(
    r'<span\b[^>]*class="[^"]*adt-static-answer-box[^"]*"[^>]*></span>', re.I
)
STYLE_RE = re.compile(r'<style\s+data-static-answer-boxes>.*?</style>\s*', re.I | re.S)

STYLE = """<style data-static-answer-boxes>
  .adt-static-answer-box {
    display: inline-block;
    box-sizing: border-box;
    width: 6rem;
    height: 2.75rem;
    margin: .25rem .4rem;
    border: 2px solid #94a3b8;
    border-radius: .55rem;
    background: #fff;
    vertical-align: middle;
    pointer-events: none;
    user-select: none;
  }
  .adt-static-answer-box-wide {
    display: block;
    width: 100%;
    min-width: 10rem;
    height: 3.5rem;
    margin: .45rem 0;
  }
  .adt-static-answer-box-drawing {
    display: block;
    width: 100%;
    min-width: 12rem;
    height: 8rem;
    margin: .55rem 0;
  }
  [data-static-answer-source="true"] {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
  }
  .adt-static-answer-layout {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: .1rem;
    max-width: 100%;
  }
</style>"""


def box(kind: str = 'short') -> str:
    extra = ''
    if kind == 'wide':
        extra = ' adt-static-answer-box-wide'
    elif kind == 'drawing':
        extra = ' adt-static-answer-box-drawing'
    return (
        f'<span class="adt-static-answer-box{extra}" role="img" '
        'aria-label="Nafasi ya jibu isiyoharirika"></span>'
    )


def marker_kind(tag: str) -> str:
    lowered = tag.lower()
    if 'drawing' in lowered:
        return 'drawing'
    if 'long' in lowered or 'wide' in lowered:
        return 'wide'
    return 'short'


def nearest_anchor(source: str, start: int, end: int) -> tuple[str | None, str]:
    window_start = max(0, start - 3000)
    before = list(re.finditer(r'data-id="([^"]+)"', source[window_start:start]))
    after = re.search(r'data-id="([^"]+)"', source[end:end + 3000])
    before_id = before[-1].group(1) if before else None
    before_distance = start - (window_start + before[-1].start()) if before else 999999
    after_id = after.group(1) if after else None
    after_distance = after.start() if after else 999999
    if before_distance <= after_distance:
        return before_id, 'after'
    return after_id, 'before'


def marker_is_image_choice(source: str, start: int, end: int, tag: str) -> bool:
    if 'choice-line' in tag.lower():
        return True
    label_start = source.rfind('<label', 0, start)
    label_end = source.find('</label>', end)
    if label_start < 0 or label_end < 0:
        return False
    prior_close = source.find('</label>', label_start, start)
    return prior_close < 0 and '<img' in source[label_start:label_end].lower()


def archive_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if not SNAPSHOT.exists():
        raise FileNotFoundError(f'Missing answer-position snapshot: {SNAPSHOT}')
    with tarfile.open(SNAPSHOT) as archive:
        for member in archive.getmembers():
            name = member.name.removeprefix('./')
            if not name.endswith('.html') or name.startswith('qz') or name == 'pg019_sec001.html':
                continue
            stream = archive.extractfile(member)
            if stream is None:
                continue
            source = stream.read().decode('utf-8', errors='ignore')
            markers = list(MARKER_RE.finditer(source))
            if not markers:
                continue
            pieces: list[str] = []
            cursor = 0
            pending: list[dict[str, object]] = []
            clean_length = 0
            for marker in markers:
                chunk = source[cursor:marker.start()]
                pieces.append(chunk)
                clean_length += len(chunk)
                cursor = marker.end()
                tag = marker.group(0)
                if marker_is_image_choice(source, marker.start(), marker.end(), tag):
                    continue
                anchor, relation = nearest_anchor(source, marker.start(), marker.end())
                pending.append({
                    'source_name': name,
                    'position': clean_length,
                    'kind': marker_kind(tag),
                    'anchor': anchor,
                    'relation': relation,
                })
            pieces.append(source[cursor:])
            cleaned = ''.join(pieces)
            for record in pending:
                record['cleaned'] = cleaned
                records.append(record)
    return records


def current_pages() -> dict[str, str]:
    pages: dict[str, str] = {}
    for path in ROOT.glob('*.html'):
        if path.name.startswith('qz'):
            continue
        source = path.read_text(encoding='utf-8')
        source = BOX_RE.sub('', source)
        source = STYLE_RE.sub('', source)
        pages[path.name] = source
    return pages


def anchor_occurrences(pages: dict[str, str], anchor: str) -> list[tuple[str, int]]:
    needle = f'data-id="{anchor}"'
    hits: list[tuple[str, int]] = []
    for name, source in pages.items():
        offset = 0
        while True:
            found = source.find(needle, offset)
            if found < 0:
                break
            hits.append((name, found))
            offset = found + len(needle)
    return hits


def insertion_for_anchor(source: str, anchor_at: int, relation: str) -> int | None:
    tag_start = source.rfind('<', 0, anchor_at)
    tag_end = source.find('>', anchor_at)
    if tag_start < 0 or tag_end < 0:
        return None
    if relation == 'before':
        return tag_start
    match = re.match(r'<\s*([a-zA-Z0-9:-]+)\b', source[tag_start:tag_end + 1])
    if not match:
        return tag_end + 1
    tag_name = match.group(1)
    opening = source[tag_start:tag_end + 1]
    if opening.rstrip().endswith('/>') or tag_name.lower() in {'img', 'input', 'br', 'hr', 'meta', 'link'}:
        return tag_end + 1
    closing = re.search(rf'</\s*{re.escape(tag_name)}\s*>', source[tag_end + 1:], re.I)
    if closing is None:
        return tag_end + 1
    return tag_end + 1 + closing.end()


def element_bounds(source: str, anchor_at: int) -> tuple[int, int, int, int] | None:
    tag_start = source.rfind('<', 0, anchor_at)
    tag_end = source.find('>', anchor_at)
    if tag_start < 0 or tag_end < 0:
        return None
    match = re.match(r'<\s*([a-zA-Z0-9:-]+)\b', source[tag_start:tag_end + 1])
    if not match:
        return None
    tag_name = match.group(1)
    opening = source[tag_start:tag_end + 1]
    if opening.rstrip().endswith('/>') or tag_name.lower() in {'img', 'input', 'br', 'hr', 'meta', 'link'}:
        return tag_start, tag_end, tag_end + 1, tag_end + 1
    closing = re.search(rf'</\s*{re.escape(tag_name)}\s*>', source[tag_end + 1:], re.I)
    if closing is None:
        return None
    close_start = tag_end + 1 + closing.start()
    close_end = tag_end + 1 + closing.end()
    return tag_start, tag_end, close_start, close_end


def restore_archive_boxes(pages: dict[str, str]) -> tuple[dict[str, list[tuple[int, str]]], set[str], int]:
    insertions: dict[str, list[tuple[int, str]]] = defaultdict(list)
    used_anchors: set[str] = set()
    restored = 0
    for record in archive_records():
        cleaned = str(record['cleaned'])
        position = int(record['position'])
        target: tuple[str, int] | None = None
        for radius in (160, 120, 80, 60, 40, 25):
            before = cleaned[max(0, position - radius):position]
            after = cleaned[position:position + radius]
            needle = before + after
            matches: list[tuple[str, int]] = []
            if not needle:
                continue
            for name, source in pages.items():
                if name == 'pg019_sec001.html':
                    continue
                offset = 0
                while True:
                    found = source.find(needle, offset)
                    if found < 0:
                        break
                    matches.append((name, found + len(before)))
                    offset = found + 1
            if len(matches) == 1:
                target = matches[0]
                break
        anchor = record.get('anchor')
        if target is None and isinstance(anchor, str):
            hits = anchor_occurrences(pages, anchor)
            hits = [hit for hit in hits if hit[0] != 'pg019_sec001.html']
            if len(hits) == 1:
                name, anchor_at = hits[0]
                point = insertion_for_anchor(pages[name], anchor_at, str(record['relation']))
                if point is not None:
                    target = (name, point)
        if target is None:
            continue
        name, point = target
        insertions[name].append((point, box(str(record['kind']))))
        if isinstance(anchor, str):
            used_anchors.add(anchor)
        restored += 1
    return insertions, used_anchors, restored


def old_token_answers() -> dict[str, str]:
    raw = subprocess.check_output(['git', 'show', 'HEAD:content/i18n/sw/texts.json'], cwd=ROOT)
    catalog = json.loads(raw)
    answers: dict[str, str] = {}
    for key, value in catalog.items():
        if not isinstance(value, str):
            continue
        if re.search(r'\[\[blank:[^\]]+\]\]', value):
            answers[key] = value
    return answers


def token_layout(template: str) -> tuple[str, int]:
    parts = re.split(r'(\[\[blank:[^\]]+\]\])', template)
    markup: list[str] = ['<span class="adt-static-answer-layout" aria-hidden="true">']
    count = 0
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r'\[\[blank:[^\]]+\]\]', part):
            markup.append(box('short'))
            count += 1
        else:
            markup.append(html.escape(part))
    markup.append('</span>')
    return ''.join(markup), count


def add_token_boxes(
    pages: dict[str, str],
    insertions: dict[str, list[tuple[int, str]]],
    used_anchors: set[str],
) -> int:
    restored = 0
    for anchor, template in old_token_answers().items():
        if anchor in used_anchors:
            continue
        hits = anchor_occurrences(pages, anchor)
        hits = [hit for hit in hits if hit[0] != 'pg019_sec001.html']
        if len(hits) != 1:
            continue
        name, anchor_at = hits[0]
        bounds = element_bounds(pages[name], anchor_at)
        if bounds is None:
            continue
        _, open_end, _, close_end = bounds
        layout, count = token_layout(template)
        insertions[name].append((open_end, ' data-static-answer-source="true"'))
        insertions[name].append((close_end, layout))
        restored += count
    return restored


def apply_insertions(pages: dict[str, str], insertions: dict[str, list[tuple[int, str]]]) -> int:
    changed = 0
    for name, source in pages.items():
        items = insertions.get(name, [])
        if not items:
            path = ROOT / name
            if path.read_text(encoding='utf-8') != source:
                path.write_text(source, encoding='utf-8')
                changed += 1
            continue
        grouped: dict[int, list[str]] = defaultdict(list)
        for point, markup in items:
            grouped[point].append(markup)
        for point in sorted(grouped, reverse=True):
            source = source[:point] + ''.join(grouped[point]) + source[point:]
        source = source.replace('</head>', STYLE + '\n</head>', 1)
        (ROOT / name).write_text(source, encoding='utf-8')
        changed += 1
    return changed


def main() -> None:
    pages = current_pages()
    insertions, used_anchors, archive_count = restore_archive_boxes(pages)
    token_count = add_token_boxes(pages, insertions, used_anchors)
    changed = apply_insertions(pages, insertions)
    print(
        f'changed_files={changed} archive_boxes={archive_count} '
        f'token_boxes={token_count} total_boxes={archive_count + token_count}'
    )


if __name__ == '__main__':
    main()
