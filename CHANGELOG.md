# Changelog

## v0.5.0
**Import**
- .concept-files are automatically converted on import (no converter script needed anymore)

**UI/UX**
- Collapsable top bar
- consistent section cards (light & dark).
- FILES panel cleaned: **Advanced** mode for loading 'JSON/Images'.
- Added**Log** (collapsible).
- **Dark Mode + White lines** grouped together (Can be toggled).

**Shortcuts**  
- Keyboard shortcuts (all noted in the info-modal)

**Export**
- **PNG export @1×/2×/4×** using offscreen canvas.
- Auto filenames include version/zoom/dark/white.
- **SVG export** works again, see **Known Gaps**

**ZIP download**
- ZIP name & contents based on input filename: `name.zip` includes `name.json` and `name_thumb.jpg` (generated if missing).

**Persistence**
- Remembers Collapse, Advanced, Log open, Dark, White lines, Images opacity.
- **Reset UI** (localStorage) in Info panel.

**Known Gaps**
- SVG export is still experimental, maybe needs horiz./vert. mirroring
- SVG stroke-linecaps are not rounded
- Lava Flow Tag Soup but stable

## v0.4.18.alpha
- First working release with an integrated *.concept to *json converter.
- Converting is performed within file, no external py-script
- Also works with embedded image files.
- Download option for converted *.json-file + embedded imgs to *.zip-file.

## v0.4.7
- First stable version
- import of converted json file
- image loading with accurat positioning behind drawing
- various flip/mirror options for global drawing, all images, selected iamges
- opacity slider for images
- dark mode with option for displaying all strokes/lines in white color
- Stable zoom
- multi-layer support, just displays all on canvas
- good working rendering for fixed-width strokes (pencil) and basic marker/airbrush
- robust longest-segment (MaxJump) segmentation for noisy paths
- export view to PNG and SVG
- Known gaps: Auto-Shapes (rect/ellipse/polygon), Shape tool, textured/pattern brushes, full brush dynamics