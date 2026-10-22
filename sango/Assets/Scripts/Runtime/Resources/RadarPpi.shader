// 独立 PPI 雷达屏视频通道(00-REPORT §5/§6 P2):单 pass 极坐标→笛卡尔 blit。
// 输入 = P0 RadarSpokeStream 解码的 checkpoint 栅格(Texture2D R8,u=距离 bin、v=方位 row)
// + 行元数据纹理;逐式镜像 web radar-video.js raster():70-114——显示系→世界系旋转
// (HU/NU)、行源平移双查、年龄门 1.1 圈、GAIN/SEA/RAIN 门限;本屏增量 = 余辉衰减
// 0.97/帧@60fps(按 sim_time 年龄表达,RadarPpiMath.AfterglowDecay 同式)与扫描线/
// 余辉楔(radar-ppi.js draw:322-332 同角序)。只被 RadarPpiScreen 经 Graphics.Blit
// 使用,常规渲染不引用;放 Resources/ 保 player 构建可含(LidarViewPass 同工艺)。
Shader "Sango/Twin/RadarPpi"
{
    Properties
    {
        _MainTex ("Spoke raster (u=bin v=row)", 2D) = "black" {}
        _RowDelta ("Per-row own-minus-origin NE (RGFloat)", 2D) = "black" {}
        _RowTimes ("Per-row acquisition sim time (RFloat)", 2D) = "black" {}
        _Spokes ("Spokes per revolution", Float) = 2048
        _Bins ("Range bins", Float) = 1024
        _VideoRangeM ("Video range (m)", Float) = 1389
        _ScaleM ("Display range scale (m)", Float) = 1389
        _Rotation ("Display rotation rad (HU=heading, NU=0)", Float) = 0
        _SimTime ("Simulation time (s)", Float) = 0
        _ScanPeriod ("Scan period (s)", Float) = 2.5
        _Gain ("GAIN (web gain key)", Float) = 0
        _Sea ("SEA (web sea key)", Float) = 0
        _Rain ("RAIN (web rain key)", Float) = 0
        _SweepRad ("Sweep compass azimuth rad", Float) = 0
        _VideoValid ("Row metadata present (0/1)", Float) = 0
        _Accent ("Beam/accent colour", Color) = (0.224, 0.851, 0.541, 1)
        _Surface ("Disc surface colour", Color) = (0.016, 0.078, 0.059, 1)
    }
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

            sampler2D _MainTex;
            sampler2D _RowDelta;
            sampler2D _RowTimes;
            float _Spokes, _Bins, _VideoRangeM, _ScaleM, _Rotation, _SimTime, _ScanPeriod;
            float _Gain, _Sea, _Rain, _SweepRad, _VideoValid;
            float4 _Accent, _Surface;

            #define TWO_PI 6.28318530718

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            // Graphics.Blit 全屏 quad(appdata_img/UnityCG.cginc 惯例,uv 直通)
            v2f vert(appdata_img v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.texcoord;
                return o;
            }

            // 正模到 [0, 1)(web (((x % 1) + 1) % 1) 同语义)
            float posfrac(float x) { return x - floor(x); }

            // 罗盘方位角(自北顺时针,[0,2π)):atan2(东, 北) 再正模
            float compass(float north, float east) { return posfrac(atan2(east, north) / TWO_PI) * TWO_PI; }

            float4 frag(v2f i) : SV_Target
            {
                // 显示系局部 NE(NU:上=北/右=东;量程归一化同 web raster() localN/localE)
                float localN = (i.uv.y - 0.5) * 2.0 * _ScaleM;
                float localE = (i.uv.x - 0.5) * 2.0 * _ScaleM;
                float radius = length(float2(localN, localE));
                if (radius > _ScaleM)
                    return fixed4(0, 0, 0, 0); // 盘外透明(盘缘由刻度盘纹理绘制)

                // 底色(radar-ppi.js surface #04140F 同色)
                float4 outputColor = _Surface;

                if (_VideoValid > 0.5)
                {
                    // 显示系 → 世界系(raster():80-81:north = lN·cos − lE·sin;east = lN·sin + lE·cos)
                    float cosR = cos(_Rotation), sinR = sin(_Rotation);
                    float north = localN * cosR - localE * sinR;
                    float east = localN * sinR + localE * cosR;

                    // 行源平移双查(raster():82-91):行差纹理存 本船NE − 行源NE(CPU double 域
                    // 预算,防 7e6 级大数减法的 float 吞位);行时间 < 0 = 未采集 → 跳过该像素视频
                    float row0 = posfrac(atan2(east, north) / TWO_PI) * _Spokes;
                    float2 uvRow0 = float2((floor(row0) + 0.5) / _Spokes, 0.5);
                    float t0 = tex2D(_RowTimes, uvRow0).r;
                    float2 d0 = tex2D(_RowDelta, uvRow0).xy;
                    float rn = north + d0.x;
                    float re = east + d0.y;
                    float row1 = posfrac(atan2(re, rn) / TWO_PI) * _Spokes;
                    float2 uvRow1 = float2((floor(row1) + 0.5) / _Spokes, 0.5);
                    float t1 = tex2D(_RowTimes, uvRow1).r;
                    float2 d1 = tex2D(_RowDelta, uvRow1).xy;
                    rn = north + d1.x;
                    re = east + d1.y;

                    float range = length(float2(rn, re));
                    float binF = range / _VideoRangeM * _Bins;
                    float age = max(0.0, _SimTime - t1);
                    if (t1 >= 0.0 && binF >= 0.0 && binF < _Bins && age <= _ScanPeriod * 1.1)
                    {
                        // GAIN/SEA/RAIN 门限(raster():97-98 逐式)
                        float sample = tex2D(_MainTex, float2(binF / _Bins, (floor(row1) + 0.5) / _Spokes)).r * 255.0;
                        float suppression = _Sea * 0.6 * exp(-range / 1800.0) + _Rain * 0.3;
                        float value = clamp(sample + _Gain * 2.0 - suppression, 0.0, 255.0);
                        // 余辉 0.97/帧@60fps,按 sim_time 年龄(RadarPpiMath.AfterglowDecay 同式)
                        value *= pow(0.97, age * 60.0);
                        // 着色(raster():110 的 (0.2·v, v, 0.5·v)/255)
                        float v = value / 255.0;
                        float3 video = float3(v * 0.2, v, v * 0.5);
                        outputColor.rgb = max(outputColor.rgb, video);
                    }
                }

                // 余辉楔 + 扫描线(radar-ppi.js draw:322-332/405-411 同角序,显示系角):
                // 像素显示方位 azPix(自上顺时针);扫掠世界方位换到显示系 = _SweepRad − _Rotation;
                // behind = 扫线顺时针领先像素的角距 ∈ [0,2π)——楔覆盖 behind ∈ (0, 36°)。
                float azPix = compass(localN, localE);
                float behind = _SweepRad - _Rotation - azPix;
                behind -= floor(behind / TWO_PI) * TWO_PI;
                float wedge = saturate(1.0 - behind / 0.6283185); // π/5 = 36°
                float angDist = min(behind, TWO_PI - behind);
                float line = 1.0 - saturate(angDist / 0.004); // ~2px @512px 盘
                float glow = 0.35 * wedge + 0.85 * line * saturate(radius / (_ScaleM * 0.04));
                outputColor.rgb += _Accent.rgb * glow;
                outputColor.a = 1.0;
                return outputColor;
            }
            ENDCG
        }
    }
}
