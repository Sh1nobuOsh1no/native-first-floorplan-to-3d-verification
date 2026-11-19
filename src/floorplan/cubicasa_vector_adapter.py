"""Strict adapter for CubiCasa5K's *human annotated* SVG sidecar.

This is an annotation-assisted integration test, not raster model inference.
It rejects nonrectangular rooms, uncertain scale, ambiguous openings and
unsupported wall geometry rather than silently rectifying the drawing.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path

from src.scene_graph.metric_scene import validate_scene


def polygon(group):
    child = next((x for x in group if x.tag.endswith("polygon")), None)
    if child is None:
        raise ValueError("ANNOTATION_MISSING_POLYGON")
    return [tuple(map(float, pair.split(","))) for pair in child.attrib["points"].split()]


def bbox(points):
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def rectangularity(points):
    area = abs(sum(points[i][0] * points[(i + 1) % len(points)][1] -
                   points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points))) / 2)
    x0, y0, x1, y1 = bbox(points)
    return area / ((x1 - x0) * (y1 - y0))


def convert(image_path: Path, svg_path: Path, out_dir: Path, height_m: float = 2.7) -> dict:
    image_path, svg_path, out_dir = Path(image_path), Path(svg_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = ET.parse(svg_path).getroot()
    spaces_px, walls_px, openings_px, scales = [], [], [], []
    for group in root.iter():
        cls = group.attrib.get("class", "")
        if cls.startswith("Space ") and "Outdoor" not in cls and cls != "Space Undefined":
            poly = polygon(group)
            if rectangularity(poly) < .995:
                raise ValueError(f"UNSUPPORTED_GEOMETRY: nonrectangular room {cls} {group.attrib.get('id')}")
            b = bbox(poly)
            label = next((x for x in group.iter() if x.attrib.get("class") == "SpaceDimensionsLabel"), None)
            if label is not None:
                values = re.findall(r"(\d+(?:\.\d+)?)\s*m\s*x\s*(\d+(?:\.\d+)?)\s*m", "".join(label.itertext()))
                if values:
                    a, c = map(float, values[-1])
                    scales.extend([a / (b[2] - b[0]), c / (b[3] - b[1])])
            spaces_px.append((cls[6:], b, group.attrib.get("id", "")))
        elif cls.startswith("Wall"):
            poly = polygon(group)
            b = bbox(poly)
            if min(b[2] - b[0], b[3] - b[1]) < 3:
                raise ValueError("UNSUPPORTED_GEOMETRY: degenerate wall")
            walls_px.append((cls, b, group.attrib.get("id", "")))
        elif cls.startswith("Door ") or cls.startswith("Window "):
            openings_px.append(("door" if cls.startswith("Door ") else "window", bbox(polygon(group)),
                                group.attrib.get("id", "")))
    if len(spaces_px) < 3 or not any("Entry" in s[0] or "Corridor" in s[0] or "Hall" in s[0] for s in spaces_px):
        raise ValueError("UNSUPPORTED_TOPOLOGY: needs multiple rooms and an entry/corridor")
    if len(scales) < 4:
        raise ValueError("NEEDS_SCALE: insufficient visible metric dimension labels")
    scale = statistics.median(scales)
    if max(abs(s - scale) / scale for s in scales) > .03:
        raise ValueError("NEEDS_SCALE: dimension labels disagree by over 3 percent")
    # Only exact annotation coordinates are transformed. No room is added or
    # shape altered to fit metric_scene_v1.
    all_interior = [b for _, b, _ in spaces_px]
    x_origin = min(b[0] for b in all_interior)
    y_bottom = max(b[3] for b in all_interior)
    def xy(x, y):
        return [round((x - x_origin) * scale, 5), round((y_bottom - y) * scale, 5)]
    def metric_box(b):
        lo = xy(b[0], b[3]); hi = xy(b[2], b[1])
        return [lo[0], lo[1], hi[0], hi[1]]
    source_ref = f"CUBICASA5K_HUMAN_SVG:{svg_path.name}"
    spaces = []
    for i, (name, b, gid) in enumerate(spaces_px):
        semantic = "corridor" if "Entry" in name or "Corridor" in name or "Hall" in name else name.lower().replace(" ", "_")
        spaces.append({"id": f"space_{i:02d}", "semantic": semantic, "bounds_m": metric_box(b),
                       "source_evidence": f"{source_ref}#{gid}", "confidence": 1.0,
                       "annotation_class": name})
    walls = []
    skipped_walls = []
    for i, (cls, b, gid) in enumerate(walls_px):
        bw, bh = b[2] - b[0], b[3] - b[1]
        if min(bw, bh) / max(bw, bh) > .16:
            raise ValueError(f"UNSUPPORTED_GEOMETRY: non-axis wall {gid}")
        if bw > bh:
            center = (b[1] + b[3]) / 2
            p0, p1 = xy(b[0], center), xy(b[2], center)
            thick = bh * scale
        else:
            center = (b[0] + b[2]) / 2
            # Pixel Y is reversed in the global frame.
            p0, p1 = xy(center, b[3]), xy(center, b[1])
            thick = bw * scale
        # Ignore exterior balcony railing annotations that border no indoor
        # space; they are not part of this indoor building shell.
        near = any(not (b[2] < r[0] - 3 or b[0] > r[2] + 3 or b[3] < r[1] - 3 or b[1] > r[3] + 3)
                   for _, r, _ in spaces_px)
        if not near:
            skipped_walls.append(gid)
            continue
        walls.append({"id": f"wall_{i:02d}", "p0_m": p0, "p1_m": p1,
                      "thickness_m": round(thick, 5), "source_evidence": f"{source_ref}#{gid}",
                      "confidence": 1.0, "openings": [], "_bbox_px": b})
    unresolved = []
    for opening_index, (kind, b, gid) in enumerate(openings_px):
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        eligible = []
        for wall in walls:
            wb = wall["_bbox_px"]
            horizontal = abs(wall["p1_m"][0] - wall["p0_m"][0]) > 1e-6
            perp = abs(cy - (wb[1] + wb[3]) / 2) if horizontal else abs(cx - (wb[0] + wb[2]) / 2)
            inside = wb[0] - 2 <= cx <= wb[2] + 2 if horizontal else wb[1] - 2 <= cy <= wb[3] + 2
            if inside and perp <= max((wb[3] - wb[1] if horizontal else wb[2] - wb[0]) / 2 + 4, 8):
                eligible.append((perp, wall))
        if not eligible:
            unresolved.append({"id": gid, "reason": "no wall annotation overlap"})
            continue
        eligible.sort(key=lambda x: x[0])
        if len(eligible) > 1 and eligible[1][0] - eligible[0][0] < 2:
            unresolved.append({"id": gid, "reason": "ambiguous wall assignment"})
            continue
        wall = eligible[0][1]
        horizontal = abs(wall["p1_m"][0] - wall["p0_m"][0]) > 1e-6
        wb = wall["_bbox_px"]
        low = (b[0] - wb[0]) * scale if horizontal else (wb[3] - b[3]) * scale
        high = (b[2] - wb[0]) * scale if horizontal else (wb[3] - b[1]) * scale
        length = math.dist(wall["p0_m"], wall["p1_m"])
        low, high = max(0.0, low), min(length, high)
        if high - low < .25:
            unresolved.append({"id": gid, "reason": "opening too narrow after calibration"})
            continue
        op = {"id": f"opening_{opening_index:03d}_{gid[:8]}", "kind": kind,
              "u0_m": round(low, 5), "u1_m": round(high, 5),
              "z0_m": 0 if kind == "door" else .9,
              "z1_m": 2.1 if kind == "door" else 2.1,
              "source_evidence": f"{source_ref}#{gid}", "confidence": 1.0}
        if kind == "door":
            mid = (low + high) / 2
            p0, p1 = wall["p0_m"], wall["p1_m"]
            tangent = ((p1[0] - p0[0]) / length, (p1[1] - p0[1]) / length)
            normal = (-tangent[1], tangent[0])
            center = (p0[0] + mid * tangent[0], p0[1] + mid * tangent[1])
            offset = wall["thickness_m"] / 2 + .12
            sides = []
            for sign in (-1, 1):
                q = (center[0] + sign * offset * normal[0], center[1] + sign * offset * normal[1])
                ids = [r["id"] for r in spaces if r["bounds_m"][0] < q[0] < r["bounds_m"][2]
                       and r["bounds_m"][1] < q[1] < r["bounds_m"][3]]
                sides.append(ids)
            if any(len(x) > 1 for x in sides) or all(not x for x in sides):
                unresolved.append({"id": gid, "reason": "ambiguous room side"})
                continue
            links = sorted(set(sides[0] + sides[1]))
            if len(links) == 2:
                op["connects"] = links
            elif len(links) == 1:
                op["kind"] = "exterior_door"
                op["connects"] = links
            else:
                unresolved.append({"id": gid, "reason": "invalid topology"})
                continue
        wall["openings"].append(op)
    if unresolved:
        raise ValueError(f"NEEDS_REVIEW: unresolved annotated openings: {unresolved}")
    for wall in walls:
        wall.pop("_bbox_px")
    x0 = min(s["bounds_m"][0] for s in spaces)
    y0 = min(s["bounds_m"][1] for s in spaces)
    x1 = max(s["bounds_m"][2] for s in spaces)
    y1 = max(s["bounds_m"][3] for s in spaces)
    image_copy = out_dir / "source_floorplan.png"
    svg_copy = out_dir / "source_annotation.svg"
    shutil.copy2(image_path, image_copy)
    shutil.copy2(svg_path, svg_copy)
    scene = {"schema": "metric_scene_v1", "scene_id": f"cubicasa5k_{image_path.parent.name}",
             "units": "m", "world_frame": "RH_Z_UP", "floor_z_m": 0,
             "bounds_m": [x0, y0, x1, y1], "height_m": height_m,
             "footprint_mode": "SPACE_UNION",
             "provenance": {"kind": "SOURCE_DRAWING", "source_file": image_copy.name,
                            "source_sha256": hashlib.sha256(image_copy.read_bytes()).hexdigest(),
                            "annotation_file": svg_copy.name,
                            "annotation_sha256": hashlib.sha256(svg_copy.read_bytes()).hexdigest(),
                            "parser_kind": "CUBICASA5K_HUMAN_SVG_ANNOTATION_ADAPTER",
                            "automatic_raster_inference": False, "real_floorplan_parsed": True,
                            "scale_evidence": f"SVG room dimension labels, median {scale:.6f} m/px from {len(scales)} measurements",
                            "scale_m_per_px": scale, "height_evidence": "ASSUMED_2.7_M_FOR_SAGE_GT",
                            "agent_interpretation_used": False},
             "spaces": spaces, "walls": walls, "objects": [], "cameras": [], "agent_revisions": [],
             "limitations": ["Human SVG annotations supply geometry; not an image model prediction",
                             "2.7 m height is assumed, not measured from floorplan",
                             f"Skipped {len(skipped_walls)} exterior/outdoor wall annotations"]}
    validate_scene(scene)
    (out_dir / "metric_scene.json").write_text(json.dumps(scene, indent=2) + "\n")
    return scene


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("image", type=Path)
    p.add_argument("svg", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args()
    scene = convert(a.image, a.svg, a.out)
    print(json.dumps({"scene_id": scene["scene_id"], "rooms": len(scene["spaces"]),
                      "walls": len(scene["walls"]), "annotation_assisted": True}))
