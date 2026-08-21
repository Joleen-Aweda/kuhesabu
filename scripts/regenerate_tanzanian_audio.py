#!/usr/bin/env python3
"""Regenerate read-aloud clips with corrected Tanzanian Swahili speech.

Visible textbook strings remain authoritative. This module creates a separate
spoken representation and never rewrites texts.json or page HTML.
"""

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
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOICE = "sw-TZ-DaudiNeural"
# Retained as an import-compatible alias for older audit tooling. Every spoken
# segment now uses Daudi, including acronyms, URLs, and email addresses.
ENGLISH_VOICE = DEFAULT_VOICE
DEFAULT_RATE = "-5%"
LANGS = ("sw", "sw-TZ")

TOC_PAGE_NUMBERS = {
    "pg003_n0006": 5, "pg003_n0009": 6, "pg003_n0014": 1,
    "pg003_n0019": 4, "pg003_n0024": 10, "pg003_n0029": 13,
    "pg003_n0034": 19, "pg003_n0039": 22, "pg003_n0044": 35,
    "pg003_n0049": 46, "pg004_n0006": 57, "pg004_n0010": 61,
    "pg004_n0014": 64, "pg004_n0018": 68, "pg004_n0022": 82,
    "pg004_n0026": 100, "pg004_n0030": 119, "pg004_n0034": 124,
    "pg004_n0036": 125, "pg004_n0038": 126,
}
TOC_ROMAN_PAGE_NUMBERS = {"pg003_n0006": 5, "pg003_n0009": 6}

