using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    public class TwinNativeWaterTests
    {
        [TestCase(double.NaN, 0, "RUNNING", false)]
        [TestCase(0, 0, "RUNNING", false)]
        [TestCase(0, 1, "CREATED", false)]
        [TestCase(0, 1, "PAUSED", false)]
        [TestCase(0, 1, "FINISHED", false)]
        [TestCase(0, 1, "FAILED", false)]
        [TestCase(1, 0, "RUNNING", false)]
        [TestCase(0, 0.016, "RUNNING", true)]
        [TestCase(0, 0.08, "RUNNING", true)]
        [TestCase(0, 0.016, null, true)]
        public void PropulsionWakeRequiresAdvancingPresentedTruth(double previous, double current, string state, bool expected)
            => Assert.That(TwinWaterMotion.IsAdvancing(previous, current, state), Is.EqualTo(expected));

        [Test]
        public void FoamRegionRemainsFixedDuringOrdinaryMotionAndRecentersBeforeSourcesLeave()
        {
            var center = new Vector3(21000, 0, -5000);
            var size = new Vector2(108, 108);
            Assert.That(TwinWaterMotion.RegionNeedsRecenter(center, center + new Vector3(1, 5, 0), size), Is.False);
            Assert.That(TwinWaterMotion.RegionNeedsRecenter(center, center + new Vector3(10, 0, 0), size), Is.False);
            Assert.That(TwinWaterMotion.RegionNeedsRecenter(center, center + new Vector3(11, 0, 0), size), Is.True);
            Assert.That(TwinWaterMotion.RegionNeedsRecenter(center, center + new Vector3(0, 0, -11), size), Is.True);
            // FCB45 maximum bow/stern corner radius ~37m, plus 10.8m drift <54m half-region.
            Assert.That(37f + size.x * 0.1f, Is.LessThan(size.x * 0.5f));
        }

        [Test]
        public void NativeFoamIsShortSternSourceAndStopsInjectingAtZeroSpeed()
        {
            var root = new GameObject("native-water-test");
            root.SetActive(false);
            try
            {
                var type = TestReflection.FindAssemblyCSharpType("Sango.BoatWaterDecals");
                var gate = root.AddComponent(type);
                var bow = new GameObject("bow").AddComponent<WaterDecal>();
                bow.transform.SetParent(root.transform);
                var wash = new GameObject("wash").AddComponent<WaterDecal>();
                wash.transform.SetParent(root.transform);
                type.GetField("bowDecal").SetValue(gate, bow);
                type.GetField("wakeDecal").SetValue(gate, wash);
                type.GetField("loaMeters").SetValue(gate, 45f);
                type.GetMethod("ConfigureTwinWater").Invoke(gate, new object[] { null, 8f, false });
                var shader = UnityEditor.AssetDatabase.LoadAssetAtPath<Shader>("Assets/Art/WaterDecals/TwinFoamInjector.shader");
                Assert.That(shader, Is.Not.Null);
                Assert.That(UnityEditor.ShaderUtil.ShaderHasError(shader), Is.False);
                Assert.That(wash.material.shader, Is.EqualTo(shader));
                Assert.That(wash.material.GetFloat("_AffectDeformation"), Is.Zero);
                Assert.That(wash.material.GetFloat("_AffectFoam"), Is.EqualTo(1));
                Assert.That(wash.material.GetTexture("_Foam_Texture"), Is.Not.Null);
                Assert.That(wash.regionSize.y, Is.LessThan(20.1f));
                Assert.That(wash.transform.localPosition.z, Is.LessThan(-22.5f));
                type.GetMethod("ApplySpeed").Invoke(gate, new object[] { 8f });
                Assert.That(wash.enabled, Is.True);
                Assert.That(wash.surfaceFoamDimmer, Is.GreaterThan(0));
                type.GetMethod("ApplySpeed").Invoke(gate, new object[] { 0f });
                Assert.That(wash.enabled, Is.False);
                Assert.That(wash.surfaceFoamDimmer, Is.Zero);
                type.GetMethod("OnDestroy", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(gate, null);
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }

        [Test]
        public void ReattachRetargetsCurrentShipAndDiscardsOldSceneFreePose()
        {
            var host = new GameObject("reattach-test"); host.SetActive(false);
            var cameraGo = new GameObject("reattach-camera"); cameraGo.SetActive(false);
            var ship = new GameObject("current-vessel");
            try
            {
                var cameraType = TestReflection.FindAssemblyCSharpType("Sango.CameraRig");
                var cameraRig = cameraGo.AddComponent(cameraType);
                cameraType.GetMethod("SetFreePose").Invoke(cameraRig, new object[] { new Vector3(1, 10, 2), 45f, -30f, 60f });
                Assert.That((bool)cameraType.GetProperty("FreePoseActive").GetValue(cameraRig), Is.True);
                var bridgeType = TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeService");
                var bridge = host.AddComponent(bridgeType);
                bridgeType.GetField("cameraRig").SetValue(bridge, cameraRig);
                bridgeType.GetMethod("RetargetCameraFollow", BindingFlags.NonPublic | BindingFlags.Instance)
                    .Invoke(bridge, new object[] { ship.transform, ship.name });
                Assert.That(cameraType.GetField("followShip").GetValue(cameraRig), Is.EqualTo(ship.transform));
                Assert.That((bool)cameraType.GetProperty("FreePoseActive").GetValue(cameraRig), Is.False);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(host);
                UnityEngine.Object.DestroyImmediate(cameraGo);
                UnityEngine.Object.DestroyImmediate(ship);
            }
        }

        [Test]
        public void DetachPreservesMastRigBeforeItsVesselIsDestroyed()
        {
            var host = new GameObject("water-bridge-test"); host.SetActive(false);
            var ship = new GameObject("old-water-vessel");
            var rigGo = new GameObject("water-mast-test");
            var rig = rigGo.AddComponent<Sango.Vessels.Mast.MastSensorRig>();
            try
            {
                Assert.That(rig.Attach(ship.transform), Is.True);
                var type = TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeService");
                var service = host.AddComponent(type);
                type.GetField("mastRig").SetValue(service, rig);
                type.GetMethod("DetachDataPlane", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(service, null);
                Assert.That(rig.transform.parent, Is.Null);
                UnityEngine.Object.DestroyImmediate(ship); ship = null;
                Assert.That(rig != null, Is.True);
                Assert.That(rig.Attached, Is.False);
                var next = new GameObject("next-water-vessel");
                try { Assert.That(rig.Attach(next.transform), Is.True); rig.Detach(); }
                finally { UnityEngine.Object.DestroyImmediate(next); }
            }
            finally
            {
                if (rigGo != null) UnityEngine.Object.DestroyImmediate(rigGo);
                if (ship != null) UnityEngine.Object.DestroyImmediate(ship);
                UnityEngine.Object.DestroyImmediate(host);
            }
        }

        [Test]
        public void TwinCannotDrawRibbonOrRingOrSuppressWaterFoam()
        {
            var root = new GameObject("native-rig-test");
            root.SetActive(false);
            try
            {
                var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cube.transform.SetParent(root.transform, false);
                cube.transform.localScale = new Vector3(8, 2, 45);
                var gateType = TestReflection.FindAssemblyCSharpType("Sango.BoatWaterDecals");
                var gate = root.AddComponent(gateType);
                var wash = new GameObject("wash").AddComponent<WaterDecal>();
                wash.transform.SetParent(root.transform);
                gateType.GetField("wakeDecal").SetValue(gate, wash);
                var type = TestReflection.FindAssemblyCSharpType("Sango.WakeFoamRig");
                var rig = root.AddComponent(type);
                type.GetField("twinSurfaceWake").SetValue(rig, true);
                type.GetField("decals").SetValue(rig, gate);
                type.GetMethod("BuildRig", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(rig, null);
                M8Quality.SetTier(M8QualityTier.High);
                type.GetMethod("ApplySpeed").Invoke(rig, new object[] { 8f });
                type.GetMethod("ApplyDecalSuppression").Invoke(rig, null);
                Assert.That(wash.enabled, Is.True);
                Assert.That(GameObject.Find("WakeFoam.World/WakeRibbon").GetComponent<MeshRenderer>().enabled, Is.False);
                Assert.That(root.transform.Find("WakeFoamRig/WaterlineFoamRing").GetComponent<MeshRenderer>().enabled, Is.False);
                Assert.That((int)type.GetProperty("LastWaterQueries").GetValue(rig), Is.Zero);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(root);
                var orphan = GameObject.Find("WakeFoam.World");
                if (orphan != null) UnityEngine.Object.DestroyImmediate(orphan);
                M8Quality.SetTier(M8QualityTier.High);
            }
        }
    }
}
