using System.Text;
using UnityEditor;
using UnityEngine;

namespace Sango.Editor
{
    /// <summary>
    /// M2-A 船模资产流水线（spec #80）：确定性、幂等、可 batchmode 执行。
    /// (a) FBX 导入设置：关相机/灯/动画，中等网格压缩；
    /// (b) 由 colormap.png 直制 HDRP/Lit 材质（不走材质升级器 API）；
    /// (c) 按类目标 LOA 实测渲染器包围盒算统一缩放，烘焙在 prefab 根上；
    /// (d) 生成三个 prefab + VesselCatalog ScriptableObject 资产。
    /// 菜单 Sango/M2/Build Vessel Assets；batchmode: -executeMethod Sango.Editor.VesselAssetPipeline.BuildAll。
    /// 艏向/水线常量来源（kit 预览图 + kit OBJ 顶点逐层分析）见
    /// docs/research/2026-09-22-sango-prototype/evidence/m2a-build-log.md。
    /// </summary>
    public static class VesselAssetPipeline
    {
        public const string RootDir = "Assets/Art/KenneyWatercraft";
        public const string CatalogAssetPath = RootDir + "/VesselCatalog.asset";

        const string k_ModelsDir = RootDir + "/Models";
        const string k_ColormapPath = k_ModelsDir + "/Textures/colormap.png";
        const string k_MaterialsDir = RootDir + "/Materials";
        const string k_PrefabsDir = RootDir + "/Prefabs";
        const string k_HdrpLitShader = "HDRP/Lit";

        // spec #80 目标 LOA（米）
        const float k_TargetLoaLarge = 100f;
        const float k_TargetLoaMedium = 60f;
        const float k_TargetLoaSmall = 12f;

        // 水线解析规则：吃水 = 15% × 船体主甲板高。主甲板高按 OBJ 顶点逐层分析取
        // “船壳侧板顶”高度，再除以模型总高存成比例常量（与导入单位无关）：
        //   ship-large         甲板 y=2.10  / 总高 9.964 → 0.2108
        //   ship-ocean-liner   主甲板 y=3.04 / 总高 8.934 → 0.3403
        //   boat-fishing-small 船壳顶 y=0.70 / 总高 2.600 → 0.2692
        struct Spec
        {
            public VesselClass vesselClass;
            public string model;             // FBX 文件名（不含扩展名）
            public string prefabName;
            public float targetLoa;
            public float bowYawDeg;          // 原生艏向 → +Z 所需根 yaw（字面量，测试同步断言）
            public float hullHeightFraction; // 主甲板高 / 模型总高（见上表）
        }

        static readonly Spec[] k_Specs =
        {
            new Spec
            {
                vesselClass = VesselClass.Large, model = "ship-large", prefabName = "VesselLarge",
                targetLoa = k_TargetLoaLarge, bowYawDeg = 0f, hullHeightFraction = 2.1f / 9.964f,
            },
            new Spec
            {
                vesselClass = VesselClass.Medium, model = "ship-ocean-liner", prefabName = "VesselMedium",
                targetLoa = k_TargetLoaMedium, bowYawDeg = 180f, hullHeightFraction = 3.04f / 8.934f,
            },
            new Spec
            {
                vesselClass = VesselClass.Small, model = "boat-fishing-small", prefabName = "VesselSmall",
                targetLoa = k_TargetLoaSmall, bowYawDeg = 0f, hullHeightFraction = 0.7f / 2.6f,
            },
        };

        [MenuItem("Sango/M2/Build Vessel Assets")]
        public static void BuildAll()
        {
            BuildAllInternal();
        }

        /// <summary>干净克隆一键重建前置检查：编目 + 三 prefab 齐全则跳过，否则整跑流水线。</summary>
        public static void EnsureBuilt()
        {
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(CatalogAssetPath);
            if (catalog != null)
            {
                var complete = true;
                foreach (var spec in k_Specs)
                {
                    var entry = catalog.GetEntry(spec.vesselClass);
                    if (entry == null || entry.prefab == null)
                    {
                        complete = false;
                        break;
                    }
                }
                if (complete) return;
            }
            BuildAllInternal();
        }

