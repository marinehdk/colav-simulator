using UnityEngine;

namespace Sango
{
    /// <summary>
    /// M2-E2 相机切换器（spec #85）：C 键循环 Bridge → Bow → Chase → TopDown，位姿过渡
    /// smoothstep ~1 s；bow/chase/top-down 每帧从船实时位姿重解目标（FollowsShip——demo 航行中
    /// 相机跟船）。位姿解析全在纯函数 CameraViews（spec Testing Decisions 缝），本类只做引擎薄壳。
    /// 偏离（documented）：TopDown 的透视⇄正交投影切换无法插值，过渡开始瞬间瞬切。
    /// 桥楼位姿 = M1 场景既有机位（解析器 Bridge 常数同源，零观感变化）。
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
        float m_Blend = 1f; // 1 = 过渡完成（直接贴目标位姿）
        bool m_WarnedNoCamera;

        void Awake()
        {
            Application.runInBackground = true; // 采集/演示失焦不停渲染（WeatherGUI 同款）
            if (controlledCamera == null) controlledCamera = GetComponent<Camera>();
            ApplyProjection(CurrentView);
            SnapNow(); // 起始即桥楼位姿（与 M1 场景相机默认位姿逐位同源）
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
            var targetRot = Quaternion.Euler(target.PitchDeg, target.YawDeg, 0f);
            if (m_Blend < 1f)
            {
                m_Blend = Mathf.Min(1f, m_Blend + (Time.deltaTime > 0f ? Time.deltaTime / Mathf.Max(0.01f, transitionSeconds) : 1f));
                float t = Mathf.SmoothStep(0f, 1f, m_Blend);
                controlledCamera.transform.position = Vector3.Lerp(m_FromPos, target.Position, t);
                controlledCamera.transform.rotation = Quaternion.Slerp(m_FromRot, targetRot, t);
            }
            else
            {
                controlledCamera.transform.position = target.Position;
                controlledCamera.transform.rotation = targetRot;
            }
        }

        /// <summary>C 键入口：循环到下一视图。</summary>
        public void CycleView() => SetView(CameraViews.Next(CurrentView));

        /// <summary>切视图：捕获当前位姿 → 过渡计时归零 → 投影档随视图（正交瞬切，documented）。</summary>
        public void SetView(CameraView view)
        {
            if (view == CurrentView || controlledCamera == null) return;
            m_FromPos = controlledCamera.transform.position;
            m_FromRot = controlledCamera.transform.rotation;
            m_Blend = 0f;
            CurrentView = view;
            ApplyProjection(view);
            Debug.Log($"[Sango.M2E2] camera view -> {view} (transition {transitionSeconds:0.0}s)");
        }

        void ApplyProjection(CameraView view)
        {
            bool ortho = view == CameraView.TopDown;
            controlledCamera.orthographic = ortho;
            if (ortho) controlledCamera.orthographicSize = CameraViews.TopDownOrthoSizeM;
        }

        void SnapNow()
        {
            var target = CameraViews.Resolve(CurrentView, FollowPos(), FollowYawDeg());
            controlledCamera.transform.position = target.Position;
            controlledCamera.transform.rotation = Quaternion.Euler(target.PitchDeg, target.YawDeg, 0f);
        }

        Vector3 FollowPos() => followShip != null ? followShip.position : Vector3.zero;
        float FollowYawDeg() => followShip != null ? followShip.eulerAngles.y : 0f;
    }
}
