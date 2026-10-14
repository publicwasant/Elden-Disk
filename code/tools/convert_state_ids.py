"""One-off: turn an old flat names.json (`{id: {name, sources, ...}}`) into the 1.6.3 shape
(`{"buffs": {id: {...}}, "animations": {id: {...}}}`, no `sources`). Stdlib only.

    python tools/convert_state_ids.py names.json            # writes names.json.bak, then the new file
    python tools/convert_state_ids.py old.json --out new.json       # leaves old.json alone

An entry whose `sources` is ANIMATIONS goes to `animations`, every other one (EFFECTS, a missing `sources`) to `buffs`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def convert(old: dict) -> dict:
    out: dict = {"buffs": {}, "animations": {}}
    for key, item in old.items():
        if str(key).startswith("_"):
            continue
        if not isinstance(item, dict):
            raise ValueError(f"entry {key!r} is not an object")
        item = dict(item)
        kind = "animations" if item.pop("sources", "EFFECTS") == "ANIMATIONS" else "buffs"
        out[kind][str(key)] = item
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", type=Path)
    ap.add_argument("--out", type=Path, help="write here instead of replacing PATH (no .bak)")
    args = ap.parse_args(argv)
    data = json.loads(args.path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and {"buffs", "animations"} & set(data):
        print(f"{args.path}: already in the new shape", file=sys.stderr)
        return 1
    new = convert(data)
    if args.out is None:
        shutil.copyfile(args.path, args.path.with_name(args.path.name + ".bak"))
    (args.out or args.path).write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(new['buffs'])} buffs, {len(new['animations'])} animations -> {args.out or args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
