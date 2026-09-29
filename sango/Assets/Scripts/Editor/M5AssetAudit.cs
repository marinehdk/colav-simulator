using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace Sango.Editor
{
    /// <summary>
    /// M5 采购船队面数/贴图审计闸门（C3：hero ≤150k tri，超标记录裁决，不静默入库）。
    /// 逐船输出：三角数/顶点数、贴图分辨率清单、UV 通道数、LOD 层级、导入后包围盒 vs 预期 LOA
    /// （偏差>20% = finding，编目归一化时修正）、±Z 两端宽度（BowYawDeg 几何证据）。
    /// 报告写 docs/research/2026-09-29-m5-fleet-import/m5-audit.md；
    /// 菜单 Sango/M5/Audit Purchased Fleet；batchmode: -executeMethod Sango.Editor.M5AssetAudit.Run。
    /// 另输出 seed-42 岛群实测中心/半径（锚地布景与 FCB 演示航线的清障核验用）。
    /// </summary>
    public static class M5AssetAudit
    {
        const string k_ReportDir = "docs/research/2026-09-29-m5-fleet-import"; // 仓库根 docs/（非 sango/Docs）
        const string k_ReportPath = k_ReportDir + "/m5-audit.md";
        const float k_HeroTriBudget = 150_000f; // C3：hero 档面数预算（tri）

        struct AuditSpec
        {
            public string label;        // 报告行名
            public string modelPath;    // Assets/ 下 FBX 路径
            public float expectedLoa;   // 预期 LOA（米，任务带/作者 desc；0 = 仅量测不比对）
            public string role;         // hero 候选 / 中景 / 远景剪影
        }

        // 预期 LOA 出处：任务带（渔 25m 级 / 箱杂 100-150 / 油 200-300 / 拖 30 / Houbei 42 /
        // PC-3 55）+ Sketchfab 作者 desc（Suez-Max 322 m、LNG 305 m——按带内 300 作预期，
        // 偏差按 finding 记录后再在编目归一化裁决）。
        static readonly AuditSpec[] k_Specs =
        {
            new AuditSpec { label = "fishing-trawler",  modelPath = "Assets/Art/Purchased/fishing-trawler/source/Trawler.fbx",              expectedLoa = 25f,  role = "中远" },
            new AuditSpec { label = "cargo-general",    modelPath = "Assets/Art/Purchased/cargo-general/source/cargo_ship.fbx",            expectedLoa = 125f, role = "中景" },
            new AuditSpec { label = "cargo-container",  modelPath = "Assets/Art/Purchased/cargo-container/source/Ship.fbx",               expectedLoa = 150f, role = "中景" },
            new AuditSpec { label = "tanker-suezmax",   modelPath = "Assets/Art/Purchased/tanker-suezmax/source/tanker_ship.fbx",         expectedLoa = 300f, role = "中景" },
            new AuditSpec { label = "tanker-lng",       modelPath = "Assets/Art/Purchased/tanker-lng/source/lng_ship.fbx",                expectedLoa = 300f, role = "中景" },
            new AuditSpec { label = "tug-rastar3200",   modelPath = "Assets/Art/Purchased/tug-rastar3200/source/rastar_3200_tugboat.fbx", expectedLoa = 30f,  role = "中景" },
            new AuditSpec { label = "fcb-houbei",       modelPath = "Assets/Art/Purchased/fcb-houbei/source/type_22_missile_boat.fbx",    expectedLoa = 42f,  role = "hero 候选" },
            new AuditSpec { label = "fcb-pc3",          modelPath = "Assets/Art/Purchased/fcb-pc3/source/lowpoly_uss_hurricane_pc-3.fbx", expectedLoa = 55f,  role = "中景/剪影" },
            new AuditSpec { label = "quaternius-boat",  modelPath = "Assets/Art/Purchased/Quaternius/source/Boat.fbx",                    expectedLoa = 0f,   role = "远景剪影(CC0)" },
            new AuditSpec { label = "quaternius-cruise",modelPath = "Assets/Art/Purchased/Quaternius/source/CruiseShip.fbx",              expectedLoa = 0f,   role = "远景剪影(CC0)" },
        };

        [MenuItem("Sango/M5/Audit Purchased Fleet")]
        public static void Run()
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
            var sb = new StringBuilder();
            sb.AppendLine("# M5 采购船队面数审计（C3 闸门）— m5-audit");
            sb.AppendLine();
            sb.AppendLine("- 日期：2026-09-29 ｜ 工具：`Sango.Editor.M5AssetAudit`（menu Sango/M5/Audit Purchased Fleet，batchmode `-executeMethod Sango.Editor.M5AssetAudit.Run`）");
            sb.AppendLine("- 闸门：**hero ≤150,000 tri**（C3）；超标船记录裁决=减面或降级中景，不静默入库。");
            sb.AppendLine("- 面数为 Unity 导入后实测（全部 MeshFilter × 全部 submesh 索引和，去重网格）；Sketchfab faceCount 仅作对照。");
            sb.AppendLine("- 包围盒 = 恒等姿态实例化的世界渲染器并集（含 FBX 导入缩放）；偏差>20% 记 finding，编目 LOA 归一化时修正。");
            sb.AppendLine();
            sb.AppendLine("| 船 | 角色 | tri | verts | 贴图 | UV 通道 | LOD | 包围盒 (x,y,z m) | 实测水平边 | 预期 LOA | 偏差 | C3 裁决 |");
            sb.AppendLine("|---|---|---|---|---|---|---|---|---|---|---|---|");

            var detail = new StringBuilder();
            foreach (var spec in k_Specs)
            {
                AuditOne(spec, sb, detail);
            }

            sb.AppendLine();
            sb.AppendLine("## 逐船明细");
            sb.AppendLine();
            sb.Append(detail);
            sb.AppendLine();
            sb.AppendLine("## 附：seed-42 岛群实测（锚地/航线清障数据）");
            sb.AppendLine();
            sb.AppendLine("```");
            sb.Append(AuditIslands());
            sb.AppendLine("```");

            // 仓库根 docs/（sango/Assets → 上两级）；sango/Docs 是项目内文档另一套，别混
            var full = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", k_ReportPath));
            Directory.CreateDirectory(Path.GetDirectoryName(full));
            File.WriteAllText(full, sb.ToString());
            Debug.Log($"[Sango.M5] audit written: {full}");
        }

        static void AuditOne(AuditSpec spec, StringBuilder table, StringBuilder detail)
        {
            var source = AssetDatabase.LoadAssetAtPath<GameObject>(spec.modelPath);
            if (source == null)
            {
                table.AppendLine($"| {spec.label} | {spec.role} | MISSING | | | | | 模型缺失：{spec.modelPath} | | | | | 阻断 |");
                Debug.LogError($"[Sango.M5] model missing: {spec.modelPath}");
                return;
            }
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(source);

            // 去重网格：FBX 常一 mesh 多 MeshFilter 引用，逐 filter 计会双计
            var meshes = new HashSet<Mesh>();
            foreach (var filter in instance.GetComponentsInChildren<MeshFilter>(true))
            {
                if (filter.sharedMesh != null) meshes.Add(filter.sharedMesh);
            }
            long tris = 0, verts = 0;
            foreach (var mesh in meshes)
            {
                for (int s = 0; s < mesh.subMeshCount; s++) tris += mesh.GetIndexCount(s) / 3;
                verts += mesh.vertexCount;
            }

            // UV 通道（有数据的最大通道号 +1），LOD 层级
            int uvChannels = 0;
            var uvScratch = new List<Vector4>();
            foreach (var mesh in meshes)
            {
                for (int ch = 3; ch >= 0; ch--)
                {
                    uvScratch.Clear();
                    mesh.GetUVs(ch, uvScratch);
                    if (uvScratch.Count > 0) { uvChannels = Mathf.Max(uvChannels, ch + 1); break; }
                }
            }
            int lodGroups = instance.GetComponentsInChildren<LODGroup>(true).Length;

            // 贴图：材质槽位枚举 shader 全部 TexEnv 属性 + FBX 内嵌贴图兜底
            var textures = new SortedSet<string>();
            foreach (var renderer in instance.GetComponentsInChildren<Renderer>(true))
            {
                foreach (var material in renderer.sharedMaterials)
                {
                    if (material == null || material.shader == null) continue;
                    var shader = material.shader;
                    for (int p = 0; p < shader.GetPropertyCount(); p++)
                    {
                        if (shader.GetPropertyType(p) != UnityEngine.Rendering.ShaderPropertyType.Texture) continue;
                        if (material.GetTexture(shader.GetPropertyName(p)) is Texture2D tex)
                        {
                            textures.Add($"{tex.name} {tex.width}x{tex.height}");
                        }
                    }
                }
            }
            foreach (var embedded in AssetDatabase.LoadAllAssetsAtPath(spec.modelPath).OfType<Texture2D>())
            {
                textures.Add($"{embedded.name} {embedded.width}x{embedded.height}");
            }
            string texSummary = textures.Count > 0
                ? string.Join("; ", textures.Take(6)) + (textures.Count > 6 ? $" (+{textures.Count - 6})" : "")
                : "无（flat/顶点色）";

            // 包围盒 vs 预期 LOA + 4 向艏向实测（M5FleetPipeline.MeasureBowYaw：船轴=水平长轴，窄端=艏）
            var bounds = VesselAssetPipeline.EncapsulatingRendererBounds(instance);
            float extent = Mathf.Max(bounds.size.x, bounds.size.z);
            string deviation = spec.expectedLoa > 0f ? $"{(extent - spec.expectedLoa) / spec.expectedLoa * 100f:+0;-0}%": "—";
            float measuredYaw = M5FleetPipeline.MeasureBowYaw(instance, out var taperLog, out var bowEndWidth, out var sternEndWidth);

            // C3 裁决（hero 预算）：hero 候选超标 → 阻断/减面；其余超标 → 限中景。
            string verdict = tris <= k_HeroTriBudget
                ? (spec.role.Contains("hero") ? "过闸（hero 可用）" : "过闸（≤150k）")
                : (spec.role.Contains("hero") ? "**超标：减面后方可作 hero**" : "**超 150k：限中景（不入 hero，不减面本批）**");

            table.AppendLine($"| {spec.label} | {spec.role} | {tris:N0} | {verts:N0} | {texSummary} | {uvChannels} | {lodGroups} | " +
                             $"({bounds.size.x:F1}, {bounds.size.y:F1}, {bounds.size.z:F1}) | {extent:F1} | {(spec.expectedLoa > 0 ? spec.expectedLoa.ToString("0") : "—")} | {deviation} | {verdict} |");

            detail.AppendLine($"### {spec.label} (`{spec.modelPath}`)");
            detail.AppendLine();
            detail.AppendLine($"- tri {tris:N0} / verts {verts:N0}（去重网格 {meshes.Count} 个，submesh 全计）");
            detail.AppendLine($"- 艏向证据：{taperLog}（艏端宽 {bowEndWidth:F2} / 艉端宽 {sternEndWidth:F2}）");
            detail.AppendLine($"- 渲染器 {instance.GetComponentsInChildren<Renderer>(true).Length} 个；UV 通道 {uvChannels}；LODGroup {lodGroups} 个");
            if (textures.Count > 0)
            {
                detail.AppendLine("- 贴图清单：");
                foreach (var t in textures) detail.AppendLine($"  - {t}");
            }
            detail.AppendLine($"- 材质 shader：{string.Join(", ", instance.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m != null).Select(m => m.shader.name).Distinct())}");
            detail.AppendLine();

            Object.DestroyImmediate(instance);
        }

        // 岛群实测：与 M1SceneBootstrapper 同参（IslandRebuild.M1Baseline 计数/尺寸，材质占位），
        // 输出各岛局部中心/世界中心/可视半径（≈0.8R 岸线口径同 M2-C）。
        static string AuditIslands()
        {
            var baseline = IslandRebuild.M1Baseline();
            var islands = PerlinIslandGenerator.GenerateIslands(baseline);
            islands.transform.position = new Vector3(0f, 0f, 180f);
            var sb = new StringBuilder();
            sb.AppendLine($"seed {baseline.seed}，{baseline.count} 岛，sizeRange {baseline.sizeRange.x:0}-{baseline.sizeRange.y:0} m，cluster r={baseline.clusterRadius:0} m，cluster center (0,0,180)");
            foreach (Transform child in islands.transform)
            {
                var b = VesselAssetPipeline.EncapsulatingRendererBounds(child.gameObject);
                float radius = Mathf.Max(b.size.x, b.size.z) * 0.5f;
                sb.AppendLine($"岛 {child.name}: local ({child.localPosition.x:F1}, {child.localPosition.z:F1})  world ({b.center.x:F1}, {b.center.z:F1})  R≈{radius:F1} m  可视岸线≈{0.8f * radius:F1} m");
            }
            Object.DestroyImmediate(islands);
            return sb.ToString();
        }
    }
}
