using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M9-1 程序化泡沫贴图（Texture2D 代码生成，零资产依赖——铁律 6"程序化生成一切运行时
    /// 资源"；确定性：无随机数，逐像素纯函数）。两张 64² RGBA32（bilinear，显存各 16 KB 量级，
    /// 全部 rig 共享静态缓存单实例）：
    ///   - RadialSoftBlob：径向软斑（alpha = smoothstep 径向衰减 × 双正弦角向扰动模拟泡沫
    ///     团块不均匀），艏浪粒子与水线环共用的"沫斑"母版；
    ///   - WakeStrip：ribbon/环带专版——U 向同款径向截面（u=0/1 处 alpha=0，环带接缝天然
    ///     无缝），V 向 1→0 线性+平滑衰减（v=0 艏/内缘浓、v=1 艉后/外缘散）。
    /// 消费方式：HDRP/Unlit 的 _UnlitColorMap（HDRP 17.3 UnlitData.hlsl 无条件采样该图，
    /// alpha = map.a × _UnlitColor.a，无需开 keyword）。
    /// </summary>
    public static class WakeFoamTexture
    {
        const int k_Size = 64;

        static Texture2D s_Blob;
        static Texture2D s_Strip;

        /// <summary>径向软斑（粒子/环带母版；静态缓存，调用方只读勿写入）。</summary>
        public static Texture2D RadialSoftBlob()
        {
            if (s_Blob != null) return s_Blob;
            s_Blob = Build((x, y) =>
            {
                // 归一中心距 r ∈ [0, ~1.41]；角向扰动让边缘呈泡沫团块状（非正圆）。
                float u = x / (k_Size - 1f) * 2f - 1f;
                float v = y / (k_Size - 1f) * 2f - 1f;
                float r = Mathf.Sqrt(u * u + v * v);
                float theta = Mathf.Atan2(v, u);
                float wobble = 1f + 0.10f * Mathf.Sin(5f * theta + 1.7f) + 0.06f * Mathf.Sin(9f * theta + 0.4f);
                float a = Mathf.SmoothStep(1.05f * wobble, 0.15f * wobble, r);
                return a;
            });
            s_Blob.name = "WakeFoam.RadialSoftBlob";
            return s_Blob;
        }

        /// <summary>尾迹带截面×纵向衰减（ribbon/水线环；静态缓存，调用方只读勿写入）。</summary>
        public static Texture2D WakeStrip()
        {
            if (s_Strip != null) return s_Strip;
            s_Strip = Build((x, y) =>
            {
                float u = x / (k_Size - 1f);        // 横向：径向截面（边缘软、中带浓）
                float v = y / (k_Size - 1f);        // 纵向：v=0 浓（艏/内缘）→ v=1 散
                float across = Mathf.SmoothStep(1f, 0.12f, Mathf.Abs(u * 2f - 1f));
                float along = Mathf.Pow(1f - v, 1.4f); // 幂次 >1：近艏端维持高浓度、尾端缓散
                return across * along;
            });
            s_Strip.name = "WakeFoam.WakeStrip";
            return s_Strip;
        }

        /// <summary>逐像素 alpha 填充（rgb 恒白：色调/亮度全由 _UnlitColor 控制）。</summary>
        static Texture2D Build(System.Func<int, int, float> alphaAt)
        {
            var tex = new Texture2D(k_Size, k_Size, TextureFormat.RGBA32, false, true)
            {
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear,
            };
            var pixels = new Color32[k_Size * k_Size]; // 一次性构建缓冲（非每帧路径）
            for (int y = 0; y < k_Size; y++)
            for (int x = 0; x < k_Size; x++)
            {
                byte a = (byte)Mathf.RoundToInt(Mathf.Clamp01(alphaAt(x, y)) * 255f);
                pixels[y * k_Size + x] = new Color32(255, 255, 255, a);
            }
            tex.SetPixels32(pixels);
            tex.Apply(false, true); // makeNoLongerReadable：上传后释放 CPU 侧副本
            return tex;
        }
    }
}
