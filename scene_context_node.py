"""
Scene Context Picker — ComfyUI node.

Genre (+ optional Genre 2, union mashup) -> filters Setting
Tone (independent) -> flavors the situation
Setting's chosen Situation carries a scene_type_bias suggestion,
which can be wired into the existing SceneGenerator node's
scene_type input (convert that widget to an input to accept it).

Outputs a plain-text context string meant to feed the existing
SceneGenerator node's `theme` input, plus metadata for the label/description.

No torch/PIL dependency — this node only assembles text, so it can be
smoke-tested standalone without a full ComfyUI install.
"""

import json
import os
import random

CONTEXT_DIR = os.path.join(os.path.dirname(__file__), "scene_context")
SETTINGS_DIR = os.path.join(CONTEXT_DIR, "settings")
TONES_PATH = os.path.join(CONTEXT_DIR, "tones.json")
ATMOSPHERE_PATH = os.path.join(CONTEXT_DIR, "atmosphere.json")
CHARACTER_SLOTS_PATH = os.path.join(CONTEXT_DIR, "character_slots.json")
FEATURES_PATH = os.path.join(CONTEXT_DIR, "character_features.json")

RANDOM = "🎲 random"
NONE_OPT = "none"

GENRE_OPTIONS = [RANDOM, "historical", "modern", "sci_fi", "fantasy"]
GENRE2_OPTIONS = [NONE_OPT, RANDOM, "historical", "modern", "sci_fi", "fantasy"]

_CACHE = {"settings": None, "tones": None, "atmosphere": None, "character_slots": None, "features": None}

# Environmental tag contract: a situation that embeds a weather claim
# declares `env`, and the atmosphere roll respects it. Untagged situations
# accept any sky. Time-of-day flourishes are "neutral" — compatible with
# everything ("squall at night" is fine; "squall under a bright midday
# sun" is not).
ENV_COMPAT = {
    "storm": {"storm", "neutral", "overcast"},
    "clear": {"clear", "neutral"},
    "overcast": {"overcast", "neutral", "storm"},
}

# Indoor situations: the frame is inside, so outdoor flourishes read as the
# weather beyond a window rather than as the scene's own sky. This is
# probabilistic by design (Alexander, 2026-08-22): interiors shouldn't be
# forced to always convey outside circumstances, and window-framing
# shouldn't dominate — sometimes the room is just the room.
#   - ~35%: the outside world shows through a window (inheriting the
#     situation's own weather env when it declares one, else any outdoor)
#   - ~65%: an indoor flourish — lamp, candle, fluorescent hum, time of day
INDOOR_WINDOW_CHANCE = 0.35
INDOOR_FLOURISHES = (
    "by lamplight, the room close and warm",
    "in the hush of a candlelit room",
    "under the white hum of fluorescent light",
    "in the dead of night",
    "in the pale light of early morning",
)
WINDOW_VIEWS = {
    "storm": "the window darkened by the storm outside",
    "clear": "sunlight through the window",
    "overcast": "grey daylight through the window",
    "neutral": "light through the window",
}


def _load_settings():
    if _CACHE["settings"] is None:
        settings = {}
        if os.path.isdir(SETTINGS_DIR):
            for fname in sorted(os.listdir(SETTINGS_DIR)):
                if fname.endswith(".json"):
                    with open(os.path.join(SETTINGS_DIR, fname), encoding="utf-8") as f:
                        data = json.load(f)
                        settings[data["name"]] = data
        _CACHE["settings"] = settings
    return _CACHE["settings"]


def _load_tones():
    if _CACHE["tones"] is None:
        with open(TONES_PATH, encoding="utf-8") as f:
            _CACHE["tones"] = json.load(f)
    return _CACHE["tones"]


def _load_atmosphere():
    if _CACHE["atmosphere"] is None:
        with open(ATMOSPHERE_PATH, encoding="utf-8") as f:
            _CACHE["atmosphere"] = json.load(f)["flourishes"]
    return _CACHE["atmosphere"]


def _pick_flourish(atmosphere, situation, rng):
    """Atmosphere flourish that doesn't contradict the situation's env."""
    required_env = situation.get("env")

    # Indoor framing: only when the situation declares itself enclosed.
    if situation.get("indoor"):
        if rng.random() < INDOOR_WINDOW_CHANCE:
            view_env = required_env if required_env in WINDOW_VIEWS else "neutral"
            return WINDOW_VIEWS[view_env]
        return rng.choice(INDOOR_FLOURISHES)

    if required_env:
        allowed = ENV_COMPAT.get(required_env, {required_env, "neutral"})
        pool = [f for f in atmosphere if f.get("env", "neutral") in allowed]
        if pool:
            return rng.choice(pool)["text"]
    outdoor = [f for f in atmosphere if f.get("env", "neutral") != "indoor"]
    return rng.choice(outdoor)["text"]


def _load_character_slots():
    if _CACHE["character_slots"] is None:
        with open(CHARACTER_SLOTS_PATH, encoding="utf-8") as f:
            _CACHE["character_slots"] = json.load(f)
    return _CACHE["character_slots"]


def _load_features():
    if _CACHE["features"] is None:
        with open(FEATURES_PATH, encoding="utf-8") as f:
            _CACHE["features"] = json.load(f)
    return _CACHE["features"]


def _decorate_cast(chars, rng, pool_key):
    """Attach a phrase from a feature pool to each figure — no repeats
    within the cast when the pool allows it."""
    feats = _load_features()[pool_key]
    picks = (
        rng.sample(feats, len(chars))
        if len(chars) <= len(feats)
        else [rng.choice(feats) for _ in chars]
    )
    return [
        f"{c}, {p}" if p not in c else c
        for c, p in zip(chars, picks)
    ]


