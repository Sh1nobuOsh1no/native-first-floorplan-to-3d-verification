"""Resumable per-drawing CPU batch with explicit provenance and failure states."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


RENDER_STEPS = ("plan", "layout", "render_A", "decode_A", "sage_A", "native_A")


def call(name: str, argv: list[str], root: Path, log_dir: Path) -> int:
    return subprocess.call([sys.executable, "-m", "src.runner.log_command", "--log-dir", str(log_dir),
                            name, "--", *argv], cwd=root)


def discover(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf"}
                  and not p.name.endswith("_original.png"))


def process(image: Path, out_root: Path, repo: Path, root: Path, blender: str,
            annotation_sidecars: bool, resume: bool, size: int, samples: int) -> dict:
    start = time.monotonic()
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    name = f"{image.parent.name}_{image.stem}_{digest[:8]}"
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    log_dir = out / "logs"
    stages = {}
    manifest_path = out / "case_manifest.json"
    prior = json.loads(manifest_path.read_text()) if resume and manifest_path.is_file() else None
    can_resume = prior is not None and prior.get("source_sha256") == digest
    def stage(label, command, marker):
        if can_resume and prior.get("stages", {}).get(label, {}).get("exit_code") == 0 and marker.is_file():
            stages[label] = {"exit_code": 0, "resumed": True, "output": str(marker)}
            return 0
        code = call(label, command, root, log_dir)
        stages[label] = {"exit_code": code, "resumed": False, "output": str(marker) if marker.is_file() else None}
        return code
    parser_dir = out / "parser"
    code = stage("parse", [sys.executable, "-m", "src.floorplan.parse_cpu", str(image), str(parser_dir)],
                 parser_dir / "raw_prediction.json")
    status = "FAILED" if code else "PARSED_CANDIDATES_ONLY"
    if code == 0:
        code = stage("revise", [sys.executable, "-m", "src.floorplan.revise_bounded",
                                str(parser_dir / "raw_prediction.json"), str(image), str(parser_dir)],
                     parser_dir / "revised_prediction.json")
        status = "FAILED" if code else "AGENT_REVISED_CANDIDATES"
    sidecar = image.with_name("model.svg")
    if code == 0 and annotation_sidecars and sidecar.is_file():
        code = stage("annotated_vector", [sys.executable, "-m", "src.floorplan.cubicasa_vector_adapter",
                                           str(image), str(sidecar), str(out)], out / "metric_scene.json")
        status = "NEEDS_REVIEW" if code else "GEOMETRY_VALIDATED_ANNOTATION_ASSISTED"
    else:
        if code == 0:
            status = "NEEDS_REVIEW"
    if code == 0 and status == "GEOMETRY_VALIDATED_ANNOTATION_ASSISTED":
        for step in RENDER_STEPS:
            markers = {"plan": out / "planned_scene.json", "layout": out / "layout_camera_map.png",
                       "render_A": out / "render_A/building_unified.glb",
                       "decode_A": out / "render_A/contact_sheet.png",
                       "sage_A": out / "sage_gt_A/renders_room" / f"cubicasa5k_{image.parent.name}" / "transforms.json",
                       "native_A": out / "native_A_report.json"}
            cmd = [sys.executable, "-m", "src.runner.run_cpu", "--scene", str(out / "metric_scene.json"),
                   "--repo", str(repo), "--output-root", str(out), "--blender", blender,
                   "--steps", step, "--size", str(size), "--samples", str(samples), "--n-views", "32"]
            code = stage(step, cmd, markers[step])
            if code:
                status = "FAILED_AFTER_GEOMETRY_VALIDATED"
                break
            if step == "render_A":
                status = "BLENDER_BUILT_ANNOTATION_ASSISTED"
            elif step == "native_A":
                status = "GENRECON_INPUT_VALIDATED_ANNOTATION_ASSISTED"
        if status == "GENRECON_INPUT_VALIDATED_ANNOTATION_ASSISTED":
            cross = out / "cross_door_structure.json"
            cross_cmd = [sys.executable, "-m", "src.cameras.check_structural_cross_door",
                         "--scene", str(out / "planned_scene.json"), "--render", str(out / "render_A"),
                         "--out", str(cross)]
            cross_code = stage("cross_door_structure", cross_cmd, cross)
            if cross_code:
                status = "PARTIAL_ANNOTATION_ASSISTED_CROSS_DOOR_FAILURE"
    milestones = []
    if stages.get("parse", {}).get("exit_code") == 0:
        milestones.append("PARSED_CANDIDATES")
    revision_file = parser_dir / "agent_revision.json"
    if revision_file.is_file() and json.loads(revision_file.read_text()).get("edits", 0) > 0:
        milestones.append("AGENT_REVISED_TRACES")
    if stages.get("annotated_vector", {}).get("exit_code") == 0:
        milestones.append("GEOMETRY_VALIDATED_ANNOTATION_ASSISTED")
    if stages.get("render_A", {}).get("exit_code") == 0:
        milestones.append("BLENDER_BUILT_ANNOTATION_ASSISTED")
    if stages.get("native_A", {}).get("exit_code") == 0:
        milestones.append("GENRECON_INPUT_VALIDATED_ANNOTATION_ASSISTED")
    if stages.get("cross_door_structure", {}).get("exit_code") == 0:
        milestones.append("CROSS_DOOR_REPROJECTION_VALIDATED")
    report = {"input": str(image.resolve()), "input_sha256": digest, "annotation_sidecar": str(sidecar) if sidecar.is_file() else None,
              "status": status, "stages": stages, "elapsed_seconds": round(time.monotonic() - start, 3),
              "milestones": milestones,
              "baseline_prediction_is_not_annotation": True,
              "agent_model_used": False,
              "note": "Annotation-assisted successes do not count as raster parser successes."}
    manifest_path.write_text(json.dumps({"source_sha256": digest, **report}, indent=2) + "\n")
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--mode", choices=["cpu"], required=True)
    p.add_argument("--repo", type=Path, required=True, help="Unmodified official GenRecon checkout")
    p.add_argument("--blender", default="/opt/homebrew/bin/blender")
    p.add_argument("--annotation-sidecars", action="store_true", help="Use labelled SVG only as a separately reported control")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--size", type=int, default=128)
    p.add_argument("--samples", type=int, default=4)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    a.output_dir.mkdir(parents=True, exist_ok=True)
    images = discover(a.input_dir)
    reports = []
    for image in images:
        try:
            reports.append(process(image.resolve(), a.output_dir.resolve(), a.repo.resolve(), root,
                                   a.blender, a.annotation_sidecars, a.resume, a.size, a.samples))
        except Exception as exc:
            reports.append({"input": str(image), "status": "FAILED", "error": repr(exc)})
        print(json.dumps({"input": reports[-1]["input"], "status": reports[-1]["status"]}), flush=True)
    counts = {s: sum(r["status"] == s for r in reports) for s in sorted({r["status"] for r in reports})}
    summary = {"total": len(reports), "counts": counts, "cases": reports}
    (a.output_dir / "batch_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"total": len(reports), "counts": counts}))
    return 0 if images else 2


if __name__ == "__main__":
    raise SystemExit(main())
