"""Exercise GenRecon's unmodified Sage_gt CPU input readers on official renders.

This stops before loading weights or running any network forward pass.
"""

import argparse
import json
import sys
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--render-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--n-views", type=int, default=8)
    parser.add_argument("--scene", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from inference.get_chunks import SageGtChunker
    from inference.get_images import SageImageSelecter, _FLIP_Y_Z

    torch.set_num_threads(4)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "chunks").mkdir(parents=True, exist_ok=True)
    (args.out_dir / "images").mkdir(parents=True, exist_ok=True)
    chunks = SageGtChunker()
    centers, original_to_chunks, chunk_to_originals, relative_translations = chunks.get_chunks(
        args.render_dir, args.out_dir / "chunks"
    )
    selector = SageImageSelecter()
    selected = selector.get_images(
        original_to_chunks, args.render_dir / "transforms.json", args.n_views,
        args.out_dir / "images", seed=42
    )
    source_scene = json.loads(args.scene.read_text())
    source_cameras = {c["id"]: c for c in source_scene["cameras"]}
    native_cameras = selector._get_cameras(args.render_dir / "transforms.json")
    native_picks = json.loads((args.out_dir / "images" / "cameras.json").read_text())
    visible_by_chunk = []
    for idx, transform in enumerate(original_to_chunks):
        accepted = []
        for cam in native_cameras:
            ext = _FLIP_Y_Z @ torch.linalg.inv(transform @ cam["c2w_blender"])
            if selector._check_acceptance(ext, cam["intrinsics"]):
                accepted.append(Path(cam["img_path"]).stem)
        picked = Path(native_picks["chunks"][idx]["cond2d_view"]["img_path"]).stem
        visible_by_chunk.append({"index": idx, "center_m": centers[idx],
                                 "accepted_camera_count": len(accepted),
                                 "accepted_camera_ids": accepted,
                                 "selected_camera_id": picked,
                                 "fallback_used": picked not in accepted,
                                 "accepted_spaces": sorted({source_cameras[x]["space_id"] for x in accepted})})
    door_visibility = []
    for wall in source_scene["walls"]:
        p0, p1 = wall["p0_m"], wall["p1_m"]
        length = ((p1[0]-p0[0])**2 + (p1[1]-p0[1])**2)**0.5
        for op in wall.get("openings", []):
            if op["kind"] != "door":
                continue
            t = (op["u0_m"] + op["u1_m"]) / (2*length)
            xy = [p0[j] + t*(p1[j]-p0[j]) for j in (0,1)]
            near = [v for v in visible_by_chunk if ((v["center_m"][0]-xy[0])**2 + (v["center_m"][1]-xy[1])**2)**0.5 <= 2.0]
            door_visibility.append({"door_id": op["id"], "connects": op["connects"],
                                    "near_chunk_count": len(near),
                                    "chunks_with_both_side_cameras": [v["index"] for v in near
                                      if set(op["connects"]) <= set(v["accepted_spaces"])]})
    report = {
        "status": "PASS_CPU_NATIVE_READER",
        "repo": str(args.repo.resolve()), "render_dir": str(args.render_dir.resolve()),
        "chunk_centers": centers,
        "n_chunk_transforms": len(original_to_chunks),
        "n_inverse_transforms": len(chunk_to_originals),
        "n_relative_translations": len(relative_translations),
        "scene_images_512_shape": list(selected.scene_images_512.shape),
        "scene_images_1024_shape": list(selected.scene_images_1024.shape),
        "scene_intrinsics_shape": list(selected.scene_intrinsics.shape),
        "scene_extrinsics_c0_shape": list(selected.scene_extrinsics_c0.shape),
        "n_cond2d_images": len(selected.cond2d_images_512),
        "chunk_indices": selected.chunk_indices,
        "images_finite": bool(torch.isfinite(selected.scene_images_512).all()),
        "extrinsics_finite": bool(torch.isfinite(selected.scene_extrinsics_c0).all()),
        "image_min_max": [float(selected.scene_images_512.min()), float(selected.scene_images_512.max())],
        "native_output_files": [str(x) for x in sorted(args.out_dir.rglob("*")) if x.is_file()],
        "source_scene_provenance": source_scene["provenance"],
        "source_camera_count": len(source_scene["cameras"]),
        "native_camera_count": len(native_cameras),
        "visible_by_chunk": visible_by_chunk,
        "zero_visible_chunks": [x["index"] for x in visible_by_chunk if not x["accepted_camera_count"]],
        "fallback_chunks": [x["index"] for x in visible_by_chunk if x["fallback_used"]],
        "door_visibility": door_visibility,
        "native_layout_limitation": "Sage_gt uses only first room outer width/length and fixed 2.7m height; interior walls and door topology are not hard constraints.",
        "disclaimer": "Only original CPU input readers ran; no GenRecon model inference or training.",
    }
    if not report["images_finite"] or not report["extrinsics_finite"] or not centers:
        report["status"] = "FAIL_CPU_NATIVE_READER"
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "n_chunks": len(centers),
                      "scene_images_512_shape": report["scene_images_512_shape"],
                      "n_cond2d_images": report["n_cond2d_images"]}, ensure_ascii=False))
    return 0 if report["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
