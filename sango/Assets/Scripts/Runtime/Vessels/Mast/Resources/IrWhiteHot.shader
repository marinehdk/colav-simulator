// P3-S2 IR white-hot view (spec #90; twin-bridge-v1 sensor_mode=ir).
// Fullscreen Custom Pass shader: scene color -> luminance -> white-hot ramp
// (black-and-white thermal, simplified model per plan裁决 3 "IR=温度 tag+灰度
// ramp"). Hot targets are tagged on the material side (IrTemperature tiers via
// ThermalTagApplier); this pass is the grayscale scope applied to the twin
// stream camera only (IrViewPass gates the camera; Demo mode never sees it).
// Boilerplate = HDRP fullscreen custom pass shader (CustomPassCommon.hlsl,
// same shape as the package's CustomPassUtils.shader).
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

    float4 FullScreenPass(Varyings input) : SV_Target
    {
        UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

        // Pixel-coords sample: no UV flip ambiguity across platforms.
        float3 color = CustomPassLoadCameraColor(uint2(input.positionCS.xy), 0);
        float luminance = dot(color, float3(0.2126, 0.7152, 0.0722));
        float x = saturate(luminance * _IrGain);
        float white = pow(x, _IrGamma);
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
