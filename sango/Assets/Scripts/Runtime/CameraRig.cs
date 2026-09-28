using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E2 相机切换器（spec #85）：C 键循环 Bridge → Bow → Chase → TopDown，位姿过渡
    /// smoothstep ~1 s；bow/chase/top-down 每帧从船实时位姿重解目标（FollowsShip——demo 航行中
    /// 相机跟船）。位姿解析全在纯函数 CameraViews（spec Testing Decisions 缝），本类只做引擎薄壳。
    /// **全透视 rig**（验收修正 2026-09-24：ortho TopDown 触发 HDRP 透视⇄正交投影切换、破坏管线
    /// 渲染状态——TopDown 花屏、切回后全局变暗；投影切换彻底移除，过渡 = 位置/旋转/FOV 插值）。
    /// 桥楼位姿 = M1 场景既有机位（解析器 Bridge 常数同源 + FOV 60，零观感变化）。
    /// </summary>
    public class CameraRig : MonoBehaviour
    {
        [Tooltip("跟随目标（M1 demo 船 Transform）。bow/chase/top-down 用其实时位姿；空 = 原点朝北。")]
        public Transform followShip;

        [Tooltip("受控相机；留空取同对象上的 Camera。")]
        public Camera controlledCamera;

        [Tooltip("过渡时长（秒，smoothstep 插值位置+旋转）。")]
        public float transitionSeconds = 1f;

        /// <summary>当前视图（C 键循环；面板/日志同源）。</summary>
        public CameraView CurrentView { get; private set; } = CameraView.Bridge;

        Vector3 m_FromPos;
        Quaternion m_FromRot;
        float m_FromFov;
        float m_Blend = 1f; // 1 = 过渡完成（直接贴目标位姿）
        bool m_WarnedNoCamera;
        float m_LastStateLog = -999f; // 运行时状态低频日志（5 s 节流，验收诊断常驻仪表）

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示失焦不停渲染（WeatherGUI 同款）
            if (controlledCamera == null) controlledCamera = GetComponent<Camera>();
            SnapNow(); // 起始即桥楼位姿 + 基准 FOV 60（与 M1 场景相机逐位同源）
        }

        void Update()
        {
            // C 键 = 相机循环（M1 键位账本：0-9/T/F 天气、G demo，C 空闲）。
            if (Input.GetKeyDown(KeyCode.C)) CycleView();
        }

        void LateUpdate()
        {
            if (controlledCamera == null)
            {
                if (!m_WarnedNoCamera)
                {
                    m_WarnedNoCamera = true;
                    Debug.LogWarning("[Sango.M2E2] CameraRig: no controlled camera — view switching disabled.", this);
                }
                return;
            }
            var target = CameraViews.Resolve(CurrentView, FollowPos(), FollowYawDeg());
            if (m_Blend < 1f)
            {
                m_Blend = Mathf.Min(1f, m_Blend + (Time.deltaTime > 0f ? Time.deltaTime / Mathf.Max(0.01f, transitionSeconds) : 1f));
                float t = Mathf.SmoothStep(0f, 1f, m_Blend);
                ApplyPose(target.Position, target.PitchDeg, target.YawDeg, Mathf.Lerp(m_FromFov, target.FieldOfView, t));
            }
            else
            {
                ApplyPose(target.Position, target.PitchDeg, target.YawDeg, target.FieldOfView);
            }

            // 验收诊断（常驻低频仪表，VesselBuoyancy 10 s 行同款模式）：相机真实运行态 +
            // 跟随目标真值——区分"位姿解算错"与"船根变换本身错"的唯一现场证据。
            if (Time.time - m_LastStateLog >= 5f)
            {
                m_LastStateLog = Time.time;
                Debug.Log($"[Sango.M2E2] cam view={CurrentView} pos={controlledCamera.transform.position.ToString("F2")} rot={controlledCamera.transform.rotation.eulerAngles.ToString("F1")} fov={controlledCamera.fieldOfView:F1} followPos={FollowPos().ToString("F2")} followYaw={FollowYawDeg():F1}");

                // 全场景相机普查（含未启用）：谁在渲染、渲到哪、小船在其视锥内吗——
                // "位姿正确却渐变" ⇒ 必有别的相机在 rig 之后（或取而代之）画屏幕。
                Vector3 boatPos = FollowPos();
                var cams = Object.FindObjectsByType<Camera>(FindObjectsInactive.Include, FindObjectsSortMode.None);
                for (int i = 0; i < cams.Length; i++)
                {
                    var c = cams[i];
                    var rt = c.targetTexture;
                    string line = $"[Sango.M2E2] cam census #{i} name={c.name} on={c.enabled} act={c.gameObject.activeInHierarchy} depth={c.depth} disp={c.targetDisplay} rt={(rt != null ? rt.name + " " + rt.width + "x" + rt.height : "screen")} rect={c.rect} pos={c.transform.position.ToString("F1")} rot={c.transform.rotation.eulerAngles.ToString("F0")} near={c.nearClipPlane:0.##} far={c.farClipPlane:0} ortho={c.orthographic} boatNDC={c.WorldToViewportPoint(boatPos).ToString("F2")}";
                    if (c == controlledCamera)
                    {
                        // 矩阵真相（区分"transform 错"与"渲染矩阵被冻结/被外部覆写"）：
                        // w2cboat = 相机缓存 worldToCameraMatrix 下的船视空间坐标；
                        // camPosByMatrix = 矩阵自报的相机世界位；projFov = 矩阵自报的垂直 FOV。
                        Vector3 w2cBoat = c.worldToCameraMatrix.MultiplyPoint(boatPos);
                        Vector3 camPosByMatrix = c.cameraToWorldMatrix.MultiplyPoint(Vector3.zero);
                        float projFov = 2f * Mathf.Atan(1f / c.projectionMatrix.m11) * Mathf.Rad2Deg;
                        line += $" w2cBoat={w2cBoat.ToString("F2")} camPosByMatrix={camPosByMatrix.ToString("F2")} projFov={projFov:F1}";
                    }
                    Debug.Log(line);
                }
            }
        }

        /// <summary>
        /// 位姿写入。**pitch 取负进 Unity**（根因修复 2026-09-28）：CameraViews 约定
        /// "PitchDeg 负 = 俯"，但 Unity Quaternion.Euler 是 **正 x = 俯**（Rx(+90)·(0,0,1) =
        /// (0,−1,0)）——此前 −26.6 直传 = 抬头 26.6°，Chase/TopDown/Bow 全在拍天海渐变
        /// （cam census w2cBoat 逐字证据：Chase 船入视空间 (0,−29.53,−18.76)，57.6° 出框下方
        /// = 30.96° 真俯角 + 26.6° 反向抬头）。取负后：桥楼 = Down 0.52°（= M1 LookRotation
        /// 位姿逐位），Chase 船回画面中心，TopDown 真·俯视 80°。
        /// </summary>
        void ApplyPose(Vector3 pos, float pitchDeg, float yawDeg, float fov)
        {
            controlledCamera.transform.position = pos;
            controlledCamera.transform.rotation = Quaternion.Euler(-pitchDeg, yawDeg, 0f);
            controlledCamera.fieldOfView = fov;
        }

        /// <summary>C 键入口：循环到下一视图。</summary>
        public void CycleView() => SetView(CameraViews.Next(CurrentView));

        /// <summary>切视图：捕获当前位姿/FOV → 过渡计时归零（全透视，无投影切换）。</summary>
        public void SetView(CameraView view)
        {
            if (view == CurrentView || controlledCamera == null) return;
            m_FromPos = controlledCamera.transform.position;
            m_FromRot = controlledCamera.transform.rotation;
            m_FromFov = controlledCamera.fieldOfView;
            m_Blend = 0f;
            CurrentView = view;
            Debug.Log($"[Sango.M2E2] camera view -> {view} (transition {transitionSeconds:0.0}s)");
        }

        void SnapNow()
        {
            var target = CameraViews.Resolve(CurrentView, FollowPos(), FollowYawDeg());
            ApplyPose(target.Position, target.PitchDeg, target.YawDeg, target.FieldOfView);
        }

        Vector3 FollowPos() => followShip != null ? followShip.position : Vector3.zero;
        float FollowYawDeg() => followShip != null ? followShip.eulerAngles.y : 0f;
    }
}
