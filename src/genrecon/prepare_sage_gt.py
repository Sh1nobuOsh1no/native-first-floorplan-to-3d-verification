"""Package a global building render for the unmodified Sage_gt reader.

The native layout file carries only outer dimensions. It does not express
interior walls, doors, topology, depth or object IDs to GenRecon.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from src.scene_graph.metric_scene import load_scene


def prepare(scene_path: Path, render_root: Path, dest_root: Path) -> Path:
    scene = load_scene(scene_path)
    if abs(scene["height_m"] - 2.7) > 1e-6:
        raise ValueError("Sage_gt fixes floor=0 and ceiling=2.7 m; incompatible height")
    scene_id = scene["scene_id"]
    render_dir = dest_root / "renders_room" / scene_id
    raw_dir = dest_root / "rooms_raw" / scene_id
    render_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = scene["bounds_m"]
    layout = {"rooms": [{"dimensions": {"width": x1 - x0, "length": y1 - y0,
                                      "height": scene["height_m"]}}],
              "adapter_provenance": scene["provenance"]["kind"] + "_BUILDING_OUTER_BOUNDS_ONLY"}
    (raw_dir / f"layout_{scene_id}.json").write_text(json.dumps(layout, indent=2) + "\n")
    transforms = json.loads((render_root / "transforms.json").read_text())
    for frame in transforms["frames"]:
        name = Path(frame["file_path"]).name
        source = render_root / "rgb" / name
        assert source.is_file(), source
        frame["file_path"] = name
        # Native Sage_gt assumes x_min=y_min=0. Keep global poses in Blender
        # metadata and explicitly translate only the native copy.
        frame["transform_matrix"][0][3] -= x0
        frame["transform_matrix"][1][3] -= y0
        shutil.copy2(source, render_dir / name)
    (render_dir / "transforms.json").write_text(json.dumps(transforms, indent=2) + "\n")
    (render_dir / "adapter_transform.json").write_text(json.dumps({
        "global_to_sage_translation_m": [-x0, -y0, 0],
        "original_bounds_m": scene["bounds_m"],
        "provenance": scene["provenance"],
        "limitation": "Only outer bounds enter Sage_gt; interior walls and doors are not hard constraints."
    }, indent=2) + "\n")
    return render_dir


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--render", type=Path, required=True)
    p.add_argument("--dest", type=Path, required=True)
    a = p.parse_args()
    print(prepare(a.scene, a.render, a.dest))
