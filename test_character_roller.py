"""
Headless test harness for the Scene Character Roller (one node = one
character).

No ComfyUI required. Rolls a character at any setting combination and
dumps the assembled string plus the components JSON.

Run:
    python3 test_character_roller.py                          # default roll
    python3 test_character_roller.py --genre fantasy --consistency 1.0
    python3 test_character_roller.py --face-detail high --body-detail high --body-type muscular --role healer
    python3 test_character_roller.py --name Abigail --pose
    python3 test_character_roller.py --age older --sex female --race black
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
    p.add_argument("--face-detail", dest="face_detail", choices=["low", "high"], default="low")
    p.add_argument("--body-detail", dest="body_detail", choices=["minimal", "low", "high"], default="low")
    p.add_argument("--body-type", dest="body_type", default="random")
    p.add_argument("--role", default="any")
    p.add_argument("--name", default="")
    p.add_argument("--pose", action="store_true")
    p.add_argument("--positioning", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--age", default=RANDOM)
    p.add_argument("--sex", default=RANDOM)
    p.add_argument("--race", default=RANDOM)
    args = p.parse_args()

    roller = SceneCharacterRoller()
    text, cj_raw, seed = roller.roll(
        args.genre, args.consistency, args.face_detail, args.body_detail, args.body_type, args.role,
        args.name, args.pose, args.positioning, args.seed,
        args.age, args.sex, args.race,
    )
    cj = json.loads(cj_raw)
    ident = cj["identity"]
    print(f"— character roll: genre={cj['genre']}{' (rolled)' if cj['genre_random'] else ''}"
          f"  target={cj['target_family']}  consistency={args.consistency}"
          f"  face={args.face_detail} body={args.body_detail}/{args.body_type}  role={args.role}  seed={args.seed} —")
    print(f"  identity: {ident['phrase']}"
          f"  (age {'🎲' if ident['age_random'] else 'set'},"
          f" sex {'🎲' if ident['sex_random'] else 'set'},"
          f" race {'🎲' if ident['race_random'] else 'set'})")
    print()
    print(text)
    print()
    srcs = cj["outfit_sources"]
    print(f"words: {len(text.split())}  "
          f"pieces honoring target: {sum(1 for v in srcs.values() if v == cj['target_family'])}/{len(srcs)}")


if __name__ == "__main__":
    main()
