using System;
using UnityEngine;

namespace Sango
{
    /// <summary>流送 tile 分组：近带（两档常驻或 High swap 让位）/ 交叠（与近带互斥）/
    /// 外环（High 常开、Low 邻域 latch）。</summary>
    public enum M8StreamGroup
    {
        Near = 0,
        Overlap = 1,
        Ring = 2,
    }

    /// <summary>一个流送 tile 条目（bootstrapper 构建期注入；rect 为 Unity 世界 xz 米）。</summary>
    [Serializable]
    public class M8StreamingTile
    {
        public GameObject tileGo;
        public Terrain terrain;   // Low 档参数降档杠杆（外环 tile）
        public string tileName;
        public float xmin, zmin, xmax, zmax;
        public M8StreamGroup group;
    }

    /// <summary>装饰组条目：组随宿主 tile 激活态走（不产生悬空岸桥/渔排）。
    /// hostTileIndex = tiles 下标（构建期解析；hostTileName 仅为场景可读性保留）。</summary>
    [Serializable]
    public class M8DecorationGroup
    {
        public GameObject groupGo;
        public string hostTileName;
        public int hostTileIndex;
    }

    /// <summary>迟滞 latch 状态（纯数据；Component 持有，Plan 纯函数推进）。</summary>
    public struct M8StreamingLatches
    {
        /// <summary>true = NEAR（近带在管参考点覆盖）；false = FAR（交叠 9 已接管，仅 High）。</summary>
        public bool nearBandEngaged;
        public bool[] ringActive;

        public static M8StreamingLatches CreateInitial(int ringCount)
        {
            var l = new M8StreamingLatches { nearBandEngaged = true, ringActive = new bool[ringCount] };
            for (int i = 0; i < ringCount; i++) l.ringActive[i] = true; // 初始 = M7 语义（外环亮）
            return l;
        }
    }

    /// <summary>
    /// 流送判据纯函数集（EditMode 全覆盖；零分配——消费方每帧调用）。
    /// 坐标约定同 M6TerrainMath：Unity xz 米，区域中心 = 原点。
    /// 互斥语义（2026-09-29 编排者覆盖语义的 M8 接棒）：交叠 9 tile 与近带 4 tile 绝不同帧
    /// 同亮（共面 z-fight 是硬伤）。High 档参考点出带 &gt;2 km 时交叠 9 整组接管、近带整组
    /// 让位（覆盖无缝、分帧期间 ≥12 km 距离 + 8 km 雾遮挡）；回带内 500 m 才换回。
    /// Low 档近带恒开、交叠恒关，仅外环按参考点邻域逐 tile 迟滞亮灭。
    /// </summary>
    public static class M8TileStreamingPlan
    {
        /// <summary>参考点到近带（±NearBandHalfM 方块）的 Chebyshev 出带距离；带内为负
        /// （= 到最近边的距离取负），单调连续，直接喂迟滞 latch。</summary>
        public static float OutsideNearBandDistance(Vector2 xz)
        {
            float h = M8QualityProfile.NearBandHalfM;
            float dx = Mathf.Max(xz.x - h, -h - xz.x);
            float dz = Mathf.Max(xz.y - h, -h - xz.y);
            return Mathf.Max(dx, dz);
        }

        /// <summary>点到轴对齐矩形（Unity xz 米）的 Chebyshev 距离；矩形内 = 0。</summary>
        public static float RectDistanceXZ(Vector2 xz, float xmin, float zmin, float xmax, float zmax)
        {
            float dx = Mathf.Max(xmin - xz.x, xz.x - xmax);
            float dz = Mathf.Max(zmin - xz.y, xz.y - zmax);
            return Mathf.Max(Mathf.Max(dx, dz), 0f);
        }

        /// <summary>NEAR/FAR 迟滞：NEAR 态出带 &gt; FarEngageOutsideM 才换 FAR；
        /// FAR 态须回带内 &gt; NearReenterInsideM 才换回；带间保持（防抖）。</summary>
        public static bool NearBandEngaged(float outsideDist, bool current)
            => current ? outsideDist <= M8QualityProfile.FarEngageOutsideM
                       : outsideDist < -M8QualityProfile.NearReenterInsideM;

        /// <summary>外环 tile 迟滞：亮态 &gt; RingExitDistanceM 才灭；灭态 ≤ RingEnterDistanceM 才亮。</summary>
        public static bool RingEngaged(float distToRect, bool current)
            => current ? distToRect <= M8QualityProfile.RingExitDistanceM
                       : distToRect <= M8QualityProfile.RingEnterDistanceM;

