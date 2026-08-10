#!/usr/bin/env python3
"""Refresh the generated inline data used when the ADT is opened offline."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "assets" / "offline-preloader.js"
START = "  var INLINE = "
END = ";\n  var BASE_DIR = "


def main() -> None:
    source = PATH.read_text(encoding="utf-8")
    start = source.index(START) + len(START)
    end = source.index(END, start)
    inline = json.loads(source[start:end])
    for key in list(inline):
        local = ROOT / key.removeprefix("./")
        if not local.exists():
            continue
        if local.suffix == ".json":
            inline[key] = json.loads(local.read_text(encoding="utf-8"))
        else:
            inline[key] = local.read_text(encoding="utf-8")
    encoded = json.dumps(inline, ensure_ascii=False, separators=(",", ":"))
    PATH.write_text(source[:start] + encoded + source[end:], encoding="utf-8")
    print(f"Refreshed {len(inline)} offline resources")


if __name__ == "__main__":
    main()
