"""One metric building scene: validated topology and box geometry for Blender.

No room-wise generation or learned model is used here. All coordinates are
metres in a single right-handed, Z-up world frame.
"""

from __future__ import annotations

import json
import math
import hashlib
from collections import deque
from pathlib import Path


EPS = 1e-6


def load_scene(path: str | Path) -> dict:
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding="utf-8"))
    validate_scene(scene)
    if scene["provenance"]["kind"] == "SOURCE_DRAWING":
        source = Path(scene["provenance"]["source_file"])
        source = source if source.is_absolute() else path.parent / source
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != scene["provenance"]["source_sha256"]:
            raise ValueError("SOURCE_DRAWING source file missing or SHA256 mismatch")
    return scene


def _finite(values) -> bool:
    return all(math.isfinite(float(v)) for v in values)


def _inside(space: dict, point: tuple[float, float], margin: float = 0.0) -> bool:
    x0, y0, x1, y1 = space["bounds_m"]
    x, y = point
    return x0 + margin < x < x1 - margin and y0 + margin < y < y1 - margin


def _wall_frame(wall: dict):
    x0, y0 = wall["p0_m"]
    x1, y1 = wall["p1_m"]
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < EPS or (abs(dx) > EPS and abs(dy) > EPS):
        raise ValueError(f"{wall['id']}: wall must be nonzero and axis aligned")
    return length, (dx / length, dy / length), (-dy / length, dx / length)


def _side_spaces(scene: dict, wall: dict, op: dict) -> set[str]:
    length, tangent, normal = _wall_frame(wall)
    mid = (op["u0_m"] + op["u1_m"]) / 2
    center = (wall["p0_m"][0] + mid * tangent[0], wall["p0_m"][1] + mid * tangent[1])
    offset = wall["thickness_m"] / 2 + 0.12
    sides = [(center[0] + s * offset * normal[0], center[1] + s * offset * normal[1]) for s in (-1, 1)]
    found = []
    for p in sides:
        matches = [room["id"] for room in scene["spaces"] if _inside(room, p)]
        if len(matches) != 1:
            raise ValueError(f"{op['id']}: each wall side must belong to one space, got {matches}")
        found.append(matches[0])
    if found[0] == found[1]:
        raise ValueError(f"{op['id']}: both door sides resolve to one space")
    return set(found)


