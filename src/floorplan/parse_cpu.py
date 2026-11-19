"""Conservative whole-image CPU baseline. Emits candidates, never invents doors.

The raster path uses OpenCV morphology and connected components. Its output is
an observation contract, not a valid Metric Scene until topology and scale are
independently established.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def read_floorplan(path: Path):
    import cv2
    import numpy as np

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pymupdf as fitz

        doc = fitz.open(path)
        if len(doc) != 1:
            raise ValueError("UNSUPPORTED_GEOMETRY: PDF must have exactly one floor/page")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)[:, :, ::-1].copy()
    elif suffix in {".png", ".jpg", ".jpeg"}:
        image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    else:
        raise ValueError(f"UNSUPPORTED_FORMAT: {suffix}")
    if image is None or min(image.shape[:2]) < 128:
        raise ValueError("INVALID_IMAGE: unreadable or too small")
    return image


def parse(path: Path, out_dir: Path) -> dict:
    import cv2
    import numpy as np

    path = Path(path).resolve()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    image = read_floorplan(path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    # Long dark axis aligned traces. This intentionally does not label every
    # drawing stroke as a wall; furniture, text and dimensions cause ambiguity.
    dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    min_line = max(30, int(min(h, w) * .035))
    traces = []
    overlay = image.copy()
    for axis, kernel in (("H", (min_line, 2)), ("V", (2, min_line))):
        mask = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kernel))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        for i in range(1, n):
            x, y, bw, bh, area = (int(t) for t in stats[i])
            length = bw if axis == "H" else bh
            thickness = bh if axis == "H" else bw
            if length < min_line or thickness > max(18, length * .12):
                continue
            center = y + bh / 2 if axis == "H" else x + bw / 2
            traces.append({"id": f"trace_{len(traces):04d}", "axis": axis,
                           "pixel_span": [x, x + bw] if axis == "H" else [y, y + bh],
                           "pixel_center": center, "pixel_thickness": thickness,
                           "bbox_px": [x, y, x + bw, y + bh], "confidence": .55,
                           "source_evidence": {"kind": "dark_line_morphology", "bbox_px": [x, y, x + bw, y + bh]}})
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (0, 0, 255), 2)
    # Enclosed light regions are room candidates, not semantic room labels.
    wall_mask = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    free = cv2.bitwise_not(wall_mask)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(free)
    regions = []
    for i in range(1, n):
        x, y, bw, bh, area = (int(t) for t in stats[i])
        if area < h * w * .006 or x == 0 or y == 0 or x + bw >= w or y + bh >= h:
            continue
        fill = area / (bw * bh)
        if fill < .45:
            continue
        regions.append({"id": f"region_{len(regions):04d}", "bbox_px": [x, y, x + bw, y + bh],
                        "area_px2": area, "rectangularity": round(fill, 3), "semantic": "UNKNOWN",
                        "confidence": round(min(.7, fill * .7), 3),
                        "source_evidence": {"kind": "enclosed_light_component", "bbox_px": [x, y, x + bw, y + bh]}})
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (0, 180, 0), 2)
    cv2.imwrite(str(out_dir / "parser_overlay.png"), overlay)
    cv2.imwrite(str(out_dir / "dark_mask.png"), dark)
    result = {"parser": "opencv_morphology_cpu_v1", "source_file": str(path),
              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "image_size_px": [w, h], "wall_traces": traces, "room_candidates": regions,
              "door_candidates": [], "window_candidates": [],
              "limitations": ["No verified metric scale", "No reliable door/window classification",
                              "Room candidates may be split by furniture/text or merged through doors"],
              "status": "PARSED_CANDIDATES_ONLY"}
    (out_dir / "raw_prediction.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = parse(a.input, a.output)
    print(json.dumps({"status": result["status"], "traces": len(result["wall_traces"]),
                      "room_candidates": len(result["room_candidates"])}))
