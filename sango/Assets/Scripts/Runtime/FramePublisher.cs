using System;
using System.Collections;
using NetMQ;
using NetMQ.Sockets;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Experimental.Rendering;
using System.Threading.Tasks;

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
    ///   绑定 tcp://127.0.0.1:5556。最高 10Hz 异步 GPU 读回，单任务后台 JPEG 编码。
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
        [Range(0.1f, 2f)] public float publishIntervalS = 0.1f;
        [Range(0.01f, 1f)] public float confidenceThreshold = 0.25f;
        public Camera sourceCamera;

        [Tooltip("P3-S2 机位标识（FrameMetadata.mount_id，observations-v1 §3 引用键；空 = 旧桥楼馈送）")]
        public string mountId = "";

        [Tooltip("P3-S2 捕获分辨率覆写（0 = 屏幕分辨率；桅杆馈送机位用标定表栅格 640×480）")]
        public Vector2Int overrideCaptureSize = Vector2Int.zero;

        PublisherSocket _pub;
        int _seq;
        bool _loopRunning;
        sealed class CaptureSlot
        {
            public RenderTexture Target;
            public AsyncGPUReadbackRequest Readback;
            public byte[] Pixels;
            public volatile bool Pending, Ready;
            public volatile bool Encoding;
            public double TimeS;
            public float Confidence;
        }
        sealed class EncodedFrame
        {
            public byte[] Jpeg;
            public int Width, Height, Generation;
            public double TimeS;
            public float Confidence;
        }
        CaptureSlot[] _slots;
        int _captureWidth, _captureHeight;
        volatile int _captureGeneration;
        double _lastPublishedCaptureTimeS = -1.0;
        Task<EncodedFrame> _encoder;
        Camera _captureCamera;
        Action<RenderTargetIdentifier, CommandBuffer> _captureAction;
        double _lastCaptureRealtime = -1;


        /// <summary>
        /// Local detector budget: minimum interval 1/10 s, three reusable capture slots and one encoder.
        /// GPU 读回与 JPEG 编码异步执行，
        /// 同机跑检测服务时保留渲染帧预算；线协议 multipart 格式、
        /// topic、seq 单调语义全部不变，感知宿主侧零感知（帧率敏感者按 seq/time 丢弃）。
        /// </summary>
        const float MinPublishIntervalS = 1f / 10f;

        /// <summary>是否处于发布态（编译期闸 ∨ 运行期开关 ∨ 命令行旗标）。</summary>
        public bool Active => runtimeEnabled;

        /// <summary>Inspector 勾选同步：单一布尔比较，关闸时即全部成本（spec 验收故事 5）。</summary>
        void Update()
        {
            if (runtimeEnabled && !_loopRunning) StartPublishing();
            else if (!runtimeEnabled && _loopRunning) StopPublishing();
            if (_loopRunning) EnsureCaptureTargets();
            if (_encoder != null && _encoder.IsCompleted)
            {
                var completed = _encoder;
                _encoder = null;
                try
                {
                    var frame = completed.GetAwaiter().GetResult();
                    if (_loopRunning && frame.Generation == _captureGeneration) PublishCapturedFrame(frame);
                }
                catch (Exception error) { Debug.LogWarning($"[Sango.M3] encode failed: {error.Message}"); }
            }
            if (!_loopRunning || _encoder != null || _slots == null) return;
            CaptureSlot newest = null;
            foreach (var slot in _slots)
                if (slot.Ready && (newest == null || slot.TimeS > newest.TimeS)) newest = slot;
            if (newest == null) return;
            foreach (var slot in _slots) if (slot.Ready) slot.Ready = false;
            newest.Encoding = true;
            int width = _captureWidth, height = _captureHeight, generation = _captureGeneration, quality = jpegQuality;
            double timeS = newest.TimeS;
            float confidence = newest.Confidence;
            _encoder = Task.Run(() =>
            {
                try
                {
                    // HDRP CameraCaptureBridge already supplies an unflipped intermediate in encoder row order.
                    return new EncodedFrame { Jpeg = ImageConversion.EncodeArrayToJPG(newest.Pixels,
                        GraphicsFormat.R8G8B8A8_UNorm, (uint)width, (uint)height, 0, quality),
                        Width = width, Height = height, TimeS = timeS, Generation = generation, Confidence = confidence };
                }
                finally { newest.Encoding = false; }
            });
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
            runtimeEnabled = true;
            if (_loopRunning) return;
            if (!EnsureSocket()) return;
            _loopRunning = true;
            _captureCamera = sourceCamera != null ? sourceCamera : Camera.main;
            if (_captureCamera == null) { runtimeEnabled = false; StopPublishing(); return; }
            _captureAction = CaptureScene;
            CameraCaptureBridge.enabled = true;
            CameraCaptureBridge.AddCaptureAction(_captureCamera, _captureAction);
            Debug.Log($"[Sango.M3] publishing frames to {endpoint} (topic {SangoSeamConfig.PublisherTopic})");
            Debug.Log($"[Sango.M3] capture device={SystemInfo.graphicsDeviceType} source=CameraCaptureBridge before GUI");
        }

        /// <summary>停止发布并释放 socket（回默认 OFF 态）。</summary>
        public void StopPublishing()
        {
            runtimeEnabled = false;
            _loopRunning = false;
            StopAllCoroutines();
            if (_captureAction != null) CameraCaptureBridge.RemoveCaptureAction(_captureCamera, _captureAction);
            _captureAction = null; _captureCamera = null;
            ReleaseCapture();
            if (_pub != null)
            {
                _pub.Dispose();
                _pub = null;
                Debug.Log("[Sango.M3] publisher socket closed");
            }
        }

        void OnDisable() => StopPublishing();

        void ReleaseCapture()
        {
            _captureGeneration++;
            if (_encoder != null)
            {
                // Only teardown/resize waits; normal rendering never waits for JPEG encoding.
                try { _encoder.GetAwaiter().GetResult(); }
                catch (Exception error) { Debug.LogWarning($"[Sango.M3] encode failed during teardown: {error.Message}"); }
                _encoder = null;
            }
            if (_slots != null)
            {
                // CommandBuffer readback has no request handle until its callback. Teardown runs outside rendering.
                foreach (var slot in _slots) if (slot.Pending) { AsyncGPUReadback.WaitAllRequests(); break; }
                foreach (var slot in _slots)
                {
                    slot.Target.Release();
                    if (Application.isPlaying) Destroy(slot.Target); else DestroyImmediate(slot.Target);
                }
            }
            _slots = null;
        }

        void EnsureCaptureTargets()
        {
            // P3-S2: 桅杆馈送机位按标定表栅格发布（MountCameraTable 对拍）；未覆写沿用屏幕分辨率（M3 语义零变化）。
            int width = overrideCaptureSize.x > 0 ? overrideCaptureSize.x : Screen.width;
            int height = overrideCaptureSize.y > 0 ? overrideCaptureSize.y : Screen.height;
            if (width <= 0 || height <= 0) return;
            if (_slots == null || width != _captureWidth || height != _captureHeight)
            {
                ReleaseCapture();
                _captureWidth = width; _captureHeight = height;
                _slots = new CaptureSlot[3];
                for (int i = 0; i < _slots.Length; i++)
                {
                    var target = new RenderTexture(width, height, 0, RenderTextureFormat.ARGB32);
                    target.Create();
                    _slots[i] = new CaptureSlot { Target = target, Pixels = new byte[width * height * 4] };
                }
            }
        }

        void CaptureScene(RenderTargetIdentifier sourceTarget, CommandBuffer command)
        {
            if (!_loopRunning || _slots == null) return;
            double now = Time.unscaledTimeAsDouble;
            if (_lastCaptureRealtime >= 0 && now - _lastCaptureRealtime < Mathf.Max(MinPublishIntervalS, publishIntervalS)) return;
            CaptureSlot available = null;
            foreach (var slot in _slots)
                if (!slot.Pending && !slot.Ready && !slot.Encoding) { available = slot; break; }
            if (available == null) return; // Bounded backpressure: skip captures rather than accumulating frames.
            var capture = available;
            capture.TimeS = Time.timeAsDouble;
            capture.Confidence = Mathf.Clamp(confidenceThreshold, 0.01f, 1f);
            capture.Pending = true;
            int generation = _captureGeneration;
            _lastCaptureRealtime = now;
            command.Blit(sourceTarget, capture.Target);
            command.RequestAsyncReadback(capture.Target, 0, TextureFormat.RGBA32, request =>
            {
                capture.Readback = request;
                if (generation != _captureGeneration) return;
                if (request.hasError)
                { capture.Pending = false; runtimeEnabled = false; Debug.LogWarning("[Sango.M3] GPU frame readback failed; publisher disabled"); return; }
                request.GetData<byte>().CopyTo(capture.Pixels);
                if (generation != _captureGeneration) return;
                capture.Ready = true;
                capture.Pending = false;
            });
        }

        void PublishCapturedFrame(EncodedFrame frame)
        {
            if (frame.TimeS <= _lastPublishedCaptureTimeS) return;
            int w = frame.Width, h = frame.Height;
            byte[] jpeg = frame.Jpeg;
            if (_pub == null) return; // StopPublishing 已跑（同帧 OnDisable）——丢这帧即可

            // P3-S2 位姿快照（写档见 FrameMetadata）：发布器从源相机变换读当帧
            // 场景系位姿（未加 anchor，诊断/对账用，非 georef 权威输入）。
            var camTransform = _captureCamera != null ? _captureCamera.transform : null;
            Vector3 camPosition = camTransform != null ? camTransform.position : Vector3.zero;
            Vector3 camForward = camTransform != null ? camTransform.forward : Vector3.forward;
            double poseYawDeg = camTransform != null
                ? System.Math.Atan2(camForward.x, camForward.z) * Mathf.Rad2Deg
                : 0.0;

            var metadata = FramePublisherCore.BuildMetadata(_seq, frame.TimeS, w, h, jpeg.Length, source,
                mountId, camPosition.x, camPosition.z, poseYawDeg);
            metadata.confidence_threshold = frame.Confidence;
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
            _lastPublishedCaptureTimeS = frame.TimeS;
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
