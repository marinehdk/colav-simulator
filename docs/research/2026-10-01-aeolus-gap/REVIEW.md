# 最终双轴评审与验收

日期：2026-10-01。本机 Mac，未连接 A4000。

基线 `cbad8202` 为本轮开始时用户要求的全部阶段一代码存档。规格 [SPEC.md](SPEC.md)，已按用户调用的 [to-spec 技能](/Users/marine/.agents/skills/to-spec/SKILL.md) 发布 [GitHub #88](https://github.com/marinehdk/colav-simulator/issues/88)。实施基于该规格，不复制 Aeolus 未公开源码/资产。

评审采用提交前 staged diff `git diff --cached cbad8202` 和最新 disk；Standards / Spec 两个独立子代理并行复核。最终提交在复核后执行；此固定基线覆盖全部本轮实现。仅手写文件运行 whitespace check；Unity 重烘焙的场景/Volume 保留引擎序列化格式与重新生成的引用 ID。

## Standards

**PASS；未解决发现 0。**

- FramePublisher 契约与 CameraCaptureBridge 实际路径一致；三槽异步 GPU 读回、单个后台 JPEG 编码，保持源帧时间与方向；排除 GUI/旧框反馈，不二次渲染主场景。
- Apply & start 先应用 draft；运行时禁止重建；Apply/Load 刷新目标编辑状态；有限数/非法航点输入拒绝，不留部分世界变更。
- 水平/艏向仍由同一运动学状态负责，浮态负责垂直/横纵摇；主船切换重绑相机/雷达/真值列表。
- FpsProbe 保留采集/日志，仅隐藏本工作台显示；菜单仅抑制检测显示，不停止回传；Radar pivot 修正后全盘在屏内。
- 三槽读回的全局等待只在停止/释放时执行，属于资源安全边界；未新增后台控制系统或算法逻辑。

## Spec

**PASS；未解决发现 0。**

- Setup 字段形成真实 public 控制链：双场景、预算、Perlin、洋流、航点、船型、EGO、感知参数、运行生命周期与天气。
- 单环境目标船可逐船增、改、删，设置不同船型、初始位置/艏向、速度、静止/直航/航点运动；稳定 ID 与 JSON 场景存取通过原生按钮事件验证。
- 固定前向船载相机关闭真值辅助追随，ego 与目标均运动；真实 YOLO 对运动他船产生匹配框，帧输入无 HUD。
- 六工况分开报告渲染、回传、空检和目标匹配；雾窗口 targetMatched=0 如实保留。真值 radar、黄色 GT fallback 与绿色 YOLO 分开标识。
- UI-only 补验通过：菜单无检测框、船模预览正立、雷达盘完整可见。OS 鼠标未计验收：computer-use 仍报告锁屏，用户已确认的 public Unity Button/InputField seam 已通过。

Standards 0 项；Spec 0 项；两轴均无未解决 blocker。

## 代码与运行验收

- 最终 EditMode：**421/421 PASS**，0 skipped/failed；原始 XML、日志在 `output/aeolus-acceptance-20261001/editmode-tests.*`。
- Python：旧帧 envelope 兼容；3 个合法 confidence 阈值接受，8 个非法阈值拒绝；服务和协调器编译通过。
- M6 bake 与 player build 成功。最终本机 binary：`sango/Builds/sango.app`，bundle `com.colav.sango.workbench`，避免误启旧 M1/M2E 实验播放器。
- 原生新增/编辑/删除/保存/载入通过；目标编辑速度从 2 改为 5 m/s 后读取 public definition 确认，删除回到两艘，保存/载入后维持两艘。
- 实际分辨率 **2560×1440**，六窗口水查询失败 **0**。ego 约 48 m、目标约 42 m；`truthAssistedCameraLock=false`。

| 工况 | wall-clock FPS | 收到结果 | fresh 渲染帧 | 匹配目标的渲染帧 |
|---|---:|---:|---:|---:|
| 昼 | 51.37 | 81 | 547 | 306 |
| 暮 | 51.42 | 80 | 529 | 392 |
| 夜 | 43.45 | 76 | 299 | 35 |
| 雾 | 51.19 | 80 | 552 | **0** |
| 雨/湿镜头 | 50.91 | 80 | 525 | 329 |
| 高海况 B6 | 50.20 | 81 | 542 | 177 |

匹配统计按渲染帧累计，可能重复展示同一个源结果；GT IoU ≥0.3 只确认当前场景识别的是他船，不是 AP/precision/recall。雾 7 个非空渲染帧最佳 IoU 0.158，不算目标识别成功；夜间回传少量检出且有空检/过期。界面、链路和性能通过不代表恶劣工况感知可靠性通过。

32 船规模单独实测：16×2 FCB45，1440p，约 **49.80 FPS**，水查询失败 0；该值仅这一布局/视角，不能外推所有船型、全船近景特效或并行推理负载。

## 证据与录像

版本化摘要：[native-report.json](evidence/native-report.json)、[authoring-buttons.json](evidence/authoring-buttons.json)、[ui-final-report.json](evidence/ui-final-report.json)、[scaling-32.json](evidence/scaling-32.json)、[scene.json](evidence/scene.json)、[模型 SHA256](evidence/model-and-capture.json)、[视频时间/编码](evidence/video-evidence.json)。

原始完整本机证据 `output/aeolus-acceptance-20261001/`：1194 个纯传感 JPEG/metadata、1186 条真实 YOLO 回传；native 窗口记录起止时间和天气值；录像保存 capture_time_s、真实状态及对应结果。模型 `yolov8n.pt` SHA256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`。

[六工况船载 YOLO 视频](/Users/marine/Code/Colav-Simulator/output/aeolus-acceptance-20261001/native/videos/onboard-yolo-six-conditions.mp4)，六个单独视频同目录。视频是原生画面定时采样后按真实时间编码为 30 FPS，保留真实框、空检与 GT fallback；采样在性能测试之后进行，编码 FPS 不充当实时性能证据。显示修正后的静态证据在 `ui-final/`；视频保持其采集时原样。

使用步骤与复跑命令见 [USAGE.md](USAGE.md)。原始 JPEG/视频/player 属本机产物，不将大量媒体纳入源代码提交。

## 下一阶段接口边界

当前已提供可复现场景定义、异构目标运动和船载图像/检测展示；为避碰适配器提供稳定 ID、米制 east/north、艏向度及初始速度。尚未执行后端控制闭环、世界坐标跟踪、AIS/雷达融合或 COLREG 避碰。现有海谱、浮态、雨雪雷电/湿镜头为视觉近似；没有新增 ML-Agents/PPO 训练、私有 Aeolus 策略或物理资格声明。
