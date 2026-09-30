using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M9-2 号灯光斑贴图（程序化生成，零外部资产）：亮核 + 指数衰减 halo 的径向 alpha 图。
    /// 通道分工按 HDRP/Unlit 采样口径（Runtime/Material/Unlit/UnlitData.hlsl:15-23）：
    /// RGB 恒白（灯色由材质 _UnlitColor.rgb 承载，相乘输出），alpha = NightGradeCore.
    /// LampSpotFalloff（相乘 _UnlitColor.a 后做叠加混合的 SrcAlpha）。会话级共享单张
    /// （各灯材质引用同贴图；域重载随静态字段清空后按需重建）。
    /// </summary>
    public static class LampSpotTexture
    {
        const int k_Size = 128; // 128² 小图 ×双线性足够（灯片世界尺寸米级，屏占比小）

        static Texture2D s_Shared;

        public static Texture2D GetShared()
        {
            if (s_Shared != null) return s_Shared;
            var tex = new Texture2D(k_Size, k_Size, TextureFormat.RGBA32, false)
            {
                name = "NavigationLampSpot",
                wrapMode = TextureWrapMode.Clamp, // 径向图越界采边不回绕
                filterMode = FilterMode.Bilinear,
                hideFlags = HideFlags.HideAndDontSave, // 纯运行时资源：不落盘、不进场景序列化
            };
            var half = (k_Size - 1) * 0.5f;
            var pixels = new Color32[k_Size * k_Size];
            for (int y = 0; y < k_Size; y++)
            for (int x = 0; x < k_Size; x++)
            {
                var r = new Vector2((x - half) / half, (y - half) / half).magnitude; // 归一化半径 [0, √2]
                var a = NightGradeCore.LampSpotFalloff(r, NightGradeCore.LampSpotCoreRadius01, NightGradeCore.LampSpotHaloDecay);
                pixels[y * k_Size + x] = new Color32(255, 255, 255, (byte)Mathf.RoundToInt(a * 255f));
            }
            tex.SetPixels32(pixels);
            tex.Apply(false); // 不建 mipmap；保持 CPU 可读（EditMode 测试断言像素用）
            s_Shared = tex;
            return tex;
        }
    }
}
