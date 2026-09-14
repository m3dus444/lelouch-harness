#!/usr/bin/env python
"""britania-vitals -- what the machine and the session can afford right now.

Two modes, one script.

    vitals.py            read it once, structured        (Lelouch calls this)
    vitals.py --gate     same, plus a go/no-go exit code (before a dispatch)
    vitals.py --watch    run outside the session, wake it on a threshold

**The orchestrator must never write shell for this.** Not to save tokens -- to
stop each agent rediscovering the same platform traps. Free memory on Windows
comes back through CIM with a locale decimal comma; battery may not exist at
all; disk has to be asked about the right drive. Those belong in one file that
is fixed once, not in whatever one-liner an agent improvises today.

What it reads, and from where:

    session quota   quota-axi --json        runway and the real reset time
    memory, disk    CIM / /proc / statvfs   free, not total
    battery         CIM / /sys              absent on a desktop, which is fine

A note inherited from the monitor this replaces, and worth keeping: on this
machine background tasks are sometimes killed with a low-memory message at times
that correlate with **nothing measurable**. Free RAM is a useful number and a
poor predictor. Report it; do not treat it as a cause.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

IS_WIN = sys.platform.startswith("win")

# Defaults. Every one of them is a judgement call, so each is overridable and
# each prints its own value in the report -- a threshold you cannot see is a
# threshold you cannot argue with.
FREE_GB_FLOOR = 2.0
DISK_GB_FLOOR = 5.0
BATTERY_FLOOR = 25
QUOTA_FLOOR = 10.0  # percent of the window still available


def sh(cmd: list[str], timeout: int = 30) -> str | None:
    """Run a command. Resolve the executable first: on Windows these CLIs are
    .CMD shims and subprocess refuses them by bare name."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return None
    try:
        p = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def ps(script: str) -> str | None:
    out = sh(["powershell", "-NoProfile", "-Command", script], timeout=20)
    return out.strip() if out else None


def num(raw: str | None) -> float | None:
    """Parse a number that may carry a locale decimal comma or a NBSP.

    A French-locale Windows writes `4,22` where the parser wants `4.22`. This
    cost a monitor its memory readings once already.
    """
    if raw is None:
        return None
    cleaned = raw.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# ----------------------------------------------------------------- the reads


def memory() -> tuple[float | None, float | None]:
    """(free_gb, total_gb)."""
    if IS_WIN:
        out = ps(
            "$o=Get-CimInstance Win32_OperatingSystem;"
            "'{0}|{1}' -f ($o.FreePhysicalMemory/1MB),($o.TotalVisibleMemorySize/1MB)"
        )
        if out and "|" in out:
            free, total = out.split("|", 1)
            return num(free), num(total)
        return None, None
    try:
        info = {}
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                info[k] = float(v.strip().split()[0]) / 1024 / 1024
        avail = info.get("MemAvailable", info.get("MemFree"))
        return avail, info.get("MemTotal")
    except (OSError, ValueError, IndexError):
        return None, None


