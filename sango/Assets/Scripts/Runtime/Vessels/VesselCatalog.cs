using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// 船只尺寸/船型档位（M2-E 遭遇脚本按 Large/Medium/Small 档取目标）。
    /// M5 枚举方案（2026-09-29，最小改动）：保留既有三档语义不动（遭遇脚本/测试的字面量
    /// 依赖零迁移），新船按"船型名"追加在尾部——插入或重命名旧值会破坏已序列化场景引用。
    /// </summary>
    public enum VesselClass
    {
        Large,  // ship-large，LOA ≈ 100 m（M2-A 仅入编目，不进 M1 场景，留给 M2-E）
        Medium, // ship-ocean-liner，LOA ≈ 60 m
        Small,  // boat-fishing-small，LOA ≈ 12 m

        // ── M5 采购船队（路线 A 免费件，CC-BY，Assets/Art/Purchased/）──────────────
        // 尺寸语义另查 VesselCatalog.loaMeters（每型实测归一化 LOA）；C3 面数裁决见
        // docs/research/2026-09-29-m5-fleet-import/m5-audit.md。
        Tanker,         // ArtBlender「Tanker Ship」Suez-Max 原油轮，LOA 300 m（中景）
        TankerLng,      // ArtBlender「LNG Ship」Moss 型液化气船，LOA 300 m（中景）
        CargoContainer, // RM02「Container Ship」集装箱船，LOA 150 m（中景，>150k tri 限中景）
        CargoGeneral,   // hungry_drifter「Cargo ship」杂货船，LOA 120 m（中景）
        Tug,            // davidbroutian「RAstar 3200」港作拖轮，LOA 32 m（中景）
        FishingTrawler, // JasperTobias「Trawler」拖网渔船，LOA 25 m（中远）
        FcbHoubei,      // dannzjs「Type 22 missile boat」FCB 占位主角，LOA 42 m（hero 白壳绿装；M1 场景主角——M6 hero 已换 Fcb45）
        FcbPc3,         // S1Priv「Lowpoly USS Hurricane (PC-3)」巡逻艇，LOA 55 m（副选/远景）

        // ── FCB45 真主角（用户自建 Blender 交付，Art/Purchased/fcb45/；provenance 见该目录）──
        Fcb45,          // 45 m Fast Crew Boat，LOA 45 m / 型宽 8 m / 设计吃水 1.55 m（M6 海峡场景 hero）
    }

    /// <summary>
    /// 船只编目（spec #80）：按 VesselClass 暴露 prefab 引用 + 实测 LOA + 水线偏移。
    /// 由 Sango.Editor.VesselAssetPipeline 生成并维护（幂等更新，不手工编辑）；
    /// EditMode 测试（Sango.Tests.EditMode）守 prefab 不变量，M2-B 直接消费 waterlineOffsetY。
    /// </summary>
    [CreateAssetMenu(fileName = "VesselCatalog", menuName = "Sango/Vessel Catalog", order = 0)]
    public class VesselCatalog : ScriptableObject
    {
        [Serializable]
        public class Entry
        {
            [Tooltip("编目键：尺寸档位。")]
            public VesselClass vesselClass;

            [Tooltip("归一化 prefab：根含统一缩放与艏向 +Z 的烘焙，渲染器全部挂 HDRP/Lit(colormap)。")]
            public GameObject prefab;

            [Tooltip("实测总长 LOA（根尺度下渲染器包围盒最大水平边，米）。")]
            public float loaMeters;

            [Tooltip("水线偏移（米，负值）：把 prefab 根放到 y=offset 让约 15% 船体高没入 y=0 水面。")]
            public float waterlineOffsetY;

            [Tooltip("实测艏端细度：模型原生坐标里、被 pinned yaw 映射到 +Z 那一端近端的 hull 宽度（导入尺度）。")]
            public float bowEndWidth;

            [Tooltip("实测艉端宽度：与 bowEndWidth 同一次测量的对端（艉）。几何上应严格大于 bowEndWidth（艏尖艉肥）。")]
            public float sternEndWidth;

            [Tooltip("艏向烘焙 yaw（度）：原生艏 → +Z 的 prefab 根 localRotation.y。Kenney 档 0/180；M5 采购件另有 90/270（X 轴原生船）。放置层组合 rotation = Euler(0,heading,0)·Euler(0,bowYawDeg,0)。")]
            public float bowYawDeg;
        }

        [Tooltip("流水线版本戳：Spec 变更（换源模型/改归一化规则）时递增；EnsureBuilt 见版本不符即整跑重建。")]
        public int pipelineVersion;

        [Tooltip("M5 采购船队流水线版本戳（Sango.Editor.M5FleetPipeline）：与 Kenney 三档的 pipelineVersion 分账，bump 强制重导 Purchased/ 船。")]
        public int fleetPipelineVersion;

        [Tooltip("三个尺寸档各一条；由流水线整表重写。")]
        public Entry[] entries = Array.Empty<Entry>();

        /// <summary>按档位查条目；缺条目返回 null（测试把“三档齐全”当不变量守着）。</summary>
        public Entry GetEntry(VesselClass vesselClass)
        {
            if (entries == null) return null;
            foreach (var e in entries)
            {
                if (e != null && e.vesselClass == vesselClass) return e;
            }
            return null;
        }

        /// <summary>按档位取 prefab 的便捷口（M2-E 主入口）。</summary>
        public GameObject GetPrefab(VesselClass vesselClass)
        {
            return GetEntry(vesselClass)?.prefab;
        }
    }
}
