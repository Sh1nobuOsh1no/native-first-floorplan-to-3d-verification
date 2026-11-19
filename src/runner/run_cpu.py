"""Parameterised CPU pipeline; every subprocess records argv, exit code and logs."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from src.scene_graph.metric_scene import load_scene

STEPS = ("plan", "layout", "render_A", "render_B", "decode_A", "decode_B",
         "sage_A", "sage_B", "native_A", "native_B", "cfg", "tests")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True, help="Any validated metric_scene_v1 building JSON")
    p.add_argument("--repo", type=Path, required=True, help="Untouched official GenRecon checkout")
    p.add_argument("--output-root", type=Path, default=Path("evidence/cpu"))
    p.add_argument("--blender", default=shutil.which("blender") or "/opt/homebrew/bin/blender")
    p.add_argument("--steps", nargs="+", choices=STEPS, default=list(STEPS[:-2]))
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--n-views", type=int, default=32)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = a.scene.resolve()
    scene = load_scene(source)
    output = a.output_root.resolve()
    planned = output / "planned_scene.json"
    render_scene = planned if "plan" in a.steps or planned.is_file() else source
    commands = {
        "plan": [sys.executable, "-m", "src.cameras.plan_native", "--scene", str(source),
                 "--repo", str(a.repo), "--out-scene", str(planned),
                 "--report", str(output / "camera_plan.json"), "--max-views", str(a.n_views)],
        "layout": [sys.executable, "-m", "src.scene_graph.plot_layout", str(render_scene), str(output / "layout_camera_map.png")],
        "cfg": [sys.executable, "-m", "src.genrecon.cfg_preflight", "--repo", str(a.repo),
                "--out", str(root / "configs/genrecon_cfg"), "--report", str(output / "cfg_preflight.json")],
        "tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
    }
    for variant in ("A", "B"):
        render = output / f"render_{variant}"
        sage = output / f"sage_gt_{variant}"
        commands[f"render_{variant}"] = [a.blender, "-b", "-t", "4", "--python-exit-code", "2",
            "--python", "src/blender/render_global.py", "--", "--scene", str(render_scene), "--variant", variant,
            "--out", str(render), "--size", str(a.size), "--samples", str(a.samples)]
        commands[f"decode_{variant}"] = [sys.executable, "-m", "src.blender.decode_passes", str(render)]
        commands[f"sage_{variant}"] = [sys.executable, "-m", "src.genrecon.prepare_sage_gt", "--scene", str(render_scene),
            "--render", str(render), "--dest", str(sage)]
        commands[f"native_{variant}"] = [sys.executable, "-m", "src.genrecon.probe_native_reader",
            "--repo", str(a.repo), "--render-dir", str(sage / "renders_room" / scene["scene_id"]),
            "--out-dir", str(output / f"native_{variant}"), "--out-json", str(output / f"native_{variant}_report.json"),
            "--scene", str(render_scene), "--n-views", str(a.n_views)]
    for step in a.steps:
        cmd = [sys.executable, "-m", "src.runner.log_command", "--log-dir", str(output / "logs"), step,
               "--", *commands[step]]
        print(f"RUN {step}: {' '.join(cmd)}", flush=True)
        code = subprocess.call(cmd, cwd=root)
        if code:
            print(f"STOP {step}: exit={code}", file=sys.stderr, flush=True)
            return code
    (output / "run_manifest.json").write_text(json.dumps({"source_scene": str(source),
        "render_scene": str(render_scene), "scene_id": scene["scene_id"], "steps": a.steps,
        "n_views": a.n_views, "size": a.size, "samples": a.samples}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
