using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Editor
{
    /// <summary>
    /// M7-B 海峡浮标/动目标/渔排构建 stage（Editor，幂等；M6StraitSceneBootstrapper.BuildScene
    /// 内挂接，顺序在 M7BackdropBuilder 之后）。三步全部先过构建期水深门禁（fail-fast，不静默
    /// 换点）再落物：
    /// B1 IALA A 区浮标 13 座（M7BMath.ChannelBuoys：主航道带 8 侧向+2 方位、锚地口 3；
    ///   逐种别基本体组合合并单 Mesh 多 submesh——罐/锥/双锥顶标/红白条+球顶；每座挂 BuoyBeacon
    ///   夜灯，复用 NavigationLights 光弧工艺的十字灯片+点光，灯质=快闪/群闪/长闪区分标种）；
    /// B2 渡轮/拖轮动目标（复用 M1SceneBootstrapper.PlaceCatalogShip + WaypointFollower
    ///   autoStart：渡轮=Medium 客船件——编目无 ferry 专档，ocean-liner 为最近替代，LOA 60 m；
    ///   拖轮=Tug RAstar 3200——沿 M7BMath 航线往返/闭环，航路 100 m 逐点采样高程&lt;0）；
    /// B4 渔排 5 组（木板排+浮筒+棚屋基本体组合合并单 Mesh，落 Batam 北侧浅水 2-8 m 窗，
    ///   FishFarmSway 系留微摇摆）。
    /// 落位 provenance：tmp/m7b/site_analysis.py + route_probe.py 对 tmp/m6-data RAW 离线实采
    /// （2026-09-29），构建期 Terrain.SampleHeight 实采复验。
    /// </summary>
    public static class M7BSceneBuilder
    {
        public struct StageStats
        {
            public int buoys;
            public int movingShips;
            public int farmGroups;
            public int routeSamples; // 渡轮+拖轮航路验证采样点合计
        }

        /// <summary>浮标落位硬门：海床高程 &lt; 0（任务契约"浮标点位水深&lt;0"；海峡 TSS 实采
        /// −55 至 −135 m 深水，浮标链长不设限，"贴近水面"指浮体浮于 y≈0）。</summary>
        const float k_BuoyDepthMarginM = 0f;
        /// <summary>航路（渡轮/拖轮）硬门：逐点高程 &lt; 0（任务契约；渡轮近岸起航段实采最深 −8.5 m）。</summary>
        const float k_RouteDepthMarginM = 0f;

        static readonly Color k_MatRed = new Color(0.72f, 0.06f, 0.05f);
        static readonly Color k_MatGreen = new Color(0.05f, 0.50f, 0.12f);
        static readonly Color k_MatBlack = new Color(0.04f, 0.04f, 0.045f);
        static readonly Color k_MatYellow = new Color(0.93f, 0.74f, 0.06f);
        static readonly Color k_MatWhite = new Color(0.90f, 0.90f, 0.88f);
        static readonly Color k_MatWood = new Color(0.44f, 0.32f, 0.18f);
        static readonly Color k_MatFloat = new Color(0.10f, 0.22f, 0.38f);
        static readonly Color k_MatRoof = new Color(0.55f, 0.22f, 0.10f);

        /// <summary>构建 M7-B stage（顺序敏感：水深门禁 → 浮标 → 渡轮/拖轮 → 渔排）。幂等：
        /// NewScene 重建流程下场景对象每次全新创建；Mesh/Material 资产 load-or-create GUID 稳定。</summary>
        public static StageStats Build(M6Manifest manifest, WaterSurface water, WeatherController weather,
            VesselCatalog catalog, M6TerrainMath.ElevationSampler sample)
        {
            var stats = new StageStats();

            // ── 水深门禁（先全部过门再落物；fail-fast 不静默换点）────────────────────
            var buoyPts = new Vector2[M7BMath.ChannelBuoys.Length];
            for (int i = 0; i < M7BMath.ChannelBuoys.Length; i++) buoyPts[i] = M7BMath.ChannelBuoys[i].xz;
            var buoyGate = M6TerrainMath.ValidateDepths(sample, buoyPts, k_BuoyDepthMarginM);
            if (!buoyGate.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M7B] BUOY DEPTH GATE FAIL: buoy at ({buoyGate.worstPoint.x:F0},{buoyGate.worstPoint.y:F0}) " +
                    $"elevation {buoyGate.worstElevationM:F1} m >= {k_BuoyDepthMarginM:F0} m — move the literal, do not silently relocate");

            var ferryWps = M7BMath.FerryWaypoints();
            var tugWps = M7BMath.TugLoopWaypoints();
            var ferryGate = M6TerrainMath.ValidateRoute(sample, ferryWps, M7BMath.RouteSampleStepM, k_RouteDepthMarginM);
            var tugGate = M6TerrainMath.ValidateRoute(sample, tugWps, M7BMath.RouteSampleStepM, k_RouteDepthMarginM);
            stats.routeSamples = ferryGate.samples + tugGate.samples;
            if (!ferryGate.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M7B] FERRY DEPTH GATE FAIL: sample at ({ferryGate.worstPoint.x:F0},{ferryGate.worstPoint.y:F0}) " +
                    $"elevation {ferryGate.worstElevationM:F1} m >= {k_RouteDepthMarginM:F0} m ({ferryGate.samples} samples) — reroute the literal, do not silently relocate");
            if (!tugGate.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M7B] TUG DEPTH GATE FAIL: sample at ({tugGate.worstPoint.x:F0},{tugGate.worstPoint.y:F0}) " +
                    $"elevation {tugGate.worstElevationM:F1} m >= {k_RouteDepthMarginM:F0} m ({tugGate.samples} samples) — reroute the literal, do not silently relocate");

            var farmGate = M7BMath.ValidateShallowBand(sample, M7BMath.FishFarmFootprints());
            if (!farmGate.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M7B] FARM DEPTH GATE FAIL: farm point ({farmGate.worstPoint.x:F0},{farmGate.worstPoint.y:F0}) " +
                    $"elevation {farmGate.worstElevationM:F1} m outside [{-M7BMath.FishFarmMaxDepthM:F0},{-M7BMath.FishFarmMinDepthM:F0}] m window — move the literal, do not silently relocate");

            var root = new GameObject("M7B Traffic & Buoys");

            // ── B1：IALA 浮标 ───────────────────────────────────────────────────────
            var mats = new Dictionary<string, Material>
            {
                { "Red", EnsureMaterial("M7B-Red", k_MatRed, 0.35f, 0.1f) },
                { "Green", EnsureMaterial("M7B-Green", k_MatGreen, 0.35f, 0.1f) },
                { "Black", EnsureMaterial("M7B-Black", k_MatBlack, 0.4f, 0.0f) },
                { "Yellow", EnsureMaterial("M7B-Yellow", k_MatYellow, 0.4f, 0.0f) },
                { "White", EnsureMaterial("M7B-White", k_MatWhite, 0.35f, 0.0f) },
            };
            for (int i = 0; i < M7BMath.ChannelBuoys.Length; i++)
            {
                var site = M7BMath.ChannelBuoys[i];
                var (mesh, matNames, lampY) = BuildBuoyMesh(site.kind);
                var go = new GameObject($"M7B Buoy {i:00} {site.kind}", typeof(MeshFilter), typeof(MeshRenderer));
                go.GetComponent<MeshFilter>().sharedMesh = EnsureMesh($"M7B_Buoy_{site.kind}", mesh);
                var renderMats = new Material[matNames.Count];
                for (int m = 0; m < matNames.Count; m++) renderMats[m] = mats[matNames[m]];
                go.GetComponent<MeshRenderer>().sharedMaterials = renderMats;
                go.transform.position = new Vector3(site.xz.x, 0f, site.xz.y); // 海面 y=0，浮体吃水由网格自带
                GameObjectUtility.SetStaticEditorFlags(go, StaticEditorFlags.BatchingStatic);
                go.transform.SetParent(root.transform, false);

                var beacon = go.AddComponent<BuoyBeacon>();
                beacon.weather = weather;
                beacon.pattern = M7BMath.PatternFor(site.kind);
                beacon.color = M7BMath.LightColorFor(site.kind);
                beacon.lampLocalOffset = new Vector3(0f, lampY, 0f);
                stats.buoys++;
            }

            // ── B2：渡轮/拖轮 ───────────────────────────────────────────────────────
            if (catalog.GetEntry(VesselClass.Medium)?.prefab == null || catalog.GetEntry(VesselClass.Tug)?.prefab == null)
                throw new System.InvalidOperationException("[Sango.M7B] vessel catalog missing Medium/Tug entry — run M5 pipeline first");

            stats.movingShips += PlaceMovingShip(catalog, VesselClass.Medium, ferryWps, 8f, 12f, 18f, water, weather, root.transform, "M7B Ferry");
            stats.movingShips += PlaceMovingShip(catalog, VesselClass.Tug, tugWps, 5f, 30f, 10f, water, weather, root.transform, "M7B Tug");

            // ── B4：渔排 5 组 ───────────────────────────────────────────────────────
            var wood = EnsureMaterial("M7B-Wood", k_MatWood, 0.2f, 0.0f);
            var floatMat = EnsureMaterial("M7B-Float", k_MatFloat, 0.3f, 0.2f);
            var roof = EnsureMaterial("M7B-Roof", k_MatRoof, 0.25f, 0.0f);
            for (int i = 0; i < M7BMath.FishFarmSites.Length; i++)
            {
                var mesh = BuildFarmMesh();
                var go = new GameObject($"M7B Fish Farm {i:00}", typeof(MeshFilter), typeof(MeshRenderer));
                go.GetComponent<MeshFilter>().sharedMesh = EnsureMesh($"M7B_Farm_{i:00}", mesh);
                go.GetComponent<MeshRenderer>().sharedMaterials = new[] { wood, floatMat, roof };
                var site = M7BMath.FishFarmSites[i];
                float yaw = (M7BackdropMath.Hash(i, 7, 13) % 360u); // 确定性组向（渔排无航向语义）
                go.transform.position = new Vector3(site.x, 0f, site.y);
                go.transform.rotation = Quaternion.Euler(0f, yaw, 0f);
                go.AddComponent<FishFarmSway>().phaseDeg = i * 73f; // 组间错相（纯函数相位锚）
                // 注意：渔排随浪微摇摆，**不可**标 static（静态批烘焙位姿会吞掉运行时位移）
                go.transform.SetParent(root.transform, false);
                stats.farmGroups++;
            }

            Debug.Log($"[Sango.M7B] stage: {stats.buoys} buoys (gate shallowest {buoyGate.shallowestElevationM:F1} m), " +
                      $"{stats.movingShips} moving ships (ferry {ferryGate.samples} / tug {tugGate.samples} route samples, " +
                      $"shallowest {Mathf.Max(ferryGate.shallowestElevationM, tugGate.shallowestElevationM):F1} m), " +
                      $"{stats.farmGroups} fish farms (band gate shallowest {farmGate.worstElevationM:F1} m)");
            return stats;
        }

        static int PlaceMovingShip(VesselCatalog catalog, VesselClass vesselClass, Vector2[] waypoints,
            float cruiseMps, float yawRateDps, float arrivalM, WaterSurface water, WeatherController weather,
            Transform parent, string goName)
        {
            // 起点位姿 = 首航点 + 朝向次航点（PlaceCatalogShip 负责水线/艏向组合烘焙）
            var from = waypoints[0];
            var to = waypoints[1];
            var dir = (to - from).normalized;
            float headingDeg = Mathf.Atan2(dir.x, dir.y) * Mathf.Rad2Deg;
            var ship = M1SceneBootstrapper.PlaceCatalogShip(catalog, vesselClass, from, headingDeg, parent, water);
            if (ship == null)
                throw new System.InvalidOperationException($"[Sango.M7B] {goName} placement failed (catalog entry {vesselClass})");
            ship.name = goName;

            var follower = ship.AddComponent<WaypointFollower>();
            follower.autoStart = true;            // Play 即起跑（常动目标；G 键暂停/恢复仍可用）
            follower.loopWaypoints = true;        // M7 review B2：终点到达即循环再跑，长会话不冻结成静态障碍
            follower.demoHotkeysEnabled = false;  // G 键演示归主角船，动目标不抢
            follower.waypoints = waypoints;
            follower.cruiseSpeedMps = cruiseMps;
            follower.maxYawRateDegPerSec = yawRateDps;
            follower.arrivalRadiusM = arrivalM;
            follower.bowYawDegOffset = VesselAssetPipeline.BowYawDeg(vesselClass);
            M1SceneBootstrapper.AttachNavigationLights(ship, vesselClass, weather);
            return 1;
        }

        // ── 浮标几何（局部系 +Y 上、水线 y=0；返回 (合并 Mesh, submesh 材质名序, 灯位高)）──

        const int k_Seg = 12; // 圆周段数（低模远景可读即可）

        static (Mesh mesh, List<string> matNames, float lampY) BuildBuoyMesh(M7BMath.IalaBuoyKind kind)
        {
            var verts = new List<Vector3>();
            var normals = new List<Vector3>();
            var subTris = new List<List<int>>();
            var matNames = new List<string>();
            float lampY;

            // 浮体吃水带：底 -1.8 m（浅吃水视觉），水上部分按种别
            switch (kind)
            {
                case M7BMath.IalaBuoyKind.PortHandCan: // 红罐：圆柱浮体 + 灯架短柱
                {
                    int body = BeginSub(matNames, subTris, "Red");
                    AppendCylinder(verts, normals, subTris[body], new Vector3(0f, 0.1f, 0f), 1.15f, 3.8f);
                    AppendCylinderCap(verts, normals, subTris[body], new Vector3(0f, 2.0f, 0f), 1.15f, true);
                    int cage = BeginSub(matNames, subTris, "Black");
                    AppendBox(verts, normals, subTris[cage], new Vector3(0f, 2.2f, 0f), new Vector3(0.5f, 0.8f, 0.5f));
                    lampY = 2.8f;
                    break;
                }
                case M7BMath.IalaBuoyKind.StarboardCone: // 绿锥：锥形浮体
                {
                    int body = BeginSub(matNames, subTris, "Green");
                    AppendCone(verts, normals, subTris[body], new Vector3(0f, 0.2f, 0f), 1.3f, 3.9f);
                    AppendConeCap(verts, normals, subTris[body], new Vector3(0f, -1.75f, 0f), 1.3f);
                    int cage = BeginSub(matNames, subTris, "Black");
                    AppendBox(verts, normals, subTris[cage], new Vector3(0f, 2.35f, 0f), new Vector3(0.45f, 0.7f, 0.45f));
                    lampY = 2.9f;
                    break;
                }
                case M7BMath.IalaBuoyKind.NorthCardinal: // 北方位：黑上黄下 + 双锥朝上
                {
                    Band doubleBand = new Band { lower = "Yellow", upper = "Black" };
                    lampY = BuildCardinalBody(verts, normals, subTris, matNames, doubleBand, up: true);
                    break;
                }
                case M7BMath.IalaBuoyKind.SouthCardinal: // 南方位：黄上黑下 + 双锥朝下
                {
                    Band southBand = new Band { lower = "Black", upper = "Yellow" };
                    lampY = BuildCardinalBody(verts, normals, subTris, matNames, southBand, up: false);
                    break;
                }
                default: // SafeWater：红白横条 + 红球顶
                {
                    int band0 = BeginSub(matNames, subTris, "Red");
                    AppendCylinder(verts, normals, subTris[band0], new Vector3(0f, -1.0f, 0f), 1.15f, 1.6f);
                    int band1 = BeginSub(matNames, subTris, "White");
                    AppendCylinder(verts, normals, subTris[band1], new Vector3(0f, 0.6f, 0f), 1.15f, 1.6f);
                    int band2 = BeginSub(matNames, subTris, "Red");
                    AppendCylinder(verts, normals, subTris[band2], new Vector3(0f, 2.0f, 0f), 1.15f, 1.2f);
                    AppendCylinderCap(verts, normals, subTris[band2], new Vector3(0f, 2.6f, 0f), 1.15f, true);
                    int ball = BeginSub(matNames, subTris, "Red");
                    AppendSphere(verts, normals, subTris[ball], new Vector3(0f, 3.2f, 0f), 0.7f);
                    lampY = 3.2f;
                    break;
                }
            }

            var mesh = new Mesh { indexFormat = IndexFormat.UInt16 };
            mesh.SetVertices(verts);
            mesh.SetNormals(normals);
            mesh.subMeshCount = subTris.Count;
            for (int i = 0; i < subTris.Count; i++) mesh.SetTriangles(subTris[i], i, false);
            mesh.RecalculateBounds();
            return (mesh, matNames, lampY);
        }

        struct Band { public string lower, upper; }

        /// <summary>方位标浮体（双色横带圆柱）+ 顶标（N 双锥朝上 / S 双锥朝下）；返回灯位高。</summary>
        static float BuildCardinalBody(List<Vector3> verts, List<Vector3> normals, List<List<int>> subTris,
            List<string> matNames, Band band, bool up)
        {
            int lower = BeginSub(matNames, subTris, band.lower);
            AppendCylinder(verts, normals, subTris[lower], new Vector3(0f, -0.5f, 0f), 1.15f, 2.6f);
            int upper = BeginSub(matNames, subTris, band.upper);
            AppendCylinder(verts, normals, subTris[upper], new Vector3(0f, 1.4f, 0f), 1.15f, 1.8f);
            AppendCylinderCap(verts, normals, subTris[upper], new Vector3(0f, 2.3f, 0f), 1.15f, true);

            // 顶标双锥（小锥 h=0.7 r=0.55；N 叠两枚尖朝上，S 桅杆短柱下挂两枚尖朝下）
            int mark = BeginSub(matNames, subTris, "Black");
            if (up)
            {
                AppendCone(verts, normals, subTris[mark], new Vector3(0f, 2.65f, 0f), 0.55f, 0.7f);
                AppendCone(verts, normals, subTris[mark], new Vector3(0f, 3.35f, 0f), 0.55f, 0.7f);
            }
            else
            {
                AppendCone(verts, normals, subTris[mark], new Vector3(0f, 2.3f, 0f), 0.55f, 0.7f, inverted: true);
                AppendCone(verts, normals, subTris[mark], new Vector3(0f, 3.0f, 0f), 0.55f, 0.7f, inverted: true);
            }
            return 3.9f;
        }

        // ── 渔排几何（木板排 + 浮筒 + 棚屋；submesh 0 木 / 1 浮筒 / 2 屋顶）────────────

        static Mesh BuildFarmMesh()
        {
            var verts = new List<Vector3>();
            var normals = new List<Vector3>();
            var subTris = new List<List<int>> { new List<int>(), new List<int>(), new List<int>() };

            // 两组排架（沿 x 并排，间距 1.2 m 走道）：每架 16×8 m 甲板
            for (int u = 0; u < 2; u++)
            {
                float ux = u == 0 ? -8.6f : 8.6f;
                // 木板甲板：7 条板条（沿 x 长条，留缝显木排质感）
                for (int p = 0; p < 7; p++)
                {
                    float z = -3.6f + p * 1.2f;
                    AppendBox(verts, normals, subTris[0], new Vector3(ux, 0.22f, z), new Vector3(16f, 0.12f, 1.0f));
                }
                // 浮筒：每架 4 只（两两沿边）
                for (int f = 0; f < 4; f++)
                {
                    float x = ux + (f % 2 == 0 ? -6.5f : 6.5f);
                    float z = f < 2 ? -2.8f : 2.8f;
                    AppendBox(verts, normals, subTris[1], new Vector3(x, -0.1f, z), new Vector3(2.4f, 0.9f, 0.9f));
                }
                // 棚屋：仅第一架（角柱 4 + 平顶 + 脊条）
                if (u == 0)
                {
                    foreach (var (cx, cz) in new[] { (-2.4f, -1.6f), (2.4f, -1.6f), (-2.4f, 1.6f), (2.4f, 1.6f) })
                        AppendBox(verts, normals, subTris[0], new Vector3(ux + cx, 1.15f, cz), new Vector3(0.16f, 1.9f, 0.16f));
                    AppendBox(verts, normals, subTris[2], new Vector3(ux, 2.2f, 0f), new Vector3(6.2f, 0.12f, 4.6f));
                    AppendBox(verts, normals, subTris[2], new Vector3(ux, 2.3f, 0f), new Vector3(0.5f, 0.2f, 4.8f));
                }
            }
            // 连桥（跨走道）
            AppendBox(verts, normals, subTris[0], new Vector3(0f, 0.2f, 0f), new Vector3(1.4f, 0.1f, 6f));

            var mesh = new Mesh { indexFormat = IndexFormat.UInt16 };
            mesh.SetVertices(verts);
            mesh.SetNormals(normals);
            mesh.subMeshCount = subTris.Count;
            for (int i = 0; i < subTris.Count; i++) mesh.SetTriangles(subTris[i], i, false);
            mesh.RecalculateBounds();
            return mesh;
        }

        // ── 基本体网格 appender（构建期一次性；共享 verts/normals、逐 submesh 三角表）────

        static int BeginSub(List<string> matNames, List<List<int>> subTris, string matName)
        {
            matNames.Add(matName);
            subTris.Add(new List<int>());
            return subTris.Count - 1;
        }

        static void AppendQuad(List<Vector3> verts, List<Vector3> normals, List<int> tris,
            Vector3 c, Vector3 u, Vector3 v, Vector3 n)
        {
            int b = verts.Count;
            verts.Add(c - u - v); normals.Add(n);
            verts.Add(c + u - v); normals.Add(n);
            verts.Add(c + u + v); normals.Add(n);
            verts.Add(c - u + v); normals.Add(n);
            tris.AddRange(new[] { b, b + 1, b + 2, b, b + 2, b + 3 });
        }

        /// <summary>轴对齐盒（6 面硬边）。</summary>
        static void AppendBox(List<Vector3> verts, List<Vector3> normals, List<int> tris, Vector3 center, Vector3 size)
        {
            var h = size * 0.5f;
            AppendQuad(verts, normals, tris, center + Vector3.up * h.y, Vector3.right * h.x, Vector3.forward * h.z, Vector3.up);
            AppendQuad(verts, normals, tris, center - Vector3.up * h.y, Vector3.forward * h.z, Vector3.right * h.x, -Vector3.up);
            AppendQuad(verts, normals, tris, center + Vector3.right * h.x, Vector3.forward * h.z, Vector3.up * h.y, Vector3.right);
            AppendQuad(verts, normals, tris, center - Vector3.right * h.x, Vector3.up * h.y, Vector3.forward * h.z, -Vector3.right);
            AppendQuad(verts, normals, tris, center + Vector3.forward * h.z, Vector3.up * h.y, Vector3.right * h.x, Vector3.forward);
            AppendQuad(verts, normals, tris, center - Vector3.forward * h.z, Vector3.right * h.x, Vector3.up * h.y, -Vector3.forward);
        }

        /// <summary>竖直圆柱侧面（顶/底盖另调 AppendCylinderCap）。绕向对齐 M7-A AppendQuad
        /// 的实证口径（正面 ⇔ 右手边叉 = −stated normal）。</summary>
        static void AppendCylinder(List<Vector3> verts, List<Vector3> normals, List<int> tris,
            Vector3 center, float radius, float height)
        {
            int b = verts.Count;
            for (int i = 0; i <= k_Seg; i++)
            {
                float a = i / (float)k_Seg * Mathf.PI * 2f;
                var dir = new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a));
                verts.Add(center + dir * radius - Vector3.up * (height * 0.5f));
                normals.Add(dir);
                verts.Add(center + dir * radius + Vector3.up * (height * 0.5f));
                normals.Add(dir);
            }
            for (int i = 0; i < k_Seg; i++)
            {
                int v0 = b + i * 2;
                tris.AddRange(new[] { v0, v0 + 3, v0 + 2, v0, v0 + 1, v0 + 3 });
            }
        }

        /// <summary>圆柱顶盖/底盖（扇形）。</summary>
        static void AppendCylinderCap(List<Vector3> verts, List<Vector3> normals, List<int> tris,
            Vector3 center, float radius, bool facingUp)
        {
            var n = facingUp ? Vector3.up : -Vector3.up;
            int c = verts.Count;
            verts.Add(center); normals.Add(n);
            for (int i = 0; i <= k_Seg; i++)
            {
                float a = i / (float)k_Seg * Mathf.PI * 2f;
                verts.Add(center + new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a)) * radius);
                normals.Add(n);
            }
            for (int i = 0; i < k_Seg; i++)
            {
                if (facingUp) tris.AddRange(new[] { c, c + 2 + i, c + 1 + i });
                else tris.AddRange(new[] { c, c + 1 + i, c + 2 + i });
            }
        }

        /// <summary>竖直圆锥（尖端在上）。inverted = 尖朝下（南方位顶标）。</summary>
        static void AppendCone(List<Vector3> verts, List<Vector3> normals, List<int> tris,
            Vector3 center, float baseRadius, float height, bool inverted = false)
        {
            float half = height * 0.5f;
            float slope = baseRadius / height; // 侧面法线的水平/垂直分量比
            int b = verts.Count;
            float apexY = inverted ? center.y - half : center.y + half;
            float baseY = inverted ? center.y + half : center.y - half;
            for (int i = 0; i <= k_Seg; i++)
            {
                float a = i / (float)k_Seg * Mathf.PI * 2f;
                var dir = new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a));
                var n = new Vector3(dir.x, inverted ? -slope : slope, dir.z).normalized;
                verts.Add(new Vector3(center.x + dir.x * baseRadius, baseY, center.z + dir.z * baseRadius));
                normals.Add(n);
                verts.Add(new Vector3(center.x, apexY, center.z));
                normals.Add(n);
            }
            for (int i = 0; i < k_Seg; i++)
            {
                int v0 = b + i * 2;
                tris.AddRange(new[] { v0, v0 + 3, v0 + 2, v0, v0 + 1, v0 + 3 });
            }
        }

        /// <summary>圆锥底盖（扇形；法线朝下/上按 inverted）。</summary>
        static void AppendConeCap(List<Vector3> verts, List<Vector3> normals, List<int> tris,
            Vector3 center, float radius)
        {
            AppendCylinderCap(verts, normals, tris, center, radius, facingUp: false);
        }

        /// <summary>低模 UV 球（8 纵 × 5 环；安全水域标球顶）。</summary>
        static void AppendSphere(List<Vector3> verts, List<Vector3> normals, List<int> tris,
            Vector3 center, float radius)
        {
            const int lon = 8, lat = 5;
            int b = verts.Count;
            for (int y = 0; y <= lat; y++)
            {
                float phi = y / (float)lat * Mathf.PI; // 0=北极
                for (int x = 0; x <= lon; x++)
                {
                    float theta = x / (float)lon * Mathf.PI * 2f;
                    var n = new Vector3(Mathf.Sin(phi) * Mathf.Sin(theta), Mathf.Cos(phi), Mathf.Sin(phi) * Mathf.Cos(theta));
                    verts.Add(center + n * radius);
                    normals.Add(n);
                }
            }
            for (int y = 0; y < lat; y++)
            {
                for (int x = 0; x < lon; x++)
                {
                    int r0 = b + y * (lon + 1), r1 = b + (y + 1) * (lon + 1);
                    tris.AddRange(new[] { r0 + x, r0 + x + 1, r1 + x + 1, r0 + x, r1 + x + 1, r1 + x });
                }
            }
        }

        // ── 资产工具（load-or-create；M7-A EnsureMesh/EnsureMaterial 同款，GUID 稳定）────

        static Mesh EnsureMesh(string name, Mesh built)
        {
            string path = $"{M7BackdropBuilder.MeshDir}/{name}.asset";
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

        static Material EnsureMaterial(string name, Color color, float smoothness, float metallic)
        {
            string path = $"{M7BackdropBuilder.MaterialDir}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = Shader.Find("HDRP/Lit");
                if (shader == null) throw new System.Exception("[Sango.M7B] HDRP/Lit shader not found");
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetColor("_BaseColor", color);
            mat.SetFloat("_Smoothness", smoothness);
            mat.SetFloat("_Metallic", metallic);
            EditorUtility.SetDirty(mat);
            return mat;
        }
    }
}
