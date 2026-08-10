#!/usr/bin/env python3
"""Regenerate corrected read-aloud clips with the Tanzanian Swahili voice."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
VOICE = "sw-TZ-RehemaNeural"
LANGS = ("sw", "sw-TZ")


async def main() -> None:
    ids = [line.strip() for line in (ROOT / "matrix-corrected-audio-ids.txt").read_text().splitlines() if line.strip()]
    semaphore = asyncio.Semaphore(24)

    async def generate(lang: str, text_id: str, text: str, filename: str) -> None:
        destination = ROOT / "content" / "i18n" / lang / "audio" / filename
        temporary = destination.with_suffix(".mp3.part")
        async with semaphore:
            await edge_tts.Communicate(text, VOICE, rate="-8%").save(str(temporary))
        os.replace(temporary, destination)

    jobs = []
    for lang in LANGS:
        base = ROOT / "content" / "i18n" / lang
        texts = json.loads((base / "texts.json").read_text(encoding="utf-8"))
        audios = json.loads((base / "audios.json").read_text(encoding="utf-8"))
        for text_id in ids:
            filename = audios.get(text_id)
            if filename and texts.get(text_id):
                jobs.append(generate(lang, text_id, texts[text_id], filename))
    await asyncio.gather(*jobs)
    print(f"Generated {len(jobs)} clips with {VOICE}")


if __name__ == "__main__":
    asyncio.run(main())
