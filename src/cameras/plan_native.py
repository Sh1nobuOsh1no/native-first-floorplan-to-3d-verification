"""Plan building cameras against GenRecon's unmodified Sage_gt CPU acceptance rule."""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import torch

from src.scene_graph.metric_scene import components, first_hit, load_scene, validate_scene


def _pose(eye, target):
    e, t = torch.tensor(eye, dtype=torch.float32), torch.tensor(target, dtype=torch.float32)
    forward = torch.nn.functional.normalize(t - e, dim=0)
    right = torch.nn.functional.normalize(torch.linalg.cross(forward, torch.tensor([0., 0., 1.])), dim=0)
    up = torch.linalg.cross(right, forward)
    pose = torch.eye(4)
    pose[:3, :3] = torch.stack((right, up, -forward), dim=1)
    pose[:3, 3] = e
    return pose


def _candidate(scene, chunk, room, index):
    x0, y0, x1, y1 = room["bounds_m"]
    cx, cy, cz = chunk
    margin = min(.4, (x1-x0)/4, (y1-y0)/4)
    points = [((x0+x1)/2, (y0+y1)/2),
              (x0+.25*(x1-x0), y0+.25*(y1-y0)),
              (x0+.75*(x1-x0), y0+.25*(y1-y0)),
              (x0+.25*(x1-x0), y0+.75*(y1-y0)),
              (x0+.75*(x1-x0), y0+.75*(y1-y0)),
              (min(max(cx, x0+margin), x1-margin), min(max(cy, y0+margin), y1-margin))]
    for j, (x, y) in enumerate(points):
        if math.hypot(cx-x, cy-y) < .3:
            continue
        yield {"id": f"auto_{index:02d}_{room['id']}_{j}", "space_id": room["id"],
               "eye_m": [x, y, min(1.55, scene["height_m"]-.5)],
               "target_m": [cx, cy, cz], "fov_deg": 100.0}


def _area_details(cam, m, offset, flip):
    pose = _pose(cam["eye_m"], cam["target_m"])
    pose[:3, 3] -= offset
    ext = flip @ torch.linalg.inv(m @ pose)
    xyz = torch.tensor([[x,y,z,1.] for x in (-.5,.5) for y in (-.5,.5) for z in (-.5,.5)] + [[0.,0.,0.,1.]])
    p = (ext @ xyz.T).T[:, :3]
    p = p[p[:,2] > 0]
    if not len(p):
        return {"projected_clipped_area": 0., "reason": "all_chunk_sample_points_behind_camera"}
    f = .5 / math.tan(math.radians(cam["fov_deg"])/2)
    u = (f*p[:,0]/p[:,2]+.5).clamp(0,1)
    v = (f*p[:,1]/p[:,2]+.5).clamp(0,1)
    area = float((u.max()-u.min())*(v.max()-v.min()))
    return {"projected_clipped_area": area, "front_sample_count": len(p),
            "reason": "clipped_projected_area_below_0.4" if area < .4 else "accepted"}


def door_side_candidates(scene: dict) -> list[dict]:
    """Add topology-derived cross-door views only where no existing shared-object pair exists."""
    walls = components(scene, False)
    rooms = {s["id"]: s for s in scene["spaces"]}
    result = []

    def sees(cam, point):
        eye = torch.tensor(cam["eye_m"], dtype=torch.float32)
        aim = torch.tensor(cam["target_m"], dtype=torch.float32) - eye
        ray = torch.tensor(point, dtype=torch.float32) - eye
        cosine = float(torch.dot(aim, ray) / (torch.linalg.norm(aim)*torch.linalg.norm(ray)))
        return (cosine >= math.cos(math.radians(cam["fov_deg"])/2) and
                first_hit(cam["eye_m"], point, walls, {"wall"}) is None)

    for wall in scene["walls"]:
        p0, p1 = wall["p0_m"], wall["p1_m"]
        length = math.dist(p0, p1)
        tangent = ((p1[0]-p0[0])/length, (p1[1]-p0[1])/length)
        normal = (-tangent[1], tangent[0])
        for door in wall.get("openings", []):
            if door["kind"] != "door":
                continue
            u = (door["u0_m"]+door["u1_m"])/2
            mid = [p0[0]+u*tangent[0], p0[1]+u*tangent[1]]
            shared = False
            for obj in scene.get("objects", []):
                if obj["room_id"] not in door["connects"]:
                    continue
                if all(any(c["space_id"] == space and sees(c, obj["center_m"])
                           for c in scene.get("cameras", [])) for space in door["connects"]):
                    shared = True
                    break
            if shared:
                continue
            for space in door["connects"]:
                room = rooms[space]
                x0,y0,x1,y1 = room["bounds_m"]
                for sign in (-1, 1):
                    eye_xy = [mid[j]+sign*normal[j]*.85 for j in (0,1)]
                    if x0 < eye_xy[0] < x1 and y0 < eye_xy[1] < y1:
                        target_xy = [mid[j]-sign*normal[j]*1.2 for j in (0,1)]
                        result.append({"id": f"door_{door['id']}_{space}", "space_id": space,
                                       "eye_m": [*eye_xy, min(1.55, scene["height_m"]-.5)],
                                       "target_m": [*target_xy, 1.4], "fov_deg": 90.0})
                        break
                else:
                    raise ValueError(f"{door['id']}: cannot place camera on {space} side")
    return result


