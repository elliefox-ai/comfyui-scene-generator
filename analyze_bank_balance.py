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
  4. Frequency    — venue/situation/tone/flourish draw balance from the
                    real SceneContextComposer, per genre-sampling mode,
                    vs an exact analytic expected share. Unlike the
                    roller import above (sys.path + bare import — fine
                    for the roller, whose own try/except import always
                    lands on the same names either way), the composer
                    is loaded as a real package via
                    spec_from_file_location + exec_module, so its
                    `from .scene_context_node import ...` resolves
                    through the *relative* branch — the actual path
                    ComfyUI runs, not the standalone fallback. That
                    gap is what let a live bug slip past tests before.

Usage:
  python3 analyze_bank_balance.py [--casts 250] [--per 4] [--seed0 100000]
                                  [--affinity-casts 300]
  python3 analyze_bank_balance.py --lint        # vocab coverage; exit 1 on fail
  python3 analyze_bank_balance.py --frequency [--freq-n 2000]
                                  [--freq-seed0 900000]  # exit 1 on fail

Pure read: imports the roller / composer, consumes components_json,
prints a table. Never edits picker code or bank JSON.
"""
import argparse
import importlib.util
import json
import os
import sys
import types
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_character_roller as roller  # noqa: E402

FEATS = json.load(open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scene_context", "character_features.json")))

POOLS = ["face_shapes", "hair", "eyes", "nose", "mouth", "jaw", "cheekbones", "brow", "ears", "marks",
         "face_detail", "build", "demeanor", "physique_torso", "physique_legs", "physique_arms"]
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


# --------------------------------------------------------------------
# Frequency mode — venue/situation/tone/flourish draw balance for the
# real SceneContextComposer, against an exact analytic expectation.
# --------------------------------------------------------------------

_SCENE_PKG_NAME = "_scene_gen_pkg"


def _load_scene_pack():
    """Load the composer/picker as a real package via
    spec_from_file_location + exec_module, so their internal
    `from .scene_context_node import ...` resolves through the
    relative branch — the path ComfyUI actually runs.

    Tries the pack's own __init__.py first (the exact mechanism
    ComfyUI's custom_nodes loader uses: spec_from_file_location on
    __init__.py with submodule_search_locations set). If this script
    isn't sitting next to one, falls back to registering a synthetic
    namespace package over the same directory and loading the two
    modules we need into it directly — still spec-based, never a bare
    `python3 scene_context_composer.py` run, just not coupled to
    __init__.py's exact contents.
    """
    if _SCENE_PKG_NAME in sys.modules:
        return sys.modules[_SCENE_PKG_NAME]

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    init_path = os.path.join(pkg_dir, "__init__.py")

    if os.path.isfile(init_path):
        spec = importlib.util.spec_from_file_location(
            _SCENE_PKG_NAME, init_path, submodule_search_locations=[pkg_dir]
        )
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[_SCENE_PKG_NAME] = pkg
        spec.loader.exec_module(pkg)
        if not hasattr(pkg, "scene_context_composer"):
            raise ImportError(
                f"{init_path} loaded but doesn't expose scene_context_composer — "
                "expected it to import the composer (directly or via "
                "NODE_CLASS_MAPPINGS aggregation) the way a ComfyUI pack's "
                "__init__.py normally does"
            )
        return pkg

    # No __init__.py here — build the minimal namespace package by hand.
    pkg = types.ModuleType(_SCENE_PKG_NAME)
    pkg.__path__ = [pkg_dir]
    pkg.__package__ = _SCENE_PKG_NAME
    sys.modules[_SCENE_PKG_NAME] = pkg

    for name in ("scene_context_node", "scene_context_composer"):
        mod_name = f"{_SCENE_PKG_NAME}.{name}"
        mod_spec = importlib.util.spec_from_file_location(
            mod_name, os.path.join(pkg_dir, f"{name}.py")
        )
        mod = importlib.util.module_from_spec(mod_spec)
        mod.__package__ = _SCENE_PKG_NAME
        sys.modules[mod_name] = mod
        mod_spec.loader.exec_module(mod)
        setattr(pkg, name, mod)

    return pkg


def _freq_expected(pkg, genre):
    """Exact analytic draw probability for one sampling mode (genre=None
    is the picker's own 🎲-random-genre default; a genre string is a
    firm-genre input), assuming setting/tone/composition are all left
    on 🎲 the way _freq_run_mode drives the composer.

    Built entirely from the real pool/filter functions and env-compat
    constants (imported, never re-derived), composed the same way
    compose() itself chains per-step uniform draws — venue, then tone,
    then the tone-filtered situation, then the situation-determined
    flourish — so "expected" tracks the system's actual (intentionally
    non-uniform) join structure rather than a flat 1/count baseline
    that would flag normal pool-size variation as a false failure.
    situation keys are (venue_name, situation_id).
    """
    node = pkg.scene_context_node
    RANDOM, NONE_OPT = node.RANDOM, node.NONE_OPT

    settings = node._load_settings()
    tones = node._load_tones()
    atmosphere = node._load_atmosphere()

    genre_pool = node._filter_by_genre(settings, RANDOM if genre is None else genre, NONE_OPT)
    venue_p = {v["name"]: 1.0 / len(genre_pool) for v in genre_pool}

    tone_keys = list(tones.keys())
    tone_p = {tk: 1.0 / len(tone_keys) for tk in tone_keys}

    situation_p = defaultdict(float)
    for v in genre_pool:
        p_v = venue_p[v["name"]]
        situations = v["situations"]
        for tk in tone_keys:
            p_t = 1.0 / len(tone_keys)
            compatible = tones[tk].get("compatible")
            if compatible:
                pool = [s for s in situations
                        if any(tag in s.get("tags", []) for tag in compatible)]
                if not pool:
                    # join-miss: tone yields to the venue's full pool —
                    # mirrors compose()'s own fallback branch.
                    pool = situations
            else:
                pool = situations
            p_s = 1.0 / len(pool)
            for s in pool:
                situation_p[(v["name"], s["id"])] += p_v * p_t * p_s

    ENV_COMPAT = node.ENV_COMPAT
    INDOOR_WINDOW_CHANCE = node.INDOOR_WINDOW_CHANCE
    INDOOR_FLOURISHES = node.INDOOR_FLOURISHES
    WINDOW_VIEWS = node.WINDOW_VIEWS

    def flourish_dist(situation):
        required_env = situation.get("env")
        if situation.get("indoor"):
            view_env = required_env if required_env in WINDOW_VIEWS else "neutral"
            dist = {WINDOW_VIEWS[view_env]: INDOOR_WINDOW_CHANCE}
            share = (1.0 - INDOOR_WINDOW_CHANCE) / len(INDOOR_FLOURISHES)
            for f in INDOOR_FLOURISHES:
                dist[f] = dist.get(f, 0.0) + share
            return dist
        if required_env:
            allowed = ENV_COMPAT.get(required_env, {required_env, "neutral"})
            pool = [f for f in atmosphere if f.get("env", "neutral") in allowed]
            if pool:
                return {f["text"]: 1.0 / len(pool) for f in pool}
        outdoor = [f for f in atmosphere if f.get("env", "neutral") != "indoor"]
        return {f["text"]: 1.0 / len(outdoor) for f in outdoor}

    by_name = {v["name"]: v for v in genre_pool}
    flourish_p = defaultdict(float)
    for (vname, sid), p_vs in situation_p.items():
        situation = next(s for s in by_name[vname]["situations"] if s["id"] == sid)
        for text, p in flourish_dist(situation).items():
            flourish_p[text] += p_vs * p

    return venue_p, dict(situation_p), tone_p, dict(flourish_p)


def _freq_run_mode(pkg, genre, n, seed0):
    """Draw N seeded generations through the real composer, tally
    venue / situation / tone / flourish outcomes."""
    node = pkg.scene_context_node
    composer = pkg.scene_context_composer.SceneContextComposer()
    RANDOM, NONE_OPT = node.RANDOM, node.NONE_OPT
    genre_arg = RANDOM if genre is None else genre

    venue_c, situation_c, tone_c, flourish_c = Counter(), Counter(), Counter(), Counter()
    for i in range(n):
        _, _, comp_json, _ = composer.compose(
            genre=genre_arg, genre2=NONE_OPT, tone=RANDOM, setting=RANDOM,
            composition=RANDOM, seed=seed0 + i, pose=False, positioning=False,
        )
        c = json.loads(comp_json)
        venue_c[c["venue"]] += 1
        situation_c[(c["venue"], c["situation_id"])] += 1
        tone_c[c["tone"]] += 1
        flourish_c[c["atmosphere"]] += 1
    return venue_c, situation_c, tone_c, flourish_c


_FREQ_DOMINANCE = 3.0


def _freq_audit_axis(label, counts, expected_p, n, fails):
    """Print one axis's table (dense, one line per entry — same
    register as the affinity table) and collect failures:
      - 0 draws on a reachable entry             ← DEAD
      - >3x expected share                       ← HOT
      - total draws for the axis != N
      - a drawn entry the model says is unreachable (drift check)
    """
    total = sum(counts.values())
    if total != n:
        fails.append(f"{label}: total draws {total} != N={n} (dropped/duplicated)")

    rows = []
    for key in set(counts) | set(expected_p):
        actual = counts.get(key, 0)
        exp_share = expected_p.get(key, 0.0)
        exp_count = exp_share * n
        flag = ""
        if key not in expected_p:
            flag = "  ← UNEXPECTED"
            fails.append(f"{label} {key!r}: {actual} draws, expected share 0.0 "
                         f"— drift between harness model and real join logic")
        elif actual == 0:
            flag = "  ← DEAD"
            fails.append(f"{label} {key!r}: 0 draws (expect ~{exp_count:.1f}) — unreachable")
        elif exp_count > 0 and actual > _FREQ_DOMINANCE * exp_count:
            flag = "  ← HOT"
            fails.append(f"{label} {key!r}: {actual} draws vs expect {exp_count:.1f} "
                         f"(>{_FREQ_DOMINANCE:.0f}x) — dominance")
        rows.append((key, actual, 100.0 * actual / n if n else 0.0, exp_count,
                     100.0 * exp_share, flag))

    rows.sort(key=lambda r: r[1], reverse=True)
    for key, actual, pct, exp_count, exp_pct, flag in rows:
        name = str(key)
        if len(name) > 38:
            name = name[:35] + "..."
        print(f"{name:<40} draws {actual:5d} ({pct:5.1f}%)"
              f"  expect {exp_count:6.1f} ({exp_pct:5.1f}%){flag}")


def frequency(args):
    """venue/situation/tone/flourish balance across the picker's
    🎲-genre default plus each firm genre it exposes. Returns exit
    code (0 pass, 1 fail — gates merges)."""
    pkg = _load_scene_pack()
    node = pkg.scene_context_node
    genres = [g for g in node.GENRE_OPTIONS if g != node.RANDOM]
    modes = [None] + genres

    n, seed0 = args.freq_n, args.freq_seed0
    all_fails = {}

    for genre in modes:
        label = genre if genre else "default (🎲 genre)"
        print(f"\n=== FREQUENCY: {label}  (N={n}, seed0={seed0}) ===")
        venue_p, situation_p, tone_p, flourish_p = _freq_expected(pkg, genre)
        venue_c, situation_c, tone_c, flourish_c = _freq_run_mode(pkg, genre, n, seed0)

        fails = []
        for axis, counts, expected_p in (
            ("venue", venue_c, venue_p),
            ("situation", situation_c, situation_p),
            ("tone", tone_c, tone_p),
            ("flourish", flourish_c, flourish_p),
        ):
            print(f"\n--- {axis} ---")
            _freq_audit_axis(axis, counts, expected_p, n, fails)

        if fails:
            all_fails[label] = fails

    if all_fails:
        print("\nFREQUENCY FAIL:")
        for label, fails in all_fails.items():
            for f_ in fails:
                print(f"  - [{label}] {f_}")
        return 1
    print("\nFREQUENCY PASS")
    return 0


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

    genre_n = Counter(t for v in venues for t in v.get("tags", []))
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
    for g in tags["genre"]:
        n = sum(
            1 for f in fams.values()
            if f.get("genre") in scene_tags.genre_with_parents(g, tags)
        )
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
    ap.add_argument("--frequency", action="store_true",
                    help="venue/situation/tone/flourish balance audit "
                         "against the real composer; exit 1 on fail")
    ap.add_argument("--freq-n", type=int, default=2000,
                    help="draws per sampling mode for --frequency")
    ap.add_argument("--freq-seed0", type=int, default=900000,
                    help="base seed for --frequency (own seed space, "
                         "separate from --seed0's roller draws)")
    args = ap.parse_args()

    if args.lint:
        sys.exit(lint())

    if args.frequency:
        sys.exit(frequency(args))

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
