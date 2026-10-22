using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    /// <summary>P0-C shore-wave decals (plan §2 P0-C): placement-table loading
    /// and the rig/toggle/water-region lifecycle. Pure visuals (foam look,
    /// amplitude constants) are intentionally untested — they are 视觉修整、非实测
    /// pending the remote-player acceptance pass.</summary>
    public class QingdaoShoreFoamTests
    {
        Type Scene => TestReflection.FindAssemblyCSharpType("Sango.QingdaoStaticScene");

        [Test]
        public void BundledPlacementTableLoadsAndCoversItsDecals()
        {
            var asset = Resources.Load<TextAsset>("Qingdao/shorefoam");
            Assert.That(asset, Is.Not.Null, "shorefoam.json must ship in Resources (bake: build_qingdao_static.py)");
            var parse = Scene.GetMethod("ParseShoreFoam");
            var table = parse.Invoke(null, new object[] { asset.text });
            Assert.That(table, Is.Not.Null);
            var decals = (Array)table.GetType().GetField("decals").GetValue(table);
            Assert.That(decals.Length, Is.InRange(1, 3), "plan shrinks placement to 2-3 main-view segments");
            float anchorX = (float)table.GetType().GetField("anchor_x").GetValue(table);
            float anchorZ = (float)table.GetType().GetField("anchor_z").GetValue(table);
            float region = (float)table.GetType().GetField("region_size_m").GetValue(table);
            Assert.That(region, Is.GreaterThan(0));
            foreach (var entry in decals)
            {
                var t = entry.GetType();
                float x = (float)t.GetField("x").GetValue(entry), z = (float)t.GetField("z").GetValue(entry);
                float sx = (float)t.GetField("size_x").GetValue(entry), sz = (float)t.GetField("size_z").GetValue(entry);
                // the decal region must cover every decal rect or none of them renders
                Assert.That(Math.Abs(x - anchorX) + sx / 2f, Is.LessThanOrEqualTo(region / 2f + 0.001f));
                Assert.That(Math.Abs(z - anchorZ) + sz / 2f, Is.LessThanOrEqualTo(region / 2f + 0.001f));
            }
        }

        [Test]
        public void ParseRejectsForeignDocuments()
        {
            var parse = Scene.GetMethod("ParseShoreFoam");
            Assert.That(parse.Invoke(null, new object[] { null }), Is.Null);
            Assert.That(parse.Invoke(null, new object[] { "{\"schema\":\"other\"}" }), Is.Null);
            Assert.That(parse.Invoke(null, new object[] { "{\"schema\":\"qingdao-shorefoam.v1\",\"region_size_m\":0,\"decals\":[]}" }), Is.Null);
        }

        [Test]
        public void DecalsFollowPlacementTableWithRealtimeAtlas()
        {
            var material = Resources.Load<Material>("Qingdao/QingdaoShoreWave");
            Assert.That(material, Is.Not.Null, "QingdaoShoreWave.mat must ship in Resources (registry: HDRP WaterSamples derivative)");
            Assert.That(material.IsKeywordEnabled("_TYPE_SHORE_WAVE"), Is.True, "the _TYPE=3 Shore Wave branch must be selected");
            var table = Scene.GetMethod("ParseShoreFoam").Invoke(null,
                new object[] { "{\"schema\":\"qingdao-shorefoam.v1\",\"anchor_x\":-4,\"anchor_z\":8,\"region_size_m\":512,"
                    + "\"decals\":[{\"x\":-10,\"z\":20,\"yaw_deg\":-90,\"size_x\":64,\"size_z\":152}]}" });
            var parent = new GameObject("shore foam parent");
            try
            {
                var build = Scene.GetMethod("BuildShoreFoamDecals");
                var decals = (WaterDecal[])build.Invoke(null, new object[] { parent.transform, table, material });
                Assert.That(decals.Length, Is.EqualTo(1));
                var decal = decals[0];
                Assert.That(decal.transform.localPosition, Is.EqualTo(new Vector3(-10, 0, 20)));
                var angles = decal.transform.localEulerAngles; // Unity float epsilon: compare per component
                Assert.That(Mathf.Abs(angles.x) < 1e-3f && Mathf.Abs(angles.y - 270f) < 1e-3f && Mathf.Abs(angles.z) < 1e-3f,
                    Is.True, $"yaw -90 stored as {angles}");
                // yaw -90 must map local +X (=wave travel) to scene +Z north = landward
                var travel = decal.transform.TransformDirection(Vector3.right);
                Assert.That(Mathf.Abs(travel.x) < 1e-4f && Mathf.Abs(travel.y) < 1e-4f && Mathf.Abs(travel.z - 1f) < 1e-3f,
                    Is.True, $"wave travel direction was {travel}");
                Assert.That(decal.regionSize, Is.EqualTo(new Vector2(64, 152)));
                Assert.That(decal.scaleMode, Is.EqualTo(DecalScaleMode.ScaleInvariant));
                Assert.That(decal.material, Is.EqualTo(material));
                Assert.That(decal.updateMode, Is.EqualTo(CustomRenderTextureUpdateMode.Realtime),
                    "the Shore Wave branch is Time-driven noise; OnLoad would freeze it (spike notes §6)");
            }
            finally { UnityEngine.Object.DestroyImmediate(parent); }
        }

        [Test]
        public void ToggleAndClearRestoreTheWaterDecalRegion()
        {
            var root = new GameObject("qingdao shore foam lifecycle"); root.SetActive(false);
            var scene = root.AddComponent(Scene);
            var flags = BindingFlags.Instance | BindingFlags.NonPublic;
            var landscape = new GameObject("root");
            var waterGo = new GameObject("water");
            var water = waterGo.AddComponent<WaterSurface>();
            var previousSize = water.decalRegionSize;
            try
            {
                Scene.GetField("m_Root", flags).SetValue(scene, landscape);
                Scene.GetMethod("BuildShoreFoam", flags).Invoke(scene, null);
                var rig = (GameObject)Scene.GetField("m_ShoreFoamRoot", flags).GetValue(scene);
                Assert.That(rig, Is.Not.Null, "bundled table + material must wire the rig");
                Assert.That(rig.activeSelf, Is.True, "default is on");
                // no driver in this scene: the region claim lands on the scene water surface
                Assert.That(water.decalRegionAnchor, Is.EqualTo((Transform)Scene.GetField("m_ShoreFoamAnchor", flags).GetValue(scene)));
                Assert.That(water.decalRegionSize.x, Is.GreaterThan(1000), "region must span the baked cluster, not the 108 m default");

                var toggle = Scene.GetProperty("shoreFoamEnabled", BindingFlags.Instance | BindingFlags.Public);
                toggle.SetValue(scene, false, null);
                Assert.That(rig.activeSelf, Is.False, "toggle off hides the rig");
                Assert.That(water.decalRegionAnchor, Is.Not.Null, "toggle is visual-only; Clear owns the region");
                toggle.SetValue(scene, true, null);
                Assert.That(rig.activeSelf, Is.True);

                Scene.GetField("m_Opened", flags).SetValue(scene, true);
                Scene.GetMethod("Clear").Invoke(scene, null);
                Assert.That(rig.activeSelf, Is.False, "Clear hides the retained rig");
                Assert.That(water.decalRegionAnchor, Is.Null, "Clear restores the pre-attach camera-follow region");
                Assert.That(water.decalRegionSize, Is.EqualTo(previousSize));
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(waterGo);
                UnityEngine.Object.DestroyImmediate(landscape);
                UnityEngine.Object.DestroyImmediate(root);
            }
        }
    }
}
