using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P3-11（spec #91 前置批）EditMode 回归：TwinBridgeService 视口跟随重挂。
    /// 根因另一半：bridge attach 后 CameraRig.followShip 恒指 M6 demo 船（海峡内，
    /// 距 twin 槽位 ~5km）——URS 流（主相机）永远拍不到 twin 会话的船。修复面：
    /// 桅杆挂载成功即把 followShip 重挂到 twin 本船槽位（首次记忆原目标），
    /// DetachDataPlane 单点恢复（demo 零残留）。
    /// TwinBridgeService 在 Assembly-CSharp（Runtime 根无 asmdef），经反射驱动
    /// （TwinBridgeClockGuardTests 先例）；期望值不回声实现（重挂=槽位 transform、
    /// 恢复=原 demo transform、未重挂时 detach 不动 followShip）。
    /// </summary>
    public class TwinBridgeFollowRetargetTests
    {
        GameObject _go;
        Component _service;
        Component _rig; // Sango.CameraRig（Assembly-CSharp，反射驱动——asmdef 不引 Assembly-CSharp）
        Transform _demoShip;
        Transform _ownShip;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("twin-bridge-follow");
            _service = _go.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.TwinBridgeService"));
            var rigGo = new GameObject("camera-rig");
            _rig = rigGo.AddComponent(TestReflection.FindAssemblyCSharpType("Sango.CameraRig"));
            _demoShip = new GameObject("demo-vessel").transform;
            _ownShip = new GameObject("Twin vessel 0").transform;
            FollowShip = _demoShip;
            _service.GetType()
                .GetField("cameraRig", System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance)
                .SetValue(_service, _rig);
        }

        [TearDown]
        public void TearDown()
        {
            if (_go != null) Object.DestroyImmediate(_go);
            Object.DestroyImmediate(_rig.gameObject);
            Object.DestroyImmediate(_demoShip.gameObject);
            Object.DestroyImmediate(_ownShip.gameObject);
        }

        System.Reflection.BindingFlags Instance => System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;

        Transform FollowShip
        {
            get => (Transform)_rig.GetType().GetField("followShip").GetValue(_rig);
            set => _rig.GetType().GetField("followShip").SetValue(_rig, value);
        }

        void Retarget()
            => _service.GetType().GetMethod("RetargetCameraFollow", Instance)
                .Invoke(_service, new object[] { _ownShip, _ownShip.name });

        void Detach()
            => _service.GetType().GetMethod("DetachDataPlane", Instance).Invoke(_service, null);

        bool Retargeted => (bool)_service.GetType().GetField("m_FollowRetargeted", Instance).GetValue(_service);

        [Test]
        public void Retarget_FollowsOwnShip_AndRemembersDemoTarget()
        {
            // M6 场景的 BridgeCameraMount 焊死在 demo 船上（mount 分支优先于 followPos）
            // —P3-11 实证 followPos 已是 twin 本船而相机仍钉在 demo 桥楼。重挂必须同时
            // 摘 mount + 开 ship-relative，Bridge 视口才真正拍 twin 本船。
            _rig.GetType().GetField("bridgeMount").SetValue(_rig, new GameObject("demo bridge mount").transform);
            _rig.GetType().GetField("bowMount").SetValue(_rig, new GameObject("demo bow mount").transform);
            _rig.GetType().GetField("bridgeShipRelative").SetValue(_rig, false);
            Retarget();
            Assert.That(FollowShip, Is.EqualTo(_ownShip), "viewport camera must follow the twin own ship after retarget");
            Assert.That(_rig.GetType().GetField("bridgeMount").GetValue(_rig), Is.Null, "demo bridge mount detached while attached (mount branch would override followPos)");
            Assert.That(_rig.GetType().GetField("bowMount").GetValue(_rig), Is.Null, "demo bow mount detached while attached");
            Assert.That(_rig.GetType().GetField("bridgeShipRelative").GetValue(_rig), Is.True, "bridge view resolves ship-relative against the twin own ship");
            Assert.That(Retargeted, Is.True, "first retarget records the demo follow target");
            Detach();
            Assert.That(FollowShip, Is.EqualTo(_demoShip), "detach restores the original follow target (demo zero residue)");
            Assert.That(_rig.GetType().GetField("bridgeMount").GetValue(_rig), Is.Not.Null, "detach restores the demo bridge mount");
            Assert.That(_rig.GetType().GetField("bowMount").GetValue(_rig), Is.Not.Null, "detach restores the demo bow mount");
            Assert.That(_rig.GetType().GetField("bridgeShipRelative").GetValue(_rig), Is.False, "detach restores the original bridgeShipRelative");
            Assert.That(Retargeted, Is.False);
        }

        [Test]
        public void Detach_WithoutRetarget_LeavesFollowUntouched()
        {
            Detach();
            Assert.That(FollowShip, Is.EqualTo(_demoShip), "no attach happened — follow target untouched");
            Assert.That(Retargeted, Is.False);
        }

        [Test]
        public void Retarget_IsIdempotent_DemoMemoryKeptOnce()
        {
            Retarget();
            var demoMemory = (Transform)_service.GetType().GetField("m_DemoFollowShip", Instance).GetValue(_service);
            Assert.That(demoMemory, Is.EqualTo(_demoShip));
            Retarget(); // 二次调用（同船幂等路径）不得覆盖记忆
            demoMemory = (Transform)_service.GetType().GetField("m_DemoFollowShip", Instance).GetValue(_service);
            Assert.That(demoMemory, Is.EqualTo(_demoShip), "re-retarget must not overwrite the recorded demo target");
            Assert.That(FollowShip, Is.EqualTo(_ownShip));
        }
    }
}
