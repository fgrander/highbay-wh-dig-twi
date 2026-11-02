import http.client
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from highbay_sim import viewer_server
from highbay_sim.viewer_server import ViewerServer, create_server

REPLAY_CONTENT = b'{"format_version":1}\n'


@pytest.fixture
def replay_path(tmp_path: Path) -> Path:
    path = tmp_path / "replay.json"
    path.write_bytes(REPLAY_CONTENT)
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    return path


@pytest.fixture
def server(replay_path: Path) -> Iterator[ViewerServer]:
    instance = create_server(replay_path)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()


def request(server: ViewerServer, method: str, path: str) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    connection.putrequest(method, path, skip_accept_encoding=True)
    connection.endheaders()
    return connection.getresponse()


def test_binds_only_to_the_local_computer(server: ViewerServer) -> None:
    assert server.server_address[0] == "127.0.0.1"


def test_chosen_port_is_used(replay_path: Path) -> None:
    first = create_server(replay_path)
    port = first.port
    first.server_close()
    second = create_server(replay_path, port)
    assert second.port == port
    second.server_close()


def test_root_serves_the_viewer_page(server: ViewerServer) -> None:
    response = request(server, "GET", "/")
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("text/html")
    assert b"<" in response.read()


def test_replay_file_is_served_unchanged(server: ViewerServer) -> None:
    response = request(server, "GET", "/replay.json")
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("application/json")
    assert response.read() == REPLAY_CONTENT


def test_damaged_replay_file_is_still_served(server: ViewerServer, replay_path: Path) -> None:
    replay_path.write_bytes(b"{damaged")
    assert request(server, "GET", "/replay.json").read() == b"{damaged"


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/index.html", "text/html"),
        ("/style.css", "text/css"),
        ("/vendor/three.module.min.js", "text/javascript"),
        ("/vendor/three.module.min.js?version=1", "text/javascript"),
    ],
)
def test_content_types_are_explicit(server: ViewerServer, path: str, content_type: str) -> None:
    response = request(server, "GET", path)
    assert response.status == 200
    assert response.getheader("Content-Type").startswith(content_type)


def test_head_gives_headers_without_a_body(server: ViewerServer) -> None:
    response = request(server, "HEAD", "/replay.json")
    assert response.status == 200
    assert response.getheader("Content-Length") == str(len(REPLAY_CONTENT))
    assert response.read() == b""


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
def test_other_methods_are_refused_and_change_nothing(
    server: ViewerServer, replay_path: Path, method: str
) -> None:
    response = request(server, method, "/replay.json")
    assert response.status in (405, 501)
    assert replay_path.read_bytes() == REPLAY_CONTENT


@pytest.mark.parametrize(
    "path",
    [
        "/../viewer_server.py",
        "/%2e%2e/viewer_server.py",
        "/%2E%2E%2Fviewer_server.py",
        "/..%5Cviewer_server.py",
        "/vendor/../../cli.py",
        "/secret.txt",
        "/missing.js",
        "//etc/passwd",
        "/vendor/README.md",
    ],
)
def test_other_paths_are_refused(server: ViewerServer, path: str) -> None:
    assert request(server, "GET", path).status == 404


@pytest.mark.parametrize(
    "path",
    [
        "/../outside.js",
        "/%2e%2e/outside.js",
        "/%2E%2E%2Foutside.js",
        "/..%5Coutside.js",
        "/nested/../../outside.html",
    ],
)
def test_files_of_served_types_outside_the_viewer_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    viewer = tmp_path / "viewer"
    viewer.mkdir()
    (viewer / "inside.js").write_text("inside", encoding="utf-8")
    (tmp_path / "outside.js").write_text("outside", encoding="utf-8")
    (tmp_path / "outside.html").write_text("outside", encoding="utf-8")
    monkeypatch.setattr(viewer_server, "VIEWER_DIRECTORY", viewer)

    instance = create_server(tmp_path / "replay.json")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        assert request(instance, "GET", "/inside.js").status == 200
        assert request(instance, "GET", path).status == 404
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join()
