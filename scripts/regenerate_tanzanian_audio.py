#!/usr/bin/env python3
"""Regenerate every read-aloud clip with natural Tanzanian Swahili speech."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOICE = "sw-TZ-RehemaNeural"
LANGS = ("sw", "sw-TZ")

ONES = (
    "sifuri", "moja", "mbili", "tatu", "nne", "tano", "sita", "saba",
    "nane", "tisa",
)
TENS = (
    "", "kumi", "ishirini", "thelathini", "arobaini", "hamsini",
    "sitini", "sabini", "themanini", "tisini",
)


def number_to_swahili(value: int) -> str:
    """Return a natural Swahili reading for a non-negative integer."""
    if value < 10:
        return ONES[value]
    if value < 100:
        tens, ones = divmod(value, 10)
        return TENS[tens] + (f" na {ONES[ones]}" if ones else "")
    if value < 1_000:
        hundreds, rest = divmod(value, 100)
        result = f"mia {ONES[hundreds]}"
        return result + (f" na {number_to_swahili(rest)}" if rest else "")
    if value < 1_000_000:
        thousands, rest = divmod(value, 1_000)
        prefix = "elfu moja" if thousands == 1 else f"elfu {number_to_swahili(thousands)}"
        return prefix + (f" na {number_to_swahili(rest)}" if rest else "")
    return str(value)


def spoken_swahili(text: str) -> str:
    """Prepare visible textbook text for Tanzanian Swahili narration only."""
    spoken = text.replace("−", " - ").replace("–", " - ")
    operators = {
        "+": " jumlisha ",
        "-": " toa ",
        "=": " ni sawa na ",
        "×": " zidisha kwa ",
        "÷": " gawanya kwa ",
        "/": " gawanya kwa ",
    }
    for symbol, words in operators.items():
        spoken = spoken.replace(symbol, words)

    def replace_number(match: re.Match[str]) -> str:
        raw = match.group(0).replace(",", "")
        return number_to_swahili(int(raw))

    spoken = re.sub(r"(?<![\w])\d{1,6}(?:,\d{3})*(?![\w])", replace_number, spoken)
    spoken = re.sub(r"\bQR\b", "kyu ar", spoken, flags=re.IGNORECASE)
    spoken = re.sub(r"\s+", " ", spoken).strip()
    return spoken


def load_jobs(requested_ids: set[str] | None = None) -> dict[str, list[Path]]:
    """Group destinations by spoken phrase so identical clips are generated once."""
    grouped: dict[str, list[Path]] = defaultdict(list)
    for lang in LANGS:
        base = ROOT / "content" / "i18n" / lang
        texts = json.loads((base / "texts.json").read_text(encoding="utf-8"))
        audios = json.loads((base / "audios.json").read_text(encoding="utf-8"))
        for text_id, filename in audios.items():
            if requested_ids is not None and text_id not in requested_ids:
                continue
            text = texts.get(text_id, "")
            if isinstance(text, str) and text.strip():
                grouped[spoken_swahili(text)].append(base / "audio" / filename)
    return grouped


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default="-8%")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--limit", type=int, help="Generate only this many unique phrases (testing)")
    parser.add_argument("--ids", nargs="+", help="Generate only the listed text IDs")
    args = parser.parse_args()

    jobs = load_jobs(set(args.ids) if args.ids else None)
    items = sorted(jobs.items())
    if args.limit:
        items = items[: args.limit]
    semaphore = asyncio.Semaphore(args.concurrency)
    cache_dir = Path(tempfile.mkdtemp(prefix="kuhesabu-tts-"))

    async def generate(spoken: str, destinations: list[Path]) -> None:
        digest = hashlib.sha256(spoken.encode("utf-8")).hexdigest()
        cached = cache_dir / f"{digest}.mp3"
        temporary = cached.with_suffix(".mp3.part")
        async with semaphore:
            await edge_tts.Communicate(spoken, args.voice, rate=args.rate).save(str(temporary))
        os.replace(temporary, cached)
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, destination)

    try:
        await asyncio.gather(*(generate(spoken, destinations) for spoken, destinations in items))
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)

    clip_count = sum(len(destinations) for _, destinations in items)
    print(f"Generated {clip_count} clips from {len(items)} unique phrases with {args.voice}")


if __name__ == "__main__":
    asyncio.run(main())
