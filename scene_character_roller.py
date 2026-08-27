"""
Scene Character Roller — one node, one character.

Add a node per figure. Where the Picker/Composer stage *where people
stand*, this node decides *who one person is*: role concept + wardrobe
family + face anchors, assembled compositionally from tagged banks
rather than flat pools. Wire its output into a Picker/Composer
character slot (or any text prompt).

Axes:
    Genre (historical / modern / sci_fi / fantasy, or 🎲) gates the
        wardrobe families. Each node resolves its own — set firm
        genres across the cast when the era must be shared (🎲 per
        node rolls independently: cross-era casts by design, or wire
        a shared source once one exists).
    Identity (age / sex / race, each 🎲 by default) — one stated
        identity per figure, stated ONCE in the identity phrase
        ("an older Black woman") and never repeated from the banks.
        🎲 rolls the axis, then weights every feature draw toward the
        rolled value — soft affinity, never a filter: tagged matches
        draw 4×, untagged entries 2×, mismatches 1×. Consistent but
        individually exclusive — the tiny randomization that lets a
        fixed "older" still draw the occasional unlined brow.
    Consistency (0..1) — how much this character honors the genre's
        substyle, per garment. 1 = full coherence: one outfit family
        head to toe, one palette, family concept. 0 = random character
        style: every piece rolls independently (a FIRM genre still
        binds pieces to the era — mismatch happens *within* it, never
        across it). Between = mostly-family with wandering pieces.
    Fallback law — a firm genre with zero wardrobe families never
        borrows another era's clothes: it drops to the genre-less
        era-neutral basics bank and warns on console. Consent to
        cross-era mismatch belongs to the consistency dial, never
        the system. Genre-less families never join 🎲 draws.
    Detail — low = wide-shot legible (identity phrase, outer layer +
        palette, face shape, hair, eyes, maybe one mark). high = the
        portrait ladder plus a complexion phrase, sampled and never
        enumerated ("full detail doesn't mean listing each and every
        feature").
    Role — genre-agnostic social function (leader / warrior / healer /
        ...), the character-side analogue of the setting archetypes.
        Filters concept banks; falls back to the full bank on empty
        join. The role NAME stays portable (leader, not mayor); genre
        flavor lives in the bank entries.

Name: a single optional string — "Abigail, an older white woman, a
weathered sea captain in a heavy oilskin coat". A binding handle for
the renderer (the randomizer's `xxxx` substitution, promoted to a
field).

Pose / positioning toggles (default off): bake a posture / position
phrase into the character string. The scene nodes carry the same
toggles — if both fire, the doubled phrase is the user's call.
Sometimes the composition works itself out.

Banks live in scene_context/ — character_wardrobe.json (families:
genre tag, layer grammar, palettes, wear states, role-tagged concepts)
and character_features.json (identity-tagged faces, hair, eyes, marks,
build, demeanor; postures/positions; race-keyed complexion). Expand
the banks, not the code.

Outputs:
    character        one description string
    components_json  everything resolved, for remixing downstream
    seed_used        pass-through so samplers can share the roll
"""

import json
import os
import random

try:  # package context — how ComfyUI loads custom node packs
    from .scene_context_node import (
        GENRE_OPTIONS,
        RANDOM,
        CONTEXT_DIR,
        _load_features,
    )
    from .scene_tags import genre_with_parents, load_tags
except ImportError:  # standalone — test harness / direct exec
    from scene_context_node import (  # noqa: F811
        GENRE_OPTIONS,
        RANDOM,
        CONTEXT_DIR,
        _load_features,
    )
    from scene_tags import genre_with_parents, load_tags  # noqa: F811

WARDROBE_PATH = os.path.join(CONTEXT_DIR, "character_wardrobe.json")

_CACHE = {"wardrobe": None}


