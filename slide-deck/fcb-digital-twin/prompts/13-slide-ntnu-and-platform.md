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
Three-layer cutaway technical illustration of vessel model, virtual sensor rays, software modules across upper two-thirds, with four clean callout text regions. Lower-right small toolbox/plug connectors indicating replaceable backends. No university logo, no Google Gemini imagery, no unsupported mature-production checkmark. Keep named text exact and no extra product labels.
Layout: bento-grid

ON-IMAGE TEXT — EXACT COPY
Main title: 【NTNU经验与平台选择】
Subtitle: 借鉴分层与验证方法，保留后端替换能力

Group 1:
NTNU架构
海事模型 + 三维传感器 + 自治软件

Group 2:
研究边界
仿真同步不等于实船验证

Group 3:
本项目选择
Colav编排 · ROS2集成 · 可替换三维后端

Group 4:
先做构建验证
Gemini已归档，ROS2适配需补齐

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
来源：Autoferry Gemini (2020), Hanssen game thesis (2022), milliAmpere2 design/testing (2025), Berg syncing (2025), Menges predictive/RL (2024), Kandemir SINDy (2025)。Gemini公开适配器ROS1、主仓库归档；PyGemini仅列研究候选，不承诺安装成熟度。SINDy有小型Otter数据但不直接迁移FCB参数。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ntnu-gemini-evidence.md
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-twin-sync-identification-evidence.md
https://github.com/Gemini-team/Gemini
https://github.com/Gemini-team/ros_adapter
https://doi.org/10.1038/s41598-025-93635-9
https://doi.org/10.1016/j.apor.2025.104825
