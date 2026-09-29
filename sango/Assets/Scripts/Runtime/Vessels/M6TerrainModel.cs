using System;
using UnityEngine;

namespace Sango
{
    // ── M6 地形数据契约模型（纯数据/纯函数，Sango.Vessels 可直测）──────────────────
    // 消费链：Sango.Editor.M6TerrainPipeline（RAW→TerrainData）与 M6StraitSceneBootstrapper
    // （场景装配 + 水深 fail-fast 验证）。字段名 = tmp/m6-data/manifest.json 契约
    // （docs/research/2026-09-29-m6-terrain-pipeline/notes.md §manifest 契约），JsonUtility
    // 直接反序列化；未声明字段（s2 等）静默跳过（ColavTelemetry 同款纪律）。
    // 类型先例：坐标数组 float[]（DetectionResult.box_xyxy）、标量 double（ColavTelemetry.sim_time）
    // ——double[] 无先例不用；UTM 大数 float 化误差 ~2 cm（366493.33→366493.34），远小于
    // tile 12 km 尺度，无缝断言按 0.5 m 容差。

    [Serializable]
    public class M6Manifest
    {
        public int epsg;
        public float[] center_lonlat;
        public float[] center_utm; // [E, N]（EPSG:32648）= Unity 世界原点
        public float feather_m;
        public M6Band near;
        public M6Band far;

        public static M6Manifest Parse(string json) => JsonUtility.FromJson<M6Manifest>(json);
    }

    [Serializable]
    public class M6Band
    {
        public float[] extent_utm;   // [xmin, ymin, xmax, ymax] 逻辑域（RAW 光栅多东/南各 1 共享 px）
        public int tile_px;          // 高度图分辨率（2049/513，2^n+1 顶点格）
        public float tile_size_m;    // 恒 12000
        public int[] grid;           // [rows, cols]
        public float m_per_px;
        public int basemap_px;
        public double elev_min;      // u16=0 对应高程（米，海面下为负）
        public double elev_max;      // u16=65535 对应高程
        public M6Tile[] tiles;

        public double ElevSpan => elev_max - elev_min;
    }

    [Serializable]
    public class M6Tile
    {
        public string name;
        public float[] utm_bounds; // [xmin, ymin, xmax, ymax]
        public string path_raw;    // 仓库根相对
        public string path_jpg;
    }

    /// <summary>一个 tile 在 Unity 世界的落地参数（terrain position/size 由它唯一决定）。</summary>
    public struct M6TileLayout
    {
        public string name;
        public Vector2 originXZ;  // tile 西南角（Unity +X=东、+Z=北，米）
        public float sizeMeters;  // 12000
        public int heightmapResolution;
        public double elevMin;    // terrain.position.y = elevMin → 世界 y = 真实高程
        public double elevSpan;   // terrainData.size.y
        public M6Tile tile;
    }

    /// <summary>
    /// M6 地形布局/换算/水深验证纯函数集（EditMode 全覆盖，M5 F1 教训：fresh 路径钉契约）。
    /// 世界坐标约定：区域中心（manifest center_utm）= Unity 原点；+X=东、+Z=北；海面 y=0。
    /// </summary>
    public static class M6TerrainMath
    {
        /// <summary>tile 布局：西南角 = utm_bounds 最小角 − 区域中心。</summary>
        public static M6TileLayout LayoutFor(M6Tile tile, M6Band band, Vector2 centerUTM)
        {
            return new M6TileLayout
            {
                name = tile.name,
                originXZ = new Vector2(tile.utm_bounds[0] - centerUTM.x, tile.utm_bounds[1] - centerUTM.y),
                sizeMeters = band.tile_size_m,
                heightmapResolution = band.tile_px,
                elevMin = band.elev_min,
                elevSpan = band.ElevSpan,
                tile = tile,
            };
        }

