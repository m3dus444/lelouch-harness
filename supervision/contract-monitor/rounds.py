# -*- coding: utf-8 -*-
"""Per-round finding ids for a branch, to test convergence (F-058)."""
import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = "file:C:/Users/JulienH\u00e9lie/.no-mistakes/state.sqlite?mode=ro"


def ids(blob):
    """findings_json is nested and inconsistent; dig out ids wherever they live."""
    if not blob or blob == "null":
        return []
    try:
        d = json.loads(blob)
    except Exception:
        return []
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "id" in node and isinstance(node["id"], str):
                found.append((node["id"], node.get("severity", "?")))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(d)
    return found


def main(pattern):
    cx = sqlite3.connect(DB, uri=True, timeout=10)
    run = cx.execute(
        "select id, status from runs where branch like ?"
        " order by created_at desc limit 1", (f"%{pattern}",)).fetchone()
    if not run:
        print("no run for", pattern)
        return
    print(f"=== {pattern}   run {run[0]}  ({run[1]})")

    steps = cx.execute(
        "select id, step_name, status from step_results where run_id = ?"
        " order by step_order", (run[0],)).fetchall()

    seen_before: set[str] = set()
    for sid, name, sstatus in steps:
        rounds = cx.execute(
            "select round, findings_json, selected_finding_ids, duration_ms"
            "  from step_rounds where step_result_id = ? order by round", (sid,)).fetchall()
        if not rounds:
            continue
        print(f"\n  step {name} ({sstatus})")
        for rnd, fj, selected, dur in rounds:
            got = ids(fj)
            fresh = [i for i, _s in got if i not in seen_before]
            mins = f"{dur/60000:.0f}m" if dur else "-"
            print(f"    round {rnd}  {len(got)} findings, {len(fresh)} never seen before  [{mins}]")
            for i, sev in got:
                mark = "NEW " if i in fresh else "rpt "
                print(f"        {mark}{sev:<8} {i}")
            seen_before.update(i for i, _s in got)
            if selected and selected not in ("null", "[]"):
                try:
                    sel = json.loads(selected)
                    print(f"        selected for fix: {len(sel)} -> {', '.join(sel)[:120]}")
                except Exception:
                    pass


if __name__ == "__main__":
    for pat in sys.argv[1:] or ["wa-landing-route"]:
        main(pat)
        print()
