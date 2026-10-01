using System.Collections.Concurrent;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class DetectionOverlayCadenceTests
    {
        [TestCase(false)]
        [TestCase(true)]
        public void ResultSurvivesRenderFramesWithoutNewInference(bool empty)
        {
            var consumerType = TestReflection.FindAssemblyCSharpType("Sango.DetectionResultConsumer");
            var overlayType = TestReflection.FindAssemblyCSharpType("Sango.DetectionOverlay");
            var go = new GameObject("Detection cadence test");
            try
            {
                var consumer = go.AddComponent(consumerType);
                var overlay = go.AddComponent(overlayType);
                var result = new DetectionResult
                {
                    frame_seq = 10,
                    frame_time_s = Time.timeAsDouble,
                    source = "yolo-detector",
                    detections = empty ? new DetectionResult.Box[0] : new[] {
                        new DetectionResult.Box { box_xyxy = new[] { 10f, 20f, 30f, 40f }, class_id = 8, class_name = "boat" }
                    },
                };
                var inbox = new ConcurrentQueue<DetectionResult>();
                inbox.Enqueue(result);
                consumerType.GetField("_inbox", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(consumer, inbox);
                consumerType.GetField("_running", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(consumer, true);
                overlayType.GetField("liveSource").SetValue(overlay, consumer);
                var update = overlayType.GetMethod("Update", BindingFlags.Instance | BindingFlags.NonPublic);
                var cache = overlayType.GetField("_liveFrame", BindingFlags.Instance | BindingFlags.NonPublic);
                update.Invoke(overlay, null);
                Assert.That(cache.GetValue(overlay), Is.SameAs(result));
                update.Invoke(overlay, null);
                Assert.That(cache.GetValue(overlay), Is.SameAs(result),
                    "A render frame without inference must preserve the still-fresh live result, including authoritative empty detections.");
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