def _load_wardrobe():
    if _CACHE["wardrobe"] is None:
        with open(WARDROBE_PATH, encoding="utf-8") as f:
            _CACHE["wardrobe"] = json.load(f)["families"]
    return _CACHE["wardrobe"]


def _role_options():
    roles = sorted({
        r
        for fam in _load_wardrobe().values()
        if fam.get("genre")  # fallback-only families stay invisible
        for c in fam["concepts"]
        for r in c.get("roles", [])
    })
    return ["any"] + roles


_FALLBACK_WARNED = set()


def _warn_fallback(genre):
    """One console line per genre per process. Broken data should
    be visible, not silent — but it needn't be noisy."""
    if genre not in _FALLBACK_WARNED:
        _FALLBACK_WARNED.add(genre)
        print(
            f"[scene-gen] character roller: no wardrobe families for "
            f"'{genre}' — using the era-neutral fallback bank "
            f"(restore the genre's families in character_wardrobe.json)"
        )


# --- Identity -----------------------------------------------------------

AGE_OPTIONS = [RANDOM, "young adult", "middle-aged", "older"]
SEX_OPTIONS = [RANDOM, "female", "male"]
RACE_OPTIONS = [
    RANDOM, "white", "black", "east_asian", "south_asian",
    "latino", "middle_eastern", "indigenous",
]

# Dropdown vocabulary -> descriptive register. Stated once, never raw.
_AGE_PHRASE = {"young adult": "young", "middle-aged": "middle-aged", "older": "older"}
_SEX_PHRASE = {"female": "woman", "male": "man"}
_RACE_PHRASE = {
    "white": "white", "black": "Black", "east_asian": "East Asian",
    "south_asian": "South Asian", "latino": "Latino",
    "middle_eastern": "Middle Eastern", "indigenous": "Indigenous",
}

IDENTITY_AXES = ("age", "sex", "race")


def _resolve_axis(value, options, rng):
    """🎲 rolls this axis; a fixed value passes through untouched."""
    if value == RANDOM:
        return rng.choice([o for o in options if o != RANDOM]), True
    return value, False


def _identity_phrase(identity):
    parts = [
        _AGE_PHRASE[identity["age"]],
        _RACE_PHRASE[identity["race"]],
        _SEX_PHRASE[identity["sex"]],
    ]
    article = "an" if parts[0][0].lower() in "aeiou" else "a"
    return f"{article} {' '.join(parts)}"


# Historical spellings → canonical axis values (AGE_OPTIONS etc.),
# single-sourced from the tag registry (tags.json "_aliases"). Add no
# new ones — normalize the data instead. Origin: "age": "young" never
# matched identity "young adult", inverting the affinity (tagged drew
# at HALF the untagged rate) — found live 2026-08-22.
_TAG_ALIAS = dict(load_tags().get("_aliases", {}).get("age", {}))

# Identity dropdowns mirror the registry — membership parity, not
# display order (order is free; vocabulary is not).
for _opts, _ns in (
    (AGE_OPTIONS[1:], "identity_age"),
    (SEX_OPTIONS[1:], "identity_sex"),
    (RACE_OPTIONS[1:], "identity_race"),
):
    if set(_opts) != set(load_tags()[_ns]):
        raise ValueError(
            f"scene_character_roller: {_ns} options don't match "
            f"tags.json (roller: {sorted(_opts)}; "
            f"registry: {sorted(load_tags()[_ns])})")


def _weighted(pool, identity, rng, w_match=4, w_untagged=2, w_mismatch=1):
    """Soft-affinity draw: the stated identity WEIGHTS the pool, it
    never filters it. Match 4× / untagged 2× / mismatch 1×, multiplied
    across axes — consistent, but individually exclusive details stay
    reachable. That reachability is the tiny randomization."""
    weights = []
    for entry in pool:
        w = 1.0
        for axis in IDENTITY_AXES:
            tag = entry.get(axis)
            if isinstance(tag, str):
                tag = _TAG_ALIAS.get(tag, tag)
            if tag is None:
                w *= w_untagged
            elif isinstance(tag, dict):
                # Dict tag = explicit per-value multipliers
                # ({"east_asian": 3}) — races not listed draw at 1×,
                # the mismatch floor: possible, just rarer. Soft
                # affinity still, never a filter.
                w *= tag.get(identity[axis], 1)
            elif tag == identity[axis]:
                w *= w_match
            else:
                w *= w_mismatch
        weights.append(w)
    return rng.choices(pool, weights=weights, k=1)[0]


