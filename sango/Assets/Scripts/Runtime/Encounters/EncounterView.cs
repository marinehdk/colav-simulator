using UnityEngine;
using UnityEngine.Rendering;
using TMPro;

namespace Sango
{
    /// <summary>
    /// M2-E1 俯视视觉语言（spec #84）：每船一条运行中追加的彩色轨迹（LineRenderer，own 青 /
    /// target 琥珀）、固定仿真间隔的时间球（小球贴水面）、Start/WP 世界标签（TMP 平铺水面，
    /// 北向上可读）与 50 m 比例尺。纯运行时构建（WeatherGUI idiom：零场景资产依赖），
    /// HDRP/Unlit 运行时材质（M2-D 同款，真机可用）。EncounterDirector 驱动。
    /// </summary>
    public class EncounterView : MonoBehaviour
    {
        static readonly Color[] k_ShipColor =
        {
            new Color(0.25f, 0.85f, 1f),   // own：青
            new Color(1f, 0.72f, 0.15f),   // target：琥珀
        };
        static readonly string[] k_ShipName = { "OWN", "TARGET" };

        const float k_TrackWidthM = 2.5f;
        const float k_TrackY = 0.4f;
        const float k_MinTrackSegmentM = 3f;  // 轨迹抽稀：位移小于此不落点（顶点数有界）
        const float k_BallDiameterM = 7f;
        const float k_ScaleBarLengthM = 50f;

        LineRenderer[] _tracks;
        Material[] _shipMats;
        Transform _ballRoot;
        Transform _labelRoot;
        Transform _scaleBarRoot;
        float _extentM = 500f;

        public static EncounterView Create(Transform parent)
        {
            var go = new GameObject("Encounter View");
            go.transform.SetParent(parent, false);
            return go.AddComponent<EncounterView>();
        }

        void Awake()
        {
            _shipMats = new Material[2];
            for (int i = 0; i < 2; i++)
            {
                var m = new Material(Shader.Find("HDRP/Unlit"));
                m.color = k_ShipColor[i];
                _shipMats[i] = m;
            }

            _tracks = new LineRenderer[2];
            for (int i = 0; i < 2; i++)
            {
                var go = new GameObject($"Track.{k_ShipName[i]}");
                go.transform.SetParent(transform, false);
                var lr = go.AddComponent<LineRenderer>();
                lr.material = _shipMats[i];
                lr.startColor = lr.endColor = k_ShipColor[i];
                lr.widthMultiplier = k_TrackWidthM;
                lr.positionCount = 0;
                lr.numCornerVertices = 4;
                lr.numCapVertices = 2;
                lr.shadowCastingMode = ShadowCastingMode.Off;
                _tracks[i] = lr;
            }

            _ballRoot = new GameObject("TimeBalls").transform;
            _ballRoot.SetParent(transform, false);
        }

        /// <summary>模式装载/重置：清轨迹与时间球，按新几何重建标签与比例尺。</summary>
        public void Setup(in EncounterPattern pattern)
        {
            _extentM = pattern.ExtentM > 1f ? pattern.ExtentM : 500f;
            foreach (var lr in _tracks) lr.positionCount = 0;
            if (_ballRoot != null)
            {
                for (int i = _ballRoot.childCount - 1; i >= 0; i--) Destroy(_ballRoot.GetChild(i).gameObject);
            }
            BuildLabels(pattern);
            BuildScaleBar();
        }

        /// <summary>追加轨迹点（世界 x/z；y 贴水面）。位移小于抽稀阈值不落点。</summary>
        public void AppendTrack(int shipIdx, Vector3 shipPos)
        {
            var lr = _tracks[shipIdx];
            var p = new Vector3(shipPos.x, k_TrackY, shipPos.z);
            if (lr.positionCount > 0 &&
                (lr.GetPosition(lr.positionCount - 1) - p).sqrMagnitude < k_MinTrackSegmentM * k_MinTrackSegmentM)
            {
                return;
            }
            lr.positionCount++;
            lr.SetPosition(lr.positionCount - 1, p);
        }

        /// <summary>在船当前位置落一颗时间球（颜色随船）。</summary>
        public void DropBall(int shipIdx, Vector3 shipPos)
        {
            var ball = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            Destroy(ball.GetComponent<Collider>()); // 标记非碰撞体
            ball.name = $"Ball.{k_ShipName[shipIdx]}";
            ball.transform.SetParent(_ballRoot, false);
            ball.transform.position = new Vector3(shipPos.x, 1.5f, shipPos.z);
            ball.transform.localScale = Vector3.one * k_BallDiameterM;
            var mr = ball.GetComponent<MeshRenderer>();
            mr.sharedMaterial = _shipMats[shipIdx];
            mr.shadowCastingMode = ShadowCastingMode.Off;
        }

