#!/usr/bin/env python3
"""Build the Qingdao-specific Cesium tileset material (plan P0-B, 2026-10-19).

Clones the Cesium for Unity ``CesiumUnlitTilesetShader`` shader graph (Apache-2.0,
unmodified upstream copy in Library/PackageCache) into
``sango/Assets/Resources/Qingdao/QingdaoTilesetShader.shadergraph`` and extends the
clone with three additive changes while keeping every existing node, edge and
alpha-test wire untouched:

1. a WaterMask overlay channel (materialKey "WaterMask") following the exact
   CesiumRasterOverlay protocol node group already used by the 0/1/2 and Clipping
   channels — the imagery base color is pushed toward a dark, desaturated water
   tone where the binary water mask selects water;
2. Smoothness 0 -> 0.15 (0.60 inside the wet band) on the HD Lit sub-target;
3. a metric procedural detail normal: gradient noise sampled at world XZ /
   7 m periods, converted to a tangent-space normal for NormalTS.

The shared Norwegian material (Assets/Resources/TwinCesiumLandscapeMaterial.mat) is
never touched; the Qingdao landscape consumes the clone via
Resources.Load("Qingdao/QingdaoCesiumLandscapeMaterial"). Visual constants are
first-pass values (视觉修整、非实测) pending the post-deploy same-view A/B pass.
New nodes are cloned whole from local package shader graphs so every serialized
slot keeps Unity's own field set. Run with the project .venv Python; the upstream
packages are read-only input.
"""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SANGO = ROOT / "sango"
OUT_GRAPH = SANGO / "Assets/Resources/Qingdao/QingdaoTilesetShader.shadergraph"
OUT_MAT = SANGO / "Assets/Resources/Qingdao/QingdaoCesiumLandscapeMaterial.mat"
TWIN_MAT = SANGO / "Assets/Resources/TwinCesiumLandscapeMaterial.mat"

SHADERGRAPH_GUID = "8e4b0c37a92d4f16b3d5e7c41a2f9b60"
MATERIAL_GUID = "c61d5f88e0b34a2f9d7c4b1e6a3905d2"

# First-pass visual constants (A/B tuning stays a post-deploy step, plan P0-B).
WATER_TONE_RGBA = (0.055, 0.085, 0.10, 1.0)  # dark, desaturated water tone
WET_BLEND = 0.55                              # imagery lerp toward the tone inside the wet band
SMOOTHNESS_LAND = 0.15                        # plan band 0.1-0.2
SMOOTHNESS_WET = 0.60                         # intertidal wet sheen
DETAIL_PERIOD_M = 7.0                         # metric detail normal feature size
DETAIL_STRENGTH = 0.35


def parse_docs(raw):
    decoder = json.JSONDecoder()
    docs, i = [], 0
    while i < len(raw):
        while i < len(raw) and raw[i] in " \n\r\t":
            i += 1
        if i >= len(raw):
            break
        obj, i = decoder.raw_decode(raw, i)
        docs.append(obj)
    return docs


def dump_docs(docs):
    return "\n\n".join(json.dumps(doc, indent=4) for doc in docs) + "\n"


def load_template_sources():
    """Every new node type is cloned from a local package shader graph (node + its slots)."""
    cache = SANGO / "Library/PackageCache"
    cesium = next(cache.glob("com.cesium.unity*/Source/Runtime/Resources"))
    sources = [
        cesium / "CesiumUnlitTilesetShader.shadergraph",
        cesium / "CesiumDefaultTilesetShader.shadergraph",
        next(cache.glob("com.unity.timeline*/Samples~/GameplaySequenceDemo/Shaders/WorldSpaceGrid_Graph.shadergraph")),
        next(cache.glob("com.unity.render-pipelines.high-definition*/Samples~/WaterSamples/VFX/Shader Graphs/SG_MotionBlur_Tube.shadergraph")),
        next(cache.glob("com.unity.visualeffectgraph*/Samples~/VFXLearningTemplates/Shaders/SG_Vase.shadergraph")),
    ]
    return [parse_docs(path.read_text()) for path in sources]


