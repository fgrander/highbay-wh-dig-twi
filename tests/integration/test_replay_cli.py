import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from highbay_sim import viewer_server
from highbay_sim.cli import main

ROOT = Path(__file__).parents[2]
WAREHOUSE = ROOT / "samples" / "small-warehouse.yaml"
SCENARIO = ROOT / "samples" / "daily-scenario.yaml"
RESULT_FILES = ("report.md", "result.json", "orders.csv")


def run(output: Path, *options: str) -> int:
    return main(["run", str(WAREHOUSE), str(SCENARIO), "--output", str(output), *options])


def run_in_process(output: Path, hash_seed: int) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "highbay_sim.cli",
            "run",
            str(WAREHOUSE),
            str(SCENARIO),
            "--output",
            str(output),
            "--replay",
        ],
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONHASHSEED": str(hash_seed)},
    )


def test_replay_option_writes_replay_file(tmp_path: Path) -> None:
    assert run(tmp_path, "--replay") == 0
    replay = json.loads((tmp_path / "replay.json").read_text(encoding="utf-8"))
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert replay["format_version"] == 1
    assert replay["run"] == result["run"]


def test_no_replay_file_without_the_option(tmp_path: Path) -> None:
    assert run(tmp_path) == 0
    assert not (tmp_path / "replay.json").exists()


def test_result_files_are_byte_identical_with_and_without_replay(tmp_path: Path) -> None:
    assert run(tmp_path / "without") == 0
    assert run(tmp_path / "with", "--replay") == 0
    for name in RESULT_FILES:
        assert (tmp_path / "without" / name).read_bytes() == (tmp_path / "with" / name).read_bytes()


def test_replay_file_is_byte_identical_across_processes(tmp_path: Path) -> None:
    run_in_process(tmp_path / "a", hash_seed=1)
    run_in_process(tmp_path / "b", hash_seed=2)
    assert (tmp_path / "a" / "replay.json").read_bytes() == (
        tmp_path / "b" / "replay.json"
    ).read_bytes()


def test_replay_file_has_unix_line_endings_and_no_machine_details(tmp_path: Path) -> None:
    assert run(tmp_path, "--replay") == 0
    content = (tmp_path / "replay.json").read_bytes()
    assert b"\r" not in content
    text = content.decode("utf-8")
    assert os.environ.get("COMPUTERNAME", "no-such-machine-name") not in text
    assert str(Path.home()).replace("\\", "\\\\") not in text
    assert str(tmp_path).replace("\\", "\\\\") not in text


def test_existing_replay_file_fails_without_overwrite(tmp_path: Path) -> None:
    assert run(tmp_path, "--replay") == 0
    original = (tmp_path / "replay.json").read_bytes()
    for name in RESULT_FILES:
        (tmp_path / name).unlink()
    assert run(tmp_path, "--replay") == 1
    assert run(tmp_path) == 1
    assert (tmp_path / "replay.json").read_bytes() == original
    assert not (tmp_path / "result.json").exists()


def test_overwrite_with_replay_replaces_it(tmp_path: Path) -> None:
    assert run(tmp_path, "--replay") == 0
    expected = (tmp_path / "replay.json").read_bytes()
    (tmp_path / "replay.json").write_text("old", encoding="utf-8")
    assert run(tmp_path, "--replay", "--overwrite") == 0
    assert (tmp_path / "replay.json").read_bytes() == expected


def test_overwrite_without_replay_deletes_it(tmp_path: Path) -> None:
    assert run(tmp_path, "--replay") == 0
    assert run(tmp_path, "--overwrite") == 0
    assert not (tmp_path / "replay.json").exists()
    assert (tmp_path / "result.json").is_file()


def test_run_with_replay_loads_no_graphical_module(tmp_path: Path) -> None:
    code = (
        "import sys\n"
        "from highbay_sim.cli import main\n"
        f"code = main(['run', {str(WAREHOUSE)!r}, {str(SCENARIO)!r}, '--output', "
        f"{str(tmp_path / 'out')!r}, '--replay'])\n"
        "graphical = {'tkinter', 'turtle', 'PyQt5', 'PyQt6', 'PySide6', 'wx', 'pygame', "
        "'pyglet', 'matplotlib', 'OpenGL', 'webbrowser', 'http.server'}\n"
        "assert not graphical & set(sys.modules), graphical & set(sys.modules)\n"
        "sys.exit(code)\n"
    )
    environment = {key: value for key, value in os.environ.items() if key != "DISPLAY"}
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, env=environment)
    assert (tmp_path / "out" / "replay.json").is_file()


def test_view_with_missing_path_exits_with_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["view", str(tmp_path / "missing"), "--no-browser"]) == 2
    assert "missing" in capsys.readouterr().err


def test_view_with_directory_without_replay_exits_with_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["view", str(tmp_path), "--no-browser"]) == 2
    assert "replay.json" in capsys.readouterr().err


def stop_at_once(self: object) -> None:
    raise KeyboardInterrupt


def test_view_prints_address_and_stops_with_zero_on_ctrl_c(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "replay.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(viewer_server.ViewerServer, "serve_forever", stop_at_once)
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", opened.append)

    assert main(["view", str(tmp_path), "--no-browser"]) == 0
    printed = capsys.readouterr().out
    assert "http://127.0.0.1:" in printed
    assert "Ctrl+C" in printed
    assert opened == []


def test_view_opens_the_browser_by_default_and_accepts_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replay = tmp_path / "replay.json"
    replay.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(viewer_server.ViewerServer, "serve_forever", stop_at_once)
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", opened.append)

    assert main(["view", str(replay)]) == 0
    assert len(opened) == 1
    assert opened[0].startswith("http://127.0.0.1:")


def test_view_with_unusable_port_exits_with_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "replay.json").write_text("{}", encoding="utf-8")
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        code = main(["view", str(tmp_path), "--no-browser", "--port", str(port)])
    assert code == 1
    assert str(port) in capsys.readouterr().err
