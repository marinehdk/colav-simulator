using UnityEngine;

namespace Sango
{
    /// <summary>五视图（spec #85 四视图 + M7-A F1 瞭望档）。C 键循环。</summary>
    public enum CameraView
    {
        Bridge,   // 桥楼固定机位（M1 既有 (0,12,-40) 望北）
        Bow,      // 艏视角：装在小船艏部随船
        Chase,    // 追随视角：艉后上方随船
        TopDown,  // 北向上透视俯视战术档（encounter 同款方向约定）
        Overlook, // 瞭望：船前上方回望（M7-A F1——艉后方向尽收：出生点见 PP 岸桥天际线，航线后段见东锚地）
    }

    /// <summary>相机目标位姿（yaw/pitch 分量式，无 roll）+ 每视图 FOV。
    /// PitchDeg 约定 **负 = 俯**（几何直觉制）；消费者转 Unity 时须取负
    /// （Unity Quaternion.Euler 正 x = 俯，CameraRig.ApplyPose 单点负责）。</summary>
    public struct CameraPose
    {
        public Vector3 Position;
        public float YawDeg;      // 0 = 北(+z)，顺时针为正（= Unity rotation.y）
        public float PitchDeg;    // 负 = 俯
        public float FieldOfView; // 垂直视场角（桥楼/艏/追随 60，俯视 35）
        public bool FollowsShip;  // true = 每帧从船实时位姿重解（bow/chase/top-down）
    }

    /// <summary>
    /// M2-E2 相机视图位姿解析（纯函数，无引擎调用——船位姿作参数传入，spec #85 Testing Decisions）。
    /// 坐标约定与 WaypointKinematics 同源：东 = +x，北 = +z，艏向角自北顺时针；
    /// 艏向单位向量 = (sin h, 0, cos h)。bow/chase 偏移按船位姿船体系（艏向旋转）叠加。
    /// **全部视图透视**（验收修正 2026-09-24：ortho TopDown 触发 HDRP 透视⇄正交投影切换的
    /// 管线状态破坏——TopDown 花屏、切回透视后全局变暗；投影切换彻底移除）。
    /// TopDown = 北向上战术俯视：160 m 高、pitch −80°、FOV 35°（地面足迹 ~100 m，
    /// 12 m 小船 ~100+ px 恒在画面正中）。
    /// </summary>
    public static class CameraViews
    {
        /// <summary>常规视图垂直 FOV（桥楼/艏/追随）。</summary>
        public const float BaseFovDeg = 60f;
        /// <summary>俯视战术档垂直 FOV（收窄放大船体）。</summary>
        public const float TopDownFovDeg = 35f;

        // 桥楼：M1 场景既有机位 (0,12,-40) 望岛群 (0,10,180)——pitch = atan2(-2, 220) ≈ -0.52°。
        // 高度/艉后分量单独成常量：bridgeShipRelative=true 时同一偏移按船艏向旋转叠加
        // （M6 海峡 review S1 2026-09-29：船在 (-1500,-5000) 时固定机位拍空海——首帧无船）。
        public const float BridgeHeightM = 12f;
        public const float BridgeAsternOffsetM = 40f;
        public static readonly Vector3 BridgePosition = new Vector3(0f, BridgeHeightM, -BridgeAsternOffsetM);
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

        // 俯视（战术档，全透视）：船上空 160 m、pitch −80°（视线略北倾，足迹中心 ~28 m 北）、
        // 北向上（yaw 0 = 海图方向），FOV 35°。
        public const float TopDownHeightM = 160f;
        public const float TopDownPitchDeg = -80f;

        // 瞭望（M7-A F1 2026-09-29）：艏向前 80 m、高 40 m，yaw = 艏向+180° 回望、俯角
        // atan2(40,80) ≈ 26.6°（船居画面中心）——M7-A 四机位均沿艏向（hero 艏向 134° SE），
        // PP 岸桥天际线（艉后 3.4 km）与东锚地船群（右舷前 11 km）demo 全程不可见；本档
        // 出生点即见 PP 岸桥天际线（bearing≈346°，16:9 半横视场 45.7° 内），航线后段回望见东锚地。
        public const float OverlookHeightM = 40f;
        public const float OverlookForwardOffsetM = 80f;
        public const float OverlookPitchDeg = -26.6f;

