using System;
using System.Reflection;
using NUnit.Framework;
using Sango;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    public class TwinEnvironmentTests
    {
        [Test]
        public void CompassFromVectorsAndRollInterpolation_PreserveTruth()
        {
            var e = new TwinEnvironment { enabled = true, current_speed_mps = 2, current_from_deg = 90 };
            Assert.That(e.CurrentVelocity.x, Is.EqualTo(-2).Within(1e-5));
            Assert.That(e.CurrentVelocity.z, Is.EqualTo(0).Within(1e-5));
            Assert.That(TwinEnvironment.WaterOrientation(0), Is.EqualTo(270));
            var a = new ColavTelemetry.ShipEntry { has_roll = true, roll_rad = 0 };
            var b = new ColavTelemetry.ShipEntry { has_roll = true, roll_rad = 0.2f };
            Assert.That(TwinPose.LerpEntries(a, b, 0.5f).roll_rad, Is.EqualTo(0.1f).Within(1e-5));
        }

        [Test]
        public void ReplayKeepsRecordedEnvironmentAndNativeRoll()
        {
            var environment = new TwinEnvironment { enabled = true, time_of_day_hours = 23, wave_hs_m = 2 };
            var context = new ReplayStaticContext { environment = environment };
            var frame = new ReplayFrame { sequence = 1, sim_time = 0,
                payload = new ReplayShipPayload { Ship0 = new ReplayShipSlot { id = 0, state = new double[] { 0, 0, 0, 1, 0, 0 }, active = true } },
                gnc_balance = new ReplayRecordedBalance { roll_deg = 10 } };
            var telemetry = ReplayWindowAdapter.ToTelemetry(frame, context);
            Assert.That(telemetry.environment, Is.SameAs(environment));
            Assert.That(telemetry.truth[0].has_roll, Is.True);
            Assert.That(telemetry.truth[0].roll_rad, Is.EqualTo(10 * Mathf.Deg2Rad).Within(1e-6));
        }

        [TestCase(0f)] [TestCase(90f)] [TestCase(180f)]
        public void NativeRollAppliesEvenWithoutWater_AtCorrectPrefabAxis(float bowYaw)
        {
            var type = TestReflection.FindAssemblyCSharpType("Sango.VesselBuoyancy");
            var ship = new GameObject("backend roll", typeof(MeshFilter));
            ship.SetActive(false);
            var mesh = new Mesh { vertices = new[] { Vector3.zero, Vector3.right, Vector3.forward }, triangles = new[] { 0, 1, 2 } };
            ship.GetComponent<MeshFilter>().sharedMesh = mesh;
            try
            {
                var component = ship.AddComponent(type);
                type.GetField("bowYawDeg").SetValue(component, bowYaw);
                type.GetField("twinRollDeg").SetValue(component, new Func<float?>(() => 10f));
                ship.transform.rotation = Quaternion.Euler(0, 45 + bowYaw, 0);
                ship.SetActive(true);
                type.GetMethod("LateUpdate", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(component, null);
                var starboard = ship.transform.rotation * Quaternion.Euler(0, -bowYaw, 0) * Vector3.right;
                Assert.That(starboard.y, Is.EqualTo(-Mathf.Sin(10 * Mathf.Deg2Rad)).Within(1e-4), "NED positive roll lowers starboard, independent of prefab bow yaw");
            }
            finally { UnityEngine.Object.DestroyImmediate(ship); UnityEngine.Object.DestroyImmediate(mesh); }
        }

        [Test]
        public void WeatherSettingsReachWaterCloudsAndFog_OffCalmsTheSurface()
        {
            var type = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
            var applyType = TestReflection.FindAssemblyCSharpType("Sango.TwinEnvironmentVisuals");
            var go = new GameObject("session weather");
            var waterGo = new GameObject("session water");
            var volumeGo = new GameObject("session clouds");
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            profile.Add<Fog>(); profile.Add<VolumetricClouds>();
            try
            {
                var controller = go.AddComponent(type);
                var water = waterGo.AddComponent<WaterSurface>();
                var volume = volumeGo.AddComponent<Volume>(); volume.sharedProfile = profile;
                type.GetField("waterSurface").SetValue(controller, water);
                type.GetField("globalVolume").SetValue(controller, volume);
                var e = new TwinEnvironment { enabled = true, wind_speed_mps = 12, wave_hs_m = 2, wave_period_s = 8,
                    wave_from_deg = 0, time_of_day_hours = 23, cloud_cover = 0.9f, fog_distance_m = 750, current_speed_mps = 1 };
                applyType.GetMethod("Apply").Invoke(null, new object[] { controller, e });
                Assert.That((float)type.GetProperty("LastWindSpeedMs").GetValue(controller), Is.EqualTo(12));
                Assert.That(water.largeOrientationValue, Is.EqualTo(270));
                Assert.That(water.largeCurrentSpeedValue, Is.EqualTo(3.6f));
                Assert.That(water.largeBand0Multiplier, Is.GreaterThan(0));
                volume.profile.TryGet<Fog>(out var fog); Assert.That(fog.maxFogDistance.value, Is.EqualTo(750));
                volume.profile.TryGet<VolumetricClouds>(out var clouds); Assert.That(clouds.enable.overrideState, Is.True);
                e.enabled = false;
                applyType.GetMethod("Apply").Invoke(null, new object[] { controller, e });
                Assert.That(water.largeBand0Multiplier, Is.EqualTo(0));
                Assert.That(water.largeBand1Multiplier, Is.EqualTo(0));
                Assert.That(water.largeCurrentSpeedValue, Is.EqualTo(0));
                Assert.That(clouds.enable.value, Is.False);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(go); UnityEngine.Object.DestroyImmediate(waterGo);
                UnityEngine.Object.DestroyImmediate(volumeGo); UnityEngine.Object.DestroyImmediate(profile);
            }
        }
    }
}
