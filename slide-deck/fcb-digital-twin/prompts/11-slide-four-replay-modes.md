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
2x2 matrix of four equal illustrated cards: recorded solid trajectory; measured vs predicted trajectories; fixed sensor data feeding alternative decision blocks; branching vessel tracks with a new sensor viewpoint. Subtle consistent linework. First card brown factual, last teal hypothetical, middle complementary. Question text large and correct, one question per card. No invented performance comparison.
Layout: comparison-matrix

ON-IMAGE TEXT — EXACT COPY
Main title: 【四种回放，四种问题】
Subtitle: 分清历史事实、模型预测与策略假设

Group 1:
历史重现
船长当时怎样开船？

Group 2:
模型验证
同样舵桨输入，船模响应是否一致？

Group 3:
决策回放
同样观测，新算法会提出什么动作？

Group 4:
反事实闭环
执行新动作后，仿真结果会怎样？

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
反事实船位改变后，旧相机/雷达画面不能作为新位姿反馈；需重新生成观测或限定目标级近似。历史目标不响应是假设，不能宣称真实交互。seek需重置/快照与预热，不是播放器移动位置即可。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md
