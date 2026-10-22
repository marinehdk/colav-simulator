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
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Sea), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Land)), "P2：环境陆地略暖于海（白天储热，survey §4 #7）");
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Land), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Deck)), "陆地仍远冷于船体任何部位");
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Deck), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Hull)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Hull), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.EngineRoom)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.EngineRoom), Is.LessThan(IrTemperature.TierGray(IrTemperatureTier.Exhaust)));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Exhaust), Is.EqualTo(1f));
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Sky), Is.EqualTo(0.05f).Within(1e-6), "天空最低");
            Assert.That(IrTemperature.TierGray(IrTemperatureTier.Land), Is.EqualTo(0.2f).Within(1e-6), "P2 默认 Land≈0.2");
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
        public void TierForMaterial_MapsAmbientLandKeywords()
        {
            Assert.That(IrTemperature.TierForMaterial("TwinCesiumLandscapeMaterial"), Is.EqualTo(IrTemperatureTier.Land),
                "P2 环境注册主路径：共享 Cesium 地景材质名命中 land（ThermalTagApplier.AmbientLandscapeMaterialName）");
            Assert.That(IrTemperature.TierForMaterial("QingdaoShoreline"), Is.EqualTo(IrTemperatureTier.Land), "岸线");
            Assert.That(IrTemperature.TierForMaterial("JiaozhouBridgeDeck"), Is.EqualTo(IrTemperatureTier.Deck),
                "桥面带 deck 关键词优先按船甲板档（部分可见的桥面结构按上结构处理）");
            Assert.That(IrTemperature.TierForMaterial("HarbourBuilding_03"), Is.EqualTo(IrTemperatureTier.Land), "岸线建筑");
            Assert.That(IrTemperature.TierForMaterial("RockIsland"), Is.EqualTo(IrTemperatureTier.Land), "地形/岛");
            Assert.That(IrTemperature.TierForMaterial("CoastTerrain"), Is.EqualTo(IrTemperatureTier.Land), "地形");
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

        [Test]
        public void WhiteHot_DefaultGain_KeepsAllSixTiersSeparated()
        {
            // 评审修复：默认增益 = 档位标定（1.0），六档全部过 0.8-gamma ramp 后仍两两
            // 可分（EngineRoom 不再与 Exhaust 饱并成同一片白；P3-S2 的 1.6 曾把
            // EngineRoom/Hull 拉饱和，叠加未钳 AGC 后塌缩成 天/海/船白 三级）。
            float sky = IrTemperature.WhiteHot(IrTemperature.SkyGray);
            float sea = IrTemperature.WhiteHot(IrTemperature.SeaGray);
            float land = IrTemperature.WhiteHot(IrTemperature.LandGray);
            float deck = IrTemperature.WhiteHot(IrTemperature.DeckGray);
            float hull = IrTemperature.WhiteHot(IrTemperature.HullGray);
            float engine = IrTemperature.WhiteHot(IrTemperature.EngineRoomGray);
            float exhaust = IrTemperature.WhiteHot(IrTemperature.ExhaustGray);
            Assert.That(sky, Is.LessThan(sea));
            Assert.That(sea, Is.LessThan(land));
            Assert.That(land, Is.LessThan(deck));
            Assert.That(deck, Is.LessThan(hull));
            Assert.That(hull, Is.LessThan(engine), "机舱 ≠ 船体（未饱和）");
            Assert.That(engine, Is.LessThan(exhaust), "机舱 ≠ 排气（排气档独占饱和白）");
            // AGC 全程增益 ≤1.25 时分层仍成立（呼吸上限不塌缩档位）。
            Assert.That(IrTemperature.WhiteHot(IrTemperature.HullGray, 1.25f), Is.LessThan(1f), "船体在 AGC 上限不饱和");
            Assert.That(IrTemperature.WhiteHot(IrTemperature.DeckGray, 1.25f), Is.LessThan(1f));
        }

        [Test]
        public void AgcServo_TimeConstantAndClampMirrorTheShader()
        {
            // EMA：一帧(1/30s)内增益基值只移动 dt/τ ≈ 4%（评审：无时间常数会闪烁）。
            float stepped = IrTemperature.AgcStep(0.15f, 0.60f, 1f / 30f);
            Assert.That(stepped, Is.GreaterThan(0.15f));
            Assert.That(stepped, Is.LessThan(0.60f));
            Assert.That(stepped, Is.EqualTo(0.15f + 0.45f * (1f / 30f / 0.8f)).Within(1e-5), "α = dt/τ");
            // τ 秒单步（dt=τ）alpha 钳到 1 → 直达目标；连续小步近似一阶收敛。
            Assert.That(IrTemperature.AgcStep(0.15f, 0.60f, 0.8f), Is.EqualTo(0.60f).Within(1e-6), "单步 dt=τ 钳满步直达");
            float consecutive = 0.15f;
            for (int i = 0; i < 30; i++) consecutive = IrTemperature.AgcStep(consecutive, 0.60f, 1f / 30f);
            Assert.That(consecutive, Is.GreaterThan(0.15f).And.LessThan(0.60f), "连续 30 帧(1s) 介于初值与目标之间");
            Assert.That(IrTemperature.AgcStep(0.15f, 0.60f, 0f), Is.EqualTo(0.15f), "dt=0 不动（EditMode 静态帧）");
            Assert.That(IrTemperature.AgcStep(0.15f, 0.60f, 10f), Is.EqualTo(0.60f).Within(1e-6), "大步钳到目标");
            // 增益钳位 0.8-1.25：海天场景（均值≈目标）单位增益；热源掩盖 tap 的极端
            // 均值也不会推增益越界（评审：工作点塌缩修复）。
            Assert.That(IrTemperature.AgcGain(0.15f, 0.15f), Is.EqualTo(1f).Within(1e-6), "海天工作点 = 单位增益");
            Assert.That(IrTemperature.AgcGain(0.15f, 0.05f), Is.EqualTo(1.25f), "暗场景钳上限");
            Assert.That(IrTemperature.AgcGain(0.15f, 0.50f), Is.EqualTo(0.8f), "亮场景钳下限");
            Assert.That(IrTemperature.AgcGain(0.15f, 0f), Is.EqualTo(1.25f), "零均值回退（readback 未就绪）钳上限而非除零");
        }

        [Test]
        public void DisplayGray_PolarityMirrorOfShaderFinalLerp()
        {
            Assert.That(IrTemperature.DisplayGray(0.7f, blackHot: false), Is.EqualTo(0.7f).Within(1e-6), "白热 = 恒等");
            Assert.That(IrTemperature.DisplayGray(0.7f, blackHot: true), Is.EqualTo(0.3f).Within(1e-6), "黑热 = 反转显示映射（survey §4 #1）");
            Assert.That(IrTemperature.DisplayGray(IrTemperature.ExhaustGray, blackHot: true), Is.EqualTo(0f).Within(1e-6), "黑热下排气档最暗");
            Assert.That(IrTemperature.DisplayGray(IrTemperature.SkyGray, blackHot: true), Is.EqualTo(0.95f).Within(1e-6), "黑热下天空最亮");
        }
    }

    /// <summary>
    /// P2 IR realism sensor math seams (spec: survey §4 #7 horizon gradient).
    /// IrViewPass itself lives in Assembly-CSharp (CustomPass subclass outside
    /// the Sango.Vessels asmdef — LidarViewPass precedent) so its static
    /// SetActive gating is not EditMode-reachable; the pass-gating logic it
    /// consumes is TwinBridge.SensorModeEffect (SensorModeEffectTests).
    /// </summary>
    public class IrSensorMathTests
    {
        [Test]
        public void HorizonScreenY_PinholeHorizonProjection()
        {
            Assert.That(IrTemperature.HorizonScreenY(0f, 65f), Is.EqualTo(0.5f).Within(1e-4), "平视：地平线在画面正中");
            // 俯 10°（域约定 pitch=−10；Unity Euler x=+10，经 PitchFromUnityEulerX 取负——
            // 评审修复前的注释把 Unity x=-10 当俯，固化了同一符号错误认知）：
            // 地平线升到画面上半（>0.5）。
            float down = IrTemperature.HorizonScreenY(-10f, 65f);
            Assert.That(down, Is.GreaterThan(0.5f));
            Assert.That(down, Is.EqualTo(0.5f + 0.5f * Mathf.Tan(10f * Mathf.Deg2Rad) / Mathf.Tan(32.5f * Mathf.Deg2Rad)).Within(1e-4), "uv = (−tan(pitch)/tan(fov/2)+1)/2");
            // 仰 10°：地平线落到画面下半（<0.5），与俯视对称。
            Assert.That(IrTemperature.HorizonScreenY(10f, 65f), Is.EqualTo(1f - down).Within(1e-4));
            // 广角地平线更靠近中心（同 pitch 下投影位移按 1/tan(fov/2) 缩放）。
            Assert.That(IrTemperature.HorizonScreenY(-10f, 100f), Is.LessThan(down));
            // 越界（地平线出画）允许返回 [0,1] 外的值——shader 梯度按方向仍成立。
            Assert.That(IrTemperature.HorizonScreenY(-60f, 65f), Is.GreaterThan(1f));
        }

        [Test]
        public void PitchFromUnityEulerX_PinsTheCallSiteSign_ChaseTopBow()
        {
            // P2 评审修复回归锁：IrViewPass.Execute 之前把 Unity Euler x 直传
            // HorizonScreenY（域约定负=俯）——符号反转。Unity 正 x = 俯
            // （CameraRig.ApplyPose 根因注释：Rx(+90)·(0,0,1)=(0,−1,0)）。
            Assert.That(IrTemperature.PitchFromUnityEulerX(0f), Is.EqualTo(0f).Within(1e-6), "平视");
            // chase 档（Unity x=+26.6，俯）：域 pitch=−26.6 → 地平线近画面顶 0.934；
            // 反号错误会得 0.066（83% 画面被 shader 天空温度 lerp 压平）。
            Assert.That(IrTemperature.PitchFromUnityEulerX(26.6f), Is.EqualTo(-26.6f).Within(1e-4));
            Assert.That(IrTemperature.HorizonScreenY(IrTemperature.PitchFromUnityEulerX(26.6f), 60f),
                Is.EqualTo(0.9330f).Within(1e-3), "chase 档：地平线在画面上部，热目标不被天空 lerp 压平");
            // top 档（+80 俯，fov35）：地平线出画上方（修复前 −8.49 → 100% 画面误判为天空）。
            Assert.That(IrTemperature.PitchFromUnityEulerX(80f), Is.EqualTo(-80f).Within(1e-4));
            Assert.That(IrTemperature.HorizonScreenY(IrTemperature.PitchFromUnityEulerX(80f), 35f), Is.GreaterThan(1f));
            // bow 档（+8 俯）：地平线上移过中線，近地平线海面带仍走海侧分支。
            Assert.That(IrTemperature.PitchFromUnityEulerX(8f), Is.EqualTo(-8f).Within(1e-4));
            Assert.That(IrTemperature.HorizonScreenY(IrTemperature.PitchFromUnityEulerX(8f), 60f), Is.GreaterThan(0.5f));
            // Euler [0,360) 回卷：333.4° = 仰 26.6（域 +26.6）；350° = 仰 10。
            Assert.That(IrTemperature.PitchFromUnityEulerX(333.4f), Is.EqualTo(26.6f).Within(1e-4));
            Assert.That(IrTemperature.PitchFromUnityEulerX(350f), Is.EqualTo(10f).Within(1e-4));
            // 域值原样对称（已是 [−180,180] 的输入只取负）。
            Assert.That(IrTemperature.PitchFromUnityEulerX(-10f), Is.EqualTo(10f).Within(1e-6));
        }
    }

    public class SensorModeEffectTests
    {
        [Test]
        public void EffectTable_MatchesContractVocabulary()
        {
            TwinBridge.SensorModeEffect("eo", out bool eoIr, out bool eoLidar, out bool eoBlack);
            Assert.That(eoIr, Is.False, "eo = 默认正常渲染");
            Assert.That(eoLidar, Is.False);
            Assert.That(eoBlack, Is.False);

            TwinBridge.SensorModeEffect("ir", out bool irActive, out bool irLidar, out bool irBlack);
            Assert.That(irActive, Is.True, "ir = 流相机黑白热像");
            Assert.That(irLidar, Is.False);
            Assert.That(irBlack, Is.False, "ir 别名 = 白热");

            TwinBridge.SensorModeEffect("lidar", out bool lidarIr, out bool lidarRender, out bool lidarBlack);
            Assert.That(lidarIr, Is.False, "lidar 不开 IR pass");
            Assert.That(lidarRender, Is.True, "P3-S3：lidar = 点云视角真实现（LidarViewPass）");
            Assert.That(lidarBlack, Is.False);

            TwinBridge.SensorModeEffect("thermal", out bool badIr, out bool badLidar, out bool badBlack);
            Assert.That(badIr, Is.False);
            Assert.That(badLidar, Is.False);
            Assert.That(badBlack, Is.False);
        }

        [Test]
        public void EffectTable_P2PolarityValues_OpenIrPassWithDisplayInversion()
        {
            TwinBridge.SensorModeEffect(TwinBridge.IrWhiteHotMode, out bool whIr, out bool whLidar, out bool whBlack);
            Assert.That(whIr, Is.True, "ir_whitehot 开 IR pass");
            Assert.That(whLidar, Is.False);
            Assert.That(whBlack, Is.False, "白热 = 不反转");

            TwinBridge.SensorModeEffect(TwinBridge.IrBlackHotMode, out bool bhIr, out bool bhLidar, out bool bhBlack);
            Assert.That(bhIr, Is.True, "ir_blackhot 同一 pass");
            Assert.That(bhLidar, Is.False);
            Assert.That(bhBlack, Is.True, "黑热 = 显示映射反转（survey §4 #1）");

            Assert.That(TwinBridge.IsIrMode("ir"), Is.True);
            Assert.That(TwinBridge.IsIrMode(TwinBridge.IrWhiteHotMode), Is.True);
            Assert.That(TwinBridge.IsIrMode(TwinBridge.IrBlackHotMode), Is.True);
            Assert.That(TwinBridge.IsIrMode("eo"), Is.False);
            Assert.That(TwinBridge.IsIrMode("lidar"), Is.False);
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
