using System.Diagnostics;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;
// System.Diagnostics.Debug 与 UnityEngine.Debug 二义，显式消歧。
using Debug = UnityEngine.Debug;

namespace Sango
{
    /// <summary>
    /// M2-B 逐三角浮力姿态（spec #81）：引擎适配器薄壳。采样沿用 M0 probe 既定模式
    /// （hull 三角质心 → HDRP Water CPU 水高查询，k_SearchError=0.01 / k_MaxIterations=8），
    /// 姿态全部由纯求解器 BuoyancyAttitudeSolver 产出（确定性单点真值）。
    /// 只碰 y/roll/pitch：位置 x/z 与 yaw 永不被写入（后续 waypoint 批次的导航代码独占）；
    /// heave 施加在根 y（基线 = 挂载时根 y，即编目 waterlineOffsetY），roll/pitch 以本地欧拉
    /// Z/X 叠加在脚本拥有的 yaw 上。无 Rigidbody/PhysX，纯视觉。
    /// 采样量控制：hull 三角总数按 maxSamplesPerHull 均匀步进抽样（Small 711 / Medium 8388 三角
    /// 全采将达 ~9.1k 查询/帧 ≈ M0 锚点 0.42 ms 的 20 倍，见 evidence m2b-build-log.md），
    /// 默认 64 点/船 → 两船 128 查询/帧，低于 M0 锚点 144。
    /// </summary>
    [DefaultExecutionOrder(100)] // 与 M0 probe 同档；帧级静态统计在帧末（FpsProbe 200 档）前聚合完整
    public class VesselBuoyancy : MonoBehaviour
    {
        [Tooltip("要查询的 HDRP Water Surface（场景构建器注入，也可 Inspector 拖拽）。")]
        public WaterSurface waterSurface;

        [Tooltip("临界阻尼平滑频率（Hz）：越大跟浪越紧，越小越沉稳。0.8 ≈ 1.5 s 整定，货轮量级观感。")]
        public float smoothingFrequencyHz = 0.8f;

        [Tooltip("横摇钳制上限（度，对称）：涌浪再大也不许倾覆观感。")]
        public float maxRollDeg = BuoyancyParams.Default.MaxRollDeg;

        [Tooltip("纵摇钳制上限（度，对称）。")]
        public float maxPitchDeg = BuoyancyParams.Default.MaxPitchDeg;

        [Tooltip("每船水高查询抽样上限（hull 三角质心均匀步进抽取）。")]
        public int maxSamplesPerHull = 64;

        // 搜索参数取值对齐 M0 probe（= HDRP 官方 WaterSamples/Buoyancy.cs 默认）。
        const float k_SearchError = 0.01f;
        const int k_MaxIterations = 8;

        // 帧级统计（probe 模式）：帧内首个组件重置，统计含失败查询与耗时。
        static int s_FrameStamp;
        static int s_FrameQueries;
        static int s_FrameFailedQueries;
        static double s_FrameQueryMs;

        /// <summary>本帧水高查询总次数（含失败，全部 VesselBuoyancy 合计）。</summary>
        public static int FrameQueries => s_FrameQueries;
        /// <summary>本帧查询失败次数（scriptInteractions 未开 / 回读未就绪等）。</summary>
        public static int FrameFailedQueries => s_FrameFailedQueries;
        /// <summary>本帧查询累计耗时（毫秒）。</summary>
        public static double FrameQueryMs => s_FrameQueryMs;

        // 实例观测口（证据/Inspector 观测用）。
        /// <summary>本船实际抽样点数（≤ maxSamplesPerHull）。</summary>
        public int SampleCount => m_RootLocalCentroids != null ? m_RootLocalCentroids.Length : 0;
        /// <summary>本帧求解目标姿态（heave 米 / roll 度 / pitch 度，钉死约定见求解器）。</summary>
        public Vector3 TargetAttitude => new Vector3(m_TargetHeave, m_TargetRoll, m_TargetPitch);
        /// <summary>当前平滑后姿态（同上）。</summary>
        public Vector3 SmoothedAttitude => new Vector3(m_Heave.Value, m_Roll.Value, m_Pitch.Value);
        /// <summary>设计吃水基线（挂载时根 y，= 编目 waterlineOffsetY）。</summary>
        public float DraftBaselineY => m_BaselineY;

        struct HullTriangle
        {
            public Vector3 RootLocalCentroid; // 挂载时缓存：filter局部质心 → 根局部空间（静态几何）
            public float BaselineSubmersion;  // 静水基线浸没 = -(baselineY + rootLocal.y)
        }

