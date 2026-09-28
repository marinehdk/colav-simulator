using System.IO;
using System.IO.Compression;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.PackageManager;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Editor
{
    /// <summary>
    /// M2-E1 遭遇场景生成器（幂等，batchmode 可执行；spec #84）。深蓝开阔海面（无岛）+
    /// Global Volume（独立 M2E profile：M1 重建先删后建会换 GUID，不得共享）+ 太阳方向光 +
    /// WeatherController/WeatherGUI（复用）+ 两艘编目船（own = Medium liner / target = Large cargo，
    /// 经 PlaceCatalogShip 组合烘焙艏向放置）+ WaypointFollower×2（enabled=false，导演驱动）+
    /// EncounterDirector + EncounterPanel（右上角）+ 北向上正交俯视相机。无岛、无桥楼相机。
    /// 保存 Assets/Scenes/M2E-Encounter.unity。首跑自动导入 TMP Essentials（世界标签需要）。
    /// batchmode: -executeMethod Sango.Editor.M2ESceneBootstrapper.Build（带 -quit）。
    /// </summary>
    public static class M2ESceneBootstrapper
    {
        const string k_SceneDir = "Assets/Scenes";
        const string k_ScenePath = k_SceneDir + "/M2E-Encounter.unity";
        const string k_ProfileAsset = "Assets/Settings/M2E-GlobalVolumeProfile.asset";
        const string k_TmpSettingsAsset = "Assets/TextMesh Pro/Resources/TMP Settings.asset";

        // 俯视相机高度：正交视野尺寸由 EncounterDirector 按 ExtentM 驱动，高度只需盖住波浪起伏。
        const float k_CameraHeight = 600f;

        [MenuItem("Sango/M2/Build Encounter Scene")]
        public static void Build()
        {
            M0SceneBootstrapper.ConfigureHdrpAssets();
            VesselAssetPipeline.EnsureBuilt(); // 干净克隆时自动补建船模 prefab/编目（齐全则零开销跳过）
            EnsureTmpEssentials();
            var profile = M1SceneBootstrapper.CreateVolumeProfileAsset(k_ProfileAsset);
            BuildScene(profile);
        }

        // ── TMP Essentials（spec：世界标签用 TextMeshPro，未导入则导入）─────────────────
        // batchmode 安全路径：AssetDatabase.ImportPackage 在 -batchmode -quit 下是"排队到下个
        // editor tick"语义，批跑直接退出 → 永不执行（实测 FAILED）。unitypackage 本体是
        // gzipped tar（<guid>/asset + asset.meta + pathname），手工解包等价导入（保留 GUID，
        // 与菜单导入逐字节同结果）。
        static void EnsureTmpEssentials()
        {
            if (File.Exists(k_TmpSettingsAsset))
            {
                Debug.Log("[Sango.M2E] TMP Essentials already present, skip import");
                return;
            }
            string packageDir = UguiPackageDir();
            string unitypackage = packageDir != null
                ? Path.Combine(packageDir, "Package Resources", "TMP Essential Resources.unitypackage")
                : null;
            if (unitypackage == null || !File.Exists(unitypackage))
            {
                Debug.LogError($"[Sango.M2E] TMP essential resources package not found ({unitypackage}) — world labels will fall back to TMP default font (may not render)");
                return;
            }
            int files = ExtractUnityPackage(unitypackage, "Assets");
            AssetDatabase.Refresh();
            bool ok = File.Exists(k_TmpSettingsAsset);
            Debug.Log($"[Sango.M2E] TMP Essentials import from {unitypackage}: {(ok ? "OK" : "FAILED")} ({files} files extracted)");
        }

        /// <summary>
        /// 解包 unitypackage 到工程（等价非交互 ImportPackage）。tar 逐 512 字节头解析：
        /// name@0..100 / size@124..136（八进制）/ typeflag@156；每个 &lt;guid&gt;/ 目录含
        /// pathname（目标路径）、asset（内容）、asset.meta（含 GUID 的 importer 元数据）。
        /// </summary>
        static int ExtractUnityPackage(string unitypackagePath, string destRoot)
        {
            var entries = new Dictionary<string, (string path, byte[] data)>();
            using (var gz = new GZipStream(File.OpenRead(unitypackagePath), CompressionMode.Decompress))
            {
                var header = new byte[512];
                while (ReadExactly(gz, header, 512))
                {
                    bool allZero = true;
                    foreach (byte b in header) { if (b != 0) { allZero = false; break; } }
                    if (allZero) continue; // 两块全零结束块（或块间填充），跳过续读
                    string name = TarString(header, 0, 100).TrimStart('.', '/');
                    long size = ParseOctal(header, 124, 12);
                    char typeflag = (char)header[156];
                    if (typeflag == '5' || size == 0) continue; // 目录项无内容
                    var data = new byte[size];
                    if (!ReadExactly(gz, data, (int)size)) break;
                    string key = name.Trim('/');
                    entries[key] = (name, data);
                    // 数据按 512 对齐补读尾块
                    long pad = (512 - size % 512) % 512;
                    if (pad > 0)
                    {
                        var padBuf = new byte[pad];
                        if (!ReadExactly(gz, padBuf, (int)pad)) break;
                    }
                }
            }

            // 按 <guid>/ 分组：pathname 给目标路径，asset / asset.meta 成对落盘。
            var guids = new HashSet<string>();
            foreach (var key in entries.Keys)
            {
                int slash = key.IndexOf('/');
                if (slash > 0) guids.Add(key.Substring(0, slash));
            }
            int written = 0;
            foreach (var guid in guids)
            {
                if (!entries.TryGetValue(guid + "/pathname", out var pathname)) continue;
                string destPath = TarStringFromBytes(pathname.data).Trim().TrimStart('.', '/');
                if (string.IsNullOrEmpty(destPath) || !destPath.StartsWith("Assets/")) continue;
                if (entries.TryGetValue(guid + "/asset", out var asset))
                {
                    string full = Path.Combine(destRoot, destPath.Substring("Assets/".Length));
                    Directory.CreateDirectory(Path.GetDirectoryName(full));
                    File.WriteAllBytes(full, asset.data);
                    written++;
                }
                if (entries.TryGetValue(guid + "/asset.meta", out var meta))
                {
                    string full = Path.Combine(destRoot, destPath.Substring("Assets/".Length)) + ".meta";
                    File.WriteAllBytes(full, meta.data);
                }
            }
            return written;
        }

        static string TarStringFromBytes(byte[] data)
        {
            int end = data.Length;
            for (int i = 0; i < data.Length; i++)
            {
                if (data[i] == 0) { end = i; break; }
            }
            return System.Text.Encoding.UTF8.GetString(data, 0, end).TrimEnd('\0');
        }

        static string TarString(byte[] buf, int offset, int count)
        {
            int end = offset + count;
            for (int i = offset; i < offset + count; i++)
            {
                if (buf[i] == 0) { end = i; break; }
            }
            return System.Text.Encoding.UTF8.GetString(buf, offset, end - offset).TrimEnd('\0');
        }

        static long ParseOctal(byte[] buf, int offset, int count)
        {
            string s = TarString(buf, offset, count).Trim(' ', '\0');
            return s.Length == 0 ? 0 : System.Convert.ToInt64(s, 8);
        }

        static bool ReadExactly(Stream s, byte[] buf, int count)
        {
            int total = 0;
            while (total < count)
            {
                int n = s.Read(buf, total, count - total);
                if (n <= 0) return false;
                total += n;
            }
            return true;
        }

        static string UguiPackageDir()
        {
            // UnityEditor.PackageInfo 与 PackageManager.PackageInfo 二义，显式消歧。
            var info = UnityEditor.PackageManager.PackageInfo.FindForAssetPath("Packages/com.unity.ugui/package.json");
            if (info != null && !string.IsNullOrEmpty(info.resolvedPath)) return info.resolvedPath;
            string[] dirs = Directory.GetDirectories("Library/PackageCache", "com.unity.ugui@*");
            return dirs.Length > 0 ? dirs[0] : null;
        }

        static void BuildScene(VolumeProfile profile)
        {
            // 幂等核心：NewScene 重建（未保存的当前场景改动会被丢弃）。
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // a. Water Surface：Ocean + Infinite + Script Interactions（同 M1，无岛）。
            var waterGo = new GameObject("Water Surface", typeof(WaterSurface));
            var water = waterGo.GetComponent<WaterSurface>();
            water.surfaceType = WaterSurfaceType.OceanSeaLake;
            water.scriptInteractions = true; // M2 浮力查询

            // b. Global Volume（独立 M2E profile）
            var volumeGo = new GameObject("Global Volume", typeof(Volume));
            var volume = volumeGo.GetComponent<Volume>();
            volume.isGlobal = true;
            volume.priority = 10f;
            volume.sharedProfile = profile;

            // c. Directional Light：PBS 太阳（旋转/强度由 WeatherController 驱动，同 M1）
            var lightGo = new GameObject("Directional Light", typeof(Light));
            var light = lightGo.GetComponent<Light>();
            light.type = LightType.Directional;
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            lightGo.AddComponent<HDAdditionalLightData>();
            light.intensity = 100000f;

            // d. 天气（复用 WeatherController/WeatherGUI；GUI 面板在左上）
            var weatherGo = new GameObject("Weather", typeof(WeatherController));
            var weather = weatherGo.GetComponent<WeatherController>();
            weather.waterSurface = water;
            weather.globalVolume = volume;
            weather.sunLight = light;
            weather.applyEveryFrame = true;
            var guiGo = new GameObject("Weather GUI", typeof(WeatherGUI));
            var gui = guiGo.GetComponent<WeatherGUI>();
            gui.controller = weather;
            // M2-E：关数字键 0-9（直设蒲福级）——同屏 EncounterPanel 用 1/2/3 选模式，避免一键双义；
            // T/F 时刻/雾距预设保留给天气侧。M1 场景默认档不变（digitHotkeysEnabled = true）。
            gui.digitHotkeysEnabled = false;

            // e. 两艘编目船：own = Medium liner / target = Large cargo（spec Implementation Decisions）。
            //    初始位姿 = 对遇模式生成几何（EncounterDirector.Awake 会重摆，此处给场景一个合理默认态）。
            var headOn = EncounterGeometry.Build(EncounterType.HeadOn, EncounterGeometry.DefaultArea);
            var catalog = AssetDatabase.LoadAssetAtPath<VesselCatalog>(VesselAssetPipeline.CatalogAssetPath);
            if (catalog == null)
            {
                Debug.LogError($"[Sango.M2E] vessel catalog missing at {VesselAssetPipeline.CatalogAssetPath}");
                return;
            }
            var shipsRoot = new GameObject("Ships");
            var own = M1SceneBootstrapper.PlaceCatalogShip(catalog, VesselClass.Medium, headOn.Own.SpawnXZ, headOn.Own.HeadingDeg, shipsRoot.transform, water);
            var target = M1SceneBootstrapper.PlaceCatalogShip(catalog, VesselClass.Large, headOn.Target.SpawnXZ, headOn.Target.HeadingDeg, shipsRoot.transform, water);
            if (own == null || target == null)
            {
                Debug.LogError("[Sango.M2E] ship placement failed, scene build aborted");
                return;
            }

            // f. 跟随器：enabled=false——自身 Update 关闭，EncounterDirector 按仿真步长 StepOnce。
            //    烘焙艏向补偿按编目档位注入（Medium 180 / Large 0）：导航艏向 = 渲染艏向。
            var ownFollower = own.AddComponent<WaypointFollower>();
            ownFollower.enabled = false;
            ownFollower.demoHotkeysEnabled = false; // 演示 G 只归 M1 演示船；遭遇船纯面板驱动
            ownFollower.bowYawDegOffset = VesselAssetPipeline.BowYawDeg(VesselClass.Medium);
            var targetFollower = target.AddComponent<WaypointFollower>();
            targetFollower.enabled = false;
            targetFollower.demoHotkeysEnabled = false;
            targetFollower.bowYawDegOffset = VesselAssetPipeline.BowYawDeg(VesselClass.Large);

            // g. 遭遇导演 + 面板（右上角）。
            var directorGo = new GameObject("Encounter Director", typeof(EncounterDirector));
            var director = directorGo.GetComponent<EncounterDirector>();
            director.ownFollower = ownFollower;
            director.targetFollower = targetFollower;
            director.ownShip = own.transform;
            director.targetShip = target.transform;

            var panelGo = new GameObject("Encounter GUI", typeof(EncounterPanel));
            panelGo.GetComponent<EncounterPanel>().director = director;

            // g2. M3 缝钉子①④（spec #86）：检测框叠加层（B 切换，真值框 + "1.0 (gt)" 标签，
            //     相机随 Top Camera；投影走 OverlayProjection 纯函数）+ ZMQ 帧发布器（默认 OFF）。
            var overlayGo = new GameObject("Detection Overlay", typeof(DetectionOverlay));
            overlayGo.GetComponent<DetectionOverlay>().ships = new[] { own.transform, target.transform };
            var pubGo = new GameObject("Frame Publisher", typeof(FramePublisher));
            Debug.Log($"[Sango.M3] wired: detection overlay (B, 2 ships), frame publisher (default OFF, {pubGo.GetComponent<FramePublisher>().endpoint})");

            // h. 北向上正交俯视相机（唯一相机）：forward = 下、up = 北 → 屏幕右上东、上北（标准海图方向）。
            var cameraGo = new GameObject("Top Camera", typeof(Camera));
            cameraGo.tag = "MainCamera";
            cameraGo.transform.position = new Vector3(0f, k_CameraHeight, 0f);
            cameraGo.transform.rotation = Quaternion.LookRotation(Vector3.down, Vector3.forward);
            var camera = cameraGo.GetComponent<Camera>();
            camera.orthographic = true;
            camera.orthographicSize = headOn.ExtentM; // Awake 后由 director 按 ExtentM 驱动
            camera.nearClipPlane = 1f;
            camera.farClipPlane = 1500f;
            cameraGo.AddComponent<HDAdditionalCameraData>();

            // i. 保存
            if (!AssetDatabase.IsValidFolder(k_SceneDir))
            {
                AssetDatabase.CreateFolder("Assets", "Scenes");
            }
            EditorSceneManager.SaveScene(scene, k_ScenePath);
            AssetDatabase.SaveAssets();

            Debug.Log($"[Sango.M2E] scene written: {Path.GetFullPath(k_ScenePath)}\n" +
                      "next: Play -> 右上角面板选模式 -> Start -> 俯视看会遇/轨迹/时间球/标签/比例尺 -> Pause/x2/Reset");
        }
    }
}
