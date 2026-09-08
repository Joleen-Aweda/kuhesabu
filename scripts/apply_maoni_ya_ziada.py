#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")

# Overview descriptions that repeat content already represented item-by-item in
# the semantic reading order. They remain in the locale catalog for source
# history, but are removed from automatic page narration.
REDUNDANT_FIGURES = {
    "pg013_sec001.html": ("pg013_im016",),
    "pg024_sec001.html": ("pg024_im007",),
    "pg060_sec001.html": ("pg060_im006",),
    "pg065_sec001.html": ("pg065_im006_crop1", "pg065_im007_crop_v1_crop2"),
    "pg066_sec001.html": ("pg066_im006",),
    "pg071_sec001.html": ("pg071_im006",),
    "pg099_sec001.html": ("pg099_im006",),
    "pg100_sec001.html": ("pg100_im006",),
}

REDUNDANT_CAPTIONS = {
    "pg013_sec001.html": ("pg013_table001_desc",),
    "pg019_sec001.html": ("pg019_table001_desc",),
    "pg022_sec001.html": ("pg022_table001_desc",),
    "pg023_sec001.html": ("pg023_table001_desc",),
    "pg024_sec001.html": ("pg024_table001_desc",),
    "pg025_sec001.html": ("pg025_table001_desc",),
    "pg127_sec001.html": ("pg127_table001_desc",),
}

REDUNDANT_REVIEW_IDS = {
    "pg101_sec001.html": (
        "pg101_q19_review_v1",
        "pg101_q20_review_v1",
        "pg101_q21_review_v1",
    ),
    "pg114_sec001.html": tuple(
        f"pg114_prev_q{number:02d}_review_v1" for number in range(9, 15)
    ),
}

PAGE22_BLANK_IDS = tuple(
    f"pg022_sec001_answer_blank_{number:03d}" for number in range(1, 11)
)

TEXT_UPDATES = {
    "pg027_n0004_easy_read":
        "Andika idadi ya vitu katika boksi, kiberiti, sahani na trei.",
    "pg045_ex_im001": (
        "Vipanya vinne vya KASA ya kompyuta vya rangi ya zambarau, punguza, "
        "vipanya vitatu vya KASA ya kompyuta vya rangi ya zambarau, baki, "
        "kipanya kimoja cha KASA ya kompyuta cha rangi ya zambarau."
    ),
}


def remove_list_item(text: str, text_id: str) -> str:
    if f'data-id="{text_id}"' not in text:
        return text
    pattern = re.compile(
        rf"<li>(?:(?!</li>).)*data-id=\"{re.escape(text_id)}\"(?:(?!</li>).)*</li>",
        re.DOTALL,
    )
    text, count = pattern.subn("", text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected one semantic list item for {text_id}, found {count}")
    return text


def write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8")
    if old == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


changed_files: list[str] = []

for filename, ids in REDUNDANT_FIGURES.items():
    path = ROOT / filename
    text = path.read_text(encoding="utf-8")
    for text_id in ids:
        text = remove_list_item(text, text_id)
    if write_if_changed(path, text):
        changed_files.append(filename)

for filename, ids in REDUNDANT_REVIEW_IDS.items():
    path = ROOT / filename
    text = path.read_text(encoding="utf-8")
    for text_id in ids:
        text = remove_list_item(text, text_id)
    if write_if_changed(path, text):
        changed_files.append(filename)

for filename, ids in REDUNDANT_CAPTIONS.items():
    path = ROOT / filename
    text = path.read_text(encoding="utf-8")
    for text_id in ids:
        text, count = re.subn(
            rf"(<caption) data-id=\"{re.escape(text_id)}\"",
            r"\1",
            text,
            count=1,
        )
        if count not in (0, 1):
            raise RuntimeError(f"Expected one caption for {text_id}, found {count}")
    if write_if_changed(path, text):
        changed_files.append(filename)

# Page 13: go directly from the exercise title to the fruit quantity, digit,
# and number word in each row.
page13 = ROOT / "pg013_sec001.html"
text = page13.read_text(encoding="utf-8")
text = remove_list_item(text, "pg013_n0003")
if write_if_changed(page13, text):
    changed_files.append(page13.name)

# Page 22: say "Dashi" for the visibly empty number positions.
page22 = ROOT / "pg022_sec001.html"
text = page22.read_text(encoding="utf-8")
for text_id in PAGE22_BLANK_IDS:
    pattern = re.compile(
        rf'(<span[^>]*data-id="{re.escape(text_id)}"[^>]*>)(.*?)(</span>)',
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"Missing page 22 answer blank {text_id}")
    opening = re.sub(r'aria-label="[^"]*"', 'aria-label="Dashi"', match.group(1))
    text = text[:match.start()] + opening + "Dashi." + match.group(3) + text[match.end():]
if write_if_changed(page22, text):
    changed_files.append(page22.name)

# Page 45: terminology requested by the reviewer; semantic narration only.
page45 = ROOT / "pg045_sec001.html"
text = page45.read_text(encoding="utf-8")
old = re.search(r'(<figcaption[^>]*data-id="pg045_ex_im001"[^>]*>)(.*?)(</figcaption>)', text, re.DOTALL)
if not old:
    raise RuntimeError("Missing pg045_ex_im001")
replacement = old.group(1) + html.escape(TEXT_UPDATES["pg045_ex_im001"]) + old.group(3)
text = text[:old.start()] + replacement + text[old.end():]
if write_if_changed(page45, text):
    changed_files.append(page45.name)

# Keep both locale catalogs synchronized with the corrected narration.
for lang in LANGS:
    path = ROOT / "content" / "i18n" / lang / "texts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for text_id in PAGE22_BLANK_IDS:
        data[text_id] = "Dashi."
    for text_id, value in TEXT_UPDATES.items():
        data[text_id] = value
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if write_if_changed(path, rendered):
        changed_files.append(str(path.relative_to(ROOT)))

    audios_path = ROOT / "content" / "i18n" / lang / "audios.json"
    audios = json.loads(audios_path.read_text(encoding="utf-8"))
    # The corrected Easy Read instruction is now identical to the standard
    # sentence, so reuse its existing Daudi recording without an external call.
    audios["pg027_n0004_easy_read"] = audios["pg027_n0004"]
    rendered = json.dumps(audios, ensure_ascii=False, indent=2) + "\n"
    if write_if_changed(audios_path, rendered):
        changed_files.append(str(audios_path.relative_to(ROOT)))

# Synchronize the source semantic manifest for the changed image description.
semantics_path = ROOT / "content" / "page-semantics.json"
semantics = json.loads(semantics_path.read_text(encoding="utf-8"))

def update_semantic(node: object) -> None:
    if isinstance(node, dict):
        text_id = node.get("id")
        if text_id == "pg045_ex_im001":
            for key in ("text", "alt", "description", "value"):
                if key in node and isinstance(node[key], str):
                    node[key] = TEXT_UPDATES[text_id]
        for value in node.values():
            update_semantic(value)
    elif isinstance(node, list):
        for value in node:
            update_semantic(value)

update_semantic(semantics)
rendered = json.dumps(semantics, ensure_ascii=False, indent=2) + "\n"
if write_if_changed(semantics_path, rendered):
    changed_files.append(str(semantics_path.relative_to(ROOT)))

print("Changed files:")
for filename in sorted(set(changed_files)):
    print(filename)
print("Audio IDs:")
for text_id in (*PAGE22_BLANK_IDS, *TEXT_UPDATES):
    print(text_id)
