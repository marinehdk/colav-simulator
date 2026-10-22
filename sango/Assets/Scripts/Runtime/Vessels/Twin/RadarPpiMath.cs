using System;
using System.Collections.Generic;

namespace Sango
{
    /// <summary>CFAR 聚类检测(P2 独立 PPI 雷达屏产物;结构镜像后端 radar_video.py _detections:271-315)。</summary>
    public struct RadarPpiDetection
    {
        /// <summary>质心北向(米,会话 NE 域;行源 + 方位 × bin 距离的加权平均)。</summary>
        public double NorthM;

        /// <summary>质心东向(米)。</summary>
        public double EastM;

        /// <summary>簇内峰值线性功率(LUT 重建域)。</summary>
        public double PeakPower;

        /// <summary>10·log10(峰值/簇内平均门限)——后端 threshold_excess_db 同式。</summary>
        public double ExcessDb;

        /// <summary>簇内过门限单元数。</summary>
        public int CellCount;

        /// <summary>显示亮度 [0.08,1](web radar-ppi.js ppiIntensity:77-80 的 clamp((x)/18, 0.08, 1) 斜率)。</summary>
        public double Intensity => RadarPpiMath.IntensityFromExcessDb(ExcessDb);
    }

    /// <summary>
    /// 独立 PPI 雷达屏纯函数核心(00-REPORT §5/§6 P2;只读消费 P0 RadarSpokeStream 解码产物,
    /// spec 调研 docs/research/2026-10-21-unity-xband-radar/)。三源镜像钉死:
    /// - web web_gui/modules/radar-ppi.js:量程环 1/3·2/3·满(rangeRingsM:157-160)、
    ///   30° 刻度/90° 加长(draw:334-353)、扫掠相位(sweepAzimuthRad:83-86)、
    ///   blip 亮度/半径(intensity→ppiIntensity:77-80 + draw:374-375)、
    ///   VRM/EBL 显隐与角解算(draw:397-403)、HU/NU 旋转(rotation():251);
    /// - web web_gui/modules/radar-video.js raster():70-114:GAIN/SEA/RAIN 显示门限公式
    ///   (:97-98)、显示系→世界系旋转(:80-81)、行源平移双查(:82-91)、年龄门 1.1 圈(:96);
    /// - 后端 colav_simulator/core/radar_video.py:CA-CFAR 结构与 alpha 公式(ca_cfar:48-65)、
    ///   质心聚类/excess 公式(_detections:271-315)、u8 视频映射式(step:130)。
    /// Unity 屏与 web 屏逐 spoke 可对拍(00-REPORT §5 验收)——本类公式即对拍基准。
    /// 显式偏差面(记录在案,不视为缺陷):① CFAR 输入 = checkpoint u8 视频,经 256 档
    /// LUT 按 step:130 映射式逆回线性功率(后端在生成侧线性功率域运行,本侧消费侧重建
    /// 同一域);② 余辉"0.97/帧"(00-REPORT §5 底图层)按 60 fps 换算为 sim_time 年龄的
    /// 纯函数——帧率无关且可 EditMode 钉死。
    /// </summary>
    public static class RadarPpiMath
    {
        /// <summary>海里换算(米;web radar-ppi.js N_METERS_PER_NM:23)。</summary>
        public const double NmPerM = 1852.0;

        /// <summary>余辉每帧衰减系数(00-REPORT §5 底图层:spoke raster 余辉 0.97/帧)。</summary>
        public const double AfterglowDecayPerFrame = 0.97;

        /// <summary>"每帧"的帧率基准:衰减以 sim_time 年龄表达,0.97/帧@60fps(帧率无关换算)。</summary>
        public const double AfterglowReferenceFps = 60.0;

        /// <summary>余辉楔角宽(36°;web radar-ppi.js:329 arc(sweep−π/5, sweep) 同宽)。</summary>
        public const double WedgeSpanRad = Math.PI / 5.0;

        /// <summary>非 trails 年龄门(圈;web radar-video.js:96 age &gt; scanPeriodS*1.1 同系数)。</summary>
        public const double AgeGateRevolutions = 1.1;

        static readonly double[] s_VideoToPower = BuildVideoToPowerLut();

