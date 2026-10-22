using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;
using UnityEngine;

namespace Sango
{
    /// <summary>envelope radar_scans[*] 的 Unity 消费子集（compact-v1 投影后形状，
    /// gui_server/radar_transport.py project_compact_scans：chunk 剥除、checkpoint 换
    /// 内容寻址 URL 引用）。JsonUtility 未声明字段静默跳过（ColavTelemetry 同语义）。</summary>
    [Serializable]
    public class RadarScanEntry
    {
        public int vessel_id;
        public string sensor_label;
        public double t_s;
        public RadarShadowVideo shadow_video;

        /// <summary>P1 检测滑窗回波（radar_scan.py display_returns；RadarDisplayReturn
        /// 子集，协方差嵌套数组静默跳过）——经 onDisplayReturns 广播给 RadarTargetMarkers。</summary>
        public RadarDisplayReturn[] display_returns;
    }

    /// <summary>shadow_video 子集：维度/进度元数据 + checkpoint 引用（大流量不走 WS 内联）。</summary>
    [Serializable]
    public class RadarShadowVideo
    {
        public double range_m;
        public int spokes;
        public int spoke_seq_end;
        public RadarCheckpointRef checkpoint;
    }

    /// <summary>checkpoint REST 引用（radar_transport.py:33 同形：/api/radar/checkpoints/{64hex}）。</summary>
    [Serializable]
    public class RadarCheckpointRef
    {
        public string url;
        public string checkpoint_key;
    }

    /// <summary>
    /// envelope 顶层键 radar_ppi（radar-ppi@1，sensing.py ppi_descriptor）的 Unity 表现层
    /// 子集。blind_sectors_deg 为嵌套数组（JsonUtility 不支持，本 DTO 不声明）——
    /// ReceiveLoop 侧 RadarOverlayMath.ParseBlindSectors 从信封原文解析后经
    /// ColavTelemetry.radarPpiBlindSectors 携带、onBlindSectors 广播（P1 盲区可视化）；
    /// clutter_*/snr_model（web 端杂波重生成与 GAIN/SEA/RAIN 档位，P2 雷达屏再进）。
    /// </summary>
    [Serializable]
    public class RadarPpiDescriptor
    {
        public string schema_version;
        public string sensor_label;
        public string mount_id;
        public int seed;
        public int spokes;
        public double scan_period_s;
        public double range_scale_nm;
        public double blind_ring_m;
        public double[] range_scales_nm;
        public double sea_state_beaufort;
    }

    /// <summary>checkpoint REST 文档（radar_video.py step:136-144 checkpoint 形状）。
    /// row_origins_ne_m 为嵌套数组，JsonUtility 不支持，经 RadarSpokeDecoder.ParseRowOrigins 解析。</summary>
    [Serializable]
    public class RadarCheckpointDocument
    {
        public string encoding;
        public int[] shape;
        public string data;
        public string sha256;
        public double[] row_times_s;
        public double[] row_bearings_rad;
        public double t_s;
    }

    /// <summary>一转解码产物：raster（spokes×bins u8 行主序，row=方位、col=距离 bin）+ 行元数据。
    /// rangeM 来自 envelope shadow_video.range_m（checkpoint 本体不带量程）。</summary>
    public sealed class RadarSpokeFrame
    {
        public byte[] raster;
        public int spokes;
        public int bins;
        public double rangeM;
        public double tS;
        public double[] rowTimesS;
        public double[] rowBearingsRad;
        public double[][] rowOriginsNeM;
    }

