"""
Standalone coverage audit for scene_context/settings/.

Reports situation-pool sizes after the same joins the composer performs
(genre union -> archetype facet-subset -> tone compatible-tag filter),
so silent tag gaps and zero-pools surface before they hit ComfyUI.

Run: python3 coverage_audit.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scene_context_node import _load_settings, _load_tones, _filter_by_genre, GENRE_OPTIONS
from scene_context_composer import _load_archetypes

GENRES = [g for g in GENRE_OPTIONS if g != "\U0001f3b2 random"]


def main():
    settings = _load_settings()
    tones = _load_tones()
    archetypes = _load_archetypes()

    print(f"Loaded {len(settings)} venues, {sum(len(v['situations']) for v in settings.values())} total situations\n")

    # ── Per-venue schema sanity ──
    problems = []
    for name, v in sorted(settings.items()):
        if not v.get("subject_label"):
            problems.append(f"{name}: missing subject_label")
        if not v.get("genre_tags"):
            problems.append(f"{name}: no genre_tags — invisible to genre filter, only reachable by pinning")
        bad_genres = set(v.get("genre_tags", [])) - set(GENRES)
        if bad_genres:
            problems.append(f"{name}: genre_tags outside closed set: {bad_genres}")
        for s in v.get("situations", []):
            tags = set(s.get("tags", []))
            content_tags = tags & {"action", "social", "labor", "nature"}
            tone_tags = tags & {"calm_capable", "tense_capable", "violent_capable"}
            if len(content_tags) != 1:
                problems.append(f"{name}/{s['id']}: expected exactly 1 content tag, got {content_tags or 'none'}")
            if not tone_tags:
                problems.append(f"{name}/{s['id']}: no tone-capability tag — unreachable under any tone filter (falls back to full pool, silently)")
            bias = s.get("scene_type_bias")
            if bias and bias not in {"face_off", "gathering", "candid_moment", "atmospheric", "close_group", "at_work"}:
                problems.append(f"{name}/{s['id']}: scene_type_bias '{bias}' not in known composition pools — will silently fall back to 'default'")
            env = s.get("env")
            if env and env not in {"clear", "overcast", "storm", "neutral"}:
                problems.append(f"{name}/{s['id']}: env '{env}' outside circulation set")

    if problems:
        print("── Schema flags ──")
        for p in problems:
            print(f"  ! {p}")
        print()
    else:
        print("No schema flags.\n")

    # ── Archetype coverage: which venues satisfy each archetype ──
    print("── Archetype coverage ──")
    for aid, a in archetypes.items():
        facets = set(a["facets"])
        matches = [n for n, v in settings.items() if facets <= set(v.get("facet_tags", []))]
        print(f"  {aid} ({a['label']}, facets={sorted(facets)}): {len(matches)} venues -> {sorted(matches)}")
    print()

    # ── Genre x Archetype x Tone joined pool sizes ──
    print("── Joined pool sizes (genre x archetype x tone) ──")
    print("   flags any combination whose situation pool is 0 (raises) or very thin (<2)\n")
    thin = []
    for genre in GENRES:
        genre_pool = _filter_by_genre(settings, genre, "none")
        for aid, a in archetypes.items():
            facets = set(a["facets"])
            venue_pool = [v for v in genre_pool if facets <= set(v.get("facet_tags", []))]
            if not venue_pool:
                venue_pool = [v for v in settings.values() if facets <= set(v.get("facet_tags", []))]
            all_situations = [s for v in venue_pool for s in v["situations"]]
            for tone_key, tone in tones.items():
                compat = tone.get("compatible")
                if compat:
                    pool = [s for s in all_situations if set(s.get("tags", [])) & set(compat)]
                    if not pool:
                        pool = all_situations  # join-miss fallback per composer logic
                else:
                    pool = all_situations
                if len(pool) < 2:
                    thin.append((genre, aid, tone_key, len(pool), len(venue_pool)))
    if thin:
        for genre, aid, tone_key, n, nv in thin:
            print(f"  ! genre={genre:<10} archetype={aid:<16} tone={tone_key:<10} -> {n} situations from {nv} venues")
    else:
        print("  none — every genre x archetype x tone combination has >=2 situations to draw from")
    print()

    # ── Storm env coverage ──
    storm_situations = [f"{n}/{s['id']}" for n, v in settings.items() for s in v["situations"] if s.get("env") == "storm"]
    print(f"── Storm-tagged situations: {len(storm_situations)} ──")
    for s in storm_situations:
        print(f"  {s}")
    print()

    # ── Facet tag vocabulary — flag anything not already in circulation,
    #    since new tags should be coined deliberately, not decoratively ──
    KNOWN_FACETS = {
        "sea", "vessel", "shore", "age_of_sail", "small_crew", "leisure",
        "crowd", "small_crowd",
        "mountain", "road", "forest", "city", "street", "station",
    }
    all_facets = set()
    for v in settings.values():
        all_facets |= set(v.get("facet_tags", []))
    new_facets = all_facets - KNOWN_FACETS
    print(f"── Facet tags in use: {len(all_facets)} ──")
    if new_facets:
        print(f"  ! not in the known vocabulary list above (update KNOWN_FACETS if intentional): {sorted(new_facets)}")
    else:
        print("  all accounted for")

    # ── Genre coverage per archetype — batch 2 constraint: each new
    #    archetype needs >=1 modern-or-sci_fi venue so genre filtering
    #    has something to bite on beyond historical/fantasy ──
    print("\n── Genre coverage per archetype ──")
    for aid, a in archetypes.items():
        facets = set(a["facets"])
        matches = [(n, v.get("genre_tags", [])) for n, v in settings.items() if facets <= set(v.get("facet_tags", []))]
        modern_or_scifi = [n for n, g in matches if "modern" in g or "sci_fi" in g]
        flag = "" if modern_or_scifi else "  ! no modern/sci_fi venue in this archetype"
        print(f"  {aid}: {[n for n, _ in matches]}{flag}")


if __name__ == "__main__":
    main()