        // ── 静态标注（每模式重建）────────────────────────────────────────────────────

        void BuildLabels(in EncounterPattern p)
        {
            if (_labelRoot != null) Destroy(_labelRoot.gameObject);
            _labelRoot = new GameObject("Labels").transform;
            _labelRoot.SetParent(transform, false);
            CreateLabel("Start OWN", p.Own.SpawnXZ, k_ShipColor[0]);
            CreateLabel("WP OWN", p.Own.Waypoints[p.Own.Waypoints.Length - 1], k_ShipColor[0]);
            CreateLabel("Start TARGET", p.Target.SpawnXZ, k_ShipColor[1]);
            CreateLabel("WP TARGET", p.Target.Waypoints[p.Target.Waypoints.Length - 1], k_ShipColor[1]);
        }

        // 标签文字向东北偏 30 m，压不到船与轨迹主线。
        void CreateLabel(string text, Vector2 xz, Color color)
        {
            CreateWorldLabel(_labelRoot, text, text, color, new Vector2(xz.x + 30f, xz.y + 30f), new Vector2(800f, 160f), 0.2f);
        }

        // M2-E2 carry-in 去重（spec #85）：CreateLabel / CreateScaleLabel 的 TMP 世界标签
        // 建构抽到单一入口（此前两份复制：字体/朝向/镜像缩放纪律只改过一处漏一处）。
        static void CreateWorldLabel(Transform parent, string name, string text, Color color,
            Vector2 xz, Vector2 sizeDelta, float scale)
        {
            var go = new GameObject($"Label.{name}", typeof(TextMeshPro)); // RequireComponent 自动加 MeshRenderer
            go.transform.SetParent(parent, false);
            var tmp = go.GetComponent<TextMeshPro>();
            if (TMP_Settings.defaultFontAsset != null) tmp.font = TMP_Settings.defaultFontAsset;
            tmp.text = text;
            tmp.fontSize = 100f;
            tmp.color = color;
            tmp.alignment = TextAlignmentOptions.Center;
            tmp.overflowMode = TextOverflowModes.Overflow;
            tmp.raycastTarget = false;
            var rt = tmp.rectTransform;
            rt.sizeDelta = sizeDelta;
            // 平铺水面（正面向上）、字头朝北（北向上俯视可读）：先绕 X −90° 立起正面向上，
            // 再绕世界 Y 180° 调字头方向，最后局部 X 负缩放把阅读方向镜像回正
            // （TMP SDF shader Cull Off，负缩放安全）。
            go.transform.rotation = Quaternion.Euler(0f, 180f, 0f) * Quaternion.Euler(-90f, 0f, 0f);
            go.transform.localScale = new Vector3(-scale, scale, scale);
            go.transform.position = new Vector3(xz.x, 0.6f, xz.y);
            go.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
        }

        void BuildScaleBar()
        {
            if (_scaleBarRoot != null) Destroy(_scaleBarRoot.gameObject);
            _scaleBarRoot = new GameObject("ScaleBar").transform;
            _scaleBarRoot.SetParent(transform, false);

            float z = -(_extentM - 80f);          // 视野南缘内 80 m
            float x0 = -_extentM * 0.55f;
            var lineGo = new GameObject("Bar");
            lineGo.transform.SetParent(_scaleBarRoot, false);
            var lr = lineGo.AddComponent<LineRenderer>();
            var mat = new Material(Shader.Find("HDRP/Unlit"));
            mat.color = Color.white;
            lr.material = mat;
            lr.startColor = lr.endColor = Color.white;
            lr.widthMultiplier = 2f;
            lr.positionCount = 2;
            lr.SetPosition(0, new Vector3(x0, k_TrackY, z));
            lr.SetPosition(1, new Vector3(x0 + k_ScaleBarLengthM, k_TrackY, z));
            lr.shadowCastingMode = ShadowCastingMode.Off;

            CreateScaleLabel(new Vector2(x0 + k_ScaleBarLengthM * 0.5f, z + 30f));
        }

        void CreateScaleLabel(Vector2 xz)
        {
            CreateWorldLabel(_scaleBarRoot, "50 m", "50 m", Color.white, xz, new Vector2(400f, 160f), 0.15f); // ≈15 m 字高
        }
    }
}
