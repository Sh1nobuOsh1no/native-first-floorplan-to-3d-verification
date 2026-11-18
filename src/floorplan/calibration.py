"""Whole-image pixel polygons to global metres with explicit scale evidence.

Adapted from the prior affine pixel-to-metric adapter. This only calibrates
coordinates; it does not infer walls, doors or room topology from a drawing.
"""
from __future__ import annotations

import numpy as np


def calibrate_polygons(predictions: list[dict], calibration: dict) -> dict:
    affine = np.asarray(calibration["pixel_to_world_m"], dtype=float)
    if affine.shape != (2, 3) or not np.isfinite(affine).all() or abs(np.linalg.det(affine[:, :2])) < 1e-12:
        raise ValueError("NEEDS_SCALE: finite nonsingular 2x3 affine required")
    if not calibration.get("source_image_sha256") or not calibration.get("scale_evidence"):
        raise ValueError("source hash and scale evidence required")
    image_ids = {p["image_id"] for p in predictions}
    if len(image_ids) != 1:
        raise ValueError("all polygons must come from one complete floorplan image")
    result = []
    ids = set()
    for p in predictions:
        if p["id"] in ids:
            raise ValueError("duplicate polygon ID")
        ids.add(p["id"])
        xy = np.asarray(p["segmentation"], dtype=float).reshape(-1, 2)
        if len(xy) < 3 or not np.isfinite(xy).all():
            raise ValueError("invalid source polygon")
        metric = np.c_[xy, np.ones(len(xy))] @ affine.T
        result.append({"id": p["id"], "category_id": p["category_id"],
                       "vertices_m": metric.tolist(), "source_image_id": p["image_id"]})
    return {"units": "m", "world_frame": "RH_Z_UP", "provenance": "CALIBRATED_PIXEL_POLYGONS_ONLY",
            "source_image_sha256": calibration["source_image_sha256"],
            "scale_evidence": calibration["scale_evidence"], "polygons": result}
