using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.HighDefinition;

namespace Sango.Editor
{
    /// <summary>
    /// M0-C 批处理入口：空工程无 HDRP Asset（Build() 里的 ConfigureHdrpAssets 对空集合空转），
    /// 此处先按 HDRP 17.3 官方工厂路径创建并挂默认管线（对齐 HDAssetFactory.cs:16 与
    /// HDWizard.Configuration.cs:452 的写法），再触发场景构建。
    /// 用法: -executeMethod Sango.Editor.M0SetupPipeline.Setup
    /// </summary>
    public static class M0SetupPipeline
    {
        const string k_AssetPath = "Assets/Settings/SangoHDRP.asset";

        public static void Setup()
        {
            EnsureHdrpAsset();
            M0SceneBootstrapper.Build();
        }

        static void EnsureHdrpAsset()
        {
            if (GraphicsSettings.defaultRenderPipeline is HDRenderPipelineAsset)
            {
                Debug.Log("[Sango.M0] HDRP asset already assigned, skipping creation");
                return;
            }

            var existing = AssetDatabase.LoadAssetAtPath<HDRenderPipelineAsset>(k_AssetPath);
            var asset = existing;
            if (asset == null)
            {
                if (!AssetDatabase.IsValidFolder("Assets/Settings"))
                {
                    AssetDatabase.CreateFolder("Assets", "Settings");
                }
                // HDRP 官方工厂路径：无额外 default resources 绑定（HDAssetFactory.cs 同款）
                asset = ScriptableObject.CreateInstance<HDRenderPipelineAsset>();
                AssetDatabase.CreateAsset(asset, k_AssetPath);
            }

            GraphicsSettings.defaultRenderPipeline = asset;
            AssetDatabase.SaveAssets();
            Debug.Log($"[Sango.M0] HDRP asset created and assigned: {k_AssetPath}");
        }
    }
}
