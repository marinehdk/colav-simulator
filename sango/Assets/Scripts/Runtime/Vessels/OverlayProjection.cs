using System;
using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M3 缝钉子①投影数学（spec #86：DetectionOverlay box→screen projection math as a pure function）。
    /// 输入 viewport AABB（0..1，y 向上，Camera.WorldToViewportPoint 域）→ 输出像素 xyxy 矩形
    /// （原点画面左上、y 向下，与 DetectionResult.Box.box_xyxy 同域），并钳到屏幕内。
    /// 相机无关 = EditMode 纯函数可测；相机相关的 8 角点世界→viewport 收纳在 DetectionOverlay 适配层。
    /// </summary>
    public static class OverlayProjection
    {
        /// <summary>
        /// viewport AABB → 像素矩形。marginPx 向四周外扩（框包住船体边缘），出屏部分钳到屏幕。
        /// </summary>
        public static Rect ViewportBoxToPixelRect(Vector2 vpMin, Vector2 vpMax, int screenWidth, int screenHeight, float marginPx)
        {
            // viewport → 像素：x 直乘屏宽；y 翻转（viewport 上 = 像素 y 小，GUI 左上原点）。
            float x0 = vpMin.x * screenWidth - marginPx;
            float x1 = vpMax.x * screenWidth + marginPx;
            float y0 = (1f - vpMax.y) * screenHeight - marginPx;
            float y1 = (1f - vpMin.y) * screenHeight + marginPx;
            // 出屏钳制到屏幕内（框可部分出屏，但坐标不越界）。
            x0 = Mathf.Clamp(x0, 0f, screenWidth);
            x1 = Mathf.Clamp(x1, 0f, screenWidth);
            y0 = Mathf.Clamp(y0, 0f, screenHeight);
            y1 = Mathf.Clamp(y1, 0f, screenHeight);
            return Rect.MinMaxRect(x0, y0, x1, y1);
        }

        /// <summary>
        /// 置信度标签：真值框恒 1 → "1.0 (gt)"（spec 演示要求）；普通检测 → "0.87" 式两位小数。
        /// </summary>
        public static string ConfidenceLabel(float confidence, bool groundTruth)
        {
            return groundTruth ? $"{confidence:0.0#} (gt)" : $"{confidence:0.0#}";
        }
    }
}
