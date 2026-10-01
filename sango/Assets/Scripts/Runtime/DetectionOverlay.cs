using System;
using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子①④适配层（spec #86）：检测框叠加层，来源无关。
    /// - Phase-1 演示：ProvideGroundTruth() 从船包围盒真值出框（置信度标签 "1.0 (gt)"）。
    /// - Phase-2 接入（M9）：live 路径消费 DetectionResultConsumer 的新鲜结果——有新鲜 YOLO
    ///   结果则按 box_xyxy 像素直绘（标签 = class_name + confidence），否则回退 ground-truth
    ///   （判定走 DetectionFreshness.PreferLiveOverGroundTruth 纯函数，EditMode 已测；
    ///   协议文档：sango/Docs/contracts/detection-return-v1.md）。关闸/无消费端时恒走真值，行为不变。
    /// - 键位 B 切换（key ledger 空闲槽）；关时 OnGUI 早退，Update 仅查键——零可测成本。
    /// - 投影数学在 OverlayProjection（Sango.Vessels 纯函数，EditMode 已测）；
    ///   本类只做相机相关的 WorldToViewportPoint 收纳（8 角点 AABB）。
    /// </summary>
    public class DetectionOverlay : MonoBehaviour
    {
        [Tooltip("检测结果消费端（live 路径数据源；留空 = 启动时自动查找场景内 DetectionResultConsumer）")]
        public DetectionResultConsumer liveSource;

        [Tooltip("参与真值出框的船（根 Transform，含 Renderer 即可）")]
        public Transform[] ships = Array.Empty<Transform>();

        [Tooltip("叠加层可见性（B 切换；默认关）")]
        public bool visible;

        [Tooltip("投影相机；留空 = Camera.main（随 CameraRig 视图切换自动跟随）")]
        public Camera sourceCamera;

        [Tooltip("框外扩像素（包住船体涂装边缘）")]
        public float marginPx = 6f;

        DetectionResultConsumer _consumer;   // 自动查找缓存（只找一次，防每帧 Find 开销）
        bool _consumerSearched;
        DetectionResult _liveFrame;          // 本帧 live 结果（Update 取用，OnGUI 只读不消费队列）
        public bool HasFreshLiveResult => Consumer != null && Consumer.Active
            && DetectionFreshness.PreferLiveOverGroundTruth(_liveFrame, Time.timeAsDouble, Consumer.maxAgeS);

        /// <summary>消费端引用：Inspector 优先，否则场景内查找一次。</summary>
        DetectionResultConsumer Consumer
        {
            get
            {
                if (liveSource != null) return liveSource;
                if (!_consumerSearched)
                {
                    _consumer = FindFirstObjectByType<DetectionResultConsumer>();
                    _consumerSearched = true;
                }
                return _consumer;
            }
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.B))
            {
                visible = !visible;
                Debug.Log($"[Sango.M3] detection overlay {(visible ? "ON" : "OFF")} (B)");
            }

            // live 取用每帧恰好一次（OnGUI 同帧可多次触发，队列消费不能放 OnGUI）。
            // 消费端关闸时 TryTakeFresh 一次布尔比较即返回，真值路径成本不变。
            var consumer = Consumer;
            if (consumer == null || !consumer.Active) _liveFrame = null;
            else if (consumer.TryTakeFresh(Time.timeAsDouble, out var fresh)) _liveFrame = fresh;
        }

        void OnGUI()
        {
            if (!visible) return; // 关时零绘制
            var cam = sourceCamera != null ? sourceCamera : Camera.main;
            if (cam == null) return;

            // live/GT 判定（纯函数）：有新鲜 live 结果按像素 xyxy 直绘（渲染时刻再验一次 age，幂等）；
            // 否则回退真值——与 M3 行为逐位一致。
            bool live = HasFreshLiveResult;
            GUI.Label(new Rect(Screen.width - 260f, 20f, 250f, 24f), live ? "YOLO live" : "Ground truth demo");
            if (live)
            {
                foreach (var box in _liveFrame.detections)
                {
                    if (box?.box_xyxy == null || box.box_xyxy.Length != 4) continue;
                    var rect = Rect.MinMaxRect(box.box_xyxy[0], box.box_xyxy[1], box.box_xyxy[2], box.box_xyxy[3]);
                    GUI.Box(rect, $"{box.class_name}  {OverlayProjection.ConfidenceLabel(box.confidence, false)}");
                }
                return;
            }

            var boxes = CollectBoxes(cam, Screen.width, Screen.height);
            foreach (var box in boxes)
                GUI.Box(PixelRectFor(box, Screen.width, Screen.height),
                    $"{box.label}  {OverlayProjection.ConfidenceLabel(1f, true)}");
        }

        /// <summary>
        /// 真值出框（phase-1 数据源，spec "ProvideGroundTruth() path"）：
        /// 当前帧所有船 → DetectionResult（source="ground-truth"，confidence=1）。
        /// phase-2 把本方法换掉、其余渲染逻辑原样保留。
        /// </summary>
        public DetectionResult ProvideGroundTruth(int frameSeq, double frameTimeS)
        {
            var cam = sourceCamera != null ? sourceCamera : Camera.main;
            var boxes = cam != null ? CollectBoxes(cam, Screen.width, Screen.height) : new List<ScreenBox>();
            var detections = new DetectionResult.Box[boxes.Count];
            for (int i = 0; i < boxes.Count; i++)
            {
                var rect = PixelRectFor(boxes[i], Screen.width, Screen.height);
                detections[i] = new DetectionResult.Box
                {
                    box_xyxy = new[] { rect.xMin, rect.yMin, rect.xMax, rect.yMax },
                    class_id = 0,
                    class_name = boxes[i].label,
                    confidence = 1f,
                };
            }
            return new DetectionResult
            {
                frame_seq = frameSeq,
                frame_time_s = frameTimeS,
                source = "ground-truth",
                detections = detections,
            };
        }

        struct ScreenBox
        {
            public Vector2 vpMin, vpMax;
            public string label;
        }

        /// <summary>viewport AABB → 像素 xyxy（唯一换算点；OnGUI 与 ProvideGroundTruth 共用）。</summary>
        Rect PixelRectFor(ScreenBox box, int screenW, int screenH)
        {
            return OverlayProjection.ViewportBoxToPixelRect(box.vpMin, box.vpMax, screenW, screenH, marginPx);
        }

        List<ScreenBox> CollectBoxes(Camera cam, int screenW, int screenH)
        {
            var result = new List<ScreenBox>();
            foreach (var ship in ships)
            {
                if (ship == null) continue;
                if (!ShipViewportAabb(ship, cam, out var vpMin, out var vpMax)) continue;
                result.Add(new ScreenBox { vpMin = vpMin, vpMax = vpMax, label = ship.name });
            }
            return result;
        }

        /// <summary>世界包围盒 8 角点 → viewport AABB；无角点在相机前方（船在镜后）→ false。</summary>
        static bool ShipViewportAabb(Transform ship, Camera cam, out Vector2 vpMin, out Vector2 vpMax)
        {
            var renderers = ship.GetComponentsInChildren<Renderer>();
            vpMin = new Vector2(float.MaxValue, float.MaxValue);
            vpMax = new Vector2(float.MinValue, float.MinValue);
            bool anyInFront = false;
            foreach (var r in renderers)
            {
                if (r is ParticleSystemRenderer || r is TrailRenderer) continue;
                bool effectMesh = false;
                for (var parent = r.transform; parent != null && parent != ship; parent = parent.parent)
                    if (parent.name == "NavigationLightsRig" || parent.name == "WakeFoamRig" || parent.name == "WaterlineDecalsRig")
                    { effectMesh = true; break; }
                if (effectMesh) continue;
                var b = r.bounds;
                for (int cx = 0; cx < 2; cx++)
                for (int cy = 0; cy < 2; cy++)
                for (int cz = 0; cz < 2; cz++)
                {
                    var corner = new Vector3(
                        (cx & 1) != 0 ? b.max.x : b.min.x,
                        (cy & 1) != 0 ? b.max.y : b.min.y,
                        (cz & 1) != 0 ? b.max.z : b.min.z);
                    var v = cam.WorldToViewportPoint(corner);
                    if (v.z <= 0f) continue; // 镜后角点不参与（防翻转假框）
                    anyInFront = true;
                    vpMin = Vector2.Min(vpMin, new Vector2(v.x, v.y));
                    vpMax = Vector2.Max(vpMax, new Vector2(v.x, v.y));
                }
            }
            return anyInFront && vpMin.x <= vpMax.x && vpMin.y <= vpMax.y;
        }
    }
}
