// P3-S3 LiDAR point-cloud view (spec #90; twin-bridge-v1 sensor_mode=lidar).
// One shader, one pass (CustomPass fullscreen boilerplate = IrWhiteHot
// precedent, CustomPassCommon.hlsl): "Lidar Vision" — the stream camera's own
// depth field re-rendered as the 16-line point lattice over the deep-dark
// backdrop (正常网格暗化/隐藏，深色背景). Each screen cell unprojects its ray
// (stream camera transform + tan-half fov — plain component values), reads the
// range from CustomPassLoadCameraDepth (render-graph native, same camera),
// snaps it to the nearest VLP-16 elevation channel and paints the survey §2.3
// noise-shaded point (AWSIM distance/angle Gaussians, CARLA dropout +
// attenuation, 10 Hz seed). C# twin = Sango.Vessels.Mast.LidarPattern /
// LidarNoise (EditMode-tested; this shader stays a thin port).
//
// Rendering-path ledger (P3-S3 debugging): only fullscreen DrawProcedural(3,1)
// draws execute inside the render-graph custom pass on Metal (quad/mesh/
// SV_InstanceID draws stay invisible); all per-frame values ride as MATERIAL
// properties (Update-time shader globals do not bind); cross-camera RT
// sampling does not bind — hence the same-camera depth field. HDRP is
// camera-relative for its own constant buffers; the ray/point math here uses
// plain world-space component values instead.
Shader "Hidden/Sango/LidarPointCloud"
{
    HLSLINCLUDE

    #pragma target 4.5
    #pragma only_renderers d3d11 playstation xboxone xboxseries vulkan metal switch switch2

    #include "Packages/com.unity.render-pipelines.high-definition/Runtime/RenderPipeline/RenderPass/CustomPass/CustomPassCommon.hlsl"

    // Stream camera bundle (component values, LidarViewPass feeds per frame):
    float4x4 _RayCamLocalToWorld; // stream camera transform (ray direction -> world)
    float3 _RayCamPos;            // stream camera world position (ray origin)
    float4 _RayTanHalfFov;        // (tanHalfH, tanHalfV, 0, 0) of the stream raster
    float4 _LidarScreenSize;      // stream raster (w, h, 0, 0)

    // Scan pattern + noise table (C# twins: LidarPattern / LidarNoise).
    int _LidarChannelCount;       // 16
    float _LidarChannelSpanDeg;   // 30 (±15° band)
    float _LidarMaxRange;         // 100 m clip
    float _LidarPointSpacingPx;   // screen-space cell size (lattice pitch)
    float _LidarSeed;             // 10 Hz frame seed
    float _LidarRangeSigmaBase;
    float _LidarRangeSigmaRise;
    float _LidarAttenPerM;
    float _LidarDropRate;
    float _LidarDropLimit;
    float _LidarZeroIntensity;
    float4 _LidarRampHeights;     // (yMin, yMax, 0, 0)

    // ── hash / gaussian (GPU-only; C# statistics use System.Random mirrors) ──
    float LidarRand(uint index, uint salt)
    {
        uint h = index * 747796405u + 2891336453u * salt + asuint(_LidarSeed);
        h = (h >> ((h >> 28) + 4u)) ^ (h * 277803737u);
        h = (h >> 22) ^ h;
        return (h & 0x00FFFFFFu) / 16777216.0; // [0, 1)
    }

    float LidarGauss(uint index, uint salt)
    {
        float u1 = max(LidarRand(index, salt), 1e-6);
        float u2 = max(LidarRand(index, salt + 131u), 1e-6);
        return sqrt(-2.0 * log(u1)) * cos(6.2831853 * u2); // Box-Muller
    }

    // ── C# mirrors (LidarNoise) ──
    float LidarRangeSigma(float range) { return _LidarRangeSigmaBase + _LidarRangeSigmaRise * max(0.0, range); }

    float LidarIntensityFactor(float range) { return saturate(1.0 - _LidarAttenPerM * max(0.0, range)); }

    float3 LidarHeightRamp(float t)
    {
        t = saturate(t);
        float3 keys[5] =
        {
            float3(0.05, 0.10, 0.35),
            float3(0.00, 0.55, 0.55),
            float3(0.15, 0.75, 0.20),
            float3(0.90, 0.80, 0.10),
            float3(1.00, 1.00, 1.00),
        };
        float scaled = t * 4.0;
        int index = (int)min(floor(scaled), 3.0);
        return lerp(keys[index], keys[index + 1], scaled - index);
    }

    // Pass 0: the 16-line point lattice over the stream camera's depth field.
    float4 LidarPointsFragment(Varyings input) : SV_Target
    {
        UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);
        float2 pixel = input.positionCS.xy;
        float2 cellCenterPx = (floor(pixel / _LidarPointSpacingPx) + 0.5) * _LidarPointSpacingPx;
        float2 ndc = cellCenterPx / _LidarScreenSize.xy * 2.0 - 1.0;
        float3 dirCam = normalize(float3(ndc.x * _RayTanHalfFov.x, ndc.y * _RayTanHalfFov.y, 1.0));
        float3 rayDir = mul(_RayCamLocalToWorld, float4(dirCam, 0.0)).xyz; // world direction
        float rayLen = length(rayDir);
        float3 rayN = rayDir / max(rayLen, 1e-5);

        // Stream-camera depth along the cell ray (graph-native, same camera).
        float raw = CustomPassLoadCameraDepth(uint2(pixel));
        float range = min(LinearEyeDepth(raw, _ZBufferParams), _LidarMaxRange);
        if (range < 0.05 || range >= _LidarMaxRange)
            return float4(0.008, 0.012, 0.020, 1.0); // sky/beyond clip -> deep-dark backdrop

        // Snap to the nearest VLP-16 elevation channel (world-up approximation —
        // the ship's roll/pitch are small at sea; LidarPattern mirror).
        float elevationDeg = asin(clamp(rayN.y, -1.0, 1.0)) * 57.29578;
        float channelF = floor((elevationDeg + 0.5 * _LidarChannelSpanDeg) / (_LidarChannelSpanDeg / (float)_LidarChannelCount));
        bool inBand = channelF >= 0.0 && channelF < (float)_LidarChannelCount;
        // Lane duty: the point band occupies the middle of each channel's angular slot.
        float lanePhase = frac((elevationDeg + 0.5 * _LidarChannelSpanDeg) / (_LidarChannelSpanDeg / (float)_LidarChannelCount));
        bool inLane = inBand && lanePhase > 0.25 && lanePhase < 0.75;
        // Dot checker inside the lane (5 px cells).
        bool dotCell = ((uint(cellCenterPx.x) + uint(cellCenterPx.y)) & 1u) == 0u;
        if (!inLane || !dotCell)
            return float4(0.008, 0.012, 0.020, 1.0);

        uint pointId = (uint)max(channelF, 0.0) * 97u + (uint)(cellCenterPx.x / _LidarPointSpacingPx);

        // CARLA dropout 概率随距离.
        float intensity = LidarIntensityFactor(range);
        if (intensity < _LidarDropLimit && LidarRand(pointId, 3u) < _LidarDropRate)
            return float4(0.008, 0.012, 0.020, 1.0);

        // AWSIM distance Gaussian along the ray (noise re-seeds at 10 Hz).
        range += LidarRangeSigma(range) * LidarGauss(pointId, 5u);

        // Point world position (z-depth along the view axis -> world along the ray).
        float3 camForward = mul((float3x3)_RayCamLocalToWorld, float3(0.0, 0.0, 1.0));
        float alongFactor = range / max(dot(rayN, normalize(camForward)), 1e-4);
        float3 world = _RayCamPos + rayN * alongFactor;

        float t = saturate((world.y - _LidarRampHeights.x) / (_LidarRampHeights.y - _LidarRampHeights.x));
        float brightness = 0.35 + 0.65 * max(intensity, _LidarZeroIntensity); // LidarNoise.IntensityBrightness
        float shade = 1.0 - 0.35 * lanePhase;                                 // depth cue inside the lane
        return float4(LidarHeightRamp(t) * brightness * shade, 1.0);
    }

    ENDHLSL

    SubShader
    {
        Pass
        {
            Name "Lidar Points"

            Cull Off ZWrite Off ZTest Always

            HLSLPROGRAM
                #pragma vertex Vert
                #pragma fragment LidarPointsFragment
            ENDHLSL
        }
    }

    Fallback Off
}