    /// <summary>
    /// P0 雷达 spoke 通道组件（00-REPORT §2.2/§6 P0）：envelope radar_scans →
    /// 内容寻址 checkpoint REST 拉取 → RadarSpokeDecoder 解码 → 环形保留最近 2 转 +
    /// 广播给订阅者（P1 水面余辉盘 / P2 独立雷达屏的消费口）。与 web RadarVideoBuffer
    /// （radar-video.js）同源同节奏：同一 checkpoint、同一 sim_time——Unity 屏与 web 屏
    /// 逐 spoke 可对拍即本通道的保真验收手段。
    /// - 帧由 TwinSessionDriver 主线程 hook 转发（DrainInbox 接受帧后）；checkpoint
    ///   URL 严格校验（^/api/radar/checkpoints/[a-f0-9]{64}$，radar-video.js:35 同式），
    ///   同 URL 只拉一次（内容寻址：同键同内容），超过 64 键清表重钉（后端缓存本就只保 16）。
    /// - 线程模型同 TwinSessionDriver/OwnshipRelayLoop：单后台 worker TwinRest.Get 同步
    ///   拉取 + JsonUtility/解码纯 CPU（后台线程可用），产物 ConcurrentQueue 入队，
    ///   主线程 Update 排空进环形 + 广播（CheckpointFetcher 惰性起，首个 URL 才建线程）。
    /// - live 专用：replay window 的 shadow_video.checkpoint 为 $radar_checkpoint 键引用
    ///   （radar_transport.py project_radar_window），非 URL——本组件对其不动作，
    ///   replay 侧接线属 ReplayWindowAdapter 所有者的后续段。
    /// </summary>
    public class RadarSpokeStream : MonoBehaviour
    {
        [Tooltip("checkpoint REST 基址（TwinWs/TwinSessionDriver 同一配置源；driver hook 建流时注入）")]
        public string backendBase = SangoSeamConfig.TwinBackendBase;

        /// <summary>环形容量：最近 2 转（当前 + 前一；P2 尾迹如需更深受消费侧再扩）。</summary>
        const int RingCapacity = 2;

        /// <summary>同键去重表上限：超出整表清空（内容寻址重拉无正确性代价，后端缓存 16 同量级）。</summary>
        const int FetchedKeyCap = 64;

        readonly Queue<RadarSpokeFrame> m_Revolutions = new Queue<RadarSpokeFrame>(RingCapacity);
        readonly HashSet<string> m_QueuedUrls = new HashSet<string>();
        readonly ConcurrentQueue<string> m_FetchQueue = new ConcurrentQueue<string>();
        readonly ConcurrentQueue<RadarSpokeFrame> m_Results = new ConcurrentQueue<RadarSpokeFrame>();
        Thread m_FetchThread;
        CancellationTokenSource m_FetchCancel;

        // envelope 侧最新量程/维度（main 线程写，DrainResults 读——同线程，无竞争）
        double m_LatestRangeM;
        int m_ExpectedSpokes;

        // 上次广播的盲扇区表（值比较去重；envelope 每帧携带同值，广播只在变化时）
        float[][] m_LastBlindSectors;

        int m_DecodedCount, m_RejectedCount, m_FetchErrors;

        /// <summary>一转解码完成（主线程，每整转一次；P1/P2 表现层订阅口）。</summary>
        public event Action<RadarSpokeFrame> onRevolution;

        /// <summary>envelope radar_ppi 描述子到达/变化（主线程；scan_period 供相位函数）。</summary>
        public event Action<RadarPpiDescriptor> onDescriptor;

        /// <summary>P1 检测滑窗到达（主线程，每 envelope 帧一次；radar_x 优先帧，
        /// returns=null/空=本帧无检测）。latestTs = 滑窗内最新回波时刻（过期门用）。</summary>
        public event Action<RadarDisplayReturn[], double> onDisplayReturns;

        /// <summary>P1 盲扇区表变化（主线程；[[center_rel_bow_deg, half_width_deg],…]，
        /// null = 信封无 radar_ppi 键，空 = 后端声明无遮挡）。</summary>
        public event Action<float[][]> onBlindSectors;

        /// <summary>环形快照（旧→新，≤2 转）；无数据为空。</summary>
        public IReadOnlyList<RadarSpokeFrame> Revolutions => Array.AsReadOnly(m_Revolutions.ToArray());

