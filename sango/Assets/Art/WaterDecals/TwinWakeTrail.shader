Shader "Sango/Water/TwinWakeTrail"
{
    Properties
    {
        _Seed("Foam pattern", Float) = 7.3
        _Bow("Bow interaction", Float) = 0
        _Region("Region metres", Vector) = (32,32,0,0)
        [HideInInspector] _AffectFoam("Affect Foam", Float) = 1
        [HideInInspector] _AffectDeformation("Affect Deformation", Float) = 1
    }
    SubShader
    {
        Tags { "RenderPipeline"="HDRenderPipeline" "ShaderGraphTargetId"="WaterDecalSubTarget" }
        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
        float _FlipY, _Seed, _Bow;
        float4 _Region;
        struct Varyings { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };
        Varyings Vert(uint id : SV_VertexID)
        {
            Varyings o;
            o.positionCS = GetFullScreenTriangleVertexPosition(id);
            o.uv = o.positionCS.xy * 0.5 + 0.5;
            #if UNITY_UV_STARTS_AT_TOP
            if (_FlipY < 0.5) o.uv.y = 1 - o.uv.y;
            #endif
            return o;
        }
        float Hash(float2 p) { return frac(sin(dot(p, float2(127.1,311.7)) + _Seed) * 43758.5453); }
        float Noise(float2 p)
        {
            float2 i = floor(p), f = frac(p); f = f*f*(3-2*f);
            return lerp(lerp(Hash(i), Hash(i+float2(1,0)), f.x),
                        lerp(Hash(i+float2(0,1)), Hash(i+1), f.x), f.y);
        }
        float EndFade(float y) { return 1-smoothstep(0.55, 1, abs(y)); }
        float2 BowProfile(float2 uv)
        {
            float aft = (1-uv.y)*_Region.y;
            float ridge = abs((uv.x-0.5)*_Region.x) - (0.6 + aft*0.45);
            float fade = smoothstep(0, 1.5, aft) * (1-smoothstep(_Region.y*0.65, _Region.y, aft));
            return float2(ridge,fade);
        }
        ENDHLSL
        Pass
        {
            Name "Foam"
            Cull Off ZTest Always ZWrite Off
            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            float4 Frag(Varyings i) : SV_Target
            {
                float2 p = i.uv*2-1;
                if (_Bow > 0.5)
                {
                    float2 bow = BowProfile(i.uv);
                    float crest = exp(-pow(bow.x/1.1, 2)) * bow.y;
                    float textureWeight = lerp(0.25,1,Noise(i.uv*float2(38,28)));
                    // A two-metre crest only covers a world-water pixel for about
                    // 0.25 s at cruise speed; compensate its short injection dwell.
                    return float4(0,crest*textureWeight*4,crest*0.5,0);
                }
                float swirl = (Noise(i.uv*float2(8,5))-0.5)*0.22;
                float center = exp(-pow((p.x+swirl)*5, 2));
                float ridge = exp(-pow((abs(p.x)-0.69)*20, 2));
                float pores = lerp(0.5,1,Noise(i.uv*float2(37,14)));
                float patches = lerp(0.65,1,Noise(i.uv*float2(13,7)));
                float foam = saturate((center + ridge*0.30) * pow(pores * patches, 0.8) * EndFade(p.y));
                // Pinned HDRP 17.3 atlas ABI: consumer reads .yz.
                return float4(0, foam, center*0.4*EndFade(p.y), 0);
            }
            ENDHLSL
        }
        Pass
        {
            Name "Deformation"
            Cull Off ZTest Always ZWrite Off
            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            float4 Frag(Varyings i) : SV_Target
            {
                float2 p = i.uv*2-1;
                if (_Bow > 0.5)
                {
                    float2 bow = BowProfile(i.uv);
                    float x = bow.x/1.35;
                    return float4((1-2*x*x)*exp(-x*x)*bow.y,0,0,0);
                }
                float x = (abs(p.x)-0.68)*15;
                float crest = (1-2*x*x)*exp(-x*x);
                return float4(crest*EndFade(p.y), 0, 0, 0);
            }
            ENDHLSL
        }
    }
}