        static void BuildAllInternal()
        {
            EnsureFolder("Assets", "Art");
            EnsureFolder("Assets/Art", "KenneyWatercraft");
            EnsureFolder(RootDir, "Materials");
            EnsureFolder(RootDir, "Prefabs");

            ApplyFbxImportSettings();
            var colormap = AssetDatabase.LoadAssetAtPath<Texture2D>(k_ColormapPath);
            if (colormap == null)
            {
                Debug.LogError($"[Sango.M2] colormap missing: {k_ColormapPath}");
                return;
            }
            var materials = AuthorMaterials(colormap);
            var catalog = BuildPrefabsAndCatalog(materials);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            var sb = new StringBuilder("[Sango.M2] vessel assets built:\n");
            foreach (var spec in k_Specs)
            {
                var entry = catalog.GetEntry(spec.vesselClass);
                sb.AppendFormat("  {0,-7} {1,-20} LOA={2:F1} m (target {3:F0})  waterlineOffsetY={4:F2} m  bowYaw={5}°\n",
                    spec.vesselClass, spec.model, entry.loaMeters, spec.targetLoa, entry.waterlineOffsetY, spec.bowYawDeg);
            }
            Debug.Log(sb.ToString());
        }

        // ── (a) FBX 导入设置 ──────────────────────────────────────────────────────────
        static void ApplyFbxImportSettings()
        {
            foreach (var spec in k_Specs)
            {
                var path = $"{k_ModelsDir}/{spec.model}.fbx";
                if (AssetImporter.GetAtPath(path) is not ModelImporter importer)
                {
                    Debug.LogError($"[Sango.M2] model missing or not a ModelImporter: {path}");
                    continue;
                }
                // 只在需要时 SaveAndReimport，保幂等（重复跑不再触发导入）
                if (importer.importCameras || importer.importLights || importer.importAnimation
                    || importer.meshCompression != ModelImporterMeshCompression.Medium)
                {
                    importer.importCameras = false;
                    importer.importLights = false;
                    importer.importAnimation = false;
                    importer.meshCompression = ModelImporterMeshCompression.Medium;
                    importer.SaveAndReimport();
                }
            }
        }

        // ── (b) HDRP/Lit 材质直制（colormap 做 base map；原地更新保 GUID/引用稳定）─────
        static Material[] AuthorMaterials(Texture2D colormap)
        {
            var materials = new Material[k_Specs.Length];
            for (int i = 0; i < k_Specs.Length; i++)
            {
                var spec = k_Specs[i];
                var path = $"{k_MaterialsDir}/{spec.model}.mat";
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (mat == null)
                {
                    mat = new Material(Shader.Find(k_HdrpLitShader));
                    AssetDatabase.CreateAsset(mat, path);
                }
                // HDRP/Lit 基础色贴图属性名是 _BaseColorMap（URP 才叫 _BaseMap，写错会静默落空）
                mat.SetTexture("_BaseColorMap", colormap);
                EditorUtility.SetDirty(mat);
                materials[i] = mat;
            }
            return materials;
        }

