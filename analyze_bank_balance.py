#!/usr/bin/env python3
"""Bank-balance auditor — the measurement instrument for bank expansion.

Rolls casts headless through the real roller and reports:
  1. Pool census  — draws, distinct/size, hottest phrase vs mean (skew)
  2. Cast echo    — within-cast duplicate rate per pool, vs the
                    birthday-collision prediction for that pool size
  3. Affinity     — per-entry draw-rate ratio, tagged-match vs untagged,
                    for each fixable identity axis value.
                    Expected ≈ w_match/w_untagged = 2.0.
                    Ratio < 1.0 = tag-bug signature (an affinity
                    running backwards — see _TAG_ALIAS, 2026-08-22).

Usage:
  python3 analyze_bank_balance.py [--casts 250] [--per 4] [--seed0 100000]
                                  [--affinity-casts 300]
  python3 analyze_bank_balance.py --lint        # vocab coverage; exit 1 on fail

Pure read: imports the roller, consumes components_json, prints a table.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_character_roller as roller  # noqa: E402

FEATS = json.load(open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scene_context", "character_features.json")))

POOLS = ["face_shapes", "hair", "eyes", "marks", "face_detail",
         "build", "demeanor"]
GEOMETRY = ["postures", "positions"]

AXIS_VALUES = {
    "age": ["young adult", "middle-aged", "older"],
    "sex": ["female", "male"],
    "race": ["white", "black", "east_asian", "south_asian",
             "latino", "middle_eastern", "indigenous"],
}


def phrase_index():
    idx = {}
    for pool in POOLS + ["complexion"]:
        v = FEATS[pool]
        if pool == "complexion":
            for phrases in v.values():
                for p in phrases:
                    idx[p] = pool
        else:
            for e in v:
                idx[e["text"] if isinstance(e, dict) else e] = pool
    for pool in GEOMETRY:
        for s in FEATS[pool]:
            idx[s] = pool
    return idx


def roll_casts(n_casts, per, seed0, detail="high"):
    """Returns list of casts; each cast is a list of component dicts."""
    R = roller.RANDOM
    node = roller.SceneCharacterRoller()
    casts = []
    for i in range(n_casts):
        members = []
        for j in range(per):
            _, comp, _ = node.roll(R, 0.3, detail, "any", "",
                                   True, True, seed0 + i * per + j,
                                   R, R, R)
            members.append(json.loads(comp))
        casts.append(members)
    return casts


def census(casts, idx):
    counts = defaultdict(Counter)
    for cast in casts:
        for m in cast:
            for phrase in m["face"] + [m["pose"], m["position"]]:
                if not phrase:
                    continue
                counts[idx[phrase]][phrase] += 1
    return counts


def echo_rates(casts, idx, per):
    """Fraction of casts with a same-pool duplicate among members."""
    out = {}
    for pool in POOLS + GEOMETRY:
        dup_casts = 0
        for cast in casts:
            seen = set()
            dup = False
            for m in cast:
                for p in m["face"] + [m["pose"], m["position"]]:
                    if p and idx.get(p) == pool:
                        if p in seen:
                            dup = True
                        seen.add(p)
            dup_casts += dup
        size = len(FEATS[pool]) if pool in POOLS else len(FEATS[pool])
        # P(all per draws distinct) = ∏(1 - k/size)
        p_distinct = 1.0
        for k in range(per):
            p_distinct *= max(0.0, (size - k) / size)
        out[pool] = (dup_casts / len(casts), 1.0 - p_distinct, size)
    return out


def affinity(axis, value, n_casts, seed0):
    """Per-entry rate ratio: entries tagged `value` vs untagged on `axis`.

    Other axes left random — weights are separable per axis. With the
    standard 4/2/1 weights and single-axis tagging, expected ratio 2.0.
    """
    R = roller.RANDOM
    node = roller.SceneCharacterRoller()
    kwargs = {axis: value}
    others = {a: R for a in ("age", "sex", "race") if a != axis}
    tagged_draws, tagged_n = Counter(), 0
    plain_draws, plain_n = Counter(), 0
    for i in range(n_casts):
        _, comp, _ = node.roll(R, 0.3, "high", "any", "",
                               False, False, seed0 + 7919 + i,
                               kwargs.get("age", R),
                               kwargs.get("sex", R),
                               kwargs.get("race", R))
        comp = json.loads(comp)
        for phrase in comp["face"]:
            pool = None
            for p in POOLS:
                for e in FEATS[p]:
                    if (e["text"] if isinstance(e, dict) else e) == phrase:
                        pool = p
                        entry = e
                        break
                if pool:
                    break
            if not pool:
                continue
            tag = (entry.get(axis) if isinstance(entry, dict) else None)
            if tag is not None:
                tag = roller._TAG_ALIAS.get(tag, tag)
            if tag == value:
                tagged_draws[phrase] += 1
            elif tag is None:
                plain_draws[phrase] += 1
    # per-entry mean rates
    per_pool = {}
    for p in POOLS:
        t_entries = [e["text"] for e in FEATS[p]
                     if isinstance(e, dict) and roller._TAG_ALIAS.get(e.get(axis), e.get(axis)) == value]
        u_entries = [e["text"] for e in FEATS[p]
                     if isinstance(e, dict) and e.get(axis) is None]
        if not t_entries or not u_entries:
            continue
        t_rate = sum(tagged_draws[t] for t in t_entries) / len(t_entries)
        u_rate = sum(plain_draws[u] for u in u_entries) / len(u_entries)
        if t_rate and u_rate:
            per_pool[p] = (t_rate / u_rate, t_rate, u_rate)
    return per_pool


def lint():
    """Vocabulary coverage lint for the scene side. Returns exit code.

    The loader (scene_tags) guarantees every tag is KNOWN; this
    guarantees the vocabularies are USEFUL: every genre genre-pickable
    (>=3 venues or the picker silently falls back to ALL settings),
    every facet shared (>=2 venues), every situation tag reachable,
    every genre with >=2 wardrobe families (firm-genre rolls starve
    below). Self-tests the validator each run: an injected unknown tag
    must be caught, or the law itself is broken.
    """
    import scene_tags
    from scene_context_node import GENRE_OPTIONS, RANDOM

    tags = scene_tags.load_tags()
    fails = []

    probs = []
    scene_tags._validate_venue(
        "self_test", {"genre_tags": ["phantom"], "situations": []},
        tags, probs)
    if not probs:
        fails.append("self-test: unknown genre tag slipped validation")

    for note in scene_tags.validate_scene_tags():
        print(f"  legacy-alias (accepted): {note}")

    venues = []
    for fn in sorted(os.listdir(scene_tags.SETTINGS_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(scene_tags.SETTINGS_DIR, fn),
                      encoding="utf-8") as f:
                venues.append(json.load(f))

    genre_n = Counter(t for v in venues for t in v["genre_tags"])
    for g in tags["genre"]:
        n = genre_n.get(g, 0)
        print(f"  genre    {g:14s} {n:2d} venues")
        if n < 3:
            fails.append(
                f"genre '{g}': {n} venues (<3) — picker falls back to ALL")

    facet_n = Counter(t for v in venues for t in v["facet_tags"])
    for fc in tags["facet"]:
        n = facet_n.get(fc, 0)
        print(f"  facet    {fc:14s} {n:2d} uses")
        if n < 2:
            fails.append(f"facet '{fc}': {n} uses (<2) — orphan vocabulary")

    sit_n = Counter(
        t for v in venues for s in v["situations"] for t in s["tags"])
    for st in tags["situation"]:
        if sit_n.get(st, 0) < 1:
            fails.append(f"situation tag '{st}': unreachable (0 uses)")

    with open(scene_tags.WARDROBE_PATH, encoding="utf-8") as f:
        fams = json.load(f)["families"]
    fam_n = Counter(f["genre"] for f in fams.values() if f.get("genre"))
    for g in tags["genre"]:
        n = fam_n.get(g, 0)
        print(f"  wardrobe {g:14s} {n} families")
        if n < 2:
            fails.append(f"wardrobe: genre '{g}' has {n} families (<2)")
    if not any(not f.get("genre") for f in fams.values()):
        fails.append(
            "wardrobe: no era-neutral fallback family "
            "(a genre-less family must exist for firm-genre "
            "rolls with no families)")

    expected = [RANDOM] + list(tags["genre"])
    if GENRE_OPTIONS != expected:
        fails.append(f"enum drift: GENRE_OPTIONS != registry {expected}")

    if fails:
        print("\nLINT FAIL:")
        for f_ in fails:
            print(f"  - {f_}")
        return 1
    print("LINT PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casts", type=int, default=250)
    ap.add_argument("--per", type=int, default=4)
    ap.add_argument("--seed0", type=int, default=100000)
    ap.add_argument("--affinity-casts", type=int, default=300)
    ap.add_argument("--lint", action="store_true",
                    help="vocabulary coverage lint; exit 1 on fail")
    args = ap.parse_args()

    if args.lint:
        sys.exit(lint())

    idx = phrase_index()
    casts = roll_casts(args.casts, args.per, args.seed0)
    counts = census(casts, idx)

    total_rolls = args.casts * args.per
    print(f"=== POOL CENSUS  ({total_rolls} rolls, {args.per}/cast, detail=high) ===")
    for pool in POOLS + GEOMETRY + ["complexion"]:
        c = counts[pool]
        size = (sum(len(v) for v in FEATS["complexion"].values())
                if pool == "complexion" else len(FEATS[pool]))
        draws = sum(c.values())
        if not draws:
            continue
        mean = draws / size
        top, n = c.most_common(1)[0]
        zero = size - len(c)
        print(f"{pool:14s} draws {draws:5d}  distinct {len(c)}/{size:<3d}"
              f"  unused {zero:<3d}  hottest {n / mean:4.1f}×mean  ({top[:40]})")

    print(f"\n=== CAST ECHO  (duplicate within a cast, {args.per} members) ===")
    for pool, (obs, pred, size) in echo_rates(casts, idx, args.per).items():
        flag = "  ← THIN" if obs > 0.35 else ""
        print(f"{pool:14s} observed {obs:5.1%}  predicted {pred:5.1%}"
              f"  (pool {size}){flag}")

    print("\n=== AFFINITY AUDIT  (tagged-match vs untagged, expect ≈2.0; <1.0 = bug) ===")
    for axis, values in AXIS_VALUES.items():
        for value in values:
            res = affinity(axis, value, args.affinity_casts, args.seed0)
            for pool, (ratio, t, u) in res.items():
                flag = "  ← INVERTED" if ratio < 1.0 else ""
                print(f"{axis}={value:14s} {pool:14s} ratio {ratio:4.2f}"
                      f"  (tagged {t:.3f}/entry vs untagged {u:.3f}/entry){flag}")


if __name__ == "__main__":
    main()
