using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M9-2 夜景光照纯核心（无引擎场景依赖，EditMode worked examples 钉值，同 NavigationLightsCore 口径）：
    /// ①夜间曝光补偿曲线——太阳仰角 → 附加负 EV，修"夜空不暗"（M6 profile 自动曝光 limitMax=14 会把
    /// 0.1 lux 夜景重新 normalize 回中灰，固定负补偿移动直方图目标才压得住，M7-B 雷暴 −1.6 EV 白天先例）；
    /// ②号灯光斑径向衰减——billboard 圆形化（替代交叉双面十字的方核穿帮）；
    /// ③billboard 边长换算——亮核圆直径 = 原方片边长的观感尺寸守恒；
    /// ④拖尾点光层级因子——夜里反射拖尾与点光亮度一致性微调（桅灯 &gt; 舷灯 &gt; 艉灯）。
    /// </summary>
    public static class NightGradeCore
    {
        // ── 夜间曝光地板（WeatherController.ApplySun → ApplyAtmosphereExtras 消费）─────
        /// <summary>暮光渐入带宽（度）：仰角 0 → −6°（civil twilight 量级）线性渐入，日落不跳变。</summary>
        public const float NightEvFadeDeg = 6f;

        /// <summary>夜间地板补偿（EV，负 = 压暗）：−3 EV ≈ 8×，雷暴白天 −1.6 EV 先例之上的夜间加码（TBD-实机调值）。</summary>
        public const float NightFloorEv = -3f;

        /// <summary>
        /// 夜间补偿 EV ∈ [floorEv, 0]：仰角 ≥ 0 恒返 0f（白天与旧契约逐位一致——消费方以 != 0
        /// 判定是否并入加法）；0 → −fadeDeg 线性渐入；≤ −fadeDeg 满幅地板。
        /// 入参口径 = WeatherController.ApplySun 的钳后仰角（−18..60°）。
        /// </summary>
        public static float NightCompensationEv(float sunElevationDeg, float fadeDeg = NightEvFadeDeg, float floorEv = NightFloorEv)
        {
            if (sunElevationDeg >= 0f) return 0f;
            if (sunElevationDeg <= -fadeDeg) return floorEv;
            return floorEv * (-sunElevationDeg / fadeDeg);
        }

        // ── 号灯光斑（NavigationLights.BuildLamp / LampSpotTexture 消费）──────────────
        /// <summary>亮核半径（占半边长分数）：核内恒 1（灯珠本体），核外指数衰减 halo；billboard 边长按此反算。</summary>
        public const float LampSpotCoreRadius01 = 0.25f;

        /// <summary>halo 指数衰减率：r=1 处 alpha = exp(−4.5) ≈ 0.011（近零收边，TBD-实机观感）。</summary>
        public const float LampSpotHaloDecay = 4.5f;

        /// <summary>
        /// 光斑径向衰减 ∈ (0,1]：r01 ≤ coreRadius01 恒 1（亮核），核外 exp(−decay·(r−core)/(1−core))
        /// 自核边指数衰减至 r=1 的 exp(−decay)。r01 钳 [0,1]（贴图角落 r 可达 √2）。
        /// </summary>
        public static float LampSpotFalloff(float r01, float coreRadius01 = LampSpotCoreRadius01, float haloDecay = LampSpotHaloDecay)
        {
            r01 = Mathf.Clamp01(r01);
            if (r01 <= coreRadius01) return 1f;
            return Mathf.Exp(-haloDecay * (r01 - coreRadius01) / Mathf.Max(1e-5f, 1f - coreRadius01));
        }

        /// <summary>billboard 边长 m：亮核圆直径（2·core·edge）= lampSizeM（原方片边长），观感尺寸守恒。</summary>
        public static float BillboardEdgeM(float lampSizeM, float coreRadius01 = LampSpotCoreRadius01)
            => lampSizeM / Mathf.Max(2f * coreRadius01, 1e-5f);

        // ── 拖尾点光层级（NavigationLights.BuildRig 消费）─────────────────────────────
        /// <summary>
        /// 拖尾亮度/长度因子 ∈ [0.55, 1]：按灯点光流明占最亮灯（桅灯）的比例微调——夜里反射
        /// 拖尾与点光层级一致（桅灯 600 lm 全强、舷灯 300 lm → 0.775、艉灯 200 lm → 0.70）；
        /// 比例 ≥ 1 钳满幅。只动观感弱项（alpha/长度），不重做拖尾几何。
        /// </summary>
        public static float StreakNightFactor(float lampLumens, float maxLampLumens)
            => Mathf.Lerp(0.55f, 1f, Mathf.Clamp01(lampLumens / Mathf.Max(1f, maxLampLumens)));
    }
}
