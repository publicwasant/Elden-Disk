"""1.7.2 external scripts: edstdlib (Interface, tools) on a fake backend, the host (threads, pace, a script that fails, ends itself or
hangs, the game closing), the command and the examples."""
import json
import threading
import time
from pathlib import Path

import pytest

import eldendisk.__main__ as cli
import eldendisk.extension.external_scripts  # noqa: F401  (installs `edstdlib`)
from eldendisk.commands import scripts as cmd
from eldendisk.extension.external_scripts import edstdlib as ed
from eldendisk.extension.external_scripts import host
from tests.fake_tools import FakeBackend

EXAMPLES_DIR = Path(__file__).parent / "external_scripts"     # the example scripts: tests here, examples for a person

from edstdlib import *  # noqa: E402,F403  (the way a script imports it)
from edstdlib import Interface, tools  # noqa: E402


# ------------------------------------------------------------------------------------------------------------------------ edstdlib
def test_from_edstdlib_import_star_gives_interface_and_tools_only():
    names = {}
    exec("from edstdlib import *", names)
    assert {k for k in names if not k.startswith("__")} == {"Interface", "Tools", "tools"}


def test_tools_read_gives_the_document_as_an_object():
    with FakeBackend():
        x = tools.read()
        assert x.character.vitals.hit_point.current == 1000 and x.character.attributes.faith == 60
        assert x.params.effects[1621000].effectEndurance == 2.0                       # a number key with [ ]
        rct = x.extension.innovate_items.spells[2230000]
        assert rct is not None and rct.id == "reverse_cursed_technique"
        assert x.extension.innovate_items.spells.reverse_cursed_technique.slot == 1    # a spell also by its label
        assert rct.customs.advanced.colors["SpEffect.1642100"] == "#90D5FF"            # a dotted key whole
        assert rct.customs.advanced.colors.SpEffect[1642100] == "#90D5FF"               # or in two parts
        assert rct.customs.basic["SpEffect.1642100.effectEndurance"] == 20.0
        assert "21951000" in x.character.buffs and x.character.buffs[21951000].name == "reverse_cursed_technique"


def test_a_name_that_is_not_there_says_what_is():
    with FakeBackend():
        x = tools.read()
        with pytest.raises(AttributeError, match="no such value.*vigor"):
            x.character.attributes.charisma


def test_tools_write_writes_only_what_was_changed_and_under_the_part_given():
    with FakeBackend() as b:
        x = tools.read()
        x.character.attributes.vigor = 61
        x.extension.innovate_items.spells[2230000].customs.advanced.colors["SpEffect.1642100"] = "#FF909E"
        assert tools.write(x.extension) is True                                     # only the part under `extension`
        assert b.writes == [("extension.innovate_items.spells.2230000.customs.advanced.colors.SpEffect.1642100", "#FF909E")]
        assert tools.write(x) is True and b.writes[-1] == ("character.attributes.vigor", 61)
        assert tools.write(x) is True and len(b.writes) == 2                        # nothing changed since: nothing written


def test_a_refused_write_is_false_and_in_the_log():
    with FakeBackend(refuse={"character.level"}) as b:
        x = tools.read()
        x.character.level = 200
        x.systems.status.pid = 9
        assert tools.write(x) is False
        assert sum(1 for level, m in b.lines if level == "W" and "not written" in m) == 2


def test_tools_write_wants_the_snapshot_not_the_value():
    with FakeBackend():
        with pytest.raises(TypeError, match="snapshot of tools.read"):
            tools.write("#90D5FF")


def test_a_snapshot_is_its_own_and_the_next_read_sees_what_was_written():
    with FakeBackend():
        x, y = tools.read(), tools.read()
        x.character.attributes.vigor = 70
        assert y.character.attributes.vigor == 60                                   # another snapshot is not changed
        tools.write(x)
        assert tools.read().character.attributes.vigor == 70


def test_without_a_character_reading_in_it_skips_the_loop():
    doc = json.loads(json.dumps(__import__("tests.fake_tools", fromlist=["DOC"]).DOC))
    doc["character"] = None
    calls = []

    class Reads(Interface):
        def loop(self):
            calls.append(1)
            tools.read().character.vitals.hit_point.current

    with FakeBackend(doc) as b:
        b.run(Reads(), loops=3)                                                     # no error: each loop skipped
    assert len(calls) == 3


def test_log_lines_start_with_the_scripts_name():
    class Talk(Interface):
        def loop(self):
            tools.log("hi")
            tools.log("careful", "warn")

    with FakeBackend() as b:
        b.run(Talk())
    assert b.lines == [("I", "Talk: hi"), ("W", "Talk: careful")]


