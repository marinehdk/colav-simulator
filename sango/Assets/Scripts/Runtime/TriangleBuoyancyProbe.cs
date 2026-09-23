using System.Collections.Generic;
using System.Diagnostics;
using Unity.Mathematics;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;
// System.Diagnostics.Debug 与 UnityEngine.Debug 二义，显式消歧。
using Debug = UnityEngine.Debug;

namespace Sango
{
    /// <summary>
    /// M0 冒烟负载：遍历所属 mesh 的全部三角形，逐三角形取三顶点质心做一次 HDRP Water CPU 水高查询，
    /// 累计每帧查询次数与查询耗时供 FpsProbe 读取。
    /// 决策：按任务要求保持逐三角形串行查询（阶段1 冒烟要测的就是最坏情况串行代价 + GPU 回读），
    /// 不做并行/Job 化优化。
    /// </summary>
    [DefaultExecutionOrder(100)] // 先于 FpsProbe(200) 的 LateUpdate，保证帧内统计完整
    public class TriangleBuoyancyProbe : MonoBehaviour
    {
        [Tooltip("要查询的 HDRP Water Surface，由 M0SceneBootstrapper 注入，也可在 Inspector 拖拽。")]
        public WaterSurface waterSurface;

        // 搜索参数取值对齐 HDRP 官方 WaterSamples/Scripts/Buoyancy.cs（Unity 6000.3 分支）。
        const float k_SearchError = 0.01f;
        const int k_MaxIterations = 8;

        // 帧级统计：本帧首个运行的 probe 重置，FpsProbe(执行序 200) 在帧末读取。
        static int s_FrameStamp;
        static int s_FrameQueries;
        static int s_FrameFailedQueries;
        static double s_FrameQueryMs;

        /// <summary>本帧水高查询总次数（含失败）。</summary>
        public static int FrameQueries => s_FrameQueries;
        /// <summary>本帧查询失败次数（scriptInteractions 未开 / 回读数据未就绪等）。</summary>
        public static int FrameFailedQueries => s_FrameFailedQueries;
        /// <summary>本帧查询累计耗时（毫秒）。</summary>
        public static double FrameQueryMs => s_FrameQueryMs;

        Stopwatch m_Stopwatch;
        WaterSearchParameters m_SearchParams; // 结构体复用：只初始化一次，循环内改字段，避免每三角形分配
        WaterSearchResult m_SearchResult;     // 同上
        Vector3[][] m_Vertices;
        int[][] m_Indices;
        Transform[] m_FilterTransforms;
        float m_LastSampledHeight; // 保留查询结果引用；便于 Inspector 观测

        void OnEnable()
        {
            // 规格要求引用同物体 MeshFilter；M0SceneBootstrapper 把 probe 挂在船根物体（mesh 在子物体上），
            // 故同物体没有 MeshFilter 时回退收集子物体。
            MeshFilter[] filters;
            var own = GetComponent<MeshFilter>();
            if (own != null)
            {
                filters = new[] { own };
            }
            else
            {
                filters = GetComponentsInChildren<MeshFilter>(false);
            }

            var verts = new List<Vector3[]>(filters.Length);
            var idx = new List<int[]>(filters.Length);
            var transforms = new List<Transform>(filters.Length);
            foreach (var filter in filters)
            {
                var mesh = filter != null ? filter.sharedMesh : null;
                if (mesh == null) continue;
                // 只读缓存顶点/索引拷贝与变换引用；绝不写 sharedMesh（primitive 内置 mesh 为全局只读资源）。
                verts.Add(mesh.vertices);
                idx.Add(mesh.triangles);
                transforms.Add(filter.transform);
            }

            if (verts.Count == 0)
            {
                Debug.LogWarning($"[{nameof(TriangleBuoyancyProbe)}] {name}: no MeshFilter with a mesh found, probe disabled.", this);
                enabled = false;
                return;
            }

            m_Vertices = verts.ToArray();
            m_Indices = idx.ToArray();
            m_FilterTransforms = transforms.ToArray();
            m_Stopwatch = new Stopwatch();

            // 结构体参数只在此初始化一次（对齐官方 Buoyancy 样本默认：不启用 deformation/normal 输出，
            // 冒烟测的就是浮力式"仅取高度"查询的代价）。
            m_SearchParams.error = k_SearchError;
            m_SearchParams.maxIterations = k_MaxIterations;
            m_SearchParams.outputNormal = false;
        }

        void LateUpdate()
        {
            if (waterSurface == null || m_Vertices == null)
            {
                return;
            }

            // 帧内首个 probe 负责重置累加器（主线程单线程访问，无竞争）。
            if (s_FrameStamp != Time.frameCount)
            {
                s_FrameStamp = Time.frameCount;
                s_FrameQueries = 0;
                s_FrameFailedQueries = 0;
                s_FrameQueryMs = 0.0;
            }

            for (int mi = 0; mi < m_Vertices.Length; mi++)
            {
                var localToWorld = m_FilterTransforms[mi].localToWorldMatrix;
                var verts = m_Vertices[mi];
                var idx = m_Indices[mi];

                for (int t = 0; t < idx.Length; t += 3)
                {
                    // 仿射变换下"局部质心变换 == 变换后三顶点质心"，每三角形只需一次矩阵乘。
                    Vector3 localCentroid = (verts[idx[t]] + verts[idx[t + 1]] + verts[idx[t + 2]]) / 3f;
                    Vector3 world = localToWorld.MultiplyPoint3x4(localCentroid);
                    float3 target = new float3(world.x, world.y, world.z);

                    // 不做跨帧 warm-start（官方样本用上帧 candidateLocationWS 做起点提示；
                    // 这里直接以目标点为起点，省去逐三角形提示存储，8 次迭代对冒烟足够）。
                    m_SearchParams.startPositionWS = target;
                    m_SearchParams.targetPositionWS = target;

                    m_Stopwatch.Restart();
                    // HDRP CPU 水高查询。文档:
                    // https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.WaterSurface.html
                    // 前置：WaterSurface.scriptInteractions = true 且 HDRP Asset 启用 waterScriptInteractionsMode。
                    bool ok = waterSurface.ProjectPointOnWaterSurface(m_SearchParams, out m_SearchResult);
                    m_Stopwatch.Stop();

                    s_FrameQueries++;
                    if (!ok)
                    {
                        s_FrameFailedQueries++;
                    }
                    else
                    {
                        // 结果字段（6000.3 核对）:
                        // https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.3/api/UnityEngine.Rendering.HighDefinition.WaterSearchResult.html
                        m_LastSampledHeight = m_SearchResult.projectedPositionWS.y;
                    }

                    s_FrameQueryMs += (double)m_Stopwatch.ElapsedTicks * 1000.0 / Stopwatch.Frequency;
                }
            }
        }
    }
}
