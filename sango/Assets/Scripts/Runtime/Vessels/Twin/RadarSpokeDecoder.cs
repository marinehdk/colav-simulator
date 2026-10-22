using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

namespace Sango
{
    /// <summary>
    /// X 波段雷达 spoke 解码/几何纯函数核心（00-REPORT.md §2.2/§6 P0，spec 调研
    /// docs/research/2026-10-21-unity-xband-radar/）。字节格式三向镜像钉死：
    /// 后端编码 = colav_simulator/core/radar_video.py encode_video（zlib.compress(raw,1)
    /// → base64 → sha256，encoding="deflate-base64-u8"），web 解码 =
    /// web_gui/modules/radar-video.js decodeRadarVideo（DecompressionStream('deflate')），
    /// 本类 = C# 侧同一容器：base64 → zlib 头校验（CMF 0x78，后端 wbits=15 恒出）→
    /// 剥 2 字节头 DeflateStream 解压 → 尾 4 字节 adler32 校验 → sha256 钉内容。
    /// 期望字节向量由后端 encode_video 生成、hex 字面量钉在 EditMode 测试
    /// （RadarSpokeDecoderTests），跨语言不漂移。
    /// </summary>
    public static class RadarSpokeDecoder
    {
        /// <summary>容器词汇（encode_video "encoding" 字段；decode_video/radar-video.js 同串）。</summary>
        public const string EncodingName = "deflate-base64-u8";

        /// <summary>shape 合法域镜像 decode_video（radar_video.py:82：rows∈[0,8192]、cols∈[1,4096]）。</summary>
        public const int MaxSpokes = 8192, MaxBins = 4096;

        /// <summary>错误码对齐 web decodeRadarVideo 的 throw 词汇（探针/日志对拍用）。</summary>
        public const string ErrorInvalidEncoding = "INVALID_RADAR_ENCODING";
        public const string ErrorLengthMismatch = "RADAR_LENGTH_MISMATCH";
        public const string ErrorHashMismatch = "RADAR_HASH_MISMATCH";

        /// <summary>
        /// 解码一份 encode_video 文档为 spoke raster（u8，spokes×bins 行主序，
        /// row=方位 index、col=距离 bin）。镜像 decode_video 的显式校验序：
        /// encoding/shape → base64 → 长度恰等 → sha256。非法输入抛
        /// InvalidOperationException（code=上述词汇），不返回部分数据。
        /// </summary>
        public static byte[] DecodeVideo(string encoding, int[] shape, string base64Data, string sha256Hex)
        {
            if (encoding != EncodingName || shape == null || shape.Length != 2)
                throw Fail(ErrorInvalidEncoding);
            int spokes = shape[0], bins = shape[1];
            if (spokes < 0 || spokes > MaxSpokes || bins < 1 || bins > MaxBins)
                throw Fail(ErrorInvalidEncoding);
            int size = checked(spokes * bins);
            byte[] compressed;
            try { compressed = Convert.FromBase64String(base64Data); }
            catch (FormatException) { throw Fail(ErrorInvalidEncoding); }
            byte[] raster;
            try { raster = InflateZlib(compressed, size); }
            catch (System.IO.InvalidDataException) { throw Fail(ErrorLengthMismatch); } // 截断流（DeflateStream 原生抛）归长度失配族
            if (raster == null || raster.Length != size)
                throw Fail(ErrorLengthMismatch);
            if (!Sha256Hex(raster).Equals(sha256Hex, StringComparison.OrdinalIgnoreCase))
                throw Fail(ErrorHashMismatch);
            return raster;
        }

        /// <summary>解码产出容器（DecodeVideo 的文档形状重载，checkpoint/共用）。</summary>
        public struct VideoDocument
        {
            public string encoding;
            public int[] shape;
            public string data;
            public string sha256;
        }

