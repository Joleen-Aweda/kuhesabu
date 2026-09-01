#!/usr/bin/env python3
"""Apply the September 2026 ADT validation-report corrections.

The visual textbook remains unchanged except for the corrected commissioner name
and the requested removal of the word ``gusa``.  The remaining changes improve
the semantic/read-aloud layer and its localized manifests.
"""

from __future__ import annotations

import json
import html
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")

GUSA_PAGES = tuple(range(1, 133))
GUSA_EASY_READ_IDS = (
    "pg008_n0003_easy_read",
    "pg008_n0011_easy_read",
    "pg010_n0009_easy_read",
    "pg011_n0006_easy_read",
    "pg012_n0003_easy_read",
)
DASH_PAGES = (15, 19, 20, 21, 22, 23, 27, 33, 34, 35, 36, 37, 38, 41, 127)

TABLE_DESCRIPTIONS = {
    13: (
        "pg013_table001_desc",
        "Jedwali la Zoezi la 4 lina safu za matunda, tarakimu na namba kwa maneno. "
        "Kila mstari unaonesha tunda na idadi yake kuanzia moja hadi tisa.",
    ),
    15: (
        "pg015_table001_desc",
        "Jedwali la Zoezi la 6 lina safu mbili: Matunda na Idadi. Mistari ina tufaha "
        "tatu, matikiti maji manne, parachichi sita, mapapai saba na mananasi nane, "
        "pamoja na nafasi za kuandika idadi.",
    ),
    19: (
        "pg019_table001_desc",
        "Jedwali la Zoezi la 1 lina namba moja hadi tisa na mistari ya nukta ya "
        "kuunganisha ili kuandika kila namba mara tatu.",
    ),
    22: (
        "pg022_table001_desc",
        "Jedwali la Zoezi la 5 lina mistari ya namba zilizopangwa kwa ulalo na nafasi "
        "za kuandika namba zinazokosekana.",
    ),
    23: (
        "pg023_table001_desc",
        "Jedwali la Zoezi la 6 lina tarakimu tatu, sita, moja, nne, saba, nane, tano, "
        "tisa na mbili, kila moja ikiwa na nafasi ya kuandika namba kwa maneno.",
    ),
    24: (
        "pg024_table001_desc",
        "Jedwali la Zoezi la 7 lina safu za aina za matunda na idadi zake. Kila mstari "
        "una picha ya tunda na nafasi ya kuandika idadi.",
    ),
    25: (
        "pg025_table001_desc",
        "Jedwali la Zoezi la 1 lina namba zilizopangwa katika mistari minne ili "
        "zisomwe kwa sauti au kwa lugha ya alama.",
    ),
    127: (
        "pg127_table001_desc",
        "Jedwali la Zoezi la 3 lina majina ya maumbo saba: duara, mraba, mstatili, "
        "pembetatu, nyota, mviringo na tiara, pamoja na nafasi ya kuchora kila umbo.",
    ),
}

END_ID = "adt_end_of_page"
END_TEXT = "Mwisho wa ukurasa."
BLANK_TEXT = "Nafasi ya kuandika jibu."
BLANK_LABEL = "Nafasi ya kuandika jibu"
PAGE24_BLANK_IDS = tuple(f"pg024_sec001_answer_blank_{number:03d}" for number in range(1, 9))


def page_path(page: int) -> Path:
    return ROOT / ("index.html" if page == 1 else f"pg{page:03d}_sec001.html")


