# [SPEC · 已批准] Deployment H | N | C | 3D 与 OpenBridge AR 标牌

**状态：用户于 2026-09-20 明确同意规格并授权实施。** 以本会话批准为执行依据。先在隔离工作树验证，通过后交付；不能用部分测试代替全项验收。

## Problem Statement

用户希望在当前 Colav-Simulator Deployment 页面中观察仿真航行的三维过程：看到驾驶台外视景、本船及目标船、未来轨迹和有来源的避碰信息，同时保留现有海图、左右信息栏及运行控制。当前只有二维海图；独立 HTML 演示没有真实遥测、会话身份和可靠坐标/时钟，不能直接成为数字孪生功能。

用户指定底部按钮从 `H | N | F | C` 改为 `H | N | C | 3D`，删除 F，3D 用于视角切换；希望复用 OpenBridge AR Web Components。

## Solution

在现有 Deployment 中加入只读三维展示模式。2D 与 3D 使用同一个 Active Session、Telemetry Playback 和 Telemetry Projection；显示模式切换不创建、重置、暂停或替换会话，不改变 Run Specification。

**首版建议：现有 Canvas ENC + CesiumJS 三维场景 + 官方 OpenBridge AR DOM 标牌。** Cesium 完成本船/目标、航线与预测、基础海面和相机；官方 POI 组件完成标牌排布与分组。第一版不要求叠加 Three.js。用户最初提出的 Cesium+Three.js 混合方向保留为后续选择：只有实测证明 Cesium 原生能力不足以满足已批准需求时，再批准双引擎同步工作。

三维页保留现有顶栏、左右栏、播放/暂停/倍速与状态。首次进入默认“驾驶台”机位，场景内小型机位控件支持“驾驶台 / 追随 / 俯视”。展示标识为“仿真三维视景”；不宣称已完成实船同步、传感器 AR 配准或导航设备认证。

## User Stories

1. As a simulation operator, I want H, N, C and 3D in that order, so that the requested view controls remain compact and predictable.
2. As a simulation operator, I want F removed from Deployment, so that fit-to-traffic no longer occupies the view strip.
3. As a simulation operator, I want H to retain Heading Up, so that the chart follows vessel heading.
4. As a simulation operator, I want N to retain North Up, so that I can restore geographical orientation.
5. As a simulation operator, I want C to retain Centre on Ownship, so that it does not silently become Course Up.
6. As a simulation operator, I want 3D to enter the scene and return to my previous chart view, so that exploration remains reversible.
7. As a simulation operator, I want H or N in 3D to return directly to that chart orientation, so that exit is unambiguous.
8. As a simulation operator, I want C in 3D to restore ownship framing for the current camera preset, so that panning cannot leave me lost.
9. As a simulation operator, I want bridge, chase and top camera presets, so that I can compare local sightlines and overall encounter geometry.
10. As a simulation operator, I want the camera to follow heading rather than ground course, so that side drift remains understandable.
11. As a simulation operator, I want existing runtime controls and sidebars available, so that 3D does not become a separate application.
12. As a simulation operator, I want the same session identity and displayed time in both views, so that switching does not restart the encounter.
13. As a simulation operator, I want motion and labels to remain aligned under pause and speed changes, so that display animation cannot invent vessel motion.
14. As a simulation operator, I want buffering or disconnection shown explicitly, so that frozen evidence is not mistaken for live state.
15. As a simulation operator, I want old ships and labels cleared on Session Replacement, so that data from different runs never mix.
16. As a simulation operator, I want all current target vessels represented, so that label decluttering does not remove traffic from the world.
17. As a simulation operator, I want truth and tracked positions distinguished consistently with the chart, so that synthetic knowledge is not presented as sensor evidence.
18. As a simulation operator, I want official OpenBridge POI symbols and grouping, so that the AR interaction matches the surrounding UI.
19. As a simulation operator, I want selecting a 3D target to open the same vessel information, so that selection is shared across views.
20. As a simulation operator, I want selection separate from Planner Primary, so that clicking does not change avoidance duties.
21. As a simulation operator, I want target DCPA, TCPA and responsibility from the canonical snapshot, so that 2D and 3D do not disagree about threat facts.
22. As a simulation operator, I want unavailable, stale or invalid evidence displayed as such, so that missing data never becomes a safe green value.
23. As a simulation operator, I want crowded labels expandable, so that individual contacts remain inspectable.
24. As a simulation operator, I want behind-camera and offscreen targets handled explicitly, so that cards are not projected onto unrelated screen positions.
25. As a simulation operator, I want mission routes, planned predictions and actual history visibly distinct, so that prediction is not confused with guaranteed execution.
26. As a simulation operator, I want prediction ages and time markers based on available plan evidence, so that old or untimed paths do not appear current.
27. As a simulation operator, I want model dimensions and missing attitude identified honestly, so that low-detail graphics are not mistaken for a calibrated six-degree-of-freedom vessel.
28. As a simulation operator, I want local resources and explicit unavailable geography, so that missing online maps do not prevent basic scene use or fabricate terrain.
29. As a simulation operator, I want usable fallback to the chart after a rendering failure, so that a 3D error does not disrupt my simulation session.
30. As a keyboard user, I want named controls, visible focus and correct pressed states, so that view switching is accessible.
31. As a maintainer, I want one display integration boundary, so that new renderers do not duplicate session, playback or risk logic.
32. As a reviewer, I want coordinate, browser and lifecycle evidence, so that a screenshot alone cannot be treated as completed integration.
33. As a simulation operator, I want compact numbered symbols and expanded data cards inspired by the supplied references, so that labels stay small until details are needed.
34. As a simulation operator, I want distance rings and bearing marks in the chase view, so that I can judge relative geometry without treating them as safety boundaries.

