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
Two paired columns: left measured and simulated vessel trajectory overlay with parameter gear; right captain console and event timeline. Across bottom two clearly separated cards for independent validation and update principle. Delicate diagram arrows. No claim that behavior cloning identifies intent automatically; no neural net or RL depicted as required first step.
Layout: two-columns

ON-IMAGE TEXT — EXACT COPY
Main title: 【模型校准与船长行为分析】
Subtitle: 物理响应和决策意图分别建立证据

Group 1:
模型校准
时钟与坐标 → 执行器 → 船体 → 环境残差

Group 2:
船长行为
何时避让、怎样操纵、何时恢复

Group 3:
独立验证
按航次留出数据，检查多步预测

Group 4:
更新原则
通过回归后更新模型，意图依靠复盘标注

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
先灰箱校准，再根据残差考虑SINDy/学习方法。按独立航次切分，避免相邻采样随机打散泄漏。船长轨迹只支持行为推断，不能独自证明意图/最优性。更新离线候选，非自动更新船载控制器。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md
