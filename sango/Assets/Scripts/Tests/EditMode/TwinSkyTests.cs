using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    public class TwinSkyTests
    {
        [Test]
        public void SessionSkyOverridesDefaultHdriAndSurvivesWeatherRefresh()
        {
            var host = new GameObject("twin sky regression");
            var profile = ScriptableObject.CreateInstance<VolumeProfile>();
            profile.Add<VisualEnvironment>();
            profile.Add<PhysicallyBasedSky>();
            profile.Add<VolumetricClouds>();
            var volume = host.AddComponent<Volume>();
            volume.sharedProfile = profile;
            try
            {
                var type = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
                var weather = host.AddComponent(type);
                type.GetField("globalVolume").SetValue(weather, volume);
                var apply = TestReflection.FindAssemblyCSharpType("Sango.TwinEnvironmentVisuals").GetMethod("Apply");
                var environment = new TwinEnvironment { enabled = true, cloud_cover = 0.1f, time_of_day_hours = 12 };
                apply.Invoke(null, new object[] { weather, environment });
                type.GetMethod("Apply").Invoke(weather, null);
                volume.profile.TryGet<VisualEnvironment>(out var sky);
                Assert.That(sky.skyType.overrideState, Is.True, "An unoverridden sky inherits the project's HDRI, even when its value is 4.");
                Assert.That(sky.skyType.value, Is.EqualTo((int)SkyType.PhysicallyBased));
                volume.profile.TryGet<VolumetricClouds>(out var clouds);
                Assert.That(clouds.shapeScale.value, Is.LessThan(5f), "Sparse preset must not restore the small repeated cloud field.");
                environment.cloud_cover = 0;
                apply.Invoke(null, new object[] { weather, environment });
                type.GetMethod("Apply").Invoke(weather, null);
                Assert.That(clouds.enable.value, Is.False);
            }
            finally
            {
                Object.DestroyImmediate(volume.profile);
                Object.DestroyImmediate(host);
                Object.DestroyImmediate(profile);
            }
        }
    }
}
