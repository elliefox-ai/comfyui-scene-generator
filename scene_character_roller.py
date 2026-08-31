"""
Scene Character Roller — one node, one character.

Add a node per figure. Where the Picker/Composer stage *where people
stand*, this node decides *who one person is*: persona + wardrobe
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
    Detail (split axes) — face_detail gates the face ladder,
        body_detail the body. Face: low = wide-shot legible (shape,
        hair, eyes, maybe a mark); high = the portrait ladder — eyes,
        nose, mouth, jaw, cheekbones, brow, ears sampled under a
        phrase budget (~6 face phrases per character), never
        enumerated. Body: minimal = portrait companion — one
        guaranteed build word for proportions, single outer garment,
        no ladder; low = wide-shot legible; high = the garment ladder
        plus build (high adds physique children — chest/legs/arms, soft-weighted on the drawn archetype). Demeanor rides whichever axis is high. ("Full
        detail doesn't mean listing each and every feature.")
    Persona (v2) — closed set of ten (warrior / worker / scholar /
        healer / leader / drifter / athlete / caregiver / charmer /
        gala) or "any". Weights the draw — wardrobe families,
        garments, wear states, build — via multipliers in
        personas.json. Soft affinity, never a lock. official is
        retired (split leader/worker, Alexander 2026-08-30).
    Character register — none (baseline) / authentic / pulp /
        costume / cartoon (+ random). What the character IS in the
        frame: a direct identification sentence rides second in the
        sheet, plus multipliers over wear and marks, the persona's
        uniform-look coin (authentic reads it as UNIFORM — flat,
        utilitarian — not costume), and per-family wear overrides.
        All data lives in scene_context/character_registers.json.

Name: a single optional string — "Abigail, an older white woman, a
weathered sea captain in a heavy oilskin coat". A binding handle for
the renderer (the randomizer's `xxxx` substitution, promoted to a
field).

Pose / positioning toggles (default off): bake a posture / position
phrase into the character string. The scene nodes carry the same
toggles — if both fire, the doubled phrase is the user's call.
Sometimes the composition works itself out.

Banks live in scene_context/ — character_wardrobe.json (families:
genre tag, layer grammar, palettes, wear states), personas.json (the
persona weight table — the v2 role surface) and
character_features.json (identity-tagged faces, hair, eyes, nose,
mouth, jaw, cheekbones, brow, ears, marks, build + physique children (torso/legs/arms), demeanor;
postures/positions; race-keyed complexion). Hair is modular —
'hair_v2' (length × color × gated sections) assembles into one
sentence when hair_mode='modular'; the legacy pool + compose spec
stay reachable via 'legacy'. Expand
the banks, not the code.

Outputs:
    character        one description string
    components_json  everything resolved, for remixing downstream
    seed_used        pass-through so samplers can share the roll
"""

import json
import os
import random
import re

try:  # package context — how ComfyUI loads custom node packs
    from .scene_context_node import (
        GENRE_OPTIONS,
        RANDOM,
        CONTEXT_DIR,
        _load_features,
    )
    from .scene_tags import genre_with_parents, load_tags
    from .scene_wardrobe_heat import (
        FOCUS_WEIGHTS, archetype_for, heat_pool, posture_pool,
            is_short_hem,
        legwear_pool,
)
except ImportError:  # standalone — test harness / direct exec
    from scene_context_node import (  # noqa: F811
        GENRE_OPTIONS,
        RANDOM,
        CONTEXT_DIR,
        _load_features,
    )
    from scene_tags import genre_with_parents, load_tags  # noqa: F811
    from scene_wardrobe_heat import (  # noqa: F811
        FOCUS_WEIGHTS, archetype_for, heat_pool, posture_pool,
      is_short_hem,
  legwear_pool,
)

WARDROBE_PATH = os.path.join(CONTEXT_DIR, "character_wardrobe.json")

_CACHE = {"wardrobe": None}


def _load_wardrobe():
    if _CACHE["wardrobe"] is None:
        with open(WARDROBE_PATH, encoding="utf-8") as f:
            _CACHE["wardrobe"] = json.load(f)["families"]
    return _CACHE["wardrobe"]


_COSTUME_CACHE = {}


