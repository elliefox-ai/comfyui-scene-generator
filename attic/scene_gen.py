"""
Scene Generator node for ComfyUI — procedurally generates Ideogram 4 JSON prompts
from parameterized templates, with a PIL-rendered bbox layout preview.

Two layers drive composition:
  1. Templates (creative): mood, subject descriptions, actions, backgrounds, style, props
  2. Layout engine (spatial): subject bounding boxes + natural language spatial descriptions

Three compositional knobs control the layout engine:
  - scale_hierarchy: equal | dominant | environmental
  - arrangement:     opposing | clustered | offset | scattered
  - density:         sparse | balanced | dense

Scene types (face_off, close_group, hero_journey, etc.) are composition presets
that set all three knobs. They describe HOW figures are arranged in frame,
not WHAT the scene is about — that comes from the scenario pack.
Any knob can be overridden individually.

Each filter can be locked or set to 🎲 random. The seed cascades through all
unlocked layers.
"""

import json
import os
import random

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from server import PromptServer
from aiohttp import web

try:
    from .layout_engine import compute_layout, resolve_knobs, SCENE_PRESETS, _FRAMING_TEXT
except ImportError:
    from layout_engine import compute_layout, resolve_knobs, SCENE_PRESETS, _FRAMING_TEXT


# ── Paths ─────────────────────────────────────────────────────────

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")
STYLE_PRESETS_PATH = os.path.join(os.path.dirname(__file__), "style_presets.json")
_FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "FreeMono.ttf")
_COMFY_FONT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "fonts", "FreeMono.ttf"
)

# Sentinels for "let the seed decide"
RANDOM_SCENE = "🎲 random"
RANDOM_SHOT = "🎲 random"
RANDOM_SUBJECTS = -1

# Compositional knob options
AUTO = "auto"  # Inherit from scene_type preset
SCALE_OPTIONS = [AUTO, "equal", "dominant", "environmental", "🎲 random"]
ARR_OPTIONS = [AUTO, "opposing", "clustered", "offset", "scattered", "🎲 random"]
DENSITY_OPTIONS = [AUTO, "sparse", "balanced", "dense", "🎲 random"]
FRAMING_OPTIONS = ["eye_level", "high_angle", "low_angle", "dutch", "🎲 random"]

# Style mode options
STYLE_FROM_TEMPLATE = "template"
STYLE_OPTIONS = [STYLE_FROM_TEMPLATE, "🎲 random", "cinematic", "photoreal", "hyperreal_3d", "painterly", "anime", "concept_art", "minimal", "cel_shaded", "claymation", "watercolor", "low_poly", "noir", "storybook"]

# Lighting mode options
LIGHTING_FROM_TEMPLATE = "template"
LIGHTING_OPTIONS = [
    LIGHTING_FROM_TEMPLATE,
    "🎲 random",
    "hard_directional",
    "soft_diffused",
    "split_warm_cool",
    "backlit_rim",
    "overhead_practical",
    "golden_hour",
    "overcast_flat",
    "volumetric_god_rays",
    "cel_shaded",
    "flat_even",
]

# Palette mode options
PALETTE_MODE_OPTIONS = [
    "auto",
    "🎲 random",
    "brighter",
    "darker",
    "saturated",
    "desaturated",
    "grayscale",
]

# Scenario options
SCENARIO_NONE = "none"
SCENARIO_RANDOM = "🎲 random"


def _adjust_palette(palette, mode, rng):
    """Adjust a hex color palette based on the palette mode."""
    if mode in ("auto", "🎲 random") or not palette:
        return palette
    
    def clamp(v):
        return max(0, min(255, int(v)))
    
    def hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    def rgb_to_hex(rgb):
        return '#' + ''.join(f'{clamp(c):02x}' for c in rgb)
    
    adjusted = []
    for color in palette:
        r, g, b = hex_to_rgb(color)
        if mode == "brighter":
            lift = rng.randint(30, 60)
            r, g, b = r + lift, g + lift, b + lift
        elif mode == "darker":
            cut = rng.randint(30, 60)
            r, g, b = r - cut, g - cut, b - cut
        elif mode == "saturated":
            avg = (r + g + b) / 3
            factor = 1.4
            r = avg + (r - avg) * factor
            g = avg + (g - avg) * factor
            b = avg + (b - avg) * factor
        elif mode == "desaturated":
            avg = (r + g + b) / 3
            factor = 0.4
            r = avg + (r - avg) * factor
            g = avg + (g - avg) * factor
            b = avg + (b - avg) * factor
        elif mode == "grayscale":
            avg = int((r + g + b) / 3)
            r, g, b = avg, avg, avg
        adjusted.append(rgb_to_hex((r, g, b)))
    
    return adjusted