        /// <summary>角归一化到 [0,2π)(负角取正模;web (((x%1)+1)%1) 同语义的弧度版)。</summary>
        public static double WrapPositive(double angleRad)
            => angleRad - Math.Floor(angleRad / (2.0 * Math.PI)) * (2.0 * Math.PI);

        /// <summary>
        /// 量程环半径(米):{1/3, 2/3, 满}(web radar-ppi.js rangeRingsM:157-160 逐式;
        /// 非正量程回空数组同款守卫)。
        /// </summary>
        public static double[] RangeRingRadiiM(double scaleM)
            => scaleM > 0 ? new[] { scaleM / 3.0, 2.0 * scaleM / 3.0, scaleM } : Array.Empty<double>();

        /// <summary>30° 方位刻度是否 90° 整倍(0/90/180/270 加长;web radar-ppi.js:348 deg%90 同判)。</summary>
        public static bool IsCardinalTick(int bearingDeg) => bearingDeg % 90 == 0;

        /// <summary>
        /// 余辉衰减因子:0.97^(max(0,age)·60)。age 为该 spoke 采集时刻距当前 sim_time 的秒数
        /// ——同一 spoke 在任意渲染帧率下衰减一致(对拍确定性),年龄 0 = 全亮。
        /// </summary>
        public static double AfterglowDecay(double ageS)
            => Math.Pow(AfterglowDecayPerFrame, Math.Max(0.0, ageS) * AfterglowReferenceFps);

        /// <summary>
        /// GAIN/SEA/RAIN 显示门限(web radar-video.js:97-98 逐式镜像):
        /// value = clamp(u8 + gain·2 − (sea·0.6·e^(−range/1800) + rain·0.3), 0, 255)。
        /// sea 抑制随距离衰减(近程强),rain 恒定——错误设置可复现真实误操作(00-REPORT §5 控制行)。
        /// </summary>
        public static double VideoDisplayValue(byte sample, double gain, double sea, double rain, double rangeM)
            => Clamp(sample + gain * 2.0 - (sea * 0.6 * Math.Exp(-rangeM / 1800.0) + rain * 0.3), 0.0, 255.0);

        /// <summary>
        /// 显示系旋转角(rad):HU = 本船艏向,NU = 0(web radar-ppi.js rotation():251 逐式;
        /// CU/TM 为 backlog 不做)。显示系像素 → 世界系 = 本角的正向旋转(见 raster():80-81)。
        /// </summary>
        public static double DisplayRotationRad(bool headingUp, double headingRad) => headingUp ? headingRad : 0.0;

        /// <summary>
        /// EBL 显示角(rad,自屏上方顺时针):ebl 真方位 − 显示旋转(web radar-ppi.js:400
        /// bearing = eblDeg·π/180 − rotation() 逐式;wrap 到 [0,2π) 便于 UGUI 取向)。
        /// </summary>
        public static double EblDisplayAngleRad(double eblTrueDeg, double rotationRad)
            => WrapPositive(eblTrueDeg * Math.PI / 180.0 - rotationRad);

        /// <summary>VRM 显隐:0 &lt; vrm ≤ 量程(web radar-ppi.js:397 vrmNm&gt;0 &amp;&amp; ≤ rangeScaleNm 同判)。</summary>
        public static bool VrmVisible(double vrmNm, double scaleNm) => vrmNm > 0 && vrmNm <= scaleNm;

        /// <summary>VRM 环半径占比 = vrm/量程(web :399 radius·vrmNm/rangeScaleNm 同式;量程非正回 0)。</summary>
        public static double VrmRadiusFraction(double vrmNm, double scaleNm)
            => scaleNm > 0 ? vrmNm / scaleNm : 0.0;

        /// <summary>
        /// 扫描线显示角(rad,自屏上方顺时针):扫掠相位 − 显示旋转(web radar-ppi.js:322
        /// sweepCanvas = sweepAzRad − π/2 − rotation() 的罗盘角等价式;相位本体检
        /// RadarSpokeDecoder.SweepPhaseRad——sim_time/scan_period 纯函数,Unity/web 同钟同相)。
        /// </summary>
        public static double SweepDisplayAngleRad(double simTimeS, double scanPeriodS, double rotationRad)
            => WrapPositive(RadarSpokeDecoder.SweepPhaseRad(simTimeS, scanPeriodS) - rotationRad);

