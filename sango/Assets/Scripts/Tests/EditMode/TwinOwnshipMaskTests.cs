using NUnit.Framework;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Rendering;

namespace Sango.Tests
{
    // ownship-mask-v1.md §3 黄金向量(编码器=Sango.Vessels 程序集 OwnshipMaskRle):逐行 uint16 LE 行程码、恒以 0 游程开头、
    // 顶行先行(编码器负责垂直翻转)——与 tests/test_sango_detector_mask.py 的
    // decode_mask_rle 对拍同一向量,锁跨语言格式与行序。
    public class TwinOwnshipMaskTests
    {
        static NativeArray<byte> BottomFirst(byte[] rowsTopFirst, int width, int height)
        {
            var bottom = new byte[rowsTopFirst.Length];
            for (int row = 0; row < height; row++)
                System.Array.Copy(rowsTopFirst, row * width, bottom, (height - 1 - row) * width, width);
            return new NativeArray<byte>(bottom, Allocator.Temp);
        }

        [Test]
        public void EncodeRleMatchesFrozenGoldenVector()
        {
            // 4×3 顶行先行位图:0000/0110/0000 → 每行 RLE 4 / 1,2,1 / 4(uint16 LE)
            var readback = BottomFirst(new byte[] {
                0,0,0,0,
                0,1,1,0,
                0,0,0,0,
            }, 4, 3);
            Assert.AreEqual(new byte[] { 0x04,0x00, 0x01,0x00,0x02,0x00,0x01,0x00, 0x04,0x00 },
                OwnshipMaskRle.Encode(readback, 4, 3));
            readback.Dispose();
        }

        [Test]
        public void EncodeRleEmitsLeadingZeroRunWhenRowStartsWhite()
        {
            // 行首即 1:首游程=0 个 0(契约恒以 0 游程开头)
            var readback = BottomFirst(new byte[] { 1,1,0 }, 3, 1);
            Assert.AreEqual(new byte[] { 0x00,0x00, 0x02,0x00, 0x01,0x00 },
                OwnshipMaskRle.Encode(readback, 3, 1));
            readback.Dispose();
        }

        [Test]
        public void EncodeRleAllZeroMaskIsOneRunPerRow()
        {
            var readback = BottomFirst(new byte[6 * 4], 6, 4);
            Assert.AreEqual(new byte[] { 0x06,0x00, 0x06,0x00, 0x06,0x00, 0x06,0x00 },
                OwnshipMaskRle.Encode(readback, 6, 4));
            readback.Dispose();
        }

        [Test]
        public void EncodeRleRejectsShortReadback()
        {
            var readback = new NativeArray<byte>(3, Allocator.Temp);
            Assert.Throws<System.ArgumentException>(() => OwnshipMaskRle.Encode(readback, 4, 1));
            readback.Dispose();
        }

        // TwinOwnshipMaskPublisher 住在 Assembly-CSharp(测试 asmdef 不可引用),
        // 按名反射锁 RefreshShip 的装配窗口重扫契约:空扫描(层级未激活/无渲染器)
        // 必须置空缓存下帧重扫,否则空表永久卡死 → 全零掩膜本船裸奔(20261020 根因)。
        static System.Reflection.MethodInfo RefreshShipMethod()
        {
            var type = System.Type.GetType("Sango.TwinOwnshipMaskPublisher, Assembly-CSharp");
            Assert.NotNull(type, "TwinOwnshipMaskPublisher 应存在于 Assembly-CSharp");
            return type.GetMethod("RefreshShip", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        }

        [Test]
        public void RefreshShipRescansWhenScanLandsEmpty()
        {
            var method = RefreshShipMethod();
            var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
            var publisher = new GameObject("mask publisher under test").AddComponent(method.DeclaringType);
            var shipField = method.DeclaringType.GetField("m_Ship", flags);
            var renderersField = method.DeclaringType.GetField("m_Renderers", flags);
            try
            {
                var ship = new GameObject("own ship"); // 激活但渲染器子物体未激活 = 装配窗口
                var hull = GameObject.CreatePrimitive(PrimitiveType.Cube);
                hull.transform.SetParent(ship.transform, false);
                hull.SetActive(false);

                Assert.IsFalse((bool)method.Invoke(publisher, new object[] { ship }), "空扫描应返回未就绪");
                Assert.IsNull(shipField.GetValue(publisher), "空扫描必须置空 m_Ship 触发下帧重扫");

                hull.SetActive(true); // 装配完成
                Assert.IsTrue((bool)method.Invoke(publisher, new object[] { ship }), "重扫应成功");
                var renderers = renderersField.GetValue(publisher) as Renderer[];
                Assert.AreEqual(1, renderers.Length, "应扫到 1 个 MeshRenderer");
                Assert.AreSame(ship, shipField.GetValue(publisher));
                Object.DestroyImmediate(hull);
                Object.DestroyImmediate(ship);
            }
            finally { Object.DestroyImmediate(publisher.gameObject); }
        }
    }
}