class Surgery:
    def __init__(self, docs, sources, seed):
        self.docs = docs
        self.graph = docs[0]
        self.sources = sources
        self.by_id = {d["m_ObjectId"]: d for d in docs if isinstance(d.get("m_ObjectId"), str)}
        self.seed = seed
        self._n = 0

    def oid(self, label):
        self._n += 1
        return hashlib.sha1(f"{self.seed}/{label}/{self._n}".encode()).hexdigest()[:32]

    def template(self, node_type_suffix):
        """Find a node doc of a type in any local graph, with its slot docs bundled."""
        for source in self.sources:
            by_id = {d["m_ObjectId"]: d for d in source if isinstance(d.get("m_ObjectId"), str)}
            for doc in source:
                if str(doc.get("m_Type", "")).endswith("." + node_type_suffix):
                    doc = copy.deepcopy(doc)
                    doc["_slots"] = {ref["m_Id"]: by_id[ref["m_Id"]] for ref in doc.get("m_Slots", [])}
                    return doc
        raise KeyError(node_type_suffix)

    def clone_node(self, template, name, group, position, value=None):
        """Clone a whole node doc (with fresh slot docs) from any local graph."""
        doc = copy.deepcopy(template)
        doc.pop("_slots", None)
        doc["m_ObjectId"] = self.oid("node")
        doc["m_Name"] = name
        doc["m_Group"] = {"m_Id": group}
        doc["m_DrawState"] = {
            "m_Expanded": True,
            "m_Position": {"serializedVersion": "2", "x": position[0], "y": position[1],
                           "width": 208.0, "height": 140.0},
        }
        for slot_ref in doc.get("m_Slots", []):
            source_slot = template.get("_slots", {}).get(slot_ref["m_Id"]) or self.by_id[slot_ref["m_Id"]]
            slot = copy.deepcopy(source_slot)
            slot["m_ObjectId"] = self.oid("slot")
            self.docs.append(slot)
            slot_ref["m_Id"] = slot["m_ObjectId"]
        if value is not None and "m_Value" in doc:
            doc["m_Value"] = value
        self.docs.append(doc)
        self.graph["m_Nodes"].append({"m_Id": doc["m_ObjectId"]})
        return doc

    def edge(self, out_node, out_slot, in_node, in_slot):
        self.graph["m_Edges"].append({
            "m_OutputSlot": {"m_Node": {"m_Id": out_node["m_ObjectId"]}, "m_SlotId": out_slot},
            "m_InputSlot": {"m_Node": {"m_Id": in_node["m_ObjectId"]}, "m_SlotId": in_slot},
        })

    def remove_edge(self, out_oid, out_slot, in_oid, in_slot):
        before = len(self.graph["m_Edges"])
        self.graph["m_Edges"] = [
            e for e in self.graph["m_Edges"]
            if not (e["m_OutputSlot"]["m_Node"]["m_Id"] == out_oid
                    and e["m_OutputSlot"]["m_SlotId"] == out_slot
                    and e["m_InputSlot"]["m_Node"]["m_Id"] == in_oid
                    and e["m_InputSlot"]["m_SlotId"] == in_slot)
        ]
        assert len(self.graph["m_Edges"]) == before - 1, "edge to rewire not found"

    def clone_property(self, template_oid, name, guid):
        doc = copy.deepcopy(self.by_id[template_oid])
        doc["m_ObjectId"] = self.oid("prop")
        doc["m_Guid"]["m_GuidSerialized"] = guid
        doc["m_Name"] = name
        doc["m_RefNameGeneratedByDisplayName"] = name
        doc["m_DefaultReferenceName"] = f"_{name}"
        self.docs.append(doc)
        self.graph["m_Properties"].append({"m_Id": doc["m_ObjectId"]})
        return doc

    def clone_property_node(self, template_oid, prop, group, position):
        doc = copy.deepcopy(self.by_id[template_oid])
        doc["m_ObjectId"] = self.oid("node")
        doc["m_Group"] = {"m_Id": group}
        doc["m_Name"] = "Property"
        doc["m_DrawState"] = {"m_Expanded": True, "m_Position": {
            "serializedVersion": "2", "x": position[0], "y": position[1], "width": 210.0, "height": 34.0}}
        doc["m_Property"] = {"m_Id": prop["m_ObjectId"]}
        for slot_ref in doc["m_Slots"]:
            slot = copy.deepcopy(self.by_id[slot_ref["m_Id"]])
            slot["m_ObjectId"] = self.oid("slot")
            slot["m_DisplayName"] = prop["m_Name"]
            self.docs.append(slot)
            slot_ref["m_Id"] = slot["m_ObjectId"]
        self.docs.append(doc)
        self.graph["m_Nodes"].append({"m_Id": doc["m_ObjectId"]})
        return doc


