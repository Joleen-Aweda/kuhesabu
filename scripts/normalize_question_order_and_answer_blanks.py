#!/usr/bin/env python3
"""Normalize exercise narration order and answer-blank speech book-wide.

This script edits only the semantic read-aloud layer. It keeps each numbered
question together with all of its associated content while sorting question
groups numerically. Ordinary answer blanks share one localized "Dashi" cue;
the five addition-layout prompts explicitly requested as
"Dashi, ongeza, dashi, jumla, dashi" are preserved.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXTS_PATH = ROOT / "content/i18n/sw-TZ/texts.json"
SEMANTICS_PATH = ROOT / "content/page-semantics.json"

SPECIAL_ANSWER_IDS = {
    "pg030_q1_answer_pattern_v1",
    "pg031_q2_answer_pattern_v1",
    "pg031_q3_answer_pattern_v1",
    "pg031_q4_answer_pattern_v1",
    "pg032_q5_answer_pattern_v1",
}

ORDERED_LIST_RE = re.compile(
    r'(<ol\s+class="adt-page-reading-order"[^>]*>)(.*?)(</ol>)', re.DOTALL
)
LIST_ITEM_RE = re.compile(r"<li\b.*?</li>", re.DOTALL)
ANSWER_BLANK_RE = re.compile(
    r'<span\b(?=[^>]*\bclass="[^"]*\badt-semantic-answer-blank\b[^"]*")[^>]*>.*?</span>',
    re.DOTALL,
)
DATA_ID_RE = re.compile(r'data-id="([^"]+)"')
QUESTION_RE = re.compile(r"(?:Swali namba\s+)?(\d+)\.", re.IGNORECASE)
SECTION_BARRIER_RE = re.compile(
    r"(?:Zoezi|Mfano|Jaribio|Jibu|Njia|Sura|Mada|Kazi)(?:\b|\s)", re.IGNORECASE
)

def standard_blank(blank_id: str) -> str:
    return (
        '<span class="adt-semantic-answer-blank" role="img" '
        f'aria-label="Dashi" data-id="{blank_id}">Dashi.</span>'
    )


def visible_value(fragment: str, texts: dict[str, str]) -> str:
    for data_id in DATA_ID_RE.findall(fragment):
        value = texts.get(data_id)
        if isinstance(value, str) and value.strip():
            return value.strip()
    plain = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return " ".join(plain.split())


def question_number(value: str) -> int | None:
    match = QUESTION_RE.fullmatch(value.strip())
    return int(match.group(1)) if match else None


def sort_question_groups(items: list, value_for_item) -> tuple[list, list[list[int]]]:
    """Sort numbered question chunks inside each exercise/page segment."""
    if not items:
        return items, []

    starts = [0]
    for index, item in enumerate(items):
        if index and SECTION_BARRIER_RE.match(value_for_item(item)):
            starts.append(index)
    starts.append(len(items))

    changed_runs: list[list[int]] = []
    result = list(items)
    for start, end in zip(starts, starts[1:]):
        numbered = [
            (index, question_number(value_for_item(result[index])))
            for index in range(start, end)
        ]
        numbered = [(index, number) for index, number in numbered if number is not None]
        numbers = [number for _, number in numbered]
        if (
            len(numbered) < 2
            or len(numbers) != len(set(numbers))
            or numbers == sorted(numbers)
        ):
            continue

        first_question = numbered[0][0]
        chunks = []
        for offset, (chunk_start, number) in enumerate(numbered):
            chunk_end = numbered[offset + 1][0] if offset + 1 < len(numbered) else end
            chunks.append((number, result[chunk_start:chunk_end]))

        prefix = result[start:first_question]
        sorted_chunks = [chunk for _, chunk in sorted(chunks, key=lambda pair: pair[0])]
        result[start:end] = prefix + [entry for chunk in sorted_chunks for entry in chunk]
        changed_runs.append(numbers)

    return result, changed_runs


def normalize_html(
    texts: dict[str, str],
) -> tuple[set[str], set[str], dict[str, list[list[int]]], int]:
    custom_answer_ids: set[str] = set()
    normalized_answer_ids: set[str] = set()
    changed_orders: dict[str, list[list[int]]] = {}
    normalized_blanks = 0

    for path in sorted(ROOT.glob("pg*.html")):
        source = path.read_text(encoding="utf-8")
        answer_counter = 0

        def reorder_list(match: re.Match[str]) -> str:
            nonlocal source
            opening, body, closing = match.groups()
            items = LIST_ITEM_RE.findall(body)
            if not items:
                return match.group(0)
            separators = LIST_ITEM_RE.split(body)
            ordered, runs = sort_question_groups(
                items, lambda item: visible_value(item, texts)
            )
            if not runs:
                return match.group(0)
            changed_orders.setdefault(path.name, []).extend(runs)
            rebuilt = separators[0] + "".join(
                item + separators[index + 1] for index, item in enumerate(ordered)
            )
            return opening + rebuilt + closing

        source = ORDERED_LIST_RE.sub(reorder_list, source)

        def normalize_blank(match: re.Match[str]) -> str:
            nonlocal answer_counter, normalized_blanks
            fragment = match.group(0)
            ids = DATA_ID_RE.findall(fragment)
            if any(data_id in SPECIAL_ANSWER_IDS for data_id in ids):
                return fragment
            custom_answer_ids.update(ids)
            answer_counter += 1
            blank_id = f"{path.stem}_answer_blank_{answer_counter:03d}"
            normalized_answer_ids.add(blank_id)
            normalized_blanks += 1
            return standard_blank(blank_id)

        updated = ANSWER_BLANK_RE.sub(normalize_blank, source)
        if updated != path.read_text(encoding="utf-8"):
            path.write_text(updated, encoding="utf-8")

    return custom_answer_ids, normalized_answer_ids, changed_orders, normalized_blanks


def block_value(block: dict) -> str:
    value = block.get("text") or block.get("label") or ""
    return value.strip() if isinstance(value, str) else ""


def normalize_semantics(custom_answer_ids: set[str]) -> dict[str, list[list[int]]]:
    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    changed_orders: dict[str, list[list[int]]] = {}

    for page, blocks in semantics.items():
        ordered, runs = sort_question_groups(blocks, block_value)
        if runs:
            changed_orders[page] = runs

        normalized = []
        for block in ordered:
            if block.get("id") in custom_answer_ids:
                normalized.append({"kind": "blank", "label": "Dashi"})
            elif block.get("kind") == "blank":
                replacement = dict(block)
                replacement["label"] = "Dashi"
                normalized.append(replacement)
            else:
                normalized.append(block)
        semantics[page] = normalized

    SEMANTICS_PATH.write_text(
        json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return changed_orders


def add_shared_localization(normalized_answer_ids: set[str]) -> None:
    for locale in ("sw", "sw-TZ"):
        locale_dir = ROOT / "content/i18n" / locale
        texts_path = locale_dir / "texts.json"
        audios_path = locale_dir / "audios.json"

        localized_texts = json.loads(texts_path.read_text(encoding="utf-8"))
        localized_texts["answer_blank_dash"] = "Dashi."
        localized_texts["answer_blank_dash_easy_read"] = "Dashi."
        for blank_id in sorted(normalized_answer_ids):
            localized_texts[blank_id] = "Dashi."
        texts_path.write_text(
            json.dumps(localized_texts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        audio_map = json.loads(audios_path.read_text(encoding="utf-8"))
        audio_map["answer_blank_dash"] = "answer_blank_dash_daudi_v1.mp3"
        audio_map["answer_blank_dash_easy_read"] = (
            "answer_blank_dash_easy_read_daudi_v1.mp3"
        )
        for blank_id in sorted(normalized_answer_ids):
            audio_map[blank_id] = "answer_blank_dash_daudi_v1.mp3"
        audios_path.write_text(
            json.dumps(audio_map, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    texts = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
    custom_ids, normalized_ids, html_orders, normalized_blanks = normalize_html(texts)
    semantic_orders = normalize_semantics(custom_ids)
    add_shared_localization(normalized_ids)

    print(f"Normalized ordinary answer blanks: {normalized_blanks}")
    print(f"Preserved special answer patterns: {len(SPECIAL_ANSWER_IDS)}")
    print("HTML question runs sorted:")
    for page, runs in html_orders.items():
        print(f"  {page}: {runs}")
    print("Semantic manifest question runs sorted:")
    for page, runs in semantic_orders.items():
        print(f"  {page}: {runs}")


if __name__ == "__main__":
    main()
