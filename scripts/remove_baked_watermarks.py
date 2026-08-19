#!/usr/bin/env python3
"""Replace displayed page-render crops with identical watermark-free PDF crops."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pdfplumber
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DecodedStreamObject, NameObject


ROOT = Path(__file__).resolve().parents[1]


class VisibleImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "img":
            return
        values = {key: value or "" for key, value in attrs}
        classes = values.get("class", "").split()
        if "hidden" in classes or values.get("aria-hidden", "").casefold() == "true":
            return
        source = values.get("src", "")
        if source.startswith("images/"):
            self.sources.append(source)


def remove_watermark_artifacts(source_pdf: Path, clean_pdf: Path) -> int:
    reader = PdfReader(source_pdf)
    writer = PdfWriter()
    removed = 0
    for page in reader.pages:
        stream = ContentStream(page.get_contents(), reader)
        kept = []
        skip_depth = 0
        for operands, operator in stream.operations:
            if skip_depth:
                if operator in (b"BDC", b"BMC"):
                    skip_depth += 1
                elif operator == b"EMC":
                    skip_depth -= 1
                continue
            is_watermark = False
            if operator == b"BDC" and len(operands) > 1:
                properties = operands[1]
                try:
                    is_watermark = str(properties.get("/Subtype", "")) == "/Watermark"
                except AttributeError:
                    is_watermark = False
            if is_watermark:
                skip_depth = 1
                removed += 1
                continue
            kept.append((operands, operator))
        stream.operations = kept
        replacement = DecodedStreamObject()
        replacement.set_data(stream.get_data())
        page[NameObject("/Contents")] = replacement
        writer.add_page(page)
    clean_pdf.parent.mkdir(parents=True, exist_ok=True)
    with clean_pdf.open("wb") as output:
        writer.write(output)
    return removed


def visible_assets() -> list[Path]:
    sources = set()
    for page in (ROOT / "index.html", *sorted(ROOT.glob("pg*.html"))):
        parser = VisibleImageParser()
        parser.feed(page.read_text(encoding="utf-8", errors="ignore"))
        sources.update(parser.sources)
    return sorted(ROOT / source for source in sources if (ROOT / source).is_file())


def window_sums(values: np.ndarray, height: int, width: int) -> np.ndarray:
    integral = np.pad(values.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    return (
        integral[height:, width:]
        - integral[:-height, width:]
        - integral[height:, :-width]
        + integral[:-height, :-width]
    )


def fft_match(page: Image.Image, template: Image.Image, factor: int = 5) -> tuple[int, int, float]:
    page_gray = np.asarray(
        page.convert("L").resize((max(1, page.width // factor), max(1, page.height // factor))),
        dtype=np.float32,
    )
    template_gray = np.asarray(
        template.convert("L").resize((max(1, template.width // factor), max(1, template.height // factor))),
        dtype=np.float32,
    )
    ph, pw = page_gray.shape
    th, tw = template_gray.shape
    if th > ph or tw > pw:
        return 0, 0, float("inf")
    shape = (ph + th - 1, pw + tw - 1)
    page_fft = np.fft.rfftn(page_gray, shape)
    template_fft = np.fft.rfftn(np.flip(template_gray, axis=(0, 1)), shape)
    correlation = np.fft.irfftn(page_fft * template_fft, shape)
    correlation = correlation[th - 1:ph, tw - 1:pw]
    page_sq = window_sums(page_gray * page_gray, th, tw)
    template_sq = float(np.sum(template_gray * template_gray))
    ssd = np.maximum(0, page_sq + template_sq - 2 * correlation)
    y, x = np.unravel_index(np.argmin(ssd), ssd.shape)
    return int(x * factor), int(y * factor), float(np.sqrt(ssd[y, x] / (th * tw)))


def refine_match(page: Image.Image, template: Image.Image, x: int, y: int, radius: int = 7) -> tuple[int, int, float]:
    page_rgb = np.asarray(page.convert("RGB"), dtype=np.int16)
    template_rgb = np.asarray(template.convert("RGB"), dtype=np.int16)
    best = (float("inf"), x, y)
    for candidate_y in range(max(0, y - radius), min(page.height - template.height, y + radius) + 1):
        for candidate_x in range(max(0, x - radius), min(page.width - template.width, x + radius) + 1):
            crop = page_rgb[candidate_y:candidate_y + template.height, candidate_x:candidate_x + template.width]
            score = float(np.mean(np.abs(crop - template_rgb)))
            if score < best[0]:
                best = (score, candidate_x, candidate_y)
    return best[1], best[2], best[0]


def pink_seed_count(image: Image.Image) -> int:
    pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    mask = (red >= 248) & (green >= 184) & (green <= 200) & (blue >= 184) & (blue <= 201)
    return int(mask.sum())


def save_crop(crop: Image.Image, destination: Path) -> None:
    if destination.suffix.casefold() in {".jpg", ".jpeg"}:
        crop.convert("RGB").save(destination, quality=95, subsampling=0, optimize=True)
    else:
        crop.convert("RGB").save(destination, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--clean-pdf", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--max-mae", type=float, default=16.0)
    args = parser.parse_args()

    removed_layers = remove_watermark_artifacts(args.pdf, args.clean_pdf)
    assets = visible_assets()
    by_page: dict[int, list[Path]] = defaultdict(list)
    for asset in assets:
        match = re.match(r"pg(\d{3})_", asset.name)
        if match:
            by_page[int(match.group(1))].append(asset)

    backup_root = ROOT / "tmp" / "watermark-originals"
    rows = []
    replaced = 0
    with pdfplumber.open(args.pdf) as source, pdfplumber.open(args.clean_pdf) as clean:
        for page_number, page_assets in sorted(by_page.items()):
            if page_number < 1 or page_number > len(source.pages):
                continue
            source_page = source.pages[page_number - 1].to_image(resolution=144).original.convert("RGB")
            clean_page = clean.pages[page_number - 1].to_image(resolution=144).original.convert("RGB")
            for asset in page_assets:
                template = Image.open(asset).convert("RGB")
                seeds_before = pink_seed_count(template)
                x, y, coarse = fft_match(source_page, template)
                x, y, mae = refine_match(source_page, template, x, y)
                fits = x + template.width <= clean_page.width and y + template.height <= clean_page.height
                should_replace = fits and mae <= args.max_mae and seeds_before > 0
                seeds_after = seeds_before
                if should_replace:
                    relative = asset.relative_to(ROOT)
                    backup = backup_root / relative
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    if not backup.exists():
                        shutil.copy2(asset, backup)
                    crop = clean_page.crop((x, y, x + template.width, y + template.height))
                    save_crop(crop, asset)
                    seeds_after = pink_seed_count(crop)
                    replaced += 1
                rows.append({
                    "asset": str(asset.relative_to(ROOT)),
                    "page": page_number,
                    "x": x,
                    "y": y,
                    "coarse_rmse": round(coarse, 3),
                    "mae": round(mae, 3),
                    "pink_seeds_before": seeds_before,
                    "pink_seeds_after": seeds_after,
                    "replaced": should_replace,
                })

    report = {
        "watermark_layers_removed": removed_layers,
        "visible_assets": len(assets),
        "page_mapped_assets": sum(len(items) for items in by_page.values()),
        "replaced_assets": replaced,
        "assets": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("watermark_layers_removed", "visible_assets", "replaced_assets")}, indent=2))


if __name__ == "__main__":
    main()