        /// <summary>最新一转（未解码任何 checkpoint 时 null）。</summary>
        public RadarSpokeFrame Latest => m_Revolutions.Count > 0 ? PeekNewest() : null;

        /// <summary>最近一次 envelope radar_ppi（未携带过 null）。</summary>
        public RadarPpiDescriptor LatestDescriptor { get; private set; }

        public int DecodedCount => m_DecodedCount;
        public int RejectedCount => m_RejectedCount;
        public int FetchErrorCount => m_FetchErrors;

        /// <summary>已入队（去重后）checkpoint URL 数（诊断/EditMode 断言面）。</summary>
        public int QueuedUrlCount => m_QueuedUrls.Count;

        /// <summary>单行诊断（HUD/日志同款式；P0 验收对拍 web __dtVpLogInfo 的 spoke 维度面）。</summary>
        public string Status
        {
            get
            {
                var latest = Latest;
                return "radar stream " + (latest != null
                    ? $"revs={m_DecodedCount} {latest.spokes}x{latest.bins} range={latest.rangeM:0.#}m t={latest.tS:0.00}s"
                    : $"revs=0 pending={m_FetchQueue.Count} rejected={m_RejectedCount} fetchErrors={m_FetchErrors}");
            }
        }

        RadarSpokeFrame PeekNewest()
        {
            RadarSpokeFrame newest = null;
            foreach (var frame in m_Revolutions) newest = frame; // Queue 无尾读，环形恒 ≤2 走一遍
            return newest;
        }

        // ── 数据面：envelope 帧（主线程；TwinSessionDriver hook 转发） ─────────────

        /// <summary>
        /// 消费一帧 compact envelope：拾取 radar_scans 内首个 radar_x 的 checkpoint 引用
        /// （校验通过才入拉取队列，同 URL 只入一次）；radar_ppi 描述子变化即广播。
        /// </summary>
        public void OnEnvelopeFrame(ColavTelemetry frame)
        {
            if (frame == null) return;
            if (frame.radar_ppi != null && frame.radar_ppi.spokes > 0)
            {
                bool changed = LatestDescriptor == null
                    || LatestDescriptor.seed != frame.radar_ppi.seed
                    || LatestDescriptor.scan_period_s != frame.radar_ppi.scan_period_s;
                LatestDescriptor = frame.radar_ppi;
                if (changed) onDescriptor?.Invoke(LatestDescriptor);
            }
            // P1 盲扇区（ReceiveLoop 原文解析携带；值比较去重，变化才广播）
            if (!SameBlindSectors(frame.radarPpiBlindSectors, m_LastBlindSectors))
            {
                m_LastBlindSectors = frame.radarPpiBlindSectors;
                onBlindSectors?.Invoke(m_LastBlindSectors);
            }
            if (frame.radar_scans == null) return;
            RadarScanEntry chosen = null;
            foreach (var scan in frame.radar_scans)
            {
                if (scan == null) continue;
                bool usable = scan.shadow_video?.checkpoint != null || scan.display_returns != null;
                if (!usable) continue;
                if (chosen == null || (PreferRadarX(scan) && !PreferRadarX(chosen))) chosen = scan;
            }
            // P1 检测滑窗：与 checkpoint 拉取共用同一 chosen 帧（radar_x 优先；无检测帧
            // 传 null/空——消费侧过期门收标记，"遮挡目标正确消失"的帧面）。
            RadarDisplayReturn[] returns = chosen?.display_returns;
            double latest = double.NegativeInfinity;
            if (returns != null)
                foreach (var item in returns)
                    if (item != null && item.t_s > latest) latest = item.t_s;
            onDisplayReturns?.Invoke(returns, latest);
            if (chosen?.shadow_video?.checkpoint == null) return;
            var video = chosen.shadow_video;
            if (video.spokes > 0) m_ExpectedSpokes = video.spokes; // checkpoint 维度一致性门（web MISSING_RADAR_CHECKPOINT 同判；worker 读允许一转陈旧）
            if (video.range_m > 0) m_LatestRangeM = video.range_m;
            string url = video.checkpoint.url;
            if (!IsValidCheckpointUrl(url) || m_QueuedUrls.Contains(url)) return;
            if (m_QueuedUrls.Count >= FetchedKeyCap) m_QueuedUrls.Clear();
            m_QueuedUrls.Add(url);
            m_FetchQueue.Enqueue(url);
            EnsureFetchWorker();
        }

