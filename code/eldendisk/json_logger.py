"""Atomic JSON writer. Refuses to write inside the game folder."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

RETRIES = 5
RETRY_DELAY_S = 0.01


class JsonLogger:
    def __init__(self, out_dir: Path, game_dir: Path | None = None, filename: str = "disk-state.json"):
        out = Path(out_dir).resolve()
        if game_dir is not None:
            g = Path(game_dir).resolve()
            if out == g or g in out.parents:
                raise ValueError(f"output directory must not be inside the game folder: {out}")
        out.mkdir(parents=True, exist_ok=True)
        self.path = out / filename
        self._tmp = out / (filename + ".tmp")

    def write(self, doc: dict) -> bool:
        """True when the file was replaced. False if a reader/antivirus held the file (caller skips this sample)."""
        text = json.dumps(doc, indent=2)
        for _ in range(RETRIES):
            try:
                self._tmp.write_text(text, encoding="utf-8")
                os.replace(self._tmp, self.path)
                return True
            except PermissionError:  # tmp or target locked by another process
                time.sleep(RETRY_DELAY_S)
        return False