def write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8")
    if old == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def update_html() -> set[Path]:
    changed: set[Path] = set()
    for page in range(1, 133):
        path = page_path(page)
        text = path.read_text(encoding="utf-8")

        if page == 1:
            text = text.replace("Lyabwene M. Mtabhwa", "Lyabwene M. Mtahabwa")

        if page in GUSA_PAGES:
            text = text.replace("gusa au ", "")

        if page in DASH_PAGES:
            text = text.replace('aria-label="Dashi"', f'aria-label="{BLANK_LABEL}"')
            # Answer blanks are semantic-only elements, so this does not alter
            # the printed page artwork or its layout.
            text = re.sub(
                r'(<(?:span|p)[^>]*data-id="pg\d{3}_sec001_answer_blank_\d+"[^>]*>)Dashi\.(</(?:span|p)>)',
                rf'\1{BLANK_TEXT}\2',
                text,
            )

        if page in TABLE_DESCRIPTIONS:
            text_id, description = TABLE_DESCRIPTIONS[page]
            text = re.sub(
                rf'<caption(?: data-id="{re.escape(text_id)}")?>.*?</caption>',
                f'<caption data-id="{text_id}">{description}</caption>',
                text,
                count=1,
            )

        if page == 24 and "pg024_sec001_answer_blank_001" not in text:
            blank_number = 0

            def page_24_blank(_: re.Match[str]) -> str:
                nonlocal blank_number
                blank_number += 1
                return (
                    '<td><span class="adt-semantic-answer-blank" role="img" '
                    f'aria-label="{BLANK_LABEL}" '
                    f'data-id="pg024_sec001_answer_blank_{blank_number:03d}">'
                    f'{BLANK_TEXT}</span></td>'
                )

            semantic_start = text.find('<div class="adt-semantic-page">')
            before, semantic = text[:semantic_start], text[semantic_start:]
            semantic = re.sub(r"<td></td>", page_24_blank, semantic)
            if blank_number != 8:
                raise RuntimeError(f"Expected 8 empty answer cells on page 24, found {blank_number}")
            text = before + semantic

        # Correct semantic narration where the visible artwork contains an
        # empty answer field rather than a literal dash character.
        if page in (36, 38, 41, 127):
            semantic_start = text.find('<div class="adt-semantic-page">')
            if semantic_start >= 0:
                before, semantic = text[:semantic_start], text[semantic_start:]
                semantic = semantic.replace("Dashi.", BLANK_TEXT)
                semantic = re.sub(r"\bdashi\b", "nafasi ya kuandika jibu", semantic)
                semantic = semantic.replace(". nafasi ya kuandika jibu", ". Nafasi ya kuandika jibu")
                semantic = semantic.replace("Nafasi ya kuandika jibu..", BLANK_TEXT)
                text = before + semantic

        if f'data-id="{END_ID}"' not in text:
            text, count = re.subn(
                r'(</ol>\s*</div>)',
                rf'<li><p data-id="{END_ID}">{END_TEXT}</p></li>\1',
                text,
                count=1,
            )
            if count != 1:
                raise RuntimeError(f"Could not find reading-order list in {path.name}")

        if write_if_changed(path, text):
            changed.add(path)

    # Some pages also have secondary HTML sections. Keep their inline fallback
    # instructions synchronized with the localized text used by the runtime.
    for path in ROOT.glob("pg*_sec*.html"):
        if path.name.endswith("_sec001.html"):
            continue
        text = path.read_text(encoding="utf-8").replace("gusa au ", "")
        if write_if_changed(path, text):
            changed.add(path)
    return changed


