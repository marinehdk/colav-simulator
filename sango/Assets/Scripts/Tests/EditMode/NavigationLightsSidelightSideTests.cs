using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEditor;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// L1 舷灯侧别一锤定音（M7-B acceptance 移交项，2026-09-29）：fresh placement
    /// FcbHoubei × heading ∈ {0°, 134°, 270°} 后，NavigationLightsCore.DeriveAnchors 四锚点
    /// 经实例变换到世界系，断言 port 灯在世界右舷半平面负侧、starboard 灯在正侧
    /// ((portPos−shipCenter)·starboardDir &lt; 0、(stbdPos−shipCenter)·starboardDir &gt; 0)。
    /// 赋位与 M1SceneBootstrapper.PlaceCatalogShip 逐语句同款（M5FleetPlacementPoseTests idiom：
    /// instantiate → position=(xz, waterlineOffsetY) → rotation=Euler(0,heading,0)·Euler(0,bowYawDeg,0)）；
    /// hull 根局部包围盒收集法同 NavigationLights.BuildRig。starboardDir = 渲染艏绕 +Y 顺时针
    /// 90°（艏 = rotation·原生艏向量，PlaceCatalogShip 放置自证映射；Unity 正 yaw 顺时针）。
    /// 测试挂 = 真实反侧 bug（上报裁决，不修色别约定）；过 = 夜拍"红在右舷"为艉后视角读色误判。
    /// census loa/port 数为网格根局部原生单位（×根缩放 = 世界米），日志口径已在
    /// NavigationLights.BuildRig 行内标注（M7 review 修复）。
    /// </summary>
    public class NavigationLightsSidelightSideTests
    {
        const string k_CatalogPath = "Assets/Art/KenneyWatercraft/VesselCatalog.asset";

        static readonly float[] k_Headings = { 0f, 134f, 270f }; // 0=北基线 / 134=M6 hero 泊位艏向 / 270=西

        readonly List<Object> m_Spawned = new List<Object>();

        [TearDown]
        public void TearDown()
        {
            foreach (var o in m_Spawned)
                if (o != null) Object.DestroyImmediate(o);
            m_Spawned.Clear();
        }

        [Test, TestCaseSource(nameof(k_Headings))]
        public void PlacedFcbHoubei_PortLightWorldPos_OnPortHalfPlane(float headingDeg)
        {
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(k_CatalogPath);
            Assert.That(catalog, Is.Not.Null, $"catalog asset missing at {k_CatalogPath} — run Sango/M5/Build Purchased Fleet");
            var entry = catalog.GetEntry(VesselClass.FcbHoubei);
            Assert.That(entry, Is.Not.Null, "catalog entry missing for FcbHoubei");

            // fresh placement（PlaceCatalogShip 逐语句同款赋位；hero 泊位原位 (-1500,-5000)）
            var go = (GameObject)PrefabUtility.InstantiatePrefab(entry.prefab);
            Assert.That(go, Is.Not.Null, "failed to instantiate FcbHoubei prefab");
            m_Spawned.Add(go);
            go.transform.position = new Vector3(-1500f, entry.waterlineOffsetY, -5000f);
            go.transform.rotation = Quaternion.Euler(0f, headingDeg, 0f) * Quaternion.Euler(0f, entry.bowYawDeg, 0f);

            // 放置自证：渲染艏（世界）= rotation·原生艏向量 = heading 方向（组合烘焙艏向契约）
            var nativeBow = new Vector3(-Mathf.Sin(entry.bowYawDeg * Mathf.Deg2Rad), 0f, Mathf.Cos(entry.bowYawDeg * Mathf.Deg2Rad));
            var bow = go.transform.rotation * nativeBow;
            var headingDir = new Vector3(Mathf.Sin(headingDeg * Mathf.Deg2Rad), 0f, Mathf.Cos(headingDeg * Mathf.Deg2Rad));
            Assert.That(Vector3.Dot(bow, headingDir), Is.GreaterThan(0.999f),
                $"heading {headingDeg}°：渲染艏须沿艏向（组合烘焙艏向自证，反了则本测试前提不成立）");
            var starboardDir = Quaternion.Euler(0f, 90f, 0f) * bow; // 艏向右旋 90° = 右舷单位向量

            // hull 根局部包围盒（NavigationLights.BuildRig 同款：MeshFilter 局部 → 根局部）
            var rootInverse = go.transform.worldToLocalMatrix;
            var bounds = new Bounds();
            bool any = false;
            foreach (var filter in go.GetComponentsInChildren<MeshFilter>(false))
            {
                var mesh = filter.sharedMesh;
                if (mesh == null) continue;
                var filterToRoot = rootInverse * filter.transform.localToWorldMatrix;
                var b = mesh.bounds;
                for (int xi = 0; xi < 2; xi++)
                for (int yi = 0; yi < 2; yi++)
                for (int zi = 0; zi < 2; zi++)
                {
                    var corner = filterToRoot.MultiplyPoint3x4(new Vector3(
                        xi == 0 ? b.min.x : b.max.x,
                        yi == 0 ? b.min.y : b.max.y,
                        zi == 0 ? b.min.z : b.max.z));
                    if (!any) { bounds = new Bounds(corner, Vector3.zero); any = true; }
                    else bounds.Encapsulate(corner);
                }
            }
            Assert.That(any, Is.True, "FcbHoubei prefab hull 包围盒非空（MeshFilter 收集）");

            // 四锚点（根局部，原生系）→ 世界系；shipCenter = hull 包围盒世界中心
            // （DeriveAnchors 的锚点框架原点——port/stbd 只在 ±X 舷侧极值上取值，符号判定与它对齐）
            var layout = NavigationLightsCore.DeriveAnchors(bounds, entry.bowYawDeg);
            var centerWorld = go.transform.TransformPoint(bounds.center);
            var portWorld = go.transform.TransformPoint(layout.PortSidelight);
            var stbdWorld = go.transform.TransformPoint(layout.StarboardSidelight);

            float portDot = Vector3.Dot(portWorld - centerWorld, starboardDir);
            float stbdDot = Vector3.Dot(stbdWorld - centerWorld, starboardDir);
            float scale = go.transform.lossyScale.x;
            Debug.Log($"[Sango.L1] heading={headingDeg:0}° bowYaw={entry.bowYawDeg:0}° " +
                      $"portDot={portDot:F2} stbdDot={stbdDot:F2} (mesh-local units; ×root scale {scale:F4} → " +
                      $"port {portDot * scale:F2} m / stbd {stbdDot * scale:F2} m world, LOA {bounds.size.z * scale:F1} m) " +
                      $"portWorld={portWorld.ToString("F1")} stbdWorld={stbdWorld.ToString("F1")}");

            // 一锤定音断言（M7-B acceptance L1 原文口径）：port 灯在 −starboard 半平面、stbd 灯在 +starboard。
            // PortSidelight = 红灯（NavigationLights.BuildRig 色表 (1,0.12,0.08) 红 / (0.15,1,0.25) 绿）。
            Assert.That(portDot, Is.LessThan(0f),
                $"heading {headingDeg}°：port（红）锚点须在 −starboard 半平面（实测 portDot={portDot:F2} local / {portDot * scale:F2} m）——" +
                "挂 = 真实反侧 bug，上报裁决不得改色别约定");
            Assert.That(stbdDot, Is.GreaterThan(0f),
                $"heading {headingDeg}°：starboard（绿）锚点须在 +starboard 半平面（实测 stbdDot={stbdDot:F2} local / {stbdDot * scale:F2} m）");
        }
    }
}