        /// <summary>
        /// 推进 latch 并计算全表期望激活态（tiles + 装饰组合并编号：desired[tiles.Length+i]
        /// = 装饰组 i）。纯函数零分配；latch 状态经 ref 就地推进。
        /// High：near = latch、overlap = !latch、ring 恒真。
        /// Low：near 恒真、overlap 恒假、ring = 逐 tile 距离 latch。
        /// 装饰组 = 宿主 tile 期望态。
        /// </summary>
        public static void ComputeDesired(M8StreamingTile[] tiles, M8DecorationGroup[] decorations,
            M8QualityTier tier, Vector2 refXZ, ref M8StreamingLatches latches, bool[] desired)
        {
            int tileCount = tiles != null ? tiles.Length : 0;
            float outside = OutsideNearBandDistance(refXZ);
            latches.nearBandEngaged = NearBandEngaged(outside, latches.nearBandEngaged);
            bool high = tier == M8QualityTier.High;
            bool nearOn = high ? latches.nearBandEngaged : true;  // Low 近带恒开
            bool overlapOn = high && !latches.nearBandEngaged;    // 互斥：Low 恒关

            for (int i = 0; i < tileCount; i++)
            {
                var t = tiles[i];
                switch (t.group)
                {
                    case M8StreamGroup.Near:
                        desired[i] = nearOn;
                        break;
                    case M8StreamGroup.Overlap:
                        desired[i] = overlapOn;
                        break;
                    default: // Ring
                        if (high)
                        {
                            desired[i] = true;
                        }
                        else
                        {
                            float d = RectDistanceXZ(refXZ, t.xmin, t.zmin, t.xmax, t.zmax);
                            bool cur = latches.ringActive != null && i < latches.ringActive.Length && latches.ringActive[i];
                            bool next = RingEngaged(d, cur);
                            if (latches.ringActive != null && i < latches.ringActive.Length) latches.ringActive[i] = next;
                            desired[i] = next;
                        }
                        break;
                }
            }

            int decoCount = decorations != null ? decorations.Length : 0;
            for (int i = 0; i < decoCount; i++)
            {
                int host = decorations[i].hostTileIndex;
                desired[tileCount + i] = host >= 0 && host < tileCount && desired[host];
            }
        }
    }

    /// <summary>
    /// 分帧应用队列（纯逻辑，EditMode 可测）：按 desired vs actual 重建待应用变更，
    /// 每次 TryDequeue 只出一个变更（每帧 ≤1 次 SetActive 防激活尖峰）。排序：激活先于
    /// 停用，同类按距参考点距离升序（参考点周边先亮）。容量固定、插入排序，零稳态分配。
    /// </summary>
    public class M8StreamingChangeQueue
    {
        public struct Change
        {
            public int index;
            public bool activate;
        }

        readonly Change[] m_Items;
        readonly float[] m_Keys;
        int m_Count;

        public M8StreamingChangeQueue(int capacity)
        {
            m_Items = new Change[capacity];
            m_Keys = new float[capacity];
        }

        public int Pending => m_Count;

        /// <summary>替换式重建待应用队列（desired[i] != actual[i] 入队）。distanceToRef =
        /// 各条目到参考点的排序距离（tiles = tile 矩形距离、装饰组 = 宿主 tile 距离）。</summary>
        public void Rebuild(bool[] desired, bool[] actual, float[] distanceToRef)
        {
            m_Count = 0;
            for (int i = 0; i < desired.Length; i++)
            {
                if (desired[i] == actual[i]) continue;
                m_Items[m_Count] = new Change { index = i, activate = desired[i] };
                float d = distanceToRef != null && i < distanceToRef.Length ? distanceToRef[i] : 0f;
                m_Keys[m_Count] = (desired[i] ? 0f : 1e9f) + d; // 激活优先，同类近者先
                m_Count++;
            }
            for (int i = 1; i < m_Count; i++) // 插入排序（N ≤ 38）
            {
                var item = m_Items[i];
                var key = m_Keys[i];
                int j = i - 1;
                while (j >= 0 && m_Keys[j] > key)
                {
                    m_Items[j + 1] = m_Items[j];
                    m_Keys[j + 1] = m_Keys[j];
                    j--;
                }
                m_Items[j + 1] = item;
                m_Keys[j + 1] = key;
            }
        }

        /// <summary>出队一个变更（每帧至多调一次 = 分帧预算）；空返回 false。</summary>
        public bool TryDequeue(out Change change)
        {
            if (m_Count == 0)
            {
                change = default;
                return false;
            }
            change = m_Items[0];
            for (int i = 1; i < m_Count; i++) m_Items[i - 1] = m_Items[i];
            m_Count--;
            return true;
        }

        public void Clear() => m_Count = 0;
    }

