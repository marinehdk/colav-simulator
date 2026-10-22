using NUnit.Framework;
using Sango.Vessels.Mast;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P1 主桅顶 X 波段雷达天线装配纯函数/组件测试（00-REPORT §3 A案定案）。
    /// 挂点常量与后端权威登记（colav_simulator/core/mast_cameras.py RADAR_* 平行表）
    /// 双向对齐——任何一侧改动必须同步另一侧（后端 parity 测试钉同一字面量；
    /// 雷达行走平行表，不进相机标定族 MastCameraTable.Mounts）。
    /// 扫掠相位与 web PPI sweepAzimuthRad（radar-ppi.js:83-86）同式同源 sim_time。
    /// </summary>
    public class RadarAntennaMountTests
    {
        [Test]
        public void Constants_ParityWithBackendMastCameras()
        {
            Assert.That(RadarAntennaMount.MountId, Is.EqualTo("mast_top_xband"),
                "sensor-model-v1 §3 冻结词汇 = RadarXParams.mount_id 默认（后端 MOUNT_ID_RADAR_X_DEFAULT 同串）");
            Assert.That(RadarAntennaMount.HeightM, Is.EqualTo(12.98f), "FBX 实测空气干舷工程口径（FBX 属性 12.9）");
            Assert.That(RadarAntennaMount.ForwardOffsetM, Is.EqualTo(2.1f), "桅中心线舯前 +2.1 m");
            Assert.That(RadarAntennaMount.StarboardOffsetM, Is.EqualTo(0f), "桅中心线");
        }

        [Test]
        public void Radome_Envelope_Halo24_24Inch()
        {
            Assert.That(RadarAntennaMount.RadomeDiameterM, Is.EqualTo(0.61f), "HALO24 24 寸罩 Ø610 mm（手册 988-12307-003）");
            Assert.That(RadarAntennaMount.RadomeHeightM, Is.EqualTo(0.225f), "罩高 225 mm");
            Assert.That(RadarAntennaMount.RadomeCylinderHeightM + RadarAntennaMount.RadomeCapHeightM,
                Is.EqualTo(RadarAntennaMount.RadomeHeightM).Within(1e-6f), "圆柱段 + 扁球冠 = 总高");
            Assert.That(RadarAntennaMount.ScanRpmDefault, Is.EqualTo(24f), "后端 RadarXParams.rpm 默认同源");
        }

        [Test]
        public void LocalPosition_ShipFrameAnchor()
        {
            Assert.That(RadarAntennaMount.LocalPosition, Is.EqualTo(new Vector3(0f, 12.98f, 2.1f)),
                "ship frame: +z 艏/+x 右舷/+y 上、原点舯部水线 — MastCameraTable 同约定");
        }

        [Test]
        public void WorldPosition_PureFunctionOfVesselPose()
        {
            var position = new Vector3(100f, 0f, -50f);
            Assert.That(RadarAntennaMount.WorldPosition(position, Quaternion.identity),
                Is.EqualTo(new Vector3(100f, 12.98f, -47.9f)));

            var yawed = Quaternion.Euler(0f, 90f, 0f);
            Assert.That(RadarAntennaMount.WorldPosition(position, yawed),
                Is.EqualTo(new Vector3(102.1f, 12.98f, -50f)).Within(1e-4f),
                "yaw 90°（右舷向）：挂点舯前 2.1 m 转到 +x");
        }

        [Test]
        public void ScanPeriod_RpmConvention()
        {
            Assert.That(RadarAntennaMount.ScanPeriodS(24f), Is.EqualTo(2.5f), "24 rpm ⇒ 2.5 s/圈");
            Assert.That(RadarAntennaMount.ScanPeriodS(60f), Is.EqualTo(1f).Within(1e-5f), "近程 60 rpm ⇒ 1 s");
            Assert.That(RadarAntennaMount.ScanPeriodS(0f), Is.EqualTo(float.PositiveInfinity), "rpm ≤ 0 = 不转");
        }

        [Test]
        public void SweepPhase_SameFormulaAsWebPpi()
        {
            Assert.That(RadarAntennaMount.SweepPhaseRad(0f, 24f), Is.EqualTo(0f).Within(1e-6f));
            Assert.That(RadarAntennaMount.SweepPhaseRad(1.25f, 24f), Is.EqualTo(Mathf.PI).Within(1e-4f), "半圈");
            Assert.That(RadarAntennaMount.SweepPhaseRad(2.5f, 24f), Is.EqualTo(0f).Within(1e-4f), "整圈回卷");
            Assert.That(RadarAntennaMount.SweepPhaseRad(-0.25f, 24f), Is.EqualTo(0.9f * 2f * Mathf.PI).Within(1e-4f),
                "负时刻正回卷 — web sweepAzimuthRad ((t/p)%1+1)%1 同式（radar-ppi.js:83-86）");
            Assert.That(RadarAntennaMount.SweepPhaseRad(0.5f, 60f), Is.EqualTo(Mathf.PI).Within(1e-4f), "60 rpm ⇒ 1 s/圈");
            Assert.That(RadarAntennaMount.SweepPhaseRad(1f, 0f), Is.EqualTo(0f), "rpm ≤ 0 相位恒 0");
        }
    }

    public class RadarAntennaSpinTests
    {
        [Test]
        public void ApplySweep_PhaseAndRpmConversion()
        {
            var go = new GameObject("antenna");
            try
            {
                var spin = go.AddComponent<RadarAntennaSpin>(); // rpm 默认 24
                spin.ApplySweep(1.25);
                Assert.That(go.transform.localEulerAngles.y, Is.EqualTo(180f).Within(1e-3f), "1.25 s = 半圈（2.5 s/圈）");
                spin.ApplySweep(0.625);
                Assert.That(go.transform.localEulerAngles.y, Is.EqualTo(90f).Within(1e-3f));
                spin.ApplySweep(2.5);
                Assert.That(go.transform.localEulerAngles.y, Is.EqualTo(0f).Within(1e-3f), "整圈回卷");
                spin.rpm = 60f;
                spin.ApplySweep(0.5);
                Assert.That(go.transform.localEulerAngles.y, Is.EqualTo(180f).Within(1e-3f), "60 rpm ⇒ 1 s/圈");
                // 方向惯例：yaw 正 = 自上顺时针 = 自艏向右舷（MastCameraTable az 90° = +x 同式）
                spin.rpm = 24f;
                spin.ApplySweep(0.625);
                Assert.That((go.transform.localRotation * Vector3.forward - Vector3.right).magnitude,
                    Is.LessThan(1e-4f), "同上:Vector3 comparer 忽略 Within,用 magnitude 标量断言");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void SampleAndApply_GatedByStandbyClockAndSync()
        {
            var go = new GameObject("antenna");
            try
            {
                var spin = go.AddComponent<RadarAntennaSpin>();
                var clock = new TwinClock();
                spin.clock = clock;
                Assert.That(spin.SampleAndApplySweep(), Is.False, "未同步（NaN）静止等待，不自由转");
                Assert.That(go.transform.localRotation, Is.EqualTo(Quaternion.identity));

                spin.standby = true;
                clock.OnFrame(0.625, Time.realtimeSinceStartupAsDouble, 1.0);
                Assert.That(spin.SampleAndApplySweep(), Is.False, "standby 置位即停（雷达待机语义）");
                Assert.That(go.transform.localRotation, Is.EqualTo(Quaternion.identity));

                spin.standby = false;
                Assert.That(spin.SampleAndApplySweep(), Is.True, "已同步且非 standby ⇒ 施加扫掠");
                Assert.That(go.transform.localEulerAngles.y, Is.GreaterThan(45f).And.LessThan(135f),
                    "锚在 0.625 s（90° 相位）+ 测试内墙钟微量前进");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void SampleAndApply_NullClock_IsNoOp()
        {
            var go = new GameObject("antenna");
            try
            {
                var spin = go.AddComponent<RadarAntennaSpin>();
                Assert.That(spin.SampleAndApplySweep(), Is.False, "clock 未注入（null）静止等待");
                Assert.That(go.transform.localRotation, Is.EqualTo(Quaternion.identity));
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void BuildRadome_ProceduralHalo24Envelope()
        {
            var go = new GameObject("antenna");
            try
            {
                var spin = go.AddComponent<RadarAntennaSpin>();
                spin.BuildRadome();
                spin.BuildRadome(); // 幂等
                Assert.That(go.transform.childCount, Is.EqualTo(2));

                var cylinder = go.transform.Find("radome_cylinder");
                var cap = go.transform.Find("radome_cap");
                Assert.That(cylinder, Is.Not.Null);
                Assert.That(cap, Is.Not.Null);

                // Unity 原生网格默认尺寸：cylinder 径 1/高 2、sphere 径 1 ⇒ scale 即目标尺寸比
                Assert.That(cylinder.localScale,
                    Is.EqualTo(new Vector3(RadarAntennaMount.RadomeDiameterM, RadarAntennaMount.RadomeCylinderHeightM * 0.5f, RadarAntennaMount.RadomeDiameterM)),
                    "径 0.61；默认高 2 ⇒ scale.y = 段高 0.15 / 2");
                Assert.That(cylinder.localPosition, Is.EqualTo(new Vector3(0f, 0.075f, 0f)), "底面 = 挂点（holder origin = 法兰）");
                Assert.That(cap.localScale,
                    Is.EqualTo(new Vector3(RadarAntennaMount.RadomeDiameterM, RadarAntennaMount.RadomeCapHeightM, RadarAntennaMount.RadomeDiameterM)),
                    "扁球冠：赤道径 0.61、极向高 = 冠高 0.075");
                Assert.That(cap.localPosition, Is.EqualTo(new Vector3(0f, 0.15f, 0f)), "赤道面接圆柱顶；总高 0.225");
                Assert.That(cylinder.GetComponent<Collider>(), Is.Null, "纯表现实体剥 Collider（不进物理/射线）");
                Assert.That(cap.GetComponent<Collider>(), Is.Null);
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }
    }

    /// <summary>
    /// P1 装配分支回归：MastSensorRig.Attach 建桅顶天线实体（父节点 =
    /// FCB45_MastAndSensors 桅顶网格节点，世界坐标由 ship-local 纯函数锚定；
    /// 非 FCB45 槽位船回退 vessel root）。Detach 只毁自建 holder。
    /// </summary>
    public class MastSensorRigRadarAntennaTests
    {
        GameObject _rigGo;
        GameObject _ship;
        Transform _mastNode;

        [SetUp]
        public void SetUp()
        {
            _rigGo = new GameObject("mast-rig");
            _ship = new GameObject("twin-own-ship");
            var mast = new GameObject("FCB45_MastAndSensors");
            mast.transform.SetParent(_ship.transform, false);
            mast.transform.localPosition = new Vector3(1f, 2f, 3f); // FBX 节点自有变换 — worldPositionStays 锚定
            mast.transform.localRotation = Quaternion.Euler(0f, 30f, 0f);
            _mastNode = mast.transform;
        }

        [TearDown]
        public void TearDown()
        {
            if (_rigGo != null) Object.DestroyImmediate(_rigGo);
            if (_ship != null) Object.DestroyImmediate(_ship);
        }

        [Test]
        public void Attach_BuildsAntennaUnderMastNode_AtPureMathWorldPose()
        {
            _ship.transform.SetPositionAndRotation(new Vector3(10f, 0f, -5f), Quaternion.Euler(0f, 90f, 0f));
            var rig = _rigGo.AddComponent<MastSensorRig>();
            Assert.That(rig.Attach(_ship.transform), Is.True);

            var antenna = rig.RadarAntenna;
            Assert.That(antenna, Is.Not.Null, "装配分支建出天线实体");
            Assert.That(antenna.transform.IsChildOf(_mastNode), Is.True, "父节点 = FCB45_MastAndSensors 桅顶节点");
            // magnitude 标量断言:Unity NUnit 的 Vector3 comparer 忽略 Within tolerance
            // (精确比较,SetParent(worldPositionStays) 往返差 ~1e-6 即挂)——TwinCameraBehaviorTests 同款模式
            Assert.That((antenna.transform.position
                - RadarAntennaMount.WorldPosition(new Vector3(10f, 0f, -5f), Quaternion.Euler(0f, 90f, 0f))).magnitude,
                Is.LessThan(1e-4f),
                "世界坐标由 ship-local 纯函数锚定（与桅节点自身平移/旋转无关）");
            Assert.That(rig.BuiltMountCount, Is.EqualTo(MastCameraTable.Mounts.Length), "相机族不受装配分支扰动");
        }

        [Test]
        public void Attach_NonFcb45Vessel_FallsBackToVesselRoot()
        {
            Object.DestroyImmediate(_mastNode.gameObject);
            var rig = _rigGo.AddComponent<MastSensorRig>();
            Assert.That(rig.Attach(_ship.transform), Is.True);

            var antenna = rig.RadarAntenna;
            Assert.That(antenna, Is.Not.Null);
            Assert.That(antenna.transform.parent, Is.EqualTo(_ship.transform), "非 FCB45 船回退 vessel root");
            Assert.That(antenna.transform.position, Is.EqualTo(RadarAntennaMount.LocalPosition).Within(1e-5f));
        }

        [Test]
        public void Detach_DestroysAntennaHolder_ForeignMastChildrenSurvive()
        {
            var rig = _rigGo.AddComponent<MastSensorRig>();
            Assert.That(rig.Attach(_ship.transform), Is.True);
            var holder = rig.RadarAntenna.gameObject;
            var foreign = new GameObject("foreign-mast-child");
            foreign.transform.SetParent(_mastNode, false);

            rig.Detach();

            Assert.That(rig.RadarAntenna, Is.Null);
            Assert.That(holder == null, Is.True, "天线 holder 随 Detach 销毁");
            Assert.That(foreign == null, Is.False, "桅顶节点上非自建子物体存活（只毁自建物语义）");
        }
    }
}