def _load_costumes():
    """Occupation costume table (roles + outfits). Missing file or
    bad JSON degrades to an empty table — the feature is off."""
    if "d" not in _COSTUME_CACHE:
        path = os.path.join(CONTEXT_DIR, "occupation_costumes.json")
        try:
            with open(path, encoding="utf-8") as f:
                _COSTUME_CACHE["d"] = json.load(f)
        except (OSError, ValueError):
            _COSTUME_CACHE["d"] = {"roles": [], "costumes": {}}
    return _COSTUME_CACHE["d"]


def _costume_for(role):
    return _load_costumes().get("costumes", {}).get(role)


_PERSONAS_CACHE = {}


def _load_personas():
    """Persona weight table (v2). Required data — a missing or broken
    file is a hard error: personas ARE the role surface now."""
    if "d" not in _PERSONAS_CACHE:
        path = os.path.join(CONTEXT_DIR, "personas.json")
        with open(path, encoding="utf-8") as f:
            _PERSONAS_CACHE["d"] = json.load(f)
    return _PERSONAS_CACHE["d"].get("personas", {})


def _role_options():
    return ["any"] + sorted(_load_personas())


REGISTER_OPTIONS = ["random", "none", "authentic", "pulp", "costume",
                    "cartoon"]
# Character register (Alexander, 2026-08-31): what the character IS
# in the frame. Sentences, wear/marks tilts, the uniform-look coin
# and per-family wear overrides live in
# scene_context/character_registers.json — data, not code. The old
# authenticity dial maps documentary->authentic, stylized->costume,
# cinematic->none.
_REGISTER_PATH = os.path.join(CONTEXT_DIR, "character_registers.json")
_REG_CACHE = {"data": None}


def _load_registers():
    if _REG_CACHE["data"] is None:
        with open(_REGISTER_PATH, encoding="utf-8") as f:
            _REG_CACHE["data"] = json.load(f)["registers"]
    return _REG_CACHE["data"]

# Coarse persona intents -> real bank vocabulary. Seeded judgment
# calls, same status as the personas.json weights: refine against
# draws, don't harden into law.
_WEAR_SYNONYMS = {
    "worn": ["worn", "frayed", "patched", "mended", "faded", "creased",
             "distressed", "danced-in", "pilled", "shrunken", "stained",
             "dust", "sun-", "salt-", "tar-", "scorched", "cracked",
             "mud-", "smoke", "weather", "tape", "wire", "faction"],
    "hard-used": ["grease", "held together", "paint-flecked",
                  "dust-caked", "tar-spotted"],
    "pristine": ["brand new", "crisp", "pressed", "immaculate",
                 "well-kept", "wax-polished", "well-oiled", "dust-sealed"],
    "sweat-worn": ["danced-in", "sun-faded", "pilled"],
    "worn-comfortable": ["well-loved", "lightly creased", "soft"],
}
_BUILD_SYNONYMS = {
    "broad_build": ["broad-framed", "broad-hipped", "hulking", "muscular",
                    "sturdy"],
    "stocky_build": ["stocky", "husky", "blocky", "heavyset"],
    "athletic_build": ["athletic", "lithe", "sinewy", "wiry", "rangy"],
    "soft_build": ["soft-bodied", "heavyset", "dumpy"],
    "lean_build": ["lean", "lanky", "willowy", "lithe", "scrawny",
                   "slight-framed"],
}


def _lean_w(texts, leans, synonyms):
    """Per-entry multipliers for plain rng.choices pools: each lean key
    matches through its synonym fragments (case-insensitive substring);
    a key contributes at most once per entry. Unmatched = 1.0. With no
    leans, callers skip weighting entirely."""
    ws = []
    for t in texts:
        lt = (t if isinstance(t, str) else str(t.get("text", ""))).lower()
        w = 1.0
        for key, m in leans.items():
            for frag in synonyms.get(key, (key,)):
                if frag in lt:
                    w *= m
                    break
        ws.append(w)
    return ws


def _scaled_pool(pool, leans, synonyms):
    """Same lean law for _weighted pools: clone entries, scale their
    static 'weight' field — the identity affinity multiplies on top
    unchanged."""
    if not leans:
        return pool
    out = []
    for e in pool:
        if isinstance(e, dict):
            e = dict(e)
            lt = str(e.get("text", "")).lower()
            m = 1.0
            for key, lm in leans.items():
                for frag in synonyms.get(key, (key,)):
                    if frag in lt:
                        m *= lm
                        break
            if m != 1.0:
                e["weight"] = e.get("weight", 1) * m
        out.append(e)
    return out


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


_GRAMMAR = re.compile(r"\{([^{}|]*\|[^{}]*)\}")


