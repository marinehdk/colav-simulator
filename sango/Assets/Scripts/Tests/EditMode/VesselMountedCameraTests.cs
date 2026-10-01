using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class VesselMountedCameraTests
    {
        [Test]
        public void BowCameraUsesMountPositionAndInheritsVesselAttitude()
        {
            var ship = new GameObject("Mounted camera vessel");
            var cameraGo = new GameObject("Mounted camera test", typeof(Camera));
            try
            {
                ship.transform.position = new Vector3(10f, 0.5f, 20f);
                ship.transform.rotation = Quaternion.Euler(5f, 90f, 6f);
                var mount = new GameObject("Bow mount").transform;
                mount.SetParent(ship.transform, false);
                mount.localPosition = new Vector3(0f, 5.75f, 20.5f);
                var type = TestReflection.FindAssemblyCSharpType("Sango.CameraRig");
                var rig = cameraGo.AddComponent(type);
                type.GetField("controlledCamera").SetValue(rig, cameraGo.GetComponent<Camera>());
                type.GetField("followShip").SetValue(rig, ship.transform);
                type.GetField("bowMount").SetValue(rig, mount);
                type.GetField("transitionSeconds").SetValue(rig, 0f);
                type.GetMethod("SetView").Invoke(rig, new object[] { CameraView.Bow });
                type.GetField("m_Blend", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(rig, 1f);
                type.GetMethod("LateUpdate", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(rig, null);
                Assert.That(Vector3.Distance(cameraGo.transform.position, mount.position), Is.LessThan(1e-4f));
                var expected = mount.rotation * Quaternion.Euler(-CameraViews.BowPitchDeg, 0f, 0f);
                Assert.That(Quaternion.Angle(cameraGo.transform.rotation, expected), Is.LessThan(0.01f));
            }
            finally { Object.DestroyImmediate(cameraGo); Object.DestroyImmediate(ship); }
        }
    }
}
