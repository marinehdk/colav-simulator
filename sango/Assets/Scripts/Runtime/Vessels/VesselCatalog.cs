using System;
using UnityEngine;

namespace Sango
{
    /// <summary>船只尺寸档位（M2-E 遭遇脚本按档取目标）。</summary>
    public enum VesselClass
    {
        Large,  // ship-large，LOA ≈ 100 m（M2-A 仅入编目，不进 M1 场景，留给 M2-E）
        Medium, // ship-ocean-liner，LOA ≈ 60 m
        Small,  // boat-fishing-small，LOA ≈ 12 m
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
        }

        [Tooltip("流水线版本戳：Spec 变更（换源模型/改归一化规则）时递增；EnsureBuilt 见版本不符即整跑重建。")]
        public int pipelineVersion;

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
