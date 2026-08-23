# Scene Context Pack (ComfyUI)

A procedural narrative-context generator: venue, situation, tone, atmosphere, composition — and one node per character with identity-aware features and wardrobe. Built by [Ellie](https://github.com/elliefox-ai) 🦊 and Alexander Dutton.

> **Related packs:** the visual editing nodes that used to live here moved to their own homes — [comfyui-elliefoxai-canvas](https://github.com/elliefox-ai/comfyui-elliefoxai-canvas) (Outpaint Controller, Inpaint Painter) and [comfyui-elliefoxai-diagnostics](https://github.com/elliefox-ai/comfyui-elliefoxai-diagnostics) (PromptPeek, VAE Round-Trip, Latent Boundary Analyzer).
>
> **Retired:** the original Ideogram-era SceneGenerator (bbox layout engine, debug-card renderer, scenario packs) lives in `attic/` — git history preserved, comeback possible.

## The Nodes

### 🎼 Scene Context Composer

**v2 — the clean-room node.** Everything the four-axis cascade learned, with no legacy surface: Genre (+optional union mashup) → two-tier Setting (archetype gates venues by facet tags; explicit venue = author override) → Situation — selected by the **double filter**: Setting and Tone *jointly* narrow the pool — env-tagged, atmosphere respects it, and **Composition as a first-class axis** (framing phrases keyed by the situation's `scene_type_bias`, allow-listed with a generic fallback pool).

Tone is a selection axis, not seasoning: `tones.json` declares which situation capability tags (`violent_capable`, `calm_capable`, …) each register can carry; an absent `compatible` list means the register is open and sits on any situation (satirical, by design). A tone that matches nothing at a venue falls back to the full situation list — flavor yields to structure, same rule as genre.

**Authoring rule of thumb:** situation text describes *action and posture*, never characters or props — specifics belong to tone modifiers and composition phrases, so contexts blend across seeds instead of pinning one image.

Renderer-agnostic by construction: `render_prompt` (context + framing) feeds any text-conditioned model, `components_json` exposes every piece separately for remixing, and `seed_used` wires straight into a sampler. Data lives in `scene_context/`, shared with the Picker — single source of truth.

### 🧭 Scene Context Picker

Upstream companion: resolves setting (genre-filtered, with optional two-genre mashups), situation, tone, and an atmosphere flourish, and emits structured text plus a `scene_type` suggestion. Wire `context_text` into any text-conditioned renderer, or use the Composer for the full cascade.

### 🎲 Scene Character Roller

One node, one character. Decides *who one person is*: role concept + wardrobe family + face anchors, assembled compositionally from tagged banks. Identity (age / sex / race) is stated once in the identity phrase and every feature draw is soft-weighted toward it — affinity, never a filter. Add a node per figure; wire into a Picker/Composer character slot or any text prompt.

Co-designed with Claude (Anthropic). See [CO-AUTHORS.md](CO-AUTHORS.md) for the full story.

## The tag law

`scene_context/tags.json` is the registry: every genre / facet / situation / identity tag in the data is validated against it at ComfyUI startup, and the genre dropdowns derive from it. An unknown tag is a hard startup failure naming the venue. `python3 analyze_bank_balance.py --lint` checks coverage (venues per genre, facet uses, wardrobe families, enum parity).

## Installation

1. Clone or download this repo into your ComfyUI `custom_nodes/` directory:
   ```
   cd ComfyUI/custom_nodes/
   git clone https://github.com/elliefox-ai/comfyui-scene-generator.git ComfyUI-EllieFoxAI-scene-gen
   ```
2. Restart ComfyUI
3. Look for the nodes under `SceneGen` in the node menu

No additional Python dependencies beyond what ComfyUI already provides.

## Development

Headless harnesses — no ComfyUI required:

```
python3 test_context.py          # Picker cascade
python3 test_composer.py         # Composer cascade
python3 test_character_roller.py # Character Roller
python3 test_scene_tags.py       # tag registry validation
python3 analyze_bank_balance.py --lint   # coverage law
```

## License
