"""Assemble + render the Qianwan satellite-draped scene (Blender 5.2 headless).

Run: /Applications/Blender.app/Contents/MacOS/Blender -b -P build_blend_scene.py
Inputs (same dir): scene_data.npz, qianwan_mosaic.png, quays/revets/shore_areas
.obj, placement.json. Output: qianwan_terrain.blend + renders/*.png.
"""
import json
import math
from pathlib import Path

import bpy
import numpy as np

D = Path(__file__).resolve().parent
SCENE_FILE = "qianwan_terrain"

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

# ---- scene defaults ----------------------------------------------------------
bpy.context.scene.render.engine = "CYCLES"
try:
    bpy.context.scene.cycles.device = "GPU"
except Exception:
    bpy.context.scene.cycles.device = "CPU"
bpy.context.scene.cycles.samples = 96
bpy.context.scene.render.resolution_x = 1600
bpy.context.scene.render.resolution_y = 900
world = bpy.data.worlds["World"]
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.55, 0.7, 0.9, 1.0)
bg.inputs[1].default_value = 1.0


def principled(name, color, rough=0.85, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    return mat


# ---- satellite material ------------------------------------------------------
sat_img = bpy.data.images.load(str(D / "qianwan_mosaic.png"))
sat_mat = bpy.data.materials.new("Satellite")
sat_mat.use_nodes = True
nodes, links = sat_mat.node_tree.nodes, sat_mat.node_tree.links
bsdf = nodes["Principled BSDF"]
tex = nodes.new("ShaderNodeTexImage")
tex.image = sat_img
tex.interpolation = "Smart"
links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.95
bsdf.inputs["Metallic"].default_value = 0.0

# ---- terrain mesh from npz ---------------------------------------------------
npz = np.load(D / "scene_data.npz")
h, xs, ys, uv = npz["height"], npz["x"], npz["y"], npz["uv"]
n = len(xs)
verts, uvs_ = [], []
for i in range(n):
    for j in range(n):
        verts.append((xs[j], ys[i], float(h[i, j]) - 0.4))  # bury 0.4 m vs water
        uvs_.append((float(uv[i, j, 0]), float(uv[i, j, 1])))
faces = []
for i in range(n - 1):
    for j in range(n - 1):
        a = i * n + j
        faces.append((a, a + 1, a + n + 1, a + n))
mesh = bpy.data.meshes.new("Terrain")
mesh.from_pydata(verts, [], faces)
mesh.validate()
uvl = mesh.uv_layers.new()
for li, loop in enumerate(mesh.loops):
    uvl.data[li].uv = uvs_[loop.vertex_index]
ob = bpy.data.objects.new("Terrain", mesh)
bpy.context.collection.objects.link(ob)
ob.data.materials.append(sat_mat)
mod = ob.modifiers.new("sub", "SUBSURF")
mod.levels = 0
mod.render_levels = 1  # smooth the 70 m grid at render time
for poly in mesh.polygons:
    poly.use_smooth = True

# ---- SLCONS volumes (quays / revetments / digitised areas) -------------------
for name in ("quays", "revets", "shore_areas"):
    p = D / f"{name}.obj"
    if not p.exists():
        continue
    bpy.ops.wm.obj_import(filepath=str(p))
    for ob in bpy.context.selected_objects:
        ob.data.materials.clear()
        ob.data.materials.append(sat_mat)

# ---- water -------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=24000, location=(0, 0, 0.0))
water = bpy.context.active_object
water.name = "Water"
water.data.materials.append(
    principled("WaterMat", (0.016, 0.075, 0.12), rough=0.18, metal=0.05)
)

# ---- berth rig (cranes / bollards / fenders / containers) --------------------
pl = json.loads((D / "placement.json").read_text())
p0, p1 = np.array(pl["p0"]), np.array(pl["p1"])
mid = (p0 + p1) / 2
d = (p1 - p0) / pl["length"]
ang = math.atan2(d[1], d[0])  # spike +X -> berth direction
rig = bpy.data.objects.new("BerthRig", None)
rig.empty_display_size = 40
rig.location = (float(mid[0]), float(mid[1]), 0)
rig.rotation_euler = (0, 0, ang)
bpy.context.collection.objects.link(rig)

DECK = 6.0
steel_red = principled("CraneRed", (0.62, 0.07, 0.05), rough=0.5)
steel_dark = principled("SteelDark", (0.13, 0.13, 0.15), rough=0.6, metal=0.3)
rubber = principled("Rubber", (0.04, 0.04, 0.04), rough=0.95)
concrete = principled("Concrete", (0.5, 0.5, 0.48), rough=0.95)
box_mats = {
    "red": principled("BoxR", (0.45, 0.2, 0.1), rough=0.8),
    "blue": principled("BoxB", (0.15, 0.3, 0.5), rough=0.8),
    "green": principled("BoxG", (0.2, 0.4, 0.25), rough=0.8),
    "orange": principled("BoxO", (0.8, 0.4, 0.1), rough=0.8),
    "gray": principled("BoxX", (0.55, 0.55, 0.55), rough=0.8),
}


def box(name, loc, scale, mat, parent=rig):
    bpy.ops.mesh.primitive_cube_add(location=loc, scale=scale)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    ob.parent = parent
    ob.matrix_parent_inverse = rig.matrix_world.inverted()
    return ob


# rails + bollards + fenders along the middle 500 m of the face (water = +Y)
for y_off in (8.0, -8.0):
    box(f"Rail{y_off:+.0f}", (0, y_off, DECK + 0.15), (250, 0.35, 0.15), steel_dark)
for k, x in enumerate(range(-210, 211, 84)):
    box(f"Bollard{k}", (x, 8.5, DECK + 0.7), (0.4, 0.4, 1.4), steel_dark)
for k, x in enumerate(range(-210, 211, 60)):
    box(f"Fender{k}", (x, 10.6, DECK - 2.5), (2.0, 0.4, 1.1), rubber)


def crane(name, cx):
    legs = [(cx - 20, 8), (cx + 20, 8), (cx - 20, -8), (cx + 20, -8)]
    for i, (lx, ly) in enumerate(legs):
        box(f"{name}Leg{i}", (lx, ly, DECK + 19), (1, 1, 19), steel_red)
    for lx in (cx - 20, cx + 20):
        box(f"{name}Beam", (lx, 0, DECK + 38.5), (1.25, 9, 1.25), steel_red)
    box(f"{name}Mast", (cx, -4, DECK + 51), (1, 1, 13), steel_red)
    box(f"{name}Boom", (cx, 0, DECK + 46), (1.5, 55, 1.5), steel_red)
    box(f"{name}Trolley", (cx, 30, DECK + 43), (2.5, 2, 1.5), steel_dark)
    box(f"{name}Spreader", (cx, 30, DECK + 34), (6, 0.25, 0.25), steel_dark)
    box(f"{name}House", (cx, -16, DECK + 41), (5, 4, 2.5), concrete)


crane("CraneA", -140)
crane("CraneB", 140)
colors = ["red", "blue", "green", "orange", "gray"]
for k, x in enumerate(range(-240, -80, 32)):
    box(f"Container{k}", (x, -26, DECK + 1.3), (6.1, 1.22, 1.3), box_mats[colors[k % 5]])

# ---- lights + cameras --------------------------------------------------------
bpy.ops.object.light_add(type="SUN", location=(4000, -6000, 5000))
sun = bpy.context.active_object
sun.data.energy = 3.2
sun.rotation_euler = (math.radians(55), math.radians(-15), math.radians(200))

water_dir = np.array([-d[1], d[0]])  # left of p0->p1 = water side


def cam(name, off, look):
    bpy.ops.object.camera_add(location=tuple(off))
    c = bpy.context.active_object
    c.name = name
    c.data.lens = 50
    c.data.clip_start = 1.0
    c.data.clip_end = 40000.0
    direction = look - np.array(off)
    c.rotation_euler = ((direction / np.linalg.norm(direction)).flatten()).tolist() and \
        tuple(__import__("mathutils").Vector(direction / np.linalg.norm(direction)).to_track_quat("-Z", "Y").to_euler())
    return c


midx, midy = float(mid[0]), float(mid[1])
aerial = cam("AerialCam", (midx - water_dir[0] * 2600 + 1200, midy - water_dir[1] * 2600 - 2200, 1500),
             np.array([midx, midy, 6.0]))
port = cam("PortCam", (midx + water_dir[0] * 700 - 300, midy + water_dir[1] * 700 - 500, 140),
           np.array([midx - 60, midy + 60, 30.0]))
bpy.context.scene.camera = aerial

renders = D / "renders"
renders.mkdir(exist_ok=True)
bpy.context.scene.camera = aerial
bpy.context.scene.render.filepath = str(renders / "aerial.png")
bpy.ops.render.render(write_still=True)
bpy.context.scene.camera = port
bpy.context.scene.render.filepath = str(renders / "port.png")
bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=str(D / f"{SCENE_FILE}.blend"))
print("RENDERS DONE")
