#!/usr/bin/env python3
"""Synchronize ADT emphasis with the original PDF without changing visible text."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pdfplumber


WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)
DATA_TAG_RE = re.compile(r"<(?P<tag>[a-zA-Z][\w:-]*)(?P<attrs>[^>]*?\bdata-id=(?P<q>['\"])(?P<id>[^'\"]+)(?P=q)[^>]*)>")
TITLE_WORDS = re.compile(
    r"^(?:sura\b|zoezi\b|jaribio\b|mfano\b|kazi\b|shukurani\b|dibaji\b|yaliyomo\b|"
    r"utangulizi\b|marejeleo\b|kielelezo\b|faharasa\b)", re.IGNORECASE
)


def tokens(value: str) -> tuple[str, ...]:
    value = unicodedata.normalize("NFKC", value).replace("[[blank:", " ")
    return tuple(x.casefold() for x in WORD_RE.findall(value))


def is_bold_font(fontname: str) -> bool:
    name = fontname.casefold()
    return any(marker in name for marker in ("bold", "black", "heavy", "semibold", "demi"))


def source_bold_sequences(pdf_path: Path) -> dict[int, set[tuple[str, ...]]]:
    result: dict[int, set[tuple[str, ...]]] = defaultdict(set)
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(extra_attrs=["fontname", "size"], use_text_flow=True)
            # Retain each bold run, then all of its contiguous sub-runs. Text IDs
            # often split a PDF heading into smaller accessible phrases.
            runs: list[list[str]] = []
            current: list[str] = []
            previous_top: float | None = None
            previous_right: float | None = None
            for word in words:
                word_tokens = list(tokens(word.get("text", "")))
                bold = is_bold_font(str(word.get("fontname", "")))
                top = float(word.get("top", 0))
                left = float(word.get("x0", 0))
                new_line = previous_top is not None and abs(top - previous_top) > 3.0
                large_gap = previous_right is not None and left - previous_right > 42.0
                if not bold or new_line or large_gap:
                    if current:
                        runs.append(current)
                    current = []
                if bold and word_tokens:
                    current.extend(word_tokens)
                previous_top = top
                previous_right = float(word.get("x1", left))
            if current:
                runs.append(current)

            for run in runs:
                for start in range(len(run)):
                    for end in range(start + 1, len(run) + 1):
                        result[page_number].add(tuple(run[start:end]))
    return result


def add_bold_class(tag_match: re.Match[str]) -> tuple[str, bool]:
    full = tag_match.group(0)
    attrs = tag_match.group("attrs")
    if re.search(r"\bfont-(?:bold|semibold|extrabold|black)\b", attrs):
        return full, False
    class_match = re.search(r"\bclass=(['\"])(.*?)\1", attrs, re.DOTALL)
    if class_match:
        old = class_match.group(0)
        quote = class_match.group(1)
        classes = class_match.group(2).strip()
        new = f"class={quote}{classes} font-bold{quote}"
        return full.replace(old, new, 1), True
    insert_at = full.rfind(">")
    return full[:insert_at] + ' class="font-bold"' + full[insert_at:], True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    texts = json.loads((root / "content/i18n/sw/texts.json").read_text(encoding="utf-8"))
    bold_by_page = source_bold_sequences(args.pdf)
    changed_ids: list[str] = []
    changed_files: set[str] = set()
    applied_ids: list[str] = []
    applied_files: set[str] = set()

    for html_path in sorted(root.glob("pg*_sec*.html")):
        match_page = re.match(r"pg(\d{3})_", html_path.name)
        if not match_page:
            continue
        page_number = int(match_page.group(1))
        source_sequences = bold_by_page.get(page_number, set())
        source = html_path.read_text(encoding="utf-8")

        def replace(match: re.Match[str]) -> str:
            text_id = match.group("id")
            visible = str(texts.get(text_id, ""))
            phrase = tokens(visible)
            tag = match.group("tag").casefold()
            if "_im" in text_id:
                return match.group(0)
            semantic_title = tag in {"h1", "h2", "h3", "h4", "h5", "h6"}
            named_title = bool(TITLE_WORDS.search(visible.strip())) and len(phrase) <= 14
            # Page numbers and exercise numerals repeat frequently, so token-only
            # matching cannot place them safely. Image data IDs describe artwork
            # rather than printed typography. Exclude both from automatic styling.
            has_letter = any(character.isalpha() for character in visible)
            pdf_bold = (
                bool(phrase)
                and has_letter
                and phrase in source_sequences
            )
            if not (pdf_bold or semantic_title or named_title):
                return match.group(0)
            applied_ids.append(text_id)
            applied_files.add(html_path.name)
            updated, did_change = add_bold_class(match)
            if did_change:
                changed_ids.append(text_id)
                changed_files.add(html_path.name)
            return updated

        updated = DATA_TAG_RE.sub(replace, source)
        if updated != source:
            html_path.write_text(updated, encoding="utf-8")

    report = {
        "source_pdf": str(args.pdf),
        "changed_file_count": len(changed_files),
        "changed_text_id_count": len(set(changed_ids)),
        "changed_files": sorted(changed_files),
        "changed_text_ids": sorted(set(changed_ids)),
        "applied_file_count": len(applied_files),
        "applied_text_id_count": len(set(applied_ids)),
        "applied_files": sorted(applied_files),
        "applied_text_ids": sorted(set(applied_ids)),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("changed_file_count", "changed_text_id_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
