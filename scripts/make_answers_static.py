#!/usr/bin/env python3
"""Convert learner answer controls to non-interactive printed answer lines."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STYLE = """<style data-static-answer-lines>
  .adt-answer-line {
    display: inline-block;
    box-sizing: border-box;
    width: min(8rem, 100%);
    min-width: 3.5rem;
    height: 1.8rem;
    margin: 0.15rem 0.25rem;
    border: 0;
    border-bottom: 2px solid #64748b;
    vertical-align: middle;
  }
  .adt-answer-line-wide {
    display: block;
    width: 100%;
    min-width: 8rem;
    margin: 0.3rem 0;
  }
  .adt-answer-lines {
    display: block;
    box-sizing: border-box;
    width: 100%;
    min-width: 8rem;
    min-height: 6rem;
    margin: 0.35rem 0;
    background: repeating-linear-gradient(to bottom, transparent 0, transparent 1.8rem, #64748b 1.8rem, #64748b calc(1.8rem + 2px));
  }
</style>"""

BLANK = '<span class="adt-answer-line" role="img" aria-label="Mstari wa jibu"></span>'
WIDE = '<span class="adt-answer-line adt-answer-line-wide" role="img" aria-label="Mstari wa jibu"></span>'
LINES = '<span class="adt-answer-lines" role="img" aria-label="Mistari ya jibu"></span>'


def attr(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{re.escape(name)}\s*=\s*(["\'])(.*?)\1', tag, re.I | re.S)
    return match.group(2) if match else None


def input_replacement(match: re.Match[str]) -> str:
    return ''


def strip_activity_logic(source: str) -> str:
    # Static pages must not be rehydrated into answer widgets by the reader runtime.
    source = re.sub(r'data-section-type=(["\'])activity_[^"\']*\1', 'data-section-type="text_and_images"', source, flags=re.I)
    source = re.sub(r'\srole=(["\'])(?:activity|form)\1', ' role="article"', source, flags=re.I)
    for name in (
        "data-correct-answers",
        "data-option-explanations",
        "data-activity-item",
        "data-explanation-id",
        "data-explanation",
        "data-submit-target",
        "data-aria-id",
    ):
        source = re.sub(rf'\s{re.escape(name)}\b(?:\s*=\s*(["\']).*?\1)?', '', source, flags=re.I | re.S)
    source = re.sub(r'\s-id\s*=\s*(["\']).*?\1', '', source, flags=re.I | re.S)
    source = re.sub(r'\bactivity-option\b', 'static-option', source)
    source = re.sub(
        r'<label\b([^>]*)>',
        lambda m: '<label' + re.sub(r'\s+tabindex\s*=\s*(["\'])0\1', '', m.group(1), flags=re.I) + '>',
        source,
        flags=re.I | re.S,
    )
    source = re.sub(r'\bfitb-sentence\b\s*', '', source)
    return source


def remove_submit_controls(source: str) -> str:
    # Remove explicit Tuma wrappers first, then any remaining submit button itself.
    source = re.sub(
        r'<div\b[^>]*>\s*<button\b[^>]*>\s*(?:Tuma|Wasilisha|Submit)\s*</button>\s*</div>',
        '',
        source,
        flags=re.I | re.S,
    )
    source = re.sub(
        r'<button\b[^>]*>\s*(?:Tuma|Wasilisha|Submit)\s*</button>',
        '',
        source,
        flags=re.I | re.S,
    )
    # Quiz submit targets become empty containers after the attribute is stripped.
    source = re.sub(r'<div\b([^>]*)>\s*</div>', lambda m: '' if 'submit' in m.group(1).lower() else m.group(0), source, flags=re.I | re.S)
    return source


def remove_validation_scripts(source: str) -> str:
    source = re.sub(
        r'<script\b[^>]*\bid=(["\'])(?:quiz-correct-answers|quiz-explanations)\1[^>]*>.*?</script>',
        '',
        source,
        flags=re.I | re.S,
    )
    source = re.sub(
        r'<script\b[^>]*>[^<]*window\.correctAnswers\s*=.*?</script>',
        '',
        source,
        flags=re.I | re.S,
    )
    return source


def process_html(path: Path) -> tuple[int, int, int]:
    source = path.read_text(encoding="utf-8")
    original = source
    input_count = len(re.findall(r'<input\b', source, re.I))
    textarea_count = len(re.findall(r'<textarea\b', source, re.I))
    token_count = len(re.findall(r'\[\[blank:[^\]]+\]\]', source, re.I))

    source = re.sub(r'<input\b[^>]*?/?>', input_replacement, source, flags=re.I | re.S)
    source = re.sub(r'<textarea\b[^>]*>.*?</textarea>', '', source, flags=re.I | re.S)
    source = re.sub(r'<select\b[^>]*>.*?</select>', '', source, flags=re.I | re.S)
    source = re.sub(r'<canvas\b[^>]*>.*?</canvas>', '', source, flags=re.I | re.S)
    source = re.sub(r'\[\[blank:[^\]]+\]\]', '', source, flags=re.I)
    # Picture-choice exercises should show only the pictures; an answer line
    # directly attached to an image is visually misleading.
    source = re.sub(
        r'<span class="adt-answer-line(?: adt-answer-line-wide)?" role="img" aria-label="Mstari wa jibu"></span>\s*(?=<img\b)',
        '',
        source,
        flags=re.I,
    )
    source = re.sub(
        r'<span\b[^>]*class="[^"]*\badt-answer-lines?\b[^"]*"[^>]*>\s*</span>',
        '',
        source,
        flags=re.I,
    )
    source = re.sub(r'<style\s+data-static-answer-lines>.*?</style>\s*', '', source, flags=re.I | re.S)
    source = remove_submit_controls(source)
    source = remove_validation_scripts(source)
    source = strip_activity_logic(source)

    if source != original:
        path.write_text(source, encoding="utf-8")
    return input_count, textarea_count, token_count


def replace_catalog_blanks(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for key, value in data.items():
        if isinstance(value, str) and re.search(r'\[\[blank:[^\]]+\]\]', value):
            updated, n = re.subn(r'\[\[blank:[^\]]+\]\]', '', value)
            data[key] = updated
            count += n
        if isinstance(data[key], str) and '______' in data[key]:
            count += data[key].count('______')
            data[key] = data[key].replace('______', '')
    if count:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
    return count


def main() -> None:
    totals = [0, 0, 0]
    changed_files = 0
    for path in sorted(ROOT.glob('*.html')):
        before = path.read_text(encoding="utf-8")
        counts = process_html(path)
        after = path.read_text(encoding="utf-8")
        changed_files += before != after
        totals = [a + b for a, b in zip(totals, counts)]

    catalog_blanks = 0
    for path in sorted((ROOT / 'content' / 'i18n').glob('*/texts.json')):
        catalog_blanks += replace_catalog_blanks(path)

    print(
        f'changed_files={changed_files} inputs={totals[0]} textareas={totals[1]} '
        f'inline_blanks={totals[2]} catalog_blanks={catalog_blanks}'
    )


if __name__ == '__main__':
    main()
