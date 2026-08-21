"""
Scene Context Composer — v2 of the scene context system.

Clean-room node: everything the four-axis cascade has learned, none of
the legacy Ideogram-era surface. Renderer-agnostic — it composes text
and metadata, and any text-conditioned model (local GGUF, hosted API,
whatever) consumes the result. Nothing here assumes a backend.

Axes:
    Genre (+ optional Genre 2, union) -> flavors the venue pool
    Setting is two-tier:
        Archetype ('on a nautical vessel') gates venues by facet tags
        Venue (pirate_ship) pins a specific setting outright
    Setting -> Situation (may declare an `env` requirement)
    Tone (independent) -> modifier phrase
    Atmosphere (env-constrained) -> flourish
    Composition (first-class, new) -> framing phrase keyed by the
        situation's scene_type_bias; unknown/missing keys fall back to
        the generic pool (allow-list shape — new bias values match
        nothing until a pool is deliberately added)

Outputs:
    context_text    subject, situation, tone modifier, atmosphere
    render_prompt   context_text + composition phrase (model-ready)
    components_json every piece separately, for remixing downstream
    seed_used       pass-through so samplers can share the roll

Data lives in scene_context/ — shared with SceneContextPicker, single
source of truth, no schema fork.
"""

import json
import os
import random

try:  # package context — how ComfyUI loads custom node packs
    from .scene_context_node import (
        GENRE_OPTIONS,
        GENRE2_OPTIONS,
        RANDOM,
        NONE_OPT,
        _load_settings,
        _load_tones,
        _load_atmosphere,
        _pick_flourish,
        _filter_by_genre,
    )
except ImportError:  # standalone — test harness / direct exec
    from scene_context_node import (  # noqa: F811
        GENRE_OPTIONS,
        GENRE2_OPTIONS,
        RANDOM,
        NONE_OPT,
        _load_settings,
        _load_tones,
        _load_atmosphere,
        _pick_flourish,
        _filter_by_genre,
    )

COMPOSITION_PATH = os.path.join(
    os.path.dirname(__file__), "scene_context", "composition.json"
)
ARCHETYPES_PATH = os.path.join(
    os.path.dirname(__file__), "scene_context", "archetypes.json"
)