    /// <summary>
    /// M8 画质双档 + 交叠 tile 互斥流送（Runtime 薄壳；判据/队列纯函数在
    /// M8TileStreamingPlan / M8StreamingChangeQueue，EditMode 全覆盖）。
    /// bootstrapper 构建期注入 tiles（29：近 4/交叠 9/外环 16）+ 装饰组（9）+ 参考点
    /// （主船，fallback 主相机）+ 太阳光。每帧：推进 latch → desired vs actual → 重建
    /// 队列 → 至多应用 1 个 SetActive。档切换（GUI 下拉/L 键/程序 API M8Quality）：
    /// 外环 Terrain 参数降档/回写基线 + 太阳影档 + 全表重同步（仍走分帧队列）。
    /// High 档基线 = M7 终态：外环/近带/装饰参数经基线捕获原样回写，零漂移。
    /// </summary>
    public class M8TileStreaming : MonoBehaviour
    {
        [Tooltip("流送 tile 表（近带 4 + 交叠 9 + 外环 16；bootstrapper 注入，rect 为世界 xz 米）")]
        public M8StreamingTile[] tiles;

        [Tooltip("装饰组（岸桥/箱堆/渔排；随宿主 tile 激活态走）")]
        public M8DecorationGroup[] decorationGroups;

        [Tooltip("参考点：主船 Transform；空则回退主相机位置，再空 = 原点")]
        public Transform reference;

        [Tooltip("太阳方向光（Low 档软影→硬影杠杆；空则跳过阴影切换）")]
        public Light sunLight;

        M8StreamingLatches m_Latches;
        bool[] m_Actual;
        bool[] m_Desired;
        bool[] m_QueuedDesired;
        float[] m_DistToRef;
        M8StreamingChangeQueue m_Queue;
        int m_AppliedTier = -1;

        // 外环 Terrain 参数基线（首次应用前捕获 = M7 终态；High 档回写保证零漂移）
        int[] m_BaseRingTileIndex;
        float[] m_BaseTreeDistance, m_BaseDetailDistance, m_BasePixelError;
        LightShadows m_BaseSunShadows;
        bool m_BaselineCaptured;

        int TileCount => tiles != null ? tiles.Length : 0;
        int DecoCount => decorationGroups != null ? decorationGroups.Length : 0;
        int RingCount
        {
            get
            {
                int n = 0;
                for (int i = 0; i < TileCount; i++)
                    if (tiles[i].group == M8StreamGroup.Ring) n++;
                return n;
            }
        }

        /// <summary>当前已应用档（OnEnable 前读 = High）。</summary>
        public M8QualityTier appliedTier => m_AppliedTier < 0 ? M8QualityTier.High : (M8QualityTier)m_AppliedTier;

        void Awake()
        {
            int count = TileCount + DecoCount;
            m_Actual = new bool[count];
            m_Desired = new bool[count];
            m_DistToRef = new float[count];
            m_QueuedDesired = null; // 强制首次重建
            m_Latches = M8StreamingLatches.CreateInitial(RingCount);
            for (int i = 0; i < TileCount; i++)
                m_Actual[i] = tiles[i].tileGo != null && tiles[i].tileGo.activeSelf;
            for (int i = 0; i < DecoCount; i++)
                m_Actual[TileCount + i] = decorationGroups[i].groupGo != null && decorationGroups[i].groupGo.activeSelf;
            m_Queue = new M8StreamingChangeQueue(Mathf.Max(1, count));
        }

        void OnEnable()
        {
            M8Quality.Register(this);
            ApplyTier(M8Quality.CurrentTier); // 全量重同步（含场景初始态与静态档对齐）
        }

        void OnDisable() => M8Quality.Unregister(this);

        /// <summary>切档入口（幂等；重复同档直接返回）。外环 Terrain 参数与太阳影档
        /// 立即生效，tile 激活态差异走分帧队列（每帧 ≤1 次 SetActive）。</summary>
        public void ApplyTier(M8QualityTier tier)
        {
            if ((int)tier == m_AppliedTier) return;
            CaptureBaseline();
            m_AppliedTier = (int)tier;
            ApplyTerrainParams(tier);
            m_QueuedDesired = null; // 下一帧全量重建
        }

        void CaptureBaseline()
        {
            if (m_BaselineCaptured) return;
            m_BaselineCaptured = true;
            int ring = RingCount;
            m_BaseRingTileIndex = new int[ring];
            m_BaseTreeDistance = new float[ring];
            m_BaseDetailDistance = new float[ring];
            m_BasePixelError = new float[ring];
            int k = 0;
            for (int i = 0; i < TileCount && k < ring; i++)
            {
                if (tiles[i].group != M8StreamGroup.Ring || tiles[i].terrain == null) continue;
                m_BaseRingTileIndex[k] = i;
                m_BaseTreeDistance[k] = tiles[i].terrain.treeDistance;
                m_BaseDetailDistance[k] = tiles[i].terrain.detailObjectDistance;
                m_BasePixelError[k] = tiles[i].terrain.heightmapPixelError;
                k++;
            }
            if (sunLight != null) m_BaseSunShadows = sunLight.shadows;
        }