        /// <summary>拾取过滤：radar_x 优先（web buildPpiModel 同判），否则首个带 checkpoint 的扫描。</summary>
        static bool PreferRadarX(RadarScanEntry scan) => scan != null && scan.sensor_label == "radar_x";

        /// <summary>盲扇区表值比较（envelope 每帧同值去重；元素级，表恒小）。</summary>
        static bool SameBlindSectors(float[][] a, float[][] b)
        {
            if (ReferenceEquals(a, b)) return true;
            if (a == null || b == null || a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++)
            {
                var pa = a[i];
                var pb = b[i];
                if (ReferenceEquals(pa, pb)) continue;
                if (pa == null || pb == null || pa.Length != pb.Length) return false;
                for (int j = 0; j < pa.Length; j++)
                    if (!Mathf.Approximately(pa[j], pb[j])) return false;
            }
            return true;
        }

        /// <summary>checkpoint URL 白名单（radar-video.js:35 正则同语义：/api/radar/checkpoints/ + 64 位小写 hex）。</summary>
        public static bool IsValidCheckpointUrl(string url)
        {
            if (string.IsNullOrEmpty(url)) return false;
            const string prefix = "/api/radar/checkpoints/";
            if (!url.StartsWith(prefix, StringComparison.Ordinal)) return false;
            if (url.Length != prefix.Length + 64) return false;
            for (int i = prefix.Length; i < url.Length; i++)
            {
                char c = url[i];
                bool hex = c >= '0' && c <= '9' || c >= 'a' && c <= 'f';
                if (!hex) return false;
            }
            return true;
        }

        /// <summary>会话重建（seq 倒退/TwinSessionDriver Rebuild）：清环 + 清去重表，等待新会话 checkpoint。</summary>
        public void OnSessionRebuilt()
        {
            m_Revolutions.Clear();
            m_QueuedUrls.Clear();
            m_ExpectedSpokes = 0;
            m_LatestRangeM = 0;
            m_LastBlindSectors = null; // 新会话首批盲扇区表重新广播
        }

        // ── checkpoint 拉取 worker（后台线程） ─────────────────────────────────────

        void EnsureFetchWorker()
        {
            if (!isActiveAndEnabled) return; // EditMode 直调禁用态：只入队不起线程（测试确定性）
            if (m_FetchThread != null && m_FetchThread.IsAlive) return;
            m_FetchCancel = new CancellationTokenSource();
            var cancellation = m_FetchCancel.Token;
            string backend = backendBase; // 代际快照（worker 不追配置变化，重建走 OnSessionRebuilt）
            m_FetchThread = new Thread(() => FetchLoop(backend, cancellation))
                { IsBackground = true, Name = "Sango.RadarSpokeStream" };
            m_FetchThread.Start();
        }

        /// <summary>
        /// 后台 worker：URL 队列 → TwinRest.Get（同步阻塞 15s 上限，仅本线程）→
        /// ApplyCheckpoint 解码入结果队列。失败节流告警（前 3 + 每 100 次，OwnshipRelayLoop 同款），
        /// 丢一个 checkpoint 不重试（下一整转自然有新键）。空队 100ms 轮询。
        /// </summary>
        void FetchLoop(string backend, CancellationToken cancellation)
        {
            while (!cancellation.IsCancellationRequested)
            {
                if (!m_FetchQueue.TryDequeue(out string url))
                {
                    if (cancellation.WaitHandle.WaitOne(TimeSpan.FromMilliseconds(100))) break;
                    continue;
                }
                try
                {
                    ApplyCheckpoint(TwinRest.Get(backend, url));
                }
                catch (Exception error)
                {
                    m_FetchErrors++;
                    if (m_FetchErrors <= 3 || m_FetchErrors % 100 == 0)
                        Debug.LogWarning($"[Sango.RadarStream] checkpoint fetch failed (#{m_FetchErrors}) {url}: {error.Message}");
                }
            }
        }

