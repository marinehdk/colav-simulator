"""Build an original, unit-sized low-poly display hull (glTF Y-up, +X forward).

No measured hull or hydrodynamic geometry is implied. ModelMatrix supplies the
telemetry length, beam and explicitly illustrative above-water height.
"""

import base64
import json
import struct
from pathlib import Path

vertices = []
indices = []


def prism(outline: list[tuple[float, float]], bottom: float, top: float) -> None:
    """Append one closed prism to the unit hull mesh."""
    start = len(vertices)
    vertices.extend((x, y, z) for y in (bottom, top) for x, z in outline)
    n = len(outline)
    for i in range(1, n - 1):
        indices.extend((start + n, start + n + i, start + n + i + 1))
        indices.extend((start, start + i + 1, start + i))
    for i in range(n):
        j = (i + 1) % n
        indices.extend((start + i, start + j, start + n + j, start + i, start + n + j, start + n + i))


prism([(-0.5, -0.5), (0.25, -0.5), (0.5, 0), (0.25, 0.5), (-0.5, 0.5)], 0, 0.4)
prism([(-0.3, -0.3), (0.05, -0.3), (0.05, 0.3), (-0.3, 0.3)], 0.4, 1)
positions = struct.pack("<" + "f" * (3 * len(vertices)), *(v for p in vertices for v in p))
triangles = struct.pack("<" + "H" * len(indices), *indices)
blob = positions + triangles
model = {
    "asset": {"version": "2.0", "generator": "Colav-Simulator illustrative hull"},
    "extensionsUsed": ["KHR_materials_unlit"],
    "scene": 0,
    "scenes": [{"nodes": [0]}],
    "nodes": [{"mesh": 0}],
    "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
    "materials": [
        {
            "doubleSided": True,
            "extensions": {"KHR_materials_unlit": {}},
            "pbrMetallicRoughness": {"baseColorFactor": [0.88, 0.91, 0.94, 1]},
        }
    ],
    "buffers": [{"byteLength": len(blob), "uri": "data:application/octet-stream;base64," + base64.b64encode(blob).decode()}],
    "bufferViews": [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
        {"buffer": 0, "byteOffset": len(positions), "byteLength": len(triangles)},
    ],
    "accessors": [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": len(vertices),
            "type": "VEC3",
            "min": [-0.5, 0, -0.5],
            "max": [0.5, 1, 0.5],
        },
        {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
    ],
}
Path("web_gui/assets/3d/vessel.gltf").write_text(json.dumps(model, separators=(",", ":")) + "\n")
