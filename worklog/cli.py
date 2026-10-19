"""Command line: extract, build, serve, and generate the fictional demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from worklog import __version__
from worklog.build import build_site
from worklog.config import ConfigError, default_config_path, load_config
from worklog.extract import extract, write_log
from worklog.serve import serve_forever


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="worklog",
        description="Local dashboard of what your AI agents did. Nothing leaves this machine.",
    )
    parser.add_argument("--version", action="version", version="worklog %s" % __version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    extract_cmd = sub.add_parser("extract", help="Read sources and write a redacted log.json")
    _add_config(extract_cmd)
    extract_cmd.add_argument("-o", "--output", help="Path for log.json (default: <output>/log.json)")
    extract_cmd.set_defaults(func=cmd_extract)

    build_cmd = sub.add_parser("build", help="Extract and write the static dashboard")
    _add_config(build_cmd)
    build_cmd.set_defaults(func=cmd_build)

    serve_cmd = sub.add_parser("serve", help="Serve the dashboard on 127.0.0.1")
    _add_config(serve_cmd)
    serve_cmd.add_argument("--port", type=int, help="Port (default: the port in the config)")
    serve_cmd.add_argument(
        "--rebuild",
        action="store_true",
        help="Extract and rebuild before serving",
    )
    serve_cmd.set_defaults(func=cmd_serve)

    demo_cmd = sub.add_parser("demo", help="Write fictional sample data, then build it")
    demo_cmd.add_argument("--dir", default="demo", help="Directory to write (default: ./demo)")
    demo_cmd.add_argument("--serve", action="store_true", help="Serve the demo after building")
    demo_cmd.add_argument("--port", type=int, help="Port to serve on (default: the demo config)")
    demo_cmd.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-c",
        "--config",
        help="Path to worklog.toml or worklog.json (default: ./worklog.toml or ./worklog.json)",
    )


def _load(args) -> object:
    if getattr(args, "config", None):
        return load_config(Path(args.config))
    found = default_config_path()
    if found is None:
        raise ConfigError(
            "no worklog.toml or worklog.json in the current directory.\n"
            "Copy worklog.example.toml, or run: python -m worklog demo"
        )
    return load_config(found)


def _report(document: dict) -> None:
    for warning in document.get("warnings") or []:
        print(warning, file=sys.stderr)
    for row in document.get("summary") or []:
        tail = ", %d excluded" % row["excluded"] if row.get("excluded") else ""
        print("%s: %d kept%s" % (row["label"], row["kept"], tail))


def cmd_extract(args) -> int:
    cfg = _load(args)
    document = extract(cfg)
    destination = Path(args.output) if args.output else cfg.output / "log.json"
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    write_log(document, destination)
    _report(document)
    print("wrote %s" % destination)
    return 0


def cmd_build(args) -> int:
    cfg = _load(args)
    destination, document = build_site(cfg)
    _report(document)
    copied = document.get("copied") or 0
    print("built %s (%d deliverable file%s)" % (destination / "index.html", copied, "" if copied == 1 else "s"))
    return 0


def cmd_serve(args) -> int:
    cfg = _load(args)
    index = cfg.output / "index.html"
    if args.rebuild or not index.is_file():
        _destination, document = build_site(cfg)
        _report(document)
        print("built %s" % (_destination / "index.html"))
    port = cfg.port if args.port is None else args.port
    serve_forever(cfg.output, cfg.host, port)
    return 0


def cmd_demo(args) -> int:
    from worklog.demo_data import materialize

    root = Path(args.dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    config_path = materialize(root)
    print("wrote fictional demo in %s" % root)
    cfg = load_config(config_path)
    destination, document = build_site(cfg)
    _report(document)
    print("built %s" % (destination / "index.html"))
    if args.serve:
        port = cfg.port if args.port is None else args.port
        serve_forever(destination, cfg.host, port)
    return 0
