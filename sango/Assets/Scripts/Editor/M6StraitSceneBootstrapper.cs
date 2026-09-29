using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Editor
{
    /// <summary>
    /// M6 新加坡海峡场景生成器（真实地形；幂等，batchmode 可执行）。
    /// batchmode: -executeMethod Sango.Editor.M6StraitSceneBootstrapper.Build（门禁契约方法名）。
    /// 组成：29 块真实地形（M6TerrainPipeline 资产：GEBCO 水深并入、世界 y=真实高程、海面 y=0）
    /// + 单实例 Ocean Water Surface（scriptInteractions，decalRegionAnchor 锚主角船）+ 太阳方向光
    /// + M6 Global Volume（M1 CreateVolumeProfileAsset 同款，含自动曝光 override——M2-E2 教训）
    /// + WeatherController/WeatherGUI（0-9 海况/T 昼夜/F 雾距全保留）+ SimulationPanel
    /// （锚地密度 + M4 水面工艺滑条保留；岛数控件 islandControlsVisible=false 隐藏——真实地形无 Perlin 岛）
    /// + FpsProbe（overlays fps 行，干净协议读它）+ 主角船 FcbHoubei（PlaceCatalogShip 全套接线：
    ///   浮力/号灯/水线湿感/艏波尾迹 WaterDecal/G 键 WaypointFollower 沿主航道）+ AnchorageFleet
    /// 海峡锚地船群（SetSlots 注入开阔水域字面量）+ DetectionOverlay（B）+ FramePublisher（默认关）。
    /// 水深验证（防搁浅，fail-fast 不许静默换点）：构建期 Terrain.SampleHeight 采样——
    /// ①锚地所有船位高程 &lt; 0；②G 航路逐航点间插值采样高程 &lt; 0。纯函数见 M6TerrainMath（EditMode 全覆盖）。
    /// 保存 Assets/Scenes/M6-Strait.unity；M1-Weather.unity（Perlin 岛开发代理场景）不动。
    /// </summary>
    public static class M6StraitSceneBootstrapper
    {
        const string k_SceneDir = "Assets/Scenes";
        const string k_ScenePath = k_SceneDir + "/M6-Strait.unity";
        const string k_ProfileAsset = "Assets/Settings/M6-GlobalVolumeProfile.asset";

        // ── 海峡字面量（Unity xz 米，原点 = 区域中心 (103.80E, 1.28N)；+X=东 +Z=北）──────────
        // 水深 provenance 2026-09-29：对 tmp/m6-data 近景带 RAW 逐 50 m 采样离线选点，
        // 构建期 depth gate（Terrain.SampleHeight 实采）复验。初版航路首跑被 gate 拦下
        // （(3407,-6370) 高程 −4.8 m：Bukom/Sudong 岛群浅滩；首版离线验证误用"段内最深处"
        // 统计——gate 纠正为"段内最浅处 < −5 m"口径后重选）。现版：泊位 200 m 盒最浅 −13.3 m；
        // 航路三段最浅 −15.0/−46.9/−46.9 m（绕岛群南侧深水航道）。
        // M7-A（2026-09-29）：锚地迁真实锚区（见 k_StraitSlots 注）；新增布景四要素 stage
        // （M7BackdropBuilder：Tuas/PP 岸桥天际线+箱堆、A3 平整、A4 远景植被），落位另有陆上门禁。

        /// <summary>海峡锚地槽位（M7-A 迁真实锚区；表体/选点 provenance 见
        /// M7BackdropMath.StraitAnchorageSlots——此仅转发引用，保 k_StraitSlots 消费点不动）。</summary>
        static readonly AnchorageSlot[] k_StraitSlots = M7BackdropMath.StraitAnchorageSlots;

        // M7-B（2026-09-29）：f3 stage 接棒——IALA A 区浮标 13 座（主航道带 10 + 锚地口 3，
        // 夜灯 BuoyBeacon）、渡轮/拖轮动目标（WaypointFollower autoStart，航线往返/闭环）、
        // 渔排 5 组（浅水 2-8 m 窗，FishFarmSway 系留微摇摆）、大气三档（浓霾晴/积雨云/
        // 雷暴雨幡；WeatherGUI N 键循环 + 下拉，雨 VFX 挂 Main Camera）。落位与航路逐点
        // 水深门禁在 M7BSceneBuilder.Build 内 fail-fast（选点 provenance 见 M7BMath 类头注）。

        /// <summary>主角泊位（中部深水航道西缘，艏向沿航线首段 ~134°）。</summary>
        static readonly Vector2 k_HeroBerth = new Vector2(-1500f, -5000f);
        const float k_HeroHeadingDeg = 134f;

        /// <summary>G 键主航道路径点（M1 demo 语义：起点 = 泊位不在表内；绕 Bukom/Sudong
        /// 岛群南侧深水航道东行，BFS 深水连通搜索的解，见上 provenance）。</summary>
        static readonly Vector2[] k_StraitRoute =
        {
            new Vector2(5200f, -11400f),
            new Vector2(7200f, -11200f),
            new Vector2(9500f, -8800f),
        };

        // 水深 fail-fast 裕量：除"高程<0"硬门外再压 5 m（防搁浅工程口径：keel/锚链富余）。
        const float k_DepthMarginM = 5f;
        const float k_RouteSampleStepM = 100f;

        /// <summary>海峡默认雾距（review S2 2026-09-29）：开阔海峡档 8000 m——F 键 A/B 实证
        /// 亮度随雾距单调变化、3000 档自动曝光把海面压成深灰墨绿；M1 默认 3000 不动
        /// （WeatherController 字段初始化器），此处场景构建时注入覆盖。</summary>
        const float k_DefaultFogDistanceM = 8000f;

        [MenuItem("Sango/M6/Build Strait Scene")]
        public static void Build()
        {
            M0SceneBootstrapper.ConfigureHdrpAssets();
            VesselAssetPipeline.EnsureBuilt(); // 干净克隆自举（齐全则零开销跳过）
            M5FleetPipeline.EnsureBuilt();
            M6TerrainPipeline.BuildAll();      // 幂等：TerrainData/TerrainLayer/底图资产就绪
            var profile = M1SceneBootstrapper.CreateVolumeProfileAsset(k_ProfileAsset); // 独立 profile（M1 重建先删后建换 GUID，不得共享）
            BuildScene(profile);
        }

        static void BuildScene(VolumeProfile profile)
        {
            var manifest = M6TerrainPipeline.LoadManifest();
            var center = new Vector2(manifest.center_utm[0], manifest.center_utm[1]);

            // 幂等核心：NewScene 重建（M1/M2E 同款）
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // a. 29 块真实地形：近景 4 全激活；与近景带有实际交叠的远景 tile SetActive(false)
            //    ——2026-09-29 编排者裁决"覆盖语义"：真实网格半 tile 偏移（交叠 9 / 全覆盖 1，
            //    任务文本"4 个"字面数不成立），共面双层地形 z-fight 是硬伤；洞在 12–24 km
            //    远景环、默认雾距外被遮蔽。M8 流送接棒（勿为凑数激活任何交叠 tile）。
            var material = AssetDatabase.LoadAssetAtPath<Material>(M6TerrainPipeline.MaterialPath);
            var terrains = new List<Terrain>();
            int hidden = 0;
            foreach (var band in new[] { manifest.near, manifest.far })
            {
                bool nearBand = band == manifest.near;
                foreach (var tile in band.tiles)
                {
                    var layout = M6TerrainMath.LayoutFor(tile, band, center);
                    var data = AssetDatabase.LoadAssetAtPath<TerrainData>(M6TerrainPipeline.TerrainDataPath(tile.name));
                    if (data == null)
                        throw new System.InvalidOperationException($"[Sango.M6] TerrainData missing: {tile.name} — run Sango/M6/Build Terrain Assets first");
                    var go = Terrain.CreateTerrainGameObject(data);
                    go.name = tile.name;
                    var terrain = go.GetComponent<Terrain>();
                    terrain.materialTemplate = material;
                    // 世界 y = 真实高程：terrain y=elevMin + [0..span] 归一化高度（海面 y=0 天然成立）
                    go.transform.position = new Vector3(layout.originXZ.x, (float)layout.elevMin, layout.originXZ.y);
                    bool underNear = !nearBand && M6TerrainMath.FarTileUnderNearBand(tile, manifest.near.extent_utm);
                    if (underNear)
                    {
                        go.SetActive(false);
                        hidden++;
                    }
                    terrains.Add(terrain);
                }
            }
            Debug.Log($"[Sango.M6] terrain: {terrains.Count} tiles placed ({manifest.near.tiles.Length} near active, " +
                      $"{hidden} far hidden under near band, {manifest.far.tiles.Length - hidden} far active — coverage-semantics ruling 2026-09-29, M8 streaming supersedes)");

            // b. 单实例 Ocean Water Surface（y=0；infinite extent；scriptInteractions 供浮力查询）
            var waterGo = new GameObject("Water Surface", typeof(WaterSurface));
            var water = waterGo.GetComponent<WaterSurface>();
            water.surfaceType = WaterSurfaceType.OceanSeaLake;
            water.scriptInteractions = true;

            // c. Global Volume + 太阳方向光（WeatherController 运行时驱动，M1 同款）
            var volumeGo = new GameObject("Global Volume", typeof(Volume));
            var volume = volumeGo.GetComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 10f;
            volume.sharedProfile = profile;

            var lightGo = new GameObject("Directional Light", typeof(Light));
            var light = lightGo.GetComponent<Light>();
            light.type = LightType.Directional;
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            lightGo.AddComponent<HDAdditionalLightData>();
            light.intensity = 100000f;

            // d. 天气（0-9 海况 / T 昼夜 / F 雾距热键全保留：digitHotkeysEnabled 默认 true）
            var weatherGo = new GameObject("Weather", typeof(WeatherController));
            var weather = weatherGo.GetComponent<WeatherController>();
            weather.waterSurface = water;
            weather.globalVolume = volume;
            weather.sunLight = light;
            weather.applyEveryFrame = true;
            weather.fogDistanceMeters = k_DefaultFogDistanceM; // review S2：海峡默认 8000 m（M1 默认 3000 不变）
            var guiGo = new GameObject("Weather GUI", typeof(WeatherGUI));
            guiGo.GetComponent<WeatherGUI>().controller = weather;

            // e. 主角船 = FcbHoubei（M5 编目，PlaceCatalogShip 全套接线照 M1 现版）
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(VesselAssetPipeline.CatalogAssetPath);
            if (catalog == null)
                throw new System.InvalidOperationException($"[Sango.M6] vessel catalog missing at {VesselAssetPipeline.CatalogAssetPath}");
            var shipsRoot = new GameObject("Ships");
            var hero = M1SceneBootstrapper.PlaceCatalogShip(catalog, VesselClass.FcbHoubei, k_HeroBerth, k_HeroHeadingDeg, shipsRoot.transform, water);
            if (hero == null)
                throw new System.InvalidOperationException("[Sango.M6] hero ship placement failed");

            // G 键航路：WaypointFollower 沿主航道（M1 demo 语义；字面量见上，水深构建期验证）
            var heroFollower = hero.AddComponent<WaypointFollower>();
            heroFollower.demoHotkeysEnabled = true;
            heroFollower.cruiseSpeedMps = 8f;
            heroFollower.maxYawRateDegPerSec = 25f;
            heroFollower.arrivalRadiusM = 12f;
            heroFollower.bowYawDegOffset = VesselAssetPipeline.BowYawDeg(VesselClass.FcbHoubei);
            heroFollower.waypoints = k_StraitRoute;

            // 艏波/尾迹 WaterDecal（WaterDecalSizing 按 LOA 定尺寸；decalRegionAnchor 锚主角船）
            var heroDecals = M1SceneBootstrapper.AttachWaterDecals(hero, water, catalog.GetEntry(VesselClass.FcbHoubei)?.loaMeters ?? 42f, heroFollower);
            M1SceneBootstrapper.AttachNavigationLights(hero, VesselClass.FcbHoubei, weather);
            M1SceneBootstrapper.AttachHullWaterlineDecals(hero, 1.2f);

            // f. 锚地船群（海峡槽位注入；开阔水域，纯布景随浪摇）
            var anchorageGo = new GameObject("Anchorage Fleet", typeof(AnchorageFleet));
            var anchorage = anchorageGo.GetComponent<AnchorageFleet>();
            anchorage.catalog = catalog;
            anchorage.waterSurface = water;
            anchorage.SetSlots(k_StraitSlots);
            anchorage.SetDensity(k_StraitSlots.Length);

            // f2. M7-A 布景四要素（A3 平整 → 陆上落位门禁 fail-fast → 岸桥/箱堆 → A4 远景植被；
            //     幂等：平整在 M6TerrainPipeline.BuildAll 重建 RAW 高度后重放，资产 load-or-create）
            M7BackdropBuilder.BuildBackdrop(manifest, terrains, BuildSampler(terrains));

            // f3. M7-B 海峡浮标/动目标/渔排（B1 IALA 浮标 + B2 渡轮/拖轮 + B4 渔排；
            //     内置构建期水深门禁 fail-fast——浮标逐点 <0、航路 100 m 逐点 <0、渔排 [-8,-2] 窗）
            M7BSceneBuilder.Build(manifest, water, weather, catalog, BuildSampler(terrains));

            // g. 水深验证（构建期 fail-fast，确定性，防搁浅；不满足即构建失败报错，不静默换点）
            ValidateDepths(terrains);

            // h. 相机：桥楼视角（远平面 ≥30000 m 盖住远景带，near 0.5）+ 全套 rig
            var cameraGo = new GameObject("Main Camera", typeof(Camera));
            cameraGo.tag = "MainCamera";
            var bow = new Vector3(Mathf.Sin(k_HeroHeadingDeg * Mathf.Deg2Rad), 0f, Mathf.Cos(k_HeroHeadingDeg * Mathf.Deg2Rad));
            // 下方两行 = 编辑器 Scene 视图位姿；运行时由 CameraRig.Bridge 接管（Awake→SnapNow）
            cameraGo.transform.position = new Vector3(k_HeroBerth.x - 150f, 20f, k_HeroBerth.y - 80f);
            cameraGo.transform.rotation = Quaternion.LookRotation(
                new Vector3(k_HeroBerth.x, 2f, k_HeroBerth.y) + bow * 200f - cameraGo.transform.position, Vector3.up);
            var camera = cameraGo.GetComponent<Camera>();
            camera.fieldOfView = 60f;
            camera.nearClipPlane = 0.5f;
            camera.farClipPlane = 32000f; // 远景带 ±30 km（雾距滑条上限 8 km < far）
            cameraGo.AddComponent<HDAdditionalCameraData>();

            var cameraRig = cameraGo.AddComponent<CameraRig>();
            cameraRig.followShip = hero.transform;
            cameraRig.controlledCamera = camera;
            cameraRig.bridgeShipRelative = true; // review S1：桥楼随船解算（固定 M1 机位在海峡拍空海——首帧无船）

            var sway = cameraGo.AddComponent<BridgeSway>();
            sway.weather = weather;
            sway.rig = cameraRig;

            // M7-B 雨 VFX（雷暴雨幡档）：相机挂载（发射器跟相机、粒子世界系），WeatherController 驱动
            weather.rain = cameraGo.AddComponent<RainFall>();

            var radarGo = new GameObject("Radar Overlay", typeof(RadarOverlay));
            var radar = radarGo.GetComponent<RadarOverlay>();
            radar.ownShip = hero.transform;
            radar.otherShips = anchorage.ShipTransforms().ToArray();

            var arrows = hero.AddComponent<VectorArrows>();
            arrows.follower = heroFollower;
            arrows.cameraRig = cameraRig;

            var autoGo = new GameObject("Autonomous Control", typeof(AutonomousControlPanel));
            autoGo.GetComponent<AutonomousControlPanel>().follower = heroFollower;

            // i. Simulation 面板：锚地密度 + M4 水面工艺保留；岛数控件隐藏（真实地形场景）
            var simGo = new GameObject("Simulation GUI", typeof(SimulationPanel));
            var sim = simGo.GetComponent<SimulationPanel>();
            sim.radar = radar;
            sim.catalog = catalog;
            sim.waterDecals = heroDecals;
            sim.anchorage = anchorage;
            sim.islandControlsVisible = false; // 岛数/缩放/Apply 岛群重建不适用于真实地形

            // j. M3 链路（probe 30/30 验收门）：检测框叠加（B）+ ZMQ 帧发布器（默认 OFF）
            var overlayGo = new GameObject("Detection Overlay", typeof(DetectionOverlay));
            var overlayShips = new List<Transform> { hero.transform };
            overlayShips.AddRange(anchorage.ShipTransforms());
            overlayGo.GetComponent<DetectionOverlay>().ships = overlayShips.ToArray();
            var pubGo = new GameObject("Frame Publisher", typeof(FramePublisher));
            Debug.Log($"[Sango.M3] wired: detection overlay (B, {overlayShips.Count} ships), frame publisher (default OFF, {pubGo.GetComponent<FramePublisher>().endpoint})");

            // k. FpsProbe（overlays fps 行 + Logs/fps-report.jsonl，干净协议读它）
            var fpsProbeGo = new GameObject("M6 Fps Probe", typeof(FpsProbe));
            fpsProbeGo.GetComponent<FpsProbe>().anchor = FpsProbe.OverlayAnchor.BottomLeft; // review S3：置底避让 WeatherGUI 左上面板

            // l. 保存
            if (!AssetDatabase.IsValidFolder(k_SceneDir))
                AssetDatabase.CreateFolder("Assets", "Scenes");
            EditorSceneManager.SaveScene(scene, k_ScenePath);
            AssetDatabase.SaveAssets();
            Debug.Log($"[Sango.M6] scene written: {Path.GetFullPath(k_ScenePath)}");
        }

        /// <summary>
        /// 构建期水深验证（fail-fast）：Terrain.SampleHeight 实采。①泊位+锚地全船位；
        /// ②G 航路逐航点间 100 m 插值。一律要求高程 &lt; −5 m（0 硬门 + 5 m 防搁浅裕量）。
        /// 违规抛异常终止构建（不静默换点）；采样点/最差值进异常消息可复现。
        /// </summary>
        static void ValidateDepths(List<Terrain> terrains)
        {
            var sampler = BuildSampler(terrains);

            var points = new List<Vector2> { k_HeroBerth };
            foreach (var slot in k_StraitSlots) points.Add(slot.xz);
            var slotsReport = M6TerrainMath.ValidateDepths(sampler, points.ToArray(), k_DepthMarginM);
            if (!slotsReport.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M6] DEPTH GATE FAIL: berth/anchorage at ({slotsReport.worstPoint.x:F0},{slotsReport.worstPoint.y:F0}) " +
                    $"elevation {slotsReport.worstElevationM:F1} m >= -{k_DepthMarginM} m — move the literal, do not silently relocate");

            var routeReport = M6TerrainMath.ValidateRoute(sampler, k_StraitRoute, k_RouteSampleStepM, k_DepthMarginM);
            if (!routeReport.ok)
                throw new System.InvalidOperationException(
                    $"[Sango.M6] DEPTH GATE FAIL: route sample at ({routeReport.worstPoint.x:F0},{routeReport.worstPoint.y:F0}) " +
                    $"elevation {routeReport.worstElevationM:F1} m >= -{k_DepthMarginM} m ({routeReport.samples} samples) — reroute the literal, do not silently relocate");

            Debug.Log($"[Sango.M6] depth gate PASS: {points.Count} berths/slots shallowest {slotsReport.shallowestElevationM:F1} m (deepest {slotsReport.worstElevationM:F1}); " +
                      $"route {routeReport.samples} samples shallowest {routeReport.shallowestElevationM:F1} m (deepest {routeReport.worstElevationM:F1}) — gate: all < -{k_DepthMarginM} m");
        }

        /// <summary>世界 (x,z) → 高程米采样器：找包含点的 tile，Terrain.SampleHeight + terrain y 偏移。
        /// 实证（EditMode TerrainDataFreshBuild 首跑红）：Terrain.SampleHeight 返回高度图数据高
        /// （0..size.y），**不含 terrain.transform.position.y**——世界高程必须自行加 elevMin 锚定。</summary>
        static M6TerrainMath.ElevationSampler BuildSampler(List<Terrain> terrains)
        {
            return xz =>
            {
                var world = new Vector3(xz.x, 0f, xz.y);
                foreach (var t in terrains)
                {
                    var p = t.transform.position;
                    var s = t.terrainData.size;
                    if (world.x >= p.x && world.x <= p.x + s.x && world.z >= p.z && world.z <= p.z + s.z)
                        return t.SampleHeight(world) + p.y;
                }
                throw new System.ArgumentOutOfRangeException($"({xz.x:F0},{xz.y:F0}) outside all terrain tiles");
            };
        }

        // ── Standalone 播放器（海峡场景接棒主 demo；M1-Weather 场景与 M2E app 保留不动）────
        [MenuItem("Sango/M6/Build Strait Player (Mono)")]
        public static void BuildStraitPlayer()
        {
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            PlayerSettings.runInBackground = true; // 失焦不停渲染（自动化采集；WeatherGUI.Awake 同款保险）
            var report = BuildPipeline.BuildPlayer(
                new[] { k_ScenePath },
                "Builds/sango.app",
                BuildTarget.StandaloneOSX,
                BuildOptions.None);
            Debug.Log($"[Sango.M6] player build: {report.summary.result} " +
                      $"size={report.summary.totalSize / (1024 * 1024)}MB out={report.summary.outputPath}");
        }
    }
}