        /// <summary>文档形状重载（RadarCheckpointDocument 直接转译）。</summary>
        public static byte[] DecodeVideo(VideoDocument document) =>
            DecodeVideo(document.encoding, document.shape, document.data, document.sha256);

        /// <summary>
        /// zlib 容器剥离 + inflate（镜像 web DecompressionStream('deflate') 的 zlib 分支）：
        /// CMF 必为 0x78（CM=8 deflate、CINFO=7 32K 窗——后端 zlib.compress 默认 wbits 恒出），
        /// 头 2 字节 FCHECK 校验（(CMF&lt;&lt;8|FLG)%31==0）且无 FDICT；体 = [2, len-4) 的
        /// raw deflate；尾 4 字节大端 adler32（zlib 尾校验，web/python 解压隐式验证，此处显式）。
        /// 容器损坏（头/尾校验）抛 INVALID_RADAR_ENCODING；输出超 maxBytes 返 null =
        /// 长度失配（Python decompressobj(maxLength=size+1) 超长同语义；不足由调用方判）。
        /// </summary>
        static byte[] InflateZlib(byte[] compressed, int maxBytes)
        {
            if (compressed.Length < 6 || compressed[0] != 0x78
                || (((compressed[0] << 8) | compressed[1]) % 31) != 0
                || (compressed[1] & 0x20) != 0)
                throw Fail(ErrorInvalidEncoding);
            int bodyLength = compressed.Length - 6; // 剥头 2 + adler32 尾 4
            using (var source = new MemoryStream(compressed, 2, bodyLength, false))
            using (var inflater = new DeflateStream(source, CompressionMode.Decompress))
            using (var sink = new MemoryStream())
            {
                var buffer = new byte[64 * 1024];
                while (true)
                {
                    int read = inflater.Read(buffer, 0, buffer.Length);
                    if (read <= 0) break;
                    if (sink.Length + read > maxBytes) return null; // 超长 = 长度失配
                    sink.Write(buffer, 0, read);
                }
                if (Adler32(sink.ToArray()) != ReadUInt32BigEndian(compressed, compressed.Length - 4))
                    throw Fail(ErrorInvalidEncoding); // zlib 尾校验失败（python zlib.error / web 解压失败同位）
                return sink.ToArray();
            }
        }

        /// <summary>
        /// 扫掠相位（rad，自北顺时针）：sim_time/scan_period 的小数相位 × 2π。
        /// 逐字符镜像 web radar-ppi.js sweepAzimuthRad（83-86 行）——负 sim_time 取正模、
        /// scanPeriod≤0 回 0；Unity/web 同一 sim_time 即同一天线方位（00-REPORT §2.2 注意 ③）。
        /// </summary>
        public static double SweepPhaseRad(double simTimeS, double scanPeriodS)
        {
            if (!(scanPeriodS > 0)) return 0;
            return (((simTimeS / scanPeriodS) % 1.0) + 1.0) % 1.0 * (2.0 * Math.PI);
        }

        /// <summary>row（方位 index）→ 方位 rad：row·2π/spokes（radar_video.py:120 同式）。</summary>
        public static double RowBearingRad(int row, int spokes) => row * (2.0 * Math.PI) / spokes;

        /// <summary>bin → 采样距离 m：(bin+0.5)·量程/bins（bin 中心，radar_video.py:124 同式）。</summary>
        public static double BinRangeM(int bin, int bins, double rangeM) => (bin + 0.5) * rangeM / bins;

        /// <summary>
        /// 极坐标 bin → 本船 NE 投影（radar_video.py:300 检测质心同式）：
        /// north = originN + cos(bearing)·range，east = originE + sin(bearing)·range。
        /// origin = 该 spoke 采集时刻的天线位（checkpoint row_origins_ne_m[row]，本船平移
        /// 期用行源坐标，web radar-video.js raster() 同语义）。
        /// </summary>
        public static void ProjectBinToNe(double originNorthM, double originEastM, double bearingRad,
            double rangeM, out double northM, out double eastM)
        {
            northM = originNorthM + Math.Cos(bearingRad) * rangeM;
            eastM = originEastM + Math.Sin(bearingRad) * rangeM;
        }

