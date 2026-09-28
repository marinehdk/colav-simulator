using System;
using System.Collections;
using NetMQ;
using NetMQ.Sockets;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子②适配层（spec #86）：ZeroMQ PUB 帧发布器，默认 OFF。
    /// - 关闸零开销：OnEnable 早退——不建 socket、不起协程、Update 无逻辑（验收故事 5）。
    /// - 开闸路径（三选一，均不改编译期默认 SangoSeamConfig.PublisherEnabled=false）：
    ///   a) Inspector 勾 runtimeEnabled；b) 运行时调 StartPublishing()；
    ///   c) 播放器命令行带 --sango-publisher（验收探针标准路径，见 frame-publisher-v1.md）。
    /// - 线上协议：3 段 multipart [topic "sango.frame"][FrameMetadata JSON][JPEG 字节]，
    ///   绑定 tcp://127.0.0.1:5556。逐帧全屏 ReadPixels→EncodeToJPG(60)。
    /// - NetMQ（LGPL-3.0）/AsyncIO（MPL-2.0）以未修改 dll 形式随 Assets/Plugins/NetMQ 分发
    ///   （许可证全文同目录）。socket 建立失败仅告警降级，绝不拖垮宿主场景。
    /// </summary>
    public class FramePublisher : MonoBehaviour
    {
        [Tooltip("运行期开关；默认 = SangoSeamConfig.PublisherEnabled（编译期总闸，恒 false）")]
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
            if (Active) StartPublishing();
        }

        /// <summary>开启发布循环（幂等：循环已在跑则忽略）。</summary>
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
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0f, 0f, w, h), 0, 0);
            tex.Apply();
            byte[] jpeg = tex.EncodeToJPG(jpegQuality);
            Destroy(tex);

            var metadata = FramePublisherCore.BuildMetadata(_seq, Time.timeAsDouble, w, h, jpeg.Length, source);
            var message = new NetMQMessage();
            message.Append(SangoSeamConfig.PublisherTopic);            // 段1：主题（SUB 过滤键）
            message.Append(FramePublisherCore.MetadataToJson(metadata)); // 段2：元数据 JSON
            message.Append(jpeg);                                       // 段3：JPEG 字节
            _pub.SendMultipartMessage(message);

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
                runtimeEnabled = false;
                return false;
            }
        }
    }
}
