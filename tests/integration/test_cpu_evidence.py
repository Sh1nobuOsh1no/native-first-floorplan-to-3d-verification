"""Tests actual Blender and unmodified GenRecon CPU outputs; never synthesize passes."""
import json
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from src.cameras.geometry import validate_camera
from src.genrecon.prepare_sage_gt import prepare

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / "evidence/cpu"
PAIRS = [("c00_corridor_to_bed", "c01_bed_to_bed", "bed_01"),
         ("c05_corridor_to_office", "c06_office_to_desk", "desk_01"),
         ("c08_corridor_to_living", "c09_living_to_sofa", "sofa_01"),
         ("c12_corridor_to_kitchen", "c13_kitchen_to_counter", "counter_01")]


def artifact(frame, key):
    return E / f"render_{frame['variant']}" / frame[key]


@lru_cache(maxsize=4)
def packed(variant, kind):
    return np.load(E / f"render_{variant}" / f"{kind}_all.npz")


def load_pass(frame, key):
    path = artifact(frame, key)
    if path.is_file():
        return np.load(path)
    kind = "depth" if key == "depth_npy" else "object_id"
    return packed(frame["variant"], kind)[frame["camera_id"]]


def project(points, meta):
    K = np.array(meta["K_px"])
    inv = np.linalg.inv(np.array(meta["c2w_blender"]))
    p = inv @ points
    u = np.rint(K[0, 0] * p[0] / -p[2] + K[0, 2] - .5).astype(int)
    v = np.rint(K[1, 2] - K[1, 1] * p[1] / -p[2] - .5).astype(int)
    return u, v, -p[2]


class CPUEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = {}
        for variant in ("A", "B"):
            root = E / f"render_{variant}"
            cls.frames[variant] = {f["camera_id"]: (f | {"variant": variant})
                                   for f in json.loads((root / "camera_metadata.json").read_text())["frames"]}
        cls.id_map = json.loads((E / "render_B/object_id_map.json").read_text())

    def test_same_global_cameras_A_B(self):
        self.assertEqual(set(self.frames["A"]), set(self.frames["B"]))
        self.assertEqual(len(self.frames["A"]), 20)
        for cid in self.frames["A"]:
            a, b = self.frames["A"][cid], self.frames["B"][cid]
            np.testing.assert_allclose(a["K_px"], b["K_px"], atol=1e-8)
            np.testing.assert_allclose(a["c2w_blender"], b["c2w_blender"], atol=1e-8)
            C = np.array(a["c2w_blender"])
            validate_camera(a["K_px"], C, (256, 256))
            np.testing.assert_allclose(C[:3, :3].T @ C[:3, :3], np.eye(3), atol=1e-6)
            np.testing.assert_allclose(C[:3, 3], a["eye_m"], atol=1e-6)

    def test_aligned_real_render_passes(self):
        for variant in ("A", "B"):
            for frame in self.frames[variant].values():
                rgb = np.array(Image.open(artifact(frame, "rgb")))
                depth = load_pass(frame, "depth_npy")
                ids = load_pass(frame, "object_id_npy")
                self.assertEqual(rgb.shape, (256, 256, 3))
                self.assertEqual(depth.shape, ids.shape)
                self.assertGreater(np.isfinite(depth[depth < 1e8]).sum(), 1000)
                self.assertGreater(len(np.unique(ids)), 1)

    def test_global_unified_mesh_extent(self):
        for variant, objects in (("A", 36), ("B", 40)):
            root = E / f"render_{variant}"
            manifest = json.loads((root / "render_manifest.json").read_text())
            self.assertTrue(manifest["global_scene"])
            self.assertEqual(manifest["object_count"], objects)
            mesh = trimesh.load(root / "building_unified.glb", force="scene")
            self.assertGreater(sum(len(g.faces) for g in mesh.geometry.values()), 400)
            # glTF exports Blender Z-up as glTF Y-up; physical extents are unchanged.
            np.testing.assert_allclose(mesh.extents, [12.2, 2.94, 9.2], atol=.02)

    def test_corrupt_camera_pose_rejected(self):
        a = self.frames["B"]["c00_corridor_to_bed"]
        bad = np.array(a["c2w_blender"])
        bad[0, 0] *= 2
        with self.assertRaises(ValueError):
            validate_camera(a["K_px"], bad, (256, 256))

    def test_same_object_visible_across_each_door(self):
        for corridor, inside, obj in PAIRS:
            value = next(int(k) for k, v in self.id_map.items() if v["source_id"] == obj)
            counts = []
            for cid in (corridor, inside):
                ids = load_pass(self.frames["B"][cid], "object_id_npy")
                counts.append(int((ids == value).sum()))
            self.assertGreater(min(counts), 500, (obj, counts))

    def test_depth_reprojection_crosses_bedroom_door(self):
        a = self.frames["B"]["c00_corridor_to_bed"]
        b = self.frames["B"]["c01_bed_to_bed"]
        value = next(int(k) for k, v in self.id_map.items() if v["source_id"] == "bed_01")
        depth_a = load_pass(a, "depth_npy")
        ids_a = load_pass(a, "object_id_npy")
        ids_b = load_pass(b, "object_id_npy")
        depth_b = load_pass(b, "depth_npy")
        y, x = np.where(ids_a == value)
        K = np.array(a["K_px"])
        rays = np.stack([(x+.5-K[0,2])/K[0,0]*depth_a[y,x],
                         -(y+.5-K[1,2])/K[1,1]*depth_a[y,x],
                         -depth_a[y,x], np.ones(len(x))])
        world = np.array(a["c2w_blender"]) @ rays
        u, v, z = project(world, b)
        keep = (u >= 0) & (u < 256) & (v >= 0) & (v < 256) & (z > 0)
        self.assertGreater(keep.sum(), 1000)
        matching = (ids_b[v[keep], u[keep]] == value) & (np.abs(depth_b[v[keep], u[keep]] - z[keep]) < .1)
        self.assertGreater(float(matching.mean()), .90)

    def test_door_jamb_occludes_deeper_furniture(self):
        a = self.frames["B"]["c00_corridor_to_bed"]
        points = np.array([[2.2, 2.9], [3.5, 2.125], [1.3, .5], [1., 1.]])
        u, v, _ = project(points, a)
        ids = load_pass(a, "object_id_npy")
        depth = load_pass(a, "depth_npy")
        self.assertEqual(self.id_map[str(ids[v[0], u[0]])]["source_id"], "south_rooms")
        self.assertEqual(self.id_map[str(ids[v[1], u[1]])]["source_id"], "bed_01")
        self.assertLess(float(depth[v[0], u[0]]), float(depth[v[1], u[1]]))

    def test_native_reader_and_fallbacks_labeled(self):
        for variant in ("A", "B"):
            report = json.loads((E / f"native_{variant}_report.json").read_text())
            self.assertEqual(report["status"], "PASS_CPU_NATIVE_READER")
            self.assertEqual(report["source_scene_provenance"]["kind"], "SYNTHETIC")
            self.assertEqual(report["source_camera_count"], 20)
            self.assertEqual(len(report["chunk_centers"]), 30)
            self.assertEqual(report["fallback_chunks"], [])
            self.assertEqual(report["zero_selected_visible_chunks"], [])
            self.assertEqual(report["selected_scene_camera_count"], 20)
            self.assertEqual(len(report["door_visibility"]), 4)
            self.assertTrue(all(x["chunks_with_both_side_cameras"] for x in report["door_visibility"]))
            self.assertIn("not hard constraints", report["native_layout_limitation"])

    def test_camera_plan_and_all_door_reprojections(self):
        plan = json.loads((E / "camera_plan.json").read_text())
        self.assertEqual(plan["missing_before"], [3, 5, 17, 27])
        self.assertEqual(plan["missing_after"], [])
        self.assertEqual(plan["planned_camera_count"], 20)
        self.assertTrue(plan["auto_camera_requires_unblocked_ray_to_chunk_center"])
        self.assertEqual(plan["num_imgs_per_scene"], 32)
        report = json.loads((E / "cross_door_check.json").read_text())
        self.assertTrue(report["all_pass"])
        self.assertEqual(len(report["results"]), 4)
        self.assertTrue(all(x["depth_id_match_ratio"] > .99 for x in report["results"]))

    def test_different_topology_and_offset_origin(self):
        alt = E / "alternate"
        plan = json.loads((alt / "camera_plan.json").read_text())
        self.assertEqual(plan["global_to_sage_translation_m"], [4, -10, 0])
        self.assertEqual(plan["missing_after"], [])
        for variant in ("A", "B"):
            report = json.loads((alt / f"native_{variant}_report.json").read_text())
            self.assertEqual(len(report["chunk_centers"]), 20)
            self.assertEqual(report["fallback_chunks"], [])
            self.assertEqual(report["selected_scene_camera_count"], 13)
            self.assertEqual(report["global_to_sage_translation_m"], [4, -10, 0])
            self.assertEqual(len(report["door_visibility"]), 2)
        cross = json.loads((alt / "cross_door_check.json").read_text())
        self.assertTrue(cross["all_pass"])

    def test_alternate_rgb_depth_id_and_camera_alignment(self):
        alt = E / "alternate"
        metas = {}
        for variant in ("A", "B"):
            root = alt / f"render_{variant}"
            metas[variant] = {f["camera_id"]: f for f in json.loads((root / "camera_metadata.json").read_text())["frames"]}
            with np.load(root / "depth_all.npz") as depth, np.load(root / "object_id_all.npz") as ids:
                self.assertEqual(set(depth.files), set(metas[variant]))
                for cid, frame in metas[variant].items():
                    rgb = np.asarray(Image.open(root / frame["rgb"]))
                    self.assertEqual(rgb.shape[:2], depth[cid].shape)
                    self.assertEqual(depth[cid].shape, ids[cid].shape)
                    self.assertGreater(len(np.unique(ids[cid])), 1)
                    validate_camera(frame["K_px"], frame["c2w_blender"], (256, 256))
                    np.testing.assert_allclose(np.asarray(frame["c2w_blender"])[:3, 3], frame["eye_m"], atol=1e-6)
        self.assertEqual(set(metas["A"]), set(metas["B"]))
        for cid in metas["A"]:
            np.testing.assert_allclose(metas["A"][cid]["K_px"], metas["B"][cid]["K_px"])
            np.testing.assert_allclose(metas["A"][cid]["c2w_blender"], metas["B"][cid]["c2w_blender"])

    def test_native_image_cap_can_reintroduce_fallbacks(self):
        report = json.loads((E / "native_B_cap8_report.json").read_text())
        self.assertEqual(report["selected_scene_camera_count"], 8)
        self.assertEqual(len(report["fallback_chunks"]), 11)
        self.assertEqual(report["fallback_chunks"], report["zero_selected_visible_chunks"])

    def test_sage_gt_rejects_nonstandard_height(self):
        scene = json.loads((ROOT / "fixtures/multiroom/synthetic_building.json").read_text())
        scene["height_m"] = 3.0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"tall.json"
            path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "2.7"):
                prepare(path, E/"render_B", Path(tmp)/"sage")

    def test_cfg_preflight_only(self):
        report = json.loads((E / "cfg_preflight.json").read_text())
        self.assertEqual(report["status"], "PASS_STATIC_CPU_ONLY")
        self.assertFalse(report["inference_executed"])
        self.assertFalse(report["cfg_effect_measured"])
        self.assertEqual(len(report["variants"]), 4)


if __name__ == "__main__":
    unittest.main()