def disk(path: str) -> tuple[float | None, float | None]:
    """(free_gb, total_gb) for the volume that actually holds the work."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None, None
    return usage.free / 1024**3, usage.total / 1024**3


def battery() -> tuple[int | None, bool | None]:
    """(percent, on_mains). Absent on a desktop -- that is not an error."""
    if IS_WIN:
        out = ps(
            "$b=Get-CimInstance Win32_Battery | Select-Object -First 1;"
            "if($b){'{0}|{1}' -f $b.EstimatedChargeRemaining,$b.BatteryStatus}"
        )
        if out and "|" in out:
            pct, status = out.split("|", 1)
            try:
                # BatteryStatus 2 = on mains. Everything else is discharging.
                return int(float(pct)), status.strip() == "2"
            except ValueError:
                return None, None
        return None, None
    base = "/sys/class/power_supply"
    try:
        for name in os.listdir(base):
            cap = os.path.join(base, name, "capacity")
            if os.path.exists(cap):
                with open(cap, encoding="utf-8") as fh:
                    pct = int(fh.read().strip())
                status = os.path.join(base, name, "status")
                mains = None
                if os.path.exists(status):
                    with open(status, encoding="utf-8") as fh:
                        mains = fh.read().strip().lower() != "discharging"
                return pct, mains
    except (OSError, ValueError):
        pass
    return None, None


def quota(provider: str = "claude") -> dict | None:
    """Runway from quota-axi, reported for the window that actually binds.

    The JSON is NOT shaped like the default TOON view -- it is

        {providers: [{provider, plan, windows: [
            {id, label, kind, resetsAt, percentRemaining, pace: {...}}, ...]}]}

    with several concurrent windows (a five-hour session, a seven-day cap).
    **The binding one is whichever has least left**, and that is the only one
    worth reporting: a session window at 99% means nothing if the weekly cap is
    at 4%. Its `resetsAt` is what a scheduled resume is scheduled against.
    """
    raw = sh(["quota-axi", "--json", "--provider", provider, "--no-credential-refresh"], timeout=60)
    if not raw:
        return None
    try:
        data = json.loads(raw[raw.find("{"):])
    except (json.JSONDecodeError, ValueError):
        return None

    windows: list[dict] = []
    for p in (data.get("providers") or []):
        if p.get("provider") != provider:
            continue
        for w in (p.get("windows") or []):
            if isinstance(w.get("percentRemaining"), (int, float)):
                windows.append(w)
    if not windows:
        return None

    binding = min(windows, key=lambda w: w["percentRemaining"])
    return {
        "percent": binding.get("percentRemaining"),
        "runway": binding.get("label") or binding.get("id"),
        "limited_by": binding.get("id"),
        "resets_at": binding.get("resetsAt"),
        "windows": [(w.get("id"), w.get("percentRemaining")) for w in windows],
    }


# -------------------------------------------------------------- the verdict


def resets_in(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "-"
    secs = int((when - datetime.now(timezone.utc)).total_seconds())
    if secs <= 0:
        return "now"
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


def collect(path: str, provider: str) -> dict:
    free_gb, total_gb = memory()
    free_disk, total_disk = disk(path)
    pct, mains = battery()
    q = quota(provider) or {}
    v = {
        "mem_free": free_gb, "mem_total": total_gb,
        "disk_free": free_disk, "disk_total": total_disk,
        "battery": pct, "on_mains": mains,
        "quota_pct": q.get("percent"), "quota_runway": q.get("runway"),
        "resets_at": q.get("resets_at"), "resets_in": resets_in(q.get("resets_at")),
        "quota_windows": q.get("windows"),
    }
    blocks = []
    if free_gb is not None and free_gb < FREE_GB_FLOOR:
        blocks.append(f"memory {free_gb:.2f}GB < {FREE_GB_FLOOR}GB")
    if free_disk is not None and free_disk < DISK_GB_FLOOR:
        blocks.append(f"disk {free_disk:.1f}GB < {DISK_GB_FLOOR}GB")
    if pct is not None and mains is False and pct < BATTERY_FLOOR:
        blocks.append(f"battery {pct}% on battery")
    if isinstance(v["quota_pct"], (int, float)) and v["quota_pct"] < QUOTA_FLOOR:
        blocks.append(f"quota {v['quota_pct']}% left, resets in {v['resets_in']}")
    v["blocks"] = blocks
    return v


def render(v: dict) -> str:
    def gb(free, total, floor):
        if free is None:
            return "unavailable"
        flag = "  LOW" if free < floor else ""
        return f"{free:.2f} / {total:.1f} GB free (floor {floor}){flag}" if total else f"{free:.2f} GB free{flag}"

    batt = "no battery (desktop or mains-only)"
    if v["battery"] is not None:
        batt = f"{v['battery']}%" + (" on mains" if v["on_mains"] else " ON BATTERY")

    qp = v["quota_pct"]
    q = "unavailable" if qp is None else (
        f"{qp}% left on the binding window ({v['quota_runway']}), resets in {v['resets_in']}"
        + (f"   all: {', '.join(f'{i}={p}%' for i, p in v['quota_windows'])}" if v.get("quota_windows") else "")
    )

    lines = [
        "vitals:",
        f"  memory   {gb(v['mem_free'], v['mem_total'], FREE_GB_FLOOR)}",
        f"  disk     {gb(v['disk_free'], v['disk_total'], DISK_GB_FLOOR)}",
        f"  battery  {batt}",
        f"  session  {q}",
    ]
    lines.append("  verdict  " + ("clear to dispatch" if not v["blocks"] else "HOLD -- " + "; ".join(v["blocks"])))
    return "\n".join(lines)


# ----------------------------------------------------------------- auto mode


def coordinator_handle() -> str | None:
    """Lelouch's terminal, from the Run he is bound to."""
    raw = sh(["orca", "orchestration", "run-list", "--json"])
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    runs = (data.get("result", data) or {}).get("runs") or []
    for r in runs:
        if r.get("coordinator_handle"):
            return r["coordinator_handle"]
    return None


