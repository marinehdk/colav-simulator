// P3-S2 IR white-hot view (spec #90; twin-bridge-v1 sensor_mode=ir), P2 IR
// realism round (survey docs/research/2026-10-19-sitaw-ir-latency-realism §4).
// Fullscreen Custom Pass shader = Boson-class thermal scope over the twin
// stream camera only (IrViewPass gates the camera; Demo mode never sees it):
//   #9  像元栅格化 — uv 量化到 640×512 + 轻模糊（衍射/MTF 软化近似）
//   #7  地平线冷天空渐变 + 掠射角海面降温（Graber：近地平线渐亮、海面向天温收敛）
//   #11 AGC 呼吸 — 场景均值（IrViewPass 侧 EMA 伺服，_IrAgcMean uniform 馈入）
//       → ±25% 缓变增益（热源进出画面整体亮度起伏）；无当帧逐像素求均值
//   #3  NETD 时域噪声 — hash(uv,t) 小幅"沸雪"（平滑区可见）
//   #4  FPN 固定图案噪声 — 静态像元 hash 微偏置 + 列条纹
//   #5  热源饱和白晕 — 排气/机舱档邻域 ring-max bloom 近似（探测器饱和溢出）
//   #1  极性 — _IrPolarity 0=白热 / 1=黑热（sensor_mode=ir_blackhot）
// Hot targets are tagged on the material side (IrTemperature tiers via
// ThermalTagApplier). Boilerplate = HDRP fullscreen custom pass shader
// (CustomPassCommon.hlsl). Pixel-coords sampling throughout: no UV flip
// ambiguity across platforms. AGC gain centres on unity (0.8-1.25 clamp) so
// the six P3-S2 temperature tiers stay separated through the ramp — the
// static gain itself is the tier calibration (IrViewPass.DefaultGain).
Shader "Hidden/Sango/IrWhiteHot"
{
    HLSLINCLUDE

    #pragma vertex Vert

    #pragma target 4.5
    #pragma only_renderers d3d11 playstation xboxone xboxseries vulkan metal switch switch2

    #include "Packages/com.unity.render-pipelines.high-definition/Runtime/RenderPipeline/RenderPass/CustomPass/CustomPassCommon.hlsl"

    // White-hot ramp parameters (C# twin: Sango.Vessels.Mast.IrTemperature.WhiteHot).
    float _IrGain;
    float _IrGamma;
    // P2 uniforms (C# feeder: IrViewPass.Execute).
    float _IrPolarity;    // 0 = white hot, 1 = black hot (§4 #1)
    float _IrTime;        // unscaled seconds — NETD temporal phase + AGC servo wobble
    float _IrHorizonY;    // horizon uv.y (0 bottom, 1 top; IrTemperature.HorizonScreenY)
    float _IrAgcTarget;   // scene pre-ramp mean the AGC servo homes in on
    float _IrAgcMean;     // EMA-smoothed scene mean (IrViewPass readback servo)
    float4 _IrSensorRes;  // (640, 512, 0, 0) Boson-class raster

    static const float3 kLuma = float3(0.2126, 0.7152, 0.0722);

    // Compact sin-free hash (Dave Hoskins) — stable at integer pixel magnitudes.
    float IrHash12(float2 p)
    {
        float3 p3 = frac(float3(p.xyx) * 0.1031);
        p3 += dot(p3, p3.yzx + 33.33);
        return frac((p3.x + p3.y) * p3.z);
    }

    float4 FullScreenPass(Varyings input) : SV_Target
    {
        UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

        float2 screenRes = _ScreenSize.xy;
        float2 sensorPx  = floor((input.positionCS.xy / screenRes) * _IrSensorRes.xy);
        float2 pxPerCell = screenRes / _IrSensorRes.xy;
        int2   basePx    = int2((sensorPx + 0.5) * pxPerCell); // quantized cell centre

        // #9 像元栅格化：量化 + 4 对角子 tap 轻模糊（细胞内反锯齿、格感保留）。
        int2 softPx = int2(round(pxPerCell * 0.25));
        float3 c = CustomPassLoadCameraColor(basePx + int2(-softPx.x, -softPx.y), 0).rgb
                 + CustomPassLoadCameraColor(basePx + int2( softPx.x, -softPx.y), 0).rgb
                 + CustomPassLoadCameraColor(basePx + int2(-softPx.x,  softPx.y), 0).rgb
                 + CustomPassLoadCameraColor(basePx + int2( softPx.x,  softPx.y), 0).rgb;
        float lum = dot(c * 0.25, kLuma);

        // #7 地平线热结构：地平线上方收敛到热天空（近地平线略暖→天顶冷，海天线渐变）；
        //    地平线下掠射角海面向冷天空反射收敛（海面贴地平线更冷）。Sky 口径对齐
        //    IrTemperature.SkyGray=0.05（白热语义：天空最冷最暗）。
        //    轴约定：_IrHorizonY 是 y-up uv（0=bottom，MastCameraTable.HorizonScreenY
        //    纯函数口径）；SV_Position 是光栅轴 y=0 在画面顶（core RP
        //    Common.hlsl GetFullScreenTriangleTexCoord 在 UNITY_UV_STARTS_AT_TOP 下
        //    翻 y 而 GetFullScreenTriangleVertexPosition 不翻）→ 先 1−y 转成 y-up 再比。
        float yUp = 1.0 - input.positionCS.y / screenRes.y;
        float above = yUp - _IrHorizonY;
        if (above > 0.0)
        {
            float grad = saturate(above * 4.0);
            float skyTemp = lerp(0.10, 0.05, grad);
            lum = lerp(lum, skyTemp, saturate(above * 10.0));
        }
        else
        {
            lum = lerp(lum * 0.75, lum, saturate(-above * 6.0));
        }

        // #11 AGC 呼吸：增益由 C# 侧伺服馈入的 EMA 场景均值（_IrAgcMean，τ≈0.8s，
        //    AsyncGPUReadback 16×9 降采样）决定，钳位 0.8-1.25 —— 以 1.0 为中心的
        //    ±25% 缓变呼吸（热源进出画面时整体亮度起伏），不做当帧逐像素均值（热源
        //    掩盖单 tap 会让增益一帧内跳变，TAA 抖动直进增益），也不把六档温度分层
        //    拉平成饱和白。0.7Hz 微摆模拟伺服 hunting。
        float agc = clamp(_IrAgcTarget / max(_IrAgcMean, 1e-3), 0.8, 1.25);
        agc *= 1.0 + 0.02 * sin(_IrTime * 0.7);

        // #3 NETD 时域噪声（温度域小幅"沸雪"）+ #4 FPN 固定图案（像元微偏置 + 列条纹）。
        float tPhase = frac(_IrTime * 0.617) * 613.0;
        float netd = (IrHash12(sensorPx + tPhase) - 0.5) * 0.030;
        float fpn  = (IrHash12(sensorPx * 0.987 + 17.31) - 0.5) * 0.015
                   + (IrHash12(float2(sensorPx.x * 0.311, 5.7)) - 0.5) * 0.012;

        float x = lum * agc * _IrGain + netd + fpn;

        // 白热 ramp（C# 镜像 IrTemperature.WhiteHot；静态增益 = 档位标定，agc 只在其
        // 上 ±25% 呼吸）。
        float white = pow(saturate(x), _IrGamma);

        // #5 热源饱和白晕：4 向 ring-max 邻域（总增益 ≤1.25×DefaultGain 标定）的饱和
        //    溢出近似 —— 排气/机舱档（gray≥0.85，×1.0 增益后 ≥0.85 触发）边缘发糊溢
        //    白；船体档（0.50×1.25=0.63）不触发。ring 采样按传感器 cell 量化（同一
        //    cell 内四邻居相同，硬件 cache 命中，逐像素实际 fetch 开销远低于名义 4 LOAD）。
        static const float2 kRing[4] =
        {
            float2( 1.0, 0.0), float2(-1.0, 0.0), float2(0.0,  1.0), float2(0.0, -1.0)
        };
        float ring = 0.0;
        [unroll] for (int k = 0; k < 4; k++)
        {
            float nl = dot(CustomPassLoadCameraColor(basePx + int2(kRing[k] * pxPerCell * 2.0), 0).rgb, kLuma);
            ring = max(ring, nl * agc * _IrGain);
        }
        white = saturate(white + smoothstep(0.85, 1.10, ring) * 0.45);

        // #1 极性：黑热 = 同一负像数据的反转显示映射（C# 镜像 IrTemperature.DisplayGray）。
        white = lerp(white, 1.0 - white, _IrPolarity);
        return float4(white.xxx, 1.0);
    }

    ENDHLSL

    SubShader
    {
        Pass
        {
            Name "Custom Pass 0"

            Cull Off ZWrite Off ZTest Always

            HLSLPROGRAM
                #pragma fragment FullScreenPass
            ENDHLSL
        }
    }

    Fallback Off
}
