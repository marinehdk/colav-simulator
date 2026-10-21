# ownship-mask-v1 — 本船逐像素掩膜真值通道（路线 A）

日期:2026-10-20 · 裁决依据:`docs/research/2026-10-20-ownship-exclusion-segmentation-survey.md` §4.2
（A 孪生原生掩膜为主、C 几何 guard 降级后备;CARLA "Hull"/Stonefish 分割真值同构先例）。
本文冻结线协议与降级语义;实施注入点=替换 P1 `situation_frame.ownship_polygon` 的
`cv2.fillPoly` 多边形供源（HTTP 中继免掉,帧对齐沿用 FRAME_MARKER frame_id 精确匹配）。

## 1. 动机一句话

检测输入接在可转动操作员视口上,本船入画是物理常态——几何投影（水线多边形+底带）
追不上任意视角（上仰/左右转实测泄漏,逐角度补丁不可收敛）。孪生里渲染器直接给
逐像素真值:任意视角精确、零学习、零维护;真实系统的对应物=安装位设计把本船
挡在传感器视野之外。

## 2. 线协议（ZMQ PUB,Sango 播放器 → 检测服务,同机回环）

- 端点:`tcp://127.0.0.1:5558`（`SangoSeamConfig.OwnshipMaskEndpoint`;PUB bind 播放器侧,
  SUB connect 检测侧,SNDHWM 60/RCVHWM 120——掩膜小帧丢旧不积压）。
- 消息 3 段 multipart（与 frame-publisher-v1 三段式同构）:
  - 段1 主题:`"sango.ownship_mask"`
  - 段2 JSON:`{"schema":"ownship_mask@1","frame_id":<u16>,"width":640,"height":360,"rle_bytes":<N>}`
  - 段3 RLE 字节:N 字节,格式见 §3。
- 掩膜分辨率:固定 640×360（16:9,与 sender detect tap 1280×720 同宽高比;检测端
  NEAREST 缩放到当帧尺寸）。掩膜=本船全部 Renderer 表面像素并集（含自遮挡隐藏面,
  ZTest Always——掩膜宁可超集不可漏）;尾流/浪花 decal 不入掩膜（后续可选）。

## 3. RLE 格式（1bit 行程码,冻结）

- 逐行独立编码,行主序、**顶行先行**（与分流帧/JPEG 编码行序一致;Unity RT 读回为
  视口底行先行,发送端编码时垂直翻转——黄金向量锁定此约定,两侧测试共用）。
- 每行:交替 `0游程,1游程,0游程,…` 的 **uint16 小端** 计数序列,**恒以 0 游程开头**
  （行首像素为 1 时首游程=0）;每行游程和 == width;行间不共享游程。
- 值语义:1 = 本船像素（推理前填海灰+轻噪,同 P1 常量 灰 115/σ5）;0 = 放行。
- 全空掩膜 = 360 行 × 单游程 640（uint16 LE = `80 02`）共 720 字节——权威
  "本船不在画",检测端不填不改。
- **黄金向量**（width=4,height=3,顶行先行位图 `0000/0110/0000`）:
  RLE 字节 = `04 00 | 01 00 02 00 01 00 | 04 00`（每行独立:4 / 1,2,1 / 4）。
  C# `EncodeRle` 与 Python `decode_mask_rle` 测试各自对拍此向量。

## 4. 帧对齐与节拍

- 对齐键:分流帧顶部 FRAME_MARKER 像素条解码出的 `frame_id`（twin-bridge-v1 situation
  display 契约,检测端已有移植解码）。掩膜消息的 frame_id = 该掩膜渲染帧的 marker 值
  （`TwinOwnshipMaskPublisher` 在 `TwinSituationDisplay`（order 10000）之后的 LateUpdate
  （order 10001）采 `CurrentFrameId`,相机位姿为该帧终值——与 blit 进视频的 marker 同帧）。
- 发布节拍:marker 变化 ∨ 相机位姿/本船位置有实际移动（阈值:位移>0.01m 或旋转>0.05°）
  才渲+发;上限=渲染帧率,典型 ~10-20Hz。 gst 路由下检测帧来自 sender detect tap
  （编码管线滞后 100-300ms）,掩膜 ZMQ 即时先到——检测端环形缓存（容量 600 帧 ≈
  60fps 下 10s）按 frame_id 精确匹配,天然覆盖视频滞后。

## 5. 降级链（fail-open,任一环缺失不阻断推理）

1. 掩膜命中（frame_id 在环、RLE 合法、有像素）→ 应用掩膜,`ownship_mask="mask"`。
2. 掩膜缺失/损坏/空 → P1 多边形通道（`--ownship-polygon-url` 开启时）→ `"polygon"`。
3. 都缺 → 原帧直推,`"none"`。web 端 P0 锁帧 guard（floorY/polygon/circles）不动,
   仍是显示层最后防线。
- `ownship_mask` 态随 viewport-detections@1 逐帧 POST 透传（可选字段,旧发送端缺省
  None),供记录仪复演与泄漏归因。

## 6. 端点开关

- Unity:组件随 TwinBridgeService 起桥自动挂载（运行时 AddComponent,免场景资产改动）;
  桥断/无 driver/无相机即停发（与 TwinSituationDisplay 同门控）。
- 检测服务:`--ownship-mask-endpoint`（默认 `tcp://127.0.0.1:5558`,空串=关;默认开的
  语义:无播放器掩膜源时 SUB 静默等待,零行为差）。

## 7. 验证路径

- Mac/离线:C#+Python 黄金向量对拍;`tests/test_sango_detector_mask.py` 掩膜环/RLE
  解码/回退链/应用域测试。
