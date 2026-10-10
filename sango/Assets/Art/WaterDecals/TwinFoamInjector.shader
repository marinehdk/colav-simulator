Shader "Sango/Water/TwinFoamInjector"
{
    Properties
    {
        [NoScaleOffset] _Foam_Texture("Surface (R) / Deep (G) Foam", 2D) = "black" {}
        [HideInInspector] _AffectFoam("Affect Foam", Float) = 1
        [HideInInspector] _AffectDeformation("Affect Deformation", Float) = 0
    }
    SubShader
    {
        Tags { "RenderPipeline"="HDRenderPipeline" "ShaderGraphTargetId"="WaterDecalSubTarget" }
        Pass
        {
            // HDRP 17.3 WaterSystem renders this pass into its RGBA decal atlas.
            Name "Foam"
            Cull Off
            ZTest Always
            ZWrite Off
            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
            TEXTURE2D(_Foam_Texture);
            SAMPLER(sampler_Foam_Texture);
            float _FlipY;
            struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };
            Varyings Vert(uint vertexID : SV_VertexID)
            {
                Varyings output;
                output.positionCS = GetFullScreenTriangleVertexPosition(vertexID);
                output.uv = output.positionCS.xy * 0.5 + 0.5;
                #if UNITY_UV_STARTS_AT_TOP
                if (_FlipY < 0.5) output.uv.y = 1 - output.uv.y;
                #endif
                return output;
            }
            float4 Frag(Varyings input) : SV_Target
            {
                float2 foam = saturate(SAMPLE_TEXTURE2D(_Foam_Texture, sampler_Foam_Texture, input.uv).rg);
                // WaterDecal.shader's FoamDecal pass consumes atlas.yz, not .xy.
                // Its ShaderGraph template currently writes float2 to .xy; adapt the ABI here.
                return float4(0, foam.x, foam.y, 0);
            }
            ENDHLSL
        }
    }
}
