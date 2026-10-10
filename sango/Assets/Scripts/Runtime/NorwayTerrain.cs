using UnityEngine;

namespace Sango
{
    /// <summary>Geographic visual terrain. Does not replace ENC depths or navigation authority.</summary>
    public sealed class NorwayTerrain : MonoBehaviour
    {
        public Terrain[] tiles;
        public TwinAnchor Anchor => NorwayChartFrame.Anchor;

        public float ElevationAt(Vector3 point)
        {
            if (tiles == null) return float.NaN;
            foreach (var tile in tiles)
            {
                if (tile == null) continue;
                var p = tile.transform.position;
                var size = tile.terrainData.size;
                if (point.x >= p.x && point.x <= p.x + size.x && point.z >= p.z && point.z <= p.z + size.z)
                    return tile.SampleHeight(point) + p.y;
            }
            return float.NaN;
        }

        public M6TwinGeo.FitReport ClassifyFit(Vector2 min, Vector2 max)
        {
            int covered = 0, wet = 0, count = 0;
            for (float x = min.x; x <= max.x + 1; x += 100)
            for (float z = min.y; z <= max.y + 1; z += 100)
            {
                float height = ElevationAt(new Vector3(x, 0, z));
                count++;
                if (float.IsNaN(height)) continue;
                covered++;
                if (height <= 0) wet++;
            }
            float terrain = covered / (float)Mathf.Max(count, 1);
            float water = wet / (float)Mathf.Max(count, 1);
            return new M6TwinGeo.FitReport {
                Fit = terrain < 0.5f ? M6TwinGeo.FitOutside : water < 0.98f ? M6TwinGeo.FitPartial : M6TwinGeo.FitInside,
                TerrainFraction = terrain, WaterFraction = water
            };
        }
    }
}