        HullTriangle[] m_RootLocalCentroids;
        HullSample[] m_SolverScratch; // 持久求解缓冲：LateUpdate 热循环零分配（复用 count 重载忽略尾部残留）
        float m_BaselineY;
        Stopwatch m_Stopwatch;
        WaterSearchParameters m_SearchParams; // 结构体复用（probe 模式：只初始化一次）
        WaterSearchResult m_SearchResult;

        DampedScalar m_Heave;
        DampedScalar m_Roll;
        DampedScalar m_Pitch;
        float m_TargetHeave;
        float m_TargetRoll;
        float m_TargetPitch;
        float m_NextStatsLogTime;

        void OnEnable()
        {
            // 收集 hull 三角质心（probe 模式：同物体 MeshFilter 优先，否则全部子物体）。
            var own = GetComponent<MeshFilter>();
            var filters = own != null ? new[] { own } : GetComponentsInChildren<MeshFilter>(false);

            // 先数总三角数（跨 filter 统一编号），再按步进均匀抽样。
            int totalTriangles = 0;
            int usableFilters = 0;
            int nullMeshFilters = 0;
            int unreadableMeshes = 0;
            foreach (var filter in filters)
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null)
                {
                    nullMeshFilters++;
                    continue;
                }
                usableFilters++;
                // 玩家构建上 mesh 未开 Read/Write 时 triangles 返回空并报 "not readable"
                //（GUI editor 恒可读，此坑只在真机暴露——见 m2b-build-log.md 根因节）。
                if (!mesh.isReadable) unreadableMeshes++;
                totalTriangles += mesh.triangles.Length / 3;
            }
            if (totalTriangles == 0)
            {
                Debug.LogWarning($"[{nameof(VesselBuoyancy)}] {name}: no usable hull mesh " +
                                 $"(filters={filters.Length} usable={usableFilters} nullMesh={nullMeshFilters} unreadable={unreadableMeshes}) — " +
                                 $"unreadable => enable Read/Write in FBX import (VesselAssetPipeline), buoyancy disabled.", this);
                enabled = false;
                return;
            }

