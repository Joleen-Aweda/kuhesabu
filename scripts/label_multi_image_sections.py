#!/usr/bin/env python3
"""Letter multi-image sections and place simple captions before their images."""

from __future__ import annotations

import json
import re
from pathlib import Path

from lxml import html


ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")
LETTER_RE = re.compile(r"^[a-z]+$", re.I)


def alpha_label(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(97 + remainder) + result
    return result


def image_tag_pattern(image_id: str) -> re.Pattern[str]:
    return re.compile(
        r"<img\b(?=[^>]*\bdata-id=(?:\"" + re.escape(image_id) + r"\"|'"
        + re.escape(image_id) + r"'))[^>]*>",
        re.I,
    )


def image_tag_match(source: str, image_id: str, occurrence: int) -> re.Match[str] | None:
    matches = list(image_tag_pattern(image_id).finditer(source))
    return matches[occurrence] if occurrence < len(matches) else None


def move_simple_caption_before(source: str, image_id: str, occurrence: int) -> str:
    image_pattern = image_tag_pattern(image_id)
    image_match = image_tag_match(source, image_id, occurrence)
    if not image_match:
        return source
    tail = source[image_match.end():]
    caption_match = re.match(
        r"(?P<space>\s*)(?P<caption><(?P<tag>figcaption|p|span|div)\b[^>]*\bdata-id="
        r"(?:\"[^\"]+\"|'[^']+')[^>]*>(?P<text>[^<>]+)</(?P=tag)>)",
        tail,
        re.I,
    )
    if not caption_match:
        return source
    caption_text = re.sub(r"\s+", " ", caption_match.group("text")).strip()
    if not caption_text or len(caption_text) > 60 or any(symbol in caption_text for symbol in "=+×÷"):
        return source
    start = image_match.start()
    end = image_match.end() + caption_match.end()
    replacement = caption_match.group("caption") + caption_match.group("space") + image_match.group(0)
    return source[:start] + replacement + source[end:]


def move_existing_letter_before(source: str, image_id: str, expected: str, occurrence: int) -> tuple[str, str | None]:
    image_match = image_tag_match(source, image_id, occurrence)
    if not image_match:
        return source, None
    prefix = source[:image_match.start()]
    previous_label = re.search(
        r"<(?P<tag>span|div|p)\b[^>]*\bdata-id=(?P<quote>\"|')(?P<id>[^\"']+)"
        r"(?P=quote)[^>]*>\s*(?P<text>[a-z]+)\s*</(?P=tag)>\s*$",
        prefix,
        re.I,
    )
    if previous_label and previous_label.group("text").casefold() == expected.casefold():
        return source, previous_label.group("id")
    tail = source[image_match.end():]
    label_match = re.match(
        r"(?P<space>\s*)(?P<label><(?P<tag>span|div|p)\b[^>]*\bdata-id="
        r"(?P<quote>\"|')(?P<id>[^\"']+)(?P=quote)[^>]*>\s*(?P<text>[a-z]+)\s*</(?P=tag)>)",
        tail,
        re.I,
    )
    if not label_match or label_match.group("text").casefold() != expected.casefold():
        return source, None
    start = image_match.start()
    end = image_match.end() + label_match.end()
    replacement = label_match.group("label") + label_match.group("space") + image_match.group(0)
    return source[:start] + replacement + source[end:], label_match.group("id")


def insert_label(source: str, image_id: str, label_id: str, label: str, occurrence: int) -> str:
    image_match = image_tag_match(source, image_id, occurrence)
    if not image_match:
        return source
    insertion = (
        f'<div data-id="{label_id}" class="image-sequence-label font-bold italic '
        f'text-sky-600">{label}</div>\n'
    )
    # If a caption was moved above the image, put the letter before that caption.
    prefix = source[:image_match.start()]
    caption = re.search(
        r"<(?P<tag>figcaption|p|span|div)\b[^>]*\bdata-id=(?:\"[^\"]+\"|'[^']+')[^>]*>"
        r"[^<>]+</(?P=tag)>\s*$",
        prefix,
        re.I,
    )
    position = caption.start() if caption else image_match.start()
    return source[:position] + insertion + source[position:]


def main() -> None:
    text_maps = {
        lang: json.loads((ROOT / f"content/i18n/{lang}/texts.json").read_text(encoding="utf-8"))
        for lang in LANGS
    }
    audio_maps = {
        lang: json.loads((ROOT / f"content/i18n/{lang}/audios.json").read_text(encoding="utf-8"))
        for lang in LANGS
    }
    new_ids: list[str] = []
    changed_files: list[str] = []
    image_count = 0

    files = sorted(ROOT.glob("pg*_sec*.html")) + sorted(ROOT.glob("qz*.html"))
    for path in files:
        source = path.read_text(encoding="utf-8")
        try:
            document = html.fromstring(source)
        except Exception:
            continue
        file_changed = False
        for section in document.xpath("//section"):
            images = section.xpath(
                './/img[not(contains(concat(" ",normalize-space(@class)," ")," hidden "))]'
            )
            images = [image for image in images if image.get("data-id")]
            if len(images) < 2:
                continue
            section_id = section.get("data-section-id") or section.get("data-id") or path.stem
            image_occurrences: dict[str, int] = {}
            for index, image in enumerate(images):
                image_count += 1
                image_id = image.get("data-id")
                occurrence = image_occurrences.get(image_id, 0)
                image_occurrences[image_id] = occurrence + 1
                label = alpha_label(index)

                updated, existing_id = move_existing_letter_before(source, image_id, label, occurrence)
                if updated != source:
                    source = updated
                    file_changed = True
                if existing_id:
                    continue

                updated = move_simple_caption_before(source, image_id, occurrence)
                if updated != source:
                    source = updated
                    file_changed = True

                label_id = f"{section_id}_imglbl{index + 1:03d}"
                if f'data-id="{label_id}"' not in source and f"data-id='{label_id}'" not in source:
                    source = insert_label(source, image_id, label_id, label, occurrence)
                    file_changed = True
                for lang in LANGS:
                    text_maps[lang][label_id] = label
                    text_maps[lang][label_id + "_easy_read"] = label
                    audio_maps[lang][label_id] = label_id + ".mp3"
                    audio_maps[lang][label_id + "_easy_read"] = label_id + "_easy_read.mp3"
                new_ids.extend((label_id, label_id + "_easy_read"))

        if file_changed:
            path.write_text(source, encoding="utf-8")
            changed_files.append(path.name)

    for lang in LANGS:
        (ROOT / f"content/i18n/{lang}/texts.json").write_text(
            json.dumps(text_maps[lang], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (ROOT / f"content/i18n/{lang}/audios.json").write_text(
            json.dumps(audio_maps[lang], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    ids_path = ROOT / "reports/multi_image_label_audio_ids.txt"
    ids_path.parent.mkdir(parents=True, exist_ok=True)
    ids_path.write_text("\n".join(sorted(set(new_ids))) + "\n", encoding="utf-8")
    print(json.dumps({
        "changed_files": len(changed_files),
        "multi_image_images": image_count,
        "new_text_audio_ids": len(set(new_ids)),
    }, indent=2))


if __name__ == "__main__":
    main()
