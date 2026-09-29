using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

namespace Sango
{
    /// <summary>
    /// M5 锚地布景（任务项 4）：静态锚泊船群，密度可调（Simulation 面板滑条 live 驱动，M4-A 模式）。
    /// 槽位表 = AnchorageSlots.Defaults（离线验证字面量；清障不变量由 AnchorageSlotsTests 守）。
    /// 锚泊船 = 纯布景：VesselBuoyancy 挂（随浪摇），无 WaypointFollower、无 WaterDecal——
    /// 锚泊船零 decal 开销（spike notes §7.1：多船锚泊时速度门限自动关的布景侧实现）。
    /// 摆位沿 PlaceCatalogShip 惯例：y = 编目水线偏移，rotation = Euler(0,heading,0)·Euler(0,bowYawDeg,0)。
    /// </summary>
    public class AnchorageFleet : MonoBehaviour
    {
        [Tooltip("锚泊槽位表（场景可覆写；默认 = AnchorageSlots.Defaults 离线验证字面量）。")]
        [SerializeField]
        AnchorageSlot[] m_Slots = AnchorageSlots.Defaults;

        [Tooltip("船只编目（按槽位档取 prefab/水线/艏向 yaw）。")]
        public VesselCatalog catalog;

        [Tooltip("浮力注入的 Water Surface（null 时锚泊船不挂浮力）。")]
        public WaterSurface waterSurface;

        int m_Density;
        Transform m_Root;

        /// <summary>当前锚泊船数。</summary>
        public int density => m_Density;

        /// <summary>
        /// M6：场景构建器注入自定义槽位表（海峡锚地字面量）后调 SetDensity 落船。
        /// 必须在 SetDensity 前调用；运行时改表不会自动重摆（重建走 SetDensity）。
        /// </summary>
        public void SetSlots(AnchorageSlot[] slots)
        {
            m_Slots = slots ?? AnchorageSlots.Defaults;
            m_Density = 0; // 表已换：旧计数失效，下次 SetDensity 整群重建
        }

        /// <summary>槽位总数（滑条上限）。</summary>
        public int maxDensity => m_Slots.Length;

        /// <summary>锚泊船 transforms（雷达/检测叠加等消费方取用）。</summary>
        public List<Transform> ShipTransforms()
        {
            var list = new List<Transform>();
            if (m_Root == null) return list;
            foreach (Transform child in m_Root) list.Add(child);
            return list;
        }

        /// <summary>
        /// 设定锚泊密度并整群重建（幂等；Simulation 面板滑条 live 驱动 = M4-A 即时生效模式）。
        /// 返回实际落位船数（编目缺档的槽位跳过并 LogError）。
        /// </summary>
        public int SetDensity(int count)
        {
            count = Mathf.Clamp(count, 0, m_Slots.Length);
            if (m_Root == null)
            {
                m_Root = new GameObject("Anchored Ships").transform;
                m_Root.SetParent(transform, false);
            }
            if (count == m_Density && m_Root.childCount == m_Density) return m_Density;

            for (int i = m_Root.childCount - 1; i >= 0; i--)
            {
                var child = m_Root.GetChild(i).gameObject;
                if (Application.isPlaying) Destroy(child);
                else DestroyImmediate(child);
            }
            m_Density = 0;

            for (int i = 0; i < count; i++)
            {
                var slot = m_Slots[i];
                if (catalog == null)
                {
                    Debug.LogError("[Sango.M5] AnchorageFleet catalog not wired — slot skipped");
                    break;
                }
                var entry = catalog.GetEntry(slot.vesselClass);
                if (entry?.prefab == null)
                {
                    Debug.LogError($"[Sango.M5] no catalog prefab for {slot.vesselClass} — anchorage slot {i} skipped");
                    continue;
                }
#if UNITY_EDITOR
                // 编辑期（场景构建器调用）：linked prefab instance——prefab/材质后续重建时场景船自动跟进
                var ship = (GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(entry.prefab);
#else
                var ship = Instantiate(entry.prefab);
#endif
                ship.name = $"Anchored.{slot.vesselClass}";
                ship.transform.SetParent(m_Root, false);
                ship.transform.position = new Vector3(slot.xz.x, entry.waterlineOffsetY, slot.xz.y);
                ship.transform.rotation = Quaternion.Euler(0f, slot.headingDeg, 0f) * Quaternion.Euler(0f, entry.bowYawDeg, 0f);
                if (waterSurface != null)
                {
                    ship.AddComponent<VesselBuoyancy>().waterSurface = waterSurface;
                }
                m_Density++;
            }

            Debug.Log($"[Sango.M5] anchorage density {m_Density}/{m_Slots.Length} (SetDensity {count})");
            return m_Density;
        }
    }
}
