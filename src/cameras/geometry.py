"""Global Blender camera validation and pixel/world transforms in metres."""
from __future__ import annotations

import numpy as np


def validate_camera(K, c2w, image_size: tuple[int, int]) -> None:
    K = np.asarray(K, dtype=float)
    C = np.asarray(c2w, dtype=float)
    if K.shape != (3, 3) or C.shape != (4, 4) or not np.isfinite(K).all() or not np.isfinite(C).all():
        raise ValueError("Camera matrices must be finite 3x3 and 4x4")
    if not np.allclose(C[3], [0, 0, 0, 1], atol=1e-6):
        raise ValueError("Invalid homogeneous camera pose")
    R = C[:3, :3]
    if not np.allclose(R.T @ R, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(R), 1, atol=1e-5):
        raise ValueError("Camera rotation must be right handed and orthonormal")
    w, h = image_size
    if w <= 0 or h <= 0 or K[0, 0] <= 0 or K[1, 1] <= 0 or not 0 < K[0, 2] < w or not 0 < K[1, 2] < h:
        raise ValueError("Invalid camera intrinsics or image size")
    if not np.allclose(K[2], [0, 0, 1], atol=1e-6):
        raise ValueError("Invalid intrinsic homogeneous row")


def unproject(u: np.ndarray, v: np.ndarray, depth_z_m: np.ndarray, K, c2w) -> np.ndarray:
    """Blender depth pass is camera-axis Z distance; pixel centres use +0.5."""
    K, C = np.asarray(K), np.asarray(c2w)
    d = np.asarray(depth_z_m)
    camera = np.stack(((u + .5 - K[0, 2]) / K[0, 0] * d,
                       -(v + .5 - K[1, 2]) / K[1, 1] * d, -d, np.ones_like(d)))
    return C @ camera
