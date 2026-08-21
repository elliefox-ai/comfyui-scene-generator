# ComfyUI Scene Generator (Ideogram 4)

A structured multi-character scene prompt generator with spatial layout control, for [ComfyUI](https://github.com/comfyanonymous/ComfyUI). Built by [Ellie](https://github.com/elliefox-ai) 🦊 and Alexander Dutton.

> **Related packs:** the visual editing nodes that used to live here moved to their own homes — [comfyui-elliefoxai-canvas](https://github.com/elliefox-ai/comfyui-elliefoxai-canvas) (Outpaint Controller, Inpaint Painter) and [comfyui-elliefoxai-diagnostics](https://github.com/elliefox-ai/comfyui-elliefoxai-diagnostics) (PromptPeek, VAE Round-Trip, Latent Boundary Analyzer).

## The Node

### 🧭 Scene Context Picker

Upstream companion to the Scene Generator: procedurally resolves a narrative context — setting (genre-filtered, with optional two-genre mashups), situation, tone, and an atmosphere flourish — and emits it as structured text plus a `scene_type` suggestion. Wire `context_text` → Scene Generator's `theme`, `scene_type_suggestion` → `scene_type`, and let one seed drive both nodes.

Co-designed with Claude (Anthropic). See [CO-AUTHORS.md](CO-AUTHORS.md) for the full story.

### 🗳️ Scene Generator (Ideogram 4)

Procedurally generates structured multi-character scene prompts from parameterized templates, with a live bbox layout preview on the node canvas.

**Features:**
- **Two-axis design:** Scene Type (composition: *how*) × Scenario (content: *what*)
- **3-knob layout engine:** scale hierarchy, arrangement pattern, density
- **Shot-width-aware backgrounds** that match the composition
- **Camera framing:** eye_level, high_angle, low_angle, dutch
- **6 scenario packs:** fantasy, medieval_tavern, noir_city, pirate_ship, sci_fi, western
- **`{setting}` coherence:** backgrounds always reference the chosen setting
- **Live bbox preview** — renders the layout on the node canvas as you change parameters, no execution needed
- **🎲 random option** on every filter — the seed decides

Designed for [Ideogram](https://ideogram.ai)'s structured prompts, but the JSON it emits (subjects with bounding boxes + scene text) works with any model or workflow that accepts spatial hints.

## Installation

1. Clone or download this repo into your ComfyUI `custom_nodes/` directory:
   ```
   cd ComfyUI/custom_nodes/
   git clone https://github.com/elliefox-ai/comfyui-scene-generator.git ComfyUI-EllieFoxAI-scene-gen
   ```
2. Restart ComfyUI
3. Look for **🗳️ Scene Generator (Ideogram 4)** in the node menu (under `SceneGen`)

No additional Python dependencies beyond what ComfyUI already provides.

## Development

`test_layout.py` exercises the layout engine standalone (no ComfyUI required):
```
python3 test_layout.py
```

## License

MIT

## Credits

Built by **Ellie** (AI agent) and **Alexander Dutton** (human partner) through [OpenClaw](https://github.com/openclaw/openclaw). See [CO-AUTHORS.md](CO-AUTHORS.md) for the full collaboration story — wrong turns and all.
