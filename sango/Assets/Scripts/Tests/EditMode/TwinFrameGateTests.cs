using NUnit.Framework;
using Sango;

namespace Sango.Tests
{
    /// <summary>
    /// P2-S1 seq 闸门/信封守卫测试（spec #89；纯函数）。
    /// seq 语义按 S0 实证校准（evidence/p2s0-notes.md 发现 1：求解步 0.5s、步间 ~10Hz
    /// 重发同 seq 快照，实序 [0,1,1,1,1,2,2,2,2,2,3,3]）——同值重发是常态而非异常，
    /// 唯倒退判会话重建。
    /// </summary>
    public class TwinFrameGateTests
    {
        [Test]
        public void FirstFrame_Accepts()
        {
            Assert.That(TwinFrameGate.Classify(0, -1), Is.EqualTo(TwinFrameDecision.Accept));
            Assert.That(TwinFrameGate.Classify(42, -1), Is.EqualTo(TwinFrameDecision.Accept));
        }

        [Test]
        public void SameSeqResend_IsDuplicate()
        {
            // S0 实序 [0,1,1,1,1,2,2,...]：步间重发同 seq 快照必须丢弃（spec #89 去重）。
            Assert.That(TwinFrameGate.Classify(1, 1), Is.EqualTo(TwinFrameDecision.Duplicate));
            Assert.That(TwinFrameGate.Classify(2, 2), Is.EqualTo(TwinFrameDecision.Duplicate));
        }

        [Test]
        public void Advance_Accepts_AndRegression_Rebuilds()
        {
            Assert.That(TwinFrameGate.Classify(2, 1), Is.EqualTo(TwinFrameDecision.Accept));
            Assert.That(TwinFrameGate.Classify(3, 2), Is.EqualTo(TwinFrameDecision.Accept));
            Assert.That(TwinFrameGate.Classify(1, 3), Is.EqualTo(TwinFrameDecision.Rebuild));
            Assert.That(TwinFrameGate.Classify(0, 3), Is.EqualTo(TwinFrameDecision.Rebuild));
        }

        [Test]
        public void Envelope_ValidCompactRequiresTransportSchemaAndTruth()
        {
            Assert.That(TwinEnvelope.IsValidCompact(null), Is.False);

            var noTransport = new ColavTelemetry { truth = new[] { new ColavTelemetry.ShipEntry() } };
            Assert.That(TwinEnvelope.IsValidCompact(noTransport), Is.False);

            var wrongSchema = new ColavTelemetry
            {
                transport = new ColavTelemetry.Transport { schema_version = "colav.telemetry.static-once@1" },
                truth = new[] { new ColavTelemetry.ShipEntry() },
            };
            Assert.That(TwinEnvelope.IsValidCompact(wrongSchema), Is.False, "static-once 流不是 twin 消费对象");

            var noTruth = new ColavTelemetry
            {
                transport = new ColavTelemetry.Transport { schema_version = TwinEnvelope.CompactSchemaVersion },
                truth = new ColavTelemetry.ShipEntry[0],
            };
            Assert.That(TwinEnvelope.IsValidCompact(noTruth), Is.False, "truth[0]=本船，缺失即不可锚定");

            var valid = new ColavTelemetry
            {
                transport = new ColavTelemetry.Transport
                {
                    schema_version = "colav.telemetry.compact@1",
                    static_included = true,
                },
                truth = new[] { new ColavTelemetry.ShipEntry { id = 0 } },
            };
            Assert.That(TwinEnvelope.IsValidCompact(valid), Is.True);
        }
    }
}
