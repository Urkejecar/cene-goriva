"""Fail (exit 1) when the last update recorded source errors, so GitHub emails the owner.

Run with:  python -m scraper.check_errors site/data.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    errors = data.get("errors") or []
    for e in errors:
        print(f"Source failed: {e.get('source')}: {e.get('message')}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
