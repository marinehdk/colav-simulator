using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E2 Simulation 面板 → 岛屿重建的参数映射（纯函数，spec #85 Testing Decisions）。
    /// 映射表（面板值 → IslandSettings 字段，全档 documented）：
    ///   count        → count（直传，钳 1..24）
    ///   scale        → sizeRange.x/y × scale（岛直径整体缩放）、clusterRadius × scale（撒点盘同比放大，
    ///                  保密度观感）；maxHeight/resolution/seed/材质原样保留（竖向尺度不变——约定缝只动
    ///                  这三处；seed 恒 42 = 同一群岛等比缩放，确定性）。
    /// 同 seed + 同 scale 下 rebuild 逐位一致（xorshift + Perlin 都无隐藏状态）。
    /// </summary>
    public static class IslandRebuild
    {
        public const int CountMin = 1;
        public const int CountMax = 24;
        public const float ScaleMin = 0.25f;
        public const float ScaleMax = 3f;

        /// <summary>M1 场景既有岛群基线（M1SceneBootstrapper 常数同源；材质由调用方注入）。</summary>
        public static IslandSettings M1Baseline()
        {
            return new IslandSettings
            {
                count = 5,
                sizeRange = new Vector2(80f, 240f),
                maxHeight = 45f,
                resolution = 96,
                seed = 42,
                clusterRadius = 260f,
                material = null, // M1SceneBootstrapper 注入岛体材质（TintedLit 深绿灰）
                vertexColors = false,
            };
        }

        /// <summary>面板 count/scale → 生成设置（其余字段从基线复制）。</summary>
        public static IslandSettings MapToSettings(IslandSettings baseline, int count, float scale)
        {
            float s = Mathf.Clamp(scale, ScaleMin, ScaleMax);
            return new IslandSettings
            {
                count = Mathf.Clamp(count, CountMin, CountMax), // 直传（钳预算）
                sizeRange = new Vector2(baseline.sizeRange.x * s, baseline.sizeRange.y * s),
                clusterRadius = baseline.clusterRadius * s, // 撒点盘同比放大，岛群密度观感不变
                maxHeight = baseline.maxHeight,             // 竖向尺度不变（约定缝只动横向三处）
                resolution = baseline.resolution,
                seed = baseline.seed,                       // seed 恒定 = 同一群岛等比缩放，确定性
                material = baseline.material,
                vertexColors = baseline.vertexColors,
            };
        }
    }
}
