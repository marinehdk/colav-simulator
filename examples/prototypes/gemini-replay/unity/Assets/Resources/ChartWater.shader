Shader "ColavPrototype/ChartWater" {
 Properties { _MainTex ("Recorded ENC", 2D) = "white" {} _ReplayTime ("Replay time", Float) = 0 }
 SubShader {
  Tags { "RenderType"="Opaque" }
  CGPROGRAM
  #pragma surface surf Standard
  sampler2D _MainTex;
  float _ReplayTime;
  struct Input { float2 uv_MainTex; float3 worldPos; };
  void surf(Input IN, inout SurfaceOutputStandard o) {
   fixed3 baseColor=tex2D(_MainTex,IN.uv_MainTex).rgb;
   float water=saturate((baseColor.b-baseColor.r)*5);
   float ripple=sin(IN.worldPos.x*.025+IN.worldPos.z*.018-_ReplayTime*.6)*sin(IN.worldPos.z*.033-_ReplayTime*.3);
   o.Albedo=baseColor*(.96+.025*ripple*water);
   o.Emission=baseColor*.12;
   o.Smoothness=.12+.12*water;
   o.Alpha=1;
  }
  ENDCG
 }
 Fallback "Diffuse"
}
