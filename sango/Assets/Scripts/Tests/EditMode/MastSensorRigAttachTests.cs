using NUnit.Framework;
using Sango.Vessels.Mast;
using UnityEngine;
using UnityEngine.TestTools;

namespace Sango.Tests
{
    /// <summary>
    /// P3-11（spec #91 前置批）EditMode 回归：MastSensorRig.Attach 的挂载语义。
    /// 根因（用户报障 + Player.log cam census 实证）：旧烘焙把 rig AddComponent 在
    /// "Twin Bridge" 本体上，而槽位船 Instantiate 的父 transform 恰是同一 GO——
    /// Attach 的 SetParent(槽位) 成环，Unity 6000.3.24f1 **静默拒绝**（批模式实证：
    /// 无异常、无日志、层级不变），rig 永久停在原点世界位姿 → EO 馈送不随船、
    /// 画面无目标船；且旧 Detach 清空 rig transform 全部子物体 = 顺带毁掉共享 GO
    /// 上的槽位船（Player.log 双份 vector arrows/wake rig 构建记录的来源）。
    /// 修复面：①环目标显式拒绝（保现场，不再假报成功）②Detach 只毁自建 mount
    /// holder ③场景烘焙把 rig 放独立子 GO（TwinBridgeSceneBuilder，构建期产物）。
    /// MastSensorRig 在 Assembly-CSharp（Runtime 根无 asmdef），EditMode 直引
    /// （同 IrrViewPass 测试先例——Runtime/Vessels/Mast 与测试同程序集可见性下
    /// Assembly-CSharp-Editor 可见）。
    /// </summary>
    public class MastSensorRigAttachTests
    {
        GameObject _rigGo;
        GameObject _ship;

        [SetUp]
        public void SetUp()
        {
            _rigGo = new GameObject("mast-rig");
            _ship = new GameObject("twin-own-ship");
        }

        [TearDown]
        public void TearDown()
        {
            if (_rigGo != null) Object.DestroyImmediate(_rigGo);
            if (_ship != null) Object.DestroyImmediate(_ship);
        }

        MastSensorRig Rig() => _rigGo.AddComponent<MastSensorRig>();

        [Test]
        public void Attach_ToStandaloneVessel_ParentsRigUnderVessel()
        {
            var rig = Rig();
            Assert.That(rig.Attach(_ship.transform), Is.True, "attach should succeed on a standalone vessel root");
            Assert.That(rig.transform.parent, Is.EqualTo(_ship.transform), "rig must physically parent under the vessel");
            Assert.That(rig.transform.localPosition, Is.EqualTo(Vector3.zero));
            Assert.That(rig.Attached, Is.True, "Attached requires live parentage, not just a feed camera");
            Assert.That(rig.BuiltMountCount, Is.EqualTo(MastCameraTable.Mounts.Length));
            Assert.That(rig.FeedCamera, Is.Not.Null);
            Assert.That(rig.FeedCamera.targetTexture, Is.Not.Null, "feed mount renders into its target texture");
        }

        [Test]
        public void Attach_CyclicTarget_RefusedWithoutMassacringSubtree()
        {
            // 旧烘焙病态：rig 与槽位工厂同 GO——槽位船（子物体）当挂载目标 = SetParent 成环。
            var shared = new GameObject("twin-bridge-shared");
            try
            {
                var rig = shared.AddComponent<MastSensorRig>();
                var slotShip = new GameObject("Twin vessel 0");
                slotShip.transform.SetParent(shared.transform, false); // 槽位 = rig GO 子物体
                var foreign = new GameObject("foreign-sibling");
                foreign.transform.SetParent(shared.transform, false);

                LogAssert.Expect(LogType.Error, new System.Text.RegularExpressions.Regex("attach refused.*subtree"));
                Assert.That(rig.Attach(slotShip.transform), Is.False,
                    "cyclic target must be refused loudly instead of the old silent phantom attach");
                Assert.That(slotShip == null, Is.False, "refusal must keep the slot ship alive (no Detach on the shared GO)");
                Assert.That(foreign == null, Is.False, "refusal must keep unrelated siblings alive");
                Assert.That(rig.Attached, Is.False);
            }
            finally
            {
                Object.DestroyImmediate(shared);
            }
        }

        [Test]
        public void Detach_DestroysOnlyMountHolders_ForeignChildrenSurvive()
        {
            var rig = Rig();
            Assert.That(rig.Attach(_ship.transform), Is.True);
            var foreign = new GameObject("foreign-child");
            foreign.transform.SetParent(rig.transform, false); // rig GO 上的非 mount 子物体

            rig.Detach();

            Assert.That(foreign == null, Is.False,
                "old Detach wiped every child of the rig transform (shared-GO bakes lost slot ships) — only mount holders may go");
            Assert.That(rig.transform.childCount, Is.EqualTo(1), "only the foreign child remains (mount holders are gone)");
            Assert.That(rig.transform.GetChild(0).name, Is.EqualTo("foreign-child"));
            Assert.That(rig.Attached, Is.False);
            Assert.That(rig.transform.parent, Is.Null);
        }

        [Test]
        public void Reattach_ToNewVessel_RebuildsFamilyOnce()
        {
            var rig = Rig();
            Assert.That(rig.Attach(_ship.transform), Is.True);
            var second = new GameObject("twin-own-ship-2");
            try
            {
                Assert.That(rig.Attach(second.transform), Is.True, "idempotent re-attach to a new vessel");
                Assert.That(rig.transform.parent, Is.EqualTo(second.transform));
                Assert.That(rig.BuiltMountCount, Is.EqualTo(MastCameraTable.Mounts.Length), "mounts rebuilt exactly once");
            }
            finally
            {
                Object.DestroyImmediate(second);
            }
        }
    }
}