# Lighting presets: named lighting descriptions for override mode
LIGHTING_PRESETS = {
    "hard_directional": [
        "Hard directional light with deep shadows. Strong key light from one side.",
        "Harsh raking light across surfaces, carving texture and form.",
        "Single-source hard light, dramatic shadow falloff, high contrast."
    ],
    "soft_diffused": [
        "Soft diffused light filling the frame evenly. Gentle shadow falloff.",
        "Diffused softbox light wrapping subjects smoothly. Minimal harsh shadows.",
        "Ambient soft light, gradient transitions, low contrast."
    ],
    "split_warm_cool": [
        "Split lighting \u2014 warm key on one side, cool fill on the other.",
        "Bicolour lighting: amber from camera left, blue-cyan from camera right.",
        "Complementary split light \u2014 orange and teal balancing across the frame."
    ],
    "backlit_rim": [
        "Backlit, figures rimmed with light against darker backgrounds.",
        "Strong backlight creating silhouette edges and halo rim light.",
        "Rim lighting from behind, separating subjects from background with bright edges."
    ],
    "overhead_practical": [
        "Overhead practical light source \u2014 lamp, fire, or skylight \u2014 carving subjects from above.",
        "Single hanging light above, pooling illumination in a circle around subjects.",
        "Top-down practical lighting \u2014 motivated by a visible or implied fixture overhead."
    ],
    "golden_hour": [
        "Golden hour \u2014 low warm sun, long shadows stretching behind subjects.",
        "Warm sunset light raking across the scene, amber highlights and soft purple shadows.",
        "Magic-hour backlight, sun low on the horizon, lens flares and warm haze."
    ],
    "overcast_flat": [
        "Overcast \u2014 soft, flat, true color rendering.",
        "Cloudy-day diffuse light, even illumination, no harsh shadows.",
        "Grey-skies ambient light, muted contrast, naturalistic color."
    ],
    "volumetric_god_rays": [
        "Atmospheric lighting with god rays or volumetric light shafts piercing the scene.",
        "Visible light beams cutting through atmosphere \u2014 dust, fog, or smoke enhancing volume.",
        "Shafts of light through canopy or architecture, scattering through particulate in the air."
    ],
    "cel_shaded": [
        "Hard-edged shadow shapes with a single light direction. Crisp shadow boundaries, two-tone light and dark regions.",
        "Sharp posterized lighting — one light source, hard shadow lines, flat tone areas.",
        "Bold shadow edges, single-direction light, stepped tonal separation."
    ],
    "flat_even": [
        "Flat even lighting, no shadows.",
        "Uniform ambient light, zero contrast, all surfaces equally lit.",
        "Shadowless flat light, no directional component, even illumination throughout."
    ],
}

# ── Background scope cues ───────────────────────────────────────
# Appended to the background description to match the camera's viewing
# distance to the bbox scale.  The bboxes control character size; these
# cues control how much environment is visible and at what detail level,
# so Ideogram doesn't paint a close-up backdrop behind tiny figures
# (or a panoramic vista behind ones that fill the frame).

_BG_CUES = {
    # ── Close: tight crop, minimal background, shallow focus ──
    ("close", "equal"):         " The background is close behind, softly out of focus with shallow depth of field, only nearest surfaces and textures visible.",
    ("close", "dominant"):      " The immediate background blurs to bokeh behind the close perspective, only the nearest environmental details distinguishable.",
    ("close", "environmental"): " Close perspective with shallow focus — the environment is a soft, out-of-focus field behind the subjects, only the closest surfaces tangible.",

    # ── Medium: natural mid-distance, environment visible but not dominant ──
    ("medium", "equal"):         " The environment extends behind at a natural mid-distance, clearly visible but not dominant, a believable space surrounding the subjects.",
    ("medium", "dominant"):      " Mid-distance perspective with the environment stretching behind at a comfortable depth, enough to ground the scene without overpowering it.",
    ("medium", "environmental"): " The environment opens up behind at mid-distance, wide enough to show the broader setting while keeping the subjects grounded in it.",

    # ── Wide: expansive, environment dominates the frame ──
    ("wide", "equal"):           " The environment stretches wide and deep behind, an expansive view where the full landscape is visible and dominant.",
    ("wide", "dominant"):        " A sweeping, wide-angle view of the environment extending far behind and around, the landscape vast and dominant.",
    ("wide", "environmental"):   " A vast panoramic vista with the environment stretching to the horizon and beyond, wide-angle scope emphasizing the scale of the setting.",
}

# ── Framing modifiers ───────────────────────────────────────────
# Camera-angle language injected at three layers: HLD (already handled
# by _FRAMING_TEXT in layout_engine), background, and per-element desc.
# These ensure every part of the prompt agrees on camera perspective.

_BG_FRAMING_CUES = {
    "eye_level":  "",
    "high_angle": " Viewed from above — the groundplane and surfaces below are visible, figures seen from an elevated vantage looking down.",
    "low_angle":  " Viewed from below — ceiling, sky, or canopy is visible above the subjects, camera tilted upward.",
    "dutch":      " Composed with a canted Dutch tilt — the horizon line is off-kilter, creating diagonal tension.",
}

_ELEMENT_FRAMING_CUES = {
    "eye_level":  "",
    "high_angle": " Seen from above",
    "low_angle":  " Seen from below",
    "dutch":      " Framed at a tilted angle",
}


def _bg_cue(shot_width, scale_mode):
    """Return spatial grounding text for the background based on shot/scale."""
    return _BG_CUES.get((shot_width, scale_mode), "")


def _load_style_presets():
    global _STYLE_CACHE
    if _STYLE_CACHE is None:
        try:
            with open(STYLE_PRESETS_PATH, encoding="utf-8") as f:
                _STYLE_CACHE = json.load(f)
        except (IOError, json.JSONDecodeError):
            _STYLE_CACHE = {}
    return _STYLE_CACHE


def _load_scenarios():
    """Load all scenario packs from the scenarios directory."""
    global _SCENARIO_CACHE
    if _SCENARIO_CACHE is not None:
        return _SCENARIO_CACHE
    _SCENARIO_CACHE = {}
    if not os.path.isdir(SCENARIOS_DIR):
        return _SCENARIO_CACHE
    for fname in sorted(os.listdir(SCENARIOS_DIR)):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(SCENARIOS_DIR, fname), encoding='utf-8') as f:
                pack = json.load(f)
            key = pack.get("name", fname.replace('.json', ''))
            _SCENARIO_CACHE[key] = pack
        except (json.JSONDecodeError, IOError):
            continue
    return _SCENARIO_CACHE


