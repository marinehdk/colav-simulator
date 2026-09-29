using System.Collections.Generic;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M5 锚地槽位/演示航线清障不变量测试：用 PerlinIslandGenerator 同参重生成 seed-42 岛群
    /// （确定性，与 M1 场景逐位一致），按 AnchorageSlots 的裕量口径复验——挪槽位/改岛 seed/改
    /// 航线任一，本测试即红。字面量解的验证记录见
    /// docs/research/2026-09-29-m5-fleet-import/m5-audit.md（离线搜索同口径）。
    /// </summary>
    public class AnchorageSlotsTests
    {
        // hero 泊位（demo 航线起点，AnchorageSlots.StaticBerths[0] 同源）
        static readonly Vector2 k_Berth = new Vector2(30f, -12f);
        const float k_FcbLoa = 42f, k_FcbBeam = 12.6f;

        Vector2[] m_Centers;
        float[] m_Shore;

        [SetUp]
        public void SetUp()
        {
            // 与 M1SceneBootstrapper/IslandRebuild.M1Baseline 同参（resolution 96 与审计一致，
            // 保证岛体包围盒半径逐位复现）
            var islands = PerlinIslandGenerator.GenerateIslands(new IslandSettings
            {
                count = 5,
                sizeRange = new Vector2(80f, 240f),
                maxHeight = 45f,
                resolution = 96,
                seed = 42,
                clusterRadius = 260f,
                material = null,
                vertexColors = false,
            });
            islands.transform.position = new Vector3(0f, 0f, 180f);
            var centers = new List<Vector2>();
            var shore = new List<float>();
            foreach (Transform child in islands.transform)
            {
                var renderers = child.GetComponentsInChildren<Renderer>();
                var b = renderers[0].bounds;
                foreach (var r in renderers) b.Encapsulate(r.bounds);
                centers.Add(new Vector2(b.center.x, b.center.z));
                shore.Add(Mathf.Max(b.size.x, b.size.z) * 0.5f * 0.8f); // 可视岸线 ≈ 0.8R（M2-C 口径）
            }
            m_Centers = centers.ToArray();
            m_Shore = shore.ToArray();
            Object.DestroyImmediate(islands);
            Assert.That(m_Centers.Length, Is.EqualTo(5), "seed-42 岛群应 5 岛（口径漂移即红）");
        }

        [Test]
        public void DemoRoute_FcbHullRectangle_StaysOffAllIslandShores()
        {
            var path = new List<Vector2> { k_Berth };
            path.AddRange(AnchorageSlots.DemoRoute);
            float worst = float.MaxValue;
            for (int i = 0; i + 1 < path.Count; i++)
            {
                worst = Mathf.Min(worst, AnchorageSlots.RouteShoreMargin(path[i], path[i + 1], k_FcbLoa, k_FcbBeam, m_Centers, m_Shore));
            }
            // 离线验证最差 6.0 m；容差 2 m 给分辨率/浮点微差
            Assert.That(worst, Is.GreaterThanOrEqualTo(4f),
                $"FCB demo 航线船体矩形最差岛岸线裕量 {worst:F1} m < 4 m（离线解 6.0 m）");
        }

        [Test]
        public void DefaultSlots_ClearOfIslands_ByHalfDiagonalPlus12()
        {
            foreach (var slot in AnchorageSlots.Defaults)
            {
                float need = Mathf.Sqrt(Mathf.Pow(AnchorageSlots.LoaOf(slot.vesselClass), 2f) +
                                        Mathf.Pow(AnchorageSlots.BeamOf(slot.vesselClass), 2f)) * 0.5f + 12f;
                float margin = AnchorageSlots.ShoreMargin(slot.xz, m_Centers, m_Shore);
                Assert.That(margin, Is.GreaterThanOrEqualTo(need - 0.5f),
                    $"{slot.vesselClass} 槽位 {slot.xz} 岛岸线裕量 {margin:F1} < 需求 {need:F1}");
            }
        }

        [Test]
        public void DefaultSlots_KeepClearOf_DemoRouteAndStaticBerths()
        {
            var route = new List<Vector2> { k_Berth };
            route.AddRange(AnchorageSlots.DemoRoute);
            var routeArr = route.ToArray();
            foreach (var slot in AnchorageSlots.Defaults)
            {
                Assert.That(AnchorageSlots.DistanceToPolyline(slot.xz, routeArr), Is.GreaterThanOrEqualTo(50f),
                    $"{slot.vesselClass} 槽位距 demo 航线 < 50 m");
                foreach (var berth in AnchorageSlots.StaticBerths)
                {
                    Assert.That(Vector2.Distance(slot.xz, berth), Is.GreaterThanOrEqualTo(70f),
                        $"{slot.vesselClass} 槽位距静态泊位 {berth} < 70 m");
                }
            }
        }

        [Test]
        public void DefaultSlots_MutuallySeparated_ByHalfDiagonalSumPlus60()
        {
            var slots = AnchorageSlots.Defaults;
            for (int i = 0; i < slots.Length; i++)
            {
                for (int j = i + 1; j < slots.Length; j++)
                {
                    float need = (Mathf.Sqrt(Mathf.Pow(AnchorageSlots.LoaOf(slots[i].vesselClass), 2f) + Mathf.Pow(AnchorageSlots.BeamOf(slots[i].vesselClass), 2f)) +
                                  Mathf.Sqrt(Mathf.Pow(AnchorageSlots.LoaOf(slots[j].vesselClass), 2f) + Mathf.Pow(AnchorageSlots.BeamOf(slots[j].vesselClass), 2f))) * 0.5f + 60f;
                    Assert.That(Vector2.Distance(slots[i].xz, slots[j].xz), Is.GreaterThanOrEqualTo(need - 0.5f),
                        $"{slots[i].vesselClass} 与 {slots[j].vesselClass} 槽位间距不足（需 {need:F0} m）");
                }
            }
        }

        [Test]
        public void DemoRoute_StartBerth_FcbHull_IsOffAllIslandShores()
        {
            // hero 静泊位（heading 20°）：离线验证最差 11.6 m
            float worst = float.MaxValue;
            foreach (var corner in AnchorageSlots.HullCorners(k_Berth, 20f, k_FcbLoa, k_FcbBeam))
            {
                worst = Mathf.Min(worst, AnchorageSlots.ShoreMargin(corner, m_Centers, m_Shore));
            }
            Assert.That(worst, Is.GreaterThanOrEqualTo(8f), $"hero 泊位船体矩形最差裕量 {worst:F1} m < 8 m（离线解 11.6 m）");
        }
    }
}
