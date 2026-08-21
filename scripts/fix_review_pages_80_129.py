#!/usr/bin/env python3
"""Apply the August listening-review fixes for PDF pages 80 through 129.

Each stage is intentionally independent so corrections can be applied and
verified in the same page order as the listening notes.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTICS_PATH = ROOT / "content/page-semantics.json"
LOCALES = ("sw", "sw-TZ")
ANSWER_PATTERN = "Makumi dashi, mamoja dashi, ni sawa na dashi."


def read_page(page: int) -> str:
    return (ROOT / f"pg{page:03d}_sec001.html").read_text(encoding="utf-8")


def write_page(page: int, source: str) -> None:
    (ROOT / f"pg{page:03d}_sec001.html").write_text(source, encoding="utf-8")


def update_first_semantic_table(page: int, transform) -> None:
    source = read_page(page)
    pattern = re.compile(
        r'(<div class="adt-semantic-page">.*?<table\b[^>]*>.*?<tbody>)(.*?)(</tbody></table>)',
        re.DOTALL,
    )
    match = pattern.search(source)
    if not match:
        raise RuntimeError(f"No semantic table found on page {page}")
    replacement = match.group(1) + transform(match.group(2)) + match.group(3)
    write_page(page, source[: match.start()] + replacement + source[match.end() :])


def table_rows(body: str) -> list[str]:
    return re.findall(r"<tr>.*?</tr>", body, flags=re.DOTALL)


def replace_inline_text(source: str, text_id: str, value: str) -> str:
    pattern = re.compile(
        rf'(<(?P<tag>p|span|figcaption)\b(?=[^>]*data-id="{re.escape(text_id)}")[^>]*>)'
        rf'.*?(</(?P=tag)>)',
        re.DOTALL,
    )
    return pattern.sub(lambda match: match.group(1) + value + match.group(3), source)


def set_localized_texts(updates: dict[str, str], new_ids: set[str] | None = None) -> None:
    new_ids = new_ids or set()
    for locale in LOCALES:
        base = ROOT / "content/i18n" / locale
        texts_path = base / "texts.json"
        audios_path = base / "audios.json"
        texts = json.loads(texts_path.read_text(encoding="utf-8"))
        audios = json.loads(audios_path.read_text(encoding="utf-8"))
        for text_id, value in updates.items():
            texts[text_id] = value
            if text_id in new_ids:
                texts[f"{text_id}_easy_read"] = value
                audios[text_id] = f"{text_id}_daudi_v1.mp3"
                audios[f"{text_id}_easy_read"] = f"{text_id}_easy_read_daudi_v1.mp3"
            elif f"{text_id}_easy_read" in texts:
                texts[f"{text_id}_easy_read"] = value
        texts_path.write_text(json.dumps(texts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        audios_path.write_text(json.dumps(audios, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_page_texts(page: int, updates: dict[str, str]) -> None:
    source = read_page(page)
    for text_id, value in updates.items():
        source = replace_inline_text(source, text_id, value)
    write_page(page, source)


def stage_pages80_81() -> None:
    def fix_80(body: str) -> str:
        rows = [row for row in table_rows(body) if "pg080_n0017" in row or "pg080_n0029" in row]
        duplicate_ids = (2, 4, 6, 8)
        for index, row in enumerate(rows):
            for blank_number in duplicate_ids:
                row = re.sub(
                    rf'<span\b(?=[^>]*data-id="pg080_sec001_answer_blank_{blank_number:03d}")[^>]*>.*?</span>',
                    "",
                    row,
                    flags=re.DOTALL,
                )
            rows[index] = row
        return "".join(rows)

    def fix_81(body: str) -> str:
        return "".join(row for row in table_rows(body) if "pg081_n" in row)

    update_first_semantic_table(80, fix_80)
    update_first_semantic_table(81, fix_81)

    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    page80_table = next(block for block in semantics["080"] if block.get("kind") == "table")
    page80_table["rows"] = page80_table["rows"][:2]
    for row in page80_table["rows"]:
        for cell in row[3:5]:
            cell["blanks"] = 1
            cell["blank_labels"] = ["Dashi"]

    page81_table = next(block for block in semantics["081"] if block.get("kind") == "table")
    page81_table["rows"] = [
        row for row in page81_table["rows"]
        if any(cell.get("items") for cell in row)
    ]
    SEMANTICS_PATH.write_text(
        json.dumps(semantics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def stage_pages84_86() -> None:
    pattern_ids_84 = {
        "pg084_im013_seg001_v1_crop_v1": "pg084_q1_answer_pattern_v1",
        "pg084_im013_seg002_v1": "pg084_q2_answer_pattern_v1",
    }
    pattern_ids_85 = {
        "pg085_im012_seg001_v1": "pg085_q3_answer_pattern_v1",
        "pg085_im012_seg003_v1": "pg085_q4_answer_pattern_v1",
        "pg085_im012_seg005_v1": "pg085_q5_answer_pattern_v1",
        "pg085_im012_seg002_v1": "pg085_q6_answer_pattern_v1",
        "pg085_im012_seg004_v1": "pg085_q7_answer_pattern_v1",
        "pg085_im012_seg006_v1": "pg085_q8_answer_pattern_v1",
    }
    caption_updates = {
        "pg085_im012_seg001_v1": "Makumi 6 na mamoja 1 ni 61.",
        "pg085_im012_seg003_v1": "Makumi 5 na mamoja 0 ni 50.",
        "pg085_im012_seg005_v1": "Makumi 2 na mamoja 6 ni 26.",
        "pg085_im012_seg002_v1": "Makumi 0 na mamoja 4 ni 4.",
        "pg085_im012_seg004_v1": "Makumi 2 na mamoja 7 ni 27.",
        "pg085_im012_seg006_v1": "Makumi 6 na mamoja 0 ni 60.",
    }
    page86_values = [34, 73, 5, 29, 90, 66, 87, 51]
    page86_ids = [f"pg086_n{number:04d}" for number in range(10, 46, 5)]
    page86_updates = {
        text_id: f"{value} ni sawa na makumi dashi mamoja dashi."
        for text_id, value in zip(page86_ids, page86_values)
    }
    all_new_ids = set(pattern_ids_84.values()) | set(pattern_ids_85.values())
    updates = {text_id: ANSWER_PATTERN for text_id in all_new_ids}
    updates.update(caption_updates)
    updates.update(page86_updates)
    set_localized_texts(updates, all_new_ids)

    for page, mappings in ((84, pattern_ids_84), (85, pattern_ids_85)):
        source = read_page(page)
        for text_id, value in caption_updates.items():
            if text_id.startswith(f"pg{page:03d}_"):
                source = replace_inline_text(source, text_id, value)
        for pattern_id in mappings.values():
            source = re.sub(
                rf'<li><p data-id="{re.escape(pattern_id)}">.*?</p></li>',
                "",
                source,
                flags=re.DOTALL,
            )
        source = re.sub(
            r'<li><span\b(?=[^>]*adt-semantic-answer-blank)[^>]*>.*?</span></li>',
            "",
            source,
            flags=re.DOTALL,
        )
        source = re.sub(
            rf'<li><p data-id="pg{page:03d}_n(?:0025|0030|0006)">=</p></li>',
            "",
            source,
        )
        for image_id, pattern_id in mappings.items():
            source = re.sub(
                rf'(<li><figure\b.*?<figcaption\b[^>]*data-id="{re.escape(image_id)}".*?</figure></li>)',
                rf'\1<li><p data-id="{pattern_id}">{ANSWER_PATTERN}</p></li>',
                source,
                count=1,
                flags=re.DOTALL,
            )
        write_page(page, source)

    source86 = read_page(86)
    for text_id, value in page86_updates.items():
        source86 = replace_inline_text(source86, text_id, value)
    source86 = re.sub(
        r'<span\b(?=[^>]*adt-semantic-answer-blank)[^>]*>.*?</span>',
        "",
        source86,
        flags=re.DOTALL,
    )
    write_page(86, source86)

    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    for page, mappings in ((84, pattern_ids_84), (85, pattern_ids_85)):
        rebuilt = []
        for block in semantics[f"{page:03d}"]:
            if block.get("kind") == "blank" or block.get("id") in {"pg084_n0025", "pg084_n0030", "pg085_n0006"}:
                continue
            text_id = block.get("id")
            if text_id in caption_updates:
                block["text"] = caption_updates[text_id]
            rebuilt.append(block)
            if text_id in mappings:
                pattern_id = mappings[text_id]
                rebuilt.append({"kind": "text", "id": pattern_id, "tag": "p", "text": ANSWER_PATTERN})
        semantics[f"{page:03d}"] = rebuilt
    page86_table = next(block for block in semantics["086"] if block.get("kind") == "table")
    for row, (text_id, value) in zip(page86_table["rows"], page86_updates.items()):
        cell = row[1]
        cell["items"][0]["text"] = value
        cell["blanks"] = 0
        cell.pop("blank_labels", None)
    SEMANTICS_PATH.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stage_pages101_105() -> None:
    page101_updates = {
        "pg101_q19_review_v1": "Swali la kumi na tisa. Arobaini na saba jumlisha arobaini na saba ni sawa na dashi.",
        "pg101_q20_review_v1": "Swali la ishirini. Hamsini na saba jumlisha kumi na tatu ni sawa na dashi.",
        "pg101_q21_review_v1": "Swali la ishirini na moja. Kumi na tisa jumlisha ishirini na tisa ni sawa na dashi.",
    }
    page103_updates = {
        f"pg103_n{number:04d}": "Jumla ni shilingi dashi."
        for number in (8, 13, 18, 23, 28, 33)
    }
    page104_105_ids = [
        "pg104_n0022", "pg104_n0029", "pg104_n0036",
        "pg105_n0005", "pg105_n0009", "pg105_n0013", "pg105_n0018", "pg105_n0023",
    ]
    texts = json.loads((ROOT / "content/i18n/sw-TZ/texts.json").read_text(encoding="utf-8"))
    prose_updates = {}
    for text_id in page104_105_ids:
        value = texts[text_id]
        value = re.sub(r"\s*Jibu ni dashi\.?$", " Dashi.", value, flags=re.IGNORECASE)
        prose_updates[text_id] = value

    updates = page101_updates | page103_updates | prose_updates
    set_localized_texts(updates, set(page101_updates))

    source101 = read_page(101)
    for text_id in page101_updates:
        source101 = re.sub(
            rf'<li><p data-id="{re.escape(text_id)}">.*?</p></li>',
            "",
            source101,
            flags=re.DOTALL,
        )
    insertion = "".join(f'<li><p data-id="{text_id}">{value}</p></li>' for text_id, value in page101_updates.items())
    source101 = source101.replace('<ol class="adt-page-reading-order">', '<ol class="adt-page-reading-order">' + insertion, 1)
    write_page(101, source101)
    replace_page_texts(103, page103_updates)
    replace_page_texts(104, {k: v for k, v in prose_updates.items() if k.startswith("pg104_")})
    replace_page_texts(105, {k: v for k, v in prose_updates.items() if k.startswith("pg105_")})

    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    semantics["101"] = [
        {"kind": "text", "id": text_id, "tag": "p", "text": value}
        for text_id, value in page101_updates.items()
    ] + [block for block in semantics["101"] if block.get("id") not in page101_updates]
    for page in (103, 104, 105):
        for block in semantics[f"{page:03d}"]:
            text_id = block.get("id")
            if text_id in updates:
                block["text"] = updates[text_id]
    SEMANTICS_PATH.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stage_pages114_122() -> None:
    previous_questions = {
        "pg114_prev_q09_review_v1": "Swali la tisa. Thelathini na sita toa tisa ni dashi.",
        "pg114_prev_q10_review_v1": "Swali la kumi. Sabini na mbili toa ishirini na nane ni dashi.",
        "pg114_prev_q11_review_v1": "Swali la kumi na moja. Arobaini na tatu toa kumi na tisa ni dashi.",
        "pg114_prev_q12_review_v1": "Swali la kumi na mbili. Tisini na moja toa thelathini na tatu ni dashi.",
        "pg114_prev_q13_review_v1": "Swali la kumi na tatu. Ishirini na tatu toa kumi na nne ni dashi.",
        "pg114_prev_q14_review_v1": "Swali la kumi na nne. Sabini toa kumi na tisa ni dashi.",
    }
    texts = json.loads((ROOT / "content/i18n/sw-TZ/texts.json").read_text(encoding="utf-8"))

    page118_ids = [f"pg118_n{number:04d}" for number in (3, 12, 21, 30, 6, 15, 24, 33, 9, 18, 27, 36)]
    page118_updates = {}
    for text_id in page118_ids:
        value = texts[text_id]
        match = re.fullmatch(r"(Swali la .+?\.) Toa (.+?) kutoka (.+?), jibu ni dashi\.", value, flags=re.IGNORECASE)
        if match:
            ordinal, subtrahend, minuend = match.groups()
            page118_updates[text_id] = f"{ordinal} {minuend.capitalize()} toa {subtrahend} ni dashi."
        elif re.fullmatch(r"Swali la .+?\. .+? toa .+? ni dashi\.", value, flags=re.IGNORECASE):
            page118_updates[text_id] = value
        else:
            raise RuntimeError(f"Unexpected page 118 narration: {text_id} -> {value}")

    plain_dashi_ids = [
        *[f"pg119_n{number:04d}" for number in (8, 11, 14, 17, 20, 23, 26, 29)],
        *[f"pg121_n{number:04d}" for number in (17, 22, 27)],
        *[f"pg122_n{number:04d}" for number in (7, 12, 17, 22, 27)],
    ]
    plain_dashi_updates = {}
    for text_id in plain_dashi_ids:
        value = texts[text_id]
        plain_dashi_updates[text_id] = re.sub(
            r"\s*Jibu ni dashi\.?$", " Dashi.", value, flags=re.IGNORECASE
        )

    page120_updates = {
        f"pg120_n{number:04d}": "Jumla ni shilingi dashi."
        for number in (7, 11, 15, 19, 23, 27)
    }
    updates = previous_questions | page118_updates | plain_dashi_updates | page120_updates
    set_localized_texts(updates, set(previous_questions))

    source114 = read_page(114)
    for text_id in previous_questions:
        source114 = re.sub(rf'<li><p data-id="{re.escape(text_id)}">.*?</p></li>', "", source114, flags=re.DOTALL)
    insertion = "".join(f'<li><p data-id="{text_id}">{value}</p></li>' for text_id, value in previous_questions.items())
    source114 = source114.replace('<ol class="adt-page-reading-order">', '<ol class="adt-page-reading-order">' + insertion, 1)
    write_page(114, source114)

    for page, page_updates in (
        (118, page118_updates),
        (119, {k: v for k, v in plain_dashi_updates.items() if k.startswith("pg119_")}),
        (120, page120_updates),
        (121, {k: v for k, v in plain_dashi_updates.items() if k.startswith("pg121_")}),
        (122, {k: v for k, v in plain_dashi_updates.items() if k.startswith("pg122_")}),
    ):
        replace_page_texts(page, page_updates)

    source120 = read_page(120)
    source120 = re.sub(
        r'<li><figure\b.*?<figcaption\b[^>]*data-id="pg120_im006".*?</figure></li>',
        "",
        source120,
        count=1,
        flags=re.DOTALL,
    )
    write_page(120, source120)

    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    semantics["114"] = [
        {"kind": "text", "id": text_id, "tag": "p", "text": value}
        for text_id, value in previous_questions.items()
    ] + [block for block in semantics["114"] if block.get("id") not in previous_questions]
    semantics["120"] = [block for block in semantics["120"] if block.get("id") != "pg120_im006"]
    for page in (118, 119, 120, 121, 122):
        for block in semantics[f"{page:03d}"]:
            text_id = block.get("id")
            if text_id in updates:
                block["text"] = updates[text_id]
    SEMANTICS_PATH.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stage_pages126_129() -> None:
    shape_updates = {
        "pg126_im008_seg001_v1_crop1": "Swali la kwanza. Mchoro unaonesha duara la rangi ya njano. Dashi.",
        "pg126_im008_seg003_v1_crop1": "Swali la pili. Mchoro unaonesha mraba wa rangi ya njano. Dashi.",
        "pg126_im008_seg005_v1_crop1": "Swali la tatu. Mchoro unaonesha mstatili wa rangi ya buluu isiyokolea. Dashi.",
        "pg126_im008_seg007_v1_crop1": "Swali la nne. Mchoro unaonesha mraba wa rangi ya kijani. Dashi.",
        "pg126_im008_seg002_v1_crop1": "Swali la tano. Mchoro unaonesha tiara ya rangi ya buluu. Dashi.",
        "pg126_im008_seg004_v1_crop1": "Swali la sita. Mchoro unaonesha nyota ya rangi ya njano. Dashi.",
        "pg126_im008_seg006_v1_crop1": "Swali la saba. Mchoro unaonesha mstatili wa rangi ya kijani. Dashi.",
        "pg126_im008_seg008_v1_crop1": "Swali la nane. Mchoro unaonesha pembetatu ya rangi ya zambarau. Dashi.",
        "pg127_im006_seg001_v1_crop1": "Swali la tisa. Mchoro unaonesha duara la rangi ya kijivu. Dashi.",
        "pg127_im006_seg003_v1_crop1": "Swali la kumi. Mchoro unaonesha pembetatu ya rangi ya njano. Dashi.",
        "pg127_im006_seg002_v1_crop_v1_crop1": "Swali la kumi na moja. Mchoro unaonesha mviringo wa rangi ya waridi. Dashi.",
        "pg127_im006_seg004_v1_crop1": "Swali la kumi na mbili. Mchoro unaonesha pentagoni ya rangi ya waridi isiyokolea. Dashi.",
    }
    number_ids_126 = {"pg126_n0005", "pg126_n0011", "pg126_n0017", "pg126_n0023", "pg126_n0008", "pg126_n0014", "pg126_n0020", "pg126_n0026"}
    number_ids_127 = {"pg127_n0005", "pg127_n0014", "pg127_n0009", "pg127_n0018"}

    page128_names = ["Pembetatu", "Duara", "Mstatili", "Mraba", "Mviringo", "Nyota", "Tiara", "Pentagoni"]
    ordinal_words = ["moja", "mbili", "tatu", "nne", "tano", "sita", "saba", "nane"]
    page128_name_updates = {
        f"pg128_n{number:04d}_txt": f"Namba {ordinal_words[index]}, {name}."
        for index, (number, name) in enumerate(zip(range(5, 13), page128_names))
    }
    page128_new = {
        "pg128_column1_label_v1": "Safu ya kwanza, majina ya maumbo.",
        "pg128_column2_label_v1": "Safu ya pili, michoro ya maumbo.",
        "pg128_shape1_review_v1": "Namba moja, mstatili wa rangi ya waridi.",
        "pg128_shape2_review_v1": "Namba mbili, mraba wa rangi ya buluu.",
        "pg128_shape3_review_v1": "Namba tatu, duara la rangi ya njano.",
        "pg128_shape4_review_v1": "Namba nne, pembetatu ya rangi ya njano.",
        "pg128_shape5_review_v1": "Namba tano, mviringo wa rangi ya kijani.",
        "pg128_shape6_review_v1": "Namba sita, tiara ya rangi ya chungwa.",
        "pg128_shape7_review_v1": "Namba saba, nyota ya rangi ya waridi.",
        "pg128_shape8_review_v1": "Namba nane, pentagoni ya rangi ya buluu.",
    }

    page129_updates = {
        "pg129_n0003": "Chunguza, gusa au sikiliza maelezo ya maumbo yafuatayo, kisha andika herufi zote zinazoonesha maumbo bapa.",
        "pg129_im018_seg001_v1_crop_v1_crop1": "Herufi a. Tufe la rangi ya buluu; hili ni umbo la anga tatu lenye uso uliopinda.",
        "pg129_im018_seg002_v1_crop_v1_crop1": "Herufi b. Koni ya rangi nyekundu; hili ni umbo la anga tatu lenye kitako cha duara na ncha moja.",
        "pg129_im018_seg003_v1_crop_v1_crop1": "Herufi c. Mviringo wa rangi ya chungwa isiyokolea; hili ni umbo bapa.",
        "pg129_im018_seg004_v1_crop_v1_crop1": "Herufi d. Mraba wa rangi ya njano; hili ni umbo bapa lenye pande nne sawa.",
        "pg129_im018_seg005_v1_crop_v1_crop1": "Herufi e. Pembetatu ya rangi ya kijani; hili ni umbo bapa lenye pande tatu.",
        "pg129_im018_seg006_v1_crop_v1": "Herufi f. Mche mstatili wa rangi ya chungwa; hili ni umbo la anga tatu lenye nyuso za mstatili.",
        "pg129_im018_seg007_v1_crop_v1_crop1": "Herufi g. Tufe la rangi ya buluu isiyokolea; hili ni umbo la anga tatu lenye uso uliopinda.",
        "pg129_im018_seg008_v1_crop1": "Herufi h. Mche mraba wa rangi nyekundu; hili ni umbo la anga tatu lenye nyuso sita za mraba.",
        "pg129_im018_seg009_v1_crop_v1_crop1": "Herufi i. Mstatili wa rangi ya njano; hili ni umbo bapa lenye pande nne.",
        "pg129_im018_seg010_v1_crop_v1_crop1": "Herufi j. Silinda ya rangi ya buluu; hili ni umbo la anga tatu lenye vitako viwili vya duara.",
    }
    new_ids = set(page128_new)
    updates = shape_updates | page128_name_updates | page128_new | page129_updates
    set_localized_texts(updates, new_ids)

    for page, removed_ids in ((126, number_ids_126), (127, number_ids_127)):
        source = read_page(page)
        for text_id, value in shape_updates.items():
            if text_id.startswith(f"pg{page:03d}_"):
                source = replace_inline_text(source, text_id, value)
        for text_id in removed_ids:
            source = re.sub(rf'<li><p data-id="{re.escape(text_id)}">.*?</p></li>', "", source, flags=re.DOTALL)
        write_page(page, source)

    source128 = read_page(128)
    body128 = [
        '<li><p data-id="pg128_n0002">Zoezi la 4</p></li>',
        '<li><p data-id="pg128_n0003">Chora mstari kuoanisha umbo na jina lake.</p></li>',
        f'<li><p data-id="pg128_column1_label_v1">{page128_new["pg128_column1_label_v1"]}</p></li>',
    ]
    body128.extend(f'<li><p data-id="{text_id}">{value}</p></li>' for text_id, value in page128_name_updates.items())
    body128.append(f'<li><p data-id="pg128_column2_label_v1">{page128_new["pg128_column2_label_v1"]}</p></li>')
    body128.extend(
        f'<li><p data-id="pg128_shape{index}_review_v1">{page128_new[f"pg128_shape{index}_review_v1"]}</p></li>'
        for index in range(1, 9)
    )
    source128 = re.sub(
        r'(<div class="adt-semantic-page"><p\b.*?</p><ol class="adt-page-reading-order">).*?(</ol></div>)',
        lambda match: match.group(1) + "".join(body128) + match.group(2),
        source128,
        count=1,
        flags=re.DOTALL,
    )
    write_page(128, source128)

    source129 = read_page(129)
    for text_id, value in page129_updates.items():
        if text_id != "pg129_answer_dash_review_v1":
            source129 = replace_inline_text(source129, text_id, value)
    source129 = re.sub(r'<li><p data-id="pg129_answer_dash_review_v1">.*?</p></li>', "", source129, flags=re.DOTALL)
    write_page(129, source129)

    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    for page, removed_ids in ((126, number_ids_126), (127, number_ids_127)):
        rebuilt = []
        for block in semantics[f"{page:03d}"]:
            if block.get("id") in removed_ids:
                continue
            if block.get("id") in shape_updates:
                block["text"] = shape_updates[block["id"]]
            rebuilt.append(block)
        semantics[f"{page:03d}"] = rebuilt
    semantics["128"] = [
        {"kind": "text", "id": "pg128_n0002", "tag": "p", "text": "Zoezi la 4"},
        {"kind": "text", "id": "pg128_n0003", "tag": "p", "text": "Chora mstari kuoanisha umbo na jina lake."},
        {"kind": "text", "id": "pg128_column1_label_v1", "tag": "p", "text": page128_new["pg128_column1_label_v1"]},
        *({"kind": "text", "id": text_id, "tag": "p", "text": value} for text_id, value in page128_name_updates.items()),
        {"kind": "text", "id": "pg128_column2_label_v1", "tag": "p", "text": page128_new["pg128_column2_label_v1"]},
        *({"kind": "text", "id": f"pg128_shape{index}_review_v1", "tag": "p", "text": page128_new[f"pg128_shape{index}_review_v1"]} for index in range(1, 9)),
    ]
    rebuilt129 = []
    for block in semantics["129"]:
        text_id = block.get("id")
        if text_id == "pg129_answer_dash_review_v1":
            continue
        if text_id in page129_updates:
            block["text"] = page129_updates[text_id]
        rebuilt129.append(block)
    semantics["129"] = rebuilt129
    SEMANTICS_PATH.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stage_audio_ids() -> None:
    ids = {
        "pg084_q1_answer_pattern_v1", "pg084_q2_answer_pattern_v1",
        *{f"pg085_q{number}_answer_pattern_v1" for number in range(3, 9)},
        *{f"pg085_im012_seg{number:03d}_v1" for number in range(1, 7)},
        *{f"pg086_n{number:04d}" for number in range(10, 46, 5)},
        *{f"pg101_q{number}_review_v1" for number in range(19, 22)},
        *{f"pg103_n{number:04d}" for number in (8, 13, 18, 23, 28, 33)},
        *{f"pg104_n{number:04d}" for number in (22, 29, 36)},
        *{f"pg105_n{number:04d}" for number in (5, 9, 13, 18, 23)},
        *{f"pg114_prev_q{number:02d}_review_v1" for number in range(9, 15)},
        *{f"pg118_n{number:04d}" for number in (3, 12, 21, 30, 6, 15, 24, 33, 9, 18, 27, 36)},
        *{f"pg119_n{number:04d}" for number in (8, 11, 14, 17, 20, 23, 26, 29)},
        *{f"pg120_n{number:04d}" for number in (7, 11, 15, 19, 23, 27)},
        *{f"pg121_n{number:04d}" for number in (17, 22, 27)},
        *{f"pg122_n{number:04d}" for number in (7, 12, 17, 22, 27)},
        "pg126_im008_seg001_v1_crop1", "pg126_im008_seg003_v1_crop1",
        "pg126_im008_seg005_v1_crop1", "pg126_im008_seg007_v1_crop1",
        "pg126_im008_seg002_v1_crop1", "pg126_im008_seg004_v1_crop1",
        "pg126_im008_seg006_v1_crop1", "pg126_im008_seg008_v1_crop1",
        "pg127_im006_seg001_v1_crop1", "pg127_im006_seg003_v1_crop1",
        "pg127_im006_seg002_v1_crop_v1_crop1", "pg127_im006_seg004_v1_crop1",
        *{f"pg128_n{number:04d}_txt" for number in range(5, 13)},
        "pg128_column1_label_v1", "pg128_column2_label_v1",
        *{f"pg128_shape{number}_review_v1" for number in range(1, 9)},
        "pg129_n0003",
        *{f"pg129_im018_seg{number:03d}_v1_crop_v1_crop1" for number in (1, 2, 3, 4, 5, 7, 9, 10)},
        "pg129_im018_seg006_v1_crop_v1", "pg129_im018_seg008_v1_crop1",
        "pg131_q14_shape_description_v1", "pg131_n0058", "pg131_n0063", "pg131_n0067",
        "pg132_im008_crop_v1_crop1", "pg132_n0094", "pg132_n0100", "pg132_n0106",
    }
    audios = json.loads((ROOT / "content/i18n/sw-TZ/audios.json").read_text(encoding="utf-8"))
    expanded = sorted(
        candidate
        for text_id in ids
        for candidate in (text_id, f"{text_id}_easy_read")
        if candidate in audios
    )
    destination = Path("/private/tmp/kuhesabu-review-audio-ids.txt")
    destination.write_text("\n".join(expanded) + "\n", encoding="utf-8")
    print(f"Wrote {len(expanded)} audio IDs to {destination}")


def stage_page131() -> None:
    updates = {
        "pg131_q14_shape_description_v1": (
            "Mchoro unaonesha umbo bapa la rangi ya waridi isiyokolea, "
            "lenye pande nne zilizo sawa na pembe nne."
        ),
        "pg131_n0058": "Umbo hili linaitwaje? Dashi.",
        "pg131_n0063": "Jumla ya umri wao ni miaka mingapi? Dashi.",
        "pg131_n0067": "Iwapo mayai 8 yatavunjika, yatabaki mayai mangapi? Dashi.",
    }
    set_localized_texts(updates, {"pg131_q14_shape_description_v1"})
    source = read_page(131)
    for text_id, value in updates.items():
        if text_id != "pg131_q14_shape_description_v1":
            source = replace_inline_text(source, text_id, value)
    source = re.sub(
        r'<li><p data-id="pg131_q14_shape_description_v1">.*?</p></li>',
        "",
        source,
        flags=re.DOTALL,
    )
    marker = '<li><p data-id="pg131_n0057">14.</p></li>'
    description = (
        '<li><p data-id="pg131_q14_shape_description_v1">'
        + updates["pg131_q14_shape_description_v1"]
        + "</p></li>"
    )
    source = source.replace(marker, marker + description, 1)
    write_page(131, source)

    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    rebuilt = []
    for block in semantics["131"]:
        text_id = block.get("id")
        if text_id == "pg131_q14_shape_description_v1":
            continue
        if text_id in updates:
            block["text"] = updates[text_id]
        rebuilt.append(block)
        if text_id == "pg131_n0057":
            rebuilt.append({
                "kind": "image",
                "id": "pg131_q14_shape_description_v1",
                "tag": "p",
                "text": updates["pg131_q14_shape_description_v1"],
            })
    semantics["131"] = rebuilt
    SEMANTICS_PATH.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stage_page132() -> None:
    updates = {
        "pg132_im008_crop_v1_crop1": (
            "Mchoro unaonesha umbo bapa la rangi ya njano, "
            "lenye pande tatu na pembe tatu. Dashi."
        ),
        "pg132_n0094": "Sakafu ya darasa ina umbo gani? Dashi.",
        "pg132_n0100": "Walibaki kuku wangapi? Dashi.",
        "pg132_n0106": "Jumla ana machungwa mangapi? Dashi.",
    }
    set_localized_texts(updates)
    replace_page_texts(132, updates)
    semantics = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
    for block in semantics["132"]:
        text_id = block.get("id")
        if text_id in updates:
            block["text"] = updates[text_id]
    SEMANTICS_PATH.write_text(json.dumps(semantics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


STAGES = {
    "pages80_81": stage_pages80_81,
    "pages84_86": stage_pages84_86,
    "pages101_105": stage_pages101_105,
    "pages114_122": stage_pages114_122,
    "pages126_129": stage_pages126_129,
    "audio_ids": stage_audio_ids,
    "page131": stage_page131,
    "page132": stage_page132,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=STAGES)
    args = parser.parse_args()
    STAGES[args.stage]()
    print(f"Completed {args.stage}")


if __name__ == "__main__":
    main()
