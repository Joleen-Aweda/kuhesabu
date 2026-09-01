#!/usr/bin/env python3
"""Insert the original front and back covers around the 132-page book."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

COVER_TEXTS = {
    "cover_n0000": "Jalada la mbele la kitabu.",
    "cover_n0001": "Kuhesabu",
    "cover_n0002": "Kitabu cha Mwanafunzi",
    "cover_n0003": "Darasa la Kwanza",
    "cover_n0004": "Taasisi ya Elimu Tanzania",
    "cover_n0005": "Mali ya Serikali ya Jamhuri ya Muungano wa Tanzania, hakiuzwi.",
    "cover_im001": (
        "Jalada la mbele la kitabu cha Kuhesabu, Kitabu cha Mwanafunzi, Darasa la Kwanza. "
        "Lina picha ya baiskeli, mkoba mmoja na mpira mmoja, mikoba miwili na mipira miwili, "
        "pamoja na mikoba mitatu na mipira mitatu."
    ),
}

BACK_COVER_TEXTS = {
    "backcover_n0000": "Jalada la nyuma la kitabu.",
    "backcover_n0001": "Vitabu vingine kutoka Taasisi ya Elimu Tanzania",
    "backcover_n0002": "Darasa la Kwanza",
    "backcover_n0003": "Utamaduni, Sanaa na Michezo. Kitabu cha Mwanafunzi, Darasa la Kwanza.",
    "backcover_n0004": "Kusoma. Kitabu cha Mwanafunzi, Darasa la Kwanza.",
    "backcover_n0005": "Afya na Mazingira. Kitabu cha Mwanafunzi, Darasa la Kwanza.",
    "backcover_n0006": "Kuandika. Kitabu cha Mwanafunzi, Darasa la Kwanza.",
    "backcover_n0007": "Learn English. Pupil's Book. Standard One, Kiswahili Medium Schools.",
    "backcover_n0008": "ISBN: 978-9987-09-901-6",
    "backcover_n0009": "Mali ya Serikali ya Jamhuri ya Muungano wa Tanzania, hakiuzwi.",
    "backcover_im001": (
        "Jalada la nyuma linaonyesha vitabu vingine vya Darasa la Kwanza kutoka Taasisi ya "
        "Elimu Tanzania: Utamaduni, Sanaa na Michezo; Kusoma; Afya na Mazingira; Kuandika; "
        "na Learn English. Pia lina nembo ya Taasisi ya Elimu Tanzania na msimbo pau wa ISBN."
    ),
}


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    index_path = ROOT / "index.html"
    page_one_path = ROOT / "pg001_sec001.html"

    if not page_one_path.exists():
        original_page_one = index_path.read_text(encoding="utf-8")
        page_one_path.write_text(original_page_one, encoding="utf-8")

    cover_html = """<!DOCTYPE html>
<html lang="sw">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kuhesabu Kitabu cha Mwanafunzi - Jalada</title>
  <meta name="title-id" content="cover_sec001" />
  <meta name="page-section-id" content="1" />
  <link href="./content/tailwind_output.css?v=13" rel="stylesheet">
  <link href="./content/page-faithful.css?v=13" rel="stylesheet">
  <link href="./assets/libs/fontawesome/css/all.min.css" rel="stylesheet">
  <link href="./assets/fonts.css" rel="stylesheet">
</head>
<body class="adt-faithful-book-page font-sans">
  <main>
    <div id="content" class="opacity-0">
      <section role="article" data-section-type="page_faithful" data-section-id="cover_sec001" class="adt-page-shell">
        <div class="adt-page-visual">
          <img src="images/book-cover-front.png" alt="" aria-hidden="true" style="display:block;width:100%;height:auto" />
        </div>
        <div class="adt-semantic-page">
          <p data-id="cover_n0000">Jalada la mbele la kitabu.</p>
          <ol class="adt-page-reading-order">
            <li><h1 data-id="cover_n0001">Kuhesabu</h1></li>
            <li><h2 data-id="cover_n0002">Kitabu cha Mwanafunzi</h2></li>
            <li><p data-id="cover_n0003">Darasa la Kwanza</p></li>
            <li><figure class="adt-semantic-image" role="img" aria-labelledby="cover-image-caption"><figcaption id="cover-image-caption" data-id="cover_im001">Jalada la mbele la kitabu cha Kuhesabu, Kitabu cha Mwanafunzi, Darasa la Kwanza. Lina picha ya baiskeli, mkoba mmoja na mpira mmoja, mikoba miwili na mipira miwili, pamoja na mikoba mitatu na mipira mitatu.</figcaption></figure></li>
            <li><p data-id="cover_n0004">Taasisi ya Elimu Tanzania</p></li>
            <li><p data-id="cover_n0005">Mali ya Serikali ya Jamhuri ya Muungano wa Tanzania, hakiuzwi.</p></li>
            <li><p data-id="adt_end_of_page">Mwisho wa ukurasa.</p></li>
          </ol>
        </div>
      </section>
    </div>
  </main>
  <div class="relative z-50" id="interface-container"></div>
  <div class="relative z-50" id="nav-container"></div>
  <script src="./assets/offline-preloader.js?v=99"></script>
  <script src="./assets/scorm.js"></script>
  <script src="./assets/enable-image-descriptions.js"></script>
  <script src="./assets/base.bundle.local.js?v=99"></script>
  <script src="./assets/sign-video-fallback.js?v=100" defer></script>
</body>
</html>
"""
    index_path.write_text(cover_html, encoding="utf-8")

    back_cover_path = ROOT / "back-cover.html"
    back_cover_html = """<!DOCTYPE html>
