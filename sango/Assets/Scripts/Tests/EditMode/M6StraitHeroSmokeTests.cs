using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M6 海峡场景 hero 接线 smoke-open（EditMode，先例 M5FleetCatalogTests 外观断言风格）：
    /// 打开已烘焙的 Assets/Scenes/M6-Strait.unity（缺失即失败，提示先跑 Sango/M6/Build Strait
    /// Scene），断言——
    /// a) hero prefab 源 = 编目 Fcb45 条目（真主角交付，2026-09-30 换装；占位 FcbHoubei 退守 M1）；
    /// b) 接线全家桶齐：VesselBuoyancy/WaypointFollower/NavigationLights/BoatWaterDecals/
    ///    WakeFoamRig/HullWaterlineDecals/VectorArrows；
    /// c) hull 包围盒 LOA ∈ [43,47] m、beam ∈ [7,9] m（交付 45×8 m ± 容差）；
    /// d) 泊位 = k_HeroBerth (-1500,-5000)（xz ±1 m；y = 编目水线偏移 ±0.1 m）。
    /// TearDown 开空场景：不把 29 块地形/水面对象留给后续测试。
    /// </summary>
    public class M6StraitHeroSmokeTests
    {
        const string k_ScenePath = "Assets/Scenes/M6-Strait.unity";
        const string k_CatalogPath = "Assets/Art/KenneyWatercraft/VesselCatalog.asset";
        static readonly Vector2 k_HeroBerth = new Vector2(-1500f, -5000f);

        [TearDown]
        public void TearDown()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        }

        [Test]
        public void M6Scene_Hero_IsFcb45_WithFullWiring_AndSaneHullBounds()
        {
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(k_CatalogPath);
            Assert.That(catalog, Is.Not.Null, $"catalog asset missing at {k_CatalogPath}");

            var scene = EditorSceneManager.OpenScene(k_ScenePath, OpenSceneMode.Single);
            Assert.That(scene.IsValid, Is.True, $"场景打开失败：{k_ScenePath} —— 先跑 Sango/M6/Build Strait Scene");

            var shipsRoot = GameObject.Find("Ships");
            Assert.That(shipsRoot, Is.Not.Null, "场景缺 Ships 根——不是 M6 构建产物或被手改");
            var hero = shipsRoot.transform.Find("VesselFcb45")?.gameObject;
            Assert.That(hero, Is.Not.Null, "Ships 下无 VesselFcb45 实例——hero 换装未烘焙进场景");

            var prefabSource = PrefabUtility.GetCorrespondingObjectFromSource(hero);
            Assert.That(prefabSource, Is.EqualTo(catalog.GetPrefab(VesselClass.Fcb45)),
                "hero 的 prefab 源 ≠ 编目 Fcb45 条目——放置层类目失同步");

            // 接线全家桶（M6StraitSceneBootstrapper e 段逐项；按类型名断言——本 asmdef 只引
            // Sango.Vessels，Assembly-CSharp 侧组件（VesselBuoyancy 等）无法编译期引用）
            var wired = new HashSet<string>();
            foreach (var component in hero.GetComponents<Component>()) wired.Add(component.GetType().Name);
            foreach (var expected in new[]
                     {
                         "VesselBuoyancy", "WaypointFollower", "NavigationLights",
                         "BoatWaterDecals", "WakeFoamRig", "HullWaterlineDecals", "VectorArrows",
                     })
            {
                Assert.That(wired, Does.Contain(expected), $"hero 缺 {expected} 接线");
            }

            // hull 包围盒（hero 本地系：世界系 AABB 会被 134° 艏向压短成 ~38 m，编目 LOA 口径
            // 是恒等姿态）。逐 MeshFilter sharedMesh 局部 AABB 8 角点 → hero 局部系并集
            // （渲染器相对 hero 根近平恒等，bakeAxisConversion 烘顶点；粒子/拖尾无 mesh 跳过）。
            // LOA 45（43–47），beam 8.69 含护舷（7–9）。
            Vector3 min = new Vector3(float.MaxValue, float.MaxValue, float.MaxValue);
            Vector3 max = new Vector3(float.MinValue, float.MinValue, float.MinValue);
            int meshCount = 0;
            foreach (var filter in hero.GetComponentsInChildren<MeshFilter>(true))
            {
                var mesh = filter.sharedMesh;
                if (mesh == null) continue;
                var toHeroLocal = hero.transform.worldToLocalMatrix * filter.transform.localToWorldMatrix;
                var b = mesh.bounds;
                for (int cx = 0; cx < 2; cx++)
                for (int cy = 0; cy < 2; cy++)
                for (int cz = 0; cz < 2; cz++)
                {
                    var corner = toHeroLocal.MultiplyPoint3x4(new Vector3(
                        (cx == 0) ? b.min.x : b.max.x,
                        (cy == 0) ? b.min.y : b.max.y,
                        (cz == 0) ? b.min.z : b.max.z));
                    min = Vector3.Min(min, corner);
                    max = Vector3.Max(max, corner);
                }
                meshCount++;
            }
            Assert.That(meshCount, Is.GreaterThanOrEqualTo(1), "hero 无网格");
            var size = max - min;
            float loa = Mathf.Max(size.x, size.z);
            float beam = Mathf.Min(size.x, size.z);
            Assert.That(loa, Is.InRange(43f, 47f), $"hero LOA {loa:F1} m 出 43–47 m 窗");
            Assert.That(beam, Is.InRange(7f, 9f), $"hero beam {beam:F1} m 出 7–9 m 窗");

            // 泊位与水线（放置层落位；y 基线 = 编目 waterlineOffsetY）
            var entry = catalog.GetEntry(VesselClass.Fcb45);
            Assert.That(entry, Is.Not.Null, "编目缺 Fcb45 条目");
            Assert.That(hero.transform.position.x, Is.EqualTo(k_HeroBerth.x).Within(1f), "hero 泊位 x ≠ k_HeroBerth");
            Assert.That(hero.transform.position.z, Is.EqualTo(k_HeroBerth.y).Within(1f), "hero 泊位 z ≠ k_HeroBerth");
            Assert.That(hero.transform.position.y, Is.EqualTo(entry.waterlineOffsetY).Within(0.1f),
                "hero 根 y ≠ 编目水线偏移");
        }
    }
}
