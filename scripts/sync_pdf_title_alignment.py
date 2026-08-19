#!/usr/bin/env python3
"""Match semantic title centering to the original PDF page geometry."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import pdfplumber


WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)
TAG_RE = re.compile(
    r'<(?P<tag>h[1-6]|div|p|span)(?P<attrs>[^>]*\bdata-id=(?P<q>["\'])(?P<id>pg\d{3}_[^"\']+)(?P=q)[^>]*)>',
    re.I,
)
TITLE_RE = re.compile(
    r"^(?:sura\b|zoezi\b|jaribio\b|mfano\b|kazi\b|shukurani\b|dibaji\b|yaliyomo\b|"
    r"utangulizi\b|marejeleo\b|kielelezo\b|faharasa\b|kutambua\b|kujumlisha\b|kutoa\b|"
    r"kupanga\b|tuhesabu\b)",
    re.I,
)


def tokens(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value)
    return tuple(word.casefold() for word in WORD_RE.findall(normalized))


def pdf_lines(pdf_path: Path) -> dict[int, list[tuple[tuple[str, ...], float, float, float]]]:
    result: dict[int, list[tuple[tuple[str, ...], float, float, float]]] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(use_text_flow=True, x_tolerance=2, y_tolerance=3)
            groups: list[list[dict]] = []
            for word in sorted(words, key=lambda item: (round(float(item["top"]) / 3), float(item["x0"]))):
                if not groups or abs(float(word["top"]) - float(groups[-1][0]["top"])) > 3:
                    groups.append([word])
                else:
                    groups[-1].append(word)
            lines = []
            for group in groups:
                group.sort(key=lambda item: float(item["x0"]))
                line_tokens = tokens(" ".join(str(item["text"]) for item in group))
                if line_tokens:
                    lines.append((line_tokens, float(group[0]["x0"]), float(group[-1]["x1"]), float(page.width)))
            result[page_number] = lines
    return result


def is_centered(phrase: tuple[str, ...], lines: list[tuple[tuple[str, ...], float, float, float]]) -> bool | None:
    matches = []
    for line_tokens, x0, x1, width in lines:
        if len(phrase) > len(line_tokens):
            continue
        for start in range(len(line_tokens) - len(phrase) + 1):
            if line_tokens[start:start + len(phrase)] == phrase:
                matches.append((x0, x1, width))
    if len(matches) != 1:
        return None
    x0, x1, width = matches[0]
    return abs(((x0 + x1) / 2) - (width / 2)) <= width * 0.10


def align_tag(match: re.Match[str], center: bool) -> str:
    full = match.group(0)
    attrs = match.group("attrs")
    class_match = re.search(r'\bclass=(["\'])(.*?)\1', attrs, re.S)
    desired = "text-center" if center else "text-left"
    opposite = "text-left" if center else "text-center"
    if class_match:
        classes = re.sub(rf"(?:^|\s){opposite}(?=\s|$)", " ", class_match.group(2))
        if not re.search(rf"(?:^|\s){desired}(?:\s|$)", classes):
            classes += " " + desired
        classes = re.sub(r"\s+", " ", classes).strip()
        old = class_match.group(0)
        new = f'class={class_match.group(1)}{classes}{class_match.group(1)}'
        return full.replace(old, new, 1)
    return full[:-1] + f' class="{desired}">' 


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    texts = json.loads((root / "content/i18n/sw/texts.json").read_text(encoding="utf-8"))
    lines = pdf_lines(args.pdf)
    changed_ids: set[str] = set()
    centered_ids: set[str] = set()

    for path in sorted((*root.glob("pg*_sec*.html"), root / "index.html")):
        source = path.read_text(encoding="utf-8")

        def replace(match: re.Match[str]) -> str:
            text_id = match.group("id")
            value = str(texts.get(text_id, "")).strip()
            phrase = tokens(value)
            semantic = match.group("tag").lower().startswith("h")
            named = bool(TITLE_RE.search(value)) and len(phrase) <= 14
            if not phrase or not (semantic or named):
                return match.group(0)
            page_match = re.match(r"pg(\d{3})_", text_id)
            if not page_match:
                return match.group(0)
            center = is_centered(phrase, lines.get(int(page_match.group(1)), []))
            if center is None:
                return match.group(0)
            revised = align_tag(match, center)
            if center:
                centered_ids.add(text_id)
            if revised != match.group(0):
                changed_ids.add(text_id)
            return revised

        revised = TAG_RE.sub(replace, source)
        if revised != source:
            path.write_text(revised, encoding="utf-8")

    report = {
        "changed_text_id_count": len(changed_ids),
        "changed_text_ids": sorted(changed_ids),
        "centered_text_id_count": len(centered_ids),
        "centered_text_ids": sorted(centered_ids),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("changed_text_id_count", "centered_text_id_count")}))


if __name__ == "__main__":
    main()
