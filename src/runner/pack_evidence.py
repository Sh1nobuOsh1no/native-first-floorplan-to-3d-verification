"""Compress aligned depth/object-ID arrays for compact public CPU evidence."""
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("evidence/cpu"))
    root = p.parse_args().root
    for variant in ("A", "B"):
        render = root / f"render_{variant}"
        camera_ids = [f["camera_id"] for f in json.loads((render / "camera_metadata.json").read_text())["frames"]]
        for kind in ("depth", "object_id"):
            arrays = {cid: np.load(render / kind / f"{cid}.npy") for cid in camera_ids}
            expected = json.loads((render / "render_manifest.json").read_text())["frame_count"]
            assert len(arrays) == expected, (render, kind, len(arrays), expected)
            target = render / f"{kind}_all.npz"
            np.savez_compressed(target, **arrays)
            with np.load(target) as check:
                assert set(check.files) == set(arrays)
            print(target, target.stat().st_size)


if __name__ == "__main__":
    main()
