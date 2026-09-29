#!/usr/bin/env python3
"""Batch-convert purchased fleet GLB (Sketchfab glTF 2.0) to Unity-ready FBX.

M5 asset import batch (2026-09-29). Blender is not installed on this machine as
an app dependency — it is installed once via `brew install --cask blender` and
driven headless:

    /Applications/Blender.app/Contents/MacOS/blender -b --python tools/convert_glb_to_fbx.py -- <glb> [<glb> ...]

Per input `Purchased/<product>/<name>.glb` this writes `Purchased/<product>/source/<name>.fbx`
plus the GLB's embedded textures as sibling PNG/JPG files (FBX export path_mode='COPY',
embed_textures=False — Unity 侧逐材质回接，嵌入会与贴图重导管线打架；见 :88-90 注释).
If no GLB paths are passed, every `sango/Assets/Art/Purchased/**/*.glb`
is converted (idempotent: an existing target FBX is skipped unless --force).

Scale chain note (audit hook): glTF is metres; Blender's glTF importer converts to
Blender's metre scene units; the FBX exporter runs with apply_unit_scale=True and
default '-Z forward, Y up' axes so Unity's ModelImporter applies its usual 0.01→m
handling. The Unity-side audit tool (Sango.Editor.M5AssetAudit) reports imported
bounds vs expected LOA per ship and flags >20% deviation as a finding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import bpy  # Blender-bundled interpreter only
except ImportError:  # pragma: no cover - direct python3 run gives a clear message
    sys.exit("This script must run inside Blender: blender -b --python convert_glb_to_fbx.py -- <args>")


def clear_scene() -> None:
    """Empty the .blend so per-ship exports cannot pick up the previous ship."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def unpack_images(out_dir: Path) -> int:
    """Write glTF-packed textures to out_dir and point image filepaths at them.

    The FBX exporter's path_mode='COPY' only copies images with real filepaths;
    GLB-imported images stay packed in Blender data, so without this step the
    FBX ships textureless (M5 audit 2026-09-29 evidence).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ext_of = {"PNG": "png", "JPEG": "jpg", "JPEG2000": "jp2", "WEBP": "webp", "BMP": "bmp", "TARGA": "tga"}
    used: set[str] = set()
    written = 0
    for img in bpy.data.images:
        if img.packed_file is None:
            continue
        ext = ext_of.get(img.file_format, "png")
        clean = "".join(c if (c.isalnum() or c in "._-") else "_" for c in img.name) or f"texture{written}"
        if not clean.lower().endswith("." + ext):
            clean = f"{clean}.{ext}"
        while clean.lower() in used:
            stem, dot, suffix = clean.rpartition(".")
            clean = f"{stem}_{written}.{suffix}"
        used.add(clean.lower())
        target = out_dir / clean
        target.write_bytes(img.packed_file.data)
        img.filepath = str(target)
        written += 1
    return written


def convert(glb: Path, out_dir: Path, force: bool) -> bool:
    fbx_out = out_dir / f"{glb.stem}.fbx"
    if fbx_out.exists() and not force:
        print(f"[skip] {fbx_out} exists (--force to redo)")
        return True

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(glb))
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not meshes:
        print(f"[FAIL] {glb}: glTF import yielded no mesh objects")
        return False

    unpacked = unpack_images(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_out),
        object_types={"MESH", "ARMATURE"},
        path_mode="COPY",          # copy textures next to the FBX and reference relatively
        embed_textures=False,      # Unity's MaterialDescription does not wire Blender-embedded
                                   # FBX media (M5 audit 2026-09-29: 0 textures wired); external
                                   # files beside the FBX import + wire automatically
        apply_unit_scale=True,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
        bake_space_transform=True, # glTF metres -> FBX units, keeps Unity import at ~1:1
    )
    print(f"[ok]   {glb.name} -> {fbx_out.relative_to(fbx_out.parents[2])} "
          f"({len(meshes)} mesh objects, {unpacked} textures unpacked)")
    return True


def blender_argv() -> list[str]:
    """Args after the `--` separator (Blender 5.2 forwards the whole command line)."""
    argv = sys.argv[1:]
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    return []


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glbs", nargs="*", help="GLB files (default: all under Purchased/)")
    parser.add_argument("--force", action="store_true", help="re-export even if target FBX exists")
    args = parser.parse_args(blender_argv())

    glbs = [Path(p) for p in args.glbs]
    if not glbs:
        glbs = sorted((repo / "sango/Assets/Art/Purchased").rglob("*.glb"))

    if not glbs:
        print("no GLB inputs found")
        return 1

    failures = 0
    for glb in glbs:
        if not convert(glb, glb.parent / "source", args.force):
            failures += 1
    print(f"converted {len(glbs) - failures}/{len(glbs)} models")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
