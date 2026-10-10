using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>Consumes session weather without creating an independent physical environment.</summary>
    public static class TwinEnvironmentVisuals
    {
        public static void Apply(WeatherController weather, TwinEnvironment e)
        {
            if (weather == null || e == null) return;
            weather.windSpeedOverrideMs = e.enabled ? e.wind_speed_mps : 0f;
            weather.waveHsOverrideM = e.enabled ? e.wave_hs_m : 0f;
            weather.wavePeriodOverrideS = e.wave_period_s;
            weather.windDirectionDeg = TwinEnvironment.WaterOrientation(e.wind_from_deg);
            weather.waveDirectionDeg = TwinEnvironment.WaterOrientation(e.wave_from_deg);
            weather.timeOfDayHours = e.enabled ? e.time_of_day_hours : 12f;
            weather.cloudCover = e.enabled ? e.cloud_cover : 0f;
            weather.fogDistanceMeters = e.enabled ? e.fog_distance_m : 8000f;
            weather.waveDevelopment = e.wave_development;
            weather.waveAlignment = e.wave_alignment;
            weather.visualSpectrumStyle = e.spectrum_style == "pm" ? 0 : e.spectrum_style == "tma" ? 2 : 1;
            weather.spectrumTier = e.wave_hs_m < 0.1f ? JsPmTier.Calm : e.wave_hs_m < 1f ? JsPmTier.Moderate : e.wave_hs_m < 2.5f ? JsPmTier.Rough : JsPmTier.VeryRough;
            weather.atmosphereTier = e.atmosphere == "thunderstorm" ? M7BMath.AtmosphereTier.Thunderstorm
                : e.atmosphere == "cumulonimbus" ? M7BMath.AtmosphereTier.Cumulonimbus : M7BMath.AtmosphereTier.HazyClear;
            var atmosphere = M7BMath.AtmospherePresetFor(weather.atmosphereTier);
            weather.exposureCompensationEv = e.enabled ? atmosphere.exposureCompensationEv : 0f;
            weather.sunDimFactor = e.enabled ? atmosphere.sunDimFactor : 1f;
            weather.precipitationOverride = true;
            weather.rainEnabled = e.enabled && e.rain_enabled;
            weather.snowEnabled = e.enabled && e.snow_enabled;
            weather.thunderEnabled = e.enabled && e.thunder_enabled;
            weather.wetLensEnabled = e.enabled && e.wet_lens_enabled;
            weather.precipitationIntensity = e.precipitation_intensity;
            if (weather.globalVolume != null && weather.globalVolume.profile.TryGet<VisualEnvironment>(out var sky))
            {
                // The scene's serialized skyType was not overridden: HDRP inherited
                // DefaultHDRISky.exr while the sun and volumetric clouds kept moving.
                sky.skyType.Override((int)SkyType.PhysicallyBased);
                sky.skyAmbientMode.Override(SkyAmbientMode.Dynamic);
                sky.windSpeed.Override(e.enabled ? e.wind_speed_mps * 3.6f : 0f);
                sky.windOrientation.Override(TwinEnvironment.WaterOrientation(e.wind_from_deg));
                var profile = weather.globalVolume.profile;
                if (!profile.TryGet<Tonemapping>(out var tone)) tone = profile.Add<Tonemapping>();
                tone.active = true;
                tone.mode.Override(TonemappingMode.ACES);
            }
            if (weather.rain != null)
            {
                float dir = e.wind_from_deg * Mathf.Deg2Rad;
                weather.rain.SetWindVelocity(e.enabled ? new Vector3(-Mathf.Sin(dir), 0, -Mathf.Cos(dir)) * e.wind_speed_mps : Vector3.zero);
            }
            weather.Apply();
            if (weather.waterSurface != null)
            {
                weather.waterSurface.largeCurrentSpeedValue = e.enabled ? e.current_speed_mps * 3.6f : 0f;
                weather.waterSurface.ripplesCurrentSpeedValue = weather.waterSurface.largeCurrentSpeedValue;
            }
            int quality = e.quality == "low" ? 1 : 0;
            if (M8Quality.DropdownIndex != quality) M8Quality.SetTierFromDropdownIndex(quality);
        }
    }
}
