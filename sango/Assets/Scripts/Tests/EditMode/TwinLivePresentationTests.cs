using System;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using Sango;

namespace Sango.Tests
{
    public class TwinLivePresentationTests
    {
        static ColavTelemetry Frame(int seq, double sim, double? rate = null, string state = "RUNNING")
            => new ColavTelemetry { seq = seq, sim_time = sim, state = state,
                playback = rate.HasValue ? new ColavTelemetry.Playback { effective_multiplier = rate.Value } : null,
                truth = new[] { new ColavTelemetry.ShipEntry { east = 39500 + sim * 7, north = 6957500 + sim * 7 } } };

        [TestCase(1.0)] [TestCase(2.0)] [TestCase(5.0)]
        public void SparsePlaybackAndSolverJitter_DoNotFreezeOrJump(double rate)
        {
            var buffer = new TwinLivePresentation();
            buffer.Offer(Frame(0, 0, rate), 0);
            int seq = 1, moving = 0;
            double prior = 0, biggestStep = 0;
            for (int tick = 1; tick <= 600; tick++)
            {
                double wall = tick / 60.0;
                // A solver stalls for 0.7s once each 2s, then delivers its backlog.
                bool stalled = wall % 2.0 < 0.7;
                if (!stalled)
                    while (seq * 0.5 / rate <= wall) { buffer.Offer(Frame(seq, seq * 0.5), wall); seq++; }
                buffer.Bracket(wall, out var a, out var b, out var time);
                Assert.That(time, Is.LessThanOrEqualTo(b.sim_time));
                double position = TwinPose.LerpEntries(a.truth[0], b.truth[0], TwinPose.InterpolationAlpha(time, a.sim_time, b.sim_time)).north;
                if (wall > 4.0)
                {
                    double step = position - prior;
                    Assert.That(step, Is.GreaterThan(0), "every rendered frame must advance after the buffer fills");
                    biggestStep = System.Math.Max(biggestStep, step); moving++;
                }
                prior = position;
            }
            Assert.That(moving, Is.EqualTo(360));
            Assert.That(biggestStep, Is.LessThanOrEqualTo(rate * 7 / 60 + 0.001));
            Assert.That(buffer.Rate, Is.EqualTo(rate), "missing playback must retain 2x/5x");
        }

        [Serializable] class Trace { public Sample[] samples; }
        [Serializable] class Sample { public double wall_s, sim_time, rate, east, north; public int seq; public string state; }

        [Test]
        public void RecordedSparseCompactCadence_RendersEveryFrameAfterWarmup()
        {
            var trace = JsonUtility.FromJson<Trace>(File.ReadAllText(Path.Combine(Application.dataPath,
                "Tests/Fixtures/twin-live-cadence.json")));
            var buffer = new TwinLivePresentation();
            int index = 0, moving = 0;
            double prior = 0, largestStep = 0;
            for (int tick = 0; tick <= 720; tick++)
            {
                double wall = tick / 60.0;
                while (index < trace.samples.Length && trace.samples[index].wall_s <= wall)
                {
                    var s = trace.samples[index++];
                    var frame = Frame(s.seq, s.sim_time, s.rate > 0 ? s.rate : (double?)null, s.state);
                    frame.truth[0].east = s.east; frame.truth[0].north = s.north;
                    buffer.Offer(frame, wall);
                }
                if (!buffer.Bracket(wall, out var a, out var b, out var time)) continue;
                var ship = TwinPose.LerpEntries(a.truth[0], b.truth[0], TwinPose.InterpolationAlpha(time, a.sim_time, b.sim_time));
                if (wall > 5)
                {
                    double step = ship.north - prior;
                    Assert.That(step, Is.GreaterThan(0), "recorded solver jitter cannot hold presentation frames");
                    largestStep = Math.Max(largestStep, step); moving++;
                }
                prior = ship.north;
            }
            Assert.That(moving, Is.EqualTo(420));
            Assert.That(largestStep, Is.LessThan(0.3), "no solver-sized position jumps");
        }

        [Test]
        public void PauseResumeAndReset_KeepKnownTruthAndRate()
        {
            var buffer = new TwinLivePresentation();
            buffer.Offer(Frame(1, 0, 2), 0);
            buffer.Offer(Frame(2, 1), 0.5);
            buffer.ObservePlayback(Frame(2, 1, null, "PAUSED"), 0.6);
            Assert.That(buffer.Sample(10), Is.EqualTo(1));
            buffer.ObservePlayback(Frame(2, 1), 10);
            Assert.That(buffer.Sample(10), Is.EqualTo(1));
            Assert.That(buffer.Rate, Is.EqualTo(2));
            buffer.Reset(); Assert.That(double.IsNaN(buffer.Sample(11)), Is.True);
        }
    }
}