def validate_scene(scene: dict) -> None:
    if scene.get("schema") != "metric_scene_v1" or not scene.get("scene_id"):
        raise ValueError("Expected metric_scene_v1 and nonempty scene_id")
    if scene.get("units") != "m" or scene.get("world_frame") != "RH_Z_UP":
        raise ValueError("Expected metres and RH_Z_UP global frame")
    if float(scene.get("floor_z_m", 0)) != 0:
        raise ValueError("metric_scene_v1 fixes floor_z_m=0; nonzero vertical origin is unsupported")
    if scene.get("provenance", {}).get("kind") not in {"SYNTHETIC", "SOURCE_DRAWING"}:
        raise ValueError("Explicit provenance kind required")
    if scene["provenance"]["kind"] == "SOURCE_DRAWING":
        source = scene["provenance"]
        digest = source.get("source_sha256", "")
        if (not source.get("source_file") or len(digest) != 64 or
                any(c not in "0123456789abcdef" for c in digest.lower()) or
                not source.get("scale_evidence") or source.get("real_floorplan_parsed") is not True):
            raise ValueError("SOURCE_DRAWING requires source_file and SHA256")
    height = float(scene.get("height_m", 0))
    if not 2.0 <= height <= 6.0:
        raise ValueError("Invalid scene height")
    bx0, by0, bx1, by1 = scene["bounds_m"]
    if not _finite(scene["bounds_m"]) or bx1 <= bx0 or by1 <= by0:
        raise ValueError("Scene bounds must have positive metric extents")
    spaces = scene["spaces"]
    if len(spaces) < 3 or sum(s["semantic"] == "corridor" for s in spaces) < 1:
        raise ValueError("Need at least two rooms and one corridor")
    ids = set()
    for group in ("spaces", "walls", "objects", "cameras"):
        for item in scene.get(group, []):
            if not item.get("id") or item["id"] in ids:
                raise ValueError(f"Duplicate or empty ID: {item.get('id')}")
            ids.add(item["id"])
    space_ids = {s["id"] for s in spaces}
    for room in spaces:
        b = room["bounds_m"]
        if not _finite(b) or not (bx0 <= b[0] < b[2] <= bx1 and by0 <= b[1] < b[3] <= by1):
            raise ValueError(f"{room['id']}: bad bounds")
        if not room.get("source_evidence"):
            raise ValueError(f"{room['id']}: missing source evidence")
        if scene["provenance"]["kind"] == "SOURCE_DRAWING" and room["source_evidence"].startswith("SYNTHETIC"):
            raise ValueError(f"{room['id']}: synthetic room cannot be marked source drawing")
    doors = []
    for wall in scene["walls"]:
        length, _, _ = _wall_frame(wall)
        if not _finite([*wall["p0_m"], *wall["p1_m"], wall["thickness_m"]]) or wall["thickness_m"] <= 0:
            raise ValueError(f"{wall['id']}: bad metric geometry")
        if not wall.get("source_evidence"):
            raise ValueError(f"{wall['id']}: missing source evidence")
        if scene["provenance"]["kind"] == "SOURCE_DRAWING" and wall["source_evidence"].startswith("SYNTHETIC"):
            raise ValueError(f"{wall['id']}: synthetic wall cannot be marked source drawing")
        spans = []
        for op in wall.get("openings", []):
            if not op.get("id") or op["id"] in ids:
                raise ValueError(f"Duplicate opening ID: {op.get('id')}")
            ids.add(op["id"])
            u0, u1, z0, z1 = (float(op[k]) for k in ("u0_m", "u1_m", "z0_m", "z1_m"))
            if not _finite((u0, u1, z0, z1)) or not (0 <= u0 < u1 <= length and 0 <= z0 < z1 <= height):
                raise ValueError(f"{op['id']}: opening outside wall")
            if any(max(u0, a) < min(u1, b) - EPS for a, b in spans):
                raise ValueError(f"{op['id']}: overlapping openings")
            spans.append((u0, u1))
            if op["kind"] == "door":
                if abs(z0) > EPS or z1 < 1.8 or len(op.get("connects", [])) != 2:
                    raise ValueError(f"{op['id']}: invalid door height or links")
                declared = set(op["connects"])
                if not declared <= space_ids or declared != _side_spaces(scene, wall, op):
                    raise ValueError(f"{op['id']}: door links disagree with physical wall sides")
                doors.append(op)
            elif op["kind"] != "window" or op.get("connects"):
                raise ValueError(f"{op['id']}: invalid window")
    if len(doors) < len(spaces) - 1:
        raise ValueError("Too few physically linked doors for connected spaces")
    adjacency = {x: set() for x in space_ids}
    for op in doors:
        a, b = op["connects"]
        adjacency[a].add(b)
        adjacency[b].add(a)
    visited = set()
    queue = deque([next(s["id"] for s in spaces if s["semantic"] == "corridor")])
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        queue.extend(adjacency[node] - visited)
    if visited != space_ids:
        raise ValueError(f"Disconnected spaces: {sorted(space_ids - visited)}")
    for obj in scene.get("objects", []):
        if scene["provenance"]["kind"] == "SOURCE_DRAWING" and obj.get("source_evidence", "").startswith("SYNTHETIC"):
            raise ValueError(f"{obj['id']}: synthetic object cannot be marked source drawing")
        if obj["room_id"] not in space_ids or not _finite([*obj["center_m"], *obj["size_m"]]):
            raise ValueError(f"{obj['id']}: invalid object or room")
        if min(obj["size_m"]) <= 0 or not _inside(next(s for s in spaces if s["id"] == obj["room_id"]), obj["center_m"][:2]):
            raise ValueError(f"{obj['id']}: invalid object bounds")
    for cam in scene["cameras"]:
        if cam["space_id"] not in space_ids or not _finite([*cam["eye_m"], *cam["target_m"], cam["fov_deg"]]):
            raise ValueError(f"{cam['id']}: invalid pose")
        if math.dist(cam["eye_m"], cam["target_m"]) < 0.1 or not 20 <= cam["fov_deg"] <= 110:
            raise ValueError(f"{cam['id']}: degenerate camera")
        if not _inside(next(s for s in spaces if s["id"] == cam["space_id"]), cam["eye_m"][:2]):
            raise ValueError(f"{cam['id']}: camera not in declared space")


