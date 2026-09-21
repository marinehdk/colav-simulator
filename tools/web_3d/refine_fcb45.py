"""Rebuild the supplied FCB45 visual shell from the user's five reference views.

Display-only, +Y up / -Z bow / midship waterline origin. Principal hull 45 x 8m.
Run with trimesh==4.7.4 and the project's NumPy/SciPy; no runtime dependency.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "web_gui/assets/models/fcb45/ownship.glb"
OUTPUT = ROOT / "web_gui/assets/models/fcb45/ownship-v1.glb"
PARTS = []
GROUPS = defaultdict(list)


def material(name: str, hex_color: str, roughness: float = 0.6, metal: float = 0.0) -> PBRMaterial:
    """Author linear glTF base-color factors from sRGB reference paint colors."""
    srgb = np.array([int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4)])
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    return PBRMaterial(
        name=name,
        baseColorFactor=np.r_[np.round(linear * 255), 255].astype(np.uint8),
        metallicFactor=metal,
        roughnessFactor=roughness,
        doubleSided=False,
    )


MATS = {
    "paint": material("FCB lime paint", "91ca43", 0.5, 0.02),
    "white": material("Off-white superstructure", "e4e9e6", 0.48, 0.02),
    "deck": material("Non-slip work deck", "79837f", 0.88),
    "black": material("Black livery and boot-top", "18241f", 0.58),
    "rubber": material("Rubber fenders", "242b29", 0.92),
    "rubber_rim": material("Raised tire sidewall", "4b5650", 0.72),
    "steel": material("Brushed guardrails", "929e99", 0.4, 0.45),
    "glass": material("Opaque tinted glazing", "16323a", 0.19, 0.22),
    "yellow": material("Safety yellow", "e6bc2c", 0.58),
    "red": material("Safety red", "c83830", 0.6),
    "bronze": material("Propeller bronze", "958053", 0.37, 0.55),
}


def add(name: str, mesh: trimesh.Trimesh, mat: str = "steel", smooth: bool = False) -> None:
    """Accumulate a named part with valid hard or smooth normals."""
    if not len(mesh.faces):
        return
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-8))
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not smooth:
        mesh.unmerge_vertices()
    mesh.vertex_normals = mesh.vertex_normals
    GROUPS[mat].append(mesh)
    PARTS.append({"name": name, "material": mat, "triangles": len(mesh.faces)})


def box(name: str, center: list[float], size: list[float], mat: str = "steel") -> None:
    """Add a hard-surface rectangular detail."""
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(center)
    add(name, mesh, mat)


def rod(name: str, a: list[float], b: list[float], radius: float = 0.03, mat: str = "steel", sections: int = 8) -> None:
    """Add a circular rail, frame or support between two endpoints."""
    add(name, trimesh.creation.cylinder(radius=radius, segment=[a, b], sections=sections), mat, True)


def patch(name: str, points: list[list[float]], mat: str, double: bool = False) -> None:
    """Triangulate one planar or ruled visual surface."""
    faces = [[0, i, i + 1] for i in range(1, len(points) - 1)]
    if double:
        faces += [[a, c, b] for a, b, c in faces.copy()]
    add(name, trimesh.Trimesh(vertices=points, faces=faces, process=False), mat)


# Bow taper, flare, hard chines and rounded stern corners; visual reconstruction.
STATIONS = np.array(
    [
        [-22.5, 0.025, 4.05],
        [-21.4, 0.85, 4.15],
        [-19, 1.92, 4.15],
        [-16, 2.95, 4.15],
        [-12, 3.62, 4.15],
        [-7, 3.95, 4.15],
        [0, 4, 4.15],
        [3.8, 4, 4.15],
        [4.15, 4, 2.45],
        [12, 4, 2.45],
        [20.8, 3.97, 2.45],
        [21.9, 3.84, 2.45],
        [22.5, 3.57, 2.45],
    ]
)


def width(z: float) -> float:
    """Interpolate the visual hull half-breadth."""
    return float(np.interp(z, STATIONS[:, 0], STATIONS[:, 1]))


def top(z: float) -> float:
    """Interpolate the deck sheer height."""
    return float(np.interp(z, STATIONS[:, 0], STATIONS[:, 2]))


def side(z: float, y: float) -> float:
    """Find the upper hull skin for visible markings."""
    # Match the hull's upper side band rather than burying decals in a flat plane.
    return width(z) * float(np.interp(y, [0.25, 0.65, top(z) - 0.16, top(z)], [0.94, 0.98, 1, 0.94]))


def clipped_transom(points: list[list[float]], above: bool) -> list[list[float]]:
    """Split the stern cap at the boot-top without painting underwater faces green."""
    output = []
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        inside_a = a[1] >= 0.25 if above else a[1] <= 0.25
        inside_b = b[1] >= 0.25 if above else b[1] <= 0.25
        if inside_a:
            output.append(a)
        if inside_a != inside_b:
            fraction = (0.25 - a[1]) / (b[1] - a[1])
            output.append([a[i] + fraction * (b[i] - a[i]) for i in range(3)])
    return output


def build_hull() -> None:
    """Build a tapered hull with chines, boot-top and surface-following livery."""
    rings = []
    for z, w, h in STATIONS:
        keel = -1.55 if z > -19 else float(np.interp(z, [-22.5, -19], [0.15, -1.55]))
        rings.append(
            [
                [x, y, z + max(0, (-19 - z) / 3.5) * 2.8 * max(0, (h - y) / (h - keel))]
                for x, y in [
                    (-0.94 * w, h),
                    (0.94 * w, h),
                    (w, h - 0.16),
                    (0.98 * w, 0.65),
                    (0.94 * w, 0.25),
                    (0.89 * w, -0.25),
                    (0.68 * w, -0.9),
                    (0.18 * w, keel),
                    (0, keel - 0.025),
                    (-0.18 * w, keel),
                    (-0.68 * w, -0.9),
                    (-0.89 * w, -0.25),
                    (-0.94 * w, 0.25),
                    (-0.98 * w, 0.65),
                    (-w, h - 0.16),
                ]
            ]
        )
    for i in range(len(rings) - 1):
        for j in range(len(rings[0])):
            k = (j + 1) % len(rings[0])
            mat = "black" if 4 <= j <= 11 else "paint"
            if j == 0:
                mat = "deck"
            patch(f"Hull section {i}/{j}", [rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]], mat, True)
    patch("Closed transom upper", clipped_transom(rings[-1], True), "paint", True)
    patch("Closed transom boot-top", clipped_transom(rings[-1], False), "black", True)
    patch("Closed bow", list(reversed(rings[0])), "paint", True)
    for sign in [-1, 1]:
        for i in range(len(STATIONS) - 1):
            z0, z1 = STATIONS[i : i + 2, 0]
            for label, height, radius, mat in [
                ("rubbing strake", None, 0.105, "rubber"),
                ("lower chine", 0.35, 0.045, "black"),
            ]:
                y0 = top(z0) - (1.45 if z0 < 4 else 0.7) if height is None else height
                y1 = top(z1) - (1.45 if z1 < 4 else 0.7) if height is None else height
                rod(
                    f"{label} {sign}/{i}",
                    [sign * (side(z0, y0) + 0.04), y0, z0],
                    [sign * (side(z1, y1) + 0.04), y1, z1],
                    radius,
                    mat,
                )
        for offset in [-2.5, 1.1]:
            for t in range(12):
                y0 = 0.4 + t * 3.63 / 12
                y1 = 0.4 + (t + 1) * 3.63 / 12
                z0 = offset + 2.3 - (y0 - 0.4) * 1.0
                z1 = offset + 2.3 - (y1 - 0.4) * 1.0
                pts = []
                for z, y in [(z0, y0), (z0 + 1.45, y0), (z1 + 1.45, y1), (z1, y1)]:
                    pts.append([sign * (side(z, y) + 0.025), y, z])
                patch(f"Diagonal hull livery {sign}/{offset}/{t}", pts, "black", True)
        for index, z in enumerate(np.linspace(-15.5, 2.5, 12)):
            y = 3.45
            pts = [
                [sign * (side(zz, yy) + 0.045), yy, zz]
                for zz, yy in [(z - 0.5, y - 0.27), (z + 0.5, y - 0.27), (z + 0.5, y + 0.27), (z - 0.5, y + 0.27)]
            ]
            patch(f"Passenger window {sign}/{index}", pts, "glass", True)
            for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
                rod(f"Passenger gasket {sign}/{index}", a, b, 0.025, "black", 6)


def rounded_outline(w: float, length: float, zcenter: float, radius: float = 0.55) -> list[list[float]]:
    """Sample a rounded rectangular cabin footprint."""
    points = []
    for cx, cz, start in [
        (w - radius, zcenter + length / 2 - radius, 0),
        (-w + radius, zcenter + length / 2 - radius, 90),
        (-w + radius, zcenter - length / 2 + radius, 180),
        (w - radius, zcenter - length / 2 + radius, 270),
    ]:
        for angle in np.linspace(start, start + 90, 4, endpoint=False):
            r = np.deg2rad(angle)
            points.append([cx + radius * np.cos(r), cz + radius * np.sin(r)])
    return points


def loft(name: str, bottom: list[list[float]], upper: list[list[float]], low: float, high: float, mat: str) -> None:
    """Join two closed cabin outlines and cap the roof."""
    for i in range(len(bottom)):
        j = (i + 1) % len(bottom)
        patch(
            name,
            [
                [bottom[i][0], low, bottom[i][1]],
                [bottom[j][0], low, bottom[j][1]],
                [upper[j][0], high, upper[j][1]],
                [upper[i][0], high, upper[i][1]],
            ],
            mat,
            True,
        )
    patch(name + " roof", [[x, high, z] for x, z in upper], mat, True)


def build_bridge() -> None:
    """Model raked wraparound glazing, access and aft equipment."""
    lower = rounded_outline(2.85, 9.5, -2.1)
    loft("Cabin white plinth", lower, lower, 4.16, 5.0, "white")
    glass_lower = rounded_outline(2.86, 9.5, -2.1)
    glass_upper = rounded_outline(3.22, 10.25, -2.1, 0.7)
    loft("Outward raked wraparound glazing", glass_lower, glass_upper, 5.03, 6.67, "glass")
    for i in range(len(glass_lower)):
        a = [glass_lower[i][0], 5.03, glass_lower[i][1]]
        b = [glass_upper[i][0], 6.67, glass_upper[i][1]]
        rod("Bridge window mullion", a, b, 0.045, "black")
        j = (i + 1) % len(glass_lower)
        rod("Bridge lower gasket", a, [glass_lower[j][0], 5.03, glass_lower[j][1]], 0.055, "black")
        rod("Bridge upper gasket", b, [glass_upper[j][0], 6.67, glass_upper[j][1]], 0.045, "black")
    for sign in [-1, 1]:
        for z in [-5.6, -3.8, -2.0, -0.2, 1.6]:
            rod("Side windshield frame", [sign * 2.875, 5.03, z], [sign * 3.235, 6.67, z], 0.038, "steel")
    for sign in [-1, 1]:
        for x in [-1.9, -0.65, 0.65, 1.9]:
            rod(
                "Front rear windshield frame",
                [x, 5.03, -2.1 + sign * 4.755],
                [x * 1.07, 6.67, -2.1 + sign * 5.13],
                0.035,
                "steel",
            )
    roof = rounded_outline(3.42, 10.65, -2.1, 0.8)
    loft("Overhanging roof", glass_upper, roof, 6.7, 6.88, "white")
    for i in range(len(roof)):
        j = (i + 1) % len(roof)
        rod("Roof edge", [roof[i][0], 6.84, roof[i][1]], [roof[j][0], 6.84, roof[j][1]], 0.055, "white")
    # Aft equipment wall, framed doors and access stair as in the rear view.
    box("Aft equipment bulkhead", [0, 3.28, 4.18], [5.8, 1.73, 0.1], "white")
    for x in [-1.95, 0, 1.95]:
        box("Aft door gasket", [x, 3.28, 4.26], [1.31, 1.69, 0.055], "black")
        box("Aft door panel", [x, 3.28, 4.30], [1.21, 1.59, 0.05], "white")
        box("Aft door glazing", [x, 3.64, 4.34], [0.70, 0.52, 0.025], "glass")
        rod("Door handle", [x + 0.43, 3.16, 4.37], [x + 0.43, 3.4, 4.37], 0.035)
    for i in range(8):
        box("Port access stair", [-3.05, 2.55 + i * 0.215, 6.1 - i * 0.24], [0.75, 0.09, 0.29], "deck")
    for x in [-3.5, -2.63]:
        rod("Stair handrail", [x, 3.35, 6.3], [x, 5.15, 4.3], 0.035)
    rod("Davit base", [-2.9, 4.2, 3.45], [-2.9, 5.7, 3.45], 0.12)
    rod("Davit boom", [-2.9, 5.7, 3.45], [-2.9, 6.65, 5.75], 0.09)
    rod("Davit cable", [-2.9, 6.65, 5.75], [-2.9, 4.6, 5.75], 0.012, "black", 6)


def build_deck() -> None:
    """Add rails, workdeck seams and visible mooring equipment."""
    for sign in [-1, 1]:
        zs = sorted({*np.linspace(-21.8, 3.6, 20), *np.linspace(4.4, 22.2, 13)})
        for z in zs:
            x = sign * width(z) * 0.92
            y = top(z)
            rod("Deck stanchion", [x, y, z], [x, y + 1.0, z], 0.026)
        for a, b in zip(zs[:-1], zs[1:], strict=True):
            for height in [0.48, 1.0]:
                rod(
                    "Continuous deck rail",
                    [sign * width(a) * 0.92, top(a) + height, a],
                    [sign * width(b) * 0.92, top(b) + height, b],
                    0.025,
                )
        for z in [6, 12, 18]:
            box("Green deck locker", [sign * 3.15, 2.75, z], [0.55, 0.55, 1.55], "paint")
        for z in [7, 20.8]:
            for dz in [-0.18, 0.18]:
                rod("Mooring bollard", [sign * 3.25, 2.45, z + dz], [sign * 3.25, 2.9, z + dz], 0.085, "steel", 12)
            rod("Bollard crossbar", [sign * 3.25, 2.83, z - 0.35], [sign * 3.25, 2.83, z + 0.35], 0.06)
    for z in np.linspace(5, 21.8, 10):
        box("Work deck cross seam", [0, 2.46, z], [6.9, 0.015, 0.035], "white")
    for x in [-2.6, 0, 2.6]:
        box("Work deck longitudinal seam", [x, 2.46, 13.3], [0.035, 0.015, 16.6], "white")
    for z in np.linspace(-20, -8, 7):
        box("Foredeck seam", [0, 4.16, z], [max(0.1, width(z) * 1.8), 0.018, 0.025], "white")
    box("Yellow aft hatch", [1.9, 2.48, 20.0], [1.1, 0.04, 0.9], "yellow")
    rod("Emergency cylinder", [2.65, 2.5, 4.35], [2.65, 3.3, 4.35], 0.14, "red", 16)
    box("Emergency locker", [2.7, 3.5, 4.32], [0.36, 0.45, 0.16], "red")


def build_fenders() -> None:
    """Build round hanging tires with raised sidewall detail."""
    for sign in [-1, 1]:
        for z in [20.4, 19.1, 17.8, 9.0, 7.6, 2.1, 0.7, -6.8, -8.2, -12.9, -14.3]:
            y = top(z) - (1.65 if z < 4 else 0.58)
            x = sign * (side(z, y) + 0.14)
            mesh = trimesh.creation.torus(0.43, 0.135, major_sections=24, minor_sections=12)
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
            mesh.apply_translation([x, y, z])
            add("Side tire fender", mesh, "rubber", True)
            rim = trimesh.creation.torus(0.435, 0.025, major_sections=24, minor_sections=6)
            rim.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
            rim.apply_translation([x + sign * 0.12, y, z])
            add("Raised tire sidewall", rim, "rubber_rim", True)
            rod("Tire suspension", [x, y + 0.38, z], [sign * width(z) * 0.96, top(z) + 0.04, z], 0.022, "black", 6)
    for x in [-3.05, -1.9, -0.75, 0.75, 1.9, 3.05]:
        mesh = trimesh.creation.torus(0.42, 0.14, major_sections=24, minor_sections=12)
        mesh.apply_translation([x, 1.92, 22.56])
        add("Transom tire fender", mesh, "rubber", True)
        rim = trimesh.creation.torus(0.425, 0.025, major_sections=24, minor_sections=6)
        rim.apply_translation([x, 1.92, 22.69])
        add("Transom tire sidewall", rim, "rubber_rim", True)
    box("Transom boarding step", [0, 0.55, 22.59], [1.30, 0.22, 0.28], "black")


def main() -> None:
    """Export an auditable visual revision while preserving the supplied source."""
    GROUPS.clear()
    PARTS.clear()
    original = trimesh.load(SOURCE, force="scene", process=False)
    # Preserve original evidence for A/B inspection, without editing the user file.
    debug = ROOT / "tmp/fcb45-visual"
    debug.mkdir(parents=True, exist_ok=True)
    (debug / "normals-only.glb").write_bytes(trimesh.exchange.gltf.export_glb(original, include_normals=True))
    build_hull()
    build_bridge()
    build_deck()
    build_fenders()
    for node in original.graph.nodes_geometry:
        transform, key = original.graph[node]
        mesh = original.geometry[key]
        if key.startswith(("Main_Mast", "Mast_", "Radar_", "Sensor", "Propeller_", "Rudder_")):
            copy = mesh.copy()
            copy.apply_transform(transform)
            mat = (
                "bronze"
                if key.startswith("Propeller")
                else "black"
                if key.startswith(("Rudder", "BowThruster"))
                else "steel"
            )
            add("Retained " + key, copy, mat, True)
    scene = trimesh.Scene()
    for name, meshes in GROUPS.items():
        merged = trimesh.util.concatenate(meshes)
        merged.visual = trimesh.visual.TextureVisuals(material=MATS[name])
        merged.vertex_normals = merged.vertex_normals
        scene.add_geometry(merged, geom_name=name, node_name=name)
    scene.metadata.update(
        {
            "display_only": True,
            "origin": "midship design waterline",
            "forward": "-Z",
            "up": "+Y",
            "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        }
    )
    OUTPUT.write_bytes(trimesh.exchange.gltf.export_glb(scene, include_normals=True))
    report = {
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "triangles": sum(len(m.faces) for m in scene.geometry.values()),
        "materials": len(scene.geometry),
        "parts": PARTS,
        "bounds": scene.bounds.tolist(),
        "method": "reference-driven visual reconstruction, not CAD or hull calibration",
    }
    (OUTPUT.parent / "refinement-v1.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "parts"}, indent=2))


if __name__ == "__main__":
    main()
