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

        [Header("M7-B atmosphere tier (V key / GUI dropdown; preset = M7BMath.AtmospherePresetFor)")]
        public M7BMath.AtmosphereTier atmosphereTier = M7BMath.AtmosphereTier.HazyClear; // 浓霾晴 = 默认档
        [Range(-3f, 1f)] public float exposureCompensationEv = 0f;   // 当前曝光补偿 EV（档间过渡动画值）
        [Range(0f, 1f)] public float sunDimFactor = 1f;              // 当前直射太阳强度乘子（过渡动画值）
        [Min(0f)] public float rainRate = 0f;                        // 当前雨粒子发射率 粒子/s（过渡动画值）
        [Tooltip("雨粒子 VFX（场景构建器挂 Main Camera；空则无雨）。")]
        public RainFall rain;

        [Header("Runtime")]
        public bool applyEveryFrame = true;                          // Play 中每帧 Apply（GUI 拖动即时生效的兜底）

        /// <summary>最近一次 Apply 算出的风速 m/s（GUI 顶部读数与映射表核对用，M1 验收条款 2）。</summary>
        public float LastWindSpeedMs { get; private set; }

        /// <summary>最近一次 Apply 算出的夜间补偿 EV（白天恒 0；M9-2 夜间曝光地板观测口）。</summary>
        public float LastNightCompensationEv => m_NightCompEv;

        // ── M7-B 大气档间过渡（preset lerp；AdvanceAtmosphereTransition 是 EditMode 可测缝）──
        // 目标值来自 M7BMath.AtmospherePresetFor（纯函数）；动画只改 fogDistanceMeters/cloudCover/
        // exposureCompensationEv/sunDimFactor/rainRate 五个"当前值"字段（GUI 滑条镜像随动），HDRP
        // 写入仍走既有 Apply 管线（.Override 口径）。初始 m_TransT == m_TransDur = 无过渡，字段
        // 保持Inspector/构建器注入值——首次 ApplyAtmosphereTier 才起动画。
        // M9-2：beaufort（风档）并入同轨（ApplyAtmosphereTier 钉当前值不动风；风渐变只走
        // BeginUserGradeTransition——digits/F 等用户直设路径的切档断崖修复）。
        float m_TransT = 1f;
        float m_TransDur = 1f;
        float m_FogFrom, m_FogTo, m_CloudFrom, m_CloudTo, m_EvFrom, m_EvTo, m_DimFrom, m_DimTo, m_RainFrom, m_RainTo;
        float m_BftFrom, m_BftTo;
        float m_SpectrumCurrent = float.NaN;
        float m_SpectrumFrom, m_SpectrumTo;

        // M9-2 夜间曝光地板调值（NightGradeCore 曲线；TBD-实机）：暮光带宽 6°（civil twilight
        // 量级，日落渐入不跳变）、地板 −3 EV（雷暴白天 −1.6 EV 先例之上的夜间加码，≈8× 压暗）。
        const float k_NightEvFadeDeg = NightGradeCore.NightEvFadeDeg;
        const float k_NightFloorEv = NightGradeCore.NightFloorEv;
        float m_NightCompEv; // 最近一次 ApplySun 算出的夜间补偿 EV（白天恒 0；观测口 LastNightCompensationEv）

        /// <summary>档间过渡进行中？（首帧前 false——初始字段即当前值。）</summary>
        public bool AtmosphereTransitioning => m_TransT < m_TransDur;

        /// <summary>
        /// 切到 atmosphereTier 并从当前值起过渡（WeatherGUI N 键/下拉消费；可重复调用重定向）。
        /// </summary>
        public void ApplyAtmosphereTier()
        {
            BeginSpectrumTransition();
            var p = M7BMath.AtmospherePresetFor(atmosphereTier);
            m_FogFrom = fogDistanceMeters; m_FogTo = p.fogDistanceM;
            m_CloudFrom = cloudCover; m_CloudTo = p.cloudCover;
            m_EvFrom = exposureCompensationEv; m_EvTo = p.exposureCompensationEv;
            m_DimFrom = sunDimFactor; m_DimTo = p.sunDimFactor;
            m_RainFrom = rainRate; m_RainTo = p.rain ? p.rainRate : 0f;
            m_BftFrom = beaufort; m_BftTo = beaufort; // N 档不动风（通道钉当前值；M8RecordingRunner 确定性路径行为不变）
            m_TransDur = Mathf.Max(0.01f, p.transitionSeconds);
            m_TransT = 0f;
        }

        /// <summary>
        /// 用户切档渐变（M9-2）：GUI digits 0-9（风档）/ F 键（雾距）等原"直设字段即跳变"的
        /// 切档改目标态 + smoothstep 渐变（默认 2.5 s，任务 2-3 s 窗中值）。可空参数 = 通道不
        /// 参与（钉当前值，与其他通道同轨推进，半途重定向不跳变，语义同 ApplyAtmosphereTier
        /// 可重复调用）。只服务用户切档路径：M8RecordingRunner 与 T 键直设 timeOfDayHours 的
        /// 确定性路径不经此缝（时刻永不渐变）；N 键大气档走 ApplyAtmosphereTier（preset
        /// transitionSeconds = 3 s，本就在 2-3 s 窗内）。
        /// </summary>
        public void BeginUserGradeTransition(float? targetBeaufort = null, float? targetFogMeters = null, float durationSeconds = 2.5f)
        {
            BeginSpectrumTransition();
            m_BftFrom = beaufort; m_BftTo = targetBeaufort ?? beaufort;
            m_FogFrom = fogDistanceMeters; m_FogTo = targetFogMeters ?? fogDistanceMeters;
            m_CloudFrom = m_CloudTo = cloudCover;
            m_EvFrom = m_EvTo = exposureCompensationEv;
            m_DimFrom = m_DimTo = sunDimFactor;
            m_RainFrom = m_RainTo = rainRate;
            m_TransDur = Mathf.Max(0.01f, durationSeconds);
            m_TransT = 0f;
        }

        /// <summary>
        /// 推进过渡 dt 秒（Update 消费 Time.deltaTime；EditMode 测试直接喂 dt——Time.time 在
        /// 编辑器态不前进，dt 显式参数是可测缝）。返回 true = 仍在过渡中。
        /// </summary>
        public bool AdvanceAtmosphereTransition(float dt)
        {
            if (!AtmosphereTransitioning) return false;
            m_TransT = Mathf.Min(m_TransDur, m_TransT + Mathf.Max(0f, dt));
            float t = m_TransT / m_TransDur;
            t = t * t * (3f - 2f * t); // smoothstep：档间两端缓入缓出
            fogDistanceMeters = Mathf.Lerp(m_FogFrom, m_FogTo, t);
            cloudCover = Mathf.Lerp(m_CloudFrom, m_CloudTo, t);
            exposureCompensationEv = Mathf.Lerp(m_EvFrom, m_EvTo, t);
            sunDimFactor = Mathf.Lerp(m_DimFrom, m_DimTo, t);
            rainRate = Mathf.Lerp(m_RainFrom, m_RainTo, t);
            beaufort = Mathf.Lerp(m_BftFrom, m_BftTo, t); // M9-2：风档同轨渐变（风m/s/浪 band 全部随 Apply 派生）
            m_SpectrumCurrent = Mathf.Lerp(m_SpectrumFrom, m_SpectrumTo, t);
            return AtmosphereTransitioning;
        }

        void BeginSpectrumTransition()
        {
            m_SpectrumFrom = float.IsNaN(m_SpectrumCurrent) ? (float)spectrumTier : m_SpectrumCurrent;
            m_SpectrumTo = (float)spectrumTier;
            m_SpectrumCurrent = m_SpectrumFrom;
        }

        static float TierValue(float[] values, float tier)
        {
            tier = Mathf.Clamp(tier, 0f, values.Length - 1f);
            int lo = Mathf.FloorToInt(tier);
            return Mathf.Lerp(values[lo], values[Mathf.Min(lo + 1, values.Length - 1)], tier - lo);
        }

        // 蒲福→风速锚点（级内中值，公认换算：B0≈0.5 / B3≈4.5 / B6≈12.5 / B9≈22.5，PLAN §5 M1 验收 1）
        static readonly (float bft, float ms)[] WindAnchors =
        {
            (0f, 0.5f), (3f, 4.5f), (6f, 12.5f), (9f, 22.5f),
        };

        // 谱档→band 组合近似（起调值，全部 TBD-实机调值；量级指引见 sango/Docs/beaufort-water-mapping.md 调值指引节）
        static readonly float[] TierSwellWindFactor = { 0.35f, 1.00f, 0.90f, 1.10f }; // B3 uses the displayed wind, rather than suppressing it to 2.7 m/s.
        static readonly float[] TierBand0Mult       = { 0.15f, 0.70f, 0.75f, 0.90f };
        static readonly float[] TierBand1Mult       = { 0.10f, 0.45f, 0.65f, 0.85f };
        static readonly float[] TierRippleWindFactor = { 0.5f, 0.8f, 1.0f, 1.3f };    // ×风速 km/h → ripplesWindSpeed（钳 0..15）
        static readonly float[] TierRippleChaos     = { 0.60f, 0.70f, 0.80f, 0.90f };
        static readonly float[] TierFoamAmount      = { 0.00f, 0.10f, 0.25f, 0.45f }; // 白沫量
        static readonly string[] TierNames          = { "Calm", "Moderate", "Rough", "VeryRough" };

        void Update()
        {
            if (applyEveryFrame && Application.isPlaying)
            {
                AdvanceAtmosphereTransition(Time.deltaTime); // 档间 lerp 先行，Apply 消费动画后的当前值
                Apply();
            }
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
            ApplyAtmosphereExtras();
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
            if (!AtmosphereTransitioning) m_SpectrumCurrent = (float)spectrumTier;
            float t = float.IsNaN(m_SpectrumCurrent) ? (float)spectrumTier : m_SpectrumCurrent;
            float windKmh = windMs * 3.6f; // largeWindSpeed/ripplesWindSpeed 单位 km/h（见上注）

            waterSurface.largeWindSpeed = Mathf.Clamp(windKmh * TierValue(TierSwellWindFactor, t), 0f, 250f);
            waterSurface.largeBand0Multiplier = Mathf.Clamp01(TierValue(TierBand0Mult, t));
            waterSurface.largeBand1Multiplier = Mathf.Clamp01(TierValue(TierBand1Mult, t));
            waterSurface.largeOrientationValue = windDirectionDeg;
            waterSurface.largeChaos = Mathf.Lerp(0.9f, 0.5f, t / 3f); // 低风更单向，高风更散（起调值 TBD-实机）
            waterSurface.ripples = true;
            waterSurface.ripplesWindSpeed = Mathf.Clamp(windKmh * TierValue(TierRippleWindFactor, t), 0f, 15f);
            waterSurface.ripplesChaos = Mathf.Clamp01(TierValue(TierRippleChaos, t));
            waterSurface.ripplesOrientationValue = windDirectionDeg;
            waterSurface.foam = true;
            waterSurface.simulationFoamAmount = Mathf.Clamp01(TierValue(TierFoamAmount, t));
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
            // M7-B：sunDimFactor=1（晴档/默认）时与旧契约逐位一致；积雨云/雷暴档压直射
            sunLight.intensity = Mathf.Lerp(0.1f, 100000f, dayFactor * dayFactor) * sunDimFactor;
            // M9-2 夜间曝光地板：仰角 < 0 起 6° 暮光带线性渐入固定负补偿（曲线 NightGradeCore.
            // NightCompensationEv，ApplyAtmosphereExtras 消费）。根因：自动曝光（M6 profile
            // limitMax=14）把 0.1 lux 夜景 normalize 回中灰 = 评审"夜空不暗"；直射压暗会被
            // 逐帧直方图自适应抵消，负补偿 EV 移动直方图目标才留得住暗夜（同 M7-B 雷暴先例）。
            // 月光方向光不加：太阳夜间 0.1 lux 已是月光量级，再添方向光有双光源/双影风险（克制）。
            m_NightCompEv = NightGradeCore.NightCompensationEv(elevationDeg, k_NightEvFadeDeg, k_NightFloorEv);
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

        // ── M7-B 大气档附加杠杆：曝光补偿 + 雨 ────────────────────────────────────────
        // Exposure.compensation 是自动曝光（M6 profile Automatic 档）下的确定性压暗杠杆——
        // 直射太阳压暗（sunDimFactor）会被逐帧直方图自适应抵消，补偿 EV 移动直方图目标才留得住
        // 雷暴暗天观感。字段源码 PostProcessing/Components/Exposure.cs:46（FloatParameter）。
        void ApplyAtmosphereExtras()
        {
            if (globalVolume != null && globalVolume.profile.TryGet<Exposure>(out var exposure))
            {
                exposure.active = true;
                // .Override 口径（同雾参数注释）。M9-2：夜间地板补偿只在此处并入——白天
                // m_NightCompEv 恒 0（NightCompensationEv 仰角 ≥ 0 返 0f），跳过加法保证
                // compensation 写入值与旧契约逐位一致。
                float ev = exposureCompensationEv;
                if (m_NightCompEv != 0f) ev += m_NightCompEv;
                exposure.compensation.Override(ev);
            }
            if (rain != null) rain.SetRate(rainRate);
        }
    }
}
