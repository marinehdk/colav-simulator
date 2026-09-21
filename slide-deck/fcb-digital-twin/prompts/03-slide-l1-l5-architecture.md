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
Make an unambiguous architecture diagram. A wide prominent teal L1 bar in upper-middle with subtitle inside. BELOW it four boxes left to right: L2 规划, L3 避碰, L4 导引, L5 控制. Four separate thin teal downward arrows from L1 bar to EACH of four boxes (not just L2). Dark horizontal arrows connect L2 to L3 to L4 to L5 for plan/reference flow; label this row 计划与指令. Lower-right box 执行器与船舶 receives command arrow from L5. A return arrow from physical box goes around right edge back to L1, labeled 传感器反馈. L1 is not a mission-planning node. Keep all arrowheads clear and avoid crossing labels.
Layout: hierarchical-layers

ON-IMAGE TEXT — EXACT COPY
Main title: 【L1提供共享态势】
Subtitle: 规划、避碰、导引、控制共用同一态势来源

Group 1:
L1 传感器与态势融合
本船状态 · 目标航迹 · 环境估计

Group 2:
L2 规划
L3 避碰
L4 导引
L5 控制

Group 3:
计划与指令
执行器与船舶
传感器反馈

Render headings clearly; use generous card padding and clean consistent alignment. No missing words, invented abbreviations, duplicated labels, or illegible microtext. Text carries content; drawings support it.

NOT FOR ON-IMAGE RENDERING — SPEAKER NOTES AND SOURCES
用户定义优先：L1=传感器与态势感知融合。图为逻辑合同；正式实现仍需航线/控制权仲裁及接口适配。L1输出含质量/时间戳，态势不等于仿真真值。
/Users/marine/Code/Colav-Simulator/docs/research/2026-09-17-fcb-digital-twin-three-stage-architecture.md
User clarification: L1 sensors and situational awareness fusion, shared source for other layers
