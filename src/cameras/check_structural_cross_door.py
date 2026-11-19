"""Measure the same rendered wall across each physical interior door."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from src.scene_graph.metric_scene import components, first_hit, load_scene


def project_pair(a, b, da, ia, db, ib, oid):
    y, x = np.where(ia == oid)
    if len(x) == 0:
        return 0, 0.0
    K = np.asarray(a["K_px"])
    c2w = np.asarray(a["c2w_blender"])
    xyz = np.stack(((x + .5 - K[0, 2]) / K[0, 0] * da[y, x],
                    -(y + .5 - K[1, 2]) / K[1, 1] * da[y, x],
                    -da[y, x], np.ones(len(x))))
    p = np.linalg.inv(np.asarray(b["c2w_blender"])) @ (c2w @ xyz)
    Kb = np.asarray(b["K_px"])
    u = np.rint(Kb[0, 0] * p[0] / -p[2] + Kb[0, 2] - .5).astype(int)
    v = np.rint(Kb[1, 2] - Kb[1, 1] * p[1] / -p[2] - .5).astype(int)
    z = -p[2]
    h, w = db.shape
    keep = (u >= 0) & (u < w) & (v >= 0) & (v < h) & (z > 0) & np.isfinite(z)
    if not keep.any():
        return 0, 0.0
    matched = (ib[v[keep], u[keep]] == oid) & (abs(db[v[keep], u[keep]] - z[keep]) < .1)
    return int(keep.sum()), float(matched.mean())


def check(scene_path: Path, render: Path, out: Path) -> dict:
    scene = load_scene(scene_path)
    meta = json.loads((render / "camera_metadata.json").read_text())
    frames = {f["camera_id"]: f for f in meta["frames"]}
    id_map = json.loads((render / "object_id_map.json").read_text())
    wall_ids = {int(k): v for k, v in id_map.items() if v["kind"] == "wall"}
    wall_boxes = components(scene, False)
    results, tiles = [], []
    for wall in scene["walls"]:
        for door in wall.get("openings", []):
            if door["kind"] != "door":
                continue
            candidates = []
            side_frames = []
            for sid in door["connects"]:
                cid = f"door_{door['id']}_{sid}"
                if cid in frames:
                    side_frames.append(frames[cid])
            if len(side_frames) != 2:
                results.append({"door_id": door["id"], "status": "FAIL_MISSING_SIDE_CAMERA"})
                continue
            a, b = side_frames
            ray_clear = first_hit(a["eye_m"], b["eye_m"], wall_boxes, {"wall"}) is None
            ia = np.load(render / a["object_id_npy"])
            ib = np.load(render / b["object_id_npy"])
            da = np.load(render / a["depth_npy"])
            db = np.load(render / b["depth_npy"])
            for oid, obj in wall_ids.items():
                na, nb = int((ia == oid).sum()), int((ib == oid).sum())
                if min(na, nb) < 20:
                    continue
                n, ratio = project_pair(a, b, da, ia, db, ib, oid)
                candidates.append((n * ratio, n, ratio, obj["source_id"], obj["id"], oid, na, nb))
            if candidates:
                # A shared wall can show different faces from opposite rooms.
                # Select the component with the strongest actual reprojection,
                # and keep the raw match ratio in the report.
                _, n, ratio, source, component, oid, na, nb = max(candidates, key=lambda x: (x[2], x[1]))
                status = "PASS" if n >= 20 and ratio >= .8 else "FAIL_REPROJECTION"
                results.append({"door_id": door["id"], "connects": door["connects"], "status": status,
                                "cameras": [a["camera_id"], b["camera_id"]], "shared_wall_source_id": source,
                                "shared_component_id": component,
                                "door_to_door_camera_ray_clear": ray_clear,
                                "visible_pixels": [na, nb], "reprojected_pixels": n,
                                "depth_id_match_ratio": ratio, "depth_tolerance_m": .1})
            else:
                results.append({"door_id": door["id"], "connects": door["connects"],
                                "status": "FAIL_NO_SHARED_WALL_VISIBLE", "cameras": [a["camera_id"], b["camera_id"]],
                                "door_to_door_camera_ray_clear": ray_clear})
            for f in (a, b):
                tile = Image.open(render / f["rgb"]).convert("RGB")
                ImageDraw.Draw(tile).text((3, 3), f["camera_id"], fill=(255, 0, 0))
                tiles.append(tile)
    out.parent.mkdir(parents=True, exist_ok=True)
    if tiles:
        w, h = tiles[0].size
        canvas = Image.new("RGB", (2 * w, ((len(tiles) + 1) // 2) * h))
        for i, tile in enumerate(tiles):
            canvas.paste(tile, ((i % 2) * w, (i // 2) * h))
        canvas.save(out.with_suffix(".png"))
    report = {"scene_id": scene["scene_id"], "source": "BLENDER_CPU_WHITEBOX",
              "doors": results, "pass_count": sum(x["status"] == "PASS" for x in results),
              "clear_door_ray_count": sum(x.get("door_to_door_camera_ray_clear", False) for x in results),
              "total": len(results), "all_pass": all(x["status"] == "PASS" for x in results)}
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scene", required=True, type=Path)
    p.add_argument("--render", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    result = check(a.scene, a.render, a.out)
    print(json.dumps({"pass": result["pass_count"], "total": result["total"]}))
    raise SystemExit(0 if result["all_pass"] else 2)