def test_an_interface_class_is_named_after_itself_even_without_super_init():
    class Plain(Interface):
        def __init__(self):
            self.n = 0

        def loop(self):
            self.n += 1

    s = Plain()
    assert s.name == "Plain" and not s.stopping


def test_without_a_backend_edstdlib_says_how_scripts_run():
    old = ed._use(None)
    try:
        with pytest.raises(RuntimeError, match="eldendisk run"):
            tools.read()
    finally:
        ed._use(old)


# ------------------------------------------------------------------------------------------------------------------------ loading
def write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


GOOD = ("from edstdlib import *\nclass A(Interface):\n    every = 0.05\n    def loop(self):\n"
        "        tools.read().character.vitals.hit_point.current\n")


def test_files_are_loaded_one_by_one_and_a_bad_one_says_why(tmp_path):
    write(tmp_path, "a.py", GOOD)
    write(tmp_path, "b_syntax.py", "def (:\n")
    write(tmp_path, "c_none.py", "x = 1\n")
    write(tmp_path, "d_noloop.py", "from edstdlib import *\nclass D(Interface):\n    pass\n")
    write(tmp_path, "_helper.py", "raise SystemExit('never imported')\n")
    write(tmp_path, "e_exit.py", "raise SystemExit(3)\n")
    files = host.script_files(tmp_path)
    assert [f.name for f in files] == ["a.py", "b_syntax.py", "c_none.py", "d_noloop.py", "e_exit.py"]
    got = {f.name: host.load_file(f) for f in files}
    assert [s.name for s in got["a.py"].scripts] == ["A"] and got["a.py"].error is None
    assert "SyntaxError" in got["b_syntax.py"].error and "no Interface class" in got["c_none.py"].error
    assert "has no loop()" in got["d_noloop.py"].error and "SystemExit" in got["e_exit.py"].error


# ------------------------------------------------------------------------------------------------------------------------ the host
@pytest.fixture
def lines(monkeypatch):
    out = []
    host.set_log(lambda level, msg: out.append((level, msg)))
    monkeypatch.setattr(host, "WATCH", 0.02)
    yield out
    host.set_log(lambda level, msg: None)


def supervise(tmp_path, backend, files, seconds=None, until=None):
    end = None if seconds is None else time.monotonic() + seconds
    stop = until or (lambda: end is not None and time.monotonic() >= end)
    old = ed._use(backend)
    try:
        sup = host.Supervisor([host.load_file(f) for f in files], backend.alive, tmp_path / "status.json")
        sup.start()
        sup.watch(stop)
        return sup
    finally:
        ed._use(old)


def test_each_script_runs_in_a_thread_of_its_own_at_its_pace_and_ends_with_teardown(tmp_path, lines):
    f = write(tmp_path / "s", "count.py", "from edstdlib import *\nclass Count(Interface):\n    every = 0.05\n    def setup(self):\n"
              "        self.n, self.threads = 0, set()\n    def loop(self):\n        import threading\n        self.n += 1\n"
              "        self.threads.add(threading.current_thread().name)\n    def teardown(self):\n        self.done = True\n")
    sup = supervise(tmp_path, FakeBackend(), [f], seconds=0.5)
    r = sup.runners[0]
    assert r.state == "stopped" and 3 <= r.script.n <= 12 and r.script.threads == {"script:Count"} and r.script.done
    assert ("OK", "Count: live (every 0.05 s)") in lines
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["scripts"][0]["name"] == "Count" and status["scripts"][0]["state"] == "stopped"


def test_tools_dead_ends_the_script_that_calls_it_even_inside_a_try(tmp_path, lines):
    f = write(tmp_path / "s", "d.py", "from edstdlib import *\nclass D(Interface):\n    every = 0.05\n    def setup(self):\n"
              "        self.n = 0\n    def loop(self):\n        self.n += 1\n        try:\n            if self.n == 2:\n"
              "                tools.dead()\n        except Exception:\n            pass\n    def teardown(self):\n"
              "        type(self).torn = True\n")
    sup = supervise(tmp_path, FakeBackend(), [f], seconds=0.4)
    r = sup.runners[0]
    assert r.state == "stopped" and r.script.n == 2 and type(r.script).torn and r.error is None
    assert any("D: stopped (tools.dead())" in m for _l, m in lines)


