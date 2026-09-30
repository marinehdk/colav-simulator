using System;

namespace Sango
{
    /// <summary>
    /// M9 回传新鲜度纯核心（detection-return-v1.md §3）：seq 连续 + age 窗两谓词，以及
    /// DetectionOverlay 的 live/GT 路径判定。全部纯函数——不建 socket、不读时钟，
    /// now 由调用方传入（Unity 侧用 Time.timeAsDouble，与 FrameMetadata.frame_time_s 同钟域），
    /// EditMode 直测 worked examples。
    /// </summary>
    public static class DetectionFreshness
    {
        /// <summary>新鲜度窗口上限（秒）：age 超窗的结果按陈旧丢弃，渲染回退 ground-truth。</summary>
        public const double MaxAgeS = 0.5;

        /// <summary>
        /// age 窗谓词：age = nowS − frameTimeS，需 0 ≤ age ≤ maxAgeS。
        /// 负 age（未来时间戳，如时钟域不一致的外部源）按陈旧拒绝。
        /// </summary>
        public static bool IsFresh(double nowS, double frameTimeS, double maxAgeS = MaxAgeS)
        {
            double age = nowS - frameTimeS;
            return age >= 0.0 && age <= maxAgeS;
        }

        /// <summary>
        /// seq 连续谓词：只消费严格大于上一已消费帧号的结果（PUB 慢加入/掉帧导致的
        /// 跳号容忍，重复与乱序旧帧拒绝）。初始 lastConsumedSeq = -1，帧号从 0 起可消费。
        /// </summary>
        public static bool IsNewer(int candidateSeq, int lastConsumedSeq)
        {
            return candidateSeq > lastConsumedSeq;
        }

        /// <summary>
        /// overlay live/GT 判定（纯函数）：存在新鲜 live 结果 → live 路径，否则回退 ground-truth。
        /// detections=[] 的权威空结果也算 live 接管（YOLO 明确"没看到"，渲染零框）；
        /// null 结果 / detections 缺失（畸形 JSON）/ 陈旧 / 未来戳 → 真值路径。
        /// </summary>
        public static bool PreferLiveOverGroundTruth(DetectionResult live, double nowS, double maxAgeS = MaxAgeS)
        {
            return live != null && live.detections != null && IsFresh(nowS, live.frame_time_s, maxAgeS);
        }
    }
}
