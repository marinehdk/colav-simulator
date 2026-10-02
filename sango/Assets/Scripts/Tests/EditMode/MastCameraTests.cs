using NUnit.Framework;
using Sango.Vessels.Mast;
using UnityEngine;

namespace Sango.Tests
{
    /// <summary>
    /// P3-S2 桅杆传感器机位族纯函数测试（spec #90）。机位表常量与后端权威标定
    /// （colav_simulator/core/mast_cameras.py，milliampere-ch5 §4.2）双向对齐——
    /// 任何一侧改动必须同步另一侧（后端 parity 测试钉同一字面量）。
    /// IR 温度分级 = plan裁决 3 "温度 tag+灰度 ramp" 的数据面；WhiteHot 与
    /// IrWhiteHot.shader 同式（C# 镜像可测）。
    /// </summary>
    public class MastCameraTableTests
    {
        [Test]
        public void Family_Composition_MatchesTaskLayout()
        {
            Assert.That(MastCameraTable.Mounts.Length, Is.EqualTo(12), "EO×5 + IR×4 + PTZ 双光谱×2 通道 + LiDAR×1（P3-S3）");
            int eo = 0, ir = 0, ptz = 0, lidar = 0;
            foreach (var mount in MastCameraTable.Mounts)
            {
                if (mount.MountId.StartsWith("mast_ptz")) ptz++;
                else if (mount.Channel == MastSensorChannel.Lidar) lidar++;
                else if (mount.Channel == MastSensorChannel.Eo) eo++;
                else ir++;
            }
            Assert.That(eo, Is.EqualTo(5), "EO 固定环视 ×5");
            Assert.That(ir, Is.EqualTo(4), "IR 固定 ×4");
            Assert.That(ptz, Is.EqualTo(2), "PTZ 双光谱 = 白光 + LWIR 两通道机位");
            Assert.That(lidar, Is.EqualTo(1), "LiDAR 深度相机 ×1（P3-S3 点云视角）");
        }

        [Test]
        public void MountIds_AreUnique_AndContractVocabulary()
        {
            var seen = new System.Collections.Generic.HashSet<string>();
            foreach (var mount in MastCameraTable.Mounts)
                Assert.That(seen.Add(mount.MountId), Is.True, $"{mount.MountId} 重复");
            Assert.That(MastCameraTable.TryGet("mast_ir_bow", out _), Is.True, "observations-v1 §3 样例词汇");
            Assert.That(MastCameraTable.TryGet("nope", out _), Is.False);
        }

        [Test]
        public void RingLayout_MatchesTaskAzimuths()
        {
            Assert.That(AzimuthOf("mast_eo_bow_stbd"), Is.EqualTo(60f));
            Assert.That(AzimuthOf("mast_eo_bow_port"), Is.EqualTo(300f));
            Assert.That(AzimuthOf("mast_eo_stbd"), Is.EqualTo(90f));
            Assert.That(AzimuthOf("mast_eo_port"), Is.EqualTo(270f));
            Assert.That(AzimuthOf("mast_eo_quarter"), Is.EqualTo(180f));
            Assert.That(AzimuthOf("mast_ir_bow"), Is.EqualTo(0f));
            Assert.That(AzimuthOf("mast_ir_stbd"), Is.EqualTo(90f));
            Assert.That(AzimuthOf("mast_ir_port"), Is.EqualTo(270f));
            Assert.That(AzimuthOf("mast_ir_quarter"), Is.EqualTo(180f));
            Assert.That(AzimuthOf("mast_ptz_eo"), Is.EqualTo(0f), "PTZ 白光通道 = 前向 EO 角色（写档偏差注）");
        }

        [Test]
        public void Heights_AnchorOnFbxMastMeasurements()
        {
            foreach (var mount in MastCameraTable.Mounts)
            {
                if (mount.MountId.StartsWith("mast_ptz"))
                {
                    Assert.That(mount.HeightM, Is.EqualTo(11.5f), "桅顶前伸托架（milliampere §4.2）");
                    Assert.That(mount.ForwardOffsetM, Is.EqualTo(2.5f));
                }
                else if (mount.Channel == MastSensorChannel.Lidar)
                {
                    Assert.That(mount.HeightM, Is.EqualTo(11.0f), "桅顶下法兰 11 m（milliampere §4.2 LiDAR 行）");
                    Assert.That(mount.ForwardOffsetM, Is.EqualTo(2.1f), "桅位舯前 2.1 m");
                }
                else
                {
                    Assert.That(mount.HeightM, Is.EqualTo(10.5f), "桅围栏圈（FBX 空气高 12.98 m 桅系）");
                    Assert.That(mount.ForwardOffsetM, Is.EqualTo(2.1f), "桅位舯前 2.1 m");
                }
            }
        }