def test_a_script_that_fails_is_dead_and_the_others_go_on(tmp_path, lines):
    folder = tmp_path / "s"
    good = write(folder, "a_good.py", GOOD)
    bad = write(folder, "b_bad.py", "from edstdlib import *\nclass Bad(Interface):\n    every = 0.05\n    def loop(self):\n"
                "        raise ValueError('on purpose')\n    def teardown(self):\n        type(self).torn = True\n")
    sup = supervise(tmp_path, FakeBackend(), [good, bad], seconds=0.4)
    a, b = sup.runners
    assert b.state == "dead" and "ValueError: on purpose" in b.error and type(b.script).torn
    assert a.state == "stopped" and a.loops >= 2                               # it ran on after the other one died
    assert any(level == "E" and "Bad: dead: ValueError: on purpose" in m for level, m in lines)
    assert any(level == "D" and "Traceback" in m for level, m in lines)


def test_a_script_that_hangs_is_reported_and_left_behind_and_the_host_still_ends(tmp_path, lines, monkeypatch):
    monkeypatch.setattr(host, "STUCK", 0.2)
    monkeypatch.setattr(host, "JOIN", 0.1)
    release = threading.Event()
    f = write(tmp_path / "s", "hang.py", "from edstdlib import *\nclass Hang(Interface):\n    every = 0.05\n    def loop(self):\n"
              "        type(self).gate.wait(5)\n")
    found = host.load_file(f)
    type(found.scripts[0]).gate = release
    old = ed._use(FakeBackend())
    try:
        sup = host.Supervisor([found], lambda: True, None)
        sup.start()
        t0 = time.monotonic()
        sup.watch(lambda: time.monotonic() - t0 > 0.6)
    finally:
        ed._use(old)
        release.set()
    assert time.monotonic() - t0 < 2.0
    assert any(level == "W" and "Hang: loop() has not returned" in m for level, m in lines)
    assert any(level == "W" and "Hang: did not end within" in m for level, m in lines)


def test_when_the_game_closes_every_script_stops(tmp_path, lines):
    b = FakeBackend()
    f = write(tmp_path / "s", "a.py", GOOD)

    def close_soon():
        time.sleep(0.3)
        b.is_alive = False
    threading.Thread(target=close_soon, daemon=True).start()
    sup = supervise(tmp_path, b, [f], seconds=3)
    assert sup.runners[0].state == "stopped" and ("I", "the game closed: stopping every script") in lines


def test_no_character_in_the_world_skips_a_loop_and_is_not_an_error(tmp_path, lines):
    from tests.fake_tools import DOC
    doc = json.loads(json.dumps(DOC))
    character, doc["character"] = doc["character"], None
    b = FakeBackend(doc)
    f = write(tmp_path / "s", "a.py", GOOD)

    def load_soon():
        time.sleep(0.2)
        b.doc["character"] = character
    threading.Thread(target=load_soon, daemon=True).start()
    sup = supervise(tmp_path, b, [f], seconds=0.5)
    r = sup.runners[0]
    assert r.state == "stopped" and r.skipped >= 1 and r.loops > r.skipped
    assert any(m == "A: waiting, no character in the world" for _l, m in lines)              # said once, not twice in brackets
    assert any("A: a character is in the world again" in m for _l, m in lines)


def test_a_slow_loop_is_said_once_and_off_or_broken_files_are_in_the_status(tmp_path, lines):
    folder = tmp_path / "s"
    slow = write(folder, "a_slow.py", "import time\nfrom edstdlib import *\nclass Slow(Interface):\n    every = 0.05\n"
                 "    def loop(self):\n        time.sleep(0.08)\n")
    off = write(folder, "b_off.py", "from edstdlib import *\nclass Off(Interface):\n    enabled = False\n    def loop(self):\n        pass\n")
    broken = write(folder, "c_broken.py", "def (:\n")
    supervise(tmp_path, FakeBackend(), [slow, off, broken], seconds=0.4)
    assert sum(1 for level, m in lines if level == "W" and "Slow: loop() took" in m) == 1
    states = {s["name"]: s["state"] for s in json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["scripts"]}
    assert states == {"Slow": "stopped", "Off": "off", "c_broken": "failed"}


def test_two_scripts_of_the_same_name_get_told_apart(tmp_path, lines):
    a = write(tmp_path / "s", "one.py", GOOD)
    b = write(tmp_path / "s", "two.py", GOOD)
    sup = supervise(tmp_path, FakeBackend(), [a, b], seconds=0.1)
    assert [r.name for r in sup.runners] == ["A", "A@two"]


