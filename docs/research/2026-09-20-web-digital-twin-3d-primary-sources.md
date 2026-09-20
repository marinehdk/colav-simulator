# 8010 Web 数字孪生与 OpenBridge AR POI 一手来源调研

日期：2026-09-20。范围：在现有 Deployment 海图视区加入 `H | N | C | 3D` 视角控制，评估 Cesium 单引擎、Cesium + Three.js、Unity Web，以及 OpenBridge POI 组件的真实能力。本文只记录能追溯到官方文档、项目源码或标准的事实；对话和 `digital_twin_demo.html` 作为方案线索，不视为规范或实现证据。

## 结论

可以基于 8010 实现。第一阶段建议保留现有 2D 海图和 H/N/C 操作，在同一 Deployment 视区以 3D 按钮切换 Cesium 视图；两个视图读取同一个带 `run_id`、`sim_time`/帧号的状态快照。Cesium 官方 API 已支持地理定位 glTF/GLB 船模、地理坐标转屏幕坐标和地形/影像图层。对当前目标，暂时没有必须同时引入 Three.js 的证据；只有确认 Cesium 无法满足的水面材质、特殊模型或后处理需求后，再做混合渲染验证。[Cesium `Model`](https://cesium.com/learn/cesiumjs/ref-doc/Model.html)、[Entities / glTF](https://cesium.com/learn/cesiumjs-learn/cesiumjs-creating-entities/)

OpenBridge 官方确有 AR POI 设计框架和可运行 Web Components；“OpenBridge 6.0 AR 标牌标准”说法过强。官方页面把 AR 内容称为 framework/case，公开材料将其描述为设计框架与研究项目，并未证明这是经监管批准或具有强制效力的 AR 标准。[OpenBridge AR framework](https://www.openbridge.no/cases/ar-framework)、[OICL OpenAR](https://www.oicl.no/projects/openar)、[AR 导航界面设计研究](https://www.mdpi.com/2077-1312/12/3/505)

## 已核实事实

### OpenBridge 组件、版本和边界

- 官方 AR framework 页面介绍 POI anatomy（按钮、指针、数据块）、选择模式、空间仪表和对象族，并链接到名为 OpenBridge 6.0 AR Framework 的 Figma 文件。页面本身称它为 case/framework；因此可把它作为设计和组件参考，不能称为已发布的 AR 强制规范。Figma 文件页面无法由本次抓取读取；具体设计条款仍应以官方 Storybook/Figma 原件评审。[官方 case](https://www.openbridge.no/cases/ar-framework)、[Figma 6.0 AR framework](https://www.figma.com/design/1539167811791910040/openbridge-6-0-ar-framework)
- 官方 Web Components 发布包 `@oicl/openbridge-webcomponents@1.0.1` 含 `poi-layer`、`poi-controller`、`poi-layer-stack` 的构建产物和类型声明；该版本映射到上游 commit `0101c4d2310f72aa4362b0991e81ae517b2715ac`。包版本 `1.0.1` 与设计文件的 `6.0` 是两套版本号。[npm 1.0.1](https://www.npmjs.com/package/@oicl/openbridge-webcomponents/v/1.0.1)、[固定 commit 的 POI 源码](https://github.com/Ocean-Industries-Concept-Lab/openbridge-webcomponents/tree/0101c4d2310f72aa4362b0991e81ae517b2715ac/packages/openbridge-webcomponents/src/ar)
- 当前本地 8010 已 vendoring 1.0.1，并导入 `chart-object-vessel-button` 和 `poi-card`；尚未在入口中导入 `poi-layer`、`poi-controller`、`poi-layer-stack`。本地捆绑没有运行时 CDN 依赖。[本地 vendoring 说明](../../web_gui/vendor/openbridge/README.md)、[本地组件入口](../../web_gui/vendor/openbridge/entry-source.mjs)
- `obc-poi-layer` 接受 `x/y` 屏幕坐标，负责目标重叠后的 grouping 或 crossing、可选自动分组和 `layer-resize {height, label}`。它不把经纬度或 3D 世界坐标投影到屏幕。`isSelected` 在 layer 类中只有 attribute 反映和 TODO 注释；`poi-layer-stack` 另行管理选择行为。[POI layer](https://github.com/Ocean-Industries-Concept-Lab/openbridge-webcomponents/blob/0101c4d2310f72aa4362b0991e81ae517b2715ac/packages/openbridge-webcomponents/src/ar/poi-layer/poi-layer.ts)、[POI stack](https://github.com/Ocean-Industries-Concept-Lab/openbridge-webcomponents/blob/0101c4d2310f72aa4362b0991e81ae517b2715ac/packages/openbridge-webcomponents/src/ar/poi-layer-stack/poi-layer-stack.ts)
- `obc-poi-controller` 用于 video/image 媒体里的 detection 框；其 `contain/cover` 逻辑在媒体像素和显示矩形之间缩放坐标。它不是 AIS/仿真目标的地理坐标转换器。[POI controller](https://github.com/Ocean-Industries-Concept-Lab/openbridge-webcomponents/blob/0101c4d2310f72aa4362b0991e81ae517b2715ac/packages/openbridge-webcomponents/src/ar/poi-controller/poi-controller.ts)、[官方 Storybook POI layer](https://openbridge-storybook.web.app/?path=/docs/ar-poi-layer--docs)
- 官方页面未证明“水面卡片”“Sky-pinned POIs”存在普遍禁令，也未为 DCPA/TCPA 定义通用阈值。本次能访问的公开代码没有这些规则；Figma 原件抓取受限，所以不能据此断言完整设计文件中不存在相关个别建议。Gemini 对这些规则的陈述须逐条对照官方设计原件，不能直接当规范。

### 8010 当前视图与用户要求

- 当前海图控件为 H、N、F、C：H/N 切换 heading-up/north-up；F 调用 `fitTraffic()`；C 调用 `recenterOwnship()`，含义是“中心置于本船”，不是 course。用户要求的是 H、N、C、3D，并将 3D 放在最后作为视角切换。该改动尚未实施。[Deployment 控件](../../web_gui/index.html#L534)、[当前行为绑定](../../web_gui/app.js#L496)
- 建议把数字孪生视景称为 3D/AR-style overlay。浏览器视角加屏幕 POI 标牌不等于 HMD see-through AR：原型没有证明真实相机姿态、SLAM/头部追踪、标定或传感器融合链路。附带 HTML 自行推进硬编码 `simState`，只适合作为视觉草图，不能证明已接通 8010 仿真状态。

### Cesium 单引擎与混合 Three.js

- Cesium `Entity.model`/`Model.fromGltfAsync` 可加载 glTF/GLB，给出地理位置和 orientation；不需要 Three.js 才能摆放和驱动船模。[Cesium 3D model API](https://cesium.com/learn/cesiumjs/ref-doc/Model.html)、[Creating Entities](https://cesium.com/learn/cesiumjs-learn/cesiumjs-creating-entities/)
- Cesium 的 `SceneTransforms.worldToWindowCoordinates` 将地理世界坐标投影到浏览器窗口坐标，文档明确该接口常用于把 HTML 元素放在 3D 场景对象的屏幕位置。它可作为 Cesium → OpenBridge POI 的适配缝；高 DPI/页面缩放时要区分窗口坐标与 drawing-buffer 坐标。[SceneTransforms](https://cesium.com/learn/cesiumjs/ref-doc/SceneTransforms.html)
- Cesium 可深度测试自身的 billboard/label 等图元；OpenBridge POI 是 HTML/Web Component，不能自动读取 Cesium 深度缓冲。因此遮挡、离屏、目标在船体/地形后方时的显隐需由适配层定义和验证。此结论是两个渲染层边界的工程推断。[Cesium Globe depth test](https://cesium.com/learn/cesiumjs/ref-doc/Globe.html)
- Cesium 官方 GitHub 的 `cesium-threejs-experiment` 自称小型实验。代码创建独立 Three renderer/canvas，每帧先渲染 Cesium，再复制 Cesium 相机矩阵和视场角给 Three 相机并渲染 Three。它证明混合做法可行，不证明它是受支持的必选架构；两个渲染器的相机同步、深度/遮挡、资源占用和每帧渲染需额外处理。性能代价尚无 8010 实测。[CesiumGS experiment](https://github.com/CesiumGS/cesium-threejs-experiment)
- **推断/推荐：**首个可评审切片用 Cesium 单 3D renderer；Three.js 留作之后可替换的渲染扩展。这样仍可保留 8010 的 2D ENC 主视图和 OpenBridge DOM 面板，避免先承担双相机、双渲染循环和跨渲染器深度问题。

### 坐标、同步、离线和许可

- Cesium ENU 固定帧定义为 x=East、y=North、z=Up，并以指定地理原点转换到 Earth-fixed 坐标。UTM 是带 zone/central meridian、尺度因子和假东/假北的 Transverse Mercator 投影坐标，不是 ENU。应从项目实际 CRS（EPSG、datum、zone、单位、高程基准）逆投影到 geodetic，再转 ECEF/局部 ENU；同时校准 grid north 与 true north/course 的角度差。[Cesium ENU](https://cesium.com/learn/cesiumjs/ref-doc/Transforms.html)、[PROJ UTM](https://proj.org/en/stable/operations/projections/utm.html)、[PROJ Transverse Mercator](https://proj.org/en/stable/operations/projections/tmerc.html)
- 用户确认 Deployment 中 2D/3D 需同一帧验收。建议同一个 8010 页面直接把同一状态快照（`run_id`、仿真时间、单调帧号）送给两种 renderer，不重复推进仿真。WHATWG 定义的 `BroadcastChannel.postMessage` 会为接收者排入 task；标准没有给出毫秒硬实时或帧同步保证，单页内不应把它当硬同步协议。[WHATWG BroadcastChannel](https://html.spec.whatwg.org/multipage/web-messaging.html#broadcastchannel)
- CesiumJS 源码为 Apache-2.0；Three.js 为 MIT。Cesium ion SaaS 提供托管/切片服务，若 8010 必须完全离线，可把 ENC 衍生图层、地形/影像、glTF 等由本机静态服务或评估合适的自托管服务提供；Cesium 官方也记录 ion self-host 路径。地图/ENC 数据的授权另行确认。[Cesium license](https://github.com/CesiumGS/cesium/blob/main/LICENSE.md)、[Three.js license](https://github.com/mrdoob/three.js/blob/dev/LICENSE)、[Cesium ion self-hosted](https://cesium.com/learn/ion/self-hosted/)
- OpenBridge 1.0.1 npm 元数据标记 Apache-2.0；上游 README 同时说明新版本/commit 的延迟许可切换政策。两条来源表述不完全一致，本次未作法律解释；继续使用前应以将要固定的 tarball、对应 LICENSE 和上游版本政策核对。[1.0.1 package metadata](https://registry.npmjs.org/@oicl/openbridge-webcomponents/1.0.1)、[上游 README](https://github.com/Ocean-Industries-Concept-Lab/openbridge-webcomponents#licensing-model)

### Unity Web 对比

- Unity 6 Web 可在浏览器运行，官方说明产物包含 loader/framework JavaScript、WebAssembly 和场景/资产数据；可用 JavaScript plug-in 与宿主网页交互。它不是“不能上 Web”。[Unity Web introduction](https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-intro.html)、[Build folder](https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-building.html)、[Browser scripting](https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-interactingwithbrowserscripting.html)
- Unity Web 受浏览器网络和 WebGL 约束，官方还列出 C# 托管线程不支持、部分 .NET API 限制等。相对 8010 现有 Web UI，它需要管理一套独立 build/asset/runtime 和 JS 数据接口；这是集成复杂度推断，不是性能劣势实测。[Unity Web technical limitations](https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-technical-overview.html)
- 没有同设备、同场景、同画质基准能证明 Cesium/Three 比 Unity 快。Unity 仍适合复用已存在的 Unity 船舶资产/物理管线或将来独立 3D 应用；现阶段以 8010 同页视角切换为目标时，Cesium 单引擎是较小验证范围。

## 建议的首个实现范围与验收边界

1. Deployment 海图控件呈现 `H | N | C | 3D`；H/N 操作原有 2D 方位，C 仍为 centre-on-ownship，3D 切到地理 3D 视角。侧栏和仿真播放控件留在原页面。
2. 先接只读场景快照：本船、目标船、航迹/计划线和 sim_time。先复用现有视图数据，不由 renderer 驱动或修改仿真。
3. 明确 UTM/EPSG/高度基准 → WGS84/ECEF/ENU 转换；Cesium 世界坐标 → CSS 像素后，才把 POI `x/y` 交给 OpenBridge layer。固定已导入的 1.0.1 并只扩展本地 vendored entry，不依赖 CDN。
4. 验收覆盖：同一 `sim_time`/帧号下 2D 与 3D 船位、航向、目标一致；已知经纬度/E/N 控制点和方向转换正确；POI 在 resize、高 DPI、遮挡/离屏、密集目标下定位/分组可用；无网或断网能载入离线场景；实机对比 2D 基线记录加载时间、稳定帧率、内存和 GPU 负载。

## 仍待项目确认

- 配套[当前代码审计](2026-09-20-deployment-3d-integration-audit.md)已确认：UI 的 x/y 是相对 ENC 原点的 UTM N/E，north/east 为绝对网格坐标；现有逆投影函数采用 EPSG 6172/6173→4326。待补的是显式 metadata 合同、垂向显示基准及 heading 网格北到真北的转换验收，不再把坐标类型本身列为未知。
- 现有 ENC/海岸线/水深能否以 3D 可用的数据源复用，转换授权和目标区域数据准备方式未确认。
- 待评审规格已提议默认 grouping、天空紧凑标牌与点选详情，并纳入用户补充的四张参考图；批准前仍不是最终设计。暂无通用 DCPA/TCPA 阈值依据。
- 3D 船模来源、朝向/尺度/水线高度、地形与海面深度策略、目标数量和运行硬件均未冻结；Cesium/Three/Unity 性能选择需在确定场景后实测。
