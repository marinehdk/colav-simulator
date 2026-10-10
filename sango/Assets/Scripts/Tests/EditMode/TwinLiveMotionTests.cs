using System;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class TwinLiveMotionTests
    {
        [Test]
        public void LiveDriver_RendersBetweenSnapshotsRatherThanHoldingLatest()
        {
            var type = AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType("Sango.TwinSessionDriver")).First(t => t != null);
            var go = new GameObject("Twin motion regression");
            try
            {
                var driver = go.AddComponent(type);
                ((Behaviour)driver).enabled = false;
                type.GetField("runtimeEnabled").SetValue(driver, true);
                var offer = type.GetMethod("OfferReplayFrame");
                var drain = type.GetMethod("DrainInbox", BindingFlags.NonPublic | BindingFlags.Instance);
                double now = Time.realtimeSinceStartupAsDouble;
                var sampleTime = type.GetMethod("SamplePoseTime", BindingFlags.NonPublic | BindingFlags.Instance);
                for (int i = 0; i <= 13; i++)
                {
                    double wall = now - 6.75 + i * 0.5;
                    var frame = new ColavTelemetry { seq = i + 1, sim_time = i * 0.5, state = "RUNNING",
                        truth = new[] { new ColavTelemetry.ShipEntry { id = 0, east = i * 5.0, north = 6957500 + i * 5.0 } } };
                    offer.Invoke(driver, new object[] { frame });
                    drain.Invoke(driver, new object[] { wall });
                    sampleTime.Invoke(driver, new object[] { wall });
                }
                double render = (double)type.GetProperty("RenderSimTime").GetValue(driver);
                float alpha = TwinPose.InterpolationAlpha(render, 3.5, 4.0);
                Assert.That(alpha, Is.InRange(0.45f, 0.7f), "30 FPS must traverse received positions, not clamp every frame to alpha=1");
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [TestCase(1.0)]
        [TestCase(2.0)]
        [TestCase(5.0)]
        public void LiveDriver_ContinuousMotionSurvivesRepeatedSimTimeAndPause(double rate)
        {
            var type = AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType("Sango.TwinSessionDriver")).First(t => t != null);
            var go = new GameObject("Twin cadence regression");
            try
            {
                var driver = go.AddComponent(type);
                ((Behaviour)driver).enabled = false;
                type.GetField("runtimeEnabled").SetValue(driver, true);
                var offer = type.GetMethod("OfferReplayFrame");
                var drain = type.GetMethod("DrainInbox", BindingFlags.NonPublic | BindingFlags.Instance);
                var sample = type.GetMethod("SamplePoseTime", BindingFlags.NonPublic | BindingFlags.Instance);
                void Frame(int seq, double sim, double wall, string state = "RUNNING")
                {
                    var frame = new ColavTelemetry { seq = seq, sim_time = sim, state = state,
                        playback = new ColavTelemetry.Playback { effective_multiplier = rate },
                        truth = new[] { new ColavTelemetry.ShipEntry { id = 0, east = sim * 10, north = 6957500 + sim * 10 } } };
                    offer.Invoke(driver, new object[] { frame });
                    drain.Invoke(driver, new object[] { wall });
                }
                double Sample(double wall) => (double)sample.Invoke(driver, new object[] { wall });
                double interval = 0.5 / rate;
                int seq = 1;
                for (int i = 0; i <= (int)(8 * rate); i++)
                {
                    Frame(seq++, i * 0.5, i * interval);
                    Sample(i * interval);
                }
                double wallNow = 4.0;
                double before = Sample(wallNow + interval * 0.4);
                Frame(seq++, 4 * rate, wallNow + interval * 0.4);
                Assert.That(Sample(wallNow + interval * 0.6), Is.GreaterThan(before), "repeated time cannot erase the live buffer");
                Frame(seq - 1, 4 * rate, wallNow + interval * 0.7, "PAUSED");
                Assert.That(Sample(100), Is.EqualTo(4 * rate), "pause heartbeat at same seq must freeze immediately");
                Frame(seq++, 4 * rate, 101);
                Assert.That(Sample(101), Is.EqualTo(4 * rate), "resume cannot rewind buffered truth");
                Frame(seq++, 100, 200);
                Assert.That(Sample(200), Is.EqualTo(100), "large source jump must snap rather than interpolate across jump");
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
    }
}
