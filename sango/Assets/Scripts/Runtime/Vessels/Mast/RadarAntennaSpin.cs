using UnityEngine;

namespace Sango.Vessels.Mast
{
    /// <summary>
    /// 桅顶雷达天线实体组件（P1 装配，00-REPORT §3/§4-4）：24 寸 HALO24 级罩体
    /// （程序化 cylinder+扁球冠组合，不引外部资产）+ TwinClock 驱动的扫掠旋转。
    /// yaw = <see cref="RadarAntennaMount.SweepYawDeg"/>(simTime, rpm) — 相位与
    /// web PPI sweepAzimuthRad 同源 sim_time（后端 spoke 扫掠节律 2.5 s/圈）。
    /// 时钟经 <see cref="clock"/> 注入（TwinClock 实例在 twin 数据面宿主里，
    /// Assembly-CSharp 一侧；asmdef 边界本组件不能自取）。未注入/未同步（NaN）
    /// 时天线静止等待 — 不退化为墙钟自由转（假同步比不转更糟）。
    /// standby 置位即停（雷达待机语义）。
    /// </summary>
    public class RadarAntennaSpin : MonoBehaviour
    {
        [Tooltip("扫掠转速 rpm（24 rpm ≡ 2.5 s/圈，后端 RadarXParams.rpm 默认）")]
        public float rpm = RadarAntennaMount.ScanRpmDefault;

        [Tooltip("待机停转（雷达 standby 语义；置位即停）")]
        public bool standby;

        [Tooltip("TwinClock 渲染钟（bridge 装配侧注入；null = 静止等待同步）")]
        public TwinClock clock;

        /// <summary>
        /// 程序化罩体：下半圆柱 + 上扁球冠，底面 = 挂点（holder origin = 桅顶法兰）。
        /// 幂等（重复调用不重建）。Unity 原生网格默认尺寸：cylinder 直径 1/高 2、
        /// sphere 直径 1 — localScale 即目标尺寸比。纯表现实体：剥 Collider
        /// （不进物理/射线，掩膜与深度相机射线不受桅顶罩干扰）。
        /// </summary>
        public void BuildRadome()
        {
            if (transform.Find("radome_cylinder") != null) return;
            float d = RadarAntennaMount.RadomeDiameterM;
            float cylH = RadarAntennaMount.RadomeCylinderHeightM;
            float capH = RadarAntennaMount.RadomeCapHeightM;

            var cylinder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            cylinder.name = "radome_cylinder";
            StripCollider(cylinder);
            cylinder.transform.SetParent(transform, false);
            cylinder.transform.localPosition = new Vector3(0f, cylH * 0.5f, 0f);
            cylinder.transform.localScale = new Vector3(d, cylH * 0.5f, d); // 默认高 2 ⇒ scale.y = h/2

            var cap = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            cap.name = "radome_cap";
            StripCollider(cap);
            cap.transform.SetParent(transform, false);
            cap.transform.localPosition = new Vector3(0f, cylH, 0f); // 扁球冠赤道面接圆柱顶
            cap.transform.localScale = new Vector3(d, capH, d);
        }

        /// <summary>按仿真时刻施加扫掠 yaw（度规换算在 RadarAntennaMount 纯函数，EditMode 钉）。</summary>
        public void ApplySweep(double simTimeS)
            => transform.localRotation = Quaternion.Euler(0f, RadarAntennaMount.SweepYawDeg((float)simTimeS, rpm), 0f);

        /// <summary>
        /// 门控采样（Update 同式；返回是否施加了扫掠，供 EditMode 钉门控行为）：
        /// standby / clock 未注入 / 未同步（NaN）三态都不转 — 静止等待同步。
        /// </summary>
        public bool SampleAndApplySweep()
        {
            if (standby || clock == null) return false;
            double sim = clock.Sample(Time.realtimeSinceStartupAsDouble);
            if (double.IsNaN(sim)) return false;
            ApplySweep(sim);
            return true;
        }

        void Update() => SampleAndApplySweep();

        static void StripCollider(GameObject primitive)
        {
            var collider = primitive.GetComponent<Collider>();
            if (collider == null) return;
            if (Application.isPlaying) Destroy(collider);
            else DestroyImmediate(collider);
        }
    }
}
