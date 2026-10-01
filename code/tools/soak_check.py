"""V-06 helper: watch output/telemetry-state.json and report anything wrong. Stdlib only.

    python tools/soak_check.py [path] [--interval 0.1]

Prints state transitions as they happen, flags invalid/out-of-range documents and a stalled
writer, and prints a summary on Ctrl+C. Exit code 1 if any problem was seen.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

STATES = {"WAITING_FOR_PROCESS", "EAC_ACTIVE", "EAC_DETECTED", "UNSUPPORTED_VERSION",
          "WAITING_FOR_WORLD", "CONNECTED", "DISCONNECTED"}
ATTRS = ("vigor", "mind", "endurance", "strength", "dexterity", "intelligence", "faith", "arcane")
STALE_AFTER = 3.0  # seconds without a new timestamp


def check(doc: dict) -> list[str]:
    """Problems found in one telemetry document (empty list = fine)."""
    try:
        st, ch, tel = doc["system_status"], doc["character"], doc["telemetry"]
        state = st["state"]
    except (KeyError, TypeError):
        return ["missing top-level keys"]
    out: list[str] = []
    if state not in STATES:
        out.append(f"unknown state {state!r}")
    if st.get("read_only") is not True:
        out.append("read_only is not true")
    if state != "CONNECTED":
        if ch is not None:
            out.append(f"character present while state={state}")
        return out
    if not isinstance(ch, dict):
        return out + ["CONNECTED but character is null"]
    if not 1 <= ch["level"] <= 713:
        out.append(f"level {ch['level']} out of range")
    if not 0 <= ch["runes"] <= 999_999_999:
        out.append(f"runes {ch['runes']} out of range")
    attrs = ch.get("attributes", {})
    for name in ATTRS:
        if not 1 <= attrs.get(name, 0) <= 99:
            out.append(f"attribute {name}={attrs.get(name)} out of range")
    for eid, eff in ch.get("effects", {}).items():
        if eff.get("kind") == "TIMED":
            t = eff.get("times", {})
            rem, mx = t.get("buff_duration"), t.get("max_duration")
            if rem is None or mx is None or rem < 0 or mx <= 0 or rem > mx + 1:
                out.append(f"buff {eid} has impossible timer {rem}/{mx}")
    start = tel.get("session_start_runes")
    if start is None or tel.get("rune_delta") != ch["runes"] - start:
        out.append("rune_delta inconsistent with session_start_runes")
    return out


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def watch(path: Path, interval: float = 0.1, duration: float | None = None, out=print) -> dict:
    stats = {"reads": 0, "busy": 0, "invalid_json": 0, "problems": 0, "stale_episodes": 0,
             "states": Counter(), "longest_gap": 0.0}
    last_state = last_err = last_ts = None
    last_change = time.monotonic()
    stale = False
    end = None if duration is None else time.monotonic() + duration
    try:
        _loop(path, interval, end, stats, out, [last_state, last_err, last_ts, last_change, stale])
    except KeyboardInterrupt:
        pass
    return stats


def _loop(path, interval, end, stats, out, st_):
    last_state, last_err, last_ts, last_change, stale = st_
    while end is None or time.monotonic() < end:
        time.sleep(interval)
        text = None
        for _ in range(5):  # the writer swaps the file; a reader can briefly lose the race
            try:
                text = Path(path).read_text(encoding="utf-8")
                break
            except OSError:
                stats["busy"] += 1
                time.sleep(0.02)
        if text is None:
            continue
        stats["reads"] += 1
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            stats["invalid_json"] += 1
            out(f"{_now()} !! INVALID JSON")
            continue
        for p in check(doc):
            stats["problems"] += 1
            out(f"{_now()} !! {p}")
        st = doc.get("system_status", {})
        state, err, ts = st.get("state"), st.get("last_error"), doc.get("timestamp")
        stats["states"][state] += 1
        if (state, err) != (last_state, last_err):
            out(f"{_now()} {last_state or '-'} -> {state}" + (f"  ({err})" if err else ""))
            last_state, last_err = state, err
        mono = time.monotonic()
        if ts != last_ts:
            stats["longest_gap"] = max(stats["longest_gap"], mono - last_change)
            last_ts, last_change, stale = ts, mono, False
        elif mono - last_change > STALE_AFTER and not stale:
            stale = True
            stats["stale_episodes"] += 1
            out(f"{_now()} !! STALE: timestamp has not changed for {STALE_AFTER:.0f}s (tool stopped?)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default=str(Path(__file__).resolve().parent.parent / "output" / "telemetry-state.json"))
    ap.add_argument("--interval", type=float, default=0.1)
    args = ap.parse_args()
    print(f"watching {args.path}  (Ctrl+C for summary)")
    s = watch(Path(args.path), args.interval)
    bad = s["problems"] + s["invalid_json"] + s["stale_episodes"]
    print(f"\nreads={s['reads']} busy-retries={s['busy']} invalid_json={s['invalid_json']} "
          f"problems={s['problems']} stale_episodes={s['stale_episodes']} longest_gap={s['longest_gap']:.2f}s")
    print("states seen:", dict(s["states"]))
    print("RESULT:", "PASS" if bad == 0 else "FAIL")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
