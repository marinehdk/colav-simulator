using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEditor;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5 落位位姿契约 EditMode 测试（review F1 加固批，先例 M5FleetCatalogTests）。
    /// 放置层（M1SceneBootstrapper.PlaceCatalogShip / AnchorageFleet）只覆盖实例 root 的
    /// position/rotation、scale 与子节点一概不动——归一化（水平居中/设计吃水）必须烘在
    /// 子节点里；烘在根位姿上的补偿会被覆盖静默抹除。本测试按放置层同款赋位（heading=0）
    /// 后断言（先 instantiate 再赋位，与两层实现逐语句同款）：
    /// a) 世界包围盒 min.y ≈ waterlineOffsetY（容差 max(0.5 m, 3% LOA) 取宽者）——keel 落在设计吃水；
    /// b) 世界包围盒 center.x/z 模长 ≤ 5% LOA——水平居中。
    /// </summary>
    public class M5FleetPlacementPoseTests
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
            new TestCaseData(VesselClass.Fcb45, 45f, 0f).SetName("Fcb45 (45 m Fast Crew Boat hero, LOA 45 m, yaw 0)"),
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

        // 放置层同款赋位（heading=0）：position=(0, waterlineOffsetY, 0)，
        // rotation=Euler(0,heading,0)·Euler(0,bowYawDeg,0)；scale 不动（两层放置实现均不碰缩放）。
        GameObject PlaceAtHeadingZero(VesselClass cls, out VesselCatalog.Entry entry)
        {
            entry = LoadCatalog().GetEntry(cls);
            Assert.That(entry, Is.Not.Null, $"catalog entry missing for {cls}");
            var go = InstantiatePrefab(cls);
            go.transform.position = new Vector3(0f, entry.waterlineOffsetY, 0f);
            go.transform.rotation = Quaternion.Euler(0f, 0f, 0f) * Quaternion.Euler(0f, entry.bowYawDeg, 0f);
            return go;
        }

        static Bounds WorldRenderBounds(GameObject go)
        {
            var renderers = go.GetComponentsInChildren<Renderer>(true);
            Assert.That(renderers.Length, Is.GreaterThanOrEqualTo(1), $"{go.name}: no renderers");
            var bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);
            return bounds;
        }

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Placed_Keel_MinY_LandsOn_WaterlineOffset(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var go = PlaceAtHeadingZero(cls, out var entry);
            var bounds = WorldRenderBounds(go);
            float tolerance = Mathf.Max(0.5f, 0.03f * entry.loaMeters);
            // 放置自证（batchmode 日志取证，M1SceneBootstrapper.PlaceCatalogShip 同惯例）：
            // 实测 keel/中心逐船落表 docs 汇报与审计 center 列互证。
            Debug.Log($"[Sango.M5] placed pose {cls}: keel min.y={bounds.min.y:F3} (waterlineOffsetY {entry.waterlineOffsetY:F3}, dev {bounds.min.y - entry.waterlineOffsetY:+0.000;-0.000}), " +
                      $"center ({bounds.center.x:F3}, {bounds.center.y:F3}, {bounds.center.z:F3}) hOff {new Vector2(bounds.center.x, bounds.center.z).magnitude:F3}, " +
                      $"LOA {entry.loaMeters:F1}, tol {tolerance:F2}");
            Assert.That(bounds.min.y, Is.EqualTo(entry.waterlineOffsetY).Within(tolerance),
                $"{cls}: 放置后 keel min.y={bounds.min.y:F2} m ≠ waterlineOffsetY={entry.waterlineOffsetY:F2} m " +
                $"（偏差 {bounds.min.y - entry.waterlineOffsetY:+0.00;-0.00} m，容差 {tolerance:F2} m）" +
                $"——归一化吃水补偿烘在根位姿上，被放置层覆盖抹除");
        }

        [Test, TestCaseSource(nameof(k_FleetExpectations))]
        public void Placed_BoundsCenter_HorizontalOffset_Within5PctLoa(VesselClass cls, float targetLoa, float bowYawDeg)
        {
            var go = PlaceAtHeadingZero(cls, out var entry);
            var bounds = WorldRenderBounds(go);
            float offset = new Vector2(bounds.center.x, bounds.center.z).magnitude;
            Assert.That(offset, Is.LessThanOrEqualTo(0.05f * entry.loaMeters),
                $"{cls}: 放置后包围盒中心 ({bounds.center.x:F1}, {bounds.center.z:F1}) 水平偏移模长 {offset:F1} m " +
                $"> 5% LOA（{0.05f * entry.loaMeters:F1} m）——居中补偿烘在根位姿上，被放置层覆盖抹除");
        }
    }
}
