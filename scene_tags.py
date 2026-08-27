"""Scene tag registry — the single source of truth for tag vocabularies.

Vocabulary lives in scene_context/tags.json; every tag written in venue,
situation, character-feature, and wardrobe data is validated against it
at import time. An unknown tag is a HARD failure naming the file and the
tag: silent vocabulary drift (the young-tag inversion bug's habitat)
must never ship again.

Adding a genre: add the id to tags.json — the enums derive from the
registry at import (scene_context_node.py), so registry and dropdowns
cannot drift apart — then author venues honestly (cross-tag rule: a
venue carries genre G only if it is welcome in every pool built from
G) and give the genre two wardrobe families.

Legacy spellings (tags.json "_aliases") are accepted and reported, not
failed — normalize the data when convenient, never add new aliases.
"""

import json
import os

_CONTEXT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "scene_context"
)
TAGS_PATH = os.path.join(_CONTEXT_DIR, "tags.json")
SETTINGS_DIR = os.path.join(_CONTEXT_DIR, "settings")
FEATURES_PATH = os.path.join(_CONTEXT_DIR, "character_features.json")
WARDROBE_PATH = os.path.join(_CONTEXT_DIR, "character_wardrobe.json")

_IDENTITY_AXES = ("age", "sex", "race")

_TAGS_CACHE = None


def load_tags():
    """Load (and cache) the tag registry."""
    global _TAGS_CACHE
    if _TAGS_CACHE is None:
        with open(TAGS_PATH, encoding="utf-8") as f:
            _TAGS_CACHE = json.load(f)
    return _TAGS_CACHE


def genre_with_parents(genre_id, tags=None):
    """Resolve a genre id to itself plus every ancestor genre in the
    parent ladder (from tags.json). Subgenres inherit their parents'
    wardrobe families — western resolves to {western, historical},
    post_apocalyptic to {post_apocalyptic, sci_fi, modern}."""
    if tags is None:
        tags = load_tags()
    genres = tags.get("genre", {})
    out = set()
    stack = [genre_id]
    while stack:
        g = stack.pop()
        if g in out:
            continue
        out.add(g)
        stack.extend(genres.get(g, {}).get("parents", []))
    return out


def _validate_venue(name, data, tags, problems):
    """Check one venue dict's genre/facet/situation tags. Mutates problems."""
    for t in data.get("genre_tags", []):
        if t not in tags["genre"]:
            problems.append(f"venue '{name}': unknown genre tag '{t}'")
    for t in data.get("facet_tags", []):
        if t not in tags["facet"]:
            problems.append(f"venue '{name}': unknown facet tag '{t}'")
    for s in data.get("situations", []):
        for t in s.get("tags", []):
            if t not in tags["situation"]:
                problems.append(
                    f"venue '{name}' situation '{s.get('id', '?')}': "
                    f"unknown situation tag '{t}'"
                )


def _validate_features(feats, tags, problems, legacy):
    """Check identity-axis tags on feature-pool entries. Soft pools only."""
    aliases = tags.get("_aliases", {})
    for pool, entries in feats.items():
        if pool.startswith("_") or not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            for ax in _IDENTITY_AXES:
                if ax not in e:
                    continue
                val = e[ax]
                if val in tags[f"identity_{ax}"]:
                    continue
                alias = aliases.get(ax, {})
                if val in alias:
                    legacy.append(
                        f"{pool} '{str(e.get('text', '?'))[:34]}': "
                        f"legacy {ax} '{val}' -> '{alias[val]}'"
                    )
                else:
                    problems.append(
                        f"features '{pool}': unknown {ax} value '{val}' "
                        f"(entry '{str(e.get('text', '?'))[:34]}')"
                    )


def _validate_wardrobe(families, tags, problems):
    for fam, spec in families.items():
        g = spec.get("genre")
        if g and g not in tags["genre"]:
            problems.append(f"wardrobe family '{fam}': unknown genre '{g}'")


def validate_scene_tags(tags=None):
    """Validate all tag-bearing data against the registry.

    Raises ValueError with the full violation report on any unknown tag.
    Returns the list of legacy-alias notes (informational, never fatal).
    """
    tags = tags if tags is not None else load_tags()
    problems = []
    legacy = []

    for fname in sorted(os.listdir(SETTINGS_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(SETTINGS_DIR, fname), encoding="utf-8") as f:
            data = json.load(f)
        _validate_venue(data.get("name", fname), data, tags, problems)

    with open(FEATURES_PATH, encoding="utf-8") as f:
        feats = json.load(f)
    _validate_features(feats, tags, problems, legacy)
    for rk in feats.get("complexion", {}):
        if rk not in tags["identity_race"]:
            problems.append(
                f"features 'complexion': unknown race key '{rk}'")

    with open(WARDROBE_PATH, encoding="utf-8") as f:
        _validate_wardrobe(json.load(f).get("families", {}), tags, problems)

    if problems:
        raise ValueError(
            "Tag registry violations "
            f"({len(problems)}; registry: {TAGS_PATH}):\n  "
            + "\n  ".join(problems)
        )
    return legacy