def wake(handle: str, text: str, dry: bool) -> bool:
    """Deliver a line into the session, at a turn boundary.

    Waiting for tui-idle is not politeness -- injecting mid-turn corrupts the
    state of whatever the agent was doing.
    """
    if dry:
        print(f"[dry-run] would wake {handle}: {text}")
        return True
    sh(["orca", "terminal", "wait", "--terminal", handle, "--for", "tui-idle",
        "--timeout-ms", "120000"], timeout=150)
    return sh(["orca", "terminal", "send", "--terminal", handle,
               "--text", text, "--enter"], timeout=30) is not None


def watch(args) -> int:
    handle = args.terminal or coordinator_handle()
    if not handle and not args.dry_run:
        print("no coordinator terminal found; pass --terminal <handle>", file=sys.stderr)
        return 2

    print(f"vitals watching every {args.interval}s  ->  {handle or '(dry run)'}", flush=True)
    fired: set[str] = set()
    while True:
        v = collect(args.path, args.provider)
        current = {b.split()[0] for b in v["blocks"]}

        for kind in sorted(current - fired):
            detail = next(b for b in v["blocks"] if b.startswith(kind))
            print(f"{datetime.now():%H:%M:%S}  BREACH  {detail}", flush=True)
            if args.present:
                # C.C is at the keyboard: warn, never act for them.
                print("        (user present -- warning only, taking no action)", flush=True)
            else:
                wake(handle, f"britania-vitals: {detail}. Stop dispatching and park the run.", args.dry_run)
        # Clearing a breach re-arms it, so a level that recovers and degrades
        # again alarms twice. A latch is right for an episode, wrong for a level.
        fired = current

        if v["quota_pct"] is not None and v["quota_pct"] < QUOTA_FLOOR and v["resets_at"]:
            print(f"{datetime.now():%H:%M:%S}  quota resets in {v['resets_in']}", flush=True)

        time.sleep(args.interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="Machine and session vitals.")
    ap.add_argument("--gate", action="store_true",
                    help="for the orchestrator: exit 0 = clear to dispatch, 1 = hold")
    ap.add_argument("--breach", action="store_true",
                    help="for an automation precheck: exit 0 = there IS a breach, 1 = nothing to do")
    ap.add_argument("--watch", action="store_true", help="auto mode: wake the session on a breach")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--interval", type=int, default=300, help="seconds between checks in --watch")
    ap.add_argument("--terminal", help="coordinator terminal handle for --watch")
    ap.add_argument("--present", action="store_true", help="user is at the keyboard: warn, never act")
    ap.add_argument("--dry-run", action="store_true", help="print what --watch would send")
    ap.add_argument("--path", default=os.getcwd(), help="volume to measure disk on")
    ap.add_argument("--provider", default="claude")
    args = ap.parse_args()

    if args.watch:
        try:
            return watch(args)
        except KeyboardInterrupt:
            return 0

    v = collect(args.path, args.provider)
    print(json.dumps(v, indent=2) if args.json else render(v))

    # Two exit codes that are deliberate inverses, because two callers ask
    # opposite questions and the same number would be wrong for one of them:
    #
    #   --gate    "may I dispatch?"      0 = yes, clear   1 = no, hold
    #   --breach  "is there a problem?"  0 = yes, breach  1 = no, all fine
    #
    # --breach exists for `orca automations --precheck`, which documents
    # "exit code 0 continues, anything else records a skipped run". Wiring
    # --gate there inverts the whole thing: it would wake an agent every quiet
    # hour and stay silent during an actual breach.
    if args.breach:
        return 0 if v["blocks"] else 1
    return 1 if (args.gate and v["blocks"]) else 0


if __name__ == "__main__":
    sys.exit(main())