        /// <summary>
        /// blip 显示归一(world 相对 NE → 显示系再除量程;web radar-ppi.js:368-371 旋转式 +
        /// ppiProject:146-154 inside 判定逐式镜像)。显示系 up=displayNorth、right=displayEast;
        /// 返回 false = 出量程(隐藏,web projected.inside 同判)。
        /// </summary>
        public static bool BlipDisplayNormalized(double northRelM, double eastRelM, double scaleM,
            double rotationRad, out double displayNorth, out double displayEast)
        {
            double cos = Math.Cos(rotationRad), sin = Math.Sin(rotationRad);
            displayNorth = northRelM * cos + eastRelM * sin;
            displayEast = -northRelM * sin + eastRelM * cos;
            double fraction = scaleM > 0
                ? Math.Sqrt(northRelM * northRelM + eastRelM * eastRelM) / scaleM : 0.0;
            return fraction <= 1.0;
        }

        /// <summary>blip 亮度 [0.08,1]:clamp(excessDb/18, 0.08, 1)(web ppiIntensity:77-80 斜率/下限同值)。</summary>
        public static double IntensityFromExcessDb(double excessDb)
            => Clamp(excessDb / 18.0, 0.08, 1.0);

        /// <summary>
        /// u8 视频 → 线性功率(radar_video.py step:130 映射式 video=(10·log10(power)+10)·255/70
        /// 的逆:power = 10^((u8·70/255 − 10)/10);256 档 LUT 预计算——消费侧重建后端 CFAR 的
        /// 输入域,2M 单元无逐点 pow)。
        /// </summary>
        public static double LinearPower(byte sample) => s_VideoToPower[sample];

        static double[] BuildVideoToPowerLut()
        {
            var lut = new double[256];
            for (int v = 0; v < 256; v++)
                lut[v] = Math.Pow(10.0, (v * 70.0 / 255.0 - 10.0) / 10.0);
            return lut;
        }

        /// <summary>
        /// 逐行双侧距离 CA-CFAR(结构镜像 radar_video.py ca_cfar:48-65,输入换为 LUT 重建的
        /// 线性功率):前缀和训练窗噪声 → alpha·noise 门限 → power &gt; threshold 掩膜。
        /// alpha = 2·training·(pfa^(−1/(2·training)) − 1) 同式;边缘 bin(两侧余量
        /// margin = guard+training 内)无门限主张 = 恒 false/∞ 门限(numpy 同款)。
        /// 行区间 [rowStart,rowEnd) 切片处理——单帧预算保险(2M 单元分片,每片 O(bins))。
        /// mask/threshold 为 spokes×bins 行主序调用方缓冲(本调用只写切片行)。
        /// </summary>
        public static void CaCfarRows(byte[] video, int spokes, int bins, int rowStart, int rowEnd,
            double pfa, int guard, int training, bool[] mask, double[] threshold)
        {
            if (video == null || mask == null || threshold == null
                || spokes < 1 || bins < 1 || rowStart < 0 || rowEnd > spokes || rowStart >= rowEnd)
                throw new ArgumentOutOfRangeException(nameof(rowEnd), "invalid CA-CFAR slice");
            int margin = guard + training;
            double alpha = 2.0 * training * (Math.Pow(pfa, -1.0 / (2.0 * training)) - 1.0);
            var prefix = new double[bins + 1];
            for (int row = rowStart; row < rowEnd; row++)
            {
                int rowBase = row * bins;
                if (bins <= 2 * margin)
                {
                    // 窄栅格退化:全部无门限主张(后端 width<=2*margin 早退同语义)。
                    for (int i = 0; i < bins; i++) { mask[rowBase + i] = false; threshold[rowBase + i] = double.PositiveInfinity; }
                    continue;
                }
                prefix[0] = 0.0;
                for (int c = 0; c < bins; c++)
                    prefix[c + 1] = prefix[c] + LinearPower(video[rowBase + c]);
                for (int i = 0; i < bins; i++) { mask[rowBase + i] = false; threshold[rowBase + i] = double.PositiveInfinity; }
                for (int i = margin; i < bins - margin; i++)
                {
                    // 训练窗和(numpy 索引镜像:左 = pref[i−guard] − pref[i−guard−training],
                    // 右 = pref[i+guard+training+1] − pref[i+guard+1])
                    double left = prefix[i - guard] - prefix[i - guard - training];
                    double right = prefix[i + guard + training + 1] - prefix[i + guard + 1];
                    double noise = (left + right) / (2.0 * training);
                    double level = alpha * noise;
                    threshold[rowBase + i] = level;
                    mask[rowBase + i] = LinearPower(video[rowBase + i]) > level;
                }
            }
        }

