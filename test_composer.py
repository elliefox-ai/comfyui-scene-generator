"""
Headless test harness for the Scene Context Composer (v2).

No ComfyUI required. Exercises the full two-tier setting axis:
archetype labels, explicit venues, genre flavor, tone, composition.

Run:
    python3 test_composer.py                        # random sampling
    python3 test_composer.py --setting "on the coast"
    python3 test_composer.py --setting harbor_tavern
    python3 test_composer.py --genre modern --n 20
    python3 test_composer.py --composition face_off --tone violent
    python3 test_composer.py --cast 2 --ambient "a giant rubber duck floating impossibly large"
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scene_context_composer import SceneContextComposer, RANDOM, NONE_OPT

CAST_SAMPLES = [
    "a tall woman in a weathered duster",
    "a wiry man with rope-scarred hands",
    "an older woman in mechanic's coveralls",
    "a broad-shouldered sailor in a knit cap",
]


def _selfcheck():
    # Toggle invariants (include_setting / include_context). Exit 1 on fail.
    compose = SceneContextComposer.compose
    seed = 4242

    def draw(**flags):
        return compose(None, RANDOM, NONE_OPT, RANDOM, RANDOM, RANDOM, seed, **flags)

    ctx_d, _, cj_d, _ = draw()
    c_d = json.loads(cj_d)
    venue_words = c_d["setting"].replace("_", " ")
    frag = c_d["situation_text"].strip().rstrip(".").strip()
    frag_cap = frag[:1].upper() + frag[1:]

    def has_frag(s):
        return frag in s or frag_cap in s

    ctx_x, _, cj_x, _ = draw(include_setting=True, include_context=True)
    ctx_s, _, cj_s, _ = draw(include_setting=False)
    c_s = json.loads(cj_s)
    ctx_c, _, cj_c, _ = draw(include_context=False)
    c_c = json.loads(cj_c)
    ctx_n, _, cj_n, _ = draw(include_setting=False, include_context=False)

    checks = [
        ("default == explicit both-on", ctx_d == ctx_x and cj_d == cj_x),
        ("default: venue present", venue_words in ctx_d),
        ("default: situation present", has_frag(ctx_d)),
        ("setting-off: venue absent", venue_words not in ctx_s),
        ("setting-off: situation present", has_frag(ctx_s)),
        ("setting-off: capitalized opener", ctx_s[:1].isupper()),
        ("setting-off: venue still rolled", c_s["setting"] == c_d["setting"]),
        ("context-off: situation absent", not has_frag(ctx_c)),
        ("context-off: venue present", venue_words in ctx_c),
        ("context-off: situation still rolled", c_c["situation_id"] == c_d["situation_id"]),
        ("both-off: mood opener", ctx_n.startswith("The mood is")),
        ("both-off: venue absent", venue_words not in ctx_n),
        ("both-off: situation absent", not has_frag(ctx_n)),
        ("flags recorded in components",
            c_d["include_setting"] is True and c_d["include_context"] is True
            and c_s["include_setting"] is False and c_c["include_context"] is False),
    ]
    bad = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {name}")
    if bad:
        print(f"TOGGLE SELFCHECK FAILED: {bad}")
        sys.exit(1)
    print("  toggle selfcheck: all invariants hold")


def main():
    _selfcheck()

    parser = argparse.ArgumentParser()
    parser.add_argument("--genre", default=RANDOM)
    parser.add_argument("--genre2", default=NONE_OPT)
    parser.add_argument("--tone", default=RANDOM)
    parser.add_argument(
        "--setting",
        default=RANDOM,
        help="Archetype label ('on the coast') or venue name (harbor_tavern)",
    )
    parser.add_argument("--composition", default=RANDOM)
    parser.add_argument("--n", type=int, default=10, help="Number of samples")
    parser.add_argument("--seed", type=int, default=None, help="Master seed")
    parser.add_argument(
        "--cast", type=int, default=0,
        help="Wire N sample characters with pose+positioning staging "
             "(exercises the _stage_characters path)",
    )
    parser.add_argument(
        "--ambient", default="",
        help="Wire this ambient fragment (exercises the ambient slot)",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    compose = SceneContextComposer.compose

    print(f"— Sampling {args.n} v2 contexts —")
    print(
        f"  setting: {args.setting}   genre: {args.genre}/{args.genre2}   "
        f"tone: {args.tone}   comp: {args.composition}"
    )
    print()

    for i in range(args.n):
        seed = rng.randrange(2**32)
        kwargs = {}
        if args.cast:
            kwargs["pose"] = True
            kwargs["positioning"] = True
            for j in range(args.cast):
                kwargs[f"character_{j + 1}"] = CAST_SAMPLES[j % len(CAST_SAMPLES)]
        if args.ambient:
            kwargs["ambient"] = args.ambient
        ctx, rp, cj, _ = compose(
            None, args.genre, args.genre2, args.tone,
            args.setting, args.composition, seed, **kwargs,
        )
        c = json.loads(cj)
        notes = []
        if args.cast:
            notes.append(f"cast {args.cast} staged")
        if args.ambient:
            notes.append("ambient wired")
        if c["archetype_narrowed"]:
            notes.append("archetype gated the pool")
        if c["genre_narrowed"]:
            notes.append("genre flavored the pool")
        tail = f"   [{'; '.join(notes)}]" if notes else ""
        print(f"[{i+1:>2}] seed {seed:<10} ({c['venue']} / {c['tone']}){tail}")
        print(f"     {ctx}")
        print()


if __name__ == "__main__":
    main()
