"""Run one command and preserve exact argv, output, exit status, and timing."""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--log-dir", default="reports/logs")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        parser.error("missing command")
    root = Path(args.log_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = root / f"{stamp}_{args.name}"
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=args.cwd, text=True, capture_output=True)
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except OSError as exc:
        code, stdout, stderr = 127, "", str(exc) + "\n"
    elapsed = time.monotonic() - start
    Path(str(prefix) + ".stdout.log").write_text(stdout)
    Path(str(prefix) + ".stderr.log").write_text(stderr)
    record = {
        "argv": cmd,
        "cwd": str(Path(args.cwd).resolve()),
        "start_utc": stamp,
        "elapsed_seconds": elapsed,
        "exit_code": code,
        "stdout": str(prefix) + ".stdout.log",
        "stderr": str(prefix) + ".stderr.log",
    }
    Path(str(prefix) + ".json").write_text(json.dumps(record, indent=2) + "\n")
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