        /// <summary>
        /// 掩膜 4-连通聚类 → 检测质心(镜像 radar_video.py _detections:271-315:scipy label
        /// 默认 4-连通(平面无回绕)、簇内功率加权质心、threshold_excess_db =
        /// 10·log10(峰值/平均门限)、超 cap 截断且总簇数照报)。质心投影 = 行源 +
        /// cos/sin(方位)·bin 中心距离(后端 :300 同式,方位取帧 row_bearings_rad,
        /// 缺失回退 row·2π/spokes)。mask 为消费即清的 scratch(调用后全 false);
        /// 行源缺失行按原点 0 处理(该行本无有效视频,与后端 origins 缺行跳过同效域)。
        /// </summary>
        public static int ClusterDetections(byte[] video, bool[] mask, double[] threshold, int spokes, int bins,
            double[][] rowOriginsNeM, double[] rowBearingsRad, double rangeM, int cap, List<RadarPpiDetection> results)
        {
            if (video == null || mask == null || results == null || spokes < 1 || bins < 1) return 0;
            bool hasBearings = rowBearingsRad != null && rowBearingsRad.Length == spokes;
            bool hasOrigins = rowOriginsNeM != null && rowOriginsNeM.Length == spokes;
            results.Clear();
            var cells = new List<int>(64);
            int found = 0;
            for (int row = 0; row < spokes; row++)
            {
                int rowBase = row * bins;
                for (int col = 0; col < bins; col++)
                {
                    int index = rowBase + col;
                    if (!mask[index]) continue;
                    // 就地淹没:掩膜即访问标记(不改簇形状,只防重入)
                    cells.Clear();
                    mask[index] = false;
                    cells.Add(index);
                    for (int k = 0; k < cells.Count; k++)
                    {
                        int cur = cells[k];
                        int r = cur / bins, c = cur % bins;
                        if (r > 0 && mask[cur - bins]) { mask[cur - bins] = false; cells.Add(cur - bins); }
                        if (r < spokes - 1 && mask[cur + bins]) { mask[cur + bins] = false; cells.Add(cur + bins); }
                        if (c > 0 && mask[cur - 1]) { mask[cur - 1] = false; cells.Add(cur - 1); }
                        if (c < bins - 1 && mask[cur + 1]) { mask[cur + 1] = false; cells.Add(cur + 1); }
                    }
                    double weightSum = 0.0, northSum = 0.0, eastSum = 0.0, peak = 0.0, thresholdSum = 0.0;
                    double bearing = hasBearings ? rowBearingsRad[row] : RadarSpokeDecoder.RowBearingRad(row, spokes);
                    double cosB = Math.Cos(bearing), sinB = Math.Sin(bearing);
                    double originN = hasOrigins && rowOriginsNeM[row] != null ? rowOriginsNeM[row][0] : 0.0;
                    double originE = hasOrigins && rowOriginsNeM[row] != null ? rowOriginsNeM[row][1] : 0.0;
                    foreach (int cur in cells)
                    {
                        int r = cur / bins, c = cur % bins;
                        double power = LinearPower(video[cur]);
                        double range = RadarSpokeDecoder.BinRangeM(c, bins, rangeM);
                        northSum += power * (originN + cosB * range);
                        eastSum += power * (originE + sinB * range);
                        weightSum += power;
                        if (power > peak) peak = power;
                        thresholdSum += threshold[cur];
                    }
                    double meanThreshold = thresholdSum / cells.Count;
                    found++;
                    if (results.Count >= cap) continue; // 超量照常清掩膜,不进结果(后端 break 截断同语义)
                    results.Add(new RadarPpiDetection
                    {
                        NorthM = weightSum > 0 ? northSum / weightSum : originN,
                        EastM = weightSum > 0 ? eastSum / weightSum : originE,
                        PeakPower = peak,
                        ExcessDb = 10.0 * Math.Log10(peak / Math.Max(meanThreshold, 1e-9)),
                        CellCount = cells.Count,
                    });
                }
            }
            return found;
        }

        static double Clamp(double value, double min, double max)
            => value < min ? min : value > max ? max : value;
    }
}
