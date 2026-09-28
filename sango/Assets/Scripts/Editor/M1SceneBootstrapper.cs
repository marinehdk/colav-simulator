using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Editor
{
    /// <summary>
    /// M1 海况环境与天气场景生成器（幂等：NewScene 重建 + 旧 profile 资产先删后建，学 M0SceneBootstrapper）。
    /// 场景：Water Surface(Ocean, Script Interactions) + Global Volume(PBS 天空/体积云/Fog/Water Rendering)
    /// + 太阳方向光 + 2 艘编目船模(M2-A) + Perlin 岛屿(5 岛 seed 42) + WeatherController + WeatherGUI + 桥楼视角相机。
    /// 保存 Assets/Scenes/M1-Weather.unity 与 Assets/Settings/M1-GlobalVolumeProfile.asset。
    /// </summary>
    public static class M1SceneBootstrapper
    {
        const string k_SceneDir = "Assets/Scenes";
        const string k_ScenePath = k_SceneDir + "/M1-Weather.unity";
        const string k_ProfileDir = "Assets/Settings";
        const string k_ProfileAsset = k_ProfileDir + "/M1-GlobalVolumeProfile.asset";

        // 岛群与相机布局：相机在 (0,12,-40)（桥楼高度），岛群中心 (0,0,180)，向北望岛
        const float k_CameraHeight = 12f;
        static readonly Vector3 k_IslandCenter = new Vector3(0f, 0f, 180f);
        const float k_IslandClusterRadius = 260f;

        [MenuItem("Sango/M1/Build Weather Scene")]
        public static void Build()
        {
            M0SceneBootstrapper.ConfigureHdrpAssets(); // plan A applied: M0 版已改 public，避免两处同步维护
            VesselAssetPipeline.EnsureBuilt(); // M2-A：干净克隆时自动补建船模 prefab/编目（齐全则零开销跳过）
            var profile = CreateVolumeProfileAsset();
            BuildScene(profile);
        }

        // M2-A：从编目实例化一艘船到指定平面位置/航向，y 用编目水线偏移（约 15% 船体高没入水下）。
        // M2-B：挂 VesselBuoyancy 并注入 Water Surface（heave/roll/pitch 由求解器驱动，x/z/yaw 仍归放置脚本）。
        // M2-C：x/z/yaw 的所有权移交 WaypointFollower（合成契约的另一半）。
        // M2-E1（spec #84 授权的放置层修复）：组合烘焙艏向——root.rotation = Euler(0,heading,0)·Euler(0,bowYaw,0)。
        // 此前的绝对赋值把 prefab 根上"原生艏→+Z"的烘焙覆盖掉，Medium（bowYaw 180°）以"艉朝 heading"
        // 渲染（视觉艏 = heading+180°，M2-D 验收遗留）。组合后渲染艏 = heading，对全部编目档位成立。
        // public static：M2ESceneBootstrapper 复用同一放置路径（单一修复点）。
        public static GameObject PlaceCatalogShip(VesselCatalog catalog, VesselClass vesselClass, Vector2 xz, float headingDeg, Transform parent, WaterSurface waterSurface)
        {
            var entry = catalog.GetEntry(vesselClass);
            if (entry?.prefab == null)
            {
                Debug.LogError($"[Sango.M1] no prefab in catalog for {vesselClass}, ship skipped");
                return null;
            }
            var ship = (GameObject)PrefabUtility.InstantiatePrefab(entry.prefab);
            ship.transform.SetParent(parent, true);
            ship.transform.position = new Vector3(xz.x, entry.waterlineOffsetY, xz.y);
            float bowYawDeg = VesselAssetPipeline.BowYawDeg(vesselClass);
            ship.transform.rotation = Quaternion.Euler(0f, headingDeg, 0f) * Quaternion.Euler(0f, bowYawDeg, 0f);
            // 放置自证（batchmode 日志取证）：渲染艏（世界）= rotation·原生艏向量，必须等于 heading 方向。
            // 原生艏向量 = (0,0,cos bowYaw)（编目 yaw 仅 0/180：0→+Z、180→−Z，见 VesselAssetPipeline.k_Specs）。
            var nativeBow = new Vector3(0f, 0f, Mathf.Cos(bowYawDeg * Mathf.Deg2Rad));
            var renderedBow = ship.transform.rotation * nativeBow;
            float rad = headingDeg * Mathf.Deg2Rad;
            Debug.Log($"[Sango.M1] placed {vesselClass} @ ({xz.x:F0},{xz.y:F0}) heading {headingDeg:0}° + bowYaw {bowYawDeg:0}° " +
                      $"-> root eulerY {Mathf.Repeat(headingDeg + bowYawDeg, 360f):0}°, rendered bow ({renderedBow.x:F2},0,{renderedBow.z:F2}) " +
                      $"expect heading dir ({Mathf.Sin(rad):F2},0,{Mathf.Cos(rad):F2})");
            var buoyancy = ship.AddComponent<VesselBuoyancy>();
            buoyancy.waterSurface = waterSurface;
            return ship;
        }

        static Material TintedLit(Color c) => new Material(Shader.Find("HDRP/Lit")) { color = c };

        // M2-D 航行灯接线：bowYawDeg 由 VesselAssetPipeline.BowYawDeg 查 k_Specs（原生轴映射，见 BuildScene 注释）。
        static void AttachNavigationLights(GameObject ship, VesselClass vesselClass, WeatherController weather)
        {
            if (ship == null) return;
            var nav = ship.AddComponent<NavigationLights>();
            nav.weather = weather;
            nav.bowYawDeg = VesselAssetPipeline.BowYawDeg(vesselClass);
        }

        // M4 spike：艏波+尾迹 WaterDecal 接线。材质来自 HDRP 17.3 WaterSamples 的
        // CurrentWithSplines/"Sample Water Decal" 拷贝改造（Assets/Art/WaterDecals/，
        // GUID 随 meta 保留）——真 WaterDecalSubTarget 图，CustomFunctionNode 直调
        // WaterDecalUtilities.hlsl 的 EvaluateBowWaveAmplitude（抛物线 V 形 SDF）。
        // 几何约定（WaterDecal.shader GetDecalVaryings + EvaluateBowWaveAmplitude 推导）：
        // 图 UV.y=0 边是 V 尖顶（apex）侧 = decal 局部 −Z；故 decal 子物体 yaw 180°
        // （decal −Z = 船 +Z 艏），apex 距区域中心 0.4·regionSize.y（uv.y=0.1 顶点 + 半径过渡）。
        // scaleMode=ScaleInvariant：regionSize 直接是米，不被 prefab 根烘焙缩放放大；
        // 子物体局部 z 需按 lossyScale 折算（局部单位 × s = 世界米）。
        const string k_BowWaveMatPath = "Assets/Art/WaterDecals/M4_BowWave.mat";
        const string k_WakeFoamMatPath = "Assets/Art/WaterDecals/M4_WakeFoam.mat";

        static BoatWaterDecals AttachWaterDecals(GameObject ship, WaterSurface water, float loaMeters, WaypointFollower follower)
        {
            if (ship == null || follower == null) return null;
            var bowMat = AssetDatabase.LoadAssetAtPath<Material>(k_BowWaveMatPath);
            var wakeMat = AssetDatabase.LoadAssetAtPath<Material>(k_WakeFoamMatPath);
            if (bowMat == null || wakeMat == null)
            {
                Debug.LogError($"[Sango.M4] water decal materials missing ({k_BowWaveMatPath} / {k_WakeFoamMatPath}); decals skipped");
                return null;
            }

            float s = Mathf.Max(ship.transform.lossyScale.x, 1e-3f); // 均匀烘焙缩放：局部单位 × s = 米
            float halfLoa = loaMeters * 0.5f;

            // 艏波：V 尖顶落在艏柱（+loa/2），双臂向艉展开覆盖船身（12 m 小船量级）。
            var bowGo = new GameObject("Bow Wave Decal");
            bowGo.transform.SetParent(ship.transform, false);
            bowGo.transform.localPosition = new Vector3(0f, 0f, (halfLoa - 0.4f * 12f) / s);
            bowGo.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            var bow = bowGo.AddComponent<WaterDecal>();
            bow.material = bowMat;
            bow.scaleMode = DecalScaleMode.ScaleInvariant;
            bow.regionSize = new Vector2(12f, 12f);
            bow.amplitude = 0.4f;          // 全强航速 0.4 m 抬升（适配器按航速缩放）
            bow.surfaceFoamDimmer = 0f;
            bow.deepFoamDimmer = 0f;

            // 尾迹泡沫：V 尖顶落船中，双臂向艉外扩 + 泡沫缓冲持久化拖出尾迹；变形走材质关闭（_AffectDeformation: 0）。
            var wakeGo = new GameObject("Wake Foam Decal");
            wakeGo.transform.SetParent(ship.transform, false);
            wakeGo.transform.localPosition = new Vector3(0f, 0f, (0f - 0.4f * 28f) / s);
            wakeGo.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            var wake = wakeGo.AddComponent<WaterDecal>();
            wake.material = wakeMat;
            wake.scaleMode = DecalScaleMode.ScaleInvariant;
            wake.regionSize = new Vector2(14f, 28f);
            wake.amplitude = 0f;
            wake.surfaceFoamDimmer = 0f;   // 适配器按航速爬坡驱动
            wake.deepFoamDimmer = 0.6f;

            // 速度门限适配器：G 键 demo 同一航速真值（WaypointFollower.SpeedMps）。LOA 进适配器
            // （艏波 Froude 曲线尺度分母），编目缺档兜底 12 = Small。
            var gate = ship.AddComponent<BoatWaterDecals>();
            gate.bowDecal = bow;
            gate.wakeDecal = wake;
            gate.follower = follower;
            gate.speedThresholdMps = 0.5f;
            gate.fullEffectSpeedMps = 5f;
            gate.bowAmplitudeM = 0.4f;
            gate.loaMeters = loaMeters;

            // 水面开关：deformation/foam 任一 false 时对应 pass 直接不可见（WaterSystem.Decals CullWaterDecals）。
            // decal 区域锚到演示船：region 跟船走，64 m 方区在 512 res 下 ≈ 8 px/m（默认 200 m 只有 2.56）。
            water.deformation = true;
            water.foam = true;
            water.decalRegionAnchor = ship.transform;
            water.decalRegionSize = new Vector2(64f, 64f);
            // M4-A 分辨率降档（issue #87）：deformation/foam 由默认 512 降 256——spike 实测 512 档
            // fps 25–28 < 30 闸门，且每升一档显存/reproject 代价 ×4（spike notes §5），256 档把两块
            // 模拟 RT 与泡沫 CS 降为 1/4 面积换回性能头寸；64 m 区域 256 档 ≈ 4 px/m 仍够 12 m 船 V 形。
            // 回滚开关 = 下面两行枚举改回 Resolution512（视觉是否变粗由编排者实机裁决）。
            water.deformationRes = WaterSurface.WaterDecalRegionResolution.Resolution256;
            water.foamResolution = WaterSurface.WaterDecalRegionResolution.Resolution256;

            Debug.Log("[Sango.M4] water decals wired: bow V deformation (12x12 m, amp 0.4 m) + wake foam (14x28 m), " +
                      "speed gate 0.5 m/s, full effect 5 m/s, decal region 64x64 m anchored to demo boat, sim res 256");
            return gate;
        }

        static VolumeProfile CreateVolumeProfileAsset() => CreateVolumeProfileAsset(k_ProfileAsset);

        // M2-E1：路径参数化。遭遇场景必须用独立 profile 资产——本构建器对 M1 profile 是
        // "先删后建"（GUID 会变），共享路径会让遭遇场景的引用在 M1 重建后静默失效。
        public static VolumeProfile CreateVolumeProfileAsset(string profileAsset)
        {
            // 幂等：旧 profile 资产先删再建（M1 用独立资产，不与 M0 共用：M0 重跑会整建删重建其资产）
            if (AssetDatabase.LoadAssetAtPath<VolumeProfile>(profileAsset) != null)
            {
                AssetDatabase.DeleteAsset(profileAsset);
            }
            if (!AssetDatabase.IsValidFolder(k_ProfileDir))
            {
                AssetDatabase.CreateFolder("Assets", "Settings");
            }

            var profile = ScriptableObject.CreateInstance(typeof(VolumeProfile)) as VolumeProfile;
            AssetDatabase.CreateAsset(profile, profileAsset);

            // VisualEnvironment + Physical Sky：同 M0（SkyManager 按 skyType 取天空，PBS 太阳由场景方向光驱动）。
            // https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.PhysicallyBasedSky.html
            var environment = profile.Add<VisualEnvironment>();
            environment.skyType.value = (int)SkyType.PhysicallyBased;
            AssetDatabase.AddObjectToAsset(environment, profile);

            var sky = profile.Add<PhysicallyBasedSky>();
            sky.active = true;
            AssetDatabase.AddObjectToAsset(sky, profile);

            // Volumetric Clouds：Simple + Performance 低配档（同 M0；嵌套枚举 VolumetricClouds.cs:38,51）。
            // 运行时云量→预设四档量化由 WeatherController.ApplyCloudsAndFog 处理（17.3 无标量 coverage 字段）。
            var clouds = profile.Add<VolumetricClouds>();
            clouds.active = true;
            clouds.enable.value = true;
            clouds.cloudControl.value = VolumetricClouds.CloudControl.Simple;
            clouds.cloudSimpleMode.value = VolumetricClouds.CloudSimpleMode.Performance;
            AssetDatabase.AddObjectToAsset(clouds, profile);

            // Fog override（M1 新增）：WeatherController 运行时改 maxFogDistance/meanFreePath
            // （Fog.cs:29,50；旧 VolumetricFog 组件已 Obsolete 勿用）。此处只挂组件开总开关。
            var fog = profile.Add<Fog>();
            fog.active = true;
            fog.enabled.value = true;
            fog.enableVolumetricFog.value = true;
            AssetDatabase.AddObjectToAsset(fog, profile);

            // Exposure override（E2 高视角欠曝根因修复 2026-09-28）：此前全项目无 Exposure
            // override，HDRP 落到类默认 **Fixed 0 EV**——平掠水面（天空反射辐射）恰在色调曲线
            // 亮段、陡视角水体（透射辐射，低 2-3 个数量级）掉进暗段 = Chase/TopDown 随俯角变暗
            // （cam census `expMode=Fixed expFixed=0` 逐字证据）。Automatic 直方图逐帧归一到
            // 中灰：四视图各自正确曝光、亮度不再随俯角/高度漂移。limitMin=0 = 夜航亮度地板
            // 保持与旧 Fixed-0 夜景逐位同观感（M2-D 夜景验收不回退）；adaptationMode=Fixed =
            // 逐帧即时无惯量（Exposure.cs "The exposure changes instantly"），切视图瞬间到位。
            // **必须用 .Override()**：VolumeParameter.value setter 只写 m_Value 不置 overrideState
            // （core VolumeParameter.cs:182）——本项目全部历史 .value 卷参数写入（雾/云/skyType）
            // 因此从未激活（census fogEn=False 同源），此处不再重蹈。
            var exposure = profile.Add<Exposure>();
            exposure.active = true;
            exposure.mode.Override(ExposureMode.Automatic);
            exposure.adaptationMode.Override(AdaptationMode.Fixed);
            exposure.limitMin.Override(0f);
            exposure.limitMax.Override(14f);
            AssetDatabase.AddObjectToAsset(exposure, profile);

            // Water Rendering override enable：水体渲染第二道闸（同 M0）。
            var waterRendering = profile.Add<WaterRendering>();
            waterRendering.active = true;
            waterRendering.enable.value = true;
            AssetDatabase.AddObjectToAsset(waterRendering, profile);

            AssetDatabase.SaveAssets();
            return profile;
        }

        static void BuildScene(VolumeProfile profile)
        {
            // 幂等核心：NewScene 重建（未保存的当前场景改动会被丢弃，跑菜单前先保存工作场景）。
            // https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SceneManagement.EditorSceneManager.NewScene.html
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // a. Water Surface：Ocean + Infinite + Script Interactions（同 M0）。
            //    https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.WaterSurface.html
            var waterGo = new GameObject("Water Surface", typeof(WaterSurface));
            var water = waterGo.GetComponent<WaterSurface>();
            water.surfaceType = WaterSurfaceType.OceanSeaLake;
            water.scriptInteractions = true; // M2 浮力查询前置；M1 仅继承 M0 配置

            // b. Global Volume
            var volumeGo = new GameObject("Global Volume", typeof(Volume));
            var volume = volumeGo.GetComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 10f;
            volume.sharedProfile = profile;

            // c. Directional Light：PBS 太阳（同 M0 注释：HDRP 17.3 无 SetSun() 公开 API，方向光旋转/强度由 WeatherController 驱动）
            var lightGo = new GameObject("Directional Light", typeof(Light));
            var light = lightGo.GetComponent<Light>();
            light.type = LightType.Directional;
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            lightGo.AddComponent<HDAdditionalLightData>();
            light.intensity = 100000f; // 正午量级 lux；Apply() 会按时刻滑条覆盖

            // d. 2 艘编目船模（M2-A 替换占位方块船；M1 不做浮力查询，纯看海况尺度）：
            //    小渔船近桥（原 Ship-0 位 (14,-6)，艏向 20°），邮轮中距 ((30,90)，艏向 -35°)。
            //    泊位复算：seed-42 岛5 中心 (-30.9,51.6) 可视岸线 ~0.8R=61m，旧位 (-30,30) 距岛心仅 22m 搁浅，
            //    新位 (30,90) 距岛5/岛3 可视岸线均 ≥17m（艏艉端投影 ≥15m，PerlinIslandGenerator 确定性复算）。
            //    ship-cargo-a 编目在册但本场景不摆（留给 M2-E 遭遇场景）。
            GameObject small = null, medium = null;
            WaypointFollower smallFollower = null; // M2-E2：相机 rig/矢量箭头/Autonomous 按钮接线用
            BoatWaterDecals smallDecals = null;    // M4-A：Simulation 面板「水面工艺」滑条驱动目标
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(VesselAssetPipeline.CatalogAssetPath);
            if (catalog == null)
            {
                Debug.LogError($"[Sango.M1] vessel catalog missing at {VesselAssetPipeline.CatalogAssetPath}");
            }
            else
            {
                var shipsRoot = new GameObject("Ships");
                small = PlaceCatalogShip(catalog, VesselClass.Small, new Vector2(14f, -6f), 20f, shipsRoot.transform, water);
                medium = PlaceCatalogShip(catalog, VesselClass.Medium, new Vector2(30f, 90f), -35f, shipsRoot.transform, water);

                // M2-C demo 航线（spec #82）：小渔船按 G 起航/停船，走清水走廊后回到泊位附近停船。
                // 航点对 seed-42 全部 5 岛的可视岸线（≈0.8R）逐一核过 ≥12 m 裕量（推演见 evidence m2c-build-log.md）；
                // 全程 ≈120 m，巡航 5 m/s ≈ 30 s 演示（含 3 次转弯与终点减速）。
                if (small != null)
                {
                    smallFollower = small.AddComponent<WaypointFollower>(); // 参数用组件默认档（5 m/s / 20°/s / 8 m / 2 m/s²）
                    smallFollower.demoHotkeysEnabled = true; // 仅演示船响应 G；M2-E 多跟随器实例默认 false，互不串扰
                    smallFollower.waypoints = new[]
                    {
                        new Vector2(40f, 0f),
                        new Vector2(60f, -20f),
                        new Vector2(20f, -30f),
                        new Vector2(5f, -12f),
                    };
                    Debug.Log("[Sango.M1] M2-C waypoint demo wired on Small ship: press G to sail/stop; " +
                              "route (14,-6) -> (40,0) -> (60,-20) -> (20,-30) -> (5,-12), cruise 5 m/s");

                    // M4 spike：艏波变形 + 尾迹泡沫 WaterDecal（编目 LOA 定 V 尖顶锚位，速度门限接跟随器真值）。
                    smallDecals = AttachWaterDecals(small, water, catalog.GetEntry(VesselClass.Small)?.loaMeters ?? 12f, smallFollower);
                }
            }

            // e. Perlin 岛屿：5 岛 seed 42（PLAN §5 M1；程序化 mesh 生成器见 PerlinIslandGenerator）
            //    M2-E2：岛体材质提到局部变量——Simulation 面板 Apply 重建时从基线设置取同一材质。
            var islandMaterial = TintedLit(new Color(0.22f, 0.30f, 0.22f)); // 岛体深绿灰：默认 Lit 白色远景像冰盖/白沫
            var islands = PerlinIslandGenerator.GenerateIslands(new IslandSettings
            {
                count = 5,
                sizeRange = new Vector2(80f, 240f), // 岛直径 m
                maxHeight = 45f,
                resolution = 96,
                seed = 42,
                clusterRadius = k_IslandClusterRadius,
                material = islandMaterial,
                vertexColors = false,
            });
            islands.transform.position = k_IslandCenter;

            // f. WeatherController + WeatherGUI（运行时由 WeatherGUI.Awake 建 UGUI 面板）
            var weatherGo = new GameObject("Weather");
            var weather = weatherGo.AddComponent<WeatherController>();
            weather.waterSurface = water;
            weather.globalVolume = volume;
            weather.sunLight = light;
            weather.applyEveryFrame = true;

            var guiGo = new GameObject("Weather GUI", typeof(WeatherGUI));
            guiGo.GetComponent<WeatherGUI>().controller = weather;

            // M2-D 航行灯（spec #83）：两船各挂 NavigationLights，时刻真值注入 WeatherController。
            // 明灭随既有 T 循环/时刻滑条（纯阈值 NavigationLightsCore.IsLightsOn），无新键位。
            // bowYawDeg 由 VesselAssetPipeline.BowYawDeg 查 k_Specs（Medium 根烘焙 180°）：
            // 根局部空间是原生轴，锚点推导必须按它映射，否则 −Z 原生艏的 Medium 被静默镜像（验收 P2）。
            AttachNavigationLights(small, VesselClass.Small, weather);
            AttachNavigationLights(medium, VesselClass.Medium, weather);
            Debug.Log("[Sango.M1] M2-D navigation lights wired on both ships (on/off follows time-of-day; port RED / starboard GREEN / white masthead + stern)");

            // g. 相机：桥楼高度视角 (0,12,-40) 望岛群
            var cameraGo = new GameObject("Main Camera", typeof(Camera));
            cameraGo.tag = "MainCamera";
            cameraGo.transform.position = new Vector3(0f, k_CameraHeight, -40f);
            cameraGo.transform.rotation = Quaternion.LookRotation(new Vector3(k_IslandCenter.x, 10f, k_IslandCenter.z) - cameraGo.transform.position, Vector3.up);
            var camera = cameraGo.GetComponent<Camera>();
            camera.fieldOfView = 60f;
            camera.nearClipPlane = 0.3f;
            camera.farClipPlane = 8000f; // 雾距滑条上限 8000m，far 需盖住
            cameraGo.AddComponent<HDAdditionalCameraData>();

            // g2. M2-E2 相机切换 + 桥楼矢量 + 雷达 + Simulation 面板 + Autonomous 按钮（spec #85）。
            //     键位账本：C 相机循环 · V 矢量开关 · A demo（G 既有）· Q/E 雷达量程 · Z/X 转速
            //     · -/= 岛数 · ,/. 缩放 · Enter Apply · P 预览档 · B 检测框叠加（M3，0-9/T/F 天气不动）。
            var cameraRig = cameraGo.AddComponent<CameraRig>();
            cameraRig.followShip = small != null ? small.transform : null;
            cameraRig.controlledCamera = camera;

            var radarGo = new GameObject("Radar Overlay", typeof(RadarOverlay));
            var radar = radarGo.GetComponent<RadarOverlay>();
            radar.ownShip = small != null ? small.transform : null;
            radar.otherShips = medium != null ? new[] { medium.transform } : System.Array.Empty<Transform>();

            if (smallFollower != null)
            {
                var arrows = small.AddComponent<VectorArrows>();
                arrows.follower = smallFollower;
                arrows.cameraRig = cameraRig;

                var autoGo = new GameObject("Autonomous Control", typeof(AutonomousControlPanel));
                autoGo.GetComponent<AutonomousControlPanel>().follower = smallFollower;
            }

            var simGo = new GameObject("Simulation GUI", typeof(SimulationPanel));
            var sim = simGo.GetComponent<SimulationPanel>();
            sim.radar = radar;
            sim.catalog = catalog;
            sim.islandCenter = k_IslandCenter;
            sim.waterDecals = smallDecals; // M4-A：水面工艺滑条（材质缺失跳过时为 null，滑条照常显示不生效）
            var islandBaseline = IslandRebuild.M1Baseline();
            islandBaseline.material = islandMaterial;
            sim.islandBaseline = islandBaseline;

            // M3 缝钉子①④（spec #86）：检测框叠加层（B 切换，真值框 + "1.0 (gt)" 标签）
            // + ZMQ 帧发布器（默认 OFF，SangoSeamConfig.PublisherEnabled=false；启用路径见 frame-publisher-v1.md）。
            var overlayGo = new GameObject("Detection Overlay", typeof(DetectionOverlay));
            var overlay = overlayGo.GetComponent<DetectionOverlay>();
            var overlayShips = new List<Transform>();
            if (small != null) overlayShips.Add(small.transform);
            if (medium != null) overlayShips.Add(medium.transform);
            overlay.ships = overlayShips.ToArray();

            var pubGo = new GameObject("Frame Publisher", typeof(FramePublisher)); // 默认关闸：OnEnable 早退零开销
            Debug.Log($"[Sango.M3] wired: detection overlay (B, {overlayShips.Count} ships), frame publisher (default OFF, {pubGo.GetComponent<FramePublisher>().endpoint})");

            Debug.Log("[Sango.M2E2] wired: camera rig (C cycle bridge/bow/chase/top-down), vector arrows (V), " +
                      "radar overlay (Q/E range, Z/X sweep), simulation panel (-/= count, ,/. scale, Enter apply, P model), " +
                      "autonomous control (A, G unchanged)");

            // h. 保存场景（目录不存在先建）。
            // https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SceneManagement.EditorSceneManager.SaveScene.html
            if (!AssetDatabase.IsValidFolder(k_SceneDir))
            {
                AssetDatabase.CreateFolder("Assets", "Scenes");
            }
            EditorSceneManager.SaveScene(scene, k_ScenePath);
            AssetDatabase.SaveAssets();

            Debug.Log($"[Sango.M1] scene written: {Path.GetFullPath(k_ScenePath)}\n" +
                      "next: Play -> 左上角天气面板拖 Beaufort 0-11 看波高/白沫变化 -> 面板风速读数对照 Docs/beaufort-water-mapping.md -> 实机调锚点回填表格");
        }
    }
}
