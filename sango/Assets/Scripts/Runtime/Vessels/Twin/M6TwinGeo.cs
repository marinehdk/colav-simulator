using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M6 孪生场景地理配准（P3-12 spec #91 批 1 遗留闭环）：会话 NE 域 → M6 海峡场景
    /// 坐标的登记变换 + 覆盖度（geo_fit）判定。单一真源 = 本类常量 + M6WaterMask。
    ///
    /// 背景（批 1 台账）：twin 数据位姿槽位对拍 0.13 m 正确，但锚点把会话 NE 直接当
    /// 场景坐标用——live 首帧本船/replay ENC origin 落在场景 (0,0) = 区域中心
    /// (103.80E, 1.28N)，DEM 实采高程 +41.3 m（新加坡本岛陆域），目标船视觉压在陆地
    /// 贴图上。会话 NE 域（enc origin (37000,6955000)，框 7000×7000 m，frame
    /// "local_north_east_m"）是后端合成域，与场景 EPSG:32648 域无大地对应——登记 =
    /// 纯平移（两域同以北为 0° 顺时针艏向、米制；无旋转/缩放）：
    ///
    ///     scenePos = (NE − anchorNE) + LandingM
    ///
    /// LandingM = (21000, −5000) 选点 provenance（tools/m6_water_mask.py 同源 DEM 离线
    /// 实采，2026-10-02）：海峡东侧开阔水域（新加坡海峡东口），对两种锚定语义的
    /// 7×7 km 会话框均 100% 水面且全程 DEM 覆盖内——live（首帧本船锚，框 ±3.5 km 围绕
    /// 落点）与 replay（ENC origin 锚，框 [落点, 落点+7 km]²）：
    ///   live 框   [17.5,−8.5]..[24.5,−1.5] km：water=1.000 terrain=1.000 深度 −65.4..−44.3 m 中位
    ///   replay 框 [21,−5]..[28,2]         km：water=1.000 terrain=1.000 深度 −61.5..−41.6 m 中位
    /// 落点与其 box 全程落在**激活**远景环 tile（x ≥ +18 km 带，交叠隐藏 9 tile 之外——
    /// 首版落点 (17000,−4800) 踩在近带下的隐藏 tile 上：水面视觉成立但 ElevationAt 采不到
    /// 地形、近旁海岸细节缺失，弃）。且与 Demo 布景（主角泊位 (−1500,−5000)、M7 锚地/
    /// M7B 浮标·渡轮·渔排群）零重叠。反例存档：场景 (0,0) 6×6 km 框 water≈0.17（批 1
    /// 缺陷复现面）；主航道带 (9,−8) 框 live 侧 water=0.948（Batam 西北岸）——均不满足落点门。
    /// </summary>
    public static class M6TwinGeo
    {
        /// <summary>geo_fit 词汇（twin-bridge-v1 §3/§8 演进字段；空串 = 尚无帧无判定）。</summary>
        public const string FitInside = "inside";
        public const string FitPartial = "partial";
        public const string FitOutside = "outside";

        /// <summary>登记平移：锚定局部原点在场景中的落点（场景米，+x 东 +z 北）。</summary>
        public static Vector2 LandingM => new Vector2(21000f, -5000f);

        /// <summary>geo_fit 判定门：水面占比 ≥ 98% = inside；地形覆盖占比 &lt; 50% = outside
        /// （DEM 覆盖外开阔海面，无限海面视觉成立但无真实地形）；其余 = partial。</summary>
        public const float InsideWaterFractionMin = 0.98f;
        public const float OutsideTerrainFractionMax = 0.5f;

        /// <summary>覆盖度采样步（米）= 掩膜分辨率。</summary>
        public const float FitSampleStepM = 200f;

        /// <summary>geo_fit 判定结果（分数为掩膜实采占比）。</summary>
        public struct FitReport
        {
            public string Fit;
            public float WaterFraction;
            public float TerrainFraction;
        }

        /// <summary>
        /// 会话矩形（场景米 min/max 角）→ geo_fit。纯函数（消费 M6WaterMask 烘焙掩膜，
        /// 不触地形对象）。0 面积退化（单点首帧）按单格采样。
        /// </summary>
        public static FitReport ClassifyFit(Vector2 sceneMin, Vector2 sceneMax)
        {
            float x0 = Mathf.Min(sceneMin.x, sceneMax.x), x1 = Mathf.Max(sceneMin.x, sceneMax.x);
            float z0 = Mathf.Min(sceneMin.y, sceneMax.y), z1 = Mathf.Max(sceneMin.y, sceneMax.y);
            int water = 0, terrain = 0, total = 0;
            for (float z = SnapCell(z0); z <= z1 + 0.5f * FitSampleStepM; z += FitSampleStepM)
                for (float x = SnapCell(x0); x <= x1 + 0.5f * FitSampleStepM; x += FitSampleStepM)
                {
                    byte cell = M6WaterMask.Sample(x, z);
                    total++;
                    if (cell != M6WaterMask.Outside) terrain++;
                    if (cell == M6WaterMask.Water) water++;
                }
            float terrainFraction = total > 0 ? terrain / (float)total : 0f;
            float waterFraction = total > 0 ? water / (float)total : 0f;
            return new FitReport
            {
                Fit = terrainFraction < OutsideTerrainFractionMax ? FitOutside
                    : waterFraction < InsideWaterFractionMin ? FitPartial
                    : FitInside,
                WaterFraction = waterFraction,
                TerrainFraction = terrainFraction,
            };
        }

        /// <summary>采样点对齐掩膜格心（避免步进浮点漂移逐点错格）。</summary>
        static float SnapCell(float value)
        {
            int index = Mathf.FloorToInt((value + M6WaterMask.ExtentM) / FitSampleStepM);
            return -M6WaterMask.ExtentM + (index + 0.5f) * FitSampleStepM;
        }

        // ── 场景高程实采（诊断面：diag 行 e= 字段，"船在水面"断言的权威判据）────────

        static Terrain[] m_Terrains;

        /// <summary>
        /// 场景 (x,z) → 地形世界高程（米；海面下为负）。与构建期门同口径
        /// （M6StraitSceneBootstrapper.BuildSampler：SampleHeight 不含 terrain y，须加
        /// position.y 锚定）。无地形/覆盖外返回 NaN（开阔海面——无限海面无地形可采）。
        /// 惰性缓存地形表；twin 诊断专用，Demo 路径零调用。
        /// </summary>
        public static float ElevationAt(Vector3 sceneXZ)
        {
            if (m_Terrains == null)
                m_Terrains = Object.FindObjectsByType<Terrain>(FindObjectsSortMode.None);
            foreach (var terrain in m_Terrains)
            {
                if (terrain == null) continue;
                var p = terrain.transform.position;
                var size = terrain.terrainData.size;
                if (sceneXZ.x >= p.x && sceneXZ.x <= p.x + size.x
                    && sceneXZ.z >= p.z && sceneXZ.z <= p.z + size.z)
                    return terrain.SampleHeight(sceneXZ) + p.y;
            }
            return float.NaN;
        }
    }
}