def build():
    cesium = next((SANGO / "Library/PackageCache").glob("com.cesium.unity*/Source/Runtime/Resources"))
    base = parse_docs((cesium / "CesiumUnlitTilesetShader.shadergraph").read_text())
    surgery = Surgery(base, load_template_sources(), seed="qingdao-tileset-material")
    by = surgery.by_id

    def by_prefix(prefix):
        return next(oid for oid in by if oid.startswith(prefix))

    # Anchor docs inside the base graph (ids verified against cesium-unity 1.26.0).
    clipping_sub = by["af3b945543674b91b77b84a6318a4ab7"]
    prop_texture = by["5c7dc79eeebc43aca1165f84dfd98b83"]
    prop_uvindex = by["b7b1c17cdd484ddea80ebf6b9ded354a"]
    prop_transcale = by["6562f5a8ffa74765af992c6eda4725dd"]
    prop_node_texture = by[by_prefix("2eef314a")]
    prop_node_uvindex = by[by_prefix("0586d9e7")]
    prop_node_transcale = by[by_prefix("a5eea1fc")]
    block_basecolor = by[by_prefix("3a08d0a6")]
    block_smoothness = by[by_prefix("15b4aee3")]
    block_normalts = by[by_prefix("6eb3bb84")]
    overlay_chain_end = by[by_prefix("ad4fdb31")]
    multiply_template = by[by_prefix("a16bd5ae")]
    split_template = by[by_prefix("4dd6b8d7")]

    # Fresh group keeps the additions visually separate from upstream protocol groups.
    group = {
        "m_SGVersion": 0,
        "m_Type": "UnityEditor.ShaderGraph.GroupData",
        "m_ObjectId": surgery.oid("group"),
        "m_Title": "Qingdao WaterMask + Microsurface (plan P0-B)",
        "m_Position": {"x": 2050.0, "y": 1250.0},
    }
    surgery.docs.append(group)
    surgery.graph["m_GroupDatas"].append({"m_Id": group["m_ObjectId"]})
    gid = group["m_ObjectId"]

    # --- WaterMask overlay channel: same protocol as the Clipping group -----------------
    wm_texture = surgery.clone_property(prop_texture["m_ObjectId"], "overlayTexture_WaterMask",
                                        "3f8a1d26b7c94e05a1c2d3b4e5f60718")
    wm_uvindex = surgery.clone_property(prop_uvindex["m_ObjectId"], "overlayTextureCoordinateIndex_WaterMask",
                                        "9c2e7b45d1f84a30b6c5e7d8f9a0b1c2")
    wm_transcale = surgery.clone_property(prop_transcale["m_ObjectId"], "overlayTranslationAndScale_WaterMask",
                                          "5b9d3c62e8a147f1b0d9c2e3f4a5b6c7")
    node_wm_texture = surgery.clone_property_node(prop_node_texture["m_ObjectId"], wm_texture, gid, (2100.0, 1320.0))
    node_wm_uvindex = surgery.clone_property_node(prop_node_uvindex["m_ObjectId"], wm_uvindex, gid, (2100.0, 1400.0))
    node_wm_transcale = surgery.clone_property_node(prop_node_transcale["m_ObjectId"], wm_transcale, gid, (2100.0, 1480.0))
    node_wm_sub = surgery.clone_node(clipping_sub, "CesiumRasterOverlay", gid, (2340.0, 1320.0))
    surgery.edge(node_wm_uvindex, -1177420189, node_wm_sub, -1177420189)
    surgery.edge(node_wm_texture, -590019148, node_wm_sub, -590019148)
    surgery.edge(node_wm_transcale, 1843696189, node_wm_sub, 1843696189)

    node_wm_split = surgery.clone_node(split_template, "Split", gid, (2680.0, 1320.0))
    surgery.edge(node_wm_sub, 1, node_wm_split, 0)  # RGBA -> R(1) is the binary water mask

    node_tone = surgery.clone_node(surgery.template("Vector4Node"), "Water tone", gid, (2680.0, 1520.0),
                                   value={"x": WATER_TONE_RGBA[0], "y": WATER_TONE_RGBA[1],
                                          "z": WATER_TONE_RGBA[2], "w": WATER_TONE_RGBA[3]})
    node_blend = surgery.clone_node(surgery.template("Vector1Node"), "Wet blend", gid, (2680.0, 1740.0),
                                    value=WET_BLEND)
    node_wett = surgery.clone_node(multiply_template, "Wet mask x blend", gid, (2870.0, 1560.0))
    surgery.edge(node_wm_split, 1, node_wett, 0)
    surgery.edge(node_blend, 0, node_wett, 1)

    node_lerp = surgery.clone_node(surgery.template("LerpNode"), "Blend imagery toward water tone", gid,
                                   (3140.0, 1320.0))
    surgery.edge(overlay_chain_end, 1, node_lerp, 0)   # A: overlay 0/1/2 chain result (RGBA)
    surgery.edge(node_tone, 0, node_lerp, 1)           # B: water tone
    surgery.edge(node_wett, 2, node_lerp, 2)           # T: wet x blend
    surgery.remove_edge(overlay_chain_end["m_ObjectId"], 1, block_basecolor["m_ObjectId"], 0)
    surgery.edge(node_lerp, 3, block_basecolor, 0)

    # --- Smoothness: 0 -> 0.15 land, 0.60 wet band ---------------------------------------
    node_sm_lo = surgery.clone_node(surgery.template("Vector1Node"), "Smoothness land", gid, (3140.0, 1620.0),
                                    value=SMOOTHNESS_LAND)
    node_sm_hi = surgery.clone_node(surgery.template("Vector1Node"), "Smoothness wet", gid, (3140.0, 1740.0),
                                    value=SMOOTHNESS_WET)
    node_sm_lerp = surgery.clone_node(surgery.template("LerpNode"), "Wet sheen", gid, (3360.0, 1620.0))
    surgery.edge(node_sm_lo, 0, node_sm_lerp, 0)
    surgery.edge(node_sm_hi, 0, node_sm_lerp, 1)
    surgery.edge(node_wm_split, 1, node_sm_lerp, 2)
    surgery.edge(node_sm_lerp, 3, block_smoothness, 0)

    # --- Metric procedural detail normal (world XZ / period, Normal From Height) ---------
    node_pos = surgery.clone_node(surgery.template("PositionNode"), "Position (world)", gid, (2100.0, 1900.0))
    inv = 1.0 / DETAIL_PERIOD_M
    node_pscale = surgery.clone_node(surgery.template("Vector3Node"), "Metric UV scale", gid, (2100.0, 2020.0),
                                     value={"x": inv, "y": inv, "z": inv})
    node_uvmul = surgery.clone_node(multiply_template, "World XZ / period", gid, (2340.0, 1900.0))
    surgery.edge(node_pos, 0, node_uvmul, 0)
    surgery.edge(node_pscale, 0, node_uvmul, 1)

    node_noise = surgery.clone_node(surgery.template("GradientNoiseNode"), "Gradient Noise (metric)", gid,
                                    (2600.0, 1900.0))
    node_nstr = surgery.clone_node(surgery.template("Vector1Node"), "Detail strength", gid, (2600.0, 2060.0),
                                   value=DETAIL_STRENGTH)
    node_nfh = surgery.clone_node(surgery.template("NormalFromHeightNode"), "Detail normal", gid, (2830.0, 1900.0))
    surgery.edge(node_uvmul, 2, node_noise, 0)   # v3 out truncated to the UV (xy) input
    surgery.edge(node_noise, 2, node_nfh, 0)     # height
    surgery.edge(node_nstr, 0, node_nfh, 2)      # strength
    surgery.edge(node_nfh, 1, block_normalts, 0) # tangent-space normal

    return surgery


