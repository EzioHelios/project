# SCADA 设备图标生成记录

生成日期：2026-08-12
生成方式：Codex built-in ImageGen
最终资产：`src/js/web/src/assets/microgrid/scada-equipment-atlas-v1.webp`

## Final prompt

```text
Use case: stylized-concept
Asset type: SCADA microgrid equipment icon atlas for a production industrial web application
Primary request: create one coherent atlas of exactly six polished equipment icons arranged in a strict 3 columns by 2 rows grid. Row 1 left-to-right: electrical utility grid connection represented by a compact substation/power pylon; rooftop photovoltaic array; battery energy storage cabinet. Row 2 left-to-right: EV charging group; warehouse industrial lighting; warehouse operations building/load.
Style/medium: premium semi-flat isometric industrial technology illustration, crisp technical geometry, restrained depth, consistent dark graphite outline, subtle brushed metal panels, small low-saturation teal/cyan energy accents, no glow, no cyberpunk, no cartoon softness.
Composition/framing: exactly one centered object per equal cell, identical visual scale, generous equal padding, no overlap between cells, no separator lines, front three-quarter isometric view.
Color palette: cool graphite, slate, steel gray, off-white, low-saturation teal and cyan accents. Do not use magenta anywhere in any icon.
Scene/backdrop: perfectly flat solid #ff00ff chroma-key background across the entire image, uniform edge to edge, no shadows on background, no gradients, no texture, no floor plane.
Constraints: no text, no letters, no numbers, no logos, no watermarks; exactly six icons; recognizable at 64 pixels; consistent lighting from upper-left; crisp silhouettes; each icon fully inside its own grid cell.
Avoid: green environmental poster aesthetic, neon glow, excessive detail, photorealism, labels, borders, frames, people, vehicles, cables leaving cell boundaries.
```

生成后使用品红色键控去背景，再转换为带 Alpha 通道的 WebP 图集。前端以单一精灵图资源请求分区展示六类设备。
