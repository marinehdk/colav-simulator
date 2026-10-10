using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Sango.Tests
{
    public class TwinCesiumMeshTests
    {
        [Test]
        public void CoastlineUsesRasterMaskWithoutDeletingSourceTriangles()
        {
            var root = new GameObject("coastline regression");
            var tile = new GameObject("photogrammetry coast");
            var data = new TerrainData { heightmapResolution = 33, size = new Vector3(200,100,200) };
            var terrain = Terrain.CreateTerrainGameObject(data);
            terrain.transform.position = new Vector3(-100,-80,-100);
            var mesh = new Mesh { vertices = new[] { new Vector3(0,2,0), new Vector3(10,2,0), new Vector3(0,2,10) }, triangles = new[] { 0,1,2 } };
            tile.AddComponent<MeshFilter>().sharedMesh = mesh;
            tile.AddComponent<MeshRenderer>();
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinCesiumLandscape");
            var landscape = root.AddComponent(type);
            var geographyType = TestReflection.FindAssemblyCSharpType("Sango.NorwayTerrain");
            var geography = root.AddComponent(geographyType);
            geographyType.GetField("tiles").SetValue(geography,new[] { terrain.GetComponent<Terrain>() });
            type.GetField("geography").SetValue(landscape,geography);
            try
            {
                type.GetMethod("ProjectTile",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(landscape,new object[] { tile,false });
                Assert.That(mesh.triangles,Is.EqualTo(new[] { 0,1,2 }),
                    "Coarse DEM samples must not delete a whole photographic triangle; N50 raster mask clips its sea pixels.");
            }
            finally { Object.DestroyImmediate(tile); Object.DestroyImmediate(root); Object.DestroyImmediate(terrain); Object.DestroyImmediate(data); Object.DestroyImmediate(mesh); }
        }

        [Test]
        public void ProjectionPreservesSdkMeshPoolOwnership()
        {
            var root = new GameObject("landscape projection regression");
            var tile = new GameObject("SDK tile");
            var mesh = new Mesh { vertices = new[] {
                new Vector3(-3000,2,-2450), new Vector3(-2990,2,-2450), new Vector3(-3000,2,-2440) },
                triangles = new[] { 0,1,2 } };
            var filter = tile.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;
            var material = new Material(Resources.Load<Material>("CesiumUnlitTilesetMaterial"));
            material.SetFloat("_AlphaCutoffEnable",0);
            tile.AddComponent<MeshRenderer>().sharedMaterial = material;
            var type = TestReflection.FindAssemblyCSharpType("Sango.TwinCesiumLandscape");
            var component = root.AddComponent(type);
            try
            {
                type.GetMethod("ProjectTile",BindingFlags.Instance|BindingFlags.NonPublic)
                    .Invoke(component,new object[] { tile,false });
                Assert.That(filter.sharedMesh,Is.SameAs(mesh),
                    "SDK returns MeshFilter.sharedMesh to its pool; swapping in an owned clone corrupts reuse.");
                Assert.That(mesh.vertices[0].y,Is.GreaterThan(2),"The chart height correction must still be applied.");
                Assert.That(material.GetFloat("_AlphaCutoffEnable"),Is.EqualTo(1),
                    "HDRP must discard pixels outside the coastline, including the SDK unlit template.");
                Assert.That(material.IsKeywordEnabled("_ALPHATEST_ON"),Is.True);
                Object.DestroyImmediate(tile);
                Assert.That(mesh != null,Is.True,"The SDK retains mesh lifetime ownership after tile destruction.");
            }
            finally
            {
                if (tile != null) Object.DestroyImmediate(tile);
                Object.DestroyImmediate(root);
                Object.DestroyImmediate(mesh);
                Object.DestroyImmediate(material);
            }
        }
    }
}