        /// <summary>两个轴对齐矩形（[xmin,ymin,xmax,ymax]）的交叠面积（米²）；0=仅边界相触。</summary>
        public static float OverlapAreaM2(float[] a, float[] b)
        {
            float ox = Mathf.Min(a[2], b[2]) - Mathf.Max(a[0], b[0]);
            float oy = Mathf.Min(a[3], b[3]) - Mathf.Max(a[1], b[1]);
            return (ox > 0f && oy > 0f) ? ox * oy : 0f;
        }

        /// <summary>
        /// 与近景带有实际交叠（面积 &gt; epsilon，边界相触不算）的远景 tile 名集合——
        /// 这些 tile 场景里 SetActive(false)（2026-09-29 编排者裁决：覆盖语义优先于
        /// 任务文本的"4 个"字面数——真实网格半 tile 偏移，交叠=9/全覆盖=1，无划分得 4；
        /// 共面双层地形 z-fight 是硬伤，洞在 12–24 km 远景环、默认雾距外被遮蔽，M8 流送接棒）。
        /// </summary>
        public static bool FarTileUnderNearBand(M6Tile farTile, float[] nearExtentUtm, float epsilonM2 = 1f)
            => OverlapAreaM2(farTile.utm_bounds, nearExtentUtm) > epsilonM2;

        // ── RAW 解码（ENVI 裸二进制 UInt16 单带 BSQ、小端、行序北上）──────────────

        /// <summary>
        /// 小端 u16 网格原样读出（无翻转；row 0 = 最北行）。字节序/往返契约的测试锚点。
        /// </summary>
        public static ushort[,] ReadU16GridLittleEndian(byte[] raw, int res)
        {
            if (raw.Length != res * res * 2)
                throw new ArgumentException($"RAW size {raw.Length} != {res}x{res}x2 (u16 BSQ)");
            var grid = new ushort[res, res];
            int i = 0;
            for (int r = 0; r < res; r++)
                for (int c = 0; c < res; c++)
                {
                    // 小端：低字节在前
                    grid[r, c] = (ushort)(raw[i] | (raw[i + 1] << 8));
                    i += 2;
                }
            return grid;
        }

        /// <summary>
        /// RAW → Unity SetHeights 归一化高度（0..1），带垂直翻转：RAW row 0 = 最北行，
        /// SetHeights 的 y=0 行是最南行（heights[y,x]，y 自南向北）。这是"Unity 导入须
        /// 垂直翻转"契约的实现点（notes.md §RAW 约定）。
        /// </summary>
        public static float[,] DecodeNormalizedHeights(byte[] raw, int res)
        {
            var grid = ReadU16GridLittleEndian(raw, res);
            var heights = new float[res, res];
            for (int r = 0; r < res; r++)          // r = RAW 行（0=北）
                for (int c = 0; c < res; c++)
                    heights[res - 1 - r, c] = grid[r, c] / 65535f;
            return heights;
        }

        // ── u16 ↔ 米换算（带内共用一对 min/max；跨带灰度不可直接比，见 notes.md §限制 5）──

        /// <summary>归一化高度（0..1）→ 高程米（海面下为负）。</summary>
        public static float ElevMeters(float normalized, double elevMin, double elevMax)
            => (float)(elevMin + normalized * (elevMax - elevMin));

        /// <summary>u16 原值 → 高程米。</summary>
        public static float ElevMetersFromU16(ushort u16, double elevMin, double elevMax)
            => ElevMeters(u16 / 65535f, elevMin, elevMax);

        // ── 水深采样 / 验证（防搁浅 fail-fast；构建期消费，纯函数进 EditMode）────────

        /// <summary>世界 (x,z) → 高程米的采样委托（实现方：Terrain.SampleHeight / 合成 fixture）。</summary>
        public delegate float ElevationSampler(Vector2 worldXZ);

