"""Wardrobe heat — the archetype physics layer for the character roller.

Three tiers:
  families   character_wardrobe.json    — flavor: genre, palettes, wear words
  archetypes wardrobe_archetypes.json   — physics: what each garment class CAN do
  leaves     the prose items themselves — tagged into archetypes via item_tags

Axes (heat today; wear / formality later) query the archetype layer and
borrow flavor vocabulary from the family. Heat is silhouette & reveal
ONLY — never color or material, which stay orthogonal with palettes and
wear states. One garment, one state. Tier 3 caps at steamy-but-clothed:
the FlatDeep distribution is normal content, and pushing past it would
fight the style the dataset just built.

Draw discipline: heat only ever ADDS rng draws. With heat='off' the
roller reproduces the plain register exactly — pools are consulted
after the garment draws, never instead of them.

Expand the bank, not the code.
"""

import json
import os

HEAT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scene_context", "wardrobe_archetypes.json")

HEAT_OPTIONS = ("off", "suggestive", "flirty", "smoldering")
_LEVEL_NUM = {"suggestive": 1, "flirty": 2, "smoldering": 3}

# Which layer the dial prefers to touch: torso and legs carry the
# register; outer supports; feet only when nothing else qualifies.
# headwear carries no pools, so its weight never matters.
FOCUS_WEIGHTS = {"torso": 3, "legs": 3, "outer": 2, "feet": 1, "head": 0}

_CACHE = {"bank": None}


def load_heat_bank():
    if _CACHE["bank"] is None:
        with open(HEAT_PATH, encoding="utf-8") as f:
            _CACHE["bank"] = json.load(f)
    return _CACHE["bank"]


def archetype_for(raw_item):
    """Tag lookup on the RAW (pre-expansion) item string."""
    return load_heat_bank().get("item_tags", {}).get(raw_item, "")


def heat_pool(raw_item, level):
    """Non-drawing probe: the phrase pool for this item at this level,
    or [] when the item is untagged / its archetype has no pool here."""
    n = _LEVEL_NUM.get(level, 0)
    if n <= 0:
        return []
    arch = archetype_for(raw_item)
    if not arch:
        return []
    pools = (load_heat_bank().get("archetypes", {})
             .get(arch, {}).get("heat", {}))
    return pools.get(str(n), [])


def posture_pool(level):
    """Non-drawing probe: the heat-register posture pool, or []."""
    n = _LEVEL_NUM.get(level, 0)
    if n <= 0:
        return []
    return load_heat_bank().get("posture_heat", {}).get(str(n), [])


def short_hem_items():
    """Raw wardrobe items whose hem exposes the thigh. Drives the
    legwear draw and the tall-boot gate: those states only read on
    bare leg."""
    return load_heat_bank().get("short_hem", [])


def is_short_hem(raw_item):
    return raw_item in short_hem_items()


def legwear_pool(level):
    """Non-drawing probe: the heat-register legwear garment pool
    (thigh-highs, stockings) — garment names, not fit states."""
    n = _LEVEL_NUM.get(level, 0)
    if n <= 0:
        return []
    return (load_heat_bank().get("archetypes", {})
            .get("legwear", {}).get("heat", {}).get(str(n), []))


def validate_heat_bank(wardrobe_path=None):
    """Data hygiene: tags must name known archetypes and key real
    wardrobe items; pool levels must be '1'-'3' lists of strings.
    Returns (problems, info) — info carries tag coverage so drift
    is visible, not silent."""
    bank = load_heat_bank()
    problems = []
    archetypes = bank.get("archetypes", {})
    tags = bank.get("item_tags", {})
    if wardrobe_path is None:
        wardrobe_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "scene_context", "character_wardrobe.json")
    with open(wardrobe_path, encoding="utf-8") as f:
        families = json.load(f)["families"]
    real = set()
    for fam in families.values():
        for items in fam.get("layers", {}).values():
            real.update(items)
    for key, arch in tags.items():
        if arch not in archetypes:
            problems.append(
                f"item_tags[{key!r}]: unknown archetype {arch!r}")
        if key not in real:
            problems.append(
                f"item_tags key matches no wardrobe item: {key!r}")
    for name, spec in archetypes.items():
        for lvl, pool in spec.get("heat", {}).items():
            if lvl not in ("1", "2", "3"):
                problems.append(
                    f"archetype {name!r}: bad heat level {lvl!r}")
            elif not pool or not all(
                    isinstance(p, str) and p for p in pool):
                problems.append(
                    f"archetype {name!r} level {lvl}: empty/bad pool")
    for key in bank.get("short_hem", []):
        if key not in real:
            problems.append(
                f"short_hem key matches no wardrobe item: {key!r}")
    used = set(tags.values())
    unused = sorted(a for a in archetypes if a not in used)
    tagged = sum(1 for k in tags if k in real)
    return problems, {
        "tagged": tagged, "total": len(real),
        "untagged_archetypes": unused,
    }
