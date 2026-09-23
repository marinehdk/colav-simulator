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
    /// M0 海面冒烟场景生成器（幂等：每次运行都重建场景与 Volume Profile 资产并覆盖保存；
    /// 新场景为空场景，不存在同名对象冲突；旧资产文件先删后建）。
    /// 场景内容：Water Surface(Ocean, Script Interactions) + Global Volume(PBS 天空/体积云/Water Rendering)
    /// + 太阳方向光 + 6 艘占位船（逐三角形水高查询负载）+ 相机 + FpsProbe。
    /// </summary>
    public static class M0SceneBootstrapper
    {
        const string k_SceneDir = "Assets/Scenes";
        const string k_ScenePath = k_SceneDir + "/M0-WaterSmoke.unity";
        const string k_ProfileDir = "Assets/Settings";
        const string k_ProfileAsset = k_ProfileDir + "/M0-GlobalVolumeProfile.asset";

        [MenuItem("Sango/M0/Build Water Smoke Scene")]
        public static void Build()
        {
            ConfigureHdrpAssets();
            var profile = CreateVolumeProfileAsset();
            BuildScene(profile);
        }

        // 在所有可解析到的 HDRP Asset（默认管线 + 当前管线 + 各画质档槽位）上强制开启
        // Water 支持与 Script Interactions（CPU 查询前置，引入 GPU->CPU 回读代价，即 M0 要测的成本）。
        public static void ConfigureHdrpAssets()
        {
            var assets = new HashSet<HDRenderPipelineAsset>();
            if (GraphicsSettings.defaultRenderPipeline is HDRenderPipelineAsset defaultAsset) assets.Add(defaultAsset);
            if (GraphicsSettings.currentRenderPipeline is HDRenderPipelineAsset currentAsset) assets.Add(currentAsset);
            var qualityNames = QualitySettings.names;
            for (int i = 0; i < qualityNames.Length; i++)
            {
                // https://docs.unity3d.com/6000.3/Documentation/ScriptReference/QualitySettings.GetRenderPipelineAssetAt.html
                if (QualitySettings.GetRenderPipelineAssetAt(i) is HDRenderPipelineAsset qualityAsset) assets.Add(qualityAsset);
            }

            foreach (var asset in assets)
            {
                // RenderPipelineSettings 是结构体：读出、改字段、写回（直接改成员不回写会丢失）。
                // 文档: https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.RenderPipelineSettings.html
                var settings = asset.currentPlatformRenderPipelineSettings;
                settings.supportWater = true;                                  // HDRP 默认 false；关掉时整套 WaterSystem 不跑
                settings.supportVolumetricClouds = true;
                settings.waterScriptInteractionsMode = WaterScriptInteractionsMode.GPUReadback; // 精确但含回读代价
                asset.currentPlatformRenderPipelineSettings = settings;
                EditorUtility.SetDirty(asset);
            }
            AssetDatabase.SaveAssets();
        }

        static VolumeProfile CreateVolumeProfileAsset()
        {
            // 幂等：旧 profile 资产先删再建。
            if (AssetDatabase.LoadAssetAtPath<VolumeProfile>(k_ProfileAsset) != null)
            {
                AssetDatabase.DeleteAsset(k_ProfileAsset);
            }
            if (!AssetDatabase.IsValidFolder(k_ProfileDir))
            {
                AssetDatabase.CreateFolder("Assets", "Settings");
            }

            var profile = ScriptableObject.CreateInstance(typeof(VolumeProfile)) as VolumeProfile;
            AssetDatabase.CreateAsset(profile, k_ProfileAsset);

            // VolumeProfile.Add API（同类型组件唯一，重复添加会抛异常；此处为新建 profile，安全）:
            // https://docs.unity3d.com/Packages/com.unity.render-pipelines.core@17.3/api/UnityEngine.Rendering.VolumeProfile.html
            var environment = profile.Add<VisualEnvironment>();
            environment.skyType.value = (int)SkyType.PhysicallyBased; // SkyManager 按 skyType 从 volume 栈取天空
            AssetDatabase.AddObjectToAsset(environment, profile);

            // Physical Sky（HDRP "Physically Based Sky"，太阳方向由场景方向光驱动，太阳圆盘自动渲染）:
            // https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.PhysicallyBasedSky.html
            var sky = profile.Add<PhysicallyBasedSky>();
            sky.active = true;
            AssetDatabase.AddObjectToAsset(sky, profile);

            // Volumetric Clouds 低配档：Simple + Performance 档位。HDRP 17.3 无脚本可设的"半分辨率"开关，
            // Performance 即官方低代价档（文档同 VolumetricClouds API 页）。
            // https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.VolumetricClouds.html
            var clouds = profile.Add<VolumetricClouds>();
            clouds.active = true;
            clouds.enable.value = true;
            // 嵌套枚举（HDRP 17.3 源码 Runtime/Lighting/VolumetricClouds/VolumetricClouds.cs:38,51）
            clouds.cloudControl.value = VolumetricClouds.CloudControl.Simple;
            clouds.cloudSimpleMode.value = VolumetricClouds.CloudSimpleMode.Performance;
            AssetDatabase.AddObjectToAsset(clouds, profile);

            // Water Rendering override enable 是水体渲染的第二道闸（HDRP Asset supportWater 之外）:
            // https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.WaterRendering.html
            var waterRendering = profile.Add<WaterRendering>();
            waterRendering.active = true;
            waterRendering.enable.value = true;
            AssetDatabase.AddObjectToAsset(waterRendering, profile);

            AssetDatabase.SaveAssets();
            return profile;
        }

        static void BuildScene(VolumeProfile profile)
        {
            // 幂等核心：直接换新空场景再重建（未保存的当前场景改动会被丢弃，跑菜单前先保存工作场景）。
            // https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SceneManagement.EditorSceneManager.NewScene.html
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // a. Water Surface：等价于菜单 GameObject > Water Surface（Ocean/Sea/Lake）。
            //    组件默认即 OceanSeaLake + Infinite 几何；band 参数留默认（正式项目再调，M1 做映射表）。
            //    https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.WaterSurface.html
            //    手册（GameObject > Water Surface 入口与 Script Interactions 说明）:
            //    https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/manual/water-use-the-water-system-in-your-project.html
            var waterGo = new GameObject("Water Surface", typeof(WaterSurface));
            var water = waterGo.GetComponent<WaterSurface>();
            water.surfaceType = WaterSurfaceType.OceanSeaLake;
            water.scriptInteractions = true; // ProjectPointOnWaterSurface 的前置开关（另需 HDRP Asset 侧开启，见 ConfigureHdrpAssets）

            // b. Global Volume
            var volumeGo = new GameObject("Global Volume", typeof(Volume));
            var volume = volumeGo.GetComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 10f;
            volume.sharedProfile = profile;
            // https://docs.unity3d.com/Packages/com.unity.render-pipelines.core@17.3/api/UnityEngine.Rendering.Volume.html

            // c. Directional Light：HDRP 17.3 无 SetSun()/EnableSunDisk() 公开 API（已核对 HDAdditionalLightData 全部公开成员），
            //    Physically Based Sky 自动把场景方向光当太阳（SkyManager 的 sunLight 通路 / PhysicallyBasedSkyRenderer.FindSunLight，
            //    HDRP 17.3.0 源码核对）。保守可编译形态 = 默认 HDAdditionalLightData，不做额外调用。
            //    https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.HDAdditionalLightData.html
            var lightGo = new GameObject("Directional Light", typeof(Light));
            var light = lightGo.GetComponent<Light>();
            light.type = LightType.Directional;
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            lightGo.AddComponent<HDAdditionalLightData>();
            light.intensity = 100000f; // 正午太阳量级（HDRP 方向光单位 lux），可调

            // d. 6 艘占位船：船根挂 TriangleBuoyancyProbe，hull ~12x3x4m + 上层建筑小 box，
            //    两排各 3 艘、间距 15m。primitive 内置 mesh 只读遍历，逐三角形查询负载约 24 tri/船。
            var shipsRoot = new GameObject("Ships");
            for (int i = 0; i < 6; i++)
            {
                var ship = new GameObject($"Ship-{i}", typeof(TriangleBuoyancyProbe));
                ship.transform.SetParent(shipsRoot.transform, false);
                ship.transform.localPosition = new Vector3(((i % 3) - 1) * 15f, 0f, (i / 3 - 0.5f) * 15f);

                var hull = GameObject.CreatePrimitive(PrimitiveType.Cube);
                hull.name = "Hull";
                hull.transform.SetParent(ship.transform, false);
                hull.transform.localPosition = Vector3.zero; // 吃水一半在 y=0 水面下
                hull.transform.localScale = new Vector3(12f, 3f, 4f);

                var superstructure = GameObject.CreatePrimitive(PrimitiveType.Cube);
                superstructure.name = "Superstructure";
                superstructure.transform.SetParent(ship.transform, false);
                superstructure.transform.localPosition = new Vector3(-2f, 2.75f, 0f);
                superstructure.transform.localScale = new Vector3(3f, 2.5f, 2.5f);

                ship.GetComponent<TriangleBuoyancyProbe>().waterSurface = water;
            }

            // e. Main Camera
            var cameraGo = new GameObject("Main Camera", typeof(Camera));
            cameraGo.tag = "MainCamera";
            cameraGo.transform.position = new Vector3(0f, 8f, -25f);
            cameraGo.transform.rotation = Quaternion.LookRotation(Vector3.zero - cameraGo.transform.position, Vector3.up);
            var camera = cameraGo.GetComponent<Camera>();
            camera.fieldOfView = 60f;
            camera.nearClipPlane = 0.3f;
            camera.farClipPlane = 5000f;
            cameraGo.AddComponent<HDAdditionalCameraData>();

            // FpsProbe：覆盖层 + Logs/fps-report.jsonl
            new GameObject("M0 Fps Probe", typeof(FpsProbe));

            // f. 保存场景（目录不存在先建）。
            // https://docs.unity3d.com/6000.3/Documentation/ScriptReference/SceneManagement.EditorSceneManager.SaveScene.html
            if (!AssetDatabase.IsValidFolder(k_SceneDir))
            {
                AssetDatabase.CreateFolder("Assets", "Scenes");
            }
            EditorSceneManager.SaveScene(scene, k_ScenePath);
            AssetDatabase.SaveAssets();

            Debug.Log($"[Sango.M0] scene written: {Path.GetFullPath(k_ScenePath)}\n" +
                      "next: Project Settings > Quality 确认 HDRP 中画质档 -> Game 视图 1440p -> Play -> 读 FpsProbe 覆盖层 / Logs/fps-report.jsonl");
        }
    }
}
