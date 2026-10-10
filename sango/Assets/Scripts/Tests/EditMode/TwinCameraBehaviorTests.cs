using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class TwinCameraBehaviorTests
    {
        [TestCase(0f)] [TestCase(90f)] [TestCase(270f)]
        public void OverviewKeepsShipSmallAndHorizonVisible(float heading)
        {
            var pose = CameraViews.Overview(Vector3.zero, heading, 45);
            Assert.That(pose.Position.magnitude, Is.GreaterThan(190));
            Assert.That(pose.PitchDeg, Is.GreaterThan(-15));
            var go = new GameObject("overview-test");
            try
            {
                var camera = go.AddComponent<Camera>();
                camera.aspect = 16f / 9; camera.fieldOfView = pose.FieldOfView;
                go.transform.SetPositionAndRotation(pose.Position, Quaternion.Euler(-pose.PitchDeg, pose.YawDeg, 0));
                var forward = Quaternion.Euler(0, heading, 0) * Vector3.forward;
                var center = camera.WorldToViewportPoint(Vector3.up * 3);
                var bow = camera.WorldToViewportPoint(forward * 22.5f + Vector3.up * 12);
                var stern = camera.WorldToViewportPoint(-forward * 22.5f);
                Assert.That(center.y, Is.InRange(.35f, .5f), "ownship sits below center with sea ahead");
                Assert.That(Mathf.Abs(bow.y - stern.y), Is.LessThan(.1f), "ownship occupies under 10% of image height");
            }
            finally { Object.DestroyImmediate(go); }
        }

        [Test]
        public void TargetTrackingFollowsMotionAndPresetReturnsToOwnship()
        {
            var go = new GameObject("tracking-camera");
            var own = new GameObject("ownship");
            var target = new GameObject("selected-target");
            try
            {
                var camera = go.AddComponent<Camera>();
                var type = TestReflection.FindAssemblyCSharpType("Sango.CameraRig");
                var rig = go.AddComponent(type);
                type.GetField("controlledCamera").SetValue(rig, camera);
                type.GetField("followShip").SetValue(rig, own.transform);
                type.GetField("twinOverviewLengthM").SetValue(rig, 45f);
                type.GetField("transitionSeconds").SetValue(rig, .01f);
                type.GetMethod("TrackTarget").Invoke(rig, new object[] { target.transform, 12f });
                // Verify steady tracking independently of editor frame timing during view transition.
                type.GetField("m_Blend", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(rig, 1f);
                var update = type.GetMethod("LateUpdate", BindingFlags.Instance | BindingFlags.NonPublic);
                update.Invoke(rig, null);
                var before = camera.transform.position;
                target.transform.position += new Vector3(100, 0, 200);
                update.Invoke(rig, null);
                Assert.That((camera.transform.position - before - new Vector3(100, 0, 200)).magnitude, Is.LessThan(.01f));
                Assert.That(camera.fieldOfView, Is.EqualTo(50));
                Assert.That((bool)type.GetProperty("TargetTrackingActive").GetValue(rig), Is.True);
                type.GetMethod("SetView").Invoke(rig, new object[] { CameraView.Chase });
                update.Invoke(rig, null);
                Assert.That((bool)type.GetProperty("TargetTrackingActive").GetValue(rig), Is.False);
                Assert.That((camera.transform.position - CameraViews.Overview(Vector3.zero, 0, 45).Position).magnitude, Is.LessThan(.01f));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(own); Object.DestroyImmediate(target); }
        }
    }
}
