# 阶段一：本机优化与验收记录（2026-10-01）

基线 `31c82773`；Unity 6000.3.24f1 / HDRP 17.3 / Mac Metal / Mono。全部开发、场景烘焙、播放器、录制与 CPU YOLO 回环在本机完成，未连接 A4000。保留原有无关工作树改动，本轮尚未提交。

## 修复结果

| 问题 | 结果与依据 |
| --- | --- |
| 浮态 target 近零、已呈现姿态反向影响采样 | 水高查询固定在设计基准姿态；绝对升沉/横摇/纵摇目标不再由当前渲染姿态抵消。临界阻尼改为解析解，长帧不发散。B0/B3/B6/B9 原生水高与姿态记录可查。 |
| 海况切档先跳波谱后渐变风速 | band、风谱与泡沫同随切档渐变；Moderate 按 B3 实际风速驱动谱。属于视觉谱校准，不是实船 RAO 校准。 |
| 桥楼机位在船后、艏机位穿船 | FCB45 独立桥楼/艏安装锚点，艏视角可见前甲板与锚机；挂载机位继承船体姿态一次，去除重复人工摇晃。 |
| 尾迹板片、串珠、没有扩散臂 | 连续 propwash 与 Kelvin 视觉包络；密集历史节点、噪声破碎与远段衰减。尾迹和水线环逐顶点贴当前水面；High 移动时最多 817 次额外水高查询，停止/Low 为零。 |
| 泡沫夜间自发光、透明区仍反光/遮挡 | 泡沫使用受场景光照的 HDRP/Lit；修复透明深度、双面与保留高光设置。保留 Resources 材质，避免播放器剥离对应 shader variant。 |
| 水线贴花失效、错误湿感、巨型包围盒 | 保留 HDRP/Decal 模板；按升沉轴计算湿感；几何边界排除航行灯/尾迹特效。FCB45 日志吃水恢复约 1.54m。 |
| 方形号灯巨晕、雨丝粗竖条 | 圆形灯孔、世界尺寸钳位、透明 alpha 不乘亮度；灯色与方位扇区保持原核心。缩窄雨滴、减少拖影，将发射体移至相机上方。自有材质与 Mesh 随宿主销毁。 |
| YOLO 缓存逐渲染帧清空 | 未收到新推理时保留仍新鲜结果，包括合法空检测；只消费最新有效序号。显示 `YOLO live` / `Ground truth demo`，0.5 秒过期门保持不变。 |
| 同机帧发布拖低渲染性能 | 三个异步 GPU 读回槽、单后台 JPEG 编码任务、最高 10Hz、过载跳帧；NetMQ 发送仍在主线程。停止/resize 等待本组件编码与读回完成后释放纹理。 |
| 协议缺字段被默认零值掩盖 | 必需字段严格反序列化，验证框形状/有限值/置信度。Python 服务验证 multipart、元数据、JPEG 尺寸，推理前丢弃积压旧帧。 |

## 验收条件与结果

完整 EditMode **411/411**；包含检测渲染节拍、必需字段、固定浮态基准、挂载相机、海况渐变、长帧阻尼、透明材质与停止编码回归。此前对应缺陷已出现红例，再修复转绿。

识别录像补验发现异步 GPU 行序与 JPEG 编码器不一致，已在后台编码前按平台 UV 原点归一化，修复发布画面上下倒置及回传框坐标不一致。新增偶数/奇数高度方向回归后，完整 EditMode **413/413**；重新构建的 Mac Metal 播放器原帧确认天空/HUD 正向、识别框覆盖船体。新证据位于 `output/sango-yolo-video-20261001/`，旧倒置原帧保留在其中 `orientation-before-fix/`。此前的字段/吞吐验收不包含图像方向，不能替代本次方向实拍。

原生 standalone 以实际 **2560×1440**、墙钟时间采样；性能窗口独占本机 GPU，未与 Editor/Recorder 并行。

| 路径 | High 静态 | High 航行 | Low |
| --- | ---: | ---: | ---: |
| 展示路径，publisher OFF | 34.86 FPS | 34.50 FPS | 35.41 FPS |
| 最终播放器 + 本机 CPU YOLO | 33.47 FPS | 33.06 FPS | 34.16 FPS |