<html lang="sw">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kuhesabu Kitabu cha Mwanafunzi - Jalada la Nyuma</title>
  <meta name="title-id" content="back_cover_sec001" />
  <meta name="page-section-id" content="134" />
  <link href="./content/tailwind_output.css?v=13" rel="stylesheet">
  <link href="./content/page-faithful.css?v=13" rel="stylesheet">
  <link href="./assets/libs/fontawesome/css/all.min.css" rel="stylesheet">
  <link href="./assets/fonts.css" rel="stylesheet">
</head>
<body class="adt-faithful-book-page font-sans">
  <main>
    <div id="content" class="opacity-0">
      <section role="article" data-section-type="page_faithful" data-section-id="back_cover_sec001" class="adt-page-shell">
        <div class="adt-page-visual">
          <img src="images/book-cover-back.png" alt="" aria-hidden="true" style="display:block;width:100%;height:auto" />
        </div>
        <div class="adt-semantic-page">
          <p data-id="backcover_n0000">Jalada la nyuma la kitabu.</p>
          <ol class="adt-page-reading-order">
            <li><h1 data-id="backcover_n0001">Vitabu vingine kutoka Taasisi ya Elimu Tanzania</h1></li>
            <li><h2 data-id="backcover_n0002">Darasa la Kwanza</h2></li>
            <li><figure class="adt-semantic-image" role="img" aria-labelledby="back-cover-image-caption"><figcaption id="back-cover-image-caption" data-id="backcover_im001">Jalada la nyuma linaonyesha vitabu vingine vya Darasa la Kwanza kutoka Taasisi ya Elimu Tanzania: Utamaduni, Sanaa na Michezo; Kusoma; Afya na Mazingira; Kuandika; na Learn English. Pia lina nembo ya Taasisi ya Elimu Tanzania na msimbo pau wa ISBN.</figcaption></figure></li>
            <li><p data-id="backcover_n0003">Utamaduni, Sanaa na Michezo. Kitabu cha Mwanafunzi, Darasa la Kwanza.</p></li>
            <li><p data-id="backcover_n0004">Kusoma. Kitabu cha Mwanafunzi, Darasa la Kwanza.</p></li>
            <li><p data-id="backcover_n0005">Afya na Mazingira. Kitabu cha Mwanafunzi, Darasa la Kwanza.</p></li>
            <li><p data-id="backcover_n0006">Kuandika. Kitabu cha Mwanafunzi, Darasa la Kwanza.</p></li>
            <li><p data-id="backcover_n0007">Learn English. Pupil's Book. Standard One, Kiswahili Medium Schools.</p></li>
            <li><p data-id="backcover_n0008">ISBN: 978-9987-09-901-6</p></li>
            <li><p data-id="backcover_n0009">Mali ya Serikali ya Jamhuri ya Muungano wa Tanzania, hakiuzwi.</p></li>
            <li><p data-id="adt_end_of_page">Mwisho wa ukurasa.</p></li>
          </ol>
        </div>
      </section>
    </div>
  </main>
  <div class="relative z-50" id="interface-container"></div>
  <div class="relative z-50" id="nav-container"></div>
  <script src="./assets/offline-preloader.js?v=99"></script>
  <script src="./assets/scorm.js"></script>
  <script src="./assets/enable-image-descriptions.js"></script>
  <script src="./assets/base.bundle.local.js?v=99"></script>
  <script src="./assets/sign-video-fallback.js?v=100" defer></script>
</body>
</html>
"""
    back_cover_path.write_text(back_cover_html, encoding="utf-8")

    pages_path = ROOT / "content" / "pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))
    pages = [entry for entry in pages if entry.get("section_id") != "cover_sec001"]
    pages = [entry for entry in pages if entry.get("section_id") != "back_cover_sec001"]
    for entry in pages:
        if entry.get("section_id") == "pg001_sec001":
            entry["href"] = "pg001_sec001.html"
    pages.insert(0, {"section_id": "cover_sec001", "href": "index.html"})
    pages.append({"section_id": "back_cover_sec001", "href": "back-cover.html"})
    write_json(pages_path, pages)

    toc_path = ROOT / "content" / "toc.json"
    toc = json.loads(toc_path.read_text(encoding="utf-8"))
    toc = [entry for entry in toc if entry.get("section_id") != "cover_sec001"]
    toc = [entry for entry in toc if entry.get("section_id") != "back_cover_sec001"]
    for entry in toc:
        if entry.get("section_id") == "pg001_sec001":
            entry["href"] = "pg001_sec001.html"
    toc.insert(
        0,
        {
            "section_id": "cover_sec001",
            "href": "index.html",
            "title": "Jalada",
            "chapter_id": "cover_n0000",
            "level": 1,
        },
    )
    toc.append(
        {
            "section_id": "back_cover_sec001",
            "href": "back-cover.html",
            "title": "Jalada la nyuma",
            "chapter_id": "backcover_n0000",
            "level": 1,
        }
    )
    write_json(toc_path, toc)

    for lang in ("sw", "sw-TZ"):
        locale_root = ROOT / "content" / "i18n" / lang
        texts_path = locale_root / "texts.json"
        audios_path = locale_root / "audios.json"
        texts = json.loads(texts_path.read_text(encoding="utf-8"))
        audios = json.loads(audios_path.read_text(encoding="utf-8"))
        for text_id, value in {**COVER_TEXTS, **BACK_COVER_TEXTS}.items():
            texts[text_id] = value
            texts[f"{text_id}_easy_read"] = value
            audios.setdefault(text_id, f"{text_id}_daudi_v1.mp3")
            audios.setdefault(f"{text_id}_easy_read", f"{text_id}_easy_read_daudi_v1.mp3")
        write_json(texts_path, texts)
        write_json(audios_path, audios)

    print("Inserted the original front and back covers around all 132 existing pages.")


if __name__ == "__main__":
    main()