        // ── (c)(d) prefab + 编目 ─────────────────────────────────────────────────────
        static VesselCatalog BuildPrefabsAndCatalog(Material[] materials)
        {
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(CatalogAssetPath);
            if (catalog == null)
            {
                catalog = ScriptableObject.CreateInstance<VesselCatalog>();
                AssetDatabase.CreateAsset(catalog, CatalogAssetPath);
            }
            catalog.entries = new VesselCatalog.Entry[k_Specs.Length];

            for (int i = 0; i < k_Specs.Length; i++)
            {
                var spec = k_Specs[i];
                var modelPath = $"{k_ModelsDir}/{spec.model}.fbx";
                var source = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
                if (source == null)
                {
                    Debug.LogError($"[Sango.M2] model asset missing: {modelPath}");
                    continue;
                }

                // 场景里以恒等姿态实例化，实测世界包围盒（含 FBX 导入自身缩放，单位无关）
                var instance = (GameObject)PrefabUtility.InstantiatePrefab(source);
                var bounds = EncapsulatingRendererBounds(instance);
                LogBowTaperEvidence(spec, instance); // 艏向 Unity 侧证据（窄端=艏）

                float extent = Mathf.Max(bounds.size.x, bounds.size.z);
                float scale = spec.targetLoa / extent; // 统一缩放：最大水平边 → 目标 LOA
                float draft = 0.15f * spec.hullHeightFraction * bounds.size.y * scale;
                float loa = extent * scale;

                // 根节点：yaw 定艏向 + 统一缩放烘焙；根原点对中船体、吃水沉到根局部 -draft
                var root = new GameObject(spec.prefabName);
                instance.transform.SetParent(root.transform, true); // 根仍恒等，local==world
                var yaw = Quaternion.Euler(0f, spec.bowYawDeg, 0f);
                root.transform.localScale = new Vector3(scale, scale, scale);
                root.transform.rotation = yaw;
                var rotatedCenter = yaw * bounds.center;
                root.transform.position = new Vector3(
                    -scale * rotatedCenter.x,
                    -draft - scale * bounds.min.y,
                    -scale * rotatedCenter.z);

                // 全部渲染器槽位挂本模型材质
                foreach (var renderer in instance.GetComponentsInChildren<Renderer>(true))
                {
                    var slots = new Material[renderer.sharedMaterials.Length];
                    for (int s = 0; s < slots.Length; s++) slots[s] = materials[i];
                    renderer.sharedMaterials = slots;
                }

                PrefabUtility.SaveAsPrefabAsset(root, $"{k_PrefabsDir}/{spec.prefabName}.prefab");
                Object.DestroyImmediate(root);

                catalog.entries[i] = new VesselCatalog.Entry
                {
                    vesselClass = spec.vesselClass,
                    prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{k_PrefabsDir}/{spec.prefabName}.prefab"),
                    loaMeters = loa,
                    waterlineOffsetY = -draft,
                };
            }

            EditorUtility.SetDirty(catalog);
            return catalog;
        }

        static Bounds EncapsulatingRendererBounds(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>(true);
            var bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);
            return bounds;
        }

        // 艏向 Unity 侧证据：导入后网格按 z 切 10 片统计 x 宽度，窄端应与 k_Specs 艏向字面量一致
        //（独立于 kit OBJ 分析的交叉验证；两端皆窄的中段结构只影响中段片宽，不影响首末片）。
        static void LogBowTaperEvidence(Spec spec, GameObject instance)
        {
            const int slices = 10;
            float zMin = float.MaxValue, zMax = float.MinValue;
            var points = new System.Collections.Generic.List<Vector3>();
            foreach (var filter in instance.GetComponentsInChildren<MeshFilter>(true))
            {
                var mesh = filter.sharedMesh;
                if (mesh == null) continue;
                var l2w = filter.transform.localToWorldMatrix;
                foreach (var v in mesh.vertices) points.Add(l2w.MultiplyPoint3x4(v));
            }
            if (points.Count == 0) return;
            foreach (var p in points)
            {
                if (p.z < zMin) zMin = p.z;
                if (p.z > zMax) zMax = p.z;
            }
            var sliceWidth = new float[slices];
            for (int s = 0; s < slices; s++)
            {
                float lo = zMin + (zMax - zMin) * s / slices;
                float hi = zMin + (zMax - zMin) * (s + 1) / slices;
                float wMin = float.MaxValue, wMax = float.MinValue;
                foreach (var p in points)
                {
                    if (p.z < lo || p.z >= hi) continue;
                    if (p.x < wMin) wMin = p.x;
                    if (p.x > wMax) wMax = p.x;
                }
                sliceWidth[s] = wMax >= wMin ? wMax - wMin : 0f;
            }
            // 首末 20% 范围内取平均片宽作两端特征（抗单片空洞）
            float negEnd = 0f, posEnd = 0f;
            for (int s = 0; s < 2; s++) negEnd += sliceWidth[s];
            for (int s = slices - 2; s < slices; s++) posEnd += sliceWidth[s];
            string bowAt = negEnd < posEnd ? "-Z" : "+Z";
            Debug.Log($"[Sango.M2] bow evidence {spec.model}: -Z end width {negEnd:F2}, +Z end width {posEnd:F2} → native bow {bowAt}, pinned yaw {spec.bowYawDeg}° maps it to +Z");
        }

        static void EnsureFolder(string parent, string name)
        {
            if (!AssetDatabase.IsValidFolder(parent + "/" + name))
            {
                AssetDatabase.CreateFolder(parent, name);
            }
        }
    }
}