方向修复后再次完整回环：High 33.51 FPS / 航行 32.95 FPS / Low 34.07 FPS，实际 2560×1440，全部门通过；航行 397/397 渲染帧保持 live，服务 Rx/Tx 978/978。识别视频直接保存发布流 JPEG 原帧及返回 JSON，按采集时间戳编码；约 8Hz 源采样，不作为全渲染帧录像或识别准确率证据。

两路径门均通过：分辨率正确、对应窗口 ≥30 FPS、水高查询失败为零、数值有限、湿感材质在播放器构建成功。回环额外要求各测量窗口 Rx/live 非零；最终航行窗口 99 次回传、395/398 渲染帧保持 live，未扩大 freshness 或隐藏 fallback。CPU 服务共接收/发送 **956/956**；probe **30/30** 有效全尺寸 JPEG。空检测并不等同检测链故障，本结果不评定识别准确率。

Standards 最终复核通过，无并发/生命周期阻塞项；Spec 接受本地视觉样机，保留以下 P2 观感余项。M9 历史三票 round3 的 FAIL 记录未改写；本轮未声称取得新的三票评分。

证据根目录：仓库 `output/sango-stage1-20261001/`。`acceptance/report.json` 为展示路径，`detector-return/report.json` 为最终回环；`editmode.xml`、`probe.log`、`detector.log`、烘焙/构建日志及 `source-manifest.json` 可对账。`terrain-review/` 是已回退的 basemapDistance 试验，不作最终画面基线。

## 保留边界

- Kelvin 臂仍偏规则，中央带近看仍有 Mesh 质感；属于可继续打磨的视觉近似，未计算船舶 CFD、兴波阻力或实船 RAO。
- 远景白带仍有 Sentinel-2 TCI 云污染/高反射地面影响。32km basemapDistance 试验无改善，已回退；保留原始 DEM/GEBCO 与源影像，不以改地理高程掩盖影像质量。后续应使用可追溯云掩膜/无云影像处理。
- 航行灯按观察方位验证；桥楼前向机位不能同时看到位于自身后方的全部桅灯/艉灯。水面 streak 仍是视觉近似。
- FCB45 是尺寸约束视觉重建，未标定实船 CAD、相机内外参或水动力。此处通过的是阶段一展示与感知接口样机验收，未覆盖阶段二 WebSocket 遥测/控制闭环、阶段三传感器/融合/海试资格。
- `video/` 为 Recorder Constant60 离线视频，不能作为实时 FPS 证据。早期 `recording/` 视频为优化过程版本；`final-recording/` 为最终源码复录。

## 本机复跑

场景接线改动必须先烘焙，再构建播放器；禁止以旧场景打包判断脚本是否生效。

```bash
UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity
"$UNITY" -batchmode -projectPath "$PWD/sango" -runTests -testPlatform EditMode -testResults /tmp/sango-editmode.xml -logFile /tmp/sango-editmode.log
"$UNITY" -batchmode -quit -projectPath "$PWD/sango" -executeMethod Sango.Editor.M6StraitSceneBootstrapper.Build -logFile /tmp/sango-bake.log
"$UNITY" -batchmode -quit -projectPath "$PWD/sango" -executeMethod Sango.Editor.M6StraitSceneBootstrapper.BuildStraitPlayer -logFile /tmp/sango-build.log
./sango/Builds/sango.app/Contents/MacOS/sango --sango-verify "$PWD/output/sango-stage1-recheck" -screen-width 2560 -screen-height 1440 -screen-fullscreen 0
```

检测回环：另开终端运行 `.venv-detector/bin/python tools/sango_detector_service.py --device cpu`，播放器同命令加 `--sango-publisher`；probe 用 `.venv-detector/bin/python tools/sango_zmq_probe.py --count 30 --timeout 30`。保证 5556/5557 空闲，关闭其他 GPU 测试后测量。可视操作与录像命令见 `README-M1.md` 本机优化段。
