using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>M8 画质档（High = M7 终态基线 / Low = 性能降档）。</summary>
    public enum M8QualityTier
    {
        High = 0,
        Low = 1,
    }

    /// <summary>
    /// M8 画质双档参数表（纯静态 preset，代码内字面量；不引入 ScriptableObject 资产——
    /// Simplicity First）。EditMode 全覆盖；消费方 Sango.Editor.M6StraitSceneBootstrapper
    /// （构建期接线 + 断言 fail-fast）与 M8TileStreaming（运行时消费）。
    /// 档语义：
    /// - High = M7 终态全量：近带 4 tile 激活、交叠 9 tile 隐藏（覆盖语义）、外环 16 tile
    ///   常开、全树卡/箱堆/岸桥、后处理/阴影保持场景原值（参数经基线捕获回写，零漂移）。
    /// - Low = 近带 4 tile 常开 + 外环按参考点邻域（逐 tile 迟滞 latch）裁剪；交叠 9 tile
    ///   恒关（与近带互斥，z-fight 硬伤）；外环 tile 树距/detail 距/pixelError 收窄 + 太阳
    ///   软影转硬影（记录在案的降档杠杆）；装饰组随宿主 tile 走（不产生悬空岸桥）。
    /// </summary>
    public static class M8QualityProfile
    {
        // ── tile 编排常量（manifest 几何，构建期接线断言复核）────────────────────────
        public const int NearTileCount = 4;      // 近带 2×2（2049²）
        public const int OverlapTileCount = 9;   // 交叠远景 = 远带 5×5 中央 3×3
        public const int RingTileCount = 16;     // 外环远景（与近带无交叠）
        public const int TotalTileCount = NearTileCount + OverlapTileCount + RingTileCount; // 29
        public const float TileSizeM = 12000f;
        public const float NearBandHalfM = 12000f; // 近带 = ±12 km（manifest near extent）
        public const float FarBandHalfM = 30000f;  // 远带 = ±30 km

        // ── NEAR/FAR 互斥 swap 迟滞（Chebyshev 出带距离，<0 = 带内）──────────────────
        /// <summary>NEAR→FAR：出带 &gt;2 km 才换（迟滞带宽防边界抖动）。</summary>
        public const float FarEngageOutsideM = 2000f;
        /// <summary>FAR→NEAR：须回带内 500 m 才换回（迟滞回程）。</summary>
        public const float NearReenterInsideM = 500f;

        // ── Low 档外环邻域逐 tile 迟滞（Chebyshev 距参考点距离）──────────────────────
        public const float RingEnterDistanceM = 13000f; // ≤13 km 亮（> 近带缘 1 km）
        public const float RingExitDistanceM = 16000f;  // >16 km 灭（迟滞 3 km）
        /// <summary>Low 档同时激活的外环 tile 上限（断言护栏；邻域最坏 2×2=4，留裕量）。</summary>
        public const int LowMaxActiveRingTiles = 9;

        // ── High 档 = M7 终态语义（布尔钉死，测试对照）──────────────────────────────
        public const bool HighOverlapStartsHidden = true;
        public const bool HighRingAlwaysOn = true;
        public const bool HighSwapsNearOutsideBand = true; // 主船出带后交叠 9 接管、近带让位（互斥）
        /// <summary>High 档外环树距 = Unity Terrain 默认（M7 未改；接线期基线捕获回写保证零漂移，
        /// 此常量仅作文档/Low 对照锚）。</summary>
        public const int HighFarTreeDistanceM = 2000;

        // ── Low 档降档参数（记录在案）────────────────────────────────────────────────
        public const bool LowSwapsNearOutsideBand = false; // 近带恒开（近带核心观感保证）
        public const int LowFarTreeDistanceM = 1500;       // < High 2000
        public const int LowFarDetailObjectDistanceM = 40; // < 默认 80（本场景无 detail 层，记录用）
        public const float LowFarHeightmapPixelError = 6f; // 外环网格 LOD 放粗（默认 1）
        public const bool LowSunShadowsHard = true;        // 太阳软影 → 硬影（过滤开销归零）

        // ── 树/箱上限常量（与 M7 常量同源钉死）──────────────────────────────────────
        public const int TreeCardBudgetHigh = M7BackdropMath.MaxTreeInstances;       // 4000
        public const int TreeCardsPerFarTileHigh = M7BackdropMath.MaxTreesPerFarTile; // 220

        // ── 装饰组静态索引（构建期编号；GO 名 = M7BackdropBuilder/M7BSceneBuilder 字面量）──
        public const int DecorationGroupCount = 9; // PP 岸桥+箱堆、Tuas 岸桥+箱堆、渔排×5
        public const int GroupPasirPanjangCranes = 0;
        public const int GroupPasirPanjangYard = 1;
        public const int GroupTuasCranes = 2;
        public const int GroupTuasYard = 3;
        public const int GroupFishFarmFirst = 4;

        /// <summary>装饰组宿主 tile（组随宿主 tile 激活态走；PP 在近带 r1c0、Tuas 在外环
        /// far_r2c0、渔排在 M7BMath 钉值外环 far_r3c4——M7-B provenance 注）。</summary>
        public const string PasirPanjangHostTile = "near_r1c0_2049";
        public const string TuasHostTile = "far_r2c0_513";
        public const string FishFarmHostTile = "far_r3c4_513";

        public static readonly string[] DecorationGoNames =
        {
            "M7 Cranes PasirPanjang",
            "M7 Yard PasirPanjang",
            "M7 Cranes TuasPier",
            "M7 Yard TuasPier",
            "M7B Fish Farm 00",
            "M7B Fish Farm 01",
            "M7B Fish Farm 02",
            "M7B Fish Farm 03",
            "M7B Fish Farm 04",
        };

        public static readonly string[] DecorationHostTiles =
        {
            PasirPanjangHostTile,
            PasirPanjangHostTile,
            TuasHostTile,
            TuasHostTile,
            FishFarmHostTile,
            FishFarmHostTile,
            FishFarmHostTile,
            FishFarmHostTile,
            FishFarmHostTile,
        };

        // ── 纯函数 ─────────────────────────────────────────────────────────────────

        /// <summary>GUI 下拉索引 → 档（越界钳位；下拉序 = 枚举序 High/Low）。</summary>
        public static M8QualityTier TierFromDropdownIndex(int index)
            => (M8QualityTier)Mathf.Clamp(index, (int)M8QualityTier.High, (int)M8QualityTier.Low);

        /// <summary>渔排宿主 tile 矩形（Unity 米；由远带常量推出，供漂移断言）。</summary>
        public static Rect FishFarmHostRect()
        {
            // far_r3c4：row 3（z -18000..-6000）、col 4（x 18000..30000）
            float xmin = -FarBandHalfM + 4 * TileSizeM;
            float zmin = -FarBandHalfM + 1 * TileSizeM;
            return Rect.MinMaxRect(xmin, zmin, xmin + TileSizeM, zmin + TileSizeM);
        }

        /// <summary>
        /// 构建期断言（bootstrapper 接线前调用；返回错误列表，空 = 通过）。可注入被检表
        /// （默认静态表）——EditMode 走注入路径触发断言（构建期断言触发路径可测）。
        /// 检：两档参数完整性/互异性、装饰组表与 M7 builder 字面量同源、渔排落位在宿主
        /// tile 矩形内（M7BMath 漂移即红）、迟滞常量 sane。
        /// </summary>
        public static List<string> Validate(
            string[] decorationGoNames = null,
            string[] decorationHostTiles = null,
            Vector2[] fishFarmSites = null)
        {
            var errors = new List<string>();
            decorationGoNames = decorationGoNames ?? DecorationGoNames;
            decorationHostTiles = decorationHostTiles ?? DecorationHostTiles;
            fishFarmSites = fishFarmSites ?? M7BMath.FishFarmSites;

            // 参数完整性（两档互异 + sane）
            if (FarEngageOutsideM <= 0f || NearReenterInsideM <= 0f)
                errors.Add($"hysteresis constants must be positive (engage {FarEngageOutsideM}, reenter {NearReenterInsideM})");
            if (RingEnterDistanceM <= NearBandHalfM || RingEnterDistanceM >= RingExitDistanceM)
                errors.Add($"ring latch band invalid: enter {RingEnterDistanceM} must be in ({NearBandHalfM}, exit {RingExitDistanceM})");
            if (LowFarTreeDistanceM <= 0 || LowFarTreeDistanceM >= HighFarTreeDistanceM)
                errors.Add($"Low far tree distance {LowFarTreeDistanceM} must be in (0, {HighFarTreeDistanceM})");
            if (LowFarHeightmapPixelError < 1f)
                errors.Add($"Low far pixel error {LowFarHeightmapPixelError} < 1");
            if (LowMaxActiveRingTiles < 1 || LowMaxActiveRingTiles > RingTileCount)
                errors.Add($"Low max active ring tiles {LowMaxActiveRingTiles} out of [1,{RingTileCount}]");
            if (!LowSwapsNearOutsideBand && !LowSunShadowsHard
                && LowFarTreeDistanceM >= HighFarTreeDistanceM)
                errors.Add("Low tier has no recorded downgrade lever — tiers not distinct");
            if (TreeCardBudgetHigh != M7BackdropMath.MaxTreeInstances
                || TreeCardsPerFarTileHigh != M7BackdropMath.MaxTreesPerFarTile)
                errors.Add("tree budget constants drifted from M7BackdropMath");

            // 装饰组表：计数、命名、宿主同源
            if (decorationGoNames == null || decorationGoNames.Length != DecorationGroupCount)
                errors.Add($"decoration GO names count {(decorationGoNames?.Length ?? 0)} != {DecorationGroupCount}");
            if (decorationHostTiles == null || decorationHostTiles.Length != DecorationGroupCount)
                errors.Add($"decoration host tiles count {(decorationHostTiles?.Length ?? 0)} != {DecorationGroupCount}");
            if (errors.Count == 0)
            {
                for (int i = GroupFishFarmFirst; i < DecorationGroupCount; i++)
                {
                    string expect = $"M7B Fish Farm {i - GroupFishFarmFirst:00}";
                    if (decorationGoNames[i] != expect)
                        errors.Add($"farm group {i} GO name '{decorationGoNames[i]}' != '{expect}'");
                    if (decorationHostTiles[i] != FishFarmHostTile)
                        errors.Add($"farm group {i} host '{decorationHostTiles[i]}' != '{FishFarmHostTile}'");
                }
                if (decorationHostTiles[GroupPasirPanjangCranes] != M7BackdropMath.PasirPanjang.tileName
                    || decorationHostTiles[GroupPasirPanjangYard] != M7BackdropMath.PasirPanjang.tileName)
                    errors.Add($"Pasir Panjang groups host drift (expect {M7BackdropMath.PasirPanjang.tileName})");
                if (decorationHostTiles[GroupTuasCranes] != M7BackdropMath.TuasPier.tileName
                    || decorationHostTiles[GroupTuasYard] != M7BackdropMath.TuasPier.tileName)
                    errors.Add($"Tuas groups host drift (expect {M7BackdropMath.TuasPier.tileName})");
                if (decorationGoNames[GroupPasirPanjangCranes] != $"M7 Cranes {M7BackdropMath.PasirPanjang.name}"
                    || decorationGoNames[GroupPasirPanjangYard] != $"M7 Yard {M7BackdropMath.PasirPanjang.name}"
                    || decorationGoNames[GroupTuasCranes] != $"M7 Cranes {M7BackdropMath.TuasPier.name}"
                    || decorationGoNames[GroupTuasYard] != $"M7 Yard {M7BackdropMath.TuasPier.name}")
                    errors.Add("terminal decoration GO names drifted from M7BackdropBuilder literals");

                // 渔排落位 ⊂ 宿主 tile 矩形（M7BMath 选点漂移即红——宿主隐藏 = 渔排悬空）
                var hostRect = FishFarmHostRect();
                foreach (var s in fishFarmSites)
                    if (!hostRect.Contains(s))
                        errors.Add($"fish farm site ({s.x:F0},{s.y:F0}) outside host tile rect {hostRect} — host tile would hide/separate it");
            }
            return errors;
        }
    }
}
