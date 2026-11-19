"""Independent count and geometry check against CubiCasa human SVG labels."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np

from src.floorplan.cubicasa_vector_adapter import bbox, polygon


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    aa = (a[2] - a[0]) * (a[3] - a[1])
    bb = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (aa + bb - intersection) if aa + bb > intersection else 0.0


def evaluate(prediction: Path, svg: Path, out: Path):
    pred = json.loads(prediction.read_text())
    root = ET.parse(svg).getroot()
    rooms, walls, doors, windows = [], [], [], []
    for g in root.iter():
        cls = g.attrib.get("class", "")
        if cls.startswith("Space ") and "Outdoor" not in cls and cls != "Space Undefined":
            rooms.append(bbox(polygon(g)))
        elif cls.startswith("Wall"):
            walls.append(polygon(g))
        elif cls.startswith("Door "):
            doors.append(bbox(polygon(g)))
        elif cls.startswith("Window "):
            windows.append(bbox(polygon(g)))
    candidates = [x["bbox_px"] for x in pred["room_candidates"]]
    pairs = sorted(((iou(a, b), i, j) for i, a in enumerate(candidates) for j, b in enumerate(rooms)), reverse=True)
    matched_pred, matched_gt, matches = set(), set(), []
    for score, i, j in pairs:
        if score < .5 or i in matched_pred or j in matched_gt:
            continue
        matched_pred.add(i); matched_gt.add(j); matches.append({"candidate": i, "annotation": j, "bbox_iou": round(score, 4)})
    mask = np.zeros((pred["image_size_px"][1], pred["image_size_px"][0]), dtype=np.uint8)
    for points in walls:
        cv2.fillPoly(mask, [np.rint(np.asarray(points)).astype(np.int32)], 255)
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    trace_match = []
    for trace in pred["wall_traces"]:
        a, b = map(int, trace["pixel_span"])
        c = int(round(trace["pixel_center"]))
        if trace["axis"] == "H":
            segment = mask[max(0, c):c + 1, max(0, a):b]
        else:
            segment = mask[max(0, a):b, max(0, c):c + 1]
        overlap = float(np.mean(segment > 0)) if segment.size else 0.0
        trace_match.append(overlap)
    result = {"source": "CUBICASA5K_HUMAN_SVG_REFERENCE_NOT_PARSER_INPUT",
              "rooms": {"candidate_count": len(candidates), "reference_count": len(rooms),
                        "matched_iou_ge_0_5": len(matches), "precision": len(matches) / len(candidates) if candidates else 0,
                        "recall": len(matches) / len(rooms) if rooms else 0, "matches": matches},
              "walls": {"trace_count": len(trace_match), "reference_polygon_count": len(walls),
                        "traces_overlapping_reference_ge_0_5": sum(x >= .5 for x in trace_match),
                        "trace_precision_proxy": sum(x >= .5 for x in trace_match) / len(trace_match) if trace_match else 0},
              "doors": {"candidate_count": len(pred["door_candidates"]), "reference_count": len(doors),
                        "recall": 0 if doors else None},
              "windows": {"candidate_count": len(pred["window_candidates"]), "reference_count": len(windows),
                          "recall": 0 if windows else None},
              "limitations": ["Wall trace overlap is a pixel proxy, not instance level wall F1",
                              "Annotation alignment to source raster may introduce small IoU error"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("prediction", type=Path)
    p.add_argument("svg", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args()
    print(json.dumps(evaluate(a.prediction, a.svg, a.out)))
