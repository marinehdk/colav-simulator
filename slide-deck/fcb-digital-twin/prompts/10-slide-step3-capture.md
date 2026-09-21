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
Central illustrated FCB with three instrument callout groups for navigation/environment, actuator console, radar/GNSS/target fusion. All feed a prominent lower archive/data-package block. Show dual separate traces from commanded rudder and measured rudder but no invented chart values. Recording equipment not assumed physically installed. All supplied Chinese text exact.
Layout: hub-spoke

ON-IMAGE TEXT — EXACT COPY
Main title: 【第三步：采集可校模的数据】
Subtitle: 同时记录命令、反馈、状态与当时态势

Group 1:
本船与环境
位置、航向、速度、IMU、风流与装载

Group 2:
命令与执行
舵桨指令、实际反馈、模式与接管

Group 3:
L1与周围交通
原始传感器、融合航迹、时间与质量

Group 4:
数据包
MCAP + 原始文件 + 参数版本 + 校验清单

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
原生频率与丢帧统计，保留设备时间和接收时间。海流/波浪未测时标注未测而非伪造真值。MCAP和原始视频/雷达旁路文件共用manifest和时钟映射。设备库存仍需团队确认。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md
