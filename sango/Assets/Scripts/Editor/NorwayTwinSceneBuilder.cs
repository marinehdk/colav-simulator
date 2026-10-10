using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

namespace Sango.Editor
{
    /// <summary>Build the current Norwegian ENC terrain without modifying the M6 demo.</summary>
    public static class NorwayTwinSceneBuilder
    {
        const string AssetsDir = "Assets/TerrainNorway";
        [Serializable] class Manifest { public string crs; public double origin_e, origin_n; public Tile[] tiles; }
        [Serializable] class Tile { public string name; public int resolution; public float x, z, size, baseY, rangeY; }

        public static void BuildPlayer()
        {
            Build();
            TwinBridge.TwinBridgeSceneBuilder.BuildTwinPlayer();
        }

        [MenuItem("Sango/Twin/Build Norwegian ENC Scene")]
        public static void Build()
        {
            string source = Path.GetFullPath(Path.Combine(Application.dataPath, "../../tmp/norway-terrain/baked"));
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(source, "manifest.json")));
            if (manifest.crs != "EPSG:25833" || manifest.origin_e != NorwayChartFrame.OriginEastM || manifest.origin_n != NorwayChartFrame.OriginNorthM)
                throw new InvalidDataException("Norway terrain and chart coordinate frames differ");
            Directory.CreateDirectory(AssetsDir);
            AssetDatabase.Refresh();
            var diffuse = ImportTexture("rocky_terrain_02_diff_4k.jpg", false);
            var normal = ImportTexture("rocky_terrain_02_nor_gl_4k.jpg", true);
            var layers = new TerrainLayer[3];
            for (int i = 0; i < layers.Length; i++)
            {
                string path = $"{AssetsDir}/Surface-{i}.terrainlayer";
                var layer = AssetDatabase.LoadAssetAtPath<TerrainLayer>(path);
                if (layer == null) { layer = new TerrainLayer(); AssetDatabase.CreateAsset(layer, path); }
                layer.diffuseTexture = diffuse;
                layer.normalMapTexture = normal;
                layer.normalScale = 0.65f;
                layer.tileSize = new Vector2(90, 90); // Source photogrammetry covers 90 m.
                layer.metallic = 0;
                layer.smoothness = 0.18f;
                layer.diffuseRemapMax = i == 1 ? new Vector4(0.35f,0.48f,0.32f,1)
                    : i == 2 ? new Vector4(0.75f,0.75f,0.75f,1) : new Vector4(0.85f,0.85f,0.85f,1);
                EditorUtility.SetDirty(layer); layers[i] = layer;
            }
            TwinBridge.TwinBridgeSceneBuilder.BuildTwinScene();
            var session = Object.FindFirstObjectByType<VisualSimulationSession>();
            var driver = Object.FindFirstObjectByType<TwinSessionDriver>();
            var camera = Object.FindFirstObjectByType<CameraRig>();
            // Remove the geographically unrelated landscape and staged Singapore traffic.
            foreach (var terrain in Object.FindObjectsByType<Terrain>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                Object.DestroyImmediate(terrain.gameObject);
            foreach (var ship in session.originalVessels) if (ship != null) Object.DestroyImmediate(ship);
            foreach (var root in EditorSceneManager.GetActiveScene().GetRootGameObjects())
                if (root.name.StartsWith("M7") || root.name == "M8 Tile Streaming") Object.DestroyImmediate(root);
            session.originalVessels = Array.Empty<GameObject>();
            session.realTerrainAndDecor = Array.Empty<GameObject>();
            session.tileStreaming = null;
            session.enabled = false;
            var workbench = session.GetComponent<SimulationWorkbench>();
            if (workbench != null) workbench.enabled = false;
            camera.followShip = camera.bridgeMount = camera.bowMount = null;
            var geography = new GameObject("Norwegian ENC terrain EPSG25833").AddComponent<NorwayTerrain>();
            var terrains = new List<Terrain>();
            var material = AssetDatabase.LoadAssetAtPath<Material>("Assets/TerrainM6/M6-TerrainLit.mat");
            if (material == null) throw new InvalidDataException("HDRP TerrainLit material missing");
            foreach (var tile in manifest.tiles)
            {
                string path = $"{AssetsDir}/{tile.name}.asset";
                var data = AssetDatabase.LoadAssetAtPath<TerrainData>(path);
                if (data == null) { data = new TerrainData(); AssetDatabase.CreateAsset(data, path); }
                byte[] raw = File.ReadAllBytes(Path.Combine(source, tile.name + ".raw"));
                if (raw.Length != tile.resolution * tile.resolution * 2) throw new InvalidDataException(tile.name);
                var heights = new float[tile.resolution, tile.resolution];
                for (int y = 0; y < tile.resolution; y++) for (int x = 0; x < tile.resolution; x++)
                { int index = (y*tile.resolution+x)*2; heights[y,x] = (raw[index] | raw[index+1]<<8) / 65535f; }
                data.heightmapResolution = tile.resolution;
                data.size = new Vector3(tile.size, tile.rangeY, tile.size);
                data.SetHeights(0, 0, heights);
                data.terrainLayers = layers;
                data.alphamapResolution = 512;
                data.baseMapResolution = 1024;
                byte[] cover = File.ReadAllBytes(Path.Combine(source, tile.name + ".cover"));
                if (cover.Length != 512*512) throw new InvalidDataException(tile.name + " cover");
                var weights = new float[512,512,3];
                for (int y = 0; y < 512; y++) for (int x = 0; x < 512; x++)
                    weights[y,x,cover[y*512+x] < 3 ? cover[y*512+x] : 0] = 1;
                data.SetAlphamaps(0, 0, weights);
                var go = Terrain.CreateTerrainGameObject(data);
                go.name = tile.name;
                go.transform.SetParent(geography.transform, false);
                go.transform.position = new Vector3(tile.x, tile.baseY, tile.z);
                var terrain = go.GetComponent<Terrain>();
                terrain.materialTemplate = material;
                terrain.heightmapPixelError = 3;
                terrain.drawInstanced = true;
                terrain.basemapDistance = 16000;
                terrains.Add(terrain);
                EditorUtility.SetDirty(data);
            }
            geography.tiles = terrains.ToArray();
            driver.geography = geography;
            geography.gameObject.AddComponent<TwinCesiumLandscape>().geography = geography;
            foreach (var terrain in terrains)
            {
                var p = terrain.transform.position;
                Terrain Neighbour(float x, float z) => terrains.Find(t => Mathf.Abs(t.transform.position.x-x)<1 && Mathf.Abs(t.transform.position.z-z)<1);
                terrain.SetNeighbors(Neighbour(p.x-6000,p.z),Neighbour(p.x,p.z+6000),Neighbour(p.x+6000,p.z),Neighbour(p.x,p.z-6000));
            }
            var own = NorwayChartFrame.Anchor.ToLocal(39000, 6957000);
            float height = geography.ElevationAt(new Vector3(own.x,0,own.y));
            if (float.IsNaN(height) || height >= 0) throw new InvalidDataException("Current ENC ownship must fall on water, got " + height);
            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), "Assets/Scenes/SangoTwin.unity");
            AssetDatabase.SaveAssets();
            Debug.Log($"[Sango.Norway] {terrains.Count} tiles, EPSG25833 origin=(42000,6959450), ownship=({own.x},{own.y}) visual_floor={height:F2}m");
        }

        static Texture2D ImportTexture(string name, bool normal)
        {
            string path = "Assets/Art/NorwayTerrain/" + name;
            AssetDatabase.ImportAsset(path);
            var importer = (TextureImporter)AssetImporter.GetAtPath(path);
            importer.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            importer.sRGBTexture = !normal;
            importer.wrapMode = TextureWrapMode.Repeat;
            importer.anisoLevel = 8;
            importer.maxTextureSize = 4096;
            importer.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }
    }
}
