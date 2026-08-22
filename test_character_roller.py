"""
Headless test harness for the Scene Character Roller.

No ComfyUI required. Rolls casts at any setting combination and dumps
the assembled strings plus the components JSON.

Run:
    python3 test_character_roller.py                       # default cast
    python3 test_character_roller.py --genre fantasy --consistency 1.0
    python3 test_character_roller.py --detail high --count 1
    python3 test_character_roller.py --names "Abigail, Bernadette"
"""

import argparse
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))

from scene_character_roller import SceneCharacterRoller, RANDOM


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--genre", default=RANDOM)
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--consistency", type=float, default=0.7)
    p.add_argument("--detail", choices=["low", "high"], default="low")
    p.add_argument("--role", default="any")
    p.add_argument("--names", default="")
    p.add_argument("--pose", action="store_true")
    p.add_argument("--positioning", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    roller = SceneCharacterRoller()
    out = roller.roll(
        args.genre, args.count, args.consistency, args.detail,
        args.role, args.names, args.pose, args.positioning, args.seed,
    )
    cj = json.loads(out[4])
    print(f"— cast roll: genre={cj['genre']}{' (rolled)' if cj['genre_random'] else ''}"
          f"  family={cj['shared_family']}  consistency={args.consistency}"
          f"  detail={args.detail}  role={args.role}  seed={args.seed} —")
    print()
    for c in cj["characters"]:
        rogue = "" if c["shared_family"] else "  [rogue family]"
        print(f"[{c['index']}] {c['text']}{rogue}")
        print(f"    family={c['family']}  palette={c['palette']}  roles={c['roles']}")
        print()
    print(f"word counts: {[len(c['text'].split()) for c in cj['characters']]}")


if __name__ == "__main__":
    main()
