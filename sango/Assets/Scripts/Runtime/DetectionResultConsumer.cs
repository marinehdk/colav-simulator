using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Threading;
using NetMQ;
using NetMQ.Sockets;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M9 回传消费端适配层（detection-return-v1.md）：ZeroMQ SUB 订阅检测结果，默认 OFF。
    /// - 关闸零开销：runtimeEnabled=false 不建 socket、不起线程、不进队列；Update 仅布尔比较
    ///   （先例 FramePublisher 关闸模式；本组件用后台线程替代协程——NetMQ socket 单线程属主）。
    /// - 开闸路径与发布器同一面闸（SangoSeamConfig.ConsumerCliFlag == PublisherCliFlag，
    ///   seam 总闸一处开闸两侧同使能）；等价路径：Inspector 勾 runtimeEnabled 或调 StartConsumer()。
    /// - 线程模型：后台线程持有 SUB socket → 解析 JSON（JsonUtility 支持后台线程）→
    ///   ConcurrentQueue 入队 → 主线程 TryTakeFresh 排空取最新；新鲜度判定走 DetectionFreshness
    ///   纯函数（seq 连续 + age 窗），本类不含判定逻辑。
    /// - 不向主线程抛异常：connect/recv/解析失败一律降级为日志；停止时 Join(1s) 收线程。
    /// - 线上协议：2 段 multipart [topic "sango.detection"][DetectionResult JSON]，
    ///   连接 tcp://127.0.0.1:5557（服务端 PUB bind）。
    /// </summary>
    public class DetectionResultConsumer : MonoBehaviour
    {
        [Tooltip("运行期开关；默认关（与 PublisherEnabled 同语义）。Play 中勾选/取消即启停")]
        public bool runtimeEnabled = false;

        [Tooltip("SUB 连接端点（检测服务 PUB 绑定地址，见 SangoSeamConfig.DetectionEndpoint）")]
        public string endpoint = SangoSeamConfig.DetectionEndpoint;

        [Tooltip("订阅主题（消息第 1 段，ZMQ SUB 过滤键）")]
        public string topic = SangoSeamConfig.DetectionTopic;

        [Tooltip("结果新鲜度窗口（秒）：age 超窗按陈旧丢弃，渲染回退 ground-truth")]
        public double maxAgeS = DetectionFreshness.MaxAgeS;

        /// <summary>队列积压上限：主线程长期不取用时丢最旧，防无界增长。</summary>
        const int QueueCap = 64;

        ConcurrentQueue<DetectionResult> _inbox;
        Thread _worker;
        volatile bool _running;
        int _lastSeq = -1;
        long _rxCount;

        /// <summary>是否处于消费态（运行期开关 ∨ 命令行旗标）。</summary>
        public bool Active => _running;

        /// <summary>后台线程累计收到的合法结果条数（诊断用）。</summary>
        public long RxCount => Interlocked.Read(ref _rxCount);

        /// <summary>Inspector 勾选同步：关闸时一次布尔比较即全部成本（对齐 FramePublisher.Update）。</summary>
        void Update()
        {
            if (runtimeEnabled && !_running) StartConsumer();
            else if (!runtimeEnabled && _running) StopConsumer();
        }

        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == SangoSeamConfig.ConsumerCliFlag)
                {
                    runtimeEnabled = true;
                    Debug.Log($"[Sango.M9] consumer enabled via {SangoSeamConfig.ConsumerCliFlag}");
                    break;
                }
            }
        }

        /// <summary>开启消费线程（幂等：线程已在跑则忽略）。</summary>
        public void StartConsumer()
        {
            runtimeEnabled = true;
            if (_running) return;
            if (_worker != null && _worker.IsAlive) return;
            _inbox = new ConcurrentQueue<DetectionResult>();
            _lastSeq = -1;
            _running = true;
            _worker = new Thread(ReceiveLoop) { IsBackground = true, Name = "Sango.DetectionResultConsumer" };
            _worker.Start();
        }

        /// <summary>停消费线程并等其退出（recv 200ms tick，Join 上限 1s；回默认 OFF 态）。</summary>
        public void StopConsumer()
        {
            runtimeEnabled = false;
            bool wasRunning = _running;
            _running = false;
            if (_worker != null)
            {
                if (_worker.IsAlive && !_worker.Join(1000))
                {
                    Debug.LogWarning("[Sango.M9] consumer thread did not exit within 1s");
                }
                else _worker = null;
            }
            _inbox = null;
            if (wasRunning)
                Debug.Log($"[Sango.M9] consumer stopped (rx={Interlocked.Read(ref _rxCount)})");
        }

        void OnDisable() => StopConsumer();

        /// <summary>
        /// 主线程取用：排空队列取最新一条，过 DetectionFreshness（seq 连续 + age 窗）。
        /// 关闸或队列空即 false——关闸成本 = 一次布尔比较。
        /// </summary>
        public bool TryTakeFresh(double nowS, out DetectionResult fresh)
        {
            fresh = null;
            if (!_running || _inbox == null) return false;

            DetectionResult newest = null;
            while (_inbox.TryDequeue(out var item))
            {
                if (item != null && DetectionFreshness.IsNewer(item.frame_seq, _lastSeq)
                    && DetectionFreshness.IsFresh(nowS, item.frame_time_s, maxAgeS)
                    && (newest == null || item.frame_seq > newest.frame_seq)) newest = item;
            }
            if (newest == null) return false;
            if (!DetectionFreshness.IsNewer(newest.frame_seq, _lastSeq)) return false;
            if (!DetectionFreshness.IsFresh(nowS, newest.frame_time_s, maxAgeS)) return false;

            _lastSeq = newest.frame_seq;
            fresh = newest;
            return true;
        }

        /// <summary>后台线程主体：SUB connect → 循环收 2 段消息 → 解析入队。socket 仅本线程触碰。</summary>
        void ReceiveLoop()
        {
            var inbox = _inbox;
            long rx = 0;
            try
            {
                using (var sub = new SubscriberSocket())
                {
                    sub.Options.ReceiveHighWatermark = 30; // 与发布端 HWM 对称，掉线不积压
                    sub.Subscribe(topic);
                    sub.Connect(endpoint);
                    Debug.Log($"[Sango.M9] consumer subscribed {endpoint} (topic {topic})");

                    while (_running)
                    {
                        List<string> parts = null;
                        if (!sub.TryReceiveMultipartStrings(TimeSpan.FromMilliseconds(200), ref parts)) continue;
                        var result = ParseMessage(parts);
                        if (result == null) continue;
                        rx++;
                        Interlocked.Exchange(ref _rxCount, rx);
                        while (inbox.Count >= QueueCap && inbox.TryDequeue(out _)) { }
                        inbox.Enqueue(result);
                    }
                }
            }
            catch (Exception e)
            {
                if (_running)
                    Debug.LogError($"[Sango.M9] consumer thread exited: {e.GetType().Name} {e.Message}");
            }
            finally { runtimeEnabled = false; _running = false; }
        }

        /// <summary>[topic][DetectionResult JSON] → 结果；段数/topic 不符或 JSON 损坏 → null（丢弃）。</summary>
        DetectionResult ParseMessage(List<string> parts)
        {
            if (parts == null || parts.Count != 2 || parts[0] != topic) return null;
            try
            {
                var result = DetectionResult.FromJsonStrict(parts[1]);
                return DetectionFreshness.IsWellFormed(result) ? result : null;
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Sango.M9] detection JSON parse failed: {e.GetType().Name} {e.Message}");
                return null;
            }
        }
    }
}
