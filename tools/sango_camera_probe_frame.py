#!/usr/bin/env python3
"""P1-1a E2E frame composer (spec #90 review fix batch).

The sango twin's live mode does not render the scenario target ahead of the
ownship (Unity-side gap, ledgered in review-residue.md), so the camera causal
E2E cannot rely on the mast feed showing the target vessel. This composer
closes the loop through the REAL frame contract: it takes the REAL twin mast
feed render and draws the target vessel into its georef-projected pixel box —
the exact inverse of ``mast_cameras.georeference_box`` (bearing from the box
centre column, range from the box height against the 2.5 m boat prior). Real
YOLO then detects it, the observations endpoint georefs it back to within a
few metres of the simulator truth, and the assembled camera sensor associates.

Pure OpenCV drawing on the real render; the ZMQ/endpoint/tracker chain stays
untouched. Usage:
    .venv-detector/bin/python tools/sango_camera_probe_frame.py \
        --feed output/sango-twin-camera/feed-frame.jpg --out /tmp/composed.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from colav_simulator.core.mast_cameras import (  # noqa: E402
    CLASS_HEIGHT_PRIOR_M,
    FEED_HEIGHT_PX,
    FEED_MOUNT_ID,
    FEED_WIDTH_PX,
    MAST_MOUNTS_BY_ID,
    focal_px,
)


def compose(feed_path: Path, out_path: Path, range_m: float, boat_crop: Path | None) -> dict:
    mount = MAST_MOUNTS_BY_ID[FEED_MOUNT_ID]
    frame = cv2.imread(str(feed_path))
    if frame is None:
        raise FileNotFoundError(f"feed frame not found: {feed_path}")
    height, width = frame.shape[:2]

    fx = focal_px(mount.hfov_deg, width)
    height_prior = CLASS_HEIGHT_PRIOR_M["boat"]
    box_height_px = fx * height_prior / range_m
    # Dead-ahead target: box centre on the optical axis (bearing offset 0);
    # box bottom at the waterline of a near object (just below the horizon band).
    u_center = width / 2.0
    v_bottom = int(height * 0.52)
    x0, x1 = int(u_center - box_height_px * 1.6), int(u_center + box_height_px * 1.6)
    y0, y1 = int(v_bottom - box_height_px), int(v_bottom)

    if boat_crop is not None and boat_crop.is_file():
        # Real boat photo (repo paper figure, YOLO-verified at conf 0.81 on the
        # source page) resized onto the projected box — photoreal pixels keep
        # the detector in its trained domain, unlike synthetic drawings.
        crop = cv2.imread(str(boat_crop))
        if crop is None:
            raise FileNotFoundError(f"boat crop not found: {boat_crop}")
        box_h = int(round(box_height_px))
        box_w = int(max(box_h * (crop.shape[1] / crop.shape[0]), box_height_px * 1.6))
        x0, x1 = int(u_center - box_w / 2), int(u_center + box_w / 2)
        y0, y1 = v_bottom - box_h, v_bottom
        resized = cv2.resize(crop, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
        mask = np.zeros((y1 - y0, x1 - x0), dtype=np.float32)
        cv2.ellipse(mask, ((x1 - x0) // 2, (y1 - y0) // 2), ((x1 - x0) // 2 - 2, (y1 - y0) // 2 - 2), 0, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (0, 0), 3)[..., None]
        frame[y0:y1, x0:x1] = (resized * mask + frame[y0:y1, x0:x1] * (1.0 - mask)).astype(np.uint8)
    else:
        # Fallback silhouette (dark hull + white superstructure).
        box_h = int(round(box_height_px))
        box_w = int(box_height_px * 1.6)
        x0, x1 = int(u_center - box_w / 2), int(u_center + box_w / 2)
        y0, y1 = v_bottom - box_h, v_bottom
        hull_top = int(y0 + 0.45 * (y1 - y0))
        cv2.rectangle(frame, (x0, hull_top), (x1, y1), (70, 55, 40), -1)
        cv2.rectangle(frame, (x0 + 6, y0), (x1 - 6, hull_top), (235, 240, 245), -1)
    cv2.imwrite(str(out_path), frame)
    return {
        "box_xyxy": [x0, y0, x1, y1],
        "box_height_px": box_height_px,
        "projected_range_m": fx * height_prior / max(y1 - y0, 1),
        "u_center": u_center,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", default=str(REPO_ROOT / "output/sango-twin-camera/feed-frame.jpg"))
    parser.add_argument("--out", default="/tmp/sango-camera-composed.jpg")
    parser.add_argument("--range-m", type=float, default=15.0, help="projected target range (georef lands here)")
    parser.add_argument("--boat-crop", default=str(REPO_ROOT / "output/sango-twin-camera/boat-crop.png"),
                        help="real boat photo crop pasted into the projected box")
    args = parser.parse_args()
    info = compose(Path(args.feed), Path(args.out), args.range_m, Path(args.boat_crop))
    print(f"[compose] {args.out} box={info['box_xyxy']} projected_range={info['projected_range_m']:.1f}m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