        /// <summary>
        /// checkpoint JSON → 解码产物入结果队列（线程安全：worker 调；EditMode 测试直调）。
        /// 拒绝路径（形状/哈希/维度门不符）计数不抛——坏 checkpoint 不允许炸通道。
        /// </summary>
        public void ApplyCheckpoint(string json)
        {
            RadarCheckpointDocument document = null;
            RadarSpokeFrame frame;
            try
            {
                document = JsonUtility.FromJson<RadarCheckpointDocument>(json);
                var raster = RadarSpokeDecoder.DecodeVideo(document.encoding, document.shape, document.data, document.sha256);
                int spokes = document.shape[0], bins = document.shape[1];
                if (m_ExpectedSpokes > 0 && spokes != m_ExpectedSpokes)
                    throw new InvalidOperationException("radar spokes mismatch vs envelope");
                frame = new RadarSpokeFrame
                {
                    raster = raster,
                    spokes = spokes,
                    bins = bins,
                    tS = document.t_s,
                    rowTimesS = document.row_times_s,
                    rowBearingsRad = document.row_bearings_rad,
                    rowOriginsNeM = RadarSpokeDecoder.ParseRowOrigins(json),
                };
            }
            catch (Exception error)
            {
                m_RejectedCount++;
                Debug.LogWarning($"[Sango.RadarStream] checkpoint rejected (#{m_RejectedCount}): {error.Message}");
                return;
            }
            m_Results.Enqueue(frame);
        }

        // ── 主线程消费：结果出队 → 环形 + 广播 ────────────────────────────────────

        void Update() => DrainResults();

        /// <summary>排空解码产物（主线程；Update 驱动，EditMode 测试直调）：量程回填
        /// （envelope range_m）→ 环形进位（超 2 转丢最旧）→ onRevolution 广播 + 维度登记日志。</summary>
        public void DrainResults()
        {
            while (m_Results.TryDequeue(out var frame))
            {
                if (frame.rowTimesS != null && frame.rowTimesS.Length != frame.spokes)
                    frame.rowTimesS = null; // 行元数据维度门：不符即弃该面（raster 本体已钉）
                frame.rangeM = m_LatestRangeM;
                m_Revolutions.Enqueue(frame);
                while (m_Revolutions.Count > RingCapacity) m_Revolutions.Dequeue();
                m_DecodedCount++;
                // P0 验收面（00-REPORT §6）：Console 打印 spoke 维度，与 web __dtVpLogInfo 对拍。
                Debug.Log($"[Sango.RadarStream] revolution #{m_DecodedCount} spokes={frame.spokes} bins={frame.bins} " +
                          $"range={frame.rangeM:0.#}m t={frame.tS:0.00}s rows={frame.rowOriginsNeM?.Length ?? 0}");
                onRevolution?.Invoke(frame);
            }
        }

        void OnDisable() => StopFetchWorker();

        void StopFetchWorker()
        {
            if (m_FetchCancel != null) { try { m_FetchCancel.Cancel(); } catch (ObjectDisposedException) { } }
            if (m_FetchThread != null && m_FetchThread.IsAlive && !m_FetchThread.Join(500))
                Debug.LogWarning("[Sango.RadarStream] fetch worker did not exit within 0.5s");
            m_FetchThread = null;
            if (m_FetchCancel != null) { m_FetchCancel.Dispose(); m_FetchCancel = null; }
        }
    }
}
