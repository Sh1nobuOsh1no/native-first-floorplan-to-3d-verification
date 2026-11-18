"""Single reproducible CPU entry point; all invoked commands get exit-code logs."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

STEPS = ("fixture", "layout", "render_A", "render_B", "decode_A", "decode_B",
         "sage_A", "sage_B", "native_A", "native_B", "cfg", "tests")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True, help="Untouched official GenRecon checkout")
    p.add_argument("--blender", default=shutil.which("blender") or "/opt/homebrew/bin/blender")
    p.add_argument("--steps", nargs="+", choices=STEPS, default=list(STEPS))
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--samples", type=int, default=8)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    fixture = "fixtures/multiroom/synthetic_building.json"
    evidence = "evidence/cpu"
    commands = {
        "fixture": [sys.executable, "src/floorplan/make_fixture.py", fixture],
        "layout": [sys.executable, "-m", "src.scene_graph.plot_layout", fixture, f"{evidence}/layout_camera_map.png"],
        "cfg": [sys.executable, "src/genrecon/cfg_preflight.py", "--repo", str(a.repo),
                "--out", "configs/genrecon_cfg", "--report", f"{evidence}/cfg_preflight.json"],
        "tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    }
    for variant in ("A", "B"):
        render = f"{evidence}/render_{variant}"
        sage = f"{evidence}/sage_gt_{variant}"
        commands[f"render_{variant}"] = [a.blender, "-b", "-t", "4", "--python-exit-code", "2",
            "--python", "src/blender/render_global.py", "--", "--scene", fixture, "--variant", variant,
            "--out", render, "--size", str(a.size), "--samples", str(a.samples)]
        commands[f"decode_{variant}"] = [sys.executable, "src/blender/decode_passes.py", render]
        commands[f"sage_{variant}"] = [sys.executable, "src/genrecon/prepare_sage_gt.py", "--scene", fixture,
            "--render", render, "--dest", sage]
        commands[f"native_{variant}"] = [sys.executable, "src/genrecon/probe_native_reader.py",
            "--repo", str(a.repo), "--render-dir", f"{sage}/renders_room/synthetic_multiroom_4r1c",
            "--out-dir", f"{evidence}/native_{variant}", "--out-json", f"{evidence}/native_{variant}_report.json",
            "--scene", fixture, "--n-views", "16"]
    for step in a.steps:
        cmd = [sys.executable, "src/runner/log_command.py", "--log-dir", f"{evidence}/logs", step,
               "--", *commands[step]]
        print(f"RUN {step}: {' '.join(cmd)}", flush=True)
        code = subprocess.call(cmd, cwd=root)
        if code != 0:
            print(f"STOP {step}: exit={code}", file=sys.stderr, flush=True)
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
