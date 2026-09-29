using System;
using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M7-A 布景四要素纯函数集（EditMode 全覆盖；消费方 Sango.Editor.M7BackdropBuilder）。
    /// 组成：①EPSG:32648（UTM 48N / WGS84）经纬度 ↔ Unity 换算（Krüger/Snyder 横轴墨卡托
    /// 级数，逆投影不动点迭代——参考值由 pyproj 3.7 离线固化进 EditMode 测试）；
    /// ②陆/水掩膜纯函数（elev ≥ 0 = 陆上，构建期落位门禁的口径）；③A4 远景带滩涂/丛林
    /// 两段 splat 权重（逐海拔、归一化）；④A1 岸桥/箱堆布局字面量与生成器（确定性，无
    /// 运行时随机）；⑤A4 远景近岸线树卡散布规划器（双遍计数+哈希采样，确定性、上限封顶）；
    /// ⑥A3/A4 builder 管线数学（flatten 归一化映射 / alphamap→高度图最近格 / TreeInstance
    /// 归一化——M7 review A11 抽出单点真值，builder 与 fresh EditMode 测试共用）。
    /// 坐标约定与 M6TerrainMath 一致：manifest center_utm = Unity 原点，+X=东、+Z=北、海面 y=0。
    /// </summary>
    public static class M7BackdropMath
    {
        // ── 预算护栏常量（任务护栏字面量化，EditMode 钉死）────────────────────────────
        /// <summary>岸桥总数上限（任务：12-16 台沿两处码头线排）。</summary>
        public const int MinQuayCranesTotal = 12;
        public const int MaxQuayCranesTotal = 16;
        /// <summary>树实例总上限（GPU instancing 走 Terrain 引擎树管线，无每帧分配）。</summary>
        public const int MaxTreeInstances = 4000;
        /// <summary>单远景 tile 树卡上限（活跃远景 tile ≤16 → 总数 ≤3520）。</summary>
        public const int MaxTreesPerFarTile = 220;
        /// <summary>新增 Assets 体积预算（字节）。</summary>
        public const long NewAssetsBudgetBytes = 60L * 1024 * 1024;
        /// <summary>箱堆色板档数（任务：5-6 色随机板）。</summary>
        public const int ContainerColorCount = 6;
        public const int YardBlocksPerTerminal = 4; // 任务：3-5 block
        public const int YardColsPerBlock = 12;     // 任务：10-20 列
        public const int YardRowsDeep = 5;
        public const int YardLayersMin = 3;         // 任务：堆高 3-5 层
        public const int YardLayersMax = 5;
        /// <summary>构建期陆上落位门禁：所有水上落位（岸桥/箱堆/平台角点）高程 ≥ 此值。</summary>
        public const float LandGateMinElevationM = 0f;

        // ── ① EPSG:32648（UTM 48N / WGS84）横轴墨卡托（Snyder 级数；中心经线 105°E）──

        const double k_SemiMajor = 6378137.0;
        const double k_Flattening = 1.0 / 298.257223563;
        const double k_ScaleFactor = 0.9996;
        const double k_FalseEasting = 500000.0;
        const double k_CentralMeridianDeg = 105.0;

        static double EccentricitySquared => k_Flattening * (2.0 - k_Flattening);

        /// <summary>经纬度（度）→ UTM 48N（米，[E, N]）。与 pyproj/EPSG:32648 对齐（mm 级）。</summary>
        public static Vector2 LatLonToUtm(double latDeg, double lonDeg)
        {
            double e2 = EccentricitySquared;
            double ep2 = e2 / (1.0 - e2);
            double a = k_SemiMajor;

            double phi = latDeg * Math.PI / 180.0;
            double dLon = (lonDeg - k_CentralMeridianDeg) * Math.PI / 180.0;
            // dLon 归一到 [-π, π)（跨反经线不进入本区域，但保持稳健）
            dLon = Math.IEEERemainder(dLon, 2.0 * Math.PI);

            double sinPhi = Math.Sin(phi), cosPhi = Math.Cos(phi), tanPhi = Math.Tan(phi);
            double t = tanPhi * tanPhi;
            double c = ep2 * cosPhi * cosPhi;
            double n = a / Math.Sqrt(1.0 - e2 * sinPhi * sinPhi);

            // 子午线弧长 M（自赤道；UTM φ0=0）
            double arc = a * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * e2 * e2 * e2 / 256.0);
            double m = arc * (phi
                - (3.0 * e2 / 8.0 + 3.0 * e2 * e2 / 16.0 + 213.0 * e2 * e2 * e2 / 2048.0) * Math.Sin(2.0 * phi)
                + (15.0 * e2 * e2 / 256.0 + 45.0 * e2 * e2 * e2 / 1024.0) * Math.Sin(4.0 * phi)
                - (35.0 * e2 * e2 * e2 / 3072.0) * Math.Sin(6.0 * phi));

            // Snyder 8-9/8-11 标准级数：级数变量 A = dλ·cosφ（漏乘 cosφ 在 1.3° 处 ~33 m 偏差，
            // EditMode pyproj 钉值测试首跑红抓出）
            double aa = dLon * cosPhi;
            double x = k_FalseEasting + k_ScaleFactor * n * (aa
                + (1.0 - t + c) * aa * aa * aa / 6.0
                + (5.0 - 18.0 * t + t * t + 72.0 * c - 58.0 * ep2) * aa * aa * aa * aa * aa / 120.0);
            double y = k_ScaleFactor * (m + n * tanPhi * (aa * aa / 2.0
                + (5.0 - t + 9.0 * c + 4.0 * c * c) * aa * aa * aa * aa / 24.0
                + (61.0 - 58.0 * t + t * t + 600.0 * c - 330.0 * ep2) * aa * aa * aa * aa * aa * aa / 720.0));

            return new Vector2((float)x, (float)y);
        }

        /// <summary>UTM 48N（米）→ 经纬度（度）。反投影标准迭代（footpoint 级数，一步收敛 mm 级）。</summary>
        public static (double latDeg, double lonDeg) UtmToLatLon(double eastingM, double northingM)
        {
            double e2 = EccentricitySquared;
            double ep2 = e2 / (1.0 - e2);
            double a = k_SemiMajor;

            double x = eastingM - k_FalseEasting;
            double m = northingM / k_ScaleFactor;

            double A = a * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * e2 * e2 * e2 / 256.0);
            double mu = m / A;
            double e1 = (1.0 - Math.Sqrt(1.0 - e2)) / (1.0 + Math.Sqrt(1.0 - e2));

            double phi1 = mu
                + (3.0 * e1 / 2.0 - 27.0 * e1 * e1 * e1 / 32.0) * Math.Sin(2.0 * mu)
                + (21.0 * e1 * e1 / 16.0 - 55.0 * e1 * e1 * e1 * e1 / 32.0) * Math.Sin(4.0 * mu)
                + (151.0 * e1 * e1 * e1 / 96.0) * Math.Sin(6.0 * mu)
                + (1097.0 * e1 * e1 * e1 * e1 / 512.0) * Math.Sin(8.0 * mu);

            double sinPhi1 = Math.Sin(phi1), cosPhi1 = Math.Cos(phi1), tanPhi1 = Math.Tan(phi1);
            double t1 = tanPhi1 * tanPhi1;
            double c1 = ep2 * cosPhi1 * cosPhi1;
            double n1 = a / Math.Sqrt(1.0 - e2 * sinPhi1 * sinPhi1);
            double r1 = a * (1.0 - e2) / Math.Pow(1.0 - e2 * sinPhi1 * sinPhi1, 1.5);
            double d = x / (n1 * k_ScaleFactor);

            double phi = phi1 - (n1 * tanPhi1 / r1) * (d * d / 2.0
                - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1 * c1 - 9.0 * ep2) * d * d * d * d / 24.0
                + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1 * t1 - 252.0 * ep2 - 3.0 * c1 * c1)
                    * d * d * d * d * d * d / 720.0);
            double lon = k_CentralMeridianDeg * Math.PI / 180.0 + (d
                - (1.0 + 2.0 * t1 + c1) * d * d * d / 6.0
                + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1 * c1 + 8.0 * ep2 + 24.0 * t1 * t1)
                    * d * d * d * d * d / 120.0) / cosPhi1;

            return (phi * 180.0 / Math.PI, lon * 180.0 / Math.PI);
        }

        /// <summary>经纬度（度）→ Unity 世界 (x=东, z=北)：UTM − 区域中心（manifest center_utm）。</summary>
        public static Vector2 LatLonToUnity(double latDeg, double lonDeg, Vector2 centerUtm)
        {
            var utm = LatLonToUtm(latDeg, lonDeg);
            return new Vector2(utm.x - centerUtm.x, utm.y - centerUtm.y);
        }

        /// <summary>Unity 世界 (x, z) → 经纬度（度）。LatLonToUnity 的精确逆。</summary>
        public static (double latDeg, double lonDeg) UnityToLatLon(float x, float z, Vector2 centerUtm)
            => UtmToLatLon(x + centerUtm.x, z + centerUtm.y);

        // ── A2 真实锚地槽位（M7-A 2026-09-29）───────────────────────────────────────
        // 东锚地（Eastern OPL ≈1.21N 103.90E）+ 西南锚地（≈1.17N 103.71E 一带，开阔水域）。
        // 离线对 tmp/m6-data RAW 实采选点（tmp/m7a site analysis，pyproj EPSG:32648 换算）；
        // S2 底图（2026-03-20）锚泊船点群纹理核对（两区均见锚泊船）。全槽含 300 m 大船
        // ±175 m 角点盒最浅 −23.7 m（构建期 depth gate：&lt; −5 m 复验）。朝向 = 字面量随机档。
        public static readonly AnchorageSlot[] StraitAnchorageSlots =
        {
            // 东锚地（S2 可见锚泊船群带；距主航道北缘 ~3 km 开阔水域）
            new AnchorageSlot(VesselClass.Tug,             new Vector2(10136f,  -7751f),  35f),
            new AnchorageSlot(VesselClass.FishingTrawler,  new Vector2(10733f,  -7791f), 115f),
            new AnchorageSlot(VesselClass.CargoContainer,  new Vector2(10100f,  -8361f),  70f),
            new AnchorageSlot(VesselClass.TankerLng,       new Vector2(10832f,  -8502f), 155f),
            new AnchorageSlot(VesselClass.Tanker,          new Vector2(11432f,  -8366f),  20f),
            new AnchorageSlot(VesselClass.CargoGeneral,    new Vector2(12070f,  -8377f), 100f),
            // 西南锚地（Selat Panjang 以西开阔水域）
            new AnchorageSlot(VesselClass.FcbPc3,          new Vector2(-10976f, -12131f),  40f),
            new AnchorageSlot(VesselClass.Tug,             new Vector2(-10398f, -12155f), 130f),
            new AnchorageSlot(VesselClass.Tanker,          new Vector2(-11148f, -12857f),  80f),
            new AnchorageSlot(VesselClass.TankerLng,       new Vector2(-10349f, -12956f), 160f),
            new AnchorageSlot(VesselClass.CargoContainer,  new Vector2(-9744f,  -12767f),  25f),
            new AnchorageSlot(VesselClass.CargoGeneral,    new Vector2(-9060f,  -12935f),  95f),
        };

        /// <summary>锚地水深离线验证值（上表逐槽最浅角点盒高程，米；site analysis 2026-09-29）。
        /// 供 EditMode 参考断言：构建期 gate（Terrain.SampleHeight 实采）才是权威。</summary>
        public const float AnchorageOfflineWorstShallowM = -23.7f;

        // ── ② 陆/水掩膜（构建期落位门禁口径）────────────────────────────────────────

        /// <summary>陆上掩膜：海面 y=0 口径下 elev ≥ 0 为陆上（岸桥/箱堆落位硬门）。</summary>
        public static bool IsLand(float elevationM) => elevationM >= 0f;

        /// <summary>陆上落位验证（fail-fast，与 M6TerrainMath.ValidateDepths 同款报告语义）：
        /// 所有点高程 ≥ minElevationM；失败时定位首个违规点，成功时 lowest* = 全局最低。
        /// （M7 review A10：移除置位后无消费方的 samples 死字段——报告只暴露实际被读的
        /// ok/worstPoint/worstElevationM，避免照抄 DepthReport 的口径漂移。）</summary>
        public struct LandReport
        {
            public bool ok;
            public float worstElevationM;    // 失败 = 首个违规点高程；成功 = 全局最低高程
            public Vector2 worstPoint;
        }

        public static LandReport ValidateDryLand(M6TerrainMath.ElevationSampler sample, Vector2[] points, float minElevationM = LandGateMinElevationM)
        {
            var report = new LandReport { ok = true, worstElevationM = float.MaxValue };
            foreach (var p in points)
            {
                float e = sample(p);
                if (e < minElevationM)
                {
                    report.ok = false;
                    report.worstElevationM = e;
                    report.worstPoint = p;
                    return report; // fail fast：首个违规即停，报违规点本身
                }
                if (e < report.worstElevationM) { report.worstElevationM = e; report.worstPoint = p; }
            }
            return report;
        }

        // ── ③ A4 远景带 splat 权重（滩涂 0-4 m / 丛林 >4 m，逐海拔、归一化）──────────

        /// <summary>
        /// 远景带三层权重（基带 S2 底图 / 泥绿滩涂 / 深绿丛林）：elev &lt; 0 = 纯基带（海床不动）；
        /// 0-4 m 滩涂带（0.5 m 处峰值 0.5，4 m 归零）；&gt;4 m 丛林带（4-10 m 线性升至 0.65 封顶）。
        /// 输出恒归一化（sum = 1）。确定性纯函数。
        /// </summary>
        public static (float baseWeight, float mudWeight, float jungleWeight) SplatWeights(float elevationM)
        {
            float mud = 0f, jungle = 0f;
            if (elevationM > 0f && elevationM < 4f)
            {
                float rise = Mathf.Clamp01(elevationM / 0.5f);          // 0 → 0.5 m 起坡
                float fall = 1f - Mathf.Clamp01((elevationM - 1.5f) / 2.5f); // 1.5 → 4 m 收坡
                mud = 0.5f * rise * fall;
            }
            if (elevationM > 4f)
                jungle = 0.65f * Mathf.Clamp01((elevationM - 4f) / 6f); // 4 → 10 m 线性封顶

            float baseW = Mathf.Max(0f, 1f - mud - jungle);
            // 数值再归一（恒 sum=1，防浮点漂移出 alphamap 断言）
            float sum = baseW + mud + jungle;
            return (baseW / sum, mud / sum, jungle / sum);
        }

        // ── ④ A1 岸桥/箱堆布局字面量与生成器（确定性）────────────────────────────────

        /// <summary>一处集装箱码头布局：岸桥沿码头线（起点→终点）排布，箱堆在陆侧。
        /// 全部 Unity 坐标（x=东, z=北）；落位 provenance：S2 底图（2026-03-20）对齐
        /// + DEM 高程核查（2026-09-29，M7-A site analysis；详见提交说明）。</summary>
        public struct TerminalLayout
        {
            public string name;              // 显示名（GO 命名/日志）
            public Vector2 quayStart;        // 码头线起点（西/南端）
            public Vector2 quayEnd;          // 码头线终点（东/北端）
            public int craneCount;           // 岸桥台数（沿线等距）
            public float[] flattenRectUnity; // A3 小块平整矩形 [xmin, zmin, xmax, zmax]（Unity 米）
            public float flattenTargetM;     // 平整目标高程（码头面 +2 m）
            public string tileName;          // 承载 tile（高度图/SetHeights 目标）
        }

        /// <summary>
        /// Pasir Panjang 码头（S2: 集装箱泊位西缘岸桥线；tile near_r1c0，5.86 m/px）。
        /// DEM 实测：S2 泊位平台在 DEM 中为 0 m 平台（GLO-30 期次早于 S2 2026-03），
        /// A3 小块平整至 +2 m 后落位（岸桥落点 ≥ 0 硬门 + 码头前沿贴 0 水线）。
        /// </summary>
        public static readonly TerminalLayout PasirPanjang = new TerminalLayout
        {
            name = "PasirPanjang",
            // start→end 取向使右旋 90°（+Z→切向系下的 +X）= 海侧（西）；网格局部系依赖此约定
            quayStart = new Vector2(-2380f, -1000f),
            quayEnd = new Vector2(-2290f, -2350f),
            craneCount = 8,
            flattenRectUnity = new[] { -2650f, -2600f, -1250f, -700f },
            flattenTargetM = 2f,
            tileName = "near_r1c0_2049",
        };

        /// <summary>
        /// Tuas 码头西泊位（S2: 大型集装箱泊位南缘岸桥线；tile far_r2c0，23.4 m/px；
        /// 东侧相邻 tile far_r2c1 被 M6 覆盖语义隐藏，故只取活跃 tile 内的西泊位段）。
        /// DEM 实测：S2 泊位在 DEM 中为水域（同上期次差），A3 平整至 +2 m 后落位。
        /// </summary>
        public static readonly TerminalLayout TuasPier = new TerminalLayout
        {
            name = "TuasPier",
            quayStart = new Vector2(-20300f, -2950f),
            quayEnd = new Vector2(-18200f, -3250f),
            craneCount = 8,
            flattenRectUnity = new[] { -20400f, -3350f, -17900f, -2700f },
            flattenTargetM = 2f,
            tileName = "far_r2c0_513",
        };

        public static readonly TerminalLayout[] Terminals = { PasirPanjang, TuasPier };

        public static int TotalCraneCount
        {
            get
            {
                int sum = 0;
                foreach (var t in Terminals) sum += t.craneCount;
                return sum;
            }
        }

        /// <summary>码头线切向（单位化，start→end）。</summary>
        public static Vector2 QuayTangent(TerminalLayout t)
            => (t.quayEnd - t.quayStart).normalized;

        /// <summary>码头线海侧法向（单位化；切向右旋 90°：n = (t.z, −t.x)——
        /// 两处布局字面量均满足水域在此侧，EditMode 由布局自检测试钉住）。</summary>
        public static Vector2 QuaySeawardNormal(TerminalLayout t)
        {
            var tan = QuayTangent(t);
            return new Vector2(tan.y, -tan.x);
        }

        /// <summary>岸桥沿线等距落位（count 台，含两端）。</summary>
        public static Vector2[] CranePositions(TerminalLayout t)
        {
            var pts = new Vector2[t.craneCount];
            for (int i = 0; i < t.craneCount; i++)
            {
                float s = t.craneCount == 1 ? 0f : i / (float)(t.craneCount - 1);
                pts[i] = Vector2.Lerp(t.quayStart, t.quayEnd, s);
            }
            return pts;
        }

        /// <summary>落位点是否在矩形（[xmin,zmin,xmax,zmax]）内（含边界，1 m 容差）。</summary>
        public static bool InRect(Vector2 p, float[] rect)
            => p.x >= rect[0] - 1f && p.y >= rect[1] - 1f && p.x <= rect[2] + 1f && p.y <= rect[3] + 1f;

        /// <summary>落位点是否在 tile 内（tile 西南角 origin + 12 km 边长；2 m 容差）。</summary>
        public static bool InTile(Vector2 p, Vector2 tileOriginXZ, float tileMeters)
            => p.x >= tileOriginXZ.x - 2f && p.y >= tileOriginXZ.y - 2f
                && p.x <= tileOriginXZ.x + tileMeters + 2f && p.y <= tileOriginXZ.y + tileMeters + 2f;

        // ── 箱堆生成（确定性哈希取色/层数，无运行时随机）────────────────────────────

        /// <summary>单个集装箱（等比长方体）参数。</summary>
        public struct ContainerBox
        {
            public Vector3 center;   // 世界 XZY（y = 相对码头面抬升）
            public Vector3 size;
            public int colorIndex;   // [0, ContainerColorCount)
        }

        // 40 ft 标准箱等比：12.2 × 2.6 × 2.8 m（长×宽×高），留吊装间隙
        public const float BoxLengthM = 12.2f;
        public const float BoxWidthM = 2.6f;
        public const float BoxHeightM = 2.8f;
        const float k_AlongGapM = 1.6f;
        const float k_AcrossGapM = 1.0f;
        /// <summary>箱底相对码头面抬升（平接触视觉留缝）。</summary>
        public const float YardBaseLiftM = 0.15f;

        /// <summary>确定性哈希（无状态；同输入逐位同输出）。</summary>
        public static uint Hash(int a, int b, int c)
        {
            uint h = (uint)(a * 73856093) ^ (uint)(b * 19349663) ^ (uint)(c * 83492791);
            h ^= h >> 13; h *= 0x5bd1e995u; h ^= h >> 15;
            return h;
        }

        /// <summary>堆叠层数：3-5 层（任务档），哈希决定。</summary>
        public static int LayersFor(int block, int col, int row)
            => YardLayersMin + (int)(Hash(block, col, row) % (uint)(YardLayersMax - YardLayersMin + 1));

        /// <summary>色板档：0-5（6 色），哈希决定。</summary>
        public static int ColorIndexFor(int block, int col, int row, int layer)
            => (int)(Hash(block + 101, col, row * 7 + layer) % (uint)ContainerColorCount);

        /// <summary>箱堆生成（终端局部系核心）：原点 = quayStart，+Z = 切向，+X = 海侧法向；
        /// 沿码头线陆侧布置 YardBlocksPerTerminal 个 block（列沿切向、行深向陆），逐箱参数
        /// 确定性（哈希取层数/色板，无随机状态）。y = 相对码头面（平整平台）的局部抬升。</summary>
        public static List<ContainerBox> GenerateYardLocal(TerminalLayout t)
        {
            var boxes = new List<ContainerBox>();
            float alongStep = BoxLengthM + k_AlongGapM;   // 列间距（沿切向）
            float acrossStep = BoxWidthM + k_AcrossGapM;  // 行间距（沿法向）
            float blockLength = YardColsPerBlock * alongStep - k_AlongGapM;
            float blockDepth = YardRowsDeep * acrossStep - k_AcrossGapM;
            float lineLength = Vector2.Distance(t.quayStart, t.quayEnd);

            for (int b = 0; b < YardBlocksPerTerminal; b++)
            {
                float alongC = (b + 0.5f) / YardBlocksPerTerminal * lineLength; // block 中心弧长位
                float acrossC = YardInlandOffsetM + blockDepth * 0.5f;          // block 中心陆侧距离
                for (int col = 0; col < YardColsPerBlock; col++)
                {
                    float along = alongC + (col + 0.5f) * alongStep - blockLength * 0.5f;
                    for (int row = 0; row < YardRowsDeep; row++)
                    {
                        float across = acrossC + (row + 0.5f) * acrossStep - blockDepth * 0.5f;
                        int layers = LayersFor(b, col, row);
                        for (int layer = 0; layer < layers; layer++)
                        {
                            boxes.Add(new ContainerBox
                            {
                                center = new Vector3(-across, YardBaseLiftM + layer * BoxHeightM + BoxHeightM * 0.5f, along),
                                size = new Vector3(BoxWidthM, BoxHeightM, BoxLengthM),
                                colorIndex = ColorIndexFor(b, col, row, layer),
                            });
                        }
                    }
                }
            }
            return boxes;
        }

        /// <summary>箱堆生成（世界系）：GenerateYardLocal 的旋平变换（+Z→切向、+X→海侧法向、
        /// 原点=quayStart）。供落位门禁（world 实采高程）消费。</summary>
        public static List<ContainerBox> GenerateYard(TerminalLayout t)
        {
            var tan = QuayTangent(t);
            var seaward = QuaySeawardNormal(t);
            var result = new List<ContainerBox>();
            foreach (var b in GenerateYardLocal(t))
            {
                var flat = t.quayStart + seaward * b.center.x + tan * b.center.z;
                result.Add(new ContainerBox
                {
                    center = new Vector3(flat.x, b.center.y, flat.y),
                    size = b.size,
                    colorIndex = b.colorIndex,
                });
            }
            return result;
        }

    /// <summary>箱堆陆侧偏移（码头线 → 首 block 前缘距离；岸桥后伸梁跨过此带）。</summary>
    public const float YardInlandOffsetM = 70f;

    // ── ⑥ A3/A4 builder 管线数学（单点真值；M7BackdropBuilder 逐点消费）──────────────

    /// <summary>A3 小块平整：目标高程（米）→ 高度图归一化值 (target − elevMin) / span。
    /// SetHeights 写入该值即平整到 targetM（M7 review A11 fresh 测试钉契约：平整到错误
    /// 高程如 +20 m 在此即红，不再只靠构建期 gate 的 ≥0 单边验证）。</summary>
    public static double FlattenNormTarget(double elevMin, double elevSpan, float targetM)
        => (targetM - elevMin) / elevSpan;

    /// <summary>A4 alphamap texel 中心 → 高度图最近格索引：floor((texel+0.5)/alphaRes·heightmapRes)
    /// 钳 [0, heightmapRes−1]（texel 中心比例映射取整；中景 2049 格/257 texel → ~8 格对 1 texel）。</summary>
    public static int HeightmapIndexForTexel(int texel, int alphaRes, int heightmapRes)
        => Mathf.Min((int)((texel + 0.5f) / alphaRes * heightmapRes), heightmapRes - 1);

    /// <summary>A4 树卡世界 (x,z) → TreeInstance.position 归一化分量（tile 原点 + 边长；
    /// y 由地形引擎贴地，恒 0）。</summary>
    public static Vector2 TreeNormalizedPosition(Vector2 worldXZ, Vector2 originXZ, float sizeMeters)
        => new Vector2((worldXZ.x - originXZ.x) / sizeMeters, (worldXZ.y - originXZ.y) / sizeMeters);

        // ── ⑤ A4 远景近岸线树卡散布规划器（确定性、上限封顶）────────────────────────

        /// <summary>
        /// 从 tile 高度图规划树卡落位：候选 = 海拔 [2, 60] m 且 4 邻域含水下（&lt;0）格点
        /// （近岸线），按步长扫描；双遍规划（先计数定 stride，再按序采样）保证确定性、
        /// 总数 ≤ maxCount。exclusions（A3 平整矩形等）内的候选剔除。
        /// 返回 Unity 世界 (x, z) = 候选顶点原位（不做抖动：贴岸点若抖向水域会落海，
        /// 顶点原位保证落点高程 = 候选格高程 ≥ +2 m）。
        /// </summary>
        public static List<Vector2> ScatterTreeCards(
            float[,] heights, int res, float sizeMeters, Vector2 originXZ,
            double elevMin, double elevSpan, int maxCount, float[][] exclusions)
        {
            var candidates = new List<(int x, int y)>();
            const int step = 4; // ≈94 m（远景 23.4 m/px）
            for (int y = step; y < res - step; y += step)
            {
                for (int x = step; x < res - step; x += step)
                {
                    float e = M6TerrainMath.ElevMeters(heights[y, x], elevMin, elevSpan + elevMin);
                    if (e < 2f || e > 60f) continue;
                    float left = M6TerrainMath.ElevMeters(heights[y, x - step], elevMin, elevSpan + elevMin);
                    float right = M6TerrainMath.ElevMeters(heights[y, x + step], elevMin, elevSpan + elevMin);
                    float down = M6TerrainMath.ElevMeters(heights[y - step, x], elevMin, elevSpan + elevMin);
                    float up = M6TerrainMath.ElevMeters(heights[y + step, x], elevMin, elevSpan + elevMin);
                    if (Mathf.Min(Mathf.Min(left, right), Mathf.Min(down, up)) >= 0f) continue; // 需邻水
                    var world = new Vector2(originXZ.x + x / (float)(res - 1) * sizeMeters,
                                            originXZ.y + y / (float)(res - 1) * sizeMeters);
                    bool excluded = false;
                    if (exclusions != null)
                        foreach (var r in exclusions)
                            if (InRect(world, r)) { excluded = true; break; }
                    if (!excluded) candidates.Add((x, y));
                }
            }

            var result = new List<Vector2>();
            if (candidates.Count == 0) return result;
            int stride = Mathf.Max(1, candidates.Count / Mathf.Max(1, maxCount));
            for (int i = 0; i < candidates.Count && result.Count < maxCount; i++)
            {
                if (i % stride != 0) continue;
                var (x, y) = candidates[i];
                result.Add(new Vector2(
                    originXZ.x + x / (float)(res - 1) * sizeMeters,
                    originXZ.y + y / (float)(res - 1) * sizeMeters));
            }
            return result;
        }
    }
}
