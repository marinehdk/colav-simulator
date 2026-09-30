# Sango M9 Handoff — 第一阶段收官(20260930 会话H 终版)

**用途**:下一会话接续。**首读物 = 持久记忆 sango-phase1-prototype-workflow-20260922.md**(含 M8 全程+坑账本,本档只补执行入口)。

## 状态一页纸

- **第一阶段(M4-M8)收官**:代码链终态 `10def041`(本地 main 未 push,remote=marine)。EditMode **337/337**。
- **主 demo**:`open sango/Builds/sango.app`——海峡场景全内容(29 tile+岸桥天际线+锚地+绿脊+IALA 浮标+渡轮拖轮+大气三档 N 键+夜航号灯 T 键+五机位 C 键+自航 G)+ **M8 双档(L 键)+HUD 隐藏(H 键)**。fps 60 vsync 上限。
- **M8-C 三票制两轮 FAIL(运动 2/尺度 3/光照 2)如实入档**:渲染/管线/工艺链客观门禁全过(337 测试、fps 60×两档、出片 10809/10809 帧 @Constant60、probe 30/30),观感保真度差距集中在尾迹系统与夜景光照=M9 polish,已按协议转 backlog。
- **出片产物**:docs/research/2026-09-29-m8c-review-materials/ 九段 mp4(round2 终版)+round1/ 存档+两轮聚合表+fps 表。

## a4000 出片机(全通,复跑配方)

```bash
# Unity: ~/unity-install/6000.3.24f1 (tarball 解包)  Hub: ~/unity-install/hub (dpkg -x)  工程: ~/unity-project/sango
# license 已激活(RDP+Hub Google OAuth);重跑出片:
ssh a4000 'nohup ~/unity-project/run-shots.sh > ~/unity-project/run-shots.out 2>&1 &'
# 脚本内含: DISPLAY=:0 XAUTHORITY=/tmp/gdm-auth + Unity -batchmode -force-vulkan -executeMethod Sango.Editor.M8RecordingRunner.RunFromCli
# 产物: ~/unity-project/sango/tmp/m8-frames/<段>/<段>_NNNN.jpg → rsync 拉回 → ffmpeg 转码
```
- **两个铁律**:`-force-vulkan` 必须显式(缺省 OpenGLCore→HDRP 拒渲染→全黑帧,帧同字节数=纯色特征);X 必须用 GDM :0(docker 组读 auth),Xvfb/xrdp-X 均无 GPU DRI。
- license 死路账本(勿重试):alf→ulf(拒 Personal)/--update-license CLI(静默无 entitlement)/ulf 拷贝(机器绑定)/Hub headless CLI(无 license 命令)/X11 转发键盘(全坏)/conversation 跨设备信号(不回传)。

## M9 候选 backlog(人闸裁决优先级)

1. **尾迹/艏波系统升级**(decal 贴花→粒子+网格,泡沫水线/桨流)——三票公认压分主力
2. **夜景光照链**(夜空亮度/号灯 sprite 圆形化+光晕/水面灯光反射)
3. 船-水交界(吃水硬边/双艏绿楔/悬空感)
4. a4000 渲染侧(艏波贴片平板化/夜段透明排序/天气切换平滑)
5. 资产项(hero 拖锚/甲板质感/地平线白带)

其余入口:后端真握手(契约冻结,probe 30/30);M8 review 未决小项=M8RecordingRunner 超长雨丝粒子生命周期(评审 C 点名)。

## 坑速查(全量在记忆)

- Unity batch 单实例;pgrep/pkill 自匹配([u] 技巧);Electron 强杀留 SingletonLock;门禁锚数据契约勿锚自创布局(M8-B glob 假阴性);Read 视频 30MB 上限(大文件 ffmpeg 代理);评审抽帧密度致分歧(速度日志反证)。
- 热键账本:0-9/T/F/G/C/B/A/P/Q/E/Z/X/Space/R/±,./Enter/V/N(大气)/L(画质)/H(HUD)。