class SceneCharacterRoller:
    """Rolls one character: identity phrase, tagged wardrobe family,
    sampled face anchors. Pure text — no renderer assumptions."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "genre": (GENRE_OPTIONS, {"default": RANDOM,
                    "tooltip": "🎲 rolls this character's era independently. For a shared-era cast, set the same firm genre on every roller node (a shared source input is the parked next step). A firm genre binds every draw to that era's families."}),
                "consistency": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "How much this character honors the genre's substyle, garment by garment. 1 = full coherence: one outfit family head to toe, one palette. 0 = random character style: every piece rolls independently (firm genre keeps the mismatch within the era). Between = mostly-family with wandering pieces."}),
                "detail": (["low", "high"], {"default": "low",
                    "tooltip": "low = wide-shot legible: identity phrase, outer layer + palette, face shape, hair, eyes, maybe one mark — enough to read at distance without pulling the render into a close-up. high = portrait ladder (layers, wear, face architecture, complexion, build, demeanor), sampled — never the whole list."}),
                "role": (_role_options(), {"default": "any",
                    "tooltip": "Genre-agnostic social function. Filters the concept banks; a family with no matching concepts falls back to its full bank."}),
                "name": ("STRING", {"default": "", "multiline": False,
                    "tooltip": "Optional. 'Abigail'. Prefixes the description — a binding handle that helps the renderer cohere details to this specific figure. Blank = no name."}),
                "pose": ("BOOLEAN", {"default": False,
                    "tooltip": "Bake a posture phrase into the character ('weight sunk into one hip'). Static stance register — no actions."}),
                "positioning": ("BOOLEAN", {"default": False,
                    "tooltip": "Bake a position phrase into the character ('on the near side of the frame'). The scene nodes have the same toggle — if both fire, doubled placement is on you."}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**32 - 1}),
                "age": (AGE_OPTIONS, {"default": RANDOM,
                    "tooltip": "🎲 rolls this figure's age, then weights every feature draw toward it (soft affinity — never a filter; the occasional age-mismatched detail is the point). Stated once in the identity phrase: 'an older…'. Fixed values weight the pools the same way."}),
                "sex": (SEX_OPTIONS, {"default": RANDOM,
                    "tooltip": "🎲 rolls this figure's sex and weights feature draws toward it. Stated once in the identity phrase ('…woman' / '…man'). The wardrobe banks stay unisex — sex never gates garments."}),
                "race": (RACE_OPTIONS, {"default": RANDOM,
                    "tooltip": "Broad-stroke, descriptive register. 🎲 rolls this figure's race, weights feature draws toward it, and (at detail=high) adds a complexion phrase keyed to it. Dropdown values never enter the string raw — vocabulary maps through phrase banks, stated once."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("character", "components_json", "seed_used")
    FUNCTION = "roll"
    CATEGORY = "SceneGen"

    def roll(self, genre, consistency, detail, role, name,
             pose, positioning, seed, age, sex, race):
        rng = random.Random(seed)
        families = _load_wardrobe()
        feats = _load_features()

        # Draw order (documented for stability): identity first — who
        # before when — then genre, then everything downstream.
        age_res, age_rand = _resolve_axis(age, AGE_OPTIONS, rng)
        sex_res, sex_rand = _resolve_axis(sex, SEX_OPTIONS, rng)
        race_res, race_rand = _resolve_axis(race, RACE_OPTIONS, rng)
        identity = {"age": age_res, "sex": sex_res, "race": race_res}
        identity_phrase = _identity_phrase(identity)

        if genre == RANDOM:
            genre_resolved = rng.choice(
                [g for g in GENRE_OPTIONS if g != RANDOM]
            )
            firm = False
        else:
            genre_resolved = genre
            firm = True

        # Parent ladder: a subgenre inherits its parents' families
        # (western -> historical's frontier + age_of_sail). Fallback
        # law still holds: a firm genre with no families up the chain
        # never borrows another era's clothes — it drops to the
        # era-neutral bank (genre-less families) and warns.
        genre_ids = genre_with_parents(genre_resolved)
        genre_pool = [
            (fid, fam) for fid, fam in families.items()
            if fam.get("genre") in genre_ids
        ]
        if not genre_pool:
            _warn_fallback(genre_resolved)
            genre_pool = [
                (fid, fam) for fid, fam in families.items()
                if not fam.get("genre")
            ]
            if not genre_pool:
                raise ValueError(
                    "wardrobe has no era-neutral fallback family — "
                    "character_wardrobe.json is missing its "
                    "genre-less basics bank"
                )
        # The coherence TARGET: one family the slider pulls toward.
        target_id, target = rng.choice(genre_pool)
        # Where wandering pieces roam: the era if firm, genre'd
        # families only if 🎲 — the fallback bank never roams.
        roam = genre_pool if firm else [
            (fid, fam) for fid, fam in families.items()
            if fam.get("genre")
        ]

        def layer_draw(layer_key):
            """One garment: honor the target family, or roll from the
            wider pool. Every draw flips its own coin — that's the
            dial: at 1 all honor (head-to-toe family), at 0 all roam
            (fully independent pieces)."""
            if rng.random() < consistency:
                return rng.choice(target["layers"][layer_key]), target_id
            fid, fam = rng.choice(roam)
            return rng.choice(fam["layers"][layer_key]), fid

        def concepts_of(fam):
            cs = [
                c for c in fam["concepts"]
                if role == "any" or role in c.get("roles", [])
            ]
            return cs or fam["concepts"]

        # Concept: same coin as the garments.
        if rng.random() < consistency:
            concept = rng.choice(concepts_of(target))
            concept_src = target_id
        else:
            concept_src, fam = rng.choice(roam)
            concept = rng.choice(concepts_of(fam))

        sources = {}
        outer, src = layer_draw("outer")
        sources["outer"] = src
        if detail == "high":
            if rng.random() < 0.6:
                # Wear state follows the garment it describes.
                outer = f"{outer}, {rng.choice(families[src]['wear'])}"
            outfit = f"in {outer}"
            if rng.random() < 0.8:
                piece, sources["torso"] = layer_draw("torso")
                outfit += f" over {piece}"
            tails = []
            if rng.random() < 0.8:
                piece, sources["legs"] = layer_draw("legs")
                tails.append(piece)
            if rng.random() < 0.7:
                piece, sources["feet"] = layer_draw("feet")
                tails.append(piece)
            if rng.random() < 0.5:
                piece, sources["head"] = layer_draw("head")
                tails.append(piece)
            if tails:
                outfit += ", " + ", ".join(tails)
        else:
            outfit = f"in {outer}"

        if rng.random() < consistency:
            palette, pal_src = rng.choice(target["palettes"]), target_id
        else:
            pal_src, fam = rng.choice(roam)
            palette = rng.choice(fam["palettes"])
        sources["palette"] = pal_src

        compose_cfg = feats.get("_compose", {})

        def wmaybe(pool_key, p, bucket):
            """Sample one feature: identity-weighted soft draw — or,
            when the bank has a _compose group, a composed phrase
            built from its slots (chance decides compose vs flat)."""
            if rng.random() < p:
                cfg = compose_cfg.get(pool_key)
                if cfg and rng.random() < cfg.get("chance", 0.5):
                    joiner = cfg.get("joiner", " ")
                    parts = []
                    for slot in cfg["slots"]:
                        if slot.get("optional") and rng.random() > slot["optional"]:
                            continue
                        opt = _weighted(slot["options"], identity, rng)
                        parts.append(opt["text"] if isinstance(opt, dict) else opt)
                    if not parts:
                        # Every optional slot sat out — anchor on the
                        # first slot so the phrase never degenerates to
                        # the bare suffix ("hair", "eyes").
                        anchor = _weighted(cfg["slots"][0]["options"],
                                           identity, rng)
                        parts.append(anchor["text"]
                                     if isinstance(anchor, dict) else anchor)
                    if len(parts) > 1 and len(set(parts)) == 1:
                        # All slots drew the same word — break the echo
                        # ("easygoing but easygoing") by re-rolling the last.
                        for _ in range(5):
                            opt = _weighted(cfg["slots"][-1]["options"],
                                            identity, rng)
                            parts[-1] = opt["text"] if isinstance(opt, dict) else opt
                            if len(set(parts)) > 1:
                                break
                    phrase = joiner.join(parts)
                    if cfg.get("suffix"):
                        phrase = f"{phrase} {cfg['suffix']}"
                    bucket.append(phrase)
                else:
                    entry = _weighted(feats[pool_key], identity, rng)
                    bucket.append(entry["text"] if isinstance(entry, dict) else entry)

        face_bits = []
        if detail == "high":
            wmaybe("face_shapes", 0.7, face_bits)
            wmaybe("hair", 0.9, face_bits)
            wmaybe("eyes", 0.8, face_bits)
            if rng.random() < 0.75:
                # Complexion: the one hard-keyed draw — race selects its
                # own phrase bank, descriptive register, never raw.
                face_bits.append(rng.choice(feats["complexion"][race_res]))
            wmaybe("marks", 0.6, face_bits)
            if rng.random() < 0.75:
                wmaybe("face_detail", 1.0, face_bits)
                if rng.random() < 0.35:
                    wmaybe("face_detail", 1.0, face_bits)
            wmaybe("build", 0.85, face_bits)
            wmaybe("demeanor", 0.7, face_bits)
        else:
            # wide-shot legible: shape, hair, eyes, maybe one mark
            wmaybe("face_shapes", 0.9, face_bits)
            wmaybe("hair", 0.9, face_bits)
            wmaybe("eyes", 0.85, face_bits)
            wmaybe("marks", 0.45, face_bits)

        segs = [identity_phrase, concept["text"], outfit, palette] + face_bits

        posture = rng.choice(feats["postures"]) if pose else ""
        position = rng.choice(feats["positions"]) if positioning else ""
        if posture:
            segs.append(posture)
        if position:
            segs.append(position)

        text = ", ".join(segs)
        name = (name or "").strip()
        if name:
            text = f"{name}, {text}"

        components = {
            "genre": genre_resolved,
            "genre_random": genre == RANDOM,
            "identity": {
                "age": age_res, "sex": sex_res, "race": race_res,
                "age_random": age_rand, "sex_random": sex_rand,
                "race_random": race_rand,
                "phrase": identity_phrase,
            },
            "target_family": target_id,
            "consistency": consistency,
            "detail": detail,
            "role": role,
            "name": name,
            "concept": concept["text"],
            "concept_family": concept_src,
            "roles": concept.get("roles", []),
            "palette": palette,
            "palette_family": pal_src,
            "outfit_sources": sources,
            "face": face_bits,
            "pose": posture,
            "position": position,
            "seed": seed,
            "text": text,
        }
        return (text, json.dumps(components, ensure_ascii=False), seed)


NODE_CLASS_MAPPINGS = {
    "SceneCharacterRoller": SceneCharacterRoller,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneCharacterRoller": "🎲 Scene Character Roller",
}