def _load_composition():
    with open(COMPOSITION_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_archetypes():
    with open(ARCHETYPES_PATH, encoding="utf-8") as f:
        return json.load(f)["archetypes"]


def _setting_options():
    """One dropdown, two tiers: archetype labels first (casual path),
    then concrete venue names (author override path)."""
    labels = [a["label"] for a in _load_archetypes().values()]
    return [RANDOM] + labels + sorted(_load_settings().keys())


class SceneContextComposer:
    """Composes a structured scene context; suggests framing from the
    situation's composition bias. Pure text — no renderer assumptions."""

    @classmethod
    def INPUT_TYPES(cls):
        comp = _load_composition()
        comp_keys = sorted(k for k in comp if k != "default")
        return {
            "required": {
                "genre": (GENRE_OPTIONS, {"default": RANDOM}),
                "genre2": (GENRE2_OPTIONS, {"default": NONE_OPT,
                    "tooltip": "Optional second genre. Union with genre — settings matching EITHER are eligible (mashup)."}),
                "tone": ([RANDOM] + list(_load_tones().keys()), {"default": RANDOM}),
                "setting": (_setting_options(), {"default": RANDOM,
                    "tooltip": "Two tiers: an archetype ('on a nautical vessel') filters venues by facet tags, random within the pool; a specific venue name pins it outright. 🎲 rolls venues by Genre."}),
                "composition": ([RANDOM, NONE_OPT] + comp_keys, {"default": RANDOM,
                    "tooltip": "Framing axis. random: follow the situation's scene_type_bias. none: emit no framing phrase."}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**32 - 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("context_text", "render_prompt", "components_json", "seed_used")
    FUNCTION = "compose"
    CATEGORY = "SceneGen"

    def compose(self, genre, genre2, tone, setting, composition, seed):
        rng = random.Random(seed)
        settings = _load_settings()
        tones = _load_tones()
        archetypes = _load_archetypes()
        label_to_id = {a["label"]: aid for aid, a in archetypes.items()}

        if setting != RANDOM and setting in settings:
            # explicit venue override — the author escape hatch, always
            # unconstrained (a fantasy cruise ship is a legitimate ask)
            chosen = settings[setting]
            genre_narrowed = False
            archetype_narrowed = False
        else:
            genre_pool = _filter_by_genre(settings, genre, genre2)
            genre_narrowed = len(genre_pool) < len(settings)
            if setting in label_to_id:
                facets = set(archetypes[label_to_id[setting]]["facets"])
                pool = [
                    v for v in genre_pool
                    if facets <= set(v.get("facet_tags", []))
                ]
                if not pool:
                    # join-miss: archetype is structural, genre is flavor —
                    # flavor yields first (decided up front; issue #2)
                    pool = [
                        v for v in settings.values()
                        if facets <= set(v.get("facet_tags", []))
                    ]
                if not pool:
                    raise ValueError(
                        f"Archetype '{setting}' matches no venue — add a "
                        f"setting with facet tags {sorted(facets)}"
                    )
                archetype_narrowed = len(pool) < len(genre_pool)
                chosen = rng.choice(pool)
            else:
                archetype_narrowed = False
                chosen = rng.choice(genre_pool)

        # Tone resolves BEFORE the situation pick — it's a selection
        # axis, not seasoning sprinkled on after the fact (the double-
        # filter design: Setting AND Tone jointly narrow the situation).
        tone_key = tone if tone != RANDOM else rng.choice(list(tones.keys()))
        compatible = tones[tone_key].get("compatible")
        # absent "compatible" = open register: sits on any situation
        if compatible:
            tone_pool = [
                s for s in chosen["situations"]
                if any(tag in s.get("tags", []) for tag in compatible)
            ]
            if not tone_pool:
                # join-miss: the venue IS its situations (structure);
                # tone is flavor — flavor yields, same rule as genre
                tone_pool = chosen["situations"]
        else:
            tone_pool = chosen["situations"]
        tone_narrowed = len(tone_pool) < len(chosen["situations"])

        situation = rng.choice(tone_pool)
        modifier = rng.choice(tones[tone_key]["modifiers"])
        flourish = _pick_flourish(_load_atmosphere(), situation, rng)

        context_text = (
            f"{chosen['subject_label']}, {situation['text']}, {modifier}, {flourish}"
        )

        comp_pool = _load_composition()
        comp_key = ""
        comp_phrase = ""
        if composition != NONE_OPT:
            key = (
                composition
                if composition != RANDOM
                else situation.get("scene_type_bias", "")
            )
            pool = comp_pool.get(key) or comp_pool["default"]
            comp_key = key if comp_pool.get(key) else "default"
            comp_phrase = rng.choice(pool)

        render_prompt = (
            f"{context_text}, {comp_phrase}" if comp_phrase else context_text
        )

        # which archetypes does the chosen venue satisfy? (may be several)
        chosen_facets = set(chosen.get("facet_tags", []))
        arch_matches = [
            archetypes[aid]["label"]
            for aid in archetypes
            if set(archetypes[aid]["facets"]) <= chosen_facets
        ]

        components = {
            "setting": chosen["name"],
            "venue": chosen["name"],
            "archetype": (
                setting if setting in label_to_id
                else (arch_matches[0] if arch_matches else "")
            ),
            "archetype_matches": arch_matches,
            "genre_narrowed": genre_narrowed,
            "archetype_narrowed": archetype_narrowed,
            "tone_narrowed": tone_narrowed,
            "subject": chosen["subject_label"],
            "situation_id": situation["id"],
            "situation_text": situation["text"],
            "tone": tone_key,
            "tone_modifier": modifier,
            "atmosphere": flourish,
            "env": situation.get("env", ""),
            "composition": comp_key,
            "composition_phrase": comp_phrase,
            "context_text": context_text,
            "render_prompt": render_prompt,
            "seed": seed,
        }
        return (
            context_text,
            render_prompt,
            json.dumps(components, ensure_ascii=False),
            seed,
        )


NODE_CLASS_MAPPINGS = {
    "SceneContextComposer": SceneContextComposer,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneContextComposer": "🎼 Scene Context Composer",
}
