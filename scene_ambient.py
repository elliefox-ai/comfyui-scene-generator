"""Scene Ambient Activity — background figures and activity (v2).

Where the Composer stages *where and what*, and the Roller decides
*who the cast is*, this node populates the crowd: background cameo
subjects drawn from scene_context/ambient_banks_draft.json (the
2026-08-30 harvest), with optional treatment operators (satire /
chaotic) applied ON TOP at draw time — subjects are written played
straight; the twist is never baked in.

Own seed, separate from the Composer: keep the cast, reroll the
crowd. Same seed -> same crowd (v2 contract; no cross-version seed
compatibility).

Dropdowns:
  subject    none (default) | one of the eight pools | random |
             multiversal. random = ONE pool for the whole crowd
             (coherent); multiversal = each figure draws its own pool
             (crossover). The pool list supersedes the 9-entry spec
             draft: the harvest delivered nine banks, all selectable
             — popculture is the opt-in branded pool (2026-08-31
             taste-call wave; the other pools stay brand-free).
  treatment  none (default) | satire | chaotic | random. Militant
             satire is the blended cell (humiliation + tender
             inversion). Pools without a by-category bank fall back
             to the generic operator. random = per-figure 50/50.
  genre      any (default) | a roller genre id | the roller's 🎲
             random sentinel. Setting it filters each pool to entries
             tagged for the genre plus tagless
             (setting-neutral) entries; zero matches falls back to
             the full pool. any is byte-identical to legacy draws.

Era tags on entries ({"tags": ["era:1950s"]}) are carried data for a
future era-aware filter; v1 renders the text only.
"""

import json
import os
import random

try:  # package context (deployed pack)
    from .scene_character_roller import _expand, GENRE_OPTIONS, RANDOM
except ImportError:  # headless harness
    from scene_character_roller import _expand, GENRE_OPTIONS, RANDOM

CONTEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "scene_context")
BANKS_FILE = "ambient_banks_draft.json"

_BANKS_CACHE = {}


def _load_banks():
    """Ambient banks (v2). Required data — a missing or broken file is
    a hard error: the pools ARE this node."""
    if "d" not in _BANKS_CACHE:
        path = os.path.join(CONTEXT_DIR, BANKS_FILE)
        with open(path, encoding="utf-8") as f:
            _BANKS_CACHE["d"] = json.load(f)
    return _BANKS_CACHE["d"]


_SUBJECT_POOLS = ("accurate", "wholesome", "militant", "sexy", "absurd",
                  "cool", "dorky", "elegant", "popculture")
SUBJECT_OPTIONS = ["none"] + list(_SUBJECT_POOLS) + ["random", "multiversal"]
TREATMENT_OPTIONS = ["none", "satire", "chaotic", "random"]

# Genre filter vocabulary: "any" (unfiltered = byte-identical legacy
# draws), the roller's genre ids, and the roller's 🎲 sentinel so
# synced primitives validate across the node family. 🎲 rolls ONCE
# into a concrete genre (coherent crowd), then filters exactly like it.
_GENRE_IDS = [g for g in GENRE_OPTIONS if g != RANDOM]
GENRE_INPUT_OPTIONS = ["any"] + _GENRE_IDS + [RANDOM]


def _entries(banks, pool):
    return banks["subjects"][pool]["entries"]


def _entry_text(e):
    return e["text"] if isinstance(e, dict) else e


def _satire_phrases(banks, pool):
    """Satire operator stock for one pool. Militant is the blended
    cell (humiliation + tender inversion); pools without a by-category
    bank fall back to the generic humiliation operator."""
    cell = banks["treatments"]["satire"]["by_category"].get(pool)
    if isinstance(cell, dict):
        return list(cell.get("humiliation", [])) + \
            list(cell.get("tender_inversion", []))
    if cell:
        return cell
    return banks["treatments"]["satire"]["generic_humiliation"]


def _chaotic_phrases(banks, pool):
    return (banks["treatments"]["chaotic"]["by_category"].get(pool)
            or banks["treatments"]["chaotic"]["generic"])


def _candidates(entries, genre):
    """Genre filter (v2.1). Eligible = no genre: tags (setting-
    neutral) or tagged for the requested genre; era-only tags read
    as neutral. Never empty: a genre with zero matches falls back
    to the full pool. any skips the filter entirely — legacy draw
    order untouched."""
    if genre == "any":
        return entries
    picked = []
    for e in entries:
        gtags = [t for t in (e.get("tags", []) if isinstance(e, dict) else [])
                 if isinstance(t, str) and t.startswith("genre:")]
        if not gtags or f"genre:{genre}" in gtags:
            picked.append(e)
    return picked or entries


class SceneAmbientActivity:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subject": (SUBJECT_OPTIONS, {"default": "none",
                    "tooltip": "Background cameo pool. random = one pool for the whole crowd (coherent); multiversal = each figure draws its own pool (crossover)."}),
                "treatment": (TREATMENT_OPTIONS, {"default": "none",
                    "tooltip": "Operator applied ON TOP of subjects at draw time — subjects are played straight; the twist is never baked in. Militant satire is the blended cell (humiliation + tender inversion)."}),
                "count": ("INT", {"default": 1, "min": 1, "max": 3,
                    "tooltip": "How many background figures to describe."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**32 - 1,
                    "tooltip": "Own seed — keep the cast, reroll the crowd. Same seed, same crowd."}),
                "genre": (GENRE_INPUT_OPTIONS, {"default": "any",
                    "tooltip": "Filter the crowd pool to entries tagged for this genre — tagless entries always eligible; never empty. any = no filter. 🎲 random rolls one genre per generation — one coherent crowd."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("ambient_text",)
    FUNCTION = "roll"
    CATEGORY = "SceneGen"

    def roll(self, subject, treatment, count, seed, genre="any"):
        if subject == "none" or count < 1:
            return ("",)
        banks = _load_banks()
        rng = random.Random(seed)
        # 🎲 random resolves ONCE per generation — one coherent genre
        # for the whole crowd — before any other draw. Every other
        # value consumes nothing, so legacy draws stay byte-identical.
        if genre == RANDOM:
            genre = rng.choice(_GENRE_IDS)

        # One upfront pool draw for random — a coherent crowd.
        # multiversal defers pool resolution to the loop (per figure);
        # random resolves ONCE here (one pool per crowd).
        pool = subject
        entries = None
        if subject == "random":
            pool = rng.choice(_SUBJECT_POOLS)
        if subject != "multiversal":
            entries = _candidates(_entries(banks, pool), genre)

        out = []
        for _ in range(count):
            # Draw order (documented for stability): genre sentinel
            # (🎲 random only), pool (multiversal only), genre filter
            # (no rng), subject entry, treatment pick (random only),
            # treatment phrase.
            if subject == "multiversal":
                pool = rng.choice(_SUBJECT_POOLS)
                entries = _candidates(_entries(banks, pool), genre)
            subj = _expand(_entry_text(rng.choice(entries)), rng)
            tmode = treatment
            if treatment == "random":
                tmode = rng.choice(("satire", "chaotic"))
            if tmode == "satire":
                twist = rng.choice(_satire_phrases(banks, pool))
            elif tmode == "chaotic":
                twist = rng.choice(_chaotic_phrases(banks, pool))
            else:
                twist = ""
            out.append(f"{subj}, {twist}" if twist else subj)
        return ("; ".join(out),)


NODE_CLASS_MAPPINGS = {
    "SceneAmbientActivity": SceneAmbientActivity,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SceneAmbientActivity": "🎭 Scene Ambient Activity",
}