- 在线:`--dump-frame` 看海灰填充落位（垂直翻转错=填充镜像,一眼可辨）;检测器日志
  `masked=`/`mask_fb_poly=`/`mask_miss=` 计数;记录仪 `guard` 行加 mask 命中态复演
  上仰/左右转场景本船泄漏清零。

## 8. 修订(2026-10-20 下午):frame_id 元数据直供(生产根因修复)

gst 路由下 sender detect tap 把 2560×1440 缩到 1280×720 后,marker 条减半为
128×8(4px 格)——JPEG 压缩后多格落 (80,175) 歧义窗,**检测端像素解码在生产
100% 失败**(masked=0/mask_miss=2200/mask_rx=7435 实测;web/sender 探针在全
分辨率侧解码不受影响)。修复:sender 在 tap 支路缩放**前**(tap_queue sink pad)
解码 marker,frame_id 按 buffer pts(pts 贯穿 convert/scale/jpegenc 不变)对位,
随 FrameMetadata 可选字段 `frame_id` 下发;检测端 `ownship_mask_step2` 优先读
元数据,像素条解码降级为 FramePublisher 直连/离线回放路径的后备。§4 对齐键
语义不变,载体从像素升级为元数据。

## 9. 修订(2026-10-20 晚):空扫描重扫 + 读回晚到等待(泄漏二轮根因)

修元数据链后仍泄漏:检测端 `--ownship-diag-dir` 分类实测 none 帧 88%=缓存
**命中但掩膜全零**,线上订阅 :5558 解码证实逐帧 360 行×单 640 零游程。根因
在发布器 `RefreshShip`:`GetComponentsInChildren<Renderer>(false)` 扫描落在
本船层级装配/激活窗口时拿空表,而空表在该方法内**永不重扫** → CommandBuffer
只剩 clear+readback(照常执行)→ 全零掩膜合法发布、本船裸奔检出。同二进制
逐次启动随机(player A 扫描时已激活=正常,player B 撞窗口=全零),与"上时段
masked=2623、本时段全零"逐进程分野吻合。修复:空扫描(或 ship 非 null 而
零渲染器)置空 `m_Ship` 下帧重扫;30s 日志加 `renderers=N` 供线上判读。
次要根因 race≈12%(AsyncGPUReadback 晚于图像分流到达):检测端精确匹配未
命中时 `wait_for_mask` 自旋排空 ≤30ms 把竞态转命中。线协议/RLE 格式不变。

## 10. 修订(2026-10-20 深夜):marker 行级鲁棒解码 + 读回竞态智能等待(empty 89% 三期根因)

二轮修复后稳态健康(命中 83%、renderers=24),但快速变视角时 `none_causes
{empty:632, stamp:36, race:14}`——泄漏帧像素实锤本船白色上层建筑在画而掩膜全零。
定位(泄漏帧 marker 条像素级分析):**Unity 侧同帧一致无失配**(CameraRig 位姿
写入 LateUpdate order 125 → marker 更新 10000 → 掩膜渲染 10001 → 相机渲染,
全程同一姿态);失配发生在检测分流侧,两处:

1. **empty(主因)**:快速转视角时 TAA 幽影/亮部泛光**逐行污染** marker 条带
   (泄漏帧实测:列内 16 行自上而下白→黑渐变,格心落歧义窗),sender 单行
   (固定第 8 行)解码失败 → `_tap_frame_id_for` ±40ms 近邻兜底把**邻帧 id**
   盖上本帧 → 检测端按邻帧姿态的掩膜匹配 → 本船已出画=全零=合法发布却泄漏。
   修复:sender `_decode_marker_pad` 对条内 6 行(3/5/7/9/11/13)逐行独立解码,
   魔数+校验和通过的行投票取多数——行级污染免疫;30s 账本加
   `rows_recovered/all_rows_failed` 供线上判读。
2. **race(次因)**:tap 支路在缩放/JPEG 前分流,链路延迟≈0,视频帧**跑赢**
   掩膜 AsyncGPUReadback 1-2 个渲染帧(实锤 `want=19097 cache max=19095`);
   旧 30ms 等待预算 < 1 帧周期 33ms 盖不住。修复:检测端 `wait_for_mask` 预算
   30→120ms,且只对模 u16 距环内最新 ≤64 id(还在路上)的想要值等待,滑出
   环底/离群旧 id 立即 miss 不空等(`OwnshipMaskCache.newest_id`)。

线协议/RLE 格式不变;±40ms 近邻兜底保留(全行污染时的最后恢复手段)。
回归:gst-base 容器 sender 单测 8/8(行拖影救回/对抗单行票选/全行 fail-closed),
pytest mask 44/44。Unity 侧零改动,player 无需重建。

### 10.1 追记(2026-10-21 上午):泛光均匀抬升→行内自适应阈值

三期部署后用户实测甩动仍泄漏,泄漏帧 marker 条逐行实锤:本船白色上层建筑
**泛光把黑格从 ~20 均匀抬到 49-177**(多格落 80-175 歧义窗,白格稳定
185-203)→ §10 的多行采样对"整条均匀抬升"无效(all_rows_failed 占发送
23%,rows_recovered 仅 10)→ 近邻兜底继续错盖邻帧 id。修复:`_decode_marker_row`
改**行内自适应阈值**——32 格取 (min+max)/2 分界按相对序分类,泛光不改
变黑白相对序即免疫;条带对比 <60(被淹没/无 marker)或位串未过魔数+校验
和仍 fail-closed。容器单测 9/9(新增均匀泛光用例黑 150/白 210)。另:部署
侧回归教训=手动拉 sender 必须带 `TWIN_GST_DETECT_TAP=1`(tap 默认关,漏带
=检测链整条断粮而掩膜侧无感)。