ONES = (
    "sifuri", "moja", "mbili", "tatu", "nne", "tano", "sita", "saba",
    "nane", "tisa",
)
TENS = (
    "", "kumi", "ishirini", "thelathini", "arobaini", "hamsini",
    "sitini", "sabini", "themanini", "tisini",
)
ORDINALS = {1: "kwanza", 2: "pili", 3: "tatu", 4: "nne", 5: "tano", 6: "sita"}
ROMAN_NUMERALS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
LIST_LETTERS = {
    "a": "a", "b": "be", "c": "che", "d": "de", "e": "e", "f": "efu",
    "g": "ge", "h": "ha", "i": "i", "j": "je", "k": "ka", "l": "ele",
    "m": "eme", "n": "ene", "o": "o", "p": "pe", "q": "ku", "r": "ere",
    "s": "ese", "t": "te", "u": "u", "v": "ve", "w": "we", "x": "eksi",
    "y": "ya", "z": "ze",
}
ABBREVIATIONS = {
    r"\bDkt\.": "Daktari", r"\bBw\.": "Bwana", r"\bBi\.": "Bibi",
    r"\bProf\.": "Profesa", r"\bNa\.": "namba",
}
ENGLISH_ACRONYMS = {"KDE", "ISBN", "QR", "USB", "OK", "TET", "UDSM", "UDOM", "SQA"}
BLANK_TOKEN = re.compile(r"\[\[blank:[^]]+\]\]", re.IGNORECASE)
URL_OR_EMAIL = re.compile(
    r"https?://[^\s,;]+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|"
    r"\b(?:(?:www|ol)\.)?tie\.go\.tz(?:/[^\s,;]+)?|"
    r"\b(?:ISBN\s*:\s*[0-9-]+|FOR ONLINE READING ONLY|Room to Read)\b",
    re.IGNORECASE,
)
SPECIAL_ENGLISH = re.compile(
    URL_OR_EMAIL.pattern + r"|\b(?:KDE|QR|USB|OK|TET|UDSM|UDOM|SQA)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpeechSegment:
    voice: str
    text: str


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


def ordinal_to_swahili(value: int) -> str:
    return ORDINALS.get(value, number_to_swahili(value))


def spell_english_token(token: str) -> str:
    """Make English/acronym/Internet spans explicit for Daudi."""
    stripped = token.strip()
    if stripped.upper() == "TET":
        # This acronym is conventionally pronounced as one Swahili word.
        return "teti"
    if stripped.upper().startswith("ISBN"):
        digits = re.sub(r"\D", "", stripped.split(":", 1)[-1])
        return "I S B N, " + ", ".join(ONES[int(digit)] for digit in digits)
    if re.match(r"https?://", stripped, re.I):
        value = re.sub(r"^https", "H T T P S", stripped, flags=re.I)
        value = re.sub(r"^http", "H T T P", value, flags=re.I)
        value = value.replace(":", " colon ").replace("/", " slash ")
        value = value.replace(".", " dot ").replace("-", " hyphen ")
        value = re.sub(r"\bol\b", "O L", value, flags=re.I)
        value = re.sub(r"\btie\b", "T I E", value, flags=re.I)
        value = re.sub(r"\bgo\b", "G O", value, flags=re.I)
        value = re.sub(r"\btz\b", "T Z", value, flags=re.I)
        return re.sub(r"\s+", " ", value).strip()
    if re.match(r"(?:(?:www|ol)\.)?tie\.go\.tz", stripped, re.I):
        value = stripped.replace("/", " slash ").replace(".", " dot ").replace("-", " hyphen ")
        value = re.sub(r"\bwww\b", "W W W", value, flags=re.I)
        value = re.sub(r"\bol\b", "O L", value, flags=re.I)
        value = re.sub(r"\btie\b", "T I E", value, flags=re.I)
        value = re.sub(r"\bgo\b", "G O", value, flags=re.I)
        value = re.sub(r"\btz\b", "T Z", value, flags=re.I)
        return re.sub(r"\s+", " ", value).strip()
    if "@" in stripped:
        value = stripped.replace("@", " at ").replace(".", " dot ").replace("-", " hyphen ")
        value = re.sub(r"\btie\b", "T I E", value, flags=re.I)
        value = re.sub(r"\bgo\b", "G O", value, flags=re.I)
        value = re.sub(r"\btz\b", "T Z", value, flags=re.I)
        return re.sub(r"\s+", " ", value).strip()
    if stripped.upper() in ENGLISH_ACRONYMS:
        return " ".join(stripped.upper())
    return stripped


def _remove_repeated_bracketed_digits(text: str) -> str:
    number_words = "|".join(ONES[1:] + TENS[1:])
    return re.sub(rf"\b({number_words})\s*\(\s*\d+\s*\)", r"\1", text, flags=re.I)


def _replace_numbered_headings(text: str) -> str:
    def activity(match: re.Match[str]) -> str:
        return f"{match.group(1)} {ordinal_to_swahili(int(match.group(2)))}"

    text = re.sub(
        r"\b(Zoezi la|Jaribio la|Kazi ya kufanya ya|Mfano wa)\s+(\d+)\b",
        activity,
        text,
    )
    text = re.sub(
        r"\bKielelezo\s+(\d+)\b",
        lambda m: f"Kielelezo cha {ordinal_to_swahili(int(m.group(1)))}",
        text,
    )
    return text


def _replace_roman_numerals(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = ROMAN_NUMERALS[match.group(0).upper()]
        return number_to_swahili(value)

    return re.sub(r"(?<![\w])(?:III|IV|VI|II|V|I)(?![\w])", replace, text, flags=re.I)


def _replace_ranges_in_prose(text: str) -> str:
    """Read digit hyphens as ranges in prose, but retain subtraction formulas."""
    if not re.search(r"[A-Za-zÀ-ÿ]", text):
        return text
    # A compact 1-9 form is a range; spaced 1 - 9 forms in this mathematics
    # book are subtraction expressions, including those embedded in prose.
    return re.sub(r"(?<![\w])([0-9]+)[-–−]([0-9]+)(?![\w])", r"\1 hadi \2", text)


def spoken_swahili(text: str) -> str:
    """Transform authoritative visible text into Tanzanian Swahili narration."""
    spoken = BLANK_TOKEN.sub(" ", text)
    spoken = _remove_repeated_bracketed_digits(spoken)
    spoken = _replace_numbered_headings(spoken)
    spoken = re.sub(r"\ba\s+mpaka\s+d\b", "a mpaka de", spoken, flags=re.I)
    for pattern, replacement in ABBREVIATIONS.items():
        spoken = re.sub(pattern, replacement, spoken)
    spoken = spoken.replace("→", " inaelekea ").replace("←", " inatoka ")
    spoken = _replace_roman_numerals(spoken)
    spoken = _replace_ranges_in_prose(spoken)
    spoken = spoken.replace("−", " - ").replace("–", " - ")
    operators = {
        "+": " jumlisha ", "-": " toa ", "=": " ni sawa na ",
        "×": " zidisha kwa ", "÷": " gawanya kwa ", "/": " gawanya kwa ",
    }
    for symbol, words in operators.items():
        spoken = spoken.replace(symbol, words)

    def replace_number(match: re.Match[str]) -> str:
        return number_to_swahili(int(match.group(0).replace(",", "")))

    spoken = re.sub(r"(?<![\w])\d{1,6}(?:,\d{3})*(?![\w])", replace_number, spoken)
    spoken = re.sub(r"\bTEHAMA\b", "tehama", spoken, flags=re.I)
    # Separate the syllables after operator expansion so the hyphen remains a
    # pronunciation cue and is not interpreted as subtraction.
    spoken = re.sub(r"\bpasi\b", "pa-si", spoken, flags=re.I)
    spoken = re.sub(r"\s+", " ", spoken).strip(" ,")
    return spoken


def page_two_spoken(text: str) -> str:
    """Prepare one uninterrupted Daudi utterance for a page-two text item."""
    stripped = BLANK_TOKEN.sub(" ", text).strip()
    # The slash between the two telephone numbers is punctuation, not a
    # division operator. Name the mark so the contact line is unambiguous.
    stripped = re.sub(r"(?<=\d)\s*/\s*(?=\+?\d)", " alama ya mkato ", stripped)
    parts: list[str] = []
    cursor = 0
    for match in SPECIAL_ENGLISH.finditer(stripped):
        before = spoken_swahili(stripped[cursor:match.start()])
        if before:
            parts.append(before)
        parts.append(spell_english_token(match.group(0)))
        cursor = match.end()
    tail = spoken_swahili(stripped[cursor:])
    if tail:
        parts.append(tail)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def toc_page_spoken(text_id: str) -> str | None:
    base_id = text_id[:-10] if text_id.endswith("_easy_read") else text_id
    page_number = TOC_PAGE_NUMBERS.get(base_id)
    if page_number is None:
        return None
    if base_id in TOC_ROMAN_PAGE_NUMBERS:
        return f"namba {number_to_swahili(page_number)} ya Kirumi"
    return f"ukurasa wa {ordinal_to_swahili(page_number) if page_number == 1 else number_to_swahili(page_number)}"


def speech_segments(text_id: str, text: str) -> tuple[SpeechSegment, ...]:
    """Transform content into speech segments that all use Daudi."""
    page_narration = toc_page_spoken(text_id)
    if page_narration:
        return (SpeechSegment(DEFAULT_VOICE, page_narration),)
    stripped = BLANK_TOKEN.sub(" ", text).strip()
    if not re.search(r"[\wÀ-ÿ]", stripped):
        return (SpeechSegment("silence", ""),)
    if text_id.startswith("pg002_"):
        transformed = page_two_spoken(stripped)
        if transformed and transformed[-1] not in ".!?":
            transformed += "."
        return (SpeechSegment(DEFAULT_VOICE, transformed),)
    if stripped.lower().rstrip(".):") in LIST_LETTERS and len(stripped) <= 3:
        key = stripped.lower().rstrip(".):")
        return (SpeechSegment(DEFAULT_VOICE, LIST_LETTERS[key] + "."),)

    segments: list[SpeechSegment] = []
    cursor = 0
    for match in SPECIAL_ENGLISH.finditer(stripped):
        before = spoken_swahili(stripped[cursor:match.start()])
        if before and re.search(r"[\wÀ-ÿ]", before):
            segments.append(SpeechSegment(DEFAULT_VOICE, before))
        token = match.group(0)
        segments.append(SpeechSegment(DEFAULT_VOICE, spell_english_token(token)))
        cursor = match.end()
    tail = spoken_swahili(stripped[cursor:])
    if tail and re.search(r"[\wÀ-ÿ]", tail):
        segments.append(SpeechSegment(DEFAULT_VOICE, tail))
    if not segments:
        transformed = spoken_swahili(stripped)
        segments.append(SpeechSegment(DEFAULT_VOICE, transformed) if transformed else SpeechSegment("silence", ""))

    # Punctuation gives isolated labels/table cells a short terminal pause.
    if len(stripped.split()) <= 3:
        last = segments[-1]
        if last.text and last.text[-1] not in ".!?":
            segments[-1] = SpeechSegment(last.voice, last.text + ".")
    return tuple(segment for segment in segments if segment.text.strip() or segment.voice == "silence")


def load_jobs(requested_ids: set[str] | None = None):
    grouped: dict[tuple[SpeechSegment, ...], list[Path]] = defaultdict(list)
    affected: dict[str, dict[str, object]] = {}
    for lang in LANGS:
        base = ROOT / "content" / "i18n" / lang
        texts = json.loads((base / "texts.json").read_text(encoding="utf-8"))
        audios = json.loads((base / "audios.json").read_text(encoding="utf-8"))
        for text_id, filename in audios.items():
            if requested_ids is not None and text_id not in requested_ids:
                continue
            text = texts.get(text_id, "")
            if isinstance(text, str) and text.strip():
                segments = speech_segments(text_id, text)
                grouped[segments].append(base / "audio" / filename)
                affected.setdefault(text_id, {"visible": text, "spoken": [s.text for s in segments], "voices": [s.voice for s in segments]})
    return grouped, affected


async def main() -> None:
    try:
        import edge_tts
    except ModuleNotFoundError as error:
        raise SystemExit("edge-tts is required only when generating new audio clips") from error
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default=DEFAULT_RATE)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--ids-file", type=Path, help="Read one requested text ID per line")
    parser.add_argument("--matching-regex", help="Generate mapped IDs whose visible text matches this regex")
    parser.add_argument("--manifest", type=Path, help="Write the transformed-ID manifest")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    requested_ids = set(args.ids) if args.ids else None
    if args.ids_file:
        requested_ids = {
            line.strip() for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    if args.matching_regex:
        sw_base = ROOT / "content" / "i18n" / "sw"
        sw_texts = json.loads((sw_base / "texts.json").read_text(encoding="utf-8"))
        sw_audios = json.loads((sw_base / "audios.json").read_text(encoding="utf-8"))
        pattern = re.compile(args.matching_regex)
        matched = {
            text_id for text_id, value in sw_texts.items()
            if text_id in sw_audios and isinstance(value, str) and pattern.search(value)
        }
        requested_ids = matched if requested_ids is None else requested_ids | matched
    jobs, affected = load_jobs(requested_ids)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(affected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    items = sorted(jobs.items(), key=lambda item: repr(item[0]))
    if args.limit:
        items = items[:args.limit]
    if args.dry_run:
        print(f"Prepared {len(affected)} IDs in {len(items)} unique segmented phrases.")
        return

    semaphore = asyncio.Semaphore(args.concurrency)
    cache_dir = Path(tempfile.mkdtemp(prefix="kuhesabu-tts-"))

    async def synthesize(segment: SpeechSegment, destination: Path) -> None:
        if segment.voice == "silence":
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                "anullsrc=r=24000:cl=mono", "-t", "0.35", "-q:a", "9",
                "-acodec", "libmp3lame", str(destination),
            )
            if await process.wait() != 0:
                raise RuntimeError("ffmpeg failed while creating a silent answer-field clip")
            return
        voice = args.voice
        error: Exception | None = None
        for attempt in range(4):
            try:
                await asyncio.wait_for(
                    edge_tts.Communicate(segment.text, voice, rate=args.rate).save(str(destination)),
                    timeout=30,
                )
                return
            except Exception as exc:
                error = exc
                await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"TTS failed after retries: {segment.text[:80]!r}") from error

    async def generate(segments: tuple[SpeechSegment, ...], destinations: list[Path]) -> None:
        digest = hashlib.sha256(repr(segments).encode("utf-8")).hexdigest()
        cached = cache_dir / f"{digest}.mp3"
        async with semaphore:
            pieces: list[Path] = []
            for index, segment in enumerate(segments):
                piece = cache_dir / f"{digest}-{index}.mp3"
                await synthesize(segment, piece)
                pieces.append(piece)
            if len(pieces) == 1:
                shutil.copyfile(pieces[0], cached)
            else:
                concat_file = cache_dir / f"{digest}.txt"
                concat_file.write_text("".join(f"file '{piece}'\n" for piece in pieces), encoding="utf-8")
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(concat_file), "-c", "copy", str(cached),
                )
                if await process.wait() != 0:
                    raise RuntimeError(f"ffmpeg failed while joining {len(pieces)} speech segments")
        for destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, destination)

    try:
        await asyncio.gather(*(generate(segments, destinations) for segments, destinations in items))
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)

    clip_count = sum(len(destinations) for _, destinations in items)
    print(f"Generated {clip_count} clips from {len(items)} unique phrases with {args.voice} at {args.rate}.")


if __name__ == "__main__":
    asyncio.run(main())
