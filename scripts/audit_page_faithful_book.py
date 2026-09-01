#!/usr/bin/env python3
"""Audit both original covers plus 132 PDF-faithful textbook pages."""

from __future__ import annotations

import json
import re
from pathlib import Path

from lxml import html


ROOT = Path(__file__).resolve().parents[1]
LANGS = ("sw", "sw-TZ")
OFFLINE_START = "  var INLINE = "
OFFLINE_END = ";\n  var BASE_DIR = "


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def main() -> None:
    errors: list[str] = []
    pages = load_json(ROOT / "content/pages.json")
    if len(pages) != 134:
        errors.append(f"pages.json has {len(pages)} entries instead of 134")
    if not pages or pages[0] != {"section_id": "cover_sec001", "href": "index.html"}:
        errors.append("pages.json does not begin with the original front cover")
    if not pages or pages[-1] != {"section_id": "back_cover_sec001", "href": "back-cover.html"}:
        errors.append("pages.json does not end with the original back cover")

    cover_path = ROOT / "index.html"
    if not cover_path.is_file():
        errors.append("missing original front-cover page: index.html")
    else:
        cover_document = html.fromstring(cover_path.read_text(encoding="utf-8"))
        if cover_document.xpath('//meta[@name="title-id"]/@content') != ["cover_sec001"]:
            errors.append("index.html: incorrect cover title-id")
        if cover_document.xpath('//meta[@name="page-section-id"]/@content') != ["1"]:
            errors.append("index.html: incorrect cover page-section-id")
        cover_image = cover_document.xpath(
            '//section[@data-section-id="cover_sec001"]//img[@src="images/book-cover-front.png"]'
        )
        if len(cover_image) != 1 or not (ROOT / "images/book-cover-front.png").is_file():
            errors.append("index.html: missing original front-cover image")

    back_cover_path = ROOT / "back-cover.html"
    if not back_cover_path.is_file():
        errors.append("missing original back-cover page: back-cover.html")
    else:
        back_cover_document = html.fromstring(back_cover_path.read_text(encoding="utf-8"))
        if back_cover_document.xpath('//meta[@name="title-id"]/@content') != ["back_cover_sec001"]:
            errors.append("back-cover.html: incorrect back-cover title-id")
        if back_cover_document.xpath('//meta[@name="page-section-id"]/@content') != ["134"]:
            errors.append("back-cover.html: incorrect back-cover page-section-id")
        back_cover_image = back_cover_document.xpath(
            '//section[@data-section-id="back_cover_sec001"]//img[@src="images/book-cover-back.png"]'
        )
        if len(back_cover_image) != 1 or not (ROOT / "images/book-cover-back.png").is_file():
            errors.append("back-cover.html: missing original back-cover image")

    catalogs = {}
    for language in LANGS:
        base = ROOT / "content/i18n" / language
        catalogs[language] = {
            "texts": load_json(base / "texts.json"),
            "audios": load_json(base / "audios.json"),
            "audio_dir": base / "audio",
        }

    total_ids = 0
    total_figures = 0
    total_tables = 0
    total_blanks = 0
    hrefs: set[str] = {"index.html", "back-cover.html"}
    for page_number in range(1, 133):
        expected_href = f"pg{page_number:03d}_sec001.html"
        expected_section = f"pg{page_number:03d}_sec001"
        if page_number < len(pages):
            entry = pages[page_number]
            if entry != {
                "section_id": expected_section,
                "href": expected_href,
                "page_number": page_number,
            }:
                errors.append(f"pages.json entry {page_number} is incorrect: {entry}")
        if expected_href in hrefs:
            errors.append(f"duplicate manifest href: {expected_href}")
        hrefs.add(expected_href)

        path = ROOT / expected_href
        if not path.is_file():
            errors.append(f"missing page file: {expected_href}")
            continue
        document = html.fromstring(path.read_text(encoding="utf-8"))
        title_meta = document.xpath('//meta[@name="title-id"]/@content')
        section_meta = document.xpath('//meta[@name="page-section-id"]/@content')
        if title_meta != [expected_section]:
            errors.append(f"{expected_href}: incorrect title-id {title_meta}")
        if section_meta != [str(page_number + 1)]:
            errors.append(f"{expected_href}: incorrect page-section-id {section_meta}")

        article = document.xpath(
            f'//section[@role="article" and @data-section-id="{expected_section}"]'
        )
        if len(article) != 1:
            errors.append(f"{expected_href}: missing unique article section")
            continue
        article = article[0]
        svg = article.xpath('.//*[local-name()="svg" and contains(@class,"adt-source-page-svg")]')
        if len(svg) != 1:
            errors.append(f"{expected_href}: expected one source-page SVG, found {len(svg)}")
        else:
            if svg[0].get("aria-hidden") != "true":
                errors.append(f"{expected_href}: visible SVG is not hidden from assistive technology")
            view_box = svg[0].get("viewBox") or svg[0].get("viewbox")
            if view_box != "0 0 569.244 779.008":
                errors.append(f"{expected_href}: unexpected PDF page geometry")

        semantic = article.xpath('.//div[contains(@class,"adt-semantic-page")]')
        if len(semantic) != 1:
            errors.append(f"{expected_href}: missing unique semantic page layer")
            continue
        semantic = semantic[0]
        page_label = f"Ukurasa wa PDF {page_number} kati ya 132"
        if not semantic.xpath(f'.//p[@aria-label="{page_label}"]'):
            errors.append(f"{expected_href}: missing accessible page number")

        editable = article.xpath('.//input|.//textarea|.//select|.//*[@contenteditable="true"]')
        if editable:
            errors.append(f"{expected_href}: contains {len(editable)} editable controls")

        data_elements = semantic.xpath('.//*[@data-id]')
        data_ids = [element.get("data-id") for element in data_elements]
        total_ids += len(data_ids)
        duplicates = sorted({text_id for text_id in data_ids if data_ids.count(text_id) > 1})
        if duplicates:
            errors.append(f"{expected_href}: duplicate spoken IDs {duplicates}")

        for element, text_id in zip(data_elements, data_ids):
            fallback = " ".join(element.text_content().split())
            for language, catalog in catalogs.items():
                text = catalog["texts"].get(text_id)
                audio = catalog["audios"].get(text_id)
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"{expected_href}:{text_id}: missing {language} text")
                if not audio:
                    errors.append(f"{expected_href}:{text_id}: missing {language} audio mapping")
                elif not (catalog["audio_dir"] / audio).is_file():
                    errors.append(f"{expected_href}:{text_id}: missing {language} audio file {audio}")
            sw_text = catalogs["sw"]["texts"].get(text_id, "")
            if isinstance(sw_text, str) and normalized(fallback) != normalized(sw_text):
                errors.append(f"{expected_href}:{text_id}: inline fallback differs from Swahili text")

        figures = semantic.xpath('.//figure[contains(@class,"adt-semantic-image")]')
        total_figures += len(figures)
        descriptions = [
            normalized(" ".join(figure.text_content().split()))
            for figure in figures
        ]
        if len(descriptions) != len(set(descriptions)):
            errors.append(f"{expected_href}: duplicate image descriptions in reading order")
        for figure in figures:
            captions = figure.xpath('./figcaption[@data-id]')
            if len(captions) != 1 or not figure.get("aria-labelledby"):
                errors.append(f"{expected_href}: image description is not correctly labelled")

        tables = semantic.xpath('.//table[contains(@class,"adt-semantic-table")]')
        total_tables += len(tables)
        for table in tables:
            if not table.xpath('./caption') or not table.xpath('.//tr'):
                errors.append(f"{expected_href}: accessible table lacks caption or rows")
            for cell in table.xpath('.//th|.//td'):
                if not cell.xpath('.//*[@data-id] | .//*[@aria-label]'):
                    errors.append(f"{expected_href}: accessible table contains an empty cell")

        blanks = semantic.xpath('.//*[contains(@class,"adt-semantic-answer-blank")]')
        total_blanks += len(blanks)
        for blank in blanks:
            if blank.get("role") != "img" or not str(blank.get("aria-label", "")).strip():
                errors.append(f"{expected_href}: answer blank lacks a static accessible label")

    toc = load_json(ROOT / "content/toc.json")
    for entry in toc:
        href = str(entry.get("href", "")).split("#", 1)[0]
        if href not in hrefs:
            errors.append(f"toc.json points outside the 132-page spine: {entry.get('href')}")

    offline_source = (ROOT / "assets/offline-preloader.js").read_text(encoding="utf-8")
    start = offline_source.index(OFFLINE_START) + len(OFFLINE_START)
    end = offline_source.index(OFFLINE_END, start)
    inline = json.loads(offline_source[start:end])
    if len(inline.get("./content/pages.json", [])) != 134:
        errors.append("offline preloader does not contain both covers plus 132-page manifest")

    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(
        "PASS: original front and back covers plus 132 PDF-faithful pages; "
        f"{total_ids} spoken content IDs; {total_figures} unique image descriptions; "
        f"{total_tables} accessible tables; {total_blanks} static answer blanks; "
        "audio present in sw and sw-TZ; no editable exercise controls."
    )


if __name__ == "__main__":
    main()