def _expand(tpl, rng):
    """Inline variant grammar for wardrobe strings: {a|b} picks one
    variant; an empty option ('{|a}' / '{a|}') makes the group
    optional. Nested groups resolve innermost-first. Weight a choice
    by duplicating it ({a|a|b}). Groups without '|' pass through
    untouched, so placeholders like {name} are never eaten. Leftmost
    innermost draw order -- stable for a given seed. Whitespace left
    by empty picks is collapsed."""
    if not isinstance(tpl, str):
        return tpl
    while True:
        m = _GRAMMAR.search(tpl)
        if not m:
            return " ".join(tpl.split())
        pick = rng.choice(m.group(1).split("|"))
        tpl = tpl[:m.start()] + pick + tpl[m.end():]


def _article(t):
    return "an" if t[:1].lower() in "aeiou" else "a"


def _roll_hair(feats, identity, rng, name=""):
    """Modular hair sentence: Alexander's facedetailer sections
    (2026-08-29) — length x color x bangs x styled x parting x
    texture x hairline x grooming x accessory — with explicit
    per-option weights (no dilution strings) and length-class gating
    (ties/braids/buns need long/medium/undercut; shorn closes
    everything but color and hairline). Returns (sentence, details);
    sentence is '' when the roll closes out. Runs when the node's
    hair_mode is 'modular'; the legacy pool + compose spec remain
    for 'legacy'."""
    spec = feats.get("hair_v2")
    if not spec:
        return "", {}
    if rng.random() > spec.get("chance", 0.97):
        return "", {}
    # Gender balance: class-level multipliers (spec
    # length_class_by_sex) shift the whole distribution per sex —
    # buzz/undercut ride mostly on men, long and pixie lean female.
    # Soft affinity still — multipliers, never a filter.
    _sw = spec.get("length_class_by_sex", {}).get(
        identity.get("sex", ""), {})
    ln = _weighted([dict(o, weight=o.get("weight", 1)
                         * _sw.get(o.get("class", ""), 1.0))
                    for o in spec["length"]["options"]], identity, rng)
    ltext = _expand(ln.get("text", ""), rng)
    lclass = ln.get("class", "long")
    lform = ln.get("form", "modifier")
    # Race balance: family-level multipliers (spec
    # color_family_by_race) — same pattern as the sex table. Red
    # and blonde stay reachable on every race, just rarer where
    # they read as dyed. Soft affinity, never a filter.
    _rw = spec.get("color_family_by_race", {}).get(
        identity.get("race", ""), {})
    fam = _weighted([dict(f, weight=f.get("weight", 1)
                          * _rw.get(f.get("name", ""), 1.0))
                     for f in spec["color"]["families"]], identity, rng)
    shade = _weighted(fam["options"], identity, rng)
    stext = _expand(shade.get("text", ""), rng)
    sform = shade.get("form", "adj")
    if lform == "noun":
        if sform == "phrase":
            core = f"{ltext} with {stext}"
        else:
            core = ln["emission"].replace("{color}", stext)
    elif sform == "phrase":
        core = f"{ltext} hair with {stext}"
    else:
        core = f"{ltext} {stext} hair"
    tail = []
    drawn = []
    for sec in spec.get("sections", []):
        if rng.random() > sec.get("chance", 0.3):
            continue
        classes = sec.get("classes")
        if classes and lclass not in classes:
            continue
        pool = []
        for pd in sec.get("pools", [{"options": sec.get("options", [])}]):
            pc = pd.get("classes")
            if pc and lclass not in pc:
                continue
            pool.extend(pd.get("options", []))
        if not pool:
            continue
        pick = _weighted(pool, identity, rng)
        text = _expand(pick.get("text", ""), rng)
        lead = sec.get("lead")
        if lead == "styled":
            art = "" if pick.get("article") is False else _article(text) + " "
            frag = f"styled in {art}{text}"
        elif lead == "wearing":
            frag = f"wearing {text}"
        else:
            frag = text
        tail.append(frag)
        drawn.append(f"{sec['name']}: {text}")
    stem = f"{name} has" if name else "They have"
    sent = f"{stem} {core}"
    if tail:
        joiner = " " if tail[0].startswith("with ") else ", "
        sent += joiner + tail[0]
        sent += "".join(", " + t for t in tail[1:])
    details = {
        "length": ltext, "class": lclass, "color": stext,
        "sections": drawn, "sentence": sent + ".",
    }
    return sent + ".", details


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
        # Static option weight (hair_v2 shapes frequencies with it;
        # banks without "weight" keys are unaffected).
        w *= entry.get("weight", 1)
        # Axes iterated: the identity axes PLUS any extra context
        # axes the caller injected (children pass the drawn build
        # archetype as identity['build'] — tags on that axis weight
        # the same as age/sex/race). Face/parent draws pass plain
        # identity, so their axes — and their outputs — are
        # unchanged.
        for axis in sorted(set(IDENTITY_AXES) | set(identity)):
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
                "face_detail": (["low", "high"], {"default": "low",
                    "tooltip": "Face ladder. low = wide-shot legible: face shape, hair, eyes, maybe a mark — reads at distance. high = portrait ladder: complexion, nose, mouth, jaw, cheekbones, brow, ears sampled under a phrase budget (~6 face phrases, never the whole list)."}),
                "hair_mode": (["modular", "legacy"], {"default": "modular",
                    "tooltip": "Modular: hair composed from facedetailer-style sections (length × color × bangs × style × parting × texture × hairline × grooming × accessory) into one sentence — thousands of coherent combinations, gated by length class (ties need length; shorn closes sections; pixie up, buzz/undercut rare by measurement). Legacy: the old static pool + slot compose. Same seed differs across modes (draw order changes)."}),
                "body_detail": (["minimal", "low", "high"], {"default": "low",
                    "tooltip": "Body depth. minimal = portrait companion: one guaranteed build word for proportions, single outer garment, no layers. low = wide-shot: outer garment + palette, build usually. high = garment ladder (wear state, layered pieces) + build. Pair with face_detail=high for closeup portraits."}),
                "emphasis": (["off", "low", "high"], {"default": "off",
                    "tooltip": "Corroboration dial for the build — the trait diffusion under-reads. low = one independent restatement rides in the body sentence ('a lean build, no wasted weight on them'); high = two. Adds angles, never intensifiers: 'very lean' does nothing, a second physical observation does. Same seed + off reproduces the plain register exactly."}),
                "heat": (["off", "suggestive", "flirty", "smoldering"], {"default": "off",
                    "tooltip": "Heat dial — silhouette & reveal only, never color or material. off = the plain register (zero extra draws; same seed, same string). suggestive = one garment gains a fit-and-fabric state ('pulled taut across the chest'). flirty = one explicit reveal ('cropped above the navel'). smoldering = two garments at the hottest states — steamy-but-clothed by design (FlatDeep-safe). With pose on, the posture draw comes from the heat register instead. Needs garments to touch: pair with body_detail=high for the full effect."}),
                "character_register": (REGISTER_OPTIONS, {"default": "none",
                    "tooltip": "🎲 What this character IS in the frame — the sheet says it in words and the dice follow. none = fair dice, silent sheet (the old cinematic). authentic = the real thing — wear up, marks up, but fine families (evening, office) keep their clothes; a role's full-rig reads as UNIFORM. pulp = romanticized — scars become backstory, swagger in every seam. costume = a person in costume — pristine, props, reads as COSTUME. cartoon = drawn for Saturday morning — pristine, marks rare, one exaggeration clause (known ceiling: sheet words can't bend the render style). random = rolls a mode per character, so mixed-register crowds come free. Retired dial mapping: documentary→authentic, stylized→costume, cinematic→none. Old seeds die."}),
                "body_type": (["random"] + [e["text"] for e in _load_features()["build"]],
                    {"default": "random",
                     "tooltip": "🎲 random rolls the build archetype each time; physique children (chest/legs/arms at body detail low/high) weight toward the drawn parent. A fixed value (muscular, willowy, heavyset…) forces the parent every roll — a distinct set of characters. Children stay soft-influenced, never locked."}),
                "role": (_role_options(), {"default": "any",
                    "tooltip": "Persona register — closed set of ten (warrior, worker, scholar, healer, leader, drifter, athlete, caregiver, charmer, gala) or any. Weights the draw: wardrobe family, garments, wear states, build. Soft affinity, never a lock."}),
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
                    "tooltip": "Broad-stroke, descriptive register. 🎲 rolls this figure's race, weights feature draws toward it, and (at face_detail=high) adds a complexion phrase keyed to it. Dropdown values never enter the string raw — vocabulary maps through phrase banks, stated once."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("character", "components_json", "seed_used")
    FUNCTION = "roll"
    CATEGORY = "SceneGen"

    def roll(self, genre, consistency, face_detail, body_detail, body_type,
             role, name, pose, positioning, seed, age, sex, race,
             hair_mode="modular", emphasis="off", heat="off",
             character_register="none"):
        rng = random.Random(seed)
        families = _load_wardrobe()

        # Persona weight layer (v2). Dict work only — consumes no rng,
        # so the draw ORDER below is the plain register's order.
        persona = {} if role == "any" else _load_personas().get(role, {})
        # Register mode — resolved first so "random" costs exactly
        # one draw, here, before everything else. Any fixed mode
        # costs nothing: same seed, same plain content.
        _reg_mode = character_register
        if _reg_mode == "random":
            _reg_mode = rng.choice([m for m in REGISTER_OPTIONS
                                    if m != "random"])
        _reg = _load_registers().get(_reg_mode, {})
        fam_leans = persona.get("family_leans", {})
        gar_leans = persona.get("garment_leans", {})
        feat_leans = persona.get("feature_leans", {})
        wear_leans = dict(persona.get("wear_leans", {}))
        for _k, _m in _reg.get("wear", {}).items():
            wear_leans[_k] = wear_leans.get(_k, 1.0) * _m
        marks_mult = _reg.get("marks", 1.0)
        _reg_uniform_p = _reg.get("uniform_p", 0.25)
        _reg_uniform_label = _reg.get("uniform_label", "costume")
        _reg_family_wear = _reg.get("family_wear", {})
        _reg_sentence_pool = _reg.get("sentence_pool", [])
        _reg_exag_pool = _reg.get("exaggeration_pool", [])
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
        if fam_leans:
            target_id, target = rng.choices(
                genre_pool,
                weights=[fam_leans.get(fid, 1.0) for fid, _f in genre_pool],
                k=1)[0]
        else:
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
            (fully independent pieces). Returns (text, raw, src) —
            raw kept so the heat phase can look up the archetype;
            draw order (choice, then expansion) is load-bearing."""
            def _pick(fid, fam):
                pool = fam["layers"][layer_key]
                if gar_leans:
                    raw = rng.choices(
                        pool, weights=_lean_w(pool, gar_leans, {}),
                        k=1)[0]
                else:
                    raw = rng.choice(pool)
                return raw, fid

            if rng.random() < consistency:
                raw, src = _pick(target_id, target)
            else:
                if fam_leans:
                    fid, fam = rng.choices(
                        roam,
                        weights=[fam_leans.get(f, 1.0)
                                 for f, _fam in roam], k=1)[0]
                else:
                    fid, fam = rng.choice(roam)
                raw, src = _pick(fid, fam)
            return _expand(raw, rng), raw, src

        # Concepts bank: RETIRED (Alexander, 13:39). The character
        # line asserts only what it places — garments, features,
        # posture — no noun identity claims. The draw order here
        # shortens by one; v2 has no cross-version seed contract.

        sources = {}
        heat_notes = {}

        # Garment phase first, in the same draw order as ever — the
        # heat phase only ever ADDS draws, so heat="off" reproduces
        # the plain register draw-for-draw, same seed = same string.
        pieces = []  # [layer, text, raw]
        text, raw, src = layer_draw("outer")
        sources["outer"] = src
        pieces.append(["outer", text, raw])
        if body_detail == "high":
            if rng.random() < 0.35:
                # Wear state follows the garment it describes; persona
                # and register leans weight the pool (synonym
                # fragments). The register's family_wear keys on the
                # family the garment actually came from (src) — the
                # prestige fix: fine families keep their clothes even
                # at authentic.
                wpool = families[src]["wear"]
                _eff_wear = wear_leans
                _fwo = _reg_family_wear.get(src)
                if _fwo:
                    _eff_wear = dict(wear_leans)
                    for _k, _m in _fwo.items():
                        _eff_wear[_k] = _eff_wear.get(_k, 1.0) * _m
                if _eff_wear:
                    wraw = rng.choices(
                        wpool,
                        weights=_lean_w(wpool, _eff_wear, _WEAR_SYNONYMS),
                        k=1)[0]
                else:
                    wraw = rng.choice(wpool)
                w = _expand(wraw, rng)
                pieces[0][1] = f"{pieces[0][1]}, {w}"
            for key, p in (("torso", 0.8), ("legs", 0.8),
                           ("feet", 0.7), ("head", 0.5)):
                if rng.random() < p:
                    text, raw, src = layer_draw(key)
                    sources[key] = src
                    pieces.append([key, text, raw])

        # Uniform look: ONE weighted option inside its persona. The
        # coin only exists for personas that declare a look — every
        # other draw, and every draw before this point, is untouched.
        # authentic reads it flat: base garments, accessories off
        # ("the non-stylized uniform is very flat and utilitarian" —
        # Alexander, 12:22).
        uniform_rec = None
        _look = persona.get("uniform_look")
        if _look:
            if rng.random() < _reg_uniform_p:
                costume = _costume_for(_look)
                if costume and costume.get("garments"):
                    slots = ("outer", "torso", "legs")
                    pieces = [[slots[i], g, g] for i, g
                              in enumerate(costume["garments"][:3])]
                    if _reg_uniform_label != "uniform":
                        for acc in costume.get("accessories", [])[:1]:
                            pieces.append(["head", acc, acc])
                    uniform_rec = {"look": _look, "fired": True,
                                   "reading": _reg_uniform_label}
                else:
                    uniform_rec = {"look": _look, "fired": False,
                                   "reason": "look missing from costume table"}
            else:
                uniform_rec = {"look": _look, "fired": False,
                               "reason": "coin"}

        # Heat phase — silhouette & reveal only, never color or
        # material. Budget: one garment per dial, two at smoldering.
        if heat != "off":
            legs_raw = next((praw for lk, _t, praw in pieces
                             if lk == "legs"), None)
            hem = legs_raw is not None and is_short_hem(legs_raw)
            eligible = []
            for lk, t, praw in pieces:
                if lk == "feet" and not hem:
                    continue  # tall-boot states only read on bare thigh
                pool = heat_pool(praw, heat)
                if pool:
                    eligible.append((lk, t, praw, pool))
            budget = 2 if heat == "smoldering" else 1
            for _ in range(min(budget, len(eligible))):
                weights = [FOCUS_WEIGHTS.get(lk, 1)
                           for lk, _t, _r, _p in eligible]
                pick = rng.choices(eligible, weights=weights, k=1)[0]
                eligible.remove(pick)
                lk, _t, praw, pool = pick
                phrase = rng.choice(pool)
                heat_notes[lk] = {"archetype": archetype_for(praw),
                                  "phrase": phrase}
                for piece in pieces:
                    if piece[0] == lk:
                        piece[1] = f"{piece[1]}, {phrase}"
                        break
            # Legwear rides over an exposed hem only — thigh-highs
            # under a mini skirt, never over jeans. Suggestive flips
            # a coin; flirty and up commit. Extra draw, outside the
            # focus budget: an accessory, not a garment state.
            if hem:
                pool = legwear_pool(heat)
                if pool and (heat != "suggestive" or rng.random() < 0.5):
                    phrase = rng.choice(pool)
                    heat_notes["legwear"] = {"archetype": "legwear",
                                             "phrase": phrase}
                    pieces.append(["legwear", phrase, "legwear"])

        by_layer = {lk: t for lk, t, _praw in pieces}
        if body_detail == "high":
            outfit = f"in {by_layer['outer']}"
            if "torso" in by_layer:
                outfit += f" over {by_layer['torso']}"
            tails = [by_layer[k] for k in ("legs", "legwear", "feet", "head")
                     if k in by_layer]
            if tails:
                outfit += ", " + ", ".join(tails)
        else:
            outfit = f"in {by_layer['outer']}"

        if rng.random() < consistency:
            palette, pal_src = _expand(rng.choice(target["palettes"]), rng), target_id
        else:
            pal_src, fam = rng.choice(roam)
            palette = _expand(rng.choice(fam["palettes"]), rng)
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
                    drawn = {}
                    for slot in cfg["slots"]:
                        if slot.get("optional") and rng.random() > slot["optional"]:
                            continue
                        req = slot.get("requires")
                        if req and not drawn.get(req):
                            continue
                        opt = _weighted(slot["options"], identity, rng)
                        text = opt["text"] if isinstance(opt, dict) else opt
                        parts.append(text)
                        if slot.get("name"):
                            drawn[slot["name"]] = text
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
        hair_sentence, hair_details = "", {}
        name_str = (name or "").strip()
        if face_detail == "high":
            # Phrase budget: a high face samples ~6 phrases total.
            # Gates drop as banks multiply — variety across the cast,
            # not inventory on one face.
            wmaybe("face_shapes", 0.65, face_bits)
            if hair_mode == "modular" and feats.get("hair_v2"):
                if rng.random() < 0.85:
                    hair_sentence, hair_details = _roll_hair(
                        feats, identity, rng, name_str)
            else:
                wmaybe("hair", 0.85, face_bits)
            wmaybe("eyes", 0.75, face_bits)
            if rng.random() < 0.65:
                # Complexion: the one hard-keyed draw — race selects its
                # own phrase bank, descriptive register, never raw.
                face_bits.append(rng.choice(feats["complexion"][race_res]))
            wmaybe("marks", min(0.9, 0.3 * marks_mult), face_bits)
            wmaybe("nose", 0.45, face_bits)
            wmaybe("mouth", 0.3, face_bits)
            wmaybe("jaw", 0.25, face_bits)
            wmaybe("cheekbones", 0.3, face_bits)
            wmaybe("brow", 0.25, face_bits)
            wmaybe("ears", 0.2, face_bits)
            if rng.random() < 0.65:
                wmaybe("face_detail", 1.0, face_bits)
                if rng.random() < 0.25:
                    wmaybe("face_detail", 1.0, face_bits)
        else:
            # wide-shot legible: shape, hair, eyes, maybe one mark
            wmaybe("face_shapes", 0.9, face_bits)
            if hair_mode == "modular" and feats.get("hair_v2"):
                if rng.random() < 0.9:
                    hair_sentence, hair_details = _roll_hair(
                        feats, identity, rng, name_str)
            else:
                wmaybe("hair", 0.9, face_bits)
            wmaybe("eyes", 0.85, face_bits)
            wmaybe("marks", min(0.9, 0.25 * marks_mult), face_bits)

        # Physique: build parent + influenced children. The parent
        # is a clean archetype, always drawn flat — its canonical
        # text is the axis children weight on, so compose never fires
        # here. Children draw soft-weighted on BOTH identity and the
        # drawn parent: influenced, never exclusive; skip-leg-day
        # lives in the tails. minimal = the portrait proportions
        # anchor: one build word, nothing deeper.
        body_bits = []     # raw fragments — debug/UI record
        body_frags = []    # (prefix, text) — sentence-ready, in order
        arch = [e["text"] for e in feats["build"]]
        forced = None if body_type == "random" else body_type
        if forced is not None and forced not in arch:
            forced = None  # stale workflow value — fall back to random
        gate = 1.0 if forced else {
            "minimal": 1.0, "low": 0.7, "high": 1.0,
        }[body_detail]
        build_text = forced
        if gate >= 1.0 or rng.random() < gate:
            if forced is None:
                entry = _weighted(
                    _scaled_pool(feats["build"], feat_leans, _BUILD_SYNONYMS),
                    identity, rng)
                build_text = entry["text"] if isinstance(entry, dict) else entry
            body_bits.append(build_text)
            build_entry = next((e for e in feats["build"] if isinstance(e, dict)
                                and e.get("text") == build_text), None)
            build_frag = (build_entry or {}).get("emission")
            if not build_frag:
                build_frag = f"{_article(build_text)} {build_text} build"
            body_frags.append(("", build_frag))
        if build_text and body_detail != "minimal":
            pid = dict(identity, build=build_text)
            children = []
            if body_detail == "high":
                for key, p in (("physique_torso", 0.6),
                               ("physique_legs", 0.5),
                               ("physique_arms", 0.4)):
                    if rng.random() < p:
                        e = _weighted(feats[key], pid, rng)
                        children.append((key, e["text"] if isinstance(e, dict) else e))
            elif rng.random() < 0.25:
                e = _weighted(feats["physique_torso"], pid, rng)
                children.append(("physique_torso",
                                 e["text"] if isinstance(e, dict) else e))
            for key, frag in children:
                body_bits.append(frag)
                # all children ride bare — adjectival entries
                # ("bow-legged", "thick through the thighs") can't
                # take "with" without breaking
                body_frags.append(("", frag))

        # Emphasis knob: corroboration, not intensifiers — diffusion
        # shrugs off "very lean" but reads a second independent
        # physical observation of the same trait. Phrases ride just
        # after the build phrase so trait and echo stay adjacent.
        # Guarded so emphasis="off" consumes no rng draws (same-seed
        # output identical to the plain register).
        if emphasis != "off" and body_frags:
            be = next((e for e in feats["build"] if isinstance(e, dict)
                       and e.get("text") == build_text), None)
            pool = (be or {}).get("emph") or []
            if pool:
                k = 1 if emphasis == "low" else 2
                picks = rng.sample(pool, min(k, len(pool)))
                for pick in reversed(picks):
                    body_frags.insert(1, ("", pick))

        # Demeanor is person-energy, not face or body — it fires
        # when either axis asks for depth, and rides as its own
        # sentence. Full-clause entries already carry their subject;
        # everything else takes "They seem …".
        demeanor_bits = []
        if face_detail == "high" or body_detail == "high":
            wmaybe("demeanor", 0.7, demeanor_bits)

        # Register: identity/outfit/palette stay a comma
        # core; body, face, demeanor, hair and named posture ride as
        # full sentences after it. Krea/T5 reads sentences, not
        # comma chains — fragments under-convey (his 17:37 finding).
        core = [identity_phrase, outfit, palette]

        posture = ""
        posture_sent = False
        post_frag = ""
        if pose:
            heat_postures = posture_pool(heat) if heat != "off" else []
            if heat_postures:
                # Heat register replaces the plain draw — body
                # language is part of the dial.
                post_frag = rng.choice(heat_postures)
                posture = post_frag
            else:
                pe = rng.choice(feats["postures"])
                post_frag = pe.get("text", "") if isinstance(pe, dict) else pe
                if isinstance(pe, dict) and pe.get("sentence"):
                    posture = pe["sentence"]
                    posture_sent = True
                else:
                    posture = post_frag
        position = rng.choice(feats["positions"]) if positioning else ""
        # Register sentence — drawn LAST of all draws so register
        # modes never disturb the existing draw order: none consumes
        # nothing, same seed = the plain sheet, byte for byte.
        reg_sentence = ""
        if _reg_sentence_pool:
            reg_sentence = rng.choice(_reg_sentence_pool)
            if _reg_exag_pool:
                reg_sentence = f"{reg_sentence} {rng.choice(_reg_exag_pool)}"
        # nameless posture/position fragments stay in the comma core
        if posture and not posture_sent:
            core.append(posture)
        if position:
            core.append(position)

        text = ", ".join(core)
        name = (name or "").strip()
        if name:
            text = f"{name}, {text}"
        text += "."
        # Register sentence rides second — adjacent to the outfit it
        # summarizes, ahead of the body/face sentences.
        if reg_sentence:
            text = f"{text} {reg_sentence}"

        # Body sentence: build + physique children, one flowing pass.
        body_sent = ""
        if body_frags:
            pieces = [body_frags[0][1]]
            pieces += [(f"with {t}" if pre else t) for pre, t in body_frags[1:]]
            body_sent = f"They have {', '.join(pieces)}."
        # Face sentence: all face fragments as one have-list.
        face_sent = f"They have {', '.join(face_bits)}." if face_bits else ""
        # Demeanor sentence: "They seem {adj}." — or the entry's own
        # clause when it already carries its subject.
        demeanor_sent = ""
        if demeanor_bits:
            dfrag = demeanor_bits[0]
            low = dfrag.lower()
            demeanor_sent = f"{dfrag}." if low.startswith("they ") \
                or low.startswith("their ") else f"They seem {dfrag}."

        for sent in (body_sent, face_sent, demeanor_sent):
            if sent:
                text = f"{text} {sent}"
        if hair_sentence:
            # Modular hair rides as its own sentence — opening clean
            # after a period, like name-bound posture sentences.
            text = f"{text} {hair_sentence}"
        if posture_sent:
            # name-bound posture sentence: opens clean after a period
            if name:
                posture = posture.replace("{name}", name)
                text = f"{text} {posture}"
            elif post_frag:
                posture = post_frag
                text = f"{text}, {post_frag}"

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
            "face_detail": face_detail,
            "body_detail": body_detail,
            "body_type": body_type,
            "persona": {
                "name": role,
                "applied": bool(persona),
                "posture_intent": persona.get("posture"),
            },
            "character_register": {"mode": _reg_mode,
                                   "sentence": reg_sentence,
                                   "uniform": uniform_rec},
            "name": name,
            "palette": palette,
            "palette_family": pal_src,
            "outfit_sources": sources,
            "face": face_bits,
            "demeanor": demeanor_bits,
            "hair_mode": hair_mode,
            "emphasis": emphasis,
            "hair": hair_details,
            "body": body_bits,
            "pose": posture,
            "position": position,
            "heat": {"level": heat, "applied": heat_notes},
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