def plan(scene_path: Path, repo: Path, out_scene: Path, report_path: Path, max_views: int = 32) -> dict:
    scene = load_scene(scene_path)
    if abs(scene["height_m"] - 2.7) > 1e-6:
        raise ValueError("Sage_gt hardcodes floor 0 and ceiling 2.7 m; reject incompatible height")
    sys.path.insert(0, str(repo.resolve()))
    from inference.get_chunks import SageGtChunker
    from inference.get_images import SageImageSelecter, _FLIP_Y_Z

    chunker = SageGtChunker()
    size = 2.7 + .15
    x0, y0, x1, y1 = scene["bounds_m"]
    centers = chunker._define_centers(0, x1-x0, 0, y1-y0, 0, size)
    # Official chunk transforms require an output path; only the adapter owns it.
    report_path.parent.mkdir(parents=True, exist_ok=True)
    transforms, _, _ = chunker._get_transforms(centers, size, report_path.parent)
    selector = SageImageSelecter()
    offset = torch.tensor([x0, y0, 0.], dtype=torch.float32)
    walls = components(scene, False)

    def accepted(cam):
        pose = _pose(cam["eye_m"], cam["target_m"])
        pose[:3, 3] -= offset
        f = .5 / math.tan(math.radians(cam["fov_deg"])/2)
        k = torch.tensor([[f, 0., .5], [0., f, .5], [0., 0., 1.]], dtype=torch.float32)
        return {i for i, m in enumerate(transforms)
                if selector._check_acceptance(_FLIP_Y_Z @ torch.linalg.inv(m @ pose), k)}

    original = list(scene.get("cameras", []))
    original_coverage = {c["id"]: accepted(c) for c in original}
    chosen = list(original)
    covered = set().union(*original_coverage.values()) if original_coverage else set()
    missing_before = sorted(set(range(len(centers))) - covered)
    door_cameras = door_side_candidates(scene)
    chosen.extend(door_cameras)
    for cam in door_cameras:
        covered |= accepted(cam)
    failure_diagnostics = {}
    for i in missing_before:
        ranked = sorted(({"camera_id": c["id"], "space_id": c["space_id"],
                          "fov_deg": c["fov_deg"], "eye_m": c["eye_m"],
                          "target_m": c["target_m"],
                          **_area_details(c, transforms[i], offset, _FLIP_Y_Z)} for c in original),
                        key=lambda d: d["projected_clipped_area"], reverse=True)
        failure_diagnostics[str(i)] = {"center_sage_m": centers[i],
            "center_world_m": [centers[i][0]+x0, centers[i][1]+y0, centers[i][2]],
            "best_original_cameras": ranked[:4], "all_original_rejected": True}
    candidates = []
    for i in missing_before:
        world_chunk = (centers[i][0]+x0, centers[i][1]+y0, centers[i][2])
        for room in scene["spaces"]:
            candidates.extend(_candidate(scene, world_chunk, room, i))
    candidate_coverage = {}
    for cam in candidates:
        native_accepted = accepted(cam)
        candidate_coverage[cam["id"]] = {i for i in native_accepted
            if first_hit(cam["eye_m"], [centers[i][0]+x0, centers[i][1]+y0, centers[i][2]],
                         walls, {"wall"}) is None}
    while len(covered) < len(centers) and len(chosen) < max_views:
        best = max(candidates, key=lambda c: len(candidate_coverage[c["id"]] - covered), default=None)
        if best is None or not candidate_coverage[best["id"]] - covered:
            break
        chosen.append(best)
        covered |= candidate_coverage[best["id"]]
        candidates.remove(best)

    # The native selector uses all cameras only when the source count is <= the cap.
    # A full source pool is required so a cover on discarded images cannot masquerade as success.
    if len(chosen) > max_views:
        raise ValueError("Planned camera set exceeds num_imgs_per_scene")
    planned = copy.deepcopy(scene)
    planned["cameras"] = chosen
    validate_scene(planned)
    out_scene.parent.mkdir(parents=True, exist_ok=True)
    out_scene.write_text(json.dumps(planned, indent=2) + "\n")
    report = {"scene_id": scene["scene_id"], "native_rule": "GenRecon chunk_visible_in_camera, projected clipped area >= 0.4",
              "chunk_size_m": size, "chunk_centers_sage_m": centers,
              "global_to_sage_translation_m": [-x0, -y0, 0],
              "original_camera_count": len(original), "planned_camera_count": len(chosen),
              "topology_door_camera_ids": [c["id"] for c in door_cameras],
              "num_imgs_per_scene": max_views, "missing_before": missing_before,
              "missing_after": sorted(set(range(len(centers))) - covered),
              "original_accepted_counts": {str(i): sum(i in v for v in original_coverage.values()) for i in range(len(centers))},
              "failure_diagnostics": failure_diagnostics,
              "planned_camera_ids": [c["id"] for c in chosen],
              "auto_camera_coverage": {c["id"]: sorted(candidate_coverage[c["id"]]) for c in chosen if c["id"] in candidate_coverage},
              "auto_camera_requires_unblocked_ray_to_chunk_center": True,
              "official_source_sha": "unmodified", "model_forward_executed": False}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--scene", required=True, type=Path)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--out-scene", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--max-views", type=int, default=32)
    a = p.parse_args()
    print(json.dumps(plan(a.scene, a.repo, a.out_scene, a.report, a.max_views)))
