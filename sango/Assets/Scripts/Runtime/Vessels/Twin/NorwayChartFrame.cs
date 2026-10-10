using UnityEngine;

namespace Sango
{
    /// <summary>Fixed EPSG:25833 frame for the current Alesund ENC and its surrounding terrain.</summary>
    public static class NorwayChartFrame
    {
        public const double OriginEastM = 42000;
        public const double OriginNorthM = 6959450;
        public const float HalfExtentM = 9000;
        // GDAL EPSG:5973 -> ECEF calibration at the chart origin. The 6 km ENC
        // horizontal fit error is <= 0.102 m; the surrounding 18 km fit is < 0.92 m.
        public const double Longitude = 6.09466369035883;
        public const double Latitude = 62.4812439056859;
        public const double EllipsoidHeight = 44.6918514333224;
        public const float CesiumScale = 1.002163223238058f;
        public const float CesiumYaw = 7.911396821729316f;
        public static TwinAnchor Anchor => new TwinAnchor {
            EastM = OriginEastM, NorthM = OriginNorthM, LandingM = Vector2.zero
        };
        public static bool Contains(Vector2 point)
            => Mathf.Abs(point.x) <= HalfExtentM && Mathf.Abs(point.y) <= HalfExtentM;

        public static float SeaLevelCorrection(Vector3 grid)
        {
            double x = grid.x, z = grid.z;
            return (float)(1.2163666666666541e-5*x - 2.4049999999984832e-6*z
                + 7.743411007025784e-8*x*x - 9.31388888890777e-11*x*z + 7.736982435597174e-8*z*z);
        }
    }
}