def _stage_characters(chars, rng, pose=False, positioning=False):
    """Turn a list of character descriptions into one staging phrase,
    or "" when no characters are supplied. Placement templates scale
    with the cast size (1..4, soft cap — diffusion muddies past ~3
    named subjects). Register: lateral/relational only, photograph
    staging; scale/framing language belongs to the layout layer.

    pose=True appends a static posture phrase to each figure (from
    character_features.json). positioning=True hands scene placement to
    stochastic per-figure position phrases instead of the placement
    templates — the "bare" template set keeps sentence structure without
    adding its own placement language. The Scene Character Roller
    carries the same toggles; if both fire somewhere, the doubled cue
    is the user's call. Sometimes the composition works itself out."""
    chars = [
        c.replace("\n", " ").strip().rstrip(".")
        for c in chars
        if isinstance(c, str) and c.strip()
    ]
    if not chars:
        return ""
    n = min(len(chars), 4)
    chars = chars[:n]

    if pose:
        chars = _decorate_cast(chars, rng, "postures")
    if positioning:
        chars = _decorate_cast(chars, rng, "positions")
        bare = _load_character_slots().get("bare", {})
        template = (
            rng.choice(bare[str(n)]) if str(n) in bare
            else "; ".join(f"{{c{i + 1}}}" for i in range(n))
        )
        return template.format(**{f"c{i + 1}": chars[i] for i in range(n)})

    template = rng.choice(_load_character_slots()["placements"][str(n)])
    return template.format(**{f"c{i + 1}": chars[i] for i in range(n)})


def _setting_names():
    names = sorted(_load_settings().keys())
    return names or ["pirate_ship"]


def _filter_by_genre(settings, genre, genre2):
    """Union filter: include if genre OR genre2 matches. Both 'random'/'none'
    are treated as no constraint on that slot."""
    g1 = None if genre == RANDOM else genre
    g2 = None if genre2 in (NONE_OPT, RANDOM) else genre2

    if g1 is None and g2 is None:
        return list(settings.values())

    wanted = {g for g in (g1, g2) if g}
    matches = [s for s in settings.values() if wanted & set(s.get("genre_tags", []))]
    return matches or list(settings.values())


class SceneContextPicker:
    """Assembles a coherent scene context string from Genre/Tone/Setting,
    and suggests a scene_type composition bias for the layout engine."""

    @classmethod
    def INPUT_TYPES(cls):
        tone_keys = list(_load_tones().keys())
        return {
            "required": {
                "genre": (GENRE_OPTIONS, {"default": RANDOM}),
                "genre2": (GENRE2_OPTIONS, {"default": NONE_OPT,
                    "tooltip": "Optional second genre. Union with genre — settings matching EITHER are eligible (mashup)."}),
                "tone": ([RANDOM] + tone_keys, {"default": RANDOM}),
                "setting": ([RANDOM] + _setting_names(), {"default": RANDOM,
                    "tooltip": "Force a specific setting, or let Genre(s) filter randomly."}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**32 - 1}),
                "pose": ("BOOLEAN", {"default": False,
                    "tooltip": "Append a posture phrase to each staged character (static stance register). The Scene Character Roller has the same toggle — if both fire, doubled cues are yours."}),
                "positioning": ("BOOLEAN", {"default": False,
                    "tooltip": "Drop the placement templates; each staged character gets its own position phrase. Off = template staging, the default."}),
            },
            "optional": {
                f"character_{i}": ("STRING", {
                    "forceInput": True,
                    "tooltip": (
                        "Wire a character description ('a fisher in a yellow "
                        "slicker'). Placement is staged automatically — "
                        "left/center/right per cast size. Soft cap: 4; "
                        "beyond that, extras are ignored."
                        if i == 1 else
                        "Additional character. Leave unwired to drop."
                    ),
                })
                for i in range(1, 5)
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("context_text", "scene_type_suggestion", "resolved_setting", "resolved_tone", "seed_used")
    FUNCTION = "generate"
    CATEGORY = "SceneGen"

    def generate(self, genre, genre2, tone, setting, seed, pose=False, positioning=False, **kwargs):
        rng = random.Random(seed)
        settings = _load_settings()
        tones = _load_tones()
        atmosphere = _load_atmosphere()

        if setting != RANDOM and setting in settings:
            chosen_setting = settings[setting]
        else:
            pool = _filter_by_genre(settings, genre, genre2)
            chosen_setting = rng.choice(pool)

        situation = rng.choice(chosen_setting["situations"])

        chosen_tone_key = tone if tone != RANDOM else rng.choice(list(tones.keys()))
        tone_data = tones[chosen_tone_key]
        modifier = rng.choice(tone_data["modifiers"])

        flourish = _pick_flourish(atmosphere, situation, rng)

        chars = [kwargs.get(f"character_{i}") or "" for i in (1, 2, 3, 4)]
        staging = _stage_characters(chars, rng, pose=pose, positioning=positioning)

        parts = [chosen_setting['subject_label'], situation['text'], modifier]
        if staging:
            parts.append(staging)
        parts.append(flourish)
        context_text = ", ".join(parts)
        scene_type_suggestion = situation.get("scene_type_bias", "")

        return (context_text, scene_type_suggestion, chosen_setting["name"], chosen_tone_key, seed)


NODE_CLASS_MAPPINGS = {
    "SceneContextPicker": SceneContextPicker,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneContextPicker": "🧭 Scene Context Picker",
}
