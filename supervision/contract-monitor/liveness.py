#!/usr/bin/env python3
"""Who is actually alive, measured from transcript ROWS - never from mtime.

Written after the 9 Sep failure. Three workers stalled at 16:17. The silence
alarm fired at 16:32, correctly. The supervisor then checked liveness with file
mtime, read "8.6 min ago", called the alarm benign, and stood down. The real
last row was 15 minutes old and no more were coming. The stall ran 2h20m.

mtime is not activity. A file can be touched, flushed, or rotated without a new
row, and the number it gives is always more reassuring than the truth. Read the
last row's timestamp, and read the last GAP, because a session that is about to
be declared healthy on one recent row may have been dead for two hours before it.

    python liveness.py weave-atlas
"""
from __future__ import annotations

import json
import pathlib
import sys
import datetime as dt

PROJECTS = pathlib.Path.home() / ".claude" / "projects"


def rows(f: pathlib.Path) -> list[dt.datetime]:
    out: list[dt.datetime] = []
    for line in f.open(encoding="utf-8", errors="replace"):
        if '"timestamp"' not in line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = r.get("timestamp")
        if not t:
            continue
        try:
            out.append(dt.datetime.fromisoformat(str(t).replace("Z", "+00:00")))
        except ValueError:
            pass
    out.sort()
    return out


def main() -> int:
    needle = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    now = dt.datetime.now(dt.timezone.utc)
    print(f"now {now.astimezone():%H:%M:%S}   (ages from LAST ROW, not mtime)\n")
    found = []
    for d in sorted(PROJECTS.iterdir()):
        if not d.is_dir():
            continue
        nm = d.name.lower()
        if needle not in nm and "worktrees-" not in nm:
            continue
        for f in d.glob("*.jsonl"):
            ts = rows(f)
            if not ts:
                continue
            age = (now - ts[-1]).total_seconds() / 60
            if age > 240:
                continue
            gaps = [(b - a).total_seconds() / 60 for a, b in zip(ts, ts[1:])]
            worst = max(gaps[-40:], default=0.0)
            low = nm
            tag = (low.split(needle + "-")[-1] if "workspaces" in low
                   else "gate:" + d.name[-8:] if "worktrees-" in low else "lelouch")
            found.append((age, tag, ts[-1], worst))
    for age, tag, last, worst in sorted(found):
        flag = "  <-- STALLED" if age > 15 else ""
        print(f"  {tag:<20} last row {age:6.1f} min ago ({last.astimezone():%H:%M:%S})"
              f"   worst recent gap {worst:6.1f} min{flag}")
    if not found:
        print("  (nothing written in the last 4 hours)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