def _scenario_labels():
    """Return dropdown labels for scenarios: [🎲 random, none, pirate_ship, ...]"""
    packs = _load_scenarios()
    labels = [SCENARIO_RANDOM, SCENARIO_NONE]
    for key, pack in sorted(packs.items()):
        labels.append(pack.get("label", key))
    return labels


# ── Font helper ───────────────────────────────────────────────────

def _font(size):
    for path in [_FONT_PATH, _COMFY_FONT]:
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


# ── Color helpers ─────────────────────────────────────────────────

def _hex_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)) if len(h) == 6 else (140, 140, 140)


def _readable(rgb):
    r, g, b = rgb
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if lum < 130:
        t = (130 - lum) / (255 - lum)
        r = round(r + (255 - r) * t)
        g = round(g + (255 - g) * t)
        b = round(b + (255 - b) * t)
    return (r, g, b)


def _type_color(elem_type):
    return {
        "background": (74, 138, 202),
        "subject": (202, 74, 74),
        "prop": (74, 202, 108),
        "threshold": (202, 180, 74),
    }.get(elem_type, (140, 140, 140))


def _wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            test = word if not line else line + " " + word
            if line and draw.textlength(test, font=font) > max_w:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
    return lines


# ── Preview Renderer (PIL → tensor) ───────────────────────────────

def _render_preview(elements, width=1024, height=1024):
    long_edge = max(width, height)
    scale = min(1.0, 1024 / long_edge) if long_edge > 0 else 1.0
    rw = max(1, round(width * scale))
    rh = max(1, round(height * scale))

    img = Image.new("RGBA", (rw, rh), (18, 18, 24, 255))
    overlay = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    fs = max(10, round(rh / 64))
    font = _font(fs)
    tag_font = _font(max(9, fs - 2))
    lh = fs + 2

    # Grid
    grid_color = (45, 45, 52, 120)
    for i in range(200, 1000, 200):
        gx = round(i / 1000 * rw)
        gy = round(i / 1000 * rh)
        draw.line([(gx, 0), (gx, rh)], fill=grid_color, width=1)
        draw.line([(0, gy), (rw, gy)], fill=grid_color, width=1)

    for elem in elements:
        bbox = elem.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        ymin, xmin, ymax, xmax = bbox
        x1 = max(0, min(rw, round(xmin / 1000 * rw)))
        y1 = max(0, min(rh, round(ymin / 1000 * rh)))
        x2 = max(0, min(rw, round(xmax / 1000 * rw)))
        y2 = max(0, min(rh, round(ymax / 1000 * rh)))
        if x2 < x1: x1, x2 = x2, x1
        if y2 < y1: y1, y2 = y2, y1

        etype = elem.get("type", "subject")
        r, g, b = _type_color(etype)
        label = elem.get("label", etype[:3].upper())
        desc = elem.get("desc", "")

        draw.rectangle([x1, y1, x2, y2], fill=(r, g, b, 38), outline=(r, g, b, 255), width=2)

        # Tag chip
        tw = draw.textlength(label, font=tag_font)
        draw.rectangle([x1, y1, x1 + tw + 8, y1 + fs + 2], fill=(r, g, b, 255))
        tagfill = (0, 0, 0, 255) if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else (255, 255, 255, 255)
        draw.text((x1 + 4, y1 + 1), label, fill=tagfill, font=tag_font)

        # Description inside box
        if desc and (x2 - x1) > 12 and (y2 - y1) > fs + 8:
            ty = y1 + fs + 6
            for line in _wrap(draw, desc, font, x2 - x1 - 8):
                if ty > y2 - 2: break
                draw.text((x1 + 4, ty), line, fill=_readable((r, g, b)) + (255,), font=font)
                ty += lh

    img = Image.alpha_composite(img, overlay).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


# ── Template Cache ────────────────────────────────────────────────

_TEMPLATE_CACHE = {}
_STYLE_CACHE = None
_SCENARIO_CACHE = None
_CACHE_VALID = False


def _invalidate_cache():
    """Invalidate all caches — templates, styles, and scenarios."""
    global _CACHE_VALID, _STYLE_CACHE, _SCENARIO_CACHE
    _CACHE_VALID = False
    _STYLE_CACHE = None
    _SCENARIO_CACHE = None


def _ensure_cache():
    global _TEMPLATE_CACHE, _CACHE_VALID
    if _CACHE_VALID:
        return
    _TEMPLATE_CACHE = {}
    _STYLE_CACHE = None
    _SCENARIO_CACHE = None
    if not os.path.isdir(TEMPLATES_DIR):
        _CACHE_VALID = True
        return
    for scene_type in sorted(os.listdir(TEMPLATES_DIR)):
        scene_dir = os.path.join(TEMPLATES_DIR, scene_type)
        if not os.path.isdir(scene_dir):
            continue
        for fname in sorted(os.listdir(scene_dir)):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(scene_dir, fname), encoding='utf-8') as f:
                    tpl = json.load(f)
                key = f"{scene_type}/{tpl.get('shot_width', 'unknown')}"
                if key not in _TEMPLATE_CACHE:
                    _TEMPLATE_CACHE[key] = []
                _TEMPLATE_CACHE[key].append(tpl)
            except (json.JSONDecodeError, IOError):
                continue
    _CACHE_VALID = True


def _all_scene_types():
    _ensure_cache()
    return sorted(set(k.split("/")[0] for k in _TEMPLATE_CACHE))


