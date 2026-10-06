"""The game is started detached from the host's console, so the host's Ctrl+C / console close cannot reach it."""
import subprocess

import eldendisk.host.launcher as launcher


def capture(monkeypatch, platform):
    seen = {}
    monkeypatch.setattr(launcher.sys, "platform", platform)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda cmd, **kw: seen.update(cmd=cmd, **kw) or object())
    launcher.launch(__import__("pathlib").Path("G"))
    return seen


def test_windows_launch_is_detached_from_the_console(monkeypatch):
    seen = capture(monkeypatch, "win32")
    flags = seen["creationflags"]
    assert flags & 0x00000008 and flags & 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    assert seen["stdin"] is subprocess.DEVNULL and seen["stdout"] is subprocess.DEVNULL
    assert seen["cmd"][1] == "-eac-nop-loaded" and seen["env"]["SteamAppId"] == "1245620"


def test_other_platforms_use_no_creation_flags(monkeypatch):
    assert capture(monkeypatch, "linux")["creationflags"] == 0
