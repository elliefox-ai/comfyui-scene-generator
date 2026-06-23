# Scene Generator for ComfyUI (Ideogram)

A ComfyUI custom node that generates structured multi-character scene prompts with spatial layout control. Designed for [Ideogram](https://ideogram.ai) but works with any image model that respects bounding box control nets.

## How It Works

Two independent systems that combine into a single prompt:

- **Scene Type** (composition) — Controls *how* figures are arranged: scale hierarchy, arrangement pattern, and density. Think camera/composition language: `face_off`, `close_group`, `wide_vista`, etc.
- **Scenario** (content) — Controls *what's* in the scene: setting, characters, actions, backgrounds. Genre-flavored content packs: fantasy, western, sci-fi, noir, etc.

Any scene type pairs with any scenario. `face_off` + `pirate_ship` gives you a standoff on the deck. `atmospheric` + `noir_city` gives you a moody detective scene.

## Features

- **3-knob composition system**: scale hierarchy (equal/dominant/environmental), arrangement (opposing/clustered/scattered/offset), density (sparse/balanced/dense)
- **Shot-width-aware backgrounds**: Each background is tagged close/medium/wide and selected to match the composition
- **Camera framing**: eye_level, high_angle, low_angle, dutch — injected at 3 layers (HLD, background, per-character) with corresponding bbox height scaling
- **Scenario packs**: 6 included (fantasy, medieval_tavern, noir_city, pirate_ship, sci_fi, western), each with 9-10 backgrounds, 12 subjects, 12 actions
- **`{setting}` coherence**: Backgrounds always reference the picked setting, guaranteeing thematic consistency
- **🎲 Random options**: Random scene type, scenario, and framing for discovery

## Installation

Drop the `scene-gen/` folder into your ComfyUI `custom_nodes/` directory and restart ComfyUI.

## Requirements

- ComfyUI
- Ideogram model (or any model that supports bbox control nets)

## License

MIT
