using System;

namespace Sango
{
    /// <summary>
    /// Twin 船槽选型（P2-S1 spec #89；纯函数）。truth 的 length/width 是后端场景事实
    /// （head_on 本船 8.45 m / replay run 745d63fd 本船 44.1 m），本地编目按实测 LOA
    /// 最近匹配挑 prefab 槽——|loa − length| 最小者，平手取先（编目顺序稳定）。
    /// 匹配不到编目（空/缺条目）返回 null，消费方跳过该船并计数，不脑补替身。
    /// </summary>
    public static class TwinShipFactory
    {
        public static VesselCatalog.Entry Select(VesselCatalog catalog, float lengthMeters)
        {
            if (catalog == null || catalog.entries == null) return null;
            VesselCatalog.Entry best = null;
            float bestDistance = float.MaxValue;
            foreach (var entry in catalog.entries)
            {
                if (entry == null) continue;
                float distance = Math.Abs(entry.loaMeters - lengthMeters);
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    best = entry;
                }
            }
            return best;
        }

        /// <summary>
        /// 按型取编目条目（目标船视觉档位；查无此型返回 null 走 truth 匹配）。
        /// 20261015 用户裁决：DT 视口目标船统一大视觉档（12m 真值渔船在 2km 外仅
        /// ~4px 低于 YOLO P3 检测下限）；20261020 改默认 BulkCarrier 180m 散货船
        /// （真实船型+更大目标）；物理仍按 truth.length，仅显示层换型
        /// （--twin-target-visual truth 可复原）。
        /// </summary>
        public static VesselCatalog.Entry SelectByClass(VesselCatalog catalog, VesselClass vesselClass)
        {
            if (catalog == null || catalog.entries == null) return null;
            foreach (var entry in catalog.entries)
                if (entry != null && entry.vesselClass == vesselClass) return entry;
            return null;
        }

        /// <summary>视觉档位 CLI 值解析（纯函数，测试锚）："truth"→null（按真值匹配），
        /// 合法型名（大小写不敏感）→该型，非法值原样返回 fallback 不动当前档。</summary>
        public static VesselClass? ParseVisualOverride(string value, VesselClass? fallback)
        {
            if (string.Equals(value, "truth", StringComparison.OrdinalIgnoreCase)) return null;
            return Enum.TryParse(value, true, out VesselClass parsed) ? parsed : fallback;
        }
    }
}
