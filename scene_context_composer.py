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
    Tone (independent) -> summary word + behavior clause
    Atmosphere (env-constrained) -> flourish
    Composition (first-class, new) -> framing phrase keyed by the
        situation's scene_type_bias; unknown/missing keys fall back to
        the generic pool (allow-list shape — new bias values match
        nothing until a pool is deliberately added)

Outputs:
    context_text    whole-scene sentences: locative + subject + activity,
                    anchored mood summary, behavior ground
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
        _stage_characters,
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
        _stage_characters,
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
    """One dropdown, family-clustered: each archetype label sits directly
    above the venues it can roll (facet-superset membership — the same
    rule compose() applies), so the flat list reads as grouped families.
    Hierarchy is order-only on purpose: in a ComfyUI combo the display
    string IS the persisted value, so cosmetic prefixes/indents would
    rewrite what saved workflows store. Venues may appear under several
    families (facets are axes, not partitions) and the unclaimed tail
    keeps every venue reachable in one scan."""
    archetypes = _load_archetypes()
    settings = _load_settings()
    entries = [RANDOM]
    claimed = set()
    for arch in archetypes.values():
        facets = set(arch["facets"])
        members = sorted(
            v for v, d in settings.items()
            if facets <= set(d.get("facet_tags", []))
        )
        if not members:
            continue  # a family that can't roll is noise in the list
        entries.append(arch["label"])
        entries.extend(members)
        claimed.update(members)
    return entries + sorted(v for v in settings if v not in claimed)


def _short_group(subject_label, venue_words):
    """Short in-sentence subject: the fragment register carried the venue
    as a compound-noun prefix ('salvage yard crew'); in a sentence the
    locative already says it. Falls back to the full label, de-articled."""
    label = subject_label.strip()
    low = venue_words.lower()
    if label.lower().startswith(low + " "):
        return "the " + label[len(low) + 1:]
    if label[:2].lower() in ("a ", "an "):
        return "the " + label[2:].lstrip()
    return "the " + label


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
                "pose": ("BOOLEAN", {"default": False,
                    "tooltip": "Append a posture phrase to each staged character (static stance register). The Scene Character Roller has the same toggle — if both fire, doubled cues are yours."}),
                "positioning": ("BOOLEAN", {"default": False,
                    "tooltip": "Stage the cast with placement templates — lateral/relational phrases per cast size ('on the near side of the frame, …'). Off (default) = no placement language; the renderer arranges."}),
                "include_setting": ("BOOLEAN", {"default": True,
                    "tooltip": "Emit the venue phrase ('In an arcane library') that opens the scene line. Off = no location language; the renderer places the scene. The venue still rolls — tone and composition still draw from it — only the text is gated."}),
                "include_context": ("BOOLEAN", {"default": True,
                    "tooltip": "Emit the situation clause (what the group is doing). Off = place and mood only. The situation still rolls — tone compatibility and composition bias still key off it; only the text is gated."}),
            },
            "optional": {
                **{
                f"character_{i}": ("STRING", {
                    "forceInput": True,
                    "tooltip": (
                        "Wire a character description. Default staging adds "
                        "no placement — enable the positioning toggle for "
                        "template staging. Soft cap: 4."
                        if i == 1 else
                        "Additional character. Leave unwired to drop."
                    ),
                })
                for i in range(1, 5)
                },
                "ambient": ("STRING", {"forceInput": True,
                    "tooltip": "Wire the Scene Ambient Activity output — background figures and activity, slotted into the scene line. Leave unwired for none."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = ("context_text", "render_prompt", "components_json", "seed_used")
    FUNCTION = "compose"
    CATEGORY = "SceneGen"

    def compose(self, genre, genre2, tone, setting, composition, seed, pose=False, positioning=False,
                include_setting=True, include_context=True, **kwargs):
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
        summary = tones[tone_key].get("summary") or tone_key
        flourish = _pick_flourish(_load_atmosphere(), situation, rng)

        chars = [kwargs.get(f"character_{i}") or "" for i in (1, 2, 3, 4)]
        staging = _stage_characters(chars, rng, pose=pose, positioning=positioning)
        ambient = (kwargs.get("ambient") or "").strip()

        # Whole-scene sentence assembly (2026-08-31): syntax carries the
        # relations a comma-pile can't — locative context, a subject doing
        # something over something, then a mood summary anchored by its
        # behavior clause. Off-limits stays structural: no era presumption,
        # no broken referents, no abstraction without a spine.
        # include_setting / include_context gate TEXT emission only — the
        # rolls above are untouched, so tone/composition keys stay stable.
        venue_words = chosen["name"].replace("_", " ")
        venue_art = "an" if venue_words[:1].lower() in "aeiou" else "a"
        locative = str(chosen.get("locative", "in")).capitalize()
        group = chosen.get("group") or _short_group(
            chosen["subject_label"], venue_words
        )
        verb = "are" if group.rstrip().endswith("s") else "is"

        text = situation["text"].strip()
        words = text.split()
        verbled = words[0].lower().endswith(("ing", "ed")) or (
            len(words) > 1
            and words[1].lower().endswith(("ing", "ed"))
            and words[0].lower() not in ("a", "an", "the")
        )
        if situation.get("role") == "aside":
            # second-subject scene event — its own absolute sentence, no
            # group clause: the stranger/crowd/train is the subject.
            body = text
        else:
            if verbled:
                act = text
            else:
                act = f"in {text}"  # NP event: light carrier keeps it grammatical
            body = f"{group} {verb} {act}"
        venue_phrase = f"{locative} {venue_art} {venue_words}"
        if include_setting and include_context:
            scene = f"{venue_phrase}, {body}"
        elif include_setting:
            scene = venue_phrase
        elif include_context:
            scene = body[:1].upper() + body[1:]
        else:
            scene = ""  # no scene sentence — a bare flourish would be an orphan
        if scene and flourish:
            scene = f"{scene}, {flourish}"
        sentences = [scene + "."] if scene else []
        mood = f"The mood is {summary}"
        if modifier:
            mood = f"{mood} — {modifier}"
        sentences.append(mood + ".")
        if staging:
            lead = staging[0].upper() + staging[1:]
            if not lead.rstrip().endswith((".", "!", "?")):
                lead += "."
            sentences.append(lead)
        if ambient:
            sentences.append(f"In the background, {ambient}.")
        context_text = " ".join(sentences)

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
            "tone_summary": summary,
            "group": group,
            "atmosphere": flourish,
            "characters_staged": staging,
            "ambient": ambient,
            "pose": pose,
            "positioning": positioning,
            "include_setting": include_setting,
            "include_context": include_context,
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
