"""Read GLB bounds through scene-node transforms; never execute model content."""

import hashlib
import itertools
import json
import struct
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]


def inspect(path: Path) -> dict:
    """Return decoded, world-space mesh bounds and a checksum."""
    body = path.read_bytes()
    if body[:4] != b"glTF" or struct.unpack_from("<I", body, 4)[0] != 2:
        raise ValueError(f"Not a GLB 2.0 asset: {path}")
    length = struct.unpack_from("<I", body, 12)[0]
    model = json.loads(body[20 : 20 + length])
    bounds = []
    triangles = 0

    def visit(index: int, parent: np.ndarray) -> None:
        nonlocal triangles
        node = model["nodes"][index]
        if "matrix" in node:
            local = np.array(node["matrix"]).reshape(4, 4, order="F")
        else:
            local = np.eye(4)
            local[:3, :3] = Rotation.from_quat(node.get("rotation", [0, 0, 0, 1])).as_matrix() @ np.diag(
                node.get("scale", [1, 1, 1])
            )
            local[:3, 3] = node.get("translation", [0, 0, 0])
        world = parent @ local
        if "mesh" in node:
            for primitive in model["meshes"][node["mesh"]]["primitives"]:
                accessor = model["accessors"][primitive["attributes"]["POSITION"]]
                low = np.array(accessor["min"], dtype=float)
                high = np.array(accessor["max"], dtype=float)
                if accessor.get("normalized"):
                    divisor = {5120: 127, 5121: 255, 5122: 32767, 5123: 65535}[accessor["componentType"]]
                    low = np.maximum(-1, low / divisor)
                    high = np.maximum(-1, high / divisor)
                for vertex in itertools.product(*zip(low, high, strict=True)):
                    bounds.append((world @ np.array([*vertex, 1]))[:3])
                triangles += (
                    model["accessors"][primitive["indices"]]["count"] // 3
                    if "indices" in primitive
                    else accessor["count"] // 3
                )
        for child in node.get("children", []):
            visit(child, world)

    for index in model["scenes"][model.get("scene", 0)]["nodes"]:
        visit(index, np.eye(4))
    b = np.array(bounds)
    low = b.min(axis=0)
    high = b.max(axis=0)
    return {
        "bounds_min": low.tolist(),
        "bounds_max": high.tolist(),
        "size": (high - low).tolist(),
        "triangles": triangles,
        "sha256": hashlib.sha256(body).hexdigest(),
        "images": model.get("images", []),
    }


if __name__ == "__main__":
    result = {
        str(p.relative_to(ROOT / "web_gui/assets/models")): inspect(p)
        for p in (ROOT / "web_gui/assets/models").rglob("*.glb")
    }
    (ROOT / "web_gui/assets/models/bounds.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, entry in result.items():
        print(name, entry["size"], entry["triangles"])
