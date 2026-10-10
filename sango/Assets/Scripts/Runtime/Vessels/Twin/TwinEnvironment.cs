using System;
using UnityEngine;

namespace Sango
{
    [Serializable]
    public class TwinEnvironment
    {
        public bool enabled;
        public float wind_speed_mps, wind_from_deg, current_speed_mps, current_from_deg;
        public float wave_hs_m, wave_period_s, wave_from_deg;
        public float time_of_day_hours = 12, cloud_cover = 0.4f, fog_distance_m = 3000;
        public float wave_development = 0.5f, wave_alignment = 0.7f, precipitation_intensity = 0.5f;
        public bool rain_enabled, snow_enabled, thunder_enabled, wet_lens_enabled;
        public string spectrum_style = "jonswap", atmosphere = "hazy_clear", quality = "high";

        // Compass FROM -> Unity +x east / +z north travelling vector.
        public Vector3 CurrentVelocity => enabled
            ? new Vector3(-Mathf.Sin(current_from_deg * Mathf.Deg2Rad), 0, -Mathf.Cos(current_from_deg * Mathf.Deg2Rad)) * current_speed_mps
            : Vector3.zero;
        // HDRP spectral orientation is measured from +x toward +z.
        public static float WaterOrientation(float fromDeg) => Mathf.Repeat(270f - fromDeg, 360f);
    }
}
