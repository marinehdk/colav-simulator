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
    }
}