def _all_shot_widths(scene_type=None):
    _ensure_cache()
    widths = set()
    for k in _TEMPLATE_CACHE:
        st, sw = k.split("/")
        if scene_type and st != scene_type:
            continue
        widths.add(sw)
    return sorted(widths)


# ── API Routes ────────────────────────────────────────────────────

@PromptServer.instance.routes.get("/scene_gen/templates")
async def api_list_templates(request):
    _ensure_cache()
    scene_type = request.query.get("scene_type")
    shot_width = request.query.get("shot_width")
    results = []
    for key, templates in _TEMPLATE_CACHE.items():
        st, sw = key.split("/")
        if scene_type and st != scene_type:
            continue
        if shot_width and sw != shot_width:
            continue
        for tpl in templates:
            results.append({
                "name": tpl.get("name", ""),
                "description": tpl.get("description", ""),
                "scene_type": st,
                "shot_width": sw,
                "min_subjects": tpl.get("min_subjects", 0),
                "max_subjects": tpl.get("max_subjects", 6),
                "element_description_counts": {
                    k: len(v) for k, v in tpl.get("element_descriptions", {}).items()
                },
            })
    return web.json_response({"templates": results})


@PromptServer.instance.routes.get("/scene_gen/scene_types")
async def api_list_scene_types(request):
    return web.json_response({"scene_types": _all_scene_types()})


# ── Node ──────────────────────────────────────────────────────────

