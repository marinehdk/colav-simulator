using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// P1 3D 探测能力可视化纯函数（00-REPORT §4-1/2/3，2026-10-21；任务书④ EditMode 钉死面）。
    /// 服务三个表现层组件（Assembly-CSharp 侧 RadarSurfaceOverlay / RadarTargetMarkers /
    /// RadarBlindZones）——组件 glue（材质/订阅）不进测试，本类按 M2-E2 RadarMath 惯例
    /// 落 Sango.Vessels（EditMode asmdef 直引），全部 CPU 纯函数。三向锚点：
    /// raster 像素映射 = web radar-video.js raster()（RGB 0.2/1.0/0.5×v，行龄门
    /// age&gt;1.1×scan_period 剔除）；盲扇区判定 = 后端 sensing.py _bearing_blind
    /// （相对艏向、±180 wrap）；NE 投影 = RadarSpokeDecoder.ProjectBinToNe + TwinAnchor
    /// .ToLocal 组合（行源 row_origins_ne_m 语义同 web raster() 逐行平移）。
    /// </summary>
    public static class RadarOverlayMath
    {
        /// <summary>海里→米（后端 N_METERS_PER_NM，sensing.py:451 镜像）。</summary>
        public const float MetersPerNm = 1852f;

        /// <summary>盲环半径缺省（Halo24 口径 12 m 天线 / VBW 25° ⇒ R_min≈54 m；web clutterPoints 同缺省）。</summary>
        public const float BlindRingFallbackM = 54f;

        /// <summary>上一圈余辉基线（最新圈 1.0；任务书①"按圈龄衰减透明度"）。</summary>
        public const float PrevRevolutionAlpha = 0.45f;

        /// <summary>圈龄 → 余辉 alpha：最新圈 1、上一圈 0.45、更旧 0（ring 容量 2 之外无残像）。</summary>
        public static float RevolutionAlpha(int revolutionsOld)
            => revolutionsOld <= 0 ? 1f : revolutionsOld == 1 ? PrevRevolutionAlpha : 0f;

        /// <summary>u8 栅格值 → 强度 [0,1]（线性；GAIN/SEA/RAIN 档位属 P2 雷达屏）。</summary>
        public static float RasterIntensity(byte value) => value / 255f;

        /// <summary>
        /// u8 栅格值 → 纹理像素（radar-video.js raster() 同映射：R=0.2v G=v B=0.5v，
        /// 0..255 域直接换算）。alpha=v：黑（无回波）全透明、强回波不透明绿——
        /// 单色绿映射 + 强度即透明度，与 web 屏观感同构（逐 spoke 对拍面）。
        /// </summary>
        public static Color32 RasterPixel(byte value) =>
            new Color32((byte)(value * 0.2f), value, (byte)(value * 0.5f), value);

        /// <summary>
        /// 行新鲜度门（radar-video.js raster() 同判：age = max(0, tNow−tRow)，
        /// age &gt; 1.1×scan_period 的行不画——旧圈行数据不入新转纹理）。
        /// scanPeriod≤0 视为恒新鲜（无描述子时的降级）。
        /// </summary>
        public static bool RowFresh(double rowTimeS, double frameTimeS, double scanPeriodS)
        {
            if (!(scanPeriodS > 0)) return true;
            double age = Math.Max(0.0, frameTimeS - rowTimeS);
            return age <= scanPeriodS * 1.1;
        }

        /// <summary>
        /// 方位（rad，自北顺时针）→ 最近的 raster 行号（web raster() 同式：
        /// 正模 + floor；结果对 spokes 取模，2π 回卷到行 0）。
        /// </summary>
        public static int BearingRow(double bearingRad, int spokes)
        {
            if (spokes <= 0) return 0;
            double frac = ((bearingRad / (2.0 * Math.PI)) % 1.0 + 1.0) % 1.0;
            int row = (int)Math.Floor(frac * spokes);
            return row >= spokes ? spokes - 1 : row;
        }

        /// <summary>
        /// raster 极坐标采样 → 世界坐标（任务书④"raster bin→世界坐标投影"）：
        /// 行源 NE（该 spoke 采集时刻天线位）+ 方位/距离偏移 → 绝对 NE
        /// （RadarSpokeDecoder.ProjectBinToNe 同式）→ TwinAnchor.ToLocal 场景
        /// （east→x、north→z），y 贴水面抬升由调用方给（余辉盘 0.5 m）。
        /// 行源 null（checkpoint 缺 row_origins）时以锚点为本船位降级放置。
        /// </summary>
        public static Vector3 DiscVertexWorld(TwinAnchor anchor, double originNorthM, double originEastM,
            double bearingRad, double rangeM, float worldYM)
        {
            RadarSpokeDecoder.ProjectBinToNe(originNorthM, originEastM, bearingRad, rangeM,
                out double north, out double east);
            Vector2 local = anchor.ToLocal(east, north);
            return new Vector3(local.x, worldYM, local.y);
        }

        /// <summary>检测回波绝对 NE → 世界坐标（display_returns 投影，同锚定变换）。</summary>
        public static Vector3 ReturnWorldPosition(TwinAnchor anchor, double northM, double eastM, float worldYM)
        {
            Vector2 local = anchor.ToLocal(eastM, northM);
            return new Vector3(local.x, worldYM, local.y);
        }

        /// <summary>
        /// 最近船匹配：回波场景 XZ → 船列表最近者下标；全部超 maxMatchM（或空表）→ -1。
        /// 匹配半径由调用方定（目标船长/量程尺度），不脑补远亲。
        /// </summary>
        public static int NearestVesselIndex(Vector2 returnXz, Vector2[] vesselXz, float maxMatchM)
        {
            if (vesselXz == null || vesselXz.Length == 0) return -1;
            int best = -1;
            float bestSq = maxMatchM * maxMatchM;
            for (int i = 0; i < vesselXz.Length; i++)
            {
                float dx = vesselXz[i].x - returnXz.x, dz = vesselXz[i].y - returnXz.y;
                float distSq = dx * dx + dz * dz;
                if (distSq <= bestSq) { bestSq = distSq; best = i; }
            }
            return best;
        }

        /// <summary>检测标签文本（置信度 = 后端 RadarReturn.confidence = PD）。</summary>
        public static string MarkerLabelText(float confidence, float rangeM) =>
            $"RDR {confidence * 100f:0}% {rangeM:0}m";

        /// <summary>世界方位 → 相对艏向方位（度，0..360 wrap；sensing.py _bearing_blind 同域）。</summary>
        public static float BearingFromBowDeg(double worldBearingRad, double bowRad)
        {
            double delta = (worldBearingRad - bowRad) * Mathf.Rad2Deg;
            return (float)((delta % 360.0 + 360.0) % 360.0);
        }

        /// <summary>
        /// 盲扇区命中判定（sensing.py:939-946 _bearing_blind 逐语义镜像：
        /// relative = bearingFromBow − center；|wrap±180(relative)| ≤ halfWidth 即盲。
        /// 注意 C# % 对负数保号——先双正模再回中（Python 单 % 恒非负的语义等价）。
        /// </summary>
        public static bool BearingInSectorDeg(float bearingFromBowDeg, float centerRelBowDeg, float halfWidthDeg)
        {
            if (halfWidthDeg < 0f) return false;
            float relative = bearingFromBowDeg - centerRelBowDeg;
            float wrapped = (((relative + 180f) % 360f) + 360f) % 360f - 180f;
            return Math.Abs(wrapped) <= halfWidthDeg;
        }

        /// <summary>
        /// 扇楔本地顶点（ship frame：+z 艏 / +x 右舷，MastCameraTable 同约定）：
        /// 自艏顺时针方位 → (sin, 0, cos)·range（TwinPose.HeadingVector 同手性）。
        /// 挂在随艏向 yaw 的根节点下即得世界扇楔。
        /// </summary>
        public static Vector3 WedgeLocalPoint(float bearingFromBowDeg, float rangeM)
        {
            float rad = bearingFromBowDeg * Mathf.Deg2Rad;
            return new Vector3(Mathf.Sin(rad) * rangeM, 0f, Mathf.Cos(rad) * rangeM);
        }

        /// <summary>
        /// ppi 描述子 blind_sectors_deg（[[center_rel_bow_deg, half_width_deg],…]，
        /// sensing.py:1101）解析。JsonUtility 不支持嵌套数组，此处限定扫描器
        /// （RadarSpokeDecoder.ParseRowOrigins 同工艺）：键缺失返 null；严格
        /// [[数,数],…] 形状（容空白/科学计数法），畸形返 null 不部分产出。
        /// </summary>
        public static float[][] ParseBlindSectors(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            int key = json.IndexOf("\"blind_sectors_deg\"", StringComparison.Ordinal);
            if (key < 0) return null;
            int cursor = json.IndexOf('[', key + 19);
            if (cursor < 0) return null;
            cursor = SkipSpace(json, cursor + 1); // 进入外层 [
            if (cursor < json.Length && json[cursor] == ']') return new float[0][];
            var sectors = new List<float[]>();
            while (true)
            {
                if (cursor >= json.Length || json[cursor] != '[') return null;
                var pair = new float[2];
                for (int i = 0; i < 2; i++)
                {
                    if (i == 1) // 数间逗号
                    {
                        cursor = SkipSpace(json, cursor);
                        if (cursor >= json.Length || json[cursor] != ',') return null;
                    }
                    cursor = ScanNumber(json, SkipSpace(json, cursor + 1), out pair[i]);
                    if (cursor < 0) return null;
                }
                cursor = SkipSpace(json, cursor);
                if (cursor >= json.Length || json[cursor] != ']') return null;
                sectors.Add(pair);
                cursor = SkipSpace(json, cursor + 1);
                if (cursor >= json.Length) return null;
                if (json[cursor] == ']') return sectors.ToArray();
                if (json[cursor] != ',') return null;
                cursor = SkipSpace(json, cursor + 1);
            }
        }

        static int ScanNumber(string json, int index, out float value)
        {
            value = 0;
            if (index >= json.Length) return -1;
            int end = index;
            while (end < json.Length && (char.IsDigit(json[end]) || "+-.eE".IndexOf(json[end]) >= 0)) end++;
            return end > index && float.TryParse(json.Substring(index, end - index), NumberStyles.Float,
                CultureInfo.InvariantCulture, out value) ? end : -1;
        }

        static int SkipSpace(string json, int index)
        {
            while (index < json.Length && (json[index] == ' ' || json[index] == '\t'
                || json[index] == '\n' || json[index] == '\r'))
                index++;
            return index;
        }
    }

    /// <summary>
    /// 后端 RadarScanPacket.display_returns 单条回波的 Unity 子集（radar_scan.py:11-19；
    /// 协方差嵌套数组 JsonUtility 不支持，静默跳过——表现层只吃位置/时间/置信度）。
    /// confidence = RadarXBand PD（Swerling-0），north/east = 绝对 NE 米制。
    /// </summary>
    [Serializable]
    public class RadarDisplayReturn
    {
        public double north_m;
        public double east_m;
        public double t_s;
        public double snr_db;
        public float confidence;
    }

    /// <summary>
    /// ApplyScanJson 入口文档（radar_scans[*] 子集形状）。live 接线缝：RadarScanEntry
    /// （P0 DTO，RadarSpokeStream.cs）尚未声明 display_returns + compact 帧 radar_scans
    /// 键尚待 main.py 侧保留（tests/test_radar_transport.py:105-118 已记红）——两缝补齐后
    /// 由接线侧把 scan JSON 喂进 RadarTargetMarkers.ApplyScanJson（JsonUtility 在此解析）。
    /// </summary>
    [Serializable]
    public class RadarDisplayScanDocument
    {
        public RadarDisplayReturn[] display_returns;
    }
}
