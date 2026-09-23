"""Local HTTP server for the NEXUS-MFP research terminal."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .data import DashboardRepository, MarketCache
from .progress import RunProgress


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"


class RunManager:
    """Own exactly one subprocess and expose its observable progress."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.progress = RunProgress()
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None

    def start(self, mode: str) -> tuple[bool, str]:
        if mode not in {"standard", "causal"}:
            return False, "Modo inválido"
        with self._lock:
            if self._process and self._process.poll() is None:
                return False, "Ya existe una ejecución activa"
            workspace = self.root / "runtime" / "terminal_workspace"
            workspace.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, "-u", str(self.root / "src" / "nexus_mfp.py")]
            if mode == "causal":
                command.append("--causal")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.root / "src")
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.progress.start(mode)
            try:
                self._process = subprocess.Popen(
                    command,
                    cwd=workspace,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creationflags,
                )
            except OSError as exc:
                self.progress.ingest(f"No se pudo iniciar: {exc}")
                self.progress.finish(1)
                return False, str(exc)
            self.progress.set_pid(self._process.pid)
            threading.Thread(target=self._watch, daemon=True).start()
            return True, "Ejecución iniciada"

    def _watch(self) -> None:
        process = self._process
        if process is None:
            return
        assert process.stdout is not None
        for line in process.stdout:
            self.progress.ingest(line)
        self.progress.finish(process.wait())

    def snapshot(self) -> dict:
        return self.progress.snapshot()


class TerminalApplication:
    def __init__(self, root: Path):
        self.repository = DashboardRepository(root)
        self.market = MarketCache()
        self.runs = RunManager(root)
        self.market.refresh_async()


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


def handler_factory(app: TerminalApplication):
    class TerminalHandler(BaseHTTPRequestHandler):
        server_version = "NexusTerminal/1.0"

        def log_message(self, fmt: str, *args) -> None:
            sys.stdout.write("[terminal] " + (fmt % args) + "\n")

        def _headers(self, status: int, content_type: str, length: int, cache: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                "style-src 'self'; script-src 'self'; font-src 'self'",
            )
            self.end_headers()

        def _json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body), "no-store")
            self.wfile.write(body)

        def _body(self) -> dict:
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 16_384)
                return json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return {}

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/health":
                self._json({"ok": True, "service": "nexus-terminal"})
                return
            if path == "/api/dashboard":
                self._json(app.repository.snapshot())
                return
            if path == "/api/market":
                self._json(app.market.snapshot())
                return
            if path == "/api/run":
                self._json(app.runs.snapshot())
                return
            static_map = {
                "/": STATIC / "index.html",
                "/index.html": STATIC / "index.html",
                "/styles.css": STATIC / "styles.css",
                "/app.js": STATIC / "app.js",
            }
            file_path = static_map.get(path)
            if file_path is None or not file_path.exists():
                self._json({"error": "No encontrado"}, HTTPStatus.NOT_FOUND)
                return
            body = file_path.read_bytes()
            content_type = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
            self._headers(HTTPStatus.OK, content_type, len(body), "no-cache")
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/market/refresh":
                started = app.market.refresh_async()
                self._json({"started": started, **app.market.snapshot()}, HTTPStatus.ACCEPTED)
                return
            if path == "/api/run":
                mode = str(self._body().get("mode", "standard"))
                started, message = app.runs.start(mode)
                status = HTTPStatus.ACCEPTED if started else HTTPStatus.CONFLICT
                self._json(
                    {"started": started, "message": message, **app.runs.snapshot()},
                    status,
                )
                return
            self._json({"error": "No encontrado"}, HTTPStatus.NOT_FOUND)

    return TerminalHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="NEXUS-MFP Research Terminal")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("Por seguridad, el terminal sólo puede enlazarse a localhost")
    app = TerminalApplication(ROOT)
    server = ThreadingHTTPServer((args.host, args.port), handler_factory(app))
    print(f"NEXUS Research Terminal: http://{args.host}:{args.port}")
    print("PAPER/RESEARCH ONLY · no ejecuta operaciones reales")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
