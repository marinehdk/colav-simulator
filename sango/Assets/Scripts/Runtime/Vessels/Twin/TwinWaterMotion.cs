using System;
using UnityEngine;

namespace Sango
{
    /// <summary>Only advancing presented truth may inject propulsion wake. Null state is replay.</summary>
    public static class TwinWaterMotion
    {
        // Ten percent leaves room for the bow and stern sources at any FCB heading.
        public static bool RegionNeedsRecenter(Vector3 center, Vector3 ship, Vector2 size)
        {
            float threshold = Mathf.Min(size.x, size.y) * 0.1f;
            var offset = new Vector2(ship.x - center.x, ship.z - center.z);
            return offset.sqrMagnitude > threshold * threshold;
        }

        public static bool IsAdvancing(double previous, double current, string state)
            => !double.IsNaN(previous) && !double.IsInfinity(previous)
               && !double.IsNaN(current) && !double.IsInfinity(current)
               && current > previous + 1e-6 && (state == null || state == "RUNNING");
    }
}