        [Test]
        public void EoRing_DoesNotOwnDeadAhead_PtzDoes()
        {
            Assert.That(RingCovers("mast_eo_bow_stbd", 0f), Is.False, "±60° 前向双 90° HFOV 不含正前");
            Assert.That(RingCovers("mast_eo_bow_port", 0f), Is.False);
            Assert.That(RingCovers("mast_ptz_eo", 0f), Is.True, "正前 = PTZ 档（前向由云台补，milliAmpere 工艺）");
        }

        [Test]
        public void EoFamily_CoversFullCircle()
        {
            for (float azimuth = 0f; azimuth < 360f; azimuth += 1f)
            {
                bool covered = false;
                foreach (var mount in MastCameraTable.Mounts)
                    if (mount.Channel == MastSensorChannel.Eo && MastCameraTable.CoversAzimuth(mount, azimuth)) { covered = true; break; }
                Assert.That(covered, Is.True, $"EO 族（环视+PTZ）须全覆盖 {azimuth}°");
            }
        }

        [Test]
        public void FeedMount_IsForwardEo_AtPublishedFeedRaster()
        {
            Assert.That(MastCameraTable.TryGet(MastCameraTable.FeedMountId, out var feed), Is.True);
            Assert.That(feed.Channel, Is.EqualTo(MastSensorChannel.Eo));
            Assert.That(feed.HFovDeg, Is.EqualTo(60f));
            Assert.That(feed.FrameWidthPx, Is.EqualTo(640));
            Assert.That(feed.FrameHeightPx, Is.EqualTo(480));
            Assert.That(feed.ReferenceWidthPx, Is.EqualTo(1920), "内参参考栅格 1080p");
        }

        [Test]
        public void LocalPose_ShipFrameMath()
        {
            Assert.That(MastCameraTable.TryGet("mast_ptz_eo", out var forward), Is.True);
            var position = MastCameraTable.LocalPosition(forward);
            Assert.That(position, Is.EqualTo(new Vector3(0f, 11.5f, 2.5f)));
            var rotation = MastCameraTable.LocalRotation(forward);
            var look = rotation * Vector3.forward;
            Assert.That(look, Is.EqualTo(new Vector3(0f, 0f, 1f)).Within(1e-5), "az 0 = 艏向 (+z)");

            Assert.That(MastCameraTable.TryGet("mast_eo_stbd", out var stbd), Is.True);
            var stbdLook = MastCameraTable.LocalRotation(stbd) * Vector3.forward;
            Assert.That(stbdLook.x, Is.EqualTo(1f).Within(1e-5), "az 90°（右舷正横）= +x");
            Assert.That(stbdLook.z, Is.EqualTo(0f).Within(1e-5));
            var stbdPosition = MastCameraTable.LocalPosition(stbd);
            Assert.That(stbdPosition, Is.EqualTo(new Vector3(0f, 10.5f, 2.1f)));

            // P3-S3: the camera family stays level (pitch 0); only the LiDAR row
            // carries its install downtilt.
            foreach (var mount in MastCameraTable.Mounts)
            {
                float expectedPitch = mount.Channel == MastSensorChannel.Lidar ? LidarPattern.MountPitchDeg : 0f;
                Assert.That(mount.PitchDeg, Is.EqualTo(expectedPitch), mount.MountId);
            }
        }

        [Test]
        public void FocalPx_PinholeMath_ParityWithBackend()
        {
            Assert.That(MastCameraTable.TryGet("mast_ptz_eo", out var feed), Is.True);
            double fx640 = MastCameraTable.FocalPx(feed, 640);
            Assert.That(fx640, Is.EqualTo(554.2562584220409).Within(1e-6), "(640/2)/tan(30°)——后端 focal_px 同式");
            double fx1920 = MastCameraTable.FocalPx(feed, 1920);
            Assert.That(fx1920, Is.EqualTo(1662.7687756571226).Within(1e-6));
            Assert.That(MastCameraTable.TryGet("mast_ir_bow", out var ir), Is.True);
            Assert.That(MastCameraTable.FocalPx(ir, 640), Is.EqualTo(320.0).Within(1e-9), "90° HFOV: fx = W/2");
        }

        static float AzimuthOf(string mountId)
        {
            Assert.That(MastCameraTable.TryGet(mountId, out var mount), Is.True, mountId);
            return mount.AzimuthDeg;
        }

        static bool RingCovers(string mountId, float azimuth)
        {
            Assert.That(MastCameraTable.TryGet(mountId, out var mount), Is.True, mountId);
            return MastCameraTable.CoversAzimuth(mount, azimuth);
        }
    }

