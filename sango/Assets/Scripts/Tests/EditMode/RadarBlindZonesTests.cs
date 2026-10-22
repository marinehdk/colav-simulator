using NUnit.Framework;
using Sango;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// RadarBlindZones 纯函数面测试（00-REPORT §4-3，任务书④：扇楔几何）。组件本体
    /// 在 Assembly-CSharp（mesh/材质 glue 不进测试）；几何与解析在 RadarOverlayMath
    /// （Sango.Vessels 直引）。锚点：盲扇区判定 = sensing.py:939-946 _bearing_blind
    /// （相对艏向 ±180 wrap——C# % 负数保号需双正模，见实现注）；扇楔本地系 =
    /// ship frame +z 艏/+x 右舷（MastCameraTable 同约定，TwinPose.HeadingVector 同
    /// 手性）；解析器 = RadarSpokeDecoder.ParseRowOrigins 同工艺限定扫描器。
    /// </summary>
    public class RadarBlindZonesTests
    {
        const float Tolerance = 1e-3f;

        [Test]
        public void WedgeLocalPoint_ShipFrameBowStarboard()
        {
            // Vector3+Within 走整体相等不逐分量容差——全部按分量断言（TwinPoseTests 同款）。
            Vector3 bow = RadarOverlayMath.WedgeLocalPoint(0f, 100f);
            Assert.That(bow.x, Is.EqualTo(0f).Within(Tolerance));
            Assert.That(bow.z, Is.EqualTo(100f).Within(Tolerance), "0° = 艏向 +z");
            Assert.That(bow.y, Is.EqualTo(0f).Within(Tolerance), "贴水平面");

            Vector3 starboard = RadarOverlayMath.WedgeLocalPoint(90f, 100f);
            Assert.That(starboard.x, Is.EqualTo(100f).Within(Tolerance), "90° = 右舷 +x（自艏顺时针，俯视）");
            Assert.That(starboard.z, Is.EqualTo(0f).Within(Tolerance));

            Vector3 stern = RadarOverlayMath.WedgeLocalPoint(180f, 100f);
            Assert.That(stern.x, Is.EqualTo(0f).Within(Tolerance));
            Assert.That(stern.z, Is.EqualTo(-100f).Within(Tolerance), "180° = 艉向 −z（FCB45 驾驶室遮挡盲区所在象限，30-repo §7）");

            Vector3 port = RadarOverlayMath.WedgeLocalPoint(270f, 100f);
            Assert.That(port.x, Is.EqualTo(-100f).Within(Tolerance), "270° = 左舷 −x");
            Assert.That(port.z, Is.EqualTo(0f).Within(Tolerance));

            Vector3 diagonal = RadarOverlayMath.WedgeLocalPoint(45f, Mathf.Sqrt(2f) * 50f);
            Assert.That(diagonal.x, Is.EqualTo(50f).Within(0.1f), "45° 对角分解 sin/cos");
            Assert.That(diagonal.z, Is.EqualTo(50f).Within(0.1f));

            Vector3 zero = RadarOverlayMath.WedgeLocalPoint(0f, 0f);
            Assert.That(zero.x, Is.EqualTo(0f).Within(Tolerance), "零半径退化");
            Assert.That(zero.z, Is.EqualTo(0f).Within(Tolerance));
        }

        [Test]
        public void BearingInSector_MirrorsBackendBlindSectorMath()
        {
            // sensing.py:941-945 逐例：relative = bearing − center；wrap±180 后 ≤ half。
            Assert.That(RadarOverlayMath.BearingInSectorDeg(180f, 180f, 10f), Is.True, "正中");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(190f, 180f, 10f), Is.True, "右缘内");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(170f, 180f, 10f), Is.True, "左缘内");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(160.5f, 180f, 10f), Is.False, "缘外 9.5°");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(200f, 180f, 10f), Is.False);

            // 北向跨零扇区（Python % 恒非负 vs C# 保号——双正模回中的镜像验证）。
            Assert.That(RadarOverlayMath.BearingInSectorDeg(355f, 0f, 10f), Is.True, "跨零 −5° 在内");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(3f, 0f, 10f), Is.True, "跨零 +3° 在内");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(348f, 355f, 10f), Is.True, "中心 355：跨零左缘");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(3f, 355f, 10f), Is.True, "中心 355：跨零右缘（C# 负模陷阱位）");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(345f, 355f, 10f), Is.True, "边界 10° = ≤ 同判（后端一致）");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(344f, 355f, 10f), Is.False, "缘外 11°");

            // 退化与护栏。
            Assert.That(RadarOverlayMath.BearingInSectorDeg(180f, 180f, 0f), Is.True, "零半宽只中方位（后端 ≤ 同判）");
            Assert.That(RadarOverlayMath.BearingInSectorDeg(179f, 180f, 0f), Is.False);
            Assert.That(RadarOverlayMath.BearingInSectorDeg(180f, 180f, -5f), Is.False, "负半宽 = 无扇区");
        }

        [Test]
        public void BearingFromBow_WrapsToCompassDomain()
        {
            Assert.That(RadarOverlayMath.BearingFromBowDeg(0.0, 0.0), Is.EqualTo(0f).Within(Tolerance));
            Assert.That(RadarOverlayMath.BearingFromBowDeg(Mathf.PI / 2, 0.0), Is.EqualTo(90f).Within(Tolerance));
            // 世界北（bearing 0）对艏向 90°（朝东）= 左舷 90° 后 = 相对 270°。
            Assert.That(RadarOverlayMath.BearingFromBowDeg(0.0, Mathf.PI / 2), Is.EqualTo(270f).Within(Tolerance));
            Assert.That(RadarOverlayMath.BearingFromBowDeg(-Mathf.PI / 2, 0.0), Is.EqualTo(270f).Within(Tolerance), "负方位正模");
            Assert.That(RadarOverlayMath.BearingFromBowDeg(Mathf.PI * 2.5, 0.0), Is.EqualTo(90f).Within(Tolerance), "多转取模");
        }

        [Test]
        public void ParseBlindSectors_StrictPairScanner()
        {
            const string doc = "{\"schema_version\":\"radar-ppi@1\",\"blind_ring_m\":54.0," +
                "\"blind_sectors_deg\": [[180.0, 12.5],[355, 5],[1e1, 2.5]],\"scan_period_s\":2.5}";
            float[][] sectors = RadarOverlayMath.ParseBlindSectors(doc);
            Assert.That(sectors, Is.Not.Null);
            Assert.That(sectors.Length, Is.EqualTo(3));
            Assert.That(sectors[0][0], Is.EqualTo(180f).Within(Tolerance), "center_rel_bow_deg");
            Assert.That(sectors[0][1], Is.EqualTo(12.5f).Within(Tolerance), "half_width_deg");
            Assert.That(sectors[1][0], Is.EqualTo(355f).Within(Tolerance));
            Assert.That(sectors[2][0], Is.EqualTo(10f).Within(Tolerance), "科学计数法可解析");

            Assert.That(RadarOverlayMath.ParseBlindSectors("{\"blind_ring_m\":54.0}"), Is.Null, "键缺失 → null");
            Assert.That(RadarOverlayMath.ParseBlindSectors(null), Is.Null);
            Assert.That(RadarOverlayMath.ParseBlindSectors("{\"blind_sectors_deg\":[]}").Length, Is.EqualTo(0),
                "空表 = 无盲扇区（后端默认 ()，sensing.py:507）");
            Assert.That(RadarOverlayMath.ParseBlindSectors("{\"blind_sectors_deg\":[[180,12.5],[3]]}"), Is.Null,
                "畸形对 → null 不部分产出");
            Assert.That(RadarOverlayMath.ParseBlindSectors("{\"blind_sectors_deg\":[1,2]}"), Is.Null, "未嵌套 → null");
            Assert.That(RadarOverlayMath.ParseBlindSectors("{\"blind_sectors_deg\":[[180,12.5],]}"), Is.Null, "尾逗号 → null");
        }

        [Test]
        public void Constants_PinBackendAnchors()
        {
            Assert.That(RadarOverlayMath.MetersPerNm, Is.EqualTo(1852f), "后端 N_METERS_PER_NM（sensing.py:451）");
            Assert.That(RadarOverlayMath.BlindRingFallbackM, Is.EqualTo(54f),
                "Halo24 口径 R_min 缺省（h=12 m / VBW 25°，web clutterPoints 同缺省）");
            Assert.That(RadarOverlayMath.PrevRevolutionAlpha, Is.EqualTo(0.45f), "余辉基线与 RadarSurfaceOverlayTests 同钉");
        }
    }
}
