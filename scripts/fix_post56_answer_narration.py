#!/usr/bin/env python3
"""Place answer dashes inside their questions on PDF pages 56 through 132.

The page artwork is intentionally untouched.  This script updates the
localized accessible text and its inline HTML fallback, then removes only the
standalone semantic dash nodes that had been collected at the end of a page.
Blanks already nested in accessible grids/tables are preserved.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("sw", "sw-TZ")

OL_RE = re.compile(
    r'(<ol\s+class="adt-page-reading-order"[^>]*>)(.*?)(</ol>)', re.DOTALL
)
LI_RE = re.compile(r"<li\b.*?</li>", re.DOTALL)
DATA_ID_RE = re.compile(r'data-id="([^"]+)"')
DIRECT_BLANK_LI_RE = re.compile(
    r'<li>\s*<span\b(?=[^>]*\bclass="[^"]*\badt-semantic-answer-blank\b[^"]*")'
    r'[^>]*>.*?</span>\s*</li>',
    re.DOTALL,
)

TEXTS: dict[str, str] = json.loads(
    (ROOT / "content/i18n/sw-TZ/texts.json").read_text(encoding="utf-8")
)
CHANGED_IDS: set[str] = set()


def set_text(text_id: str, value: str) -> None:
    value = re.sub(r"\s+", " ", value).strip()
    if TEXTS.get(text_id) != value:
        TEXTS[text_id] = value
        CHANGED_IDS.add(text_id)


def append_result_dash(text_id: str) -> None:
    value = TEXTS[text_id].strip()
    if re.search(r"\bdashi[.!]?$", value, re.IGNORECASE):
        return
    if value.endswith("="):
        set_text(text_id, f"{value} dashi")
    elif re.search(r"[+−–-]", value):
        set_text(text_id, f"{value} = dashi")
    else:
        set_text(text_id, f"{value}. Jibu ni dashi.")


def append_answer_sentence(text_id: str) -> None:
    value = TEXTS[text_id].strip()
    if "dashi" not in value.lower():
        set_text(text_id, f"{value} Jibu ni dashi.")


def ids(page: int, numbers: list[int], suffix: str = "") -> list[str]:
    return [f"pg{page:03d}_n{number:04d}{suffix}" for number in numbers]


# Arithmetic answer boxes whose missing value is the result.
RESULT_IDS: dict[int, list[str]] = {
    56: ids(56, [15, 20, 25, 30, 35, 40, 17, 22, 27, 32, 37, 42]),
    57: ids(57, [16, 29, 42, 20, 33, 46, 24, 37, 50]),
    58: ids(58, [7, 9, 11, 13, 15, 17, 19, 21, 23, 25]),
    60: ids(60, list(range(5, 62, 4))),
    87: ids(87, list(range(8, 36, 3))),
    90: ids(90, list(range(8, 54, 3))),
    91: ids(91, list(range(8, 49, 5)) + list(range(10, 51, 5))),
    93: ids(93, [10, 23, 36, 49, 14, 27, 40, 53, 18, 31, 44, 57]),
    94: ids(94, [9, 19, 29, 39, 49, 12, 22, 32, 42, 52, 15, 25, 35, 45, 55]),
    95: ids(95, [4, 7, 10, 13, 16, 19, 22, 25, 28]),
    96: ids(96, list(range(10, 68, 3))),
    97: ids(97, list(range(8, 74, 5)) + list(range(10, 76, 5))),
    99: ids(99, [9, 22, 35, 48, 61, 74, 13, 26, 39, 52, 65, 78, 17, 30, 43, 56, 69, 82]),
    100: ids(100, [11, 30, 49, 68, 87, 106, 17, 36, 55, 74, 93, 112, 23, 42, 61, 80, 99, 118, 123, 128, 132]),
    107: [f"pg107_n{number:04d}_eq" for number in range(6, 26)] + ids(107, list(range(31, 37))),
    108: ids(108, list(range(5, 36, 5)) + list(range(7, 38, 5))),
    109: ids(109, [34, 47, 60, 38, 51, 64, 42, 55, 68]),
    110: ids(110, [6, 10, 14, 23, 36, 49, 62, 27, 40, 53, 66, 31, 44, 57, 70]),
    111: ids(111, [7, 20, 11, 24, 15, 28]),
    113: ids(113, [33, 42, 51, 60, 37, 46, 55, 64, 67, 69, 71, 73, 75, 77]),
    114: [f"pg114_n{number:04d}_eq" for number in range(5, 23)],
    116: ids(116, [14, 24, 34, 44, 17, 27, 37, 47, 20, 30, 40, 50]),
    117: ids(117, [6, 16, 9, 19, 12, 22, 29, 39, 49, 32, 42, 52, 35, 45, 55]),
    122: ids(122, [38, 47, 56, 65, 74, 42, 51, 60, 69, 78]),
    123: ids(123, list(range(5, 57, 3)) + list(range(64, 80, 3))),
    124: ids(124, list(range(2, 8)) + list(range(12, 24))),
}


for page_ids in RESULT_IDS.values():
    for text_id in page_ids:
        append_result_dash(text_id)


# Pages where the answer belongs to a prose, sequence, image, money, or
# place-value prompt rather than to a conventional equation.
number_words = [
    "kwanza", "pili", "tatu", "nne", "tano", "sita", "saba", "nane",
    "tisa", "kumi", "kumi na moja", "kumi na mbili", "kumi na tatu",
    "kumi na nne", "kumi na tano", "kumi na sita", "kumi na saba",
    "kumi na nane", "kumi na tisa", "ishirini",
]
page67_values = [52, 33, 74, 48, 19, 91, 54, 61, 39, 14, 28, 77, 88, 57, 11, 81, 90, 27, 50, 22]
set_text(
    "pg067_im020_crop_v1_crop1",
    "Jedwali la zoezi la kuandika namba kwa maneno. "
    + " ".join(
        f"Swali la {number_words[index]}, namba {value}, dashi."
        for index, value in enumerate(page67_values)
    ),
)

for text_id in ids(68, [7, 10, 13, 16, 19, 22, 25, 28, 31, 34]):
    base_value = TEXTS[text_id].split(",", 1)[0].strip()
    set_text(text_id, f"{base_value}, dashi.")

for text_id in ids(71, [8, 11, 14, 17, 25, 28, 31, 34]):
    append_answer_sentence(text_id)

for index, text_id in enumerate(ids(83, [9, 18, 27, 36, 45, 13, 22, 31, 40, 49])):
    count = 2 if index < 7 else 1
    base_value = TEXTS[text_id].split(",", 1)[0].strip()
    set_text(text_id, f"{base_value}, " + ", ".join(["dashi"] * count) + ".")

for text_id in ids(101, [22, 24]) + ids(102, [5, 8, 11, 14, 17, 20]):
    value = TEXTS[text_id].strip()
    base_value = re.split(r"\s+dashi\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    base_value = re.sub(r"\s*\.\s*$", "", base_value)
    set_text(text_id, f"{base_value} dashi.")

for text_id in ids(103, [8, 13, 18, 23, 28, 33]):
    set_text(text_id, "Jumla ni shilingi dashi.")

for text_id in ids(104, [22, 29, 36]) + ids(105, [5, 9, 13, 18, 23]):
    append_answer_sentence(text_id)

for text_id in ids(120, [7, 11, 15, 19, 23, 27]):
    set_text(text_id, "Jumla ni shilingi dashi.")

for text_id in ids(121, [17, 22, 27]) + ids(122, [7, 12, 17, 22, 27]):
    append_answer_sentence(text_id)

for text_id in [
    "pg126_im008_seg001_v1_crop1", "pg126_im008_seg003_v1_crop1",
    "pg126_im008_seg005_v1_crop1", "pg126_im008_seg007_v1_crop1",
    "pg126_im008_seg002_v1_crop1", "pg126_im008_seg004_v1_crop1",
    "pg126_im008_seg006_v1_crop1", "pg126_im008_seg008_v1_crop1",
    "pg127_im006_seg001_v1_crop1", "pg127_im006_seg003_v1_crop1",
    "pg127_im006_seg002_v1_crop_v1_crop1", "pg127_im006_seg004_v1_crop1",
]:
    append_answer_sentence(text_id)

# The custom narration on these pages already says the question ordinal; only
# replace the generic answer-area wording with the spoken dash itself.
for text_id in ids(118, [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]):
    value = re.sub(
        r",?\s*kisha andika jibu katika nafasi iliyo wazi\.?$",
        ", jibu ni dashi.",
        TEXTS[text_id].strip(),
        flags=re.IGNORECASE,
    )
    set_text(text_id, value)

for text_id in ids(119, [8, 11, 14, 17, 20, 23, 26, 29]):
    value = re.sub(
        r"Nafasi ya kuandika jibu\.?$",
        "Jibu ni dashi.",
        TEXTS[text_id].strip(),
        flags=re.IGNORECASE,
    )
    set_text(text_id, value)


# Review page 130: two word answers, three missing sequence values, ordinary
# results, two preceding-number blanks, and one missing operand.
CUSTOM_TEXT = {
    "pg130_n0007": "5, dashi.",
    "pg130_n0008": "16, dashi.",
    "pg130_n0012": "1, 2, 3, dashi, 5, 6.",
    "pg130_n0013": "10, 20, 30, 40, dashi, dashi, 70.",
    "pg130_n0016": "5 + 3 = dashi",
    "pg130_n0019": "8 + 2 = dashi",
    "pg130_n0022": "3 + 6 + 0 = dashi",
    "pg130_n0026": "+ 3 = dashi",
    "pg130_n0031": "+ 18 = dashi",
    "pg130_n0035": "13 - 7 = dashi",
    "pg130_n0038": "9 - 5 = dashi",
    "pg130_n0042": "- 6 = dashi",
    "pg130_n0047": "- 41 = dashi",
    "pg130_n0051": "83 + 9 = dashi",
    "pg130_n0054": "6 + 18 = dashi",
    "pg130_n0058": "- 3 = dashi",
    "pg130_n0063": "+ 24 = dashi",
    "pg130_n0067": "30 - 25 = dashi",
    "pg130_n0071": "+ 12 = dashi",
    "pg130_n0076": "+ 38 = dashi",
    "pg130_n0081": "dashi, 14",
    "pg130_n0082": "dashi, 7",
    "pg130_n0085": "8 + dashi = 12",
    # Review page 131.
    "pg131_n0006": "36, dashi.",
    "pg131_n0007": "47, dashi.",
    "pg131_n0008": "69, dashi.",
    "pg131_n0011": "82 + 0 = dashi",
    "pg131_n0014": "31 + 4 = dashi",
    "pg131_n0017": "48 - 18 = dashi",
    "pg131_n0020": "87 - 49 = dashi",
    "pg131_n0024": "+ 12 = dashi",
    "pg131_n0029": "- 29 = dashi",
    "pg131_n0034": "+ 16 = dashi",
    "pg131_n0039": "- 11 = dashi",
    "pg131_n0044": "Tisini na tisa, dashi.",
    "pg131_n0045": "Themanini na nane, dashi.",
    "pg131_n0046": "Ishirini na saba, dashi.",
    "pg131_n0049": "dashi + 5 = 8",
    "pg131_n0052": "9 - dashi = 2",
    "pg131_n0055": "dashi - 8 = 7",
    "pg131_n0058": "Umbo hili linaitwaje? Dashi.",
    "pg131_n0063": "Jumla ya umri wao ni miaka mingapi? Dashi.",
    "pg131_n0067": "Iwapo mayai 8 yatavunjika, yatabaki mayai mangapi? Dashi.",
    "pg131_n0070": "36 = makumi dashi, mamoja dashi.",
    "pg131_n0073": "Makumi 7, mamoja 4 = dashi",
    # Review page 132.
    "pg132_n0006": "3, 4, 5, dashi, 7, dashi, 9",
    "pg132_n0039": "35 - 31 = dashi",
    "pg132_n0042": "72 + 19 = dashi",
    "pg132_n0045": "26 - 6 = dashi",
    "pg132_n0048": "48 - 21 = dashi",
    "pg132_n0053": "+ 25 = dashi",
    "pg132_n0059": "+ 9 = dashi",
    "pg132_n0064": "makumi dashi",
    "pg132_n0065": "mamoja dashi",
    "pg132_n0067": "= dashi",
    "pg132_n0072": "- 46 = dashi",
    "pg132_n0078": "+ 25 = dashi",
    "pg132_n0082": "Makumi 7, mamoja 3 = dashi",
    "pg132_n0085": "Makumi 8, mamoja 0 = dashi",
    "pg132_n0088": "Makumi 0, mamoja 5 = dashi",
    "pg132_im008_crop_v1_crop1": (
        "Mchoro unaonesha umbo bapa la rangi ya njano, "
        "lenye pande tatu na pembe tatu. Dashi."
    ),
    "pg132_n0094": "Sakafu ya darasa ina umbo gani? Dashi.",
    "pg132_n0100": "Walibaki kuku wangapi? Dashi.",
    "pg132_n0106": "Jumla ana machungwa mangapi? Dashi.",
    "pg132_n0109": (
        "Andika thamani ya nafasi ya tarakimu za namba 48. "
        "Thamani ya tarakimu 4 ni dashi, na thamani ya tarakimu 8 ni dashi."
    ),
}
for text_id, value in CUSTOM_TEXT.items():
    set_text(text_id, value)


REMOVE_DIRECT_BLANK_PAGES = {
    56, 57, 58, 59, 60, 67, 68, 71, 83, 85, 87, 90, 91, 93, 94, 95,
    96, 97, 99, 100, 101, 102, 103, 104, 105, 107, 108, 109, 110, 111,
    113, 114, 116, 117, 118, 119, 120, 121, 122, 123, 124, 126, 127,
    128, 129, 130, 131, 132,
}


PAGE_ORDERS = {
    103: ids(103, [2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18,
                         20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33,
                         35, 37, 38, 40, 42, 43]),
    118: ids(118, [3, 12, 21, 30, 6, 15, 24, 33, 9, 18, 27, 36,
                         39, 41, 43, 45, 47, 48]),
    124: ids(124, [2, 5, 3, 6, 4, 7, 10, 11, 12, 13, 14, 15, 16, 17,
                         18, 19, 20, 21, 22, 23]),
}


def replace_inline_text(source: str, text_id: str, value: str) -> str:
    pattern = re.compile(
        rf'(<(?P<tag>p|span|figcaption)\b(?=[^>]*\bdata-id="{re.escape(text_id)}")[^>]*>)'
        rf'.*?(</(?P=tag)>)',
        re.DOTALL,
    )
    return pattern.sub(lambda match: match.group(1) + html.escape(value) + match.group(3), source)


def reorder_page(source: str, desired_ids: list[str]) -> str:
    match = OL_RE.search(source)
    if not match:
        return source
    opening, body, closing = match.groups()
    items = LI_RE.findall(body)
    by_id: dict[str, str] = {}
    for item in items:
        found = DATA_ID_RE.findall(item)
        if found:
            by_id.setdefault(found[0], item)

    ordered: list[str] = []
    used: set[str] = set()
    for text_id in desired_ids:
        item = by_id.get(text_id)
        if item is None:
            item = f'<li><p data-id="{text_id}">{html.escape(TEXTS[text_id])}</p></li>'
        ordered.append(item)
        used.add(text_id)
    for item in items:
        found = DATA_ID_RE.findall(item)
        if not found or found[0] not in used:
            ordered.append(item)
    replacement = opening + "".join(ordered) + closing
    return source[: match.start()] + replacement + source[match.end() :]


removed_by_page: dict[int, int] = {}
page69_duplicate_blanks_removed = 0
for page in range(56, 133):
    path = ROOT / f"pg{page:03d}_sec001.html"
    if not path.exists():
        continue
    source = path.read_text(encoding="utf-8")
    for text_id in sorted(CHANGED_IDS):
        if text_id.startswith(f"pg{page:03d}_"):
            source = replace_inline_text(source, text_id, TEXTS[text_id])
    if page in REMOVE_DIRECT_BLANK_PAGES:
        source, count = DIRECT_BLANK_LI_RE.subn("", source)
        removed_by_page[page] = count
    if page == 69:
        # The source table has one answer column.  The earlier semantic-table
        # conversion mistakenly inserted another blank inside the words
        # column, causing every row to announce "dashi" twice.
        for blank_number in range(1, 32, 2):
            source, count = re.subn(
                rf'<span\b(?=[^>]*\bdata-id="pg069_sec001_answer_blank_{blank_number:03d}")[^>]*>.*?</span>',
                "",
                source,
                count=1,
                flags=re.DOTALL,
            )
            page69_duplicate_blanks_removed += count
    if page == 132:
        # The empty top-left header cell is structural, not an answer blank.
        source = re.sub(
            r'<span\b(?=[^>]*\bdata-id="pg132_sec001_answer_blank_001")[^>]*>.*?</span>',
            "",
            source,
            count=1,
            flags=re.DOTALL,
        )
    if page in PAGE_ORDERS:
        source = reorder_page(source, PAGE_ORDERS[page])
    path.write_text(source, encoding="utf-8")


for locale in LOCALES:
    path = ROOT / "content/i18n" / locale / "texts.json"
    localized = json.loads(path.read_text(encoding="utf-8"))
    for text_id in CHANGED_IDS:
        localized[text_id] = TEXTS[text_id]
        easy_id = f"{text_id}_easy_read"
        if easy_id in localized:
            localized[easy_id] = TEXTS[text_id]
    path.write_text(json.dumps(localized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


semantics_path = ROOT / "content/page-semantics.json"
semantics = json.loads(semantics_path.read_text(encoding="utf-8"))
page69_blocks = semantics.get("069", [])
page69_table = next((block for block in page69_blocks if block.get("kind") == "table"), None)
if page69_table:
    for row in page69_table.get("rows", []):
        if len(row) < 3:
            continue
        row[1]["blanks"] = 0
        row[1].pop("blank_labels", None)
        row[2]["blanks"] = 1
        row[2]["blank_labels"] = ["Dashi"]
for page in REMOVE_DIRECT_BLANK_PAGES:
    key = f"{page:03d}"
    if key not in semantics:
        continue
    blocks = [block for block in semantics[key] if block.get("kind") != "blank"]
    for block in blocks:
        text_id = block.get("id")
        if text_id in CHANGED_IDS:
            if "text" in block:
                block["text"] = TEXTS[text_id]
            elif "label" in block:
                block["label"] = TEXTS[text_id]
    if page in PAGE_ORDERS:
        by_id = {block.get("id"): block for block in blocks if block.get("id")}
        ordered = []
        used = set()
        for text_id in PAGE_ORDERS[page]:
            block = by_id.get(text_id, {"kind": "text", "id": text_id, "tag": "p", "text": TEXTS[text_id]})
            ordered.append(block)
            used.add(text_id)
        ordered.extend(block for block in blocks if block.get("id") not in used)
        blocks = ordered
    semantics[key] = blocks
semantics_path.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


print(f"Updated accessible text IDs: {len(CHANGED_IDS)}")
print(f"Removed detached direct blank nodes: {sum(removed_by_page.values())}")
print(f"Removed page 69 duplicate table blanks: {page69_duplicate_blanks_removed}")
for page, count in sorted(removed_by_page.items()):
    if count:
        print(f"  page {page}: {count}")
