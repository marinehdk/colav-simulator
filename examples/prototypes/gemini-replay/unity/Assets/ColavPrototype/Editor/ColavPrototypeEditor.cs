using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class ColavPrototypeEditor
{
    const string ScenePath = "Assets/ColavPrototype/Replay.unity";

    [InitializeOnLoadMethod]
    static void Initialize() { EditorApplication.delayCall += EnsureScene; }

    static void EnsureScene()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode || File.Exists(ScenePath)) return;
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        new GameObject("Recorded Colav + original Gemini service");
        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new [] { new EditorBuildSettingsScene(ScenePath, true) };
        PlayerSettings.productName = "Gemini Colav Replay Prototype";
        PlayerSettings.companyName = "Colav-Simulator prototype";
        PlayerSettings.defaultScreenWidth = 1440;
        PlayerSettings.defaultScreenHeight = 900;
        PlayerSettings.runInBackground = true;
        PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        AssetDatabase.SaveAssets();
    }

    [MenuItem("COLAV/Play Gemini Replay")]
    public static void Play()
    {
        EnsureScene();
        EditorSceneManager.OpenScene(ScenePath);
        EditorApplication.isPlaying = true;
    }

    [MenuItem("COLAV/Build Mac Replay")]
    public static void BuildMac()
    {
        EnsureScene();
        // Runtime-generated meshes still need their shaders included in standalone builds.
        if (!AssetDatabase.IsValidFolder("Assets/Resources")) AssetDatabase.CreateFolder("Assets", "Resources");
        if (!File.Exists("Assets/Resources/PrototypeStandard.mat"))
            AssetDatabase.CreateAsset(new Material(Shader.Find("Standard")), "Assets/Resources/PrototypeStandard.mat");
        if (!File.Exists("Assets/Resources/PrototypeLine.mat"))
            AssetDatabase.CreateAsset(new Material(Shader.Find("Sprites/Default")), "Assets/Resources/PrototypeLine.mat");
        AssetDatabase.SaveAssets();
        string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../outputs/Gemini-Colav-Replay.app"));
        var report = BuildPipeline.BuildPlayer(new [] { ScenePath }, output, BuildTarget.StandaloneOSX, BuildOptions.None);
        if (report == null || report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            throw new System.Exception("Standalone build failed; inspect build log.");
        Debug.Log("COLAV_PLAYER_BUILD_SUCCESS " + output);
    }
}