## Implementation Decisions

以下决定已获用户评审同意。

### 1. 按钮与状态

| 输入 | 2D 下行为 | 3D 下行为 |
|---|---|---|
| H | Heading Up | 返回 2D Heading Up |
| N | North Up | 返回 2D North Up |
| C | 当前本船居中行为 | 恢复当前机位默认偏移与本船锁定；保持 3D |
| 3D | 保存 2D 方向、缩放、平移及选择，进入 3D | 返回保存的 2D 状态 |

选择为跨视图共享状态：无新选择时保留进入前选择；在3D明确选择新目标后，返回2D保留该最近选择，不以旧ID覆盖用户动作。

H/N 为海图方向选项；3D 为显示模式；C 为瞬时动作，不能四个按钮都做同语义 radio。3D 激活时仅 3D 呈按下状态；H/N 返回海图后恢复对应按下状态；C 不保持按下。

首次进入使用驾驶台机位；同一会话内再次进入保留上次机位。Session Replacement 清除目标选择与场景对象，重置机位到驾驶台，方向偏好可保留。无有效本船/地理基准时 3D 禁用并给出原因；加载中重复点击不创建第二个 Viewer，H/N 可取消进入。初始化失败保留或恢复 2D，显示失败原因与重试入口。

不删除共享 fit-to-traffic API，不改变 Evaluation 原有按钮和 Config 预览。删除 F 仅涉及 Deployment 可见控件及其专属绑定。

### 2. 渲染职责

- Display mode controller 负责模式、生命周期和相机预设；两个具体显示适配器消费同一呈现数据。只增加此实际接缝，不预建通用渲染插件框架。
- 首版 Cesium 使用低面数本船/目标模型、基础海面、任务航线、历史轨迹和规划预测。能用原生模型/图元完成的内容不引入 Three.js。
- 无真实三维地形时展示明确标识的平面地理参考；没有资产的岸线不挤出虚构山体。已有 ENC 作为经正确重投影的平面参考，可通过现有图层开关控制；超出覆盖范围显示无海图覆盖。
- 3D 相机自由查看只改变视觉状态。驾驶台眼点/追随距离来自声明的显示配置，默认眼点为示意值，不能声称符合真实船图。缺失 roll/pitch/heave 不生成波浪摇摆。
- 追随/俯视可开启以本船为中心的0.50/1.00NM距离环和方位刻度，均按真实米制坐标绘制并随相机透视；这些是距离参考，不是安全域。沿用当前主题的低干扰线型，不复制参考图的整套黑青界面或意义不明的红橙告警带。
- 3D 中保留有意义的船舶、航线、预测、历史图层；仅适用于海图的量测、二维决策平面叠加和比例尺应禁用/说明或留在 2D，不能静默展示错误单位。鼠标缩放与触控板操作作用于当前渲染器。

### 3. 统一时间与选择