def _box(component_id: str, kind: str, center, size, source_id: str) -> dict:
    return {"id": component_id, "kind": kind, "center_m": list(center), "size_m": list(size), "source_id": source_id}


def components(scene: dict, with_furniture: bool) -> list[dict]:
    """Compile all rooms into one list of global-world primitives."""
    validate_scene(scene)
    bx0, by0, bx1, by1 = scene["bounds_m"]
    h = scene["height_m"]
    result = [
        _box("floor", "floor", [(bx0 + bx1) / 2, (by0 + by1) / 2, -0.06], [bx1 - bx0, by1 - by0, 0.12], "floor"),
        _box("ceiling", "ceiling", [(bx0 + bx1) / 2, (by0 + by1) / 2, h + 0.06], [bx1 - bx0, by1 - by0, 0.12], "ceiling"),
    ]
    for wall in scene["walls"]:
        length, tangent, _ = _wall_frame(wall)
        breaks = sorted({0.0, length, *(float(v) for op in wall.get("openings", []) for v in (op["u0_m"], op["u1_m"]))})
        for i, (a, b) in enumerate(zip(breaks, breaks[1:])):
            active = next((op for op in wall.get("openings", []) if op["u0_m"] + EPS < (a + b) / 2 < op["u1_m"] - EPS), None)
            zs = [(0.0, h)] if active is None else [(0.0, active["z0_m"]), (active["z1_m"], h)]
            for j, (z0, z1) in enumerate(zs):
                if z1 - z0 < EPS:
                    continue
                mid = (a + b) / 2
                cx = wall["p0_m"][0] + mid * tangent[0]
                cy = wall["p0_m"][1] + mid * tangent[1]
                size = [b - a, wall["thickness_m"], z1 - z0] if abs(tangent[0]) > 0 else [wall["thickness_m"], b - a, z1 - z0]
                result.append(_box(f"{wall['id']}__{i}_{j}", "wall", [cx, cy, (z0 + z1) / 2], size, wall["id"]))
    if with_furniture:
        result.extend(_box(o["id"], "furniture", o["center_m"], o["size_m"], o["id"]) for o in scene.get("objects", []))
    return result


def ray_box_distance(origin, direction, box: dict) -> float | None:
    bounds = [(c - s / 2, c + s / 2) for c, s in zip(box["center_m"], box["size_m"])]
    near, far = -math.inf, math.inf
    for (lo, hi), o, d in zip(bounds, origin, direction):
        if abs(d) < EPS:
            if not lo <= o <= hi:
                return None
            continue
        a, b = (lo - o) / d, (hi - o) / d
        near, far = max(near, min(a, b)), min(far, max(a, b))
    return near if far >= max(near, 0) and near >= 0 else (0.0 if far >= 0 and near < 0 else None)


def first_hit(origin, target, boxes: list[dict], kinds: set[str] | None = None) -> tuple[str, float] | None:
    length = math.dist(origin, target)
    direction = [(b - a) / length for a, b in zip(origin, target)]
    hits = [(distance, box["id"]) for box in boxes if kinds is None or box["kind"] in kinds
            if (distance := ray_box_distance(origin, direction, box)) is not None and distance <= length + EPS]
    return (min(hits)[1], min(hits)[0]) if hits else None
