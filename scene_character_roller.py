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
    Consistency (0..1) — how much this character honors the genre's
        substyle, per garment. 1 = full coherence: one outfit family
        head to toe, one palette, family concept. 0 = random character
        style: every piece rolls independently (a FIRM genre still
        binds pieces to the era — mismatch happens *within* it, never
        across it). Between = mostly-family with wandering pieces.
    Detail — low = wide-shot legible (face shape, hair, eyes, maybe
        one discriminating mark; outer layer + palette). high = the
        portrait ladder, sampled and never enumerated ("full detail
        doesn't mean listing each and every feature").
    Role — genre-agnostic social function (leader / warrior / healer /
        ...), the character-side analogue of the setting archetypes.
        Filters concept banks; falls back to the full bank on empty
        join. The role NAME stays portable (leader, not mayor); genre
        flavor lives in the bank entries.

Name: a single optional string — "Abigail, a weathered sea captain in
a heavy oilskin coat". A binding handle for the renderer (the
randomizer's `xxxx` substitution, promoted to a field).

Pose / positioning toggles (default off): bake a posture / position
phrase into the character string. The scene nodes carry the same
toggles — if both fire, the doubled phrase is the user's call.
Sometimes the composition works itself out.

Banks live in scene_context/ — character_wardrobe.json (families:
genre tag, layer grammar, palettes, wear states, role-tagged concepts)
and character_features.json (faces, hair, eyes, marks, build,
demeanor, postures, positions). Expand the banks, not the code.

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
except ImportError:  # standalone — test harness / direct exec
    from scene_context_node import (  # noqa: F811
        GENRE_OPTIONS,
        RANDOM,
        CONTEXT_DIR,
        _load_features,
    )

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
        for c in fam["concepts"]
        for r in c.get("roles", [])
    })
    return ["any"] + roles


class SceneCharacterRoller:
    """Rolls one character: tagged wardrobe family, role concept,
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
                    "tooltip": "low = wide-shot legible: outer layer + palette, face shape, hair, eyes, maybe one mark — enough to read at distance without pulling the render into a close-up. high = portrait ladder (layers, wear, face architecture, build, demeanor), sampled — never the whole list."}),
                "role": (_role_options(), {"default": "any",
                    "tooltip": "Genre-agnostic social function. Filters the concept banks; a family with no matching concepts falls back to its full bank."}),
                "name": ("STRING", {"default": "", "multiline": False,
                    "tooltip": "Optional. 'Abigail'. Prefixes the description — a binding handle that helps the renderer cohere details to this specific figure. Blank = no name."}),
                "pose": ("BOOLEAN", {"default": False,
                    "tooltip": "Bake a posture phrase into the character ('weight sunk into one hip'). Static stance register — no actions."}),
                "positioning": ("BOOLEAN", {"default": False,
                    "tooltip": "Bake a position phrase into the character ('on the near side of the frame'). The scene nodes have the same toggle — if both fire, doubled placement is on you."}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**32 - 1}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("character", "components_json", "seed_used")
    FUNCTION = "roll"
    CATEGORY = "SceneGen"

    def roll(self, genre, consistency, detail, role, name,
             pose, positioning, seed):
        rng = random.Random(seed)
        families = _load_wardrobe()
        feats = _load_features()

        if genre == RANDOM:
            genre_resolved = rng.choice(
                [g for g in GENRE_OPTIONS if g != RANDOM]
            )
            firm = False
        else:
            genre_resolved = genre
            firm = True

        genre_pool = [
            (fid, fam) for fid, fam in families.items()
            if fam["genre"] == genre_resolved
        ] or list(families.items())
        # The coherence TARGET: one family the slider pulls toward.
        target_id, target = rng.choice(genre_pool)
        # Where wandering pieces roam: the era if firm, everywhere if 🎲.
        roam = genre_pool if firm else list(families.items())

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

        segs = [concept["text"], outfit, palette]

        def maybe(pool_key, p, bucket):
            if rng.random() < p:
                bucket.append(rng.choice(feats[pool_key]))

        face_bits = []
        if detail == "high":
            maybe("face_shapes", 0.7, face_bits)
            maybe("hair", 0.9, face_bits)
            maybe("eyes", 0.8, face_bits)
            maybe("marks", 0.6, face_bits)
            if rng.random() < 0.75:
                face_bits.append(rng.choice(feats["face_detail"]))
                if rng.random() < 0.35:
                    face_bits.append(rng.choice(feats["face_detail"]))
            maybe("build", 0.85, face_bits)
            maybe("demeanor", 0.7, face_bits)
        else:
            # wide-shot legible: shape, hair, eyes, maybe one mark
            maybe("face_shapes", 0.9, face_bits)
            maybe("hair", 0.9, face_bits)
            maybe("eyes", 0.85, face_bits)
            maybe("marks", 0.45, face_bits)
        segs += face_bits

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
