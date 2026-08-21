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
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scene_context_composer import SceneContextComposer, RANDOM, NONE_OPT


def main():
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
        ctx, rp, cj, _ = compose(
            None, args.genre, args.genre2, args.tone,
            args.setting, args.composition, seed,
        )
        c = json.loads(cj)
        notes = []
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
