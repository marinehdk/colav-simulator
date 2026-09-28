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

    /// <summary>灯型（M4-B COLREG 光弧驱动用）：相对方位弧由 Rule 21 钉死，见 GetArc。</summary>
    public enum LampKind
    {
        StarboardSidelight, // 绿，右舷 112.5°
        PortSidelight,      // 红，左舷 112.5°
        Masthead,           // 白，艏向 225°
        SternLight,         // 白，艉向 135°
    }

    /// <summary>
    /// M2-D 航行灯纯核心（spec #83）：时刻→明灭阈值 + hull 包围盒→锚点布局。
    /// M4-B（issue #87 批次 B 项 3）增：Rule 21 光弧 SectorIntensity。
    /// 纯静态、无引擎场景依赖——单点真值供 NavigationLights 适配器与测试共用。
    /// </summary>
    public static class NavigationLightsCore
    {
        // ── COLREG 光弧（M4-B）──────────────────────────────────────────────────
        /// <summary>
        /// 扇区过渡带（度）：COLREG Annex I §9 允许扇区边界外 1°-3° 内衰减至实际截止，
        /// 取上限 3° = 低模 rig 上最柔的合法过渡。
        /// </summary>
        public const float SectorFalloffDeg = 3f;

        /// <summary>
        /// 相对方位约定（SectorIntensity 与适配器共用）：0 = 正艏前方，顺时针（俯视）为正
        /// = 观察者在右舷侧，[0,360)。例：90 = 右正横，180 = 正艉，270 = 左正横。
        /// </summary>
        static float Normalize360(float deg)
        {
            float d = deg % 360f;
            return d < 0f ? d + 360f : d;
        }

        /// <summary>
        /// Rule 21 光弧强度 ∈ [0,1]：relBearingDeg 在 [arcStartDeg, arcEndDeg]（顺时针区间，
        /// 支持跨 0/360 环绕，边界含端点）内 = 1；区间外按离近端边界的角距在 falloffDeg 内
        /// 线性衰减至 0（Annex I §9 "steady decrease to practical cut-off"）。
        /// falloffDeg ≤ 0 = 硬截止（无过渡带）。弧端点语义 = 舷灯 0→112.5 / 247.5→360、
        /// 桅灯 247.5→112.5（跨 0）、艉灯 112.5→247.5，全部顺时针。
        /// </summary>
        public static float SectorIntensity(float relBearingDeg, float arcStartDeg, float arcEndDeg, float falloffDeg)
        {
            float b = Normalize360(relBearingDeg);
            float span = Normalize360(arcEndDeg - arcStartDeg); // 顺时针弧长 (0,360]
            float d = Normalize360(b - Normalize360(arcStartDeg)); // 距弧起点的顺时针距离 [0,360)
            if (d <= span) return 1f; // 弧内（含边界；span=0 退化 = 单点弧）
            if (falloffDeg <= 0f) return 0f;
            float beyondEnd = d - span;   // 顺时针越过终边界的角距
            float beforeStart = 360f - d; // 逆时针距起始边界的角距
            return Mathf.Clamp01(1f - Mathf.Min(beyondEnd, beforeStart) / falloffDeg);
        }

        /// <summary>
        /// 灯型 → Rule 21 光弧（relBearing 约定的顺时针区间）：
        ///   舷灯各 112.5°（自艏向艉 22.5° 后起算：右舷 0→112.5，左舷 247.5→360）；
        ///   桅灯 225°（自艏向两舷各 112.5°：247.5→112.5 跨 0/360 环绕）；
        ///   艉灯 135°（自艉向艏每舷 67.5°：112.5→247.5）。
        /// 正艏方位 0 同时在两舷弧端点上（两舷灯在正艏均可见，Rule 21 语义如此）。
        /// </summary>
        public static (float startDeg, float endDeg) GetArc(LampKind kind)
        {
            switch (kind)
            {
                case LampKind.StarboardSidelight: return (0f, 112.5f);
                case LampKind.PortSidelight: return (247.5f, 360f);
                case LampKind.Masthead: return (247.5f, 112.5f);
                case LampKind.SternLight: return (112.5f, 247.5f);
                default: return (0f, 0f);
            }
        }

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
        /// 仰角 +7.8°，仍属日落前）。边界注意：h=6/18 时参数为 ±π/2 的 float 近似，cos 算出
        /// ~−7e-8 量级的非零值而非精确 0，恰在 6.0/18.0 的判定落侧依赖此舍入——由
        /// IsLightsOn_HorizonBoundaries6hAnd18h_ReturnsOn 在本平台钉死。
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
            return DeriveAnchors(hullBounds, 0f);
        }

        /// <summary>
        /// 带艏向修正的锚点推导。bowYawDeg = 编目 prefab 根上烘焙的"原生艏向 → +Z"根 yaw
        /// （VesselAssetPipeline：root.localRotation = Euler(0, bowYawDeg, 0)，模型子节点保持原生轴）。
        /// 锚点先按艏 +Z 舷框架计算，再映射回根局部（原生）空间：native = R(−bowYawDeg)·(bowFrame − center)
        /// + center（由 root 旋转 R(yaw)·native = corrected 反解）。编目 yaw 仅 0/180，
        /// 180° 下 AABB 对中心旋转不变 → 映射精确；未来引入非 90° 倍数 yaw 需改用 OBB 推导。
        /// </summary>
        public static NavigationLightLayout DeriveAnchors(Bounds hullBounds, float bowYawDeg)
        {
            var c = hullBounds.center;
            var e = hullBounds.extents;
            float deckY = c.y + k_SidelightHeightFrac * e.y;
            float rad = -bowYawDeg * Mathf.Deg2Rad; // native = R(−yaw)·corrected（Unity yaw：x' = x cosθ + z sinθ, z' = −x sinθ + z cosθ）
            float cos = Mathf.Cos(rad), sin = Mathf.Sin(rad);
            Vector3 ToNative(Vector3 p)
            {
                var d = p - c;
                return c + new Vector3(cos * d.x + sin * d.z, d.y, -sin * d.x + cos * d.z);
            }
            return new NavigationLightLayout
            {
                PortSidelight = ToNative(new Vector3(c.x - e.x, deckY, c.z + k_SidelightForwardFrac * e.z)),
                StarboardSidelight = ToNative(new Vector3(c.x + e.x, deckY, c.z + k_SidelightForwardFrac * e.z)),
                Masthead = ToNative(new Vector3(c.x, c.y + e.y, c.z + k_MastheadForwardFrac * e.z)),
                SternLight = ToNative(new Vector3(c.x, c.y + k_SternHeightFrac * e.y, c.z - e.z)),
            };
        }
    }
}