        void ApplyTerrainParams(M8QualityTier tier)
        {
            if (m_BaseRingTileIndex == null) return;
            bool low = tier == M8QualityTier.Low;
            for (int k = 0; k < m_BaseRingTileIndex.Length; k++)
            {
                var terrain = tiles[m_BaseRingTileIndex[k]].terrain;
                if (terrain == null) continue;
                terrain.treeDistance = low ? M8QualityProfile.LowFarTreeDistanceM : m_BaseTreeDistance[k];
                terrain.detailObjectDistance = low ? M8QualityProfile.LowFarDetailObjectDistanceM : m_BaseDetailDistance[k];
                terrain.heightmapPixelError = low ? M8QualityProfile.LowFarHeightmapPixelError : m_BasePixelError[k];
            }
            if (sunLight != null)
                sunLight.shadows = low ? LightShadows.Hard : m_BaseSunShadows;
        }

        void Update()
        {
            int count = TileCount + DecoCount;
            if (count == 0) return;
            var refXZ = ResolveReferenceXZ();
            var tier = appliedTier;
            M8TileStreamingPlan.ComputeDesired(tiles, decorationGroups, tier, refXZ, ref m_Latches, m_Desired);

            bool desiredChanged = m_QueuedDesired == null;
            if (!desiredChanged)
            {
                for (int i = 0; i < count; i++)
                {
                    if (m_QueuedDesired[i] != m_Desired[i]) { desiredChanged = true; break; }
                }
            }
            if (desiredChanged)
            {
                for (int i = 0; i < TileCount; i++)
                    m_DistToRef[i] = M8TileStreamingPlan.RectDistanceXZ(refXZ, tiles[i].xmin, tiles[i].zmin, tiles[i].xmax, tiles[i].zmax);
                for (int i = 0; i < DecoCount; i++)
                {
                    int host = decorationGroups[i].hostTileIndex;
                    m_DistToRef[TileCount + i] = host >= 0 && host < TileCount ? m_DistToRef[host] : 0f;
                }
                m_Queue.Rebuild(m_Desired, m_Actual, m_DistToRef);
                if (m_QueuedDesired == null) m_QueuedDesired = new bool[count];
                Array.Copy(m_Desired, m_QueuedDesired, count);
            }

            if (m_Queue.TryDequeue(out var change)) // 分帧预算：每帧 ≤1 次 SetActive
            {
                var go = change.index < TileCount ? tiles[change.index].tileGo
                    : decorationGroups[change.index - TileCount].groupGo;
                if (go != null) go.SetActive(change.activate);
                m_Actual[change.index] = change.activate;
            }
        }

        Vector2 ResolveReferenceXZ()
        {
            if (reference != null) return new Vector2(reference.position.x, reference.position.z);
            var cam = Camera.main; // fallback：主相机（ask 语义：主船 fallback 相机）
            if (cam != null) return new Vector2(cam.transform.position.x, cam.transform.position.z);
            return Vector2.zero;
        }
    }

    /// <summary>
    /// M8 画质程序 API（静态入口；出片脚本/Recorder 可直接切档，无需找场景对象）。
    /// 档值静态常驻（无 streamer 的场景也记账），streamer 在场时立即应用。
    /// </summary>
    public static class M8Quality
    {
        public static M8QualityTier CurrentTier { get; private set; } = M8QualityTier.High;

        static M8TileStreaming s_Active;

        public static void Register(M8TileStreaming streamer) => s_Active = streamer;
        public static void Unregister(M8TileStreaming streamer)
        {
            if (ReferenceEquals(s_Active, streamer)) s_Active = null;
        }

        /// <summary>切档并应用；返回是否找到在场的 streamer（纯静态记账恒成功）。</summary>
        public static bool SetTier(M8QualityTier tier)
        {
            CurrentTier = tier;
            if (s_Active != null)
            {
                s_Active.ApplyTier(tier);
                return true;
            }
            return false;
        }

        /// <summary>GUI 下拉回调入口（越界钳位）。</summary>
        public static bool SetTierFromDropdownIndex(int index)
            => SetTier(M8QualityProfile.TierFromDropdownIndex(index));

        /// <summary>High ↔ Low 循环（L 键入口；键位账本核对结论：L 全工程空闲）。</summary>
        public static bool CycleTier()
            => SetTier(CurrentTier == M8QualityTier.High ? M8QualityTier.Low : M8QualityTier.High);

        /// <summary>GUI 镜像用下拉索引。</summary>
        public static int DropdownIndex => (int)CurrentTier;
    }
}
