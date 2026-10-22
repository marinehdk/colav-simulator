using System;
using System.Collections.Generic;
using Unity.Collections;

namespace Sango
{
    /// <summary>
    /// ownship-mask-v1 §3 的 1bit 行程编码纯函数（Testing Decisions 先例
    /// FramePublisherCore:编码路径放可测程序集,MonoBehaviour 胶水在 Runtime 根）。
    /// 逐行独立、uint16 小端、恒以 0 游程开头、行游程和==width;输入=RT 读回
    /// （视口底行先行）,输出顶行先行——垂直翻转在此完成,与分流帧 JPEG 行序对齐;
    /// 黄金向量锁定两侧实现（TwinOwnshipMaskTests + test_sango_detector_mask.py）。
    /// </summary>
    public static class OwnshipMaskRle
    {
        public static byte[] Encode(NativeArray<byte> rowsBottomFirst, int width, int height)
        {
            if (rowsBottomFirst.Length < width * height)
                throw new ArgumentException("readback shorter than width*height");
            var bytes = new List<byte>(4096);
            for (int row = height - 1; row >= 0; row--)
            {
                int offset = row * width, value = 0, length = 0;
                for (int col = 0; col < width; col++)
                {
                    int bit = rowsBottomFirst[offset + col] != 0 ? 1 : 0;
                    if (bit == value) { length++; continue; }
                    AppendRun(bytes, length);
                    value = bit; length = 1;
                }
                AppendRun(bytes, length); // 行尾游程（全 0 行=单游程 width）
            }
            return bytes.ToArray();
        }

        static void AppendRun(List<byte> bytes, int length)
        {
            // width ≤1280 恒在 uint16 域;契约行游程和==width,越界即编码 bug,快死好过静默错
            if (length > ushort.MaxValue) throw new InvalidOperationException($"run {length} overflows u16 (width contract broken)");
            bytes.Add((byte)(length & 0xFF));
            bytes.Add((byte)(length >> 8));
        }
    }
}
