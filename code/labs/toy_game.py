"""Toy 'game' for Lab 3: builds Manager -> PlayerIns -> PlayerGameData in memory.

Run it, note the printed PID and ROOT address, then read it from another process
with labs/toy_reader.py. Every run prints DIFFERENT addresses for the heap objects.
"""
import ctypes
import os
import time


class PlayerGameData(ctypes.Structure):
    _fields_ = [("pad0", ctypes.c_uint8 * 0x68), ("level", ctypes.c_uint32), ("runes", ctypes.c_uint32)]


class PlayerIns(ctypes.Structure):
    _fields_ = [("pad0", ctypes.c_uint8 * 0x580), ("game_data", ctypes.c_void_p)]


class Manager(ctypes.Structure):
    _fields_ = [("player", ctypes.c_void_p)]  # offset 0 -> PlayerIns


gd = PlayerGameData()
gd.level, gd.runes = 42, 1000
player = PlayerIns()
player.game_data = ctypes.addressof(gd)
manager = Manager()
manager.player = ctypes.addressof(player)

# ROOT plays the role of "eldenring.exe + RVA": a fixed place that holds a pointer.
root = ctypes.c_void_p(ctypes.addressof(manager))

if __name__ == "__main__":
    print(f"PID  = {os.getpid()}")
    print(f"ROOT = 0x{ctypes.addressof(root):X}   (holds a pointer to Manager)")
    print(f"(spoiler) PlayerIns at 0x{ctypes.addressof(player):X}, PlayerGameData at 0x{ctypes.addressof(gd):X}")
    while True:
        gd.runes += 100
        time.sleep(1)
