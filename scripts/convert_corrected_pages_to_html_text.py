#!/usr/bin/env python3
"""Replace PDF-outlined glyphs with positioned, selectable HTML text.

The current corrected SVG remains the source of truth for every illustration,
rule, colour block, and page dimension. Only glyph <use> elements are removed.
Text positions, sizes, weights, styles, and colours are read from the same PDF
used by the corrected page build and rendered as absolutely positioned spans.
"""

from __future__ import annotations

import html
from difflib import SequenceMatcher
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF = Path("/Users/joleen/Desktop/KUHESABU DRS 1 PB/Kuhesabu DRS 1 PB (2023) FINAL WAMO.pdf")
PDFTOHTML = Path(
    "/Users/joleen/.cache/codex-runtimes/codex-primary-runtime/dependencies/"
    "native/poppler/poppler/bin/pdftohtml"
)

GLYPH_USE = re.compile(r'<use\s+[^>]*xlink:href="#glyph-[^"]+"[^>]*/>\s*')
GLYPH_DEF = re.compile(r'<g id="glyph-[^"]+">\s*.*?</g>\s*', re.S)
# Narrow, full-height raster strips are the printed page-edge texture. They
# are decorative and make the responsive HTML page resemble a scanned sheet.
PAGE_EDGE_USE = re.compile(
    r'<use\s+[^>]*xlink:href="#source-(?:5|8|11|14|17)"[^>]*/>\s*'
)
OLD_OVERLAY = re.compile(r'\s*<div class="adt-html-text-layer".*?</div>\s*', re.S)
SVG_END = re.compile(r'(</svg>)(\s*</div>\s*<div class="adt-semantic-page">)', re.S)
BLACK_FILLED_PATH = re.compile(
    r'<path\s+fill-rule="nonzero"\s+fill="rgb\(13\.729858%, 12\.159729%, 12\.548828%\)"[^>]*d="([^"]+)"[^>]*/>'
)

# The corrected build intentionally replaces these printed instructions with
# inclusive wording. Use the same corrected strings and coordinates here.
CORRECTED_SENTENCES = {
    8: (("Chunguza, gusa au sikiliza maelezo, kisha tambua fungu lenye vitu vichache katika ulalo.", 87, 111, 395, 19.0, 16.0), ("Chunguza, gusa au sikiliza maelezo, kisha tambua kundi lenye vitu vingi katika ulalo.", 87, 452, 395, 19.0, 16.0)),
    10: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu picha kisha tamka namba kwa kuonesha idadi ya vidole.", 87, 306, 395, 17.5, 19.0),),
    11: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu picha kisha tamka namba kwa kuonesha idadi ya vidole.", 99, 240, 380, 19.0, 18.5),),
    12: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu vitu vilivyopo katika kila mstari kisha taja idadi.", 87, 126, 395, 19.0, 21.0),),
    13: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu matunda yafuatayo kisha tamka namba inayowakilisha idadi.", 100, 123, 382, 19.0, 18.0),),
    15: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu matunda katika kila mstari kisha andika idadi yake.", 100, 123, 382, 19.0, 18.0),),
    24: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu kila aina ya tunda kisha andika idadi yake.", 87, 124, 395, 19.0, 21.0),),
    30: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu vitu kisha andika idadi yake kwenye nafasi iliyo wazi.", 87, 507, 395, 18.0, 20.0),),
    63: (("Soma, onyesha au wasilisha namba zifuatazo za maneno.", 96, 351, 395, 16.9, 18.0),),
    64: (("Soma, onyesha au wasilisha namba zifuatazo.", 86, 122, 395, 17.7, 20.0), ("Soma, onyesha au wasilisha namba zifuatazo.", 82, 482, 395, 19.0, 21.0)),
    78: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu vitu kisha soma namba katika makumi na mamoja.", 87, 369, 395, 19.0, 21.0),),
    80: (("Chunguza, gusa au sikiliza maelezo, kisha hesabu vitu kisha jaza nafasi zilizo wazi.", 87, 222, 375, 18.0, 17.0), ("Chunguza, gusa au sikiliza maelezo, kisha hesabu vitu kisha jaza tarakimu za makumi na mamoja.", 87, 429, 386, 19.0, 21.0)),
    125: (("Chunguza, gusa au sikiliza maelezo ya maumbo bapa yafuatayo kisha soma majina yake.", 102, 432, 382, 19.0, 21.0),),
    129: (("Chunguza, gusa au sikiliza maelezo ya maumbo yafuatayo, kisha andika herufi zote zinazoonesha maumbo bapa.", 102, 123, 392, 19.0, 21.0),),
}