def semantic_text_by_id(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for match in re.finditer(
        r'<[^>]+data-id="([^"]+)"[^>]*>(.*?)</[^>]+>', text, flags=re.DOTALL
    ):
        value = re.sub(r"<[^>]+>", " ", match.group(2))
        value = re.sub(r"\s+", " ", value).strip()
        result[match.group(1)] = html.unescape(value)
    return result


def update_text_and_audio_manifests() -> tuple[set[str], set[str]]:
    regenerated: set[str] = {
        "pg001_im001",
        "pg001_n0013",
        "pg001_n0013_easy_read",
        "pg001_n0015",
        "pg001_n0015_easy_read",
        "pg002_n0004",
        "pg002_n0007",
        "pg002_n0008",
        "pg005_n0006",
        "pg005_n0008",
        "pg005_n0010",
        "pg005_n0012",
        "pg005_im001",
        "pg005_n0016",
    }
    new_ids = {END_ID, *PAGE24_BLANK_IDS, *(item[0] for item in TABLE_DESCRIPTIONS.values())}

    # Existing IDs whose visible semantic wording changed.
    changed_pages = {1, 24, *GUSA_PAGES, *DASH_PAGES, 127}
    current: dict[str, str] = {}
    for page in changed_pages:
        current.update(semantic_text_by_id(page_path(page)))

    for lang in LANGS:
        base = ROOT / "content" / "i18n" / lang
        texts_path = base / "texts.json"
        audios_path = base / "audios.json"
        texts = json.loads(texts_path.read_text(encoding="utf-8"))
        audios = json.loads(audios_path.read_text(encoding="utf-8"))
        try:
            original_texts = json.loads(
                subprocess.check_output(
                    ["git", "show", f"HEAD:content/i18n/{lang}/texts.json"],
                    cwd=ROOT,
                )
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            original_texts = {}

        for text_id, value in current.items():
            if text_id not in texts:
                continue
            original = original_texts.get(text_id, texts[text_id])
            if isinstance(original, str) and original.strip() == value.strip():
                texts[text_id] = original
            else:
                if texts[text_id] != value:
                    texts[text_id] = value
                if text_id in audios:
                    regenerated.add(text_id)

        # Easy-read mirrors of the corrected front-page name.
        texts["pg001_n0015_easy_read"] = "Dkt. Lyabwene M. Mtahabwa"
        for text_id in GUSA_EASY_READ_IDS:
            corrected = texts[text_id].replace("gusa au ", "")
            if corrected != texts[text_id]:
                texts[text_id] = corrected
                regenerated.add(text_id)
        # The later whole-book correction removes the touch instruction from
        # every standard and Easy Read string, not only the initially reported
        # pages.
        for text_id, value in list(texts.items()):
            if not isinstance(value, str) or not re.search(r"\bgusa\b", value, re.IGNORECASE):
                continue
            corrected = re.sub(r"\bgusa\s+au\s+", "", value, flags=re.IGNORECASE)
            corrected = re.sub(r"\bgusa\b", "", corrected, flags=re.IGNORECASE)
            corrected = re.sub(r"\s{2,}", " ", corrected)
            corrected = corrected.replace(" ,", ",")
            texts[text_id] = corrected
            if text_id in audios:
                regenerated.add(text_id)

        for _, (text_id, description) in TABLE_DESCRIPTIONS.items():
            texts[text_id] = description
            audios.setdefault(text_id, f"{text_id}_daudi_v1.mp3")
        texts[END_ID] = END_TEXT
        audios.setdefault(END_ID, f"{END_ID}_daudi_v1.mp3")
        for text_id in PAGE24_BLANK_IDS:
            texts[text_id] = BLANK_TEXT
            audios.setdefault(text_id, f"{text_id}_daudi_v1.mp3")

        texts_path.write_text(json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audios_path.write_text(json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return regenerated, new_ids


def update_interface_labels() -> None:
    for lang in LANGS:
        path = ROOT / "assets" / "interface_translations" / lang / "interface_translations.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["glossary-book-label"] = "Faharasa ya kitabu"
        data["glossary-label"] = "Faharasa"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def update_page_semantics() -> None:
    path = ROOT / "content" / "page-semantics.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for page in range(1, 133):
        key = f"{page:03d}"
        items = data.get(key, [])
        html_values = semantic_text_by_id(page_path(page))
        for item in items:
            text_id = item.get("id")
            if text_id in html_values:
                item["text"] = html_values[text_id]
        table = TABLE_DESCRIPTIONS.get(page)
        if table and not any(item.get("id") == table[0] for item in items):
            items.append({"kind": "text", "id": table[0], "tag": "caption", "text": table[1]})
        if not any(item.get("id") == END_ID for item in items):
            items.append({"kind": "text", "id": END_ID, "tag": "p", "text": END_TEXT})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    changed_html = update_html()
    regenerated, new_ids = update_text_and_audio_manifests()
    update_interface_labels()
    update_page_semantics()

    ids_path = ROOT / ".validation_audio_ids.txt"
    ids_path.write_text("\n".join(sorted(regenerated | new_ids)) + "\n", encoding="utf-8")
    print(f"Updated {len(changed_html)} HTML pages.")
    print(f"Prepared {len(regenerated | new_ids)} audio IDs in {ids_path.name}.")


if __name__ == "__main__":
    main()