- 唯一输入来自 Active Session 的既有 Telemetry Playback → Telemetry Projection；不新开遥测连接，不让 Cesium Clock 自行推进船位。
- 呈现身份包含 run_id、seq、render_time_s 和原始证据时间。motion-only 更新与普通更新均送到当前视图；风险/规则只随相应 canonical snapshot 更新，不能按运动插值重算。
- 对已经 Playback 插值的帧，2D/3D 在共享最终采样边界消费相同坐标。处理现有 Canvas 二次插值，不能简单并列订阅后宣称“同帧”。非缓冲输入和 Config/Replay 现有行为通过回归保护。
- 暂停保持姿态；缓冲耗尽保持最后真实状态并显示 buffering；禁用位置外推。用户仍可转动观察相机。倍速来自现有运行控制，不乘到另一个物理时钟。
- Session Replacement、退出页面和异步加载使用 generation/run_id 守卫；旧加载不得重新挂入新场景。
- 目标身份使用 run_id + target_id + generation。2D 与 3D 共享用户选择，但 selection 永远不改 Planner Primary 或后端职责。

### 4. 坐标与地理数据

- 输入局部 x/y 分别为相对于 ENC 原点的 UTM North/East；绝对 north/east 为网格坐标。先还原绝对坐标，再按当前水平 CRS 转 WGS84/ECEF。不能把 UTM 差值直接作为精确 ENU。
- 优先在显示边界采用固定版本的批量本地投影转换，并以现有后端转换为数值基准。每目标每帧 HTTP 转换禁止。只在现有 ENC metadata 增补有来源的水平 CRS 标识、半球和竖直显示基准；不新增世界服务或物理数据总线。
- 当前 CRS 只覆盖已有 zone 32/33。未知 CRS/缺失 origin/run_id 不猜测；阻止地理 3D 并提示。海面 h=0 是明确的显示约定，不冒充潮位/NN54 到椭球高的测量结果。
- 船位、目标、航点、历史与预测使用同一转换。模型朝向校核网格北/真北差异与模型局部前轴；Heading 与 COG 分别保留。
- ENC 投影栅格通过带地理位置的采样网格或等价重投影处理，不当作任意经纬矩形贴图。采样密度以全范围误差验收驱动，不硬编码一个四角平面后忽略内部误差。
- 新显示字段向后兼容；不改 PlannerInput、动力学、威胁门限或评价器。

### 5. OpenBridge AR 组件与数据

- 以官方 AR POI Layer、POI Group、POI Card、POI Vessel 等已发布组件作为显示材料；按固定版本能力选择最小集合。Layer Stack / Controller 仅在职责确有需要时接入。
- 固定基线为当前包1.0.1，官方对应源码提交 `0101c4d2310f72aa4362b0991e81ae517b2715ac`，包含上述层组件。POI Controller面向图像/视频检测框适配，合成3D首版不为“有AR”而强行使用它；Cesium投影直接供POI数据与层布局。
- POI Layer 管屏幕排布，不管世界投影和风险。显示适配器负责相机矩阵、完整视锥检查、CSS 像素位置、DPR/resize 与有效可见性，再交给官方组件。
- 默认采用官方 grouping；位置交叉、聚合/展开均保持目标身份。不得另写一套与其竞争的分组算法。`isSelected` 若在所选版本仅反映属性，不作为自动选择管理的保证。
- 使用目标锚点、引线与紧凑标牌；优先天空区域排布是本项目显示策略，不能伪称所有机位下的强制海事标准。俯视无天空时使用顶部标牌带/边缘布局，明确与目标连线，避免把卡片钉到错误水面位置。
- 镜头后方不画世界锚定卡片；出屏隐藏锚定卡片。选中/主威胁出屏时，在场景边缘给出方向提示和稳定目标身份；不把屏幕裁剪后的点伪装成真实投影。
- 首版无实测三维遮挡场，不能声称自动解决真实山体/船体遮挡。平面参考下标牌属于信息叠加；未来 terrain 接入须先补深度遮挡验收。
- 目标卡显示身份、来源/质量、有效的 DCPA/TCPA、会遇/角色、证据时间。距离/方位若 canonical 字段缺失则不可用；不另算出一套风险事实。COLREG 解释只映射已有事实，不生成没有证据的因果结论。
- 参照用户四图，默认圆形类别徽标或紧凑竖牌＋稳定编号，点选展开官方详情卡。展开卡包含可用的船名/ID、来源、BRG/RNG、CPA/TCPA、HDG/SPD及单位；沿用已有字段的真实语义，HDG不可偷偷用COG替代，SPD明确是SOG还是STW。来源仅按provenance标AIS/Tracker/God等，不复制示例AIS。缺失字段显示不可用。详情卡可占据视景一角，不承诺“所有卡片永不覆盖海面”。
- 风险样式复用 canonical display class 的显式映射；未知映射为不可用，不能按固定门限造红/黄/绿。让路职责本身不等于最高告警等级。第一版不新增闪烁或声音告警。
- 密度管理只折叠标牌；不删除船体、改变 planner target set 或把隐藏标签视为安全。选中目标与主威胁在组内可识别并可展开。

