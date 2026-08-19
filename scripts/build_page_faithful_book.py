#!/usr/bin/env python3
"""Build a 132-page, PDF-faithful ADT with a separate semantic reading layer."""

from __future__ import annotations

import argparse
import html as html_std
import json
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import pymupdf
from lxml import html


ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")
PAGE_ID = re.compile(r"^pg(\d{3})_")
GRID_ID = re.compile(r"^(pg\d{3}_grid\d*)_(n\d+|r\d+c\d+|c\d+)$")
GRID_ROW_COLUMN = re.compile(r"mstari wa\s*(\d+).*nafasi ya\s*(\d+)", re.IGNORECASE)
SKIP_IDS = {
    "pg006_n0001",
    "pg011_n0024",
    "pg017_n0033",
    "pg019_n0093",
    "pg034_n0036",
    "pg039_n0030",
    "pg049_n0072",
    "pg083_n0051",
    "pg100_n0121",
    "pg103_n0045",
    "pg110_n0072",
    "pg126_n0029",
    "pg131_n0074",
    "pg132_n0113",
}

DEFAULT_PDFTOCAIRO = Path(
    "/Users/joleen/.cache/codex-runtimes/codex-primary-runtime/dependencies/"
    "native/poppler/poppler/bin/pdftocairo"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text_id(text_id: str) -> bool:
    lowered = text_id.casefold()
    return (
        bool(PAGE_ID.match(text_id))
        and text_id not in SKIP_IDS
        and not lowered.endswith("_easy_read")
        and "_ans" not in lowered
        and "answer" not in lowered
    )


def page_number_for_id(text_id: str) -> int | None:
    match = PAGE_ID.match(text_id)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 132 else None


def has_hidden_ancestor(element) -> bool:
    current = element
    while current is not None:
        if str(current.get("aria-hidden", "")).casefold() == "true":
            return True
        current = current.getparent()
    return False


def nearest_ancestor(element, tag: str):
    current = element
    while current is not None:
        if isinstance(current.tag, str) and current.tag.casefold() == tag:
            return current
        current = current.getparent()
    return None


def text_item(text_id: str, element, texts: dict[str, str], image_ids: set[str]) -> dict:
    source_tag = element.tag.casefold() if isinstance(element.tag, str) else "span"
    if source_tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        tag = source_tag
    elif nearest_ancestor(element, "h1") is not None:
        tag = "h1"
    elif nearest_ancestor(element, "h2") is not None:
        tag = "h2"
    elif nearest_ancestor(element, "h3") is not None:
        tag = "h3"
    else:
        tag = "p"
    kind = "image" if source_tag == "img" or text_id in image_ids else "text"
    return {"kind": kind, "id": text_id, "tag": tag, "text": texts[text_id]}


def table_item(table, page_number: int, texts: dict[str, str], image_ids: set[str]) -> dict | None:
    rows = []
    table_ids = []
    for row in table.xpath(".//tr"):
        cells = []
        for cell in row.xpath("./th|./td"):
            cell_items = []
            for element in cell.xpath(".//*[@data-id] | self::*[@data-id]"):
                text_id = element.get("data-id", "")
                if (
                    page_number_for_id(text_id) == page_number
                    and clean_text_id(text_id)
                    and text_id in texts
                    and str(texts[text_id]).strip()
                ):
                    table_ids.append(text_id)
                    cell_items.append(text_item(text_id, element, texts, image_ids))
            blanks = 0
            for blank in cell.xpath('.//*[@role="img"]'):
                label = blank.get("aria-label", "")
                if "nafasi" in label.casefold() or "jibu" in label.casefold():
                    blanks += 1
            if cell_items or blanks:
                cells.append({"tag": cell.tag.casefold(), "items": cell_items, "blanks": blanks})
            else:
                cells.append({"tag": cell.tag.casefold(), "items": [], "blanks": 0})
        if cells:
            rows.append(cells)
    if not table_ids:
        return None
    return {"kind": "table", "ids": list(dict.fromkeys(table_ids)), "rows": rows}


def build_semantics() -> dict[str, list[dict]]:
    texts = load_json(ROOT / "content/i18n/sw/texts.json")
    audio_catalogs = [load_json(ROOT / f"content/i18n/{lang}/audios.json") for lang in LANGS]
    page_items: dict[int, list[dict]] = defaultdict(list)
    seen_ids: dict[int, set[str]] = defaultdict(set)
    seen_tables: dict[int, set[tuple[str, ...]]] = defaultdict(set)
    image_ids: set[str] = set()

    source_files = [ROOT / "index.html", *sorted(ROOT.glob("pg*.html"))]
    parsed = []
    for path in source_files:
        try:
            document = html.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        parsed.append(document)
        for image in document.xpath("//img[@data-id]"):
            image_ids.add(image.get("data-id"))

    for document in parsed:
        for element in document.xpath("//*[@data-id]"):
            text_id = element.get("data-id", "")
            page_number = page_number_for_id(text_id)
            if (
                page_number is None
                or not clean_text_id(text_id)
                or text_id not in texts
                or not isinstance(texts[text_id], str)
                or not texts[text_id].strip()
                or not all(text_id in catalog for catalog in audio_catalogs)
                or has_hidden_ancestor(element)
            ):
                continue
            table = nearest_ancestor(element, "table")
            if table is not None:
                candidate = table_item(table, page_number, texts, image_ids)
                if candidate is None:
                    continue
                signature = tuple(candidate["ids"])
                if signature not in seen_tables[page_number]:
                    page_items[page_number].append(candidate)
                    seen_tables[page_number].add(signature)
                    seen_ids[page_number].update(candidate["ids"])
                continue
            if text_id in seen_ids[page_number]:
                continue
            page_items[page_number].append(text_item(text_id, element, texts, image_ids))
            seen_ids[page_number].add(text_id)

    missing = [number for number in range(1, 133) if not page_items[number]]
    if missing:
        raise RuntimeError(f"No accessible semantic content found for PDF pages: {missing}")
    return {f"{number:03d}": page_items[number] for number in range(1, 133)}


def git_source_metadata() -> tuple[dict[int, list[str]], dict[int, set[str]]]:
    """Recover input labels and original image IDs from the pre-conversion HTML."""
    blank_labels: dict[int, list[str]] = defaultdict(list)
    image_ids: dict[int, set[str]] = defaultdict(set)
    try:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return blank_labels, image_ids

    for relative_path in listing:
        match = re.fullmatch(r"pg(\d{3})_sec\d{3}\.html", relative_path)
        if not match:
            continue
        page_number = int(match.group(1))
        try:
            source = subprocess.run(
                ["git", "show", f"HEAD:{relative_path}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            document = html.fromstring(source)
        except (OSError, subprocess.CalledProcessError, ValueError):
            continue

        for image in document.xpath("//img[@data-id]"):
            image_ids[page_number].add(image.get("data-id"))
        controls = document.xpath(
            '//input[not(@type) or @type="text" or @type="number"] | //textarea'
        )
        for control_number, control in enumerate(controls, 1):
            label = str(control.get("aria-label", "")).strip()
            if not label:
                label = f"Nafasi ya kuandika jibu {control_number}"
            blank_labels[page_number].append(label)
    return blank_labels, image_ids


def nested_item_ids(item: dict) -> set[str]:
    if item.get("kind") == "table":
        return {
            child["id"]
            for row in item.get("rows", [])
            for cell in row
            for child in cell.get("items", [])
            if child.get("id")
        }
    return {item["id"]} if item.get("id") else set()


def grid_table_item(prefix: str, grid_items: list[dict], labels: list[str]) -> tuple[dict, list[str]]:
    """Turn data-ID-backed number grids into semantic table rows and cells."""
    explicit_cells: dict[tuple[int, int], dict] = {}
    column_cells: dict[int, dict] = {}
    sequential_items: list[dict] = []
    for item in grid_items:
        suffix = item["id"][len(prefix) + 1 :]
        row_column = re.fullmatch(r"r0*(\d+)c0*(\d+)", suffix)
        column = re.fullmatch(r"c0*(\d+)", suffix)
        if row_column:
            explicit_cells[(int(row_column.group(1)), int(row_column.group(2)))] = item
        elif column:
            column_cells[int(column.group(1))] = item
        else:
            sequential_items.append(item)

    used_labels: list[str] = []
    rows: list[list[dict]] = []
    if explicit_cells:
        row_count = max(row for row, _ in explicit_cells)
        column_count = max(column for _, column in explicit_cells)
        for row in range(1, row_count + 1):
            rows.append(
                [
                    {
                        "tag": "td",
                        "items": [explicit_cells[(row, column)]]
                        if (row, column) in explicit_cells
                        else [],
                        "blanks": 0,
                        "blank_labels": [],
                    }
                    for column in range(1, column_count + 1)
                ]
            )
    elif column_cells:
        rows.append(
            [
                {
                    "tag": "td",
                    "items": [column_cells[column]],
                    "blanks": 0,
                    "blank_labels": [],
                }
                for column in sorted(column_cells)
            ]
        )
    else:
        positioned_blanks: dict[tuple[int, int], str] = {}
        for label in labels:
            match = GRID_ROW_COLUMN.search(label)
            if match:
                positioned_blanks[(int(match.group(1)), int(match.group(2)))] = label
        if positioned_blanks:
            row_count = max(row for row, _ in positioned_blanks)
            column_count = max(column for _, column in positioned_blanks)
            known = iter(sequential_items)
            for row in range(1, row_count + 1):
                cells = []
                for column in range(1, column_count + 1):
                    label = positioned_blanks.get((row, column))
                    if label:
                        used_labels.append(label)
                        cells.append(
                            {
                                "tag": "td",
                                "items": [],
                                "blanks": 0,
                                "blank_labels": [label],
                            }
                        )
                    else:
                        item = next(known, None)
                        cells.append(
                            {
                                "tag": "td",
                                "items": [item] if item else [],
                                "blanks": 0,
                                "blank_labels": [],
                            }
                        )
                rows.append(cells)
        else:
            column_count = 10 if len(sequential_items) > 10 else len(sequential_items)
            for start in range(0, len(sequential_items), column_count):
                rows.append(
                    [
                        {
                            "tag": "td",
                            "items": [item],
                            "blanks": 0,
                            "blank_labels": [],
                        }
                        for item in sequential_items[start : start + column_count]
                    ]
                )
    return {
        "kind": "table",
        "ids": [item["id"] for item in grid_items],
        "rows": rows,
        "caption": "Gridi ya namba inayosomeka kwa mpangilio wa safu na mistari",
    }, used_labels


def clean_semantic_items(items: list[dict]) -> list[dict]:
    """Keep each spoken ID and each image description once, preferring table structure."""
    table_ids: set[str] = set()
    table_image_descriptions: set[str] = set()
    for item in items:
        if item.get("kind") != "table":
            continue
        for row in item.get("rows", []):
            for cell in row:
                cleaned_children = []
                had_placeholder = False
                for child in cell.get("items", []):
                    text_id = child.get("id")
                    description = " ".join(str(child.get("text", "")).casefold().split())
                    if child.get("kind") == "text" and re.fullmatch(r"_+", str(child.get("text", "")).strip()):
                        had_placeholder = True
                        continue
                    if text_id and text_id in table_ids:
                        continue
                    if child.get("kind") == "image" and description in table_image_descriptions:
                        continue
                    cleaned_children.append(child)
                    if text_id:
                        table_ids.add(text_id)
                    if child.get("kind") == "image":
                        table_image_descriptions.add(description)
                cell["items"] = cleaned_children
                if had_placeholder and not cell.get("blanks", 0) and not cell.get("blank_labels", []):
                    cell["blank_labels"] = ["Nafasi ya kuandika jibu"]
                if (
                    not cleaned_children
                    and not cell.get("blanks", 0)
                    and not cell.get("blank_labels", [])
                ):
                    cell["blank_labels"] = ["Kisanduku tupu katika jedwali"]

    cleaned_items = []
    seen_ids = set(table_ids)
    seen_image_descriptions = set(table_image_descriptions)
    for item in items:
        if item.get("kind") == "table":
            cleaned_items.append(item)
            continue
        text_id = item.get("id")
        description = " ".join(str(item.get("text", "")).casefold().split())
        if text_id and text_id in seen_ids:
            continue
        if item.get("kind") == "image" and description in seen_image_descriptions:
            continue
        cleaned_items.append(item)
        if text_id:
            seen_ids.add(text_id)
        if item.get("kind") == "image":
            seen_image_descriptions.add(description)
    return cleaned_items


def page_specific_reading_order(page_number: int, items: list[dict]) -> list[dict]:
    """Correct layouts whose visual columns do not match their spoken sequence."""
    if page_number != 131:
        return items

    by_id = {
        item["id"]: item
        for item in items
        if item.get("kind") in {"text", "image"} and item.get("id")
    }
    sequence: list[dict] = []
    used_ids: set[str] = set()

    def add_id(text_id: str) -> None:
        item = by_id.get(text_id)
        if item is not None and text_id not in used_ids:
            sequence.append(item)
            used_ids.add(text_id)

    def add_blank(label: str) -> None:
        sequence.append({"kind": "blank", "label": label})

    add_id("pg131_n0002")

    add_id("pg131_n0004")
    add_id("pg131_n0005")
    for text_id, number in (
        ("pg131_n0006", "36"),
        ("pg131_n0007", "47"),
        ("pg131_n0008", "69"),
    ):
        add_id(text_id)
        add_blank(f"Nafasi ya kuandika jibu la swali la 1 kwa namba {number}")

    for question, number_id, content_ids, answer_count in (
        (2, "pg131_n0010", ("pg131_n0011",), 1),
        (3, "pg131_n0013", ("pg131_n0014",), 1),
        (4, "pg131_n0016", ("pg131_n0017",), 1),
        (5, "pg131_n0019", ("pg131_n0020",), 1),
        (6, "pg131_n0022", ("pg131_n0023", "pg131_n0024"), 1),
        (7, "pg131_n0027", ("pg131_n0028", "pg131_n0029"), 1),
        (8, "pg131_n0032", ("pg131_n0033", "pg131_n0034"), 1),
        (9, "pg131_n0037", ("pg131_n0038", "pg131_n0039"), 1),
    ):
        add_id(number_id)
        for text_id in content_ids:
            add_id(text_id)
        for _ in range(answer_count):
            add_blank(f"Nafasi ya kuandika jibu la swali la {question}")

    add_id("pg131_n0042")
    add_id("pg131_n0043")
    for text_id, words in (
        ("pg131_n0044", "Tisini na tisa"),
        ("pg131_n0045", "Themanini na nane"),
        ("pg131_n0046", "Ishirini na saba"),
    ):
        add_id(text_id)
        add_blank(f"Nafasi ya kuandika jibu la swali la 10 kwa {words}")

    for question, number_id, content_ids in (
        (11, "pg131_n0048", ("pg131_n0049",)),
        (12, "pg131_n0051", ("pg131_n0052",)),
        (13, "pg131_n0054", ("pg131_n0055",)),
        (14, "pg131_n0057", ("pg131_n0058",)),
    ):
        add_id(number_id)
        for text_id in content_ids:
            add_id(text_id)
        add_blank(f"Nafasi ya kuandika jibu la swali la {question}")

    for number_id, content_id in (
        ("pg131_n0077", "pg131_n0078"),
        ("pg131_n0080", "pg131_n0081"),
    ):
        add_id(number_id)
        add_id(content_id)

    for question, number_id, content_ids, answer_count in (
        (17, "pg131_n0060", ("pg131_n0061", "pg131_n0062", "pg131_n0063"), 1),
        (18, "pg131_n0065", ("pg131_n0066", "pg131_n0067"), 1),
        (19, "pg131_n0069", ("pg131_n0070",), 2),
        (20, "pg131_n0072", ("pg131_n0073",), 1),
    ):
        add_id(number_id)
        for text_id in content_ids:
            add_id(text_id)
        for answer_number in range(1, answer_count + 1):
            suffix = f", sehemu ya {answer_number}" if answer_count > 1 else ""
            add_blank(f"Nafasi ya kuandika jibu la swali la {question}{suffix}")

    sequence.extend(
        item
        for item in items
        if item.get("kind") != "blank" and not (item.get("id") and item["id"] in used_ids)
    )
    return sequence


def ensure_semantic_audio(semantics: dict[str, list[dict]]) -> None:
    """Alias existing recordings for any semantic IDs that share the same spoken text."""
    required_ids = set()
    for items in semantics.values():
        for item in items:
            required_ids.update(nested_item_ids(item))

    for language in LANGS:
        base = ROOT / f"content/i18n/{language}"
        texts = load_json(base / "texts.json")
        audios_path = base / "audios.json"
        audios = load_json(audios_path)
        reusable: dict[str, str] = {}
        for text_id, filename in audios.items():
            value = texts.get(text_id)
            if (
                isinstance(value, str)
                and value.strip()
                and filename
                and (base / "audio" / filename).is_file()
            ):
                reusable.setdefault(" ".join(value.casefold().split()), filename)
        changed = False
        for text_id in sorted(required_ids):
            if audios.get(text_id):
                continue
            value = texts.get(text_id)
            filename = reusable.get(" ".join(str(value).casefold().split()))
            if filename:
                audios[text_id] = filename
                changed = True
        if changed:
            audios_path.write_text(
                json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )


def enrich_semantics(semantics: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Preserve every image description, add static blanks, and group number grids."""
    texts = load_json(ROOT / "content/i18n/sw/texts.json")
    audio_catalogs = [load_json(ROOT / f"content/i18n/{lang}/audios.json") for lang in LANGS]
    blank_labels, git_image_ids = git_source_metadata()

    for page_number in range(1, 133):
        page_key = f"{page_number:03d}"
        items = [item for item in semantics[page_key] if item.get("kind") != "blank"]
        labels = list(blank_labels.get(page_number, []))

        deduplicated_items = []
        seen_image_descriptions: set[str] = set()
        for item in items:
            if item.get("kind") == "image":
                normalized = " ".join(str(item.get("text", "")).casefold().split())
                if normalized in seen_image_descriptions:
                    continue
                seen_image_descriptions.add(normalized)
            deduplicated_items.append(item)
        items = deduplicated_items

        grouped: dict[str, list[dict]] = defaultdict(list)
        first_grid_index: dict[str, int] = {}
        for index, item in enumerate(items):
            if item.get("kind") != "text" or not item.get("id"):
                continue
            match = GRID_ID.match(item["id"])
            if match:
                prefix = match.group(1)
                grouped[prefix].append(item)
                first_grid_index.setdefault(prefix, index)

        used_label_counts: dict[str, int] = defaultdict(int)
        if grouped:
            rebuilt = []
            inserted: set[str] = set()
            for index, item in enumerate(items):
                match = GRID_ID.match(str(item.get("id", "")))
                if not match:
                    rebuilt.append(item)
                    continue
                prefix = match.group(1)
                if prefix in inserted:
                    continue
                table, used = grid_table_item(prefix, grouped[prefix], labels)
                rebuilt.append(table)
                inserted.add(prefix)
                for label in used:
                    used_label_counts[label] += 1
            items = rebuilt

        existing_ids = set().union(*(nested_item_ids(item) for item in items))
        likely_image_ids = {
            text_id
            for text_id in texts
            if page_number_for_id(text_id) == page_number and "_im" in text_id
        }
        likely_image_ids.update(git_image_ids.get(page_number, set()))
        for text_id in sorted(likely_image_ids):
            normalized_description = " ".join(str(texts.get(text_id, "")).casefold().split())
            if (
                text_id in existing_ids
                or not clean_text_id(text_id)
                or not isinstance(texts.get(text_id), str)
                or not texts[text_id].strip()
                or normalized_description in seen_image_descriptions
                or not all(text_id in catalog for catalog in audio_catalogs)
            ):
                continue
            items.append({"kind": "image", "id": text_id, "tag": "p", "text": texts[text_id]})
            existing_ids.add(text_id)
            seen_image_descriptions.add(normalized_description)

        spoken_values = {
            " ".join(str(child.get("text", "")).casefold().split())
            for item in items
            for child in (
                [item]
                if item.get("kind") != "table"
                else [
                    nested
                    for row in item.get("rows", [])
                    for cell in row
                    for nested in cell.get("items", [])
                ]
            )
            if child.get("kind") in {"text", "image"} and str(child.get("text", "")).strip()
        }
        for text_id in sorted(texts):
            value = texts.get(text_id)
            normalized_value = " ".join(str(value).casefold().split())
            if (
                page_number_for_id(text_id) != page_number
                or text_id in existing_ids
                or text_id in likely_image_ids
                or "_grid" in text_id
                or not clean_text_id(text_id)
                or not isinstance(value, str)
                or not value.strip()
                or normalized_value in spoken_values
                or not all(text_id in catalog for catalog in audio_catalogs)
            ):
                continue
            items.append({"kind": "text", "id": text_id, "tag": "p", "text": value})
            existing_ids.add(text_id)
            spoken_values.add(normalized_value)

        remaining_labels = []
        for label in labels:
            if used_label_counts[label]:
                used_label_counts[label] -= 1
            else:
                remaining_labels.append(label)

        existing_table_blanks = sum(
            cell.get("blanks", 0) + len(cell.get("blank_labels", []))
            for item in items
            if item.get("kind") == "table"
            for row in item.get("rows", [])
            for cell in row
        )
        if existing_table_blanks:
            remaining_labels = remaining_labels[existing_table_blanks:]

        answer_count = sum(
            1
            for text_id in texts
            if page_number_for_id(text_id) == page_number and "_ans_item-" in text_id
        )
        desired_blank_count = max(len(labels), answer_count)
        represented_blank_count = existing_table_blanks + len(remaining_labels)
        while represented_blank_count < desired_blank_count:
            remaining_labels.append(f"Nafasi ya kuandika jibu {represented_blank_count + 1}")
            represented_blank_count += 1
        items.extend({"kind": "blank", "label": label} for label in remaining_labels)
        semantics[page_key] = page_specific_reading_order(
            page_number, clean_semantic_items(items)
        )
    return semantics


def render_item(item: dict, page_number: int, item_number: int) -> str:
    if item["kind"] == "blank":
        label = html_std.escape(item.get("label", "Nafasi ya kuandika jibu"), quote=True)
        return f'<span class="adt-semantic-answer-blank" role="img" aria-label="{label}"></span>'

    if item["kind"] == "table":
        rows = []
        for row in item["rows"]:
            cells = []
            for cell in row:
                content = []
                for child_number, child in enumerate(cell["items"], 1):
                    content.append(render_item(child, page_number, item_number * 100 + child_number))
                blank_labels = list(cell.get("blank_labels", []))
                blank_labels.extend("Nafasi ya kuandika jibu" for _ in range(cell.get("blanks", 0)))
                for blank_label in blank_labels:
                    blank_label = html_std.escape(blank_label, quote=True)
                    content.append(
                        '<span class="adt-semantic-answer-blank" role="img" '
                        f'aria-label="{blank_label}"></span>'
                    )
                cell_tag = "th" if cell["tag"] == "th" else "td"
                cells.append(f"<{cell_tag}>{''.join(content)}</{cell_tag}>")
            rows.append(f"<tr>{''.join(cells)}</tr>")
        return (
            '<table class="adt-semantic-table">'
            f'<caption>{html_std.escape(item.get("caption", f"Jedwali katika ukurasa wa PDF {page_number}"))}</caption>'
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    text_id = html_std.escape(item["id"], quote=True)
    value = html_std.escape(item["text"])
    if item["kind"] == "image":
        caption_id = f"adt-image-caption-{page_number}-{item_number}"
        return (
            f'<figure class="adt-semantic-image" role="img" aria-labelledby="{caption_id}">'
            f'<figcaption id="{caption_id}" data-id="{text_id}">{value}</figcaption>'
            "</figure>"
        )
    tag = item.get("tag", "p")
    if tag not in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "span"}:
        tag = "p"
    return f'<{tag} data-id="{text_id}">{value}</{tag}>'


def accessible_layer(items: list[dict], page_number: int) -> str:
    rendered = "".join(
        f"<li>{render_item(item, page_number, index)}</li>"
        for index, item in enumerate(items, 1)
    )
    return (
        '<div class="adt-semantic-page">'
        f'<p aria-label="Ukurasa wa PDF {page_number} kati ya 132">'
        f"Ukurasa wa PDF {page_number} kati ya 132.</p>"
        f'<ol class="adt-page-reading-order">{rendered}</ol>'
        "</div>"
    )


def faithful_css() -> str:
    return """/* PDF-faithful page canvas with an independent accessible reading layer. */
html { background: #dbe3e8; }
body.adt-faithful-book-page {
  margin: 0;
  min-height: 100vh;
  background: #dbe3e8;
}
body.adt-faithful-book-page main {
  display: flex;
  width: 100%;
  justify-content: center;
  padding: 1rem 0;
}
body.adt-faithful-book-page #content {
  width: 100%;
  max-width: 860px;
  padding: 0 0.75rem;
  box-sizing: border-box;
}
.adt-page-shell {
  position: relative;
  width: 100%;
  margin: 0 auto;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.2);
}
.adt-page-visual,
.adt-page-visual svg {
  display: block;
  width: 100%;
  height: auto;
  line-height: 0;
}
.adt-semantic-page {
  position: absolute !important;
  left: 0 !important;
  top: 0 !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: 0 !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  clip-path: inset(50%) !important;
  white-space: normal !important;
  border: 0 !important;
}
.adt-semantic-page table { border-collapse: collapse; }
.adt-semantic-page caption { white-space: nowrap; }
.adt-semantic-answer-blank::after { content: "Nafasi ya kuandika jibu"; }
@media (max-width: 640px) {
  body.adt-faithful-book-page main { padding-top: 0.25rem; }
  body.adt-faithful-book-page #content { padding: 0 0.25rem; }
  .adt-page-shell { box-shadow: none; }
}
"""


def page_html(page_number: int, svg: str, items: list[dict]) -> str:
    section_id = f"pg{page_number:03d}_sec001"
    svg = svg.replace(
        "<svg ",
        '<svg class="adt-source-page-svg" aria-hidden="true" focusable="false" '
        'preserveAspectRatio="xMidYMid meet" ',
        1,
    )
    return f"""<!DOCTYPE html>
<html lang="sw">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kuhesabu Kitabu cha Mwanafunzi - Ukurasa {page_number}</title>
  <meta name="title-id" content="{section_id}" />
  <meta name="page-section-id" content="{page_number}" />
  <link href="./content/tailwind_output.css?v=13" rel="stylesheet">
  <link href="./content/page-faithful.css?v=1" rel="stylesheet">
  <link href="./assets/libs/fontawesome/css/all.min.css" rel="stylesheet">
  <link href="./assets/fonts.css" rel="stylesheet">
</head>
<body class="adt-faithful-book-page font-sans">
  <main>
    <div id="content" class="opacity-0">
      <section role="article" data-section-type="page_faithful" data-section-id="{section_id}" class="adt-page-shell">
        <div class="adt-page-visual">{svg}</div>
        {accessible_layer(items, page_number)}
      </section>
    </div>
  </main>
  <div class="relative z-50" id="interface-container"></div>
  <div class="relative z-50" id="nav-container"></div>
  <script src="./assets/offline-preloader.js?v=12"></script>
  <script src="./assets/scorm.js"></script>
  <script src="./assets/enable-image-descriptions.js"></script>
  <script src="./assets/base.bundle.local.js"></script>
</body>
</html>
"""


def poppler_svg(pdftocairo: Path, pdf: Path, page_number: int) -> str:
    """Convert one PDF page to browser-safe SVG while preserving vector layout."""
    with tempfile.TemporaryDirectory(prefix="kuhesabu-svg-") as temp_dir:
        output = Path(temp_dir) / f"page-{page_number:03d}.svg"
        subprocess.run(
            [
                str(pdftocairo),
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-svg",
                str(pdf),
                str(output),
            ],
            check=True,
        )
        svg = output.read_text(encoding="utf-8")
    start = svg.find("<svg")
    if start < 0:
        raise RuntimeError(f"Poppler did not produce SVG for page {page_number}")
    return svg[start:]


def update_manifests() -> None:
    pages = []
    for number in range(1, 133):
        pages.append(
            {
                "section_id": f"pg{number:03d}_sec001",
                "href": "index.html" if number == 1 else f"pg{number:03d}_sec001.html",
                "page_number": number,
            }
        )
    (ROOT / "content/pages.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    toc_path = ROOT / "content/toc.json"
    toc = load_json(toc_path)
    for entry in toc:
        match = re.match(r"pg(\d{3})_", str(entry.get("section_id", "")))
        if not match:
            continue
        number = int(match.group(1))
        entry["href"] = "index.html" if number == 1 else f"pg{number:03d}_sec001.html"
    toc_path.write_text(json.dumps(toc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pdftocairo", type=Path, default=DEFAULT_PDFTOCAIRO)
    parser.add_argument("--pages", default="1-132", help="Page number or inclusive range")
    parser.add_argument("--rebuild-semantics", action="store_true")
    parser.add_argument("--update-manifests", action="store_true")
    args = parser.parse_args()

    semantics_path = ROOT / "content/page-semantics.json"
    if args.rebuild_semantics or not semantics_path.exists():
        semantics = build_semantics()
        semantics_path.write_text(
            json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        semantics = load_json(semantics_path)
    semantics = enrich_semantics(semantics)
    ensure_semantic_audio(semantics)
    semantics_path.write_text(
        json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if "-" in args.pages:
        first, last = (int(value) for value in args.pages.split("-", 1))
    else:
        first = last = int(args.pages)
    if first < 1 or last > 132 or first > last:
        raise ValueError("Pages must be between 1 and 132")

    (ROOT / "content/page-faithful.css").write_text(faithful_css(), encoding="utf-8")
    document = pymupdf.open(args.pdf)
    if len(document) != 132:
        raise RuntimeError(f"Expected 132 PDF pages, found {len(document)}")
    for page_number in range(first, last + 1):
        svg = poppler_svg(args.pdftocairo, args.pdf, page_number)
        output = ROOT / ("index.html" if page_number == 1 else f"pg{page_number:03d}_sec001.html")
        output.write_text(page_html(page_number, svg, semantics[f"{page_number:03d}"]), encoding="utf-8")
        print(f"{page_number:03d}: {output.name} ({len(svg):,} SVG characters)")

    if args.update_manifests:
        if first != 1 or last != 132:
            raise RuntimeError("Manifest update requires building all 132 pages")
        update_manifests()


if __name__ == "__main__":
    main()