def verify(surgery):
    ids = {d["m_ObjectId"] for d in surgery.docs if isinstance(d.get("m_ObjectId"), str)}
    nodes = {n["m_Id"] for n in surgery.graph["m_Nodes"]}
    assert nodes <= ids, "dangling node reference"
    for e in surgery.graph["m_Edges"]:
        assert e["m_OutputSlot"]["m_Node"]["m_Id"] in nodes, "edge from unknown node"
        assert e["m_InputSlot"]["m_Node"]["m_Id"] in nodes, "edge to unknown node"
    for name in ("overlayTexture_WaterMask", "overlayTextureCoordinateIndex_WaterMask",
                 "overlayTranslationAndScale_WaterMask"):
        assert any(d.get("m_Name") == name for d in surgery.docs), f"missing property {name}"
    # 49 nodes + 18 additions; 40 edges + 20 new - 1 rewired; 17 properties + 3.
    assert len(surgery.graph["m_Nodes"]) == 67, len(surgery.graph["m_Nodes"])
    assert len(surgery.graph["m_Edges"]) == 59, len(surgery.graph["m_Edges"])
    assert len(surgery.graph["m_Properties"]) == 20, len(surgery.graph["m_Properties"])


def build_material():
    text = TWIN_MAT.read_text()
    text = text.replace("m_Name: TwinCesiumLandscapeMaterial", "m_Name: QingdaoCesiumLandscapeMaterial")
    text = text.replace("guid: 6902218a8ff66b74bb629eda5698e039", f"guid: {SHADERGRAPH_GUID}")
    texture_block = """    - _overlayTexture_Clipping:
        m_Texture: {fileID: 0}
        m_Scale: {x: 1, y: 1}
        m_Offset: {x: 0, y: 0}
"""
    water_block = texture_block.replace("_overlayTexture_Clipping", "_overlayTexture_WaterMask")
    assert texture_block in text
    text = text.replace(texture_block, texture_block + water_block)
    text = text.replace(
        "    - _overlayTextureCoordinateIndex_Clipping: 0\n",
        "    - _overlayTextureCoordinateIndex_Clipping: 0\n"
        "    - _overlayTextureCoordinateIndex_WaterMask: 0\n",
    )
    text = text.replace(
        "    - _overlayTranslationAndScale_Clipping: {r: 0, g: 0, b: 1, a: 1}\n",
        "    - _overlayTranslationAndScale_Clipping: {r: 0, g: 0, b: 1, a: 1}\n"
        "    - _overlayTranslationAndScale_WaterMask: {r: 0, g: 0, b: 1, a: 1}\n",
    )
    assert text.count("_overlayTexture_WaterMask") == 1
    return text


