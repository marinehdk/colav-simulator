using System;
using System.Collections;
using NetMQ;
using NetMQ.Sockets;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子②适配层（spec #86）：ZeroMQ PUB 帧发布器，默认 OFF。
    /// - 关闸零开销：无订阅者时不起 socket、不起协程；Update 仅一次布尔比较（无可测成本，验收故事 5）。
    /// - 开闸路径（三选一，均不改变编译期默认 SangoSeamConfig.PublisherEnabled=false）：
    ///   a) Inspector 勾/取消勾 runtimeEnabled（Update 闸每帧同步启停）；
    ///   b) 运行时调 StartPublishing()/StopPublishing()；
    ///   c) 播放器命令行带 --sango-publisher（验收探针标准路径，见 frame-publisher-v1.md）。
    /// - 线上协议：3 段 multipart [topic "sango.frame"][FrameMetadata JSON][JPEG 字节]，
    ///   绑定 tcp://127.0.0.1:5556。逐帧全屏 ReadPixels→EncodeToJPG(60)。
    /// - 不向渲染循环抛异常：socket 建立失败、发送超时/丢帧、读屏失败全部降级为日志
    ///   （TrySend 超时 100ms；订阅端掉线只是丢帧，绝不阻塞/炸出协程）。
    /// - NetMQ（LGPL-3.0）/NaCl/AsyncIO（MPL-2.0）以未修改 dll 形式随 Assets/Plugins/NetMQ 分发
    ///   （许可证全文同目录）。
    /// </summary>
    public class FramePublisher : MonoBehaviour
    {
        [Tooltip("运行期开关；默认 = SangoSeamConfig.PublisherEnabled（编译期总闸，恒 false）。Play 中勾选/取消即启停")]
        public bool runtimeEnabled = SangoSeamConfig.PublisherEnabled;

        [Tooltip("PUB 绑定端点（默认 tcp://127.0.0.1:5556，见 SangoSeamConfig）")]
        public string endpoint = SangoSeamConfig.PublisherEndpoint;

        [Tooltip("JPEG 编码质量（0-100）")]
        [Range(1, 100)] public int jpegQuality = 60;

        [Tooltip("发布源标识（FrameMetadata.source）")]
        public string source = "sango";

        PublisherSocket _pub;
        int _seq;
        bool _loopRunning;

        /// <summary>是否处于发布态（编译期闸 ∨ 运行期开关 ∨ 命令行旗标）。</summary>
        public bool Active => runtimeEnabled;

        /// <summary>Inspector 勾选同步：单一布尔比较，关闸时即全部成本（spec 验收故事 5）。</summary>
        void Update()
        {
            if (runtimeEnabled && !_loopRunning) StartPublishing();
            else if (!runtimeEnabled && _loopRunning) StopPublishing();
        }

        void Start()
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == SangoSeamConfig.PublisherCliFlag)
                {
                    runtimeEnabled = true;
                    Debug.Log($"[Sango.M3] publisher enabled via {SangoSeamConfig.PublisherCliFlag}");
                    break;
                }
            }
        }

        /// <summary>开启发布循环（幂等：循环已在跑则忽略；bind 失败仅告警降级）。</summary>
        public void StartPublishing()
        {
            if (_loopRunning) return;
            if (!EnsureSocket()) return;
            _loopRunning = true;
            StartCoroutine(PublishLoop());
            Debug.Log($"[Sango.M3] publishing frames to {endpoint} (topic {SangoSeamConfig.PublisherTopic})");
        }

        /// <summary>停止发布并释放 socket（回默认 OFF 态）。</summary>
        public void StopPublishing()
        {
            _loopRunning = false;
            StopAllCoroutines();
            if (_pub != null)
            {
                _pub.Dispose();
                _pub = null;
                Debug.Log("[Sango.M3] publisher socket closed");
            }
        }

        void OnDisable() => StopPublishing();

        IEnumerator PublishLoop()
        {
            while (_loopRunning && Active)
            {
                yield return new WaitForEndOfFrame(); // 屏幕已渲完，ReadPixels 拿到完整帧
                try
                {
                    PublishOnce();
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[Sango.M3] publish frame failed: {e.GetType().Name} {e.Message}");
                }
            }
        }

        void PublishOnce()
        {
            int w = Screen.width, h = Screen.height;
            if (w <= 0 || h <= 0) return; // 无有效表面（如 batchmode）——静默跳帧，避免告警风暴

            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0f, 0f, w, h), 0, 0);
            tex.Apply();
            byte[] jpeg = tex.EncodeToJPG(jpegQuality);
            Destroy(tex);

            if (_pub == null) return; // StopPublishing 已跑（同帧 OnDisable）——丢这帧即可

            var metadata = FramePublisherCore.BuildMetadata(_seq, Time.timeAsDouble, w, h, jpeg.Length, source);
            var message = new NetMQMessage();
            message.Append(SangoSeamConfig.PublisherTopic);            // 段1：主题（SUB 过滤键）
            message.Append(FramePublisherCore.MetadataToJson(metadata)); // 段2：元数据 JSON
            message.Append(jpeg);                                       // 段3：JPEG 字节

            // TrySend 带超时：订阅端 HWM 满 / socket 异常 = 丢帧 + 告警，绝不阻塞渲染循环
            if (!_pub.TrySendMultipartMessage(TimeSpan.FromMilliseconds(100), message))
            {
                Debug.LogWarning("[Sango.M3] frame dropped (subscriber slow or socket busy)");
                return;
            }

            _seq++;
            if (_seq % 30 == 1)
                Debug.Log($"[Sango.M3] frame seq={metadata.frame_seq} {w}x{h} jpeg={jpeg.Length}B");
        }

        bool EnsureSocket()
        {
            if (_pub != null) return true;
            try
            {
                _pub = new PublisherSocket();
                _pub.Options.SendHighWatermark = 30; // 订阅端掉线时不无限积压
                _pub.Bind(endpoint);
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError($"[Sango.M3] publisher bind {endpoint} failed: {e.GetType().Name} {e.Message} (publisher disabled)");
                _pub?.Dispose();
                _pub = null;
                runtimeEnabled = false; // Update 闸不再重试，直至人为重新勾选
                return false;
            }
        }
    }
}
