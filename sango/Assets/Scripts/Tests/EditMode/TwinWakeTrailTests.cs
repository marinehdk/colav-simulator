using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    public class TwinWakeTrailTests
    {
        [Test]
        public void TrailSurvivesTurnStopsSpawningAtRestAndExpires()
        {
            var root = new GameObject("wake regression");
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinWakeTrail");
            var trail = root.AddComponent(type);
            var advance = type.GetMethod("Advance");
            try
            {
                type.GetMethod("Initialize").Invoke(trail, new object[] { 45f, 8f, true });
                void Step(float t, Vector3 point, Vector3 forward, float speed, Vector3 current)
                    => advance.Invoke(trail, new object[] { t, 1f, point, forward, speed, current });
                Step(0, Vector3.zero, Vector3.forward, 8, Vector3.zero);
                var world = (GameObject)type.GetField("m_World", BindingFlags.Instance | BindingFlags.NonPublic).GetValue(trail);
                Assert.That(world, Is.Not.Null);
                var first = world.transform.GetChild(0).GetComponent<WaterDecal>();
                Assert.That(first.material.FindPass("Deformation"), Is.GreaterThanOrEqualTo(0));
                Step(1, Vector3.forward * 8, Vector3.forward, 8, Vector3.zero);
                Step(2, new Vector3(8, 0, 8), Vector3.right, 8, Vector3.zero);
                Assert.That(first.transform.position, Is.EqualTo(Vector3.zero));
                Assert.That(Vector3.Dot(first.transform.forward, Vector3.forward), Is.GreaterThan(0.99f));
                Assert.That((int)type.GetProperty("ActiveSamples").GetValue(trail), Is.EqualTo(3));
                Step(3, new Vector3(8, 0, 8), Vector3.right, 0, Vector3.right * 0.5f);
                Assert.That((int)type.GetProperty("ActiveSamples").GetValue(trail), Is.EqualTo(3));
                Assert.That(first.transform.position.x, Is.EqualTo(0.5f).Within(1e-5));
                Step(35, new Vector3(8, 0, 8), Vector3.right, 0, Vector3.zero);
                Assert.That((int)type.GetProperty("ActiveSamples").GetValue(trail), Is.Zero);
                Assert.That(first.enabled, Is.False);
                Step(36, new Vector3(8, 0, 8), Vector3.right, 8, Vector3.zero);
                Step(37, new Vector3(1000, 0, 1000), Vector3.right, 8, Vector3.zero);
                Assert.That((int)type.GetProperty("ActiveSamples").GetValue(trail), Is.EqualTo(1), "Seek must not leave a connection across the scene.");
            }
            finally
            {
                // EditMode components do not receive all runtime destruction callbacks.
                type.GetMethod("OnDestroy", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(trail, null);
                Object.DestroyImmediate(root);
            }
        }
    }
}
