using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace Sango.Editor
{
    /// <summary>
    /// M7-A 布景四要素构建 stage（Editor，幂等；M6StraitSceneBootstrapper.BuildScene 内挂接）。
    /// A1 岸桥天际线 + 集装箱堆场：基本体门架组合（门腿×2+横梁+后伸梁+前伸小车臂）逐端子
    /// 合并为单 Mesh（2 submesh：钢结构/小车臂强调色），箱堆 6 色板合并单 Mesh（6 submesh）；
    /// 网格取终端局部系（+Z=码头线切向、+X=海侧法向），GO 旋转 = 码头线 yaw，故箱体随码头线取正。
    /// A2 锚地船群不在此（真实锚区槽位字面量进 M6StraitSceneBootstrapper.k_StraitSlots，
    /// 复用 AnchorageFleet 既有浮力/摇摆工艺）。A3 填海岸线核查修正：S2 码头平台在 DEM
    /// 期次差下缺失/0 平台（GLO-30/GEBCO 早于 S2 2026-03）→ SetHeights 小块平整至 +2 m
    /// （不碰 tile 管线；M6TerrainPipeline.BuildAll 每次重建 RAW 高度后重放，天然幂等）。
    /// A4 Batam/Bintan 绿脊：远景带逐活跃 tile 叠 2 层 TerrainLayer（泥绿滩涂 0-4 m /
    /// 深绿丛林 &gt;4 m，权重按最终高度图生成并归一化）+ 近岸线散树卡（Terrain 树管线引擎
    /// 实例化，无每帧分配；Kenney Nature Kit 无 3D 树、Quaternius 直链被 itch 会话流拦 →
    /// 基本体 card 兜底，任务允许链路末档）。
    /// 落位门禁（fail-fast）：岸桥基座/箱堆四角/平台角点一律高程 ≥ 0 且在平整矩形内，
    /// 不静默换点。
    /// </summary>
    public static class M7BackdropBuilder
    {
        public const string AssetRoot = "Assets/TerrainM7";
        public const string MeshDir = AssetRoot + "/Meshes";
        public const string MaterialDir = AssetRoot + "/Materials";
        public const string TextureDir = AssetRoot + "/Textures";

        static readonly Color[] k_ContainerColors =
        {
            new Color(0.72f, 0.10f, 0.08f), // 锈红
            new Color(0.10f, 0.28f, 0.55f), // 深蓝
            new Color(0.16f, 0.42f, 0.20f), // 集装箱绿
            new Color(0.85f, 0.48f, 0.08f), // 橙黄
            new Color(0.55f, 0.58f, 0.60f), // 灰白
            new Color(0.42f, 0.12f, 0.38f), // 暗紫红
        };

        /// <summary>布景 stage 统计（构建日志 + 测试钉契约）。</summary>
        public struct BackdropStats
        {
            public int cranes;
            public int containerBoxes;
            public int treeCards;
            public int splattedFarTiles;
            public int flattenedAprons;
            public long newAssetBytes;
        }

        /// <summary>
        /// 构建布景（顺序敏感）：A3 平整 → 陆上落位门禁（fail-fast）→ 岸桥/箱堆 →
        /// A4 splat/树卡。sample = 最终高度图（含平整）上的高程采样（Bootstrapper 提供）。
        /// 所有资产 load-or-create（幂等，GUID 稳定）；返回统计。
        /// </summary>
        public static BackdropStats BuildBackdrop(M6Manifest manifest, List<Terrain> terrains,
            M6TerrainMath.ElevationSampler sample)
        {
            var stats = new BackdropStats();
            EnsureFolders();

            // ── A3：S2 码头平台小块平整（岸桥/箱堆落位前提）─────────────────────────
            var exclusions = new List<float[]>();
            foreach (var t in M7BackdropMath.Terminals)
            {
                FlattenTerminalApron(t);
                stats.flattenedAprons++;
                exclusions.Add(t.flattenRectUnity);
            }

            // ── A1：岸桥 + 箱堆 ─────────────────────────────────────────────────────
            var steel = EnsureMaterial("M7-Steel", new Color(0.42f, 0.44f, 0.46f), 0.45f, 0.6f);
            var accent = EnsureMaterial("M7-CraneAccent", new Color(0.70f, 0.12f, 0.10f), 0.4f, 0.5f);
            var yardMats = new Material[M7BackdropMath.ContainerColorCount];
            for (int i = 0; i < yardMats.Length; i++)
                yardMats[i] = EnsureMaterial($"M7-Container{i}", k_ContainerColors[i], 0.35f, 0.4f);

            var backdropRoot = new GameObject("M7 Backdrop");
            foreach (var t in M7BackdropMath.Terminals)
                stats.containerBoxes += PlaceTerminal(t, steel, accent, yardMats, backdropRoot.transform, sample);
            stats.cranes = M7BackdropMath.TotalCraneCount;

            // ── A4：远景带 splat 植被观感 + 近岸线树卡 ───────────────────────────────
            var center = new Vector2(manifest.center_utm[0], manifest.center_utm[1]);
            var mudLayer = EnsureSolidLayer("M7-Mudflat", new Color(0.36f, 0.40f, 0.22f));
            var jungleLayer = EnsureSolidLayer("M7-Jungle", new Color(0.05f, 0.20f, 0.07f));
            int activeFar = 0;
            foreach (var tile in manifest.far.tiles)
            {
                var terrain = FindTerrain(terrains, tile.name);
                if (terrain == null)
                    throw new System.InvalidOperationException($"[Sango.M7] far terrain missing: {tile.name}");
                if (!terrain.gameObject.activeSelf)
                    continue; // M6 覆盖语义隐藏 tile：不渲染不浪费 alphamap/树
                activeFar++;
                ApplyFarBandSplat(terrain, manifest.far, mudLayer, jungleLayer);
                stats.splattedFarTiles++;
            }

            var treeProto = EnsureTreeCardPrefab();
            foreach (var tile in manifest.far.tiles)
            {
                var terrain = FindTerrain(terrains, tile.name);
                if (terrain == null || !terrain.gameObject.activeSelf) continue;
                var layout = M6TerrainMath.LayoutFor(tile, manifest.far, center);
                stats.treeCards += ScatterTrees(terrain, layout, treeProto, exclusions.ToArray());
            }
            if (stats.treeCards > M7BackdropMath.MaxTreeInstances)
                throw new System.InvalidOperationException(
                    $"[Sango.M7] tree cards {stats.treeCards} > budget {M7BackdropMath.MaxTreeInstances}");

            stats.newAssetBytes = DirSizeBytes(AssetRoot);
            Debug.Log($"[Sango.M7] backdrop: {stats.cranes} cranes, {stats.containerBoxes} containers, " +
                      $"{stats.treeCards} tree cards, {stats.splattedFarTiles} far tiles splatted, " +
                      $"{stats.flattenedAprons} aprons flattened -> {AssetRoot} " +
                      $"({stats.newAssetBytes / (1024f * 1024f):F1} MB; budget {M7BackdropMath.NewAssetsBudgetBytes / (1024 * 1024)} MB)");
            if (stats.newAssetBytes > M7BackdropMath.NewAssetsBudgetBytes)
                throw new System.Exception($"[Sango.M7] {AssetRoot} = {stats.newAssetBytes / (1024f * 1024f):F1} MB " +
                                           $"> {M7BackdropMath.NewAssetsBudgetBytes / (1024 * 1024)} MB budget — stop and report");
            return stats;
        }

        // ── A3：码头面小块平整（SetHeights 局部修正，不碰 tile 管线）──────────────────

        /// <summary>把码头平台矩形内的高度图顶点抬到 flattenTargetM（重放幂等：BuildAll 每次
        /// 从 RAW 重建高度后再应用）。tile/manifest 缺失即抛（fail-fast）。</summary>
        static void FlattenTerminalApron(M7BackdropMath.TerminalLayout t)
        {
            var dataPath = M6TerrainPipeline.TerrainDataPath(t.tileName);
            var data = AssetDatabase.LoadAssetAtPath<TerrainData>(dataPath);
            if (data == null)
                throw new System.InvalidOperationException($"[Sango.M7] TerrainData missing for flatten: {dataPath}");

            var manifest = M6TerrainPipeline.LoadManifest();
            M6Band band = System.Array.FindIndex(manifest.far.tiles, x => x.name == t.tileName) >= 0
                ? manifest.far
                : manifest.near;
            M6Tile tile = System.Array.Find(band.tiles, x => x.name == t.tileName);
            var center = new Vector2(manifest.center_utm[0], manifest.center_utm[1]);
            var layout = M6TerrainMath.LayoutFor(tile, band, center);

            int res = data.heightmapResolution;
            float cell = layout.sizeMeters / (res - 1);
            var r = t.flattenRectUnity;
            int x0 = Mathf.Clamp(Mathf.FloorToInt((r[0] - layout.originXZ.x) / cell), 0, res - 1);
            int x1 = Mathf.Clamp(Mathf.CeilToInt((r[2] - layout.originXZ.x) / cell), 0, res - 1);
            int y0 = Mathf.Clamp(Mathf.FloorToInt((r[1] - layout.originXZ.y) / cell), 0, res - 1);
            int y1 = Mathf.Clamp(Mathf.CeilToInt((r[3] - layout.originXZ.y) / cell), 0, res - 1);
            int w = x1 - x0 + 1, h = y1 - y0 + 1;
            if (w <= 1 || h <= 1)
                throw new System.InvalidOperationException($"[Sango.M7] flatten rect outside tile {t.tileName}: [{r[0]},{r[1]},{r[2]},{r[3]}]");

            float normTarget = (float)((t.flattenTargetM - layout.elevMin) / layout.elevSpan);
            var block = new float[h, w];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    block[y, x] = normTarget;
            data.SetHeights(x0, y0, block);
            EditorUtility.SetDirty(data);
            Debug.Log($"[Sango.M7] A3 flatten {t.name}: tile {t.tileName} rect [{r[0]},{r[1]}]-[{r[2]},{r[3]}] -> " +
                      $"{t.flattenTargetM} m ({w}x{h} texels @ {cell:F2} m/px)");
        }

        // ── A1：岸桥（门架组合网格）+ 箱堆（合并网格），终端局部系 ───────────────────

        static int PlaceTerminal(M7BackdropMath.TerminalLayout t, Material steel, Material accent,
            Material[] yardMats, Transform root, M6TerrainMath.ElevationSampler sample)
        {
            // ── 落位门禁（world 坐标实采）：岸桥基座 + 箱堆四角 + 平整平台四角 ≥ 0 且在矩形内
            var cranes = M7BackdropMath.CranePositions(t);
            var yard = M7BackdropMath.GenerateYard(t);
            var gate = new List<Vector2>(cranes);
            var tan = M7BackdropMath.QuayTangent(t);
            var seaward = M7BackdropMath.QuaySeawardNormal(t);
            foreach (var cb in yard)
            {
                var flat = new Vector2(cb.center.x, cb.center.z);
                gate.Add(flat);
                gate.Add(flat + tan * (cb.size.z * 0.5f) + seaward * (cb.size.x * 0.5f));
                gate.Add(flat - tan * (cb.size.z * 0.5f) - seaward * (cb.size.x * 0.5f));
            }
            var report = M7BackdropMath.ValidateDryLand(sample, gate.ToArray(), M7BackdropMath.LandGateMinElevationM);
            if (!report.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M7] LAND GATE FAIL: {t.name} placement at ({report.worstPoint.x:F0},{report.worstPoint.y:F0}) " +
                    $"elevation {report.worstElevationM:F2} m < {M7BackdropMath.LandGateMinElevationM} m — " +
                    $"fix the flatten rect / quay literals, do not silently relocate");
            foreach (var p in cranes)
                if (!M7BackdropMath.InRect(p, t.flattenRectUnity) || !InYardRect(yard, t))
                    throw new System.InvalidOperationException(
                        $"[Sango.M7] LAYOUT GATE FAIL: {t.name} placement outside flatten rect (crane {p}) — mesh assumes flattened apron");

            // ── 岸桥：逐台局部 box 组合 → 合并单 Mesh（submesh0 钢结构 / submesh1 小车臂强调色）
            var allSteel = new List<Box>();
            var allAccent = new List<Box>();
            foreach (var p in cranes)
            {
                // 局部坐标：起点 = quayStart，+Z = 切向，+X = 海侧法向（GO 旋转 = 码头线 yaw）
                float along = Vector2.Dot(p - t.quayStart, tan);
                float across = Vector2.Dot(p - t.quayStart, seaward);
                foreach (var (box, isSteel) in BuildCraneBoxes())
                {
                    var center = new Vector3(box.Center.x + across, box.Center.y, box.Center.z + along);
                    (isSteel ? allSteel : allAccent).Add(new Box(center, box.Size));
                }
            }
            var craneMesh = BuildMesh(new[] { allSteel, allAccent });
            var craneGo = new GameObject($"M7 Cranes {t.name}", typeof(MeshFilter), typeof(MeshRenderer));
            craneGo.GetComponent<MeshFilter>().sharedMesh = EnsureMesh($"{t.name}_Cranes", craneMesh);
            craneGo.GetComponent<MeshRenderer>().sharedMaterials = new[] { steel, accent };
            craneGo.transform.position = new Vector3(t.quayStart.x, t.flattenTargetM, t.quayStart.y);
            craneGo.transform.rotation = QuayYaw(t);
            GameObjectUtility.SetStaticEditorFlags(craneGo, StaticEditorFlags.BatchingStatic);
            craneGo.transform.SetParent(root, false);

            // ── 箱堆：全部箱合并单 Mesh（6 色板 submesh）；GO y = 平整平台面（门禁已保证落点在矩形内）
            var byColor = new List<Box>[M7BackdropMath.ContainerColorCount];
            for (int c = 0; c < byColor.Length; c++) byColor[c] = new List<Box>();
            foreach (var cb in M7BackdropMath.GenerateYardLocal(t))
                byColor[cb.colorIndex].Add(new Box(cb.center, cb.size));
            var yardMesh = BuildMesh(byColor);
            var yardGo = new GameObject($"M7 Yard {t.name}", typeof(MeshFilter), typeof(MeshRenderer));
            yardGo.GetComponent<MeshFilter>().sharedMesh = EnsureMesh($"{t.name}_Yard", yardMesh);
            yardGo.GetComponent<MeshRenderer>().sharedMaterials = yardMats;
            yardGo.transform.position = new Vector3(t.quayStart.x, t.flattenTargetM, t.quayStart.y);
            yardGo.transform.rotation = QuayYaw(t);
            GameObjectUtility.SetStaticEditorFlags(yardGo, StaticEditorFlags.BatchingStatic);
            yardGo.transform.SetParent(root, false);
            return yard.Count;
        }

        static bool InYardRect(List<M7BackdropMath.ContainerBox> yard, M7BackdropMath.TerminalLayout t)
        {
            foreach (var cb in yard)
                if (!M7BackdropMath.InRect(new Vector2(cb.center.x, cb.center.z), t.flattenRectUnity))
                    return false;
            return true;
        }

        static Quaternion QuayYaw(M7BackdropMath.TerminalLayout t)
        {
            var tan = M7BackdropMath.QuayTangent(t);
            return Quaternion.Euler(0f, Mathf.Atan2(tan.x, tan.y) * Mathf.Rad2Deg, 0f);
        }

        /// <summary>单台岸桥 box 组合（局部：+Z=码头线切向，+X=海侧法向，y=0 站面）。
        /// 门腿×2 + 上下横梁 + 后伸梁 + 前伸小车臂 + 机房（低模基本体组合，中景观感）。</summary>
        static List<(Box box, bool steel)> BuildCraneBoxes()
        {
            const float gaugeHalf = 15f;   // 轨距半宽（海侧↔陆侧）
            const float legH = 42f;
            var boxes = new List<(Box, bool)>
            {
                (new Box(new Vector3(-gaugeHalf, legH * 0.5f, 0f), new Vector3(4f, legH, 4f)), true),   // 陆侧门腿
                (new Box(new Vector3(gaugeHalf, legH * 0.5f, 0f), new Vector3(4f, legH, 4f)), true),    // 海侧门腿
                (new Box(new Vector3(0f, 10f, 0f), new Vector3(30f, 2.5f, 3f)), true),                  // 下横梁
                (new Box(new Vector3(0f, legH - 2f, 0f), new Vector3(34f, 4f, 4f)), true),              // 上横梁
                (new Box(new Vector3(-14f, legH + 1f, 0f), new Vector3(26f, 3f, 3f)), true),            // 后伸梁（陆侧）
                (new Box(new Vector3(-16f, legH + 5f, 0f), new Vector3(10f, 6f, 8f)), true),            // 机房
                (new Box(new Vector3(44f, legH + 1f, 0f), new Vector3(60f, 3f, 3f)), false),            // 前伸小车臂（海侧）
            };
            return boxes;
        }

        // ── 合并网格工具（editor 构建期一次性；24 顶点 box、面法线、UInt32 索引）────────

        readonly struct Box
        {
            public readonly Vector3 Center;
            public readonly Vector3 Size;
            public Box(Vector3 center, Vector3 size) { Center = center; Size = size; }
        }

        /// <summary>把多组 box 合并为多 submesh Mesh（groups[i] → submesh i）。</summary>
        static Mesh BuildMesh(List<Box>[] groups)
        {
            var verts = new List<Vector3>();
            var normals = new List<Vector3>();
            var indices = new List<int[]>();
            foreach (var group in groups) indices.Add(AppendBoxes(group, verts, normals));

            var mesh = new Mesh { indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(verts);
            mesh.SetNormals(normals);
            mesh.subMeshCount = indices.Count;
            for (int i = 0; i < indices.Count; i++) mesh.SetTriangles(indices[i], i, false);
            mesh.RecalculateBounds();
            return mesh;
        }

        static int[] AppendBoxes(List<Box> boxes, List<Vector3> verts, List<Vector3> normals)
        {
            var tri = new List<int>(boxes.Count * 36);
            foreach (var box in boxes)
            {
                var h = box.Size * 0.5f;
                int v0 = verts.Count;
                // 6 面 × 4 顶点（面法线硬边）
                AppendQuad(verts, normals, box.Center + Vector3.up * h.y, Vector3.right * h.x, Vector3.forward * h.z, Vector3.up);
                AppendQuad(verts, normals, box.Center - Vector3.up * h.y, Vector3.forward * h.z, Vector3.right * h.x, -Vector3.up);
                AppendQuad(verts, normals, box.Center + Vector3.right * h.x, Vector3.forward * h.z, Vector3.up * h.y, Vector3.right);
                AppendQuad(verts, normals, box.Center - Vector3.right * h.x, Vector3.up * h.y, Vector3.forward * h.z, -Vector3.right);
                AppendQuad(verts, normals, box.Center + Vector3.forward * h.z, Vector3.up * h.y, Vector3.right * h.x, Vector3.forward);
                AppendQuad(verts, normals, box.Center - Vector3.forward * h.z, Vector3.right * h.x, Vector3.up * h.y, -Vector3.forward);
                for (int f = 0; f < 6; f++)
                {
                    int b = v0 + f * 4;
                    tri.AddRange(new[] { b, b + 1, b + 2, b, b + 2, b + 3 });
                }
            }
            return tri.ToArray();
        }

        static void AppendQuad(List<Vector3> verts, List<Vector3> normals, Vector3 center, Vector3 axisU, Vector3 axisV, Vector3 normal)
        {
            verts.Add(center - axisU - axisV); normals.Add(normal);
            verts.Add(center + axisU - axisV); normals.Add(normal);
            verts.Add(center + axisU + axisV); normals.Add(normal);
            verts.Add(center - axisU + axisV); normals.Add(normal);
        }

        static Mesh EnsureMesh(string name, Mesh built)
        {
            string path = $"{MeshDir}/{name}.asset";
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing != null)
            {
                EditorUtility.CopySerialized(built, existing); // 原路径覆盖：GUID 稳定
                Object.DestroyImmediate(built);
                EditorUtility.SetDirty(existing);
                return existing;
            }
            AssetDatabase.CreateAsset(built, path);
            return built;
        }

        // ── A4：远景带 splat + 树卡 ─────────────────────────────────────────────────

        /// <summary>远景 tile 叠 2 层植被 TerrainLayer：weights 按最终高度图（含平整）逐 texel 生成并归一化。</summary>
        static void ApplyFarBandSplat(Terrain terrain, M6Band band, TerrainLayer mud, TerrainLayer jungle)
        {
            var data = terrain.terrainData;
            var existing = data.terrainLayers;
            var layers = new List<TerrainLayer>(existing);
            if (!layers.Contains(mud)) layers.Add(mud);
            if (!layers.Contains(jungle)) layers.Add(jungle);
            data.terrainLayers = layers.ToArray();
            int alphaRes = 257; // 远景 23.4 m/px → 权重图 ~46.8 m/px，平滑权重足够且省资产体积
            data.alphamapResolution = alphaRes;
            var heights = data.GetHeights(0, 0, data.heightmapResolution, data.heightmapResolution);
            var maps = new float[alphaRes, alphaRes, layers.Count];
            double elevMin = band.elev_min, elevSpan = band.ElevSpan;
            for (int y = 0; y < alphaRes; y++)
            {
                for (int x = 0; x < alphaRes; x++)
                {
                    // alphamap texel 中心 → 高度图最近格
                    int hx = Mathf.Min((int)((x + 0.5f) / alphaRes * data.heightmapResolution), data.heightmapResolution - 1);
                    int hy = Mathf.Min((int)((y + 0.5f) / alphaRes * data.heightmapResolution), data.heightmapResolution - 1);
                    float elev = M6TerrainMath.ElevMeters(heights[hy, hx], elevMin, elevSpan + elevMin);
                    var w = M7BackdropMath.SplatWeights(elev);
                    maps[y, x, 0] = w.baseWeight;
                    maps[y, x, 1] = w.mudWeight;
                    maps[y, x, 2] = w.jungleWeight;
                    for (int l = 3; l < layers.Count; l++) maps[y, x, l] = 0f;
                }
            }
            data.SetAlphamaps(0, 0, maps);
            EditorUtility.SetDirty(data);
        }

        /// <summary>远景近岸线树卡散布（Terrain 树管线：引擎实例化/LOD，无每帧分配）。</summary>
        static int ScatterTrees(Terrain terrain, M6TileLayout layout, GameObject protoPrefab, float[][] exclusions)
        {
            var data = terrain.terrainData;
            data.treePrototypes = new[] { new TreePrototype { prefab = protoPrefab } };

            var heights = data.GetHeights(0, 0, data.heightmapResolution, data.heightmapResolution);
            var points = M7BackdropMath.ScatterTreeCards(
                heights, data.heightmapResolution, layout.sizeMeters, layout.originXZ,
                layout.elevMin, layout.elevSpan, M7BackdropMath.MaxTreesPerFarTile, exclusions);

            var instances = new TreeInstance[points.Count];
            for (int i = 0; i < points.Count; i++)
            {
                float nx = (points[i].x - layout.originXZ.x) / layout.sizeMeters;
                float nz = (points[i].y - layout.originXZ.y) / layout.sizeMeters;
                instances[i] = new TreeInstance
                {
                    position = new Vector3(nx, 0f, nz), // y 由地形引擎贴地
                    widthScale = 1f,
                    heightScale = 1f,
                    color = Color.white,
                    lightmapColor = Color.white,
                    prototypeIndex = 0,
                };
            }
            data.treeInstances = instances;
            EditorUtility.SetDirty(data);
            return points.Count;
        }

        /// <summary>树卡 prefab：交叉双面 quad（基本体兜底；20+ km 剪影增强）。load-or-create。</summary>
        static GameObject EnsureTreeCardPrefab()
        {
            string prefabPath = $"{AssetRoot}/TreeCard.prefab";
            var existing = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (existing != null) return existing;

            var mat = EnsureMaterial("M7-TreeCard", new Color(0.043f, 0.157f, 0.059f), 0.0f, 0.0f);

            const float w = 24f, h = 34f;
            var verts = new List<Vector3>();
            var normals = new List<Vector3>();
            var tri = new List<int>();
            void Quad(Vector3 offset, Vector3 u, Vector3 v, Vector3 n)
            {
                int v0 = verts.Count;
                verts.Add(offset - u - v); normals.Add(n);
                verts.Add(offset + u - v); normals.Add(n);
                verts.Add(offset + u + v); normals.Add(n);
                verts.Add(offset - u + v); normals.Add(n);
                tri.AddRange(new[] { v0, v0 + 1, v0 + 2, v0, v0 + 2, v0 + 3, // 正面
                    v0, v0 + 3, v0 + 2, v0, v0 + 2, v0 + 1 });               // 背面
            }
            var up = Vector3.up * (h * 0.5f);
            Quad(new Vector3(0f, h * 0.5f, 0f), Vector3.right * (w * 0.5f), up, Vector3.forward);
            Quad(new Vector3(0f, h * 0.5f, 0f), Vector3.forward * (w * 0.5f), up, Vector3.right);
            var mesh = new Mesh();
            mesh.SetVertices(verts);
            mesh.SetNormals(normals);
            mesh.SetTriangles(tri, 0);
            mesh.RecalculateBounds();

            string meshPath = $"{MeshDir}/TreeCard.asset";
            var meshAsset = AssetDatabase.LoadAssetAtPath<Mesh>(meshPath);
            if (meshAsset == null) AssetDatabase.CreateAsset(mesh, meshPath);
            else { EditorUtility.CopySerialized(mesh, meshAsset); Object.DestroyImmediate(mesh); }

            var go = new GameObject("TreeCard", typeof(MeshFilter), typeof(MeshRenderer));
            go.GetComponent<MeshFilter>().sharedMesh = meshAsset;
            go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            var prefab = PrefabUtility.SaveAsPrefabAsset(go, prefabPath);
            Object.DestroyImmediate(go);
            return prefab;
        }

        // ── 资产工具（load-or-create / 目录）────────────────────────────────────────

        static Material EnsureMaterial(string name, Color color, float smoothness, float metallic)
        {
            string path = $"{MaterialDir}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = Shader.Find("HDRP/Lit");
                if (shader == null) throw new System.Exception("[Sango.M7] HDRP/Lit shader not found");
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetColor("_BaseColor", color);
            mat.SetFloat("_Smoothness", smoothness);
            mat.SetFloat("_Metallic", metallic);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        static TerrainLayer EnsureSolidLayer(string name, Color color)
        {
            string layerPath = $"{AssetRoot}/{name}_Layer.asset";
            var layer = AssetDatabase.LoadAssetAtPath<TerrainLayer>(layerPath);
            if (layer == null)
            {
                layer = new TerrainLayer();
                AssetDatabase.CreateAsset(layer, layerPath);
            }
            string texPath = $"{TextureDir}/{name}_Diffuse.png";
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(texPath);
            if (tex == null)
            {
                tex = new Texture2D(4, 4, TextureFormat.RGBA32, false);
                var px = new Color[16];
                for (int i = 0; i < px.Length; i++) px[i] = color;
                tex.SetPixels(px);
                tex.Apply();
                AssetDatabase.CreateAsset(tex, texPath);
            }
            layer.diffuseTexture = tex;
            layer.tileSize = new Vector2(12000f, 12000f);
            layer.tileOffset = Vector2.zero;
            EditorUtility.SetDirty(layer);
            return layer;
        }

        static Terrain FindTerrain(List<Terrain> terrains, string tileName)
        {
            foreach (var t in terrains)
                if (t != null && t.gameObject.name == tileName) return t;
            return null;
        }

        static void EnsureFolders()
        {
            foreach (var dir in new[] { AssetRoot, MeshDir, MaterialDir, TextureDir })
            {
                string parent = Path.GetDirectoryName(dir)!.Replace('\\', '/');
                string leaf = Path.GetFileName(dir);
                if (!AssetDatabase.IsValidFolder(dir))
                    AssetDatabase.CreateFolder(parent, leaf);
            }
        }

        static long DirSizeBytes(string assetPath)
        {
            string full = Path.Combine(M6TerrainPipeline.RepoRoot, "sango", assetPath);
            if (!Directory.Exists(full)) return 0;
            long sum = 0;
            foreach (var f in Directory.GetFiles(full, "*", SearchOption.AllDirectories))
                sum += new FileInfo(f).Length;
            return sum;
        }
    }
}