# ------------------------------------------------------------------------------------------------------------------------ the examples
def example(name, index=0):
    found = host.load_file(EXAMPLES_DIR / name)
    assert found.error is None, found.error
    return found.scripts[index]


def test_every_example_loads():
    files = host.script_files(EXAMPLES_DIR)
    got = [host.load_file(f) for f in files]
    assert len(files) == 7 and all(f.error is None and f.scripts for f in got)


def test_keep_fp_refills_below_a_fifth():
    with FakeBackend() as b:
        b.run(example("keep_fp.py"))
    assert b.writes == [("character.vitals.focus_point.current", 300)] and any("FP refilled" in m for _l, m in b.lines)


def test_low_hp_warns_once_until_hp_is_back():
    s = example("low_hp.py")
    with FakeBackend() as b:
        b.doc["character"]["vitals"]["hit_point"]["current"] = 100
        ed._set_current(s)
        s.setup()
        s.loop()
        s.loop()
        b.doc["character"]["vitals"]["hit_point"]["current"] = 1900
        s.loop()
        ed._set_current(None)
    assert [level for level, _m in b.lines] == ["W", "I"]


def test_buff_logger_says_what_came_and_went():
    s = example("buff_logger.py")
    with FakeBackend() as b:
        ed._set_current(s)
        s.setup()
        b.doc["character"]["buffs"]["311100"] = {"name": "Gold Scarab"}
        s.loop()
        b.doc["character"]["buffs"].pop("21951000")
        s.loop()
        ed._set_current(None)
    assert b.lines == [("I", "BuffLogger: + 311100 Gold Scarab"), ("I", "BuffLogger: - 21951000")]


def test_eyes_follow_hp_writes_the_colour_of_the_spell_once_per_change():
    s = example("eyes_follow_hp.py")
    key = "extension.innovate_items.spells.2230000.customs.advanced.colors.SpEffect.1642100"
    with FakeBackend() as b:
        ed._set_current(s)
        s.setup()
        b.doc["character"]["vitals"]["hit_point"]["current"] = 100
        s.loop()
        s.loop()
        b.doc["character"]["vitals"]["hit_point"]["current"] = 1900
        s.loop()
        ed._set_current(None)
    assert b.writes == [(key, "#FF909E"), (key, "#90D5FF")]


# ------------------------------------------------------------------------------------------------------------------------ the command
def test_the_list_shows_every_script_and_how_it_ended(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    folder = tmp_path / "s"
    write(folder, "a.py", GOOD)
    write(folder, "b.py", "def (:\n")
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / host.STATUS_FILE).write_text(json.dumps({"updated": "now", "scripts": [{"name": "A", "state": "dead", "loops": 3,
                                                                                   "error": "ValueError: x"}]}), encoding="utf-8")
    assert cli.main(["extension", "external-scripts", "--scripts-dir", str(folder), "--extension-dir", str(ext)]) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "A, every 0.05 s; last run: dead after 3 loop(s) (ValueError: x)" in out and "b.py cannot be loaded: SyntaxError" in out


def test_when_loaded_goes_with_run(capsys):
    with pytest.raises(SystemExit):
        cli.main(["extension", "external-scripts", "--when-loaded"])


def test_run_without_scripts_has_nothing_to_do(tmp_path, monkeypatch):
    monkeypatch.setattr(cmd, "require_windows_x64", lambda: None)
    monkeypatch.setattr(cmd, "default_dir", lambda: tmp_path / "none")
    assert cli.main(["extension", "external-scripts", "--run", "--scripts-dir", str(tmp_path / "empty")]) == 0


def test_run_scripts_runs_them_on_a_backend_until_told(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "WATCH", 0.02)
    f = write(tmp_path / "s", "a.py", GOOD)
    t0 = time.monotonic()
    assert cmd.run_scripts([f], FakeBackend(), tmp_path / "status.json", until=lambda: time.monotonic() - t0 > 0.2) == 0
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["scripts"][0]["state"] == "stopped"
    bad = write(tmp_path / "s2", "b.py", "def (:\n")
    assert cmd.run_scripts([bad], FakeBackend(), None) == 1


def test_run_starts_the_host_only_when_there_are_scripts(tmp_path, monkeypatch):
    import eldendisk.commands.run as run_cmd
    monkeypatch.setattr(cmd, "default_dir", lambda: tmp_path / "none")
    args = cli.build_parser().parse_args(["run", "--scripts-dir", str(tmp_path / "s")])
    assert not run_cmd.has_scripts(args)
    write(tmp_path / "s", "a.py", GOOD)
    assert run_cmd.has_scripts(args)
    seen = []
    run_cmd.start_scripts(args, tmp_path / "vault", spawn=lambda c, **kw: seen.append(c))
    assert seen[0][-6:] == ["extension", "external-scripts", "--run", "--when-loaded", "--scripts-dir", str(tmp_path / "s")]


