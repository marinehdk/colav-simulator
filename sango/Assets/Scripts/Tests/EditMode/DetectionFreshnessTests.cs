using NUnit.Framework;
using Sango;

namespace Sango.Tests
{
    /// <summary>
    /// M9 新鲜度纯核心 worked examples（detection-return-v1.md §3：消费端只认 age≤0.5s 且
    /// seq 严格前进的结果）。期望值来自独立事实（协议文档规则），不回声实现。
    /// </summary>
    public class DetectionFreshnessTests
    {
        [Test]
        public void MaxAge_Window_MatchesContract()
        {
            Assert.That(DetectionFreshness.MaxAgeS, Is.EqualTo(0.5), "契约冻结：age ≤ 0.5s");
        }

        [TestCase(10.0, 9.8,  true)]  // age 0.2s：窗内
        [TestCase(10.0, 9.5,  true)]  // age 0.5s：边界含（≤）
        [TestCase(10.0, 10.0, true)]  // age 0：同刻
        [TestCase(10.0, 9.499, false)] // age 0.501s：刚超窗
        [TestCase(10.0, 9.2,  false)] // age 0.8s：陈旧
        [TestCase(10.0, 10.2, false)] // 负 age（未来戳）：按陈旧拒绝
        public void IsFresh_WorkedExamples(double nowS, double frameTimeS, bool expected)
        {
            Assert.That(DetectionFreshness.IsFresh(nowS, frameTimeS), Is.EqualTo(expected));
        }

        [Test]
        public void IsFresh_CustomWindow_Scales()
        {
            Assert.That(DetectionFreshness.IsFresh(10.0, 9.8, 0.2), Is.True, "age=0.2 恰在 0.2s 窗边界");
            Assert.That(DetectionFreshness.IsFresh(10.0, 9.7, 0.2), Is.False, "age=0.3 超 0.2s 窗");
        }

        [TestCase(0, -1,  true)]  // 初始态：帧号从 0 起可消费
        [TestCase(5, 4,   true)]  // 严格前进
        [TestCase(5, 5,   false)] // 重复拒绝
        [TestCase(5, 6,   false)] // 乱序旧帧拒绝
        [TestCase(42, 40, true)]  // 跳号容忍（PUB 慢加入/掉帧）
        public void IsNewer_WorkedExamples(int candidateSeq, int lastConsumedSeq, bool expected)
        {
            Assert.That(DetectionFreshness.IsNewer(candidateSeq, lastConsumedSeq), Is.EqualTo(expected));
        }

        [Test]
        public void SeamDetectionConsts_AreDocumentedDefaults()
        {
            Assert.That(SangoSeamConfig.DetectionEndpoint, Is.EqualTo("tcp://127.0.0.1:5557"));
            Assert.That(SangoSeamConfig.DetectionTopic, Is.EqualTo("sango.detection"));
            Assert.That(SangoSeamConfig.ConsumerCliFlag, Is.EqualTo("--sango-publisher"),
                "seam 总闸：消费端与发布器同旗标使能");
        }
    }
}
