using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class BuoyancyDesignDatumTests
    {
        [Test]
        public void RenderedHeaveAndTiltDoNotFeedBackIntoAbsoluteWaterTarget()
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                go.transform.position = new Vector3(10f, -1.5f, 20f);
                var type = TestReflection.FindAssemblyCSharpType("Sango.VesselBuoyancy");
                var buoyancy = go.AddComponent(type);
                var sample = type.GetMethod("SampleAtDesignPose", BindingFlags.Instance | BindingFlags.NonPublic);
                var centroid = new Vector3(0.5f, -0.2f, 0.7f);
                var before = (Vector3)sample.Invoke(buoyancy, new object[] { centroid });
                go.transform.position += Vector3.up * 0.8f;
                go.transform.rotation = Quaternion.Euler(5f, 0f, 6f);
                var after = (Vector3)sample.Invoke(buoyancy, new object[] { centroid });
                Assert.That(Vector3.Distance(before, after), Is.LessThan(1e-5f),
                    "Absolute target must query at design datum; current rendered heave/tilt must not cancel the wave input.");
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
