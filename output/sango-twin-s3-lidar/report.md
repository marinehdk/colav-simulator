# P3-S3 LiDAR point-cloud view E2E — sango_twin_lidar_probe

- date: 2026-10-02T22:11:51.088Z
- live session: `fd3fa440-a0aa-41a8-9edf-ce1e8ba6fb06` (rule14/head_on/vo, tracker=god — capabilities gate)
- mode cycle: eo → ir → lidar → eo through the real Deployment button group; state echoes all four
- EO baseline: mean=79.0 std=64.4 spread=34 dark=0.12 lit=0.2911
- IR (S2 non-regression): mean=83.1 std=55.0 spread=5 dark=0.00 lit=0.3058
- LiDAR: mean=8.9 std=16.7 spread=106 dark=0.97 lit=0.0167 — dark backdrop + sparse lit points, mean < 0.6× EO
- LiDAR top-preset (camera orthogonality): mean=9.0 std=16.8 spread=103 dark=0.97 lit=0.0168
- EO restore: mean=78.8 std=64.4 spread=40 dark=0.12 lit=0.2897

## 点云管线选型（写档）

- 路线 = HDRP 17 CustomPass 官方 API（survey §2.1）：`LidarViewPass` 全屏 pass 挂流相机
  BeforePostProcess，逐 5px cell 反投影光线、取流相机自身深度场
  （`CustomPassLoadCameraDepth`——render-graph 原生同相机通道），按世界仰角 snap 到
  VLP-16 的 16 通道画点：深色背景 + 噪声点阵。
- 跨相机方案弃选理由（调试台账，shader 头注）：mast_lidar 深度采集相机 → 流相机 cross-camera
  纹理采样在 render-graph custom pass 内不绑定（RT 未注册），且 quad/mesh/SV_InstanceID
  非全屏 draw 全部不可见——仅全屏 DrawProcedural(3,1) 可靠执行；材质属性（矩阵/向量/浮点）
  可靠、Update 期 shader global 不绑定。最终改为流相机自身深度场的"LiDAR-vision"点阵。
- v1 偏差（写档）：①点阵锚定流相机视场（"LiDAR-vision"），非桅顶 mast_lidar 的 90°x32° 物理
  视场——mast_lidar 机位行保留（后端接触模型互钉 + 升级位），跨相机重投影留后续段；
  ②角度抖动（AWSIM 0.057°）在屏幕锚定实现中不可观测，噪声链保留距离高斯+dropout+衰减；
  ③HDRP Water 部分写入深度 → 海面点以暗色出现（低矮高程 ramp），船/岸/浮标可辨。
- 两路独立（硬边界）：Unity 点云只做视景不回传；后端 `LidarContactSensor`（sensor_id=4，
  旁路）按几何真值自产接触点，两路零数据交换。

## 噪声参数表（survey §2.3 先例照抄）

| 参数 | 值 | 先例 |
|---|---|---|
| 距离高斯 σ 基值 | 0.02 m | AWSIM/RGL（survey §2.3） |
| 距离高斯 σ 斜率 | 0.002 /m（可调项，无先例钉值 → 100 m 处 σ=0.22 m） | AWSIM「rise per meter 可调」 |
| 角度高斯 σ | 0.057°（方位/俯仰同） | AWSIM/RGL（survey §2.3） |
| dropoff general rate | 0.45 | CARLA lidar 默认（survey §2.3） |
| dropoff intensity limit | 0.8 | CARLA lidar 默认 |
| zero intensity | 0.4（远端亮度下限） | CARLA lidar 默认 |
| 大气衰减 | 0.004 /m（强度 1−a·d，50 m 触发 dropoff） | CARLA atmosphere_attenuation_rate |

## 降采样说明

- mast_lidar 深度相机：640×184 pinhole（90°×32°，aspect=tan45°/tan16°），far=100 m 量程裁剪；
- 16 线栅格：VLP-16 通道 -15°…+15°（2° 步距）落在 32° FOV 的 1° 上下边距内 →
  通道 i 采样深度图 v=(2i+1)/32（精确 texel 中心，point sampling 零插值斜偏）；
- 每线 640 采样：u=(j+0.5)/640（针孔 tan 域等像素列，方位由像素射线反解）；
- 10 Hz 帧节拍：噪声/图案种子按 0.1 s 重掷（深度纹理逐帧连续，点云视觉按 10 Hz 刷新）；
- 16×640 = 10240 点/帧 ≈ 10.2 万点/s（VLP-16 单回波 30 万点/s 同量级）。

## Assertions

- PASS  preflight backend 8010 — http://127.0.0.1:8010/api/capabilities -> 200
- PASS  preflight URS signaling 8080 — http://127.0.0.1:8080/config -> 200
- PASS  live session created (POST /api/sessions, tracker=god; capabilities-gated) — status 200
- PASS  live session started — session=fd3fa440-a0aa-41a8-9edf-ce1e8ba6fb06
- PASS  video frames arriving (live pixel stream) — attached run=fd3fa440 ships=2
- PASS  EO baseline frame captured — mean=79.0 std=64.4 spread=34 dark=0.12 lit=0.2911
- PASS  EO frame artifact
- PASS  IR switch: state echo sensor_mode=ir
- PASS  IR = black-and-white thermal (max channel spread ~0) — maxSpread=5
- PASS  IR frame artifact
- PASS  LiDAR switch: state echo sensor_mode=lidar (contract §3)
- PASS  sensor-mode chip shows the un-pended LiDAR label — SENSOR LiDAR
- PASS  LiDAR frame captured — mean=8.9 std=16.7 spread=106 dark=0.97 lit=0.0167
- PASS  LiDAR = deep-dark backdrop (dark fraction dominates EO) — lidar dark=0.97 vs eo dark=0.12
- PASS  LiDAR = point cloud on the backdrop (sparse lit points present) — lit=0.0167
- PASS  LiDAR mean luminance collapses vs EO (quantified frame diff) — lidar mean=8.9 vs eo mean=79.0
- PASS  LiDAR frame artifact (decoded stream frame)
- PASS  LiDAR top-preset frame captured (camera/lidar orthogonality) — mean=9.0 std=16.8 spread=103 dark=0.97 lit=0.0168
- PASS  LiDAR top-preset frame artifact
- PASS  EO restore: state echo sensor_mode=eo
- PASS  EO restore = visible light (channel spread returns) — maxSpread=40
- PASS  EO restored frame artifact
- PASS  Player.log double proof (sensor_mode -> lidar + lidar point-cloud view active + mast rig) — /Users/marine/Library/Logs/DefaultCompany/sango/Player.log
