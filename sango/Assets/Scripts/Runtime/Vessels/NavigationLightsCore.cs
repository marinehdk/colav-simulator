using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-D 航行灯锚点布局（spec #83 纯函数缝 b）：hull 包围盒 → 四灯本地锚点。
    /// 坐标 = prefab 根局部空间（编目 prefab 艏向 +Z：+X 右舷 / −X 左舷 / +Y 上）。
    /// </summary>
    public struct NavigationLightLayout
    {
        /// <summary>左舷 sidelight（RED）：−X 舷侧极值、上甲板、艏侧 1/3。</summary>
        public Vector3 PortSidelight;
        /// <summary>右舷 sidelight（GREEN）：+X 舷侧极值，与左舷镜像。</summary>
        public Vector3 StarboardSidelight;
        /// <summary>桅灯（WHITE）：中线、舱顶最高、艏部上方。</summary>
        public Vector3 Masthead;
        /// <summary>艉灯（WHITE）：中线、上甲板、艉端极值。</summary>
        public Vector3 SternLight;
    }

    /// <summary>
    /// M2-D 航行灯纯核心（spec #83）：时刻→明灭阈值 + hull 包围盒→锚点布局。
    /// 纯静态、无引擎场景依赖——单点真值供 NavigationLights 适配器与测试共用。
    /// </summary>
    public static class NavigationLightsCore
    {
        // 锚点分数常量（hull 半尺寸的比例；worked examples 钉死在测试侧，改这里必红）：
        // 舷灯上甲板（中心 + 0.5·半高）、艏侧 1/3 站位；桅灯舱顶、艏部上方；艉灯上甲板、艉端极值。
        const float k_SidelightHeightFrac = 0.5f;
        const float k_SidelightForwardFrac = 0.3f;
        const float k_MastheadForwardFrac = 0.4f;
        const float k_SternHeightFrac = 0.5f;

        /// <summary>
        /// 明灭阈值（spec #83 "sun-below-horizon heuristic"）：仰角 = 60·cos(π(h−12)/12)，
        /// 与 WeatherController.ApplySun 逐字同式（滑条 [0,24] 同一时刻语义，改公式须两处同步）。
        /// 仰角 ≤ 0 开灯：地平线恰好 0°（6h/18h）时直射日光贡献为 0（ApplySun 强度落到 0.1 lux
        /// 地板），归夜侧。COLREGs 语义 = 日落点灯：昼窗 (6,18) 开区间内灭灯（17.5h 傍晚档
        /// 仰角 +7.8°，仍属日落前）。
        /// </summary>
        public static bool IsLightsOn(float timeOfDayHours)
        {
            float elevationDeg = 60f * Mathf.Cos(Mathf.PI * (timeOfDayHours - 12f) / 12f);
            return elevationDeg <= 0f;
        }

        /// <summary>
        /// hull 包围盒（根局部空间，艏 +Z / 右舷 +X）→ 四灯锚点。归一化分数偏移，
        /// 不做每型号手工摆位——任意未来编目条目直接可用（spec #83 Implementation Decisions）。
        /// </summary>
        public static NavigationLightLayout DeriveAnchors(Bounds hullBounds)
        {
            var c = hullBounds.center;
            var e = hullBounds.extents;
            float deckY = c.y + k_SidelightHeightFrac * e.y;
            return new NavigationLightLayout
            {
                PortSidelight = new Vector3(c.x - e.x, deckY, c.z + k_SidelightForwardFrac * e.z),
                StarboardSidelight = new Vector3(c.x + e.x, deckY, c.z + k_SidelightForwardFrac * e.z),
                Masthead = new Vector3(c.x, c.y + e.y, c.z + k_MastheadForwardFrac * e.z),
                SternLight = new Vector3(c.x, c.y + k_SternHeightFrac * e.y, c.z - e.z),
            };
        }
    }
}
