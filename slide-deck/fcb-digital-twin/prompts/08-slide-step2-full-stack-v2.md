IMAGE EDIT TASK. Preserve the reference slide except the precise correction below.

Use case: productivity-visual
Asset type: One finished presentation slide image, raster, landscape 16:9, ideally 1920x1080 or 2048x1152.
Generate exactly ONE slide, not a montage of multiple slides. All on-image words must be Simplified Chinese or supplied technical names. Preserve all source spelling. Do not show filenames, slide numbers, source URLs, speaker notes, or prompt metadata. No image overlays will be used: render correct text directly.

<STYLE_INSTRUCTIONS>
Design Aesthetic: sango-ai Chinese engineering briefing. Precise 2D technical illustration with restrained hand-inked outlines, subtle cream paper, generous structure. This is a polished readable presentation, not a notebook doodle.
Background: flat aged cream #F5F0E6, extremely faint paper grain. No stains, no curled edges.
Typography: large bold dark maroon #5D3A3A Simplified Chinese headings in corner brackets; body clean geometric Chinese sans-serif #1A1A1A. Crisp correct Chinese glyphs, clear technical abbreviations. Title about 56px and body at least 28px on a 1920x1080 canvas.
Palette: teal #2F7373 for simulation, warm brown #8B7355 for physical vessel, maroon #722F37 for emphasis, charcoal #2D2D2D outlines. Off-white cards. Muted blue-gray for ROS2.
Visual Elements: original technical drawings of a 45m fast crew boat, harbor coastline, sensors, sparse wave contours, clear arrows and tidy cards. Boat is illustrative, not as-built geometry. Readable engineering schematics, not photorealism or glossy 3D.
Density: 3-4 grouped content areas per slide, balanced negative space, 6% safe margins, avoid tiny annotations. Diagram labels may appear inside grouped areas.
Rules: one clear message per slide; exact Chinese copy supplied below, no invented text. No page numbers, footer, logo, watermark, source URLs, fake charts, invented metrics, decorative pseudo-code, gradients or luminous sci-fi effects. No mission layer called L1: L1 always means sensors and situational awareness fusion. Never suggest vessel validation is already complete.
</STYLE_INSTRUCTIONS>

COMPOSITION
Two large lanes: upper blue-gray enclosure 真实ROS2软件 with L1 bar feeding each of L2-L5, horizontal plan chain. Lower teal/brown enclosure 数字船与环境 with boat, actuator, waves. Between them one conspicuous 仿真设备边界 with separate up sensor arrow and down actuator-command arrow. A right-side callout lists validation target. Clearly the actual software runs, model replaces devices. No third uncontrolled autopilot.
Layout: two-columns

ON-IMAGE TEXT — EXACT COPY
Main title: 【第二步：真实ROS2全栈联调】
Subtitle: L1–L5运行目标软件，数字船替代实船设备

Group 1:
真实ROS2软件
L1 态势融合
L2 规划 → L3 避碰 → L4 导引 → L5 控制

Group 2:
仿真设备边界
传感器数据 ↔ 执行器命令与反馈

Group 3:
数字船与环境
FCB船模 · 舵桨模型 · 风浪流

Group 4:
验证目标
接口协作 · 模式切换 · 故障响应

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
使用生产包/commit和真实DDS执行。既有嵌入式C++核心通过不等于ROS2全栈通过。L1融合也必须作为生产节点参与此阶段。逐模块换入，替身不能计入最终全链路验收。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ros2-twin-platform-evidence.md


MANDATORY CORRECTION (highest priority for this edit):
CRITICAL ARCHITECTURE EDIT: Rebuild ONLY the inside of the upper 真实ROS2软件 enclosure. Put a wide horizontal bar L1 传感器与态势融合 above a row of FOUR boxes L2 规划, L3 避碰, L4 导引, L5 控制. Draw FOUR DISTINCT downward arrows from L1 to EACH of L2,L3,L4,L5. Connect only the FOUR lower boxes left-to-right with plan arrows. L1 is NOT the first item in a serial five-box chain. The lower sensor-up arrow must connect to L1 bar, routed along left edge. On right, separate downward 执行器命令 arrow and upward 实际反馈 arrow, from/to L5 and digital boat. Keep the main title/subtitle, right validation cards and lower boat/environment illustration. Enlarge upper enclosure vertically if required, using spare lower sea area, maintain readability.
