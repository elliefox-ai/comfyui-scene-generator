"""
Scene Character Roller — the cast side of the scene context system.

Where the Picker/Composer stage *where people stand*, this node decides
*who the people are*: role concept + wardrobe family + face anchors,
assembled compositionally from tagged banks rather than flat pools.

Axes:
    Genre (historical / modern / sci_fi / fantasy, or 🎲 rolled ONCE per
        run and shared by the cast) gates the wardrobe families.
    Consistency (0..1) — per character, a loaded coin: heads inherits
        the cast's shared family + palette, tails rolls fresh. 0 = the
        old randomizer's chaos mode (every layer independent). 1 = one
        family, one palette; roles, faces and details still vary. A
        FIRM genre always binds rogue rolls to that genre's pool —
        mismatch happens *within* the era, never across it.
    Detail — low = wide-shot legible (face shape, hair, eyes, maybe one
        discriminating mark; outer layer + palette). high = the portrait
        ladder, sampled and never enumerated ("full detail doesn't mean
        listing each and every feature").
    Role — genre-agnostic social function (leader / warrior / healer /
        ...), the character-side analogue of the setting archetypes.
        Filters concept banks; falls back to the full bank on empty
        join. The role NAME stays portable (leader, not mayor); the
        genre flavor lives in the bank entries.

Names: free-text comma list, applied in order — "Abigail, a weathered
sea captain in a heavy oilskin coat". The name is a binding handle for
the renderer (the randomizer's `xxxx` substitution, promoted to a
field).

Pose / positioning toggles (default off): bake a posture / position
phrase into each character string. The scene nodes carry the same
toggles — if both fire somewhere, the doubled phrase is the user's
call. Sometimes the composition works itself out.

Banks live in scene_context/ — character_wardrobe.json (families:
genre tag, layer grammar, palettes, wear states, role-tagged concepts)
and character_features.json (faces, hair, eyes, marks, build,
demeanor, postures, positions). Expand the banks, not the code.

Outputs:
    character_1..4   wire into the Picker/Composer staging slots
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
    """Rolls a coherent cast: tagged wardrobe families, role concepts,
    sampled face anchors. Pure text — no renderer assumptions."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "genre": (GENRE_OPTIONS, {"default": RANDOM,
                    "tooltip": "🎲 rolls ONCE per run and the cast shares it (a max-consistency cast can't be a genre zoo). A firm genre binds every character — even rogue rolls stay within the era."}),
                "count": ("INT", {"default": 2, "min": 1, "max": 4,
                    "tooltip": "Cast size. Slots beyond count emit empty strings (staging drops them)."}),
                "consistency": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "0 = each character rolls independently (chaos mode). 1 = cast locks to one outfit family and one palette; roles and faces still vary. Firm genre + 0 = mismatched within the era (legal and intentional)."}),
                "detail": (["low", "high"], {"default": "low",
                    "tooltip": "low = wide-shot legible: outer layer + palette, face shape, hair, eyes, maybe one mark — enough to read at distance without pulling the render into a close-up. high = portrait ladder (layers, wear, face architecture, build, demeanor), sampled — never the whole list."}),
                "role": (_role_options(), {"default": "any",
                    "tooltip": "Genre-agnostic social function. Filters the concept banks; a family with no matching concepts falls back to its full bank."}),
                "names": ("STRING", {"default": "", "multiline": False,
                    "tooltip": "Optional. Comma-separated, applied in order: 'Abigail, Bernadette'. Prefixes each description — a binding handle that helps the renderer cohere details to a specific figure. Blank = no names."}),
                "pose": ("BOOLEAN", {"default": False,
                    "tooltip": "Bake a posture phrase into each character ('weight sunk into one hip'). Static stance register — no actions."}),
                "positioning": ("BOOLEAN", {"default": False,
                    "tooltip": "Bake a position phrase into each character ('on the near side of the frame'). The scene nodes have the same toggle — if both fire, doubled placement is on you."}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 2**32 - 1}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "INT")
    RETURN_NAMES = (
        "character_1", "character_2", "character_3", "character_4",
        "components_json", "seed_used",
    )
    FUNCTION = "roll"
    CATEGORY = "SceneGen"

    def roll(self, genre, count, consistency, detail, role, names,
             pose, positioning, seed):
        rng = random.Random(seed)
        families = _load_wardrobe()
        feats = _load_features()

        # Genre resolves ONCE per run — the cast shares the era.
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
        shared_id, shared = rng.choice(genre_pool)
        shared_palette = rng.choice(shared["palettes"])
        # Firm genre binds rogues to the era; 🎲 lets them cross it.
        rogue_pool = genre_pool if firm else list(families.items())

        name_list = [n.strip() for n in names.split(",") if n.strip()]
        used_concepts = set()
        chars, meta = [], []

        for i in range(count):
            if rng.random() < consistency:
                fam_id, fam, palette = shared_id, shared, shared_palette
            else:
                fam_id, fam = rng.choice(rogue_pool)
                palette = rng.choice(fam["palettes"])

            concepts = [
                c for c in fam["concepts"]
                if role == "any" or role in c.get("roles", [])
            ] or fam["concepts"]
            fresh = [c for c in concepts if c["text"] not in used_concepts]
            if not fresh:
                fresh = concepts  # tiny banks may repeat before they grow
            concept = rng.choice(fresh)
            used_concepts.add(concept["text"])

            segs = [concept["text"]]
            layers = fam["layers"]
            outer = rng.choice(layers["outer"])
            if detail == "high":
                if rng.random() < 0.6:
                    outer = f"{outer}, {rng.choice(fam['wear'])}"
                outfit = f"in {outer}"
                if rng.random() < 0.8:
                    outfit += f" over {rng.choice(layers['torso'])}"
                tails = []
                if rng.random() < 0.8:
                    tails.append(rng.choice(layers["legs"]))
                if rng.random() < 0.7:
                    tails.append(rng.choice(layers["feet"]))
                if rng.random() < 0.5:
                    tails.append(rng.choice(layers["head"]))
                if tails:
                    outfit += ", " + ", ".join(tails)
            else:
                outfit = f"in {outer}"
            segs += [outfit, palette]

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
            name = name_list[i] if i < len(name_list) else ""
            if name:
                text = f"{name}, {text}"

            chars.append(text)
            meta.append({
                "index": i + 1,
                "name": name,
                "concept": concept["text"],
                "roles": concept.get("roles", []),
                "family": fam_id,
                "palette": palette,
                "shared_family": fam_id == shared_id,
                "face": face_bits,
                "pose": posture,
                "position": position,
                "text": text,
            })

        components = {
            "genre": genre_resolved,
            "genre_random": genre == RANDOM,
            "shared_family": shared_id,
            "shared_palette": shared_palette,
            "count": count,
            "consistency": consistency,
            "detail": detail,
            "role": role,
            "seed": seed,
            "characters": meta,
        }
        while len(chars) < 4:
            chars.append("")
        return (
            chars[0], chars[1], chars[2], chars[3],
            json.dumps(components, ensure_ascii=False), seed,
        )


NODE_CLASS_MAPPINGS = {
    "SceneCharacterRoller": SceneCharacterRoller,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneCharacterRoller": "🎲 Scene Character Roller",
}
