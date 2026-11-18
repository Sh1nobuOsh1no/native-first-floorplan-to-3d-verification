"""Package a global synthetic building render for the unmodified Sage_gt reader.

The native layout file carries only outer dimensions. It does not express
interior walls, doors, topology, depth or object IDs to GenRecon.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def prepare(scene_path: Path, render_root: Path, dest_root: Path) -> Path:
    scene = json.loads(scene_path.read_text())
    assert scene["provenance"]["kind"] == "SYNTHETIC"
    scene_id = scene["scene_id"]
    render_dir = dest_root / "renders_room" / scene_id
    raw_dir = dest_root / "rooms_raw" / scene_id
    render_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = scene["bounds_m"]
    layout = {"rooms": [{"dimensions": {"width": x1 - x0, "length": y1 - y0,
                                      "height": scene["height_m"]}}],
              "adapter_provenance": "SYNTHETIC_BUILDING_OUTER_BOUNDS_ONLY"}
    (raw_dir / f"layout_{scene_id}.json").write_text(json.dumps(layout, indent=2) + "\n")
    transforms = json.loads((render_root / "transforms.json").read_text())
    for frame in transforms["frames"]:
        name = Path(frame["file_path"]).name
        source = render_root / "rgb" / name
        assert source.is_file(), source
        frame["file_path"] = name
        shutil.copy2(source, render_dir / name)
    (render_dir / "transforms.json").write_text(json.dumps(transforms, indent=2) + "\n")
    return render_dir


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--render", type=Path, required=True)
    p.add_argument("--dest", type=Path, required=True)
    a = p.parse_args()
    print(prepare(a.scene, a.render, a.dest))
