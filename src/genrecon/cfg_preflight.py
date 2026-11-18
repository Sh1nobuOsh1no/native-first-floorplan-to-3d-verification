"""Build four external CFG configs from an untouched official JSON baseline."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

KEYS = ("sparse_structure_sampler", "shape_slat_sampler", "tex_slat_sampler")
RUNS = {"official_baseline": (7.5, 7.5, 1.0),
        "geometry_cfg_3": (3.0, 3.0, 1.0),
        "no_extra_cfg": (1.0, 1.0, 1.0),
        "texture_cfg_0_5": (7.5, 7.5, 0.5)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(repo: Path, out: Path) -> dict:
    baseline_path = repo / "configs/pipelines/original.json"
    baseline = json.loads(baseline_path.read_text())
    assert tuple(baseline["args"][k]["params"]["guidance_strength"] for k in KEYS) == RUNS["official_baseline"]
    checks = {
        "pipeline_config_cli": ("reconstruct_scene.py", "--pipeline_config"),
        "cond_2D": ("genrecon/pipelines/images_to_3d.py", "cond_2D"),
        "cond_3D_projection": ("genrecon/pipelines/images_to_3d.py", "get_3D_cond"),
        "dino_v3": ("configs/pipelines/original.json", "DinoV3FeatureExtractor"),
        "sparse_structure": ("genrecon/pipelines/full_scene_images_to_3d.py", "sparse_structure"),
        "shape_slat": ("genrecon/pipelines/full_scene_images_to_3d.py", "shape_slat"),
        "texture_slat": ("genrecon/pipelines/full_scene_images_to_3d.py", "tex_slat"),
        "classifier_free_guidance": ("genrecon/pipelines/samplers/flow_euler.py", "guidance_strength"),
    }
    source_checks = {}
    for label, (rel, needle) in checks.items():
        path = repo / rel
        text = path.read_text()
        if rel.endswith(".py"):
            ast.parse(text, filename=str(path))
        assert needle in text, label
        source_checks[label] = {"path": rel, "line": next(i for i, line in enumerate(text.splitlines(), 1) if needle in line),
                                "sha256": sha(path)}
    out.mkdir(parents=True, exist_ok=True)
    variants = {}
    for label, values in RUNS.items():
        config = json.loads(json.dumps(baseline))
        for key, value in zip(KEYS, values):
            config["args"][key]["params"]["guidance_strength"] = value
        path = out / f"{label}.json"
        path.write_text(json.dumps(config, indent=2) + "\n")
        check = json.loads(path.read_text())
        assert tuple(check["args"][k]["params"]["guidance_strength"] for k in KEYS) == values
        variants[label] = {"path": str(path), "cfg": values, "sha256": sha(path)}
    report = {"status": "PASS_STATIC_CPU_ONLY", "official_repo_sha256_of_original_json": sha(baseline_path),
              "source_checks": source_checks, "variants": variants,
              "inference_executed": False, "cfg_effect_measured": False}
    return report


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True); p.add_argument("--report",type=Path,required=True)
    a=p.parse_args(); report=build(a.repo,a.out)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status": report["status"], "variants": list(report["variants"])}))