            int stride = Mathf.Max(1, Mathf.CeilToInt(totalTriangles / (float)Mathf.Max(1, maxSamplesPerHull)));
            // 设计吃水基线：PlaceCatalogShip 放的根 y（= 编目 waterlineOffsetY），heave 施加的参照点。
            m_BaselineY = transform.position.y;
            var rootInverse = transform.worldToLocalMatrix;
            var samples = new System.Collections.Generic.List<HullTriangle>(maxSamplesPerHull);
            int globalTriangle = 0;
            foreach (var filter in filters)
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null) continue;
                // 只读缓存，绝不写 sharedMesh（probe 纪律）。filter局部→根局部 合并矩阵只在此算一次。
                var filterToRoot = rootInverse * filter.transform.localToWorldMatrix;
                var verts = mesh.vertices;
                var idx = mesh.triangles;
                for (int t = 0; t < idx.Length; t += 3, globalTriangle++)
                {
                    if (globalTriangle % stride != 0) continue;
                    Vector3 centroid = (verts[idx[t]] + verts[idx[t + 1]] + verts[idx[t + 2]]) / 3f;
                    samples.Add(new HullTriangle
                    {
                        // 根"局部"空间含烘焙的统一缩放（模型单位，非米！）——只用于运行时 TransformPoint。
                        // 基线浸没不能用它混算世界米（M2-B 修复：曾致 heave 目标偏差 ≈(scale-1)·mean(modelY)），
                        // 改在收集后用世界坐标统一推导（船此时在设计位姿）。
                        RootLocalCentroid = filterToRoot.MultiplyPoint3x4(centroid),
                    });
                }
            }
            m_RootLocalCentroids = samples.ToArray();
            m_SolverScratch = new HullSample[m_RootLocalCentroids.Length];
            // 基线浸没（米，世界尺度）：OnEnable 时船在设计位姿（水线偏移 + yaw），静水(y=0)下
            // 基线浸没 = 0 − 设计世界高度。
            for (int i = 0; i < m_RootLocalCentroids.Length; i++)
            {
                Vector3 designWorld = transform.TransformPoint(m_RootLocalCentroids[i].RootLocalCentroid);
                m_RootLocalCentroids[i].BaselineSubmersion = -designWorld.y;
            }

            m_Stopwatch = new Stopwatch();
            m_SearchParams.error = k_SearchError;
            m_SearchParams.maxIterations = k_MaxIterations;
            m_SearchParams.outputNormal = false;
        }

        void LateUpdate()
        {
            if (waterSurface == null || m_RootLocalCentroids == null || m_RootLocalCentroids.Length == 0)
            {
                return;
            }

            if (s_FrameStamp != Time.frameCount)
            {
                s_FrameStamp = Time.frameCount;
                s_FrameQueries = 0;
                s_FrameFailedQueries = 0;
                s_FrameQueryMs = 0.0;
            }

            // 姿态写入只经 y/欧拉 X/Z；x/z/yaw 原样读取，永不回写。
            var rootPos = transform.position;
            float yawDeg = transform.eulerAngles.y;
            Quaternion yawInverse = Quaternion.Inverse(Quaternion.Euler(0f, yawDeg, 0f));

            var p = BuoyancyParams.Default;
            p.MaxRollDeg = maxRollDeg;
            p.MaxPitchDeg = maxPitchDeg;
            var hullSamples = m_SolverScratch;
            int validSamples = 0;
            int failedThisInstance = 0;

            for (int i = 0; i < m_RootLocalCentroids.Length; i++)
            {
                Vector3 world = transform.TransformPoint(m_RootLocalCentroids[i].RootLocalCentroid);
                float3 target = new float3(world.x, world.y, world.z);
                m_SearchParams.startPositionWS = target;
                m_SearchParams.targetPositionWS = target;

                m_Stopwatch.Restart();
                bool ok = waterSurface.ProjectPointOnWaterSurface(m_SearchParams, out m_SearchResult);
                m_Stopwatch.Stop();
                s_FrameQueries++;
                s_FrameQueryMs += (double)m_Stopwatch.ElapsedTicks * 1000.0 / Stopwatch.Frequency;
                if (!ok)
                {
                    failedThisInstance++;
                    continue;
                }

                Vector3 inYawFrame = yawInverse * (world - rootPos);
                hullSamples[validSamples++] = new HullSample
                {
                    StarboardOffset = inYawFrame.x,
                    ForwardOffset = inYawFrame.z,
                    Submersion = m_SearchResult.projectedPositionWS.y - world.y,
                    BaselineSubmersion = m_RootLocalCentroids[i].BaselineSubmersion,
                };
            }
            s_FrameFailedQueries += failedThisInstance;

            // 周期观测行（FpsProbe 的 [Sango.M0] 10s 汇总同款纪律）：真机运行日志自证查询是否生效。
            // batchmode 无渲染帧 → 水面回读永不就绪 → 全失败属预期（见 evidence m2b-build-log.md）。
            if (Time.unscaledTime >= m_NextStatsLogTime)
            {
                m_NextStatsLogTime = Time.unscaledTime + 10f;
                Debug.Log($"[{nameof(VesselBuoyancy)}] {name}: samples={SampleCount} queries={s_FrameQueries} (failed {s_FrameFailedQueries}) " +
                          $"query_ms={s_FrameQueryMs:F3} target(h/r/p)={m_TargetHeave:F2}/{m_TargetRoll:F2}/{m_TargetPitch:F2} " +
                          $"smoothed={m_Heave.Value:F2}/{m_Roll.Value:F2}/{m_Pitch.Value:F2}", this);
            }

            // 本帧查询全废（数据未就绪等）：保持上帧姿态，不用残缺数据解算。
            if (validSamples == 0) return;

            // count 重载：只消费前 validSamples 个有效样点，缓冲尾部残留被忽略，无需切割分配。
            var attitude = BuoyancyAttitudeSolver.Solve(hullSamples, validSamples, p);
            m_TargetHeave = attitude.HeaveOffset;
            m_TargetRoll = attitude.RollDeg;
            m_TargetPitch = attitude.PitchDeg;

            float dt = Time.deltaTime;
            m_Heave = BuoyancyAttitudeSolver.Damp(m_Heave, m_TargetHeave, smoothingFrequencyHz, dt);
            m_Roll = BuoyancyAttitudeSolver.Damp(m_Roll, m_TargetRoll, smoothingFrequencyHz, dt);
            m_Pitch = BuoyancyAttitudeSolver.Damp(m_Pitch, m_TargetPitch, smoothingFrequencyHz, dt);

            // 施加：heave 只改根 y（基线 + 偏移）；roll/pitch 叠在脚本拥有的 yaw 上。
            rootPos.y = m_BaselineY + m_Heave.Value;
            transform.position = rootPos;
            transform.rotation = Quaternion.Euler(m_Pitch.Value, yawDeg, m_Roll.Value);
        }
    }
}