def main():
    surgery = build()
    verify(surgery)
    OUT_GRAPH.write_text(dump_docs(surgery.docs))
    (OUT_GRAPH.parent / (OUT_GRAPH.name + ".meta")).write_text(
        "fileFormatVersion: 2\n"
        f"guid: {SHADERGRAPH_GUID}\n"
        "ScriptedImporter:\n"
        "  internalIDToNameTable: []\n"
        "  externalObjects: {}\n"
        "  serializedVersion: 2\n"
        "  userData: \n"
        "  assetBundleName: \n"
        "  assetBundleVariant: \n"
        "  script: {fileID: 11500000, guid: 625f186215c104763be7675aa2d941aa, type: 3}\n"
    )
    OUT_MAT.write_text(build_material())
    (OUT_MAT.parent / (OUT_MAT.name + ".meta")).write_text(
        "fileFormatVersion: 2\n"
        f"guid: {MATERIAL_GUID}\n"
        "NativeFormatImporter:\n"
        "  externalObjects: {}\n"
        "  mainObjectFileID: 2100000\n"
        "  userData: \n"
        "  assetBundleName: \n"
        "  assetBundleVariant: \n"
    )
    print(f"Qingdao tileset material written: {OUT_MAT.name} + {OUT_GRAPH.name} "
          f"({len(surgery.graph['m_Nodes'])} nodes, {len(surgery.graph['m_Edges'])} edges, "
          f"{len(surgery.graph['m_Properties'])} properties)")


if __name__ == "__main__":
    main()
