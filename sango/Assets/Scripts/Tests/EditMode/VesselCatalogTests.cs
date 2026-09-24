using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEditor;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M2-A 编目缝 EditMode 测试（spec #80 Testing Decisions）：只走 VesselCatalog 公开 API 与
    /// prefab 外观属性（渲染器/材质/世界尺寸/根朝向），不测流水线内部。期望值全部是独立事实：
    /// LOA 目标与艏向字面量来自 spec + kit 预览图/OBJ 顶点分析（docs/research/…/evidence/m2a-build-log.md）。
    /// </summary>
    public class VesselCatalogTests
    {
        const string k_CatalogPath = "Assets/Art/KenneyWatercraft/VesselCatalog.asset";
        const string k_ColormapPath = "Assets/Art/KenneyWatercraft/Models/Textures/colormap.png";

        // 艏向字面量（艏 → +Z 所需的根 yaw）：ship-large 原生艏 +Z → 0°；
        // ship-ocean-liner 原生艏 -Z（龙骨点在 -Z 端、+Z 端船底上收=巡洋舰艉）→ 180°；
        // boat-fishing-small 原生艏 +Z（龙骨在 +Z 端收成尖点、艏驾驶台）→ 0°。
        static readonly TestCaseData[] k_ClassExpectations =
        {
            new TestCaseData(VesselClass.Large, 100f, 0f).SetName("Large (ship-large, LOA 100 m, yaw 0)"),
            new TestCaseData(VesselClass.Medium, 60f, 180f).SetName("Medium (ship-ocean-liner, LOA 60 m, yaw 180)"),
            new TestCaseData(VesselClass.Small, 12f, 0f).SetName("Small (boat-fishing-small, LOA 12 m, yaw 0)"),
        };

        readonly List<Object> m_Spawned = new List<Object>();

        [TearDown]
        public void TearDown()
        {
            foreach (var o in m_Spawned)
            {
                if (o != null) Object.DestroyImmediate(o);
            }
            m_Spawned.Clear();
        }

        VesselCatalog LoadCatalog()
        {
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(k_CatalogPath);
            Assert.That(catalog, Is.Not.Null, $"catalog asset missing at {k_CatalogPath} — run Sango/M2/Build Vessel Assets");
            return catalog;
        }

        GameObject InstantiatePrefab(VesselClass vesselClass)
        {
            var prefab = LoadCatalog().GetPrefab(vesselClass);
            Assert.That(prefab, Is.Not.Null, $"no prefab registered for {vesselClass}");
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
            Assert.That(go, Is.Not.Null, $"failed to instantiate prefab for {vesselClass}");
            m_Spawned.Add(go);
            return go;
        }

        static Bounds EncapsulatingRendererBounds(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>(true);
            Assert.That(renderers.Length, Is.GreaterThanOrEqualTo(1), "prefab has no renderer");
            var bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);
            return bounds;
        }

        [Test, TestCaseSource(nameof(k_ClassExpectations))]
        public void Catalog_ResolvesPrefab_ForEachClass(VesselClass vesselClass, float targetLoa, float bowYawDeg)
        {
            var entry = LoadCatalog().GetEntry(vesselClass);
            Assert.That(entry, Is.Not.Null, $"catalog entry missing for {vesselClass}");
            Assert.That(entry.prefab, Is.Not.Null, $"catalog entry for {vesselClass} has no prefab");
        }

        [Test, TestCaseSource(nameof(k_ClassExpectations))]
        public void Prefab_HasAtLeastOneRenderer_ForEachClass(VesselClass vesselClass, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(vesselClass);
            Assert.That(go.GetComponentsInChildren<Renderer>(true).Length, Is.GreaterThanOrEqualTo(1));
        }

        [Test, TestCaseSource(nameof(k_ClassExpectations))]
        public void Prefab_AllRendererMaterials_AreHdrpLit_WithColormapBaseMap(VesselClass vesselClass, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(vesselClass);
            var colormap = AssetDatabase.LoadAssetAtPath<Texture2D>(k_ColormapPath);
            Assert.That(colormap, Is.Not.Null, $"colormap missing at {k_ColormapPath}");

            var checkedMaterials = 0;
            foreach (var renderer in go.GetComponentsInChildren<Renderer>(true))
            {
                Assert.That(renderer.sharedMaterials, Is.Not.Empty, $"{renderer.name}: no material slots");
                foreach (var material in renderer.sharedMaterials)
                {
                    Assert.That(material, Is.Not.Null, $"{renderer.name}: null material slot");
                    Assert.That(material.shader.name, Is.EqualTo("HDRP/Lit"),
                        $"{renderer.name}/{material.name}: expected HDRP/Lit, got {material.shader.name}");
                    Assert.That(AssetDatabase.GetAssetPath(material.GetTexture("_BaseColorMap")),
                        Is.EqualTo(k_ColormapPath),
                        $"{renderer.name}/{material.name}: base map is not the kit colormap");
                    checkedMaterials++;
                }
            }
            Assert.That(checkedMaterials, Is.GreaterThanOrEqualTo(1));
        }

        [Test, TestCaseSource(nameof(k_ClassExpectations))]
        public void Prefab_WorldLength_Within10Pct_OfTargetLoa(VesselClass vesselClass, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(vesselClass);
            var bounds = EncapsulatingRendererBounds(go);
            float loa = Mathf.Max(bounds.size.x, bounds.size.z);
            Assert.That(loa, Is.InRange(targetLoa * 0.9f, targetLoa * 1.1f),
                $"{vesselClass}: LOA {loa:F1} m outside ±10% of {targetLoa} m");
        }

        [Test, TestCaseSource(nameof(k_ClassExpectations))]
        public void Prefab_RootRotation_PointsBowToPlusZ(VesselClass vesselClass, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(vesselClass);
            float angle = Quaternion.Angle(go.transform.rotation, Quaternion.Euler(0f, bowYawDeg, 0f));
            Assert.That(angle, Is.LessThan(0.5f),
                $"{vesselClass}: root yaw {go.transform.eulerAngles.y:F1}° != pinned {bowYawDeg}°");
        }

        [Test, TestCaseSource(nameof(k_ClassExpectations))]
        public void Catalog_Entry_CarriesMeasuredLoa_AndNegativeWaterlineOffset(VesselClass vesselClass, float targetLoa, float bowYawDeg)
        {
            var entry = LoadCatalog().GetEntry(vesselClass);
            Assert.That(entry.loaMeters, Is.InRange(targetLoa * 0.9f, targetLoa * 1.1f),
                $"{vesselClass}: catalog LOA {entry.loaMeters} outside ±10% of {targetLoa}");
            Assert.That(entry.waterlineOffsetY, Is.LessThan(0f),
                $"{vesselClass}: waterline offset must submerge (negative), got {entry.waterlineOffsetY}");
        }
    }
}
