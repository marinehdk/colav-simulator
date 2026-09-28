using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// 海浪谱档位。HDRP Water 不暴露谱型选择（PM/JONSWAP/TMA），此枚举为 JS-PM 档位的
    /// band 幅值/风强近似映射（PLAN §5 M1 诚实点）；档位→band 组合见 ApplyWater 内 Tier* 表。
    /// </summary>
    public enum JsPmTier
    {
        Calm = 0,
        Moderate = 1,
        Rough = 2,
        VeryRough = 3,
    }

    /// <summary>
    /// M1 天气状态与 HDRP 映射核心。GUI（WeatherGUI）改公开字段后调 Apply()。
    /// 所有 HDRP 专有字段调用处均注明 HDRP 17.3.0 源码 file:line（包缓存
    /// sango/Library/PackageCache/com.unity.render-pipelines.high-definition@700710090fa9/）。
    /// </summary>
    public class WeatherController : MonoBehaviour
    {
        [Header("Scene refs (M1SceneBootstrapper 接线)")]
        public WaterSurface waterSurface;
        public Volume globalVolume;
        public Light sunLight;

        [Header("Weather state")]
        [Range(0f, 11f)] public float beaufort = 3f;                 // 蒲福风级滑条值（0.1 步进在 GUI 侧钳）
        [Range(0f, 360f)] public float windDirectionDeg = 30f;       // 风向 deg（波向沿用同值：涌浪/涟漪均对齐风向）
        [Range(0f, 24f)] public float timeOfDayHours = 12f;          // 时刻 h
        [Range(0f, 1f)] public float cloudCover = 0.4f;              // 云量 0-1（→ 预设四档量化，见 ApplyClouds）
        [Min(100f)] public float fogDistanceMeters = 3000f;          // 雾距 m
        public JsPmTier spectrumTier = JsPmTier.Moderate;            // 海浪谱档位

        [Header("Runtime")]
        public bool applyEveryFrame = true;                          // Play 中每帧 Apply（GUI 拖动即时生效的兜底）

        /// <summary>最近一次 Apply 算出的风速 m/s（GUI 顶部读数与映射表核对用，M1 验收条款 2）。</summary>
        public float LastWindSpeedMs { get; private set; }

        // 蒲福→风速锚点（级内中值，公认换算：B0≈0.5 / B3≈4.5 / B6≈12.5 / B9≈22.5，PLAN §5 M1 验收 1）
        static readonly (float bft, float ms)[] WindAnchors =
        {
            (0f, 0.5f), (3f, 4.5f), (6f, 12.5f), (9f, 22.5f),
        };

        // 谱档→band 组合近似（起调值，全部 TBD-实机调值；量级指引见 sango/Docs/beaufort-water-mapping.md 调值指引节）
        static readonly float[] TierSwellWindFactor = { 0.35f, 0.60f, 0.90f, 1.10f }; // ×风速 → largeWindSpeed
        static readonly float[] TierBand0Mult       = { 0.15f, 0.35f, 0.50f, 0.65f }; // 涌浪 band 幅值倍率
        static readonly float[] TierBand1Mult       = { 0.10f, 0.25f, 0.45f, 0.70f }; // 风浪 band 幅值倍率
        static readonly float[] TierRippleWindFactor = { 0.5f, 0.8f, 1.0f, 1.3f };    // ×风速 km/h → ripplesWindSpeed（钳 0..15）
        static readonly float[] TierRippleChaos     = { 0.60f, 0.70f, 0.80f, 0.90f };
        static readonly float[] TierFoamAmount      = { 0.00f, 0.10f, 0.25f, 0.45f }; // 白沫量
        static readonly string[] TierNames          = { "Calm", "Moderate", "Rough", "VeryRough" };

        void Update()
        {
            if (applyEveryFrame && Application.isPlaying) Apply();
        }

        void OnValidate()
        {
            // 仅 Play 中触发，避免编辑器态反复实例化 Volume 运行时副本
            if (Application.isPlaying) Apply();
        }

        /// <summary>
        /// 蒲福级→风速 m/s：锚点间分段线性插值；末段斜率外推 B9-B11（B11≈29.2，落在公认 28.8-32.6 区间内）。
        /// public static：映射表文档与 GUI 读数共用同一实现，保证"面板风速与映射表一致"（M1 验收条款 2）。
        /// </summary>
        public static float BeaufortToWindSpeedMs(float bft)
        {
            bft = Mathf.Clamp(bft, WindAnchors[0].bft, 11f);
            if (bft >= WindAnchors[WindAnchors.Length - 1].bft)
            {
                var last = WindAnchors[WindAnchors.Length - 1];
                var prev = WindAnchors[WindAnchors.Length - 2];
                float slope = (last.ms - prev.ms) / (last.bft - prev.bft);
                return last.ms + (bft - last.bft) * slope;
            }
            for (int i = 0; i < WindAnchors.Length - 1; i++)
            {
                var a = WindAnchors[i];
                var b = WindAnchors[i + 1];
                if (bft <= b.bft) return Mathf.Lerp(a.ms, b.ms, (bft - a.bft) / (b.bft - a.bft));
            }
            return WindAnchors[WindAnchors.Length - 1].ms; // 不可达
        }

        public string TierName() => TierNames[(int)spectrumTier];

        /// <summary>把全部状态刷到 HDRP 对象。空引用安全（可只接部分场景对象分步验证）。</summary>
        public void Apply()
        {
            float windMs = BeaufortToWindSpeedMs(beaufort);
            LastWindSpeedMs = windMs;
            ApplyWater(windMs);
            ApplySun();
            ApplyCloudsAndFog();
        }

        // ── Water band 映射 ─────────────────────────────────────────────────────────────
        // HDRP 17.3 Water band 参数挂在 WaterSurface 分部类（无独立谱型字段）。源码：
        //   Runtime/Water/WaterSurface/WaterSurface.Simulation.cs
        //     :27   repetitionSize        [250..5000] m  涌浪 patch 尺寸（常量 WaterSystemDef.cs:36-38）
        //     :32   largeOrientationValue deg            涌浪/风浪方向（涟漪默认 Inherit 时同向，Simulation.cs:284）
        //     :38   largeWindSpeed        [0..250] km/h  涌浪风速。注意单位 km/h：内部 ×1/3.6 转 m/s
        //                                                （Simulation.cs:291-293；换算常量 WaterSystemDef.cs:17-21）
        //     :44   largeChaos            [0..1]         方向衰减（patchWindDirDampener，Simulation.cs:296-298）
        //     :50   largeBand0Multiplier  [0..1]         涌浪 band 幅值倍率（Simulation.cs:397-399）
        //     :71   largeBand1Multiplier  [0..1]         风浪 band 幅值倍率
        //     :109  ripplesWindSpeed      [0..15] km/h   涟漪风速（上限 k_RipplesMaxWindSpeed=15，WaterSystemDef.cs:52）
        //     :115  ripplesChaos          [0..1]
        //   Runtime/Water/WaterSurface/WaterSurface.Foam.cs
        //     :14   foam                  bool           白沫模拟开关
        //     :55   simulationFoamAmount  [0..1]         白沫量（白帽覆盖强度）
        // 运行时改字段即生效：CheckResources 每帧重算 spectrum 参数，与旧值不同则失效重建
        // （WaterSurface.Simulation.cs:221-231），无需额外刷新 API。
        void ApplyWater(float windMs)
        {
            if (waterSurface == null) return;
            int t = (int)spectrumTier;
            float windKmh = windMs * 3.6f; // largeWindSpeed/ripplesWindSpeed 单位 km/h（见上注）

            waterSurface.largeWindSpeed = Mathf.Clamp(windKmh * TierSwellWindFactor[t], 0f, 250f);
            waterSurface.largeBand0Multiplier = Mathf.Clamp01(TierBand0Mult[t]);
            waterSurface.largeBand1Multiplier = Mathf.Clamp01(TierBand1Mult[t]);
            waterSurface.largeOrientationValue = windDirectionDeg;
            waterSurface.largeChaos = Mathf.Lerp(0.9f, 0.5f, t / 3f); // 低风更单向，高风更散（起调值 TBD-实机）
            waterSurface.ripples = true;
            waterSurface.ripplesWindSpeed = Mathf.Clamp(windKmh * TierRippleWindFactor[t], 0f, 15f);
            waterSurface.ripplesChaos = Mathf.Clamp01(TierRippleChaos[t]);
            waterSurface.ripplesOrientationValue = windDirectionDeg;
            waterSurface.foam = true;
            waterSurface.simulationFoamAmount = Mathf.Clamp01(TierFoamAmount[t]);
            // 白沫起风阈值曲线留组件默认（preset 曲线：归一化风速 <0.2 无沫、>0.3 全沫，
            // WaterSurface.Presets.cs:100；Foam.cs:80 simulationFoamWindCurve），实机后随档位再调。
        }

        // ── 时刻 → 太阳 ────────────────────────────────────────────────────────────────
        // 粗近似模型（TBD-实机）：仰角 = 60°·cos(π·(h-12)/12)，地平线下钳 -18°；方位角 24h 匀速一圈。
        // Physical Sky 自动把场景方向光当太阳（M0SceneBootstrapper.cs 注释 c：HDRP 17.3 无 SetSun()
        // 公开 API，PhysicallyBasedSkyRenderer.FindSunLight 取场景方向光），转方向光即驱动天空变暗。
        // 强度：HDRP 方向光单位 lux；正午 100000 lux（M0 同值），夜间钳 0.1 lux（满月 ~0.1-0.3 lux 量级，
        // PLAN §5 M1"夜间接近 0 并保持微弱月光量级"）。画面3 验收降为"暗夜空"（PLAN §6 修订 2）。
        void ApplySun()
        {
            if (sunLight == null) return;
            float elevationDeg = Mathf.Max(-18f, 60f * Mathf.Cos(Mathf.PI * (timeOfDayHours - 12f) / 12f));
            float azimuthDeg = (timeOfDayHours / 24f) * 360f;
            sunLight.transform.rotation = Quaternion.Euler(elevationDeg, azimuthDeg, 0f);
            float dayFactor = Mathf.Clamp01(Mathf.Sin(elevationDeg * Mathf.Deg2Rad));
            sunLight.intensity = Mathf.Lerp(0.1f, 100000f, dayFactor * dayFactor); // 平方压暗晨昏
        }

        // ── 云量 / 雾距 → Volume override ─────────────────────────────────────────────
        // 运行时改 Volume 的方式：读 volume.profile（getter 把 sharedProfile Instantiate 成运行时副本，
        // 改副本不落盘；直接改 sharedProfile 会持久化进资产并影响所有引用该资产的 Volume——
        // core 包源码 Runtime/Volume/Volume.cs:55-63 注释、:77-87 实现）。TryGet：
        // core 包 Runtime/Volume/VolumeProfile.cs:231。参数写入必须 .Override()：.value setter
        // 只写 m_Value 不置 overrideState（core VolumeParameter.cs:182-186），HDRP 体积混合只认
        // overrideState=True 的参数（Override 实现 :234-238；同 1297f610 曝光修复口径）。
        void ApplyCloudsAndFog()
        {
            if (globalVolume == null) return;
            var profile = globalVolume.profile;

            // 云：HDRP 17.3 VolumetricClouds 无标量 coverage 字段（枚举/预设见
            // Runtime/Lighting/VolumetricClouds/VolumetricClouds.cs:38-69 CloudControl/CloudPresets，
            // :216-229 cloudPreset 属性与 m_CloudPreset）。唯一连续覆盖参数 cumulusMapMultiplier(:241)
            // 仅 Advanced 模式生效，M1 弃用。云量 0-1 量化到 Simple 模式四档预设（阈值 TBD-实机）。
            // setter 赋值触发 ApplyCurrentCloudPreset 重写 density/erosion/altitude（VolumetricClouds.cs:502）。
            if (profile.TryGet<VolumetricClouds>(out var clouds))
            {
                clouds.enable.value = true;
                var preset = cloudCover < 0.25f ? VolumetricClouds.CloudPresets.Sparse
                           : cloudCover < 0.50f ? VolumetricClouds.CloudPresets.Cloudy
                           : cloudCover < 0.75f ? VolumetricClouds.CloudPresets.Overcast
                           : VolumetricClouds.CloudPresets.Stormy;
                if (clouds.cloudPreset != preset) clouds.cloudPreset = preset; // 仅变化时赋值，避免每帧重刷预设
            }

            // 雾：用现行 Fog override（旧 VolumetricFog 组件已 [Obsolete("#from(2021.2)")]，
            // Runtime/Lighting/AtmosphericScattering/VolumetricFog.cs:7-9，勿引用）。字段源码 Fog.cs：
            //   :17 enabled              BoolParameter   雾总开关
            //   :29 maxFogDistance       MinFloatParameter(5000, 0)  m，远处雾的裁剪距离
            //   :50 meanFreePath         MinFloatParameter(400, 1)   m，体积雾散射平均自由程（决定可见度）
            //   :55 enableVolumetricFog  BoolParameter   体积雾子开关
            //   :47 maximumHeight        FloatParameter  雾层顶高 m
            if (profile.TryGet<Fog>(out var fog))
            {
                fog.active = true;
                // .Override() 而非 .value：value setter 只写 m_Value 不置 overrideState
                // （VolumeParameter.cs:182-186），雾参数从未真正生效 = 雾距滑条 no-op
                // （census fogEn=True(ovr=False) 逐字证据）；Override 一并置位（:234-238）。
                fog.enabled.Override(true);
                fog.enableVolumetricFog.Override(true);
                fog.maxFogDistance.Override(Mathf.Max(0f, fogDistanceMeters));
                fog.meanFreePath.Override(Mathf.Max(1f, fogDistanceMeters)); // 起调值修正：0.25×雾距在 3km 档自由程仅 750m，
                                                                             // 数公里外全白且散射拖暗正午（M1-C 实测）；1× 保持
                                                                             // 雾感同时目标可见（仍 TBD-实机微调）
                fog.maximumHeight.Override(120f); // 雾层盖过桥楼视线（相机 y=12 + 余量），TBD-实机
            }
        }
    }
}
