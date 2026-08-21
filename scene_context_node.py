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

RANDOM = "🎲 random"
NONE_OPT = "none"

GENRE_OPTIONS = [RANDOM, "historical", "modern", "sci_fi", "fantasy"]
GENRE2_OPTIONS = [NONE_OPT, RANDOM, "historical", "modern", "sci_fi", "fantasy"]

_CACHE = {"settings": None, "tones": None, "atmosphere": None}


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
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("context_text", "scene_type_suggestion", "resolved_setting", "resolved_tone", "seed_used")
    FUNCTION = "generate"
    CATEGORY = "SceneGen"

    def generate(self, genre, genre2, tone, setting, seed):
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

        flourish = rng.choice(atmosphere)

        context_text = f"{chosen_setting['subject_label']}, {situation['text']}, {modifier}, {flourish}"
        scene_type_suggestion = situation.get("scene_type_bias", "")

        return (context_text, scene_type_suggestion, chosen_setting["name"], chosen_tone_key, seed)


NODE_CLASS_MAPPINGS = {
    "SceneContextPicker": SceneContextPicker,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneContextPicker": "🧭 Scene Context Picker",
}
