"""Deterministic synthetic full-building metric fixture, not a parsed drawing."""
from __future__ import annotations

import json
from pathlib import Path


def make_scene() -> dict:
    source = "SYNTHETIC: hand-authored multiroom geometry, no source drawing"
    spaces = [
        ("bedroom", "bedroom", [0, 0, 6, 3.5]),
        ("office", "office", [6, 0, 12, 3.5]),
        ("corridor", "corridor", [0, 3.5, 12, 5.5]),
        ("living", "living_room", [0, 5.5, 6, 9]),
        ("kitchen", "kitchen", [6, 5.5, 12, 9]),
    ]
    def wall(wid, p0, p1, openings=()):
        return {"id": wid, "p0_m": p0, "p1_m": p1, "thickness_m": 0.2,
                "source_evidence": source, "openings": list(openings)}
    def door(did, u0, u1, room):
        return {"id": did, "kind": "door", "u0_m": u0, "u1_m": u1,
                "z0_m": 0.0, "z1_m": 2.15, "connects": ["corridor", room],
                "source_evidence": source}
    def window(wid, u0, u1):
        return {"id": wid, "kind": "window", "u0_m": u0, "u1_m": u1,
                "z0_m": 0.9, "z1_m": 2.2, "source_evidence": source}
    walls = [
        wall("south", [0, 0], [12, 0], [window("window_bed", 1.3, 2.6), window("window_office", 8.0, 9.3)]),
        wall("north", [0, 9], [12, 9], [window("window_living", 1.3, 2.6), window("window_kitchen", 8.0, 9.3)]),
        wall("west", [0, 0], [0, 9], [window("window_west", 6.5, 7.8)]),
        wall("east", [12, 0], [12, 9], [window("window_east", 1.1, 2.4)]),
        wall("south_rooms", [0, 3.5], [12, 3.5], [door("door_bedroom", 2.4, 3.4, "bedroom"), door("door_office", 8.6, 9.6, "office")]),
        wall("north_rooms", [0, 5.5], [12, 5.5], [door("door_living", 2.4, 3.4, "living"), door("door_kitchen", 8.6, 9.6, "kitchen")]),
        wall("south_divider", [6, 0], [6, 3.5]),
        wall("north_divider", [6, 5.5], [6, 9]),
    ]
    objects = [
        {"id": "bed_01", "room_id": "bedroom", "kind": "bed_block", "center_m": [2.9, 1.65, 0.35], "size_m": [1.25, 0.95, 0.7], "source_evidence": source},
        {"id": "desk_01", "room_id": "office", "kind": "desk_block", "center_m": [9.1, 1.65, 0.4], "size_m": [1.2, 0.8, 0.8], "source_evidence": source},
        {"id": "sofa_01", "room_id": "living", "kind": "sofa_block", "center_m": [2.9, 7.3, 0.4], "size_m": [1.4, 0.85, 0.8], "source_evidence": source},
        {"id": "counter_01", "room_id": "kitchen", "kind": "counter_block", "center_m": [9.1, 7.3, 0.45], "size_m": [1.4, 0.7, 0.9], "source_evidence": source},
    ]
    cameras = [
        ("c00_corridor_to_bed", "corridor", [2.9, 4.8, 1.55], [2.9, 1.65, 0.7]),
        ("c01_bed_to_bed", "bedroom", [2.0, 2.7, 1.55], [2.9, 1.65, 0.4]),
        ("c02_bed_side", "bedroom", [1.0, 1.5, 1.55], [2.9, 1.65, 0.4]),
        ("c03_bed_to_corridor", "bedroom", [2.9, 1.0, 1.55], [2.9, 4.6, 1.45]),
        ("c04_corridor_oblique_bed", "corridor", [1.5, 4.5, 1.55], [2.9, 2.3, 0.9]),
        ("c05_corridor_to_office", "corridor", [9.1, 4.8, 1.55], [9.1, 1.65, 0.8]),
        ("c06_office_to_desk", "office", [8.4, 2.8, 1.55], [9.1, 1.65, 0.4]),
        ("c07_office_side", "office", [10.7, 1.6, 1.55], [9.1, 1.65, 0.4]),
        ("c08_corridor_to_living", "corridor", [2.9, 4.2, 1.55], [2.9, 7.3, 0.8]),
        ("c09_living_to_sofa", "living", [2.1, 6.2, 1.55], [2.9, 7.3, 0.4]),
        ("c10_living_side", "living", [1.0, 7.5, 1.55], [2.9, 7.3, 0.4]),
        ("c11_living_to_corridor", "living", [2.9, 8.2, 1.55], [2.9, 4.6, 1.45]),
        ("c12_corridor_to_kitchen", "corridor", [9.1, 4.2, 1.55], [9.1, 7.3, 0.8]),
        ("c13_kitchen_to_counter", "kitchen", [8.4, 6.2, 1.55], [9.1, 7.3, 0.45]),
        ("c14_kitchen_side", "kitchen", [10.8, 7.5, 1.55], [9.1, 7.3, 0.45]),
        ("c15_corridor_axis", "corridor", [6.0, 4.5, 1.55], [10.5, 4.5, 1.5]),
    ]
    return {
        "schema": "metric_scene_v1", "scene_id": "synthetic_multiroom_4r1c", "units": "m", "world_frame": "RH_Z_UP",
        "bounds_m": [0.0, 0.0, 12.0, 9.0], "height_m": 2.7,
        "provenance": {"kind": "SYNTHETIC", "source_evidence": source,
                       "real_floorplan_parsed": False, "agent_interpretation_used": False},
        "spaces": [{"id": sid, "semantic": sem, "bounds_m": box, "source_evidence": source} for sid, sem, box in spaces],
        "walls": walls, "objects": objects,
        "cameras": [{"id": cid, "space_id": space, "eye_m": eye, "target_m": target,
                     "fov_deg": 78.0, "source_evidence": source} for cid, space, eye, target in cameras],
    }


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(make_scene(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
