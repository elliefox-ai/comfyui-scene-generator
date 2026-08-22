"""
Headless test harness for the Scene Character Roller (one node = one
character).

No ComfyUI required. Rolls a character at any setting combination and
dumps the assembled string plus the components JSON.

Run:
    python3 test_character_roller.py                          # default roll
    python3 test_character_roller.py --genre fantasy --consistency 1.0
    python3 test_character_roller.py --detail high --role healer
    python3 test_character_roller.py --name Abigail --pose
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scene_character_roller import SceneCharacterRoller, RANDOM


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--genre", default=RANDOM)
    p.add_argument("--consistency", type=float, default=0.7)
    p.add_argument("--detail", choices=["low", "high"], default="low")
    p.add_argument("--role", default="any")
    p.add_argument("--name", default="")
    p.add_argument("--pose", action="store_true")
    p.add_argument("--positioning", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    roller = SceneCharacterRoller()
    text, cj_raw, seed = roller.roll(
        args.genre, args.consistency, args.detail, args.role,
        args.name, args.pose, args.positioning, args.seed,
    )
    cj = json.loads(cj_raw)
    print(f"— character roll: genre={cj['genre']}{' (rolled)' if cj['genre_random'] else ''}"
          f"  target={cj['target_family']}  consistency={args.consistency}"
          f"  detail={args.detail}  role={args.role}  seed={args.seed} —")
    print()
    print(text)
    print()
    srcs = cj["outfit_sources"]
    print(f"words: {len(text.split())}  "
          f"pieces honoring target: {sum(1 for v in srcs.values() if v == cj['target_family'])}/{len(srcs)}")


if __name__ == "__main__":
    main()
