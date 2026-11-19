"""Auditable deterministic agent rules over parser candidates.

No language model is invoked. The only implemented edits merge duplicate or
broken collinear traces when the original raster supports the merged pixels.
"""
from __future__ import annotations

import json
from pathlib import Path


ALLOWED_EDITS = {"MERGE_DUPLICATE_TRACE", "BRIDGE_EVIDENCED_TRACE_GAP"}


def revise(prediction: dict, image_path: Path, out_dir: Path, max_rounds: int = 2) -> dict:
    import cv2
    import numpy as np
    from src.floorplan.parse_cpu import read_floorplan

    image = cv2.cvtColor(read_floorplan(Path(image_path)), cv2.COLOR_BGR2GRAY)
    traces = [dict(t) for t in prediction["wall_traces"]]
    history = []
    for turn in range(max_rounds):
        changed = False
        for i, a in enumerate(traces):
            for j in range(i + 1, len(traces)):
                b = traces[j]
                if a["axis"] != b["axis"] or abs(a["pixel_center"] - b["pixel_center"]) > 3:
                    continue
                a0, a1 = a["pixel_span"]
                b0, b1 = b["pixel_span"]
                gap = max(a0, b0) - min(a1, b1)
                if gap > 12:
                    continue
                edit = "MERGE_DUPLICATE_TRACE" if gap <= 0 else "BRIDGE_EVIDENCED_TRACE_GAP"
                if edit not in ALLOWED_EDITS:
                    continue
                lo, hi = (int(min(a1, b1)), int(max(a0, b0))) if gap > 0 else (0, 0)
                if gap > 0:
                    c = int(round((a["pixel_center"] + b["pixel_center"]) / 2))
                    patch = image[max(0, c - 2):c + 3, lo:hi] if a["axis"] == "H" else image[lo:hi, max(0, c - 2):c + 3]
                    if patch.size == 0 or float(np.mean(patch < 128)) < .75:
                        continue
                before = [a.copy(), b.copy()]
                a["pixel_span"] = [min(a0, b0), max(a1, b1)]
                a["pixel_thickness"] = max(a["pixel_thickness"], b["pixel_thickness"])
                a["bbox_px"] = [min(a["bbox_px"][0], b["bbox_px"][0]),
                                min(a["bbox_px"][1], b["bbox_px"][1]),
                                max(a["bbox_px"][2], b["bbox_px"][2]),
                                max(a["bbox_px"][3], b["bbox_px"][3])]
                a["source_evidence"] = {"kind": edit, "source_trace_ids": [before[0]["id"], before[1]["id"]],
                                        "gap_px": [lo, hi] if gap > 0 else None}
                traces.pop(j)
                history.append({"round": turn + 1, "edit_type": edit, "before": before,
                                "after": a.copy(), "reason": "collinear traces with source pixel support",
                                "source_evidence": a["source_evidence"], "validation": "axis_and_pixel_check_passed"})
                changed = True
                break
            if changed:
                break
        if not changed:
            break
    revised = dict(prediction)
    revised["wall_traces"] = traces
    revised["agent_revision"] = {"implementation": "deterministic_rules_v1", "model_used": False,
                                 "max_rounds": max_rounds, "edits": len(history), "history": history}
    revised["status"] = "AGENT_REVISED_CANDIDATES" if history else "PARSER_ONLY_CANDIDATES"
    out_dir = Path(out_dir)
    (out_dir / "agent_revision.json").write_text(json.dumps(revised["agent_revision"], indent=2) + "\n")
    (out_dir / "revised_prediction.json").write_text(json.dumps(revised, indent=2) + "\n")
    return revised


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("prediction", type=Path)
    p.add_argument("image", type=Path)
    p.add_argument("out", type=Path)
    a = p.parse_args()
    result = revise(json.loads(a.prediction.read_text()), a.image, a.out)
    print(json.dumps({"status": result["status"], "edits": result["agent_revision"]["edits"]}))
