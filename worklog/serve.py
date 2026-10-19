"""Serve the built site on the loopback interface only."""

from __future__ import annotations

import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from worklog.config import LOOPBACK, ConfigError


def ensure_loopback(host: str) -> str:
    """Map a configured host to a loopback address, or refuse."""
    if host not in LOOPBACK:
        raise ConfigError("refusing to bind %s; the work log stays on this machine" % host)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ConfigError("could not resolve %s" % host) from exc
    ips = {info[4][0] for info in infos}
    for ip in ips:
        if not _is_loopback(ip):
            raise ConfigError("refusing to bind %s; the work log stays on this machine" % host)
    if host == "::1" or (ips and ips <= {"::1"}):
        return "::1"
    return "127.0.0.1"


def _is_loopback(ip: str) -> bool:
    if ip == "0.0.0.0":
        return False
    try:
        packed = socket.inet_aton(ip) if ":" not in ip else None
    except OSError:
        packed = None
    if packed is not None:
        return packed[0] == 127
    try:
        return ip == "::1" or ip.startswith("::ffff:127.")
    except Exception:
        return False


def make_handler(directory: Path):
    root = str(directory)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            print("%s - %s" % (self.address_string(), fmt % args))

        def list_directory(self, path):  # noqa: ARG002 — directory listings stay off
            self.send_error(404, "Not found")
            return None

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            super().end_headers()

    return Handler


def start_server(directory: Path, host: str, port: int) -> ThreadingHTTPServer:
    bind = ensure_loopback(host)
    handler = make_handler(directory)
    server = ThreadingHTTPServer((bind, int(port)), handler)
    return server


def serve_forever(directory: Path, host: str, port: int) -> None:
    server = start_server(directory, host, port)
    bound_host, bound_port = server.server_address[:2]
    shown = "127.0.0.1" if bound_host in ("127.0.0.1", "0.0.0.0") else bound_host
    print("serving http://%s:%s/" % (shown, bound_port))
    print("local only — press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
