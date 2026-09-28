using System;
using System.Collections.Generic;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子①④适配层（spec #86）：检测框叠加层，来源无关。
    /// - Phase-1 演示：ProvideGroundTruth() 从船包围盒真值出框（置信度标签 "1.0 (gt)"）。
    /// - Phase-2 接入：喂 DetectionResult（后端/YOLO 回传的契约结构）即渲染，渲染路径零改动。
    /// - 键位 B 切换（key ledger 空闲槽）；关时 OnGUI 早退，Update 仅查键——零可测成本。
    /// - 投影数学在 OverlayProjection（Sango.Vessels 纯函数，EditMode 已测）；
    ///   本类只做相机相关的 WorldToViewportPoint 收纳（8 角点 AABB）。
    /// </summary>
    public class DetectionOverlay : MonoBehaviour
    {
        [Tooltip("参与真值出框的船（根 Transform，含 Renderer 即可）")]
        public Transform[] ships = Array.Empty<Transform>();

        [Tooltip("叠加层可见性（B 切换；默认关）")]
        public bool visible;

        [Tooltip("投影相机；留空 = Camera.main（随 CameraRig 视图切换自动跟随）")]
        public Camera sourceCamera;

        [Tooltip("框外扩像素（包住船体涂装边缘）")]
        public float marginPx = 6f;

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.B))
            {
                visible = !visible;
                Debug.Log($"[Sango.M3] detection overlay {(visible ? "ON" : "OFF")} (B)");
            }
        }

        void OnGUI()
        {
            if (!visible) return; // 关时零绘制
            var cam = sourceCamera != null ? sourceCamera : Camera.main;
            if (cam == null) return;
            var boxes = CollectBoxes(cam, Screen.width, Screen.height);
            foreach (var box in boxes)
            {
                var rect = OverlayProjection.ViewportBoxToPixelRect(box.vpMin, box.vpMax, Screen.width, Screen.height, marginPx);
                GUI.Box(rect, $"{box.label}  {OverlayProjection.ConfidenceLabel(1f, true)}");
            }
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
                var rect = OverlayProjection.ViewportBoxToPixelRect(boxes[i].vpMin, boxes[i].vpMax, Screen.width, Screen.height, marginPx);
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