### 6. 航线和预测语义

- 任务航线、实际轨迹、当前预测、过期预测和可执行路线必须区分。没有执行接纳证据时标为“预测”，不能标“已接纳安全航道”。
- 第一版保证中心线与已有时间证据。只有存在带单位、有来源的航宽/XTD 数据时才画定量走廊；不得复制演示的固定 36m 带宽。
- 时间节点取规划提供的采样时间或明确 dt；无时间依据不自行填 60/120/180s。旧预测按原有过期规则显示或隐藏，不移到当前时刻冒充新解。
- 三维通过不能替代 G3 安全、COLREG 行为、L4 接纳或 Independent Evaluator 结论。

### 7. 资源与失败处理

- 按现有 vendor 方式固定版本、本地加载引擎、worker、样式和模型；首次进入再加载 3D。默认不依赖公共 CDN、ion token 或外部底图账户。
- 官方 Storybook 当前页面与本地包版本分别记录。优先复用当前 1.0.1；若所需 API 需要升级，先核版本差异和组件回归，统一 bundle/CSS，禁止两份同名 custom element 并存。
- 退出 3D 停止不必要绘制，保留轻量相机状态；退出页面/换会话回收 GPU 对象、事件监听和旧 POI。WebGL 不可用或 context lost 时给出明确状态并恢复海图。
- 不把模型、海图和影像许可合并成一个引擎许可。交付记录每项实际依赖与素材来源；无现成资产时使用工程示意模型。

## Testing Decisions

**用户已确认主边界：Telemetry Playback → Telemetry Projection → Deployment。** 优先验证外部可观察行为、帧身份、数据一致性与交互结果，不用大量源码正则或类名快照证明功能成立。

既有测试先例：Telemetry Playback 的可控时钟与断流样本；Telemetry Projection 的 canonical threat / unavailable 样本；Situation Display 的注入式 canvas、session/ENC generation 守卫；Active Session Runtime 的副作用记录；Kinematics 的角度插值；浏览器启动与主题检查。浏览器 GPU 渲染无法由 Node stub 代替。

| 编号 | 场景 | 可验证完成条件 |
|---|---|---|
| T1 | 按钮与往返 | Deployment 精确 H/N/C/3D，F 不可见；C 无持久 pressed；所有切换符合表格；保存/恢复方向、平移和缩放 |
| T2 | 会话副作用 | 连续切换 20 次，run_id 不变；无 create/reset/pause/speed 请求，无第二个 telemetry WebSocket |
| T3 | 同帧 | 固定输入序列下，两适配器收到相同 run_id/seq/render_time；在同一采样时刻位置、艏向和选择一致，无额外插值延迟 |
| T4 | 时钟状态 | 1x/2x/5x、pause/resume、求解停顿、长断流、terminal drain 均沿用 Playback；断流无新造运动，证据时间保持可追踪 |
| T5 | 会话隔离 | 旧资源加载晚到、旧 frame 晚到、target id 复用但 generation 改变，不出现旧船/旧卡或风险串绑 |
| T6 | 地理转换 | zone 32/33 已知点、四象限艏向、角度环绕；与后端基准比较水平误差 ≤0.5m；错误 CRS 明确阻止 |
| T7 | ENC 配准 | 当前 6km 区域角点、中心和内点网格测试，船位/航线与投影底图配准误差 ≤1m；网格北/真北处理一致 |
| T8 | AR 布局 | 单船、两个重叠、16 船、移动交叉、组展开、后方/出屏、俯视、resize/DPR=1/2，卡片身份稳定且不投影到错误位置；紧凑/展开卡对照四张参考图检查；距离环0.50/1.00NM=926/1852m |
| T9 | 风险权威 | 有效/缺失/过期/不同 generation 的 canonical snapshot；与2D同值；缺失不是绿色安全，点击不改变主威胁 |
| T10 | 路线语义 | 任务/历史/预测可辨；无宽度不画定量安全带，无时间不造节点；无接纳凭证不标执行已安全 |
| T11 | 运行环境 | 本地资源齐备、外网禁用时基础3D可用；模拟模型丢失、引擎加载失败、WebGL context loss 可回2D；会话继续 |
| T12 | 可用性与回归 | 键盘Enter/Space、焦点、pressed、主题、侧栏折叠和窗口resize正确；Config与Evaluation现有功能回归通过 |
| T13 | 性能目标 | 记录真实设备/GPU/浏览器，1920×1080、DPR=1、16船基础场景5分钟，暖启动后p95帧耗时≤33.3ms；切换后交互响应≤250ms；结果未测前不得声称达标 |
| T14 | 资源释放 | 20次切换、5次会话替换后，无重复listener、render loop、POI或增长的活跃GPU对象；提供计数/浏览器诊断 |

