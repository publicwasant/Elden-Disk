"""Lab 3 reader: walks ROOT -> +0 -> +0x580 -> (+0x68 level, +0x6C runes) using the project's own code.

Usage (Windows, 64-bit Python, from the folder that contains elden_telemetry/):
    python labs/toy_reader.py <PID> <ROOT hex>
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root

from elden_telemetry.memory_reader import ProcessMemory, is_user_ptr, read_ptr, read_u32

pid, root = int(sys.argv[1]), int(sys.argv[2], 16)
mem = ProcessMemory(pid)
try:
    while mem.alive():
        manager = read_ptr(mem, root)                 # [ROOT]
        player = read_ptr(mem, manager + 0x0) if manager and is_user_ptr(manager) else None
        gd = read_ptr(mem, player + 0x580) if player and is_user_ptr(player) else None
        if gd and is_user_ptr(gd):
            print(f"level={read_u32(mem, gd + 0x68)} runes={read_u32(mem, gd + 0x6C)}")
        else:
            print("chain not resolvable")
        time.sleep(1)
finally:
    mem.close()
