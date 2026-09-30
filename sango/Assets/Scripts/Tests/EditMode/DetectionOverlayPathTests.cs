using NUnit.Framework;
using Sango;

namespace Sango.Tests
{
    /// <summary>
    /// M9 overlay live/GT 路径判定纯函数（DetectionFreshness.PreferLiveOverGroundTruth，
    /// DetectionOverlay.OnGUI 的分支谓词）worked examples：null/畸形/陈旧/未来戳 → 真值回退；
    /// 新鲜结果（含权威空 detections）→ live 接管。消费端/overlay 适配层不进测试（无 socket、无场景）。
    /// </summary>
    public class DetectionOverlayPathTests
    {
        static DetectionResult Live(double frameTimeS, params DetectionResult.Box[] boxes)
        {
            return new DetectionResult
            {
                frame_seq = 9,
                frame_time_s = frameTimeS,
                source = "yolo-detector",
                detections = boxes,
            };
        }

        static DetectionResult.Box Boat(float confidence = 0.7f)
        {
            return new DetectionResult.Box
            {
                box_xyxy = new[] { 10f, 20f, 300f, 200f },
                class_id = 8,
                class_name = "boat",
                confidence = confidence,
            };
        }

        [Test]
        public void NullLive_FallsBackToGroundTruth()
        {
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(null, 100.0), Is.False,
                "无 live 结果（消费端关闸/队列空）→ 真值路径");
        }

        [Test]
        public void FreshResult_TakesLivePath()
        {
            var live = Live(100.0 - 0.1, Boat());
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(live, 100.0), Is.True);
        }

        [Test]
        public void FreshEmptyResult_TakesLivePath()
        {
            var live = Live(100.0 - 0.1);
            Assert.That(live.detections, Is.Empty);
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(live, 100.0), Is.True,
                "detections=[] 是 YOLO 的权威'没看到'：live 接管渲染零框，不回退真值");
        }

        [Test]
        public void StaleResult_FallsBackToGroundTruth()
        {
            var live = Live(100.0 - 0.6, Boat());
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(live, 100.0), Is.False,
                "age 0.6s > 0.5s 窗 → 真值回退");
        }

        [Test]
        public void FutureTimestampedResult_FallsBackToGroundTruth()
        {
            var live = Live(100.0 + 0.2, Boat());
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(live, 100.0), Is.False,
                "负 age（外部源时钟域不一致）按陈旧拒绝");
        }

        [Test]
        public void MalformedResult_NullDetections_FallsBackToGroundTruth()
        {
            // JsonUtility 对缺 detections 字段取 null（DetectionResult.FromJson("{}") 路径）
            var malformed = DetectionResult.FromJson("{\"frame_seq\":1,\"frame_time_s\":99.9,\"source\":\"yolo-detector\"}");
            Assert.That(malformed.detections, Is.Null);
            Assert.That(DetectionFreshness.PreferLiveOverGroundTruth(malformed, 100.0), Is.False,
                "畸形结果（detections 缺失）→ 真值回退");
        }
    }
}
