"""Decode Blender 5.3 multipart EXR into aligned RGB, metric depth and IDs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import OpenEXR
from PIL import Image, ImageDraw


def srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.clip(linear, 0, 1)
    return np.where(linear <= 0.0031308, 12.92 * linear,
                    1.055 * np.power(linear, 1 / 2.4) - 0.055)


def decode(root: Path) -> dict:
    meta = json.loads((root / "camera_metadata.json").read_text())
    rows = []
    tiles = []
    for frame in meta["frames"]:
        cid = frame["camera_id"]
        exr = OpenEXR.File(str(root / "passes" / f"{cid}.exr"))
        parts = {p.name(): p for p in exr.parts}
        assert set(parts) == {"Image", "Depth", "ObjectID"}, set(parts)
        rgba = parts["Image"].channels["Image"].pixels
        depth = parts["Depth"].channels["Depth.V"].pixels.astype(np.float32)
        ids = np.rint(parts["ObjectID"].channels["ObjectID.V"].pixels).astype(np.int32)
        assert rgba.shape[:2] == depth.shape == ids.shape
        rgb = (srgb(rgba[:, :, :3]) * 255 + 0.5).astype(np.uint8)
        Image.fromarray(rgb, "RGB").save(root / "rgb" / f"{cid}.png")
        np.save(root / "depth" / f"{cid}.npy", depth)
        np.save(root / "object_id" / f"{cid}.npy", ids)
        valid = np.isfinite(depth) & (depth < 1e8)
        d = np.zeros_like(depth, dtype=np.uint8)
        if valid.any():
            d[valid] = np.clip(255 * (1 - depth[valid] / 15), 0, 255).astype(np.uint8)
        Image.fromarray(d, "L").save(root / "depth" / f"{cid}.png")
        palette = np.stack(((ids * 59) % 256, (ids * 137) % 256, (ids * 211) % 256), axis=-1).astype(np.uint8)
        Image.fromarray(palette, "RGB").save(root / "object_id" / f"{cid}.png")
        rows.append({"camera_id": cid, "shape": list(depth.shape), "finite_depth_pixels": int(valid.sum()),
                     "depth_range_m": [float(depth[valid].min()), float(depth[valid].max())] if valid.any() else None,
                     "visible_object_indices": [int(x) for x in np.unique(ids)]})
        tile = Image.fromarray(rgb).resize((256, 256))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, 256, 20), fill=(20, 20, 20))
        draw.text((4, 3), cid, fill=(255, 255, 255))
        tiles.append(tile)
    canvas = Image.new("RGB", (4 * 256, 4 * 256))
    for i, tile in enumerate(tiles):
        canvas.paste(tile, ((i % 4) * 256, (i // 4) * 256))
    canvas.save(root / "contact_sheet.png")
    result = {"variant": meta["variant"], "frame_count": len(rows), "frames": rows,
              "provenance": "SYNTHETIC_BLENDER_CPU"}
    (root / "decode_check.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("render_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(decode(args.render_root), indent=2))
