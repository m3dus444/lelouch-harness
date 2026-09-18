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
from pathlib import Path

IS_WIN = sys.platform.startswith("win")

# Defaults. Every one of them is a judgement call, so each is overridable and
# each prints its own value in the report -- a threshold you cannot see is a
# threshold you cannot argue with.
FREE_GB_FLOOR = 1.0  # was 2.0: four breaches in one run, every one self-recovering,
                     # zero kills. Defender alone holds ~1.5GB, so 2.0GB free was
                     # nowhere near distress -- a 100% false-positive rate is a line
                     # drawn in the wrong place, not a machine in trouble.
DISK_GB_FLOOR = 5.0
BATTERY_FLOOR = 25
QUOTA_FLOOR = 10.0  # percent of the window still available

# How far back a value must come before anyone is told it recovered. Declaring
# an all-clear at exactly the floor means declaring it one reading before the
# next alarm, and a run that is parked, released and parked again has been told
# nothing it can act on. The band between the two lines is deliberately silent:
# whatever was last said about that value still stands.
RECOVERY_MARGIN = 1.25  # of the floor

# Memory is judged over a window rather than at a moment -- see `memory_collapsed`.
MEM_HISTORY = 6    # readings kept; half an hour of them at the watcher's cadence
MEM_STEP_GB = 1.0  # a fall this large is something *taking* memory, not churn
MEM_SUSTAIN = 2    # consecutive low readings before a dip counts as a level

# On the watcher's cadence, which lives elsewhere: `WATCHER_EVERY_MIN` in
# geass/cli.py was agreed to move 15 -> 5 minutes **conditional on the quiet in
# this file landing first** -- the quota-0 skip, the latch, and the all-clear.
# Tripling the rate of an instrument that could only ever say "park" would have
# turned one run's nine injections into twenty-seven. If any of that quiet is
# ever taken back out, the cadence goes back up with it.


# Where a CLI lives when it is installed for the user rather than the machine.
# A scheduled task does not inherit an interactive shell's environment, so a
# tool on the *user* PATH is simply absent as far as `shutil.which` is
# concerned -- and both `python` and `orca` install here by default.
FALLBACK_BINS: dict[str, tuple[str, ...]] = {
    "orca": (
        r"%LOCALAPPDATA%\Programs\orca\resources\bin\orca.exe",
        r"%LOCALAPPDATA%\Programs\orca\resources\bin\orca.cmd",
        r"%PROGRAMFILES%\orca\resources\bin\orca.exe",
    ),
}


def resolve(name: str) -> str | None:
    """Find an executable, including one only the user's PATH knows about.

    `shutil.which` searches the PATH of the process it is running in. Under the
    OS scheduler that is not the PATH you get in a terminal, and this is not
    hypothetical: fixing the watcher's interpreter without fixing this would
    have produced a task that started cleanly, failed to find `orca`, woke
    nobody, and **exited 0** -- reporting success while doing nothing, which is
    strictly harder to notice than the crash it replaced.
    """
    exe = shutil.which(name)
    if exe:
        return exe
    for candidate in FALLBACK_BINS.get(name, ()):
        path = Path(os.path.expandvars(candidate))
        if path.exists():
            return str(path)
    return None