    public class IrTemperatureTests
    {
        [Test]
        public void TierGrays_OrderColdestToHottest()
        {
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Sky), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Sea)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Sea), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Deck)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Deck), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Hull)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Hull), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.EngineRoom)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.EngineRoom), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Exhaust)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Exhaust), Is.EqualTo(1f));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Sky), Is.EqualTo(0.05f).Within(1e-6), "天空最低");
        }

        [Test]
        public void TierForMaterial_MapsNameKeywords()
        {
            Assert.That(IrTemperature.TierForMaterial("VesselFcb45.Funnel"), Is.EqualTo(IrTemperatureTier.Exhaust), "烟囱最高");
            Assert.That(IrTemperature.TierForMaterial("engine_room"), Is.EqualTo(IrTemperatureTier.EngineRoom), "机舱高");
            Assert.That(IrTemperature.TierForMaterial("VesselFcb45.HullSide"), Is.EqualTo(IrTemperatureTier.Hull), "船体中");
            Assert.That(IrTemperature.TierForMaterial("MainDeck"), Is.EqualTo(IrTemperatureTier.Deck));
            Assert.That(IrTemperature.TierForMaterial("OceanSurface"), Is.EqualTo(IrTemperatureTier.Sea), "海面低");
            Assert.That(IrTemperature.TierForMaterial("SkyDome"), Is.EqualTo(IrTemperatureTier.Sky), "天空最低");
            Assert.That(IrTemperature.TierForMaterial("VesselFcb45.Cabin"), Is.EqualTo(IrTemperatureTier.Hull), "未命中 = 船体档（船是热目标）");
            Assert.That(IrTemperature.TierForMaterial(null), Is.EqualTo(IrTemperatureTier.Hull));
        }

        [Test]
        public void WhiteHot_RampMatchesShaderFormula()
        {
            Assert.That(IrTemperature.WhiteHot(0f), Is.EqualTo(0f));
            Assert.That(IrTemperature.WhiteHot(1f), Is.EqualTo(1f));
            float shaped = IrTemperature.WhiteHot(0.3f, 1.6f, 0.8f);
            Assert.That(shaped, Is.EqualTo(Mathf.Pow(Mathf.Clamp01(0.3f * 1.6f), 0.8f)).Within(1e-5));
            Assert.That(IrTemperature.WhiteHot(0.8f), Is.GreaterThan(IrTemperature.WhiteHot(0.4f)), "单调 white-hot");
            Assert.That(IrTemperature.WhiteHot(5f), Is.EqualTo(1f), "饱和钳位");
        }
    }

    public class SensorModeEffectTests
    {
        [Test]
        public void EffectTable_MatchesContractVocabulary()
        {
            TwinBridge.SensorModeEffect("eo", out bool eoIr, out bool eoLidar);
            Assert.That(eoIr, Is.False, "eo = 默认正常渲染");
            Assert.That(eoLidar, Is.False);

            TwinBridge.SensorModeEffect("ir", out bool irActive, out bool irLidar);
            Assert.That(irActive, Is.True, "ir = 流相机黑白热像");
            Assert.That(irLidar, Is.False);

            TwinBridge.SensorModeEffect("lidar", out bool lidarIr, out bool lidarRender);
            Assert.That(lidarIr, Is.False, "lidar 不开 IR pass");
            Assert.That(lidarRender, Is.True, "P3-S3：lidar = 点云视角真实现（LidarViewPass）");

            TwinBridge.SensorModeEffect("thermal", out bool badIr, out bool badLidar);
            Assert.That(badIr, Is.False);
            Assert.That(badLidar, Is.False);
        }
    }

    public class FrameMetadataMountTests
    {
        [Test]
        public void BuildMetadata_WithMountAndPose_AssignsP3S2Fields()
        {
            var m = FramePublisherCore.BuildMetadata(41, 12.402, 640, 480, 51200, "sango",
                "mast_ptz_eo", 12.5, -3.25, 137.0);
            Assert.That(m.mount_id, Is.EqualTo("mast_ptz_eo"), "observations-v1 §3 引用键");
            Assert.That(m.pose_east_m, Is.EqualTo(12.5).Within(1e-9));
            Assert.That(m.pose_north_m, Is.EqualTo(-3.25).Within(1e-9));
            Assert.That(m.pose_yaw_deg, Is.EqualTo(137.0).Within(1e-9));
        }

        [Test]
        public void BuildMetadata_LegacySignature_KeepsEmptyMount()
        {
            var m = FramePublisherCore.BuildMetadata(1, 0.1, 1280, 720, 1024, "sango");
            Assert.That(m.mount_id, Is.EqualTo(""), "旧馈送语义零变化（只加字段）");
            Assert.That(m.pose_east_m, Is.EqualTo(0.0));
        }

        [Test]
        public void MetadataJson_RoundTripCarriesMountAndPose()
        {
            var m = FramePublisherCore.BuildMetadata(42, 1.5, 640, 480, 2048, "sango",
                "mast_ptz_eo", 1.25, -2.5, 90.0);
            string json = FramePublisherCore.MetadataToJson(m);
            Assert.That(json, Does.Contain("\"mount_id\":\"mast_ptz_eo\""));
            Assert.That(json, Does.Contain("\"pose_yaw_deg\":90"));
            var back = JsonUtility.FromJson<FrameMetadata>(json);
            Assert.That(back.mount_id, Is.EqualTo("mast_ptz_eo"));
            Assert.That(back.pose_yaw_deg, Is.EqualTo(90.0).Within(1e-9));
        }
    }
}
