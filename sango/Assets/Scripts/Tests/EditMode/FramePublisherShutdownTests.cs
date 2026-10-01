using System;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class FramePublisherShutdownTests
    {
        [Test]
        public void StopWaitsForInFlightEncoderBeforeReturning()
        {
            var type = TestReflection.FindAssemblyCSharpType("Sango.FramePublisher");
            var frameType = type.GetNestedType("EncodedFrame", BindingFlags.NonPublic);
            var completionType = typeof(TaskCompletionSource<>).MakeGenericType(frameType);
            var completion = Activator.CreateInstance(completionType);
            var task = (Task)completionType.GetProperty("Task").GetValue(completion);
            var setResult = completionType.GetMethod("SetResult");
            var frame = Activator.CreateInstance(frameType);
            var go = new GameObject("Publisher shutdown test");
            var publisher = go.AddComponent(type);
            try
            {
                type.GetField("_encoder", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(publisher, task);
                ThreadPool.QueueUserWorkItem(_ =>
                {
                    Thread.Sleep(80);
                    setResult.Invoke(completion, new[] { frame });
                });
                type.GetMethod("StopPublishing").Invoke(publisher, null);
                Assert.That(task.IsCompleted, Is.True,
                    "Stop must not leave an encoder retaining a full-resolution frame in the background.");
                Assert.That(type.GetProperty("Active").GetValue(publisher), Is.False);
            }
            finally
            {
                task.Wait();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }
    }
}