WATERMARK_WORDS = ("FOR", "ONLINE", "READING", "ONLY")
VERTICAL_ARITHMETIC_PAGES = {
    37, 48, 49, 50, 57,
    92, 93, 94, 98, 99, 100, 101,
    106, 109, 110, 111, 112, 113, 115, 116, 117, 121,
}
WATERMARK_FRAGMENTS = {
    word[start:end]
    for word in WATERMARK_WORDS
    for start in range(len(word))
    for end in range(start + 1, len(word) + 1)
}

TEXT_CORRECTIONS = {
    (2, "Simu: +255 735 041 170 +255 735 041 168"): "Simu: +255 735 041 170 / +255 735 041 168",
    (18, "Soma namba zifuatazo kwa sauti."): "Soma / Tambua namba zifuatazo kwa sauti.",
    (19, "Tuandike namba moja hadi tisa l"): "Tuandike namba moja hadi tisa.",
    (25, "Soma namba zifuatazo kwa sauti."): "Soma namba zifuatazo kwa sauti/kwa lugha ya alama.",
    (40, "2. Soma swali linaloonekana kwenye skirini"): "2. Soma / Tambua swali linaloonekana kwenye",
    (40, "na ulielewe."): "skirini na ulielewe.",
    (51, "2. Soma swali linaloonekana kwenye skirini na"): "2. Soma / Tambua swali linaloonekana kwenye skirini",
    (51, "ulielewe."): "na ulielewe.",
    (55, "4 + 6"): "4 +",
    (55, "1 + 9 = 10"): "1 + 9 =",
    (65, "Soma namba zifuatazo kwa sauti."): "Soma / Tambua namba zifuatazo kwa sauti.",
    (66, "Soma namba zifuatazo kwa sauti."): "Soma / Tambua namba zifuatazo kwa sauti.",
    (90, "30 + 8"): "30 + 8 =",
    (90, "61 + 7"): "61 + 7 =",
    (90, "28 + 11"): "28 + 11 =",
    (90, "8"): "8 + 91 =",
    (112, "Andika 4 katika nafasi 1 13"): "Andika 4 katika nafasi",
    (113, "mamoja 10. Yamebaki 8 0 – 44 ="): "mamoja 10. Yamebaki",
    (113, "Andika 6 katika nafasi 7 10"): "Andika 6 katika nafasi",
}


def page_path(number: int) -> Path:
    return ROOT / ("index.html" if number == 1 else f"pg{number:03d}_sec001.html")