class SceneGenerator:
    """Procedurally generates Ideogram 4 structured JSON prompts from templates.

    Each filter can be locked to a specific value or set to random (🎲).
    The seed cascades through all unlocked layers.
    """

    @classmethod
    def INPUT_TYPES(cls):
        scene_types = _all_scene_types() or [
            "face_off", "close_group", "hero_journey",
            "wide_vista", "candid_moment"
        ]
        # Always offer all standard shot widths so saved workflows don't break
        shot_widths = ["close", "medium", "wide"]

        return {
            "required": {
                "scene_type": ([RANDOM_SCENE] + scene_types, {
                    "tooltip": "COMPOSITION preset — controls how figures are arranged and sized in frame (scale/arrangement/density). Pair with any scenario. Examples: face_off = opposing sides equal size; wide_vista = tiny figures in vast landscape; spotlight = one dominant figure."
                }),
                "shot_width": ([RANDOM_SHOT] + shot_widths,),
                "num_subjects": ("INT", {
                    "default": RANDOM_SUBJECTS,
                    "min": -1, "max": 6,
                    "tooltip": "-1 = random (within template's supported range)"
                }),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**32 - 1}),
                "seed_mode": (["static", "random", "iterate"],),
                "theme": ("STRING", {"default": "", "multiline": True,
                    "tooltip": "Optional flavor text. If scenario is selected, scenario provides the setting."}),
                "scenario": (_scenario_labels(), {
                    "default": SCENARIO_RANDOM,
                    "tooltip": "CONTENT pack — controls the setting, characters, and actions (the WHAT). Pair with any scene_type (the HOW). 'none' = use theme text only."
                }),
                "template_mode": (["random", "select"],),
                "template_index": ("INT", {"default": 0, "min": 0, "max": 50}),
                "style_mode": (STYLE_OPTIONS, {
                    "default": STYLE_FROM_TEMPLATE,
                    "tooltip": "template = use template's style (if any). Otherwise pick a preset or random."
                }),
                "lighting_mode": (LIGHTING_OPTIONS, {
                    "default": LIGHTING_FROM_TEMPLATE,
                    "tooltip": "template = inherit lighting from style/template. Otherwise pick a specific lighting setup or random."
                }),
                "palette_mode": (PALETTE_MODE_OPTIONS, {
                    "default": "auto",
                    "tooltip": "auto = inherit from style preset. Adjust brightness, saturation, or convert to grayscale."
                }),
            },
            "optional": {
                "width": ("INT", {
                    "default": 1024,
                    "min": 256, "max": 2048,
                    "step": 16,
                    "tooltip": "Output image width (Ideogram 4: 256-2048, multiples of 16)"
                }),
                "height": ("INT", {
                    "default": 1024,
                    "min": 256, "max": 2048,
                    "step": 16,
                    "tooltip": "Output image height (Ideogram 4: 256-2048, multiples of 16)"
                }),
                "scale_hierarchy": (SCALE_OPTIONS, {
                    "default": AUTO,
                    "tooltip": "auto = inherit from scene type preset"
                }),
                "arrangement": (ARR_OPTIONS, {
                    "default": AUTO,
                    "tooltip": "auto = inherit from scene type preset"
                }),
                "density": (DENSITY_OPTIONS, {
                    "default": AUTO,
                    "tooltip": "auto = inherit from scene type preset"
                }),
                "framing": (FRAMING_OPTIONS, {
                    "default": "eye_level",
                    "tooltip": "Camera angle. eye_level = horizon, high_angle = looking down, low_angle = looking up, dutch = tilted."
                }),
                "custom_subjects": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "One subject per line. Used when subject_mode is replace or supplement."
                }),
                "subject_mode": (["auto", "replace", "supplement"], {
                    "default": "auto",
                    "tooltip": "auto = scenario pack only. replace = custom only. supplement = custom + scenario shuffled together."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT", "IMAGE", "INT", "INT")
    RETURN_NAMES = ("prompt_json", "description", "seed_used", "preview", "width", "height")
    FUNCTION = "generate"
    CATEGORY = "SceneGen"

    # ── Template Loading ───────────────────────────────────────────

    @staticmethod
    def _load_templates(scene_type, shot_width):
        scene_dir = os.path.join(TEMPLATES_DIR, scene_type)
        if not os.path.isdir(scene_dir):
            return []
        results = []
        for fname in sorted(os.listdir(scene_dir)):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(scene_dir, fname), encoding='utf-8') as f:
                    tpl = json.load(f)
                if tpl.get('shot_width') == shot_width:
                    results.append(tpl)
            except (json.JSONDecodeError, IOError):
                continue
        return results

    @staticmethod
    def _load_all_templates():
        """Load every template across all scene types and shot widths."""
        _ensure_cache()
        results = []
        for key, tpls in _TEMPLATE_CACHE.items():
            results.extend(tpls)
        return results

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _pick(rng, pool, default=""):
        return rng.choice(pool) if pool else default

    @staticmethod
    def _fill(text, theme):
        if not text:
            return text
        return text.replace("{theme}", theme or "")

    @staticmethod
    def _get_layout(subject_layouts, num_subjects):
        if not subject_layouts:
            return {"boxes": []}
        key = str(num_subjects)
        if key in subject_layouts:
            return subject_layouts[key]
        available = sorted(int(k) for k in subject_layouts.keys())
        closest = min(available, key=lambda x: abs(x - num_subjects))
        return subject_layouts[str(closest)]

    # ── Element Description Helper ────────────────────────────────

    @staticmethod
    def _get_element_descs(template, num_subjects):
        """Get element descriptions for a given subject count, with fallback."""
        descs = template.get("element_descriptions", {})
        key = str(num_subjects)
        if key in descs:
            return list(descs[key])
        # Find closest available count
        available = sorted(int(k) for k in descs.keys())
        if available:
            closest = min(available, key=lambda x: abs(x - num_subjects))
            result = list(descs[str(closest)])
            while len(result) < num_subjects:
                result.append("{subject}, part of the scene.")
            return result
        return ["{subject}, part of the scene." for _ in range(num_subjects)]

    # ── Preview Element Builder ────────────────────────────────────

    @staticmethod
    def _build_preview_elements(template, num_subjects, scene_type=None, knobs=None,
                                width=1024, height=1024, scenario_pack=None, seed=42,
                                custom_subjects="", subject_mode="auto",
                                shot_width="medium"):
        elements = []

        if num_subjects > 0:
            layout_results = compute_layout(
                scene_type=scene_type, num_subjects=num_subjects,
                seed=42,  # deterministic preview
                width=width, height=height,
                shot_width=shot_width,
                **(knobs or {})
            )
            element_descs = SceneGenerator._get_element_descs(template, num_subjects)

            # Use _pick_subjects so preview matches output logic
            rng = random.Random(seed)
            preview_subjects = SceneGenerator._pick_subjects(
                scenario_pack, num_subjects, rng,
                custom_subjects, subject_mode)

            # Resolve actions so preview matches output
            action_pool = template.get("action_pool", [])
            actions = []
            if action_pool:
                shuffled = rng.sample(action_pool, len(action_pool))
                actions = [shuffled[i % len(shuffled)] for i in range(num_subjects)]

            for r in layout_results:
                i = r["position_index"]
                desc = element_descs[i] if i < len(element_descs) else f"Figure {i+1}"
                # Fill {subject} for preview
                if "{subject}" in desc:
                    desc = desc.replace("{subject}", preview_subjects[i])
                # Append action for preview parity
                if i < len(actions) and actions[i]:
                    desc = desc.rstrip('.') + ", " + actions[i] + "."
                elements.append({
                    "bbox": r["box"], "type": "subject",
                    "label": f"S{i+1}", "desc": desc[:100],
                })

        return elements

    # ── Layered Resolution ─────────────────────────────────────────
    #
    # Each parameter is resolved top-down. If the user set it to a specific
    # value, that's used directly. If it's "random", the seed decides.
    # The cascade: scene_type → shot_width → template → subjects → knobs → internals

    def _resolve(self, scene_type, shot_width, num_subjects,
                 template_mode, template_index, seed,
                 scale_hierarchy=AUTO, arrangement=AUTO, density=AUTO,
                 framing="eye_level"):
        """Resolve all random layers and return (template, resolved_scene_type,
        resolved_shot_width, resolved_num_subjects, resolved_knobs, rng)."""
        rng = random.Random(seed)

        # ── Layer 1: Scene type ──
        if scene_type == RANDOM_SCENE:
            all_types = _all_scene_types()
            resolved_st = rng.choice(all_types) if all_types else "face_off"
        else:
            resolved_st = scene_type

        # ── Layer 2: Shot width ──
        if shot_width == RANDOM_SHOT:
            avail_widths = _all_shot_widths(resolved_st)
            resolved_sw = rng.choice(avail_widths) if avail_widths else "wide"
        else:
            resolved_sw = shot_width

        # ── Layer 3: Template ──
        # Try exact shot_width match first
        templates = self._load_templates(resolved_st, resolved_sw)
        if not templates:
            # Fallback: try nearest shot_width for this scene type
            if resolved_sw == "close":
                fallback_widths = ["medium", "wide"]
            elif resolved_sw == "wide":
                fallback_widths = ["medium", "close"]
            else:
                fallback_widths = ["close", "wide"]
            for fb_w in fallback_widths:
                templates = self._load_templates(resolved_st, fb_w)
                if templates:
                    break
        if not templates:
            # Last resort: any template at all
            templates = self._load_all_templates()

        if template_mode == "select":
            idx = min(template_index, len(templates) - 1) if templates else 0
            template = templates[idx] if templates else None
        else:
            template = rng.choice(templates) if templates else None

        # Update resolved scene_type from the actual template (it might
        # differ if we fell back to a different scene type entirely).
        # BUT keep the user's requested shot_width — that controls box scaling
        # regardless of whether the template content matches.
        if template:
            resolved_st = template.get("scene_type", resolved_st)
            # resolved_sw stays as the user's choice, NOT the template's shot_width

        # ── Layer 4: Subject count ──
        if num_subjects == RANDOM_SUBJECTS:
            min_s = template.get("min_subjects", 0) if template else 0
            max_s = template.get("max_subjects", 4) if template else 4
            max_s = min(max_s, 6)  # cap at node max
            resolved_n = rng.randint(min_s, max_s) if max_s >= min_s else min_s
        else:
            resolved_n = num_subjects

        # ── Layer 5: Compositional knobs ──
        resolved_knobs = {}
        for user_val, knob_key in [
            (scale_hierarchy, "scale"),
            (arrangement, "arrangement"),
            (density, "density"),
        ]:
            if user_val == AUTO:
                # Inherit from preset
                resolved_knobs[knob_key] = None  # None = let compute_layout use preset
            elif user_val == RANDOM_SCENE:  # "🎲 random"
                options = {
                    "scale": ["equal", "dominant", "environmental"],
                    "arrangement": ["opposing", "clustered", "offset", "scattered"],
                    "density": ["sparse", "balanced", "dense"],
                }
                resolved_knobs[knob_key] = rng.choice(options[knob_key])
            else:
                resolved_knobs[knob_key] = user_val

        # ── Framing ──
        if framing == "🎲 random":
            resolved_knobs["framing"] = rng.choice(["eye_level", "high_angle", "low_angle", "dutch"])
        else:
            resolved_knobs["framing"] = framing

        return template, resolved_st, resolved_sw, resolved_n, resolved_knobs, rng

    # ── Main Generation ────────────────────────────────────────────

    def _resolve_scenario(self, scenario_label, rng):
        """Resolve scenario selection. Returns pack dict or None."""
        packs = _load_scenarios()
        if scenario_label == SCENARIO_RANDOM:
            if packs:
                key = rng.choice(sorted(packs.keys()))
                return packs[key]
            return None
        elif scenario_label == SCENARIO_NONE:
            return None
        else:
            # Match by label or name
            for key, pack in packs.items():
                if pack.get("label", key) == scenario_label or key == scenario_label:
                    return pack
            return None

    def generate(self, scene_type, shot_width, num_subjects, seed,
                 seed_mode, theme, scenario, template_mode, template_index,
                 style_mode=STYLE_FROM_TEMPLATE,
                 lighting_mode=LIGHTING_FROM_TEMPLATE,
                 palette_mode="auto",
                 width=1024, height=1024,
                 scale_hierarchy=AUTO, arrangement=AUTO, density=AUTO,
                 framing="eye_level",
                 custom_subjects="", subject_mode="auto"):
        # Resolve seed
        if seed_mode == "random":
            actual_seed = random.randint(0, 2**32 - 1)
        elif seed_mode == "iterate":
            actual_seed = (seed + 1) % (2**32)
        else:
            actual_seed = seed

        # Resolve all layers
        template, r_st, r_sw, r_n, r_knobs, rng = self._resolve(
            scene_type, shot_width, num_subjects,
            template_mode, template_index, actual_seed,
            scale_hierarchy, arrangement, density, framing
        )

        # Resolve scenario
        scenario_pack = self._resolve_scenario(scenario, rng)

        if not template:
            fallback = self._fallback_prompt(
                scene_type if scene_type != RANDOM_SCENE else "random",
                theme, max(num_subjects, 0)
            )
            preview = _render_preview([{
                "bbox": [200, 300, 800, 700],
                "type": "subject", "label": "?", "desc": "No template found",
            }], width, height)
            return (json.dumps(fallback, indent=2),
                    fallback["high_level_description"], actual_seed, preview,
                    width, height)

        prompt, preview_elements = self._build(template, r_n, theme, rng, r_st, r_knobs, width, height,
                              style_mode, lighting_mode, palette_mode, scenario_pack,
                              custom_subjects, subject_mode, shot_width=r_sw)

        # Render preview from actual output elements (guarantees parity)
        preview = _render_preview(preview_elements, width, height)

        # Enrich description with resolved values for user feedback
        desc = prompt["high_level_description"]
        tags = []
        # Scene type (flag if was random)
        if scene_type == RANDOM_SCENE:
            tags.append(f"scene:{r_st} 🎲")
        else:
            tags.append(f"scene:{r_st}")
        # Shot width
        if shot_width == RANDOM_SHOT:
            tags.append(f"shot:{r_sw} 🎲")
        else:
            tags.append(f"shot:{r_sw}")
        # Subject count
        if num_subjects == RANDOM_SUBJECTS:
            tags.append(f"n:{r_n} 🎲")
        else:
            tags.append(f"n:{r_n}")
        # Scenario
        if scenario_pack:
            tags.append(f"scenario:{scenario_pack.get('name', '?')}")
        # Style — show what was actually picked
        if style_mode == STYLE_FROM_TEMPLATE:
            tags.append("style:from_template")
        elif style_mode == "🎲 random":
            sb = prompt.get("style_description", {})
            picked = sb.get("photo", sb.get("art_style", "?"))
            if isinstance(picked, list):
                picked = picked[0] if picked else "?"
            tags.append(f"style:🎲 {str(picked)[:35]}")
        else:
            tags.append(f"style:{style_mode}")
        # Lighting
        if lighting_mode == LIGHTING_FROM_TEMPLATE:
            tags.append("light:from_template")
        elif lighting_mode == "🎲 random":
            actual_light = prompt.get("style_description", {}).get("lighting", "?")
            if isinstance(actual_light, list):
                actual_light = actual_light[0] if actual_light else "?"
            tags.append(f"light:🎲 {str(actual_light)[:30]}")
        else:
            tags.append(f"light:{lighting_mode}")
        # Palette
        tags.append(f"palette:{palette_mode}")
        # Framing
        tags.append(f"framing:{framing}")
        # Compositional knobs (always show resolved)
        _rk = {k: v for k, v in r_knobs.items() if k != "framing"}
        effective = resolve_knobs(r_st, **_rk)
        tags.append(f"scale:{effective['scale']}")
        tags.append(f"arr:{effective['arrangement']}")
        tags.append(f"density:{effective['density']}")
        # Template name
        tags.append(f"tmpl:{template.get('name', '?')}")
        if tags:
            desc += f"  [{', '.join(tags)}]"

        return (json.dumps(prompt, indent=2), desc, actual_seed, preview,
                width, height)

    @staticmethod
    def _pick_subjects(scenario_pack, num_subjects, rng,
                       custom_subjects="", subject_mode="auto"):
        """Pick subject descriptions, shuffled by seed.
        
        Priority: custom_subjects (replace) > custom+scenario (supplement) > scenario (auto) > "a figure"
        """
        # Parse custom subjects (one per line, strip empties)
        custom = []
        if custom_subjects and custom_subjects.strip():
            custom = [line.strip() for line in custom_subjects.splitlines() if line.strip()]
        
        if subject_mode == "replace" and custom:
            pool = list(custom)
        elif subject_mode == "supplement" and custom:
            pool = list(custom)
            if scenario_pack:
                pool.extend(scenario_pack.get("subject_pool", []))
        else:
            # auto, or custom empty
            if scenario_pack:
                pool = list(scenario_pack.get("subject_pool", ["a figure"]))
            else:
                pool = ["a figure"]
        
        if not pool:
            pool = ["a figure"]
        
        rng.shuffle(pool)
        subjects = []
        for i in range(num_subjects):
            subjects.append(pool[i % len(pool)])
        return subjects

    def _build(self, template, num_subjects, theme, rng, scene_type=None, knobs=None,
                width=1024, height=1024, style_mode=STYLE_FROM_TEMPLATE,
                lighting_mode=LIGHTING_FROM_TEMPLATE,
                palette_mode="auto",
                scenario_pack=None, custom_subjects="", subject_mode="auto",
                shot_width="medium"):
        # ── Resolve setting text ──
        if scenario_pack:
            setting = self._pick(rng, scenario_pack.get("setting_pool", []), "A scene")
        else:
            setting = theme.strip() if theme.strip() else "A scene"

        # HLD: fill {setting} and {theme}
        hld_pattern = self._pick(rng, template.get("hld_patterns", []), "{setting}.")
        high_level = hld_pattern.replace("{setting}", setting)
        high_level = high_level.replace("{theme}", theme or "")
        # Clean up trailing space if theme is empty
        high_level = high_level.strip()
        # Inject camera angle language for framing modes
        framing = (knobs or {}).get("framing", "eye_level")
        framing_text = _FRAMING_TEXT.get(framing, "")
        if framing_text:
            if high_level.endswith('.'):
                high_level = high_level + framing_text
            else:
                high_level = high_level + "." + framing_text
        if high_level.endswith('.'):
            pass  # good
        else:
            high_level += '.'

        # ── Style resolution ──
        if style_mode == STYLE_FROM_TEMPLATE:
            style = template.get("style", {})
            style_block = {
                "aesthetics": self._pick(rng, style.get("aesthetics_pool", []),
                                         "Cinematic digital illustration"),
                "lighting": self._pick(rng, style.get("lighting_pool", []),
                                       "Naturalistic lighting with atmospheric depth"),
            }
            if style.get("photo_pool"):
                style_block["photo"] = self._pick(rng, style["photo_pool"], "50mm cinematic photography")
            elif style.get("art_style_pool"):
                style_block["art_style"] = self._pick(rng, style["art_style_pool"], "Digital illustration")
            else:
                style_block["photo"] = "50mm cinematic photography"
            style_block["medium"] = self._pick(rng, style.get("medium_pool", []),
                                     "Digital illustration")
            style_block["color_palette"] = _adjust_palette(
                    self._pick(rng, style.get("palette_pool", []),
                               ["#3a3a3a", "#8a8a8a", "#d0d0d0", "#1a1a2e", "#c4956a"]),
                    palette_mode, rng)
        else:
            presets = _load_style_presets()
            if style_mode == "🎲 random":
                preset_names = list(presets.keys())
                chosen = rng.choice(preset_names) if preset_names else "cinematic"
            else:
                chosen = style_mode
            preset = presets.get(chosen, presets.get("cinematic", {}))
            style_block = {
                "aesthetics": self._pick(rng, preset.get("aesthetics", []),
                                         "Cinematic digital illustration"),
                "lighting": self._pick(rng, preset.get("lighting", []),
                                       "Naturalistic lighting"),
            }
            # Emit photo OR art_style — never both, never neither
            if preset.get("photo"):
                style_block["photo"] = self._pick(rng, preset["photo"], "50mm")
            elif preset.get("art_style"):
                style_block["art_style"] = self._pick(rng, preset["art_style"], "Digital illustration")
            else:
                style_block["photo"] = "50mm"
            style_block["medium"] = self._pick(rng, preset.get("medium", []),
                                     "Digital illustration")
            style_block["color_palette"] = _adjust_palette(
                    self._pick(rng, preset.get("palette", []),
                               ["#3a3a3a", "#8a8a8a", "#d0d0d0", "#1a1a2e", "#c4956a"]),
                    palette_mode, rng)

        # ── Lighting override ──
        if lighting_mode != LIGHTING_FROM_TEMPLATE:
            if lighting_mode == "🎲 random":
                preset_names = list(LIGHTING_PRESETS.keys())
                chosen_light = rng.choice(preset_names)
            else:
                chosen_light = lighting_mode
            light_pool = LIGHTING_PRESETS.get(chosen_light, ["Naturalistic lighting with atmospheric depth"])
            style_block["lighting"] = self._pick(rng, light_pool, "Naturalistic lighting")

        # ── Resolve background ──
        # Scenario backgrounds are thematically matched to the setting and
        # take priority. Template backgrounds are a fallback when no scenario
        # is selected.
        if scenario_pack and scenario_pack.get("background_pool"):
            bg_pool = scenario_pack["background_pool"]
        else:
            bg_pool = template.get("background_pool", [])

        # Normalise pool entries to {text, shot} dicts; legacy strings get
        # shot="any" so they work at any width.
        norm_pool = []
        for entry in bg_pool:
            if isinstance(entry, dict):
                norm_pool.append(entry)
            else:
                norm_pool.append({"text": entry, "shot": "any"})

        # Prefer backgrounds whose natural shot matches the resolved
        # shot_width. Fall back to 'any' entries, then to the full pool
        # so we never return empty.
        match_pool = [e for e in norm_pool if e.get("shot") == shot_width]
        if not match_pool:
            match_pool = [e for e in norm_pool if e.get("shot") == "any"]
        if not match_pool:
            match_pool = norm_pool
        bg_entry = self._pick(rng, match_pool, {}) if match_pool else {}
        background = bg_entry.get("text", "") if isinstance(bg_entry, dict) else str(bg_entry)

        # Inject setting text into background (same as element descs)
        if background:
            background = background.replace("{setting}", setting.lower() if len(setting) > 1 else setting)
        # Inject spatial cue to ground subjects relative to their environment
        if background and num_subjects > 0:
            raw_scale = (knobs or {}).get("scale")
            if raw_scale is None:
                effective_scale = resolve_knobs(scene_type)["scale"]
            else:
                effective_scale = raw_scale
            bg_cue = _bg_cue(shot_width, effective_scale)
            if bg_cue:
                if background.endswith('.'):
                    background = background + " " + bg_cue.lstrip()
                else:
                    background = background + "." + bg_cue.lstrip()

        # Inject camera-angle cue into background
        bg_framing = _BG_FRAMING_CUES.get(framing, "")
        if bg_framing and background:
            if background.endswith('.'):
                background = background + " " + bg_framing.lstrip()
            else:
                background = background + "." + bg_framing.lstrip()

        # ── Resolve action pool ──
        action_pool = template.get("action_pool", [])
        # Pick distinct actions for each subject (cycle if pool < subjects)
        actions = []
        if action_pool:
            shuffled = rng.sample(action_pool, len(action_pool))
            for i in range(num_subjects):
                actions.append(shuffled[i % len(shuffled)])

        elements = []
        preview_elements = []

        if num_subjects > 0:
            element_descs = self._get_element_descs(template, num_subjects)
            subjects = self._pick_subjects(scenario_pack, num_subjects, rng,
                                           custom_subjects, subject_mode)

            layout_seed = rng.randint(0, 2**32 - 1)
            layout_results = compute_layout(
                scene_type=scene_type, num_subjects=num_subjects,
                seed=layout_seed, width=width, height=height,
                shot_width=shot_width,
                **(knobs or {})
            )

            for r in layout_results:
                i = r["position_index"]
                desc = element_descs[i] if i < len(element_descs) else f"Figure {i+1}."
                # Fill placeholders
                desc = desc.replace("{subject}", subjects[i])
                desc = desc.replace("{setting}", setting)
                desc = desc.replace("{theme}", theme or "")
                # Inject camera-angle modifier into element description
                elem_framing = _ELEMENT_FRAMING_CUES.get(framing, "")
                if elem_framing and elem_framing not in desc:
                    desc = desc.rstrip('.') + f", {elem_framing}."
                # Append action if available
                if i < len(actions) and actions[i]:
                    if desc.endswith('.'):
                        desc = desc[:-1] + ", " + actions[i] + "."
                    else:
                        desc = desc + ", " + actions[i] + "."
                elements.append({
                    "type": "obj",
                    "bbox": r["box"],
                    "desc": desc,
                })
                preview_elements.append({
                    "bbox": r["box"],
                    "type": "subject",
                    "label": f"S{i+1}",
                    "desc": desc[:100],
                })

        return {
            "high_level_description": high_level,
            "style_description": style_block,
            "compositional_deconstruction": {
                "background": background,
                "elements": elements,
            }
        }, preview_elements

    @staticmethod
    def _fallback_prompt(scene_type, theme, num_subjects):
        elements = []
        if num_subjects > 0:
            elements.append({
                "type": "obj", "bbox": [200, 300, 800, 700],
                "desc": "A figure in the scene, apparently unaware of the viewer."
            })
        return {
            "high_level_description": f"A {scene_type.replace('_', ' ')} scene. {theme}".strip(),
            "style_description": {
                "aesthetics": "Cinematic digital illustration",
                "lighting": "Naturalistic lighting with atmospheric depth",
                "photo": "50mm cinematic photography",
                "medium": "Digital illustration",
                "color_palette": ["#3a3a3a", "#8a8a8a", "#d0d0d0", "#1a1a2e", "#c4956a"]
            },
            "compositional_deconstruction": {
                "background": f"A detailed {theme} environment with layered depth.",
                "elements": elements
            }
        }
