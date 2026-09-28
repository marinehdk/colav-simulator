using System.IO;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// M3 缝钉子③ fixture 测试（spec #86 Testing Decisions / PLAN §5 M3 验收 3）：
    /// 真实录制的 compact-v1 WS 快照（Assets/Tests/Fixtures/telemetry-sample.json，
    /// provenance 见 evidence m3-build-log.md）反序列化成功，断言 twin 消费的子集：
    /// transport.schema_version=="colav.telemetry.compact@1"、truth.Length>0、
    /// 本船/目标 id + east/north + psi(rad) + sog，且被剥字段（measurements/tracks/colav）
    /// 可缺省（fixture 本体即无这三键，反序列化不炸即为行为）。
    /// 期望值来自录制时的后端事实（session head_on/rule14/vo/god），不回声实现。
    /// </summary>
    public class ColavTelemetryDeserializeTests
    {
        const string k_FixtureRelPath = "Tests/Fixtures/telemetry-sample.json";

        static ColavTelemetry LoadFixture()
        {
            string path = Path.Combine(Application.dataPath, k_FixtureRelPath);
            Assert.That(File.Exists(path), Is.True, $"fixture 缺失：{path}");
            return ColavTelemetry.FromJson(File.ReadAllText(path));
        }

        [Test]
        public void Fixture_TransportEnvelopeIsCompactV1()
        {
            var t = LoadFixture();
            Assert.That(t.schema_version, Is.EqualTo("1.0"), "compact 信封仍是 schema 1.0 文档（PLAN §8.3）");
            Assert.That(t.transport, Is.Not.Null);
            Assert.That(t.transport.schema_version, Is.EqualTo("colav.telemetry.compact@1"));
        }

        [Test]
        public void Fixture_TruthShips_TwinConsumedFields()
        {
            var t = LoadFixture();
            Assert.That(t.truth, Is.Not.Null);
            Assert.That(t.truth.Length, Is.GreaterThanOrEqualTo(2), "head_on 场景：本船 + 1 目标");

            var own = t.truth[0];
            Assert.That(own.id, Is.EqualTo(0), "truth[0] = 本船");
            Assert.That(own.mmsi, Is.EqualTo(100));
            Assert.That(own.length, Is.EqualTo(8.45f).Within(1e-4f));
            Assert.That(own.width, Is.EqualTo(2.71f).Within(1e-4f));
            Assert.That(own.east, Is.EqualTo(39632.9978f).Within(0.5f), "对遇 26.5s 后本船东向位置（录制事实）");
            Assert.That(own.north, Is.EqualTo(6957632.9978f).Within(0.5f));
            Assert.That(own.psi, Is.EqualTo(0.7853982f).Within(1e-4f), "ψ=π/4（北偏东 45°，rad）");
            Assert.That(own.sog, Is.EqualTo(7.097f).Within(0.01f));
            Assert.That(own.active, Is.True);

            var target = t.truth[1];
            Assert.That(target.id, Is.EqualTo(1), "truth[1] = 目标");
            Assert.That(target.east, Is.EqualTo(41368.8317f).Within(0.5f));
            Assert.That(target.north, Is.EqualTo(6959368.8317f).Within(0.5f));
            Assert.That(target.psi, Is.EqualTo(-2.3561945f).Within(1e-4f), "ψ=-3π/4（对遇反向）");
            Assert.That(target.sog, Is.EqualTo(7f).Within(0.01f));
        }

        [Test]
        public void Fixture_StrippedFieldsTolerated_DeserializeSucceeds()
        {
            // compact-v1 每船剥掉 measurements/tracks/colav（main.py:178-181）——
            // 契约类不声明这三键且反序列化成功 = "可缺省"（PLAN §8 风险 5）。
            var t = LoadFixture();
            Assert.That(t.truth.Length, Is.EqualTo(2));
            Assert.That(t.truth[0].sog, Is.GreaterThan(0f), "剥字段后业务字段仍在");
        }

        [Test]
        public void Fixture_EnvelopeSeqSimTimeStatePlayback()
        {
            var t = LoadFixture();
            Assert.That(t.seq, Is.EqualTo(54));
            Assert.That(t.sim_time, Is.EqualTo(26.5).Within(1e-6));
            Assert.That(t.state, Is.EqualTo("RUNNING"));
            Assert.That(t.playback, Is.Not.Null);
            Assert.That(t.playback.requested_multiplier, Is.EqualTo(1.0).Within(1e-9));
            Assert.That(t.playback.effective_multiplier, Is.EqualTo(0.9997006040878215).Within(1e-9));
            Assert.That(t.playback.realtime_limited, Is.False);
        }
    }
}
