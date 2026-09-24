using UnityEngine;

namespace Sango
{
    /// <summary>四视图（spec #85 画面 2/3/4 补全）。C 键循环。</summary>
    public enum CameraView
    {
        Bridge,  // 桥楼固定机位（M1 既有 (0,12,-40) 望北）
        Bow,     // 艏视角：装在小船艏部随船
        Chase,   // 追随视角：艉后上方随船
        TopDown, // 北向上正交俯视（encounter 同款方向约定）
    }

    /// <summary>相机目标位姿（yaw/pitch 分量式：Euler(pitch, yaw, 0)，无 roll）。</summary>
    public struct CameraPose
    {
        public Vector3 Position;
        public float YawDeg;      // 0 = 北(+z)，顺时针为正（= Unity rotation.y）
        public float PitchDeg;    // 负 = 俯
        public bool FollowsShip;  // true = 每帧从船实时位姿重解（bow/chase/top-down）
        public bool Orthographic; // top-down 正交
        public float OrthoSizeM;  // 正交半高 m
    }

    /// <summary>
    /// M2-E2 相机视图位姿解析（纯函数，无引擎调用——船位姿作参数传入，spec #85 Testing Decisions）。
    /// 坐标约定与 WaypointKinematics 同源：东 = +x，北 = +z，艏向角自北顺时针；
    /// 艏向单位向量 = (sin h, 0, cos h)。bow/chase 偏移按船位姿船体系（艏向旋转）叠加。
    /// </summary>
    public static class CameraViews
    {
        // 桥楼：M1 场景既有机位 (0,12,-40) 望岛群 (0,10,180)——pitch = atan2(-2, 220) ≈ -0.52°。
        public static readonly Vector3 BridgePosition = new Vector3(0f, 12f, -40f);
        public const float BridgeYawDeg = 0f;
        public const float BridgePitchDeg = -0.52f;

        // 艏视角：艏向前 8 m、高 4.5 m（小船 LOA ≈12 m 的艏部上空），沿艏向前看微俯 8°。
        public const float BowForwardOffsetM = 8f;
        public const float BowHeightM = 4.5f;
        public const float BowPitchDeg = -8f;

        // 追随：艉后 30 m、高 18 m，望船（俯角 atan2(18-3, 30) ≈ 26.6°）。
        public const float ChaseAsternOffsetM = 30f;
        public const float ChaseHeightM = 18f;
        public const float ChasePitchDeg = -26.6f;

        // 俯视：船上空 300 m 正交、北向上（forward=下、up=北），半高 150 m。
        public const float TopDownHeightM = 300f;
        public const float TopDownOrthoSizeM = 150f;

        public static CameraPose Resolve(CameraView view, Vector3 shipPos, float shipHeadingDeg)
        {
            // 艏向单位向量（约定：自北顺时针，(sin h, 0, cos h)）；偏移全在水平面，艏部/艉后高度走 +y。
            float rad = shipHeadingDeg * Mathf.Deg2Rad;
            var fwd = new Vector3(Mathf.Sin(rad), 0f, Mathf.Cos(rad));
            switch (view)
            {
                case CameraView.Bow:
                    return new CameraPose
                    {
                        Position = shipPos + fwd * BowForwardOffsetM + Vector3.up * BowHeightM,
                        YawDeg = shipHeadingDeg,
                        PitchDeg = BowPitchDeg,
                        FollowsShip = true,
                    };
                case CameraView.Chase:
                    return new CameraPose
                    {
                        Position = shipPos - fwd * ChaseAsternOffsetM + Vector3.up * ChaseHeightM,
                        YawDeg = shipHeadingDeg,
                        PitchDeg = ChasePitchDeg,
                        FollowsShip = true,
                    };
                case CameraView.TopDown:
                    return new CameraPose
                    {
                        Position = shipPos + Vector3.up * TopDownHeightM,
                        YawDeg = 0f, // 北向上（海图方向）：yaw 归零、pitch −90
                        PitchDeg = -90f,
                        FollowsShip = true,
                        Orthographic = true,
                        OrthoSizeM = TopDownOrthoSizeM,
                };
                case CameraView.Bridge:
                default:
                    return new CameraPose
                    {
                        Position = BridgePosition,
                        YawDeg = BridgeYawDeg,
                        PitchDeg = BridgePitchDeg,
                    };
            }
        }

        /// <summary>C 键循环顺序：Bridge → Bow → Chase → TopDown → Bridge。</summary>
        public static CameraView Next(CameraView view)
        {
            int next = (int)view + 1;
            return next > (int)CameraView.TopDown ? CameraView.Bridge : (CameraView)next;
        }
    }
}
