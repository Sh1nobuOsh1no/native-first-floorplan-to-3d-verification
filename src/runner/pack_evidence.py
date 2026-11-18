"""Compress aligned depth/object-ID arrays for compact public CPU evidence."""
from pathlib import Path

import numpy as np


def main():
    root = Path("evidence/cpu")
    for variant in ("A", "B"):
        render = root / f"render_{variant}"
        for kind in ("depth", "object_id"):
            arrays = {p.stem: np.load(p) for p in sorted((render / kind).glob("*.npy"))}
            assert len(arrays) == 16
            target = render / f"{kind}_all.npz"
            np.savez_compressed(target, **arrays)
            with np.load(target) as check:
                assert set(check.files) == set(arrays)
            print(target, target.stat().st_size)


if __name__ == "__main__":
    main()
