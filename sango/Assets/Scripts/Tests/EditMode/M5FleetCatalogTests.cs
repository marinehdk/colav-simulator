using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEditor;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5 采购船队编目缝 EditMode 测试（先例 VesselCatalogTests，只走公开 API 与 prefab 外观）：
    /// 8 档齐全、全渲染器 HDRP/Lit（粉紫=shader 丢失验收钉死）、LOA ±10%、根 yaw = 钉值字面量、
    /// 编目 bowYawDeg 与编辑器查表口（VesselAssetPipeline.BowYawDeg 转查 M5FleetPipeline）一致。
    /// 艏向字面量证据 = M5AssetAudit 4 向端宽实测（docs/research/2026-09-29-m5-fleet-import/m5-audit.md）；
    /// 盒形船体（箱船/油轮/拖轮）端宽近平局的档位在 k_Specs 注释里标 ⚠，GUI 目检翻案时改字面量+本表。
    /// </summary>
    public class M5FleetCatalogTests
    {
        const string k_CatalogPath = "Assets/Art/KenneyWatercraft/VesselCatalog.asset";

        static readonly TestCaseData[] k_FleetExpectations =
        {
            new TestCaseData(VesselClass.FishingTrawler, 25f, 90f).SetName("FishingTrawler (Trawler, LOA 25 m, yaw 90)"),
            new TestCaseData(VesselClass.CargoGeneral, 120f, 90f).SetName("CargoGeneral (cargo_ship, LOA 120 m, yaw 90)"),
            new TestCaseData(VesselClass.CargoContainer, 150f, 90f).SetName("CargoContainer (Ship.fbx, LOA 150 m, yaw 90)"),
            new TestCaseData(VesselClass.Tanker, 300f, 0f).SetName("Tanker (Suez-Max, LOA 300 m, yaw 0)"),
            new TestCaseData(VesselClass.TankerLng, 300f, 0f).SetName("TankerLng (Moss LNG, LOA 300 m, yaw 0)"),
            new TestCaseData(VesselClass.Tug, 32f, 0f).SetName("Tug (RAstar 3200, LOA 32 m, yaw 0)"),
            new TestCaseData(VesselClass.FcbHoubei, 42f, 180f).SetName("FcbHoubei (Type 22 hero, LOA 42 m, yaw 180)"),
            new TestCaseData(VesselClass.FcbPc3, 55f, 180f).SetName("FcbPc3 (Hurricane, LOA 55 m, yaw 180)"),
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
            Assert.That(catalog, Is.Not.Null, $"catalog asset missing at {k_CatalogPath} — run Sango/M5/Build Purchased Fleet");
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

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Catalog_ResolvesPrefab_ForEachFleetClass(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var entry = LoadCatalog().GetEntry(cls);
            Assert.That(entry, Is.Not.Null, $"catalog entry missing for {cls}");
            Assert.That(entry.prefab, Is.Not.Null, $"catalog entry for {cls} has no prefab");
        }

        [Test]
        public void Catalog_FleetPipelineVersion_MatchesPipelineStamp()
        {
            // M5FleetPipeline 在 Assembly-CSharp-Editor（asmdef 不能引用预定义程序集）→ 反射取常量
            int stamp = (int)EditorField("Sango.Editor.M5FleetPipeline", "k_PipelineVersion").GetValue(null);
            Assert.That(LoadCatalog().fleetPipelineVersion, Is.EqualTo(stamp),
                "fleetPipelineVersion 不符——EnsureBuilt 会整跑重建，字面量需与流水线同步");
        }

        [Test]
        public void Catalog_KenneyTierEntries_SurvivedFleetRebuild()
        {
            // M5 流水线重写编目时必须保留 Kenney 三档（VesselAssetPipeline 对称保留 M5 档）
            var catalog = LoadCatalog();
            foreach (VesselClass kenney in new[] { VesselClass.Large, VesselClass.Medium, VesselClass.Small })
            {
                Assert.That(catalog.GetEntry(kenney)?.prefab, Is.Not.Null, $"{kenney} 被 M5 构建抹掉");
            }
            Assert.That(catalog.entries.Length, Is.EqualTo(11), "编目应 3 Kenney + 8 M5 共 11 条");
        }

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Prefab_AllRendererMaterials_AreHdrpLit_NotPink(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(cls);
            int checkedMaterials = 0;
            foreach (var renderer in go.GetComponentsInChildren<Renderer>(true))
            {
                Assert.That(renderer.sharedMaterials, Is.Not.Empty, $"{renderer.name}: no material slots");
                foreach (var material in renderer.sharedMaterials)
                {
                    Assert.That(material, Is.Not.Null, $"{renderer.name}: null material slot");
                    Assert.That(material.shader.name, Is.EqualTo("HDRP/Lit"),
                        $"{renderer.name}/{material.name}: expected HDRP/Lit (pink = lost shader), got {material.shader.name}");
                    checkedMaterials++;
                }
            }
            Assert.That(checkedMaterials, Is.GreaterThanOrEqualTo(1));
        }

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Prefab_WorldLength_Within10Pct_OfTargetLoa(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(cls);
            var renderers = go.GetComponentsInChildren<Renderer>(true);
            var bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);
            float loa = Mathf.Max(bounds.size.x, bounds.size.z);
            Assert.That(loa, Is.InRange(targetLoa * 0.9f, targetLoa * 1.1f),
                $"{cls}: LOA {loa:F1} m outside ±10% of {targetLoa} m（glTF→FBX→Unity 链路缩放修正失效）");
        }

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Prefab_RootRotation_PointsBowToPlusZ(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var go = InstantiatePrefab(cls);
            float angle = Quaternion.Angle(go.transform.rotation, Quaternion.Euler(0f, bowYawDeg, 0f));
            Assert.That(angle, Is.LessThan(0.5f),
                $"{cls}: root yaw {go.transform.eulerAngles.y:F1}° != pinned {bowYawDeg}°");
        }

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Catalog_Entry_CarriesLoa_Waterline_AndBowYawSyncedWithEditorLookup(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var entry = LoadCatalog().GetEntry(cls);
            Assert.That(entry.loaMeters, Is.InRange(targetLoa * 0.9f, targetLoa * 1.1f));
            Assert.That(entry.waterlineOffsetY, Is.LessThan(0f),
                $"{cls}: waterline offset must submerge (negative), got {entry.waterlineOffsetY}");
            Assert.That(entry.bowYawDeg, Is.EqualTo(bowYawDeg).Within(0.01f),
                $"{cls}: catalog bowYawDeg {entry.bowYawDeg} != 测试字面量 {bowYawDeg}");
            // 编辑器查表口（VesselAssetPipeline.BowYawDeg → M5FleetPipeline 转查，均在编辑器程序集）
            // 与编目字段的一致性：PlaceCatalogShip 用前者、AnchorageFleet 用后者，失同步 = 放置层静默镜像船
            var pipelineType = EditorType("Sango.Editor.VesselAssetPipeline");
            float lookup = (float)pipelineType.GetMethod("BowYawDeg").Invoke(null, new object[] { cls });
            Assert.That(lookup, Is.EqualTo(bowYawDeg).Within(0.01f),
                $"{cls}: editor 查表口与字面量失同步");
        }

        // ── 反射小件：被测类型在 Assembly-CSharp-Editor（TestReflection 先例） ─────────

        static System.Type EditorType(string fullName)
        {
            foreach (var asm in System.AppDomain.CurrentDomain.GetAssemblies())
            {
                if (asm.GetName().Name != "Assembly-CSharp-Editor") continue;
                var t = asm.GetType(fullName);
                Assert.That(t, Is.Not.Null, $"Assembly-CSharp-Editor 缺类型 {fullName}");
                return t;
            }
            Assert.Fail("Assembly-CSharp-Editor 程序集未加载");
            return null;
        }

        static System.Reflection.FieldInfo EditorField(string typeName, string fieldName)
        {
            var f = EditorType(typeName).GetField(fieldName, System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
            Assert.That(f, Is.Not.Null, $"{typeName}.{fieldName} 缺字段");
            return f;
        }

        // ── FCB 占位专项（任务项 5）：白壳绿装 + 轮胎护舷 ─────────────────────────────

        [Test]
        public void FcbHoubei_TireFenders_BothSidesPresent_BlackHdrpLit()
        {
            var go = InstantiatePrefab(VesselClass.FcbHoubei);
            var fenders = go.transform.Find("Tire Fenders");
            Assert.That(fenders, Is.Not.Null, "VesselFcbHoubei 缺 Tire Fenders 子物体");
            var renderers = fenders.GetComponentsInChildren<MeshRenderer>();
            Assert.That(renderers.Length, Is.EqualTo(12), "两舷各 6 环 = 12 个轮胎护舷渲染器");
            int leftRight = 0;
            foreach (var r in renderers)
            {
                Assert.That(r.sharedMaterial.shader.name, Is.EqualTo("HDRP/Lit"));
                Assert.That(r.sharedMaterial.name, Does.Contain("TireBlack"));
                var localX = r.transform.localPosition.x * go.transform.localScale.x; // root 烘焙缩放后近似世界 x
                if (!Mathf.Approximately(localX, 0f)) leftRight++;
            }
            Assert.That(leftRight, Is.EqualTo(12), "全部护舷应分列两舷（x ≠ 0）");
            // 两舷对生：x 符号各 6
            int neg = 0, pos = 0;
            foreach (var r in renderers)
            {
                float x = r.transform.localPosition.x;
                if (x < 0f) neg++; else if (x > 0f) pos++;
            }
            Assert.That(neg, Is.EqualTo(6));
            Assert.That(pos, Is.EqualTo(6));
        }

        [Test]
        public void FcbHoubei_Palette_IsWhiteHull_GreenFittings_NoSourceCamouflage()
        {
            var go = InstantiatePrefab(VesselClass.FcbHoubei);
            var palettes = new HashSet<Material>();
            foreach (var renderer in go.GetComponentsInChildren<Renderer>(true))
            {
                if (renderer.transform != null && renderer.name.StartsWith("Tire")) continue;
                foreach (var m in renderer.sharedMaterials) palettes.Add(m);
            }
            palettes.Remove(go.transform.Find("Tire Fenders")?.GetComponentInChildren<MeshRenderer>()?.sharedMaterial);
            // 船体渲染器只允许白/绿两个 flat 材质（原蓝迷彩贴图不入 prefab）
            foreach (var m in palettes)
            {
                bool isWhite = m.name.Contains("HullWhite");
                bool isGreen = m.name.Contains("FittingsGreen");
                Assert.That(isWhite || isGreen, Is.True, $"FCB 占位出现非调色板材质 {m.name}");
            }
            Assert.That(palettes.Count, Is.InRange(1, 2), "白壳/绿装 flat 调色板应为 1-2 个材质");
        }
    }
}
