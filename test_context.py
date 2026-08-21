"""
Headless test harness for the Setting -> Situation x Tone x Atmosphere
context assembler. No ComfyUI required.

Run:
    python3 test_context.py                       # random sampling
    python3 test_context.py --setting pirate_ship
    python3 test_context.py --tone charming
    python3 test_context.py --genre historical
"""

import argparse
import json
import os
import random

BASE = os.path.join(os.path.dirname(__file__), "scene_context")


def load_settings():
    settings_dir = os.path.join(BASE, "settings")
    settings = {}
    for fname in sorted(os.listdir(settings_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(settings_dir, fname), encoding="utf-8") as f:
                data = json.load(f)
                settings[data["name"]] = data
    return settings


def load_tones():
    with open(os.path.join(BASE, "tones.json"), encoding="utf-8") as f:
        return json.load(f)


def load_atmosphere():
    with open(os.path.join(BASE, "atmosphere.json"), encoding="utf-8") as f:
        return json.load(f)["flourishes"]


def filter_settings_by_genre(settings, genre, rng):
    if not genre or genre == "random":
        return list(settings.values())
    matches = [s for s in settings.values() if genre in s.get("genre_tags", [])]
    return matches or list(settings.values())


def assemble_context(setting, tones, atmosphere, rng, tone_key=None):
    situation = rng.choice(setting["situations"])

    if tone_key and tone_key != "random":
        chosen_tone_key = tone_key
    else:
        chosen_tone_key = rng.choice(list(tones.keys()))
    tone = tones[chosen_tone_key]
    modifier = rng.choice(tone["modifiers"])

    flourish = rng.choice(atmosphere)

    context_str = f"{setting['subject_label']}, {situation['text']}, {modifier}, {flourish}"

    return {
        "setting": setting["name"],
        "situation_id": situation["id"],
        "tone": chosen_tone_key,
        "context": context_str,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setting", default=None, help="Force a specific setting name")
    parser.add_argument("--genre", default=None, help="Filter settings by genre tag")
    parser.add_argument("--tone", default=None, help="Force a specific tone key")
    parser.add_argument("--n", type=int, default=10, help="Number of samples")
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducibility")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    settings = load_settings()
    tones = load_tones()
    atmosphere = load_atmosphere()

    pool = [settings[args.setting]] if args.setting else filter_settings_by_genre(
        settings, args.genre, rng
    )

    print(f"— Sampling {args.n} contexts —")
    print(f"  setting filter: {args.setting or args.genre or 'none'}   tone filter: {args.tone or 'random'}")
    print()

    for i in range(args.n):
        setting = rng.choice(pool)
        result = assemble_context(setting, tones, atmosphere, rng, tone_key=args.tone)
        print(f"[{i+1:>2}] ({result['setting']} / {result['tone']} / {result['situation_id']})")
        print(f"     {result['context']}")
        print()


if __name__ == "__main__":
    main()
