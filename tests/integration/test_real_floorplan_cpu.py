"""Checks that real source images, annotations and mesh contracts stay distinct."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.floorplan.cubicasa_vector_adapter import convert
from src.floorplan.evaluate_reference import evaluate
from src.floorplan.parse_cpu import parse
from src.floorplan.revise_bounded import revise
from src.runner.batch_floorplans import discover
from src.scene_graph.metric_scene import components, first_hit, load_scene, validate_scene


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "fixtures/real_floorplans"


class RealFloorplanCPU(unittest.TestCase):
    def test_batch_discovers_five_distinct_source_drawings(self):
        images = discover(DATA)
        self.assertEqual(len(images), 5)
        self.assertEqual(len({p.parent.name for p in images}), 5)

    def test_raster_baseline_preserves_uncertainty_and_reference_is_separate(self):
        image = DATA / "4702/F1_scaled.png"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            raw = parse(image, out)
            revised = revise(raw, image, out)
            score = evaluate(out / "raw_prediction.json", DATA / "4702/model.svg", out / "reference.json")
            self.assertEqual(raw["door_candidates"], [])
            self.assertEqual(revised["door_candidates"], [])
            self.assertFalse(revised["agent_revision"]["model_used"])
            self.assertGreater(score["rooms"]["reference_count"], 0)
            self.assertIn("NOT_PARSER_INPUT", score["source"])

    def test_vector_control_yields_one_global_structural_scene(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            scene = convert(DATA / "4702/F1_scaled.png", DATA / "4702/model.svg", out)
            loaded = load_scene(out / "metric_scene.json")
            self.assertEqual(len(loaded["spaces"]), 6)
            self.assertEqual(scene["provenance"]["automatic_raster_inference"], False)
            self.assertEqual(len([o for w in loaded["walls"] for o in w["openings"] if o["kind"] == "door"]), 5)
            self.assertEqual(len([o for w in loaded["walls"] for o in w["openings"] if o["kind"] == "exterior_door"]), 2)
            self.assertTrue(all(box["source_id"] != "floor" for box in components(loaded, False) if box["kind"] == "floor"))
            annotation = out / "source_annotation.svg"
            original_annotation = annotation.read_bytes()
            annotation.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "annotation file missing or SHA256 mismatch"):
                load_scene(out / "metric_scene.json")
            annotation.write_bytes(original_annotation)
            # Tampering with the source file must invalidate SOURCE_DRAWING.
            (out / "source_floorplan.png").write_bytes(b"invalid")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                load_scene(out / "metric_scene.json")

    def test_nonrectangular_real_annotation_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "UNSUPPORTED_GEOMETRY"):
                convert(DATA / "2055/F1_scaled.png", DATA / "2055/model.svg", Path(d))

    def test_single_page_pdf_contract_and_multi_page_rejection(self):
        import pymupdf as fitz

        image = DATA / "4702/F1_scaled.png"
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            pdf = out / "real_floorplan.pdf"
            doc = fitz.open()
            page = doc.new_page(width=680, height=635)
            page.insert_image(page.rect, filename=str(image))
            doc.save(pdf)
            doc.close()
            parsed = parse(pdf, out / "parsed")
            self.assertGreater(len(parsed["wall_traces"]), 0)
            doc = fitz.open(pdf)
            doc.new_page(width=680, height=635)
            doc.save(out / "two_floors.pdf")
            doc.close()
            with self.assertRaisesRegex(ValueError, "exactly one floor/page"):
                parse(out / "two_floors.pdf", out / "rejected")


if __name__ == "__main__":
    unittest.main()