def extract_pdf_xml(first_page: int = 1, last_page: int = 132) -> tuple[ET.Element, ET.Element]:
    with tempfile.TemporaryDirectory(prefix="kuhesabu-html-text-") as temp:
        target = Path(temp) / "book.xml"
        bbox_target = Path(temp) / "book-bbox.html"
        subprocess.run(
            [str(PDFTOHTML), "-f", str(first_page), "-l", str(last_page), "-xml", "-hidden", "-nodrm", str(PDF), str(target)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pdftotext = PDFTOHTML.with_name("pdftotext")
        subprocess.run(
            [str(pdftotext), "-f", str(first_page), "-l", str(last_page), "-bbox-layout", str(PDF), str(bbox_target)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ET.fromstring(target.read_bytes()), ET.fromstring(bbox_target.read_bytes())


def font_family(pdf_family: str) -> str:
    if "sassoon" in pdf_family.casefold():
        return "'ADT Sassoon Primary', sans-serif"
    if "merriweather" in pdf_family.casefold():
        return "Merriweather, serif"
    return "'Atkinson Hyperlegible', Arial, sans-serif"


def corrected_spans(page_number: int, width: float, height: float) -> list[str]:
    spans = []
    for text, x, y, box_width, font_size, leading in CORRECTED_SENTENCES.get(page_number, ()):
        words = text.split()
        lines, current = [], ""
        # Match the wrapping logic used by the corrected PDF build closely.
        # These early exercise pages have shallow instruction boxes. Their
        # Sassoon text fits comfortably at a slightly tighter average width,
        # which avoids stacking three crowded lines where two will fit.
        average_character_width = font_size * (0.40 if page_number in {8, 10, 12, 13} else 0.48)
        max_chars = max(1, int(box_width / average_character_width))
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > max_chars:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        if page_number == 8:
            relaxed_leading = font_size * 0.98
        elif page_number in {10, 12, 13}:
            relaxed_leading = max(leading, font_size * 1.08)
        else:
            relaxed_leading = leading
        for index, line in enumerate(lines):
            top = y + index * relaxed_leading
            style = (
                f"left:{x / width * 100:.6f}%;top:{top / height * 100:.6f}%;"
                f"width:{box_width / width * 100:.6f}%;font-size:{font_size / width * 100:.6f}cqw;"
                f"line-height:{relaxed_leading / width * 100:.6f}cqw;color:#231f20;"
                "font-family:'ADT Sassoon Primary',sans-serif"
            )
            spans.append(f'<span class="adt-html-text" style="{style}">{html.escape(line)}</span>')
    return spans


def html_text_layer(style_page: ET.Element, bbox_page: ET.Element, page_number: int, fonts: dict[str, dict[str, str]]) -> str:
    width = float(bbox_page.attrib["width"])
    height = float(bbox_page.attrib["height"])
    style_nodes = list(style_page.findall("text"))
    spans = []
    masks = []
    corrected = page_number in CORRECTED_SENTENCES
    for line in bbox_page.findall(".//{*}line"):
        words = ["".join(word.itertext()).strip() for word in line.findall("{*}word")]
        text = " ".join(word for word in words if word)
        normalized = " ".join(text.split())
        normalized = TEXT_CORRECTIONS.get((page_number, normalized), normalized)
        text = normalized
        if not normalized:
            continue
        if page_number == 2 and normalized == "/":
            continue
        if any(mark in normalized.upper() for mark in ("FOR ONLINE", "READING ONLY")) or normalized.upper() in {"READING", "ONLY", "ONLINE"}:
            continue
        # The corrected build covered the original instruction in these bands.
        top = float(line.attrib["yMin"])
        if (
            page_number == 113
            and (
                # The exercise heading is redrawn once below so its white
                # lettering does not stack on top of itself.
                (0.60 <= top / height <= 0.64 and normalized == "Zoezi la 5")
                # Every grid question is likewise rebuilt as one clean HTML
                # row.  Skip the extracted copies (including a lone "=").
                or 0.69 <= top / height <= 0.87
            )
        ):
            continue
        if (
            page_number == 90
            and 0.20 <= top / height <= 0.48
            and normalized in {"=", "+ 91 ="}
        ):
            continue
        if (
            page_number == 63
            and 0.49 <= top / height <= 0.86
            and re.match(r"^\d+\.", normalized)
        ):
            continue
        if (
            page_number == 64
            and 0.65 <= top / height <= 0.86
            and re.match(r"^\d+\.", normalized)
        ):
            continue
        if (
            page_number == 83
            and 0.20 <= top / height <= 0.80
            and (
                re.fullmatch(r"\d+\.", normalized)
                or all(token.isdigit() for token in normalized.split())
                or re.fullmatch(r"\d+\.\s+(?:\d+\s*)+", normalized)
            )
        ):
            continue
        if page_number == 102 and normalized in {"Shilingi 15", "+ Shilingi 50", "Shilingi 65"}:
            continue
        if page_number == 119 and normalized in {"Shilingi 50", "– Shilingi 10", "Shilingi 40"}:
            continue
        if corrected and any(y - 8 <= top <= y + 60 for _, _, y, _, _, _ in CORRECTED_SENTENCES[page_number]):
            continue
        left = float(line.attrib["xMin"])
        right = float(line.attrib["xMax"])
        numeric_sequence = (
            len(normalized.split()) >= 2
            and all(token.isdigit() for token in normalized.split())
        )
        if numeric_sequence:
            right = left + (right - left) / 0.9
        if page_number == 25 and normalized == "Soma namba zifuatazo kwa sauti/kwa lugha ya alama.":
            right = min(width * 0.94, left + width * 0.76)
        if page_number in {18, 65, 66} and normalized == "Soma / Tambua namba zifuatazo kwa sauti.":
            right = min(width * 0.94, left + width * 0.62)
        if page_number in {40, 51} and "Soma / Tambua swali" in normalized:
            right = min(width * 0.94, left + width * 0.79)
        if page_number == 90 and normalized in {"30 + 8 =", "61 + 7 =", "28 + 11 =", "8 + 91 ="}:
            right = left + width * 0.18496096
        if page_number == 118 and re.fullmatch(r"–\s*(?:26|79)", normalized):
            # Keep the subtraction sign in its existing operator column while
            # right-aligning 26/79 directly beneath 40/80.
            right += width * 0.0042
        if page_number == 124 and re.fullmatch(r"[+–−-]\s*\d+", normalized):
            # The extracted operator rows finish slightly before the top
            # numbers. Widen their flex row so every lower value shares the
            # same right-hand digit column while the operator stays fixed.
            lower_value = re.sub(r"\D", "", normalized)
            right += width * (0.00355 if len(lower_value) == 1 else 0.0042)
        bottom = float(line.attrib["yMax"])
        compact = normalized.upper().replace(" ", "")
        watermark_axis = 620 - 0.85 * ((left + right) / 2)
        if compact in WATERMARK_FRAGMENTS and abs(((top + bottom) / 2) - watermark_axis) < 135:
            continue
        center_x = ((left + right) / 2) * 1.5
        center_y = ((top + bottom) / 2) * 1.5
        candidates = []
        for node in style_nodes:
            node_left = float(node.attrib["left"])
            node_top = float(node.attrib["top"])
            node_right = node_left + float(node.attrib.get("width", "0"))
            node_bottom = node_top + float(node.attrib.get("height", "0"))
            horizontal_gap = 0 if node_left <= center_x <= node_right else min(abs(center_x - node_left), abs(center_x - node_right))
            vertical_gap = 0 if node_top <= center_y <= node_bottom else min(abs(center_y - node_top), abs(center_y - node_bottom))
            node_text = " ".join("".join(node.itertext()).split())
            similarity = SequenceMatcher(None, normalized.casefold(), node_text.casefold()).ratio()
            candidates.append((horizontal_gap + vertical_gap * 2 - similarity * 1000, node))
        node = min(candidates, key=lambda item: item[0])[1] if candidates else None
        font = fonts.get(node.attrib.get("font", ""), {}) if node is not None else {}
        if float(font.get("opacity", "1")) < 0.9:
            continue
        text_width = right - left
        size = float(font.get("size", (bottom - top) * 1.5)) / 1.5
        color = font.get("color", "#231f20")
        if page_number in {130, 131, 132} and re.fullmatch(r"\d+\.", normalized):
            color = "#d11f27"
        if page_number == 90 and normalized == "8 + 91 =":
            color = "#231f20"
        force_regular = False
        if (
            page_number == 55
            and normalized in {"4", "6"}
            and left / width >= 0.70
            and top / height >= 0.70
        ):
            color = "#231f20"
        if (
            page_number == 70
            and normalized in {"4", "6"}
            and 0.70 <= top / height <= 0.85
            and color.casefold() == "#ffffff"
        ):
            color = "#231f20"
            size = width * 0.03513432
            force_regular = True
        source_bold = node is not None and (
            node.find("b") is not None or node.find(".//b") is not None
        )
        emphasis_color = color.casefold() in {"#d11f27", "#00aaaf", "#00acef", "#ffffff"}
        semantic_bold = emphasis_color and any(character.isalpha() for character in normalized)
        bold = source_bold or semantic_bold
        if force_regular:
            bold = False
        italic = node is not None and node.find("i") is not None
        style = (
            f"left:{left / width * 100:.6f}%;top:{top / height * 100:.6f}%;"
            f"width:{max(text_width, 1) / width * 100:.6f}%;font-size:{size / width * 100:.6f}cqw;"
            f"line-height:{size * 1.08 / width * 100:.6f}cqw;color:{color};"
            f"font-family:{font_family(font.get('family', ''))};"
            f"font-weight:{'700' if bold else '400'};font-style:{'italic' if italic else 'normal'}"
        )
        if (
            page_number in VERTICAL_ARITHMETIC_PAGES
            and normalized.isdigit()
            and 0.08 <= top / height <= 0.89
            and color.casefold() == "#231f20"
        ):
            if len(normalized) >= 2:
                style += ";transform:translateX(-0.72cqw) scale(1,0.78)"
            else:
                style += ";transform:scale(1,0.78)"
        if page_number == 109 and normalized == "65":
            style += ";transform:translateX(-1.3cqw) scale(1,0.78)"
        if page_number == 109 and normalized == "5":
            style += ";transform:translateX(-1.65cqw) scale(1,0.78)"
        classes = ["adt-html-text"]
        if normalized.startswith("Zoezi la "):
            classes.append("adt-exercise-label")
            if page_number == 25:
                masks.append(
                    f'<span class="adt-page25-exercise-card" '
                    f'style="left:{left / width * 100 - 1.9:.6f}%;'
                    f'top:{top / height * 100 - 0.3:.6f}%;width:18.5%;height:3.6%"></span>'
                )
            if page_number == 52 and normalized in {"Zoezi la 1", "Zoezi la 2"}:
                masks.append(
                    f'<span class="adt-page52-exercise-label-mask" '
                    f'style="left:{left / width * 100 - 1.8:.6f}%;'
                    f'top:{top / height * 100 - 0.2:.6f}%;width:20.2%;height:3.8%"></span>'
                )
        if page_number == 1 and normalized == "Kitabu cha Mwanafunzi":
            classes.append("adt-source-text-mask")
        if page_number == 19 and normalized in set("123456789") and 25 <= left / width * 100 <= 31:
            classes.append("adt-page19-trace-number")
            masks.append(
                f'<span class="adt-number-mask" style="left:{left / width * 100 - 0.7:.6f}%;'
                f'top:{top / height * 100 - 0.2:.6f}%;width:6%;height:5.4%"></span>'
            )
        display_html = html.escape(text)
        page46_horizontal_question = (
            page_number == 46
            and top / height >= 0.68
            and (re.match(r"^[1-8]\.\s", text) or text in {"- 1 =", "9 =", "6 =", "0 ="})
        )
        page47_horizontal_question = (
            page_number == 47
            and 0.10 <= top / height <= 0.50
            and (
                re.match(r"^(?:9|1[0-9]|2[0-6])\.(?:\s|$)", text)
                or re.fullmatch(r"-\s+\d+\s+=", text)
            )
        )
        numbered_math_fragment = re.match(r"^\d+\.\s+\d+(?:\s|$)", text) is not None
        numeric_sequence_fragment = (
            len(text.split()) >= 2
            and all(token.isdigit() for token in text.split())
        )
        vertical_question = re.fullmatch(r"[+–−-]\s+\d+", text) is not None
        if (
            page46_horizontal_question
            or page47_horizontal_question
            or numbered_math_fragment
            or numeric_sequence_fragment
            or vertical_question
        ):
            token_spans = []
            for token in text.split():
                if numeric_sequence_fragment:
                    token_color = color
                else:
                    token_color = "#d11f27" if re.fullmatch(r"\d+\.", token) else "#231f20"
                token_spans.append(
                    f'<span style="color:{token_color};font-family:inherit;font-size:inherit;'
                    f'font-weight:inherit">{html.escape(token)}</span>'
                )
            display_html = (
                '<span style="display:flex;width:100%;align-items:baseline;justify-content:space-between;'
                'font-family:inherit;font-size:inherit;font-weight:inherit">'
                + "".join(token_spans)
                + "</span>"
            )
        if page_number == 2:
            for label in ("Simu:", "Baruapepe:", "Tovuti:"):
                if text.startswith(label):
                    display_html = f"<strong>{html.escape(label)}</strong>{html.escape(text[len(label):])}"
                    break
        if page_number == 112 and normalized.startswith("3. Toa mamoja:"):
            display_html = (
                '<span style="color:#d11f27;font-family:inherit;font-size:inherit;font-weight:inherit">3.</span>'
                + html.escape(normalized[2:])
            )
        if page_number == 113 and re.match(r"^[34]\. Toa ", normalized):
            display_html = (
                f'<span style="color:#d11f27;font-family:inherit;font-size:inherit;font-weight:inherit">{normalized[:2]}</span>'
                + html.escape(normalized[2:])
            )
        if (
            page_number in {130, 131, 132}
            and re.match(r"^\d+\.\s", normalized)
            and int(normalized.split(".", 1)[0]) <= 20
            and not numbered_math_fragment
            and (left / width < 0.22 or 0.47 <= left / width <= 0.57)
        ):
            label, remainder = normalized.split(".", 1)
            display_html = (
                f'<span style="color:#d11f27;font-family:inherit;font-size:inherit;'
                f'font-weight:inherit">{label}.</span>'
                + html.escape(remainder)
            )
        spans.append(f'<span class="{" ".join(classes)}" style="{style}">{display_html}</span>')

    if page_number == 55:
        example_number_style = (
            "top:44.975071%;width:5.8%;font-size:3.513432cqw;line-height:3.794506cqw;"
            "color:#231f20;font-family:'ADT Sassoon Primary', sans-serif;font-weight:400;"
            "font-style:normal;text-align:center"
        )
        spans.append(
            f'<span class="adt-html-text" style="left:25.53%;{example_number_style}">6</span>'
        )
        spans.append(
            f'<span class="adt-html-text" style="left:70.84%;{example_number_style}">10</span>'
        )
    if page_number == 63:
        left_questions = [
            "kumi na moja", "kumi na saba", "ishirini na tatu", "ishirini na tano",
            "thelathini na tatu", "thelathini na nane", "arobaini na tano",
            "arobaini na tisa", "tisini na sita",
        ]
        right_questions = [
            "hamsini na mbili", "hamsini na sita", "sitini", "sitini na nne",
            "sabini na tatu", "sabini na tisa", "themanini na mbili",
            "themanini na moja", "tisini na nane",
        ]
        for row, (left_text, right_text) in enumerate(zip(left_questions, right_questions)):
            row_top = 49.497651 + row * 4.336320
            common = (
                f"top:{row_top:.6f}%;font-size:3.630546cqw;line-height:3.920990cqw;"
                "font-family:'ADT Sassoon Primary', sans-serif;font-weight:400;font-style:normal"
            )
            spans.extend(
                [
                    f'<span class="adt-html-text" style="left:17.498191%;width:3.8%;color:#d11f27;{common}">{row + 1}.</span>',
                    f'<span class="adt-html-text" style="left:21.6%;width:26%;color:#231f20;{common}">{html.escape(left_text)}</span>',
                    f'<span class="adt-html-text" style="left:51.262451%;width:5.1%;color:#d11f27;{common}">{row + 10}.</span>',
                    f'<span class="adt-html-text" style="left:57.0%;width:28%;color:#231f20;{common}">{html.escape(right_text)}</span>',
                ]
            )
    if page_number == 64:
        left_questions = [
            "4, 20, 35, 18", "37, 44, 10, 29", "18, 32, 79, 80",
            "88, 99, 43, 50", "12, 45, 60, 70",
        ]
        right_questions = [
            "22, 27, 35, 92", "92, 86, 31, 90", "99, 18, 30, 53",
            "11, 18, 61, 15", "17, 53, 41, 92",
        ]
        for row, (left_text, right_text) in enumerate(zip(left_questions, right_questions)):
            row_top = 66.399557 + row * 4.336320
            common = (
                f"top:{row_top:.6f}%;font-size:3.630546cqw;line-height:3.920990cqw;"
                "font-family:'ADT Sassoon Primary', sans-serif;font-weight:400;font-style:normal"
            )
            spans.extend(
                [
                    f'<span class="adt-html-text" style="left:14.968498%;width:3.8%;color:#d11f27;{common}">{row + 1}.</span>',
                    f'<span class="adt-html-text" style="left:20.2%;width:27%;color:#231f20;{common}">{html.escape(left_text)}</span>',
                    f'<span class="adt-html-text" style="left:50.317178%;width:5.1%;color:#d11f27;{common}">{row + 6}.</span>',
                    f'<span class="adt-html-text" style="left:57.872508%;width:24%;color:#231f20;{common}">{html.escape(right_text)}</span>',
                ]
            )

    if page_number == 83:
        # Keep the red question labels in their original table column, while
        # centring each black digit exactly over the vertical guide it names.
        rows = [
            (21.646671, 1, ("1", "9"), (148.335938, 168.976562), 6, ("3", "0"), (348.687500, 369.328125)),
            (34.677141, 2, ("1", "0"), (157.703125, 178.343750), 7, ("1", "6"), (346.925781, 367.566406)),
            (47.707610, 3, ("3", "4"), (148.335938, 168.976562), 8, ("3",), (346.925781,)),
            (60.738080, 4, ("2", "3"), (148.335938, 168.976562), 9, ("9",), (346.925781,)),
            (73.768549, 5, ("4", "5"), (148.335938, 168.976562), 10, ("6",), (346.925781,)),
        ]
        common = (
            "font-size:3.513432cqw;line-height:3.794506cqw;"
            "font-family:'ADT Sassoon Primary', sans-serif;font-weight:400;font-style:normal"
        )
        digit_width = 12.0
        for top_pct, left_number, left_digits, left_guides, right_number, right_digits, right_guides in rows:
            spans.extend(
                [
                    f'<span class="adt-html-text" style="left:19.367442%;top:{top_pct:.6f}%;width:2.659668%;color:#d11f27;{common}">{left_number}.</span>',
                    f'<span class="adt-html-text" style="left:{53.272674 if right_number == 10 else 54.147518:.6f}%;top:{top_pct:.6f}%;width:{5.0 if right_number == 10 else 2.659668:.6f}%;color:#d11f27;{common}">{right_number}.</span>',
                ]
            )
            for digit, guide_x in zip(left_digits + right_digits, left_guides + right_guides):
                digit_left = (guide_x - digit_width * 0.45) / width * 100
                spans.append(
                    f'<span class="adt-html-text" style="left:{digit_left:.6f}%;top:{top_pct:.6f}%;'
                    f'width:{digit_width / width * 100:.6f}%;text-align:center;color:#231f20;{common}">{digit}</span>'
                )

    if page_number == 102:
        money_rows = [
            (73.858601, "", "15"),
            (77.448669, "+", "50"),
            (81.384352, "", "65"),
        ]
        for row_top, sign, amount in money_rows:
            spans.append(
                f'<span class="adt-html-text" style="left:18.077888%;top:{row_top:.6f}%;'
                'width:23%;font-size:3.630546cqw;line-height:3.920990cqw;color:#231f20;'
                "font-family:'ADT Sassoon Primary', sans-serif;font-weight:400;font-style:normal;"
                'display:grid;grid-template-columns:1.2em 1fr 2em;column-gap:.2em;align-items:baseline">'
                f'<span>{sign}</span><span>Shilingi</span><span style="text-align:right;'
                f'font-variant-numeric:tabular-nums">{amount}</span></span>'
            )

    if page_number == 119:
        money_rows = [
            (71.190850, "", "50"),
            (74.417877, "–", "10"),
            (77.988841, "", "40"),
        ]
        for row_top, sign, amount in money_rows:
            spans.append(
                f'<span class="adt-html-text" style="left:20.554936%;top:{row_top:.6f}%;'
                'width:19.604128%;font-size:3.630546cqw;line-height:3.920990cqw;'
                "color:#231f20;font-family:'ADT Sassoon Primary', sans-serif;"
                'font-weight:400;font-style:normal;display:grid;'
                'grid-template-columns:1.2em 1fr 2em;column-gap:.2em;align-items:baseline">'
                f'<span>{sign}</span><span>Shilingi</span><span style="text-align:right;'
                f'font-variant-numeric:tabular-nums">{amount}</span></span>'
            )

    if page_number == 129:
        # Four shape labels were lost where their source glyphs intersected
        # the diagonal watermark. Restore them at their exact PDF positions.
        label_style = (
            "font-size:3.162089cqw;line-height:3.415056cqw;color:#d11f27;"
            "font-family:'ADT Sassoon Primary', sans-serif;font-weight:700;"
            "font-style:normal"
        )
        missing_labels = (
            ("d", 61.178133, 31.691138, 1.631638),
            ("e", 74.828851, 31.691138, 1.385029),
            ("g", 37.134942, 42.316099, 1.577882),
            ("i", 60.583495, 42.316099, 0.711470),
        )
        for label, left_pct, top_pct, width_pct in missing_labels:
            spans.append(
                f'<span class="adt-html-text" style="left:{left_pct:.6f}%;'
                f'top:{top_pct:.6f}%;width:{width_pct:.6f}%;{label_style}">{label}</span>'
            )

    if page_number == 113:
        # Restore the two pieces that were joined to neighbouring text during
        # extraction in the worked example's right-hand column: the equation
        # in step 2 and the borrowed 7 tens / 10 ones in step 3.
        worked_equation_style = (
            "width:15.151394%;font-size:3.044974cqw;line-height:3.288572cqw;"
            "color:#231f20;font-family:'ADT Sassoon Primary', sans-serif;"
            "font-weight:400;font-style:normal"
        )
        spans.append(
            f'<span class="adt-html-text" style="left:57.751860%;top:20.214000%;'
            f'{worked_equation_style}">8 0 − 44 =</span>'
        )
        spans.append(
            '<span class="adt-html-text" style="left:57.751860%;top:33.920000%;'
            'width:4.613136%;font-size:2.342288cqw;line-height:2.529671cqw;'
            "color:#d11f27;font-family:'ADT Sassoon Primary', sans-serif;"
            'font-weight:400;font-style:normal"><span style="display:flex;width:100%;'
            'align-items:baseline;justify-content:space-between;font-family:inherit;'
            'font-size:inherit;font-weight:inherit"><span>7</span><span>10</span>'
            '</span></span>'
        )
        rows = [
            ("1.", "47 − 18 =", "5.", "33 − 27 ="),
            ("2.", "24 − 7 =", "6.", "80 − 8 ="),
            ("3.", "52 − 17 =", "7.", "36 − 18 ="),
            ("4.", "80 − 12 =", "8.", "54 − 29 ="),
        ]
        common = (
            "font-size:3.630546cqw;line-height:3.920990cqw;"
            "font-family:'ADT Sassoon Primary', sans-serif;font-weight:400;font-style:normal"
        )
        for row, (left_label, left_question, right_label, right_question) in enumerate(rows):
            row_top = 70.275 + row * 4.1105
            spans.extend(
                [
                    f'<span class="adt-html-text" style="left:19.894%;top:{row_top:.6f}%;width:3.5%;color:#d11f27;{common}">{left_label}</span>',
                    f'<span class="adt-html-text" style="left:25.270%;top:{row_top:.6f}%;width:20.5%;color:#231f20;{common}">{left_question}</span>',
                    f'<span class="adt-html-text" style="left:52.868%;top:{row_top:.6f}%;width:3.5%;color:#d11f27;{common}">{right_label}</span>',
                    f'<span class="adt-html-text" style="left:59.044%;top:{row_top:.6f}%;width:20.5%;color:#231f20;{common}">{right_question}</span>',
                ]
            )

    # The first row label is present in the semantic table but its outlined
    # source glyph is absent from the visible artwork. Restore it beside row 1,
    # matching the position, colour, and typography of the visible "2." label.
    if page_number == 80:
        spans.append(
            '<span class="adt-html-text" style="left:16.540411%;top:62.633542%;'
            'width:2.659668%;font-size:3.513432cqw;line-height:3.794506cqw;'
            "color:#d11f27;font-family:'ADT Sassoon Primary', sans-serif;"
            'font-weight:400;font-style:normal">1.</span>'
        )

    spans.extend(corrected_spans(page_number, width, height))
    special_masks = ""
    if page_number == 1:
        special_masks += '<span class="adt-cover-subtitle-mask" aria-hidden="true"></span>'
    if page_number == 25:
        special_masks += '<span class="adt-source-instruction-mask" aria-hidden="true"></span>'
    if page_number == 113:
        # Cover only the printed text inside each grid cell, preserving every
        # turquoise border, then redraw the questions with comfortable padding.
        special_masks += (
            '<span aria-hidden="true" style="position:absolute;left:17.95%;top:60.62%;'
            'width:16.2%;height:3.45%;background:#00aaaf;z-index:0"></span>'
        )
        for row in range(4):
            mask_top = (542.4 + row * 31.98) / height * 100
            mask_height = 30.9 / height * 100
            for x1, x2 in ((103.7, 137.6), (138.4, 286.6), (287.5, 329.6), (330.4, 477.0)):
                special_masks += (
                    f'<span aria-hidden="true" style="position:absolute;left:{x1 / width * 100:.6f}%;'
                    f'top:{mask_top:.6f}%;width:{(x2 - x1) / width * 100:.6f}%;'
                    f'height:{mask_height:.6f}%;background:#ffffff;z-index:0"></span>'
                )
        spans.append(
            '<span class="adt-html-text adt-exercise-label" style="left:18.083%;top:60.821%;'
            'width:15.8%;font-size:3.396317cqw;line-height:3.668023cqw;color:#ffffff;'
            "font-family:'ADT Sassoon Primary', sans-serif;font-weight:700;font-style:normal\">Zoezi la 5</span>"
        )
    if page_number == 117:
        # Hide the outlined source copy of the final 8; the accessible HTML
        # heading above it remains the single visible "Zoezi la 8" label.
        special_masks += (
            '<span aria-hidden="true" style="position:absolute;left:17.70%;top:40.70%;'
            'width:16.25%;height:3.45%;background:#00aaaf;z-index:0"></span>'
        )
    return (
        f'<div class="adt-html-text-layer" aria-hidden="true" '
        f'style="--adt-source-width:{width};--adt-source-height:{height}">'
        + special_masks
        + "".join(masks)
        + "".join(spans)
        + "</div>"
    )


def convert_page(path: Path, page_number: int, style_page: ET.Element, bbox_page: ET.Element, fonts: dict[str, dict[str, str]]) -> None:
    source = path.read_text(encoding="utf-8")
    source = OLD_OVERLAY.sub("", source)
    source = GLYPH_USE.sub("", source)
    source = GLYPH_DEF.sub("", source)
    source = PAGE_EDGE_USE.sub("", source)
    if page_number == 102:
        # End both money-example rules at the right edge of the fixed amount
        # column (15, 50, 65).
        source = source.replace("217.027344", "220.750000")
    if page_number == 83:
        # Each place-value guide begins with a black vertical rule. Extend its
        # top to meet the digit directly above it, for every question in the
        # exercise. Other black artwork and table rules are left untouched.
        extensions = []
        for match in BLACK_FILLED_PATH.finditer(source):
            start = re.match(
                r"M ([0-9.]+) ([0-9.]+) L ([0-9.]+) ([0-9.]+)",
                match.group(1),
            )
            if not start:
                continue
            x1, y1, x2, y2 = map(float, start.groups())
            if abs(x1 - x2) < 0.01 and 20 <= y2 - y1 <= 55:
                extensions.append(
                    f'<rect x="{x1:.6f}" y="{y1 - 9:.6f}" width="1" height="10" '
                    'fill="rgb(13.729858%, 12.159729%, 12.548828%)"/>'
                )
        if extensions:
            source = source.replace("</svg>", "".join(extensions) + "</svg>", 1)
    layer = html_text_layer(style_page, bbox_page, page_number, fonts)
    updated, count = SVG_END.subn(r"\1\n" + layer + r"\2", source, count=1)
    if count != 1:
        raise RuntimeError(f"Could not insert HTML text layer into {path.name}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    first_page = last_page = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if len(sys.argv) == 1:
        last_page = 132
    style_root, bbox_root = extract_pdf_xml(first_page, last_page)
    style_pages = style_root.findall("page")
    bbox_pages = bbox_root.findall(".//{*}page")
    fonts = {font.attrib["id"]: font.attrib for font in style_root.findall(".//fontspec")}
    expected_pages = last_page - first_page + 1
    if len(style_pages) != expected_pages or len(bbox_pages) != expected_pages:
        raise RuntimeError(
            f"Expected {expected_pages} PDF pages, found {len(style_pages)} style and {len(bbox_pages)} text pages"
        )
    for number, (style_page, bbox_page) in enumerate(zip(style_pages, bbox_pages), first_page):
        convert_page(page_path(number), number, style_page, bbox_page, fonts)
    print(f"Converted outlined text to positioned HTML on pages {first_page}-{last_page}.")


if __name__ == "__main__":
    main()
