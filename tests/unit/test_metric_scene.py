import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.scene_graph.metric_scene import components, first_hit, load_scene, validate_scene
from src.floorplan.calibration import calibrate_polygons
from src.cameras.plan_native import door_side_candidates

SCENE = Path(__file__).resolve().parents[2] / "fixtures/multiroom/synthetic_building.json"
ALTERNATE = SCENE.with_name("synthetic_offset_2r1c.json")


class MetricSceneTests(unittest.TestCase):
    def setUp(self):
        self.scene = load_scene(SCENE)

    def rejects(self, edit):
        scene = copy.deepcopy(self.scene)
        edit(scene)
        with self.assertRaises(ValueError):
            validate_scene(scene)

    def test_global_topology_and_units(self):
        self.assertEqual((self.scene["units"], self.scene["world_frame"]), ("m", "RH_Z_UP"))
        self.assertEqual(len(self.scene["spaces"]), 5)
        doors = [o for w in self.scene["walls"] for o in w.get("openings", []) if o["kind"] == "door"]
        self.assertEqual(len(doors), 4)
        self.assertEqual(self.scene["provenance"]["kind"], "SYNTHETIC")

    def test_alternate_layout_has_global_offset_and_two_links(self):
        scene = load_scene(ALTERNATE)
        self.assertEqual(scene["bounds_m"], [-4, 10, 2, 19])
        self.assertEqual(len(scene["spaces"]), 3)
        self.assertEqual(len([o for w in scene["walls"] for o in w.get("openings", []) if o["kind"]=="door"]), 2)
        self.assertEqual(scene["provenance"]["kind"], "SYNTHETIC")

    def test_topology_generates_missing_door_side_cameras(self):
        scene = load_scene(ALTERNATE)
        scene["cameras"] = []
        generated = door_side_candidates(scene)
        self.assertEqual(len(generated), 4)
        self.assertEqual({c["space_id"] for c in generated}, {"corridor", "bedroom", "living"})
        for camera in generated:
            self.assertIsNone(first_hit(camera["eye_m"], camera["target_m"], components(scene, False), {"wall"}))
        scene["cameras"] = generated
        validate_scene(scene)

    def test_every_corridor_door_has_unblocked_ray(self):
        boxes = components(self.scene, False)
        for cam, obj in [("c00_corridor_to_bed", "bed_01"), ("c05_corridor_to_office", "desk_01"),
                         ("c08_corridor_to_living", "sofa_01"), ("c12_corridor_to_kitchen", "counter_01")]:
            eye = next(c["eye_m"] for c in self.scene["cameras"] if c["id"] == cam)
            target = next(o["center_m"] for o in self.scene["objects"] if o["id"] == obj)
            self.assertIsNone(first_hit(eye, target, boxes, {"wall"}), cam)

    def test_closed_wall_blocks_ray(self):
        boxes = components(self.scene, False)
        self.assertIsNotNone(first_hit([5, 4.7, 1.4], [5, 2, 1.4], boxes, {"wall"}))

    def test_invalid_door_width(self):
        self.rejects(lambda s: s["walls"][4]["openings"][0].update(u1_m=20))

    def test_invalid_door_links(self):
        self.rejects(lambda s: s["walls"][4]["openings"][0].update(connects=["corridor", "kitchen"]))

    def test_disconnected_room(self):
        self.rejects(lambda s: s["walls"][4]["openings"].pop())

    def test_wrong_unit(self):
        self.rejects(lambda s: s.update(units="cm"))

    def test_camera_outside_declared_space(self):
        self.rejects(lambda s: s["cameras"][0].update(eye_m=[20, 20, 1.5]))

    def test_degenerate_camera(self):
        self.rejects(lambda s: s["cameras"][0].update(target_m=s["cameras"][0]["eye_m"]))

    def test_synthetic_cannot_claim_real_drawing(self):
        self.rejects(lambda s: s["provenance"].update(kind="SOURCE_DRAWING"))

    def test_source_drawing_hash_and_component_evidence_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.json"
            drawing = Path(tmp) / "drawing.png"
            drawing.write_bytes(b"placeholder source bytes for rejection test")
            scene = copy.deepcopy(self.scene)
            scene["provenance"].update(kind="SOURCE_DRAWING", source_file="drawing.png",
                source_sha256="0"*64, scale_evidence="claimed", real_floorplan_parsed=True)
            path.write_text(json.dumps(scene))
            with self.assertRaises(ValueError):
                load_scene(path)
            for item in scene["spaces"]+scene["walls"]+scene["objects"]:
                item["source_evidence"]="unverified claim"
            path.write_text(json.dumps(scene))
            with self.assertRaises(ValueError):
                load_scene(path)

    def test_global_affine_calibration_keeps_negative_coordinates(self):
        calibration = {"pixel_to_world_m": [[.01, 0, -2], [0, -.01, 5]],
                       "source_image_sha256": "a"*64, "scale_evidence": "synthetic 100 px/m fixture"}
        polygons = [{"id": n, "image_id": "whole_building", "category_id": 1,
                     "segmentation": [0+100*n, 0, 50+100*n, 0, 50+100*n, 50]}
                    for n in range(4)]
        result = calibrate_polygons(polygons, calibration)
        self.assertEqual(len(result["polygons"]), 4)
        self.assertEqual(result["polygons"][0]["vertices_m"][0], [-2.0, 5.0])

    def test_calibration_rejects_missing_scale_evidence(self):
        with self.assertRaises(ValueError):
            calibrate_polygons([{"id": 1, "image_id": "x", "category_id": 1,
                                 "segmentation": [0,0,1,0,1,1]}],
                               {"pixel_to_world_m": [[1,0,0],[0,1,0]], "source_image_sha256": "a"*64})


if __name__ == "__main__":
    unittest.main()