def test_the_run_console_shows_the_lines_of_the_scripts_and_a_check_mark_when_one_starts(monkeypatch):
    from eldendisk import ui
    monkeypatch.setenv("NO_COLOR", "1")
    import io
    buf = io.StringIO()
    ui.child_line("10-13 03:20:10.026 25728 I scripts  : Heartbeat: live (every 5 s)", stream=buf, show_time=False)
    ui.child_line("10-13 03:20:11.026 25728 D scripts  : not shown", stream=buf, show_time=False)
    ui.child_line("10-13 03:20:12.026 25728 E scripts  : Bad: dead: ValueError: x", stream=buf, show_time=False)
    lines = buf.getvalue().splitlines()
    assert len(lines) == 2 and "Heartbeat: live" in lines[0] and ("✓" in lines[0] or "+" in lines[0]) and "dead" in lines[1]


def test_the_default_scripts_and_every_scripts_dir_are_run_folders_or_files_each_once(tmp_path, monkeypatch):
    default = tmp_path / "defaults"
    write(default, "a.py", GOOD)
    monkeypatch.setattr(cmd, "default_dir", lambda: default)
    extra = write(tmp_path / "more", "b.py", GOOD)
    one = write(tmp_path / "elsewhere", "c.py", GOOD)
    args = cli.build_parser().parse_args(["extension", "external-scripts", "--scripts-dir", str(extra.parent), str(one),
                                          "--scripts-dir", str(default / "a.py"), str(tmp_path / "missing")])
    said = []
    got = cmd.script_paths(args, warn=said.append)
    assert [p.name for p in got] == ["a.py", "b.py", "c.py"]
    assert len(said) == 1 and "missing" in said[0] and "left out" in said[0]


def test_in_the_exe_the_default_scripts_are_the_embedded_ones(tmp_path, monkeypatch):
    embedded, external = tmp_path / "meipass", tmp_path / "dist"
    (embedded / "external-scripts").mkdir(parents=True)
    external.mkdir()
    monkeypatch.setattr(cmd, "runtime_dirs", lambda: (external, embedded))
    assert cmd.default_dir() == embedded / "external-scripts"
    (embedded / "external-scripts").rmdir()
    (external / "external-scripts").mkdir()
    assert cmd.default_dir() == external / "external-scripts"
    monkeypatch.setattr(cmd, "runtime_dirs", lambda: (None, None))
    assert cmd.default_dir() == cmd.DEFAULTS_DIR


def test_run_passes_every_scripts_dir_on(tmp_path):
    import eldendisk.commands.run as run_cmd
    args = cli.build_parser().parse_args(["run", "--scripts-dir", str(tmp_path / "a"), str(tmp_path / "b.py")])
    seen = []
    run_cmd.start_scripts(args, tmp_path / "vault", spawn=lambda c, **kw: seen.append(c))
    assert seen[0][-3:] == ["--scripts-dir", str(tmp_path / "a"), str(tmp_path / "b.py")]


def test_the_wait_for_the_world_of_the_scripts_is_logged_under_their_own_tag(monkeypatch):
    import eldendisk.commands.write as wcmd
    seen = []
    monkeypatch.setattr(wcmd.book, "i", lambda tag, msg: seen.append((tag, msg)))
    monkeypatch.setattr(wcmd, "world_loaded", lambda mem, target: (True, ""))
    clock = iter(range(100))
    monkeypatch.setattr(wcmd, "_clock", lambda: next(clock) * 10.0)
    monkeypatch.setattr(wcmd, "_sleep", lambda s: None)
    mem = type("M", (), {"alive": lambda self: True})()
    assert wcmd._wait_world(mem, None, "external scripts", tag="scripts")
    assert seen == [("scripts", "external scripts: a character is in the world")]


def test_a_group_used_as_a_number_says_which_values_it_has():
    with FakeBackend():
        x = tools.read()
        with pytest.raises(TypeError, match=r"character.runes is a group \(total, baseline, delta\), not a number: use one of its "
                                            r"values, e.g. character.runes.total"):
            x.character.runes += 50
        with pytest.raises(TypeError, match="is a group"):
            x.character.vitals.hit_point < 500
        x.character.runes.total += 50                                                 # the value itself is a number
        assert x.character.runes.total == 1284
