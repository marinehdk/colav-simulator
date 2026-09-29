using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Sango.Editor
{
    /// <summary>
    /// M5 采购船队导入流水线（路线 A 免费件，spec：M5 逼真性阶段②引擎侧）。
    /// 沿 VesselAssetPipeline（M2-A）惯例：确定性、幂等、可 batchmode 执行——
    /// (a) FBX 导入设置：关相机/灯/动画，isReadable=true（浮力 CPU 采样），网格压缩 Off；
    /// (b) 材质：Built-in/Standard 出货件逐槽位重建 HDRP/Lit 并回接 base color 贴图
    ///     （不走材质升级器 API，防粉紫）；FCB 占位（Houbei）换白壳+绿装 flat 调色板
    ///     + 自制轮胎护舷（环状 torus mesh，非贴图/AI 工序）；
    /// (c) 按类目标 LOA 实测渲染器包围盒算统一缩放烘焙 prefab 根，BowYawDeg 窄端实测
    ///     （±Z 两端 10 片宽度证据，M2-A MeasureEndTaper 复用），规格表字面量钉值；
    /// (d) 写同一 VesselCatalog 资产（Kenney 三档保留，fleetPipelineVersion 分账 bump 强制重导）。
    /// 菜单 Sango/M5/Build Purchased Fleet；batchmode: -executeMethod Sango.Editor.M5FleetPipeline.BuildAll。
    /// C3 面数裁决档案：docs/research/2026-09-29-m5-fleet-import/m5-audit.md（先审计后入库）。
    /// </summary>
    public static class M5FleetPipeline
    {
        public const string RootDir = "Assets/Art/Purchased";
        const string k_MaterialsDir = RootDir + "/Materials";
        const string k_PrefabsDir = RootDir + "/Prefabs";
        const string k_HdrpLitShader = "HDRP/Lit";

        // 编目版本戳（VesselCatalog.fleetPipelineVersion，与 Kenney pipelineVersion 分账）：
        // 换源模型/改归一化规则/改贴图回接时 +1；EnsureBuilt 见版本不符即整跑重建。
        // 历史：1=首版（8 船入库，Houbei hero 白壳绿装+轮胎护舷）。
        public const int k_PipelineVersion = 1;

        /// <summary>Houbei 占位涂装：白壳 + 绿装（flat 调色板，替换原蓝迷彩贴图；无 AI 工序）。</summary>
        static readonly Color k_FcbHullWhite = new Color(0.93f, 0.94f, 0.92f);
        static readonly Color k_FcbFittingsGreen = new Color(0.13f, 0.32f, 0.20f);
        static readonly Color k_FcbTireBlack = new Color(0.05f, 0.05f, 0.05f);

        enum MaterialMode
        {
            Remap, // 逐材质槽位 HDRP/Lit 重建 + base color 贴图回接（出货 Standard → HDRP）
            FcbPlaceholder, // Houbei：白壳/绿装 flat 调色板 + 轮胎护舷（替换演示主角船）
        }

        struct FleetSpec
        {
            public VesselClass vesselClass;
            public string modelPath;      // Assets/ 下 FBX
            public string prefabName;
            public float targetLoa;       // 归一化目标（米；审计 finding 修正后的裁决值）
            public float draftFraction;   // 吃水 / 模型总高（船型估值，审计文档记载；水线观感定值）
            public MaterialMode materialMode;
            public float bowYawDeg;       // 字面量钉值（窄端实测证据回填；与几何不符构建即报错）
        }

        // 目标 LOA 出处：任务带 + 作者 desc（Suez-Max 322 m→按带内 300 归一化、Moss LNG 305→300、
        // RAstar 3200 级 32 m、Houbei 42 m、Cyclone 级 55 m、Trawler 25 m 级；箱船带内上沿 150/杂货 120）。
        // draftFraction = 吃水/模型总高（总高含桅杆/球罐，故各型不同）：按实船典型吃水 ÷ 审计实测
        // 归一化后总高折算的估值（trawler≈2.6/10.3、cargo≈7.5/37.5、container≈8.3/27.7、tanker≈14/50、
        // lng≈11.7/58.6、tug≈5.4/22.5、houbei≈1.7/16.8、pc3≈2.1/13.8 米）——逐船主甲板线分析未做，
        // 估值口径记入 m5-audit.md；bowYawDeg 初值 0（+Z 原生艏假设）——M5AssetAudit 4 向窄端证据回填钉值。
        static readonly FleetSpec[] k_Specs =
        {
            new FleetSpec { vesselClass = VesselClass.FishingTrawler, prefabName = "VesselFishingTrawler",
                modelPath = RootDir + "/fishing-trawler/source/Trawler.fbx", targetLoa = 25f, draftFraction = 0.25f,
                materialMode = MaterialMode.Remap, bowYawDeg = 90f }, // −X 艏（端宽 5.41/6.98，22% 差）
            new FleetSpec { vesselClass = VesselClass.CargoGeneral, prefabName = "VesselCargoGeneral",
                modelPath = RootDir + "/cargo-general/source/cargo_ship.fbx", targetLoa = 120f, draftFraction = 0.20f,
                materialMode = MaterialMode.Remap, bowYawDeg = 90f }, // −X 艏（16.37/19.24，⚠ 15% 差模糊档，按实测钉）
            new FleetSpec { vesselClass = VesselClass.CargoContainer, prefabName = "VesselCargoContainer",
                modelPath = RootDir + "/cargo-container/source/Ship.fbx", targetLoa = 150f, draftFraction = 0.30f,
                materialMode = MaterialMode.Remap, bowYawDeg = 90f }, // −X 艏（8.82/8.86，⚠ 盒形船体近平局，按实测钉，GUI 目检 follow-up）
            new FleetSpec { vesselClass = VesselClass.Tanker, prefabName = "VesselTanker",
                modelPath = RootDir + "/tanker-suezmax/source/tanker_ship.fbx", targetLoa = 300f, draftFraction = 0.28f,
                materialMode = MaterialMode.Remap, bowYawDeg = 0f }, // +Z 艏（19.57/19.63，⚠ 近平局，按实测钉）
            new FleetSpec { vesselClass = VesselClass.TankerLng, prefabName = "VesselTankerLng",
                modelPath = RootDir + "/tanker-lng/source/lng_ship.fbx", targetLoa = 300f, draftFraction = 0.20f,
                materialMode = MaterialMode.Remap, bowYawDeg = 0f }, // +Z 艏（5.25/5.80）
            new FleetSpec { vesselClass = VesselClass.Tug, prefabName = "VesselTug",
                modelPath = RootDir + "/tug-rastar3200/source/rastar_3200_tugboat.fbx", targetLoa = 32f, draftFraction = 0.24f,
                materialMode = MaterialMode.Remap, bowYawDeg = 0f }, // +Z 艏（11.69/11.73，⚠ 近平局；ASD 拖轮艉作业端更宽，合理）
            new FleetSpec { vesselClass = VesselClass.FcbHoubei, prefabName = "VesselFcbHoubei",
                modelPath = RootDir + "/fcb-houbei/source/type_22_missile_boat.fbx", targetLoa = 42f, draftFraction = 0.10f,
                materialMode = MaterialMode.FcbPlaceholder, bowYawDeg = 180f }, // −Z 艏（207.96/275.71，25% 差，证据最硬一档）
            new FleetSpec { vesselClass = VesselClass.FcbPc3, prefabName = "VesselFcbPc3",
                modelPath = RootDir + "/fcb-pc3/source/lowpoly_uss_hurricane_pc-3.fbx", targetLoa = 55f, draftFraction = 0.15f,
                materialMode = MaterialMode.Remap, bowYawDeg = 180f }, // −Z 艏（2.47/2.88）
        };

        /// <summary>M5 船型艏向查表口（VesselAssetPipeline.BowYawDeg 的转查落点）。</summary>
        public static float BowYawDeg(VesselClass vesselClass)
        {
            foreach (var spec in k_Specs)
            {
                if (spec.vesselClass == vesselClass) return spec.bowYawDeg;
            }
            return 0f;
        }

        /// <summary>
        /// 4 向艏向实测：船轴 = 包围盒水平长轴（采购件原生轴向不一：trawler/cargo 系 X 轴、
        /// tanker 系 Z 轴，M5 审计 2026-09-29）；船轴窄端 = 艏。返回把原生艏转到 +Z 的根 yaw：
        /// +Z 艏 0° · −X 艏 90° · −Z 艏 180° · +X 艏 270°（nativeBow = (−sinθ,0,cosθ) 的逆映射）。
        /// 两端宽度差 <15% 判模糊（盒形船体/双体船），logLine 带 ⚠ 供人工钉值裁决。
        /// </summary>
        public static float MeasureBowYaw(GameObject instance, out string logLine, out float bowEndWidth, out float sternEndWidth)
        {
            var bounds = VesselAssetPipeline.EncapsulatingRendererBounds(instance);
            bool alongX = bounds.size.x >= bounds.size.z;

            var points = new List<Vector3>();
            foreach (var filter in instance.GetComponentsInChildren<MeshFilter>(true))
            {
                var mesh = filter.sharedMesh;
                if (mesh == null) continue;
                var l2w = filter.transform.localToWorldMatrix;
                foreach (var v in mesh.vertices) points.Add(l2w.MultiplyPoint3x4(v));
            }
            float aMin = float.MaxValue, aMax = float.MinValue;
            foreach (var p in points)
            {
                float a = alongX ? p.x : p.z;
                if (a < aMin) aMin = a;
                if (a > aMax) aMax = a;
            }
            const int slices = 10;
            float span = aMax - aMin;
            float negW = 0f, posW = 0f;
            if (span > 0f)
            {
                // 首末各两片（跨船轴切片，量横向宽度：X 轴船量 |z|、Z 轴船量 |x|），平均抗单片空洞
                for (int s = 0; s < 2; s++)
                {
                    negW += SliceWidth(points, alongX, aMin + span * s / slices, aMin + span * (s + 1) / slices);
                    posW += SliceWidth(points, alongX, aMin + span * (slices - 2 + s) / slices, aMin + span * (slices - 1 + s) / slices);
                }
                negW *= 0.5f;
                posW *= 0.5f;
            }

            bool bowAtNeg = negW < posW;
            float yaw = alongX ? (bowAtNeg ? 90f : 270f) : (bowAtNeg ? 180f : 0f);
            bowEndWidth = bowAtNeg ? negW : posW;
            sternEndWidth = bowAtNeg ? posW : negW;
            float relDiff = Mathf.Abs(negW - posW) / Mathf.Max(negW, posW, 1e-5f);
            string axis = alongX ? "X" : "Z";
            string bowEnd = bowAtNeg ? $"−{axis}" : $"+{axis}";
            logLine = $"船轴 {axis}（extent {span:F1}）· −{axis}端 {negW:F2} / +{axis}端 {posW:F2} → 艏 {bowEnd} → yaw {yaw:0}°" +
                      (relDiff < 0.15f ? " ⚠ 端宽差<15%（盒形/双体），自动判定模糊，以人工钉值为准" : "");
            return yaw;
        }

        static float SliceWidth(List<Vector3> points, bool alongX, float lo, float hi)
        {
            float wMin = float.MaxValue, wMax = float.MinValue;
            foreach (var p in points)
            {
                float a = alongX ? p.x : p.z;
                if (a < lo || a >= hi) continue;
                float w = alongX ? p.z : p.x;
                if (w < wMin) wMin = w;
                if (w > wMax) wMax = w;
            }
            return wMax >= wMin ? wMax - wMin : 0f;
        }

        [MenuItem("Sango/M5/Build Purchased Fleet")]
        public static void BuildAll()
        {
            BuildAllInternal();
        }

        /// <summary>干净克隆一键重建前置检查：fleet 版本戳相符且 8 prefab 齐全则跳过。</summary>
        public static void EnsureBuilt()
        {
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(VesselAssetPipeline.CatalogAssetPath);
            if (catalog != null && catalog.fleetPipelineVersion == k_PipelineVersion)
            {
                var complete = true;
                foreach (var spec in k_Specs)
                {
                    var entry = catalog.GetEntry(spec.vesselClass);
                    if (entry == null || entry.prefab == null) { complete = false; break; }
                }
                if (complete) return;
            }
            BuildAllInternal();
        }

        static void BuildAllInternal()
        {
            EnsureFolder("Assets/Art", "Purchased");
            EnsureFolder(RootDir, "Materials");
            EnsureFolder(RootDir, "Prefabs");

            ApplyFbxImportSettings();

            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(VesselAssetPipeline.CatalogAssetPath);
            if (catalog == null)
            {
                catalog = ScriptableObject.CreateInstance<VesselCatalog>();
                AssetDatabase.CreateAsset(catalog, VesselAssetPipeline.CatalogAssetPath);
            }
            catalog.fleetPipelineVersion = k_PipelineVersion;

            // 整表只重写 M5 档位；Kenney 三档（与其他非 M5 条目）原样保留（对称于 VesselAssetPipeline）。
            var preserved = new List<VesselCatalog.Entry>();
            foreach (var existing in catalog.entries)
            {
                if (existing == null) continue;
                bool ownedByM5 = false;
                foreach (var spec in k_Specs)
                {
                    if (spec.vesselClass == existing.vesselClass) { ownedByM5 = true; break; }
                }
                if (!ownedByM5) preserved.Add(existing);
            }
            catalog.entries = new VesselCatalog.Entry[k_Specs.Length + preserved.Count];

            for (int i = 0; i < k_Specs.Length; i++)
            {
                catalog.entries[i] = BuildPrefabAndEntry(k_Specs[i]);
            }
            for (int p = 0; p < preserved.Count; p++) catalog.entries[k_Specs.Length + p] = preserved[p];

            EditorUtility.SetDirty(catalog);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            var sb = new StringBuilder($"[Sango.M5] purchased fleet built (fleetPipelineVersion {k_PipelineVersion}):\n");
            foreach (var spec in k_Specs)
            {
                var entry = catalog.GetEntry(spec.vesselClass);
                if (entry == null) { sb.AppendLine($"  {spec.vesselClass} MISSING"); continue; }
                sb.AppendFormat("  {0,-15} LOA={1:F1} m (target {2:F0})  waterlineOffsetY={3:F2} m  bowYaw={4}°  bowW={5:F2} sternW={6:F2}\n",
                    spec.vesselClass, entry.loaMeters, spec.targetLoa, entry.waterlineOffsetY,
                    spec.bowYawDeg, entry.bowEndWidth, entry.sternEndWidth);
            }
            Debug.Log(sb.ToString());
        }

        // ── (a) FBX 导入设置（幂等：仅字段变动时 SaveAndReimport）────────────────────
        static void ApplyFbxImportSettings()
        {
            foreach (var spec in k_Specs)
            {
                if (AssetImporter.GetAtPath(spec.modelPath) is not ModelImporter importer)
                {
                    Debug.LogError($"[Sango.M5] model missing or not a ModelImporter: {spec.modelPath}");
                    continue;
                }
                if (importer.importCameras || importer.importLights || importer.importAnimation
                    || importer.meshCompression != ModelImporterMeshCompression.Off
                    || !importer.isReadable)
                {
                    importer.importCameras = false;
                    importer.importLights = false;
                    importer.importAnimation = false;
                    importer.meshCompression = ModelImporterMeshCompression.Off; // hero/中景保真优先（Kenney 档 Medium 是低模内存取舍）
                    importer.isReadable = true; // VesselBuoyancy CPU 采样（M2-B 同款）
                    importer.SaveAndReimport();
                }
            }
        }

        // ── (b)(c)(d) 单船 prefab + 编目条目 ────────────────────────────────────────
        static VesselCatalog.Entry BuildPrefabAndEntry(FleetSpec spec)
        {
            var source = AssetDatabase.LoadAssetAtPath<GameObject>(spec.modelPath);
            if (source == null)
            {
                Debug.LogError($"[Sango.M5] model asset missing: {spec.modelPath}");
                return null;
            }

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(source);
            var bounds = VesselAssetPipeline.EncapsulatingRendererBounds(instance);

            // 艏向实测（4 向：船轴 = 水平长轴，采购件原生轴向不一）。与规格表钉值不符即报错
            // （字面量-几何耦合纪律，M2-A 测试同款把关）。
            float measuredYaw = MeasureBowYaw(instance, out var taperLog, out float bowEndWidth, out float sternEndWidth);
            if (!Mathf.Approximately(Mathf.DeltaAngle(measuredYaw, spec.bowYawDeg), 0f))
            {
                Debug.LogError($"[Sango.M5] {spec.vesselClass}: pinned bowYaw {spec.bowYawDeg}° contradicts measured taper " +
                               $"(measured yaw {measuredYaw:0}°; {taperLog}) — fix k_Specs literal");
            }
            bool negEndIsBow = Mathf.Approximately(Mathf.DeltaAngle(spec.bowYawDeg, 180f), 0f); // 日志取证用（Kenney 惯例）
            Debug.Log($"[Sango.M5] bow evidence {spec.prefabName}: {taperLog}; pinned yaw {spec.bowYawDeg}°" +
                      $"{(negEndIsBow ? " (native −Z bow)" : "")}");

            float extent = Mathf.Max(bounds.size.x, bounds.size.z);
            float scale = spec.targetLoa / extent;
            float draft = spec.draftFraction * bounds.size.y * scale;
            float loa = extent * scale;

            var root = new GameObject(spec.prefabName);
            instance.transform.SetParent(root.transform, true);
            var yaw = Quaternion.Euler(0f, spec.bowYawDeg, 0f);
            root.transform.localScale = new Vector3(scale, scale, scale);
            root.transform.rotation = yaw;
            var rotatedCenter = yaw * bounds.center;
            root.transform.position = new Vector3(
                -scale * rotatedCenter.x,
                -draft - scale * bounds.min.y,
                -scale * rotatedCenter.z);

            if (spec.materialMode == MaterialMode.FcbPlaceholder)
            {
                ApplyFcbPlaceholderDressing(root, instance, bounds, scale, draft);
            }
            else
            {
                ApplyRemappedMaterials(root, instance, spec);
            }

            PrefabUtility.SaveAsPrefabAsset(root, $"{k_PrefabsDir}/{spec.prefabName}.prefab");
            Object.DestroyImmediate(root);

            return new VesselCatalog.Entry
            {
                vesselClass = spec.vesselClass,
                prefab = AssetDatabase.LoadAssetAtPath<GameObject>($"{k_PrefabsDir}/{spec.prefabName}.prefab"),
                loaMeters = loa,
                waterlineOffsetY = -draft,
                bowEndWidth = bowEndWidth,
                sternEndWidth = sternEndWidth,
                bowYawDeg = spec.bowYawDeg, // 运行时放置层（AnchorageFleet）组合艏向用
            };
        }

        // ── (b1) Standard→HDRP/Lit 重置 + 贴图回接 ──────────────────────────────────
        // 逐材质槽位：每个源 Standard 材质生成/复用一个 HDRP/Lit 材质资产（路径稳定保 GUID），
        // 回接 base color（_MainTex→_BaseColorMap；无贴图时回退产品 textures/ 目录单图/纯色）。
        // 已是 HDRP shader 的源（现成 HDRP 声明件）走同一资产路径核对即用（幂等重建后必为 HDRP/Lit）。
        // 法线/金属度/粗糙度回接为已知简化：DirectX 法线绿通道约定差异 + Mask 图需通道烘焙，
        // 本批不接（audit 文档记载，验收看粉紫=shader 丢失，法线缺只降细节）。
        static void ApplyRemappedMaterials(GameObject root, GameObject instance, FleetSpec spec)
        {
            foreach (var renderer in instance.GetComponentsInChildren<Renderer>(true))
            {
                var src = renderer.sharedMaterials;
                var slots = new Material[src.Length];
                for (int s = 0; s < src.Length; s++)
                {
                    var source = src[s];
                    string slotName = source != null ? SanitizeFileName(source.name) : $"slot{s}";
                    string path = $"{k_MaterialsDir}/{spec.prefabName}.{slotName}.mat";
                    slots[s] = RemapMaterial(path, source, spec);
                }
                renderer.sharedMaterials = slots;
            }
        }

        static Material RemapMaterial(string path, Material source, FleetSpec spec)
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(Shader.Find(k_HdrpLitShader));
                AssetDatabase.CreateAsset(mat, path);
            }
            if (mat.shader.name != k_HdrpLitShader)
            {
                // 版本升级兜底：资产存在但 shader 不对（粉紫源）——整个重建
                mat.shader = Shader.Find(k_HdrpLitShader);
            }
            mat.SetTexture("_BaseColorMap", FindBaseMap(source, spec));
            var tint = source != null && source.HasProperty("_Color") ? source.GetColor("_Color") : Color.white;
            if (tint.a <= 0f) tint = Color.white;
            mat.SetColor("_BaseColor", tint);
            mat.SetFloat("_Smoothness", 0.55f);
            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", 0.15f);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        static Texture2D FindBaseMap(Material source, FleetSpec spec)
        {
            if (source != null)
            {
                if (source.GetTexture("_MainTex") is Texture2D main) return main;
                if (source.GetTexture("_BaseMap") is Texture2D baseMap) return baseMap;
                if (source.GetTexture("_BaseColorMap") is Texture2D baseColor) return baseColor; // 已是 HDRP 源
                // Standard 之外的命名兜底：TexEnv 里名字带 base/albedo/diffuse/color 的第一张
                var shader = source.shader;
                for (int p = 0; p < shader.GetPropertyCount(); p++)
                {
                    if (shader.GetPropertyType(p) != UnityEngine.Rendering.ShaderPropertyType.Texture) continue;
                    string propName = shader.GetPropertyName(p);
                    string n = propName.ToLowerInvariant();
                    if (source.GetTexture(propName) is Texture2D tex &&
                        (n.Contains("base") || n.Contains("albedo") || n.Contains("diffuse") || n.Contains("color")))
                    {
                        return tex;
                    }
                }
            }
            // FBX 外置贴图未被导入器接上时：扫产品 textures/ 目录（Sketchfab 直发 FBX 的布局是
            // 产品根/textures 与 source/ 平级——如 fishing-trawler/textures/Colour_Palette.png；
            // 两处都试，命名优先 base/color/albedo/palette，否则唯一图直取）
            string modelDir = Path.GetDirectoryName(spec.modelPath)?.Replace('\\', '/');
            var texDirs = new[] { modelDir + "/textures", Path.GetDirectoryName(modelDir)?.Replace('\\', '/') + "/textures" };
            foreach (string texDir in texDirs)
            {
                if (!AssetDatabase.IsValidFolder(texDir)) continue;
                var guids = AssetDatabase.FindAssets("t:texture2d", new[] { texDir });
                Texture2D fallback = null, named = null;
                foreach (var guid in guids)
                {
                    var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(AssetDatabase.GUIDToAssetPath(guid));
                    if (tex == null) continue;
                    fallback ??= tex;
                    string n = tex.name.ToLowerInvariant();
                    if (n.Contains("base") || n.Contains("color") || n.Contains("albedo") || n.Contains("palette")) named ??= tex;
                }
                if (named != null || fallback != null) return named ?? fallback;
            }
            return null;
        }

        // ── (b2) FCB 占位换装：白壳 + 绿装 + 轮胎护舷 ────────────────────────────────
        // 材质规则（数据驱动）：渲染器沿船长方向跨度 ≥45% LOA = 船体类 → 白；其余（驾驶台/
        // 桅杆/武器/舾装）→ 绿。轮胎护舷 = 程序化 torus 环（无贴图工序，环嵌船舷两侧）。
        static void ApplyFcbPlaceholderDressing(GameObject root, GameObject instance, Bounds bounds, float scale, float draft)
        {
            float shipSpan = Mathf.Max(bounds.size.x, bounds.size.z);
            var hullMat = FlatLit($"{k_MaterialsDir}/VesselFcbHoubei.HullWhite.mat", k_FcbHullWhite, 0.35f);
            var greenMat = FlatLit($"{k_MaterialsDir}/VesselFcbHoubei.FittingsGreen.mat", k_FcbFittingsGreen, 0.40f);
            foreach (var renderer in instance.GetComponentsInChildren<Renderer>(true))
            {
                float span = Mathf.Max(renderer.bounds.size.x, renderer.bounds.size.z);
                bool hullLike = span >= 0.45f * shipSpan;
                var slots = new Material[renderer.sharedMaterials.Length];
                for (int s = 0; s < slots.Length; s++) slots[s] = hullLike ? hullMat : greenMat;
                renderer.sharedMaterials = slots;
            }

            // 轮胎护舷：两舷各 6 环，沿船中前段均匀分布；环面竖直（轴指向舷外 X）。
            var tireMat = FlatLit($"{k_MaterialsDir}/VesselFcbHoubei.TireBlack.mat", k_FcbTireBlack, 0.25f);
            var tireMesh = CreateTorusMesh(ringRadius: 0.55f, tubeRadius: 0.22f, ringSegments: 16, tubeSegments: 8);
            float beam = bounds.size.x * scale;
            const int perSide = 6;
            var fenders = new GameObject("Tire Fenders");
            fenders.transform.SetParent(root.transform, false);
            for (int side = -1; side <= 1; side += 2)
            {
                for (int i = 0; i < perSide; i++)
                {
                    var go = new GameObject($"Tire {side:+0;-0}.{i}");
                    go.transform.SetParent(fenders.transform, false);
                    // root 局部单位 × scale = 米：位置按米给定再除 scale；y 相对水线（root 在 -draft）
                    float zMeters = Mathf.Lerp(-0.28f, 0.34f, i / (float)(perSide - 1)) * shipSpan * scale;
                    float xMeters = side * beam * 0.46f;
                    float yMeters = 0.7f;
                    go.transform.localPosition = new Vector3(xMeters / scale, (yMeters + draft) / scale, zMeters / scale);
                    go.transform.localRotation = Quaternion.Euler(0f, 0f, 90f); // torus 默认环面 XZ（轴 Y）→ 轴转到 X
                    go.transform.localScale = Vector3.one / scale;              // mesh 以米建模，抵消 root 烘焙缩放
                    go.AddComponent<MeshFilter>().sharedMesh = tireMesh;
                    go.AddComponent<MeshRenderer>().sharedMaterial = tireMat;
                }
            }
        }

        static Material FlatLit(string path, Color color, float smoothness)
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                mat = new Material(Shader.Find(k_HdrpLitShader));
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetColor("_BaseColor", color);
            mat.SetFloat("_Smoothness", smoothness);
            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", 0f);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        // torus：环面默认躺在 XZ 平面（轴向 +Y）。主半径 ringRadius、管半径 tubeRadius，米制单位。
        static Mesh CreateTorusMesh(float ringRadius, float tubeRadius, int ringSegments, int tubeSegments)
        {
            var mesh = new Mesh { name = "TireFenderTorus" };
            var verts = new Vector3[(ringSegments + 1) * (tubeSegments + 1)];
            var uvs = new Vector2[verts.Length];
            var tris = new int[ringSegments * tubeSegments * 6];
            int v = 0, t = 0;
            for (int r = 0; r <= ringSegments; r++)
            {
                float ringAngle = 2f * Mathf.PI * r / ringSegments;
                var ringDir = new Vector3(Mathf.Cos(ringAngle), 0f, Mathf.Sin(ringAngle));
                for (int u = 0; u <= tubeSegments; u++)
                {
                    float tubeAngle = 2f * Mathf.PI * u / tubeSegments;
                    verts[v] = (ringRadius + tubeRadius * Mathf.Cos(tubeAngle)) * ringDir
                               + tubeRadius * Mathf.Sin(tubeAngle) * Vector3.up;
                    uvs[v] = new Vector2(r / (float)ringSegments, u / (float)tubeSegments);
                    v++;
                }
            }
            for (int r = 0; r < ringSegments; r++)
            {
                for (int u = 0; u < tubeSegments; u++)
                {
                    int a = r * (tubeSegments + 1) + u;
                    int b = a + tubeSegments + 1;
                    tris[t++] = a; tris[t++] = b; tris[t++] = a + 1;
                    tris[t++] = b; tris[t++] = b + 1; tris[t++] = a + 1;
                }
            }
            mesh.vertices = verts;
            mesh.uv = uvs;
            mesh.triangles = tris;
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            return mesh;
        }

        static string SanitizeFileName(string name)
        {
            var invalid = Path.GetInvalidFileNameChars();
            var sb = new StringBuilder(name.Length);
            foreach (char c in name) sb.Append(invalid.Contains(c) ? '_' : c);
            return sb.ToString();
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
