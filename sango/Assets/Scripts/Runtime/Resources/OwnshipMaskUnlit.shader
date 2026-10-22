// 路线A 本船掩膜真值通道专用（ownship-mask-v1.md §2）:白 unlit、无剔除无深度,
// 掩膜=本船全部表面像素并集(含自遮挡隐藏面,宁超集不漏)。只被
// TwinOwnshipMaskPublisher 经 CommandBuffer.DrawRenderer 使用,常规渲染不引用。
Shader "Sango/OwnshipMaskUnlit"
{
    SubShader
    {
        Pass
        {
            Cull Off
            ZWrite Off
            ZTest Always
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float4 vert(float4 vertex : POSITION) : SV_POSITION { return UnityObjectToClipPos(vertex); }
            fixed4 frag() : SV_TARGET { return fixed4(1, 1, 1, 1); }
            ENDCG
        }
    }
}
