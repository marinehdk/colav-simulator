"""Bounded radar checkpoints and sealed-window projection; no runtime imports."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from collections.abc import Callable


def checkpoint_key(checkpoint: dict) -> str:
    """Hash bytes and acquisition metadata together."""
    return hashlib.sha256(json.dumps(checkpoint, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class RadarCheckpointCache:
    """Keep 16 snapshots; evicted evidence is an explicit 404."""

    def __init__(self):
        """Create a bounded, thread-safe evidence cache."""
        self._items: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def reference(self, checkpoint: dict) -> dict:
        """Return a same-origin content-addressed checkpoint URL."""
        key = checkpoint_key(checkpoint)
        with self._lock:
            self._items[key] = checkpoint
            self._items.move_to_end(key)
            while len(self._items) > 16:
                self._items.popitem(last=False)
        return {"url": f"/api/radar/checkpoints/{key}", "checkpoint_key": key}

    def get(self, key: str) -> dict | None:
        """Read recorded evidence without running a sensor."""
        with self._lock:
            return self._items.get(key)


LIVE_CHECKPOINTS = RadarCheckpointCache()


def project_scans(scans: list, reference: Callable[[dict], dict]) -> list:
    """Copy changed branches; never mutate producer or sealed frames."""
    result = []
    for original in scans:
        scan = dict(original)
        video = scan.get("shadow_video")
        if isinstance(video, dict) and isinstance(video.get("checkpoint"), dict) and "data" in video["checkpoint"]:
            scan["shadow_video"] = {**video, "checkpoint": reference(video["checkpoint"])}
        result.append(scan)
    return result


def project_radar_window(document: dict) -> dict:
    """Transmit each checkpoint once per bounded replay window."""
    checkpoints = {}

    def reference(checkpoint: dict) -> dict:
        key = checkpoint_key(checkpoint)
        checkpoints[key] = checkpoint
        return {"$radar_checkpoint": key}

    def frame(original: dict | None) -> dict | None:
        if original is None:
            return None
        payload = dict(original.get("payload", {}))
        for name, ship in payload.items():
            if isinstance(ship, dict) and ship.get("radar_scans"):
                payload[name] = {**ship, "radar_scans": project_scans(ship["radar_scans"], reference)}
        return {**original, "payload": payload}

    result = {**document, "frames": [frame(item) for item in document.get("frames", [])]}
    for name in ("before", "after"):
        if name in document:
            result[name] = frame(document[name])
    if checkpoints:
        result["radar_checkpoints"] = checkpoints
    return result
