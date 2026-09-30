"""Atomic JSON writer. Refuses to write inside the game folder."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class JsonLogger:
    def __init__(self, out_dir: Path, game_dir: Path | None = None, filename: str = "telemetry-state.json"):
        out = Path(out_dir).resolve()
        if game_dir is not None:
            g = Path(game_dir).resolve()
            if out == g or g in out.parents:
                raise ValueError(f"output directory must not be inside the game folder: {out}")
        out.mkdir(parents=True, exist_ok=True)
        self.path = out / filename
        self._tmp = out / (filename + ".tmp")

    def write(self, doc: dict) -> bool:
        self._tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        for _ in range(5):
            try:
                os.replace(self._tmp, self.path)
                return True
            except PermissionError:  # a reader has the file open
                time.sleep(0.02)
        return False
