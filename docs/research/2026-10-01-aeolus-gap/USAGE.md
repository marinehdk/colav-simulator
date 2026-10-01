# 本机场景工作台使用与阶段边界

## 启动

打开 `sango/Builds/sango.app`。本轮仅 Mac 本机运行；无需 A4000。

需要真实 YOLO 时，先启动本机服务：

```sh
.venv-detector/bin/python tools/sango_detector_service.py --device cpu
```

在 Simulation setup 选择 `YOLO + truth radar (no fusion)`，Apply。服务未启动时显示 waiting/unavailable，空回传显示 empty；真值演示标明 GT，不能充当识别成功。

## 创建场景与目标船

1. Simulation setup → Scene：真实海峡或 Procedural experiment。真实地形仅单环境；程序化场最多 16 环境、总计 32 船。先配置默认船型、生成槽数、航点预设、种子和洋流，再 Apply scene。
2. 暂停后点 Targets。左侧选稳定 ID；中央设置船型、局部东/北位置、艏向、速度、Stationary / Straight / Waypoints、循环及自定义航点。
3. 航点格式 `120,100;-120,100`：每对 east,north，分号分隔，单位米。空列表采用预设；速度单位 m/s、艏向单位度。单环境可 Add、Update、Remove；当前 EGO 不能直接删除。删除保留其他 ID，新船复用空槽。
4. 选中船后可 Designate EGO，桥楼/艏机位、手动操舵、雷达原点和导航向量同时切换。
5. Back → Scene name → Save scene definition。Load 从同名本机 JSON 恢复。运行中 Apply/编辑/Load 被拒绝，先 Pause。存档为已应用设置；编辑 draft 后先 Apply。

保存位置：Unity `Application.persistentDataPath/scenes/`；实际绝对路径显示在保存反馈。名称仅字母、数字、`-`、`_`。存档包含 `schema_version=sango.visual-scene@1`、世界原点、设置及目标稳定 ID。局部坐标 east=x、north=z，艏向度；后端 psi 使用正向弧度。此存档是下一阶段适配器输入基础，未创建后端 Active Session。

## 航行与视觉

`Apply & start` 应用当前 draft 并开始本地航点导航；Start / pause 切换运行，Reset 回到初始姿态。Manual / waypoint 切换控制；方向键加减速、转舵。Camera 切桥楼/艏/追随/俯视/总览。蓝色速度/艏向、绿色航点方向与航点文字随配置显示。

Weather 提供时刻、云、雾、Beaufort、风向、波向、发育和对齐，以及独立雨、雪、视觉雷电、湿镜头和质量档。天气及海谱为 HDRP 视觉近似；不代表实船水动力、RAO 或标定光学传感器。

Truth-assisted target camera lock 是可关闭的真值辅助演示，相机朝向附近目标，不输出目标估计距离。关闭后采用固定船载前向视角；最终识别验收使用关闭状态。运行盘明确标记 TRUTH RADAR；它是场景真值显示，不是实测回波或融合航迹。

## 复跑

场景修改先烘焙，再构建 player；Unity 测试、烘焙、构建串行。性能测量时关闭其他 Unity Editor/player、视频编码；不将离线视频 FPS 当作渲染性能。

```sh
UNITY=/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity
"$UNITY" -batchmode -projectPath "$PWD/sango" -runTests -testPlatform EditMode -testResults /tmp/sango-tests.xml -logFile /tmp/sango-tests.log
"$UNITY" -batchmode -quit -projectPath "$PWD/sango" -executeMethod Sango.Editor.M6StraitSceneBootstrapper.Build -logFile /tmp/sango-bake.log
"$UNITY" -batchmode -quit -projectPath "$PWD/sango" -executeMethod Sango.Editor.M6StraitSceneBootstrapper.BuildStraitPlayer -logFile /tmp/sango-build.log
.venv-detector/bin/python tools/sango_workbench_capture.py --out output/aeolus-acceptance-rerun --fixed-camera --record-video
```

协调器仅启停自己启动的服务/player；端口 5556/5557 占用时拒绝启动。输出真实 1440p wall-clock FPS、昼暮夜雾雨高海况独立窗口、原始无 HUD 传感 JPEG/metadata、真实结果、模型 SHA256、场景设置、工况时间线、原生按钮事件验证及 32 船单独规模报告。录像采集在性能窗口结束后进行，原生框/空检状态原样保留。

## 下一阶段接入

已具备场景定义、异构目标船与可复现运动、船载图像回传和识别展示。下一阶段仍需接入世界坐标跟踪、时钟/坐标契约、AIS/雷达融合、COLAV 控制接口及安全验收。当前航点控制不执行避碰策略；夜间和恶劣天气漏检是模型能力缺口，不能由真值框替代。
