IMAGE EDIT: fix incorrect architecture labels only.
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
A practical 2x2 workboard with four large cards; each has the exact title plus proposed responsible role/detail. Small line icons for interface contract, hull parameter binder, scene connector, recorder. Cards numbered nowhere. No calendar dates or duration promises. Precise readable text is central, minimal decoration.
Layout: bento-grid

ON-IMAGE TEXT — EXACT COPY
Main title: 【近期可立即启动的四项工作】
Subtitle: 先明确接口与数据，再完成最小联调

Group 1:
统一L1–L5接口
各层负责人：字段、单位、频率与控制权

Group 2:
核对FCB参数
船模负责人：参数来源、缺口与适用范围

Group 3:
验证三维连接
仿真负责人：外部位姿、时钟与重置

Group 4:
演练海试记录
采集团队：信号清单、同步与离线回放

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
角色为建议分工，非已获团队承诺。每项产物：接口字典v1；参数台账；构建/外部位姿驱动记录；可离线回放的数据演练包。现在就可启动，先确认同事包版本和设备数据可获得性。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-ros2-twin-platform-evidence.md


MANDATORY CORRECTION:
EDIT ONLY the five colored label rows in upper-left 统一L1–L5接口 card. Replace their text EXACTLY as follows, one row each, top to bottom:
L1 传感器与态势融合
L2 规划
L3 避碰
L4 导引
L5 控制
The existing labels 感知与环境理解, 决策与任务规划, 控制与执行, 平台与运维 are WRONG and must be removed. Do not expand the corrected short labels. Preserve title, all other text, diagrams and three other cards. No other changes.