        /// <summary>合成高度图双线性采样（测试/工具用）：heights 为 SetHeights 同款 [y,x] 归一化格。</summary>
        public static float SampleNormalized(float[,] heights, int res, float sizeMeters, Vector2 localXZ)
        {
            float fx = Mathf.Clamp(localXZ.x / sizeMeters, 0f, 1f) * (res - 1);
            float fy = Mathf.Clamp(localXZ.y / sizeMeters, 0f, 1f) * (res - 1);
            int x0 = Mathf.Min((int)fx, res - 2), y0 = Mathf.Min((int)fy, res - 2);
            float tx = fx - x0, ty = fy - y0;
            float a = Mathf.Lerp(heights[y0, x0], heights[y0, x0 + 1], tx);
            float b = Mathf.Lerp(heights[y0 + 1, x0], heights[y0 + 1, x0 + 1], tx);
            return Mathf.Lerp(a, b, ty);
        }

        /// <summary>水深验证结果：ok=false 时 worstPoint/worstElevationM = 首个违规采样（fail-fast 报错用）；
        /// ok=true 时 worst* = 全局最深、shallowestElevationM = 全局最浅（门的绑定值）。</summary>
        public struct DepthReport
        {
            public bool ok;
            public float worstElevationM;
            public Vector2 worstPoint;
            public float shallowestElevationM;
            public int samples;
        }

        /// <summary>
        /// 锚地船位验证：所有位置高程 &lt; 0（水面下）。不满足不静默换点——调用方按
        /// 报告 fail fast。marginM：要求低于海平面的额外裕量（0 = 仅 &lt; 0）。
        /// 报告语义：失败时 worst* = 首个违规采样（可复现坐标）；成功时 worst* = 全局最深点。
        /// </summary>
        public static DepthReport ValidateDepths(ElevationSampler sample, Vector2[] points, float marginM = 0f)
        {
            var report = new DepthReport { ok = true, worstElevationM = float.MaxValue, shallowestElevationM = float.MinValue, samples = points.Length };
            foreach (var p in points)
            {
                float e = sample(p);
                if (e >= -marginM)
                {
                    report.ok = false;
                    report.worstElevationM = e;
                    report.worstPoint = p;
                    return report; // fail fast：首个违规即停，报违规点本身
                }
                if (e < report.worstElevationM) { report.worstElevationM = e; report.worstPoint = p; }
                if (e > report.shallowestElevationM) report.shallowestElevationM = e;
            }
            return report;
        }

        /// <summary>
        /// G 航路验证：逐航点间按 sampleStepM 插值采样，全程高程 &lt; 0（含 -marginM 裕量）。
        /// 采样步长覆盖断言：samples ≥ ceil(总长/步长)+1。
        /// </summary>
        public static DepthReport ValidateRoute(ElevationSampler sample, Vector2[] waypoints, float sampleStepM, float marginM = 0f)
        {
            if (waypoints == null || waypoints.Length < 2)
                throw new ArgumentException("route needs >= 2 waypoints");
            var report = new DepthReport { ok = true, worstElevationM = float.MaxValue, shallowestElevationM = float.MinValue, samples = 0 };
            for (int i = 0; i + 1 < waypoints.Length; i++)
            {
                var a = waypoints[i];
                var b = waypoints[i + 1];
                float length = Vector2.Distance(a, b);
                int steps = Mathf.Max(1, Mathf.CeilToInt(length / sampleStepM));
                for (int k = 0; k <= steps; k++)
                {
                    var p = Vector2.Lerp(a, b, k / (float)steps);
                    float e = sample(p);
                    report.samples++;
                    if (e >= -marginM)
                    {
                        report.ok = false;
                        report.worstElevationM = e;
                        report.worstPoint = p;
                        return report; // fail fast：报违规采样点本身（非全局最深）
                    }
                    if (e < report.worstElevationM) { report.worstElevationM = e; report.worstPoint = p; }
                    if (e > report.shallowestElevationM) report.shallowestElevationM = e;
                }
            }
            return report;
        }
    }
}