def sh(cmd: list[str], timeout: int = 30) -> str | None:
    """Run a command and return stdout, or None if it failed in any way.

    Two Windows traps, both of which fail *silently* rather than loudly:

    **Resolve the executable first.** These CLIs install as `.CMD` shims, and
    subprocess refuses them by bare name with `FileNotFoundError` even though
    the same command works in a shell.

    **Force UTF-8.** `text=True` decodes using the locale codec -- cp1252 on a
    French Windows -- and any non-ASCII byte in the output (a path containing
    `é`, say) raises inside subprocess's reader thread. The call still returns,
    with nothing in it, so every consumer silently sees an empty result and
    concludes the thing it asked about does not exist.
    """
    exe = resolve(cmd[0])
    if exe is None:
        return None
    try:
        p = subprocess.run(
            [exe, *cmd[1:]], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
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
    # Two lines per reading, not one. `blocks` is the floor -- what is bad now.
    # `clears` sits RECOVERY_MARGIN above it -- what is good enough to say so out
    # loud. Everything between them says nothing at all, which is what stops a
    # value sitting on the line from announcing itself twice a tick.
    blocks, clears = [], []
    if free_gb is not None:
        if free_gb < FREE_GB_FLOOR:
            blocks.append(f"memory {free_gb:.2f}GB < {FREE_GB_FLOOR}GB")
        elif free_gb >= FREE_GB_FLOOR * RECOVERY_MARGIN:
            clears.append(f"memory back to {free_gb:.2f}GB free")
    if free_disk is not None:
        if free_disk < DISK_GB_FLOOR:
            blocks.append(f"disk {free_disk:.1f}GB < {DISK_GB_FLOOR}GB")
        elif free_disk >= DISK_GB_FLOOR * RECOVERY_MARGIN:
            clears.append(f"disk back to {free_disk:.1f}GB free")
    if pct is not None and mains is False and pct < BATTERY_FLOOR:
        blocks.append(f"battery {pct}% on battery")
    elif pct is not None and (mains or pct >= BATTERY_FLOOR * RECOVERY_MARGIN):
        clears.append(f"battery {pct}%" + (" and back on mains" if mains else " and above the floor"))
    if isinstance(v["quota_pct"], (int, float)):
        if v["quota_pct"] < QUOTA_FLOOR:
            blocks.append(f"quota {v['quota_pct']}% left, resets in {v['resets_in']}")
        elif v["quota_pct"] >= QUOTA_FLOOR * RECOVERY_MARGIN:
            clears.append(f"quota back to {v['quota_pct']}% on the binding window")
    v["blocks"] = blocks
    v["clears"] = clears
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


def _orca(args: list[str]) -> dict:
    raw = sh(["orca", *args])
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return (data.get("result", data) or {}) if isinstance(data, dict) else {}


def _same_project(a: str | None, b: str) -> bool:
    """Do two paths name the same project? Compared case-insensitively with
    normalised separators, because Orca reports `C:/...` and argv carries
    `C:\\...` for the identical directory."""
    if not a:
        return False
    norm = lambda p: os.path.normcase(os.path.abspath(str(p))).replace("\\", "/").rstrip("/")
    return norm(a) == norm(b)


def coordinator_handle(project: str) -> str | None:
    """The orchestrator's terminal **for this project**, or None.

    This is the part that must not be guessed. A Run carries no project
    identity at all -- only an id, a free-text objective and a
    `coordinator_handle` -- and a machine running several projects will have
    several Runs. Taking "the first Run with a handle" would poke whichever
    project happened to sort first, which is worse than doing nothing.

    Terminals are what know where they live, so the join goes through them:

        run-list      -> coordinator_handle
        terminal list -> handle, worktreePath, connected, orphaned

    A handle only qualifies when its terminal is in **this** project, is
    connected, and is not orphaned. Runs are considered newest first, so a
    finished Run from last week cannot win over the live one.
    """
    def alive(t: dict) -> bool:
        return (
            isinstance(t, dict)
            and _same_project(t.get("worktreePath"), project)
            and str(t.get("orphaned")).lower() != "true"
            and str(t.get("connected")).lower() != "false"
        )

    terminals = _orca(["terminal", "list", "--json"]).get("terminals") or []
    here = {t["handle"]: t for t in terminals if isinstance(t, dict) and t.get("handle") and alive(t)}
    if not here:
        return None

    # Strongest signal: a Run that names one of this project's live terminals.
    runs = _orca(["orchestration", "run-list", "--json"]).get("runs") or []
    runs.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    for r in runs:
        if r.get("coordinator_handle") in here:
            return r["coordinator_handle"]

    # Fallback, because a Run outlives the terminal it names. Runs persist for
    # weeks while terminals are closed and recreated, so `coordinator_handle`
    # goes stale and the strong signal simply stops matching anything.
    #
    # The discriminator that still holds: **a coordinator sits in the project
    # directory itself, workers sit in their own worktrees.** So an agent
    # terminal whose worktreePath IS the project is the orchestrator. Terminals
    # without an `agentIdentity` are plain shells and are never it.
    agents = [t for t in here.values() if t.get("agentIdentity")]
    if len(agents) == 1:
        return agents[0]["handle"]
    if agents:
        # More than one agent in the project root is ambiguous, and waking the
        # wrong one is worse than waking none. Prefer the most recently active.
        agents.sort(key=lambda t: int(t.get("lastOutputAt") or 0), reverse=True)
        return agents[0]["handle"]
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


def user_is_away(project: str) -> bool:
    """Read britania-afk's marker rather than trusting a flag.

    `--present` was a flag someone had to remember to pass, and the one time it
    is wrong is the time it matters. The AFK marker is the same signal, already
    written deliberately by the person who left.
    """
    marker = Path(project) / ".lelouch" / "afk.json"
    if not marker.exists():
        return False
    try:
        json.loads(marker.read_text(encoding="utf-8"))
        return True
    except (OSError, json.JSONDecodeError):
        return False


def session_can_reply(v: dict) -> bool:
    """Is there anyone home to hear a wake?

    A binding window at exactly 0% is not "nearly out", it is out, and every
    line sent into that session comes back *"you've hit your session limit"*.
    Eight wake injections once landed in a session in precisely that state: the
    breach had disabled the reader the breach was addressed to.

    This is the one condition where the usual delegation -- *"a level that is
    still bad is still worth saying, and de-duplication belongs to whoever reads
    it"* -- cannot hold, because the reader is structurally incapable of
    performing its half. Anything above 0 keeps the delegation; only 0 is
    hopeless. An unavailable reading (None) is not 0 and still gets woken: not
    knowing the quota is no reason to stay quiet about the disk.
    """
    return v.get("quota_pct") != 0


def memory_collapsed(free_gb: float | None, history: list[float]) -> bool:
    """Did memory take a step down, stay down, and land somewhere dangerous?

    **Both halves, never either**, because each one alone is a false-alarm
    generator with this machine's data behind it:

    - *The floor alone fires on churn.* Free RAM here wanders across whatever
      line you draw -- three dips under 2GB in forty-five minutes, every one
      recovered by the next reading, not one of them a kill.
    - *The step alone fires on a harmless drop.* 8GB falling to 6GB and staying
      is a large sustained step and entirely fine: something launched, and there
      is still ample headroom.

    What is worth a wake is the intersection: a fall big enough to be a program
    taking memory and keeping it, which also leaves the machine somewhere it
    cannot afford. 2.2GB -> 0.4GB held is that. 1.92GB for one minute is not,
    and neither is a machine that has simply been low all along -- no step, no
    news, and the latch already said what there was to say.

    `history` is the previous readings, oldest first. Without a window there is
    nothing to compare against, so the very first run never alarms on memory;
    the floor is a backstop here, not the trigger.
    """
    if free_gb is None or free_gb >= FREE_GB_FLOOR:
        return False
    recent = [free_gb, *reversed(history)][:MEM_SUSTAIN]
    if len(recent) < MEM_SUSTAIN or any(r >= FREE_GB_FLOOR for r in recent):
        return False  # a dip, not a level
    return bool(history) and max(history) - free_gb >= MEM_STEP_GB


STATE_FILE = ".lelouch/vitals-state.json"  # beside britania-afk's marker


def load_state(project: str) -> dict:
    """What the last tick saw. Missing or unreadable means "nothing yet".

    File-held state in a stateless one-shot deserves suspicion, so be precise
    about what it can cost. **This file never decides what to send, only whether
    to repeat it.** Every message is driven by the reading taken from the
    machine this tick. So a lost or corrupt write produces a duplicate park, or
    a duplicate all-clear -- one wasted turn -- and it cannot produce an
    inverted one. That asymmetry is why `--once` is allowed to keep state at all.
    """
    try:
        data = json.loads((Path(project) / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(project: str, state: dict) -> None:
    path = Path(project) / STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass  # see load_state: this costs a duplicate message and nothing else


def tick(args, handle: str | None) -> dict:
    """One check: wake on a new breach, wake again when it lifts, else say nothing.

    **The pairing is the point.** There used to be exactly one `wake()` here with
    one fixed text, which made the watcher a ratchet -- it could only ever reduce
    activity. A transient dip converted a live run into a parked one
    *permanently*, and nothing but a human ever converted it back. It said
    "park" every fifteen minutes indefinitely and "resume" under no condition at
    all. Recovery therefore depended on exactly the unreliable attention the
    watcher exists to compensate for.

    So there are two directions now, and a latch across ticks so that each is
    said once per episode rather than once per reading.
    """
    v = collect(args.path, args.provider)
    state = load_state(args.path)
    parked: set[str] = set(state.get("parked") or [])
    history = [float(x) for x in (state.get("mem_free_history") or [])
               if isinstance(x, (int, float))]

    breaching = {b.split()[0] for b in v["blocks"]}
    if "memory" in breaching and not memory_collapsed(v["mem_free"], history):
        # Under the floor, but not a step that stuck. See memory_collapsed.
        breaching.discard("memory")
        print(f"{datetime.now():%H:%M:%S}  memory {v['mem_free']:.2f}GB under the floor, "
              f"no sustained step -- not alarming", flush=True)
    recovered = {c.split()[0] for c in v["clears"]} - breaching

    # Explicit --present still wins; otherwise the marker decides.
    present = args.present or not user_is_away(args.path)

    def say(detail: str, text: str, label: str) -> None:
        print(f"{datetime.now():%H:%M:%S}  {label}  {detail}", flush=True)
        if present:
            # C.C is at the keyboard: warn, never act for them.
            print("        (user present -- warning only, taking no action)", flush=True)
        elif not session_can_reply(v):
            print("        (session at 0% quota -- it cannot answer, so not waking it)", flush=True)
        else:
            wake(handle, text, args.dry_run)

    for kind in sorted(breaching - parked):
        detail = next(b for b in v["blocks"] if b.startswith(kind))
        say(detail, f"britania-vitals: {detail}. Stop dispatching and park the run.", "BREACH")

    for kind in sorted(parked & recovered):
        detail = next(c for c in v["clears"] if c.startswith(kind))
        say(detail, f"britania-vitals: {detail}. If the run was parked for it, "
                    f"the hold is lifted and you may resume.", "CLEAR ")

    if v["quota_pct"] is not None and v["quota_pct"] < QUOTA_FLOOR and v["resets_at"]:
        print(f"{datetime.now():%H:%M:%S}  quota resets in {v['resets_in']}", flush=True)

    state["parked"] = sorted((parked | breaching) - recovered)
    if v["mem_free"] is not None:
        history.append(v["mem_free"])
    state["mem_free_history"] = history[-MEM_HISTORY:]
    if args.dry_run:
        # A dry run that latched would make the next real run think it had
        # already spoken -- which is the one way this file could lose a message.
        print(f"[dry-run] would remember parked={state['parked']}")
    else:
        save_state(args.path, state)
    return v


def once(args) -> int:
    """Check once, wake if needed, exit. **This is the mode a scheduler runs.**

    Preferred over `--watch` for anything unattended, and the reason is this
    machine's own history: a long-lived watcher is a process that can die
    without saying so, and a monitor that has gone quiet looks exactly like a
    healthy one. A scheduled one-shot has nothing to keep alive -- if a run is
    missed the scheduler records it, and the next one still fires. *Records*,
    not announces: that record is `LastTaskResult`, and it is only a safety net
    if something reads it. `geass doctor` does.

    A one-shot has no memory of its own, so what it must not repeat is written
    down -- see `load_state`. It carries the latch and the memory window, and
    nothing else: the decision is always taken from the machine, never from the
    file. The older rule here was that a standing breach should re-alarm every
    tick because *"de-duplication belongs to whoever reads it"*. That reasoning
    holds whenever the reader can read, and the latch costs it nothing; it is
    the case where the breach silences the reader that it never covered, and
    that case is `session_can_reply`.

    **Two ways to wake nobody, and only one of them is fine.** An idle machine
    with no orchestrator open is the normal case and exits 0 -- alarming on it
    would make the scheduler's record useless through sheer noise. Being unable
    to *ask* is the other case: if `orca` cannot be resolved at all, this cannot
    do its job and must say so with a non-zero exit, because the only surface a
    scheduled task has is its result code.
    """
    if resolve("orca") is None:
        print("orca not found; cannot see the session, so nothing is being watched",
              file=sys.stderr)
        return 3

    handle = args.terminal or coordinator_handle(args.path)
    if not handle and not args.dry_run:
        print("no coordinator terminal found; nothing to wake", file=sys.stderr)
        return 0
    tick(args, handle)
    return 0


def watch(args) -> int:
    """Stay resident and poll. Useful in a foreground terminal you are watching;
    for anything unattended prefer `--once` on a scheduler (see above)."""
    handle = args.terminal or coordinator_handle(args.path)
    if not handle and not args.dry_run:
        print("no coordinator terminal found; pass --terminal <handle>", file=sys.stderr)
        return 2

    print(f"vitals watching every {args.interval}s  ->  {handle or '(dry run)'}", flush=True)
    while True:
        # The latch lives in the state file rather than in this loop, so a
        # foreground watcher and a scheduled one-shot cannot disagree about what
        # has already been said -- and restarting this process does not re-alarm
        # everything that was already reported.
        tick(args, handle)
        time.sleep(args.interval)


def main() -> int:
    ap = argparse.ArgumentParser(description="Machine and session vitals.")
    ap.add_argument("--gate", action="store_true",
                    help="for the orchestrator: exit 0 = clear to dispatch, 1 = hold")
    ap.add_argument("--breach", action="store_true",
                    help="for an automation precheck: exit 0 = there IS a breach, 1 = nothing to do")
    ap.add_argument("--once", action="store_true",
                    help="auto mode, scheduler-friendly: check once, wake on a breach, exit")
    ap.add_argument("--watch", action="store_true", help="stay resident and poll (foreground use)")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--interval", type=int, default=300, help="seconds between checks in --watch")
    ap.add_argument("--terminal", help="coordinator terminal handle for --watch")
    ap.add_argument("--present", action="store_true",
                    help="force warn-only; otherwise britania-afk's marker decides")
    ap.add_argument("--dry-run", action="store_true", help="print what --watch would send")
    ap.add_argument("--path", default=os.getcwd(), help="volume to measure disk on")
    ap.add_argument("--provider", default="claude")
    args = ap.parse_args()

    if args.once:
        return once(args)
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
