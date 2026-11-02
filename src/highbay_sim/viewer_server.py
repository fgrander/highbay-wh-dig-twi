"""The read-only local server for the viewer, as in contracts/cli.md.

It can only be reached from the same computer, answers only GET and HEAD, and serves only the
viewer's own files and the chosen replay file.
"""

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

VIEWER_DIRECTORY = Path(__file__).parent / "viewer"
LOCAL_ADDRESS = "127.0.0.1"
REPLAY_ROUTE = "/replay.json"
JSON_TYPE = "application/json"
# Explicit, as the types registered on a Windows computer can stop browsers running modules.
CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows, address reuse would let this server share a port that is already in use.
    allow_reuse_address = False

    def __init__(self, replay_path: Path, port: int) -> None:
        super().__init__((LOCAL_ADDRESS, port), _Handler)
        self.replay_path = replay_path

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def address(self) -> str:
        return f"http://{LOCAL_ADDRESS}:{self.port}/"


def create_server(replay_path: Path, port: int = 0) -> ViewerServer:
    """Create a server for one replay file; port 0 chooses a free port."""
    return ViewerServer(replay_path, port)


class _Handler(BaseHTTPRequestHandler):
    server: ViewerServer

    def do_GET(self) -> None:
        self._respond(include_body=True)

    def do_HEAD(self) -> None:
        self._respond(include_body=False)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the terminal free of request logs."""

    def _respond(self, include_body: bool) -> None:
        found = self._find_file()
        if found is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path, content_type = found
        try:
            content = path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(content)

    def _find_file(self) -> tuple[Path, str] | None:
        route = unquote(urlsplit(self.path).path)
        if route == REPLAY_ROUTE:
            return self.server.replay_path, JSON_TYPE
        relative = "index.html" if route == "/" else route.lstrip("/")
        path = (VIEWER_DIRECTORY / relative).resolve()
        content_type = CONTENT_TYPES.get(path.suffix)
        if content_type is None or not path.is_file():
            return None
        if not path.is_relative_to(VIEWER_DIRECTORY.resolve()):
            return None
        return path, content_type
