using UnityEngine;
using UnityEngine.Rendering;

namespace Sango
{
    /// <summary>
    /// M2-E2 桥楼矢量箭头（spec #85 Story 2）：蓝 = 速度箭头（长度 ∝ 速度，比例因子
    /// VectorArrowMath.VelocityMetersPerMps = 2 m/(m/s)，零速 stub 1.5 m）、绿 = 航点方向箭头
    /// （定长 10 m 指向活动航点）。挂在 M1 demo 船上；端点数学全在纯函数 VectorArrowMath。
    /// 杆+锥世界空间原语（HDRP/Unlit HDR 亮色 = 自发光观感，NavigationLights 同款路径）。
    /// idle 行为（documented，spec 授权自定）：demo 未起跑/暂停 → 整树隐藏；跑动中零速 →
    /// stub 箭头仍可见；TopDown 俯视 → 隐藏（世界箭头在俯视下读不出方向）；V 键总开关。
    /// rig 为世界空间根（非船子物体）：箭头长度/朝向逐帧按导航艏向（psi = euler.y − 烘焙补偿）
    /// 重排，避免船根烘焙艏向耦合。
    /// </summary>
    public class VectorArrows : MonoBehaviour
    {
        [Tooltip("同船跟随器（速度/活动航点/烘焙艏向真值）。")]
        public WaypointFollower follower;

        [Tooltip("相机 rig（TopDown 时隐藏箭头）；空 = 不做视图过滤。")]
        public CameraRig cameraRig;

        [Tooltip("矢量显示总开关（V 键切换）。")]
        public bool show = true;

        Transform m_Root;
        Transform m_VelocityArrow, m_WaypointArrow;
        Transform m_VelocityShaft, m_VelocityHead, m_WaypointShaft, m_WaypointHead;

        // 箭头离水线高度：速度箭头贴甲板 (~3 m)，航点箭头更高一层 (~5 m) 防同高穿插。
        // 宽度按追随视角 30-50 m 距离校验（FOV 60°：40 m 处 ~19 px/m——杆 0.35 m ≈ 7 px、
        // 头 1.0×1.5 m 可辨）；速度箭头在 chase 内正对相机指向（前向）透视收缩成亮点属
        // 几何必然，绿色航点箭头（斜方位）承担该视角的可读性。
        const float k_VelocityHeightM = 3f;
        const float k_WaypointHeightM = 5f;
        const float k_ShaftWidthM = 0.35f;
        const float k_HeadLengthM = 1.5f;   // 锥头长（沿指向）
        const float k_HeadWidthM = 1.0f;    // 锥头底径

        void OnEnable()
        {
            if (m_Root != null) return; // 幂等（域重载不重建）
            m_Root = new GameObject("VectorArrowsRig").transform;

            var velocityMat = UnlitBright(new Color(0.25f, 0.55f, 1f), 2.5f); // 蓝
            var waypointMat = UnlitBright(new Color(0.3f, 1f, 0.45f), 2.5f);  // 绿
            (m_VelocityShaft, m_VelocityHead) = BuildArrow("Velocity", velocityMat);
            (m_WaypointShaft, m_WaypointHead) = BuildArrow("Waypoint", waypointMat);
            m_VelocityArrow = m_VelocityShaft.parent;
            m_WaypointArrow = m_WaypointShaft.parent;
            Debug.Log("[Sango.M2E2] vector arrows rig built (blue velocity x2 m per m/s, green waypoint fixed 10 m) on " + name);
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.V))
            {
                show = !show;
                Debug.Log($"[Sango.M2E2] vectors {(show ? "shown" : "hidden")} (V)");
            }

            bool active = show && follower != null && follower.DemoRunning
                          && (cameraRig == null || cameraRig.CurrentView != CameraView.TopDown);
            if (m_Root.gameObject.activeSelf != active) m_Root.gameObject.SetActive(active);
            if (!active) return;

            // 导航艏向（ WaypointFollower 初始化捕获反解同式）：psi = 根 euler.y − 烘焙艏向补偿。
            float psi = transform.eulerAngles.y - follower.bowYawDegOffset;