        /// <summary>
        /// checkpoint JSON 的 row_origins_ne_m（[[north,east],…]）解析。JsonUtility 不支持
        /// 嵌套匿名数组，此处手写限定扫描器（纯函数，EditMode 钉死）：键缺失返 null；
        /// 严格 [[数,数],…] 形状（容空白），畸形返 null 不部分产出。
        /// </summary>
        public static double[][] ParseRowOrigins(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            int key = json.IndexOf("\"row_origins_ne_m\"", StringComparison.Ordinal);
            if (key < 0) return null;
            int cursor = json.IndexOf('[', key + 18);
            if (cursor < 0) return null;
            cursor = SkipSpace(json, cursor + 1); // 进入外层 [
            if (cursor < json.Length && json[cursor] == ']') return new double[0][]; // 空数组
            var rows = new List<double[]>();
            while (true)
            {
                if (cursor >= json.Length || json[cursor] != '[') return null;
                var pair = new double[2];
                for (int i = 0; i < 2; i++)
                {
                    if (i == 1) // 数间逗号
                    {
                        cursor = SkipSpace(json, cursor);
                        if (cursor >= json.Length || json[cursor] != ',') return null;
                    }
                    cursor = ScanNumber(json, SkipSpace(json, cursor + 1), out pair[i]);
                    if (cursor < 0) return null;
                }
                cursor = SkipSpace(json, cursor);
                if (cursor >= json.Length || json[cursor] != ']') return null;
                rows.Add(pair);
                cursor = SkipSpace(json, cursor + 1);
                if (cursor >= json.Length) return null;
                if (json[cursor] == ']') return rows.ToArray();
                if (json[cursor] != ',') return null;
                cursor = SkipSpace(json, cursor + 1);
            }
        }

        /// <summary>自 index 起扫描一个 JSON 数（数字/符号/小数点/指数），成功返尾后位置，失败返 -1。</summary>
        static int ScanNumber(string json, int index, out double value)
        {
            value = 0;
            if (index >= json.Length) return -1;
            int end = index;
            while (end < json.Length && (char.IsDigit(json[end]) || "+-.eE".IndexOf(json[end]) >= 0)) end++;
            return end > index && double.TryParse(json.Substring(index, end - index), NumberStyles.Float,
                CultureInfo.InvariantCulture, out value) ? end : -1;
        }

        static int SkipSpace(string json, int index)
        {
            while (index < json.Length && (json[index] == ' ' || json[index] == '\t'
                || json[index] == '\n' || json[index] == '\r'))
                index++;
            return index;
        }

        /// <summary>SHA-256 hex（小写；encode_video sha256 字段同格式）。</summary>
        public static string Sha256Hex(byte[] payload)
        {
            using (var hasher = SHA256.Create())
                return ToHexLower(hasher.ComputeHash(payload));
        }

        static string ToHexLower(byte[] digest)
        {
            var builder = new StringBuilder(digest.Length * 2);
            foreach (byte value in digest) builder.Append(value.ToString("x2"));
            return builder.ToString();
        }

        static uint ReadUInt32BigEndian(byte[] source, int offset) =>
            (uint)(source[offset] << 24 | source[offset + 1] << 16 | source[offset + 2] << 8 | source[offset + 3]);

        /// <summary>adler32（RFC 1950 尾校验；模 65521 延迟回减避免 uint 溢出路径）。</summary>
        static uint Adler32(byte[] payload)
        {
            uint a = 1, b = 0;
            foreach (byte value in payload)
            {
                a = (a + value) % 65521;
                b = (b + a) % 65521;
            }
            return (b << 16) | a;
        }

        static InvalidOperationException Fail(string code) => new InvalidOperationException(code);
    }
}
