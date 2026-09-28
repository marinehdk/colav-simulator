using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M4-B 水线工艺纯核心（issue #87 批次 B 项 1/4）：湿带上界偏移量 + boot top 带高。
    /// 纯静态、确定性、零引擎写——DecalProjector 的每帧 y 驱动是 HullWaterlineDecals
    /// 适配器的职责（分层先例：BuoyancyAttitudeSolver / WaterDecalSpeedGate）。
    /// </summary>
    public static class HullWaterlineCore
    {
        /// <summary>
        /// 湿带上界偏移量（米）：waterHeight − baseline 钳到船体型深范围
        /// [−draftM（龙骨方向）, +freeboardM（干舷方向）]。
        ///   waterHeight/baseline 语义由调用方定（适配器传"水面相对船体的高度 vs 设计水线 0"）；
        ///   正偏移 = 水面升到设计水线之上（湿带沿干舷上爬），负 = 水面退到设计水线之下
        ///   （湿带收进吃水线以下，船壳露出干面）。
        /// 退化护栏：draftM/freeboardM 为负视为 0（无该方向可动程，钳死在设计水线）。
        /// </summary>
        public static float WetBandUpperOffsetM(float waterHeightM, float baselineM, float draftM, float freeboardM)
        {
            float lower = draftM > 0f ? -draftM : 0f;
            float upper = freeboardM > 0f ? freeboardM : 0f;
            return Mathf.Clamp(waterHeightM - baselineM, lower, upper);
        }

        /// <summary>
        /// boot top 带高（米）：请求值钳到 [0, freeboardM]——静态防污红带从设计吃水线
        /// 上缘向上铺，不允许越过船体上缘（型深上限）。freeboardM ≤ 0（水线在包围盒顶之上，
        /// 理论不可能）返回 0 = 不铺带。
        /// </summary>
        public static float BootTopBandHeightM(float requestedM, float freeboardM)
        {
            if (freeboardM <= 0f) return 0f;
            return Mathf.Clamp(requestedM, 0f, freeboardM);
        }
    }
}