            // 速度箭头：origin = 船 + 甲板高，沿 psi；长度 ∝ 速度（零速 stub，纯函数）。
            var vOrigin = transform.position + Vector3.up * k_VelocityHeightM;
            float vLen = VectorArrowMath.VelocityArrowLengthM(follower.SpeedMps);
            m_VelocityArrow.SetPositionAndRotation(vOrigin, Quaternion.Euler(0f, psi, 0f));
            LayoutArrow(m_VelocityShaft, m_VelocityHead, vLen);

            // 航点箭头：origin = 船 + 更高一层，方位 = 指活动航点；无航点表时隐藏。
            var wps = follower.waypoints;
            int idx = follower.ActiveWaypointIndex;
            if (wps != null && wps.Length > 0)
            {
                var wp = wps[Mathf.Clamp(idx, 0, wps.Length - 1)];
                var pos = transform.position;
                float bearing = Mathf.Atan2(wp.x - pos.x, wp.y - pos.z) * Mathf.Rad2Deg;
                m_WaypointArrow.SetPositionAndRotation(pos + Vector3.up * k_WaypointHeightM,
                    Quaternion.Euler(0f, bearing, 0f));
                LayoutArrow(m_WaypointShaft, m_WaypointHead, VectorArrowMath.WaypointArrowLengthM);
            }
            else
            {
                m_WaypointArrow.gameObject.SetActive(false);
            }
        }

        // ── rig 构建（杆 + 锥头，+Z 为指向）──────────────────────────────────────────

        (Transform shaft, Transform head) BuildArrow(string name, Material mat)
        {
            var arrow = new GameObject($"{name}Arrow").transform;
            arrow.SetParent(m_Root, false);

            var shaft = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.Destroy(shaft.GetComponent<Collider>()); // 标记非碰撞体
            shaft.name = $"{name}.Shaft";
            shaft.transform.SetParent(arrow, false);
            shaft.GetComponent<MeshRenderer>().sharedMaterial = mat;
            shaft.transform.localScale = new Vector3(k_ShaftWidthM, k_ShaftWidthM, 1f);
            shaft.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;

            var head = GameObject.CreatePrimitive(PrimitiveType.Cube);
            Object.Destroy(head.GetComponent<Collider>());
            head.name = $"{name}.Head";
            head.transform.SetParent(arrow, false);
            head.GetComponent<MeshRenderer>().sharedMaterial = mat;
            // 无 Cone 原语（Unity 6000.3 PrimitiveType 仅 Cube/Sphere/Capsule/Cylinder/Plane/Quad）：
            // 方块绕长轴滚 45°（Euler(90,0,45)：先 +Y→+Z 指向，再 45° 菱形截面）读作箭头端。
            head.transform.localRotation = Quaternion.Euler(90f, 0f, 45f);
            head.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
            return (shaft.transform, head.transform);
        }

        /// <summary>按总长布杆/头：杆 = 总长 − 头长，头心在末端收半头。</summary>
        static void LayoutArrow(Transform shaft, Transform head, float totalLen)
        {
            float shaftLen = Mathf.Max(0.05f, totalLen - k_HeadLengthM);
            shaft.localPosition = Vector3.zero;
            shaft.localScale = new Vector3(k_ShaftWidthM, k_ShaftWidthM, shaftLen);
            shaft.localPosition = new Vector3(0f, 0f, shaftLen * 0.5f);
            head.localPosition = new Vector3(0f, 0f, shaftLen + k_HeadLengthM * 0.5f);
            head.localScale = new Vector3(k_HeadWidthM, k_HeadLengthM, k_HeadWidthM); // Cube 原语 1 单位边长：y = 头长
        }

        /// <summary>HDRP/Unlit 不透明 HDR 亮色（颜色 × 亮度 nits → 无光照自发光观感，M2-D 同款）。</summary>
        static Material UnlitBright(Color c, float nits)
        {
            return new Material(Shader.Find("HDRP/Unlit")) { color = new Color(c.r * nits, c.g * nits, c.b * nits, 1f) };
        }
    }
}