        /// <summary>3 参旧签名（bridgeShipRelative=false，M1 语义零变化）；既有调用/测试不动。</summary>
        public static CameraPose Resolve(CameraView view, Vector3 shipPos, float shipHeadingDeg)
            => Resolve(view, shipPos, shipHeadingDeg, bridgeShipRelative: false);

        /// <summary>
        /// bridgeShipRelative=true 时 Bridge 改随船解算：船位 + 船艏向系 (0,12,-40) 偏移
        /// （艉后 40 m 高 12 m）、视线沿艏向、FollowsShip=true——供船远离世界原点的场景
        /// （M6 主角泊位 (-1500,-5000)）使用；false = M1 固定机位 (0,12,-40) 望北，零变化。
        /// </summary>
        public static CameraPose Resolve(CameraView view, Vector3 shipPos, float shipHeadingDeg, bool bridgeShipRelative)
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
                        FieldOfView = BaseFovDeg,
                        FollowsShip = true,
                    };
                case CameraView.Chase:
                    return new CameraPose
                    {
                        Position = shipPos - fwd * ChaseAsternOffsetM + Vector3.up * ChaseHeightM,
                        YawDeg = shipHeadingDeg,
                        PitchDeg = ChasePitchDeg,
                        FieldOfView = BaseFovDeg,
                        FollowsShip = true,
                    };
                case CameraView.TopDown:
                    return new CameraPose
                    {
                        Position = shipPos + Vector3.up * TopDownHeightM,
                        YawDeg = 0f, // 北向上（海图方向，不随艏向）
                        PitchDeg = TopDownPitchDeg,
                        FieldOfView = TopDownFovDeg,
                        FollowsShip = true,
                    };
                case CameraView.Overlook:
                    // 船艏向系前方 (0,40,+80)（+Z=艏）随艏向旋转，yaw = 艏向+180° 回望（M6 S1
                    // bridgeShipRelative 同款船相对解算模式，镜像在艏前而非艉后）；FollowsShip
                    // = 每帧从船实时位姿重解，航行中艉后方向恒在画面。
                    return new CameraPose
                    {
                        Position = shipPos + fwd * OverlookForwardOffsetM + Vector3.up * OverlookHeightM,
                        YawDeg = Mathf.Repeat(shipHeadingDeg + 180f, 360f),
                        PitchDeg = OverlookPitchDeg,
                        FieldOfView = BaseFovDeg,
                        FollowsShip = true,
                    };
                case CameraView.Bridge:
                default:
                    if (bridgeShipRelative)
                    {
                        // 船体系 (0,12,-40) 随艏向旋转：艉后 40 m 高 12 m，视线沿艏向（船恒在
                        // 画面内）；pitch 沿用固定机位微俯 -0.52°。
                        return new CameraPose
                        {
                            Position = shipPos - fwd * BridgeAsternOffsetM + Vector3.up * BridgeHeightM,
                            YawDeg = shipHeadingDeg,
                            PitchDeg = BridgePitchDeg,
                            FieldOfView = BaseFovDeg,
                            FollowsShip = true,
                        };
                    }
                    return new CameraPose
                    {
                        Position = BridgePosition,
                        YawDeg = BridgeYawDeg,
                        PitchDeg = BridgePitchDeg,
                        FieldOfView = BaseFovDeg,
                    };
            }
        }

        /// <summary>C 键循环顺序：Bridge → Bow → Chase → TopDown → Overlook → Bridge。</summary>
        public static CameraView Next(CameraView view)
        {
            int next = (int)view + 1;
            return next > (int)CameraView.Overlook ? CameraView.Bridge : (CameraView)next;
        }
    }
}
