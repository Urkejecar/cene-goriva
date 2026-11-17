"""Fail (exit 1) when a source has been failing long enough to tell the owner, so GitHub emails them.

Single failed runs are only printed: sources hiccup, and an email for every one of
them would teach the owner to ignore the emails. See `update._alerts`.

Run with:  python -m scraper.check_errors site/data.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    for e in data.get("errors") or []:
        print(f"Source failed: {e.get('source')}: {e.get('message')}")
    alerts = data.get("alerts") or []
    if alerts:
        print(f"Failing for 3+ hours: {', '.join(alerts)}")
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
