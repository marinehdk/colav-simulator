using System.IO;
using UnityEditor;
using UnityEngine;

namespace Sango.Editor
{
    /// <summary>
    /// M6 地形资产管线（Editor）：读 tmp/m6-data/manifest.json → 逐 tile 读 RAW（小端 u16、
    /// 行序北上，M6TerrainMath 解码含垂直翻转）→ TerrainData（heightmapResolution 2049/513，
    /// size=(12000, elev_max−elev_min, 12000)，世界 y=真实高程：terrain.position.y=elev_min 由
    /// 场景装配层设置）+ TerrainLayer（S2 底图 JPG，sRGB，tileSize=12000 → UV 0-1 恰铺满）。
    /// 资产落 sango/Assets/TerrainM6/（Data/Layers/Textures + M6-TerrainLit 材质）。
    /// 幂等：重跑对既有资产原路径覆盖重建（load-or-create 保 GUID，场景引用不失效）。
    /// manifest path 一律仓库根相对（notes.md §manifest 契约，V7 同口径）。
    /// </summary>
    public static class M6TerrainPipeline
    {
        public const string AssetRoot = "Assets/TerrainM6";
        public const string DataDir = AssetRoot + "/Data";
        public const string LayerDir = AssetRoot + "/Layers";
        public const string TextureDir = AssetRoot + "/Textures";
        public const string MaterialPath = AssetRoot + "/M6-TerrainLit.mat";
        const long k_SizeBudgetBytes = 100L * 1024 * 1024; // >100MB 停下上报（任务纪律）

        /// <summary>仓库根（sango/ 的上级；Application.dataPath = sango/Assets）。</summary>
        public static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));

        public static string ManifestPath => Path.Combine(RepoRoot, "tmp/m6-data/manifest.json");

        public static string TerrainDataPath(string tileName) => $"{DataDir}/{tileName}.asset";

        public static M6Manifest LoadManifest()
        {
            if (!File.Exists(ManifestPath))
                throw new FileNotFoundException($"M6 manifest missing: {ManifestPath} — run tools/terrain/m6_pipeline.sh first");
            return M6Manifest.Parse(File.ReadAllText(ManifestPath));
        }

        [MenuItem("Sango/M6/Build Terrain Assets")]
        public static void BuildAll()
        {
            var manifest = LoadManifest();
            EnsureFolders();

            var center = new Vector2(manifest.center_utm[0], manifest.center_utm[1]);
            int built = 0;
            built += BuildBand(manifest.near, center, "near");
            built += BuildBand(manifest.far, center, "far");

            EnsureTerrainLitMaterial();
            AssetDatabase.SaveAssets();

            long bytes = DirSizeBytes(AssetRoot);
            Debug.Log($"[Sango.M6] terrain assets: {built} tiles -> {AssetRoot} " +
                      $"({bytes / (1024f * 1024f):F1} MB total; budget {k_SizeBudgetBytes / (1024 * 1024)} MB)");
            if (bytes > k_SizeBudgetBytes)
                throw new System.Exception($"[Sango.M6] Assets/TerrainM6 = {bytes / (1024f * 1024f):F1} MB > 100 MB budget — stop and report");
        }

        static int BuildBand(M6Band band, Vector2 centerUtm, string tier)
        {
            int count = 0;
            foreach (var tile in band.tiles)
            {
                var layout = M6TerrainMath.LayoutFor(tile, band, centerUtm);
                string rawPath = Path.Combine(RepoRoot, tile.path_raw);
                if (!File.Exists(rawPath))
                    throw new FileNotFoundException($"[Sango.M6] RAW missing (repo-root relative): {tile.path_raw}");
                var heights = M6TerrainMath.DecodeNormalizedHeights(File.ReadAllBytes(rawPath), layout.heightmapResolution);

                // load-or-create：原路径覆盖重建，GUID 稳定（幂等；场景引用不失效）
                var data = AssetDatabase.LoadAssetAtPath<TerrainData>(TerrainDataPath(tile.name));
                if (data == null)
                {
                    data = new TerrainData();
                    AssetDatabase.CreateAsset(data, TerrainDataPath(tile.name));
                }
                data.heightmapResolution = layout.heightmapResolution;
                data.size = new Vector3(layout.sizeMeters, (float)layout.elevSpan, layout.sizeMeters);
                data.SetHeights(0, 0, heights);
                data.terrainLayers = new[] { BuildTerrainLayer(tile, layout, tier) };
                EditorUtility.SetDirty(data);
                count++;
            }
            return count;
        }

        static TerrainLayer BuildTerrainLayer(M6Tile tile, M6TileLayout layout, string tier)
        {
            string jpgSrc = Path.Combine(RepoRoot, tile.path_jpg);
            if (!File.Exists(jpgSrc))
                throw new FileNotFoundException($"[Sango.M6] basemap JPG missing: {tile.path_jpg}");
            string jpgDst = $"{TextureDir}/{tile.name}.jpg";
            File.Copy(jpgSrc, jpgDst, overwrite: true);
            AssetDatabase.ImportAsset(jpgDst);
            var importer = (TextureImporter)AssetImporter.GetAtPath(jpgDst);
            importer.sRGBTexture = true; // S2 TCI sRGB 原色（notes.md §S2 底图）
            importer.maxTextureSize = tier == "near" ? 4096 : 1024;
            importer.SaveAndReimport();
            var diffuse = AssetDatabase.LoadAssetAtPath<Texture2D>(jpgDst);

            string layerPath = $"{LayerDir}/{tile.name}_Layer.asset";
            var layer = AssetDatabase.LoadAssetAtPath<TerrainLayer>(layerPath);
            if (layer == null)
            {
                layer = new TerrainLayer();
                AssetDatabase.CreateAsset(layer, layerPath);
            }
            layer.diffuseTexture = diffuse;
            layer.tileSize = new Vector2(layout.sizeMeters, layout.sizeMeters); // UV 0-1 恰铺满 12 km tile
            layer.tileOffset = Vector2.zero;
            EditorUtility.SetDirty(layer);
            return layer;
        }

        static void EnsureTerrainLitMaterial()
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
            if (mat == null)
            {
                var shader = Shader.Find("HDRP/TerrainLit");
                if (shader == null) throw new System.Exception("[Sango.M6] HDRP/TerrainLit shader not found");
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, MaterialPath);
            }
        }

        static void EnsureFolders()
        {
            foreach (var dir in new[] { AssetRoot, DataDir, LayerDir, TextureDir })
            {
                string parent = Path.GetDirectoryName(dir)!.Replace('\\', '/');
                string leaf = Path.GetFileName(dir);
                if (!AssetDatabase.IsValidFolder(dir))
                    AssetDatabase.CreateFolder(parent, leaf);
            }
        }

        static long DirSizeBytes(string assetPath)
        {
            string full = Path.Combine(RepoRoot, "sango", assetPath);
            if (!Directory.Exists(full)) return 0;
            long sum = 0;
            foreach (var f in Directory.GetFiles(full, "*", SearchOption.AllDirectories))
                sum += new FileInfo(f).Length;
            return sum;
        }
    }
}
