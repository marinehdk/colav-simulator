using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Tests
{
    public class WeatherSpectrumTransitionTests
    {
        [Test]
        public void ChangingTierDoesNotJumpWaterBeforeTransitionAdvances()
        {
            var go = new GameObject("Spectrum transition test");
            var waterGo = new GameObject("Transition water");
            try
            {
                var water = waterGo.AddComponent<WaterSurface>();
                var type = TestReflection.FindAssemblyCSharpType("Sango.WeatherController");
                var controller = go.AddComponent(type);
                type.GetField("waterSurface").SetValue(controller, water);
                type.GetMethod("Apply").Invoke(controller, null);
                float initialBand = water.largeBand0Multiplier;
                float initialFoam = water.simulationFoamAmount;
                type.GetField("spectrumTier").SetValue(controller, System.Enum.ToObject(type.GetField("spectrumTier").FieldType, 2));
                type.GetMethod("BeginUserGradeTransition").Invoke(controller, new object[] { (float?)6f, null, 2.5f });
                type.GetMethod("Apply").Invoke(controller, null);
                Assert.That(water.largeBand0Multiplier, Is.EqualTo(initialBand).Within(1e-6f));
                Assert.That(water.simulationFoamAmount, Is.EqualTo(initialFoam).Within(1e-6f));
                type.GetMethod("AdvanceAtmosphereTransition").Invoke(controller, new object[] { 1.25f });
                type.GetMethod("Apply").Invoke(controller, null);
                Assert.That(water.largeBand0Multiplier, Is.InRange(initialBand + 0.001f, 0.849f));
                type.GetMethod("AdvanceAtmosphereTransition").Invoke(controller, new object[] { 1.25f });
                type.GetMethod("Apply").Invoke(controller, null);
                Assert.That(water.largeBand0Multiplier, Is.EqualTo(0.85f).Within(1e-6f));
                Assert.That(water.simulationFoamAmount, Is.EqualTo(0.42f).Within(1e-6f));
            }
            finally { Object.DestroyImmediate(go); Object.DestroyImmediate(waterGo); }
        }
    }
}
