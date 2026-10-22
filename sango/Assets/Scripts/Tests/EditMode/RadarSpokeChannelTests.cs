using System;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// RadarSpokeDecoder 纯函数测试（00-REPORT §6 P0；镜像三源：
    /// 后端 colav_simulator/core/radar_video.py encode_video/decode_video、
    /// web web_gui/modules/radar-video.js decodeRadarVideo、radar-ppi.js sweepAzimuthRad）。
    /// 期望字节向量由后端 encode_video 生成（.venv/bin/python，
    /// np.arange(256).reshape(16,16) / 降序 / 0xAB 常数三份，2026-10-21），hex/b64
    /// 字面量钉死在此——跨语言字节兼容不随 zlib 实现漂移。
    /// </summary>
    public class RadarSpokeDecoderTests
    {
        // ── 后端钉死向量（provenance：encode_video，zlib level 1，头 0x78 0x01）──
        const string AscendingBase64 = "eAEBAAH//gABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4fICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj9AQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVpbXF1eX2BhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5ent8fX5/gIGCg4SFhoeIiYqLjI2Oj5CRkpOUlZaXmJmam5ydnp+goaKjpKWmp6ipqqusra6vsLGys7S1tre4ubq7vL2+v8DBwsPExcbHyMnKy8zNzs/Q0dLT1NXW19jZ2tvc3d7f4OHi4+Tl5ufo6err7O3u7/Dx8vP09fb3+Pn6+/z9/v+t9n+B";
        const string AscendingSha256 = "40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880";
        const string DescendingBase64 = "eAEBAAH//v/+/fz7+vn49/b19PPy8fDv7u3s6+rp6Ofm5eTj4uHg397d3Nva2djX1tXU09LR0M/OzczLysnIx8bFxMPCwcC/vr28u7q5uLe2tbSzsrGwr66trKuqqainpqWko6KhoJ+enZybmpmYl5aVlJOSkZCPjo2Mi4qJiIeGhYSDgoGAf359fHt6eXh3dnV0c3JxcG9ubWxramloZ2ZlZGNiYWBfXl1cW1pZWFdWVVRTUlFQT05NTEtKSUhHRkVEQ0JBQD8+PTw7Ojk4NzY1NDMyMTAvLi0sKyopKCcmJSQjIiEgHx4dHBsaGRgXFhUUExIREA8ODQwLCgkIBwYFBAMCAQBa+3+B";
        const string DescendingSha256 = "cd6816b77f68d70001fc3eaa4d42bdd67cb5973b3151cc5292ecc02a3daac6ab";
        const string ConstantAbBase64 = "eAFbvXpkAwDbe6sB";
        const string ConstantAbSha256 = "1080e279b51b8594a78556e2fdb4dfe9ca82ac2fbab5007de2bac4213c2e1f92";
        // 0x00..0xFF 全字节序 hex（ascending 栅格的原始内容钉死）
        const string AscendingHex =
            "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f" +
            "202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f" +
            "404142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f" +
            "606162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f" +
            "808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f" +
            "a0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebf" +
            "c0c1c2c3c4c5c6c7c8c9cacbcccdcecfd0d1d2d3d4d5d6d7d8d9dadbdcdddedf" +
            "e0e1e2e3e4e5e6e7e8e9eaebecedeeeff0f1f2f3f4f5f6f7f8f9fafbfcfdfeff";

        const double Tolerance = 1e-9;

        [Test]
        public void DecodeVideo_PinnedBackendVector_IsByteExact()
        {
            byte[] raster = RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 16 }, AscendingBase64, AscendingSha256);
            Assert.That(raster.Length, Is.EqualTo(256));
            Assert.That(raster, Is.EqualTo(FromHex(AscendingHex)), "解码字节 = 后端 encode_video 的原始栅格");
            for (int i = 0; i < 256; i++) Assert.That(raster[i], Is.EqualTo((byte)i), $"byte {i}");
        }

        [Test]
        public void DecodeVideo_PinnedCompressibleVector_DecodesConstantGrid()
        {
            // 可压缩载荷：zlib level 1 走真压缩分支（非存储块），同一容器照样解。
            byte[] raster = RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 16 }, ConstantAbBase64, ConstantAbSha256);
            Assert.That(raster.Length, Is.EqualTo(256));
            for (int i = 0; i < raster.Length; i++) Assert.That(raster[i], Is.EqualTo(0xAB));
        }

        [Test]
        public void DecodeVideo_CSharpEncodedVector_RoundTrips()
        {
            // C# DeflateStream 产的 zlib 容器（头+deflate+adler32）→ 解码往返：
            // 证明容器构造与 zlib 规范互通（独立于后端字节的另一方向钉子）。
            var raw = new byte[8 * 32];
            for (int i = 0; i < raw.Length; i++) raw[i] = (byte)(i * 7 + i / 32 * 3);
            string encoded = ZlibContainerBase64(raw);
            byte[] raster = RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 8, 32 }, encoded, RadarSpokeDecoder.Sha256Hex(raw));
            Assert.That(raster, Is.EqualTo(raw));
        }

        [Test]
        public void DecodeVideo_RejectsMirroringWebErrorVocabulary()
        {
            // encoding 词汇错 → INVALID_RADAR_ENCODING（web 同 throw）
            AssertCode(RadarSpokeDecoder.ErrorInvalidEncoding, () => RadarSpokeDecoder.DecodeVideo(
                "raw-u8", new[] { 16, 16 }, AscendingBase64, AscendingSha256));
            // shape 越界（cols=0）→ INVALID_RADAR_ENCODING（decode_video 同域）
            AssertCode(RadarSpokeDecoder.ErrorInvalidEncoding, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 0 }, AscendingBase64, AscendingSha256));
            // 坏 base64 → INVALID_RADAR_ENCODING
            AssertCode(RadarSpokeDecoder.ErrorInvalidEncoding, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 16 }, "!!not-base64!!", AscendingSha256));
            // zlib 头非 0x78 → INVALID_RADAR_ENCODING
            byte[] broken = Convert.FromBase64String(AscendingBase64);
            broken[0] = 0x77;
            AssertCode(RadarSpokeDecoder.ErrorInvalidEncoding, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 16 }, Convert.ToBase64String(broken), AscendingSha256));
            // 尾部截断（adler 尾被切，容器不完整）→ INVALID_RADAR_ENCODING
            AssertCode(RadarSpokeDecoder.ErrorInvalidEncoding, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 16 },
                AscendingBase64.Substring(0, AscendingBase64.Length - 8), AscendingSha256));
            // shape 声明与载荷不符（两个方向）→ RADAR_LENGTH_MISMATCH
            AssertCode(RadarSpokeDecoder.ErrorLengthMismatch, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 32 }, AscendingBase64, AscendingSha256));
            AssertCode(RadarSpokeDecoder.ErrorLengthMismatch, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 8 }, AscendingBase64, AscendingSha256));
            // sha256 失配 → RADAR_HASH_MISMATCH
            AssertCode(RadarSpokeDecoder.ErrorHashMismatch, () => RadarSpokeDecoder.DecodeVideo(
                RadarSpokeDecoder.EncodingName, new[] { 16, 16 }, AscendingBase64, DescendingSha256));
        }

        static void AssertCode(string code, TestDelegate call)
        {
            var error = Assert.Throws<InvalidOperationException>(call, code);
            Assert.That(error.Message, Is.EqualTo(code));
        }

        [Test]
        public void SweepPhaseRad_MirrorsWebSweepAzimuth()
        {
            // radar-ppi.js:83-86 逐语义镜像：正 wrap/负 wrap/周期边界/非正周期守卫。
            Assert.That(RadarSpokeDecoder.SweepPhaseRad(0.0, 2.5), Is.EqualTo(0.0).Within(Tolerance));
            Assert.That(RadarSpokeDecoder.SweepPhaseRad(1.25, 2.5), Is.EqualTo(Math.PI).Within(Tolerance), "半周期 = 180°");
            Assert.That(RadarSpokeDecoder.SweepPhaseRad(2.5, 2.5), Is.EqualTo(0.0).Within(Tolerance), "整周期 wrap 回 0");
            Assert.That(RadarSpokeDecoder.SweepPhaseRad(3.75, 2.5), Is.EqualTo(Math.PI).Within(Tolerance));
            Assert.That(RadarSpokeDecoder.SweepPhaseRad(-1.25, 2.5), Is.EqualTo(Math.PI).Within(Tolerance), "负 sim_time 取正模（web +1)%1 同式）");
            Assert.That(RadarSpokeDecoder.SweepPhaseRad(10.0, 0.0), Is.EqualTo(0.0), "scanPeriod<=0 回 0");
            // 与描述子一致性：24 rpm（scan_period 2.5s）下 spoke 序号相位 = row/2048 全转
            double full = RadarSpokeDecoder.SweepPhaseRad(2.5, 2.5);
            Assert.That(full, Is.EqualTo(0.0).Within(Tolerance));
        }

        [Test]
        public void PolarProjection_MirrorsBackendCentroidMath()
        {
            // radar_video.py:120/124/300 同式：row→bearing、bin→bin 中心距离、极坐标→NE。
            Assert.That(RadarSpokeDecoder.RowBearingRad(1024, 2048), Is.EqualTo(Math.PI).Within(Tolerance), "半转 = 180°");
            Assert.That(RadarSpokeDecoder.RowBearingRad(512, 2048), Is.EqualTo(Math.PI / 2).Within(Tolerance), "四分之一转 = 90°");
            Assert.That(RadarSpokeDecoder.RowBearingRad(0, 2048), Is.EqualTo(0.0).Within(Tolerance));
            double range = RadarSpokeDecoder.BinRangeM(1023, 1024, 1388.9);
            Assert.That(range, Is.EqualTo(1023.5 * 1388.9 / 1024).Within(1e-6), "bin 中心采样");

            RadarSpokeDecoder.ProjectBinToNe(100.0, 200.0, 0.0, 500.0, out double north, out double east);
            Assert.That(north, Is.EqualTo(600.0).Within(Tolerance), "bearing 0 = 正北 +range");
            Assert.That(east, Is.EqualTo(200.0).Within(Tolerance));

            RadarSpokeDecoder.ProjectBinToNe(100.0, 200.0, Math.PI / 2, 500.0, out north, out east);
            Assert.That(north, Is.EqualTo(100.0).Within(Tolerance));
            Assert.That(east, Is.EqualTo(700.0).Within(Tolerance), "bearing 90° = 正东 +range");

            RadarSpokeDecoder.ProjectBinToNe(100.0, 200.0, Math.PI, 500.0, out north, out east);
            Assert.That(north, Is.EqualTo(-400.0).Within(Tolerance), "bearing 180° = 正南");

            // 组合：row 1024（正南）、bin 0（bin 中心）→ 检测质心同源投影。
            double bearing = RadarSpokeDecoder.RowBearingRad(1024, 2048);
            double binRange = RadarSpokeDecoder.BinRangeM(0, 1024, 1388.9);
            RadarSpokeDecoder.ProjectBinToNe(6957500.0, 39500.0, bearing, binRange, out north, out east);
            Assert.That(north, Is.EqualTo(6957500.0 - binRange).Within(1e-6));
            Assert.That(east, Is.EqualTo(39500.0).Within(1e-6));
        }

        [Test]
        public void ParseRowOrigins_StrictPairScanner()
        {
            const string doc = "{\"t_s\":2.5,\"row_origins_ne_m\": [[100.5, 200.25],[1e3, -2.5],[3, 4]],\"row_times_s\":[0]}";
            double[][] origins = RadarSpokeDecoder.ParseRowOrigins(doc);
            Assert.That(origins, Is.Not.Null);
            Assert.That(origins.Length, Is.EqualTo(3));
            Assert.That(origins[0][0], Is.EqualTo(100.5).Within(Tolerance));
            Assert.That(origins[0][1], Is.EqualTo(200.25).Within(Tolerance));
            Assert.That(origins[1][0], Is.EqualTo(1000.0).Within(Tolerance), "科学计数法可解析");
            Assert.That(origins[1][1], Is.EqualTo(-2.5).Within(Tolerance));

            Assert.That(RadarSpokeDecoder.ParseRowOrigins("{\"row_times_s\":[0]}"), Is.Null, "键缺失 → null");
            Assert.That(RadarSpokeDecoder.ParseRowOrigins("{\"row_origins_ne_m\":[]}").Length, Is.EqualTo(0), "空数组");
            Assert.That(RadarSpokeDecoder.ParseRowOrigins("{\"row_origins_ne_m\":[[1,2],[3]]}"), Is.Null, "畸形对 → null 不部分产出");
            Assert.That(RadarSpokeDecoder.ParseRowOrigins("{\"row_origins_ne_m\":[1,2]}"), Is.Null, "未嵌套 → null");
        }

        // ── 测试侧 zlib 容器构造（与解码器独立实现，双向钉子）────────────────────

        static string ZlibContainerBase64(byte[] raw)
        {
            using (var sink = new MemoryStream())
            {
                sink.WriteByte(0x78);
                sink.WriteByte(0x01);
                using (var deflater = new DeflateStream(sink, System.IO.Compression.CompressionLevel.Optimal, true))
                    deflater.Write(raw, 0, raw.Length);
                uint a = 1, b = 0; // adler32（RFC 1950）
                foreach (byte value in raw) { a = (a + value) % 65521; b = (b + a) % 65521; }
                uint adler = (b << 16) | a;
                sink.WriteByte((byte)(adler >> 24));
                sink.WriteByte((byte)(adler >> 16));
                sink.WriteByte((byte)(adler >> 8));
                sink.WriteByte((byte)adler);
                return Convert.ToBase64String(sink.ToArray());
            }
        }

        static byte[] FromHex(string hex)
        {
            var raw = new byte[hex.Length / 2];
            for (int i = 0; i < raw.Length; i++) raw[i] = Convert.ToByte(hex.Substring(i * 2, 2), 16);
            return raw;
        }
    }

    /// <summary>
    /// RadarSpokeStream 组件测试（EditMode；组件禁用态直调——不起 fetch worker，
    /// HTTP 面由 TwinRest 既有模式覆盖，此处钉数据面状态机）。checkpoint 载荷用
    /// RadarSpokeDecoderTests 同三份后端钉死向量（16×16；envelope spokes 对齐 16）。
    /// </summary>
    public class RadarSpokeStreamTests
    {
        RadarSpokeStream m_Stream;

        [SetUp]
        public void SetUp()
        {
            var host = new GameObject("radar spoke stream under test");
            m_Stream = host.AddComponent<RadarSpokeStream>();
            m_Stream.enabled = false; // 直调路径：URL 只入队不拉取（EditMode 确定性）
        }

        [TearDown]
        public void TearDown()
        {
            if (m_Stream != null) UnityEngine.Object.DestroyImmediate(m_Stream.gameObject);
        }

        static string Key64(char c) => new string(c, 64);

        static ColavTelemetry EnvelopeFrame(string key, int spokes = 2048, double rangeM = 1388.9)
        {
            string json = "{\"seq\":1,\"sim_time\":2.5,\"truth\":[{\"id\":0,\"north\":6957500,\"east\":39500}]," +
                "\"radar_ppi\":{\"schema_version\":\"radar-ppi@1\",\"sensor_label\":\"radar_x\",\"mount_id\":\"mast_top_xband\"," +
                "\"seed\":7,\"spokes\":" + spokes + ",\"scan_period_s\":2.5,\"range_scale_nm\":0.75,\"blind_ring_m\":54.0," +
                "\"range_scales_nm\":[0.75,1.5,3.0,6.0,12.0,24.0],\"sea_state_beaufort\":3.0}," +
                "\"radar_scans\":[{\"vessel_id\":0,\"sensor_label\":\"radar_x\",\"t_s\":2.5," +
                "\"shadow_video\":{\"range_m\":" + rangeM.ToString(CultureInfo.InvariantCulture) + ",\"spokes\":" + spokes +
                ",\"spoke_seq_end\":2048,\"checkpoint\":{\"url\":\"/api/radar/checkpoints/" + key +
                "\",\"checkpoint_key\":\"" + key + "\"}}}]}";
            return ColavTelemetry.FromJson(json);
        }

        static string CheckpointJson(string base64, string sha256, double tS = 2.5) =>
            "{\"encoding\":\"deflate-base64-u8\",\"shape\":[16,16],\"data\":\"" + base64 + "\",\"sha256\":\"" + sha256 +
            "\",\"row_times_s\":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]," +
            "\"row_bearings_rad\":[0.0,0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,0.1,0.2,0.3,0.4]," +
            "\"row_origins_ne_m\":[[100.5,200.25],[1,2],[3,4],[5,6],[7,8],[9,10],[11,12],[13,14]," +
            "[15,16],[17,18],[19,20],[21,22],[23,24],[25,26],[27,28],[29,30]],\"t_s\":" +
            tS.ToString(CultureInfo.InvariantCulture) + "}";

        const string AscendingBase64 = "eAEBAAH//gABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4fICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj9AQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVpbXF1eX2BhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5ent8fX5/gIGCg4SFhoeIiYqLjI2Oj5CRkpOUlZaXmJmam5ydnp+goaKjpKWmp6ipqqusra6vsLGys7S1tre4ubq7vL2+v8DBwsPExcbHyMnKy8zNzs/Q0dLT1NXW19jZ2tvc3d7f4OHi4+Tl5ufo6err7O3u7/Dx8vP09fb3+Pn6+/z9/v+t9n+B";
        const string AscendingSha256 = "40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880";
        const string DescendingBase64 = "eAEBAAH//v/+/fz7+vn49/b19PPy8fDv7u3s6+rp6Ofm5eTj4uHg397d3Nva2djX1tXU09LR0M/OzczLysnIx8bFxMPCwcC/vr28u7q5uLe2tbSzsrGwr66trKuqqainpqWko6KhoJ+enZybmpmYl5aVlJOSkZCPjo2Mi4qJiIeGhYSDgoGAf359fHt6eXh3dnV0c3JxcG9ubWxramloZ2ZlZGNiYWBfXl1cW1pZWFdWVVRTUlFQT05NTEtKSUhHRkVEQ0JBQD8+PTw7Ojk4NzY1NDMyMTAvLi0sKyopKCcmJSQjIiEgHx4dHBsaGRgXFhUUExIREA8ODQwLCgkIBwYFBAMCAQBa+3+B";
        const string DescendingSha256 = "cd6816b77f68d70001fc3eaa4d42bdd67cb5973b3151cc5292ecc02a3daac6ab";
        const string ConstantAbBase64 = "eAFbvXpkAwDbe6sB";
        const string ConstantAbSha256 = "1080e279b51b8594a78556e2fdb4dfe9ca82ac2fbab5007de2bac4213c2e1f92";

        [Test]
        public void CheckpointUrlValidation_MirrorsWebWhitelist()
        {
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl("/api/radar/checkpoints/" + Key64('a')), Is.True);
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl("/api/radar/checkpoints/" + Key64('0')), Is.True);
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl("/api/radar/checkpoints/" + Key64('A')), Is.False, "大写 hex 拒绝（web 正则 [a-f0-9] 同款）");
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl("/api/radar/checkpoints/" + new string('a', 63)), Is.False, "63 位拒绝");
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl("/api/radar/checkpoints/../../etc/passwd"), Is.False);
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl("http://evil/api/radar/checkpoints/" + Key64('a')), Is.False, "仅同源相对路径");
            Assert.That(RadarSpokeStream.IsValidCheckpointUrl(null), Is.False);
        }

        [Test]
        public void OnEnvelopeFrame_DescriptorBroadcastAndUrlDedupe()
        {
            int descriptorEvents = 0;
            m_Stream.onDescriptor += _ => descriptorEvents++;
            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('a')));
            Assert.That(descriptorEvents, Is.EqualTo(1), "首个描述子广播");
            var descriptor = m_Stream.LatestDescriptor;
            Assert.That(descriptor.schema_version, Is.EqualTo("radar-ppi@1"));
            Assert.That(descriptor.spokes, Is.EqualTo(2048));
            Assert.That(descriptor.scan_period_s, Is.EqualTo(2.5).Within(1e-9));
            Assert.That(descriptor.seed, Is.EqualTo(7));
            Assert.That(descriptor.mount_id, Is.EqualTo("mast_top_xband"));
            Assert.That(descriptor.range_scales_nm.Length, Is.EqualTo(6));
            Assert.That(m_Stream.QueuedUrlCount, Is.EqualTo(1), "checkpoint URL 入队");

            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('a')));
            Assert.That(descriptorEvents, Is.EqualTo(1), "同 seed/周期不重复广播");
            Assert.That(m_Stream.QueuedUrlCount, Is.EqualTo(1), "同 URL 去重（内容寻址）");

            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('b')));
            Assert.That(m_Stream.QueuedUrlCount, Is.EqualTo(2), "新 checkpoint（下一整转）入队");
        }

        [Test]
        public void CheckpointPipeline_DecodesBroadcastsAndKeepsLastTwoRevolutions()
        {
            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('a'), spokes: 16, rangeM: 1388.9));
            int revolutions = 0;
            RadarSpokeFrame last = null;
            m_Stream.onRevolution += frame => { revolutions++; last = frame; };

            m_Stream.ApplyCheckpoint(CheckpointJson(AscendingBase64, AscendingSha256, 2.5));
            m_Stream.DrainResults();
            Assert.That(revolutions, Is.EqualTo(1));
            Assert.That(m_Stream.DecodedCount, Is.EqualTo(1));
            Assert.That(last.spokes, Is.EqualTo(16));
            Assert.That(last.bins, Is.EqualTo(16));
            Assert.That(last.rangeM, Is.EqualTo(1388.9).Within(1e-6), "量程从 envelope 回填（checkpoint 本体不带）");
            Assert.That(last.raster[0], Is.EqualTo((byte)0));
            Assert.That(last.raster[255], Is.EqualTo((byte)255));
            Assert.That(last.rowOriginsNeM.Length, Is.EqualTo(16));
            Assert.That(last.rowOriginsNeM[0][0], Is.EqualTo(100.5).Within(1e-9));
            Assert.That(last.rowOriginsNeM[0][1], Is.EqualTo(200.25).Within(1e-9));
            Assert.That(last.rowTimesS.Length, Is.EqualTo(16));
            Assert.That(m_Stream.Revolutions.Count, Is.EqualTo(1));

            m_Stream.ApplyCheckpoint(CheckpointJson(DescendingBase64, DescendingSha256, 5.0));
            m_Stream.DrainResults();
            Assert.That(m_Stream.Revolutions.Count, Is.EqualTo(2));
            Assert.That(m_Stream.Latest, Is.Not.Null);
            Assert.That(m_Stream.Latest.raster[0], Is.EqualTo((byte)255), "最新 = 降序栅格");

            m_Stream.ApplyCheckpoint(CheckpointJson(ConstantAbBase64, ConstantAbSha256, 7.5));
            m_Stream.DrainResults();
            Assert.That(m_Stream.Revolutions.Count, Is.EqualTo(2), "环形容量 2：第 3 转丢最旧");
            Assert.That(m_Stream.DecodedCount, Is.EqualTo(3));
            Assert.That(m_Stream.Latest.raster[0], Is.EqualTo((byte)0xAB));
            Assert.That(m_Stream.Latest.raster[200], Is.EqualTo((byte)0xAB));
            Assert.That(m_Stream.Revolutions[0].raster[0], Is.EqualTo((byte)255), "最旧 = 第 2 转（升序被逐出）");
        }

        [Test]
        public void CheckpointPipeline_RejectsBadHashAndSpokeMismatchWithoutBroadcast()
        {
            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('a'), spokes: 16));
            int revolutions = 0;
            m_Stream.onRevolution += _ => revolutions++;

            m_Stream.ApplyCheckpoint(CheckpointJson(AscendingBase64, DescendingSha256, 2.5)); // sha 失配
            m_Stream.DrainResults();
            Assert.That(revolutions, Is.EqualTo(0), "坏哈希不广播");
            Assert.That(m_Stream.RejectedCount, Is.EqualTo(1));
            Assert.That(m_Stream.Latest, Is.Null);

            // envelope spokes=16 门下喂 16 行 checkpoint 合法，随后维度门失配（web MISSING_RADAR_CHECKPOINT 同判）
            m_Stream.ApplyCheckpoint(CheckpointJson(AscendingBase64, AscendingSha256, 2.5));
            m_Stream.DrainResults();
            Assert.That(revolutions, Is.EqualTo(1));

            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('b'), spokes: 2048)); // 会话换量程档（spokes 门变 2048）
            m_Stream.ApplyCheckpoint(CheckpointJson(DescendingBase64, DescendingSha256, 5.0)); // 16 行 checkpoint
            m_Stream.DrainResults();
            Assert.That(revolutions, Is.EqualTo(1), "spoke 维度门拒绝");
            Assert.That(m_Stream.RejectedCount, Is.EqualTo(2));
        }

        [Test]
        public void OnSessionRebuilt_ClearsRingAndDedupeTable()
        {
            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('a'), spokes: 16));
            m_Stream.ApplyCheckpoint(CheckpointJson(AscendingBase64, AscendingSha256, 2.5));
            m_Stream.DrainResults();
            Assert.That(m_Stream.Revolutions.Count, Is.EqualTo(1));

            m_Stream.OnSessionRebuilt();
            Assert.That(m_Stream.Revolutions.Count, Is.EqualTo(0));
            Assert.That(m_Stream.Latest, Is.Null);
            Assert.That(m_Stream.QueuedUrlCount, Is.EqualTo(0));
            Assert.That(m_Stream.DecodedCount, Is.EqualTo(1), "累计诊断计数保留（会话代际不归零）");

            // 重建后同 URL 重新可入队（新会话同键重拉 = 同内容，无正确性代价）。
            m_Stream.OnEnvelopeFrame(EnvelopeFrame(Key64('a'), spokes: 16));
            Assert.That(m_Stream.QueuedUrlCount, Is.EqualTo(1));
        }
    }

    /// <summary>
    /// twin-bridge radar_view 词汇/效果/回显测试（2026-10-21 P0，契约 §2/§8 演进；
    /// sensor_mode 同惯例——词汇冻结 + 纯函数效果面 + state 只加字段回显）。
    /// </summary>
    public class TwinBridgeRadarViewTests
    {
        [Test]
        public void Vocabulary_FrozenFourValuesWithOffDefault()
        {
            Assert.That(TwinBridge.RadarViewValues, Is.EqualTo(new[] { "off", "overlay", "ppi", "both" }));
            Assert.That(TwinBridge.DefaultRadarView, Is.EqualTo("off"));
            foreach (string value in TwinBridge.RadarViewValues)
                Assert.That(TwinBridge.IsValidRadarView(value), Is.True, value);
            Assert.That(TwinBridge.IsValidRadarView("on"), Is.False);
            Assert.That(TwinBridge.IsValidRadarView("OVERLAY"), Is.False, "大小写敏感（sensor_mode 同款）");
            Assert.That(TwinBridge.IsValidRadarView(null), Is.False);
        }

        [Test]
        public void RadarViewEffect_PureFacetQuery()
        {
            TwinBridge.RadarViewEffect("off", out bool overlay, out bool ppi);
            Assert.That(overlay, Is.False); Assert.That(ppi, Is.False);
            TwinBridge.RadarViewEffect("overlay", out overlay, out ppi);
            Assert.That(overlay, Is.True); Assert.That(ppi, Is.False);
            TwinBridge.RadarViewEffect("ppi", out overlay, out ppi);
            Assert.That(overlay, Is.False); Assert.That(ppi, Is.True);
            TwinBridge.RadarViewEffect("both", out overlay, out ppi);
            Assert.That(overlay, Is.True); Assert.That(ppi, Is.True);
        }

        [Test]
        public void StateEcho_AdditiveFieldWithOffDefault()
        {
            // JsonUtility 恒写全字段：新字段对旧 web 宽松消费（sensor_mode/geo_fit 同惯例）。
            string json = new TwinBridgeState().ToJson();
            Assert.That(json, Does.Contain("\"radar_view\":\"off\""));
            var echo = new TwinBridgeState { radar_view = "both" };
            Assert.That(echo.ToJson(), Does.Contain("\"radar_view\":\"both\""));
            Assert.That(TwinBridgeState.FromJson(echo.ToJson()).radar_view, Is.EqualTo("both"));
        }
    }
}