T6/T7 容差为本规格提议的数值配准门槛，不是海图测绘精度或导航安全保证。T13 若目标设备不满足，应报告瓶颈与降低视觉负载方案，不降低数据正确性要求或偷偷删目标。

实施验收命令以现有 `node --test tests/web_gui/*.test.mjs` 为前端回归入口；如扩展 ENC 元数据，追加现有 Web API、transport、clock/ENC 合同的针对性 pytest。真实浏览器在隔离开发服务完成上述场景并保存证据；通过前不替换 8010。代码测试输出、截图、性能记录分别报告，截图不代替时间/坐标证据。

## Out of Scope

- 未经验收直接替换 8010。
- Evaluation 回放加入3D、跨窗口多屏硬同步、独立驾驶室页面。
- Three.js 双引擎叠层、Unity迁移、WebGPU专用管线、写实海浪和港口建模。
- 真实视频 AR、摄像机标定、雷达原始回波、LiDAR、感知合成和实船遥测接入。
- 新增手动操船权、改变自主/应急仲裁、控制器/动力学/避碰/评价逻辑。
- 自动补全6DOF、数字孪生模型校准、S-52/S-101/ECDIS或IEC符合性认证。
- 更改整个前端框架、把2D海图迁到Cesium、全局重构与未请求的告警体系。

## Further Notes

调研已核当前 8010 与源码基线、Gemini 分享、HTML 演示、官方 Storybook；研究文件保留源码路径和具体证据，Implementation Decisions 刻意仅用职责名称。

用户后补四张 OpenBridge/古野截图已纳入：水面目标框和天空紧凑标牌、圆形类别徽标、点选展开的航行信息卡、追随视角航线与距离环。它们限定视觉意图，不直接证明颜色语义、风险规则、真实资产或官方强制规范。将截图照片替换为合成视景并不等于已实现真实视频AR。

评审顺序：①首版 Cesium 单渲染器与 Three.js 延后；②按钮表、驾驶台默认机位与3种机位；③AR信息/预测边界；④坐标和性能门槛。批准本规格后才进入实现。

阶段建议：A 模式和同帧数据接入 → B 地理/模型/相机 → C 官方AR标牌与真实预测 → D 浏览器、失败恢复与性能验收。每阶段只推进该阶段所需改动，最终交付须全部通过，不能以“按钮可点击”结束。

相关一手来源：[OpenBridge POI Layer](https://openbridge-storybook.web.app/?path=/docs/ar-poi-layer--docs)、[OpenBridge AR Framework](https://www.openbridge.no/cases/ar-framework)、[Cesium Model](https://cesium.com/learn/cesiumjs/ref-doc/Model.html)、[Cesium Transforms](https://cesium.com/learn/cesiumjs/ref-doc/Transforms.html)。工程建议与官方能力事实分开解释于配套调研。


### Approved asset addition during implementation

用户于实施中追加 `FCB45_Cesium_LOD0_v0.glb` 与 `target-vessel-model-downloader.zip`，要求集成现成模型。本船使用提供的GLB，目标模型按清单本地化；只选完整船体进入运行目录索引。目标详情增加本地“显示外观”选择，明确不修改船型、尺寸或动力学事实。未知类别使用标明来源的视觉代理，不随机赋予AIS船型。新增资产重新验证坐标轴、尺寸、水线、资源失败与多目标性能。
